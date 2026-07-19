/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml, optionTags } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";
import { renderDescriptionCard } from "./description-card.ts";
import { StructureTree } from "./structure-tree.ts";

void StructureTree;

/**
 * KnowledgeView renders a canvas-based explorer for graph records returned by the CLI facade.
 * Entities/classes become draggable nodes. Relations become selectable edges.
 */
export class KnowledgeView extends HTMLElement {
    static get selector() {
        return "brain-knowledge-view";
    }

    #api = null;
    #state = null;
    #scope = "all";
    #selectedScopes = new Set(["global", "local"]);
    #treeScope = "all";
    #mode = "all";
    #domain = "all";
    #query = "";
    #output = null;
    #records = [];
    #relations = [];
    #nodes = [];
    #edges = [];
    #selectedNodeId = "";
    #selectedRelationId = "";
    #hoveredRelationId = "";
    #hoveredNodeId = "";
    #regionNodeIds = new Set();
    #regionEdgeIds = new Set();
    #regionPositions = new Map();
    #regionHistory = [];
    #regionRootNodeId = "";
    #dragNode = null;
    #panState = null;
    #cameraAnimationFrame = 0;
    #viewport = { x: 0, y: 0, scale: 1 };
    #renderFrustum = null;
    #edgeLabelBounds = new Map();
    #nodeLabelBounds = new Map();
    #viewportNodeIds = new Set();
    #viewportBadgeSignature = "";
    #viewportInspectorTimer = 0;
    #viewportBadgeRankingFrozen = false;
    #expandedDomains = new Set(["global::all", "local::all"]);
    #resizeObserver = null;
    #loadScheduled = false;
    #graphBusyDepth = 0;
    #graphBusyLabel = "Loading graph";
    #needsViewportFit = true;
    #filtersOpen = false;
    #domainTreeNodes = [];
    #memoryPaths = [];
    #pictures = [];
    #messages = [];
    #messageSessions = [];
    #logEntries = [];
    #selectedTreePath = "";
    #sourcePath = "";
    #sourceKind = "";
    #treeVisualType = "";
    #focusViewport = null;
    #relationHoverViewport = null;
    #badgeHoverViewport = null;
    #pointerCandidate = null;
    #domainColors = new Map();
    #usedDomainColors = new Set();
    #pendingEntityLabel = "";

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        const target = this.#state?.consumeRouteTarget?.("knowledge") || null;
        this.#pendingEntityLabel = String(target?.entityLabel || "").trim();
        this.#render();
        this.#scheduleInitialLoad();
        if (this.#output) queueMicrotask(() => this.#resolvePendingEntity());
    }

    /**
     * Initialize component DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
        this.#scheduleInitialLoad();
    }

    /**
     * Disconnect canvas observers.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        this.#resizeObserver?.disconnect();
        cancelAnimationFrame(this.#cameraAnimationFrame);
        clearTimeout(this.#viewportInspectorTimer);
    }

    /**
     * Load records once after the component has context.
     *
     * @returns {void}
     */
    #scheduleInitialLoad() {
        if (!this.#api || this.#loadScheduled || this.#output) {
            return;
        }
        this.#loadScheduled = true;
        queueMicrotask(() => this.#showRecords());
    }

    /**
     * List graph records for the current scope and view.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after list call.
     */
    async #showRecords(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        this.#beginGraphBusy(forceRefresh ? "Refreshing graph" : "Loading graph");
        try {
            this.#readControls();
            const [result, memoryResult, pictureResult, messageResult, logResult] = await Promise.all([
                this.#api.knowledgeShow({ scope: "all", mode: "all" }, { forceRefresh }),
                this.#api.memoryTree({ forceRefresh }),
                this.#api.pictures({}, { forceRefresh }),
                this.#api.getVoiceMessages({ all: "true" }, { forceRefresh, silent: true }),
                this.#api.logIndex({}, { forceRefresh, silent: true })
            ]);
            this.#state?.setLastResult(result);
            this.#output = result;
            this.#memoryPaths = Array.isArray(memoryResult.data) ? memoryResult.data.map(path => String(path)) : [];
            this.#pictures = Array.isArray(pictureResult.data?.pictures) ? pictureResult.data.pictures : [];
            this.#messages = Array.isArray(messageResult.data?.history) ? messageResult.data.history : [];
            this.#messageSessions = Array.isArray(messageResult.data?.sessions) ? messageResult.data.sessions : [];
            this.#logEntries = Array.isArray(logResult.data?.entries) ? logResult.data.entries : [];
            this.#ingestGraph(result.data);
            this.#render();
            this.#resolvePendingEntity();
        } finally {
            this.#endGraphBusy();
        }
    }

    /**
     * Search graph records.
     *
     * @returns {Promise<void>} Resolves after query call.
     */
    async #queryRecords() {
        if (!this.#api) {
            return;
        }
        this.#readControls();
        if (!this.#query) {
            await this.#applyFilters();
            return;
        }
        this.#beginGraphBusy("Searching graph");
        try {
            const result = await this.#api.knowledgeQuery({
                q: this.#query,
                scope: this.#scope,
                limit: "120",
                explain: "true"
            });
            this.#state?.setLastResult(result);
            this.#output = result;
            this.#ingestGraph(result.data);
            this.#render();
        } finally {
            this.#endGraphBusy();
        }
    }

    /**
     * Load pending delta review.
     *
     * @returns {Promise<void>} Resolves after delta review.
     */
    async #reviewDeltas() {
        if (!this.#api) {
            return;
        }
        this.#beginGraphBusy("Reviewing graph deltas");
        try {
            this.#readControls();
            const result = await this.#api.knowledgeDeltas({
                scope: this.#scope,
                limit: "80",
                status: "pending"
            }, { forceRefresh: true });
            this.#state?.setLastResult(result);
            this.#output = result;
            this.#ingestGraph(result.data);
            this.#render();
        } finally {
            this.#endGraphBusy();
        }
    }

    /**
     * Store normalized graph data and refresh derived nodes.
     *
     * @param {unknown} data Command data.
     * @returns {void}
     */
    #ingestGraph(data) {
        const graph = this.#collectGraph(data);
        this.#records = graph.records;
        this.#relations = graph.relations;
        if (this.#domain !== "all" && !this.#domains().some(domain => domain === this.#domain || domain.startsWith(`${this.#domain}.`))) {
            this.#domain = "all";
        }
        this.#selectedNodeId = "";
        this.#selectedRelationId = "";
        this.#regionNodeIds.clear();
        this.#regionEdgeIds.clear();
        this.#regionPositions.clear();
        this.#regionHistory = [];
        this.#regionRootNodeId = "";
        this.#needsViewportFit = true;
        this.#prepareGraph();
    }

    /**
     * Read form controls into component state.
     *
     * @returns {void}
     */
    #readControls() {
        this.#selectedScopes = new Set(
            [...this.querySelectorAll("[data-filter-kind='kg-scope']:checked")].map(input => input.value)
        );
        this.#scope = this.#selectedScopes.size === 1 ? [...this.#selectedScopes][0] : "all";
        const selectedModes = [...this.querySelectorAll("[data-filter-kind='kg-mode']:checked")]
            .map(input => input.value);
        this.#mode = selectedModes.length === 1 ? selectedModes[0] : "all";
        this.#query = this.querySelector("[data-role='kg-query']")?.value.trim() || "";
    }

    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface knowledge-console">
                <div class="structure-layout knowledge-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.#renderDomainTree()}
                        </div>
                    </aside>
                    <main class="structure-content knowledge-content">
                        <div class="content-head graph-toolbar">
                            <input class="graph-search-input" aria-label="Search graph" data-role="kg-query" value="${escapeHtml(this.#query)}" placeholder="Filter or search graph">
                            <details class="action-menu filter-menu knowledge-filter-menu" ${this.#filtersOpen ? "open" : ""}>
                                <summary class="compact-action">${icon("filter")}<span>Filters</span></summary>
                                <div class="action-menu-panel filter-menu-panel">
                                    <fieldset class="checkbox-filter-group knowledge-scope-filter">
                                        <legend>Scope</legend>
                                        <div class="knowledge-filter-options">
                                            <label><input type="checkbox" data-filter-kind="kg-scope" value="global" ${this.#selectedScopes.has("global") ? "checked" : ""}><span>Global</span></label>
                                            <label><input type="checkbox" data-filter-kind="kg-scope" value="local" ${this.#selectedScopes.has("local") ? "checked" : ""}><span>Local</span></label>
                                        </div>
                                    </fieldset>
                                    <fieldset class="checkbox-filter-group">
                                        <legend>Visible content</legend>
                                        <div class="knowledge-filter-options">
                                            <label><input type="checkbox" data-filter-kind="kg-mode" value="entities" ${this.#mode === "all" || this.#mode === "entities" ? "checked" : ""}><span>Entities</span></label>
                                            <label><input type="checkbox" data-filter-kind="kg-mode" value="classes" ${this.#mode === "all" || this.#mode === "classes" ? "checked" : ""}><span>Classes</span></label>
                                        </div>
                                    </fieldset>
                                </div>
                            </details>
                            <button data-action="query-records" class="primary-action">${icon("search")}Search</button>
                        </div>
                        <div class="knowledge-canvas-layout">
                            <main class="graph-viewport">
                                <button class="graph-focus-back secondary-action compact-action" data-action="navigate-region-back" ${this.#regionHistory.length ? "" : "hidden"}>
                                    ${icon("chevronLeft")} Back
                                </button>
                                <canvas class="knowledge-graph-canvas" data-role="knowledge-canvas" aria-label="Knowledge graph"></canvas>
                                ${this.#renderGraphBusyState()}
                                <div data-role="relation-preview-host">
                                    ${this.#renderRelationPreview()}
                                </div>
                                ${this.#renderCanvasEmptyState()}
                            </main>
                            <aside class="graph-detail-list">
                                ${this.#renderDetails()}
                            </aside>
                        </div>
                    </main>
                </div>
            </section>
        `;
        this.#bindEvents();
        this.#configureDomainTree();
        this.#bindCanvas();
    }

    /**
     * Render an empty overlay only when there are no visible nodes.
     *
     * @returns {string} HTML.
     */
    #renderCanvasEmptyState() {
        if (this.#nodes.length || this.#records.length || this.#relations.length) {
            return "";
        }
        return `
            <div class="knowledge-empty-state canvas-empty">
                ${icon("graph")}
                <h2>${this.#output?.ok === false ? "Query failed" : "Loading graph"}</h2>
                <p>${escapeHtml(this.#output?.error || this.#output?.stderr || "Nodes will appear here.")}</p>
            </div>
        `;
    }

    /** Render the bounded operation status overlay for the canvas. */
    #renderGraphBusyState() {
        return `
            <div class="graph-busy-overlay" data-role="graph-busy-overlay" role="status" aria-live="polite" ${this.#graphBusyDepth ? "" : "hidden"}>
                <span class="graph-busy-spinner" aria-hidden="true"></span>
                <strong data-role="graph-busy-label">${escapeHtml(this.#graphBusyLabel)}</strong>
            </div>
        `;
    }

    /** Begin one graph operation and expose its latest user-facing status. */
    #beginGraphBusy(label) {
        this.#graphBusyDepth += 1;
        this.#graphBusyLabel = String(label || "Loading graph");
        this.#syncGraphBusyState();
    }

    /** Finish one graph operation without hiding another overlapping operation. */
    #endGraphBusy() {
        this.#graphBusyDepth = Math.max(0, this.#graphBusyDepth - 1);
        this.#syncGraphBusyState();
    }

    /** Synchronize busy state without rebuilding the Knowledge component. */
    #syncGraphBusyState() {
        const overlay = this.querySelector("[data-role='graph-busy-overlay']");
        const viewport = this.querySelector(".graph-viewport");
        if (overlay) {
            overlay.hidden = this.#graphBusyDepth === 0;
            const label = overlay.querySelector("[data-role='graph-busy-label']");
            if (label) {
                label.textContent = this.#graphBusyLabel;
            }
        }
        viewport?.setAttribute("aria-busy", String(this.#graphBusyDepth > 0));
    }

    /** Yield one paint frame so synchronous graph projection can expose the spinner. */
    #waitForGraphPaint() {
        return new Promise(resolve => requestAnimationFrame(() => resolve()));
    }

    /** Render the complete subject-predicate-object preview for the selected relation. */
    #renderRelationPreview() {
        const relationId = this.#hoveredRelationId || this.#selectedRelationId;
        const relation = this.#edges.find(edge => edge.id === relationId);
        if (!relation) {
            return "";
        }
        const source = this.#nodes.find(node => node.id === relation.from);
        const target = this.#nodes.find(node => node.id === relation.to);
        return `
            <section class="graph-relation-preview" role="status" aria-label="Focused relation preview">
                <button class="graph-relation-endpoint" data-action="navigate-relation-endpoint" data-node-id="${escapeHtml(relation.from)}" style="--entity-color: ${escapeHtml(source?.color || "var(--primary)")}">
                    ${escapeHtml(relation.fromLabel)}
                </button>
                <span class="graph-relation-connector">
                    <strong class="graph-relation-predicate" title="${escapeHtml(relation.label)}">${escapeHtml(relation.label)}</strong>
                </span>
                <button class="graph-relation-endpoint" data-action="navigate-relation-endpoint" data-node-id="${escapeHtml(relation.to)}" style="--entity-color: ${escapeHtml(target?.color || "var(--primary)")}">
                    ${escapeHtml(relation.toLabel)}
                </button>
            </section>
        `;
    }

    /**
     * Render the domain tree used to scope the graph.
     *
     * @returns {string} HTML.
     */
    #renderDomainTree() {
        this.#domainTreeNodes = [
            this.#scopeTreeRoot("global", "Global knowledge", this.#memoryPaths),
            this.#scopeTreeRoot("local", "Local knowledge", [])
        ].filter(root => this.#selectedScopes.has(root.scope));
        return `<brain-structure-tree data-role="knowledge-domain-tree"></brain-structure-tree>`;
    }

    /** Build one physical-scope root without hiding canonical empty sources. */
    #scopeTreeRoot(scope, label, canonicalPaths) {
        let children = [];
        if (scope === "global") {
            const leaves = new Set(canonicalPaths.filter(path => !canonicalPaths.some(candidate => candidate.startsWith(`${path}.`))));
            const memoryEntries = canonicalPaths.map(path => ({
                segments: this.#domainParts(path),
                domain: path,
                sourcePath: leaves.has(path) ? `memory/${path.replaceAll(".", "/")}.md` : ""
            }));
            const pictureEntries = this.#pictures.map(picture => this.#pictureTreeEntry(picture));
            children = [
                this.#sourceCategory(scope, "memory", "Global memory", memoryEntries, "memory"),
                this.#classSuperDomain(scope),
                this.#sourceCategory(scope, "pictures", "Pictures", pictureEntries, "camera")
            ];
        } else {
            children = [
                this.#sourceCategory(scope, "memory", "Local memory", [], "memory"),
                this.#classSuperDomain(scope),
                this.#sourceCategory(scope, "logs", "Logs", this.#logTreeEntries(), "document"),
                this.#sourceCategory(scope, "messages", "Messages", this.#messageTreeEntries(), "messageCircle")
            ];
        }
        return {
            id: `${scope}::all`,
            path: `${scope}::all`,
            label,
            icon: "database",
            count: this.#graphCountLabel("all", scope),
            children,
            actions: [{ id: "filter-source", label: "FILTER", icon: "filter" }],
            scope,
            domain: "all"
        };
    }

    /** Build one canonical picture-tree entry without duplicating its domain prefix. */
    #pictureTreeEntry(picture) {
        const sourcePath = String(picture.relative_path || picture.filename || "").replaceAll("\\", "/");
        const sourceSegments = sourcePath.split("/").filter(Boolean);
        const domainSegments = this.#domainParts(String(picture.domain || "no-domain"));
        const alreadyPrefixed = domainSegments.every((segment, index) => (
            String(sourceSegments[index] || "").toLowerCase() === segment.toLowerCase()
        ));
        const segments = alreadyPrefixed ? sourceSegments : [...domainSegments, ...sourceSegments];
        return {
            segments,
            sourcePrefixes: segments.map((_, index) => segments.slice(0, index + 1).join("/")),
            domain: "pictures",
            sourcePath,
            openRoute: "pictures",
            openTarget: { pictureId: String(picture.id) },
            detail: String(picture.description || "")
        };
    }

    /** Build a canonical source category from filesystem or registry entries. */
    #sourceCategory(scope, key, label, entries, categoryIcon) {
        const root = { children: new Map() };
        entries.forEach(entry => {
            let node = root;
            entry.segments.forEach((part, index) => {
                const terminal = index === entry.segments.length - 1;
                const branchSourcePath = String(entry.sourcePrefixes?.[index] || "");
                const baseId = `${scope}::source:${key}/${entry.segments.slice(0, index + 1).join("/")}`;
                const id = terminal && entry.sourcePath ? `${baseId}::${entry.sourcePath}` : baseId;
                const childKey = terminal && entry.sourcePath ? `${part}::${entry.sourcePath}` : part;
                const branchDomain = key === "memory"
                    ? entry.segments.slice(0, index + 1).join(".")
                    : entry.domain;
                if (!node.children.has(childKey)) {
                    node.children.set(childKey, {
                        label: part,
                        path: id,
                        scope,
                        domain: branchDomain,
                        sourceKind: key,
                        sourcePath: branchSourcePath,
                        children: new Map()
                    });
                }
                node = node.children.get(childKey);
                if (key === "memory") node.domain = branchDomain;
                if (terminal) Object.assign(node, entry);
            });
        });
        const sourceChildren = this.#knowledgeTreeNodes([...root.children.values()]);
        return {
            id: `${scope}::source:${key}`,
            path: `${scope}::source:${key}`,
            label,
            icon: categoryIcon,
            count: this.#graphCountLabel("all", scope, key),
            children: sourceChildren,
            actions: [{ id: "filter-source", label: "FILTER", icon: "filter" }],
            scope,
            domain: "all",
            sourceKind: key,
            folder: true,
            sortKey: `${({ memory: 0, pictures: 2, logs: 2, messages: 3 })[key] ?? 4}:${label}`
        };
    }

    /** Build a non-owning class projection while retaining each class in its source branch. */
    #classSuperDomain(scope) {
        return {
            id: `${scope}::classes`,
            path: `${scope}::classes`,
            label: "Classes",
            icon: "graph",
            count: this.#graphCountLabel("all", scope, "", "", "class"),
            children: [],
            actions: [{ id: "filter-source", label: "FILTER", icon: "filter" }],
            scope,
            domain: "all",
            sourceKind: "",
            visualType: "class",
            folder: true,
            sortKey: "1:Classes"
        };
    }

    /** Project persisted message bodies beneath their canonical sessions. */
    #messageTreeEntries() {
        const sessions = new Map(this.#messageSessions.map(session => [`${session.date}:${session.chatId}`, session]));
        return this.#messages.map(message => {
            const session = sessions.get(`${message.date}:${message.chat_id}`) || null;
            const date = String(session?.date || message.created_at || "no-date").slice(0, 10);
            const sessionLabel = String(session?.label || session?.chatId || message.chat_id || "session");
            const body = String(message.text || message.display_text || "Message has no body");
            return {
                segments: [...date.split("-"), sessionLabel, this.#shortLabel(body.replace(/\s+/g, " "), 54)],
                domain: "messages",
                sourcePath: `messages/${message.id}`,
                openRoute: "messages",
                openTarget: { messageId: String(message.id), sessionId: String(session?.id || "") },
                detail: body
            };
        });
    }

    /** Project the persisted log index as canonical local-memory sources. */
    #logTreeEntries() {
        return this.#logEntries.map((entry, index) => {
            const domain = String(entry.domain || "logs");
            const timestamp = String(entry.timestamp || "");
            const [date = "", ...timeParts] = timestamp.split(" ");
            const time = timeParts.join(" ");
            return {
                segments: [...this.#domainParts(domain), String(entry.title || timestamp || `log-${index + 1}`)],
                domain: "logs",
                sourcePath: `logs/${domain}/${timestamp || "undated"}/${index}`,
                openRoute: "logs",
                openTarget: { domain, date, time },
                detail: String(entry.title || "")
            };
        });
    }

    /**
     * Convert parsed Knowledge domains into shared tree nodes.
     *
     * @param {object[]} nodes Source domain nodes.
     * @returns {object[]} Shared tree nodes.
     */
    #knowledgeTreeNodes(nodes) {
        return nodes
            .map(node => {
                const children = this.#knowledgeTreeNodes([...node.children.values()]);
                return {
                    id: node.path,
                    path: node.path,
                    label: node.label,
                    color: this.#domainColor(node.path),
                    count: this.#graphCountLabel(node.domain, node.scope, node.sourceKind, node.sourcePath || ""),
                    children,
                    actions: [
                        { id: "consolidate-source", label: "CONSOLIDATE", icon: "graph" },
                        { id: "filter-source", label: "FILTER", icon: "filter" },
                        ...(node.openRoute ? [{ id: "open-source", label: "OPEN", icon: "chevronRight" }] : [])
                    ],
                    scope: node.scope,
                    domain: node.domain,
                    sourceKind: node.sourceKind || "",
                    visualType: node.visualType || "",
                    sortKey: node.sortKey,
                    sourcePath: node.sourcePath || "",
                    openRoute: node.openRoute || "",
                    openTarget: node.openTarget || null,
                    detail: node.detail || "",
                    folder: children.length > 0 || (!node.sourcePath && !node.openRoute)
                };
            })
            .sort((left, right) => left.label.localeCompare(right.label));
    }

    /**
     * Configure the shared tree with Knowledge graph actions.
     *
     * @returns {void}
     */
    #configureDomainTree() {
        const treeElement = this.querySelector("[data-role='knowledge-domain-tree']");
        if (!treeElement) {
            return;
        }
        treeElement.model = {
            nodes: this.#domainTreeNodes,
            selectedPath: this.#selectedTreePath,
            expandedPaths: this.#expandedDomains,
            toggleOnBranchSelect: true,
            title: "Knowledge",
            toolbarActions: [
                { id: "refresh-graph", label: "Refresh graph", icon: "refresh" },
                { id: "review-deltas", label: "Review deltas", icon: "graph" },
                { id: "fit-graph", label: "Fit canvas", icon: "filter" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "document"
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onDomainTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onDomainTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onDomainTreeAction(event));
    }

    /**
     * Scope the graph to a selected domain.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onDomainTreeSelected(event) {
        const node = event.detail.node || {};
        this.#selectedTreePath = String(node.path || "");
        this.#treeScope = String(node.scope || "all");
        this.#domain = String(node.domain || "all");
        this.#sourceKind = String(node.sourceKind || "");
        this.#treeVisualType = String(node.visualType || "");
        this.#sourcePath = String(node.sourcePath || "");
        this.#applyTreeSelection();
    }

    /**
     * Run one global Knowledge tree action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onDomainTreeToolbarAction(event) {
        if (event.detail.action === "refresh-graph") {
            this.#showRecords(true);
        } else if (event.detail.action === "review-deltas") {
            this.#reviewDeltas();
        } else if (event.detail.action === "fit-graph") {
            this.#needsViewportFit = true;
            this.#drawCanvas();
        }
    }

    /**
     * Scope the graph from a domain contextual action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onDomainTreeAction(event) {
        if (!event.detail.node?.path) {
            return;
        }
        if (event.detail.action === "filter-source") {
            this.#selectedTreePath = String(event.detail.node.path);
            this.#treeScope = String(event.detail.node.scope || "all");
            this.#domain = String(event.detail.node.domain || "all");
            this.#sourceKind = String(event.detail.node.sourceKind || "");
            this.#treeVisualType = String(event.detail.node.visualType || "");
            this.#sourcePath = String(event.detail.node.sourcePath || "");
            this.#applyTreeSelection();
            return;
        }
        if (event.detail.action === "open-source" && event.detail.node.openRoute) {
            this.#state?.setRouteTarget?.(event.detail.node.openRoute, event.detail.node.openTarget || {});
            return;
        }
        if (event.detail.action === "consolidate-source") {
            this.#reviewDeltas();
        }
    }

    /**
     * Render recursive domain rows.
     *
     * @param {object[]} nodes Domain nodes.
     * @param {number} depth Tree depth.
     * @param {string} filter Text filter.
     * @returns {string} HTML.
     */
    #renderDomainChildren(nodes, depth, filter) {
        return nodes
            .filter(node => !filter || node.path.toLowerCase().includes(filter))
            .map(node => {
                const children = [...node.children.values()];
                const expanded = this.#expandedDomains.has(node.path);
                const count = this.#countRecordsInDomain(node.path);
                return `
                    <div class="tree-node-wrap">
                        <button class="tree-node ${this.#domain === node.path ? "is-active" : ""}" style="--tree-depth: ${depth}" data-action="select-domain" data-domain-path="${escapeHtml(node.path)}">
                            <span class="tree-caret">${children.length ? icon(expanded ? "chevronDown" : "chevronRight") : ""}</span>
                            ${icon(children.length ? "folder" : "document")}
                            <span>${escapeHtml(node.label)}</span>
                            <small>${escapeHtml(String(count))}</small>
                        </button>
                        ${expanded && children.length ? `<div class="tree-children">${this.#renderDomainChildren(children, depth + 1, filter)}</div>` : ""}
                    </div>
                `;
            }).join("");
    }

    /**
     * Render the graph inspector.
     *
     * @returns {string} HTML.
     */
    #renderDetails() {
        const selectedRelation = this.#edges.find(edge => edge.id === this.#selectedRelationId);
        if (selectedRelation) {
            return this.#renderRelationDetails(selectedRelation);
        }
        const selected = this.#nodes.find(node => node.id === this.#selectedNodeId);
        if (selected) {
            return this.#renderNodeDetails(selected);
        }
        const importantNodes = this.#importantNodes();
        return `
            <div class="content-head">
                <strong>Inspector</strong>
                <span>${escapeHtml(String(this.#nodes.length))} nodes · ${escapeHtml(String(this.#edges.length))} relations</span>
            </div>
            <div class="node-inspector scroll-list">
                <p>Select a canvas node or relation. Nodes are draggable; the canvas supports pan and zoom.</p>
                <div class="source-chip-row important-node-chips" aria-label="Important entities">
                    ${importantNodes.map(node => `
                        <button data-action="focus-node" data-node-id="${escapeHtml(node.id)}" title="Focus ${escapeHtml(node.label)}" style="--entity-color: ${escapeHtml(node.color)}">
                            <strong>${escapeHtml(node.label)}</strong>
                            <small>${escapeHtml(String(node.degree))}</small>
                        </button>
                    `).join("")}
                </div>
            </div>
        `;
    }

    /**
     * Render entity/class node details.
     *
     * @param {object} selected Selected graph node.
     * @returns {string} HTML.
     */
    #renderNodeDetails(selected) {
        const picture = this.#pictureForNode(selected);
        const message = this.#messageForNode(selected);
        const pictureTag = this.#isPictureTagNode(selected);
        return `
            <div class="content-head">
                <strong>${escapeHtml(selected.label)}</strong>
                <span>${escapeHtml(selected.domain)}</span>
            </div>
            <div class="node-inspector scroll-list">
                ${picture ? `
                    <button class="knowledge-source-preview" data-action="open-detail-source" data-route="pictures" data-picture-id="${escapeHtml(String(picture.id))}">
                        <img src="${escapeHtml(this.#api?.pictureUrl(String(picture.id)) || "")}" alt="${escapeHtml(picture.description || picture.filename)}">
                        <span>Open in Pictures</span>
                    </button>
                ` : ""}
                ${message ? `
                    <blockquote class="knowledge-message-preview">${escapeHtml(String(message.text || ""))}</blockquote>
                    <button class="secondary-action" data-action="open-detail-source" data-route="messages" data-message-id="${escapeHtml(String(message.id))}">Open in Messages</button>
                ` : ""}
                <dl>
                    <dt>Context</dt><dd>${escapeHtml(selected.context)}</dd>
                    <dt>Domain</dt><dd>${escapeHtml(selected.domain)}</dd>
                    <dt>${pictureTag ? "Provenance" : "Source"}</dt><dd>${pictureTag
                        ? `Derived from image analysis · ${escapeHtml(selected.source)}`
                        : escapeHtml(selected.source)}</dd>
                    <dt>Suggested class</dt><dd>${escapeHtml(selected.classHint || "-")}</dd>
                    <dt>Confidence</dt><dd>${escapeHtml(String(selected.confidence || "-"))}</dd>
                </dl>
                ${renderDescriptionCard(
                    selected.description || "",
                    { title: picture ? "Image description" : "Entity description" }
                )}
                ${this.#renderRelatedNodes(selected)}
            </div>
        `;
    }

    /** Resolve an image registry record from one graph source reference. */
    #pictureForNode(node) {
        if (this.#isPictureTagNode(node)) return null;
        const source = String(node.source || "").replaceAll("\\", "/").toLowerCase();
        const pictureId = String(node.raw?.picture_id || "");
        return this.#pictures.find(picture => pictureId === String(picture.id)
            || source.endsWith(String(picture.relative_path || "").replaceAll("\\", "/").toLowerCase())) || null;
    }

    /** Return whether a semantic image-analysis tag is being inspected, not its picture source. */
    #isPictureTagNode(node) {
        return String(node.classHint || "").trim().toLowerCase() === "misc.tag";
    }

    /** Resolve a persisted message body from one graph source reference. */
    #messageForNode(node) {
        const source = String(node.source || "");
        return this.#messages.find(message => source.includes(String(message.id))) || null;
    }

    /**
     * Render relation edge details.
     *
     * @param {object} relation Selected relation edge.
     * @returns {string} HTML.
     */
    #renderRelationDetails(relation) {
        return `
            <div class="content-head">
                <strong>Relation</strong>
                <span>${escapeHtml(relation.label)}</span>
            </div>
            <div class="node-inspector relation-inspector scroll-list">
                <dl>
                    <dt>Name</dt><dd>${escapeHtml(relation.label)}</dd>
                    <dt>Source node</dt><dd>${escapeHtml(relation.fromLabel)}</dd>
                    <dt>Target node</dt><dd>${escapeHtml(relation.toLabel)}</dd>
                    <dt>Context</dt><dd>${escapeHtml(relation.context)}</dd>
                    <dt>Domain</dt><dd>${escapeHtml(relation.domain)}</dd>
                    <dt>Source</dt><dd>${escapeHtml(relation.source)}</dd>
                    <dt>Confidence</dt><dd>${escapeHtml(String(relation.confidence || "-"))}</dd>
                </dl>
                ${renderDescriptionCard(
                    relation.description || "Relation detected by the CLI facade.",
                    { title: "Relation description" }
                )}
                <div class="graph-list">
                    ${[relation.from, relation.to].map(nodeId => {
                        const node = this.#nodes.find(item => item.id === nodeId);
                        return node ? `
                            <button class="graph-list-item" data-action="select-node" data-node-id="${escapeHtml(node.id)}">
                                <span class="activity-dot" style="background: ${escapeHtml(node.color)}"></span>
                                <strong>${escapeHtml(node.label)}</strong>
                            </button>
                        ` : "";
                    }).join("")}
                </div>
            </div>
        `;
    }

    /**
     * Render related node labels for the selected node.
     *
     * @param {object} selected Selected graph node.
     * @returns {string} HTML.
     */
    #renderRelatedNodes(selected) {
        const related = this.#edges
            .filter(edge => edge.from === selected.id || edge.to === selected.id)
            .slice(0, 10);
        if (!related.length) {
            return "";
        }
        return `
            <h2>Visible relations</h2>
            <div class="graph-list">
                ${related.map(edge => {
                    const opposite = this.#nodes.find(node => node.id === (edge.from === selected.id ? edge.to : edge.from));
                    return opposite ? `
                        <button class="graph-list-item" data-action="select-relation" data-relation-id="${escapeHtml(edge.id)}">
                            <span class="activity-dot" style="background: ${escapeHtml(opposite.color)}"></span>
                            <strong>${escapeHtml(edge.label)} - ${escapeHtml(opposite.label)}</strong>
                        </button>
                    ` : "";
                }).join("")}
            </div>
        `;
    }

    /** Return highest-connectivity entities in the currently visible graph or region. */
    #importantNodes() {
        const focus = this.#focusGraph();
        const logicalCandidates = focus
            ? this.#nodes.filter(node => focus.nodeIds.has(node.id))
            : this.#nodes;
        const candidates = this.#viewportBadgeSignature
            ? logicalCandidates.filter(node => this.#viewportNodeIds.has(node.id))
            : logicalCandidates;
        return this.#rankImportantNodes(candidates);
    }

    /** Rank one explicit visible-node set by its internal connectivity. */
    #rankImportantNodes(candidates) {
        const visibleIds = new Set(candidates.map(node => node.id));
        const degrees = this.#nodeDegrees({ nodeIds: visibleIds, edgeIds: new Set() });
        return candidates
            .filter(node => node.visualType !== "class")
            .map(node => ({ ...node, degree: degrees.get(node.id) || 0 }))
            .sort((left, right) => right.degree - left.degree || left.label.localeCompare(right.label))
            .slice(0, 12);
    }

    /**
     * Convert command data to normalized graph records.
     *
     * @param {unknown} data Command data.
     * @returns {{records: object[], relations: object[]}} Graph data.
     */
    #collectGraph(data) {
        const relationItems = this.#relationDataArray(data);
        const relations = relationItems.map((item, index) => this.#relationFromItem(item, index)).filter(Boolean);
        const nodeItems = this.#nodeDataArray(data);
        const records = nodeItems.map((item, index) => this.#recordFromItem(item, index)).filter(record => record.label);

        return { records, relations };
    }

    /**
     * Return arrays that should become nodes.
     *
     * @param {unknown} data Command data.
     * @returns {Array} Raw node array.
     */
    #nodeDataArray(data) {
        if (Array.isArray(data)) {
            return this.#withVisualType(data, this.#mode === "classes" ? "class" : "entity");
        }
        if (!data || typeof data !== "object") {
            return [];
        }
        if (this.#mode === "all") {
            const entityItems = this.#withVisualType(data.entities || data.nodes || [], "entity");
            const classItems = this.#withVisualType(data.classes || [], "class");
            const mixedItems = this.#withVisualType(data.results || data.matches || [], "entity");
            const combinedItems = [...entityItems, ...classItems, ...mixedItems];
            if (combinedItems.length) {
                return combinedItems;
            }
        }
        if (this.#mode === "classes" && Array.isArray(data.classes)) {
            return this.#withVisualType(data.classes, "class");
        }
        if (Array.isArray(data.entities)) {
            const entities = this.#mode === "entities"
                ? data.entities.filter(item => !this.#looksLikeClass(item))
                : data.entities;
            return this.#withVisualType(entities, "entity");
        }
        if (Array.isArray(data.nodes)) {
            const nodes = this.#mode === "entities"
                ? data.nodes.filter(item => !this.#looksLikeClass(item))
                : data.nodes;
            return this.#withVisualType(nodes, "entity");
        }
        if (Array.isArray(data.results)) {
            return this.#withVisualType(
                this.#mode === "entities" ? data.results.filter(item => !this.#looksLikeClass(item)) : data.results,
                "entity"
            );
        }
        if (Array.isArray(data.matches)) {
            return this.#withVisualType(
                this.#mode === "entities" ? data.matches.filter(item => !this.#looksLikeClass(item)) : data.matches,
                "entity"
            );
        }
        return Object.values(data)
            .filter(value => Array.isArray(value))
            .flat()
            .filter(item => !this.#looksLikeRelation(item))
            .map(item => this.#withVisualType([item], this.#looksLikeClass(item) ? "class" : "entity")[0]);
    }

    /**
     * Attach UI-only graph type metadata to raw records.
     *
     * @param {Array} items Raw records.
     * @param {"entity"|"class"} visualType Visual node type.
     * @returns {Array} Records carrying visual type.
     */
    #withVisualType(items, visualType) {
        if (!Array.isArray(items)) {
            return [];
        }
        return items.map(item => {
            if (!item || typeof item !== "object") {
                return item;
            }
            return {
                ...item,
                __visualType: visualType
            };
        });
    }

    /**
     * Return arrays that should become edges.
     *
     * @param {unknown} data Command data.
     * @returns {Array} Raw relation array.
     */
    #relationDataArray(data) {
        if (!data || typeof data !== "object") {
            return [];
        }
        if (Array.isArray(data.relations)) {
            return data.relations;
        }
        if (Array.isArray(data.edges)) {
            return data.edges;
        }
        if (Array.isArray(data.links)) {
            return data.links;
        }
        return Object.values(data)
            .filter(value => Array.isArray(value))
            .flat()
            .filter(item => this.#looksLikeRelation(item));
    }

    /**
     * Convert one item into a graph node record.
     *
     * @param {unknown} item Raw item.
     * @param {number} index Fallback index.
     * @returns {object} Node record.
     */
    #recordFromItem(item, index) {
        const label = this.#itemLabel(item, index);
        const sourcePath = String(item?.source_path || item?.path || item?.source || "");
        const domain = this.#domainFromRecord(item, sourcePath);
        const entityId = item?.entity_id ?? item?.id ?? "";
        const knowledgeScope = String(item?.knowledge_scope || this.#scope || "global");
        return {
            id: String(entityId || this.#nodeId(domain, label, index)),
            label,
            kind: "node",
            visualType: this.#looksLikeClass(item) ? "class" : (item?.__visualType || "entity"),
            context: this.#contextFromRecord(item, sourcePath),
            classHint: String(item?.entity_class || item?.class || item?.type || item?.kind || ""),
            domain,
            entityId: String(entityId),
            knowledgeScope,
            source: sourcePath || String(item?.source_type || item?.source_title || "knowledge"),
            description: String(item?.description || item?.excerpt || item?.text || ""),
            confidence: item?.confidence ?? item?.score ?? "",
            raw: item
        };
    }

    /**
     * Convert one relation payload into an edge record.
     *
     * @param {unknown} item Raw item.
     * @param {number} index Fallback index.
     * @returns {object|null} Relation record.
     */
    #relationFromItem(item, index) {
        if (!item || typeof item !== "object") {
            return null;
        }
        const sourcePath = String(item?.source_path || item?.path || item?.source_file || item?.source || "");
        const domain = this.#domainFromRecord(item, sourcePath);
        const fromLabel = String(item?.subject_name || item?.source_name || item?.source_label || item?.subject || item?.from || item?.head || item?.source || item?.entity || `Origen ${index + 1}`);
        const toLabel = String(item?.object_name || item?.target_name || item?.target_label || item?.object || item?.to || item?.tail || item?.target || item?.related || `Destino ${index + 1}`);
        const label = String(item?.relation || item?.predicate || item?.label || item?.type || item?.kind || "relation");
        const fromEntityId = item?.subject_entity_id ?? item?.source_entity_id ?? item?.from_entity_id ?? item?.head_entity_id ?? "";
        const toEntityId = item?.object_entity_id ?? item?.target_entity_id ?? item?.to_entity_id ?? item?.tail_entity_id ?? "";
        const knowledgeScope = String(item?.knowledge_scope || this.#scope || "global");
        return {
            id: String(item?.id || `relation:${domain}:${fromLabel}:${label}:${toLabel}:${index}`),
            kind: "relation",
            label,
            fromLabel,
            toLabel,
            from: String(fromEntityId || this.#nodeId(domain, fromLabel)),
            to: String(toEntityId || this.#nodeId(domain, toLabel)),
            fromEntityId: String(fromEntityId),
            toEntityId: String(toEntityId),
            knowledgeScope,
            fromClass: String(item?.subject_class || item?.source_class || item?.from_class || ""),
            toClass: String(item?.object_class || item?.target_class || item?.to_class || ""),
            domain,
            context: this.#contextFromRecord(item, sourcePath),
            source: sourcePath || String(item?.source_type || item?.source_title || "knowledge"),
            description: String(item?.description || item?.excerpt || item?.text || ""),
            confidence: item?.confidence ?? item?.score ?? "",
            raw: item
        };
    }

    /**
     * Return whether a payload appears to represent an edge.
     *
     * @param {unknown} item Raw item.
     * @returns {boolean} True when relation-like.
     */
    #looksLikeRelation(item) {
        return Boolean(item && typeof item === "object" && (
            ("subject" in item && "object" in item) ||
            ("source" in item && "target" in item) ||
            ("from" in item && "to" in item) ||
            ("head" in item && "tail" in item)
        ));
    }

    /**
     * Return whether a payload appears to represent a class node.
     *
     * @param {unknown} item Raw item.
     * @returns {boolean} True when class-like.
     */
    #looksLikeClass(item) {
        if (!item || typeof item !== "object") {
            return false;
        }
        const marker = String(
            item.entity_type || item.node_type || item.type || item.kind || item.category || item.entity_class || item.class || ""
        ).toLowerCase();
        const identifier = String(item.entity_id || item.id || "").toLowerCase();
        return marker === "cls"
            || marker === "class"
            || marker === "clase"
            || /^cls[:_-]/.test(identifier);
    }

    /**
     * Resolve one readable item label.
     *
     * @param {unknown} item Raw item.
     * @param {number} index Fallback index.
     * @returns {string} Label.
     */
    #itemLabel(item, index) {
        if (typeof item === "string") {
            return item;
        }
        if (item && typeof item === "object") {
            return item.canonical_name || item.name || item.title || item.entity || item.id || `Node ${index + 1}`;
        }
        return String(item || "");
    }

    /**
     * Resolve a context label from graph metadata.
     *
     * @param {object} item Raw item.
     * @param {string} sourcePath Source path.
     * @returns {string} Context label.
     */
    #contextFromRecord(item, sourcePath) {
        if (sourcePath.includes("/")) {
            const parts = sourcePath.split("/").filter(Boolean);
            const memoryIndex = parts.indexOf("memory");
            if (memoryIndex >= 0) {
                return parts.slice(memoryIndex, -1).join("/") || "memory";
            }
            return parts.slice(0, -1).join("/") || parts[0] || "knowledge";
        }
        return String(item?.source_type || item?.domain || item?.kind || "knowledge");
    }

    /**
     * Resolve a domain from graph metadata.
     *
     * @param {object} item Raw item.
     * @param {string} sourcePath Source path.
     * @returns {string} Domain label.
     */
    #domainFromRecord(item, sourcePath) {
        const normalizedSourcePath = String(sourcePath || "").replaceAll("\\", "/");
        if (normalizedSourcePath.includes("/")) {
            const parts = normalizedSourcePath.split("/").filter(Boolean);
            const memoryIndex = parts.indexOf("memory");
            if (memoryIndex >= 0 && parts[memoryIndex + 1]) {
                const domainParts = parts.slice(memoryIndex + 1);
                const leafIndex = domainParts.length - 1;
                domainParts[leafIndex] = domainParts[leafIndex].replace(/\.[^.]+$/, "");
                return domainParts.filter(Boolean).join(".") || "memory";
            }
            return parts[0] || "knowledge";
        }
        return String(item?.domain || item?.source_domain || item?.source_type || "knowledge");
    }

    /**
     * Prepare graph nodes and edges from current records and filters.
     *
     * @returns {void}
     */
    #prepareGraph() {
        const records = this.#mergeScopeRecords(this.#filteredRecords());
        const domainGroups = new Map();
        records.forEach(record => {
            if (!domainGroups.has(record.domain)) {
                domainGroups.set(record.domain, []);
            }
            domainGroups.get(record.domain).push(record);
        });
        const domains = Array.from(domainGroups.keys()).sort();
        this.#nodes = records.map((record, index) => this.#nodeFromRecord(record, index, domains, domainGroups));
        this.#edges = this.#edgesFromRelations(records);
        this.#viewportNodeIds.clear();
        this.#viewportBadgeSignature = "";
        this.#applyConnectivitySizing();
        this.#layoutGraphByNeighbors();
        this.#reconcileRegionEdges();
    }

    /** Merge same-name identities across scopes so their relations share one visible node. */
    #mergeScopeRecords(records) {
        const merged = new Map();
        records.forEach(record => {
            const key = `${record.visualType}:${record.label.toLowerCase()}`;
            const current = merged.get(key);
            if (!current) {
                merged.set(key, {
                    ...record,
                    aliases: [record.id],
                    knowledgeScopes: [record.knowledgeScope],
                    sources: [record.source]
                });
                return;
            }
            current.aliases.push(record.id);
            if (!current.knowledgeScopes.includes(record.knowledgeScope)) current.knowledgeScopes.push(record.knowledgeScope);
            if (!current.sources.includes(record.source)) current.sources.push(record.source);
            current.knowledgeScope = current.knowledgeScopes.length > 1 ? "all" : current.knowledgeScopes[0];
            current.source = current.sources.filter(Boolean).join(" · ");
            if (record.description.length > current.description.length) current.description = record.description;
        });
        return [...merged.values()];
    }

    /**
     * Convert one record into a graph node.
     *
     * @param {object} record Graph record.
     * @param {number} index Global index.
     * @param {string[]} domains Domain list.
     * @param {Map<string, object[]>} domainGroups Grouped records.
     * @returns {object} Graph node.
     */
    #nodeFromRecord(record, index, domains, domainGroups) {
        const domainIndex = Math.max(domains.indexOf(record.domain), 0);
        const group = domainGroups.get(record.domain) || [];
        const localIndex = Math.max(group.findIndex(item => item.id === record.id), 0);
        const domainAngle = (Math.PI * 2 * domainIndex) / Math.max(domains.length, 1);
        const localAngle = domainAngle + (localIndex / Math.max(group.length, 1)) * 0.96;
        const radius = 130 + (localIndex % 11) * 24 + domainIndex * 10;
        return {
            ...record,
            x: Math.cos(localAngle) * radius,
            y: Math.sin(localAngle) * radius,
            radius: this.#mode === "classes" ? 15 : 11,
            color: this.#domainColor(record.domain),
            expanded: false
        };
    }

    /** Return a stable color that is never reused by another domain or superdomain. */
    #domainColor(domain) {
        const normalized = String(domain || "knowledge").toLowerCase();
        const existing = this.#domainColors.get(normalized);
        if (existing) {
            return existing;
        }
        const hash = [...normalized].reduce((total, character) => ((total * 31) + character.charCodeAt(0)) >>> 0, 0);
        let offset = 0;
        let color = "";
        do {
            const hue = ((hash % 3600) / 10 + offset * 137.508) % 360;
            const saturation = 68 + ((hash + offset * 7) % 17);
            const lightness = 52 + ((hash + offset * 11) % 25);
            color = `hsl(${hue.toFixed(1)} ${saturation}% ${lightness}%)`;
            offset += 1;
        } while (this.#usedDomainColors.has(color));
        this.#domainColors.set(normalized, color);
        this.#usedDomainColors.add(color);
        return color;
    }

    /**
     * Build edges from relation data returned by the CLI facade.
     *
     * @param {object[]} records Current node records.
     * @returns {object[]} Edges.
     */
    #edgesFromRelations(records, relations = null) {
        const nodeById = new Map();
        records.forEach(record => {
            nodeById.set(record.id, record);
            (record.aliases || []).forEach(alias => nodeById.set(alias, record));
        });
        const nodeByLabel = new Map(records.map(record => [`${record.domain}:${record.label}`.toLowerCase(), record]));
        const domainRelations = relations || this.#relations.filter(relation => this.#recordMatchesTree(relation));
        const edges = domainRelations
            .map((relation, index) => {
                const from = this.#nodeForRelationEnd(nodeById, nodeByLabel, relation, "from");
                const to = this.#nodeForRelationEnd(nodeById, nodeByLabel, relation, "to");
                if (!from || !to) {
                    return null;
                }
                return {
                    ...relation,
                    id: relation.id || `relation-edge-${index}`,
                    from: from.id,
                    to: to.id
                };
            })
            .filter(Boolean);
        return edges;
    }

    /**
     * Resolve a relation endpoint against visible node records.
     *
     * @param {Map<string, object>} nodeById Visible nodes by id.
     * @param {Map<string, object>} nodeByLabel Visible nodes by domain and label.
     * @param {object} relation Relation record.
     * @param {"from"|"to"} side Endpoint side.
     * @returns {object|null} Matching node.
     */
    #nodeForRelationEnd(nodeById, nodeByLabel, relation, side) {
        const id = String(relation[side] || "");
        const entityId = side === "from" ? relation.fromEntityId : relation.toEntityId;
        const label = side === "from" ? relation.fromLabel : relation.toLabel;
        const classHint = side === "from" ? relation.fromClass : relation.toClass;
        return nodeById.get(id) ||
            nodeById.get(String(entityId || "")) ||
            nodeByLabel.get(`${relation.domain}:${label}`.toLowerCase()) ||
            nodeByLabel.get(`${relation.domain}:${classHint}`.toLowerCase()) ||
            null;
    }

    /**
     * Position nodes through neighbor expansion when relations exist, otherwise by domain grid.
     *
     * @returns {void}
     */
    #layoutGraphByNeighbors() {
        const linkedIds = new Set(this.#edges.flatMap(edge => [edge.from, edge.to]));
        const linkedNodes = this.#nodes.filter(node => linkedIds.has(node.id));
        const freeNodes = this.#nodes.filter(node => !linkedIds.has(node.id));
        const footprints = this.#nodeLayoutFootprints();
        if (linkedNodes.length) {
            this.#layoutConnectedNodes(linkedNodes, 0, footprints);
        }
        const startY = linkedNodes.length ? 420 : 0;
        this.#layoutDomainGrid(freeNodes, startY, footprints);
    }

    /** Estimate each node's visual footprint from radius, labels, connectivity, and predicates. */
    #nodeLayoutFootprints() {
        const degrees = this.#nodeDegrees();
        const longestPredicate = new Map(this.#nodes.map(node => [node.id, 0]));
        this.#edges.forEach(edge => {
            const length = String(edge.label || "").length;
            longestPredicate.set(edge.from, Math.max(longestPredicate.get(edge.from) || 0, length));
            longestPredicate.set(edge.to, Math.max(longestPredicate.get(edge.to) || 0, length));
        });
        return new Map(this.#nodes.map(node => {
            const degree = degrees.get(node.id) || 0;
            const connectivity = Math.min(48, Math.sqrt(degree) * 8);
            const nodeLabelWidth = Math.min(240, Math.max(62, String(node.label || "").length * 7.2 + 24));
            const relationLabelWidth = Math.min(180, (longestPredicate.get(node.id) || 0) * 6.2);
            return [node.id, {
                width: Math.max(node.radius * 2 + 24, nodeLabelWidth) + connectivity + relationLabelWidth * 0.16,
                height: node.radius * 2 + 32 + Math.min(30, connectivity * 0.55),
                gap: 26 + Math.min(28, relationLabelWidth * 0.12) + Math.min(18, connectivity * 0.3),
                relationLabelWidth
            }];
        }));
    }

    /**
     * Expand connected components by neighbor depth.
     *
     * @param {object[]} nodes Connected nodes.
     * @param {number} startY Vertical offset.
     * @returns {void}
     */
    #layoutConnectedNodes(nodes, startY, footprints) {
        const byId = new Map(nodes.map(node => [node.id, node]));
        const adjacency = this.#adjacencyMap(byId);
        const visited = new Set();
        const components = [];
        nodes.forEach(node => {
            if (visited.has(node.id)) {
                return;
            }
            components.push(this.#componentFromNode(node.id, adjacency, visited));
        });
        const rowWidth = Math.min(4200, Math.max(2200, Math.sqrt(nodes.length) * 210));
        let cursorX = 0;
        let cursorY = startY;
        let packedRowHeight = 0;
        components.sort((left, right) => right.length - left.length).forEach(component => {
            this.#positionComponent(component, adjacency, byId, 0, 0, footprints);
            const bounds = this.#componentBounds(component, byId, footprints);
            if (cursorX && cursorX + bounds.width > rowWidth) {
                cursorX = 0;
                cursorY += packedRowHeight + 220;
                packedRowHeight = 0;
            }
            this.#translateComponent(component, byId, cursorX - bounds.minX, cursorY - bounds.minY);
            cursorX += bounds.width + 220;
            packedRowHeight = Math.max(packedRowHeight, bounds.height);
        });
    }

    /** Return a component rectangle that includes node and label footprints. */
    #componentBounds(component, byId, footprints) {
        const bounds = component.reduce((result, id) => {
            const node = byId.get(id);
            const footprint = footprints.get(id);
            if (!node || !footprint) return result;
            return {
                minX: Math.min(result.minX, node.x - footprint.width / 2),
                maxX: Math.max(result.maxX, node.x + footprint.width / 2),
                minY: Math.min(result.minY, node.y - footprint.height / 2),
                maxY: Math.max(result.maxY, node.y + footprint.height / 2)
            };
        }, { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });
        return {
            ...bounds,
            width: Math.max(1, bounds.maxX - bounds.minX),
            height: Math.max(1, bounds.maxY - bounds.minY)
        };
    }

    /** Translate every node in one already-positioned connected component. */
    #translateComponent(component, byId, deltaX, deltaY) {
        component.forEach(id => {
            const node = byId.get(id);
            if (!node) return;
            node.x += deltaX;
            node.y += deltaY;
        });
    }

    /**
     * Build adjacency from visible edges.
     *
     * @param {Map<string, object>} byId Visible nodes by id.
     * @returns {Map<string, Set<string>>} Adjacency map.
     */
    #adjacencyMap(byId) {
        const adjacency = new Map([...byId.keys()].map(id => [id, new Set()]));
        this.#edges.forEach(edge => {
            if (!byId.has(edge.from) || !byId.has(edge.to)) {
                return;
            }
            adjacency.get(edge.from).add(edge.to);
            adjacency.get(edge.to).add(edge.from);
        });
        return adjacency;
    }

    /**
     * Collect one connected component.
     *
     * @param {string} rootId Component root node id.
     * @param {Map<string, Set<string>>} adjacency Adjacency map.
     * @param {Set<string>} visited Visited node ids.
     * @returns {string[]} Component ids.
     */
    #componentFromNode(rootId, adjacency, visited) {
        const queue = [rootId];
        const component = [];
        visited.add(rootId);
        while (queue.length) {
            const current = queue.shift();
            component.push(current);
            [...(adjacency.get(current) || [])].forEach(next => {
                if (!visited.has(next)) {
                    visited.add(next);
                    queue.push(next);
                }
            });
        }
        return component;
    }

    /**
     * Position one component around the highest-degree node.
     *
     * @param {string[]} component Component node ids.
     * @param {Map<string, Set<string>>} adjacency Adjacency map.
     * @param {Map<string, object>} byId Visible nodes by id.
     * @param {number} offsetX Component horizontal offset.
     * @param {number} offsetY Component vertical offset.
     * @param {Map<string, object>} footprints Estimated node footprints.
     * @returns {void}
     */
    #positionComponent(component, adjacency, byId, offsetX, offsetY, footprints) {
        const rootId = [...component].sort((left, right) => (adjacency.get(right)?.size || 0) - (adjacency.get(left)?.size || 0))[0];
        const levels = this.#neighborLevels(rootId, adjacency);
        let previousRight = null;
        [...levels.entries()].sort(([left], [right]) => left - right).forEach(([, levelIds]) => {
            const ids = [...levelIds].sort((left, right) => {
                const degreeDifference = (adjacency.get(right)?.size || 0) - (adjacency.get(left)?.size || 0);
                return degreeDifference || String(byId.get(left)?.label || "").localeCompare(String(byId.get(right)?.label || ""));
            });
            const rowsPerColumn = Math.max(1, Math.ceil(Math.sqrt(ids.length * 1.6)));
            const columnCount = Math.ceil(ids.length / rowsPerColumn);
            const maxWidth = Math.max(...ids.map(id => footprints.get(id)?.width || 80));
            const maxPredicateWidth = Math.max(0, ...ids.map(id => footprints.get(id)?.relationLabelWidth || 0));
            const columnGap = 34 + Math.min(38, maxPredicateWidth * 0.18);
            const layerGap = 90 + Math.min(150, maxPredicateWidth * 0.72);
            const bandWidth = columnCount * maxWidth + Math.max(0, columnCount - 1) * columnGap;
            const bandLeft = previousRight === null ? offsetX - bandWidth / 2 : previousRight + layerGap;
            for (let column = 0; column < columnCount; column += 1) {
                const columnIds = ids.slice(column * rowsPerColumn, (column + 1) * rowsPerColumn);
                const totalHeight = columnIds.reduce((total, id, index) => {
                    const footprint = footprints.get(id) || { height: 70, gap: 28 };
                    return total + footprint.height + (index ? footprint.gap : 0);
                }, 0);
                let cursorY = offsetY - totalHeight / 2;
                columnIds.forEach((id, index) => {
                    const node = byId.get(id);
                    const footprint = footprints.get(id) || { height: 70, gap: 28 };
                    if (!node) return;
                    if (index) cursorY += footprint.gap;
                    node.x = bandLeft + column * (maxWidth + columnGap) + maxWidth / 2;
                    node.y = cursorY + footprint.height / 2;
                    cursorY += footprint.height;
                });
            }
            previousRight = bandLeft + bandWidth;
        });
    }

    /**
     * Group neighbor ids by breadth-first depth.
     *
     * @param {string} rootId Root node id.
     * @param {Map<string, Set<string>>} adjacency Adjacency map.
     * @returns {Map<number, string[]>} Level groups.
     */
    #neighborLevels(rootId, adjacency) {
        const levels = new Map();
        const visited = new Set([rootId]);
        const queue = [{ id: rootId, depth: 0 }];
        while (queue.length) {
            const current = queue.shift();
            if (!levels.has(current.depth)) {
                levels.set(current.depth, []);
            }
            levels.get(current.depth).push(current.id);
            [...(adjacency.get(current.id) || [])].sort().forEach(next => {
                if (!visited.has(next)) {
                    visited.add(next);
                    queue.push({ id: next, depth: current.depth + 1 });
                }
            });
        }
        return levels;
    }

    /**
     * Position unlinked nodes in a wide domain-aware grid.
     *
     * @param {object[]} nodes Free nodes.
     * @param {number} startY Vertical offset.
     * @returns {void}
     */
    #layoutDomainGrid(nodes, startY, footprints) {
        const groups = new Map();
        nodes.forEach(node => {
            if (!groups.has(node.domain)) {
                groups.set(node.domain, []);
            }
            groups.get(node.domain).push(node);
        });
        let cursorX = 0;
        let cursorY = startY;
        let rowHeight = 0;
        [...groups.entries()].sort(([left], [right]) => left.localeCompare(right)).forEach(([, group], groupIndex) => {
            const columns = Math.ceil(Math.sqrt(group.length));
            const columnWidth = Math.max(116, ...group.map(node => (footprints.get(node.id)?.width || 80) + 30));
            const cellHeight = Math.max(94, ...group.map(node => {
                const footprint = footprints.get(node.id) || { height: 64, gap: 28 };
                return footprint.height + footprint.gap;
            }));
            const groupWidth = columns * columnWidth;
            const groupRows = Math.ceil(group.length / columns);
            const groupHeight = groupRows * cellHeight;
            if (groupIndex && groupIndex % 3 === 0) {
                cursorX = 0;
                cursorY += rowHeight + 160;
                rowHeight = 0;
            }
            group.forEach((node, index) => {
                node.x = cursorX + (index % columns) * columnWidth;
                node.y = cursorY + Math.floor(index / columns) * cellHeight;
            });
            cursorX += groupWidth + 160;
            rowHeight = Math.max(rowHeight, groupHeight);
        });
    }

    /**
     * Return records after domain, mode, and query filters.
     *
     * @returns {object[]} Filtered records.
     */
    #filteredRecords() {
        const needle = this.#query.toLowerCase();
        const visualType = this.#treeVisualType || (this.#mode === "classes" ? "class" : this.#mode === "entities" ? "entity" : "");
        const projection = this.#treeProjection(
            this.#domain,
            this.#treeScope,
            this.#sourceKind,
            this.#sourcePath,
            this.#treeVisualType
        );
        return projection.records
            .filter(record => this.#selectedScopes.has(record.knowledgeScope))
            .filter(record => !visualType || record.visualType === visualType)
            .filter(record => !needle || `${record.label} ${record.description} ${record.domain} ${record.context}`.toLowerCase().includes(needle));
    }

    /**
     * Return whether a domain is active under the selected tree node.
     *
     * @param {string} domain Domain path.
     * @returns {boolean} True when visible.
     */
    #recordMatchesTree(record) {
        if (!this.#selectedScopes.has(record.knowledgeScope)) {
            return false;
        }
        return this.#recordMatchesTreeSelection(
            record,
            this.#domain,
            this.#treeScope,
            this.#sourceKind,
            this.#sourcePath,
            this.#treeVisualType
        );
    }

    /** Apply one explicit inclusive tree selection without depending on current UI state. */
    #recordMatchesTreeSelection(record, domain, scope = "", sourceKind = "", sourcePath = "", visualType = "") {
        if (scope && scope !== "all" && record.knowledgeScope !== scope) return false;
        if (visualType && record.visualType && record.visualType !== visualType) return false;
        if (sourceKind && !this.#recordMatchesSourceKind(record, sourceKind, scope)) return false;
        const selectedSource = String(sourcePath || "").replaceAll("\\", "/").toLowerCase();
        if (selectedSource) {
            const source = String(record.source || "").replaceAll("\\", "/").toLowerCase();
            if (!source.includes(selectedSource) && !selectedSource.includes(source)) return false;
        }
        return domain === "all" || record.domain === domain || record.domain.startsWith(`${domain}.`);
    }

    /** Classify one graph record into mutually exclusive canonical source families. */
    #recordMatchesSourceKind(record, sourceKind, scope = "") {
        const source = String(record.source || "").replaceAll("\\", "/").toLowerCase();
        const domain = String(record.domain || "").toLowerCase();
        const isPicture = domain === "pictures" || domain.startsWith("pictures.")
            || this.#pictures.some(picture => source.endsWith(String(picture.relative_path || "").replaceAll("\\", "/").toLowerCase()));
        const isMessage = domain === "messages" || domain.startsWith("messages.") || source.includes("message");
        const isLog = domain === "logs" || domain.startsWith("logs.") || source.includes("/logs/");
        if (sourceKind === "pictures") return isPicture;
        if (sourceKind === "messages") return isMessage;
        if (sourceKind === "logs") return isLog;
        if (sourceKind === "memory") {
            return scope === "global" ? !isPicture : !isLog && !isMessage && !isPicture;
        }
        return true;
    }

    /**
     * Return available domains from loaded records and relations.
     *
     * @returns {string[]} Domain labels.
     */
    #domains(scope = "") {
        return [...new Set([
            ...this.#records.filter(record => !scope || record.knowledgeScope === scope).map(record => record.domain),
            ...this.#relations.filter(relation => !scope || relation.knowledgeScope === scope).map(relation => relation.domain)
        ].filter(Boolean))].sort();
    }

    /**
     * Return domain hierarchy parts.
     *
     * @param {string} domain Domain path.
     * @returns {string[]} Parts.
     */
    #domainParts(domain) {
        return String(domain || "knowledge").split(/[./\\]+/).filter(Boolean);
    }

    /**
     * Count records under one domain branch.
     *
     * @param {string} domain Domain path.
     * @returns {number} Count.
     */
    #countRecordsInDomain(domain, scope = "") {
        const domainMatches = record => domain === "all" || record.domain === domain || record.domain.startsWith(`${domain}.`);
        const scopeMatches = record => !scope || record.knowledgeScope === scope;
        return this.#records.filter(record => scopeMatches(record) && domainMatches(record)).length +
            this.#relations.filter(record => scopeMatches(record) && domainMatches(record)).length;
    }

    /** Return visible entity/relation counts using the canvas' exact projection rules. */
    #graphCountLabel(domain, scope = "", sourceKind = "", sourcePath = "", visualType = "") {
        const projection = this.#treeProjection(domain, scope, sourceKind, sourcePath, visualType);
        const records = this.#mergeScopeRecords(projection.records);
        const relations = projection.relations;
        const edges = this.#edgesFromRelations(records, relations);
        return `E: ${records.length} R: ${edges.length}`;
    }

    /** Include relation endpoints in virtual source projections without changing their canonical ownership. */
    #treeProjection(domain, scope = "", sourceKind = "", sourcePath = "", visualType = "") {
        const matches = record => this.#recordMatchesTreeSelection(record, domain, scope, sourceKind, sourcePath, visualType);
        const relations = this.#relations.filter(matches);
        const records = this.#records.filter(matches);
        if (!sourceKind && !sourcePath) return { records, relations };
        const endpointIds = new Set(relations.flatMap(relation => [String(relation.from), String(relation.to)]));
        const endpointLabels = new Set(relations.flatMap(relation => [
            String(relation.fromLabel || "").toLowerCase(),
            String(relation.toLabel || "").toLowerCase()
        ]));
        const includedIds = new Set(records.map(record => String(record.id)));
        this.#records.forEach(record => {
            if (scope && scope !== "all" && record.knowledgeScope !== scope) return;
            if (visualType && record.visualType !== visualType) return;
            const connected = endpointIds.has(String(record.id))
                || endpointIds.has(String(record.entityId))
                || endpointLabels.has(String(record.label || "").toLowerCase());
            if (connected && !includedIds.has(String(record.id))) {
                records.push(record);
                includedIds.add(String(record.id));
            }
        });
        return { records, relations };
    }

    /**
     * Apply local reactive filters without a new CLI call.
     *
     * @returns {void}
     */
    async #applyFilters() {
        this.#beginGraphBusy("Filtering graph");
        await this.#waitForGraphPaint();
        try {
            this.#readControls();
            if (this.#treeScope !== "all" && !this.#selectedScopes.has(this.#treeScope)) {
                this.#selectedTreePath = "";
                this.#treeScope = "all";
                this.#domain = "all";
                this.#sourceKind = "";
                this.#sourcePath = "";
                this.#treeVisualType = "";
            }
            this.#needsViewportFit = true;
            this.#prepareGraph();
            this.#render();
        } finally {
            this.#endGraphBusy();
        }
    }

    /** Apply one tree selection without rebuilding the complete Explorer surface. */
    async #applyTreeSelection() {
        this.#beginGraphBusy("Focusing graph source");
        await this.#waitForGraphPaint();
        try {
            this.#resetGraphRegion();
            this.#needsViewportFit = true;
            this.#prepareGraph();
            this.#syncDomainTreeSelection();
            this.#drawCanvas();
            this.#renderInspector();
        } finally {
            this.#endGraphBusy();
        }
    }

    /** Update selected tree-row styling while preserving expansion and scroll state. */
    #syncDomainTreeSelection() {
        const tree = this.querySelector("[data-role='knowledge-domain-tree']");
        tree?.querySelectorAll("[data-tree-path]").forEach(button => {
            const selected = button.getAttribute("data-tree-path") === this.#selectedTreePath;
            button.classList.toggle("is-active", selected);
            button.closest("[role='treeitem']")?.setAttribute("aria-selected", String(selected));
        });
    }

    /**
     * Bind DOM events.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelector("[data-action='show-records']")?.addEventListener("click", () => this.#showRecords(true));
        this.querySelector("[data-action='query-records']")?.addEventListener("click", () => this.#queryRecords());
        this.querySelector("[data-action='review-deltas']")?.addEventListener("click", () => this.#reviewDeltas());
        this.querySelector("[data-action='fit-graph']")?.addEventListener("click", () => {
            this.#resetVisibleGraphViewport();
        });
        this.querySelector("[data-action='navigate-region-back']")?.addEventListener("click", () => {
            this.#navigateBackGraphRegion();
        });
        this.querySelector(".filter-menu")?.addEventListener("toggle", event => {
            this.#filtersOpen = event.currentTarget.open;
        });
        this.querySelectorAll("[data-action='select-domain']").forEach(button => {
            button.addEventListener("click", () => {
                const domain = button.getAttribute("data-domain-path") || "all";
                this.#domain = domain;
                this.#resetGraphRegion();
                if (this.#expandedDomains.has(domain)) {
                    this.#expandedDomains.delete(domain);
                } else {
                    this.#expandedDomains.add(domain);
                }
                this.#applyFilters();
            });
        });
        this.querySelector("[data-role='kg-query']")?.addEventListener("input", () => {
            this.#readControls();
            this.#needsViewportFit = true;
            this.#prepareGraph();
            this.#drawCanvas();
            this.#renderInspector();
        });
        this.querySelector("[data-role='kg-query']")?.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                this.#queryRecords();
            }
        });
        this.querySelectorAll("[data-filter-kind='kg-scope']").forEach(input => {
            input.addEventListener("change", () => this.#applyFilters());
        });
        this.querySelectorAll("[data-filter-kind='kg-mode']").forEach(input => {
            input.addEventListener("change", () => this.#applyFilters());
        });
        this.#bindInspectorButtons();
    }

    /**
     * Bind inspector relation/node selection buttons.
     *
     * @returns {void}
     */
    #bindInspectorButtons() {
        this.querySelectorAll("[data-action='open-detail-source']").forEach(button => {
            button.addEventListener("click", () => {
                const route = button.getAttribute("data-route") || "";
                if (route === "pictures") {
                    this.#state?.setRouteTarget?.("pictures", { pictureId: button.getAttribute("data-picture-id") || "" });
                    return;
                }
                const messageId = button.getAttribute("data-message-id") || "";
                const message = this.#messages.find(item => String(item.id) === messageId);
                const session = this.#messageSessions.find(item => item.date === message?.date && item.chatId === message?.chat_id);
                this.#state?.setRouteTarget?.("messages", { messageId, sessionId: session?.id || "" });
            });
        });
        this.querySelectorAll("[data-action='focus-node']").forEach(button => {
            button.addEventListener("pointerenter", () => {
                this.#showHoveredEndpoint(button.getAttribute("data-node-id") || "");
            });
            button.addEventListener("pointerleave", () => this.#showHoveredEndpoint(""));
            button.addEventListener("click", () => this.#focusNode(button.getAttribute("data-node-id") || "", false));
        });
        this.querySelectorAll("[data-action='resolve-description-entity']").forEach(button => {
            button.addEventListener("click", () => this.#focusEntityByLabel(button.getAttribute("data-entity-label") || ""));
        });
        this.querySelectorAll("[data-action='select-node']").forEach(button => {
            button.addEventListener("click", () => {
                this.#focusNode(button.getAttribute("data-node-id") || "", false);
            });
        });
        this.querySelectorAll("[data-action='select-relation']").forEach(button => {
            button.addEventListener("pointerenter", () => {
                this.#showHoveredRelation(button.getAttribute("data-relation-id") || "");
            });
            button.addEventListener("pointerleave", () => {
                this.#showHoveredRelation("");
            });
            button.addEventListener("click", () => {
                this.#selectRelation(button.getAttribute("data-relation-id") || "");
            });
        });
        this.#bindRelationEndpointButtons();
    }

    /** Bind transient and persistent navigation on relation endpoint badges. */
    #bindRelationEndpointButtons() {
        this.querySelectorAll("[data-action='navigate-relation-endpoint']").forEach(button => {
            const nodeId = button.getAttribute("data-node-id") || "";
            button.addEventListener("pointerenter", () => this.#showHoveredEndpoint(nodeId));
            button.addEventListener("pointerleave", () => this.#showHoveredEndpoint(""));
            button.addEventListener("click", () => this.#navigateRelationEndpoint(nodeId));
        });
    }

    /** Update the existing relation preview and camera from one transient sidepanel hover. */
    #showHoveredRelation(relationId) {
        const relation = this.#edges.find(edge => edge.id === relationId);
        if (relation) {
            if (!this.#hoveredRelationId) {
                this.#relationHoverViewport = { ...this.#viewport };
            }
            this.#hoveredRelationId = relation.id;
            this.#hoveredNodeId = "";
            this.#animateCameraToRelation(relation, Math.max(this.#viewport.scale, 1.35));
        } else {
            this.#hoveredRelationId = "";
            this.#hoveredNodeId = "";
            if (this.#relationHoverViewport) {
                const previousViewport = this.#relationHoverViewport;
                this.#relationHoverViewport = null;
                this.#animateViewport(previousViewport);
            } else {
                this.#drawCanvas();
            }
        }
        const relationPreviewHost = this.querySelector("[data-role='relation-preview-host']");
        if (relationPreviewHost) {
            relationPreviewHost.innerHTML = this.#renderRelationPreview();
        }
        this.#bindRelationEndpointButtons();
    }

    /** Preview one endpoint node while preserving the camera that preceded badge hover. */
    #showHoveredEndpoint(nodeId) {
        const node = this.#nodes.find(item => item.id === nodeId);
        if (node) {
            if (!this.#hoveredNodeId) {
                this.#badgeHoverViewport = { ...this.#viewport };
            }
            this.#viewportBadgeRankingFrozen = true;
            clearTimeout(this.#viewportInspectorTimer);
            this.#hoveredNodeId = node.id;
            this.#animateCameraToNode(node, Math.max(this.#viewport.scale, 1.35));
            return;
        }
        this.#hoveredNodeId = "";
        if (this.#badgeHoverViewport) {
            const previousViewport = this.#badgeHoverViewport;
            this.#badgeHoverViewport = null;
            this.#animateViewport(previousViewport, () => this.#releaseViewportBadgeRanking());
        } else {
            this.#releaseViewportBadgeRanking();
            this.#drawCanvas();
        }
    }

    /** Resume viewport-driven badge ranking after a transient entity preview fully returns. */
    #releaseViewportBadgeRanking() {
        this.#viewportBadgeRankingFrozen = false;
        this.#syncViewportBadgeCandidates();
    }

    /** Persist camera navigation to one relation endpoint without replacing relation selection. */
    #navigateRelationEndpoint(nodeId) {
        const node = this.#nodes.find(item => item.id === nodeId);
        if (!node) {
            return;
        }
        this.#badgeHoverViewport = null;
        this.#viewportBadgeRankingFrozen = false;
        this.#hoveredNodeId = node.id;
        this.#animateCameraToNode(node, Math.max(this.#viewport.scale, 1.35));
    }

    /** Resolve one description badge to the most connected matching graph node. */
    #focusEntityByLabel(label) {
        const normalized = String(label || "").trim().toLowerCase();
        if (!normalized) return false;
        const degrees = this.#nodeDegrees();
        const match = this.#nodes
            .filter(node => String(node.label || "").trim().toLowerCase() === normalized)
            .sort((left, right) => (degrees.get(right.id) || 0) - (degrees.get(left.id) || 0))[0];
        if (!match) return false;
        this.#focusNode(match.id, false);
        return true;
    }

    /** Focus a route-targeted entity after the graph has been prepared. */
    #resolvePendingEntity() {
        if (!this.#pendingEntityLabel) return;
        const label = this.#pendingEntityLabel;
        if (this.#focusEntityByLabel(label)) this.#pendingEntityLabel = "";
    }

    /**
     * Bind canvas drawing and pointer interaction.
     *
     * @returns {void}
     */
    #bindCanvas() {
        const canvas = this.querySelector("[data-role='knowledge-canvas']");
        if (!(canvas instanceof HTMLCanvasElement)) {
            return;
        }
        this.#resizeObserver?.disconnect();
        this.#resizeObserver = new ResizeObserver(() => this.#drawCanvas());
        this.#resizeObserver.observe(canvas);
        canvas.addEventListener("pointerdown", event => this.#onPointerDown(event, canvas));
        canvas.addEventListener("pointermove", event => this.#onPointerMove(event, canvas));
        canvas.addEventListener("pointerup", event => this.#onPointerUp(event, canvas));
        canvas.addEventListener("pointerleave", event => this.#onPointerUp(event, canvas));
        canvas.addEventListener("wheel", event => this.#onWheel(event, canvas), { passive: false });
        canvas.addEventListener("dblclick", event => {
            event.preventDefault();
            this.#resetVisibleGraphViewport();
        });
        requestAnimationFrame(() => this.#drawCanvas());
    }

    /**
     * Draw nodes and edges onto the canvas.
     *
     * @returns {void}
     */
    #drawCanvas() {
        const canvas = this.querySelector("[data-role='knowledge-canvas']");
        if (!(canvas instanceof HTMLCanvasElement)) {
            return;
        }
        const rect = canvas.getBoundingClientRect();
        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.max(1, Math.floor(rect.width * ratio));
        canvas.height = Math.max(1, Math.floor(rect.height * ratio));
        const context = canvas.getContext("2d");
        if (!context) {
            return;
        }
        if (this.#needsViewportFit) {
            this.#fitViewport(rect);
        }
        this.#updateRenderFrustum(rect);
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        context.clearRect(0, 0, rect.width, rect.height);
        this.#applyConnectivitySizing(this.#focusGraph());
        context.translate((rect.width / 2) + this.#viewport.x, (rect.height / 2) + this.#viewport.y);
        context.scale(this.#viewport.scale, this.#viewport.scale);
        this.#drawEdges(context);
        this.#drawNodes(context);
        this.#syncViewportBadgeCandidates();
    }

    /**
     * Fit graph bounds into the canvas viewport.
     *
     * @param {DOMRect} rect Canvas bounds.
     * @returns {void}
     */
    #fitViewport(rect) {
        this.#viewport = this.#fittedViewport(rect);
        this.#needsViewportFit = false;
    }

    /**
     * Calculate the centered fit camera for the complete graph or active subregion.
     *
     * @param {DOMRect} rect Canvas bounds.
     * @returns {{x: number, y: number, scale: number}} Fitted camera.
     */
    #fittedViewport(rect) {
        const focus = this.#focusGraph();
        if (focus) {
            this.#layoutFocusedRegion(focus);
        }
        const visibleNodes = focus
            ? this.#nodes.filter(node => focus.nodeIds.has(node.id))
            : this.#nodes;
        if (!visibleNodes.length) {
            return { x: 0, y: 0, scale: 1 };
        }
        const bounds = visibleNodes.reduce((acc, node) => ({
            minX: Math.min(acc.minX, node.x - node.radius - 60),
            maxX: Math.max(acc.maxX, node.x + node.radius + 60),
            minY: Math.min(acc.minY, node.y - node.radius - 42),
            maxY: Math.max(acc.maxY, node.y + node.radius + 42)
        }), { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });
        const width = Math.max(1, bounds.maxX - bounds.minX);
        const height = Math.max(1, bounds.maxY - bounds.minY);
        const maximumScale = focus ? 1.8 : 1.15;
        const scale = Math.min(maximumScale, Math.max(0.005, Math.min((rect.width - 72) / width, (rect.height - 72) / height)));
        return {
            x: -((bounds.minX + bounds.maxX) / 2) * scale,
            y: -((bounds.minY + bounds.maxY) / 2) * scale,
            scale
        };
    }

    /** Compute the current canvas viewport in graph coordinates. */
    #updateRenderFrustum(rect) {
        const scale = Math.max(this.#viewport.scale, 0.0001);
        const halfWidth = rect.width / (2 * scale);
        const halfHeight = rect.height / (2 * scale);
        const centerX = -this.#viewport.x / scale;
        const centerY = -this.#viewport.y / scale;
        const padding = 14 / scale;
        this.#renderFrustum = {
            left: centerX - halfWidth - padding,
            right: centerX + halfWidth + padding,
            top: centerY - halfHeight - padding,
            bottom: centerY + halfHeight + padding,
            centerX,
            centerY,
            radius: Math.hypot(halfWidth, halfHeight) + padding
        };
    }

    /** Return whether a node circle intersects the graph-space viewport. */
    #nodeIntersectsRenderFrustum(node) {
        const frustum = this.#renderFrustum;
        if (!frustum) {
            return true;
        }
        const radius = node.radius + (20 / Math.max(this.#viewport.scale, 0.0001));
        return node.x + radius >= frustum.left
            && node.x - radius <= frustum.right
            && node.y + radius >= frustum.top
            && node.y - radius <= frustum.bottom;
    }

    /** Refresh important-entity candidates from the exact nodes intersecting the canvas viewport. */
    #syncViewportBadgeCandidates() {
        if (this.#viewportBadgeRankingFrozen) return;
        const focus = this.#focusGraph();
        const candidates = focus
            ? this.#nodes.filter(node => focus.nodeIds.has(node.id))
            : this.#nodes;
        const visibleIds = candidates
            .filter(node => this.#nodeIntersectsRenderFrustum(node))
            .map(node => node.id);
        const signature = visibleIds.join("|") || "__empty__";
        if (signature === this.#viewportBadgeSignature) {
            return;
        }
        this.#viewportNodeIds = new Set(visibleIds);
        this.#viewportBadgeSignature = signature;
        clearTimeout(this.#viewportInspectorTimer);
        this.#viewportInspectorTimer = window.setTimeout(() => {
            if (!this.#viewportBadgeRankingFrozen && !this.#selectedNodeId && !this.#selectedRelationId) {
                this.#renderInspector();
            }
        }, 140);
    }

    /** Apply endpoint, circumscribed-radius, and exact edge culling. */
    #edgeIntersectsRenderFrustum(from, to) {
        const frustum = this.#renderFrustum;
        if (!frustum) {
            return true;
        }
        if (this.#nodeIntersectsRenderFrustum(from) || this.#nodeIntersectsRenderFrustum(to)) {
            return true;
        }
        const distance = this.#pointToSegmentDistance(
            frustum.centerX,
            frustum.centerY,
            from.x,
            from.y,
            to.x,
            to.y
        );
        if (distance > frustum.radius) {
            return false;
        }
        return this.#segmentIntersectsFrustum(from.x, from.y, to.x, to.y, frustum);
    }

    /** Test a segment against an axis-aligned viewport using Liang-Barsky. */
    #segmentIntersectsFrustum(x1, y1, x2, y2, frustum) {
        const deltaX = x2 - x1;
        const deltaY = y2 - y1;
        const p = [-deltaX, deltaX, -deltaY, deltaY];
        const q = [x1 - frustum.left, frustum.right - x1, y1 - frustum.top, frustum.bottom - y1];
        let minimum = 0;
        let maximum = 1;
        for (let index = 0; index < 4; index += 1) {
            if (p[index] === 0) {
                if (q[index] < 0) {
                    return false;
                }
                continue;
            }
            const ratio = q[index] / p[index];
            if (p[index] < 0) {
                minimum = Math.max(minimum, ratio);
            } else {
                maximum = Math.min(maximum, ratio);
            }
            if (minimum > maximum) {
                return false;
            }
        }
        return true;
    }

    /**
     * Distribute an isolated region around its selected center before fitting.
     *
     * @param {{nodeIds: Set<string>, edgeIds: Set<string>}} focus Focus ids.
     * @returns {void}
     */
    #layoutFocusedRegion(focus) {
        const focusedNodes = this.#nodes.filter(node => focus.nodeIds.has(node.id));
        if (!focusedNodes.length) {
            return;
        }
        focusedNodes.forEach(node => {
            const position = this.#regionPositions.get(node.id);
            if (position) {
                node.x = position.x;
                node.y = position.y;
            }
        });
        const newNodes = focusedNodes.filter(node => !this.#regionPositions.has(node.id));
        if (!newNodes.length) {
            return;
        }
        const selectedPosition = this.#regionPositions.get(this.#selectedNodeId);
        const anchor = selectedPosition || this.#regionCentroid();
        if (!this.#regionPositions.size) {
            const selectedIndex = newNodes.findIndex(node => node.id === this.#selectedNodeId);
            const centerIndex = selectedIndex >= 0 ? selectedIndex : 0;
            const [center] = newNodes.splice(centerIndex, 1);
            center.x = 0;
            center.y = 0;
            this.#regionPositions.set(center.id, { x: 0, y: 0 });
        }
        const baseSlot = this.#regionPositions.size;
        newNodes.forEach((node, index) => {
            const slot = baseSlot + index;
            const angle = (slot * 2.399963229728653) - (Math.PI / 2);
            const radius = 120 + (Math.floor(slot / 7) * 75);
            node.x = anchor.x + (Math.cos(angle) * radius);
            node.y = anchor.y + (Math.sin(angle) * radius);
            this.#regionPositions.set(node.id, { x: node.x, y: node.y });
        });
    }

    /** Return the centroid of persisted region positions. */
    #regionCentroid() {
        const positions = [...this.#regionPositions.values()];
        if (!positions.length) {
            return { x: 0, y: 0 };
        }
        return {
            x: positions.reduce((total, position) => total + position.x, 0) / positions.length,
            y: positions.reduce((total, position) => total + position.y, 0) / positions.length
        };
    }

    /**
     * Draw graph edges.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @returns {void}
     */
    #drawEdges(context) {
        this.#edgeLabelBounds.clear();
        const styles = getComputedStyle(this);
        const focus = this.#focusGraph();
        const orderedEdges = focus
            ? this.#edges.filter(edge => focus.edgeIds.has(edge.id))
            : this.#edges;
        const nodesById = new Map(this.#nodes.map(node => [node.id, node]));
        const connectivity = this.#connectivityMetrics(focus);
        orderedEdges.forEach(edge => {
            const from = nodesById.get(edge.from);
            const to = nodesById.get(edge.to);
            if (!from || !to || !this.#edgeIntersectsRenderFrustum(from, to)) {
                return;
            }
            const activeRelationId = this.#hoveredRelationId || this.#selectedRelationId;
            const selected = edge.id === activeRelationId;
            context.save();
            context.globalAlpha = 0.92;
            context.beginPath();
            context.moveTo(from.x, from.y);
            context.lineTo(to.x, to.y);
            context.strokeStyle = selected ? styles.getPropertyValue("--primary").trim() : styles.getPropertyValue("--border-strong").trim();
            context.lineWidth = selected ? 3.2 / this.#viewport.scale : 1.2 / this.#viewport.scale;
            context.stroke();
            this.#drawEdgeArrow(context, from, to, connectivity.score(from.id));
            this.#drawEdgeLabel(context, edge, from, to, selected);
            context.restore();
        });
    }

    /** Draw a subject-to-object arrowhead immediately before the target node. */
    #drawEdgeArrow(context, from, to, sourceRank) {
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const distance = Math.hypot(dx, dy);
        if (distance < 1) return;
        const unitX = dx / distance;
        const unitY = dy / distance;
        const scale = this.#viewport.scale;
        const tipOffset = to.radius + (3 / scale);
        const zoomFactor = 0.72 + (Math.min(scale, 2.5) * 0.28);
        const rankFactor = 0.72 + (sourceRank * 0.78);
        const arrowLength = (9 * zoomFactor * rankFactor) / scale;
        const arrowWidth = (5.2 * zoomFactor * rankFactor) / scale;
        const tipX = to.x - (unitX * tipOffset);
        const tipY = to.y - (unitY * tipOffset);
        const baseX = tipX - (unitX * arrowLength);
        const baseY = tipY - (unitY * arrowLength);
        const normalX = -unitY;
        const normalY = unitX;
        context.beginPath();
        context.moveTo(tipX, tipY);
        context.lineTo(baseX + (normalX * arrowWidth), baseY + (normalY * arrowWidth));
        context.lineTo(baseX - (normalX * arrowWidth), baseY - (normalY * arrowWidth));
        context.closePath();
        context.fillStyle = context.strokeStyle;
        context.fill();
    }

    /**
     * Draw an edge label.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @param {object} edge Edge record.
     * @param {object} from Source node.
     * @param {object} to Target node.
     * @param {boolean} selected Whether selected.
     * @returns {void}
     */
    #drawEdgeLabel(context, edge, from, to, selected) {
        if (!selected && this.#viewport.scale < 0.45) {
            return;
        }
        const styles = getComputedStyle(this);
        const x = (from.x + to.x) / 2;
        const y = (from.y + to.y) / 2;
        const label = this.#shortLabel(edge.label, selected ? 24 : 16);
        context.save();
        context.font = `${selected ? 700 : 650} ${10 / this.#viewport.scale}px Inter, system-ui, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        const width = context.measureText(label).width + 12;
        const height = 18 / this.#viewport.scale;
        this.#edgeLabelBounds.set(edge.id, {
            left: x - width / 2,
            right: x + width / 2,
            top: y - height / 2,
            bottom: y + height / 2
        });
        context.fillStyle = styles.getPropertyValue("--surface").trim();
        context.strokeStyle = styles.getPropertyValue("--border").trim();
        this.#roundedRect(context, x - width / 2, y - height / 2, width, height, 8 / this.#viewport.scale);
        context.fill();
        context.stroke();
        context.fillStyle = selected ? styles.getPropertyValue("--primary").trim() : styles.getPropertyValue("--text-muted").trim();
        context.fillText(label, x, y);
        context.restore();
    }

    /**
     * Draw graph nodes.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @returns {void}
     */
    #drawNodes(context) {
        this.#nodeLabelBounds.clear();
        const styles = getComputedStyle(this);
        const focus = this.#focusGraph();
        const activeRelationId = this.#hoveredRelationId || this.#selectedRelationId;
        const selectedRelation = this.#edges.find(edge => edge.id === activeRelationId);
        const connectivity = this.#connectivityMetrics(focus);
        const degrees = connectivity.degrees;
        const maxDegree = Math.max(0, ...degrees.values());
        const orderedNodes = focus
            ? this.#nodes.filter(node => focus.nodeIds.has(node.id))
            : this.#nodes;
        const visibleNodes = orderedNodes.filter(node => this.#nodeIntersectsRenderFrustum(node));
        const rankedNodeIds = new Set(this.#rankImportantNodes(visibleNodes).map(node => node.id));
        const rankedLabelBounds = [];
        visibleNodes.forEach(node => {
            const selected = node.id === this.#selectedNodeId;
            const hovered = node.id === this.#hoveredNodeId;
            const ranked = rankedNodeIds.has(node.id);
            const relationEndpoint = selectedRelation?.from === node.id || selectedRelation?.to === node.id;
            const focused = selected || hovered || relationEndpoint || Boolean(focus?.nodeIds.has(node.id));
            const radius = selected || hovered ? node.radius + 5 : relationEndpoint ? node.radius + 4 : focused ? node.radius + 2 : node.radius;
            context.save();
            context.globalAlpha = 1;
            context.beginPath();
            context.arc(node.x, node.y, radius, 0, Math.PI * 2);
            context.fillStyle = selected || hovered || relationEndpoint
                ? styles.getPropertyValue("--primary").trim()
                : styles.getPropertyValue("--surface-strong").trim();
            context.strokeStyle = node.color;
            context.lineWidth = selected || hovered || relationEndpoint
                ? 3.4 / this.#viewport.scale
                : focused ? 2.6 / this.#viewport.scale : 1.8 / this.#viewport.scale;
            context.setLineDash(node.visualType === "class" ? [7 / this.#viewport.scale, 5 / this.#viewport.scale] : []);
            context.fill();
            context.stroke();
            if (this.#nodeLabelIsVisible(node, degrees, maxDegree, selected || focused, ranked)) {
                this.#drawNodeLabel(context, node, selected || focused, ranked, rankedLabelBounds);
            }
            if (selected && this.#nodeCanExpand(node.id)) {
                this.#drawNodeExpansionBadge(context, node);
            }
            context.restore();
        });
    }

    /** Return the number of visible relations incident to each node. */
    #nodeDegrees(focus = null) {
        const visibleNodeIds = focus?.nodeIds || new Set(this.#nodes.map(node => node.id));
        const degrees = new Map([...visibleNodeIds].map(nodeId => [nodeId, 0]));
        this.#edges.forEach(edge => {
            if (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to)) {
                return;
            }
            degrees.set(edge.from, (degrees.get(edge.from) || 0) + 1);
            degrees.set(edge.to, (degrees.get(edge.to) || 0) + 1);
        });
        return degrees;
    }

    /** Return connectivity normalized against the maximum of the visible graph. */
    #connectivityMetrics(focus = this.#focusGraph()) {
        const degrees = this.#nodeDegrees(focus);
        const maxDegree = Math.max(1, ...degrees.values());
        return {
            degrees,
            maxDegree,
            score: nodeId => (degrees.get(nodeId) || 0) / maxDegree
        };
    }

    /** Scale node radii by connectivity while preserving readable bounds. */
    #applyConnectivitySizing(focus = null) {
        const connectivity = this.#connectivityMetrics(focus);
        const baseRadius = this.#mode === "classes" ? 14 : 10;
        const radiusRange = this.#mode === "classes" ? 16 : 13;
        this.#nodes.forEach(node => {
            const normalized = Math.sqrt(connectivity.score(node.id));
            node.radius = baseRadius + normalized * radiusRange;
        });
    }

    /** Decide whether a label belongs to the zoom-dependent connectivity tier. */
    #nodeLabelIsVisible(node, degrees, maxDegree, emphasized, ranked = false) {
        if (emphasized || ranked || this.#viewport.scale >= 0.78) {
            return true;
        }
        const normalizedRank = maxDegree ? (degrees.get(node.id) || 0) / maxDegree : 0;
        const zoomProgress = Math.max(0, Math.min(1, (this.#viewport.scale - 0.005) / 0.775));
        const easedTolerance = zoomProgress * zoomProgress * (3 - (2 * zoomProgress));
        const minimumRank = 0.56 * (1 - easedTolerance);
        return normalizedRank >= minimumRank;
    }

    /**
     * Return the current selected node/relation neighborhood.
     *
     * @returns {{nodeIds: Set<string>, edgeIds: Set<string>}|null} Focus ids.
     */
    #focusGraph() {
        if (!this.#regionNodeIds.size) {
            return null;
        }
        return {
            nodeIds: this.#regionNodeIds,
            edgeIds: this.#regionEdgeIds
        };
    }

    /** Return whether a node can become the root of a distinct child region. */
    #nodeCanExpand(nodeId) {
        const child = this.#graphRegionForNode(nodeId);
        if (!child.edgeIds.size) return false;
        if (!this.#regionNodeIds.size) return true;
        return child.nodeIds.size !== this.#regionNodeIds.size
            || [...child.nodeIds].some(id => !this.#regionNodeIds.has(id));
    }

    /** Draw a screen-stable expansion affordance above a selected node. */
    #drawNodeExpansionBadge(context, node) {
        const styles = getComputedStyle(this);
        const scale = this.#viewport.scale;
        const badgeRadius = 9 / scale;
        const x = node.x + node.radius * 0.72;
        const y = node.y - node.radius * 0.72;
        context.save();
        context.beginPath();
        context.arc(x, y, badgeRadius, 0, Math.PI * 2);
        context.fillStyle = styles.getPropertyValue("--primary").trim();
        context.strokeStyle = styles.getPropertyValue("--surface").trim();
        context.lineWidth = 2 / scale;
        context.fill();
        context.stroke();
        context.strokeStyle = styles.getPropertyValue("--on-primary").trim() || "#fff";
        context.lineWidth = 1.8 / scale;
        context.lineCap = "round";
        context.beginPath();
        context.moveTo(x - 4 / scale, y);
        context.lineTo(x + 4 / scale, y);
        context.moveTo(x, y - 4 / scale);
        context.lineTo(x, y + 4 / scale);
        context.stroke();
        context.restore();
    }

    /** Build the child region rooted at one node and its immediate neighbors. */
    #graphRegionForNode(nodeId) {
        const nodeIds = new Set(nodeId ? [nodeId] : []);
        const edgeIds = new Set();
        this.#edges.forEach(edge => {
            if (edge.from !== nodeId && edge.to !== nodeId) {
                return;
            }
            edgeIds.add(edge.id);
            nodeIds.add(edge.from);
            nodeIds.add(edge.to);
        });
        this.#edges.forEach(edge => {
            if (nodeIds.has(edge.from) && nodeIds.has(edge.to)) edgeIds.add(edge.id);
        });
        return { nodeIds, edgeIds };
    }

    /** Reconcile a preserved region after the graph records are rebuilt. */
    #reconcileRegionEdges() {
        const availableNodeIds = new Set(this.#nodes.map(node => node.id));
        this.#regionNodeIds = new Set([...this.#regionNodeIds].filter(id => availableNodeIds.has(id)));
        this.#regionEdgeIds = new Set(this.#edges
            .filter(edge => this.#regionNodeIds.has(edge.from) && this.#regionNodeIds.has(edge.to))
            .map(edge => edge.id));
    }

    /** Capture the current level before navigating to a child region. */
    #captureGraphRegionLevel() {
        return {
            nodeIds: new Set(this.#regionNodeIds),
            edgeIds: new Set(this.#regionEdgeIds),
            positions: new Map(this.#regionPositions),
            graphPositions: new Map(this.#nodes.map(node => [node.id, { x: node.x, y: node.y }])),
            rootNodeId: this.#regionRootNodeId,
            selectedNodeId: this.#selectedNodeId,
            selectedRelationId: this.#selectedRelationId,
            viewport: { ...this.#viewport }
        };
    }

    /** Replace the current graph level with a child region rooted at one node. */
    #navigateGraphRegion(nodeId) {
        if (!this.#nodeCanExpand(nodeId)) return;
        const child = this.#graphRegionForNode(nodeId);
        this.#regionHistory.push(this.#captureGraphRegionLevel());
        this.#regionNodeIds = child.nodeIds;
        this.#regionEdgeIds = child.edgeIds;
        this.#regionPositions = new Map();
        this.#regionRootNodeId = nodeId;
        this.#selectedNodeId = nodeId;
        this.#selectedRelationId = "";
        this.#focusViewport = null;
        const focus = this.#focusGraph();
        if (focus) this.#layoutFocusedRegion(focus);
        this.#needsViewportFit = true;
        this.#drawCanvas();
        this.#renderInspector();
    }

    /** Restore exactly one parent graph level, including its layout and camera. */
    #navigateBackGraphRegion() {
        const previous = this.#regionHistory.pop();
        if (!previous) return;
        cancelAnimationFrame(this.#cameraAnimationFrame);
        this.#cameraAnimationFrame = 0;
        this.#regionNodeIds = new Set(previous.nodeIds);
        this.#regionEdgeIds = new Set(previous.edgeIds);
        this.#regionPositions = new Map(previous.positions);
        this.#regionRootNodeId = previous.rootNodeId;
        this.#selectedNodeId = previous.selectedNodeId;
        this.#selectedRelationId = previous.selectedRelationId;
        previous.graphPositions.forEach((position, nodeId) => {
            const node = this.#nodes.find(item => item.id === nodeId);
            if (node) Object.assign(node, position);
        });
        this.#viewport = { ...previous.viewport };
        this.#needsViewportFit = false;
        this.#focusViewport = null;
        this.#hoveredNodeId = "";
        this.#hoveredRelationId = "";
        this.#relationHoverViewport = null;
        this.#badgeHoverViewport = null;
        this.#drawCanvas();
        this.#renderInspector();
    }

    /**
     * Draw a persistent node label.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @param {object} node Graph node.
     * @param {boolean} selected Whether selected.
     * @param {boolean} ranked Whether represented by a ranked inspector badge.
     * @param {object[]} occupiedBounds Ranked-label rectangles already placed this frame.
     * @returns {void}
     */
    #drawNodeLabel(context, node, selected, ranked = false, occupiedBounds = []) {
        const styles = getComputedStyle(this);
        const label = this.#shortLabel(node.label, selected ? 28 : 18);
        const fontSize = selected ? 12 : ranked ? 11 : 10;
        const scale = this.#viewport.scale;
        context.save();
        context.font = `800 ${fontSize / scale}px Inter, system-ui, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        const width = context.measureText(label).width + (14 / scale);
        const height = (fontSize + 8) / scale;
        const placement = ranked
            ? this.#rankedLabelPlacement(node, width, height, occupiedBounds)
            : { x: node.x, y: node.y + node.radius + (14 / scale) };
        const x = placement.x;
        const y = placement.y;
        if (ranked || selected) {
            context.fillStyle = styles.getPropertyValue("--surface").trim();
            context.strokeStyle = node.color;
            context.lineWidth = 1.5 / scale;
            this.#roundedRect(context, x - width / 2, y - height / 2, width, height, 8 / scale);
            context.fill();
            context.stroke();
            this.#nodeLabelBounds.set(node.id, {
                left: x - width / 2,
                right: x + width / 2,
                top: y - height / 2,
                bottom: y + height / 2
            });
        }
        context.fillStyle = node.color;
        context.shadowColor = styles.getPropertyValue("--surface").trim();
        context.shadowBlur = 4 / scale;
        context.lineWidth = 3 / scale;
        context.fillText(label, x, y);
        context.restore();
    }

    /** Place one screen-stable ranked label without intersecting earlier ranked labels. */
    #rankedLabelPlacement(node, width, height, occupiedBounds) {
        const scale = this.#viewport.scale;
        const vertical = node.radius + (14 / scale);
        const horizontal = node.radius + (8 / scale) + width / 2;
        const candidates = [
            { x: node.x, y: node.y + vertical },
            { x: node.x, y: node.y - vertical },
            { x: node.x + horizontal, y: node.y },
            { x: node.x - horizontal, y: node.y },
            { x: node.x, y: node.y + vertical + height + (6 / scale) },
            { x: node.x, y: node.y - vertical - height - (6 / scale) },
            { x: node.x + horizontal, y: node.y + height + (6 / scale) },
            { x: node.x - horizontal, y: node.y - height - (6 / scale) }
        ];
        const padding = 4 / scale;
        const rectangleFor = candidate => ({
            left: candidate.x - width / 2 - padding,
            right: candidate.x + width / 2 + padding,
            top: candidate.y - height / 2 - padding,
            bottom: candidate.y + height / 2 + padding
        });
        const overlaps = rectangle => occupiedBounds.some(other => (
            rectangle.left < other.right
            && rectangle.right > other.left
            && rectangle.top < other.bottom
            && rectangle.bottom > other.top
        ));
        const placement = candidates.find(candidate => !overlaps(rectangleFor(candidate)))
            || { x: node.x, y: node.y + vertical + (occupiedBounds.length * (height + padding)) };
        occupiedBounds.push(rectangleFor(placement));
        return placement;
    }

    /**
     * Draw a rounded rectangle path.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @param {number} x X coordinate.
     * @param {number} y Y coordinate.
     * @param {number} width Width.
     * @param {number} height Height.
     * @param {number} radius Radius.
     * @returns {void}
     */
    #roundedRect(context, x, y, width, height, radius) {
        context.beginPath();
        context.moveTo(x + radius, y);
        context.lineTo(x + width - radius, y);
        context.quadraticCurveTo(x + width, y, x + width, y + radius);
        context.lineTo(x + width, y + height - radius);
        context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        context.lineTo(x + radius, y + height);
        context.quadraticCurveTo(x, y + height, x, y + height - radius);
        context.lineTo(x, y + radius);
        context.quadraticCurveTo(x, y, x + radius, y);
        context.closePath();
    }

    /**
     * Start node dragging, relation selection, or canvas panning.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    #onPointerDown(event, canvas) {
        const point = this.#canvasPoint(event, canvas);
        const expansionNode = this.#hitTestNodeExpansionBadge(point.x, point.y);
        if (expansionNode) {
            event.preventDefault();
            this.#navigateGraphRegion(expansionNode.id);
            return;
        }
        const labelNode = this.#hitTestNodeLabel(point.x, point.y);
        if (labelNode) {
            event.preventDefault();
            this.#focusNode(labelNode.id, false);
            return;
        }
        const labelEdge = this.#hitTestEdgeLabel(point.x, point.y);
        if (labelEdge) {
            this.#selectRelation(labelEdge.id);
            return;
        }
        const node = this.#hitTestNode(point.x, point.y);
        const edge = this.#hitTestEdge(point.x, point.y);
        if (edge && (!node || !this.#nodeOwnsPoint(node, point.x, point.y))) {
            this.#selectRelation(edge.id);
            return;
        }
        if (node) {
            this.#pointerCandidate = {
                id: node.id,
                pointerId: event.pointerId,
                clientX: event.clientX,
                clientY: event.clientY,
                offsetX: point.x - node.x,
                offsetY: point.y - node.y,
                moved: false
            };
            canvas.setPointerCapture(event.pointerId);
            return;
        }
        if (edge) {
            this.#selectRelation(edge.id);
            return;
        }
        if (this.#selectedNodeId || this.#selectedRelationId) {
            this.#selectedNodeId = "";
            this.#selectedRelationId = "";
            this.#restoreFocusViewport();
            this.#renderInspector();
            return;
        }
        this.#panState = {
            pointerId: event.pointerId,
            clientX: event.clientX,
            clientY: event.clientY,
            startX: this.#viewport.x,
            startY: this.#viewport.y
        };
        cancelAnimationFrame(this.#cameraAnimationFrame);
        this.#cameraAnimationFrame = 0;
        canvas.setPointerCapture(event.pointerId);
    }

    /** Smoothly center one node while optionally changing the camera scale. */
    #animateCameraToNode(node, targetScale) {
        this.#animateViewport({
            x: -node.x * targetScale,
            y: -node.y * targetScale,
            scale: targetScale
        });
    }

    /** Smoothly center one relation midpoint while optionally changing camera scale. */
    #animateCameraToRelation(relation, targetScale) {
        const source = this.#nodes.find(node => node.id === relation.from);
        const target = this.#nodes.find(node => node.id === relation.to);
        if (!source || !target) {
            return;
        }
        this.#animateViewport({
            x: -((source.x + target.x) / 2) * targetScale,
            y: -((source.y + target.y) / 2) * targetScale,
            scale: targetScale
        });
    }

    /**
     * Animate from the current camera to one exact viewport.
     *
     * @param {{x: number, y: number, scale: number}} target Destination camera.
     * @param {(() => void)|null} onComplete Callback after the final rendered frame.
     * @returns {void}
     */
    #animateViewport(target, onComplete = null) {
        cancelAnimationFrame(this.#cameraAnimationFrame);
        this.#needsViewportFit = false;
        const start = { ...this.#viewport };
        const startedAt = performance.now();
        const duration = 420;
        const animate = now => {
            const progress = Math.max(0, Math.min(1, (now - startedAt) / duration));
            const eased = 1 - Math.pow(1 - progress, 3);
            this.#viewport = {
                x: start.x + (target.x - start.x) * eased,
                y: start.y + (target.y - start.y) * eased,
                scale: start.scale + (target.scale - start.scale) * eased
            };
            this.#drawCanvas();
            if (progress < 1) {
                this.#cameraAnimationFrame = requestAnimationFrame(animate);
            } else {
                this.#cameraAnimationFrame = 0;
                onComplete?.();
            }
        };
        this.#cameraAnimationFrame = requestAnimationFrame(animate);
    }

    /** Focus one node while preserving the camera that preceded the focus zoom. */
    #focusNode(nodeId, allowExpansion = true) {
        const node = this.#nodes.find(item => item.id === nodeId);
        if (!node) {
            return;
        }
        const hadRegion = this.#regionNodeIds.size > 0;
        if (!this.#selectedNodeId) {
            this.#focusViewport = this.#badgeHoverViewport
                ? { ...this.#badgeHoverViewport }
                : { ...this.#viewport };
        }
        this.#badgeHoverViewport = null;
        this.#viewportBadgeRankingFrozen = false;
        this.#hoveredNodeId = "";
        this.#selectedNodeId = node.id;
        this.#selectedRelationId = "";
        this.#animateCameraToNode(node, hadRegion ? this.#viewport.scale : Math.max(this.#viewport.scale, 1.35));
        this.#renderInspector();
    }

    /** Select and center one relation without mutating the graph region. */
    #selectRelation(relationId) {
        const relation = this.#edges.find(edge => edge.id === relationId);
        if (!relation) {
            return;
        }
        if (!this.#selectedNodeId && !this.#selectedRelationId) {
            this.#focusViewport = this.#relationHoverViewport
                ? { ...this.#relationHoverViewport }
                : { ...this.#viewport };
        }
        this.#selectedRelationId = relationId;
        this.#selectedNodeId = "";
        this.#hoveredRelationId = "";
        this.#hoveredNodeId = "";
        this.#relationHoverViewport = null;
        this.#badgeHoverViewport = null;
        this.#viewportBadgeRankingFrozen = false;
        this.#animateCameraToRelation(relation, Math.max(this.#viewport.scale, 1.35));
        this.#renderInspector();
    }

    /** Restore the camera snapshot captured immediately before entity focus. */
    #restoreFocusViewport() {
        if (!this.#focusViewport) {
            this.#drawCanvas();
            return;
        }
        const previousViewport = this.#focusViewport;
        this.#focusViewport = null;
        this.#animateViewport(previousViewport);
    }

    /**
     * Move a dragged node or pan the graph.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    #onPointerMove(event, canvas) {
        if (this.#pointerCandidate && !this.#dragNode) {
            const distance = Math.hypot(
                event.clientX - this.#pointerCandidate.clientX,
                event.clientY - this.#pointerCandidate.clientY
            );
            if (distance >= 4) {
                this.#pointerCandidate.moved = true;
                this.#dragNode = {
                    id: this.#pointerCandidate.id,
                    offsetX: this.#pointerCandidate.offsetX,
                    offsetY: this.#pointerCandidate.offsetY
                };
            }
        }
        if (this.#dragNode) {
            const point = this.#canvasPoint(event, canvas);
            const node = this.#nodes.find(item => item.id === this.#dragNode.id);
            if (!node) {
                return;
            }
            node.x = point.x - this.#dragNode.offsetX;
            node.y = point.y - this.#dragNode.offsetY;
            if (this.#regionNodeIds.has(node.id)) {
                this.#regionPositions.set(node.id, { x: node.x, y: node.y });
            }
            this.#drawCanvas();
            return;
        }
        if (!this.#panState) {
            return;
        }
        this.#viewport.x = this.#panState.startX + (event.clientX - this.#panState.clientX);
        this.#viewport.y = this.#panState.startY + (event.clientY - this.#panState.clientY);
        this.#drawCanvas();
    }

    /**
     * End dragging or panning.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    #onPointerUp(event, canvas) {
        const candidate = this.#pointerCandidate;
        if (candidate && !candidate.moved) {
            this.#focusNode(candidate.id, true);
        }
        this.#pointerCandidate = null;
        this.#dragNode = null;
        this.#panState = null;
        if (canvas.hasPointerCapture?.(event.pointerId)) {
            canvas.releasePointerCapture(event.pointerId);
        }
    }

    /**
     * Zoom the graph around the cursor.
     *
     * @param {WheelEvent} event Wheel event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    #onWheel(event, canvas) {
        event.preventDefault();
        cancelAnimationFrame(this.#cameraAnimationFrame);
        this.#cameraAnimationFrame = 0;
        const rect = canvas.getBoundingClientRect();
        const cursorX = event.clientX - rect.left - rect.width / 2;
        const cursorY = event.clientY - rect.top - rect.height / 2;
        const previousScale = this.#viewport.scale;
        const nextScale = Math.min(3.4, Math.max(0.005, previousScale * (event.deltaY > 0 ? 0.9 : 1.1)));
        const graphX = (cursorX - this.#viewport.x) / previousScale;
        const graphY = (cursorY - this.#viewport.y) / previousScale;
        this.#viewport.x = cursorX - graphX * nextScale;
        this.#viewport.y = cursorY - graphY * nextScale;
        this.#viewport.scale = nextScale;
        this.#needsViewportFit = false;
        this.#drawCanvas();
    }

    /**
     * Refresh the inspector without replacing the canvas.
     *
     * @returns {void}
     */
    #renderInspector() {
        const inspector = this.querySelector(".graph-detail-list");
        if (!inspector) {
            return;
        }
        inspector.innerHTML = this.#renderDetails();
        const relationPreviewHost = this.querySelector("[data-role='relation-preview-host']");
        if (relationPreviewHost) {
            relationPreviewHost.innerHTML = this.#renderRelationPreview();
        }
        const backButton = this.querySelector("[data-action='navigate-region-back']");
        if (backButton) {
            backButton.hidden = !this.#regionHistory.length;
        }
        this.#bindInspectorButtons();
    }

    /**
     * Restore the complete graph from any isolated node or relation level.
     *
     * @returns {void}
     */
    #clearGraphFocus() {
        this.#resetGraphRegion();
        this.#layoutGraphByNeighbors();
        this.#needsViewportFit = true;
        this.#drawCanvas();
        this.#renderInspector();
    }

    /** Reset camera zoom and center while preserving the current graph or subregion. */
    #resetVisibleGraphViewport() {
        cancelAnimationFrame(this.#cameraAnimationFrame);
        this.#cameraAnimationFrame = 0;
        this.#hoveredNodeId = "";
        this.#hoveredRelationId = "";
        this.#relationHoverViewport = null;
        this.#badgeHoverViewport = null;
        const canvas = this.querySelector("[data-role='knowledge-canvas']");
        if (!(canvas instanceof HTMLCanvasElement)) return;
        this.#viewportBadgeRankingFrozen = true;
        this.#needsViewportFit = false;
        const target = this.#fittedViewport(canvas.getBoundingClientRect());
        this.#animateViewport(target, () => this.#releaseViewportBadgeRanking());
        this.#renderInspector();
    }

    /** Clear persistent region state without rendering. */
    #resetGraphRegion() {
        this.#selectedNodeId = "";
        this.#selectedRelationId = "";
        this.#hoveredNodeId = "";
        this.#hoveredRelationId = "";
        this.#regionNodeIds.clear();
        this.#regionEdgeIds.clear();
        this.#regionPositions.clear();
        this.#regionHistory = [];
        this.#regionRootNodeId = "";
        this.#focusViewport = null;
        this.#relationHoverViewport = null;
        this.#badgeHoverViewport = null;
        this.#viewportBadgeRankingFrozen = false;
    }

    /**
     * Convert viewport pointer coordinates into graph coordinates.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {{x: number, y: number}} Graph point.
     */
    #canvasPoint(event, canvas) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: (event.clientX - rect.left - rect.width / 2 - this.#viewport.x) / this.#viewport.scale,
            y: (event.clientY - rect.top - rect.height / 2 - this.#viewport.y) / this.#viewport.scale
        };
    }

    /**
     * Find a node under graph coordinates.
     *
     * @param {number} x Graph x.
     * @param {number} y Graph y.
     * @returns {object|null} Hit node.
     */
    #hitTestNode(x, y) {
        const focus = this.#focusGraph();
        const candidates = focus ? this.#nodes.filter(node => focus.nodeIds.has(node.id)) : this.#nodes;
        return [...candidates].reverse().find(node => {
            const dx = node.x - x;
            const dy = node.y - y;
            return Math.sqrt((dx * dx) + (dy * dy)) <= node.radius + (16 / this.#viewport.scale);
        }) || null;
    }

    /** Find the selected node whose explicit child-region affordance contains a point. */
    #hitTestNodeExpansionBadge(x, y) {
        if (!this.#selectedNodeId || !this.#nodeCanExpand(this.#selectedNodeId)) return null;
        const node = this.#nodes.find(item => item.id === this.#selectedNodeId);
        if (!node || (this.#regionNodeIds.size && !this.#regionNodeIds.has(node.id))) return null;
        const badgeX = node.x + node.radius * 0.72;
        const badgeY = node.y - node.radius * 0.72;
        const hitRadius = 13 / this.#viewport.scale;
        return Math.hypot(x - badgeX, y - badgeY) <= hitRadius ? node : null;
    }

    /** Resolve ranked node-label rectangles before relation labels and node hit halos. */
    #hitTestNodeLabel(x, y) {
        const padding = 5 / Math.max(this.#viewport.scale, 0.005);
        for (const [nodeId, bounds] of [...this.#nodeLabelBounds.entries()].reverse()) {
            if (x < bounds.left - padding || x > bounds.right + padding
                || y < bounds.top - padding || y > bounds.bottom + padding) continue;
            return this.#nodes.find(node => node.id === nodeId) || null;
        }
        return null;
    }

    /** Return whether a point belongs to the visible node body rather than its generous hit halo. */
    #nodeOwnsPoint(node, x, y) {
        return Math.hypot(node.x - x, node.y - y) <= node.radius + (4 / this.#viewport.scale);
    }

    /** Find a relation whose rendered label rectangle contains graph coordinates. */
    #hitTestEdgeLabel(x, y) {
        const focus = this.#focusGraph();
        const candidates = focus ? this.#edges.filter(edge => focus.edgeIds.has(edge.id)) : this.#edges;
        const padding = 4 / this.#viewport.scale;
        return [...candidates].reverse().find(edge => {
            const bounds = this.#edgeLabelBounds.get(edge.id);
            return bounds
                && x >= bounds.left - padding
                && x <= bounds.right + padding
                && y >= bounds.top - padding
                && y <= bounds.bottom + padding;
        }) || null;
    }

    /**
     * Find an edge near graph coordinates.
     *
     * @param {number} x Graph x.
     * @param {number} y Graph y.
     * @returns {object|null} Hit edge.
     */
    #hitTestEdge(x, y) {
        const focus = this.#focusGraph();
        const candidates = focus ? this.#edges.filter(edge => focus.edgeIds.has(edge.id)) : this.#edges;
        return [...candidates].reverse().find(edge => {
            const from = this.#nodes.find(node => node.id === edge.from);
            const to = this.#nodes.find(node => node.id === edge.to);
            if (!from || !to) {
                return false;
            }
            return this.#pointToSegmentDistance(x, y, from.x, from.y, to.x, to.y) <= 7 / this.#viewport.scale;
        }) || null;
    }

    /**
     * Distance from point to segment.
     *
     * @param {number} px Point x.
     * @param {number} py Point y.
     * @param {number} x1 Segment x1.
     * @param {number} y1 Segment y1.
     * @param {number} x2 Segment x2.
     * @param {number} y2 Segment y2.
     * @returns {number} Distance.
     */
    #pointToSegmentDistance(px, py, x1, y1, x2, y2) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        if (dx === 0 && dy === 0) {
            return Math.hypot(px - x1, py - y1);
        }
        const t = Math.max(0, Math.min(1, (((px - x1) * dx) + ((py - y1) * dy)) / ((dx * dx) + (dy * dy))));
        return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
    }

    /**
     * Build a stable node id from contextual label.
     *
     * @param {string} domain Domain.
     * @param {string} label Label.
     * @param {number} index Fallback index.
     * @returns {string} Node id.
     */
    #nodeId(domain, label, index = 0) {
        return `node:${domain}:${String(label || index).toLowerCase()}`;
    }

    /**
     * Shorten a graph label.
     *
     * @param {string} label Full label.
     * @param {number} limit Character limit.
     * @returns {string} Short label.
     */
    #shortLabel(label, limit = 14) {
        const text = String(label || "");
        return text.length > limit ? `${text.slice(0, Math.max(1, limit - 1))}...` : text;
    }
}

customElements.define(KnowledgeView.selector, KnowledgeView);
