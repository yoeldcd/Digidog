/**
 * Runtime narrowing for route identifiers crossing outer-layer boundaries.
 *
 * @module application/shell/validators/route-id
 */

import type { RouteId } from "../contracts/shell-contracts.ts";

/**
 * Complete closed route vocabulary accepted by Explorer navigation state.
 */
const ROUTE_IDS: readonly RouteId[] = [
    "dashboard", "memory", "knowledge", "pictures", "query", "profiles",
    "logs", "backlog", "messages", "wikis", "settings",
];

/**
 * Narrow an untrusted DOM or API string to the application route contract.
 *
 * This validator deliberately lives in Application rather than the shell route
 * registry so feature layouts can validate navigation without importing the
 * Presentation composition root and creating a circular module dependency.
 *
 * @param {string | null} value Untrusted route identifier read at an outer-layer boundary.
 * @returns {boolean} `true` only when `value` belongs to the complete route vocabulary.
 */
export function isRouteId(value: string | null): value is RouteId {
    return value !== null && ROUTE_IDS.some(route => route === value);
}
