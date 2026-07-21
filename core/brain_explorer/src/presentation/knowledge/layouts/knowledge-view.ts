/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */
import { escapeHtml } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import { StructureTree } from "../../shared/components/structure-tree.ts";
import { KnowledgeGraphNormalizer } from "../normalizers/knowledge-graph-normalizer.ts";
import { KnowledgeSourceTreeProjector } from "../projectors/knowledge-source-tree-projector.ts";
import { KnowledgeInspectorRenderer } from "../renderers/knowledge-inspector-renderer.ts";
import { KnowledgeGraphLayoutEngine } from "../layout_engines/knowledge-graph-layout-engine.ts";
import { knowledgeNodeId } from "../formatters/knowledge-graph-formatter.ts";
import { KnowledgeTreeInteractionController } from "../controllers/knowledge-tree-interaction-controller.ts";
import type { AvatarMessageRecord } from "../../../application/messages/dtos/responses/messages-response.ts";
import type { PictureRecord } from "../../../application/pictures/dtos/responses/pictures-response.ts";
import type { ComponentContext } from "../../shared/view_models/component-context-view-model.ts";
import type {
    KnowledgeGraphEdge,
    KnowledgeGraphCollection,
    KnowledgeGraphNode,
    KnowledgeRankedNode,
    KnowledgeSourceKind,
    MergedKnowledgeRecord,
    KnowledgeRecord,
    KnowledgeRelation,
    KnowledgeScope,
    KnowledgeTreeProjection,
    KnowledgeVisualType,
} from "../view_models/knowledge-view-model.ts";
void StructureTree;
/**
 * KnowledgeView renders a canvas-based explorer for graph records returned by the CLI facade.
 * Entities/classes become draggable nodes. Relations become selectable edges.
 */
export class KnowledgeView extends KnowledgeTreeInteractionController {
    /**
     * Projects persistence-backed source records into the shared navigation tree.
     * @type {KnowledgeSourceTreeProjector}
     */
    protected readonly sourceTreeProjector = new KnowledgeSourceTreeProjector();
    /**
     * Renders inspector markup while this layout owns selection and navigation.
     * @type {KnowledgeInspectorRenderer}
     */
    protected readonly inspectorRenderer = new KnowledgeInspectorRenderer();
    /**
     * Positions graph nodes without owning view lifecycle or rendering.
     * @type {KnowledgeGraphLayoutEngine}
     */
    protected readonly graphLayout = new KnowledgeGraphLayoutEngine();
    /**
     * Canonical custom-element selector registered by the application bootstrap.
     * @returns {string} The string identifier 'brain-knowledge-view'.
     */
    static get selector(): string {
        return "brain-knowledge-view";
    }
    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context: ComponentContext) {
        this.api = context.api;
        this.state = context.state;
        const target = this.state?.consumeRouteTarget?.("knowledge") || null;
        this.pendingEntityLabel = String(target?.entityLabel || "").trim();
        this.render();
        this.scheduleInitialLoad();
        if (this.output) queueMicrotask(() => this.resolvePendingEntity());
    }
    /**
     * Initialize component DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.render();
        this.scheduleInitialLoad();
    }
    /**
     * Disconnect canvas observers.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        this.resizeObserver?.disconnect();
        cancelAnimationFrame(this.cameraAnimationFrame);
        clearTimeout(this.viewportInspectorTimer);
    }
    /**
     * Load records once after the component has context.
     *
     * @returns {void}
     * @param {unknown} data The data value used by this operation.
     */
    protected ingestGraph(data: unknown): void {
        const graph = this.collectGraph(data);
        this.records = graph.records;
        this.relations = graph.relations;
        if (this.domain !== "all" && !this.domains().some(domain => domain === this.domain || domain.startsWith(`${this.domain}.`))) {
            this.domain = "all";
        }
        this.selectedNodeId = "";
        this.selectedRelationId = "";
        this.regionNodeIds.clear();
        this.regionEdgeIds.clear();
        this.regionPositions.clear();
        this.regionHistory = [];
        this.regionRootNodeId = "";
        this.needsViewportFit = true;
        this.prepareGraph();
    }
    /**
     * Read form controls into component state.
     *
     * @returns {void}
     */
    protected readControls(): void {
        const scopes = Array.from(this.querySelectorAll<HTMLInputElement>("[data-filter-kind='kg-scope']:checked"))
            .map(input => input.value)
            .filter((scope): scope is "global" | "local" => scope === "global" || scope === "local");
        this.selectedScopes = new Set(scopes);
        this.scope = scopes.length === 1 ? (scopes[0] ?? "all") : "all";
        const selectedModes = Array.from(this.querySelectorAll<HTMLInputElement>("[data-filter-kind='kg-mode']:checked"))
            .map(input => input.value)
            .filter((mode): mode is "entities" | "classes" => mode === "entities" || mode === "classes");
        this.mode = selectedModes.length === 1 ? (selectedModes[0] ?? "all") : "all";
        this.query = this.querySelector<HTMLInputElement>("[data-role='kg-query']")?.value.trim() || "";
    }
    /**
     * Render view markup.
     *
     * @returns {void}
     */
    protected render() {
        this.innerHTML = `
            <section class="page-surface knowledge-console">
                <div class="structure-layout knowledge-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.renderDomainTree()}
                        </div>
                    </aside>
                    <main class="structure-content knowledge-content">
                        <div class="content-head graph-toolbar">
                            <input class="graph-search-input" aria-label="Search graph" data-role="kg-query" value="${escapeHtml(this.query)}" placeholder="Filter or search graph">
                            <details class="action-menu filter-menu knowledge-filter-menu" ${this.filtersOpen ? "open" : ""}>
                                <summary class="compact-action">${icon("filter")}<span>Filters</span></summary>
                                <div class="action-menu-panel filter-menu-panel">
                                    <fieldset class="checkbox-filter-group knowledge-scope-filter">
                                        <legend>Scope</legend>
                                        <div class="knowledge-filter-options">
                                            <label><input type="checkbox" data-filter-kind="kg-scope" value="global" ${this.selectedScopes.has("global") ? "checked" : ""}><span>Global</span></label>
                                            <label><input type="checkbox" data-filter-kind="kg-scope" value="local" ${this.selectedScopes.has("local") ? "checked" : ""}><span>Local</span></label>
                                        </div>
                                    </fieldset>
                                    <fieldset class="checkbox-filter-group">
                                        <legend>Visible content</legend>
                                        <div class="knowledge-filter-options">
                                            <label><input type="checkbox" data-filter-kind="kg-mode" value="entities" ${this.mode === "all" || this.mode === "entities" ? "checked" : ""}><span>Entities</span></label>
                                            <label><input type="checkbox" data-filter-kind="kg-mode" value="classes" ${this.mode === "all" || this.mode === "classes" ? "checked" : ""}><span>Classes</span></label>
                                        </div>
                                    </fieldset>
                                </div>
                            </details>
                            <button data-action="query-records" class="primary-action">${icon("search")}Search</button>
                        </div>
                        <div class="knowledge-canvas-layout">
                            <main class="graph-viewport">
                                <button class="graph-focus-back secondary-action compact-action" data-action="navigate-region-back" ${this.regionHistory.length ? "" : "hidden"}>
                                    ${icon("chevronLeft")} Back
                                </button>
                                <canvas class="knowledge-graph-canvas" data-role="knowledge-canvas" aria-label="Knowledge graph"></canvas>
                                ${this.renderGraphBusyState()}
                                <div data-role="relation-preview-host">
                                    ${this.renderRelationPreview()}
                                </div>
                                ${this.renderCanvasEmptyState()}
                            </main>
                            <aside class="graph-detail-list">
                                ${this.renderDetails()}
                            </aside>
                        </div>
                    </main>
                </div>
            </section>
        `;
        this.bindEvents();
        this.configureDomainTree();
        this.bindCanvas();
    }
    /**
     * Render an empty overlay only when there are no visible nodes.
     *
     * @returns {string} HTML.
     */
    protected renderCanvasEmptyState(): string {
        if (this.nodes.length || this.records.length || this.relations.length) {
            return "";
        }
        return `
            <div class="knowledge-empty-state canvas-empty">
                ${icon("graph")}
                <h2>${this.output?.ok === false ? "Query failed" : "Loading graph"}</h2>
                <p>${escapeHtml(this.output?.error || this.output?.stderr || "Nodes will appear here.")}</p>
            </div>
        `;
    }
    /**
     * Render the bounded operation status overlay for the canvas.
     * @returns {string} An HTML string representing the graph busy state overlay.
     */
    protected renderGraphBusyState(): string {
        return `
            <div class="graph-busy-overlay" data-role="graph-busy-overlay" role="status" aria-live="polite" ${this.graphBusyDepth ? "" : "hidden"}>
                <span class="graph-busy-spinner" aria-hidden="true"></span>
                <strong data-role="graph-busy-label">${escapeHtml(this.graphBusyLabel)}</strong>
            </div>
        `;
    }
    /**
     * Begin one graph operation and expose its latest user-facing status.      * @param {string} label The label value used by this operation.
     */
    protected beginGraphBusy(label: string): void {
        this.graphBusyDepth += 1;
        this.graphBusyLabel = String(label || "Loading graph");
        this.syncGraphBusyState();
    }
    /**
     * Finish one graph operation without hiding another overlapping operation.
     */
    protected endGraphBusy(): void {
        this.graphBusyDepth = Math.max(0, this.graphBusyDepth - 1);
        this.syncGraphBusyState();
    }
    /**
     * Synchronize busy state without rebuilding the Knowledge component.
     */
    protected syncGraphBusyState(): void {
        const overlay = this.querySelector<HTMLElement>("[data-role='graph-busy-overlay']");
        const viewport = this.querySelector(".graph-viewport");
        if (overlay) {
            overlay.hidden = this.graphBusyDepth === 0;
            const label = overlay.querySelector("[data-role='graph-busy-label']");
            if (label) {
                label.textContent = this.graphBusyLabel;
            }
        }
        viewport?.setAttribute("aria-busy", String(this.graphBusyDepth > 0));
    }
    /**
     * Yield one paint frame so synchronous graph projection can expose the spinner.
     * @returns {Promise<void>} A promise that resolves once the requestAnimationFrame callback is executed.
     */
    protected waitForGraphPaint(): Promise<void> {
        return new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
    }
    /**
     * Render the complete subject-predicate-object preview for the selected relation.
     * @returns {string} An HTML section containing the relation's predicate and endpoint buttons, or an empty string if no relation is active.
     */
    protected renderRelationPreview(): string {
        const relationId = this.hoveredRelationId || this.selectedRelationId;
        const relation = this.edges.find(edge => edge.id === relationId);
        if (!relation) {
            return "";
        }
        const source = this.nodes.find(node => node.id === relation.from);
        const target = this.nodes.find(node => node.id === relation.to);
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
    protected renderDomainTree(): string {
        this.domainTreeNodes = this.sourceTreeProjector.project({
            selectedScopes: this.selectedScopes,
            memoryPaths: this.memoryPaths,
            pictures: this.pictures,
            messages: this.messages,
            messageSessions: this.messageSessions,
            logEntries: this.logEntries,
            graphCountLabel: (domain, scope, sourceKind = "", sourcePath = "", visualType = "") => (
                this.graphCountLabel(domain, scope, sourceKind, sourcePath, visualType)
            ),
            domainColor: domain => this.domainColor(domain),
        });
        return `<brain-structure-tree data-role="knowledge-domain-tree"></brain-structure-tree>`;
    }
    /**
     * Render inspector markup through the dedicated stateless renderer.
     * @returns {string} An HTML string representing the rendered inspector details.
     */
    protected renderDetails(): string {
        const proxiedInspector = this.inspectorRenderer.render({
            nodes: this.nodes,
            edges: this.edges,
            selectedNodeId: this.selectedNodeId,
            selectedRelationId: this.selectedRelationId,
            importantNodes: this.importantNodes(),
            pictureForNode: node => this.pictureForNode(node),
            messageForNode: node => this.messageForNode(node),
            isPictureTagNode: node => this.isPictureTagNode(node),
            pictureUrl: pictureId => this.api?.pictureUrl(pictureId) || "",
        });
        return proxiedInspector;
    }
    /**
     * Resolve an image registry record from one graph source reference.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     *
     * @returns {PictureRecord | null} The matching PictureRecord if found and the node is not a picture tag, otherwise null.
     */
    protected pictureForNode(node: KnowledgeGraphNode): PictureRecord | null {
        if (this.isPictureTagNode(node)) return null;
        const source = String(node.source || "").replaceAll("\\", "/").toLowerCase();
        const pictureId = String(node.raw?.picture_id || "");
        return this.pictures.find(picture => pictureId === String(picture.id)
            || source.endsWith(String(picture.relative_path || "").replaceAll("\\", "/").toLowerCase())) || null;
    }
    /**
     * Return whether a semantic image-analysis tag is being inspected, not its picture source.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     *
     * @returns {boolean} True if the node's class hint matches 'misc.tag' after normalization, otherwise false.
     */
    protected isPictureTagNode(node: KnowledgeGraphNode): boolean {
        return String(node.classHint || "").trim().toLowerCase() === "misc.tag";
    }
    /**
     * Resolve a persisted message body from one graph source reference.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     *
     * @returns {AvatarMessageRecord | null} The matching AvatarMessageRecord if found, otherwise null.
     */
    protected messageForNode(node: KnowledgeGraphNode): AvatarMessageRecord | null {
        const source = String(node.source || "");
        return this.messages.find(message => source.includes(String(message.id))) || null;
    }
    /**
     * Return highest-connectivity entities in the currently visible graph or region.
     * @returns {KnowledgeRankedNode[]} An array of KnowledgeRankedNode objects sorted by their importance rank.
     */
    protected importantNodes(): KnowledgeRankedNode[] {
        const focus = this.focusGraph();
        const logicalCandidates = focus
            ? this.nodes.filter(node => focus.nodeIds.has(node.id))
            : this.nodes;
        const candidates = this.viewportBadgeSignature
            ? logicalCandidates.filter(node => this.viewportNodeIds.has(node.id))
            : logicalCandidates;
        return this.rankImportantNodes(candidates);
    }
    /**
     * Rank one explicit visible-node set by its internal connectivity.      * @param {KnowledgeGraphNode[]} candidates The candidates value used by this operation.
     *
     * @returns {KnowledgeRankedNode[]} A sorted list of up to 12 nodes augmented with their respective connection degrees.
     */
    protected rankImportantNodes(candidates: KnowledgeGraphNode[]): KnowledgeRankedNode[] {
        const visibleIds = new Set<string>(candidates.map(node => node.id));
        const degrees = this.nodeDegrees({ nodeIds: visibleIds, edgeIds: new Set<string>() });
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
    protected collectGraph(data: unknown): KnowledgeGraphCollection {
        return new KnowledgeGraphNormalizer({
            mode: this.mode,
            scope: this.scope,
            nodeId: knowledgeNodeId,
        }).collect(data);
    }
    /**
     * Prepare graph nodes and edges from current records and filters.
     *
     * @returns {void}
     */
    protected prepareGraph(): void {
        const records = this.mergeScopeRecords(this.filteredRecords());
        const domainGroups = new Map<string, MergedKnowledgeRecord[]>();
        records.forEach(record => {
            if (!domainGroups.has(record.domain)) {
                domainGroups.set(record.domain, []);
            }
            domainGroups.get(record.domain)?.push(record);
        });
        const domains = Array.from(domainGroups.keys()).sort();
        this.nodes = records.map(record => this.nodeFromRecord(record, domains, domainGroups));
        this.edges = this.edgesFromRelations(records);
        this.viewportNodeIds.clear();
        this.viewportBadgeSignature = "";
        this.applyConnectivitySizing();
        this.graphLayout.layout(this.nodes, this.edges);
        this.reconcileRegionEdges();
    }
    /**
     * Merge same-name identities across scopes so their relations share one visible node.      * @param {KnowledgeRecord[]} records The records value used by this operation.
     *
     * @returns {MergedKnowledgeRecord[]} An array of merged knowledge records where duplicates are consolidated into single entries with aggregated metadata.
     */
    protected mergeScopeRecords(records: KnowledgeRecord[]): MergedKnowledgeRecord[] {
        const merged = new Map<string, MergedKnowledgeRecord>();
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
            current.knowledgeScope = current.knowledgeScopes.length > 1 ? "all" : (current.knowledgeScopes[0] ?? "global");
            current.source = current.sources.filter(Boolean).join(" · ");
            if (record.description.length > current.description.length) current.description = record.description;
        });
        return [...merged.values()];
    }
    /**
     * Convert one record into a graph node.
     *
     * @param {object} record Graph record.
     * @param {string[]} domains Domain list.
     * @param {Map<string, object[]>} domainGroups Grouped records.
     * @returns {object} Graph node.
     */
    protected nodeFromRecord(record: MergedKnowledgeRecord, domains: string[], domainGroups: Map<string, MergedKnowledgeRecord[]>): KnowledgeGraphNode {
        const domainIndex = Math.max(domains.indexOf(record.domain), 0);
        const group = domainGroups.get(record.domain) || [];
        const localIndex = Math.max(group.findIndex(item => item.id === record.id), 0);
        const domainAngle = (Math.PI * 2 * domainIndex) / Math.max(domains.length, 1);
        const localAngle = domainAngle + (localIndex / Math.max(group.length, 1)) * 0.96;
        const radius = 130 + (localIndex % 11) * 24 + domainIndex * 10;
        const baseRadius = this.mode === "classes" ? 15 : 11;
        return {
            ...record,
            x: Math.cos(localAngle) * radius,
            y: Math.sin(localAngle) * radius,
            radius: baseRadius,
            baseRadius,
            color: this.domainColor(record.domain)
        };
    }
    /**
     * Return a stable color that is never reused by another domain or superdomain.      * @param {string} domain The domain value used by this operation.
     *
     * @returns {string} A unique HSL color string associated with the provided domain.
     */
    protected domainColor(domain: string): string {
        const normalized = String(domain || "knowledge").toLowerCase();
        const existing = this.domainColors.get(normalized);
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
        } while (this.usedDomainColors.has(color));
        this.domainColors.set(normalized, color);
        this.usedDomainColors.add(color);
        return color;
    }
    /**
     * Build edges from relation data returned by the CLI facade.
     *
     * @param {object[]} records Current node records.
     * @returns {object[]} Edges.
     * @param {KnowledgeRelation[] | null} relations The relations value used by this operation.
     */
    protected edgesFromRelations(records: MergedKnowledgeRecord[], relations: KnowledgeRelation[] | null = null): KnowledgeGraphEdge[] {
        const nodeById = new Map<string, MergedKnowledgeRecord>();
        records.forEach(record => {
            nodeById.set(record.id, record);
            (record.aliases || []).forEach(alias => nodeById.set(alias, record));
        });
        const nodeByLabel = new Map<string, MergedKnowledgeRecord>(records.map(record => [`${record.domain}:${record.label}`.toLowerCase(), record]));
        const domainRelations = relations || this.relations.filter(relation => this.recordMatchesTree(relation));
        const edges = domainRelations
            .map((relation, index) => {
                const from = this.nodeForRelationEnd(nodeById, nodeByLabel, relation, "from");
                const to = this.nodeForRelationEnd(nodeById, nodeByLabel, relation, "to");
                if (!from || !to) {
                    return null;
                }
                return {
                    ...relation,
                    id: relation.id || `relation-edge-${index}`,
                    from: from.id,
                    to: to.id,
                    color: this.domainColor(relation.domain),
                };
            })
            .filter((edge): edge is KnowledgeGraphEdge => edge !== null);
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
    protected nodeForRelationEnd(nodeById: Map<string, MergedKnowledgeRecord>, nodeByLabel: Map<string, MergedKnowledgeRecord>, relation: KnowledgeRelation, side: "from" | "to"): MergedKnowledgeRecord | null {
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
    protected filteredRecords(): KnowledgeRecord[] {
        const needle = this.query.toLowerCase();
        const visualType = this.treeVisualType || (this.mode === "classes" ? "class" : this.mode === "entities" ? "entity" : "");
        const projection = this.treeProjection(
            this.domain,
            this.treeScope,
            this.sourceKind,
            this.sourcePath,
            this.treeVisualType
        );
        return projection.records
            .filter(record => (record.knowledgeScope === "global" || record.knowledgeScope === "local")
                && this.selectedScopes.has(record.knowledgeScope))
            .filter(record => !visualType || record.visualType === visualType)
            .filter(record => !needle || `${record.label} ${record.description} ${record.domain} ${record.context}`.toLowerCase().includes(needle));
    }
    /**
     * Return whether a domain is active under the selected tree node.
     *
     * @param {string} domain Domain path.
     * @returns {boolean} True when visible.
     * @param {KnowledgeRecord | KnowledgeRelation} record The record value used by this operation.
     */
    protected recordMatchesTree(record: KnowledgeRecord | KnowledgeRelation): boolean {
        if ((record.knowledgeScope !== "global" && record.knowledgeScope !== "local")
            || !this.selectedScopes.has(record.knowledgeScope)) {
            return false;
        }
        return this.recordMatchesTreeSelection(
            record,
            this.domain,
            this.treeScope,
            this.sourceKind,
            this.sourcePath,
            this.treeVisualType
        );
    }
    /**
     * Apply one explicit inclusive tree selection without depending on current UI state.      * @param {KnowledgeRecord | KnowledgeRelation} record The record value used by this operation.
     * @param {string} domain The domain value used by this operation.
     * @param {"" | KnowledgeScope} scope The scope value used by this operation.
     * @param {"" | KnowledgeSourceKind} sourceKind The source kind value used by this operation.
     * @param {string} sourcePath The source path value used by this operation.
     * @param {"" | KnowledgeVisualType} visualType The visual type value used by this operation.
     *
     * @returns {boolean} True if the record satisfies all provided filter constraints; otherwise, false.
     */
    protected recordMatchesTreeSelection(
        record: KnowledgeRecord | KnowledgeRelation,
        domain: string,
        scope: KnowledgeScope | "" = "",
        sourceKind: KnowledgeSourceKind | "" = "",
        sourcePath = "",
        visualType: KnowledgeVisualType | "" = ""
    ): boolean {
        if (scope && scope !== "all" && record.knowledgeScope !== scope) return false;
        if (visualType && "visualType" in record && record.visualType && record.visualType !== visualType) return false;
        if (sourceKind && !this.recordMatchesSourceKind(record, sourceKind, scope)) return false;
        const selectedSource = String(sourcePath || "").replaceAll("\\", "/").toLowerCase();
        if (selectedSource) {
            const source = String(record.source || "").replaceAll("\\", "/").toLowerCase();
            if (!source.includes(selectedSource) && !selectedSource.includes(source)) return false;
        }
        return domain === "all" || record.domain === domain || record.domain.startsWith(`${domain}.`);
    }
    /**
     * Classify one graph record into mutually exclusive canonical source families.      * @param {KnowledgeRecord | KnowledgeRelation} record The record value used by this operation.
     * @param {KnowledgeSourceKind} sourceKind The source kind value used by this operation.
     * @param {"" | KnowledgeScope} scope The scope value used by this operation.
     *
     * @returns {boolean} A boolean indicating whether the record's properties satisfy the criteria for the given source kind and scope.
     */
    protected recordMatchesSourceKind(
        record: KnowledgeRecord | KnowledgeRelation,
        sourceKind: KnowledgeSourceKind,
        scope: KnowledgeScope | "" = ""
    ): boolean {
        const source = String(record.source || "").replaceAll("\\", "/").toLowerCase();
        const domain = String(record.domain || "").toLowerCase();
        const isPicture = domain === "pictures" || domain.startsWith("pictures.")
            || this.pictures.some(picture => source.endsWith(String(picture.relative_path || "").replaceAll("\\", "/").toLowerCase()));
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
     * @param {"" | KnowledgeScope} scope The scope value used by this operation.
     */
    protected domains(scope: KnowledgeScope | "" = ""): string[] {
        return [...new Set([
            ...this.records.filter(record => !scope || record.knowledgeScope === scope).map(record => record.domain),
            ...this.relations.filter(relation => !scope || relation.knowledgeScope === scope).map(relation => relation.domain)
        ].filter(Boolean))].sort();
    }
    /**
     * Return visible entity/relation counts using the canvas' exact projection rules.      * @param {string} domain The domain value used by this operation.
     * @param {"" | KnowledgeScope} scope The scope value used by this operation.
     * @param {"" | KnowledgeSourceKind} sourceKind The source kind value used by this operation.
     * @param {string} sourcePath The source path value used by this operation.
     * @param {"" | KnowledgeVisualType} visualType The visual type value used by this operation.
     *
     * @returns {string} A string representing the count of entities (E) and relations (R) in the format 'E: [count] R: [count]'.
     */
    protected graphCountLabel(
        domain: string,
        scope: KnowledgeScope | "" = "",
        sourceKind: KnowledgeSourceKind | "" = "",
        sourcePath = "",
        visualType: KnowledgeVisualType | "" = ""
    ): string {
        const projection = this.treeProjection(domain, scope, sourceKind, sourcePath, visualType);
        const records = this.mergeScopeRecords(projection.records);
        const relations = projection.relations;
        const edges = this.edgesFromRelations(records, relations);
        return `E: ${records.length} R: ${edges.length}`;
    }
    /**
     * Include relation endpoints in virtual source projections without changing their canonical ownership.      * @param {string} domain The domain value used by this operation.
     * @param {"" | KnowledgeScope} scope The scope value used by this operation.
     * @param {"" | KnowledgeSourceKind} sourceKind The source kind value used by this operation.
     * @param {string} sourcePath The source path value used by this operation.
     * @param {"" | KnowledgeVisualType} visualType The visual type value used by this operation.
     *
     * @returns {KnowledgeTreeProjection} An object containing the filtered and expanded collections of records and relations.
     */
    protected treeProjection(
        domain: string,
        scope: KnowledgeScope | "" = "",
        sourceKind: KnowledgeSourceKind | "" = "",
        sourcePath = "",
        visualType: KnowledgeVisualType | "" = ""
    ): KnowledgeTreeProjection {
        const matches = (record: KnowledgeRecord | KnowledgeRelation): boolean =>
            this.recordMatchesTreeSelection(record, domain, scope, sourceKind, sourcePath, visualType);
        const relations = this.relations.filter(matches);
        const records = this.records.filter(matches);
        if (!sourceKind && !sourcePath) return { records, relations };
        const endpointIds = new Set(relations.flatMap(relation => [String(relation.from), String(relation.to)]));
        const endpointLabels = new Set(relations.flatMap(relation => [
            String(relation.fromLabel || "").toLowerCase(),
            String(relation.toLabel || "").toLowerCase()
        ]));
        const includedIds = new Set(records.map(record => String(record.id)));
        this.records.forEach(record => {
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
    protected async applyFilters() {
        this.beginGraphBusy("Filtering graph");
        await this.waitForGraphPaint();
        try {
            this.readControls();
            if (this.treeScope !== "all" && !this.selectedScopes.has(this.treeScope)) {
                this.selectedTreePath = "";
                this.treeScope = "all";
                this.domain = "all";
                this.sourceKind = "";
                this.sourcePath = "";
                this.treeVisualType = "";
            }
            this.needsViewportFit = true;
            this.prepareGraph();
            this.render();
        } finally {
            this.endGraphBusy();
        }
    }
    /**
     * Apply one tree selection without rebuilding the complete Explorer surface.
     */
    protected async applyTreeSelection() {
        this.beginGraphBusy("Focusing graph source");
        await this.waitForGraphPaint();
        try {
            this.resetGraphRegion();
            this.needsViewportFit = true;
            this.prepareGraph();
            this.syncDomainTreeSelection();
            this.drawCanvas();
            this.renderInspector();
        } finally {
            this.endGraphBusy();
        }
    }
    /**
     * Update selected tree-row styling while preserving expansion and scroll state.
     */
    protected syncDomainTreeSelection() {
        const tree = this.querySelector("[data-role='knowledge-domain-tree']");
        tree?.querySelectorAll("[data-tree-path]").forEach(button => {
            const selected = button.getAttribute("data-tree-path") === this.selectedTreePath;
            button.classList.toggle("is-active", selected);
            button.closest("[role='treeitem']")?.setAttribute("aria-selected", String(selected));
        });
    }
    /**
     * Bind DOM events.
     *
     * @returns {void}
     */
}
customElements.define(KnowledgeView.selector, KnowledgeView);
