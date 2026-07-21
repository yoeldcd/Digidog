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
