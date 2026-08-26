#!/bin/sh
# Validate the durable-job switch combination for a deployment.
#
# Usage: validate-job-switches.sh <producer_enabled> <worker_enabled> [paused_deployment]
#
# Every input must be exactly "true" or "false". The only accepted
# combinations are:
#   producer=true  worker=true  paused=false   normal active deployment
#   producer=false worker=true  paused=false   worker-only active deployment
#   producer=false worker=false paused=true    approved paused deployment
# Everything else is rejected. An active deployment (worker enabled) may only
# run with paused=false, and a paused deployment requires both switches to be
# disabled. The workflow skips the active-consumer readiness gate only when
# paused=true, which this validator proves implies both switches are disabled.
set -eu

producer="$1"
worker="$2"
paused="${3:-false}"

for value in "$producer" "$worker" "$paused"; do
  if [ "$value" != "true" ] && [ "$value" != "false" ]; then
    echo "invalid boolean value: $value" >&2
    exit 1
  fi
done

if [ "$paused" = "true" ]; then
  if [ "$producer" = "false" ] && [ "$worker" = "false" ]; then
    echo "paused deployment: both switches disabled with explicit approval"
    exit 0
  fi
  echo "paused deployment requires both producer and worker to be disabled" >&2
  exit 1
fi

if [ "$worker" = "true" ]; then
  echo "normal deployment path: worker enabled and ready"
  exit 0
fi

echo "worker disabled requires an explicitly approved paused deployment" >&2
exit 1
