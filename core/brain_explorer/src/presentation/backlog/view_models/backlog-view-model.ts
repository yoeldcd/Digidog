/**
 * View-ready contracts owned by the main Backlog presentation feature.
 *
 * @module presentation/backlog/view_models/backlog-view-model
 */

/**
 * Mutable domain hierarchy used while projecting task domains into tree rows.
 */
export interface BacklogDomainTreeNode {
    /**
     * Visible label for the current dot-path segment.
     * @type {string}
     */
    label: string;
    /**
     * Complete dot-delimited domain represented by the node.
     * @type {string}
     */
    path: string;
    /**
     * Child nodes keyed by their immediate path segment.
     * @type {Map<string, BacklogDomainTreeNode>}
     */
    children: Map<string, BacklogDomainTreeNode>;
}

/**
 * Closed status options rendered by the task filter menu.
 */
export const BACKLOG_STATUS_FILTER_OPTIONS = [
    ["TODO", "Pending"],
    ["WORKING", "In progress"],
    ["DONE", "Completed"],
] as const;

/**
 * Closed priority options rendered by the task filter menu.
 */
export const BACKLOG_PRIORITY_FILTER_OPTIONS = [
    ["HIGH", "High"],
    ["MEDIUM", "Medium"],
    ["LOW", "Low"],
] as const;
