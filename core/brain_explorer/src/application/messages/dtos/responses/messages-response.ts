/**
 * Metadata for one persisted audio artifact exposed by the voice-message query.
 */
export interface VoiceMessageRecord {
    /**
     * Stable database identifier when associated with a message row.
     * @type {string | undefined}
     */
    id?: string;
    /**
     * Server-side filename used by replay and download operations.
     * @type {string}
     */
    name: string;
    /**
     * Encoded audio size in bytes.
     * @type {number}
     */
    sizeBytes: number;
    /**
     * ISO-compatible creation timestamp supplied by the server.
     * @type {string}
     */
    createdAt: string;
    /**
     * Identifier of the speech job that produced the artifact.
     * @type {string | undefined}
     */
    speakId?: string;
    /**
     * Source text synthesized into the audio artifact.
     * @type {string | undefined}
     */
    text?: string;
    /**
     * Origin classification recorded by the voice service.
     * @type {string | undefined}
     */
    source?: string;
}

/**
 * Current server-side state of one text-to-speech job.
 */
export interface VoiceSpeakRecord {
    /**
     * Stable speech-job identifier.
     * @type {string}
     */
    id: string;
    /**
     * Text submitted to the synthesis pipeline.
     * @type {string}
     */
    text: string;
    /**
     * Language code selected for synthesis.
     * @type {string}
     */
    lang: string;
    /**
     * Closed lifecycle state reported by the voice queue.
     * @type {"WORKING" | "DONE" | "QUEUED" | "ERROR"}
     */
    status: "QUEUED" | "WORKING" | "DONE" | "ERROR";
    /**
     * ISO-compatible timestamp for job creation.
     * @type {string}
     */
    createdAt: string;
    /**
     * Human-readable failure detail when the job ended in `ERROR`.
     * @type {string | undefined}
     */
    error?: string;
}

/**
 * Persisted avatar transcript entry returned by the message-history endpoint.
 */
export interface AvatarMessageRecord {
    /**
     * Stable transcript identifier.
     * @type {string}
     */
    id: string;
    /**
     * Canonical creation timestamp.
     * @type {string}
     */
    created_at: string;
    /**
     * Calendar date used to group transcript sessions.
     * @type {string}
     */
    date: string;
    /**
     * Local display time associated with the transcript entry.
     * @type {string}
     */
    time: string;
    /**
     * Markdown-capable avatar message body.
     * @type {string}
     */
    text: string;
    /**
     * Emotion selected for avatar rendering and voice expression.
     * @type {string}
     */
    emotion: string;
    /**
     * Chat identifier that scopes the transcript session.
     * @type {string}
     */
    chat_id: string;
    /**
     * Language code detected or selected for narration.
     * @type {string}
     */
    language: string;
    /**
     * Operation category that produced the transcript entry.
     * @type {"speak" | "operation"}
     */
    source_type: "speak" | "operation";
    /**
     * CLI command responsible for the entry.
     * @type {string}
     */
    source_command: string;
    /**
     * Command lifecycle phase responsible for persistence.
     * @type {string}
     */
    source_phase: string;
}

/**
 * Summary of one avatar transcript session available for selection.
 */
export interface AvatarMessageSession {
    /**
     * Stable session identifier used by Presentation state.
     * @type {string}
     */
    id: string;
    /**
     * Calendar date containing the session.
     * @type {string}
     */
    date: string;
    /**
     * Chat identifier that disambiguates sessions on the same date.
     * @type {string}
     */
    chatId: string;
    /**
     * Human-readable session label.
     * @type {string}
     */
    label: string;
    /**
     * Number of transcript entries in the session.
     * @type {number}
     */
    messageCount: number;
    /**
     * Timestamp of the first persisted entry.
     * @type {string}
     */
    startedAt: string;
    /**
     * Timestamp of the last persisted entry.
     * @type {string}
     */
    endedAt: string;
}

/**
 * Canonical server-normalized selector for one transcript session.
 */
export interface SelectedAvatarMessageSession {
    /**
     * Calendar date containing the selected transcript session.
     * @type {string}
     */
    date: string;
    /**
     * Chat identifier disambiguating sessions that share the same date.
     * @type {string}
     */
    chatId: string;
}

/**
 * Aggregate response returned by the voice-message browsing query.
 */
export interface VoiceMessagesResponse {
    /**
     * Whether the server completed the query successfully.
     * @type {boolean}
     */
    ok: boolean;
    /**
     * Speech jobs visible to the current workspace.
     * @type {VoiceSpeakRecord[]}
     */
    speaks: VoiceSpeakRecord[];
    /**
     * Persisted audio artifacts visible to the current workspace.
     * @type {VoiceMessageRecord[]}
     */
    messages: VoiceMessageRecord[];
    /**
     * Transcript entries for the selected session or query window.
     * @type {AvatarMessageRecord[]}
     */
    history: AvatarMessageRecord[];
    /**
     * Total transcript count before client-side pagination.
     * @type {number}
     */
    historyTotal: number;
    /**
     * Sessions available for transcript navigation.
     * @type {AvatarMessageSession[]}
     */
    sessions: AvatarMessageSession[];
    /**
     * Server-normalized session selector, or `null` when none is active.
     * @type {SelectedAvatarMessageSession | null}
     */
    selectedSession: SelectedAvatarMessageSession | null;
    /**
     * Database path or logical database identifier used by diagnostics.
     * @type {string}
     */
    database: string;
}

/**
 * Live state snapshot returned by the voice-status endpoint.
 */
export interface VoiceStatusResponse {
    /**
     * Closed runtime state rendered by message player controls.
     * @type {"working" | "stopped" | "awaiting" | "thinking" | "preparing" | "speaking" | "muted" | "muted_replay"}
     */
    state: "stopped" | "awaiting" | "working" | "thinking" | "preparing" | "speaking" | "muted" | "muted_replay";
    /**
     * Speech job currently owned by the voice runtime, or an empty string.
     * @type {string}
     */
    activeSpeakId: string;
    /**
     * Whether narration output is currently suppressed.
     * @type {boolean}
     */
    muted: boolean;
    /**
     * Audible-output level applied by the avatar voice daemon.
     * @type {"off" | "partial" | "total"}
     */
    muteMode: "off" | "partial" | "total";
}

/**
 * Result returned after requesting on-demand synthesis for one transcript entry.
 */
export interface VoiceSynthesisResponse {
    /**
     * Identifier of the queued speech job, when the request was accepted.
     * @type {string | undefined}
     */
    speakId?: string;
}
