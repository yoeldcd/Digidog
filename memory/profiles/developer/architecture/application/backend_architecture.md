# Archeitectural distribution patterns for (Back-End Codebase)

Organize the codebase tree to following verticals sliced Clean Architecture (under **featurizer segmentation**):

## Tree

```powershell
{codebase_root}/ # Repository root that groups every Clean Architecture layout, feature module, and support boundary.
├── [domain]/ # Owns enterprise business rules, pure models, domain invariants, and domain language.
│   └── (feat/sub_feat/...)/ # MUST: Group domain code by business capability and nested sub-capability. (e.g orders/returns)
│       ├── [models]/ # MUST: Represent domain entities as pure business models. (e.g order)
│       │   ├── [name]_model.{ext} # INCLUDE: entity state, invariant methods, and behavior like (e.g [`OrderModel`, `add_item`, `ORDER_STATUS`]). NOT INCLUDE: HTTP details, ORM annotations, SQL, framework decorators, or serialization formats.
│       │   ├── [name]_factory.{ext} # INCLUDE: safe model creation rules like (e.g [`OrderFactory`, `create_draft_order`, `DEFAULT_ORDER_STATUS`]). NOT INCLUDE: persistence calls, request parsing, or external API calls.
│       │   └── [name]_snapshot.{ext} # INCLUDE: immutable model snapshot shape for state comparison like (e.g [`OrderSnapshot`, `from_order`, `ORDER_SNAPSHOT_VERSION`]). NOT INCLUDE: database schemas, transport DTOs, or cache keys.
│       ├── [value_objects]/ # MUST: Encapsulate small immutable concepts with validation and equality. (e.g money)
│       │   ├── [name]_value_object.{ext} # INCLUDE: value validation, normalization, and equality like (e.g [`MoneyValueObject`, `is_same_currency`, `DEFAULT_CURRENCY`]). NOT INCLUDE: repositories, HTTP status codes, or framework validators.
│       │   ├── [name]_range.{ext} # INCLUDE: bounded value intervals and range operations like (e.g [`DateRange`, `contains_date`, `MAX_RANGE_DAYS`]). NOT INCLUDE: scheduler implementations, database queries, or timezone infrastructure.
│       │   └── [name]_identifier.{ext} # INCLUDE: typed identifiers and identity validation like (e.g [`OrderId`, `from_string`, `ORDER_ID_PREFIX`]). NOT INCLUDE: route parsing, auto-increment configuration, or database column definitions.
│       ├── [rules]/ # MUST: Keep reusable business rules and invariant checks. (e.g pricing)
│       │   ├── [name]_rule.{ext} # INCLUDE: pure business decision rules like (e.g [`DiscountEligibilityRule`, `can_apply_discount`, `MAX_DISCOUNT_PERCENT`]). NOT INCLUDE: user session data, API payload parsing, or persistence concerns.
│       │   ├── [name]_policy.{ext} # INCLUDE: domain policy decisions across models like (e.g [`RefundPolicy`, `is_refundable`, `REFUND_WINDOW_DAYS`]). NOT INCLUDE: workflow orchestration, notification sending, or transaction handling.
│       │   └── [name]_specification.{ext} # INCLUDE: composable domain predicates like (e.g [`ActiveCustomerSpecification`, `is_satisfied_by`, `MIN_ACTIVE_ORDERS`]). NOT INCLUDE: SQL builders, ORM predicates, or infrastructure filters.
│       ├── [services]/ # MUST: Hold pure domain services for behavior that does not naturally belong to one model. (e.g pricing)
│       │   ├── [name]_domain_service.{ext} # INCLUDE: stateless domain operations across models like (e.g [`PricingDomainService`, `calculate_total`, `TAXABLE_ITEM_TYPES`]). NOT INCLUDE: application workflows, repositories, message brokers, or logging frameworks.
│       │   └── [name]_calculator.{ext} # INCLUDE: deterministic calculations using domain types like (e.g [`ShippingCostCalculator`, `calculate_shipping_cost`, `FREE_SHIPPING_THRESHOLD`]). NOT INCLUDE: carrier API calls, database access, or configuration readers.
│       ├── [events]/ # MUST: Define facts that happened inside the domain. (e.g order_created)
│       │   ├── [name]_event.{ext} # INCLUDE: immutable domain event data and occurrence metadata like (e.g [`OrderCreatedEvent`, `occurred_at`, `EVENT_VERSION`]). NOT INCLUDE: event broker clients, retry policies, or serialization adapters.
│       │   ├── [name]_event_payload.{ext} # INCLUDE: stable domain event payload shape like (e.g [`OrderCreatedPayload`, `to_payload`, `PAYLOAD_VERSION`]). NOT INCLUDE: transport envelope headers, queue names, or topic configuration.
│       │   └── [name]_event_type.{ext} # INCLUDE: event type constants or enums like (e.g [`OrderEventType`, `ORDER_CREATED`, `ORDER_CANCELLED`]). NOT INCLUDE: broker routing keys, HTTP routes, or subscriber setup.
│       ├── [errors]/ # MUST: Represent domain failures using business language. (e.g order_errors)
│       │   ├── [name]_domain_error.{ext} # INCLUDE: domain-specific error types like (e.g [`OrderCannotBeCancelledError`, `build_reason`, `ORDER_ALREADY_SHIPPED`]). NOT INCLUDE: HTTP response codes, framework exceptions, or logging side effects.
│       │   └── [name]_violation.{ext} # INCLUDE: invariant violation details like (e.g [`CreditLimitViolation`, `describe_violation`, `CREDIT_LIMIT_EXCEEDED`]). NOT INCLUDE: controller error formatting, database error codes, or monitoring tags.
│       ├── [constants]/ # MUST: Keep stable domain constants expressed in ubiquitous language. (e.g order_constants)
│       │   └── [name]_constant.{ext} # INCLUDE: domain constants and enumerations like (e.g [`OrderConstants`, `MAX_ORDER_ITEMS`, `DEFAULT_ORDER_STATUS`]). NOT INCLUDE: environment variables, API URLs, or framework configuration.
│       └── [contracts]/ # MUST: Define domain-only contracts when a pure abstraction is part of the business language. (e.g policy_contracts)
│           └── [name]_contract.{ext} # INCLUDE: domain abstraction signatures like (e.g [`ExchangeRateContract`, `get_rate_for`, `SUPPORTED_CURRENCY_PAIR`]). NOT INCLUDE: infrastructure adapters, dependency injection wiring, or concrete API clients.
├── [application]/ # Owns use cases, application-specific business rules, ports, orchestration, and transaction intent.
│   └── (feat/sub_feat/...)/ # MUST: Group application code by business capability and nested sub-capability. (e.g orders/checkout)
│       ├── [use_cases]/ # MUST: Implement one application action or user/system intent per file. (e.g create_order)
│       │   ├── [name]_use_case.{ext} # INCLUDE: orchestration of domain models and ports like (e.g [`CreateOrderUseCase`, `execute`, `CREATE_ORDER_TIMEOUT`]). NOT INCLUDE: HTTP controllers, SQL statements, framework request objects, or concrete external clients.
│       │   ├── [name]_command.{ext} # INCLUDE: write-intent input structure like (e.g [`CreateOrderCommand`, `validate_command`, `COMMAND_VERSION`]). NOT INCLUDE: HTTP headers, database entities, or authorization middleware.
│       │   ├── [name]_query.{ext} # INCLUDE: read-intent input structure like (e.g [`FindOrderQuery`, `normalize_filters`, `DEFAULT_PAGE_SIZE`]). NOT INCLUDE: SQL syntax, ORM criteria, or web route parameters.
│       │   ├── [name]_result.{ext} # INCLUDE: use-case output shape like (e.g [`CreateOrderResult`, `from_model`, `RESULT_VERSION`]). NOT INCLUDE: HTTP response envelopes, presenter formatting, or persistence models.
│       │   └── [name]_interactor.{ext} # INCLUDE: input-port implementation and use-case delegation like (e.g [`CreateOrderInteractor`, `handle`, `INTERACTOR_NAME`]). NOT INCLUDE: framework annotations, route registration, or infrastructure construction.
│       ├── [ports]/ # MUST: Define application boundaries for inbound calls and outbound dependencies. (e.g order_ports)
│       │   ├── [inbound]/ # MUST: Define how external adapters invoke application behavior. (e.g commands)
│       │   │   ├── [name]_input_port.{ext} # INCLUDE: input boundary interface like (e.g [`CreateOrderInputPort`, `execute`, `INPUT_PORT_NAME`]). NOT INCLUDE: controller classes, request DTO parsing, or framework decorators.
│       │   │   ├── [name]_query_port.{ext} # INCLUDE: read boundary interface like (e.g [`FindOrdersQueryPort`, `find`, `QUERY_PORT_NAME`]). NOT INCLUDE: SQL execution, HTTP pagination parsing, or cache access.
│       │   │   └── [name]_workflow_port.{ext} # INCLUDE: workflow boundary interface like (e.g [`CheckoutWorkflowPort`, `run`, `WORKFLOW_PORT_NAME`]). NOT INCLUDE: queue listeners, cron definitions, or concrete transaction managers.
│       │   └── [outbound]/ # MUST: Define dependencies required by use cases and implemented outside the application layer. (e.g repositories)
│       │       ├── [name]_repository_port.{ext} # INCLUDE: persistence abstraction needed by use cases like (e.g [`OrderRepositoryPort`, `save`, `find_by_id`]). NOT INCLUDE: SQL, ORM models, connection pools, or migration scripts.
│       │       ├── [name]_gateway_port.{ext} # INCLUDE: external system abstraction like (e.g [`PaymentGatewayPort`, `authorize_payment`, `PAYMENT_GATEWAY_NAME`]). NOT INCLUDE: vendor SDK calls, HTTP clients, credentials, or retry implementations.
│       │       ├── [name]_publisher_port.{ext} # INCLUDE: event publishing abstraction like (e.g [`DomainEventPublisherPort`, `publish`, `EVENT_PUBLISHER_NAME`]). NOT INCLUDE: broker topics, serialization libraries, or queue configuration.
│       │       ├── [name]_transaction_port.{ext} # INCLUDE: transaction boundary abstraction like (e.g [`TransactionPort`, `run_in_transaction`, `DEFAULT_TX_TIMEOUT`]). NOT INCLUDE: database driver calls, unit-of-work implementation, or framework transaction decorators.
│       │       ├── [name]_clock_port.{ext} # INCLUDE: time abstraction like (e.g [`ClockPort`, `now`, `SYSTEM_CLOCK_NAME`]). NOT INCLUDE: direct system time calls inside use cases, timezone database setup, or scheduler configuration.
│       │       ├── [name]_id_generator_port.{ext} # INCLUDE: identity generation abstraction like (e.g [`IdGeneratorPort`, `new_id`, `ID_GENERATOR_NAME`]). NOT INCLUDE: UUID library wiring, database sequences, or random provider setup.
│       │       └── [name]_authorization_port.{ext} # INCLUDE: authorization decision abstraction like (e.g [`AuthorizationPort`, `can_perform`, `AUTHORIZATION_CONTEXT`]). NOT INCLUDE: middleware, token decoding, or policy engine SDK calls.
│       ├── [dtos]/ # MUST: Carry application input/output data without transport or persistence coupling. (e.g order_dtos)
│       │   ├── [name]_input_dto.{ext} # INCLUDE: use-case input data shape like (e.g [`CreateOrderInputDto`, `to_command`, `INPUT_DTO_VERSION`]). NOT INCLUDE: HTTP request classes, ORM entities, or validation annotations tied to a framework.
│       │   ├── [name]_output_dto.{ext} # INCLUDE: use-case output data shape like (e.g [`OrderOutputDto`, `from_result`, `OUTPUT_DTO_VERSION`]). NOT INCLUDE: HTTP response status, serialization decorators, or database fields not exposed to the use case.
│       │   └── [name]_criteria_dto.{ext} # INCLUDE: application-level search criteria like (e.g [`OrderSearchCriteriaDto`, `normalize_criteria`, `DEFAULT_SORT_FIELD`]). NOT INCLUDE: SQL clauses, ORM query builders, or URL query parsing.
│       ├── [mappers]/ # MUST: Convert between application DTOs, commands, results, and domain models. (e.g order_mappers)
│       │   ├── [name]_application_mapper.{ext} # INCLUDE: pure mapping between application and domain shapes like (e.g [`OrderApplicationMapper`, `to_model`, `to_result`]). NOT INCLUDE: JSON serialization, ORM hydration, or HTTP response formatting.
│       │   └── [name]_command_mapper.{ext} # INCLUDE: conversion from validated input DTOs to commands like (e.g [`CreateOrderCommandMapper`, `to_command`, `COMMAND_MAPPER_NAME`]). NOT INCLUDE: request parsing, controller logic, or database mapping.
│       ├── [validators]/ # MUST: Validate application input constraints before use-case execution. (e.g create_order_validation)
│       │   ├── [name]_validator.{ext} # INCLUDE: application-level validation rules like (e.g [`CreateOrderValidator`, `validate`, `MAX_ITEMS_PER_COMMAND`]). NOT INCLUDE: HTTP status mapping, persistence existence checks unless exposed by ports, or framework-specific decorators.
│       │   └── [name]_guard.{ext} # INCLUDE: precondition guards for use cases like (e.g [`OrderAccessGuard`, `ensure_allowed`, `REQUIRED_PERMISSION`]). NOT INCLUDE: middleware implementation, token parsing, or controller redirects.
│       ├── [handlers]/ # MUST: React to domain/application events by invoking use cases or ports. (e.g order_event_handlers)
│       │   ├── [name]_event_handler.{ext} # INCLUDE: application reaction to an event like (e.g [`OrderCreatedEventHandler`, `handle`, `HANDLED_EVENT_TYPE`]). NOT INCLUDE: broker consumer code, framework listener decorators, or concrete publisher clients.
│       │   ├── [name]_command_handler.{ext} # INCLUDE: command dispatch handling like (e.g [`CreateOrderCommandHandler`, `handle`, `COMMAND_HANDLER_NAME`]). NOT INCLUDE: HTTP controllers, request body parsing, or persistence adapters.
│       │   └── [name]_query_handler.{ext} # INCLUDE: query dispatch handling like (e.g [`FindOrderQueryHandler`, `handle`, `QUERY_HANDLER_NAME`]). NOT INCLUDE: SQL builders, REST response formatting, or cache drivers.
│       ├── [workflows]/ # MUST: Coordinate multi-step application processes across use cases. (e.g checkout)
│       │   ├── [name]_workflow.{ext} # INCLUDE: ordered application steps and compensations like (e.g [`CheckoutWorkflow`, `run`, `CHECKOUT_STEPS`]). NOT INCLUDE: framework jobs, broker consumers, or vendor-specific transaction APIs.
│       │   └── [name]_saga.{ext} # INCLUDE: long-running process state transitions like (e.g [`PaymentSaga`, `advance`, `SAGA_VERSION`]). NOT INCLUDE: queue subscriptions, persistence schema details, or scheduler setup.
│       ├── [read_models]/ # MUST: Define application read projections when reads differ from domain models. (e.g order_summary)
│       │   ├── [name]_read_model.{ext} # INCLUDE: query-optimized application view like (e.g [`OrderSummaryReadModel`, `from_projection`, `READ_MODEL_VERSION`]). NOT INCLUDE: database view DDL, HTTP response envelopes, or ORM entity annotations.
│       │   └── [name]_projection.{ext} # INCLUDE: projection transformation rules like (e.g [`OrderSummaryProjection`, `apply_event`, `PROJECTION_VERSION`]). NOT INCLUDE: message broker consumers, database writes, or scheduling details.
│       └── [errors]/ # MUST: Represent application-specific failures and boundary errors. (e.g use_case_errors)
│           ├── [name]_application_error.{ext} # INCLUDE: use-case failure types like (e.g [`OrderNotFoundApplicationError`, `reason`, `ORDER_NOT_FOUND`]). NOT INCLUDE: HTTP status codes, SQL error codes, or framework exception filters.
│           └── [name]_validation_error.{ext} # INCLUDE: validation failure details like (e.g [`CreateOrderValidationError`, `field_errors`, `VALIDATION_ERROR_CODE`]). NOT INCLUDE: translated UI messages, controller response bodies, or logging side effects.
├── [interface_adapters]/ # Owns adapters that translate external formats to application ports and application outputs to external formats.
│   └── (feat/sub_feat/...)/ # MUST: Group adapter code by business capability and nested sub-capability. (e.g orders/checkout)
│       ├── [controllers]/ # MUST: Convert inbound transport requests into application use-case calls. (e.g order_controller)
│       │   ├── [name]_controller.{ext} # INCLUDE: request handling, calling inbound ports, and adapter-level error handoff like (e.g [`OrderController`, `create_order`, `CREATE_ORDER_ROUTE_NAME`]). NOT INCLUDE: business rules, direct SQL, domain mutations without use cases, or concrete external SDK calls.
│       │   ├── [name]_rpc_controller.{ext} # INCLUDE: RPC/grpc-style adapter methods like (e.g [`OrderRpcController`, `CreateOrder`, `ORDER_RPC_SERVICE`]). NOT INCLUDE: use-case business logic, persistence code, or transport-agnostic domain rules.
│       │   └── [name]_cli_controller.{ext} # INCLUDE: command-line adapter parsing and use-case invocation like (e.g [`OrderCliController`, `run_create_order`, `CLI_COMMAND_NAME`]). NOT INCLUDE: application orchestration, repository implementations, or domain calculations.
│       ├── [routes]/ # MUST: Declare transport routes and bind them to controllers. (e.g order_routes)
│       │   ├── [name]_route.{ext} # INCLUDE: endpoint path, method, controller binding, and route metadata like (e.g [`OrderRoute`, `register_routes`, `ORDER_ROUTE_PREFIX`]). NOT INCLUDE: domain rules, SQL queries, or use-case implementation.
│       │   └── [name]_route_contract.{ext} # INCLUDE: route-level contract metadata like (e.g [`CreateOrderRouteContract`, `request_shape`, `RESPONSE_CODES`]). NOT INCLUDE: persistence models, business calculations, or external SDK configuration.
│       ├── [requests]/ # MUST: Represent inbound transport payloads. (e.g order_requests)
│       │   ├── [name]_request.{ext} # INCLUDE: inbound request shape and adapter validation hints like (e.g [`CreateOrderRequest`, `to_input_dto`, `REQUEST_VERSION`]). NOT INCLUDE: domain behavior, repository calls, or use-case execution.
│       │   ├── [name]_query_request.{ext} # INCLUDE: query parameter shape and parsing helpers like (e.g [`FindOrdersQueryRequest`, `to_criteria`, `DEFAULT_LIMIT`]). NOT INCLUDE: SQL predicates, ORM filters, or domain model methods.
│       │   └── [name]_path_params.{ext} # INCLUDE: path parameter shape and conversion like (e.g [`OrderPathParams`, `to_order_id`, `ORDER_ID_PARAM`]). NOT INCLUDE: domain persistence checks, controller response creation, or route registration.
│       ├── [responses]/ # MUST: Represent outbound transport response payloads. (e.g order_responses)
│       │   ├── [name]_response.{ext} # INCLUDE: response shape and presenter output fields like (e.g [`OrderResponse`, `from_presenter`, `RESPONSE_VERSION`]). NOT INCLUDE: domain methods, repository access, or use-case execution.
│       │   ├── [name]_error_response.{ext} # INCLUDE: adapter-level error response shape like (e.g [`OrderErrorResponse`, `from_error`, `ERROR_RESPONSE_VERSION`]). NOT INCLUDE: domain exception classes, logging side effects, or database error details.
│       │   └── [name]_page_response.{ext} # INCLUDE: paginated response shape like (e.g [`OrderPageResponse`, `from_page`, `DEFAULT_PAGE_META`]). NOT INCLUDE: query execution, application criteria validation, or persistence cursors.
│       ├── [presenters]/ # MUST: Transform application results into response-ready output. (e.g order_presenter)
│       │   ├── [name]_presenter.{ext} # INCLUDE: formatting of use-case results for a transport response like (e.g [`OrderPresenter`, `present`, `PRESENTER_NAME`]). NOT INCLUDE: business decisions, database access, or use-case orchestration.
│       │   └── [name]_error_presenter.{ext} # INCLUDE: mapping application errors to adapter error models like (e.g [`OrderErrorPresenter`, `present_error`, `ERROR_PRESENTER_NAME`]). NOT INCLUDE: framework exception filters, log shipping, or domain invariant logic.
│       ├── [mappers]/ # MUST: Convert between transport DTOs and application DTOs/results. (e.g order_api_mapper)
│       │   ├── [name]_request_mapper.{ext} # INCLUDE: request-to-application input conversion like (e.g [`CreateOrderRequestMapper`, `to_input_dto`, `REQUEST_MAPPER_NAME`]). NOT INCLUDE: domain behavior, database mapping, or use-case execution.
│       │   ├── [name]_response_mapper.{ext} # INCLUDE: application output-to-response conversion like (e.g [`OrderResponseMapper`, `to_response`, `RESPONSE_MAPPER_NAME`]). NOT INCLUDE: domain mutations, SQL, or repository calls.
│       │   └── [name]_error_mapper.{ext} # INCLUDE: application error-to-adapter error conversion like (e.g [`OrderErrorMapper`, `to_error_response`, `ERROR_MAPPER_NAME`]). NOT INCLUDE: logging frameworks, exception throwing policies, or broker retries.
│       ├── [gateways]/ # MUST: Adapt application outbound gateway ports to infrastructure clients or protocol-neutral clients. (e.g payment_gateway)
│       │   ├── [name]_gateway_adapter.{ext} # INCLUDE: implementation of an application gateway port using lower-level clients like (e.g [`PaymentGatewayAdapter`, `authorize_payment`, `PAYMENT_GATEWAY_ADAPTER`]). NOT INCLUDE: domain rules, controller code, or direct environment secret values.
│       │   └── [name]_gateway_mapper.{ext} # INCLUDE: mapping between application gateway data and provider-neutral client data like (e.g [`PaymentGatewayMapper`, `to_provider_request`, `GATEWAY_MAPPER_NAME`]). NOT INCLUDE: HTTP route registration, use-case orchestration, or ORM schemas.
│       ├── [repositories]/ # MUST: Adapt repository ports to persistence abstractions while keeping application contracts stable. (e.g order_repository)
│       │   ├── [name]_repository_adapter.{ext} # INCLUDE: repository port implementation and persistence abstraction delegation like (e.g [`OrderRepositoryAdapter`, `save`, `find_by_id`]). NOT INCLUDE: controller logic, domain invariant definitions, or raw connection setup.
│       │   ├── [name]_repository_mapper.{ext} # INCLUDE: mapping between domain models and persistence records like (e.g [`OrderRepositoryMapper`, `to_record`, `to_model`]). NOT INCLUDE: SQL execution, HTTP DTOs, or use-case coordination.
│       │   └── [name]_unit_of_work_adapter.{ext} # INCLUDE: adapter-level unit-of-work coordination via transaction ports like (e.g [`OrderUnitOfWorkAdapter`, `commit`, `rollback`]). NOT INCLUDE: business rules, route definitions, or database migration scripts.
│       ├── [consumers]/ # MUST: Convert inbound messages/events into application commands or handlers. (e.g order_consumer)
│       │   ├── [name]_consumer.{ext} # INCLUDE: message payload adaptation and application handler invocation like (e.g [`OrderCreatedConsumer`, `consume`, `CONSUMER_NAME`]). NOT INCLUDE: domain business logic, queue infrastructure setup, or concrete broker connection creation.
│       │   └── [name]_message_mapper.{ext} # INCLUDE: message-to-application DTO conversion like (e.g [`OrderMessageMapper`, `to_command`, `MESSAGE_VERSION`]). NOT INCLUDE: broker subscriptions, use-case implementation, or persistence queries.
│       ├── [serializers]/ # MUST: Convert adapter data to transport-safe serialized forms. (e.g order_serializers)
│       │   ├── [name]_serializer.{ext} # INCLUDE: output serialization rules like (e.g [`OrderSerializer`, `serialize`, `SERIALIZER_VERSION`]). NOT INCLUDE: domain validation, use-case execution, or database access.
│       │   └── [name]_deserializer.{ext} # INCLUDE: input deserialization rules like (e.g [`OrderDeserializer`, `deserialize`, `DESERIALIZER_VERSION`]). NOT INCLUDE: business decisions, repository calls, or transport listener setup.
│       ├── [filters]/ # MUST: Apply adapter-level request/response filtering. (e.g order_filters)
│       │   ├── [name]_filter.{ext} # INCLUDE: adapter filtering logic such as response field selection like (e.g [`OrderFieldFilter`, `apply`, `DEFAULT_FIELDS`]). NOT INCLUDE: authorization policy engines, domain rules, or SQL filters.
│       │   └── [name]_pagination_filter.{ext} # INCLUDE: pagination parameter normalization like (e.g [`OrderPaginationFilter`, `normalize`, `MAX_PAGE_SIZE`]). NOT INCLUDE: repository implementation, query execution, or presenter formatting.
│       └── [middlewares]/ # MUST: Hold transport-level middleware that stays outside application rules. (e.g auth_middleware)
│           ├── [name]_middleware.{ext} # INCLUDE: adapter pipeline behavior like (e.g [`CorrelationIdMiddleware`, `handle`, `CORRELATION_ID_HEADER`]). NOT INCLUDE: use-case business logic, domain validations, or repository operations.
│           └── [name]_exception_filter.{ext} # INCLUDE: framework-adapter exception translation like (e.g [`HttpExceptionFilter`, `catch`, `DEFAULT_ERROR_CODE`]). NOT INCLUDE: domain error definitions, application validation rules, or infrastructure retry policies.
├── [infrastructure]/ # Owns frameworks, drivers, persistence, external systems, runtime implementations, and technical details.
│   └── (feat/sub_feat/...)/ # MUST: Group infrastructure code by business capability and nested sub-capability. (e.g orders/payment_provider)
│       ├── [persistence]/ # MUST: Implement storage details and database-specific structures. (e.g order_persistence)
│       │   ├── [schemas]/ # MUST: Define database/table/document schemas. (e.g order_schema)
│       │   │   ├── [name]_schema.{ext} # INCLUDE: persistence schema definition like (e.g [`OrderSchema`, `define_columns`, `ORDER_TABLE_NAME`]). NOT INCLUDE: domain invariants, use-case logic, or HTTP response fields.
│       │   │   └── [name]_index.{ext} # INCLUDE: persistence index declarations like (e.g [`OrderIndex`, `build_indexes`, `ORDER_CREATED_AT_INDEX`]). NOT INCLUDE: repository port signatures, domain model behavior, or request validation.
│       │   ├── [orm]/ # MUST: Hold ORM-specific entities or models when the language/framework uses them. (e.g order_orm)
│       │   │   ├── [name]_orm_model.{ext} # INCLUDE: ORM entity metadata and persistence fields like (e.g [`OrderOrmModel`, `table_name`, `ORDER_ENTITY_NAME`]). NOT INCLUDE: domain methods, application commands, or controller decorators.
│       │   │   └── [name]_orm_mapper.{ext} # INCLUDE: ORM model to persistence record conversion when needed like (e.g [`OrderOrmMapper`, `to_orm`, `from_orm`]). NOT INCLUDE: HTTP serialization, use-case orchestration, or business decisions.
│       │   ├── [migrations]/ # MUST: Keep database evolution scripts. (e.g order_migrations)
│       │   │   ├── [timestamp]_[name]_migration.{ext} # INCLUDE: reversible schema/data migration steps like (e.g [`AddOrdersTableMigration`, `up`, `down`]). NOT INCLUDE: domain services, use-case code, or runtime request handling.
│       │   │   └── [timestamp]_[name]_rollback.{ext} # INCLUDE: explicit rollback helper when the migration tooling requires it like (e.g [`RollbackOrdersTable`, `rollback`, `ROLLBACK_VERSION`]). NOT INCLUDE: business policies, controllers, or event handlers.
│       │   ├── [dao]/ # MUST: Encapsulate low-level data access operations. (e.g order_dao)
│       │   │   ├── [name]_dao.{ext} # INCLUDE: database operations and query execution like (e.g [`OrderDao`, `insert`, `select_by_id`]). NOT INCLUDE: use-case orchestration, HTTP payload parsing, or domain invariant enforcement.
│       │   │   └── [name]_query_builder.{ext} # INCLUDE: persistence-specific query construction like (e.g [`OrderQueryBuilder`, `build_find_query`, `DEFAULT_ORDER_SORT`]). NOT INCLUDE: application query DTOs, controller logic, or domain specifications.
│       │   ├── [seeders]/ # MUST: Provide safe seed data for local/test environments. (e.g order_seeders)
│       │   │   ├── [name]_seed.{ext} # INCLUDE: deterministic seed records like (e.g [`OrderSeed`, `run`, `SEED_ORDER_ID`]). NOT INCLUDE: production secrets, business workflow execution, or external service calls.
│       │   │   └── [name]_fixture_seed.{ext} # INCLUDE: fixture-oriented seed data like (e.g [`OrderFixtureSeed`, `insert_fixtures`, `FIXTURE_VERSION`]). NOT INCLUDE: domain factories as the source of business truth, controller calls, or migration logic.
│       │   └── [transactions]/ # MUST: Implement concrete transaction management. (e.g order_transactions)
│       │       └── [name]_transaction_manager.{ext} # INCLUDE: concrete transaction handling like (e.g [`DatabaseTransactionManager`, `run_in_transaction`, `TX_ISOLATION_LEVEL`]). NOT INCLUDE: application use-case decisions, domain rules, or HTTP response handling.
│       ├── [web]/ # MUST: Hold web framework-specific infrastructure. (e.g http_server)
│       │   ├── [name]_server.{ext} # INCLUDE: server startup and framework instance creation like (e.g [`HttpServer`, `start`, `DEFAULT_PORT`]). NOT INCLUDE: domain behavior, use-case code, or direct repository queries.
│       │   ├── [name]_web_config.{ext} # INCLUDE: web framework options like (e.g [`WebConfig`, `load_web_config`, `REQUEST_BODY_LIMIT`]). NOT INCLUDE: business constants, database credentials as raw values, or domain validation.
│       │   └── [name]_health_check.{ext} # INCLUDE: technical health probe implementation like (e.g [`HealthCheckEndpoint`, `check`, `HEALTH_STATUS_OK`]). NOT INCLUDE: business reporting, use-case execution, or domain model mutation.
│       ├── [clients]/ # MUST: Implement concrete external service clients. (e.g payment_client)
│       │   ├── [name]_http_client.{ext} # INCLUDE: HTTP client calls, endpoint paths, and provider response handling like (e.g [`PaymentHttpClient`, `post_authorization`, `PAYMENT_API_PATH`]). NOT INCLUDE: domain policy decisions, controller code, or hard-coded secrets.
│       │   ├── [name]_sdk_client.{ext} # INCLUDE: vendor SDK wrapper calls like (e.g [`StripeSdkClient`, `create_charge`, `SDK_CLIENT_NAME`]). NOT INCLUDE: use-case orchestration, domain calculations, or transport request parsing.
│       │   └── [name]_client_config.{ext} # INCLUDE: client technical settings like (e.g [`PaymentClientConfig`, `load_config`, `PAYMENT_TIMEOUT_MS`]). NOT INCLUDE: secret literal values, domain constants, or HTTP controller behavior.
│       ├── [messaging]/ # MUST: Implement broker-specific event and message infrastructure. (e.g order_messaging)
│       │   ├── [name]_producer.{ext} # INCLUDE: concrete broker publishing like (e.g [`OrderEventProducer`, `publish`, `ORDER_TOPIC`]). NOT INCLUDE: domain event definitions, use-case orchestration, or controller parsing.
│       │   ├── [name]_subscriber.{ext} # INCLUDE: broker subscription wiring like (e.g [`OrderSubscriber`, `subscribe`, `ORDER_CONSUMER_GROUP`]). NOT INCLUDE: application event handling logic, domain calculations, or database schemas.
│       │   ├── [name]_message_bus.{ext} # INCLUDE: concrete message bus implementation like (e.g [`KafkaMessageBus`, `dispatch`, `MESSAGE_BUS_NAME`]). NOT INCLUDE: domain event classes, application port definitions, or HTTP routes.
│       │   └── [name]_topic_config.{ext} # INCLUDE: topic, exchange, routing, and queue configuration like (e.g [`OrderTopicConfig`, `topic_name`, `ORDER_EVENTS_TOPIC`]). NOT INCLUDE: use-case logic, entity invariants, or request DTOs.
│       ├── [cache]/ # MUST: Implement cache stores and cache-specific mechanics. (e.g order_cache)
│       │   ├── [name]_cache_store.{ext} # INCLUDE: concrete cache operations like (e.g [`OrderCacheStore`, `get`, `set`]). NOT INCLUDE: domain rules, controller responses, or use-case transaction decisions.
│       │   ├── [name]_cache_key.{ext} # INCLUDE: cache key building rules like (e.g [`OrderCacheKey`, `for_order_id`, `ORDER_CACHE_PREFIX`]). NOT INCLUDE: domain identifiers as raw persistence details, HTTP route paths, or SQL queries.
│       │   └── [name]_cache_policy.{ext} # INCLUDE: technical TTL and invalidation settings like (e.g [`OrderCachePolicy`, `ttl_for`, `ORDER_CACHE_TTL_SECONDS`]). NOT INCLUDE: business refund policies, application validation, or domain specifications.
│       ├── [storage]/ # MUST: Implement file/blob/object storage integrations. (e.g invoice_storage)
│       │   ├── [name]_storage_client.{ext} # INCLUDE: concrete storage provider operations like (e.g [`InvoiceStorageClient`, `upload`, `INVOICE_BUCKET_NAME`]). NOT INCLUDE: domain document rules, controller parsing, or hard-coded credentials.
│       │   ├── [name]_storage_mapper.{ext} # INCLUDE: mapping between application storage data and provider metadata like (e.g [`InvoiceStorageMapper`, `to_metadata`, `STORAGE_MAPPER_NAME`]). NOT INCLUDE: use-case orchestration, HTTP response formatting, or domain invariants.
│       │   └── [name]_storage_config.{ext} # INCLUDE: storage technical configuration like (e.g [`StorageConfig`, `load_storage_config`, `MAX_UPLOAD_BYTES`]). NOT INCLUDE: secret literal values, domain constants, or controller logic.
│       ├── [auth]/ # MUST: Implement authentication and identity provider integrations. (e.g jwt_auth)
│       │   ├── [name]_auth_provider.{ext} # INCLUDE: concrete identity provider calls like (e.g [`JwtAuthProvider`, `verify_token`, `AUTH_PROVIDER_NAME`]). NOT INCLUDE: domain authorization rules, use-case logic, or controller business decisions.
│       │   ├── [name]_token_parser.{ext} # INCLUDE: token decoding and technical claim extraction like (e.g [`JwtTokenParser`, `parse_claims`, `AUTH_HEADER_NAME`]). NOT INCLUDE: business permission decisions, repository access, or HTTP response formatting.
│       │   └── [name]_principal_mapper.{ext} # INCLUDE: mapping identity claims to application principal data like (e.g [`PrincipalMapper`, `to_principal`, `PRINCIPAL_VERSION`]). NOT INCLUDE: token verification implementation, domain model behavior, or SQL queries.
│       ├── [observability]/ # MUST: Implement logs, metrics, tracing, and audit infrastructure. (e.g order_observability)
│       │   ├── [name]_logger.{ext} # INCLUDE: concrete logging adapter like (e.g [`OrderLogger`, `info`, `LOGGER_NAME`]). NOT INCLUDE: business rule decisions, domain events as definitions, or controller routing.
│       │   ├── [name]_metrics.{ext} # INCLUDE: metrics counters, histograms, and tags like (e.g [`OrderMetrics`, `record_created`, `ORDER_CREATED_COUNTER`]). NOT INCLUDE: use-case branching rules, domain calculations, or database migrations.
│       │   ├── [name]_tracer.{ext} # INCLUDE: tracing spans and context propagation like (e.g [`OrderTracer`, `start_span`, `TRACE_OPERATION_NAME`]). NOT INCLUDE: application validation, domain invariants, or HTTP request DTOs.
│       │   └── [name]_audit_writer.{ext} # INCLUDE: technical audit sink integration like (e.g [`AuditWriter`, `write_event`, `AUDIT_STREAM_NAME`]). NOT INCLUDE: domain event definition, business policy code, or controller response formatting.
│       ├── [config]/ # MUST: Load and validate runtime configuration. (e.g order_config)
│       │   ├── [name]_config.{ext} # INCLUDE: typed configuration loading and defaults like (e.g [`OrderConfig`, `load`, `ORDER_CONFIG_PREFIX`]). NOT INCLUDE: secret literal values, domain constants, or use-case business logic.
│       │   ├── [name]_env.{ext} # INCLUDE: environment variable names and parsing helpers like (e.g [`OrderEnv`, `read_env`, `ORDER_ENV_PREFIX`]). NOT INCLUDE: credentials committed to code, domain behavior, or controller actions.
│       │   └── [name]_feature_flag.{ext} # INCLUDE: technical feature flag access like (e.g [`FeatureFlagClient`, `is_enabled`, `CHECKOUT_FLAG`]). NOT INCLUDE: business rules as flags, use-case orchestration, or database schema definitions.
│       ├── [security]/ # MUST: Implement technical security utilities and protections. (e.g crypto)
│       │   ├── [name]_encryptor.{ext} # INCLUDE: encryption/decryption implementation like (e.g [`FieldEncryptor`, `encrypt`, `ENCRYPTION_ALGORITHM`]). NOT INCLUDE: business authorization rules, HTTP controllers, or secret literal values.
│       │   ├── [name]_hasher.{ext} # INCLUDE: hashing implementation like (e.g [`PasswordHasher`, `hash`, `HASH_ALGORITHM`]). NOT INCLUDE: user registration use-case logic, domain password policy, or controller validation.
│       │   └── [name]_sanitizer.{ext} # INCLUDE: technical sanitization utilities like (e.g [`InputSanitizer`, `sanitize`, `SANITIZER_NAME`]). NOT INCLUDE: domain validation rules, persistence mapping, or presenter formatting.
│       └── [resilience]/ # MUST: Implement retry, timeout, circuit-breaker, and fallback details. (e.g payment_resilience)
│           ├── [name]_retry_policy.{ext} # INCLUDE: technical retry policy configuration like (e.g [`PaymentRetryPolicy`, `should_retry`, `MAX_RETRY_ATTEMPTS`]). NOT INCLUDE: business compensation rules, use-case orchestration, or domain events.
│           ├── [name]_circuit_breaker.{ext} # INCLUDE: circuit breaker setup and thresholds like (e.g [`PaymentCircuitBreaker`, `execute`, `FAILURE_THRESHOLD`]). NOT INCLUDE: domain policy decisions, controller mapping, or repository ports.
│           └── [name]_timeout_policy.{ext} # INCLUDE: technical timeout settings like (e.g [`PaymentTimeoutPolicy`, `timeout_for`, `PAYMENT_TIMEOUT_MS`]). NOT INCLUDE: business deadlines, application validation, or database migrations.
├── [composition]/ # Owns dependency wiring, module assembly, bootstrap, and runtime entrypoints.
│   └── (feat/sub_feat/...)/ # MUST: Group composition code by business capability and nested sub-capability. (e.g orders/checkout)
│       ├── [modules]/ # MUST: Assemble feature dependencies and expose a feature module. (e.g order_module)
│       │   ├── [name]_module.{ext} # INCLUDE: dependency graph registration for a feature like (e.g [`OrderModule`, `register`, `ORDER_MODULE_NAME`]). NOT INCLUDE: business logic, SQL queries, or domain model methods.
│       │   ├── [name]_provider.{ext} # INCLUDE: provider/factory registration for dependencies like (e.g [`OrderProvider`, `provide_use_case`, `ORDER_PROVIDER_NAME`]). NOT INCLUDE: use-case implementation, controller behavior, or hard-coded secrets.
│       │   └── [name]_binding.{ext} # INCLUDE: port-to-adapter binding declarations like (e.g [`OrderBinding`, `bind_repository`, `ORDER_REPOSITORY_BINDING`]). NOT INCLUDE: repository implementation internals, domain rules, or HTTP parsing.
│       ├── [bootstrap]/ # MUST: Start and initialize runtime components for the feature or service. (e.g order_bootstrap)
│       │   ├── [name]_bootstrap.{ext} # INCLUDE: startup sequence and module initialization like (e.g [`OrderBootstrap`, `start`, `BOOTSTRAP_ORDER`]). NOT INCLUDE: business decisions, model invariants, or direct SQL statements.
│       │   └── [name]_lifecycle.{ext} # INCLUDE: startup/shutdown lifecycle hooks like (e.g [`OrderLifecycle`, `on_start`, `on_stop`]). NOT INCLUDE: use-case orchestration, domain events definitions, or controller actions.
│       ├── [entrypoints]/ # MUST: Declare executable entrypoints for the backend process. (e.g service_entrypoint)
│       │   ├── [name]_main.{ext} # INCLUDE: process entrypoint and global bootstrap call like (e.g [`main`, `start_application`, `APP_NAME`]). NOT INCLUDE: business rules, route handler implementations, or persistence schemas.
│       │   ├── [name]_worker_main.{ext} # INCLUDE: worker process entrypoint like (e.g [`worker_main`, `start_worker`, `WORKER_NAME`]). NOT INCLUDE: message handler business logic, domain calculations, or repository implementation.
│       │   └── [name]_cli_main.{ext} # INCLUDE: CLI process entrypoint like (e.g [`cli_main`, `run_command`, `CLI_APP_NAME`]). NOT INCLUDE: command business logic, direct database queries, or domain validation rules.
│       ├── [registries]/ # MUST: Register controllers, consumers, handlers, and infrastructure plugins. (e.g order_registry)
│       │   ├── [name]_controller_registry.{ext} # INCLUDE: controller registration and route binding like (e.g [`OrderControllerRegistry`, `register`, `ORDER_CONTROLLER_TAG`]). NOT INCLUDE: controller method logic, use-case implementation, or domain models.
│       │   ├── [name]_handler_registry.{ext} # INCLUDE: event/command/query handler registration like (e.g [`OrderHandlerRegistry`, `register_handlers`, `ORDER_HANDLER_TAG`]). NOT INCLUDE: handler business behavior, broker setup internals, or persistence queries.
│       │   └── [name]_adapter_registry.{ext} # INCLUDE: adapter and infrastructure registration like (e.g [`OrderAdapterRegistry`, `register_adapters`, `ORDER_ADAPTER_TAG`]). NOT INCLUDE: adapter method logic, domain rules, or request mapping.
│       └── [settings]/ # MUST: Compose global and feature configuration into runtime settings. (e.g order_settings)
│           ├── [name]_settings.{ext} # INCLUDE: assembled runtime settings object like (e.g [`OrderSettings`, `from_config`, `SETTINGS_VERSION`]). NOT INCLUDE: secret literal values, business constants, or use-case code.
│           └── [name]_settings_validator.{ext} # INCLUDE: startup configuration validation like (e.g [`OrderSettingsValidator`, `validate`, `REQUIRED_SETTING_KEYS`]). NOT INCLUDE: domain validation, request validation, or controller logic.
└── [tests]/ # Validates Clean Architecture boundaries, behavior, adapters, and integrations without owning production behavior.
    └── (feat/sub_feat/...)/ # MUST: Group tests by business capability and nested sub-capability. (e.g orders/checkout)
        ├── [unit]/ # MUST: Test isolated units without real infrastructure. (e.g order_unit_tests)
        │   ├── [domain]/ # MUST: Test pure domain models, rules, value objects, and domain services. (e.g order_domain_tests)
        │   │   ├── [name]_model_spec.{ext} # INCLUDE: model behavior tests like (e.g [`OrderModelSpec`, `should_add_item`, `VALID_ORDER_FIXTURE`]). NOT INCLUDE: database calls, HTTP requests, or external services.
        │   │   ├── [name]_rule_spec.{ext} # INCLUDE: rule and policy tests like (e.g [`RefundPolicySpec`, `should_reject_late_refund`, `LATE_REFUND_CASE`]). NOT INCLUDE: controller setup, persistence fixtures, or framework bootstrapping.
        │   │   └── [name]_value_object_spec.{ext} # INCLUDE: value object validation/equality tests like (e.g [`MoneyValueObjectSpec`, `should_compare_amounts`, `USD_10`]). NOT INCLUDE: ORM mappings, route tests, or broker interactions.
        │   ├── [application]/ # MUST: Test use cases with mocked ports and pure application dependencies. (e.g order_application_tests)
        │   │   ├── [name]_use_case_spec.{ext} # INCLUDE: use-case orchestration tests with port fakes like (e.g [`CreateOrderUseCaseSpec`, `should_save_order`, `FAKE_ORDER_ID`]). NOT INCLUDE: real database access, real HTTP clients, or web server bootstrapping.
        │   │   ├── [name]_handler_spec.{ext} # INCLUDE: handler reaction tests like (e.g [`OrderCreatedHandlerSpec`, `should_publish_notification`, `FAKE_EVENT`]). NOT INCLUDE: broker connections, framework listeners, or persistence migrations.
        │   │   └── [name]_validator_spec.{ext} # INCLUDE: application input validation tests like (e.g [`CreateOrderValidatorSpec`, `should_reject_empty_items`, `INVALID_INPUT`]). NOT INCLUDE: HTTP response assertions, ORM fixtures, or external API calls.
        │   └── [interface_adapters]/ # MUST: Test adapter mapping and translation without real infrastructure. (e.g order_adapter_tests)
        │       ├── [name]_controller_spec.{ext} # INCLUDE: controller-to-use-case interaction tests like (e.g [`OrderControllerSpec`, `should_call_use_case`, `CREATE_REQUEST`]). NOT INCLUDE: real web server startup, database access, or domain business rule duplication.
        │       ├── [name]_mapper_spec.{ext} # INCLUDE: request/response mapping tests like (e.g [`OrderRequestMapperSpec`, `should_map_to_input`, `REQUEST_FIXTURE`]). NOT INCLUDE: repository calls, use-case orchestration, or framework integration.
        │       └── [name]_presenter_spec.{ext} # INCLUDE: presenter formatting tests like (e.g [`OrderPresenterSpec`, `should_format_response`, `RESULT_FIXTURE`]). NOT INCLUDE: HTTP routing, database queries, or external SDK calls.
        ├── [integration]/ # MUST: Test adapters with real or controlled infrastructure boundaries. (e.g order_integration_tests)
        │   ├── [name]_repository_it.{ext} # INCLUDE: repository adapter with database/test container like (e.g [`OrderRepositoryIT`, `should_persist_order`, `TEST_DB_URL`]). NOT INCLUDE: external production services, UI assertions, or unrelated feature workflows.
        │   ├── [name]_client_it.{ext} # INCLUDE: external client integration against fake/stub server like (e.g [`PaymentClientIT`, `should_authorize_payment`, `FAKE_PROVIDER_URL`]). NOT INCLUDE: domain rule tests, real secret values, or production endpoints.
        │   └── [name]_messaging_it.{ext} # INCLUDE: broker integration with test topics/queues like (e.g [`OrderMessagingIT`, `should_publish_event`, `TEST_TOPIC`]). NOT INCLUDE: business policy assertions, controller response formatting, or production broker access.
        ├── [contract]/ # MUST: Test contracts between adapters, APIs, events, and external systems. (e.g order_contract_tests)
        │   ├── [name]_api_contract_spec.{ext} # INCLUDE: request/response contract assertions like (e.g [`OrderApiContractSpec`, `should_match_schema`, `ORDER_API_CONTRACT_VERSION`]). NOT INCLUDE: domain model internals, SQL queries, or real external services.
        │   ├── [name]_event_contract_spec.{ext} # INCLUDE: event schema compatibility tests like (e.g [`OrderCreatedEventContractSpec`, `should_match_event_schema`, `EVENT_CONTRACT_VERSION`]). NOT INCLUDE: broker runtime setup, use-case execution, or persistence details.
        │   └── [name]_gateway_contract_spec.{ext} # INCLUDE: outbound provider contract tests like (e.g [`PaymentGatewayContractSpec`, `should_match_provider_contract`, `PROVIDER_CONTRACT_VERSION`]). NOT INCLUDE: domain policies, real credentials, or controller tests.
        ├── [e2e]/ # MUST: Test full backend behavior through public boundaries. (e.g order_e2e_tests)
        │   ├── [name]_api_e2e.{ext} # INCLUDE: end-to-end API behavior through server boundary like (e.g [`OrderApiE2E`, `should_create_order`, `E2E_ORDER_PAYLOAD`]). NOT INCLUDE: unit-level implementation assertions, private method tests, or production service calls.
        │   ├── [name]_worker_e2e.{ext} # INCLUDE: worker flow through message boundary like (e.g [`OrderWorkerE2E`, `should_process_order_event`, `E2E_EVENT_PAYLOAD`]). NOT INCLUDE: domain-only unit assertions, real production brokers, or manual steps.
        │   └── [name]_workflow_e2e.{ext} # INCLUDE: complete business workflow through public adapters like (e.g [`CheckoutWorkflowE2E`, `should_complete_checkout`, `CHECKOUT_SCENARIO`]). NOT INCLUDE: persistence implementation details, private adapter assertions, or real payment charges.
        ├── [fixtures]/ # MUST: Provide deterministic test data shared by tests. (e.g order_fixtures)
        │   ├── [name]_fixture.{ext} # INCLUDE: reusable test objects and payloads like (e.g [`OrderFixture`, `valid_order`, `VALID_ORDER_ID`]). NOT INCLUDE: production data, secret values, or behavior under test.
        │   ├── [name]_payload_fixture.{ext} # INCLUDE: transport payload fixtures like (e.g [`CreateOrderPayloadFixture`, `valid_payload`, `CREATE_ORDER_JSON`]). NOT INCLUDE: controller implementation, use-case logic, or database queries.
        │   └── [name]_event_fixture.{ext} # INCLUDE: event fixtures like (e.g [`OrderCreatedEventFixture`, `valid_event`, `ORDER_CREATED_EVENT_JSON`]). NOT INCLUDE: broker clients, production topic names, or event handler implementation.
        ├── [builders]/ # MUST: Build test objects with readable defaults. (e.g order_builders)
        │   ├── [name]_test_builder.{ext} # INCLUDE: fluent test data builders like (e.g [`OrderTestBuilder`, `with_item`, `DEFAULT_ORDER_ID`]). NOT INCLUDE: production factories, persistence logic, or framework bootstrapping.
        │   └── [name]_mock_builder.{ext} # INCLUDE: mock/fake dependency builders like (e.g [`OrderPortMockBuilder`, `with_saved_order`, `DEFAULT_MOCK_RESULT`]). NOT INCLUDE: real external clients, real repositories, or business logic.
        └── [architecture]/ # MUST: Test dependency direction and layer boundaries. (e.g clean_architecture_rules)
            ├── [name]_dependency_rule_spec.{ext} # INCLUDE: dependency direction checks like (e.g [`DependencyRuleSpec`, `domain_should_not_depend_on_infrastructure`, `FORBIDDEN_IMPORTS`]). NOT INCLUDE: business behavior assertions, database access, or HTTP calls.
            └── [name]_module_boundary_spec.{ext} # INCLUDE: feature/module boundary checks like (e.g [`ModuleBoundarySpec`, `should_not_cross_feature_boundary`, `ALLOWED_DEPENDENCIES`]). NOT INCLUDE: runtime workflow tests, external service calls, or persistence schemas.
```

**IMPORTANT**: This **IS NOT FIXED DIR-TREE** use as responsibility distribution guideline patern.
