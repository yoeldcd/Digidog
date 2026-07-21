/**
 * Projects Backlog tasks into domain trees and filtered task collections.
 *
 * This module contains no DOM, API, or lifecycle behavior. Each projector instance
 * represents one immutable UI-filter snapshot supplied by the Backlog component.
 *
 * @module presentation/backlog/projectors/backlog-task-projector
 */

import type { BacklogTask } from "../../../application/backlog/dtos/responses/backlog-response.ts";
import type { BacklogDomainTreeNode } from "../view_models/backlog-view-model.ts";
import type { BacklogPipTaskViewModel } from "../view_models/backlog-pip-view-model.ts";

/**
 * Complete state needed to derive the visible Backlog presentation.
 */
export interface BacklogTaskProjectionInput {
    /**
     * Tasks returned by the Backlog endpoint.
     * @type {readonly BacklogPipTaskViewModel[]}
     */
    tasks: readonly BacklogPipTaskViewModel[];
    /**
     * Selected domain subtree, or an empty string for every domain.
     * @type {string}
     */
    selectedDomain: string;
    /**
     * Free-text query matched against identity and descriptive fields.
     * @type {string}
     */
    filter: string;
    /**
     * Allowed task statuses; an empty set means every status.
     * @type {ReadonlySet<"TODO" | "WORKING" | "DONE">}
     */
    statusFilter: ReadonlySet<BacklogTask["status"]>;
    /**
     * Allowed task priorities; an empty set means every priority.
     * @type {ReadonlySet<"HIGH" | "MEDIUM" | "LOW">}
     */
    priorityFilter: ReadonlySet<BacklogTask["priority"]>;
}

/**
 * Derives domain and filter projections from one Backlog state snapshot.
 */
export class BacklogTaskProjector {
    /**
     * Immutable projection context supplied by the component.
     * @type {BacklogTaskProjectionInput}
     */
    readonly #input: BacklogTaskProjectionInput;
    /**
     * Lower-cased, trimmed text filter reused by every task query.
     * @type {string}
     */
    readonly #needle: string;

    /**
     * Create a projector for one component-state snapshot.
     *
     * @param {BacklogTaskProjectionInput} input Tasks, selection, and active filter sets used by all queries.
     */
    constructor(input: BacklogTaskProjectionInput) {
        this.#input = input;
        this.#needle = input.filter.trim().toLowerCase();
    }

    /**
     * @returns {BacklogPipTaskViewModel[]} Tasks owned by the selected domain or any of its descendants.
     */
    domainTasks(): BacklogPipTaskViewModel[] {
        const domain = this.#input.selectedDomain;
        return this.#input.tasks.filter(task =>
            !domain || task.domain === domain || task.domain.startsWith(`${domain}.`));
    }

    /**
     * Return domain-scoped tasks satisfying text, status, and priority filters.
     *
     * @returns {BacklogPipTaskViewModel[]} New array in the same stable order as the endpoint response.
     */
    visibleTasks(): BacklogPipTaskViewModel[] {
        return this.domainTasks()
            .filter(task => !this.#needle
                || `${task.domain} ${task.title} ${task.description} ${task.id}`.toLowerCase().includes(this.#needle))
            .filter(task => this.matchesActiveFilters(task));
    }

    /**
     * @returns {number} Number of selected status and priority filter values.
     */
    activeFilterCount(): number {
        return this.#input.statusFilter.size + this.#input.priorityFilter.size;
    }

    /**
     * Build a hierarchy containing every unique task domain.
     *
     * @returns {BacklogDomainTreeNode} Synthetic root whose descendants represent dot-delimited segments.
     */
    buildTree(): BacklogDomainTreeNode {
        const root: BacklogDomainTreeNode = { label: "", path: "", children: new Map() };
        for (const domain of this.domains()) {
            const parts = domain.split(".").filter(Boolean);
            let current = root;
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                let child = current.children.get(part);
                if (!child) {
                    child = { label: part, path, children: new Map() };
                    current.children.set(part, child);
                }
                current = child;
            });
        }
        return root;
    }

    /**
     * @returns {string[]} Sorted unique non-empty task domain paths.
     */
    domains(): string[] {
        return [...new Set(this.#input.tasks.map(task => task.domain).filter(Boolean))].sort();
    }

    /**
     * Determine whether a domain node owns any task accepted by active closed filters.
     *
     * @param {BacklogDomainTreeNode} node Candidate domain-tree node.
     * @returns {boolean} True when the branch should remain in the filtered tree.
     */
    matchesNode(node: BacklogDomainTreeNode): boolean {
        return this.#input.tasks.some(task =>
            (task.domain === node.path || task.domain.startsWith(`${node.path}.`))
            && this.matchesActiveFilters(task));
    }

    /**
     * Determine whether a task satisfies selected status and priority values.
     *
     * @param {BacklogPipTaskViewModel} task Candidate task from the Backlog endpoint.
     * @returns {boolean} True when both closed filter dimensions accept the task.
     */
    matchesActiveFilters(task: BacklogPipTaskViewModel): boolean {
        const matchesStatus = !this.#input.statusFilter.size || this.#input.statusFilter.has(task.status);
        const matchesPriority = !this.#input.priorityFilter.size || this.#input.priorityFilter.has(task.priority);
        return matchesStatus && matchesPriority;
    }

    /**
     * Return every non-terminal ancestor of a dot-delimited domain.
     *
     * @param {string} domain Selected domain whose parent branches must be expanded.
     * @returns {string[]} Ancestor paths ordered from the root toward the immediate parent.
     */
    ancestorPaths(domain: string): string[] {
        const parts = domain.split(".");
        return parts.slice(1).map((_part, index) => parts.slice(0, index + 1).join("."));
    }
}
