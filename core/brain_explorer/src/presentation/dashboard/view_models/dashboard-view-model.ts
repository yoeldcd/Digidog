/**
 * Render-ready contracts projected by the Dashboard presentation feature.
 *
 * @module presentation/dashboard/view_models/dashboard-view-model
 */

import type { RouteId } from "../../../application/shell/contracts/shell-contracts.ts";
import type { IconName } from "../../shared/utils/icons.ts";

/**
 * Render-ready dashboard row projected from one server context item or section.
 */
export interface ContextEntry {
    /**
     * Stable entry category used to choose rendering semantics.
     * @type {string}
     */
    kind: string;
    /**
     * Symbol rendered beside the entry label.
     * @type {"edit" | "settings" | "home" | "database" | "graph" | "search" | "messageCircle" | "sliders" | "users" | "document" | "plus" | "documentPlus" | "folderPlus" | "copy" | "trash" | "save" | "refresh" | "pulse" | "folder" | "moon" | "sun" | "terminal" | "close" | "collapseLeft" | "expandRight" | "eye" | "filter" | "checkSquare" | "chevronRight" | "chevronLeft" | "chevronDown" | "minus" | "more" | "clock" | "camera" | "book" | "volume" | "play" | "pause" | "download"}
     */
    icon: IconName;
    /**
     * Primary human-readable entry label.
     * @type {string}
     */
    label: string;
    /**
     * Compact explanatory text.
     * @type {string}
     */
    summary: string;
    /**
     * Explorer destination opened by the entry.
     * @type {RouteId | undefined}
     */
    route?: RouteId;
    /**
     * Runtime-validated destination metadata.
     * @type {Record<string, unknown> | undefined}
     */
    target?: Record<string, unknown>;
    /**
     * Calendar date displayed for chronological entries.
     * @type {string | undefined}
     */
    date?: string;
    /**
     * Local time displayed for chronological entries.
     * @type {string | undefined}
     */
    time?: string;
    /**
     * Human-readable server record classification.
     * @type {string | undefined}
     */
    typeLabel?: string;
    /**
     * Optional expanded title.
     * @type {string | undefined}
     */
    title?: string;
    /**
     * Canonical dotted ownership domain.
     * @type {string | undefined}
     */
    domain?: string;
    /**
     * Changelog category associated with the entry.
     * @type {string | undefined}
     */
    changeType?: string;
}
