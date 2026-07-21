/**
 * Projects the flat log index into a year, month, day, and entry hierarchy.
 *
 * The projector is deliberately independent from DOM state so date grouping can be
 * reused and tested without instantiating the Logs Web Component.
 *
 * @module presentation/logs/projectors/log-date-tree-projector
 */

import type { LogEntryPayload } from "../../../application/logs/dtos/responses/logs-response.ts";
import { logClockMinute } from "../formatters/log-entry-parser.ts";
import type { LogDateGroup } from "../view_models/logs-view-model.ts";
import type { StructureTreeNode } from "../../shared/view_models/structure-tree-view-model.ts";

/**
 * Month labels indexed by their one-based numeric month value.
 */
const LOG_MONTH_LABELS: readonly string[] = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
];

/**
 * Build shared tree nodes ordered from the newest year and month to the oldest.
 *
 * Malformed timestamps are omitted because they cannot be assigned to an honest
 * calendar branch; their underlying records remain available in domain mode.
 *
 * @param {readonly LogEntryPayload[]} entries Complete immutable log-index projection returned by the API.
 * @returns {StructureTreeNode[]} Date hierarchy compatible with the shared structure-tree component.
 */
export function projectLogDateTree(entries: readonly LogEntryPayload[]): StructureTreeNode[] {
    const years = new Map<string, LogDateGroup>();
    entries.forEach((entry, index) => appendDateEntry(years, entry, index));
    return Array.from(years.values())
        .sort((left, right) => right.id.localeCompare(left.id))
        .map(projectDateGroup);
}

/**
 * Append one valid index entry to its year, month, and day accumulators.
 *
 * @param {Map<string, LogDateGroup>} years Mutable top-level accumulator map owned by one projection call.
 * @param {LogEntryPayload} entry Structured log-index entry to classify.
 * @param {number} index Stable source position used to disambiguate render identities.
 */
function appendDateEntry(years: Map<string, LogDateGroup>, entry: LogEntryPayload, index: number): void {
    const [date = "", ...timeParts] = String(entry.timestamp || "").split(" ");
    const match = date.match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (!match) return;
    const day = match[1] ?? "";
    const month = match[2] ?? "";
    const year = match[3] ?? "";
    const time = timeParts.join(" ");
    const monthLabel = LOG_MONTH_LABELS[Number(month)] || month;
    const yearNode = ensureDateGroup(years, `logs-date:${year}`, year, "folder");
    const monthNode = ensureDateGroup(yearNode.children, `logs-date:${year}-${month}`, monthLabel, "folder");
    const dayNode = ensureDateGroup(
        monthNode.children,
        `logs-date:${year}-${month}-${day}`,
        `${day} ${monthLabel}`,
        "clock"
    );
    dayNode.entries.push({
        id: `logs-date-entry:${index}:${date}:${time}:${entry.domain || "logs"}`,
        path: `logs-date-entry:${date}:${time}:${entry.domain || "logs"}`,
        label: entry.title || "Log entry",
        timestamp: time,
        sortKey: String(logClockMinute(time)).padStart(4, "0"),
        detail: entry.domain || "logs",
        presentation: "log",
        domain: entry.domain || "",
        date,
        time,
        children: []
    });
}

/**
 * Create or retrieve one sibling date-group accumulator.
 *
 * @param {Map<string, LogDateGroup>} groups Mutable sibling map for a single calendar depth.
 * @param {string} id Stable structural identity for the group.
 * @param {string} label Human-readable group label.
 * @param {"edit" | "settings" | "home" | "database" | "graph" | "search" | "messageCircle" | "sliders" | "users" | "document" | "plus" | "documentPlus" | "folderPlus" | "copy" | "trash" | "save" | "refresh" | "pulse" | "folder" | "moon" | "sun" | "terminal" | "close" | "collapseLeft" | "expandRight" | "eye" | "filter" | "checkSquare" | "chevronRight" | "chevronLeft" | "chevronDown" | "minus" | "more" | "clock" | "camera" | "book" | "volume" | "play" | "pause" | "download"} icon Registered shared-tree icon associated with this depth.
 * @returns {LogDateGroup} Existing or newly created accumulator stored in `groups`.
 */
function ensureDateGroup(
    groups: Map<string, LogDateGroup>,
    id: string,
    label: string,
    icon: LogDateGroup["icon"]
): LogDateGroup {
    const existing = groups.get(id);
    if (existing) return existing;
    const created: LogDateGroup = { id, label, icon, children: new Map(), entries: [] };
    groups.set(id, created);
    return created;
}

/**
 * Convert one mutable accumulator and all descendants into immutable tree nodes.
 *
 * @param {LogDateGroup} group Calendar accumulator to project.
 * @returns {StructureTreeNode} Shared tree node containing sorted subgroup and terminal entry children.
 */
function projectDateGroup(group: LogDateGroup): StructureTreeNode {
    const groups = Array.from(group.children.values())
        .sort((left, right) => right.id.localeCompare(left.id))
        .map(projectDateGroup);
    const entries = [...group.entries].sort((left, right) => right.timestamp.localeCompare(left.timestamp));
    return {
        id: group.id,
        path: group.id,
        label: group.label,
        sortKey: group.id,
        icon: group.icon,
        count: countDateEntries(group),
        sortDirection: "desc",
        children: [...groups, ...entries]
    };
}

/**
 * Count terminal log entries recursively beneath a calendar group.
 *
 * @param {LogDateGroup} group Calendar accumulator whose descendants must be counted.
 * @returns {number} Total number of terminal entries owned by the group hierarchy.
 */
function countDateEntries(group: LogDateGroup): number {
    return group.entries.length + Array.from(group.children.values())
        .reduce((total, child) => total + countDateEntries(child), 0);
}
