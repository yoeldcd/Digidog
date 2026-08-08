/**
 * Project chronological log entries into functional separator groups.
 *
 * @module presentation/logs/projectors/log-entry-group-projector
 */

import type { ParsedLogEntryViewModel } from "../view_models/logs-view-model.ts";

/**
 * Supported functional grouping dimensions for rendered log entries.
 */
export type LogEntryGroupMode = "domain" | "date";

/**
 * One ordered collection rendered below a single authentic log separator.
 */
export interface LogEntryGroup {
    /**
     * Stable grouping key.
     * @type {string}
     */
    key: string;
    /**
     * Human-readable separator label.
     * @type {string}
     */
    label: string;
    /**
     * Grouping dimension used by presentation styles.
     * @type {LogEntryGroupMode}
     */
    mode: LogEntryGroupMode;
    /**
     * Chronologically ordered entries owned by this group.
     * @type {ParsedLogEntryViewModel[]}
     */
    entries: ParsedLogEntryViewModel[];
}

/**
 * Group entries without losing their chronological order inside each group.
 * Domain groups are alphabetical; date groups preserve the date order already
 * established by the active ascending or descending log projection.
 *
 * @param {readonly ParsedLogEntryViewModel[]} entries Chronologically projected log entries.
 * @param {LogEntryGroupMode} mode Functional separator dimension.
 * @returns {LogEntryGroup[]} Ordered groups ready for rendering.
 */
export function projectLogEntryGroups(
    entries: readonly ParsedLogEntryViewModel[],
    mode: LogEntryGroupMode
): LogEntryGroup[] {
    const groups = new Map<string, LogEntryGroup>();
    for (const entry of entries) {
        const key = mode === "domain" ? (entry.domain || "logs") : (entry.date || "Unknown date");
        const group = groups.get(key) ?? { key, label: key, mode, entries: [] };
        group.entries.push(entry);
        groups.set(key, group);
    }
    const projected = [...groups.values()];
    return mode === "domain"
        ? projected.sort((left, right) => left.label.localeCompare(right.label))
        : projected;
}
