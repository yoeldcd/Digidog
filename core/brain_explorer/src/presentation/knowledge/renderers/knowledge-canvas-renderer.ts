/**
 * Draws the Knowledge graph canvas while preserving the established visual contract.
 */
import { shortKnowledgeLabel } from "../formatters/knowledge-graph-formatter.ts";
import { pointToSegmentDistance } from "../geometry/knowledge-graph-geometry.ts";
import type { KnowledgeConnectivityMetrics, KnowledgeGraphEdge, KnowledgeGraphFocus, KnowledgeGraphNode, KnowledgePoint, KnowledgeRectangle, KnowledgeRenderFrustum, KnowledgeViewport } from "../view_models/knowledge-view-model.ts";
import { KnowledgeCanvasState } from "../state/knowledge-canvas-state.ts";
/**
 * Canvas renderer and graph-region presentation base.
 */
export abstract class KnowledgeCanvasRenderer extends KnowledgeCanvasState {
    /**
     * Bind the existing canvas element to resize and pointer lifecycle events.
     */
    protected bindCanvas() {
        const canvas = this.querySelector("[data-role='knowledge-canvas']");
        if (!(canvas instanceof HTMLCanvasElement)) {
            return;
        }
        this.resizeObserver?.disconnect();
        this.resizeObserver = new ResizeObserver(() => this.drawCanvas());
        this.resizeObserver.observe(canvas);
        canvas.addEventListener("pointerdown", event => this.onPointerDown(event, canvas));
        canvas.addEventListener("pointermove", event => this.onPointerMove(event, canvas));
        canvas.addEventListener("pointerup", event => this.onPointerUp(event, canvas));
        canvas.addEventListener("pointerleave", event => this.onPointerUp(event, canvas));
        canvas.addEventListener("wheel", event => this.onWheel(event, canvas), { passive: false });
        canvas.addEventListener("dblclick", event => {
            event.preventDefault();
            this.resetVisibleGraphViewport();
        });
        requestAnimationFrame(() => this.drawCanvas());
    }
    /**
     * Draw nodes and edges onto the canvas.
     *
     * @returns {void}
     */
    protected drawCanvas() {
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
        if (this.needsViewportFit) {
            this.fitViewport(rect);
        }
        this.updateRenderFrustum(rect);
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        context.clearRect(0, 0, rect.width, rect.height);
        this.applyConnectivitySizing(this.focusGraph());
        context.translate((rect.width / 2) + this.viewport.x, (rect.height / 2) + this.viewport.y);
        context.scale(this.viewport.scale, this.viewport.scale);
        this.drawEdges(context);
        this.drawNodes(context);
        this.syncViewportBadgeCandidates();
    }
    /**
     * Fit graph bounds into the canvas viewport.
     *
     * @param {DOMRect} rect Canvas bounds.
     * @returns {void}
     */
    protected fitViewport(rect: DOMRect): void {
        this.viewport = this.fittedViewport(rect);
        this.needsViewportFit = false;
    }
    /**
     * Calculate the centered fit camera for the complete graph or active subregion.
     *
     * @param {DOMRect} rect Canvas bounds.
     * @returns {{x: number, y: number, scale: number}} Fitted camera.
     */
    protected fittedViewport(rect: DOMRect): KnowledgeViewport {
        const focus = this.focusGraph();
        if (focus) {
            this.layoutFocusedRegion(focus);
        }
        const visibleNodes = focus
            ? this.nodes.filter(node => focus.nodeIds.has(node.id))
            : this.nodes;
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
    /**
     * Compute the current canvas viewport in graph coordinates.      * @param {DOMRect} rect The rect value used by this operation.
     */
    protected updateRenderFrustum(rect: DOMRect): void {
        const scale = Math.max(this.viewport.scale, 0.0001);
        const halfWidth = rect.width / (2 * scale);
        const halfHeight = rect.height / (2 * scale);
        const centerX = -this.viewport.x / scale;
        const centerY = -this.viewport.y / scale;
        const padding = 14 / scale;
        this.renderFrustum = {
            left: centerX - halfWidth - padding,
            right: centerX + halfWidth + padding,
            top: centerY - halfHeight - padding,
            bottom: centerY + halfHeight + padding,
            centerX,
            centerY,
            radius: Math.hypot(halfWidth, halfHeight) + padding
        };
    }
    /**
     * Return whether a node circle intersects the graph-space viewport.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     *
     * @returns {boolean} True if the node intersects the render frustum or if no frustum is defined; otherwise, false.
     */
    protected nodeIntersectsRenderFrustum(node: KnowledgeGraphNode): boolean {
        const frustum = this.renderFrustum;
        if (!frustum) {
            return true;
        }
        const radius = node.radius + (20 / Math.max(this.viewport.scale, 0.0001));
        return node.x + radius >= frustum.left
            && node.x - radius <= frustum.right
            && node.y + radius >= frustum.top
            && node.y - radius <= frustum.bottom;
    }
    /**
     * Refresh important-entity candidates from the exact nodes intersecting the canvas viewport.
     */
    protected syncViewportBadgeCandidates() {
        if (this.viewportBadgeRankingFrozen) return;
        const focus = this.focusGraph();
        const candidates = focus
            ? this.nodes.filter(node => focus.nodeIds.has(node.id))
            : this.nodes;
        const visibleIds = candidates
            .filter(node => this.nodeIntersectsRenderFrustum(node))
            .map(node => node.id);
        const signature = visibleIds.join("|") || "__empty__";
        if (signature === this.viewportBadgeSignature) {
            return;
        }
        this.viewportNodeIds = new Set(visibleIds);
        this.viewportBadgeSignature = signature;
        clearTimeout(this.viewportInspectorTimer);
        this.viewportInspectorTimer = window.setTimeout(() => {
            if (!this.viewportBadgeRankingFrozen && !this.selectedNodeId && !this.selectedRelationId) {
                this.renderInspector();
            }
        }, 140);
    }
    /**
     * Apply endpoint, circumscribed-radius, and exact edge culling.      * @param {KnowledgeGraphNode} from The from value used by this operation.
     * @param {KnowledgeGraphNode} to The to value used by this operation.
     *
     * @returns {boolean} True if either endpoint is within the frustum or the edge segment intersects the frustum area; otherwise false.
     */
    protected edgeIntersectsRenderFrustum(from: KnowledgeGraphNode, to: KnowledgeGraphNode): boolean {
        const frustum = this.renderFrustum;
        if (!frustum) {
            return true;
        }
        if (this.nodeIntersectsRenderFrustum(from) || this.nodeIntersectsRenderFrustum(to)) {
            return true;
        }
        const distance = pointToSegmentDistance(
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
        return this.segmentIntersectsFrustum(from.x, from.y, to.x, to.y, frustum);
    }
    /**
     * Test a segment against an axis-aligned viewport using Liang-Barsky.      * @param {number} x1 The x1 value used by this operation.
     * @param {number} y1 The y1 value used by this operation.
     * @param {number} x2 The x2 value used by this operation.
     * @param {number} y2 The y2 value used by this operation.
     * @param {KnowledgeRenderFrustum} frustum The frustum value used by this operation.
     *
     * @returns {boolean} True if any part of the segment lies within the frustum boundaries, otherwise false.
     */
    protected segmentIntersectsFrustum(x1: number, y1: number, x2: number, y2: number, frustum: KnowledgeRenderFrustum): boolean {
        const deltaX = x2 - x1;
        const deltaY = y2 - y1;
        const p = [-deltaX, deltaX, -deltaY, deltaY];
        const q = [x1 - frustum.left, frustum.right - x1, y1 - frustum.top, frustum.bottom - y1];
        let minimum = 0;
        let maximum = 1;
        for (let index = 0; index < 4; index += 1) {
            const pValue = p[index];
            const qValue = q[index];
            if (pValue === undefined || qValue === undefined) continue;
            if (pValue === 0) {
                if (qValue < 0) {
                    return false;
                }
                continue;
            }
            const ratio = qValue / pValue;
            if (pValue < 0) {
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
    protected layoutFocusedRegion(focus: KnowledgeGraphFocus): void {
        const focusedNodes = this.nodes.filter(node => focus.nodeIds.has(node.id));
        if (!focusedNodes.length) {
            return;
        }
        focusedNodes.forEach(node => {
            const position = this.regionPositions.get(node.id);
            if (position) {
                node.x = position.x;
                node.y = position.y;
            }
        });
        const newNodes = focusedNodes.filter(node => !this.regionPositions.has(node.id));
        if (!newNodes.length) {
            return;
        }
        const selectedPosition = this.regionPositions.get(this.selectedNodeId);
        const anchor = selectedPosition || this.regionCentroid();
        if (!this.regionPositions.size) {
            const selectedIndex = newNodes.findIndex(node => node.id === this.selectedNodeId);
            const centerIndex = selectedIndex >= 0 ? selectedIndex : 0;
            const center = newNodes.splice(centerIndex, 1)[0];
            if (!center) return;
            center.x = 0;
            center.y = 0;
            this.regionPositions.set(center.id, { x: 0, y: 0 });
        }
        const baseSlot = this.regionPositions.size;
        newNodes.forEach((node, index) => {
            const slot = baseSlot + index;
            const angle = (slot * 2.399963229728653) - (Math.PI / 2);
            const radius = 120 + (Math.floor(slot / 7) * 75);
            node.x = anchor.x + (Math.cos(angle) * radius);
            node.y = anchor.y + (Math.sin(angle) * radius);
            this.regionPositions.set(node.id, { x: node.x, y: node.y });
        });
    }
    /**
     * Return the centroid of persisted region positions.
     * @returns {KnowledgePoint} A KnowledgePoint representing the average x and y coordinates of the region, or a zeroed point if no positions exist.
     */
    protected regionCentroid(): KnowledgePoint {
        const positions = [...this.regionPositions.values()];
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
    protected drawEdges(context: CanvasRenderingContext2D): void {
        this.edgeLabelBounds.clear();
        const styles = getComputedStyle(this);
        const focus = this.focusGraph();
        const orderedEdges = focus
            ? this.edges.filter(edge => focus.edgeIds.has(edge.id))
            : this.edges;
        const nodesById = new Map(this.nodes.map(node => [node.id, node]));
        const connectivity = this.connectivityMetrics(focus);
        orderedEdges.forEach(edge => {
            const from = nodesById.get(edge.from);
            const to = nodesById.get(edge.to);
            if (!from || !to || !this.edgeIntersectsRenderFrustum(from, to)) {
                return;
            }
            const activeRelationId = this.hoveredRelationId || this.selectedRelationId;
            const selected = edge.id === activeRelationId;
            context.save();
            context.globalAlpha = 0.92;
            context.beginPath();
            context.moveTo(from.x, from.y);
            context.lineTo(to.x, to.y);
            context.strokeStyle = selected ? styles.getPropertyValue("--primary").trim() : styles.getPropertyValue("--border-strong").trim();
            context.lineWidth = selected ? 3.2 / this.viewport.scale : 1.2 / this.viewport.scale;
            context.stroke();
            this.drawEdgeArrow(context, from, to, connectivity.score(from.id));
            this.drawEdgeLabel(context, edge, from, to, selected);
            context.restore();
        });
    }
    /**
     * Draw a subject-to-object arrowhead immediately before the target node.      * @param {CanvasRenderingContext2D} context The context value used by this operation.
     * @param {KnowledgeGraphNode} from The from value used by this operation.
     * @param {KnowledgeGraphNode} to The to value used by this operation.
     * @param {number} sourceRank The source rank value used by this operation.
     */
    protected drawEdgeArrow(context: CanvasRenderingContext2D, from: KnowledgeGraphNode, to: KnowledgeGraphNode, sourceRank: number): void {
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const distance = Math.hypot(dx, dy);
        if (distance < 1) return;
        const unitX = dx / distance;
        const unitY = dy / distance;
        const scale = this.viewport.scale;
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
    protected drawEdgeLabel(context: CanvasRenderingContext2D, edge: KnowledgeGraphEdge, from: KnowledgeGraphNode, to: KnowledgeGraphNode, selected: boolean): void {
        if (!selected && this.viewport.scale < 0.45) {
            return;
        }
        const styles = getComputedStyle(this);
        const x = (from.x + to.x) / 2;
        const y = (from.y + to.y) / 2;
        const label = shortKnowledgeLabel(edge.label, selected ? 24 : 16);
        context.save();
        context.font = `${selected ? 700 : 650} ${10 / this.viewport.scale}px Inter, system-ui, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        const width = context.measureText(label).width + 12;
        const height = 18 / this.viewport.scale;
        this.edgeLabelBounds.set(edge.id, {
            left: x - width / 2,
            right: x + width / 2,
            top: y - height / 2,
            bottom: y + height / 2
        });
        context.fillStyle = styles.getPropertyValue("--surface").trim();
        context.strokeStyle = styles.getPropertyValue("--border").trim();
        this.roundedRect(context, x - width / 2, y - height / 2, width, height, 8 / this.viewport.scale);
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
    protected drawNodes(context: CanvasRenderingContext2D): void {
        this.nodeLabelBounds.clear();
        const styles = getComputedStyle(this);
        const focus = this.focusGraph();
        const activeRelationId = this.hoveredRelationId || this.selectedRelationId;
        const selectedRelation = this.edges.find(edge => edge.id === activeRelationId);
        const connectivity = this.connectivityMetrics(focus);
        const degrees = connectivity.degrees;
        const maxDegree = Math.max(0, ...degrees.values());
        const orderedNodes = focus
            ? this.nodes.filter(node => focus.nodeIds.has(node.id))
            : this.nodes;
        const visibleNodes = orderedNodes.filter(node => this.nodeIntersectsRenderFrustum(node));
        const rankedNodeIds = new Set(this.rankImportantNodes(visibleNodes).map(node => node.id));
        const rankedLabelBounds: KnowledgeRectangle[] = [];
        visibleNodes.forEach(node => {
            const selected = node.id === this.selectedNodeId;
            const hovered = node.id === this.hoveredNodeId;
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
                ? 3.4 / this.viewport.scale
                : focused ? 2.6 / this.viewport.scale : 1.8 / this.viewport.scale;
            context.setLineDash(node.visualType === "class" ? [7 / this.viewport.scale, 5 / this.viewport.scale] : []);
            context.fill();
            context.stroke();
            if (this.nodeLabelIsVisible(node, degrees, maxDegree, selected || focused, ranked)) {
                this.drawNodeLabel(context, node, selected || focused, ranked, rankedLabelBounds);
            }
            if (selected && this.nodeCanExpand(node.id)) {
                this.drawNodeExpansionBadge(context, node);
            }
            context.restore();
        });
    }
    /**
     * Return the number of visible relations incident to each node.      * @param {KnowledgeGraphFocus | null} focus The focus value used by this operation.
     *
     * @returns {Map<string, number>} A map associating each visible node identifier with its total number of incident edges.
     */
    protected nodeDegrees(focus: KnowledgeGraphFocus | null = null): Map<string, number> {
        const visibleNodeIds = focus?.nodeIds || new Set(this.nodes.map(node => node.id));
        const degrees = new Map([...visibleNodeIds].map(nodeId => [nodeId, 0]));
        this.edges.forEach(edge => {
            if (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to)) {
                return;
            }
            degrees.set(edge.from, (degrees.get(edge.from) || 0) + 1);
            degrees.set(edge.to, (degrees.get(edge.to) || 0) + 1);
        });
        return degrees;
    }
    /**
     * Return connectivity normalized against the maximum of the visible graph.      * @param {KnowledgeGraphFocus | null} focus The focus value used by this operation.
     *
     * @returns {KnowledgeConnectivityMetrics} An object containing the raw node degrees, the maximum degree found, and a function to retrieve a normalized connectivity score for a specific node.
     */
    protected connectivityMetrics(focus: KnowledgeGraphFocus | null = this.focusGraph()): KnowledgeConnectivityMetrics {
        const degrees = this.nodeDegrees(focus);
        const maxDegree = Math.max(1, ...degrees.values());
        return {
            degrees,
            maxDegree,
            score: (nodeId: string) => (degrees.get(nodeId) || 0) / maxDegree
        };
    }
    /**
     * Scale node radii by connectivity while preserving readable bounds.      * @param {KnowledgeGraphFocus | null} focus The focus value used by this operation.
     */
    protected applyConnectivitySizing(focus: KnowledgeGraphFocus | null = null): void {
        const connectivity = this.connectivityMetrics(focus);
        const baseRadius = this.mode === "classes" ? 14 : 10;
        const radiusRange = this.mode === "classes" ? 16 : 13;
        this.nodes.forEach(node => {
            const normalized = Math.sqrt(connectivity.score(node.id));
            node.radius = baseRadius + normalized * radiusRange;
        });
    }
    /**
     * Decide whether a label belongs to the zoom-dependent connectivity tier.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     * @param {Map<string, number>} degrees The degrees value used by this operation.
     * @param {number} maxDegree The max degree value used by this operation.
     * @param {boolean} emphasized The emphasized value used by this operation.
     * @param {boolean} ranked The ranked value used by this operation.
     *
     * @returns {boolean} A boolean indicating if the node label meets the visibility criteria.
     */
    protected nodeLabelIsVisible(node: KnowledgeGraphNode, degrees: Map<string, number>, maxDegree: number, emphasized: boolean, ranked = false): boolean {
        if (emphasized || ranked || this.viewport.scale >= 0.78) {
            return true;
        }
        const normalizedRank = maxDegree ? (degrees.get(node.id) || 0) / maxDegree : 0;
        const zoomProgress = Math.max(0, Math.min(1, (this.viewport.scale - 0.005) / 0.775));
        const easedTolerance = zoomProgress * zoomProgress * (3 - (2 * zoomProgress));
        const minimumRank = 0.56 * (1 - easedTolerance);
        return normalizedRank >= minimumRank;
    }
    /**
     * Return the current selected node/relation neighborhood.
     *
     * @returns {{nodeIds: Set<string>, edgeIds: Set<string>}|null} Focus ids.
     */
    protected focusGraph(): KnowledgeGraphFocus | null {
        if (!this.regionNodeIds.size) {
            return null;
        }
        return {
            nodeIds: this.regionNodeIds,
            edgeIds: this.regionEdgeIds
        };
    }
    /**
     * Return whether a node can become the root of a distinct child region.      * @param {string} nodeId The node id value used by this operation.
     *
     * @returns {boolean} True if the node has children and is not already fully expanded within the current region; otherwise, false.
     */
    protected nodeCanExpand(nodeId: string): boolean {
        const child = this.graphRegionForNode(nodeId);
        if (!child.edgeIds.size) return false;
        if (!this.regionNodeIds.size) return true;
        return child.nodeIds.size !== this.regionNodeIds.size
            || [...child.nodeIds].some(id => !this.regionNodeIds.has(id));
    }
    /**
     * Draw a screen-stable expansion affordance above a selected node.      * @param {CanvasRenderingContext2D} context The context value used by this operation.
     * @param {KnowledgeGraphNode} node The node value used by this operation.
     */
    protected drawNodeExpansionBadge(context: CanvasRenderingContext2D, node: KnowledgeGraphNode): void {
        const styles = getComputedStyle(this);
        const scale = this.viewport.scale;
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
    /**
     * Build the child region rooted at one node and its immediate neighbors.      * @param {string} nodeId The node id value used by this operation.
     *
     * @returns {KnowledgeGraphFocus} An object containing the sets of node and edge identifiers that form the focused graph region.
     */
    protected graphRegionForNode(nodeId: string): KnowledgeGraphFocus {
        const nodeIds = new Set<string>(nodeId ? [nodeId] : []);
        const edgeIds = new Set<string>();
        this.edges.forEach(edge => {
            if (edge.from !== nodeId && edge.to !== nodeId) {
                return;
            }
            edgeIds.add(edge.id);
            nodeIds.add(edge.from);
            nodeIds.add(edge.to);
        });
        this.edges.forEach(edge => {
            if (nodeIds.has(edge.from) && nodeIds.has(edge.to)) edgeIds.add(edge.id);
        });
        return { nodeIds, edgeIds };
    }
    /**
     * Reconcile a preserved region after the graph records are rebuilt.
     */
    protected reconcileRegionEdges() {
        const availableNodeIds = new Set(this.nodes.map(node => node.id));
        this.regionNodeIds = new Set([...this.regionNodeIds].filter(id => availableNodeIds.has(id)));
        this.regionEdgeIds = new Set(this.edges
            .filter(edge => this.regionNodeIds.has(edge.from) && this.regionNodeIds.has(edge.to))
            .map(edge => edge.id));
    }
    /**
     * Capture the current level before navigating to a child region.
     * @returns {{ nodeIds: Set<string>; edgeIds: Set<string>; positions: Map<string, KnowledgePoint>; graphPositions: Map<string, { x: number; y: number; }>; rootNodeId: string; selectedNodeId: string; selectedRelationId: string; viewport: { x: number; y: number; scale: number; }; }} A snapshot object containing sets of region IDs, position maps, root and selection identifiers, and the current viewport state.
     */
    protected captureGraphRegionLevel() {
        return {
            nodeIds: new Set(this.regionNodeIds),
            edgeIds: new Set(this.regionEdgeIds),
            positions: new Map(this.regionPositions),
            graphPositions: new Map(this.nodes.map(node => [node.id, { x: node.x, y: node.y }])),
            rootNodeId: this.regionRootNodeId,
            selectedNodeId: this.selectedNodeId,
            selectedRelationId: this.selectedRelationId,
            viewport: { ...this.viewport }
        };
    }
    /**
     * Replace the current graph level with a child region rooted at one node.      * @param {string} nodeId The node id value used by this operation.
     */
    protected navigateGraphRegion(nodeId: string): void {
        if (!this.nodeCanExpand(nodeId)) return;
        const child = this.graphRegionForNode(nodeId);
        this.regionHistory.push(this.captureGraphRegionLevel());
        this.regionNodeIds = child.nodeIds;
        this.regionEdgeIds = child.edgeIds;
        this.regionPositions = new Map();
        this.regionRootNodeId = nodeId;
        this.selectedNodeId = nodeId;
        this.selectedRelationId = "";
        this.focusViewport = null;
        const focus = this.focusGraph();
        if (focus) this.layoutFocusedRegion(focus);
        this.needsViewportFit = true;
        this.drawCanvas();
        this.renderInspector();
    }
    /**
     * Restore exactly one parent graph level, including its layout and camera.
     */
    protected navigateBackGraphRegion() {
        const previous = this.regionHistory.pop();
        if (!previous) return;
        cancelAnimationFrame(this.cameraAnimationFrame);
        this.cameraAnimationFrame = 0;
        this.regionNodeIds = new Set(previous.nodeIds);
        this.regionEdgeIds = new Set(previous.edgeIds);
        this.regionPositions = new Map(previous.positions);
        this.regionRootNodeId = previous.rootNodeId;
        this.selectedNodeId = previous.selectedNodeId;
        this.selectedRelationId = previous.selectedRelationId;
        previous.graphPositions.forEach((position, nodeId) => {
            const node = this.nodes.find(item => item.id === nodeId);
            if (node) Object.assign(node, position);
        });
        this.viewport = { ...previous.viewport };
        this.needsViewportFit = false;
        this.focusViewport = null;
        this.hoveredNodeId = "";
        this.hoveredRelationId = "";
        this.relationHoverViewport = null;
        this.badgeHoverViewport = null;
        this.drawCanvas();
        this.renderInspector();
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
    protected drawNodeLabel(context: CanvasRenderingContext2D, node: KnowledgeGraphNode, selected: boolean, ranked = false, occupiedBounds: KnowledgeRectangle[] = []): void {
        const styles = getComputedStyle(this);
        const label = shortKnowledgeLabel(node.label, selected ? 28 : 18);
        const fontSize = selected ? 12 : ranked ? 11 : 10;
        const scale = this.viewport.scale;
        context.save();
        context.font = `800 ${fontSize / scale}px Inter, system-ui, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        const width = context.measureText(label).width + (14 / scale);
        const height = (fontSize + 8) / scale;
        const placement = ranked
            ? this.rankedLabelPlacement(node, width, height, occupiedBounds)
            : { x: node.x, y: node.y + node.radius + (14 / scale) };
        const x = placement.x;
        const y = placement.y;
        if (ranked || selected) {
            context.fillStyle = styles.getPropertyValue("--surface").trim();
            context.strokeStyle = node.color;
            context.lineWidth = 1.5 / scale;
            this.roundedRect(context, x - width / 2, y - height / 2, width, height, 8 / scale);
            context.fill();
            context.stroke();
            this.nodeLabelBounds.set(node.id, {
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
    /**
     * Place one screen-stable ranked label without intersecting earlier ranked labels.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     * @param {number} width The width value used by this operation.
     * @param {number} height The height value used by this operation.
     * @param {KnowledgeRectangle[]} occupiedBounds The occupied bounds value used by this operation.
     *
     * @returns {KnowledgePoint} The selected coordinate for the label placement, which is then added to the occupied bounds.
     */
    protected rankedLabelPlacement(node: KnowledgeGraphNode, width: number, height: number, occupiedBounds: KnowledgeRectangle[]): KnowledgePoint {
        const scale = this.viewport.scale;
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
        const rectangleFor = (candidate: KnowledgePoint): KnowledgeRectangle => ({
            left: candidate.x - width / 2 - padding,
            right: candidate.x + width / 2 + padding,
            top: candidate.y - height / 2 - padding,
            bottom: candidate.y + height / 2 + padding
        });
        const overlaps = (rectangle: KnowledgeRectangle): boolean => occupiedBounds.some(other => (
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
    protected roundedRect(context: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number): void {
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
}