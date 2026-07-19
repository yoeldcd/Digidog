/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import type {
    AvatarMessageRecord,
    AvatarMessageSession,
    VoiceMessageRecord,
    VoiceSpeakRecord
} from "../../application/contracts/api-dtos.ts";
import { BrainApiClient } from "../../infrastructure/api/brain-api-client.ts";
import { StructureTree } from "./structure-tree.ts";
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
    #history: AvatarMessageRecord[] = [];
    #sessions: AvatarMessageSession[] = [];
    #selectedSessionId = "";
    #loading = false;
    #playingName = "";
    #refreshTimer: number | null = null;
    #statusTimer: number | null = null;
    #activeSpeakId = "";
    #serviceState = "stopped";
    #expandedIds = new Set<string>();
    #expandedTreePaths = new Set<string>();
    #generatingAudioIds = new Set<string>();
    #generatedAudioSpeakIds = new Map<string, string>();
    #pendingTarget = null;

    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#pendingTarget = this.#state?.consumeRouteTarget?.("messages") || null;
        void this.#loadMessages();
        void this.#pollVoiceStatus();
    }

    connectedCallback() {
        this.#render();
    }

    disconnectedCallback() {
        this.#stopAudio();
        if (this.#refreshTimer !== null) window.clearTimeout(this.#refreshTimer);
        if (this.#statusTimer !== null) window.clearTimeout(this.#statusTimer);
    }

    /** Synchronize playback controls exclusively from the daemon's latest status. */
    async #pollVoiceStatus() {
        if (!this.#api) return;
        if (this.#statusTimer !== null) window.clearTimeout(this.#statusTimer);
        this.#statusTimer = null;
        try {
            const response = await this.#api.getVoiceStatus({ forceRefresh: true, silent: true });
            const activeSpeakId = response.data?.activeSpeakId ?? "";
            const serviceState = response.data?.state ?? "stopped";
            const playbackActive = ["preparing", "speaking", "muted_replay"].includes(serviceState);
            const playingName = playbackActive
                ? this.#messages.find(message => message.speakId === activeSpeakId)?.name ?? ""
                : "";
            if (
                activeSpeakId !== this.#activeSpeakId
                || serviceState !== this.#serviceState
                || playingName !== this.#playingName
            ) {
                this.#activeSpeakId = activeSpeakId;
                this.#serviceState = serviceState;
                this.#playingName = playingName;
                this.#render();
            }
        } finally {
            if (this.isConnected) {
                this.#statusTimer = window.setTimeout(() => void this.#pollVoiceStatus(), 750);
            }
        }
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
            const selected = this.#sessions.find(session => session.id === this.#selectedSessionId);
            const params = selected ? { date: selected.date, chatId: selected.chatId } : {};
            const response = await this.#api.getVoiceMessages(params, { forceRefresh: true, silent });
            this.#messages = response.data?.messages ?? [];
            this.#speaks = response.data?.speaks ?? [];
            this.#history = response.data?.history ?? [];
            this.#sessions = response.data?.sessions ?? [];
            if (this.#pendingTarget && this.#sessions.length) {
                const target = this.#pendingTarget;
                this.#pendingTarget = null;
                this.#selectedSessionId = String(target.sessionId || this.#selectedSessionId || this.#sessions[0].id);
                const targetSession = this.#sessions.find(session => session.id === this.#selectedSessionId);
                if (targetSession) this.#expandSessionPath(targetSession);
                if (target.messageId) this.#expandedIds.add(String(target.messageId));
                await this.#loadMessages(true);
                return;
            }
            if (!this.#selectedSessionId && this.#sessions.length) {
                this.#selectedSessionId = this.#sessions[0].id;
                this.#expandSessionPath(this.#sessions[0]);
                await this.#loadMessages(true);
                return;
            }
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
                <div class="structure-layout messages-structure">
                    <aside class="structure-tree" aria-label="Message sessions">
                        <brain-structure-tree data-role="message-session-tree"></brain-structure-tree>
                    </aside>
                    <main class="structure-content">
                        <header class="content-head">
                            <strong>${escapeHtml(this.#selectedSessionLabel())}</strong>
                            <span>${this.#selectedSessionId && this.#history.length ? `${this.#history.length} messages` : ""}</span>
                        </header>
                        <section class="voice-message-list" aria-label="Session messages">
                            ${this.#loading ? `<div class="loading-state"><span></span><strong>Loading messages...</strong></div>` : this.#renderMessages()}
                        </section>
                    </main>
                </div>
            </section>
        `;
        this.querySelectorAll("[data-action='play-message']").forEach(button => {
            button.addEventListener("click", () => void this.#toggleMessage(button.getAttribute("data-name") || ""));
        });
        this.querySelectorAll(".voice-message-item").forEach(item => {
            item.addEventListener("click", event => {
                const target = event.target instanceof Element ? event.target : null;
                if (target?.closest(".voice-message-actions, .voice-message-leading-action")) return;
                this.#toggleExpandedMessage(item.getAttribute("data-message-id") || "");
            });
        });
        this.querySelectorAll("[data-action='copy-message']").forEach(button => {
            button.addEventListener("click", () => void this.#copyMessage(button));
        });
        this.querySelectorAll("[data-action='generate-message-audio']").forEach(button => {
            button.addEventListener("click", () => {
                void this.#generateMessageAudio(button.getAttribute("data-message-id") || "");
            });
        });
        this.#configureTree();
    }

    #renderMessages() {
        if (!this.#selectedSessionId) {
            return `<div class="voice-empty-state">${icon("messageCircle")}<strong>Select a session</strong></div>`;
        }
        if (!this.#history.length) {
            return `<div class="voice-empty-state">${icon("messageCircle")}<strong>This session has no messages</strong></div>`;
        }
        const pairedNames = new Set<string>();
        const persistedItems = this.#history.map(record => {
            const speak = this.#speaks.find(candidate => candidate.id === record.id) ?? null;
            const generatedSpeakId = this.#generatedAudioSpeakIds.get(record.id);
            const message = this.#messages.find(candidate =>
                candidate.speakId === record.id || candidate.speakId === generatedSpeakId
            );
            if (message) pairedNames.add(message.name);
            return this.#renderMessageItem(record, speak, message);
        });
        return persistedItems.join("");
    }

    /** Project durable summaries into the shared Explorer tree contract. */
    #sessionTreeNodes() {
        const years = new Map<string, Map<string, Map<string, AvatarMessageSession[]>>>();
        this.#sessions.forEach(session => {
            const [year, month, day] = session.date.split("-");
            if (!years.has(year)) years.set(year, new Map());
            const months = years.get(year)!;
            if (!months.has(month)) months.set(month, new Map());
            const days = months.get(month)!;
            if (!days.has(day)) days.set(day, []);
            days.get(day)!.push(session);
        });
        return [...years.entries()].map(([year, months]) => ({
            id: `messages/${year}`,
            path: `messages/${year}`,
            label: year,
            icon: "folder",
            count: [...months.values()].reduce((total, days) => total + [...days.values()].flat().length, 0),
            children: [...months.entries()].map(([month, days]) => ({
                id: `messages/${year}/${month}`,
                path: `messages/${year}/${month}`,
                label: this.#monthLabel(month),
                icon: "folder",
                count: [...days.values()].flat().length,
                children: [...days.entries()].map(([day, sessions]) => ({
                    id: `messages/${year}/${month}/${day}`,
                    path: `messages/${year}/${month}/${day}`,
                    label: `Dia ${day}`,
                    icon: "folder",
                    count: sessions.length,
                    children: sessions.map(session => ({
                        id: session.id,
                        path: session.id,
                        label: session.chatId ? session.label : `Session ${this.#formatTime(session.startedAt)}`,
                        icon: "messageCircle",
                        count: session.messageCount
                    }))
                }))
            }))
        }));
    }

    /** Configure the reusable structural tree with message session nodes. */
    #configureTree() {
        const tree = this.querySelector("[data-role='message-session-tree']");
        if (!(tree instanceof StructureTree)) return;
        tree.model = {
            nodes: this.#sessionTreeNodes(),
            selectedPath: this.#selectedSessionId,
            expandedPaths: this.#expandedTreePaths,
            toggleOnBranchSelect: true,
            title: "Messages",
            toolbarActions: [{ id: "refresh", label: "Refresh messages", icon: "refresh" }],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "messageCircle",
            searchPlaceholder: "Search sessions...",
            emptyText: this.#loading ? "Loading sessions..." : "No stored sessions."
        };
        tree.addEventListener("brain-tree-select", event => {
            if (!event.detail.branch) void this.#selectSession(event.detail.path);
        });
        tree.addEventListener("brain-tree-toolbar-action", event => {
            if (event.detail.action === "refresh") void this.#loadMessages();
        });
    }

    /** Expand the ancestors of the active session in the shared tree. */
    #expandSessionPath(session: AvatarMessageSession) {
        const [year, month, day] = session.date.split("-");
        this.#expandedTreePaths.add(`messages/${year}`);
        this.#expandedTreePaths.add(`messages/${year}/${month}`);
        this.#expandedTreePaths.add(`messages/${year}/${month}/${day}`);
    }

    /** Return the content-panel heading for the selected session. */
    #selectedSessionLabel() {
        const session = this.#sessions.find(candidate => candidate.id === this.#selectedSessionId);
        if (!session) return "Select a session";
        return session.chatId ? session.label : `Session on ${session.date} at ${this.#formatTime(session.startedAt)}`;
    }

    /** Select a durable session and request only its messages. */
    async #selectSession(id: string) {
        if (!id || id === this.#selectedSessionId) return;
        this.#selectedSessionId = id;
        const selected = this.#sessions.find(session => session.id === id);
        if (selected) this.#expandSessionPath(selected);
        this.#history = [];
        await this.#loadMessages();
    }

    #renderMessageItem(
        record: AvatarMessageRecord,
        speak: VoiceSpeakRecord | null,
        message: VoiceMessageRecord | undefined
    ) {
        const id = record.id;
        const expanded = this.#expandedIds.has(id);
        const name = message?.name ?? "";
        const createdAt = record.created_at;
        const text = record.text;
        const status = speak?.status ?? "DONE";
        const generatingAudio = this.#generatingAudioIds.has(id);
        const sourceLabel = record.source_command
            ? `${record.source_command}:${record.source_phase || "output"}`
            : record.emotion || "speak";
        return `
            <article class="voice-message-item ${name === this.#playingName ? "is-playing" : ""} ${expanded ? "is-expanded" : ""}" data-message-id="${escapeHtml(id)}">
                <div class="voice-message-header">
                    ${expanded
                        ? `<span class="voice-message-leading-placeholder" aria-hidden="true"></span>`
                        : this.#renderLeadingAudioAction(id, name, generatingAudio)}
                    <button class="voice-message-summary" data-action="toggle-message-details" data-id="${escapeHtml(id)}" aria-expanded="${expanded}">
                        ${expanded ? `<span class="voice-message-spacer"></span>` : `<span class="voice-message-preview">${escapeHtml(text)}</span>`}
                        <span class="voice-speak-status is-${status.toLowerCase()}">${escapeHtml(sourceLabel)}</span>
                        <time class="voice-message-time" datetime="${escapeHtml(createdAt)}">${escapeHtml(this.#formatTime(createdAt))}</time>
                    </button>
                </div>
                ${expanded ? `
                    <div class="voice-message-detail">
                        <div class="voice-message-markdown">${renderMarkdown(text)}</div>
                        ${speak?.error ? `<section class="voice-error-detail" role="alert"><strong>Error details</strong><pre>${escapeHtml(speak.error)}</pre></section>` : ""}
                        <footer class="voice-message-footer">
                            <div class="voice-message-actions">
                                ${name
                                    ? `<button class="voice-icon-action" data-action="play-message" data-name="${escapeHtml(name)}" title="Play message" aria-label="Play message">${icon(name === this.#playingName ? "pause" : "play")}</button>`
                                    : `<button class="voice-icon-action" data-action="generate-message-audio" data-message-id="${escapeHtml(id)}" ${generatingAudio ? "disabled" : ""} title="Generate audio" aria-label="Generate audio">${icon("volume")}</button>`
                                }
                                ${message ? `<a class="voice-download-button labeled" href="${this.#api?.voiceMessageUrl(message.name) ?? "#"}" download="${escapeHtml(message.name)}" title="Download message">${icon("download")} ${this.#formatBytes(message.sizeBytes)}</a>` : ""}
                                <button class="voice-icon-action" data-action="copy-message" data-text="${escapeHtml(text)}" title="Copy message" aria-label="Copy message">${icon("copy")}</button>
                            </div>
                        </footer>
                    </div>
                ` : ""}
            </article>
        `;
    }

    #renderLegacyMessageItem(message: VoiceMessageRecord) {
        const createdAt = message.createdAt;
        const text = message.text ?? "Historical audio without transcription";
        const id = message.id ?? message.name;
        const expanded = this.#expandedIds.has(id);
        return `
            <article class="voice-message-item ${message.name === this.#playingName ? "is-playing" : ""} ${expanded ? "is-expanded" : ""}" data-message-id="${escapeHtml(id)}">
                <div class="voice-message-header">
                    ${expanded
                        ? `<span class="voice-message-leading-placeholder" aria-hidden="true"></span>`
                        : this.#renderLeadingAudioAction(id, message.name, false)}
                    <button class="voice-message-summary" data-action="toggle-message-details" data-id="${escapeHtml(id)}" aria-expanded="${expanded}">
                        <span class="voice-message-preview">${escapeHtml(text)}</span>
                        <span class="voice-speak-status is-done">audio</span>
                        <time class="voice-message-time" datetime="${escapeHtml(createdAt)}">${escapeHtml(this.#formatTime(createdAt))}</time>
                    </button>
                </div>
                ${expanded ? `
                    <div class="voice-message-detail">
                        <div class="voice-message-markdown">${renderMarkdown(text)}</div>
                        <footer class="voice-message-footer">
                            <div class="voice-message-actions">
                                <button class="voice-icon-action" data-action="play-message" data-name="${escapeHtml(message.name)}" title="Play message" aria-label="Play message">${icon(message.name === this.#playingName ? "pause" : "play")}</button>
                                <a class="voice-download-button labeled" href="${this.#api?.voiceMessageUrl(message.name) ?? "#"}" download="${escapeHtml(message.name)}" title="Download message">${icon("download")} ${this.#formatBytes(message.sizeBytes)}</a>
                                <button class="voice-icon-action" data-action="copy-message" data-text="${escapeHtml(text)}" title="Copy message" aria-label="Copy message">${icon("copy")}</button>
                            </div>
                        </footer>
                    </div>
                ` : ""}
            </article>
        `;
    }

    /** Render the primary list action as replay or on-demand audio generation. */
    #renderLeadingAudioAction(id: string, name: string, generatingAudio: boolean) {
        if (name) {
            const playing = name === this.#playingName;
            return `<button class="voice-icon-action voice-message-leading-action" data-action="play-message" data-name="${escapeHtml(name)}" title="${playing ? "Pause message" : "Play message"}" aria-label="${playing ? "Pause message" : "Play message"}">${icon(playing ? "pause" : "play")}</button>`;
        }
        return `<button class="voice-icon-action voice-message-leading-action" data-action="generate-message-audio" data-message-id="${escapeHtml(id)}" ${generatingAudio ? "disabled" : ""} title="Generate and play audio" aria-label="Generate and play audio">${icon("play")}</button>`;
    }

    async #copyMessage(button: Element) {
        await navigator.clipboard.writeText(button.getAttribute("data-text") || "");
        button.setAttribute("title", "Copiado");
    }

    /** Request one non-persistent audio rendering for a historical message. */
    async #generateMessageAudio(id: string) {
        if (!this.#api || !id || this.#generatingAudioIds.has(id)) return;
        this.#generatingAudioIds.add(id);
        this.#render();
        try {
            const result = await this.#api.synthesizeVoiceMessage(id);
            this.#state?.setLastResult(result);
            const speakId = (result.data as { speakId?: string } | undefined)?.speakId ?? "";
            if (result.ok && speakId) {
                this.#generatedAudioSpeakIds.set(id, speakId);
                await this.#waitForGeneratedAudio(speakId);
            }
        } finally {
            this.#generatingAudioIds.delete(id);
            this.#render();
        }
    }

    /** Refresh briefly until the daemon exposes the newly retained MP3. */
    async #waitForGeneratedAudio(speakId: string) {
        for (let attempt = 0; attempt < 20; attempt += 1) {
            await new Promise(resolve => window.setTimeout(resolve, 500));
            await this.#loadMessages(true);
            if (this.#messages.some(message => message.speakId === speakId)) return;
        }
    }

    /** Toggle one bubble while restoring keyboard focus after the DOM refresh. */
    #toggleExpandedMessage(id: string) {
        if (!id) return;
        const willExpand = !this.#expandedIds.has(id);
        if (willExpand) this.#expandedIds.add(id);
        else this.#expandedIds.delete(id);
        this.#render();
        requestAnimationFrame(() => this.#focusMessage(id, willExpand));
    }

    /** Focus one summary and keep its expanded card inside the message viewport. */
    #focusMessage(id: string, expanded: boolean) {
        const summary = Array.from(this.querySelectorAll<HTMLElement>(".voice-message-summary"))
            .find(candidate => candidate.getAttribute("data-id") === id);
        summary?.focus({ preventScroll: true });
        if (!expanded) return;
        const article = summary?.closest<HTMLElement>(".voice-message-item");
        const container = article?.closest<HTMLElement>(".voice-message-list");
        if (!article || !container) return;
        const articleBounds = article.getBoundingClientRect();
        const containerBounds = container.getBoundingClientRect();
        if (articleBounds.top < containerBounds.top) {
            container.scrollTop -= containerBounds.top - articleBounds.top;
        } else if (articleBounds.bottom > containerBounds.bottom) {
            container.scrollTop += articleBounds.bottom - containerBounds.bottom;
        }
    }

    async #toggleMessage(name: string) {
        if (!this.#api || !name) return;
        if (this.#playingName === name && ["preparing", "speaking", "muted_replay"].includes(this.#serviceState)) {
            await this.#api.pauseVoiceReplay();
            return;
        }
        try {
            await this.#api.replayVoiceMessage(name);
        } catch {
            return;
        }
    }

    #stopAudio() {
        this.#playingName = "";
    }

    #formatTime(value: string) {
        return new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
    }

    #monthLabel(value: string) {
        const date = new Date(2026, Number(value) - 1, 1);
        return new Intl.DateTimeFormat("en", { month: "long" }).format(date);
    }

    #formatBytes(value: number) {
        return `${Math.max(1, Math.round(value / 1024))} KB`;
    }
}

customElements.define(MessagesView.selector, MessagesView);
