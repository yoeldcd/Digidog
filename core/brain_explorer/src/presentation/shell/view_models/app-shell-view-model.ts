/**
 * Presentation contracts retained by the persistent Brain Explorer shell.
 *
 * @module presentation/shell/view_models/app-shell-view-model
 */

import type { RouteId } from "../../../application/shell/contracts/shell-contracts.ts";
import type { IconName } from "../../shared/utils/icons.ts";
import type { ApiResponse } from "../../../application/shared/contracts/api-response-contract.ts";

/**
 * Describes one route that the persistent application shell can render.
 *
 * The model contains presentation-only metadata. It intentionally excludes
 * API clients, component instances, and mutable route state so the shell can
 * render navigation without coupling its markup to infrastructure details.
 */
export interface ShellRouteViewModel {
    /**
     * Stable application route identifier consumed by `AppState`.
     * @type {RouteId}
     */
    id: RouteId;
    /**
     * Human-readable route label displayed in navigation and headings.
     * @type {string}
     */
    label: string;
    /**
     * Registered SVG icon key rendered beside the route label.
     * @type {"edit" | "settings" | "home" | "database" | "graph" | "search" | "messageCircle" | "sliders" | "users" | "document" | "plus" | "documentPlus" | "folderPlus" | "copy" | "trash" | "save" | "refresh" | "pulse" | "folder" | "moon" | "sun" | "terminal" | "close" | "collapseLeft" | "expandRight" | "eye" | "filter" | "checkSquare" | "chevronRight" | "chevronLeft" | "chevronDown" | "minus" | "more" | "clock" | "camera" | "book" | "volume" | "play" | "pause" | "download"}
     */
    icon: IconName;
    /**
     * Custom Element selector mounted when the route becomes active.
     * @type {string}
     */
    element: string;
    /**
     * Whether the route appears in persistent navigation; defaults to true.
     * @type {boolean | undefined}
     */
    nav?: boolean;
}

/**
 * Tracks the browser timer associated with a transient shell notification.
 *
 * Keeping this shape outside the component makes the timer registry explicit
 * and prevents anonymous object literals from becoming an undocumented shell
 * state contract.
 */
export interface NotificationTimerViewModel {
    /**
     * Numeric browser timer handle returned by `window.setTimeout`.
     * @type {number}
     */
    timer: number;
}

/**
 * Describes the payload emitted by `BrainApiClient` request lifecycle events.
 */
export interface ApiRequestEventDetail {
    /**
     * Human-readable command label displayed in the shell footer.
     * @type {string | undefined}
     */
    command?: string;
    /**
     * HTTP method used to classify read and mutation feedback.
     * @type {string | undefined}
     */
    method?: string;
    /**
     * Completed API envelope, present on request-end events.
     * @type {ApiResponse<unknown> | undefined}
     */
    payload?: ApiResponse;
}

/**
 * Input used to render one transient shell notification.
 */
export interface ShellNotificationInput {
    /**
     * Semantic visual tone applied to the notification.
     * @type {"error" | "info" | "success" | undefined}
     */
    tone?: "info" | "success" | "error";
    /**
     * Short notification heading.
     * @type {string | undefined}
     */
    title?: string;
    /**
     * Detailed user-facing result message.
     * @type {string | undefined}
     */
    message?: string;
}
