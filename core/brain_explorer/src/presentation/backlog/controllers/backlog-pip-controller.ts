/**
 * Owns native Document Picture-in-Picture lifecycle for the Backlog feature.
 *
 * The controller isolates browser-window creation, style transfer, desktop capture,
 * component mounting, and disposal from the route-level Backlog Web Component.
 *
 * @module presentation/backlog/controllers/backlog-pip-controller
 */

import { documentPictureInPictureController } from "../contracts/document-picture-in-picture.ts";
import type { DesktopCaptureConstraints } from "../contracts/document-picture-in-picture.ts";
import { BacklogPip } from "../layouts/backlog-pip.ts";
import type {
    BacklogPipCreateTaskInput,
    BacklogPipCreateTaskResult,
    BacklogPipTaskViewModel
} from "../view_models/backlog-pip-view-model.ts";

/**
 * Inputs required when opening the Backlog Picture-in-Picture surface.
 */
export interface OpenBacklogPipInput {
    /**
     * Current task projection displayed immediately after mounting.
     * @type {readonly BacklogPipTaskViewModel[]}
     */
    tasks: readonly BacklogPipTaskViewModel[];
    /**
     * Application callback that persists a PiP task draft.
     * @type {(input: BacklogPipCreateTaskInput) => Promise<BacklogPipCreateTaskResult>}
     */
    onAddTask: (input: BacklogPipCreateTaskInput) => Promise<BacklogPipCreateTaskResult>;
}

/**
 * Manages the single native Backlog PiP window allowed per route instance.
 */
export class BacklogPipController {
    /**
     * Browser window currently hosting the PiP component.
     * @type {Window | null}
     */
    #pipWindow: Window | null = null;
    /**
     * Mounted task component synchronized by subsequent Backlog responses.
     * @type {BacklogPip | null}
     */
    #pipComponent: BacklogPip | null = null;
    /**
     * Prevents overlapping native `requestWindow` calls.
     * @type {boolean}
     */
    #requestInFlight = false;

    /**
     * @returns {boolean} True when the current browser exposes native Document PiP.
     */
    supported(): boolean {
        return documentPictureInPictureController(window) !== null;
    }

    /**
     * Open or focus the native PiP window and mount its dedicated component.
     *
     * @param {OpenBacklogPipInput} input Current tasks and the application mutation callback.
     *
     * @returns {Promise<void>} A promise that resolves once the window request process has completed or failed.
     */
    async open(input: OpenBacklogPipInput): Promise<void> {
        if (!this.supported() || this.#requestInFlight) return;
        if (this.#pipWindow && !this.#pipWindow.closed) {
            this.#pipWindow.focus();
            return;
        }
        this.#requestInFlight = true;
        try {
            const nativeController = documentPictureInPictureController(window);
            if (!nativeController) return;
            const pipWindow = await nativeController.requestWindow({
                width: 420,
                height: 620,
                disallowReturnToOpener: false,
                preferInitialWindowPlacement: true
            });
            this.#pipWindow = pipWindow;
            this.#copyStyles(pipWindow.document);
            pipWindow.document.title = "Backlog";
            pipWindow.document.documentElement.dataset.theme = document.documentElement.dataset.theme || "dark";
            pipWindow.document.body.className = "backlog-pip-document";
            const component = new BacklogPip();
            component.tasks = [...input.tasks];
            component.onCaptureScreen = () => this.#captureScreen();
            component.onAddTask = input.onAddTask;
            pipWindow.document.body.replaceChildren(component);
            this.#pipComponent = component;
            pipWindow.addEventListener("pagehide", () => this.#release(pipWindow), { once: true });
        } catch (error) {
            console.warn("Unable to open the Document Picture-in-Picture window.", error);
        } finally {
            this.#requestInFlight = false;
        }
    }

    /**
     * Synchronize the mounted component after the authoritative task list changes.
     *
     * @param {readonly BacklogPipTaskViewModel[]} tasks Refreshed task projection from the Backlog endpoint.
     */
    syncTasks(tasks: readonly BacklogPipTaskViewModel[]): void {
        if (this.#pipComponent) this.#pipComponent.tasks = [...tasks];
    }

    /**
     * Close the active native window and release its component references.
     */
    close(): void {
        const pipWindow = this.#pipWindow;
        if (!pipWindow || pipWindow.closed) return;
        pipWindow.close();
        this.#release(pipWindow);
    }

    /**
     * Copy same-origin Explorer styles into the isolated PiP document.
     *
     * @param {Document} pipDocument Destination document created by the native PiP API.
     */
    #copyStyles(pipDocument: Document): void {
        for (const stylesheet of Array.from(document.styleSheets)) {
            try {
                if (stylesheet.href) {
                    const link = pipDocument.createElement("link");
                    link.rel = "stylesheet";
                    link.href = stylesheet.href;
                    pipDocument.head.appendChild(link);
                } else {
                    const style = pipDocument.createElement("style");
                    style.textContent = Array.from(stylesheet.cssRules, rule => rule.cssText).join("\n");
                    pipDocument.head.appendChild(style);
                }
            } catch (_error) {
                // Browser-owned and cross-origin stylesheets are optional in PiP.
            }
        }
    }

    /**
     * @returns {Promise<string | null>} PNG data URL of a user-selected desktop surface, or null on cancellation.
     */
    async #captureScreen(): Promise<string | null> {
        try {
            const video: DesktopCaptureConstraints = { mediaSource: "screen" };
            const stream = await navigator.mediaDevices.getDisplayMedia({ video });
            const videoElement = document.createElement("video");
            videoElement.srcObject = stream;
            await videoElement.play();
            await new Promise<void>(resolve => { videoElement.onloadedmetadata = () => resolve(); });
            await new Promise<void>(resolve => window.setTimeout(resolve, 300));
            const canvas = document.createElement("canvas");
            canvas.width = videoElement.videoWidth;
            canvas.height = videoElement.videoHeight;
            const context = canvas.getContext("2d");
            if (!context) return null;
            context.drawImage(videoElement, 0, 0);
            stream.getTracks().forEach(track => track.stop());
            return canvas.toDataURL("image/png");
        } catch (error) {
            console.error("Screenshot capture failed:", error);
            return null;
        }
    }

    /**
     * Release state only when the closing window is the controller's active window.
     *
     * @param {Window} pipWindow Window reported by the browser lifecycle event.
     */
    #release(pipWindow: Window): void {
        if (this.#pipWindow !== pipWindow) return;
        this.#pipComponent?.remove();
        this.#pipComponent = null;
        this.#pipWindow = null;
    }
}
