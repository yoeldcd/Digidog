/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { BrainApiClient } from "./infrastructure/shared/http/clients/brain-api-client.ts";
import { parseStartupRouteTarget } from "./application/shell/validators/startup-route-target.ts";
import { AppState } from "./presentation/shell/state/app-state.ts";
import { BrainExplorerApp } from "./presentation/shell/layouts/app-shell.ts";

/**
 * Bootstrap the Brain Explorer browser application.
 *
 * @returns {void}
 */
function bootstrapBrainExplorer() {
    const app = document.querySelector<BrainExplorerApp>(BrainExplorerApp.selector);
    if (!app) {
        return;
    }
    const api = new BrainApiClient();
    const activePath = localStorage.getItem("active_project_path");
    const state = new AppState(activePath || "");
    const startupTarget = parseStartupRouteTarget(window.location.search);
    if (startupTarget) {
        state.setRouteTarget(startupTarget.route, startupTarget.target);
    }

    app.context = {
        api,
        state,
    };
}

bootstrapBrainExplorer();
