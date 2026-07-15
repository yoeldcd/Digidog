import type { ApiResponse } from "../../application/contracts/api-dtos.ts";

export interface NotificationText {
    title: string;
    message: string;
}

/** Build concise human feedback from one structured API response. */
export function notificationText(payload: ApiResponse, method: string, requestLabel = ""): NotificationText {
    const data = asRecord(payload.data);
    if (!payload.ok) {
        return { title: "No se pudo completar", message: readableError(payload, data) };
    }
    return { title: successTitle(data, method), message: successMessage(data, requestLabel) };
}

function successTitle(data: Record<string, unknown>, method: string): string {
    const command = String(data.command || "");
    if (command.includes("delete") || method === "DELETE") return "Elemento eliminado";
    if (command.includes("add") || command.includes("create")) return "Elemento creado";
    if (typeof data.domain === "string" && typeof data.key === "string") return "Cambios guardados";
    if (command.includes("set") || command.includes("edit") || command.includes("save")) return "Cambios guardados";
    return "Operación completada";
}

function successMessage(data: Record<string, unknown>, requestLabel: string): string {
    const command = String(data.command || "");
    const task = asRecord(data.task);
    if (Object.keys(task).length) {
        const title = quoted(task.title || task.id || "tarea");
        const status = String(task.status || "");
        if (command === "add-task") return `Se creó la tarea ${title}.`;
        if (command === "edit-task") return `Se actualizaron los datos de ${title}.`;
        if (status === "DONE") return `La tarea ${title} quedó completada.`;
        if (status === "WORKING") return `La tarea ${title} está en progreso.`;
        if (status === "TODO") return `La tarea ${title} volvió a pendientes.`;
    }
    if (command === "delete-task" || data.deleted === true) {
        return `Se eliminó la tarea ${quoted(data.taskId || "seleccionada")}.`;
    }
    if (typeof data.domain === "string" && typeof data.key === "string") {
        const entry = quoted(`${data.domain}.${data.key}`);
        return command.includes("delete") ? `Se eliminó la memoria ${entry}.` : `Se guardó la memoria ${entry}.`;
    }
    if (typeof data.domain === "string") {
        if (command.includes("delete")) return `Se eliminó el dominio ${quoted(data.domain)}.`;
        if (command.includes("add")) return `Se creó el dominio ${quoted(data.domain)}.`;
    }
    if (command === "clone-snippet") return `Se clonó el snippet ${quoted(data.snippet || "seleccionado")}.`;
    if (command === "register-project") {
        const project = asRecord(data.project);
        return `Se registró el proyecto ${quoted(project.name || project.path || "seleccionado")}.`;
    }
    if (command === "speak" || requestLabel.includes("voice")) return "La solicitud de voz fue procesada correctamente.";
    return humanString(data.message) || requestFallback(requestLabel);
}

function readableError(payload: ApiResponse, data: Record<string, unknown>): string {
    for (const candidate of [data.error, data.message, payload.error, payload.stderr]) {
        const message = humanString(candidate);
        if (message) return message;
    }
    return "La operación no pudo completarse. Revisa los datos e inténtalo de nuevo.";
}

function requestFallback(requestLabel: string): string {
    const label = requestLabel.toLowerCase();
    if (label.includes("memory/entry")) return "La entrada de memoria fue actualizada.";
    if (label.includes("memory/domain")) return "El dominio de memoria fue actualizado.";
    if (label.includes("backlog/task")) return "La tarea fue actualizada.";
    if (label.includes("voice/replay")) return "La reproducción de voz comenzó.";
    if (label.includes("voice/pause")) return "La reproducción de voz se pausó.";
    return "Los cambios se aplicaron correctamente.";
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
