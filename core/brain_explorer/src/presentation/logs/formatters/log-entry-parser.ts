/**
 * Converts transport-level log records into sorted, filterable presentation entries.
 *
 * This module owns deterministic parsing and picture-reference discovery so the Logs
 * Web Component remains responsible only for rendering and interaction orchestration.
 *
 * @module presentation/logs/formatters/log-entry-parser
 */

import type { LogEntryPayload } from "../../../application/logs/dtos/responses/logs-response.ts";
import type { LogsSortOrder, ParsedLogEntryViewModel } from "../view_models/logs-view-model.ts";

/**
 * Inputs required to produce the visible log-entry projection.
 */
export interface VisibleLogEntriesInput {
    /**
     * Structured records returned by the logs application endpoint.
     * @type {readonly LogEntryPayload[]}
     */
    entries: readonly LogEntryPayload[];
    /**
     * Domain selected in the Logs structure tree and used as a missing-domain fallback.
     * @type {string}
     */
    selectedDomain: string;
    /**
     * Earliest accepted clock time in browser `HH:MM` form, or an empty string.
     * @type {string}
     */
    hourFrom: string;
    /**
     * Latest accepted clock time in browser `HH:MM` form, or an empty string.
     * @type {string}
     */
    hourTo: string;
    /**
     * Direction used to order the resulting chronological projection.
     * @type {LogsSortOrder}
     */
    sortOrder: LogsSortOrder;
    /**
     * Task identifiers whose log records have an associated backlog image.
     * @type {readonly string[]}
     */
    logsWithImages: readonly string[];
}

/**
 * Produce normalized, hour-filtered, chronologically ordered log entries.
 *
 * @param {VisibleLogEntriesInput} input Complete immutable parsing and filtering context.
 * @returns {ParsedLogEntryViewModel[]} A new array suitable for direct rendering by the Logs layout.
 */
export function visibleLogEntries(input: VisibleLogEntriesInput): ParsedLogEntryViewModel[] {
    const earliestMinute = timeInputMinute(input.hourFrom);
    const latestMinute = timeInputMinute(input.hourTo);
    return input.entries
        .map((entry, index) => parsedLogEntry(entry, index, input.selectedDomain, input.logsWithImages))
        .filter(entry => minuteIsWithinRange(entry.hourValue, earliestMinute, latestMinute))
        .sort((left, right) => {
            const delta = left.timestamp - right.timestamp;
            return input.sortOrder === "asc" ? delta : -delta;
        });
}

/**
 * Normalize one transport record into the view model expected by the log-card renderer.
 *
 * @param {LogEntryPayload} entry Structured server record to normalize.
 * @param {number} index Stable array position used to build a local render identity.
 * @param {string} selectedDomain Domain fallback for records that omit their own domain.
 * @param {readonly string[]} logsWithImages Task ids known to own a backlog reference image.
 * @returns {ParsedLogEntryViewModel} Fully populated presentation entry with derived time and picture metadata.
 */
function parsedLogEntry(
    entry: LogEntryPayload,
    index: number,
    selectedDomain: string,
    logsWithImages: readonly string[]
): ParsedLogEntryViewModel {
    const [date = "", ...timeParts] = String(entry.timestamp || "").split(" ");
    const time = timeParts.join(" ");
    const searchableText = [entry.title, entry.why, entry.description, entry.impact].join("\n");
    return {
        id: `log-${index}`,
        date,
        time,
        hourValue: logClockMinute(time),
        timestamp: sortableTimestamp(date, time),
        domain: entry.domain || selectedDomain,
        title: entry.title || "Log entry",
        type: "log",
        changeType: entry.change_type || "",
        why: entry.why || "",
        description: entry.description || "",
        impact: entry.impact || "",
        pictures: pictureNames(searchableText, logsWithImages)
    };
}

/**
 * Extract unique safe picture filenames referenced by Markdown fields or task ids.
 *
 * @param {string} source Concatenated Markdown content belonging to one log record.
 * @param {readonly string[]} logsWithImages Task identifiers known to have a generated backlog picture.
 * @returns {string[]} Deduplicated filenames without directory traversal segments.
 */
function pictureNames(source: string, logsWithImages: readonly string[]): string[] {
    const names = new Set<string>();
    const matcher = /(?:\$agent[\\/])?pictures[\\/]([A-Za-z0-9][A-Za-z0-9._-]*\.(?:png|jpe?g|gif|webp))/gi;
    for (const match of String(source || "").matchAll(matcher)) {
        const name = match[1];
        if (name) names.add(name);
    }
    for (const match of String(source || "").matchAll(/#?(t\d+)\b/gi)) {
        const taskId = (match[1] ?? "").toLowerCase();
        if (logsWithImages.includes(taskId)) names.add(`backlog-pic-${taskId}.png`);
    }
    return [...names];
}

/**
 * Determine whether a minute value falls inside an optional inclusive range.
 *
 * @param {number} value Candidate minutes after midnight.
 * @param {number | null} earliest Inclusive lower bound, or null when unrestricted.
 * @param {number | null} latest Inclusive upper bound, or null when unrestricted.
 * @returns {boolean} True when the candidate satisfies both configured bounds.
 */
function minuteIsWithinRange(value: number, earliest: number | null, latest: number | null): boolean {
    if (earliest !== null && value < earliest) return false;
    if (latest !== null && value > latest) return false;
    return true;
}

/**
 * Parse a browser time-control value into minutes after midnight.
 *
 * @param {string} value Browser `HH:MM` value or an empty filter value.
 * @returns {number | null} Parsed minutes, or null when the value does not represent a complete time.
 */
function timeInputMinute(value: string): number | null {
    const match = String(value || "").match(/^(\d{2}):(\d{2})$/);
    return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}

/**
 * Parse a 12-hour or 24-hour log label into minutes after midnight.
 *
 * @param {string} label Human-readable clock label emitted by the log facade.
 * @returns {number} Parsed minutes, or zero when no clock value can be recognized.
 */
export function logClockMinute(label: string): number {
    const match = String(label || "").toLowerCase().match(/(\d{1,2}):(\d{2})\s*(am|pm)?/);
    if (!match) return 0;
    let hour = Number(match[1]);
    const minute = Number(match[2]);
    if (match[3] === "pm" && hour < 12) hour += 12;
    if (match[3] === "am" && hour === 12) hour = 0;
    return hour * 60 + minute;
}

/**
 * Combine exported date and time labels into a sortable local timestamp.
 *
 * @param {string} date Date label in `DD-MM-YYYY` form.
 * @param {string} time Clock label accepted by {@link logClockMinute}.
 * @returns {number} Milliseconds since the epoch, or zero for malformed dates.
 */
function sortableTimestamp(date: string, time: string): number {
    const match = String(date || "").match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (!match) return 0;
    const minutes = logClockMinute(time);
    return new Date(
        Number(match[3]),
        Number(match[2]) - 1,
        Number(match[1]),
        Math.floor(minutes / 60),
        minutes % 60
    ).getTime();
}
