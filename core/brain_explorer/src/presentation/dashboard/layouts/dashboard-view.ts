/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml } from "../../shared/utils/html.ts";
import { icon, type IconName } from "../../shared/utils/icons.ts";
import type { ContextItem, ContextSection, ContextTarget } from "../../../application/dashboard/dtos/responses/context-response.ts";
import type { BrainApiClient } from "../../../infrastructure/shared/http/clients/brain-api-client.ts";
import type { AppState } from "../../shell/state/app-state.ts";
import type { ComponentContext } from "../../shared/view_models/component-context-view-model.ts";
import type { ContextEntry } from "../view_models/dashboard-view-model.ts";
import { isRouteId } from "../../../application/shell/validators/route-id.ts";

/**
 * DashboardView renders the `get-context --json` items as the Explorer entry point.
 */
export class DashboardView extends HTMLElement {
    /**
     * Registered Custom Element tag used by the shell route registry.
     * @returns {string} A string representing the component's DOM selector.
     */
    static get selector() {
        return "brain-dashboard-view";
    }

    /**
     * Injected Explorer HTTP adapter, or `null` before context assignment.
     * @type {BrainApiClient | null}
     */
    #api: BrainApiClient | null = null;
    /**
     * Injected shell state store, or `null` before context assignment.
     * @type {AppState | null}
     */
    #state: AppState | null = null;
    /**
     * Ordered live context sections returned by the Dashboard endpoint.
     * @type {ContextSection[]}
     */
    #contextSections: ContextSection[] = [];
    /**
     * Whether the initial or forced context request is in progress.
     * @type {boolean}
     */
    #loading = false;

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context: ComponentContext) {
        this.#api = context.api;
        this.#state = context.state;
        this.#load();
    }

    /**
     * Initialize the component.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
    }

    /**
     * Load live context from the explorer API.
     *
     * @param {boolean} forceRefresh Whether to bypass the browser API cache.
     * @returns {Promise<void>} Resolves after rendering.
     */
    async #load(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        this.#loading = true;
        this.#render();
        const context = await this.#api.context({ forceRefresh });
        this.#contextSections = Array.isArray(context.data?.sections) ? context.data.sections : [];
        this.#state?.setLastResult(context);
        this.#loading = false;
        this.#render();
    }

    /**
     * Render dashboard markup.
     *
     * @returns {void}
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface dashboard-view context-home">
                <main class="context-document scroll-area">
                    ${this.#loading ? this.#loadingState() : this.#renderContextDocument()}
                </main>
            </section>
        `;
        this.querySelector("[data-action='refresh-dashboard']")?.addEventListener("click", () => this.#load(true));
        this.querySelectorAll("[data-context-route]").forEach(button => {
            button.addEventListener("click", () => this.#openContextCard(button));
        });
    }

    /**
     * Open a context card destination.
     *
     * @param {Element} button Clicked card button.
     * @returns {void}
     */
    #openContextCard(button: Element): void {
        const routeValue = button.getAttribute("data-context-route");
        const route = isRouteId(routeValue) ? routeValue : "dashboard";
        const target = this.#decodeTarget(button.getAttribute("data-context-target") || "");
        this.#state?.setRouteTarget?.(route, target);
    }

    /**
     * Render the live context as a collapsible document outline.
     *
     * @returns {string} HTML.
     */
    #renderContextDocument(): string {
        if (!this.#contextSections.length) {
            return `
                <div class="knowledge-empty-state">
                    ${icon("document")}
                    <h2>Contexto no cargado</h2>
                    <p>Refresh to read the live workspace context.</p>
                </div>
            `;
        }
        const entryCount = this.#contextSections.reduce((total, section) => total + Math.max(1, Array.isArray(section.items) ? section.items.length : 0), 0);
        return `
            <article class="context-document-root context-outline">
                <div class="context-document-actions">
                    <span>${escapeHtml(String(entryCount))} enlaces</span>
                    <button data-action="refresh-dashboard" class="icon-action compact-action" title="Refresh context" aria-label="Refresh context">${icon("refresh")}</button>
                </div>
                <div class="context-tree-document">
                    ${this.#contextSections.map(section => this.#renderContextSection(section)).join("")}
                </div>
            </article>
        `;
    }

    /**
     * Render one context document section.
     *
     * @param {object} section Context section.
     * @returns {string} HTML.
     */
    #renderContextSection(section: ContextSection): string {
        const items = Array.isArray(section.items) ? section.items : [];
        const entries = items.length
            ? items.map(item => this.#itemEntry(section, item))
            : [this.#sectionEntry(section)].filter((entry): entry is ContextEntry => entry !== null);
        if (!entries.length) {
            return "";
        }
        const kind = section.kind || "item";
        return `
            <details class="context-tree-section context-kind-${escapeHtml(kind)}" open>
                <summary class="context-tree-summary">
                    <span class="context-summary-caret">${icon("chevronRight")}</span>
                    <span class="metric-icon">${icon(this.#sectionIcon(section))}</span>
                    <span class="context-summary-copy">
                        <strong>${escapeHtml(section.title || this.#sectionTitle(section))}</strong>
                        <small>${escapeHtml(section.summary || this.#sectionSummary(section, entries.length))}</small>
                    </span>
                    <span class="context-summary-count">${escapeHtml(String(entries.length))}</span>
                </summary>
                <div class="context-section-body">
                    ${this.#renderSectionBody(kind, entries)}
                </div>
            </details>
        `;
    }

    /**
     * Render section entries using type-specific document shapes.
     *
     * @param {string} kind Section kind.
     * @param {object[]} entries Normalized entries.
     * @returns {string} HTML.
     */
    #renderSectionBody(kind: string, entries: ContextEntry[]): string {
        if (kind === "logs") {
            const chronologicalEntries = this.#sortLogsNewestFirst(entries);
            return `
                <nav class="context-log-links" aria-label="Recent log entries">
                    ${chronologicalEntries.map(entry => this.#renderContextLine(entry, "context-link-line")).join("")}
                </nav>
            `;
        }
        if (kind === "diary") {
            return `
                <ol class="context-timeline">
                    ${entries.map(entry => `<li>${this.#renderContextLine(entry, "context-timeline-entry")}</li>`).join("")}
                </ol>
            `;
        }
        if (kind === "profiles") {
            return `
                <nav class="context-profile-links" aria-label="Available profiles">
                    ${entries.map(entry => this.#renderContextLine(entry, "context-profile-link")).join("")}
                </nav>
            `;
        }
        if (kind === "workspace" || kind === "system" || kind === "notice") {
            return entries.map(entry => this.#renderFactRow(entry)).join("");
        }
        return entries.map(entry => this.#renderContextLine(entry, "context-link-line")).join("");
    }

    /**
     * Return log entries in reverse chronological order without mutating the
     * domain-oriented sequence received from the CLI facade.
     *
     * Entries with equal or missing timestamps retain their original order.
     *
     * @param {object[]} entries Normalized log entries.
     * @returns {object[]} Newest entries first.
     */
    #sortLogsNewestFirst(entries: ContextEntry[]): ContextEntry[] {
        return entries
            .map((entry, index) => ({
                entry,
                index,
                timestamp: this.#logTimestamp(entry)
            }))
            .sort((left, right) => {
                if (left.timestamp === right.timestamp) {
                    return left.index - right.index;
                }
                return right.timestamp - left.timestamp;
            })
            .map(({ entry }) => entry);
    }

    /**
     * Parse the CLI display date and time into a sortable UTC value.
     *
     * @param {object} entry Normalized log entry.
     * @returns {number} UTC timestamp or negative infinity when unavailable.
     */
    #logTimestamp(entry: ContextEntry): number {
        const dateMatch = String(entry.date || "").match(/^(\d{2})-(\d{2})-(\d{4})$/);
        const timeMatch = String(entry.time || "00:00").match(/^(\d{2}):(\d{2})(?::(\d{2}))?$/);
        if (!dateMatch || !timeMatch) {
            return Number.NEGATIVE_INFINITY;
        }
        const [, day, month, year] = dateMatch;
        const [, hour, minute, second = "0"] = timeMatch;
        return Date.UTC(
            Number(year),
            Number(month) - 1,
            Number(day),
            Number(hour),
            Number(minute),
            Number(second)
        );
    }

    /**
     * Render one navigable document line.
     *
     * @param {object} entry Normalized entry.
     * @param {string} className Row class.
     * @returns {string} HTML.
     */
    #renderContextLine(entry: ContextEntry, className: string): string {
        const routeAttributes = entry.route
            ? `data-context-route="${escapeHtml(entry.route)}" data-context-target="${escapeHtml(this.#encodeTarget(entry.target || {}))}"`
            : "";
        const tag = entry.route ? "button" : "article";
        return `
            <${tag} class="${className} context-kind-${escapeHtml(entry.kind)}" ${routeAttributes}>
                <span class="metric-icon">${icon(entry.icon)}</span>
                <strong>${escapeHtml(entry.label)}</strong>
            </${tag}>
        `;
    }

    /**
     * Render a non-list fact row.
     *
     * @param {object} entry Normalized entry.
     * @returns {string} HTML.
     */
    #renderFactRow(entry: ContextEntry): string {
        return `
            <button class="context-fact-row" data-context-route="${escapeHtml(entry.route || "settings")}" data-context-target="${escapeHtml(this.#encodeTarget(entry.target || {}))}">
                <span class="metric-icon">${icon(entry.icon)}</span>
                <strong>${escapeHtml(entry.label)}</strong>
                <span>${escapeHtml(entry.summary)}</span>
                <span class="context-entry-open">${icon("chevronRight")}</span>
            </button>
        `;
    }


    /**
     * Convert one section without children into a dashboard card.
     *
     * @param {object} section Context section.
     * @returns {object|null} Normalized card or null.
     */
    #sectionEntry(section: ContextSection): ContextEntry | null {
        if (section.kind === "workspace") {
            return {
                kind: "workspace",
                icon: "home",
                typeLabel: "Workspace",
                label: "Workspace root",
                summary: section.path || section.summary || "",
                route: "settings",
                target: { panel: "workspace" }
            };
        }
        if (section.kind === "system") {
            return {
                kind: "system",
                icon: "pulse",
                typeLabel: "System",
                label: section.status === "ok" ? "Checks passed" : "Checks with errors",
                summary: section.summary || "",
                route: "settings",
                target: { panel: "health" }
            };
        }
        if (section.kind === "notice") {
            return {
                kind: "notice",
                icon: "settings",
                typeLabel: "Aviso",
                label: section.title || "Aviso",
                summary: section.summary || section.body || "",
                route: "settings",
                target: { panel: "notice" }
            };
        }
        return null;
    }

    /**
     * Convert one section item into a dashboard card.
     *
     * @param {object} section Context section.
     * @param {object} item Section item.
     * @returns {object} Normalized card.
     */
    #itemEntry(section: ContextSection, item: ContextItem): ContextEntry {
        const iconName = ({
            profiles: "users",
            diary: "document",
            logs: "document",
            backlog: "checkSquare"
        } satisfies Record<string, IconName>)[section.kind ?? ""] || "document";
        return {
            kind: section.kind || "item",
            icon: iconName,
            typeLabel: this.#typeLabel(section, item),
            label: this.#itemLabel(section, item),
            summary: this.#itemSummary(section, item),
            title: item.label || item.id || section.title || "Contexto",
            ...((item.route || section.route) ? { route: item.route || section.route } : {}),
            target: item.target || {},
            domain: item.domain || item.target?.domain || "",
            date: item.date || item.target?.date || "",
            time: item.time || item.target?.time || "",
            changeType: item.changeType || item.type || ""
        };
    }

    /**
     * Return a human-readable title for one context entry.
     *
     * Log domains describe where an entry belongs. The entry identity is its
     * timestamp followed by its own title, which avoids repeating a terminal
     * domain segment as though it were the log title.
     *
     * @param {object} section Context section.
     * @param {object} item Section item.
     * @returns {string} Entry label.
     */
    #itemLabel(section: ContextSection, item: ContextItem): string {
        const fallback = item.label || item.id || section.title || "Contexto";
        if (section.kind !== "logs") {
            return fallback;
        }
        const timestamp = [item.date, item.time].filter(Boolean).join(" ");
        return timestamp ? `${timestamp} -> ${fallback}` : fallback;
    }

    /**
     * Return the Spanish card type label.
     *
     * @param {object} section Context section.
     * @param {object} item Section item.
     * @returns {string} Type label.
     */
    #typeLabel(section: ContextSection, item: ContextItem): string {
        if (section.kind === "profiles") {
            return "Perfil";
        }
        if (section.kind === "diary") {
            return `Diario ${item.date || ""}`.trim();
        }
        if (section.kind === "logs") {
            return "Log entry";
        }
        return section.title || "Contexto";
    }

    /**
     * Build a compact context summary.
     *
     * @param {object} section Context section.
     * @param {object} item Section item.
     * @returns {string} Summary.
     */
    #itemSummary(section: ContextSection, item: ContextItem): string {
        if (section.kind === "profiles") {
            return item.command || `read-profile ${item.label || ""}`;
        }
        if (section.kind === "diary") {
            return item.target?.path || item.command || "Diary entry";
        }
        if (section.kind === "logs") {
            return `${item.domain || "logs"} - ${item.changeType || "registro"}`;
        }
        return item.command || section.summary || "";
    }

    /**
     * Resolve the section icon.
     *
     * @param {object} section Context section.
     * @returns {string} Icon key.
     */
    #sectionIcon(section: ContextSection): IconName {
        return ({
            workspace: "home",
            profiles: "users",
            diary: "document",
            logs: "document",
            system: "pulse",
            notice: "settings"
        } satisfies Record<string, IconName>)[section.kind ?? ""] || "document";
    }

    /**
     * Resolve a fallback title for one context section.
     *
     * @param {object} section Context section.
     * @returns {string} Section title.
     */
    #sectionTitle(section: ContextSection): string {
        return ({
            workspace: "Workspace",
            profiles: "Profiles",
            diary: "Diario reciente",
            logs: "Logs recientes",
            system: "System",
            notice: "Avisos"
        } satisfies Record<string, string>)[section.kind ?? ""] || "Contexto";
    }

    /**
     * Resolve a fallback section summary.
     *
     * @param {object} section Context section.
     * @param {number} count Entry count.
     * @returns {string} Section summary.
     */
    #sectionSummary(section: ContextSection, count: number): string {
        if (section.kind === "workspace") {
            return section.path || "Workspace root";
        }
        return `${count} linked entries`;
    }

    /**
     * Encode a target object for an HTML attribute.
     *
     * @param {object} target Card target.
     * @returns {string} Encoded target.
     */
    #encodeTarget(target: ContextTarget): string {
        return encodeURIComponent(JSON.stringify(target));
    }

    /**
     * Decode a target object from an HTML attribute.
     *
     * @param {string} value Encoded target.
     * @returns {object} Decoded target.
     */
    #decodeTarget(value: string): ContextTarget {
        try {
            return JSON.parse(decodeURIComponent(value));
        } catch {
            return {};
        }
    }

    /**
     * Render loading state.
     *
     * @returns {string} HTML.
     */
    #loadingState() {
        return `
            <div class="loading-state">
                <span></span>
                <strong>Hidratando contexto</strong>
            </div>
        `;
    }
}

customElements.define(DashboardView.selector, DashboardView);
