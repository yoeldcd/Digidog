# Javascript development practices

## Clean architecture principles

- **Vanilla Web Standards**: Rather than locking code into monolithic frameworks, we build directly on web standards (ES Modules, Custom Elements v1, and native CSS custom properties) to ensure the codebase remains sustainable and free from framework obsolescence.
- **Decoupling and Separation of Concerns**: We strictly segregate presentation logic (native Web Components), business domain orchestration (Services), and data contract definitions (DTOs/Models) to ensure maximum testability, modularity, and maintainability.
- **Event-Driven Communication**: Components and services communicate asynchronously via event-based observers (`EventEmitter`), avoiding tight coupling and circular dependencies.
- **Smart Minimun Codebases**: Allways possible manage files under line number range of 500 ~ 700 lines at maximun. Decompose large files in cohesive modular architecture.

---

## Application design system (CSS)

- Use a structured styling system leveraging CSS custom variables, Flexbox, and Grid layouts.
- Styles should reside in external stylesheets named identically to their corresponding Web Component to keep markup and styling concerns logically isolated.

---

## ES modules & import conventions

- Organize imports into distinct, commented sections to highlight library vs. application boundaries.
- Explicitly declare the `.js` extension for all local modules to remain compatible with standard browser module resolution.
- Use clean relative paths to trace dependency graphs.

```js
// Generic Utilities / Core
import { AppService } from "../../generics/services/app-service.js"
import { EventEmitter } from "../../generics/classes/event-emmiter.js"

// Error Handling
import { AppError } from "../../generics/errors/app-error.js"

// Module Specific Classes
import { ConnectionResult } from "../classes/connection-request.js"
```

---

## Code structure & cohesion

- Maintain a maximum line length of 120 characters and an indentation of 4 spaces.
- **Real Encapsulation**: Hide component internal state and DOM references using native private fields (`#fieldName`).
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
- **Web Component Selectors**: `kebab-case` (e.g., `user-profile-card`).
- **Methods and Variables**: `camelCase` (e.g., `initialize`, `fetchData`).
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_ATTEMPTS`).
- **Private Fields**: `#camelCase` (e.g., `#isInitialized`).
- **Event Callbacks**: Prefix `on` + `Noun` + `PastTenseVerb` (e.g., `onUserLogged`, `onDialogClosed`) to signify observer registrations.

---

## General documentation policy (JSDoc)

Document every class, method, function, and parameter using JSDoc. This serves as an explicit API contract between architectural layers.

### File headers

Begin source files with descriptive metadata to quickly communicate their modular responsibility.

```javascript
/** 
 * @author:  Development Team
 * @version: 1.0.0
 * 
 * Implements the dynamic rendering engine for UI components, 
 * managing lifecycle and style injection.
 */
```

### Logical dividers

Use comment blocks to physically separate private logic from public interfaces in class implementations.

```javascript
// --- SECTION ---

// --- PRIVATE LOGIC ---

/**
 * **NATIVE DOM LOGIC**
 * Lifecycle callback...
 */
```

### Component & service contracts

#### Constructors

- Document configuration parameters and option objects explicitly, outlining nested attributes in case of destructuring.

#### Reactive properties

- Use JSDoc annotations to define property types (`@type`) and access permissions (`@readonly`, `@private`).

#### Callbacks & observers

- Define event subscriber properties clearly, specifying parameter structures to assist caller integration.

```javascript
/** 
 * Callback triggered after a successful login.
 * @type {function({user: T, timestamp: number}): void | null} 
 * @param {object} param0 - Event payload object.
 * @param {T} param0.user - Authenticated user instance.
 * @param {number} param0.timestamp - Operation timestamp.
 */
onLoginSuccess = null
```

#### Documented class design pattern

```javascript
/**
 * @author:  Development Team
 * @version: 1.2.0
 * 
 * AuthManager: Manages global authentication state.
 * @template T - User profile additional data type.
 * @extends EventEmitter
 */
export class AuthManager extends EventEmitter {

    /** 
     * Current user session token.
     * @type {string|null} 
     * @private 
     */
    #token = null

    /** 
     * User profile object with generic type.
     * @type {T|null}
     * @private
     */
    #userProfile = null

    /** 
     * Indicates whether the session has expired by comparing current TS.
     * @readonly
     * @type {boolean} 
     */
    get isExpired() { return this.#checkExpiry() }

    /** 
     * Callback triggered after a successful login.
     * @type {function({user: T, timestamp: number}): void | null} 
     */
    onLoginSuccess = null

    /**
     * @constructor
     * @param {object} param0 - Configuration object.
     * @param {string} param0.initialToken - Recovered session token.
     * @param {T} [param0.profile=null] - Initial profile if available.
     */
    constructor({ initialToken, profile = null }) {
        super()
        this.#token = initialToken
        this.#userProfile = profile
    }

    /**
     * Validates token expiration using internal JWT decoder.
     * @returns {boolean} True if the token is no longer valid.
     * @private
     */
    #checkExpiry() {
        if (!this.#token) return true
        // Internal validation logic...
        return false
    }

    /**
     * Updates system credentials and notifies observers.
     * @param {string} newToken - New token issued by the server.
     * @param {T} userProfile - Authenticated user data.
     * @returns {void}
     */
    updateCredentials(newToken, userProfile) {
        this.#token = newToken
        this.#userProfile = userProfile
        
        // Subscriber notification
        this.onLoginSuccess?.({ 
            user: this.#userProfile, 
            timestamp: Date.now() 
        })
    }
}
```

### Function interfaces

#### Natural functions

- Focus documentation on the core algorithm responsibility, input arguments (`@param`), and outputs (`@returns`).

#### Arrow functions

- Annotate as typed constant values, outlining their functional signatures.

```javascript
/**
 * Formats a raw numeric value into a currency string.
 * 
 * @param {number} value - The numeric value to format.
 * @param {string} [currency='USD'] - The currency code.
 * @returns {string} The formatted currency string.
 */
function formatCurrency(value, currency = 'USD') {
    return `${value} ${currency}`
}

/**
 * Validates if an email string follows the corporate pattern.
 * 
 * @type {function(string): boolean}
 * @param {string} email - Raw input from user.
 * @returns {boolean} True if valid.
 */
const isValidEmail = (email) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}
```

---

## Architectural components

### Reusable web components

Web components encapsulate presentation. Setters and attribute trackers coordinate state mutations, updating child DOM nodes and firing lifecycle callbacks (`#onInit`, `#onDestroy`).

```javascript
/** 
 * @author:  Development Team
 * @version: 1.0.0
 * 
 * Base template for custom Web Component declarations.
 */

/**
 * GenericComponent - A template for all UI components.
 * @element     generic-component
 * @description Custom web component template with reactive properties and DOM handling.
 * @example
 * <generic-component> </generic-component>
 */
export class GenericComponent extends HTMLElement {

    // --- COMPONENT STANDARD VALUES ---
    
    /**
     * Standard tagname of custom component element.
     * @static
     * @type {string}
     */
    static get selector() { return 'generic-component' }

    /**
     * List of custom attribute names expected to be changed.
     * @static
     * @readonly
     * @type {string[]}
     */
    static get observedAttributes() { return ['status', 'title']; }

    /**
     * Flag indicating the initialization state of this component.
     * @type {boolean}
     */
    #isInitialized = false;

    // --- PRIVATE FIELDS DECLARATION ---

    /**
     * Internal state representation for status.
     * @type {string}
     */
    #status = 'idle';

    /**
     * Reference to internal DOM container.
     * @type {HTMLDivElement}
     */
    #contentBox = null;
    
    // --- PUBLIC FIELDS DECLARATION ---
    
    /**
     * Callback triggered when status changes.
     * @type {function}
     * @param {object} param0
     * @param {string} param0.status - New assigned status.
     * @param {string} param0.oldStatus - Previous status value.
     */
    onStatusChanged = null

    /**
     * Public value accessible outside the class instance.
     * @type {string}
     */
    publicValue

    // --- PUBLIC CONSTRUCTOR ---

    /**
     * Constructor for the custom component. DOM initialization is deferred to connect.
     */
    constructor() {
        super();
    }

    // --- PUBLIC VALUES (Getters & Setters) ---

    /**
     * Get current status.
     * @readonly
     * @type {string}
     */
    get status() { return this.#status }

    /**
     * Set status and update internal elements.
     * @param {string} value 
     */
    set status(value) {
        if (this.#status === value) {
            return
        }

        const oldStatus = this.#status
        this.#status = value

        // Emit callback status change
        this.onStatusChanged?.({ status: value, oldStatus })

        if (this.#isInitialized && this.#contentBox) {
            this.#contentBox.setAttribute('data-status', value);
        }
    }

    // --- PRIVATE IMPLEMENTATION METHODS ---

    /** 
     * Renders DOM structure and subscribes to events.
     * @param {Object} [stateValues={}] Initial configuration values.
     */
    #onInit(stateValues = {}) {
        this.innerHTML = `
            <div class='example-content-box'>
                <!-- Component DOM children container -->
            </div>
        `
        this.#contentBox = this.querySelector('.example-content-box')
        this.#contentBox.onclick = () => {
            // Internal interaction logic
        }
    }
    
    /**
     * Performs cleanup of DOM elements and observers.
     */
    #onDestroy() {
        return
    }

    // --- LIFECYCLE CALLBACKS ---

    /**
     * Lifecycle callback invoked when the element is added to the DOM.
     */
    connectedCallback() {
        this.#onInit(this.#stateValues)
        this.#isInitialized = true
    }

    /**
     * Lifecycle callback invoked when the element is removed from the DOM.
     */
    disconnectedCallback() {
        this.#onDestroy()
        this.#isInitialized = false
    }

    /**
     * Callback invoked when a tracked attribute changes.
     * @param {string} attribName - Name of the changed attribute.
     * @param {string} oldValue - Previous attribute value.
     * @param {string} newValue - New attribute value.
     */
    attributeChangedCallback(attribName, oldValue, newValue) {
        if (oldValue === newValue) {
            return
        }

        if (attribName === 'status') {
            this.status = newValue;
        } else {
            this[attribName] = newValue
        }
    }
}

customElements.define(GenericComponent.selector, GenericComponent);
```

---

### Decoupled dialog design

Modals must not pollute the global layout. A central coordinator (`AppDialogRegisterService`) handles dialogue lifecycle and dynamic injection, keeping dialog presentation isolated.

#### Dialog coordinator pattern

```javascript
/**
 * @author:  Angi Ichiva
 * @version: 1.0.0
 * 
 * AppDialogRegisterService: Orchestrates dialog lifecycle and DOM injection.
 * @extends AppService
 */
import { AppService } from "../../generics/services/app-service.js";

export class AppDialogRegisterService extends AppService {

    /**
     * Initializes the dialog service registry.
     */
    constructor() {
        super('DialogRegisterService')

        /** 
         * Map of registered dialogs indexed by their unique ID.
         * @type {Map<string, HTMLElement>} 
         */
        this.dialogs = new Map();

        /** 
         * Root DOM element where dialogs are appended.
         * @type {HTMLElement|null} 
         */
        this.rootView = null
    }
    
    /**
     * Assigns root view and appends already registered dialogs.
     * @param {object} params
     * @param {HTMLElement} params.rootView - Main container of the application.
     */
    initialize({ rootView }) {
        this.rootView = rootView
        this.dialogs.forEach(dialog => this.rootView.appendChild(dialog))
        super.ready()
    }

    /**
     * Registers and appends a dialog to root view if initialized.
     * @param {HTMLElement} dialog - Custom dialog element instance.
     */
    register(dialog) {
        if (!dialog.id) {
            console.warn('DialogRegister: Attempted to register a dialog without an ID.');
        }
        this.dialogs.set(dialog.id, dialog)
        if (this.rootView) {
            this.rootView.appendChild(dialog)
        }
    }
}
```

#### Modal dialog custom element

```javascript
import { ChatDialogRegister } from "../../services/services.js";

/**
 * @author:  Angi Ichiva
 * @version: 1.0.0
 * 
 * BaseDialog: Standard implementation template for all app modals.
 * @element base-dialog
 */
export class BaseDialog extends HTMLElement {
    
    static get selector() { return 'base-dialog' }

    #isInitialized = false
    #isVisible = false

    /** 
     * Event callback invoked when the dialog is dismissed.
     * @type {function|null} 
     */
    onClose = null

    /** 
     * Event callback invoked when the dialog is showed.
     * @type {function|null} 
     */
    onShow = null

    constructor() {
        super()
        this.id = 'base-modal-instance'
    }

    /**
     * Renders overlay structure.
     * @private
     */
    #onInit() {
        this.innerHTML = `
            <div class="dialog-overlay" style="display: none; position: fixed; inset: 0; z-index: 9999;">
                <div class="dialog-content">
                    <button class="close-btn">Close</button>
                    <div class="dialog-body"><slot></slot></div>
                </div>
            </div>
        `
        this.querySelector('.close-btn').onclick = () => this.hide()
    }

    /**
     * Shows modal overlay.
     */
    show() {
        this.#isVisible = true
        this.querySelector('.dialog-overlay').style.display = 'flex'
        this.onShow?.()
    }

    /**
     * Hides modal overlay and triggers close callbacks.
     */
    hide() {
        this.#isVisible = false
        this.querySelector('.dialog-overlay').style.display = 'none'
        this.onClose?.({ target: this, timestamp: Date.now() })
    }

    connectedCallback() {
        if (!this.#isInitialized) {
            this.#onInit()
            this.#isInitialized = true
        }
    }
}

customElements.define(BaseDialog.selector, BaseDialog)
```

#### Decoupled orchestration flow

```javascript
/**
 * Example of how a Logic Service manages a dialog.
 */
async function triggerUserAction() {
    const dialog = new BaseDialog();
    dialogRegisterService.register(dialog);
    
    dialog.onClose = (data) => {
        console.log('User closed dialog at:', data.timestamp);
    };

    dialog.show();
    
    setTimeout(() => {
        dialog.hide()
    }, 10000)
}
```

---

## Model-DTO separation layer

We maintain a strict boundary between raw transmission payloads (DTOs) and application domain representations (Models) to protect client business logic from database or API schema changes.

### DTO (Data Transfer Object) contract

#### Option 1: Typedef representation

```javascript
/**
 * Data structure representing a user as received from Backend API.
 * 
 * @typedef {object} UserDTO
 * @property {string} id             Unique server identifier.
 * @property {string} full_name      Combined name string.
 * @property {number} last_login_ts  Unix timestamp of last login.
 */
```

#### Option 2: Immutable public field schema

```javascript
/**
 * @author: Development Team
 * UserDTO: Data structure representing a user as received from Backend API.
 */
export class UserDTO {

    /** 
     * Unique server identifier for the user.
     * @type {string} 
     */
    id = ""

    /** 
     * Complete name string provided by the database.
     * @type {string} 
     */
    full_name = ""

    /** 
     * Registered user email address.
     * @type {string} 
     */
    email_address = ""

    /** 
     * Unix timestamp representing the last time the user logged in.
     * @type {number} 
     */
    last_login_ts = 0
}
```

### Domain model pattern

Models process DTO inputs, encapsulate properties in private fields (`#`), and supply formatting logic without leaking database serialization concerns.

```javascript
/**
 * @author:  Development Team
 * @version: 1.0.0
 * 
 * User: Domain entity used within application logic and UI.
 */
export class User {

    /** 
     * Internal user unique ID.
     * @type {string} 
     * @private
     */
    #id = ""

    /** 
     * Formatted name for display purposes.
     * @type {string} 
     * @private
     */
    #displayName = ""

    /** 
     * Processed Date object for the last login event.
     * @type {Date} 
     * @private
     */
    #lastLoginDate = null

    /**
     * @constructor
     * @param {UserDTO} dto - The raw data object from the connector.
     */
    constructor(dto) {
        this.#id = dto.id
        this.#displayName = this.#capitalize(dto.full_name)
        this.#lastLoginDate = new Date(dto.last_login_ts * 1000)
    }

    /**
     * Get user ID.
     * @readonly
     * @returns {string} 
     */
    get id() { return this.#id }

    /** 
     * Get the display name.
     * @readonly
     * @returns {string} 
     */
    get name() { return this.#displayName }

    /** 
     * Returns a human-readable string of the last login date.
     * @returns {string} Formatted date (e.g., "12/22/2025").
     */
    get formattedLastLogin() {
        return this.#lastLoginDate.toLocaleDateString()
    }

    /**
     * Update user last login Date.
     * @param {number} lastLoginDate - Unix timestamp in seconds.
     */
    set lastLogingDate(lastLoginDate) {
        this.#lastLoginDate = new Date(lastLoginDate * 1000)
    }
    
    /**
     * Private helper to capitalize name tokens.
     * @param {string} str - Raw input.
     * @returns {string} Capitalized output.
     * @private
     */
    #capitalize(str) {
        return str.toLowerCase().replace(/(^|\s)\S/g, l => l.toUpperCase())
    }
}
```

---

## Services and connectors architecture

Business logic is implemented outside visual components by utilizing service classes derived from `AppService`.

```javascript
/** 
 * @author:  Development Team
 * @version: 1.0.0
 * 
 * Generic Business Logic Service.
 */
import { AppService } from "../../generics/services/app-service.js";

/**
 * Service class that handles specific business domain logic.
 * @extends AppService
 */
export class SpecificBusinessService extends AppService {
    
    /**
     * Internal configuration object.
     * @type {object}
     * @private
     */
    #config = null;

    /**
     * Callback triggered when a logic operation is complete.
     * @type {function}
     * @param {Object} result - Operation result status.
     * @param {String} dataId - hexadecimal UUID string.
     */
    onLogicDone = null

    constructor() {
        super('SpecificBusinessService');
        this.detectEventProperties();
    }

    /**
     * Initializes the service with configurations.
     * @param {object} param0
     * @param {object} param0.config - Global configurations dictionary.
     */
    initialize({ config }) {
        this.#config = config;
        super.ready(); 
    }

    /**
     * Executes a core business operation.
     * @param {string} dataId - Identifier for the target data.
     * @returns {Promise<boolean>}
     */
    async doBusinessLogic(dataId) {
        this.checksReady();
        const result = true;
        this.emit('onLogicDone', { result, dataId });
        return result;
    }
}
```

### Network connectors

Connectors inherit from `AppConnector` and isolate HTTP calls, translation rules, and URL mappings from services.

```javascript
/** 
 * @author:  Development Team
 * @version: 1.0.0
 * 
 * Specialized Connector for Domain Resources.
 */
import { AppConnector } from "../../connection/connectors/app-connector.js";

/**
 * Connector class that encapsulates API communication for a specific domain.
 * @extends AppConnector
 */
export class DomainConnector extends AppConnector {

    /**
     * Static private mapping of auth endpoints.
     * @type {object}
     * @private
     */
    static #ENDPOINTS = {
        loginUser: "/auth/token/login",
        logoutUser: "/auth/token/logout",
        refreshUserToken: "auth/token/refresh",
    };

    /**
     * Initializes the base connector with Host URL and endpoint mappings.
     * @param {object} param0
     * @param {string} param0.host - Target API host URL.
     * @param {AppConnectionService} param0.connector - Shared request dispatcher.
     */
    initialize({ host, connector }) {
        super.initialize({ host, connector, endpoints: DomainConnector.#ENDPOINTS });
    }

    /**
     * Executes a domain resource request.
     * @param {object} param0
     * @param {string} param0.resourceId - Target UUID.
     * @returns {Promise<object>} Response data mapping.
     */
    async fetchResource({ resourceId }) {
        const requestParameters = {
            "includeDetails": false 
        }

        const url = this.endpointURL('fetchResource', requestParameters); 

        /** @type {ConnectionResult<ResourceDTO>} */
        const result = await this.connector.get({
            url: `${url}/${resourceId}`,
            outputAs: "json"
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

```javascript
/** 
 * @author:  Angi Ichiva
 * @version: 1.0.0
 * 
 * Coordinates domain state and connector invocation.
 */
import { AppService } from "../../generics/services/app-service.js";

/**
 * DomainService - Coordinates state and requests.
 * @extends AppService
 */
export class DomainService extends AppService {

    /** 
     * Connector instance for server communication.
     * @type {DomainConnector}
     * @private
     */
    #connector = null;

    /**
     * Internal state containing local collection.
     * @type {Map<string, object>}
     * @private
     */
    #items = new Map();

    /**
     * Callback triggered when items changes.
     * @type {function}
     * @param {object} param0
     * @param {Array} param0.items - List of current active items.
     */
    onItemsChanged = null;

    constructor() {
        super('DomainService');
        this.detectEventProperties();
    }

    /**
     * Sets domain connector and ready state.
     * @param {object} param0
     * @param {DomainConnector} param0.connector - Initialized connector instance.
     */
    initialize({ connector }) {
        this.#connector = connector;
        super.ready(); 
    }

    /**
     * Fetch resource from API and update service cache.
     * @param {object} param0
     * @param {string} param0.id - Item ID.
     */
    async loadItem({ id }) {
        this.checksReady();

        const result = await this.#connector.fetchResource({ resourceId: id });

        if (result.error) {
            return;
        }

        this.#items.set(id, result.data);
        this.onItemsChanged?.({ items: Array.from(this.#items.values()) });
    }

    /**
     * Get items cache.
     * @readonly
     * @returns {Array} Active items.
     */
    get items() {
        return Array.from(this.#items.values());
    }
}
```

### Observer implementation

Services extend from `AppService` and auto-discover public properties prefixed with `on` and set to `null` on instantiation. The service converts these properties into decoupled pub/sub emission hooks.

```javascript
/**
 * @author:  Development Team
 * @version: 1.0.0
 * 
 * ChatService handles messages, connections and observers.
 * @extends AppService
 */
export class ChatService extends AppService {

    /**
     * Message log cache.
     * @type {Array<object>}
     * @private
     */
    #messages = []

    /**
     * State of network connection.
     * @type {boolean}
     * @private
     */
    #isConnected = false

    // --- EVENT PROPERTIES (Detected automatically) ---

    /**
     * Callback triggered on new message events.
     * @type {function}
     * @param {object} param0
     * @param {object} param0.message - Incoming message record.
     */
    onMessageReceived = null

    /**
     * Callback triggered when history is updated.
     * @type {function}
     * @param {object} param0
     * @param {Array} param0.history - Complete message array.
     */
    onHistoryUpdated = null

    /**
     * Callback triggered when connection changes.
     * @type {function}
     * @param {object} param0
     * @param {boolean} param0.status - Active connection status flag.
     */
    onStatusChanged = null

    constructor() {
        super('ChatService')
        this.detectEventProperties()
    }

    /**
     * Setup connection state and ready registry.
     */
    initialize() {
        this.#isConnected = true
        super.ready()
        this.onStatusChanged({ status: true })
    }

    /**
     * Process message payload, appends to cache and emits updates.
     * @param {object} rawMessage - Message payload object.
     */
    receiveMessage(rawMessage) {
        this.checksReady()

        const message = {
            id: crypto.randomUUID(),
            text: rawMessage.text,
            timestamp: Date.now()
        }

        this.#messages.push(message)

        this.onMessageReceived({ message })
        this.onHistoryUpdated({ history: [...this.#messages] })
    }

    /**
     * Get active message array.
     * @readonly
     * @type {Array}
     */
    get history() {
        return [...this.#messages]
    }
}
```
