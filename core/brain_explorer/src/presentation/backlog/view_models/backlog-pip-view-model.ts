/**
 * Presentation contracts used by the backlog Picture-in-Picture component.
 *
 * This module deliberately owns data shapes only. Keeping these contracts out
 * of the Web Component preserves the presentation boundary: the component
 * renders view-ready values, while callers remain responsible for adapting API
 * payloads to these explicit models.
 *
 * @module presentation/backlog/view_models/backlog-pip-view-model
 */

import type { BacklogTask } from "../../../application/backlog/dtos/responses/backlog-response.ts";

/**
 * Priority value accepted by the task-creation form.
 */
export type BacklogPipPriority = BacklogTask["priority"];

/**
 * View-ready backlog task rendered inside the compact PiP task list.
 */
export interface BacklogPipTaskViewModel extends BacklogTask {
    /**
     * Compatibility completion flag exposed by legacy backlog payloads.
     * New callers should derive this value from `status === "DONE"`.
     *
     * @type {boolean | undefined}
     */
    done?: boolean;
}

/**
 * Editable values retained while the PiP creation form is rerendered.
 */
export interface BacklogPipFormDraft {
    /**
     * Human-readable task title after user editing but before trimming.
     * @type {string}
     */
    title: string;
    /**
     * Detailed task description after user editing but before trimming.
     * @type {string}
     */
    description: string;
    /**
     * Validated priority selected from the form's closed option set.
     * @type {"HIGH" | "MEDIUM" | "LOW"}
     */
    priority: BacklogPipPriority;
}

/**
 * Normalized rectangle drawn over a captured visual reference.
 */
export interface BacklogPipMarkingRectangle {
    /**
     * Horizontal origin expressed as a fraction of image width.
     * @type {number}
     */
    x: number;
    /**
     * Vertical origin expressed as a fraction of image height.
     * @type {number}
     */
    y: number;
    /**
     * Rectangle width expressed as a fraction of image width.
     * @type {number}
     */
    w: number;
    /**
     * Rectangle height expressed as a fraction of image height.
     * @type {number}
     */
    h: number;
    /**
     * CSS color used for the rectangle and its numeric label.
     * @type {string}
     */
    color: string;
}

/**
 * Command object passed to the application callback when a task is submitted.
 */
export interface BacklogPipCreateTaskInput {
    /**
     * Trimmed non-empty task title supplied by the user.
     * @type {string}
     */
    title: string;
    /**
     * Trimmed task description, including any visual-reference marker.
     * @type {string}
     */
    description: string;
    /**
     * Validated task priority selected in the PiP form.
     * @type {"HIGH" | "MEDIUM" | "LOW"}
     */
    priority: BacklogPipPriority;
    /**
     * Baked PNG data URL, or `null` when no visual reference is attached.
     * @type {string | null}
     */
    image: string | null;
}

/**
 * Result returned by the task-creation application callback.
 */
export interface BacklogPipCreateTaskResult {
    /**
     * Whether the application accepted and persisted the new task.
     * @type {boolean}
     */
    ok: boolean;
    /**
     * Refreshed tasks when the caller can update the PiP without another fetch.
     * @type {BacklogPipTaskViewModel[] | undefined}
     */
    tasks?: BacklogPipTaskViewModel[];
    /**
     * User-facing failure explanation when `ok` is `false`.
     * @type {string | undefined}
     */
    message?: string;
}

/**
 * Produces an image data URL for a screen capture, or `null` on cancellation.
 */
export type BacklogPipCaptureHandler = () => Promise<string | null>;

/**
 * Persists a task created from the PiP form and returns its application result.
 */
export type BacklogPipCreateTaskHandler = (
    input: BacklogPipCreateTaskInput,
) => Promise<BacklogPipCreateTaskResult>;
