/**
 * Validate route targets encoded in the Explorer startup URL.
 *
 * @module application/shell/validators/startup-route-target
 */

import type { RouteId } from "../contracts/shell-contracts.ts";
import { isRouteId } from "./route-id.ts";

/**
 * Validated route and destination payload restored during application bootstrap.
 */
export interface StartupRouteTarget {
    /**
     * Explorer section selected by the startup URL.
     * @type {RouteId}
     */
    route: RouteId;
    /**
     * Validated route-specific target fields.
     * @type {Record<string, unknown>}
     */
    target: Record<string, unknown>;
}

/**
 * Parse a startup query string into a safe Explorer route target.
 *
 * Only a canonical ``tN`` task identifier is forwarded to Backlog. Unknown
 * sections and malformed targets are ignored instead of mutating shell state.
 *
 * @param {string} search Raw ``window.location.search`` value.
 * @returns {StartupRouteTarget | null} Validated startup target, or null when absent or invalid.
 */
export function parseStartupRouteTarget(search: string): StartupRouteTarget | null {
    const parameters = new URLSearchParams(search);
    const section = parameters.get("section");
    if (!isRouteId(section)) return null;

    const target: Record<string, unknown> = {};
    const taskId = parameters.get("task")?.trim() ?? "";
    if (section === "backlog" && /^t\d+$/i.test(taskId)) {
        target.taskId = taskId.toLowerCase();
    }
    return { route: section, target };
}
