/**
 * Query presentation layout for global search answers and traceable evidence.
 *
 * @module presentation/query/layouts/query-view
 */

import type { QueryEvidence, QueryResultData } from "../../../application/query/dtos/responses/query-response.ts";
import type { BrainApiClient } from "../../../infrastructure/shared/http/clients/brain-api-client.ts";
import { escapeHtml } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { ComponentContext, ReactiveContentFilterLayout } from "../../shared/view_models/component-context-view-model.ts";
import type { AppState } from "../../shell/state/app-state.ts";
import { resolveQueryResultRenderer } from "./query-result-renderer-registry.ts";
import { mapQueryResponse, type MappedQueryResponse } from "../view_models/query-result-mapper.ts";
import type { QueryEvidenceViewModel, QueryResult } from "../view_models/query-view-model.ts";


const DEFAULT_SOURCES: readonly string[] = ["memory", "knowledge", "pictures", "logs", "messages", "backlog"];
const DEFAULT_MECHANISMS: readonly string[] = ["graph", "vector", "text"];
const PAGE_SIZES: readonly number[] = [10, 25, 50, 100];


type QueryResponseEnvelope = {
    readonly ok?: boolean;
    readonly data?: unknown;
    readonly stderr?: string;
    readonly error?: string;
};


/** Render query answers, source-specific evidence sections, and pagination. */
export class QueryView extends HTMLElement implements ReactiveContentFilterLayout {

    /** Custom-element selector registered by the shell. */
    static get selector(): string {
        return "brain-query-view";
    }

    #api: BrainApiClient | null = null;
    #state: AppState | null = null;
    #sources: string[] = [...DEFAULT_SOURCES];
    #mechanisms: string[] = [...DEFAULT_MECHANISMS];
    #scope: string = "all";
    #domain: string = "";
    #query: string = "";
    #result: QueryResult | null = null;
    #response: MappedQueryResponse | null = null;
    #page: number = 1;
    #pageSize: number = 25;
    #activeSource: string = "";
    #reactiveQuery: string = "";
    #requestToken: number = 0;
    #globalCounts: Readonly<Record<string, number>> = {};

    /** Attach application dependencies and execute any pending query. */
    set context(context: ComponentContext) {
        this.#api = context.api;
        this.#state = context.state;

        const pendingQuery: string = this.#state.consumePendingQuery?.() || "";
        const options = this.#state.consumePendingQueryOptions?.() || {};

        this.#sources = options.sources?.length
            ? [...options.sources]
            : [...DEFAULT_SOURCES];
        this.#mechanisms = options.mechanisms?.length
            ? [...options.mechanisms]
            : [...DEFAULT_MECHANISMS];
        this.#query = pendingQuery;
        this.#render();

        if (pendingQuery) {
            queueMicrotask(() => void this.#runQuery());
        }
    }

    /** Narrow the exhaustive cached result set from the shell searchbar without refetching. */
    public applyReactiveContentFilter(query: string): void {
        this.#reactiveQuery = query.trim();
        this.#page = 1;
        this.#render();
    }

    /** Render the empty state when connected. */
    connectedCallback(): void {
        this.#render();
    }

    /** Execute one exhaustive server query; filtering and pagination remain local. */
    async #runQuery(): Promise<void> {
        const query: string = this.#query.trim();
        const api: BrainApiClient | null = this.#api;

        if (!query || !api) return;

        const requestToken: number = ++this.#requestToken;
        const indexedSources: string[] = this.#sources.filter((source) => source !== "backlog");
        const source: string = indexedSources.length === 1 ? indexedSources[0] || "all" : "all";
        const mechanism: string = this.#mechanisms.length === 1 ? this.#mechanisms[0] || "all" : "all";

        this.#query = query;
        this.#result = { loading: true };
        this.#render();

        try {
            const rawResponse = await api.globalQuery({
                q: query,
                domain: this.#domain,
                source,
                mechanism,
                knowledgeScope: this.#scope,
                page: "1",
                pageSize: "0",
                explain: "false",
                deep: "false",
            });

            if (requestToken !== this.#requestToken) return;

            const envelope: QueryResponseEnvelope = rawResponse as QueryResponseEnvelope;
            const data: QueryResultData = this.#queryData(envelope.data);
            this.#response = mapQueryResponse(data);
            this.#globalCounts = this.#response.countsBySource;
            const presentSources: readonly string[] = this.#presentSources(this.#response);
            this.#activeSource = presentSources.includes(this.#activeSource) ? this.#activeSource : presentSources[0] || "";
            this.#result = { ok: envelope.ok ?? true, data, stderr: envelope.stderr || envelope.error || "" };
            this.#state?.setLastResult(rawResponse);
        } catch (error: unknown) {
            if (requestToken === this.#requestToken) {
                const message: string = error instanceof Error ? error.message : "Query failed.";
                this.#response = null;
                this.#result = { ok: false, stderr: message };
            }
        } finally {
            if (requestToken === this.#requestToken) this.#render();
        }
    }

    /** Normalize the object or array response payload for the mapper. */
    #queryData(data: unknown): QueryResultData {
        if (Array.isArray(data)) {
            return { items: data as QueryEvidence[] };
        }

        if (!data || typeof data !== "object") {
            return {};
        }

        return data as QueryResultData;
    }

    /** Compose markup and attach local interaction handlers. */
    #render(): void {
        this.innerHTML = `<section class="page-surface search-console">
            <main class="search-results-column scroll-area">${this.#renderResult()}</main>
        </section>`;

        this.#highlightQueryMatches();

        this.querySelectorAll<HTMLButtonElement>("[data-source-tab]").forEach((tab) => {
            tab.addEventListener("click", () => {
                this.#activeSource = tab.dataset.sourceTab || "";
                this.#page = 1;
                this.#render();
            });
        });

        this.querySelector<HTMLSelectElement>("[data-page-size]")?.addEventListener("change", (event) => {
            const selector: HTMLSelectElement = event.target as HTMLSelectElement;

            this.#pageSize = Number(selector.value);
            this.#page = 1;
            this.#render();
        });

        this.querySelectorAll<HTMLButtonElement>("[data-route]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.stopPropagation();
                const route = button.dataset.route;

                if (route) {
                    const serializedTarget: string = button.dataset.routeTarget || "{}";
                    const target = JSON.parse(serializedTarget) as Readonly<Record<string, unknown>>;

                    this.#state?.setRouteTarget(route as Parameters<AppState["setRouteTarget"]>[0], target);
                }
            });
        });

        this.querySelectorAll<HTMLElement>(".query-result-card[role=\"link\"]").forEach((card) => {
            card.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    card.click();
                }
            });
        });

        this.querySelectorAll<HTMLButtonElement>("[data-page-action]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.stopPropagation();
                const action: string = button.dataset.pageAction || "";

                this.#page += action === "previous" ? -1 : 1;
                this.#render();
            });
        });

    }

    /** Highlight literal query phrases and meaningful terms in rendered result text nodes. */
    #highlightQueryMatches(): void {
        const query: string = (this.#reactiveQuery || this.#query).trim();
        if (!query) return;

        const candidates: string[] = [query, ...query.split(/\s+/u).filter((term) => term.length > 2)];
        const terms: string[] = [...new Set(candidates.map((term) => term.trim()).filter(Boolean))]
            .sort((left, right) => right.length - left.length);
        if (!terms.length) return;

        const escapedTerms: string[] = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
        const pattern: RegExp = new RegExp(escapedTerms.join("|"), "giu");
        const textNodes: Text[] = [];
        this.querySelectorAll<HTMLElement>(".query-result-card").forEach((card) => {
            const walker: TreeWalker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
            let currentNode: Node | null = walker.nextNode();
            while (currentNode) {
                const parentElement: HTMLElement | null = currentNode.parentElement;
                if (parentElement && !parentElement.closest("script, style, mark")) textNodes.push(currentNode as Text);
                currentNode = walker.nextNode();
            }
        });

        textNodes.forEach((textNode) => {
            const value: string = textNode.nodeValue || "";
            pattern.lastIndex = 0;
            if (!pattern.test(value)) return;
            pattern.lastIndex = 0;
            const fragment: DocumentFragment = document.createDocumentFragment();
            let offset: number = 0;
            value.replace(pattern, (match: string, ...args: unknown[]) => {
                const index: number = Number(args[args.length - 2]);
                fragment.append(value.slice(offset, index));
                const mark: HTMLElement = document.createElement("mark");
                mark.className = "query-match-highlight";
                mark.textContent = match;
                fragment.append(mark);
                offset = index + match.length;
                return match;
            });
            fragment.append(value.slice(offset));
            textNode.replaceWith(fragment);
        });
    }

    /** Render loading, empty, or completed query state. */
    #renderResult(): string {
        if (this.#result?.loading) return `<div class="loading-state search-loading"><strong>Searching all indexed sources</strong></div>`;
        if (!this.#result) return `<section class="search-empty"><h2>Results</h2><p>Enter a query in the header search box to begin.</p></section>`;

        const response: MappedQueryResponse | null = this.#response;
        if (!response) return `<p class="query-error">${escapeHtml(this.#result.stderr || "Query failed.")}</p>`;

        const visibleResponse: MappedQueryResponse = this.#localResponse(response);
        const sources: readonly string[] = this.#presentSources(response);
        const tabs: string = sources.map((source) => this.#renderSourceTab(source, response)).join("");
        const visibleSources: readonly string[] = this.#activeSource ? [this.#activeSource] : [];
        const content: string = visibleResponse.items.length
            ? visibleSources.map((source) => this.#renderSourceSection(source, visibleResponse.items)).join("")
            : this.#renderEmptyResults();
        const sourceCount: number = sources.length;

        return `<article class="query-results" aria-live="polite">
            <header class="query-results-header">
                <div class="query-header-primary"><div class="query-title-lockup"><span class="query-title-icon">${icon("search")}</span><div><h1>${escapeHtml(this.#query)}</h1><p class="query-summary">${response.totalItems.toLocaleString()} matches across ${sourceCount} sources</p></div></div></div>
                <div class="query-header-controls">
                    <nav class="query-source-tabs" role="tablist" aria-label="Filter results by source">${tabs}</nav>
                    <div class="query-results-toolbar-region">${this.#renderResultsToolbar(visibleResponse)}</div>
                </div>
            </header>
            <section id="query-results-panel" class="query-results-panel" role="tabpanel" aria-labelledby="query-tab-${escapeHtml(this.#activeSource)}" aria-live="polite">${content}</section>
        </article>`;
    }

    /** Project the exhaustive response into the active source and local page. */
    #localResponse(response: MappedQueryResponse): MappedQueryResponse {
        const sourceItems: readonly QueryEvidenceViewModel[] = response.items.filter((item) => item.source === this.#activeSource);
        const needle: string = this.#reactiveQuery.toLocaleLowerCase();
        const filtered: readonly QueryEvidenceViewModel[] = needle
            ? sourceItems.filter((item) => `${item.title} ${item.markdown} ${item.origin.domain} ${item.navigation.path} ${item.resourceId}`.toLocaleLowerCase().includes(needle))
            : sourceItems;
        const totalItems: number = filtered.length;
        const totalPages: number = Math.max(1, Math.ceil(totalItems / this.#pageSize));
        const page: number = Math.min(Math.max(1, this.#page), totalPages);
        const start: number = (page - 1) * this.#pageSize;

        this.#page = page;
        return { ...response, items: filtered.slice(start, start + this.#pageSize), page, pageSize: this.#pageSize, totalItems, totalPages, hasPrevious: page > 1, hasNext: page < totalPages };
    }

    /** Return sources represented by global counts or current-page evidence. */
    #presentSources(response: MappedQueryResponse): readonly string[] {
        const counts: Readonly<Record<string, number>> = Object.keys(this.#globalCounts).length
            ? this.#globalCounts
            : response.countsBySource;
        const countedSources: string[] = Object.entries(counts)
            .filter(([, count]) => count > 0)
            .map(([source]) => source);
        const itemSources: string[] = response.items.map((item) => item.source);

        return [...new Set([...countedSources, ...itemSources])];
    }

    /** Render one source-filter tab with its stable global count. */
    #renderSourceTab(source: string, response: MappedQueryResponse): string {
        const active: boolean = this.#activeSource === source;
        const counts: Readonly<Record<string, number>> = Object.keys(this.#globalCounts).length
            ? this.#globalCounts
            : response.countsBySource;
        const count: number = counts[source] || 0;
        const label: string = source.charAt(0).toUpperCase() + source.slice(1);

        return `<button
            type="button"
            class="query-source-tab is-source-${escapeHtml(source)}${active ? " active" : ""}"
            data-source-tab="${escapeHtml(source)}"
            role="tab"
            id="query-tab-${escapeHtml(source)}"
            aria-controls="query-results-panel"
            aria-selected="${active}"
            tabindex="${active ? "0" : "-1"}"
        >${icon(source === "memory" ? "book" : source === "knowledge" ? "graph" : source === "pictures" ? "camera" : source === "logs" ? "document" : source === "messages" ? "messageCircle" : "clock")}<span>${escapeHtml(label)}</span> <span>${count}</span></button>`;
    }

    /** Registry renderers own query-result-row, query-result-main, and query-result-meta markup. */
    #renderSourceSection(source: string, items: readonly QueryEvidenceViewModel[]): string {
        const sourceItems: readonly QueryEvidenceViewModel[] = items.filter((item) => item.source === source);
        const renderedItems: string = sourceItems
            .map((item) => resolveQueryResultRenderer(item.source)(item))
            .join("");
        const label: string = source.charAt(0).toUpperCase() + source.slice(1);

        return `<section class="query-source-section is-source-${escapeHtml(source)}">
            <header>
                <h3>${escapeHtml(label)}</h3>
                <span class="query-count-badge">${sourceItems.length} on this page</span>
            </header>
            <ol class="query-source-list is-source-${escapeHtml(source)}">${renderedItems}</ol>
        </section>`;
    }

    /** Render compact local pagination controls for the active result projection. */
    #renderResultsToolbar(response: MappedQueryResponse): string {
        if (!response.items.length || response.totalItems === 0) return `<nav class="query-pagination" aria-label="Query result pages"><span class="query-page-status">0/0</span></nav>`;

        const options: string = PAGE_SIZES.map((size) => `<option value="${size}"${size === this.#pageSize ? " selected" : ""}>${size}</option>`).join("");

        return `<nav class="query-pagination" aria-label="Query result pages">
            <select class="query-page-size" data-page-size aria-label="Results per page">${options}</select>
            <button class="query-page-action" data-page-action="previous" ${response.hasPrevious ? "" : "disabled"} aria-label="Previous page" title="Previous page">${icon("chevronLeft")}</button>
            <span class="query-page-status">${response.page}/${response.totalPages}</span>
            <button class="query-page-action" data-page-action="next" ${response.hasNext ? "" : "disabled"} aria-label="Next page" title="Next page">${icon("chevronRight")}</button>
        </nav>`;
    }

    /** Render an actionable empty state for the current source selection. */
    #renderEmptyResults(): string {
        return `<section class="query-empty-state">
            <h2>No ${escapeHtml(this.#activeSource || "source")} results found</h2>
            <p>${this.#reactiveQuery ? "Clear or change the reactive filter." : "Try a different query."}</p>
        </section>`;
    }


}

customElements.define(QueryView.selector, QueryView);
