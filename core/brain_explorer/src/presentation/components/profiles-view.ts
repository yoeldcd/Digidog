import { escapeHtml, renderMarkdown } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";

/**
 * ProfilesView renders available operational profiles as a list plus one Markdown reader.
 */
export class ProfilesView extends HTMLElement {
    static get selector() {
        return "brain-profiles-view";
    }

    #api = null;
    #state = null;
    #profiles = [];
    #selectedProfile = "";
    #profileText = "";
    #profileEntries = [];
    #selectedEntryKey = "";
    #editing = false;
    #loading = false;
    #pendingTarget = null;

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#pendingTarget = this.#state?.consumeRouteTarget?.("profiles") || this.#pendingTarget;
        this.#loadProfiles();
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
     * Load profile names.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadProfiles(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        const result = await this.#api.profiles({ forceRefresh });
        this.#state?.setLastResult(result);
        this.#profiles = Array.isArray(result.data?.profiles) ? result.data.profiles : Array.isArray(result.data) ? result.data : [];
        const target = this.#pendingTarget || this.#state?.consumeRouteTarget?.("profiles");
        this.#pendingTarget = null;
        if (target?.profile && target.profile !== this.#selectedProfile) {
            this.#profileText = "";
        }
        this.#selectedProfile = target?.profile || this.#selectedProfile || this.#profiles[0] || "";
        this.#render();
        if (this.#selectedProfile && !this.#profileText) {
            await this.#readProfile(this.#selectedProfile, forceRefresh);
        }
    }

    /**
     * Read one profile through the API facade.
     *
     * @param {string} profile Profile name.
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #readProfile(profile, forceRefresh = false) {
        if (!this.#api || !profile) {
            return;
        }
        this.#selectedProfile = profile;
        this.#loading = true;
        this.#render();
        const result = await this.#api.profileRead({ name: profile }, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#profileEntries = Array.isArray(result.data?.entries) ? result.data.entries : [];
        this.#selectedEntryKey = this.#profileEntries.some(entry => entry.key === this.#selectedEntryKey)
            ? this.#selectedEntryKey
            : this.#profileEntries[0]?.key || "";
        this.#profileText = this.#profileMarkdown(result, profile);
        this.#editing = false;
        this.#loading = false;
        this.#render();
    }

    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface profiles-console">
                <main class="structure-layout profiles-layout">
                    <aside class="structure-tree">
                        <header class="structure-panel-header">
                            <strong>Disponibles</strong>
                            <details class="action-menu">
                                <summary>${icon("more")}<span class="sr-only">Acciones</span></summary>
                                <div class="action-menu-panel">
                                    <button data-action="refresh-profiles">${icon("refresh")}Actualizar perfiles</button>
                                </div>
                            </details>
                        </header>
                        <div class="profile-list scroll-list">
                            ${this.#renderProfiles()}
                        </div>
                    </aside>
                    <section class="structure-content">
                        <div class="content-head">
                            <strong>${escapeHtml(this.#selectedProfile || "Sin perfil")}</strong>
                            <div class="profile-entry-actions">
                                ${this.#profileEntries.length ? `
                                    <select data-role="profile-entry" aria-label="Entrada del perfil">
                                        ${this.#profileEntries.map(entry => `<option value="${escapeHtml(entry.key)}" ${entry.key === this.#selectedEntryKey ? "selected" : ""}>${escapeHtml(entry.key)}</option>`).join("")}
                                    </select>
                                    ${this.#editing ? `
                                        <button class="icon-action" data-action="cancel-profile-edit" title="Cancelar edición" aria-label="Cancelar edición">${icon("close")}</button>
                                        <button class="icon-action primary-icon-action" data-action="save-profile" title="Guardar entrada" aria-label="Guardar entrada">${icon("save")}</button>
                                    ` : `<button class="icon-action" data-action="edit-profile" title="Editar entrada" aria-label="Editar entrada">${icon("edit")}</button>`}
                                ` : ""}
                            </div>
                        </div>
                        <article class="markdown-preview profile-reader scroll-area">
                            ${this.#renderProfileContent()}
                        </article>
                    </section>
                </main>
            </section>
        `;
        this.querySelector("[data-action='refresh-profiles']")?.addEventListener("click", () => this.#loadProfiles(true));
        this.querySelectorAll("[data-profile]").forEach(button => {
            button.addEventListener("click", () => this.#readProfile(button.getAttribute("data-profile") || ""));
        });
        this.querySelector("[data-role='profile-entry']")?.addEventListener("change", event => {
            this.#selectedEntryKey = event.target.value;
            this.#editing = false;
            this.#render();
        });
        this.querySelector("[data-action='edit-profile']")?.addEventListener("click", () => {
            this.#editing = true;
            this.#render();
        });
        this.querySelector("[data-action='cancel-profile-edit']")?.addEventListener("click", () => {
            this.#editing = false;
            this.#render();
        });
        this.querySelector("[data-action='save-profile']")?.addEventListener("click", () => this.#saveProfileEntry());
    }

    /**
     * Render profile rows.
     *
     * @returns {string} Profile markup.
     */
    #renderProfiles() {
        if (!this.#profiles.length) {
            return `<p class="empty-state">Sin perfiles.</p>`;
        }
        return this.#profiles.map(profile => `
            <button class="profile-row ${profile === this.#selectedProfile ? "is-active" : ""}" data-profile="${escapeHtml(profile)}">
                ${icon("users")}
                <span>
                    <strong>${escapeHtml(profile)}</strong>
                    <small>read-profile ${escapeHtml(profile)}</small>
                </span>
            </button>
        `).join("");
    }

    /**
     * Render selected profile content.
     *
     * @returns {string} HTML.
     */
    #renderProfileContent() {
        if (this.#loading) {
            return `
                <div class="loading-state">
                    <span></span>
                    <strong>Leyendo perfil</strong>
                </div>
            `;
        }
        if (!this.#selectedProfile) {
            return `<div class="knowledge-empty-state">${icon("users")}<h2>Selecciona un perfil</h2></div>`;
        }
        const entry = this.#profileEntries.find(item => item.key === this.#selectedEntryKey);
        if (this.#editing && entry) {
            return `<textarea class="profile-editor" data-role="profile-editor" aria-label="Contenido de ${escapeHtml(entry.key)}">${escapeHtml(entry.content || entry.text || "")}</textarea>`;
        }
        if (entry) {
            return renderMarkdown(entry.content || entry.text || "Sin contenido cargado.");
        }
        return renderMarkdown(this.#profileText || "Sin contenido cargado.");
    }

    /** Save the selected profile entry through the memory facade. */
    async #saveProfileEntry() {
        const editor = this.querySelector("[data-role='profile-editor']");
        const content = editor?.value ?? "";
        if (!this.#api || !this.#selectedProfile || !this.#selectedEntryKey) {
            return;
        }
        const path = `profiles.${this.#selectedProfile}.${this.#selectedEntryKey}`;
        const result = await this.#api.saveMemoryEntry(path, content);
        this.#state?.setLastResult(result);
        if (result.ok) {
            await this.#readProfile(this.#selectedProfile, true);
        }
    }

    /**
     * Convert profile JSON/stdout into Markdown.
     *
     * @param {object} result API result.
     * @param {string} profile Profile name.
     * @returns {string} Markdown.
     */
    #profileMarkdown(result, profile) {
        if (Array.isArray(result.data?.entries)) {
            return [`# Profile: ${profile}`, "", ...result.data.entries.map(entry => `## ${entry.key || entry.name || "entrada"}\n\n${entry.content || entry.text || ""}`)].join("\n");
        }
        return result.stdout || result.data?.text || result.error || result.stderr || "";
    }
}

customElements.define(ProfilesView.selector, ProfilesView);
