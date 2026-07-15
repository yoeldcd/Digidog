import { escapeHtml, optionTags } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";
import { BacklogPip } from "./backlog-pip.ts";
import { StructureTree } from "./structure-tree.ts";

void StructureTree;

/**
 * BacklogView renders workspace tasks as a domain tree and focused task board.
 */
export class BacklogView extends HTMLElement {
    static get selector() {
        return "brain-backlog-view";
    }

    #api = null;
    #state = null;
    #backlogSignature = "";
    #tasks = [];
    #selectedDomain = "";
    #filter = "";
    #statusFilter = new Set();
    #priorityFilter = new Set();
    #filtersOpen = false;
    #expandedNodes = new Set();
    #pipWindow = null;
    #pipComponent = null;
    #pipRequestInFlight = false;
    #tasksWithImages = [];
    #refreshTimer = null;
    #refreshInFlight = false;

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#loadBacklog();
    }

    /**
     * Render initial DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
        this.#startSilentRefresh();
    }

    /**
     * Close the native PiP document when its source route is unmounted.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        this.#stopSilentRefresh();
        this.#closePipWindow();
    }

    /** Start the view-owned silent refresh cycle. */
    #startSilentRefresh() {
        if (this.#refreshTimer) {
            return;
        }
        this.#scheduleSilentRefresh();
    }

    /** Stop the silent refresh cycle when this route is unmounted. */
    #stopSilentRefresh() {
        window.clearTimeout(this.#refreshTimer);
        this.#refreshTimer = null;
    }

    /** Schedule the next cycle five seconds after the previous one completed. */
    #scheduleSilentRefresh() {
        if (!this.isConnected) {
            return;
        }
        this.#refreshTimer = window.setTimeout(() => {
            this.#refreshTimer = null;
            this.#refreshSilently();
        }, 60000);
    }

    /** Refresh changed tasks without overlapping requests or repainting unchanged UI. */
    async #refreshSilently() {
        if (!this.#api || this.#refreshInFlight || document.hidden) {
            return;
        }
        this.#refreshInFlight = true;
        try {
            const result = await this.#api.backlog({}, { forceRefresh: true, silent: true });
            const nextTasks = result.data?.tasks || [];
            const nextSignature = JSON.stringify(nextTasks);
            const nextImages = result.hasImages || [];
            if (nextSignature === this.#backlogSignature && JSON.stringify(nextImages) === JSON.stringify(this.#tasksWithImages)) {
                return;
            }
            this.#state?.setLastResult(result);
            this.#backlogSignature = nextSignature;
            this.#tasksWithImages = nextImages;
            this.#tasks = nextTasks;
            this.#syncPipTasks();
            this.#refreshTaskContent();
            this.#configureTree();
        } finally {
            this.#refreshInFlight = false;
            this.#scheduleSilentRefresh();
        }
    }

    /**
     * Load backlog text from the CLI facade.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadBacklog(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        const result = await this.#api.backlog({}, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#tasks = result.data?.tasks || [];
        this.#backlogSignature = JSON.stringify(this.#tasks);
        this.#tasksWithImages = result.hasImages || [];
        this.#syncPipTasks();
        this.#selectedDomain = this.#selectedDomain || "";
        if (this.#selectedDomain) {
            this.#expandAncestors(this.#selectedDomain);
        }
        this.#render();
    }

    /**
     * Set one task state through the CLI facade.
     *
     * @param {string} taskId Task id.
     * @param {string} status Target backlog state.
     * @returns {Promise<void>} Resolves after mutation.
     */
    async #setTaskStatus(taskId, status) {
        const action = String(status).toLowerCase();
        const result = await this.#api.updateBacklog({ action, taskId });
        this.#state?.setLastResult(result);
        if (!result.ok) {
            return;
        }
        await this.#loadBacklog(true);
    }

    /**
     * Delete one task.
     *
     * @param {string} taskId Task id.
     * @param {string} status Current task state.
     * @returns {Promise<void>} Resolves after mutation.
     */
    async #deleteTask(taskId, status) {
        const force = status !== "DONE";
        if (force && !window.confirm("La tarea sigue en curso. Eliminarla de todos modos?")) {
            return;
        }
        const result = await this.#api.updateBacklog({ action: "delete", taskId, force });
        this.#state?.setLastResult(result);
        if (!result.ok) {
            return;
        }
        await this.#loadBacklog(true);
    }

    /**
     * Add one task in the selected domain.
     *
     * @returns {Promise<void>} Resolves after mutation.
     */
    async #addTask() {
        const domain = this.querySelector("[data-role='task-domain']")?.value.trim() || this.#selectedDomain;
        const title = this.querySelector("[data-role='task-title']")?.value.trim();
        const description = this.querySelector("[data-role='task-description']")?.value.trim() || title;
        const priority = this.querySelector("[data-role='task-priority']")?.value || "HIGH";
        if (!domain || !title) {
            return;
        }
        const result = await this.#api.updateBacklog({ action: "add", domain, title, description, priority });
        this.#state?.setLastResult(result);
        this.#selectedDomain = domain;
        await this.#loadBacklog(true);
    }

    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        const domainTasks = this.#domainTasks();
        const visibleTasks = this.#visibleTasks();
        const pipSupported = this.#supportsDocumentPip();
        this.innerHTML = `
            <section class="page-surface backlog-console">
                <div class="structure-layout backlog-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.#renderTree()}
                        </div>
                    </aside>
                    <main class="structure-content">
                        <div class="content-head">
                            <strong style="display: inline-flex; align-items: center; gap: 8px;">
                                ${escapeHtml(this.#selectedDomain || "Backlog")}
                                <span class="backlog-task-count" style="font-size: 13px; font-weight: normal; color: var(--text-muted);">(${visibleTasks.length} tareas)</span>
                            </strong>
                            <div class="backlog-header-actions" style="display: flex; gap: 8px; align-items: center;">
                                <details class="action-menu filter-menu backlog-filter-menu" ${this.#filtersOpen ? "open" : ""}>
                                    <summary class="icon-action" title="Filtrar tareas" aria-label="Filtrar tareas">
                                        ${icon("filter")}
                                        <span class="backlog-filter-count" ${this.#activeFilterCount() ? "" : "hidden"}>${this.#activeFilterCount()}</span>
                                    </summary>
                                    <div class="action-menu-panel filter-menu-panel">
                                        <fieldset class="checkbox-filter-group"><legend>Estado</legend>
                                            ${[["TODO", "Pendientes"], ["WORKING", "En progreso"], ["DONE", "Completadas"]].map(([value, label]) => `<label><input type="checkbox" data-filter-kind="status" value="${value}" ${this.#statusFilter.has(value) ? "checked" : ""}><span>${label}</span></label>`).join("")}
                                        </fieldset>
                                        <fieldset class="checkbox-filter-group"><legend>Prioridad</legend>
                                            ${[["HIGH", "Alta"], ["MEDIUM", "Media"], ["LOW", "Baja"]].map(([value, label]) => `<label><input type="checkbox" data-filter-kind="priority" value="${value}" ${this.#priorityFilter.has(value) ? "checked" : ""}><span>${label}</span></label>`).join("")}
                                        </fieldset>
                                        <button data-action="clear-backlog-filters" class="ghost-action">${icon("close")}Limpiar filtros</button>
                                    </div>
                                </details>
                                <button data-action="open-create-modal" class="ghost-action compact-action" style="font-size: 13px; height: 32px; display: inline-flex; align-items: center; gap: 6px;">${icon("plus")} Crear tarea</button>
                                <button data-action="toggle-pip" class="ghost-action compact-action" style="font-size: 13px; height: 32px; display: inline-flex; align-items: center; gap: 6px;" ${pipSupported ? "" : "disabled"} title="${pipSupported ? "Abrir ventana Picture-in-Picture" : "Document Picture-in-Picture no está disponible en este navegador"}">${icon("eye")} Vista PIP</button>
                            </div>
                        </div>
                        <div class="backlog-workspace scroll-area" style="padding: 14px;">
                            <div class="task-list">
                                ${this.#renderTaskList(domainTasks)}
                                <p class="empty-state backlog-filter-empty" hidden>No hay tareas para estos filtros.</p>
                            </div>
                        </div>
                    </main>
                </div>
            </section>
            ${this.#renderModal()}
        `;
        this.#bindEvents();
        this.#configureTree();
        this.#applyTaskFiltersToDom();
    }

    #renderTaskList(visibleTasks) {
        if (!visibleTasks.length) {
            return `<p class="empty-state">No hay tareas visibles para este dominio.</p>`;
        }
        const directTasks = [];
        const subgroupMap = new Map();
        for (const task of visibleTasks) {
            if (task.domain === this.#selectedDomain) {
                directTasks.push(task);
            } else {
                const list = subgroupMap.get(task.domain) || [];
                list.push(task);
                subgroupMap.set(task.domain, list);
            }
        }
        const html = [];
        if (directTasks.length) {
            html.push(`
                <div class="direct-tasks-section" style="margin-bottom: 12px; display: grid; gap: 8px;">
                    ${directTasks.map(task => this.#renderTask(task)).join("")}
                </div>
            `);
        }
        const sortedDomains = Array.from(subgroupMap.keys()).sort();
        for (const domain of sortedDomains) {
            const tasks = subgroupMap.get(domain);
            const relDomain = this.#selectedDomain ? domain.slice(this.#selectedDomain.length + 1) : domain;
            html.push(`
                <details class="subdomain-group" open>
                    <summary class="subdomain-group-header">
                        ${icon("chevronRight")}
                        <strong>${escapeHtml(relDomain)}</strong>
                        <span class="subdomain-task-count">(${tasks.length} tareas)</span>
                        <span class="subdomain-line-separator"></span>
                    </summary>
                    <div class="subdomain-group-content">
                        ${tasks.map(task => this.#renderTask(task)).join("")}
                    </div>
                </details>
            `);
        }
        return html.join("");
    }

    #renderModal() {
        return `
            <dialog id="backlog-modal" class="backlog-dialog" style="border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 0; width: 720px; height: 540px; max-width: 90vw; max-height: 90vh; box-shadow: var(--shadow); background: var(--surface); color: var(--text);">
                <form method="dialog" class="backlog-modal-form" data-role="modal-form" style="display: flex; flex-direction: column; height: 100%;">
                    <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                        <strong data-role="modal-title" style="font-size: 16px; color: var(--text-strong);">Crear nueva tarea</strong>
                        <button type="button" class="icon-action close-modal-btn" data-action="close-modal" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
                    </header>
                    <div class="modal-body" style="padding: 18px; flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden;">
                        <input type="hidden" data-role="modal-task-id" value="">
                        <input type="hidden" data-role="modal-domain" value="">

                        <div class="modal-toolbar" style="display: flex; gap: 10px; align-items: center; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
                            <input type="text" data-role="modal-title-input" placeholder="Título de la tarea" required style="flex: 1; min-height: 38px;">
                            <select data-role="modal-priority" style="width: 110px; min-height: 38px;">
                                <option value="HIGH">HIGH</option>
                                <option value="MEDIUM">MEDIUM</option>
                                <option value="LOW">LOW</option>
                            </select>
                            <button type="button" data-action="open-visual-reference" class="ghost-action compact-action" style="display: inline-flex; align-items: center; gap: 6px; padding: 0 12px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 13px; font-weight: bold; background: var(--surface-muted); color: var(--primary); height: 38px;">
                                ${icon("camera")} Referencia Visual
                            </button>
                        </div>

                        <div style="flex: 1; display: flex; min-height: 0; margin-top: 12px;">
                            <textarea data-role="modal-description" placeholder="Escribe detalles y descripción de la tarea aquí..." required style="flex: 1; border: 0; padding: 0; outline: none; background: transparent; font-family: inherit; font-size: 14px; line-height: 1.6; resize: none; overflow-y: auto; scrollbar-width: none; -ms-overflow-style: none;"></textarea>
                        </div>
                    </div>
                    <footer class="modal-footer" style="display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding: 14px 18px; border-top: 1px solid var(--border); background: var(--surface-strong);">
                        <button type="button" class="ghost-action" data-action="close-modal">Cancelar</button>
                        <button type="submit" class="primary-action" data-role="modal-submit-btn">Crear</button>
                    </footer>
                </form>
            </dialog>

            <dialog id="visual-reference-modal" class="backlog-dialog visual-reference-dialog">
                <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong style="font-size: 16px; color: var(--text-strong);">Referencia Visual</strong>
                    <button type="button" class="icon-action close-modal-btn" data-action="close-visual-reference" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
                </header>
                <div class="modal-body visual-reference-body">
                    <div class="file-upload-zone visual-reference-upload" data-role="image-upload-zone">
                        <span class="visual-reference-label">Adjuntar Imagen / Captura (Opcional)</span>
                        <input type="file" data-role="modal-image-file" accept="image/*" class="file-input" style="display: none;">
                        <div class="image-preview-area" data-role="image-preview-area">
                            <span class="upload-placeholder" style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px;">Haga clic o arrastre una imagen aquí</span>
                        </div>
                    </div>
                </div>
                <footer class="modal-footer visual-reference-footer">
                    <button type="button" class="primary-action" data-action="close-visual-reference" style="min-width: 100px;">Listo</button>
                </footer>
            </dialog>

            <dialog id="image-viewer-modal" class="backlog-dialog" style="border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 0; width: min(800px, 95vw); box-shadow: var(--shadow); background: var(--surface); color: var(--text);">
                <header class="modal-header" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong style="font-size: 16px; color: var(--text-strong);">Vista Ampliada</strong>
                    <button type="button" class="icon-action close-modal-btn" data-action="close-image-viewer" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
                </header>
                <div class="modal-body" style="padding: 18px; display: grid; place-items: center; background: var(--bg);">
                    <img data-role="viewer-img" src="" style="max-width: 100%; max-height: 70vh; object-fit: contain; border-radius: var(--radius);">
                </div>
            </dialog>
        `;
    }

    /**
     * Determine whether this browser exposes the real Document PiP API.
     *
     * @returns {boolean} True when a user gesture can request a PiP window.
     */
    #supportsDocumentPip() {
        return typeof window.documentPictureInPicture?.requestWindow === "function";
    }

    /**
     * Open one native Document Picture-in-Picture window and mount the
     * dedicated component inside that document.
     *
     * @returns {Promise<void>} Resolves after the PiP component is mounted.
     */
    async #openPipWindow() {
        if (!this.#supportsDocumentPip() || this.#pipRequestInFlight) {
            return;
        }
        if (this.#pipWindow && !this.#pipWindow.closed) {
            this.#pipWindow.focus();
            return;
        }

        this.#pipRequestInFlight = true;
        try {
            const pipWindow = await window.documentPictureInPicture.requestWindow({
                width: 420,
                height: 620,
                disallowReturnToOpener: false,
                preferInitialWindowPlacement: true
            });
            this.#pipWindow = pipWindow;
            this.#copyStylesToPipDocument(pipWindow.document);
            pipWindow.document.title = "Backlog";
            pipWindow.document.documentElement.dataset.theme = document.documentElement.dataset.theme || "dark";
            pipWindow.document.body.className = "backlog-pip-document";

            const pipComponent = document.createElement(BacklogPip.selector);
            pipComponent.tasks = this.#tasks;
            pipComponent.onCaptureScreen = async () => {
                try {
                    const stream = await navigator.mediaDevices.getDisplayMedia({
                        video: { mediaSource: "screen" }
                    });
                    const video = document.createElement("video");
                    video.srcObject = stream;
                    video.play();
                    await new Promise(resolve => {
                        video.onloadedmetadata = () => resolve();
                    });
                    await new Promise(resolve => setTimeout(resolve, 300));
                    const canvas = document.createElement("canvas");
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    const ctx = canvas.getContext("2d");
                    ctx.drawImage(video, 0, 0);
                    stream.getTracks().forEach(track => track.stop());
                    return canvas.toDataURL("image/png");
                } catch (e) {
                    console.error("Screenshot capture failed:", e);
                    return null;
                }
            };
            pipComponent.onAddTask = async (taskData) => {
                const domVal = this.#selectedDomain || "Backlog";
                this.#state?.setActiveCommand(`add-task ${domVal} "${taskData.title}"`);
                try {
                    const result = await this.#api.updateBacklog({
                        action: "add",
                        domain: domVal,
                        title: taskData.title,
                        description: taskData.description,
                        priority: taskData.priority,
                        image: taskData.image
                    });
                    this.#state?.setLastResult(result);
                    if (!result.ok) {
                        return {
                            ok: false,
                            message: result.error || result.stderr || "No se pudo crear la tarea."
                        };
                    }
                    this.#selectedDomain = domVal;
                    await this.#loadBacklog(true);
                    return { ok: true, tasks: this.#tasks };
                } catch (error) {
                    console.error("Unable to add a task from Document PiP.", error);
                    return {
                        ok: false,
                        message: "No se pudo crear la tarea. Intenta de nuevo."
                    };
                }
            };
            pipWindow.document.body.replaceChildren(pipComponent);
            this.#pipComponent = pipComponent;
            pipWindow.addEventListener("pagehide", () => this.#releasePipWindow(pipWindow), { once: true });
        } catch (error) {
            console.warn("Unable to open the Document Picture-in-Picture window.", error);
        } finally {
            this.#pipRequestInFlight = false;
        }
    }

    /**
     * Copy the current Explorer stylesheet contract into a same-origin PiP document.
     *
     * @param {Document} pipDocument Destination document.
     * @returns {void}
     */
    #copyStylesToPipDocument(pipDocument) {
        for (const stylesheet of document.styleSheets) {
            try {
                if (stylesheet.href) {
                    const link = pipDocument.createElement("link");
                    link.rel = "stylesheet";
                    link.href = stylesheet.href;
                    pipDocument.head.appendChild(link);
                    continue;
                }
                const style = pipDocument.createElement("style");
                style.textContent = Array.from(stylesheet.cssRules, rule => rule.cssText).join("\n");
                pipDocument.head.appendChild(style);
            } catch (_error) {
                // Browser-owned and cross-origin stylesheets are not required by PiP.
            }
        }
    }

    /**
     * Update the mounted PiP component without re-opening its window.
     *
     * @returns {void}
     */
    #syncPipTasks() {
        if (this.#pipComponent) {
            this.#pipComponent.tasks = this.#tasks;
        }
    }

    /**
     * Release references to a PiP window that the browser closed.
     *
     * @param {Window} pipWindow Closed PiP window.
     * @returns {void}
     */
    #releasePipWindow(pipWindow) {
        if (this.#pipWindow !== pipWindow) {
            return;
        }
        this.#pipComponent?.remove();
        this.#pipComponent = null;
        this.#pipWindow = null;
    }

    /**
     * Close the active PiP window during Backlog view disposal.
     *
     * @returns {void}
     */
    #closePipWindow() {
        const pipWindow = this.#pipWindow;
        if (!pipWindow || pipWindow.closed) {
            return;
        }
        pipWindow.close();
        this.#releasePipWindow(pipWindow);
    }

    /**
     * Open the standard task composer from either the main view or PiP.
     *
     * @returns {void}
     */
    #openCreateTaskModal() {
        window.focus();
        this.querySelector("[data-action='open-create-modal']")?.click();
    }

    /**
     * Render one task.
     *
     * @param {object} task Parsed task.
     * @returns {string} HTML.
     */
    #renderTask(task) {
        let statusIcon = "";
        let statusClass = "";
        if (task.status === "DONE") {
            statusIcon = icon("checkSquare");
            statusClass = "task-status-done";
        } else if (task.status === "WORKING") {
            statusIcon = `
                <div class="working-spinner" title="En progreso">
                    <span class="dot dot-blue"></span>
                    <span class="dot dot-cyan"></span>
                    <span class="dot dot-green"></span>
                    <span class="dot dot-yellow"></span>
                    <span class="dot dot-red"></span>
                    <span class="dot dot-pink"></span>
                </div>
            `;
            statusClass = "task-status-working";
        } else {
            statusIcon = icon("clock");
            const p = String(task.priority).toUpperCase();
            if (p === "HIGH") {
                statusClass = "task-status-high";
            } else if (p === "MEDIUM") {
                statusClass = "task-status-medium";
            } else {
                statusClass = "task-status-low";
            }
        }
        const status = task.status || "TODO";
        let statusButtons = "";
        if (status === "DONE") {
            statusButtons = `<button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="TODO">${icon("clock")}Reabrir</button>`;
        } else if (status === "TODO") {
            statusButtons = `
                <button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="WORKING">
                    <span style="display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; margin-right: 8px; flex-shrink: 0;">
                        <span class="working-spinner" style="transform: scale(0.85); width: 14px; height: 14px; margin: 0; display: inline-block; position: relative;">
                            <span class="dot dot-blue" style="width: 3px; height: 3px;"></span>
                            <span class="dot dot-cyan" style="width: 3px; height: 3px;"></span>
                            <span class="dot dot-green" style="width: 3px; height: 3px;"></span>
                            <span class="dot dot-yellow" style="width: 3px; height: 3px;"></span>
                            <span class="dot dot-red" style="width: 3px; height: 3px;"></span>
                            <span class="dot dot-pink" style="width: 3px; height: 3px;"></span>
                        </span>
                    </span>
                    Iniciar trabajo
                </button>
                <button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="DONE">${icon("checkSquare")}Marcar hecha</button>
            `;
        } else if (status === "WORKING") {
            statusButtons = `
                <button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="DONE">${icon("checkSquare")}Marcar hecha</button>
                <button data-action="set-task-status" data-task-id="${escapeHtml(task.id)}" data-task-status="TODO">${icon("clock")}Pausar (TODO)</button>
            `;
        }
        const imageTaskId = task.id.replace(/^#/, "");
        const hasImage = this.#tasksWithImages.includes(imageTaskId);
        const imageThumbnail = hasImage
            ? `<button class="task-image-thumbnail" type="button" data-action="view-image" data-task-id="${escapeHtml(imageTaskId)}" title="Ver imagen de referencia">
                  <img src="/api/backlog/image?taskId=${escapeHtml(imageTaskId)}" alt="Referencia visual de ${escapeHtml(task.title)}">
               </button>`
            : "";
        return `
            <article class="task-row ${task.status === "DONE" ? "is-done" : ""}" data-task-row-id="${escapeHtml(task.id)}">
                <span class="task-status ${statusClass}">${statusIcon}</span>
                <div style="flex: 1; min-width: 0;">
                    <strong>${escapeHtml(task.id)} - ${escapeHtml(task.title)}</strong>
                    <p>${escapeHtml(task.description)}</p>
                </div>
                <div class="task-actions" style="display: inline-flex; align-items: center; gap: 8px; justify-self: end;">
                    ${imageThumbnail}
                    <details class="action-menu">
                        <summary class="icon-action borderless-summary" title="Opciones">${icon("more")}</summary>
                        <div class="action-menu-panel">
                            <button data-action="edit-task" data-task-id="${escapeHtml(task.id)}">${icon("edit")}Editar</button>
                            ${statusButtons}
                            <button data-action="delete-task" data-task-id="${escapeHtml(task.id)}" data-task-status="${status}" class="danger-button">${icon("trash")}Eliminar tarea</button>
                        </div>
                    </details>
                </div>
            </article>
        `;
    }

    /**
     * Render domain tree.
     *
     * @returns {string} HTML.
     */
    #renderTree() {
        return `<brain-structure-tree data-role="backlog-tree"></brain-structure-tree>`;
    }

    /**
     * Render one tree node.
     *
     * @param {object} node Tree node.
     * @param {number} depth Tree depth.
     * @returns {string} HTML.
     */
    #renderTreeNode(node, depth) {
        const children = Array.from(node.children.values()).sort((left, right) => left.label.localeCompare(right.label));
        const hasChildren = children.length > 0;
        const isOpen = this.#expandedNodes.has(node.path);
        const isActive = node.path === this.#selectedDomain;
        const count = this.#tasks.filter(task => task.domain === node.path || task.domain.startsWith(`${node.path}.`)).length;
        if (!this.#matchesNode(node)) {
            return "";
        }
        return `
            <div class="tree-node-wrap">
                <button class="tree-node ${isActive ? "is-active" : ""}" style="--tree-depth:${depth}" data-node-path="${escapeHtml(node.path)}" data-node-branch="${hasChildren ? "true" : "false"}">
                    <span class="tree-caret">${hasChildren ? icon(isOpen ? "chevronDown" : "chevronRight") : ""}</span>
                    ${icon(hasChildren ? "folder" : "checkSquare")}
                    <span>${escapeHtml(node.label)}</span>
                    <small>${escapeHtml(String(count))}</small>
                </button>
                ${hasChildren && isOpen ? `<div class="tree-children">${children.map(child => this.#renderTreeNode(child, depth + 1)).join("")}</div>` : ""}
            </div>
        `;
    }

    /**
     * Configure the shared Backlog domain tree.
     *
     * @returns {void}
     */
    #configureTree() {
        const treeElement = this.querySelector("[data-role='backlog-tree']");
        if (!treeElement) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
            toggleOnBranchSelect: true,
            title: "Backlog",
            toolbarActions: [
                { id: "new-domain", label: "Nuevo dominio", icon: "plus" },
                { id: "refresh", label: "Actualizar backlog", icon: "refresh" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "checkSquare",
            searchQuery: this.#filter,
            emptyText: "Sin dominios de backlog. Actualiza para cargar tareas."
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onTreeAction(event));
        treeElement.addEventListener("brain-tree-search", event => {
            this.#filter = event.detail.query;
            this.#refreshTaskContent();
        });
    }

    /**
     * Convert the task domain tree into shared nodes.
     *
     * @returns {object[]} Tree node list.
     */
    #treeNodes() {
        const toNode = node => {
            const children = Array.from(node.children.values())
                .filter(child => this.#matchesNode(child))
                .sort((left, right) => left.label.localeCompare(right.label))
                .map(toNode);
            const count = this.#tasks.filter(task =>
                (task.domain === node.path || task.domain.startsWith(`${node.path}.`))
                && this.#matchesActiveTaskFilters(task)
            ).length;
            return {
                id: node.path,
                path: node.path,
                label: node.label,
                count,
                children,
                actions: []
            };
        };
        return Array.from(this.#buildTree().children.values())
            .filter(node => this.#matchesNode(node))
            .sort((left, right) => left.label.localeCompare(right.label))
            .map(toNode);
    }

    /**
     * Select one Backlog domain without refetching its tree.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeSelected(event) {
        if (event.detail.branch && event.detail.clickedCaret) {
            return;
        }
        this.#selectedDomain = event.detail.path;
        this.#expandAncestors(event.detail.path);
        this.#render();
    }

    /**
     * Handle global Backlog tree actions.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeToolbarAction(event) {
        if (event.detail.action === "new-domain") {
            const newDomain = prompt("Introduce el nombre del nuevo dominio (ej. mi.nuevo.dominio):");
            if (newDomain && newDomain.trim()) {
                const requestedDomain = newDomain.trim();
                const targetDomain = this.#selectedDomain && !requestedDomain.includes(".")
                    ? `${this.#selectedDomain}.${requestedDomain}`
                    : requestedDomain;
                const dialog = this.querySelector("#backlog-modal");
                if (dialog) {
                    this.querySelector("[data-role='modal-task-id']").value = "";
                    const domInput = this.querySelector("[data-role='modal-domain']");
                    domInput.value = targetDomain;
                    domInput.removeAttribute("disabled");
                    this.querySelector("[data-role='modal-title-input']").value = "";
                    this.querySelector("[data-role='modal-description']").value = "";
                    this.querySelector("[data-role='modal-priority']").value = "HIGH";
                    this.#markingRects = [];
                    const imgInput = this.querySelector("[data-role='modal-image-file']");
                    if (imgInput) imgInput.value = "";
                    const previewArea = this.querySelector("[data-role='image-preview-area']");
                    if (previewArea) {
                        previewArea.innerHTML = `<span class="upload-placeholder" style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px;">Haga clic o arrastre una imagen aquí</span>`;
                    }
                    this.#setVisualReferenceHasImage(false);
                    this.querySelector("[data-role='modal-title']").textContent = `Crear nueva tarea en ${newDomain.trim()}`;
                    this.querySelector("[data-role='modal-submit-btn']").textContent = "Crear";
                    dialog.showModal();
                }
            }
        } else if (event.detail.action === "refresh") {
            this.#loadBacklog(true);
        }
    }

    /**
     * Handle contextual Backlog item actions.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeAction(event) {
        const node = event.detail.node;
        if (!node?.path) {
            return;
        }
        this.#selectedDomain = node.path;
        this.#expandAncestors(node.path);
        this.#render();
    }

    /**
     * Return tasks owned by the selected domain subtree.
     *
     * @returns {object[]} Domain-scoped tasks.
     */
    #domainTasks() {
        return this.#tasks
            .filter(task => !this.#selectedDomain || task.domain === this.#selectedDomain || task.domain.startsWith(`${this.#selectedDomain}.`));
    }

    /**
     * Return visible tasks for the selected domain and local content filters.
     *
     * @returns {object[]} Visible tasks.
     */
    #visibleTasks() {
        const needle = this.#filter.toLowerCase();
        return this.#domainTasks()
            .filter(task => !needle || `${task.domain} ${task.title} ${task.description} ${task.id}`.toLowerCase().includes(needle))
            .filter(task => !this.#statusFilter.size || this.#statusFilter.has(task.status))
            .filter(task => !this.#priorityFilter.size || this.#priorityFilter.has(String(task.priority).toUpperCase()));
    }

    /**
     * Count active task-list filters for the toolbar indicator.
     *
     * @returns {number} Number of non-default filters.
     */
    #activeFilterCount() {
        return this.#statusFilter.size + this.#priorityFilter.size;
    }

    /**
     * Refresh the task panel after a local filter change without rebuilding
     * the structural tree or issuing a CLI request.
     *
     * @returns {void}
     */
    #refreshTaskContent() {
        const visibleTasks = this.#visibleTasks();
        this.#applyTaskFiltersToDom();
        const countSpan = this.querySelector(".backlog-task-count");
        if (countSpan) {
            countSpan.textContent = `(${visibleTasks.length} tareas)`;
        }
        const filterCount = this.querySelector(".backlog-filter-count");
        if (filterCount) {
            const activeCount = this.#activeFilterCount();
            filterCount.textContent = String(activeCount);
            filterCount.toggleAttribute("hidden", activeCount === 0);
        }
    }

    /**
     * Toggle mounted task rows and groups for the active local filters.
     * Existing row controls keep their listeners because no row is recreated.
     *
     * @returns {void}
     */
    #applyTaskFiltersToDom() {
        const domainTasks = this.#domainTasks();
        const visibleIds = new Set(this.#visibleTasks().map(task => task.id));
        this.querySelectorAll("[data-task-row-id]").forEach(row => {
            row.toggleAttribute("hidden", !visibleIds.has(row.getAttribute("data-task-row-id") || ""));
        });
        this.querySelectorAll(".direct-tasks-section, .subdomain-group").forEach(group => {
            const hasVisibleRows = Array.from(group.querySelectorAll("[data-task-row-id]")).some(row => !row.hidden);
            group.toggleAttribute("hidden", !hasVisibleRows);
        });
        const emptyState = this.querySelector(".backlog-filter-empty");
        if (emptyState) {
            emptyState.toggleAttribute("hidden", domainTasks.length === 0 || visibleIds.size > 0);
        }
    }

    /**
     * Build tree from task domains.
     *
     * @returns {object} Tree root.
     */
    #buildTree() {
        const root = { label: "", path: "", children: new Map() };
        for (const domain of this.#domains()) {
            const parts = domain.split(".").filter(Boolean);
            let current = root;
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                if (!current.children.has(part)) {
                    current.children.set(part, { label: part, path, children: new Map() });
                }
                current = current.children.get(part);
            });
        }
        return root;
    }

    /**
     * Return unique task domains.
     *
     * @returns {string[]} Domain list.
     */
    #domains() {
        return [...new Set(this.#tasks.map(task => task.domain).filter(Boolean))].sort();
    }

    /**
     * Return whether a node should be visible.
     *
     * @param {object} node Tree node.
     * @returns {boolean} Visibility flag.
     */
    #matchesNode(node) {
        return this.#tasks.some(task =>
            (task.domain === node.path || task.domain.startsWith(`${node.path}.`))
            && this.#matchesActiveTaskFilters(task)
        );
    }

    /**
     * Return whether a task satisfies the toolbar state and priority filters.
     *
     * @param {object} task Backlog task.
     * @returns {boolean} Filter match.
     */
    #matchesActiveTaskFilters(task) {
        const matchesStatus = !this.#statusFilter.size || this.#statusFilter.has(task.status);
        const matchesPriority = !this.#priorityFilter.size
            || this.#priorityFilter.has(String(task.priority).toUpperCase());
        return matchesStatus && matchesPriority;
    }

    /**
     * Expand ancestors for one domain path.
     *
     * @param {string} domain Domain path.
     * @returns {void}
     */
    #expandAncestors(domain) {
        const parts = domain.split(".");
        for (let index = 1; index < parts.length; index += 1) {
            this.#expandedNodes.add(parts.slice(0, index).join("."));
        }
    }

    #markingRects = [];
    #labelDraft = "";

    #displayImageToMark(dataUrl) {
        const previewArea = this.querySelector("[data-role='image-preview-area']");
        if (!previewArea) return;
        this.#setVisualReferenceHasImage(true);
        this.#markingRects = [];
        this.#selectedMarkIndex = -1;
        this.#labelDraft = "";
        previewArea.innerHTML = `
            <div class="marking-container">
                <img data-role="preview-img-element" src="${dataUrl}">
                <svg id="marking-svg" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; cursor: crosshair; touch-action: none;"></svg>
            </div>
            <details class="marking-toolbar-pill">
                <summary>${icon("edit")}<span>Marcas</span>${icon("chevronDown")}</summary>
                <div class="marking-toolbar">
                    <label class="mark-color-control"><span>Color</span><input type="color" data-action="change-mark-color" value="#ff3b30" aria-label="Color de marca"></label>
                    <button type="button" class="mark-delete-control" data-action="delete-selected-mark" title="Eliminar marca seleccionada" aria-label="Eliminar marca seleccionada" disabled>${icon("trash")}</button>
                    <label class="mark-shape-control"><span>Forma</span><select data-action="change-mark-shape"><option value="rectangle">Rectángulo</option><option value="arrow">Flecha</option><option value="path">Trazo</option><option value="label">LABEL</option></select></label>
                    <label class="mark-label-control"><span>Etiqueta</span><input type="text" data-action="change-mark-label" placeholder="Texto para LABEL"></label>
                </div>
            </details>
        `;
        this.#bindImageMarking();
    }

    /** Synchronize empty and loaded states of the visual-reference drop area. */
    #setVisualReferenceHasImage(hasImage) {
        this.querySelector("[data-role='image-upload-zone']")?.classList.toggle("has-image", hasImage);
        this.querySelector("[data-role='image-preview-area']")?.classList.toggle("has-image", hasImage);
        const fileInput = this.querySelector("[data-role='modal-image-file']");
        if (fileInput instanceof HTMLInputElement) {
            fileInput.disabled = hasImage;
        }
    }

    #bindImageMarking() {
        const svg = this.querySelector("#marking-svg");
        if (!svg) return;
        let interaction = null;
        const point = event => {
            const bounds = svg.getBoundingClientRect();
            return { x: (event.clientX - bounds.left) / bounds.width, y: (event.clientY - bounds.top) / bounds.height, bounds };
        };
        svg.addEventListener("pointerdown", event => {
            event.preventDefault();
            const start = point(event);
            const target = event.target.closest?.("[data-mark-index]");
            if (target) {
                const index = Number(target.getAttribute("data-mark-index"));
                this.#selectedMarkIndex = index;
                interaction = { mode: "drag", index, start, original: structuredClone(this.#markingRects[index]) };
                svg.setPointerCapture(event.pointerId);
                this.#renderImageMarks(svg);
                return;
            }
            const type = this.querySelector("[data-action='change-mark-shape']")?.value || "rectangle";
            const color = this.querySelector("[data-action='change-mark-color']")?.value || "#ff3b30";
            if (type === "label") {
                const labelInput = this.querySelector("[data-action='change-mark-label']");
                const label = labelInput?.value.trim() || "";
                if (!label) {
                    labelInput?.focus();
                    return;
                }
                this.#markingRects.push({ type, x: start.x, y: start.y, w: 0, h: 0, points: null, color, label });
                this.#selectedMarkIndex = this.#markingRects.length - 1;
                this.#labelDraft = label;
                this.#renderImageMarks(svg);
                return;
            }
            const index = this.#markingRects.length;
            const draft = {
                type,
                x: start.x,
                y: start.y,
                w: 0,
                h: 0,
                points: type === "path" ? [{ x: start.x, y: start.y }] : null,
                color,
                label: String(this.#shapeMarkCount() + 1)
            };
            this.#markingRects.push(draft);
            this.#selectedMarkIndex = index;
            interaction = { mode: "draw", index, start, type };
            svg.setPointerCapture(event.pointerId);
            this.#renderImageMarks(svg);
        });
        svg.addEventListener("pointermove", event => {
            if (!interaction) return;
            const current = point(event);
            if (interaction.mode === "drag") {
                const dx = current.x - interaction.start.x;
                const dy = current.y - interaction.start.y;
                const mark = { ...interaction.original, x: interaction.original.x + dx, y: interaction.original.y + dy };
                if (mark.points) mark.points = interaction.original.points.map(item => ({ x: item.x + dx, y: item.y + dy }));
                this.#markingRects[interaction.index] = mark;
                this.#renderImageMarks(svg);
            } else {
                const mark = this.#markingRects[interaction.index];
                mark.w = current.x - interaction.start.x;
                mark.h = current.y - interaction.start.y;
                if (interaction.type === "path") {
                    mark.points.push({ x: current.x, y: current.y });
                }
                this.#renderImageMarks(svg);
            }
        });
        svg.addEventListener("pointerup", event => {
            if (!interaction) return;
            const current = point(event);
            if (interaction.mode === "draw") {
                const dx = current.x - interaction.start.x;
                const dy = current.y - interaction.start.y;
                const mark = this.#markingRects[interaction.index];
                mark.w = dx;
                mark.h = dy;
                const valid = interaction.type === "path" ? mark.points.length > 2 : Math.hypot(dx, dy) > 0.01;
                if (!valid) {
                    this.#markingRects.splice(interaction.index, 1);
                    this.#selectedMarkIndex = -1;
                    this.#renumberShapeMarks();
                }
            }
            interaction = null;
            svg.releasePointerCapture?.(event.pointerId);
            this.#renderImageMarks(svg);
        });
        this.querySelector("[data-action='delete-selected-mark']")?.addEventListener("click", e => {
            e.stopPropagation();
            if (this.#selectedMarkIndex < 0 || this.#selectedMarkIndex >= this.#markingRects.length) return;
            this.#markingRects.splice(this.#selectedMarkIndex, 1);
            this.#selectedMarkIndex = -1;
            this.#renumberShapeMarks();
            this.#renderImageMarks(svg);
        });
        this.querySelector("[data-action='change-mark-color']")?.addEventListener("input", event => {
            if (this.#selectedMarkIndex < 0) return;
            this.#markingRects[this.#selectedMarkIndex].color = event.currentTarget.value;
            this.#renderImageMarks(svg);
        });
        this.querySelector("[data-action='change-mark-label']")?.addEventListener("input", event => {
            this.#labelDraft = event.currentTarget.value;
            const selected = this.#markingRects[this.#selectedMarkIndex];
            if (selected?.type === "label") {
                selected.label = event.currentTarget.value;
                this.#renderImageMarks(svg);
            }
        });
    }

    #selectedMarkIndex = -1;

    /** Return the number of geometric marks, excluding standalone labels. */
    #shapeMarkCount() {
        return this.#markingRects.filter(mark => mark.type !== "label").length;
    }

    /** Keep geometric mark numbers sequential without consuming LABEL entries. */
    #renumberShapeMarks() {
        let number = 0;
        for (const mark of this.#markingRects) {
            if (mark.type !== "label") {
                number += 1;
                mark.label = String(number);
            }
        }
    }

    /** Render normalized mark geometry into the interactive SVG overlay. */
    #renderImageMarks(svg) {
        const bounds = svg.getBoundingClientRect();
        const width = bounds.width || 1;
        const height = bounds.height || 1;
        const markup = this.#markingRects.map((mark, index) => {
            const selected = index === this.#selectedMarkIndex ? " is-selected" : "";
            const common = `data-mark-index="${index}" class="${selected}" stroke="${mark.color}" stroke-width="3" fill="none" vector-effect="non-scaling-stroke"`;
            let shape = "";
            if (mark.type === "label") {
                return `<text data-mark-index="${index}" class="mark-standalone-label${selected}" x="${mark.x * width}" y="${mark.y * height}" fill="${mark.color}" font-size="16" font-weight="800" dominant-baseline="hanging">${escapeHtml(mark.label)}</text>`;
            } else if (mark.type === "arrow") {
                const x1 = mark.x * width, y1 = mark.y * height, x2 = (mark.x + mark.w) * width, y2 = (mark.y + mark.h) * height;
                const angle = Math.atan2(y2 - y1, x2 - x1), size = 12;
                const points = `${x2},${y2} ${x2 - size * Math.cos(angle - .45)},${y2 - size * Math.sin(angle - .45)} ${x2 - size * Math.cos(angle + .45)},${y2 - size * Math.sin(angle + .45)}`;
                shape = `<line ${common} x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/><polygon ${common} points="${points}" fill="${mark.color}"/>`;
            } else if (mark.type === "path") {
                shape = `<polyline ${common} points="${mark.points.map(item => `${item.x * width},${item.y * height}`).join(" ")}"/>`;
            } else {
                const x = Math.min(mark.x, mark.x + mark.w) * width, y = Math.min(mark.y, mark.y + mark.h) * height;
                shape = `<rect ${common} x="${x}" y="${y}" width="${Math.abs(mark.w) * width}" height="${Math.abs(mark.h) * height}"/>`;
            }
            const labelX = (mark.x + mark.w) * width - 5, labelY = (mark.y + mark.h) * height - 5;
            return `<g>${shape}<text data-mark-index="${index}" class="${selected}" x="${labelX}" y="${labelY}" fill="${mark.color}" font-size="14" font-weight="800" text-anchor="end">${escapeHtml(mark.label || String(index + 1))}</text></g>`;
        }).join("");
        svg.innerHTML = markup;
        const selected = this.#markingRects[this.#selectedMarkIndex];
        const labelInput = this.querySelector("[data-action='change-mark-label']");
        const colorInput = this.querySelector("[data-action='change-mark-color']");
        const deleteButton = this.querySelector("[data-action='delete-selected-mark']");
        if (labelInput) labelInput.value = selected?.type === "label" ? selected.label : this.#labelDraft;
        if (colorInput && selected?.color) colorInput.value = selected.color;
        if (deleteButton instanceof HTMLButtonElement) deleteButton.disabled = !selected;
    }

    async #getMarkedImageBase64() {
        const img = this.querySelector("[data-role='preview-img-element']");
        if (!img) return null;
        if (!img.complete) {
            await new Promise(resolve => img.onload = resolve);
        }
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0);
        
        this.#markingRects.forEach((r, i) => {
            ctx.strokeStyle = r.color || "red";
            ctx.fillStyle = r.color || "red";
            ctx.lineWidth = 3;
            const x1 = r.x * img.naturalWidth;
            const y1 = r.y * img.naturalHeight;
            const x2 = (r.x + r.w) * img.naturalWidth;
            const y2 = (r.y + r.h) * img.naturalHeight;
            if (r.type === "label") {
                ctx.font = `bold ${Math.max(16, img.naturalWidth * .016)}px sans-serif`;
                ctx.textBaseline = "top";
                ctx.textAlign = "left";
                ctx.fillText(r.label, x1, y1);
                return;
            } else if (r.type === "arrow") {
                const angle = Math.atan2(y2 - y1, x2 - x1);
                const size = Math.max(14, img.naturalWidth * .015);
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(x2, y2);
                ctx.lineTo(x2 - size * Math.cos(angle - .45), y2 - size * Math.sin(angle - .45));
                ctx.lineTo(x2 - size * Math.cos(angle + .45), y2 - size * Math.sin(angle + .45));
                ctx.closePath();
                ctx.fill();
            } else if (r.type === "path") {
                ctx.beginPath();
                r.points.forEach((item, pointIndex) => {
                    const x = item.x * img.naturalWidth, y = item.y * img.naturalHeight;
                    if (pointIndex === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                });
                ctx.stroke();
            } else {
                ctx.strokeRect(x1, y1, r.w * img.naturalWidth, r.h * img.naturalHeight);
            }
            ctx.font = "bold 16px sans-serif";
            ctx.textBaseline = "bottom";
            ctx.textAlign = "right";
            ctx.fillText(
                r.label || String(i + 1),
                x2 - 6,
                y2 - 6
            );
        });
        return canvas.toDataURL("image/png");
    }

    async #captureScreenshot() {
        try {
            const stream = await navigator.mediaDevices.getDisplayMedia({
                video: { mediaSource: "screen" }
            });
            const video = document.createElement("video");
            video.srcObject = stream;
            video.play();
            await new Promise(resolve => {
                video.onloadedmetadata = () => resolve();
            });
            await new Promise(resolve => setTimeout(resolve, 300));
            const canvas = document.createElement("canvas");
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext("2d");
            ctx.drawImage(video, 0, 0);
            stream.getTracks().forEach(track => track.stop());
            const dataUrl = canvas.toDataURL("image/png");
            const createBtn = this.querySelector("[data-action='open-create-modal']");
            createBtn?.click();
            this.#displayImageToMark(dataUrl);
        } catch (err) {
            console.error("Screen capture failed:", err);
        }
    }

    /**
     * Bind DOM events.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelector("[data-action='refresh-backlog']")?.addEventListener("click", () => this.#loadBacklog(true));
        this.querySelector(".backlog-filter-menu")?.addEventListener("toggle", event => {
            this.#filtersOpen = event.currentTarget.open;
        });
        this.querySelectorAll("[data-filter-kind]").forEach(input => input.addEventListener("change", event => {
            const target = event.currentTarget;
            const collection = target.dataset.filterKind === "status" ? this.#statusFilter : this.#priorityFilter;
            if (target.checked) collection.add(target.value); else collection.delete(target.value);
            this.#render();
        }));
        this.querySelector("[data-action='clear-backlog-filters']")?.addEventListener("click", () => {
            this.#statusFilter.clear();
            this.#priorityFilter.clear();
            this.#render();
        });
        this.querySelectorAll("[data-node-path]").forEach(button => button.addEventListener("click", () => {
            const path = button.getAttribute("data-node-path") || "";
            const isBranch = button.getAttribute("data-node-branch") === "true";
            this.#selectedDomain = path;
            this.#expandAncestors(path);
            if (isBranch && this.#expandedNodes.has(path)) {
                this.#expandedNodes.delete(path);
            } else {
                this.#expandedNodes.add(path);
            }
            this.#render();
        }));
        this.querySelectorAll("[data-action='set-task-status']").forEach(button => {
            button.addEventListener("click", () => this.#setTaskStatus(
                button.getAttribute("data-task-id") || "",
                button.getAttribute("data-task-status") || "DONE"
            ));
        });
        this.querySelectorAll("[data-action='delete-task']").forEach(button => {
            button.addEventListener("click", () => this.#deleteTask(
                button.getAttribute("data-task-id") || "",
                button.getAttribute("data-task-status") || "WORKING"
            ));
        });

        // Open Create Modal
        this.querySelector("[data-action='open-create-modal']")?.addEventListener("click", () => {
            const dialog = this.querySelector("#backlog-modal");
            if (!dialog) return;
            this.querySelector("[data-role='modal-task-id']").value = "";
            const domInput = this.querySelector("[data-role='modal-domain']");
            domInput.value = this.#selectedDomain;
            domInput.removeAttribute("disabled");
            this.querySelector("[data-role='modal-title-input']").value = "";
            this.querySelector("[data-role='modal-description']").value = "";
            this.querySelector("[data-role='modal-priority']").value = "HIGH";
            this.#markingRects = [];
            const imgInput = this.querySelector("[data-role='modal-image-file']");
            if (imgInput) imgInput.value = "";
            const previewArea = this.querySelector("[data-role='image-preview-area']");
            if (previewArea) {
                previewArea.innerHTML = `<span class="upload-placeholder" style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px;">Haga clic o arrastre una imagen aquí</span>`;
            }
            this.#setVisualReferenceHasImage(false);
            const imgUploadZone = this.querySelector("[data-role='image-upload-zone']");
            if (imgUploadZone) {
                imgUploadZone.style.removeProperty("display");
            }
            this.querySelector("[data-role='modal-title']").textContent = "Crear nueva tarea";
            this.querySelector("[data-role='modal-submit-btn']").textContent = "Crear";
            dialog.showModal();
        });

        // Open Edit Modal
        this.querySelectorAll("[data-action='edit-task']").forEach(button => {
            button.addEventListener("click", () => {
                const taskId = button.getAttribute("data-task-id") || "";
                const task = this.#tasks.find(t => t.id === taskId);
                if (!task) return;
                const dialog = this.querySelector("#backlog-modal");
                if (!dialog) return;
                this.querySelector("[data-role='modal-task-id']").value = task.id;
                const domInput = this.querySelector("[data-role='modal-domain']");
                domInput.value = task.domain;
                domInput.setAttribute("disabled", "true");
                this.querySelector("[data-role='modal-title-input']").value = task.title;
                this.querySelector("[data-role='modal-description']").value = task.description;
                this.querySelector("[data-role='modal-priority']").value = task.priority;

                const imgUploadZone = this.querySelector("[data-role='image-upload-zone']");
                if (imgUploadZone) {
                    imgUploadZone.style.removeProperty("display");
                }
                this.#markingRects = [];
                const imgInput = this.querySelector("[data-role='modal-image-file']");
                if (imgInput) imgInput.value = "";
                const previewArea = this.querySelector("[data-role='image-preview-area']");
                if (previewArea) {
                    previewArea.innerHTML = `<span class="upload-placeholder" style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px;">Haga clic o arrastre una imagen aquí</span>`;
                }
                this.#setVisualReferenceHasImage(false);
                const imageTaskId = task.id.replace(/^#/, "");
                if (this.#tasksWithImages.includes(imageTaskId)) {
                    this.#displayImageToMark(`/api/backlog/image?taskId=${encodeURIComponent(imageTaskId)}`);
                }

                this.querySelector("[data-role='modal-title']").textContent = `Editar tarea #${task.id}`;
                this.querySelector("[data-role='modal-submit-btn']").textContent = "Guardar";
                dialog.showModal();
            });
        });

        // Close Modal
        this.querySelectorAll("[data-action='close-modal']").forEach(btn => {
            btn.addEventListener("click", () => {
                this.querySelector("#backlog-modal")?.close();
            });
        });

        // Open & Close Visual Reference Modal
        this.querySelector("[data-action='open-visual-reference']")?.addEventListener("click", () => {
            this.querySelector("#visual-reference-modal")?.showModal();
        });
        this.querySelectorAll("[data-action='close-visual-reference']").forEach(btn => {
            btn.addEventListener("click", () => {
                this.querySelector("#visual-reference-modal")?.close();
            });
        });

        // Image Viewer Modal Listeners
        this.querySelectorAll("[data-action='view-image']").forEach(thumb => {
            thumb.addEventListener("click", () => {
                const taskId = thumb.getAttribute("data-task-id") || "";
                const modal = this.querySelector("#image-viewer-modal");
                const img = this.querySelector("[data-role='viewer-img']");
                if (modal && img) {
                    img.src = `/api/backlog/image?taskId=${taskId}`;
                    modal.showModal();
                }
            });
        });
        this.querySelector("[data-action='close-image-viewer']")?.addEventListener("click", () => {
            this.querySelector("#image-viewer-modal")?.close();
        });

        // Paste Image from Clipboard Listener
        const descInput = this.querySelector("[data-role='modal-description']");
        descInput?.addEventListener("paste", event => {
            const items = event.clipboardData?.items;
            if (!items) return;
            for (const item of items) {
                if (item.type.startsWith("image/")) {
                    event.preventDefault();
                    const file = item.getAsFile();
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = ev => {
                            this.#displayImageToMark(ev.target.result);
                            // Insert {ref_image} tag at cursor
                            const start = descInput.selectionStart;
                            const end = descInput.selectionEnd;
                            const val = descInput.value;
                            descInput.value = val.slice(0, start) + "{ref_image}" + val.slice(end);
                            descInput.selectionStart = descInput.selectionEnd = start + "{ref_image}".length;
                        };
                        reader.readAsDataURL(file);
                    }
                    break;
                }
            }
        });

        // Modal Form Submit
        this.querySelector("[data-role='modal-form']")?.addEventListener("submit", async event => {
            event.preventDefault();
            const dialog = this.querySelector("#backlog-modal");
            const taskId = this.querySelector("[data-role='modal-task-id']").value;
            const domain = this.querySelector("[data-role='modal-domain']").value.trim() || this.#selectedDomain || "Backlog";
            const title = this.querySelector("[data-role='modal-title-input']").value.trim();
            const description = this.querySelector("[data-role='modal-description']").value.trim();
            const priority = this.querySelector("[data-role='modal-priority']").value;
            dialog.close();
            if (taskId) {
                this.#state?.setActiveCommand(`edit-task ${taskId}`);
                let base64Image = null;
                try {
                    base64Image = await this.#getMarkedImageBase64();
                } catch (e) {
                    console.error("Error baking marked image:", e);
                }
                const result = await this.#api.updateBacklog({
                    action: "edit",
                    taskId,
                    title,
                    description,
                    priority,
                    image: base64Image
                });
                this.#state?.setLastResult(result);
                await this.#loadBacklog(true);
            } else {
                this.#state?.setActiveCommand(`add-task ${domain} "${title}"`);
                let base64Image = null;
                try {
                    base64Image = await this.#getMarkedImageBase64();
                } catch (e) {
                    console.error("Error baking marked image:", e);
                }
                const result = await this.#api.updateBacklog({
                    action: "add",
                    domain,
                    title,
                    description,
                    priority,
                    image: base64Image
                });
                this.#state?.setLastResult(result);
                this.#selectedDomain = domain;
                await this.#loadBacklog(true);
            }
        });

        // Image Drag & Drop / File Input Click
        const previewArea = this.querySelector("[data-role='image-preview-area']");
        const fileInput = this.querySelector("[data-role='modal-image-file']");
        previewArea?.addEventListener("click", event => {
            if (previewArea.classList.contains("has-image") || fileInput?.disabled) return;
            if (!event.target.closest(".upload-placeholder") && event.target !== previewArea) return;
            fileInput?.click();
        });
        fileInput?.addEventListener("change", e => {
            const file = e.target.files?.[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = ev => {
                    this.#displayImageToMark(ev.target.result);
                };
                reader.readAsDataURL(file);
            }
        });

        // Real Document PiP
        this.querySelector("[data-action='toggle-pip']")?.addEventListener("click", () => {
            this.#openPipWindow();
        });
        this.querySelector("[data-action='capture-screen']")?.addEventListener("click", () => {
            this.#captureScreenshot();
        });
    }
}

customElements.define(BacklogView.selector, BacklogView);
