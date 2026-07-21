/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { escapeHtml } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import { isBacklogPipPriority } from "../validators/backlog-pip-priority.ts";
import type {
    BacklogPipCaptureHandler,
    BacklogPipCreateTaskHandler,
    BacklogPipFormDraft,
    BacklogPipMarkingRectangle,
    BacklogPipTaskViewModel,
} from "../view_models/backlog-pip-view-model.ts";

/**
 * BacklogPip is a self-contained component designed to live inside
 * a Document Picture-in-Picture window. It renders grouped tasks
 * with expandable details, and manages an inline task creation form.
 *
 * @element brain-backlog-pip
 */
export class BacklogPip extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the BacklogPip component in the DOM.
     * @returns {string} The string identifier 'brain-backlog-pip'.
     */
    static get selector(): string {
        return "brain-backlog-pip";
    }

    /**
     * Maintains a private collection of task view models for the backlog pipeline display.
     *
     * @type {BacklogPipTaskViewModel[]}
     */
    #tasks: BacklogPipTaskViewModel[] = [];
    /**
     * Maintains a private set of unique identifiers representing the currently expanded items within the backlog pipeline view.
     *
     * @type {Set<string>}
     */
    #expandedIds = new Set<string>();
    /**
     * Tracks whether the event listeners for the backlog pipeline have been attached to the DOM.
     *
     * @type {boolean}
     */
    #eventsBound = false;
    /**
     * Tracks the visibility state of the backlog item form within the BacklogPip component.
     *
     * @type {boolean}
     */
    #isFormOpen = false;
    /**
     * Tracks the submission state of the BacklogPip component to prevent concurrent requests.
     *
     * @type {boolean}
     */
    #isSubmitting = false;
    /**
     * Stores the current error message associated with the backlog form validation state.
     *
     * @type {string}
     */
    #formError = "";
    /**
     * Maintains the internal state of a draft form for the BacklogPip component, initialized with default values for title, description, and priority.
     *
     * @type {BacklogPipFormDraft}
     */
    #formDraft: BacklogPipFormDraft = { title: "", description: "", priority: "HIGH" };
    /**
     * Stores the base64-encoded data URL of the picture-in-picture image or null if no image is currently loaded.
     *
     * @type {string | null}
     */
    #pipImageDataUrl: string | null = null;
    /**
     * Maintains a private collection of marking rectangles used for the BacklogPip visual representation.
     *
     * @type {BacklogPipMarkingRectangle[]}
     */
    #pipMarkingRects: BacklogPipMarkingRectangle[] = [];

    /**
     * Callback invoked when a screen capture is requested.
     * Must return a Promise resolving to a base64 image data URL.
     *
     * @type {(() => Promise<string | null>) | null}
     */
    onCaptureScreen: BacklogPipCaptureHandler | null = null;

    /**
     * Callback invoked when a new task is created.
     *
     * The resolved result carries the refreshed task list so the PiP owns
     * its transition back to the list after a successful mutation.
     *
     * @type {((taskData: { title: string; description: string; priority: string; image: string | null }) => Promise<{ ok: boolean; tasks?: object[]; message?: string }>) | null}
     */
    onAddTask: BacklogPipCreateTaskHandler | null = null;

    /**
     * Set the task list and re-render.
     *
     * @param {object[]} tasks Parsed task array from BacklogView.
     */
    set tasks(tasks: BacklogPipTaskViewModel[]) {
        this.#tasks = Array.isArray(tasks) ? tasks : [];
        if (!this.#isFormOpen) {
            this.#render();
        }
    }

    /**
     * Lifecycle hook that initializes the component by binding event listeners and executing the initial render process.
     */
    connectedCallback() {
        this.#bindEvents();
        this.#render();
    }

    /**
     * Conditionally renders either the form view or the list view based on the current open state of the form.
     */
    #render() {
        if (this.#isFormOpen) {
            this.#renderForm();
        } else {
            this.#renderList();
        }
    }

    /**
     * Updates the component's inner HTML to render the Backlog PIP layout, including the header with task counts and the grouped task list.
     */
    #renderList() {
        this.innerHTML = `
            <div class="pip-root" style="display: flex; flex-direction: column; height: 100vh; font-family: var(--font); background: var(--bg); color: var(--text);">
                <header class="pip-header" style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong class="pip-title" style="font-size: 14px; color: var(--text-strong); display: flex; align-items: center; gap: 6px;">
                        ${icon("checkSquare")} Backlog PIP
                    </strong>
                    <span class="pip-count" style="font-size: 12px; color: var(--text-muted); margin-left: auto; margin-right: 12px;">
                        ${this.#tasks.length} tasks
                    </span>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <button class="icon-action" data-action="pip-capture-screen" title="Capture screen and create task" style="border: 0; background: transparent; cursor: pointer; color: var(--primary);">${icon("camera")}</button>
                        <button class="icon-action" data-action="pip-add-task" title="Create task" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("plus")}</button>
                    </div>
                </header>
                <main class="pip-body scroll-area" style="flex: 1; overflow-y: auto; padding: 12px; display: grid; gap: 10px; background: color-mix(in srgb, var(--bg), transparent 40%);">
                    ${this.#renderGroups()}
                </main>
            </div>
        `;
    }

    /**
     * Populates the component's innerHTML with a task creation form, including conditional image preview and error messaging, then initializes event bindings and draft restoration.
     */
    #renderForm() {
        this.innerHTML = `
            <div class="pip-root" style="display: flex; flex-direction: column; height: 100vh; font-family: var(--font); background: var(--bg); color: var(--text);">
                <header class="pip-header" style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--border); background: var(--surface-strong);">
                    <strong class="pip-title" style="font-size: 14px; color: var(--text-strong); display: flex; align-items: center; gap: 6px;">
                        ${icon("plus")} New Task (PIP)
                    </strong>
                    <button class="icon-action" data-action="pip-close-form" title="Back" style="border: 0; background: transparent; cursor: pointer; color: var(--text);">${icon("close")}</button>
                </header>
                <form class="pip-add-form" style="padding: 12px; display: flex; flex-direction: column; gap: 8px; flex: 1; overflow-y: auto; background: var(--bg);">
                    <input type="text" id="pip-title-input" placeholder="Title" required style="padding: 6px 8px; font-size: 13px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface-strong); color: var(--text-strong);">
                    <select id="pip-priority-select" style="padding: 6px; font-size: 13px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface-strong); color: var(--text-strong);">
                        <option value="HIGH">HIGH</option>
                        <option value="MEDIUM">MEDIUM</option>
                        <option value="LOW">LOW</option>
                    </select>
                    <textarea id="pip-desc-input" placeholder="Description (use Ctrl+V to paste an image)" required style="padding: 6px 8px; font-size: 13px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface-strong); color: var(--text-strong); min-height: 80px; resize: vertical;"></textarea>
                    
                    <button type="button" class="ghost-action compact-action" data-action="pip-form-capture" style="display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-size: 12px; height: 32px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface-muted); color: var(--primary);">
                        ${icon("camera")} Capture Visual Reference
                    </button>

                    ${this.#pipImageDataUrl ? `
                        <div style="display: flex; flex-direction: column; gap: 6px; border: 1px solid var(--border); padding: 8px; border-radius: 6px; background: var(--surface);">
                            <div class="marking-container" style="position: relative; display: inline-block; max-width: 100%;">
                                <img id="pip-preview-img" src="${this.#pipImageDataUrl}" style="max-width: 100%; display: block; max-height: 200px; object-fit: contain;">
                                <svg id="pip-marking-svg" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; cursor: crosshair; touch-action: none;"></svg>
                            </div>
                            <div style="display: flex; gap: 8px; align-items: center; justify-content: space-between;">
                                <button type="button" class="ghost-action compact-action" data-action="pip-clear-marks" style="padding: 4px 8px; font-size: 11px;">Clear</button>
                                <select id="pip-mark-color" style="padding: 2px 6px; font-size: 11px; border-radius: 4px; border: 1px solid var(--border); background: var(--surface); color: var(--text-strong);">
                                    <option value="red" selected>Rojo</option>
                                    <option value="blue">Azul</option>
                                    <option value="green">Verde</option>
                                    <option value="yellow">Amarillo</option>
                                    <option value="magenta">Rosa</option>
                                </select>
                            </div>
                        </div>
                    ` : ""}
                    
                    ${this.#formError ? `<p role="alert" style="margin: 0; font-size: 12px; color: var(--danger);">${escapeHtml(this.#formError)}</p>` : ""}
                    <button type="submit" class="primary-action" ${this.#isSubmitting ? "disabled" : ""} style="padding: 8px; font-size: 13px; font-weight: bold; border-radius: 4px; margin-top: auto;">${this.#isSubmitting ? "Creating..." : "Create Task"}</button>
                </form>
            </div>
        `;
        this.#bindFormEvents();
        this.#restoreFormDraft();
    }

    /**
     * Save active creation form values before an asynchronous operation.
     *
     * @returns {void}
     */
    #captureFormDraft() {
        const title = this.querySelector("#pip-title-input");
        const description = this.querySelector("#pip-desc-input");
        const priority = this.querySelector("#pip-priority-select");
        if (title instanceof HTMLInputElement) {
            this.#formDraft.title = title.value;
        }
        if (description instanceof HTMLTextAreaElement) {
            this.#formDraft.description = description.value;
        }
        if (priority instanceof HTMLSelectElement && isBacklogPipPriority(priority.value)) {
            this.#formDraft.priority = priority.value;
        }
    }

    /**
     * Restore creation form values after its DOM has been re-rendered.
     *
     * @returns {void}
     */
    #restoreFormDraft() {
        const title = this.querySelector("#pip-title-input");
        const description = this.querySelector("#pip-desc-input");
        const priority = this.querySelector("#pip-priority-select");
        if (title instanceof HTMLInputElement) {
            title.value = this.#formDraft.title;
        }
        if (description instanceof HTMLTextAreaElement) {
            description.value = this.#formDraft.description;
        }
        if (priority instanceof HTMLSelectElement) {
            priority.value = this.#formDraft.priority;
        }
    }

    /**
     * Clear form-only values after dismissal or successful task creation.
     *
     * @returns {void}
     */
    #resetFormDraft() {
        this.#formDraft = { title: "", description: "", priority: "HIGH" };
        this.#formError = "";
    }

    /**
     * Generates an HTML string representing tasks grouped by their domain, sorted alphabetically, or a fallback empty state message.
     * @returns {string} An HTML string containing the grouped task sections or an empty state notification.
     */
    #renderGroups(): string {
        if (!this.#tasks.length) {
            return `<p class="pip-empty" style="text-align: center; color: var(--text-muted); padding: 24px;">No tasks.</p>`;
        }
        const groups = new Map<string, BacklogPipTaskViewModel[]>();
        for (const task of this.#tasks) {
            const list = groups.get(task.domain) || [];
            list.push(task);
            groups.set(task.domain, list);
        }
        const sections: string[] = [];
        const sortedDomains = Array.from(groups.keys()).sort();
        for (const domain of sortedDomains) {
            const tasks = groups.get(domain) ?? [];
            sections.push(`
                <section class="pip-group" style="margin-bottom: 10px;">
                    <h2 class="pip-domain-label" style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--primary); margin-bottom: 4px; border-bottom: 1px solid var(--border); padding-bottom: 2px;">
                        ${escapeHtml(domain)}
                    </h2>
                    <div class="pip-task-list" style="display: grid; gap: 4px;">
                        ${tasks.map(task => this.#renderTask(task)).join("")}
                    </div>
                </section>
            `);
        }
        return sections.join("");
    }

    /**
     * Generates an HTML string representation of a task item, incorporating its status, priority, and expansion state.
     * @param {BacklogPipTaskViewModel} task The view model containing the task's identity, completion status, priority, and descriptive content.
     * @returns {string} An HTML string containing the structured markup for the task's row and optional detail section.
     */
    #renderTask(task: BacklogPipTaskViewModel): string {
        const expanded = this.#expandedIds.has(task.id);
        const statusIcon = task.done
            ? icon("checkSquare")
            : (task.status === "WORKING"
                ? `
                    <div class="working-spinner" style="vertical-align: middle;">
                        <span class="dot dot-blue"></span>
                        <span class="dot dot-cyan"></span>
                        <span class="dot dot-green"></span>
                        <span class="dot dot-yellow"></span>
                        <span class="dot dot-red"></span>
                        <span class="dot dot-pink"></span>
                    </div>
                `
                : icon("clock")
              );
        const priorityClass = task.done
            ? "pip-done"
            : `pip-priority-${String(task.priority).toLowerCase()}`;
        return `
            <div class="pip-task ${priorityClass} ${expanded ? "is-expanded" : ""}" data-pip-task-id="${escapeHtml(task.id)}" style="display: flex; flex-direction: column; background: var(--surface); border-radius: 6px; border: 1px solid var(--border); overflow: hidden;">
                <button class="pip-task-row" data-pip-toggle="${escapeHtml(task.id)}" style="display: flex; align-items: center; gap: 6px; padding: 6px 8px; width: 100%; border: 0; background: transparent; cursor: pointer; text-align: left; font-size: 12px; color: var(--text-strong);">
                    <span class="pip-task-icon" style="display: flex; align-items: center; justify-content: center; width: 18px; height: 18px;">${statusIcon}</span>
                    <span class="pip-task-title" style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-strong); ${task.done ? 'text-decoration: line-through; opacity: 0.6;' : ''}">${escapeHtml(task.title)}</span>
                    <span class="pip-task-chevron" style="display: flex; align-items: center; justify-content: center; width: 18px; height: 18px; color: var(--text-muted);">${icon(expanded ? "chevronDown" : "chevronRight")}</span>
                </button>
                ${expanded ? `
                    <div class="pip-task-detail" style="padding: 6px 8px 8px 8px; border-top: 1px solid var(--border); background: color-mix(in srgb, var(--bg), transparent 60%); font-size: 11px; color: var(--text);">
                        <span style="font-weight: bold; color: var(--primary); margin-right: 8px;">${escapeHtml(task.id)}</span>
                        <span style="background: var(--surface-strong); padding: 1px 4px; border-radius: 3px; font-size: 10px; font-weight: bold;">${escapeHtml(String(task.priority).toUpperCase())}</span>
                        ${task.description ? `<p class="pip-task-desc" style="margin-top: 4px; line-height: 1.4; white-space: pre-wrap;">${escapeHtml(task.description)}</p>` : ""}
                    </div>
                ` : ""}
            </div>
        `;
    }

    /**
     * Idempotently attaches a click event listener to manage the expansion of items, the opening of the task creation form, and the triggering of screen capture functionality.
     */
    #bindEvents() {
        if (this.#eventsBound) return;
        this.#eventsBound = true;

        this.addEventListener("click", async event => {
            const target = event.target instanceof Element ? event.target : null;
            const toggle = target?.closest<HTMLElement>("[data-pip-toggle]");
            if (toggle) {
                const id = toggle.dataset.pipToggle ?? "";
                if (this.#expandedIds.has(id)) {
                    this.#expandedIds.delete(id);
                } else {
                    this.#expandedIds.add(id);
                }
                this.#render();
                return;
            }

            const addBtn = target?.closest("[data-action='pip-add-task']");
            if (addBtn) {
                this.#isFormOpen = true;
                this.#resetFormDraft();
                this.#pipImageDataUrl = null;
                this.#pipMarkingRects = [];
                this.#render();
                return;
            }

            const captureBtn = target?.closest("[data-action='pip-capture-screen']");
            if (captureBtn) {
                if (this.onCaptureScreen) {
                    const dataUrl = await this.onCaptureScreen();
                    if (dataUrl) {
                        this.#isFormOpen = true;
                        this.#resetFormDraft();
                        this.#pipImageDataUrl = dataUrl;
                        this.#pipMarkingRects = [];
                        this.#render();
                    }
                }
            }
        });
    }

    /**
     * Attaches event listeners to the form for handling closure, screen capture, image pasting, and task submission.
     */
    #bindFormEvents() {
        const form = this.querySelector<HTMLFormElement>(".pip-add-form");
        if (!form) return;

        // Close Form
        this.querySelector("[data-action='pip-close-form']")?.addEventListener("click", () => {
            this.#isFormOpen = false;
            this.#resetFormDraft();
            this.#render();
        });

        // Form Screen Capture
        this.querySelector("[data-action='pip-form-capture']")?.addEventListener("click", async () => {
            if (this.onCaptureScreen) {
                this.#captureFormDraft();
                const dataUrl = await this.onCaptureScreen();
                if (dataUrl) {
                    this.#pipImageDataUrl = dataUrl;
                    this.#pipMarkingRects = [];
                    this.#render();
                }
            }
        });

        // Clipboard Paste Listener
        const descInput = this.querySelector<HTMLTextAreaElement>("#pip-desc-input");
        descInput?.addEventListener("paste", (event: ClipboardEvent) => {
            const items = event.clipboardData?.items;
            if (!items) return;
            for (let index = 0; index < items.length; index += 1) {
                const item = items[index];
                if (!item) continue;
                if (item.type.startsWith("image/")) {
                    event.preventDefault();
                    const file = item.getAsFile();
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = () => {
                            const result = reader.result;
                            if (typeof result !== "string") return;
                            this.#pipImageDataUrl = result;
                            this.#pipMarkingRects = [];
                            this.#render();
                            
                            // Insert {ref_image} tag
                            const start = descInput.selectionStart;
                            const end = descInput.selectionEnd;
                            const val = descInput.value;
                            descInput.value = val.slice(0, start) + "{ref_image}" + val.slice(end);
                            descInput.selectionStart = descInput.selectionEnd = start + "{ref_image}".length;
                        };
                        reader.readAsDataURL(file);
                    }
                    break;
                }
            }
        });

        // Image marking canvas interaction
        this.#bindFormImageMarking();

        // Submit form
        form.addEventListener("submit", async event => {
            event.preventDefault();
            this.#captureFormDraft();
            const title = this.#formDraft.title.trim();
            const description = this.#formDraft.description.trim();
            const priority = this.#formDraft.priority;
            
            let bakedImage: string | null = null;
            if (this.#pipImageDataUrl) {
                try {
                    bakedImage = await this.#bakeMarkedImage();
                } catch (e) {
                    console.error("Error baking PiP image:", e);
                }
            }

            if (!this.onAddTask || this.#isSubmitting) {
                return;
            }

            this.#isSubmitting = true;
            this.#formError = "";
            const submitButton = form.querySelector("[type='submit']");
            if (submitButton instanceof HTMLButtonElement) {
                submitButton.disabled = true;
                submitButton.textContent = "Creating...";
            }

            try {
                const completion = await this.onAddTask({ title, description, priority, image: bakedImage });
                if (!completion?.ok) {
                    this.#formError = completion?.message || "Could not create the task.";
                    return;
                }
                if (Array.isArray(completion.tasks)) {
                    this.#tasks = completion.tasks;
                }
                this.#isFormOpen = false;
                this.#resetFormDraft();
                this.#pipImageDataUrl = null;
                this.#pipMarkingRects = [];
            } catch (error) {
                this.#formError = error instanceof Error ? error.message : "Could not create the task.";
            } finally {
                this.#isSubmitting = false;
                this.#render();
            }
        });
    }

    /**
     * Initializes pointer event listeners on an SVG element to enable interactive drawing of colored rectangular markings over a preview image and manages the storage of normalized marking coordinates.
     */
    #bindFormImageMarking() {
        const svg = this.querySelector<SVGSVGElement>("#pip-marking-svg");
        const img = this.querySelector<HTMLImageElement>("#pip-preview-img");
        if (!svg || !img) return;

        let startX = 0, startY = 0;
        let isDrawing = false;
        let activeRect: SVGRectElement | null = null;

        svg.addEventListener("pointerdown", (e: PointerEvent) => {
            e.preventDefault();
            const bounds = svg.getBoundingClientRect();
            startX = e.clientX - bounds.left;
            startY = e.clientY - bounds.top;
            isDrawing = true;
            activeRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
            
            const colorSelect = this.querySelector<HTMLSelectElement>("#pip-mark-color");
            const selectedColor = colorSelect ? colorSelect.value : "red";
            
            activeRect.setAttribute("stroke", selectedColor);
            activeRect.setAttribute("stroke-width", "3");
            activeRect.setAttribute("fill", "none");
            svg.appendChild(activeRect);
        });

        svg.addEventListener("pointermove", (e: PointerEvent) => {
            if (!isDrawing || !activeRect) return;
            const bounds = svg.getBoundingClientRect();
            const curX = e.clientX - bounds.left;
            const curY = e.clientY - bounds.top;
            const x = Math.min(startX, curX);
            const y = Math.min(startY, curY);
            const w = Math.abs(startX - curX);
            const h = Math.abs(startY - curY);
            activeRect.setAttribute("x", String(x));
            activeRect.setAttribute("y", String(y));
            activeRect.setAttribute("width", String(w));
            activeRect.setAttribute("height", String(h));
        });

        svg.addEventListener("pointerup", (e: PointerEvent) => {
            if (!isDrawing || !activeRect) return;
            isDrawing = false;
            const bounds = svg.getBoundingClientRect();
            const curX = e.clientX - bounds.left;
            const curY = e.clientY - bounds.top;
            const x = Math.min(startX, curX);
            const y = Math.min(startY, curY);
            const w = Math.abs(startX - curX);
            const h = Math.abs(startY - curY);

            if (w > 4 && h > 4) {
                const colorSelect = this.querySelector<HTMLSelectElement>("#pip-mark-color");
                const selectedColor = colorSelect ? colorSelect.value : "red";
                this.#pipMarkingRects.push({
                    x: x / bounds.width,
                    y: y / bounds.height,
                    w: w / bounds.width,
                    h: h / bounds.height,
                    color: selectedColor
                });

                // Index number label in SVG
                const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
                text.setAttribute("x", String(x + w - 6));
                text.setAttribute("y", String(y + h - 6));
                text.setAttribute("fill", selectedColor);
                text.setAttribute("font-size", "12");
                text.setAttribute("font-weight", "bold");
                text.setAttribute("text-anchor", "end");
                text.textContent = String(this.#pipMarkingRects.length);
                svg.appendChild(text);
            } else {
                activeRect.remove();
            }
        });

        this.querySelector("[data-action='pip-clear-marks']")?.addEventListener("click", e => {
            e.stopPropagation();
            this.#pipMarkingRects = [];
            svg.innerHTML = "";
        });
    }

    /**
     * Renders the current preview image onto a canvas, overlays defined marking rectangles and labels, and exports the result as a PNG data URL.
     * @returns {Promise<string | null>} A base64 encoded PNG image string containing the marked preview, or null if the image element or canvas context is unavailable.
     */
    async #bakeMarkedImage(): Promise<string | null> {
        const img = this.querySelector<HTMLImageElement>("#pip-preview-img");
        if (!img) return null;
        if (!img.complete) {
            await new Promise<void>(resolve => {
                img.addEventListener("load", () => resolve(), { once: true });
            });
        }
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d");
        if (!ctx) return null;
        ctx.drawImage(img, 0, 0);
        
        this.#pipMarkingRects.forEach((r, i) => {
            ctx.strokeStyle = r.color || "red";
            ctx.lineWidth = 3;
            ctx.strokeRect(
                r.x * img.naturalWidth,
                r.y * img.naturalHeight,
                r.w * img.naturalWidth,
                r.h * img.naturalHeight
            );
            
            // Draw number label
            ctx.fillStyle = r.color || "red";
            ctx.font = "bold 16px sans-serif";
            ctx.textBaseline = "bottom";
            ctx.textAlign = "right";
            ctx.fillText(
                String(i + 1),
                (r.x + r.w) * img.naturalWidth - 6,
                (r.y + r.h) * img.naturalHeight - 6
            );
        });
        return canvas.toDataURL("image/png");
    }
}

customElements.define(BacklogPip.selector, BacklogPip);
