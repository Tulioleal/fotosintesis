#!/usr/bin/env sh
set -eu

if [ "$#" -ne 4 ]; then
  printf 'Usage: %s <namespace> <deployment> <container> <timeout>\n' "$0" >&2
  exit 2
fi

namespace="$1"
deployment="$2"
container="$3"
timeout="$4"
selector="app.kubernetes.io/name=$deployment"

if kubectl rollout status "deployment/$deployment" -n "$namespace" --timeout="$timeout"; then
  exit 0
fi

printf 'Rollout failed for %s\n' "$deployment" >&2
kubectl describe "deployment/$deployment" -n "$namespace" >&2 || true
kubectl get replicasets -n "$namespace" -l "$selector" -o wide >&2 || true
kubectl get pods -n "$namespace" -l "$selector" -o wide >&2 || true

pods="$(kubectl get pods -n "$namespace" -l "$selector" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || true)"
for pod in $pods; do
  kubectl logs "$pod" -n "$namespace" -c "$container" --tail=200 >&2 || true
  kubectl logs "$pod" -n "$namespace" -c "$container" --previous --tail=200 >&2 || true
  if [ "$container" = "backend" ] || [ "$container" = "worker" ]; then
    kubectl logs "$pod" -n "$namespace" -c cloud-sql-proxy --tail=200 >&2 || true
  fi
  kubectl describe pod "$pod" -n "$namespace" >&2 || true
done
kubectl get events -n "$namespace" --sort-by=.lastTimestamp >&2 || true
exit 1
