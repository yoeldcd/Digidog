/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import type {
    AvatarMessageRecord,
    AvatarMessageSession,
    VoiceMessageRecord,
    VoiceSpeakRecord
} from "../../../application/messages/dtos/responses/messages-response.ts";
import { BrainApiClient } from "../../../infrastructure/shared/http/clients/brain-api-client.ts";
import { StructureTree } from "../../shared/components/structure-tree.ts";
import { treeActionDetail, treeSelectDetail } from "../../shared/view_models/structure-tree-view-model.ts";
import type { StructureTreeNode } from "../../shared/view_models/structure-tree-view-model.ts";
import { escapeHtml, renderMarkdown } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { AppState } from "../../shell/state/app-state.ts";
import type { ComponentContext } from "../../shared/view_models/component-context-view-model.ts";

/**
 * Browse, inspect, copy, download, and replay persisted voice messages.
 */
export class MessagesView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the MessagesView component in the DOM.
     * @returns {string} A string representing the component's DOM selector.
     */
    static get selector() {
        return "brain-messages-view";
    }

    /**
     * Holds a reference to the BrainApiClient instance used for making API requests within the MessagesView component.
     *
     * @type {BrainApiClient | null}
     */
    #api: BrainApiClient | null = null;
    /**
     * Holds the current application state for the messages view or remains null if the state is not yet initialized.
     *
     * @type {AppState | null}
     */
    #state: AppState | null = null;
    /**
     * Maintains a private collection of voice message records within the view state.
     *
     * @type {VoiceMessageRecord[]}
     */
    #messages: VoiceMessageRecord[] = [];
    /**
     * Maintains a private collection of voice speaking records associated with the messages view.
     *
     * @type {VoiceSpeakRecord[]}
     */
    #speaks: VoiceSpeakRecord[] = [];
    /**
     * Maintains a private collection of avatar message records representing the conversation history.
     *
     * @type {AvatarMessageRecord[]}
     */
    #history: AvatarMessageRecord[] = [];
    /**
     * Maintains a private collection of active avatar message sessions within the view.
     *
     * @type {AvatarMessageSession[]}
     */
    #sessions: AvatarMessageSession[] = [];
    /**
     * Stores the unique identifier of the currently active messaging session.
     *
     * @type {string}
     */
    #selectedSessionId = "";
    /**
     * Tracks the loading state of the messages view to indicate whether data is currently being fetched.
     *
     * @type {boolean}
     */
    #loading = false;
    /**
     * Stores the name of the currently playing track as a private class property.
     *
     * @type {string}
     */
    #playingName = "";
    /**
     * Tracks the active timer identifier for periodic message refreshing or is null when no refresh is scheduled.
     *
     * @type {number | null}
     */
    #refreshTimer: number | null = null;
    /**
     * Tracks the active timeout identifier for message status updates to enable cancellation or rescheduling.
     *
     * @type {number | null}
     */
    #statusTimer: number | null = null;
    /**
     * Maintains the unique identifier of the currently active speaking entity within the messages view.
     *
     * @type {string}
     */
    #activeSpeakId = "";
    /**
     * Tracks the current operational status of the messaging service, initializing to a stopped state.
     *
     * @type {string}
     */
    #serviceState = "stopped";
    /**
     * Tracks the set of unique identifiers for messages currently in an expanded state within the view.
     *
     * @type {Set<string>}
     */
    #expandedIds = new Set<string>();
    /**
     * Maintains a unique collection of active path identifiers for expanded nodes within the messages tree view.
     *
     * @type {Set<string>}
     */
    #expandedTreePaths = new Set<string>();
    /**
     * Tracks the unique identifiers of audio files currently in the process of being generated to prevent duplicate requests.
     *
     * @type {Set<string>}
     */
    #generatingAudioIds = new Set<string>();
    /**
     * Maintains a mapping of generated audio identifiers to their corresponding speak IDs for tracking audio playback state.
     *
     * @type {Map<string, string>}
     */
    #generatedAudioSpeakIds = new Map<string, string>();
    /**
     * Stores the data of a target entity awaiting a pending operation or navigation transition.
     *
     * @type {Record<string, unknown> | null}
     */
    #pendingTarget: Record<string, unknown> | null = null;

    /**
     * Assigns the component context to initialize API and state references, resolves the route target, and triggers initial message loading and voice status polling.
     * @param {ComponentContext} context The component context providing access to the API and state management.
     */
    set context(context: ComponentContext) {
        this.#api = context.api;
        this.#state = context.state;
        this.#pendingTarget = this.#state?.consumeRouteTarget?.("messages") || null;
        void this.#loadMessages();
        void this.#pollVoiceStatus();
    }

    /**
     * Triggers the initial rendering of the component when it is attached to the document DOM.
     */
    connectedCallback() {
        this.#render();
    }

    /**
     * Performs cleanup by stopping audio playback and clearing active refresh and status timers when the component is removed from the DOM.
     */
    disconnectedCallback() {
        this.#stopAudio();
        if (this.#refreshTimer !== null) window.clearTimeout(this.#refreshTimer);
        if (this.#statusTimer !== null) window.clearTimeout(this.#statusTimer);
    }

    /**
     * Synchronize playback controls exclusively from the daemon's latest status.
     */
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

    /**
     * Asynchronously fetches voice messages and session data from the API, updates the internal state, and schedules a recurring refresh timer.
     * @param {boolean} silent Determines whether to suppress the loading state and associated UI re-renders during the fetch process.
     */
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
                this.#selectedSessionId = String(target.sessionId || this.#selectedSessionId || this.#sessions[0]?.id || "");
                const targetSession = this.#sessions.find(session => session.id === this.#selectedSessionId);
                if (targetSession) this.#expandSessionPath(targetSession);
                if (target.messageId) this.#expandedIds.add(String(target.messageId));
                await this.#loadMessages(true);
                return;
            }
            if (!this.#selectedSessionId && this.#sessions.length) {
                const firstSession = this.#sessions[0];
                if (!firstSession) return;
                this.#selectedSessionId = firstSession.id;
                this.#expandSessionPath(firstSession);
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

    /**
     * Updates the component's inner HTML to render the messages console layout and attaches event listeners for message playback, expansion, copying, and audio generation.
     */
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

    /**
     * Generates an HTML string representing the message history list or an empty state view based on the current session selection and history availability.
     * @returns {string} An HTML string containing either a prompt to select a session, a no-messages notification, or a concatenated list of rendered message items.
     */
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

    /**
     * Project durable summaries into the shared Explorer tree contract.
     * @returns {StructureTreeNode[]} An array of StructureTreeNode objects representing the nested temporal hierarchy of message sessions.
     */
    #sessionTreeNodes(): StructureTreeNode[] {
        const years = new Map<string, Map<string, Map<string, AvatarMessageSession[]>>>();
        this.#sessions.forEach(session => {
            const [year = "unknown", month = "unknown", day = "unknown"] = session.date.split("-");
            let months = years.get(year);
            if (!months) {
                months = new Map<string, Map<string, AvatarMessageSession[]>>();
                years.set(year, months);
            }
            let days = months.get(month);
            if (!days) {
                days = new Map<string, AvatarMessageSession[]>();
                months.set(month, days);
            }
            let sessions = days.get(day);
            if (!sessions) {
                sessions = [];
                days.set(day, sessions);
            }
            sessions.push(session);
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

    /**
     * Configure the reusable structural tree with message session nodes.
     */
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
            const detail = event instanceof CustomEvent ? treeSelectDetail(event.detail) : null;
            if (!detail) return;
            if (!detail.branch) void this.#selectSession(detail.path);
        });
        tree.addEventListener("brain-tree-toolbar-action", event => {
            const detail = event instanceof CustomEvent ? treeActionDetail(event.detail) : null;
            if (detail?.action === "refresh") void this.#loadMessages();
        });
    }

    /**
     * Expand the ancestors of the active session in the shared tree.
     * @param {AvatarMessageSession} session The message session containing the date string used to generate the directory hierarchy.
     */
    #expandSessionPath(session: AvatarMessageSession) {
        const [year = "unknown", month = "unknown", day = "unknown"] = session.date.split("-");
        this.#expandedTreePaths.add(`messages/${year}`);
        this.#expandedTreePaths.add(`messages/${year}/${month}`);
        this.#expandedTreePaths.add(`messages/${year}/${month}/${day}`);
    }

    /**
     * Return the content-panel heading for the selected session.
     * @returns {string} A string representing the session's chat ID, its label, or a formatted timestamp of its start time.
     */
    #selectedSessionLabel() {
        const session = this.#sessions.find(candidate => candidate.id === this.#selectedSessionId);
        if (!session) return "Select a session";
        return session.chatId ? session.label : `Session on ${session.date} at ${this.#formatTime(session.startedAt)}`;
    }

    /**
     * Select a durable session and request only its messages.
     * @param {string} id The unique identifier of the session to be selected.
     */
    async #selectSession(id: string) {
        if (!id || id === this.#selectedSessionId) return;
        this.#selectedSessionId = id;
        const selected = this.#sessions.find(session => session.id === id);
        if (selected) this.#expandSessionPath(selected);
        this.#history = [];
        await this.#loadMessages();
    }

    /**
     * Generates an HTML string representing a single voice message item, including its header, status, and optional expanded detail view.
     * @param {AvatarMessageRecord} record The core message data containing the ID, text, timestamp, and source information.
     * @param {VoiceSpeakRecord | null} speak The current voice synthesis status and potential error details.
     * @param {VoiceMessageRecord | undefined} message The metadata for the generated audio file, used for download links.
     * @returns {string} An HTML string containing the markup for the message item.
     */
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

    /**
     * Render the primary list action as replay or on-demand audio generation.
     * @param {string} id The unique identifier of the message used for audio generation requests.
     * @param {string} name The identifier of the audio file to play, or a falsy value if audio must be generated.
     * @param {boolean} generatingAudio A flag indicating whether the audio generation process is currently active to disable the button.
     * @returns {string} An HTML string representing the audio action button with appropriate attributes and icons based on the message state.
     */
    #renderLeadingAudioAction(id: string, name: string, generatingAudio: boolean) {
        if (name) {
            const playing = name === this.#playingName;
            return `<button class="voice-icon-action voice-message-leading-action" data-action="play-message" data-name="${escapeHtml(name)}" title="${playing ? "Pause message" : "Play message"}" aria-label="${playing ? "Pause message" : "Play message"}">${icon(playing ? "pause" : "play")}</button>`;
        }
        return `<button class="voice-icon-action voice-message-leading-action" data-action="generate-message-audio" data-message-id="${escapeHtml(id)}" ${generatingAudio ? "disabled" : ""} title="Generate and play audio" aria-label="Generate and play audio">${icon("play")}</button>`;
    }

    /**
     * Copies the text content from a button's data attribute to the system clipboard and updates the button's tooltip title.
     * @param {Element} button The DOM element containing the text to be copied in its data-text attribute.
     */
    async #copyMessage(button: Element) {
        await navigator.clipboard.writeText(button.getAttribute("data-text") || "");
        button.setAttribute("title", "Copiado");
    }

    /**
     * Request one non-persistent audio rendering for a historical message.
     * @param {string} id The unique identifier of the message to be synthesized into audio.
     */
    async #generateMessageAudio(id: string) {
        if (!this.#api || !id || this.#generatingAudioIds.has(id)) return;
        this.#generatingAudioIds.add(id);
        this.#render();
        try {
            const result = await this.#api.synthesizeVoiceMessage(id);
            this.#state?.setLastResult(result);
            const speakId = result.data?.speakId ?? "";
            if (result.ok && speakId) {
                this.#generatedAudioSpeakIds.set(id, speakId);
                await this.#waitForGeneratedAudio(speakId);
            }
        } finally {
            this.#generatingAudioIds.delete(id);
            this.#render();
        }
    }

    /**
     * Refresh briefly until the daemon exposes the newly retained MP3.
     * @param {string} speakId The unique identifier of the generated audio message to wait for.
     */
    async #waitForGeneratedAudio(speakId: string) {
        for (let attempt = 0; attempt < 20; attempt += 1) {
            await new Promise(resolve => window.setTimeout(resolve, 500));
            await this.#loadMessages(true);
            if (this.#messages.some(message => message.speakId === speakId)) return;
        }
    }

    /**
     * Toggle one bubble while restoring keyboard focus after the DOM refresh.
     * @param {string} id The unique identifier of the message to be expanded or collapsed.
     */
    #toggleExpandedMessage(id: string) {
        if (!id) return;
        const willExpand = !this.#expandedIds.has(id);
        if (willExpand) this.#expandedIds.add(id);
        else this.#expandedIds.delete(id);
        this.#render();
        requestAnimationFrame(() => this.#focusMessage(id, willExpand));
    }

    /**
     * Focus one summary and keep its expanded card inside the message viewport.
     * @param {string} id The unique identifier of the message summary element to be focused.
     * @param {boolean} expanded A flag determining whether the view should scroll to ensure the message item is visible.
     */
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

    /**
     * Toggles the playback of a voice message by either pausing the current replay or initiating a new one based on the provided message identifier and current service state.
     * @param {string} name The unique identifier of the voice message to be toggled.
     */
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

    /**
     * Resets the internal tracking of the currently playing audio by clearing the playing name state.
     */
    #stopAudio() {
        this.#playingName = "";
    }

    /**
     * Formats an ISO or date string into a localized English time string containing only hours and minutes.
     * @param {string} value The date string to be parsed and formatted.
     * @returns {string} A string representing the time in 2-digit hour and minute format.
     */
    #formatTime(value: string) {
        return new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
    }

    /**
     * Converts a numeric month string into its full English name using the Intl.DateTimeFormat API.
     * @param {string} value The numeric representation of the month to be formatted.
     * @returns {string} The full English name of the month.
     */
    #monthLabel(value: string) {
        const date = new Date(2026, Number(value) - 1, 1);
        return new Intl.DateTimeFormat("en", { month: "long" }).format(date);
    }

    /**
     * Converts a numeric byte value into a rounded kilobyte string representation with a minimum floor of 1 KB.
     * @param {number} value The number of bytes to be formatted.
     * @returns {string} A string representing the size in kilobytes followed by the 'KB' unit suffix.
     */
    #formatBytes(value: number) {
        return `${Math.max(1, Math.round(value / 1024))} KB`;
    }
}

customElements.define(MessagesView.selector, MessagesView);
