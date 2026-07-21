/**
 * Task record returned by the durable Backlog projection.
 */
export interface BacklogTask {
    /**
     * Stable task identifier.
     * @type {string}
     */
    id: string;
    /**
     * Human-readable task title.
     * @type {string}
     */
    title: string;
    /**
     * Complete task description.
     * @type {string}
     */
    description: string;
    /**
     * Closed scheduling priority.
     * @type {"HIGH" | "MEDIUM" | "LOW"}
     */
    priority: "HIGH" | "MEDIUM" | "LOW";
    /**
     * Closed workflow state.
     * @type {"TODO" | "WORKING" | "DONE"}
     */
    status: "TODO" | "WORKING" | "DONE";
    /**
     * Canonical dotted ownership domain.
     * @type {string}
     */
    domain: string;
    /**
     * Original creation timestamp.
     * @type {string | number | undefined}
     */
    created_at?: string | number;
    /**
     * Completion timestamp when done.
     * @type {string | undefined}
     */
    completed_at?: string;
    /**
     * Compatibility completion flag from the CLI projection.
     * @type {boolean}
     */
    checked: boolean;
}

/**
 * Complete response payload returned by `show-backlog`.
 */
export interface BacklogPayload {
    /**
     * Whether projection succeeded.
     * @type {boolean}
     */
    ok: boolean;
    /**
     * Authoritative command identity.
     * @type {"show-backlog"}
     */
    command: "show-backlog";
    /**
     * Requested domain filter, or null for all domains.
     * @type {string | null}
     */
    domain: string | null;
    /**
     * Whether completed tasks were included.
     * @type {boolean}
     */
    includeDone: boolean;
    /**
     * Total number of returned tasks.
     * @type {number}
     */
    count: number;
    /**
     * Stable task collection.
     * @type {BacklogTask[]}
     */
    tasks: BacklogTask[];
}
