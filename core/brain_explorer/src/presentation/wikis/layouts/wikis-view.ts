/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import { BrainApiClient } from "../../../infrastructure/shared/http/clients/brain-api-client.ts";
import type { WikiRecord } from "../../../application/wikis/dtos/responses/wikis-response.ts";
import type { AppState } from "../../shell/state/app-state.ts";
import type { ComponentContext } from "../../shared/view_models/component-context-view-model.ts";

/**
 * WikisView renders detected subproject documentation wikis and opens them
 * inside an embedded iframe. No generation step — serves markdown live.
 */
export class WikisView extends HTMLElement {
    /**
     * Provides the unique CSS selector used to identify the WikisView component in the DOM.
     * @returns {string} A string representing the component's custom element tag name.
     */
    static get selector() {
        return "brain-wikis-view";
    }

    /**
     * Holds a reference to the BrainApiClient instance used for making API requests within the WikisView component.
     *
     * @type {BrainApiClient | null}
     */
    #api: BrainApiClient | null = null;
    /**
     * Holds the current application state or null if the state has not been initialized.
     *
     * @type {AppState | null}
     */
    #state: AppState | null = null;
    /**
     * Maintains a private collection of wiki records used for rendering the wikis view.
     *
     * @type {WikiRecord[]}
     */
    #wikis: WikiRecord[] = [];
    /** Active workspace root associated with the loaded wiki registry. */
    #workspaceRoot = "";
    /**
     * Tracks the asynchronous loading state of the WikisView component.
     *
     * @type {boolean}
     */
    #loading = false;
    /**
     * Indicates whether the wiki content is currently being loaded.
     *
     * @type {boolean}
     */
    #wikiLoading = false;
    /**
     * Stores the name of the currently selected wiki or null if no wiki is active.
     *
     * @type {string | null}
     */
    #activeWikiName: string | null = null;

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context: ComponentContext) {
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
            const res = await this.#api.getWikis({ forceRefresh: true });
            this.#wikis = res.data?.wikis ?? [];
            this.#workspaceRoot = res.data?.workspaceRoot ?? localStorage.getItem("active_project_path") ?? "";
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
                    <h2 class="wiki-console-title">Subproject Wikis</h2>
                    <button data-action="refresh-wikis" class="primary-action compact-action" title="Find wikis">${icon("refresh")}</button>
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
                void this.#openWiki(btn.getAttribute("data-name") || "");
            });
            btn.addEventListener("keydown", (event: Event) => {
                if (!(event instanceof KeyboardEvent)) return;
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    if (btn instanceof HTMLElement) btn.click();
                }
            });
        });
    }

    /**
     * Open a selected wiki while keeping its frame hidden until its response is valid.
     *
     * @param {string} name Selected wiki name.
     * @returns {void} Nothing.
     */
    async #openWiki(name: string): Promise<void> {
        if (!this.#api || !name) return;
        try {
            const result = await this.#api.getWikis({ forceRefresh: true, commandLabel: "Refresh wikis" });
            this.#state?.setLastResult(result);
            this.#wikis = result.data?.wikis ?? [];
            this.#workspaceRoot = result.data?.workspaceRoot ?? localStorage.getItem("active_project_path") ?? "";
            const currentWiki = this.#wikis.find(wiki => wiki.name === name);
            if (!result.ok || !currentWiki) {
                const failure = this.#api.reportClientFailure("Open wiki", "Wiki list changed. Select the refreshed entry.");
                this.#state?.setLastResult(failure);
                this.#render();
                return;
            }
            this.#activeWikiName = currentWiki.name;
            this.#wikiLoading = true;
            this.#render();
        } catch {
            const failure = this.#api.reportClientFailure("Open wiki", "Could not refresh the wiki list.");
            this.#state?.setLastResult(failure);
        }
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
                    <h3>No documentation folders found</h3>
                    <p>Create a <code>documentation</code> folder in a subproject to enable local wikis.</p>
                </div>
            `;
        }

        return `
            <main class="wiki-list">
                ${this.#wikis.map(wiki => `
                    <article class="wiki-list-item ${wiki.hasWiki ? "is-clickable" : ""}"
                        ${wiki.hasWiki ? `data-action="view-wiki" data-name="${escapeHtml(wiki.name)}" tabindex="0" role="button" aria-label="Open wiki ${escapeHtml(wiki.name)}"` : ""}>
                        <div class="wiki-list-content">
                            <div class="wiki-list-heading">
                                <strong>${escapeHtml(wiki.name)}</strong>
                                <span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 600; background: ${wiki.hasWiki ? "rgba(16, 185, 129, 0.15); color: #10b981;" : "rgba(156, 163, 175, 0.15); color: #9ca3af;"};">
                                    ${wiki.hasWiki ? "Available" : "No Markdown"}
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
                                <span style="font-size: var(--font-size-sm); color: var(--text-muted); padding: 6px 0;">No documentation pages</span>
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
        const activeWikiName = this.#activeWikiName ?? "";
        this.innerHTML = `
            <div class="wiki-frame-view">
                <header class="wiki-frame-toolbar">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <button data-action="close-wiki" class="secondary-action compact-action" style="min-height: 32px; display: flex; align-items: center; gap: 4px;">
                            ${icon("chevronLeft")} Back
                        </button>
                        <h2 style="margin: 0; font-size: var(--font-size-lg); color: var(--text-strong);">Wiki ~ ${escapeHtml(activeWikiName)}</h2>
                    </div>
                </header>
                <div class="wiki-frame-container">
                    <div class="wiki-frame-loading" ${this.#wikiLoading ? "" : "hidden"} role="status">
                        <span class="loading-spinner" aria-hidden="true"></span>
                        <strong>Resolviendo wiki...</strong>
                    </div>
                    <iframe hidden src="/wiki/workspace/${encodeURIComponent(this.#workspaceRoot)}/${encodeURIComponent(activeWikiName)}/wiki/index.html" scrolling="yes" style="width: 100%; height: 100%; border: none;" title="Wiki Frame"></iframe>
                </div>
            </div>
        `;

        this.querySelector("[data-action='close-wiki']")?.addEventListener("click", () => {
            this.#activeWikiName = null;
            this.#render();
        });
        this.querySelector("iframe")?.addEventListener("load", event => {
            if (event.currentTarget instanceof HTMLIFrameElement) this.#handleWikiFrameLoad(event.currentTarget);
        });
    }

    /**
     * Reject JSON error documents before they become visible inside the wiki frame.
     *
     * @param {HTMLIFrameElement} iframe Loaded same-origin wiki frame.
     * @returns {void} Nothing.
     */
    #handleWikiFrameLoad(iframe: HTMLIFrameElement): void {
        const text = iframe.contentDocument?.body?.textContent?.trim() || "";
        let error = "";
        try {
            const payload: unknown = JSON.parse(text);
            if (typeof payload === "object" && payload !== null && "ok" in payload && payload.ok === false) {
                error = "error" in payload && typeof payload.error === "string" ? payload.error : "Could not open wiki.";
            }
        } catch {
            // A rendered wiki is HTML, not a JSON error document.
        }
        if (error) {
            this.#activeWikiName = null;
            this.#wikiLoading = false;
            const result = this.#api?.reportClientFailure("Open wiki", error) ?? null;
            this.#state?.setLastResult(result);
            void this.#loadWikis();
            return;
        }
        this.#wikiLoading = false;
        iframe.hidden = false;
        this.querySelector(".wiki-frame-loading")?.setAttribute("hidden", "");
        this.#hideIframeScrollbar(iframe);
    }

    /**
     * Hide the same-origin wiki scrollbar while preserving wheel, keyboard,
     * and touch scrolling inside the embedded document.
     *
     * @param {HTMLIFrameElement} iframe Loaded wiki frame.
     * @returns {void}
     */
    #hideIframeScrollbar(iframe: HTMLIFrameElement): void {
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
