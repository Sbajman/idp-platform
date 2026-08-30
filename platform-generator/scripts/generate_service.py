#!/usr/bin/env python3

import sys
from pathlib import Path
import yaml


def load_service_definition(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def validate_service(service):
    required_fields = [
        ("metadata", "name"),
        ("spec", "owner"),
        ("spec", "image"),
        ("spec", "runtime"),
    ]

    for path in required_fields:
        current = service

        for key in path:
            if key not in current:
                raise ValueError(
                    f"Missing required field: {'.'.join(path)}"
                )
            current = current[key]


def generate_values(service):
    spec = service["spec"]

    values = {
        "replicaCount": spec["environments"]["local"]["replicas"],

        "image": {
            "repository": spec["image"]["repository"],
            "tag": str(spec["image"]["tag"]),
            "pullPolicy": "IfNotPresent",
        },

        "service": {
            "type": "ClusterIP",
            "port": spec["runtime"]["port"],
        },

        "env": {
            "ENVIRONMENT": "local",
            "SERVICE_NAME": service["metadata"]["name"],
        },

        "resources": spec.get("resources", {}),
    }

    return values


def generate_base_kustomization():
    return {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization",

        "helmGlobals": {
            "chartHome": "../../../../platform-charts"
        },

        "helmCharts": [
            {
                "name": "microservice",
                "releaseName": "{{SERVICE_NAME}}",
                "namespace": "demo",
                "valuesFile": "values.yaml",
            }
        ],
    }


def generate_overlay(service):
    service_name = service["metadata"]["name"]
    owner = service["spec"]["owner"]

    return {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization",

        "resources": [
            "../../base"
        ],

        "namespace": "demo",

        "labels": [
            {
                "pairs": {
                    "platform.example.com/environment": "local",
                    "platform.example.com/application": service_name,
                    "platform.example.com/managed-by": "idp-platform",
                },
                "includeSelectors": False,
            }
        ],

        "commonAnnotations": {
            "platform.example.com/environment": "local",
            "platform.example.com/owner": owner,
        },
    }


def write_yaml(path, data):
    with open(path, "w") as f:
        yaml.safe_dump(
            data,
            f,
            sort_keys=False,
            default_flow_style=False,
        )


def main():

    if len(sys.argv) != 3:
        print(
            "Usage: generate_service.py "
            "<service.yaml> <output-directory>"
        )
        sys.exit(1)

    service_file = Path(sys.argv[1])
    output_root = Path(sys.argv[2])

    print(f"Loading service definition: {service_file}")

    service = load_service_definition(service_file)

    validate_service(service)

    service_name = service["metadata"]["name"]

    print(f"Generating GitOps configuration for: {service_name}")

    service_dir = output_root / service_name

    base_dir = service_dir / "base"
    overlay_dir = service_dir / "overlays" / "local"

    base_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)

    # Generate values.yaml
    values = generate_values(service)

    write_yaml(
        base_dir / "values.yaml",
        values,
    )

    # Generate base kustomization.yaml
    base_kustomization = generate_base_kustomization()

    # Replace placeholder
    base_kustomization["helmCharts"][0]["releaseName"] = service_name

    write_yaml(
        base_dir / "kustomization.yaml",
        base_kustomization,
    )

    # Generate local overlay
    overlay = generate_overlay(service)

    write_yaml(
        overlay_dir / "kustomization.yaml",
        overlay,
    )

    print("\nGenerated:")

    print(base_dir / "values.yaml")
    print(base_dir / "kustomization.yaml")
    print(overlay_dir / "kustomization.yaml")

    print("\nGeneration complete.")


if __name__ == "__main__":
    main()