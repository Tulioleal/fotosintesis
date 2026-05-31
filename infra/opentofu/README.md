# OpenTofu GCP Infrastructure

This directory provisions cloud infrastructure for Fotosintesis AI. Workload deployment stays in `deploy/k8s` and consumes the outputs from the selected environment.

Use one environment at a time:

```bash
cd infra/opentofu/envs/dev
tofu init
tofu plan -var-file=terraform.tfvars.example
```

For remote state, copy `backend.tf.example` to `backend.tf` in the environment directory and replace the bucket/prefix values with your own state bucket.
