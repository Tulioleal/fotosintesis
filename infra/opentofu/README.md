# OpenTofu GCP Infrastructure

This directory provisions cloud infrastructure for Fotosintesis AI. Workload deployment stays in `deploy/k8s` and consumes the outputs from the selected environment.

Use one environment at a time:

```bash
cd infra/opentofu/envs/dev
tofu init \
  -backend-config="bucket=${DEV_TF_STATE_BUCKET}" \
  -backend-config="prefix=fotosintesis/dev"
tofu plan -var-file=terraform.tfvars
```

Each env root declares `backend "gcs" {}`. Bucket and prefix are supplied
via `-backend-config` at init time. Do not commit credentials or generated
state files.
