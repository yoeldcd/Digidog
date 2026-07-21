/**
 * Closed mutation operations accepted by the Backlog endpoint.
 */
export type BacklogAction = "add" | "delete" | "finish" | "working" | "done" | "todo" | "edit";

/**
 * Normalized Backlog mutation request sent by presentation controllers.
 */
export interface BacklogMutation {
    /**
     * Mutation operation to execute.
     * @type {BacklogAction}
     */
    action: BacklogAction;
    /**
     * Existing task identifier for task-specific mutations.
     * @type {string | undefined}
     */
    taskId?: string;
    /**
     * Canonical domain used when creating or moving a task.
     * @type {string | undefined}
     */
    domain?: string;
    /**
     * Human-readable task title.
     * @type {string | undefined}
     */
    title?: string;
    /**
     * Complete task description.
     * @type {string | undefined}
     */
    description?: string;
    /**
     * Accepted canonical or CLI-compatible priority value.
     * @type {"HIGH" | "MEDIUM" | "LOW" | "high" | "medium" | "low" | undefined}
     */
    priority?: "HIGH" | "MEDIUM" | "LOW" | "high" | "medium" | "low";
    /**
     * Whether a protected destructive mutation is explicitly forced.
     * @type {boolean | undefined}
     */
    force?: boolean;
    /**
     * Optional base64 image attachment, or null to remove it.
     * @type {string | null | undefined}
     */
    image?: string | null;
}
