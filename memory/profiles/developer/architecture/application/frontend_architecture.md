# Architectural distribution patterns for (Front-End Codebase)

Organize the codebase tree to following verticals sliced Clean Architecture ( under **featurizer segmentation**):

## Tree

```powershell
{codebase_root}/ # Owns the complete FrontEnd workspace and keeps Clean Architecture boundaries explicit.
├── [domain]/ # Encapsulates enterprise rules, domain language, and pure business invariants.
│   └── (feat/sub_feat/...)/ # MUST: Group domain artifacts by business capability path while staying independent from UI, transport, and storage. (e.g identity/profile)
│       ├── [models]/ # MUST: Represent domain entities as code models with identity, behavior, and invariants. (e.g user)
│       │   ├── [name]_model.{ext} # INCLUDE: domain fields, invariants, and behavior like (e.g `User`, `rename_user`, `is_verified`). NOT INCLUDE: UI labels, HTTP payload fields, database records, framework lifecycle hooks.
│       │   ├── [name]_rule.{ext} # INCLUDE: pure entity rule functions like (e.g `can_user_change_email`, `UserActivationRule`). NOT INCLUDE: remote calls, storage reads, notifications, analytics.
│       │   └── [name]_policy.{ext} # INCLUDE: domain policy decisions like (e.g `PasswordPolicy`, `can_reset_password`). NOT INCLUDE: screen permissions, route guards, token parsing, role fetching.
│       ├── [aggregates]/ # MUST: Protect consistency boundaries around related domain models. (e.g cart)
│       │   ├── [name]_aggregate.{ext} # INCLUDE: aggregate root operations and invariant enforcement like (e.g `Cart`, `add_item`, `calculate_total`). NOT INCLUDE: UI state mutations, HTTP request execution, local cache writes.
│       │   └── [name]_spec.{ext} # INCLUDE: pure aggregate predicates and consistency checks like (e.g `CartCanCheckoutSpec`, `is_cart_ready_to_checkout`). NOT INCLUDE: application workflow orchestration, API validation, persistence queries.
│       ├── [value_objects]/ # MUST: Model immutable validated domain values. (e.g email)
│       │   ├── [name]_value_object.{ext} # INCLUDE: validation, normalization, equality, and formatting-safe value behavior like (e.g `EmailAddress`, `from_string`). NOT INCLUDE: form widgets, translation keys, database columns, network DTOs.
│       │   └── [name]_constant.{ext} # INCLUDE: value-specific domain constants like (e.g `MAX_EMAIL_LENGTH`, `DEFAULT_CURRENCY_CODE`). NOT INCLUDE: UI breakpoints, API endpoints, storage keys.
│       ├── [events]/ # MUST: Describe domain facts that already happened and can be reacted to by inner or application-level handlers. (e.g user_registered)
│       │   ├── [name]_event.{ext} # INCLUDE: event name, timestamp, aggregate identifier, and immutable payload like (e.g `UserRegisteredEvent`, `occurred_at`). NOT INCLUDE: message broker metadata, UI notifications, HTTP headers.
│       │   └── [name]_handler.{ext} # INCLUDE: pure domain reaction logic that produces domain changes or new domain events like (e.g `ApplyDiscountOnItemAddedHandler`, `handle_item_added`). NOT INCLUDE: sending email, logging providers, repository saves, UI refreshes.
│       ├── [enums]/ # MUST: Centralize closed domain vocabularies and legal states. (e.g order_status)
│       │   └── [name]_enum.{ext} # INCLUDE: allowed domain values and transition helpers like (e.g `OrderStatus`, `is_terminal_status`). NOT INCLUDE: translated labels, CSS classes, API-specific status codes unless mapped explicitly elsewhere.
│       ├── [constants]/ # MUST: Store stable business constants shared by domain objects. (e.g limits)
│       │   └── [name]_constant.{ext} # INCLUDE: domain-level limits, defaults, and symbolic names like (e.g `MIN_PASSWORD_SCORE`, `MAX_CART_ITEMS`). NOT INCLUDE: environment variables, route names, component sizes, cache keys.
│       └── [specs]/ # MUST: Capture reusable pure business predicates using the specification pattern. (e.g eligibility)
│           └── [name]_spec.{ext} # INCLUDE: composable domain checks like (e.g `CustomerCanUseCouponSpec`, `is_coupon_applicable`). NOT INCLUDE: validators for forms, API schemas, persistence filters, UI visibility conditions.
├── [application]/ # Coordinates use cases, owns ports/contracts, and translates intentions into domain operations.
│   └── (feat/sub_feat/...)/ # MUST: Mirror the feature/sub-feature path used by the domain while exposing application workflows. (e.g identity/profile)
│       ├── [use_cases]/ # MUST: Expose business workflows as application operations. (e.g sign_in)
│       │   ├── [commands]/ # MUST: Represent state-changing intentions. (e.g update_profile)
│       │   │   ├── [name]_command.{ext} # INCLUDE: command input shape and creation helpers like (e.g `UpdateProfileCommand`, `create_update_profile_command`). NOT INCLUDE: UI event objects, HTTP request objects, storage records.
│       │   │   ├── [name]_handler.{ext} # INCLUDE: orchestration of domain models, ports, validators, and transaction-like flow like (e.g `UpdateProfileHandler`, `handle_update_profile`). NOT INCLUDE: rendering, concrete API clients, concrete local storage calls.
│       │   │   └── [name]_result.{ext} # INCLUDE: use-case outcome shape and success/failure variants like (e.g `UpdateProfileResult`, `profile_updated`). NOT INCLUDE: component props, HTTP response metadata, database row structures.
│       │   ├── [queries]/ # MUST: Represent read-only application intentions. (e.g get_profile)
│       │   │   ├── [name]_query.{ext} # INCLUDE: query parameters and read criteria like (e.g `GetProfileQuery`, `include_preferences`). NOT INCLUDE: SQL strings, HTTP URLs, UI filter widgets.
│       │   │   ├── [name]_handler.{ext} # INCLUDE: read orchestration through ports and mappers like (e.g `GetProfileHandler`, `handle_get_profile`). NOT INCLUDE: direct fetch calls, view rendering, storage implementation details.
│       │   │   └── [name]_result.{ext} # INCLUDE: read outcome shape like (e.g `GetProfileResult`, `ProfileSummary`). NOT INCLUDE: raw API payloads, UI component state, persistence records.
│       │   └── [interactors]/ # MUST: Provide command/query-neutral use-case classes or functions when the project does not split CQRS. (e.g onboarding)
│       │       └── [name]_use_case.{ext} # INCLUDE: application workflow orchestration like (e.g `CompleteOnboardingUseCase`, `execute_complete_onboarding`). NOT INCLUDE: UI rendering, framework routing, repository implementation.
│       ├── [services]/ # MUST: Group application business services that coordinate multiple use cases or domain concepts. (e.g session)
│       │   └── [name]_service.{ext} # INCLUDE: cross-use-case coordination like (e.g `SessionService`, `refresh_session_if_needed`). NOT INCLUDE: domain invariants that belong in models, concrete adapters, component state.
│       ├── [ports]/ # MUST: Define application-owned boundaries that outer layers implement or call. (e.g profile_gateway)
│       │   ├── [inbound]/ # MUST: Define operations exposed to the Presentation layer. (e.g profile_actions)
│       │   │   ├── [name]_port.{ext} # INCLUDE: callable input boundary signatures like (e.g `ProfileInputPort`, `update_profile`). NOT INCLUDE: UI framework types, route objects, HTML events.
│       │   │   └── [name]_interface.{ext} # INCLUDE: language-agnostic service contract shape like (e.g `ProfileActions`, `load_profile`). NOT INCLUDE: implementation code, adapter imports, view model formatting.
│       │   └── [outbound]/ # MUST: Define operations required from Infrastructure or Persistence. (e.g profile_repository)
│       │       ├── [name]_port.{ext} # INCLUDE: dependency boundary methods like (e.g `ProfileRepositoryPort`, `save_profile`). NOT INCLUDE: HTTP client names, storage keys, SDK instances.
│       │       └── [name]_interface.{ext} # INCLUDE: abstract external capability signatures like (e.g `TokenProvider`, `get_access_token`). NOT INCLUDE: token storage mechanics, vendor SDK setup, logging implementation.
│       ├── [contracts]/ # MUST: Define stable application contracts exchanged across use cases and ports. (e.g profile_contracts)
│       │   ├── [name]_contract.{ext} # INCLUDE: public application contract structures like (e.g `ProfileContract`, `ProfileCapability`). NOT INCLUDE: UI-only props, vendor payloads, persistence schemas.
│       │   └── [name]_abstraction.{ext} # INCLUDE: abstract concepts shared by use cases like (e.g `Clock`, `IdGenerator`). NOT INCLUDE: concrete system time calls, UUID library imports, platform APIs.
│       ├── [dtos]/ # MUST: Carry application data across boundaries without domain behavior. (e.g profile_dto)
│       │   ├── [requests]/ # MUST: Represent application request models after UI input has been normalized. (e.g update_profile_request)
│       │   │   └── [name]_request.{ext} # INCLUDE: validated request shape like (e.g `UpdateProfileRequest`, `display_name`). NOT INCLUDE: raw form controls, HTTP headers, database IDs not owned by the application.
│       │   ├── [responses]/ # MUST: Represent application response models before the Presentation layer formats them. (e.g profile_response)
│       │   │   └── [name]_response.{ext} # INCLUDE: response fields and outcome metadata like (e.g `ProfileResponse`, `updated_at`). NOT INCLUDE: CSS classes, raw API envelopes, domain methods.
│       │   └── [mappers]/ # MUST: Convert domain models to DTOs and DTOs to domain-safe inputs. (e.g profile_mapper)
│       │       └── [name]_mapper.{ext} # INCLUDE: pure transformations like (e.g `map_user_to_profile_response`, `ProfileDtoMapper`). NOT INCLUDE: HTTP calls, local storage access, component formatting.
│       ├── [validators]/ # MUST: Validate application requests and commands before domain execution. (e.g profile_validation)
│       │   ├── [name]_validator.{ext} # INCLUDE: input validation rules like (e.g `UpdateProfileValidator`, `validate_update_profile`). NOT INCLUDE: DOM validation messages, persistence constraints, API status handling.
│       │   └── [name]_ruleset.{ext} # INCLUDE: reusable application validation rule groups like (e.g `ProfileRuleset`, `required_display_name`). NOT INCLUDE: domain invariants already enforced by value objects, UI translations, CSS state.
│       ├── [behaviors]/ # MUST: Apply application pipeline behaviors around handlers. (e.g retry_validation)
│       │   ├── [name]_behavior.{ext} # INCLUDE: cross-cutting handler steps like (e.g `ValidationBehavior`, `with_validation`). NOT INCLUDE: UI middleware, HTTP interceptors, vendor SDK configuration.
│       │   └── [name]_pipeline.{ext} # INCLUDE: handler composition logic like (e.g `UseCasePipeline`, `compose_behaviors`). NOT INCLUDE: framework routers, component trees, concrete adapter construction.
│       ├── [events]/ # MUST: React to domain/application events by coordinating ports and use cases. (e.g profile_events)
│       │   ├── [handlers]/ # MUST: Keep side-effect orchestration caused by events in the application boundary. (e.g welcome_flow)
│       │   │   └── [name]_handler.{ext} # INCLUDE: event handling orchestration through ports like (e.g `SendWelcomeNotificationHandler`, `handle_user_registered`). NOT INCLUDE: direct email SDK calls, UI toasts, storage implementation.
│       │   └── [publishers]/ # MUST: Define how application events are published through abstract ports. (e.g app_event_bus)
│       │       └── [name]_port.{ext} # INCLUDE: abstract publish/subscribe operations like (e.g `ApplicationEventBusPort`, `publish_event`). NOT INCLUDE: concrete message broker, browser channel, logger.
│       ├── [errors]/ # MUST: Define application-level failures and exception equivalents. (e.g profile_errors)
│       │   ├── [name]_error.{ext} # INCLUDE: typed failure objects and error codes like (e.g `ProfileNotFoundError`, `PROFILE_NOT_FOUND`). NOT INCLUDE: HTTP status mapping, toast messages, log sinks.
│       │   └── [name]_exception.{ext} # INCLUDE: exceptional application failure shape when the language/runtime uses exceptions like (e.g `UseCaseException`, `throw_profile_locked`). NOT INCLUDE: transport exceptions, UI error boundaries, vendor SDK errors.
│       └── [specs]/ # MUST: Express application-level selection or workflow specifications. (e.g profile_access)
│           └── [name]_spec.{ext} # INCLUDE: workflow predicates like (e.g `ProfileCanBeEditedSpec`, `can_edit_profile`). NOT INCLUDE: persistence query code, UI visibility checks, domain invariant duplication.
├── [infrastructure]/ # Implements technical adapters for external services, platform APIs, and framework-specific details.
│   └── (feat/sub_feat/...)/ # MUST: Mirror the feature/sub-feature path while keeping technical implementations outside the core. (e.g identity/profile)
│       ├── [http]/ # MUST: Implement network transport used by infrastructure adapters. (e.g rest)
│       │   ├── [clients]/ # MUST: Encapsulate HTTP or RPC client setup. (e.g profile_api)
│       │   │   ├── [name]_client.{ext} # INCLUDE: low-level request execution like (e.g `ProfileApiClient`, `send_request`). NOT INCLUDE: domain decisions, UI state, use-case orchestration.
│       │   │   └── [name]_config.{ext} # INCLUDE: client base settings and transport options like (e.g `PROFILE_API_BASE_URL`, `create_http_config`). NOT INCLUDE: secrets in source code, domain constants, component config.
│       │   ├── [interceptors]/ # MUST: Apply transport-level request/response concerns. (e.g auth_header)
│       │   │   └── [name]_interceptor.{ext} # INCLUDE: request decoration and response normalization like (e.g `AuthHeaderInterceptor`, `attach_auth_header`). NOT INCLUDE: use-case validation, domain rules, UI notifications.
│       │   └── [serializers]/ # MUST: Convert transport payload formats at the edge. (e.g json_payload)
│       │       └── [name]_serializer.{ext} # INCLUDE: encode/decode logic like (e.g `JsonSerializer`, `serialize_profile_request`). NOT INCLUDE: domain behavior, component formatting, repository policy.
│       ├── [auth]/ # MUST: Integrate authentication and identity providers. (e.g oidc)
│       │   ├── [identity]/ # MUST: Adapt identity-provider SDKs or APIs to application ports. (e.g account_provider)
│       │   │   ├── [name]_adapter.{ext} # INCLUDE: application port implementation like (e.g `IdentityProviderAdapter`, `get_current_identity`). NOT INCLUDE: domain invariants, route rendering, storage schema ownership.
│       │   │   └── [name]_provider.{ext} # INCLUDE: provider lifecycle wrapper like (e.g `IdentitySdkProvider`, `initialize_identity_sdk`). NOT INCLUDE: use-case decisions, UI components, persistence migrations.
│       │   ├── [tokens]/ # MUST: Handle token access through infrastructure abstractions. (e.g access_token)
│       │   │   └── [name]_provider.{ext} # INCLUDE: token acquisition and refresh implementation like (e.g `AccessTokenProvider`, `refresh_access_token`). NOT INCLUDE: domain identity model behavior, UI login form, raw token display.
│       │   └── [social_login]/ # MUST: Isolate social login provider integration. (e.g google_login)
│       │       └── [name]_adapter.{ext} # INCLUDE: social provider sign-in implementation like (e.g `SocialLoginAdapter`, `sign_in_with_provider`). NOT INCLUDE: application profile merging policy, route navigation, UI button styling.
│       ├── [files]/ # MUST: Integrate file and object storage capabilities. (e.g avatar_upload)
│       │   ├── [storage]/ # MUST: Implement file/object storage ports. (e.g media_bucket)
│       │   │   └── [name]_adapter.{ext} # INCLUDE: upload, download, delete, and URL generation logic like (e.g `AvatarStorageAdapter`, `upload_avatar`). NOT INCLUDE: domain validation, image component rendering, form state.
│       │   └── [mappers]/ # MUST: Convert file service payloads to application contracts. (e.g uploaded_file)
│       │       └── [name]_mapper.{ext} # INCLUDE: external file metadata mapping like (e.g `map_upload_response_to_file_dto`). NOT INCLUDE: rendering previews, domain rules, storage migrations.
│       ├── [messaging]/ # MUST: Adapt browser channels, queues, sockets, or event buses used by the FrontEnd. (e.g realtime)
│       │   ├── [queues]/ # MUST: Provide queue-like delivery abstractions when the client runtime supports them. (e.g offline_outbox)
│       │   │   └── [name]_adapter.{ext} # INCLUDE: enqueue, dequeue, acknowledge, and retry implementation like (e.g `OfflineOutboxAdapter`, `enqueue_command`). NOT INCLUDE: use-case business decisions, UI notifications, domain events definitions.
│       │   ├── [sockets]/ # MUST: Encapsulate real-time connection clients. (e.g notifications_socket)
│       │   │   └── [name]_client.{ext} # INCLUDE: connect, subscribe, unsubscribe, reconnect logic like (e.g `NotificationsSocketClient`, `subscribe_to_channel`). NOT INCLUDE: view rendering, domain model mutation, storage record schemas.
│       │   └── [mappers]/ # MUST: Translate transport messages to application events or DTOs. (e.g socket_event)
│       │       └── [name]_mapper.{ext} # INCLUDE: payload-to-event conversion like (e.g `map_socket_message_to_notification_event`). NOT INCLUDE: event side effects, UI toasts, repository writes.
│       ├── [notifications]/ # MUST: Integrate user notification providers or notification-triggering services. (e.g push)
│       │   └── [name]_adapter.{ext} # INCLUDE: notification permission, registration, and send/trigger calls through ports like (e.g `PushNotificationAdapter`, `request_permission`). NOT INCLUDE: notification copywriting, domain event definitions, component rendering.
│       ├── [third_party]/ # MUST: Isolate vendor SDK integrations. (e.g maps)
│       │   ├── [sdk]/ # MUST: Wrap vendor SDK lifecycle and configuration. (e.g maps_sdk)
│       │   │   ├── [name]_provider.{ext} # INCLUDE: SDK initialization and disposal like (e.g `MapsSdkProvider`, `load_maps_sdk`). NOT INCLUDE: domain policies, use-case orchestration, UI layout.
│       │   │   └── [name]_config.{ext} # INCLUDE: vendor SDK runtime options like (e.g `MAPS_SDK_OPTIONS`, `create_maps_config`). NOT INCLUDE: hard-coded secrets, domain constants, component props.
│       │   └── [adapters]/ # MUST: Implement application ports using vendor capabilities. (e.g geocoding)
│       │       └── [name]_adapter.{ext} # INCLUDE: vendor-to-port implementation like (e.g `GeocodingAdapter`, `find_coordinates`). NOT INCLUDE: UI autocomplete rendering, domain value validation, persistence mapping.
│       ├── [logging]/ # MUST: Implement logging, telemetry, and error-reporting ports. (e.g telemetry)
│       │   ├── [name]_logger.{ext} # INCLUDE: structured logging adapter like (e.g `AppLogger`, `log_info`). NOT INCLUDE: domain decisions, UI error messages, transport retry policy.
│       │   ├── [name]_reporter.{ext} # INCLUDE: error reporting integration like (e.g `ErrorReporter`, `capture_exception`). NOT INCLUDE: exception definitions, component error boundaries, user-facing alerts.
│       │   └── [name]_adapter.{ext} # INCLUDE: analytics/telemetry port implementation like (e.g `TelemetryAdapter`, `track_event`). NOT INCLUDE: domain events definitions, UI interaction handlers, persistence storage.
│       ├── [payments]/ # MUST: Isolate payment provider integrations when the FrontEnd initiates checkout. (e.g checkout)
│       │   ├── [name]_adapter.{ext} # INCLUDE: payment port implementation like (e.g `PaymentGatewayAdapter`, `start_checkout`). NOT INCLUDE: pricing rules, cart invariants, UI checkout form layout.
│       │   ├── [name]_client.{ext} # INCLUDE: provider-specific client calls like (e.g `CheckoutClient`, `create_payment_session`). NOT INCLUDE: application authorization policy, component state, domain calculations.
│       │   └── [name]_mapper.{ext} # INCLUDE: payment provider payload mapping like (e.g `map_payment_session_to_checkout_response`). NOT INCLUDE: UI messages, repository implementation, domain value objects.
│       ├── [config]/ # MUST: Centralize runtime configuration for outer technical concerns. (e.g env)
│       │   ├── [name]_config.{ext} # INCLUDE: environment-derived settings like (e.g `RuntimeConfig`, `get_api_base_url`). NOT INCLUDE: business constants, domain defaults, component props.
│       │   └── [name]_provider.{ext} # INCLUDE: configuration access abstraction like (e.g `ConfigProvider`, `read_runtime_config`). NOT INCLUDE: direct UI rendering, domain rules, storage migrations.
│       └── [composition]/ # MUST: Wire application ports to infrastructure and persistence implementations at the outer edge. (e.g profile_module)
│           ├── [name]_module.{ext} # INCLUDE: feature dependency registrations like (e.g `ProfileInfrastructureModule`, `register_profile_adapters`). NOT INCLUDE: business rules, UI layout, domain model definitions.
│           └── [name]_container.{ext} # INCLUDE: dependency container factory or service locator setup like (e.g `create_profile_container`, `PROFILE_PROVIDERS`). NOT INCLUDE: handler business logic, component rendering, vendor payload mapping.
├── [persistence]/ # Provides client-side data contexts, repository implementations, migrations, seeds, and caching.
│   └── (feat/sub_feat/...)/ # MUST: Mirror the feature/sub-feature path while keeping storage details outside Application and Domain. (e.g identity/profile)
│       ├── [data_context]/ # MUST: Encapsulate storage connection/session context for a feature. (e.g profile_db)
│       │   ├── [name]_data_context.{ext} # INCLUDE: storage context creation and unit-of-work-like boundaries like (e.g `ProfileDataContext`, `open_profile_store`). NOT INCLUDE: domain invariants, UI rendering, use-case orchestration.
│       │   └── [name]_config.{ext} # INCLUDE: storage names, versions, and connection options like (e.g `PROFILE_STORE_VERSION`, `profile_store_name`). NOT INCLUDE: API base URLs, UI constants, domain limits.
│       ├── [repositories]/ # MUST: Implement application repository ports using concrete storage. (e.g profile_repository)
│       │   ├── [name]_repository.{ext} # INCLUDE: save, find, remove, and query implementations like (e.g `ProfileRepository`, `find_profile_by_id`). NOT INCLUDE: UI state, domain rule definitions, HTTP transport.
│       │   └── [name]_mapper.{ext} # INCLUDE: domain-to-record and record-to-domain transformations like (e.g `map_profile_record_to_user`, `map_user_to_profile_record`). NOT INCLUDE: UI formatting, remote API calls, validation messages.
│       ├── [records]/ # MUST: Represent persistence-specific data records. (e.g profile_record)
│       │   ├── [name]_record.{ext} # INCLUDE: storage record shape and storage-only fields like (e.g `ProfileRecord`, `updated_index`). NOT INCLUDE: domain methods, UI props, application result variants.
│       │   └── [name]_schema.{ext} # INCLUDE: storage schema declarations like (e.g `ProfileSchema`, `PROFILE_RECORD_SCHEMA`). NOT INCLUDE: domain model behavior, form schemas, API contracts.
│       ├── [storage]/ # MUST: Encapsulate concrete client storage mechanisms. (e.g key_value)
│       │   ├── [key_value]/ # MUST: Store simple key-value data. (e.g preferences)
│       │   │   └── [name]_storage.{ext} # INCLUDE: get, set, remove, and clear primitives like (e.g `PreferencesStorage`, `set_preference`). NOT INCLUDE: domain workflows, component state, API clients.
│       │   ├── [document]/ # MUST: Store structured document-like client data. (e.g offline_profiles)
│       │   │   └── [name]_storage.{ext} # INCLUDE: document read/write/query primitives like (e.g `OfflineProfileStorage`, `put_document`). NOT INCLUDE: use-case decisions, view formatting, identity provider calls.
│       │   └── [secure]/ # MUST: Store sensitive client data through platform-supported secure mechanisms when available. (e.g session_secret)
│       │       └── [name]_storage.{ext} # INCLUDE: secure read/write/delete primitives like (e.g `SecureTokenStorage`, `store_refresh_token`). NOT INCLUDE: token refresh policy, login UI, domain identity behavior.
│       ├── [migrations]/ # MUST: Evolve client-side storage schemas safely. (e.g v2_profile)
│       │   ├── [name]_migration.{ext} # INCLUDE: forward migration steps like (e.g `ProfileV2Migration`, `migrate_profile_records`). NOT INCLUDE: domain use cases, component rendering, remote API versioning.
│       │   └── [name]_migration_plan.{ext} # INCLUDE: ordered migration registration like (e.g `ProfileMigrationPlan`, `PROFILE_MIGRATIONS`). NOT INCLUDE: business workflows, UI state, external SDK initialization.
│       ├── [seeds]/ # MUST: Provide development, demo, or offline seed data when appropriate. (e.g demo_profile)
│       │   ├── [name]_seed.{ext} # INCLUDE: deterministic seed records like (e.g `seed_demo_profiles`, `DEMO_PROFILE_RECORDS`). NOT INCLUDE: production secrets, domain policies, UI snapshots.
│       │   └── [name]_fixture.{ext} # INCLUDE: reusable test/demo persistence fixtures like (e.g `ProfileRecordFixture`, `create_profile_record_fixture`). NOT INCLUDE: use-case tests, component mocks, vendor SDK stubs.
│       ├── [cache]/ # MUST: Store derived or fetched data with explicit invalidation rules. (e.g profile_cache)
│       │   ├── [memory]/ # MUST: Keep ephemeral runtime cache. (e.g session_cache)
│       │   │   └── [name]_cache.{ext} # INCLUDE: in-memory cache read/write/evict logic like (e.g `ProfileMemoryCache`, `remember_profile`). NOT INCLUDE: durable storage schemas, UI state, domain invariants.
│       │   ├── [persistent]/ # MUST: Keep durable cache that survives page reloads when useful. (e.g catalog_cache)
│       │   │   └── [name]_cache.{ext} # INCLUDE: persistent cache adapter like (e.g `CatalogPersistentCache`, `cache_catalog_page`). NOT INCLUDE: repository business policy, component subscriptions, remote client setup.
│       │   └── [invalidators]/ # MUST: Centralize cache eviction and freshness rules. (e.g profile_freshness)
│       │       └── [name]_invalidator.{ext} # INCLUDE: invalidation conditions and cache key decisions like (e.g `ProfileCacheInvalidator`, `invalidate_after_profile_update`). NOT INCLUDE: UI refresh logic, domain events definitions, HTTP interceptors.
│       └── [serializers]/ # MUST: Encode and decode persistence formats. (e.g record_json)
│           └── [name]_serializer.{ext} # INCLUDE: storage-safe serialization logic like (e.g `ProfileRecordSerializer`, `deserialize_profile_record`). NOT INCLUDE: HTTP serialization, UI formatting, domain invariant checks.
└── [presentation]/ # Owns user-facing delivery, view state, interaction handling, and UI-to-application mapping.
|   └── (feat/sub_feat/...)/ # MUST: Mirror the feature/sub-feature path while keeping user interaction separate from business rules. (e.g identity/profile)
|       ├── [routes]/ # MUST: Define navigation entries and route-level data boundaries. (e.g profile_route)
|       │   ├── [name]_route.{ext} # INCLUDE: path metadata, route composition, and screen binding like (e.g `ProfileRoute`, `profile_route`). NOT INCLUDE: domain rules, concrete repositories, API client setup.
|       │   ├── [name]_guard.{ext} # INCLUDE: route access checks using application ports like (e.g `AuthenticatedGuard`, `can_enter_profile_route`). NOT INCLUDE: token parsing implementation, domain authorization policy, UI rendering.
|       │   └── [name]_loader.{ext} # INCLUDE: route data loading orchestration through application queries like (e.g `ProfileLoader`, `load_profile_route_data`). NOT INCLUDE: direct HTTP calls, storage queries, component styling.
|       ├── [pages]/ # MUST: Compose route-level screens from views, layouts, and application-facing controllers. (e.g profile_page)
|       │   ├── [name]_page.{ext} # INCLUDE: page composition and feature-level screen assembly like (e.g `ProfilePage`, `render_profile_page`). NOT INCLUDE: domain invariants, repository calls, vendor SDK initialization.
|       │   └── [name]_page_meta.{ext} # INCLUDE: page metadata and user-facing navigation descriptors like (e.g `ProfilePageMeta`, `PROFILE_PAGE_TITLE`). NOT INCLUDE: business constants, API endpoints, persistence schemas.
|       ├── [layouts]/ # MUST: Define reusable visual regions and page shells. (e.g account_layout)
|       │   ├── [name]_layout.{ext} # INCLUDE: layout structure and slot placement like (e.g `AccountLayout`, `render_account_shell`). NOT INCLUDE: use-case logic, storage access, domain policies.
|       │   └── [name]_slot.{ext} # INCLUDE: named content outlet definitions like (e.g `SidebarSlot`, `render_profile_sidebar_slot`). NOT INCLUDE: domain models, API calls, cache invalidation.
|       ├── [views]/ # MUST: Render feature-specific visual states from view models. (e.g profile_view)
|       │   ├── [name]_view.{ext} # INCLUDE: view rendering and display branching like (e.g `ProfileView`, `render_profile_view`). NOT INCLUDE: application workflow orchestration, repository access, domain invariant enforcement.
|       │   └── [name]_empty_view.{ext} # INCLUDE: specialized empty/error/loading visual state rendering like (e.g `ProfileEmptyView`, `render_empty_profile`). NOT INCLUDE: error classification policy, remote calls, storage state.
|       ├── [components]/ # MUST: Hold reusable UI building blocks for the feature. (e.g avatar)
|       │   ├── [ui]/ # MUST: Keep presentational components with minimal behavior. (e.g avatar_card)
|       │   │   ├── [name]_component.{ext} # INCLUDE: visual structure, slots, and user interaction outputs like (e.g `AvatarCard`, `on_avatar_clicked`). NOT INCLUDE: application use-case execution, API calls, domain calculations.
|       │   │   └── [name]_props.{ext} # INCLUDE: component input/output shape like (e.g `AvatarCardProps`, `on_select`). NOT INCLUDE: domain models with behavior, repository ports, storage records.
|       │   ├── [containers]/ # MUST: Connect UI components to presentation state and application controllers. (e.g profile_header)
|       │   │   └── [name]_component.{ext} # INCLUDE: state binding and controller calls like (e.g `ProfileHeaderContainer`, `load_profile`). NOT INCLUDE: direct infrastructure calls, persistence implementation, domain invariants.
|       │   └── [events]/ # MUST: Normalize UI interaction events before controller handling. (e.g avatar_events)
|       │       └── [name]_event.{ext} # INCLUDE: UI event payloads and component-level event names like (e.g `AvatarSelectedEvent`, `avatar_selected`). NOT INCLUDE: domain event definitions, message queue metadata, persistence records.
|       ├── [forms]/ # MUST: Own user input composition, UI validation messages, and request mapping. (e.g profile_form)
|       │   ├── [name]_form.{ext} # INCLUDE: form structure and submit orchestration to controllers like (e.g `ProfileForm`, `submit_profile_form`). NOT INCLUDE: domain persistence, API clients, aggregate invariants.
|       │   ├── [name]_field.{ext} # INCLUDE: field configuration and display constraints like (e.g `DisplayNameField`, `DISPLAY_NAME_FIELD`). NOT INCLUDE: domain value object implementation, repository calls, route guards.
|       │   ├── [name]_form_schema.{ext} # INCLUDE: UI-level form validation schema like (e.g `ProfileFormSchema`, `validate_profile_form_input`). NOT INCLUDE: domain invariant duplication beyond user input checks, API payload schemas, storage schema.
|       │   └── [name]_mapper.{ext} # INCLUDE: form-to-application request mapping like (e.g `map_profile_form_to_update_request`). NOT INCLUDE: API serialization, domain-to-record mapping, component rendering.
|       ├── [controllers]/ # MUST: Translate user intentions into application commands and queries. (e.g profile_controller)
|       │   ├── [name]_controller.{ext} # INCLUDE: UI action handlers and application port calls like (e.g `ProfileController`, `on_save_profile`). NOT INCLUDE: direct HTTP clients, storage implementation, domain rule enforcement.
|       │   └── [name]_presenter.{ext} # INCLUDE: presentation response handling and view model preparation like (e.g `ProfilePresenter`, `present_profile_updated`). NOT INCLUDE: use-case execution internals, repository mapping, vendor SDK logic.
|       ├── [view_models]/ # MUST: Shape application responses for visual consumption. (e.g profile_vm)
|       │   ├── [name]_view_model.{ext} # INCLUDE: render-ready data and UI state flags like (e.g `ProfileViewModel`, `can_show_avatar`). NOT INCLUDE: domain behavior, raw API payloads, persistence records.
|       │   ├── [name]_mapper.{ext} # INCLUDE: response-to-view-model mapping like (e.g `map_profile_response_to_view_model`). NOT INCLUDE: HTTP calls, domain invariant checks, storage access.
|       │   └── [name]_formatter.{ext} # INCLUDE: display formatting helpers like (e.g `ProfileDateFormatter`, `format_join_date`). NOT INCLUDE: domain value normalization, API serialization, repository querying.
|       ├── [state]/ # MUST: Manage feature presentation state, subscriptions, and side effects. (e.g profile_state)
|       │   ├── [stores]/ # MUST: Hold observable or reactive UI state containers. (e.g profile_store)
|       │   │   └── [name]_store.{ext} # INCLUDE: presentation state, status flags, and state transitions like (e.g `ProfileStore`, `set_loading`). NOT INCLUDE: domain models with behavior, concrete storage writes, transport code.
|       │   ├── [actions]/ # MUST: Describe UI state transitions or user-driven actions. (e.g profile_actions)
|       │   │   └── [name]_action.{ext} # INCLUDE: action names and payloads like (e.g `ProfileSavedAction`, `PROFILE_SAVE_REQUESTED`). NOT INCLUDE: domain events, API payloads, persistence records.
|       │   ├── [selectors]/ # MUST: Derive display data from presentation state. (e.g profile_selectors)
|       │   │   └── [name]_selector.{ext} # INCLUDE: pure derived-state functions like (e.g `select_profile_title`, `is_profile_dirty`). NOT INCLUDE: remote calls, domain invariant enforcement, storage queries.
|       │   └── [effects]/ # MUST: Bridge state changes to controllers or application calls when the chosen UI pattern requires it. (e.g profile_effects)
|       │       └── [name]_effect.{ext} # INCLUDE: presentation side-effect orchestration like (e.g `LoadProfileEffect`, `run_load_profile`). NOT INCLUDE: concrete HTTP adapters, repository implementations, domain rules.
|       ├── [middleware]/ # MUST: Apply presentation pipeline concerns around navigation, state, or controller execution. (e.g auth_redirect)
|       │   └── [name]_middleware.{ext} # INCLUDE: UI-layer interception logic like (e.g `AuthRedirectMiddleware`, `with_loading_state`). NOT INCLUDE: application behavior pipeline, HTTP interceptors, domain policies.
|       ├── [filters]/ # MUST: Filter UI collections or presentation requests without changing domain meaning. (e.g profile_list)
|       │   └── [name]_filter.{ext} # INCLUDE: view-level filter predicates and filter state mapping like (e.g `VisibleProfilesFilter`, `filter_visible_profiles`). NOT INCLUDE: repository queries, authorization policy, domain specifications.
|       ├── [directives]/ # MUST: Represent reusable UI attributes, annotations, or declarative behavior hooks. (e.g autofocus)
|       │   ├── [name]_directive.{ext} # INCLUDE: declarative UI behavior like (e.g `AutofocusDirective`, `apply_autofocus`). NOT INCLUDE: application use-case orchestration, domain models, persistence access.
|       │   └── [name]_attribute.{ext} # INCLUDE: attribute metadata or lightweight UI annotations like (e.g `TrackClickAttribute`, `TRACK_CLICK_ATTR`). NOT INCLUDE: domain annotations, API headers, storage keys.
|       ├── [styles]/ # MUST: Keep visual styling assets and design tokens. (e.g profile_theme)
|       │   ├── [tokens]/ # MUST: Define feature-level visual tokens. (e.g spacing)
|       │   │   └── [name]_tokens.{ext} # INCLUDE: design token values like (e.g `PROFILE_SPACING`, `profile_color_tokens`). NOT INCLUDE: domain constants, API URLs, validation rules.
|       │   ├── [themes]/ # MUST: Define theme variants for the feature. (e.g compact)
|       │   │   └── [name]_theme.{ext} # INCLUDE: theme maps and visual variants like (e.g `ProfileTheme`, `create_compact_theme`). NOT INCLUDE: business policies, use-case results, repository configuration.
|       │   └── [sheets]/ # MUST: Store feature-specific style sheets or style modules. (e.g profile_card)
|       │       └── [name]_styles.{ext} # INCLUDE: style declarations and visual classes like (e.g `profile_card_styles`, `PROFILE_CARD_CLASS`). NOT INCLUDE: application state, domain values, API payload mapping.
|       ├── [api]/ # MUST: Expose presentation-owned endpoints only when the FrontEnd framework includes API routes, BFF handlers, or edge handlers. (e.g profile_endpoint)
|       │   ├── [name]_endpoint.{ext} # INCLUDE: request/response endpoint boundary and application use-case invocation like (e.g `ProfileEndpoint`, `handle_profile_request`). NOT INCLUDE: domain rule definitions, concrete repository code, component rendering.
|       │   ├── [name]_controller.{ext} # INCLUDE: endpoint controller flow and response status mapping like (e.g `ProfileApiController`, `to_http_response`). NOT INCLUDE: UI component state, domain invariant implementation, storage schema.
|       │   └── [name]_mapper.{ext} # INCLUDE: endpoint request/response mapping like (e.g `map_http_request_to_profile_command`). NOT INCLUDE: visual formatting, repository implementation, vendor SDK calls.
|       ├── [assets]/ # MUST: Own static assets referenced by the feature presentation layer. (e.g profile_images)
|       │   ├── [name]_manifest.{ext} # INCLUDE: asset references and semantic aliases like (e.g `PROFILE_ASSETS`, `avatar_placeholder_asset`). NOT INCLUDE: business constants, API endpoints, persistence keys.
|       │   └── [name]_asset.{ext} # INCLUDE: asset metadata or generated asset module like (e.g `AvatarPlaceholderAsset`, `get_avatar_asset`). NOT INCLUDE: component logic, domain rules, remote storage clients.
|       └── [scripts]/ # MUST: Hold feature-local presentation scripts or UI bootstrap helpers when the framework requires them. (e.g profile_bootstrap)
|           ├── [name]_script.{ext} # INCLUDE: presentation-only bootstrap or enhancement logic like (e.g `profile_bootstrap`, `enhance_profile_page`). NOT INCLUDE: domain logic, application use-case internals, persistence implementation.
|           └── [name]_bootstrap.{ext} # INCLUDE: UI initialization hooks like (e.g `bootstrap_profile_ui`, `PROFILE_UI_BOOTSTRAP`). NOT INCLUDE: dependency container construction for infrastructure, domain rules, storage migrations.
└── [/documentation]
    ├── [/wiki]
    └── [domain]_[feat]_[docfile_type].md
```

**IMPORTANT**: This **IS NOT FIXED DIR-TREE** use as responsibility distribution guideline patern.
