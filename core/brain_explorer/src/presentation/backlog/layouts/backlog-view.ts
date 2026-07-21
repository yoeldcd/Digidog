/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import { StructureTree } from "../../shared/components/structure-tree.ts";
import type { BacklogAction } from "../../../application/backlog/dtos/requests/backlog-mutation-request.ts";
import type { BacklogTask } from "../../../application/backlog/dtos/responses/backlog-response.ts";
import { BacklogPipController } from "../controllers/backlog-pip-controller.ts";
import { BacklogVisualReferenceController } from "../controllers/backlog-visual-reference-controller.ts";
import { BACKLOG_PRIORITY_FILTER_OPTIONS, BACKLOG_STATUS_FILTER_OPTIONS } from "../view_models/backlog-view-model.ts";
import type { BacklogDomainTreeNode } from "../view_models/backlog-view-model.ts";
import type { BacklogPipCreateTaskInput, BacklogPipTaskViewModel } from "../view_models/backlog-pip-view-model.ts";
import type { ComponentContext } from "../../shared/view_models/component-context-view-model.ts";
import type { StructureTreeNode } from "../../shared/view_models/structure-tree-view-model.ts";
import { BacklogTaskProjector } from "../projectors/backlog-task-projector.ts";
import { renderBacklogDialogs, renderBacklogTaskList } from "../renderers/backlog-layout-renderer.ts";

void StructureTree;

/**
 * BacklogView renders workspace tasks as a domain tree and focused task board.
 */
export class BacklogView extends HTMLElement {
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
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context: ComponentContext) {
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
        this.#selectedDomain = this.#selectedDomain || "";
        if (this.#selectedDomain) {
            this.#taskProjector().ancestorPaths(this.#selectedDomain).forEach(path => this.#expandedNodes.add(path));
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
            selectedPath: this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
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
                actions: []
            };
        };
        return Array.from(projector.buildTree().children.values())
            .filter(node => projector.matchesNode(node))
            .sort((left, right) => left.label.localeCompare(right.label))
            .map(toNode);
    }

    /**
     * Select one Backlog domain without refetching its tree.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeSelected(event: Event): void {
        if (!(event instanceof CustomEvent)) return;
        if (event.detail.branch && event.detail.clickedCaret) {
            return;
        }
        this.#selectedDomain = event.detail.path;
        this.#taskProjector().ancestorPaths(event.detail.path).forEach(path => this.#expandedNodes.add(path));
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
                    const submitButton = this.querySelector<HTMLButtonElement>("[data-role='modal-submit-btn']");
                    if (modalTitle) modalTitle.textContent = `Create task in ${newDomain.trim()}`;
                    if (submitButton) submitButton.textContent = "Create";
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
    #onTreeAction(event: Event): void {
        if (!(event instanceof CustomEvent)) return;
        const node = event.detail.node;
        if (!node?.path) {
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
            filter: this.#filter,
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
            const submitButton = this.querySelector<HTMLButtonElement>("[data-role='modal-submit-btn']");
            if (modalTitle) modalTitle.textContent = "Create task";
            if (submitButton) submitButton.textContent = "Create";
            dialog.showModal();
        });

        // Open Edit Modal
        this.querySelectorAll("[data-action='edit-task']").forEach(button => {
            button.addEventListener("click", () => {
                const taskId = button.getAttribute("data-task-id") || "";
                const task = this.#tasks.find(t => t.id === taskId);
                if (!task) return;
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
                descriptionInput.value = task.description;
                priorityInput.value = task.priority;

                const imgUploadZone = this.querySelector<HTMLElement>("[data-role='image-upload-zone']");
                if (imgUploadZone) {
                    imgUploadZone.style.removeProperty("display");
                }
            const imgInput = this.querySelector<HTMLInputElement>("[data-role='modal-image-file']");
            if (imgInput) imgInput.value = "";
            this.#visualReferenceController.reset();
                const imageTaskId = task.id.replace(/^#/, "");
                if (this.#tasksWithImages.includes(imageTaskId)) {
                    this.#visualReferenceController.displayImage(`/api/backlog/image?taskId=${encodeURIComponent(imageTaskId)}`);
                }

                const modalTitle = this.querySelector<HTMLElement>("[data-role='modal-title']");
                const submitButton = this.querySelector<HTMLButtonElement>("[data-role='modal-submit-btn']");
                if (modalTitle) modalTitle.textContent = `Edit task #${task.id}`;
                if (submitButton) submitButton.textContent = "Save";
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
        this.querySelector("[data-action='open-visual-reference']")?.addEventListener("click", () => {
            this.querySelector<HTMLDialogElement>("#visual-reference-modal")?.showModal();
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
                    img.src = `/api/backlog/image?taskId=${taskId}`;
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

customElements.define(BacklogView.selector, BacklogView);
