/**
 * Coordinates Knowledge source-tree selection, actions, and navigation.
 */
import { StructureTree } from "../../shared/components/structure-tree.ts";
import { KnowledgeCanvasInteractionController } from "./knowledge-canvas-interaction-controller.ts";

/**
 * Source-tree interaction controller layered above canvas behavior.
 */
export abstract class KnowledgeTreeInteractionController extends KnowledgeCanvasInteractionController {
    /**
     * Configure the shared structure tree with Knowledge nodes and action handlers.
     */
    protected configureDomainTree(): void {
        const treeElement = this.querySelector("[data-role='knowledge-domain-tree']");
        if (!(treeElement instanceof StructureTree)) {
            return;
        }
        treeElement.model = {
            nodes: this.domainTreeNodes,
            selectedPath: this.selectedTreePath,
            expandedPaths: this.expandedDomains,
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
        treeElement.addEventListener("brain-tree-select", event => this.onDomainTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.onDomainTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.onDomainTreeAction(event));
    }

    /**
     * Scope the graph to a selected domain.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    protected onDomainTreeSelected(event: Event): void {
        if (!(event instanceof CustomEvent)) return;
        const node = event.detail.node || {};
        this.selectedTreePath = String(node.path || "");
        this.treeScope = node.scope === "global" || node.scope === "local" ? node.scope : "all";
        this.domain = String(node.domain || "all");
        this.sourceKind = node.sourceKind === "memory" || node.sourceKind === "pictures"
            || node.sourceKind === "messages" || node.sourceKind === "logs" ? node.sourceKind : "";
        this.treeVisualType = node.visualType === "class" || node.visualType === "entity" ? node.visualType : "";
        this.sourcePath = String(node.sourcePath || "");
        this.applyTreeSelection();
    }

    /**
     * Run one global Knowledge tree action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    protected onDomainTreeToolbarAction(event: Event): void {
        if (!(event instanceof CustomEvent)) return;
        if (event.detail.action === "refresh-graph") {
            this.showRecords(true);
        } else if (event.detail.action === "review-deltas") {
            this.reviewDeltas();
        } else if (event.detail.action === "fit-graph") {
            this.needsViewportFit = true;
            this.drawCanvas();
        }
    }

    /**
     * Scope the graph from a domain contextual action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    protected onDomainTreeAction(event: Event): void {
        if (!(event instanceof CustomEvent)) return;
        if (!event.detail.node?.path) {
            return;
        }
        if (event.detail.action === "filter-source") {
            this.selectedTreePath = String(event.detail.node.path);
            this.treeScope = event.detail.node.scope === "global" || event.detail.node.scope === "local" ? event.detail.node.scope : "all";
            this.domain = String(event.detail.node.domain || "all");
            const sourceKind = event.detail.node.sourceKind;
            this.sourceKind = sourceKind === "memory" || sourceKind === "pictures"
                || sourceKind === "messages" || sourceKind === "logs" ? sourceKind : "";
            this.treeVisualType = event.detail.node.visualType === "class" || event.detail.node.visualType === "entity" ? event.detail.node.visualType : "";
            this.sourcePath = String(event.detail.node.sourcePath || "");
            this.applyTreeSelection();
            return;
        }
        if (event.detail.action === "open-source" && event.detail.node.openRoute) {
            this.state?.setRouteTarget?.(event.detail.node.openRoute, event.detail.node.openTarget || {});
            return;
        }
        if (event.detail.action === "consolidate-source") {
            this.reviewDeltas();
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
    protected scheduleInitialLoad() {
        if (!this.api || this.loadScheduled || this.output) {
            return;
        }
        this.loadScheduled = true;
        queueMicrotask(() => this.showRecords());
    }

    /**
     * List graph records for the current scope and view.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after list call.
     */
    protected async showRecords(forceRefresh = false) {
        if (!this.api) {
            return;
        }
        this.beginGraphBusy(forceRefresh ? "Refreshing graph" : "Loading graph");
        try {
            this.readControls();
            const [result, memoryResult, pictureResult, messageResult, logResult] = await Promise.all([
                this.api.knowledgeShow({ scope: "all", mode: "all" }, { forceRefresh }),
                this.api.memoryTree({ forceRefresh }),
                this.api.pictures({}, { forceRefresh }),
                this.api.getVoiceMessages({ all: "true" }, { forceRefresh, silent: true }),
                this.api.logIndex({}, { forceRefresh, silent: true })
            ]);
            this.state?.setLastResult(result);
            this.output = result;
            this.memoryPaths = Array.isArray(memoryResult.data) ? memoryResult.data.map(path => String(path)) : [];
            this.pictures = Array.isArray(pictureResult.data?.pictures) ? pictureResult.data.pictures : [];
            this.messages = Array.isArray(messageResult.data?.history) ? messageResult.data.history : [];
            this.messageSessions = Array.isArray(messageResult.data?.sessions) ? messageResult.data.sessions : [];
            this.logEntries = Array.isArray(logResult.data?.entries) ? logResult.data.entries : [];
            this.ingestGraph(result.data);
            this.render();
            this.resolvePendingEntity();
        } finally {
            this.endGraphBusy();
        }
    }

    /**
     * Search graph records.
     *
     * @returns {Promise<void>} Resolves after query call.
     */
    protected async queryRecords() {
        if (!this.api) {
            return;
        }
        this.readControls();
        if (!this.query) {
            await this.applyFilters();
            return;
        }
        this.beginGraphBusy("Searching graph");
        try {
            const result = await this.api.knowledgeQuery({
                q: this.query,
                scope: this.scope,
                limit: "120",
                explain: "true"
            });
            this.state?.setLastResult(result);
            this.output = result;
            this.ingestGraph(result.data);
            this.render();
        } finally {
            this.endGraphBusy();
        }
    }

    /**
     * Load pending delta review.
     *
     * @returns {Promise<void>} Resolves after delta review.
     */
    protected async reviewDeltas() {
        if (!this.api) {
            return;
        }
        this.beginGraphBusy("Reviewing graph deltas");
        try {
            this.readControls();
            const result = await this.api.knowledgeDeltas({
                scope: this.scope,
                limit: "80",
                status: "pending"
            }, { forceRefresh: true });
            this.state?.setLastResult(result);
            this.output = result;
            this.ingestGraph(result.data);
            this.render();
        } finally {
            this.endGraphBusy();
        }
    }

    /**
     * Store normalized graph data and refresh derived nodes.
     *
     * @param {unknown} data Command data.
     * @returns {void}
     */

}
