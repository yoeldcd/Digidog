# Archeitectural distribution patterns for Deployment Assets

/{deployment_infrastructure, e.g. deployment}
├── /{container_image_repository, e.g. docker}
│   └── (file struct e.g: deployment/docker/...)
│       └── - [service_name]_runtime_image.dockerfile # MUST: define container builds for production deployment. MUST NOT: copy databases, store local secrets, or include source map files.
│           - `[ServiceName]RuntimeImage` (Stage): build stage for container build construction
│
├── /{ci_cd_pipeline_repository, e.g. pipelines}
│   └── (file struct e.g: deployment/pipelines/...)
│       └── - [pipeline_name]_ci_pipeline.yaml # MUST: run automated testing, linting, and scanning on source changes. MUST NOT: deploy release artifacts without validation steps.
│           - `[PipelineName]CiPipeline` (Descriptor): descriptor for automated CI/CD pipeline steps
│
└── /{runtime_orchestration_repository, e.g. orchestration}
    └── (file struct e.g: deployment/orchestration/...)
        ├── - [service_name]_k8s_manifest.yaml # MUST: define target service network deployment and cluster topology. MUST NOT: contain unencrypted secret credentials.
        │   - `[ServiceName]K8sManifest` (Descriptor): descriptor for container deployment orchestration
        └── - [migration_name]_schema_migration.yaml # MUST: document structural database schema transformations. MUST NOT: execute query updates directly without transactional control.
            - `[MigrationName]SchemaMigration` (Descriptor): descriptor for database schema execution migrations
