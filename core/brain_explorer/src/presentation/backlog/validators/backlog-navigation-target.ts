/**
 * Runtime validation for Backlog route targets.
 *
 * @module presentation/backlog/validators/backlog-navigation-target
 */

/**
 * Validated route payload consumed by the Backlog view.
 */
export interface BacklogNavigationTarget {
    /**
     * Canonical task identifier to reveal and focus.
     * @type {string}
     */
    taskId: string;
}

/**
 * Narrow an untrusted shell target to a canonical Backlog navigation target.
 *
 * @param {Record<string, unknown> | null} target Raw destination payload from application state.
 * @returns {BacklogNavigationTarget | null} Valid target, or null when no canonical task id exists.
 */
export function parseBacklogNavigationTarget(
    target: Record<string, unknown> | null,
): BacklogNavigationTarget | null {
    const taskId = typeof target?.taskId === "string" ? target.taskId.trim() : "";
    return /^t\d+$/i.test(taskId) ? { taskId: taskId.toLowerCase() } : null;
}
