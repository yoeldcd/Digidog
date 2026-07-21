/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";
import type {
    StructureTreeModel,
    StructureTreeModelInput,
    StructureTreeNode
} from "../view_models/structure-tree-view-model.ts";

const TREE_WIDTH_STORAGE_KEY = "brain.structure-tree.width";

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
 * @property {boolean} [folder] Preserve folder affordances when the node has no loaded children.
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
    /**
     * Provides the unique CSS selector used to identify and locate the StructureTree component within the DOM.
     * @returns {string} A string representing the component's custom element tag name.
     */
    static get selector() {
        return "brain-structure-tree";
    }

    /**
     * Maintains the internal state and configuration for the structure tree component, including node hierarchy, selection, and UI preferences.
     *
     * @type {StructureTreeModel}
     */
    #model: StructureTreeModel = {
        nodes: [],
        selectedPath: "",
        expandedPaths: new Set<string>(),
        toggleOnBranchSelect: true,
        title: "",
        toolbarActions: [],
        showSearch: true,
        searchPlaceholder: "Search...",
        sortDirection: "asc",
        emptyText: "No items yet.",
        defaultBranchIcon: null,
        defaultLeafIcon: null
    };

    /**
     * Stores the unique identifier of the currently active or expanded action node within the structure tree.
     *
     * @type {string}
     */
    #openActionNodeId = "";
    /**
     * Maintains the current text filter used to search and highlight nodes within the structure tree.
     *
     * @type {string}
     */
    #searchQuery = "";
    /**
     * A private state property that determines whether the structure tree's filtering mechanism is deactivated.
     *
     * @type {boolean}
     */
    #disableFilter = false;
    /**
     * Holds a reference to the HTML element used for resizing panes within the structure tree component.
     *
     * @type {HTMLElement | null}
     */
    #resizePane: HTMLElement | null = null;
    /**
     * Holds a reference to the HTML element used as the resize handle for the structure tree component.
     *
     * @type {HTMLDivElement | null}
     */
    #resizeHandle: HTMLDivElement | null = null;
    /**
     * Stores the unique identifier of the active resize pointer element, or null when no resizing operation is in progress.
     *
     * @type {number | null}
     */
    #resizePointerId: number | null = null;
    /**
     * Stores the initial horizontal coordinate of the cursor when a resize operation begins.
     *
     * @type {number}
     */
    #resizeOriginX = 0;
    /**
     * Stores the initial horizontal coordinate of the resize handle at the start of a resizing operation.
     *
     * @type {number}
     */
    #resizeOriginWidth = 0;
    /**
     * Handles global pointer down events to trigger the closure of menus located outside the event target.
     *
     * @type {(event: PointerEvent) => void}
     */
    #onDocumentPointerDown = (event: PointerEvent) => this.#closeMenusOutside(event);
    /**
     * Handles pointer movement events to trigger the tree resizing logic based on the current pointer position.
     *
     * @type {(event: PointerEvent) => void}
     */
    #onResizePointerMove = (event: PointerEvent) => this.#resizeTreeFromPointer(event);
    /**
     * An event handler that triggers the completion of the tree resizing process when a pointer-up event occurs.
     *
     * @type {(event: PointerEvent) => void}
     */
    #onResizePointerUp = (event: PointerEvent) => this.#finishTreeResize(event);

    /**
     * Assign the full tree presentation model.
     *
     * @param {{nodes: StructureTreeNode[], selectedPath?: string, expandedPaths?: Set<string>, toggleOnBranchSelect?: boolean, title?: string, toolbarActions?: object[], searchQuery?: string, disableFilter?: boolean, showSearch?: boolean, searchPlaceholder?: string, sortDirection?: "asc"|"desc", emptyText?: string}} value Tree model.
     */
    set model(value: StructureTreeModelInput) {
        this.#model = {
            nodes: Array.isArray(value?.nodes) ? value.nodes : [],
            selectedPath: value?.selectedPath || "",
            expandedPaths: value?.expandedPaths instanceof Set ? value.expandedPaths : new Set(),
            toggleOnBranchSelect: value?.toggleOnBranchSelect !== false,
            title: value?.title || "",
            toolbarActions: Array.isArray(value?.toolbarActions) ? value.toolbarActions : [],
            showSearch: value?.showSearch !== false,
            searchPlaceholder: value?.searchPlaceholder || "Search...",
            sortDirection: value?.sortDirection === "desc" ? "desc" : "asc",
            emptyText: value?.emptyText || "No items yet."
            ,defaultBranchIcon: value.defaultBranchIcon ?? null
            ,defaultLeafIcon: value.defaultLeafIcon ?? null
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
        this.#installResizeHandle();
        document.addEventListener("pointerdown", this.#onDocumentPointerDown);
    }

    /**
     * Release the document-level menu listener.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        document.removeEventListener("pointerdown", this.#onDocumentPointerDown);
        window.removeEventListener("pointermove", this.#onResizePointerMove);
        window.removeEventListener("pointerup", this.#onResizePointerUp);
        this.#resizeHandle?.remove();
        this.#resizeHandle = null;
        this.#resizePane = null;
    }

    /**
     * Mount a full-height drag target on the owning structure-tree pane.
     */
    #installResizeHandle() {
        const pane = this.closest(".structure-tree");
        if (!(pane instanceof HTMLElement) || pane.querySelector(":scope > .structure-tree-resize-handle")) return;
        this.#resizePane = pane;
        pane.classList.add("has-resize-handle");
        try {
            const storedWidth = Number(localStorage.getItem(TREE_WIDTH_STORAGE_KEY) || 0);
            if (storedWidth) this.#setTreeWidth(storedWidth);
        } catch {
            // Storage can be unavailable in restricted browser contexts; resizing still works in-memory.
        }
        const handle = document.createElement("div");
        handle.className = "structure-tree-resize-handle";
        handle.setAttribute("role", "separator");
        handle.setAttribute("aria-label", "Resize tree");
        handle.setAttribute("aria-orientation", "vertical");
        handle.tabIndex = 0;
        handle.addEventListener("pointerdown", event => this.#startTreeResize(event));
        handle.addEventListener("keydown", event => this.#resizeTreeFromKeyboard(event));
        pane.append(handle);
        this.#resizeHandle = handle;
    }

    /**
     * Begin one right-edge horizontal resize gesture.
     * @param {PointerEvent} event The pointer event triggering the resize operation, used to validate the primary mouse button and capture initial coordinates.
     */
    #startTreeResize(event: PointerEvent): void {
        if (!this.#resizePane || event.button !== 0) return;
        event.preventDefault();
        this.#resizePointerId = event.pointerId;
        this.#resizeOriginX = event.clientX;
        this.#resizeOriginWidth = this.#resizePane.getBoundingClientRect().width;
        this.#resizePane.classList.add("is-resizing");
        this.#resizeHandle?.setPointerCapture?.(event.pointerId);
        window.addEventListener("pointermove", this.#onResizePointerMove);
        window.addEventListener("pointerup", this.#onResizePointerUp);
    }

    /**
     * Update the sidebar while the pointer moves anywhere along the viewport.
     * @param {PointerEvent} event The pointer event containing the current client coordinates and pointer identifier.
     */
    #resizeTreeFromPointer(event: PointerEvent): void {
        if (event.pointerId !== this.#resizePointerId) return;
        this.#setTreeWidth(this.#resizeOriginWidth + event.clientX - this.#resizeOriginX);
    }

    /**
     * Finish and persist one resize gesture.
     * @param {PointerEvent} event The pointer event that triggered the completion of the resize action.
     */
    #finishTreeResize(event: PointerEvent): void {
        if (event.pointerId !== this.#resizePointerId) return;
        this.#resizePointerId = null;
        this.#resizePane?.classList.remove("is-resizing");
        window.removeEventListener("pointermove", this.#onResizePointerMove);
        window.removeEventListener("pointerup", this.#onResizePointerUp);
        this.#persistTreeWidth();
    }

    /**
     * Support precise keyboard resizing from the same separator.
     * @param {KeyboardEvent} event The keyboard event containing the key pressed and modifier state.
     */
    #resizeTreeFromKeyboard(event: KeyboardEvent): void {
        if (!this.#resizePane || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
        event.preventDefault();
        const direction = event.key === "ArrowRight" ? 1 : -1;
        this.#setTreeWidth(this.#resizePane.getBoundingClientRect().width + direction * (event.shiftKey ? 40 : 12));
        this.#persistTreeWidth();
    }

    /**
     * Clamp and apply a shared desktop tree width.
     * @param {number} width The requested width in pixels to be applied to the pane.
     */
    #setTreeWidth(width: number): void {
        if (!this.#resizePane) return;
        const maximum = Math.min(640, window.innerWidth * 0.48);
        const nextWidth = Math.max(380, Math.min(maximum, Number(width) || 380));
        this.#resizePane.style.width = `${Math.round(nextWidth)}px`;
        this.#resizeHandle?.setAttribute("aria-valuenow", String(Math.round(nextWidth)));
    }

    /**
     * Persist the most recent shared tree width when browser storage is available.
     */
    #persistTreeWidth() {
        if (!this.#resizePane) return;
        try {
            localStorage.setItem(TREE_WIDTH_STORAGE_KEY, String(Math.round(this.#resizePane.getBoundingClientRect().width)));
        } catch {
            // Keep the active width even when persistence is unavailable.
        }
    }

    /**
     * Recursively determines if a structure node or any of its descendants match the current search query, unless filtering is disabled.
     * @param {StructureTreeNode} node The structure node being evaluated for a match against the search criteria.
     * @returns {boolean} True if the node's label or path contains the search query, or if any of its children match; otherwise false.
     */
    #matchesFilter(node: StructureTreeNode): boolean {
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

    /**
     * Updates the component's innerHTML by rendering a toolbar, an optional search input, and a sorted, filtered list of structure nodes based on the current model state.
     */
    #render() {
        const rootDirection = this.#model.sortDirection === "desc" ? -1 : 1;
        const sortedRootNodes = [...this.#model.nodes].sort((left, right) => this.#compareNodes(left, right, rootDirection));
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
                    <button class="icon-action ${action.active ? "is-active" : ""}" data-tree-toolbar-action="${escapeHtml(action.id)}" title="${escapeHtml(action.label)}" aria-label="${escapeHtml(action.label)}" ${action.active !== undefined ? `aria-pressed="${String(!!action.active)}"` : ""}>
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
    #renderNode(node: StructureTreeNode, depth: number): string {
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
                            <time>${escapeHtml(node.timestamp || "No date")}</time>
                            <strong>${escapeHtml(node.label)}</strong>
                            <small>${escapeHtml(node.detail || "")}</small>
                            ${this.#renderNodeActionTrigger(node)}
                        </button>
                        ${this.#renderNodeActionMenu(node)}
                    </div>
                </div>
            `;
        }

        const childDirection = node.sortDirection === "desc" ? -1 : 1;
        const sortedChildren = [...children].sort((left, right) => this.#compareNodes(left, right, childDirection));
        const isFolder = hasChildren || node.folder === true;
        const caret = hasChildren
            ? icon(expanded ? "chevronDown" : "chevronRight")
            : isFolder ? "+" : "";

        return `
            <div class="tree-node-wrap" role="treeitem" aria-level="${depth}" ${hasChildren ? `aria-expanded="${expanded}"` : ""} aria-selected="${active}" style="--depth: ${depth};">
                <div class="tree-item ${active ? "is-active" : ""}">
                    <button class="tree-node ${hasChildren ? "" : "tree-node--leaf"} ${sourceClass} ${active ? "is-active" : ""}"${sourceStyle}
                        data-tree-id="${escapeHtml(node.id || node.path)}" data-tree-path="${escapeHtml(node.path)}" data-tree-branch="${hasChildren}"
                        title="${escapeHtml(node.label)}">
                        <span class="tree-caret ${isFolder && !hasChildren ? "is-empty-folder" : ""}">${caret}</span>
                        ${icon(node.icon || (isFolder ? defaultBranch : defaultLeaf))}
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
    #renderNodeActionTrigger(node: StructureTreeNode): string {
        if (!node.actions?.length) {
            return "";
        }
        const nodeId = escapeHtml(node.id || node.path);
        return `
            <span class="tree-action-trigger" data-tree-actions="${nodeId}" title="Actions" aria-label="Actions">
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
    #renderNodeActionMenu(node: StructureTreeNode): string {
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
        this.querySelectorAll<HTMLElement>("[data-tree-id]").forEach(button => {
            button.addEventListener("click", event => this.#onNodeClicked(button, event));
        });
        this.querySelectorAll<HTMLElement>("[data-tree-toolbar-action]").forEach(button => {
            button.addEventListener("click", () => this.#emitToolbarAction(button));
        });
        this.querySelectorAll<HTMLElement>("[data-tree-actions]").forEach(trigger => {
            trigger.addEventListener("click", event => this.#toggleNodeActionMenu(trigger, event));
        });
        this.querySelectorAll<HTMLElement>("[data-tree-action]").forEach(button => {
            button.addEventListener("click", () => this.#emitNodeAction(button));
        });

        // Filter Input Event
        const filterInput = this.querySelector<HTMLInputElement>("[data-role='tree-filter']");
        filterInput?.addEventListener("input", event => {
            this.#searchQuery = event.currentTarget instanceof HTMLInputElement ? event.currentTarget.value : "";
            
            // Render only nodes container to keep focus and cursor position!
            const rootDirection = this.#model.sortDirection === "desc" ? -1 : 1;
            const sortedRootNodes = [...this.#model.nodes].sort((left, right) => this.#compareNodes(left, right, rootDirection));
            
            const nodesContainer = this.querySelector(".structure-tree-nodes");
            if (nodesContainer) {
                nodesContainer.innerHTML = sortedRootNodes.map(node => this.#renderNode(node, 1)).join("");
            }
            
            // Re-bind listeners on new node elements!
            this.querySelectorAll<HTMLElement>("[data-tree-id]").forEach(button => {
                button.addEventListener("click", ev => this.#onNodeClicked(button, ev));
            });
            this.querySelectorAll<HTMLElement>("[data-tree-actions]").forEach(trigger => {
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
    #onNodeClicked(button: HTMLElement, event: Event): void {
        const eventTarget = event.target instanceof Element ? event.target : null;
        if (eventTarget?.closest("[data-tree-actions]")) {
            return;
        }
        const id = button.getAttribute("data-tree-id") || "";
        const path = button.getAttribute("data-tree-path") || "";
        const branch = button.getAttribute("data-tree-branch") === "true";
        const clickedCaret = Boolean(eventTarget?.closest(".tree-caret"));
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
     * Respect explicit super-domain order before the default branch-first tree order.
     * @param {StructureTreeNode} left The first node to compare.
     * @param {StructureTreeNode} right The second node to compare.
     * @param {number} direction A multiplier used to invert or maintain the sort order direction.
     * @returns {number} A numeric value indicating whether the left node precedes, follows, or is equivalent to the right node.
     */
    #compareNodes(left: StructureTreeNode, right: StructureTreeNode, direction: number): number {
        if (left.sortKey !== undefined || right.sortKey !== undefined) {
            return direction * String(left.sortKey || left.label || "")
                .localeCompare(String(right.sortKey || right.label || ""));
        }
        const leftHas = Array.isArray(left.children) && left.children.length > 0;
        const rightHas = Array.isArray(right.children) && right.children.length > 0;
        if (leftHas !== rightHas) return leftHas ? -1 : 1;
        return direction * String(left.label || "").localeCompare(String(right.label || ""));
    }

    /**
     * Restore the node that initiated a gesture after a consumer re-renders
     * and replaces the shared tree synchronously.
     *
     * @param {string} id Stable rendered node identity.
     * @param {number} scrollTop Previous tree scroll offset.
     * @returns {void}
     */
    #restoreInteractionAnchor(id: string, scrollTop: number): void {
        requestAnimationFrame(() => {
            const trees = document.querySelectorAll<StructureTree>(StructureTree.selector);
            for (const tree of Array.from(trees)) {
                const button = Array.from(tree.querySelectorAll<HTMLElement>("[data-tree-id]"))
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
    #setExpanded(button: HTMLElement, id: string, expanded: boolean): void {
        if (expanded) {
            this.#model.expandedPaths.add(id);
        } else {
            this.#model.expandedPaths.delete(id);
        }
        const childContainer = button.closest(".tree-node-wrap")?.querySelector<HTMLElement>(":scope > .tree-children");
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
    #emitToolbarAction(button: HTMLElement): void {
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
    #emitNodeAction(button: HTMLElement): void {
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
    #closeMenusOutside(event: PointerEvent): void {
        if (!this.#openActionNodeId || (event.target instanceof Node && this.contains(event.target))) {
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
    #toggleNodeActionMenu(trigger: HTMLElement, event: Event): void {
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
    #findNode(nodes: StructureTreeNode[], id: string): StructureTreeNode | null {
        for (const node of nodes) {
            if ((node.id || node.path) === id) {
                return node;
            }
            const found: StructureTreeNode | null = this.#findNode(node.children || [], id);
            if (found) {
                return found;
            }
        }
        return null;
    }
}

customElements.define(StructureTree.selector, StructureTree);
