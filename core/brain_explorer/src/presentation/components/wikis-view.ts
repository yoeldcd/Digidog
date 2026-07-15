import { escapeHtml } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";
import { BrainApiClient } from "../../infrastructure/api/brain-api-client.ts";

/**
 * WikisView renders detected subproject documentation wikis and opens them
 * inside an embedded iframe. No generation step — serves markdown live.
 */
export class WikisView extends HTMLElement {
    static get selector() {
        return "brain-wikis-view";
    }

    #api = null;
    #state = null;
    #wikis = [];
    #loading = false;
    #wikiLoading = false;
    #activeWikiName = null;

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#loadWikis();
    }

    /**
     * Initialize DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
    }

    /**
     * Load server wikis list.
     *
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadWikis() {
        if (!this.#api) return;
        this.#loading = true;
        this.#render();
        try {
            const api = this.#api as unknown as BrainApiClient;
            const res = await api.getWikis();
            this.#wikis = res?.wikis || [];
            this.#state?.setLastResult(res);
        } catch (err) {
            console.error("Error fetching wikis:", err);
        } finally {
            this.#loading = false;
            this.#render();
        }
    }

    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        if (this.#activeWikiName) {
            this.#renderIframeView();
            return;
        }

        this.innerHTML = `
            <section class="page-surface settings-console wiki-console ${this.#loading ? "is-loading" : (this.#wikis.length ? "has-items" : "is-empty")}">
                <header class="view-header" style="display: flex; justify-content: space-between; align-items: center; padding-bottom: var(--spacing-md); border-bottom: 1px solid var(--border); margin-bottom: var(--spacing-lg);">
                    <div>
                        <h2 style="margin: 0; font-size: var(--font-size-xl); color: var(--text-strong);">Wikis de Subproyectos</h2>
                        <small style="color: var(--text-muted);">Documentación interactiva disponible en el path activo</small>
                    </div>
                    <button data-action="refresh-wikis" class="primary-action compact-action" title="Buscar wikis">${icon("refresh")}</button>
                </header>
                
                ${this.#loading ? `
                    <div class="loading-state" style="padding: 40px; text-align: center;">
                        <span></span>
                        <strong>Buscando wikis...</strong>
                    </div>
                ` : this.#renderWikisGrid()}
            </section>
        `;

        this.querySelector("[data-action='refresh-wikis']")?.addEventListener("click", () => this.#loadWikis());
        
        this.querySelectorAll("[data-action='view-wiki']").forEach(btn => {
            btn.addEventListener("click", () => {
                this.#activeWikiName = btn.getAttribute("data-name");
                this.#wikiLoading = true;
                this.#render();
            });
            btn.addEventListener("keydown", event => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    btn.click();
                }
            });
        });
    }

    /**
     * Render wikis as compact horizontal list items.
     *
     * @returns {string} HTML.
     */
    #renderWikisGrid() {
        if (!this.#wikis.length) {
            return `
                <div class="knowledge-empty-state wiki-empty-state">
                    ${icon("document")}
                    <h3>No se encontraron carpetas de documentación</h3>
                    <p>Crea una carpeta <code>documentation</code> en algún subproyecto para habilitar wikis locales.</p>
                </div>
            `;
        }

        return `
            <main class="wiki-list">
                ${this.#wikis.map(wiki => `
                    <article class="wiki-list-item ${wiki.hasWiki ? "is-clickable" : ""}"
                        ${wiki.hasWiki ? `data-action="view-wiki" data-name="${escapeHtml(wiki.name)}" tabindex="0" role="button" aria-label="Abrir wiki ${escapeHtml(wiki.name)}"` : ""}>
                        <div class="wiki-list-content">
                            <div class="wiki-list-heading">
                                <strong>${escapeHtml(wiki.name)}</strong>
                                <span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 600; background: ${wiki.hasWiki ? "rgba(16, 185, 129, 0.15); color: #10b981;" : "rgba(156, 163, 175, 0.15); color: #9ca3af;"};">
                                    ${wiki.hasWiki ? "Disponible" : "Sin compilar"}
                                </span>
                            </div>
                            <span class="wiki-list-path">
                                ${escapeHtml(wiki.path)}
                            </span>
                        </div>
                        <div class="wiki-list-action">
                            ${wiki.hasWiki ? `
                                <button class="primary-action compact-action" tabindex="-1">
                                    ${icon("book")} Ver Wiki
                                </button>
                            ` : `
                                <span style="font-size: var(--font-size-sm); color: var(--text-muted); padding: 6px 0;">Ejecuta <code>generate</code> para habilitar</span>
                            `}
                        </div>
                    </article>
                `).join("")}
            </main>
        `;
    }

    /**
     * Render the active wiki iframe full view.
     *
     * @returns {void}
     */
    #renderIframeView() {
        this.innerHTML = `
            <div class="wiki-frame-view">
                <header class="wiki-frame-toolbar">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <button data-action="close-wiki" class="secondary-action compact-action" style="min-height: 32px; display: flex; align-items: center; gap: 4px;">
                            ${icon("chevronRight")} Atrás
                        </button>
                        <h2 style="margin: 0; font-size: var(--font-size-lg); color: var(--text-strong);">Wiki ~ ${escapeHtml(this.#activeWikiName)}</h2>
                    </div>
                </header>
                <div class="wiki-frame-container">
                    <div class="wiki-frame-loading" ${this.#wikiLoading ? "" : "hidden"} role="status">
                        <span class="loading-spinner" aria-hidden="true"></span>
                        <strong>Resolviendo wiki...</strong>
                    </div>
                    <iframe src="/wiki/${this.#activeWikiName}/wiki/index.html" scrolling="yes" style="width: 100%; height: 100%; border: none;" title="Wiki Frame"></iframe>
                </div>
            </div>
        `;

        this.querySelector("[data-action='close-wiki']")?.addEventListener("click", () => {
            this.#activeWikiName = null;
            this.#render();
        });
        this.querySelector("iframe")?.addEventListener("load", event => {
            this.#wikiLoading = false;
            this.querySelector(".wiki-frame-loading")?.setAttribute("hidden", "");
            this.#hideIframeScrollbar(event.currentTarget);
        });
    }

    /**
     * Hide the same-origin wiki scrollbar while preserving wheel, keyboard,
     * and touch scrolling inside the embedded document.
     *
     * @param {HTMLIFrameElement} iframe Loaded wiki frame.
     * @returns {void}
     */
    #hideIframeScrollbar(iframe) {
        const documentRoot = iframe.contentDocument;
        if (!documentRoot?.head) {
            return;
        }
        const style = documentRoot.createElement("style");
        style.dataset.brainExplorerScrollbar = "hidden";
        style.textContent = `
            html, body {
                scrollbar-width: none !important;
                -ms-overflow-style: none !important;
            }
            html::-webkit-scrollbar,
            body::-webkit-scrollbar {
                display: none !important;
                width: 0 !important;
                height: 0 !important;
            }
        `;
        documentRoot.head.querySelector("[data-brain-explorer-scrollbar]")?.remove();
        documentRoot.head.append(style);
    }
}

customElements.define(WikisView.selector, WikisView);
