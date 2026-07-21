/**
 * Builds and queries the presentation tree derived from dot-notated memory paths.
 *
 * The projector contains no DOM or API behavior. A new instance represents one
 * immutable path/filter snapshot and can therefore be used safely throughout a
 * single component render or interaction.
 *
 * @module presentation/memory/projectors/memory-tree-projector
 */

import type { MemoryNode } from "../view_models/memory-view-model.ts";

/**
 * Provides deterministic tree construction, filtering, and leaf queries for Memory.
 */
export class MemoryTreeProjector {
    /**
     * Memory paths included in this immutable projection snapshot.
     * @type {readonly string[]}
     */
    readonly #paths: readonly string[];
    /**
     * Normalized, case-insensitive substring used by visibility queries.
     * @type {string}
     */
    readonly #filterNeedle: string;

    /**
     * Create one projector for the current Memory response and text filter.
     *
     * @param {readonly string[]} paths Dot-notated memory paths returned by the application facade.
     * @param {string} filter User-entered filter text; surrounding whitespace is ignored.
     */
    constructor(paths: readonly string[], filter = "") {
        this.#paths = paths;
        this.#filterNeedle = filter.trim().toLowerCase();
    }

    /**
     * Build a new hierarchical tree from this projector's path snapshot.
     *
     * @returns {MemoryNode} Synthetic root whose children contain every normalized path segment.
     */
    buildTree(): MemoryNode {
        const root: MemoryNode = { label: "", path: "", children: new Map<string, MemoryNode>() };
        for (const path of this.#paths) {
            const parts = String(path).split(".").filter(Boolean);
            let current = root;
            parts.forEach((part, index) => {
                const nodePath = parts.slice(0, index + 1).join(".");
                let child = current.children.get(part);
                if (!child) {
                    child = { label: part, path: nodePath, children: new Map<string, MemoryNode>() };
                    current.children.set(part, child);
                }
                current = child;
            });
        }
        return root;
    }

    /**
     * Return visible direct children of a selected domain in branch-first order.
     *
     * @param {string} selectedDomain Dot-notated branch path, or an empty string for root.
     * @returns {MemoryNode[]} New array containing matching direct descendants.
     */
    childItems(selectedDomain: string): MemoryNode[] {
        const tree = this.buildTree();
        const parent = this.findNode(tree, selectedDomain) ?? tree;
        return Array.from(parent.children.values())
            .filter(item => this.matchesFilter(item) || this.containsFilter(item))
            .sort((left, right) => this.compareNodes(left, right));
    }

    /**
     * Find a node by its complete dot-notated identity.
     *
     * @param {MemoryNode} root Tree root from which traversal begins.
     * @param {string} path Dot-notated identity to resolve.
     * @returns {MemoryNode | null} Matching node, the supplied root for an empty path, or null when absent.
     */
    findNode(root: MemoryNode, path: string): MemoryNode | null {
        if (!path) return root;
        let current: MemoryNode | undefined = root;
        for (const part of path.split(".")) {
            current = current?.children.get(part);
            if (!current) return null;
        }
        return current;
    }

    /**
     * @returns {string[]} Unique top-level domain names in source order.
     */
    topDomains(): string[] {
        return [...new Set(this.#paths.map(path => path.split(".")[0]).filter((part): part is string => Boolean(part)))];
    }

    /**
     * @returns {string[]} Terminal entry paths, excluding root-only domain declarations.
     */
    leafPaths(): string[] {
        return this.#paths.filter(path => !this.hasChildren(path) && path.includes("."));
    }

    /**
     * Return terminal paths owned by a branch.
     *
     * @param {string} prefix Branch path whose descendants should be included.
     * @returns {string[]} Terminal paths equal to or nested beneath `prefix`.
     */
    leafPathsUnder(prefix: string): string[] {
        return this.leafPaths().filter(path => path === prefix || path.startsWith(`${prefix}.`));
    }

    /**
     * Determine whether another known path is nested beneath a candidate.
     *
     * @param {string} path Candidate branch identity.
     * @returns {boolean} True when at least one distinct descendant path exists.
     */
    hasChildren(path: string): boolean {
        return this.#paths.some(candidate => candidate !== path && candidate.startsWith(`${path}.`));
    }

    /**
     * Resolve the parent of a dot-notated path.
     *
     * @param {string} path Path whose final segment should be removed.
     * @returns {string} Parent path, or an empty string for a top-level value.
     */
    parentPath(path: string): string {
        const parts = String(path || "").split(".");
        parts.pop();
        return parts.join(".");
    }

    /**
     * Determine whether a node itself satisfies the normalized text filter.
     *
     * @param {MemoryNode} node Candidate tree node.
     * @returns {boolean} True when no filter is active or the full node path contains it.
     */
    matchesFilter(node: MemoryNode): boolean {
        return !this.#filterNeedle || node.path.toLowerCase().includes(this.#filterNeedle);
    }

    /**
     * Determine whether a node or any descendant satisfies the text filter.
     *
     * @param {MemoryNode} node Branch from which recursive visibility is evaluated.
     * @returns {boolean} True when the branch must remain visible to expose a match.
     */
    containsFilter(node: MemoryNode): boolean {
        return this.matchesFilter(node)
            || Array.from(node.children.values()).some(child => this.containsFilter(child));
    }

    /**
     * Compare nodes with branches before leaves and labels in locale order.
     *
     * @param {MemoryNode} left First node in the sort comparison.
     * @param {MemoryNode} right Second node in the sort comparison.
     * @returns {number} Negative, zero, or positive value compatible with `Array.sort`.
     */
    compareNodes(left: MemoryNode, right: MemoryNode): number {
        const branchDelta = Number(right.children.size > 0) - Number(left.children.size > 0);
        return branchDelta || left.label.localeCompare(right.label);
    }
}
