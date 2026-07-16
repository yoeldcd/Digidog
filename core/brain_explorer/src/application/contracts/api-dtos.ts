/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 * @version: 1.0.0
 *
 * Browser-facing DTO contracts for the Brain Explorer API.
 */

export type ThemeMode = "light" | "dark";

export type RouteId = "dashboard" | "memory" | "knowledge" | "query" | "profiles" | "logs" | "backlog" | "messages" | "wikis" | "settings";

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonRecord = Record<string, JsonValue | undefined>;

export interface ApiResponse<TData = unknown> {
    ok: boolean;
    command?: string[];
    code?: number;
    data?: TData;
    stdout?: string;
    stderr?: string;
    durationMs?: number;
    error?: string;
    cached?: boolean;
}

export interface ApiRequestOptions extends RequestInit {
    forceRefresh?: boolean;
    cacheTtlMs?: number;
    commandLabel?: string;
    silent?: boolean;
}

export type QueryParams = Record<string, string | number | boolean | undefined>;

export type BacklogAction = "add" | "delete" | "finish" | "working" | "done" | "todo" | "edit";

export interface BacklogMutation {
    action: BacklogAction;
    taskId?: string;
    domain?: string;
    title?: string;
    description?: string;
    priority?: "HIGH" | "MEDIUM" | "LOW" | "high" | "medium" | "low";
    force?: boolean;
    image?: string | null;
}

export interface RouteTarget {
    route: RouteId;
    target: Record<string, unknown>;
}

export interface CallLogRecord {
    id: string;
    time: string;
    ok: boolean;
    code: number | string;
    durationMs: number;
    command: string;
    data: unknown;
    stdout: string;
    stderr: string;
}

export interface ActiveCommand {
    command: string;
    startedAt: number;
}

export interface CliCommandResult extends ApiResponse {
    command: string[];
    code: number;
    stdout: string;
    stderr: string;
    durationMs: number;
}

export interface MemoryTreeNode {
    path: string;
    name: string;
    kind: "domain" | "entry";
}

export interface MemoryEntry {
    domain: string;
    key: string;
    content: string;
}

export interface KnowledgeStatus {
    ok: boolean;
    scopes: unknown[];
}

export interface KnowledgeListing {
    ok: boolean;
    entities?: unknown[];
    relations?: unknown[];
    classes?: unknown[];
}

export interface ApiError {
    ok: false;
    error: string;
}

export interface ProjectRecord {
    name: string;
    path: string;
}

export interface ProjectsResponse {
    ok: boolean;
    projects: ProjectRecord[];
}

export interface HealthStatus {
    ok: boolean;
    name: string;
    distDir: string;
    workspaceRoot: string;
    agentHome: string;
}

export interface BacklogTask {
    id: string;
    title: string;
    description: string;
    priority: "HIGH" | "MEDIUM" | "LOW";
    status: "TODO" | "WORKING" | "DONE";
    domain: string;
    created_at?: string | number;
    completed_at?: string;
    checked: boolean;
}

export interface BacklogPayload {
    ok: boolean;
    command: "show-backlog";
    domain: string | null;
    includeDone: boolean;
    count: number;
    tasks: BacklogTask[];
}

export interface LogEntryPayload {
    timestamp: string;
    domain: string;
    title: string;
    change_type: string;
    why: string;
    description: string;
    impact: string;
    source_path: string;
    source_mtime: number;
    source_size: number;
}

export interface LogsPayload {
    ok: boolean;
    command: "export-logs" | "log-index";
    count: number;
    entries: LogEntryPayload[];
}

export interface WikiRecord {
    name: string;
    path: string;
    hasWiki: boolean;
}

export interface WikisResponse {
    ok: boolean;
    wikis: WikiRecord[];
}

export interface VoiceMessageRecord {
    id?: string;
    name: string;
    sizeBytes: number;
    createdAt: string;
    speakId?: string;
    text?: string;
    source?: string;
}

export interface VoiceSpeakRecord {
    id: string;
    text: string;
    lang: string;
    status: "QUEUED" | "WORKING" | "DONE" | "ERROR";
    createdAt: string;
    error?: string;
}

export interface VoiceMessagesResponse {
    ok: boolean;
    speaks: VoiceSpeakRecord[];
    messages: VoiceMessageRecord[];
}

export interface WikiUpdateResponse {
    ok: boolean;
    stdout?: string;
    error?: string;
}
