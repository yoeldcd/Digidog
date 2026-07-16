# Generic Modular CLI Project Tree — Clean Architecture

Organize the codebase tree to following verticals sliced Clean Architecture ( under **featurizer segmentation**):

## Tree

```powershell
{codebase_root}/ # Repository root for a generic, modular CLI application.
├── [domain]/ # Owns enterprise business rules, pure domain behavior, and framework-independent business concepts.
│   └── (feat/sub_feat/...)/ # MUST: Group domain code by feature and optional sub-feature without coupling it to delivery or storage. (e.g billing/invoices)
│       ├── [models]/ # MUST: Represent domain concepts as behavior-rich models instead of anemic data bags. (e.g order)
│       │   ├── [name]_model.{ext} # INCLUDE: domain state, invariants, and behavior like (e.g [`OrderModel`, `calculate_total`, `mark_as_paid`]). NOT INCLUDE: persistence annotations, CLI parsing, HTTP payloads, database queries, or framework decorators.
│       │   ├── [name]_value.{ext} # INCLUDE: immutable value objects and self-validation like (e.g [`MoneyValue`, `EmailValue`, `normalize_currency`]). NOT INCLUDE: external service calls, mutable global state, or serialization framework details.
│       │   ├── [name]_enum.{ext} # INCLUDE: finite business states or categories like (e.g [`OrderStatus`, `PaymentMethod`, `DEFAULT_STATUS`]). NOT INCLUDE: UI labels, terminal colors, storage codes, or transport-specific names.
│       │   └── [name]_factory.{ext} # INCLUDE: safe construction rules for complex domain models like (e.g [`OrderFactory`, `create_from_items`, `DEFAULT_TAX_POLICY`]). NOT INCLUDE: dependency injection, database access, CLI flags, or infrastructure configuration.
│       ├── [events]/ # MUST: Define facts that already happened inside the domain. (e.g payments)
│       │   ├── [name]_event.{ext} # INCLUDE: immutable domain event data like (e.g [`PaymentCapturedEvent`, `occurred_at`, `aggregate_id`]). NOT INCLUDE: event bus publishing, retry logic, queue names, or handler orchestration.
│       │   └── [name]_event_type.{ext} # INCLUDE: canonical event names or event discriminators like (e.g [`PaymentEventType`, `PAYMENT_CAPTURED`, `to_event_name`]). NOT INCLUDE: broker topic configuration, JSON schemas tied to vendors, or CLI output labels.
│       ├── [rules]/ # MUST: Hold explicit business rules that models and services can reuse. (e.g pricing)
│       │   ├── [name]_rule.{ext} # INCLUDE: atomic business predicates or calculations like (e.g [`DiscountRule`, `is_eligible`, `MAX_DISCOUNT_RATE`]). NOT INCLUDE: repository calls, process execution, terminal prompts, or configuration file reads.
│       │   └── [name]_policy.{ext} # INCLUDE: replaceable domain decisions and strategy-like rules like (e.g [`RefundPolicy`, `can_refund`, `REFUND_WINDOW_DAYS`]). NOT INCLUDE: environment variables, user-interface wording, or framework-specific policy classes.
│       ├── [specs]/ # MUST: Express composable domain conditions used to select or validate models. (e.g eligibility)
│       │   └── [name]_spec.{ext} # INCLUDE: pure boolean domain specifications like (e.g [`ActiveSubscriptionSpec`, `is_satisfied_by`, `MIN_ACTIVE_DAYS`]). NOT INCLUDE: SQL filters, ORM query builders, or CLI option validation.
│       ├── [services]/ # MUST: Place domain behavior that naturally spans multiple models. (e.g allocation)
│       │   └── [name]_domain_service.{ext} # INCLUDE: stateless domain operations like (e.g [`InventoryAllocatorDomainService`, `allocate`, `RESERVATION_LIMIT`]). NOT INCLUDE: transaction management, logging setup, application orchestration, or external I/O.
│       ├── [errors]/ # MUST: Define domain failures in business language. (e.g validation)
│       │   ├── [name]_error.{ext} # INCLUDE: domain-specific exceptions/results like (e.g [`InvalidOrderError`, `reason`, `INVALID_STATE`]). NOT INCLUDE: HTTP status codes, shell exit codes, database error classes, or stack-trace formatting.
│       │   └── [name]_violation.{ext} # INCLUDE: structured invariant violation details like (e.g [`PriceViolation`, `field`, `MIN_PRICE`]). NOT INCLUDE: localization strings, terminal formatting, or transport-level validation metadata.
│       └── [types]/ # MUST: Keep domain-local aliases and primitives that make business signatures explicit. (e.g identity)
│           ├── [name]_id.{ext} # INCLUDE: strongly typed identifiers or identity helpers like (e.g [`OrderId`, `new_order_id`, `ORDER_ID_PREFIX`]). NOT INCLUDE: database primary-key generation tied to a vendor, CLI aliases, or URL parameters.
│           └── [name]_type.{ext} # INCLUDE: domain type aliases and small primitives like (e.g [`CurrencyCode`, `Quantity`, `DEFAULT_QUANTITY`]). NOT INCLUDE: DTO shapes, schema definitions, or framework-specific type metadata.
├── [application]/ # Owns use-case orchestration, input/output boundaries, and application-specific business rules.
│   └── (feat/sub_feat/...)/ # MUST: Group application workflows by feature and optional sub-feature while depending only on domain and ports. (e.g billing/invoices)
│       ├── [use_cases]/ # MUST: Coordinate one user/system intention without knowing the CLI, database, or framework. (e.g create)
│       │   ├── [name]_use_case.{ext} # INCLUDE: use-case orchestration, transaction boundary calls through ports, and domain model coordination like (e.g [`CreateInvoiceUseCase`, `execute`, `CreateInvoiceInputDto`]). NOT INCLUDE: CLI argument parsing, terminal output, SQL, HTTP clients, or concrete repositories.
│       │   ├── [name]_interactor.{ext} # INCLUDE: input-boundary implementation and response-boundary calls like (e.g [`CreateInvoiceInteractor`, `handle`, `present_success`]). NOT INCLUDE: concrete presenters, framework controllers, or direct console writes.
│       │   └── [name]_workflow.{ext} # INCLUDE: multi-step application flows across use cases like (e.g [`ImportCatalogWorkflow`, `run`, `BATCH_SIZE`]). NOT INCLUDE: shell command registration, file-system implementations, or vendor SDK calls.
│       ├── [messages]/ # MUST: Represent application requests and responses for command/query style workflows. (e.g requests)
│       │   ├── [name]_command.{ext} # INCLUDE: intent-changing request data like (e.g [`CreateUserCommand`, `email`, `role`]). NOT INCLUDE: CLI option metadata, terminal colors, persistence schema fields, or domain behavior.
│       │   ├── [name]_query.{ext} # INCLUDE: read-only request data like (e.g [`FindUserQuery`, `user_id`, `include_disabled`]). NOT INCLUDE: SQL strings, external API filters, or presentation formatting.
│       │   └── [name]_result.{ext} # INCLUDE: application result objects like (e.g [`CreateUserResult`, `created_id`, `warnings`]). NOT INCLUDE: raw database records, CLI tables, JSON serializer annotations, or framework response objects.
│       ├── [ports]/ # MUST: Declare boundaries that outer layers implement and use cases depend on. (e.g outbound)
│       │   ├── [name]_in_port.{ext} # INCLUDE: input boundary contracts for invoking use cases like (e.g [`CreateUserInPort`, `execute`, `CreateUserCommand`]). NOT INCLUDE: CLI framework command classes, concrete controllers, or terminal dependencies.
│       │   ├── [name]_out_port.{ext} # INCLUDE: output boundary contracts for presenting use-case results like (e.g [`CreateUserOutPort`, `present`, `CreateUserResult`]). NOT INCLUDE: terminal rendering, JSON formatting, or concrete presenter state.
│       │   ├── [name]_repository_port.{ext} # INCLUDE: persistence contract in application language like (e.g [`UserRepositoryPort`, `save`, `find_by_id`]). NOT INCLUDE: ORM models, SQL queries, connection pools, or migration code.
│       │   ├── [name]_gateway_port.{ext} # INCLUDE: external capability contract like (e.g [`PaymentGatewayPort`, `capture`, `GatewayResponse`]). NOT INCLUDE: vendor SDK objects, HTTP clients, credential loading, or retry implementation.
│       │   ├── [name]_event_bus_port.{ext} # INCLUDE: event publishing contract like (e.g [`EventBusPort`, `publish`, `DomainEvent`]). NOT INCLUDE: broker topics, queue configuration, or concrete serialization.
│       │   ├── [name]_unit_of_work_port.{ext} # INCLUDE: transaction boundary contract like (e.g [`UnitOfWorkPort`, `commit`, `rollback`]). NOT INCLUDE: database connection handling, ORM sessions, or infrastructure retries.
│       │   └── [name]_clock_port.{ext} # INCLUDE: time provider contract for deterministic use cases like (e.g [`ClockPort`, `now`, `UTC_ZONE`]). NOT INCLUDE: direct system clock calls or timezone configuration loading.
│       ├── [dto]/ # MUST: Carry data across application boundaries without leaking domain internals. (e.g invoice)
│       │   ├── [name]_input_dto.{ext} # INCLUDE: validated use-case input shape like (e.g [`CreateInvoiceInputDto`, `customer_id`, `items`]). NOT INCLUDE: CLI parser objects, raw argv arrays, ORM records, or terminal prompts.
│       │   ├── [name]_output_dto.{ext} # INCLUDE: use-case output shape like (e.g [`InvoiceOutputDto`, `invoice_id`, `total`]). NOT INCLUDE: formatted tables, localized text, ANSI styling, or persistence entities.
│       │   └── [name]_error_dto.{ext} # INCLUDE: application-level error payloads like (e.g [`UseCaseErrorDto`, `code`, `message_key`]). NOT INCLUDE: stack traces, framework error responses, or shell exit-code mapping.
│       ├── [validators]/ # MUST: Validate application input before domain execution. (e.g create)
│       │   └── [name]_validator.{ext} # INCLUDE: application request validation like (e.g [`CreateUserValidator`, `validate`, `REQUIRED_FIELDS`]). NOT INCLUDE: domain invariants already owned by models, CLI parsing, or database uniqueness checks unless expressed through ports.
│       ├── [handlers]/ # MUST: Dispatch application messages and events to use-case behavior. (e.g commands)
│       │   ├── [name]_command_handler.{ext} # INCLUDE: command-to-use-case handling like (e.g [`CreateUserCommandHandler`, `handle`, `CreateUserUseCase`]). NOT INCLUDE: CLI command definitions, terminal output, or concrete infrastructure setup.
│       │   ├── [name]_query_handler.{ext} # INCLUDE: query-to-use-case handling like (e.g [`FindUserQueryHandler`, `handle`, `FindUserUseCase`]). NOT INCLUDE: SQL builders, screen rendering, or transport concerns.
│       │   └── [name]_event_handler.{ext} # INCLUDE: application reaction to domain events like (e.g [`SendReceiptOnPaymentCapturedHandler`, `handle`, `PaymentCapturedEvent`]). NOT INCLUDE: broker subscription wiring, queue workers, or CLI notifications.
│       ├── [mappers]/ # MUST: Translate between application DTOs and domain models while staying framework-independent. (e.g invoices)
│       │   ├── [name]_assembler.{ext} # INCLUDE: DTO-to-domain assembly helpers like (e.g [`InvoiceAssembler`, `to_model`, `to_output_dto`]). NOT INCLUDE: JSON parsing, terminal formatting, ORM hydration, or database schema mapping.
│       │   └── [name]_projection.{ext} # INCLUDE: read-model shapes designed for use-case outputs like (e.g [`InvoiceSummaryProjection`, `from_model`, `TOTAL_LABEL_KEY`]). NOT INCLUDE: UI layout, SQL views, or framework serializers.
│       └── [errors]/ # MUST: Define failures caused by use-case execution rules. (e.g conflict)
│           ├── [name]_app_error.{ext} # INCLUDE: application-specific errors like (e.g [`UserAlreadyExistsAppError`, `code`, `conflict_id`]). NOT INCLUDE: domain invariant classes, database driver exceptions, or shell-specific exit codes.
│           └── [name]_error_code.{ext} # INCLUDE: stable application error codes like (e.g [`UseCaseErrorCode`, `USER_ALREADY_EXISTS`, `INVALID_COMMAND`]). NOT INCLUDE: HTTP status codes, ANSI colors, or translated messages.
├── [adapters]/ # Owns interface adapters that translate CLI input/output and external data shapes into application boundaries.
│   └── (feat/sub_feat/...)/ # MUST: Group adapter code by feature and optional sub-feature while depending inward on application ports. (e.g billing/invoices)
│       ├── [cli]/ # MUST: Adapt shell commands, arguments, and terminal responses to use-case boundaries. (e.g commands)
│       │   ├── [commands]/ # MUST: Define command-line verbs and subcommands for the feature. (e.g create)
│       │   │   ├── [name]_cli_command.{ext} # INCLUDE: CLI command metadata and delegation to controllers like (e.g [`CreateInvoiceCliCommand`, `register`, `COMMAND_NAME`]). NOT INCLUDE: business rules, database access, or direct domain model mutation.
│       │   │   ├── [name]_cli_options.{ext} # INCLUDE: option/flag declarations and CLI defaults like (e.g [`CreateInvoiceCliOptions`, `--customer`, `DEFAULT_FORMAT`]). NOT INCLUDE: use-case orchestration, persistence details, or domain invariants.
│       │   │   └── [name]_cli_alias.{ext} # INCLUDE: aliases and command shortcuts like (e.g [`InvoiceAlias`, `inv:create`, `ALIAS_MAP`]). NOT INCLUDE: application logic, external service calls, or storage mapping.
│       │   ├── [controllers]/ # MUST: Convert parsed CLI input into application requests. (e.g invoice)
│       │   │   └── [name]_controller.{ext} # INCLUDE: request construction and use-case invocation like (e.g [`CreateInvoiceController`, `run`, `CreateInvoiceInputDto`]). NOT INCLUDE: domain calculations, database drivers, terminal styling, or dependency wiring.
│       │   ├── [presenters]/ # MUST: Convert application outputs into CLI-facing view models. (e.g table)
│       │   │   ├── [name]_presenter.{ext} # INCLUDE: output-port implementation and view-model creation like (e.g [`InvoicePresenter`, `present_success`, `present_error`]). NOT INCLUDE: business decisions, raw console writes, or concrete terminal driver calls.
│       │   │   └── [name]_view_model.{ext} # INCLUDE: presentation-ready data for CLI rendering like (e.g [`InvoiceViewModel`, `rows`, `summary`]). NOT INCLUDE: domain behavior, use-case execution, or database records.
│       │   ├── [parsers]/ # MUST: Parse raw shell arguments into structured adapter input. (e.g argv)
│       │   │   └── [name]_args_parser.{ext} # INCLUDE: argv parsing and syntactic validation like (e.g [`InvoiceArgsParser`, `parse`, `SUPPORTED_FLAGS`]). NOT INCLUDE: domain validation, repository access, or use-case transactions.
│       │   ├── [formatters]/ # MUST: Format view models into terminal-safe output strings. (e.g json)
│       │   │   ├── [name]_output_formatter.{ext} # INCLUDE: text/table/json formatting like (e.g [`InvoiceOutputFormatter`, `format`, `FORMAT_JSON`]). NOT INCLUDE: use-case logic, domain state changes, or persistence code.
│       │   │   └── [name]_error_formatter.{ext} # INCLUDE: user-facing CLI error formatting like (e.g [`CliErrorFormatter`, `format_error`, `EXIT_HINTS`]). NOT INCLUDE: stack-trace policy, domain exception definitions, or database exception handling.
│       │   └── [errors]/ # MUST: Map adapter-level CLI problems to readable command failures. (e.g invalid_args)
│       │       ├── [name]_cli_error.{ext} # INCLUDE: CLI-specific error types like (e.g [`InvalidCliOptionError`, `option_name`, `INVALID_OPTION`]). NOT INCLUDE: application error codes, domain invariant classes, or database errors.
│       │       └── [name]_exit_code.{ext} # INCLUDE: shell exit-code mapping like (e.g [`CliExitCode`, `SUCCESS`, `USAGE_ERROR`]). NOT INCLUDE: business statuses, repository errors, or framework response objects.
│       ├── [gateways]/ # MUST: Adapt application gateway/repository ports to data shapes required by infrastructure drivers. (e.g persistence)
│       │   ├── [name]_gateway_adapter.{ext} # INCLUDE: application-port implementation that delegates to an infrastructure client like (e.g [`PaymentGatewayAdapter`, `capture`, `PaymentClient`]). NOT INCLUDE: domain rules, CLI parsing, or framework bootstrap.
│       │   ├── [name]_repository_adapter.{ext} # INCLUDE: repository-port implementation and model/data mapping coordination like (e.g [`UserRepositoryAdapter`, `save`, `UserDataSource`]). NOT INCLUDE: SQL schema definitions, terminal output, or use-case orchestration.
│       │   └── [name]_unit_of_work_adapter.{ext} # INCLUDE: application transaction-port implementation like (e.g [`SqlUnitOfWorkAdapter`, `commit`, `rollback`]). NOT INCLUDE: command parsing, domain invariants, or presenter formatting.
│       ├── [mappers]/ # MUST: Translate across adapter, DTO, domain, and infrastructure data shapes. (e.g user)
│       │   ├── [name]_request_mapper.{ext} # INCLUDE: CLI/input request mapping like (e.g [`CreateUserRequestMapper`, `to_input_dto`, `ARG_EMAIL`]). NOT INCLUDE: use-case execution, database calls, or terminal rendering.
│       │   ├── [name]_response_mapper.{ext} # INCLUDE: application-output to view-model mapping like (e.g [`UserResponseMapper`, `to_view_model`, `STATUS_LABELS`]). NOT INCLUDE: business calculations, repository implementation, or raw console writes.
│       │   └── [name]_record_mapper.{ext} # INCLUDE: infrastructure-record to domain/application mapping like (e.g [`UserRecordMapper`, `to_model`, `to_record`]). NOT INCLUDE: SQL execution, CLI options, or use-case branching.
│       ├── [serializers]/ # MUST: Convert adapter data into exchange formats supported by the CLI. (e.g json)
│       │   ├── [name]_serializer.{ext} # INCLUDE: serialization of view models or DTOs like (e.g [`JsonInvoiceSerializer`, `serialize`, `CONTENT_TYPE_JSON`]). NOT INCLUDE: domain behavior, file writing, or use-case coordination.
│       │   └── [name]_deserializer.{ext} # INCLUDE: deserialization of CLI input files or stdin payloads like (e.g [`CsvUserDeserializer`, `deserialize`, `EXPECTED_COLUMNS`]). NOT INCLUDE: domain validation beyond shape checks, persistence writes, or command registration.
│       └── [middleware]/ # MUST: Apply adapter-level cross-cutting behavior around CLI/controller execution. (e.g tracing)
│           ├── [name]_adapter_middleware.{ext} # INCLUDE: adapter pipeline behavior like (e.g [`CliTracingMiddleware`, `around`, `TRACE_HEADER`]). NOT INCLUDE: domain rules, application transactions unless delegated, or infrastructure setup.
│           └── [name]_exception_mapper.{ext} # INCLUDE: mapping domain/application errors to adapter errors like (e.g [`CliExceptionMapper`, `to_cli_error`, `ERROR_MAP`]). NOT INCLUDE: stack-trace printing, database error creation, or user prompts.
├── [infrastructure]/ # Owns frameworks, drivers, external I/O, storage, operating-system access, and concrete port implementations.
│   └── (feat/sub_feat/...)/ # MUST: Group technology-specific implementations by feature and optional sub-feature. (e.g billing/invoices)
│       ├── [persistence]/ # MUST: Implement storage mechanisms used by repository or unit-of-work adapters. (e.g sql)
│       │   ├── [repositories]/ # MUST: Hold concrete persistence implementations when the adapter and driver are intentionally colocated. (e.g sqlite)
│       │   │   └── [name]_repository.{ext} # INCLUDE: concrete data access behind an application port like (e.g [`SqliteUserRepository`, `save`, `find_by_id`]). NOT INCLUDE: CLI argument parsing, terminal formatting, or domain policy decisions.
│       │   ├── [data_sources]/ # MUST: Encapsulate low-level reads/writes against storage backends. (e.g files)
│       │   │   └── [name]_data_source.{ext} # INCLUDE: storage client calls and query execution like (e.g [`UserSqlDataSource`, `insert`, `select_by_id`]). NOT INCLUDE: use-case orchestration, domain invariants, or CLI messages.
│       │   ├── [schemas]/ # MUST: Define storage schema structures separate from domain models. (e.g tables)
│       │   │   ├── [name]_schema.{ext} # INCLUDE: table/collection/file schema definitions like (e.g [`UserSchema`, `columns`, `TABLE_NAME`]). NOT INCLUDE: domain behavior, application DTO validation, or terminal views.
│       │   │   └── [name]_record.{ext} # INCLUDE: persistence record shapes like (e.g [`UserRecord`, `user_id`, `created_at`]). NOT INCLUDE: domain methods, use-case results, or CLI view labels.
│       │   ├── [migrations]/ # MUST: Describe storage evolution steps. (e.g v001)
│       │   │   └── [timestamp]_[name]_migration.{ext} # INCLUDE: forward/backward schema changes like (e.g [`CreateUsersTableMigration`, `up`, `down`]). NOT INCLUDE: use-case logic, terminal prompts, or domain events.
│       │   └── [seeders]/ # MUST: Provide optional development or initial storage data. (e.g defaults)
│       │       └── [name]_seeder.{ext} # INCLUDE: deterministic seed data creation like (e.g [`DefaultRolesSeeder`, `seed`, `DEFAULT_ROLES`]). NOT INCLUDE: production business rules, CLI workflows, or domain factories with I/O.
│       ├── [filesystem]/ # MUST: Isolate file-system access and path management. (e.g local)
│       │   ├── [name]_file_store.{ext} # INCLUDE: concrete file read/write operations like (e.g [`LocalFileStore`, `read`, `write`]). NOT INCLUDE: use-case decisions, domain validation, or CLI formatting.
│       │   ├── [name]_path_resolver.{ext} # INCLUDE: OS-aware path resolution like (e.g [`ConfigPathResolver`, `resolve`, `APP_CONFIG_DIR`]). NOT INCLUDE: business identifiers, command definitions, or persistence schema logic.
│       │   └── [name]_template_loader.{ext} # INCLUDE: loading static templates/assets like (e.g [`ReportTemplateLoader`, `load`, `TEMPLATE_DIR`]). NOT INCLUDE: rendering decisions owned by presenters or business calculations.
│       ├── [terminal]/ # MUST: Encapsulate concrete terminal, stdin, stdout, and interactive prompt drivers. (e.g tty)
│       │   ├── [name]_terminal.{ext} # INCLUDE: concrete stdout/stderr/stdin operations like (e.g [`SystemTerminal`, `write_line`, `read_line`]). NOT INCLUDE: application logic, domain models, or command routing decisions.
│       │   ├── [name]_table_renderer.{ext} # INCLUDE: concrete table rendering implementation like (e.g [`AsciiTableRenderer`, `render`, `MAX_WIDTH`]). NOT INCLUDE: use-case result creation, domain calculations, or repository access.
│       │   └── [name]_prompt_driver.{ext} # INCLUDE: interactive prompt implementation like (e.g [`ConfirmPromptDriver`, `ask_yes_no`, `DEFAULT_CONFIRM`]). NOT INCLUDE: business approval rules, application validation, or persistence operations.
│       ├── [process]/ # MUST: Isolate operating-system process and signal interactions. (e.g shell)
│       │   ├── [name]_process_runner.{ext} # INCLUDE: child-process execution details like (e.g [`ShellProcessRunner`, `run`, `DEFAULT_TIMEOUT`]). NOT INCLUDE: use-case orchestration, domain rules, or command metadata.
│       │   └── [name]_signal_handler.{ext} # INCLUDE: OS signal handling like (e.g [`ShutdownSignalHandler`, `on_interrupt`, `SIGINT_NAME`]). NOT INCLUDE: business rollback decisions unless delegated through application ports.
│       ├── [network]/ # MUST: Isolate network clients and remote protocol details. (e.g api)
│       │   ├── [name]_http_client.{ext} # INCLUDE: low-level HTTP calls and request configuration like (e.g [`DefaultHttpClient`, `send`, `TIMEOUT_SECONDS`]). NOT INCLUDE: application business decisions, domain models as wire payloads, or CLI output.
│       │   └── [name]_api_client.{ext} # INCLUDE: vendor or remote API calls like (e.g [`PaymentsApiClient`, `capture_payment`, `API_VERSION`]). NOT INCLUDE: use-case orchestration, credential policy beyond driver needs, or domain validation.
│       ├── [config]/ # MUST: Load and expose runtime configuration without leaking it inward. (e.g env)
│       │   ├── [name]_config.{ext} # INCLUDE: typed runtime configuration shape like (e.g [`AppConfig`, `database_url`, `log_level`]). NOT INCLUDE: domain constants, use-case defaults, or CLI option declarations.
│       │   ├── [name]_config_loader.{ext} # INCLUDE: config file/env loading like (e.g [`EnvConfigLoader`, `load`, `CONFIG_FILE_NAME`]). NOT INCLUDE: business validation, command routing, or database queries.
│       │   └── [name]_env.{ext} # INCLUDE: environment variable access wrappers like (e.g [`EnvironmentReader`, `get`, `ENV_PREFIX`]). NOT INCLUDE: domain decisions, CLI parsing, or application DTOs.
│       ├── [logging]/ # MUST: Implement concrete logging and telemetry details. (e.g console)
│       │   ├── [name]_logger.{ext} # INCLUDE: logger implementation or adapter like (e.g [`ConsoleLogger`, `info`, `error`]). NOT INCLUDE: domain events as log messages, use-case branching, or terminal presenter formatting.
│       │   └── [name]_log_formatter.{ext} # INCLUDE: log record formatting like (e.g [`JsonLogFormatter`, `format`, `TRACE_ID_FIELD`]). NOT INCLUDE: CLI output formatting, business result mapping, or persistence schemas.
│       ├── [events]/ # MUST: Implement event transport and handler execution mechanisms outside the domain. (e.g local_bus)
│       │   ├── [name]_event_bus.{ext} # INCLUDE: concrete event bus implementation like (e.g [`InMemoryEventBus`, `publish`, `subscribe`]). NOT INCLUDE: domain event definitions, business decisions, or CLI command registration.
│       │   ├── [name]_event_dispatcher.{ext} # INCLUDE: dispatch strategy and handler invocation like (e.g [`DomainEventDispatcher`, `dispatch`, `HANDLER_MAP`]). NOT INCLUDE: domain model mutation unless through application handlers.
│       │   └── [name]_event_handler.{ext} # INCLUDE: infrastructure-side event reactions like (e.g [`WriteAuditLogEventHandler`, `handle`, `AuditLogRepository`]). NOT INCLUDE: core domain policies, CLI parsing, or use-case input validation.
│       ├── [security]/ # MUST: Isolate credentials, secrets, tokens, and encryption drivers. (e.g secrets)
│       │   ├── [name]_secret_store.{ext} # INCLUDE: secret retrieval/storage implementation like (e.g [`KeychainSecretStore`, `get_secret`, `SECRET_NAMESPACE`]). NOT INCLUDE: domain passwords as business data, CLI prompts, or use-case branching.
│       │   └── [name]_token_provider.{ext} # INCLUDE: token acquisition and refresh driver logic like (e.g [`OAuthTokenProvider`, `get_token`, `TOKEN_EXPIRY_SKEW`]). NOT INCLUDE: domain authorization policies, command registration, or presenter formatting.
│       └── [time]/ # MUST: Provide concrete implementations for time-related application ports. (e.g system)
│           └── [name]_clock.{ext} # INCLUDE: system clock implementation like (e.g [`SystemClock`, `now`, `DEFAULT_TIMEZONE`]). NOT INCLUDE: direct use-case decisions, domain date policies, or CLI display formatting.
├── [runtime]/ # Owns executable composition, dependency wiring, startup/shutdown, and command routing at the outermost boundary.
|   └── (feat/sub_feat/...)/ # MUST: Group runtime assembly by feature and optional sub-feature when the CLI is composed modularly. (e.g billing/invoices)
|       ├── [composition]/ # MUST: Wire concrete implementations to application ports. (e.g modules)
|       │   ├── [name]_container.{ext} # INCLUDE: dependency graph/container assembly like (e.g [`AppContainer`, `resolve`, `register`]). NOT INCLUDE: business logic, domain rules, or CLI output formatting.
|       │   ├── [name]_module.{ext} # INCLUDE: feature-level dependency module wiring like (e.g [`BillingModule`, `bind_ports`, `MODULE_NAME`]). NOT INCLUDE: use-case internals, SQL queries, or terminal rendering.
|       │   └── [name]_provider.{ext} # INCLUDE: factory/provider functions for concrete dependencies like (e.g [`provide_user_repository`, `provide_clock`, `DEFAULT_SCOPE`]). NOT INCLUDE: domain behavior, command parsing, or application validation.
|       ├── [bootstrap]/ # MUST: Start and stop the CLI application safely. (e.g startup)
|       │   ├── [name]_bootstrap.{ext} # INCLUDE: initialization sequence like (e.g [`CliBootstrap`, `start`, `load_config`]). NOT INCLUDE: use-case business logic, domain model mutation, or repository query details.
|       │   ├── [name]_startup.{ext} # INCLUDE: startup checks and resource initialization like (e.g [`StartupChecks`, `verify`, `REQUIRED_RESOURCES`]). NOT INCLUDE: domain invariants, application request validation, or presenter formatting.
|       │   └── [name]_shutdown.{ext} # INCLUDE: graceful resource cleanup like (e.g [`ShutdownHooks`, `close`, `FLUSH_TIMEOUT`]). NOT INCLUDE: business rollback rules unless delegated through application ports.
|       ├── [entrypoints]/ # MUST: Expose executable entry files for the CLI process. (e.g main)
|       │   ├── [name]_main.{ext} # INCLUDE: minimal process entrypoint like (e.g [`main`, `exit`, `CliBootstrap`]). NOT INCLUDE: business rules, direct database access, or terminal formatting details.
|       │   └── [name]_cli.{ext} # INCLUDE: top-level CLI process launcher like (e.g [`run_cli`, `argv`, `EXIT_SUCCESS`]). NOT INCLUDE: use-case internals, domain calculations, or concrete storage queries.
|       └── [routing]/ # MUST: Register and resolve CLI commands to adapter controllers. (e.g router)
|           ├── [name]_command_router.{ext} # INCLUDE: route resolution from command names to handlers/controllers like (e.g [`CommandRouter`, `route`, `UNKNOWN_COMMAND`]). NOT INCLUDE: domain behavior, repository implementation, or presenter formatting.
|           └── [name]_command_registry.{ext} # INCLUDE: command registration catalog like (e.g [`CommandRegistry`, `register_all`, `AVAILABLE_COMMANDS`]). NOT INCLUDE: business validation, database access, or use-case transaction control.
└── [/documentation]
    ├── [/wiki]
    └── [domain]_[feat]_[docfile_type].md
```

**IMPORTANT**: This **IS NOT FIXED DIR-TREE** use as responsibility distribution guideline patern.
