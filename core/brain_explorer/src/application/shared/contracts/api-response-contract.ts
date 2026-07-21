/**
 * Shared transport contracts used by every Brain Explorer application feature.
 */

/**
 * Standard response envelope returned by the local Explorer API.
 *
 * @typeParam TData Feature-owned response payload carried by the envelope.
 */
export interface ApiResponse<TData = unknown> {
    /**
     * Whether the server completed the requested command successfully.
     * @type {boolean}
     */
    ok: boolean;
    /**
     * Canonical CLI command tokens executed by the server, when applicable.
     * @type {string[] | undefined}
     */
    command?: string[];
    /**
     * Process or application result code supplied by the server.
     * @type {number | undefined}
     */
    code?: number;
    /**
     * Feature-owned response payload.
     * @type {TData | undefined}
     */
    data?: TData;
    /**
     * Captured standard output intended for diagnostics.
     * @type {string | undefined}
     */
    stdout?: string;
    /**
     * Captured standard error intended for diagnostics.
     * @type {string | undefined}
     */
    stderr?: string;
    /**
     * End-to-end server operation duration in milliseconds.
     * @type {number | undefined}
     */
    durationMs?: number;
    /**
     * Human-readable failure description when the operation failed.
     * @type {string | undefined}
     */
    error?: string;
    /**
     * Whether the browser client served a cached response.
     * @type {boolean | undefined}
     */
    cached?: boolean;
    /**
     * Task identifiers whose records have server-managed image attachments.
     * @type {string[] | undefined}
     */
    hasImages?: string[];
}

/**
 * Fetch options extended with Explorer client cache and feedback controls.
 */
export interface ApiRequestOptions extends RequestInit {
    /**
     * Bypass a valid browser response cache entry.
     * @type {boolean | undefined}
     */
    forceRefresh?: boolean;
    /**
     * Override the default response-cache lifetime in milliseconds.
     * @type {number | undefined}
     */
    cacheTtlMs?: number;
    /**
     * User-facing command label emitted through request lifecycle events.
     * @type {string | undefined}
     */
    commandLabel?: string;
    /**
     * Suppress global request lifecycle feedback for background refreshes.
     * @type {boolean | undefined}
     */
    silent?: boolean;
}

/**
 * Primitive values accepted by the Explorer query-string serializer.
 */
export type QueryParams = Record<string, string | number | boolean | undefined>;
