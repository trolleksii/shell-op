#!/usr/bin/env bash

source /hooks/common/functions.sh

hook::config() {
cat <<-EOF
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
EOF
}

hook::trigger() {
  type=$(jq -r '.[0].type' $BINDING_CONTEXT_PATH)
  if [[ $type == "Synchronization" ]] ; then
    echo Got Synchronization event
    exit 0
  fi

  count=$(jq '. | length' $BINDING_CONTEXT_PATH)

  for ((i=0; i<$count; i++)); do
    app=$(jq -r '.['$i'].object.metadata.name' $BINDING_CONTEXT_PATH)
    namespace=$(jq -r '.['$i'].object.metadata.namespace' $BINDING_CONTEXT_PATH)

    previous_health=$(jq -r '.['$i'].object.metadata.annotations.previousHealthState' $BINDING_CONTEXT_PATH)
    previous_revision=$(jq -r '.['$i'].object.metadata.annotations.previousRevision' $BINDING_CONTEXT_PATH)
    current_health=$(jq -r '.['$i'].object.status.health.status' $BINDING_CONTEXT_PATH)
    current_revision=$(jq -r '.['$i'].object.status.sync.revision' $BINDING_CONTEXT_PATH)
    phase=$(jq -r '.['$i'].object.status.operationState.phase' $BINDING_CONTEXT_PATH)
    sync=$(jq -r '.['$i'].object.status.sync.status' $BINDING_CONTEXT_PATH)

    curl -s -X POST -d "{\"app\":\"$app\",\"revision\":\"$revision\",\"health\":\"$current_health\",\"sync\":\"$sync\",\"phase\":\"$phase\"}" http://localhost:8080

    #
    if [ $previous_health == "null" ]; then
      kubectl -n $namespace annotate application $app previousHealthState=$current_health previousRevision=$current_revision
      exit 0
    fi
    if [ $current_health == "Degraded" ] && [ $previous_health != "Degraded" ]; then
      echo "Application $app has degraded"
      kubectl -n $namespace annotate --overwrite application $app previousHealthState=$current_health
      exit 0
    fi
    if [ $current_health == "Healthy" ] && [ $previous_health == "Degraded" ]; then
      kubectl -n $namespace annotate --overwrite application $app previousHealthState=$current_health
      echo "Application $app has recovered"
      exit 0
    fi
  done
}

common::run_hook "$@"