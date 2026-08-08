/**
 * Inert HTML renderer for the persistent shell navigation registry.
 *
 * @module presentation/shell/renderers/shell-navigation-renderer
 */

import type { RouteId } from "../../../application/shell/contracts/shell-contracts.ts";
import { escapeHtml } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import { SHELL_ROUTES } from "../config/shell-routes.ts";

/**
 * Render all persistent navigation buttons and the active-route state.
 *
 * @param {RouteId} activeRouteId Route identity currently owned by the shell state store.
 * @returns {string} Inert navigation-button markup in canonical registry order.
 */
export function renderShellNavigation(activeRouteId: RouteId, hasPreservedQuery: boolean = false): string {
    const returnToResultsButton = `
        <button class="side-nav-item side-nav-return-results" ${hasPreservedQuery && activeRouteId !== "query" ? "" : "hidden"} data-action="return-to-results" data-tooltip="Search Results" aria-label="Search Results">
            ${icon("search")}
            <span class="nav-label">Search Results</span>
        </button>
    `;
    return returnToResultsButton + SHELL_ROUTES.filter(route => route.nav !== false).map(route => `
        <button class="side-nav-item ${route.id === activeRouteId ? "is-active" : ""}" data-route="${route.id}" data-tooltip="${escapeHtml(route.label)}" aria-label="${escapeHtml(route.label)}">
            ${icon(route.icon)}
            <span class="nav-label">${escapeHtml(route.label)}</span>
        </button>
    `).join("");
}
