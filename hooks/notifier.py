#!/usr/bin/env python

import json, os, requests, sys

from kubernetes import client, config

CONFIG='''---
configVersion: v1
kubernetes:
- name: onArgoAppUpdated
  apiVersion: argoproj.io/v1alpha1
  kind: Application
  executeHookOnEvent:
  - Modified
  namespace:
    nameSelector:
      matchNames:
      - argocd
  executeHookOnSynchronization: false
  jqFilter: "{health: .status.health.status, phase: .status.operationState.phase, revision: .status.sync.revision, status: .status.sync.status}"
'''


def annotate_argoapp(name, namespace, annotations):
    body = {
        "metadata": {
            "annotations": annotations
        }
    }
    api_instance.patch_namespaced_custom_object(
        group='argoproj.io',
        version='v1alpha1',
        plural='applications',
        namespace=namespace,
        name=name,
        body=body)

def process(event):
    print("Processing: ", event["name"])
    annotations = {
        "ple-argo-notifier.previousRevision": event["revision"],
        "ple-argo-notifier.previousHealth": event["health"],
    }
    annotate_argoapp(
        name = event["name"],
        namespace = event["namespace"],
        annotations = annotations
    )
    requests.post("http://localhost:8080", data=json.dumps({
        "name": event["name"],
        "revision_changed": event["revision_changed"],
        "revision": event["revision"],
        "health_changed": event["health_changed"],
        "health": event["health"]
    }))

def handle_events():
    binding_context_path = os.environ.get("BINDING_CONTEXT_PATH")
    with open(binding_context_path, 'r') as f:
        binding_contexts = json.load(f)

    validated_events = map(
        lambda c: {
            "name": c["object"]["metadata"]["name"],
            "namespace": c["object"]["metadata"]["namespace"],
            "health": c["object"]["status"]["health"]["status"],
            "revision": c["object"]["status"]["sync"]["revision"],
            "health_changed": c["object"]["metadata"]["annotations"].get("ple-argo-notifier.previousHealth", None) != c["object"]["status"]["health"]["status"],
            "revision_changed": c["object"]["metadata"]["annotations"].get("ple-argo-notifier.previousRevision", None) != c["object"]["status"]["sync"]["revision"],
        },
        filter(
            lambda c: all([
                c["object"]["status"].get("sync", {}).get("status", "") == "Synced",
                c["object"]["status"].get("operationState", {}).get("phase", "Running") != "Running",
                c["object"]["status"].get("health", {}).get("status", "Progressing") != "Progressing",
                any([
                    c["object"]["metadata"]["annotations"].get("ple-argo-notifier.previousRevision", None) != c["object"]["status"].get("sync", {}).get("revision", None),
                    c["object"]["metadata"]["annotations"].get("ple-argo-notifier.previousHealth", None) != c["object"]["status"].get("health", {}).get("status", None),
                ])
            ]),
            binding_contexts
        )
    )

    for event in validated_events:
        process(event)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--config":
        print(CONFIG)
    else:
        config.load_incluster_config()
        api_instance = client.CustomObjectsApi()
        argocd_domain = os.environ.get("ARGOCD_DOMAIN")
        environment = os.environ.get("ENVIRONMENT")
        region = os.environ.get("REGION")
        github_token = os.environ.get("GITHUB_TOKEN")
        slack_token = os.environ.get("SLACK_TOKEN")
        handle_events()
