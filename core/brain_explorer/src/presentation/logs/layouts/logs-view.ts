/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml, optionTags, renderMarkdown } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import { StructureTree } from "../../shared/components/structure-tree.ts";
import { logsRouteTarget } from "../validators/logs-route-target.ts";
import { visibleLogEntries } from "../formatters/log-entry-parser.ts";
import { projectLogDateTree } from "../projectors/log-date-tree-projector.ts";
import { logDateTreeSelection, treeDetailNode } from "../validators/log-date-tree-entry.ts";
import { treeSelectDetail } from "../../shared/view_models/structure-tree-view-model.ts";
import type { LogEntryPayload } from "../../../application/logs/dtos/responses/logs-response.ts";
import type { ComponentContext } from "../../shared/view_models/component-context-view-model.ts";
import type {
    LogDomainRecord,
    LogDomainTreeNode,
    LogsRouteTarget,
    LogsSortOrder,
    LogsTreeMode,
    ParsedLogEntryViewModel,
} from "../view_models/logs-view-model.ts";
import type { StructureTreeNode } from "../../shared/view_models/structure-tree-view-model.ts";

void StructureTree;

/**
 * LogsView renders log domains as a structural tree plus one focused content pane.
 */
export class LogsView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the logs view component in the DOM.
     * @returns {string} The string identifier 'brain-logs-view'.
     */
    static get selector(): string {
        return "brain-logs-view";
    }

    /**
     * Holds a reference to the component's API context for accessing shared services and state, defaulting to null.
     *
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/infrastructure/shared/http/clients/brain-api-client").BrainApiClient | null}
     */
    #api: ComponentContext["api"] | null = null;
    /**
     * Holds the internal state of the component context or remains null if the context is not yet initialized.
     *
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/presentation/shell/state/app-state").AppState | null}
     */
    #state: ComponentContext["state"] | null = null;
    /**
     * Maintains a collection of log entry payloads for indexing within the logs view.
     *
     * @type {LogEntryPayload[]}
     */
    #indexEntries: LogEntryPayload[] = [];
    /**
     * Maintains a private collection of log entry payloads for the view's state.
     *
     * @type {LogEntryPayload[]}
     */
    #logEntries: LogEntryPayload[] = [];
    /**
     * Stores the identifier of the currently selected domain within the logs view state.
     *
     * @type {string}
     */
    #selectedDomain = "";
    /**
     * Maintains the current text filter string used to narrow the displayed log entries.
     *
     * @type {string}
     */
    #filter = "";
    /**
     * Stores the starting boundary or source identifier for filtering log entries.
     *
     * @type {string}
     */
    #from = "";
    /**
     * Stores the destination target identifier for log filtering or navigation.
     *
     * @type {string}
     */
    #to = "";
    /**
     * Stores the starting hour boundary for filtering or displaying log entries.
     *
     * @type {string}
     */
    #hourFrom = "";
    /**
     * Stores the upper bound hour limit for filtering log entries.
     *
     * @type {string}
     */
    #hourTo = "";
    /**
     * Maintains the current sorting direction for the logs display, defaulting to descending order.
     *
     * @type {LogsSortOrder}
     */
    #sortOrder: LogsSortOrder = "desc";
    /**
     * Maintains the current structural visualization mode for the logs tree, defaulting to domain-based grouping.
     *
     * @type {LogsTreeMode}
     */
    #treeMode: LogsTreeMode = "domain";
    /**
     * Maintains the current file system or URI path associated with the selected date for log retrieval.
     *
     * @type {string}
     */
    #selectedDatePath = "";
    /**
     * Tracks the visibility state of the logs filter interface.
     *
     * @type {boolean}
     */
    #filtersOpen = false;
    /**
     * Maintains a set of unique identifiers representing the currently expanded nodes within the logs view hierarchy.
     *
     * @type {Set<string>}
     */
    #expandedNodes = new Set<string>();
    /**
     * Stores a reference to a pending navigation target within the logs view, or null if no target is queued.
     *
     * @type {LogsRouteTarget | null}
     */
    #pendingTarget: LogsRouteTarget | null = null;
    /**
     * Maintains a private collection of image source URLs associated with the logs.
     *
     * @type {string[]}
     */
    #logsWithImages: string[] = [];
    /**
     * Stores the numeric identifier of the active polling timer used to trigger log refreshes.
     *
     * @type {number | null}
     */
    #refreshTimer: number | null = null;
    /**
     * Tracks whether a log refresh operation is currently in progress to prevent concurrent execution.
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
        this.#pendingTarget = logsRouteTarget(this.#state.consumeRouteTarget("logs")) || this.#pendingTarget;
        this.#loadIndex();
    }

    /**
     * Initialize DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
        this.#startSilentRefresh();
    }

    /**
     * Stop background work when the Logs route is unmounted.
     */
    disconnectedCallback() {
        if (this.#refreshTimer !== null) window.clearTimeout(this.#refreshTimer);
        this.#refreshTimer = null;
    }

    /**
     * Start a single view-owned silent refresh cycle.
     */
    #startSilentRefresh() {
        if (this.#refreshTimer) {
            return;
        }
        this.#scheduleSilentRefresh();
    }

    /**
     * Schedule the next cycle one minute after the previous one completed.
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
     * Refresh the index and reload focused content only after an index change.
     */
    async #refreshSilently() {
        if (!this.#api || this.#refreshInFlight || document.hidden) {
            return;
        }
        this.#refreshInFlight = true;
        try {
            const indexResult = await this.#api.logIndex({}, { forceRefresh: true, silent: true });
            const nextIndexEntries = indexResult.data?.entries || [];
            if (JSON.stringify(nextIndexEntries) === JSON.stringify(this.#indexEntries)) {
                return;
            }
            this.#indexEntries = nextIndexEntries;
            if (!this.#logEntries.length || !this.#selectedDomain) {
                this.#state?.setLastResult(indexResult);
                this.#render();
                return;
            }
            const logsResult = await this.#api.logs({
                domain: this.#selectedDomain,
                date: this.#from && this.#from === this.#to ? this.#from : "",
                time: this.#hourFrom && this.#hourFrom === this.#hourTo ? this.#hourFrom : "",
                from: this.#from,
                to: this.#to
            }, { forceRefresh: true, silent: true });
            const nextLogEntries = logsResult.data?.entries || [];
            const nextImages = logsResult.hasImages || [];
            this.#state?.setLastResult(logsResult);
            this.#logEntries = nextLogEntries;
            this.#logsWithImages = nextImages;
            this.#render();
        } finally {
            this.#refreshInFlight = false;
            this.#scheduleSilentRefresh();
        }
    }

    /**
     * Load the log domain index.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadIndex(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        const result = await this.#api.logIndex({}, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#indexEntries = result.data?.entries || [];
        const domains = this.#domains();
        this.#selectedDomain = this.#selectedDomain || domains[0]?.path || "";
        if (this.#selectedDomain) {
            this.#expandAncestors(this.#selectedDomain);
        }
        if (await this.#applyPendingTarget()) {
            return;
        }
        this.#render();
    }

    /**
     * Apply one pending SPA target and load the matching log entry range.
     *
     * @returns {Promise<boolean>} True when a target was consumed.
     */
    async #applyPendingTarget() {
        const target = this.#pendingTarget || logsRouteTarget(this.#state?.consumeRouteTarget("logs") ?? null);
        this.#pendingTarget = null;
        if (!target) {
            return false;
        }
        this.#selectedDomain = target.domain || this.#selectedDomain;
        this.#from = target.from || target.date || this.#from;
        this.#to = target.to || target.date || this.#to || this.#from;
        this.#hourFrom = target.hourFrom || target.time || this.#hourFrom;
        this.#hourTo = target.hourTo || target.time || this.#hourTo;
        this.#sortOrder = target.sortOrder || "desc";
        this.#expandAncestors(this.#selectedDomain);
        await this.#loadLogs(true, false);
        return true;
    }

    /**
     * Load logs for the selected domain and filters.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     *
     * @param {boolean} readControls Specifies whether to synchronize the current filter values from the UI controls before initiating the request.
     */
    async #loadLogs(forceRefresh = false, readControls = true) {
        if (!this.#api) {
            return;
        }
        if (readControls) {
            this.#readFilters();
        }
        const result = await this.#api.logs({
            domain: this.#selectedDomain,
            date: this.#from && this.#from === this.#to ? this.#from : "",
            time: this.#hourFrom && this.#hourFrom === this.#hourTo ? this.#hourFrom : "",
            from: this.#from,
            to: this.#to
        }, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#logsWithImages = result.hasImages || [];
        this.#logEntries = result.data?.entries || [];
        this.#render();
    }

    /**
     * Read compact filter controls.
     *
     * @returns {void}
     */
    #readFilters(): void {
        this.#from = this.querySelector<HTMLInputElement>("[data-role='log-from']")?.value.trim() || "";
        this.#to = this.querySelector<HTMLInputElement>("[data-role='log-to']")?.value.trim() || "";
        this.#hourFrom = this.querySelector<HTMLInputElement>("[data-role='log-hour-from']")?.value.trim() || "";
        this.#hourTo = this.querySelector<HTMLInputElement>("[data-role='log-hour-to']")?.value.trim() || "";
        const order = this.querySelector<HTMLSelectElement>("[data-role='log-order']")?.value;
        if (order === "asc" || order === "desc") this.#sortOrder = order;
    }

    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        const entries = this.#visibleLogEntries();
        const selectedRecord = this.#recordForPath(this.#selectedDomain);
        this.innerHTML = `
            <section class="page-surface logs-console">
                <div class="structure-layout logs-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.#renderTree()}
                        </div>
                    </aside>
                    <main class="structure-content">
                        <div class="content-head logs-head">
                            <strong>${escapeHtml(this.#selectedDomain || "Log index")}</strong>
                            <span>${escapeHtml(this.#logEntries.length ? `${entries.length} entries` : (selectedRecord?.date ? "Indexed entry" : "Select a domain"))}</span>
                            <details class="action-menu filter-menu" ${this.#filtersOpen ? "open" : ""}>
                                <summary class="compact-action">${icon("filter")}<span>Filters</span></summary>
                                <div class="action-menu-panel filter-menu-panel">
                                    <label><span>Desde</span><input data-role="log-from" value="${escapeHtml(this.#from)}" placeholder="DD-MM-YYYY"></label>
                                    <label><span>Hasta</span><input data-role="log-to" value="${escapeHtml(this.#to)}" placeholder="DD-MM-YYYY"></label>
                                    <label><span>Hora inicio</span><input data-role="log-hour-from" type="time" value="${escapeHtml(this.#hourFrom)}"></label>
                                    <label><span>Hora fin</span><input data-role="log-hour-to" type="time" value="${escapeHtml(this.#hourTo)}"></label>
                                    <label><span>Orden</span><select data-role="log-order">${optionTags(["desc", "asc"], this.#sortOrder)}</select></label>
                                    <div class="filter-menu-actions">
                                        <button data-action="clear-log-filters" class="ghost-action">${icon("filter")}Clear</button>
                                        <button data-action="load-logs" class="primary-action">${icon("search")}Aplicar</button>
                                    </div>
                                </div>
                            </details>
                        </div>
                        <div class="log-output log-card-list scroll-area">
                            ${this.#logEntries.length ? this.#renderLogEntries(entries) : `<p class="empty-state">Select a domain and load its history.</p>`}
                        </div>
                    </main>
                </div>
            </section>
        `;
        this.#bindEvents();
        this.#configureTree();
    }

    /**
     * Render parsed log entries as operational cards.
     *
     * @param {object[]} entries Visible entries.
     * @returns {string} HTML.
     */
    #renderLogEntries(entries: ParsedLogEntryViewModel[]): string {
        if (!entries.length) {
            return `<p class="empty-state">No entries match these filters.</p>`;
        }
        return entries.map(entry => `
            <details class="log-entry-card">
                <summary class="log-entry-summary">
                    <time class="log-date-badge">
                        <strong>${escapeHtml(entry.date)}</strong>
                        <span>${escapeHtml(entry.time)}</span>
                    </time>
                    <span class="log-entry-heading">
                        <strong>${escapeHtml(entry.title)}</strong>
                        <span class="log-entry-tags">
                            <span>${escapeHtml(entry.domain || this.#selectedDomain || "logs")}</span>
                            <span>${escapeHtml(entry.type || "log")}</span>
                            <span>${escapeHtml(entry.changeType || "registro")}</span>
                        </span>
                    </span>
                    <span class="log-entry-chevron">${icon("chevronDown")}</span>
                </summary>
                <div class="log-entry-body">
                    ${entry.why ? `<section><h2>Why</h2><div>${renderMarkdown(entry.why)}</div></section>` : ""}
                    ${entry.description ? `<section><h2>Description</h2><div>${renderMarkdown(entry.description)}</div></section>` : ""}
                    ${entry.impact ? `<section><h2>Impact</h2><div>${renderMarkdown(entry.impact)}</div></section>` : ""}
                    ${this.#renderPictures(entry.pictures)}
                </div>
            </details>
        `).join("");
    }

    /**
     * Render image attachments referenced by one log entry.
     *
     * @param {string[]} pictures Safe workspace picture file names.
     * @returns {string} Attachment gallery HTML.
     */
    #renderPictures(pictures: string[] = []): string {
        if (!pictures.length) {
            return "";
        }
        return `
            <div class="log-entry-media" aria-label="Attached images">
                ${pictures.map(name => {
                    const source = `/api/logs/image?name=${encodeURIComponent(name)}`;
                    return `<a href="${source}" target="_blank" rel="noopener" title="Open attached image"><img src="${source}" alt="Attached image ${escapeHtml(name)}"></a>`;
                }).join("")}
            </div>
        `;
    }

    /**
     * Parse, sort, and filter log entries.
     *
     * @returns {object[]} Visible entries.
     */
    #visibleLogEntries(): ParsedLogEntryViewModel[] {
        return visibleLogEntries({
            entries: this.#logEntries,
            selectedDomain: this.#selectedDomain,
            hourFrom: this.#hourFrom,
            hourTo: this.#hourTo,
            sortOrder: this.#sortOrder,
            logsWithImages: this.#logsWithImages
        });
    }

    /**
     * Render log domains as a collapsible tree.
     *
     * @returns {string} Tree HTML.
     */
    #renderTree(): string {
        return `<brain-structure-tree data-role="logs-tree"></brain-structure-tree>`;
    }

    /**
     * Render one log tree node.
     *
     * @param {object} node Tree node.
     * @param {number} depth Tree depth.
     * @returns {string} Node HTML.
     */
    #renderTreeNode(node: LogDomainTreeNode, depth: number): string {
        const children = Array.from(node.children.values()).sort((left, right) => left.label.localeCompare(right.label));
        const hasChildren = children.length > 0;
        const isOpen = this.#expandedNodes.has(node.path);
        const isActive = node.targetPath === this.#selectedDomain;
        if (!this.#matchesTree(node)) {
            return "";
        }
        return `
            <div class="tree-node-wrap">
                <button class="tree-node ${isActive ? "is-active" : ""}" style="--tree-depth:${depth}" data-node-path="${escapeHtml(node.targetPath)}" data-node-branch="${hasChildren ? "true" : "false"}">
                    <span class="tree-caret">${hasChildren ? icon(isOpen ? "chevronDown" : "chevronRight") : ""}</span>
                    ${icon(hasChildren ? "folder" : "document")}
                    <span>${escapeHtml(node.label)}</span>
                    ${node.command ? `<small>${escapeHtml(node.command)}</small>` : ""}
                </button>
                ${hasChildren ? `<div class="tree-children" ${isOpen ? "" : "hidden"}>${children.map(child => this.#renderTreeNode(child, depth + 1)).join("")}</div>` : ""}
            </div>
        `;
    }

    /**
     * Configure the shared tree with Log-specific toolbar and node actions.
     *
     * @returns {void}
     */
    #configureTree(): void {
        const treeElement = this.querySelector("[data-role='logs-tree']");
        if (!(treeElement instanceof StructureTree)) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#treeMode === "date" ? this.#selectedDatePath : this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
            toggleOnBranchSelect: true,
            title: "Logs",
            toolbarActions: [
                { id: "tree-domain", label: "Group by domain", icon: "folder", active: this.#treeMode === "domain" },
                { id: "tree-date", label: "Group by date", icon: "clock", active: this.#treeMode === "date" },
                { id: "refresh-index", label: "Refresh index", icon: "refresh" }
            ],
            sortDirection: this.#treeMode === "date" ? "desc" : "asc",
            defaultBranchIcon: "folder",
            defaultLeafIcon: "terminal",
            searchQuery: this.#filter,
            emptyText: "No index loaded. Refresh to browse logs."
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onTreeAction(event));
        treeElement.addEventListener("brain-tree-search", event => {
            if (!(event instanceof CustomEvent) || typeof event.detail?.query !== "string") return;
            this.#filter = event.detail.query;
            const entries = this.#visibleLogEntries();
            const selectedRecord = this.#recordForPath(this.#selectedDomain);
            const countSpan = this.querySelector(".logs-head span");
            if (countSpan) {
                countSpan.textContent = this.#logEntries.length ? `${entries.length} entries` : (selectedRecord?.date ? "Indexed entry" : "Select a domain");
            }
            const logOutput = this.querySelector(".log-output");
            if (logOutput) {
                logOutput.innerHTML = this.#logEntries.length ? this.#renderLogEntries(entries) : `<p class="empty-state">Select a domain and load its history.</p>`;
            }
        });
    }

    /**
     * Convert the parsed log index to shared tree nodes.
     *
     * @returns {object[]} Tree node list.
     */
    #treeNodes(): StructureTreeNode[] {
        if (this.#treeMode === "date") {
            return this.#dateTreeNodes();
        }
        const toNode = (node: LogDomainTreeNode): StructureTreeNode => {
            const children: StructureTreeNode[] = Array.from(node.children.values())
                .filter(child => this.#matchesTree(child))
                .sort((left, right) => left.label.localeCompare(right.label))
                .map(toNode);
            const isEntry = node.leaf === true;
            return {
                id: node.path,
                path: node.targetPath,
                label: isEntry ? node.label : node.label,
                timestamp: isEntry ? [node.date, node.time].filter(Boolean).join(" ") : "",
                detail: isEntry ? node.targetPath : "",
                presentation: isEntry ? "log" : "default",
                ...(!isEntry ? { count: this.#countTreeEntries(node) } : {}),
                children,
                actions: []
            };
        };
        return Array.from(this.#buildTree().children.values())
            .filter(node => this.#matchesTree(node))
            .sort((left, right) => left.label.localeCompare(right.label))
            .map(toNode);
    }

    /**
     * Group the complete log index into year, month, day, and entry nodes.
     *
     * @returns {object[]} Shared tree nodes ordered from newest to oldest.
     */
    #dateTreeNodes(): StructureTreeNode[] {
        return projectLogDateTree(this.#indexEntries);
    }

    /**
     * Count terminal records below one parsed tree node.
     *
     * @param {object} node Parsed node.
     * @returns {number} Descendant entry count.
     */
    #countTreeEntries(node: LogDomainTreeNode): number {
        return this.#indexEntries.filter(entry => {
            const domain = String(entry.domain || "");
            return domain === node.path || domain.startsWith(`${node.path}.`);
        }).length;
    }

    /**
     * Handle selection emitted by the shared tree.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {Promise<void>} Resolves after a selected domain loads.
     */
    async #onTreeSelected(event: Event): Promise<void> {
        if (!(event instanceof CustomEvent)) return;
        const selection = treeSelectDetail(event.detail);
        if (!selection || selection.branch) {
            return;
        }
        const dateNode = logDateTreeSelection(treeDetailNode(event.detail));
        if (this.#treeMode === "date" && dateNode) {
            this.#selectedDatePath = selection.path;
            this.#selectedDomain = dateNode.domain;
            this.#from = dateNode.date;
            this.#to = dateNode.date;
            this.#hourFrom = dateNode.time;
            this.#hourTo = dateNode.time;
            await this.#loadLogs(true, false);
            return;
        }
        const alreadySelected = selection.path === this.#selectedDomain;
        this.#selectedDomain = selection.path;
        this.#expandAncestors(selection.path);
        const record = this.#recordForPath(selection.path);
        if (record?.date) {
            this.#from = record.date;
            this.#to = record.date;
            this.#hourFrom = record.time || "";
            this.#hourTo = record.time || "";
        }
        if (alreadySelected && this.#logEntries.length) {
            this.#render();
            return;
        }
        await this.#loadLogs(true, !record?.date);
    }

    /**
     * Handle a Logs tree toolbar action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeToolbarAction(event: Event): void {
        if (!(event instanceof CustomEvent)) return;
        if (event.detail.action === "tree-domain" || event.detail.action === "tree-date") {
            const nextMode = event.detail.action === "tree-date" ? "date" : "domain";
            if (nextMode === this.#treeMode) {
                return;
            }
            this.#treeMode = nextMode;
            this.#expandedNodes.clear();
            this.#render();
            return;
        }
        if (event.detail.action === "refresh-index") {
            this.#loadIndex(true);
        }
    }

    /**
     * Handle a contextual action for one Logs tree node.
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
        const record = this.#recordForPath(node.path);
        if (record?.date) {
            this.#from = record.date;
            this.#to = record.date;
            this.#hourFrom = record.time || "";
            this.#hourTo = record.time || "";
        }
        this.#loadLogs(true, !record?.date);
    }

    /**
     * Parse log index text into domain records.
     *
     * @returns {object[]} Log domain records.
     */
    #domains(): LogDomainRecord[] {
        const records: LogDomainRecord[] = [];
        for (const entry of this.#indexEntries) {
            const domain = String(entry.domain || "");
            const parts = domain.split(".").filter(Boolean);
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                const terminal = index === parts.length - 1;
                const [date = "", ...timeParts] = String(entry.timestamp || "").split(" ");
                const time = timeParts.join(" ");
                records.push({
                    path,
                    label: terminal ? (entry.title || part) : part,
                    command: terminal ? `read-log -d ${date} --time ${time}` : "",
                    date: terminal ? date : "",
                    time: terminal ? time : "",
                    leaf: false
                });
            });
        }
        return this.#dedupeRecords(records).filter(record => record.path);
    }

    /**
     * Build a dot-domain tree from parsed records.
     *
     * @returns {object} Tree root.
     */
    #buildTree(): LogDomainTreeNode {
        const root: LogDomainTreeNode = { label: "", path: "", targetPath: "", children: new Map<string, LogDomainTreeNode>(), command: "", leaf: false, entryCount: 0 };
        for (const record of this.#domains()) {
            const parts = record.path.split(".").filter(Boolean);
            let current = root;
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                if (!current.children.has(part)) {
                    current.children.set(part, {
                        label: part,
                        path,
                        targetPath: path,
                        children: new Map<string, LogDomainTreeNode>(),
                        command: "",
                        leaf: false,
                        entryCount: 0
                    });
                }
                const child = current.children.get(part);
                if (!child) throw new Error(`Unable to create log domain node: ${path}`);
                current = child;
                if (index === parts.length - 1 && !record.leaf) {
                    current.command = record.command;
                    current.date = record.date;
                    current.time = record.time;
                    current.leaf = record.leaf;
                }
            });
            if (record.leaf) {
                current.entryCount = (current.entryCount || 0) + 1;
            }
        }
        return root;
    }

    /**
     * Find one parsed index record by path.
     *
     * @param {string} path Dot path.
     * @returns {object|null} Record or null.
     */
    #recordForPath(path: string): LogDomainRecord | null {
        return this.#domains().find(record => record.path === path) || null;
    }

    /**
     * Remove duplicate parsed records.
     *
     * @param {object[]} records Parsed records.
     * @returns {object[]} Unique records.
     */
    #dedupeRecords(records: LogDomainRecord[]): LogDomainRecord[] {
        const byPath = new Map<string, LogDomainRecord>();
        records.forEach(record => byPath.set(record.path, record));
        return Array.from(byPath.values());
    }

    /**
     * Return whether a node or descendant matches the filter.
     *
     * @param {object} node Tree node.
     * @returns {boolean} Visibility flag.
     */
    #matchesTree(node: LogDomainTreeNode): boolean {
        const needle = this.#filter.toLowerCase();
        if (!needle) {
            return true;
        }
        if (node.path.toLowerCase().includes(needle) || node.command.toLowerCase().includes(needle)) {
            return true;
        }
        return Array.from(node.children.values()).some(child => this.#matchesTree(child));
    }

    /**
     * Expand ancestors for a selected domain.
     *
     * @param {string} path Dot domain path.
     * @returns {void}
     */
    #expandAncestors(path: string): void {
        const parts = path.split(".");
        for (let index = 1; index <= parts.length; index += 1) {
            this.#expandedNodes.add(parts.slice(0, index).join("."));
        }
    }

    /**
     * Bind DOM events.
     *
     * @returns {void}
     */
    #bindEvents(): void {
        this.querySelector("[data-action='refresh-index']")?.addEventListener("click", () => this.#loadIndex(true));
        this.querySelectorAll("[data-action='load-logs']").forEach(button => button.addEventListener("click", () => this.#loadLogs(true)));
        this.querySelector<HTMLDetailsElement>(".filter-menu")?.addEventListener("toggle", event => {
            if (event.currentTarget instanceof HTMLDetailsElement) this.#filtersOpen = event.currentTarget.open;
        });
        this.querySelector("[data-action='clear-log-filters']")?.addEventListener("click", () => {
            this.#from = "";
            this.#to = "";
            this.#hourFrom = "";
            this.#hourTo = "";
            this.#sortOrder = "desc";
            this.#filtersOpen = true;
            this.#render();
        });
        // Filter input handled inside tree component
        this.querySelectorAll("[data-node-path]").forEach(button => button.addEventListener("click", async event => {
            const path = button.getAttribute("data-node-path") || "";
            const isBranch = button.getAttribute("data-node-branch") === "true";
            const wasExpanded = this.#expandedNodes.has(path);
            const clickedCaret = event.target instanceof Element && Boolean(event.target.closest(".tree-caret"));
            if (isBranch && clickedCaret) {
                const nextOpen = !wasExpanded;
                if (wasExpanded) {
                    this.#expandedNodes.delete(path);
                } else {
                    this.#expandedNodes.add(path);
                }
                const childContainer = Array.from(button.parentElement?.children || []).find((child): child is HTMLElement => child instanceof HTMLElement && child.classList.contains("tree-children"));
                if (childContainer) {
                    childContainer.hidden = !nextOpen;
                }
                const caret = button.querySelector(".tree-caret");
                if (caret) {
                    caret.innerHTML = icon(nextOpen ? "chevronDown" : "chevronRight");
                }
                return;
            }
            const alreadySelected = path === this.#selectedDomain;
            this.#selectedDomain = path;
            this.#expandAncestors(path);
            const record = this.#recordForPath(path);
            if (record?.date) {
                this.#from = record.date;
                this.#to = record.date;
                this.#hourFrom = record.time || "";
                this.#hourTo = record.time || "";
            }
            if (isBranch) {
                this.#expandedNodes.add(path);
            }
            if (alreadySelected && this.#logEntries.length) {
                this.#render();
                return;
            }
            await this.#loadLogs(true, !record?.date);
        }));
    }
}

customElements.define(LogsView.selector, LogsView);
