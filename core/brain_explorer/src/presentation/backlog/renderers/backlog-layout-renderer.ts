/**
 * Renders Backlog task collections and dialog surfaces as inert HTML strings.
 *
 * Event binding and state mutation remain owned by the Backlog Web Component; this
 * module owns only deterministic markup composition from explicit typed inputs.
 *
 * @module presentation/backlog/renderers/backlog-layout-renderer
 */

import { escapeHtml, workspaceScopedUrl } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { BacklogPipTaskViewModel } from "../view_models/backlog-pip-view-model.ts";

/**
 * Render tasks grouped into direct and descendant-domain sections.
 *
 * @param {readonly BacklogPipTaskViewModel[]} tasks Domain-scoped tasks in endpoint order.
 * @param {string} selectedDomain Domain used to distinguish direct tasks and shorten subgroup labels.
 * @param {readonly string[]} tasksWithImages Task identifiers with persisted visual references.
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
        <dialog id="backlog-modal" class="backlog-dialog backlog-task-editor-dialog">
            <form method="dialog" class="backlog-modal-form task-editor-form" data-role="modal-form">
                <header class="modal-header task-editor-header">
                    <span class="task-status task-editor-status-indicator is-neutral" data-role="modal-status-indicator" title="New task">${icon("clock")}</span>
                    <div class="task-editor-heading"><strong data-role="modal-title">Create task</strong></div>
                    <button type="button" class="task-dialog-close" data-action="close-modal" title="Close editor" aria-label="Close editor">${icon("close")}</button>
                </header>
                <div class="modal-body" style="padding: 18px; flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden;">
                    <input type="hidden" data-role="modal-task-id" value=""><input type="hidden" data-role="modal-domain" value="">
                    <div class="modal-toolbar task-editor-toolbar">
                        <label class="task-editor-field task-editor-title-field"><span>Title</span><input type="text" data-role="modal-title-input" placeholder="Task title" required></label>
                        <label class="task-editor-field task-editor-priority-field"><span>Priority</span><select data-role="modal-priority"><option value="HIGH">HIGH</option><option value="MEDIUM">MEDIUM</option><option value="LOW">LOW</option></select></label>
                        <div class="task-editor-tools">
                            <button type="button" data-action="open-visual-reference" class="task-editor-tool-action" title="Attach or edit a visual reference">${icon("camera")}<span>Image</span></button>
                            <button type="button" data-action="enrich-task-draft" class="task-editor-tool-action task-draft-enrich-action" title="Enrich this draft with profiles and visual context">${icon("enrich")}<span>Enrich</span></button>
                        </div>
                    </div>
                    <div class="task-editor-content">
                        <textarea data-role="modal-description" placeholder="Write task details and description here..." required></textarea>
                    </div>
                </div>
                <footer class="modal-footer task-editor-footer">
                    <button type="button" class="ghost-action task-footer-action" data-action="close-modal">${icon("close")}<span>Cancel</span></button>
                    <button type="submit" class="primary-action task-footer-action" data-role="modal-submit-btn">${icon("save")}<span data-role="modal-submit-label">Create</span></button>
                </footer>
                <div class="task-enrichment-overlay" data-role="task-enrichment-overlay" role="status" aria-live="polite" hidden><span class="working-spinner" aria-hidden="true">${["blue", "cyan", "green", "yellow", "red", "pink"].map(color => `<span class="dot dot-${color}"></span>`).join("")}</span><span>Enriching taskΓÇª</span></div>
            </form>
        </dialog>
        <dialog id="task-viewer-modal" class="backlog-dialog backlog-task-viewer-dialog">
            <article class="task-viewer-shell">
                <header class="modal-header task-viewer-header">
                    <span class="task-status task-viewer-status-indicator" data-role="task-viewer-status-indicator"></span>
                    <div class="task-viewer-heading"><strong data-role="task-viewer-title">Task</strong><div class="task-viewer-badges" data-role="task-viewer-meta"></div></div>
                    <div class="task-viewer-header-actions"><button type="button" class="task-dialog-close" data-action="close-task-viewer" title="Close viewer" aria-label="Close viewer">${icon("close")}</button></div>
                </header>
                <div class="task-viewer-markdown enriched-content" data-role="task-viewer-description"></div>
                <footer class="modal-footer task-viewer-footer">
                    <details class="action-menu task-viewer-options">
                        <summary class="ghost-action task-footer-action" title="Task options">${icon("more")}<span>Options</span></summary>
                        <div class="action-menu-panel task-viewer-options-panel" data-role="task-viewer-options-panel"></div>
                    </details>
                    <button type="button" class="primary-action task-footer-action" data-action="close-task-viewer">${icon("close")}<span>Close</span></button>
                </footer>
            </article>
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
 * Render one compact task row whose title opens the complete task editor.
 *
 * @param {BacklogPipTaskViewModel} task View-ready task to render.
 * @param {readonly string[]} tasksWithImages Task identifiers with persisted visual references.
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
    const normalizedTaskId = task.id.replace(/^#/, "");
    const imageUrl = workspaceScopedUrl(`/api/backlog/image?taskId=${encodeURIComponent(normalizedTaskId)}`);
    const thumbnail = tasksWithImages.includes(normalizedTaskId)
        ? `<button type="button" class="task-reference-thumbnail" data-action="view-image" data-task-id="${escapeHtml(normalizedTaskId)}" title="Open visual reference" aria-label="Open visual reference for ${escapeHtml(task.title)}"><img src="${escapeHtml(imageUrl)}" alt=""></button>`
        : "";
    return `<article class="task-row ${status === "DONE" ? "is-done" : ""}" data-task-row-id="${escapeHtml(task.id)}" tabindex="-1">
        <span class="task-status ${statusClass}">${statusIcon}</span>
        <button type="button" class="task-open-viewer" data-action="view-task" data-task-id="${escapeHtml(task.id)}"><strong>${escapeHtml(task.id)} - ${escapeHtml(task.title)}</strong></button>
        ${thumbnail}
        <div class="task-actions" style="display: inline-flex; align-items: center; gap: 8px; justify-self: end;"><details class="action-menu"><summary class="icon-action borderless-summary" title="Options">${icon("more")}</summary><div class="action-menu-panel"><button data-action="edit-task" data-task-id="${escapeHtml(task.id)}">${icon("edit")}Edit</button>${buttons}<button data-action="delete-task" data-task-id="${escapeHtml(task.id)}" data-task-status="${status}" class="danger-button">${icon("trash")}Delete task</button></div></details></div>
    </article>`;
}
