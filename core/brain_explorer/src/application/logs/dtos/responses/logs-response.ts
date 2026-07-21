/**
 * One normalized durable work-log index entry returned by the Logs application query.
 */
export interface LogEntryPayload {
    /**
     * Canonical log timestamp.
     * @type {string}
     */
    timestamp: string;
    /**
     * Canonical ownership domain.
     * @type {string}
     */
    domain: string;
    /**
     * Human-readable change title.
     * @type {string}
     */
    title: string;
    /**
     * Recorded change category.
     * @type {string}
     */
    change_type: string;
    /**
     * Motivation captured when work completed.
     * @type {string}
     */
    why: string;
    /**
     * Complete change description.
     * @type {string}
     */
    description: string;
    /**
     * Documented downstream impact.
     * @type {string}
     */
    impact: string;
    /**
     * Workspace-relative log source path.
     * @type {string}
     */
    source_path: string;
    /**
     * Source modification timestamp.
     * @type {number}
     */
    source_mtime: number;
    /**
     * Source size in bytes.
     * @type {number}
     */
    source_size: number;
}

/**
 * Complete Logs export or index response payload.
 */
export interface LogsPayload {
    /**
     * Whether the log projection succeeded.
     * @type {boolean}
     */
    ok: boolean;
    /**
     * Query command that produced this payload.
     * @type {"export-logs" | "log-index"}
     */
    command: "export-logs" | "log-index";
    /**
     * Total number of returned records.
     * @type {number}
     */
    count: number;
    /**
     * Ordered log index records.
     * @type {LogEntryPayload[]}
     */
    entries: LogEntryPayload[];
}
