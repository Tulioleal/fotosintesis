#!/bin/sh
# Verify GKE network policy enforcement with one allowed and one denied probe.
#
# Usage: verify-network-policy.sh <namespace> <backend-health-url>
#
# The cluster must already have the application NetworkPolicies applied
# (deploy/k8s/base/05-network-policies.yaml). Under the namespace default-deny
# baseline:
#   * The allow probe is labelled app.kubernetes.io/name=fotosintesis-smoke, so
#     the smoke egress policy lets it reach the backend /health endpoint and the
#     backend ingress policy accepts it. The probe must succeed.
#   * The deny probe carries no allow labels, so default-deny egress blocks its
#     connection to the backend. The probe must fail to connect.
#
# This is the enforcement proof required by the enforce-gke-network-segmentation
# change: presence of policy YAML alone is not proof that enforcement works.
set -eu

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <namespace> <backend-health-url>" >&2
  exit 2
fi

namespace="$1"
backend_url="$2"
allow_pod="fotosintesis-np-allow-probe"
deny_pod="fotosintesis-np-deny-probe"

cleanup() {
  kubectl delete pod "$allow_pod" -n "$namespace" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  kubectl delete pod "$deny_pod" -n "$namespace" --ignore-not-found --wait=false >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

echo "Network policy: verifying an allowed connection succeeds"
if ! kubectl run "$allow_pod" \
    -n "$namespace" \
    --image=curlimages/curl:8.10.1 \
    --restart=Never \
    --labels="app.kubernetes.io/name=fotosintesis-smoke" \
    --attach=true \
    --pod-running-timeout=120s \
    --command -- curl \
    --silent \
    --show-error \
    --fail \
    --connect-timeout 5 \
    --max-time 15 \
    "$backend_url"; then
  echo "::error::Allowed network-policy probe failed; expected the backend /health endpoint to be reachable." >&2
  kubectl logs "$allow_pod" -n "$namespace" >&2 || true
  kubectl describe pod "$allow_pod" -n "$namespace" >&2 || true
  exit 1
fi
echo "Network policy: allowed probe succeeded"

echo "Network policy: verifying an unexpected connection is denied"
if kubectl run "$deny_pod" \
    -n "$namespace" \
    --image=curlimages/curl:8.10.1 \
    --restart=Never \
    --attach=true \
    --pod-running-timeout=120s \
    --command -- curl \
    --silent \
    --show-error \
    --connect-timeout 5 \
    --max-time 15 \
    "$backend_url" >/dev/null 2>&1; then
  echo "::error::Denied network-policy probe succeeded; default-deny egress is not being enforced." >&2
  kubectl logs "$deny_pod" -n "$namespace" >&2 || true
  kubectl describe pod "$deny_pod" -n "$namespace" >&2 || true
  exit 1
fi
echo "Network policy: denied probe was blocked as expected"
echo "Network policy enforcement verified in namespace $namespace"
