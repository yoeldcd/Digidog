/**
 * Coordinates Backlog visual-reference editor state and desktop capture.
 *
 * The controller owns DOM adaptation specific to the atomic editor while the route
 * component retains task-form lifecycle and persistence decisions.
 *
 * @module presentation/backlog/controllers/backlog-visual-reference-controller
 */

import { VisualReferenceEditor } from "../layouts/visual-reference-editor.ts";
import type { DesktopCaptureConstraints } from "../contracts/document-picture-in-picture.ts";

/**
 * Controls the visual-reference subtree mounted inside one Backlog component host.
 */
export class BacklogVisualReferenceController {
    /**
     * Backlog Custom Element used as the query boundary for editor controls.
     * @type {HTMLElement}
     */
    readonly #host: HTMLElement;

    /**
     * Bind the controller to one route component instance.
     *
     * @param {HTMLElement} host Backlog host containing the dialog and atomic editor.
     */
    constructor(host: HTMLElement) {
        this.#host = host;
    }

    /**
     * Load an image source and transition the drop area to its populated state.
     *
     * @param {string} dataUrl Data URL or same-origin endpoint understood by the editor.
     */
    displayImage(dataUrl: string): void {
        const editor = this.#editor();
        if (!editor) return;
        this.#setHasImage(true);
        editor.loadImage(dataUrl);
    }

    /**
     * Reset editor marks, image state, drop-area styling, and file-input availability.
     */
    reset(): void {
        this.#editor()?.reset();
        this.#setHasImage(false);
    }

    /**
     * @returns {Promise<string | null>} PNG export from the mounted editor, or null when it is unavailable.
     */
    async exportPng(): Promise<string | null> {
        return this.#editor()?.exportPng() ?? null;
    }

    /**
     * Capture a user-selected desktop surface and load it into the task editor.
     *
     * @returns {Promise<void>} Promise resolved after capture, modal opening, and editor loading.
     */
    async captureScreen(): Promise<void> {
        try {
            const videoConstraints: DesktopCaptureConstraints = { mediaSource: "screen" };
            const stream = await navigator.mediaDevices.getDisplayMedia({ video: videoConstraints });
            const video = document.createElement("video");
            video.srcObject = stream;
            await video.play();
            await new Promise<void>(resolve => { video.onloadedmetadata = () => resolve(); });
            await new Promise<void>(resolve => window.setTimeout(resolve, 300));
            const canvas = document.createElement("canvas");
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const context = canvas.getContext("2d");
            if (!context) return;
            context.drawImage(video, 0, 0);
            stream.getTracks().forEach(track => track.stop());
            this.#host.querySelector<HTMLButtonElement>("[data-action='open-create-modal']")?.click();
            this.displayImage(canvas.toDataURL("image/png"));
        } catch (error) {
            console.error("Screen capture failed:", error);
        }
    }

    /**
     * @returns {VisualReferenceEditor | null} Mounted atomic visual-reference editor, or null before rendering.
     */
    #editor(): VisualReferenceEditor | null {
        const editor = this.#host.querySelector(VisualReferenceEditor.selector);
        return editor instanceof VisualReferenceEditor ? editor : null;
    }

    /**
     * Synchronize populated-state classes and native file-input availability.
     *
     * @param {boolean} hasImage Whether the atomic editor currently owns an image.
     */
    #setHasImage(hasImage: boolean): void {
        this.#host.querySelector("[data-role='image-upload-zone']")?.classList.toggle("has-image", hasImage);
        this.#host.querySelector("[data-role='image-preview-area']")?.classList.toggle("has-image", hasImage);
        const fileInput = this.#host.querySelector("[data-role='modal-image-file']");
        if (fileInput instanceof HTMLInputElement) fileInput.disabled = hasImage;
    }
}
