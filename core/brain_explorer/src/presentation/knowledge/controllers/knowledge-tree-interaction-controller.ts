/**
 * Coordinates Knowledge source-tree selection, actions, and navigation.
 */
import { StructureTree } from "../../shared/components/structure-tree.ts";
import type { StructureTreeAction } from "../../shared/view_models/structure-tree-view-model.ts";
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
                { id: "refresh-tree", label: "Refresh", icon: "refresh", showLabel: true } satisfies StructureTreeAction,
                ...(this.treeFilterActive
                    ? [{ id: "revert-tree-filter", label: "Revert", icon: "chevronLeft", showLabel: true } satisfies StructureTreeAction]
                    : []),
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
        this.highlightScope = node.scope === "global" || node.scope === "local" ? node.scope : "all";
        this.highlightDomain = String(node.domain || "all");
        this.sourceKind = node.sourceKind === "memory" || node.sourceKind === "pictures"
            || node.sourceKind === "messages" || node.sourceKind === "logs" ? node.sourceKind : "";
        this.highlightSourceKind = this.sourceKind;
        this.sourceKind = "";
        this.highlightVisualType = node.visualType === "class" || node.visualType === "entity" ? node.visualType : "";
        this.highlightSourcePath = String(node.sourcePath || "");
        this.treeHighlightActive = true;
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
        if (event.detail.action === "refresh-tree") {
            this.showRecords(true);
        } else if (event.detail.action === "revert-tree-filter") {
            this.revertTreeFilter();
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
            this.treeFilterActive = true;
            this.treeScope = event.detail.node.scope === "global" || event.detail.node.scope === "local" ? event.detail.node.scope : "all";
            this.domain = String(event.detail.node.domain || "all");
            const sourceKind = event.detail.node.sourceKind;
            this.sourceKind = sourceKind === "memory" || sourceKind === "pictures"
                || sourceKind === "messages" || sourceKind === "logs" ? sourceKind : "";
            this.treeVisualType = event.detail.node.visualType === "class" || event.detail.node.visualType === "entity" ? event.detail.node.visualType : "";
            this.sourcePath = String(event.detail.node.sourcePath || "");
            this.treeHighlightActive = false;
            this.treeHighlightNodeIds.clear();
            this.treeHighlightEdgeIds.clear();
            this.applyFilters();
            return;
        }
        if (event.detail.action === "open-source" && event.detail.node.openRoute) {
            this.state?.setRouteTarget?.(event.detail.node.openRoute, event.detail.node.openTarget || {});
            return;
        }
        if (event.detail.action === "consolidate-source" || event.detail.action === "recompose-source") {
            this.runContainerDream(
                event.detail.node,
                event.detail.action === "recompose-source" ? "recompose" : "consolidate",
            );
        }
    }

    /**
     * Restore the complete source hierarchy and remove its structural graph scope.
     */
    protected revertTreeFilter(): void {
        this.selectedTreePath = "";
        this.treeFilterActive = false;
        this.treeScope = "all";
        this.domain = "all";
        this.sourceKind = "";
        this.sourcePath = "";
        this.treeVisualType = "";
        this.treeHighlightActive = false;
        this.treeHighlightNodeIds.clear();
        this.treeHighlightEdgeIds.clear();
        this.applyFilters();
    }

    /**
     * Generate proposals for every source owned by one selected tree container.
     *
     * @param {Record<string, any>} node Selected tree node.
     * @param {"consolidate" | "recompose"} action Requested generation mode.
     * @returns {Promise<void>} Resolves after the graph reflects the dream response.
     */
    protected async runContainerDream(node: Record<string, any>, action: "consolidate" | "recompose"): Promise<void> {
        if (!this.api) return;
        const api = this.api;
        const scope = node.scope === "global" || node.scope === "local" ? node.scope : "global";
        const sourceKind = String(node.sourceKind || "");
        const sourcePaths = this.collectTreeSourcePaths(node);
        const rawDomain = String(node.domain || "all").split(/[./\\]/)[0]?.toLowerCase() || "all";
        const domain = sourceKind === "logs" || sourceKind === "messages"
            ? sourceKind
            : rawDomain === "profiles" || rawDomain === "diary" ? rawDomain : "memory";
        this.beginGraphBusy(action === "recompose" ? "Recomposing source container" : "Consolidating source container");
        try {
            const result = await api.knowledgeDream({
                action,
                scope,
                domain,
                sourcePaths,
                limit: Math.max(sourcePaths.length, 20),
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
     * Return the unique canonical leaf paths owned by a tree container.
     * @param {Record<string, any>} node Selected tree container.
     * @returns {string[]} Unique canonical descendant source paths.
     */
    protected collectTreeSourcePaths(node: Record<string, any>): string[] {
        const paths = new Set<string>();
        const visit = (current: Record<string, any>): void => {
            const sourcePath = String(current.sourcePath || "").trim();
            if (sourcePath) paths.add(sourcePath.replaceAll("\\", "/"));
            if (Array.isArray(current.children)) current.children.forEach(child => visit(child));
        };
        visit(node);
        return [...paths].sort();
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
