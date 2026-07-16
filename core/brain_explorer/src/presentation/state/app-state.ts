/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 * @version: 1.0.0
 *
 * Lightweight event-driven presentation state for Brain Explorer.
 */

import type { ActiveCommand, ApiResponse, CallLogRecord, RouteId, RouteTarget, ThemeMode } from "../../application/contracts/api-dtos.ts";

const THEME_STORAGE_KEY = "brain_explorer_theme_v2";

/**
 * AppState coordinates route, theme, and latest CLI result.
 */
export class AppState extends EventTarget {
    #route: RouteId = "dashboard";
    #theme = this.#initialTheme();
    #lastResult: ApiResponse | null = null;
    #pendingQuery = "";
    #pendingQueryOptions: Record<string, string[]> = {};
    #routeTarget: RouteTarget | null = null;
    #callLog: CallLogRecord[] = [];
    #activeCommand: ActiveCommand | null = null;
    #diagnosticsOpen = false;
    #sidebarOpen = false;

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
        this.#emitChange("route");
    }

    /**
     * Route to search with a query captured in the global shell.
     *
     * @param {string} query Query text.
     * @returns {void}
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

    /** Read and clear search options captured by the persistent shell. */
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
