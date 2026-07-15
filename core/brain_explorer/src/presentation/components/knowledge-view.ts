import { escapeHtml, optionTags } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";
import { StructureTree } from "./structure-tree.ts";

void StructureTree;

/**
 * KnowledgeView renders a canvas-based explorer for graph records returned by the CLI facade.
 * Entities/classes become draggable nodes. Relations become selectable edges.
 */
export class KnowledgeView extends HTMLElement {
    static get selector() {
        return "brain-knowledge-view";
    }

    #api = null;
    #state = null;
    #scope = "global";
    #mode = "all";
    #domain = "all";
    #query = "";
    #output = null;
    #records = [];
    #relations = [];
    #nodes = [];
    #edges = [];
    #selectedNodeId = "";
    #selectedRelationId = "";
    #regionNodeIds = new Set();
    #regionEdgeIds = new Set();
    #regionPositions = new Map();
    #dragNode = null;
    #panState = null;
    #cameraAnimationFrame = 0;
    #viewport = { x: 0, y: 0, scale: 1 };
    #renderFrustum = null;
    #expandedDomains = new Set(["all"]);
    #resizeObserver = null;
    #loadScheduled = false;
    #needsViewportFit = true;
    #filtersOpen = false;
    #domainTreeNodes = [];

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#render();
        this.#scheduleInitialLoad();
    }

    /**
     * Initialize component DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
        this.#scheduleInitialLoad();
    }

    /**
     * Disconnect canvas observers.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        this.#resizeObserver?.disconnect();
        cancelAnimationFrame(this.#cameraAnimationFrame);
    }

    /**
     * Load records once after the component has context.
     *
     * @returns {void}
     */
    #scheduleInitialLoad() {
        if (!this.#api || this.#loadScheduled || this.#output) {
            return;
        }
        this.#loadScheduled = true;
        queueMicrotask(() => this.#showRecords());
    }

    /**
     * List graph records for the current scope and view.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after list call.
     */
    async #showRecords(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        this.#readControls();
        const result = await this.#api.knowledgeShow({
            scope: this.#scope,
            mode: "all"
        }, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#output = result;
        this.#ingestGraph(result.data);
        this.#render();
    }

    /**
     * Search graph records.
     *
     * @returns {Promise<void>} Resolves after query call.
     */
    async #queryRecords() {
        if (!this.#api) {
            return;
        }
        this.#readControls();
        if (!this.#query) {
            this.#applyFilters();
            return;
        }
        const result = await this.#api.knowledgeQuery({
            q: this.#query,
            scope: this.#scope,
            limit: "120",
            explain: "true"
        });
        this.#state?.setLastResult(result);
        this.#output = result;
        this.#ingestGraph(result.data);
        this.#render();
    }

    /**
     * Load pending delta review.
     *
     * @returns {Promise<void>} Resolves after delta review.
     */
    async #reviewDeltas() {
        if (!this.#api) {
            return;
        }
        this.#readControls();
        const result = await this.#api.knowledgeDeltas({
            scope: this.#scope,
            limit: "80",
            status: "pending"
        }, { forceRefresh: true });
        this.#state?.setLastResult(result);
        this.#output = result;
        this.#ingestGraph(result.data);
        this.#render();
    }

    /**
     * Store normalized graph data and refresh derived nodes.
     *
     * @param {unknown} data Command data.
     * @returns {void}
     */
    #ingestGraph(data) {
        const graph = this.#collectGraph(data);
        this.#records = graph.records;
        this.#relations = graph.relations;
        if (this.#domain !== "all" && !this.#domains().some(domain => domain === this.#domain || domain.startsWith(`${this.#domain}.`))) {
            this.#domain = "all";
        }
        this.#selectedNodeId = "";
        this.#selectedRelationId = "";
        this.#regionNodeIds.clear();
        this.#regionEdgeIds.clear();
        this.#regionPositions.clear();
        this.#needsViewportFit = true;
        this.#prepareGraph();
    }

    /**
     * Read form controls into component state.
     *
     * @returns {void}
     */
    #readControls() {
        this.#scope = this.querySelector("[data-role='kg-scope']")?.value || this.#scope;
        const selectedModes = [...this.querySelectorAll("[data-filter-kind='kg-mode']:checked")]
            .map(input => input.value);
        this.#mode = selectedModes.length === 1 ? selectedModes[0] : "all";
        this.#query = this.querySelector("[data-role='kg-query']")?.value.trim() || "";
    }

    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        this.innerHTML = `
            <section class="page-surface knowledge-console">
                <div class="structure-layout knowledge-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.#renderDomainTree()}
                        </div>
                    </aside>
                    <main class="structure-content knowledge-content">
                        <div class="content-head graph-toolbar">
                            <input class="graph-search-input" aria-label="Buscar en el grafo" data-role="kg-query" value="${escapeHtml(this.#query)}" placeholder="Filtrar o buscar en el grafo">
                            <details class="action-menu filter-menu knowledge-filter-menu" ${this.#filtersOpen ? "open" : ""}>
                                <summary class="compact-action">${icon("filter")}<span>Filtros</span></summary>
                                <div class="action-menu-panel filter-menu-panel">
                                    <header class="knowledge-filter-heading">
                                        <strong>Vista del grafo</strong>
                                        <small>Ajusta el alcance y el contenido visible.</small>
                                    </header>
                                    <label class="knowledge-filter-control">
                                        <span>Alcance</span>
                                        <select data-role="kg-scope">
                                            <option value="global" ${this.#scope === "global" ? "selected" : ""}>Global</option>
                                            <option value="local" ${this.#scope === "local" ? "selected" : ""}>Local</option>
                                        </select>
                                    </label>
                                    <fieldset class="checkbox-filter-group">
                                        <legend>Contenido visible</legend>
                                        <div class="knowledge-filter-options">
                                            <label><input type="checkbox" data-filter-kind="kg-mode" value="entities" ${this.#mode === "all" || this.#mode === "entities" ? "checked" : ""}><span>Entidades</span></label>
                                            <label><input type="checkbox" data-filter-kind="kg-mode" value="classes" ${this.#mode === "all" || this.#mode === "classes" ? "checked" : ""}><span>Clases</span></label>
                                        </div>
                                    </fieldset>
                                </div>
                            </details>
                            <button data-action="query-records" class="primary-action">${icon("search")}Buscar</button>
                        </div>
                        <div class="knowledge-canvas-layout">
                            <main class="graph-viewport">
                                <button class="graph-focus-back secondary-action compact-action" data-action="clear-graph-focus" ${this.#regionNodeIds.size ? "" : "hidden"}>
                                    ${icon("chevronRight")} Atrás
                                </button>
                                <canvas class="knowledge-graph-canvas" data-role="knowledge-canvas" aria-label="Grafo de conocimiento"></canvas>
                                ${this.#renderCanvasEmptyState()}
                            </main>
                            <aside class="graph-detail-list">
                                ${this.#renderDetails()}
                            </aside>
                        </div>
                    </main>
                </div>
            </section>
        `;
        this.#bindEvents();
        this.#configureDomainTree();
        this.#bindCanvas();
    }

    /**
     * Render an empty overlay only when there are no visible nodes.
     *
     * @returns {string} HTML.
     */
    #renderCanvasEmptyState() {
        if (this.#nodes.length || this.#records.length || this.#relations.length) {
            return "";
        }
        return `
            <div class="knowledge-empty-state canvas-empty">
                ${icon("graph")}
                <h2>${this.#output?.ok === false ? "No se pudo consultar" : "Cargando grafo"}</h2>
                <p>${escapeHtml(this.#output?.error || this.#output?.stderr || "Los nodos apareceran aqui.")}</p>
            </div>
        `;
    }

    /**
     * Render the domain tree used to scope the graph.
     *
     * @returns {string} HTML.
     */
    #renderDomainTree() {
        const root = { label: "Todo el conocimiento", path: "all", children: new Map() };
        this.#domains().forEach(domain => {
            const parts = this.#domainParts(domain);
            let node = root;
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                if (!node.children.has(part)) {
                    node.children.set(part, { label: part, path, children: new Map() });
                }
                node = node.children.get(part);
            });
        });
        const children = this.#knowledgeTreeNodes([...root.children.values()]);
        this.#domainTreeNodes = [{
            id: "all",
            path: "all",
            label: "Todo el conocimiento",
            icon: "database",
            count: this.#records.length + this.#relations.length,
            children,
            actions: []
        }];
        return `<brain-structure-tree data-role="knowledge-domain-tree"></brain-structure-tree>`;
    }

    /**
     * Convert parsed Knowledge domains into shared tree nodes.
     *
     * @param {object[]} nodes Source domain nodes.
     * @returns {object[]} Shared tree nodes.
     */
    #knowledgeTreeNodes(nodes) {
        return nodes
            .map(node => {
                const children = this.#knowledgeTreeNodes([...node.children.values()]);
                return {
                    id: node.path,
                    path: node.path,
                    label: node.label,
                    color: this.#domainColor(node.path),
                    count: this.#countRecordsInDomain(node.path),
                    children,
                    actions: []
                };
            })
            .sort((left, right) => left.label.localeCompare(right.label));
    }

    /**
     * Configure the shared tree with Knowledge graph actions.
     *
     * @returns {void}
     */
    #configureDomainTree() {
        const treeElement = this.querySelector("[data-role='knowledge-domain-tree']");
        if (!treeElement) {
            return;
        }
        treeElement.model = {
            nodes: this.#domainTreeNodes,
            selectedPath: this.#domain,
            expandedPaths: this.#expandedDomains,
            toggleOnBranchSelect: true,
            title: "Conocimiento",
            toolbarActions: [
                { id: "refresh-graph", label: "Actualizar grafo", icon: "refresh" },
                { id: "review-deltas", label: "Revisar deltas", icon: "graph" },
                { id: "fit-graph", label: "Centrar canvas", icon: "filter" }
            ],
            defaultBranchIcon: "folder",
            defaultLeafIcon: "document"
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onDomainTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onDomainTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onDomainTreeAction(event));
    }

    /**
     * Scope the graph to a selected domain.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onDomainTreeSelected(event) {
        if (event.detail.branch && event.detail.clickedCaret) {
            return;
        }
        this.#domain = event.detail.path || "all";
        this.#applyFilters();
    }

    /**
     * Run one global Knowledge tree action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onDomainTreeToolbarAction(event) {
        if (event.detail.action === "refresh-graph") {
            this.#showRecords(true);
        } else if (event.detail.action === "review-deltas") {
            this.#reviewDeltas();
        } else if (event.detail.action === "fit-graph") {
            this.#needsViewportFit = true;
            this.#drawCanvas();
        }
    }

    /**
     * Scope the graph from a domain contextual action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onDomainTreeAction(event) {
        if (!event.detail.node?.path) {
            return;
        }
        this.#domain = event.detail.node.path;
        this.#applyFilters();
    }

    /**
     * Render recursive domain rows.
     *
     * @param {object[]} nodes Domain nodes.
     * @param {number} depth Tree depth.
     * @param {string} filter Text filter.
     * @returns {string} HTML.
     */
    #renderDomainChildren(nodes, depth, filter) {
        return nodes
            .filter(node => !filter || node.path.toLowerCase().includes(filter))
            .map(node => {
                const children = [...node.children.values()];
                const expanded = this.#expandedDomains.has(node.path);
                const count = this.#countRecordsInDomain(node.path);
                return `
                    <div class="tree-node-wrap">
                        <button class="tree-node ${this.#domain === node.path ? "is-active" : ""}" style="--tree-depth: ${depth}" data-action="select-domain" data-domain-path="${escapeHtml(node.path)}">
                            <span class="tree-caret">${children.length ? icon(expanded ? "chevronDown" : "chevronRight") : ""}</span>
                            ${icon(children.length ? "folder" : "document")}
                            <span>${escapeHtml(node.label)}</span>
                            <small>${escapeHtml(String(count))}</small>
                        </button>
                        ${expanded && children.length ? `<div class="tree-children">${this.#renderDomainChildren(children, depth + 1, filter)}</div>` : ""}
                    </div>
                `;
            }).join("");
    }

    /**
     * Render the graph inspector.
     *
     * @returns {string} HTML.
     */
    #renderDetails() {
        const selectedRelation = this.#edges.find(edge => edge.id === this.#selectedRelationId);
        if (selectedRelation) {
            return this.#renderRelationDetails(selectedRelation);
        }
        const selected = this.#nodes.find(node => node.id === this.#selectedNodeId);
        if (selected) {
            return this.#renderNodeDetails(selected);
        }
        const domains = this.#domains();
        return `
            <div class="content-head">
                <strong>Inspector</strong>
                <span>${escapeHtml(String(this.#nodes.length))} nodos · ${escapeHtml(String(this.#edges.length))} relaciones</span>
            </div>
            <div class="node-inspector scroll-list">
                <p>Selecciona un nodo o una relacion del canvas. Los nodos se arrastran; el lienzo acepta pan y zoom.</p>
                <div class="source-chip-row">
                    ${domains.slice(0, 12).map(domain => `<span>${escapeHtml(domain)}</span>`).join("")}
                </div>
            </div>
        `;
    }

    /**
     * Render entity/class node details.
     *
     * @param {object} selected Selected graph node.
     * @returns {string} HTML.
     */
    #renderNodeDetails(selected) {
        return `
            <div class="content-head">
                <strong>${escapeHtml(selected.label)}</strong>
                <span>${escapeHtml(selected.domain)}</span>
            </div>
            <div class="node-inspector scroll-list">
                <dl>
                    <dt>Contexto</dt><dd>${escapeHtml(selected.context)}</dd>
                    <dt>Dominio</dt><dd>${escapeHtml(selected.domain)}</dd>
                    <dt>Fuente</dt><dd>${escapeHtml(selected.source)}</dd>
                    <dt>Clase sugerida</dt><dd>${escapeHtml(selected.classHint || "-")}</dd>
                    <dt>Confianza</dt><dd>${escapeHtml(String(selected.confidence || "-"))}</dd>
                </dl>
                <p>${escapeHtml(selected.description || "Sin descripcion disponible.")}</p>
                ${this.#renderRelatedNodes(selected)}
            </div>
        `;
    }

    /**
     * Render relation edge details.
     *
     * @param {object} relation Selected relation edge.
     * @returns {string} HTML.
     */
    #renderRelationDetails(relation) {
        return `
            <div class="content-head">
                <strong>Relacion</strong>
                <span>${escapeHtml(relation.label)}</span>
            </div>
            <div class="node-inspector relation-inspector scroll-list">
                <dl>
                    <dt>Nombre</dt><dd>${escapeHtml(relation.label)}</dd>
                    <dt>Origen</dt><dd>${escapeHtml(relation.fromLabel)}</dd>
                    <dt>Destino</dt><dd>${escapeHtml(relation.toLabel)}</dd>
                    <dt>Contexto</dt><dd>${escapeHtml(relation.context)}</dd>
                    <dt>Dominio</dt><dd>${escapeHtml(relation.domain)}</dd>
                    <dt>Fuente</dt><dd>${escapeHtml(relation.source)}</dd>
                    <dt>Confianza</dt><dd>${escapeHtml(String(relation.confidence || "-"))}</dd>
                </dl>
                <p>${escapeHtml(relation.description || "Relacion detectada por el facade CLI.")}</p>
                <div class="graph-list">
                    ${[relation.from, relation.to].map(nodeId => {
                        const node = this.#nodes.find(item => item.id === nodeId);
                        return node ? `
                            <button class="graph-list-item" data-action="select-node" data-node-id="${escapeHtml(node.id)}">
                                <span class="activity-dot" style="background: ${escapeHtml(node.color)}"></span>
                                <strong>${escapeHtml(node.label)}</strong>
                            </button>
                        ` : "";
                    }).join("")}
                </div>
            </div>
        `;
    }

    /**
     * Render related node labels for the selected node.
     *
     * @param {object} selected Selected graph node.
     * @returns {string} HTML.
     */
    #renderRelatedNodes(selected) {
        const related = this.#edges
            .filter(edge => edge.from === selected.id || edge.to === selected.id)
            .slice(0, 10);
        if (!related.length) {
            return "";
        }
        return `
            <h2>Relaciones visibles</h2>
            <div class="graph-list">
                ${related.map(edge => {
                    const opposite = this.#nodes.find(node => node.id === (edge.from === selected.id ? edge.to : edge.from));
                    return opposite ? `
                        <button class="graph-list-item" data-action="select-relation" data-relation-id="${escapeHtml(edge.id)}">
                            <span class="activity-dot" style="background: ${escapeHtml(opposite.color)}"></span>
                            <strong>${escapeHtml(edge.label)} - ${escapeHtml(opposite.label)}</strong>
                        </button>
                    ` : "";
                }).join("")}
            </div>
        `;
    }

    /**
     * Convert command data to normalized graph records.
     *
     * @param {unknown} data Command data.
     * @returns {{records: object[], relations: object[]}} Graph data.
     */
    #collectGraph(data) {
        const relationItems = this.#relationDataArray(data);
        const relations = relationItems.map((item, index) => this.#relationFromItem(item, index)).filter(Boolean);
        const nodeItems = this.#nodeDataArray(data);
        const records = nodeItems.map((item, index) => this.#recordFromItem(item, index)).filter(record => record.label);

        return { records, relations };
    }

    /**
     * Return arrays that should become nodes.
     *
     * @param {unknown} data Command data.
     * @returns {Array} Raw node array.
     */
    #nodeDataArray(data) {
        if (Array.isArray(data)) {
            return this.#withVisualType(data, this.#mode === "classes" ? "class" : "entity");
        }
        if (!data || typeof data !== "object") {
            return [];
        }
        if (this.#mode === "all") {
            const entityItems = this.#withVisualType(data.entities || data.nodes || [], "entity");
            const classItems = this.#withVisualType(data.classes || [], "class");
            const mixedItems = this.#withVisualType(data.results || data.matches || [], "entity");
            const combinedItems = [...entityItems, ...classItems, ...mixedItems];
            if (combinedItems.length) {
                return combinedItems;
            }
        }
        if (this.#mode === "classes" && Array.isArray(data.classes)) {
            return this.#withVisualType(data.classes, "class");
        }
        if (Array.isArray(data.entities)) {
            const entities = this.#mode === "entities"
                ? data.entities.filter(item => !this.#looksLikeClass(item))
                : data.entities;
            return this.#withVisualType(entities, "entity");
        }
        if (Array.isArray(data.nodes)) {
            const nodes = this.#mode === "entities"
                ? data.nodes.filter(item => !this.#looksLikeClass(item))
                : data.nodes;
            return this.#withVisualType(nodes, "entity");
        }
        if (Array.isArray(data.results)) {
            return this.#withVisualType(
                this.#mode === "entities" ? data.results.filter(item => !this.#looksLikeClass(item)) : data.results,
                "entity"
            );
        }
        if (Array.isArray(data.matches)) {
            return this.#withVisualType(
                this.#mode === "entities" ? data.matches.filter(item => !this.#looksLikeClass(item)) : data.matches,
                "entity"
            );
        }
        return Object.values(data)
            .filter(value => Array.isArray(value))
            .flat()
            .filter(item => !this.#looksLikeRelation(item))
            .map(item => this.#withVisualType([item], this.#looksLikeClass(item) ? "class" : "entity")[0]);
    }

    /**
     * Attach UI-only graph type metadata to raw records.
     *
     * @param {Array} items Raw records.
     * @param {"entity"|"class"} visualType Visual node type.
     * @returns {Array} Records carrying visual type.
     */
    #withVisualType(items, visualType) {
        if (!Array.isArray(items)) {
            return [];
        }
        return items.map(item => {
            if (!item || typeof item !== "object") {
                return item;
            }
            return {
                ...item,
                __visualType: visualType
            };
        });
    }

    /**
     * Return arrays that should become edges.
     *
     * @param {unknown} data Command data.
     * @returns {Array} Raw relation array.
     */
    #relationDataArray(data) {
        if (!data || typeof data !== "object") {
            return [];
        }
        if (Array.isArray(data.relations)) {
            return data.relations;
        }
        if (Array.isArray(data.edges)) {
            return data.edges;
        }
        if (Array.isArray(data.links)) {
            return data.links;
        }
        return Object.values(data)
            .filter(value => Array.isArray(value))
            .flat()
            .filter(item => this.#looksLikeRelation(item));
    }

    /**
     * Convert one item into a graph node record.
     *
     * @param {unknown} item Raw item.
     * @param {number} index Fallback index.
     * @returns {object} Node record.
     */
    #recordFromItem(item, index) {
        const label = this.#itemLabel(item, index);
        const sourcePath = String(item?.source_path || item?.path || item?.source || "");
        const domain = this.#domainFromRecord(item, sourcePath);
        const entityId = item?.entity_id ?? item?.id ?? "";
        return {
            id: String(entityId || this.#nodeId(domain, label, index)),
            label,
            kind: "node",
            visualType: this.#looksLikeClass(item) ? "class" : (item?.__visualType || "entity"),
            context: this.#contextFromRecord(item, sourcePath),
            classHint: String(item?.entity_class || item?.class || item?.type || item?.kind || ""),
            domain,
            entityId: String(entityId),
            source: sourcePath || String(item?.source_type || item?.source_title || "knowledge"),
            description: String(item?.description || item?.excerpt || item?.text || ""),
            confidence: item?.confidence ?? item?.score ?? "",
            raw: item
        };
    }

    /**
     * Convert one relation payload into an edge record.
     *
     * @param {unknown} item Raw item.
     * @param {number} index Fallback index.
     * @returns {object|null} Relation record.
     */
    #relationFromItem(item, index) {
        if (!item || typeof item !== "object") {
            return null;
        }
        const sourcePath = String(item?.source_path || item?.path || item?.source_file || item?.source || "");
        const domain = this.#domainFromRecord(item, sourcePath);
        const fromLabel = String(item?.subject_name || item?.source_name || item?.source_label || item?.subject || item?.from || item?.head || item?.source || item?.entity || `Origen ${index + 1}`);
        const toLabel = String(item?.object_name || item?.target_name || item?.target_label || item?.object || item?.to || item?.tail || item?.target || item?.related || `Destino ${index + 1}`);
        const label = String(item?.relation || item?.predicate || item?.label || item?.type || item?.kind || "relacion");
        const fromEntityId = item?.subject_entity_id ?? item?.source_entity_id ?? item?.from_entity_id ?? item?.head_entity_id ?? "";
        const toEntityId = item?.object_entity_id ?? item?.target_entity_id ?? item?.to_entity_id ?? item?.tail_entity_id ?? "";
        return {
            id: String(item?.id || `relation:${domain}:${fromLabel}:${label}:${toLabel}:${index}`),
            kind: "relation",
            label,
            fromLabel,
            toLabel,
            from: String(fromEntityId || this.#nodeId(domain, fromLabel)),
            to: String(toEntityId || this.#nodeId(domain, toLabel)),
            fromEntityId: String(fromEntityId),
            toEntityId: String(toEntityId),
            fromClass: String(item?.subject_class || item?.source_class || item?.from_class || ""),
            toClass: String(item?.object_class || item?.target_class || item?.to_class || ""),
            domain,
            context: this.#contextFromRecord(item, sourcePath),
            source: sourcePath || String(item?.source_type || item?.source_title || "knowledge"),
            description: String(item?.description || item?.excerpt || item?.text || ""),
            confidence: item?.confidence ?? item?.score ?? "",
            raw: item
        };
    }

    /**
     * Return whether a payload appears to represent an edge.
     *
     * @param {unknown} item Raw item.
     * @returns {boolean} True when relation-like.
     */
    #looksLikeRelation(item) {
        return Boolean(item && typeof item === "object" && (
            ("subject" in item && "object" in item) ||
            ("source" in item && "target" in item) ||
            ("from" in item && "to" in item) ||
            ("head" in item && "tail" in item)
        ));
    }

    /**
     * Return whether a payload appears to represent a class node.
     *
     * @param {unknown} item Raw item.
     * @returns {boolean} True when class-like.
     */
    #looksLikeClass(item) {
        if (!item || typeof item !== "object") {
            return false;
        }
        const marker = String(
            item.entity_type || item.node_type || item.type || item.kind || item.category || item.entity_class || item.class || ""
        ).toLowerCase();
        const identifier = String(item.entity_id || item.id || "").toLowerCase();
        return marker === "cls"
            || marker === "class"
            || marker === "clase"
            || /^cls[:_-]/.test(identifier);
    }

    /**
     * Resolve one readable item label.
     *
     * @param {unknown} item Raw item.
     * @param {number} index Fallback index.
     * @returns {string} Label.
     */
    #itemLabel(item, index) {
        if (typeof item === "string") {
            return item;
        }
        if (item && typeof item === "object") {
            return item.canonical_name || item.name || item.title || item.entity || item.id || `Nodo ${index + 1}`;
        }
        return String(item || "");
    }

    /**
     * Resolve a context label from graph metadata.
     *
     * @param {object} item Raw item.
     * @param {string} sourcePath Source path.
     * @returns {string} Context label.
     */
    #contextFromRecord(item, sourcePath) {
        if (sourcePath.includes("/")) {
            const parts = sourcePath.split("/").filter(Boolean);
            const memoryIndex = parts.indexOf("memory");
            if (memoryIndex >= 0) {
                return parts.slice(memoryIndex, -1).join("/") || "memory";
            }
            return parts.slice(0, -1).join("/") || parts[0] || "knowledge";
        }
        return String(item?.source_type || item?.domain || item?.kind || "knowledge");
    }

    /**
     * Resolve a domain from graph metadata.
     *
     * @param {object} item Raw item.
     * @param {string} sourcePath Source path.
     * @returns {string} Domain label.
     */
    #domainFromRecord(item, sourcePath) {
        if (sourcePath.includes("/")) {
            const parts = sourcePath.split("/").filter(Boolean);
            const memoryIndex = parts.indexOf("memory");
            if (memoryIndex >= 0 && parts[memoryIndex + 1]) {
                const domainParts = parts.slice(memoryIndex + 1, -1);
                return domainParts.length ? domainParts.join(".") : parts[memoryIndex + 1];
            }
            return parts[0] || "knowledge";
        }
        return String(item?.domain || item?.source_domain || item?.source_type || "knowledge");
    }

    /**
     * Prepare graph nodes and edges from current records and filters.
     *
     * @returns {void}
     */
    #prepareGraph() {
        const records = this.#filteredRecords();
        const domainGroups = new Map();
        records.forEach(record => {
            if (!domainGroups.has(record.domain)) {
                domainGroups.set(record.domain, []);
            }
            domainGroups.get(record.domain).push(record);
        });
        const domains = Array.from(domainGroups.keys()).sort();
        this.#nodes = records.map((record, index) => this.#nodeFromRecord(record, index, domains, domainGroups));
        this.#edges = this.#edgesFromRelations(records);
        this.#applyConnectivitySizing();
        this.#layoutGraphByNeighbors();
        this.#reconcileRegionEdges();
    }

    /**
     * Convert one record into a graph node.
     *
     * @param {object} record Graph record.
     * @param {number} index Global index.
     * @param {string[]} domains Domain list.
     * @param {Map<string, object[]>} domainGroups Grouped records.
     * @returns {object} Graph node.
     */
    #nodeFromRecord(record, index, domains, domainGroups) {
        const domainIndex = Math.max(domains.indexOf(record.domain), 0);
        const group = domainGroups.get(record.domain) || [];
        const localIndex = Math.max(group.findIndex(item => item.id === record.id), 0);
        const domainAngle = (Math.PI * 2 * domainIndex) / Math.max(domains.length, 1);
        const localAngle = domainAngle + (localIndex / Math.max(group.length, 1)) * 0.96;
        const radius = 130 + (localIndex % 11) * 24 + domainIndex * 10;
        return {
            ...record,
            x: Math.cos(localAngle) * radius,
            y: Math.sin(localAngle) * radius,
            radius: this.#mode === "classes" ? 15 : 11,
            color: this.#domainColor(record.domain),
            expanded: false
        };
    }

    /** Return a unique root hue and inherited tonal variation for descendants. */
    #domainColor(domain) {
        const normalized = String(domain || "knowledge").toLowerCase();
        const parts = this.#domainParts(normalized);
        const roots = [...new Set(this.#domains().map(item => this.#domainParts(item)[0]).filter(Boolean))].sort();
        const rootIndex = Math.max(roots.indexOf(parts[0]), 0);
        const hue = Math.round((206 + (rootIndex * 137.508)) % 360);
        if (parts.length <= 1) {
            return `hsl(${hue} 84% 58%)`;
        }
        const hash = [...normalized].reduce((total, character) => ((total * 31) + character.charCodeAt(0)) >>> 0, 0);
        const saturation = 68 + (hash % 17);
        const lightness = 52 + (((parts.length * 7) + (hash % 19)) % 25);
        return `hsl(${hue} ${saturation}% ${lightness}%)`;
    }

    /**
     * Build edges from relation data returned by the CLI facade.
     *
     * @param {object[]} records Current node records.
     * @returns {object[]} Edges.
     */
    #edgesFromRelations(records) {
        const nodeById = new Map(records.map(record => [record.id, record]));
        const nodeByLabel = new Map(records.map(record => [`${record.domain}:${record.label}`.toLowerCase(), record]));
        const domainRelations = this.#relations.filter(relation => this.#domainMatches(relation.domain));
        const edges = domainRelations
            .map((relation, index) => {
                const from = this.#nodeForRelationEnd(nodeById, nodeByLabel, relation, "from");
                const to = this.#nodeForRelationEnd(nodeById, nodeByLabel, relation, "to");
                if (!from || !to) {
                    return null;
                }
                return {
                    ...relation,
                    id: relation.id || `relation-edge-${index}`,
                    from: from.id,
                    to: to.id
                };
            })
            .filter(Boolean);
        return edges;
    }

    /**
     * Resolve a relation endpoint against visible node records.
     *
     * @param {Map<string, object>} nodeById Visible nodes by id.
     * @param {Map<string, object>} nodeByLabel Visible nodes by domain and label.
     * @param {object} relation Relation record.
     * @param {"from"|"to"} side Endpoint side.
     * @returns {object|null} Matching node.
     */
    #nodeForRelationEnd(nodeById, nodeByLabel, relation, side) {
        const id = String(relation[side] || "");
        const entityId = side === "from" ? relation.fromEntityId : relation.toEntityId;
        const label = side === "from" ? relation.fromLabel : relation.toLabel;
        const classHint = side === "from" ? relation.fromClass : relation.toClass;
        return nodeById.get(id) ||
            nodeById.get(String(entityId || "")) ||
            nodeByLabel.get(`${relation.domain}:${label}`.toLowerCase()) ||
            nodeByLabel.get(`${relation.domain}:${classHint}`.toLowerCase()) ||
            null;
    }

    /**
     * Position nodes through neighbor expansion when relations exist, otherwise by domain grid.
     *
     * @returns {void}
     */
    #layoutGraphByNeighbors() {
        const linkedIds = new Set(this.#edges.flatMap(edge => [edge.from, edge.to]));
        const linkedNodes = this.#nodes.filter(node => linkedIds.has(node.id));
        const freeNodes = this.#nodes.filter(node => !linkedIds.has(node.id));
        if (linkedNodes.length) {
            this.#layoutConnectedNodes(linkedNodes, 0);
        }
        const startY = linkedNodes.length ? 420 : 0;
        this.#layoutDomainGrid(freeNodes, startY);
    }

    /**
     * Expand connected components by neighbor depth.
     *
     * @param {object[]} nodes Connected nodes.
     * @param {number} startY Vertical offset.
     * @returns {void}
     */
    #layoutConnectedNodes(nodes, startY) {
        const byId = new Map(nodes.map(node => [node.id, node]));
        const adjacency = this.#adjacencyMap(byId);
        const visited = new Set();
        let componentIndex = 0;
        nodes.forEach(node => {
            if (visited.has(node.id)) {
                return;
            }
            const component = this.#componentFromNode(node.id, adjacency, visited);
            const offsetX = (componentIndex % 3) * 620;
            const offsetY = startY + Math.floor(componentIndex / 3) * 460;
            this.#positionComponent(component, adjacency, byId, offsetX, offsetY);
            componentIndex += 1;
        });
    }

    /**
     * Build adjacency from visible edges.
     *
     * @param {Map<string, object>} byId Visible nodes by id.
     * @returns {Map<string, Set<string>>} Adjacency map.
     */
    #adjacencyMap(byId) {
        const adjacency = new Map([...byId.keys()].map(id => [id, new Set()]));
        this.#edges.forEach(edge => {
            if (!byId.has(edge.from) || !byId.has(edge.to)) {
                return;
            }
            adjacency.get(edge.from).add(edge.to);
            adjacency.get(edge.to).add(edge.from);
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
    #componentFromNode(rootId, adjacency, visited) {
        const queue = [rootId];
        const component = [];
        visited.add(rootId);
        while (queue.length) {
            const current = queue.shift();
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
     * @returns {void}
     */
    #positionComponent(component, adjacency, byId, offsetX, offsetY) {
        const rootId = [...component].sort((left, right) => (adjacency.get(right)?.size || 0) - (adjacency.get(left)?.size || 0))[0];
        const levels = this.#neighborLevels(rootId, adjacency);
        [...levels.entries()].forEach(([depth, ids]) => {
            const spacing = Math.max(92, 120 - depth * 8);
            ids.forEach((id, index) => {
                const node = byId.get(id);
                if (!node) {
                    return;
                }
                node.x = offsetX + depth * 190;
                node.y = offsetY + (index - (ids.length - 1) / 2) * spacing;
            });
        });
    }

    /**
     * Group neighbor ids by breadth-first depth.
     *
     * @param {string} rootId Root node id.
     * @param {Map<string, Set<string>>} adjacency Adjacency map.
     * @returns {Map<number, string[]>} Level groups.
     */
    #neighborLevels(rootId, adjacency) {
        const levels = new Map();
        const visited = new Set([rootId]);
        const queue = [{ id: rootId, depth: 0 }];
        while (queue.length) {
            const current = queue.shift();
            if (!levels.has(current.depth)) {
                levels.set(current.depth, []);
            }
            levels.get(current.depth).push(current.id);
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
     */
    #layoutDomainGrid(nodes, startY) {
        const groups = new Map();
        nodes.forEach(node => {
            if (!groups.has(node.domain)) {
                groups.set(node.domain, []);
            }
            groups.get(node.domain).push(node);
        });
        [...groups.entries()].sort(([left], [right]) => left.localeCompare(right)).forEach(([, group], groupIndex) => {
            const columns = Math.ceil(Math.sqrt(group.length));
            const offsetX = (groupIndex % 3) * 520;
            const offsetY = startY + Math.floor(groupIndex / 3) * 360;
            group.forEach((node, index) => {
                node.x = offsetX + (index % columns) * 116;
                node.y = offsetY + Math.floor(index / columns) * 94;
            });
        });
    }

    /**
     * Return records after domain, mode, and query filters.
     *
     * @returns {object[]} Filtered records.
     */
    #filteredRecords() {
        const needle = this.#query.toLowerCase();
        const visualType = this.#mode === "classes" ? "class" : this.#mode === "entities" ? "entity" : "";
        return this.#records
            .filter(record => this.#domainMatches(record.domain))
            .filter(record => !visualType || record.visualType === visualType)
            .filter(record => !needle || `${record.label} ${record.description} ${record.domain} ${record.context}`.toLowerCase().includes(needle));
    }

    /**
     * Return whether a domain is active under the selected tree node.
     *
     * @param {string} domain Domain path.
     * @returns {boolean} True when visible.
     */
    #domainMatches(domain) {
        return this.#domain === "all" || domain === this.#domain || domain.startsWith(`${this.#domain}.`);
    }

    /**
     * Return available domains from loaded records and relations.
     *
     * @returns {string[]} Domain labels.
     */
    #domains() {
        return [...new Set([
            ...this.#records.map(record => record.domain),
            ...this.#relations.map(relation => relation.domain)
        ].filter(Boolean))].sort();
    }

    /**
     * Return domain hierarchy parts.
     *
     * @param {string} domain Domain path.
     * @returns {string[]} Parts.
     */
    #domainParts(domain) {
        return String(domain || "knowledge").split(/[./\\]+/).filter(Boolean);
    }

    /**
     * Count records under one domain branch.
     *
     * @param {string} domain Domain path.
     * @returns {number} Count.
     */
    #countRecordsInDomain(domain) {
        return this.#records.filter(record => record.domain === domain || record.domain.startsWith(`${domain}.`)).length +
            this.#relations.filter(relation => relation.domain === domain || relation.domain.startsWith(`${domain}.`)).length;
    }

    /**
     * Apply local reactive filters without a new CLI call.
     *
     * @returns {void}
     */
    #applyFilters() {
        this.#readControls();
        this.#needsViewportFit = true;
        this.#prepareGraph();
        this.#render();
    }

    /**
     * Bind DOM events.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelector("[data-action='show-records']")?.addEventListener("click", () => this.#showRecords(true));
        this.querySelector("[data-action='query-records']")?.addEventListener("click", () => this.#queryRecords());
        this.querySelector("[data-action='review-deltas']")?.addEventListener("click", () => this.#reviewDeltas());
        this.querySelector("[data-action='fit-graph']")?.addEventListener("click", () => {
            this.#needsViewportFit = true;
            this.#drawCanvas();
        });
        this.querySelector("[data-action='clear-graph-focus']")?.addEventListener("click", () => {
            this.#clearGraphFocus();
        });
        this.querySelector(".filter-menu")?.addEventListener("toggle", event => {
            this.#filtersOpen = event.currentTarget.open;
        });
        this.querySelectorAll("[data-action='select-domain']").forEach(button => {
            button.addEventListener("click", () => {
                const domain = button.getAttribute("data-domain-path") || "all";
                this.#domain = domain;
                this.#resetGraphRegion();
                if (this.#expandedDomains.has(domain)) {
                    this.#expandedDomains.delete(domain);
                } else {
                    this.#expandedDomains.add(domain);
                }
                this.#applyFilters();
            });
        });
        this.querySelector("[data-role='kg-query']")?.addEventListener("input", () => {
            this.#readControls();
            this.#needsViewportFit = true;
            this.#prepareGraph();
            this.#drawCanvas();
            this.#renderInspector();
        });
        this.querySelector("[data-role='kg-query']")?.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                this.#queryRecords();
            }
        });
        this.querySelector("[data-role='kg-scope']")?.addEventListener("change", () => this.#showRecords(true));
        this.querySelectorAll("[data-filter-kind='kg-mode']").forEach(input => {
            input.addEventListener("change", () => this.#applyFilters());
        });
        this.#bindInspectorButtons();
    }

    /**
     * Bind inspector relation/node selection buttons.
     *
     * @returns {void}
     */
    #bindInspectorButtons() {
        this.querySelectorAll("[data-action='select-node']").forEach(button => {
            button.addEventListener("click", () => {
                const hadRegion = this.#regionNodeIds.size > 0;
                this.#selectedNodeId = button.getAttribute("data-node-id") || "";
                this.#selectedRelationId = "";
                this.#expandGraphRegion(this.#selectedNodeId);
                this.#completeRegionExpansion(hadRegion);
                this.#drawCanvas();
                this.#renderInspector();
            });
        });
        this.querySelectorAll("[data-action='select-relation']").forEach(button => {
            button.addEventListener("click", () => {
                const hadRegion = this.#regionNodeIds.size > 0;
                this.#selectedRelationId = button.getAttribute("data-relation-id") || "";
                this.#selectedNodeId = "";
                this.#expandGraphRegionFromEdge(this.#selectedRelationId);
                this.#completeRegionExpansion(hadRegion);
                this.#drawCanvas();
                this.#renderInspector();
            });
        });
    }

    /**
     * Bind canvas drawing and pointer interaction.
     *
     * @returns {void}
     */
    #bindCanvas() {
        const canvas = this.querySelector("[data-role='knowledge-canvas']");
        if (!(canvas instanceof HTMLCanvasElement)) {
            return;
        }
        this.#resizeObserver?.disconnect();
        this.#resizeObserver = new ResizeObserver(() => this.#drawCanvas());
        this.#resizeObserver.observe(canvas);
        canvas.addEventListener("pointerdown", event => this.#onPointerDown(event, canvas));
        canvas.addEventListener("pointermove", event => this.#onPointerMove(event, canvas));
        canvas.addEventListener("pointerup", event => this.#onPointerUp(event, canvas));
        canvas.addEventListener("pointerleave", event => this.#onPointerUp(event, canvas));
        canvas.addEventListener("wheel", event => this.#onWheel(event, canvas), { passive: false });
        requestAnimationFrame(() => this.#drawCanvas());
    }

    /**
     * Draw nodes and edges onto the canvas.
     *
     * @returns {void}
     */
    #drawCanvas() {
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
        if (this.#needsViewportFit) {
            this.#fitViewport(rect);
        }
        this.#updateRenderFrustum(rect);
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        context.clearRect(0, 0, rect.width, rect.height);
        this.#applyConnectivitySizing(this.#focusGraph());
        context.translate((rect.width / 2) + this.#viewport.x, (rect.height / 2) + this.#viewport.y);
        context.scale(this.#viewport.scale, this.#viewport.scale);
        this.#drawEdges(context);
        this.#drawNodes(context);
    }

    /**
     * Fit graph bounds into the canvas viewport.
     *
     * @param {DOMRect} rect Canvas bounds.
     * @returns {void}
     */
    #fitViewport(rect) {
        const focus = this.#focusGraph();
        if (focus) {
            this.#layoutFocusedRegion(focus);
        }
        const visibleNodes = focus
            ? this.#nodes.filter(node => focus.nodeIds.has(node.id))
            : this.#nodes;
        if (!visibleNodes.length) {
            this.#viewport = { x: 0, y: 0, scale: 1 };
            this.#needsViewportFit = false;
            return;
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
        const scale = Math.min(maximumScale, Math.max(0.18, Math.min((rect.width - 72) / width, (rect.height - 72) / height)));
        this.#viewport = {
            x: -((bounds.minX + bounds.maxX) / 2) * scale,
            y: -((bounds.minY + bounds.maxY) / 2) * scale,
            scale
        };
        this.#needsViewportFit = false;
    }

    /** Compute the current canvas viewport in graph coordinates. */
    #updateRenderFrustum(rect) {
        const scale = Math.max(this.#viewport.scale, 0.0001);
        const halfWidth = rect.width / (2 * scale);
        const halfHeight = rect.height / (2 * scale);
        const centerX = -this.#viewport.x / scale;
        const centerY = -this.#viewport.y / scale;
        const padding = 14 / scale;
        this.#renderFrustum = {
            left: centerX - halfWidth - padding,
            right: centerX + halfWidth + padding,
            top: centerY - halfHeight - padding,
            bottom: centerY + halfHeight + padding,
            centerX,
            centerY,
            radius: Math.hypot(halfWidth, halfHeight) + padding
        };
    }

    /** Return whether a node circle intersects the graph-space viewport. */
    #nodeIntersectsRenderFrustum(node) {
        const frustum = this.#renderFrustum;
        if (!frustum) {
            return true;
        }
        const radius = node.radius + (20 / Math.max(this.#viewport.scale, 0.0001));
        return node.x + radius >= frustum.left
            && node.x - radius <= frustum.right
            && node.y + radius >= frustum.top
            && node.y - radius <= frustum.bottom;
    }

    /** Apply endpoint, circumscribed-radius, and exact edge culling. */
    #edgeIntersectsRenderFrustum(from, to) {
        const frustum = this.#renderFrustum;
        if (!frustum) {
            return true;
        }
        if (this.#nodeIntersectsRenderFrustum(from) || this.#nodeIntersectsRenderFrustum(to)) {
            return true;
        }
        const distance = this.#pointToSegmentDistance(
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
        return this.#segmentIntersectsFrustum(from.x, from.y, to.x, to.y, frustum);
    }

    /** Test a segment against an axis-aligned viewport using Liang-Barsky. */
    #segmentIntersectsFrustum(x1, y1, x2, y2, frustum) {
        const deltaX = x2 - x1;
        const deltaY = y2 - y1;
        const p = [-deltaX, deltaX, -deltaY, deltaY];
        const q = [x1 - frustum.left, frustum.right - x1, y1 - frustum.top, frustum.bottom - y1];
        let minimum = 0;
        let maximum = 1;
        for (let index = 0; index < 4; index += 1) {
            if (p[index] === 0) {
                if (q[index] < 0) {
                    return false;
                }
                continue;
            }
            const ratio = q[index] / p[index];
            if (p[index] < 0) {
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
    #layoutFocusedRegion(focus) {
        const focusedNodes = this.#nodes.filter(node => focus.nodeIds.has(node.id));
        if (!focusedNodes.length) {
            return;
        }
        focusedNodes.forEach(node => {
            const position = this.#regionPositions.get(node.id);
            if (position) {
                node.x = position.x;
                node.y = position.y;
            }
        });
        const newNodes = focusedNodes.filter(node => !this.#regionPositions.has(node.id));
        if (!newNodes.length) {
            return;
        }
        const selectedPosition = this.#regionPositions.get(this.#selectedNodeId);
        const anchor = selectedPosition || this.#regionCentroid();
        if (!this.#regionPositions.size) {
            const selectedIndex = newNodes.findIndex(node => node.id === this.#selectedNodeId);
            const centerIndex = selectedIndex >= 0 ? selectedIndex : 0;
            const [center] = newNodes.splice(centerIndex, 1);
            center.x = 0;
            center.y = 0;
            this.#regionPositions.set(center.id, { x: 0, y: 0 });
        }
        const baseSlot = this.#regionPositions.size;
        newNodes.forEach((node, index) => {
            const slot = baseSlot + index;
            const angle = (slot * 2.399963229728653) - (Math.PI / 2);
            const radius = 120 + (Math.floor(slot / 7) * 75);
            node.x = anchor.x + (Math.cos(angle) * radius);
            node.y = anchor.y + (Math.sin(angle) * radius);
            this.#regionPositions.set(node.id, { x: node.x, y: node.y });
        });
    }

    /** Return the centroid of persisted region positions. */
    #regionCentroid() {
        const positions = [...this.#regionPositions.values()];
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
    #drawEdges(context) {
        const styles = getComputedStyle(this);
        const focus = this.#focusGraph();
        const orderedEdges = focus
            ? this.#edges.filter(edge => focus.edgeIds.has(edge.id))
            : this.#edges;
        const nodesById = new Map(this.#nodes.map(node => [node.id, node]));
        const connectivity = this.#connectivityMetrics(focus);
        orderedEdges.forEach(edge => {
            const from = nodesById.get(edge.from);
            const to = nodesById.get(edge.to);
            if (!from || !to || !this.#edgeIntersectsRenderFrustum(from, to)) {
                return;
            }
            const selected = edge.id === this.#selectedRelationId || Boolean(focus?.edgeIds.has(edge.id));
            context.save();
            context.globalAlpha = 0.92;
            context.beginPath();
            context.moveTo(from.x, from.y);
            context.lineTo(to.x, to.y);
            context.strokeStyle = selected ? styles.getPropertyValue("--primary").trim() : styles.getPropertyValue("--border-strong").trim();
            context.lineWidth = selected ? 3.2 / this.#viewport.scale : 1.2 / this.#viewport.scale;
            context.stroke();
            this.#drawEdgeArrow(context, from, to, connectivity.score(from.id));
            this.#drawEdgeLabel(context, edge, from, to, selected);
            context.restore();
        });
    }

    /** Draw a subject-to-object arrowhead immediately before the target node. */
    #drawEdgeArrow(context, from, to, sourceRank) {
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const distance = Math.hypot(dx, dy);
        if (distance < 1) return;
        const unitX = dx / distance;
        const unitY = dy / distance;
        const scale = this.#viewport.scale;
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
    #drawEdgeLabel(context, edge, from, to, selected) {
        if (!selected && this.#viewport.scale < 0.45) {
            return;
        }
        const styles = getComputedStyle(this);
        const x = (from.x + to.x) / 2;
        const y = (from.y + to.y) / 2;
        const label = this.#shortLabel(edge.label, selected ? 24 : 16);
        context.save();
        context.font = `${selected ? 700 : 650} ${10 / this.#viewport.scale}px Inter, system-ui, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        const width = context.measureText(label).width + 12;
        const height = 18 / this.#viewport.scale;
        context.fillStyle = styles.getPropertyValue("--surface").trim();
        context.strokeStyle = styles.getPropertyValue("--border").trim();
        this.#roundedRect(context, x - width / 2, y - height / 2, width, height, 8 / this.#viewport.scale);
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
    #drawNodes(context) {
        const styles = getComputedStyle(this);
        const focus = this.#focusGraph();
        const connectivity = this.#connectivityMetrics(focus);
        const degrees = connectivity.degrees;
        const maxDegree = Math.max(0, ...degrees.values());
        const orderedNodes = focus
            ? this.#nodes.filter(node => focus.nodeIds.has(node.id))
            : this.#nodes;
        orderedNodes.filter(node => this.#nodeIntersectsRenderFrustum(node)).forEach(node => {
            const selected = node.id === this.#selectedNodeId;
            const focused = selected || Boolean(focus?.nodeIds.has(node.id));
            const radius = selected ? node.radius + 5 : focused ? node.radius + 2 : node.radius;
            context.save();
            context.globalAlpha = 1;
            context.beginPath();
            context.arc(node.x, node.y, radius, 0, Math.PI * 2);
            context.fillStyle = selected ? styles.getPropertyValue("--primary").trim() : styles.getPropertyValue("--surface-strong").trim();
            context.strokeStyle = node.color;
            context.lineWidth = selected ? 3.4 / this.#viewport.scale : focused ? 2.6 / this.#viewport.scale : 1.8 / this.#viewport.scale;
            context.setLineDash(node.visualType === "class" ? [7 / this.#viewport.scale, 5 / this.#viewport.scale] : []);
            context.fill();
            context.stroke();
            if (this.#nodeLabelIsVisible(node, degrees, maxDegree, selected || focused)) {
                this.#drawNodeLabel(context, node, selected || focused);
            }
            if (selected && focus && this.#nodeCanExpand(node.id)) {
                this.#drawNodeExpansionBadge(context, node);
            }
            context.restore();
        });
    }

    /** Return the number of visible relations incident to each node. */
    #nodeDegrees(focus = null) {
        const visibleNodeIds = focus?.nodeIds || new Set(this.#nodes.map(node => node.id));
        const degrees = new Map([...visibleNodeIds].map(nodeId => [nodeId, 0]));
        this.#edges.forEach(edge => {
            if (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to)) {
                return;
            }
            degrees.set(edge.from, (degrees.get(edge.from) || 0) + 1);
            degrees.set(edge.to, (degrees.get(edge.to) || 0) + 1);
        });
        return degrees;
    }

    /** Return connectivity normalized against the maximum of the visible graph. */
    #connectivityMetrics(focus = this.#focusGraph()) {
        const degrees = this.#nodeDegrees(focus);
        const maxDegree = Math.max(1, ...degrees.values());
        return {
            degrees,
            maxDegree,
            score: nodeId => (degrees.get(nodeId) || 0) / maxDegree
        };
    }

    /** Scale node radii by connectivity while preserving readable bounds. */
    #applyConnectivitySizing(focus = null) {
        const connectivity = this.#connectivityMetrics(focus);
        const baseRadius = this.#mode === "classes" ? 14 : 10;
        const radiusRange = this.#mode === "classes" ? 16 : 13;
        this.#nodes.forEach(node => {
            const normalized = Math.sqrt(connectivity.score(node.id));
            node.radius = baseRadius + normalized * radiusRange;
        });
    }

    /** Decide whether a label belongs to the zoom-dependent connectivity tier. */
    #nodeLabelIsVisible(node, degrees, maxDegree, emphasized) {
        if (emphasized || this.#viewport.scale >= 0.78) {
            return true;
        }
        const normalizedRank = maxDegree ? (degrees.get(node.id) || 0) / maxDegree : 0;
        const zoomProgress = Math.max(0, Math.min(1, (this.#viewport.scale - 0.14) / 0.64));
        const easedTolerance = zoomProgress * zoomProgress * (3 - (2 * zoomProgress));
        const minimumRank = 0.56 * (1 - easedTolerance);
        return normalizedRank >= minimumRank;
    }

    /**
     * Return the current selected node/relation neighborhood.
     *
     * @returns {{nodeIds: Set<string>, edgeIds: Set<string>}|null} Focus ids.
     */
    #focusGraph() {
        if (!this.#regionNodeIds.size) {
            return null;
        }
        return {
            nodeIds: this.#regionNodeIds,
            edgeIds: this.#regionEdgeIds
        };
    }

    /** Return whether selecting a node can reveal neighbors outside the region. */
    #nodeCanExpand(nodeId) {
        return this.#edges.some(edge => {
            if (edge.from !== nodeId && edge.to !== nodeId) {
                return false;
            }
            const neighborId = edge.from === nodeId ? edge.to : edge.from;
            return !this.#regionNodeIds.has(neighborId);
        });
    }

    /** Draw a screen-stable expansion affordance above a selected node. */
    #drawNodeExpansionBadge(context, node) {
        const styles = getComputedStyle(this);
        const scale = this.#viewport.scale;
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
     * Add a node and its immediate neighbors to the persistent region.
     *
     * @param {string} nodeId Selected node id.
     * @returns {void}
     */
    #expandGraphRegion(nodeId) {
        if (!nodeId) {
            return;
        }
        this.#regionNodeIds.add(nodeId);
        this.#edges.forEach(edge => {
            if (edge.from !== nodeId && edge.to !== nodeId) {
                return;
            }
            this.#regionEdgeIds.add(edge.id);
            this.#regionNodeIds.add(edge.from);
            this.#regionNodeIds.add(edge.to);
        });
        this.#reconcileRegionEdges();
    }

    /** Rebuild all currently visible relations internal to the persistent region. */
    #reconcileRegionEdges() {
        this.#regionEdgeIds.clear();
        this.#edges.forEach(edge => {
            if (this.#regionNodeIds.has(edge.from) && this.#regionNodeIds.has(edge.to)) {
                this.#regionEdgeIds.add(edge.id);
            }
        });
    }

    /**
     * Add a selected relation and both endpoint neighborhoods to the region.
     *
     * @param {string} edgeId Selected edge id.
     * @returns {void}
     */
    #expandGraphRegionFromEdge(edgeId) {
        const edge = this.#edges.find(item => item.id === edgeId);
        if (!edge) {
            return;
        }
        this.#regionEdgeIds.add(edge.id);
        this.#expandGraphRegion(edge.from);
        this.#expandGraphRegion(edge.to);
    }

    /** Position additions while fitting only the first region creation. */
    #completeRegionExpansion(hadRegion) {
        const focus = this.#focusGraph();
        if (focus) {
            this.#layoutFocusedRegion(focus);
        }
        this.#needsViewportFit = !hadRegion;
    }

    /**
     * Draw a persistent node label.
     *
     * @param {CanvasRenderingContext2D} context Canvas context.
     * @param {object} node Graph node.
     * @param {boolean} selected Whether selected.
     * @returns {void}
     */
    #drawNodeLabel(context, node, selected) {
        const styles = getComputedStyle(this);
        const label = this.#shortLabel(node.label, selected ? 28 : 18);
        const fontSize = selected ? 12 : 10;
        const x = node.x;
        const y = node.y + node.radius + (14 / this.#viewport.scale);
        context.save();
        context.font = `800 ${fontSize / this.#viewport.scale}px Inter, system-ui, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.fillStyle = node.color;
        context.shadowColor = styles.getPropertyValue("--surface").trim();
        context.shadowBlur = 4 / this.#viewport.scale;
        context.lineWidth = 3 / this.#viewport.scale;
        context.fillText(label, x, y);
        context.restore();
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
    #roundedRect(context, x, y, width, height, radius) {
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
    #onPointerDown(event, canvas) {
        const point = this.#canvasPoint(event, canvas);
        const node = this.#hitTestNode(point.x, point.y);
        if (node) {
            const wasSelected = this.#selectedNodeId === node.id;
            const hadRegion = this.#regionNodeIds.size > 0;
            this.#selectedNodeId = node.id;
            this.#selectedRelationId = "";
            if (wasSelected && this.#nodeCanExpand(node.id)) {
                this.#expandGraphRegion(node.id);
                this.#completeRegionExpansion(hadRegion);
                this.#animateCameraToNode(node, hadRegion ? this.#viewport.scale : Math.max(this.#viewport.scale, 1.35));
            } else if (wasSelected && hadRegion) {
                this.#dragNode = {
                    id: node.id,
                    offsetX: point.x - node.x,
                    offsetY: point.y - node.y
                };
                canvas.setPointerCapture(event.pointerId);
                this.#drawCanvas();
            } else {
                this.#animateCameraToNode(node, hadRegion ? this.#viewport.scale : Math.max(this.#viewport.scale, 1.35));
            }
            this.#renderInspector();
            return;
        }
        const edge = this.#hitTestEdge(point.x, point.y);
        if (edge) {
            const hadRegion = this.#regionNodeIds.size > 0;
            this.#selectedRelationId = edge.id;
            this.#selectedNodeId = "";
            this.#expandGraphRegionFromEdge(edge.id);
            this.#completeRegionExpansion(hadRegion);
            this.#drawCanvas();
            this.#renderInspector();
            return;
        }
        if (this.#selectedNodeId || this.#selectedRelationId) {
            this.#selectedNodeId = "";
            this.#selectedRelationId = "";
            this.#drawCanvas();
            this.#renderInspector();
            return;
        }
        this.#panState = {
            pointerId: event.pointerId,
            clientX: event.clientX,
            clientY: event.clientY,
            startX: this.#viewport.x,
            startY: this.#viewport.y
        };
        cancelAnimationFrame(this.#cameraAnimationFrame);
        this.#cameraAnimationFrame = 0;
        canvas.setPointerCapture(event.pointerId);
    }

    /** Smoothly center one node while optionally changing the camera scale. */
    #animateCameraToNode(node, targetScale) {
        cancelAnimationFrame(this.#cameraAnimationFrame);
        this.#needsViewportFit = false;
        const start = { ...this.#viewport };
        const target = {
            x: -node.x * targetScale,
            y: -node.y * targetScale,
            scale: targetScale
        };
        const startedAt = performance.now();
        const duration = 420;
        const animate = now => {
            const progress = Math.min(1, (now - startedAt) / duration);
            const eased = 1 - Math.pow(1 - progress, 3);
            this.#viewport = {
                x: start.x + (target.x - start.x) * eased,
                y: start.y + (target.y - start.y) * eased,
                scale: start.scale + (target.scale - start.scale) * eased
            };
            this.#drawCanvas();
            if (progress < 1) {
                this.#cameraAnimationFrame = requestAnimationFrame(animate);
            } else {
                this.#cameraAnimationFrame = 0;
            }
        };
        this.#cameraAnimationFrame = requestAnimationFrame(animate);
    }

    /**
     * Move a dragged node or pan the graph.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    #onPointerMove(event, canvas) {
        if (this.#dragNode) {
            const point = this.#canvasPoint(event, canvas);
            const node = this.#nodes.find(item => item.id === this.#dragNode.id);
            if (!node) {
                return;
            }
            node.x = point.x - this.#dragNode.offsetX;
            node.y = point.y - this.#dragNode.offsetY;
            if (this.#regionNodeIds.has(node.id)) {
                this.#regionPositions.set(node.id, { x: node.x, y: node.y });
            }
            this.#drawCanvas();
            return;
        }
        if (!this.#panState) {
            return;
        }
        this.#viewport.x = this.#panState.startX + (event.clientX - this.#panState.clientX);
        this.#viewport.y = this.#panState.startY + (event.clientY - this.#panState.clientY);
        this.#drawCanvas();
    }

    /**
     * End dragging or panning.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {void}
     */
    #onPointerUp(event, canvas) {
        this.#dragNode = null;
        this.#panState = null;
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
    #onWheel(event, canvas) {
        event.preventDefault();
        cancelAnimationFrame(this.#cameraAnimationFrame);
        this.#cameraAnimationFrame = 0;
        const rect = canvas.getBoundingClientRect();
        const cursorX = event.clientX - rect.left - rect.width / 2;
        const cursorY = event.clientY - rect.top - rect.height / 2;
        const previousScale = this.#viewport.scale;
        const nextScale = Math.min(3.4, Math.max(0.14, previousScale * (event.deltaY > 0 ? 0.9 : 1.1)));
        const graphX = (cursorX - this.#viewport.x) / previousScale;
        const graphY = (cursorY - this.#viewport.y) / previousScale;
        this.#viewport.x = cursorX - graphX * nextScale;
        this.#viewport.y = cursorY - graphY * nextScale;
        this.#viewport.scale = nextScale;
        this.#needsViewportFit = false;
        this.#drawCanvas();
    }

    /**
     * Refresh the inspector without replacing the canvas.
     *
     * @returns {void}
     */
    #renderInspector() {
        const inspector = this.querySelector(".graph-detail-list");
        if (!inspector) {
            return;
        }
        inspector.innerHTML = this.#renderDetails();
        const backButton = this.querySelector("[data-action='clear-graph-focus']");
        if (backButton) {
            backButton.hidden = !this.#focusGraph();
        }
        this.#bindInspectorButtons();
    }

    /**
     * Restore the complete graph from any isolated node or relation level.
     *
     * @returns {void}
     */
    #clearGraphFocus() {
        this.#resetGraphRegion();
        this.#layoutGraphByNeighbors();
        this.#needsViewportFit = true;
        this.#drawCanvas();
        this.#renderInspector();
    }

    /** Clear persistent region state without rendering. */
    #resetGraphRegion() {
        this.#selectedNodeId = "";
        this.#selectedRelationId = "";
        this.#regionNodeIds.clear();
        this.#regionEdgeIds.clear();
        this.#regionPositions.clear();
    }

    /**
     * Convert viewport pointer coordinates into graph coordinates.
     *
     * @param {PointerEvent} event Pointer event.
     * @param {HTMLCanvasElement} canvas Canvas element.
     * @returns {{x: number, y: number}} Graph point.
     */
    #canvasPoint(event, canvas) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: (event.clientX - rect.left - rect.width / 2 - this.#viewport.x) / this.#viewport.scale,
            y: (event.clientY - rect.top - rect.height / 2 - this.#viewport.y) / this.#viewport.scale
        };
    }

    /**
     * Find a node under graph coordinates.
     *
     * @param {number} x Graph x.
     * @param {number} y Graph y.
     * @returns {object|null} Hit node.
     */
    #hitTestNode(x, y) {
        const focus = this.#focusGraph();
        const candidates = focus ? this.#nodes.filter(node => focus.nodeIds.has(node.id)) : this.#nodes;
        return [...candidates].reverse().find(node => {
            const dx = node.x - x;
            const dy = node.y - y;
            return Math.sqrt((dx * dx) + (dy * dy)) <= node.radius + (16 / this.#viewport.scale);
        }) || null;
    }

    /**
     * Find an edge near graph coordinates.
     *
     * @param {number} x Graph x.
     * @param {number} y Graph y.
     * @returns {object|null} Hit edge.
     */
    #hitTestEdge(x, y) {
        const focus = this.#focusGraph();
        const candidates = focus ? this.#edges.filter(edge => focus.edgeIds.has(edge.id)) : this.#edges;
        return [...candidates].reverse().find(edge => {
            const from = this.#nodes.find(node => node.id === edge.from);
            const to = this.#nodes.find(node => node.id === edge.to);
            if (!from || !to) {
                return false;
            }
            return this.#pointToSegmentDistance(x, y, from.x, from.y, to.x, to.y) <= 7 / this.#viewport.scale;
        }) || null;
    }

    /**
     * Distance from point to segment.
     *
     * @param {number} px Point x.
     * @param {number} py Point y.
     * @param {number} x1 Segment x1.
     * @param {number} y1 Segment y1.
     * @param {number} x2 Segment x2.
     * @param {number} y2 Segment y2.
     * @returns {number} Distance.
     */
    #pointToSegmentDistance(px, py, x1, y1, x2, y2) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        if (dx === 0 && dy === 0) {
            return Math.hypot(px - x1, py - y1);
        }
        const t = Math.max(0, Math.min(1, (((px - x1) * dx) + ((py - y1) * dy)) / ((dx * dx) + (dy * dy))));
        return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
    }

    /**
     * Build a stable node id from contextual label.
     *
     * @param {string} domain Domain.
     * @param {string} label Label.
     * @param {number} index Fallback index.
     * @returns {string} Node id.
     */
    #nodeId(domain, label, index = 0) {
        return `node:${domain}:${String(label || index).toLowerCase()}`;
    }

    /**
     * Shorten a graph label.
     *
     * @param {string} label Full label.
     * @param {number} limit Character limit.
     * @returns {string} Short label.
     */
    #shortLabel(label, limit = 14) {
        const text = String(label || "");
        return text.length > limit ? `${text.slice(0, Math.max(1, limit - 1))}...` : text;
    }
}

customElements.define(KnowledgeView.selector, KnowledgeView);
