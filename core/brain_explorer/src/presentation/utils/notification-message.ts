/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import type { ApiResponse } from "../../application/contracts/api-dtos.ts";

export interface NotificationText {
    title: string;
    message: string;
}

/** Build concise human feedback from one structured API response. */
export function notificationText(payload: ApiResponse, method: string, requestLabel = ""): NotificationText {
    const data = asRecord(payload.data);
    if (!payload.ok) {
        return { title: "Could not complete", message: readableError(payload, data) };
    }
    return { title: successTitle(data, method), message: successMessage(data, requestLabel) };
}

function successTitle(data: Record<string, unknown>, method: string): string {
    const command = String(data.command || "");
    if (command.includes("delete") || method === "DELETE") return "Item deleted";
    if (command.includes("add") || command.includes("create")) return "Item created";
    if (typeof data.domain === "string" && typeof data.key === "string") return "Changes saved";
    if (command.includes("set") || command.includes("edit") || command.includes("save")) return "Changes saved";
    return "Operation completed";
}

function successMessage(data: Record<string, unknown>, requestLabel: string): string {
    const command = String(data.command || "");
    const task = asRecord(data.task);
    if (Object.keys(task).length) {
        const title = quoted(task.title || task.id || "task");
        const status = String(task.status || "");
        if (command === "add-task") return `Task ${title} was created.`;
        if (command === "edit-task") return `Task ${title} was updated.`;
        if (status === "DONE") return `Task ${title} was completed.`;
        if (status === "WORKING") return `Task ${title} is in progress.`;
        if (status === "TODO") return `Task ${title} returned to pending.`;
    }
    if (command === "delete-task" || data.deleted === true) {
        return `Task ${quoted(data.taskId || "selected")} was deleted.`;
    }
    if (typeof data.domain === "string" && typeof data.key === "string") {
        const entry = quoted(`${data.domain}.${data.key}`);
        return command.includes("delete") ? `Memory ${entry} was deleted.` : `Memory ${entry} was saved.`;
    }
    if (typeof data.domain === "string") {
        if (command.includes("delete")) return `Domain ${quoted(data.domain)} was deleted.`;
        if (command.includes("add")) return `Domain ${quoted(data.domain)} was created.`;
    }
    if (command === "clone-snippet") return `Snippet ${quoted(data.snippet || "selected")} was cloned.`;
    if (command === "register-project") {
        const project = asRecord(data.project);
        return `Project ${quoted(project.name || project.path || "selected")} was registered.`;
    }
    if (command === "speak" || requestLabel.includes("voice")) return "The voice request was processed successfully.";
    return humanString(data.message) || requestFallback(requestLabel);
}

function readableError(payload: ApiResponse, data: Record<string, unknown>): string {
    for (const candidate of [data.error, data.message, payload.error, payload.stderr]) {
        const message = humanString(candidate);
        if (message) return message;
    }
    return "The operation could not be completed. Review the data and try again.";
}

function requestFallback(requestLabel: string): string {
    const label = requestLabel.toLowerCase();
    if (label.includes("memory/entry")) return "The memory entry was updated.";
    if (label.includes("memory/domain")) return "The memory domain was updated.";
    if (label.includes("backlog/task")) return "The task was updated.";
    if (label.includes("voice/replay")) return "Voice playback started.";
    if (label.includes("voice/pause")) return "Voice playback paused.";
    return "The changes were applied successfully.";
}

/** Accept only plain human strings, never serialized JSON documents. */
function humanString(value: unknown): string {
    if (typeof value !== "string") return "";
    const text = value.trim().replace(/^Error:\s*/i, "");
    if (!text || text.startsWith("{") || text.startsWith("[")) return "";
    return text;
}

function asRecord(value: unknown): Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value)
        ? value as Record<string, unknown>
        : {};
}

function quoted(value: unknown): string {
    return `“${String(value || "").trim()}”`;
}
