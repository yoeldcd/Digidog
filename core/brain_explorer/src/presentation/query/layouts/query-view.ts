/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml, renderMarkdown } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { BrainApiClient } from "../../../infrastructure/shared/http/clients/brain-api-client.ts";
import type { AppState } from "../../shell/state/app-state.ts";
import type { ComponentContext } from "../../shared/view_models/component-context-view-model.ts";
import type { QueryEvidence } from "../../../application/query/dtos/responses/query-response.ts";
import type { QueryGroup, QueryResult } from "../view_models/query-view-model.ts";

const DEFAULT_SOURCES = ["memory", "knowledge", "messages", "pictures"];
const DEFAULT_MECHANISMS = ["graph", "vector", "text"];

/**
 * Render global search answers and grouped, traceable source results.
 */
export class QueryView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the QueryView component in the DOM.
     * @returns {string} The string identifier 'brain-query-view'.
     */
    static get selector() {
        return "brain-query-view";
    }

    /**
     * Holds a reference to the BrainApiClient instance used for making API requests within the QueryView component.
     *
     * @type {BrainApiClient | null}
     */
    #api: BrainApiClient | null = null;
    /**
     * Holds the current application state for the query view or remains null if the state is not yet initialized.
     *
     * @type {AppState | null}
     */
    #state: AppState | null = null;
    /**
     * Initializes a private collection of data sources by cloning the default source configuration.
     *
     * @type {string[]}
     */
    #sources = [...DEFAULT_SOURCES];
    /**
     * Initializes a private collection of query mechanisms by cloning the default mechanism set.
     *
     * @type {string[]}
     */
    #mechanisms = [...DEFAULT_MECHANISMS];
    /**
     * Defines the default visibility or filtering scope for the query view, initialized to all records.
     *
     * @type {string}
     */
    #scope = "all";
    /**
     * Stores the domain identifier associated with the current query view.
     *
     * @type {string}
     */
    #domain = "";
    /**
     * Stores the current search query string used for filtering or retrieving data within the view.
     *
     * @type {string}
     */
    #query = "";
    /**
     * Stores the outcome of a query execution or remains null if no result has been retrieved.
     *
     * @type {QueryResult | null}
     */
    #result: QueryResult | null = null;

    /**
     * Initializes the view's API, state, and query configuration from the provided component context and triggers an immediate render or query execution if a pending query exists.
     * @param {ComponentContext} context The component context containing the API and state required to configure the view's data sources and mechanisms.
     */
    set context(context: ComponentContext) {
        this.#api = context.api;
        this.#state = context.state;
        const pendingQuery = this.#state?.consumePendingQuery?.() || "";
        const options = this.#state?.consumePendingQueryOptions?.() || {};
        this.#sources = options.sources?.length ? options.sources : [...DEFAULT_SOURCES];
        this.#mechanisms = options.mechanisms?.length ? options.mechanisms : [...DEFAULT_MECHANISMS];
        if (pendingQuery) {
            this.#query = pendingQuery;
            this.#render();
            queueMicrotask(() => this.#runQuery());
            return;
        }
        this.#render();
    }

    /**
     * Triggers the initial rendering of the component when it is attached to the document DOM.
     */
    connectedCallback() {
        this.#render();
    }

    /**
     * Executes a global API query based on current view state, filters the resulting evidence by selected sources and mechanisms, and updates the internal result state to trigger a re-render.
     */
    async #runQuery() {
        const query = this.#query.trim();
        const api = this.#api;
        if (!query || !api) return;
        this.#query = query;
        this.#result = { loading: true };
        this.#render();
        const source = this.#sources.length === 1 ? this.#sources[0] ?? "all" : "all";
        const mechanism = this.#mechanisms.length === 1 ? this.#mechanisms[0] ?? "all" : "all";
        const response = await api.globalQuery({
            q: query,
            domain: this.#domain,
            source,
            mechanism,
            knowledgeScope: this.#scope,
            limit: "10",
            explain: "true",
            deep: "false"
        });
        const responseData = !Array.isArray(response.data) ? response.data ?? {} : {};
        const rawResults: QueryEvidence[] = Array.isArray(response.data)
            ? response.data
            : responseData.results || responseData.matches || [];
        const results = rawResults.filter(item =>
            item.source !== undefined && item.mechanism !== undefined
            && this.#sources.includes(item.source) && this.#mechanisms.includes(item.mechanism));
        this.#result = {
            ok: response.ok,
            data: { response: responseData.response || "", results: this.#deduplicate(results) },
            stderr: response.stderr || response.error || ""
        };
        this.#state?.setLastResult(response);
        this.#render();
    }

    /**
     * Filters a list of query evidence to remove duplicate entries based on a composite key of source, mechanism, path, title, text, and excerpt.
     * @param {QueryEvidence[]} results The collection of query evidence items to be deduplicated.
     * @returns {QueryEvidence[]} An array containing only the first occurrence of each unique evidence item.
     */
    #deduplicate(results: QueryEvidence[]): QueryEvidence[] {
        const unique = new Map<string, QueryEvidence>();
        results.forEach(result => {
            const key = [result.source, result.mechanism, result.path, result.title, result.text, result.excerpt].join("|");
            if (!unique.has(key)) unique.set(key, result);
        });
        return [...unique.values()];
    }

    /**
     * Updates the component's inner HTML with the search results layout and attaches click event listeners to picture-opening buttons to update the state route target.
     */
    #render(): void {
        this.innerHTML = `
            <section class="page-surface search-console">
                <main class="search-results-column scroll-area">${this.#renderResult()}</main>
            </section>
        `;
        this.querySelectorAll("[data-open-picture]").forEach(button => {
            button.addEventListener("click", () => {
                this.#state?.setRouteTarget("pictures", { pictureId: button.getAttribute("data-open-picture") || "" });
            });
        });
    }

    /**
     * Generates an HTML string representing the query result state, handling loading, empty, and data-populated views.
     * @returns {string} An HTML string containing the rendered result interface or a status placeholder.
     */
    #renderResult(): string {
        if (this.#result?.loading) {
            return `<div class="loading-state search-loading"><span></span><strong>Searching memory, knowledge, and messages</strong><small>Preparing results...</small></div>`;
        }
        if (!this.#result) {
            return `<section class="search-empty">${icon("search")}<h2>Results</h2><p>Enter a query in the header search box to begin.</p></section>`;
        }
        const text = this.#result.data?.response || this.#firstResultText() || this.#result.stderr || "No readable output.";
        return `
            <article class="answer-sheet">
                <header><span class="${this.#result.ok ? "status-pill success" : "status-pill danger"}">${this.#result.ok ? "Response" : "Error"}</span></header>
                <h2>${escapeHtml(this.#query || "Consulta")}</h2>
                <div>${renderMarkdown(String(text).slice(0, 2200))}</div>
            </article>
            ${this.#renderResultGroups()}
        `;
    }

    /**
     * Retrieves the most representative text string from the first available search result.
     * @returns {string} The text, excerpt, or title of the first result, or an empty string if no result or valid text field exists.
     */
    #firstResultText(): string {
        const first = this.#results()[0];
        return first?.text || first?.excerpt || first?.title || "";
    }

    /**
     * Retrieves a normalized list of query evidence by extracting results or matches from the internal result state.
     * @returns {QueryEvidence[]} An array of QueryEvidence objects derived from the current result data, or an empty array if no valid results are found.
     */
    #results(): QueryEvidence[] {
        const results = this.#result?.data?.results || this.#result?.data?.matches || [];
        return Array.isArray(results) ? results : [];
    }

    /**
     * Groups query results by source and mechanism to generate an HTML representation of the search evidence section.
     * @returns {string} An HTML string containing the grouped results and their metadata, or an empty string if no results exist.
     */
    #renderResultGroups(): string {
        const groups = new Map<string, QueryGroup>();
        this.#results().forEach(item => {
            const source = item.source || "unknown";
            const mechanism = item.mechanism || "unknown";
            const key = `${source}:${mechanism}`;
            if (!groups.has(key)) groups.set(key, { source, mechanism, items: [] });
            groups.get(key)?.items.push(item);
        });
        if (!groups.size) return "";
        return `
            <section class="search-evidence" aria-label="Response sources">
                <header><h3>Sources consulted</h3><span>${this.#results().length} results</span></header>
                ${[...groups.values()].map(group => `
                    <section class="result-group">
                        <header><h4>${escapeHtml(this.#sourceLabel(group.source))}</h4><span>${escapeHtml(this.#mechanismLabel(group.mechanism))}</span></header>
                        <ol>
                            ${group.items.map(item => `
                                <li>
                                    <span class="result-order" aria-hidden="true"></span>
                                    <div class="result-copy">
                                        <strong>${escapeHtml(item.title || item.path || item.kind || "Result")}</strong>
                                        <p>${escapeHtml(item.excerpt || item.content?.excerpt || item.data?.excerpt || item.text || item.description || "No excerpt available")}</p>
                                        <small>${escapeHtml(this.#resultOrigin(item))}</small>
                                    </div>
                                    ${item.rank !== undefined ? `<span class="result-rank" title="Relevancia">${Number(item.rank).toFixed(2)}</span>` : ""}
                                    ${item.source === "pictures" && item.data?.id ? `<button class="result-open-button" data-open-picture="${escapeHtml(item.data.id)}">Open</button>` : ""}
                                </li>
                            `).join("")}
                        </ol>
                    </section>
                `).join("")}
            </section>
        `;
    }

    /**
     * Resolves a human-readable origin string from a QueryEvidence object by checking multiple fallback path and identity properties.
     * @param {QueryEvidence} item The evidence object containing potential source references, paths, or domain identifiers.
     * @returns {string} The first available path or identifier found in the evidence hierarchy, or a default fallback string if none exist.
     */
    #resultOrigin(item: QueryEvidence): string {
        return item.sourceRef?.path || item.source_ref?.path || item.path || item.domain || item.kind || "Origen no especificado";
    }

    /**
     * Maps a technical source identifier to its corresponding human-readable display label.
     * @param {string} source The technical identifier of the data source to be labeled.
     * @returns {string} The localized string representation of the source, defaulting to 'Other results' for unrecognized inputs.
     */
    #sourceLabel(source: string): string {
        if (source === "memory") return "Memory";
        if (source === "knowledge") return "Knowledge";
        if (source === "messages") return "Messages";
        if (source === "pictures") return "Pictures";
        return "Other results";
    }

    /**
     * Maps a mechanism identifier to its corresponding localized display label.
     * @param {string} mechanism The technical identifier of the mechanism to be translated.
     * @returns {string} The localized string representation of the mechanism, or the original identifier if no mapping exists.
     */
    #mechanismLabel(mechanism: string): string {
        return mechanism === "graph" ? "Grafo" : mechanism === "vector" ? "Vectorial" : mechanism === "text" ? "Texto" : mechanism;
    }
}

customElements.define(QueryView.selector, QueryView);
