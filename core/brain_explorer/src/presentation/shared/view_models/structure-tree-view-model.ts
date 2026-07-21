/**
 * Shared, framework-neutral contracts for the reusable hierarchical tree component.
 *
 * Feature layouts project their domain-specific records into these view models and
 * validate emitted Custom Event details through the boundary helpers in this module.
 * No interface declared here owns API, persistence, or feature business semantics.
 *
 * @module presentation/shared/view_models/structure-tree-view-model
 */

import type { IconName } from "../utils/icons.ts";

/**
 * One contextual or toolbar action exposed by the shared tree.
 */
export interface StructureTreeAction {
    /**
     * Stable machine-readable action identifier emitted in event details.
     * @type {string}
     */
    id: string;
    /**
     * Human-readable action label used by menus and accessibility text.
     * @type {string}
     */
    label: string;
    /**
     * Optional icon rendered before the visible action label.
     * @type {"edit" | "settings" | "home" | "database" | "graph" | "search" | "messageCircle" | "sliders" | "users" | "document" | "plus" | "documentPlus" | "folderPlus" | "copy" | "trash" | "save" | "refresh" | "pulse" | "folder" | "moon" | "sun" | "terminal" | "close" | "collapseLeft" | "expandRight" | "eye" | "filter" | "checkSquare" | "chevronRight" | "chevronLeft" | "chevronDown" | "minus" | "more" | "clock" | "camera" | "book" | "volume" | "play" | "pause" | "download" | undefined}
     */
    icon?: IconName;
    /**
     * Whether the action represents a destructive operation.
     * @type {boolean | undefined}
     */
    danger?: boolean;
    /**
     * Whether the action currently represents an active toggle state.
     * @type {boolean | undefined}
     */
    active?: boolean;
}

/**
 * Recursive, render-ready node accepted by the shared tree component.
 */
export interface StructureTreeNode {
    /**
     * Stable node identity unique within the current tree model.
     * @type {string}
     */
    id: string;
    /**
     * Canonical selection path emitted when the node is activated.
     * @type {string}
     */
    path: string;
    /**
     * Human-readable node label.
     * @type {string}
     */
    label: string;
    /**
     * Optional explicit icon overriding the component branch/leaf defaults.
     * @type {"edit" | "settings" | "home" | "database" | "graph" | "search" | "messageCircle" | "sliders" | "users" | "document" | "plus" | "documentPlus" | "folderPlus" | "copy" | "trash" | "save" | "refresh" | "pulse" | "folder" | "moon" | "sun" | "terminal" | "close" | "collapseLeft" | "expandRight" | "eye" | "filter" | "checkSquare" | "chevronRight" | "chevronLeft" | "chevronDown" | "minus" | "more" | "clock" | "camera" | "book" | "volume" | "play" | "pause" | "download" | undefined}
     */
    icon?: IconName;
    /**
     * Optional aggregate value rendered at the trailing edge of the row.
     * @type {string | number | undefined}
     */
    count?: number | string;
    /**
     * Optional secondary text rendered beneath or beside the primary label.
     * @type {string | undefined}
     */
    detail?: string;
    /**
     * Optional chronological label used by log-style rows.
     * @type {string | undefined}
     */
    timestamp?: string;
    /**
     * Explicit branch hint for empty folders that do not yet have children.
     * @type {boolean | undefined}
     */
    folder?: boolean;
    /**
     * Closed visual row treatment selected by the owning feature.
     * @type {"log" | "default" | undefined}
     */
    presentation?: "default" | "log";
    /**
     * Contextual actions available for this node.
     * @type {StructureTreeAction[] | undefined}
     */
    actions?: StructureTreeAction[];
    /**
     * Recursively nested child nodes in display order.
     * @type {StructureTreeNode[] | undefined}
     */
    children?: StructureTreeNode[];
    /**
     * Optional feature color applied to the node marker.
     * @type {string | undefined}
     */
    color?: string;
    /**
     * Optional per-node child sorting direction.
     * @type {"asc" | "desc" | undefined}
     */
    sortDirection?: "asc" | "desc";
    /**
     * Optional normalized value used instead of `label` when sorting siblings.
     * @type {string | undefined}
     */
    sortKey?: string;
}

/**
 * Complete normalized configuration retained by `StructureTree`.
 */
export interface StructureTreeModel {
    /**
     * Root nodes rendered by the tree.
     * @type {StructureTreeNode[]}
     */
    nodes: StructureTreeNode[];
    /**
     * Canonical path of the currently selected node.
     * @type {string}
     */
    selectedPath: string;
    /**
     * Canonical paths of branches whose children are visible.
     * @type {Set<string>}
     */
    expandedPaths: Set<string>;
    /**
     * Whether selecting a branch row also toggles its expansion state.
     * @type {boolean}
     */
    toggleOnBranchSelect: boolean;
    /**
     * Human-readable tree title rendered in the sidepanel toolbar.
     * @type {string}
     */
    title: string;
    /**
     * Global actions rendered in the tree toolbar.
     * @type {StructureTreeAction[]}
     */
    toolbarActions: StructureTreeAction[];
    /**
     * Whether the built-in text filter control is visible.
     * @type {boolean}
     */
    showSearch: boolean;
    /**
     * Placeholder displayed by the built-in text filter control.
     * @type {string}
     */
    searchPlaceholder: string;
    /**
     * Default sibling sorting direction.
     * @type {"asc" | "desc"}
     */
    sortDirection: "asc" | "desc";
    /**
     * Empty-state message rendered when no node survives filtering.
     * @type {string}
     */
    emptyText: string;
    /**
     * Default icon for branch nodes, or `null` to render no branch icon.
     * @type {"edit" | "settings" | "home" | "database" | "graph" | "search" | "messageCircle" | "sliders" | "users" | "document" | "plus" | "documentPlus" | "folderPlus" | "copy" | "trash" | "save" | "refresh" | "pulse" | "folder" | "moon" | "sun" | "terminal" | "close" | "collapseLeft" | "expandRight" | "eye" | "filter" | "checkSquare" | "chevronRight" | "chevronLeft" | "chevronDown" | "minus" | "more" | "clock" | "camera" | "book" | "volume" | "play" | "pause" | "download" | null}
     */
    defaultBranchIcon: IconName | null;
    /**
     * Default icon for terminal nodes, or `null` to render no leaf icon.
     * @type {"edit" | "settings" | "home" | "database" | "graph" | "search" | "messageCircle" | "sliders" | "users" | "document" | "plus" | "documentPlus" | "folderPlus" | "copy" | "trash" | "save" | "refresh" | "pulse" | "folder" | "moon" | "sun" | "terminal" | "close" | "collapseLeft" | "expandRight" | "eye" | "filter" | "checkSquare" | "chevronRight" | "chevronLeft" | "chevronDown" | "minus" | "more" | "clock" | "camera" | "book" | "volume" | "play" | "pause" | "download" | null}
     */
    defaultLeafIcon: IconName | null;
}

/**
 * Partial configuration accepted by the public tree setter.
 *
 * `nodes` remains mandatory because an update without a source collection cannot
 * define a coherent tree. `searchQuery` and `disableFilter` are transient setter
 * controls and are therefore not retained in the normalized `StructureTreeModel`.
 */
export type StructureTreeModelInput = Partial<StructureTreeModel> & {
    /**
     * Root nodes that replace the component's current source collection.
     * @type {StructureTreeNode[]}
     */
    nodes: StructureTreeNode[];
    /**
     * Optional search query applied immediately after model normalization.
     * @type {string | undefined}
     */
    searchQuery?: string;
    /**
     * Whether this update bypasses the built-in recursive text filter.
     * @type {boolean | undefined}
     */
    disableFilter?: boolean;
};

/**
 * Validated detail emitted when a tree row or caret is selected.
 */
export interface TreeSelectDetail {
    /**
     * Canonical path of the selected node.
     * @type {string}
     */
    path: string;
    /**
     * Whether the selected node owns or represents a branch.
     * @type {boolean}
     */
    branch: boolean;
    /**
     * Whether the pointer activation originated on the expansion caret.
     * @type {boolean}
     */
    clickedCaret: boolean;
}

/**
 * Validated detail emitted by tree toolbar and contextual node actions.
 */
export interface TreeActionDetail {
    /**
     * Stable action identifier supplied by the tree model.
     * @type {string}
     */
    action: string;
    /**
     * Minimal selected node projection when the event targets a node action.
     * @type {StructureTreeNode | null | undefined}
     */
    node?: StructureTreeNode | null;
}

/**
 * Detail emitted when the reusable tree search query changes.
 */
export interface TreeSearchDetail {
    /**
     * Current raw search query entered by the user.
     * @type {string}
     */
    query: string;
}

/**
 * Convert an unknown object to an indexable record without a type assertion.
 *
 * @param {unknown} value Untrusted value crossing the DOM Custom Event boundary.
 * @returns {Record<string, unknown> | null} A shallow record copy, or `null` for primitives, arrays, and null.
 */
function detailRecord(value: unknown): Record<string, unknown> | null {
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
export function treeSelectDetail(value: unknown): TreeSelectDetail | null {
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
export function treeActionDetail(value: unknown): TreeActionDetail | null {
    const detail = detailRecord(value);
    if (!detail || typeof detail.action !== "string") return null;
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
export function treeSearchDetail(value: unknown): TreeSearchDetail | null {
    const detail = detailRecord(value);
    return detail && typeof detail.query === "string" ? { query: detail.query } : null;
}
