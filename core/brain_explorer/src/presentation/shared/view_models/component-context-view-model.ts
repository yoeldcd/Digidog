/**
 * Cross-feature runtime dependency contract injected into route-level components.
 *
 * @module presentation/shared/view_models/component-context-view-model
 */

import type { BrainApiClient } from "../../../infrastructure/shared/http/clients/brain-api-client.ts";
import type { AppState } from "../../shell/state/app-state.ts";

/**
 * Runtime dependencies injected into every route-level Explorer component.
 */
export interface ReactiveContentFilterLayout {
    /** Apply a debounced shell query incrementally without rebuilding mounted DOM. */
    applyReactiveContentFilter(query: string): void;
}

/**
 * Public route-target focus contract implemented by layouts that own deferred navigation.
 */
export interface TargetFocusableLayout {
    /** Focus or reveal the destination represented by a route target. */
    focusTarget(target: Readonly<Record<string, unknown>>): Promise<void> | void;
}

export interface ComponentContext {
    /**
     * Shared HTTP adapter used to invoke typed Explorer API operations.
     * @type {BrainApiClient}
     */
    api: BrainApiClient;
    /**
     * Shared browser state store coordinating routes, diagnostics, and pending targets.
     * @type {AppState}
     */
    state: AppState;
}
