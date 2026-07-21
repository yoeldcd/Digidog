/**
 * Renders Backlog task collections and dialog surfaces as inert HTML strings.
 *
 * Event binding and state mutation remain owned by the Backlog Web Component; this
 * module owns only deterministic markup composition from explicit typed inputs.
 *
 * @module presentation/backlog/renderers/backlog-layout-renderer
 */

import { escapeHtml } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { BacklogPipTaskViewModel } from "../view_models/backlog-pip-view-model.ts";

/**
 * Render tasks grouped into direct and descendant-domain sections.
 *
 * @param {readonly BacklogPipTaskViewModel[]} tasks Domain-scoped tasks in endpoint order.
 * @param {string} selectedDomain Domain used to distinguish direct tasks and shorten subgroup labels.
 * @param {readonly string[]} tasksWithImages Task identifiers with a persisted visual reference.
 * @returns {string} Backlog task-list markup or an empty-state paragraph.
 */
export function renderBacklogTaskList(
    tasks: readonly BacklogPipTaskViewModel[],
    selectedDomain: string,
    tasksWithImages: readonly string[]
): string {
    if (!tasks.length) return `<p class="empty-state">No visible tasks in this domain.</p>`;
    const directTasks: BacklogPipTaskViewModel[] = [];
    const subgroupMap = new Map<string, BacklogPipTaskViewModel[]>();
    for (const task of tasks) {
        if (task.domain === selectedDomain) {
            directTasks.push(task);
        } else {
            const group = subgroupMap.get(task.domain) ?? [];
            group.push(task);
            subgroupMap.set(task.domain, group);
        }
    }
    const sections: string[] = [];
    if (directTasks.length) {
        sections.push(`<div class="direct-tasks-section" style="margin-bottom: 12px; display: grid; gap: 8px;">
            ${directTasks.map(task => renderBacklogTask(task, tasksWithImages)).join("")}
        </div>`);
    }
    for (const domain of [...subgroupMap.keys()].sort()) {
        const group = subgroupMap.get(domain) ?? [];
        const relativeDomain = selectedDomain ? domain.slice(selectedDomain.length + 1) : domain;
        sections.push(`<details class="subdomain-group" open>
            <summary class="subdomain-group-header">
                ${icon("chevronRight")}<strong>${escapeHtml(relativeDomain)}</strong>
                <span class="subdomain-task-count">(${group.length} tasks)</span>
                <span class="subdomain-line-separator"></span>
            </summary>
            <div class="subdomain-group-content">
                ${group.map(task => renderBacklogTask(task, tasksWithImages)).join("")}
            </div>
        </details>`);
    }
    return sections.join("");
}

/**
 * Render the task composer, visual-reference editor, and image viewer dialogs.
 *
 * @returns {string} Static dialog markup whose controls are bound by the Backlog component.
 */
export function renderBacklogDialogs(): string {
    return `
        <dialog id="backlog-modal" class="backlog-dialog" style="border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 0; width: 720px; height: 540px; max-width: 90vw; max-height: 90vh; box-shadow: var(--shadow); background: var(--surface); color: var(--text);">
            <form method="dialog" class="backlog-modal-form" data-role="modal-form" style="display: flex; flex-direction: column; height: 100%;">
                <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong data-role="modal-title" style="font-size: 16px; color: var(--text-strong);">Create task</strong>
                    <button type="button" class="icon-action close-modal-btn" data-action="close-modal" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
                </header>
                <div class="modal-body" style="padding: 18px; flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden;">
                    <input type="hidden" data-role="modal-task-id" value=""><input type="hidden" data-role="modal-domain" value="">
                    <div class="modal-toolbar" style="display: flex; gap: 10px; align-items: center; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
                        <input type="text" data-role="modal-title-input" placeholder="Task title" required style="flex: 1; min-height: 38px;">
                        <select data-role="modal-priority" style="width: 110px; min-height: 38px;">
                            <option value="HIGH">HIGH</option><option value="MEDIUM">MEDIUM</option><option value="LOW">LOW</option>
                        </select>
                        <button type="button" data-action="open-visual-reference" class="ghost-action compact-action" style="display: inline-flex; align-items: center; gap: 6px; padding: 0 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 13px; font-weight: bold; background: var(--surface-muted); color: var(--primary); height: 38px;">${icon("camera")} Visual Reference</button>
                    </div>
                    <div style="flex: 1; display: flex; min-height: 0; margin-top: 12px;">
                        <textarea data-role="modal-description" placeholder="Write task details and description here..." required style="flex: 1; border: 0; padding: 0; outline: none; background: transparent; font-family: inherit; font-size: 14px; line-height: 1.6; resize: none; overflow-y: auto; scrollbar-width: none; -ms-overflow-style: none;"></textarea>
                    </div>
                </div>
                <footer class="modal-footer" style="display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding: 14px 18px; border-top: 1px solid var(--border); background: var(--surface-strong);">
                    <button type="button" class="ghost-action" data-action="close-modal">Cancel</button>
                    <button type="submit" class="primary-action" data-role="modal-submit-btn">Create</button>
                </footer>
            </form>
        </dialog>
        <dialog id="visual-reference-modal" class="backlog-dialog visual-reference-dialog">
            <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                <strong style="font-size: 16px; color: var(--text-strong);">Visual Reference</strong>
                <button type="button" class="icon-action close-modal-btn" data-action="close-visual-reference" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
            </header>
            <div class="modal-body visual-reference-body"><div class="file-upload-zone visual-reference-upload" data-role="image-upload-zone">
                <span class="visual-reference-label">Attach image / screenshot (optional)</span>
                <input type="file" data-role="modal-image-file" accept="image/*" class="file-input" style="display: none;">
                <div class="image-preview-area" data-role="image-preview-area"><span class="upload-placeholder" style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px;">Click or drag an image here</span><brain-visual-reference-editor hidden></brain-visual-reference-editor></div>
            </div></div>
            <footer class="modal-footer visual-reference-footer"><button type="button" class="primary-action" data-action="close-visual-reference" style="min-width: 100px;">Listo</button></footer>
        </dialog>
        <dialog id="image-viewer-modal" class="backlog-dialog" style="border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 0; width: min(800px, 95vw); box-shadow: var(--shadow); background: var(--surface); color: var(--text);">
            <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);"><strong style="font-size: 16px; color: var(--text-strong);">Vista Ampliada</strong><button type="button" class="icon-action close-modal-btn" data-action="close-image-viewer" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button></header>
            <div class="modal-body" style="padding: 18px; display: grid; place-items: center; background: var(--bg);"><img data-role="viewer-img" src="" style="max-width: 100%; max-height: 70vh; object-fit: contain; border-radius: var(--radius);"></div>
        </dialog>`;
}

/**
 * Render one task row, its state actions, and optional visual-reference thumbnail.
 *
 * @param {BacklogPipTaskViewModel} task View-ready task to render.
 * @param {readonly string[]} tasksWithImages Task identifiers with persisted reference images.
 * @returns {string} Inert task-row markup.
 */
function renderBacklogTask(task: BacklogPipTaskViewModel, tasksWithImages: readonly string[]): string {
    const status = task.status || "TODO";
    const workingIcon = `<div class="working-spinner" title="In progress">${["blue", "cyan", "green", "yellow", "red", "pink"].map(color => `<span class="dot dot-${color}"></span>`).join("")}</div>`;
    const statusIcon = status === "DONE" ? icon("checkSquare") : status === "WORKING" ? workingIcon : icon("clock");
    const statusClass = status === "DONE" ? "task-status-done"
        : status === "WORKING" ? "task-status-working"
            : `task-status-${task.priority.toLowerCase()}`;
    const startSpinner = `<span style="display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; margin-right: 8px; flex-shrink: 0;"><span class="working-spinner" style="transform: scale(0.85); width: 14px; height: 14px; margin: 0; display: inline-block; position: relative;">${["blue", "cyan", "green", "yellow", "red", "pink"].map(color => `<span class="dot dot-${color}" style="width: 3px; height: 3px;"></span>`).join("")}</span></span>`;
    const buttons = status === "DONE"
        ? `<button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="TODO">${icon("clock")}Reopen</button>`
        : status === "TODO"
            ? `<button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="WORKING">${startSpinner}Iniciar trabajo</button><button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="DONE">${icon("checkSquare")}Mark done</button>`
            : `<button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="DONE">${icon("checkSquare")}Mark done</button><button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="TODO">${icon("clock")}Pause (TODO)</button>`;
    const imageTaskId = task.id.replace(/^#/, "");
    const thumbnail = tasksWithImages.includes(imageTaskId)
        ? `<button class="task-image-thumbnail" type="button" data-action="view-image" data-task-id="${escapeHtml(imageTaskId)}" title="View reference image"><img src="/api/backlog/image?taskId=${escapeHtml(imageTaskId)}" alt="Visual reference for ${escapeHtml(task.title)}"></button>`
        : "";
    return `<article class="task-row ${status === "DONE" ? "is-done" : ""}" data-task-row-id="${escapeHtml(task.id)}">
        <span class="task-status ${statusClass}">${statusIcon}</span><div style="flex: 1; min-width: 0;"><strong>${escapeHtml(task.id)} - ${escapeHtml(task.title)}</strong><p>${escapeHtml(task.description)}</p></div>
        <div class="task-actions" style="display: inline-flex; align-items: center; gap: 8px; justify-self: end;">${thumbnail}<details class="action-menu"><summary class="icon-action borderless-summary" title="Opciones">${icon("more")}</summary><div class="action-menu-panel"><button data-action="edit-task" data-task-id="${escapeHtml(task.id)}">${icon("edit")}Edit</button>${buttons}<button data-action="delete-task" data-task-id="${escapeHtml(task.id)}" data-task-status="${status}" class="danger-button">${icon("trash")}Delete task</button></div></details></div>
    </article>`;
}
