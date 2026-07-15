import { compactLabel, escapeHtml, renderMarkdown } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";
import { StructureTree } from "./structure-tree.ts";

void StructureTree;

/**
 * MemoryView renders the memory store as a collapsible tree and one focused work area.
 */
export class MemoryView extends HTMLElement {
    static get selector() {
        return "brain-memory-view";
    }

    #api = null;
    #state = null;
    #paths = [];
    #selectedPath = "";
    #selectedDomain = "";
    #content = "";
    #status = "Preparando memoria...";
    #filter = "";
    #mode = "browse";
    #loadingTree = false;
    #loadingEntry = false;
    #saving = false;
    #expandedNodes = new Set();
    #pendingTarget = null;

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#pendingTarget = this.#state?.consumeRouteTarget?.("memory") || this.#pendingTarget;
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
        this.#selectedDomain = this.#selectedDomain || this.#topDomains()[0] || "";
        if (this.#selectedDomain) {
            this.#expandedNodes.add(this.#selectedDomain);
        }
        this.#status = result.ok ? `${this.#leafPaths().length} entradas` : result.stderr || result.error || "No se pudo cargar memoria.";
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
        const target = this.#pendingTarget || this.#state?.consumeRouteTarget?.("memory");
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
    async #loadEntry(path, mode = "read", forceRefresh = false) {
        this.#selectedPath = path;
        this.#selectedDomain = this.#parentPath(path) || path.split(".")[0] || this.#selectedDomain;
        this.#expandAncestors(path);
        this.#mode = mode;
        this.#loadingEntry = true;
        this.#status = compactLabel(path);
        this.#render();
        const result = await this.#api.memoryEntry(path, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#content = result.data?.content || result.stdout || "";
        this.#status = result.ok ? compactLabel(path) : result.stderr || result.error || "No se pudo leer la entrada.";
        this.#loadingEntry = false;
        this.#render();
    }

    /**
     * Prepare a new entry in edit mode under the selected domain.
     *
     * @returns {void}
     */
    #newEntry() {
        const baseDomain = this.#selectedDomain || this.#topDomains()[0] || "notes";
        this.#selectedPath = `${baseDomain}.nueva_entrada`;
        this.#content = "# Nueva entrada\n\nEscribe memoria Markdown aqui.";
        this.#mode = "edit";
        this.#status = "Nueva entrada";
        this.#render();
    }

    /**
     * Save editor content to memory.
     *
     * @returns {Promise<void>} Resolves after save.
     */
    async #saveEntry() {
        const path = this.querySelector("[data-role='memory-path']")?.value.trim();
        const content = this.querySelector("[data-role='memory-content']")?.value || this.#content;
        if (!path) {
            this.#status = "Define una ruta antes de guardar.";
            this.#render();
            return;
        }
        this.#saving = true;
        this.#render();
        const result = await this.#api.saveMemoryEntry(path, content);
        this.#state?.setLastResult(result);
        this.#selectedPath = path;
        this.#selectedDomain = this.#parentPath(path) || path.split(".")[0] || "";
        this.#content = content;
        this.#status = result.ok ? compactLabel(path) : result.stderr || result.error || "No se pudo guardar.";
        this.#saving = false;
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
        this.#status = result.ok ? "Entrada eliminada" : result.stderr || result.error || "No se pudo eliminar.";
        await this.#loadTree(true);
    }

    /**
     * Create a memory domain.
     *
     * @returns {Promise<void>} Resolves after creation.
     */
    async #createDomain() {
        const domain = this.querySelector("[data-role='domain-name']")?.value.trim();
        if (!domain) {
            this.#status = "Escribe un dominio.";
            this.#render();
            return;
        }
        const result = await this.#api.createMemoryDomain(domain);
        this.#state?.setLastResult(result);
        this.#selectedDomain = domain;
        this.#selectedPath = "";
        this.#expandedNodes.add(domain.split(".")[0]);
        this.#status = result.ok ? `Dominio ${domain}` : result.stderr || result.error || "No se pudo crear dominio.";
        await this.#loadTree(true);
    }

    /**
     * Delete selected domain.
     *
     * @returns {Promise<void>} Resolves after deletion.
     */
    async #deleteDomain() {
        const domain = this.querySelector("[data-role='domain-name']")?.value.trim() || this.#selectedDomain;
        if (!domain) {
            return;
        }
        const result = await this.#api.deleteMemoryDomain(domain);
        this.#state?.setLastResult(result);
        this.#selectedDomain = "";
        this.#selectedPath = "";
        this.#content = "";
        this.#mode = "browse";
        this.#status = result.ok ? "Dominio eliminado" : result.stderr || result.error || "No se pudo eliminar dominio.";
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
     * Render the primary action for the current mode.
     *
     * @returns {string} HTML.
     */
    #renderPrimaryAction() {
        if (this.#mode === "edit") {
            return this.#renderIconButton("save-entry", "save", this.#saving ? "Guardando entrada" : "Guardar entrada", "primary-action compact-action", this.#saving);
        }
        if (this.#mode === "domains") {
            return this.#renderIconButton("create-domain", "folderPlus", "Crear dominio", "primary-action compact-action");
        }
        return this.#renderIconButton("new-entry", "documentPlus", "Nueva entrada", "primary-action compact-action");
    }

    /**
     * Render the memory mode menu as an icon-only control.
     *
     * @returns {string} HTML.
     */
    #renderModeMenu() {
        const modes = ["browse", "read", "edit", "domains"];
        const label = this.#modeLabel(this.#mode);
        return `
            <details class="action-menu mode-menu">
                <summary class="icon-action" title="Modo: ${escapeHtml(label)}" aria-label="Modo de memoria: ${escapeHtml(label)}">
                    ${icon(this.#modeIcon(this.#mode))}
                </summary>
                <div class="action-menu-panel">
                    ${modes.map(mode => `
                        <button data-action="set-memory-mode" data-memory-mode="${escapeHtml(mode)}" ${mode === this.#mode ? "aria-current=\"true\"" : ""}>
                            ${icon(this.#modeIcon(mode))}${escapeHtml(this.#modeLabel(mode))}
                        </button>
                    `).join("")}
                </div>
            </details>
        `;
    }

    /**
     * Render a square icon-only toolbar button.
     *
     * @param {string} action Data action name.
     * @param {string} iconName Shared SVG icon key.
     * @param {string} label Accessible action label.
     * @param {string} className Extra CSS classes.
     * @param {boolean} disabled Whether the action is disabled.
     * @returns {string} HTML.
     */
    #renderIconButton(action, iconName, label, className = "", disabled = false) {
        return `
            <button
                data-action="${escapeHtml(action)}"
                class="icon-action ${escapeHtml(className)}"
                title="${escapeHtml(label)}"
                aria-label="${escapeHtml(label)}"
                ${disabled ? "disabled" : ""}
            >${icon(iconName)}</button>
        `;
    }

    /**
     * Return the icon key for one memory mode.
     *
     * @param {string} mode Memory mode.
     * @returns {string} Icon key.
     */
    #modeIcon(mode) {
        return {
            browse: "database",
            read: "eye",
            edit: "edit",
            domains: "folder"
        }[mode] || "database";
    }

    /**
     * Return the reader-facing label for one memory mode.
     *
     * @param {string} mode Memory mode.
     * @returns {string} Spanish mode label.
     */
    #modeLabel(mode) {
        return {
            browse: "Explorar",
            read: "Leer",
            edit: "Editar",
            domains: "Dominios"
        }[mode] || "Explorar";
    }

    /**
     * Render the contextual secondary action menu.
     *
     * @returns {string} HTML.
     */
    #renderActionMenu() {
        const isEntry = Boolean(this.#selectedPath);
        const label = isEntry ? "Entrada" : "Dominio";
        const entryActions = `
            <button data-action="refresh-memory">${icon("refresh")}Actualizar</button>
            <button data-action="edit-entry" ${this.#selectedPath ? "" : "disabled"}>${icon("edit")}Editar entrada</button>
            <button data-action="duplicate-entry" ${this.#selectedPath ? "" : "disabled"}>${icon("copy")}Duplicar entrada</button>
            <button data-action="delete-entry" class="danger-button" ${this.#selectedPath ? "" : "disabled"}>${icon("trash")}Eliminar entrada</button>
        `;
        const domainActions = `
            <button data-action="refresh-memory">${icon("refresh")}Actualizar arbol</button>
            <button data-action="new-entry" ${this.#selectedDomain ? "" : "disabled"}>${icon("plus")}Nueva entrada aqui</button>
            <button data-action="domain-mode">${icon("folder")}Gestionar dominio</button>
            <button data-action="delete-domain" class="danger-button" ${this.#selectedDomain ? "" : "disabled"}>${icon("trash")}Eliminar dominio</button>
        `;
        return `
            <details class="action-menu">
                <summary class="icon-action" title="Acciones de ${escapeHtml(label.toLowerCase())}" aria-label="Acciones de ${escapeHtml(label.toLowerCase())}">
                    ${icon("more")}
                </summary>
                <div class="action-menu-panel">
                    ${isEntry ? entryActions : domainActions}
                </div>
            </details>
        `;
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
        const children = this.#childItemsForSelectedDomain();
        return `
            <div class="content-head">
                <strong>${escapeHtml(this.#selectedDomain || "Memoria")}</strong>
                <span>${escapeHtml(String(children.length))} visibles</span>
            </div>
            <div class="entry-list scroll-list">
                ${children.length ? children.map(item => this.#renderContentItem(item)).join("") : `<p class="empty-state">Selecciona un nodo del arbol.</p>`}
            </div>
        `;
    }

    /**
     * Render one child row in the content area.
     *
     * @param {object} item Tree item.
     * @returns {string} HTML.
     */
    #renderContentItem(item) {
        const isBranch = item.children.size > 0;
        const action = isBranch ? "select-domain" : "select-entry";
        const count = isBranch ? `${this.#leafPathsUnder(item.path).length} entradas` : "Entrada";
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
                <strong>${escapeHtml(compactLabel(this.#selectedPath) || "Sin entrada")}</strong>
                <span>${escapeHtml(this.#selectedPath || this.#status)}</span>
            </div>
            <article class="markdown-preview scroll-area">
                ${this.#loadingEntry ? this.#loadingState("Renderizando Markdown") : renderMarkdown(this.#content || "Selecciona una entrada.")}
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
                    <span>Ruta</span>
                    <input data-role="memory-path" value="${escapeHtml(this.#selectedPath)}" placeholder="dominio.entrada">
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
                    <span>Dominio</span>
                    <input data-role="domain-name" value="${escapeHtml(this.#selectedDomain)}" placeholder="nuevo.dominio">
                </label>
            </div>
            <div class="domain-grid scroll-list">
                ${this.#topDomains().map(domain => `
                    <button class="domain-tile ${domain === this.#selectedDomain ? "is-active" : ""}" data-action="select-domain" data-node-path="${escapeHtml(domain)}">
                        ${icon("database")}
                        <strong>${escapeHtml(domain)}</strong>
                        <span>${escapeHtml(String(this.#leafPathsUnder(domain).length))} entradas</span>
                    </button>
                `).join("") || `<p class="empty-state">Sin dominios.</p>`}
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
    #renderTreeNode(node, depth) {
        const hasChildren = node.children.size > 0;
        const isOpen = this.#expandedNodes.has(node.path);
        const isActive = node.path === this.#selectedDomain || node.path === this.#selectedPath;
        const children = Array.from(node.children.values()).sort(this.#sortTreeNodes);
        const isVisible = this.#matchesFilter(node) || children.some(child => this.#nodeContainsFilter(child));
        if (!isVisible) {
            return "";
        }
        return `
            <div class="tree-node-wrap">
                <button class="tree-node ${isActive ? "is-active" : ""}" style="--tree-depth:${depth}" data-node-path="${escapeHtml(node.path)}" data-node-branch="${hasChildren ? "true" : "false"}">
                    <span class="tree-caret">${hasChildren ? icon(isOpen ? "chevronDown" : "chevronRight") : ""}</span>
                    ${icon(hasChildren ? "folder" : "document")}
                    <span>${escapeHtml(node.label)}</span>
                    ${hasChildren ? `<small>${escapeHtml(String(this.#leafPathsUnder(node.path).length))}</small>` : ""}
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
        if (!treeElement) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#selectedPath || this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
            toggleOnBranchSelect: true,
            title: "Memoria",
            toolbarActions: [
                { id: "new-entry", label: "Nueva entrada", icon: "plus" },
                { id: "create-domain", label: "Nuevo dominio", icon: "folder" },
                { id: "refresh", label: "Actualizar arbol", icon: "refresh" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "database",
            searchQuery: this.#filter,
            emptyText: this.#loadingTree ? "Cargando arbol..." : "Sin rutas cargadas."
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onTreeAction(event));
        treeElement.addEventListener("brain-tree-search", event => {
            this.#filter = event.detail.query;
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
    #treeNodes() {
        const toNode = node => {
            const children = Array.from(node.children.values())
                .filter(child => this.#matchesFilter(child) || this.#nodeContainsFilter(child))
                .sort(this.#sortTreeNodes)
                .map(toNode);
            const hasChildren = children.length > 0;
            return {
                id: node.path,
                path: node.path,
                label: node.label,
                count: hasChildren ? this.#leafPathsUnder(node.path).length : undefined,
                children,
                actions: hasChildren
                    ? [
                        { id: "new-entry", label: "Nueva entrada", icon: "plus" },
                        { id: "delete-domain", label: "Eliminar dominio", icon: "trash", danger: true }
                    ]
                    : [
                        { id: "open-entry", label: "Abrir", icon: "document" },
                        { id: "edit-entry", label: "Editar", icon: "edit" },
                        { id: "duplicate-entry", label: "Duplicar", icon: "duplicate" },
                        { id: "delete-entry", label: "Eliminar", icon: "trash", danger: true }
                    ]
            };
        };
        return Array.from(this.#buildTree().children.values())
            .filter(node => this.#matchesFilter(node) || this.#nodeContainsFilter(node))
            .sort(this.#sortTreeNodes)
            .map(toNode);
    }

    /**
     * React to a shared tree selection.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeSelected(event) {
        const { path, branch, clickedCaret } = event.detail;
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
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeToolbarAction(event) {
        const action = event.detail.action;
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
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeAction(event) {
        const { action, node } = event.detail;
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
     * Render loading state.
     *
     * @param {string} label Loading label.
     * @returns {string} HTML.
     */
    #loadingState(label) {
        return `
            <div class="loading-state">
                <span></span>
                <strong>${escapeHtml(label)}</strong>
            </div>
        `;
    }

    /**
     * Build a tree from dot-notated paths.
     *
     * @returns {object} Tree root.
     */
    #buildTree() {
        const root = { label: "", path: "", children: new Map() };
        for (const path of this.#paths) {
            const parts = String(path).split(".").filter(Boolean);
            let current = root;
            parts.forEach((part, index) => {
                const nodePath = parts.slice(0, index + 1).join(".");
                if (!current.children.has(part)) {
                    current.children.set(part, { label: part, path: nodePath, children: new Map() });
                }
                current = current.children.get(part);
            });
        }
        return root;
    }

    /**
     * Return direct children for the selected domain.
     *
     * @returns {object[]} Child tree nodes.
     */
    #childItemsForSelectedDomain() {
        const tree = this.#buildTree();
        const node = this.#findNode(tree, this.#selectedDomain);
        const parent = node || tree;
        return Array.from(parent.children.values())
            .filter(item => this.#matchesFilter(item) || this.#nodeContainsFilter(item))
            .sort(this.#sortTreeNodes);
    }

    /**
     * Find a node by full path.
     *
     * @param {object} root Tree root.
     * @param {string} path Dot-notated path.
     * @returns {object|null} Tree node.
     */
    #findNode(root, path) {
        if (!path) {
            return root;
        }
        return path.split(".").reduce((node, part) => node?.children?.get(part), root) || null;
    }

    /**
     * Return top-level domains.
     *
     * @returns {string[]} Domain names.
     */
    #topDomains() {
        return [...new Set(this.#paths.map(path => path.split(".")[0]).filter(Boolean))];
    }

    /**
     * Return leaf entry paths.
     *
     * @returns {string[]} Leaf paths.
     */
    #leafPaths() {
        return this.#paths.filter(path => !this.#hasChildren(path) && path.includes("."));
    }

    /**
     * Return leaf entry paths under one domain path.
     *
     * @param {string} prefix Domain path.
     * @returns {string[]} Leaf paths.
     */
    #leafPathsUnder(prefix) {
        return this.#leafPaths().filter(path => path === prefix || path.startsWith(`${prefix}.`));
    }

    /**
     * Return whether a path has child paths.
     *
     * @param {string} path Dot-notated path.
     * @returns {boolean} True when the path has children.
     */
    #hasChildren(path) {
        return this.#paths.some(candidate => candidate !== path && candidate.startsWith(`${path}.`));
    }

    /**
     * Resolve parent path.
     *
     * @param {string} path Dot-notated path.
     * @returns {string} Parent path.
     */
    #parentPath(path) {
        const parts = String(path || "").split(".");
        parts.pop();
        return parts.join(".");
    }

    /**
     * Expand ancestors for a selected path.
     *
     * @param {string} path Dot-notated path.
     * @returns {void}
     */
    #expandAncestors(path) {
        const parts = String(path || "").split(".");
        for (let index = 1; index < parts.length; index += 1) {
            this.#expandedNodes.add(parts.slice(0, index).join("."));
        }
    }

    /**
     * Return whether a node matches the text filter.
     *
     * @param {object} node Tree node.
     * @returns {boolean} True when visible by filter.
     */
    #matchesFilter(node) {
        const needle = this.#filter.toLowerCase();
        return !needle || node.path.toLowerCase().includes(needle);
    }

    /**
     * Return whether a node or descendants match the current filter.
     *
     * @param {object} node Tree node.
     * @returns {boolean} True when a descendant matches.
     */
    #nodeContainsFilter(node) {
        if (this.#matchesFilter(node)) {
            return true;
        }
        return Array.from(node.children.values()).some(child => this.#nodeContainsFilter(child));
    }

    /**
     * Sort tree nodes with branches first.
     *
     * @param {object} left First node.
     * @param {object} right Second node.
     * @returns {number} Sort order.
     */
    #sortTreeNodes(left, right) {
        const leftBranch = left.children.size > 0 ? 0 : 1;
        const rightBranch = right.children.size > 0 ? 0 : 1;
        return leftBranch - rightBranch || left.label.localeCompare(right.label);
    }

    /**
     * Bind DOM events after render.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelectorAll("[data-action='set-memory-mode']").forEach(button => button.addEventListener("click", () => {
            this.#mode = button.getAttribute("data-memory-mode") || this.#mode;
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
            const isBranch = item.getAttribute("data-node-branch") === "true" || this.#hasChildren(path);
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
