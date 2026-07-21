/**
 * Controls Knowledge canvas pointer, camera, selection, and hit-testing behavior.
 */
import { pointToSegmentDistance } from "../geometry/knowledge-graph-geometry.ts";
import type { KnowledgeGraphEdge, KnowledgeGraphNode, KnowledgePoint, KnowledgeViewport } from "../view_models/knowledge-view-model.ts";
import { KnowledgeCanvasRenderer } from "../renderers/knowledge-canvas-renderer.ts";

/**
 * Interaction controller proxied by the concrete Knowledge layout.
 */
export abstract class KnowledgeCanvasInteractionController extends KnowledgeCanvasRenderer {
    /**
     * Begin node dragging, region navigation, relation selection, or canvas panning.      * @param {PointerEvent} event The event value used by this operation.
     * @param {HTMLCanvasElement} canvas The canvas value used by this operation.
     */
    protected onPointerDown(event: PointerEvent, canvas: HTMLCanvasElement): void {
        const point = this.canvasPoint(event, canvas);
        const expansionNode = this.hitTestNodeExpansionBadge(point.x, point.y);
        if (expansionNode) {
            event.preventDefault();
            this.navigateGraphRegion(expansionNode.id);
            return;
        }
        const labelNode = this.hitTestNodeLabel(point.x, point.y);
        if (labelNode) {
            event.preventDefault();
            this.focusNode(labelNode.id);
            return;
        }
        const labelEdge = this.hitTestEdgeLabel(point.x, point.y);
        if (labelEdge) {
            this.selectRelation(labelEdge.id);
            return;
        }
        const node = this.hitTestNode(point.x, point.y);
        const edge = this.hitTestEdge(point.x, point.y);
        if (edge && (!node || !this.nodeOwnsPoint(node, point.x, point.y))) {
            this.selectRelation(edge.id);
            return;
        }
        if (node) {
            this.pointerCandidate = {
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
            this.selectRelation(edge.id);
            return;
        }
        if (this.selectedNodeId || this.selectedRelationId) {
            this.selectedNodeId = "";
            this.selectedRelationId = "";
            this.restoreFocusViewport();
            this.renderInspector();
            return;
        }
        this.panState = {
            pointerId: event.pointerId,
            clientX: event.clientX,
            clientY: event.clientY,
            startX: this.viewport.x,
            startY: this.viewport.y
        };
        cancelAnimationFrame(this.cameraAnimationFrame);
        this.cameraAnimationFrame = 0;
        canvas.setPointerCapture(event.pointerId);
    }

    /**
     * Smoothly center one node while optionally changing the camera scale.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     * @param {number} targetScale The target scale value used by this operation.
     */
    protected animateCameraToNode(node: KnowledgeGraphNode, targetScale: number): void {
        this.animateViewport({
            x: -node.x * targetScale,
            y: -node.y * targetScale,
            scale: targetScale
        });
    }

    /**
     * Smoothly center one relation midpoint while optionally changing camera scale.      * @param {KnowledgeGraphEdge} relation The relation value used by this operation.
     * @param {number} targetScale The target scale value used by this operation.
     */
    protected animateCameraToRelation(relation: KnowledgeGraphEdge, targetScale: number): void {
        const source = this.nodes.find(node => node.id === relation.from);
        const target = this.nodes.find(node => node.id === relation.to);
        if (!source || !target) {
            return;
        }
        this.animateViewport({
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
    protected animateViewport(target: KnowledgeViewport, onComplete: (() => void) | null = null): void {
        cancelAnimationFrame(this.cameraAnimationFrame);
        this.needsViewportFit = false;
        const start = { ...this.viewport };
        const startedAt = performance.now();
        const duration = 420;
        const animate = (now: number): void => {
            const progress = Math.max(0, Math.min(1, (now - startedAt) / duration));
            const eased = 1 - Math.pow(1 - progress, 3);
            this.viewport = {
                x: start.x + (target.x - start.x) * eased,
                y: start.y + (target.y - start.y) * eased,
                scale: start.scale + (target.scale - start.scale) * eased
            };
            this.drawCanvas();
            if (progress < 1) {
                this.cameraAnimationFrame = requestAnimationFrame(animate);
            } else {
                this.cameraAnimationFrame = 0;
                onComplete?.();
            }
        };
        this.cameraAnimationFrame = requestAnimationFrame(animate);
    }

    /**
     * Focus one node while preserving the camera that preceded the focus zoom.      * @param {string} nodeId The node id value used by this operation.
     */
    protected focusNode(nodeId: string): void {
        const node = this.nodes.find(item => item.id === nodeId);
        if (!node) {
            return;
        }
        const hadRegion = this.regionNodeIds.size > 0;
        if (!this.selectedNodeId) {
            this.focusViewport = this.badgeHoverViewport
                ? { ...this.badgeHoverViewport }
                : { ...this.viewport };
        }
        this.badgeHoverViewport = null;
        this.viewportBadgeRankingFrozen = false;
        this.hoveredNodeId = "";
        this.selectedNodeId = node.id;
        this.selectedRelationId = "";
        this.animateCameraToNode(node, hadRegion ? this.viewport.scale : Math.max(this.viewport.scale, 1.35));
        this.renderInspector();
    }

    /**
     * Select and center one relation without mutating the graph region.      * @param {string} relationId The relation id value used by this operation.
     */
    protected selectRelation(relationId: string): void {
        const relation = this.edges.find(edge => edge.id === relationId);
        if (!relation) {
            return;
        }
        if (!this.selectedNodeId && !this.selectedRelationId) {
            this.focusViewport = this.relationHoverViewport
                ? { ...this.relationHoverViewport }
                : { ...this.viewport };
        }
        this.selectedRelationId = relationId;
        this.selectedNodeId = "";
        this.hoveredRelationId = "";
        this.hoveredNodeId = "";
        this.relationHoverViewport = null;
        this.badgeHoverViewport = null;
        this.viewportBadgeRankingFrozen = false;
        this.animateCameraToRelation(relation, Math.max(this.viewport.scale, 1.35));
        this.renderInspector();
    }

    /**
     * Restore the camera snapshot captured immediately before entity focus.
     */
    protected restoreFocusViewport() {
        if (!this.focusViewport) {
            this.drawCanvas();
            return;
        }
        const previousViewport = this.focusViewport;
        this.focusViewport = null;
        this.animateViewport(previousViewport);
    }

    /**
     * Move a dragged node or pan the graph.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    protected onPointerMove(event: PointerEvent, canvas: HTMLCanvasElement): void {
        if (this.pointerCandidate && !this.dragNode) {
            const distance = Math.hypot(
                event.clientX - this.pointerCandidate.clientX,
                event.clientY - this.pointerCandidate.clientY
            );
            if (distance >= 4) {
                this.pointerCandidate.moved = true;
                this.dragNode = {
                    id: this.pointerCandidate.id,
                    offsetX: this.pointerCandidate.offsetX,
                    offsetY: this.pointerCandidate.offsetY
                };
            }
        }
        if (this.dragNode) {
            const point = this.canvasPoint(event, canvas);
            const dragNode = this.dragNode;
            const node = this.nodes.find(item => item.id === dragNode.id);
            if (!node) {
                return;
            }
            node.x = point.x - dragNode.offsetX;
            node.y = point.y - dragNode.offsetY;
            if (this.regionNodeIds.has(node.id)) {
                this.regionPositions.set(node.id, { x: node.x, y: node.y });
            }
            this.drawCanvas();
            return;
        }
        if (!this.panState) {
            return;
        }
        this.viewport.x = this.panState.startX + (event.clientX - this.panState.clientX);
        this.viewport.y = this.panState.startY + (event.clientY - this.panState.clientY);
        this.drawCanvas();
    }

    /**
     * End dragging or panning.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    protected onPointerUp(event: PointerEvent, canvas: HTMLCanvasElement): void {
        const candidate = this.pointerCandidate;
        if (candidate && !candidate.moved) {
            this.focusNode(candidate.id);
        }
        this.pointerCandidate = null;
        this.dragNode = null;
        this.panState = null;
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
    protected onWheel(event: WheelEvent, canvas: HTMLCanvasElement): void {
        event.preventDefault();
        cancelAnimationFrame(this.cameraAnimationFrame);
        this.cameraAnimationFrame = 0;
        const rect = canvas.getBoundingClientRect();
        const cursorX = event.clientX - rect.left - rect.width / 2;
        const cursorY = event.clientY - rect.top - rect.height / 2;
        const previousScale = this.viewport.scale;
        const nextScale = Math.min(3.4, Math.max(0.005, previousScale * (event.deltaY > 0 ? 0.9 : 1.1)));
        const graphX = (cursorX - this.viewport.x) / previousScale;
        const graphY = (cursorY - this.viewport.y) / previousScale;
        this.viewport.x = cursorX - graphX * nextScale;
        this.viewport.y = cursorY - graphY * nextScale;
        this.viewport.scale = nextScale;
        this.needsViewportFit = false;
        this.drawCanvas();
    }

    /**
     * Refresh the inspector without replacing the canvas.
     *
     * @returns {void}
     */
    protected renderInspector() {
        const inspector = this.querySelector(".graph-detail-list");
        if (!inspector) {
            return;
        }
        inspector.innerHTML = this.renderDetails();
        const relationPreviewHost = this.querySelector("[data-role='relation-preview-host']");
        if (relationPreviewHost) {
            relationPreviewHost.innerHTML = this.renderRelationPreview();
        }
        const backButton = this.querySelector("[data-action='navigate-region-back']");
        if (backButton) {
            if (backButton instanceof HTMLElement) backButton.hidden = !this.regionHistory.length;
        }
        this.bindInspectorButtons();
    }

    /**
     * Reset camera zoom and center while preserving the current graph or subregion.
     */
    protected resetVisibleGraphViewport() {
        cancelAnimationFrame(this.cameraAnimationFrame);
        this.cameraAnimationFrame = 0;
        this.hoveredNodeId = "";
        this.hoveredRelationId = "";
        this.relationHoverViewport = null;
        this.badgeHoverViewport = null;
        const canvas = this.querySelector("[data-role='knowledge-canvas']");
        if (!(canvas instanceof HTMLCanvasElement)) return;
        this.viewportBadgeRankingFrozen = true;
        this.needsViewportFit = false;
        const target = this.fittedViewport(canvas.getBoundingClientRect());
        this.animateViewport(target, () => this.releaseViewportBadgeRanking());
        this.renderInspector();
    }

    /**
     * Clear persistent region state without rendering.
     */
    protected resetGraphRegion() {
        this.selectedNodeId = "";
        this.selectedRelationId = "";
        this.hoveredNodeId = "";
        this.hoveredRelationId = "";
        this.regionNodeIds.clear();
        this.regionEdgeIds.clear();
        this.regionPositions.clear();
        this.regionHistory = [];
        this.regionRootNodeId = "";
        this.focusViewport = null;
        this.relationHoverViewport = null;
        this.badgeHoverViewport = null;
        this.viewportBadgeRankingFrozen = false;
    }

    /**
     * Convert viewport pointer coordinates into graph coordinates.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {{x: number, y: number}} Graph point.
     */
    protected canvasPoint(event: PointerEvent, canvas: HTMLCanvasElement): KnowledgePoint {
        const rect = canvas.getBoundingClientRect();
        return {
            x: (event.clientX - rect.left - rect.width / 2 - this.viewport.x) / this.viewport.scale,
            y: (event.clientY - rect.top - rect.height / 2 - this.viewport.y) / this.viewport.scale
        };
    }

    /**
     * Find a node under graph coordinates.
     *
     * @param {number} x Graph x.
     * @param {number} y Graph y.
     * @returns {object|null} Hit node.
     */
    protected hitTestNode(x: number, y: number): KnowledgeGraphNode | null {
        const focus = this.focusGraph();
        const candidates = focus ? this.nodes.filter(node => focus.nodeIds.has(node.id)) : this.nodes;
        return [...candidates].reverse().find(node => {
            const dx = node.x - x;
            const dy = node.y - y;
            return Math.sqrt((dx * dx) + (dy * dy)) <= node.radius + (16 / this.viewport.scale);
        }) || null;
    }

    /**
     * Find the selected node whose explicit child-region affordance contains a point.      * @param {number} x The x value used by this operation.
     * @param {number} y The y value used by this operation.
     *
     * @returns {KnowledgeGraphNode | null} The KnowledgeGraphNode associated with the hit badge, or null if no intersection occurs or the node is not expandable.
     */
    protected hitTestNodeExpansionBadge(x: number, y: number): KnowledgeGraphNode | null {
        if (!this.selectedNodeId || !this.nodeCanExpand(this.selectedNodeId)) return null;
        const node = this.nodes.find(item => item.id === this.selectedNodeId);
        if (!node || (this.regionNodeIds.size && !this.regionNodeIds.has(node.id))) return null;
        const badgeX = node.x + node.radius * 0.72;
        const badgeY = node.y - node.radius * 0.72;
        const hitRadius = 13 / this.viewport.scale;
        return Math.hypot(x - badgeX, y - badgeY) <= hitRadius ? node : null;
    }

    /**
     * Resolve ranked node-label rectangles before relation labels and node hit halos.      * @param {number} x The x value used by this operation.
     * @param {number} y The y value used by this operation.
     *
     * @returns {KnowledgeGraphNode | null} The KnowledgeGraphNode associated with the intersected label, or null if no label was hit.
     */
    protected hitTestNodeLabel(x: number, y: number): KnowledgeGraphNode | null {
        const padding = 5 / Math.max(this.viewport.scale, 0.005);
        for (const [nodeId, bounds] of [...this.nodeLabelBounds.entries()].reverse()) {
            if (x < bounds.left - padding || x > bounds.right + padding
                || y < bounds.top - padding || y > bounds.bottom + padding) continue;
            return this.nodes.find(node => node.id === nodeId) || null;
        }
        return null;
    }

    /**
     * Return whether a point belongs to the visible node body rather than its generous hit halo.      * @param {KnowledgeGraphNode} node The node value used by this operation.
     * @param {number} x The x value used by this operation.
     * @param {number} y The y value used by this operation.
     *
     * @returns {boolean} True if the point is within the node's expanded boundary; otherwise, false.
     */
    protected nodeOwnsPoint(node: KnowledgeGraphNode, x: number, y: number): boolean {
        return Math.hypot(node.x - x, node.y - y) <= node.radius + (4 / this.viewport.scale);
    }

    /**
     * Find a relation whose rendered label rectangle contains graph coordinates.      * @param {number} x The x value used by this operation.
     * @param {number} y The y value used by this operation.
     *
     * @returns {KnowledgeGraphEdge | null} The KnowledgeGraphEdge associated with the intersected label, or null if no intersection is found.
     */
    protected hitTestEdgeLabel(x: number, y: number): KnowledgeGraphEdge | null {
        const focus = this.focusGraph();
        const candidates = focus ? this.edges.filter(edge => focus.edgeIds.has(edge.id)) : this.edges;
        const padding = 4 / this.viewport.scale;
        return [...candidates].reverse().find(edge => {
            const bounds = this.edgeLabelBounds.get(edge.id);
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
    protected hitTestEdge(x: number, y: number): KnowledgeGraphEdge | null {
        const focus = this.focusGraph();
        const candidates = focus ? this.edges.filter(edge => focus.edgeIds.has(edge.id)) : this.edges;
        return [...candidates].reverse().find(edge => {
            const from = this.nodes.find(node => node.id === edge.from);
            const to = this.nodes.find(node => node.id === edge.to);
            if (!from || !to) {
                return false;
            }
            return pointToSegmentDistance(x, y, from.x, from.y, to.x, to.y) <= 7 / this.viewport.scale;
        }) || null;
    }
    /**
     * Bind page, filter, inspector, and graph action events after a full render.
     */
    protected bindEvents() {
        this.querySelector("[data-action='show-records']")?.addEventListener("click", () => this.showRecords(true));
        this.querySelector("[data-action='query-records']")?.addEventListener("click", () => this.queryRecords());
        this.querySelector("[data-action='review-deltas']")?.addEventListener("click", () => this.reviewDeltas());
        this.querySelector("[data-action='fit-graph']")?.addEventListener("click", () => {
            this.resetVisibleGraphViewport();
        });
        this.querySelector("[data-action='navigate-region-back']")?.addEventListener("click", () => {
            this.navigateBackGraphRegion();
        });
        this.querySelector(".filter-menu")?.addEventListener("toggle", event => {
            if (event.currentTarget instanceof HTMLDetailsElement) {
                this.filtersOpen = event.currentTarget.open;
            }
        });
        this.querySelectorAll("[data-action='select-domain']").forEach(button => {
            button.addEventListener("click", () => {
                const domain = button.getAttribute("data-domain-path") || "all";
                this.domain = domain;
                this.resetGraphRegion();
                if (this.expandedDomains.has(domain)) {
                    this.expandedDomains.delete(domain);
                } else {
                    this.expandedDomains.add(domain);
                }
                this.applyFilters();
            });
        });
        this.querySelector("[data-role='kg-query']")?.addEventListener("input", () => {
            this.readControls();
            this.needsViewportFit = true;
            this.prepareGraph();
            this.drawCanvas();
            this.renderInspector();
        });
        this.querySelector("[data-role='kg-query']")?.addEventListener("keydown", event => {
            if (event instanceof KeyboardEvent && event.key === "Enter") {
                this.queryRecords();
            }
        });
        this.querySelectorAll("[data-filter-kind='kg-scope']").forEach(input => {
            input.addEventListener("change", () => this.applyFilters());
        });
        this.querySelectorAll("[data-filter-kind='kg-mode']").forEach(input => {
            input.addEventListener("change", () => this.applyFilters());
        });
        this.bindInspectorButtons();
    }

    /**
     * Bind inspector relation/node selection buttons.
     *
     * @returns {void}
     */
    protected bindInspectorButtons() {
        this.querySelectorAll("[data-action='open-detail-source']").forEach(button => {
            button.addEventListener("click", () => {
                const route = button.getAttribute("data-route") || "";
                if (route === "pictures") {
                    this.state?.setRouteTarget?.("pictures", { pictureId: button.getAttribute("data-picture-id") || "" });
                    return;
                }
                const messageId = button.getAttribute("data-message-id") || "";
                const message = this.messages.find(item => String(item.id) === messageId);
                const session = this.messageSessions.find(item => item.date === message?.date && item.chatId === message?.chat_id);
                this.state?.setRouteTarget?.("messages", { messageId, sessionId: session?.id || "" });
            });
        });
        this.querySelectorAll("[data-action='focus-node']").forEach(button => {
            button.addEventListener("pointerenter", () => {
                this.showHoveredEndpoint(button.getAttribute("data-node-id") || "");
            });
            button.addEventListener("pointerleave", () => this.showHoveredEndpoint(""));
            button.addEventListener("click", () => this.focusNode(button.getAttribute("data-node-id") || ""));
        });
        this.querySelectorAll("[data-action='resolve-description-entity']").forEach(button => {
            button.addEventListener("click", () => this.focusEntityByLabel(button.getAttribute("data-entity-label") || ""));
        });
        this.querySelectorAll("[data-action='select-node']").forEach(button => {
            button.addEventListener("click", () => {
                this.focusNode(button.getAttribute("data-node-id") || "");
            });
        });
        this.querySelectorAll("[data-action='select-relation']").forEach(button => {
            button.addEventListener("pointerenter", () => {
                this.showHoveredRelation(button.getAttribute("data-relation-id") || "");
            });
            button.addEventListener("pointerleave", () => {
                this.showHoveredRelation("");
            });
            button.addEventListener("click", () => {
                this.selectRelation(button.getAttribute("data-relation-id") || "");
            });
        });
        this.bindRelationEndpointButtons();
    }

    /**
     * Bind transient and persistent navigation on relation endpoint badges.
     */
    protected bindRelationEndpointButtons() {
        this.querySelectorAll("[data-action='navigate-relation-endpoint']").forEach(button => {
            const nodeId = button.getAttribute("data-node-id") || "";
            button.addEventListener("pointerenter", () => this.showHoveredEndpoint(nodeId));
            button.addEventListener("pointerleave", () => this.showHoveredEndpoint(""));
            button.addEventListener("click", () => this.navigateRelationEndpoint(nodeId));
        });
    }

    /**
     * Update the existing relation preview and camera from one transient sidepanel hover.      * @param {string} relationId The relation id value used by this operation.
     */
    protected showHoveredRelation(relationId: string): void {
        const relation = this.edges.find(edge => edge.id === relationId);
        if (relation) {
            if (!this.hoveredRelationId) {
                this.relationHoverViewport = { ...this.viewport };
            }
            this.hoveredRelationId = relation.id;
            this.hoveredNodeId = "";
            this.animateCameraToRelation(relation, Math.max(this.viewport.scale, 1.35));
        } else {
            this.hoveredRelationId = "";
            this.hoveredNodeId = "";
            if (this.relationHoverViewport) {
                const previousViewport = this.relationHoverViewport;
                this.relationHoverViewport = null;
                this.animateViewport(previousViewport);
            } else {
                this.drawCanvas();
            }
        }
        const relationPreviewHost = this.querySelector("[data-role='relation-preview-host']");
        if (relationPreviewHost) {
            relationPreviewHost.innerHTML = this.renderRelationPreview();
        }
        this.bindRelationEndpointButtons();
    }

    /**
     * Preview one endpoint node while preserving the camera that preceded badge hover.      * @param {string} nodeId The node id value used by this operation.
     */
    protected showHoveredEndpoint(nodeId: string): void {
        const node = this.nodes.find(item => item.id === nodeId);
        if (node) {
            if (!this.hoveredNodeId) {
                this.badgeHoverViewport = { ...this.viewport };
            }
            this.viewportBadgeRankingFrozen = true;
            clearTimeout(this.viewportInspectorTimer);
            this.hoveredNodeId = node.id;
            this.animateCameraToNode(node, Math.max(this.viewport.scale, 1.35));
            return;
        }
        this.hoveredNodeId = "";
        if (this.badgeHoverViewport) {
            const previousViewport = this.badgeHoverViewport;
            this.badgeHoverViewport = null;
            this.animateViewport(previousViewport, () => this.releaseViewportBadgeRanking());
        } else {
            this.releaseViewportBadgeRanking();
            this.drawCanvas();
        }
    }

    /**
     * Resume viewport-driven badge ranking after a transient entity preview fully returns.
     */
    protected releaseViewportBadgeRanking() {
        this.viewportBadgeRankingFrozen = false;
        this.syncViewportBadgeCandidates();
    }

    /**
     * Persist camera navigation to one relation endpoint without replacing relation selection.      * @param {string} nodeId The node id value used by this operation.
     */
    protected navigateRelationEndpoint(nodeId: string): void {
        const node = this.nodes.find(item => item.id === nodeId);
        if (!node) {
            return;
        }
        this.badgeHoverViewport = null;
        this.viewportBadgeRankingFrozen = false;
        this.hoveredNodeId = node.id;
        this.animateCameraToNode(node, Math.max(this.viewport.scale, 1.35));
    }

    /**
     * Resolve one description badge to the most connected matching graph node.      * @param {string} label The label value used by this operation.
     *
     * @returns {boolean} True if a matching node was found and focused, otherwise false.
     */
    protected focusEntityByLabel(label: string): boolean {
        const normalized = String(label || "").trim().toLowerCase();
        if (!normalized) return false;
        const degrees = this.nodeDegrees();
        const match = this.nodes
            .filter(node => String(node.label || "").trim().toLowerCase() === normalized)
            .sort((left, right) => (degrees.get(right.id) || 0) - (degrees.get(left.id) || 0))[0];
        if (!match) return false;
        this.focusNode(match.id);
        return true;
    }

    /**
     * Focus a route-targeted entity after the graph has been prepared.
     */
    protected resolvePendingEntity(): void {
        if (!this.pendingEntityLabel) return;
        const label = this.pendingEntityLabel;
        if (this.focusEntityByLabel(label)) this.pendingEntityLabel = "";
    }

    /**
     * Bind canvas drawing and pointer interaction.
     *
     * @returns {void}
     */

}
