/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { BrainApiClient } from "../../../infrastructure/shared/http/clients/brain-api-client.ts";
import type { HealthStatus } from "../../../application/settings/dtos/responses/health-response.ts";
import type { AppState } from "../../shell/state/app-state.ts";
import type { ComponentContext } from "../../shared/view_models/component-context-view-model.ts";

/**
 * SettingsView renders compact runtime health facts for the local explorer.
 */
export class SettingsView extends HTMLElement {
    /**
     * Registered Custom Element tag used by the shell route registry.
     * @returns {string} A string representing the DOM element selector for the settings view.
     */
    static get selector() {
        return "brain-settings-view";
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
     * Latest authoritative server-health snapshot rendered by the settings view.
     * @type {HealthStatus | null}
     */
    #health: HealthStatus | null = null;

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context: ComponentContext) {
        this.#api = context.api;
        this.#state = context.state;
        this.#loadHealth();
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
     * Load server health.
     *
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadHealth() {
        if (!this.#api) {
            return;
        }
        const result = await this.#api.health({ forceRefresh: true });
        this.#state?.setLastResult(result);
        this.#health = result.data ?? null;
        this.#render();
    }

    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface settings-console">
                <main class="settings-layout">
                    <button class="settings-tile settings-action-tile" data-action="refresh-health">
                        <span>${escapeHtml("Accion")}</span>
                        <strong>${icon("refresh")}Refresh runtime</strong>
                        <small>health local</small>
                    </button>
                    ${this.#tile("Server", this.#health?.ok ? "OK" : "Pending", "brain_explorer")}
                    ${this.#tile("Dist", this.#health?.distDir || "No cargado", "runtime estatico")}
                    ${this.#tile("Workspace", this.#health?.workspaceRoot || "Not loaded", "active root")}
                    ${this.#tile("Agent home", this.#health?.agentHome || "Not loaded", "shared memory")}
                </main>
            </section>
        `;
        this.querySelector("[data-action='refresh-health']")?.addEventListener("click", () => this.#loadHealth());
    }

    /**
     * Render one settings tile.
     *
     * @param {string} label Tile label.
     * @param {string} value Tile value.
     * @param {string} caption Tile caption.
     * @returns {string} HTML.
     */
    #tile(label: string, value: unknown, caption: string): string {
        return `
            <article class="settings-tile">
                <span>${escapeHtml(label)}</span>
                <strong>${escapeHtml(String(value))}</strong>
                <small>${escapeHtml(caption)}</small>
            </article>
        `;
    }
}

customElements.define(SettingsView.selector, SettingsView);
