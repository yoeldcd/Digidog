/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";

/**
 * A serializable node rendered by {@link StructureTree}.
 *
 * `path` is the public selection target. `id` can be used when two rendered
 * nodes refer to the same target path, such as a domain and one log entry.
 *
 * @typedef {object} StructureTreeNode
 * @property {string} id Stable rendered node identity.
 * @property {string} path Target path emitted in selection events.
 * @property {string} label Primary node label.
 * @property {string} [icon] SVG registry key.
 * @property {number|string} [count] Optional descendant count.
 * @property {string} [detail] Secondary compact detail.
 * @property {string} [timestamp] Timestamp for terminal log rows.
 * @property {"default"|"log"} [presentation] Node visual treatment.
 * @property {{id: string, label: string, icon?: string, danger?: boolean}[]} [actions] Context actions for this node.
 * @property {StructureTreeNode[]} [children] Descendants.
 */

/**
 * Shared structural tree for Explorer layouts.
 *
 * The element owns only local expand/collapse DOM state. Its consumer owns
 * data loading and reacts to `brain-tree-select` events, preventing a branch
 * gesture from rehydrating the active layout.
 */
export class StructureTree extends HTMLElement {
    static get selector() {
        return "brain-structure-tree";
    }

    #model = {
        nodes: [],
        selectedPath: "",
        expandedPaths: new Set(),
        toggleOnBranchSelect: true,
        title: "",
        toolbarActions: [],
        showSearch: true,
        searchPlaceholder: "Buscar...",
        emptyText: "No hay elementos todavia."
    };

    #openActionNodeId = "";
    #searchQuery = "";
    #disableFilter = false;
    #onDocumentPointerDown = event => this.#closeMenusOutside(event);

    /**
     * Assign the full tree presentation model.
     *
     * @param {{nodes: StructureTreeNode[], selectedPath?: string, expandedPaths?: Set<string>, toggleOnBranchSelect?: boolean, title?: string, toolbarActions?: object[], searchQuery?: string, disableFilter?: boolean, showSearch?: boolean, searchPlaceholder?: string, emptyText?: string}} value Tree model.
     */
    set model(value) {
        this.#model = {
            nodes: Array.isArray(value?.nodes) ? value.nodes : [],
            selectedPath: value?.selectedPath || "",
            expandedPaths: value?.expandedPaths instanceof Set ? value.expandedPaths : new Set(),
            toggleOnBranchSelect: value?.toggleOnBranchSelect !== false,
            title: value?.title || "",
            toolbarActions: Array.isArray(value?.toolbarActions) ? value.toolbarActions : [],
            showSearch: value?.showSearch !== false,
            searchPlaceholder: value?.searchPlaceholder || "Buscar...",
            emptyText: value?.emptyText || "No hay elementos todavia."
        };
        if (typeof value?.searchQuery === "string") {
            this.#searchQuery = value.searchQuery;
        }
        this.#disableFilter = !!value?.disableFilter;
        this.#render();
    }

    /**
     * Render the initial empty element.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
        document.addEventListener("pointerdown", this.#onDocumentPointerDown);
    }

    /**
     * Release the document-level menu listener.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        document.removeEventListener("pointerdown", this.#onDocumentPointerDown);
    }

    #matchesFilter(node) {
        if (this.#disableFilter) return true;
        if (!this.#searchQuery) return true;
        const needle = this.#searchQuery.toLowerCase();
        if ((node.label || "").toLowerCase().includes(needle) || (node.path || "").toLowerCase().includes(needle)) {
            return true;
        }
        if (Array.isArray(node.children)) {
            return node.children.some(child => this.#matchesFilter(child));
        }
        return false;
    }

    #render() {
        const sortedRootNodes = [...this.#model.nodes].sort((left, right) => {
            const leftHas = Array.isArray(left.children) && left.children.length > 0;
            const rightHas = Array.isArray(right.children) && right.children.length > 0;
            if (leftHas !== rightHas) {
                return leftHas ? -1 : 1;
            }
            return (left.label || "").localeCompare(right.label || "");
        });
        const visibleNodes = sortedRootNodes.filter(node => this.#matchesFilter(node));
        this.innerHTML = `
            ${this.#renderToolbar()}
            ${this.#model.showSearch ? `
                <label class="compact-search structure-tree-search">
                    ${icon("search")}
                    <input data-role="tree-filter" value="${escapeHtml(this.#searchQuery)}" placeholder="${escapeHtml(this.#model.searchPlaceholder)}">
                </label>
            ` : ""}
            <div class="structure-tree-nodes" role="tree">
                ${visibleNodes.length
                    ? visibleNodes.map(node => this.#renderNode(node, 1)).join("")
                    : `<p class="structure-tree-empty">${escapeHtml(this.#model.emptyText)}</p>`}
            </div>
        `;
        this.#bindEvents();
    }

    /**
     * Render the optional tree toolbar.
     *
     * @returns {string} Toolbar HTML.
     */
    #renderToolbar() {
        if (!this.#model.title && !this.#model.toolbarActions.length) {
            return "";
        }
        return `
            <header class="structure-tree-toolbar">
                ${this.#model.title ? `<strong>${escapeHtml(this.#model.title)}</strong>` : "<span></span>"}
                <div>
                    ${this.#model.toolbarActions.map(action => `
                        <button class="icon-action" data-tree-toolbar-action="${escapeHtml(action.id)}" title="${escapeHtml(action.label)}" aria-label="${escapeHtml(action.label)}">
                            ${icon(action.icon || "more")}
                        </button>
                    `).join("")}
                </div>
            </header>
        `;
    }

    /**
     * Render one log tree node.
     *
     * @param {object} node Tree node.
     * @param {number} depth Tree depth.
     * @returns {string} Node HTML.
     */
    #renderNode(node, depth) {
        if (!this.#matchesFilter(node)) {
            return "";
        }
        const children = Array.isArray(node.children) ? node.children : [];
        const hasChildren = children.length > 0;
        const expanded = this.#model.expandedPaths.has(node.id || node.path);
        const active = node.path === this.#model.selectedPath;
        const sourceClass = node.color ? "tree-node--source" : "";
        const sourceStyle = node.color ? ` style="--tree-source-color: ${escapeHtml(node.color)};"` : "";

        const defaultBranch = this.#model.defaultBranchIcon || "folder";
        const defaultLeaf = this.#model.defaultLeafIcon || "document";

        if (node.presentation === "log" && !hasChildren) {
            return `
                <div class="tree-node-wrap" role="treeitem" aria-level="${depth}" aria-selected="${active}" style="--depth: ${depth};">
                    <div class="tree-item ${active ? "is-active" : ""}">
                        <button class="tree-node tree-terminal-log tree-node--leaf ${active ? "is-active" : ""}"
                            data-tree-id="${escapeHtml(node.id || node.path)}" data-tree-path="${escapeHtml(node.path)}" data-tree-branch="false"
                            title="${escapeHtml(node.label)}">
                            <span class="tree-node-icon">${icon(node.icon || defaultLeaf)}</span>
                            <time>${escapeHtml(node.timestamp || "Sin fecha")}</time>
                            <strong>${escapeHtml(node.label)}</strong>
                            <small>${escapeHtml(node.detail || "")}</small>
                            ${this.#renderNodeActionTrigger(node)}
                        </button>
                        ${this.#renderNodeActionMenu(node)}
                    </div>
                </div>
            `;
        }

        const sortedChildren = [...children].sort((left, right) => {
            const leftHas = Array.isArray(left.children) && left.children.length > 0;
            const rightHas = Array.isArray(right.children) && right.children.length > 0;
            if (leftHas !== rightHas) {
                return leftHas ? -1 : 1;
            }
            return (left.label || "").localeCompare(right.label || "");
        });

        return `
            <div class="tree-node-wrap" role="treeitem" aria-level="${depth}" ${hasChildren ? `aria-expanded="${expanded}"` : ""} aria-selected="${active}" style="--depth: ${depth};">
                <div class="tree-item ${active ? "is-active" : ""}">
                    <button class="tree-node ${hasChildren ? "" : "tree-node--leaf"} ${sourceClass} ${active ? "is-active" : ""}"${sourceStyle}
                        data-tree-id="${escapeHtml(node.id || node.path)}" data-tree-path="${escapeHtml(node.path)}" data-tree-branch="${hasChildren}"
                        title="${escapeHtml(node.label)}">
                        ${hasChildren ? `<span class="tree-caret">${icon(expanded ? "chevronDown" : "chevronRight")}</span>` : ""}
                        ${icon(node.icon || (hasChildren ? defaultBranch : defaultLeaf))}
                        <span>${escapeHtml(node.label)}</span>
                        ${node.count !== undefined ? `<small>${escapeHtml(String(node.count))}</small>` : ""}
                        ${this.#renderNodeActionTrigger(node)}
                    </button>
                    ${this.#renderNodeActionMenu(node)}
                </div>
                ${hasChildren ? `<div class="tree-children" role="group" ${expanded ? "" : "hidden"}>${sortedChildren.map(child => this.#renderNode(child, depth + 1)).join("")}</div>` : ""}
            </div>
        `;
    }

    /**
     * Render the contextual action trigger inside the actual tree item button.
     *
     * @param {StructureTreeNode} node Tree node.
     * @returns {string} Trigger HTML.
     */
    #renderNodeActionTrigger(node) {
        if (!node.actions?.length) {
            return "";
        }
        const nodeId = escapeHtml(node.id || node.path);
        return `
            <span class="tree-action-trigger" data-tree-actions="${nodeId}" title="Acciones" aria-label="Acciones">
                ${icon("more")}
            </span>
        `;
    }

    /**
     * Render the menu that belongs to an open item action trigger.
     *
     * @param {StructureTreeNode} node Tree node.
     * @returns {string} Action menu HTML.
     */
    #renderNodeActionMenu(node) {
        const nodeId = node.id || node.path;
        if (!node.actions?.length || this.#openActionNodeId !== nodeId) {
            return "";
        }
        return `
            <div class="tree-node-menu action-menu-panel" role="menu">
                ${node.actions.map(action => `
                    <button class="${action.danger ? "danger-button" : ""}" data-tree-action="${escapeHtml(action.id)}" data-tree-action-node="${escapeHtml(nodeId)}">
                        ${icon(action.icon || "more")}${escapeHtml(action.label)}
                    </button>
                `).join("")}
            </div>
        `;
    }

    /**
     * Bind node selection and local expansion handlers.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelectorAll("[data-tree-id]").forEach(button => {
            button.addEventListener("click", event => this.#onNodeClicked(button, event));
        });
        this.querySelectorAll("[data-tree-toolbar-action]").forEach(button => {
            button.addEventListener("click", () => this.#emitToolbarAction(button));
        });
        this.querySelectorAll("[data-tree-actions]").forEach(trigger => {
            trigger.addEventListener("click", event => this.#toggleNodeActionMenu(trigger, event));
        });
        this.querySelectorAll("[data-tree-action]").forEach(button => {
            button.addEventListener("click", () => this.#emitNodeAction(button));
        });

        // Filter Input Event
        const filterInput = this.querySelector("[data-role='tree-filter']");
        filterInput?.addEventListener("input", event => {
            this.#searchQuery = event.target.value;
            
            // Render only nodes container to keep focus and cursor position!
            const sortedRootNodes = [...this.#model.nodes].sort((left, right) => {
                const leftHas = Array.isArray(left.children) && left.children.length > 0;
                const rightHas = Array.isArray(right.children) && right.children.length > 0;
                if (leftHas !== rightHas) {
                    return leftHas ? -1 : 1;
                }
                return (left.label || "").localeCompare(right.label || "");
            });
            
            const nodesContainer = this.querySelector(".structure-tree-nodes");
            if (nodesContainer) {
                nodesContainer.innerHTML = sortedRootNodes.map(node => this.#renderNode(node, 1)).join("");
            }
            
            // Re-bind listeners on new node elements!
            this.querySelectorAll("[data-tree-id]").forEach(button => {
                button.addEventListener("click", ev => this.#onNodeClicked(button, ev));
            });
            this.querySelectorAll("[data-tree-actions]").forEach(trigger => {
                trigger.addEventListener("click", ev => this.#toggleNodeActionMenu(trigger, ev));
            });
            
            // Emit search query event to parent view
            this.dispatchEvent(new CustomEvent("brain-tree-search", {
                bubbles: true,
                detail: { query: this.#searchQuery }
            }));
        });
    }

    /**
     * Handle one structural gesture without fetching or rehydrating the tree.
     *
     * @param {Element} button Trigger button.
     * @param {MouseEvent} event Native click event.
     * @returns {void}
     */
    #onNodeClicked(button, event) {
        if (event.target.closest("[data-tree-actions]")) {
            return;
        }
        const id = button.getAttribute("data-tree-id") || "";
        const path = button.getAttribute("data-tree-path") || "";
        const branch = button.getAttribute("data-tree-branch") === "true";
        const clickedCaret = Boolean(event.target.closest(".tree-caret"));
        const scrollTop = button.closest(".structure-tree-nodes")?.scrollTop || 0;
        let expanded = this.#model.expandedPaths.has(id);
        if (branch && (clickedCaret || this.#model.toggleOnBranchSelect)) {
            expanded = !expanded;
            this.#setExpanded(button, id, expanded);
        }
        const node = this.#findNode(this.#model.nodes, id);
        this.dispatchEvent(new CustomEvent("brain-tree-select", {
            bubbles: true,
            detail: { id, path, branch, expanded, clickedCaret, node }
        }));
        this.#restoreInteractionAnchor(id, scrollTop);
    }

    /**
     * Restore the node that initiated a gesture after a consumer re-renders
     * and replaces the shared tree synchronously.
     *
     * @param {string} id Stable rendered node identity.
     * @param {number} scrollTop Previous tree scroll offset.
     * @returns {void}
     */
    #restoreInteractionAnchor(id, scrollTop) {
        requestAnimationFrame(() => {
            const trees = document.querySelectorAll(StructureTree.selector);
            for (const tree of trees) {
                const button = Array.from(tree.querySelectorAll("[data-tree-id]"))
                    .find(candidate => candidate.getAttribute("data-tree-id") === id);
                if (!button) {
                    continue;
                }
                const container = tree.querySelector(".structure-tree-nodes");
                if (container) {
                    container.scrollTop = scrollTop;
                }
                button.focus({ preventScroll: true });
                return;
            }
        });
    }

    /**
     * Toggle descendant visibility and maintain the supplied expansion set.
     *
     * @param {Element} button Branch button.
     * @param {string} id Node identity.
     * @param {boolean} expanded Next expansion state.
     * @returns {void}
     */
    #setExpanded(button, id, expanded) {
        if (expanded) {
            this.#model.expandedPaths.add(id);
        } else {
            this.#model.expandedPaths.delete(id);
        }
        const childContainer = button.closest(".tree-node-wrap")?.querySelector(":scope > .tree-children");
        if (childContainer) {
            childContainer.hidden = !expanded;
        }
        const caret = button.querySelector(".tree-caret");
        if (caret) {
            caret.innerHTML = icon(expanded ? "chevronDown" : "chevronRight");
        }
        this.dispatchEvent(new CustomEvent("brain-tree-toggle", {
            bubbles: true,
            detail: { id, expanded }
        }));
    }

    /**
     * Emit one toolbar action for the mounted domain.
     *
     * @param {Element} button Trigger button.
     * @returns {void}
     */
    #emitToolbarAction(button) {
        this.dispatchEvent(new CustomEvent("brain-tree-toolbar-action", {
            bubbles: true,
            detail: { action: button.getAttribute("data-tree-toolbar-action") || "" }
        }));
    }

    /**
     * Emit one contextual node action.
     *
     * @param {Element} button Trigger button.
     * @returns {void}
     */
    #emitNodeAction(button) {
        const id = button.getAttribute("data-tree-action-node") || "";
        this.#openActionNodeId = "";
        this.dispatchEvent(new CustomEvent("brain-tree-action", {
            bubbles: true,
            detail: {
                action: button.getAttribute("data-tree-action") || "",
                node: this.#findNode(this.#model.nodes, id)
            }
        }));
    }

    /**
     * Close contextual menus when the gesture happens outside the tree.
     *
     * @param {PointerEvent} event Pointer interaction.
     * @returns {void}
     */
    #closeMenusOutside(event) {
        if (!this.#openActionNodeId || this.contains(event.target)) {
            return;
        }
        this.#openActionNodeId = "";
        this.#render();
    }

    /**
     * Toggle the contextual menu anchored to an item-local action trigger.
     *
     * @param {Element} trigger Action trigger.
     * @param {MouseEvent} event Native click event.
     * @returns {void}
     */
    #toggleNodeActionMenu(trigger, event) {
        event.preventDefault();
        event.stopPropagation();
        const nodeId = trigger.getAttribute("data-tree-actions") || "";
        this.#openActionNodeId = this.#openActionNodeId === nodeId ? "" : nodeId;
        this.#render();
    }

    /**
     * Resolve one node by rendered identity.
     *
     * @param {StructureTreeNode[]} nodes Candidate nodes.
     * @param {string} id Rendered identity.
     * @returns {StructureTreeNode|null} Matching node.
     */
    #findNode(nodes, id) {
        for (const node of nodes) {
            if ((node.id || node.path) === id) {
                return node;
            }
            const found = this.#findNode(node.children || [], id);
            if (found) {
                return found;
            }
        }
        return null;
    }
}

customElements.define(StructureTree.selector, StructureTree);
