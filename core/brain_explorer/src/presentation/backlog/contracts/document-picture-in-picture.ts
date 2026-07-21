/**
 * Browser contract for the Document Picture-in-Picture API.
 *
 * The API remains experimental and is not present in the baseline DOM library
 * shipped with TypeScript. This declaration models only the surface consumed by
 * Brain Explorer and leaves feature detection mandatory at runtime.
 *
 * @module presentation/backlog/contracts/document-picture-in-picture
 */

/**
 * Options accepted when requesting a native document PiP window.
 */
export interface DocumentPictureInPictureOptions {
    /**
     * Requested viewport width in CSS pixels.
     * @type {number | undefined}
     */
    width?: number;
    /**
     * Requested viewport height in CSS pixels.
     * @type {number | undefined}
     */
    height?: number;
    /**
     * Prevents a browser-provided affordance from returning to the opener.
     * @type {boolean | undefined}
     */
    disallowReturnToOpener?: boolean;
    /**
     * Requests placement near the browser's preferred initial PiP location.
     * @type {boolean | undefined}
     */
    preferInitialWindowPlacement?: boolean;
}

/**
 * Minimal native API exposed by supporting Chromium browsers.
 */
export interface DocumentPictureInPictureController {
    /**
     * Opens a new PiP document in direct response to a user gesture.
     *
     * @param {DocumentPictureInPictureOptions | undefined} options Requested native PiP viewport and opener-return policy.
     * @returns {Promise<Window>} Newly created browser window hosting the isolated PiP document.
     */
    requestWindow(options?: DocumentPictureInPictureOptions): Promise<Window>;
}

/**
 * Chromium-specific desktop capture constraint accepted by getDisplayMedia.
 */
export interface DesktopCaptureConstraints extends MediaTrackConstraints {
    /**
     * Requests the current browser surface when supported by the user agent.
     * @type {"screen" | "window" | "browser" | undefined}
     */
    mediaSource?: "screen" | "window" | "browser";
}

/**
 * Reads the optional experimental controller without widening the global
 * `Window` declaration for browsers that do not implement the API.
 *
 * @param {Window} browserWindow Window whose optional capability must be inspected.
 * @returns {DocumentPictureInPictureController | null} The usable controller, or `null` when feature detection fails.
 */
export function documentPictureInPictureController(
    browserWindow: Window,
): DocumentPictureInPictureController | null {
    const candidate = Reflect.get(browserWindow, "documentPictureInPicture");
    if (typeof candidate !== "object" || candidate === null) return null;
    const requestWindow = Reflect.get(candidate, "requestWindow");
    return typeof requestWindow === "function"
        ? { requestWindow: options => requestWindow.call(candidate, options) }
        : null;
}
