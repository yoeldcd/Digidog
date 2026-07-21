/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import type { ApiRequestOptions, ApiResponse, QueryParams } from "../../../../application/shared/contracts/api-response-contract.ts";
import type { BacklogMutation } from "../../../../application/backlog/dtos/requests/backlog-mutation-request.ts";
import type { BacklogPayload } from "../../../../application/backlog/dtos/responses/backlog-response.ts";
import type { PictureDescriptionPayload, PicturesPayload } from "../../../../application/pictures/dtos/responses/pictures-response.ts";
import type { LogsPayload } from "../../../../application/logs/dtos/responses/logs-response.ts";
import type { MemoryEntryPayload } from "../../../../application/memory/dtos/responses/memory-response.ts";
import type { ProfileReadPayload, ProfilesPayload } from "../../../../application/profiles/dtos/responses/profiles-response.ts";
import type { ProjectsResponse } from "../../../../application/projects/dtos/responses/projects-response.ts";
import type { WikisResponse } from "../../../../application/wikis/dtos/responses/wikis-response.ts";
import type { VoiceMessagesResponse, VoiceStatusResponse, VoiceSynthesisResponse } from "../../../../application/messages/dtos/responses/messages-response.ts";
import type { HealthStatus } from "../../../../application/settings/dtos/responses/health-response.ts";
import type { ContextResponse } from "../../../../application/dashboard/dtos/responses/context-response.ts";
import type { QueryResponse } from "../../../../application/query/dtos/responses/query-response.ts";

/**
 * One successful GET response retained until its absolute expiration timestamp.
 */
interface CacheRecord {
    /**
     * Untyped response envelope shared by cache consumers through the generic request boundary.
     * @type {ApiResponse<unknown>}
     */
    payload: ApiResponse;
    /**
     * Browser epoch time after which the response must not be reused.
     * @type {number}
     */
    expiresAt: number;
}

/**
 * BrainApiClient isolates every browser request to the local explorer server.
 */
export class BrainApiClient extends EventTarget {
    /**
     * Completed cacheable responses indexed by normalized HTTP method and path.
     * @type {Map<string, CacheRecord>}
     */
    #cache = new Map<string, CacheRecord>();
    /**
     * In-flight cacheable requests shared by concurrent callers of the same path.
     * @type {Map<string, Promise<ApiResponse<unknown>>>}
     */
    #inFlight = new Map<string, Promise<ApiResponse>>();
    /**
     * Default lifetime applied to cacheable GET responses in milliseconds.
     * @type {number}
     */
    #defaultTtlMs = 45_000;
    /**
     * Explicit workspace header override, or `null` to use the server default.
     * @type {string | null}
     */
    #workspaceRootOverride: string | null = null;

    /**
     * Select the workspace header applied to subsequent requests and invalidate stale cache state.
     *
     * @param {string | null} path Canonical workspace root, or `null` to restore server-side workspace selection.
     * @returns {void} Nothing; both completed and in-flight cache registries are cleared synchronously.
     */
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the health request.
     * @returns {Promise<ApiResponse<HealthStatus>>} Health payload.
     */
    async health(options: ApiRequestOptions = {}): Promise<ApiResponse<HealthStatus>> {
        const response = await this.request<HealthStatus>("/api/health", options);
        return normalizeDirectResponse(response, isHealthStatus);
    }

    /**
     * Read registered projects.
     *
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the project-registry request.
     * @returns {Promise<ApiResponse<ProjectsResponse>>} Projects list payload.
     */
    async getProjects(options: ApiRequestOptions = {}): Promise<ApiResponse<ProjectsResponse>> {
        const response = await this.request<ProjectsResponse>("/api/projects", options);
        return normalizeDirectResponse(response, isProjectsResponse);
    }

    /**
     * Read detected subproject wikis.
     *
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the wiki-registry request.
     * @returns {Promise<ApiResponse<WikisResponse>>} Wikis list.
     */
    async getWikis(options: ApiRequestOptions = {}): Promise<ApiResponse<WikisResponse>> {
        const response = await this.request<WikisResponse>("/api/wikis", options);
        return normalizeDirectResponse(response, isWikisResponse);
    }

    /**
     * Read persisted paid-voice messages and their transcript sessions.
     *
     * @param {QueryParams} params Optional server-side session, date, or pagination query values.
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the message request.
     * @returns {Promise<ApiResponse<VoiceMessagesResponse>>} Typed voice artifacts, jobs, transcript history, and session summaries.
     */
    getVoiceMessages(
        params: QueryParams = {},
        options: ApiRequestOptions = {}
    ): Promise<ApiResponse<VoiceMessagesResponse>> {
        const query = toQueryString(params);
        return this.request<VoiceMessagesResponse>(`/api/voice/messages${query ? `?${query}` : ""}`, options);
    }

    /**
     * Poll the daemon-confirmed avatar playback identity.
     *
     * @param {ApiRequestOptions} options Cache and fetch policy; polling callers normally force refresh.
     * @returns {Promise<ApiResponse<VoiceStatusResponse>>} Current daemon voice runtime state.
     */
    getVoiceStatus(options: ApiRequestOptions = {}): Promise<ApiResponse<VoiceStatusResponse>> {
        return this.request<VoiceStatusResponse>("/api/voice/status", options);
    }

    /**
     * Replay one retained daemon message without regenerating speech.
     *
     * @param {string} name Server-issued retained audio filename.
     * @returns {Promise<ApiResponse<unknown>>} Operation envelope confirming whether replay was accepted.
     */
    replayVoiceMessage(name: string): Promise<ApiResponse> {
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
    pauseVoiceReplay(): Promise<ApiResponse> {
        return this.request("/api/voice/pause", { method: "POST", forceRefresh: true });
    }

    /**
     * Generate and immediately play audio for one persisted message.
     *
     * @param {string} messageId Stable persisted avatar-message identifier.
     * @returns {Promise<ApiResponse<VoiceSynthesisResponse>>} Accepted speech-job identity when synthesis begins.
     */
    synthesizeVoiceMessage(messageId: string): Promise<ApiResponse<VoiceSynthesisResponse>> {
        return this.request<VoiceSynthesisResponse>("/api/voice/synthesize", {
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
    voiceMessageUrl(name: string): string {
        return `/api/voice/messages/${encodeURIComponent(name)}`;
    }


    /**
     * Read live workspace context through get-context.
     *
     * @param {ApiRequestOptions} options Cache and fetch policy applied to context hydration.
     * @returns {Promise<object>} Context payload.
     */
    context(options: ApiRequestOptions = {}): Promise<ApiResponse<ContextResponse>> {
        return this.request<ContextResponse>("/api/context", options);
    }

    /**
     * Execute a read-only CLI prompt command.
     *
     * @param {string} command Prompt command.
     * @returns {Promise<object>} CLI result payload.
     */
    runCli<TData = unknown>(command: string): Promise<ApiResponse<TData>> {
        return this.request<TData>("/api/cli", {
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
    memoryTree(options: ApiRequestOptions = {}): Promise<ApiResponse<string[]>> {
        return this.request<string[]>("/api/memory/tree", options);
    }

    /**
     * Read one memory entry.
     *
     * @param {string} path Dot-notated memory path.
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the entry request.
     * @returns {Promise<object>} CLI result payload.
     */
    memoryEntry(path: string, options: ApiRequestOptions = {}): Promise<ApiResponse<MemoryEntryPayload>> {
        return this.request<MemoryEntryPayload>(`/api/memory/entry?path=${encodeURIComponent(path)}`, options);
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the status request.
     * @returns {Promise<object>} CLI result payload.
     */
    knowledgeStatus(scope = "all", options: ApiRequestOptions = {}): Promise<ApiResponse> {
        return this.request(`/api/knowledge/status?scope=${encodeURIComponent(scope)}`, options);
    }

    /**
     * Show graph records.
     *
     * @param {object} params Query parameters.
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the graph-listing request.
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the graph-search request.
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the delta request.
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
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the global query request.
     * @returns {Promise<object>} CLI result payload.
     */
    globalQuery(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse<QueryResponse>> {
        const query = toQueryString(params);
        return this.request<QueryResponse>(`/api/query?${query}`, options);
    }

    /**
     * Read the canonical picture registry.
     *
     * @param {QueryParams} params Optional domain, search, and scan query values.
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the registry request.
     * @returns {Promise<ApiResponse<PicturesPayload>>} Active picture records and registry diagnostics.
     */
    pictures(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse<PicturesPayload>> {
        const query = toQueryString(params);
        return this.request<PicturesPayload>(`/api/pictures${query ? `?${query}` : ""}`, options);
    }

    /**
     * Persist one manual description or generate it when the text is omitted.
     *
     * @param {string} pictureId Stable registry identifier of the picture being described.
     * @param {string} description Human-authored description, or an empty string to request generation.
     * @returns {Promise<ApiResponse<PictureDescriptionPayload>>} Updated authoritative picture record and vector-index diagnostics.
     */
    describePicture(pictureId: string, description = ""): Promise<ApiResponse<PictureDescriptionPayload>> {
        return this.request<PictureDescriptionPayload>("/api/pictures/description", {
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
    generatePictureDescription(pictureId: string): Promise<ApiResponse<PictureDescriptionPayload>> {
        return this.describePicture(pictureId);
    }

    /**
     * Build the opaque registry-backed URL for one picture.
     *
     * @param {string} pictureId Stable registry identifier rather than a filesystem path.
     * @returns {string} Same-origin URL that resolves the active registry record.
     */
    pictureUrl(pictureId: string): string {
        return `/api/pictures/file?id=${encodeURIComponent(pictureId)}`;
    }

    /**
     * Read profile list.
     *
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the profile-list request.
     * @returns {Promise<object>} CLI result payload.
     */
    profiles(options: ApiRequestOptions = {}): Promise<ApiResponse<ProfilesPayload>> {
        return this.request<ProfilesPayload>("/api/profiles", options);
    }

    /**
     * Read one profile.
     *
     * @param {object} params Query parameters.
     * @param {ApiRequestOptions} options Cache and fetch policy applied to the profile-read request.
     * @returns {Promise<object>} CLI result payload.
     */
    async profileRead(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse<ProfileReadPayload>> {
        const query = toQueryString(params);
        const result = await this.request<ProfileReadPayload>(`/api/profiles/read?${query}`, options);
        if (this.#isMissingRoute(result) && params.name) {
            return this.runCli<ProfileReadPayload>(`read-profile ${params.name} --json`);
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
    logs(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse<LogsPayload>> {
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
    logIndex(params: QueryParams = {}, options: ApiRequestOptions = {}): Promise<ApiResponse<LogsPayload>> {
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

/**
 * Narrow an unknown JSON value to a non-null object record.
 *
 * @param {unknown} value Unknown value returned by browser JSON parsing.
 * @returns {boolean} True when string-keyed property inspection is safe.
 */
function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null;
}

/**
 * Narrow an unknown JSON object to the minimum Explorer response envelope.
 *
 * @param {unknown} value Unknown value returned by browser JSON parsing.
 * @returns {boolean} True when the required boolean `ok` discriminator exists.
 */
function isApiResponse(value: unknown): value is ApiResponse {
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
function normalizeDirectResponse<TData>(
    response: ApiResponse<TData>,
    isDirectData: (value: unknown) => value is TData
): ApiResponse<TData> {
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
function isHealthStatus(value: unknown): value is HealthStatus {
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
function isProjectsResponse(value: unknown): value is ProjectsResponse {
    return isRecord(value) && typeof value.ok === "boolean" && Array.isArray(value.projects);
}

/**
 * Narrow a direct wiki-registry response returned by the system route.
 *
 * @param {unknown} value Parsed response candidate.
 * @returns {boolean} True when the response owns a wiki array.
 */
function isWikisResponse(value: unknown): value is WikisResponse {
    return isRecord(value) && typeof value.ok === "boolean" && Array.isArray(value.wikis);
}

/**
 * Serialize defined primitive query values into a percent-encoded URL query.
 *
 * @param {QueryParams} params Feature-owned query values; undefined entries are omitted.
 * @returns {string} Query string without a leading question mark.
 */
function toQueryString(params: QueryParams): string {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
            query.set(key, String(value));
        }
    });
    return query.toString();
}
