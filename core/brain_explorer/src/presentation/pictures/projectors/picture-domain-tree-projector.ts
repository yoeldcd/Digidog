/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import type { PictureRecord } from "../../../application/pictures/dtos/responses/pictures-response.ts";
import type { StructureTreeNode } from "../../shared/view_models/structure-tree-view-model.ts";

/**
 * Mutable internal node used only while accumulating a dotted domain hierarchy.
 * This shape is deliberately private to the projector so presentation components
 * consume the stable shared-tree contract rather than an intermediate structure.
 */
interface PictureDomainAccumulator {
    /**
     * Human-readable segment represented by this hierarchy level.
     * @type {string}
     */
    label: string;
    /**
     * Canonical dotted path from the root through this segment.
     * @type {string}
     */
    path: string;
    /**
     * Number of pictures assigned directly to this exact domain.
     * @type {number}
     */
    ownCount: number;
    /**
     * Child accumulators indexed by their local segment label.
     * @type {Map<string, PictureDomainAccumulator>}
     */
    children: Map<string, PictureDomainAccumulator>;
}

/**
 * Projects flat picture-domain counts into the recursive tree contract shared by
 * Explorer layouts. Projection is deterministic and does not mutate its input.
 */
export class PictureDomainTreeProjector {
    /**
     * Immutable mapping from canonical dotted domains to direct picture counts.
     * @type {Readonly<Record<string, number>>}
     */
    readonly #domainCounts: Readonly<Record<string, number>>;
    /** Pictures loaded for a domain and exposed as actionable leaf nodes. */
    readonly #picturesByDomain: ReadonlyMap<string, readonly PictureRecord[]>;

    /**
     * Create a projector for one picture registry snapshot.
     *
     * @param {Readonly<Record<string, number>>} domainCounts Canonical domain-to-direct-count mapping from the API.
     * @param {ReadonlyMap<string, readonly PictureRecord[]>} picturesByDomain Hydrated pictures keyed by their direct domain.
     */
    constructor(domainCounts: Readonly<Record<string, number>>, picturesByDomain: ReadonlyMap<string, readonly PictureRecord[]> = new Map()) {
        this.#domainCounts = domainCounts;
        this.#picturesByDomain = picturesByDomain;
    }

    /**
     * Build the single-root recursive structure consumed by `StructureTree`.
     * Parent counts include every descendant while leaf counts remain direct.
     *
     * @returns {StructureTreeNode[]} A tree rooted at the canonical all-pictures node.
     */
    project(): StructureTreeNode[] {
        const root: PictureDomainAccumulator = {
            label: "Todo",
            path: "",
            ownCount: 0,
            children: new Map<string, PictureDomainAccumulator>(),
        };
        Object.entries(this.#domainCounts).forEach(([domain, count]) => {
            let parent = root;
            const parts = domain.split(".").filter(Boolean);
            parts.forEach((label, index) => {
                const path = parts.slice(0, index + 1).join(".");
                let child = parent.children.get(label);
                if (!child) {
                    child = { label, path, ownCount: 0, children: new Map<string, PictureDomainAccumulator>() };
                    parent.children.set(label, child);
                }
                parent = child;
            });
            parent.ownCount += count;
        });
        return [this.#projectNode(root)];
    }

    /**
     * Convert one accumulator and its descendants to the public shared-tree shape.
     *
     * @param {PictureDomainAccumulator} node Accumulator being projected.
     * @returns {StructureTreeNode} Fully projected node with aggregate descendant count.
     */
    #projectNode(node: PictureDomainAccumulator): StructureTreeNode {
        const children = [...node.children.values()].map(child => this.#projectNode(child));
        const pictures = this.#picturesByDomain.get(node.path) || [];
        const pictureNodes: StructureTreeNode[] = pictures.map(picture => ({
            id: `picture:${picture.id}`,
            path: node.path,
            label: picture.filename,
            title: picture.relative_path,
            icon: "camera",
            actions: [{ id: "download-picture", label: "Download", icon: "download" }],
        }));
        const descendantCount = children.reduce((total, child) => total + Number(child.count || 0), 0);
        return {
            id: `pictures:${node.path || "all"}`,
            path: node.path,
            label: node.label,
            icon: "folder",
            count: node.ownCount + descendantCount,
            actions: [{ id: "import-picture", label: "Import", icon: "folderPlus" }],
            children: [...children, ...pictureNodes],
        };
    }
}
