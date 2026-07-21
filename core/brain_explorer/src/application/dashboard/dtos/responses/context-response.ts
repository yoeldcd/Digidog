/**
 * Transport response contracts returned by the Dashboard context endpoint.
 *
 * @module application/dashboard/dtos/responses/context-response
 */

import type { RouteId } from "../../../shell/contracts/shell-contracts.ts";

/**
 * Route-specific destination metadata supplied by a context card.
 */
export interface ContextTarget {
    /**
     * Canonical domain selected by the destination feature.
     * @type {string | undefined}
     */
    domain?: string;
    /**
     * Calendar date selected by the destination feature.
     * @type {string | undefined}
     */
    date?: string;
    /**
     * Local time selected by the destination feature.
     * @type {string | undefined}
     */
    time?: string;
    /**
     * Canonical record or filesystem path selected by the destination feature.
     * @type {string | undefined}
     */
    path?: string;
    /**
     * Additional feature-owned fields that are validated by the destination.
     */
    [key: string]: unknown;
}

/**
 * One actionable record contained by a dashboard context section.
 */
export interface ContextItem {
    /**
     * Changelog category associated with the record.
     * @type {string | undefined}
     */
    changeType?: string;
    /**
     * CLI command that can reproduce or inspect the record.
     * @type {string | undefined}
     */
    command?: string;
    /**
     * Calendar date associated with the record.
     * @type {string | undefined}
     */
    date?: string;
    /**
     * Canonical dotted ownership domain.
     * @type {string | undefined}
     */
    domain?: string;
    /**
     * Stable record identifier.
     * @type {string | undefined}
     */
    id?: string;
    /**
     * Human-readable record label.
     * @type {string | undefined}
     */
    label?: string;
    /**
     * Explorer route opened by the record.
     * @type {RouteId | undefined}
     */
    route?: RouteId;
    /**
     * Route-specific target metadata.
     * @type {ContextTarget | undefined}
     */
    target?: ContextTarget;
    /**
     * Local time associated with the record.
     * @type {string | undefined}
     */
    time?: string;
    /**
     * Server-defined record classification.
     * @type {string | undefined}
     */
    type?: string;
}

/**
 * One status or content section returned by the live workspace context query.
 */
export interface ContextSection {
    /**
     * Markdown body used by document-style sections.
     * @type {string | undefined}
     */
    body?: string;
    /**
     * Actionable records belonging to the section.
     * @type {ContextItem[] | undefined}
     */
    items?: ContextItem[];
    /**
     * Stable server-defined section category.
     * @type {string | undefined}
     */
    kind?: string;
    /**
     * Canonical source path associated with the section.
     * @type {string | undefined}
     */
    path?: string;
    /**
     * Default Explorer route opened by the section.
     * @type {RouteId | undefined}
     */
    route?: RouteId;
    /**
     * Health or availability status associated with the section.
     * @type {string | undefined}
     */
    status?: string;
    /**
     * Compact human-readable section summary.
     * @type {string | undefined}
     */
    summary?: string;
    /**
     * Human-readable section title.
     * @type {string | undefined}
     */
    title?: string;
}

/**
 * Payload returned by the dashboard context endpoint.
 */
export interface ContextResponse {
    /**
     * Ordered context sections rendered by the Dashboard feature.
     * @type {ContextSection[] | undefined}
     */
    sections?: ContextSection[];
}
