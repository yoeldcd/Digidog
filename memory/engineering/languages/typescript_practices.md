# TypeScript development practices

## Clean architecture principles

- **Strict Type Safety**: TypeScript's static type system replaces JSDoc annotations with compile-time enforcement. All public APIs, parameters, return types, and internal state must carry explicit type annotations — never rely on `any` or inference for public contracts.
- **Vanilla Web Standards with Type Safety**: Build directly on web standards (ES Modules, Custom Elements v1, and native CSS custom properties) while leveraging TypeScript's type system to enforce contracts at compile time, eliminating an entire class of runtime errors.
- **Decoupling and Separation of Concerns**: Strictly segregate presentation logic (native Web Components), business domain orchestration (Services), and data contract definitions (interfaces / types / DTOs) to ensure maximum testability, modularity, and maintainability.
- **Event-Driven Communication**: Components and services communicate asynchronously via typed event-based observers (`EventEmitter<T>`), avoiding tight coupling and circular dependencies.
- **Smart Minimum Codebases**: Always manage files under line number range of 500 ~ 700 lines at maximum. Decompose large files into cohesive modular architecture.
- **No Implicit Any**: The `noImplicitAny` compiler flag must be enabled. Every value must have a known type at compile time.

---

## Application design system (CSS)

- Use a structured styling system leveraging CSS custom variables, Flexbox, and Grid layouts.
- Styles should reside in external stylesheets named identically to their corresponding Web Component to keep markup and styling concerns logically isolated.
- TypeScript source files use the `.ts` extension but are compiled/bundled to `.js` for browser delivery.

---

## ES modules & import conventions

- Organize imports into distinct, commented sections to highlight library vs. application boundaries.
- Import paths reference the `.js` extension (the compiled output), not `.ts`, to maintain compatibility with standard browser module resolution and TypeScript's `moduleResolution: "bundler"` or `"node16"` modes.
- Use clean relative paths to trace dependency graphs.
- Prefer `import type { ... }` for type-only imports to ensure they are erased at compile time and produce no runtime cost.

```typescript
// Generic Utilities / Core
import { AppService } from "../../generics/services/app-service.js";
import { EventEmitter } from "../../generics/classes/event-emitter.js";

// Type-only imports (erased at compile time)
import type { ServiceConfig, ConnectionResult } from "../../types.js";

// Error Handling
import { AppError } from "../../generics/errors/app-error.js";

// Module Specific Classes
import { ConnectionResult } from "../classes/connection-request.js";
```

---

## Type system conventions

### Interfaces vs. Types

- Use `interface` for object shapes that may be extended or implemented. Interfaces support declaration merging and are preferred for public API contracts.
- Use `type` for unions, intersections, mapped types, conditional types, and computed shapes.
- Never use `class` as a type when an `interface` suffices — classes carry runtime weight.

```typescript
/** Object shapes → interface */
interface UserProfile {
    readonly id: string;
    displayName: string;
    email: string;
    lastLoginAt: Date;
}

/** Unions, discriminated unions, computed types → type */
type ConnectionStatus = "idle" | "connecting" | "connected" | "error";

type Result<T> = { ok: true; data: T } | { ok: false; error: AppError };
```

### Generics

- Use descriptive generic parameter names when their role is not obvious (`TPayload`, `TResponse`), and single-letter names (`T`, `K`, `V`) only in well-known patterns (collections, maps).
- Constrain generics with `extends` to enforce structural compatibility.

```typescript
/** Constrained generic ensures TItem has an id */
interface Repository<TItem extends { id: string }> {
    get(id: string): TItem | undefined;
    save(item: TItem): void;
}
```

### Enums vs. Union literals

- Prefer `const enum` or string literal unions over regular `enum` to avoid emitting extra JavaScript objects.
- Use string literal unions for simple value sets; use `const enum` when numeric mapping or reverse lookup is needed.

```typescript
/** Preferred — zero runtime cost */
type Priority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

/** Acceptable when numeric mapping is needed */
const enum HttpStatus {
    Ok = 200,
    NotFound = 404,
    ServerError = 500,
}
```

### Utility types

- Leverage built-in utility types (`Partial<T>`, `Required<T>`, `Pick<T, K>`, `Omit<T, K>`, `Readonly<T>`, `Record<K, V>`) instead of manually redeclaring shapes.
- Use `Readonly<T>` and `ReadonlyArray<T>` for immutable data contracts.

```typescript
/** Partial for optional update payloads */
type UserUpdate = Partial<Omit<UserProfile, "id">>;

/** Readonly for immutable configuration */
type AppConfig = Readonly<{
    apiHost: string;
    maxRetries: number;
    timeout: number;
}>;
```

---

## Code structure & cohesion

- Maintain a maximum line length of 120 characters and an indentation of 4 spaces.
- **Real Encapsulation**: Hide component internal state and DOM references using native private fields (`#fieldName`). TypeScript's `private` keyword is acceptable for non-Web-Component classes, but `#` is preferred for true runtime encapsulation.
- **Clean Class Member Ordering**: Order members consistently to ensure readability across different codebases:
  1. **Static Getters** (`selector`, `observedAttributes`).
  2. **Private Fields** (`#`, including state variables and DOM element references).
  3. **Public Fields** (such as external event callback registers).
  4. **Constructor**.
  5. **Public Getters & Setters** (reactive data interfaces).
  6. **Private Methods** (internal component behaviors).
  7. **Public API Methods** (interfaces exposed for orchestration).

### Nomenclature conventions

- **Classes**: `PascalCase` (e.g., `UserProfile`, `AppConnectionService`).
- **Interfaces**: `PascalCase` without `I` prefix (e.g., `UserProfile`, not `IUserProfile`).
- **Type Aliases**: `PascalCase` (e.g., `ConnectionStatus`, `Result`).
- **Generic Parameters**: `PascalCase` with `T` prefix for clarity (e.g., `TPayload`, `TResponse`) or single letter (`T`, `K`, `V`) for well-known patterns.
- **Web Component Selectors**: `kebab-case` (e.g., `user-profile-card`).
- **Methods and Variables**: `camelCase` (e.g., `initialize`, `fetchData`).
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_ATTEMPTS`).
- **Private Fields**: `#camelCase` (e.g., `#isInitialized`).
- **Event Callbacks**: Prefix `on` + `Noun` + `PastTenseVerb` (e.g., `onUserLogged`, `onDialogClosed`) to signify observer registrations.
- **File names**: `kebab-case.ts` (e.g., `user-profile.ts`, `app-service.ts`).

---

## General documentation policy (TSDoc)

Document every class, method, function, and parameter using TSDoc. TypeScript types replace many JSDoc `@type` annotations, but documentation of intent, contracts, and non-obvious behaviors remains mandatory.

### File headers

Begin source files with descriptive metadata to quickly communicate their modular responsibility.

```typescript
/**
 * @author  Development Team
 * @version 1.0.0
 *
 * Implements the dynamic rendering engine for UI components,
 * managing lifecycle and style injection.
 */
```

### Logical dividers

Use comment blocks to physically separate private logic from public interfaces in class implementations.

```typescript
// --- SECTION ---

// --- PRIVATE LOGIC ---

/**
 * **NATIVE DOM LOGIC**
 * Lifecycle callback...
 */
```

### Component & service contracts

#### Constructors

- Document configuration parameters and option objects explicitly. TypeScript interfaces replace `@param` destructuring docs for complex option shapes.

#### Reactive properties

- Types are declared inline via TypeScript annotations. Use `readonly` modifier for read-only properties instead of `@readonly` JSDoc.

#### Callbacks & observers

- Define event subscriber properties using typed function signatures rather than `@type {function}` annotations.

```typescript
/**
 * Callback triggered after a successful login.
 */
onLoginSuccess: ((payload: { user: TUser; timestamp: number }) => void) | null = null;
```

#### Documented class design pattern

```typescript
/**
 * @author  Development Team
 * @version 1.2.0
 *
 * AuthManager: Manages global authentication state.
 */
export class AuthManager<TUser> extends EventEmitter {

    /**
     * Current user session token.
     */
    #token: string | null = null;

    /**
     * User profile object with generic type.
     */
    #userProfile: TUser | null = null;

    /**
     * Indicates whether the session has expired by comparing current TS.
     */
    get isExpired(): boolean {
        return this.#checkExpiry();
    }

    /**
     * Callback triggered after a successful login.
     */
    onLoginSuccess: ((payload: { user: TUser; timestamp: number }) => void) | null = null;

    constructor(options: { initialToken: string; profile?: TUser | null }) {
        super();
        this.#token = options.initialToken;
        this.#userProfile = options.profile ?? null;
    }

    /**
     * Validates token expiration using internal JWT decoder.
     */
    #checkExpiry(): boolean {
        if (!this.#token) return true;
        // Internal validation logic...
        return false;
    }

    /**
     * Updates system credentials and notifies observers.
     */
    updateCredentials(newToken: string, userProfile: TUser): void {
        this.#token = newToken;
        this.#userProfile = userProfile;

        this.onLoginSuccess?.({
            user: this.#userProfile,
            timestamp: Date.now(),
        });
    }
}
```

### Function interfaces

#### Natural functions

- Focus documentation on the core algorithm responsibility. Parameter and return types are declared inline via TypeScript annotations.

#### Arrow functions

- Annotate as typed constants using explicit function type signatures.

```typescript
/**
 * Formats a raw numeric value into a currency string.
 */
function formatCurrency(value: number, currency: string = "USD"): string {
    return `${value} ${currency}`;
}

/**
 * Validates if an email string follows the corporate pattern.
 */
const isValidEmail = (email: string): boolean => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
};
```

---

## Architectural components

### Reusable web components

Web components encapsulate presentation. Setters and attribute trackers coordinate state mutations, updating child DOM nodes and firing lifecycle callbacks (`#onInit`, `#onDestroy`).

```typescript
/**
 * @author  Development Team
 * @version 1.0.0
 *
 * Base template for custom Web Component declarations.
 *
 * @element generic-component
 */
export class GenericComponent extends HTMLElement {

    // --- COMPONENT STANDARD VALUES ---

    /**
     * Standard tagname of custom component element.
     */
    static get selector(): string {
        return "generic-component";
    }

    /**
     * List of custom attribute names expected to be changed.
     */
    static get observedAttributes(): string[] {
        return ["status", "title"];
    }

    /**
     * Flag indicating the initialization state of this component.
     */
    #isInitialized: boolean = false;

    // --- PRIVATE FIELDS DECLARATION ---

    /**
     * Internal state representation for status.
     */
    #status: string = "idle";

    /**
     * Reference to internal DOM container.
     */
    #contentBox: HTMLDivElement | null = null;

    // --- PUBLIC FIELDS DECLARATION ---

    /**
     * Callback triggered when status changes.
     */
    onStatusChanged: ((payload: { status: string; oldStatus: string }) => void) | null = null;

    /**
     * Public value accessible outside the class instance.
     */
    publicValue: string = "";

    // --- PUBLIC CONSTRUCTOR ---

    constructor() {
        super();
    }

    // --- PUBLIC VALUES (Getters & Setters) ---

    /**
     * Get current status.
     */
    get status(): string {
        return this.#status;
    }

    /**
     * Set status and update internal elements.
     */
    set status(value: string) {
        if (this.#status === value) {
            return;
        }

        const oldStatus = this.#status;
        this.#status = value;

        this.onStatusChanged?.({ status: value, oldStatus });

        if (this.#isInitialized && this.#contentBox) {
            this.#contentBox.setAttribute("data-status", value);
        }
    }

    // --- PRIVATE IMPLEMENTATION METHODS ---

    /**
     * Renders DOM structure and subscribes to events.
     */
    #onInit(_stateValues: Record<string, unknown> = {}): void {
        this.innerHTML = `
            <div class='example-content-box'>
                <!-- Component DOM children container -->
            </div>
        `;
        this.#contentBox = this.querySelector(".example-content-box");
        if (this.#contentBox) {
            this.#contentBox.onclick = (): void => {
                // Internal interaction logic
            };
        }
    }

    /**
     * Performs cleanup of DOM elements and observers.
     */
    #onDestroy(): void {
        return;
    }

    // --- LIFECYCLE CALLBACKS ---

    connectedCallback(): void {
        this.#onInit();
        this.#isInitialized = true;
    }

    disconnectedCallback(): void {
        this.#onDestroy();
        this.#isInitialized = false;
    }

    attributeChangedCallback(attribName: string, oldValue: string | null, newValue: string | null): void {
        if (oldValue === newValue) {
            return;
        }

        if (attribName === "status") {
            this.status = newValue ?? "idle";
        } else {
            (this as Record<string, unknown>)[attribName] = newValue;
        }
    }
}

customElements.define(GenericComponent.selector, GenericComponent);
```

---

### Decoupled dialog design

Modals must not pollute the global layout. A central coordinator (`AppDialogRegisterService`) handles dialogue lifecycle and dynamic injection, keeping dialog presentation isolated.

#### Dialog coordinator pattern

```typescript
/**
 * @author  Development Team
 * @version 1.0.0
 *
 * AppDialogRegisterService: Orchestrates dialog lifecycle and DOM injection.
 */
import { AppService } from "../../generics/services/app-service.js";

export class AppDialogRegisterService extends AppService {

    /**
     * Map of registered dialogs indexed by their unique ID.
     */
    readonly dialogs: Map<string, HTMLElement> = new Map();

    /**
     * Root DOM element where dialogs are appended.
     */
    #rootView: HTMLElement | null = null;

    constructor() {
        super("DialogRegisterService");
    }

    /**
     * Assigns root view and appends already registered dialogs.
     */
    initialize({ rootView }: { rootView: HTMLElement }): void {
        this.#rootView = rootView;
        this.dialogs.forEach(dialog => this.#rootView!.appendChild(dialog));
        super.ready();
    }

    /**
     * Registers and appends a dialog to root view if initialized.
     */
    register(dialog: HTMLElement): void {
        if (!dialog.id) {
            console.warn("DialogRegister: Attempted to register a dialog without an ID.");
        }
        this.dialogs.set(dialog.id, dialog);
        if (this.#rootView) {
            this.#rootView.appendChild(dialog);
        }
    }
}
```

#### Modal dialog custom element

```typescript
import { ChatDialogRegister } from "../../services/services.js";

/**
 * @author  Development Team
 * @version 1.0.0
 *
 * BaseDialog: Standard implementation template for all app modals.
 * @element base-dialog
 */
export class BaseDialog extends HTMLElement {

    static get selector(): string {
        return "base-dialog";
    }

    #isInitialized: boolean = false;
    #isVisible: boolean = false;

    /**
     * Event callback invoked when the dialog is dismissed.
     */
    onClose: ((data: { target: BaseDialog; timestamp: number }) => void) | null = null;

    /**
     * Event callback invoked when the dialog is shown.
     */
    onShow: (() => void) | null = null;

    constructor() {
        super();
        this.id = "base-modal-instance";
    }

    /**
     * Renders overlay structure.
     */
    #onInit(): void {
        this.innerHTML = `
            <div class="dialog-overlay" style="display: none; position: fixed; inset: 0; z-index: 9999;">
                <div class="dialog-content">
                    <button class="close-btn">Close</button>
                    <div class="dialog-body"><slot></slot></div>
                </div>
            </div>
        `;
        const closeBtn = this.querySelector<HTMLButtonElement>(".close-btn");
        if (closeBtn) {
            closeBtn.onclick = (): void => this.hide();
        }
    }

    /**
     * Shows modal overlay.
     */
    show(): void {
        this.#isVisible = true;
        const overlay = this.querySelector<HTMLElement>(".dialog-overlay");
        if (overlay) {
            overlay.style.display = "flex";
        }
        this.onShow?.();
    }

    /**
     * Hides modal overlay and triggers close callbacks.
     */
    hide(): void {
        this.#isVisible = false;
        const overlay = this.querySelector<HTMLElement>(".dialog-overlay");
        if (overlay) {
            overlay.style.display = "none";
        }
        this.onClose?.({ target: this, timestamp: Date.now() });
    }

    connectedCallback(): void {
        if (!this.#isInitialized) {
            this.#onInit();
            this.#isInitialized = true;
        }
    }
}

customElements.define(BaseDialog.selector, BaseDialog);
```

#### Decoupled orchestration flow

```typescript
/**
 * Example of how a Logic Service manages a dialog.
 */
async function triggerUserAction(): Promise<void> {
    const dialog = new BaseDialog();
    dialogRegisterService.register(dialog);

    dialog.onClose = (data): void => {
        console.log("User closed dialog at:", data.timestamp);
    };

    dialog.show();

    setTimeout((): void => {
        dialog.hide();
    }, 10_000);
}
```

---

## Model-DTO separation layer

We maintain a strict boundary between raw transmission payloads (DTOs) and application domain representations (Models) to protect client business logic from database or API schema changes.

### DTO (Data Transfer Object) contract

#### Option 1: Interface representation (preferred in TypeScript)

```typescript
/**
 * Data structure representing a user as received from Backend API.
 */
interface UserDTO {
    readonly id: string;
    readonly full_name: string;
    readonly email_address: string;
    readonly last_login_ts: number;
}
```

#### Option 2: Immutable class schema (when runtime validation is needed)

```typescript
/**
 * UserDTO: Data structure representing a user as received from Backend API.
 * Use class form only when runtime instanceof checks or validation are required.
 */
export class UserDTO {
    readonly id: string = "";
    readonly full_name: string = "";
    readonly email_address: string = "";
    readonly last_login_ts: number = 0;

    constructor(raw: Record<string, unknown>) {
        this.id = String(raw.id ?? "");
        this.full_name = String(raw.full_name ?? "");
        this.email_address = String(raw.email_address ?? "");
        this.last_login_ts = Number(raw.last_login_ts ?? 0);
    }
}
```

### Domain model pattern

Models process DTO inputs, encapsulate properties in private fields (`#`), and supply formatting logic without leaking database serialization concerns.

```typescript
/**
 * @author  Development Team
 * @version 1.0.0
 *
 * User: Domain entity used within application logic and UI.
 */
export class User {

    /**
     * Internal user unique ID.
     */
    #id: string = "";

    /**
     * Formatted name for display purposes.
     */
    #displayName: string = "";

    /**
     * Processed Date object for the last login event.
     */
    #lastLoginDate: Date | null = null;

    constructor(dto: UserDTO) {
        this.#id = dto.id;
        this.#displayName = this.#capitalize(dto.full_name);
        this.#lastLoginDate = new Date(dto.last_login_ts * 1000);
    }

    get id(): string {
        return this.#id;
    }

    get name(): string {
        return this.#displayName;
    }

    get formattedLastLogin(): string {
        return this.#lastLoginDate?.toLocaleDateString() ?? "";
    }

    set lastLoginDate(timestamp: number) {
        this.#lastLoginDate = new Date(timestamp * 1000);
    }

    /**
     * Private helper to capitalize name tokens.
     */
    #capitalize(str: string): string {
        return str.toLowerCase().replace(/(^|\s)\S/g, l => l.toUpperCase());
    }
}
```

---

## Services and connectors architecture

Business logic is implemented outside visual components by utilizing service classes derived from `AppService`.

```typescript
/**
 * @author  Development Team
 * @version 1.0.0
 *
 * Generic Business Logic Service.
 */
import { AppService } from "../../generics/services/app-service.js";

interface ServiceConfig {
    [key: string]: unknown;
}

/**
 * Service class that handles specific business domain logic.
 */
export class SpecificBusinessService extends AppService {

    /**
     * Internal configuration object.
     */
    #config: ServiceConfig | null = null;

    /**
     * Callback triggered when a logic operation is complete.
     */
    onLogicDone: ((payload: { result: boolean; dataId: string }) => void) | null = null;

    constructor() {
        super("SpecificBusinessService");
        this.detectEventProperties();
    }

    /**
     * Initializes the service with configurations.
     */
    initialize({ config }: { config: ServiceConfig }): void {
        this.#config = config;
        super.ready();
    }

    /**
     * Executes a core business operation.
     */
    async doBusinessLogic(dataId: string): Promise<boolean> {
        this.checksReady();
        const result = true;
        this.emit("onLogicDone", { result, dataId });
        return result;
    }
}
```

### Network connectors

Connectors inherit from `AppConnector` and isolate HTTP calls, translation rules, and URL mappings from services.

```typescript
/**
 * @author  Development Team
 * @version 1.0.0
 *
 * Specialized Connector for Domain Resources.
 */
import { AppConnector } from "../../connection/connectors/app-connector.js";
import type { AppConnectionService, ConnectionResult } from "../../types.js";

interface ResourceDTO {
    data: unknown;
}

/**
 * Connector class that encapsulates API communication for a specific domain.
 */
export class DomainConnector extends AppConnector {

    /**
     * Static private mapping of auth endpoints.
     */
    static #ENDPOINTS: Record<string, string> = {
        loginUser: "/auth/token/login",
        logoutUser: "/auth/token/logout",
        refreshUserToken: "auth/token/refresh",
    };

    /**
     * Initializes the base connector with Host URL and endpoint mappings.
     */
    initialize({ host, connector }: { host: string; connector: AppConnectionService }): void {
        super.initialize({ host, connector, endpoints: DomainConnector.#ENDPOINTS });
    }

    /**
     * Executes a domain resource request.
     */
    async fetchResource({ resourceId }: { resourceId: string }): Promise<{ data?: unknown; error?: unknown }> {
        const requestParameters: Record<string, boolean> = {
            includeDetails: false,
        };

        const url = this.endpointURL("fetchResource", requestParameters);

        const result: ConnectionResult<ResourceDTO> = await this.connector.get({
            url: `${url}/${resourceId}`,
            outputAs: "json",
        });

        if (result.error) {
            return { error: result.error };
        }

        return { data: result.response.data };
    }
}
```

### Service - connector integration

Services call Connector operations rather than executing fetch logic directly, maintaining layer boundaries.

```typescript
/**
 * @author  Development Team
 * @version 1.0.0
 *
 * Coordinates domain state and connector invocation.
 */
import { AppService } from "../../generics/services/app-service.js";

interface DomainItem {
    id: string;
    [key: string]: unknown;
}

/**
 * DomainService - Coordinates state and requests.
 */
export class DomainService extends AppService {

    /**
     * Connector instance for server communication.
     */
    #connector: DomainConnector | null = null;

    /**
     * Internal state containing local collection.
     */
    #items: Map<string, DomainItem> = new Map();

    /**
     * Callback triggered when items change.
     */
    onItemsChanged: ((payload: { items: DomainItem[] }) => void) | null = null;

    constructor() {
        super("DomainService");
        this.detectEventProperties();
    }

    /**
     * Sets domain connector and ready state.
     */
    initialize({ connector }: { connector: DomainConnector }): void {
        this.#connector = connector;
        super.ready();
    }

    /**
     * Fetch resource from API and update service cache.
     */
    async loadItem({ id }: { id: string }): Promise<void> {
        this.checksReady();

        const result = await this.#connector!.fetchResource({ resourceId: id });

        if (result.error) {
            return;
        }

        this.#items.set(id, result.data as DomainItem);
        this.onItemsChanged?.({ items: Array.from(this.#items.values()) });
    }

    /**
     * Get items cache.
     */
    get items(): DomainItem[] {
        return Array.from(this.#items.values());
    }
}
```

### Observer implementation

Services extend from `AppService` and auto-discover public properties prefixed with `on` and set to `null` on instantiation. The service converts these properties into decoupled pub/sub emission hooks. TypeScript enforces event payload shapes via typed callback signatures.

```typescript
/**
 * @author  Development Team
 * @version 1.0.0
 *
 * ChatService handles messages, connections and observers.
 */

interface ChatMessage {
    readonly id: string;
    readonly text: string;
    readonly timestamp: number;
}

export class ChatService extends AppService {

    /**
     * Message log cache.
     */
    #messages: ChatMessage[] = [];

    /**
     * State of network connection.
     */
    #isConnected: boolean = false;

    // --- EVENT PROPERTIES (Detected automatically) ---

    /**
     * Callback triggered on new message events.
     */
    onMessageReceived: ((payload: { message: ChatMessage }) => void) | null = null;

    /**
     * Callback triggered when history is updated.
     */
    onHistoryUpdated: ((payload: { history: ChatMessage[] }) => void) | null = null;

    /**
     * Callback triggered when connection changes.
     */
    onStatusChanged: ((payload: { status: boolean }) => void) | null = null;

    constructor() {
        super("ChatService");
        this.detectEventProperties();
    }

    /**
     * Setup connection state and ready registry.
     */
    initialize(): void {
        this.#isConnected = true;
        super.ready();
        this.onStatusChanged?.({ status: true });
    }

    /**
     * Process message payload, appends to cache and emits updates.
     */
    receiveMessage(rawMessage: { text: string }): void {
        this.checksReady();

        const message: ChatMessage = {
            id: crypto.randomUUID(),
            text: rawMessage.text,
            timestamp: Date.now(),
        };

        this.#messages.push(message);

        this.onMessageReceived?.({ message });
        this.onHistoryUpdated?.({ history: [...this.#messages] });
    }

    /**
     * Get active message array.
     */
    get history(): ReadonlyArray<ChatMessage> {
        return [...this.#messages];
    }
}
```

---

## TypeScript-specific compiler discipline

### Strict mode requirements

The following `tsconfig.json` strict flags must always be enabled:

```json
{
    "compilerOptions": {
        "strict": true,
        "noImplicitAny": true,
        "strictNullChecks": true,
        "strictFunctionTypes": true,
        "strictPropertyInitialization": true,
        "noImplicitReturns": true,
        "noFallthroughCasesInSwitch": true,
        "noUncheckedIndexedAccess": true,
        "exactOptionalPropertyTypes": true
    }
}
```

### Null safety patterns

- Prefer explicit `| null` union over `?` (optional) when a field is always present but may hold null.
- Use optional chaining (`?.`) and nullish coalescing (`??`) instead of manual null checks.
- Never use non-null assertion (`!`) except when the surrounding code guarantees non-null through control flow that TypeScript cannot infer.

### Type assertion discipline

- Prefer `as const` assertions for literal narrowing.
- Avoid `as T` type assertions; use type guards or explicit narrowing instead.
- Use `satisfies` operator to validate object shapes without widening the type.

```typescript
/** satisfies ensures shape compliance without losing literal types */
const CONFIG = {
    apiHost: "https://api.example.com",
    maxRetries: 3,
} satisfies AppConfig;

/** Type guard instead of assertion */
function isUserDTO(value: unknown): value is UserDTO {
    return typeof value === "object" && value !== null && "id" in value && "full_name" in value;
}
```

### Module boundary discipline

- Export only what is needed. Prefer named exports over default exports.
- Re-export aggregated public APIs from barrel files (`index.ts`) only at package boundaries, not within internal module hierarchies.
- Use `export type` for type-only re-exports.

```typescript
// Public API barrel (index.ts)
export { UserService } from "./services/user-service.js";
export { DomainConnector } from "./connectors/domain-connector.js";
export type { UserDTO, UserProfile } from "./types.js";
```
