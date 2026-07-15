import { escapeHtml, renderMarkdown } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";

const DEFAULT_SOURCES = ["memory", "knowledge"];
const DEFAULT_MECHANISMS = ["graph", "vector", "text"];

/** Render global search answers and grouped, traceable source results. */
export class QueryView extends HTMLElement {
    static get selector() {
        return "brain-query-view";
    }

    #api = null;
    #state = null;
    #sources = [...DEFAULT_SOURCES];
    #mechanisms = [...DEFAULT_MECHANISMS];
    #scope = "all";
    #domain = "";
    #query = "";
    #result = null;

    set context(context) {
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

    connectedCallback() {
        this.#render();
    }

    async #runQuery() {
        const query = this.#query.trim();
        if (!query) return;
        this.#query = query;
        this.#result = { loading: true };
        this.#render();
        const source = this.#sources.length === 1 ? this.#sources[0] : "all";
        const mechanism = this.#mechanisms.length === 1 ? this.#mechanisms[0] : "all";
        const response = await this.#api.globalQuery({
            q: query,
            domain: this.#domain,
            source,
            mechanism,
            knowledgeScope: this.#scope,
            limit: "10",
            explain: "true",
            deep: "false"
        });
        const rawResults = Array.isArray(response.data)
            ? response.data
            : response.data?.results || response.data?.matches || [];
        const results = rawResults.filter(item => this.#sources.includes(item.source) && this.#mechanisms.includes(item.mechanism));
        this.#result = {
            ok: response.ok,
            data: { response: response.data?.response || "", results: this.#deduplicate(results) },
            stderr: response.stderr || response.error || ""
        };
        this.#state?.setLastResult(this.#result);
        this.#render();
    }

    #deduplicate(results) {
        const unique = new Map();
        results.forEach(result => {
            const key = [result.source, result.mechanism, result.path, result.title, result.text, result.excerpt].join("|");
            if (!unique.has(key)) unique.set(key, result);
        });
        return [...unique.values()];
    }

    #render() {
        this.innerHTML = `
            <section class="page-surface search-console">
                <main class="search-results-column scroll-area">${this.#renderResult()}</main>
            </section>
        `;
    }

    #renderResult() {
        if (this.#result?.loading) {
            return `<div class="loading-state search-loading"><span></span><strong>Buscando en memoria y conocimiento</strong><small>Preparando resultados...</small></div>`;
        }
        if (!this.#result) {
            return `<section class="search-empty">${icon("search")}<h2>Resultados</h2><p>Escribe una consulta en el buscador del encabezado para comenzar.</p></section>`;
        }
        const text = this.#result.data?.response || this.#firstResultText() || this.#result.stderr || "Sin salida legible.";
        return `
            <article class="answer-sheet">
                <header><span class="${this.#result.ok ? "status-pill success" : "status-pill danger"}">${this.#result.ok ? "Respuesta" : "Error"}</span></header>
                <h2>${escapeHtml(this.#query || "Consulta")}</h2>
                <div>${renderMarkdown(String(text).slice(0, 2200))}</div>
            </article>
            ${this.#renderResultGroups()}
        `;
    }

    #firstResultText() {
        const first = this.#results()[0];
        return first?.text || first?.excerpt || first?.title || "";
    }

    #results() {
        const results = this.#result?.data?.results || this.#result?.data?.matches || [];
        return Array.isArray(results) ? results : [];
    }

    #renderResultGroups() {
        const groups = new Map();
        this.#results().forEach(item => {
            const source = item.source || "unknown";
            const mechanism = item.mechanism || "unknown";
            const key = `${source}:${mechanism}`;
            if (!groups.has(key)) groups.set(key, { source, mechanism, items: [] });
            groups.get(key).items.push(item);
        });
        if (!groups.size) return "";
        return `
            <section class="search-evidence" aria-label="Fuentes de la respuesta">
                <header><h3>Fuentes consultadas</h3><span>${this.#results().length} resultados</span></header>
                ${[...groups.values()].map(group => `
                    <section class="result-group">
                        <header><h4>${escapeHtml(this.#sourceLabel(group.source))}</h4><span>${escapeHtml(this.#mechanismLabel(group.mechanism))}</span></header>
                        <ol>
                            ${group.items.map(item => `
                                <li>
                                    <span class="result-order" aria-hidden="true"></span>
                                    <div class="result-copy">
                                        <strong>${escapeHtml(item.title || item.path || item.kind || "Resultado")}</strong>
                                        <p>${escapeHtml(item.excerpt || item.content?.excerpt || item.data?.excerpt || item.text || item.description || "Sin extracto disponible")}</p>
                                        <small>${escapeHtml(this.#resultOrigin(item))}</small>
                                    </div>
                                    ${item.rank !== undefined ? `<span class="result-rank" title="Relevancia">${Number(item.rank).toFixed(2)}</span>` : ""}
                                </li>
                            `).join("")}
                        </ol>
                    </section>
                `).join("")}
            </section>
        `;
    }

    #resultOrigin(item) {
        return item.sourceRef?.path || item.source_ref?.path || item.path || item.domain || item.kind || "Origen no especificado";
    }

    #sourceLabel(source) {
        return source === "memory" ? "Memoria" : source === "knowledge" ? "Conocimiento" : "Otros resultados";
    }

    #mechanismLabel(mechanism) {
        return mechanism === "graph" ? "Grafo" : mechanism === "vector" ? "Vectorial" : mechanism === "text" ? "Texto" : mechanism;
    }
}

customElements.define(QueryView.selector, QueryView);
