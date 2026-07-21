/**
 * Runtime narrowing for route state entering the Logs presentation feature.
 */

import type { LogsRouteTarget, LogsSortOrder } from "../view_models/logs-view-model.ts";

/**
 * Return a string property from an unknown route record when present.
 *
 * @param {Record<string, unknown>} record Untrusted route record consumed from shell navigation state.
 * @param {string} key Property name whose string value is requested.
 * @returns {string | undefined} The string property, or `undefined` for absent and non-string values.
 */
function optionalString(record: Record<string, unknown>, key: string): string | undefined {
    const value = record[key];
    return typeof value === "string" ? value : undefined;
}

/**
 * Determine whether an unknown value is a supported Logs sort order.
 *
 * @param {unknown} value Unknown sort value supplied by route state.
 * @returns {boolean} True only for the closed ascending and descending order literals.
 */
function isLogsSortOrder(value: unknown): value is LogsSortOrder {
    return value === "asc" || value === "desc";
}

/**
 * Converts an untrusted SPA route record into the explicit Logs target model.
 *
 * @param {Record<string, unknown> | null} value Unknown value consumed from global route state.
 * @returns {LogsRouteTarget | null} A safely narrowed target, or `null` when no record was supplied.
 */
export function logsRouteTarget(value: Record<string, unknown> | null): LogsRouteTarget | null {
    if (!value) return null;
    const target: LogsRouteTarget = {};
    const stringKeys = ["domain", "date", "time", "from", "to", "hourFrom", "hourTo"] as const;
    for (const key of stringKeys) {
        const property = optionalString(value, key);
        if (property !== undefined) target[key] = property;
    }
    if (isLogsSortOrder(value.sortOrder)) target.sortOrder = value.sortOrder;
    return target;
}
