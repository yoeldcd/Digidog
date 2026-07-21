/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 * @version: 1.0.0
 *
 * Lightweight event-driven presentation state for Brain Explorer.
 */

import type { ApiResponse } from "../../../application/shared/contracts/api-response-contract.ts";
import type { ActiveCommand, CallLogRecord, RouteId, RouteTarget, ThemeMode } from "../../../application/shell/contracts/shell-contracts.ts";

const THEME_STORAGE_KEY = "brain_explorer_theme_v2";
const PROJECT_ROUTE_STORAGE_PREFIX = "brain_explorer_project_route_v1:";
const PERSISTABLE_ROUTES: readonly RouteId[] = [
    "dashboard",
    "messages",
    "memory",
    "knowledge",
    "pictures",
    "profiles",
    "logs",
    "backlog",
    "wikis",
    "settings"
];

/**
 * Narrow an untrusted storage value to a route that may be restored on startup.
 * Transient routes such as query results are intentionally rejected even when
 * they are valid runtime `RouteId` values.
 *
 * @param {string | null} value Raw string obtained from project-scoped local storage.
 * @returns {boolean} True when the value belongs to the durable navigation allowlist.
 */
function isPersistableRoute(value: string | null): value is RouteId {
    return value !== null && PERSISTABLE_ROUTES.some(route => route === value);
}

/**
 * Build the isolated local-storage key for one workspace's active view.
 * @param {string} projectPath The raw project path string to be normalized and keyed.
 * @returns {string} A lowercase, trimmed string prefixed with the project route storage constant.
 */
export function projectRouteStorageKey(projectPath: string): string {
    return `${PROJECT_ROUTE_STORAGE_PREFIX}${projectPath.trim().toLocaleLowerCase()}`;
}

/**
 * Restore one stable project route while rejecting stale or transient values.
 * @param {string} projectPath The unique path identifier of the project used to derive the storage key.
 * @returns {RouteId} The persisted RouteId if it exists and is valid; otherwise, the 'dashboard' route identifier.
 */
export function restoreProjectRoute(projectPath: string): RouteId {
    if (!projectPath.trim()) return "dashboard";
    const storedRoute = localStorage.getItem(projectRouteStorageKey(projectPath));
    return isPersistableRoute(storedRoute) ? storedRoute : "dashboard";
}

/**
 * AppState coordinates route, theme, and latest CLI result.
 */
export class AppState extends EventTarget {
    /**
     * Maintains the current active route identifier within the application state.
     *
     * @type {RouteId}
     */
    #route: RouteId;
    /**
     * Stores the absolute or relative filesystem path to the currently active project.
     *
     * @type {string}
     */
    #projectPath: string;
    /**
     * Initializes the private theme state by invoking the internal initial theme provider.
     *
     * @type {ThemeMode}
     */
    #theme = this.#initialTheme();
    /**
     * Stores the most recent API response received by the application state, or null if no request has been completed.
     *
     * @type {ApiResponse<unknown> | null}
     */
    #lastResult: ApiResponse | null = null;
    /**
     * Stores the current search query string that is awaiting execution or processing.
     *
     * @type {string}
     */
    #pendingQuery = "";
    /**
     * Maintains a mapping of query identifiers to their associated pending option strings within the application state.
     *
     * @type {Record<string, string[]>}
     */
    #pendingQueryOptions: Record<string, string[]> = {};
    /**
     * Holds the current navigation destination target or null if no routing operation is pending.
     *
     * @type {RouteTarget | null}
     */
    #routeTarget: RouteTarget | null = null;
    /**
     * Maintains a private collection of call log records within the application state.
     *
     * @type {CallLogRecord[]}
     */
    #callLog: CallLogRecord[] = [];
    /**
     * Tracks the currently executing or selected command within the application state, or null if no command is active.
     *
     * @type {ActiveCommand | null}
     */
    #activeCommand: ActiveCommand | null = null;
    /**
     * Tracks the visibility state of the diagnostics panel within the application shell.
     *
     * @type {boolean}
     */
    #diagnosticsOpen = false;
    /**
     * Tracks the visibility state of the application sidebar.
     *
     * @type {boolean}
     */
    #sidebarOpen = false;

    /**
     * Initializes the application state by sanitizing the provided project path and restoring the corresponding project route.
     * @param {string} projectPath The filesystem path to the project, which is trimmed of leading and trailing whitespace.
     */
    constructor(projectPath = "") {
        super();
        this.#projectPath = projectPath.trim();
        this.#route = restoreProjectRoute(this.#projectPath);
    }

    /**
     * Get active route.
     *
     * @returns {string} Active route id.
     */
    get route(): RouteId {
        return this.#route;
    }

    /**
     * Get active theme.
     *
     * @returns {string} Theme id.
     */
    get theme(): ThemeMode {
        return this.#theme;
    }

    /**
     * Get latest CLI result.
     *
     * @returns {object|null} Last result.
     */
    get lastResult(): ApiResponse | null {
        return this.#lastResult;
    }

    /**
     * Get query text submitted from the global shell search.
     *
     * @returns {string} Pending query text.
     */
    get pendingQuery(): string {
        return this.#pendingQuery;
    }

    /**
     * Get the pending route target metadata.
     *
     * @returns {object|null} Pending route target.
     */
    get routeTarget(): RouteTarget | null {
        return this.#routeTarget ? { ...this.#routeTarget } : null;
    }

    /**
     * Get recent delegated CLI/API calls.
     *
     * @returns {object[]} Recent call records.
     */
    get callLog(): CallLogRecord[] {
        return [...this.#callLog];
    }

    /**
     * Get the currently running CLI/API command.
     *
     * @returns {object|null} Active command metadata.
     */
    get activeCommand(): ActiveCommand | null {
        return this.#activeCommand ? { ...this.#activeCommand } : null;
    }

    /**
     * Get diagnostics drawer state.
     *
     * @returns {boolean} True when diagnostics are visible.
     */
    get diagnosticsOpen(): boolean {
        return this.#diagnosticsOpen;
    }

    /**
     * Get sidebar overlay state.
     *
     * @returns {boolean} True when the expanded sidebar overlay is visible.
     */
    get sidebarOpen(): boolean {
        return this.#sidebarOpen;
    }

    /**
     * Get sidebar collapsed state.
     *
     * @returns {boolean} True when sidebar is icon-only.
     */
    get sidebarCollapsed(): boolean {
        return !this.#sidebarOpen;
    }

    /**
     * Set active route and notify subscribers.
     *
     * @param {string} route Route id.
     * @returns {void}
     */
    setRoute(route: RouteId): void {
        if (this.#route === route) {
            return;
        }
        this.#route = route;
        this.#persistProjectRoute(route);
        this.#emitChange("route");
    }

    /**
     * Navigate to a route with one structured target consumed by the destination view.
     *
     * @param {string} route Route id.
     * @param {object} target Destination-specific payload.
     * @returns {void}
     */
    setRouteTarget(route: RouteId, target: Record<string, unknown> = {}): void {
        this.#routeTarget = {
            route,
            target: { ...target }
        };
        this.#route = route;
        this.#persistProjectRoute(route);
        this.#emitChange("route");
    }

    /**
     * Route to search with a query captured in the global shell.
     *
     * @param {string} query Query text.
     * @returns {void}
     *
     * @param {Record<string, string[]>} options A collection of key-value pairs where each value is an array of strings to be cloned into the state.
     */
    setPendingQuery(query: string, options: Record<string, string[]> = {}): void {
        this.#pendingQuery = query.trim();
        this.#pendingQueryOptions = Object.fromEntries(
            Object.entries(options).map(([key, values]) => [key, [...values]])
        );
        this.#route = "query";
        this.#emitChange("route");
    }

    /**
     * Read and clear the shell query so it runs once.
     *
     * @returns {string} Query text.
     */
    consumePendingQuery(): string {
        const query = this.#pendingQuery;
        this.#pendingQuery = "";
        return query;
    }

    /**
     * Read and clear search options captured by the persistent shell.
     * @returns {Record<string, string[]>} A record mapping query keys to their associated arrays of option values.
     */
    consumePendingQueryOptions(): Record<string, string[]> {
        const options = Object.fromEntries(
            Object.entries(this.#pendingQueryOptions).map(([key, values]) => [key, [...values]])
        );
        this.#pendingQueryOptions = {};
        return options;
    }

    /**
     * Read and clear the route target for one route.
     *
     * @param {string} route Expected route id.
     * @returns {object|null} Destination payload.
     */
    consumeRouteTarget(route: RouteId): Record<string, unknown> | null {
        if (!this.#routeTarget || this.#routeTarget.route !== route) {
            return null;
        }
        const target = { ...this.#routeTarget.target };
        this.#routeTarget = null;
        return target;
    }

    /**
     * Toggle between light and dark themes.
     *
     * @returns {void}
     */
    toggleTheme(): void {
        this.#theme = this.#theme === "dark" ? "light" : "dark";
        localStorage.setItem(THEME_STORAGE_KEY, this.#theme);
        this.#emitChange("theme");
    }

    /**
     * Toggle the CLI diagnostics drawer.
     *
     * @returns {void}
     */
    toggleDiagnostics(): void {
        this.#diagnosticsOpen = !this.#diagnosticsOpen;
        if (this.#diagnosticsOpen && this.#sidebarOpen) {
            this.#sidebarOpen = false;
            this.#emitChange("sidebar");
        }
        this.#emitChange("diagnostics");
    }

    /**
     * Close the CLI diagnostics drawer.
     *
     * @returns {void}
     */
    closeDiagnostics(): void {
        if (!this.#diagnosticsOpen) {
            return;
        }
        this.#diagnosticsOpen = false;
        this.#emitChange("diagnostics");
    }

    /**
     * Toggle the navigation rail.
     *
     * @returns {void}
     */
    toggleSidebar(): void {
        this.#sidebarOpen = !this.#sidebarOpen;
        if (this.#sidebarOpen && this.#diagnosticsOpen) {
            this.#diagnosticsOpen = false;
            this.#emitChange("diagnostics");
        }
        this.#emitChange("sidebar");
    }

    /**
     * Close the expanded sidebar overlay.
     *
     * @returns {void}
     */
    closeSidebar(): void {
        if (!this.#sidebarOpen) {
            return;
        }
        this.#sidebarOpen = false;
        this.#emitChange("sidebar");
    }

    /**
     * Store latest API result.
     *
     * @param {object|null} result API result.
     * @returns {void}
     */
    setLastResult(result: ApiResponse | null): void {
        this.#activeCommand = null;
        this.#lastResult = result;
        if (result) {
            this.#callLog = [{
                id: `${Date.now()}-${this.#callLog.length}`,
                time: new Date().toLocaleTimeString(),
                ok: Boolean(result.ok),
                code: result.code ?? "",
                durationMs: result.durationMs ?? 0,
                command: Array.isArray(result.command) ? result.command.join(" ") : String(result.command || ""),
                data: result.data,
                stdout: result.stdout || "",
                stderr: result.stderr || result.error || ""
            }, ...this.#callLog].slice(0, 20);
        }
        this.dispatchEvent(new CustomEvent("result"));
        this.#emitChange("active-command");
    }

    /**
     * Remove one call log entry.
     *
     * @param {string} id Call id.
     * @returns {void}
     */
    removeCallLogItem(id: string): void {
        const nextLog = this.#callLog.filter(call => call.id !== id);
        if (nextLog.length === this.#callLog.length) {
            return;
        }
        this.#callLog = nextLog;
        this.dispatchEvent(new CustomEvent("result"));
    }

    /**
     * Clear all stored CLI/API call log entries.
     *
     * @returns {void}
     */
    clearCallLog(): void {
        if (!this.#callLog.length) {
            return;
        }
        this.#callLog = [];
        this.dispatchEvent(new CustomEvent("result"));
    }

    /**
     * Mark one command as running in the global state zone.
     *
     * @param {string} command Human-readable command text.
     * @returns {void}
     */
    setActiveCommand(command: string): void {
        this.#activeCommand = {
            command: String(command || "CLI"),
            startedAt: Date.now()
        };
        this.#emitChange("active-command");
    }

    /**
     * Clear the active command indicator.
     *
     * @returns {void}
     */
    clearActiveCommand(): void {
        if (!this.#activeCommand) {
            return;
        }
        this.#activeCommand = null;
        this.#emitChange("active-command");
    }

    /**
     * Add a state-change listener.
     *
     * @param {Function} listener Listener function.
     * @returns {void}
     */
    subscribe(listener: EventListenerOrEventListenerObject): void {
        this.addEventListener("change", listener);
    }

    /**
     * Dispatch specific and generic state changes.
     *
     * @param {string} type Specific event type.
     * @returns {void}
     */
    #emitChange(type: string): void {
        this.dispatchEvent(new CustomEvent(type, { detail: { type } }));
        this.dispatchEvent(new CustomEvent("change", { detail: { type } }));
    }

    /**
     * Persist only stable navigation views under the active project identity.
     * @param {RouteId} route The route identifier to be stored for the current project.
     */
    #persistProjectRoute(route: RouteId): void {
        if (!this.#projectPath || !PERSISTABLE_ROUTES.includes(route)) return;
        localStorage.setItem(projectRouteStorageKey(this.#projectPath), route);
    }

    /**
     * Resolve initial theme from local preference.
     *
     * @returns {string} Theme id.
     */
    #initialTheme(): ThemeMode {
        const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
        if (storedTheme === "light" || storedTheme === "dark") {
            return storedTheme;
        }
        return "light";
    }
}
