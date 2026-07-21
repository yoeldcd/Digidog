/**
 * Positions Knowledge graph nodes as connected components and domain grids.
 *
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import type {
    KnowledgeComponentBounds,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeNodeFootprint,
} from "../view_models/knowledge-view-model.ts";

/**
 * Breadth-first traversal entry used while assigning neighbor depth.
 */
interface KnowledgeTraversalQueueEntry {
    /**
     * Identifier of the graph node awaiting traversal.
     * @type {string}
     */
    readonly id: string;
    /**
     * Neighbor depth measured from the active component root.
     * @type {number}
     */
    readonly depth: number;
}

/**
 * Mutating layout engine whose sole output is graph-node coordinates.
 */
export class KnowledgeGraphLayoutEngine {
    /**
     * Nodes participating in the current bounded layout operation.
     * @type {KnowledgeGraphNode[]}
     */
    #nodes: KnowledgeGraphNode[] = [];
    /**
     * Edges participating in the current bounded layout operation.
     * @type {KnowledgeGraphEdge[]}
     */
    #edges: KnowledgeGraphEdge[] = [];

    /**
     * Position supplied nodes in place while preserving their identity and metadata.
     * @param {KnowledgeGraphNode[]} nodes Mutable graph nodes to position.
     * @param {readonly KnowledgeGraphEdge[]} edges Immutable graph connectivity used by the layout.
     */
    layout(nodes: KnowledgeGraphNode[], edges: readonly KnowledgeGraphEdge[]): void {
        this.#nodes = nodes;
        this.#edges = [...edges];
        this.#layoutGraphByNeighbors();
    }

    /**
     * Layout nodes as connected neighbor groups and isolated domain grids.
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

    /**
     * Estimate each node's visual footprint from radius, labels, connectivity, and predicates.
     * @returns {Map<string, { width: number; height: number; gap: number; relationLabelWidth: number; }>} A map associating node identifiers with their calculated layout footprints, including width, height, gap, and relation label width.
     */
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
     * Return the number of layout edges incident to every projected node.
     * @returns {Map<string, number>} A map associating each node identifier with its total edge count.
     */
    #nodeDegrees(): Map<string, number> {
        const degrees = new Map(this.#nodes.map(node => [node.id, 0]));
        this.#edges.forEach(edge => {
            degrees.set(edge.from, (degrees.get(edge.from) || 0) + 1);
            degrees.set(edge.to, (degrees.get(edge.to) || 0) + 1);
        });
        return degrees;
    }

    /**
     * Expand connected components by neighbor depth.
     *
     * @param {object[]} nodes Connected nodes.
     * @param {number} startY Vertical offset.
     * @returns {void}
     * @param {Map<string, KnowledgeNodeFootprint>} footprints The footprints value used by this operation.
     */
    #layoutConnectedNodes(nodes: KnowledgeGraphNode[], startY: number, footprints: Map<string, KnowledgeNodeFootprint>): void {
        const byId = new Map(nodes.map(node => [node.id, node]));
        const adjacency = this.#adjacencyMap(byId);
        const visited = new Set<string>();
        const components: string[][] = [];
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

    /**
     * Return a component rectangle that includes node and label footprints.      * @param {string[]} component The component value used by this operation.
     * @param {Map<string, KnowledgeGraphNode>} byId The by id value used by this operation.
     * @param {Map<string, KnowledgeNodeFootprint>} footprints The footprints value used by this operation.
     *
     * @returns {KnowledgeComponentBounds} An object containing the minimum and maximum coordinates and the total calculated width and height of the component.
     */
    #componentBounds(component: string[], byId: Map<string, KnowledgeGraphNode>, footprints: Map<string, KnowledgeNodeFootprint>): KnowledgeComponentBounds {
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

    /**
     * Translate every node in one already-positioned connected component.      * @param {string[]} component The component value used by this operation.
     * @param {Map<string, KnowledgeGraphNode>} byId The by id value used by this operation.
     * @param {number} deltaX The delta x value used by this operation.
     * @param {number} deltaY The delta y value used by this operation.
     */
    #translateComponent(component: string[], byId: Map<string, KnowledgeGraphNode>, deltaX: number, deltaY: number): void {
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
    #adjacencyMap(byId: Map<string, KnowledgeGraphNode>): Map<string, Set<string>> {
        const adjacency = new Map<string, Set<string>>([...byId.keys()].map(id => [id, new Set<string>()]));
        this.#edges.forEach(edge => {
            if (!byId.has(edge.from) || !byId.has(edge.to)) {
                return;
            }
            adjacency.get(edge.from)?.add(edge.to);
            adjacency.get(edge.to)?.add(edge.from);
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
    #componentFromNode(rootId: string, adjacency: Map<string, Set<string>>, visited: Set<string>): string[] {
        const queue: string[] = [rootId];
        const component: string[] = [];
        visited.add(rootId);
        while (queue.length) {
            const current = queue.shift();
            if (!current) continue;
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
    #positionComponent(component: string[], adjacency: Map<string, Set<string>>, byId: Map<string, KnowledgeGraphNode>, offsetX: number, offsetY: number, footprints: Map<string, KnowledgeNodeFootprint>): void {
        const rootId = [...component].sort((left, right) => (adjacency.get(right)?.size || 0) - (adjacency.get(left)?.size || 0))[0];
        if (!rootId) return;
        const levels = this.#neighborLevels(rootId, adjacency);
        let previousRight: number | null = null;
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
    #neighborLevels(rootId: string, adjacency: Map<string, Set<string>>): Map<number, string[]> {
        const levels = new Map<number, string[]>();
        const visited = new Set<string>([rootId]);
        const queue: KnowledgeTraversalQueueEntry[] = [{ id: rootId, depth: 0 }];
        while (queue.length) {
            const current = queue.shift();
            if (!current) continue;
            if (!levels.has(current.depth)) {
                levels.set(current.depth, []);
            }
            levels.get(current.depth)?.push(current.id);
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
     * @param {Map<string, KnowledgeNodeFootprint>} footprints The footprints value used by this operation.
     */
    #layoutDomainGrid(nodes: KnowledgeGraphNode[], startY: number, footprints: Map<string, KnowledgeNodeFootprint>): void {
        const groups = new Map<string, KnowledgeGraphNode[]>();
        nodes.forEach(node => {
            if (!groups.has(node.domain)) {
                groups.set(node.domain, []);
            }
            groups.get(node.domain)?.push(node);
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
}
