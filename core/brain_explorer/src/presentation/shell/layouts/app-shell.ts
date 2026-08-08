/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { BrainApiClient } from "../../../infrastructure/shared/http/clients/brain-api-client.ts";
import { codeBlock, escapeHtml } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import { notificationText } from "../../shared/utils/notification-message.ts";
import { DEFAULT_SHELL_ROUTE, isShellRouteId, SHELL_ROUTES } from "../config/shell-routes.ts";
import { handleShellSearchShortcut } from "../controllers/shell-keyboard-controller.ts";
import { renderShellNavigation } from "../renderers/shell-navigation-renderer.ts";
import type { RouteId } from "../../../application/shell/contracts/shell-contracts.ts";
import type { AppState } from "../state/app-state.ts";
import type { ComponentContext, ReactiveContentFilterLayout, TargetFocusableLayout } from "../../shared/view_models/component-context-view-model.ts";
import type { ApiRequestEventDetail, NotificationTimerViewModel, ShellNotificationInput } from "../view_models/app-shell-view-model.ts";

/**
 * BrainExplorerApp composes the persistent shell around route-level Web Components.
 */
export class BrainExplorerApp extends HTMLElement {
    /**
     * Registered Custom Element tag used by the document bootstrap.
     * @returns {string} The string identifier used as the selector for the application shell.
     */
    static get selector() {
        return "brain-explorer-app";
    }

    /**
     * Browser API adapter injected by the application bootstrap.
     * @type {BrainApiClient | null}
     */
    #api: BrainApiClient | null = null;
    /**
     * Presentation state store injected alongside the API adapter.
     * @type {AppState | null}
     */
    #state: AppState | null = null;
    /**
     * Route currently mounted in the shell content outlet.
     * @type {RouteId}
     */
    #activeRouteId: RouteId = "dashboard";
    #preservedQueryView: HTMLElement | null = null;
    /**
     * Prevents duplicate subscriptions to `AppState` lifecycle events.
     * @type {boolean}
     */
    #stateListenersBound = false;
    /**
     * Prevents duplicate subscriptions to API request lifecycle events.
     * @type {boolean}
     */
    #apiListenersBound = false;
    /**
     * Number of API requests currently visible to the global progress zone.
     * @type {number}
     */
    #activeRequestCount = 0;
    /**
     * Identifiers of diagnostics call records expanded by the user.
     * @type {Set<string>}
     */
    #openCallIds = new Set<string>();
    /**
     * Dismissal timers indexed by notification identity.
     * @type {Map<string, NotificationTimerViewModel>}
     */
    #notificationTimers = new Map<string, NotificationTimerViewModel>();
    /**
     * Debounces reactive filtering of the currently mounted layout.
     * @type {number | null}
     */
    #reactiveSearchTimer: number | null = null;
    /**
     * Stable listener delegating the global search shortcut to its feature controller.
     * @type {(event: KeyboardEvent) => void}
     */
    #handleGlobalKeyDown = (event: KeyboardEvent): void => handleShellSearchShortcut(this, event);
    /**
     * Original global error hook restored when the shell detaches.
     * @type {OnErrorEventHandler | null}
     */
    #previousWindowOnError: OnErrorEventHandler | null = null;
    /**
     * Prevents duplicate global error subscriptions across remounts.
     * @type {boolean}
     */
    #globalErrorHandlingBound = false;

    /**
     * Assign runtime dependencies and initialize shell state and bindings.
     *
     * @param {ComponentContext} context Component context containing API adapter and presentation state store.
     * @returns {void}
     */
    set context(context: ComponentContext) {
        this.#api = context.api;
        this.#state = context.state;
        this.#bindStateEvents();
        this.#bindApiEvents();
        this.#renderShell();
    }

    /**
     * Render shell and attach global window event listeners when mounted to the DOM.
     *
     * @returns {void}
     */
    connectedCallback(): void {
        if (this.#state && this.#api && !this.querySelector(".app-shell")) {
            this.#renderShell();
        }
        window.addEventListener("keydown", this.#handleGlobalKeyDown);
        this.#bindGlobalErrorHandling();
    }

    /**
     * Remove global window event listeners and active timers when unmounted from the DOM.
     *
     * @returns {void}
     */
    disconnectedCallback(): void {
        window.removeEventListener("keydown", this.#handleGlobalKeyDown);
        this.#unbindGlobalErrorHandling();
        this.#notificationTimers.forEach(record => window.clearTimeout(record.timer));
        this.#notificationTimers.clear();
        if (this.#reactiveSearchTimer !== null) {
            window.clearTimeout(this.#reactiveSearchTimer);
        }
    }

    /**
     * Reports a captured global browser or resource failure through the official notification channel.
     *
     * @param {ErrorEvent | Event} event Captured browser error event or element resource loading failure event.
     * @returns {void}
     */
    #handleGlobalError = (event: ErrorEvent | Event): void => {
        if (event instanceof ErrorEvent) {
            const fileName = event.filename ? event.filename.split("/").pop() || "" : "";
            const source = fileName ? `${fileName}:${event.lineno || 0}` : "Script runtime";
            const message = event.error?.message || event.message || "Unhandled script error.";
            this.#pushNotification({ tone: "error", title: "Runtime error", message: `${source} - ${message}` });
            return;
        }

        const target = event.target;
        if (target instanceof HTMLElement) {
            const tag = target.tagName.toLowerCase();
            const src = (target as HTMLImageElement | HTMLScriptElement | HTMLAudioElement).src
                || (target as HTMLLinkElement).href
                || "";
            const resourceName = src ? src.split("/").pop() || src : tag;
            const message = src ? `Failed to load <${tag}>: ${resourceName}` : `Failed to load <${tag}> element.`;
            this.#pushNotification({ tone: "error", title: "Resource error", message });
            return;
        }

        const message = (event as CustomEvent).detail || "Unexpected browser event error.";
        this.#pushNotification({ tone: "error", title: "Browser error", message: String(message) });
    };

    /**
     * Reports unhandled async promise rejections through the official notification channel.
     *
     * @param {PromiseRejectionEvent} event Unhandled promise rejection event containing the rejection reason.
     * @returns {void}
     */
    #handleUnhandledRejection = (event: PromiseRejectionEvent): void => {
        const reason = event.reason;
        const message = reason instanceof Error ? reason.message : String(reason || "Unhandled promise rejection.");
        const title = reason instanceof Error && reason.name && reason.name !== "Error" ? reason.name : "Async error";
        this.#pushNotification({ tone: "error", title, message });
    };

    /**
     * Bind window error listeners and capture runtime/resource errors into the notification stack.
     *
     * @returns {void}
     */
    #bindGlobalErrorHandling(): void {
        if (this.#globalErrorHandlingBound) return;
        this.#previousWindowOnError = window.onerror;
        window.onerror = (message, source, lineno, _column, error) => {
            const fileName = source ? String(source).split("/").pop() || "" : "";
            const location = fileName ? `${fileName}:${lineno || 0}` : "Runtime";
            const detail = error?.message || String(message || "Unexpected browser error.");
            this.#pushNotification({ tone: "error", title: "Runtime error", message: `${location} - ${detail}` });
            return this.#previousWindowOnError?.(message, source, lineno, _column, error) ?? false;
        };
        window.addEventListener("error", this.#handleGlobalError, true);
        window.addEventListener("unhandledrejection", this.#handleUnhandledRejection);
        this.#globalErrorHandlingBound = true;
    }

    /**
     * Restore the global browser error hooks owned by this shell instance.
     *
     * @returns {void}
     */
    #unbindGlobalErrorHandling(): void {
        if (!this.#globalErrorHandlingBound) return;
        window.removeEventListener("error", this.#handleGlobalError, true);
        window.removeEventListener("unhandledrejection", this.#handleUnhandledRejection);
        this.#globalErrorHandlingBound = false;
        if (window.onerror) window.onerror = this.#previousWindowOnError;
        this.#previousWindowOnError = null;
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
                        <img class="brain-mark" src="./brain-explorer-favicon.png" alt="DigiDog">
                        <span style="font-size: 16px; font-weight: 600; color: var(--text-normal); display: inline-flex; align-items: center;">
                            Digidog ~&nbsp;
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
                            <summary title="Search sources and methods" aria-label="Search sources and methods">${icon("sliders")}</summary>
                            <div class="action-menu-panel search-options-panel">
                                <fieldset data-search-group="search-source">
                                    <legend>Sources</legend>
                                    <label class="search-options-master"><input type="checkbox" data-search-select-all="search-source" aria-label="Select or deselect all sources" checked>All sources</label>
                                    <label><input type="checkbox" name="search-source" value="memory" checked>Memory</label>
                                    <label><input type="checkbox" name="search-source" value="knowledge" checked>Knowledge</label>
                                    <label><input type="checkbox" name="search-source" value="messages" checked>Messages</label>
                                    <label><input type="checkbox" name="search-source" value="pictures" checked>Pictures</label>
                                    <label><input type="checkbox" name="search-source" value="backlog" checked>Backlog</label>
                                </fieldset>
                                <fieldset data-search-group="search-mechanism">
                                    <legend>Methods</legend>
                                    <label class="search-options-master"><input type="checkbox" data-search-select-all="search-mechanism" aria-label="Select or deselect all methods" checked>All methods</label>
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
                        ${renderShellNavigation(this.#state.route, this.#preservedQueryView !== null)}
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
        const persistedWorkspace = localStorage.getItem("active_project_path")?.trim() || null;
        if (persistedWorkspace) {
            this.#api.setWorkspaceRootOverride(persistedWorkspace);
        }
        this.#mountRoute();
        this.#syncFooter();
        this.#renderDiagnosticsPanel();
        this.#renderActiveCommand();
        const api = this.#api;
        api.health().then(res => {
            const defaultPath = res.data?.workspaceRoot ?? "";
            if (defaultPath) {
                // Fetch and populate registered projects dropdown
                    api.getProjects().then((projectsRes) => {
                        const summaryEl = this.querySelector<HTMLElement>("[data-role='project-selector-summary']");
                        const optionsEl = this.querySelector<HTMLElement>("[data-role='project-selector-options']");
                        if (summaryEl && optionsEl && projectsRes.data?.projects) {
                            optionsEl.innerHTML = "";
                            let activePath = localStorage.getItem("active_project_path");
                            const allProjects = [...projectsRes.data.projects];
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
                    }).catch((err: unknown) => console.error("Error fetching projects for selector:", err));
            }
        }).catch((err: unknown) => console.error("Error fetching health for project indicator:", err));
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
        const api = this.#api;
        const state = this.#state;
        api.addEventListener("request-start", event => {
            if (!(event instanceof CustomEvent)) return;
            const detail: ApiRequestEventDetail = event.detail;
            this.#activeRequestCount += 1;
            state.setActiveCommand(detail.command || "CLI");
        });
        api.addEventListener("request-end", event => {
            if (!(event instanceof CustomEvent)) return;
            const detail: ApiRequestEventDetail = event.detail;
            this.#activeRequestCount = Math.max(0, this.#activeRequestCount - 1);
            if (this.#activeRequestCount === 0) {
                state.clearActiveCommand();
            }
            const payload = detail.payload;
            const method = detail.method || "GET";
            const feedback = payload
                ? notificationText(payload, method, detail.command || "")
                : null;
            if (payload && !payload.ok) {
                this.#pushNotification({
                    tone: "error",
                    title: "Could not complete",
                    message: feedback?.message ?? "The request failed."
                });
            } else if (payload && method !== "GET") {
                this.#pushNotification({
                    tone: "success",
                    title: feedback?.title ?? "Completed",
                    message: feedback?.message ?? "The mutation completed successfully."
                });
            }
        });
        this.#apiListenersBound = true;
    }

    /**
     * Add one timed, hover-pausable notification pill to the global stack.
     *
     * @param {ShellNotificationInput} input Notification tone, heading, and human-readable body.
     * @returns {void} Nothing; the method mutates only the mounted notification region.
     */
    #pushNotification(input: ShellNotificationInput): void {
        const { tone = "info", title = "Message", message = "" } = input;
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
            if (event.currentTarget instanceof Element) event.currentTarget.setAttribute("aria-expanded", String(expanded));
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
        const state = this.#state;
        if (!shell || !state) {
            return;
        }
        shell.addEventListener("click", event => this.#handleShellClick(event));
        const syncTooltipAnchor = (event: Event): void => {
            const target = event.target instanceof Element
                ? event.target.closest<HTMLElement>(".side-nav-item, .sidebar-collapse")
                : null;
            if (target) this.#syncTooltipAnchor(target);
        };
        shell.addEventListener("pointerover", syncTooltipAnchor);
        shell.addEventListener("focusin", syncTooltipAnchor);
        shell.addEventListener("submit", event => {
            if (event.target instanceof Element && event.target.matches("[data-role='cli-prompter']")) {
                event.preventDefault();
                this.#runCliPrompt();
            }
        });
        const searchInput = this.querySelector<HTMLInputElement>("[data-role='global-shell-search']");
        searchInput?.addEventListener("input", event => {
            const value = event.currentTarget instanceof HTMLInputElement ? event.currentTarget.value : "";
            this.#scheduleReactiveSearch(value);
        });
        searchInput?.addEventListener("keydown", event => {
            if (!(event instanceof KeyboardEvent) || event.key !== "Enter") return;
            const value = event.currentTarget instanceof HTMLInputElement ? event.currentTarget.value.trim() : "";
            const options = this.#selectedSearchOptions();
            if (!options.sources.length || !options.mechanisms.length) {
                this.#pushNotification({ tone: "error", title: "Search filters required", message: "Please select at least one source and method." });
                return;
            }
            if (!value) {
                state.setRoute("query");
                return;
            }
            if (this.#reactiveSearchTimer !== null) window.clearTimeout(this.#reactiveSearchTimer);
            this.querySelector(".search-options-menu")?.removeAttribute("open");
            state.setPendingQuery(value, options);
        });
        this.querySelector(".search-options-panel")?.addEventListener("change", event => this.#handleSearchOptionChange(event));
        this.#syncSearchGroupMasters();
    }

    /**
     * Anchor a collapsed-rail tooltip to the live centre of its invoking control.
     *
     * @param {HTMLElement} target Navigation control that owns the tooltip.
     * @returns {void} Nothing.
     */
    #syncTooltipAnchor(target: HTMLElement): void {
        const bounds = target.getBoundingClientRect();
        target.style.setProperty("--tooltip-top", `${Math.round(bounds.top + bounds.height / 2)}px`);
    }

    /**
     * Collect non-exclusive search source and mechanism selections.
     * @returns {Record<string, string[]>} A record mapping 'sources' and 'mechanisms' keys to arrays of their respective selected input values.
     */
    #selectedSearchOptions(): { sources: string[]; mechanisms: string[] } {
        const selected = (name: string): string[] => Array.from(this.querySelectorAll<HTMLInputElement>(`input[name='${name}']:checked`))
            .map(input => input.value);
        return { sources: selected("search-source"), mechanisms: selected("search-mechanism") };
    }

    /** Toggle one option group or synchronize its accessible master checkbox. */
    #handleSearchOptionChange(event: Event): void {
        const input = event.target instanceof HTMLInputElement ? event.target : null;
        if (!input) return;
        const groupName = input.dataset.searchSelectAll;
        if (groupName) {
            this.querySelectorAll<HTMLInputElement>(`input[name='${groupName}']`).forEach(child => {
                child.checked = input.checked;
            });
        }
        this.#syncSearchGroupMasters();
    }

    /** Reflect checked, unchecked, and partial child state in both master controls. */
    #syncSearchGroupMasters(): void {
        this.querySelectorAll<HTMLInputElement>("[data-search-select-all]").forEach(master => {
            const name = master.dataset.searchSelectAll || "";
            const children = Array.from(this.querySelectorAll<HTMLInputElement>(`input[name='${name}']`));
            const checkedCount = children.filter(child => child.checked).length;
            master.checked = children.length > 0 && checkedCount === children.length;
            master.indeterminate = checkedCount > 0 && checkedCount < children.length;
        });
    }

    /** Debounce local filtering and keep one-character input from narrowing a layout. */
    #scheduleReactiveSearch(value: string): void {
        if (this.#reactiveSearchTimer !== null) window.clearTimeout(this.#reactiveSearchTimer);
        const normalized = value.trim();
        this.#reactiveSearchTimer = window.setTimeout(() => {
            this.#reactiveSearchTimer = null;
            this.#applyReactiveSearch(normalized.length >= 2 ? normalized : "");
        }, 200);
    }

    /** Forward the reactive phrase to the mounted route's existing local filter control. */
    #applyReactiveSearch(query: string): void {
        const routeView = this.querySelector<HTMLElement>("[data-route-host] > *") as (HTMLElement & Partial<ReactiveContentFilterLayout>) | null;
        if (this.#activeRouteId === "query") {
            routeView?.applyReactiveContentFilter?.(query);
            return;
        }

        const routeSource: Partial<Record<RouteId, string>> = {
            memory: "memory", knowledge: "knowledge", messages: "messages", pictures: "pictures", backlog: "backlog"
        };
        const source = routeSource[this.#activeRouteId];
        if (!source || !this.#selectedSearchOptions().sources.includes(source)) return;
        routeView?.applyReactiveContentFilter?.(query);
    }

    /**
     * Handle shell-level click actions.
     *
     * @param {Event} event DOM click event.
     * @returns {void}
     */
    #handleShellClick(event: Event): void {
        const state = this.#state;
        if (!state) return;
        const target = event.target instanceof Element ? event.target : null;
        this.#handleDropdownMenus(target);
        if (state.sidebarOpen && target && !target.closest(".side-nav")) {
            state.closeSidebar();
        }
        const routeButton = target?.closest("[data-route]");
        if (routeButton) {
            const routeId = routeButton.getAttribute("data-route");
            if (isShellRouteId(routeId)) state.setRoute(routeId);
            state.closeSidebar();
            return;
        }
        const actionButton = target?.closest("[data-action]");
        const action = actionButton?.getAttribute("data-action") || "";
        if (action === "toggle-theme") {
            state.toggleTheme();
        }
        if (action === "play-latest-voice") {
            this.#playLatestVoice();
        }
        if (action === "toggle-diagnostics") {
            state.toggleDiagnostics();
        }
        if (action === "close-diagnostics") {
            state.closeDiagnostics();
        }
        if (action === "clear-cli-log") {
            this.#openCallIds.clear();
            state.clearCallLog();
        }
        if (action === "delete-cli-call") {
            const callId = actionButton?.getAttribute("data-call-id") || "";
            this.#openCallIds.delete(callId);
            state.removeCallLogItem(callId);
        }
        if (action === "toggle-sidebar") {
            state.toggleSidebar();
        }
        if (action === "return-to-results") {
            state.setRoute("query");
        }
        if (action === "run-cli-command") {
            this.#runCliPrompt();
        }
    }

    /**
     * Replay the latest persisted voice without requesting new synthesis.
     */
    #playLatestVoice() {
        if (!this.#api) return;
        void this.#api.replayVoiceMessage().catch(() => undefined);
    }

    /**
     * Keep native details dropdowns mutually dismissible across route components.
     *
     * @param {Element|null} target Click target.
     * @returns {void}
     */
    #handleDropdownMenus(target: Element | null): void {
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
     * Mount the active route component only when the route changes.
     *
     * @returns {void}
     */
    #mountRoute() {
        const state = this.#state;
        const api = this.#api;
        if (!state || !api) return;
        const route = SHELL_ROUTES.find(item => item.id === state.route) ?? DEFAULT_SHELL_ROUTE;
        const host = this.querySelector("[data-route-host]");
        const refreshPendingQuery = route.id === "query" && Boolean(state.pendingQuery);
        if (!host) return;

        const mountedElement = host.firstElementChild as HTMLElement | null;
        if (this.#activeRouteId === "query" && mountedElement?.querySelector(".query-results")) {
            this.#preservedQueryView = mountedElement;
        }

        const activeRouteIsMounted = mountedElement !== null && this.#activeRouteId === route.id;
        if (activeRouteIsMounted && !refreshPendingQuery) {
            this.#focusMountedRouteTarget(route.id, mountedElement, state);
            this.#syncActiveNav();
            return;
        }

        if (route.id === "query" && this.#preservedQueryView && !refreshPendingQuery) {
            host.setAttribute("aria-label", route.label);
            host.replaceChildren(this.#preservedQueryView);
            this.#activeRouteId = route.id;
            this.#focusMountedRouteTarget(route.id, this.#preservedQueryView, state);
            this.#syncActiveNav();
            return;
        }

        const element = document.createElement(route.element);
        if ("context" in element) element.context = { api, state };
        host.setAttribute("aria-label", route.label);
        host.replaceChildren(element);
        this.#activeRouteId = route.id;
        this.#focusMountedRouteTarget(route.id, element, state);
        this.#syncActiveNav();
    }

    /** Consume and delegate one pending target only for contract-aware layouts. */
    #focusMountedRouteTarget(route: RouteId, element: HTMLElement | null, state: AppState): void {
        if (!element || !("focusTarget" in element) || typeof (element as Partial<TargetFocusableLayout>).focusTarget !== "function") {
            return;
        }
        const target = state.consumeRouteTarget(route);
        if (!target) {
            return;
        }
        const focusResult = (element as HTMLElement & TargetFocusableLayout).focusTarget(target);
        if (focusResult instanceof Promise) {
            void focusResult.catch(() => undefined);
        }
    }

    /**
     * Update navigation active styles without rebuilding the route.
     *
     * @returns {void}
     */
    #syncActiveNav() {
        const state = this.#state;
        if (!state) return;
        this.querySelectorAll("[data-route]").forEach(button => {
            button.classList.toggle("is-active", button.getAttribute("data-route") === state.route);
        });
        const returnButton = this.querySelector<HTMLButtonElement>("[data-action=\"return-to-results\"]");
        if (returnButton) returnButton.hidden = this.#preservedQueryView === null || state.route === "query";
    }

    /**
     * Update theme button and document theme.
     *
     * @returns {void}
     */
    #syncTheme() {
        const state = this.#state;
        if (!state) return;
        document.documentElement.dataset.theme = state.theme;
        const button = this.querySelector("[data-action='toggle-theme']");
        if (!button) {
            return;
        }
        button.innerHTML = `
            ${icon(state.theme === "dark" ? "sun" : "moon")}
        `;
    }

    /**
     * Update overlay sidebar width, label, and icon without touching routes.
     *
     * @returns {void}
     */
    #syncSidebar() {
        const state = this.#state;
        if (!state) return;
        const shell = this.querySelector(".app-shell");
        const button = this.querySelector("[data-action='toggle-sidebar']");
        shell?.classList.toggle("is-sidebar-open", state.sidebarOpen);
        shell?.classList.toggle("is-sidebar-collapsed", !state.sidebarOpen);
        if (!button) {
            return;
        }
        const label = state.sidebarOpen ? "Collapse" : "Expand";
        const iconName = state.sidebarOpen ? "collapseLeft" : "expandRight";
        if (!(button instanceof HTMLElement)) return;
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
        const stateStore = this.#state;
        if (!stateStore) return;
        const route = SHELL_ROUTES.find(item => item.id === stateStore.route) ?? DEFAULT_SHELL_ROUTE;
        const routeLabel = this.querySelector("[data-role='footer-route']");
        const callLabel = this.querySelector("[data-role='footer-call']");
        const lastCall = stateStore.callLog[0];
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
        const state = this.#state;
        const api = this.#api;
        if (!state || !api) return;
        const input = this.querySelector<HTMLInputElement>("[data-role='cli-prompt']");
        const command = input?.value?.trim() || "";
        if (!command) {
            return;
        }
        state.setActiveCommand(command);
        const result = await api.runCli(command);
        state.setLastResult(result);
    }

    /**
     * Render diagnostics drawer in its isolated overlay host.
     *
     * @returns {void}
     */
    #renderDiagnosticsPanel() {
        const state = this.#state;
        if (!state) return;
        const host = this.querySelector("[data-diagnostics-host]");
        if (!host) {
            return;
        }
        host.innerHTML = state.diagnosticsOpen ? this.#renderDiagnosticsDrawer() : "";
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
        const activeCommand = this.#state?.activeCommand;
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
    #renderDiagnosticsActiveCommand(): string {
        const activeCommand = this.#state?.activeCommand;
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
    #renderCallLog(): string {
        const calls = this.#state?.callLog ?? [];
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
    #bindCallLogItems(): void {
        this.querySelectorAll<HTMLDetailsElement>(".call-log-item").forEach(details => {
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
     * @param {HTMLDetailsElement} details Native details element whose expanded
     * state must be mirrored in the shell's persistent expansion registry.
     * @returns {void}
     */
    #syncCallLogItem(details: HTMLDetailsElement): void {
        const id = details.getAttribute("data-call-id") || "";
        if (!id) {
            return;
        }
        if (details.open) {
            this.#openCallIds.add(id);
            return;
        }
        this.#openCallIds.delete(id);
    }

}

customElements.define(BrainExplorerApp.selector, BrainExplorerApp);
