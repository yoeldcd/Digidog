/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { icon } from "../../shared/utils/icons.ts";
import type { CanvasInteraction, CanvasPoint, MarkType, VisualMark } from "../view_models/visual-reference-editor-view-model.ts";

/**
 * Narrow a raw shape-control value to one supported visual-reference mark type.
 *
 * @param {string | undefined} value Untrusted string read from the native shape selector.
 * @returns {boolean} True only when the editor has rendering and interaction semantics for it.
 */
function isMarkType(value: string | undefined): value is MarkType {
    return value === "rectangle" || value === "arrow" || value === "path" || value === "label";
}

/**
 * VisualReferenceEditor owns image loading, canvas marking, selection, and PNG export.
 *
 * @element brain-visual-reference-editor
 */
export class VisualReferenceEditor extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the VisualReferenceEditor component in the DOM.
     * @returns {string} A string representing the component's DOM selector.
     */
    static get selector() {
        return "brain-visual-reference-editor";
    }

    /**
     * Holds a reference to the HTML image element used for visual reference, or null if no image is currently assigned.
     *
     * @type {HTMLImageElement | null}
     */
    #image: HTMLImageElement | null = null;
    /**
     * Tracks the asynchronous loading state of the visual reference image.
     *
     * @type {Promise<boolean>}
     */
    #imageLoad: Promise<boolean> = Promise.resolve(false);
    /**
     * Maintains a private collection of visual mark entities used within the reference editor.
     *
     * @type {VisualMark[]}
     */
    #marks: VisualMark[] = [];
    /**
     * Tracks the zero-based index of the currently selected mark within the visual reference editor, defaulting to -1 to indicate no selection.
     *
     * @type {number}
     */
    #selectedMarkIndex: number = -1;
    /**
     * Stores the current unsaved text input for a label within the visual reference editor.
     *
     * @type {string}
     */
    #labelDraft: string = "";

    /**
     * Render the editor once when it joins the document.
     */
    connectedCallback(): void {
        if (this.childElementCount) return;
        this.innerHTML = `
            <div class="marking-container">
                <canvas data-role="marking-canvas" aria-label="Image marking canvas"></canvas>
            </div>
            <details class="marking-toolbar-pill">
                <summary>${icon("edit")}<span>Marks</span>${icon("chevronDown")}</summary>
                <div class="marking-toolbar">
                    <label class="mark-color-control"><span>Color</span><input type="color" data-action="change-mark-color" value="#ff3b30" aria-label="Mark color"></label>
                    <button type="button" class="mark-delete-control" data-action="delete-selected-mark" title="Delete selected mark" aria-label="Delete selected mark" disabled>${icon("trash")}</button>
                    <label class="mark-shape-control"><span>Shape</span><select data-action="change-mark-shape"><option value="rectangle">Rectangle</option><option value="arrow">Arrow</option><option value="path">Path</option><option value="label">LABEL</option></select></label>
                    <label class="mark-label-control"><span>Label</span><input type="text" data-action="change-mark-label" placeholder="LABEL text"></label>
                </div>
            </details>
        `;
        this.#bindEvents();
        this.reset();
    }

    /**
     * Load an image as the immutable base layer of the editor canvas.
     * @param {string} source The URL or data URI of the image to be loaded into the editor.
     * @returns {Promise<boolean>} A promise that resolves to true if the image was successfully loaded and the canvas initialized, or false otherwise.
     */
    loadImage(source: string): Promise<boolean> {
        this.#marks = [];
        this.#selectedMarkIndex = -1;
        this.#labelDraft = "";
        this.#image = null;
        this.#imageLoad = new Promise(resolve => {
            const image = new Image();
            image.onload = () => {
                this.#image = image;
                const canvas = this.#canvas();
                if (!canvas) {
                    resolve(false);
                    return;
                }
                canvas.width = image.naturalWidth;
                canvas.height = image.naturalHeight;
                this.hidden = false;
                this.#renderCanvas();
                resolve(true);
            };
            image.onerror = () => resolve(false);
            image.src = source;
        });
        return this.#imageLoad;
    }

    /**
     * Clear the current image and all transient mark state.
     */
    reset(): void {
        this.#image = null;
        this.#imageLoad = Promise.resolve(false);
        this.#marks = [];
        this.#selectedMarkIndex = -1;
        this.#labelDraft = "";
        const canvas = this.#canvas();
        if (canvas) {
            canvas.width = 1;
            canvas.height = 1;
        }
        this.hidden = true;
    }

    /**
     * Export the canvas through the same renderer used by the interactive preview.
     * @returns {Promise<string | null>} A base64-encoded PNG image string, or null if the image has not loaded or the canvas is unavailable.
     */
    async exportPng(): Promise<string | null> {
        if (!await this.#imageLoad) return null;
        const canvas = this.#canvas();
        if (!canvas || !this.#image) return null;
        this.#renderCanvas(false);
        const result = canvas.toDataURL("image/png");
        this.#renderCanvas(true);
        return result;
    }

    /**
     * Return the editor canvas when it is mounted.
     * @returns {HTMLCanvasElement | null} The HTMLCanvasElement if found and valid, otherwise null.
     */
    #canvas(): HTMLCanvasElement | null {
        const canvas = this.querySelector<HTMLCanvasElement>("[data-role='marking-canvas']");
        return canvas instanceof HTMLCanvasElement ? canvas : null;
    }

    /**
     * Bind canvas gestures and toolbar controls.
     */
    #bindEvents(): void {
        const canvas = this.#canvas();
        if (!canvas) return;
        let interaction: CanvasInteraction | null = null;
        const point = (event: PointerEvent): CanvasPoint => {
            const bounds = canvas.getBoundingClientRect();
            return {
                x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / Math.max(1, bounds.width))),
                y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / Math.max(1, bounds.height))),
                bounds
            };
        };
        canvas.addEventListener("pointerdown", event => {
            event.preventDefault();
            const start = point(event);
            const selectedIndex = this.#markIndexAtPoint(start.x, start.y, start.bounds);
            if (selectedIndex >= 0) {
                const selectedMark = this.#marks[selectedIndex];
                if (!selectedMark) return;
                this.#selectedMarkIndex = selectedIndex;
                interaction = {
                    mode: "drag",
                    index: selectedIndex,
                    start,
                    original: structuredClone(selectedMark)
                };
                canvas.setPointerCapture(event.pointerId);
                this.#renderCanvas();
                return;
            }
            const selectedType = this.querySelector<HTMLSelectElement>("[data-action='change-mark-shape']")?.value;
            const type: MarkType = isMarkType(selectedType) ? selectedType : "rectangle";
            const color = this.querySelector<HTMLInputElement>("[data-action='change-mark-color']")?.value || "#ff3b30";
            if (type === "label") {
                const labelInput = this.querySelector<HTMLInputElement>("[data-action='change-mark-label']");
                const label = labelInput?.value.trim() || "";
                if (!label) {
                    labelInput?.focus();
                    return;
                }
                this.#marks.push({ type, x: start.x, y: start.y, w: 0, h: 0, points: null, color, label });
                this.#selectedMarkIndex = this.#marks.length - 1;
                this.#labelDraft = label;
                this.#renderCanvas();
                return;
            }
            const drawType: Exclude<MarkType, "label"> = type;
            const index = this.#marks.length;
            this.#marks.push({
                type: drawType,
                x: start.x,
                y: start.y,
                w: 0,
                h: 0,
                points: drawType === "path" ? [{ x: start.x, y: start.y }] : null,
                color,
                label: String(this.#shapeMarkCount() + 1)
            });
            this.#selectedMarkIndex = index;
            interaction = { mode: "draw", index, start, type: drawType };
            canvas.setPointerCapture(event.pointerId);
            this.#renderCanvas();
        });
        canvas.addEventListener("pointermove", event => {
            if (!interaction) return;
            const current = point(event);
            if (interaction.mode === "drag") {
                const dx = current.x - interaction.start.x;
                const dy = current.y - interaction.start.y;
                const original = interaction.original;
                const mark = { ...original, x: original.x + dx, y: original.y + dy };
                if (mark.points && original.points) {
                    mark.points = original.points.map(item => ({ x: item.x + dx, y: item.y + dy }));
                }
                this.#marks[interaction.index] = mark;
            } else {
                const mark = this.#marks[interaction.index];
                if (!mark) return;
                mark.w = current.x - interaction.start.x;
                mark.h = current.y - interaction.start.y;
                if (interaction.type === "path" && mark.points) mark.points.push({ x: current.x, y: current.y });
            }
            this.#renderCanvas();
        });
        canvas.addEventListener("pointerup", event => {
            if (!interaction) return;
            const current = point(event);
            if (interaction.mode === "draw") {
                const mark = this.#marks[interaction.index];
                if (!mark) return;
                mark.w = current.x - interaction.start.x;
                mark.h = current.y - interaction.start.y;
                const valid = interaction.type === "path"
                    ? (mark.points?.length || 0) > 2
                    : Math.hypot(mark.w, mark.h) > .01;
                if (!valid) {
                    this.#marks.splice(interaction.index, 1);
                    this.#selectedMarkIndex = -1;
                    this.#renumberShapeMarks();
                }
            }
            interaction = null;
            canvas.releasePointerCapture?.(event.pointerId);
            this.#renderCanvas();
        });
        this.querySelector("[data-action='delete-selected-mark']")?.addEventListener("click", event => {
            event.stopPropagation();
            if (this.#selectedMarkIndex < 0 || this.#selectedMarkIndex >= this.#marks.length) return;
            this.#marks.splice(this.#selectedMarkIndex, 1);
            this.#selectedMarkIndex = -1;
            this.#renumberShapeMarks();
            this.#renderCanvas();
        });
        this.querySelector<HTMLInputElement>("[data-action='change-mark-color']")?.addEventListener("input", event => {
            const input = event.currentTarget;
            if (!(input instanceof HTMLInputElement)) return;
            if (this.#selectedMarkIndex < 0) return;
            const selected = this.#marks[this.#selectedMarkIndex];
            if (!selected) return;
            selected.color = input.value;
            this.#renderCanvas();
        });
        this.querySelector<HTMLInputElement>("[data-action='change-mark-label']")?.addEventListener("input", event => {
            const input = event.currentTarget;
            if (!(input instanceof HTMLInputElement)) return;
            this.#labelDraft = input.value;
            const selected = this.#marks[this.#selectedMarkIndex];
            if (selected?.type !== "label") return;
            selected.label = input.value;
            this.#renderCanvas();
        });
    }

    /**
     * Return the number of numbered geometric marks.
     * @returns {number} The count of non-label marks currently stored in the editor.
     */
    #shapeMarkCount(): number {
        return this.#marks.filter(mark => mark.type !== "label").length;
    }

    /**
     * Keep geometric mark numbers sequential without consuming LABEL entries.
     */
    #renumberShapeMarks(): void {
        let number = 0;
        for (const mark of this.#marks) {
            if (mark.type === "label") continue;
            number += 1;
            mark.label = String(number);
        }
    }

    /**
     * Find the topmost mark under a normalized pointer coordinate.
     * @param {number} x The horizontal coordinate of the interaction point.
     * @param {number} y The vertical coordinate of the interaction point.
     * @param {DOMRect} bounds The bounding rectangle of the editor used to calculate relative tolerance and scale.
     * @returns {number} The index of the matched mark within the internal marks collection, or -1 if no mark is found at the point.
     */
    #markIndexAtPoint(x: number, y: number, bounds: DOMRect): number {
        const tolerance = 10 / Math.max(1, Math.min(bounds.width, bounds.height));
        for (let index = this.#marks.length - 1; index >= 0; index -= 1) {
            const mark = this.#marks[index];
            if (!mark) continue;
            if (mark.type === "label") {
                const width = Math.max(tolerance * 2, (mark.label.length * 10) / Math.max(1, bounds.width));
                const height = Math.max(tolerance * 2, 22 / Math.max(1, bounds.height));
                if (x >= mark.x - tolerance && x <= mark.x + width && y >= mark.y - tolerance && y <= mark.y + height) {
                    return index;
                }
                continue;
            }
            const minX = Math.min(mark.x, mark.x + mark.w) - tolerance;
            const maxX = Math.max(mark.x, mark.x + mark.w) + tolerance;
            const minY = Math.min(mark.y, mark.y + mark.h) - tolerance;
            const maxY = Math.max(mark.y, mark.y + mark.h) + tolerance;
            if (x >= minX && x <= maxX && y >= minY && y <= maxY) return index;
        }
        return -1;
    }

    /**
     * Paint the immutable image and every mark in natural-image coordinates.
     * @param {boolean} showSelection Determines whether the currently selected mark should be rendered with a shadow highlight.
     */
    #renderCanvas(showSelection: boolean = true): void {
        const canvas = this.#canvas();
        if (!canvas || !this.#image) return;
        const context = canvas.getContext("2d");
        if (!context) return;
        const width = canvas.width;
        const height = canvas.height;
        const strokeWidth = Math.max(3, Math.min(width, height) * .004);
        const fontSize = Math.max(16, width * .016);
        context.clearRect(0, 0, width, height);
        context.drawImage(this.#image, 0, 0, width, height);
        this.#marks.forEach((mark, index) => {
            const x1 = mark.x * width;
            const y1 = mark.y * height;
            const x2 = (mark.x + mark.w) * width;
            const y2 = (mark.y + mark.h) * height;
            context.save();
            context.strokeStyle = mark.color || "#ff3b30";
            context.fillStyle = mark.color || "#ff3b30";
            context.lineWidth = strokeWidth;
            if (showSelection && index === this.#selectedMarkIndex) {
                context.shadowColor = "rgba(255, 255, 255, .95)";
                context.shadowBlur = strokeWidth * 2;
            }
            if (mark.type === "label") {
                context.font = `800 ${fontSize}px sans-serif`;
                context.textBaseline = "top";
                context.fillText(mark.label, x1, y1);
                context.restore();
                return;
            }
            if (mark.type === "arrow") {
                this.#drawArrow(context, x1, y1, x2, y2, width);
            } else if (mark.type === "path") {
                context.beginPath();
                (mark.points || []).forEach((item, pointIndex) => {
                    const pointX = item.x * width;
                    const pointY = item.y * height;
                    if (pointIndex === 0) context.moveTo(pointX, pointY); else context.lineTo(pointX, pointY);
                });
                context.stroke();
            } else {
                context.strokeRect(x1, y1, mark.w * width, mark.h * height);
            }
            context.font = `800 ${fontSize}px sans-serif`;
            context.textBaseline = "bottom";
            context.textAlign = "right";
            context.fillText(mark.label || String(index + 1), x2 - strokeWidth * 2, y2 - strokeWidth * 2);
            context.restore();
        });
        this.#syncToolbar();
    }

    /**
     * Draw one arrow shaft and filled head.
     * @param {CanvasRenderingContext2D} context The 2D rendering context used for drawing operations.
     * @param {number} x1 The horizontal coordinate of the arrow's start point.
     * @param {number} y1 The vertical coordinate of the arrow's start point.
     * @param {number} x2 The horizontal coordinate of the arrow's tip.
     * @param {number} y2 The vertical coordinate of the arrow's tip.
     * @param {number} canvasWidth The total width of the canvas used to calculate the proportional size of the arrowhead.
     */
    #drawArrow(
        context: CanvasRenderingContext2D,
        x1: number,
        y1: number,
        x2: number,
        y2: number,
        canvasWidth: number
    ): void {
        const angle = Math.atan2(y2 - y1, x2 - x1);
        const size = Math.max(14, canvasWidth * .015);
        context.beginPath();
        context.moveTo(x1, y1);
        context.lineTo(x2, y2);
        context.stroke();
        context.beginPath();
        context.moveTo(x2, y2);
        context.lineTo(x2 - size * Math.cos(angle - .45), y2 - size * Math.sin(angle - .45));
        context.lineTo(x2 - size * Math.cos(angle + .45), y2 - size * Math.sin(angle + .45));
        context.closePath();
        context.fill();
    }

    /**
     * Reflect selected mark state into toolbar controls.
     */
    #syncToolbar(): void {
        const selected = this.#marks[this.#selectedMarkIndex];
        const labelInput = this.querySelector<HTMLInputElement>("[data-action='change-mark-label']");
        const colorInput = this.querySelector<HTMLInputElement>("[data-action='change-mark-color']");
        const deleteButton = this.querySelector<HTMLButtonElement>("[data-action='delete-selected-mark']");
        if (labelInput) labelInput.value = selected?.type === "label" ? selected.label : this.#labelDraft;
        if (colorInput && selected?.color) colorInput.value = selected.color;
        if (deleteButton instanceof HTMLButtonElement) deleteButton.disabled = !selected;
    }
}

customElements.define(VisualReferenceEditor.selector, VisualReferenceEditor);
