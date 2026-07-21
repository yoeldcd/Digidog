/**
 * Closed visual themes supported by the application shell.
 */
export type ThemeMode = "light" | "dark";

/**
 * Closed route identifiers addressable through Explorer navigation state.
 */
export type RouteId = "dashboard" | "memory" | "knowledge" | "pictures" | "query" | "profiles" | "logs" | "backlog" | "messages" | "wikis" | "settings";

/**
 * Deferred navigation target owned by one destination route.
 */
export interface RouteTarget {
    /**
     * Destination route that is allowed to consume the target.
     * @type {RouteId}
     */
    route: RouteId;
    /**
     * Route-specific, runtime-validated target fields.
     * @type {Record<string, unknown>}
     */
    target: Record<string, unknown>;
}

/**
 * One diagnostic API call retained by the shell state inspector.
 */
export interface CallLogRecord {
    /**
     * Stable browser-local call identity.
     * @type {string}
     */
    id: string;
    /**
     * Human-readable time at which the call completed.
     * @type {string}
     */
    time: string;
    /**
     * Whether the response reported success.
     * @type {boolean}
     */
    ok: boolean;
    /**
     * Numeric or textual result code.
     * @type {string | number}
     */
    code: number | string;
    /**
     * End-to-end duration in milliseconds.
     * @type {number}
     */
    durationMs: number;
    /**
     * User-facing command label.
     * @type {string}
     */
    command: string;
    /**
     * Untrusted response data retained for diagnostics.
     * @type {unknown}
     */
    data: unknown;
    /**
     * Captured standard output.
     * @type {string}
     */
    stdout: string;
    /**
     * Captured standard error.
     * @type {string}
     */
    stderr: string;
}

/**
 * Command currently represented by the global busy indicator.
 */
export interface ActiveCommand {
    /**
     * Human-readable command label.
     * @type {string}
     */
    command: string;
    /**
     * Browser timestamp at which execution started.
     * @type {number}
     */
    startedAt: number;
}
