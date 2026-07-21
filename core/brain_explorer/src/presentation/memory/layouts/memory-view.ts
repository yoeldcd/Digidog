/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { compactLabel, escapeHtml, renderMarkdown } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import { StructureTree } from "../../shared/components/structure-tree.ts";
import { treeActionDetail, treeSearchDetail, treeSelectDetail } from "../../shared/view_models/structure-tree-view-model.ts";
import type { StructureTreeNode, TreeActionDetail, TreeSelectDetail } from "../../shared/view_models/structure-tree-view-model.ts";
import type { BrainApiClient } from "../../../infrastructure/shared/http/clients/brain-api-client.ts";
import type { AppState } from "../../shell/state/app-state.ts";
import type { ComponentContext } from "../../shared/view_models/component-context-view-model.ts";
import { memoryTarget, type MemoryMode, type MemoryNode, type MemoryTarget } from "../view_models/memory-view-model.ts";
import { MemoryTreeProjector } from "../projectors/memory-tree-projector.ts";
import { renderMemoryLoadingState } from "../renderers/memory-state-renderer.ts";

void StructureTree;

/**
 * MemoryView renders the memory store as a collapsible tree and one focused work area.
 */
export class MemoryView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the memory view component in the DOM.
     * @returns {string} The string identifier 'brain-memory-view'.
     */
    static get selector() {
        return "brain-memory-view";
    }

    /**
     * Holds a reference to the BrainApiClient for performing API operations within the MemoryView component.
     *
     * @type {BrainApiClient}
     */
    #api!: BrainApiClient;
    /**
     * Holds the application state instance used by the MemoryView component.
     *
     * @type {AppState}
     */
    #state!: AppState;
    /**
     * Maintains a private collection of string identifiers representing the active memory paths within the view.
     *
     * @type {string[]}
     */
    #paths: string[] = [];
    /**
     * Stores the current navigation path of the selected memory element as a private string.
     *
     * @type {string}
     */
    #selectedPath = "";
    /**
     * Stores the identifier of the currently active memory domain within the view.
     *
     * @type {string}
     */
    #selectedDomain = "";
    /**
     * Stores the internal text content of the memory view as a private string.
     *
     * @type {string}
     */
    #content = "";
    /**
     * Maintains the internal state of the memory view's current operational status message.
     *
     * @type {string}
     */
    #status = "Preparing memory...";
    /**
     * Stores the current text filter used to narrow the displayed memory entries.
     *
     * @type {string}
     */
    #filter = "";
    /**
     * Maintains the current operational state of the memory view, defaulting to browse mode.
     *
     * @type {MemoryMode}
     */
    #mode: MemoryMode = "browse";
    /**
     * Tracks whether the memory tree structure is currently being loaded.
     *
     * @type {boolean}
     */
    #loadingTree = false;
    /**
     * Tracks the loading state of a memory entry within the MemoryView component.
     *
     * @type {boolean}
     */
    #loadingEntry = false;
    /**
     * Tracks the unique identifiers of memory nodes currently in an expanded state within the view.
     *
     * @type {Set<string>}
     */
    #expandedNodes = new Set<string>();
    /**
     * Tracks a MemoryTarget that is awaiting a transition or operation within the MemoryView.
     *
     * @type {MemoryTarget | null}
     */
    #pendingTarget: MemoryTarget | null = null;

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context: ComponentContext) {
        this.#api = context.api;
        this.#state = context.state;
        this.#pendingTarget = memoryTarget(this.#state.consumeRouteTarget("memory")) || this.#pendingTarget;
        this.#loadTree();
    }

    /**
     * Initialize component DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
    }

    /**
     * Load memory paths through the local CLI facade.
     *
     * @param {boolean} forceRefresh Whether to bypass API cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadTree(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        this.#loadingTree = true;
        this.#render();
        const result = await this.#api.memoryTree({ forceRefresh });
        this.#state?.setLastResult(result);
        this.#paths = Array.isArray(result.data) ? result.data : [];
        this.#selectedDomain = this.#selectedDomain || this.#treeProjector().topDomains()[0] || "";
        if (this.#selectedDomain) {
            this.#expandedNodes.add(this.#selectedDomain);
        }
        this.#status = result.ok ? `${this.#treeProjector().leafPaths().length} entries` : result.stderr || result.error || "Could not load memory.";
        this.#loadingTree = false;
        if (await this.#applyPendingTarget(forceRefresh)) {
            return;
        }
        this.#render();
    }

    /**
     * Apply one pending SPA navigation target after the tree is available.
     *
     * @param {boolean} forceRefresh Whether to bypass API cache when reading the target.
     * @returns {Promise<boolean>} True when a route target was consumed.
     */
    async #applyPendingTarget(forceRefresh = false) {
        const target = this.#pendingTarget || memoryTarget(this.#state.consumeRouteTarget("memory"));
        this.#pendingTarget = null;
        if (!target) {
            return false;
        }
        if (target.path) {
            await this.#loadEntry(target.path, target.mode || "read", forceRefresh);
            return true;
        }
        if (target.domain) {
            this.#selectedDomain = target.domain;
            this.#selectedPath = "";
            this.#expandAncestors(target.domain);
            this.#mode = target.mode || "browse";
            this.#render();
            return true;
        }
        return false;
    }

    /**
     * Load one memory entry.
     *
     * @param {string} path Dot-notated memory path.
     * @param {string} mode Target mode.
     * @param {boolean} forceRefresh Whether to bypass API cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadEntry(path: string, mode: MemoryMode = "read", forceRefresh = false): Promise<void> {
        this.#selectedPath = path;
        this.#selectedDomain = this.#treeProjector().parentPath(path) || path.split(".")[0] || this.#selectedDomain;
        this.#expandAncestors(path);
        this.#mode = mode;
        this.#loadingEntry = true;
        this.#status = compactLabel(path);
        this.#render();
        const result = await this.#api.memoryEntry(path, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#content = result.data?.content || result.stdout || "";
        this.#status = result.ok ? compactLabel(path) : result.stderr || result.error || "Could not read the entry.";
        this.#loadingEntry = false;
        this.#render();
    }

    /**
     * Prepare a new entry in edit mode under the selected domain.
     *
     * @returns {void}
     */
    #newEntry() {
        const baseDomain = this.#selectedDomain || this.#treeProjector().topDomains()[0] || "notes";
        this.#selectedPath = `${baseDomain}.new_entry`;
        this.#content = "# New entry\n\nWrite Markdown memory here.";
        this.#mode = "edit";
        this.#status = "New entry";
        this.#render();
    }

    /**
     * Save editor content to memory.
     *
     * @returns {Promise<void>} Resolves after save.
     */
    async #saveEntry() {
        const path = this.querySelector<HTMLInputElement>("[data-role='memory-path']")?.value.trim();
        const content = this.querySelector<HTMLTextAreaElement>("[data-role='memory-content']")?.value || this.#content;
        if (!path) {
            this.#status = "Define a path before saving.";
            this.#render();
            return;
        }
        this.#render();
        const result = await this.#api.saveMemoryEntry(path, content);
        this.#state?.setLastResult(result);
        this.#selectedPath = path;
        this.#selectedDomain = this.#treeProjector().parentPath(path) || path.split(".")[0] || "";
        this.#content = content;
        this.#status = result.ok ? compactLabel(path) : result.stderr || result.error || "Could not save.";
        await this.#loadTree(true);
        this.#mode = "read";
        this.#render();
    }

    /**
     * Duplicate selected entry under a new path.
     *
     * @returns {Promise<void>} Resolves after duplication.
     */
    async #duplicateEntry() {
        if (!this.#selectedPath) {
            return;
        }
        const nextPath = `${this.#selectedPath}_copy`;
        const result = await this.#api.saveMemoryEntry(nextPath, this.#content);
        this.#state?.setLastResult(result);
        if (result.ok) {
            await this.#loadTree(true);
            await this.#loadEntry(nextPath, "edit", true);
        }
    }

    /**
     * Delete selected entry.
     *
     * @returns {Promise<void>} Resolves after deletion.
     */
    async #deleteEntry() {
        if (!this.#selectedPath) {
            return;
        }
        const result = await this.#api.deleteMemoryEntry(this.#selectedPath);
        this.#state?.setLastResult(result);
        this.#selectedPath = "";
        this.#content = "";
        this.#mode = "browse";
        this.#status = result.ok ? "Entry deleted" : result.stderr || result.error || "Could not delete.";
        await this.#loadTree(true);
    }

    /**
     * Create a memory domain.
     *
     * @returns {Promise<void>} Resolves after creation.
     */
    async #createDomain() {
        const domain = this.querySelector<HTMLInputElement>("[data-role='domain-name']")?.value.trim();
        if (!domain) {
            this.#status = "Enter a domain.";
            this.#render();
            return;
        }
        const result = await this.#api.createMemoryDomain(domain);
        this.#state?.setLastResult(result);
        this.#selectedDomain = domain;
        this.#selectedPath = "";
        this.#expandedNodes.add(domain.split(".")[0] ?? domain);
        this.#status = result.ok ? `Domain ${domain}` : result.stderr || result.error || "Could not create domain.";
        await this.#loadTree(true);
    }

    /**
     * Delete selected domain.
     *
     * @returns {Promise<void>} Resolves after deletion.
     */
    async #deleteDomain() {
        const domain = this.querySelector<HTMLInputElement>("[data-role='domain-name']")?.value.trim() || this.#selectedDomain;
        if (!domain) {
            return;
        }
        const result = await this.#api.deleteMemoryDomain(domain);
        this.#state?.setLastResult(result);
        this.#selectedDomain = "";
        this.#selectedPath = "";
        this.#content = "";
        this.#mode = "browse";
        this.#status = result.ok ? "Domain deleted" : result.stderr || result.error || "Could not delete domain.";
        await this.#loadTree(true);
    }

    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface memory-console">
                <div class="structure-layout memory-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.#renderTree()}
                        </div>
                    </aside>
                    <main class="structure-content">
                        ${this.#renderContent()}
                    </main>
                </div>
            </section>
        `;
        this.#bindEvents();
        this.#configureTree();
    }

    /**
     * Render the active content area.
     *
     * @returns {string} HTML.
     */
    #renderContent() {
        if (this.#mode === "read") {
            return this.#renderReadContent();
        }
        if (this.#mode === "edit") {
            return this.#renderEditContent();
        }
        if (this.#mode === "domains") {
            return this.#renderDomainsContent();
        }
        return this.#renderBrowseContent();
    }

    /**
     * Render selected domain children.
     *
     * @returns {string} HTML.
     */
    #renderBrowseContent() {
        const children = this.#treeProjector().childItems(this.#selectedDomain);
        return `
            <div class="content-head">
                <strong>${escapeHtml(this.#selectedDomain || "Memory")}</strong>
                <span>${escapeHtml(String(children.length))} visible</span>
            </div>
            <div class="entry-list scroll-list">
                ${children.length ? children.map(item => this.#renderContentItem(item)).join("") : `<p class="empty-state">Select a tree node.</p>`}
            </div>
        `;
    }

    /**
     * Render one child row in the content area.
     *
     * @param {object} item Tree item.
     * @returns {string} HTML.
     */
    #renderContentItem(item: MemoryNode): string {
        const isBranch = item.children.size > 0;
        const action = isBranch ? "select-domain" : "select-entry";
        const count = isBranch ? `${this.#treeProjector().leafPathsUnder(item.path).length} entries` : "Entry";
        return `
            <button class="entry-row ${item.path === this.#selectedPath ? "is-active" : ""}" data-action="${action}" data-node-path="${escapeHtml(item.path)}">
                ${icon(isBranch ? "folder" : "document")}
                <span>
                    <strong>${escapeHtml(item.label)}</strong>
                    <small>${escapeHtml(count)}</small>
                </span>
            </button>
        `;
    }

    /**
     * Render markdown reading mode.
     *
     * @returns {string} HTML.
     */
    #renderReadContent() {
        return `
            <div class="content-head">
                <strong>${escapeHtml(compactLabel(this.#selectedPath) || "No entry")}</strong>
                <span>${escapeHtml(this.#selectedPath || this.#status)}</span>
            </div>
            <article class="markdown-preview scroll-area">
                ${this.#loadingEntry ? renderMemoryLoadingState("Rendering Markdown") : renderMarkdown(this.#content || "Select an entry.")}
            </article>
        `;
    }

    /**
     * Render entry editor mode.
     *
     * @returns {string} HTML.
     */
    #renderEditContent() {
        return `
            <div class="content-head editor-path-row">
                <label class="path-compact">
                    <span>Path</span>
                    <input data-role="memory-path" value="${escapeHtml(this.#selectedPath)}" placeholder="domain.entry">
                </label>
            </div>
            <textarea class="markdown-editor scroll-area" data-role="memory-content" spellcheck="false">${escapeHtml(this.#content)}</textarea>
        `;
    }

    /**
     * Render domain management mode.
     *
     * @returns {string} HTML.
     */
    #renderDomainsContent() {
        return `
            <div class="content-head editor-path-row">
                <label class="path-compact">
                    <span>Domain</span>
                    <input data-role="domain-name" value="${escapeHtml(this.#selectedDomain)}" placeholder="new.domain">
                </label>
            </div>
            <div class="domain-grid scroll-list">
                ${this.#treeProjector().topDomains().map(domain => `
                    <button class="domain-tile ${domain === this.#selectedDomain ? "is-active" : ""}" data-action="select-domain" data-node-path="${escapeHtml(domain)}">
                        ${icon("database")}
                        <strong>${escapeHtml(domain)}</strong>
                        <span>${escapeHtml(String(this.#treeProjector().leafPathsUnder(domain).length))} entries</span>
                    </button>
                `).join("") || `<p class="empty-state">No domains.</p>`}
            </div>
        `;
    }

    /**
     * Render the collapsible memory tree.
     *
     * @returns {string} HTML.
     */
    #renderTree() {
        return `<brain-structure-tree data-role="memory-tree"></brain-structure-tree>`;
    }

    /**
     * Render one tree node.
     *
     * @param {object} node Tree node.
     * @param {number} depth Tree depth.
     * @returns {string} HTML.
     */
    #renderTreeNode(node: MemoryNode, depth: number): string {
        const hasChildren = node.children.size > 0;
        const isOpen = this.#expandedNodes.has(node.path);
        const isActive = node.path === this.#selectedDomain || node.path === this.#selectedPath;
        const projector = this.#treeProjector();
        const children = Array.from(node.children.values()).sort((left, right) => projector.compareNodes(left, right));
        const isVisible = projector.matchesFilter(node) || children.some(child => projector.containsFilter(child));
        if (!isVisible) {
            return "";
        }
        return `
            <div class="tree-node-wrap">
                <button class="tree-node ${isActive ? "is-active" : ""}" style="--tree-depth:${depth}" data-node-path="${escapeHtml(node.path)}" data-node-branch="${hasChildren ? "true" : "false"}">
                    <span class="tree-caret">${hasChildren ? icon(isOpen ? "chevronDown" : "chevronRight") : ""}</span>
                    ${icon(hasChildren ? "folder" : "document")}
                    <span>${escapeHtml(node.label)}</span>
                    ${hasChildren ? `<small>${escapeHtml(String(projector.leafPathsUnder(node.path).length))}</small>` : ""}
                </button>
                ${hasChildren && isOpen ? `<div class="tree-children">${children.map(child => this.#renderTreeNode(child, depth + 1)).join("")}</div>` : ""}
            </div>
        `;
    }

    /**
     * Configure the shared structural tree with Memory-specific actions.
     *
     * @returns {void}
     */
    #configureTree() {
        const treeElement = this.querySelector("[data-role='memory-tree']");
        if (!(treeElement instanceof StructureTree)) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#selectedPath || this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
            toggleOnBranchSelect: true,
            title: "Memory",
            toolbarActions: [
                { id: "new-entry", label: "New entry", icon: "plus" },
                { id: "create-domain", label: "New domain", icon: "folder" },
                { id: "refresh", label: "Refresh tree", icon: "refresh" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "database",
            searchQuery: this.#filter,
            emptyText: this.#loadingTree ? "Loading tree..." : "No paths loaded."
        };
        treeElement.addEventListener("brain-tree-select", event => {
            const detail = event instanceof CustomEvent ? treeSelectDetail(event.detail) : null;
            if (detail) this.#onTreeSelected(detail);
        });
        treeElement.addEventListener("brain-tree-toolbar-action", event => {
            const detail = event instanceof CustomEvent ? treeActionDetail(event.detail) : null;
            if (detail) this.#onTreeToolbarAction(detail);
        });
        treeElement.addEventListener("brain-tree-action", event => {
            const detail = event instanceof CustomEvent ? treeActionDetail(event.detail) : null;
            if (detail) this.#onTreeAction(detail);
        });
        treeElement.addEventListener("brain-tree-search", event => {
            const detail = event instanceof CustomEvent ? treeSearchDetail(event.detail) : null;
            if (!detail) return;
            this.#filter = detail.query;
            const mainContent = this.querySelector(".structure-content");
            if (mainContent) {
                mainContent.innerHTML = this.#renderContent();
            }
        });
    }

    /**
     * Convert the in-memory path tree into shared presentation nodes.
     *
     * @returns {object[]} Tree node list.
     */
    #treeNodes(): StructureTreeNode[] {
        const projector = this.#treeProjector();
        const toNode = (node: MemoryNode): StructureTreeNode => {
            const children: StructureTreeNode[] = Array.from(node.children.values())
                .filter(child => projector.matchesFilter(child) || projector.containsFilter(child))
                .sort((left, right) => projector.compareNodes(left, right))
                .map(toNode);
            const hasChildren = children.length > 0;
            return {
                id: node.path,
                path: node.path,
                label: node.label,
                ...(hasChildren ? { count: projector.leafPathsUnder(node.path).length } : {}),
                children,
                actions: hasChildren
                    ? [
                        { id: "new-entry", label: "New entry", icon: "plus" },
                        { id: "delete-domain", label: "Delete domain", icon: "trash", danger: true }
                    ]
                    : [
                        { id: "open-entry", label: "Open", icon: "document" },
                        { id: "edit-entry", label: "Edit", icon: "edit" },
                        { id: "duplicate-entry", label: "Duplicar", icon: "copy" },
                        { id: "delete-entry", label: "Delete", icon: "trash", danger: true }
                    ]
            };
        };
        return Array.from(projector.buildTree().children.values())
            .filter(node => projector.matchesFilter(node) || projector.containsFilter(node))
            .sort((left, right) => projector.compareNodes(left, right))
            .map(toNode);
    }

    /**
     * React to a shared tree selection.
     *
     * @param {TreeSelectDetail} detail Validated selection detail emitted by the shared tree.
     * @returns {void}
     */
    #onTreeSelected(detail: TreeSelectDetail): void {
        const { path, branch, clickedCaret } = detail;
        if (branch) {
            if (clickedCaret) {
                return;
            }
            this.#selectedDomain = path;
            this.#selectedPath = "";
            this.#mode = this.#mode === "edit" ? "browse" : this.#mode;
            this.#render();
            return;
        }
        this.#loadEntry(path, "read");
    }

    /**
     * Execute a global Memory tree toolbar action.
     *
     * @param {TreeActionDetail} detail Validated toolbar-action detail emitted by the shared tree.
     * @returns {void}
     */
    #onTreeToolbarAction(detail: TreeActionDetail): void {
        const action = detail.action;
        if (action === "new-entry") {
            this.#newEntry();
        } else if (action === "create-domain") {
            this.#mode = "domains";
            this.#render();
        } else if (action === "refresh") {
            this.#loadTree(true);
        }
    }

    /**
     * Execute a contextual Memory item action.
     *
     * @param {TreeActionDetail} detail Validated contextual-action detail emitted by the shared tree.
     * @returns {void}
     */
    #onTreeAction(detail: TreeActionDetail): void {
        const { action, node } = detail;
        if (!node) {
            return;
        }
        if (action === "new-entry") {
            this.#selectedDomain = node.path;
            this.#newEntry();
        } else if (action === "delete-domain") {
            this.#selectedDomain = node.path;
            this.#deleteDomain();
        } else if (action === "open-entry") {
            this.#loadEntry(node.path, "read");
        } else if (action === "edit-entry") {
            this.#loadEntry(node.path, "edit");
        } else if (action === "duplicate-entry") {
            this.#selectedPath = node.path;
            this.#duplicateEntry();
        } else if (action === "delete-entry") {
            this.#selectedPath = node.path;
            this.#deleteEntry();
        }
    }

    /**
     * Create the pure tree projector for the component's current path and filter snapshot.
     *
     * @returns {MemoryTreeProjector} A stateless query object whose lifetime is limited to the calling operation.
     */
    #treeProjector(): MemoryTreeProjector {
        return new MemoryTreeProjector(this.#paths, this.#filter);
    }

    /**
     * Expand ancestors for a selected path.
     *
     * @param {string} path Dot-notated path.
     * @returns {void}
     */
    #expandAncestors(path: string): void {
        const parts = String(path || "").split(".");
        for (let index = 1; index < parts.length; index += 1) {
            this.#expandedNodes.add(parts.slice(0, index).join("."));
        }
    }

    /**
     * Bind DOM events after render.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelectorAll("[data-action='set-memory-mode']").forEach(button => button.addEventListener("click", () => {
            const mode = button.getAttribute("data-memory-mode");
            if (mode === "browse" || mode === "read" || mode === "edit" || mode === "domains") this.#mode = mode;
            this.#render();
        }));
        this.querySelector("[data-action='refresh-memory']")?.addEventListener("click", () => this.#loadTree(true));
        this.querySelectorAll("[data-action='new-entry']").forEach(button => button.addEventListener("click", () => this.#newEntry()));
        this.querySelector("[data-action='domain-mode']")?.addEventListener("click", () => {
            this.#mode = "domains";
            this.#render();
        });
        this.querySelector("[data-action='edit-entry']")?.addEventListener("click", () => {
            this.#mode = "edit";
            this.#render();
        });
        this.querySelector("[data-action='save-entry']")?.addEventListener("click", () => this.#saveEntry());
        this.querySelector("[data-action='duplicate-entry']")?.addEventListener("click", () => this.#duplicateEntry());
        this.querySelector("[data-action='delete-entry']")?.addEventListener("click", () => this.#deleteEntry());
        this.querySelector("[data-action='delete-domain']")?.addEventListener("click", () => this.#deleteDomain());
        this.querySelector("[data-action='create-domain']")?.addEventListener("click", () => this.#createDomain());
        this.querySelectorAll("[data-node-path]").forEach(item => item.addEventListener("click", () => {
            const path = item.getAttribute("data-node-path") || "";
            const isBranch = item.getAttribute("data-node-branch") === "true" || this.#treeProjector().hasChildren(path);
            if (isBranch) {
                this.#selectedDomain = path;
                this.#selectedPath = "";
                this.#mode = this.#mode === "edit" ? "browse" : this.#mode;
                if (this.#expandedNodes.has(path)) {
                    this.#expandedNodes.delete(path);
                } else {
                    this.#expandedNodes.add(path);
                }
                this.#render();
                return;
            }
            this.#loadEntry(path, "read");
        }));
    }
}

customElements.define(MemoryView.selector, MemoryView);
