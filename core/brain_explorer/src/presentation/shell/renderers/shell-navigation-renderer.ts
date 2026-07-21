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
export function renderShellNavigation(activeRouteId: RouteId): string {
    return SHELL_ROUTES.filter(route => route.nav !== false).map(route => `
        <button class="side-nav-item ${route.id === activeRouteId ? "is-active" : ""}" data-route="${route.id}" data-tooltip="${escapeHtml(route.label)}" aria-label="${escapeHtml(route.label)}">
            ${icon(route.icon)}
            <span class="nav-label">${escapeHtml(route.label)}</span>
        </button>
    `).join("");
}
