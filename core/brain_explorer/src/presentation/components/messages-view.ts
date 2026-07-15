import type { VoiceMessageRecord, VoiceSpeakRecord } from "../../application/contracts/api-dtos.ts";
import { BrainApiClient } from "../../infrastructure/api/brain-api-client.ts";
import { escapeHtml, renderMarkdown } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";

/** Browse, inspect, copy, download, and replay persisted voice messages. */
export class MessagesView extends HTMLElement {
    static get selector() {
        return "brain-messages-view";
    }

    #api: BrainApiClient | null = null;
    #state = null;
    #messages: VoiceMessageRecord[] = [];
    #speaks: VoiceSpeakRecord[] = [];
    #loading = false;
    #playingName = "";
    #refreshTimer: number | null = null;
    #expandedIds = new Set<string>();

    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        void this.#loadMessages();
    }

    connectedCallback() {
        this.#render();
    }

    disconnectedCallback() {
        this.#stopAudio();
        if (this.#refreshTimer !== null) window.clearTimeout(this.#refreshTimer);
    }

    async #loadMessages(silent = false) {
        if (!this.#api) return;
        if (this.#refreshTimer !== null) window.clearTimeout(this.#refreshTimer);
        this.#refreshTimer = null;
        if (!silent) {
            this.#loading = true;
            this.#render();
        }
        try {
            const response = await this.#api.getVoiceMessages({ forceRefresh: true, silent });
            this.#messages = response.data?.messages ?? [];
            this.#speaks = response.data?.speaks ?? [];
            this.#state?.setLastResult(response);
        } finally {
            this.#loading = false;
            this.#render();
            if (this.isConnected) this.#refreshTimer = window.setTimeout(() => void this.#loadMessages(true), 60_000);
        }
    }

    #render() {
        this.innerHTML = `
            <section class="page-surface messages-console">
                <header class="view-header messages-header">
                    <h2>Registro de Messages</h2>
                    <button data-action="refresh-messages" class="compact-action" title="Actualizar mensajes" aria-label="Actualizar mensajes">${icon("refresh")}</button>
                </header>
                <main class="voice-message-list">
                    ${this.#loading ? `<div class="loading-state"><span></span><strong>Cargando mensajes...</strong></div>` : this.#renderMessages()}
                </main>
            </section>
        `;
        this.querySelector("[data-action='refresh-messages']")?.addEventListener("click", () => void this.#loadMessages());
        this.querySelectorAll("[data-action='play-message']").forEach(button => {
            button.addEventListener("click", () => void this.#toggleMessage(button.getAttribute("data-name") || ""));
        });
        this.querySelectorAll(".voice-message-item").forEach(item => {
            item.addEventListener("click", event => {
                const target = event.target instanceof Element ? event.target : null;
                if (target?.closest(".voice-message-actions")) return;
                this.#toggleExpandedMessage(item.getAttribute("data-message-id") || "");
            });
        });
        this.querySelectorAll("[data-action='copy-message']").forEach(button => {
            button.addEventListener("click", () => void this.#copyMessage(button));
        });
    }

    #renderMessages() {
        if (!this.#messages.length && !this.#speaks.length) {
            return `<div class="voice-empty-state">${icon("messageCircle")}<strong>No hay mensajes almacenados</strong></div>`;
        }
        const pairedNames = new Set<string>();
        const retainedItems = this.#speaks.map(speak => {
            const message = this.#messages.find(candidate => candidate.speakId === speak.id);
            if (message) pairedNames.add(message.name);
            return this.#renderMessageItem(speak.id, speak, message);
        });
        const legacyItems = this.#messages
            .filter(message => !pairedNames.has(message.name))
            .map(message => this.#renderMessageItem(message.id ?? message.name, null, message));
        return [...retainedItems, ...legacyItems].join("");
    }

    #renderMessageItem(id: string, speak: VoiceSpeakRecord | null, message: VoiceMessageRecord | undefined) {
        const expanded = this.#expandedIds.has(id);
        const name = message?.name ?? "";
        const createdAt = message?.createdAt ?? speak?.createdAt ?? "";
        const text = speak?.text ?? message?.text ?? "Mensaje histórico sin transcripción";
        const status = speak?.status ?? "DONE";
        return `
            <article class="voice-message-item ${name === this.#playingName ? "is-playing" : ""} ${expanded ? "is-expanded" : ""}" data-message-id="${escapeHtml(id)}">
                <button class="voice-message-summary" data-action="toggle-message-details" data-id="${escapeHtml(id)}" aria-expanded="${expanded}">
                    ${icon(expanded ? "chevronDown" : "chevronRight")}
                    ${expanded ? `<span class="voice-message-spacer"></span>` : `<span class="voice-message-preview">${escapeHtml(text)}</span>`}
                    <span class="voice-speak-status is-${status.toLowerCase()}">${escapeHtml(status)}</span>
                </button>
                ${expanded ? `
                    <div class="voice-message-detail">
                        <div class="voice-message-markdown">${renderMarkdown(text)}</div>
                        ${speak?.error ? `<section class="voice-error-detail" role="alert"><strong>Detalle del error</strong><pre>${escapeHtml(speak.error)}</pre></section>` : ""}
                        <footer class="voice-message-footer">
                            <div class="voice-message-actions">
                                <button class="voice-icon-action" data-action="play-message" data-name="${escapeHtml(name)}" ${name ? "" : "disabled"} title="Reproducir mensaje" aria-label="Reproducir mensaje">${icon(name === this.#playingName ? "pause" : "play")}</button>
                                ${message ? `<a class="voice-download-button labeled" href="${this.#api?.voiceMessageUrl(message.name) ?? "#"}" download="${escapeHtml(message.name)}" title="Descargar mensaje">${icon("download")} ${this.#formatBytes(message.sizeBytes)}</a>` : ""}
                                <button class="voice-icon-action" data-action="copy-message" data-text="${escapeHtml(text)}" title="Copiar mensaje" aria-label="Copiar mensaje">${icon("copy")}</button>
                            </div>
                            <time datetime="${escapeHtml(createdAt)}">${escapeHtml(this.#formatTime(createdAt))}</time>
                        </footer>
                    </div>
                ` : ""}
            </article>
        `;
    }

    async #copyMessage(button: Element) {
        await navigator.clipboard.writeText(button.getAttribute("data-text") || "");
        button.setAttribute("title", "Copiado");
    }

    /** Toggle one bubble while restoring keyboard focus after the DOM refresh. */
    #toggleExpandedMessage(id: string) {
        if (!id) return;
        if (this.#expandedIds.has(id)) this.#expandedIds.delete(id);
        else this.#expandedIds.add(id);
        this.#render();
        const summary = Array.from(this.querySelectorAll<HTMLElement>(".voice-message-summary"))
            .find(candidate => candidate.getAttribute("data-id") === id);
        summary?.focus({ preventScroll: true });
    }

    async #toggleMessage(name: string) {
        if (!this.#api || !name) return;
        if (this.#playingName === name) {
            await this.#api.pauseVoiceReplay();
            this.#stopAudio();
            this.#render();
            return;
        }
        this.#stopAudio();
        this.#playingName = name;
        this.#render();
        try {
            const result = await this.#api.replayVoiceMessage(name);
            if (!result.ok) this.#stopAudio();
        } catch {
            this.#stopAudio();
        }
        this.#render();
    }

    #stopAudio() {
        this.#playingName = "";
    }

    #formatTime(value: string) {
        return new Intl.DateTimeFormat("es", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
    }

    #formatBytes(value: number) {
        return `${Math.max(1, Math.round(value / 1024))} KB`;
    }
}

customElements.define(MessagesView.selector, MessagesView);
