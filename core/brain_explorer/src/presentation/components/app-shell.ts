/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { DashboardView } from "./dashboard-view.ts";
import { BrainApiClient } from "../../infrastructure/api/brain-api-client.ts";
import { MemoryView } from "./memory-view.ts";
import { KnowledgeView } from "./knowledge-view.ts";
import { QueryView } from "./query-view.ts";
import { ProfilesView } from "./profiles-view.ts";
import { LogsView } from "./logs-view.ts";
import { BacklogView } from "./backlog-view.ts";
import { SettingsView } from "./settings-view.ts";
import { WikisView } from "./wikis-view.ts";
import { MessagesView } from "./messages-view.ts";
import { PicturesView } from "./pictures-view.ts";
import { codeBlock, escapeHtml } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";
import { notificationText } from "../utils/notification-message.ts";

const ROUTES = [
    { id: "dashboard", label: "Project", icon: "home", element: DashboardView.selector },
    { id: "messages", label: "Messages", icon: "messageCircle", element: MessagesView.selector },
    { id: "memory", label: "Memory", icon: "database", element: MemoryView.selector },
    { id: "knowledge", label: "Knowledge", icon: "graph", element: KnowledgeView.selector },
    { id: "pictures", label: "Pictures", icon: "camera", element: PicturesView.selector },
    { id: "query", label: "Results", icon: "search", element: QueryView.selector, nav: false },
    { id: "profiles", label: "Profiles", icon: "users", element: ProfilesView.selector },
    { id: "logs", label: "Logs", icon: "document", element: LogsView.selector },
    { id: "backlog", label: "Backlog", icon: "checkSquare", element: BacklogView.selector },
    { id: "wikis", label: "Wikis", icon: "book", element: WikisView.selector },
    { id: "settings", label: "Settings", icon: "settings", element: SettingsView.selector }
];

/**
 * BrainExplorerApp composes the persistent shell around route-level Web Components.
 */
export class BrainExplorerApp extends HTMLElement {
    static get selector() {
        return "brain-explorer-app";
    }

    #api = null;
    #state = null;
    #activeRouteId = "";
    #stateListenersBound = false;
    #apiListenersBound = false;
    #activeRequestCount = 0;
    #openCallIds = new Set();
    #latestVoiceAudio = null;
    #notificationTimers = new Map();
    #handleGlobalKeyDown = (event) => {
        if (event.ctrlKey && event.altKey && event.key?.toLowerCase() === "s") {
            event.preventDefault();
            const searchInput = this.querySelector("[data-role='global-shell-search']");
            searchInput?.focus();
            searchInput?.select();
        }
    };

    /**
     * Assign runtime dependencies.
     *
     * @param {object} context Component context.
     * @returns {void}
     */
    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        this.#bindStateEvents();
        this.#bindApiEvents();
        this.#renderShell();
    }

    /**
     * Render shell when attached.
     *
     * @returns {void}
     */
    connectedCallback() {
        if (this.#state && this.#api && !this.querySelector(".app-shell")) {
            this.#renderShell();
        }
        window.addEventListener("keydown", this.#handleGlobalKeyDown);
    }

    /**
     * Remove keyboard shortcut listener when detached.
     *
     * @returns {void}
     */
    disconnectedCallback() {
        window.removeEventListener("keydown", this.#handleGlobalKeyDown);
        this.#notificationTimers.forEach(record => window.clearTimeout(record.timer));
        this.#notificationTimers.clear();
    }

    /**
     * Render persistent shell markup once per context assignment.
     *
     * @returns {void}
     */
    #renderShell() {
        if (!this.#state || !this.#api) {
            return;
        }
        document.documentElement.dataset.theme = this.#state.theme;
        this.innerHTML = `
            <div class="app-shell ${this.#state.sidebarOpen ? "is-sidebar-open" : "is-sidebar-collapsed"}">
                <header class="top-bar">
                    <div class="brand-lockup" style="display: flex; align-items: center; gap: 6px;">
                        <span class="brain-mark">${icon("pulse")}</span>
                        <span style="font-size: 16px; font-weight: 600; color: var(--text-normal); display: inline-flex; align-items: center;">
                            Brain ~&nbsp;
                            <details class="action-menu project-selector-menu" style="position: relative; display: inline-block;">
                                <summary style="cursor: pointer; list-style: none; display: inline-flex; align-items: center; gap: 4px; padding-right: 14px; background-image: url(&quot;data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%23888888' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>&quot;); background-repeat: no-repeat; background-position: right center; background-size: 10px; outline: none; user-select: none;" data-role="project-selector-summary">
                                    Loading...
                                </summary>
                                <div class="action-menu-panel project-selector-panel" data-role="project-selector-options">
                                </div>
                            </details>
                        </span>
                    </div>
                    <div class="global-search-cluster">
                        <div class="global-search">
                            ${icon("search")}
                            <input data-role="global-shell-search" placeholder="Search all knowledge...">
                            <kbd>Ctrl + Alt + S</kbd>
                        </div>
                        <details class="action-menu search-options-menu">
                            <summary title="Search sources and modes" aria-label="Search sources and modes">${icon("sliders")}</summary>
                            <div class="action-menu-panel search-options-panel">
                                <fieldset>
                                    <legend>Sources</legend>
                                    <label><input type="checkbox" name="search-source" value="memory" checked>Memory</label>
                                    <label><input type="checkbox" name="search-source" value="knowledge" checked>Knowledge</label>
                                    <label><input type="checkbox" name="search-source" value="messages" checked>Messages</label>
                                    <label><input type="checkbox" name="search-source" value="pictures" checked>Pictures</label>
                                </fieldset>
                                <fieldset>
                                    <legend>Modes</legend>
                                    <label><input type="checkbox" name="search-mechanism" value="graph" checked>Graph</label>
                                    <label><input type="checkbox" name="search-mechanism" value="vector" checked>Vector</label>
                                    <label><input type="checkbox" name="search-mechanism" value="text" checked>Text</label>
                                </fieldset>
                            </div>
                        </details>
                    </div>
                    <div class="header-actions">
                        <button class="voice-header-toggle" data-action="play-latest-voice" title="Replay latest message" aria-label="Replay latest message">${icon("volume")}</button>
                        <button class="theme-toggle" data-action="toggle-theme" title="Change theme"></button>
                    </div>
                </header>

                <aside class="side-nav">
                    <button class="sidebar-collapse" data-action="toggle-sidebar"></button>
                    <nav data-role="side-nav-list" aria-label="Main navigation">
                        ${this.#renderNav()}
                    </nav>
                </aside>

                <main class="route-host" data-route-host></main>

                <footer class="status-footer">
                    <span>(c) 2026 Brain Explorer</span>
                    <span>v1.1.0</span>
                    <span data-role="footer-route"></span>
                    <span data-role="footer-call"></span>
                    <button data-action="toggle-diagnostics" class="footer-link">${icon("terminal")}CLI</button>
                    <span>Local system <i class="live-dot"></i></span>
                </footer>

                <div data-command-overlay-host></div>
                <div data-diagnostics-host></div>
                <section class="notification-stack" data-notification-stack aria-live="polite" aria-label="Notifications"></section>
            </div>
        `;
        this.#bindShellEvents();
        this.#syncTheme();
        this.#syncSidebar();
        this.#mountRoute();
        this.#syncFooter();
        this.#renderDiagnosticsPanel();
        this.#renderActiveCommand();
        this.#api.health().then(res => {
            if (res && res.workspaceRoot) {
                // Fetch and populate registered projects dropdown
                const api = this.#api as unknown as BrainApiClient;
                if (api) {
                    api.getProjects().then((projectsRes) => {
                        const summaryEl = this.querySelector("[data-role='project-selector-summary']") as HTMLElement;
                        const optionsEl = this.querySelector("[data-role='project-selector-options']") as HTMLElement;
                        if (summaryEl && optionsEl && projectsRes && projectsRes.projects) {
                            optionsEl.innerHTML = "";
                            let activePath = localStorage.getItem("active_project_path");
                            const defaultPath = res.workspaceRoot;
                            
                            const allProjects = [...projectsRes.projects];
                            if (defaultPath && !allProjects.some(p => p.path === defaultPath)) {
                                allProjects.unshift({
                                    name: defaultPath,
                                    path: defaultPath
                                });
                            }
                            allProjects.sort((a, b) => a.path.localeCompare(b.path));
                            
                            const activeProjectIsRegistered = allProjects.some(project => project.path === activePath);
                            if (!activeProjectIsRegistered && defaultPath) {
                                activePath = defaultPath;
                                localStorage.setItem("active_project_path", defaultPath);
                            }
                            
                            if (activePath) {
                                summaryEl.textContent = activePath;
                                api.setWorkspaceRootOverride(activePath);
                            } else {
                                summaryEl.textContent = defaultPath;
                            }
                            
                            allProjects.forEach(proj => {
                                const btn = document.createElement("button");
                                btn.type = "button";
                                btn.textContent = proj.path;
                                if (proj.path === activePath) {
                                    btn.classList.add("active");
                                }
                                btn.addEventListener("click", () => {
                                    localStorage.setItem("active_project_path", proj.path);
                                    api.setWorkspaceRootOverride(proj.path);
                                    window.location.reload();
                                });
                                optionsEl.appendChild(btn);
                            });
                        }
                    }).catch((err) => console.error("Error fetching projects for selector:", err));
                }
            }
        }).catch(err => console.error("Error fetching health for project indicator:", err));
    }

    /**
     * Bind application state events to focused shell updates.
     *
     * @returns {void}
     */
    #bindStateEvents() {
        if (this.#stateListenersBound || !this.#state) {
            return;
        }
        this.#state.addEventListener("route", () => {
            this.#mountRoute();
            this.#syncFooter();
        });
        this.#state.addEventListener("theme", () => this.#syncTheme());
        this.#state.addEventListener("sidebar", () => this.#syncSidebar());
        this.#state.addEventListener("diagnostics", () => this.#renderDiagnosticsPanel());
        this.#state.addEventListener("active-command", () => {
            this.#syncFooter();
            this.#renderActiveCommand();
            this.#renderDiagnosticsLog();
        });
        this.#state.addEventListener("result", () => {
            this.#syncFooter();
            this.#renderActiveCommand();
            this.#renderDiagnosticsLog();
        });
        this.#stateListenersBound = true;
    }

    /**
     * Bind API request lifecycle events to the global state zone.
     *
     * @returns {void}
     */
    #bindApiEvents() {
        if (this.#apiListenersBound || !this.#api || !this.#state) {
            return;
        }
        this.#api.addEventListener("request-start", event => {
            this.#activeRequestCount += 1;
            this.#state.setActiveCommand(event.detail?.command || "CLI");
        });
        this.#api.addEventListener("request-end", event => {
            this.#activeRequestCount = Math.max(0, this.#activeRequestCount - 1);
            if (this.#activeRequestCount === 0) {
                this.#state.clearActiveCommand();
            }
            const payload = event.detail?.payload;
            const method = event.detail?.method || "GET";
            const feedback = payload
                ? notificationText(payload, method, event.detail?.command || "")
                : null;
            if (payload && !payload.ok) {
                this.#pushNotification({
                    tone: "error",
                    title: "Could not complete",
                    message: feedback?.message
                });
            } else if (payload && method !== "GET") {
                this.#pushNotification({
                    tone: "success",
                    title: feedback?.title,
                    message: feedback?.message
                });
            }
        });
        this.#apiListenersBound = true;
    }

    /** Add one timed, hover-pausable notification pill to the global stack. */
    #pushNotification({ tone = "info", title = "Message", message = "" }) {
        const stack = this.querySelector("[data-notification-stack]");
        if (!stack) return;
        const id = `notification-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const lifetime = tone === "error" ? 10_000 : 7_000;
        const element = document.createElement("article");
        element.className = `push-notification is-${tone}`;
        element.dataset.notificationId = id;
        element.style.setProperty("--notification-life", `${lifetime}ms`);
        element.innerHTML = `
            <button class="notification-copy" type="button" aria-expanded="false">
                <strong>${escapeHtml(title)}</strong>
                <span>${escapeHtml(String(message || title))}</span>
            </button>
            <button class="notification-close" type="button" aria-label="Close notification"><i></i></button>
        `;
        stack.append(element);
        const record = { timer: 0, remaining: lifetime, startedAt: performance.now() };
        const dismiss = () => {
            window.clearTimeout(record.timer);
            this.#notificationTimers.delete(id);
            element.classList.add("is-leaving");
            window.setTimeout(() => element.remove(), 180);
        };
        const resume = () => {
            record.startedAt = performance.now();
            record.timer = window.setTimeout(dismiss, record.remaining);
            element.classList.remove("is-paused");
        };
        const pause = () => {
            window.clearTimeout(record.timer);
            record.remaining = Math.max(0, record.remaining - (performance.now() - record.startedAt));
            element.classList.add("is-paused");
        };
        element.addEventListener("mouseenter", pause);
        element.addEventListener("mouseleave", resume);
        element.querySelector(".notification-close")?.addEventListener("click", dismiss);
        element.querySelector(".notification-copy")?.addEventListener("click", event => {
            const expanded = element.classList.toggle("is-expanded");
            event.currentTarget.setAttribute("aria-expanded", String(expanded));
        });
        this.#notificationTimers.set(id, record);
        resume();
    }

    /**
     * Bind persistent DOM events using delegation so route views are not remounted.
     *
     * @returns {void}
     */
    #bindShellEvents() {
        const shell = this.querySelector(".app-shell");
        if (!shell) {
            return;
        }
        shell.addEventListener("click", event => this.#handleShellClick(event));
        shell.addEventListener("submit", event => {
            if (event.target instanceof Element && event.target.matches("[data-role='cli-prompter']")) {
                event.preventDefault();
                this.#runCliPrompt();
            }
        });
        this.querySelector("[data-role='global-shell-search']")?.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                const value = event.target.value.trim();
                if (value) {
                    this.querySelector(".search-options-menu")?.removeAttribute("open");
                    this.#state.setPendingQuery(value, this.#selectedSearchOptions());
                    return;
                }
                this.#state.setRoute("query");
            }
        });
    }

    /** Collect non-exclusive search source and mechanism selections. */
    #selectedSearchOptions() {
        const selected = name => Array.from(this.querySelectorAll(`input[name='${name}']:checked`))
            .map(input => input.value);
        return { sources: selected("search-source"), mechanisms: selected("search-mechanism") };
    }

    /**
     * Handle shell-level click actions.
     *
     * @param {Event} event DOM click event.
     * @returns {void}
     */
    #handleShellClick(event) {
        const target = event.target instanceof Element ? event.target : null;
        this.#handleDropdownMenus(target);
        if (this.#state.sidebarOpen && target && !target.closest(".side-nav")) {
            this.#state.closeSidebar();
        }
        const routeButton = target?.closest("[data-route]");
        if (routeButton) {
            this.#state.setRoute(routeButton.getAttribute("data-route"));
            this.#state.closeSidebar();
            return;
        }
        const actionButton = target?.closest("[data-action]");
        const action = actionButton?.getAttribute("data-action") || "";
        if (action === "toggle-theme") {
            this.#state.toggleTheme();
        }
        if (action === "play-latest-voice") {
            this.#playLatestVoice();
        }
        if (action === "toggle-diagnostics") {
            this.#state.toggleDiagnostics();
        }
        if (action === "close-diagnostics") {
            this.#state.closeDiagnostics();
        }
        if (action === "clear-cli-log") {
            this.#openCallIds.clear();
            this.#state.clearCallLog();
        }
        if (action === "delete-cli-call") {
            const callId = actionButton?.getAttribute("data-call-id") || "";
            this.#openCallIds.delete(callId);
            this.#state.removeCallLogItem(callId);
        }
        if (action === "toggle-sidebar") {
            this.#state.toggleSidebar();
        }
        if (action === "run-cli-command") {
            this.#runCliPrompt();
        }
    }

    /** Replay the latest persisted voice without requesting new synthesis. */
    #playLatestVoice() {
        this.#latestVoiceAudio?.pause();
        this.#latestVoiceAudio = new Audio(`/api/voice/latest?fresh=${Date.now()}`);
        void this.#latestVoiceAudio.play().catch(() => {
            this.#latestVoiceAudio = null;
        });
    }

    /**
     * Keep native details dropdowns mutually dismissible across route components.
     *
     * @param {Element|null} target Click target.
     * @returns {void}
     */
    #handleDropdownMenus(target) {
        const activeMenu = target?.closest("details.action-menu") || null;
        this.querySelectorAll("details.action-menu[open]").forEach(menu => {
            if (menu !== activeMenu) {
                menu.removeAttribute("open");
            }
        });
        if (target?.closest(".action-menu-panel button")) {
            queueMicrotask(() => activeMenu?.removeAttribute("open"));
        }
    }

    /**
     * Render navigation buttons.
     *
     * @returns {string} Navigation HTML.
     */
    #renderNav() {
        return ROUTES.filter(route => route.nav !== false).map(route => `
            <button class="side-nav-item ${route.id === this.#state.route ? "is-active" : ""}" data-route="${route.id}" data-tooltip="${escapeHtml(route.label)}" aria-label="${escapeHtml(route.label)}">
                ${icon(route.icon)}
                <span class="nav-label">${escapeHtml(route.label)}</span>
            </button>
        `).join("");
    }

    /**
     * Mount the active route component only when the route changes.
     *
     * @returns {void}
     */
    #mountRoute() {
        const route = ROUTES.find(item => item.id === this.#state.route) || ROUTES[0];
        const host = this.querySelector("[data-route-host]");
        const refreshPendingQuery = route.id === "query" && Boolean(this.#state.pendingQuery);
        if (!host || (this.#activeRouteId === route.id && !refreshPendingQuery)) {
            this.#syncActiveNav();
            return;
        }
        const element = document.createElement(route.element);
        element.context = { api: this.#api, state: this.#state };
        host.setAttribute("aria-label", route.label);
        host.replaceChildren(element);
        this.#activeRouteId = route.id;
        this.#syncActiveNav();
    }

    /**
     * Update navigation active styles without rebuilding the route.
     *
     * @returns {void}
     */
    #syncActiveNav() {
        this.querySelectorAll("[data-route]").forEach(button => {
            button.classList.toggle("is-active", button.getAttribute("data-route") === this.#state.route);
        });
    }

    /**
     * Update theme button and document theme.
     *
     * @returns {void}
     */
    #syncTheme() {
        document.documentElement.dataset.theme = this.#state.theme;
        const button = this.querySelector("[data-action='toggle-theme']");
        if (!button) {
            return;
        }
        button.innerHTML = `
            ${icon(this.#state.theme === "dark" ? "sun" : "moon")}
        `;
    }

    /**
     * Update overlay sidebar width, label, and icon without touching routes.
     *
     * @returns {void}
     */
    #syncSidebar() {
        const shell = this.querySelector(".app-shell");
        const button = this.querySelector("[data-action='toggle-sidebar']");
        shell?.classList.toggle("is-sidebar-open", this.#state.sidebarOpen);
        shell?.classList.toggle("is-sidebar-collapsed", !this.#state.sidebarOpen);
        if (!button) {
            return;
        }
        const label = this.#state.sidebarOpen ? "Collapse" : "Expand";
        const iconName = this.#state.sidebarOpen ? "collapseLeft" : "expandRight";
        button.title = `${label} navigation`;
        button.dataset.tooltip = `${label} navigation`;
        button.setAttribute("aria-label", `${label} navigation`);
        button.innerHTML = `${icon(iconName)}<span class="nav-label">${label}</span>`;
    }

    /**
     * Keep route and CLI technical state in the persistent footer.
     *
     * @returns {void}
     */
    #syncFooter() {
        const route = ROUTES.find(item => item.id === this.#state.route) || ROUTES[0];
        const routeLabel = this.querySelector("[data-role='footer-route']");
        const callLabel = this.querySelector("[data-role='footer-call']");
        const lastCall = this.#state.callLog[0];
        if (routeLabel) {
            routeLabel.textContent = route.label;
        }
        if (!callLabel) {
            return;
        }
        if (!lastCall) {
            callLabel.textContent = "No CLI calls";
            return;
        }
        const command = lastCall.command.split(" ").slice(-2).join(" ") || "API";
        const state = lastCall.ok ? "OK" : "Error";
        callLabel.textContent = `${command} - ${lastCall.durationMs} ms - ${state}`;
    }

    /**
     * Execute the command typed in the bottom CLI prompter.
     *
     * @returns {Promise<void>} Resolves after command execution.
     */
    async #runCliPrompt() {
        const input = this.querySelector("[data-role='cli-prompt']");
        const command = input?.value?.trim() || "";
        if (!command) {
            return;
        }
        this.#state.setActiveCommand(command);
        const result = await this.#api.runCli(command);
        this.#state.setLastResult(result);
    }

    /**
     * Render diagnostics drawer in its isolated overlay host.
     *
     * @returns {void}
     */
    #renderDiagnosticsPanel() {
        const host = this.querySelector("[data-diagnostics-host]");
        if (!host) {
            return;
        }
        host.innerHTML = this.#state.diagnosticsOpen ? this.#renderDiagnosticsDrawer() : "";
        this.#bindCallLogItems();
    }

    /**
     * Render diagnostics drawer.
     *
     * @returns {string} HTML.
     */
    #renderDiagnosticsDrawer() {
        return `
            <aside class="diagnostics-drawer" aria-label="CLI console">
                <div class="diagnostics-head">
                    <div>
                        <strong>CLI calls</strong>
                        <span>History, active command, and allowlisted prompt</span>
                    </div>
                    <div class="diagnostics-actions">
                        <button data-action="clear-cli-log" class="ghost-action">${icon("trash")}Clear</button>
                        <button data-action="close-diagnostics" class="icon-action cli-close-action" title="Close console" aria-label="Close console">${icon("close")}</button>
                    </div>
                </div>
                ${this.#renderDiagnosticsActiveCommand()}
                <div data-role="diagnostics-log" class="diagnostics-log">
                    ${this.#renderCallLog()}
                </div>
                <form class="cli-prompter" data-role="cli-prompter">
                    <label>
                        <span>Command</span>
                        <input data-role="cli-prompt" list="cli-command-suggestions" placeholder="get-context">
                    </label>
                    <datalist id="cli-command-suggestions">
                        ${this.#renderPromptSuggestions()}
                    </datalist>
                    <button type="button" data-action="run-cli-command" class="primary-action">${icon("terminal")}Run</button>
                </form>
            </aside>
        `;
    }

    /**
     * Render command suggestions for the allowlisted CLI prompt.
     *
     * @returns {string} Datalist option HTML.
     */
    #renderPromptSuggestions() {
        return [
            "get-context --json",
            "memory-structure --json",
            "list-profiles --json",
            "knowledge-status --scope all --json",
            "knowledge-show --scope global --entities --json",
            "show-backlog",
            "log-index",
            "vectorstore-status --json"
        ].map(command => `<option value="${escapeHtml(command)}"></option>`).join("");
    }

    /**
     * Render or clear the currently running command overlay.
     *
     * @returns {void}
     */
    #renderActiveCommand() {
        const host = this.querySelector("[data-command-overlay-host]");
        if (!host) {
            return;
        }
        const activeCommand = this.#state.activeCommand;
        host.innerHTML = activeCommand ? `
            <div class="command-blocking-overlay" role="status" aria-live="polite">
                <span class="loading-spinner"></span>
                <strong>Running command</strong>
                <code>${escapeHtml(activeCommand.command)}</code>
            </div>
        ` : "";
    }

    /**
     * Update diagnostics without remounting the active route.
     *
     * @returns {void}
     */
    #renderDiagnosticsLog() {
        const activeHost = this.querySelector("[data-role='diagnostics-active-command']");
        if (activeHost) {
            activeHost.outerHTML = this.#renderDiagnosticsActiveCommand();
        }
        const host = this.querySelector("[data-role='diagnostics-log']");
        if (host) {
            host.innerHTML = this.#renderCallLog();
            this.#bindCallLogItems();
        }
    }

    /**
     * Render the currently running command inside the diagnostics console.
     *
     * @returns {string} HTML.
     */
    #renderDiagnosticsActiveCommand() {
        const activeCommand = this.#state.activeCommand;
        if (!activeCommand) {
            return `<div data-role="diagnostics-active-command" class="diagnostics-active-strip is-empty">No command is running.</div>`;
        }
        return `
            <div data-role="diagnostics-active-command" class="diagnostics-active-strip">
                <span class="loading-spinner small-spinner"></span>
                <strong>Running</strong>
                <code>${escapeHtml(activeCommand.command)}</code>
            </div>
        `;
    }

    /**
     * Render recent calls.
     *
     * @returns {string} HTML.
     */
    #renderCallLog() {
        const calls = this.#state.callLog;
        if (!calls.length) {
            return `<p class="empty-state">No calls recorded yet.</p>`;
        }
        return calls.map(call => `
            <details class="call-log-item" data-call-id="${escapeHtml(call.id)}" ${this.#openCallIds.has(call.id) ? "open" : ""}>
                <summary>
                    <span class="${call.ok ? "status-dot ok" : "status-dot error"}"></span>
                    <strong>${escapeHtml(call.command.split(" ").slice(-3).join(" ") || "API call")}</strong>
                    <time>${escapeHtml(call.time)} - ${escapeHtml(String(call.durationMs))} ms</time>
                    <button type="button" data-action="delete-cli-call" data-call-id="${escapeHtml(call.id)}" class="icon-action call-delete" title="Delete call">${icon("trash")}</button>
                </summary>
                ${codeBlock({
                    ok: call.ok,
                    code: call.code,
                    command: call.command,
                    data: call.data,
                    stdout: call.stdout,
                    stderr: call.stderr
                }, "json")}
            </details>
        `).join("");
    }

    /**
     * Bind explicit expansion behavior for CLI call log items.
     *
     * @returns {void}
     */
    #bindCallLogItems() {
        this.querySelectorAll(".call-log-item").forEach(details => {
            const summary = details.querySelector("summary");
            summary?.addEventListener("click", event => {
                if (event.target instanceof Element && event.target.closest("button")) {
                    return;
                }
                event.preventDefault();
                details.open = !details.open;
                this.#syncCallLogItem(details);
            });
        });
    }

    /**
     * Persist one call log item expansion state.
     *
     * @param {Element} details Details element.
     * @returns {void}
     */
    #syncCallLogItem(details) {
        const id = details.getAttribute("data-call-id") || "";
        if (!id) {
            return;
        }
        if ("open" in details && details.open) {
            this.#openCallIds.add(id);
            return;
        }
        this.#openCallIds.delete(id);
    }

}

customElements.define(BrainExplorerApp.selector, BrainExplorerApp);
