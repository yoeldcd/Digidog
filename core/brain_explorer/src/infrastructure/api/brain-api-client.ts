/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import type { ApiRequestOptions, ApiResponse, BacklogMutation, BacklogPayload, LogsPayload, PictureDescriptionPayload, PicturesPayload, QueryParams, HealthStatus, ProjectsResponse, VoiceMessagesResponse, VoiceStatusResponse, WikisResponse } from "../../application/contracts/api-dtos.ts";

interface CacheRecord {
    payload: ApiResponse;
    expiresAt: number;
}

/**
 * BrainApiClient isolates every browser request to the local explorer server.
 */
export class BrainApiClient extends EventTarget {
    #cache = new Map<string, CacheRecord>();
    #inFlight = new Map<string, Promise<ApiResponse>>();
    #defaultTtlMs = 45_000;
    #workspaceRootOverride: string | null = null;

    setWorkspaceRootOverride(path: string | null) {
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
    async request<TData = unknown>(path: string, options: ApiRequestOptions = {}): Promise<ApiResponse<TData>> {
        const method = String(options.method || "GET").toUpperCase();
        const cacheable = method === "GET";
        const cacheKey = `${method} ${path}`;
        const now = Date.now();
        const ttlMs = Number(options.cacheTtlMs || this.#defaultTtlMs);
        if (cacheable && !options.forceRefresh) {
            const cached = this.#cache.get(cacheKey);
            if (cached && cached.expiresAt > now) {
                return { ...cached.payload, cached: true } as ApiResponse<TData>;
            }
            const pending = this.#inFlight.get(cacheKey);
            if (pending) {
                const payload = await pending;
                return { ...payload, cached: true } as ApiResponse<TData>;
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
        let completedPayload: ApiResponse | null = null;
        try {
            if (cacheable) {
                this.#inFlight.set(cacheKey, requestPromise);
            }
            const payload = await requestPromise;
            completedPayload = payload;
            if (cacheable) {
                this.#cache.set(cacheKey, { payload, expiresAt: Date.now() + ttlMs });
            } else {
                this.#cache.clear();
            }
            return payload as ApiResponse<TData>;
        } finally {
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
    async #fetchJson(path: string, options: RequestInit = {}): Promise<ApiResponse> {
        const headers: Record<string, string> = {
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
        const payload: unknown = await response.json();
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
    #isMissingRoute(payload: ApiResponse): boolean {
        return Boolean(!payload?.ok && String(payload?.error || payload?.stderr || "").includes("Unknown API route"));
    }

    /**
     * Read server health.
     *
     * @returns {Promise<ApiResponse<HealthStatus>>} Health payload.
     */
    health(options: ApiRequestOptions = {}): Promise<ApiResponse<HealthStatus>> {
        return this.request<HealthStatus>("/api/health", options);
    }

    /**
     * Read registered projects.
     *
     * @returns {Promise<ApiResponse<ProjectsResponse>>} Projects list payload.
     */
    getProjects(options: ApiRequestOptions = {}): Promise<ApiResponse<ProjectsResponse>> {
        return this.request<ProjectsResponse>("/api/projects", options);
    }

    /**
     * Read detected subproject wikis.
     *
     * @returns {Promise<ApiResponse<WikisResponse>>} Wikis list.
     */
    getWikis(options: ApiRequestOptions = {}): Promise<ApiResponse<WikisResponse>> {
        return this.request<WikisResponse>("/api/wikis", options);
    }

    /** Read persisted paid-voice messages. */
    getVoiceMessages(
        params: QueryParams = {},
        options: ApiRequestOptions = {}
    ): Promise<ApiResponse<VoiceMessagesResponse>> {
        const query = toQueryString(params);
        return this.request<VoiceMessagesResponse>(`/api/voice/messages${query ? `?${query}` : ""}`, options);
    }

    /** Poll the daemon-confirmed avatar playback identity. */
    getVoiceStatus(options: ApiRequestOptions = {}): Promise<ApiResponse<VoiceStatusResponse>> {
        return this.request<VoiceStatusResponse>("/api/voice/status", options);
    }

    /** Replay one retained daemon message without regenerating speech. */
    replayVoiceMessage(name: string): Promise<ApiResponse> {
        return this.request("/api/voice/replay", {
            method: "POST",
            body: JSON.stringify({ name }),
            forceRefresh: true
        });
    }

    /** Stop active daemon replay without removing retained audio. */
    pauseVoiceReplay(): Promise<ApiResponse> {
        return this.request("/api/voice/pause", { method: "POST", forceRefresh: true });
    }

    /** Generate and immediately play audio for one persisted message. */
    synthesizeVoiceMessage(messageId: string): Promise<ApiResponse> {
        return this.request("/api/voice/synthesize", {
            method: "POST",
            body: JSON.stringify({ messageId }),
            forceRefresh: true
        });
    }

    /** Build the safe media URL for one stored voice message. */
    voiceMessageUrl(name: string): string {
        return `/api/voice/messages/${encodeURIComponent(name)}`;
    }


    /**
     * Read live workspace context through get-context.
     *
     * @returns {Promise<object>} Context payload.
     */
    context(options: ApiRequestOptions = {}): Promise<ApiResponse> {
        return this.request("/api/context", options);
    }

    /**
     * Execute a read-only CLI prompt command.
     *
     * @param {string} command Prompt command.
     * @returns {Promise<object>} CLI result payload.
     */
    runCli(command: string): Promise<ApiResponse> {
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
    memoryTree(options: ApiRequestOptions = {}): Promise<ApiResponse> {
        return this.request("/api/memory/tree", options);
    }

    /**
     * Read one memory entry.
     *
     * @param {string} path Dot-notated memory path.
     * @returns {Promise<object>} CLI result payload.
     */
    memoryEntry(path: string, options: ApiRequestOptions = {}): Promise<ApiResponse> {
        return this.request(`/api/memory/entry?path=${encodeURIComponent(path)}`, options);
    }

    /**
     * Save one memory entry.
     *
     * @param {string} path Dot-notated memory path.
     * @param {string} content Markdown content.
     * @returns {Promise<object>} CLI result payload.
     */
    saveMemoryEntry(path: string, content: string): Promise<ApiResponse> {
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
    createMemoryDomain(domain: string): Promise<ApiResponse> {
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
    deleteMemoryDomain(domain: string): Promise<ApiResponse> {
        return this.request(`/api/memory/domain?domain=${encodeURIComponent(domain)}&confirm=${encodeURIComponent(domain)}`, { method: "DELETE" });
    }

    /**
     * Delete one memory entry.
     *
     * @param {string} path Dot-notated memory path.
     * @returns {Promise<object>} CLI result payload.
     */
    deleteMemoryEntry(path: string): Promise<ApiResponse> {
        return this.request(`/api/memory/entry?path=${encodeURIComponent(path)}`, { method: "DELETE" });
    }

    /**
     * Read knowledge graph status.
     *
     * @param {string} scope Knowledge scope.
     * @returns {Promise<object>} CLI result payload.
     */
    knowledgeStatus(scope = "all", options: ApiRequestOptions = {}): Promise<ApiResponse> {
        return this.request(`/api/knowledge/status?scope=${encodeURIComponent(scope)}`, options);
    }

    /**
     * Show graph records.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    knowledgeShow(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse> {
        const query = toQueryString(params);
        return this.request(`/api/knowledge/show?${query}`, options);
    }

    /**
     * Search the graph.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    knowledgeQuery(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse> {
        const query = toQueryString(params);
        return this.request(`/api/knowledge/query?${query}`, options);
    }

    /**
     * Review knowledge deltas.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    knowledgeDeltas(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse> {
        const query = toQueryString(params);
        return this.request(`/api/knowledge/deltas?${query}`, options);
    }

    /**
     * Execute global brain query.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    globalQuery(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse> {
        const query = toQueryString(params);
        return this.request(`/api/query?${query}`, options);
    }

    /** Read the canonical picture registry. */
    pictures(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse<PicturesPayload>> {
        const query = toQueryString(params);
        return this.request<PicturesPayload>(`/api/pictures${query ? `?${query}` : ""}`, options);
    }

    /** Persist one manual description or generate it when the text is omitted. */
    describePicture(pictureId: string, description = ""): Promise<ApiResponse<PictureDescriptionPayload>> {
        return this.request<PictureDescriptionPayload>("/api/pictures/description", {
            method: "POST",
            body: JSON.stringify({ pictureId, description }),
            forceRefresh: true
        });
    }

    /** Invoke the model-backed describe-picture flow for one registry record. */
    generatePictureDescription(pictureId: string): Promise<ApiResponse<PictureDescriptionPayload>> {
        return this.describePicture(pictureId);
    }

    /** Build the opaque registry-backed URL for one picture. */
    pictureUrl(pictureId: string): string {
        return `/api/pictures/file?id=${encodeURIComponent(pictureId)}`;
    }

    /**
     * Read profile list.
     *
     * @returns {Promise<object>} CLI result payload.
     */
    profiles(options: ApiRequestOptions = {}): Promise<ApiResponse> {
        return this.request("/api/profiles", options);
    }

    /**
     * Read one profile.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    async profileRead(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse> {
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
    logs(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse<LogsPayload>> {
        const query = toQueryString(params);
        return this.request(`/api/logs?${query}`, options);
    }

    /**
     * Read the log domain index.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    logIndex(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse<LogsPayload>> {
        const query = toQueryString(params);
        return this.request(`/api/logs/index?${query}`, options);
    }

    /**
     * Read the workspace backlog tree.
     *
     * @param {object} params Query parameters.
     * @returns {Promise<object>} CLI result payload.
     */
    backlog(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse<BacklogPayload>> {
        const query = toQueryString(params);
        return this.request(`/api/backlog?${query}`, options);
    }

    /**
     * Mutate one backlog task through an allowlisted API action.
     *
     * @param {object} payload Backlog mutation payload.
     * @returns {Promise<object>} CLI result payload.
     */
    updateBacklog(payload: BacklogMutation): Promise<ApiResponse> {
        return this.request("/api/backlog/task", {
            method: "POST",
            body: JSON.stringify(payload)
        });
    }
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null;
}

function isApiResponse(value: unknown): value is ApiResponse {
    return isRecord(value) && typeof value.ok === "boolean";
}

function toQueryString(params: QueryParams): string {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
            query.set(key, String(value));
        }
    });
    return query.toString();
}
