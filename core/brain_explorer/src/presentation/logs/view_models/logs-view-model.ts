/**
 * View-ready contracts for the Logs presentation feature.
 *
 * The contracts in this module separate normalized rendering data and mutable
 * tree-building accumulators from the Logs Web Component. They intentionally do
 * not perform API access or DOM work.
 *
 * @module presentation/logs/view_models/logs-view-model
 */

import type { IconName } from "../../shared/utils/icons.ts";
import type { StructureTreeNode } from "../../shared/view_models/structure-tree-view-model.ts";

/**
 * Sort direction supported by the Logs list and shared tree.
 */
export type LogsSortOrder = "asc" | "desc";

/**
 * Active grouping projection used by the Logs navigation tree.
 */
export type LogsTreeMode = "domain" | "date";

/**
 * Narrowed SPA target accepted when navigation opens the Logs layout.
 */
export interface LogsRouteTarget {
    /**
     * Domain selected in the domain tree.
     * @type {string | undefined}
     */
    domain?: string;
    /**
     * Exact date used as shorthand for both range boundaries.
     * @type {string | undefined}
     */
    date?: string;
    /**
     * Exact time used as shorthand for both hour boundaries.
     * @type {string | undefined}
     */
    time?: string;
    /**
     * Inclusive first date in `DD-MM-YYYY` form.
     * @type {string | undefined}
     */
    from?: string;
    /**
     * Inclusive final date in `DD-MM-YYYY` form.
     * @type {string | undefined}
     */
    to?: string;
    /**
     * Inclusive first time in `HH:MM` form.
     * @type {string | undefined}
     */
    hourFrom?: string;
    /**
     * Inclusive final time in `HH:MM` form.
     * @type {string | undefined}
     */
    hourTo?: string;
    /**
     * Requested chronological ordering.
     * @type {LogsSortOrder | undefined}
     */
    sortOrder?: LogsSortOrder;
}

/**
 * Normalized log entry consumed by the operational-card renderer.
 */
export interface ParsedLogEntryViewModel {
    /**
     * Stable render identity for this response-local record.
     * @type {string}
     */
    id: string;
    /**
     * Calendar label extracted from the CLI timestamp.
     * @type {string}
     */
    date: string;
    /**
     * Clock label extracted from the CLI timestamp.
     * @type {string}
     */
    time: string;
    /**
     * Comparable number of minutes after midnight.
     * @type {number}
     */
    hourValue: number;
    /**
     * Comparable JavaScript epoch time used for ordering.
     * @type {number}
     */
    timestamp: number;
    /**
     * Dot-delimited owning log domain.
     * @type {string}
     */
    domain: string;
    /**
     * Human-readable change title.
     * @type {string}
     */
    title: string;
    /**
     * Presentation category displayed in the entry tags.
     * @type {"log"}
     */
    type: "log";
    /**
     * Change classification recorded by the CLI.
     * @type {string}
     */
    changeType: string;
    /**
     * Explanation of the motivation for the change.
     * @type {string}
     */
    why: string;
    /**
     * Markdown description of the performed work.
     * @type {string}
     */
    description: string;
    /**
     * Markdown description of the resulting impact.
     * @type {string}
     */
    impact: string;
    /**
     * Safe attachment file names discovered in the entry body.
     * @type {string[]}
     */
    pictures: string[];
}

/**
 * Flat record used while projecting dot-delimited domains into a tree.
 */
export interface LogDomainRecord {
    /**
     * Unique dot path represented by this record.
     * @type {string}
     */
    path: string;
    /**
     * Visible tree label.
     * @type {string}
     */
    label: string;
    /**
     * CLI command that addresses a terminal indexed record.
     * @type {string}
     */
    command: string;
    /**
     * Indexed date when this record represents a terminal entry.
     * @type {string}
     */
    date: string;
    /**
     * Indexed time when this record represents a terminal entry.
     * @type {string}
     */
    time: string;
    /**
     * Whether this record is a terminal entry rather than a domain.
     * @type {boolean}
     */
    leaf: boolean;
}

/**
 * Mutable internal domain-tree node produced from flat index records.
 */
export interface LogDomainTreeNode {
    /**
     * Visible label for the current path segment.
     * @type {string}
     */
    label: string;
    /**
     * Stable dot-delimited node identity.
     * @type {string}
     */
    path: string;
    /**
     * Domain path selected when the node is activated.
     * @type {string}
     */
    targetPath: string;
    /**
     * Child nodes keyed by their immediate path segment.
     * @type {Map<string, LogDomainTreeNode>}
     */
    children: Map<string, LogDomainTreeNode>;
    /**
     * Optional read-log command associated with a terminal record.
     * @type {string}
     */
    command: string;
    /**
     * Whether this node represents an indexed log entry.
     * @type {boolean}
     */
    leaf: boolean;
    /**
     * Number of terminal entries accumulated directly below this node.
     * @type {number}
     */
    entryCount: number;
    /**
     * Indexed entry date when present.
     * @type {string | undefined}
     */
    date?: string;
    /**
     * Indexed entry time when present.
     * @type {string | undefined}
     */
    time?: string;
}

/**
 * Date-tree leaf enriched with the target required to load its log record.
 */
export interface LogDateTreeEntry extends StructureTreeNode {
    /**
     * Clock label used to order entries inside one calendar day.
     * @type {string}
     */
    timestamp: string;
    /**
     * Dot-delimited log domain loaded by selection.
     * @type {string}
     */
    domain: string;
    /**
     * Exact indexed date loaded by selection.
     * @type {string}
     */
    date: string;
    /**
     * Exact indexed time loaded by selection.
     * @type {string}
     */
    time: string;
}

/**
 * Mutable accumulator used to group indexed entries by year, month, and day.
 */
export interface LogDateGroup {
    /**
     * Stable chronological group identity.
     * @type {string}
     */
    id: string;
    /**
     * Human-readable year, month, or day label.
     * @type {string}
     */
    label: string;
    /**
     * Registered icon rendered for this hierarchy level.
     * @type {"edit" | "settings" | "home" | "database" | "graph" | "search" | "messageCircle" | "sliders" | "users" | "document" | "plus" | "documentPlus" | "folderPlus" | "copy" | "trash" | "save" | "refresh" | "pulse" | "folder" | "moon" | "sun" | "terminal" | "close" | "collapseLeft" | "expandRight" | "eye" | "filter" | "checkSquare" | "chevronRight" | "chevronLeft" | "chevronDown" | "minus" | "more" | "clock" | "camera" | "book" | "volume" | "play" | "pause" | "download"}
     */
    icon: IconName;
    /**
     * Nested chronological groups keyed by stable identity.
     * @type {Map<string, LogDateGroup>}
     */
    children: Map<string, LogDateGroup>;
    /**
     * Terminal log entries owned directly by this group.
     * @type {LogDateTreeEntry[]}
     */
    entries: LogDateTreeEntry[];
}
