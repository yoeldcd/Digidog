/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml, optionTags, renderMarkdown } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";
import { StructureTree } from "./structure-tree.ts";

void StructureTree;

const LOG_MONTH_LABELS = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

/**
 * LogsView renders log domains as a structural tree plus one focused content pane.
 */
export class LogsView extends HTMLElement {
    static get selector() {
        return "brain-logs-view";
    }

    #api = null;
    #state = null;
    #indexEntries = [];
    #logEntries = [];
    #selectedDomain = "";
    #filter = "";
    #from = "";
    #to = "";
    #hourFrom = "";
    #hourTo = "";
    #sortOrder = "desc";
    #treeMode = "domain";
    #selectedDatePath = "";
    #filtersOpen = false;
    #expandedNodes = new Set();
    #pendingTarget = null;
    #logsWithImages = [];
    #refreshTimer = null;
    #refreshInFlight = false;

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#pendingTarget = this.#state?.consumeRouteTarget?.("logs") || this.#pendingTarget;
        this.#loadIndex();
    }

    /**
     * Initialize DOM.
     *
     * @returns {void}
     */
    connectedCallback() {
        this.#render();
        this.#startSilentRefresh();
    }

    /** Stop background work when the Logs route is unmounted. */
    disconnectedCallback() {
        window.clearTimeout(this.#refreshTimer);
        this.#refreshTimer = null;
    }

    /** Start a single view-owned silent refresh cycle. */
    #startSilentRefresh() {
        if (this.#refreshTimer) {
            return;
        }
        this.#scheduleSilentRefresh();
    }

    /** Schedule the next cycle one minute after the previous one completed. */
    #scheduleSilentRefresh() {
        if (!this.isConnected) {
            return;
        }
        this.#refreshTimer = window.setTimeout(() => {
            this.#refreshTimer = null;
            this.#refreshSilently();
        }, 60000);
    }

    /** Refresh the index and reload focused content only after an index change. */
    async #refreshSilently() {
        if (!this.#api || this.#refreshInFlight || document.hidden) {
            return;
        }
        this.#refreshInFlight = true;
        try {
            const indexResult = await this.#api.logIndex({}, { forceRefresh: true, silent: true });
            const nextIndexEntries = indexResult.data?.entries || [];
            if (JSON.stringify(nextIndexEntries) === JSON.stringify(this.#indexEntries)) {
                return;
            }
            this.#indexEntries = nextIndexEntries;
            if (!this.#logEntries.length || !this.#selectedDomain) {
                this.#state?.setLastResult(indexResult);
                this.#render();
                return;
            }
            const logsResult = await this.#api.logs({
                domain: this.#selectedDomain,
                date: this.#from && this.#from === this.#to ? this.#from : "",
                time: this.#hourFrom && this.#hourFrom === this.#hourTo ? this.#hourFrom : "",
                from: this.#from,
                to: this.#to
            }, { forceRefresh: true, silent: true });
            const nextLogEntries = logsResult.data?.entries || [];
            const nextImages = logsResult.hasImages || [];
            this.#state?.setLastResult(logsResult);
            this.#logEntries = nextLogEntries;
            this.#logsWithImages = nextImages;
            this.#render();
        } finally {
            this.#refreshInFlight = false;
            this.#scheduleSilentRefresh();
        }
    }

    /**
     * Load the log domain index.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadIndex(forceRefresh = false) {
        if (!this.#api) {
            return;
        }
        const result = await this.#api.logIndex({}, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#indexEntries = result.data?.entries || [];
        const domains = this.#domains();
        this.#selectedDomain = this.#selectedDomain || domains[0]?.path || "";
        if (this.#selectedDomain) {
            this.#expandAncestors(this.#selectedDomain);
        }
        if (await this.#applyPendingTarget()) {
            return;
        }
        this.#render();
    }

    /**
     * Apply one pending SPA target and load the matching log entry range.
     *
     * @returns {Promise<boolean>} True when a target was consumed.
     */
    async #applyPendingTarget() {
        const target = this.#pendingTarget || this.#state?.consumeRouteTarget?.("logs");
        this.#pendingTarget = null;
        if (!target) {
            return false;
        }
        this.#selectedDomain = target.domain || this.#selectedDomain;
        this.#from = target.from || target.date || this.#from;
        this.#to = target.to || target.date || this.#to || this.#from;
        this.#hourFrom = target.hourFrom || target.time || this.#hourFrom;
        this.#hourTo = target.hourTo || target.time || this.#hourTo;
        this.#sortOrder = target.sortOrder || "desc";
        this.#expandAncestors(this.#selectedDomain);
        await this.#loadLogs(true, false);
        return true;
    }

    /**
     * Load logs for the selected domain and filters.
     *
     * @param {boolean} forceRefresh Whether to bypass cache.
     * @returns {Promise<void>} Resolves after render.
     */
    async #loadLogs(forceRefresh = false, readControls = true) {
        if (!this.#api) {
            return;
        }
        if (readControls) {
            this.#readFilters();
        }
        const result = await this.#api.logs({
            domain: this.#selectedDomain,
            date: this.#from && this.#from === this.#to ? this.#from : "",
            time: this.#hourFrom && this.#hourFrom === this.#hourTo ? this.#hourFrom : "",
            from: this.#from,
            to: this.#to
        }, { forceRefresh });
        this.#state?.setLastResult(result);
        this.#logsWithImages = result.hasImages || [];
        this.#logEntries = result.data?.entries || [];
        this.#render();
    }

    /**
     * Read compact filter controls.
     *
     * @returns {void}
     */
    #readFilters() {
        this.#from = this.querySelector("[data-role='log-from']")?.value.trim() || "";
        this.#to = this.querySelector("[data-role='log-to']")?.value.trim() || "";
        this.#hourFrom = this.querySelector("[data-role='log-hour-from']")?.value.trim() || "";
        this.#hourTo = this.querySelector("[data-role='log-hour-to']")?.value.trim() || "";
        this.#sortOrder = this.querySelector("[data-role='log-order']")?.value || this.#sortOrder;
    }

    /**
     * Render view markup.
     *
     * @returns {void}
     */
    #render() {
        const entries = this.#visibleLogEntries();
        const selectedRecord = this.#recordForPath(this.#selectedDomain);
        this.innerHTML = `
            <section class="page-surface logs-console">
                <div class="structure-layout logs-structure">
                    <aside class="structure-tree">
                        <div class="tree-list scroll-list">
                            ${this.#renderTree()}
                        </div>
                    </aside>
                    <main class="structure-content">
                        <div class="content-head logs-head">
                            <strong>${escapeHtml(this.#selectedDomain || "Indice de logs")}</strong>
                            <span>${escapeHtml(this.#logEntries.length ? `${entries.length} entradas` : (selectedRecord?.date ? "Entrada indexada" : "Selecciona dominio"))}</span>
                            <details class="action-menu filter-menu" ${this.#filtersOpen ? "open" : ""}>
                                <summary class="compact-action">${icon("filter")}<span>Filtros</span></summary>
                                <div class="action-menu-panel filter-menu-panel">
                                    <label><span>Desde</span><input data-role="log-from" value="${escapeHtml(this.#from)}" placeholder="DD-MM-YYYY"></label>
                                    <label><span>Hasta</span><input data-role="log-to" value="${escapeHtml(this.#to)}" placeholder="DD-MM-YYYY"></label>
                                    <label><span>Hora inicio</span><input data-role="log-hour-from" type="time" value="${escapeHtml(this.#hourFrom)}"></label>
                                    <label><span>Hora fin</span><input data-role="log-hour-to" type="time" value="${escapeHtml(this.#hourTo)}"></label>
                                    <label><span>Orden</span><select data-role="log-order">${optionTags(["desc", "asc"], this.#sortOrder)}</select></label>
                                    <div class="filter-menu-actions">
                                        <button data-action="clear-log-filters" class="ghost-action">${icon("filter")}Limpiar</button>
                                        <button data-action="load-logs" class="primary-action">${icon("search")}Aplicar</button>
                                    </div>
                                </div>
                            </details>
                        </div>
                        <div class="log-output log-card-list scroll-area">
                            ${this.#logEntries.length ? this.#renderLogEntries(entries) : `<p class="empty-state">Selecciona un dominio y carga su historial.</p>`}
                        </div>
                    </main>
                </div>
            </section>
        `;
        this.#bindEvents();
        this.#configureTree();
    }

    /**
     * Render parsed log entries as operational cards.
     *
     * @param {object[]} entries Visible entries.
     * @returns {string} HTML.
     */
    #renderLogEntries(entries) {
        if (!entries.length) {
            return `<p class="empty-state">No hay entradas para esos filtros.</p>`;
        }
        return entries.map(entry => `
            <details class="log-entry-card">
                <summary class="log-entry-summary">
                    <time class="log-date-badge">
                        <strong>${escapeHtml(entry.date)}</strong>
                        <span>${escapeHtml(entry.time)}</span>
                    </time>
                    <span class="log-entry-heading">
                        <strong>${escapeHtml(entry.title)}</strong>
                        <span class="log-entry-tags">
                            <span>${escapeHtml(entry.domain || this.#selectedDomain || "logs")}</span>
                            <span>${escapeHtml(entry.type || "log")}</span>
                            <span>${escapeHtml(entry.changeType || "registro")}</span>
                        </span>
                    </span>
                    <span class="log-entry-chevron">${icon("chevronDown")}</span>
                </summary>
                <div class="log-entry-body">
                    ${entry.why ? `<section><h2>Why</h2><div>${renderMarkdown(entry.why)}</div></section>` : ""}
                    ${entry.description ? `<section><h2>Description</h2><div>${renderMarkdown(entry.description)}</div></section>` : ""}
                    ${entry.impact ? `<section><h2>Impact</h2><div>${renderMarkdown(entry.impact)}</div></section>` : ""}
                    ${this.#renderPictures(entry.pictures)}
                </div>
            </details>
        `).join("");
    }

    /**
     * Render image attachments referenced by one log entry.
     *
     * @param {string[]} pictures Safe workspace picture file names.
     * @returns {string} Attachment gallery HTML.
     */
    #renderPictures(pictures = []) {
        if (!pictures.length) {
            return "";
        }
        return `
            <div class="log-entry-media" aria-label="Imagenes adjuntas">
                ${pictures.map(name => {
                    const source = `/api/logs/image?name=${encodeURIComponent(name)}`;
                    return `<a href="${source}" target="_blank" rel="noopener" title="Abrir imagen adjunta"><img src="${source}" alt="Imagen adjunta ${escapeHtml(name)}"></a>`;
                }).join("")}
            </div>
        `;
    }

    /**
     * Parse, sort, and filter log entries.
     *
     * @returns {object[]} Visible entries.
     */
    #visibleLogEntries() {
        const entries = this.#parseLogEntries();
        const filtered = entries.filter(entry => this.#matchesHour(entry.hourValue));
        return filtered.sort((left, right) => {
            const delta = left.timestamp - right.timestamp;
            return this.#sortOrder === "asc" ? delta : -delta;
        });
    }

    /**
     * Normalize structured log records returned by the CLI schema.
     *
     * @returns {object[]} Parsed entries.
     */
    #parseLogEntries() {
        return this.#logEntries.map((entry, index) => {
            const [date = "", ...timeParts] = String(entry.timestamp || "").split(" ");
            const time = timeParts.join(" ");
            const searchableText = [entry.title, entry.why, entry.description, entry.impact].join("\n");
            return {
                id: `log-${index}`,
                date,
                time,
                hourValue: this.#hourValue(time),
                timestamp: this.#timestamp(date, time),
                domain: entry.domain || this.#selectedDomain,
                title: entry.title || "Entrada de log",
                type: "log",
                changeType: entry.change_type || "",
                why: entry.why || "",
                description: entry.description || "",
                impact: entry.impact || "",
                pictures: this.#pictureNames(searchableText)
            };
        });
    }

    /**
     * Extract safe picture names from a log entry's Markdown fields.
     *
     * The server receives names only, never a workspace path, which prevents
     * an entry body from escaping the local pictures directory.
     *
     * @param {string} source Raw Markdown entry text.
     * @returns {string[]} Unique safe file names.
     */
    #pictureNames(source) {
        const names = new Set();
        const text = String(source || "");
        const matcher = /(?:\$agent[\\/])?pictures[\\/]([A-Za-z0-9][A-Za-z0-9._-]*\.(?:png|jpe?g|gif|webp))/gi;
        for (const match of text.matchAll(matcher)) {
            names.add(match[1]);
        }
        const taskMatcher = /#?(t\d+)\b/gi;
        for (const match of text.matchAll(taskMatcher)) {
            const taskId = match[1].toLowerCase();
            if (this.#logsWithImages.includes(taskId)) {
                names.add(`backlog-pic-${taskId}.png`);
            }
        }
        return [...names];
    }

    /**
     * Parse bold markdown fields from one log chunk.
     *
     * @param {string[]} lines Log chunk lines.
     * @returns {Record<string, string>} Field map.
     */
    #parseLogFields(lines) {
        const fields = {};
        let current = "";
        lines.forEach(line => {
            const field = line.match(/^\s*\*\*([^:*]+?)(?::)?\*\*\s*(.*)$/);
            if (field) {
                current = field[1].trim();
                fields[current] = field[2].trim();
                return;
            }
            if (!current || /^#{2,3}\s+/.test(line)) {
                return;
            }
            const text = line.trim();
            if (text) {
                fields[current] = `${fields[current] ? `${fields[current]}\n` : ""}${text}`;
            }
        });
        return fields;
    }

    /**
     * Return whether an entry hour is inside the selected range.
     *
     * @param {number} hourValue Minutes after midnight.
     * @returns {boolean} Visibility flag.
     */
    #matchesHour(hourValue) {
        const from = this.#timeInputValue(this.#hourFrom);
        const to = this.#timeInputValue(this.#hourTo);
        if (from === null && to === null) {
            return true;
        }
        if (from !== null && hourValue < from) {
            return false;
        }
        if (to !== null && hourValue > to) {
            return false;
        }
        return true;
    }

    /**
     * Convert a time input value into minutes after midnight.
     *
     * @param {string} value HH:MM value.
     * @returns {number|null} Minutes or null.
     */
    #timeInputValue(value) {
        const match = String(value || "").match(/^(\d{2}):(\d{2})$/);
        return match ? Number(match[1]) * 60 + Number(match[2]) : null;
    }

    /**
     * Convert a log time label into minutes after midnight.
     *
     * @param {string} label Log time.
     * @returns {number} Minutes.
     */
    #hourValue(label) {
        const match = String(label || "").toLowerCase().match(/(\d{1,2}):(\d{2})\s*(am|pm)?/);
        if (!match) {
            return 0;
        }
        let hour = Number(match[1]);
        const minute = Number(match[2]);
        if (match[3] === "pm" && hour < 12) {
            hour += 12;
        }
        if (match[3] === "am" && hour === 12) {
            hour = 0;
        }
        return hour * 60 + minute;
    }

    /**
     * Build a sortable timestamp from exported log labels.
     *
     * @param {string} date Date label.
     * @param {string} time Time label.
     * @returns {number} Timestamp.
     */
    #timestamp(date, time) {
        const match = String(date || "").match(/^(\d{2})-(\d{2})-(\d{4})$/);
        if (!match) {
            return 0;
        }
        const minutes = this.#hourValue(time);
        return new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1]), Math.floor(minutes / 60), minutes % 60).getTime();
    }

    /**
     * Render log domains as a collapsible tree.
     *
     * @returns {string} Tree HTML.
     */
    #renderTree() {
        return `<brain-structure-tree data-role="logs-tree"></brain-structure-tree>`;
    }

    /**
     * Render one log tree node.
     *
     * @param {object} node Tree node.
     * @param {number} depth Tree depth.
     * @returns {string} Node HTML.
     */
    #renderTreeNode(node, depth) {
        const children = Array.from(node.children.values()).sort((left, right) => left.label.localeCompare(right.label));
        const hasChildren = children.length > 0;
        const isOpen = this.#expandedNodes.has(node.path);
        const isActive = node.targetPath === this.#selectedDomain;
        if (!this.#matchesTree(node)) {
            return "";
        }
        return `
            <div class="tree-node-wrap">
                <button class="tree-node ${isActive ? "is-active" : ""}" style="--tree-depth:${depth}" data-node-path="${escapeHtml(node.targetPath)}" data-node-branch="${hasChildren ? "true" : "false"}">
                    <span class="tree-caret">${hasChildren ? icon(isOpen ? "chevronDown" : "chevronRight") : ""}</span>
                    ${icon(hasChildren ? "folder" : "document")}
                    <span>${escapeHtml(node.label)}</span>
                    ${node.command ? `<small>${escapeHtml(node.command)}</small>` : ""}
                </button>
                ${hasChildren ? `<div class="tree-children" ${isOpen ? "" : "hidden"}>${children.map(child => this.#renderTreeNode(child, depth + 1)).join("")}</div>` : ""}
            </div>
        `;
    }

    /**
     * Configure the shared tree with Log-specific toolbar and node actions.
     *
     * @returns {void}
     */
    #configureTree() {
        const treeElement = this.querySelector("[data-role='logs-tree']");
        if (!treeElement) {
            return;
        }
        treeElement.model = {
            nodes: this.#treeNodes(),
            selectedPath: this.#treeMode === "date" ? this.#selectedDatePath : this.#selectedDomain,
            expandedPaths: this.#expandedNodes,
            toggleOnBranchSelect: true,
            title: "Logs",
            toolbarActions: [
                { id: "tree-domain", label: "Agrupar por dominios", icon: "folder", active: this.#treeMode === "domain" },
                { id: "tree-date", label: "Agrupar por fechas", icon: "clock", active: this.#treeMode === "date" },
                { id: "refresh-index", label: "Actualizar indice", icon: "refresh" }
            ],
            sortDirection: this.#treeMode === "date" ? "desc" : "asc",
            defaultBranchIcon: "folder",
            defaultLeafIcon: "terminal",
            searchQuery: this.#filter,
            emptyText: "Sin indice cargado. Actualiza para consultar logs."
        };
        treeElement.addEventListener("brain-tree-select", event => this.#onTreeSelected(event));
        treeElement.addEventListener("brain-tree-toolbar-action", event => this.#onTreeToolbarAction(event));
        treeElement.addEventListener("brain-tree-action", event => this.#onTreeAction(event));
        treeElement.addEventListener("brain-tree-search", event => {
            this.#filter = event.detail.query;
            const entries = this.#visibleLogEntries();
            const selectedRecord = this.#recordForPath(this.#selectedDomain);
            const countSpan = this.querySelector(".logs-head span");
            if (countSpan) {
                countSpan.textContent = this.#logEntries.length ? `${entries.length} entradas` : (selectedRecord?.date ? "Entrada indexada" : "Selecciona dominio");
            }
            const logOutput = this.querySelector(".log-output");
            if (logOutput) {
                logOutput.innerHTML = this.#logEntries.length ? this.#renderLogEntries(entries) : `<p class="empty-state">Selecciona un dominio y carga su historial.</p>`;
            }
        });
    }

    /**
     * Convert the parsed log index to shared tree nodes.
     *
     * @returns {object[]} Tree node list.
     */
    #treeNodes() {
        if (this.#treeMode === "date") {
            return this.#dateTreeNodes();
        }
        const toNode = node => {
            const children = Array.from(node.children.values())
                .filter(child => this.#matchesTree(child))
                .sort((left, right) => left.label.localeCompare(right.label))
                .map(toNode);
            const isEntry = node.leaf === true;
            return {
                id: node.path,
                path: node.targetPath,
                label: isEntry ? node.label : node.label,
                timestamp: isEntry ? [node.date, node.time].filter(Boolean).join(" ") : "",
                detail: isEntry ? node.targetPath : "",
                presentation: isEntry ? "log" : "default",
                count: !isEntry ? this.#countTreeEntries(node) : undefined,
                children,
                actions: []
            };
        };
        return Array.from(this.#buildTree().children.values())
            .filter(node => this.#matchesTree(node))
            .sort((left, right) => left.label.localeCompare(right.label))
            .map(toNode);
    }

    /**
     * Group the complete log index into year, month, day, and entry nodes.
     *
     * @returns {object[]} Shared tree nodes ordered from newest to oldest.
     */
    #dateTreeNodes() {
        const years = new Map();
        this.#indexEntries.forEach((entry, index) => {
            const [date = "", ...timeParts] = String(entry.timestamp || "").split(" ");
            const match = date.match(/^(\d{2})-(\d{2})-(\d{4})$/);
            if (!match) {
                return;
            }
            const [, day, month, year] = match;
            const time = timeParts.join(" ");
            const yearNode = this.#ensureDateGroup(years, `logs-date:${year}`, year, "folder");
            const monthNode = this.#ensureDateGroup(yearNode.children, `logs-date:${year}-${month}`, LOG_MONTH_LABELS[Number(month)] || month, "folder");
            const dayNode = this.#ensureDateGroup(monthNode.children, `logs-date:${year}-${month}-${day}`, `${day} ${LOG_MONTH_LABELS[Number(month)] || month}`, "clock");
            dayNode.entries.push({
                id: `logs-date-entry:${index}:${date}:${time}:${entry.domain || "logs"}`,
                path: `logs-date-entry:${date}:${time}:${entry.domain || "logs"}`,
                label: entry.title || "Entrada de log",
                timestamp: time,
                sortKey: String(this.#hourValue(time)).padStart(4, "0"),
                detail: entry.domain || "logs",
                presentation: "log",
                domain: entry.domain || "",
                date,
                time,
                children: []
            });
        });
        const project = group => {
            const groups = Array.from(group.children.values())
                .sort((left, right) => right.id.localeCompare(left.id))
                .map(project);
            const entries = [...group.entries].sort((left, right) => right.timestamp.localeCompare(left.timestamp));
            return {
                id: group.id,
                path: group.id,
                label: group.label,
                sortKey: group.id,
                icon: group.icon,
                count: this.#countDateEntries(group),
                sortDirection: "desc",
                children: [...groups, ...entries]
            };
        };
        return Array.from(years.values())
            .sort((left, right) => right.id.localeCompare(left.id))
            .map(project);
    }

    /**
     * Create or return one mutable date-group accumulator.
     *
     * @param {Map<string, object>} groups Sibling group map.
     * @param {string} id Stable tree identity.
     * @param {string} label Visible group label.
     * @param {string} iconName Registered icon name.
     * @returns {object} Mutable group accumulator.
     */
    #ensureDateGroup(groups, id, label, iconName) {
        if (!groups.has(id)) {
            groups.set(id, { id, label, icon: iconName, children: new Map(), entries: [] });
        }
        return groups.get(id);
    }

    /**
     * Count terminal log entries below one date group.
     *
     * @param {object} group Date-group accumulator.
     * @returns {number} Descendant entry count.
     */
    #countDateEntries(group) {
        return group.entries.length + Array.from(group.children.values())
            .reduce((total, child) => total + this.#countDateEntries(child), 0);
    }

    /**
     * Count terminal records below one parsed tree node.
     *
     * @param {object} node Parsed node.
     * @returns {number} Descendant entry count.
     */
    #countTreeEntries(node) {
        return this.#indexEntries.filter(entry => {
            const domain = String(entry.domain || "");
            return domain === node.path || domain.startsWith(`${node.path}.`);
        }).length;
    }

    /**
     * Handle selection emitted by the shared tree.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {Promise<void>} Resolves after a selected domain loads.
     */
    async #onTreeSelected(event) {
        const { path, branch, node } = event.detail;
        if (branch) {
            return;
        }
        if (this.#treeMode === "date" && node?.date) {
            this.#selectedDatePath = path;
            this.#selectedDomain = node.domain;
            this.#from = node.date;
            this.#to = node.date;
            this.#hourFrom = node.time || "";
            this.#hourTo = node.time || "";
            await this.#loadLogs(true, false);
            return;
        }
        const alreadySelected = path === this.#selectedDomain;
        this.#selectedDomain = path;
        this.#expandAncestors(path);
        const record = this.#recordForPath(path);
        if (record?.date) {
            this.#from = record.date;
            this.#to = record.date;
            this.#hourFrom = record.time || "";
            this.#hourTo = record.time || "";
        }
        if (alreadySelected && this.#logEntries.length) {
            this.#render();
            return;
        }
        await this.#loadLogs(true, !record?.date);
    }

    /**
     * Handle a Logs tree toolbar action.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeToolbarAction(event) {
        if (event.detail.action === "tree-domain" || event.detail.action === "tree-date") {
            const nextMode = event.detail.action === "tree-date" ? "date" : "domain";
            if (nextMode === this.#treeMode) {
                return;
            }
            this.#treeMode = nextMode;
            this.#expandedNodes.clear();
            this.#render();
            return;
        }
        if (event.detail.action === "refresh-index") {
            this.#loadIndex(true);
        }
    }

    /**
     * Handle a contextual action for one Logs tree node.
     *
     * @param {CustomEvent} event Tree event.
     * @returns {void}
     */
    #onTreeAction(event) {
        const node = event.detail.node;
        if (!node?.path) {
            return;
        }
        this.#selectedDomain = node.path;
        const record = this.#recordForPath(node.path);
        if (record?.date) {
            this.#from = record.date;
            this.#to = record.date;
            this.#hourFrom = record.time || "";
            this.#hourTo = record.time || "";
        }
        this.#loadLogs(true, !record?.date);
    }

    /**
     * Parse log index text into domain records.
     *
     * @returns {object[]} Log domain records.
     */
    #domains() {
        const records = [];
        for (const entry of this.#indexEntries) {
            const domain = String(entry.domain || "");
            const parts = domain.split(".").filter(Boolean);
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                const terminal = index === parts.length - 1;
                const [date = "", ...timeParts] = String(entry.timestamp || "").split(" ");
                const time = timeParts.join(" ");
                records.push({
                    path,
                    label: terminal ? (entry.title || part) : part,
                    command: terminal ? `read-log -d ${date} --time ${time}` : "",
                    date: terminal ? date : "",
                    time: terminal ? time : "",
                    leaf: false
                });
            });
        }
        return this.#dedupeRecords(records).filter(record => record.path);
    }

    /**
     * Build a dot-domain tree from parsed records.
     *
     * @returns {object} Tree root.
     */
    #buildTree() {
        const root = { label: "", path: "", targetPath: "", children: new Map(), command: "", leaf: false, entryCount: 0 };
        for (const record of this.#domains()) {
            const parts = record.path.split(".").filter(Boolean);
            let current = root;
            parts.forEach((part, index) => {
                const path = parts.slice(0, index + 1).join(".");
                if (!current.children.has(part)) {
                    current.children.set(part, {
                        label: part,
                        path,
                        targetPath: path,
                        children: new Map(),
                        command: "",
                        leaf: false,
                        entryCount: 0
                    });
                }
                current = current.children.get(part);
                if (index === parts.length - 1 && !record.leaf) {
                    current.command = record.command;
                    current.date = record.date;
                    current.time = record.time;
                    current.leaf = record.leaf;
                }
            });
            if (record.leaf) {
                current.entryCount = (current.entryCount || 0) + 1;
            }
        }
        return root;
    }

    /**
     * Format a tree leaf using the log entry identity instead of its domain.
     *
     * @param {object} record Parsed log index record.
     * @returns {string} Entry label.
     */
    #entryLabel(record) {
        return record.label;
    }

    /**
     * Extract date and time from a log-index read command.
     *
     * @param {string} command Index command text.
     * @returns {{date: string, time: string}} Parsed target.
     */
    #targetFromLogCommand(command) {
        const date = String(command || "").match(/read-log\s+-d\s+(\d{2}-\d{2}-\d{4})/);
        const time = String(command || "").match(/--time\s+(\d{1,2}:\d{2})/);
        return {
            date: date?.[1] || "",
            time: time?.[1] || ""
        };
    }

    /**
     * Find one parsed index record by path.
     *
     * @param {string} path Dot path.
     * @returns {object|null} Record or null.
     */
    #recordForPath(path) {
        return this.#domains().find(record => record.path === path) || null;
    }

    /**
     * Remove duplicate parsed records.
     *
     * @param {object[]} records Parsed records.
     * @returns {object[]} Unique records.
     */
    #dedupeRecords(records) {
        const byPath = new Map();
        records.forEach(record => byPath.set(record.path, record));
        return Array.from(byPath.values());
    }

    /**
     * Return whether a node or descendant matches the filter.
     *
     * @param {object} node Tree node.
     * @returns {boolean} Visibility flag.
     */
    #matchesTree(node) {
        const needle = this.#filter.toLowerCase();
        if (!needle) {
            return true;
        }
        if (node.path.toLowerCase().includes(needle) || node.command.toLowerCase().includes(needle)) {
            return true;
        }
        return Array.from(node.children.values()).some(child => this.#matchesTree(child));
    }

    /**
     * Expand ancestors for a selected domain.
     *
     * @param {string} path Dot domain path.
     * @returns {void}
     */
    #expandAncestors(path) {
        const parts = path.split(".");
        for (let index = 1; index <= parts.length; index += 1) {
            this.#expandedNodes.add(parts.slice(0, index).join("."));
        }
    }

    /**
     * Bind DOM events.
     *
     * @returns {void}
     */
    #bindEvents() {
        this.querySelector("[data-action='refresh-index']")?.addEventListener("click", () => this.#loadIndex(true));
        this.querySelectorAll("[data-action='load-logs']").forEach(button => button.addEventListener("click", () => this.#loadLogs(true)));
        this.querySelector(".filter-menu")?.addEventListener("toggle", event => {
            this.#filtersOpen = event.currentTarget.open;
        });
        this.querySelector("[data-action='clear-log-filters']")?.addEventListener("click", () => {
            this.#from = "";
            this.#to = "";
            this.#hourFrom = "";
            this.#hourTo = "";
            this.#sortOrder = "desc";
            this.#filtersOpen = true;
            this.#render();
        });
        // Filter input handled inside tree component
        this.querySelectorAll("[data-node-path]").forEach(button => button.addEventListener("click", async event => {
            const path = button.getAttribute("data-node-path") || "";
            const isBranch = button.getAttribute("data-node-branch") === "true";
            const wasExpanded = this.#expandedNodes.has(path);
            const clickedCaret = Boolean(event.target.closest(".tree-caret"));
            if (isBranch && clickedCaret) {
                const nextOpen = !wasExpanded;
                if (wasExpanded) {
                    this.#expandedNodes.delete(path);
                } else {
                    this.#expandedNodes.add(path);
                }
                const childContainer = Array.from(button.parentElement?.children || []).find(child => child.classList?.contains("tree-children"));
                if (childContainer) {
                    childContainer.hidden = !nextOpen;
                }
                const caret = button.querySelector(".tree-caret");
                if (caret) {
                    caret.innerHTML = icon(nextOpen ? "chevronDown" : "chevronRight");
                }
                return;
            }
            const alreadySelected = path === this.#selectedDomain;
            this.#selectedDomain = path;
            this.#expandAncestors(path);
            const record = this.#recordForPath(path);
            if (record?.date) {
                this.#from = record.date;
                this.#to = record.date;
                this.#hourFrom = record.time || "";
                this.#hourTo = record.time || "";
            }
            if (isBranch) {
                this.#expandedNodes.add(path);
            }
            if (alreadySelected && this.#logEntries.length) {
                this.#render();
                return;
            }
            await this.#loadLogs(true, !record?.date);
        }));
    }
}

customElements.define(LogsView.selector, LogsView);
