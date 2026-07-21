/**
 * Geometry and interaction contracts for the Backlog visual-reference editor.
 *
 * @module presentation/backlog/view_models/visual-reference-editor-view-model
 */

/**
 * Closed annotation tool vocabulary supported by the canvas editor.
 */
export type MarkType = "rectangle" | "arrow" | "path" | "label";

/**
 * Resolution-independent point expressed as fractions of image dimensions.
 */
export interface NormalizedPoint {
    /**
     * Horizontal origin from zero to one.
     * @type {number}
     */
    x: number;
    /**
     * Vertical origin from zero to one.
     * @type {number}
     */
    y: number;
}
/**
 * Normalized pointer coordinate retaining the canvas bounds used for conversion.
 */
export interface CanvasPoint extends NormalizedPoint {
    /**
     * Canvas client rectangle captured for the current pointer event.
     * @type {DOMRect}
     */
    bounds: DOMRect;
}
/**
 * Persisted visual annotation rendered above the immutable source image.
 */
export interface VisualMark extends NormalizedPoint {
    /**
     * Annotation geometry and rendering discriminator.
     * @type {MarkType}
     */
    type: MarkType;
    /**
     * Normalized annotation width.
     * @type {number}
     */
    w: number;
    /**
     * Normalized annotation height.
     * @type {number}
     */
    h: number;
    /**
     * Freehand path points, or null for rectangle, arrow, and label marks.
     * @type {NormalizedPoint[] | null}
     */
    points: NormalizedPoint[] | null;
    /**
     * CSS-compatible annotation color.
     * @type {string}
     */
    color: string;
    /**
     * Human-readable annotation label.
     * @type {string}
     */
    label: string;
}

/**
 * Pointer gesture retained while moving an existing mark or drawing a new one.
 */
export type CanvasInteraction = {
    /**
     * Discriminator for repositioning an existing annotation.
     * @type {"drag"}
     */
    mode: "drag";
    /**
     * Index of the annotation being repositioned.
     * @type {number}
     */
    index: number;
    /**
     * Normalized pointer coordinate captured when dragging began.
     * @type {CanvasPoint}
     */
    start: CanvasPoint;
    /**
     * Immutable annotation snapshot used to calculate the drag delta.
     * @type {VisualMark}
     */
    original: VisualMark;
} | {
    /**
     * Discriminator for creating a new geometric annotation.
     * @type {"draw"}
     */
    mode: "draw";
    /**
     * Reserved insertion index of the annotation being created.
     * @type {number}
     */
    index: number;
    /**
     * Normalized pointer coordinate captured when drawing began.
     * @type {CanvasPoint}
     */
    start: CanvasPoint;
    /**
     * Geometric tool selected for the new annotation.
     * @type {"rectangle" | "arrow" | "path"}
     */
    type: Exclude<MarkType, "label">;
};
