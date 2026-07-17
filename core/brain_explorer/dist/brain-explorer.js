"use strict";
const __brainExplorerModule0=(()=>{let cache;return()=>{if(cache)return cache;
const { BrainApiClient } = __brainExplorerModule1();
const { AppState } = __brainExplorerModule2();
const { BrainExplorerApp } = __brainExplorerModule3();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */



/**
 * Bootstrap the Brain Explorer browser application.
 *
 * @returns {void}
 */
function bootstrapBrainExplorer() {
    const app = document.querySelector(BrainExplorerApp.selector);
    if (!app) {
        return;
    }
    const api = new BrainApiClient();
    const activePath = localStorage.getItem("active_project_path");
    if (activePath) {
        api.setWorkspaceRootOverride(activePath);
    }
    app.context = {
        api,
        state: new AppState(activePath || "")
    };
}
bootstrapBrainExplorer();

cache=(()=>{return {};})();return cache;};})();
const __brainExplorerModule1=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */
/**
 * BrainApiClient isolates every browser request to the local explorer server.
 */
class BrainApiClient extends EventTarget {
    #cache = new Map();
    #inFlight = new Map();
    #defaultTtlMs = 45_000;
    #workspaceRootOverride = null;
    setWorkspaceRootOverride(path) {
        this.#workspaceRootOverride = path;
        this.#cache.clear();
        this.#inFlight.clear();
    }
    /**
     * Execute a JSON API request.
     *
     * @param {string} path API path and query.
     * @param {object} options Fetch options.
     * @returns {Promise<object>} Parsed response payload.
     */
    async request(path, options = {}) {
        const method = String(options.method || "GET").toUpperCase();
        const cacheable = method === "GET";
        const cacheKey = `${method} ${path}`;
        const now = Date.now();
        const ttlMs = Number(options.cacheTtlMs || this.#defaultTtlMs);
        if (cacheable && !options.forceRefresh) {
            const cached = this.#cache.get(cacheKey);
            if (cached && cached.expiresAt > now) {
                return { ...cached.payload, cached: true };
            }
            const pending = this.#inFlight.get(cacheKey);
            if (pending) {
                const payload = await pending;
                return { ...payload, cached: true };
            }
        }
        const fetchOptions = { ...options };
        delete fetchOptions.forceRefresh;
        delete fetchOptions.cacheTtlMs;
        delete fetchOptions.commandLabel;
        delete fetchOptions.silent;
        const commandLabel = options.commandLabel || `${method} ${path}`;
        if (!options.silent) {
            this.dispatchEvent(new CustomEvent("request-start", { detail: { command: commandLabel } }));
        }
        const requestPromise = this.#fetchJson(path, fetchOptions);
        let completedPayload = null;
        try {
            if (cacheable) {
                this.#inFlight.set(cacheKey, requestPromise);
            }
            const payload = await requestPromise;
            completedPayload = payload;
            if (cacheable) {
                this.#cache.set(cacheKey, { payload, expiresAt: Date.now() + ttlMs });
            }
            else {
                this.#cache.clear();
            }
            return payload;
        }
        finally {
            if (cacheable) {
                this.#inFlight.delete(cacheKey);
            }
            if (!options.silent) {
                this.dispatchEvent(new CustomEvent("request-end", {
                    detail: { command: commandLabel, method, payload: completedPayload }
                }));
            }
        }
    }
    /**
     * Execute the actual browser request.
     *
     * @param {string} path API path and query.
     * @param {object} options Fetch options.
     * @returns {Promise<object>} Parsed response payload.
     */
    async #fetchJson(path, options = {}) {
        const headers = {
            "Content-Type": "application/json"
        };
        if (options.headers) {
            Object.assign(headers, options.headers);
        }
        if (this.#workspaceRootOverride) {
            headers["X-Workspace-Root"] = this.#workspaceRootOverride;
        }
        const response = await fetch(path, {
            ...options,
            headers
        });
        const payload = await response.json();
        if (!response.ok) {
            const error = isRecord(payload) && typeof payload.error === "string" ? payload.error : response.statusText;
            return {
                ok: false,
                code: response.status,
                command: [],
                data: null,
                stdout: "",
                stderr: "",
                durationMs: 0,
                error
            };
        }
        return isApiResponse(payload) ? payload : {
            ok: false,
            code: response.status,
            command: [],
            data: null,
            stdout: "",
            stderr: "",
            durationMs: 0,
            error: "Invalid API response."
        };
    }
    /**
     * Return whether a response points to an older explorer server without a route.
     *
     * @param {object} payload API payload.
     * @returns {boolean} True when the route is missing.
     */
    #isMissingRoute(payload) {
        return Boolean(!payload?.ok && String(payload?.error || payload?.stderr || "").includes("Unknown API route"));
    }
    /**
     * Read server health.
     *
     * @returns {Promise<ApiResponse<HealthStatus>>} Health payload.
     */
    health(options = {}) {
        return this.request("/api/health", options);
    }
    /**
     * Read registered projects.
     *
     * @returns {Promise<ApiResponse<ProjectsResponse>>} Projects list payload.
     */
    getProjects(options = {}) {
        return this.request("/api/projects", options);
    }
    /**
     * Read detected subproject wikis.
     *
     * @returns {Promise<ApiResponse<WikisResponse>>} Wikis list.
     */
    getWikis(options = {}) {
        return this.request("/api/wikis", options);
    }
    /** Read persisted paid-voice messages. */
    getVoiceMessages(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/voice/messages${query ? `?${query}` : ""}`, options);
    }
    /** Poll the daemon-confirmed avatar playback identity. */
    getVoiceStatus(options = {}) {
        return this.request("/api/voice/status", options);
    }
    /** Replay one retained daemon message without regenerating speech. */
    replayVoiceMessage(name) {
        return this.request("/api/voice/replay", {
            method: "POST",
            body: JSON.stringify({ name }),
            forceRefresh: true
        });
    }
    /** Stop active daemon replay without removing retained audio. */
    pauseVoiceReplay() {
        return this.request("/api/voice/pause", { method: "POST", forceRefresh: true });
    }
    /** Generate and immediately play audio for one persisted message. */
    synthesizeVoiceMessage(messageId) {
        return this.request("/api/voice/synthesize", {
            method: "POST",
            body: JSON.stringify({ messageId }),
            forceRefresh: true
        });
    }
    /** Build the safe media URL for one stored voice message. */
    voiceMessageUrl(name) {
        return `/api/voice/messages/${encodeURIComponent(name)}`;
    }
    /**
     * Read live workspace context through get-context.
     *
     * @returns {Promise<object>} Context payload.
     */
    context(options = {}) {
        return this.request("/api/context", options);
    }
    /**
     * Execute a read-only CLI prompt command.
     *
     * @param {string} command Prompt command.
     * @returns {Promise<object>} CLI result payload.
     */
    runCli(command) {
        return this.request("/api/cli", {
            method: "POST",
            commandLabel: command,
            body: JSON.stringify({ command })
        });
    }
    /**
     * Read memory tree paths.
     *
     * @returns {Promise<object>} CLI result payload.
     */
    memoryTree(options = {}) {
        return this.request("/api/memory/tree", options);
    }
    /**
     * Read one memory entry.
     *
     * @param {string} path Dot-notated memory path.
     * @returns {Promise<object>} CLI result payload.
     */
    memoryEntry(path, options = {}) {
        return this.request(`/api/memory/entry?path=${encodeURIComponent(path)}`, options);
    }
    /**
     * Save one memory entry.
     *
     * @param {string} path Dot-notated memory path.
     * @param {string} content Markdown content.
     * @returns {Promise<object>} CLI result payload.
     */
    saveMemoryEntry(path, content) {
        return this.request("/api/memory/entry", {
            method: "POST",
            body: JSON.stringify({ path, content })
        });
    }
    /**
     * Create a memory domain.
     *
     * @param {string} domain Dot-notated domain.
     * @returns {Promise<object>} CLI result payload.
     */
    createMemoryDomain(domain) {
        return this.request("/api/memory/domain", {
            method: "POST",
            body: JSON.stringify({ domain })
        });
    }
    /**
     * Delete one memory domain.
     *
     * @param {string} domain Dot-notated domain.
     * @returns {Promise<object>} CLI result payload.
     */
    deleteMemoryDomain(domain) {
        return this.request(`/api/memory/domain?domain=${encodeURIComponent(domain)}&confirm=${encodeURIComponent(domain)}`, { method: "DELETE" });
    }
    /**
     * Delete one memory entry.
     *
     * @param {string} path Dot-notated memory path.
     * @returns {Promise<object>} CLI result payload.
     */
    deleteMemoryEntry(path) {
        return this.request(`/api/memory/entry?path=${encodeURIComponent(path)}`, { method: "DELETE" });
    }
    /**
     * Read knowledge graph status.
     *
     * @param {string} scope Knowledge scope.
     * @returns {Promise<object>} CLI result payload.
     */
    knowledgeStatus(scope = "all", options = {}) {
        return this.request(`/api/knowledge/status?scope=${encodeURIComponent(scope)}`, options);
    }
    /**
     * Show graph records.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    knowledgeShow(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/knowledge/show?${query}`, options);
    }
    /**
     * Search the graph.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    knowledgeQuery(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/knowledge/query?${query}`, options);
    }
    /**
     * Review knowledge deltas.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    knowledgeDeltas(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/knowledge/deltas?${query}`, options);
    }
    /**
     * Execute global brain query.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    globalQuery(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/query?${query}`, options);
    }
    /** Read the canonical picture registry. */
    pictures(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/pictures${query ? `?${query}` : ""}`, options);
    }
    /** Persist one manual picture description. */
    describePicture(pictureId, description) {
        return this.request("/api/pictures/description", {
            method: "POST",
            body: JSON.stringify({ pictureId, description }),
            forceRefresh: true
        });
    }
    /** Build the opaque registry-backed URL for one picture. */
    pictureUrl(pictureId) {
        return `/api/pictures/file?id=${encodeURIComponent(pictureId)}`;
    }
    /**
     * Read profile list.
     *
     * @returns {Promise<object>} CLI result payload.
     */
    profiles(options = {}) {
        return this.request("/api/profiles", options);
    }
    /**
     * Read one profile.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    async profileRead(params = {}, options = {}) {
        const query = toQueryString(params);
        const result = await this.request(`/api/profiles/read?${query}`, options);
        if (this.#isMissingRoute(result) && params.name) {
            return this.runCli(`read-profile ${params.name} --json`);
        }
        return result;
    }
    /**
     * Read logs.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    logs(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/logs?${query}`, options);
    }
    /**
     * Read the log domain index.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    logIndex(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/logs/index?${query}`, options);
    }
    /**
     * Read the workspace backlog tree.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    backlog(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/backlog?${query}`, options);
    }
    /**
     * Mutate one backlog task through an allowlisted API action.
     *
     * @param {object} payload Backlog mutation payload.
     * @returns {Promise<object>} CLI result payload.
     */
    updateBacklog(payload) {
        return this.request("/api/backlog/task", {
            method: "POST",
            body: JSON.stringify(payload)
        });
    }
}
function isRecord(value) {
    return typeof value === "object" && value !== null;
}
function isApiResponse(value) {
    return isRecord(value) && typeof value.ok === "boolean";
}
function toQueryString(params) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
            query.set(key, String(value));
        }
    });
    return query.toString();
}

cache=(()=>{return { BrainApiClient: BrainApiClient };})();return cache;};})();
const __brainExplorerModule2=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 * @version: 1.0.0
 *
 * Lightweight event-driven presentation state for Brain Explorer.
 */
const THEME_STORAGE_KEY = "brain_explorer_theme_v2";
const PROJECT_ROUTE_STORAGE_PREFIX = "brain_explorer_project_route_v1:";
const PERSISTABLE_ROUTES = [
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
/** Build the isolated local-storage key for one workspace's active view. */
function projectRouteStorageKey(projectPath) {
    return `${PROJECT_ROUTE_STORAGE_PREFIX}${projectPath.trim().toLocaleLowerCase()}`;
}
/** Restore one stable project route while rejecting stale or transient values. */
function restoreProjectRoute(projectPath) {
    if (!projectPath.trim())
        return "dashboard";
    const storedRoute = localStorage.getItem(projectRouteStorageKey(projectPath));
    return storedRoute && PERSISTABLE_ROUTES.includes(storedRoute) ? storedRoute : "dashboard";
}
/**
 * AppState coordinates route, theme, and latest CLI result.
 */
class AppState extends EventTarget {
    #route;
    #projectPath;
    #theme = this.#initialTheme();
    #lastResult = null;
    #pendingQuery = "";
    #pendingQueryOptions = {};
    #routeTarget = null;
    #callLog = [];
    #activeCommand = null;
    #diagnosticsOpen = false;
    #sidebarOpen = false;
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
    get route() {
        return this.#route;
    }
    /**
     * Get active theme.
     *
     * @returns {string} Theme id.
     */
    get theme() {
        return this.#theme;
    }
    /**
     * Get latest CLI result.
     *
     * @returns {object|null} Last result.
     */
    get lastResult() {
        return this.#lastResult;
    }
    /**
     * Get query text submitted from the global shell search.
     *
     * @returns {string} Pending query text.
     */
    get pendingQuery() {
        return this.#pendingQuery;
    }
    /**
     * Get the pending route target metadata.
     *
     * @returns {object|null} Pending route target.
     */
    get routeTarget() {
        return this.#routeTarget ? { ...this.#routeTarget } : null;
    }
    /**
     * Get recent delegated CLI/API calls.
     *
     * @returns {object[]} Recent call records.
     */
    get callLog() {
        return [...this.#callLog];
    }
    /**
     * Get the currently running CLI/API command.
     *
     * @returns {object|null} Active command metadata.
     */
    get activeCommand() {
        return this.#activeCommand ? { ...this.#activeCommand } : null;
    }
    /**
     * Get diagnostics drawer state.
     *
     * @returns {boolean} True when diagnostics are visible.
     */
    get diagnosticsOpen() {
        return this.#diagnosticsOpen;
    }
    /**
     * Get sidebar overlay state.
     *
     * @returns {boolean} True when the expanded sidebar overlay is visible.
     */
    get sidebarOpen() {
        return this.#sidebarOpen;
    }
    /**
     * Get sidebar collapsed state.
     *
     * @returns {boolean} True when sidebar is icon-only.
     */
    get sidebarCollapsed() {
        return !this.#sidebarOpen;
    }
    /**
     * Set active route and notify subscribers.
     *
     * @param {string} route Route id.
     * @returns {void}
     */
    setRoute(route) {
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
    setRouteTarget(route, target = {}) {
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
     */
    setPendingQuery(query, options = {}) {
        this.#pendingQuery = query.trim();
        this.#pendingQueryOptions = Object.fromEntries(Object.entries(options).map(([key, values]) => [key, [...values]]));
        this.#route = "query";
        this.#emitChange("route");
    }
    /**
     * Read and clear the shell query so it runs once.
     *
     * @returns {string} Query text.
     */
    consumePendingQuery() {
        const query = this.#pendingQuery;
        this.#pendingQuery = "";
        return query;
    }
    /** Read and clear search options captured by the persistent shell. */
    consumePendingQueryOptions() {
        const options = Object.fromEntries(Object.entries(this.#pendingQueryOptions).map(([key, values]) => [key, [...values]]));
        this.#pendingQueryOptions = {};
        return options;
    }
    /**
     * Read and clear the route target for one route.
     *
     * @param {string} route Expected route id.
     * @returns {object|null} Destination payload.
     */
    consumeRouteTarget(route) {
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
    toggleTheme() {
        this.#theme = this.#theme === "dark" ? "light" : "dark";
        localStorage.setItem(THEME_STORAGE_KEY, this.#theme);
        this.#emitChange("theme");
    }
    /**
     * Toggle the CLI diagnostics drawer.
     *
     * @returns {void}
     */
    toggleDiagnostics() {
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
    closeDiagnostics() {
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
    toggleSidebar() {
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
    closeSidebar() {
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
    setLastResult(result) {
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
    removeCallLogItem(id) {
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
    clearCallLog() {
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
    setActiveCommand(command) {
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
    clearActiveCommand() {
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
    subscribe(listener) {
        this.addEventListener("change", listener);
    }
    /**
     * Dispatch specific and generic state changes.
     *
     * @param {string} type Specific event type.
     * @returns {void}
     */
    #emitChange(type) {
        this.dispatchEvent(new CustomEvent(type, { detail: { type } }));
        this.dispatchEvent(new CustomEvent("change", { detail: { type } }));
    }
    /** Persist only stable navigation views under the active project identity. */
    #persistProjectRoute(route) {
        if (!this.#projectPath || !PERSISTABLE_ROUTES.includes(route))
            return;
        localStorage.setItem(projectRouteStorageKey(this.#projectPath), route);
    }
    /**
     * Resolve initial theme from local preference.
     *
     * @returns {string} Theme id.
     */
    #initialTheme() {
        const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
        if (storedTheme === "light" || storedTheme === "dark") {
            return storedTheme;
        }
        return "light";
    }
}

cache=(()=>{return { projectRouteStorageKey: projectRouteStorageKey, restoreProjectRoute: restoreProjectRoute, AppState: AppState };})();return cache;};})();
const __brainExplorerModule3=(()=>{let cache;return()=>{if(cache)return cache;
const { DashboardView } = __brainExplorerModule4();
const { MemoryView } = __brainExplorerModule5();
const { KnowledgeView } = __brainExplorerModule6();
const { QueryView } = __brainExplorerModule7();
const { ProfilesView } = __brainExplorerModule8();
const { LogsView } = __brainExplorerModule9();
const { BacklogView } = __brainExplorerModule10();
const { SettingsView } = __brainExplorerModule11();
const { WikisView } = __brainExplorerModule12();
const { MessagesView } = __brainExplorerModule13();
const { PicturesView } = __brainExplorerModule14();
const { codeBlock, escapeHtml } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
const { notificationText } = __brainExplorerModule17();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */














const ROUTES = [
    { id: "dashboard", label: "Proyecto", icon: "home", element: DashboardView.selector },
    { id: "messages", label: "Mensajes", icon: "messageCircle", element: MessagesView.selector },
    { id: "memory", label: "Memoria", icon: "database", element: MemoryView.selector },
    { id: "knowledge", label: "Conocimiento", icon: "graph", element: KnowledgeView.selector },
    { id: "pictures", label: "Pictures", icon: "camera", element: PicturesView.selector },
    { id: "query", label: "Resultados", icon: "search", element: QueryView.selector, nav: false },
    { id: "profiles", label: "Perfiles", icon: "users", element: ProfilesView.selector },
    { id: "logs", label: "Logs", icon: "document", element: LogsView.selector },
    { id: "backlog", label: "Backlog", icon: "checkSquare", element: BacklogView.selector },
    { id: "wikis", label: "Wikis", icon: "book", element: WikisView.selector },
    { id: "settings", label: "Ajustes", icon: "settings", element: SettingsView.selector }
];
/**
 * BrainExplorerApp composes the persistent shell around route-level Web Components.
 */
class BrainExplorerApp extends HTMLElement {
    static get selector() {
        return "brain-explorer-app";
    }
    #api = null;
    #state = null;
    #activeRouteId = "";
    #stateListenersBound = false;
    #apiListenersBound = false;
    #activeRequestCount = 0;
    #openCallIds = new Set();
    #latestVoiceAudio = null;
    #notificationTimers = new Map();
    #handleGlobalKeyDown = (event) => {
        if (event.ctrlKey && event.altKey && event.key?.toLowerCase() === "s") {
            event.preventDefault();
            const searchInput = this.querySelector("[data-role='global-shell-search']");
            searchInput?.focus();
            searchInput?.select();
        }
    };
    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#bindStateEvents();
        this.#bindApiEvents();
        this.#renderShell();
    }
    /**
     * Render shell when attached.
     *
     * @returns {void}
     */
    connectedCallback() {
        if (this.#state && this.#api && !this.querySelector(".app-shell")) {
            this.#renderShell();
        }
        window.addEventListener("keydown", this.#handleGlobalKeyDown);
    }
    /**
     * Remove keyboard shortcut listener when detached.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        window.removeEventListener("keydown", this.#handleGlobalKeyDown);
        this.#notificationTimers.forEach(record => window.clearTimeout(record.timer));
        this.#notificationTimers.clear();
    }
    /**
     * Render persistent shell markup once per context assignment.
     *
     * @returns {void}
     */
    #renderShell() {
        if (!this.#state || !this.#api) {
            return;
        }
        document.documentElement.dataset.theme = this.#state.theme;
        this.innerHTML = `
            <div class="app-shell ${this.#state.sidebarOpen ? "is-sidebar-open" : "is-sidebar-collapsed"}">
                <header class="top-bar">
                    <div class="brand-lockup" style="display: flex; align-items: center; gap: 6px;">
                        <span class="brain-mark">${icon("pulse")}</span>
                        <span style="font-size: 16px; font-weight: 600; color: var(--text-normal); display: inline-flex; align-items: center;">
                            Brain ~&nbsp;
                            <details class="action-menu project-selector-menu" style="position: relative; display: inline-block;">
                                <summary style="cursor: pointer; list-style: none; display: inline-flex; align-items: center; gap: 4px; padding-right: 14px; background-image: url(&quot;data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%23888888' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>&quot;); background-repeat: no-repeat; background-position: right center; background-size: 10px; outline: none; user-select: none;" data-role="project-selector-summary">
                                    Cargando...
                                </summary>
                                <div class="action-menu-panel project-selector-panel" data-role="project-selector-options">
                                </div>
                            </details>
                        </span>
                    </div>
                    <div class="global-search-cluster">
                        <div class="global-search">
                            ${icon("search")}
                            <input data-role="global-shell-search" placeholder="Buscar en todo el conocimiento...">
                            <kbd>Ctrl + Alt + S</kbd>
                        </div>
                        <details class="action-menu search-options-menu">
                            <summary title="Fuentes y modos de búsqueda" aria-label="Fuentes y modos de búsqueda">${icon("sliders")}</summary>
                            <div class="action-menu-panel search-options-panel">
                                <fieldset>
                                    <legend>Fuentes</legend>
                                    <label><input type="checkbox" name="search-source" value="memory" checked>Memoria</label>
                                    <label><input type="checkbox" name="search-source" value="knowledge" checked>Conocimiento</label>
                                    <label><input type="checkbox" name="search-source" value="messages" checked>Mensajes</label>
                                    <label><input type="checkbox" name="search-source" value="pictures" checked>Pictures</label>
                                </fieldset>
                                <fieldset>
                                    <legend>Modos</legend>
                                    <label><input type="checkbox" name="search-mechanism" value="graph" checked>Grafo</label>
                                    <label><input type="checkbox" name="search-mechanism" value="vector" checked>Vectorial</label>
                                    <label><input type="checkbox" name="search-mechanism" value="text" checked>Texto</label>
                                </fieldset>
                            </div>
                        </details>
                    </div>
                    <div class="header-actions">
                        <button class="voice-header-toggle" data-action="play-latest-voice" title="Reproducir último mensaje" aria-label="Reproducir último mensaje">${icon("volume")}</button>
                        <button class="theme-toggle" data-action="toggle-theme" title="Cambiar tema"></button>
                    </div>
                </header>

                <aside class="side-nav">
                    <button class="sidebar-collapse" data-action="toggle-sidebar"></button>
                    <nav data-role="side-nav-list" aria-label="Navegacion principal">
                        ${this.#renderNav()}
                    </nav>
                </aside>

                <main class="route-host" data-route-host></main>

                <footer class="status-footer">
                    <span>(c) 2026 Brain Explorer</span>
                    <span>v1.1.0</span>
                    <span data-role="footer-route"></span>
                    <span data-role="footer-call"></span>
                    <button data-action="toggle-diagnostics" class="footer-link">${icon("terminal")}CLI</button>
                    <span>Sistema local <i class="live-dot"></i></span>
                </footer>

                <div data-command-overlay-host></div>
                <div data-diagnostics-host></div>
                <section class="notification-stack" data-notification-stack aria-live="polite" aria-label="Notificaciones"></section>
            </div>
        `;
        this.#bindShellEvents();
        this.#syncTheme();
        this.#syncSidebar();
        this.#mountRoute();
        this.#syncFooter();
        this.#renderDiagnosticsPanel();
        this.#renderActiveCommand();
        this.#api.health().then(res => {
            if (res && res.workspaceRoot) {
                // Fetch and populate registered projects dropdown
                const api = this.#api;
                if (api) {
                    api.getProjects().then((projectsRes) => {
                        const summaryEl = this.querySelector("[data-role='project-selector-summary']");
                        const optionsEl = this.querySelector("[data-role='project-selector-options']");
                        if (summaryEl && optionsEl && projectsRes && projectsRes.projects) {
                            optionsEl.innerHTML = "";
                            let activePath = localStorage.getItem("active_project_path");
                            const defaultPath = res.workspaceRoot;
                            const allProjects = [...projectsRes.projects];
                            if (defaultPath && !allProjects.some(p => p.path === defaultPath)) {
                                allProjects.unshift({
                                    name: defaultPath,
                                    path: defaultPath
                                });
                            }
                            allProjects.sort((a, b) => a.path.localeCompare(b.path));
                            if (!activePath && defaultPath) {
                                activePath = defaultPath;
                                localStorage.setItem("active_project_path", defaultPath);
                            }
                            if (activePath) {
                                summaryEl.textContent = activePath;
                                api.setWorkspaceRootOverride(activePath);
                            }
                            else {
                                summaryEl.textContent = defaultPath;
                            }
                            allProjects.forEach(proj => {
                                const btn = document.createElement("button");
                                btn.type = "button";
                                btn.textContent = proj.path;
                                if (proj.path === activePath) {
                                    btn.classList.add("active");
                                }
                                btn.addEventListener("click", () => {
                                    localStorage.setItem("active_project_path", proj.path);
                                    api.setWorkspaceRootOverride(proj.path);
                                    window.location.reload();
                                });
                                optionsEl.appendChild(btn);
                            });
                        }
                    }).catch((err) => console.error("Error fetching projects for selector:", err));
                }
            }
        }).catch(err => console.error("Error fetching health for project indicator:", err));
    }
    /**
     * Bind application state events to focused shell updates.
     *
     * @returns {void}
     */
    #bindStateEvents() {
        if (this.#stateListenersBound || !this.#state) {
            return;
        }
        this.#state.addEventListener("route", () => {
            this.#mountRoute();
            this.#syncFooter();
        });
        this.#state.addEventListener("theme", () => this.#syncTheme());
        this.#state.addEventListener("sidebar", () => this.#syncSidebar());
        this.#state.addEventListener("diagnostics", () => this.#renderDiagnosticsPanel());
        this.#state.addEventListener("active-command", () => {
            this.#syncFooter();
            this.#renderActiveCommand();
            this.#renderDiagnosticsLog();
        });
        this.#state.addEventListener("result", () => {
            this.#syncFooter();
            this.#renderActiveCommand();
            this.#renderDiagnosticsLog();
        });
        this.#stateListenersBound = true;
    }
    /**
     * Bind API request lifecycle events to the global state zone.
     *
     * @returns {void}
     */
    #bindApiEvents() {
        if (this.#apiListenersBound || !this.#api || !this.#state) {
            return;
        }
        this.#api.addEventListener("request-start", event => {
            this.#activeRequestCount += 1;
            this.#state.setActiveCommand(event.detail?.command || "CLI");
        });
        this.#api.addEventListener("request-end", event => {
            this.#activeRequestCount = Math.max(0, this.#activeRequestCount - 1);
            if (this.#activeRequestCount === 0) {
                this.#state.clearActiveCommand();
            }
            const payload = event.detail?.payload;
            const method = event.detail?.method || "GET";
            const feedback = payload
                ? notificationText(payload, method, event.detail?.command || "")
                : null;
            if (payload && !payload.ok) {
                this.#pushNotification({
                    tone: "error",
                    title: "No se pudo completar",
                    message: feedback?.message
                });
            }
            else if (payload && method !== "GET") {
                this.#pushNotification({
                    tone: "success",
                    title: feedback?.title,
                    message: feedback?.message
                });
            }
        });
        this.#apiListenersBound = true;
    }
    /** Add one timed, hover-pausable notification pill to the global stack. */
    #pushNotification({ tone = "info", title = "Mensaje", message = "" }) {
        const stack = this.querySelector("[data-notification-stack]");
        if (!stack)
            return;
        const id = `notification-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const lifetime = tone === "error" ? 10_000 : 7_000;
        const element = document.createElement("article");
        element.className = `push-notification is-${tone}`;
        element.dataset.notificationId = id;
        element.style.setProperty("--notification-life", `${lifetime}ms`);
        element.innerHTML = `
            <button class="notification-copy" type="button" aria-expanded="false">
                <strong>${escapeHtml(title)}</strong>
                <span>${escapeHtml(String(message || title))}</span>
            </button>
            <button class="notification-close" type="button" aria-label="Cerrar notificación"><i></i></button>
        `;
        stack.append(element);
        const record = { timer: 0, remaining: lifetime, startedAt: performance.now() };
        const dismiss = () => {
            window.clearTimeout(record.timer);
            this.#notificationTimers.delete(id);
            element.classList.add("is-leaving");
            window.setTimeout(() => element.remove(), 180);
        };
        const resume = () => {
            record.startedAt = performance.now();
            record.timer = window.setTimeout(dismiss, record.remaining);
            element.classList.remove("is-paused");
        };
        const pause = () => {
            window.clearTimeout(record.timer);
            record.remaining = Math.max(0, record.remaining - (performance.now() - record.startedAt));
            element.classList.add("is-paused");
        };
        element.addEventListener("mouseenter", pause);
        element.addEventListener("mouseleave", resume);
        element.querySelector(".notification-close")?.addEventListener("click", dismiss);
        element.querySelector(".notification-copy")?.addEventListener("click", event => {
            const expanded = element.classList.toggle("is-expanded");
            event.currentTarget.setAttribute("aria-expanded", String(expanded));
        });
        this.#notificationTimers.set(id, record);
        resume();
    }
    /**
     * Bind persistent DOM events using delegation so route views are not remounted.
     *
     * @returns {void}
     */
    #bindShellEvents() {
        const shell = this.querySelector(".app-shell");
        if (!shell) {
            return;
        }
        shell.addEventListener("click", event => this.#handleShellClick(event));
        shell.addEventListener("submit", event => {
            if (event.target instanceof Element && event.target.matches("[data-role='cli-prompter']")) {
                event.preventDefault();
                this.#runCliPrompt();
            }
        });
        this.querySelector("[data-role='global-shell-search']")?.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                const value = event.target.value.trim();
                if (value) {
                    this.querySelector(".search-options-menu")?.removeAttribute("open");
                    this.#state.setPendingQuery(value, this.#selectedSearchOptions());
                    return;
                }
                this.#state.setRoute("query");
            }
        });
    }
    /** Collect non-exclusive search source and mechanism selections. */
    #selectedSearchOptions() {
        const selected = name => Array.from(this.querySelectorAll(`input[name='${name}']:checked`))
            .map(input => input.value);
        return { sources: selected("search-source"), mechanisms: selected("search-mechanism") };
    }
    /**
     * Handle shell-level click actions.
     *
     * @param {Event} event DOM click event.
     * @returns {void}
     */
    #handleShellClick(event) {
        const target = event.target instanceof Element ? event.target : null;
        this.#handleDropdownMenus(target);
        if (this.#state.sidebarOpen && target && !target.closest(".side-nav")) {
            this.#state.closeSidebar();
        }
        const routeButton = target?.closest("[data-route]");
        if (routeButton) {
            this.#state.setRoute(routeButton.getAttribute("data-route"));
            this.#state.closeSidebar();
            return;
        }
        const actionButton = target?.closest("[data-action]");
        const action = actionButton?.getAttribute("data-action") || "";
        if (action === "toggle-theme") {
            this.#state.toggleTheme();
        }
        if (action === "play-latest-voice") {
            this.#playLatestVoice();
        }
        if (action === "toggle-diagnostics") {
            this.#state.toggleDiagnostics();
        }
        if (action === "close-diagnostics") {
            this.#state.closeDiagnostics();
        }
        if (action === "clear-cli-log") {
            this.#openCallIds.clear();
            this.#state.clearCallLog();
        }
        if (action === "delete-cli-call") {
            const callId = actionButton?.getAttribute("data-call-id") || "";
            this.#openCallIds.delete(callId);
            this.#state.removeCallLogItem(callId);
        }
        if (action === "toggle-sidebar") {
            this.#state.toggleSidebar();
        }
        if (action === "run-cli-command") {
            this.#runCliPrompt();
        }
    }
    /** Replay the latest persisted voice without requesting new synthesis. */
    #playLatestVoice() {
        this.#latestVoiceAudio?.pause();
        this.#latestVoiceAudio = new Audio(`/api/voice/latest?fresh=${Date.now()}`);
        void this.#latestVoiceAudio.play().catch(() => {
            this.#latestVoiceAudio = null;
        });
    }
    /**
     * Keep native details dropdowns mutually dismissible across route components.
     *
     * @param {Element|null} target Click target.
     * @returns {void}
     */
    #handleDropdownMenus(target) {
        const activeMenu = target?.closest("details.action-menu") || null;
        this.querySelectorAll("details.action-menu[open]").forEach(menu => {
            if (menu !== activeMenu) {
                menu.removeAttribute("open");
            }
        });
        if (target?.closest(".action-menu-panel button")) {
            queueMicrotask(() => activeMenu?.removeAttribute("open"));
        }
    }
    /**
     * Render navigation buttons.
     *
     * @returns {string} Navigation HTML.
     */
    #renderNav() {
        return ROUTES.filter(route => route.nav !== false).map(route => `
            <button class="side-nav-item ${route.id === this.#state.route ? "is-active" : ""}" data-route="${route.id}" data-tooltip="${escapeHtml(route.label)}" aria-label="${escapeHtml(route.label)}">
                ${icon(route.icon)}
                <span class="nav-label">${escapeHtml(route.label)}</span>
            </button>
        `).join("");
    }
    /**
     * Mount the active route component only when the route changes.
     *
     * @returns {void}
     */
    #mountRoute() {
        const route = ROUTES.find(item => item.id === this.#state.route) || ROUTES[0];
        const host = this.querySelector("[data-route-host]");
        const refreshPendingQuery = route.id === "query" && Boolean(this.#state.pendingQuery);
        if (!host || (this.#activeRouteId === route.id && !refreshPendingQuery)) {
            this.#syncActiveNav();
            return;
        }
        const element = document.createElement(route.element);
        element.context = { api: this.#api, state: this.#state };
        host.setAttribute("aria-label", route.label);
        host.replaceChildren(element);
        this.#activeRouteId = route.id;
        this.#syncActiveNav();
    }
    /**
     * Update navigation active styles without rebuilding the route.
     *
     * @returns {void}
     */
    #syncActiveNav() {
        this.querySelectorAll("[data-route]").forEach(button => {
            button.classList.toggle("is-active", button.getAttribute("data-route") === this.#state.route);
        });
    }
    /**
     * Update theme button and document theme.
     *
     * @returns {void}
     */
    #syncTheme() {
        document.documentElement.dataset.theme = this.#state.theme;
        const button = this.querySelector("[data-action='toggle-theme']");
        if (!button) {
            return;
        }
        button.innerHTML = `
            ${icon(this.#state.theme === "dark" ? "sun" : "moon")}
        `;
    }
    /**
     * Update overlay sidebar width, label, and icon without touching routes.
     *
     * @returns {void}
     */
    #syncSidebar() {
        const shell = this.querySelector(".app-shell");
        const button = this.querySelector("[data-action='toggle-sidebar']");
        shell?.classList.toggle("is-sidebar-open", this.#state.sidebarOpen);
        shell?.classList.toggle("is-sidebar-collapsed", !this.#state.sidebarOpen);
        if (!button) {
            return;
        }
        const label = this.#state.sidebarOpen ? "Contraer" : "Expandir";
        const iconName = this.#state.sidebarOpen ? "collapseLeft" : "expandRight";
        button.title = `${label} navegacion`;
        button.dataset.tooltip = `${label} navegacion`;
        button.setAttribute("aria-label", `${label} navegacion`);
        button.innerHTML = `${icon(iconName)}<span class="nav-label">${label}</span>`;
    }
    /**
     * Keep route and CLI technical state in the persistent footer.
     *
     * @returns {void}
     */
    #syncFooter() {
        const route = ROUTES.find(item => item.id === this.#state.route) || ROUTES[0];
        const routeLabel = this.querySelector("[data-role='footer-route']");
        const callLabel = this.querySelector("[data-role='footer-call']");
        const lastCall = this.#state.callLog[0];
        if (routeLabel) {
            routeLabel.textContent = route.label;
        }
        if (!callLabel) {
            return;
        }
        if (!lastCall) {
            callLabel.textContent = "CLI sin llamadas";
            return;
        }
        const command = lastCall.command.split(" ").slice(-2).join(" ") || "API";
        const state = lastCall.ok ? "OK" : "Error";
        callLabel.textContent = `${command} - ${lastCall.durationMs} ms - ${state}`;
    }
    /**
     * Execute the command typed in the bottom CLI prompter.
     *
     * @returns {Promise<void>} Resolves after command execution.
     */
    async #runCliPrompt() {
        const input = this.querySelector("[data-role='cli-prompt']");
        const command = input?.value?.trim() || "";
        if (!command) {
            return;
        }
        this.#state.setActiveCommand(command);
        const result = await this.#api.runCli(command);
        this.#state.setLastResult(result);
    }
    /**
     * Render diagnostics drawer in its isolated overlay host.
     *
     * @returns {void}
     */
    #renderDiagnosticsPanel() {
        const host = this.querySelector("[data-diagnostics-host]");
        if (!host) {
            return;
        }
        host.innerHTML = this.#state.diagnosticsOpen ? this.#renderDiagnosticsDrawer() : "";
        this.#bindCallLogItems();
    }
    /**
     * Render diagnostics drawer.
     *
     * @returns {string} HTML.
     */
    #renderDiagnosticsDrawer() {
        return `
            <aside class="diagnostics-drawer" aria-label="Consola CLI">
                <div class="diagnostics-head">
                    <div>
                        <strong>Llamadas CLI</strong>
                        <span>Historial, comando activo y prompter allowlisted</span>
                    </div>
                    <div class="diagnostics-actions">
                        <button data-action="clear-cli-log" class="ghost-action">${icon("trash")}Vaciar</button>
                        <button data-action="close-diagnostics" class="icon-action cli-close-action" title="Cerrar consola" aria-label="Cerrar consola">${icon("close")}</button>
                    </div>
                </div>
                ${this.#renderDiagnosticsActiveCommand()}
                <div data-role="diagnostics-log" class="diagnostics-log">
                    ${this.#renderCallLog()}
                </div>
                <form class="cli-prompter" data-role="cli-prompter">
                    <label>
                        <span>Comando</span>
                        <input data-role="cli-prompt" list="cli-command-suggestions" placeholder="get-context">
                    </label>
                    <datalist id="cli-command-suggestions">
                        ${this.#renderPromptSuggestions()}
                    </datalist>
                    <button type="button" data-action="run-cli-command" class="primary-action">${icon("terminal")}Ejecutar</button>
                </form>
            </aside>
        `;
    }
    /**
     * Render command suggestions for the allowlisted CLI prompt.
     *
     * @returns {string} Datalist option HTML.
     */
    #renderPromptSuggestions() {
        return [
            "get-context --json",
            "memory-structure --json",
            "list-profiles --json",
            "knowledge-status --scope all --json",
            "knowledge-show --scope global --entities --json",
            "show-backlog",
            "log-index",
            "vectorstore-status --json"
        ].map(command => `<option value="${escapeHtml(command)}"></option>`).join("");
    }
    /**
     * Render or clear the currently running command overlay.
     *
     * @returns {void}
     */
    #renderActiveCommand() {
        const host = this.querySelector("[data-command-overlay-host]");
        if (!host) {
            return;
        }
        const activeCommand = this.#state.activeCommand;
        host.innerHTML = activeCommand ? `
            <div class="command-blocking-overlay" role="status" aria-live="polite">
                <span class="loading-spinner"></span>
                <strong>Ejecutando comando</strong>
                <code>${escapeHtml(activeCommand.command)}</code>
            </div>
        ` : "";
    }
    /**
     * Update diagnostics without remounting the active route.
     *
     * @returns {void}
     */
    #renderDiagnosticsLog() {
        const activeHost = this.querySelector("[data-role='diagnostics-active-command']");
        if (activeHost) {
            activeHost.outerHTML = this.#renderDiagnosticsActiveCommand();
        }
        const host = this.querySelector("[data-role='diagnostics-log']");
        if (host) {
            host.innerHTML = this.#renderCallLog();
            this.#bindCallLogItems();
        }
    }
    /**
     * Render the currently running command inside the diagnostics console.
     *
     * @returns {string} HTML.
     */
    #renderDiagnosticsActiveCommand() {
        const activeCommand = this.#state.activeCommand;
        if (!activeCommand) {
            return `<div data-role="diagnostics-active-command" class="diagnostics-active-strip is-empty">Sin comando en curso.</div>`;
        }
        return `
            <div data-role="diagnostics-active-command" class="diagnostics-active-strip">
                <span class="loading-spinner small-spinner"></span>
                <strong>En curso</strong>
                <code>${escapeHtml(activeCommand.command)}</code>
            </div>
        `;
    }
    /**
     * Render recent calls.
     *
     * @returns {string} HTML.
     */
    #renderCallLog() {
        const calls = this.#state.callLog;
        if (!calls.length) {
            return `<p class="empty-state">Sin llamadas registradas todavia.</p>`;
        }
        return calls.map(call => `
            <details class="call-log-item" data-call-id="${escapeHtml(call.id)}" ${this.#openCallIds.has(call.id) ? "open" : ""}>
                <summary>
                    <span class="${call.ok ? "status-dot ok" : "status-dot error"}"></span>
                    <strong>${escapeHtml(call.command.split(" ").slice(-3).join(" ") || "API call")}</strong>
                    <time>${escapeHtml(call.time)} - ${escapeHtml(String(call.durationMs))} ms</time>
                    <button type="button" data-action="delete-cli-call" data-call-id="${escapeHtml(call.id)}" class="icon-action call-delete" title="Borrar llamada">${icon("trash")}</button>
                </summary>
                ${codeBlock({
            ok: call.ok,
            code: call.code,
            command: call.command,
            data: call.data,
            stdout: call.stdout,
            stderr: call.stderr
        }, "json")}
            </details>
        `).join("");
    }
    /**
     * Bind explicit expansion behavior for CLI call log items.
     *
     * @returns {void}
     */
    #bindCallLogItems() {
        this.querySelectorAll(".call-log-item").forEach(details => {
            const summary = details.querySelector("summary");
            summary?.addEventListener("click", event => {
                if (event.target instanceof Element && event.target.closest("button")) {
                    return;
                }
                event.preventDefault();
                details.open = !details.open;
                this.#syncCallLogItem(details);
            });
        });
    }
    /**
     * Persist one call log item expansion state.
     *
     * @param {Element} details Details element.
     * @returns {void}
     */
    #syncCallLogItem(details) {
        const id = details.getAttribute("data-call-id") || "";
        if (!id) {
            return;
        }
        if ("open" in details && details.open) {
            this.#openCallIds.add(id);
            return;
        }
        this.#openCallIds.delete(id);
    }
}
customElements.define(BrainExplorerApp.selector, BrainExplorerApp);

cache=(()=>{return { BrainExplorerApp: BrainExplorerApp };})();return cache;};})();
const __brainExplorerModule4=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */


/**
 * DashboardView renders the `get-context --json` items as the Explorer entry point.
 */
class DashboardView extends HTMLElement {
    static get selector() {
        return "brain-dashboard-view";
    }
    #api = null;
    #state = null;
    #contextSections = [];
    #loading = false;
    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#load();
    }
    /**
     * Initialize the component.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
    }
    /**
     * Load live context from the explorer API.
     *
     * @param {boolean} forceRefresh Whether to bypass the browser API cache.
     * @returns {Promise<void>} Resolves after rendering.
     */
    async #load(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        this.#loading = true;
        this.#render();
        const context = await this.#api.context({ forceRefresh });
        this.#contextSections = Array.isArray(context.data?.sections) ? context.data.sections : [];
        this.#state?.setLastResult(context);
        this.#loading = false;
        this.#render();
    }
    /**
     * Render dashboard markup.
     *
     * @returns {void}
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface dashboard-view context-home">
                <main class="context-document scroll-area">
                    ${this.#loading ? this.#loadingState() : this.#renderContextDocument()}
                </main>
            </section>
        `;
        this.querySelector("[data-action='refresh-dashboard']")?.addEventListener("click", () => this.#load(true));
        this.querySelectorAll("[data-context-route]").forEach(button => {
            button.addEventListener("click", () => this.#openContextCard(button));
        });
    }
    /**
     * Open a context card destination.
     *
     * @param {Element} button Clicked card button.
     * @returns {void}
     */
    #openContextCard(button) {
        const route = button.getAttribute("data-context-route") || "dashboard";
        const target = this.#decodeTarget(button.getAttribute("data-context-target") || "");
        this.#state?.setRouteTarget?.(route, target);
    }
    /**
     * Render the live context as a collapsible document outline.
     *
     * @returns {string} HTML.
     */
    #renderContextDocument() {
        if (!this.#contextSections.length) {
            return `
                <div class="knowledge-empty-state">
                    ${icon("document")}
                    <h2>Contexto no cargado</h2>
                    <p>Actualiza para leer el contexto vivo del workspace.</p>
                </div>
            `;
        }
        const entryCount = this.#contextSections.reduce((total, section) => total + Math.max(1, Array.isArray(section.items) ? section.items.length : 0), 0);
        return `
            <article class="context-document-root context-outline">
                <div class="context-document-actions">
                    <span>${escapeHtml(String(entryCount))} enlaces</span>
                    <button data-action="refresh-dashboard" class="icon-action compact-action" title="Actualizar contexto" aria-label="Actualizar contexto">${icon("refresh")}</button>
                </div>
                <div class="context-tree-document">
                    ${this.#contextSections.map(section => this.#renderContextSection(section)).join("")}
                </div>
            </article>
        `;
    }
    /**
     * Render one context document section.
     *
     * @param {object} section Context section.
     * @returns {string} HTML.
     */
    #renderContextSection(section) {
        const items = Array.isArray(section.items) ? section.items : [];
        const entries = items.length ? items.map(item => this.#itemEntry(section, item)) : [this.#sectionEntry(section)].filter(Boolean);
        if (!entries.length) {
            return "";
        }
        const kind = section.kind || "item";
        return `
            <details class="context-tree-section context-kind-${escapeHtml(kind)}" open>
                <summary class="context-tree-summary">
                    <span class="context-summary-caret">${icon("chevronRight")}</span>
                    <span class="metric-icon">${icon(this.#sectionIcon(section))}</span>
                    <span class="context-summary-copy">
                        <strong>${escapeHtml(section.title || this.#sectionTitle(section))}</strong>
                        <small>${escapeHtml(section.summary || this.#sectionSummary(section, entries.length))}</small>
                    </span>
                    <span class="context-summary-count">${escapeHtml(String(entries.length))}</span>
                </summary>
                <div class="context-section-body">
                    ${this.#renderSectionBody(kind, entries)}
                </div>
            </details>
        `;
    }
    /**
     * Render section entries using type-specific document shapes.
     *
     * @param {string} kind Section kind.
     * @param {object[]} entries Normalized entries.
     * @returns {string} HTML.
     */
    #renderSectionBody(kind, entries) {
        if (kind === "logs") {
            const chronologicalEntries = this.#sortLogsNewestFirst(entries);
            return `
                <nav class="context-log-links" aria-label="Entradas recientes de logs">
                    ${chronologicalEntries.map(entry => this.#renderContextLine(entry, "context-link-line")).join("")}
                </nav>
            `;
        }
        if (kind === "diary") {
            return `
                <ol class="context-timeline">
                    ${entries.map(entry => `<li>${this.#renderContextLine(entry, "context-timeline-entry")}</li>`).join("")}
                </ol>
            `;
        }
        if (kind === "profiles") {
            return `
                <nav class="context-profile-links" aria-label="Perfiles disponibles">
                    ${entries.map(entry => this.#renderContextLine(entry, "context-profile-link")).join("")}
                </nav>
            `;
        }
        if (kind === "workspace" || kind === "system" || kind === "notice") {
            return entries.map(entry => this.#renderFactRow(entry)).join("");
        }
        return entries.map(entry => this.#renderContextLine(entry, "context-link-line")).join("");
    }
    /**
     * Return log entries in reverse chronological order without mutating the
     * domain-oriented sequence received from the CLI facade.
     *
     * Entries with equal or missing timestamps retain their original order.
     *
     * @param {object[]} entries Normalized log entries.
     * @returns {object[]} Newest entries first.
     */
    #sortLogsNewestFirst(entries) {
        return entries
            .map((entry, index) => ({
            entry,
            index,
            timestamp: this.#logTimestamp(entry)
        }))
            .sort((left, right) => {
            if (left.timestamp === right.timestamp) {
                return left.index - right.index;
            }
            return right.timestamp - left.timestamp;
        })
            .map(({ entry }) => entry);
    }
    /**
     * Parse the CLI display date and time into a sortable UTC value.
     *
     * @param {object} entry Normalized log entry.
     * @returns {number} UTC timestamp or negative infinity when unavailable.
     */
    #logTimestamp(entry) {
        const dateMatch = String(entry.date || "").match(/^(\d{2})-(\d{2})-(\d{4})$/);
        const timeMatch = String(entry.time || "00:00").match(/^(\d{2}):(\d{2})(?::(\d{2}))?$/);
        if (!dateMatch || !timeMatch) {
            return Number.NEGATIVE_INFINITY;
        }
        const [, day, month, year] = dateMatch;
        const [, hour, minute, second = "0"] = timeMatch;
        return Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second));
    }
    /**
     * Render one navigable document line.
     *
     * @param {object} entry Normalized entry.
     * @param {string} className Row class.
     * @returns {string} HTML.
     */
    #renderContextLine(entry, className) {
        const routeAttributes = entry.route
            ? `data-context-route="${escapeHtml(entry.route)}" data-context-target="${escapeHtml(this.#encodeTarget(entry.target || {}))}"`
            : "";
        const tag = entry.route ? "button" : "article";
        return `
            <${tag} class="${className} context-kind-${escapeHtml(entry.kind)}" ${routeAttributes}>
                <span class="metric-icon">${icon(entry.icon)}</span>
                <strong>${escapeHtml(entry.label)}</strong>
            </${tag}>
        `;
    }
    /**
     * Render a non-list fact row.
     *
     * @param {object} entry Normalized entry.
     * @returns {string} HTML.
     */
    #renderFactRow(entry) {
        return `
            <button class="context-fact-row" data-context-route="${escapeHtml(entry.route || "settings")}" data-context-target="${escapeHtml(this.#encodeTarget(entry.target || {}))}">
                <span class="metric-icon">${icon(entry.icon)}</span>
                <strong>${escapeHtml(entry.label)}</strong>
                <span>${escapeHtml(entry.summary)}</span>
                <span class="context-entry-open">${icon("chevronRight")}</span>
            </button>
        `;
    }
    /**
     * Convert one section without children into a dashboard card.
     *
     * @param {object} section Context section.
     * @returns {object|null} Normalized card or null.
     */
    #sectionEntry(section) {
        if (section.kind === "workspace") {
            return {
                kind: "workspace",
                icon: "home",
                typeLabel: "Workspace",
                label: "Raiz del workspace",
                summary: section.path || section.summary || "",
                route: "settings",
                target: { panel: "workspace" }
            };
        }
        if (section.kind === "system") {
            return {
                kind: "system",
                icon: "pulse",
                typeLabel: "Sistema",
                label: section.status === "ok" ? "Chequeos correctos" : "Chequeos con errores",
                summary: section.summary || "",
                route: "settings",
                target: { panel: "health" }
            };
        }
        if (section.kind === "notice") {
            return {
                kind: "notice",
                icon: "settings",
                typeLabel: "Aviso",
                label: section.title || "Aviso",
                summary: section.summary || section.body || "",
                route: "settings",
                target: { panel: "notice" }
            };
        }
        return null;
    }
    /**
     * Convert one section item into a dashboard card.
     *
     * @param {object} section Context section.
     * @param {object} item Section item.
     * @returns {object} Normalized card.
     */
    #itemEntry(section, item) {
        const iconName = {
            profiles: "users",
            diary: "document",
            logs: "document",
            backlog: "checkSquare"
        }[section.kind] || "document";
        return {
            kind: section.kind || "item",
            icon: iconName,
            typeLabel: this.#typeLabel(section, item),
            label: this.#itemLabel(section, item),
            summary: this.#itemSummary(section, item),
            title: item.label || item.id || section.title || "Contexto",
            route: item.route || section.route || "",
            target: item.target || {},
            domain: item.domain || item.target?.domain || "",
            date: item.date || item.target?.date || "",
            time: item.time || item.target?.time || "",
            changeType: item.changeType || item.type || ""
        };
    }
    /**
     * Return a human-readable title for one context entry.
     *
     * Log domains describe where an entry belongs. The entry identity is its
     * timestamp followed by its own title, which avoids repeating a terminal
     * domain segment as though it were the log title.
     *
     * @param {object} section Context section.
     * @param {object} item Section item.
     * @returns {string} Entry label.
     */
    #itemLabel(section, item) {
        const fallback = item.label || item.id || section.title || "Contexto";
        if (section.kind !== "logs") {
            return fallback;
        }
        const timestamp = [item.date, item.time].filter(Boolean).join(" ");
        return timestamp ? `${timestamp} -> ${fallback}` : fallback;
    }
    /**
     * Return the Spanish card type label.
     *
     * @param {object} section Context section.
     * @param {object} item Section item.
     * @returns {string} Type label.
     */
    #typeLabel(section, item) {
        if (section.kind === "profiles") {
            return "Perfil";
        }
        if (section.kind === "diary") {
            return `Diario ${item.date || ""}`.trim();
        }
        if (section.kind === "logs") {
            return "Entrada de log";
        }
        return section.title || "Contexto";
    }
    /**
     * Build a compact context summary.
     *
     * @param {object} section Context section.
     * @param {object} item Section item.
     * @returns {string} Summary.
     */
    #itemSummary(section, item) {
        if (section.kind === "profiles") {
            return item.command || `read-profile ${item.label || ""}`;
        }
        if (section.kind === "diary") {
            return item.target?.path || item.command || "Entrada de diario";
        }
        if (section.kind === "logs") {
            return `${item.domain || "logs"} - ${item.changeType || "registro"}`;
        }
        return item.command || section.summary || "";
    }
    /**
     * Resolve the section icon.
     *
     * @param {object} section Context section.
     * @returns {string} Icon key.
     */
    #sectionIcon(section) {
        return {
            workspace: "home",
            profiles: "users",
            diary: "document",
            logs: "document",
            system: "pulse",
            notice: "settings"
        }[section.kind] || "document";
    }
    /**
     * Resolve a fallback title for one context section.
     *
     * @param {object} section Context section.
     * @returns {string} Section title.
     */
    #sectionTitle(section) {
        return {
            workspace: "Workspace",
            profiles: "Perfiles",
            diary: "Diario reciente",
            logs: "Logs recientes",
            system: "Sistema",
            notice: "Avisos"
        }[section.kind] || "Contexto";
    }
    /**
     * Resolve a fallback section summary.
     *
     * @param {object} section Context section.
     * @param {number} count Entry count.
     * @returns {string} Section summary.
     */
    #sectionSummary(section, count) {
        if (section.kind === "workspace") {
            return section.path || "Raiz del workspace";
        }
        return `${count} entradas enlazadas`;
    }
    /**
     * Encode a target object for an HTML attribute.
     *
     * @param {object} target Card target.
     * @returns {string} Encoded target.
     */
    #encodeTarget(target) {
        return encodeURIComponent(JSON.stringify(target));
    }
    /**
     * Decode a target object from an HTML attribute.
     *
     * @param {string} value Encoded target.
     * @returns {object} Decoded target.
     */
    #decodeTarget(value) {
        try {
            return JSON.parse(decodeURIComponent(value));
        }
        catch {
            return {};
        }
    }
    /**
     * Render loading state.
     *
     * @returns {string} HTML.
     */
    #loadingState() {
        return `
            <div class="loading-state">
                <span></span>
                <strong>Hidratando contexto</strong>
            </div>
        `;
    }
}
customElements.define(DashboardView.selector, DashboardView);

cache=(()=>{return { DashboardView: DashboardView };})();return cache;};})();
const __brainExplorerModule5=(()=>{let cache;return()=>{if(cache)return cache;
const { compactLabel, escapeHtml, renderMarkdown } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
const { StructureTree } = __brainExplorerModule18();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */



void StructureTree;
/**
 * MemoryView renders the memory store as a collapsible tree and one focused work area.
 */
class MemoryView extends HTMLElement {
    static get selector() {
        return "brain-memory-view";
    }
    #api = null;
    #state = null;
    #paths = [];
    #selectedPath = "";
    #selectedDomain = "";
    #content = "";
    #status = "Preparando memoria...";
    #filter = "";
    #mode = "browse";
    #loadingTree = false;
    #loadingEntry = false;
    #saving = false;
    #expandedNodes = new Set();
    #pendingTarget = null;
    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#pendingTarget = this.#state?.consumeRouteTarget?.("memory") || this.#pendingTarget;
        this.#loadTree();
    }
    /**
     * Initialize component DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
    }
    /**
     * Load memory paths through the local CLI facade.
     *
     * @param {boolean} forceRefresh Whether to bypass API cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadTree(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        this.#loadingTree = true;
        this.#render();
        const result = await this.#api.memoryTree({ forceRefresh });
        this.#state?.setLastResult(result);
        this.#paths = Array.isArray(result.data) ? result.data : [];
        this.#selectedDomain = this.#selectedDomain || this.#topDomains()[0] || "";
        if (this.#selectedDomain) {
            this.#expandedNodes.add(this.#selectedDomain);
        }
        this.#status = result.ok ? `${this.#leafPaths().length} entradas` : result.stderr || result.error || "No se pudo cargar memoria.";
        this.#loadingTree = false;
        if (await this.#applyPendingTarget(forceRefresh)) {
            return;
        }
        this.#render();
    }
    /**
     * Apply one pending SPA navigation target after the tree is available.
     *
     * @param {boolean} forceRefresh Whether to bypass API cache when reading the target.
     * @returns {Promise<boolean>} True when a route target was consumed.
     */
    async #applyPendingTarget(forceRefresh = false) {
        const target = this.#pendingTarget || this.#state?.consumeRouteTarget?.("memory");
        this.#pendingTarget = null;
        if (!target) {
            return false;
        }
        if (target.path) {
            await this.#loadEntry(target.path, target.mode || "read", forceRefresh);
            return true;
        }
        if (target.domain) {
            this.#selectedDomain = target.domain;
            this.#selectedPath = "";
            this.#expandAncestors(target.domain);
            this.#mode = target.mode || "browse";
            this.#render();
            return true;
        }
        return false;
    }
    /**
     * Load one memory entry.
     *
     * @param {string} path Dot-notated memory path.
     * @param {string} mode Target mode.
     * @param {boolean} forceRefresh Whether to bypass API cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadEntry(path, mode = "read", forceRefresh = false) {
        this.#selectedPath = path;
        this.#selectedDomain = this.#parentPath(path) || path.split(".")[0] || this.#selectedDomain;
        this.#expandAncestors(path);
        this.#mode = mode;
        this.#loadingEntry = true;
        this.#status = compactLabel(path);
        this.#render();
        const result = await this.#api.memoryEntry(path, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#content = result.data?.content || result.stdout || "";
        this.#status = result.ok ? compactLabel(path) : result.stderr || result.error || "No se pudo leer la entrada.";
        this.#loadingEntry = false;
        this.#render();
    }
    /**
     * Prepare a new entry in edit mode under the selected domain.
     *
     * @returns {void}
     */
    #newEntry() {
        const baseDomain = this.#selectedDomain || this.#topDomains()[0] || "notes";
        this.#selectedPath = `${baseDomain}.nueva_entrada`;
        this.#content = "# Nueva entrada\n\nEscribe memoria Markdown aqui.";
        this.#mode = "edit";
        this.#status = "Nueva entrada";
        this.#render();
    }
    /**
     * Save editor content to memory.
     *
     * @returns {Promise<void>} Resolves after save.
     */
    async #saveEntry() {
        const path = this.querySelector("[data-role='memory-path']")?.value.trim();
        const content = this.querySelector("[data-role='memory-content']")?.value || this.#content;
        if (!path) {
            this.#status = "Define una ruta antes de guardar.";
            this.#render();
            return;
        }
        this.#saving = true;
        this.#render();
        const result = await this.#api.saveMemoryEntry(path, content);
        this.#state?.setLastResult(result);
        this.#selectedPath = path;
        this.#selectedDomain = this.#parentPath(path) || path.split(".")[0] || "";
        this.#content = content;
        this.#status = result.ok ? compactLabel(path) : result.stderr || result.error || "No se pudo guardar.";
        this.#saving = false;
        await this.#loadTree(true);
        this.#mode = "read";
        this.#render();
    }
    /**
     * Duplicate selected entry under a new path.
     *
     * @returns {Promise<void>} Resolves after duplication.
     */
    async #duplicateEntry() {
        if (!this.#selectedPath) {
            return;
        }
        const nextPath = `${this.#selectedPath}_copy`;
        const result = await this.#api.saveMemoryEntry(nextPath, this.#content);
        this.#state?.setLastResult(result);
        if (result.ok) {
            await this.#loadTree(true);
            await this.#loadEntry(nextPath, "edit", true);
        }
    }
    /**
     * Delete selected entry.
     *
     * @returns {Promise<void>} Resolves after deletion.
     */
    async #deleteEntry() {
        if (!this.#selectedPath) {
            return;
        }
        const result = await this.#api.deleteMemoryEntry(this.#selectedPath);
        this.#state?.setLastResult(result);
        this.#selectedPath = "";
        this.#content = "";
        this.#mode = "browse";
        this.#status = result.ok ? "Entrada eliminada" : result.stderr || result.error || "No se pudo eliminar.";
        await this.#loadTree(true);
    }
    /**
     * Create a memory domain.
     *
     * @returns {Promise<void>} Resolves after creation.
     */
    async #createDomain() {
        const domain = this.querySelector("[data-role='domain-name']")?.value.trim();
        if (!domain) {
            this.#status = "Escribe un dominio.";
            this.#render();
            return;
        }
        const result = await this.#api.createMemoryDomain(domain);
        this.#state?.setLastResult(result);
        this.#selectedDomain = domain;
        this.#selectedPath = "";
        this.#expandedNodes.add(domain.split(".")[0]);
        this.#status = result.ok ? `Dominio ${domain}` : result.stderr || result.error || "No se pudo crear dominio.";
        await this.#loadTree(true);
    }
    /**
     * Delete selected domain.
     *
     * @returns {Promise<void>} Resolves after deletion.
     */
    async #deleteDomain() {
        const domain = this.querySelector("[data-role='domain-name']")?.value.trim() || this.#selectedDomain;
        if (!domain) {
            return;
        }
        const result = await this.#api.deleteMemoryDomain(domain);
        this.#state?.setLastResult(result);
        this.#selectedDomain = "";
        this.#selectedPath = "";
        this.#content = "";
        this.#mode = "browse";
        this.#status = result.ok ? "Dominio eliminado" : result.stderr || result.error || "No se pudo eliminar dominio.";
        await this.#loadTree(true);
    }
    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface memory-console">
                <div class="structure-layout memory-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.#renderTree()}
                        </div>
                    </aside>
                    <main class="structure-content">
                        ${this.#renderContent()}
                    </main>
                </div>
            </section>
        `;
        this.#bindEvents();
        this.#configureTree();
    }
    /**
     * Render the primary action for the current mode.
     *
     * @returns {string} HTML.
     */
    #renderPrimaryAction() {
        if (this.#mode === "edit") {
            return this.#renderIconButton("save-entry", "save", this.#saving ? "Guardando entrada" : "Guardar entrada", "primary-action compact-action", this.#saving);
        }
        if (this.#mode === "domains") {
            return this.#renderIconButton("create-domain", "folderPlus", "Crear dominio", "primary-action compact-action");
        }
        return this.#renderIconButton("new-entry", "documentPlus", "Nueva entrada", "primary-action compact-action");
    }
    /**
     * Render the memory mode menu as an icon-only control.
     *
     * @returns {string} HTML.
     */
    #renderModeMenu() {
        const modes = ["browse", "read", "edit", "domains"];
        const label = this.#modeLabel(this.#mode);
        return `
            <details class="action-menu mode-menu">
                <summary class="icon-action" title="Modo: ${escapeHtml(label)}" aria-label="Modo de memoria: ${escapeHtml(label)}">
                    ${icon(this.#modeIcon(this.#mode))}
                </summary>
                <div class="action-menu-panel">
                    ${modes.map(mode => `
                        <button data-action="set-memory-mode" data-memory-mode="${escapeHtml(mode)}" ${mode === this.#mode ? "aria-current=\"true\"" : ""}>
                            ${icon(this.#modeIcon(mode))}${escapeHtml(this.#modeLabel(mode))}
                        </button>
                    `).join("")}
                </div>
            </details>
        `;
    }
    /**
     * Render a square icon-only toolbar button.
     *
     * @param {string} action Data action name.
     * @param {string} iconName Shared SVG icon key.
     * @param {string} label Accessible action label.
     * @param {string} className Extra CSS classes.
     * @param {boolean} disabled Whether the action is disabled.
     * @returns {string} HTML.
     */
    #renderIconButton(action, iconName, label, className = "", disabled = false) {
        return `
            <button
                data-action="${escapeHtml(action)}"
                class="icon-action ${escapeHtml(className)}"
                title="${escapeHtml(label)}"
                aria-label="${escapeHtml(label)}"
                ${disabled ? "disabled" : ""}
            >${icon(iconName)}</button>
        `;
    }
    /**
     * Return the icon key for one memory mode.
     *
     * @param {string} mode Memory mode.
     * @returns {string} Icon key.
     */
    #modeIcon(mode) {
        return {
            browse: "database",
            read: "eye",
            edit: "edit",
            domains: "folder"
        }[mode] || "database";
    }
    /**
     * Return the reader-facing label for one memory mode.
     *
     * @param {string} mode Memory mode.
     * @returns {string} Spanish mode label.
     */
    #modeLabel(mode) {
        return {
            browse: "Explorar",
            read: "Leer",
            edit: "Editar",
            domains: "Dominios"
        }[mode] || "Explorar";
    }
    /**
     * Render the contextual secondary action menu.
     *
     * @returns {string} HTML.
     */
    #renderActionMenu() {
        const isEntry = Boolean(this.#selectedPath);
        const label = isEntry ? "Entrada" : "Dominio";
        const entryActions = `
            <button data-action="refresh-memory">${icon("refresh")}Actualizar</button>
            <button data-action="edit-entry" ${this.#selectedPath ? "" : "disabled"}>${icon("edit")}Editar entrada</button>
            <button data-action="duplicate-entry" ${this.#selectedPath ? "" : "disabled"}>${icon("copy")}Duplicar entrada</button>
            <button data-action="delete-entry" class="danger-button" ${this.#selectedPath ? "" : "disabled"}>${icon("trash")}Eliminar entrada</button>
        `;
        const domainActions = `
            <button data-action="refresh-memory">${icon("refresh")}Actualizar arbol</button>
            <button data-action="new-entry" ${this.#selectedDomain ? "" : "disabled"}>${icon("plus")}Nueva entrada aqui</button>
            <button data-action="domain-mode">${icon("folder")}Gestionar dominio</button>
            <button data-action="delete-domain" class="danger-button" ${this.#selectedDomain ? "" : "disabled"}>${icon("trash")}Eliminar dominio</button>
        `;
        return `
            <details class="action-menu">
                <summary class="icon-action" title="Acciones de ${escapeHtml(label.toLowerCase())}" aria-label="Acciones de ${escapeHtml(label.toLowerCase())}">
                    ${icon("more")}
                </summary>
                <div class="action-menu-panel">
                    ${isEntry ? entryActions : domainActions}
                </div>
            </details>
        `;
    }
    /**
     * Render the active content area.
     *
     * @returns {string} HTML.
     */
    #renderContent() {
        if (this.#mode === "read") {
            return this.#renderReadContent();
        }
        if (this.#mode === "edit") {
            return this.#renderEditContent();
        }
        if (this.#mode === "domains") {
            return this.#renderDomainsContent();
        }
        return this.#renderBrowseContent();
    }
    /**
     * Render selected domain children.
     *
     * @returns {string} HTML.
     */
    #renderBrowseContent() {
        const children = this.#childItemsForSelectedDomain();
        return `
            <div class="content-head">
                <strong>${escapeHtml(this.#selectedDomain || "Memoria")}</strong>
                <span>${escapeHtml(String(children.length))} visibles</span>
            </div>
            <div class="entry-list scroll-list">
                ${children.length ? children.map(item => this.#renderContentItem(item)).join("") : `<p class="empty-state">Selecciona un nodo del arbol.</p>`}
            </div>
        `;
    }
    /**
     * Render one child row in the content area.
     *
     * @param {object} item Tree item.
     * @returns {string} HTML.
     */
    #renderContentItem(item) {
        const isBranch = item.children.size > 0;
        const action = isBranch ? "select-domain" : "select-entry";
        const count = isBranch ? `${this.#leafPathsUnder(item.path).length} entradas` : "Entrada";
        return `
            <button class="entry-row ${item.path === this.#selectedPath ? "is-active" : ""}" data-action="${action}" data-node-path="${escapeHtml(item.path)}">
                ${icon(isBranch ? "folder" : "document")}
                <span>
                    <strong>${escapeHtml(item.label)}</strong>
                    <small>${escapeHtml(count)}</small>
                </span>
            </button>
        `;
    }
    /**
     * Render markdown reading mode.
     *
     * @returns {string} HTML.
     */
    #renderReadContent() {
        return `
            <div class="content-head">
                <strong>${escapeHtml(compactLabel(this.#selectedPath) || "Sin entrada")}</strong>
                <span>${escapeHtml(this.#selectedPath || this.#status)}</span>
            </div>
            <article class="markdown-preview scroll-area">
                ${this.#loadingEntry ? this.#loadingState("Renderizando Markdown") : renderMarkdown(this.#content || "Selecciona una entrada.")}
            </article>
        `;
    }
    /**
     * Render entry editor mode.
     *
     * @returns {string} HTML.
     */
    #renderEditContent() {
        return `
            <div class="content-head editor-path-row">
                <label class="path-compact">
                    <span>Ruta</span>
                    <input data-role="memory-path" value="${escapeHtml(this.#selectedPath)}" placeholder="dominio.entrada">
                </label>
            </div>
            <textarea class="markdown-editor scroll-area" data-role="memory-content" spellcheck="false">${escapeHtml(this.#content)}</textarea>
        `;
    }
    /**
     * Render domain management mode.
     *
     * @returns {string} HTML.
     */
    #renderDomainsContent() {
        return `
            <div class="content-head editor-path-row">
                <label class="path-compact">
                    <span>Dominio</span>
                    <input data-role="domain-name" value="${escapeHtml(this.#selectedDomain)}" placeholder="nuevo.dominio">
                </label>
            </div>
            <div class="domain-grid scroll-list">
                ${this.#topDomains().map(domain => `
                    <button class="domain-tile ${domain === this.#selectedDomain ? "is-active" : ""}" data-action="select-domain" data-node-path="${escapeHtml(domain)}">
                        ${icon("database")}
                        <strong>${escapeHtml(domain)}</strong>
                        <span>${escapeHtml(String(this.#leafPathsUnder(domain).length))} entradas</span>
                    </button>
                `).join("") || `<p class="empty-state">Sin dominios.</p>`}
            </div>
        `;
    }
    /**
     * Render the collapsible memory tree.
     *
     * @returns {string} HTML.
     */
    #renderTree() {
        return `<brain-structure-tree data-role="memory-tree"></brain-structure-tree>`;
    }
    /**
     * Render one tree node.
     *
     * @param {object} node Tree node.
     * @param {number} depth Tree depth.
     * @returns {string} HTML.
     */
    #renderTreeNode(node, depth) {
        const hasChildren = node.children.size > 0;
        const isOpen = this.#expandedNodes.has(node.path);
        const isActive = node.path === this.#selectedDomain || node.path === this.#selectedPath;
        const children = Array.from(node.children.values()).sort(this.#sortTreeNodes);
        const isVisible = this.#matchesFilter(node) || children.some(child => this.#nodeContainsFilter(child));
        if (!isVisible) {
            return "";
        }
        return `
            <div class="tree-node-wrap">
                <button class="tree-node ${isActive ? "is-active" : ""}" style="--tree-depth:${depth}" data-node-path="${escapeHtml(node.path)}" data-node-branch="${hasChildren ? "true" : "false"}">
                    <span class="tree-caret">${hasChildren ? icon(isOpen ? "chevronDown" : "chevronRight") : ""}</span>
                    ${icon(hasChildren ? "folder" : "document")}
                    <span>${escapeHtml(node.label)}</span>
                    ${hasChildren ? `<small>${escapeHtml(String(this.#leafPathsUnder(node.path).length))}</small>` : ""}
                </button>
                ${hasChildren && isOpen ? `<div class="tree-children">${children.map(child => this.#renderTreeNode(child, depth + 1)).join("")}</div>` : ""}
            </div>
        `;
    }
    /**
     * Configure the shared structural tree with Memory-specific actions.
     *
     * @returns {void}
     */
    #configureTree() {
        const treeElement = this.querySelector("[data-role='memory-tree']");
        if (!treeElement) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#selectedPath || this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
            toggleOnBranchSelect: true,
            title: "Memoria",
            toolbarActions: [
                { id: "new-entry", label: "Nueva entrada", icon: "plus" },
                { id: "create-domain", label: "Nuevo dominio", icon: "folder" },
                { id: "refresh", label: "Actualizar arbol", icon: "refresh" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "database",
            searchQuery: this.#filter,
            emptyText: this.#loadingTree ? "Cargando arbol..." : "Sin rutas cargadas."
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onTreeAction(event));
        treeElement.addEventListener("brain-tree-search", event => {
            this.#filter = event.detail.query;
            const mainContent = this.querySelector(".structure-content");
            if (mainContent) {
                mainContent.innerHTML = this.#renderContent();
            }
        });
    }
    /**
     * Convert the in-memory path tree into shared presentation nodes.
     *
     * @returns {object[]} Tree node list.
     */
    #treeNodes() {
        const toNode = node => {
            const children = Array.from(node.children.values())
                .filter(child => this.#matchesFilter(child) || this.#nodeContainsFilter(child))
                .sort(this.#sortTreeNodes)
                .map(toNode);
            const hasChildren = children.length > 0;
            return {
                id: node.path,
                path: node.path,
                label: node.label,
                count: hasChildren ? this.#leafPathsUnder(node.path).length : undefined,
                children,
                actions: hasChildren
                    ? [
                        { id: "new-entry", label: "Nueva entrada", icon: "plus" },
                        { id: "delete-domain", label: "Eliminar dominio", icon: "trash", danger: true }
                    ]
                    : [
                        { id: "open-entry", label: "Abrir", icon: "document" },
                        { id: "edit-entry", label: "Editar", icon: "edit" },
                        { id: "duplicate-entry", label: "Duplicar", icon: "duplicate" },
                        { id: "delete-entry", label: "Eliminar", icon: "trash", danger: true }
                    ]
            };
        };
        return Array.from(this.#buildTree().children.values())
            .filter(node => this.#matchesFilter(node) || this.#nodeContainsFilter(node))
            .sort(this.#sortTreeNodes)
            .map(toNode);
    }
    /**
     * React to a shared tree selection.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeSelected(event) {
        const { path, branch, clickedCaret } = event.detail;
        if (branch) {
            if (clickedCaret) {
                return;
            }
            this.#selectedDomain = path;
            this.#selectedPath = "";
            this.#mode = this.#mode === "edit" ? "browse" : this.#mode;
            this.#render();
            return;
        }
        this.#loadEntry(path, "read");
    }
    /**
     * Execute a global Memory tree toolbar action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeToolbarAction(event) {
        const action = event.detail.action;
        if (action === "new-entry") {
            this.#newEntry();
        }
        else if (action === "create-domain") {
            this.#mode = "domains";
            this.#render();
        }
        else if (action === "refresh") {
            this.#loadTree(true);
        }
    }
    /**
     * Execute a contextual Memory item action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeAction(event) {
        const { action, node } = event.detail;
        if (!node) {
            return;
        }
        if (action === "new-entry") {
            this.#selectedDomain = node.path;
            this.#newEntry();
        }
        else if (action === "delete-domain") {
            this.#selectedDomain = node.path;
            this.#deleteDomain();
        }
        else if (action === "open-entry") {
            this.#loadEntry(node.path, "read");
        }
        else if (action === "edit-entry") {
            this.#loadEntry(node.path, "edit");
        }
        else if (action === "duplicate-entry") {
            this.#selectedPath = node.path;
            this.#duplicateEntry();
        }
        else if (action === "delete-entry") {
            this.#selectedPath = node.path;
            this.#deleteEntry();
        }
    }
    /**
     * Render loading state.
     *
     * @param {string} label Loading label.
     * @returns {string} HTML.
     */
    #loadingState(label) {
        return `
            <div class="loading-state">
                <span></span>
                <strong>${escapeHtml(label)}</strong>
            </div>
        `;
    }
    /**
     * Build a tree from dot-notated paths.
     *
     * @returns {object} Tree root.
     */
    #buildTree() {
        const root = { label: "", path: "", children: new Map() };
        for (const path of this.#paths) {
            const parts = String(path).split(".").filter(Boolean);
            let current = root;
            parts.forEach((part, index) => {
                const nodePath = parts.slice(0, index + 1).join(".");
                if (!current.children.has(part)) {
                    current.children.set(part, { label: part, path: nodePath, children: new Map() });
                }
                current = current.children.get(part);
            });
        }
        return root;
    }
    /**
     * Return direct children for the selected domain.
     *
     * @returns {object[]} Child tree nodes.
     */
    #childItemsForSelectedDomain() {
        const tree = this.#buildTree();
        const node = this.#findNode(tree, this.#selectedDomain);
        const parent = node || tree;
        return Array.from(parent.children.values())
            .filter(item => this.#matchesFilter(item) || this.#nodeContainsFilter(item))
            .sort(this.#sortTreeNodes);
    }
    /**
     * Find a node by full path.
     *
     * @param {object} root Tree root.
     * @param {string} path Dot-notated path.
     * @returns {object|null} Tree node.
     */
    #findNode(root, path) {
        if (!path) {
            return root;
        }
        return path.split(".").reduce((node, part) => node?.children?.get(part), root) || null;
    }
    /**
     * Return top-level domains.
     *
     * @returns {string[]} Domain names.
     */
    #topDomains() {
        return [...new Set(this.#paths.map(path => path.split(".")[0]).filter(Boolean))];
    }
    /**
     * Return leaf entry paths.
     *
     * @returns {string[]} Leaf paths.
     */
    #leafPaths() {
        return this.#paths.filter(path => !this.#hasChildren(path) && path.includes("."));
    }
    /**
     * Return leaf entry paths under one domain path.
     *
     * @param {string} prefix Domain path.
     * @returns {string[]} Leaf paths.
     */
    #leafPathsUnder(prefix) {
        return this.#leafPaths().filter(path => path === prefix || path.startsWith(`${prefix}.`));
    }
    /**
     * Return whether a path has child paths.
     *
     * @param {string} path Dot-notated path.
     * @returns {boolean} True when the path has children.
     */
    #hasChildren(path) {
        return this.#paths.some(candidate => candidate !== path && candidate.startsWith(`${path}.`));
    }
    /**
     * Resolve parent path.
     *
     * @param {string} path Dot-notated path.
     * @returns {string} Parent path.
     */
    #parentPath(path) {
        const parts = String(path || "").split(".");
        parts.pop();
        return parts.join(".");
    }
    /**
     * Expand ancestors for a selected path.
     *
     * @param {string} path Dot-notated path.
     * @returns {void}
     */
    #expandAncestors(path) {
        const parts = String(path || "").split(".");
        for (let index = 1; index < parts.length; index += 1) {
            this.#expandedNodes.add(parts.slice(0, index).join("."));
        }
    }
    /**
     * Return whether a node matches the text filter.
     *
     * @param {object} node Tree node.
     * @returns {boolean} True when visible by filter.
     */
    #matchesFilter(node) {
        const needle = this.#filter.toLowerCase();
        return !needle || node.path.toLowerCase().includes(needle);
    }
    /**
     * Return whether a node or descendants match the current filter.
     *
     * @param {object} node Tree node.
     * @returns {boolean} True when a descendant matches.
     */
    #nodeContainsFilter(node) {
        if (this.#matchesFilter(node)) {
            return true;
        }
        return Array.from(node.children.values()).some(child => this.#nodeContainsFilter(child));
    }
    /**
     * Sort tree nodes with branches first.
     *
     * @param {object} left First node.
     * @param {object} right Second node.
     * @returns {number} Sort order.
     */
    #sortTreeNodes(left, right) {
        const leftBranch = left.children.size > 0 ? 0 : 1;
        const rightBranch = right.children.size > 0 ? 0 : 1;
        return leftBranch - rightBranch || left.label.localeCompare(right.label);
    }
    /**
     * Bind DOM events after render.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelectorAll("[data-action='set-memory-mode']").forEach(button => button.addEventListener("click", () => {
            this.#mode = button.getAttribute("data-memory-mode") || this.#mode;
            this.#render();
        }));
        this.querySelector("[data-action='refresh-memory']")?.addEventListener("click", () => this.#loadTree(true));
        this.querySelectorAll("[data-action='new-entry']").forEach(button => button.addEventListener("click", () => this.#newEntry()));
        this.querySelector("[data-action='domain-mode']")?.addEventListener("click", () => {
            this.#mode = "domains";
            this.#render();
        });
        this.querySelector("[data-action='edit-entry']")?.addEventListener("click", () => {
            this.#mode = "edit";
            this.#render();
        });
        this.querySelector("[data-action='save-entry']")?.addEventListener("click", () => this.#saveEntry());
        this.querySelector("[data-action='duplicate-entry']")?.addEventListener("click", () => this.#duplicateEntry());
        this.querySelector("[data-action='delete-entry']")?.addEventListener("click", () => this.#deleteEntry());
        this.querySelector("[data-action='delete-domain']")?.addEventListener("click", () => this.#deleteDomain());
        this.querySelector("[data-action='create-domain']")?.addEventListener("click", () => this.#createDomain());
        this.querySelectorAll("[data-node-path]").forEach(item => item.addEventListener("click", () => {
            const path = item.getAttribute("data-node-path") || "";
            const isBranch = item.getAttribute("data-node-branch") === "true" || this.#hasChildren(path);
            if (isBranch) {
                this.#selectedDomain = path;
                this.#selectedPath = "";
                this.#mode = this.#mode === "edit" ? "browse" : this.#mode;
                if (this.#expandedNodes.has(path)) {
                    this.#expandedNodes.delete(path);
                }
                else {
                    this.#expandedNodes.add(path);
                }
                this.#render();
                return;
            }
            this.#loadEntry(path, "read");
        }));
    }
}
customElements.define(MemoryView.selector, MemoryView);

cache=(()=>{return { MemoryView: MemoryView };})();return cache;};})();
const __brainExplorerModule6=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
const { StructureTree } = __brainExplorerModule18();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */



void StructureTree;
/**
 * KnowledgeView renders a canvas-based explorer for graph records returned by the CLI facade.
 * Entities/classes become draggable nodes. Relations become selectable edges.
 */
class KnowledgeView extends HTMLElement {
    static get selector() {
        return "brain-knowledge-view";
    }
    #api = null;
    #state = null;
    #scope = "global";
    #mode = "all";
    #domain = "all";
    #query = "";
    #output = null;
    #records = [];
    #relations = [];
    #nodes = [];
    #edges = [];
    #selectedNodeId = "";
    #selectedRelationId = "";
    #regionNodeIds = new Set();
    #regionEdgeIds = new Set();
    #regionPositions = new Map();
    #dragNode = null;
    #panState = null;
    #cameraAnimationFrame = 0;
    #viewport = { x: 0, y: 0, scale: 1 };
    #renderFrustum = null;
    #expandedDomains = new Set(["all"]);
    #resizeObserver = null;
    #loadScheduled = false;
    #needsViewportFit = true;
    #filtersOpen = false;
    #domainTreeNodes = [];
    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#render();
        this.#scheduleInitialLoad();
    }
    /**
     * Initialize component DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
        this.#scheduleInitialLoad();
    }
    /**
     * Disconnect canvas observers.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        this.#resizeObserver?.disconnect();
        cancelAnimationFrame(this.#cameraAnimationFrame);
    }
    /**
     * Load records once after the component has context.
     *
     * @returns {void}
     */
    #scheduleInitialLoad() {
        if (!this.#api || this.#loadScheduled || this.#output) {
            return;
        }
        this.#loadScheduled = true;
        queueMicrotask(() => this.#showRecords());
    }
    /**
     * List graph records for the current scope and view.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after list call.
     */
    async #showRecords(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        this.#readControls();
        const result = await this.#api.knowledgeShow({
            scope: this.#scope,
            mode: "all"
        }, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#output = result;
        this.#ingestGraph(result.data);
        this.#render();
    }
    /**
     * Search graph records.
     *
     * @returns {Promise<void>} Resolves after query call.
     */
    async #queryRecords() {
        if (!this.#api) {
            return;
        }
        this.#readControls();
        if (!this.#query) {
            this.#applyFilters();
            return;
        }
        const result = await this.#api.knowledgeQuery({
            q: this.#query,
            scope: this.#scope,
            limit: "120",
            explain: "true"
        });
        this.#state?.setLastResult(result);
        this.#output = result;
        this.#ingestGraph(result.data);
        this.#render();
    }
    /**
     * Load pending delta review.
     *
     * @returns {Promise<void>} Resolves after delta review.
     */
    async #reviewDeltas() {
        if (!this.#api) {
            return;
        }
        this.#readControls();
        const result = await this.#api.knowledgeDeltas({
            scope: this.#scope,
            limit: "80",
            status: "pending"
        }, { forceRefresh: true });
        this.#state?.setLastResult(result);
        this.#output = result;
        this.#ingestGraph(result.data);
        this.#render();
    }
    /**
     * Store normalized graph data and refresh derived nodes.
     *
     * @param {unknown} data Command data.
     * @returns {void}
     */
    #ingestGraph(data) {
        const graph = this.#collectGraph(data);
        this.#records = graph.records;
        this.#relations = graph.relations;
        if (this.#domain !== "all" && !this.#domains().some(domain => domain === this.#domain || domain.startsWith(`${this.#domain}.`))) {
            this.#domain = "all";
        }
        this.#selectedNodeId = "";
        this.#selectedRelationId = "";
        this.#regionNodeIds.clear();
        this.#regionEdgeIds.clear();
        this.#regionPositions.clear();
        this.#needsViewportFit = true;
        this.#prepareGraph();
    }
    /**
     * Read form controls into component state.
     *
     * @returns {void}
     */
    #readControls() {
        this.#scope = this.querySelector("[data-role='kg-scope']")?.value || this.#scope;
        const selectedModes = [...this.querySelectorAll("[data-filter-kind='kg-mode']:checked")]
            .map(input => input.value);
        this.#mode = selectedModes.length === 1 ? selectedModes[0] : "all";
        this.#query = this.querySelector("[data-role='kg-query']")?.value.trim() || "";
    }
    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface knowledge-console">
                <div class="structure-layout knowledge-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.#renderDomainTree()}
                        </div>
                    </aside>
                    <main class="structure-content knowledge-content">
                        <div class="content-head graph-toolbar">
                            <input class="graph-search-input" aria-label="Buscar en el grafo" data-role="kg-query" value="${escapeHtml(this.#query)}" placeholder="Filtrar o buscar en el grafo">
                            <details class="action-menu filter-menu knowledge-filter-menu" ${this.#filtersOpen ? "open" : ""}>
                                <summary class="compact-action">${icon("filter")}<span>Filtros</span></summary>
                                <div class="action-menu-panel filter-menu-panel">
                                    <header class="knowledge-filter-heading">
                                        <strong>Vista del grafo</strong>
                                        <small>Ajusta el alcance y el contenido visible.</small>
                                    </header>
                                    <label class="knowledge-filter-control">
                                        <span>Alcance</span>
                                        <select data-role="kg-scope">
                                            <option value="global" ${this.#scope === "global" ? "selected" : ""}>Global</option>
                                            <option value="local" ${this.#scope === "local" ? "selected" : ""}>Local</option>
                                        </select>
                                    </label>
                                    <fieldset class="checkbox-filter-group">
                                        <legend>Contenido visible</legend>
                                        <div class="knowledge-filter-options">
                                            <label><input type="checkbox" data-filter-kind="kg-mode" value="entities" ${this.#mode === "all" || this.#mode === "entities" ? "checked" : ""}><span>Entidades</span></label>
                                            <label><input type="checkbox" data-filter-kind="kg-mode" value="classes" ${this.#mode === "all" || this.#mode === "classes" ? "checked" : ""}><span>Clases</span></label>
                                        </div>
                                    </fieldset>
                                </div>
                            </details>
                            <button data-action="query-records" class="primary-action">${icon("search")}Buscar</button>
                        </div>
                        <div class="knowledge-canvas-layout">
                            <main class="graph-viewport">
                                <button class="graph-focus-back secondary-action compact-action" data-action="clear-graph-focus" ${this.#regionNodeIds.size ? "" : "hidden"}>
                                    ${icon("chevronRight")} Atrás
                                </button>
                                <canvas class="knowledge-graph-canvas" data-role="knowledge-canvas" aria-label="Grafo de conocimiento"></canvas>
                                ${this.#renderCanvasEmptyState()}
                            </main>
                            <aside class="graph-detail-list">
                                ${this.#renderDetails()}
                            </aside>
                        </div>
                    </main>
                </div>
            </section>
        `;
        this.#bindEvents();
        this.#configureDomainTree();
        this.#bindCanvas();
    }
    /**
     * Render an empty overlay only when there are no visible nodes.
     *
     * @returns {string} HTML.
     */
    #renderCanvasEmptyState() {
        if (this.#nodes.length || this.#records.length || this.#relations.length) {
            return "";
        }
        return `
            <div class="knowledge-empty-state canvas-empty">
                ${icon("graph")}
                <h2>${this.#output?.ok === false ? "No se pudo consultar" : "Cargando grafo"}</h2>
                <p>${escapeHtml(this.#output?.error || this.#output?.stderr || "Los nodos apareceran aqui.")}</p>
            </div>
        `;
    }
    /**
     * Render the domain tree used to scope the graph.
     *
     * @returns {string} HTML.
     */
    #renderDomainTree() {
        const root = { label: "Todo el conocimiento", path: "all", children: new Map() };
        this.#domains().forEach(domain => {
            const parts = this.#domainParts(domain);
            let node = root;
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                if (!node.children.has(part)) {
                    node.children.set(part, { label: part, path, children: new Map() });
                }
                node = node.children.get(part);
            });
        });
        const children = this.#knowledgeTreeNodes([...root.children.values()]);
        this.#domainTreeNodes = [{
                id: "all",
                path: "all",
                label: "Todo el conocimiento",
                icon: "database",
                count: this.#records.length + this.#relations.length,
                children,
                actions: []
            }];
        return `<brain-structure-tree data-role="knowledge-domain-tree"></brain-structure-tree>`;
    }
    /**
     * Convert parsed Knowledge domains into shared tree nodes.
     *
     * @param {object[]} nodes Source domain nodes.
     * @returns {object[]} Shared tree nodes.
     */
    #knowledgeTreeNodes(nodes) {
        return nodes
            .map(node => {
            const children = this.#knowledgeTreeNodes([...node.children.values()]);
            return {
                id: node.path,
                path: node.path,
                label: node.label,
                color: this.#domainColor(node.path),
                count: this.#countRecordsInDomain(node.path),
                children,
                actions: []
            };
        })
            .sort((left, right) => left.label.localeCompare(right.label));
    }
    /**
     * Configure the shared tree with Knowledge graph actions.
     *
     * @returns {void}
     */
    #configureDomainTree() {
        const treeElement = this.querySelector("[data-role='knowledge-domain-tree']");
        if (!treeElement) {
            return;
        }
        treeElement.model = {
            nodes: this.#domainTreeNodes,
            selectedPath: this.#domain,
            expandedPaths: this.#expandedDomains,
            toggleOnBranchSelect: true,
            title: "Conocimiento",
            toolbarActions: [
                { id: "refresh-graph", label: "Actualizar grafo", icon: "refresh" },
                { id: "review-deltas", label: "Revisar deltas", icon: "graph" },
                { id: "fit-graph", label: "Centrar canvas", icon: "filter" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "document"
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onDomainTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onDomainTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onDomainTreeAction(event));
    }
    /**
     * Scope the graph to a selected domain.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onDomainTreeSelected(event) {
        if (event.detail.branch && event.detail.clickedCaret) {
            return;
        }
        this.#domain = event.detail.path || "all";
        this.#applyFilters();
    }
    /**
     * Run one global Knowledge tree action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onDomainTreeToolbarAction(event) {
        if (event.detail.action === "refresh-graph") {
            this.#showRecords(true);
        }
        else if (event.detail.action === "review-deltas") {
            this.#reviewDeltas();
        }
        else if (event.detail.action === "fit-graph") {
            this.#needsViewportFit = true;
            this.#drawCanvas();
        }
    }
    /**
     * Scope the graph from a domain contextual action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onDomainTreeAction(event) {
        if (!event.detail.node?.path) {
            return;
        }
        this.#domain = event.detail.node.path;
        this.#applyFilters();
    }
    /**
     * Render recursive domain rows.
     *
     * @param {object[]} nodes Domain nodes.
     * @param {number} depth Tree depth.
     * @param {string} filter Text filter.
     * @returns {string} HTML.
     */
    #renderDomainChildren(nodes, depth, filter) {
        return nodes
            .filter(node => !filter || node.path.toLowerCase().includes(filter))
            .map(node => {
            const children = [...node.children.values()];
            const expanded = this.#expandedDomains.has(node.path);
            const count = this.#countRecordsInDomain(node.path);
            return `
                    <div class="tree-node-wrap">
                        <button class="tree-node ${this.#domain === node.path ? "is-active" : ""}" style="--tree-depth: ${depth}" data-action="select-domain" data-domain-path="${escapeHtml(node.path)}">
                            <span class="tree-caret">${children.length ? icon(expanded ? "chevronDown" : "chevronRight") : ""}</span>
                            ${icon(children.length ? "folder" : "document")}
                            <span>${escapeHtml(node.label)}</span>
                            <small>${escapeHtml(String(count))}</small>
                        </button>
                        ${expanded && children.length ? `<div class="tree-children">${this.#renderDomainChildren(children, depth + 1, filter)}</div>` : ""}
                    </div>
                `;
        }).join("");
    }
    /**
     * Render the graph inspector.
     *
     * @returns {string} HTML.
     */
    #renderDetails() {
        const selectedRelation = this.#edges.find(edge => edge.id === this.#selectedRelationId);
        if (selectedRelation) {
            return this.#renderRelationDetails(selectedRelation);
        }
        const selected = this.#nodes.find(node => node.id === this.#selectedNodeId);
        if (selected) {
            return this.#renderNodeDetails(selected);
        }
        const domains = this.#domains();
        return `
            <div class="content-head">
                <strong>Inspector</strong>
                <span>${escapeHtml(String(this.#nodes.length))} nodos · ${escapeHtml(String(this.#edges.length))} relaciones</span>
            </div>
            <div class="node-inspector scroll-list">
                <p>Selecciona un nodo o una relacion del canvas. Los nodos se arrastran; el lienzo acepta pan y zoom.</p>
                <div class="source-chip-row">
                    ${domains.slice(0, 12).map(domain => `<span>${escapeHtml(domain)}</span>`).join("")}
                </div>
            </div>
        `;
    }
    /**
     * Render entity/class node details.
     *
     * @param {object} selected Selected graph node.
     * @returns {string} HTML.
     */
    #renderNodeDetails(selected) {
        return `
            <div class="content-head">
                <strong>${escapeHtml(selected.label)}</strong>
                <span>${escapeHtml(selected.domain)}</span>
            </div>
            <div class="node-inspector scroll-list">
                <dl>
                    <dt>Contexto</dt><dd>${escapeHtml(selected.context)}</dd>
                    <dt>Dominio</dt><dd>${escapeHtml(selected.domain)}</dd>
                    <dt>Fuente</dt><dd>${escapeHtml(selected.source)}</dd>
                    <dt>Clase sugerida</dt><dd>${escapeHtml(selected.classHint || "-")}</dd>
                    <dt>Confianza</dt><dd>${escapeHtml(String(selected.confidence || "-"))}</dd>
                </dl>
                <p>${escapeHtml(selected.description || "Sin descripcion disponible.")}</p>
                ${this.#renderRelatedNodes(selected)}
            </div>
        `;
    }
    /**
     * Render relation edge details.
     *
     * @param {object} relation Selected relation edge.
     * @returns {string} HTML.
     */
    #renderRelationDetails(relation) {
        return `
            <div class="content-head">
                <strong>Relacion</strong>
                <span>${escapeHtml(relation.label)}</span>
            </div>
            <div class="node-inspector relation-inspector scroll-list">
                <dl>
                    <dt>Nombre</dt><dd>${escapeHtml(relation.label)}</dd>
                    <dt>Origen</dt><dd>${escapeHtml(relation.fromLabel)}</dd>
                    <dt>Destino</dt><dd>${escapeHtml(relation.toLabel)}</dd>
                    <dt>Contexto</dt><dd>${escapeHtml(relation.context)}</dd>
                    <dt>Dominio</dt><dd>${escapeHtml(relation.domain)}</dd>
                    <dt>Fuente</dt><dd>${escapeHtml(relation.source)}</dd>
                    <dt>Confianza</dt><dd>${escapeHtml(String(relation.confidence || "-"))}</dd>
                </dl>
                <p>${escapeHtml(relation.description || "Relacion detectada por el facade CLI.")}</p>
                <div class="graph-list">
                    ${[relation.from, relation.to].map(nodeId => {
            const node = this.#nodes.find(item => item.id === nodeId);
            return node ? `
                            <button class="graph-list-item" data-action="select-node" data-node-id="${escapeHtml(node.id)}">
                                <span class="activity-dot" style="background: ${escapeHtml(node.color)}"></span>
                                <strong>${escapeHtml(node.label)}</strong>
                            </button>
                        ` : "";
        }).join("")}
                </div>
            </div>
        `;
    }
    /**
     * Render related node labels for the selected node.
     *
     * @param {object} selected Selected graph node.
     * @returns {string} HTML.
     */
    #renderRelatedNodes(selected) {
        const related = this.#edges
            .filter(edge => edge.from === selected.id || edge.to === selected.id)
            .slice(0, 10);
        if (!related.length) {
            return "";
        }
        return `
            <h2>Relaciones visibles</h2>
            <div class="graph-list">
                ${related.map(edge => {
            const opposite = this.#nodes.find(node => node.id === (edge.from === selected.id ? edge.to : edge.from));
            return opposite ? `
                        <button class="graph-list-item" data-action="select-relation" data-relation-id="${escapeHtml(edge.id)}">
                            <span class="activity-dot" style="background: ${escapeHtml(opposite.color)}"></span>
                            <strong>${escapeHtml(edge.label)} - ${escapeHtml(opposite.label)}</strong>
                        </button>
                    ` : "";
        }).join("")}
            </div>
        `;
    }
    /**
     * Convert command data to normalized graph records.
     *
     * @param {unknown} data Command data.
     * @returns {{records: object[], relations: object[]}} Graph data.
     */
    #collectGraph(data) {
        const relationItems = this.#relationDataArray(data);
        const relations = relationItems.map((item, index) => this.#relationFromItem(item, index)).filter(Boolean);
        const nodeItems = this.#nodeDataArray(data);
        const records = nodeItems.map((item, index) => this.#recordFromItem(item, index)).filter(record => record.label);
        return { records, relations };
    }
    /**
     * Return arrays that should become nodes.
     *
     * @param {unknown} data Command data.
     * @returns {Array} Raw node array.
     */
    #nodeDataArray(data) {
        if (Array.isArray(data)) {
            return this.#withVisualType(data, this.#mode === "classes" ? "class" : "entity");
        }
        if (!data || typeof data !== "object") {
            return [];
        }
        if (this.#mode === "all") {
            const entityItems = this.#withVisualType(data.entities || data.nodes || [], "entity");
            const classItems = this.#withVisualType(data.classes || [], "class");
            const mixedItems = this.#withVisualType(data.results || data.matches || [], "entity");
            const combinedItems = [...entityItems, ...classItems, ...mixedItems];
            if (combinedItems.length) {
                return combinedItems;
            }
        }
        if (this.#mode === "classes" && Array.isArray(data.classes)) {
            return this.#withVisualType(data.classes, "class");
        }
        if (Array.isArray(data.entities)) {
            const entities = this.#mode === "entities"
                ? data.entities.filter(item => !this.#looksLikeClass(item))
                : data.entities;
            return this.#withVisualType(entities, "entity");
        }
        if (Array.isArray(data.nodes)) {
            const nodes = this.#mode === "entities"
                ? data.nodes.filter(item => !this.#looksLikeClass(item))
                : data.nodes;
            return this.#withVisualType(nodes, "entity");
        }
        if (Array.isArray(data.results)) {
            return this.#withVisualType(this.#mode === "entities" ? data.results.filter(item => !this.#looksLikeClass(item)) : data.results, "entity");
        }
        if (Array.isArray(data.matches)) {
            return this.#withVisualType(this.#mode === "entities" ? data.matches.filter(item => !this.#looksLikeClass(item)) : data.matches, "entity");
        }
        return Object.values(data)
            .filter(value => Array.isArray(value))
            .flat()
            .filter(item => !this.#looksLikeRelation(item))
            .map(item => this.#withVisualType([item], this.#looksLikeClass(item) ? "class" : "entity")[0]);
    }
    /**
     * Attach UI-only graph type metadata to raw records.
     *
     * @param {Array} items Raw records.
     * @param {"entity"|"class"} visualType Visual node type.
     * @returns {Array} Records carrying visual type.
     */
    #withVisualType(items, visualType) {
        if (!Array.isArray(items)) {
            return [];
        }
        return items.map(item => {
            if (!item || typeof item !== "object") {
                return item;
            }
            return {
                ...item,
                __visualType: visualType
            };
        });
    }
    /**
     * Return arrays that should become edges.
     *
     * @param {unknown} data Command data.
     * @returns {Array} Raw relation array.
     */
    #relationDataArray(data) {
        if (!data || typeof data !== "object") {
            return [];
        }
        if (Array.isArray(data.relations)) {
            return data.relations;
        }
        if (Array.isArray(data.edges)) {
            return data.edges;
        }
        if (Array.isArray(data.links)) {
            return data.links;
        }
        return Object.values(data)
            .filter(value => Array.isArray(value))
            .flat()
            .filter(item => this.#looksLikeRelation(item));
    }
    /**
     * Convert one item into a graph node record.
     *
     * @param {unknown} item Raw item.
     * @param {number} index Fallback index.
     * @returns {object} Node record.
     */
    #recordFromItem(item, index) {
        const label = this.#itemLabel(item, index);
        const sourcePath = String(item?.source_path || item?.path || item?.source || "");
        const domain = this.#domainFromRecord(item, sourcePath);
        const entityId = item?.entity_id ?? item?.id ?? "";
        return {
            id: String(entityId || this.#nodeId(domain, label, index)),
            label,
            kind: "node",
            visualType: this.#looksLikeClass(item) ? "class" : (item?.__visualType || "entity"),
            context: this.#contextFromRecord(item, sourcePath),
            classHint: String(item?.entity_class || item?.class || item?.type || item?.kind || ""),
            domain,
            entityId: String(entityId),
            source: sourcePath || String(item?.source_type || item?.source_title || "knowledge"),
            description: String(item?.description || item?.excerpt || item?.text || ""),
            confidence: item?.confidence ?? item?.score ?? "",
            raw: item
        };
    }
    /**
     * Convert one relation payload into an edge record.
     *
     * @param {unknown} item Raw item.
     * @param {number} index Fallback index.
     * @returns {object|null} Relation record.
     */
    #relationFromItem(item, index) {
        if (!item || typeof item !== "object") {
            return null;
        }
        const sourcePath = String(item?.source_path || item?.path || item?.source_file || item?.source || "");
        const domain = this.#domainFromRecord(item, sourcePath);
        const fromLabel = String(item?.subject_name || item?.source_name || item?.source_label || item?.subject || item?.from || item?.head || item?.source || item?.entity || `Origen ${index + 1}`);
        const toLabel = String(item?.object_name || item?.target_name || item?.target_label || item?.object || item?.to || item?.tail || item?.target || item?.related || `Destino ${index + 1}`);
        const label = String(item?.relation || item?.predicate || item?.label || item?.type || item?.kind || "relacion");
        const fromEntityId = item?.subject_entity_id ?? item?.source_entity_id ?? item?.from_entity_id ?? item?.head_entity_id ?? "";
        const toEntityId = item?.object_entity_id ?? item?.target_entity_id ?? item?.to_entity_id ?? item?.tail_entity_id ?? "";
        return {
            id: String(item?.id || `relation:${domain}:${fromLabel}:${label}:${toLabel}:${index}`),
            kind: "relation",
            label,
            fromLabel,
            toLabel,
            from: String(fromEntityId || this.#nodeId(domain, fromLabel)),
            to: String(toEntityId || this.#nodeId(domain, toLabel)),
            fromEntityId: String(fromEntityId),
            toEntityId: String(toEntityId),
            fromClass: String(item?.subject_class || item?.source_class || item?.from_class || ""),
            toClass: String(item?.object_class || item?.target_class || item?.to_class || ""),
            domain,
            context: this.#contextFromRecord(item, sourcePath),
            source: sourcePath || String(item?.source_type || item?.source_title || "knowledge"),
            description: String(item?.description || item?.excerpt || item?.text || ""),
            confidence: item?.confidence ?? item?.score ?? "",
            raw: item
        };
    }
    /**
     * Return whether a payload appears to represent an edge.
     *
     * @param {unknown} item Raw item.
     * @returns {boolean} True when relation-like.
     */
    #looksLikeRelation(item) {
        return Boolean(item && typeof item === "object" && (("subject" in item && "object" in item) ||
            ("source" in item && "target" in item) ||
            ("from" in item && "to" in item) ||
            ("head" in item && "tail" in item)));
    }
    /**
     * Return whether a payload appears to represent a class node.
     *
     * @param {unknown} item Raw item.
     * @returns {boolean} True when class-like.
     */
    #looksLikeClass(item) {
        if (!item || typeof item !== "object") {
            return false;
        }
        const marker = String(item.entity_type || item.node_type || item.type || item.kind || item.category || item.entity_class || item.class || "").toLowerCase();
        const identifier = String(item.entity_id || item.id || "").toLowerCase();
        return marker === "cls"
            || marker === "class"
            || marker === "clase"
            || /^cls[:_-]/.test(identifier);
    }
    /**
     * Resolve one readable item label.
     *
     * @param {unknown} item Raw item.
     * @param {number} index Fallback index.
     * @returns {string} Label.
     */
    #itemLabel(item, index) {
        if (typeof item === "string") {
            return item;
        }
        if (item && typeof item === "object") {
            return item.canonical_name || item.name || item.title || item.entity || item.id || `Nodo ${index + 1}`;
        }
        return String(item || "");
    }
    /**
     * Resolve a context label from graph metadata.
     *
     * @param {object} item Raw item.
     * @param {string} sourcePath Source path.
     * @returns {string} Context label.
     */
    #contextFromRecord(item, sourcePath) {
        if (sourcePath.includes("/")) {
            const parts = sourcePath.split("/").filter(Boolean);
            const memoryIndex = parts.indexOf("memory");
            if (memoryIndex >= 0) {
                return parts.slice(memoryIndex, -1).join("/") || "memory";
            }
            return parts.slice(0, -1).join("/") || parts[0] || "knowledge";
        }
        return String(item?.source_type || item?.domain || item?.kind || "knowledge");
    }
    /**
     * Resolve a domain from graph metadata.
     *
     * @param {object} item Raw item.
     * @param {string} sourcePath Source path.
     * @returns {string} Domain label.
     */
    #domainFromRecord(item, sourcePath) {
        if (sourcePath.includes("/")) {
            const parts = sourcePath.split("/").filter(Boolean);
            const memoryIndex = parts.indexOf("memory");
            if (memoryIndex >= 0 && parts[memoryIndex + 1]) {
                const domainParts = parts.slice(memoryIndex + 1, -1);
                return domainParts.length ? domainParts.join(".") : parts[memoryIndex + 1];
            }
            return parts[0] || "knowledge";
        }
        return String(item?.domain || item?.source_domain || item?.source_type || "knowledge");
    }
    /**
     * Prepare graph nodes and edges from current records and filters.
     *
     * @returns {void}
     */
    #prepareGraph() {
        const records = this.#filteredRecords();
        const domainGroups = new Map();
        records.forEach(record => {
            if (!domainGroups.has(record.domain)) {
                domainGroups.set(record.domain, []);
            }
            domainGroups.get(record.domain).push(record);
        });
        const domains = Array.from(domainGroups.keys()).sort();
        this.#nodes = records.map((record, index) => this.#nodeFromRecord(record, index, domains, domainGroups));
        this.#edges = this.#edgesFromRelations(records);
        this.#applyConnectivitySizing();
        this.#layoutGraphByNeighbors();
        this.#reconcileRegionEdges();
    }
    /**
     * Convert one record into a graph node.
     *
     * @param {object} record Graph record.
     * @param {number} index Global index.
     * @param {string[]} domains Domain list.
     * @param {Map<string, object[]>} domainGroups Grouped records.
     * @returns {object} Graph node.
     */
    #nodeFromRecord(record, index, domains, domainGroups) {
        const domainIndex = Math.max(domains.indexOf(record.domain), 0);
        const group = domainGroups.get(record.domain) || [];
        const localIndex = Math.max(group.findIndex(item => item.id === record.id), 0);
        const domainAngle = (Math.PI * 2 * domainIndex) / Math.max(domains.length, 1);
        const localAngle = domainAngle + (localIndex / Math.max(group.length, 1)) * 0.96;
        const radius = 130 + (localIndex % 11) * 24 + domainIndex * 10;
        return {
            ...record,
            x: Math.cos(localAngle) * radius,
            y: Math.sin(localAngle) * radius,
            radius: this.#mode === "classes" ? 15 : 11,
            color: this.#domainColor(record.domain),
            expanded: false
        };
    }
    /** Return a unique root hue and inherited tonal variation for descendants. */
    #domainColor(domain) {
        const normalized = String(domain || "knowledge").toLowerCase();
        const parts = this.#domainParts(normalized);
        const roots = [...new Set(this.#domains().map(item => this.#domainParts(item)[0]).filter(Boolean))].sort();
        const rootIndex = Math.max(roots.indexOf(parts[0]), 0);
        const hue = Math.round((206 + (rootIndex * 137.508)) % 360);
        if (parts.length <= 1) {
            return `hsl(${hue} 84% 58%)`;
        }
        const hash = [...normalized].reduce((total, character) => ((total * 31) + character.charCodeAt(0)) >>> 0, 0);
        const saturation = 68 + (hash % 17);
        const lightness = 52 + (((parts.length * 7) + (hash % 19)) % 25);
        return `hsl(${hue} ${saturation}% ${lightness}%)`;
    }
    /**
     * Build edges from relation data returned by the CLI facade.
     *
     * @param {object[]} records Current node records.
     * @returns {object[]} Edges.
     */
    #edgesFromRelations(records) {
        const nodeById = new Map(records.map(record => [record.id, record]));
        const nodeByLabel = new Map(records.map(record => [`${record.domain}:${record.label}`.toLowerCase(), record]));
        const domainRelations = this.#relations.filter(relation => this.#domainMatches(relation.domain));
        const edges = domainRelations
            .map((relation, index) => {
            const from = this.#nodeForRelationEnd(nodeById, nodeByLabel, relation, "from");
            const to = this.#nodeForRelationEnd(nodeById, nodeByLabel, relation, "to");
            if (!from || !to) {
                return null;
            }
            return {
                ...relation,
                id: relation.id || `relation-edge-${index}`,
                from: from.id,
                to: to.id
            };
        })
            .filter(Boolean);
        return edges;
    }
    /**
     * Resolve a relation endpoint against visible node records.
     *
     * @param {Map<string, object>} nodeById Visible nodes by id.
     * @param {Map<string, object>} nodeByLabel Visible nodes by domain and label.
     * @param {object} relation Relation record.
     * @param {"from"|"to"} side Endpoint side.
     * @returns {object|null} Matching node.
     */
    #nodeForRelationEnd(nodeById, nodeByLabel, relation, side) {
        const id = String(relation[side] || "");
        const entityId = side === "from" ? relation.fromEntityId : relation.toEntityId;
        const label = side === "from" ? relation.fromLabel : relation.toLabel;
        const classHint = side === "from" ? relation.fromClass : relation.toClass;
        return nodeById.get(id) ||
            nodeById.get(String(entityId || "")) ||
            nodeByLabel.get(`${relation.domain}:${label}`.toLowerCase()) ||
            nodeByLabel.get(`${relation.domain}:${classHint}`.toLowerCase()) ||
            null;
    }
    /**
     * Position nodes through neighbor expansion when relations exist, otherwise by domain grid.
     *
     * @returns {void}
     */
    #layoutGraphByNeighbors() {
        const linkedIds = new Set(this.#edges.flatMap(edge => [edge.from, edge.to]));
        const linkedNodes = this.#nodes.filter(node => linkedIds.has(node.id));
        const freeNodes = this.#nodes.filter(node => !linkedIds.has(node.id));
        if (linkedNodes.length) {
            this.#layoutConnectedNodes(linkedNodes, 0);
        }
        const startY = linkedNodes.length ? 420 : 0;
        this.#layoutDomainGrid(freeNodes, startY);
    }
    /**
     * Expand connected components by neighbor depth.
     *
     * @param {object[]} nodes Connected nodes.
     * @param {number} startY Vertical offset.
     * @returns {void}
     */
    #layoutConnectedNodes(nodes, startY) {
        const byId = new Map(nodes.map(node => [node.id, node]));
        const adjacency = this.#adjacencyMap(byId);
        const visited = new Set();
        let componentIndex = 0;
        nodes.forEach(node => {
            if (visited.has(node.id)) {
                return;
            }
            const component = this.#componentFromNode(node.id, adjacency, visited);
            const offsetX = (componentIndex % 3) * 620;
            const offsetY = startY + Math.floor(componentIndex / 3) * 460;
            this.#positionComponent(component, adjacency, byId, offsetX, offsetY);
            componentIndex += 1;
        });
    }
    /**
     * Build adjacency from visible edges.
     *
     * @param {Map<string, object>} byId Visible nodes by id.
     * @returns {Map<string, Set<string>>} Adjacency map.
     */
    #adjacencyMap(byId) {
        const adjacency = new Map([...byId.keys()].map(id => [id, new Set()]));
        this.#edges.forEach(edge => {
            if (!byId.has(edge.from) || !byId.has(edge.to)) {
                return;
            }
            adjacency.get(edge.from).add(edge.to);
            adjacency.get(edge.to).add(edge.from);
        });
        return adjacency;
    }
    /**
     * Collect one connected component.
     *
     * @param {string} rootId Component root node id.
     * @param {Map<string, Set<string>>} adjacency Adjacency map.
     * @param {Set<string>} visited Visited node ids.
     * @returns {string[]} Component ids.
     */
    #componentFromNode(rootId, adjacency, visited) {
        const queue = [rootId];
        const component = [];
        visited.add(rootId);
        while (queue.length) {
            const current = queue.shift();
            component.push(current);
            [...(adjacency.get(current) || [])].forEach(next => {
                if (!visited.has(next)) {
                    visited.add(next);
                    queue.push(next);
                }
            });
        }
        return component;
    }
    /**
     * Position one component around the highest-degree node.
     *
     * @param {string[]} component Component node ids.
     * @param {Map<string, Set<string>>} adjacency Adjacency map.
     * @param {Map<string, object>} byId Visible nodes by id.
     * @param {number} offsetX Component horizontal offset.
     * @param {number} offsetY Component vertical offset.
     * @returns {void}
     */
    #positionComponent(component, adjacency, byId, offsetX, offsetY) {
        const rootId = [...component].sort((left, right) => (adjacency.get(right)?.size || 0) - (adjacency.get(left)?.size || 0))[0];
        const levels = this.#neighborLevels(rootId, adjacency);
        [...levels.entries()].forEach(([depth, ids]) => {
            const spacing = Math.max(92, 120 - depth * 8);
            ids.forEach((id, index) => {
                const node = byId.get(id);
                if (!node) {
                    return;
                }
                node.x = offsetX + depth * 190;
                node.y = offsetY + (index - (ids.length - 1) / 2) * spacing;
            });
        });
    }
    /**
     * Group neighbor ids by breadth-first depth.
     *
     * @param {string} rootId Root node id.
     * @param {Map<string, Set<string>>} adjacency Adjacency map.
     * @returns {Map<number, string[]>} Level groups.
     */
    #neighborLevels(rootId, adjacency) {
        const levels = new Map();
        const visited = new Set([rootId]);
        const queue = [{ id: rootId, depth: 0 }];
        while (queue.length) {
            const current = queue.shift();
            if (!levels.has(current.depth)) {
                levels.set(current.depth, []);
            }
            levels.get(current.depth).push(current.id);
            [...(adjacency.get(current.id) || [])].sort().forEach(next => {
                if (!visited.has(next)) {
                    visited.add(next);
                    queue.push({ id: next, depth: current.depth + 1 });
                }
            });
        }
        return levels;
    }
    /**
     * Position unlinked nodes in a wide domain-aware grid.
     *
     * @param {object[]} nodes Free nodes.
     * @param {number} startY Vertical offset.
     * @returns {void}
     */
    #layoutDomainGrid(nodes, startY) {
        const groups = new Map();
        nodes.forEach(node => {
            if (!groups.has(node.domain)) {
                groups.set(node.domain, []);
            }
            groups.get(node.domain).push(node);
        });
        [...groups.entries()].sort(([left], [right]) => left.localeCompare(right)).forEach(([, group], groupIndex) => {
            const columns = Math.ceil(Math.sqrt(group.length));
            const offsetX = (groupIndex % 3) * 520;
            const offsetY = startY + Math.floor(groupIndex / 3) * 360;
            group.forEach((node, index) => {
                node.x = offsetX + (index % columns) * 116;
                node.y = offsetY + Math.floor(index / columns) * 94;
            });
        });
    }
    /**
     * Return records after domain, mode, and query filters.
     *
     * @returns {object[]} Filtered records.
     */
    #filteredRecords() {
        const needle = this.#query.toLowerCase();
        const visualType = this.#mode === "classes" ? "class" : this.#mode === "entities" ? "entity" : "";
        return this.#records
            .filter(record => this.#domainMatches(record.domain))
            .filter(record => !visualType || record.visualType === visualType)
            .filter(record => !needle || `${record.label} ${record.description} ${record.domain} ${record.context}`.toLowerCase().includes(needle));
    }
    /**
     * Return whether a domain is active under the selected tree node.
     *
     * @param {string} domain Domain path.
     * @returns {boolean} True when visible.
     */
    #domainMatches(domain) {
        return this.#domain === "all" || domain === this.#domain || domain.startsWith(`${this.#domain}.`);
    }
    /**
     * Return available domains from loaded records and relations.
     *
     * @returns {string[]} Domain labels.
     */
    #domains() {
        return [...new Set([
                ...this.#records.map(record => record.domain),
                ...this.#relations.map(relation => relation.domain)
            ].filter(Boolean))].sort();
    }
    /**
     * Return domain hierarchy parts.
     *
     * @param {string} domain Domain path.
     * @returns {string[]} Parts.
     */
    #domainParts(domain) {
        return String(domain || "knowledge").split(/[./\\]+/).filter(Boolean);
    }
    /**
     * Count records under one domain branch.
     *
     * @param {string} domain Domain path.
     * @returns {number} Count.
     */
    #countRecordsInDomain(domain) {
        return this.#records.filter(record => record.domain === domain || record.domain.startsWith(`${domain}.`)).length +
            this.#relations.filter(relation => relation.domain === domain || relation.domain.startsWith(`${domain}.`)).length;
    }
    /**
     * Apply local reactive filters without a new CLI call.
     *
     * @returns {void}
     */
    #applyFilters() {
        this.#readControls();
        this.#needsViewportFit = true;
        this.#prepareGraph();
        this.#render();
    }
    /**
     * Bind DOM events.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelector("[data-action='show-records']")?.addEventListener("click", () => this.#showRecords(true));
        this.querySelector("[data-action='query-records']")?.addEventListener("click", () => this.#queryRecords());
        this.querySelector("[data-action='review-deltas']")?.addEventListener("click", () => this.#reviewDeltas());
        this.querySelector("[data-action='fit-graph']")?.addEventListener("click", () => {
            this.#needsViewportFit = true;
            this.#drawCanvas();
        });
        this.querySelector("[data-action='clear-graph-focus']")?.addEventListener("click", () => {
            this.#clearGraphFocus();
        });
        this.querySelector(".filter-menu")?.addEventListener("toggle", event => {
            this.#filtersOpen = event.currentTarget.open;
        });
        this.querySelectorAll("[data-action='select-domain']").forEach(button => {
            button.addEventListener("click", () => {
                const domain = button.getAttribute("data-domain-path") || "all";
                this.#domain = domain;
                this.#resetGraphRegion();
                if (this.#expandedDomains.has(domain)) {
                    this.#expandedDomains.delete(domain);
                }
                else {
                    this.#expandedDomains.add(domain);
                }
                this.#applyFilters();
            });
        });
        this.querySelector("[data-role='kg-query']")?.addEventListener("input", () => {
            this.#readControls();
            this.#needsViewportFit = true;
            this.#prepareGraph();
            this.#drawCanvas();
            this.#renderInspector();
        });
        this.querySelector("[data-role='kg-query']")?.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                this.#queryRecords();
            }
        });
        this.querySelector("[data-role='kg-scope']")?.addEventListener("change", () => this.#showRecords(true));
        this.querySelectorAll("[data-filter-kind='kg-mode']").forEach(input => {
            input.addEventListener("change", () => this.#applyFilters());
        });
        this.#bindInspectorButtons();
    }
    /**
     * Bind inspector relation/node selection buttons.
     *
     * @returns {void}
     */
    #bindInspectorButtons() {
        this.querySelectorAll("[data-action='select-node']").forEach(button => {
            button.addEventListener("click", () => {
                const hadRegion = this.#regionNodeIds.size > 0;
                this.#selectedNodeId = button.getAttribute("data-node-id") || "";
                this.#selectedRelationId = "";
                this.#expandGraphRegion(this.#selectedNodeId);
                this.#completeRegionExpansion(hadRegion);
                this.#drawCanvas();
                this.#renderInspector();
            });
        });
        this.querySelectorAll("[data-action='select-relation']").forEach(button => {
            button.addEventListener("click", () => {
                const hadRegion = this.#regionNodeIds.size > 0;
                this.#selectedRelationId = button.getAttribute("data-relation-id") || "";
                this.#selectedNodeId = "";
                this.#expandGraphRegionFromEdge(this.#selectedRelationId);
                this.#completeRegionExpansion(hadRegion);
                this.#drawCanvas();
                this.#renderInspector();
            });
        });
    }
    /**
     * Bind canvas drawing and pointer interaction.
     *
     * @returns {void}
     */
    #bindCanvas() {
        const canvas = this.querySelector("[data-role='knowledge-canvas']");
        if (!(canvas instanceof HTMLCanvasElement)) {
            return;
        }
        this.#resizeObserver?.disconnect();
        this.#resizeObserver = new ResizeObserver(() => this.#drawCanvas());
        this.#resizeObserver.observe(canvas);
        canvas.addEventListener("pointerdown", event => this.#onPointerDown(event, canvas));
        canvas.addEventListener("pointermove", event => this.#onPointerMove(event, canvas));
        canvas.addEventListener("pointerup", event => this.#onPointerUp(event, canvas));
        canvas.addEventListener("pointerleave", event => this.#onPointerUp(event, canvas));
        canvas.addEventListener("wheel", event => this.#onWheel(event, canvas), { passive: false });
        requestAnimationFrame(() => this.#drawCanvas());
    }
    /**
     * Draw nodes and edges onto the canvas.
     *
     * @returns {void}
     */
    #drawCanvas() {
        const canvas = this.querySelector("[data-role='knowledge-canvas']");
        if (!(canvas instanceof HTMLCanvasElement)) {
            return;
        }
        const rect = canvas.getBoundingClientRect();
        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.max(1, Math.floor(rect.width * ratio));
        canvas.height = Math.max(1, Math.floor(rect.height * ratio));
        const context = canvas.getContext("2d");
        if (!context) {
            return;
        }
        if (this.#needsViewportFit) {
            this.#fitViewport(rect);
        }
        this.#updateRenderFrustum(rect);
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        context.clearRect(0, 0, rect.width, rect.height);
        this.#applyConnectivitySizing(this.#focusGraph());
        context.translate((rect.width / 2) + this.#viewport.x, (rect.height / 2) + this.#viewport.y);
        context.scale(this.#viewport.scale, this.#viewport.scale);
        this.#drawEdges(context);
        this.#drawNodes(context);
    }
    /**
     * Fit graph bounds into the canvas viewport.
     *
     * @param {DOMRect} rect Canvas bounds.
     * @returns {void}
     */
    #fitViewport(rect) {
        const focus = this.#focusGraph();
        if (focus) {
            this.#layoutFocusedRegion(focus);
        }
        const visibleNodes = focus
            ? this.#nodes.filter(node => focus.nodeIds.has(node.id))
            : this.#nodes;
        if (!visibleNodes.length) {
            this.#viewport = { x: 0, y: 0, scale: 1 };
            this.#needsViewportFit = false;
            return;
        }
        const bounds = visibleNodes.reduce((acc, node) => ({
            minX: Math.min(acc.minX, node.x - node.radius - 60),
            maxX: Math.max(acc.maxX, node.x + node.radius + 60),
            minY: Math.min(acc.minY, node.y - node.radius - 42),
            maxY: Math.max(acc.maxY, node.y + node.radius + 42)
        }), { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });
        const width = Math.max(1, bounds.maxX - bounds.minX);
        const height = Math.max(1, bounds.maxY - bounds.minY);
        const maximumScale = focus ? 1.8 : 1.15;
        const scale = Math.min(maximumScale, Math.max(0.18, Math.min((rect.width - 72) / width, (rect.height - 72) / height)));
        this.#viewport = {
            x: -((bounds.minX + bounds.maxX) / 2) * scale,
            y: -((bounds.minY + bounds.maxY) / 2) * scale,
            scale
        };
        this.#needsViewportFit = false;
    }
    /** Compute the current canvas viewport in graph coordinates. */
    #updateRenderFrustum(rect) {
        const scale = Math.max(this.#viewport.scale, 0.0001);
        const halfWidth = rect.width / (2 * scale);
        const halfHeight = rect.height / (2 * scale);
        const centerX = -this.#viewport.x / scale;
        const centerY = -this.#viewport.y / scale;
        const padding = 14 / scale;
        this.#renderFrustum = {
            left: centerX - halfWidth - padding,
            right: centerX + halfWidth + padding,
            top: centerY - halfHeight - padding,
            bottom: centerY + halfHeight + padding,
            centerX,
            centerY,
            radius: Math.hypot(halfWidth, halfHeight) + padding
        };
    }
    /** Return whether a node circle intersects the graph-space viewport. */
    #nodeIntersectsRenderFrustum(node) {
        const frustum = this.#renderFrustum;
        if (!frustum) {
            return true;
        }
        const radius = node.radius + (20 / Math.max(this.#viewport.scale, 0.0001));
        return node.x + radius >= frustum.left
            && node.x - radius <= frustum.right
            && node.y + radius >= frustum.top
            && node.y - radius <= frustum.bottom;
    }
    /** Apply endpoint, circumscribed-radius, and exact edge culling. */
    #edgeIntersectsRenderFrustum(from, to) {
        const frustum = this.#renderFrustum;
        if (!frustum) {
            return true;
        }
        if (this.#nodeIntersectsRenderFrustum(from) || this.#nodeIntersectsRenderFrustum(to)) {
            return true;
        }
        const distance = this.#pointToSegmentDistance(frustum.centerX, frustum.centerY, from.x, from.y, to.x, to.y);
        if (distance > frustum.radius) {
            return false;
        }
        return this.#segmentIntersectsFrustum(from.x, from.y, to.x, to.y, frustum);
    }
    /** Test a segment against an axis-aligned viewport using Liang-Barsky. */
    #segmentIntersectsFrustum(x1, y1, x2, y2, frustum) {
        const deltaX = x2 - x1;
        const deltaY = y2 - y1;
        const p = [-deltaX, deltaX, -deltaY, deltaY];
        const q = [x1 - frustum.left, frustum.right - x1, y1 - frustum.top, frustum.bottom - y1];
        let minimum = 0;
        let maximum = 1;
        for (let index = 0; index < 4; index += 1) {
            if (p[index] === 0) {
                if (q[index] < 0) {
                    return false;
                }
                continue;
            }
            const ratio = q[index] / p[index];
            if (p[index] < 0) {
                minimum = Math.max(minimum, ratio);
            }
            else {
                maximum = Math.min(maximum, ratio);
            }
            if (minimum > maximum) {
                return false;
            }
        }
        return true;
    }
    /**
     * Distribute an isolated region around its selected center before fitting.
     *
     * @param {{nodeIds: Set<string>, edgeIds: Set<string>}} focus Focus ids.
     * @returns {void}
     */
    #layoutFocusedRegion(focus) {
        const focusedNodes = this.#nodes.filter(node => focus.nodeIds.has(node.id));
        if (!focusedNodes.length) {
            return;
        }
        focusedNodes.forEach(node => {
            const position = this.#regionPositions.get(node.id);
            if (position) {
                node.x = position.x;
                node.y = position.y;
            }
        });
        const newNodes = focusedNodes.filter(node => !this.#regionPositions.has(node.id));
        if (!newNodes.length) {
            return;
        }
        const selectedPosition = this.#regionPositions.get(this.#selectedNodeId);
        const anchor = selectedPosition || this.#regionCentroid();
        if (!this.#regionPositions.size) {
            const selectedIndex = newNodes.findIndex(node => node.id === this.#selectedNodeId);
            const centerIndex = selectedIndex >= 0 ? selectedIndex : 0;
            const [center] = newNodes.splice(centerIndex, 1);
            center.x = 0;
            center.y = 0;
            this.#regionPositions.set(center.id, { x: 0, y: 0 });
        }
        const baseSlot = this.#regionPositions.size;
        newNodes.forEach((node, index) => {
            const slot = baseSlot + index;
            const angle = (slot * 2.399963229728653) - (Math.PI / 2);
            const radius = 120 + (Math.floor(slot / 7) * 75);
            node.x = anchor.x + (Math.cos(angle) * radius);
            node.y = anchor.y + (Math.sin(angle) * radius);
            this.#regionPositions.set(node.id, { x: node.x, y: node.y });
        });
    }
    /** Return the centroid of persisted region positions. */
    #regionCentroid() {
        const positions = [...this.#regionPositions.values()];
        if (!positions.length) {
            return { x: 0, y: 0 };
        }
        return {
            x: positions.reduce((total, position) => total + position.x, 0) / positions.length,
            y: positions.reduce((total, position) => total + position.y, 0) / positions.length
        };
    }
    /**
     * Draw graph edges.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @returns {void}
     */
    #drawEdges(context) {
        const styles = getComputedStyle(this);
        const focus = this.#focusGraph();
        const orderedEdges = focus
            ? this.#edges.filter(edge => focus.edgeIds.has(edge.id))
            : this.#edges;
        const nodesById = new Map(this.#nodes.map(node => [node.id, node]));
        const connectivity = this.#connectivityMetrics(focus);
        orderedEdges.forEach(edge => {
            const from = nodesById.get(edge.from);
            const to = nodesById.get(edge.to);
            if (!from || !to || !this.#edgeIntersectsRenderFrustum(from, to)) {
                return;
            }
            const selected = edge.id === this.#selectedRelationId || Boolean(focus?.edgeIds.has(edge.id));
            context.save();
            context.globalAlpha = 0.92;
            context.beginPath();
            context.moveTo(from.x, from.y);
            context.lineTo(to.x, to.y);
            context.strokeStyle = selected ? styles.getPropertyValue("--primary").trim() : styles.getPropertyValue("--border-strong").trim();
            context.lineWidth = selected ? 3.2 / this.#viewport.scale : 1.2 / this.#viewport.scale;
            context.stroke();
            this.#drawEdgeArrow(context, from, to, connectivity.score(from.id));
            this.#drawEdgeLabel(context, edge, from, to, selected);
            context.restore();
        });
    }
    /** Draw a subject-to-object arrowhead immediately before the target node. */
    #drawEdgeArrow(context, from, to, sourceRank) {
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const distance = Math.hypot(dx, dy);
        if (distance < 1)
            return;
        const unitX = dx / distance;
        const unitY = dy / distance;
        const scale = this.#viewport.scale;
        const tipOffset = to.radius + (3 / scale);
        const zoomFactor = 0.72 + (Math.min(scale, 2.5) * 0.28);
        const rankFactor = 0.72 + (sourceRank * 0.78);
        const arrowLength = (9 * zoomFactor * rankFactor) / scale;
        const arrowWidth = (5.2 * zoomFactor * rankFactor) / scale;
        const tipX = to.x - (unitX * tipOffset);
        const tipY = to.y - (unitY * tipOffset);
        const baseX = tipX - (unitX * arrowLength);
        const baseY = tipY - (unitY * arrowLength);
        const normalX = -unitY;
        const normalY = unitX;
        context.beginPath();
        context.moveTo(tipX, tipY);
        context.lineTo(baseX + (normalX * arrowWidth), baseY + (normalY * arrowWidth));
        context.lineTo(baseX - (normalX * arrowWidth), baseY - (normalY * arrowWidth));
        context.closePath();
        context.fillStyle = context.strokeStyle;
        context.fill();
    }
    /**
     * Draw an edge label.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @param {object} edge Edge record.
     * @param {object} from Source node.
     * @param {object} to Target node.
     * @param {boolean} selected Whether selected.
     * @returns {void}
     */
    #drawEdgeLabel(context, edge, from, to, selected) {
        if (!selected && this.#viewport.scale < 0.45) {
            return;
        }
        const styles = getComputedStyle(this);
        const x = (from.x + to.x) / 2;
        const y = (from.y + to.y) / 2;
        const label = this.#shortLabel(edge.label, selected ? 24 : 16);
        context.save();
        context.font = `${selected ? 700 : 650} ${10 / this.#viewport.scale}px Inter, system-ui, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        const width = context.measureText(label).width + 12;
        const height = 18 / this.#viewport.scale;
        context.fillStyle = styles.getPropertyValue("--surface").trim();
        context.strokeStyle = styles.getPropertyValue("--border").trim();
        this.#roundedRect(context, x - width / 2, y - height / 2, width, height, 8 / this.#viewport.scale);
        context.fill();
        context.stroke();
        context.fillStyle = selected ? styles.getPropertyValue("--primary").trim() : styles.getPropertyValue("--text-muted").trim();
        context.fillText(label, x, y);
        context.restore();
    }
    /**
     * Draw graph nodes.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @returns {void}
     */
    #drawNodes(context) {
        const styles = getComputedStyle(this);
        const focus = this.#focusGraph();
        const connectivity = this.#connectivityMetrics(focus);
        const degrees = connectivity.degrees;
        const maxDegree = Math.max(0, ...degrees.values());
        const orderedNodes = focus
            ? this.#nodes.filter(node => focus.nodeIds.has(node.id))
            : this.#nodes;
        orderedNodes.filter(node => this.#nodeIntersectsRenderFrustum(node)).forEach(node => {
            const selected = node.id === this.#selectedNodeId;
            const focused = selected || Boolean(focus?.nodeIds.has(node.id));
            const radius = selected ? node.radius + 5 : focused ? node.radius + 2 : node.radius;
            context.save();
            context.globalAlpha = 1;
            context.beginPath();
            context.arc(node.x, node.y, radius, 0, Math.PI * 2);
            context.fillStyle = selected ? styles.getPropertyValue("--primary").trim() : styles.getPropertyValue("--surface-strong").trim();
            context.strokeStyle = node.color;
            context.lineWidth = selected ? 3.4 / this.#viewport.scale : focused ? 2.6 / this.#viewport.scale : 1.8 / this.#viewport.scale;
            context.setLineDash(node.visualType === "class" ? [7 / this.#viewport.scale, 5 / this.#viewport.scale] : []);
            context.fill();
            context.stroke();
            if (this.#nodeLabelIsVisible(node, degrees, maxDegree, selected || focused)) {
                this.#drawNodeLabel(context, node, selected || focused);
            }
            if (selected && focus && this.#nodeCanExpand(node.id)) {
                this.#drawNodeExpansionBadge(context, node);
            }
            context.restore();
        });
    }
    /** Return the number of visible relations incident to each node. */
    #nodeDegrees(focus = null) {
        const visibleNodeIds = focus?.nodeIds || new Set(this.#nodes.map(node => node.id));
        const degrees = new Map([...visibleNodeIds].map(nodeId => [nodeId, 0]));
        this.#edges.forEach(edge => {
            if (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to)) {
                return;
            }
            degrees.set(edge.from, (degrees.get(edge.from) || 0) + 1);
            degrees.set(edge.to, (degrees.get(edge.to) || 0) + 1);
        });
        return degrees;
    }
    /** Return connectivity normalized against the maximum of the visible graph. */
    #connectivityMetrics(focus = this.#focusGraph()) {
        const degrees = this.#nodeDegrees(focus);
        const maxDegree = Math.max(1, ...degrees.values());
        return {
            degrees,
            maxDegree,
            score: nodeId => (degrees.get(nodeId) || 0) / maxDegree
        };
    }
    /** Scale node radii by connectivity while preserving readable bounds. */
    #applyConnectivitySizing(focus = null) {
        const connectivity = this.#connectivityMetrics(focus);
        const baseRadius = this.#mode === "classes" ? 14 : 10;
        const radiusRange = this.#mode === "classes" ? 16 : 13;
        this.#nodes.forEach(node => {
            const normalized = Math.sqrt(connectivity.score(node.id));
            node.radius = baseRadius + normalized * radiusRange;
        });
    }
    /** Decide whether a label belongs to the zoom-dependent connectivity tier. */
    #nodeLabelIsVisible(node, degrees, maxDegree, emphasized) {
        if (emphasized || this.#viewport.scale >= 0.78) {
            return true;
        }
        const normalizedRank = maxDegree ? (degrees.get(node.id) || 0) / maxDegree : 0;
        const zoomProgress = Math.max(0, Math.min(1, (this.#viewport.scale - 0.14) / 0.64));
        const easedTolerance = zoomProgress * zoomProgress * (3 - (2 * zoomProgress));
        const minimumRank = 0.56 * (1 - easedTolerance);
        return normalizedRank >= minimumRank;
    }
    /**
     * Return the current selected node/relation neighborhood.
     *
     * @returns {{nodeIds: Set<string>, edgeIds: Set<string>}|null} Focus ids.
     */
    #focusGraph() {
        if (!this.#regionNodeIds.size) {
            return null;
        }
        return {
            nodeIds: this.#regionNodeIds,
            edgeIds: this.#regionEdgeIds
        };
    }
    /** Return whether selecting a node can reveal neighbors outside the region. */
    #nodeCanExpand(nodeId) {
        return this.#edges.some(edge => {
            if (edge.from !== nodeId && edge.to !== nodeId) {
                return false;
            }
            const neighborId = edge.from === nodeId ? edge.to : edge.from;
            return !this.#regionNodeIds.has(neighborId);
        });
    }
    /** Draw a screen-stable expansion affordance above a selected node. */
    #drawNodeExpansionBadge(context, node) {
        const styles = getComputedStyle(this);
        const scale = this.#viewport.scale;
        const badgeRadius = 9 / scale;
        const x = node.x + node.radius * 0.72;
        const y = node.y - node.radius * 0.72;
        context.save();
        context.beginPath();
        context.arc(x, y, badgeRadius, 0, Math.PI * 2);
        context.fillStyle = styles.getPropertyValue("--primary").trim();
        context.strokeStyle = styles.getPropertyValue("--surface").trim();
        context.lineWidth = 2 / scale;
        context.fill();
        context.stroke();
        context.strokeStyle = styles.getPropertyValue("--on-primary").trim() || "#fff";
        context.lineWidth = 1.8 / scale;
        context.lineCap = "round";
        context.beginPath();
        context.moveTo(x - 4 / scale, y);
        context.lineTo(x + 4 / scale, y);
        context.moveTo(x, y - 4 / scale);
        context.lineTo(x, y + 4 / scale);
        context.stroke();
        context.restore();
    }
    /**
     * Add a node and its immediate neighbors to the persistent region.
     *
     * @param {string} nodeId Selected node id.
     * @returns {void}
     */
    #expandGraphRegion(nodeId) {
        if (!nodeId) {
            return;
        }
        this.#regionNodeIds.add(nodeId);
        this.#edges.forEach(edge => {
            if (edge.from !== nodeId && edge.to !== nodeId) {
                return;
            }
            this.#regionEdgeIds.add(edge.id);
            this.#regionNodeIds.add(edge.from);
            this.#regionNodeIds.add(edge.to);
        });
        this.#reconcileRegionEdges();
    }
    /** Rebuild all currently visible relations internal to the persistent region. */
    #reconcileRegionEdges() {
        this.#regionEdgeIds.clear();
        this.#edges.forEach(edge => {
            if (this.#regionNodeIds.has(edge.from) && this.#regionNodeIds.has(edge.to)) {
                this.#regionEdgeIds.add(edge.id);
            }
        });
    }
    /**
     * Add a selected relation and both endpoint neighborhoods to the region.
     *
     * @param {string} edgeId Selected edge id.
     * @returns {void}
     */
    #expandGraphRegionFromEdge(edgeId) {
        const edge = this.#edges.find(item => item.id === edgeId);
        if (!edge) {
            return;
        }
        this.#regionEdgeIds.add(edge.id);
        this.#expandGraphRegion(edge.from);
        this.#expandGraphRegion(edge.to);
    }
    /** Position additions while fitting only the first region creation. */
    #completeRegionExpansion(hadRegion) {
        const focus = this.#focusGraph();
        if (focus) {
            this.#layoutFocusedRegion(focus);
        }
        this.#needsViewportFit = !hadRegion;
    }
    /**
     * Draw a persistent node label.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @param {object} node Graph node.
     * @param {boolean} selected Whether selected.
     * @returns {void}
     */
    #drawNodeLabel(context, node, selected) {
        const styles = getComputedStyle(this);
        const label = this.#shortLabel(node.label, selected ? 28 : 18);
        const fontSize = selected ? 12 : 10;
        const x = node.x;
        const y = node.y + node.radius + (14 / this.#viewport.scale);
        context.save();
        context.font = `800 ${fontSize / this.#viewport.scale}px Inter, system-ui, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.fillStyle = node.color;
        context.shadowColor = styles.getPropertyValue("--surface").trim();
        context.shadowBlur = 4 / this.#viewport.scale;
        context.lineWidth = 3 / this.#viewport.scale;
        context.fillText(label, x, y);
        context.restore();
    }
    /**
     * Draw a rounded rectangle path.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @param {number} x X coordinate.
     * @param {number} y Y coordinate.
     * @param {number} width Width.
     * @param {number} height Height.
     * @param {number} radius Radius.
     * @returns {void}
     */
    #roundedRect(context, x, y, width, height, radius) {
        context.beginPath();
        context.moveTo(x + radius, y);
        context.lineTo(x + width - radius, y);
        context.quadraticCurveTo(x + width, y, x + width, y + radius);
        context.lineTo(x + width, y + height - radius);
        context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        context.lineTo(x + radius, y + height);
        context.quadraticCurveTo(x, y + height, x, y + height - radius);
        context.lineTo(x, y + radius);
        context.quadraticCurveTo(x, y, x + radius, y);
        context.closePath();
    }
    /**
     * Start node dragging, relation selection, or canvas panning.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    #onPointerDown(event, canvas) {
        const point = this.#canvasPoint(event, canvas);
        const node = this.#hitTestNode(point.x, point.y);
        if (node) {
            const wasSelected = this.#selectedNodeId === node.id;
            const hadRegion = this.#regionNodeIds.size > 0;
            this.#selectedNodeId = node.id;
            this.#selectedRelationId = "";
            if (wasSelected && this.#nodeCanExpand(node.id)) {
                this.#expandGraphRegion(node.id);
                this.#completeRegionExpansion(hadRegion);
                this.#animateCameraToNode(node, hadRegion ? this.#viewport.scale : Math.max(this.#viewport.scale, 1.35));
            }
            else if (wasSelected && hadRegion) {
                this.#dragNode = {
                    id: node.id,
                    offsetX: point.x - node.x,
                    offsetY: point.y - node.y
                };
                canvas.setPointerCapture(event.pointerId);
                this.#drawCanvas();
            }
            else {
                this.#animateCameraToNode(node, hadRegion ? this.#viewport.scale : Math.max(this.#viewport.scale, 1.35));
            }
            this.#renderInspector();
            return;
        }
        const edge = this.#hitTestEdge(point.x, point.y);
        if (edge) {
            const hadRegion = this.#regionNodeIds.size > 0;
            this.#selectedRelationId = edge.id;
            this.#selectedNodeId = "";
            this.#expandGraphRegionFromEdge(edge.id);
            this.#completeRegionExpansion(hadRegion);
            this.#drawCanvas();
            this.#renderInspector();
            return;
        }
        if (this.#selectedNodeId || this.#selectedRelationId) {
            this.#selectedNodeId = "";
            this.#selectedRelationId = "";
            this.#drawCanvas();
            this.#renderInspector();
            return;
        }
        this.#panState = {
            pointerId: event.pointerId,
            clientX: event.clientX,
            clientY: event.clientY,
            startX: this.#viewport.x,
            startY: this.#viewport.y
        };
        cancelAnimationFrame(this.#cameraAnimationFrame);
        this.#cameraAnimationFrame = 0;
        canvas.setPointerCapture(event.pointerId);
    }
    /** Smoothly center one node while optionally changing the camera scale. */
    #animateCameraToNode(node, targetScale) {
        cancelAnimationFrame(this.#cameraAnimationFrame);
        this.#needsViewportFit = false;
        const start = { ...this.#viewport };
        const target = {
            x: -node.x * targetScale,
            y: -node.y * targetScale,
            scale: targetScale
        };
        const startedAt = performance.now();
        const duration = 420;
        const animate = now => {
            const progress = Math.min(1, (now - startedAt) / duration);
            const eased = 1 - Math.pow(1 - progress, 3);
            this.#viewport = {
                x: start.x + (target.x - start.x) * eased,
                y: start.y + (target.y - start.y) * eased,
                scale: start.scale + (target.scale - start.scale) * eased
            };
            this.#drawCanvas();
            if (progress < 1) {
                this.#cameraAnimationFrame = requestAnimationFrame(animate);
            }
            else {
                this.#cameraAnimationFrame = 0;
            }
        };
        this.#cameraAnimationFrame = requestAnimationFrame(animate);
    }
    /**
     * Move a dragged node or pan the graph.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    #onPointerMove(event, canvas) {
        if (this.#dragNode) {
            const point = this.#canvasPoint(event, canvas);
            const node = this.#nodes.find(item => item.id === this.#dragNode.id);
            if (!node) {
                return;
            }
            node.x = point.x - this.#dragNode.offsetX;
            node.y = point.y - this.#dragNode.offsetY;
            if (this.#regionNodeIds.has(node.id)) {
                this.#regionPositions.set(node.id, { x: node.x, y: node.y });
            }
            this.#drawCanvas();
            return;
        }
        if (!this.#panState) {
            return;
        }
        this.#viewport.x = this.#panState.startX + (event.clientX - this.#panState.clientX);
        this.#viewport.y = this.#panState.startY + (event.clientY - this.#panState.clientY);
        this.#drawCanvas();
    }
    /**
     * End dragging or panning.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    #onPointerUp(event, canvas) {
        this.#dragNode = null;
        this.#panState = null;
        if (canvas.hasPointerCapture?.(event.pointerId)) {
            canvas.releasePointerCapture(event.pointerId);
        }
    }
    /**
     * Zoom the graph around the cursor.
     *
     * @param {WheelEvent} event Wheel event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    #onWheel(event, canvas) {
        event.preventDefault();
        cancelAnimationFrame(this.#cameraAnimationFrame);
        this.#cameraAnimationFrame = 0;
        const rect = canvas.getBoundingClientRect();
        const cursorX = event.clientX - rect.left - rect.width / 2;
        const cursorY = event.clientY - rect.top - rect.height / 2;
        const previousScale = this.#viewport.scale;
        const nextScale = Math.min(3.4, Math.max(0.14, previousScale * (event.deltaY > 0 ? 0.9 : 1.1)));
        const graphX = (cursorX - this.#viewport.x) / previousScale;
        const graphY = (cursorY - this.#viewport.y) / previousScale;
        this.#viewport.x = cursorX - graphX * nextScale;
        this.#viewport.y = cursorY - graphY * nextScale;
        this.#viewport.scale = nextScale;
        this.#needsViewportFit = false;
        this.#drawCanvas();
    }
    /**
     * Refresh the inspector without replacing the canvas.
     *
     * @returns {void}
     */
    #renderInspector() {
        const inspector = this.querySelector(".graph-detail-list");
        if (!inspector) {
            return;
        }
        inspector.innerHTML = this.#renderDetails();
        const backButton = this.querySelector("[data-action='clear-graph-focus']");
        if (backButton) {
            backButton.hidden = !this.#focusGraph();
        }
        this.#bindInspectorButtons();
    }
    /**
     * Restore the complete graph from any isolated node or relation level.
     *
     * @returns {void}
     */
    #clearGraphFocus() {
        this.#resetGraphRegion();
        this.#layoutGraphByNeighbors();
        this.#needsViewportFit = true;
        this.#drawCanvas();
        this.#renderInspector();
    }
    /** Clear persistent region state without rendering. */
    #resetGraphRegion() {
        this.#selectedNodeId = "";
        this.#selectedRelationId = "";
        this.#regionNodeIds.clear();
        this.#regionEdgeIds.clear();
        this.#regionPositions.clear();
    }
    /**
     * Convert viewport pointer coordinates into graph coordinates.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {{x: number, y: number}} Graph point.
     */
    #canvasPoint(event, canvas) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: (event.clientX - rect.left - rect.width / 2 - this.#viewport.x) / this.#viewport.scale,
            y: (event.clientY - rect.top - rect.height / 2 - this.#viewport.y) / this.#viewport.scale
        };
    }
    /**
     * Find a node under graph coordinates.
     *
     * @param {number} x Graph x.
     * @param {number} y Graph y.
     * @returns {object|null} Hit node.
     */
    #hitTestNode(x, y) {
        const focus = this.#focusGraph();
        const candidates = focus ? this.#nodes.filter(node => focus.nodeIds.has(node.id)) : this.#nodes;
        return [...candidates].reverse().find(node => {
            const dx = node.x - x;
            const dy = node.y - y;
            return Math.sqrt((dx * dx) + (dy * dy)) <= node.radius + (16 / this.#viewport.scale);
        }) || null;
    }
    /**
     * Find an edge near graph coordinates.
     *
     * @param {number} x Graph x.
     * @param {number} y Graph y.
     * @returns {object|null} Hit edge.
     */
    #hitTestEdge(x, y) {
        const focus = this.#focusGraph();
        const candidates = focus ? this.#edges.filter(edge => focus.edgeIds.has(edge.id)) : this.#edges;
        return [...candidates].reverse().find(edge => {
            const from = this.#nodes.find(node => node.id === edge.from);
            const to = this.#nodes.find(node => node.id === edge.to);
            if (!from || !to) {
                return false;
            }
            return this.#pointToSegmentDistance(x, y, from.x, from.y, to.x, to.y) <= 7 / this.#viewport.scale;
        }) || null;
    }
    /**
     * Distance from point to segment.
     *
     * @param {number} px Point x.
     * @param {number} py Point y.
     * @param {number} x1 Segment x1.
     * @param {number} y1 Segment y1.
     * @param {number} x2 Segment x2.
     * @param {number} y2 Segment y2.
     * @returns {number} Distance.
     */
    #pointToSegmentDistance(px, py, x1, y1, x2, y2) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        if (dx === 0 && dy === 0) {
            return Math.hypot(px - x1, py - y1);
        }
        const t = Math.max(0, Math.min(1, (((px - x1) * dx) + ((py - y1) * dy)) / ((dx * dx) + (dy * dy))));
        return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
    }
    /**
     * Build a stable node id from contextual label.
     *
     * @param {string} domain Domain.
     * @param {string} label Label.
     * @param {number} index Fallback index.
     * @returns {string} Node id.
     */
    #nodeId(domain, label, index = 0) {
        return `node:${domain}:${String(label || index).toLowerCase()}`;
    }
    /**
     * Shorten a graph label.
     *
     * @param {string} label Full label.
     * @param {number} limit Character limit.
     * @returns {string} Short label.
     */
    #shortLabel(label, limit = 14) {
        const text = String(label || "");
        return text.length > limit ? `${text.slice(0, Math.max(1, limit - 1))}...` : text;
    }
}
customElements.define(KnowledgeView.selector, KnowledgeView);

cache=(()=>{return { KnowledgeView: KnowledgeView };})();return cache;};})();
const __brainExplorerModule7=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml, renderMarkdown } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */


const DEFAULT_SOURCES = ["memory", "knowledge", "messages", "pictures"];
const DEFAULT_MECHANISMS = ["graph", "vector", "text"];
/** Render global search answers and grouped, traceable source results. */
class QueryView extends HTMLElement {
    static get selector() {
        return "brain-query-view";
    }
    #api = null;
    #state = null;
    #sources = [...DEFAULT_SOURCES];
    #mechanisms = [...DEFAULT_MECHANISMS];
    #scope = "all";
    #domain = "";
    #query = "";
    #result = null;
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        const pendingQuery = this.#state?.consumePendingQuery?.() || "";
        const options = this.#state?.consumePendingQueryOptions?.() || {};
        this.#sources = options.sources?.length ? options.sources : [...DEFAULT_SOURCES];
        this.#mechanisms = options.mechanisms?.length ? options.mechanisms : [...DEFAULT_MECHANISMS];
        if (pendingQuery) {
            this.#query = pendingQuery;
            this.#render();
            queueMicrotask(() => this.#runQuery());
            return;
        }
        this.#render();
    }
    connectedCallback() {
        this.#render();
    }
    async #runQuery() {
        const query = this.#query.trim();
        if (!query)
            return;
        this.#query = query;
        this.#result = { loading: true };
        this.#render();
        const source = this.#sources.length === 1 ? this.#sources[0] : "all";
        const mechanism = this.#mechanisms.length === 1 ? this.#mechanisms[0] : "all";
        const response = await this.#api.globalQuery({
            q: query,
            domain: this.#domain,
            source,
            mechanism,
            knowledgeScope: this.#scope,
            limit: "10",
            explain: "true",
            deep: "false"
        });
        const rawResults = Array.isArray(response.data)
            ? response.data
            : response.data?.results || response.data?.matches || [];
        const results = rawResults.filter(item => this.#sources.includes(item.source) && this.#mechanisms.includes(item.mechanism));
        this.#result = {
            ok: response.ok,
            data: { response: response.data?.response || "", results: this.#deduplicate(results) },
            stderr: response.stderr || response.error || ""
        };
        this.#state?.setLastResult(this.#result);
        this.#render();
    }
    #deduplicate(results) {
        const unique = new Map();
        results.forEach(result => {
            const key = [result.source, result.mechanism, result.path, result.title, result.text, result.excerpt].join("|");
            if (!unique.has(key))
                unique.set(key, result);
        });
        return [...unique.values()];
    }
    #render() {
        this.innerHTML = `
            <section class="page-surface search-console">
                <main class="search-results-column scroll-area">${this.#renderResult()}</main>
            </section>
        `;
        this.querySelectorAll("[data-open-picture]").forEach(button => {
            button.addEventListener("click", () => {
                this.#state?.setRouteTarget("pictures", { pictureId: button.getAttribute("data-open-picture") || "" });
            });
        });
    }
    #renderResult() {
        if (this.#result?.loading) {
            return `<div class="loading-state search-loading"><span></span><strong>Buscando en memoria, conocimiento y mensajes</strong><small>Preparando resultados...</small></div>`;
        }
        if (!this.#result) {
            return `<section class="search-empty">${icon("search")}<h2>Resultados</h2><p>Escribe una consulta en el buscador del encabezado para comenzar.</p></section>`;
        }
        const text = this.#result.data?.response || this.#firstResultText() || this.#result.stderr || "Sin salida legible.";
        return `
            <article class="answer-sheet">
                <header><span class="${this.#result.ok ? "status-pill success" : "status-pill danger"}">${this.#result.ok ? "Respuesta" : "Error"}</span></header>
                <h2>${escapeHtml(this.#query || "Consulta")}</h2>
                <div>${renderMarkdown(String(text).slice(0, 2200))}</div>
            </article>
            ${this.#renderResultGroups()}
        `;
    }
    #firstResultText() {
        const first = this.#results()[0];
        return first?.text || first?.excerpt || first?.title || "";
    }
    #results() {
        const results = this.#result?.data?.results || this.#result?.data?.matches || [];
        return Array.isArray(results) ? results : [];
    }
    #renderResultGroups() {
        const groups = new Map();
        this.#results().forEach(item => {
            const source = item.source || "unknown";
            const mechanism = item.mechanism || "unknown";
            const key = `${source}:${mechanism}`;
            if (!groups.has(key))
                groups.set(key, { source, mechanism, items: [] });
            groups.get(key).items.push(item);
        });
        if (!groups.size)
            return "";
        return `
            <section class="search-evidence" aria-label="Fuentes de la respuesta">
                <header><h3>Fuentes consultadas</h3><span>${this.#results().length} resultados</span></header>
                ${[...groups.values()].map(group => `
                    <section class="result-group">
                        <header><h4>${escapeHtml(this.#sourceLabel(group.source))}</h4><span>${escapeHtml(this.#mechanismLabel(group.mechanism))}</span></header>
                        <ol>
                            ${group.items.map(item => `
                                <li>
                                    <span class="result-order" aria-hidden="true"></span>
                                    <div class="result-copy">
                                        <strong>${escapeHtml(item.title || item.path || item.kind || "Resultado")}</strong>
                                        <p>${escapeHtml(item.excerpt || item.content?.excerpt || item.data?.excerpt || item.text || item.description || "Sin extracto disponible")}</p>
                                        <small>${escapeHtml(this.#resultOrigin(item))}</small>
                                    </div>
                                    ${item.rank !== undefined ? `<span class="result-rank" title="Relevancia">${Number(item.rank).toFixed(2)}</span>` : ""}
                                    ${item.source === "pictures" && item.data?.id ? `<button class="result-open-button" data-open-picture="${escapeHtml(item.data.id)}">Abrir</button>` : ""}
                                </li>
                            `).join("")}
                        </ol>
                    </section>
                `).join("")}
            </section>
        `;
    }
    #resultOrigin(item) {
        return item.sourceRef?.path || item.source_ref?.path || item.path || item.domain || item.kind || "Origen no especificado";
    }
    #sourceLabel(source) {
        if (source === "memory")
            return "Memoria";
        if (source === "knowledge")
            return "Conocimiento";
        if (source === "messages")
            return "Mensajes";
        if (source === "pictures")
            return "Pictures";
        return "Otros resultados";
    }
    #mechanismLabel(mechanism) {
        return mechanism === "graph" ? "Grafo" : mechanism === "vector" ? "Vectorial" : mechanism === "text" ? "Texto" : mechanism;
    }
}
customElements.define(QueryView.selector, QueryView);

cache=(()=>{return { QueryView: QueryView };})();return cache;};})();
const __brainExplorerModule8=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml, renderMarkdown } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */


/**
 * ProfilesView renders available operational profiles as a list plus one Markdown reader.
 */
class ProfilesView extends HTMLElement {
    static get selector() {
        return "brain-profiles-view";
    }
    #api = null;
    #state = null;
    #profiles = [];
    #selectedProfile = "";
    #profileText = "";
    #profileEntries = [];
    #selectedEntryKey = "";
    #editing = false;
    #loading = false;
    #pendingTarget = null;
    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#pendingTarget = this.#state?.consumeRouteTarget?.("profiles") || this.#pendingTarget;
        this.#loadProfiles();
    }
    /**
     * Initialize DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
    }
    /**
     * Load profile names.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadProfiles(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        const result = await this.#api.profiles({ forceRefresh });
        this.#state?.setLastResult(result);
        this.#profiles = Array.isArray(result.data?.profiles) ? result.data.profiles : Array.isArray(result.data) ? result.data : [];
        const target = this.#pendingTarget || this.#state?.consumeRouteTarget?.("profiles");
        this.#pendingTarget = null;
        if (target?.profile && target.profile !== this.#selectedProfile) {
            this.#profileText = "";
        }
        this.#selectedProfile = target?.profile || this.#selectedProfile || this.#profiles[0] || "";
        this.#render();
        if (this.#selectedProfile && !this.#profileText) {
            await this.#readProfile(this.#selectedProfile, forceRefresh);
        }
    }
    /**
     * Read one profile through the API facade.
     *
     * @param {string} profile Profile name.
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #readProfile(profile, forceRefresh = false) {
        if (!this.#api || !profile) {
            return;
        }
        this.#selectedProfile = profile;
        this.#loading = true;
        this.#render();
        const result = await this.#api.profileRead({ name: profile }, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#profileEntries = Array.isArray(result.data?.entries) ? result.data.entries : [];
        this.#selectedEntryKey = this.#profileEntries.some(entry => entry.key === this.#selectedEntryKey)
            ? this.#selectedEntryKey
            : this.#profileEntries[0]?.key || "";
        this.#profileText = this.#profileMarkdown(result, profile);
        this.#editing = false;
        this.#loading = false;
        this.#render();
    }
    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface profiles-console">
                <main class="structure-layout profiles-layout">
                    <aside class="structure-tree">
                        <header class="structure-panel-header">
                            <strong>Disponibles</strong>
                            <details class="action-menu">
                                <summary>${icon("more")}<span class="sr-only">Acciones</span></summary>
                                <div class="action-menu-panel">
                                    <button data-action="refresh-profiles">${icon("refresh")}Actualizar perfiles</button>
                                </div>
                            </details>
                        </header>
                        <div class="profile-list scroll-list">
                            ${this.#renderProfiles()}
                        </div>
                    </aside>
                    <section class="structure-content">
                        <div class="content-head">
                            <strong>${escapeHtml(this.#selectedProfile || "Sin perfil")}</strong>
                            <div class="profile-entry-actions">
                                ${this.#profileEntries.length ? `
                                    <select data-role="profile-entry" aria-label="Entrada del perfil">
                                        ${this.#profileEntries.map(entry => `<option value="${escapeHtml(entry.key)}" ${entry.key === this.#selectedEntryKey ? "selected" : ""}>${escapeHtml(entry.key)}</option>`).join("")}
                                    </select>
                                    ${this.#editing ? `
                                        <button class="icon-action" data-action="cancel-profile-edit" title="Cancelar edición" aria-label="Cancelar edición">${icon("close")}</button>
                                        <button class="icon-action primary-icon-action" data-action="save-profile" title="Guardar entrada" aria-label="Guardar entrada">${icon("save")}</button>
                                    ` : `<button class="icon-action" data-action="edit-profile" title="Editar entrada" aria-label="Editar entrada">${icon("edit")}</button>`}
                                ` : ""}
                            </div>
                        </div>
                        <article class="markdown-preview profile-reader scroll-area">
                            ${this.#renderProfileContent()}
                        </article>
                    </section>
                </main>
            </section>
        `;
        this.querySelector("[data-action='refresh-profiles']")?.addEventListener("click", () => this.#loadProfiles(true));
        this.querySelectorAll("[data-profile]").forEach(button => {
            button.addEventListener("click", () => this.#readProfile(button.getAttribute("data-profile") || ""));
        });
        this.querySelector("[data-role='profile-entry']")?.addEventListener("change", event => {
            this.#selectedEntryKey = event.target.value;
            this.#editing = false;
            this.#render();
        });
        this.querySelector("[data-action='edit-profile']")?.addEventListener("click", () => {
            this.#editing = true;
            this.#render();
        });
        this.querySelector("[data-action='cancel-profile-edit']")?.addEventListener("click", () => {
            this.#editing = false;
            this.#render();
        });
        this.querySelector("[data-action='save-profile']")?.addEventListener("click", () => this.#saveProfileEntry());
    }
    /**
     * Render profile rows.
     *
     * @returns {string} Profile markup.
     */
    #renderProfiles() {
        if (!this.#profiles.length) {
            return `<p class="empty-state">Sin perfiles.</p>`;
        }
        return this.#profiles.map(profile => `
            <button class="profile-row ${profile === this.#selectedProfile ? "is-active" : ""}" data-profile="${escapeHtml(profile)}">
                ${icon("users")}
                <span>
                    <strong>${escapeHtml(profile)}</strong>
                    <small>read-profile ${escapeHtml(profile)}</small>
                </span>
            </button>
        `).join("");
    }
    /**
     * Render selected profile content.
     *
     * @returns {string} HTML.
     */
    #renderProfileContent() {
        if (this.#loading) {
            return `
                <div class="loading-state">
                    <span></span>
                    <strong>Leyendo perfil</strong>
                </div>
            `;
        }
        if (!this.#selectedProfile) {
            return `<div class="knowledge-empty-state">${icon("users")}<h2>Selecciona un perfil</h2></div>`;
        }
        const entry = this.#profileEntries.find(item => item.key === this.#selectedEntryKey);
        if (this.#editing && entry) {
            return `<textarea class="profile-editor" data-role="profile-editor" aria-label="Contenido de ${escapeHtml(entry.key)}">${escapeHtml(entry.content || entry.text || "")}</textarea>`;
        }
        if (entry) {
            return renderMarkdown(entry.content || entry.text || "Sin contenido cargado.");
        }
        return renderMarkdown(this.#profileText || "Sin contenido cargado.");
    }
    /** Save the selected profile entry through the memory facade. */
    async #saveProfileEntry() {
        const editor = this.querySelector("[data-role='profile-editor']");
        const content = editor?.value ?? "";
        if (!this.#api || !this.#selectedProfile || !this.#selectedEntryKey) {
            return;
        }
        const path = `profiles.${this.#selectedProfile}.${this.#selectedEntryKey}`;
        const result = await this.#api.saveMemoryEntry(path, content);
        this.#state?.setLastResult(result);
        if (result.ok) {
            await this.#readProfile(this.#selectedProfile, true);
        }
    }
    /**
     * Convert profile JSON/stdout into Markdown.
     *
     * @param {object} result API result.
     * @param {string} profile Profile name.
     * @returns {string} Markdown.
     */
    #profileMarkdown(result, profile) {
        if (Array.isArray(result.data?.entries)) {
            return [`# Profile: ${profile}`, "", ...result.data.entries.map(entry => `## ${entry.key || entry.name || "entrada"}\n\n${entry.content || entry.text || ""}`)].join("\n");
        }
        return result.stdout || result.data?.text || result.error || result.stderr || "";
    }
}
customElements.define(ProfilesView.selector, ProfilesView);

cache=(()=>{return { ProfilesView: ProfilesView };})();return cache;};})();
const __brainExplorerModule9=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml, optionTags, renderMarkdown } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
const { StructureTree } = __brainExplorerModule18();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */



void StructureTree;
const LOG_MONTH_LABELS = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
/**
 * LogsView renders log domains as a structural tree plus one focused content pane.
 */
class LogsView extends HTMLElement {
    static get selector() {
        return "brain-logs-view";
    }
    #api = null;
    #state = null;
    #indexEntries = [];
    #logEntries = [];
    #selectedDomain = "";
    #filter = "";
    #from = "";
    #to = "";
    #hourFrom = "";
    #hourTo = "";
    #sortOrder = "desc";
    #treeMode = "domain";
    #selectedDatePath = "";
    #filtersOpen = false;
    #expandedNodes = new Set();
    #pendingTarget = null;
    #logsWithImages = [];
    #refreshTimer = null;
    #refreshInFlight = false;
    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#pendingTarget = this.#state?.consumeRouteTarget?.("logs") || this.#pendingTarget;
        this.#loadIndex();
    }
    /**
     * Initialize DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
        this.#startSilentRefresh();
    }
    /** Stop background work when the Logs route is unmounted. */
    disconnectedCallback() {
        window.clearTimeout(this.#refreshTimer);
        this.#refreshTimer = null;
    }
    /** Start a single view-owned silent refresh cycle. */
    #startSilentRefresh() {
        if (this.#refreshTimer) {
            return;
        }
        this.#scheduleSilentRefresh();
    }
    /** Schedule the next cycle one minute after the previous one completed. */
    #scheduleSilentRefresh() {
        if (!this.isConnected) {
            return;
        }
        this.#refreshTimer = window.setTimeout(() => {
            this.#refreshTimer = null;
            this.#refreshSilently();
        }, 60000);
    }
    /** Refresh the index and reload focused content only after an index change. */
    async #refreshSilently() {
        if (!this.#api || this.#refreshInFlight || document.hidden) {
            return;
        }
        this.#refreshInFlight = true;
        try {
            const indexResult = await this.#api.logIndex({}, { forceRefresh: true, silent: true });
            const nextIndexEntries = indexResult.data?.entries || [];
            if (JSON.stringify(nextIndexEntries) === JSON.stringify(this.#indexEntries)) {
                return;
            }
            this.#indexEntries = nextIndexEntries;
            if (!this.#logEntries.length || !this.#selectedDomain) {
                this.#state?.setLastResult(indexResult);
                this.#render();
                return;
            }
            const logsResult = await this.#api.logs({
                domain: this.#selectedDomain,
                date: this.#from && this.#from === this.#to ? this.#from : "",
                time: this.#hourFrom && this.#hourFrom === this.#hourTo ? this.#hourFrom : "",
                from: this.#from,
                to: this.#to
            }, { forceRefresh: true, silent: true });
            const nextLogEntries = logsResult.data?.entries || [];
            const nextImages = logsResult.hasImages || [];
            this.#state?.setLastResult(logsResult);
            this.#logEntries = nextLogEntries;
            this.#logsWithImages = nextImages;
            this.#render();
        }
        finally {
            this.#refreshInFlight = false;
            this.#scheduleSilentRefresh();
        }
    }
    /**
     * Load the log domain index.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadIndex(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        const result = await this.#api.logIndex({}, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#indexEntries = result.data?.entries || [];
        const domains = this.#domains();
        this.#selectedDomain = this.#selectedDomain || domains[0]?.path || "";
        if (this.#selectedDomain) {
            this.#expandAncestors(this.#selectedDomain);
        }
        if (await this.#applyPendingTarget()) {
            return;
        }
        this.#render();
    }
    /**
     * Apply one pending SPA target and load the matching log entry range.
     *
     * @returns {Promise<boolean>} True when a target was consumed.
     */
    async #applyPendingTarget() {
        const target = this.#pendingTarget || this.#state?.consumeRouteTarget?.("logs");
        this.#pendingTarget = null;
        if (!target) {
            return false;
        }
        this.#selectedDomain = target.domain || this.#selectedDomain;
        this.#from = target.from || target.date || this.#from;
        this.#to = target.to || target.date || this.#to || this.#from;
        this.#hourFrom = target.hourFrom || target.time || this.#hourFrom;
        this.#hourTo = target.hourTo || target.time || this.#hourTo;
        this.#sortOrder = target.sortOrder || "desc";
        this.#expandAncestors(this.#selectedDomain);
        await this.#loadLogs(true, false);
        return true;
    }
    /**
     * Load logs for the selected domain and filters.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadLogs(forceRefresh = false, readControls = true) {
        if (!this.#api) {
            return;
        }
        if (readControls) {
            this.#readFilters();
        }
        const result = await this.#api.logs({
            domain: this.#selectedDomain,
            date: this.#from && this.#from === this.#to ? this.#from : "",
            time: this.#hourFrom && this.#hourFrom === this.#hourTo ? this.#hourFrom : "",
            from: this.#from,
            to: this.#to
        }, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#logsWithImages = result.hasImages || [];
        this.#logEntries = result.data?.entries || [];
        this.#render();
    }
    /**
     * Read compact filter controls.
     *
     * @returns {void}
     */
    #readFilters() {
        this.#from = this.querySelector("[data-role='log-from']")?.value.trim() || "";
        this.#to = this.querySelector("[data-role='log-to']")?.value.trim() || "";
        this.#hourFrom = this.querySelector("[data-role='log-hour-from']")?.value.trim() || "";
        this.#hourTo = this.querySelector("[data-role='log-hour-to']")?.value.trim() || "";
        this.#sortOrder = this.querySelector("[data-role='log-order']")?.value || this.#sortOrder;
    }
    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        const entries = this.#visibleLogEntries();
        const selectedRecord = this.#recordForPath(this.#selectedDomain);
        this.innerHTML = `
            <section class="page-surface logs-console">
                <div class="structure-layout logs-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.#renderTree()}
                        </div>
                    </aside>
                    <main class="structure-content">
                        <div class="content-head logs-head">
                            <strong>${escapeHtml(this.#selectedDomain || "Indice de logs")}</strong>
                            <span>${escapeHtml(this.#logEntries.length ? `${entries.length} entradas` : (selectedRecord?.date ? "Entrada indexada" : "Selecciona dominio"))}</span>
                            <details class="action-menu filter-menu" ${this.#filtersOpen ? "open" : ""}>
                                <summary class="compact-action">${icon("filter")}<span>Filtros</span></summary>
                                <div class="action-menu-panel filter-menu-panel">
                                    <label><span>Desde</span><input data-role="log-from" value="${escapeHtml(this.#from)}" placeholder="DD-MM-YYYY"></label>
                                    <label><span>Hasta</span><input data-role="log-to" value="${escapeHtml(this.#to)}" placeholder="DD-MM-YYYY"></label>
                                    <label><span>Hora inicio</span><input data-role="log-hour-from" type="time" value="${escapeHtml(this.#hourFrom)}"></label>
                                    <label><span>Hora fin</span><input data-role="log-hour-to" type="time" value="${escapeHtml(this.#hourTo)}"></label>
                                    <label><span>Orden</span><select data-role="log-order">${optionTags(["desc", "asc"], this.#sortOrder)}</select></label>
                                    <div class="filter-menu-actions">
                                        <button data-action="clear-log-filters" class="ghost-action">${icon("filter")}Limpiar</button>
                                        <button data-action="load-logs" class="primary-action">${icon("search")}Aplicar</button>
                                    </div>
                                </div>
                            </details>
                        </div>
                        <div class="log-output log-card-list scroll-area">
                            ${this.#logEntries.length ? this.#renderLogEntries(entries) : `<p class="empty-state">Selecciona un dominio y carga su historial.</p>`}
                        </div>
                    </main>
                </div>
            </section>
        `;
        this.#bindEvents();
        this.#configureTree();
    }
    /**
     * Render parsed log entries as operational cards.
     *
     * @param {object[]} entries Visible entries.
     * @returns {string} HTML.
     */
    #renderLogEntries(entries) {
        if (!entries.length) {
            return `<p class="empty-state">No hay entradas para esos filtros.</p>`;
        }
        return entries.map(entry => `
            <details class="log-entry-card">
                <summary class="log-entry-summary">
                    <time class="log-date-badge">
                        <strong>${escapeHtml(entry.date)}</strong>
                        <span>${escapeHtml(entry.time)}</span>
                    </time>
                    <span class="log-entry-heading">
                        <strong>${escapeHtml(entry.title)}</strong>
                        <span class="log-entry-tags">
                            <span>${escapeHtml(entry.domain || this.#selectedDomain || "logs")}</span>
                            <span>${escapeHtml(entry.type || "log")}</span>
                            <span>${escapeHtml(entry.changeType || "registro")}</span>
                        </span>
                    </span>
                    <span class="log-entry-chevron">${icon("chevronDown")}</span>
                </summary>
                <div class="log-entry-body">
                    ${entry.why ? `<section><h2>Why</h2><div>${renderMarkdown(entry.why)}</div></section>` : ""}
                    ${entry.description ? `<section><h2>Description</h2><div>${renderMarkdown(entry.description)}</div></section>` : ""}
                    ${entry.impact ? `<section><h2>Impact</h2><div>${renderMarkdown(entry.impact)}</div></section>` : ""}
                    ${this.#renderPictures(entry.pictures)}
                </div>
            </details>
        `).join("");
    }
    /**
     * Render image attachments referenced by one log entry.
     *
     * @param {string[]} pictures Safe workspace picture file names.
     * @returns {string} Attachment gallery HTML.
     */
    #renderPictures(pictures = []) {
        if (!pictures.length) {
            return "";
        }
        return `
            <div class="log-entry-media" aria-label="Imagenes adjuntas">
                ${pictures.map(name => {
            const source = `/api/logs/image?name=${encodeURIComponent(name)}`;
            return `<a href="${source}" target="_blank" rel="noopener" title="Abrir imagen adjunta"><img src="${source}" alt="Imagen adjunta ${escapeHtml(name)}"></a>`;
        }).join("")}
            </div>
        `;
    }
    /**
     * Parse, sort, and filter log entries.
     *
     * @returns {object[]} Visible entries.
     */
    #visibleLogEntries() {
        const entries = this.#parseLogEntries();
        const filtered = entries.filter(entry => this.#matchesHour(entry.hourValue));
        return filtered.sort((left, right) => {
            const delta = left.timestamp - right.timestamp;
            return this.#sortOrder === "asc" ? delta : -delta;
        });
    }
    /**
     * Normalize structured log records returned by the CLI schema.
     *
     * @returns {object[]} Parsed entries.
     */
    #parseLogEntries() {
        return this.#logEntries.map((entry, index) => {
            const [date = "", ...timeParts] = String(entry.timestamp || "").split(" ");
            const time = timeParts.join(" ");
            const searchableText = [entry.title, entry.why, entry.description, entry.impact].join("\n");
            return {
                id: `log-${index}`,
                date,
                time,
                hourValue: this.#hourValue(time),
                timestamp: this.#timestamp(date, time),
                domain: entry.domain || this.#selectedDomain,
                title: entry.title || "Entrada de log",
                type: "log",
                changeType: entry.change_type || "",
                why: entry.why || "",
                description: entry.description || "",
                impact: entry.impact || "",
                pictures: this.#pictureNames(searchableText)
            };
        });
    }
    /**
     * Extract safe picture names from a log entry's Markdown fields.
     *
     * The server receives names only, never a workspace path, which prevents
     * an entry body from escaping the local pictures directory.
     *
     * @param {string} source Raw Markdown entry text.
     * @returns {string[]} Unique safe file names.
     */
    #pictureNames(source) {
        const names = new Set();
        const text = String(source || "");
        const matcher = /(?:\$agent[\\/])?pictures[\\/]([A-Za-z0-9][A-Za-z0-9._-]*\.(?:png|jpe?g|gif|webp))/gi;
        for (const match of text.matchAll(matcher)) {
            names.add(match[1]);
        }
        const taskMatcher = /#?(t\d+)\b/gi;
        for (const match of text.matchAll(taskMatcher)) {
            const taskId = match[1].toLowerCase();
            if (this.#logsWithImages.includes(taskId)) {
                names.add(`backlog-pic-${taskId}.png`);
            }
        }
        return [...names];
    }
    /**
     * Parse bold markdown fields from one log chunk.
     *
     * @param {string[]} lines Log chunk lines.
     * @returns {Record<string, string>} Field map.
     */
    #parseLogFields(lines) {
        const fields = {};
        let current = "";
        lines.forEach(line => {
            const field = line.match(/^\s*\*\*([^:*]+?)(?::)?\*\*\s*(.*)$/);
            if (field) {
                current = field[1].trim();
                fields[current] = field[2].trim();
                return;
            }
            if (!current || /^#{2,3}\s+/.test(line)) {
                return;
            }
            const text = line.trim();
            if (text) {
                fields[current] = `${fields[current] ? `${fields[current]}\n` : ""}${text}`;
            }
        });
        return fields;
    }
    /**
     * Return whether an entry hour is inside the selected range.
     *
     * @param {number} hourValue Minutes after midnight.
     * @returns {boolean} Visibility flag.
     */
    #matchesHour(hourValue) {
        const from = this.#timeInputValue(this.#hourFrom);
        const to = this.#timeInputValue(this.#hourTo);
        if (from === null && to === null) {
            return true;
        }
        if (from !== null && hourValue < from) {
            return false;
        }
        if (to !== null && hourValue > to) {
            return false;
        }
        return true;
    }
    /**
     * Convert a time input value into minutes after midnight.
     *
     * @param {string} value HH:MM value.
     * @returns {number|null} Minutes or null.
     */
    #timeInputValue(value) {
        const match = String(value || "").match(/^(\d{2}):(\d{2})$/);
        return match ? Number(match[1]) * 60 + Number(match[2]) : null;
    }
    /**
     * Convert a log time label into minutes after midnight.
     *
     * @param {string} label Log time.
     * @returns {number} Minutes.
     */
    #hourValue(label) {
        const match = String(label || "").toLowerCase().match(/(\d{1,2}):(\d{2})\s*(am|pm)?/);
        if (!match) {
            return 0;
        }
        let hour = Number(match[1]);
        const minute = Number(match[2]);
        if (match[3] === "pm" && hour < 12) {
            hour += 12;
        }
        if (match[3] === "am" && hour === 12) {
            hour = 0;
        }
        return hour * 60 + minute;
    }
    /**
     * Build a sortable timestamp from exported log labels.
     *
     * @param {string} date Date label.
     * @param {string} time Time label.
     * @returns {number} Timestamp.
     */
    #timestamp(date, time) {
        const match = String(date || "").match(/^(\d{2})-(\d{2})-(\d{4})$/);
        if (!match) {
            return 0;
        }
        const minutes = this.#hourValue(time);
        return new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1]), Math.floor(minutes / 60), minutes % 60).getTime();
    }
    /**
     * Render log domains as a collapsible tree.
     *
     * @returns {string} Tree HTML.
     */
    #renderTree() {
        return `<brain-structure-tree data-role="logs-tree"></brain-structure-tree>`;
    }
    /**
     * Render one log tree node.
     *
     * @param {object} node Tree node.
     * @param {number} depth Tree depth.
     * @returns {string} Node HTML.
     */
    #renderTreeNode(node, depth) {
        const children = Array.from(node.children.values()).sort((left, right) => left.label.localeCompare(right.label));
        const hasChildren = children.length > 0;
        const isOpen = this.#expandedNodes.has(node.path);
        const isActive = node.targetPath === this.#selectedDomain;
        if (!this.#matchesTree(node)) {
            return "";
        }
        return `
            <div class="tree-node-wrap">
                <button class="tree-node ${isActive ? "is-active" : ""}" style="--tree-depth:${depth}" data-node-path="${escapeHtml(node.targetPath)}" data-node-branch="${hasChildren ? "true" : "false"}">
                    <span class="tree-caret">${hasChildren ? icon(isOpen ? "chevronDown" : "chevronRight") : ""}</span>
                    ${icon(hasChildren ? "folder" : "document")}
                    <span>${escapeHtml(node.label)}</span>
                    ${node.command ? `<small>${escapeHtml(node.command)}</small>` : ""}
                </button>
                ${hasChildren ? `<div class="tree-children" ${isOpen ? "" : "hidden"}>${children.map(child => this.#renderTreeNode(child, depth + 1)).join("")}</div>` : ""}
            </div>
        `;
    }
    /**
     * Configure the shared tree with Log-specific toolbar and node actions.
     *
     * @returns {void}
     */
    #configureTree() {
        const treeElement = this.querySelector("[data-role='logs-tree']");
        if (!treeElement) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#treeMode === "date" ? this.#selectedDatePath : this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
            toggleOnBranchSelect: true,
            title: "Logs",
            toolbarActions: [
                { id: "tree-domain", label: "Agrupar por dominios", icon: "folder", active: this.#treeMode === "domain" },
                { id: "tree-date", label: "Agrupar por fechas", icon: "clock", active: this.#treeMode === "date" },
                { id: "refresh-index", label: "Actualizar indice", icon: "refresh" }
            ],
            sortDirection: this.#treeMode === "date" ? "desc" : "asc",
            defaultBranchIcon: "folder",
            defaultLeafIcon: "terminal",
            searchQuery: this.#filter,
            emptyText: "Sin indice cargado. Actualiza para consultar logs."
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onTreeAction(event));
        treeElement.addEventListener("brain-tree-search", event => {
            this.#filter = event.detail.query;
            const entries = this.#visibleLogEntries();
            const selectedRecord = this.#recordForPath(this.#selectedDomain);
            const countSpan = this.querySelector(".logs-head span");
            if (countSpan) {
                countSpan.textContent = this.#logEntries.length ? `${entries.length} entradas` : (selectedRecord?.date ? "Entrada indexada" : "Selecciona dominio");
            }
            const logOutput = this.querySelector(".log-output");
            if (logOutput) {
                logOutput.innerHTML = this.#logEntries.length ? this.#renderLogEntries(entries) : `<p class="empty-state">Selecciona un dominio y carga su historial.</p>`;
            }
        });
    }
    /**
     * Convert the parsed log index to shared tree nodes.
     *
     * @returns {object[]} Tree node list.
     */
    #treeNodes() {
        if (this.#treeMode === "date") {
            return this.#dateTreeNodes();
        }
        const toNode = node => {
            const children = Array.from(node.children.values())
                .filter(child => this.#matchesTree(child))
                .sort((left, right) => left.label.localeCompare(right.label))
                .map(toNode);
            const isEntry = node.leaf === true;
            return {
                id: node.path,
                path: node.targetPath,
                label: isEntry ? node.label : node.label,
                timestamp: isEntry ? [node.date, node.time].filter(Boolean).join(" ") : "",
                detail: isEntry ? node.targetPath : "",
                presentation: isEntry ? "log" : "default",
                count: !isEntry ? this.#countTreeEntries(node) : undefined,
                children,
                actions: []
            };
        };
        return Array.from(this.#buildTree().children.values())
            .filter(node => this.#matchesTree(node))
            .sort((left, right) => left.label.localeCompare(right.label))
            .map(toNode);
    }
    /**
     * Group the complete log index into year, month, day, and entry nodes.
     *
     * @returns {object[]} Shared tree nodes ordered from newest to oldest.
     */
    #dateTreeNodes() {
        const years = new Map();
        this.#indexEntries.forEach((entry, index) => {
            const [date = "", ...timeParts] = String(entry.timestamp || "").split(" ");
            const match = date.match(/^(\d{2})-(\d{2})-(\d{4})$/);
            if (!match) {
                return;
            }
            const [, day, month, year] = match;
            const time = timeParts.join(" ");
            const yearNode = this.#ensureDateGroup(years, `logs-date:${year}`, year, "folder");
            const monthNode = this.#ensureDateGroup(yearNode.children, `logs-date:${year}-${month}`, LOG_MONTH_LABELS[Number(month)] || month, "folder");
            const dayNode = this.#ensureDateGroup(monthNode.children, `logs-date:${year}-${month}-${day}`, `${day} ${LOG_MONTH_LABELS[Number(month)] || month}`, "clock");
            dayNode.entries.push({
                id: `logs-date-entry:${index}:${date}:${time}:${entry.domain || "logs"}`,
                path: `logs-date-entry:${date}:${time}:${entry.domain || "logs"}`,
                label: entry.title || "Entrada de log",
                timestamp: time,
                sortKey: String(this.#hourValue(time)).padStart(4, "0"),
                detail: entry.domain || "logs",
                presentation: "log",
                domain: entry.domain || "",
                date,
                time,
                children: []
            });
        });
        const project = group => {
            const groups = Array.from(group.children.values())
                .sort((left, right) => right.id.localeCompare(left.id))
                .map(project);
            const entries = [...group.entries].sort((left, right) => right.timestamp.localeCompare(left.timestamp));
            return {
                id: group.id,
                path: group.id,
                label: group.label,
                sortKey: group.id,
                icon: group.icon,
                count: this.#countDateEntries(group),
                sortDirection: "desc",
                children: [...groups, ...entries]
            };
        };
        return Array.from(years.values())
            .sort((left, right) => right.id.localeCompare(left.id))
            .map(project);
    }
    /**
     * Create or return one mutable date-group accumulator.
     *
     * @param {Map<string, object>} groups Sibling group map.
     * @param {string} id Stable tree identity.
     * @param {string} label Visible group label.
     * @param {string} iconName Registered icon name.
     * @returns {object} Mutable group accumulator.
     */
    #ensureDateGroup(groups, id, label, iconName) {
        if (!groups.has(id)) {
            groups.set(id, { id, label, icon: iconName, children: new Map(), entries: [] });
        }
        return groups.get(id);
    }
    /**
     * Count terminal log entries below one date group.
     *
     * @param {object} group Date-group accumulator.
     * @returns {number} Descendant entry count.
     */
    #countDateEntries(group) {
        return group.entries.length + Array.from(group.children.values())
            .reduce((total, child) => total + this.#countDateEntries(child), 0);
    }
    /**
     * Count terminal records below one parsed tree node.
     *
     * @param {object} node Parsed node.
     * @returns {number} Descendant entry count.
     */
    #countTreeEntries(node) {
        return this.#indexEntries.filter(entry => {
            const domain = String(entry.domain || "");
            return domain === node.path || domain.startsWith(`${node.path}.`);
        }).length;
    }
    /**
     * Handle selection emitted by the shared tree.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {Promise<void>} Resolves after a selected domain loads.
     */
    async #onTreeSelected(event) {
        const { path, branch, node } = event.detail;
        if (branch) {
            return;
        }
        if (this.#treeMode === "date" && node?.date) {
            this.#selectedDatePath = path;
            this.#selectedDomain = node.domain;
            this.#from = node.date;
            this.#to = node.date;
            this.#hourFrom = node.time || "";
            this.#hourTo = node.time || "";
            await this.#loadLogs(true, false);
            return;
        }
        const alreadySelected = path === this.#selectedDomain;
        this.#selectedDomain = path;
        this.#expandAncestors(path);
        const record = this.#recordForPath(path);
        if (record?.date) {
            this.#from = record.date;
            this.#to = record.date;
            this.#hourFrom = record.time || "";
            this.#hourTo = record.time || "";
        }
        if (alreadySelected && this.#logEntries.length) {
            this.#render();
            return;
        }
        await this.#loadLogs(true, !record?.date);
    }
    /**
     * Handle a Logs tree toolbar action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeToolbarAction(event) {
        if (event.detail.action === "tree-domain" || event.detail.action === "tree-date") {
            const nextMode = event.detail.action === "tree-date" ? "date" : "domain";
            if (nextMode === this.#treeMode) {
                return;
            }
            this.#treeMode = nextMode;
            this.#expandedNodes.clear();
            this.#render();
            return;
        }
        if (event.detail.action === "refresh-index") {
            this.#loadIndex(true);
        }
    }
    /**
     * Handle a contextual action for one Logs tree node.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeAction(event) {
        const node = event.detail.node;
        if (!node?.path) {
            return;
        }
        this.#selectedDomain = node.path;
        const record = this.#recordForPath(node.path);
        if (record?.date) {
            this.#from = record.date;
            this.#to = record.date;
            this.#hourFrom = record.time || "";
            this.#hourTo = record.time || "";
        }
        this.#loadLogs(true, !record?.date);
    }
    /**
     * Parse log index text into domain records.
     *
     * @returns {object[]} Log domain records.
     */
    #domains() {
        const records = [];
        for (const entry of this.#indexEntries) {
            const domain = String(entry.domain || "");
            const parts = domain.split(".").filter(Boolean);
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                const terminal = index === parts.length - 1;
                const [date = "", ...timeParts] = String(entry.timestamp || "").split(" ");
                const time = timeParts.join(" ");
                records.push({
                    path,
                    label: terminal ? (entry.title || part) : part,
                    command: terminal ? `read-log -d ${date} --time ${time}` : "",
                    date: terminal ? date : "",
                    time: terminal ? time : "",
                    leaf: false
                });
            });
        }
        return this.#dedupeRecords(records).filter(record => record.path);
    }
    /**
     * Build a dot-domain tree from parsed records.
     *
     * @returns {object} Tree root.
     */
    #buildTree() {
        const root = { label: "", path: "", targetPath: "", children: new Map(), command: "", leaf: false, entryCount: 0 };
        for (const record of this.#domains()) {
            const parts = record.path.split(".").filter(Boolean);
            let current = root;
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                if (!current.children.has(part)) {
                    current.children.set(part, {
                        label: part,
                        path,
                        targetPath: path,
                        children: new Map(),
                        command: "",
                        leaf: false,
                        entryCount: 0
                    });
                }
                current = current.children.get(part);
                if (index === parts.length - 1 && !record.leaf) {
                    current.command = record.command;
                    current.date = record.date;
                    current.time = record.time;
                    current.leaf = record.leaf;
                }
            });
            if (record.leaf) {
                current.entryCount = (current.entryCount || 0) + 1;
            }
        }
        return root;
    }
    /**
     * Format a tree leaf using the log entry identity instead of its domain.
     *
     * @param {object} record Parsed log index record.
     * @returns {string} Entry label.
     */
    #entryLabel(record) {
        return record.label;
    }
    /**
     * Extract date and time from a log-index read command.
     *
     * @param {string} command Index command text.
     * @returns {{date: string, time: string}} Parsed target.
     */
    #targetFromLogCommand(command) {
        const date = String(command || "").match(/read-log\s+-d\s+(\d{2}-\d{2}-\d{4})/);
        const time = String(command || "").match(/--time\s+(\d{1,2}:\d{2})/);
        return {
            date: date?.[1] || "",
            time: time?.[1] || ""
        };
    }
    /**
     * Find one parsed index record by path.
     *
     * @param {string} path Dot path.
     * @returns {object|null} Record or null.
     */
    #recordForPath(path) {
        return this.#domains().find(record => record.path === path) || null;
    }
    /**
     * Remove duplicate parsed records.
     *
     * @param {object[]} records Parsed records.
     * @returns {object[]} Unique records.
     */
    #dedupeRecords(records) {
        const byPath = new Map();
        records.forEach(record => byPath.set(record.path, record));
        return Array.from(byPath.values());
    }
    /**
     * Return whether a node or descendant matches the filter.
     *
     * @param {object} node Tree node.
     * @returns {boolean} Visibility flag.
     */
    #matchesTree(node) {
        const needle = this.#filter.toLowerCase();
        if (!needle) {
            return true;
        }
        if (node.path.toLowerCase().includes(needle) || node.command.toLowerCase().includes(needle)) {
            return true;
        }
        return Array.from(node.children.values()).some(child => this.#matchesTree(child));
    }
    /**
     * Expand ancestors for a selected domain.
     *
     * @param {string} path Dot domain path.
     * @returns {void}
     */
    #expandAncestors(path) {
        const parts = path.split(".");
        for (let index = 1; index <= parts.length; index += 1) {
            this.#expandedNodes.add(parts.slice(0, index).join("."));
        }
    }
    /**
     * Bind DOM events.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelector("[data-action='refresh-index']")?.addEventListener("click", () => this.#loadIndex(true));
        this.querySelectorAll("[data-action='load-logs']").forEach(button => button.addEventListener("click", () => this.#loadLogs(true)));
        this.querySelector(".filter-menu")?.addEventListener("toggle", event => {
            this.#filtersOpen = event.currentTarget.open;
        });
        this.querySelector("[data-action='clear-log-filters']")?.addEventListener("click", () => {
            this.#from = "";
            this.#to = "";
            this.#hourFrom = "";
            this.#hourTo = "";
            this.#sortOrder = "desc";
            this.#filtersOpen = true;
            this.#render();
        });
        // Filter input handled inside tree component
        this.querySelectorAll("[data-node-path]").forEach(button => button.addEventListener("click", async (event) => {
            const path = button.getAttribute("data-node-path") || "";
            const isBranch = button.getAttribute("data-node-branch") === "true";
            const wasExpanded = this.#expandedNodes.has(path);
            const clickedCaret = Boolean(event.target.closest(".tree-caret"));
            if (isBranch && clickedCaret) {
                const nextOpen = !wasExpanded;
                if (wasExpanded) {
                    this.#expandedNodes.delete(path);
                }
                else {
                    this.#expandedNodes.add(path);
                }
                const childContainer = Array.from(button.parentElement?.children || []).find(child => child.classList?.contains("tree-children"));
                if (childContainer) {
                    childContainer.hidden = !nextOpen;
                }
                const caret = button.querySelector(".tree-caret");
                if (caret) {
                    caret.innerHTML = icon(nextOpen ? "chevronDown" : "chevronRight");
                }
                return;
            }
            const alreadySelected = path === this.#selectedDomain;
            this.#selectedDomain = path;
            this.#expandAncestors(path);
            const record = this.#recordForPath(path);
            if (record?.date) {
                this.#from = record.date;
                this.#to = record.date;
                this.#hourFrom = record.time || "";
                this.#hourTo = record.time || "";
            }
            if (isBranch) {
                this.#expandedNodes.add(path);
            }
            if (alreadySelected && this.#logEntries.length) {
                this.#render();
                return;
            }
            await this.#loadLogs(true, !record?.date);
        }));
    }
}
customElements.define(LogsView.selector, LogsView);

cache=(()=>{return { LogsView: LogsView };})();return cache;};})();
const __brainExplorerModule10=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
const { BacklogPip } = __brainExplorerModule19();
const { StructureTree } = __brainExplorerModule18();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */




void StructureTree;
/**
 * BacklogView renders workspace tasks as a domain tree and focused task board.
 */
class BacklogView extends HTMLElement {
    static get selector() {
        return "brain-backlog-view";
    }
    #api = null;
    #state = null;
    #backlogSignature = "";
    #tasks = [];
    #selectedDomain = "";
    #filter = "";
    #statusFilter = new Set();
    #priorityFilter = new Set();
    #filtersOpen = false;
    #expandedNodes = new Set();
    #pipWindow = null;
    #pipComponent = null;
    #pipRequestInFlight = false;
    #tasksWithImages = [];
    #refreshTimer = null;
    #refreshInFlight = false;
    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#loadBacklog();
    }
    /**
     * Render initial DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
        this.#startSilentRefresh();
    }
    /**
     * Close the native PiP document when its source route is unmounted.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        this.#stopSilentRefresh();
        this.#closePipWindow();
    }
    /** Start the view-owned silent refresh cycle. */
    #startSilentRefresh() {
        if (this.#refreshTimer) {
            return;
        }
        this.#scheduleSilentRefresh();
    }
    /** Stop the silent refresh cycle when this route is unmounted. */
    #stopSilentRefresh() {
        window.clearTimeout(this.#refreshTimer);
        this.#refreshTimer = null;
    }
    /** Schedule the next cycle five seconds after the previous one completed. */
    #scheduleSilentRefresh() {
        if (!this.isConnected) {
            return;
        }
        this.#refreshTimer = window.setTimeout(() => {
            this.#refreshTimer = null;
            this.#refreshSilently();
        }, 60000);
    }
    /** Refresh changed tasks without overlapping requests or repainting unchanged UI. */
    async #refreshSilently() {
        if (!this.#api || this.#refreshInFlight || document.hidden) {
            return;
        }
        this.#refreshInFlight = true;
        try {
            const result = await this.#api.backlog({}, { forceRefresh: true, silent: true });
            const nextTasks = result.data?.tasks || [];
            const nextSignature = JSON.stringify(nextTasks);
            const nextImages = result.hasImages || [];
            if (nextSignature === this.#backlogSignature && JSON.stringify(nextImages) === JSON.stringify(this.#tasksWithImages)) {
                return;
            }
            this.#state?.setLastResult(result);
            this.#backlogSignature = nextSignature;
            this.#tasksWithImages = nextImages;
            this.#tasks = nextTasks;
            this.#syncPipTasks();
            this.#refreshTaskContent();
            this.#configureTree();
        }
        finally {
            this.#refreshInFlight = false;
            this.#scheduleSilentRefresh();
        }
    }
    /**
     * Load backlog text from the CLI facade.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadBacklog(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        const result = await this.#api.backlog({}, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#tasks = result.data?.tasks || [];
        this.#backlogSignature = JSON.stringify(this.#tasks);
        this.#tasksWithImages = result.hasImages || [];
        this.#syncPipTasks();
        this.#selectedDomain = this.#selectedDomain || "";
        if (this.#selectedDomain) {
            this.#expandAncestors(this.#selectedDomain);
        }
        this.#render();
    }
    /**
     * Set one task state through the CLI facade.
     *
     * @param {string} taskId Task id.
     * @param {string} status Target backlog state.
     * @returns {Promise<void>} Resolves after mutation.
     */
    async #setTaskStatus(taskId, status) {
        const action = String(status).toLowerCase();
        const result = await this.#api.updateBacklog({ action, taskId });
        this.#state?.setLastResult(result);
        if (!result.ok) {
            return;
        }
        await this.#loadBacklog(true);
    }
    /**
     * Delete one task.
     *
     * @param {string} taskId Task id.
     * @param {string} status Current task state.
     * @returns {Promise<void>} Resolves after mutation.
     */
    async #deleteTask(taskId, status) {
        const force = status !== "DONE";
        if (force && !window.confirm("La tarea sigue en curso. Eliminarla de todos modos?")) {
            return;
        }
        const result = await this.#api.updateBacklog({ action: "delete", taskId, force });
        this.#state?.setLastResult(result);
        if (!result.ok) {
            return;
        }
        await this.#loadBacklog(true);
    }
    /**
     * Add one task in the selected domain.
     *
     * @returns {Promise<void>} Resolves after mutation.
     */
    async #addTask() {
        const domain = this.querySelector("[data-role='task-domain']")?.value.trim() || this.#selectedDomain;
        const title = this.querySelector("[data-role='task-title']")?.value.trim();
        const description = this.querySelector("[data-role='task-description']")?.value.trim() || title;
        const priority = this.querySelector("[data-role='task-priority']")?.value || "HIGH";
        if (!domain || !title) {
            return;
        }
        const result = await this.#api.updateBacklog({ action: "add", domain, title, description, priority });
        this.#state?.setLastResult(result);
        this.#selectedDomain = domain;
        await this.#loadBacklog(true);
    }
    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        const domainTasks = this.#domainTasks();
        const visibleTasks = this.#visibleTasks();
        const pipSupported = this.#supportsDocumentPip();
        this.innerHTML = `
            <section class="page-surface backlog-console">
                <div class="structure-layout backlog-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.#renderTree()}
                        </div>
                    </aside>
                    <main class="structure-content">
                        <div class="content-head">
                            <strong style="display: inline-flex; align-items: center; gap: 8px;">
                                ${escapeHtml(this.#selectedDomain || "Backlog")}
                                <span class="backlog-task-count" style="font-size: 13px; font-weight: normal; color: var(--text-muted);">(${visibleTasks.length} tareas)</span>
                            </strong>
                            <div class="backlog-header-actions" style="display: flex; gap: 8px; align-items: center;">
                                <details class="action-menu filter-menu backlog-filter-menu" ${this.#filtersOpen ? "open" : ""}>
                                    <summary class="icon-action" title="Filtrar tareas" aria-label="Filtrar tareas">
                                        ${icon("filter")}
                                        <span class="backlog-filter-count" ${this.#activeFilterCount() ? "" : "hidden"}>${this.#activeFilterCount()}</span>
                                    </summary>
                                    <div class="action-menu-panel filter-menu-panel">
                                        <fieldset class="checkbox-filter-group"><legend>Estado</legend>
                                            ${[["TODO", "Pendientes"], ["WORKING", "En progreso"], ["DONE", "Completadas"]].map(([value, label]) => `<label><input type="checkbox" data-filter-kind="status" value="${value}" ${this.#statusFilter.has(value) ? "checked" : ""}><span>${label}</span></label>`).join("")}
                                        </fieldset>
                                        <fieldset class="checkbox-filter-group"><legend>Prioridad</legend>
                                            ${[["HIGH", "Alta"], ["MEDIUM", "Media"], ["LOW", "Baja"]].map(([value, label]) => `<label><input type="checkbox" data-filter-kind="priority" value="${value}" ${this.#priorityFilter.has(value) ? "checked" : ""}><span>${label}</span></label>`).join("")}
                                        </fieldset>
                                        <button data-action="clear-backlog-filters" class="ghost-action">${icon("close")}Limpiar filtros</button>
                                    </div>
                                </details>
                                <button data-action="open-create-modal" class="ghost-action compact-action" style="font-size: 13px; height: 32px; display: inline-flex; align-items: center; gap: 6px;">${icon("plus")} Crear tarea</button>
                                <button data-action="toggle-pip" class="ghost-action compact-action" style="font-size: 13px; height: 32px; display: inline-flex; align-items: center; gap: 6px;" ${pipSupported ? "" : "disabled"} title="${pipSupported ? "Abrir ventana Picture-in-Picture" : "Document Picture-in-Picture no está disponible en este navegador"}">${icon("eye")} Vista PIP</button>
                            </div>
                        </div>
                        <div class="backlog-workspace scroll-area" style="padding: 14px;">
                            <div class="task-list">
                                ${this.#renderTaskList(domainTasks)}
                                <p class="empty-state backlog-filter-empty" hidden>No hay tareas para estos filtros.</p>
                            </div>
                        </div>
                    </main>
                </div>
            </section>
            ${this.#renderModal()}
        `;
        this.#bindEvents();
        this.#configureTree();
        this.#applyTaskFiltersToDom();
    }
    #renderTaskList(visibleTasks) {
        if (!visibleTasks.length) {
            return `<p class="empty-state">No hay tareas visibles para este dominio.</p>`;
        }
        const directTasks = [];
        const subgroupMap = new Map();
        for (const task of visibleTasks) {
            if (task.domain === this.#selectedDomain) {
                directTasks.push(task);
            }
            else {
                const list = subgroupMap.get(task.domain) || [];
                list.push(task);
                subgroupMap.set(task.domain, list);
            }
        }
        const html = [];
        if (directTasks.length) {
            html.push(`
                <div class="direct-tasks-section" style="margin-bottom: 12px; display: grid; gap: 8px;">
                    ${directTasks.map(task => this.#renderTask(task)).join("")}
                </div>
            `);
        }
        const sortedDomains = Array.from(subgroupMap.keys()).sort();
        for (const domain of sortedDomains) {
            const tasks = subgroupMap.get(domain);
            const relDomain = this.#selectedDomain ? domain.slice(this.#selectedDomain.length + 1) : domain;
            html.push(`
                <details class="subdomain-group" open>
                    <summary class="subdomain-group-header">
                        ${icon("chevronRight")}
                        <strong>${escapeHtml(relDomain)}</strong>
                        <span class="subdomain-task-count">(${tasks.length} tareas)</span>
                        <span class="subdomain-line-separator"></span>
                    </summary>
                    <div class="subdomain-group-content">
                        ${tasks.map(task => this.#renderTask(task)).join("")}
                    </div>
                </details>
            `);
        }
        return html.join("");
    }
    #renderModal() {
        return `
            <dialog id="backlog-modal" class="backlog-dialog" style="border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 0; width: 720px; height: 540px; max-width: 90vw; max-height: 90vh; box-shadow: var(--shadow); background: var(--surface); color: var(--text);">
                <form method="dialog" class="backlog-modal-form" data-role="modal-form" style="display: flex; flex-direction: column; height: 100%;">
                    <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                        <strong data-role="modal-title" style="font-size: 16px; color: var(--text-strong);">Crear nueva tarea</strong>
                        <button type="button" class="icon-action close-modal-btn" data-action="close-modal" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
                    </header>
                    <div class="modal-body" style="padding: 18px; flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden;">
                        <input type="hidden" data-role="modal-task-id" value="">
                        <input type="hidden" data-role="modal-domain" value="">

                        <div class="modal-toolbar" style="display: flex; gap: 10px; align-items: center; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
                            <input type="text" data-role="modal-title-input" placeholder="Título de la tarea" required style="flex: 1; min-height: 38px;">
                            <select data-role="modal-priority" style="width: 110px; min-height: 38px;">
                                <option value="HIGH">HIGH</option>
                                <option value="MEDIUM">MEDIUM</option>
                                <option value="LOW">LOW</option>
                            </select>
                            <button type="button" data-action="open-visual-reference" class="ghost-action compact-action" style="display: inline-flex; align-items: center; gap: 6px; padding: 0 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 13px; font-weight: bold; background: var(--surface-muted); color: var(--primary); height: 38px;">
                                ${icon("camera")} Referencia Visual
                            </button>
                        </div>

                        <div style="flex: 1; display: flex; min-height: 0; margin-top: 12px;">
                            <textarea data-role="modal-description" placeholder="Escribe detalles y descripción de la tarea aquí..." required style="flex: 1; border: 0; padding: 0; outline: none; background: transparent; font-family: inherit; font-size: 14px; line-height: 1.6; resize: none; overflow-y: auto; scrollbar-width: none; -ms-overflow-style: none;"></textarea>
                        </div>
                    </div>
                    <footer class="modal-footer" style="display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding: 14px 18px; border-top: 1px solid var(--border); background: var(--surface-strong);">
                        <button type="button" class="ghost-action" data-action="close-modal">Cancelar</button>
                        <button type="submit" class="primary-action" data-role="modal-submit-btn">Crear</button>
                    </footer>
                </form>
            </dialog>

            <dialog id="visual-reference-modal" class="backlog-dialog visual-reference-dialog">
                <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong style="font-size: 16px; color: var(--text-strong);">Referencia Visual</strong>
                    <button type="button" class="icon-action close-modal-btn" data-action="close-visual-reference" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
                </header>
                <div class="modal-body visual-reference-body">
                    <div class="file-upload-zone visual-reference-upload" data-role="image-upload-zone">
                        <span class="visual-reference-label">Adjuntar Imagen / Captura (Opcional)</span>
                        <input type="file" data-role="modal-image-file" accept="image/*" class="file-input" style="display: none;">
                        <div class="image-preview-area" data-role="image-preview-area">
                            <span class="upload-placeholder" style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px;">Haga clic o arrastre una imagen aquí</span>
                        </div>
                    </div>
                </div>
                <footer class="modal-footer visual-reference-footer">
                    <button type="button" class="primary-action" data-action="close-visual-reference" style="min-width: 100px;">Listo</button>
                </footer>
            </dialog>

            <dialog id="image-viewer-modal" class="backlog-dialog" style="border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 0; width: min(800px, 95vw); box-shadow: var(--shadow); background: var(--surface); color: var(--text);">
                <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong style="font-size: 16px; color: var(--text-strong);">Vista Ampliada</strong>
                    <button type="button" class="icon-action close-modal-btn" data-action="close-image-viewer" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
                </header>
                <div class="modal-body" style="padding: 18px; display: grid; place-items: center; background: var(--bg);">
                    <img data-role="viewer-img" src="" style="max-width: 100%; max-height: 70vh; object-fit: contain; border-radius: var(--radius);">
                </div>
            </dialog>
        `;
    }
    /**
     * Determine whether this browser exposes the real Document PiP API.
     *
     * @returns {boolean} True when a user gesture can request a PiP window.
     */
    #supportsDocumentPip() {
        return typeof window.documentPictureInPicture?.requestWindow === "function";
    }
    /**
     * Open one native Document Picture-in-Picture window and mount the
     * dedicated component inside that document.
     *
     * @returns {Promise<void>} Resolves after the PiP component is mounted.
     */
    async #openPipWindow() {
        if (!this.#supportsDocumentPip() || this.#pipRequestInFlight) {
            return;
        }
        if (this.#pipWindow && !this.#pipWindow.closed) {
            this.#pipWindow.focus();
            return;
        }
        this.#pipRequestInFlight = true;
        try {
            const pipWindow = await window.documentPictureInPicture.requestWindow({
                width: 420,
                height: 620,
                disallowReturnToOpener: false,
                preferInitialWindowPlacement: true
            });
            this.#pipWindow = pipWindow;
            this.#copyStylesToPipDocument(pipWindow.document);
            pipWindow.document.title = "Backlog";
            pipWindow.document.documentElement.dataset.theme = document.documentElement.dataset.theme || "dark";
            pipWindow.document.body.className = "backlog-pip-document";
            const pipComponent = document.createElement(BacklogPip.selector);
            pipComponent.tasks = this.#tasks;
            pipComponent.onCaptureScreen = async () => {
                try {
                    const stream = await navigator.mediaDevices.getDisplayMedia({
                        video: { mediaSource: "screen" }
                    });
                    const video = document.createElement("video");
                    video.srcObject = stream;
                    video.play();
                    await new Promise(resolve => {
                        video.onloadedmetadata = () => resolve();
                    });
                    await new Promise(resolve => setTimeout(resolve, 300));
                    const canvas = document.createElement("canvas");
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    const ctx = canvas.getContext("2d");
                    ctx.drawImage(video, 0, 0);
                    stream.getTracks().forEach(track => track.stop());
                    return canvas.toDataURL("image/png");
                }
                catch (e) {
                    console.error("Screenshot capture failed:", e);
                    return null;
                }
            };
            pipComponent.onAddTask = async (taskData) => {
                const domVal = this.#selectedDomain || "Backlog";
                this.#state?.setActiveCommand(`add-task ${domVal} "${taskData.title}"`);
                try {
                    const result = await this.#api.updateBacklog({
                        action: "add",
                        domain: domVal,
                        title: taskData.title,
                        description: taskData.description,
                        priority: taskData.priority,
                        image: taskData.image
                    });
                    this.#state?.setLastResult(result);
                    if (!result.ok) {
                        return {
                            ok: false,
                            message: result.error || result.stderr || "No se pudo crear la tarea."
                        };
                    }
                    this.#selectedDomain = domVal;
                    await this.#loadBacklog(true);
                    return { ok: true, tasks: this.#tasks };
                }
                catch (error) {
                    console.error("Unable to add a task from Document PiP.", error);
                    return {
                        ok: false,
                        message: "No se pudo crear la tarea. Intenta de nuevo."
                    };
                }
            };
            pipWindow.document.body.replaceChildren(pipComponent);
            this.#pipComponent = pipComponent;
            pipWindow.addEventListener("pagehide", () => this.#releasePipWindow(pipWindow), { once: true });
        }
        catch (error) {
            console.warn("Unable to open the Document Picture-in-Picture window.", error);
        }
        finally {
            this.#pipRequestInFlight = false;
        }
    }
    /**
     * Copy the current Explorer stylesheet contract into a same-origin PiP document.
     *
     * @param {Document} pipDocument Destination document.
     * @returns {void}
     */
    #copyStylesToPipDocument(pipDocument) {
        for (const stylesheet of document.styleSheets) {
            try {
                if (stylesheet.href) {
                    const link = pipDocument.createElement("link");
                    link.rel = "stylesheet";
                    link.href = stylesheet.href;
                    pipDocument.head.appendChild(link);
                    continue;
                }
                const style = pipDocument.createElement("style");
                style.textContent = Array.from(stylesheet.cssRules, rule => rule.cssText).join("\n");
                pipDocument.head.appendChild(style);
            }
            catch (_error) {
                // Browser-owned and cross-origin stylesheets are not required by PiP.
            }
        }
    }
    /**
     * Update the mounted PiP component without re-opening its window.
     *
     * @returns {void}
     */
    #syncPipTasks() {
        if (this.#pipComponent) {
            this.#pipComponent.tasks = this.#tasks;
        }
    }
    /**
     * Release references to a PiP window that the browser closed.
     *
     * @param {Window} pipWindow Closed PiP window.
     * @returns {void}
     */
    #releasePipWindow(pipWindow) {
        if (this.#pipWindow !== pipWindow) {
            return;
        }
        this.#pipComponent?.remove();
        this.#pipComponent = null;
        this.#pipWindow = null;
    }
    /**
     * Close the active PiP window during Backlog view disposal.
     *
     * @returns {void}
     */
    #closePipWindow() {
        const pipWindow = this.#pipWindow;
        if (!pipWindow || pipWindow.closed) {
            return;
        }
        pipWindow.close();
        this.#releasePipWindow(pipWindow);
    }
    /**
     * Open the standard task composer from either the main view or PiP.
     *
     * @returns {void}
     */
    #openCreateTaskModal() {
        window.focus();
        this.querySelector("[data-action='open-create-modal']")?.click();
    }
    /**
     * Render one task.
     *
     * @param {object} task Parsed task.
     * @returns {string} HTML.
     */
    #renderTask(task) {
        let statusIcon = "";
        let statusClass = "";
        if (task.status === "DONE") {
            statusIcon = icon("checkSquare");
            statusClass = "task-status-done";
        }
        else if (task.status === "WORKING") {
            statusIcon = `
                <div class="working-spinner" title="En progreso">
                    <span class="dot dot-blue"></span>
                    <span class="dot dot-cyan"></span>
                    <span class="dot dot-green"></span>
                    <span class="dot dot-yellow"></span>
                    <span class="dot dot-red"></span>
                    <span class="dot dot-pink"></span>
                </div>
            `;
            statusClass = "task-status-working";
        }
        else {
            statusIcon = icon("clock");
            const p = String(task.priority).toUpperCase();
            if (p === "HIGH") {
                statusClass = "task-status-high";
            }
            else if (p === "MEDIUM") {
                statusClass = "task-status-medium";
            }
            else {
                statusClass = "task-status-low";
            }
        }
        const status = task.status || "TODO";
        let statusButtons = "";
        if (status === "DONE") {
            statusButtons = `<button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="TODO">${icon("clock")}Reabrir</button>`;
        }
        else if (status === "TODO") {
            statusButtons = `
                <button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="WORKING">
                    <span style="display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; margin-right: 8px; flex-shrink: 0;">
                        <span class="working-spinner" style="transform: scale(0.85); width: 14px; height: 14px; margin: 0; display: inline-block; position: relative;">
                            <span class="dot dot-blue" style="width: 3px; height: 3px;"></span>
                            <span class="dot dot-cyan" style="width: 3px; height: 3px;"></span>
                            <span class="dot dot-green" style="width: 3px; height: 3px;"></span>
                            <span class="dot dot-yellow" style="width: 3px; height: 3px;"></span>
                            <span class="dot dot-red" style="width: 3px; height: 3px;"></span>
                            <span class="dot dot-pink" style="width: 3px; height: 3px;"></span>
                        </span>
                    </span>
                    Iniciar trabajo
                </button>
                <button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="DONE">${icon("checkSquare")}Marcar hecha</button>
            `;
        }
        else if (status === "WORKING") {
            statusButtons = `
                <button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="DONE">${icon("checkSquare")}Marcar hecha</button>
                <button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="TODO">${icon("clock")}Pausar (TODO)</button>
            `;
        }
        const imageTaskId = task.id.replace(/^#/, "");
        const hasImage = this.#tasksWithImages.includes(imageTaskId);
        const imageThumbnail = hasImage
            ? `<button class="task-image-thumbnail" type="button" data-action="view-image" data-task-id="${escapeHtml(imageTaskId)}" title="Ver imagen de referencia">
                  <img src="/api/backlog/image?taskId=${escapeHtml(imageTaskId)}" alt="Referencia visual de ${escapeHtml(task.title)}">
               </button>`
            : "";
        return `
            <article class="task-row ${task.status === "DONE" ? "is-done" : ""}" data-task-row-id="${escapeHtml(task.id)}">
                <span class="task-status ${statusClass}">${statusIcon}</span>
                <div style="flex: 1; min-width: 0;">
                    <strong>${escapeHtml(task.id)} - ${escapeHtml(task.title)}</strong>
                    <p>${escapeHtml(task.description)}</p>
                </div>
                <div class="task-actions" style="display: inline-flex; align-items: center; gap: 8px; justify-self: end;">
                    ${imageThumbnail}
                    <details class="action-menu">
                        <summary class="icon-action borderless-summary" title="Opciones">${icon("more")}</summary>
                        <div class="action-menu-panel">
                            <button data-action="edit-task" data-task-id="${escapeHtml(task.id)}">${icon("edit")}Editar</button>
                            ${statusButtons}
                            <button data-action="delete-task" data-task-id="${escapeHtml(task.id)}" data-task-status="${status}" class="danger-button">${icon("trash")}Eliminar tarea</button>
                        </div>
                    </details>
                </div>
            </article>
        `;
    }
    /**
     * Render domain tree.
     *
     * @returns {string} HTML.
     */
    #renderTree() {
        return `<brain-structure-tree data-role="backlog-tree"></brain-structure-tree>`;
    }
    /**
     * Render one tree node.
     *
     * @param {object} node Tree node.
     * @param {number} depth Tree depth.
     * @returns {string} HTML.
     */
    #renderTreeNode(node, depth) {
        const children = Array.from(node.children.values()).sort((left, right) => left.label.localeCompare(right.label));
        const hasChildren = children.length > 0;
        const isOpen = this.#expandedNodes.has(node.path);
        const isActive = node.path === this.#selectedDomain;
        const count = this.#tasks.filter(task => task.domain === node.path || task.domain.startsWith(`${node.path}.`)).length;
        if (!this.#matchesNode(node)) {
            return "";
        }
        return `
            <div class="tree-node-wrap">
                <button class="tree-node ${isActive ? "is-active" : ""}" style="--tree-depth:${depth}" data-node-path="${escapeHtml(node.path)}" data-node-branch="${hasChildren ? "true" : "false"}">
                    <span class="tree-caret">${hasChildren ? icon(isOpen ? "chevronDown" : "chevronRight") : ""}</span>
                    ${icon(hasChildren ? "folder" : "checkSquare")}
                    <span>${escapeHtml(node.label)}</span>
                    <small>${escapeHtml(String(count))}</small>
                </button>
                ${hasChildren && isOpen ? `<div class="tree-children">${children.map(child => this.#renderTreeNode(child, depth + 1)).join("")}</div>` : ""}
            </div>
        `;
    }
    /**
     * Configure the shared Backlog domain tree.
     *
     * @returns {void}
     */
    #configureTree() {
        const treeElement = this.querySelector("[data-role='backlog-tree']");
        if (!treeElement) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
            toggleOnBranchSelect: true,
            title: "Backlog",
            toolbarActions: [
                { id: "new-domain", label: "Nuevo dominio", icon: "plus" },
                { id: "refresh", label: "Actualizar backlog", icon: "refresh" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "checkSquare",
            searchQuery: this.#filter,
            emptyText: "Sin dominios de backlog. Actualiza para cargar tareas."
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onTreeAction(event));
        treeElement.addEventListener("brain-tree-search", event => {
            this.#filter = event.detail.query;
            this.#refreshTaskContent();
        });
    }
    /**
     * Convert the task domain tree into shared nodes.
     *
     * @returns {object[]} Tree node list.
     */
    #treeNodes() {
        const toNode = node => {
            const children = Array.from(node.children.values())
                .filter(child => this.#matchesNode(child))
                .sort((left, right) => left.label.localeCompare(right.label))
                .map(toNode);
            const count = this.#tasks.filter(task => (task.domain === node.path || task.domain.startsWith(`${node.path}.`))
                && this.#matchesActiveTaskFilters(task)).length;
            return {
                id: node.path,
                path: node.path,
                label: node.label,
                count,
                children,
                actions: []
            };
        };
        return Array.from(this.#buildTree().children.values())
            .filter(node => this.#matchesNode(node))
            .sort((left, right) => left.label.localeCompare(right.label))
            .map(toNode);
    }
    /**
     * Select one Backlog domain without refetching its tree.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeSelected(event) {
        if (event.detail.branch && event.detail.clickedCaret) {
            return;
        }
        this.#selectedDomain = event.detail.path;
        this.#expandAncestors(event.detail.path);
        this.#render();
    }
    /**
     * Handle global Backlog tree actions.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeToolbarAction(event) {
        if (event.detail.action === "new-domain") {
            const newDomain = prompt("Introduce el nombre del nuevo dominio (ej. mi.nuevo.dominio):");
            if (newDomain && newDomain.trim()) {
                const requestedDomain = newDomain.trim();
                const targetDomain = this.#selectedDomain && !requestedDomain.includes(".")
                    ? `${this.#selectedDomain}.${requestedDomain}`
                    : requestedDomain;
                const dialog = this.querySelector("#backlog-modal");
                if (dialog) {
                    this.querySelector("[data-role='modal-task-id']").value = "";
                    const domInput = this.querySelector("[data-role='modal-domain']");
                    domInput.value = targetDomain;
                    domInput.removeAttribute("disabled");
                    this.querySelector("[data-role='modal-title-input']").value = "";
                    this.querySelector("[data-role='modal-description']").value = "";
                    this.querySelector("[data-role='modal-priority']").value = "HIGH";
                    this.#markingRects = [];
                    const imgInput = this.querySelector("[data-role='modal-image-file']");
                    if (imgInput)
                        imgInput.value = "";
                    const previewArea = this.querySelector("[data-role='image-preview-area']");
                    if (previewArea) {
                        previewArea.innerHTML = `<span class="upload-placeholder" style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px;">Haga clic o arrastre una imagen aquí</span>`;
                    }
                    this.#setVisualReferenceHasImage(false);
                    this.querySelector("[data-role='modal-title']").textContent = `Crear nueva tarea en ${newDomain.trim()}`;
                    this.querySelector("[data-role='modal-submit-btn']").textContent = "Crear";
                    dialog.showModal();
                }
            }
        }
        else if (event.detail.action === "refresh") {
            this.#loadBacklog(true);
        }
    }
    /**
     * Handle contextual Backlog item actions.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeAction(event) {
        const node = event.detail.node;
        if (!node?.path) {
            return;
        }
        this.#selectedDomain = node.path;
        this.#expandAncestors(node.path);
        this.#render();
    }
    /**
     * Return tasks owned by the selected domain subtree.
     *
     * @returns {object[]} Domain-scoped tasks.
     */
    #domainTasks() {
        return this.#tasks
            .filter(task => !this.#selectedDomain || task.domain === this.#selectedDomain || task.domain.startsWith(`${this.#selectedDomain}.`));
    }
    /**
     * Return visible tasks for the selected domain and local content filters.
     *
     * @returns {object[]} Visible tasks.
     */
    #visibleTasks() {
        const needle = this.#filter.toLowerCase();
        return this.#domainTasks()
            .filter(task => !needle || `${task.domain} ${task.title} ${task.description} ${task.id}`.toLowerCase().includes(needle))
            .filter(task => !this.#statusFilter.size || this.#statusFilter.has(task.status))
            .filter(task => !this.#priorityFilter.size || this.#priorityFilter.has(String(task.priority).toUpperCase()));
    }
    /**
     * Count active task-list filters for the toolbar indicator.
     *
     * @returns {number} Number of non-default filters.
     */
    #activeFilterCount() {
        return this.#statusFilter.size + this.#priorityFilter.size;
    }
    /**
     * Refresh the task panel after a local filter change without rebuilding
     * the structural tree or issuing a CLI request.
     *
     * @returns {void}
     */
    #refreshTaskContent() {
        const visibleTasks = this.#visibleTasks();
        this.#applyTaskFiltersToDom();
        const countSpan = this.querySelector(".backlog-task-count");
        if (countSpan) {
            countSpan.textContent = `(${visibleTasks.length} tareas)`;
        }
        const filterCount = this.querySelector(".backlog-filter-count");
        if (filterCount) {
            const activeCount = this.#activeFilterCount();
            filterCount.textContent = String(activeCount);
            filterCount.toggleAttribute("hidden", activeCount === 0);
        }
    }
    /**
     * Toggle mounted task rows and groups for the active local filters.
     * Existing row controls keep their listeners because no row is recreated.
     *
     * @returns {void}
     */
    #applyTaskFiltersToDom() {
        const domainTasks = this.#domainTasks();
        const visibleIds = new Set(this.#visibleTasks().map(task => task.id));
        this.querySelectorAll("[data-task-row-id]").forEach(row => {
            row.toggleAttribute("hidden", !visibleIds.has(row.getAttribute("data-task-row-id") || ""));
        });
        this.querySelectorAll(".direct-tasks-section, .subdomain-group").forEach(group => {
            const hasVisibleRows = Array.from(group.querySelectorAll("[data-task-row-id]")).some(row => !row.hidden);
            group.toggleAttribute("hidden", !hasVisibleRows);
        });
        const emptyState = this.querySelector(".backlog-filter-empty");
        if (emptyState) {
            emptyState.toggleAttribute("hidden", domainTasks.length === 0 || visibleIds.size > 0);
        }
    }
    /**
     * Build tree from task domains.
     *
     * @returns {object} Tree root.
     */
    #buildTree() {
        const root = { label: "", path: "", children: new Map() };
        for (const domain of this.#domains()) {
            const parts = domain.split(".").filter(Boolean);
            let current = root;
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                if (!current.children.has(part)) {
                    current.children.set(part, { label: part, path, children: new Map() });
                }
                current = current.children.get(part);
            });
        }
        return root;
    }
    /**
     * Return unique task domains.
     *
     * @returns {string[]} Domain list.
     */
    #domains() {
        return [...new Set(this.#tasks.map(task => task.domain).filter(Boolean))].sort();
    }
    /**
     * Return whether a node should be visible.
     *
     * @param {object} node Tree node.
     * @returns {boolean} Visibility flag.
     */
    #matchesNode(node) {
        return this.#tasks.some(task => (task.domain === node.path || task.domain.startsWith(`${node.path}.`))
            && this.#matchesActiveTaskFilters(task));
    }
    /**
     * Return whether a task satisfies the toolbar state and priority filters.
     *
     * @param {object} task Backlog task.
     * @returns {boolean} Filter match.
     */
    #matchesActiveTaskFilters(task) {
        const matchesStatus = !this.#statusFilter.size || this.#statusFilter.has(task.status);
        const matchesPriority = !this.#priorityFilter.size
            || this.#priorityFilter.has(String(task.priority).toUpperCase());
        return matchesStatus && matchesPriority;
    }
    /**
     * Expand ancestors for one domain path.
     *
     * @param {string} domain Domain path.
     * @returns {void}
     */
    #expandAncestors(domain) {
        const parts = domain.split(".");
        for (let index = 1; index < parts.length; index += 1) {
            this.#expandedNodes.add(parts.slice(0, index).join("."));
        }
    }
    #markingRects = [];
    #labelDraft = "";
    #displayImageToMark(dataUrl) {
        const previewArea = this.querySelector("[data-role='image-preview-area']");
        if (!previewArea)
            return;
        this.#setVisualReferenceHasImage(true);
        this.#markingRects = [];
        this.#selectedMarkIndex = -1;
        this.#labelDraft = "";
        previewArea.innerHTML = `
            <div class="marking-container">
                <img data-role="preview-img-element" src="${dataUrl}">
                <svg id="marking-svg" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; cursor: crosshair; touch-action: none;"></svg>
            </div>
            <details class="marking-toolbar-pill">
                <summary>${icon("edit")}<span>Marcas</span>${icon("chevronDown")}</summary>
                <div class="marking-toolbar">
                    <label class="mark-color-control"><span>Color</span><input type="color" data-action="change-mark-color" value="#ff3b30" aria-label="Color de marca"></label>
                    <button type="button" class="mark-delete-control" data-action="delete-selected-mark" title="Eliminar marca seleccionada" aria-label="Eliminar marca seleccionada" disabled>${icon("trash")}</button>
                    <label class="mark-shape-control"><span>Forma</span><select data-action="change-mark-shape"><option value="rectangle">Rectángulo</option><option value="arrow">Flecha</option><option value="path">Trazo</option><option value="label">LABEL</option></select></label>
                    <label class="mark-label-control"><span>Etiqueta</span><input type="text" data-action="change-mark-label" placeholder="Texto para LABEL"></label>
                </div>
            </details>
        `;
        this.#bindImageMarking();
    }
    /** Synchronize empty and loaded states of the visual-reference drop area. */
    #setVisualReferenceHasImage(hasImage) {
        this.querySelector("[data-role='image-upload-zone']")?.classList.toggle("has-image", hasImage);
        this.querySelector("[data-role='image-preview-area']")?.classList.toggle("has-image", hasImage);
        const fileInput = this.querySelector("[data-role='modal-image-file']");
        if (fileInput instanceof HTMLInputElement) {
            fileInput.disabled = hasImage;
        }
    }
    #bindImageMarking() {
        const svg = this.querySelector("#marking-svg");
        if (!svg)
            return;
        let interaction = null;
        const point = event => {
            const bounds = svg.getBoundingClientRect();
            return { x: (event.clientX - bounds.left) / bounds.width, y: (event.clientY - bounds.top) / bounds.height, bounds };
        };
        svg.addEventListener("pointerdown", event => {
            event.preventDefault();
            const start = point(event);
            const target = event.target.closest?.("[data-mark-index]");
            if (target) {
                const index = Number(target.getAttribute("data-mark-index"));
                this.#selectedMarkIndex = index;
                interaction = { mode: "drag", index, start, original: structuredClone(this.#markingRects[index]) };
                svg.setPointerCapture(event.pointerId);
                this.#renderImageMarks(svg);
                return;
            }
            const type = this.querySelector("[data-action='change-mark-shape']")?.value || "rectangle";
            const color = this.querySelector("[data-action='change-mark-color']")?.value || "#ff3b30";
            if (type === "label") {
                const labelInput = this.querySelector("[data-action='change-mark-label']");
                const label = labelInput?.value.trim() || "";
                if (!label) {
                    labelInput?.focus();
                    return;
                }
                this.#markingRects.push({ type, x: start.x, y: start.y, w: 0, h: 0, points: null, color, label });
                this.#selectedMarkIndex = this.#markingRects.length - 1;
                this.#labelDraft = label;
                this.#renderImageMarks(svg);
                return;
            }
            const index = this.#markingRects.length;
            const draft = {
                type,
                x: start.x,
                y: start.y,
                w: 0,
                h: 0,
                points: type === "path" ? [{ x: start.x, y: start.y }] : null,
                color,
                label: String(this.#shapeMarkCount() + 1)
            };
            this.#markingRects.push(draft);
            this.#selectedMarkIndex = index;
            interaction = { mode: "draw", index, start, type };
            svg.setPointerCapture(event.pointerId);
            this.#renderImageMarks(svg);
        });
        svg.addEventListener("pointermove", event => {
            if (!interaction)
                return;
            const current = point(event);
            if (interaction.mode === "drag") {
                const dx = current.x - interaction.start.x;
                const dy = current.y - interaction.start.y;
                const mark = { ...interaction.original, x: interaction.original.x + dx, y: interaction.original.y + dy };
                if (mark.points)
                    mark.points = interaction.original.points.map(item => ({ x: item.x + dx, y: item.y + dy }));
                this.#markingRects[interaction.index] = mark;
                this.#renderImageMarks(svg);
            }
            else {
                const mark = this.#markingRects[interaction.index];
                mark.w = current.x - interaction.start.x;
                mark.h = current.y - interaction.start.y;
                if (interaction.type === "path") {
                    mark.points.push({ x: current.x, y: current.y });
                }
                this.#renderImageMarks(svg);
            }
        });
        svg.addEventListener("pointerup", event => {
            if (!interaction)
                return;
            const current = point(event);
            if (interaction.mode === "draw") {
                const dx = current.x - interaction.start.x;
                const dy = current.y - interaction.start.y;
                const mark = this.#markingRects[interaction.index];
                mark.w = dx;
                mark.h = dy;
                const valid = interaction.type === "path" ? mark.points.length > 2 : Math.hypot(dx, dy) > 0.01;
                if (!valid) {
                    this.#markingRects.splice(interaction.index, 1);
                    this.#selectedMarkIndex = -1;
                    this.#renumberShapeMarks();
                }
            }
            interaction = null;
            svg.releasePointerCapture?.(event.pointerId);
            this.#renderImageMarks(svg);
        });
        this.querySelector("[data-action='delete-selected-mark']")?.addEventListener("click", e => {
            e.stopPropagation();
            if (this.#selectedMarkIndex < 0 || this.#selectedMarkIndex >= this.#markingRects.length)
                return;
            this.#markingRects.splice(this.#selectedMarkIndex, 1);
            this.#selectedMarkIndex = -1;
            this.#renumberShapeMarks();
            this.#renderImageMarks(svg);
        });
        this.querySelector("[data-action='change-mark-color']")?.addEventListener("input", event => {
            if (this.#selectedMarkIndex < 0)
                return;
            this.#markingRects[this.#selectedMarkIndex].color = event.currentTarget.value;
            this.#renderImageMarks(svg);
        });
        this.querySelector("[data-action='change-mark-label']")?.addEventListener("input", event => {
            this.#labelDraft = event.currentTarget.value;
            const selected = this.#markingRects[this.#selectedMarkIndex];
            if (selected?.type === "label") {
                selected.label = event.currentTarget.value;
                this.#renderImageMarks(svg);
            }
        });
    }
    #selectedMarkIndex = -1;
    /** Return the number of geometric marks, excluding standalone labels. */
    #shapeMarkCount() {
        return this.#markingRects.filter(mark => mark.type !== "label").length;
    }
    /** Keep geometric mark numbers sequential without consuming LABEL entries. */
    #renumberShapeMarks() {
        let number = 0;
        for (const mark of this.#markingRects) {
            if (mark.type !== "label") {
                number += 1;
                mark.label = String(number);
            }
        }
    }
    /** Render normalized mark geometry into the interactive SVG overlay. */
    #renderImageMarks(svg) {
        const bounds = svg.getBoundingClientRect();
        const width = bounds.width || 1;
        const height = bounds.height || 1;
        const markup = this.#markingRects.map((mark, index) => {
            const selected = index === this.#selectedMarkIndex ? " is-selected" : "";
            const common = `data-mark-index="${index}" class="${selected}" stroke="${mark.color}" stroke-width="3" fill="none" vector-effect="non-scaling-stroke"`;
            let shape = "";
            if (mark.type === "label") {
                return `<text data-mark-index="${index}" class="mark-standalone-label${selected}" x="${mark.x * width}" y="${mark.y * height}" fill="${mark.color}" font-size="16" font-weight="800" dominant-baseline="hanging">${escapeHtml(mark.label)}</text>`;
            }
            else if (mark.type === "arrow") {
                const x1 = mark.x * width, y1 = mark.y * height, x2 = (mark.x + mark.w) * width, y2 = (mark.y + mark.h) * height;
                const angle = Math.atan2(y2 - y1, x2 - x1), size = 12;
                const points = `${x2},${y2} ${x2 - size * Math.cos(angle - .45)},${y2 - size * Math.sin(angle - .45)} ${x2 - size * Math.cos(angle + .45)},${y2 - size * Math.sin(angle + .45)}`;
                shape = `<line ${common} x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/><polygon ${common} points="${points}" fill="${mark.color}"/>`;
            }
            else if (mark.type === "path") {
                shape = `<polyline ${common} points="${mark.points.map(item => `${item.x * width},${item.y * height}`).join(" ")}"/>`;
            }
            else {
                const x = Math.min(mark.x, mark.x + mark.w) * width, y = Math.min(mark.y, mark.y + mark.h) * height;
                shape = `<rect ${common} x="${x}" y="${y}" width="${Math.abs(mark.w) * width}" height="${Math.abs(mark.h) * height}"/>`;
            }
            const labelX = (mark.x + mark.w) * width - 5, labelY = (mark.y + mark.h) * height - 5;
            return `<g>${shape}<text data-mark-index="${index}" class="${selected}" x="${labelX}" y="${labelY}" fill="${mark.color}" font-size="14" font-weight="800" text-anchor="end">${escapeHtml(mark.label || String(index + 1))}</text></g>`;
        }).join("");
        svg.innerHTML = markup;
        const selected = this.#markingRects[this.#selectedMarkIndex];
        const labelInput = this.querySelector("[data-action='change-mark-label']");
        const colorInput = this.querySelector("[data-action='change-mark-color']");
        const deleteButton = this.querySelector("[data-action='delete-selected-mark']");
        if (labelInput)
            labelInput.value = selected?.type === "label" ? selected.label : this.#labelDraft;
        if (colorInput && selected?.color)
            colorInput.value = selected.color;
        if (deleteButton instanceof HTMLButtonElement)
            deleteButton.disabled = !selected;
    }
    async #getMarkedImageBase64() {
        const img = this.querySelector("[data-role='preview-img-element']");
        if (!img)
            return null;
        if (!img.complete) {
            await new Promise(resolve => img.onload = resolve);
        }
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0);
        this.#markingRects.forEach((r, i) => {
            ctx.strokeStyle = r.color || "red";
            ctx.fillStyle = r.color || "red";
            ctx.lineWidth = 3;
            const x1 = r.x * img.naturalWidth;
            const y1 = r.y * img.naturalHeight;
            const x2 = (r.x + r.w) * img.naturalWidth;
            const y2 = (r.y + r.h) * img.naturalHeight;
            if (r.type === "label") {
                ctx.font = `bold ${Math.max(16, img.naturalWidth * .016)}px sans-serif`;
                ctx.textBaseline = "top";
                ctx.textAlign = "left";
                ctx.fillText(r.label, x1, y1);
                return;
            }
            else if (r.type === "arrow") {
                const angle = Math.atan2(y2 - y1, x2 - x1);
                const size = Math.max(14, img.naturalWidth * .015);
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(x2, y2);
                ctx.lineTo(x2 - size * Math.cos(angle - .45), y2 - size * Math.sin(angle - .45));
                ctx.lineTo(x2 - size * Math.cos(angle + .45), y2 - size * Math.sin(angle + .45));
                ctx.closePath();
                ctx.fill();
            }
            else if (r.type === "path") {
                ctx.beginPath();
                r.points.forEach((item, pointIndex) => {
                    const x = item.x * img.naturalWidth, y = item.y * img.naturalHeight;
                    if (pointIndex === 0)
                        ctx.moveTo(x, y);
                    else
                        ctx.lineTo(x, y);
                });
                ctx.stroke();
            }
            else {
                ctx.strokeRect(x1, y1, r.w * img.naturalWidth, r.h * img.naturalHeight);
            }
            ctx.font = "bold 16px sans-serif";
            ctx.textBaseline = "bottom";
            ctx.textAlign = "right";
            ctx.fillText(r.label || String(i + 1), x2 - 6, y2 - 6);
        });
        return canvas.toDataURL("image/png");
    }
    async #captureScreenshot() {
        try {
            const stream = await navigator.mediaDevices.getDisplayMedia({
                video: { mediaSource: "screen" }
            });
            const video = document.createElement("video");
            video.srcObject = stream;
            video.play();
            await new Promise(resolve => {
                video.onloadedmetadata = () => resolve();
            });
            await new Promise(resolve => setTimeout(resolve, 300));
            const canvas = document.createElement("canvas");
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext("2d");
            ctx.drawImage(video, 0, 0);
            stream.getTracks().forEach(track => track.stop());
            const dataUrl = canvas.toDataURL("image/png");
            const createBtn = this.querySelector("[data-action='open-create-modal']");
            createBtn?.click();
            this.#displayImageToMark(dataUrl);
        }
        catch (err) {
            console.error("Screen capture failed:", err);
        }
    }
    /**
     * Bind DOM events.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelector("[data-action='refresh-backlog']")?.addEventListener("click", () => this.#loadBacklog(true));
        this.querySelector(".backlog-filter-menu")?.addEventListener("toggle", event => {
            this.#filtersOpen = event.currentTarget.open;
        });
        this.querySelectorAll("[data-filter-kind]").forEach(input => input.addEventListener("change", event => {
            const target = event.currentTarget;
            const collection = target.dataset.filterKind === "status" ? this.#statusFilter : this.#priorityFilter;
            if (target.checked)
                collection.add(target.value);
            else
                collection.delete(target.value);
            this.#render();
        }));
        this.querySelector("[data-action='clear-backlog-filters']")?.addEventListener("click", () => {
            this.#statusFilter.clear();
            this.#priorityFilter.clear();
            this.#render();
        });
        this.querySelectorAll("[data-node-path]").forEach(button => button.addEventListener("click", () => {
            const path = button.getAttribute("data-node-path") || "";
            const isBranch = button.getAttribute("data-node-branch") === "true";
            this.#selectedDomain = path;
            this.#expandAncestors(path);
            if (isBranch && this.#expandedNodes.has(path)) {
                this.#expandedNodes.delete(path);
            }
            else {
                this.#expandedNodes.add(path);
            }
            this.#render();
        }));
        this.querySelectorAll("[data-action='set-task-status']").forEach(button => {
            button.addEventListener("click", () => this.#setTaskStatus(button.getAttribute("data-task-id") || "", button.getAttribute("data-task-status") || "DONE"));
        });
        this.querySelectorAll("[data-action='delete-task']").forEach(button => {
            button.addEventListener("click", () => this.#deleteTask(button.getAttribute("data-task-id") || "", button.getAttribute("data-task-status") || "WORKING"));
        });
        // Open Create Modal
        this.querySelector("[data-action='open-create-modal']")?.addEventListener("click", () => {
            const dialog = this.querySelector("#backlog-modal");
            if (!dialog)
                return;
            this.querySelector("[data-role='modal-task-id']").value = "";
            const domInput = this.querySelector("[data-role='modal-domain']");
            domInput.value = this.#selectedDomain;
            domInput.removeAttribute("disabled");
            this.querySelector("[data-role='modal-title-input']").value = "";
            this.querySelector("[data-role='modal-description']").value = "";
            this.querySelector("[data-role='modal-priority']").value = "HIGH";
            this.#markingRects = [];
            const imgInput = this.querySelector("[data-role='modal-image-file']");
            if (imgInput)
                imgInput.value = "";
            const previewArea = this.querySelector("[data-role='image-preview-area']");
            if (previewArea) {
                previewArea.innerHTML = `<span class="upload-placeholder" style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px;">Haga clic o arrastre una imagen aquí</span>`;
            }
            this.#setVisualReferenceHasImage(false);
            const imgUploadZone = this.querySelector("[data-role='image-upload-zone']");
            if (imgUploadZone) {
                imgUploadZone.style.removeProperty("display");
            }
            this.querySelector("[data-role='modal-title']").textContent = "Crear nueva tarea";
            this.querySelector("[data-role='modal-submit-btn']").textContent = "Crear";
            dialog.showModal();
        });
        // Open Edit Modal
        this.querySelectorAll("[data-action='edit-task']").forEach(button => {
            button.addEventListener("click", () => {
                const taskId = button.getAttribute("data-task-id") || "";
                const task = this.#tasks.find(t => t.id === taskId);
                if (!task)
                    return;
                const dialog = this.querySelector("#backlog-modal");
                if (!dialog)
                    return;
                this.querySelector("[data-role='modal-task-id']").value = task.id;
                const domInput = this.querySelector("[data-role='modal-domain']");
                domInput.value = task.domain;
                domInput.setAttribute("disabled", "true");
                this.querySelector("[data-role='modal-title-input']").value = task.title;
                this.querySelector("[data-role='modal-description']").value = task.description;
                this.querySelector("[data-role='modal-priority']").value = task.priority;
                const imgUploadZone = this.querySelector("[data-role='image-upload-zone']");
                if (imgUploadZone) {
                    imgUploadZone.style.removeProperty("display");
                }
                this.#markingRects = [];
                const imgInput = this.querySelector("[data-role='modal-image-file']");
                if (imgInput)
                    imgInput.value = "";
                const previewArea = this.querySelector("[data-role='image-preview-area']");
                if (previewArea) {
                    previewArea.innerHTML = `<span class="upload-placeholder" style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px;">Haga clic o arrastre una imagen aquí</span>`;
                }
                this.#setVisualReferenceHasImage(false);
                const imageTaskId = task.id.replace(/^#/, "");
                if (this.#tasksWithImages.includes(imageTaskId)) {
                    this.#displayImageToMark(`/api/backlog/image?taskId=${encodeURIComponent(imageTaskId)}`);
                }
                this.querySelector("[data-role='modal-title']").textContent = `Editar tarea #${task.id}`;
                this.querySelector("[data-role='modal-submit-btn']").textContent = "Guardar";
                dialog.showModal();
            });
        });
        // Close Modal
        this.querySelectorAll("[data-action='close-modal']").forEach(btn => {
            btn.addEventListener("click", () => {
                this.querySelector("#backlog-modal")?.close();
            });
        });
        // Open & Close Visual Reference Modal
        this.querySelector("[data-action='open-visual-reference']")?.addEventListener("click", () => {
            this.querySelector("#visual-reference-modal")?.showModal();
        });
        this.querySelectorAll("[data-action='close-visual-reference']").forEach(btn => {
            btn.addEventListener("click", () => {
                this.querySelector("#visual-reference-modal")?.close();
            });
        });
        // Image Viewer Modal Listeners
        this.querySelectorAll("[data-action='view-image']").forEach(thumb => {
            thumb.addEventListener("click", () => {
                const taskId = thumb.getAttribute("data-task-id") || "";
                const modal = this.querySelector("#image-viewer-modal");
                const img = this.querySelector("[data-role='viewer-img']");
                if (modal && img) {
                    img.src = `/api/backlog/image?taskId=${taskId}`;
                    modal.showModal();
                }
            });
        });
        this.querySelector("[data-action='close-image-viewer']")?.addEventListener("click", () => {
            this.querySelector("#image-viewer-modal")?.close();
        });
        // Paste Image from Clipboard Listener
        const descInput = this.querySelector("[data-role='modal-description']");
        descInput?.addEventListener("paste", event => {
            const items = event.clipboardData?.items;
            if (!items)
                return;
            for (const item of items) {
                if (item.type.startsWith("image/")) {
                    event.preventDefault();
                    const file = item.getAsFile();
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = ev => {
                            this.#displayImageToMark(ev.target.result);
                            // Insert {ref_image} tag at cursor
                            const start = descInput.selectionStart;
                            const end = descInput.selectionEnd;
                            const val = descInput.value;
                            descInput.value = val.slice(0, start) + "{ref_image}" + val.slice(end);
                            descInput.selectionStart = descInput.selectionEnd = start + "{ref_image}".length;
                        };
                        reader.readAsDataURL(file);
                    }
                    break;
                }
            }
        });
        // Modal Form Submit
        this.querySelector("[data-role='modal-form']")?.addEventListener("submit", async (event) => {
            event.preventDefault();
            const dialog = this.querySelector("#backlog-modal");
            const taskId = this.querySelector("[data-role='modal-task-id']").value;
            const domain = this.querySelector("[data-role='modal-domain']").value.trim() || this.#selectedDomain || "Backlog";
            const title = this.querySelector("[data-role='modal-title-input']").value.trim();
            const description = this.querySelector("[data-role='modal-description']").value.trim();
            const priority = this.querySelector("[data-role='modal-priority']").value;
            dialog.close();
            if (taskId) {
                this.#state?.setActiveCommand(`edit-task ${taskId}`);
                let base64Image = null;
                try {
                    base64Image = await this.#getMarkedImageBase64();
                }
                catch (e) {
                    console.error("Error baking marked image:", e);
                }
                const result = await this.#api.updateBacklog({
                    action: "edit",
                    taskId,
                    title,
                    description,
                    priority,
                    image: base64Image
                });
                this.#state?.setLastResult(result);
                await this.#loadBacklog(true);
            }
            else {
                this.#state?.setActiveCommand(`add-task ${domain} "${title}"`);
                let base64Image = null;
                try {
                    base64Image = await this.#getMarkedImageBase64();
                }
                catch (e) {
                    console.error("Error baking marked image:", e);
                }
                const result = await this.#api.updateBacklog({
                    action: "add",
                    domain,
                    title,
                    description,
                    priority,
                    image: base64Image
                });
                this.#state?.setLastResult(result);
                this.#selectedDomain = domain;
                await this.#loadBacklog(true);
            }
        });
        // Image Drag & Drop / File Input Click
        const previewArea = this.querySelector("[data-role='image-preview-area']");
        const fileInput = this.querySelector("[data-role='modal-image-file']");
        previewArea?.addEventListener("click", event => {
            if (previewArea.classList.contains("has-image") || fileInput?.disabled)
                return;
            if (!event.target.closest(".upload-placeholder") && event.target !== previewArea)
                return;
            fileInput?.click();
        });
        fileInput?.addEventListener("change", e => {
            const file = e.target.files?.[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = ev => {
                    this.#displayImageToMark(ev.target.result);
                };
                reader.readAsDataURL(file);
            }
        });
        // Real Document PiP
        this.querySelector("[data-action='toggle-pip']")?.addEventListener("click", () => {
            this.#openPipWindow();
        });
        this.querySelector("[data-action='capture-screen']")?.addEventListener("click", () => {
            this.#captureScreenshot();
        });
    }
}
customElements.define(BacklogView.selector, BacklogView);

cache=(()=>{return { BacklogView: BacklogView };})();return cache;};})();
const __brainExplorerModule11=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */


/**
 * SettingsView renders compact runtime health facts for the local explorer.
 */
class SettingsView extends HTMLElement {
    static get selector() {
        return "brain-settings-view";
    }
    #api = null;
    #state = null;
    #health = null;
    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#loadHealth();
    }
    /**
     * Initialize DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
    }
    /**
     * Load server health.
     *
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadHealth() {
        if (!this.#api) {
            return;
        }
        const result = await this.#api.health({ forceRefresh: true });
        this.#state?.setLastResult(result);
        this.#health = result.data || result;
        this.#render();
    }
    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface settings-console">
                <main class="settings-layout">
                    <button class="settings-tile settings-action-tile" data-action="refresh-health">
                        <span>${escapeHtml("Accion")}</span>
                        <strong>${icon("refresh")}Actualizar runtime</strong>
                        <small>health local</small>
                    </button>
                    ${this.#tile("Servidor", this.#health?.ok ? "OK" : "Pendiente", "brain_explorer")}
                    ${this.#tile("Dist", this.#health?.distDir || "No cargado", "runtime estatico")}
                    ${this.#tile("Workspace", this.#health?.workspaceRoot || "No cargado", "raiz activa")}
                    ${this.#tile("Agent home", this.#health?.agentHome || "No cargado", "memoria compartida")}
                </main>
            </section>
        `;
        this.querySelector("[data-action='refresh-health']")?.addEventListener("click", () => this.#loadHealth());
    }
    /**
     * Render one settings tile.
     *
     * @param {string} label Tile label.
     * @param {string} value Tile value.
     * @param {string} caption Tile caption.
     * @returns {string} HTML.
     */
    #tile(label, value, caption) {
        return `
            <article class="settings-tile">
                <span>${escapeHtml(label)}</span>
                <strong>${escapeHtml(String(value))}</strong>
                <small>${escapeHtml(caption)}</small>
            </article>
        `;
    }
}
customElements.define(SettingsView.selector, SettingsView);

cache=(()=>{return { SettingsView: SettingsView };})();return cache;};})();
const __brainExplorerModule12=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */


/**
 * WikisView renders detected subproject documentation wikis and opens them
 * inside an embedded iframe. No generation step — serves markdown live.
 */
class WikisView extends HTMLElement {
    static get selector() {
        return "brain-wikis-view";
    }
    #api = null;
    #state = null;
    #wikis = [];
    #loading = false;
    #wikiLoading = false;
    #activeWikiName = null;
    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#loadWikis();
    }
    /**
     * Initialize DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
    }
    /**
     * Load server wikis list.
     *
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadWikis() {
        if (!this.#api)
            return;
        this.#loading = true;
        this.#render();
        try {
            const api = this.#api;
            const res = await api.getWikis();
            this.#wikis = res?.wikis || [];
            this.#state?.setLastResult(res);
        }
        catch (err) {
            console.error("Error fetching wikis:", err);
        }
        finally {
            this.#loading = false;
            this.#render();
        }
    }
    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        if (this.#activeWikiName) {
            this.#renderIframeView();
            return;
        }
        this.innerHTML = `
            <section class="page-surface settings-console wiki-console ${this.#loading ? "is-loading" : (this.#wikis.length ? "has-items" : "is-empty")}">
                <header class="view-header" style="display: flex; justify-content: space-between; align-items: center; padding-bottom: var(--spacing-md); border-bottom: 1px solid var(--border); margin-bottom: var(--spacing-lg);">
                    <div>
                        <h2 style="margin: 0; font-size: var(--font-size-xl); color: var(--text-strong);">Wikis de Subproyectos</h2>
                        <small style="color: var(--text-muted);">Documentación interactiva disponible en el path activo</small>
                    </div>
                    <button data-action="refresh-wikis" class="primary-action compact-action" title="Buscar wikis">${icon("refresh")}</button>
                </header>
                
                ${this.#loading ? `
                    <div class="loading-state" style="padding: 40px; text-align: center;">
                        <span></span>
                        <strong>Buscando wikis...</strong>
                    </div>
                ` : this.#renderWikisGrid()}
            </section>
        `;
        this.querySelector("[data-action='refresh-wikis']")?.addEventListener("click", () => this.#loadWikis());
        this.querySelectorAll("[data-action='view-wiki']").forEach(btn => {
            btn.addEventListener("click", () => {
                this.#activeWikiName = btn.getAttribute("data-name");
                this.#wikiLoading = true;
                this.#render();
            });
            btn.addEventListener("keydown", event => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    btn.click();
                }
            });
        });
    }
    /**
     * Render wikis as compact horizontal list items.
     *
     * @returns {string} HTML.
     */
    #renderWikisGrid() {
        if (!this.#wikis.length) {
            return `
                <div class="knowledge-empty-state wiki-empty-state">
                    ${icon("document")}
                    <h3>No se encontraron carpetas de documentación</h3>
                    <p>Crea una carpeta <code>documentation</code> en algún subproyecto para habilitar wikis locales.</p>
                </div>
            `;
        }
        return `
            <main class="wiki-list">
                ${this.#wikis.map(wiki => `
                    <article class="wiki-list-item ${wiki.hasWiki ? "is-clickable" : ""}"
                        ${wiki.hasWiki ? `data-action="view-wiki" data-name="${escapeHtml(wiki.name)}" tabindex="0" role="button" aria-label="Abrir wiki ${escapeHtml(wiki.name)}"` : ""}>
                        <div class="wiki-list-content">
                            <div class="wiki-list-heading">
                                <strong>${escapeHtml(wiki.name)}</strong>
                                <span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 600; background: ${wiki.hasWiki ? "rgba(16, 185, 129, 0.15); color: #10b981;" : "rgba(156, 163, 175, 0.15); color: #9ca3af;"};">
                                    ${wiki.hasWiki ? "Disponible" : "Sin compilar"}
                                </span>
                            </div>
                            <span class="wiki-list-path">
                                ${escapeHtml(wiki.path)}
                            </span>
                        </div>
                        <div class="wiki-list-action">
                            ${wiki.hasWiki ? `
                                <button class="primary-action compact-action" tabindex="-1">
                                    ${icon("book")} Ver Wiki
                                </button>
                            ` : `
                                <span style="font-size: var(--font-size-sm); color: var(--text-muted); padding: 6px 0;">Ejecuta <code>generate</code> para habilitar</span>
                            `}
                        </div>
                    </article>
                `).join("")}
            </main>
        `;
    }
    /**
     * Render the active wiki iframe full view.
     *
     * @returns {void}
     */
    #renderIframeView() {
        this.innerHTML = `
            <div class="wiki-frame-view">
                <header class="wiki-frame-toolbar">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <button data-action="close-wiki" class="secondary-action compact-action" style="min-height: 32px; display: flex; align-items: center; gap: 4px;">
                            ${icon("chevronRight")} Atrás
                        </button>
                        <h2 style="margin: 0; font-size: var(--font-size-lg); color: var(--text-strong);">Wiki ~ ${escapeHtml(this.#activeWikiName)}</h2>
                    </div>
                </header>
                <div class="wiki-frame-container">
                    <div class="wiki-frame-loading" ${this.#wikiLoading ? "" : "hidden"} role="status">
                        <span class="loading-spinner" aria-hidden="true"></span>
                        <strong>Resolviendo wiki...</strong>
                    </div>
                    <iframe src="/wiki/${this.#activeWikiName}/wiki/index.html" scrolling="yes" style="width: 100%; height: 100%; border: none;" title="Wiki Frame"></iframe>
                </div>
            </div>
        `;
        this.querySelector("[data-action='close-wiki']")?.addEventListener("click", () => {
            this.#activeWikiName = null;
            this.#render();
        });
        this.querySelector("iframe")?.addEventListener("load", event => {
            this.#wikiLoading = false;
            this.querySelector(".wiki-frame-loading")?.setAttribute("hidden", "");
            this.#hideIframeScrollbar(event.currentTarget);
        });
    }
    /**
     * Hide the same-origin wiki scrollbar while preserving wheel, keyboard,
     * and touch scrolling inside the embedded document.
     *
     * @param {HTMLIFrameElement} iframe Loaded wiki frame.
     * @returns {void}
     */
    #hideIframeScrollbar(iframe) {
        const documentRoot = iframe.contentDocument;
        if (!documentRoot?.head) {
            return;
        }
        const style = documentRoot.createElement("style");
        style.dataset.brainExplorerScrollbar = "hidden";
        style.textContent = `
            html, body {
                scrollbar-width: none !important;
                -ms-overflow-style: none !important;
            }
            html::-webkit-scrollbar,
            body::-webkit-scrollbar {
                display: none !important;
                width: 0 !important;
                height: 0 !important;
            }
        `;
        documentRoot.head.querySelector("[data-brain-explorer-scrollbar]")?.remove();
        documentRoot.head.append(style);
    }
}
customElements.define(WikisView.selector, WikisView);

cache=(()=>{return { WikisView: WikisView };})();return cache;};})();
const __brainExplorerModule13=(()=>{let cache;return()=>{if(cache)return cache;
const { StructureTree } = __brainExplorerModule18();
const { escapeHtml, renderMarkdown } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */



/** Browse, inspect, copy, download, and replay persisted voice messages. */
class MessagesView extends HTMLElement {
    static get selector() {
        return "brain-messages-view";
    }
    #api = null;
    #state = null;
    #messages = [];
    #speaks = [];
    #history = [];
    #sessions = [];
    #selectedSessionId = "";
    #loading = false;
    #playingName = "";
    #refreshTimer = null;
    #statusTimer = null;
    #activeSpeakId = "";
    #serviceState = "stopped";
    #expandedIds = new Set();
    #expandedTreePaths = new Set();
    #generatingAudioIds = new Set();
    #generatedAudioSpeakIds = new Map();
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        void this.#loadMessages();
        void this.#pollVoiceStatus();
    }
    connectedCallback() {
        this.#render();
    }
    disconnectedCallback() {
        this.#stopAudio();
        if (this.#refreshTimer !== null)
            window.clearTimeout(this.#refreshTimer);
        if (this.#statusTimer !== null)
            window.clearTimeout(this.#statusTimer);
    }
    /** Synchronize playback controls exclusively from the daemon's latest status. */
    async #pollVoiceStatus() {
        if (!this.#api)
            return;
        if (this.#statusTimer !== null)
            window.clearTimeout(this.#statusTimer);
        this.#statusTimer = null;
        try {
            const response = await this.#api.getVoiceStatus({ forceRefresh: true, silent: true });
            const activeSpeakId = response.data?.activeSpeakId ?? "";
            const serviceState = response.data?.state ?? "stopped";
            const playbackActive = ["preparing", "speaking", "muted_replay"].includes(serviceState);
            const playingName = playbackActive
                ? this.#messages.find(message => message.speakId === activeSpeakId)?.name ?? ""
                : "";
            if (activeSpeakId !== this.#activeSpeakId
                || serviceState !== this.#serviceState
                || playingName !== this.#playingName) {
                this.#activeSpeakId = activeSpeakId;
                this.#serviceState = serviceState;
                this.#playingName = playingName;
                this.#render();
            }
        }
        finally {
            if (this.isConnected) {
                this.#statusTimer = window.setTimeout(() => void this.#pollVoiceStatus(), 750);
            }
        }
    }
    async #loadMessages(silent = false) {
        if (!this.#api)
            return;
        if (this.#refreshTimer !== null)
            window.clearTimeout(this.#refreshTimer);
        this.#refreshTimer = null;
        if (!silent) {
            this.#loading = true;
            this.#render();
        }
        try {
            const selected = this.#sessions.find(session => session.id === this.#selectedSessionId);
            const params = selected ? { date: selected.date, chatId: selected.chatId } : {};
            const response = await this.#api.getVoiceMessages(params, { forceRefresh: true, silent });
            this.#messages = response.data?.messages ?? [];
            this.#speaks = response.data?.speaks ?? [];
            this.#history = response.data?.history ?? [];
            this.#sessions = response.data?.sessions ?? [];
            if (!this.#selectedSessionId && this.#sessions.length) {
                this.#selectedSessionId = this.#sessions[0].id;
                this.#expandSessionPath(this.#sessions[0]);
                await this.#loadMessages(true);
                return;
            }
            this.#state?.setLastResult(response);
        }
        finally {
            this.#loading = false;
            this.#render();
            if (this.isConnected)
                this.#refreshTimer = window.setTimeout(() => void this.#loadMessages(true), 60_000);
        }
    }
    #render() {
        this.innerHTML = `
            <section class="page-surface messages-console">
                <div class="structure-layout messages-structure">
                    <aside class="structure-tree" aria-label="Sesiones de mensajes">
                        <brain-structure-tree data-role="message-session-tree"></brain-structure-tree>
                    </aside>
                    <main class="structure-content">
                        <header class="content-head">
                            <strong>${escapeHtml(this.#selectedSessionLabel())}</strong>
                            <span>${this.#selectedSessionId && this.#history.length ? `${this.#history.length} mensajes` : ""}</span>
                        </header>
                        <section class="voice-message-list" aria-label="Mensajes de la sesion">
                            ${this.#loading ? `<div class="loading-state"><span></span><strong>Cargando mensajes...</strong></div>` : this.#renderMessages()}
                        </section>
                    </main>
                </div>
            </section>
        `;
        this.querySelectorAll("[data-action='play-message']").forEach(button => {
            button.addEventListener("click", () => void this.#toggleMessage(button.getAttribute("data-name") || ""));
        });
        this.querySelectorAll(".voice-message-item").forEach(item => {
            item.addEventListener("click", event => {
                const target = event.target instanceof Element ? event.target : null;
                if (target?.closest(".voice-message-actions, .voice-message-leading-action"))
                    return;
                this.#toggleExpandedMessage(item.getAttribute("data-message-id") || "");
            });
        });
        this.querySelectorAll("[data-action='copy-message']").forEach(button => {
            button.addEventListener("click", () => void this.#copyMessage(button));
        });
        this.querySelectorAll("[data-action='generate-message-audio']").forEach(button => {
            button.addEventListener("click", () => {
                void this.#generateMessageAudio(button.getAttribute("data-message-id") || "");
            });
        });
        this.#configureTree();
    }
    #renderMessages() {
        if (!this.#selectedSessionId) {
            return `<div class="voice-empty-state">${icon("messageCircle")}<strong>Selecciona una sesion</strong></div>`;
        }
        if (!this.#history.length) {
            return `<div class="voice-empty-state">${icon("messageCircle")}<strong>Esta sesion no contiene mensajes</strong></div>`;
        }
        const pairedNames = new Set();
        const persistedItems = this.#history.map(record => {
            const speak = this.#speaks.find(candidate => candidate.id === record.id) ?? null;
            const generatedSpeakId = this.#generatedAudioSpeakIds.get(record.id);
            const message = this.#messages.find(candidate => candidate.speakId === record.id || candidate.speakId === generatedSpeakId);
            if (message)
                pairedNames.add(message.name);
            return this.#renderMessageItem(record, speak, message);
        });
        return persistedItems.join("");
    }
    /** Project durable summaries into the shared Explorer tree contract. */
    #sessionTreeNodes() {
        const years = new Map();
        this.#sessions.forEach(session => {
            const [year, month, day] = session.date.split("-");
            if (!years.has(year))
                years.set(year, new Map());
            const months = years.get(year);
            if (!months.has(month))
                months.set(month, new Map());
            const days = months.get(month);
            if (!days.has(day))
                days.set(day, []);
            days.get(day).push(session);
        });
        return [...years.entries()].map(([year, months]) => ({
            id: `messages/${year}`,
            path: `messages/${year}`,
            label: year,
            icon: "folder",
            count: [...months.values()].reduce((total, days) => total + [...days.values()].flat().length, 0),
            children: [...months.entries()].map(([month, days]) => ({
                id: `messages/${year}/${month}`,
                path: `messages/${year}/${month}`,
                label: this.#monthLabel(month),
                icon: "folder",
                count: [...days.values()].flat().length,
                children: [...days.entries()].map(([day, sessions]) => ({
                    id: `messages/${year}/${month}/${day}`,
                    path: `messages/${year}/${month}/${day}`,
                    label: `Dia ${day}`,
                    icon: "folder",
                    count: sessions.length,
                    children: sessions.map(session => ({
                        id: session.id,
                        path: session.id,
                        label: session.chatId ? session.label : `Sesion ${this.#formatTime(session.startedAt)}`,
                        icon: "messageCircle",
                        count: session.messageCount
                    }))
                }))
            }))
        }));
    }
    /** Configure the reusable structural tree with message session nodes. */
    #configureTree() {
        const tree = this.querySelector("[data-role='message-session-tree']");
        if (!(tree instanceof StructureTree))
            return;
        tree.model = {
            nodes: this.#sessionTreeNodes(),
            selectedPath: this.#selectedSessionId,
            expandedPaths: this.#expandedTreePaths,
            toggleOnBranchSelect: true,
            title: "Mensajes",
            toolbarActions: [{ id: "refresh", label: "Actualizar mensajes", icon: "refresh" }],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "messageCircle",
            searchPlaceholder: "Buscar sesiones...",
            emptyText: this.#loading ? "Cargando sesiones..." : "No hay sesiones almacenadas."
        };
        tree.addEventListener("brain-tree-select", event => {
            if (!event.detail.branch)
                void this.#selectSession(event.detail.path);
        });
        tree.addEventListener("brain-tree-toolbar-action", event => {
            if (event.detail.action === "refresh")
                void this.#loadMessages();
        });
    }
    /** Expand the ancestors of the active session in the shared tree. */
    #expandSessionPath(session) {
        const [year, month, day] = session.date.split("-");
        this.#expandedTreePaths.add(`messages/${year}`);
        this.#expandedTreePaths.add(`messages/${year}/${month}`);
        this.#expandedTreePaths.add(`messages/${year}/${month}/${day}`);
    }
    /** Return the content-panel heading for the selected session. */
    #selectedSessionLabel() {
        const session = this.#sessions.find(candidate => candidate.id === this.#selectedSessionId);
        if (!session)
            return "Selecciona una sesion";
        return session.chatId ? session.label : `Sesion del ${session.date} a las ${this.#formatTime(session.startedAt)}`;
    }
    /** Select a durable session and request only its messages. */
    async #selectSession(id) {
        if (!id || id === this.#selectedSessionId)
            return;
        this.#selectedSessionId = id;
        const selected = this.#sessions.find(session => session.id === id);
        if (selected)
            this.#expandSessionPath(selected);
        this.#history = [];
        await this.#loadMessages();
    }
    #renderMessageItem(record, speak, message) {
        const id = record.id;
        const expanded = this.#expandedIds.has(id);
        const name = message?.name ?? "";
        const createdAt = record.created_at;
        const text = record.text;
        const status = speak?.status ?? "DONE";
        const generatingAudio = this.#generatingAudioIds.has(id);
        const sourceLabel = record.source_command
            ? `${record.source_command}:${record.source_phase || "output"}`
            : record.emotion || "speak";
        return `
            <article class="voice-message-item ${name === this.#playingName ? "is-playing" : ""} ${expanded ? "is-expanded" : ""}" data-message-id="${escapeHtml(id)}">
                <div class="voice-message-header">
                    ${expanded
            ? `<span class="voice-message-leading-placeholder" aria-hidden="true"></span>`
            : this.#renderLeadingAudioAction(id, name, generatingAudio)}
                    <button class="voice-message-summary" data-action="toggle-message-details" data-id="${escapeHtml(id)}" aria-expanded="${expanded}">
                        ${expanded ? `<span class="voice-message-spacer"></span>` : `<span class="voice-message-preview">${escapeHtml(text)}</span>`}
                        <span class="voice-speak-status is-${status.toLowerCase()}">${escapeHtml(sourceLabel)}</span>
                        <time class="voice-message-time" datetime="${escapeHtml(createdAt)}">${escapeHtml(this.#formatTime(createdAt))}</time>
                    </button>
                </div>
                ${expanded ? `
                    <div class="voice-message-detail">
                        <div class="voice-message-markdown">${renderMarkdown(text)}</div>
                        ${speak?.error ? `<section class="voice-error-detail" role="alert"><strong>Detalle del error</strong><pre>${escapeHtml(speak.error)}</pre></section>` : ""}
                        <footer class="voice-message-footer">
                            <div class="voice-message-actions">
                                ${name
            ? `<button class="voice-icon-action" data-action="play-message" data-name="${escapeHtml(name)}" title="Reproducir mensaje" aria-label="Reproducir mensaje">${icon(name === this.#playingName ? "pause" : "play")}</button>`
            : `<button class="voice-icon-action" data-action="generate-message-audio" data-message-id="${escapeHtml(id)}" ${generatingAudio ? "disabled" : ""} title="Generar audio" aria-label="Generar audio">${icon("volume")}</button>`}
                                ${message ? `<a class="voice-download-button labeled" href="${this.#api?.voiceMessageUrl(message.name) ?? "#"}" download="${escapeHtml(message.name)}" title="Descargar mensaje">${icon("download")} ${this.#formatBytes(message.sizeBytes)}</a>` : ""}
                                <button class="voice-icon-action" data-action="copy-message" data-text="${escapeHtml(text)}" title="Copiar mensaje" aria-label="Copiar mensaje">${icon("copy")}</button>
                            </div>
                        </footer>
                    </div>
                ` : ""}
            </article>
        `;
    }
    #renderLegacyMessageItem(message) {
        const createdAt = message.createdAt;
        const text = message.text ?? "Audio histórico sin transcripción";
        const id = message.id ?? message.name;
        const expanded = this.#expandedIds.has(id);
        return `
            <article class="voice-message-item ${message.name === this.#playingName ? "is-playing" : ""} ${expanded ? "is-expanded" : ""}" data-message-id="${escapeHtml(id)}">
                <div class="voice-message-header">
                    ${expanded
            ? `<span class="voice-message-leading-placeholder" aria-hidden="true"></span>`
            : this.#renderLeadingAudioAction(id, message.name, false)}
                    <button class="voice-message-summary" data-action="toggle-message-details" data-id="${escapeHtml(id)}" aria-expanded="${expanded}">
                        <span class="voice-message-preview">${escapeHtml(text)}</span>
                        <span class="voice-speak-status is-done">audio</span>
                        <time class="voice-message-time" datetime="${escapeHtml(createdAt)}">${escapeHtml(this.#formatTime(createdAt))}</time>
                    </button>
                </div>
                ${expanded ? `
                    <div class="voice-message-detail">
                        <div class="voice-message-markdown">${renderMarkdown(text)}</div>
                        <footer class="voice-message-footer">
                            <div class="voice-message-actions">
                                <button class="voice-icon-action" data-action="play-message" data-name="${escapeHtml(message.name)}" title="Reproducir mensaje" aria-label="Reproducir mensaje">${icon(message.name === this.#playingName ? "pause" : "play")}</button>
                                <a class="voice-download-button labeled" href="${this.#api?.voiceMessageUrl(message.name) ?? "#"}" download="${escapeHtml(message.name)}" title="Descargar mensaje">${icon("download")} ${this.#formatBytes(message.sizeBytes)}</a>
                                <button class="voice-icon-action" data-action="copy-message" data-text="${escapeHtml(text)}" title="Copiar mensaje" aria-label="Copiar mensaje">${icon("copy")}</button>
                            </div>
                        </footer>
                    </div>
                ` : ""}
            </article>
        `;
    }
    /** Render the primary list action as replay or on-demand audio generation. */
    #renderLeadingAudioAction(id, name, generatingAudio) {
        if (name) {
            const playing = name === this.#playingName;
            return `<button class="voice-icon-action voice-message-leading-action" data-action="play-message" data-name="${escapeHtml(name)}" title="${playing ? "Pausar mensaje" : "Reproducir mensaje"}" aria-label="${playing ? "Pausar mensaje" : "Reproducir mensaje"}">${icon(playing ? "pause" : "play")}</button>`;
        }
        return `<button class="voice-icon-action voice-message-leading-action" data-action="generate-message-audio" data-message-id="${escapeHtml(id)}" ${generatingAudio ? "disabled" : ""} title="Generar y reproducir audio" aria-label="Generar y reproducir audio">${icon("play")}</button>`;
    }
    async #copyMessage(button) {
        await navigator.clipboard.writeText(button.getAttribute("data-text") || "");
        button.setAttribute("title", "Copiado");
    }
    /** Request one non-persistent audio rendering for a historical message. */
    async #generateMessageAudio(id) {
        if (!this.#api || !id || this.#generatingAudioIds.has(id))
            return;
        this.#generatingAudioIds.add(id);
        this.#render();
        try {
            const result = await this.#api.synthesizeVoiceMessage(id);
            this.#state?.setLastResult(result);
            const speakId = result.data?.speakId ?? "";
            if (result.ok && speakId) {
                this.#generatedAudioSpeakIds.set(id, speakId);
                await this.#waitForGeneratedAudio(speakId);
            }
        }
        finally {
            this.#generatingAudioIds.delete(id);
            this.#render();
        }
    }
    /** Refresh briefly until the daemon exposes the newly retained MP3. */
    async #waitForGeneratedAudio(speakId) {
        for (let attempt = 0; attempt < 20; attempt += 1) {
            await new Promise(resolve => window.setTimeout(resolve, 500));
            await this.#loadMessages(true);
            if (this.#messages.some(message => message.speakId === speakId))
                return;
        }
    }
    /** Toggle one bubble while restoring keyboard focus after the DOM refresh. */
    #toggleExpandedMessage(id) {
        if (!id)
            return;
        const willExpand = !this.#expandedIds.has(id);
        if (willExpand)
            this.#expandedIds.add(id);
        else
            this.#expandedIds.delete(id);
        this.#render();
        requestAnimationFrame(() => this.#focusMessage(id, willExpand));
    }
    /** Focus one summary and keep its expanded card inside the message viewport. */
    #focusMessage(id, expanded) {
        const summary = Array.from(this.querySelectorAll(".voice-message-summary"))
            .find(candidate => candidate.getAttribute("data-id") === id);
        summary?.focus({ preventScroll: true });
        if (!expanded)
            return;
        const article = summary?.closest(".voice-message-item");
        const container = article?.closest(".voice-message-list");
        if (!article || !container)
            return;
        const articleBounds = article.getBoundingClientRect();
        const containerBounds = container.getBoundingClientRect();
        if (articleBounds.top < containerBounds.top) {
            container.scrollTop -= containerBounds.top - articleBounds.top;
        }
        else if (articleBounds.bottom > containerBounds.bottom) {
            container.scrollTop += articleBounds.bottom - containerBounds.bottom;
        }
    }
    async #toggleMessage(name) {
        if (!this.#api || !name)
            return;
        if (this.#playingName === name && ["preparing", "speaking", "muted_replay"].includes(this.#serviceState)) {
            await this.#api.pauseVoiceReplay();
            return;
        }
        try {
            await this.#api.replayVoiceMessage(name);
        }
        catch {
            return;
        }
    }
    #stopAudio() {
        this.#playingName = "";
    }
    #formatTime(value) {
        return new Intl.DateTimeFormat("es", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
    }
    #monthLabel(value) {
        const date = new Date(2026, Number(value) - 1, 1);
        return new Intl.DateTimeFormat("es", { month: "long" }).format(date);
    }
    #formatBytes(value) {
        return `${Math.max(1, Math.round(value / 1024))} KB`;
    }
}
customElements.define(MessagesView.selector, MessagesView);

cache=(()=>{return { MessagesView: MessagesView };})();return cache;};})();
const __brainExplorerModule14=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
const { StructureTree } = __brainExplorerModule18();
/** Modern registry-backed picture browser and carousel. */



void StructureTree;
class PicturesView extends HTMLElement {
    static get selector() {
        return "brain-pictures-view";
    }
    #api = null;
    #state = null;
    #pictures = [];
    #picturesByDomain = new Map();
    #domains = {};
    #domain = "";
    #domainFocused = false;
    #selectedId = "";
    #loading = false;
    #search = "";
    #expandedDomains = new Set(["pictures:all"]);
    #imageHydrationToken = 0;
    #viewerOpen = false;
    #viewerScale = 1;
    #viewerX = 0;
    #viewerY = 0;
    #viewerPointerId = null;
    #viewerScaleTimer = null;
    #viewerPointerStart = { x: 0, y: 0, originX: 0, originY: 0 };
    #handleKeyDown = (event) => {
        if (this.#viewerOpen) {
            if (event.key === "Escape")
                this.#closeViewer();
            if (event.key === "+" || event.key === "=")
                this.#zoomViewer(0.25);
            if (event.key === "-")
                this.#zoomViewer(-0.25);
            if (event.key === "0")
                this.#resetViewer();
            return;
        }
        if (event.key === "ArrowLeft")
            this.#selectRelative(-1);
        if (event.key === "ArrowRight")
            this.#selectRelative(1);
    };
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        const target = this.#state?.consumeRouteTarget?.("pictures") || null;
        this.#selectedId = String(target?.pictureId || "");
        this.#render();
        void this.#loadStructure();
    }
    connectedCallback() {
        window.addEventListener("keydown", this.#handleKeyDown);
        this.#render();
    }
    disconnectedCallback() {
        window.removeEventListener("keydown", this.#handleKeyDown);
        if (this.#viewerScaleTimer !== null)
            clearTimeout(this.#viewerScaleTimer);
    }
    /** Load the complete hierarchy once without eagerly returning picture records. */
    async #loadStructure(forceRefresh = false) {
        if (!this.#api)
            return;
        this.#loading = true;
        this.#render();
        const response = await this.#api.pictures({ structure_only: true, refresh: forceRefresh }, { forceRefresh: true, commandLabel: "Pictures structure" });
        this.#domains = response.data?.domains ?? {};
        if (forceRefresh)
            this.#picturesByDomain.clear();
        this.#state?.setLastResult(response);
        this.#loading = false;
        this.#render();
        if (this.#selectedId)
            await this.#loadPictureTarget(this.#selectedId);
    }
    /** Resolve a routed picture to its domain without loading the global registry. */
    async #loadPictureTarget(pictureId) {
        if (!this.#api)
            return;
        const response = await this.#api.pictures({ picture_id: pictureId }, { forceRefresh: true, commandLabel: "Picture target", silent: true });
        const target = response.data?.pictures?.[0];
        if (!target) {
            this.#selectedId = "";
            return;
        }
        this.#domain = target.domain;
        this.#domainFocused = true;
        await this.#loadDomain(target.domain, false, pictureId);
    }
    /** Hydrate and cache one domain only when its tree item receives focus. */
    async #loadDomain(domain, forceRefresh = false, preferredId = "") {
        if (!this.#api)
            return;
        const cached = this.#picturesByDomain.get(domain);
        if (cached && !forceRefresh) {
            this.#pictures = cached;
            this.#selectLoadedDomain(preferredId);
            this.#render();
            return;
        }
        this.#loading = true;
        this.#render();
        const response = await this.#api.pictures({ domain }, { forceRefresh: true, commandLabel: `Pictures domain: ${domain || "all"}` });
        this.#pictures = response.data?.pictures ?? [];
        this.#picturesByDomain.set(domain, this.#pictures);
        this.#selectLoadedDomain(preferredId);
        this.#state?.setLastResult(response);
        this.#loading = false;
        this.#render();
    }
    /** Preserve a routed/current selection when it belongs to the loaded domain. */
    #selectLoadedDomain(preferredId = "") {
        const candidate = preferredId || this.#selectedId;
        this.#selectedId = this.#pictures.some(picture => picture.id === candidate)
            ? candidate
            : this.#pictures[0]?.id ?? "";
    }
    #selected() {
        return this.#pictures.find(picture => picture.id === this.#selectedId) ?? null;
    }
    #selectRelative(delta) {
        if (!this.#pictures.length)
            return;
        const index = Math.max(0, this.#pictures.findIndex(picture => picture.id === this.#selectedId));
        const next = (index + delta + this.#pictures.length) % this.#pictures.length;
        this.#selectPicture(this.#pictures[next].id);
    }
    /** Update an existing carousel in place and hydrate its raster when ready. */
    #selectPicture(pictureId) {
        const picture = this.#pictures.find(candidate => candidate.id === pictureId);
        if (!picture || picture.id === this.#selectedId)
            return;
        this.#selectedId = picture.id;
        this.#hydrateSelection(picture);
        this.#focusSelectedThumbnail();
    }
    #render() {
        const selected = this.#selected();
        const selectedIndex = selected ? this.#pictures.findIndex(picture => picture.id === selected.id) : -1;
        this.innerHTML = `
            <section class="page-surface pictures-console">
                <div class="structure-layout pictures-layout">
                    <aside class="structure-tree pictures-domains" aria-label="Dominios de pictures">
                        <div class="tree-list scroll-list">
                            <brain-structure-tree data-role="pictures-domain-tree"></brain-structure-tree>
                        </div>
                    </aside>
                    <main class="pictures-stage">
                    ${this.#loading ? `<div class="loading-state"><span></span><strong>Sincronizando pictures...</strong></div>` : selected ? `
                        <section class="picture-carousel" aria-label="Carrusel de pictures">
                            <header>
                                <div><span class="status-pill" data-role="picture-domain">${escapeHtml(selected.domain)}</span><strong data-role="picture-filename">${escapeHtml(selected.filename)}</strong></div>
                                <span data-role="picture-position">${selectedIndex + 1} / ${this.#pictures.length}</span>
                            </header>
                            <div class="picture-viewport">
                                <button class="carousel-arrow is-previous" data-action="previous-picture" aria-label="Picture anterior">${icon("chevronRight")}</button>
                                <div class="picture-render-layer">
                                    <button class="picture-render-trigger" data-action="open-picture-viewer" aria-label="Abrir ${escapeHtml(selected.filename)} en visor fullscreen">
                                        <img data-role="selected-picture-image" src="${this.#api?.pictureUrl(selected.id) ?? ""}" alt="${escapeHtml(selected.description || selected.filename)}" loading="eager" decoding="async" fetchpriority="high">
                                    </button>
                                </div>
                                <button class="carousel-arrow is-next" data-action="next-picture" aria-label="Picture siguiente">${icon("chevronRight")}</button>
                            </div>
                            <div class="picture-thumbnails" role="listbox" aria-label="Miniaturas">
                                ${this.#pictures.map(picture => `
                                    <button role="option" aria-selected="${picture.id === selected.id}" data-picture-id="${escapeHtml(picture.id)}" title="${escapeHtml(picture.filename)}">
                                        <img src="${this.#api?.pictureUrl(picture.id) ?? ""}" alt="" loading="lazy" decoding="async" fetchpriority="low">
                                    </button>
                                `).join("")}
                            </div>
                        </section>
                        <aside class="picture-inspector">
                            <header><strong>Inspector</strong><span data-role="picture-dimensions">${selected.width} × ${selected.height}</span></header>
                            <dl>
                                <div><dt>Ruta</dt><dd data-role="picture-path">${escapeHtml(selected.relative_path)}</dd></div>
                                <div><dt>Tipo</dt><dd data-role="picture-mime">${escapeHtml(selected.mime_type)}</dd></div>
                                <div><dt>Tamaño</dt><dd data-role="picture-size">${this.#formatBytes(selected.size_bytes)}</dd></div>
                                <div><dt>Descripción</dt><dd data-role="picture-description-source">${escapeHtml(selected.description_source || "pendiente")}</dd></div>
                            </dl>
                            <label>Descripción
                                <textarea data-role="picture-description" placeholder="Describe personas, escena, objetos, texto y contexto...">${escapeHtml(selected.description)}</textarea>
                            </label>
                            <button class="primary-button" data-action="save-picture-description">${icon("save")} Guardar descripción</button>
                        </aside>
                    ` : `<section class="search-empty">${icon("camera")}<h2>${this.#domainFocused ? "Sin pictures" : "Selecciona un dominio"}</h2><p>${this.#domainFocused ? "No hay imágenes registradas en este dominio." : "El árbol ya está disponible; las imágenes se cargarán al enfocar un elemento."}</p></section>`}
                    </main>
                </div>
                ${selected ? this.#renderViewer(selected) : ""}
            </section>
        `;
        this.#configureDomainTree();
        this.#bindEvents();
    }
    /** Center and focus the active option without rebuilding or animating from scroll origin. */
    #focusSelectedThumbnail() {
        const selected = this.querySelector('.picture-thumbnails [role="option"][aria-selected="true"]');
        selected?.scrollIntoView({ behavior: "auto", block: "nearest", inline: "center" });
        selected?.focus({ preventScroll: true });
    }
    /** Patch carousel metadata immediately and replace only the raster after it loads. */
    #hydrateSelection(picture) {
        const position = this.#pictures.findIndex(candidate => candidate.id === picture.id) + 1;
        this.#setText("picture-domain", picture.domain);
        this.#setText("picture-filename", picture.filename);
        this.#setText("picture-position", `${position} / ${this.#pictures.length}`);
        this.#setText("picture-dimensions", `${picture.width} × ${picture.height}`);
        this.#setText("picture-path", picture.relative_path);
        this.#setText("picture-mime", picture.mime_type);
        this.#setText("picture-size", this.#formatBytes(picture.size_bytes));
        this.#setText("picture-description-source", picture.description_source || "pendiente");
        const textarea = this.querySelector("[data-role='picture-description']");
        if (textarea)
            textarea.value = picture.description;
        const trigger = this.querySelector("[data-action='open-picture-viewer']");
        trigger?.setAttribute("aria-label", `Abrir ${picture.filename} en visor fullscreen`);
        this.querySelectorAll("[data-picture-id]").forEach(option => {
            option.setAttribute("aria-selected", String(option.dataset.pictureId === picture.id));
        });
        this.#hydrateSelectedRaster(picture);
    }
    /** Load the next raster off-DOM and commit only the newest completed request. */
    #hydrateSelectedRaster(picture) {
        const token = ++this.#imageHydrationToken;
        const source = this.#api?.pictureUrl(picture.id) ?? "";
        const pending = new Image();
        pending.decoding = "async";
        pending.onload = () => {
            if (token !== this.#imageHydrationToken || picture.id !== this.#selectedId)
                return;
            const mounted = this.querySelector("[data-role='selected-picture-image']");
            if (!mounted)
                return;
            mounted.src = source;
            mounted.alt = picture.description || picture.filename;
        };
        pending.src = source;
    }
    /** Replace one render field without reconstructing its surrounding component. */
    #setText(role, value) {
        const element = this.querySelector(`[data-role='${role}']`);
        if (element)
            element.textContent = value;
    }
    /** Render the fullscreen viewer for the selected canonical picture. */
    #renderViewer(selected) {
        if (!this.#viewerOpen)
            return "";
        return `
            <section class="picture-viewer" role="dialog" aria-modal="true" aria-label="Visor fullscreen de ${escapeHtml(selected.filename)}">
                <strong class="picture-viewer-title">${escapeHtml(selected.filename)}</strong>
                <button class="picture-viewer-close" data-action="close-picture-viewer" aria-label="Cerrar visor">${icon("close")}</button>
                <div class="picture-viewer-zoom-fabs" aria-label="Controles de zoom">
                    <button data-action="viewer-zoom-in" aria-label="Acercar">${icon("plus")}</button>
                    <button data-action="viewer-zoom-out" aria-label="Alejar">${icon("minus")}</button>
                    <button data-action="viewer-reset" aria-label="Restablecer zoom y posicion">${icon("refresh")}</button>
                </div>
                <output class="picture-viewer-scale" data-role="viewer-scale">${Math.round(this.#viewerScale * 100)}%</output>
                <div class="picture-viewer-viewport" data-role="picture-viewer-viewport">
                    <img data-role="picture-viewer-image" src="${this.#api?.pictureUrl(selected.id) ?? ""}" alt="${escapeHtml(selected.description || selected.filename)}" draggable="false"
                        style="transform: translate3d(${this.#viewerX}px, ${this.#viewerY}px, 0) scale(${this.#viewerScale})">
                </div>
            </section>
        `;
    }
    /** Open the selected picture in the fullscreen viewer. */
    #openViewer() {
        const selected = this.#selected();
        if (!selected || this.#viewerOpen)
            return;
        this.#viewerOpen = true;
        this.#resetViewerState();
        this.querySelector(".pictures-console")?.insertAdjacentHTML("beforeend", this.#renderViewer(selected));
        this.#bindViewerEvents();
        requestAnimationFrame(() => this.querySelector("[data-action='close-picture-viewer']")?.focus());
    }
    /** Close the fullscreen viewer and return focus to the carousel image. */
    #closeViewer() {
        this.#viewerOpen = false;
        this.#viewerPointerId = null;
        if (this.#viewerScaleTimer !== null)
            clearTimeout(this.#viewerScaleTimer);
        this.#viewerScaleTimer = null;
        this.querySelector(".picture-viewer")?.remove();
        requestAnimationFrame(() => this.querySelector("[data-action='open-picture-viewer']")?.focus());
    }
    /** Clamp and apply one relative viewer zoom step. */
    #zoomViewer(delta) {
        this.#viewerScale = Math.min(8, Math.max(0.5, this.#viewerScale + delta));
        if (this.#viewerScale === 1) {
            this.#viewerX = 0;
            this.#viewerY = 0;
        }
        this.#applyViewerTransform(true);
    }
    /** Restore the fullscreen image transform. */
    #resetViewer() {
        this.#resetViewerState();
        this.#applyViewerTransform(true);
    }
    /** Reset viewer coordinates without causing a component render. */
    #resetViewerState() {
        this.#viewerScale = 1;
        this.#viewerX = 0;
        this.#viewerY = 0;
    }
    /** Apply the current pan and zoom state to the mounted fullscreen image. */
    #applyViewerTransform(showScale = false) {
        const image = this.querySelector("[data-role='picture-viewer-image']");
        if (image)
            image.style.transform = `translate3d(${this.#viewerX}px, ${this.#viewerY}px, 0) scale(${this.#viewerScale})`;
        const scale = this.querySelector("[data-role='viewer-scale']");
        if (scale)
            scale.value = `${Math.round(this.#viewerScale * 100)}%`;
        if (showScale)
            this.#showViewerScale();
    }
    /** Reveal the scale indicator and hide it three seconds after the latest zoom change. */
    #showViewerScale() {
        const scale = this.querySelector("[data-role='viewer-scale']");
        scale?.classList.add("is-visible");
        if (this.#viewerScaleTimer !== null)
            clearTimeout(this.#viewerScaleTimer);
        this.#viewerScaleTimer = setTimeout(() => {
            scale?.classList.remove("is-visible");
            this.#viewerScaleTimer = null;
        }, 3000);
    }
    /** Begin one mouse, pen, or touch panning gesture. */
    #startViewerPan(event, viewport) {
        this.#viewerPointerId = event.pointerId;
        this.#viewerPointerStart = { x: event.clientX, y: event.clientY, originX: this.#viewerX, originY: this.#viewerY };
        viewport.setPointerCapture(event.pointerId);
        viewport.classList.add("is-panning");
    }
    /** Continue the active panning gesture without rebuilding the carousel. */
    #moveViewerPan(event) {
        if (this.#viewerPointerId !== event.pointerId)
            return;
        this.#viewerX = this.#viewerPointerStart.originX + event.clientX - this.#viewerPointerStart.x;
        this.#viewerY = this.#viewerPointerStart.originY + event.clientY - this.#viewerPointerStart.y;
        this.#applyViewerTransform();
    }
    /** Finish the active panning gesture. */
    #endViewerPan(event, viewport) {
        if (this.#viewerPointerId !== event.pointerId)
            return;
        this.#viewerPointerId = null;
        if (viewport.hasPointerCapture(event.pointerId))
            viewport.releasePointerCapture(event.pointerId);
        viewport.classList.remove("is-panning");
    }
    /** Project dot-separated picture domains into the shared Explorer tree contract. */
    #domainTreeNodes() {
        const root = { label: "Todo", path: "", ownCount: 0, children: new Map() };
        Object.entries(this.#domains).forEach(([domain, count]) => {
            let parent = root;
            const parts = domain.split(".").filter(Boolean);
            parts.forEach((label, index) => {
                const path = parts.slice(0, index + 1).join(".");
                if (!parent.children.has(label)) {
                    parent.children.set(label, { label, path, ownCount: 0, children: new Map() });
                }
                parent = parent.children.get(label);
            });
            parent.ownCount += count;
        });
        const project = (node) => {
            const children = [...node.children.values()].map(project);
            const count = node.ownCount + children.reduce((total, child) => total + child.count, 0);
            return { id: `pictures:${node.path || "all"}`, path: node.path, label: node.label, icon: "folder", count, children };
        };
        return [project(root)];
    }
    /** Configure Pictures with the standardized structural tree component. */
    #configureDomainTree() {
        const tree = this.querySelector("[data-role='pictures-domain-tree']");
        if (!(tree instanceof StructureTree))
            return;
        tree.model = {
            nodes: this.#domainTreeNodes(),
            selectedPath: this.#domain,
            expandedPaths: this.#expandedDomains,
            toggleOnBranchSelect: true,
            title: "Pictures",
            toolbarActions: [{ id: "refresh", label: "Actualizar pictures", icon: "refresh" }],
            searchQuery: this.#search,
            searchPlaceholder: "Buscar pictures...",
            emptyText: this.#loading ? "Sincronizando pictures..." : "No hay dominios registrados.",
            defaultBranchIcon: "folder",
            defaultLeafIcon: "folder"
        };
        tree.addEventListener("brain-tree-select", event => {
            if (event.detail.clickedCaret)
                return;
            this.#domain = String(event.detail.path || "");
            this.#domainFocused = true;
            void this.#loadDomain(this.#domain);
        });
        tree.addEventListener("brain-tree-toolbar-action", event => {
            if (event.detail.action === "refresh")
                void this.#loadStructure(true);
        });
        tree.addEventListener("brain-tree-search", event => {
            this.#search = String(event.detail.query || "").trim();
        });
    }
    #bindEvents() {
        this.querySelector("[data-action='previous-picture']")?.addEventListener("click", () => this.#selectRelative(-1));
        this.querySelector("[data-action='next-picture']")?.addEventListener("click", () => this.#selectRelative(1));
        this.querySelectorAll("[data-picture-id]").forEach(button => button.addEventListener("click", () => {
            this.#selectPicture(button.getAttribute("data-picture-id") || "");
        }));
        this.querySelector("[data-action='save-picture-description']")?.addEventListener("click", () => void this.#saveDescription());
        this.querySelector("[data-action='open-picture-viewer']")?.addEventListener("click", () => this.#openViewer());
        this.#bindViewerEvents();
    }
    /** Bind controls owned only by a mounted fullscreen viewer. */
    #bindViewerEvents() {
        this.querySelector("[data-action='close-picture-viewer']")?.addEventListener("click", () => this.#closeViewer());
        this.querySelector("[data-action='viewer-zoom-in']")?.addEventListener("click", () => this.#zoomViewer(0.25));
        this.querySelector("[data-action='viewer-zoom-out']")?.addEventListener("click", () => this.#zoomViewer(-0.25));
        this.querySelector("[data-action='viewer-reset']")?.addEventListener("click", () => this.#resetViewer());
        const viewer = this.querySelector("[data-role='picture-viewer-viewport']");
        viewer?.addEventListener("wheel", event => {
            event.preventDefault();
            this.#zoomViewer(event.deltaY < 0 ? 0.25 : -0.25);
        }, { passive: false });
        viewer?.addEventListener("dblclick", () => this.#viewerScale === 1 ? this.#zoomViewer(1) : this.#resetViewer());
        viewer?.addEventListener("pointerdown", event => this.#startViewerPan(event, viewer));
        viewer?.addEventListener("pointermove", event => this.#moveViewerPan(event));
        viewer?.addEventListener("pointerup", event => this.#endViewerPan(event, viewer));
        viewer?.addEventListener("pointercancel", event => this.#endViewerPan(event, viewer));
    }
    async #saveDescription() {
        const selected = this.#selected();
        const textarea = this.querySelector("[data-role='picture-description']");
        if (!selected || !textarea || !this.#api)
            return;
        const response = await this.#api.describePicture(selected.id, textarea.value.trim());
        this.#state?.setLastResult(response);
        if (response.ok)
            await this.#loadDomain(this.#domain, true, selected.id);
    }
    #formatBytes(bytes) {
        if (bytes < 1024 * 1024)
            return `${Math.max(1, Math.round(bytes / 1024))} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
}
customElements.define(PicturesView.selector, PicturesView);

cache=(()=>{return { PicturesView: PicturesView };})();return cache;};})();
const __brainExplorerModule15=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 * @version: 1.0.0
 *
 * Small DOM helpers for safe Brain Explorer rendering.
 */
/**
 * Escape text before placing it inside HTML templates.
 *
 * @param {unknown} value Raw value to escape.
 * @returns {string} HTML-safe text.
 */
function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}
/**
 * Render JSON values with stable indentation.
 *
 * @param {unknown} value Value to render.
 * @returns {string} Pretty JSON or text fallback.
 */
function prettyJson(value) {
    if (value === undefined || value === null || value === "") {
        return "";
    }
    if (typeof value === "string") {
        return value;
    }
    try {
        return JSON.stringify(value, null, 2);
    }
    catch (_error) {
        return String(value);
    }
}
/**
 * Render code inside a Prism-compatible code block.
 *
 * @param {unknown} value Code or structured data.
 * @param {string} language Prism language id.
 * @returns {string} HTML code block.
 */
function codeBlock(value, language = "text") {
    const text = typeof value === "string" ? value : prettyJson(value);
    const safeLanguage = language.replace(/[^a-z0-9_-]/gi, "") || "text";
    return `<pre class="code-block language-${safeLanguage}"><code class="language-${safeLanguage}">${highlightCode(text, safeLanguage)}</code></pre>`;
}
/**
 * Render a conservative subset of Markdown for memory preview.
 *
 * @param {string} markdown Markdown source.
 * @returns {string} Rendered HTML.
 */
function renderMarkdown(markdown) {
    const trimmed = String(markdown || "").trim();
    if ((trimmed.startsWith("{") && trimmed.endsWith("}")) || (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
        return codeBlock(trimmed, "json");
    }
    if (trimmed.startsWith("#!") || trimmed.startsWith("import sys") || trimmed.startsWith("def main():")) {
        const lang = trimmed.includes("python") || trimmed.includes("py") || trimmed.startsWith("import sys") || trimmed.startsWith("def main():") ? "python" : "bash";
        return codeBlock(trimmed, lang);
    }
    const firstLines = trimmed.split(/\n/).slice(0, 10);
    const logMatchCount = firstLines.filter(line => line.match(/^\[(INFO|ERROR|WARNING|SUCCESS|WARN|FAIL|FATAL|OK)\]/i) ||
        line.match(/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}/)).length;
    if (logMatchCount >= 2 || (firstLines.length > 0 && logMatchCount === firstLines.length)) {
        return codeBlock(trimmed, "log");
    }
    const lines = String(markdown || "").split(/\r?\n/);
    const html = [];
    let paragraph = [];
    let list = [];
    let codeLines = [];
    let codeLanguage = "markdown";
    const flushParagraph = () => {
        if (!paragraph.length) {
            return;
        }
        html.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
        paragraph = [];
    };
    const flushList = () => {
        if (!list.length) {
            return;
        }
        html.push(`<ul>${list.map(item => `<li>${inlineMarkdown(item)}</li>`).join("")}</ul>`);
        list = [];
    };
    const flushCode = () => {
        if (!codeLines.length) {
            return;
        }
        html.push(codeBlock(codeLines.join("\n"), codeLanguage));
        codeLines = [];
        codeLanguage = "markdown";
    };
    let inCode = false;
    for (const line of lines) {
        const fence = line.match(/^```([a-z0-9_-]+)?\s*$/i);
        if (fence) {
            if (inCode) {
                flushCode();
                inCode = false;
            }
            else {
                flushParagraph();
                flushList();
                inCode = true;
                codeLanguage = fence[1] || "markdown";
            }
            continue;
        }
        if (inCode) {
            codeLines.push(line);
            continue;
        }
        if (!line.trim()) {
            flushParagraph();
            flushList();
            continue;
        }
        const heading = line.match(/^(#{1,4})\s+(.+)$/);
        if (heading) {
            flushParagraph();
            flushList();
            html.push(`<h${heading[1].length}>${inlineMarkdown(heading[2])}</h${heading[1].length}>`);
            continue;
        }
        const bullet = line.match(/^\s*[-*]\s+(.+)$/);
        if (bullet) {
            flushParagraph();
            list.push(bullet[1]);
            continue;
        }
        const quote = line.match(/^>\s+(.+)$/);
        if (quote) {
            flushParagraph();
            flushList();
            html.push(`<blockquote>${inlineMarkdown(quote[1])}</blockquote>`);
            continue;
        }
        paragraph.push(line.trim());
    }
    flushParagraph();
    flushList();
    flushCode();
    return html.join("");
}
/**
 * Convert a path-like value into a compact display label.
 *
 * @param {string} value Full path-like value.
 * @returns {string} Last path segment or the original value.
 */
function compactLabel(value) {
    const text = String(value || "");
    const parts = text.split(".");
    return parts[parts.length - 1] || text;
}
/**
 * Create an HTML option list from strings.
 *
 * @param {string[]} values Option values.
 * @param {string} selected Selected value.
 * @returns {string} HTML option tags.
 */
function optionTags(values, selected) {
    return values
        .map(value => `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(value)}</option>`)
        .join("");
}
function highlightCode(value, language) {
    const escaped = escapeHtml(value);
    const lang = String(language || "").toLowerCase();
    if (lang === "json" || lang === "javascript" || lang === "js" || lang === "typescript" || lang === "ts") {
        return escaped
            .replace(/(&quot;[^&]*?&quot;)(\s*:)?/g, (_match, stringValue, colon) => colon ? `<span class="token property">${stringValue}</span>${colon}` : `<span class="token string">${stringValue}</span>`)
            .replace(/\b(true|false|null)\b/g, `<span class="token boolean">$1</span>`)
            .replace(/\b(-?\d+(?:\.\d+)?)\b/g, `<span class="token number">$1</span>`)
            .replace(/\b(const|let|var|function|class|return|import|export|from|extends|super|new|this|typeof|async|await|if|else|for|while|do|switch|case|break|continue|default|try|catch|finally|throw)\b/g, `<span class="token keyword">$1</span>`);
    }
    if (lang === "python" || lang === "py") {
        return escaped
            .replace(/(&quot;&quot;&quot;[\s\S]*?&quot;&quot;&quot;|&#39;&#39;&#39;[\s\S]*?&#39;&#39;&#39;|&quot;[^&]*?&quot;|&#39;[^&]*?&#39;)/g, `<span class="token string">$1</span>`)
            .replace(/\b(True|False|None)\b/g, `<span class="token boolean">$1</span>`)
            .replace(/\b(-?\d+(?:\.\d+)?)\b/g, `<span class="token number">$1</span>`)
            .replace(/\b(def|class|return|import|from|as|global|nonlocal|lambda|yield|if|elif|else|for|while|break|continue|try|except|finally|raise|assert|with|pass|in|is|not|and|or)\b/g, `<span class="token keyword">$1</span>`);
    }
    if (lang === "bash" || lang === "shell" || lang === "powershell") {
        return escaped
            .replace(/(^|\n)(#.*)/g, `$1<span class="token comment">$2</span>`)
            .replace(/(&quot;.*?&quot;|'.*?')/g, `<span class="token string">$1</span>`)
            .replace(/\b(if|then|elif|else|fi|for|in|do|done|while|break|continue|return|function|exit)\b/g, `<span class="token keyword">$1</span>`);
    }
    if (lang === "log") {
        return escaped
            .replace(/(\[INFO\])/gi, `<span class="token info">$1</span>`)
            .replace(/(\[ERROR\]|\[FAIL\]|\[FATAL\])/gi, `<span class="token error">$1</span>`)
            .replace(/(\[WARNING\]|\[WARN\])/gi, `<span class="token warning">$1</span>`)
            .replace(/(\[SUCCESS\]|\[OK\])/gi, `<span class="token success">$1</span>`)
            .replace(/(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})/g, `<span class="token timestamp">$1</span>`);
    }
    return escaped;
}
function inlineMarkdown(value) {
    return escapeHtml(value)
        .replace(/`([^`]+)`/g, `<code>$1</code>`)
        .replace(/\*\*([^*]+)\*\*/g, `<strong>$1</strong>`)
        .replace(/\*([^*]+)\*/g, `<em>$1</em>`);
}

cache=(()=>{return { escapeHtml: escapeHtml, prettyJson: prettyJson, codeBlock: codeBlock, renderMarkdown: renderMarkdown, compactLabel: compactLabel, optionTags: optionTags };})();return cache;};})();
const __brainExplorerModule16=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */
const SVG_ICONS = {
    home: `<path d="M3 10.5 12 3l9 7.5"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/>`,
    database: `<ellipse cx="12" cy="5" rx="7" ry="3"/><path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5"/><path d="M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>`,
    graph: `<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="m8 7 7.8 8.7M16 7 8.2 15.7"/>`,
    search: `<circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/>`,
    messageCircle: `<path d="M21 11.5a8.5 8.5 0 0 1-9 8.5 9.5 9.5 0 0 1-4-.9L3 21l1.7-4.5A8.5 8.5 0 1 1 21 11.5Z"/>`,
    sliders: `<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>`,
    users: `<path d="M16 20v-2a4 4 0 0 0-8 0v2"/><circle cx="12" cy="8" r="4"/><path d="M22 20v-2a4 4 0 0 0-3-3.8"/><path d="M2 20v-2a4 4 0 0 1 3-3.8"/>`,
    document: `<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/>`,
    settings: `<circle cx="12" cy="12" r="3"/><path d="M19.4 15a8 8 0 0 0 .1-6l2-1.5-2-3.4-2.4 1a8 8 0 0 0-5.2-3L11.5 0h-4l-.4 2.2a8 8 0 0 0-5.2 3l-2.4-1-2 3.4 2 1.5a8 8 0 0 0 .1 6l-2 1.5 2 3.4 2.4-1a8 8 0 0 0 5.2 3l.4 2.1h4l.4-2.1a8 8 0 0 0 5.2-3l2.4 1 2-3.4z" transform="scale(.5) translate(12 12)"/>`,
    plus: `<path d="M12 5v14M5 12h14"/>`,
    documentPlus: `<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v5h5"/><path d="M12 12v6M9 15h6"/>`,
    folderPlus: `<path d="M3 6h7l2 2h9v11H3z"/><path d="M12 12v5M9.5 14.5h5"/>`,
    copy: `<rect x="8" y="8" width="11" height="11" rx="2"/><rect x="5" y="5" width="11" height="11" rx="2"/>`,
    trash: `<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 14h10l1-14"/><path d="M10 11v6M14 11v6"/>`,
    save: `<path d="M5 3h12l2 2v16H5z"/><path d="M8 3v6h8"/><path d="M8 21v-7h8v7"/>`,
    refresh: `<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v6h-6"/>`,
    pulse: `<path d="M3 12h4l2-6 4 12 2-6h6"/>`,
    folder: `<path d="M3 6h7l2 2h9v11H3z"/>`,
    moon: `<path d="M20 15.5A8 8 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5z"/>`,
    sun: `<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>`,
    terminal: `<path d="m4 7 5 5-5 5"/><path d="M12 19h8"/>`,
    close: `<path d="M6 6l12 12M18 6 6 18"/>`,
    collapseLeft: `<path d="m15 6-6 6 6 6"/><path d="M20 4v16"/>`,
    expandRight: `<path d="m9 6 6 6-6 6"/><path d="M4 4v16"/>`,
    eye: `<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z"/><circle cx="12" cy="12" r="3"/>`,
    edit: `<path d="M4 20h4l11-11-4-4L4 16z"/><path d="M13 6l4 4"/>`,
    filter: `<path d="M4 5h16l-6 7v5l-4 2v-7z"/>`,
    checkSquare: `<path d="M9 11l2 2 4-5"/><rect x="4" y="4" width="16" height="16" rx="3"/>`,
    chevronRight: `<path d="m9 6 6 6-6 6"/>`,
    chevronDown: `<path d="m6 9 6 6 6-6"/>`,
    minus: `<path d="M6 12h12"/>`,
    more: `<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>`,
    clock: `<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>`,
    camera: `<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>`,
    book: `<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><path d="M6 6h10M6 10h10M6 14h10"/>`,
    volume: `<path d="M5 9v6h4l5 4V5L9 9z"/><path d="M17 9a4 4 0 0 1 0 6"/><path d="M19.5 6.5a8 8 0 0 1 0 11"/>`,
    play: `<path d="m8 5 11 7-11 7z"/>`,
    pause: `<path d="M8 5v14M16 5v14"/>`,
    download: `<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>`
};
/**
 * Render a small stroked SVG icon.
 *
 * @param {string} name Icon name.
 * @returns {string} SVG markup.
 */
function icon(name) {
    const paths = SVG_ICONS[name] || SVG_ICONS.document;
    return `<svg class="svg-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;
}

cache=(()=>{return { icon: icon, SVG_ICONS: SVG_ICONS };})();return cache;};})();
const __brainExplorerModule17=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */
/** Build concise human feedback from one structured API response. */
function notificationText(payload, method, requestLabel = "") {
    const data = asRecord(payload.data);
    if (!payload.ok) {
        return { title: "No se pudo completar", message: readableError(payload, data) };
    }
    return { title: successTitle(data, method), message: successMessage(data, requestLabel) };
}
function successTitle(data, method) {
    const command = String(data.command || "");
    if (command.includes("delete") || method === "DELETE")
        return "Elemento eliminado";
    if (command.includes("add") || command.includes("create"))
        return "Elemento creado";
    if (typeof data.domain === "string" && typeof data.key === "string")
        return "Cambios guardados";
    if (command.includes("set") || command.includes("edit") || command.includes("save"))
        return "Cambios guardados";
    return "Operación completada";
}
function successMessage(data, requestLabel) {
    const command = String(data.command || "");
    const task = asRecord(data.task);
    if (Object.keys(task).length) {
        const title = quoted(task.title || task.id || "tarea");
        const status = String(task.status || "");
        if (command === "add-task")
            return `Se creó la tarea ${title}.`;
        if (command === "edit-task")
            return `Se actualizaron los datos de ${title}.`;
        if (status === "DONE")
            return `La tarea ${title} quedó completada.`;
        if (status === "WORKING")
            return `La tarea ${title} está en progreso.`;
        if (status === "TODO")
            return `La tarea ${title} volvió a pendientes.`;
    }
    if (command === "delete-task" || data.deleted === true) {
        return `Se eliminó la tarea ${quoted(data.taskId || "seleccionada")}.`;
    }
    if (typeof data.domain === "string" && typeof data.key === "string") {
        const entry = quoted(`${data.domain}.${data.key}`);
        return command.includes("delete") ? `Se eliminó la memoria ${entry}.` : `Se guardó la memoria ${entry}.`;
    }
    if (typeof data.domain === "string") {
        if (command.includes("delete"))
            return `Se eliminó el dominio ${quoted(data.domain)}.`;
        if (command.includes("add"))
            return `Se creó el dominio ${quoted(data.domain)}.`;
    }
    if (command === "clone-snippet")
        return `Se clonó el snippet ${quoted(data.snippet || "seleccionado")}.`;
    if (command === "register-project") {
        const project = asRecord(data.project);
        return `Se registró el proyecto ${quoted(project.name || project.path || "seleccionado")}.`;
    }
    if (command === "speak" || requestLabel.includes("voice"))
        return "La solicitud de voz fue procesada correctamente.";
    return humanString(data.message) || requestFallback(requestLabel);
}
function readableError(payload, data) {
    for (const candidate of [data.error, data.message, payload.error, payload.stderr]) {
        const message = humanString(candidate);
        if (message)
            return message;
    }
    return "La operación no pudo completarse. Revisa los datos e inténtalo de nuevo.";
}
function requestFallback(requestLabel) {
    const label = requestLabel.toLowerCase();
    if (label.includes("memory/entry"))
        return "La entrada de memoria fue actualizada.";
    if (label.includes("memory/domain"))
        return "El dominio de memoria fue actualizado.";
    if (label.includes("backlog/task"))
        return "La tarea fue actualizada.";
    if (label.includes("voice/replay"))
        return "La reproducción de voz comenzó.";
    if (label.includes("voice/pause"))
        return "La reproducción de voz se pausó.";
    return "Los cambios se aplicaron correctamente.";
}
/** Accept only plain human strings, never serialized JSON documents. */
function humanString(value) {
    if (typeof value !== "string")
        return "";
    const text = value.trim().replace(/^Error:\s*/i, "");
    if (!text || text.startsWith("{") || text.startsWith("["))
        return "";
    return text;
}
function asRecord(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value)
        ? value
        : {};
}
function quoted(value) {
    return `“${String(value || "").trim()}”`;
}

cache=(()=>{return { notificationText: notificationText };})();return cache;};})();
const __brainExplorerModule18=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */
var _a;


/**
 * A serializable node rendered by {@link StructureTree}.
 *
 * `path` is the public selection target. `id` can be used when two rendered
 * nodes refer to the same target path, such as a domain and one log entry.
 *
 * @typedef {object} StructureTreeNode
 * @property {string} id Stable rendered node identity.
 * @property {string} path Target path emitted in selection events.
 * @property {string} label Primary node label.
 * @property {string} [icon] SVG registry key.
 * @property {number|string} [count] Optional descendant count.
 * @property {string} [detail] Secondary compact detail.
 * @property {string} [timestamp] Timestamp for terminal log rows.
 * @property {"default"|"log"} [presentation] Node visual treatment.
 * @property {{id: string, label: string, icon?: string, danger?: boolean}[]} [actions] Context actions for this node.
 * @property {StructureTreeNode[]} [children] Descendants.
 */
/**
 * Shared structural tree for Explorer layouts.
 *
 * The element owns only local expand/collapse DOM state. Its consumer owns
 * data loading and reacts to `brain-tree-select` events, preventing a branch
 * gesture from rehydrating the active layout.
 */
class StructureTree extends HTMLElement {
    static get selector() {
        return "brain-structure-tree";
    }
    #model = {
        nodes: [],
        selectedPath: "",
        expandedPaths: new Set(),
        toggleOnBranchSelect: true,
        title: "",
        toolbarActions: [],
        showSearch: true,
        searchPlaceholder: "Buscar...",
        sortDirection: "asc",
        emptyText: "No hay elementos todavia."
    };
    #openActionNodeId = "";
    #searchQuery = "";
    #disableFilter = false;
    #onDocumentPointerDown = event => this.#closeMenusOutside(event);
    /**
     * Assign the full tree presentation model.
     *
     * @param {{nodes: StructureTreeNode[], selectedPath?: string, expandedPaths?: Set<string>, toggleOnBranchSelect?: boolean, title?: string, toolbarActions?: object[], searchQuery?: string, disableFilter?: boolean, showSearch?: boolean, searchPlaceholder?: string, sortDirection?: "asc"|"desc", emptyText?: string}} value Tree model.
     */
    set model(value) {
        this.#model = {
            nodes: Array.isArray(value?.nodes) ? value.nodes : [],
            selectedPath: value?.selectedPath || "",
            expandedPaths: value?.expandedPaths instanceof Set ? value.expandedPaths : new Set(),
            toggleOnBranchSelect: value?.toggleOnBranchSelect !== false,
            title: value?.title || "",
            toolbarActions: Array.isArray(value?.toolbarActions) ? value.toolbarActions : [],
            showSearch: value?.showSearch !== false,
            searchPlaceholder: value?.searchPlaceholder || "Buscar...",
            sortDirection: value?.sortDirection === "desc" ? "desc" : "asc",
            emptyText: value?.emptyText || "No hay elementos todavia."
        };
        if (typeof value?.searchQuery === "string") {
            this.#searchQuery = value.searchQuery;
        }
        this.#disableFilter = !!value?.disableFilter;
        this.#render();
    }
    /**
     * Render the initial empty element.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
        document.addEventListener("pointerdown", this.#onDocumentPointerDown);
    }
    /**
     * Release the document-level menu listener.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        document.removeEventListener("pointerdown", this.#onDocumentPointerDown);
    }
    #matchesFilter(node) {
        if (this.#disableFilter)
            return true;
        if (!this.#searchQuery)
            return true;
        const needle = this.#searchQuery.toLowerCase();
        if ((node.label || "").toLowerCase().includes(needle) || (node.path || "").toLowerCase().includes(needle)) {
            return true;
        }
        if (Array.isArray(node.children)) {
            return node.children.some(child => this.#matchesFilter(child));
        }
        return false;
    }
    #render() {
        const rootDirection = this.#model.sortDirection === "desc" ? -1 : 1;
        const sortedRootNodes = [...this.#model.nodes].sort((left, right) => {
            const leftHas = Array.isArray(left.children) && left.children.length > 0;
            const rightHas = Array.isArray(right.children) && right.children.length > 0;
            if (leftHas !== rightHas) {
                return leftHas ? -1 : 1;
            }
            return rootDirection * String(left.sortKey || left.label || "").localeCompare(String(right.sortKey || right.label || ""));
        });
        const visibleNodes = sortedRootNodes.filter(node => this.#matchesFilter(node));
        this.innerHTML = `
            ${this.#renderToolbar()}
            ${this.#model.showSearch ? `
                <label class="compact-search structure-tree-search">
                    ${icon("search")}
                    <input data-role="tree-filter" value="${escapeHtml(this.#searchQuery)}" placeholder="${escapeHtml(this.#model.searchPlaceholder)}">
                </label>
            ` : ""}
            <div class="structure-tree-nodes" role="tree">
                ${visibleNodes.length
            ? visibleNodes.map(node => this.#renderNode(node, 1)).join("")
            : `<p class="structure-tree-empty">${escapeHtml(this.#model.emptyText)}</p>`}
            </div>
        `;
        this.#bindEvents();
    }
    /**
     * Render the optional tree toolbar.
     *
     * @returns {string} Toolbar HTML.
     */
    #renderToolbar() {
        if (!this.#model.title && !this.#model.toolbarActions.length) {
            return "";
        }
        return `
            <header class="structure-tree-toolbar">
                ${this.#model.title ? `<strong>${escapeHtml(this.#model.title)}</strong>` : "<span></span>"}
                <div>
                    ${this.#model.toolbarActions.map(action => `
                    <button class="icon-action ${action.active ? "is-active" : ""}" data-tree-toolbar-action="${escapeHtml(action.id)}" title="${escapeHtml(action.label)}" aria-label="${escapeHtml(action.label)}" ${action.active !== undefined ? `aria-pressed="${String(!!action.active)}"` : ""}>
                            ${icon(action.icon || "more")}
                        </button>
                    `).join("")}
                </div>
            </header>
        `;
    }
    /**
     * Render one log tree node.
     *
     * @param {object} node Tree node.
     * @param {number} depth Tree depth.
     * @returns {string} Node HTML.
     */
    #renderNode(node, depth) {
        if (!this.#matchesFilter(node)) {
            return "";
        }
        const children = Array.isArray(node.children) ? node.children : [];
        const hasChildren = children.length > 0;
        const expanded = this.#model.expandedPaths.has(node.id || node.path);
        const active = node.path === this.#model.selectedPath;
        const sourceClass = node.color ? "tree-node--source" : "";
        const sourceStyle = node.color ? ` style="--tree-source-color: ${escapeHtml(node.color)};"` : "";
        const defaultBranch = this.#model.defaultBranchIcon || "folder";
        const defaultLeaf = this.#model.defaultLeafIcon || "document";
        if (node.presentation === "log" && !hasChildren) {
            return `
                <div class="tree-node-wrap" role="treeitem" aria-level="${depth}" aria-selected="${active}" style="--depth: ${depth};">
                    <div class="tree-item ${active ? "is-active" : ""}">
                        <button class="tree-node tree-terminal-log tree-node--leaf ${active ? "is-active" : ""}"
                            data-tree-id="${escapeHtml(node.id || node.path)}" data-tree-path="${escapeHtml(node.path)}" data-tree-branch="false"
                            title="${escapeHtml(node.label)}">
                            <span class="tree-node-icon">${icon(node.icon || defaultLeaf)}</span>
                            <time>${escapeHtml(node.timestamp || "Sin fecha")}</time>
                            <strong>${escapeHtml(node.label)}</strong>
                            <small>${escapeHtml(node.detail || "")}</small>
                            ${this.#renderNodeActionTrigger(node)}
                        </button>
                        ${this.#renderNodeActionMenu(node)}
                    </div>
                </div>
            `;
        }
        const childDirection = node.sortDirection === "desc" ? -1 : 1;
        const sortedChildren = [...children].sort((left, right) => {
            const leftHas = Array.isArray(left.children) && left.children.length > 0;
            const rightHas = Array.isArray(right.children) && right.children.length > 0;
            if (leftHas !== rightHas) {
                return leftHas ? -1 : 1;
            }
            return childDirection * String(left.sortKey || left.label || "").localeCompare(String(right.sortKey || right.label || ""));
        });
        return `
            <div class="tree-node-wrap" role="treeitem" aria-level="${depth}" ${hasChildren ? `aria-expanded="${expanded}"` : ""} aria-selected="${active}" style="--depth: ${depth};">
                <div class="tree-item ${active ? "is-active" : ""}">
                    <button class="tree-node ${hasChildren ? "" : "tree-node--leaf"} ${sourceClass} ${active ? "is-active" : ""}"${sourceStyle}
                        data-tree-id="${escapeHtml(node.id || node.path)}" data-tree-path="${escapeHtml(node.path)}" data-tree-branch="${hasChildren}"
                        title="${escapeHtml(node.label)}">
                        ${hasChildren ? `<span class="tree-caret">${icon(expanded ? "chevronDown" : "chevronRight")}</span>` : ""}
                        ${icon(node.icon || (hasChildren ? defaultBranch : defaultLeaf))}
                        <span>${escapeHtml(node.label)}</span>
                        ${node.count !== undefined ? `<small>${escapeHtml(String(node.count))}</small>` : ""}
                        ${this.#renderNodeActionTrigger(node)}
                    </button>
                    ${this.#renderNodeActionMenu(node)}
                </div>
                ${hasChildren ? `<div class="tree-children" role="group" ${expanded ? "" : "hidden"}>${sortedChildren.map(child => this.#renderNode(child, depth + 1)).join("")}</div>` : ""}
            </div>
        `;
    }
    /**
     * Render the contextual action trigger inside the actual tree item button.
     *
     * @param {StructureTreeNode} node Tree node.
     * @returns {string} Trigger HTML.
     */
    #renderNodeActionTrigger(node) {
        if (!node.actions?.length) {
            return "";
        }
        const nodeId = escapeHtml(node.id || node.path);
        return `
            <span class="tree-action-trigger" data-tree-actions="${nodeId}" title="Acciones" aria-label="Acciones">
                ${icon("more")}
            </span>
        `;
    }
    /**
     * Render the menu that belongs to an open item action trigger.
     *
     * @param {StructureTreeNode} node Tree node.
     * @returns {string} Action menu HTML.
     */
    #renderNodeActionMenu(node) {
        const nodeId = node.id || node.path;
        if (!node.actions?.length || this.#openActionNodeId !== nodeId) {
            return "";
        }
        return `
            <div class="tree-node-menu action-menu-panel" role="menu">
                ${node.actions.map(action => `
                    <button class="${action.danger ? "danger-button" : ""}" data-tree-action="${escapeHtml(action.id)}" data-tree-action-node="${escapeHtml(nodeId)}">
                        ${icon(action.icon || "more")}${escapeHtml(action.label)}
                    </button>
                `).join("")}
            </div>
        `;
    }
    /**
     * Bind node selection and local expansion handlers.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelectorAll("[data-tree-id]").forEach(button => {
            button.addEventListener("click", event => this.#onNodeClicked(button, event));
        });
        this.querySelectorAll("[data-tree-toolbar-action]").forEach(button => {
            button.addEventListener("click", () => this.#emitToolbarAction(button));
        });
        this.querySelectorAll("[data-tree-actions]").forEach(trigger => {
            trigger.addEventListener("click", event => this.#toggleNodeActionMenu(trigger, event));
        });
        this.querySelectorAll("[data-tree-action]").forEach(button => {
            button.addEventListener("click", () => this.#emitNodeAction(button));
        });
        // Filter Input Event
        const filterInput = this.querySelector("[data-role='tree-filter']");
        filterInput?.addEventListener("input", event => {
            this.#searchQuery = event.target.value;
            // Render only nodes container to keep focus and cursor position!
            const rootDirection = this.#model.sortDirection === "desc" ? -1 : 1;
            const sortedRootNodes = [...this.#model.nodes].sort((left, right) => {
                const leftHas = Array.isArray(left.children) && left.children.length > 0;
                const rightHas = Array.isArray(right.children) && right.children.length > 0;
                if (leftHas !== rightHas) {
                    return leftHas ? -1 : 1;
                }
                return rootDirection * String(left.sortKey || left.label || "").localeCompare(String(right.sortKey || right.label || ""));
            });
            const nodesContainer = this.querySelector(".structure-tree-nodes");
            if (nodesContainer) {
                nodesContainer.innerHTML = sortedRootNodes.map(node => this.#renderNode(node, 1)).join("");
            }
            // Re-bind listeners on new node elements!
            this.querySelectorAll("[data-tree-id]").forEach(button => {
                button.addEventListener("click", ev => this.#onNodeClicked(button, ev));
            });
            this.querySelectorAll("[data-tree-actions]").forEach(trigger => {
                trigger.addEventListener("click", ev => this.#toggleNodeActionMenu(trigger, ev));
            });
            // Emit search query event to parent view
            this.dispatchEvent(new CustomEvent("brain-tree-search", {
                bubbles: true,
                detail: { query: this.#searchQuery }
            }));
        });
    }
    /**
     * Handle one structural gesture without fetching or rehydrating the tree.
     *
     * @param {Element} button Trigger button.
     * @param {MouseEvent} event Native click event.
     * @returns {void}
     */
    #onNodeClicked(button, event) {
        if (event.target.closest("[data-tree-actions]")) {
            return;
        }
        const id = button.getAttribute("data-tree-id") || "";
        const path = button.getAttribute("data-tree-path") || "";
        const branch = button.getAttribute("data-tree-branch") === "true";
        const clickedCaret = Boolean(event.target.closest(".tree-caret"));
        const scrollTop = button.closest(".structure-tree-nodes")?.scrollTop || 0;
        let expanded = this.#model.expandedPaths.has(id);
        if (branch && (clickedCaret || this.#model.toggleOnBranchSelect)) {
            expanded = !expanded;
            this.#setExpanded(button, id, expanded);
        }
        const node = this.#findNode(this.#model.nodes, id);
        this.dispatchEvent(new CustomEvent("brain-tree-select", {
            bubbles: true,
            detail: { id, path, branch, expanded, clickedCaret, node }
        }));
        this.#restoreInteractionAnchor(id, scrollTop);
    }
    /**
     * Restore the node that initiated a gesture after a consumer re-renders
     * and replaces the shared tree synchronously.
     *
     * @param {string} id Stable rendered node identity.
     * @param {number} scrollTop Previous tree scroll offset.
     * @returns {void}
     */
    #restoreInteractionAnchor(id, scrollTop) {
        requestAnimationFrame(() => {
            const trees = document.querySelectorAll(_a.selector);
            for (const tree of trees) {
                const button = Array.from(tree.querySelectorAll("[data-tree-id]"))
                    .find(candidate => candidate.getAttribute("data-tree-id") === id);
                if (!button) {
                    continue;
                }
                const container = tree.querySelector(".structure-tree-nodes");
                if (container) {
                    container.scrollTop = scrollTop;
                }
                button.focus({ preventScroll: true });
                return;
            }
        });
    }
    /**
     * Toggle descendant visibility and maintain the supplied expansion set.
     *
     * @param {Element} button Branch button.
     * @param {string} id Node identity.
     * @param {boolean} expanded Next expansion state.
     * @returns {void}
     */
    #setExpanded(button, id, expanded) {
        if (expanded) {
            this.#model.expandedPaths.add(id);
        }
        else {
            this.#model.expandedPaths.delete(id);
        }
        const childContainer = button.closest(".tree-node-wrap")?.querySelector(":scope > .tree-children");
        if (childContainer) {
            childContainer.hidden = !expanded;
        }
        const caret = button.querySelector(".tree-caret");
        if (caret) {
            caret.innerHTML = icon(expanded ? "chevronDown" : "chevronRight");
        }
        this.dispatchEvent(new CustomEvent("brain-tree-toggle", {
            bubbles: true,
            detail: { id, expanded }
        }));
    }
    /**
     * Emit one toolbar action for the mounted domain.
     *
     * @param {Element} button Trigger button.
     * @returns {void}
     */
    #emitToolbarAction(button) {
        this.dispatchEvent(new CustomEvent("brain-tree-toolbar-action", {
            bubbles: true,
            detail: { action: button.getAttribute("data-tree-toolbar-action") || "" }
        }));
    }
    /**
     * Emit one contextual node action.
     *
     * @param {Element} button Trigger button.
     * @returns {void}
     */
    #emitNodeAction(button) {
        const id = button.getAttribute("data-tree-action-node") || "";
        this.#openActionNodeId = "";
        this.dispatchEvent(new CustomEvent("brain-tree-action", {
            bubbles: true,
            detail: {
                action: button.getAttribute("data-tree-action") || "",
                node: this.#findNode(this.#model.nodes, id)
            }
        }));
    }
    /**
     * Close contextual menus when the gesture happens outside the tree.
     *
     * @param {PointerEvent} event Pointer interaction.
     * @returns {void}
     */
    #closeMenusOutside(event) {
        if (!this.#openActionNodeId || this.contains(event.target)) {
            return;
        }
        this.#openActionNodeId = "";
        this.#render();
    }
    /**
     * Toggle the contextual menu anchored to an item-local action trigger.
     *
     * @param {Element} trigger Action trigger.
     * @param {MouseEvent} event Native click event.
     * @returns {void}
     */
    #toggleNodeActionMenu(trigger, event) {
        event.preventDefault();
        event.stopPropagation();
        const nodeId = trigger.getAttribute("data-tree-actions") || "";
        this.#openActionNodeId = this.#openActionNodeId === nodeId ? "" : nodeId;
        this.#render();
    }
    /**
     * Resolve one node by rendered identity.
     *
     * @param {StructureTreeNode[]} nodes Candidate nodes.
     * @param {string} id Rendered identity.
     * @returns {StructureTreeNode|null} Matching node.
     */
    #findNode(nodes, id) {
        for (const node of nodes) {
            if ((node.id || node.path) === id) {
                return node;
            }
            const found = this.#findNode(node.children || [], id);
            if (found) {
                return found;
            }
        }
        return null;
    }
}
_a = StructureTree;
customElements.define(StructureTree.selector, StructureTree);

cache=(()=>{return { StructureTree: StructureTree };})();return cache;};})();
const __brainExplorerModule19=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule15();
const { icon } = __brainExplorerModule16();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */


/**
 * BacklogPip is a self-contained component designed to live inside
 * a Document Picture-in-Picture window. It renders grouped tasks
 * with expandable details, and manages an inline task creation form.
 *
 * @element brain-backlog-pip
 */
class BacklogPip extends HTMLElement {
    static get selector() {
        return "brain-backlog-pip";
    }
    #tasks = [];
    #expandedIds = new Set();
    #eventsBound = false;
    #isFormOpen = false;
    #isSubmitting = false;
    #formError = "";
    #formDraft = { title: "", description: "", priority: "HIGH" };
    #pipImageDataUrl = null;
    #pipMarkingRects = [];
    /**
     * Callback invoked when a screen capture is requested.
     * Must return a Promise resolving to a base64 image data URL.
     *
     * @type {(() => Promise<string | null>) | null}
     */
    onCaptureScreen = null;
    /**
     * Callback invoked when a new task is created.
     *
     * The resolved result carries the refreshed task list so the PiP owns
     * its transition back to the list after a successful mutation.
     *
     * @type {((taskData: { title: string; description: string; priority: string; image: string | null }) => Promise<{ ok: boolean; tasks?: object[]; message?: string }>) | null}
     */
    onAddTask = null;
    /**
     * Set the task list and re-render.
     *
     * @param {object[]} tasks Parsed task array from BacklogView.
     */
    set tasks(tasks) {
        this.#tasks = Array.isArray(tasks) ? tasks : [];
        if (!this.#isFormOpen) {
            this.#render();
        }
    }
    connectedCallback() {
        this.#bindEvents();
        this.#render();
    }
    #render() {
        if (this.#isFormOpen) {
            this.#renderForm();
        }
        else {
            this.#renderList();
        }
    }
    #renderList() {
        this.innerHTML = `
            <div class="pip-root" style="display: flex; flex-direction: column; height: 100vh; font-family: var(--font); background: var(--bg); color: var(--text);">
                <header class="pip-header" style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong class="pip-title" style="font-size: 14px; color: var(--text-strong); display: flex; align-items: center; gap: 6px;">
                        ${icon("checkSquare")} Backlog PIP
                    </strong>
                    <span class="pip-count" style="font-size: 12px; color: var(--text-muted); margin-left: auto; margin-right: 12px;">
                        ${this.#tasks.length} tareas
                    </span>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <button class="icon-action" data-action="pip-capture-screen" title="Capturar pantalla y crear tarea" style="border: 0; background: transparent; cursor: pointer; color: var(--primary);">${icon("camera")}</button>
                        <button class="icon-action" data-action="pip-add-task" title="Crear tarea" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("plus")}</button>
                    </div>
                </header>
                <main class="pip-body scroll-area" style="flex: 1; overflow-y: auto; padding: 12px; display: grid; gap: 10px; background: color-mix(in srgb, var(--bg), transparent 40%);">
                    ${this.#renderGroups()}
                </main>
            </div>
        `;
    }
    #renderForm() {
        this.innerHTML = `
            <div class="pip-root" style="display: flex; flex-direction: column; height: 100vh; font-family: var(--font); background: var(--bg); color: var(--text);">
                <header class="pip-header" style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong class="pip-title" style="font-size: 14px; color: var(--text-strong); display: flex; align-items: center; gap: 6px;">
                        ${icon("plus")} Nueva Tarea (PIP)
                    </strong>
                    <button class="icon-action" data-action="pip-close-form" title="Volver" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
                </header>
                <form class="pip-add-form" style="padding: 12px; display: flex; flex-direction: column; gap: 8px; flex: 1; overflow-y: auto; background: var(--bg);">
                    <input type="text" id="pip-title-input" placeholder="Título" required style="padding: 6px 8px; font-size: 13px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface-strong); color: var(--text-strong);">
                    <select id="pip-priority-select" style="padding: 6px; font-size: 13px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface-strong); color: var(--text-strong);">
                        <option value="HIGH">HIGH</option>
                        <option value="MEDIUM">MEDIUM</option>
                        <option value="LOW">LOW</option>
                    </select>
                    <textarea id="pip-desc-input" placeholder="Descripción (usa Ctrl+V para pegar imagen)" required style="padding: 6px 8px; font-size: 13px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface-strong); color: var(--text-strong); min-height: 80px; resize: vertical;"></textarea>
                    
                    <button type="button" class="ghost-action compact-action" data-action="pip-form-capture" style="display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-size: 12px; height: 32px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface-muted); color: var(--primary);">
                        ${icon("camera")} Capturar Referencia Visual
                    </button>

                    ${this.#pipImageDataUrl ? `
                        <div style="display: flex; flex-direction: column; gap: 6px; border: 1px solid var(--border); padding: 8px; border-radius: 6px; background: var(--surface);">
                            <div class="marking-container" style="position: relative; display: inline-block; max-width: 100%;">
                                <img id="pip-preview-img" src="${this.#pipImageDataUrl}" style="max-width: 100%; display: block; max-height: 200px; object-fit: contain;">
                                <svg id="pip-marking-svg" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; cursor: crosshair; touch-action: none;"></svg>
                            </div>
                            <div style="display: flex; gap: 8px; align-items: center; justify-content: space-between;">
                                <button type="button" class="ghost-action compact-action" data-action="pip-clear-marks" style="padding: 4px 8px; font-size: 11px;">Limpiar</button>
                                <select id="pip-mark-color" style="padding: 2px 6px; font-size: 11px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface); color: var(--text-strong);">
                                    <option value="red" selected>Rojo</option>
                                    <option value="blue">Azul</option>
                                    <option value="green">Verde</option>
                                    <option value="yellow">Amarillo</option>
                                    <option value="magenta">Rosa</option>
                                </select>
                            </div>
                        </div>
                    ` : ""}
                    
                    ${this.#formError ? `<p role="alert" style="margin: 0; font-size: 12px; color: var(--danger);">${escapeHtml(this.#formError)}</p>` : ""}
                    <button type="submit" class="primary-action" ${this.#isSubmitting ? "disabled" : ""} style="padding: 8px; font-size: 13px; font-weight: bold; border-radius: 4px; margin-top: auto;">${this.#isSubmitting ? "Creando..." : "Crear Tarea"}</button>
                </form>
            </div>
        `;
        this.#bindFormEvents();
        this.#restoreFormDraft();
    }
    /**
     * Save active creation form values before an asynchronous operation.
     *
     * @returns {void}
     */
    #captureFormDraft() {
        const title = this.querySelector("#pip-title-input");
        const description = this.querySelector("#pip-desc-input");
        const priority = this.querySelector("#pip-priority-select");
        if (title instanceof HTMLInputElement) {
            this.#formDraft.title = title.value;
        }
        if (description instanceof HTMLTextAreaElement) {
            this.#formDraft.description = description.value;
        }
        if (priority instanceof HTMLSelectElement) {
            this.#formDraft.priority = priority.value;
        }
    }
    /**
     * Restore creation form values after its DOM has been re-rendered.
     *
     * @returns {void}
     */
    #restoreFormDraft() {
        const title = this.querySelector("#pip-title-input");
        const description = this.querySelector("#pip-desc-input");
        const priority = this.querySelector("#pip-priority-select");
        if (title instanceof HTMLInputElement) {
            title.value = this.#formDraft.title;
        }
        if (description instanceof HTMLTextAreaElement) {
            description.value = this.#formDraft.description;
        }
        if (priority instanceof HTMLSelectElement) {
            priority.value = this.#formDraft.priority;
        }
    }
    /**
     * Clear form-only values after dismissal or successful task creation.
     *
     * @returns {void}
     */
    #resetFormDraft() {
        this.#formDraft = { title: "", description: "", priority: "HIGH" };
        this.#formError = "";
    }
    #renderGroups() {
        if (!this.#tasks.length) {
            return `<p class="pip-empty" style="text-align: center; color: var(--text-muted); padding: 24px;">No hay tareas.</p>`;
        }
        const groups = new Map();
        for (const task of this.#tasks) {
            const list = groups.get(task.domain) || [];
            list.push(task);
            groups.set(task.domain, list);
        }
        const sections = [];
        const sortedDomains = Array.from(groups.keys()).sort();
        for (const domain of sortedDomains) {
            const tasks = groups.get(domain);
            sections.push(`
                <section class="pip-group" style="margin-bottom: 10px;">
                    <h2 class="pip-domain-label" style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--primary); margin-bottom: 4px; border-bottom: 1px solid var(--border); padding-bottom: 2px;">
                        ${escapeHtml(domain)}
                    </h2>
                    <div class="pip-task-list" style="display: grid; gap: 4px;">
                        ${tasks.map(task => this.#renderTask(task)).join("")}
                    </div>
                </section>
            `);
        }
        return sections.join("");
    }
    #renderTask(task) {
        const expanded = this.#expandedIds.has(task.id);
        const statusIcon = task.done
            ? icon("checkSquare")
            : (task.status === "WORKING"
                ? `
                    <div class="working-spinner" style="vertical-align: middle;">
                        <span class="dot dot-blue"></span>
                        <span class="dot dot-cyan"></span>
                        <span class="dot dot-green"></span>
                        <span class="dot dot-yellow"></span>
                        <span class="dot dot-red"></span>
                        <span class="dot dot-pink"></span>
                    </div>
                `
                : icon("clock"));
        const priorityClass = task.done
            ? "pip-done"
            : `pip-priority-${String(task.priority).toLowerCase()}`;
        return `
            <div class="pip-task ${priorityClass} ${expanded ? "is-expanded" : ""}" data-pip-task-id="${escapeHtml(task.id)}" style="display: flex; flex-direction: column; background: var(--surface); border-radius: 6px; border: 1px solid var(--border); overflow: hidden;">
                <button class="pip-task-row" data-pip-toggle="${escapeHtml(task.id)}" style="display: flex; align-items: center; gap: 6px; padding: 6px 8px; width: 100%; border: 0; background: transparent; cursor: pointer; text-align: left; font-size: 12px; color: var(--text-strong);">
                    <span class="pip-task-icon" style="display: flex; align-items: center; justify-content: center; width: 18px; height: 18px;">${statusIcon}</span>
                    <span class="pip-task-title" style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-strong); ${task.done ? 'text-decoration: line-through; opacity: 0.6;' : ''}">${escapeHtml(task.title)}</span>
                    <span class="pip-task-chevron" style="display: flex; align-items: center; justify-content: center; width: 18px; height: 18px; color: var(--text-muted);">${icon(expanded ? "chevronDown" : "chevronRight")}</span>
                </button>
                ${expanded ? `
                    <div class="pip-task-detail" style="padding: 6px 8px 8px 8px; border-top: 1px solid var(--border); background: color-mix(in srgb, var(--bg), transparent 60%); font-size: 11px; color: var(--text);">
                        <span style="font-weight: bold; color: var(--primary); margin-right: 8px;">${escapeHtml(task.id)}</span>
                        <span style="background: var(--surface-strong); padding: 1px 4px; border-radius: 3px; font-size: 10px; font-weight: bold;">${escapeHtml(String(task.priority).toUpperCase())}</span>
                        ${task.description ? `<p class="pip-task-desc" style="margin-top: 4px; line-height: 1.4; white-space: pre-wrap;">${escapeHtml(task.description)}</p>` : ""}
                    </div>
                ` : ""}
            </div>
        `;
    }
    #bindEvents() {
        if (this.#eventsBound)
            return;
        this.#eventsBound = true;
        this.addEventListener("click", async (event) => {
            const toggle = event.target.closest("[data-pip-toggle]");
            if (toggle) {
                const id = toggle.dataset.pipToggle;
                if (this.#expandedIds.has(id)) {
                    this.#expandedIds.delete(id);
                }
                else {
                    this.#expandedIds.add(id);
                }
                this.#render();
                return;
            }
            const addBtn = event.target.closest("[data-action='pip-add-task']");
            if (addBtn) {
                this.#isFormOpen = true;
                this.#resetFormDraft();
                this.#pipImageDataUrl = null;
                this.#pipMarkingRects = [];
                this.#render();
                return;
            }
            const captureBtn = event.target.closest("[data-action='pip-capture-screen']");
            if (captureBtn) {
                if (this.onCaptureScreen) {
                    const dataUrl = await this.onCaptureScreen();
                    if (dataUrl) {
                        this.#isFormOpen = true;
                        this.#resetFormDraft();
                        this.#pipImageDataUrl = dataUrl;
                        this.#pipMarkingRects = [];
                        this.#render();
                    }
                }
            }
        });
    }
    #bindFormEvents() {
        const form = this.querySelector(".pip-add-form");
        if (!form)
            return;
        // Close Form
        this.querySelector("[data-action='pip-close-form']")?.addEventListener("click", () => {
            this.#isFormOpen = false;
            this.#resetFormDraft();
            this.#render();
        });
        // Form Screen Capture
        this.querySelector("[data-action='pip-form-capture']")?.addEventListener("click", async () => {
            if (this.onCaptureScreen) {
                this.#captureFormDraft();
                const dataUrl = await this.onCaptureScreen();
                if (dataUrl) {
                    this.#pipImageDataUrl = dataUrl;
                    this.#pipMarkingRects = [];
                    this.#render();
                }
            }
        });
        // Clipboard Paste Listener
        const descInput = this.querySelector("#pip-desc-input");
        descInput?.addEventListener("paste", event => {
            const items = event.clipboardData?.items;
            if (!items)
                return;
            for (const item of items) {
                if (item.type.startsWith("image/")) {
                    event.preventDefault();
                    const file = item.getAsFile();
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = ev => {
                            this.#pipImageDataUrl = ev.target.result;
                            this.#pipMarkingRects = [];
                            this.#render();
                            // Insert {ref_image} tag
                            const start = descInput.selectionStart;
                            const end = descInput.selectionEnd;
                            const val = descInput.value;
                            descInput.value = val.slice(0, start) + "{ref_image}" + val.slice(end);
                            descInput.selectionStart = descInput.selectionEnd = start + "{ref_image}".length;
                        };
                        reader.readAsDataURL(file);
                    }
                    break;
                }
            }
        });
        // Image marking canvas interaction
        this.#bindFormImageMarking();
        // Submit form
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            this.#captureFormDraft();
            const title = this.#formDraft.title.trim();
            const description = this.#formDraft.description.trim();
            const priority = this.#formDraft.priority;
            let bakedImage = null;
            if (this.#pipImageDataUrl) {
                try {
                    bakedImage = await this.#bakeMarkedImage();
                }
                catch (e) {
                    console.error("Error baking PiP image:", e);
                }
            }
            if (!this.onAddTask || this.#isSubmitting) {
                return;
            }
            this.#isSubmitting = true;
            this.#formError = "";
            const submitButton = form.querySelector("[type='submit']");
            if (submitButton instanceof HTMLButtonElement) {
                submitButton.disabled = true;
                submitButton.textContent = "Creando...";
            }
            try {
                const completion = await this.onAddTask({ title, description, priority, image: bakedImage });
                if (!completion?.ok) {
                    this.#formError = completion?.message || "No se pudo crear la tarea.";
                    return;
                }
                if (Array.isArray(completion.tasks)) {
                    this.#tasks = completion.tasks;
                }
                this.#isFormOpen = false;
                this.#resetFormDraft();
                this.#pipImageDataUrl = null;
                this.#pipMarkingRects = [];
            }
            catch (error) {
                this.#formError = error instanceof Error ? error.message : "No se pudo crear la tarea.";
            }
            finally {
                this.#isSubmitting = false;
                this.#render();
            }
        });
    }
    #bindFormImageMarking() {
        const svg = this.querySelector("#pip-marking-svg");
        const img = this.querySelector("#pip-preview-img");
        if (!svg || !img)
            return;
        let startX = 0, startY = 0;
        let isDrawing = false;
        let activeRect = null;
        svg.addEventListener("pointerdown", e => {
            e.preventDefault();
            const bounds = svg.getBoundingClientRect();
            startX = e.clientX - bounds.left;
            startY = e.clientY - bounds.top;
            isDrawing = true;
            activeRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
            const colorSelect = this.querySelector("#pip-mark-color");
            const selectedColor = colorSelect ? colorSelect.value : "red";
            activeRect.setAttribute("stroke", selectedColor);
            activeRect.setAttribute("stroke-width", "3");
            activeRect.setAttribute("fill", "none");
            svg.appendChild(activeRect);
        });
        svg.addEventListener("pointermove", e => {
            if (!isDrawing)
                return;
            const bounds = svg.getBoundingClientRect();
            const curX = e.clientX - bounds.left;
            const curY = e.clientY - bounds.top;
            const x = Math.min(startX, curX);
            const y = Math.min(startY, curY);
            const w = Math.abs(startX - curX);
            const h = Math.abs(startY - curY);
            activeRect.setAttribute("x", String(x));
            activeRect.setAttribute("y", String(y));
            activeRect.setAttribute("width", String(w));
            activeRect.setAttribute("height", String(h));
        });
        svg.addEventListener("pointerup", e => {
            if (!isDrawing)
                return;
            isDrawing = false;
            const bounds = svg.getBoundingClientRect();
            const curX = e.clientX - bounds.left;
            const curY = e.clientY - bounds.top;
            const x = Math.min(startX, curX);
            const y = Math.min(startY, curY);
            const w = Math.abs(startX - curX);
            const h = Math.abs(startY - curY);
            if (w > 4 && h > 4) {
                const colorSelect = this.querySelector("#pip-mark-color");
                const selectedColor = colorSelect ? colorSelect.value : "red";
                this.#pipMarkingRects.push({
                    x: x / bounds.width,
                    y: y / bounds.height,
                    w: w / bounds.width,
                    h: h / bounds.height,
                    color: selectedColor
                });
                // Index number label in SVG
                const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
                text.setAttribute("x", String(x + w - 6));
                text.setAttribute("y", String(y + h - 6));
                text.setAttribute("fill", selectedColor);
                text.setAttribute("font-size", "12");
                text.setAttribute("font-weight", "bold");
                text.setAttribute("text-anchor", "end");
                text.textContent = String(this.#pipMarkingRects.length);
                svg.appendChild(text);
            }
            else {
                activeRect.remove();
            }
        });
        this.querySelector("[data-action='pip-clear-marks']")?.addEventListener("click", e => {
            e.stopPropagation();
            this.#pipMarkingRects = [];
            svg.innerHTML = "";
        });
    }
    async #bakeMarkedImage() {
        const img = this.querySelector("#pip-preview-img");
        if (!img)
            return null;
        if (!img.complete) {
            await new Promise(resolve => img.onload = resolve);
        }
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0);
        this.#pipMarkingRects.forEach((r, i) => {
            ctx.strokeStyle = r.color || "red";
            ctx.lineWidth = 3;
            ctx.strokeRect(r.x * img.naturalWidth, r.y * img.naturalHeight, r.w * img.naturalWidth, r.h * img.naturalHeight);
            // Draw number label
            ctx.fillStyle = r.color || "red";
            ctx.font = "bold 16px sans-serif";
            ctx.textBaseline = "bottom";
            ctx.textAlign = "right";
            ctx.fillText(String(i + 1), (r.x + r.w) * img.naturalWidth - 6, (r.y + r.h) * img.naturalHeight - 6);
        });
        return canvas.toDataURL("image/png");
    }
}
customElements.define(BacklogPip.selector, BacklogPip);

cache=(()=>{return { BacklogPip: BacklogPip };})();return cache;};})();
__brainExplorerModule0();
