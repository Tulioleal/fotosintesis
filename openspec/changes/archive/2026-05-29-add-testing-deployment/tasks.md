## 1. Testing And Deployment

- [x] 1.1 Add backend unit tests for auth, taxonomy validation, providers, RAG filters, ingestion and reminders
- [x] 1.2 Add backend integration tests for health, metrics, chat, plant identification, garden, reminders, light measurements and evaluation endpoints
- [x] 1.3 Add frontend component tests for forms, Home, candidate selection, profile, garden, reminders and light meter states
- [x] 1.4 Add Playwright end-to-end tests for auth, Home navigation, identification to profile, garden save, reminder creation, assistant RAG and light fallback
- [x] 1.5 Add OpenTofu project structure for GCP infrastructure
- [x] 1.6 Add OpenTofu modules for GKE, Artifact Registry, Cloud SQL PostgreSQL, Cloud Storage, Secret Manager, IAM and baseline monitoring
- [x] 1.7 Add environment configuration for dev/prod with variables, outputs and remote state documentation
- [x] 1.8 Add Kubernetes manifests for frontend, backend, migrations/jobs and required runtime config
- [x] 1.9 Connect OpenTofu outputs to deployment configuration for GKE, database, storage and secrets
- [x] 1.10 Document `tofu init`, `tofu plan`, `tofu apply`, deployment, rollback and `tofu destroy`
- [x] 1.11 Document local Docker Compose separately from cloud IaC deployment
