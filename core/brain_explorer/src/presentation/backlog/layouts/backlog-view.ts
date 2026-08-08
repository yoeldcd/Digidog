/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml, highlightRenderedContent, renderMarkdown, workspaceScopedUrl } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import { StructureTree } from "../../shared/components/structure-tree.ts";
import { renderDomainRenameDialog, requestDomainRename } from "../../shared/components/domain-rename-dialog.ts";
import type { BacklogAction } from "../../../application/backlog/dtos/requests/backlog-mutation-request.ts";
import type { BacklogTask } from "../../../application/backlog/dtos/responses/backlog-response.ts";
import { BacklogPipController } from "../controllers/backlog-pip-controller.ts";
import { BacklogVisualReferenceController } from "../controllers/backlog-visual-reference-controller.ts";
import { BACKLOG_PRIORITY_FILTER_OPTIONS, BACKLOG_STATUS_FILTER_OPTIONS } from "../view_models/backlog-view-model.ts";
import type { BacklogDomainTreeNode } from "../view_models/backlog-view-model.ts";
import type { BacklogPipCreateTaskInput, BacklogPipTaskViewModel } from "../view_models/backlog-pip-view-model.ts";
import type { ComponentContext, TargetFocusableLayout } from "../../shared/view_models/component-context-view-model.ts";
import type { StructureTreeNode } from "../../shared/view_models/structure-tree-view-model.ts";
import { BacklogTaskProjector } from "../projectors/backlog-task-projector.ts";
import { renderBacklogDialogs, renderBacklogTaskList } from "../renderers/backlog-layout-renderer.ts";
import { parseBacklogNavigationTarget } from "../validators/backlog-navigation-target.ts";

void StructureTree;

const BACKLOG_ROOT_PATH = "__backlog_all__";

/**
 * Project a persisted backlog image path back to its editable placeholder.
 *
 * @param {string} description Persisted task Markdown.
 * @param {string} taskId Owning task identifier.
 * @returns {string} Markdown suitable for the task editor.
 */
function editableBacklogDescription(description: string, taskId: string): string {
    const escapedTaskId = taskId.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const referencePattern = new RegExp(
        `(?:\\.\\/)?\\$agent[\\\\/]pictures[\\\\/]backlog-pic-${escapedTaskId}\\.(?:png|jpe?g|gif|webp)`,
        "gi"
    );
    return description.replace(referencePattern, "{ref_image}");
}
/**
 * Project a task description into read-only Markdown with an inline reference image.
 *
 * @param {string} description Persisted task Markdown.
 * @param {string} taskId Owning task identifier.
 * @param {boolean} hasImage Whether the image inventory contains the task asset.
 * @returns {string} Viewer-ready Markdown.
 */
function viewableBacklogDescription(description: string, taskId: string, hasImage: boolean): string {
    const editable = editableBacklogDescription(description, taskId);
    if (!hasImage) return editable;
    const source = workspaceScopedUrl(`/api/backlog/image?taskId=${encodeURIComponent(taskId.replace(/^#/, ""))}`);
    const imageMarkdown = `![Task visual reference](${source})`;
    return editable.includes("{ref_image}")
        ? editable.replaceAll("{ref_image}", imageMarkdown)
        : `${imageMarkdown}\n\n${editable}`;
}

/**
 * BacklogView renders workspace tasks as a domain tree and focused task board.
 */
export class BacklogView extends HTMLElement implements TargetFocusableLayout {
    /**
     * Provides the unique CSS selector string used to identify the BacklogView component in the DOM.
     * @returns {string} The string identifier 'brain-backlog-view'.
     */
    static get selector(): string {
        return "brain-backlog-view";
    }

    /**
     * Holds a reference to the component's API context for accessing shared services or state, defaulting to null.
     *
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/infrastructure/shared/http/clients/brain-api-client").BrainApiClient | null}
     */
    #api: ComponentContext["api"] | null = null;
    /**
     * Holds the internal state of the backlog view component, initialized as null until the component context is established.
     *
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/presentation/shell/state/app-state").AppState | null}
     */
    #state: ComponentContext["state"] | null = null;
    /**
     * Stores a string representation of the backlog's unique signature for identification or state tracking.
     *
     * @type {string}
     */
    #backlogSignature = "";
    /**
     * Maintains a private collection of task view models representing the items displayed within the backlog view.
     *
     * @type {BacklogPipTaskViewModel[]}
     */
    #tasks: BacklogPipTaskViewModel[] = [];
    /**
     * Maintains the identifier of the currently selected domain within the backlog view.
     *
     * @type {string}
     */
    #selectedDomain = "";
    /**
     * Maintains the current text-based filter criteria used to narrow down the displayed backlog items.
     *
     * @type {string}
     */
    #filter = "";
    /** Global-shell query applied only to task cards in the content pane. */
    #contentFilter = "";
    /**
     * Maintains a unique collection of selected task status values used to filter the backlog view.
     *
     * @type {Set<"TODO" | "WORKING" | "DONE">}
     */
    #statusFilter = new Set<BacklogTask["status"]>();
    /**
     * Maintains a unique collection of selected priority levels used to filter the displayed backlog tasks.
     *
     * @type {Set<"HIGH" | "MEDIUM" | "LOW">}
     */
    #priorityFilter = new Set<BacklogTask["priority"]>();
    /**
     * Tracks the visibility state of the backlog filter panel.
     *
     * @type {boolean}
     */
    #filtersOpen = false;
    /**
     * Maintains a set of unique identifiers representing the currently expanded nodes within the backlog view hierarchy.
     *
     * @type {Set<string>}
     */
    #expandedNodes = new Set<string>();
    /**
     * Initializes a private instance of BacklogPipController to manage the pipeline logic within the backlog view.
     *
     * @type {BacklogPipController}
     */
    #pipController = new BacklogPipController();
    /**
     * Initializes a private controller instance to manage visual references within the backlog view.
     *
     * @type {BacklogVisualReferenceController}
     */
    #visualReferenceController = new BacklogVisualReferenceController(this);
    /**
     * Maintains a private collection of identifiers or paths for tasks that contain associated images.
     *
     * @type {string[]}
     */
    #tasksWithImages: string[] = [];
    /**
     * Stores the numeric identifier of the active timer used to trigger periodic backlog data refreshes.
     *
     * @type {number | null}
     */
    #refreshTimer: number | null = null;
    /**
     * Tracks whether a backlog data refresh operation is currently in progress to prevent concurrent requests.
     *
     * @type {boolean}
     */
    #refreshInFlight = false;
    /**
     * Task identifier awaiting one post-render focus operation.
     * @type {string}
     */
    #navigationTaskId = "";
    /**
     * Active draft-enrichment request, or null while the editor is idle.
     * @type {AbortController | null}
     */
    #draftEnrichmentController: AbortController | null = null;

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context: ComponentContext) {
        this.#api = context.api;
        this.#state = context.state;
        void this.#loadBacklog();
    }

    /**
     * Focus a canonical Backlog task target after task data is available.
     *
     * @param {Readonly<Record<string, unknown>>} target Canonical route target containing taskId.
     * @returns {Promise<void>} Resolves after the task row is revealed and focused.
     */
    public async focusTarget(target: Readonly<Record<string, unknown>>): Promise<void> {
        const navigationTarget = parseBacklogNavigationTarget({ ...target });
        if (!navigationTarget) {
            return;
        }

        this.#navigationTaskId = navigationTarget.taskId;
        if (this.#tasks.length === 0) {
            await this.#loadBacklog();
            return;
        }

        this.#applyNavigationTarget();
        this.#render();
        this.#focusNavigationTarget();
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
        this.#draftEnrichmentController?.abort();
        this.#draftEnrichmentController = null;
        this.#pipController.close();
    }

    /**
     * Start the view-owned silent refresh cycle.
     */
    #startSilentRefresh() {
        if (this.#refreshTimer) {
            return;
        }
        this.#scheduleSilentRefresh();
    }

    /**
     * Stop the silent refresh cycle when this route is unmounted.
     */
    #stopSilentRefresh() {
        if (this.#refreshTimer !== null) window.clearTimeout(this.#refreshTimer);
        this.#refreshTimer = null;
    }

    /**
     * Schedule the next cycle five seconds after the previous one completed.
     */
    #scheduleSilentRefresh() {
        if (!this.isConnected) {
            return;
        }
        this.#refreshTimer = window.setTimeout(() => {
            this.#refreshTimer = null;
            this.#refreshSilently();
        }, 60000);
    }

    /**
     * Refresh changed tasks without overlapping requests or repainting unchanged UI.
     */
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
            this.#pipController.syncTasks(this.#tasks);
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
        this.#pipController.syncTasks(this.#tasks);
        this.#applyNavigationTarget();
        this.#selectedDomain = this.#selectedDomain || "";
        if (this.#selectedDomain) {
            this.#taskProjector().ancestorPaths(this.#selectedDomain).forEach(path => this.#expandedNodes.add(path));
        }
        this.#render();
        this.#focusNavigationTarget();
    }

    /**
     * Select the owning domain and expand its hierarchy for a requested task.
     *
     * The Backlog endpoint already includes completed tasks, so a completed
     * navigation target is resolved from the same authoritative collection.
     *
     * @returns {void} Nothing; this method mutates only view-local navigation state.
     */
    #applyNavigationTarget(): void {
        if (!this.#navigationTaskId) return;
        const task = this.#tasks.find(candidate => candidate.id.toLowerCase() === this.#navigationTaskId);
        if (!task) {
            this.#navigationTaskId = "";
            return;
        }
        this.#filter = "";
        this.#statusFilter.clear();
        this.#priorityFilter.clear();
        this.#selectedDomain = task.domain;
        this.#taskProjector().ancestorPaths(task.domain).forEach(path => this.#expandedNodes.add(path));
        this.#expandedNodes.add(task.domain);
    }

    /**
     * Focus and reveal the requested task after its row has been rendered.
     *
     * @returns {void} Nothing; the pending target is consumed after one successful focus.
     */
    #focusNavigationTarget(): void {
        if (!this.#navigationTaskId) return;
        const targetId = this.#navigationTaskId;
        const row = Array.from(this.querySelectorAll<HTMLElement>("[data-task-row-id]"))
            .find(candidate => candidate.dataset.taskRowId?.toLowerCase() === targetId);
        if (!row) return;
        row.classList.add("is-navigation-target");
        row.setAttribute("aria-current", "true");
        row.focus({ preventScroll: true });
        row.scrollIntoView({ behavior: "smooth", block: "center" });
        this.#navigationTaskId = "";
    }

    /**
     * Set one task state through the CLI facade.
     *
     * @param {string} taskId Task id.
     * @param {string} status Target backlog state.
     * @returns {Promise<void>} Resolves after mutation.
     */
    async #setTaskStatus(taskId: string, status: BacklogTask["status"]): Promise<void> {
        if (!this.#api) return;
        const action: BacklogAction = status === "DONE" ? "done" : status === "WORKING" ? "working" : "todo";
        const result = await this.#api.updateBacklog({ action, taskId });
        this.#state?.setLastResult(result);
        if (!result.ok) {
            return;
        }
        await this.#loadBacklog(true);
    }

    /**
     * Enrich one task specification while preserving view-local navigation state.
     *
     * @param {string} taskId Persistent task identifier.
     * @returns {Promise<void>} Resolves after the row has been refreshed.
     */
    async #enrichTask(taskId: string): Promise<void> {
        if (!this.#api || !taskId) return;
        const button = Array.from(this.querySelectorAll<HTMLButtonElement>("[data-action='enrich-task']"))
            .find(candidate => candidate.dataset.taskId === taskId);
        button?.setAttribute("aria-busy", "true");
        if (button) button.disabled = true;
        this.#state?.setActiveCommand(`enrich-task ${taskId}`);
        try {
            const result = await this.#api.enrichBacklogTask(taskId);
            this.#state?.setLastResult(result);
            if (result.ok) await this.#loadBacklog(true);
        } finally {
            button?.removeAttribute("aria-busy");
            if (button) button.disabled = false;
        }
    }




    /**
     * Replace the current form description with a non-persistent model proposal.
     *
     * @returns {Promise<void>} Resolves after the proposal is rendered or the error is reported.
     */
    async #enrichTaskDraft(): Promise<void> {
        if (this.#draftEnrichmentController) {
            this.#draftEnrichmentController.abort();
            return;
        }
        const api = this.#api;
        const taskIdInput = this.querySelector<HTMLInputElement>("[data-role='modal-task-id']");
        const domainInput = this.querySelector<HTMLInputElement>("[data-role='modal-domain']");
        const titleInput = this.querySelector<HTMLInputElement>("[data-role='modal-title-input']");
        const descriptionInput = this.querySelector<HTMLTextAreaElement>("[data-role='modal-description']");
        const priorityInput = this.querySelector<HTMLSelectElement>("[data-role='modal-priority']");
        const button = this.querySelector<HTMLButtonElement>("[data-action='enrich-task-draft']");
        if (!api || !taskIdInput || !domainInput || !titleInput || !descriptionInput || !priorityInput || !button) return;
        const title = titleInput.value.trim();
        const description = descriptionInput.value.trim();
        if (!title || !description) {
            descriptionInput.setCustomValidity("Write a task description before enriching it.");
            descriptionInput.reportValidity();
            descriptionInput.setCustomValidity("");
            return;
        }
        const controller = new AbortController();
        this.#draftEnrichmentController = controller;
        this.#setDraftEnrichmentActive(true);
        this.#state?.setActiveCommand(`enrich-task-draft ${taskIdInput.value || "new"}`);
        try {
            const priority: BacklogTask["priority"] = priorityInput.value === "MEDIUM" || priorityInput.value === "LOW" ? priorityInput.value : "HIGH";
            const image = await this.#visualReferenceController.exportPng();
            const taskId = taskIdInput.value.trim();
            const result = await api.enrichBacklogDraft({
                ...(taskId ? { taskId } : {}),
                domain: domainInput.value.trim() || this.#selectedDomain || "Backlog",
                title,
                description,
                priority,
                image
            }, controller.signal);
            this.#state?.setLastResult(result);
            if (result.ok && result.data?.description) descriptionInput.value = result.data.description;
        } catch (error: unknown) {
            if (!(error instanceof DOMException && error.name === "AbortError")) throw error;
        } finally {
            if (this.#draftEnrichmentController === controller) this.#draftEnrichmentController = null;
            this.#setDraftEnrichmentActive(false);
        }
    }

    /**
     * Toggle the task editor between editable and cancellable enrichment states.
     * @param {boolean} active Whether enrichment currently owns and locks the draft.
     * @returns {void} Nothing; the editor DOM is updated synchronously.
     */
    #setDraftEnrichmentActive(active: boolean): void {
        const button = this.querySelector<HTMLButtonElement>("[data-action='enrich-task-draft']");
        const overlay = this.querySelector<HTMLElement>("[data-role='task-enrichment-overlay']");
        const controls = this.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>("[data-role='modal-title-input'], [data-role='modal-priority'], [data-role='modal-description']");
        controls.forEach(control => {
            control.disabled = active;
            control.setAttribute("aria-disabled", String(active));
        });
        this.querySelectorAll<HTMLButtonElement>("[data-action='open-visual-reference'], [data-action='close-modal'], [data-role='modal-submit-btn']").forEach(control => {
            control.disabled = active;
            control.setAttribute("aria-disabled", String(active));
        });
        if (button) {
            button.setAttribute("aria-busy", String(active));
            button.classList.toggle("is-pause", active);
            button.innerHTML = active ? `${icon("pause")}<span>Pause</span>` : `${icon("enrich")}<span>Enrich</span>`;
            button.title = active ? "Cancel task enrichment" : "Enrich this draft with profiles and visual context";
        }
        if (overlay) overlay.hidden = !active;
    }

    /**
     * Delete one task.
     *
     * @param {string} taskId Task id.
     * @param {string} status Current task state.
     * @returns {Promise<void>} Resolves after mutation.
     */
    async #deleteTask(taskId: string, status: BacklogTask["status"]): Promise<void> {
        if (!this.#api) return;
        const force = status !== "DONE";
        if (force && !window.confirm("This task is still in progress. Delete it anyway?")) {
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
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        const projector = this.#taskProjector();
        const domainTasks = projector.domainTasks();
        const visibleTasks = projector.visibleTasks();
        const pipSupported = this.#pipController.supported();
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
                                <span class="backlog-task-count" style="font-size: 13px; font-weight: normal; color: var(--text-muted);">(${visibleTasks.length} tasks)</span>
                            </strong>
                            <div class="backlog-header-actions" style="display: flex; gap: 8px; align-items: center;">
                                <details class="action-menu filter-menu backlog-filter-menu" ${this.#filtersOpen ? "open" : ""}>
                                    <summary class="icon-action" title="Filter tasks" aria-label="Filter tasks">
                                        ${icon("filter")}
                                        <span class="backlog-filter-count" ${projector.activeFilterCount() ? "" : "hidden"}>${projector.activeFilterCount()}</span>
                                    </summary>
                                    <div class="action-menu-panel filter-menu-panel">
                                        <fieldset class="checkbox-filter-group"><legend>Status</legend>
                                            ${BACKLOG_STATUS_FILTER_OPTIONS.map(([value, label]) => `<label><input type="checkbox" data-filter-kind="status" value="${value}" ${this.#statusFilter.has(value) ? "checked" : ""}><span>${label}</span></label>`).join("")}
                                        </fieldset>
                                        <fieldset class="checkbox-filter-group"><legend>Priority</legend>
                                            ${BACKLOG_PRIORITY_FILTER_OPTIONS.map(([value, label]) => `<label><input type="checkbox" data-filter-kind="priority" value="${value}" ${this.#priorityFilter.has(value) ? "checked" : ""}><span>${label}</span></label>`).join("")}
                                        </fieldset>
                                        <button data-action="clear-backlog-filters" class="ghost-action">${icon("close")}Clear filters</button>
                                    </div>
                                </details>
                                <button data-action="open-create-modal" class="ghost-action compact-action" style="font-size: 13px; height: 32px; display: inline-flex; align-items: center; gap: 6px;">${icon("plus")} Create task</button>
                                <button data-action="toggle-pip" class="ghost-action compact-action" style="font-size: 13px; height: 32px; display: inline-flex; align-items: center; gap: 6px;" ${pipSupported ? "" : "disabled"} title="${pipSupported ? "Open Picture-in-Picture window" : "Document Picture-in-Picture is unavailable in this browser"}">${icon("eye")} PIP view</button>
                            </div>
                        </div>
                        <div class="backlog-workspace scroll-area" style="padding: 14px;">
                            <div class="task-list">
                                ${renderBacklogTaskList(domainTasks, this.#selectedDomain, this.#tasksWithImages)}
                                <p class="empty-state backlog-filter-empty" hidden>No tasks match these filters.</p>
                            </div>
                        </div>
                    </main>
                </div>
            </section>
            ${renderBacklogDialogs()}
            ${renderDomainRenameDialog("backlog-domain-rename-dialog")}
        `;
        this.#bindEvents();
        this.#configureTree();
        this.#applyTaskFiltersToDom();
    }

    /**
     * Open or focus the native Backlog PiP surface through its lifecycle controller.
     * @returns {Promise<void>} A promise that resolves once the Picture-in-Picture window has been initiated.
     */
    async #openPipWindow(): Promise<void> {
        await this.#pipController.open({
            tasks: this.#tasks,
            onAddTask: task => this.#addTaskFromPip(task)
        });
    }

    /**
     * Persist one task draft submitted by the native PiP component.
     *
     * @param {BacklogPipCreateTaskInput} taskData Validated task fields and optional marked reference image.
     * @returns {Promise<{ ok: boolean; message: string; tasks?: never; } | { ok: boolean; tasks: BacklogPipTaskViewModel[]; message?: never; }>} PiP-local mutation result containing refreshed tasks on success.
     */
    async #addTaskFromPip(taskData: BacklogPipCreateTaskInput) {
        const domain = this.#selectedDomain || "Backlog";
        this.#state?.setActiveCommand(`add-task ${domain} "${taskData.title}"`);
        try {
            if (!this.#api) return { ok: false, message: "Backlog API is unavailable." };
            const result = await this.#api.updateBacklog({
                action: "add",
                domain,
                title: taskData.title,
                description: taskData.description,
                priority: taskData.priority,
                image: taskData.image
            });
            this.#state?.setLastResult(result);
            if (!result.ok) return { ok: false, message: result.error || result.stderr || "Could not create the task." };
            this.#selectedDomain = domain;
            await this.#loadBacklog(true);
            return { ok: true, tasks: this.#tasks };
        } catch (error) {
            console.error("Unable to add a task from Document PiP.", error);
            return { ok: false, message: "Could not create the task. Try again." };
        }
    }

    /**
     * Render domain tree.
     *
     * @returns {string} HTML.
     */
    #renderTree(): string {
        return `<brain-structure-tree data-role="backlog-tree"></brain-structure-tree>`;
    }

    /**
     * Configure the shared Backlog domain tree.
     *
     * @returns {void}
     */
    #configureTree(): void {
        const treeElement = this.querySelector("[data-role='backlog-tree']");
        if (!(treeElement instanceof StructureTree)) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#selectedDomain || BACKLOG_ROOT_PATH,
            expandedPaths: new Set([BACKLOG_ROOT_PATH, ...this.#expandedNodes]),
            toggleOnBranchSelect: true,
            title: "Backlog",
            toolbarActions: [
                { id: "new-domain", label: "New domain", icon: "plus" },
                { id: "refresh", label: "Refresh backlog", icon: "refresh" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "checkSquare",
            searchQuery: this.#filter,
            emptyText: "No backlog domains. Refresh to load tasks."
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onTreeAction(event));
        treeElement.addEventListener("brain-tree-search", event => {
            if (!(event instanceof CustomEvent) || typeof event.detail?.query !== "string") return;
            this.#filter = event.detail.query;
            this.#refreshTaskContent();
        });
    }

    /**
     * Convert the task domain tree into shared nodes.
     *
     * @returns {object[]} Tree node list.
     */
    #treeNodes(): StructureTreeNode[] {
        const projector = this.#taskProjector();
        const toNode = (node: BacklogDomainTreeNode): StructureTreeNode => {
            const children: StructureTreeNode[] = Array.from(node.children.values())
                .filter(child => projector.matchesNode(child))
                .sort((left, right) => left.label.localeCompare(right.label))
                .map(toNode);
            const count = this.#tasks.filter(task =>
                (task.domain === node.path || task.domain.startsWith(`${node.path}.`))
                && projector.matchesActiveFilters(task)
            ).length;
            return {
                id: node.path,
                path: node.path,
                label: node.label,
                count,
                children,
                actions: [{ id: "rename-domain", label: "Rename domain", icon: "edit" }]
            };
        };
        const domainNodes = Array.from(projector.buildTree().children.values())
            .filter(node => projector.matchesNode(node))
            .sort((left, right) => left.label.localeCompare(right.label))
            .map(toNode);
        return [{
            id: BACKLOG_ROOT_PATH,
            path: BACKLOG_ROOT_PATH,
            label: "Backlog",
            icon: "database",
            count: this.#tasks.filter(task => projector.matchesActiveFilters(task)).length,
            children: domainNodes,
            actions: [],
            folder: true,
        }];
    }

    /**
     * Select one Backlog domain without refetching its tree.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeSelected(event: Event): void {
        if (!(event instanceof CustomEvent)) return;
        if (event.detail.branch) {
            if (event.detail.expanded) {
                this.#expandedNodes.add(event.detail.path);
            } else {
                this.#expandedNodes.delete(event.detail.path);
            }
        }
        if (event.detail.branch && event.detail.clickedCaret) {
            return;
        }
        this.#selectedDomain = event.detail.path === BACKLOG_ROOT_PATH ? "" : event.detail.path;
        if (this.#selectedDomain) {
            this.#taskProjector().ancestorPaths(this.#selectedDomain).forEach(path => this.#expandedNodes.add(path));
        }
        this.#render();
    }

    /**
     * Handle global Backlog tree actions.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeToolbarAction(event: Event): void {
        if (!(event instanceof CustomEvent)) return;
        if (event.detail.action === "new-domain") {
            const newDomain = prompt("Enter the new domain name (for example, my.new.domain):");
            if (newDomain && newDomain.trim()) {
                const requestedDomain = newDomain.trim();
                const targetDomain = this.#selectedDomain && !requestedDomain.includes(".")
                    ? `${this.#selectedDomain}.${requestedDomain}`
                    : requestedDomain;
                const dialog = this.querySelector<HTMLDialogElement>("#backlog-modal");
                if (dialog) {
                    const taskIdInput = this.querySelector<HTMLInputElement>("[data-role='modal-task-id']");
                    const domInput = this.querySelector<HTMLInputElement>("[data-role='modal-domain']");
                    const titleInput = this.querySelector<HTMLInputElement>("[data-role='modal-title-input']");
                    const descriptionInput = this.querySelector<HTMLTextAreaElement>("[data-role='modal-description']");
                    const priorityInput = this.querySelector<HTMLSelectElement>("[data-role='modal-priority']");
                    if (!taskIdInput || !domInput || !titleInput || !descriptionInput || !priorityInput) return;
                    taskIdInput.value = "";
                    domInput.value = targetDomain;
                    domInput.removeAttribute("disabled");
                    titleInput.value = "";
                    descriptionInput.value = "";
                    priorityInput.value = "HIGH";
                    const imgInput = this.querySelector<HTMLInputElement>("[data-role='modal-image-file']");
                    if (imgInput) imgInput.value = "";
                    this.#visualReferenceController.reset();
                    const modalTitle = this.querySelector<HTMLElement>("[data-role='modal-title']");
                    const submitLabel = this.querySelector<HTMLElement>("[data-role='modal-submit-label']");
                    if (modalTitle) modalTitle.textContent = `Create task in ${newDomain.trim()}`;
                    if (submitLabel) submitLabel.textContent = "Create";
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
    async #onTreeAction(event: Event): Promise<void> {
        if (!(event instanceof CustomEvent)) return;
        const node = event.detail.node;
        if (!node?.path) {
            return;
        }
        if (event.detail.action === "rename-domain") {
            const target = await requestDomainRename(this, "backlog-domain-rename-dialog", node.path);
            if (!target || !this.#api) return;
            const result = await this.#api.renameBacklogDomain({ source: node.path, target });
            if (!result.ok) return;
            this.#expandedNodes = remapExpandedDomains(this.#expandedNodes, node.path, target);
            this.#selectedDomain = target;
            await this.#loadBacklog(true);
            return;
        }
        this.#selectedDomain = node.path;
        this.#taskProjector().ancestorPaths(node.path).forEach(path => this.#expandedNodes.add(path));
        this.#render();
    }

    /**
     * Create the pure task projector for the component's current selection and filters.
     *
     * @returns {BacklogTaskProjector} Stateless projection object scoped to the calling render or interaction.
     */
    #taskProjector(): BacklogTaskProjector {
        return new BacklogTaskProjector({
            tasks: this.#tasks,
            selectedDomain: this.#selectedDomain,
            filter: this.#contentFilter || this.#filter,
            statusFilter: this.#statusFilter,
            priorityFilter: this.#priorityFilter
        });
    }

    /**
     * Refresh the task panel after a local filter change without rebuilding
     * the structural tree or issuing a CLI request.
     *
     * @returns {void}
     */
    /**
     * Apply the shell's reactive query exclusively to content cards.
     * The domain tree and its own search input remain untouched.
     *
     * @param {string} query Debounced global-shell query, or empty text to clear it.
     * @returns {void}
     */
    applyReactiveContentFilter(query: string): void {
        this.#contentFilter = query.trim();
        this.#refreshTaskContent();
    }

    #refreshTaskContent() {
        const projector = this.#taskProjector();
        const visibleTasks = projector.visibleTasks();
        this.#applyTaskFiltersToDom();
        const countSpan = this.querySelector(".backlog-task-count");
        if (countSpan) {
            countSpan.textContent = `(${visibleTasks.length} tasks)`;
        }
        const filterCount = this.querySelector(".backlog-filter-count");
        if (filterCount) {
            const activeCount = projector.activeFilterCount();
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
        const projector = this.#taskProjector();
        const domainTasks = projector.domainTasks();
        const visibleIds = new Set(projector.visibleTasks().map(task => task.id));
        this.querySelectorAll("[data-task-row-id]").forEach(row => {
            row.toggleAttribute("hidden", !visibleIds.has(row.getAttribute("data-task-row-id") || ""));
        });
        this.querySelectorAll(".direct-tasks-section, .subdomain-group").forEach(group => {
            const hasVisibleRows = Array.from(group.querySelectorAll<HTMLElement>("[data-task-row-id]")).some(row => !row.hidden);
            group.toggleAttribute("hidden", !hasVisibleRows);
        });
        highlightRenderedContent(this, this.#contentFilter || this.#filter, "[data-task-row-id]:not([hidden])");
        const emptyState = this.querySelector(".backlog-filter-empty");
        if (emptyState) {
            emptyState.toggleAttribute("hidden", domainTasks.length === 0 || visibleIds.size > 0);
        }
    }

    /**
     * Bind DOM events.
     *
     * @returns {void}
     */
    #bindEvents(): void {
        this.querySelector("[data-action='refresh-backlog']")?.addEventListener("click", () => this.#loadBacklog(true));
        this.querySelector<HTMLDetailsElement>(".backlog-filter-menu")?.addEventListener("toggle", event => {
            if (event.currentTarget instanceof HTMLDetailsElement) this.#filtersOpen = event.currentTarget.open;
        });
        this.querySelectorAll<HTMLInputElement>("[data-filter-kind]").forEach(input => input.addEventListener("change", event => {
            if (!(event.currentTarget instanceof HTMLInputElement)) return;
            const target = event.currentTarget;
            if (target.dataset.filterKind === "status" && (target.value === "TODO" || target.value === "WORKING" || target.value === "DONE")) {
                if (target.checked) this.#statusFilter.add(target.value); else this.#statusFilter.delete(target.value);
            } else if (target.dataset.filterKind === "priority" && (target.value === "HIGH" || target.value === "MEDIUM" || target.value === "LOW")) {
                if (target.checked) this.#priorityFilter.add(target.value); else this.#priorityFilter.delete(target.value);
            }
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
            this.#taskProjector().ancestorPaths(path).forEach(ancestor => this.#expandedNodes.add(ancestor));
            if (isBranch && this.#expandedNodes.has(path)) {
                this.#expandedNodes.delete(path);
            } else {
                this.#expandedNodes.add(path);
            }
            this.#render();
        }));
        this.querySelectorAll<HTMLElement>("[data-action='set-task-status']").forEach(button => {
            button.addEventListener("click", () => {
                const status = button.dataset.taskStatus;
                if (status === "TODO" || status === "WORKING" || status === "DONE") this.#setTaskStatus(button.dataset.taskId ?? "", status);
            });
        });
        this.querySelectorAll<HTMLElement>("[data-action='enrich-task']").forEach(button => {
            button.addEventListener("click", () => this.#enrichTask(button.dataset.taskId ?? ""));
        });
        this.querySelector("[data-action='enrich-task-draft']")?.addEventListener("click", () => this.#enrichTaskDraft());


        this.querySelectorAll<HTMLElement>("[data-action='delete-task']").forEach(button => {
            button.addEventListener("click", () => {
                const status = button.dataset.taskStatus;
                if (status === "TODO" || status === "WORKING" || status === "DONE") this.#deleteTask(button.dataset.taskId ?? "", status);
            });
        });

        // Open Create Modal
        this.querySelector("[data-action='open-create-modal']")?.addEventListener("click", () => {
            const dialog = this.querySelector<HTMLDialogElement>("#backlog-modal");
            const taskIdInput = this.querySelector<HTMLInputElement>("[data-role='modal-task-id']");
            const domInput = this.querySelector<HTMLInputElement>("[data-role='modal-domain']");
            const titleInput = this.querySelector<HTMLInputElement>("[data-role='modal-title-input']");
            const descriptionInput = this.querySelector<HTMLTextAreaElement>("[data-role='modal-description']");
            const priorityInput = this.querySelector<HTMLSelectElement>("[data-role='modal-priority']");
            if (!dialog || !taskIdInput || !domInput || !titleInput || !descriptionInput || !priorityInput) return;
            taskIdInput.value = "";
            domInput.value = this.#selectedDomain;
            domInput.removeAttribute("disabled");
            titleInput.value = "";
            descriptionInput.value = "";
            priorityInput.value = "HIGH";
                const imgInput = this.querySelector<HTMLInputElement>("[data-role='modal-image-file']");
                if (imgInput) imgInput.value = "";
                this.#visualReferenceController.reset();
            const imgUploadZone = this.querySelector<HTMLElement>("[data-role='image-upload-zone']");
            if (imgUploadZone) {
                imgUploadZone.style.removeProperty("display");
            }

            const modalTitle = this.querySelector<HTMLElement>("[data-role='modal-title']");
            const submitLabel = this.querySelector<HTMLElement>("[data-role='modal-submit-label']");
            const statusIndicator = this.querySelector<HTMLElement>("[data-role='modal-status-indicator']");
            if (modalTitle) modalTitle.textContent = "Create task";
            if (submitLabel) submitLabel.textContent = "Create";
            if (statusIndicator) {
                statusIndicator.className = "task-status task-editor-status-indicator is-neutral";
                statusIndicator.innerHTML = icon("clock");
                statusIndicator.title = "New task";
            }

            dialog.showModal();
        });

        // Open read-only task viewer.
        this.querySelectorAll<HTMLElement>("[data-action='view-task']").forEach(button => {
            button.addEventListener("click", () => {
                const taskId = button.dataset.taskId ?? "";
                const task = this.#tasks.find(candidate => candidate.id === taskId);
                const dialog = this.querySelector<HTMLDialogElement>("#task-viewer-modal");
                const title = this.querySelector<HTMLElement>("[data-role='task-viewer-title']");
                const meta = this.querySelector<HTMLElement>("[data-role='task-viewer-meta']");
                const description = this.querySelector<HTMLElement>("[data-role='task-viewer-description']");
                const optionsPanel = this.querySelector<HTMLElement>("[data-role='task-viewer-options-panel']");
                const statusIndicator = this.querySelector<HTMLElement>("[data-role='task-viewer-status-indicator']");
                if (!task || !dialog || !title || !meta || !description || !optionsPanel || !statusIndicator) return;
                title.textContent = `${task.id} - ${task.title}`;
                meta.textContent = `${task.domain} ┬╖ ${task.priority} ┬╖ ${task.status}`;
                const statusIcon = task.status === "DONE" ? icon("checkSquare") : task.status === "WORKING" ? icon("pulse") : icon("clock");
                const statusClass = task.status === "DONE" ? "task-status-done" : task.status === "WORKING" ? "task-status-working" : `task-status-${task.priority.toLowerCase()}`;
                meta.innerHTML = `<span class="task-viewer-badge task-viewer-domain-badge">${icon("folder")}<span>${escapeHtml(task.domain)}</span></span><span class="task-viewer-badge task-viewer-priority-badge is-${task.priority.toLowerCase()}">${icon("pulse")}<span>${escapeHtml(task.priority)}</span></span><span class="task-viewer-badge task-viewer-state-badge is-${task.status.toLowerCase()}">${statusIcon}<span>${escapeHtml(task.status)}</span></span>`;
                statusIndicator.className = `task-status task-viewer-status-indicator ${statusClass}`;
                statusIndicator.innerHTML = statusIcon;
                statusIndicator.title = task.status;
                const statusOptions = task.status === "DONE"
                    ? `<button type="button" data-viewer-task-status="TODO">${icon("clock")}<span>Reopen</span></button>`
                    : task.status === "TODO"
                        ? `<button type="button" data-viewer-task-status="WORKING">${icon("pulse")}<span>Iniciar trabajo</span></button><button type="button" data-viewer-task-status="DONE">${icon("checkSquare")}<span>Mark done</span></button>`
                        : `<button type="button" data-viewer-task-status="DONE">${icon("checkSquare")}<span>Mark done</span></button><button type="button" data-viewer-task-status="TODO">${icon("clock")}<span>Pause (TODO)</span></button>`;
                optionsPanel.innerHTML = `<button type="button" data-viewer-task-action="edit">${icon("edit")}<span>Edit</span></button>${statusOptions}<button type="button" data-viewer-task-action="delete" class="danger-button">${icon("trash")}<span>Delete task</span></button>`;
                optionsPanel.querySelector<HTMLButtonElement>("[data-viewer-task-action='edit']")?.addEventListener("click", () => {
                    this.querySelector<HTMLButtonElement>(`.task-row [data-action='edit-task'][data-task-id='${task.id}']`)?.click();
                });
                optionsPanel.querySelectorAll<HTMLButtonElement>("[data-viewer-task-status]").forEach(action => {
                    action.addEventListener("click", () => {
                        const status = action.dataset.viewerTaskStatus;
                        if (status === "TODO" || status === "WORKING" || status === "DONE") {
                            dialog.close();
                            void this.#setTaskStatus(task.id, status);
                        }
                    });
                });
                optionsPanel.querySelector<HTMLButtonElement>("[data-viewer-task-action='delete']")?.addEventListener("click", () => {
                    dialog.close();
                    void this.#deleteTask(task.id, task.status);
                });
                const normalizedTaskId = task.id.replace(/^#/, "");
                description.innerHTML = renderMarkdown(viewableBacklogDescription(task.description, task.id, this.#tasksWithImages.includes(normalizedTaskId)));
                dialog.showModal();
            });
        });
        this.querySelectorAll("[data-action='close-task-viewer']").forEach(button => {
            button.addEventListener("click", () => this.querySelector<HTMLDialogElement>("#task-viewer-modal")?.close());
        });

        // Open Edit Modal
        this.querySelectorAll("[data-action='edit-task']").forEach(button => {
            button.addEventListener("click", () => {
                const taskId = button.getAttribute("data-task-id") || "";
                const task = this.#tasks.find(t => t.id === taskId);
                if (!task) return;
                this.querySelector<HTMLDialogElement>("#task-viewer-modal")?.close();
                const dialog = this.querySelector<HTMLDialogElement>("#backlog-modal");
                const taskIdInput = this.querySelector<HTMLInputElement>("[data-role='modal-task-id']");
                const domInput = this.querySelector<HTMLInputElement>("[data-role='modal-domain']");
                const titleInput = this.querySelector<HTMLInputElement>("[data-role='modal-title-input']");
                const descriptionInput = this.querySelector<HTMLTextAreaElement>("[data-role='modal-description']");
                const priorityInput = this.querySelector<HTMLSelectElement>("[data-role='modal-priority']");
                if (!dialog || !taskIdInput || !domInput || !titleInput || !descriptionInput || !priorityInput) return;
                taskIdInput.value = task.id;
                domInput.value = task.domain;
                domInput.setAttribute("disabled", "true");
                titleInput.value = task.title;
                const editableDescription = editableBacklogDescription(task.description, task.id);
                const normalizedTaskId = task.id.replace(/^#/, "");
                descriptionInput.value = this.#tasksWithImages.includes(normalizedTaskId) && !editableDescription.includes("{ref_image}")
                    ? `${editableDescription}\n\n{ref_image}`
                    : editableDescription;
                priorityInput.value = task.priority;

                const imgUploadZone = this.querySelector<HTMLElement>("[data-role='image-upload-zone']");
                if (imgUploadZone) {
                    imgUploadZone.style.removeProperty("display");
                }
            const imgInput = this.querySelector<HTMLInputElement>("[data-role='modal-image-file']");
            if (imgInput) imgInput.value = "";
            this.#visualReferenceController.reset();
                const imageTaskId = normalizedTaskId;
                if (this.#tasksWithImages.includes(imageTaskId)) {
                    const imageUrl = workspaceScopedUrl(`/api/backlog/image?taskId=${encodeURIComponent(imageTaskId)}`);
                    this.#visualReferenceController.displayImage(imageUrl);
                }

                const modalTitle = this.querySelector<HTMLElement>("[data-role='modal-title']");
                const submitLabel = this.querySelector<HTMLElement>("[data-role='modal-submit-label']");
                const statusIndicator = this.querySelector<HTMLElement>("[data-role='modal-status-indicator']");
                if (modalTitle) modalTitle.textContent = `Edit task #${task.id}`;
                if (submitLabel) submitLabel.textContent = "Save";
                if (statusIndicator) {
                    const statusIcon = task.status === "DONE" ? icon("checkSquare") : task.status === "WORKING" ? icon("pulse") : icon("clock");
                    const statusClass = task.status === "DONE" ? "task-status-done" : task.status === "WORKING" ? "task-status-working" : `task-status-${task.priority.toLowerCase()}`;
                    statusIndicator.className = `task-status task-editor-status-indicator ${statusClass}`;
                    statusIndicator.innerHTML = statusIcon;
                    statusIndicator.title = task.status;
                }

                dialog.showModal();
            });
        });

        // Close Modal
        this.querySelectorAll("[data-action='close-modal']").forEach(btn => {
            btn.addEventListener("click", () => {
                this.querySelector<HTMLDialogElement>("#backlog-modal")?.close();
            });
        });

        // Open & Close Visual Reference Modal
        this.querySelectorAll("[data-action='open-visual-reference']").forEach(button => {
            button.addEventListener("click", () => this.querySelector<HTMLDialogElement>("#visual-reference-modal")?.showModal());
        });
        this.querySelectorAll("[data-action='close-visual-reference']").forEach(btn => {
            btn.addEventListener("click", () => {
                this.querySelector<HTMLDialogElement>("#visual-reference-modal")?.close();
            });
        });

        // Image Viewer Modal Listeners
        this.querySelectorAll("[data-action='view-image']").forEach(thumb => {
            thumb.addEventListener("click", () => {
                const taskId = thumb.getAttribute("data-task-id") || "";
                const modal = this.querySelector<HTMLDialogElement>("#image-viewer-modal");
                const img = this.querySelector<HTMLImageElement>("[data-role='viewer-img']");
                if (modal && img) {
                    img.src = workspaceScopedUrl(`/api/backlog/image?taskId=${encodeURIComponent(taskId)}`);
                    modal.showModal();
                }
            });
        });
        this.querySelector("[data-action='close-image-viewer']")?.addEventListener("click", () => {
            this.querySelector<HTMLDialogElement>("#image-viewer-modal")?.close();
        });

        // Paste Image from Clipboard Listener
        const descInput = this.querySelector<HTMLTextAreaElement>("[data-role='modal-description']");
        descInput?.addEventListener("paste", (event: ClipboardEvent) => {
            const items = event.clipboardData?.items;
            if (!items) return;
            for (let index = 0; index < items.length; index += 1) {
                const item = items[index];
                if (!item) continue;
                if (item.type.startsWith("image/")) {
                    event.preventDefault();
                    const file = item.getAsFile();
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = () => {
                            const visualReferenceDialog = this.querySelector("#visual-reference-modal");
                            if (visualReferenceDialog instanceof HTMLDialogElement && !visualReferenceDialog.open) {
                                visualReferenceDialog.showModal();
                            }
                            const result = reader.result;
                            if (typeof result !== "string") return;
                            this.#visualReferenceController.displayImage(result);
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
        this.querySelector<HTMLFormElement>("[data-role='modal-form']")?.addEventListener("submit", async event => {
            event.preventDefault();
            const dialog = this.querySelector<HTMLDialogElement>("#backlog-modal");
            const taskIdInput = this.querySelector<HTMLInputElement>("[data-role='modal-task-id']");
            const domainInput = this.querySelector<HTMLInputElement>("[data-role='modal-domain']");
            const titleInput = this.querySelector<HTMLInputElement>("[data-role='modal-title-input']");
            const descriptionInput = this.querySelector<HTMLTextAreaElement>("[data-role='modal-description']");
            const priorityInput = this.querySelector<HTMLSelectElement>("[data-role='modal-priority']");
            const api = this.#api;
            if (!dialog || !taskIdInput || !domainInput || !titleInput || !descriptionInput || !priorityInput || !api) return;
            const taskId = taskIdInput.value;
            const domain = domainInput.value.trim() || this.#selectedDomain || "Backlog";
            const title = titleInput.value.trim();
            const description = descriptionInput.value.trim();
            const priority: BacklogTask["priority"] = priorityInput.value === "MEDIUM" || priorityInput.value === "LOW" ? priorityInput.value : "HIGH";
            dialog.close();
            if (taskId) {
                this.#state?.setActiveCommand(`edit-task ${taskId}`);
                let base64Image: string | null = null;
                try {
                    base64Image = await this.#visualReferenceController.exportPng();
                } catch (e) {
                    console.error("Error baking marked image:", e);
                }
                const result = await api.updateBacklog({
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
                let base64Image: string | null = null;
                try {
                    base64Image = await this.#visualReferenceController.exportPng();
                } catch (e) {
                    console.error("Error baking marked image:", e);
                }
                const result = await api.updateBacklog({
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
        const previewArea = this.querySelector<HTMLElement>("[data-role='image-preview-area']");
        const fileInput = this.querySelector<HTMLInputElement>("[data-role='modal-image-file']");
        previewArea?.addEventListener("click", event => {
            if (previewArea.classList.contains("has-image") || fileInput?.disabled) return;
            if (!(event.target instanceof Element)) return;
            if (!event.target.closest(".upload-placeholder") && event.target !== previewArea) return;
            fileInput?.click();
        });
        fileInput?.addEventListener("change", e => {
            const file = e.currentTarget instanceof HTMLInputElement ? e.currentTarget.files?.[0] : undefined;
            if (file) {
                const reader = new FileReader();
                reader.onload = () => {
                    const result = reader.result;
                    if (typeof result === "string") this.#visualReferenceController.displayImage(result);
                };
                reader.readAsDataURL(file);
            }
        });

        // Real Document PiP
        this.querySelector("[data-action='toggle-pip']")?.addEventListener("click", () => {
            this.#openPipWindow();
        });
        this.querySelector("[data-action='capture-screen']")?.addEventListener("click", () => {
            this.#visualReferenceController.captureScreen();
        });
    }
}

/**
 * Preserve expanded tree state after moving one complete domain subtree.
 *
 * @param {Set<string>} expanded Existing expanded domain paths.
 * @param {string} source Previous subtree root.
 * @param {string} target Replacement subtree root.
 * @returns {Set<string>} Expanded paths rewritten to the new canonical prefix.
 */
function remapExpandedDomains(expanded: Set<string>, source: string, target: string): Set<string> {
    return new Set(Array.from(expanded, path => {
        if (path === source) return target;
        return path.startsWith(`${source}.`) ? `${target}${path.slice(source.length)}` : path;
    }));
}

customElements.define(BacklogView.selector, BacklogView);
