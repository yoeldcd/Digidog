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
        try {
            const result = await this.#api.health({ forceRefresh: true });
            this.#state?.setLastResult(result);
            this.#health = result.ok ? result.data ?? null : null;
        } catch {
            this.#health = null;
        }
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
                    <header class="settings-header">
                        <h1>Settings</h1>
                        <div class="settings-actions">
                            <button class="settings-refresh-action" data-action="refresh-health">${icon("refresh")}<span>Refresh</span></button>
                            <button class="settings-secondary-action" data-action="clear-api-cache">${icon("trash")}<span>Clear cache</span></button>
                        </div>
                    </header>
                    <section class="settings-section" aria-labelledby="settings-workspace-title">
                        <h2 id="settings-workspace-title">Workspace</h2>
                        <dl class="settings-path-list">
                            ${this.#pathRow("Project root", this.#health?.workspaceRoot || "Not loaded", "")}
                            ${this.#pathRow("Agent home", this.#health?.agentHome || "Not loaded", "")}
                        </dl>
                    </section>
                </main>
            </section>
        `;
        this.querySelector("[data-action='refresh-health']")?.addEventListener("click", () => this.#loadHealth());
        this.querySelector("[data-action='clear-api-cache']")?.addEventListener("click", event => {
            this.#api?.clearCache();
            if (event.currentTarget instanceof HTMLButtonElement) {
                event.currentTarget.title = "Cache cleared";
                event.currentTarget.blur();
            }
        });
        this.querySelectorAll<HTMLButtonElement>("[data-action='copy-setting']").forEach(button => {
            button.addEventListener("click", () => {
                const value = button.dataset.value || "";
                if (!value) return;
                void navigator.clipboard.writeText(value);
                button.title = "Copied";
            });
        });
    }

    /**
     * Render a copyable local runtime path.
     *
     * @param {string} label User-facing path name.
     * @param {string} value Absolute local path.
     * @param {string} description Operational purpose of the path.
     * @returns {string} HTML.
     */
    #pathRow(label: string, value: string, description: string): string {
        return `
            <div class="settings-path-row">
                <dt><strong>${escapeHtml(label)}</strong>${description ? `<small>${escapeHtml(description)}</small>` : ""}</dt>
                <dd><code>${escapeHtml(value)}</code><button class="settings-copy-action" data-action="copy-setting" data-value="${escapeHtml(value)}" title="Copy ${escapeHtml(label)}" aria-label="Copy ${escapeHtml(label)}">${icon("copy")}</button></dd>
            </div>
        `;
    }
}

customElements.define(SettingsView.selector, SettingsView);
