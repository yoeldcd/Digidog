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
    /**
     * Completed cacheable responses indexed by normalized HTTP method and path.
     * @type {Map<string, CacheRecord>}
     */
    #cache = new Map();
    /**
     * In-flight cacheable requests shared by concurrent callers of the same path.
     * @type {Map<string, Promise<ApiResponse<unknown>>>}
     */
    #inFlight = new Map();
    /**
     * Default lifetime applied to cacheable GET responses in milliseconds.
     * @type {number}
     */
    #defaultTtlMs = 45_000;
    /**
     * Explicit workspace header override, or `null` to use the server default.
     * @type {string | null}
     */
    #workspaceRootOverride = null;
    /**
     * Select the workspace header applied to subsequent requests and invalidate stale cache state.
     *
     * @param {string | null} path Canonical workspace root, or `null` to restore server-side workspace selection.
     * @returns {void} Nothing; both completed and in-flight cache registries are cleared synchronously.
     */
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the health request.
     * @returns {Promise<ApiResponse<HealthStatus>>} Health payload.
     */
    async health(options = {}) {
        const response = await this.request("/api/health", options);
        return normalizeDirectResponse(response, isHealthStatus);
    }
    /**
     * Read registered projects.
     *
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the project-registry request.
     * @returns {Promise<ApiResponse<ProjectsResponse>>} Projects list payload.
     */
    async getProjects(options = {}) {
        const response = await this.request("/api/projects", options);
        return normalizeDirectResponse(response, isProjectsResponse);
    }
    /**
     * Read detected subproject wikis.
     *
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the wiki-registry request.
     * @returns {Promise<ApiResponse<WikisResponse>>} Wikis list.
     */
    async getWikis(options = {}) {
        const response = await this.request("/api/wikis", options);
        return normalizeDirectResponse(response, isWikisResponse);
    }
    /**
     * Read persisted paid-voice messages and their transcript sessions.
     *
     * @param {QueryParams} params Optional server-side session, date, or pagination query values.
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the message request.
     * @returns {Promise<ApiResponse<VoiceMessagesResponse>>} Typed voice artifacts, jobs, transcript history, and session summaries.
     */
    getVoiceMessages(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/voice/messages${query ? `?${query}` : ""}`, options);
    }
    /**
     * Poll the daemon-confirmed avatar playback identity.
     *
     * @param {ApiRequestOptions} options Cache and fetch policy; polling callers normally force refresh.
     * @returns {Promise<ApiResponse<VoiceStatusResponse>>} Current daemon voice runtime state.
     */
    getVoiceStatus(options = {}) {
        return this.request("/api/voice/status", options);
    }
    /**
     * Replay one retained daemon message without regenerating speech.
     *
     * @param {string} name Server-issued retained audio filename.
     * @returns {Promise<ApiResponse<unknown>>} Operation envelope confirming whether replay was accepted.
     */
    replayVoiceMessage(name) {
        return this.request("/api/voice/replay", {
            method: "POST",
            body: JSON.stringify({ name }),
            forceRefresh: true
        });
    }
    /**
     * Stop active daemon replay without removing retained audio.
     * @returns {Promise<ApiResponse<unknown>>} A promise that resolves to the API response indicating the result of the pause operation.
     */
    pauseVoiceReplay() {
        return this.request("/api/voice/pause", { method: "POST", forceRefresh: true });
    }
    /**
     * Generate and immediately play audio for one persisted message.
     *
     * @param {string} messageId Stable persisted avatar-message identifier.
     * @returns {Promise<ApiResponse<VoiceSynthesisResponse>>} Accepted speech-job identity when synthesis begins.
     */
    synthesizeVoiceMessage(messageId) {
        return this.request("/api/voice/synthesize", {
            method: "POST",
            body: JSON.stringify({ messageId }),
            forceRefresh: true
        });
    }
    /**
     * Build the safe media URL for one stored voice message.
     *
     * @param {string} name Server-issued retained audio filename.
     * @returns {string} Same-origin, percent-encoded media endpoint URL.
     */
    voiceMessageUrl(name) {
        return `/api/voice/messages/${encodeURIComponent(name)}`;
    }
    /**
     * Read live workspace context through get-context.
     *
     * @param {ApiRequestOptions} options Cache and fetch policy applied to context hydration.
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the memory-index request.
     * @returns {Promise<object>} CLI result payload.
     */
    memoryTree(options = {}) {
        return this.request("/api/memory/tree", options);
    }
    /**
     * Read one memory entry.
     *
     * @param {string} path Dot-notated memory path.
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the entry request.
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the status request.
     * @returns {Promise<object>} CLI result payload.
     */
    knowledgeStatus(scope = "all", options = {}) {
        return this.request(`/api/knowledge/status?scope=${encodeURIComponent(scope)}`, options);
    }
    /**
     * Show graph records.
     *
     * @param {object} params Query parameters.
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the graph-listing request.
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the graph-search request.
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the delta request.
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the global query request.
     * @returns {Promise<object>} CLI result payload.
     */
    globalQuery(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/query?${query}`, options);
    }
    /**
     * Read the canonical picture registry.
     *
     * @param {QueryParams} params Optional domain, search, and scan query values.
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the registry request.
     * @returns {Promise<ApiResponse<PicturesPayload>>} Active picture records and registry diagnostics.
     */
    pictures(params = {}, options = {}) {
        const query = toQueryString(params);
        return this.request(`/api/pictures${query ? `?${query}` : ""}`, options);
    }
    /**
     * Persist one manual description or generate it when the text is omitted.
     *
     * @param {string} pictureId Stable registry identifier of the picture being described.
     * @param {string} description Human-authored description, or an empty string to request generation.
     * @returns {Promise<ApiResponse<PictureDescriptionPayload>>} Updated authoritative picture record and vector-index diagnostics.
     */
    describePicture(pictureId, description = "") {
        return this.request("/api/pictures/description", {
            method: "POST",
            body: JSON.stringify({ pictureId, description }),
            forceRefresh: true
        });
    }
    /**
     * Invoke the model-backed describe-picture flow for one registry record.
     *
     * @param {string} pictureId Stable registry identifier of the picture being described.
     * @returns {Promise<ApiResponse<PictureDescriptionPayload>>} Updated authoritative picture record and vector-index diagnostics.
     */
    generatePictureDescription(pictureId) {
        return this.describePicture(pictureId);
    }
    /**
     * Build the opaque registry-backed URL for one picture.
     *
     * @param {string} pictureId Stable registry identifier rather than a filesystem path.
     * @returns {string} Same-origin URL that resolves the active registry record.
     */
    pictureUrl(pictureId) {
        return `/api/pictures/file?id=${encodeURIComponent(pictureId)}`;
    }
    /**
     * Read profile list.
     *
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the profile-list request.
     * @returns {Promise<object>} CLI result payload.
     */
    profiles(options = {}) {
        return this.request("/api/profiles", options);
    }
    /**
     * Read one profile.
     *
     * @param {object} params Query parameters.
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the profile-read request.
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the log query.
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the log-index request.
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the backlog request.
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
/**
 * Narrow an unknown JSON value to a non-null object record.
 *
 * @param {unknown} value Unknown value returned by browser JSON parsing.
 * @returns {boolean} True when string-keyed property inspection is safe.
 */
function isRecord(value) {
    return typeof value === "object" && value !== null;
}
/**
 * Narrow an unknown JSON object to the minimum Explorer response envelope.
 *
 * @param {unknown} value Unknown value returned by browser JSON parsing.
 * @returns {boolean} True when the required boolean `ok` discriminator exists.
 */
function isApiResponse(value) {
    return isRecord(value) && typeof value.ok === "boolean";
}
/**
 * Adapt a successful system route that exposes feature fields at the response
 * root to the canonical client-side `data` envelope.
 *
 * @param {ApiResponse<TData>} response Parsed Explorer response.
 * @param {(value: unknown) => value is TData} isDirectData Runtime guard for the direct response shape.
 * @returns {ApiResponse<TData>} Response with canonical feature data when the server used a direct payload.
 */
function normalizeDirectResponse(response, isDirectData) {
    if (response.data !== undefined || !isDirectData(response)) {
        return response;
    }
    return { ...response, data: response };
}
/**
 * Narrow a direct health response returned by the system route.
 *
 * @param {unknown} value Parsed response candidate.
 * @returns {boolean} True when all health identity fields are present.
 */
function isHealthStatus(value) {
    return isRecord(value)
        && typeof value.ok === "boolean"
        && typeof value.name === "string"
        && typeof value.distDir === "string"
        && typeof value.workspaceRoot === "string"
        && typeof value.agentHome === "string";
}
/**
 * Narrow a direct registered-project response returned by the system route.
 *
 * @param {unknown} value Parsed response candidate.
 * @returns {boolean} True when the response owns a project array.
 */
function isProjectsResponse(value) {
    return isRecord(value) && typeof value.ok === "boolean" && Array.isArray(value.projects);
}
/**
 * Narrow a direct wiki-registry response returned by the system route.
 *
 * @param {unknown} value Parsed response candidate.
 * @returns {boolean} True when the response owns a wiki array.
 */
function isWikisResponse(value) {
    return isRecord(value) && typeof value.ok === "boolean" && Array.isArray(value.wikis);
}
/**
 * Serialize defined primitive query values into a percent-encoded URL query.
 *
 * @param {QueryParams} params Feature-owned query values; undefined entries are omitted.
 * @returns {string} Query string without a leading question mark.
 */
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
/**
 * Narrow an untrusted storage value to a route that may be restored on startup.
 * Transient routes such as query results are intentionally rejected even when
 * they are valid runtime `RouteId` values.
 *
 * @param {string | null} value Raw string obtained from project-scoped local storage.
 * @returns {boolean} True when the value belongs to the durable navigation allowlist.
 */
function isPersistableRoute(value) {
    return value !== null && PERSISTABLE_ROUTES.some(route => route === value);
}
/**
 * Build the isolated local-storage key for one workspace's active view.
 * @param {string} projectPath The raw project path string to be normalized and keyed.
 * @returns {string} A lowercase, trimmed string prefixed with the project route storage constant.
 */
function projectRouteStorageKey(projectPath) {
    return `${PROJECT_ROUTE_STORAGE_PREFIX}${projectPath.trim().toLocaleLowerCase()}`;
}
/**
 * Restore one stable project route while rejecting stale or transient values.
 * @param {string} projectPath The unique path identifier of the project used to derive the storage key.
 * @returns {RouteId} The persisted RouteId if it exists and is valid; otherwise, the 'dashboard' route identifier.
 */
function restoreProjectRoute(projectPath) {
    if (!projectPath.trim())
        return "dashboard";
    const storedRoute = localStorage.getItem(projectRouteStorageKey(projectPath));
    return isPersistableRoute(storedRoute) ? storedRoute : "dashboard";
}
/**
 * AppState coordinates route, theme, and latest CLI result.
 */
class AppState extends EventTarget {
    /**
     * Maintains the current active route identifier within the application state.
     *
     * @type {RouteId}
     */
    #route;
    /**
     * Stores the absolute or relative filesystem path to the currently active project.
     *
     * @type {string}
     */
    #projectPath;
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
    #lastResult = null;
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
    #pendingQueryOptions = {};
    /**
     * Holds the current navigation destination target or null if no routing operation is pending.
     *
     * @type {RouteTarget | null}
     */
    #routeTarget = null;
    /**
     * Maintains a private collection of call log records within the application state.
     *
     * @type {CallLogRecord[]}
     */
    #callLog = [];
    /**
     * Tracks the currently executing or selected command within the application state, or null if no command is active.
     *
     * @type {ActiveCommand | null}
     */
    #activeCommand = null;
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
     *
     * @param {Record<string, string[]>} options A collection of key-value pairs where each value is an array of strings to be cloned into the state.
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
    /**
     * Read and clear search options captured by the persistent shell.
     * @returns {Record<string, string[]>} A record mapping query keys to their associated arrays of option values.
     */
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
    /**
     * Persist only stable navigation views under the active project identity.
     * @param {RouteId} route The route identifier to be stored for the current project.
     */
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
const { codeBlock, escapeHtml } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
const { notificationText } = __brainExplorerModule6();
const { DEFAULT_SHELL_ROUTE, isShellRouteId, SHELL_ROUTES } = __brainExplorerModule7();
const { handleShellSearchShortcut } = __brainExplorerModule51();
const { renderShellNavigation } = __brainExplorerModule52();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */






/**
 * BrainExplorerApp composes the persistent shell around route-level Web Components.
 */
class BrainExplorerApp extends HTMLElement {
    /**
     * Registered Custom Element tag used by the document bootstrap.
     * @returns {string} The string identifier used as the selector for the application shell.
     */
    static get selector() {
        return "brain-explorer-app";
    }
    /**
     * Browser API adapter injected by the application bootstrap.
     * @type {BrainApiClient | null}
     */
    #api = null;
    /**
     * Presentation state store injected alongside the API adapter.
     * @type {AppState | null}
     */
    #state = null;
    /**
     * Route currently mounted in the shell content outlet.
     * @type {RouteId}
     */
    #activeRouteId = "dashboard";
    /**
     * Prevents duplicate subscriptions to `AppState` lifecycle events.
     * @type {boolean}
     */
    #stateListenersBound = false;
    /**
     * Prevents duplicate subscriptions to API request lifecycle events.
     * @type {boolean}
     */
    #apiListenersBound = false;
    /**
     * Number of API requests currently visible to the global progress zone.
     * @type {number}
     */
    #activeRequestCount = 0;
    /**
     * Identifiers of diagnostics call records expanded by the user.
     * @type {Set<string>}
     */
    #openCallIds = new Set();
    /**
     * Most recently created voice playback element, or null when idle.
     * @type {HTMLAudioElement | null}
     */
    #latestVoiceAudio = null;
    /**
     * Dismissal timers indexed by notification identity.
     * @type {Map<string, NotificationTimerViewModel>}
     */
    #notificationTimers = new Map();
    /**
     * Stable listener delegating the global search shortcut to its feature controller.
     * @type {(event: KeyboardEvent) => void}
     */
    #handleGlobalKeyDown = (event) => handleShellSearchShortcut(this, event);
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
                                    Loading...
                                </summary>
                                <div class="action-menu-panel project-selector-panel" data-role="project-selector-options">
                                </div>
                            </details>
                        </span>
                    </div>
                    <div class="global-search-cluster">
                        <div class="global-search">
                            ${icon("search")}
                            <input data-role="global-shell-search" placeholder="Search all knowledge...">
                            <kbd>Ctrl + Alt + S</kbd>
                        </div>
                        <details class="action-menu search-options-menu">
                            <summary title="Search sources and modes" aria-label="Search sources and modes">${icon("sliders")}</summary>
                            <div class="action-menu-panel search-options-panel">
                                <fieldset>
                                    <legend>Sources</legend>
                                    <label><input type="checkbox" name="search-source" value="memory" checked>Memory</label>
                                    <label><input type="checkbox" name="search-source" value="knowledge" checked>Knowledge</label>
                                    <label><input type="checkbox" name="search-source" value="messages" checked>Messages</label>
                                    <label><input type="checkbox" name="search-source" value="pictures" checked>Pictures</label>
                                </fieldset>
                                <fieldset>
                                    <legend>Modes</legend>
                                    <label><input type="checkbox" name="search-mechanism" value="graph" checked>Graph</label>
                                    <label><input type="checkbox" name="search-mechanism" value="vector" checked>Vector</label>
                                    <label><input type="checkbox" name="search-mechanism" value="text" checked>Text</label>
                                </fieldset>
                            </div>
                        </details>
                    </div>
                    <div class="header-actions">
                        <button class="voice-header-toggle" data-action="play-latest-voice" title="Replay latest message" aria-label="Replay latest message">${icon("volume")}</button>
                        <button class="theme-toggle" data-action="toggle-theme" title="Change theme"></button>
                    </div>
                </header>

                <aside class="side-nav">
                    <button class="sidebar-collapse" data-action="toggle-sidebar"></button>
                    <nav data-role="side-nav-list" aria-label="Main navigation">
                        ${renderShellNavigation(this.#state.route)}
                    </nav>
                </aside>

                <main class="route-host" data-route-host></main>

                <footer class="status-footer">
                    <span>(c) 2026 Brain Explorer</span>
                    <span>v1.1.0</span>
                    <span data-role="footer-route"></span>
                    <span data-role="footer-call"></span>
                    <button data-action="toggle-diagnostics" class="footer-link">${icon("terminal")}CLI</button>
                    <span>Local system <i class="live-dot"></i></span>
                </footer>

                <div data-command-overlay-host></div>
                <div data-diagnostics-host></div>
                <section class="notification-stack" data-notification-stack aria-live="polite" aria-label="Notifications"></section>
            </div>
        `;
        this.#bindShellEvents();
        this.#syncTheme();
        this.#syncSidebar();
        this.#mountRoute();
        this.#syncFooter();
        this.#renderDiagnosticsPanel();
        this.#renderActiveCommand();
        const api = this.#api;
        api.health().then(res => {
            const defaultPath = res.data?.workspaceRoot ?? "";
            if (defaultPath) {
                // Fetch and populate registered projects dropdown
                api.getProjects().then((projectsRes) => {
                    const summaryEl = this.querySelector("[data-role='project-selector-summary']");
                    const optionsEl = this.querySelector("[data-role='project-selector-options']");
                    if (summaryEl && optionsEl && projectsRes.data?.projects) {
                        optionsEl.innerHTML = "";
                        let activePath = localStorage.getItem("active_project_path");
                        const allProjects = [...projectsRes.data.projects];
                        if (defaultPath && !allProjects.some(p => p.path === defaultPath)) {
                            allProjects.unshift({
                                name: defaultPath,
                                path: defaultPath
                            });
                        }
                        allProjects.sort((a, b) => a.path.localeCompare(b.path));
                        const activeProjectIsRegistered = allProjects.some(project => project.path === activePath);
                        if (!activeProjectIsRegistered && defaultPath) {
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
        }).catch((err) => console.error("Error fetching health for project indicator:", err));
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
        const api = this.#api;
        const state = this.#state;
        api.addEventListener("request-start", event => {
            if (!(event instanceof CustomEvent))
                return;
            const detail = event.detail;
            this.#activeRequestCount += 1;
            state.setActiveCommand(detail.command || "CLI");
        });
        api.addEventListener("request-end", event => {
            if (!(event instanceof CustomEvent))
                return;
            const detail = event.detail;
            this.#activeRequestCount = Math.max(0, this.#activeRequestCount - 1);
            if (this.#activeRequestCount === 0) {
                state.clearActiveCommand();
            }
            const payload = detail.payload;
            const method = detail.method || "GET";
            const feedback = payload
                ? notificationText(payload, method, detail.command || "")
                : null;
            if (payload && !payload.ok) {
                this.#pushNotification({
                    tone: "error",
                    title: "Could not complete",
                    message: feedback?.message ?? "The request failed."
                });
            }
            else if (payload && method !== "GET") {
                this.#pushNotification({
                    tone: "success",
                    title: feedback?.title ?? "Completed",
                    message: feedback?.message ?? "The mutation completed successfully."
                });
            }
        });
        this.#apiListenersBound = true;
    }
    /**
     * Add one timed, hover-pausable notification pill to the global stack.
     *
     * @param {ShellNotificationInput} input Notification tone, heading, and human-readable body.
     * @returns {void} Nothing; the method mutates only the mounted notification region.
     */
    #pushNotification(input) {
        const { tone = "info", title = "Message", message = "" } = input;
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
            <button class="notification-close" type="button" aria-label="Close notification"><i></i></button>
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
            if (event.currentTarget instanceof Element)
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
        const state = this.#state;
        if (!shell || !state) {
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
            if (event instanceof KeyboardEvent && event.key === "Enter") {
                const value = event.target instanceof HTMLInputElement ? event.target.value.trim() : "";
                if (value) {
                    this.querySelector(".search-options-menu")?.removeAttribute("open");
                    state.setPendingQuery(value, this.#selectedSearchOptions());
                    return;
                }
                state.setRoute("query");
            }
        });
    }
    /**
     * Collect non-exclusive search source and mechanism selections.
     * @returns {Record<string, string[]>} A record mapping 'sources' and 'mechanisms' keys to arrays of their respective selected input values.
     */
    #selectedSearchOptions() {
        const selected = (name) => Array.from(this.querySelectorAll(`input[name='${name}']:checked`))
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
        const state = this.#state;
        if (!state)
            return;
        const target = event.target instanceof Element ? event.target : null;
        this.#handleDropdownMenus(target);
        if (state.sidebarOpen && target && !target.closest(".side-nav")) {
            state.closeSidebar();
        }
        const routeButton = target?.closest("[data-route]");
        if (routeButton) {
            const routeId = routeButton.getAttribute("data-route");
            if (isShellRouteId(routeId))
                state.setRoute(routeId);
            state.closeSidebar();
            return;
        }
        const actionButton = target?.closest("[data-action]");
        const action = actionButton?.getAttribute("data-action") || "";
        if (action === "toggle-theme") {
            state.toggleTheme();
        }
        if (action === "play-latest-voice") {
            this.#playLatestVoice();
        }
        if (action === "toggle-diagnostics") {
            state.toggleDiagnostics();
        }
        if (action === "close-diagnostics") {
            state.closeDiagnostics();
        }
        if (action === "clear-cli-log") {
            this.#openCallIds.clear();
            state.clearCallLog();
        }
        if (action === "delete-cli-call") {
            const callId = actionButton?.getAttribute("data-call-id") || "";
            this.#openCallIds.delete(callId);
            state.removeCallLogItem(callId);
        }
        if (action === "toggle-sidebar") {
            state.toggleSidebar();
        }
        if (action === "run-cli-command") {
            this.#runCliPrompt();
        }
    }
    /**
     * Replay the latest persisted voice without requesting new synthesis.
     */
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
     * Mount the active route component only when the route changes.
     *
     * @returns {void}
     */
    #mountRoute() {
        const state = this.#state;
        const api = this.#api;
        if (!state || !api)
            return;
        const route = SHELL_ROUTES.find(item => item.id === state.route) ?? DEFAULT_SHELL_ROUTE;
        const host = this.querySelector("[data-route-host]");
        const refreshPendingQuery = route.id === "query" && Boolean(state.pendingQuery);
        if (!host) {
            return;
        }
        const activeRouteIsMounted = host.childElementCount > 0 && this.#activeRouteId === route.id;
        if (activeRouteIsMounted && !refreshPendingQuery) {
            this.#syncActiveNav();
            return;
        }
        const element = document.createElement(route.element);
        if ("context" in element)
            element.context = { api, state };
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
        const state = this.#state;
        if (!state)
            return;
        this.querySelectorAll("[data-route]").forEach(button => {
            button.classList.toggle("is-active", button.getAttribute("data-route") === state.route);
        });
    }
    /**
     * Update theme button and document theme.
     *
     * @returns {void}
     */
    #syncTheme() {
        const state = this.#state;
        if (!state)
            return;
        document.documentElement.dataset.theme = state.theme;
        const button = this.querySelector("[data-action='toggle-theme']");
        if (!button) {
            return;
        }
        button.innerHTML = `
            ${icon(state.theme === "dark" ? "sun" : "moon")}
        `;
    }
    /**
     * Update overlay sidebar width, label, and icon without touching routes.
     *
     * @returns {void}
     */
    #syncSidebar() {
        const state = this.#state;
        if (!state)
            return;
        const shell = this.querySelector(".app-shell");
        const button = this.querySelector("[data-action='toggle-sidebar']");
        shell?.classList.toggle("is-sidebar-open", state.sidebarOpen);
        shell?.classList.toggle("is-sidebar-collapsed", !state.sidebarOpen);
        if (!button) {
            return;
        }
        const label = state.sidebarOpen ? "Collapse" : "Expand";
        const iconName = state.sidebarOpen ? "collapseLeft" : "expandRight";
        if (!(button instanceof HTMLElement))
            return;
        button.title = `${label} navigation`;
        button.dataset.tooltip = `${label} navigation`;
        button.setAttribute("aria-label", `${label} navigation`);
        button.innerHTML = `${icon(iconName)}<span class="nav-label">${label}</span>`;
    }
    /**
     * Keep route and CLI technical state in the persistent footer.
     *
     * @returns {void}
     */
    #syncFooter() {
        const stateStore = this.#state;
        if (!stateStore)
            return;
        const route = SHELL_ROUTES.find(item => item.id === stateStore.route) ?? DEFAULT_SHELL_ROUTE;
        const routeLabel = this.querySelector("[data-role='footer-route']");
        const callLabel = this.querySelector("[data-role='footer-call']");
        const lastCall = stateStore.callLog[0];
        if (routeLabel) {
            routeLabel.textContent = route.label;
        }
        if (!callLabel) {
            return;
        }
        if (!lastCall) {
            callLabel.textContent = "No CLI calls";
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
        const state = this.#state;
        const api = this.#api;
        if (!state || !api)
            return;
        const input = this.querySelector("[data-role='cli-prompt']");
        const command = input?.value?.trim() || "";
        if (!command) {
            return;
        }
        state.setActiveCommand(command);
        const result = await api.runCli(command);
        state.setLastResult(result);
    }
    /**
     * Render diagnostics drawer in its isolated overlay host.
     *
     * @returns {void}
     */
    #renderDiagnosticsPanel() {
        const state = this.#state;
        if (!state)
            return;
        const host = this.querySelector("[data-diagnostics-host]");
        if (!host) {
            return;
        }
        host.innerHTML = state.diagnosticsOpen ? this.#renderDiagnosticsDrawer() : "";
        this.#bindCallLogItems();
    }
    /**
     * Render diagnostics drawer.
     *
     * @returns {string} HTML.
     */
    #renderDiagnosticsDrawer() {
        return `
            <aside class="diagnostics-drawer" aria-label="CLI console">
                <div class="diagnostics-head">
                    <div>
                        <strong>CLI calls</strong>
                        <span>History, active command, and allowlisted prompt</span>
                    </div>
                    <div class="diagnostics-actions">
                        <button data-action="clear-cli-log" class="ghost-action">${icon("trash")}Clear</button>
                        <button data-action="close-diagnostics" class="icon-action cli-close-action" title="Close console" aria-label="Close console">${icon("close")}</button>
                    </div>
                </div>
                ${this.#renderDiagnosticsActiveCommand()}
                <div data-role="diagnostics-log" class="diagnostics-log">
                    ${this.#renderCallLog()}
                </div>
                <form class="cli-prompter" data-role="cli-prompter">
                    <label>
                        <span>Command</span>
                        <input data-role="cli-prompt" list="cli-command-suggestions" placeholder="get-context">
                    </label>
                    <datalist id="cli-command-suggestions">
                        ${this.#renderPromptSuggestions()}
                    </datalist>
                    <button type="button" data-action="run-cli-command" class="primary-action">${icon("terminal")}Run</button>
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
        const activeCommand = this.#state?.activeCommand;
        host.innerHTML = activeCommand ? `
            <div class="command-blocking-overlay" role="status" aria-live="polite">
                <span class="loading-spinner"></span>
                <strong>Running command</strong>
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
        const activeCommand = this.#state?.activeCommand;
        if (!activeCommand) {
            return `<div data-role="diagnostics-active-command" class="diagnostics-active-strip is-empty">No command is running.</div>`;
        }
        return `
            <div data-role="diagnostics-active-command" class="diagnostics-active-strip">
                <span class="loading-spinner small-spinner"></span>
                <strong>Running</strong>
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
        const calls = this.#state?.callLog ?? [];
        if (!calls.length) {
            return `<p class="empty-state">No calls recorded yet.</p>`;
        }
        return calls.map(call => `
            <details class="call-log-item" data-call-id="${escapeHtml(call.id)}" ${this.#openCallIds.has(call.id) ? "open" : ""}>
                <summary>
                    <span class="${call.ok ? "status-dot ok" : "status-dot error"}"></span>
                    <strong>${escapeHtml(call.command.split(" ").slice(-3).join(" ") || "API call")}</strong>
                    <time>${escapeHtml(call.time)} - ${escapeHtml(String(call.durationMs))} ms</time>
                    <button type="button" data-action="delete-cli-call" data-call-id="${escapeHtml(call.id)}" class="icon-action call-delete" title="Delete call">${icon("trash")}</button>
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
     * @param {HTMLDetailsElement} details Native details element whose expanded
     * state must be mirrored in the shell's persistent expansion registry.
     * @returns {void}
     */
    #syncCallLogItem(details) {
        const id = details.getAttribute("data-call-id") || "";
        if (!id) {
            return;
        }
        if (details.open) {
            this.#openCallIds.add(id);
            return;
        }
        this.#openCallIds.delete(id);
    }
}
customElements.define(BrainExplorerApp.selector, BrainExplorerApp);

cache=(()=>{return { BrainExplorerApp: BrainExplorerApp };})();return cache;};})();
const __brainExplorerModule4=(()=>{let cache;return()=>{if(cache)return cache;

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
                codeLanguage = fence[1] ?? "markdown";
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
            html.push(`<h${heading[1]?.length ?? 1}>${inlineMarkdown(heading[2] ?? "")}</h${heading[1]?.length ?? 1}>`);
            continue;
        }
        const bullet = line.match(/^\s*[-*]\s+(.+)$/);
        if (bullet) {
            flushParagraph();
            list.push(bullet[1] ?? "");
            continue;
        }
        const quote = line.match(/^>\s+(.+)$/);
        if (quote) {
            flushParagraph();
            flushList();
            html.push(`<blockquote>${inlineMarkdown(quote[1] ?? "")}</blockquote>`);
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
/**
 * Apply deterministic token spans to an already identified fenced-code language.
 *
 * @param {unknown} value Unknown code body normalized and escaped before highlighting.
 * @param {string} language Fence language identifier selecting the safe token rules.
 * @returns {string} Escaped HTML containing presentation-only token spans.
 */
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
/**
 * Render the supported inline Markdown subset without permitting raw HTML.
 *
 * @param {string} value Plain source text from a paragraph, list item, or heading.
 * @returns {string} Escaped HTML with code, strong, and emphasis spans.
 */
function inlineMarkdown(value) {
    return escapeHtml(value)
        .replace(/`([^`]+)`/g, `<code>$1</code>`)
        .replace(/\*\*([^*]+)\*\*/g, `<strong>$1</strong>`)
        .replace(/\*([^*]+)\*/g, `<em>$1</em>`);
}

cache=(()=>{return { escapeHtml: escapeHtml, prettyJson: prettyJson, codeBlock: codeBlock, renderMarkdown: renderMarkdown, compactLabel: compactLabel, optionTags: optionTags };})();return cache;};})();
const __brainExplorerModule5=(()=>{let cache;return()=>{if(cache)return cache;

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
    chevronLeft: `<path d="m15 18-6-6 6-6"/>`,
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
const __brainExplorerModule6=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */
/**
 * Build concise human feedback from one structured API response.
 *
 * @param {ApiResponse<unknown>} payload Authoritative typed API envelope returned by the completed request.
 * @param {string} method Uppercase HTTP method used to classify destructive operations.
 * @param {string} requestLabel Human-readable request label used when response data has no message.
 * @returns {NotificationText} Notification title and body containing no serialized JSON payloads.
 */
function notificationText(payload, method, requestLabel = "") {
    const data = asRecord(payload.data);
    if (!payload.ok) {
        return { title: "Could not complete", message: readableError(payload, data) };
    }
    return { title: successTitle(data, method), message: successMessage(data, requestLabel) };
}
/**
 * Classify a successful operation into a compact notification title.
 *
 * @param {Record<string, unknown>} data Unknown response data normalized to an indexable record.
 * @param {string} method HTTP method used as a deletion fallback.
 * @returns {string} Stable human-readable success heading.
 */
function successTitle(data, method) {
    const command = String(data.command || "");
    if (command.includes("delete") || method === "DELETE")
        return "Item deleted";
    if (command.includes("add") || command.includes("create"))
        return "Item created";
    if (typeof data.domain === "string" && typeof data.key === "string")
        return "Changes saved";
    if (command.includes("set") || command.includes("edit") || command.includes("save"))
        return "Changes saved";
    return "Operation completed";
}
/**
 * Resolve the most specific successful-operation explanation available.
 *
 * @param {Record<string, unknown>} data Unknown response data normalized to an indexable record.
 * @param {string} requestLabel Request label used when the payload exposes no recognizable entity.
 * @returns {string} Human-readable success description with entity context when available.
 */
function successMessage(data, requestLabel) {
    const command = String(data.command || "");
    const task = asRecord(data.task);
    if (Object.keys(task).length) {
        const title = quoted(task.title || task.id || "task");
        const status = String(task.status || "");
        if (command === "add-task")
            return `Task ${title} was created.`;
        if (command === "edit-task")
            return `Task ${title} was updated.`;
        if (status === "DONE")
            return `Task ${title} was completed.`;
        if (status === "WORKING")
            return `Task ${title} is in progress.`;
        if (status === "TODO")
            return `Task ${title} returned to pending.`;
    }
    if (command === "delete-task" || data.deleted === true) {
        return `Task ${quoted(data.taskId || "selected")} was deleted.`;
    }
    if (typeof data.domain === "string" && typeof data.key === "string") {
        const entry = quoted(`${data.domain}.${data.key}`);
        return command.includes("delete") ? `Memory ${entry} was deleted.` : `Memory ${entry} was saved.`;
    }
    if (typeof data.domain === "string") {
        if (command.includes("delete"))
            return `Domain ${quoted(data.domain)} was deleted.`;
        if (command.includes("add"))
            return `Domain ${quoted(data.domain)} was created.`;
    }
    if (command === "clone-snippet")
        return `Snippet ${quoted(data.snippet || "selected")} was cloned.`;
    if (command === "register-project") {
        const project = asRecord(data.project);
        return `Project ${quoted(project.name || project.path || "selected")} was registered.`;
    }
    if (command === "speak" || requestLabel.includes("voice"))
        return "The voice request was processed successfully.";
    return humanString(data.message) || requestFallback(requestLabel);
}
/**
 * Select the first safe human-readable error from a failed response.
 *
 * @param {ApiResponse<unknown>} payload Failed API envelope containing transport-level fallbacks.
 * @param {Record<string, unknown>} data Unknown response data normalized to an indexable record.
 * @returns {string} Plain error text or a stable actionable fallback.
 */
function readableError(payload, data) {
    for (const candidate of [data.error, data.message, payload.error, payload.stderr]) {
        const message = humanString(candidate);
        if (message)
            return message;
    }
    return "The operation could not be completed. Review the data and try again.";
}
/**
 * Translate a known request label into a neutral success fallback.
 *
 * @param {string} requestLabel Human-readable or path-like label attached to the request.
 * @returns {string} Feature-specific confirmation when recognized, otherwise a generic confirmation.
 */
function requestFallback(requestLabel) {
    const label = requestLabel.toLowerCase();
    if (label.includes("memory/entry"))
        return "The memory entry was updated.";
    if (label.includes("memory/domain"))
        return "The memory domain was updated.";
    if (label.includes("backlog/task"))
        return "The task was updated.";
    if (label.includes("voice/replay"))
        return "Voice playback started.";
    if (label.includes("voice/pause"))
        return "Voice playback paused.";
    return "The changes were applied successfully.";
}
/**
 * Accept only plain human strings, never serialized JSON documents.
 *
 * @param {unknown} value Unknown candidate extracted from an API payload.
 * @returns {string} Trimmed human text, or an empty string for non-text and serialized structures.
 */
function humanString(value) {
    if (typeof value !== "string")
        return "";
    const text = value.trim().replace(/^Error:\s*/i, "");
    if (!text || text.startsWith("{") || text.startsWith("["))
        return "";
    return text;
}
/**
 * Normalize an unknown plain object into an assertion-free shallow record.
 *
 * @param {unknown} value Unknown response member crossing the transport boundary.
 * @returns {Record<string, unknown>} Indexable shallow copy, or an empty record for arrays, null, and primitives.
 */
function asRecord(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value)
        ? Object.fromEntries(Object.entries(value))
        : {};
}
/**
 * Wrap an unknown entity label in typographic quotation marks.
 *
 * @param {unknown} value Unknown label value supplied by response data.
 * @returns {string} Trimmed, quoted human-readable label.
 */
function quoted(value) {
    return `“${String(value || "").trim()}”`;
}

cache=(()=>{return { notificationText: notificationText };})();return cache;};})();
const __brainExplorerModule7=(()=>{let cache;return()=>{if(cache)return cache;
const { BacklogView } = __brainExplorerModule8();
const { DashboardView } = __brainExplorerModule19();
const { KnowledgeView } = __brainExplorerModule21();
const { LogsView } = __brainExplorerModule34();
const { MemoryView } = __brainExplorerModule40();
const { MessagesView } = __brainExplorerModule44();
const { PicturesView } = __brainExplorerModule45();
const { ProfilesView } = __brainExplorerModule47();
const { QueryView } = __brainExplorerModule48();
const { SettingsView } = __brainExplorerModule49();
const { WikisView } = __brainExplorerModule50();
/**
 * Defines the immutable navigation registry used by the Brain Explorer shell.
 *
 * Keeping route composition outside the Web Component prevents the shell layout
 * from owning application configuration and gives routing consumers one typed,
 * independently testable source of truth.
 *
 * @module presentation/shell/config/shell-routes
 */











/**
 * Route displayed when persisted navigation state is absent or invalid.
 *
 * The value satisfies the route contract without widening its literal route id,
 * which lets callers use it as both a fallback and the first registry entry.
 */
const DEFAULT_SHELL_ROUTE = {
    id: "dashboard",
    label: "Project",
    icon: "home",
    element: DashboardView.selector
};
/**
 * Ordered route registry rendered by the persistent application shell.
 *
 * Entries with `nav: false` remain routable but are intentionally omitted from
 * primary navigation because another interaction, such as search, opens them.
 */
const SHELL_ROUTES = [
    DEFAULT_SHELL_ROUTE,
    { id: "messages", label: "Messages", icon: "messageCircle", element: MessagesView.selector },
    { id: "memory", label: "Memory", icon: "database", element: MemoryView.selector },
    { id: "knowledge", label: "Knowledge", icon: "graph", element: KnowledgeView.selector },
    { id: "pictures", label: "Pictures", icon: "camera", element: PicturesView.selector },
    { id: "query", label: "Results", icon: "search", element: QueryView.selector, nav: false },
    { id: "profiles", label: "Profiles", icon: "users", element: ProfilesView.selector },
    { id: "logs", label: "Logs", icon: "document", element: LogsView.selector },
    { id: "backlog", label: "Backlog", icon: "checkSquare", element: BacklogView.selector },
    { id: "wikis", label: "Wikis", icon: "book", element: WikisView.selector },
    { id: "settings", label: "Settings", icon: "settings", element: SettingsView.selector }
];
/**
 * Narrow a raw DOM attribute to an application route registered by the shell.
 *
 * @param {string | null} value Untrusted route value read from an element attribute.
 * @returns {boolean} True only when `value` is a non-null member of the immutable registry.
 */
function isShellRouteId(value) {
    return value !== null && SHELL_ROUTES.some(route => route.id === value);
}

cache=(()=>{return { isShellRouteId: isShellRouteId, DEFAULT_SHELL_ROUTE: DEFAULT_SHELL_ROUTE, SHELL_ROUTES: SHELL_ROUTES };})();return cache;};})();
const __brainExplorerModule8=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
const { StructureTree } = __brainExplorerModule9();
const { BacklogPipController } = __brainExplorerModule10();
const { BacklogVisualReferenceController } = __brainExplorerModule14();
const { BACKLOG_PRIORITY_FILTER_OPTIONS, BACKLOG_STATUS_FILTER_OPTIONS } = __brainExplorerModule16();
const { BacklogTaskProjector } = __brainExplorerModule17();
const { renderBacklogDialogs, renderBacklogTaskList } = __brainExplorerModule18();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */








void StructureTree;
/**
 * BacklogView renders workspace tasks as a domain tree and focused task board.
 */
class BacklogView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the BacklogView component in the DOM.
     * @returns {string} The string identifier 'brain-backlog-view'.
     */
    static get selector() {
        return "brain-backlog-view";
    }
    /**
     * Holds a reference to the component's API context for accessing shared services or state, defaulting to null.
     *
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/infrastructure/shared/http/clients/brain-api-client").BrainApiClient | null}
     */
    #api = null;
    /**
     * Holds the internal state of the backlog view component, initialized as null until the component context is established.
     *
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/presentation/shell/state/app-state").AppState | null}
     */
    #state = null;
    /**
     * Stores a string representation of the backlog's unique signature for identification or state tracking.
     *
     * @type {string}
     */
    #backlogSignature = "";
    /**
     * Maintains a private collection of task view models representing the items displayed within the backlog view.
     *
     * @type {BacklogPipTaskViewModel[]}
     */
    #tasks = [];
    /**
     * Maintains the identifier of the currently selected domain within the backlog view.
     *
     * @type {string}
     */
    #selectedDomain = "";
    /**
     * Maintains the current text-based filter criteria used to narrow down the displayed backlog items.
     *
     * @type {string}
     */
    #filter = "";
    /**
     * Maintains a unique collection of selected task status values used to filter the backlog view.
     *
     * @type {Set<"TODO" | "WORKING" | "DONE">}
     */
    #statusFilter = new Set();
    /**
     * Maintains a unique collection of selected priority levels used to filter the displayed backlog tasks.
     *
     * @type {Set<"HIGH" | "MEDIUM" | "LOW">}
     */
    #priorityFilter = new Set();
    /**
     * Tracks the visibility state of the backlog filter panel.
     *
     * @type {boolean}
     */
    #filtersOpen = false;
    /**
     * Maintains a set of unique identifiers representing the currently expanded nodes within the backlog view hierarchy.
     *
     * @type {Set<string>}
     */
    #expandedNodes = new Set();
    /**
     * Initializes a private instance of BacklogPipController to manage the pipeline logic within the backlog view.
     *
     * @type {BacklogPipController}
     */
    #pipController = new BacklogPipController();
    /**
     * Initializes a private controller instance to manage visual references within the backlog view.
     *
     * @type {BacklogVisualReferenceController}
     */
    #visualReferenceController = new BacklogVisualReferenceController(this);
    /**
     * Maintains a private collection of identifiers or paths for tasks that contain associated images.
     *
     * @type {string[]}
     */
    #tasksWithImages = [];
    /**
     * Stores the numeric identifier of the active timer used to trigger periodic backlog data refreshes.
     *
     * @type {number | null}
     */
    #refreshTimer = null;
    /**
     * Tracks whether a backlog data refresh operation is currently in progress to prevent concurrent requests.
     *
     * @type {boolean}
     */
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
        this.#pipController.close();
    }
    /**
     * Start the view-owned silent refresh cycle.
     */
    #startSilentRefresh() {
        if (this.#refreshTimer) {
            return;
        }
        this.#scheduleSilentRefresh();
    }
    /**
     * Stop the silent refresh cycle when this route is unmounted.
     */
    #stopSilentRefresh() {
        if (this.#refreshTimer !== null)
            window.clearTimeout(this.#refreshTimer);
        this.#refreshTimer = null;
    }
    /**
     * Schedule the next cycle five seconds after the previous one completed.
     */
    #scheduleSilentRefresh() {
        if (!this.isConnected) {
            return;
        }
        this.#refreshTimer = window.setTimeout(() => {
            this.#refreshTimer = null;
            this.#refreshSilently();
        }, 60000);
    }
    /**
     * Refresh changed tasks without overlapping requests or repainting unchanged UI.
     */
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
            this.#pipController.syncTasks(this.#tasks);
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
        this.#pipController.syncTasks(this.#tasks);
        this.#selectedDomain = this.#selectedDomain || "";
        if (this.#selectedDomain) {
            this.#taskProjector().ancestorPaths(this.#selectedDomain).forEach(path => this.#expandedNodes.add(path));
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
        if (!this.#api)
            return;
        const action = status === "DONE" ? "done" : status === "WORKING" ? "working" : "todo";
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
        if (!this.#api)
            return;
        const force = status !== "DONE";
        if (force && !window.confirm("This task is still in progress. Delete it anyway?")) {
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
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        const projector = this.#taskProjector();
        const domainTasks = projector.domainTasks();
        const visibleTasks = projector.visibleTasks();
        const pipSupported = this.#pipController.supported();
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
                                <span class="backlog-task-count" style="font-size: 13px; font-weight: normal; color: var(--text-muted);">(${visibleTasks.length} tasks)</span>
                            </strong>
                            <div class="backlog-header-actions" style="display: flex; gap: 8px; align-items: center;">
                                <details class="action-menu filter-menu backlog-filter-menu" ${this.#filtersOpen ? "open" : ""}>
                                    <summary class="icon-action" title="Filter tasks" aria-label="Filter tasks">
                                        ${icon("filter")}
                                        <span class="backlog-filter-count" ${projector.activeFilterCount() ? "" : "hidden"}>${projector.activeFilterCount()}</span>
                                    </summary>
                                    <div class="action-menu-panel filter-menu-panel">
                                        <fieldset class="checkbox-filter-group"><legend>Status</legend>
                                            ${BACKLOG_STATUS_FILTER_OPTIONS.map(([value, label]) => `<label><input type="checkbox" data-filter-kind="status" value="${value}" ${this.#statusFilter.has(value) ? "checked" : ""}><span>${label}</span></label>`).join("")}
                                        </fieldset>
                                        <fieldset class="checkbox-filter-group"><legend>Priority</legend>
                                            ${BACKLOG_PRIORITY_FILTER_OPTIONS.map(([value, label]) => `<label><input type="checkbox" data-filter-kind="priority" value="${value}" ${this.#priorityFilter.has(value) ? "checked" : ""}><span>${label}</span></label>`).join("")}
                                        </fieldset>
                                        <button data-action="clear-backlog-filters" class="ghost-action">${icon("close")}Clear filters</button>
                                    </div>
                                </details>
                                <button data-action="open-create-modal" class="ghost-action compact-action" style="font-size: 13px; height: 32px; display: inline-flex; align-items: center; gap: 6px;">${icon("plus")} Create task</button>
                                <button data-action="toggle-pip" class="ghost-action compact-action" style="font-size: 13px; height: 32px; display: inline-flex; align-items: center; gap: 6px;" ${pipSupported ? "" : "disabled"} title="${pipSupported ? "Open Picture-in-Picture window" : "Document Picture-in-Picture is unavailable in this browser"}">${icon("eye")} PIP view</button>
                            </div>
                        </div>
                        <div class="backlog-workspace scroll-area" style="padding: 14px;">
                            <div class="task-list">
                                ${renderBacklogTaskList(domainTasks, this.#selectedDomain, this.#tasksWithImages)}
                                <p class="empty-state backlog-filter-empty" hidden>No tasks match these filters.</p>
                            </div>
                        </div>
                    </main>
                </div>
            </section>
            ${renderBacklogDialogs()}
        `;
        this.#bindEvents();
        this.#configureTree();
        this.#applyTaskFiltersToDom();
    }
    /**
     * Open or focus the native Backlog PiP surface through its lifecycle controller.
     * @returns {Promise<void>} A promise that resolves once the Picture-in-Picture window has been initiated.
     */
    async #openPipWindow() {
        await this.#pipController.open({
            tasks: this.#tasks,
            onAddTask: task => this.#addTaskFromPip(task)
        });
    }
    /**
     * Persist one task draft submitted by the native PiP component.
     *
     * @param {BacklogPipCreateTaskInput} taskData Validated task fields and optional marked reference image.
     * @returns {Promise<{ ok: boolean; message: string; tasks?: never; } | { ok: boolean; tasks: BacklogPipTaskViewModel[]; message?: never; }>} PiP-local mutation result containing refreshed tasks on success.
     */
    async #addTaskFromPip(taskData) {
        const domain = this.#selectedDomain || "Backlog";
        this.#state?.setActiveCommand(`add-task ${domain} "${taskData.title}"`);
        try {
            if (!this.#api)
                return { ok: false, message: "Backlog API is unavailable." };
            const result = await this.#api.updateBacklog({
                action: "add",
                domain,
                title: taskData.title,
                description: taskData.description,
                priority: taskData.priority,
                image: taskData.image
            });
            this.#state?.setLastResult(result);
            if (!result.ok)
                return { ok: false, message: result.error || result.stderr || "Could not create the task." };
            this.#selectedDomain = domain;
            await this.#loadBacklog(true);
            return { ok: true, tasks: this.#tasks };
        }
        catch (error) {
            console.error("Unable to add a task from Document PiP.", error);
            return { ok: false, message: "Could not create the task. Try again." };
        }
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
     * Configure the shared Backlog domain tree.
     *
     * @returns {void}
     */
    #configureTree() {
        const treeElement = this.querySelector("[data-role='backlog-tree']");
        if (!(treeElement instanceof StructureTree)) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
            toggleOnBranchSelect: true,
            title: "Backlog",
            toolbarActions: [
                { id: "new-domain", label: "New domain", icon: "plus" },
                { id: "refresh", label: "Refresh backlog", icon: "refresh" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "checkSquare",
            searchQuery: this.#filter,
            emptyText: "No backlog domains. Refresh to load tasks."
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onTreeAction(event));
        treeElement.addEventListener("brain-tree-search", event => {
            if (!(event instanceof CustomEvent) || typeof event.detail?.query !== "string")
                return;
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
        const projector = this.#taskProjector();
        const toNode = (node) => {
            const children = Array.from(node.children.values())
                .filter(child => projector.matchesNode(child))
                .sort((left, right) => left.label.localeCompare(right.label))
                .map(toNode);
            const count = this.#tasks.filter(task => (task.domain === node.path || task.domain.startsWith(`${node.path}.`))
                && projector.matchesActiveFilters(task)).length;
            return {
                id: node.path,
                path: node.path,
                label: node.label,
                count,
                children,
                actions: []
            };
        };
        return Array.from(projector.buildTree().children.values())
            .filter(node => projector.matchesNode(node))
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
        if (!(event instanceof CustomEvent))
            return;
        if (event.detail.branch && event.detail.clickedCaret) {
            return;
        }
        this.#selectedDomain = event.detail.path;
        this.#taskProjector().ancestorPaths(event.detail.path).forEach(path => this.#expandedNodes.add(path));
        this.#render();
    }
    /**
     * Handle global Backlog tree actions.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeToolbarAction(event) {
        if (!(event instanceof CustomEvent))
            return;
        if (event.detail.action === "new-domain") {
            const newDomain = prompt("Enter the new domain name (for example, my.new.domain):");
            if (newDomain && newDomain.trim()) {
                const requestedDomain = newDomain.trim();
                const targetDomain = this.#selectedDomain && !requestedDomain.includes(".")
                    ? `${this.#selectedDomain}.${requestedDomain}`
                    : requestedDomain;
                const dialog = this.querySelector("#backlog-modal");
                if (dialog) {
                    const taskIdInput = this.querySelector("[data-role='modal-task-id']");
                    const domInput = this.querySelector("[data-role='modal-domain']");
                    const titleInput = this.querySelector("[data-role='modal-title-input']");
                    const descriptionInput = this.querySelector("[data-role='modal-description']");
                    const priorityInput = this.querySelector("[data-role='modal-priority']");
                    if (!taskIdInput || !domInput || !titleInput || !descriptionInput || !priorityInput)
                        return;
                    taskIdInput.value = "";
                    domInput.value = targetDomain;
                    domInput.removeAttribute("disabled");
                    titleInput.value = "";
                    descriptionInput.value = "";
                    priorityInput.value = "HIGH";
                    const imgInput = this.querySelector("[data-role='modal-image-file']");
                    if (imgInput)
                        imgInput.value = "";
                    this.#visualReferenceController.reset();
                    const modalTitle = this.querySelector("[data-role='modal-title']");
                    const submitButton = this.querySelector("[data-role='modal-submit-btn']");
                    if (modalTitle)
                        modalTitle.textContent = `Create task in ${newDomain.trim()}`;
                    if (submitButton)
                        submitButton.textContent = "Create";
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
        if (!(event instanceof CustomEvent))
            return;
        const node = event.detail.node;
        if (!node?.path) {
            return;
        }
        this.#selectedDomain = node.path;
        this.#taskProjector().ancestorPaths(node.path).forEach(path => this.#expandedNodes.add(path));
        this.#render();
    }
    /**
     * Create the pure task projector for the component's current selection and filters.
     *
     * @returns {BacklogTaskProjector} Stateless projection object scoped to the calling render or interaction.
     */
    #taskProjector() {
        return new BacklogTaskProjector({
            tasks: this.#tasks,
            selectedDomain: this.#selectedDomain,
            filter: this.#filter,
            statusFilter: this.#statusFilter,
            priorityFilter: this.#priorityFilter
        });
    }
    /**
     * Refresh the task panel after a local filter change without rebuilding
     * the structural tree or issuing a CLI request.
     *
     * @returns {void}
     */
    #refreshTaskContent() {
        const projector = this.#taskProjector();
        const visibleTasks = projector.visibleTasks();
        this.#applyTaskFiltersToDom();
        const countSpan = this.querySelector(".backlog-task-count");
        if (countSpan) {
            countSpan.textContent = `(${visibleTasks.length} tasks)`;
        }
        const filterCount = this.querySelector(".backlog-filter-count");
        if (filterCount) {
            const activeCount = projector.activeFilterCount();
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
        const projector = this.#taskProjector();
        const domainTasks = projector.domainTasks();
        const visibleIds = new Set(projector.visibleTasks().map(task => task.id));
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
     * Bind DOM events.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelector("[data-action='refresh-backlog']")?.addEventListener("click", () => this.#loadBacklog(true));
        this.querySelector(".backlog-filter-menu")?.addEventListener("toggle", event => {
            if (event.currentTarget instanceof HTMLDetailsElement)
                this.#filtersOpen = event.currentTarget.open;
        });
        this.querySelectorAll("[data-filter-kind]").forEach(input => input.addEventListener("change", event => {
            if (!(event.currentTarget instanceof HTMLInputElement))
                return;
            const target = event.currentTarget;
            if (target.dataset.filterKind === "status" && (target.value === "TODO" || target.value === "WORKING" || target.value === "DONE")) {
                if (target.checked)
                    this.#statusFilter.add(target.value);
                else
                    this.#statusFilter.delete(target.value);
            }
            else if (target.dataset.filterKind === "priority" && (target.value === "HIGH" || target.value === "MEDIUM" || target.value === "LOW")) {
                if (target.checked)
                    this.#priorityFilter.add(target.value);
                else
                    this.#priorityFilter.delete(target.value);
            }
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
            this.#taskProjector().ancestorPaths(path).forEach(ancestor => this.#expandedNodes.add(ancestor));
            if (isBranch && this.#expandedNodes.has(path)) {
                this.#expandedNodes.delete(path);
            }
            else {
                this.#expandedNodes.add(path);
            }
            this.#render();
        }));
        this.querySelectorAll("[data-action='set-task-status']").forEach(button => {
            button.addEventListener("click", () => {
                const status = button.dataset.taskStatus;
                if (status === "TODO" || status === "WORKING" || status === "DONE")
                    this.#setTaskStatus(button.dataset.taskId ?? "", status);
            });
        });
        this.querySelectorAll("[data-action='delete-task']").forEach(button => {
            button.addEventListener("click", () => {
                const status = button.dataset.taskStatus;
                if (status === "TODO" || status === "WORKING" || status === "DONE")
                    this.#deleteTask(button.dataset.taskId ?? "", status);
            });
        });
        // Open Create Modal
        this.querySelector("[data-action='open-create-modal']")?.addEventListener("click", () => {
            const dialog = this.querySelector("#backlog-modal");
            const taskIdInput = this.querySelector("[data-role='modal-task-id']");
            const domInput = this.querySelector("[data-role='modal-domain']");
            const titleInput = this.querySelector("[data-role='modal-title-input']");
            const descriptionInput = this.querySelector("[data-role='modal-description']");
            const priorityInput = this.querySelector("[data-role='modal-priority']");
            if (!dialog || !taskIdInput || !domInput || !titleInput || !descriptionInput || !priorityInput)
                return;
            taskIdInput.value = "";
            domInput.value = this.#selectedDomain;
            domInput.removeAttribute("disabled");
            titleInput.value = "";
            descriptionInput.value = "";
            priorityInput.value = "HIGH";
            const imgInput = this.querySelector("[data-role='modal-image-file']");
            if (imgInput)
                imgInput.value = "";
            this.#visualReferenceController.reset();
            const imgUploadZone = this.querySelector("[data-role='image-upload-zone']");
            if (imgUploadZone) {
                imgUploadZone.style.removeProperty("display");
            }
            const modalTitle = this.querySelector("[data-role='modal-title']");
            const submitButton = this.querySelector("[data-role='modal-submit-btn']");
            if (modalTitle)
                modalTitle.textContent = "Create task";
            if (submitButton)
                submitButton.textContent = "Create";
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
                const taskIdInput = this.querySelector("[data-role='modal-task-id']");
                const domInput = this.querySelector("[data-role='modal-domain']");
                const titleInput = this.querySelector("[data-role='modal-title-input']");
                const descriptionInput = this.querySelector("[data-role='modal-description']");
                const priorityInput = this.querySelector("[data-role='modal-priority']");
                if (!dialog || !taskIdInput || !domInput || !titleInput || !descriptionInput || !priorityInput)
                    return;
                taskIdInput.value = task.id;
                domInput.value = task.domain;
                domInput.setAttribute("disabled", "true");
                titleInput.value = task.title;
                descriptionInput.value = task.description;
                priorityInput.value = task.priority;
                const imgUploadZone = this.querySelector("[data-role='image-upload-zone']");
                if (imgUploadZone) {
                    imgUploadZone.style.removeProperty("display");
                }
                const imgInput = this.querySelector("[data-role='modal-image-file']");
                if (imgInput)
                    imgInput.value = "";
                this.#visualReferenceController.reset();
                const imageTaskId = task.id.replace(/^#/, "");
                if (this.#tasksWithImages.includes(imageTaskId)) {
                    this.#visualReferenceController.displayImage(`/api/backlog/image?taskId=${encodeURIComponent(imageTaskId)}`);
                }
                const modalTitle = this.querySelector("[data-role='modal-title']");
                const submitButton = this.querySelector("[data-role='modal-submit-btn']");
                if (modalTitle)
                    modalTitle.textContent = `Edit task #${task.id}`;
                if (submitButton)
                    submitButton.textContent = "Save";
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
        descInput?.addEventListener("paste", (event) => {
            const items = event.clipboardData?.items;
            if (!items)
                return;
            for (let index = 0; index < items.length; index += 1) {
                const item = items[index];
                if (!item)
                    continue;
                if (item.type.startsWith("image/")) {
                    event.preventDefault();
                    const file = item.getAsFile();
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = () => {
                            const visualReferenceDialog = this.querySelector("#visual-reference-modal");
                            if (visualReferenceDialog instanceof HTMLDialogElement && !visualReferenceDialog.open) {
                                visualReferenceDialog.showModal();
                            }
                            const result = reader.result;
                            if (typeof result !== "string")
                                return;
                            this.#visualReferenceController.displayImage(result);
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
            const taskIdInput = this.querySelector("[data-role='modal-task-id']");
            const domainInput = this.querySelector("[data-role='modal-domain']");
            const titleInput = this.querySelector("[data-role='modal-title-input']");
            const descriptionInput = this.querySelector("[data-role='modal-description']");
            const priorityInput = this.querySelector("[data-role='modal-priority']");
            const api = this.#api;
            if (!dialog || !taskIdInput || !domainInput || !titleInput || !descriptionInput || !priorityInput || !api)
                return;
            const taskId = taskIdInput.value;
            const domain = domainInput.value.trim() || this.#selectedDomain || "Backlog";
            const title = titleInput.value.trim();
            const description = descriptionInput.value.trim();
            const priority = priorityInput.value === "MEDIUM" || priorityInput.value === "LOW" ? priorityInput.value : "HIGH";
            dialog.close();
            if (taskId) {
                this.#state?.setActiveCommand(`edit-task ${taskId}`);
                let base64Image = null;
                try {
                    base64Image = await this.#visualReferenceController.exportPng();
                }
                catch (e) {
                    console.error("Error baking marked image:", e);
                }
                const result = await api.updateBacklog({
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
                    base64Image = await this.#visualReferenceController.exportPng();
                }
                catch (e) {
                    console.error("Error baking marked image:", e);
                }
                const result = await api.updateBacklog({
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
            if (!(event.target instanceof Element))
                return;
            if (!event.target.closest(".upload-placeholder") && event.target !== previewArea)
                return;
            fileInput?.click();
        });
        fileInput?.addEventListener("change", e => {
            const file = e.currentTarget instanceof HTMLInputElement ? e.currentTarget.files?.[0] : undefined;
            if (file) {
                const reader = new FileReader();
                reader.onload = () => {
                    const result = reader.result;
                    if (typeof result === "string")
                        this.#visualReferenceController.displayImage(result);
                };
                reader.readAsDataURL(file);
            }
        });
        // Real Document PiP
        this.querySelector("[data-action='toggle-pip']")?.addEventListener("click", () => {
            this.#openPipWindow();
        });
        this.querySelector("[data-action='capture-screen']")?.addEventListener("click", () => {
            this.#visualReferenceController.captureScreen();
        });
    }
}
customElements.define(BacklogView.selector, BacklogView);

cache=(()=>{return { BacklogView: BacklogView };})();return cache;};})();
const __brainExplorerModule9=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */
var _a;


const TREE_WIDTH_STORAGE_KEY = "brain.structure-tree.width";
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
 * @property {boolean} [folder] Preserve folder affordances when the node has no loaded children.
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
    /**
     * Provides the unique CSS selector used to identify and locate the StructureTree component within the DOM.
     * @returns {string} A string representing the component's custom element tag name.
     */
    static get selector() {
        return "brain-structure-tree";
    }
    /**
     * Maintains the internal state and configuration for the structure tree component, including node hierarchy, selection, and UI preferences.
     *
     * @type {StructureTreeModel}
     */
    #model = {
        nodes: [],
        selectedPath: "",
        expandedPaths: new Set(),
        toggleOnBranchSelect: true,
        title: "",
        toolbarActions: [],
        showSearch: true,
        searchPlaceholder: "Search...",
        sortDirection: "asc",
        emptyText: "No items yet.",
        defaultBranchIcon: null,
        defaultLeafIcon: null
    };
    /**
     * Stores the unique identifier of the currently active or expanded action node within the structure tree.
     *
     * @type {string}
     */
    #openActionNodeId = "";
    /**
     * Maintains the current text filter used to search and highlight nodes within the structure tree.
     *
     * @type {string}
     */
    #searchQuery = "";
    /**
     * A private state property that determines whether the structure tree's filtering mechanism is deactivated.
     *
     * @type {boolean}
     */
    #disableFilter = false;
    /**
     * Holds a reference to the HTML element used for resizing panes within the structure tree component.
     *
     * @type {HTMLElement | null}
     */
    #resizePane = null;
    /**
     * Holds a reference to the HTML element used as the resize handle for the structure tree component.
     *
     * @type {HTMLDivElement | null}
     */
    #resizeHandle = null;
    /**
     * Stores the unique identifier of the active resize pointer element, or null when no resizing operation is in progress.
     *
     * @type {number | null}
     */
    #resizePointerId = null;
    /**
     * Stores the initial horizontal coordinate of the cursor when a resize operation begins.
     *
     * @type {number}
     */
    #resizeOriginX = 0;
    /**
     * Stores the initial horizontal coordinate of the resize handle at the start of a resizing operation.
     *
     * @type {number}
     */
    #resizeOriginWidth = 0;
    /**
     * Handles global pointer down events to trigger the closure of menus located outside the event target.
     *
     * @type {(event: PointerEvent) => void}
     */
    #onDocumentPointerDown = (event) => this.#closeMenusOutside(event);
    /**
     * Handles pointer movement events to trigger the tree resizing logic based on the current pointer position.
     *
     * @type {(event: PointerEvent) => void}
     */
    #onResizePointerMove = (event) => this.#resizeTreeFromPointer(event);
    /**
     * An event handler that triggers the completion of the tree resizing process when a pointer-up event occurs.
     *
     * @type {(event: PointerEvent) => void}
     */
    #onResizePointerUp = (event) => this.#finishTreeResize(event);
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
            searchPlaceholder: value?.searchPlaceholder || "Search...",
            sortDirection: value?.sortDirection === "desc" ? "desc" : "asc",
            emptyText: value?.emptyText || "No items yet.",
            defaultBranchIcon: value.defaultBranchIcon ?? null,
            defaultLeafIcon: value.defaultLeafIcon ?? null
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
        this.#installResizeHandle();
        document.addEventListener("pointerdown", this.#onDocumentPointerDown);
    }
    /**
     * Release the document-level menu listener.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        document.removeEventListener("pointerdown", this.#onDocumentPointerDown);
        window.removeEventListener("pointermove", this.#onResizePointerMove);
        window.removeEventListener("pointerup", this.#onResizePointerUp);
        this.#resizeHandle?.remove();
        this.#resizeHandle = null;
        this.#resizePane = null;
    }
    /**
     * Mount a full-height drag target on the owning structure-tree pane.
     */
    #installResizeHandle() {
        const pane = this.closest(".structure-tree");
        if (!(pane instanceof HTMLElement) || pane.querySelector(":scope > .structure-tree-resize-handle"))
            return;
        this.#resizePane = pane;
        pane.classList.add("has-resize-handle");
        try {
            const storedWidth = Number(localStorage.getItem(TREE_WIDTH_STORAGE_KEY) || 0);
            if (storedWidth)
                this.#setTreeWidth(storedWidth);
        }
        catch {
            // Storage can be unavailable in restricted browser contexts; resizing still works in-memory.
        }
        const handle = document.createElement("div");
        handle.className = "structure-tree-resize-handle";
        handle.setAttribute("role", "separator");
        handle.setAttribute("aria-label", "Resize tree");
        handle.setAttribute("aria-orientation", "vertical");
        handle.tabIndex = 0;
        handle.addEventListener("pointerdown", event => this.#startTreeResize(event));
        handle.addEventListener("keydown", event => this.#resizeTreeFromKeyboard(event));
        pane.append(handle);
        this.#resizeHandle = handle;
    }
    /**
     * Begin one right-edge horizontal resize gesture.
     * @param {PointerEvent} event The pointer event triggering the resize operation, used to validate the primary mouse button and capture initial coordinates.
     */
    #startTreeResize(event) {
        if (!this.#resizePane || event.button !== 0)
            return;
        event.preventDefault();
        this.#resizePointerId = event.pointerId;
        this.#resizeOriginX = event.clientX;
        this.#resizeOriginWidth = this.#resizePane.getBoundingClientRect().width;
        this.#resizePane.classList.add("is-resizing");
        this.#resizeHandle?.setPointerCapture?.(event.pointerId);
        window.addEventListener("pointermove", this.#onResizePointerMove);
        window.addEventListener("pointerup", this.#onResizePointerUp);
    }
    /**
     * Update the sidebar while the pointer moves anywhere along the viewport.
     * @param {PointerEvent} event The pointer event containing the current client coordinates and pointer identifier.
     */
    #resizeTreeFromPointer(event) {
        if (event.pointerId !== this.#resizePointerId)
            return;
        this.#setTreeWidth(this.#resizeOriginWidth + event.clientX - this.#resizeOriginX);
    }
    /**
     * Finish and persist one resize gesture.
     * @param {PointerEvent} event The pointer event that triggered the completion of the resize action.
     */
    #finishTreeResize(event) {
        if (event.pointerId !== this.#resizePointerId)
            return;
        this.#resizePointerId = null;
        this.#resizePane?.classList.remove("is-resizing");
        window.removeEventListener("pointermove", this.#onResizePointerMove);
        window.removeEventListener("pointerup", this.#onResizePointerUp);
        this.#persistTreeWidth();
    }
    /**
     * Support precise keyboard resizing from the same separator.
     * @param {KeyboardEvent} event The keyboard event containing the key pressed and modifier state.
     */
    #resizeTreeFromKeyboard(event) {
        if (!this.#resizePane || !["ArrowLeft", "ArrowRight"].includes(event.key))
            return;
        event.preventDefault();
        const direction = event.key === "ArrowRight" ? 1 : -1;
        this.#setTreeWidth(this.#resizePane.getBoundingClientRect().width + direction * (event.shiftKey ? 40 : 12));
        this.#persistTreeWidth();
    }
    /**
     * Clamp and apply a shared desktop tree width.
     * @param {number} width The requested width in pixels to be applied to the pane.
     */
    #setTreeWidth(width) {
        if (!this.#resizePane)
            return;
        const maximum = Math.min(640, window.innerWidth * 0.48);
        const nextWidth = Math.max(380, Math.min(maximum, Number(width) || 380));
        this.#resizePane.style.width = `${Math.round(nextWidth)}px`;
        this.#resizeHandle?.setAttribute("aria-valuenow", String(Math.round(nextWidth)));
    }
    /**
     * Persist the most recent shared tree width when browser storage is available.
     */
    #persistTreeWidth() {
        if (!this.#resizePane)
            return;
        try {
            localStorage.setItem(TREE_WIDTH_STORAGE_KEY, String(Math.round(this.#resizePane.getBoundingClientRect().width)));
        }
        catch {
            // Keep the active width even when persistence is unavailable.
        }
    }
    /**
     * Recursively determines if a structure node or any of its descendants match the current search query, unless filtering is disabled.
     * @param {StructureTreeNode} node The structure node being evaluated for a match against the search criteria.
     * @returns {boolean} True if the node's label or path contains the search query, or if any of its children match; otherwise false.
     */
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
    /**
     * Updates the component's innerHTML by rendering a toolbar, an optional search input, and a sorted, filtered list of structure nodes based on the current model state.
     */
    #render() {
        const rootDirection = this.#model.sortDirection === "desc" ? -1 : 1;
        const sortedRootNodes = [...this.#model.nodes].sort((left, right) => this.#compareNodes(left, right, rootDirection));
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
                            <time>${escapeHtml(node.timestamp || "No date")}</time>
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
        const sortedChildren = [...children].sort((left, right) => this.#compareNodes(left, right, childDirection));
        const isFolder = hasChildren || node.folder === true;
        const caret = hasChildren
            ? icon(expanded ? "chevronDown" : "chevronRight")
            : isFolder ? "+" : "";
        return `
            <div class="tree-node-wrap" role="treeitem" aria-level="${depth}" ${hasChildren ? `aria-expanded="${expanded}"` : ""} aria-selected="${active}" style="--depth: ${depth};">
                <div class="tree-item ${active ? "is-active" : ""}">
                    <button class="tree-node ${hasChildren ? "" : "tree-node--leaf"} ${sourceClass} ${active ? "is-active" : ""}"${sourceStyle}
                        data-tree-id="${escapeHtml(node.id || node.path)}" data-tree-path="${escapeHtml(node.path)}" data-tree-branch="${hasChildren}"
                        title="${escapeHtml(node.label)}">
                        <span class="tree-caret ${isFolder && !hasChildren ? "is-empty-folder" : ""}">${caret}</span>
                        ${icon(node.icon || (isFolder ? defaultBranch : defaultLeaf))}
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
            <span class="tree-action-trigger" data-tree-actions="${nodeId}" title="Actions" aria-label="Actions">
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
            this.#searchQuery = event.currentTarget instanceof HTMLInputElement ? event.currentTarget.value : "";
            // Render only nodes container to keep focus and cursor position!
            const rootDirection = this.#model.sortDirection === "desc" ? -1 : 1;
            const sortedRootNodes = [...this.#model.nodes].sort((left, right) => this.#compareNodes(left, right, rootDirection));
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
        const eventTarget = event.target instanceof Element ? event.target : null;
        if (eventTarget?.closest("[data-tree-actions]")) {
            return;
        }
        const id = button.getAttribute("data-tree-id") || "";
        const path = button.getAttribute("data-tree-path") || "";
        const branch = button.getAttribute("data-tree-branch") === "true";
        const clickedCaret = Boolean(eventTarget?.closest(".tree-caret"));
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
     * Respect explicit super-domain order before the default branch-first tree order.
     * @param {StructureTreeNode} left The first node to compare.
     * @param {StructureTreeNode} right The second node to compare.
     * @param {number} direction A multiplier used to invert or maintain the sort order direction.
     * @returns {number} A numeric value indicating whether the left node precedes, follows, or is equivalent to the right node.
     */
    #compareNodes(left, right, direction) {
        if (left.sortKey !== undefined || right.sortKey !== undefined) {
            return direction * String(left.sortKey || left.label || "")
                .localeCompare(String(right.sortKey || right.label || ""));
        }
        const leftHas = Array.isArray(left.children) && left.children.length > 0;
        const rightHas = Array.isArray(right.children) && right.children.length > 0;
        if (leftHas !== rightHas)
            return leftHas ? -1 : 1;
        return direction * String(left.label || "").localeCompare(String(right.label || ""));
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
            for (const tree of Array.from(trees)) {
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
        if (!this.#openActionNodeId || (event.target instanceof Node && this.contains(event.target))) {
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
const __brainExplorerModule10=(()=>{let cache;return()=>{if(cache)return cache;
const { documentPictureInPictureController } = __brainExplorerModule11();
const { BacklogPip } = __brainExplorerModule12();
/**
 * Owns native Document Picture-in-Picture lifecycle for the Backlog feature.
 *
 * The controller isolates browser-window creation, style transfer, desktop capture,
 * component mounting, and disposal from the route-level Backlog Web Component.
 *
 * @module presentation/backlog/controllers/backlog-pip-controller
 */


/**
 * Manages the single native Backlog PiP window allowed per route instance.
 */
class BacklogPipController {
    /**
     * Browser window currently hosting the PiP component.
     * @type {Window | null}
     */
    #pipWindow = null;
    /**
     * Mounted task component synchronized by subsequent Backlog responses.
     * @type {BacklogPip | null}
     */
    #pipComponent = null;
    /**
     * Prevents overlapping native `requestWindow` calls.
     * @type {boolean}
     */
    #requestInFlight = false;
    /**
     * @returns {boolean} True when the current browser exposes native Document PiP.
     */
    supported() {
        return documentPictureInPictureController(window) !== null;
    }
    /**
     * Open or focus the native PiP window and mount its dedicated component.
     *
     * @param {OpenBacklogPipInput} input Current tasks and the application mutation callback.
     *
     * @returns {Promise<void>} A promise that resolves once the window request process has completed or failed.
     */
    async open(input) {
        if (!this.supported() || this.#requestInFlight)
            return;
        if (this.#pipWindow && !this.#pipWindow.closed) {
            this.#pipWindow.focus();
            return;
        }
        this.#requestInFlight = true;
        try {
            const nativeController = documentPictureInPictureController(window);
            if (!nativeController)
                return;
            const pipWindow = await nativeController.requestWindow({
                width: 420,
                height: 620,
                disallowReturnToOpener: false,
                preferInitialWindowPlacement: true
            });
            this.#pipWindow = pipWindow;
            this.#copyStyles(pipWindow.document);
            pipWindow.document.title = "Backlog";
            pipWindow.document.documentElement.dataset.theme = document.documentElement.dataset.theme || "dark";
            pipWindow.document.body.className = "backlog-pip-document";
            const component = new BacklogPip();
            component.tasks = [...input.tasks];
            component.onCaptureScreen = () => this.#captureScreen();
            component.onAddTask = input.onAddTask;
            pipWindow.document.body.replaceChildren(component);
            this.#pipComponent = component;
            pipWindow.addEventListener("pagehide", () => this.#release(pipWindow), { once: true });
        }
        catch (error) {
            console.warn("Unable to open the Document Picture-in-Picture window.", error);
        }
        finally {
            this.#requestInFlight = false;
        }
    }
    /**
     * Synchronize the mounted component after the authoritative task list changes.
     *
     * @param {readonly BacklogPipTaskViewModel[]} tasks Refreshed task projection from the Backlog endpoint.
     */
    syncTasks(tasks) {
        if (this.#pipComponent)
            this.#pipComponent.tasks = [...tasks];
    }
    /**
     * Close the active native window and release its component references.
     */
    close() {
        const pipWindow = this.#pipWindow;
        if (!pipWindow || pipWindow.closed)
            return;
        pipWindow.close();
        this.#release(pipWindow);
    }
    /**
     * Copy same-origin Explorer styles into the isolated PiP document.
     *
     * @param {Document} pipDocument Destination document created by the native PiP API.
     */
    #copyStyles(pipDocument) {
        for (const stylesheet of Array.from(document.styleSheets)) {
            try {
                if (stylesheet.href) {
                    const link = pipDocument.createElement("link");
                    link.rel = "stylesheet";
                    link.href = stylesheet.href;
                    pipDocument.head.appendChild(link);
                }
                else {
                    const style = pipDocument.createElement("style");
                    style.textContent = Array.from(stylesheet.cssRules, rule => rule.cssText).join("\n");
                    pipDocument.head.appendChild(style);
                }
            }
            catch (_error) {
                // Browser-owned and cross-origin stylesheets are optional in PiP.
            }
        }
    }
    /**
     * @returns {Promise<string | null>} PNG data URL of a user-selected desktop surface, or null on cancellation.
     */
    async #captureScreen() {
        try {
            const video = { mediaSource: "screen" };
            const stream = await navigator.mediaDevices.getDisplayMedia({ video });
            const videoElement = document.createElement("video");
            videoElement.srcObject = stream;
            await videoElement.play();
            await new Promise(resolve => { videoElement.onloadedmetadata = () => resolve(); });
            await new Promise(resolve => window.setTimeout(resolve, 300));
            const canvas = document.createElement("canvas");
            canvas.width = videoElement.videoWidth;
            canvas.height = videoElement.videoHeight;
            const context = canvas.getContext("2d");
            if (!context)
                return null;
            context.drawImage(videoElement, 0, 0);
            stream.getTracks().forEach(track => track.stop());
            return canvas.toDataURL("image/png");
        }
        catch (error) {
            console.error("Screenshot capture failed:", error);
            return null;
        }
    }
    /**
     * Release state only when the closing window is the controller's active window.
     *
     * @param {Window} pipWindow Window reported by the browser lifecycle event.
     */
    #release(pipWindow) {
        if (this.#pipWindow !== pipWindow)
            return;
        this.#pipComponent?.remove();
        this.#pipComponent = null;
        this.#pipWindow = null;
    }
}

cache=(()=>{return { BacklogPipController: BacklogPipController };})();return cache;};})();
const __brainExplorerModule11=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Browser contract for the Document Picture-in-Picture API.
 *
 * The API remains experimental and is not present in the baseline DOM library
 * shipped with TypeScript. This declaration models only the surface consumed by
 * Brain Explorer and leaves feature detection mandatory at runtime.
 *
 * @module presentation/backlog/contracts/document-picture-in-picture
 */
/**
 * Reads the optional experimental controller without widening the global
 * `Window` declaration for browsers that do not implement the API.
 *
 * @param {Window} browserWindow Window whose optional capability must be inspected.
 * @returns {DocumentPictureInPictureController | null} The usable controller, or `null` when feature detection fails.
 */
function documentPictureInPictureController(browserWindow) {
    const candidate = Reflect.get(browserWindow, "documentPictureInPicture");
    if (typeof candidate !== "object" || candidate === null)
        return null;
    const requestWindow = Reflect.get(candidate, "requestWindow");
    return typeof requestWindow === "function"
        ? { requestWindow: options => requestWindow.call(candidate, options) }
        : null;
}

cache=(()=>{return { documentPictureInPictureController: documentPictureInPictureController };})();return cache;};})();
const __brainExplorerModule12=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
const { isBacklogPipPriority } = __brainExplorerModule13();
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
    /**
     * Provides the unique CSS selector string used to identify the BacklogPip component in the DOM.
     * @returns {string} The string identifier 'brain-backlog-pip'.
     */
    static get selector() {
        return "brain-backlog-pip";
    }
    /**
     * Maintains a private collection of task view models for the backlog pipeline display.
     *
     * @type {BacklogPipTaskViewModel[]}
     */
    #tasks = [];
    /**
     * Maintains a private set of unique identifiers representing the currently expanded items within the backlog pipeline view.
     *
     * @type {Set<string>}
     */
    #expandedIds = new Set();
    /**
     * Tracks whether the event listeners for the backlog pipeline have been attached to the DOM.
     *
     * @type {boolean}
     */
    #eventsBound = false;
    /**
     * Tracks the visibility state of the backlog item form within the BacklogPip component.
     *
     * @type {boolean}
     */
    #isFormOpen = false;
    /**
     * Tracks the submission state of the BacklogPip component to prevent concurrent requests.
     *
     * @type {boolean}
     */
    #isSubmitting = false;
    /**
     * Stores the current error message associated with the backlog form validation state.
     *
     * @type {string}
     */
    #formError = "";
    /**
     * Maintains the internal state of a draft form for the BacklogPip component, initialized with default values for title, description, and priority.
     *
     * @type {BacklogPipFormDraft}
     */
    #formDraft = { title: "", description: "", priority: "HIGH" };
    /**
     * Stores the base64-encoded data URL of the picture-in-picture image or null if no image is currently loaded.
     *
     * @type {string | null}
     */
    #pipImageDataUrl = null;
    /**
     * Maintains a private collection of marking rectangles used for the BacklogPip visual representation.
     *
     * @type {BacklogPipMarkingRectangle[]}
     */
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
    /**
     * Lifecycle hook that initializes the component by binding event listeners and executing the initial render process.
     */
    connectedCallback() {
        this.#bindEvents();
        this.#render();
    }
    /**
     * Conditionally renders either the form view or the list view based on the current open state of the form.
     */
    #render() {
        if (this.#isFormOpen) {
            this.#renderForm();
        }
        else {
            this.#renderList();
        }
    }
    /**
     * Updates the component's inner HTML to render the Backlog PIP layout, including the header with task counts and the grouped task list.
     */
    #renderList() {
        this.innerHTML = `
            <div class="pip-root" style="display: flex; flex-direction: column; height: 100vh; font-family: var(--font); background: var(--bg); color: var(--text);">
                <header class="pip-header" style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong class="pip-title" style="font-size: 14px; color: var(--text-strong); display: flex; align-items: center; gap: 6px;">
                        ${icon("checkSquare")} Backlog PIP
                    </strong>
                    <span class="pip-count" style="font-size: 12px; color: var(--text-muted); margin-left: auto; margin-right: 12px;">
                        ${this.#tasks.length} tasks
                    </span>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <button class="icon-action" data-action="pip-capture-screen" title="Capture screen and create task" style="border: 0; background: transparent; cursor: pointer; color: var(--primary);">${icon("camera")}</button>
                        <button class="icon-action" data-action="pip-add-task" title="Create task" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("plus")}</button>
                    </div>
                </header>
                <main class="pip-body scroll-area" style="flex: 1; overflow-y: auto; padding: 12px; display: grid; gap: 10px; background: color-mix(in srgb, var(--bg), transparent 40%);">
                    ${this.#renderGroups()}
                </main>
            </div>
        `;
    }
    /**
     * Populates the component's innerHTML with a task creation form, including conditional image preview and error messaging, then initializes event bindings and draft restoration.
     */
    #renderForm() {
        this.innerHTML = `
            <div class="pip-root" style="display: flex; flex-direction: column; height: 100vh; font-family: var(--font); background: var(--bg); color: var(--text);">
                <header class="pip-header" style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong class="pip-title" style="font-size: 14px; color: var(--text-strong); display: flex; align-items: center; gap: 6px;">
                        ${icon("plus")} New Task (PIP)
                    </strong>
                    <button class="icon-action" data-action="pip-close-form" title="Back" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
                </header>
                <form class="pip-add-form" style="padding: 12px; display: flex; flex-direction: column; gap: 8px; flex: 1; overflow-y: auto; background: var(--bg);">
                    <input type="text" id="pip-title-input" placeholder="Title" required style="padding: 6px 8px; font-size: 13px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface-strong); color: var(--text-strong);">
                    <select id="pip-priority-select" style="padding: 6px; font-size: 13px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface-strong); color: var(--text-strong);">
                        <option value="HIGH">HIGH</option>
                        <option value="MEDIUM">MEDIUM</option>
                        <option value="LOW">LOW</option>
                    </select>
                    <textarea id="pip-desc-input" placeholder="Description (use Ctrl+V to paste an image)" required style="padding: 6px 8px; font-size: 13px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface-strong); color: var(--text-strong); min-height: 80px; resize: vertical;"></textarea>

                    <button type="button" class="ghost-action compact-action" data-action="pip-form-capture" style="display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-size: 12px; height: 32px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface-muted); color: var(--primary);">
                        ${icon("camera")} Capture Visual Reference
                    </button>

                    ${this.#pipImageDataUrl ? `
                        <div style="display: flex; flex-direction: column; gap: 6px; border: 1px solid var(--border); padding: 8px; border-radius: 6px; background: var(--surface);">
                            <div class="marking-container" style="position: relative; display: inline-block; max-width: 100%;">
                                <img id="pip-preview-img" src="${this.#pipImageDataUrl}" style="max-width: 100%; display: block; max-height: 200px; object-fit: contain;">
                                <svg id="pip-marking-svg" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; cursor: crosshair; touch-action: none;"></svg>
                            </div>
                            <div style="display: flex; gap: 8px; align-items: center; justify-content: space-between;">
                                <button type="button" class="ghost-action compact-action" data-action="pip-clear-marks" style="padding: 4px 8px; font-size: 11px;">Clear</button>
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
                    <button type="submit" class="primary-action" ${this.#isSubmitting ? "disabled" : ""} style="padding: 8px; font-size: 13px; font-weight: bold; border-radius: 4px; margin-top: auto;">${this.#isSubmitting ? "Creating..." : "Create Task"}</button>
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
        if (priority instanceof HTMLSelectElement && isBacklogPipPriority(priority.value)) {
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
    /**
     * Generates an HTML string representing tasks grouped by their domain, sorted alphabetically, or a fallback empty state message.
     * @returns {string} An HTML string containing the grouped task sections or an empty state notification.
     */
    #renderGroups() {
        if (!this.#tasks.length) {
            return `<p class="pip-empty" style="text-align: center; color: var(--text-muted); padding: 24px;">No tasks.</p>`;
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
            const tasks = groups.get(domain) ?? [];
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
    /**
     * Generates an HTML string representation of a task item, incorporating its status, priority, and expansion state.
     * @param {BacklogPipTaskViewModel} task The view model containing the task's identity, completion status, priority, and descriptive content.
     * @returns {string} An HTML string containing the structured markup for the task's row and optional detail section.
     */
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
    /**
     * Idempotently attaches a click event listener to manage the expansion of items, the opening of the task creation form, and the triggering of screen capture functionality.
     */
    #bindEvents() {
        if (this.#eventsBound)
            return;
        this.#eventsBound = true;
        this.addEventListener("click", async (event) => {
            const target = event.target instanceof Element ? event.target : null;
            const toggle = target?.closest("[data-pip-toggle]");
            if (toggle) {
                const id = toggle.dataset.pipToggle ?? "";
                if (this.#expandedIds.has(id)) {
                    this.#expandedIds.delete(id);
                }
                else {
                    this.#expandedIds.add(id);
                }
                this.#render();
                return;
            }
            const addBtn = target?.closest("[data-action='pip-add-task']");
            if (addBtn) {
                this.#isFormOpen = true;
                this.#resetFormDraft();
                this.#pipImageDataUrl = null;
                this.#pipMarkingRects = [];
                this.#render();
                return;
            }
            const captureBtn = target?.closest("[data-action='pip-capture-screen']");
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
    /**
     * Attaches event listeners to the form for handling closure, screen capture, image pasting, and task submission.
     */
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
        descInput?.addEventListener("paste", (event) => {
            const items = event.clipboardData?.items;
            if (!items)
                return;
            for (let index = 0; index < items.length; index += 1) {
                const item = items[index];
                if (!item)
                    continue;
                if (item.type.startsWith("image/")) {
                    event.preventDefault();
                    const file = item.getAsFile();
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = () => {
                            const result = reader.result;
                            if (typeof result !== "string")
                                return;
                            this.#pipImageDataUrl = result;
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
                submitButton.textContent = "Creating...";
            }
            try {
                const completion = await this.onAddTask({ title, description, priority, image: bakedImage });
                if (!completion?.ok) {
                    this.#formError = completion?.message || "Could not create the task.";
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
                this.#formError = error instanceof Error ? error.message : "Could not create the task.";
            }
            finally {
                this.#isSubmitting = false;
                this.#render();
            }
        });
    }
    /**
     * Initializes pointer event listeners on an SVG element to enable interactive drawing of colored rectangular markings over a preview image and manages the storage of normalized marking coordinates.
     */
    #bindFormImageMarking() {
        const svg = this.querySelector("#pip-marking-svg");
        const img = this.querySelector("#pip-preview-img");
        if (!svg || !img)
            return;
        let startX = 0, startY = 0;
        let isDrawing = false;
        let activeRect = null;
        svg.addEventListener("pointerdown", (e) => {
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
        svg.addEventListener("pointermove", (e) => {
            if (!isDrawing || !activeRect)
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
        svg.addEventListener("pointerup", (e) => {
            if (!isDrawing || !activeRect)
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
    /**
     * Renders the current preview image onto a canvas, overlays defined marking rectangles and labels, and exports the result as a PNG data URL.
     * @returns {Promise<string | null>} A base64 encoded PNG image string containing the marked preview, or null if the image element or canvas context is unavailable.
     */
    async #bakeMarkedImage() {
        const img = this.querySelector("#pip-preview-img");
        if (!img)
            return null;
        if (!img.complete) {
            await new Promise(resolve => {
                img.addEventListener("load", () => resolve(), { once: true });
            });
        }
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d");
        if (!ctx)
            return null;
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
const __brainExplorerModule13=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Runtime validation helpers for backlog PiP form values.
 *
 * Browser form controls expose arbitrary strings even when their current HTML
 * options are closed. This validator establishes the runtime boundary required
 * before a string may enter the strongly typed presentation model.
 *
 * @module presentation/backlog/validators/backlog-pip-priority
 */
/**
 * Closed set of priority values accepted by the backlog application contract.
 */
const BACKLOG_PIP_PRIORITIES = new Set(["HIGH", "MEDIUM", "LOW"]);
/**
 * Determines whether an untrusted browser value is a supported task priority.
 *
 * @param {unknown} value Arbitrary value read from a DOM form control or external caller.
 * @returns {boolean} `true` when `value` belongs to the supported priority union.
 */
function isBacklogPipPriority(value) {
    return typeof value === "string" && BACKLOG_PIP_PRIORITIES.has(value);
}

cache=(()=>{return { isBacklogPipPriority: isBacklogPipPriority };})();return cache;};})();
const __brainExplorerModule14=(()=>{let cache;return()=>{if(cache)return cache;
const { VisualReferenceEditor } = __brainExplorerModule15();
/**
 * Coordinates Backlog visual-reference editor state and desktop capture.
 *
 * The controller owns DOM adaptation specific to the atomic editor while the route
 * component retains task-form lifecycle and persistence decisions.
 *
 * @module presentation/backlog/controllers/backlog-visual-reference-controller
 */

/**
 * Controls the visual-reference subtree mounted inside one Backlog component host.
 */
class BacklogVisualReferenceController {
    /**
     * Backlog Custom Element used as the query boundary for editor controls.
     * @type {HTMLElement}
     */
    #host;
    /**
     * Bind the controller to one route component instance.
     *
     * @param {HTMLElement} host Backlog host containing the dialog and atomic editor.
     */
    constructor(host) {
        this.#host = host;
    }
    /**
     * Load an image source and transition the drop area to its populated state.
     *
     * @param {string} dataUrl Data URL or same-origin endpoint understood by the editor.
     */
    displayImage(dataUrl) {
        const editor = this.#editor();
        if (!editor)
            return;
        this.#setHasImage(true);
        editor.loadImage(dataUrl);
    }
    /**
     * Reset editor marks, image state, drop-area styling, and file-input availability.
     */
    reset() {
        this.#editor()?.reset();
        this.#setHasImage(false);
    }
    /**
     * @returns {Promise<string | null>} PNG export from the mounted editor, or null when it is unavailable.
     */
    async exportPng() {
        return this.#editor()?.exportPng() ?? null;
    }
    /**
     * Capture a user-selected desktop surface and load it into the task editor.
     *
     * @returns {Promise<void>} Promise resolved after capture, modal opening, and editor loading.
     */
    async captureScreen() {
        try {
            const videoConstraints = { mediaSource: "screen" };
            const stream = await navigator.mediaDevices.getDisplayMedia({ video: videoConstraints });
            const video = document.createElement("video");
            video.srcObject = stream;
            await video.play();
            await new Promise(resolve => { video.onloadedmetadata = () => resolve(); });
            await new Promise(resolve => window.setTimeout(resolve, 300));
            const canvas = document.createElement("canvas");
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const context = canvas.getContext("2d");
            if (!context)
                return;
            context.drawImage(video, 0, 0);
            stream.getTracks().forEach(track => track.stop());
            this.#host.querySelector("[data-action='open-create-modal']")?.click();
            this.displayImage(canvas.toDataURL("image/png"));
        }
        catch (error) {
            console.error("Screen capture failed:", error);
        }
    }
    /**
     * @returns {VisualReferenceEditor | null} Mounted atomic visual-reference editor, or null before rendering.
     */
    #editor() {
        const editor = this.#host.querySelector(VisualReferenceEditor.selector);
        return editor instanceof VisualReferenceEditor ? editor : null;
    }
    /**
     * Synchronize populated-state classes and native file-input availability.
     *
     * @param {boolean} hasImage Whether the atomic editor currently owns an image.
     */
    #setHasImage(hasImage) {
        this.#host.querySelector("[data-role='image-upload-zone']")?.classList.toggle("has-image", hasImage);
        this.#host.querySelector("[data-role='image-preview-area']")?.classList.toggle("has-image", hasImage);
        const fileInput = this.#host.querySelector("[data-role='modal-image-file']");
        if (fileInput instanceof HTMLInputElement)
            fileInput.disabled = hasImage;
    }
}

cache=(()=>{return { BacklogVisualReferenceController: BacklogVisualReferenceController };})();return cache;};})();
const __brainExplorerModule15=(()=>{let cache;return()=>{if(cache)return cache;
const { icon } = __brainExplorerModule5();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

/**
 * Narrow a raw shape-control value to one supported visual-reference mark type.
 *
 * @param {string | undefined} value Untrusted string read from the native shape selector.
 * @returns {boolean} True only when the editor has rendering and interaction semantics for it.
 */
function isMarkType(value) {
    return value === "rectangle" || value === "arrow" || value === "path" || value === "label";
}
/**
 * VisualReferenceEditor owns image loading, canvas marking, selection, and PNG export.
 *
 * @element brain-visual-reference-editor
 */
class VisualReferenceEditor extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the VisualReferenceEditor component in the DOM.
     * @returns {string} A string representing the component's DOM selector.
     */
    static get selector() {
        return "brain-visual-reference-editor";
    }
    /**
     * Holds a reference to the HTML image element used for visual reference, or null if no image is currently assigned.
     *
     * @type {HTMLImageElement | null}
     */
    #image = null;
    /**
     * Tracks the asynchronous loading state of the visual reference image.
     *
     * @type {Promise<boolean>}
     */
    #imageLoad = Promise.resolve(false);
    /**
     * Maintains a private collection of visual mark entities used within the reference editor.
     *
     * @type {VisualMark[]}
     */
    #marks = [];
    /**
     * Tracks the zero-based index of the currently selected mark within the visual reference editor, defaulting to -1 to indicate no selection.
     *
     * @type {number}
     */
    #selectedMarkIndex = -1;
    /**
     * Stores the current unsaved text input for a label within the visual reference editor.
     *
     * @type {string}
     */
    #labelDraft = "";
    /**
     * Render the editor once when it joins the document.
     */
    connectedCallback() {
        if (this.childElementCount)
            return;
        this.innerHTML = `
            <div class="marking-container">
                <canvas data-role="marking-canvas" aria-label="Image marking canvas"></canvas>
            </div>
            <details class="marking-toolbar-pill">
                <summary>${icon("edit")}<span>Marks</span>${icon("chevronDown")}</summary>
                <div class="marking-toolbar">
                    <label class="mark-color-control"><span>Color</span><input type="color" data-action="change-mark-color" value="#ff3b30" aria-label="Mark color"></label>
                    <button type="button" class="mark-delete-control" data-action="delete-selected-mark" title="Delete selected mark" aria-label="Delete selected mark" disabled>${icon("trash")}</button>
                    <label class="mark-shape-control"><span>Shape</span><select data-action="change-mark-shape"><option value="rectangle">Rectangle</option><option value="arrow">Arrow</option><option value="path">Path</option><option value="label">LABEL</option></select></label>
                    <label class="mark-label-control"><span>Label</span><input type="text" data-action="change-mark-label" placeholder="LABEL text"></label>
                </div>
            </details>
        `;
        this.#bindEvents();
        this.reset();
    }
    /**
     * Load an image as the immutable base layer of the editor canvas.
     * @param {string} source The URL or data URI of the image to be loaded into the editor.
     * @returns {Promise<boolean>} A promise that resolves to true if the image was successfully loaded and the canvas initialized, or false otherwise.
     */
    loadImage(source) {
        this.#marks = [];
        this.#selectedMarkIndex = -1;
        this.#labelDraft = "";
        this.#image = null;
        this.#imageLoad = new Promise(resolve => {
            const image = new Image();
            image.onload = () => {
                this.#image = image;
                const canvas = this.#canvas();
                if (!canvas) {
                    resolve(false);
                    return;
                }
                canvas.width = image.naturalWidth;
                canvas.height = image.naturalHeight;
                this.hidden = false;
                this.#renderCanvas();
                resolve(true);
            };
            image.onerror = () => resolve(false);
            image.src = source;
        });
        return this.#imageLoad;
    }
    /**
     * Clear the current image and all transient mark state.
     */
    reset() {
        this.#image = null;
        this.#imageLoad = Promise.resolve(false);
        this.#marks = [];
        this.#selectedMarkIndex = -1;
        this.#labelDraft = "";
        const canvas = this.#canvas();
        if (canvas) {
            canvas.width = 1;
            canvas.height = 1;
        }
        this.hidden = true;
    }
    /**
     * Export the canvas through the same renderer used by the interactive preview.
     * @returns {Promise<string | null>} A base64-encoded PNG image string, or null if the image has not loaded or the canvas is unavailable.
     */
    async exportPng() {
        if (!await this.#imageLoad)
            return null;
        const canvas = this.#canvas();
        if (!canvas || !this.#image)
            return null;
        this.#renderCanvas(false);
        const result = canvas.toDataURL("image/png");
        this.#renderCanvas(true);
        return result;
    }
    /**
     * Return the editor canvas when it is mounted.
     * @returns {HTMLCanvasElement | null} The HTMLCanvasElement if found and valid, otherwise null.
     */
    #canvas() {
        const canvas = this.querySelector("[data-role='marking-canvas']");
        return canvas instanceof HTMLCanvasElement ? canvas : null;
    }
    /**
     * Bind canvas gestures and toolbar controls.
     */
    #bindEvents() {
        const canvas = this.#canvas();
        if (!canvas)
            return;
        let interaction = null;
        const point = (event) => {
            const bounds = canvas.getBoundingClientRect();
            return {
                x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / Math.max(1, bounds.width))),
                y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / Math.max(1, bounds.height))),
                bounds
            };
        };
        canvas.addEventListener("pointerdown", event => {
            event.preventDefault();
            const start = point(event);
            const selectedIndex = this.#markIndexAtPoint(start.x, start.y, start.bounds);
            if (selectedIndex >= 0) {
                const selectedMark = this.#marks[selectedIndex];
                if (!selectedMark)
                    return;
                this.#selectedMarkIndex = selectedIndex;
                interaction = {
                    mode: "drag",
                    index: selectedIndex,
                    start,
                    original: structuredClone(selectedMark)
                };
                canvas.setPointerCapture(event.pointerId);
                this.#renderCanvas();
                return;
            }
            const selectedType = this.querySelector("[data-action='change-mark-shape']")?.value;
            const type = isMarkType(selectedType) ? selectedType : "rectangle";
            const color = this.querySelector("[data-action='change-mark-color']")?.value || "#ff3b30";
            if (type === "label") {
                const labelInput = this.querySelector("[data-action='change-mark-label']");
                const label = labelInput?.value.trim() || "";
                if (!label) {
                    labelInput?.focus();
                    return;
                }
                this.#marks.push({ type, x: start.x, y: start.y, w: 0, h: 0, points: null, color, label });
                this.#selectedMarkIndex = this.#marks.length - 1;
                this.#labelDraft = label;
                this.#renderCanvas();
                return;
            }
            const drawType = type;
            const index = this.#marks.length;
            this.#marks.push({
                type: drawType,
                x: start.x,
                y: start.y,
                w: 0,
                h: 0,
                points: drawType === "path" ? [{ x: start.x, y: start.y }] : null,
                color,
                label: String(this.#shapeMarkCount() + 1)
            });
            this.#selectedMarkIndex = index;
            interaction = { mode: "draw", index, start, type: drawType };
            canvas.setPointerCapture(event.pointerId);
            this.#renderCanvas();
        });
        canvas.addEventListener("pointermove", event => {
            if (!interaction)
                return;
            const current = point(event);
            if (interaction.mode === "drag") {
                const dx = current.x - interaction.start.x;
                const dy = current.y - interaction.start.y;
                const original = interaction.original;
                const mark = { ...original, x: original.x + dx, y: original.y + dy };
                if (mark.points && original.points) {
                    mark.points = original.points.map(item => ({ x: item.x + dx, y: item.y + dy }));
                }
                this.#marks[interaction.index] = mark;
            }
            else {
                const mark = this.#marks[interaction.index];
                if (!mark)
                    return;
                mark.w = current.x - interaction.start.x;
                mark.h = current.y - interaction.start.y;
                if (interaction.type === "path" && mark.points)
                    mark.points.push({ x: current.x, y: current.y });
            }
            this.#renderCanvas();
        });
        canvas.addEventListener("pointerup", event => {
            if (!interaction)
                return;
            const current = point(event);
            if (interaction.mode === "draw") {
                const mark = this.#marks[interaction.index];
                if (!mark)
                    return;
                mark.w = current.x - interaction.start.x;
                mark.h = current.y - interaction.start.y;
                const valid = interaction.type === "path"
                    ? (mark.points?.length || 0) > 2
                    : Math.hypot(mark.w, mark.h) > .01;
                if (!valid) {
                    this.#marks.splice(interaction.index, 1);
                    this.#selectedMarkIndex = -1;
                    this.#renumberShapeMarks();
                }
            }
            interaction = null;
            canvas.releasePointerCapture?.(event.pointerId);
            this.#renderCanvas();
        });
        this.querySelector("[data-action='delete-selected-mark']")?.addEventListener("click", event => {
            event.stopPropagation();
            if (this.#selectedMarkIndex < 0 || this.#selectedMarkIndex >= this.#marks.length)
                return;
            this.#marks.splice(this.#selectedMarkIndex, 1);
            this.#selectedMarkIndex = -1;
            this.#renumberShapeMarks();
            this.#renderCanvas();
        });
        this.querySelector("[data-action='change-mark-color']")?.addEventListener("input", event => {
            const input = event.currentTarget;
            if (!(input instanceof HTMLInputElement))
                return;
            if (this.#selectedMarkIndex < 0)
                return;
            const selected = this.#marks[this.#selectedMarkIndex];
            if (!selected)
                return;
            selected.color = input.value;
            this.#renderCanvas();
        });
        this.querySelector("[data-action='change-mark-label']")?.addEventListener("input", event => {
            const input = event.currentTarget;
            if (!(input instanceof HTMLInputElement))
                return;
            this.#labelDraft = input.value;
            const selected = this.#marks[this.#selectedMarkIndex];
            if (selected?.type !== "label")
                return;
            selected.label = input.value;
            this.#renderCanvas();
        });
    }
    /**
     * Return the number of numbered geometric marks.
     * @returns {number} The count of non-label marks currently stored in the editor.
     */
    #shapeMarkCount() {
        return this.#marks.filter(mark => mark.type !== "label").length;
    }
    /**
     * Keep geometric mark numbers sequential without consuming LABEL entries.
     */
    #renumberShapeMarks() {
        let number = 0;
        for (const mark of this.#marks) {
            if (mark.type === "label")
                continue;
            number += 1;
            mark.label = String(number);
        }
    }
    /**
     * Find the topmost mark under a normalized pointer coordinate.
     * @param {number} x The horizontal coordinate of the interaction point.
     * @param {number} y The vertical coordinate of the interaction point.
     * @param {DOMRect} bounds The bounding rectangle of the editor used to calculate relative tolerance and scale.
     * @returns {number} The index of the matched mark within the internal marks collection, or -1 if no mark is found at the point.
     */
    #markIndexAtPoint(x, y, bounds) {
        const tolerance = 10 / Math.max(1, Math.min(bounds.width, bounds.height));
        for (let index = this.#marks.length - 1; index >= 0; index -= 1) {
            const mark = this.#marks[index];
            if (!mark)
                continue;
            if (mark.type === "label") {
                const width = Math.max(tolerance * 2, (mark.label.length * 10) / Math.max(1, bounds.width));
                const height = Math.max(tolerance * 2, 22 / Math.max(1, bounds.height));
                if (x >= mark.x - tolerance && x <= mark.x + width && y >= mark.y - tolerance && y <= mark.y + height) {
                    return index;
                }
                continue;
            }
            const minX = Math.min(mark.x, mark.x + mark.w) - tolerance;
            const maxX = Math.max(mark.x, mark.x + mark.w) + tolerance;
            const minY = Math.min(mark.y, mark.y + mark.h) - tolerance;
            const maxY = Math.max(mark.y, mark.y + mark.h) + tolerance;
            if (x >= minX && x <= maxX && y >= minY && y <= maxY)
                return index;
        }
        return -1;
    }
    /**
     * Paint the immutable image and every mark in natural-image coordinates.
     * @param {boolean} showSelection Determines whether the currently selected mark should be rendered with a shadow highlight.
     */
    #renderCanvas(showSelection = true) {
        const canvas = this.#canvas();
        if (!canvas || !this.#image)
            return;
        const context = canvas.getContext("2d");
        if (!context)
            return;
        const width = canvas.width;
        const height = canvas.height;
        const strokeWidth = Math.max(3, Math.min(width, height) * .004);
        const fontSize = Math.max(16, width * .016);
        context.clearRect(0, 0, width, height);
        context.drawImage(this.#image, 0, 0, width, height);
        this.#marks.forEach((mark, index) => {
            const x1 = mark.x * width;
            const y1 = mark.y * height;
            const x2 = (mark.x + mark.w) * width;
            const y2 = (mark.y + mark.h) * height;
            context.save();
            context.strokeStyle = mark.color || "#ff3b30";
            context.fillStyle = mark.color || "#ff3b30";
            context.lineWidth = strokeWidth;
            if (showSelection && index === this.#selectedMarkIndex) {
                context.shadowColor = "rgba(255, 255, 255, .95)";
                context.shadowBlur = strokeWidth * 2;
            }
            if (mark.type === "label") {
                context.font = `800 ${fontSize}px sans-serif`;
                context.textBaseline = "top";
                context.fillText(mark.label, x1, y1);
                context.restore();
                return;
            }
            if (mark.type === "arrow") {
                this.#drawArrow(context, x1, y1, x2, y2, width);
            }
            else if (mark.type === "path") {
                context.beginPath();
                (mark.points || []).forEach((item, pointIndex) => {
                    const pointX = item.x * width;
                    const pointY = item.y * height;
                    if (pointIndex === 0)
                        context.moveTo(pointX, pointY);
                    else
                        context.lineTo(pointX, pointY);
                });
                context.stroke();
            }
            else {
                context.strokeRect(x1, y1, mark.w * width, mark.h * height);
            }
            context.font = `800 ${fontSize}px sans-serif`;
            context.textBaseline = "bottom";
            context.textAlign = "right";
            context.fillText(mark.label || String(index + 1), x2 - strokeWidth * 2, y2 - strokeWidth * 2);
            context.restore();
        });
        this.#syncToolbar();
    }
    /**
     * Draw one arrow shaft and filled head.
     * @param {CanvasRenderingContext2D} context The 2D rendering context used for drawing operations.
     * @param {number} x1 The horizontal coordinate of the arrow's start point.
     * @param {number} y1 The vertical coordinate of the arrow's start point.
     * @param {number} x2 The horizontal coordinate of the arrow's tip.
     * @param {number} y2 The vertical coordinate of the arrow's tip.
     * @param {number} canvasWidth The total width of the canvas used to calculate the proportional size of the arrowhead.
     */
    #drawArrow(context, x1, y1, x2, y2, canvasWidth) {
        const angle = Math.atan2(y2 - y1, x2 - x1);
        const size = Math.max(14, canvasWidth * .015);
        context.beginPath();
        context.moveTo(x1, y1);
        context.lineTo(x2, y2);
        context.stroke();
        context.beginPath();
        context.moveTo(x2, y2);
        context.lineTo(x2 - size * Math.cos(angle - .45), y2 - size * Math.sin(angle - .45));
        context.lineTo(x2 - size * Math.cos(angle + .45), y2 - size * Math.sin(angle + .45));
        context.closePath();
        context.fill();
    }
    /**
     * Reflect selected mark state into toolbar controls.
     */
    #syncToolbar() {
        const selected = this.#marks[this.#selectedMarkIndex];
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
}
customElements.define(VisualReferenceEditor.selector, VisualReferenceEditor);

cache=(()=>{return { VisualReferenceEditor: VisualReferenceEditor };})();return cache;};})();
const __brainExplorerModule16=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * View-ready contracts owned by the main Backlog presentation feature.
 *
 * @module presentation/backlog/view_models/backlog-view-model
 */
/**
 * Closed status options rendered by the task filter menu.
 */
const BACKLOG_STATUS_FILTER_OPTIONS = [
    ["TODO", "Pending"],
    ["WORKING", "In progress"],
    ["DONE", "Completed"],
];
/**
 * Closed priority options rendered by the task filter menu.
 */
const BACKLOG_PRIORITY_FILTER_OPTIONS = [
    ["HIGH", "High"],
    ["MEDIUM", "Medium"],
    ["LOW", "Low"],
];

cache=(()=>{return { BACKLOG_STATUS_FILTER_OPTIONS: BACKLOG_STATUS_FILTER_OPTIONS, BACKLOG_PRIORITY_FILTER_OPTIONS: BACKLOG_PRIORITY_FILTER_OPTIONS };})();return cache;};})();
const __brainExplorerModule17=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Projects Backlog tasks into domain trees and filtered task collections.
 *
 * This module contains no DOM, API, or lifecycle behavior. Each projector instance
 * represents one immutable UI-filter snapshot supplied by the Backlog component.
 *
 * @module presentation/backlog/projectors/backlog-task-projector
 */
/**
 * Derives domain and filter projections from one Backlog state snapshot.
 */
class BacklogTaskProjector {
    /**
     * Immutable projection context supplied by the component.
     * @type {BacklogTaskProjectionInput}
     */
    #input;
    /**
     * Lower-cased, trimmed text filter reused by every task query.
     * @type {string}
     */
    #needle;
    /**
     * Create a projector for one component-state snapshot.
     *
     * @param {BacklogTaskProjectionInput} input Tasks, selection, and active filter sets used by all queries.
     */
    constructor(input) {
        this.#input = input;
        this.#needle = input.filter.trim().toLowerCase();
    }
    /**
     * @returns {BacklogPipTaskViewModel[]} Tasks owned by the selected domain or any of its descendants.
     */
    domainTasks() {
        const domain = this.#input.selectedDomain;
        return this.#input.tasks.filter(task => !domain || task.domain === domain || task.domain.startsWith(`${domain}.`));
    }
    /**
     * Return domain-scoped tasks satisfying text, status, and priority filters.
     *
     * @returns {BacklogPipTaskViewModel[]} New array in the same stable order as the endpoint response.
     */
    visibleTasks() {
        return this.domainTasks()
            .filter(task => !this.#needle
            || `${task.domain} ${task.title} ${task.description} ${task.id}`.toLowerCase().includes(this.#needle))
            .filter(task => this.matchesActiveFilters(task));
    }
    /**
     * @returns {number} Number of selected status and priority filter values.
     */
    activeFilterCount() {
        return this.#input.statusFilter.size + this.#input.priorityFilter.size;
    }
    /**
     * Build a hierarchy containing every unique task domain.
     *
     * @returns {BacklogDomainTreeNode} Synthetic root whose descendants represent dot-delimited segments.
     */
    buildTree() {
        const root = { label: "", path: "", children: new Map() };
        for (const domain of this.domains()) {
            const parts = domain.split(".").filter(Boolean);
            let current = root;
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                let child = current.children.get(part);
                if (!child) {
                    child = { label: part, path, children: new Map() };
                    current.children.set(part, child);
                }
                current = child;
            });
        }
        return root;
    }
    /**
     * @returns {string[]} Sorted unique non-empty task domain paths.
     */
    domains() {
        return [...new Set(this.#input.tasks.map(task => task.domain).filter(Boolean))].sort();
    }
    /**
     * Determine whether a domain node owns any task accepted by active closed filters.
     *
     * @param {BacklogDomainTreeNode} node Candidate domain-tree node.
     * @returns {boolean} True when the branch should remain in the filtered tree.
     */
    matchesNode(node) {
        return this.#input.tasks.some(task => (task.domain === node.path || task.domain.startsWith(`${node.path}.`))
            && this.matchesActiveFilters(task));
    }
    /**
     * Determine whether a task satisfies selected status and priority values.
     *
     * @param {BacklogPipTaskViewModel} task Candidate task from the Backlog endpoint.
     * @returns {boolean} True when both closed filter dimensions accept the task.
     */
    matchesActiveFilters(task) {
        const matchesStatus = !this.#input.statusFilter.size || this.#input.statusFilter.has(task.status);
        const matchesPriority = !this.#input.priorityFilter.size || this.#input.priorityFilter.has(task.priority);
        return matchesStatus && matchesPriority;
    }
    /**
     * Return every non-terminal ancestor of a dot-delimited domain.
     *
     * @param {string} domain Selected domain whose parent branches must be expanded.
     * @returns {string[]} Ancestor paths ordered from the root toward the immediate parent.
     */
    ancestorPaths(domain) {
        const parts = domain.split(".");
        return parts.slice(1).map((_part, index) => parts.slice(0, index + 1).join("."));
    }
}

cache=(()=>{return { BacklogTaskProjector: BacklogTaskProjector };})();return cache;};})();
const __brainExplorerModule18=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
/**
 * Renders Backlog task collections and dialog surfaces as inert HTML strings.
 *
 * Event binding and state mutation remain owned by the Backlog Web Component; this
 * module owns only deterministic markup composition from explicit typed inputs.
 *
 * @module presentation/backlog/renderers/backlog-layout-renderer
 */


/**
 * Render tasks grouped into direct and descendant-domain sections.
 *
 * @param {readonly BacklogPipTaskViewModel[]} tasks Domain-scoped tasks in endpoint order.
 * @param {string} selectedDomain Domain used to distinguish direct tasks and shorten subgroup labels.
 * @param {readonly string[]} tasksWithImages Task identifiers with a persisted visual reference.
 * @returns {string} Backlog task-list markup or an empty-state paragraph.
 */
function renderBacklogTaskList(tasks, selectedDomain, tasksWithImages) {
    if (!tasks.length)
        return `<p class="empty-state">No visible tasks in this domain.</p>`;
    const directTasks = [];
    const subgroupMap = new Map();
    for (const task of tasks) {
        if (task.domain === selectedDomain) {
            directTasks.push(task);
        }
        else {
            const group = subgroupMap.get(task.domain) ?? [];
            group.push(task);
            subgroupMap.set(task.domain, group);
        }
    }
    const sections = [];
    if (directTasks.length) {
        sections.push(`<div class="direct-tasks-section" style="margin-bottom: 12px; display: grid; gap: 8px;">
            ${directTasks.map(task => renderBacklogTask(task, tasksWithImages)).join("")}
        </div>`);
    }
    for (const domain of [...subgroupMap.keys()].sort()) {
        const group = subgroupMap.get(domain) ?? [];
        const relativeDomain = selectedDomain ? domain.slice(selectedDomain.length + 1) : domain;
        sections.push(`<details class="subdomain-group" open>
            <summary class="subdomain-group-header">
                ${icon("chevronRight")}<strong>${escapeHtml(relativeDomain)}</strong>
                <span class="subdomain-task-count">(${group.length} tasks)</span>
                <span class="subdomain-line-separator"></span>
            </summary>
            <div class="subdomain-group-content">
                ${group.map(task => renderBacklogTask(task, tasksWithImages)).join("")}
            </div>
        </details>`);
    }
    return sections.join("");
}
/**
 * Render the task composer, visual-reference editor, and image viewer dialogs.
 *
 * @returns {string} Static dialog markup whose controls are bound by the Backlog component.
 */
function renderBacklogDialogs() {
    return `
        <dialog id="backlog-modal" class="backlog-dialog" style="border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 0; width: 720px; height: 540px; max-width: 90vw; max-height: 90vh; box-shadow: var(--shadow); background: var(--surface); color: var(--text);">
            <form method="dialog" class="backlog-modal-form" data-role="modal-form" style="display: flex; flex-direction: column; height: 100%;">
                <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong data-role="modal-title" style="font-size: 16px; color: var(--text-strong);">Create task</strong>
                    <button type="button" class="icon-action close-modal-btn" data-action="close-modal" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
                </header>
                <div class="modal-body" style="padding: 18px; flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden;">
                    <input type="hidden" data-role="modal-task-id" value=""><input type="hidden" data-role="modal-domain" value="">
                    <div class="modal-toolbar" style="display: flex; gap: 10px; align-items: center; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
                        <input type="text" data-role="modal-title-input" placeholder="Task title" required style="flex: 1; min-height: 38px;">
                        <select data-role="modal-priority" style="width: 110px; min-height: 38px;">
                            <option value="HIGH">HIGH</option><option value="MEDIUM">MEDIUM</option><option value="LOW">LOW</option>
                        </select>
                        <button type="button" data-action="open-visual-reference" class="ghost-action compact-action" style="display: inline-flex; align-items: center; gap: 6px; padding: 0 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 13px; font-weight: bold; background: var(--surface-muted); color: var(--primary); height: 38px;">${icon("camera")} Visual Reference</button>
                    </div>
                    <div style="flex: 1; display: flex; min-height: 0; margin-top: 12px;">
                        <textarea data-role="modal-description" placeholder="Write task details and description here..." required style="flex: 1; border: 0; padding: 0; outline: none; background: transparent; font-family: inherit; font-size: 14px; line-height: 1.6; resize: none; overflow-y: auto; scrollbar-width: none; -ms-overflow-style: none;"></textarea>
                    </div>
                </div>
                <footer class="modal-footer" style="display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding: 14px 18px; border-top: 1px solid var(--border); background: var(--surface-strong);">
                    <button type="button" class="ghost-action" data-action="close-modal">Cancel</button>
                    <button type="submit" class="primary-action" data-role="modal-submit-btn">Create</button>
                </footer>
            </form>
        </dialog>
        <dialog id="visual-reference-modal" class="backlog-dialog visual-reference-dialog">
            <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                <strong style="font-size: 16px; color: var(--text-strong);">Visual Reference</strong>
                <button type="button" class="icon-action close-modal-btn" data-action="close-visual-reference" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
            </header>
            <div class="modal-body visual-reference-body"><div class="file-upload-zone visual-reference-upload" data-role="image-upload-zone">
                <span class="visual-reference-label">Attach image / screenshot (optional)</span>
                <input type="file" data-role="modal-image-file" accept="image/*" class="file-input" style="display: none;">
                <div class="image-preview-area" data-role="image-preview-area"><span class="upload-placeholder" style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px;">Click or drag an image here</span><brain-visual-reference-editor hidden></brain-visual-reference-editor></div>
            </div></div>
            <footer class="modal-footer visual-reference-footer"><button type="button" class="primary-action" data-action="close-visual-reference" style="min-width: 100px;">Listo</button></footer>
        </dialog>
        <dialog id="image-viewer-modal" class="backlog-dialog" style="border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 0; width: min(800px, 95vw); box-shadow: var(--shadow); background: var(--surface); color: var(--text);">
            <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);"><strong style="font-size: 16px; color: var(--text-strong);">Vista Ampliada</strong><button type="button" class="icon-action close-modal-btn" data-action="close-image-viewer" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button></header>
            <div class="modal-body" style="padding: 18px; display: grid; place-items: center; background: var(--bg);"><img data-role="viewer-img" src="" style="max-width: 100%; max-height: 70vh; object-fit: contain; border-radius: var(--radius);"></div>
        </dialog>`;
}
/**
 * Render one task row, its state actions, and optional visual-reference thumbnail.
 *
 * @param {BacklogPipTaskViewModel} task View-ready task to render.
 * @param {readonly string[]} tasksWithImages Task identifiers with persisted reference images.
 * @returns {string} Inert task-row markup.
 */
function renderBacklogTask(task, tasksWithImages) {
    const status = task.status || "TODO";
    const workingIcon = `<div class="working-spinner" title="In progress">${["blue", "cyan", "green", "yellow", "red", "pink"].map(color => `<span class="dot dot-${color}"></span>`).join("")}</div>`;
    const statusIcon = status === "DONE" ? icon("checkSquare") : status === "WORKING" ? workingIcon : icon("clock");
    const statusClass = status === "DONE" ? "task-status-done"
        : status === "WORKING" ? "task-status-working"
            : `task-status-${task.priority.toLowerCase()}`;
    const startSpinner = `<span style="display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; margin-right: 8px; flex-shrink: 0;"><span class="working-spinner" style="transform: scale(0.85); width: 14px; height: 14px; margin: 0; display: inline-block; position: relative;">${["blue", "cyan", "green", "yellow", "red", "pink"].map(color => `<span class="dot dot-${color}" style="width: 3px; height: 3px;"></span>`).join("")}</span></span>`;
    const buttons = status === "DONE"
        ? `<button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="TODO">${icon("clock")}Reopen</button>`
        : status === "TODO"
            ? `<button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="WORKING">${startSpinner}Iniciar trabajo</button><button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="DONE">${icon("checkSquare")}Mark done</button>`
            : `<button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="DONE">${icon("checkSquare")}Mark done</button><button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="TODO">${icon("clock")}Pause (TODO)</button>`;
    const imageTaskId = task.id.replace(/^#/, "");
    const thumbnail = tasksWithImages.includes(imageTaskId)
        ? `<button class="task-image-thumbnail" type="button" data-action="view-image" data-task-id="${escapeHtml(imageTaskId)}" title="View reference image"><img src="/api/backlog/image?taskId=${escapeHtml(imageTaskId)}" alt="Visual reference for ${escapeHtml(task.title)}"></button>`
        : "";
    return `<article class="task-row ${status === "DONE" ? "is-done" : ""}" data-task-row-id="${escapeHtml(task.id)}">
        <span class="task-status ${statusClass}">${statusIcon}</span><div style="flex: 1; min-width: 0;"><strong>${escapeHtml(task.id)} - ${escapeHtml(task.title)}</strong><p>${escapeHtml(task.description)}</p></div>
        <div class="task-actions" style="display: inline-flex; align-items: center; gap: 8px; justify-self: end;">${thumbnail}<details class="action-menu"><summary class="icon-action borderless-summary" title="Opciones">${icon("more")}</summary><div class="action-menu-panel"><button data-action="edit-task" data-task-id="${escapeHtml(task.id)}">${icon("edit")}Edit</button>${buttons}<button data-action="delete-task" data-task-id="${escapeHtml(task.id)}" data-task-status="${status}" class="danger-button">${icon("trash")}Delete task</button></div></details></div>
    </article>`;
}

cache=(()=>{return { renderBacklogTaskList: renderBacklogTaskList, renderBacklogDialogs: renderBacklogDialogs };})();return cache;};})();
const __brainExplorerModule19=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
const { isRouteId } = __brainExplorerModule20();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */



/**
 * DashboardView renders the `get-context --json` items as the Explorer entry point.
 */
class DashboardView extends HTMLElement {
    /**
     * Registered Custom Element tag used by the shell route registry.
     * @returns {string} A string representing the component's DOM selector.
     */
    static get selector() {
        return "brain-dashboard-view";
    }
    /**
     * Injected Explorer HTTP adapter, or `null` before context assignment.
     * @type {BrainApiClient | null}
     */
    #api = null;
    /**
     * Injected shell state store, or `null` before context assignment.
     * @type {AppState | null}
     */
    #state = null;
    /**
     * Ordered live context sections returned by the Dashboard endpoint.
     * @type {ContextSection[]}
     */
    #contextSections = [];
    /**
     * Whether the initial or forced context request is in progress.
     * @type {boolean}
     */
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
        const routeValue = button.getAttribute("data-context-route");
        const route = isRouteId(routeValue) ? routeValue : "dashboard";
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
                    <p>Refresh to read the live workspace context.</p>
                </div>
            `;
        }
        const entryCount = this.#contextSections.reduce((total, section) => total + Math.max(1, Array.isArray(section.items) ? section.items.length : 0), 0);
        return `
            <article class="context-document-root context-outline">
                <div class="context-document-actions">
                    <span>${escapeHtml(String(entryCount))} enlaces</span>
                    <button data-action="refresh-dashboard" class="icon-action compact-action" title="Refresh context" aria-label="Refresh context">${icon("refresh")}</button>
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
        const entries = items.length
            ? items.map(item => this.#itemEntry(section, item))
            : [this.#sectionEntry(section)].filter((entry) => entry !== null);
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
                <nav class="context-log-links" aria-label="Recent log entries">
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
                <nav class="context-profile-links" aria-label="Available profiles">
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
                label: "Workspace root",
                summary: section.path || section.summary || "",
                route: "settings",
                target: { panel: "workspace" }
            };
        }
        if (section.kind === "system") {
            return {
                kind: "system",
                icon: "pulse",
                typeLabel: "System",
                label: section.status === "ok" ? "Checks passed" : "Checks with errors",
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
        }[section.kind ?? ""] || "document";
        return {
            kind: section.kind || "item",
            icon: iconName,
            typeLabel: this.#typeLabel(section, item),
            label: this.#itemLabel(section, item),
            summary: this.#itemSummary(section, item),
            title: item.label || item.id || section.title || "Contexto",
            ...((item.route || section.route) ? { route: item.route || section.route } : {}),
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
            return "Log entry";
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
            return item.target?.path || item.command || "Diary entry";
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
        }[section.kind ?? ""] || "document";
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
            profiles: "Profiles",
            diary: "Diario reciente",
            logs: "Logs recientes",
            system: "System",
            notice: "Avisos"
        }[section.kind ?? ""] || "Contexto";
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
            return section.path || "Workspace root";
        }
        return `${count} linked entries`;
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
const __brainExplorerModule20=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Runtime narrowing for route identifiers crossing outer-layer boundaries.
 *
 * @module application/shell/validators/route-id
 */
/**
 * Complete closed route vocabulary accepted by Explorer navigation state.
 */
const ROUTE_IDS = [
    "dashboard", "memory", "knowledge", "pictures", "query", "profiles",
    "logs", "backlog", "messages", "wikis", "settings",
];
/**
 * Narrow an untrusted DOM or API string to the application route contract.
 *
 * This validator deliberately lives in Application rather than the shell route
 * registry so feature layouts can validate navigation without importing the
 * Presentation composition root and creating a circular module dependency.
 *
 * @param {string | null} value Untrusted route identifier read at an outer-layer boundary.
 * @returns {boolean} `true` only when `value` belongs to the complete route vocabulary.
 */
function isRouteId(value) {
    return value !== null && ROUTE_IDS.some(route => route === value);
}

cache=(()=>{return { isRouteId: isRouteId };})();return cache;};})();
const __brainExplorerModule21=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
const { StructureTree } = __brainExplorerModule9();
const { KnowledgeGraphNormalizer } = __brainExplorerModule22();
const { KnowledgeSourceTreeProjector } = __brainExplorerModule24();
const { KnowledgeInspectorRenderer } = __brainExplorerModule26();
const { KnowledgeGraphLayoutEngine } = __brainExplorerModule28();
const { knowledgeNodeId } = __brainExplorerModule25();
const { KnowledgeTreeInteractionController } = __brainExplorerModule29();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */









void StructureTree;
/**
 * KnowledgeView renders a canvas-based explorer for graph records returned by the CLI facade.
 * Entities/classes become draggable nodes. Relations become selectable edges.
 */
class KnowledgeView extends KnowledgeTreeInteractionController {
    /**
     * Projects persistence-backed source records into the shared navigation tree.
     * @type {KnowledgeSourceTreeProjector}
     */
    sourceTreeProjector = new KnowledgeSourceTreeProjector();
    /**
     * Renders inspector markup while this layout owns selection and navigation.
     * @type {KnowledgeInspectorRenderer}
     */
    inspectorRenderer = new KnowledgeInspectorRenderer();
    /**
     * Positions graph nodes without owning view lifecycle or rendering.
     * @type {KnowledgeGraphLayoutEngine}
     */
    graphLayout = new KnowledgeGraphLayoutEngine();
    /**
     * Canonical custom-element selector registered by the application bootstrap.
     * @returns {string} The string identifier 'brain-knowledge-view'.
     */
    static get selector() {
        return "brain-knowledge-view";
    }
    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.api = context.api;
        this.state = context.state;
        const target = this.state?.consumeRouteTarget?.("knowledge") || null;
        this.pendingEntityLabel = String(target?.entityLabel || "").trim();
        this.render();
        this.scheduleInitialLoad();
        if (this.output)
            queueMicrotask(() => this.resolvePendingEntity());
    }
    /**
     * Initialize component DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.render();
        this.scheduleInitialLoad();
    }
    /**
     * Disconnect canvas observers.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        this.resizeObserver?.disconnect();
        cancelAnimationFrame(this.cameraAnimationFrame);
        clearTimeout(this.viewportInspectorTimer);
    }
    /**
     * Load records once after the component has context.
     *
     * @returns {void}
     * @param {unknown} data The data value used by this operation.
     */
    ingestGraph(data) {
        const graph = this.collectGraph(data);
        this.records = graph.records;
        this.relations = graph.relations;
        if (this.domain !== "all" && !this.domains().some(domain => domain === this.domain || domain.startsWith(`${this.domain}.`))) {
            this.domain = "all";
        }
        this.selectedNodeId = "";
        this.selectedRelationId = "";
        this.regionNodeIds.clear();
        this.regionEdgeIds.clear();
        this.regionPositions.clear();
        this.regionHistory = [];
        this.regionRootNodeId = "";
        this.needsViewportFit = true;
        this.prepareGraph();
    }
    /**
     * Read form controls into component state.
     *
     * @returns {void}
     */
    readControls() {
        const scopes = Array.from(this.querySelectorAll("[data-filter-kind='kg-scope']:checked"))
            .map(input => input.value)
            .filter((scope) => scope === "global" || scope === "local");
        this.selectedScopes = new Set(scopes);
        this.scope = scopes.length === 1 ? (scopes[0] ?? "all") : "all";
        const selectedModes = Array.from(this.querySelectorAll("[data-filter-kind='kg-mode']:checked"))
            .map(input => input.value)
            .filter((mode) => mode === "entities" || mode === "classes");
        this.mode = selectedModes.length === 1 ? (selectedModes[0] ?? "all") : "all";
        this.query = this.querySelector("[data-role='kg-query']")?.value.trim() || "";
    }
    /**
     * Render view markup.
     *
     * @returns {void}
     */
    render() {
        this.innerHTML = `
            <section class="page-surface knowledge-console">
                <div class="structure-layout knowledge-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.renderDomainTree()}
                        </div>
                    </aside>
                    <main class="structure-content knowledge-content">
                        <div class="content-head graph-toolbar">
                            <input class="graph-search-input" aria-label="Search graph" data-role="kg-query" value="${escapeHtml(this.query)}" placeholder="Filter or search graph">
                            <details class="action-menu filter-menu knowledge-filter-menu" ${this.filtersOpen ? "open" : ""}>
                                <summary class="compact-action">${icon("filter")}<span>Filters</span></summary>
                                <div class="action-menu-panel filter-menu-panel">
                                    <fieldset class="checkbox-filter-group knowledge-scope-filter">
                                        <legend>Scope</legend>
                                        <div class="knowledge-filter-options">
                                            <label><input type="checkbox" data-filter-kind="kg-scope" value="global" ${this.selectedScopes.has("global") ? "checked" : ""}><span>Global</span></label>
                                            <label><input type="checkbox" data-filter-kind="kg-scope" value="local" ${this.selectedScopes.has("local") ? "checked" : ""}><span>Local</span></label>
                                        </div>
                                    </fieldset>
                                    <fieldset class="checkbox-filter-group">
                                        <legend>Visible content</legend>
                                        <div class="knowledge-filter-options">
                                            <label><input type="checkbox" data-filter-kind="kg-mode" value="entities" ${this.mode === "all" || this.mode === "entities" ? "checked" : ""}><span>Entities</span></label>
                                            <label><input type="checkbox" data-filter-kind="kg-mode" value="classes" ${this.mode === "all" || this.mode === "classes" ? "checked" : ""}><span>Classes</span></label>
                                        </div>
                                    </fieldset>
                                </div>
                            </details>
                            <button data-action="query-records" class="primary-action">${icon("search")}Search</button>
                        </div>
                        <div class="knowledge-canvas-layout">
                            <main class="graph-viewport">
                                <button class="graph-focus-back secondary-action compact-action" data-action="navigate-region-back" ${this.regionHistory.length ? "" : "hidden"}>
                                    ${icon("chevronLeft")} Back
                                </button>
                                <canvas class="knowledge-graph-canvas" data-role="knowledge-canvas" aria-label="Knowledge graph"></canvas>
                                ${this.renderGraphBusyState()}
                                <div data-role="relation-preview-host">
                                    ${this.renderRelationPreview()}
                                </div>
                                ${this.renderCanvasEmptyState()}
                            </main>
                            <aside class="graph-detail-list">
                                ${this.renderDetails()}
                            </aside>
                        </div>
                    </main>
                </div>
            </section>
        `;
        this.bindEvents();
        this.configureDomainTree();
        this.bindCanvas();
    }
    /**
     * Render an empty overlay only when there are no visible nodes.
     *
     * @returns {string} HTML.
     */
    renderCanvasEmptyState() {
        if (this.nodes.length || this.records.length || this.relations.length) {
            return "";
        }
        return `
            <div class="knowledge-empty-state canvas-empty">
                ${icon("graph")}
                <h2>${this.output?.ok === false ? "Query failed" : "Loading graph"}</h2>
                <p>${escapeHtml(this.output?.error || this.output?.stderr || "Nodes will appear here.")}</p>
            </div>
        `;
    }
    /**
     * Render the bounded operation status overlay for the canvas.
     * @returns {string} An HTML string representing the graph busy state overlay.
     */
    renderGraphBusyState() {
        return `
            <div class="graph-busy-overlay" data-role="graph-busy-overlay" role="status" aria-live="polite" ${this.graphBusyDepth ? "" : "hidden"}>
                <span class="graph-busy-spinner" aria-hidden="true"></span>
                <strong data-role="graph-busy-label">${escapeHtml(this.graphBusyLabel)}</strong>
            </div>
        `;
    }
    /**
     * Begin one graph operation and expose its latest user-facing status.      * @param {string} label The label value used by this operation.
     */
    beginGraphBusy(label) {
        this.graphBusyDepth += 1;
        this.graphBusyLabel = String(label || "Loading graph");
        this.syncGraphBusyState();
    }
    /**
     * Finish one graph operation without hiding another overlapping operation.
     */
    endGraphBusy() {
        this.graphBusyDepth = Math.max(0, this.graphBusyDepth - 1);
        this.syncGraphBusyState();
    }
    /**
     * Synchronize busy state without rebuilding the Knowledge component.
     */
    syncGraphBusyState() {
        const overlay = this.querySelector("[data-role='graph-busy-overlay']");
        const viewport = this.querySelector(".graph-viewport");
        if (overlay) {
            overlay.hidden = this.graphBusyDepth === 0;
            const label = overlay.querySelector("[data-role='graph-busy-label']");
            if (label) {
                label.textContent = this.graphBusyLabel;
            }
        }
        viewport?.setAttribute("aria-busy", String(this.graphBusyDepth > 0));
    }
    /**
     * Yield one paint frame so synchronous graph projection can expose the spinner.
     * @returns {Promise<void>} A promise that resolves once the requestAnimationFrame callback is executed.
     */
    waitForGraphPaint() {
        return new Promise(resolve => requestAnimationFrame(() => resolve()));
    }
    /**
     * Render the complete subject-predicate-object preview for the selected relation.
     * @returns {string} An HTML section containing the relation's predicate and endpoint buttons, or an empty string if no relation is active.
     */
    renderRelationPreview() {
        const relationId = this.hoveredRelationId || this.selectedRelationId;
        const relation = this.edges.find(edge => edge.id === relationId);
        if (!relation) {
            return "";
        }
        const source = this.nodes.find(node => node.id === relation.from);
        const target = this.nodes.find(node => node.id === relation.to);
        return `
            <section class="graph-relation-preview" role="status" aria-label="Focused relation preview">
                <button class="graph-relation-endpoint" data-action="navigate-relation-endpoint" data-node-id="${escapeHtml(relation.from)}" style="--entity-color: ${escapeHtml(source?.color || "var(--primary)")}">
                    ${escapeHtml(relation.fromLabel)}
                </button>
                <span class="graph-relation-connector">
                    <strong class="graph-relation-predicate" title="${escapeHtml(relation.label)}">${escapeHtml(relation.label)}</strong>
                </span>
                <button class="graph-relation-endpoint" data-action="navigate-relation-endpoint" data-node-id="${escapeHtml(relation.to)}" style="--entity-color: ${escapeHtml(target?.color || "var(--primary)")}">
                    ${escapeHtml(relation.toLabel)}
                </button>
            </section>
        `;
    }
    /**
     * Render the domain tree used to scope the graph.
     *
     * @returns {string} HTML.
     */
    renderDomainTree() {
        this.domainTreeNodes = this.sourceTreeProjector.project({
            selectedScopes: this.selectedScopes,
            memoryPaths: this.memoryPaths,
            pictures: this.pictures,
            messages: this.messages,
            messageSessions: this.messageSessions,
            logEntries: this.logEntries,
            graphCountLabel: (domain, scope, sourceKind = "", sourcePath = "", visualType = "") => (this.graphCountLabel(domain, scope, sourceKind, sourcePath, visualType)),
            domainColor: domain => this.domainColor(domain),
        });
        return `<brain-structure-tree data-role="knowledge-domain-tree"></brain-structure-tree>`;
    }
    /**
     * Render inspector markup through the dedicated stateless renderer.
     * @returns {string} An HTML string representing the rendered inspector details.
     */
    renderDetails() {
        const proxiedInspector = this.inspectorRenderer.render({
            nodes: this.nodes,
            edges: this.edges,
            selectedNodeId: this.selectedNodeId,
            selectedRelationId: this.selectedRelationId,
            importantNodes: this.importantNodes(),
            pictureForNode: node => this.pictureForNode(node),
            messageForNode: node => this.messageForNode(node),
            isPictureTagNode: node => this.isPictureTagNode(node),
            pictureUrl: pictureId => this.api?.pictureUrl(pictureId) || "",
        });
        return proxiedInspector;
    }
    /**
     * Resolve an image registry record from one graph source reference.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     *
     * @returns {PictureRecord | null} The matching PictureRecord if found and the node is not a picture tag, otherwise null.
     */
    pictureForNode(node) {
        if (this.isPictureTagNode(node))
            return null;
        const source = String(node.source || "").replaceAll("\\", "/").toLowerCase();
        const pictureId = String(node.raw?.picture_id || "");
        return this.pictures.find(picture => pictureId === String(picture.id)
            || source.endsWith(String(picture.relative_path || "").replaceAll("\\", "/").toLowerCase())) || null;
    }
    /**
     * Return whether a semantic image-analysis tag is being inspected, not its picture source.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     *
     * @returns {boolean} True if the node's class hint matches 'misc.tag' after normalization, otherwise false.
     */
    isPictureTagNode(node) {
        return String(node.classHint || "").trim().toLowerCase() === "misc.tag";
    }
    /**
     * Resolve a persisted message body from one graph source reference.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     *
     * @returns {AvatarMessageRecord | null} The matching AvatarMessageRecord if found, otherwise null.
     */
    messageForNode(node) {
        const source = String(node.source || "");
        return this.messages.find(message => source.includes(String(message.id))) || null;
    }
    /**
     * Return highest-connectivity entities in the currently visible graph or region.
     * @returns {KnowledgeRankedNode[]} An array of KnowledgeRankedNode objects sorted by their importance rank.
     */
    importantNodes() {
        const focus = this.focusGraph();
        const logicalCandidates = focus
            ? this.nodes.filter(node => focus.nodeIds.has(node.id))
            : this.nodes;
        const candidates = this.viewportBadgeSignature
            ? logicalCandidates.filter(node => this.viewportNodeIds.has(node.id))
            : logicalCandidates;
        return this.rankImportantNodes(candidates);
    }
    /**
     * Rank one explicit visible-node set by its internal connectivity.      * @param {KnowledgeGraphNode[]} candidates The candidates value used by this operation.
     *
     * @returns {KnowledgeRankedNode[]} A sorted list of up to 12 nodes augmented with their respective connection degrees.
     */
    rankImportantNodes(candidates) {
        const visibleIds = new Set(candidates.map(node => node.id));
        const degrees = this.nodeDegrees({ nodeIds: visibleIds, edgeIds: new Set() });
        return candidates
            .filter(node => node.visualType !== "class")
            .map(node => ({ ...node, degree: degrees.get(node.id) || 0 }))
            .sort((left, right) => right.degree - left.degree || left.label.localeCompare(right.label))
            .slice(0, 12);
    }
    /**
     * Convert command data to normalized graph records.
     *
     * @param {unknown} data Command data.
     * @returns {{records: object[], relations: object[]}} Graph data.
     */
    collectGraph(data) {
        return new KnowledgeGraphNormalizer({
            mode: this.mode,
            scope: this.scope,
            nodeId: knowledgeNodeId,
        }).collect(data);
    }
    /**
     * Prepare graph nodes and edges from current records and filters.
     *
     * @returns {void}
     */
    prepareGraph() {
        const records = this.mergeScopeRecords(this.filteredRecords());
        const domainGroups = new Map();
        records.forEach(record => {
            if (!domainGroups.has(record.domain)) {
                domainGroups.set(record.domain, []);
            }
            domainGroups.get(record.domain)?.push(record);
        });
        const domains = Array.from(domainGroups.keys()).sort();
        this.nodes = records.map(record => this.nodeFromRecord(record, domains, domainGroups));
        this.edges = this.edgesFromRelations(records);
        this.viewportNodeIds.clear();
        this.viewportBadgeSignature = "";
        this.applyConnectivitySizing();
        this.graphLayout.layout(this.nodes, this.edges);
        this.reconcileRegionEdges();
    }
    /**
     * Merge same-name identities across scopes so their relations share one visible node.      * @param {KnowledgeRecord[]} records The records value used by this operation.
     *
     * @returns {MergedKnowledgeRecord[]} An array of merged knowledge records where duplicates are consolidated into single entries with aggregated metadata.
     */
    mergeScopeRecords(records) {
        const merged = new Map();
        records.forEach(record => {
            const key = `${record.visualType}:${record.label.toLowerCase()}`;
            const current = merged.get(key);
            if (!current) {
                merged.set(key, {
                    ...record,
                    aliases: [record.id],
                    knowledgeScopes: [record.knowledgeScope],
                    sources: [record.source]
                });
                return;
            }
            current.aliases.push(record.id);
            if (!current.knowledgeScopes.includes(record.knowledgeScope))
                current.knowledgeScopes.push(record.knowledgeScope);
            if (!current.sources.includes(record.source))
                current.sources.push(record.source);
            current.knowledgeScope = current.knowledgeScopes.length > 1 ? "all" : (current.knowledgeScopes[0] ?? "global");
            current.source = current.sources.filter(Boolean).join(" · ");
            if (record.description.length > current.description.length)
                current.description = record.description;
        });
        return [...merged.values()];
    }
    /**
     * Convert one record into a graph node.
     *
     * @param {object} record Graph record.
     * @param {string[]} domains Domain list.
     * @param {Map<string, object[]>} domainGroups Grouped records.
     * @returns {object} Graph node.
     */
    nodeFromRecord(record, domains, domainGroups) {
        const domainIndex = Math.max(domains.indexOf(record.domain), 0);
        const group = domainGroups.get(record.domain) || [];
        const localIndex = Math.max(group.findIndex(item => item.id === record.id), 0);
        const domainAngle = (Math.PI * 2 * domainIndex) / Math.max(domains.length, 1);
        const localAngle = domainAngle + (localIndex / Math.max(group.length, 1)) * 0.96;
        const radius = 130 + (localIndex % 11) * 24 + domainIndex * 10;
        const baseRadius = this.mode === "classes" ? 15 : 11;
        return {
            ...record,
            x: Math.cos(localAngle) * radius,
            y: Math.sin(localAngle) * radius,
            radius: baseRadius,
            baseRadius,
            color: this.domainColor(record.domain)
        };
    }
    /**
     * Return a stable color that is never reused by another domain or superdomain.      * @param {string} domain The domain value used by this operation.
     *
     * @returns {string} A unique HSL color string associated with the provided domain.
     */
    domainColor(domain) {
        const normalized = String(domain || "knowledge").toLowerCase();
        const existing = this.domainColors.get(normalized);
        if (existing) {
            return existing;
        }
        const hash = [...normalized].reduce((total, character) => ((total * 31) + character.charCodeAt(0)) >>> 0, 0);
        let offset = 0;
        let color = "";
        do {
            const hue = ((hash % 3600) / 10 + offset * 137.508) % 360;
            const saturation = 68 + ((hash + offset * 7) % 17);
            const lightness = 52 + ((hash + offset * 11) % 25);
            color = `hsl(${hue.toFixed(1)} ${saturation}% ${lightness}%)`;
            offset += 1;
        } while (this.usedDomainColors.has(color));
        this.domainColors.set(normalized, color);
        this.usedDomainColors.add(color);
        return color;
    }
    /**
     * Build edges from relation data returned by the CLI facade.
     *
     * @param {object[]} records Current node records.
     * @returns {object[]} Edges.
     * @param {KnowledgeRelation[] | null} relations The relations value used by this operation.
     */
    edgesFromRelations(records, relations = null) {
        const nodeById = new Map();
        records.forEach(record => {
            nodeById.set(record.id, record);
            (record.aliases || []).forEach(alias => nodeById.set(alias, record));
        });
        const nodeByLabel = new Map(records.map(record => [`${record.domain}:${record.label}`.toLowerCase(), record]));
        const domainRelations = relations || this.relations.filter(relation => this.recordMatchesTree(relation));
        const edges = domainRelations
            .map((relation, index) => {
            const from = this.nodeForRelationEnd(nodeById, nodeByLabel, relation, "from");
            const to = this.nodeForRelationEnd(nodeById, nodeByLabel, relation, "to");
            if (!from || !to) {
                return null;
            }
            return {
                ...relation,
                id: relation.id || `relation-edge-${index}`,
                from: from.id,
                to: to.id,
                color: this.domainColor(relation.domain),
            };
        })
            .filter((edge) => edge !== null);
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
    nodeForRelationEnd(nodeById, nodeByLabel, relation, side) {
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
    filteredRecords() {
        const needle = this.query.toLowerCase();
        const visualType = this.treeVisualType || (this.mode === "classes" ? "class" : this.mode === "entities" ? "entity" : "");
        const projection = this.treeProjection(this.domain, this.treeScope, this.sourceKind, this.sourcePath, this.treeVisualType);
        return projection.records
            .filter(record => (record.knowledgeScope === "global" || record.knowledgeScope === "local")
            && this.selectedScopes.has(record.knowledgeScope))
            .filter(record => !visualType || record.visualType === visualType)
            .filter(record => !needle || `${record.label} ${record.description} ${record.domain} ${record.context}`.toLowerCase().includes(needle));
    }
    /**
     * Return whether a domain is active under the selected tree node.
     *
     * @param {string} domain Domain path.
     * @returns {boolean} True when visible.
     * @param {KnowledgeRecord | KnowledgeRelation} record The record value used by this operation.
     */
    recordMatchesTree(record) {
        if ((record.knowledgeScope !== "global" && record.knowledgeScope !== "local")
            || !this.selectedScopes.has(record.knowledgeScope)) {
            return false;
        }
        return this.recordMatchesTreeSelection(record, this.domain, this.treeScope, this.sourceKind, this.sourcePath, this.treeVisualType);
    }
    /**
     * Apply one explicit inclusive tree selection without depending on current UI state.      * @param {KnowledgeRecord | KnowledgeRelation} record The record value used by this operation.
     * @param {string} domain The domain value used by this operation.
     * @param {"" | KnowledgeScope} scope The scope value used by this operation.
     * @param {"" | KnowledgeSourceKind} sourceKind The source kind value used by this operation.
     * @param {string} sourcePath The source path value used by this operation.
     * @param {"" | KnowledgeVisualType} visualType The visual type value used by this operation.
     *
     * @returns {boolean} True if the record satisfies all provided filter constraints; otherwise, false.
     */
    recordMatchesTreeSelection(record, domain, scope = "", sourceKind = "", sourcePath = "", visualType = "") {
        if (scope && scope !== "all" && record.knowledgeScope !== scope)
            return false;
        if (visualType && "visualType" in record && record.visualType && record.visualType !== visualType)
            return false;
        if (sourceKind && !this.recordMatchesSourceKind(record, sourceKind, scope))
            return false;
        const selectedSource = String(sourcePath || "").replaceAll("\\", "/").toLowerCase();
        if (selectedSource) {
            const source = String(record.source || "").replaceAll("\\", "/").toLowerCase();
            if (!source.includes(selectedSource) && !selectedSource.includes(source))
                return false;
        }
        return domain === "all" || record.domain === domain || record.domain.startsWith(`${domain}.`);
    }
    /**
     * Classify one graph record into mutually exclusive canonical source families.      * @param {KnowledgeRecord | KnowledgeRelation} record The record value used by this operation.
     * @param {KnowledgeSourceKind} sourceKind The source kind value used by this operation.
     * @param {"" | KnowledgeScope} scope The scope value used by this operation.
     *
     * @returns {boolean} A boolean indicating whether the record's properties satisfy the criteria for the given source kind and scope.
     */
    recordMatchesSourceKind(record, sourceKind, scope = "") {
        const source = String(record.source || "").replaceAll("\\", "/").toLowerCase();
        const domain = String(record.domain || "").toLowerCase();
        const isPicture = domain === "pictures" || domain.startsWith("pictures.")
            || this.pictures.some(picture => source.endsWith(String(picture.relative_path || "").replaceAll("\\", "/").toLowerCase()));
        const isMessage = domain === "messages" || domain.startsWith("messages.") || source.includes("message");
        const isLog = domain === "logs" || domain.startsWith("logs.") || source.includes("/logs/");
        if (sourceKind === "pictures")
            return isPicture;
        if (sourceKind === "messages")
            return isMessage;
        if (sourceKind === "logs")
            return isLog;
        if (sourceKind === "memory") {
            return scope === "global" ? !isPicture : !isLog && !isMessage && !isPicture;
        }
        return true;
    }
    /**
     * Return available domains from loaded records and relations.
     *
     * @returns {string[]} Domain labels.
     * @param {"" | KnowledgeScope} scope The scope value used by this operation.
     */
    domains(scope = "") {
        return [...new Set([
                ...this.records.filter(record => !scope || record.knowledgeScope === scope).map(record => record.domain),
                ...this.relations.filter(relation => !scope || relation.knowledgeScope === scope).map(relation => relation.domain)
            ].filter(Boolean))].sort();
    }
    /**
     * Return visible entity/relation counts using the canvas' exact projection rules.      * @param {string} domain The domain value used by this operation.
     * @param {"" | KnowledgeScope} scope The scope value used by this operation.
     * @param {"" | KnowledgeSourceKind} sourceKind The source kind value used by this operation.
     * @param {string} sourcePath The source path value used by this operation.
     * @param {"" | KnowledgeVisualType} visualType The visual type value used by this operation.
     *
     * @returns {string} A string representing the count of entities (E) and relations (R) in the format 'E: [count] R: [count]'.
     */
    graphCountLabel(domain, scope = "", sourceKind = "", sourcePath = "", visualType = "") {
        const projection = this.treeProjection(domain, scope, sourceKind, sourcePath, visualType);
        const records = this.mergeScopeRecords(projection.records);
        const relations = projection.relations;
        const edges = this.edgesFromRelations(records, relations);
        return `E: ${records.length} R: ${edges.length}`;
    }
    /**
     * Include relation endpoints in virtual source projections without changing their canonical ownership.      * @param {string} domain The domain value used by this operation.
     * @param {"" | KnowledgeScope} scope The scope value used by this operation.
     * @param {"" | KnowledgeSourceKind} sourceKind The source kind value used by this operation.
     * @param {string} sourcePath The source path value used by this operation.
     * @param {"" | KnowledgeVisualType} visualType The visual type value used by this operation.
     *
     * @returns {KnowledgeTreeProjection} An object containing the filtered and expanded collections of records and relations.
     */
    treeProjection(domain, scope = "", sourceKind = "", sourcePath = "", visualType = "") {
        const matches = (record) => this.recordMatchesTreeSelection(record, domain, scope, sourceKind, sourcePath, visualType);
        const relations = this.relations.filter(matches);
        const records = this.records.filter(matches);
        if (!sourceKind && !sourcePath)
            return { records, relations };
        const endpointIds = new Set(relations.flatMap(relation => [String(relation.from), String(relation.to)]));
        const endpointLabels = new Set(relations.flatMap(relation => [
            String(relation.fromLabel || "").toLowerCase(),
            String(relation.toLabel || "").toLowerCase()
        ]));
        const includedIds = new Set(records.map(record => String(record.id)));
        this.records.forEach(record => {
            if (scope && scope !== "all" && record.knowledgeScope !== scope)
                return;
            if (visualType && record.visualType !== visualType)
                return;
            const connected = endpointIds.has(String(record.id))
                || endpointIds.has(String(record.entityId))
                || endpointLabels.has(String(record.label || "").toLowerCase());
            if (connected && !includedIds.has(String(record.id))) {
                records.push(record);
                includedIds.add(String(record.id));
            }
        });
        return { records, relations };
    }
    /**
     * Apply local reactive filters without a new CLI call.
     *
     * @returns {void}
     */
    async applyFilters() {
        this.beginGraphBusy("Filtering graph");
        await this.waitForGraphPaint();
        try {
            this.readControls();
            if (this.treeScope !== "all" && !this.selectedScopes.has(this.treeScope)) {
                this.selectedTreePath = "";
                this.treeScope = "all";
                this.domain = "all";
                this.sourceKind = "";
                this.sourcePath = "";
                this.treeVisualType = "";
            }
            this.needsViewportFit = true;
            this.prepareGraph();
            this.render();
        }
        finally {
            this.endGraphBusy();
        }
    }
    /**
     * Apply one tree selection without rebuilding the complete Explorer surface.
     */
    async applyTreeSelection() {
        this.beginGraphBusy("Focusing graph source");
        await this.waitForGraphPaint();
        try {
            this.resetGraphRegion();
            this.needsViewportFit = true;
            this.prepareGraph();
            this.syncDomainTreeSelection();
            this.drawCanvas();
            this.renderInspector();
        }
        finally {
            this.endGraphBusy();
        }
    }
    /**
     * Update selected tree-row styling while preserving expansion and scroll state.
     */
    syncDomainTreeSelection() {
        const tree = this.querySelector("[data-role='knowledge-domain-tree']");
        tree?.querySelectorAll("[data-tree-path]").forEach(button => {
            const selected = button.getAttribute("data-tree-path") === this.selectedTreePath;
            button.classList.toggle("is-active", selected);
            button.closest("[role='treeitem']")?.setAttribute("aria-selected", String(selected));
        });
    }
}
customElements.define(KnowledgeView.selector, KnowledgeView);

cache=(()=>{return { KnowledgeView: KnowledgeView };})();return cache;};})();
const __brainExplorerModule22=(()=>{let cache;return()=>{if(cache)return cache;
const { isRawKnowledgeItem, rawKnowledgeItems } = __brainExplorerModule23();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

/**
 * Converts loosely shaped knowledge API payloads into the strongly typed records
 * consumed by the presentation graph. The class owns payload interpretation only;
 * it never lays out nodes, renders markup, or mutates component state.
 */
class KnowledgeGraphNormalizer {
    /**
     * Holds the immutable normalization context required for processing the knowledge graph.
     *
     * @type {KnowledgeGraphNormalizationContext}
     */
    #context;
    /**
     * Create a payload normalizer for one component-state snapshot.
     *
     * @param {KnowledgeGraphNormalizationContext} context Query mode, scope, and stable identifier contract.
     */
    constructor(context) {
        this.#context = context;
    }
    /**
     * Convert an unknown command payload into normalized node and relation records.
     * Unsupported values are represented by empty collections, while malformed
     * relations are omitted rather than leaking partial edge contracts downstream.
     *
     * @param {unknown} data Untrusted data returned by the API facade.
     * @returns {KnowledgeGraphCollection} Fully typed node and relation collections.
     */
    collect(data) {
        const relations = this.#relationDataArray(data)
            .map((item, index) => this.#relationFromItem(item, index))
            .filter((relation) => relation !== null);
        const records = this.#nodeDataArray(data)
            .map((item, index) => this.#recordFromItem(item, index))
            .filter(record => Boolean(record.label));
        return { records, relations };
    }
    /**
     * Resolve payload arrays that represent visible nodes for the active mode.
     * @param {unknown} data The raw input data, which may be an array or an object containing knowledge items, to be normalized into node values.
     * @returns {RawKnowledgeNodeValue[]} An array of RawKnowledgeNodeValue objects extracted and typed from the input data.
     */
    #nodeDataArray(data) {
        if (Array.isArray(data)) {
            return this.#withVisualType(data, this.#context.mode === "classes" ? "class" : "entity");
        }
        if (!isRawKnowledgeItem(data))
            return [];
        if (this.#context.mode === "all") {
            const combined = [
                ...this.#withVisualType(data.entities || data.nodes || [], "entity"),
                ...this.#withVisualType(data.classes || [], "class"),
                ...this.#withVisualType(data.results || data.matches || [], "entity"),
            ];
            if (combined.length)
                return combined;
        }
        if (this.#context.mode === "classes" && Array.isArray(data.classes)) {
            return this.#withVisualType(data.classes, "class");
        }
        for (const key of ["entities", "nodes", "results", "matches"]) {
            const values = data[key];
            if (!Array.isArray(values))
                continue;
            const filtered = this.#context.mode === "entities"
                ? values.filter(item => !this.#looksLikeClass(item))
                : values;
            return this.#withVisualType(filtered, "entity");
        }
        return Object.values(data)
            .filter(Array.isArray)
            .flat()
            .filter(item => !this.#looksLikeRelation(item))
            .flatMap(item => this.#withVisualType([item], this.#looksLikeClass(item) ? "class" : "entity"));
    }
    /**
     * Copy UI-only visual metadata onto object records without mutating API data.
     *
     * @param {unknown} items Candidate node values.
     * @param {KnowledgeVisualType} visualType Visual category assigned to accepted values.
     * @returns {RawKnowledgeNodeValue[]} String or object node values carrying a valid presentation shape.
     */
    #withVisualType(items, visualType) {
        if (!Array.isArray(items))
            return [];
        return items
            .map((item) => isRawKnowledgeItem(item) ? { ...item, __visualType: visualType } : item)
            .filter((item) => typeof item === "string" || isRawKnowledgeItem(item));
    }
    /**
     * Resolve payload arrays that represent graph relations.
     * @param {unknown} data The raw input object or value to be scanned for relation-like data structures.
     * @returns {RawKnowledgeItem[]} An array of validated RawKnowledgeItem objects extracted from the input.
     */
    #relationDataArray(data) {
        if (!isRawKnowledgeItem(data))
            return [];
        for (const key of ["relations", "edges", "links"]) {
            if (Array.isArray(data[key]))
                return rawKnowledgeItems(data[key]);
        }
        return Object.values(data)
            .filter(Array.isArray)
            .flat()
            .filter(isRawKnowledgeItem)
            .filter(item => this.#looksLikeRelation(item));
    }
    /**
     * Convert one accepted node value into the complete graph-record contract.
     * @param {RawKnowledgeNodeValue} item The raw knowledge node data to be normalized.
     * @param {number} index The positional index of the item used for label generation and fallback ID creation.
     * @returns {KnowledgeRecord} A normalized KnowledgeRecord containing standardized identity, classification, and source metadata.
     */
    #recordFromItem(item, index) {
        const raw = isRawKnowledgeItem(item) ? item : { label: item };
        const label = this.#itemLabel(item, index);
        const sourcePath = String(raw.source_path || raw.path || raw.source || "");
        const domain = this.#domainFromRecord(raw, sourcePath);
        const entityId = raw.entity_id ?? raw.id ?? "";
        return {
            id: String(entityId || this.#context.nodeId(domain, label, index)),
            label,
            kind: "node",
            visualType: this.#looksLikeClass(raw) || raw.__visualType === "class" ? "class" : "entity",
            context: this.#contextFromRecord(raw, sourcePath),
            classHint: String(raw.entity_class || raw.class || raw.type || raw.kind || ""),
            domain,
            entityId: String(entityId),
            knowledgeScope: String(raw.knowledge_scope || this.#context.scope || "global"),
            source: sourcePath || String(raw.source_type || raw.source_title || "knowledge"),
            description: String(raw.description || raw.excerpt || raw.text || ""),
            confidence: raw.confidence ?? raw.score ?? "",
            raw,
        };
    }
    /**
     * Convert one relation object into an edge record with stable endpoint ids.
     * @param {RawKnowledgeItem} item The raw data record containing potential relation properties and metadata.
     * @param {number} index The zero-based position of the item used to generate fallback labels and unique identifiers.
     * @returns {KnowledgeRelation | null} A KnowledgeRelation object containing normalized identifiers, labels, and scope, or null if the transformation fails.
     */
    #relationFromItem(item, index) {
        const sourcePath = String(item.source_path || item.path || item.source_file || item.source || "");
        const domain = this.#domainFromRecord(item, sourcePath);
        const fromLabel = String(item.subject_name || item.source_name || item.source_label || item.subject || item.from || item.head || item.source || item.entity || `Origen ${index + 1}`);
        const toLabel = String(item.object_name || item.target_name || item.target_label || item.object || item.to || item.tail || item.target || item.related || `Destino ${index + 1}`);
        const label = String(item.relation || item.predicate || item.label || item.type || item.kind || "relation");
        const fromEntityId = item.subject_entity_id ?? item.source_entity_id ?? item.from_entity_id ?? item.head_entity_id ?? "";
        const toEntityId = item.object_entity_id ?? item.target_entity_id ?? item.to_entity_id ?? item.tail_entity_id ?? "";
        return {
            id: String(item.id || `relation:${domain}:${fromLabel}:${label}:${toLabel}:${index}`),
            kind: "relation",
            label,
            fromLabel,
            toLabel,
            from: String(fromEntityId || this.#context.nodeId(domain, fromLabel)),
            to: String(toEntityId || this.#context.nodeId(domain, toLabel)),
            fromEntityId: String(fromEntityId),
            toEntityId: String(toEntityId),
            knowledgeScope: String(item.knowledge_scope || this.#context.scope || "global"),
            fromClass: String(item.subject_class || item.source_class || item.from_class || ""),
            toClass: String(item.object_class || item.target_class || item.to_class || ""),
            domain,
            context: this.#contextFromRecord(item, sourcePath),
            source: sourcePath || String(item.source_type || item.source_title || "knowledge"),
            description: String(item.description || item.excerpt || item.text || ""),
            confidence: item.confidence ?? item.score ?? "",
            raw: item,
        };
    }
    /**
     * Return whether a raw value contains a recognized endpoint pair.
     * @param {unknown} item The unknown value to be validated as a relational knowledge item.
     * @returns {boolean} A type guard boolean indicating whether the item conforms to the RawKnowledgeItem structure and contains relational property pairs.
     */
    #looksLikeRelation(item) {
        return isRawKnowledgeItem(item) && (("subject" in item && "object" in item)
            || ("source" in item && "target" in item)
            || ("from" in item && "to" in item)
            || ("head" in item && "tail" in item));
    }
    /**
     * Return whether node metadata identifies a class rather than an entity.
     * @param {unknown} item The raw knowledge item to evaluate for class-like characteristics.
     * @returns {boolean} True if the item is identified as a class, otherwise false.
     */
    #looksLikeClass(item) {
        if (!isRawKnowledgeItem(item))
            return false;
        const marker = String(item.entity_type || item.node_type || item.type || item.kind || item.category || item.entity_class || item.class || "").toLowerCase();
        const identifier = String(item.entity_id || item.id || "").toLowerCase();
        return marker === "cls" || marker === "class" || marker === "clase" || /^cls[:_-]/.test(identifier);
    }
    /**
     * Resolve the preferred human-readable label for one node value.
     * @param {RawKnowledgeNodeValue} item The raw knowledge node value to be labeled, provided as either a string or an object containing identity properties.
     * @param {number} index The zero-based position of the item used to generate a fallback label.
     * @returns {string} The resolved string label derived from the node's metadata or its sequence index.
     */
    #itemLabel(item, index) {
        if (typeof item === "string")
            return item;
        return String(item.canonical_name || item.name || item.title || item.entity || item.id || `Node ${index + 1}`);
    }
    /**
     * Derive a source-context label from path or record metadata.
     * @param {RawKnowledgeItem} item The raw knowledge record containing fallback metadata such as source type, domain, or kind.
     * @param {string} sourcePath The hierarchical path string used to extract the specific memory or knowledge context.
     * @returns {string} A string representing the resolved context, defaulting to 'knowledge' if no specific path or metadata is found.
     */
    #contextFromRecord(item, sourcePath) {
        if (sourcePath.includes("/")) {
            const parts = sourcePath.split("/").filter(Boolean);
            const memoryIndex = parts.indexOf("memory");
            if (memoryIndex >= 0)
                return parts.slice(memoryIndex, -1).join("/") || "memory";
            return parts.slice(0, -1).join("/") || parts[0] || "knowledge";
        }
        return String(item.source_type || item.domain || item.kind || "knowledge");
    }
    /**
     * Derive the canonical dotted domain from path or record metadata.
     * @param {RawKnowledgeItem} item The raw knowledge item containing potential fallback domain identifiers.
     * @param {string} sourcePath The file system or resource path used to derive the domain hierarchy.
     * @returns {string} The resolved domain string, defaulting to 'knowledge' or 'memory' if no specific domain is identified.
     */
    #domainFromRecord(item, sourcePath) {
        const normalizedPath = sourcePath.replaceAll("\\", "/");
        if (normalizedPath.includes("/")) {
            const parts = normalizedPath.split("/").filter(Boolean);
            const memoryIndex = parts.indexOf("memory");
            if (memoryIndex >= 0 && parts[memoryIndex + 1]) {
                const domainParts = parts.slice(memoryIndex + 1);
                const leafIndex = domainParts.length - 1;
                domainParts[leafIndex] = domainParts[leafIndex]?.replace(/\.[^.]+$/, "") || "";
                return domainParts.filter(Boolean).join(".") || "memory";
            }
            return parts[0] || "knowledge";
        }
        return String(item.domain || item.source_domain || item.source_type || "knowledge");
    }
}

cache=(()=>{return { KnowledgeGraphNormalizer: KnowledgeGraphNormalizer };})();return cache;};})();
const __brainExplorerModule23=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Runtime guards for heterogeneous Knowledge CLI payloads.
 */
/**
 * Determines whether an unknown transport value is a string-keyed object.
 * Arrays are excluded because Knowledge commands treat them as collections.
 *
 * @param {unknown} value Unknown value received from an API response.
 * @returns {boolean} `true` when named properties can be read safely.
 */
function isRawKnowledgeItem(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
/**
 * Keeps only object-like values from a heterogeneous transport array.
 *
 * @param {unknown} values Unknown collection returned by a Knowledge command.
 * @returns {RawKnowledgeItem[]} Strongly narrowed raw records ready for normalization.
 */
function rawKnowledgeItems(values) {
    return Array.isArray(values) ? values.filter(isRawKnowledgeItem) : [];
}

cache=(()=>{return { isRawKnowledgeItem: isRawKnowledgeItem, rawKnowledgeItems: rawKnowledgeItems };})();return cache;};})();
const __brainExplorerModule24=(()=>{let cache;return()=>{if(cache)return cache;
const { shortKnowledgeLabel } = __brainExplorerModule25();
/**
 * Projects Knowledge persistence sources into the shared structure-tree contract.
 *
 * The projector owns source-specific hierarchy construction while the Knowledge layout
 * remains responsible for selection, navigation, and asynchronous data acquisition.
 *
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

/**
 * Builds the complete global/local source hierarchy consumed by `StructureTree`.
 */
class KnowledgeSourceTreeProjector {
    /**
     * Project enabled physical scopes into shared tree nodes.
     *
     * @param {KnowledgeSourceTreeProjectionInput} input Source records and graph presentation policies.
     * @returns {KnowledgeTreeNode[]} Root nodes ordered as global then local scope.
     */
    project(input) {
        return [
            this.#scopeRoot("global", "Global knowledge", input.memoryPaths, input),
            this.#scopeRoot("local", "Local knowledge", [], input),
        ].filter(root => input.selectedScopes.has(root.scope === "global" ? "global" : "local"));
    }
    /**
     * Build one physical-scope root without hiding canonical empty sources.
     * @param {"global" | "local"} scope Physical persistence scope.
     * @param {string} label User-facing root label.
     * @param {readonly string[]} canonicalPaths Canonical memory paths owned by the scope.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode} A KnowledgeTreeNode object representing the root of the specified scope.
     */
    #scopeRoot(scope, label, canonicalPaths, input) {
        const children = scope === "global"
            ? this.#globalChildren(canonicalPaths, input)
            : this.#localChildren(input);
        return {
            id: `${scope}::all`,
            path: `${scope}::all`,
            label,
            icon: "database",
            count: input.graphCountLabel("all", scope),
            children,
            actions: [{ id: "filter-source", label: "FILTER", icon: "filter" }],
            scope,
            domain: "all",
            sourceKind: "",
            sourcePath: "",
            visualType: "",
        };
    }
    /**
     * Build source categories owned by global persistence.
     * @param {readonly string[]} canonicalPaths Canonical global-memory paths.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode[]} An array of KnowledgeTreeNode objects representing the global memory, class projections, and picture categories.
     */
    #globalChildren(canonicalPaths, input) {
        const leaves = new Set(canonicalPaths.filter(path => !canonicalPaths.some(candidate => candidate.startsWith(`${path}.`))));
        const memoryEntries = canonicalPaths.map(path => ({
            segments: this.#domainParts(path),
            domain: path,
            sourcePath: leaves.has(path) ? `memory/${path.replaceAll(".", "/")}.md` : "",
        }));
        const pictureEntries = input.pictures.map(picture => this.#pictureEntry(picture));
        return [
            this.#sourceCategory("global", "memory", "Global memory", memoryEntries, "database", input),
            this.#classProjection("global", input),
            this.#sourceCategory("global", "pictures", "Pictures", pictureEntries, "camera", input),
        ];
    }
    /**
     * Build source categories owned by local workspace persistence.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode[]} An array of KnowledgeTreeNode objects representing the local source hierarchy.
     */
    #localChildren(input) {
        return [
            this.#sourceCategory("local", "memory", "Local memory", [], "database", input),
            this.#classProjection("local", input),
            this.#sourceCategory("local", "logs", "Logs", this.#logEntries(input.logEntries), "document", input),
            this.#sourceCategory("local", "messages", "Messages", this.#messageEntries(input), "messageCircle", input),
        ];
    }
    /**
     * Build one canonical picture entry without duplicating its domain prefix.
     * @param {PictureRecord} picture Picture registry record to project.
     *
     * @returns {KnowledgeSourceEntry} A knowledge source entry object containing the resolved path segments, routing targets, and descriptive details.
     */
    #pictureEntry(picture) {
        const sourcePath = String(picture.relative_path || picture.filename || "").replaceAll("\\", "/");
        const sourceSegments = sourcePath.split("/").filter(Boolean);
        const domainSegments = this.#domainParts(String(picture.domain || "no-domain"));
        const alreadyPrefixed = domainSegments.every((segment, index) => (String(sourceSegments[index] || "").toLowerCase() === segment.toLowerCase()));
        const segments = alreadyPrefixed ? sourceSegments : [...domainSegments, ...sourceSegments];
        return {
            segments,
            sourcePrefixes: segments.map((_unusedSegment, index) => segments.slice(0, index + 1).join("/")),
            domain: "pictures",
            sourcePath,
            openRoute: "pictures",
            openTarget: { pictureId: String(picture.id) },
            detail: String(picture.description || ""),
        };
    }
    /**
     * Build a canonical source category from filesystem or registry entries.
     * @param {"global" | "local"} scope Physical persistence scope.
     * @param {KnowledgeSourceKind} key Canonical source family.
     * @param {string} label User-facing category label.
     * @param {readonly KnowledgeSourceEntry[]} entries Source entries to arrange hierarchically.
     * @param {"edit" | "settings" | "home" | "database" | "graph" | "search" | "messageCircle" | "sliders" | "users" | "document" | "plus" | "documentPlus" | "folderPlus" | "copy" | "trash" | "save" | "refresh" | "pulse" | "folder" | "moon" | "sun" | "terminal" | "close" | "collapseLeft" | "expandRight" | "eye" | "filter" | "checkSquare" | "chevronRight" | "chevronLeft" | "chevronDown" | "minus" | "more" | "clock" | "camera" | "book" | "volume" | "play" | "pause" | "download"} categoryIcon Shared icon assigned to the root.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode} A KnowledgeTreeNode representing a categorized folder of knowledge sources with associated metadata and children.
     */
    #sourceCategory(scope, key, label, entries, categoryIcon, input) {
        const root = {
            label: "",
            path: "",
            scope,
            domain: "all",
            sourceKind: key,
            sourcePath: "",
            children: new Map(),
        };
        entries.forEach(entry => this.#appendEntry(root, scope, key, entry));
        return {
            id: `${scope}::source:${key}`,
            path: `${scope}::source:${key}`,
            label,
            icon: categoryIcon,
            count: input.graphCountLabel("all", scope, key),
            children: this.#treeNodes([...root.children.values()], input),
            actions: [{ id: "filter-source", label: "FILTER", icon: "filter" }],
            scope,
            domain: "all",
            sourceKind: key,
            folder: true,
            sortKey: `${{ memory: 0, pictures: 2, logs: 2, messages: 3 }[key]}:${label}`,
        };
    }
    /**
     * Append one source entry to its hierarchical accumulator.
     * @param {KnowledgeSourceTreeAccumulator} root Mutable accumulator root.
     * @param {"global" | "local"} scope Physical persistence scope.
     * @param {KnowledgeSourceKind} key Canonical source family.
     * @param {KnowledgeSourceEntry} entry Source entry to append.
     */
    #appendEntry(root, scope, key, entry) {
        let node = root;
        entry.segments.forEach((part, index) => {
            const terminal = index === entry.segments.length - 1;
            const branchSourcePath = String(entry.sourcePrefixes?.[index] || "");
            const baseId = `${scope}::source:${key}/${entry.segments.slice(0, index + 1).join("/")}`;
            const id = terminal && entry.sourcePath ? `${baseId}::${entry.sourcePath}` : baseId;
            const childKey = terminal && entry.sourcePath ? `${part}::${entry.sourcePath}` : part;
            const branchDomain = key === "memory" ? entry.segments.slice(0, index + 1).join(".") : entry.domain;
            if (!node.children.has(childKey)) {
                node.children.set(childKey, {
                    label: part,
                    path: id,
                    scope,
                    domain: branchDomain,
                    sourceKind: key,
                    sourcePath: branchSourcePath,
                    children: new Map(),
                });
            }
            const child = node.children.get(childKey);
            if (!child)
                throw new Error(`Unable to create Knowledge source node: ${id}`);
            node = child;
            if (key === "memory")
                node.domain = branchDomain;
            if (terminal)
                Object.assign(node, entry);
        });
    }
    /**
     * Build a non-owning class projection while retaining canonical source ownership.
     * @param {"global" | "local"} scope Physical persistence scope.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode} A KnowledgeTreeNode configured as a folder for classes with associated metadata and filter actions.
     */
    #classProjection(scope, input) {
        return {
            id: `${scope}::classes`,
            path: `${scope}::classes`,
            label: "Classes",
            icon: "graph",
            count: input.graphCountLabel("all", scope, "", "", "class"),
            children: [],
            actions: [{ id: "filter-source", label: "FILTER", icon: "filter" }],
            scope,
            domain: "all",
            sourceKind: "",
            visualType: "class",
            folder: true,
            sortKey: "1:Classes",
        };
    }
    /**
     * Project persisted messages beneath their canonical sessions.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeSourceEntry[]} An array of KnowledgeSourceEntry objects containing formatted segments, routing metadata, and message details.
     */
    #messageEntries(input) {
        const sessions = new Map(input.messageSessions.map(session => [`${session.date}:${session.chatId}`, session]));
        return input.messages.map(message => {
            const session = sessions.get(`${message.date}:${message.chat_id}`) || null;
            const date = String(session?.date || message.created_at || "no-date").slice(0, 10);
            const sessionLabel = String(session?.label || session?.chatId || message.chat_id || "session");
            const body = String(message.text || "Message has no body");
            return {
                segments: [...date.split("-"), sessionLabel, shortKnowledgeLabel(body.replace(/\s+/g, " "), 54)],
                domain: "messages",
                sourcePath: `messages/${message.id}`,
                openRoute: "messages",
                openTarget: { messageId: String(message.id), sessionId: String(session?.id || "") },
                detail: body,
            };
        });
    }
    /**
     * Project persisted log-index entries as canonical local sources.
     * @param {readonly LogEntryPayload[]} entries Log-index records to project.
     *
     * @returns {KnowledgeSourceEntry[]} An array of KnowledgeSourceEntry objects containing calculated segments, source paths, and routing targets.
     */
    #logEntries(entries) {
        return entries.map((entry, index) => {
            const domain = String(entry.domain || "logs");
            const timestamp = String(entry.timestamp || "");
            const [date = "", ...timeParts] = timestamp.split(" ");
            return {
                segments: [...this.#domainParts(domain), String(entry.title || timestamp || `log-${index + 1}`)],
                domain: "logs",
                sourcePath: `logs/${domain}/${timestamp || "undated"}/${index}`,
                openRoute: "logs",
                openTarget: { domain, date, time: timeParts.join(" ") },
                detail: String(entry.title || ""),
            };
        });
    }
    /**
     * Convert accumulated source branches into shared tree nodes.
     * @param {readonly KnowledgeSourceTreeAccumulator[]} nodes Accumulated source branches.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode[]} A sorted array of KnowledgeTreeNode objects representing the projected hierarchy.
     */
    #treeNodes(nodes, input) {
        return nodes.map(node => {
            const children = this.#treeNodes([...node.children.values()], input);
            const actions = [
                { id: "consolidate-source", label: "CONSOLIDATE", icon: "graph" },
                { id: "filter-source", label: "FILTER", icon: "filter" },
                ...(node.openRoute ? [{ id: "open-source", label: "OPEN", icon: "chevronRight" }] : []),
            ];
            return {
                id: node.path,
                path: node.path,
                label: node.label,
                color: input.domainColor(node.path),
                count: input.graphCountLabel(node.domain, node.scope, node.sourceKind, node.sourcePath || ""),
                children,
                actions,
                scope: node.scope,
                domain: node.domain,
                sourceKind: node.sourceKind || "",
                visualType: node.visualType ?? "",
                ...(node.sortKey === undefined ? {} : { sortKey: node.sortKey }),
                sourcePath: node.sourcePath || "",
                openRoute: node.openRoute || "",
                openTarget: node.openTarget || null,
                detail: node.detail || "",
                folder: children.length > 0 || (!node.sourcePath && !node.openRoute),
            };
        }).sort((left, right) => left.label.localeCompare(right.label));
    }
    /**
     * Split a domain into non-empty canonical path segments.
     * @param {string} domain Dotted or filesystem-like domain path.
     *
     * @returns {string[]} An array of cleaned string segments extracted from the domain.
     */
    #domainParts(domain) {
        return domain.split(/[./\\]+/).map(part => part.trim()).filter(Boolean);
    }
}

cache=(()=>{return { KnowledgeSourceTreeProjector: KnowledgeSourceTreeProjector };})();return cache;};})();
const __brainExplorerModule25=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Build a deterministic fallback node identifier from graph context.
 *
 * The identifier mirrors the legacy canvas contract: labels are normalized only
 * by lower-casing, while an empty label falls back to the supplied stable index.
 *
 * @param {string} domain Canonical domain that owns the visible graph node.
 * @param {string} label Human-readable entity or class label.
 * @param {number} index Stable fallback index used only when the label is empty.
 * @returns {string} Presentation-only node identifier shared by records and relations.
 */
function knowledgeNodeId(domain, label, index = 0) {
    return `node:${domain}:${String(label || index).toLowerCase()}`;
}
/**
 * Shorten a graph label to fit a constrained canvas or source-tree surface.
 *
 * @param {string} label Full label supplied by normalized knowledge data.
 * @param {number} limit Maximum rendered character count, including the ellipsis.
 * @returns {string} Original text when it fits, otherwise a stable ellipsis-truncated label.
 */
function shortKnowledgeLabel(label, limit = 14) {
    const text = String(label || "");
    return text.length > limit ? `${text.slice(0, Math.max(1, limit - 1))}...` : text;
}

cache=(()=>{return { knowledgeNodeId: knowledgeNodeId, shortKnowledgeLabel: shortKnowledgeLabel };})();return cache;};})();
const __brainExplorerModule26=(()=>{let cache;return()=>{if(cache)return cache;
const { renderDescriptionCard } = __brainExplorerModule27();
const { escapeHtml } = __brainExplorerModule4();
/**
 * Renders the Knowledge inspector without owning DOM lifecycle or graph state.
 *
 * The renderer preserves the layout's established HTML and action attributes while
 * isolating presentation formatting from `KnowledgeView` orchestration.
 *
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */


/**
 * Produces inspector markup for empty, node, and relation selections.
 */
class KnowledgeInspectorRenderer {
    /**
     * Render the inspector for the current persistent selection.
     * @param {KnowledgeInspectorRenderInput} input Graph state and source-resolution policies.
     * @returns {string} Inspector HTML preserving existing action contracts.
     */
    render(input) {
        const selectedRelation = input.edges.find(edge => edge.id === input.selectedRelationId);
        if (selectedRelation)
            return this.#renderRelation(selectedRelation, input);
        const selectedNode = input.nodes.find(node => node.id === input.selectedNodeId);
        if (selectedNode)
            return this.#renderNode(selectedNode, input);
        return this.#renderEmpty(input);
    }
    /**
     * Render the unselected inspector and important-node shortcuts.
     * @param {KnowledgeInspectorRenderInput} input Current graph render input.
     * @returns {string} Empty-selection inspector HTML.
     */
    #renderEmpty(input) {
        return `
            <div class="content-head">
                <strong>Inspector</strong>
                <span>${escapeHtml(String(input.nodes.length))} nodes · ${escapeHtml(String(input.edges.length))} relations</span>
            </div>
            <div class="node-inspector scroll-list">
                <p>Select a canvas node or relation. Nodes are draggable; the canvas supports pan and zoom.</p>
                <div class="source-chip-row important-node-chips" aria-label="Important entities">
                    ${input.importantNodes.map(node => `
                        <button data-action="focus-node" data-node-id="${escapeHtml(node.id)}" title="Focus ${escapeHtml(node.label)}" style="--entity-color: ${escapeHtml(node.color)}">
                            <strong>${escapeHtml(node.label)}</strong>
                            <small>${escapeHtml(String(node.degree))}</small>
                        </button>
                    `).join("")}
                </div>
            </div>
        `;
    }
    /**
     * Render one selected graph node and its source previews.
     * @param {KnowledgeGraphNode} selected Selected graph node.
     * @param {KnowledgeInspectorRenderInput} input Current graph render input.
     * @returns {string} Node inspector HTML.
     */
    #renderNode(selected, input) {
        const picture = input.pictureForNode(selected);
        const message = input.messageForNode(selected);
        const pictureTag = input.isPictureTagNode(selected);
        return `
            <div class="content-head">
                <strong>${escapeHtml(selected.label)}</strong>
                <span>${escapeHtml(selected.domain)}</span>
            </div>
            <div class="node-inspector scroll-list">
                ${picture ? `
                    <button class="knowledge-source-preview" data-action="open-detail-source" data-route="pictures" data-picture-id="${escapeHtml(String(picture.id))}">
                        <img src="${escapeHtml(input.pictureUrl(String(picture.id)))}" alt="${escapeHtml(picture.description || picture.filename)}">
                        <span>Open in Pictures</span>
                    </button>
                ` : ""}
                ${message ? `
                    <blockquote class="knowledge-message-preview">${escapeHtml(String(message.text || ""))}</blockquote>
                    <button class="secondary-action" data-action="open-detail-source" data-route="messages" data-message-id="${escapeHtml(String(message.id))}">Open in Messages</button>
                ` : ""}
                <dl>
                    <dt>Context</dt><dd>${escapeHtml(selected.context)}</dd>
                    <dt>Domain</dt><dd>${escapeHtml(selected.domain)}</dd>
                    <dt>${pictureTag ? "Provenance" : "Source"}</dt><dd>${pictureTag
            ? `Derived from image analysis · ${escapeHtml(selected.source)}`
            : escapeHtml(selected.source)}</dd>
                    <dt>Suggested class</dt><dd>${escapeHtml(selected.classHint || "-")}</dd>
                    <dt>Confidence</dt><dd>${escapeHtml(String(selected.confidence || "-"))}</dd>
                </dl>
                ${renderDescriptionCard(selected.description || "", { title: picture ? "Image description" : "Entity description" })}
                ${this.#renderRelated(selected, input)}
            </div>
        `;
    }
    /**
     * Render one selected relation and its endpoint shortcuts.
     * @param {KnowledgeGraphEdge} relation Selected graph relation.
     * @param {KnowledgeInspectorRenderInput} input Current graph render input.
     * @returns {string} Relation inspector HTML.
     */
    #renderRelation(relation, input) {
        return `
            <div class="content-head"><strong>Relation</strong><span>${escapeHtml(relation.label)}</span></div>
            <div class="node-inspector relation-inspector scroll-list">
                <dl>
                    <dt>Name</dt><dd>${escapeHtml(relation.label)}</dd>
                    <dt>Source node</dt><dd>${escapeHtml(relation.fromLabel)}</dd>
                    <dt>Target node</dt><dd>${escapeHtml(relation.toLabel)}</dd>
                    <dt>Context</dt><dd>${escapeHtml(relation.context)}</dd>
                    <dt>Domain</dt><dd>${escapeHtml(relation.domain)}</dd>
                    <dt>Source</dt><dd>${escapeHtml(relation.source)}</dd>
                    <dt>Confidence</dt><dd>${escapeHtml(String(relation.confidence || "-"))}</dd>
                </dl>
                ${renderDescriptionCard(relation.description || "Relation detected by the CLI facade.", { title: "Relation description" })}
                <div class="graph-list">
                    ${[relation.from, relation.to].map(nodeId => {
            const node = input.nodes.find(item => item.id === nodeId);
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
     * Render visible relations connected to one selected node.
     * @param {KnowledgeGraphNode} selected Selected graph node.
     * @param {KnowledgeInspectorRenderInput} input Current graph render input.
     * @returns {string} Related-relation list HTML, or an empty string when isolated.
     */
    #renderRelated(selected, input) {
        const related = input.edges.filter(edge => edge.from === selected.id || edge.to === selected.id).slice(0, 10);
        if (!related.length)
            return "";
        return `
            <h2>Visible relations</h2>
            <div class="graph-list">
                ${related.map(edge => {
            const oppositeId = edge.from === selected.id ? edge.to : edge.from;
            const opposite = input.nodes.find(node => node.id === oppositeId);
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
}

cache=(()=>{return { KnowledgeInspectorRenderer: KnowledgeInspectorRenderer };})();return cache;};})();
const __brainExplorerModule27=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml, renderMarkdown } = __brainExplorerModule4();
/**
 * Shared structured presentation for long image and entity descriptions.
 */

const ENTITY_SECTION_TITLES = new Set([
    "subject",
    "subjects",
    "main subject",
    "main subjects",
    "tag",
    "tags",
    "semantic tag",
    "semantic tags"
]);
/**
 * Split model-authored Markdown into stable sections.
 *
 * Headings and bold field labels such as `**Subjects:**` are treated as
 * section boundaries even when several fields share one physical line.
 *
 * @param {string} markdown The raw markdown text to be parsed into titled sections.
 * @returns {DescriptionSection[]} An array of DescriptionSection objects containing the extracted titles and their corresponding body content.
 */
function parseDescriptionSections(markdown) {
    const source = String(markdown || "").trim();
    if (!source)
        return [];
    const markerPattern = /(?:^|\n)[ \t]{0,3}#{1,4}[ \t]+([^\n]+)|\*\*([^*\n:]{1,80}):\*\*/gm;
    const markers = [];
    let match;
    while ((match = markerPattern.exec(source)) !== null) {
        const startsWithNewline = match[0].startsWith("\n");
        markers.push({
            index: match.index + (startsWithNewline ? 1 : 0),
            end: markerPattern.lastIndex,
            title: normalizeSectionTitle(match[1] || match[2] || "Description")
        });
    }
    if (!markers.length)
        return [createSection("Description", source, 0)];
    const sections = [];
    const preamble = source.slice(0, markers[0]?.index ?? source.length).trim();
    if (preamble)
        sections.push(createSection("Overview", preamble, sections.length));
    markers.forEach((marker, index) => {
        const nextIndex = markers[index + 1]?.index ?? source.length;
        const body = normalizeSectionBody(source.slice(marker.end, nextIndex).replace(/^[\s:–—]+/, "").trim());
        if (body)
            sections.push(createSection(marker.title, body, sections.length));
    });
    return sections.length ? sections : [createSection("Description", source, 0)];
}
/**
 * Render a bounded description card with native, accessible disclosures.
 * @param {string} markdown The raw markdown string to be parsed into collapsible sections.
 * @param {DescriptionCardOptions} options Configuration for the card's title, empty state text, and initial expansion state of the first section.
 * @returns {string} An HTML string containing the structured description card markup.
 */
function renderDescriptionCard(markdown, options = {}) {
    const title = options.title || "Description";
    const emptyText = options.emptyText || "No description available.";
    const sections = parseDescriptionSections(markdown);
    const content = sections.length
        ? sections.map((section, index) => `
            <details class="description-card-section" ${options.openFirst !== false && index === 0 ? "open" : ""}>
                <summary>
                    <span>${escapeHtml(section.title)}</span>
                    <span class="description-card-chevron" aria-hidden="true">&#8250;</span>
                </summary>
                <div class="description-card-body">${renderDescriptionSection(section)}</div>
            </details>
        `).join("")
        : `<p class="description-card-empty">${escapeHtml(emptyText)}</p>`;
    return `
        <article class="description-card" data-role="description-card">
            <header>
                <strong>${escapeHtml(title)}</strong>
                ${sections.length > 1 ? `<span>${sections.length} sections</span>` : ""}
            </header>
            <div class="description-card-sections">${content}</div>
        </article>
    `;
}
/**
 * Extract entity-like values from Subjects and tag sections.
 * @param {DescriptionSection} section The description section object containing the title and body text to be parsed.
 * @returns {string[]} An array of cleaned, unique strings extracted from the section body, or an empty array if the section title is invalid.
 */
function descriptionEntityValues(section) {
    if (!ENTITY_SECTION_TITLES.has(section.title.trim().toLowerCase()))
        return [];
    const normalized = section.body
        .replace(/\s*,\s*and\s+/gi, ",")
        .replace(/\s+and\s+/gi, ",")
        .replace(/^[-*]\s*/, "");
    const seen = new Set();
    return normalized
        .split(/\s*,\s*|\r?\n+/)
        .map(value => value.replace(/^[-*]\s*/, "").replace(/[.;:]+$/, "").trim())
        .filter(value => {
        const key = value.toLowerCase();
        if (!value || value.length > 80 || seen.has(key))
            return false;
        seen.add(key);
        return true;
    });
}
/**
 * Render entity sections as resolvable badges and all other bodies as Markdown.
 * @param {DescriptionSection} section The description section object containing the title, body, and associated entity data.
 * @returns {string} An HTML string containing either a badge container for entities or the rendered markdown content.
 */
function renderDescriptionSection(section) {
    const entities = descriptionEntityValues(section);
    if (!entities.length)
        return renderMarkdown(section.body);
    return `
        <div class="description-entity-badges" aria-label="${escapeHtml(section.title)} entities">
            ${entities.map(entity => `
                <button type="button" class="description-entity-badge" data-action="resolve-description-entity" data-entity-label="${escapeHtml(entity)}">
                    ${escapeHtml(entity)}
                </button>
            `).join("")}
        </div>
    `;
}
/**
 * Convert compact model-authored inline lists into Markdown list lines.
 * @param {string} body The raw string content of the section body to be formatted.
 * @returns {string} The processed string with normalized line breaks for list items.
 */
function normalizeSectionBody(body) {
    if (/^[-*]\s+/.test(body))
        return body.replace(/\s+([-*])\s+/g, "\n$1 ");
    if (/^\d+\.\s+/.test(body))
        return body.replace(/\s+(\d+\.)\s+/g, "\n$1 ");
    return body;
}
/**
 * Create a unique, selector-safe section identity.
 * @param {string} title The display text used to generate the section's slug and title property.
 * @param {string} body The descriptive content assigned to the section's body property.
 * @param {number} index The zero-based position used to ensure ID uniqueness via 1-based incrementing.
 * @returns {DescriptionSection} A DescriptionSection object containing the generated ID, title, and body.
 */
function createSection(title, body, index) {
    const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "section";
    return { id: `${slug}-${index + 1}`, title, body };
}
/**
 * Remove residual Markdown emphasis from disclosure labels.
 * @param {string} title The raw title string to be normalized.
 * @returns {string} A cleaned string formatted for display as a section title.
 */
function normalizeSectionTitle(title) {
    return String(title || "Description")
        .replace(/^\*+|\*+$/g, "")
        .replace(/\s+/g, " ")
        .trim()
        .replace(/:$/, "") || "Description";
}

cache=(()=>{return { parseDescriptionSections: parseDescriptionSections, renderDescriptionCard: renderDescriptionCard, descriptionEntityValues: descriptionEntityValues };})();return cache;};})();
const __brainExplorerModule28=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Positions Knowledge graph nodes as connected components and domain grids.
 *
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */
/**
 * Mutating layout engine whose sole output is graph-node coordinates.
 */
class KnowledgeGraphLayoutEngine {
    /**
     * Nodes participating in the current bounded layout operation.
     * @type {KnowledgeGraphNode[]}
     */
    #nodes = [];
    /**
     * Edges participating in the current bounded layout operation.
     * @type {KnowledgeGraphEdge[]}
     */
    #edges = [];
    /**
     * Position supplied nodes in place while preserving their identity and metadata.
     * @param {KnowledgeGraphNode[]} nodes Mutable graph nodes to position.
     * @param {readonly KnowledgeGraphEdge[]} edges Immutable graph connectivity used by the layout.
     */
    layout(nodes, edges) {
        this.#nodes = nodes;
        this.#edges = [...edges];
        this.#layoutGraphByNeighbors();
    }
    /**
     * Layout nodes as connected neighbor groups and isolated domain grids.
     */
    #layoutGraphByNeighbors() {
        const linkedIds = new Set(this.#edges.flatMap(edge => [edge.from, edge.to]));
        const linkedNodes = this.#nodes.filter(node => linkedIds.has(node.id));
        const freeNodes = this.#nodes.filter(node => !linkedIds.has(node.id));
        const footprints = this.#nodeLayoutFootprints();
        if (linkedNodes.length) {
            this.#layoutConnectedNodes(linkedNodes, 0, footprints);
        }
        const startY = linkedNodes.length ? 420 : 0;
        this.#layoutDomainGrid(freeNodes, startY, footprints);
    }
    /**
     * Estimate each node's visual footprint from radius, labels, connectivity, and predicates.
     * @returns {Map<string, { width: number; height: number; gap: number; relationLabelWidth: number; }>} A map associating node identifiers with their calculated layout footprints, including width, height, gap, and relation label width.
     */
    #nodeLayoutFootprints() {
        const degrees = this.#nodeDegrees();
        const longestPredicate = new Map(this.#nodes.map(node => [node.id, 0]));
        this.#edges.forEach(edge => {
            const length = String(edge.label || "").length;
            longestPredicate.set(edge.from, Math.max(longestPredicate.get(edge.from) || 0, length));
            longestPredicate.set(edge.to, Math.max(longestPredicate.get(edge.to) || 0, length));
        });
        return new Map(this.#nodes.map(node => {
            const degree = degrees.get(node.id) || 0;
            const connectivity = Math.min(48, Math.sqrt(degree) * 8);
            const nodeLabelWidth = Math.min(240, Math.max(62, String(node.label || "").length * 7.2 + 24));
            const relationLabelWidth = Math.min(180, (longestPredicate.get(node.id) || 0) * 6.2);
            return [node.id, {
                    width: Math.max(node.radius * 2 + 24, nodeLabelWidth) + connectivity + relationLabelWidth * 0.16,
                    height: node.radius * 2 + 32 + Math.min(30, connectivity * 0.55),
                    gap: 26 + Math.min(28, relationLabelWidth * 0.12) + Math.min(18, connectivity * 0.3),
                    relationLabelWidth
                }];
        }));
    }
    /**
     * Return the number of layout edges incident to every projected node.
     * @returns {Map<string, number>} A map associating each node identifier with its total edge count.
     */
    #nodeDegrees() {
        const degrees = new Map(this.#nodes.map(node => [node.id, 0]));
        this.#edges.forEach(edge => {
            degrees.set(edge.from, (degrees.get(edge.from) || 0) + 1);
            degrees.set(edge.to, (degrees.get(edge.to) || 0) + 1);
        });
        return degrees;
    }
    /**
     * Expand connected components by neighbor depth.
     *
     * @param {object[]} nodes Connected nodes.
     * @param {number} startY Vertical offset.
     * @returns {void}
     * @param {Map<string, KnowledgeNodeFootprint>} footprints The footprints value used by this operation.
     */
    #layoutConnectedNodes(nodes, startY, footprints) {
        const byId = new Map(nodes.map(node => [node.id, node]));
        const adjacency = this.#adjacencyMap(byId);
        const visited = new Set();
        const components = [];
        nodes.forEach(node => {
            if (visited.has(node.id)) {
                return;
            }
            components.push(this.#componentFromNode(node.id, adjacency, visited));
        });
        const rowWidth = Math.min(4200, Math.max(2200, Math.sqrt(nodes.length) * 210));
        let cursorX = 0;
        let cursorY = startY;
        let packedRowHeight = 0;
        components.sort((left, right) => right.length - left.length).forEach(component => {
            this.#positionComponent(component, adjacency, byId, 0, 0, footprints);
            const bounds = this.#componentBounds(component, byId, footprints);
            if (cursorX && cursorX + bounds.width > rowWidth) {
                cursorX = 0;
                cursorY += packedRowHeight + 220;
                packedRowHeight = 0;
            }
            this.#translateComponent(component, byId, cursorX - bounds.minX, cursorY - bounds.minY);
            cursorX += bounds.width + 220;
            packedRowHeight = Math.max(packedRowHeight, bounds.height);
        });
    }
    /**
     * Return a component rectangle that includes node and label footprints.      * @param {string[]} component The component value used by this operation.
     * @param {Map<string, KnowledgeGraphNode>} byId The by id value used by this operation.
     * @param {Map<string, KnowledgeNodeFootprint>} footprints The footprints value used by this operation.
     *
     * @returns {KnowledgeComponentBounds} An object containing the minimum and maximum coordinates and the total calculated width and height of the component.
     */
    #componentBounds(component, byId, footprints) {
        const bounds = component.reduce((result, id) => {
            const node = byId.get(id);
            const footprint = footprints.get(id);
            if (!node || !footprint)
                return result;
            return {
                minX: Math.min(result.minX, node.x - footprint.width / 2),
                maxX: Math.max(result.maxX, node.x + footprint.width / 2),
                minY: Math.min(result.minY, node.y - footprint.height / 2),
                maxY: Math.max(result.maxY, node.y + footprint.height / 2)
            };
        }, { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });
        return {
            ...bounds,
            width: Math.max(1, bounds.maxX - bounds.minX),
            height: Math.max(1, bounds.maxY - bounds.minY)
        };
    }
    /**
     * Translate every node in one already-positioned connected component.      * @param {string[]} component The component value used by this operation.
     * @param {Map<string, KnowledgeGraphNode>} byId The by id value used by this operation.
     * @param {number} deltaX The delta x value used by this operation.
     * @param {number} deltaY The delta y value used by this operation.
     */
    #translateComponent(component, byId, deltaX, deltaY) {
        component.forEach(id => {
            const node = byId.get(id);
            if (!node)
                return;
            node.x += deltaX;
            node.y += deltaY;
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
            adjacency.get(edge.from)?.add(edge.to);
            adjacency.get(edge.to)?.add(edge.from);
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
            if (!current)
                continue;
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
     * @param {Map<string, object>} footprints Estimated node footprints.
     * @returns {void}
     */
    #positionComponent(component, adjacency, byId, offsetX, offsetY, footprints) {
        const rootId = [...component].sort((left, right) => (adjacency.get(right)?.size || 0) - (adjacency.get(left)?.size || 0))[0];
        if (!rootId)
            return;
        const levels = this.#neighborLevels(rootId, adjacency);
        let previousRight = null;
        [...levels.entries()].sort(([left], [right]) => left - right).forEach(([, levelIds]) => {
            const ids = [...levelIds].sort((left, right) => {
                const degreeDifference = (adjacency.get(right)?.size || 0) - (adjacency.get(left)?.size || 0);
                return degreeDifference || String(byId.get(left)?.label || "").localeCompare(String(byId.get(right)?.label || ""));
            });
            const rowsPerColumn = Math.max(1, Math.ceil(Math.sqrt(ids.length * 1.6)));
            const columnCount = Math.ceil(ids.length / rowsPerColumn);
            const maxWidth = Math.max(...ids.map(id => footprints.get(id)?.width || 80));
            const maxPredicateWidth = Math.max(0, ...ids.map(id => footprints.get(id)?.relationLabelWidth || 0));
            const columnGap = 34 + Math.min(38, maxPredicateWidth * 0.18);
            const layerGap = 90 + Math.min(150, maxPredicateWidth * 0.72);
            const bandWidth = columnCount * maxWidth + Math.max(0, columnCount - 1) * columnGap;
            const bandLeft = previousRight === null ? offsetX - bandWidth / 2 : previousRight + layerGap;
            for (let column = 0; column < columnCount; column += 1) {
                const columnIds = ids.slice(column * rowsPerColumn, (column + 1) * rowsPerColumn);
                const totalHeight = columnIds.reduce((total, id, index) => {
                    const footprint = footprints.get(id) || { height: 70, gap: 28 };
                    return total + footprint.height + (index ? footprint.gap : 0);
                }, 0);
                let cursorY = offsetY - totalHeight / 2;
                columnIds.forEach((id, index) => {
                    const node = byId.get(id);
                    const footprint = footprints.get(id) || { height: 70, gap: 28 };
                    if (!node)
                        return;
                    if (index)
                        cursorY += footprint.gap;
                    node.x = bandLeft + column * (maxWidth + columnGap) + maxWidth / 2;
                    node.y = cursorY + footprint.height / 2;
                    cursorY += footprint.height;
                });
            }
            previousRight = bandLeft + bandWidth;
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
            if (!current)
                continue;
            if (!levels.has(current.depth)) {
                levels.set(current.depth, []);
            }
            levels.get(current.depth)?.push(current.id);
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
     * @param {Map<string, KnowledgeNodeFootprint>} footprints The footprints value used by this operation.
     */
    #layoutDomainGrid(nodes, startY, footprints) {
        const groups = new Map();
        nodes.forEach(node => {
            if (!groups.has(node.domain)) {
                groups.set(node.domain, []);
            }
            groups.get(node.domain)?.push(node);
        });
        let cursorX = 0;
        let cursorY = startY;
        let rowHeight = 0;
        [...groups.entries()].sort(([left], [right]) => left.localeCompare(right)).forEach(([, group], groupIndex) => {
            const columns = Math.ceil(Math.sqrt(group.length));
            const columnWidth = Math.max(116, ...group.map(node => (footprints.get(node.id)?.width || 80) + 30));
            const cellHeight = Math.max(94, ...group.map(node => {
                const footprint = footprints.get(node.id) || { height: 64, gap: 28 };
                return footprint.height + footprint.gap;
            }));
            const groupWidth = columns * columnWidth;
            const groupRows = Math.ceil(group.length / columns);
            const groupHeight = groupRows * cellHeight;
            if (groupIndex && groupIndex % 3 === 0) {
                cursorX = 0;
                cursorY += rowHeight + 160;
                rowHeight = 0;
            }
            group.forEach((node, index) => {
                node.x = cursorX + (index % columns) * columnWidth;
                node.y = cursorY + Math.floor(index / columns) * cellHeight;
            });
            cursorX += groupWidth + 160;
            rowHeight = Math.max(rowHeight, groupHeight);
        });
    }
}

cache=(()=>{return { KnowledgeGraphLayoutEngine: KnowledgeGraphLayoutEngine };})();return cache;};})();
const __brainExplorerModule29=(()=>{let cache;return()=>{if(cache)return cache;
const { StructureTree } = __brainExplorerModule9();
const { KnowledgeCanvasInteractionController } = __brainExplorerModule30();
/**
 * Coordinates Knowledge source-tree selection, actions, and navigation.
 */


/**
 * Source-tree interaction controller layered above canvas behavior.
 */
class KnowledgeTreeInteractionController extends KnowledgeCanvasInteractionController {
    /**
     * Configure the shared structure tree with Knowledge nodes and action handlers.
     */
    configureDomainTree() {
        const treeElement = this.querySelector("[data-role='knowledge-domain-tree']");
        if (!(treeElement instanceof StructureTree)) {
            return;
        }
        treeElement.model = {
            nodes: this.domainTreeNodes,
            selectedPath: this.selectedTreePath,
            expandedPaths: this.expandedDomains,
            toggleOnBranchSelect: true,
            title: "Knowledge",
            toolbarActions: [
                { id: "refresh-graph", label: "Refresh graph", icon: "refresh" },
                { id: "review-deltas", label: "Review deltas", icon: "graph" },
                { id: "fit-graph", label: "Fit canvas", icon: "filter" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "document"
        };
        treeElement.addEventListener("brain-tree-select", event => this.onDomainTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.onDomainTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.onDomainTreeAction(event));
    }
    /**
     * Scope the graph to a selected domain.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    onDomainTreeSelected(event) {
        if (!(event instanceof CustomEvent))
            return;
        const node = event.detail.node || {};
        this.selectedTreePath = String(node.path || "");
        this.treeScope = node.scope === "global" || node.scope === "local" ? node.scope : "all";
        this.domain = String(node.domain || "all");
        this.sourceKind = node.sourceKind === "memory" || node.sourceKind === "pictures"
            || node.sourceKind === "messages" || node.sourceKind === "logs" ? node.sourceKind : "";
        this.treeVisualType = node.visualType === "class" || node.visualType === "entity" ? node.visualType : "";
        this.sourcePath = String(node.sourcePath || "");
        this.applyTreeSelection();
    }
    /**
     * Run one global Knowledge tree action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    onDomainTreeToolbarAction(event) {
        if (!(event instanceof CustomEvent))
            return;
        if (event.detail.action === "refresh-graph") {
            this.showRecords(true);
        }
        else if (event.detail.action === "review-deltas") {
            this.reviewDeltas();
        }
        else if (event.detail.action === "fit-graph") {
            this.needsViewportFit = true;
            this.drawCanvas();
        }
    }
    /**
     * Scope the graph from a domain contextual action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    onDomainTreeAction(event) {
        if (!(event instanceof CustomEvent))
            return;
        if (!event.detail.node?.path) {
            return;
        }
        if (event.detail.action === "filter-source") {
            this.selectedTreePath = String(event.detail.node.path);
            this.treeScope = event.detail.node.scope === "global" || event.detail.node.scope === "local" ? event.detail.node.scope : "all";
            this.domain = String(event.detail.node.domain || "all");
            const sourceKind = event.detail.node.sourceKind;
            this.sourceKind = sourceKind === "memory" || sourceKind === "pictures"
                || sourceKind === "messages" || sourceKind === "logs" ? sourceKind : "";
            this.treeVisualType = event.detail.node.visualType === "class" || event.detail.node.visualType === "entity" ? event.detail.node.visualType : "";
            this.sourcePath = String(event.detail.node.sourcePath || "");
            this.applyTreeSelection();
            return;
        }
        if (event.detail.action === "open-source" && event.detail.node.openRoute) {
            this.state?.setRouteTarget?.(event.detail.node.openRoute, event.detail.node.openTarget || {});
            return;
        }
        if (event.detail.action === "consolidate-source") {
            this.reviewDeltas();
        }
    }
    /**
     * Render recursive domain rows.
     *
     * @param {object[]} nodes Domain nodes.
     * @param {number} depth Tree depth.
     * @param {string} filter Text filter.
     * @returns {string} HTML.
     */
    scheduleInitialLoad() {
        if (!this.api || this.loadScheduled || this.output) {
            return;
        }
        this.loadScheduled = true;
        queueMicrotask(() => this.showRecords());
    }
    /**
     * List graph records for the current scope and view.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after list call.
     */
    async showRecords(forceRefresh = false) {
        if (!this.api) {
            return;
        }
        this.beginGraphBusy(forceRefresh ? "Refreshing graph" : "Loading graph");
        try {
            this.readControls();
            const [result, memoryResult, pictureResult, messageResult, logResult] = await Promise.all([
                this.api.knowledgeShow({ scope: "all", mode: "all" }, { forceRefresh }),
                this.api.memoryTree({ forceRefresh }),
                this.api.pictures({}, { forceRefresh }),
                this.api.getVoiceMessages({ all: "true" }, { forceRefresh, silent: true }),
                this.api.logIndex({}, { forceRefresh, silent: true })
            ]);
            this.state?.setLastResult(result);
            this.output = result;
            this.memoryPaths = Array.isArray(memoryResult.data) ? memoryResult.data.map(path => String(path)) : [];
            this.pictures = Array.isArray(pictureResult.data?.pictures) ? pictureResult.data.pictures : [];
            this.messages = Array.isArray(messageResult.data?.history) ? messageResult.data.history : [];
            this.messageSessions = Array.isArray(messageResult.data?.sessions) ? messageResult.data.sessions : [];
            this.logEntries = Array.isArray(logResult.data?.entries) ? logResult.data.entries : [];
            this.ingestGraph(result.data);
            this.render();
            this.resolvePendingEntity();
        }
        finally {
            this.endGraphBusy();
        }
    }
    /**
     * Search graph records.
     *
     * @returns {Promise<void>} Resolves after query call.
     */
    async queryRecords() {
        if (!this.api) {
            return;
        }
        this.readControls();
        if (!this.query) {
            await this.applyFilters();
            return;
        }
        this.beginGraphBusy("Searching graph");
        try {
            const result = await this.api.knowledgeQuery({
                q: this.query,
                scope: this.scope,
                limit: "120",
                explain: "true"
            });
            this.state?.setLastResult(result);
            this.output = result;
            this.ingestGraph(result.data);
            this.render();
        }
        finally {
            this.endGraphBusy();
        }
    }
    /**
     * Load pending delta review.
     *
     * @returns {Promise<void>} Resolves after delta review.
     */
    async reviewDeltas() {
        if (!this.api) {
            return;
        }
        this.beginGraphBusy("Reviewing graph deltas");
        try {
            this.readControls();
            const result = await this.api.knowledgeDeltas({
                scope: this.scope,
                limit: "80",
                status: "pending"
            }, { forceRefresh: true });
            this.state?.setLastResult(result);
            this.output = result;
            this.ingestGraph(result.data);
            this.render();
        }
        finally {
            this.endGraphBusy();
        }
    }
}

cache=(()=>{return { KnowledgeTreeInteractionController: KnowledgeTreeInteractionController };})();return cache;};})();
const __brainExplorerModule30=(()=>{let cache;return()=>{if(cache)return cache;
const { pointToSegmentDistance } = __brainExplorerModule31();
const { KnowledgeCanvasRenderer } = __brainExplorerModule32();
/**
 * Controls Knowledge canvas pointer, camera, selection, and hit-testing behavior.
 */


/**
 * Interaction controller proxied by the concrete Knowledge layout.
 */
class KnowledgeCanvasInteractionController extends KnowledgeCanvasRenderer {
    /**
     * Begin node dragging, region navigation, relation selection, or canvas panning.      * @param {PointerEvent} event The event value used by this operation.
     * @param {HTMLCanvasElement} canvas The canvas value used by this operation.
     */
    onPointerDown(event, canvas) {
        const point = this.canvasPoint(event, canvas);
        const expansionNode = this.hitTestNodeExpansionBadge(point.x, point.y);
        if (expansionNode) {
            event.preventDefault();
            this.navigateGraphRegion(expansionNode.id);
            return;
        }
        const labelNode = this.hitTestNodeLabel(point.x, point.y);
        if (labelNode) {
            event.preventDefault();
            this.focusNode(labelNode.id);
            return;
        }
        const labelEdge = this.hitTestEdgeLabel(point.x, point.y);
        if (labelEdge) {
            this.selectRelation(labelEdge.id);
            return;
        }
        const node = this.hitTestNode(point.x, point.y);
        const edge = this.hitTestEdge(point.x, point.y);
        if (edge && (!node || !this.nodeOwnsPoint(node, point.x, point.y))) {
            this.selectRelation(edge.id);
            return;
        }
        if (node) {
            this.pointerCandidate = {
                id: node.id,
                pointerId: event.pointerId,
                clientX: event.clientX,
                clientY: event.clientY,
                offsetX: point.x - node.x,
                offsetY: point.y - node.y,
                moved: false
            };
            canvas.setPointerCapture(event.pointerId);
            return;
        }
        if (edge) {
            this.selectRelation(edge.id);
            return;
        }
        if (this.selectedNodeId || this.selectedRelationId) {
            this.selectedNodeId = "";
            this.selectedRelationId = "";
            this.restoreFocusViewport();
            this.renderInspector();
            return;
        }
        this.panState = {
            pointerId: event.pointerId,
            clientX: event.clientX,
            clientY: event.clientY,
            startX: this.viewport.x,
            startY: this.viewport.y
        };
        cancelAnimationFrame(this.cameraAnimationFrame);
        this.cameraAnimationFrame = 0;
        canvas.setPointerCapture(event.pointerId);
    }
    /**
     * Smoothly center one node while optionally changing the camera scale.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     * @param {number} targetScale The target scale value used by this operation.
     */
    animateCameraToNode(node, targetScale) {
        this.animateViewport({
            x: -node.x * targetScale,
            y: -node.y * targetScale,
            scale: targetScale
        });
    }
    /**
     * Smoothly center one relation midpoint while optionally changing camera scale.      * @param {KnowledgeGraphEdge} relation The relation value used by this operation.
     * @param {number} targetScale The target scale value used by this operation.
     */
    animateCameraToRelation(relation, targetScale) {
        const source = this.nodes.find(node => node.id === relation.from);
        const target = this.nodes.find(node => node.id === relation.to);
        if (!source || !target) {
            return;
        }
        this.animateViewport({
            x: -((source.x + target.x) / 2) * targetScale,
            y: -((source.y + target.y) / 2) * targetScale,
            scale: targetScale
        });
    }
    /**
     * Animate from the current camera to one exact viewport.
     *
     * @param {{x: number, y: number, scale: number}} target Destination camera.
     * @param {(() => void)|null} onComplete Callback after the final rendered frame.
     * @returns {void}
     */
    animateViewport(target, onComplete = null) {
        cancelAnimationFrame(this.cameraAnimationFrame);
        this.needsViewportFit = false;
        const start = { ...this.viewport };
        const startedAt = performance.now();
        const duration = 420;
        const animate = (now) => {
            const progress = Math.max(0, Math.min(1, (now - startedAt) / duration));
            const eased = 1 - Math.pow(1 - progress, 3);
            this.viewport = {
                x: start.x + (target.x - start.x) * eased,
                y: start.y + (target.y - start.y) * eased,
                scale: start.scale + (target.scale - start.scale) * eased
            };
            this.drawCanvas();
            if (progress < 1) {
                this.cameraAnimationFrame = requestAnimationFrame(animate);
            }
            else {
                this.cameraAnimationFrame = 0;
                onComplete?.();
            }
        };
        this.cameraAnimationFrame = requestAnimationFrame(animate);
    }
    /**
     * Focus one node while preserving the camera that preceded the focus zoom.      * @param {string} nodeId The node id value used by this operation.
     */
    focusNode(nodeId) {
        const node = this.nodes.find(item => item.id === nodeId);
        if (!node) {
            return;
        }
        const hadRegion = this.regionNodeIds.size > 0;
        if (!this.selectedNodeId) {
            this.focusViewport = this.badgeHoverViewport
                ? { ...this.badgeHoverViewport }
                : { ...this.viewport };
        }
        this.badgeHoverViewport = null;
        this.viewportBadgeRankingFrozen = false;
        this.hoveredNodeId = "";
        this.selectedNodeId = node.id;
        this.selectedRelationId = "";
        this.animateCameraToNode(node, hadRegion ? this.viewport.scale : Math.max(this.viewport.scale, 1.35));
        this.renderInspector();
    }
    /**
     * Select and center one relation without mutating the graph region.      * @param {string} relationId The relation id value used by this operation.
     */
    selectRelation(relationId) {
        const relation = this.edges.find(edge => edge.id === relationId);
        if (!relation) {
            return;
        }
        if (!this.selectedNodeId && !this.selectedRelationId) {
            this.focusViewport = this.relationHoverViewport
                ? { ...this.relationHoverViewport }
                : { ...this.viewport };
        }
        this.selectedRelationId = relationId;
        this.selectedNodeId = "";
        this.hoveredRelationId = "";
        this.hoveredNodeId = "";
        this.relationHoverViewport = null;
        this.badgeHoverViewport = null;
        this.viewportBadgeRankingFrozen = false;
        this.animateCameraToRelation(relation, Math.max(this.viewport.scale, 1.35));
        this.renderInspector();
    }
    /**
     * Restore the camera snapshot captured immediately before entity focus.
     */
    restoreFocusViewport() {
        if (!this.focusViewport) {
            this.drawCanvas();
            return;
        }
        const previousViewport = this.focusViewport;
        this.focusViewport = null;
        this.animateViewport(previousViewport);
    }
    /**
     * Move a dragged node or pan the graph.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    onPointerMove(event, canvas) {
        if (this.pointerCandidate && !this.dragNode) {
            const distance = Math.hypot(event.clientX - this.pointerCandidate.clientX, event.clientY - this.pointerCandidate.clientY);
            if (distance >= 4) {
                this.pointerCandidate.moved = true;
                this.dragNode = {
                    id: this.pointerCandidate.id,
                    offsetX: this.pointerCandidate.offsetX,
                    offsetY: this.pointerCandidate.offsetY
                };
            }
        }
        if (this.dragNode) {
            const point = this.canvasPoint(event, canvas);
            const dragNode = this.dragNode;
            const node = this.nodes.find(item => item.id === dragNode.id);
            if (!node) {
                return;
            }
            node.x = point.x - dragNode.offsetX;
            node.y = point.y - dragNode.offsetY;
            if (this.regionNodeIds.has(node.id)) {
                this.regionPositions.set(node.id, { x: node.x, y: node.y });
            }
            this.drawCanvas();
            return;
        }
        if (!this.panState) {
            return;
        }
        this.viewport.x = this.panState.startX + (event.clientX - this.panState.clientX);
        this.viewport.y = this.panState.startY + (event.clientY - this.panState.clientY);
        this.drawCanvas();
    }
    /**
     * End dragging or panning.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    onPointerUp(event, canvas) {
        const candidate = this.pointerCandidate;
        if (candidate && !candidate.moved) {
            this.focusNode(candidate.id);
        }
        this.pointerCandidate = null;
        this.dragNode = null;
        this.panState = null;
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
    onWheel(event, canvas) {
        event.preventDefault();
        cancelAnimationFrame(this.cameraAnimationFrame);
        this.cameraAnimationFrame = 0;
        const rect = canvas.getBoundingClientRect();
        const cursorX = event.clientX - rect.left - rect.width / 2;
        const cursorY = event.clientY - rect.top - rect.height / 2;
        const previousScale = this.viewport.scale;
        const nextScale = Math.min(3.4, Math.max(0.005, previousScale * (event.deltaY > 0 ? 0.9 : 1.1)));
        const graphX = (cursorX - this.viewport.x) / previousScale;
        const graphY = (cursorY - this.viewport.y) / previousScale;
        this.viewport.x = cursorX - graphX * nextScale;
        this.viewport.y = cursorY - graphY * nextScale;
        this.viewport.scale = nextScale;
        this.needsViewportFit = false;
        this.drawCanvas();
    }
    /**
     * Refresh the inspector without replacing the canvas.
     *
     * @returns {void}
     */
    renderInspector() {
        const inspector = this.querySelector(".graph-detail-list");
        if (!inspector) {
            return;
        }
        inspector.innerHTML = this.renderDetails();
        const relationPreviewHost = this.querySelector("[data-role='relation-preview-host']");
        if (relationPreviewHost) {
            relationPreviewHost.innerHTML = this.renderRelationPreview();
        }
        const backButton = this.querySelector("[data-action='navigate-region-back']");
        if (backButton) {
            if (backButton instanceof HTMLElement)
                backButton.hidden = !this.regionHistory.length;
        }
        this.bindInspectorButtons();
    }
    /**
     * Reset camera zoom and center while preserving the current graph or subregion.
     */
    resetVisibleGraphViewport() {
        cancelAnimationFrame(this.cameraAnimationFrame);
        this.cameraAnimationFrame = 0;
        this.hoveredNodeId = "";
        this.hoveredRelationId = "";
        this.relationHoverViewport = null;
        this.badgeHoverViewport = null;
        const canvas = this.querySelector("[data-role='knowledge-canvas']");
        if (!(canvas instanceof HTMLCanvasElement))
            return;
        this.viewportBadgeRankingFrozen = true;
        this.needsViewportFit = false;
        const target = this.fittedViewport(canvas.getBoundingClientRect());
        this.animateViewport(target, () => this.releaseViewportBadgeRanking());
        this.renderInspector();
    }
    /**
     * Clear persistent region state without rendering.
     */
    resetGraphRegion() {
        this.selectedNodeId = "";
        this.selectedRelationId = "";
        this.hoveredNodeId = "";
        this.hoveredRelationId = "";
        this.regionNodeIds.clear();
        this.regionEdgeIds.clear();
        this.regionPositions.clear();
        this.regionHistory = [];
        this.regionRootNodeId = "";
        this.focusViewport = null;
        this.relationHoverViewport = null;
        this.badgeHoverViewport = null;
        this.viewportBadgeRankingFrozen = false;
    }
    /**
     * Convert viewport pointer coordinates into graph coordinates.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {{x: number, y: number}} Graph point.
     */
    canvasPoint(event, canvas) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: (event.clientX - rect.left - rect.width / 2 - this.viewport.x) / this.viewport.scale,
            y: (event.clientY - rect.top - rect.height / 2 - this.viewport.y) / this.viewport.scale
        };
    }
    /**
     * Find a node under graph coordinates.
     *
     * @param {number} x Graph x.
     * @param {number} y Graph y.
     * @returns {object|null} Hit node.
     */
    hitTestNode(x, y) {
        const focus = this.focusGraph();
        const candidates = focus ? this.nodes.filter(node => focus.nodeIds.has(node.id)) : this.nodes;
        return [...candidates].reverse().find(node => {
            const dx = node.x - x;
            const dy = node.y - y;
            return Math.sqrt((dx * dx) + (dy * dy)) <= node.radius + (16 / this.viewport.scale);
        }) || null;
    }
    /**
     * Find the selected node whose explicit child-region affordance contains a point.      * @param {number} x The x value used by this operation.
     * @param {number} y The y value used by this operation.
     *
     * @returns {KnowledgeGraphNode | null} The KnowledgeGraphNode associated with the hit badge, or null if no intersection occurs or the node is not expandable.
     */
    hitTestNodeExpansionBadge(x, y) {
        if (!this.selectedNodeId || !this.nodeCanExpand(this.selectedNodeId))
            return null;
        const node = this.nodes.find(item => item.id === this.selectedNodeId);
        if (!node || (this.regionNodeIds.size && !this.regionNodeIds.has(node.id)))
            return null;
        const badgeX = node.x + node.radius * 0.72;
        const badgeY = node.y - node.radius * 0.72;
        const hitRadius = 13 / this.viewport.scale;
        return Math.hypot(x - badgeX, y - badgeY) <= hitRadius ? node : null;
    }
    /**
     * Resolve ranked node-label rectangles before relation labels and node hit halos.      * @param {number} x The x value used by this operation.
     * @param {number} y The y value used by this operation.
     *
     * @returns {KnowledgeGraphNode | null} The KnowledgeGraphNode associated with the intersected label, or null if no label was hit.
     */
    hitTestNodeLabel(x, y) {
        const padding = 5 / Math.max(this.viewport.scale, 0.005);
        for (const [nodeId, bounds] of [...this.nodeLabelBounds.entries()].reverse()) {
            if (x < bounds.left - padding || x > bounds.right + padding
                || y < bounds.top - padding || y > bounds.bottom + padding)
                continue;
            return this.nodes.find(node => node.id === nodeId) || null;
        }
        return null;
    }
    /**
     * Return whether a point belongs to the visible node body rather than its generous hit halo.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     * @param {number} x The x value used by this operation.
     * @param {number} y The y value used by this operation.
     *
     * @returns {boolean} True if the point is within the node's expanded boundary; otherwise, false.
     */
    nodeOwnsPoint(node, x, y) {
        return Math.hypot(node.x - x, node.y - y) <= node.radius + (4 / this.viewport.scale);
    }
    /**
     * Find a relation whose rendered label rectangle contains graph coordinates.      * @param {number} x The x value used by this operation.
     * @param {number} y The y value used by this operation.
     *
     * @returns {KnowledgeGraphEdge | null} The KnowledgeGraphEdge associated with the intersected label, or null if no intersection is found.
     */
    hitTestEdgeLabel(x, y) {
        const focus = this.focusGraph();
        const candidates = focus ? this.edges.filter(edge => focus.edgeIds.has(edge.id)) : this.edges;
        const padding = 4 / this.viewport.scale;
        return [...candidates].reverse().find(edge => {
            const bounds = this.edgeLabelBounds.get(edge.id);
            return bounds
                && x >= bounds.left - padding
                && x <= bounds.right + padding
                && y >= bounds.top - padding
                && y <= bounds.bottom + padding;
        }) || null;
    }
    /**
     * Find an edge near graph coordinates.
     *
     * @param {number} x Graph x.
     * @param {number} y Graph y.
     * @returns {object|null} Hit edge.
     */
    hitTestEdge(x, y) {
        const focus = this.focusGraph();
        const candidates = focus ? this.edges.filter(edge => focus.edgeIds.has(edge.id)) : this.edges;
        return [...candidates].reverse().find(edge => {
            const from = this.nodes.find(node => node.id === edge.from);
            const to = this.nodes.find(node => node.id === edge.to);
            if (!from || !to) {
                return false;
            }
            return pointToSegmentDistance(x, y, from.x, from.y, to.x, to.y) <= 7 / this.viewport.scale;
        }) || null;
    }
    /**
     * Bind page, filter, inspector, and graph action events after a full render.
     */
    bindEvents() {
        this.querySelector("[data-action='show-records']")?.addEventListener("click", () => this.showRecords(true));
        this.querySelector("[data-action='query-records']")?.addEventListener("click", () => this.queryRecords());
        this.querySelector("[data-action='review-deltas']")?.addEventListener("click", () => this.reviewDeltas());
        this.querySelector("[data-action='fit-graph']")?.addEventListener("click", () => {
            this.resetVisibleGraphViewport();
        });
        this.querySelector("[data-action='navigate-region-back']")?.addEventListener("click", () => {
            this.navigateBackGraphRegion();
        });
        this.querySelector(".filter-menu")?.addEventListener("toggle", event => {
            if (event.currentTarget instanceof HTMLDetailsElement) {
                this.filtersOpen = event.currentTarget.open;
            }
        });
        this.querySelectorAll("[data-action='select-domain']").forEach(button => {
            button.addEventListener("click", () => {
                const domain = button.getAttribute("data-domain-path") || "all";
                this.domain = domain;
                this.resetGraphRegion();
                if (this.expandedDomains.has(domain)) {
                    this.expandedDomains.delete(domain);
                }
                else {
                    this.expandedDomains.add(domain);
                }
                this.applyFilters();
            });
        });
        this.querySelector("[data-role='kg-query']")?.addEventListener("input", () => {
            this.readControls();
            this.needsViewportFit = true;
            this.prepareGraph();
            this.drawCanvas();
            this.renderInspector();
        });
        this.querySelector("[data-role='kg-query']")?.addEventListener("keydown", event => {
            if (event instanceof KeyboardEvent && event.key === "Enter") {
                this.queryRecords();
            }
        });
        this.querySelectorAll("[data-filter-kind='kg-scope']").forEach(input => {
            input.addEventListener("change", () => this.applyFilters());
        });
        this.querySelectorAll("[data-filter-kind='kg-mode']").forEach(input => {
            input.addEventListener("change", () => this.applyFilters());
        });
        this.bindInspectorButtons();
    }
    /**
     * Bind inspector relation/node selection buttons.
     *
     * @returns {void}
     */
    bindInspectorButtons() {
        this.querySelectorAll("[data-action='open-detail-source']").forEach(button => {
            button.addEventListener("click", () => {
                const route = button.getAttribute("data-route") || "";
                if (route === "pictures") {
                    this.state?.setRouteTarget?.("pictures", { pictureId: button.getAttribute("data-picture-id") || "" });
                    return;
                }
                const messageId = button.getAttribute("data-message-id") || "";
                const message = this.messages.find(item => String(item.id) === messageId);
                const session = this.messageSessions.find(item => item.date === message?.date && item.chatId === message?.chat_id);
                this.state?.setRouteTarget?.("messages", { messageId, sessionId: session?.id || "" });
            });
        });
        this.querySelectorAll("[data-action='focus-node']").forEach(button => {
            button.addEventListener("pointerenter", () => {
                this.showHoveredEndpoint(button.getAttribute("data-node-id") || "");
            });
            button.addEventListener("pointerleave", () => this.showHoveredEndpoint(""));
            button.addEventListener("click", () => this.focusNode(button.getAttribute("data-node-id") || ""));
        });
        this.querySelectorAll("[data-action='resolve-description-entity']").forEach(button => {
            button.addEventListener("click", () => this.focusEntityByLabel(button.getAttribute("data-entity-label") || ""));
        });
        this.querySelectorAll("[data-action='select-node']").forEach(button => {
            button.addEventListener("click", () => {
                this.focusNode(button.getAttribute("data-node-id") || "");
            });
        });
        this.querySelectorAll("[data-action='select-relation']").forEach(button => {
            button.addEventListener("pointerenter", () => {
                this.showHoveredRelation(button.getAttribute("data-relation-id") || "");
            });
            button.addEventListener("pointerleave", () => {
                this.showHoveredRelation("");
            });
            button.addEventListener("click", () => {
                this.selectRelation(button.getAttribute("data-relation-id") || "");
            });
        });
        this.bindRelationEndpointButtons();
    }
    /**
     * Bind transient and persistent navigation on relation endpoint badges.
     */
    bindRelationEndpointButtons() {
        this.querySelectorAll("[data-action='navigate-relation-endpoint']").forEach(button => {
            const nodeId = button.getAttribute("data-node-id") || "";
            button.addEventListener("pointerenter", () => this.showHoveredEndpoint(nodeId));
            button.addEventListener("pointerleave", () => this.showHoveredEndpoint(""));
            button.addEventListener("click", () => this.navigateRelationEndpoint(nodeId));
        });
    }
    /**
     * Update the existing relation preview and camera from one transient sidepanel hover.      * @param {string} relationId The relation id value used by this operation.
     */
    showHoveredRelation(relationId) {
        const relation = this.edges.find(edge => edge.id === relationId);
        if (relation) {
            if (!this.hoveredRelationId) {
                this.relationHoverViewport = { ...this.viewport };
            }
            this.hoveredRelationId = relation.id;
            this.hoveredNodeId = "";
            this.animateCameraToRelation(relation, Math.max(this.viewport.scale, 1.35));
        }
        else {
            this.hoveredRelationId = "";
            this.hoveredNodeId = "";
            if (this.relationHoverViewport) {
                const previousViewport = this.relationHoverViewport;
                this.relationHoverViewport = null;
                this.animateViewport(previousViewport);
            }
            else {
                this.drawCanvas();
            }
        }
        const relationPreviewHost = this.querySelector("[data-role='relation-preview-host']");
        if (relationPreviewHost) {
            relationPreviewHost.innerHTML = this.renderRelationPreview();
        }
        this.bindRelationEndpointButtons();
    }
    /**
     * Preview one endpoint node while preserving the camera that preceded badge hover.      * @param {string} nodeId The node id value used by this operation.
     */
    showHoveredEndpoint(nodeId) {
        const node = this.nodes.find(item => item.id === nodeId);
        if (node) {
            if (!this.hoveredNodeId) {
                this.badgeHoverViewport = { ...this.viewport };
            }
            this.viewportBadgeRankingFrozen = true;
            clearTimeout(this.viewportInspectorTimer);
            this.hoveredNodeId = node.id;
            this.animateCameraToNode(node, Math.max(this.viewport.scale, 1.35));
            return;
        }
        this.hoveredNodeId = "";
        if (this.badgeHoverViewport) {
            const previousViewport = this.badgeHoverViewport;
            this.badgeHoverViewport = null;
            this.animateViewport(previousViewport, () => this.releaseViewportBadgeRanking());
        }
        else {
            this.releaseViewportBadgeRanking();
            this.drawCanvas();
        }
    }
    /**
     * Resume viewport-driven badge ranking after a transient entity preview fully returns.
     */
    releaseViewportBadgeRanking() {
        this.viewportBadgeRankingFrozen = false;
        this.syncViewportBadgeCandidates();
    }
    /**
     * Persist camera navigation to one relation endpoint without replacing relation selection.      * @param {string} nodeId The node id value used by this operation.
     */
    navigateRelationEndpoint(nodeId) {
        const node = this.nodes.find(item => item.id === nodeId);
        if (!node) {
            return;
        }
        this.badgeHoverViewport = null;
        this.viewportBadgeRankingFrozen = false;
        this.hoveredNodeId = node.id;
        this.animateCameraToNode(node, Math.max(this.viewport.scale, 1.35));
    }
    /**
     * Resolve one description badge to the most connected matching graph node.      * @param {string} label The label value used by this operation.
     *
     * @returns {boolean} True if a matching node was found and focused, otherwise false.
     */
    focusEntityByLabel(label) {
        const normalized = String(label || "").trim().toLowerCase();
        if (!normalized)
            return false;
        const degrees = this.nodeDegrees();
        const match = this.nodes
            .filter(node => String(node.label || "").trim().toLowerCase() === normalized)
            .sort((left, right) => (degrees.get(right.id) || 0) - (degrees.get(left.id) || 0))[0];
        if (!match)
            return false;
        this.focusNode(match.id);
        return true;
    }
    /**
     * Focus a route-targeted entity after the graph has been prepared.
     */
    resolvePendingEntity() {
        if (!this.pendingEntityLabel)
            return;
        const label = this.pendingEntityLabel;
        if (this.focusEntityByLabel(label))
            this.pendingEntityLabel = "";
    }
}

cache=(()=>{return { KnowledgeCanvasInteractionController: KnowledgeCanvasInteractionController };})();return cache;};})();
const __brainExplorerModule31=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Calculate the shortest Euclidean distance between a point and a finite segment.
 * Degenerate segments are treated as a single endpoint so callers never divide by
 * zero. The function is coordinate-system agnostic and has no canvas dependency.
 *
 * @param {number} pointX Horizontal coordinate of the tested point.
 * @param {number} pointY Vertical coordinate of the tested point.
 * @param {number} startX Horizontal coordinate of the segment start.
 * @param {number} startY Vertical coordinate of the segment start.
 * @param {number} endX Horizontal coordinate of the segment end.
 * @param {number} endY Vertical coordinate of the segment end.
 * @returns {number} Shortest distance in the same units as the supplied coordinates.
 */
function pointToSegmentDistance(pointX, pointY, startX, startY, endX, endY) {
    const deltaX = endX - startX;
    const deltaY = endY - startY;
    if (deltaX === 0 && deltaY === 0)
        return Math.hypot(pointX - startX, pointY - startY);
    const projection = (((pointX - startX) * deltaX) + ((pointY - startY) * deltaY))
        / ((deltaX * deltaX) + (deltaY * deltaY));
    const ratio = Math.max(0, Math.min(1, projection));
    return Math.hypot(pointX - (startX + ratio * deltaX), pointY - (startY + ratio * deltaY));
}

cache=(()=>{return { pointToSegmentDistance: pointToSegmentDistance };})();return cache;};})();
const __brainExplorerModule32=(()=>{let cache;return()=>{if(cache)return cache;
const { shortKnowledgeLabel } = __brainExplorerModule25();
const { pointToSegmentDistance } = __brainExplorerModule31();
const { KnowledgeCanvasState } = __brainExplorerModule33();
/**
 * Draws the Knowledge graph canvas while preserving the established visual contract.
 */



/**
 * Canvas renderer and graph-region presentation base.
 */
class KnowledgeCanvasRenderer extends KnowledgeCanvasState {
    /**
     * Bind the existing canvas element to resize and pointer lifecycle events.
     */
    bindCanvas() {
        const canvas = this.querySelector("[data-role='knowledge-canvas']");
        if (!(canvas instanceof HTMLCanvasElement)) {
            return;
        }
        this.resizeObserver?.disconnect();
        this.resizeObserver = new ResizeObserver(() => this.drawCanvas());
        this.resizeObserver.observe(canvas);
        canvas.addEventListener("pointerdown", event => this.onPointerDown(event, canvas));
        canvas.addEventListener("pointermove", event => this.onPointerMove(event, canvas));
        canvas.addEventListener("pointerup", event => this.onPointerUp(event, canvas));
        canvas.addEventListener("pointerleave", event => this.onPointerUp(event, canvas));
        canvas.addEventListener("wheel", event => this.onWheel(event, canvas), { passive: false });
        canvas.addEventListener("dblclick", event => {
            event.preventDefault();
            this.resetVisibleGraphViewport();
        });
        requestAnimationFrame(() => this.drawCanvas());
    }
    /**
     * Draw nodes and edges onto the canvas.
     *
     * @returns {void}
     */
    drawCanvas() {
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
        if (this.needsViewportFit) {
            this.fitViewport(rect);
        }
        this.updateRenderFrustum(rect);
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        context.clearRect(0, 0, rect.width, rect.height);
        this.applyConnectivitySizing(this.focusGraph());
        context.translate((rect.width / 2) + this.viewport.x, (rect.height / 2) + this.viewport.y);
        context.scale(this.viewport.scale, this.viewport.scale);
        this.drawEdges(context);
        this.drawNodes(context);
        this.syncViewportBadgeCandidates();
    }
    /**
     * Fit graph bounds into the canvas viewport.
     *
     * @param {DOMRect} rect Canvas bounds.
     * @returns {void}
     */
    fitViewport(rect) {
        this.viewport = this.fittedViewport(rect);
        this.needsViewportFit = false;
    }
    /**
     * Calculate the centered fit camera for the complete graph or active subregion.
     *
     * @param {DOMRect} rect Canvas bounds.
     * @returns {{x: number, y: number, scale: number}} Fitted camera.
     */
    fittedViewport(rect) {
        const focus = this.focusGraph();
        if (focus) {
            this.layoutFocusedRegion(focus);
        }
        const visibleNodes = focus
            ? this.nodes.filter(node => focus.nodeIds.has(node.id))
            : this.nodes;
        if (!visibleNodes.length) {
            return { x: 0, y: 0, scale: 1 };
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
        const scale = Math.min(maximumScale, Math.max(0.005, Math.min((rect.width - 72) / width, (rect.height - 72) / height)));
        return {
            x: -((bounds.minX + bounds.maxX) / 2) * scale,
            y: -((bounds.minY + bounds.maxY) / 2) * scale,
            scale
        };
    }
    /**
     * Compute the current canvas viewport in graph coordinates.      * @param {DOMRect} rect The rect value used by this operation.
     */
    updateRenderFrustum(rect) {
        const scale = Math.max(this.viewport.scale, 0.0001);
        const halfWidth = rect.width / (2 * scale);
        const halfHeight = rect.height / (2 * scale);
        const centerX = -this.viewport.x / scale;
        const centerY = -this.viewport.y / scale;
        const padding = 14 / scale;
        this.renderFrustum = {
            left: centerX - halfWidth - padding,
            right: centerX + halfWidth + padding,
            top: centerY - halfHeight - padding,
            bottom: centerY + halfHeight + padding,
            centerX,
            centerY,
            radius: Math.hypot(halfWidth, halfHeight) + padding
        };
    }
    /**
     * Return whether a node circle intersects the graph-space viewport.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     *
     * @returns {boolean} True if the node intersects the render frustum or if no frustum is defined; otherwise, false.
     */
    nodeIntersectsRenderFrustum(node) {
        const frustum = this.renderFrustum;
        if (!frustum) {
            return true;
        }
        const radius = node.radius + (20 / Math.max(this.viewport.scale, 0.0001));
        return node.x + radius >= frustum.left
            && node.x - radius <= frustum.right
            && node.y + radius >= frustum.top
            && node.y - radius <= frustum.bottom;
    }
    /**
     * Refresh important-entity candidates from the exact nodes intersecting the canvas viewport.
     */
    syncViewportBadgeCandidates() {
        if (this.viewportBadgeRankingFrozen)
            return;
        const focus = this.focusGraph();
        const candidates = focus
            ? this.nodes.filter(node => focus.nodeIds.has(node.id))
            : this.nodes;
        const visibleIds = candidates
            .filter(node => this.nodeIntersectsRenderFrustum(node))
            .map(node => node.id);
        const signature = visibleIds.join("|") || "__empty__";
        if (signature === this.viewportBadgeSignature) {
            return;
        }
        this.viewportNodeIds = new Set(visibleIds);
        this.viewportBadgeSignature = signature;
        clearTimeout(this.viewportInspectorTimer);
        this.viewportInspectorTimer = window.setTimeout(() => {
            if (!this.viewportBadgeRankingFrozen && !this.selectedNodeId && !this.selectedRelationId) {
                this.renderInspector();
            }
        }, 140);
    }
    /**
     * Apply endpoint, circumscribed-radius, and exact edge culling.      * @param {KnowledgeGraphNode} from The from value used by this operation.
     * @param {KnowledgeGraphNode} to The to value used by this operation.
     *
     * @returns {boolean} True if either endpoint is within the frustum or the edge segment intersects the frustum area; otherwise false.
     */
    edgeIntersectsRenderFrustum(from, to) {
        const frustum = this.renderFrustum;
        if (!frustum) {
            return true;
        }
        if (this.nodeIntersectsRenderFrustum(from) || this.nodeIntersectsRenderFrustum(to)) {
            return true;
        }
        const distance = pointToSegmentDistance(frustum.centerX, frustum.centerY, from.x, from.y, to.x, to.y);
        if (distance > frustum.radius) {
            return false;
        }
        return this.segmentIntersectsFrustum(from.x, from.y, to.x, to.y, frustum);
    }
    /**
     * Test a segment against an axis-aligned viewport using Liang-Barsky.      * @param {number} x1 The x1 value used by this operation.
     * @param {number} y1 The y1 value used by this operation.
     * @param {number} x2 The x2 value used by this operation.
     * @param {number} y2 The y2 value used by this operation.
     * @param {KnowledgeRenderFrustum} frustum The frustum value used by this operation.
     *
     * @returns {boolean} True if any part of the segment lies within the frustum boundaries, otherwise false.
     */
    segmentIntersectsFrustum(x1, y1, x2, y2, frustum) {
        const deltaX = x2 - x1;
        const deltaY = y2 - y1;
        const p = [-deltaX, deltaX, -deltaY, deltaY];
        const q = [x1 - frustum.left, frustum.right - x1, y1 - frustum.top, frustum.bottom - y1];
        let minimum = 0;
        let maximum = 1;
        for (let index = 0; index < 4; index += 1) {
            const pValue = p[index];
            const qValue = q[index];
            if (pValue === undefined || qValue === undefined)
                continue;
            if (pValue === 0) {
                if (qValue < 0) {
                    return false;
                }
                continue;
            }
            const ratio = qValue / pValue;
            if (pValue < 0) {
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
    layoutFocusedRegion(focus) {
        const focusedNodes = this.nodes.filter(node => focus.nodeIds.has(node.id));
        if (!focusedNodes.length) {
            return;
        }
        focusedNodes.forEach(node => {
            const position = this.regionPositions.get(node.id);
            if (position) {
                node.x = position.x;
                node.y = position.y;
            }
        });
        const newNodes = focusedNodes.filter(node => !this.regionPositions.has(node.id));
        if (!newNodes.length) {
            return;
        }
        const selectedPosition = this.regionPositions.get(this.selectedNodeId);
        const anchor = selectedPosition || this.regionCentroid();
        if (!this.regionPositions.size) {
            const selectedIndex = newNodes.findIndex(node => node.id === this.selectedNodeId);
            const centerIndex = selectedIndex >= 0 ? selectedIndex : 0;
            const center = newNodes.splice(centerIndex, 1)[0];
            if (!center)
                return;
            center.x = 0;
            center.y = 0;
            this.regionPositions.set(center.id, { x: 0, y: 0 });
        }
        const baseSlot = this.regionPositions.size;
        newNodes.forEach((node, index) => {
            const slot = baseSlot + index;
            const angle = (slot * 2.399963229728653) - (Math.PI / 2);
            const radius = 120 + (Math.floor(slot / 7) * 75);
            node.x = anchor.x + (Math.cos(angle) * radius);
            node.y = anchor.y + (Math.sin(angle) * radius);
            this.regionPositions.set(node.id, { x: node.x, y: node.y });
        });
    }
    /**
     * Return the centroid of persisted region positions.
     * @returns {KnowledgePoint} A KnowledgePoint representing the average x and y coordinates of the region, or a zeroed point if no positions exist.
     */
    regionCentroid() {
        const positions = [...this.regionPositions.values()];
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
    drawEdges(context) {
        this.edgeLabelBounds.clear();
        const styles = getComputedStyle(this);
        const focus = this.focusGraph();
        const orderedEdges = focus
            ? this.edges.filter(edge => focus.edgeIds.has(edge.id))
            : this.edges;
        const nodesById = new Map(this.nodes.map(node => [node.id, node]));
        const connectivity = this.connectivityMetrics(focus);
        orderedEdges.forEach(edge => {
            const from = nodesById.get(edge.from);
            const to = nodesById.get(edge.to);
            if (!from || !to || !this.edgeIntersectsRenderFrustum(from, to)) {
                return;
            }
            const activeRelationId = this.hoveredRelationId || this.selectedRelationId;
            const selected = edge.id === activeRelationId;
            context.save();
            context.globalAlpha = 0.92;
            context.beginPath();
            context.moveTo(from.x, from.y);
            context.lineTo(to.x, to.y);
            context.strokeStyle = selected ? styles.getPropertyValue("--primary").trim() : styles.getPropertyValue("--border-strong").trim();
            context.lineWidth = selected ? 3.2 / this.viewport.scale : 1.2 / this.viewport.scale;
            context.stroke();
            this.drawEdgeArrow(context, from, to, connectivity.score(from.id));
            this.drawEdgeLabel(context, edge, from, to, selected);
            context.restore();
        });
    }
    /**
     * Draw a subject-to-object arrowhead immediately before the target node.      * @param {CanvasRenderingContext2D} context The context value used by this operation.
     * @param {KnowledgeGraphNode} from The from value used by this operation.
     * @param {KnowledgeGraphNode} to The to value used by this operation.
     * @param {number} sourceRank The source rank value used by this operation.
     */
    drawEdgeArrow(context, from, to, sourceRank) {
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const distance = Math.hypot(dx, dy);
        if (distance < 1)
            return;
        const unitX = dx / distance;
        const unitY = dy / distance;
        const scale = this.viewport.scale;
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
    drawEdgeLabel(context, edge, from, to, selected) {
        if (!selected && this.viewport.scale < 0.45) {
            return;
        }
        const styles = getComputedStyle(this);
        const x = (from.x + to.x) / 2;
        const y = (from.y + to.y) / 2;
        const label = shortKnowledgeLabel(edge.label, selected ? 24 : 16);
        context.save();
        context.font = `${selected ? 700 : 650} ${10 / this.viewport.scale}px Inter, system-ui, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        const width = context.measureText(label).width + 12;
        const height = 18 / this.viewport.scale;
        this.edgeLabelBounds.set(edge.id, {
            left: x - width / 2,
            right: x + width / 2,
            top: y - height / 2,
            bottom: y + height / 2
        });
        context.fillStyle = styles.getPropertyValue("--surface").trim();
        context.strokeStyle = styles.getPropertyValue("--border").trim();
        this.roundedRect(context, x - width / 2, y - height / 2, width, height, 8 / this.viewport.scale);
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
    drawNodes(context) {
        this.nodeLabelBounds.clear();
        const styles = getComputedStyle(this);
        const focus = this.focusGraph();
        const activeRelationId = this.hoveredRelationId || this.selectedRelationId;
        const selectedRelation = this.edges.find(edge => edge.id === activeRelationId);
        const connectivity = this.connectivityMetrics(focus);
        const degrees = connectivity.degrees;
        const maxDegree = Math.max(0, ...degrees.values());
        const orderedNodes = focus
            ? this.nodes.filter(node => focus.nodeIds.has(node.id))
            : this.nodes;
        const visibleNodes = orderedNodes.filter(node => this.nodeIntersectsRenderFrustum(node));
        const rankedNodeIds = new Set(this.rankImportantNodes(visibleNodes).map(node => node.id));
        const rankedLabelBounds = [];
        visibleNodes.forEach(node => {
            const selected = node.id === this.selectedNodeId;
            const hovered = node.id === this.hoveredNodeId;
            const ranked = rankedNodeIds.has(node.id);
            const relationEndpoint = selectedRelation?.from === node.id || selectedRelation?.to === node.id;
            const focused = selected || hovered || relationEndpoint || Boolean(focus?.nodeIds.has(node.id));
            const radius = selected || hovered ? node.radius + 5 : relationEndpoint ? node.radius + 4 : focused ? node.radius + 2 : node.radius;
            context.save();
            context.globalAlpha = 1;
            context.beginPath();
            context.arc(node.x, node.y, radius, 0, Math.PI * 2);
            context.fillStyle = selected || hovered || relationEndpoint
                ? styles.getPropertyValue("--primary").trim()
                : styles.getPropertyValue("--surface-strong").trim();
            context.strokeStyle = node.color;
            context.lineWidth = selected || hovered || relationEndpoint
                ? 3.4 / this.viewport.scale
                : focused ? 2.6 / this.viewport.scale : 1.8 / this.viewport.scale;
            context.setLineDash(node.visualType === "class" ? [7 / this.viewport.scale, 5 / this.viewport.scale] : []);
            context.fill();
            context.stroke();
            if (this.nodeLabelIsVisible(node, degrees, maxDegree, selected || focused, ranked)) {
                this.drawNodeLabel(context, node, selected || focused, ranked, rankedLabelBounds);
            }
            if (selected && this.nodeCanExpand(node.id)) {
                this.drawNodeExpansionBadge(context, node);
            }
            context.restore();
        });
    }
    /**
     * Return the number of visible relations incident to each node.      * @param {KnowledgeGraphFocus | null} focus The focus value used by this operation.
     *
     * @returns {Map<string, number>} A map associating each visible node identifier with its total number of incident edges.
     */
    nodeDegrees(focus = null) {
        const visibleNodeIds = focus?.nodeIds || new Set(this.nodes.map(node => node.id));
        const degrees = new Map([...visibleNodeIds].map(nodeId => [nodeId, 0]));
        this.edges.forEach(edge => {
            if (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to)) {
                return;
            }
            degrees.set(edge.from, (degrees.get(edge.from) || 0) + 1);
            degrees.set(edge.to, (degrees.get(edge.to) || 0) + 1);
        });
        return degrees;
    }
    /**
     * Return connectivity normalized against the maximum of the visible graph.      * @param {KnowledgeGraphFocus | null} focus The focus value used by this operation.
     *
     * @returns {KnowledgeConnectivityMetrics} An object containing the raw node degrees, the maximum degree found, and a function to retrieve a normalized connectivity score for a specific node.
     */
    connectivityMetrics(focus = this.focusGraph()) {
        const degrees = this.nodeDegrees(focus);
        const maxDegree = Math.max(1, ...degrees.values());
        return {
            degrees,
            maxDegree,
            score: (nodeId) => (degrees.get(nodeId) || 0) / maxDegree
        };
    }
    /**
     * Scale node radii by connectivity while preserving readable bounds.      * @param {KnowledgeGraphFocus | null} focus The focus value used by this operation.
     */
    applyConnectivitySizing(focus = null) {
        const connectivity = this.connectivityMetrics(focus);
        const baseRadius = this.mode === "classes" ? 14 : 10;
        const radiusRange = this.mode === "classes" ? 16 : 13;
        this.nodes.forEach(node => {
            const normalized = Math.sqrt(connectivity.score(node.id));
            node.radius = baseRadius + normalized * radiusRange;
        });
    }
    /**
     * Decide whether a label belongs to the zoom-dependent connectivity tier.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     * @param {Map<string, number>} degrees The degrees value used by this operation.
     * @param {number} maxDegree The max degree value used by this operation.
     * @param {boolean} emphasized The emphasized value used by this operation.
     * @param {boolean} ranked The ranked value used by this operation.
     *
     * @returns {boolean} A boolean indicating if the node label meets the visibility criteria.
     */
    nodeLabelIsVisible(node, degrees, maxDegree, emphasized, ranked = false) {
        if (emphasized || ranked || this.viewport.scale >= 0.78) {
            return true;
        }
        const normalizedRank = maxDegree ? (degrees.get(node.id) || 0) / maxDegree : 0;
        const zoomProgress = Math.max(0, Math.min(1, (this.viewport.scale - 0.005) / 0.775));
        const easedTolerance = zoomProgress * zoomProgress * (3 - (2 * zoomProgress));
        const minimumRank = 0.56 * (1 - easedTolerance);
        return normalizedRank >= minimumRank;
    }
    /**
     * Return the current selected node/relation neighborhood.
     *
     * @returns {{nodeIds: Set<string>, edgeIds: Set<string>}|null} Focus ids.
     */
    focusGraph() {
        if (!this.regionNodeIds.size) {
            return null;
        }
        return {
            nodeIds: this.regionNodeIds,
            edgeIds: this.regionEdgeIds
        };
    }
    /**
     * Return whether a node can become the root of a distinct child region.      * @param {string} nodeId The node id value used by this operation.
     *
     * @returns {boolean} True if the node has children and is not already fully expanded within the current region; otherwise, false.
     */
    nodeCanExpand(nodeId) {
        const child = this.graphRegionForNode(nodeId);
        if (!child.edgeIds.size)
            return false;
        if (!this.regionNodeIds.size)
            return true;
        return child.nodeIds.size !== this.regionNodeIds.size
            || [...child.nodeIds].some(id => !this.regionNodeIds.has(id));
    }
    /**
     * Draw a screen-stable expansion affordance above a selected node.      * @param {CanvasRenderingContext2D} context The context value used by this operation.
     * @param {KnowledgeGraphNode} node The node value used by this operation.
     */
    drawNodeExpansionBadge(context, node) {
        const styles = getComputedStyle(this);
        const scale = this.viewport.scale;
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
     * Build the child region rooted at one node and its immediate neighbors.      * @param {string} nodeId The node id value used by this operation.
     *
     * @returns {KnowledgeGraphFocus} An object containing the sets of node and edge identifiers that form the focused graph region.
     */
    graphRegionForNode(nodeId) {
        const nodeIds = new Set(nodeId ? [nodeId] : []);
        const edgeIds = new Set();
        this.edges.forEach(edge => {
            if (edge.from !== nodeId && edge.to !== nodeId) {
                return;
            }
            edgeIds.add(edge.id);
            nodeIds.add(edge.from);
            nodeIds.add(edge.to);
        });
        this.edges.forEach(edge => {
            if (nodeIds.has(edge.from) && nodeIds.has(edge.to))
                edgeIds.add(edge.id);
        });
        return { nodeIds, edgeIds };
    }
    /**
     * Reconcile a preserved region after the graph records are rebuilt.
     */
    reconcileRegionEdges() {
        const availableNodeIds = new Set(this.nodes.map(node => node.id));
        this.regionNodeIds = new Set([...this.regionNodeIds].filter(id => availableNodeIds.has(id)));
        this.regionEdgeIds = new Set(this.edges
            .filter(edge => this.regionNodeIds.has(edge.from) && this.regionNodeIds.has(edge.to))
            .map(edge => edge.id));
    }
    /**
     * Capture the current level before navigating to a child region.
     * @returns {{ nodeIds: Set<string>; edgeIds: Set<string>; positions: Map<string, KnowledgePoint>; graphPositions: Map<string, { x: number; y: number; }>; rootNodeId: string; selectedNodeId: string; selectedRelationId: string; viewport: { x: number; y: number; scale: number; }; }} A snapshot object containing sets of region IDs, position maps, root and selection identifiers, and the current viewport state.
     */
    captureGraphRegionLevel() {
        return {
            nodeIds: new Set(this.regionNodeIds),
            edgeIds: new Set(this.regionEdgeIds),
            positions: new Map(this.regionPositions),
            graphPositions: new Map(this.nodes.map(node => [node.id, { x: node.x, y: node.y }])),
            rootNodeId: this.regionRootNodeId,
            selectedNodeId: this.selectedNodeId,
            selectedRelationId: this.selectedRelationId,
            viewport: { ...this.viewport }
        };
    }
    /**
     * Replace the current graph level with a child region rooted at one node.      * @param {string} nodeId The node id value used by this operation.
     */
    navigateGraphRegion(nodeId) {
        if (!this.nodeCanExpand(nodeId))
            return;
        const child = this.graphRegionForNode(nodeId);
        this.regionHistory.push(this.captureGraphRegionLevel());
        this.regionNodeIds = child.nodeIds;
        this.regionEdgeIds = child.edgeIds;
        this.regionPositions = new Map();
        this.regionRootNodeId = nodeId;
        this.selectedNodeId = nodeId;
        this.selectedRelationId = "";
        this.focusViewport = null;
        const focus = this.focusGraph();
        if (focus)
            this.layoutFocusedRegion(focus);
        this.needsViewportFit = true;
        this.drawCanvas();
        this.renderInspector();
    }
    /**
     * Restore exactly one parent graph level, including its layout and camera.
     */
    navigateBackGraphRegion() {
        const previous = this.regionHistory.pop();
        if (!previous)
            return;
        cancelAnimationFrame(this.cameraAnimationFrame);
        this.cameraAnimationFrame = 0;
        this.regionNodeIds = new Set(previous.nodeIds);
        this.regionEdgeIds = new Set(previous.edgeIds);
        this.regionPositions = new Map(previous.positions);
        this.regionRootNodeId = previous.rootNodeId;
        this.selectedNodeId = previous.selectedNodeId;
        this.selectedRelationId = previous.selectedRelationId;
        previous.graphPositions.forEach((position, nodeId) => {
            const node = this.nodes.find(item => item.id === nodeId);
            if (node)
                Object.assign(node, position);
        });
        this.viewport = { ...previous.viewport };
        this.needsViewportFit = false;
        this.focusViewport = null;
        this.hoveredNodeId = "";
        this.hoveredRelationId = "";
        this.relationHoverViewport = null;
        this.badgeHoverViewport = null;
        this.drawCanvas();
        this.renderInspector();
    }
    /**
     * Draw a persistent node label.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @param {object} node Graph node.
     * @param {boolean} selected Whether selected.
     * @param {boolean} ranked Whether represented by a ranked inspector badge.
     * @param {object[]} occupiedBounds Ranked-label rectangles already placed this frame.
     * @returns {void}
     */
    drawNodeLabel(context, node, selected, ranked = false, occupiedBounds = []) {
        const styles = getComputedStyle(this);
        const label = shortKnowledgeLabel(node.label, selected ? 28 : 18);
        const fontSize = selected ? 12 : ranked ? 11 : 10;
        const scale = this.viewport.scale;
        context.save();
        context.font = `800 ${fontSize / scale}px Inter, system-ui, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        const width = context.measureText(label).width + (14 / scale);
        const height = (fontSize + 8) / scale;
        const placement = ranked
            ? this.rankedLabelPlacement(node, width, height, occupiedBounds)
            : { x: node.x, y: node.y + node.radius + (14 / scale) };
        const x = placement.x;
        const y = placement.y;
        if (ranked || selected) {
            context.fillStyle = styles.getPropertyValue("--surface").trim();
            context.strokeStyle = node.color;
            context.lineWidth = 1.5 / scale;
            this.roundedRect(context, x - width / 2, y - height / 2, width, height, 8 / scale);
            context.fill();
            context.stroke();
            this.nodeLabelBounds.set(node.id, {
                left: x - width / 2,
                right: x + width / 2,
                top: y - height / 2,
                bottom: y + height / 2
            });
        }
        context.fillStyle = node.color;
        context.shadowColor = styles.getPropertyValue("--surface").trim();
        context.shadowBlur = 4 / scale;
        context.lineWidth = 3 / scale;
        context.fillText(label, x, y);
        context.restore();
    }
    /**
     * Place one screen-stable ranked label without intersecting earlier ranked labels.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     * @param {number} width The width value used by this operation.
     * @param {number} height The height value used by this operation.
     * @param {KnowledgeRectangle[]} occupiedBounds The occupied bounds value used by this operation.
     *
     * @returns {KnowledgePoint} The selected coordinate for the label placement, which is then added to the occupied bounds.
     */
    rankedLabelPlacement(node, width, height, occupiedBounds) {
        const scale = this.viewport.scale;
        const vertical = node.radius + (14 / scale);
        const horizontal = node.radius + (8 / scale) + width / 2;
        const candidates = [
            { x: node.x, y: node.y + vertical },
            { x: node.x, y: node.y - vertical },
            { x: node.x + horizontal, y: node.y },
            { x: node.x - horizontal, y: node.y },
            { x: node.x, y: node.y + vertical + height + (6 / scale) },
            { x: node.x, y: node.y - vertical - height - (6 / scale) },
            { x: node.x + horizontal, y: node.y + height + (6 / scale) },
            { x: node.x - horizontal, y: node.y - height - (6 / scale) }
        ];
        const padding = 4 / scale;
        const rectangleFor = (candidate) => ({
            left: candidate.x - width / 2 - padding,
            right: candidate.x + width / 2 + padding,
            top: candidate.y - height / 2 - padding,
            bottom: candidate.y + height / 2 + padding
        });
        const overlaps = (rectangle) => occupiedBounds.some(other => (rectangle.left < other.right
            && rectangle.right > other.left
            && rectangle.top < other.bottom
            && rectangle.bottom > other.top));
        const placement = candidates.find(candidate => !overlaps(rectangleFor(candidate)))
            || { x: node.x, y: node.y + vertical + (occupiedBounds.length * (height + padding)) };
        occupiedBounds.push(rectangleFor(placement));
        return placement;
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
    roundedRect(context, x, y, width, height, radius) {
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
}

cache=(()=>{return { KnowledgeCanvasRenderer: KnowledgeCanvasRenderer };})();return cache;};})();
const __brainExplorerModule33=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * State-bearing base contract for Knowledge canvas presentation collaborators.
 */
class KnowledgeCanvasState extends HTMLElement {
    /**
     * Stores the shared Knowledge canvas api state used by rendering and interaction collaborators.
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/infrastructure/shared/http/clients/brain-api-client").BrainApiClient | null}
     */
    api = null;
    /**
     * Stores the shared Knowledge canvas state state used by rendering and interaction collaborators.
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/presentation/shell/state/app-state").AppState | null}
     */
    state = null;
    /**
     * Stores the shared Knowledge canvas scope state used by rendering and interaction collaborators.
     * @type {KnowledgeScope}
     */
    scope = "all";
    /**
     * Stores the shared Knowledge canvas selecte copes state used by rendering and interaction collaborators.
     * @type {Set<"global" | "local">}
     */
    selectedScopes = new Set(["global", "local"]);
    /**
     * Stores the shared Knowledge canvas tre cope state used by rendering and interaction collaborators.
     * @type {KnowledgeScope}
     */
    treeScope = "all";
    /**
     * Stores the shared Knowledge canvas mode state used by rendering and interaction collaborators.
     * @type {KnowledgeMode}
     */
    mode = "all";
    /**
     * Stores the shared Knowledge canvas domain state used by rendering and interaction collaborators.
     * @type {string}
     */
    domain = "all";
    /**
     * Stores the shared Knowledge canvas query state used by rendering and interaction collaborators.
     * @type {string}
     */
    query = "";
    /**
     * Stores the shared Knowledge canvas output state used by rendering and interaction collaborators.
     * @type {ApiResponse<unknown> | null}
     */
    output = null;
    /**
     * Stores the shared Knowledge canvas records state used by rendering and interaction collaborators.
     * @type {KnowledgeRecord[]}
     */
    records = [];
    /**
     * Stores the shared Knowledge canvas relations state used by rendering and interaction collaborators.
     * @type {KnowledgeRelation[]}
     */
    relations = [];
    /**
     * Stores the shared Knowledge canvas nodes state used by rendering and interaction collaborators.
     * @type {KnowledgeGraphNode[]}
     */
    nodes = [];
    /**
     * Stores the shared Knowledge canvas edges state used by rendering and interaction collaborators.
     * @type {KnowledgeGraphEdge[]}
     */
    edges = [];
    /**
     * Stores the shared Knowledge canvas selecte od d state used by rendering and interaction collaborators.
     * @type {string}
     */
    selectedNodeId = "";
    /**
     * Stores the shared Knowledge canvas selecte elatio d state used by rendering and interaction collaborators.
     * @type {string}
     */
    selectedRelationId = "";
    /**
     * Stores the shared Knowledge canvas hovere elatio d state used by rendering and interaction collaborators.
     * @type {string}
     */
    hoveredRelationId = "";
    /**
     * Stores the shared Knowledge canvas hovere od d state used by rendering and interaction collaborators.
     * @type {string}
     */
    hoveredNodeId = "";
    /**
     * Stores the shared Knowledge canvas regio od ds state used by rendering and interaction collaborators.
     * @type {Set<string>}
     */
    regionNodeIds = new Set();
    /**
     * Stores the shared Knowledge canvas regio dg ds state used by rendering and interaction collaborators.
     * @type {Set<string>}
     */
    regionEdgeIds = new Set();
    /**
     * Stores the shared Knowledge canvas regio ositions state used by rendering and interaction collaborators.
     * @type {Map<string, KnowledgePoint>}
     */
    regionPositions = new Map();
    /**
     * Stores the shared Knowledge canvas regio istory state used by rendering and interaction collaborators.
     * @type {KnowledgeRegionHistoryEntry[]}
     */
    regionHistory = [];
    /**
     * Stores the shared Knowledge canvas regio oo od d state used by rendering and interaction collaborators.
     * @type {string}
     */
    regionRootNodeId = "";
    /**
     * Stores the shared Knowledge canvas dra ode state used by rendering and interaction collaborators.
     * @type {KnowledgeNodeDrag | null}
     */
    dragNode = null;
    /**
     * Stores the shared Knowledge canvas pa tate state used by rendering and interaction collaborators.
     * @type {KnowledgePanState | null}
     */
    panState = null;
    /**
     * Stores the shared Knowledge canvas camer nimatio rame state used by rendering and interaction collaborators.
     * @type {number}
     */
    cameraAnimationFrame = 0;
    /**
     * Stores the shared Knowledge canvas viewport state used by rendering and interaction collaborators.
     * @type {KnowledgeViewport}
     */
    viewport = { x: 0, y: 0, scale: 1 };
    /**
     * Stores the shared Knowledge canvas rende rustum state used by rendering and interaction collaborators.
     * @type {KnowledgeRenderFrustum | null}
     */
    renderFrustum = null;
    /**
     * Stores the shared Knowledge canvas edg abe ounds state used by rendering and interaction collaborators.
     * @type {Map<string, KnowledgeRectangle>}
     */
    edgeLabelBounds = new Map();
    /**
     * Stores the shared Knowledge canvas nod abe ounds state used by rendering and interaction collaborators.
     * @type {Map<string, KnowledgeRectangle>}
     */
    nodeLabelBounds = new Map();
    /**
     * Stores the shared Knowledge canvas viewpor od ds state used by rendering and interaction collaborators.
     * @type {Set<string>}
     */
    viewportNodeIds = new Set();
    /**
     * Stores the shared Knowledge canvas viewpor adg ignature state used by rendering and interaction collaborators.
     * @type {string}
     */
    viewportBadgeSignature = "";
    /**
     * Stores the shared Knowledge canvas viewpor nspecto imer state used by rendering and interaction collaborators.
     * @type {number}
     */
    viewportInspectorTimer = 0;
    /**
     * Stores the shared Knowledge canvas viewpor adg ankin rozen state used by rendering and interaction collaborators.
     * @type {boolean}
     */
    viewportBadgeRankingFrozen = false;
    /**
     * Stores the shared Knowledge canvas expande omains state used by rendering and interaction collaborators.
     * @type {Set<string>}
     */
    expandedDomains = new Set(["global::all", "local::all"]);
    /**
     * Stores the shared Knowledge canvas resiz bserver state used by rendering and interaction collaborators.
     * @type {ResizeObserver | null}
     */
    resizeObserver = null;
    /**
     * Stores the shared Knowledge canvas loa cheduled state used by rendering and interaction collaborators.
     * @type {boolean}
     */
    loadScheduled = false;
    /**
     * Stores the shared Knowledge canvas grap us epth state used by rendering and interaction collaborators.
     * @type {number}
     */
    graphBusyDepth = 0;
    /**
     * Stores the shared Knowledge canvas grap us abel state used by rendering and interaction collaborators.
     * @type {string}
     */
    graphBusyLabel = "Loading graph";
    /**
     * Stores the shared Knowledge canvas need iewpor it state used by rendering and interaction collaborators.
     * @type {boolean}
     */
    needsViewportFit = true;
    /**
     * Stores the shared Knowledge canvas filter pen state used by rendering and interaction collaborators.
     * @type {boolean}
     */
    filtersOpen = false;
    /**
     * Stores the shared Knowledge canvas domai re odes state used by rendering and interaction collaborators.
     * @type {KnowledgeTreeNode[]}
     */
    domainTreeNodes = [];
    /**
     * Stores the shared Knowledge canvas memor aths state used by rendering and interaction collaborators.
     * @type {string[]}
     */
    memoryPaths = [];
    /**
     * Stores the shared Knowledge canvas pictures state used by rendering and interaction collaborators.
     * @type {PictureRecord[]}
     */
    pictures = [];
    /**
     * Stores the shared Knowledge canvas messages state used by rendering and interaction collaborators.
     * @type {AvatarMessageRecord[]}
     */
    messages = [];
    /**
     * Stores the shared Knowledge canvas messag essions state used by rendering and interaction collaborators.
     * @type {AvatarMessageSession[]}
     */
    messageSessions = [];
    /**
     * Stores the shared Knowledge canvas lo ntries state used by rendering and interaction collaborators.
     * @type {LogEntryPayload[]}
     */
    logEntries = [];
    /**
     * Stores the shared Knowledge canvas selecte re ath state used by rendering and interaction collaborators.
     * @type {string}
     */
    selectedTreePath = "";
    /**
     * Stores the shared Knowledge canvas sourc ath state used by rendering and interaction collaborators.
     * @type {string}
     */
    sourcePath = "";
    /**
     * Stores the shared Knowledge canvas sourc ind state used by rendering and interaction collaborators.
     * @type {"" | KnowledgeSourceKind}
     */
    sourceKind = "";
    /**
     * Stores the shared Knowledge canvas tre isua ype state used by rendering and interaction collaborators.
     * @type {"" | KnowledgeVisualType}
     */
    treeVisualType = "";
    /**
     * Stores the shared Knowledge canvas focu iewport state used by rendering and interaction collaborators.
     * @type {KnowledgeViewport | null}
     */
    focusViewport = null;
    /**
     * Stores the shared Knowledge canvas relatio ove iewport state used by rendering and interaction collaborators.
     * @type {KnowledgeViewport | null}
     */
    relationHoverViewport = null;
    /**
     * Stores the shared Knowledge canvas badg ove iewport state used by rendering and interaction collaborators.
     * @type {KnowledgeViewport | null}
     */
    badgeHoverViewport = null;
    /**
     * Stores the shared Knowledge canvas pointe andidate state used by rendering and interaction collaborators.
     * @type {KnowledgePointerCandidate | null}
     */
    pointerCandidate = null;
    /**
     * Stores the shared Knowledge canvas domai olors state used by rendering and interaction collaborators.
     * @type {Map<string, string>}
     */
    domainColors = new Map();
    /**
     * Stores the shared Knowledge canvas use omai olors state used by rendering and interaction collaborators.
     * @type {Set<string>}
     */
    usedDomainColors = new Set();
    /**
     * Stores the shared Knowledge canvas pendin ntit abel state used by rendering and interaction collaborators.
     * @type {string}
     */
    pendingEntityLabel = "";
}

cache=(()=>{return { KnowledgeCanvasState: KnowledgeCanvasState };})();return cache;};})();
const __brainExplorerModule34=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml, optionTags, renderMarkdown } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
const { StructureTree } = __brainExplorerModule9();
const { logsRouteTarget } = __brainExplorerModule35();
const { visibleLogEntries } = __brainExplorerModule36();
const { projectLogDateTree } = __brainExplorerModule37();
const { logDateTreeSelection, treeDetailNode } = __brainExplorerModule38();
const { treeSelectDetail } = __brainExplorerModule39();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */








void StructureTree;
/**
 * LogsView renders log domains as a structural tree plus one focused content pane.
 */
class LogsView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the logs view component in the DOM.
     * @returns {string} The string identifier 'brain-logs-view'.
     */
    static get selector() {
        return "brain-logs-view";
    }
    /**
     * Holds a reference to the component's API context for accessing shared services and state, defaulting to null.
     *
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/infrastructure/shared/http/clients/brain-api-client").BrainApiClient | null}
     */
    #api = null;
    /**
     * Holds the internal state of the component context or remains null if the context is not yet initialized.
     *
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/presentation/shell/state/app-state").AppState | null}
     */
    #state = null;
    /**
     * Maintains a collection of log entry payloads for indexing within the logs view.
     *
     * @type {LogEntryPayload[]}
     */
    #indexEntries = [];
    /**
     * Maintains a private collection of log entry payloads for the view's state.
     *
     * @type {LogEntryPayload[]}
     */
    #logEntries = [];
    /**
     * Stores the identifier of the currently selected domain within the logs view state.
     *
     * @type {string}
     */
    #selectedDomain = "";
    /**
     * Maintains the current text filter string used to narrow the displayed log entries.
     *
     * @type {string}
     */
    #filter = "";
    /**
     * Stores the starting boundary or source identifier for filtering log entries.
     *
     * @type {string}
     */
    #from = "";
    /**
     * Stores the destination target identifier for log filtering or navigation.
     *
     * @type {string}
     */
    #to = "";
    /**
     * Stores the starting hour boundary for filtering or displaying log entries.
     *
     * @type {string}
     */
    #hourFrom = "";
    /**
     * Stores the upper bound hour limit for filtering log entries.
     *
     * @type {string}
     */
    #hourTo = "";
    /**
     * Maintains the current sorting direction for the logs display, defaulting to descending order.
     *
     * @type {LogsSortOrder}
     */
    #sortOrder = "desc";
    /**
     * Maintains the current structural visualization mode for the logs tree, defaulting to domain-based grouping.
     *
     * @type {LogsTreeMode}
     */
    #treeMode = "domain";
    /**
     * Maintains the current file system or URI path associated with the selected date for log retrieval.
     *
     * @type {string}
     */
    #selectedDatePath = "";
    /**
     * Tracks the visibility state of the logs filter interface.
     *
     * @type {boolean}
     */
    #filtersOpen = false;
    /**
     * Maintains a set of unique identifiers representing the currently expanded nodes within the logs view hierarchy.
     *
     * @type {Set<string>}
     */
    #expandedNodes = new Set();
    /**
     * Stores a reference to a pending navigation target within the logs view, or null if no target is queued.
     *
     * @type {LogsRouteTarget | null}
     */
    #pendingTarget = null;
    /**
     * Maintains a private collection of image source URLs associated with the logs.
     *
     * @type {string[]}
     */
    #logsWithImages = [];
    /**
     * Stores the numeric identifier of the active polling timer used to trigger log refreshes.
     *
     * @type {number | null}
     */
    #refreshTimer = null;
    /**
     * Tracks whether a log refresh operation is currently in progress to prevent concurrent execution.
     *
     * @type {boolean}
     */
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
        this.#pendingTarget = logsRouteTarget(this.#state.consumeRouteTarget("logs")) || this.#pendingTarget;
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
    /**
     * Stop background work when the Logs route is unmounted.
     */
    disconnectedCallback() {
        if (this.#refreshTimer !== null)
            window.clearTimeout(this.#refreshTimer);
        this.#refreshTimer = null;
    }
    /**
     * Start a single view-owned silent refresh cycle.
     */
    #startSilentRefresh() {
        if (this.#refreshTimer) {
            return;
        }
        this.#scheduleSilentRefresh();
    }
    /**
     * Schedule the next cycle one minute after the previous one completed.
     */
    #scheduleSilentRefresh() {
        if (!this.isConnected) {
            return;
        }
        this.#refreshTimer = window.setTimeout(() => {
            this.#refreshTimer = null;
            this.#refreshSilently();
        }, 60000);
    }
    /**
     * Refresh the index and reload focused content only after an index change.
     */
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
        const target = this.#pendingTarget || logsRouteTarget(this.#state?.consumeRouteTarget("logs") ?? null);
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
     *
     * @param {boolean} readControls Specifies whether to synchronize the current filter values from the UI controls before initiating the request.
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
        const order = this.querySelector("[data-role='log-order']")?.value;
        if (order === "asc" || order === "desc")
            this.#sortOrder = order;
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
                            <strong>${escapeHtml(this.#selectedDomain || "Log index")}</strong>
                            <span>${escapeHtml(this.#logEntries.length ? `${entries.length} entries` : (selectedRecord?.date ? "Indexed entry" : "Select a domain"))}</span>
                            <details class="action-menu filter-menu" ${this.#filtersOpen ? "open" : ""}>
                                <summary class="compact-action">${icon("filter")}<span>Filters</span></summary>
                                <div class="action-menu-panel filter-menu-panel">
                                    <label><span>Desde</span><input data-role="log-from" value="${escapeHtml(this.#from)}" placeholder="DD-MM-YYYY"></label>
                                    <label><span>Hasta</span><input data-role="log-to" value="${escapeHtml(this.#to)}" placeholder="DD-MM-YYYY"></label>
                                    <label><span>Hora inicio</span><input data-role="log-hour-from" type="time" value="${escapeHtml(this.#hourFrom)}"></label>
                                    <label><span>Hora fin</span><input data-role="log-hour-to" type="time" value="${escapeHtml(this.#hourTo)}"></label>
                                    <label><span>Orden</span><select data-role="log-order">${optionTags(["desc", "asc"], this.#sortOrder)}</select></label>
                                    <div class="filter-menu-actions">
                                        <button data-action="clear-log-filters" class="ghost-action">${icon("filter")}Clear</button>
                                        <button data-action="load-logs" class="primary-action">${icon("search")}Aplicar</button>
                                    </div>
                                </div>
                            </details>
                        </div>
                        <div class="log-output log-card-list scroll-area">
                            ${this.#logEntries.length ? this.#renderLogEntries(entries) : `<p class="empty-state">Select a domain and load its history.</p>`}
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
            return `<p class="empty-state">No entries match these filters.</p>`;
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
            <div class="log-entry-media" aria-label="Attached images">
                ${pictures.map(name => {
            const source = `/api/logs/image?name=${encodeURIComponent(name)}`;
            return `<a href="${source}" target="_blank" rel="noopener" title="Open attached image"><img src="${source}" alt="Attached image ${escapeHtml(name)}"></a>`;
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
        return visibleLogEntries({
            entries: this.#logEntries,
            selectedDomain: this.#selectedDomain,
            hourFrom: this.#hourFrom,
            hourTo: this.#hourTo,
            sortOrder: this.#sortOrder,
            logsWithImages: this.#logsWithImages
        });
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
        if (!(treeElement instanceof StructureTree)) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#treeMode === "date" ? this.#selectedDatePath : this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
            toggleOnBranchSelect: true,
            title: "Logs",
            toolbarActions: [
                { id: "tree-domain", label: "Group by domain", icon: "folder", active: this.#treeMode === "domain" },
                { id: "tree-date", label: "Group by date", icon: "clock", active: this.#treeMode === "date" },
                { id: "refresh-index", label: "Refresh index", icon: "refresh" }
            ],
            sortDirection: this.#treeMode === "date" ? "desc" : "asc",
            defaultBranchIcon: "folder",
            defaultLeafIcon: "terminal",
            searchQuery: this.#filter,
            emptyText: "No index loaded. Refresh to browse logs."
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onTreeAction(event));
        treeElement.addEventListener("brain-tree-search", event => {
            if (!(event instanceof CustomEvent) || typeof event.detail?.query !== "string")
                return;
            this.#filter = event.detail.query;
            const entries = this.#visibleLogEntries();
            const selectedRecord = this.#recordForPath(this.#selectedDomain);
            const countSpan = this.querySelector(".logs-head span");
            if (countSpan) {
                countSpan.textContent = this.#logEntries.length ? `${entries.length} entries` : (selectedRecord?.date ? "Indexed entry" : "Select a domain");
            }
            const logOutput = this.querySelector(".log-output");
            if (logOutput) {
                logOutput.innerHTML = this.#logEntries.length ? this.#renderLogEntries(entries) : `<p class="empty-state">Select a domain and load its history.</p>`;
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
        const toNode = (node) => {
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
                ...(!isEntry ? { count: this.#countTreeEntries(node) } : {}),
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
        return projectLogDateTree(this.#indexEntries);
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
        if (!(event instanceof CustomEvent))
            return;
        const selection = treeSelectDetail(event.detail);
        if (!selection || selection.branch) {
            return;
        }
        const dateNode = logDateTreeSelection(treeDetailNode(event.detail));
        if (this.#treeMode === "date" && dateNode) {
            this.#selectedDatePath = selection.path;
            this.#selectedDomain = dateNode.domain;
            this.#from = dateNode.date;
            this.#to = dateNode.date;
            this.#hourFrom = dateNode.time;
            this.#hourTo = dateNode.time;
            await this.#loadLogs(true, false);
            return;
        }
        const alreadySelected = selection.path === this.#selectedDomain;
        this.#selectedDomain = selection.path;
        this.#expandAncestors(selection.path);
        const record = this.#recordForPath(selection.path);
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
        if (!(event instanceof CustomEvent))
            return;
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
        if (!(event instanceof CustomEvent))
            return;
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
                const child = current.children.get(part);
                if (!child)
                    throw new Error(`Unable to create log domain node: ${path}`);
                current = child;
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
            if (event.currentTarget instanceof HTMLDetailsElement)
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
            const clickedCaret = event.target instanceof Element && Boolean(event.target.closest(".tree-caret"));
            if (isBranch && clickedCaret) {
                const nextOpen = !wasExpanded;
                if (wasExpanded) {
                    this.#expandedNodes.delete(path);
                }
                else {
                    this.#expandedNodes.add(path);
                }
                const childContainer = Array.from(button.parentElement?.children || []).find((child) => child instanceof HTMLElement && child.classList.contains("tree-children"));
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
const __brainExplorerModule35=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Runtime narrowing for route state entering the Logs presentation feature.
 */
/**
 * Return a string property from an unknown route record when present.
 *
 * @param {Record<string, unknown>} record Untrusted route record consumed from shell navigation state.
 * @param {string} key Property name whose string value is requested.
 * @returns {string | undefined} The string property, or `undefined` for absent and non-string values.
 */
function optionalString(record, key) {
    const value = record[key];
    return typeof value === "string" ? value : undefined;
}
/**
 * Determine whether an unknown value is a supported Logs sort order.
 *
 * @param {unknown} value Unknown sort value supplied by route state.
 * @returns {boolean} True only for the closed ascending and descending order literals.
 */
function isLogsSortOrder(value) {
    return value === "asc" || value === "desc";
}
/**
 * Converts an untrusted SPA route record into the explicit Logs target model.
 *
 * @param {Record<string, unknown> | null} value Unknown value consumed from global route state.
 * @returns {LogsRouteTarget | null} A safely narrowed target, or `null` when no record was supplied.
 */
function logsRouteTarget(value) {
    if (!value)
        return null;
    const target = {};
    const stringKeys = ["domain", "date", "time", "from", "to", "hourFrom", "hourTo"];
    for (const key of stringKeys) {
        const property = optionalString(value, key);
        if (property !== undefined)
            target[key] = property;
    }
    if (isLogsSortOrder(value.sortOrder))
        target.sortOrder = value.sortOrder;
    return target;
}

cache=(()=>{return { logsRouteTarget: logsRouteTarget };})();return cache;};})();
const __brainExplorerModule36=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Converts transport-level log records into sorted, filterable presentation entries.
 *
 * This module owns deterministic parsing and picture-reference discovery so the Logs
 * Web Component remains responsible only for rendering and interaction orchestration.
 *
 * @module presentation/logs/formatters/log-entry-parser
 */
/**
 * Produce normalized, hour-filtered, chronologically ordered log entries.
 *
 * @param {VisibleLogEntriesInput} input Complete immutable parsing and filtering context.
 * @returns {ParsedLogEntryViewModel[]} A new array suitable for direct rendering by the Logs layout.
 */
function visibleLogEntries(input) {
    const earliestMinute = timeInputMinute(input.hourFrom);
    const latestMinute = timeInputMinute(input.hourTo);
    return input.entries
        .map((entry, index) => parsedLogEntry(entry, index, input.selectedDomain, input.logsWithImages))
        .filter(entry => minuteIsWithinRange(entry.hourValue, earliestMinute, latestMinute))
        .sort((left, right) => {
        const delta = left.timestamp - right.timestamp;
        return input.sortOrder === "asc" ? delta : -delta;
    });
}
/**
 * Normalize one transport record into the view model expected by the log-card renderer.
 *
 * @param {LogEntryPayload} entry Structured server record to normalize.
 * @param {number} index Stable array position used to build a local render identity.
 * @param {string} selectedDomain Domain fallback for records that omit their own domain.
 * @param {readonly string[]} logsWithImages Task ids known to own a backlog reference image.
 * @returns {ParsedLogEntryViewModel} Fully populated presentation entry with derived time and picture metadata.
 */
function parsedLogEntry(entry, index, selectedDomain, logsWithImages) {
    const [date = "", ...timeParts] = String(entry.timestamp || "").split(" ");
    const time = timeParts.join(" ");
    const searchableText = [entry.title, entry.why, entry.description, entry.impact].join("\n");
    return {
        id: `log-${index}`,
        date,
        time,
        hourValue: logClockMinute(time),
        timestamp: sortableTimestamp(date, time),
        domain: entry.domain || selectedDomain,
        title: entry.title || "Log entry",
        type: "log",
        changeType: entry.change_type || "",
        why: entry.why || "",
        description: entry.description || "",
        impact: entry.impact || "",
        pictures: pictureNames(searchableText, logsWithImages)
    };
}
/**
 * Extract unique safe picture filenames referenced by Markdown fields or task ids.
 *
 * @param {string} source Concatenated Markdown content belonging to one log record.
 * @param {readonly string[]} logsWithImages Task identifiers known to have a generated backlog picture.
 * @returns {string[]} Deduplicated filenames without directory traversal segments.
 */
function pictureNames(source, logsWithImages) {
    const names = new Set();
    const matcher = /(?:\$agent[\\/])?pictures[\\/]([A-Za-z0-9][A-Za-z0-9._-]*\.(?:png|jpe?g|gif|webp))/gi;
    for (const match of String(source || "").matchAll(matcher)) {
        const name = match[1];
        if (name)
            names.add(name);
    }
    for (const match of String(source || "").matchAll(/#?(t\d+)\b/gi)) {
        const taskId = (match[1] ?? "").toLowerCase();
        if (logsWithImages.includes(taskId))
            names.add(`backlog-pic-${taskId}.png`);
    }
    return [...names];
}
/**
 * Determine whether a minute value falls inside an optional inclusive range.
 *
 * @param {number} value Candidate minutes after midnight.
 * @param {number | null} earliest Inclusive lower bound, or null when unrestricted.
 * @param {number | null} latest Inclusive upper bound, or null when unrestricted.
 * @returns {boolean} True when the candidate satisfies both configured bounds.
 */
function minuteIsWithinRange(value, earliest, latest) {
    if (earliest !== null && value < earliest)
        return false;
    if (latest !== null && value > latest)
        return false;
    return true;
}
/**
 * Parse a browser time-control value into minutes after midnight.
 *
 * @param {string} value Browser `HH:MM` value or an empty filter value.
 * @returns {number | null} Parsed minutes, or null when the value does not represent a complete time.
 */
function timeInputMinute(value) {
    const match = String(value || "").match(/^(\d{2}):(\d{2})$/);
    return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}
/**
 * Parse a 12-hour or 24-hour log label into minutes after midnight.
 *
 * @param {string} label Human-readable clock label emitted by the log facade.
 * @returns {number} Parsed minutes, or zero when no clock value can be recognized.
 */
function logClockMinute(label) {
    const match = String(label || "").toLowerCase().match(/(\d{1,2}):(\d{2})\s*(am|pm)?/);
    if (!match)
        return 0;
    let hour = Number(match[1]);
    const minute = Number(match[2]);
    if (match[3] === "pm" && hour < 12)
        hour += 12;
    if (match[3] === "am" && hour === 12)
        hour = 0;
    return hour * 60 + minute;
}
/**
 * Combine exported date and time labels into a sortable local timestamp.
 *
 * @param {string} date Date label in `DD-MM-YYYY` form.
 * @param {string} time Clock label accepted by {@link logClockMinute}.
 * @returns {number} Milliseconds since the epoch, or zero for malformed dates.
 */
function sortableTimestamp(date, time) {
    const match = String(date || "").match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (!match)
        return 0;
    const minutes = logClockMinute(time);
    return new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1]), Math.floor(minutes / 60), minutes % 60).getTime();
}

cache=(()=>{return { visibleLogEntries: visibleLogEntries, logClockMinute: logClockMinute };})();return cache;};})();
const __brainExplorerModule37=(()=>{let cache;return()=>{if(cache)return cache;
const { logClockMinute } = __brainExplorerModule36();
/**
 * Projects the flat log index into a year, month, day, and entry hierarchy.
 *
 * The projector is deliberately independent from DOM state so date grouping can be
 * reused and tested without instantiating the Logs Web Component.
 *
 * @module presentation/logs/projectors/log-date-tree-projector
 */

/**
 * Month labels indexed by their one-based numeric month value.
 */
const LOG_MONTH_LABELS = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
];
/**
 * Build shared tree nodes ordered from the newest year and month to the oldest.
 *
 * Malformed timestamps are omitted because they cannot be assigned to an honest
 * calendar branch; their underlying records remain available in domain mode.
 *
 * @param {readonly LogEntryPayload[]} entries Complete immutable log-index projection returned by the API.
 * @returns {StructureTreeNode[]} Date hierarchy compatible with the shared structure-tree component.
 */
function projectLogDateTree(entries) {
    const years = new Map();
    entries.forEach((entry, index) => appendDateEntry(years, entry, index));
    return Array.from(years.values())
        .sort((left, right) => right.id.localeCompare(left.id))
        .map(projectDateGroup);
}
/**
 * Append one valid index entry to its year, month, and day accumulators.
 *
 * @param {Map<string, LogDateGroup>} years Mutable top-level accumulator map owned by one projection call.
 * @param {LogEntryPayload} entry Structured log-index entry to classify.
 * @param {number} index Stable source position used to disambiguate render identities.
 */
function appendDateEntry(years, entry, index) {
    const [date = "", ...timeParts] = String(entry.timestamp || "").split(" ");
    const match = date.match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (!match)
        return;
    const day = match[1] ?? "";
    const month = match[2] ?? "";
    const year = match[3] ?? "";
    const time = timeParts.join(" ");
    const monthLabel = LOG_MONTH_LABELS[Number(month)] || month;
    const yearNode = ensureDateGroup(years, `logs-date:${year}`, year, "folder");
    const monthNode = ensureDateGroup(yearNode.children, `logs-date:${year}-${month}`, monthLabel, "folder");
    const dayNode = ensureDateGroup(monthNode.children, `logs-date:${year}-${month}-${day}`, `${day} ${monthLabel}`, "clock");
    dayNode.entries.push({
        id: `logs-date-entry:${index}:${date}:${time}:${entry.domain || "logs"}`,
        path: `logs-date-entry:${date}:${time}:${entry.domain || "logs"}`,
        label: entry.title || "Log entry",
        timestamp: time,
        sortKey: String(logClockMinute(time)).padStart(4, "0"),
        detail: entry.domain || "logs",
        presentation: "log",
        domain: entry.domain || "",
        date,
        time,
        children: []
    });
}
/**
 * Create or retrieve one sibling date-group accumulator.
 *
 * @param {Map<string, LogDateGroup>} groups Mutable sibling map for a single calendar depth.
 * @param {string} id Stable structural identity for the group.
 * @param {string} label Human-readable group label.
 * @param {"edit" | "settings" | "home" | "database" | "graph" | "search" | "messageCircle" | "sliders" | "users" | "document" | "plus" | "documentPlus" | "folderPlus" | "copy" | "trash" | "save" | "refresh" | "pulse" | "folder" | "moon" | "sun" | "terminal" | "close" | "collapseLeft" | "expandRight" | "eye" | "filter" | "checkSquare" | "chevronRight" | "chevronLeft" | "chevronDown" | "minus" | "more" | "clock" | "camera" | "book" | "volume" | "play" | "pause" | "download"} icon Registered shared-tree icon associated with this depth.
 * @returns {LogDateGroup} Existing or newly created accumulator stored in `groups`.
 */
function ensureDateGroup(groups, id, label, icon) {
    const existing = groups.get(id);
    if (existing)
        return existing;
    const created = { id, label, icon, children: new Map(), entries: [] };
    groups.set(id, created);
    return created;
}
/**
 * Convert one mutable accumulator and all descendants into immutable tree nodes.
 *
 * @param {LogDateGroup} group Calendar accumulator to project.
 * @returns {StructureTreeNode} Shared tree node containing sorted subgroup and terminal entry children.
 */
function projectDateGroup(group) {
    const groups = Array.from(group.children.values())
        .sort((left, right) => right.id.localeCompare(left.id))
        .map(projectDateGroup);
    const entries = [...group.entries].sort((left, right) => right.timestamp.localeCompare(left.timestamp));
    return {
        id: group.id,
        path: group.id,
        label: group.label,
        sortKey: group.id,
        icon: group.icon,
        count: countDateEntries(group),
        sortDirection: "desc",
        children: [...groups, ...entries]
    };
}
/**
 * Count terminal log entries recursively beneath a calendar group.
 *
 * @param {LogDateGroup} group Calendar accumulator whose descendants must be counted.
 * @returns {number} Total number of terminal entries owned by the group hierarchy.
 */
function countDateEntries(group) {
    return group.entries.length + Array.from(group.children.values())
        .reduce((total, child) => total + countDateEntries(child), 0);
}

cache=(()=>{return { projectLogDateTree: projectLogDateTree };})();return cache;};})();
const __brainExplorerModule38=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Narrow the untrusted node attached to a shared tree-selection event.
 *
 * @param {unknown} value Unknown `node` member emitted across the Custom Event boundary.
 * @returns {LogDateTreeSelection | null} Validated date-tree metadata, or `null` when any required field is absent.
 */
function logDateTreeSelection(value) {
    if (typeof value !== "object" || value === null || Array.isArray(value))
        return null;
    const node = Object.fromEntries(Object.entries(value));
    if (typeof node.domain !== "string" || typeof node.date !== "string" || typeof node.time !== "string")
        return null;
    return { domain: node.domain, date: node.date, time: node.time };
}
/**
 * Read the optional node member from an untrusted tree event detail object.
 *
 * @param {unknown} value Unknown Custom Event detail value.
 * @returns {unknown} Raw node member for subsequent feature-specific validation.
 */
function treeDetailNode(value) {
    if (typeof value !== "object" || value === null || Array.isArray(value))
        return undefined;
    return Object.fromEntries(Object.entries(value)).node;
}

cache=(()=>{return { logDateTreeSelection: logDateTreeSelection, treeDetailNode: treeDetailNode };})();return cache;};})();
const __brainExplorerModule39=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Shared, framework-neutral contracts for the reusable hierarchical tree component.
 *
 * Feature layouts project their domain-specific records into these view models and
 * validate emitted Custom Event details through the boundary helpers in this module.
 * No interface declared here owns API, persistence, or feature business semantics.
 *
 * @module presentation/shared/view_models/structure-tree-view-model
 */
/**
 * Convert an unknown object to an indexable record without a type assertion.
 *
 * @param {unknown} value Untrusted value crossing the DOM Custom Event boundary.
 * @returns {Record<string, unknown> | null} A shallow record copy, or `null` for primitives, arrays, and null.
 */
function detailRecord(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value)
        ? Object.fromEntries(Object.entries(value))
        : null;
}
/**
 * Validate and normalize a tree-selection event payload at the DOM boundary.
 *
 * @param {unknown} value Untrusted `CustomEvent.detail` value.
 * @returns {TreeSelectDetail | null} A closed selection contract, or `null` when required fields are invalid.
 */
function treeSelectDetail(value) {
    const detail = detailRecord(value);
    if (!detail || typeof detail.path !== "string" || typeof detail.branch !== "boolean" || typeof detail.clickedCaret !== "boolean") {
        return null;
    }
    return { path: detail.path, branch: detail.branch, clickedCaret: detail.clickedCaret };
}
/**
 * Validate and normalize a tree-action event payload at the DOM boundary.
 *
 * The optional node is intentionally omitted unless it is an object. Consumers
 * that require feature-specific node metadata must validate those fields locally.
 *
 * @param {unknown} value Untrusted `CustomEvent.detail` value.
 * @returns {TreeActionDetail | null} A safe action contract, or `null` when the action id is absent.
 */
function treeActionDetail(value) {
    const detail = detailRecord(value);
    if (!detail || typeof detail.action !== "string")
        return null;
    const nodeRecord = detailRecord(detail.node);
    const node = nodeRecord && typeof nodeRecord.id === "string" && typeof nodeRecord.path === "string" && typeof nodeRecord.label === "string"
        ? { id: nodeRecord.id, path: nodeRecord.path, label: nodeRecord.label }
        : null;
    return { action: detail.action, ...(node ? { node } : {}) };
}
/**
 * Validate and normalize a tree-search event payload at the DOM boundary.
 *
 * @param {unknown} value Untrusted `CustomEvent.detail` value.
 * @returns {TreeSearchDetail | null} A safe query contract, or `null` for non-string queries.
 */
function treeSearchDetail(value) {
    const detail = detailRecord(value);
    return detail && typeof detail.query === "string" ? { query: detail.query } : null;
}

cache=(()=>{return { treeSelectDetail: treeSelectDetail, treeActionDetail: treeActionDetail, treeSearchDetail: treeSearchDetail };})();return cache;};})();
const __brainExplorerModule40=(()=>{let cache;return()=>{if(cache)return cache;
const { compactLabel, escapeHtml, renderMarkdown } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
const { StructureTree } = __brainExplorerModule9();
const { treeActionDetail, treeSearchDetail, treeSelectDetail } = __brainExplorerModule39();
const { memoryTarget } = __brainExplorerModule41();
const { MemoryTreeProjector } = __brainExplorerModule42();
const { renderMemoryLoadingState } = __brainExplorerModule43();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */







void StructureTree;
/**
 * MemoryView renders the memory store as a collapsible tree and one focused work area.
 */
class MemoryView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the memory view component in the DOM.
     * @returns {string} The string identifier 'brain-memory-view'.
     */
    static get selector() {
        return "brain-memory-view";
    }
    /**
     * Holds a reference to the BrainApiClient for performing API operations within the MemoryView component.
     *
     * @type {BrainApiClient}
     */
    #api;
    /**
     * Holds the application state instance used by the MemoryView component.
     *
     * @type {AppState}
     */
    #state;
    /**
     * Maintains a private collection of string identifiers representing the active memory paths within the view.
     *
     * @type {string[]}
     */
    #paths = [];
    /**
     * Stores the current navigation path of the selected memory element as a private string.
     *
     * @type {string}
     */
    #selectedPath = "";
    /**
     * Stores the identifier of the currently active memory domain within the view.
     *
     * @type {string}
     */
    #selectedDomain = "";
    /**
     * Stores the internal text content of the memory view as a private string.
     *
     * @type {string}
     */
    #content = "";
    /**
     * Maintains the internal state of the memory view's current operational status message.
     *
     * @type {string}
     */
    #status = "Preparing memory...";
    /**
     * Stores the current text filter used to narrow the displayed memory entries.
     *
     * @type {string}
     */
    #filter = "";
    /**
     * Maintains the current operational state of the memory view, defaulting to browse mode.
     *
     * @type {MemoryMode}
     */
    #mode = "browse";
    /**
     * Tracks whether the memory tree structure is currently being loaded.
     *
     * @type {boolean}
     */
    #loadingTree = false;
    /**
     * Tracks the loading state of a memory entry within the MemoryView component.
     *
     * @type {boolean}
     */
    #loadingEntry = false;
    /**
     * Tracks the unique identifiers of memory nodes currently in an expanded state within the view.
     *
     * @type {Set<string>}
     */
    #expandedNodes = new Set();
    /**
     * Tracks a MemoryTarget that is awaiting a transition or operation within the MemoryView.
     *
     * @type {MemoryTarget | null}
     */
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
        this.#pendingTarget = memoryTarget(this.#state.consumeRouteTarget("memory")) || this.#pendingTarget;
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
        this.#selectedDomain = this.#selectedDomain || this.#treeProjector().topDomains()[0] || "";
        if (this.#selectedDomain) {
            this.#expandedNodes.add(this.#selectedDomain);
        }
        this.#status = result.ok ? `${this.#treeProjector().leafPaths().length} entries` : result.stderr || result.error || "Could not load memory.";
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
        const target = this.#pendingTarget || memoryTarget(this.#state.consumeRouteTarget("memory"));
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
        this.#selectedDomain = this.#treeProjector().parentPath(path) || path.split(".")[0] || this.#selectedDomain;
        this.#expandAncestors(path);
        this.#mode = mode;
        this.#loadingEntry = true;
        this.#status = compactLabel(path);
        this.#render();
        const result = await this.#api.memoryEntry(path, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#content = result.data?.content || result.stdout || "";
        this.#status = result.ok ? compactLabel(path) : result.stderr || result.error || "Could not read the entry.";
        this.#loadingEntry = false;
        this.#render();
    }
    /**
     * Prepare a new entry in edit mode under the selected domain.
     *
     * @returns {void}
     */
    #newEntry() {
        const baseDomain = this.#selectedDomain || this.#treeProjector().topDomains()[0] || "notes";
        this.#selectedPath = `${baseDomain}.new_entry`;
        this.#content = "# New entry\n\nWrite Markdown memory here.";
        this.#mode = "edit";
        this.#status = "New entry";
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
            this.#status = "Define a path before saving.";
            this.#render();
            return;
        }
        this.#render();
        const result = await this.#api.saveMemoryEntry(path, content);
        this.#state?.setLastResult(result);
        this.#selectedPath = path;
        this.#selectedDomain = this.#treeProjector().parentPath(path) || path.split(".")[0] || "";
        this.#content = content;
        this.#status = result.ok ? compactLabel(path) : result.stderr || result.error || "Could not save.";
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
        this.#status = result.ok ? "Entry deleted" : result.stderr || result.error || "Could not delete.";
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
            this.#status = "Enter a domain.";
            this.#render();
            return;
        }
        const result = await this.#api.createMemoryDomain(domain);
        this.#state?.setLastResult(result);
        this.#selectedDomain = domain;
        this.#selectedPath = "";
        this.#expandedNodes.add(domain.split(".")[0] ?? domain);
        this.#status = result.ok ? `Domain ${domain}` : result.stderr || result.error || "Could not create domain.";
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
        this.#status = result.ok ? "Domain deleted" : result.stderr || result.error || "Could not delete domain.";
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
        const children = this.#treeProjector().childItems(this.#selectedDomain);
        return `
            <div class="content-head">
                <strong>${escapeHtml(this.#selectedDomain || "Memory")}</strong>
                <span>${escapeHtml(String(children.length))} visible</span>
            </div>
            <div class="entry-list scroll-list">
                ${children.length ? children.map(item => this.#renderContentItem(item)).join("") : `<p class="empty-state">Select a tree node.</p>`}
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
        const count = isBranch ? `${this.#treeProjector().leafPathsUnder(item.path).length} entries` : "Entry";
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
                <strong>${escapeHtml(compactLabel(this.#selectedPath) || "No entry")}</strong>
                <span>${escapeHtml(this.#selectedPath || this.#status)}</span>
            </div>
            <article class="markdown-preview scroll-area">
                ${this.#loadingEntry ? renderMemoryLoadingState("Rendering Markdown") : renderMarkdown(this.#content || "Select an entry.")}
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
                    <span>Path</span>
                    <input data-role="memory-path" value="${escapeHtml(this.#selectedPath)}" placeholder="domain.entry">
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
                    <span>Domain</span>
                    <input data-role="domain-name" value="${escapeHtml(this.#selectedDomain)}" placeholder="new.domain">
                </label>
            </div>
            <div class="domain-grid scroll-list">
                ${this.#treeProjector().topDomains().map(domain => `
                    <button class="domain-tile ${domain === this.#selectedDomain ? "is-active" : ""}" data-action="select-domain" data-node-path="${escapeHtml(domain)}">
                        ${icon("database")}
                        <strong>${escapeHtml(domain)}</strong>
                        <span>${escapeHtml(String(this.#treeProjector().leafPathsUnder(domain).length))} entries</span>
                    </button>
                `).join("") || `<p class="empty-state">No domains.</p>`}
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
        const projector = this.#treeProjector();
        const children = Array.from(node.children.values()).sort((left, right) => projector.compareNodes(left, right));
        const isVisible = projector.matchesFilter(node) || children.some(child => projector.containsFilter(child));
        if (!isVisible) {
            return "";
        }
        return `
            <div class="tree-node-wrap">
                <button class="tree-node ${isActive ? "is-active" : ""}" style="--tree-depth:${depth}" data-node-path="${escapeHtml(node.path)}" data-node-branch="${hasChildren ? "true" : "false"}">
                    <span class="tree-caret">${hasChildren ? icon(isOpen ? "chevronDown" : "chevronRight") : ""}</span>
                    ${icon(hasChildren ? "folder" : "document")}
                    <span>${escapeHtml(node.label)}</span>
                    ${hasChildren ? `<small>${escapeHtml(String(projector.leafPathsUnder(node.path).length))}</small>` : ""}
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
        if (!(treeElement instanceof StructureTree)) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#selectedPath || this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
            toggleOnBranchSelect: true,
            title: "Memory",
            toolbarActions: [
                { id: "new-entry", label: "New entry", icon: "plus" },
                { id: "create-domain", label: "New domain", icon: "folder" },
                { id: "refresh", label: "Refresh tree", icon: "refresh" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "database",
            searchQuery: this.#filter,
            emptyText: this.#loadingTree ? "Loading tree..." : "No paths loaded."
        };
        treeElement.addEventListener("brain-tree-select", event => {
            const detail = event instanceof CustomEvent ? treeSelectDetail(event.detail) : null;
            if (detail)
                this.#onTreeSelected(detail);
        });
        treeElement.addEventListener("brain-tree-toolbar-action", event => {
            const detail = event instanceof CustomEvent ? treeActionDetail(event.detail) : null;
            if (detail)
                this.#onTreeToolbarAction(detail);
        });
        treeElement.addEventListener("brain-tree-action", event => {
            const detail = event instanceof CustomEvent ? treeActionDetail(event.detail) : null;
            if (detail)
                this.#onTreeAction(detail);
        });
        treeElement.addEventListener("brain-tree-search", event => {
            const detail = event instanceof CustomEvent ? treeSearchDetail(event.detail) : null;
            if (!detail)
                return;
            this.#filter = detail.query;
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
        const projector = this.#treeProjector();
        const toNode = (node) => {
            const children = Array.from(node.children.values())
                .filter(child => projector.matchesFilter(child) || projector.containsFilter(child))
                .sort((left, right) => projector.compareNodes(left, right))
                .map(toNode);
            const hasChildren = children.length > 0;
            return {
                id: node.path,
                path: node.path,
                label: node.label,
                ...(hasChildren ? { count: projector.leafPathsUnder(node.path).length } : {}),
                children,
                actions: hasChildren
                    ? [
                        { id: "new-entry", label: "New entry", icon: "plus" },
                        { id: "delete-domain", label: "Delete domain", icon: "trash", danger: true }
                    ]
                    : [
                        { id: "open-entry", label: "Open", icon: "document" },
                        { id: "edit-entry", label: "Edit", icon: "edit" },
                        { id: "duplicate-entry", label: "Duplicar", icon: "copy" },
                        { id: "delete-entry", label: "Delete", icon: "trash", danger: true }
                    ]
            };
        };
        return Array.from(projector.buildTree().children.values())
            .filter(node => projector.matchesFilter(node) || projector.containsFilter(node))
            .sort((left, right) => projector.compareNodes(left, right))
            .map(toNode);
    }
    /**
     * React to a shared tree selection.
     *
     * @param {TreeSelectDetail} detail Validated selection detail emitted by the shared tree.
     * @returns {void}
     */
    #onTreeSelected(detail) {
        const { path, branch, clickedCaret } = detail;
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
     * @param {TreeActionDetail} detail Validated toolbar-action detail emitted by the shared tree.
     * @returns {void}
     */
    #onTreeToolbarAction(detail) {
        const action = detail.action;
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
     * @param {TreeActionDetail} detail Validated contextual-action detail emitted by the shared tree.
     * @returns {void}
     */
    #onTreeAction(detail) {
        const { action, node } = detail;
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
     * Create the pure tree projector for the component's current path and filter snapshot.
     *
     * @returns {MemoryTreeProjector} A stateless query object whose lifetime is limited to the calling operation.
     */
    #treeProjector() {
        return new MemoryTreeProjector(this.#paths, this.#filter);
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
     * Bind DOM events after render.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelectorAll("[data-action='set-memory-mode']").forEach(button => button.addEventListener("click", () => {
            const mode = button.getAttribute("data-memory-mode");
            if (mode === "browse" || mode === "read" || mode === "edit" || mode === "domains")
                this.#mode = mode;
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
            const isBranch = item.getAttribute("data-node-branch") === "true" || this.#treeProjector().hasChildren(path);
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
const __brainExplorerModule41=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Navigation and tree projection contracts for the Memory presentation feature.
 *
 * @module presentation/memory/view_models/memory-view-model
 */
/**
 * Narrow an untrusted route-target value to one supported Memory presentation mode.
 *
 * @param {unknown} value Candidate value received from shared navigation state.
 * @returns {boolean} True only for one of the four closed Memory modes.
 */
function isMemoryMode(value) {
    return value === "browse" || value === "read" || value === "edit" || value === "domains";
}
/**
 * Normalize untrusted shell route state into the Memory target contract.
 *
 * @param {Record<string, unknown> | null} value Unknown route record previously stored by another feature.
 * @returns {MemoryTarget | null} Narrowed target, or null when no route record was supplied.
 */
function memoryTarget(value) {
    if (!value)
        return null;
    const mode = isMemoryMode(value.mode) ? value.mode : undefined;
    return {
        ...(typeof value.path === "string" ? { path: value.path } : {}),
        ...(typeof value.domain === "string" ? { domain: value.domain } : {}),
        ...(mode ? { mode } : {})
    };
}

cache=(()=>{return { memoryTarget: memoryTarget };})();return cache;};})();
const __brainExplorerModule42=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Builds and queries the presentation tree derived from dot-notated memory paths.
 *
 * The projector contains no DOM or API behavior. A new instance represents one
 * immutable path/filter snapshot and can therefore be used safely throughout a
 * single component render or interaction.
 *
 * @module presentation/memory/projectors/memory-tree-projector
 */
/**
 * Provides deterministic tree construction, filtering, and leaf queries for Memory.
 */
class MemoryTreeProjector {
    /**
     * Memory paths included in this immutable projection snapshot.
     * @type {readonly string[]}
     */
    #paths;
    /**
     * Normalized, case-insensitive substring used by visibility queries.
     * @type {string}
     */
    #filterNeedle;
    /**
     * Create one projector for the current Memory response and text filter.
     *
     * @param {readonly string[]} paths Dot-notated memory paths returned by the application facade.
     * @param {string} filter User-entered filter text; surrounding whitespace is ignored.
     */
    constructor(paths, filter = "") {
        this.#paths = paths;
        this.#filterNeedle = filter.trim().toLowerCase();
    }
    /**
     * Build a new hierarchical tree from this projector's path snapshot.
     *
     * @returns {MemoryNode} Synthetic root whose children contain every normalized path segment.
     */
    buildTree() {
        const root = { label: "", path: "", children: new Map() };
        for (const path of this.#paths) {
            const parts = String(path).split(".").filter(Boolean);
            let current = root;
            parts.forEach((part, index) => {
                const nodePath = parts.slice(0, index + 1).join(".");
                let child = current.children.get(part);
                if (!child) {
                    child = { label: part, path: nodePath, children: new Map() };
                    current.children.set(part, child);
                }
                current = child;
            });
        }
        return root;
    }
    /**
     * Return visible direct children of a selected domain in branch-first order.
     *
     * @param {string} selectedDomain Dot-notated branch path, or an empty string for root.
     * @returns {MemoryNode[]} New array containing matching direct descendants.
     */
    childItems(selectedDomain) {
        const tree = this.buildTree();
        const parent = this.findNode(tree, selectedDomain) ?? tree;
        return Array.from(parent.children.values())
            .filter(item => this.matchesFilter(item) || this.containsFilter(item))
            .sort((left, right) => this.compareNodes(left, right));
    }
    /**
     * Find a node by its complete dot-notated identity.
     *
     * @param {MemoryNode} root Tree root from which traversal begins.
     * @param {string} path Dot-notated identity to resolve.
     * @returns {MemoryNode | null} Matching node, the supplied root for an empty path, or null when absent.
     */
    findNode(root, path) {
        if (!path)
            return root;
        let current = root;
        for (const part of path.split(".")) {
            current = current?.children.get(part);
            if (!current)
                return null;
        }
        return current;
    }
    /**
     * @returns {string[]} Unique top-level domain names in source order.
     */
    topDomains() {
        return [...new Set(this.#paths.map(path => path.split(".")[0]).filter((part) => Boolean(part)))];
    }
    /**
     * @returns {string[]} Terminal entry paths, excluding root-only domain declarations.
     */
    leafPaths() {
        return this.#paths.filter(path => !this.hasChildren(path) && path.includes("."));
    }
    /**
     * Return terminal paths owned by a branch.
     *
     * @param {string} prefix Branch path whose descendants should be included.
     * @returns {string[]} Terminal paths equal to or nested beneath `prefix`.
     */
    leafPathsUnder(prefix) {
        return this.leafPaths().filter(path => path === prefix || path.startsWith(`${prefix}.`));
    }
    /**
     * Determine whether another known path is nested beneath a candidate.
     *
     * @param {string} path Candidate branch identity.
     * @returns {boolean} True when at least one distinct descendant path exists.
     */
    hasChildren(path) {
        return this.#paths.some(candidate => candidate !== path && candidate.startsWith(`${path}.`));
    }
    /**
     * Resolve the parent of a dot-notated path.
     *
     * @param {string} path Path whose final segment should be removed.
     * @returns {string} Parent path, or an empty string for a top-level value.
     */
    parentPath(path) {
        const parts = String(path || "").split(".");
        parts.pop();
        return parts.join(".");
    }
    /**
     * Determine whether a node itself satisfies the normalized text filter.
     *
     * @param {MemoryNode} node Candidate tree node.
     * @returns {boolean} True when no filter is active or the full node path contains it.
     */
    matchesFilter(node) {
        return !this.#filterNeedle || node.path.toLowerCase().includes(this.#filterNeedle);
    }
    /**
     * Determine whether a node or any descendant satisfies the text filter.
     *
     * @param {MemoryNode} node Branch from which recursive visibility is evaluated.
     * @returns {boolean} True when the branch must remain visible to expose a match.
     */
    containsFilter(node) {
        return this.matchesFilter(node)
            || Array.from(node.children.values()).some(child => this.containsFilter(child));
    }
    /**
     * Compare nodes with branches before leaves and labels in locale order.
     *
     * @param {MemoryNode} left First node in the sort comparison.
     * @param {MemoryNode} right Second node in the sort comparison.
     * @returns {number} Negative, zero, or positive value compatible with `Array.sort`.
     */
    compareNodes(left, right) {
        const branchDelta = Number(right.children.size > 0) - Number(left.children.size > 0);
        return branchDelta || left.label.localeCompare(right.label);
    }
}

cache=(()=>{return { MemoryTreeProjector: MemoryTreeProjector };})();return cache;};})();
const __brainExplorerModule43=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule4();
/**
 * Render the inert loading placeholder used by Memory content operations.
 *
 * The function owns markup composition only. Callers retain responsibility for
 * deciding when the loading state is visible and for supplying trusted UI copy.
 *
 * @param {string} label Human-readable operation currently preparing Memory content.
 * @returns {string} Static HTML for the standardized animated loading indicator.
 */
function renderMemoryLoadingState(label) {
    return `
        <div class="loading-state">
            <span></span>
            <strong>${escapeHtml(label)}</strong>
        </div>
    `;
}


cache=(()=>{return { renderMemoryLoadingState: renderMemoryLoadingState };})();return cache;};})();
const __brainExplorerModule44=(()=>{let cache;return()=>{if(cache)return cache;
const { StructureTree } = __brainExplorerModule9();
const { treeActionDetail, treeSelectDetail } = __brainExplorerModule39();
const { escapeHtml, renderMarkdown } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */




/**
 * Browse, inspect, copy, download, and replay persisted voice messages.
 */
class MessagesView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the MessagesView component in the DOM.
     * @returns {string} A string representing the component's DOM selector.
     */
    static get selector() {
        return "brain-messages-view";
    }
    /**
     * Holds a reference to the BrainApiClient instance used for making API requests within the MessagesView component.
     *
     * @type {BrainApiClient | null}
     */
    #api = null;
    /**
     * Holds the current application state for the messages view or remains null if the state is not yet initialized.
     *
     * @type {AppState | null}
     */
    #state = null;
    /**
     * Maintains a private collection of voice message records within the view state.
     *
     * @type {VoiceMessageRecord[]}
     */
    #messages = [];
    /**
     * Maintains a private collection of voice speaking records associated with the messages view.
     *
     * @type {VoiceSpeakRecord[]}
     */
    #speaks = [];
    /**
     * Maintains a private collection of avatar message records representing the conversation history.
     *
     * @type {AvatarMessageRecord[]}
     */
    #history = [];
    /**
     * Maintains a private collection of active avatar message sessions within the view.
     *
     * @type {AvatarMessageSession[]}
     */
    #sessions = [];
    /**
     * Stores the unique identifier of the currently active messaging session.
     *
     * @type {string}
     */
    #selectedSessionId = "";
    /**
     * Tracks the loading state of the messages view to indicate whether data is currently being fetched.
     *
     * @type {boolean}
     */
    #loading = false;
    /**
     * Stores the name of the currently playing track as a private class property.
     *
     * @type {string}
     */
    #playingName = "";
    /**
     * Tracks the active timer identifier for periodic message refreshing or is null when no refresh is scheduled.
     *
     * @type {number | null}
     */
    #refreshTimer = null;
    /**
     * Tracks the active timeout identifier for message status updates to enable cancellation or rescheduling.
     *
     * @type {number | null}
     */
    #statusTimer = null;
    /**
     * Maintains the unique identifier of the currently active speaking entity within the messages view.
     *
     * @type {string}
     */
    #activeSpeakId = "";
    /**
     * Tracks the current operational status of the messaging service, initializing to a stopped state.
     *
     * @type {string}
     */
    #serviceState = "stopped";
    /**
     * Tracks the set of unique identifiers for messages currently in an expanded state within the view.
     *
     * @type {Set<string>}
     */
    #expandedIds = new Set();
    /**
     * Maintains a unique collection of active path identifiers for expanded nodes within the messages tree view.
     *
     * @type {Set<string>}
     */
    #expandedTreePaths = new Set();
    /**
     * Tracks the unique identifiers of audio files currently in the process of being generated to prevent duplicate requests.
     *
     * @type {Set<string>}
     */
    #generatingAudioIds = new Set();
    /**
     * Maintains a mapping of generated audio identifiers to their corresponding speak IDs for tracking audio playback state.
     *
     * @type {Map<string, string>}
     */
    #generatedAudioSpeakIds = new Map();
    /**
     * Stores the data of a target entity awaiting a pending operation or navigation transition.
     *
     * @type {Record<string, unknown> | null}
     */
    #pendingTarget = null;
    /**
     * Assigns the component context to initialize API and state references, resolves the route target, and triggers initial message loading and voice status polling.
     * @param {ComponentContext} context The component context providing access to the API and state management.
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#pendingTarget = this.#state?.consumeRouteTarget?.("messages") || null;
        void this.#loadMessages();
        void this.#pollVoiceStatus();
    }
    /**
     * Triggers the initial rendering of the component when it is attached to the document DOM.
     */
    connectedCallback() {
        this.#render();
    }
    /**
     * Performs cleanup by stopping audio playback and clearing active refresh and status timers when the component is removed from the DOM.
     */
    disconnectedCallback() {
        this.#stopAudio();
        if (this.#refreshTimer !== null)
            window.clearTimeout(this.#refreshTimer);
        if (this.#statusTimer !== null)
            window.clearTimeout(this.#statusTimer);
    }
    /**
     * Synchronize playback controls exclusively from the daemon's latest status.
     */
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
    /**
     * Asynchronously fetches voice messages and session data from the API, updates the internal state, and schedules a recurring refresh timer.
     * @param {boolean} silent Determines whether to suppress the loading state and associated UI re-renders during the fetch process.
     */
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
            if (this.#pendingTarget && this.#sessions.length) {
                const target = this.#pendingTarget;
                this.#pendingTarget = null;
                this.#selectedSessionId = String(target.sessionId || this.#selectedSessionId || this.#sessions[0]?.id || "");
                const targetSession = this.#sessions.find(session => session.id === this.#selectedSessionId);
                if (targetSession)
                    this.#expandSessionPath(targetSession);
                if (target.messageId)
                    this.#expandedIds.add(String(target.messageId));
                await this.#loadMessages(true);
                return;
            }
            if (!this.#selectedSessionId && this.#sessions.length) {
                const firstSession = this.#sessions[0];
                if (!firstSession)
                    return;
                this.#selectedSessionId = firstSession.id;
                this.#expandSessionPath(firstSession);
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
    /**
     * Updates the component's inner HTML to render the messages console layout and attaches event listeners for message playback, expansion, copying, and audio generation.
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface messages-console">
                <div class="structure-layout messages-structure">
                    <aside class="structure-tree" aria-label="Message sessions">
                        <brain-structure-tree data-role="message-session-tree"></brain-structure-tree>
                    </aside>
                    <main class="structure-content">
                        <header class="content-head">
                            <strong>${escapeHtml(this.#selectedSessionLabel())}</strong>
                            <span>${this.#selectedSessionId && this.#history.length ? `${this.#history.length} messages` : ""}</span>
                        </header>
                        <section class="voice-message-list" aria-label="Session messages">
                            ${this.#loading ? `<div class="loading-state"><span></span><strong>Loading messages...</strong></div>` : this.#renderMessages()}
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
    /**
     * Generates an HTML string representing the message history list or an empty state view based on the current session selection and history availability.
     * @returns {string} An HTML string containing either a prompt to select a session, a no-messages notification, or a concatenated list of rendered message items.
     */
    #renderMessages() {
        if (!this.#selectedSessionId) {
            return `<div class="voice-empty-state">${icon("messageCircle")}<strong>Select a session</strong></div>`;
        }
        if (!this.#history.length) {
            return `<div class="voice-empty-state">${icon("messageCircle")}<strong>This session has no messages</strong></div>`;
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
    /**
     * Project durable summaries into the shared Explorer tree contract.
     * @returns {StructureTreeNode[]} An array of StructureTreeNode objects representing the nested temporal hierarchy of message sessions.
     */
    #sessionTreeNodes() {
        const years = new Map();
        this.#sessions.forEach(session => {
            const [year = "unknown", month = "unknown", day = "unknown"] = session.date.split("-");
            let months = years.get(year);
            if (!months) {
                months = new Map();
                years.set(year, months);
            }
            let days = months.get(month);
            if (!days) {
                days = new Map();
                months.set(month, days);
            }
            let sessions = days.get(day);
            if (!sessions) {
                sessions = [];
                days.set(day, sessions);
            }
            sessions.push(session);
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
                        label: session.chatId ? session.label : `Session ${this.#formatTime(session.startedAt)}`,
                        icon: "messageCircle",
                        count: session.messageCount
                    }))
                }))
            }))
        }));
    }
    /**
     * Configure the reusable structural tree with message session nodes.
     */
    #configureTree() {
        const tree = this.querySelector("[data-role='message-session-tree']");
        if (!(tree instanceof StructureTree))
            return;
        tree.model = {
            nodes: this.#sessionTreeNodes(),
            selectedPath: this.#selectedSessionId,
            expandedPaths: this.#expandedTreePaths,
            toggleOnBranchSelect: true,
            title: "Messages",
            toolbarActions: [{ id: "refresh", label: "Refresh messages", icon: "refresh" }],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "messageCircle",
            searchPlaceholder: "Search sessions...",
            emptyText: this.#loading ? "Loading sessions..." : "No stored sessions."
        };
        tree.addEventListener("brain-tree-select", event => {
            const detail = event instanceof CustomEvent ? treeSelectDetail(event.detail) : null;
            if (!detail)
                return;
            if (!detail.branch)
                void this.#selectSession(detail.path);
        });
        tree.addEventListener("brain-tree-toolbar-action", event => {
            const detail = event instanceof CustomEvent ? treeActionDetail(event.detail) : null;
            if (detail?.action === "refresh")
                void this.#loadMessages();
        });
    }
    /**
     * Expand the ancestors of the active session in the shared tree.
     * @param {AvatarMessageSession} session The message session containing the date string used to generate the directory hierarchy.
     */
    #expandSessionPath(session) {
        const [year = "unknown", month = "unknown", day = "unknown"] = session.date.split("-");
        this.#expandedTreePaths.add(`messages/${year}`);
        this.#expandedTreePaths.add(`messages/${year}/${month}`);
        this.#expandedTreePaths.add(`messages/${year}/${month}/${day}`);
    }
    /**
     * Return the content-panel heading for the selected session.
     * @returns {string} A string representing the session's chat ID, its label, or a formatted timestamp of its start time.
     */
    #selectedSessionLabel() {
        const session = this.#sessions.find(candidate => candidate.id === this.#selectedSessionId);
        if (!session)
            return "Select a session";
        return session.chatId ? session.label : `Session on ${session.date} at ${this.#formatTime(session.startedAt)}`;
    }
    /**
     * Select a durable session and request only its messages.
     * @param {string} id The unique identifier of the session to be selected.
     */
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
    /**
     * Generates an HTML string representing a single voice message item, including its header, status, and optional expanded detail view.
     * @param {AvatarMessageRecord} record The core message data containing the ID, text, timestamp, and source information.
     * @param {VoiceSpeakRecord | null} speak The current voice synthesis status and potential error details.
     * @param {VoiceMessageRecord | undefined} message The metadata for the generated audio file, used for download links.
     * @returns {string} An HTML string containing the markup for the message item.
     */
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
                        ${speak?.error ? `<section class="voice-error-detail" role="alert"><strong>Error details</strong><pre>${escapeHtml(speak.error)}</pre></section>` : ""}
                        <footer class="voice-message-footer">
                            <div class="voice-message-actions">
                                ${name
            ? `<button class="voice-icon-action" data-action="play-message" data-name="${escapeHtml(name)}" title="Play message" aria-label="Play message">${icon(name === this.#playingName ? "pause" : "play")}</button>`
            : `<button class="voice-icon-action" data-action="generate-message-audio" data-message-id="${escapeHtml(id)}" ${generatingAudio ? "disabled" : ""} title="Generate audio" aria-label="Generate audio">${icon("volume")}</button>`}
                                ${message ? `<a class="voice-download-button labeled" href="${this.#api?.voiceMessageUrl(message.name) ?? "#"}" download="${escapeHtml(message.name)}" title="Download message">${icon("download")} ${this.#formatBytes(message.sizeBytes)}</a>` : ""}
                                <button class="voice-icon-action" data-action="copy-message" data-text="${escapeHtml(text)}" title="Copy message" aria-label="Copy message">${icon("copy")}</button>
                            </div>
                        </footer>
                    </div>
                ` : ""}
            </article>
        `;
    }
    /**
     * Render the primary list action as replay or on-demand audio generation.
     * @param {string} id The unique identifier of the message used for audio generation requests.
     * @param {string} name The identifier of the audio file to play, or a falsy value if audio must be generated.
     * @param {boolean} generatingAudio A flag indicating whether the audio generation process is currently active to disable the button.
     * @returns {string} An HTML string representing the audio action button with appropriate attributes and icons based on the message state.
     */
    #renderLeadingAudioAction(id, name, generatingAudio) {
        if (name) {
            const playing = name === this.#playingName;
            return `<button class="voice-icon-action voice-message-leading-action" data-action="play-message" data-name="${escapeHtml(name)}" title="${playing ? "Pause message" : "Play message"}" aria-label="${playing ? "Pause message" : "Play message"}">${icon(playing ? "pause" : "play")}</button>`;
        }
        return `<button class="voice-icon-action voice-message-leading-action" data-action="generate-message-audio" data-message-id="${escapeHtml(id)}" ${generatingAudio ? "disabled" : ""} title="Generate and play audio" aria-label="Generate and play audio">${icon("play")}</button>`;
    }
    /**
     * Copies the text content from a button's data attribute to the system clipboard and updates the button's tooltip title.
     * @param {Element} button The DOM element containing the text to be copied in its data-text attribute.
     */
    async #copyMessage(button) {
        await navigator.clipboard.writeText(button.getAttribute("data-text") || "");
        button.setAttribute("title", "Copiado");
    }
    /**
     * Request one non-persistent audio rendering for a historical message.
     * @param {string} id The unique identifier of the message to be synthesized into audio.
     */
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
    /**
     * Refresh briefly until the daemon exposes the newly retained MP3.
     * @param {string} speakId The unique identifier of the generated audio message to wait for.
     */
    async #waitForGeneratedAudio(speakId) {
        for (let attempt = 0; attempt < 20; attempt += 1) {
            await new Promise(resolve => window.setTimeout(resolve, 500));
            await this.#loadMessages(true);
            if (this.#messages.some(message => message.speakId === speakId))
                return;
        }
    }
    /**
     * Toggle one bubble while restoring keyboard focus after the DOM refresh.
     * @param {string} id The unique identifier of the message to be expanded or collapsed.
     */
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
    /**
     * Focus one summary and keep its expanded card inside the message viewport.
     * @param {string} id The unique identifier of the message summary element to be focused.
     * @param {boolean} expanded A flag determining whether the view should scroll to ensure the message item is visible.
     */
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
    /**
     * Toggles the playback of a voice message by either pausing the current replay or initiating a new one based on the provided message identifier and current service state.
     * @param {string} name The unique identifier of the voice message to be toggled.
     */
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
    /**
     * Resets the internal tracking of the currently playing audio by clearing the playing name state.
     */
    #stopAudio() {
        this.#playingName = "";
    }
    /**
     * Formats an ISO or date string into a localized English time string containing only hours and minutes.
     * @param {string} value The date string to be parsed and formatted.
     * @returns {string} A string representing the time in 2-digit hour and minute format.
     */
    #formatTime(value) {
        return new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
    }
    /**
     * Converts a numeric month string into its full English name using the Intl.DateTimeFormat API.
     * @param {string} value The numeric representation of the month to be formatted.
     * @returns {string} The full English name of the month.
     */
    #monthLabel(value) {
        const date = new Date(2026, Number(value) - 1, 1);
        return new Intl.DateTimeFormat("en", { month: "long" }).format(date);
    }
    /**
     * Converts a numeric byte value into a rounded kilobyte string representation with a minimum floor of 1 KB.
     * @param {number} value The number of bytes to be formatted.
     * @returns {string} A string representing the size in kilobytes followed by the 'KB' unit suffix.
     */
    #formatBytes(value) {
        return `${Math.max(1, Math.round(value / 1024))} KB`;
    }
}
customElements.define(MessagesView.selector, MessagesView);

cache=(()=>{return { MessagesView: MessagesView };})();return cache;};})();
const __brainExplorerModule45=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
const { renderDescriptionCard } = __brainExplorerModule27();
const { StructureTree } = __brainExplorerModule9();
const { PictureDomainTreeProjector } = __brainExplorerModule46();
/**
 * Modern registry-backed picture browser and carousel.
 */





void StructureTree;
/**
 * A custom HTML element that manages the browsing, selection, and viewing of picture records organized by domains via an API.
 */
class PicturesView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the PicturesView component in the DOM.
     * @returns {string} A string representing the component's DOM selector.
     */
    static get selector() {
        return "brain-pictures-view";
    }
    /**
     * Holds a reference to the BrainApiClient instance used for data operations within the PicturesView, defaulting to null.
     *
     * @type {BrainApiClient | null}
     */
    #api = null;
    /**
     * Holds the current application state for the pictures view or remains null if the state is not yet initialized.
     *
     * @type {AppState | null}
     */
    #state = null;
    /**
     * Maintains a private collection of picture records used within the view layout.
     *
     * @type {PictureRecord[]}
     */
    #pictures = [];
    /**
     * Maintains a private mapping of domain identifiers to their associated collections of picture records.
     *
     * @type {Map<string, PictureRecord[]>}
     */
    #picturesByDomain = new Map();
    /**
     * Maintains a mapping of domain identifiers to their associated numerical counts.
     *
     * @type {Record<string, number>}
     */
    #domains = {};
    /**
     * Stores the current domain identifier used for filtering or scoping the pictures view.
     *
     * @type {string}
     */
    #domain = "";
    /**
     * Tracks whether the domain-specific focus state is currently active within the pictures view.
     *
     * @type {boolean}
     */
    #domainFocused = false;
    /**
     * Maintains the unique identifier of the currently selected picture within the view state.
     *
     * @type {string}
     */
    #selectedId = "";
    /**
     * Tracks the loading state of the pictures view to manage the visibility of loading indicators.
     *
     * @type {boolean}
     */
    #loading = false;
    /**
     * Tracks whether a request to fetch picture descriptions is currently in progress.
     *
     * @type {boolean}
     */
    #descriptionRequestPending = false;
    /**
     * Tracks whether the picture description is currently in an editing state.
     *
     * @type {boolean}
     */
    #descriptionEditing = false;
    /**
     * Tracks the active timeout reference for the copy-to-clipboard feedback duration.
     *
     * @type {number | null}
     */
    #copyFeedbackTimer = null;
    /**
     * Maintains the current search query string used to filter the pictures view.
     *
     * @type {string}
     */
    #search = "";
    /**
     * Maintains a set of currently expanded domain identifiers, initialized with the global pictures collection.
     *
     * @type {Set<string>}
     */
    #expandedDomains = new Set(["pictures:all"]);
    /**
     * Initializes a private numeric token used to track or trigger the hydration process of images within the view.
     *
     * @type {number}
     */
    #imageHydrationToken = 0;
    /**
     * Tracks the visibility state of the image viewer component.
     *
     * @type {boolean}
     */
    #viewerOpen = false;
    /**
     * Maintains the current magnification level of the picture viewer.
     *
     * @type {number}
     */
    #viewerScale = 1;
    /**
     * Stores the horizontal coordinate of the picture viewer.
     *
     * @type {number}
     */
    #viewerX = 0;
    /**
     * Tracks the vertical coordinate offset of the picture viewer.
     *
     * @type {number}
     */
    #viewerY = 0;
    /**
     * Stores the unique identifier of the currently active viewer pointer, or null if no pointer is active.
     *
     * @type {number | null}
     */
    #viewerPointerId = null;
    /**
     * Holds the reference to a timeout timer used to manage the scaling state of the picture viewer.
     *
     * @type {number | null}
     */
    #viewerScaleTimer = null;
    /**
     * Stores the initial coordinate state and origin offsets for the viewer's pointer interaction.
     *
     * @type {{ x: number; y: number; originX: number; originY: number; }}
     */
    #viewerPointerStart = { x: 0, y: 0, originX: 0, originY: 0 };
    /**
     * Processes keyboard input to control image viewer navigation, zooming, and visibility based on the current viewer state.
     *
     * @type {(event: KeyboardEvent) => void}
     */
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
    /**
     * Assigns the component context to initialize API and state references, synchronize the selected picture ID from the route target, and trigger the initial render and data load.
     * @param {ComponentContext} context The component context providing access to the application API and state management.
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        const target = this.#state?.consumeRouteTarget?.("pictures") || null;
        this.#selectedId = String(target?.pictureId || "");
        this.#render();
        void this.#loadStructure();
    }
    /**
     * Registers a global keyboard event listener and triggers the initial component rendering when the element is added to the DOM.
     */
    connectedCallback() {
        window.addEventListener("keydown", this.#handleKeyDown);
        this.#render();
    }
    /**
     * Cleans up global event listeners and active timers when the component is removed from the DOM.
     */
    disconnectedCallback() {
        window.removeEventListener("keydown", this.#handleKeyDown);
        if (this.#viewerScaleTimer !== null)
            clearTimeout(this.#viewerScaleTimer);
        if (this.#copyFeedbackTimer !== null)
            clearTimeout(this.#copyFeedbackTimer);
    }
    /**
     * Load the complete hierarchy once without eagerly returning picture records.
     * @param {boolean} forceRefresh A boolean flag indicating whether to bypass cached data and clear the existing pictures-by-domain mapping.
     */
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
    /**
     * Resolve a routed picture to its domain without loading the global registry.
     * @param {string} pictureId The unique identifier of the picture to be retrieved.
     */
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
    /**
     * Hydrate and cache one domain only when its tree item receives focus.
     * @param {string} domain The unique identifier of the domain to load pictures from.
     * @param {boolean} forceRefresh A flag indicating whether to bypass the local cache and fetch fresh data from the API.
     * @param {string} preferredId The identifier of the specific picture to be selected after the domain data is loaded.
     */
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
    /**
     * Preserve a routed/current selection when it belongs to the loaded domain.
     * @param {string} preferredId The optional identifier of the picture to be selected.
     */
    #selectLoadedDomain(preferredId = "") {
        const candidate = preferredId || this.#selectedId;
        this.#selectedId = this.#pictures.some(picture => picture.id === candidate)
            ? candidate
            : this.#pictures[0]?.id ?? "";
        this.#descriptionEditing = false;
    }
    /**
     * Retrieves the picture record that matches the currently stored selected identifier.
     * @returns {PictureRecord | null} The matching PictureRecord if found, otherwise null.
     */
    #selected() {
        return this.#pictures.find(picture => picture.id === this.#selectedId) ?? null;
    }
    /**
     * Updates the currently selected picture by shifting the selection index by a specified offset, wrapping around the collection boundaries.
     * @param {number} delta The numeric offset to move the selection forward or backward.
     */
    #selectRelative(delta) {
        if (!this.#pictures.length)
            return;
        const index = Math.max(0, this.#pictures.findIndex(picture => picture.id === this.#selectedId));
        const next = (index + delta + this.#pictures.length) % this.#pictures.length;
        const picture = this.#pictures[next];
        if (picture)
            this.#selectPicture(picture.id);
    }
    /**
     * Update an existing carousel in place and hydrate its raster when ready.
     * @param {string} pictureId The unique identifier of the picture to be selected.
     */
    #selectPicture(pictureId) {
        const picture = this.#pictures.find(candidate => candidate.id === pictureId);
        if (!picture || picture.id === this.#selectedId)
            return;
        this.#selectedId = picture.id;
        this.#descriptionEditing = false;
        this.#hydrateSelection(picture);
        this.#focusSelectedThumbnail();
    }
    /**
     * Updates the component's innerHTML to render the pictures gallery interface, including the domain tree, image carousel, and inspector panel, based on the current selection and loading state.
     */
    #render() {
        const selected = this.#selected();
        const selectedIndex = selected ? this.#pictures.findIndex(picture => picture.id === selected.id) : -1;
        this.innerHTML = `
            <section class="page-surface pictures-console">
                <div class="structure-layout pictures-layout">
                    <aside class="structure-tree pictures-domains" aria-label="Picture domains">
                        <div class="tree-list scroll-list">
                            <brain-structure-tree data-role="pictures-domain-tree"></brain-structure-tree>
                        </div>
                    </aside>
                    <main class="pictures-stage">
                    ${this.#loading ? `<div class="loading-state"><span></span><strong>Syncing pictures...</strong></div>` : selected ? `
                        <section class="picture-carousel" aria-label="Picture carousel">
                            <header>
                                <div><span class="status-pill" data-role="picture-domain">${escapeHtml(selected.domain)}</span><strong data-role="picture-filename">${escapeHtml(selected.filename)}</strong></div>
                                <span data-role="picture-position">${selectedIndex + 1} / ${this.#pictures.length}</span>
                            </header>
                            <div class="picture-viewport">
                                <button class="carousel-arrow is-previous" data-action="previous-picture" aria-label="Previous picture">${icon("chevronRight")}</button>
                                <div class="picture-render-layer">
                                    <button class="picture-render-trigger" data-action="open-picture-viewer" aria-label="Open ${escapeHtml(selected.filename)} in fullscreen viewer">
                                        <img data-role="selected-picture-image" src="${this.#api?.pictureUrl(selected.id) ?? ""}" alt="${escapeHtml(selected.description || selected.filename)}" loading="eager" decoding="async" fetchpriority="high">
                                    </button>
                                </div>
                                <button class="carousel-arrow is-next" data-action="next-picture" aria-label="Next picture">${icon("chevronRight")}</button>
                            </div>
                            <div class="picture-thumbnails" role="listbox" aria-label="Thumbnails">
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
                                <div class="picture-path-row">
                                    <dt>Path</dt>
                                    <dd>
                                        <span data-role="picture-path">${escapeHtml(selected.relative_path)}</span>
                                        <button class="picture-copy-path" data-action="copy-picture-path" data-copy-path="${escapeHtml(selected.absolute_path || "")}" title="Copy absolute path" aria-label="Copy absolute picture path">
                                            ${icon("copy")}<span>Copy</span>
                                        </button>
                                    </dd>
                                </div>
                                <div><dt>Type</dt><dd data-role="picture-mime">${escapeHtml(selected.mime_type)}</dd></div>
                                <div><dt>Size</dt><dd data-role="picture-size">${this.#formatBytes(selected.size_bytes)}</dd></div>
                                <div><dt>Description</dt><dd data-role="picture-description-source">${escapeHtml(selected.description_source || "pending")}</dd></div>
                            </dl>
                            ${this.#renderDescriptionPanel(selected)}
                        </aside>
                    ` : `<section class="search-empty">${icon("camera")}<h2>${this.#domainFocused ? "No pictures" : "Select a domain"}</h2><p>${this.#domainFocused ? "No pictures are registered in this domain." : "The tree is ready; pictures load when an item is focused."}</p></section>`}
                    </main>
                </div>
                ${selected ? this.#renderViewer(selected) : ""}
            </section>
        `;
        this.#configureDomainTree();
        this.#bindEvents();
    }
    /**
     * Center and focus the active option without rebuilding or animating from scroll origin.
     */
    #focusSelectedThumbnail() {
        const selected = this.querySelector('.picture-thumbnails [role="option"][aria-selected="true"]');
        selected?.scrollIntoView({ behavior: "auto", block: "nearest", inline: "center" });
        selected?.focus({ preventScroll: true });
    }
    /**
     * Patch carousel metadata immediately and replace only the raster after it loads.
     * @param {PictureRecord} picture The picture record containing the metadata and identifiers used to populate the UI.
     */
    #hydrateSelection(picture) {
        const position = this.#pictures.findIndex(candidate => candidate.id === picture.id) + 1;
        this.#setText("picture-domain", picture.domain);
        this.#setText("picture-filename", picture.filename);
        this.#setText("picture-position", `${position} / ${this.#pictures.length}`);
        this.#setText("picture-dimensions", `${picture.width} × ${picture.height}`);
        this.#setText("picture-path", picture.relative_path);
        const copyPath = this.querySelector("[data-action='copy-picture-path']");
        if (copyPath) {
            copyPath.dataset.copyPath = picture.absolute_path || "";
            copyPath.disabled = !picture.absolute_path;
        }
        this.#setText("picture-mime", picture.mime_type);
        this.#setText("picture-size", this.#formatBytes(picture.size_bytes));
        this.#setText("picture-description-source", picture.description_source || "pending");
        this.#mountDescriptionPanel(picture);
        const trigger = this.querySelector("[data-action='open-picture-viewer']");
        trigger?.setAttribute("aria-label", `Open ${picture.filename} in fullscreen viewer`);
        this.querySelectorAll("[data-picture-id]").forEach(option => {
            option.setAttribute("aria-selected", String(option.dataset.pictureId === picture.id));
        });
        this.#hydrateSelectedRaster(picture);
    }
    /**
     * Load the next raster off-DOM and commit only the newest completed request.
     * @param {PictureRecord} picture The picture record containing the identifier and metadata used to fetch and display the image.
     */
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
    /**
     * Replace one render field without reconstructing its surrounding component.
     * @param {string} role The unique identifier used in the data-role attribute to locate the target element.
     * @param {string} value The string to be assigned to the element's text content.
     */
    #setText(role, value) {
        const element = this.querySelector(`[data-role='${role}']`);
        if (element)
            element.textContent = value;
    }
    /**
     * Render the fullscreen viewer for the selected canonical picture.
     * @param {PictureRecord} selected The picture record containing the metadata and identifier used to populate the viewer's content and source URL.
     * @returns {string} An HTML string representing the viewer dialog, or an empty string if the viewer is closed.
     */
    #renderViewer(selected) {
        if (!this.#viewerOpen)
            return "";
        return `
            <section class="picture-viewer" role="dialog" aria-modal="true" aria-label="Fullscreen viewer for ${escapeHtml(selected.filename)}">
                <strong class="picture-viewer-title">${escapeHtml(selected.filename)}</strong>
                <button class="picture-viewer-close" data-action="close-picture-viewer" aria-label="Close viewer">${icon("close")}</button>
                <div class="picture-viewer-zoom-fabs" aria-label="Zoom controls">
                    <button data-action="viewer-zoom-in" aria-label="Zoom in">${icon("plus")}</button>
                    <button data-action="viewer-zoom-out" aria-label="Zoom out">${icon("minus")}</button>
                    <button data-action="viewer-reset" aria-label="Reset zoom and position">${icon("refresh")}</button>
                </div>
                <output class="picture-viewer-scale" data-role="viewer-scale">${Math.round(this.#viewerScale * 100)}%</output>
                <div class="picture-viewer-viewport" data-role="picture-viewer-viewport">
                    <img data-role="picture-viewer-image" src="${this.#api?.pictureUrl(selected.id) ?? ""}" alt="${escapeHtml(selected.description || selected.filename)}" draggable="false"
                        style="transform: translate3d(${this.#viewerX}px, ${this.#viewerY}px, 0) scale(${this.#viewerScale})">
                </div>
            </section>
        `;
    }
    /**
     * Open the selected picture in the fullscreen viewer.
     */
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
    /**
     * Close the fullscreen viewer and return focus to the carousel image.
     */
    #closeViewer() {
        this.#viewerOpen = false;
        this.#viewerPointerId = null;
        if (this.#viewerScaleTimer !== null)
            clearTimeout(this.#viewerScaleTimer);
        this.#viewerScaleTimer = null;
        this.querySelector(".picture-viewer")?.remove();
        requestAnimationFrame(() => this.querySelector("[data-action='open-picture-viewer']")?.focus());
    }
    /**
     * Clamp and apply one relative viewer zoom step.
     * @param {number} delta The numeric value to add to the current scale factor.
     */
    #zoomViewer(delta) {
        this.#viewerScale = Math.min(8, Math.max(0.5, this.#viewerScale + delta));
        if (this.#viewerScale === 1) {
            this.#viewerX = 0;
            this.#viewerY = 0;
        }
        this.#applyViewerTransform(true);
    }
    /**
     * Restore the fullscreen image transform.
     */
    #resetViewer() {
        this.#resetViewerState();
        this.#applyViewerTransform(true);
    }
    /**
     * Reset viewer coordinates without causing a component render.
     */
    #resetViewerState() {
        this.#viewerScale = 1;
        this.#viewerX = 0;
        this.#viewerY = 0;
    }
    /**
     * Apply the current pan and zoom state to the mounted fullscreen image.
     * @param {boolean} showScale Determines whether the scale indicator visibility should be triggered.
     */
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
    /**
     * Reveal the scale indicator and hide it three seconds after the latest zoom change.
     */
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
    /**
     * Begin one mouse, pen, or touch panning gesture.
     * @param {PointerEvent} event The pointer event containing the unique pointer identifier and initial screen coordinates.
     * @param {HTMLElement} viewport The HTML element used to capture the pointer and receive the panning CSS class.
     */
    #startViewerPan(event, viewport) {
        this.#viewerPointerId = event.pointerId;
        this.#viewerPointerStart = { x: event.clientX, y: event.clientY, originX: this.#viewerX, originY: this.#viewerY };
        viewport.setPointerCapture(event.pointerId);
        viewport.classList.add("is-panning");
    }
    /**
     * Continue the active panning gesture without rebuilding the carousel.
     * @param {PointerEvent} event The pointer event containing the current client coordinates and unique pointer identifier.
     */
    #moveViewerPan(event) {
        if (this.#viewerPointerId !== event.pointerId)
            return;
        this.#viewerX = this.#viewerPointerStart.originX + event.clientX - this.#viewerPointerStart.x;
        this.#viewerY = this.#viewerPointerStart.originY + event.clientY - this.#viewerPointerStart.y;
        this.#applyViewerTransform();
    }
    /**
     * Finish the active panning gesture.
     * @param {PointerEvent} event The pointer event triggering the end of the pan operation.
     * @param {HTMLElement} viewport The HTML element acting as the panning container and pointer capture target.
     */
    #endViewerPan(event, viewport) {
        if (this.#viewerPointerId !== event.pointerId)
            return;
        this.#viewerPointerId = null;
        if (viewport.hasPointerCapture(event.pointerId))
            viewport.releasePointerCapture(event.pointerId);
        viewport.classList.remove("is-panning");
    }
    /**
     * Project dot-separated picture domains into the shared Explorer tree contract.
     * @returns {import("D:/.agents/@Angi/core/brain_explorer/src/presentation/shared/view_models/structure-tree-view-model").StructureTreeNode[]} The result of the projection process from the PictureDomainTreeProjector.
     */
    #domainTreeNodes() {
        return new PictureDomainTreeProjector(this.#domains).project();
    }
    /**
     * Configure Pictures with the standardized structural tree component.
     */
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
            toolbarActions: [{ id: "refresh", label: "Refresh pictures", icon: "refresh" }],
            searchQuery: this.#search,
            searchPlaceholder: "Search pictures...",
            emptyText: this.#loading ? "Syncing pictures..." : "No registered domains.",
            defaultBranchIcon: "folder",
            defaultLeafIcon: "folder"
        };
        tree.addEventListener("brain-tree-select", event => {
            if (!(event instanceof CustomEvent))
                return;
            if (event.detail.clickedCaret)
                return;
            this.#domain = String(event.detail.path || "");
            this.#domainFocused = true;
            void this.#loadDomain(this.#domain);
        });
        tree.addEventListener("brain-tree-toolbar-action", event => {
            if (event instanceof CustomEvent && event.detail.action === "refresh")
                void this.#loadStructure(true);
        });
        tree.addEventListener("brain-tree-search", event => {
            if (event instanceof CustomEvent)
                this.#search = String(event.detail.query || "").trim();
        });
    }
    /**
     * Attaches click event listeners to navigation controls, picture selection buttons, and viewer actions within the component's DOM.
     */
    #bindEvents() {
        this.querySelector("[data-action='previous-picture']")?.addEventListener("click", () => this.#selectRelative(-1));
        this.querySelector("[data-action='next-picture']")?.addEventListener("click", () => this.#selectRelative(1));
        this.querySelectorAll("[data-picture-id]").forEach(button => button.addEventListener("click", () => {
            this.#selectPicture(button.getAttribute("data-picture-id") || "");
        }));
        this.#bindDescriptionEvents();
        this.querySelector("[data-action='copy-picture-path']")?.addEventListener("click", event => {
            if (event.currentTarget instanceof HTMLButtonElement)
                void this.#copyPicturePath(event.currentTarget);
        });
        this.querySelector("[data-action='open-picture-viewer']")?.addEventListener("click", () => this.#openViewer());
        this.#bindViewerEvents();
    }
    /**
     * Copy the server-resolved canonical image path and expose feedback in place.
     * @param {HTMLButtonElement} button The HTML button element containing the path to be copied in its data-copy-path attribute.
     */
    async #copyPicturePath(button) {
        const absolutePath = button.dataset.copyPath || "";
        if (!absolutePath || !navigator.clipboard?.writeText)
            return;
        if (this.#copyFeedbackTimer !== null)
            clearTimeout(this.#copyFeedbackTimer);
        try {
            await navigator.clipboard.writeText(absolutePath);
            button.innerHTML = `${icon("checkSquare")}<span>Copied</span>`;
            button.title = absolutePath;
            this.#copyFeedbackTimer = setTimeout(() => {
                button.innerHTML = `${icon("copy")}<span>Copy</span>`;
                button.title = "Copy absolute path";
                this.#copyFeedbackTimer = null;
            }, 2200);
        }
        catch (_error) {
            button.innerHTML = `${icon("pulse")}<span>Copy failed</span>`;
        }
    }
    /**
     * Render the mutually exclusive read and edit states for one description.
     * @param {PictureRecord} picture The picture record containing the description text to be displayed or edited.
     * @returns {string} An HTML string representing the rendered description panel.
     */
    #renderDescriptionPanel(picture) {
        if (!this.#descriptionEditing) {
            return `
                <section class="picture-description-panel" data-role="picture-description-panel" data-mode="read">
                    <div class="picture-description-toolbar">
                        <strong>Description</strong>
                        <button class="secondary-action" data-action="edit-picture-description">${icon("edit")} Edit</button>
                    </div>
                    ${renderDescriptionCard(picture.description, { title: "Image analysis" })}
                </section>
            `;
        }
        return `
            <section class="picture-description-panel" data-role="picture-description-panel" data-mode="edit">
                <label>Description editor
                    <textarea data-role="picture-description" placeholder="Describe people, scene, objects, text, and context...">${escapeHtml(picture.description)}</textarea>
                </label>
                <div class="picture-description-actions">
                    <button class="secondary-action" data-action="cancel-picture-description">${icon("close")} Cancel</button>
                    <button class="secondary-action" data-action="generate-picture-description">${icon("camera")} Regenerate</button>
                    <button class="primary-button" data-action="save-picture-description">${icon("save")} Save</button>
                </div>
            </section>
        `;
    }
    /**
     * Replace only the description surface so carousel and image state remain mounted.
     * @param {PictureRecord} picture The picture record containing the data to be displayed in the description panel.
     */
    #mountDescriptionPanel(picture) {
        const panel = this.querySelector("[data-role='picture-description-panel']");
        if (!panel)
            return;
        panel.outerHTML = this.#renderDescriptionPanel(picture);
        this.#bindDescriptionEvents();
    }
    /**
     * Bind controls owned by the current description mode.
     */
    #bindDescriptionEvents() {
        this.querySelector("[data-action='edit-picture-description']")?.addEventListener("click", () => this.#setDescriptionEditing(true));
        this.querySelector("[data-action='cancel-picture-description']")?.addEventListener("click", () => this.#setDescriptionEditing(false));
        this.querySelector("[data-action='save-picture-description']")?.addEventListener("click", () => void this.#saveDescription());
        this.querySelector("[data-action='generate-picture-description']")?.addEventListener("click", () => void this.#generateDescription());
        this.querySelectorAll("[data-action='resolve-description-entity']").forEach(button => {
            button.addEventListener("click", () => {
                this.#state?.setRouteTarget?.("knowledge", { entityLabel: button.getAttribute("data-entity-label") || "" });
            });
        });
    }
    /**
     * Toggle between the structured card and textarea without changing selection.
     * @param {boolean} editing A boolean flag indicating whether to enable or disable the description editing mode.
     */
    #setDescriptionEditing(editing) {
        const selected = this.#selected();
        if (!selected || this.#descriptionRequestPending)
            return;
        this.#descriptionEditing = editing;
        this.#mountDescriptionPanel(selected);
        if (editing)
            requestAnimationFrame(() => this.querySelector("[data-role='picture-description']")?.focus());
    }
    /**
     * Bind controls owned only by a mounted fullscreen viewer.
     */
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
    /**
     * Asynchronously persists the trimmed text from the description textarea to the API for the currently selected picture, provided no request is already pending.
     */
    async #saveDescription() {
        const selected = this.#selected();
        const textarea = this.querySelector("[data-role='picture-description']");
        const api = this.#api;
        if (!selected || !textarea || !api || this.#descriptionRequestPending)
            return;
        await this.#submitDescription(() => api.describePicture(selected.id, textarea.value.trim()), "Saving...");
    }
    /**
     * Generate a model-backed description without overwriting the mounted draft on failure.
     */
    async #generateDescription() {
        const selected = this.#selected();
        const api = this.#api;
        if (!selected || !api || this.#descriptionRequestPending)
            return;
        await this.#submitDescription(() => api.generatePictureDescription(selected.id), "Generating...");
    }
    /**
     * Serialize description mutations and patch the cached record without rebuilding the carousel.
     * @param {() => Promise<ApiResponse<PictureDescriptionPayload>>} request A function that returns a promise resolving to an API response containing the picture description payload.
     * @param {string} pendingLabel The text label to display while the description request is in progress.
     */
    async #submitDescription(request, pendingLabel) {
        this.#descriptionRequestPending = true;
        this.#setDescriptionActionsBusy(true, pendingLabel);
        try {
            const response = await request();
            this.#state?.setLastResult(response);
            const updated = response.data?.picture;
            if (!response.ok || !updated)
                return;
            const index = this.#pictures.findIndex(picture => picture.id === updated.id);
            if (index >= 0)
                this.#pictures[index] = updated;
            this.#picturesByDomain.set(this.#domain, this.#pictures);
            if (this.#selectedId === updated.id) {
                this.#descriptionEditing = false;
                this.#hydrateSelection(updated);
            }
        }
        finally {
            this.#descriptionRequestPending = false;
            this.#setDescriptionActionsBusy(false);
        }
    }
    /**
     * Keep both mutually exclusive description actions synchronized and accessible.
     * @param {boolean} busy A boolean indicating whether the description actions are currently executing and should be disabled.
     * @param {string} pendingLabel An optional string used to set the button text when the action is in a busy state.
     */
    #setDescriptionActionsBusy(busy, pendingLabel = "") {
        const generate = this.querySelector("[data-action='generate-picture-description']");
        const save = this.querySelector("[data-action='save-picture-description']");
        if (generate) {
            generate.disabled = busy;
            generate.setAttribute("aria-busy", String(busy));
            generate.innerHTML = busy && pendingLabel === "Generating..."
                ? `${icon("refresh")} ${pendingLabel}`
                : `${icon("camera")} Regenerate`;
        }
        if (save) {
            save.disabled = busy;
            save.setAttribute("aria-busy", String(busy));
            save.innerHTML = busy && pendingLabel === "Saving..."
                ? `${icon("refresh")} ${pendingLabel}`
                : `${icon("save")} Save description`;
        }
    }
    /**
     * Converts a byte count into a human-readable string formatted as either kilobytes or megabytes.
     * @param {number} bytes The total number of bytes to be formatted.
     * @returns {string} A string representing the size in KB or MB based on the input magnitude.
     */
    #formatBytes(bytes) {
        if (bytes < 1024 * 1024)
            return `${Math.max(1, Math.round(bytes / 1024))} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
}
customElements.define(PicturesView.selector, PicturesView);

cache=(()=>{return { PicturesView: PicturesView };})();return cache;};})();
const __brainExplorerModule46=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */
/**
 * Projects flat picture-domain counts into the recursive tree contract shared by
 * Explorer layouts. Projection is deterministic and does not mutate its input.
 */
class PictureDomainTreeProjector {
    /**
     * Immutable mapping from canonical dotted domains to direct picture counts.
     * @type {Readonly<Record<string, number>>}
     */
    #domainCounts;
    /**
     * Create a projector for one picture registry snapshot.
     *
     * @param {Readonly<Record<string, number>>} domainCounts Canonical domain-to-direct-count mapping from the API.
     */
    constructor(domainCounts) {
        this.#domainCounts = domainCounts;
    }
    /**
     * Build the single-root recursive structure consumed by `StructureTree`.
     * Parent counts include every descendant while leaf counts remain direct.
     *
     * @returns {StructureTreeNode[]} A tree rooted at the canonical all-pictures node.
     */
    project() {
        const root = {
            label: "Todo",
            path: "",
            ownCount: 0,
            children: new Map(),
        };
        Object.entries(this.#domainCounts).forEach(([domain, count]) => {
            let parent = root;
            const parts = domain.split(".").filter(Boolean);
            parts.forEach((label, index) => {
                const path = parts.slice(0, index + 1).join(".");
                let child = parent.children.get(label);
                if (!child) {
                    child = { label, path, ownCount: 0, children: new Map() };
                    parent.children.set(label, child);
                }
                parent = child;
            });
            parent.ownCount += count;
        });
        return [this.#projectNode(root)];
    }
    /**
     * Convert one accumulator and its descendants to the public shared-tree shape.
     *
     * @param {PictureDomainAccumulator} node Accumulator being projected.
     * @returns {StructureTreeNode} Fully projected node with aggregate descendant count.
     */
    #projectNode(node) {
        const children = [...node.children.values()].map(child => this.#projectNode(child));
        const descendantCount = children.reduce((total, child) => total + Number(child.count || 0), 0);
        return {
            id: `pictures:${node.path || "all"}`,
            path: node.path,
            label: node.label,
            icon: "folder",
            count: node.ownCount + descendantCount,
            children,
        };
    }
}

cache=(()=>{return { PictureDomainTreeProjector: PictureDomainTreeProjector };})();return cache;};})();
const __brainExplorerModule47=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml, renderMarkdown } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */


/**
 * ProfilesView renders available operational profiles as a list plus one Markdown reader.
 */
class ProfilesView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the ProfilesView component in the DOM.
     * @returns {string} The string identifier 'brain-profiles-view'.
     */
    static get selector() {
        return "brain-profiles-view";
    }
    /**
     * Holds a reference to the BrainApiClient instance for performing API operations within the ProfilesView, initialized as null.
     *
     * @type {BrainApiClient | null}
     */
    #api = null;
    /**
     * Holds the current application state for the profiles view or remains null if the state is not yet initialized.
     *
     * @type {AppState | null}
     */
    #state = null;
    /**
     * Maintains a private collection of profile identifiers used within the ProfilesView component.
     *
     * @type {string[]}
     */
    #profiles = [];
    /**
     * Maintains the unique identifier of the currently active profile within the view state.
     *
     * @type {string}
     */
    #selectedProfile = "";
    /**
     * Maintains the internal state of the profile's textual representation as a private string.
     *
     * @type {string}
     */
    #profileText = "";
    /**
     * Maintains a private collection of profile entry data used within the ProfilesView component.
     *
     * @type {ProfileEntry[]}
     */
    #profileEntries = [];
    /**
     * Stores the unique identifier of the currently active or highlighted profile entry.
     *
     * @type {string}
     */
    #selectedEntryKey = "";
    /**
     * Tracks whether the profile view is currently in an editing state.
     *
     * @type {boolean}
     */
    #editing = false;
    /**
     * Tracks the loading state of the profiles view to manage asynchronous data fetching indicators.
     *
     * @type {boolean}
     */
    #loading = false;
    /**
     * Stores the data of a profile target currently awaiting navigation or processing.
     *
     * @type {Record<string, unknown> | null}
     */
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
        const targetProfile = typeof target?.profile === "string" ? target.profile : "";
        if (targetProfile && targetProfile !== this.#selectedProfile) {
            this.#profileText = "";
        }
        this.#selectedProfile = targetProfile || this.#selectedProfile || this.#profiles[0] || "";
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
                            <strong>Available</strong>
                            <details class="action-menu">
                                <summary>${icon("more")}<span class="sr-only">Actions</span></summary>
                                <div class="action-menu-panel">
                                    <button data-action="refresh-profiles">${icon("refresh")}Refresh profiles</button>
                                </div>
                            </details>
                        </header>
                        <div class="profile-list scroll-list">
                            ${this.#renderProfiles()}
                        </div>
                    </aside>
                    <section class="structure-content">
                        <div class="content-head">
                            <strong>${escapeHtml(this.#selectedProfile || "No profile")}</strong>
                            <div class="profile-entry-actions">
                                ${this.#profileEntries.length ? `
                                    <select data-role="profile-entry" aria-label="Profile entry">
                                        ${this.#profileEntries.map(entry => `<option value="${escapeHtml(entry.key)}" ${entry.key === this.#selectedEntryKey ? "selected" : ""}>${escapeHtml(entry.key)}</option>`).join("")}
                                    </select>
                                    ${this.#editing ? `
                                        <button class="icon-action" data-action="cancel-profile-edit" title="Cancel editing" aria-label="Cancel editing">${icon("close")}</button>
                                        <button class="icon-action primary-icon-action" data-action="save-profile" title="Save entry" aria-label="Save entry">${icon("save")}</button>
                                    ` : `<button class="icon-action" data-action="edit-profile" title="Edit entry" aria-label="Edit entry">${icon("edit")}</button>`}
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
            if (!(event.target instanceof HTMLSelectElement))
                return;
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
            return `<p class="empty-state">No profiles.</p>`;
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
            return `<div class="knowledge-empty-state">${icon("users")}<h2>Select a profile</h2></div>`;
        }
        const entry = this.#profileEntries.find(item => item.key === this.#selectedEntryKey);
        if (this.#editing && entry) {
            return `<textarea class="profile-editor" data-role="profile-editor" aria-label="${escapeHtml(entry.key)} content">${escapeHtml(entry.content || entry.text || "")}</textarea>`;
        }
        if (entry) {
            return renderMarkdown(entry.content || entry.text || "No content loaded.");
        }
        return renderMarkdown(this.#profileText || "No content loaded.");
    }
    /**
     * Save the selected profile entry through the memory facade.
     */
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
            return [`# Profile: ${profile}`, "", ...result.data.entries.map(entry => `## ${entry.key || entry.name || "entry"}\n\n${entry.content || entry.text || ""}`)].join("\n");
        }
        return result.stdout || result.data?.text || result.error || result.stderr || "";
    }
}
customElements.define(ProfilesView.selector, ProfilesView);

cache=(()=>{return { ProfilesView: ProfilesView };})();return cache;};})();
const __brainExplorerModule48=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml, renderMarkdown } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */


const DEFAULT_SOURCES = ["memory", "knowledge", "messages", "pictures"];
const DEFAULT_MECHANISMS = ["graph", "vector", "text"];
/**
 * Render global search answers and grouped, traceable source results.
 */
class QueryView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the QueryView component in the DOM.
     * @returns {string} The string identifier 'brain-query-view'.
     */
    static get selector() {
        return "brain-query-view";
    }
    /**
     * Holds a reference to the BrainApiClient instance used for making API requests within the QueryView component.
     *
     * @type {BrainApiClient | null}
     */
    #api = null;
    /**
     * Holds the current application state for the query view or remains null if the state is not yet initialized.
     *
     * @type {AppState | null}
     */
    #state = null;
    /**
     * Initializes a private collection of data sources by cloning the default source configuration.
     *
     * @type {string[]}
     */
    #sources = [...DEFAULT_SOURCES];
    /**
     * Initializes a private collection of query mechanisms by cloning the default mechanism set.
     *
     * @type {string[]}
     */
    #mechanisms = [...DEFAULT_MECHANISMS];
    /**
     * Defines the default visibility or filtering scope for the query view, initialized to all records.
     *
     * @type {string}
     */
    #scope = "all";
    /**
     * Stores the domain identifier associated with the current query view.
     *
     * @type {string}
     */
    #domain = "";
    /**
     * Stores the current search query string used for filtering or retrieving data within the view.
     *
     * @type {string}
     */
    #query = "";
    /**
     * Stores the outcome of a query execution or remains null if no result has been retrieved.
     *
     * @type {QueryResult | null}
     */
    #result = null;
    /**
     * Initializes the view's API, state, and query configuration from the provided component context and triggers an immediate render or query execution if a pending query exists.
     * @param {ComponentContext} context The component context containing the API and state required to configure the view's data sources and mechanisms.
     */
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
    /**
     * Triggers the initial rendering of the component when it is attached to the document DOM.
     */
    connectedCallback() {
        this.#render();
    }
    /**
     * Executes a global API query based on current view state, filters the resulting evidence by selected sources and mechanisms, and updates the internal result state to trigger a re-render.
     */
    async #runQuery() {
        const query = this.#query.trim();
        const api = this.#api;
        if (!query || !api)
            return;
        this.#query = query;
        this.#result = { loading: true };
        this.#render();
        const source = this.#sources.length === 1 ? this.#sources[0] ?? "all" : "all";
        const mechanism = this.#mechanisms.length === 1 ? this.#mechanisms[0] ?? "all" : "all";
        const response = await api.globalQuery({
            q: query,
            domain: this.#domain,
            source,
            mechanism,
            knowledgeScope: this.#scope,
            limit: "10",
            explain: "true",
            deep: "false"
        });
        const responseData = !Array.isArray(response.data) ? response.data ?? {} : {};
        const rawResults = Array.isArray(response.data)
            ? response.data
            : responseData.results || responseData.matches || [];
        const results = rawResults.filter(item => item.source !== undefined && item.mechanism !== undefined
            && this.#sources.includes(item.source) && this.#mechanisms.includes(item.mechanism));
        this.#result = {
            ok: response.ok,
            data: { response: responseData.response || "", results: this.#deduplicate(results) },
            stderr: response.stderr || response.error || ""
        };
        this.#state?.setLastResult(response);
        this.#render();
    }
    /**
     * Filters a list of query evidence to remove duplicate entries based on a composite key of source, mechanism, path, title, text, and excerpt.
     * @param {QueryEvidence[]} results The collection of query evidence items to be deduplicated.
     * @returns {QueryEvidence[]} An array containing only the first occurrence of each unique evidence item.
     */
    #deduplicate(results) {
        const unique = new Map();
        results.forEach(result => {
            const key = [result.source, result.mechanism, result.path, result.title, result.text, result.excerpt].join("|");
            if (!unique.has(key))
                unique.set(key, result);
        });
        return [...unique.values()];
    }
    /**
     * Updates the component's inner HTML with the search results layout and attaches click event listeners to picture-opening buttons to update the state route target.
     */
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
    /**
     * Generates an HTML string representing the query result state, handling loading, empty, and data-populated views.
     * @returns {string} An HTML string containing the rendered result interface or a status placeholder.
     */
    #renderResult() {
        if (this.#result?.loading) {
            return `<div class="loading-state search-loading"><span></span><strong>Searching memory, knowledge, and messages</strong><small>Preparing results...</small></div>`;
        }
        if (!this.#result) {
            return `<section class="search-empty">${icon("search")}<h2>Results</h2><p>Enter a query in the header search box to begin.</p></section>`;
        }
        const text = this.#result.data?.response || this.#firstResultText() || this.#result.stderr || "No readable output.";
        return `
            <article class="answer-sheet">
                <header><span class="${this.#result.ok ? "status-pill success" : "status-pill danger"}">${this.#result.ok ? "Response" : "Error"}</span></header>
                <h2>${escapeHtml(this.#query || "Consulta")}</h2>
                <div>${renderMarkdown(String(text).slice(0, 2200))}</div>
            </article>
            ${this.#renderResultGroups()}
        `;
    }
    /**
     * Retrieves the most representative text string from the first available search result.
     * @returns {string} The text, excerpt, or title of the first result, or an empty string if no result or valid text field exists.
     */
    #firstResultText() {
        const first = this.#results()[0];
        return first?.text || first?.excerpt || first?.title || "";
    }
    /**
     * Retrieves a normalized list of query evidence by extracting results or matches from the internal result state.
     * @returns {QueryEvidence[]} An array of QueryEvidence objects derived from the current result data, or an empty array if no valid results are found.
     */
    #results() {
        const results = this.#result?.data?.results || this.#result?.data?.matches || [];
        return Array.isArray(results) ? results : [];
    }
    /**
     * Groups query results by source and mechanism to generate an HTML representation of the search evidence section.
     * @returns {string} An HTML string containing the grouped results and their metadata, or an empty string if no results exist.
     */
    #renderResultGroups() {
        const groups = new Map();
        this.#results().forEach(item => {
            const source = item.source || "unknown";
            const mechanism = item.mechanism || "unknown";
            const key = `${source}:${mechanism}`;
            if (!groups.has(key))
                groups.set(key, { source, mechanism, items: [] });
            groups.get(key)?.items.push(item);
        });
        if (!groups.size)
            return "";
        return `
            <section class="search-evidence" aria-label="Response sources">
                <header><h3>Sources consulted</h3><span>${this.#results().length} results</span></header>
                ${[...groups.values()].map(group => `
                    <section class="result-group">
                        <header><h4>${escapeHtml(this.#sourceLabel(group.source))}</h4><span>${escapeHtml(this.#mechanismLabel(group.mechanism))}</span></header>
                        <ol>
                            ${group.items.map(item => `
                                <li>
                                    <span class="result-order" aria-hidden="true"></span>
                                    <div class="result-copy">
                                        <strong>${escapeHtml(item.title || item.path || item.kind || "Result")}</strong>
                                        <p>${escapeHtml(item.excerpt || item.content?.excerpt || item.data?.excerpt || item.text || item.description || "No excerpt available")}</p>
                                        <small>${escapeHtml(this.#resultOrigin(item))}</small>
                                    </div>
                                    ${item.rank !== undefined ? `<span class="result-rank" title="Relevancia">${Number(item.rank).toFixed(2)}</span>` : ""}
                                    ${item.source === "pictures" && item.data?.id ? `<button class="result-open-button" data-open-picture="${escapeHtml(item.data.id)}">Open</button>` : ""}
                                </li>
                            `).join("")}
                        </ol>
                    </section>
                `).join("")}
            </section>
        `;
    }
    /**
     * Resolves a human-readable origin string from a QueryEvidence object by checking multiple fallback path and identity properties.
     * @param {QueryEvidence} item The evidence object containing potential source references, paths, or domain identifiers.
     * @returns {string} The first available path or identifier found in the evidence hierarchy, or a default fallback string if none exist.
     */
    #resultOrigin(item) {
        return item.sourceRef?.path || item.source_ref?.path || item.path || item.domain || item.kind || "Origen no especificado";
    }
    /**
     * Maps a technical source identifier to its corresponding human-readable display label.
     * @param {string} source The technical identifier of the data source to be labeled.
     * @returns {string} The localized string representation of the source, defaulting to 'Other results' for unrecognized inputs.
     */
    #sourceLabel(source) {
        if (source === "memory")
            return "Memory";
        if (source === "knowledge")
            return "Knowledge";
        if (source === "messages")
            return "Messages";
        if (source === "pictures")
            return "Pictures";
        return "Other results";
    }
    /**
     * Maps a mechanism identifier to its corresponding localized display label.
     * @param {string} mechanism The technical identifier of the mechanism to be translated.
     * @returns {string} The localized string representation of the mechanism, or the original identifier if no mapping exists.
     */
    #mechanismLabel(mechanism) {
        return mechanism === "graph" ? "Grafo" : mechanism === "vector" ? "Vectorial" : mechanism === "text" ? "Texto" : mechanism;
    }
}
customElements.define(QueryView.selector, QueryView);

cache=(()=>{return { QueryView: QueryView };})();return cache;};})();
const __brainExplorerModule49=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */


/**
 * SettingsView renders compact runtime health facts for the local explorer.
 */
class SettingsView extends HTMLElement {
    /**
     * Registered Custom Element tag used by the shell route registry.
     * @returns {string} A string representing the DOM element selector for the settings view.
     */
    static get selector() {
        return "brain-settings-view";
    }
    /**
     * Injected Explorer HTTP adapter, or `null` before context assignment.
     * @type {BrainApiClient | null}
     */
    #api = null;
    /**
     * Injected shell state store, or `null` before context assignment.
     * @type {AppState | null}
     */
    #state = null;
    /**
     * Latest authoritative server-health snapshot rendered by the settings view.
     * @type {HealthStatus | null}
     */
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
        this.#health = result.data ?? null;
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
                        <strong>${icon("refresh")}Refresh runtime</strong>
                        <small>health local</small>
                    </button>
                    ${this.#tile("Server", this.#health?.ok ? "OK" : "Pending", "brain_explorer")}
                    ${this.#tile("Dist", this.#health?.distDir || "No cargado", "runtime estatico")}
                    ${this.#tile("Workspace", this.#health?.workspaceRoot || "Not loaded", "active root")}
                    ${this.#tile("Agent home", this.#health?.agentHome || "Not loaded", "shared memory")}
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
const __brainExplorerModule50=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */


/**
 * WikisView renders detected subproject documentation wikis and opens them
 * inside an embedded iframe. No generation step — serves markdown live.
 */
class WikisView extends HTMLElement {
    /**
     * Provides the unique CSS selector used to identify the WikisView component in the DOM.
     * @returns {string} A string representing the component's custom element tag name.
     */
    static get selector() {
        return "brain-wikis-view";
    }
    /**
     * Holds a reference to the BrainApiClient instance used for making API requests within the WikisView component.
     *
     * @type {BrainApiClient | null}
     */
    #api = null;
    /**
     * Holds the current application state or null if the state has not been initialized.
     *
     * @type {AppState | null}
     */
    #state = null;
    /**
     * Maintains a private collection of wiki records used for rendering the wikis view.
     *
     * @type {WikiRecord[]}
     */
    #wikis = [];
    /**
     * Tracks the asynchronous loading state of the WikisView component.
     *
     * @type {boolean}
     */
    #loading = false;
    /**
     * Indicates whether the wiki content is currently being loaded.
     *
     * @type {boolean}
     */
    #wikiLoading = false;
    /**
     * Stores the name of the currently selected wiki or null if no wiki is active.
     *
     * @type {string | null}
     */
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
            const res = await this.#api.getWikis();
            this.#wikis = res.data?.wikis ?? [];
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
                        <h2 style="margin: 0; font-size: var(--font-size-xl); color: var(--text-strong);">Subproject Wikis</h2>
                        <small style="color: var(--text-muted);">Interactive documentation available in the active path</small>
                    </div>
                    <button data-action="refresh-wikis" class="primary-action compact-action" title="Find wikis">${icon("refresh")}</button>
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
            btn.addEventListener("keydown", (event) => {
                if (!(event instanceof KeyboardEvent))
                    return;
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    if (btn instanceof HTMLElement)
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
                    <h3>No documentation folders found</h3>
                    <p>Create a <code>documentation</code> folder in a subproject to enable local wikis.</p>
                </div>
            `;
        }
        return `
            <main class="wiki-list">
                ${this.#wikis.map(wiki => `
                    <article class="wiki-list-item ${wiki.hasWiki ? "is-clickable" : ""}"
                        ${wiki.hasWiki ? `data-action="view-wiki" data-name="${escapeHtml(wiki.name)}" tabindex="0" role="button" aria-label="Open wiki ${escapeHtml(wiki.name)}"` : ""}>
                        <div class="wiki-list-content">
                            <div class="wiki-list-heading">
                                <strong>${escapeHtml(wiki.name)}</strong>
                                <span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 600; background: ${wiki.hasWiki ? "rgba(16, 185, 129, 0.15); color: #10b981;" : "rgba(156, 163, 175, 0.15); color: #9ca3af;"};">
                                    ${wiki.hasWiki ? "Available" : "Not built"}
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
                                <span style="font-size: var(--font-size-sm); color: var(--text-muted); padding: 6px 0;">Run <code>generate</code> to enable</span>
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
                            ${icon("chevronRight")} Back
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
            if (event.currentTarget instanceof HTMLIFrameElement)
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
const __brainExplorerModule51=(()=>{let cache;return()=>{if(cache)return cache;

/**
 * Handles global keyboard interactions owned by the persistent application shell.
 *
 * @module presentation/shell/controllers/shell-keyboard-controller
 */
/**
 * Focus and select the shell search field when the registered shortcut is pressed.
 *
 * The controller receives its host explicitly and therefore owns no DOM lifecycle
 * or global listener registration; the shell component remains responsible for
 * attaching and detaching the stable event callback.
 *
 * @param {HTMLElement} host Shell Custom Element containing the global search input.
 * @param {KeyboardEvent} event Native keyboard interaction dispatched by `window`.
 */
function handleShellSearchShortcut(host, event) {
    if (!event.ctrlKey || !event.altKey || event.key.toLowerCase() !== "s")
        return;
    event.preventDefault();
    const searchInput = host.querySelector("[data-role='global-shell-search']");
    searchInput?.focus();
    searchInput?.select();
}

cache=(()=>{return { handleShellSearchShortcut: handleShellSearchShortcut };})();return cache;};})();
const __brainExplorerModule52=(()=>{let cache;return()=>{if(cache)return cache;
const { escapeHtml } = __brainExplorerModule4();
const { icon } = __brainExplorerModule5();
const { SHELL_ROUTES } = __brainExplorerModule7();
/**
 * Inert HTML renderer for the persistent shell navigation registry.
 *
 * @module presentation/shell/renderers/shell-navigation-renderer
 */



/**
 * Render all persistent navigation buttons and the active-route state.
 *
 * @param {RouteId} activeRouteId Route identity currently owned by the shell state store.
 * @returns {string} Inert navigation-button markup in canonical registry order.
 */
function renderShellNavigation(activeRouteId) {
    return SHELL_ROUTES.filter(route => route.nav !== false).map(route => `
        <button class="side-nav-item ${route.id === activeRouteId ? "is-active" : ""}" data-route="${route.id}" data-tooltip="${escapeHtml(route.label)}" aria-label="${escapeHtml(route.label)}">
            ${icon(route.icon)}
            <span class="nav-label">${escapeHtml(route.label)}</span>
        </button>
    `).join("");
}

cache=(()=>{return { renderShellNavigation: renderShellNavigation };})();return cache;};})();
__brainExplorerModule0();
