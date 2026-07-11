## MODIFIED Requirements

### Requirement: Persistence and storage baseline

The system SHALL include PostgreSQL + pgvector migrations and an object storage abstraction for user images and temporary identification assets. The object storage abstraction SHALL support local filesystem storage for development and GCS-backed storage for GCP runtime environments.

#### Scenario: Baseline migration applied

- **WHEN** database migrations are applied to a clean local database
- **THEN** the system enables the baseline schema and vector extension needed by later features

#### Scenario: Local object storage remains available
- **WHEN** the backend runs in local development configuration
- **THEN** user image and temporary identification assets are stored through the local filesystem storage implementation without requiring GCP credentials

#### Scenario: GCP object storage uses GCS
- **WHEN** the backend runs in a GCP environment with object storage provider configured for GCS
- **THEN** user image and temporary identification assets are stored in the configured GCS bucket through the backend storage abstraction

#### Scenario: GCS access uses workload identity
- **WHEN** backend GCS storage is used in GKE
- **THEN** storage access is authorized through the backend workload identity service account and does not require static object storage access keys in Kubernetes secrets
