/**
 * Date-tree metadata required to load one exact log record.
 */
export interface LogDateTreeSelection {
    /**
     * Dot-delimited log domain containing the record.
     * @type {string}
     */
    domain: string;
    /**
     * Indexed calendar date used for both range boundaries.
     * @type {string}
     */
    date: string;
    /**
     * Indexed clock time used for both hour boundaries.
     * @type {string}
     */
    time: string;
}

/**
 * Narrow the untrusted node attached to a shared tree-selection event.
 *
 * @param {unknown} value Unknown `node` member emitted across the Custom Event boundary.
 * @returns {LogDateTreeSelection | null} Validated date-tree metadata, or `null` when any required field is absent.
 */
export function logDateTreeSelection(value: unknown): LogDateTreeSelection | null {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
    const node = Object.fromEntries(Object.entries(value));
    if (typeof node.domain !== "string" || typeof node.date !== "string" || typeof node.time !== "string") return null;
    return { domain: node.domain, date: node.date, time: node.time };
}

/**
 * Read the optional node member from an untrusted tree event detail object.
 *
 * @param {unknown} value Unknown Custom Event detail value.
 * @returns {unknown} Raw node member for subsequent feature-specific validation.
 */
export function treeDetailNode(value: unknown): unknown {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return undefined;
    return Object.fromEntries(Object.entries(value)).node;
}
