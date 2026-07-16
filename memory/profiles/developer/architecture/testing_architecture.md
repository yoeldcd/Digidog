# Archeitectural distribution patterns for (Testing Codebase)

/{test_suite, e.g. tests}
├── /{unit_test_subdomain, e.g. unit}
│   ├── /{mocking_repository, e.g. mocks}
│   │   └── (file struct e.g: tests/unit/mocks/...)
│   │       └── - [port_name]_mock.{ext} # MUST: provide mock doubles for outbound ports to isolate code unit testing. MUST NOT: invoke real database storage or perform network calls.
│   │           - `[PortName]Mock` (Class): class for mock doubles behavior
│   └── /{specification_repository, e.g. specifications}
│       └── (file struct e.g: tests/unit/specifications/...)
│           ├── - [model_name]_unit_test.{ext} # MUST: verify business models and invariant logic. MUST NOT: write data stores, depend on other tests, or call external services.
│           │   - `[ModelName]UnitTest` (Class): class for verifying model behavior
│           └── - [service_name]_unit_test.{ext} # MUST: verify application services orchestration. MUST NOT: bypass mocks or require server environments.
│               - `[ServiceName]UnitTest` (Class): class for verifying service flow orchestration
│
├── /{integration_test_subdomain, e.g. integration}
│   └── /{adapter_integration_repository, e.g. adapters}
│       └── (file struct e.g: tests/integration/adapters/...)
│           ├── - [repository_name]_integration_test.{ext} # MUST: verify repository adapters against isolated databases. MUST NOT: connect to production data stores or skip database cleanup.
│           │   - `[RepositoryName]IntegrationTest` (Class): class for verifying repository execution
│           └── - [controller_name]_integration_test.{ext} # MUST: verify HTTP controllers, API endpoints, or routing. MUST NOT: bypass authorization mocks or connect to live external servers.
│               - `[ControllerName]IntegrationTest` (Class): class for verifying controller boundary mappings
│
└── /{test_data_builder_subdomain, e.g. fixtures}
    └── /{data_builder_repository, e.g. builders}
        └── (file struct e.g: tests/fixtures/builders/...)
            └── - [model_name]_builder.{ext} # MUST: construct valid test entity templates with overridden fields. MUST NOT: write databases or generate nondeterministic attributes.
                - `[ModelName]Builder` (Class): class for building entity test data
