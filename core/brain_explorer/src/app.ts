/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { BrainApiClient } from "./infrastructure/shared/http/clients/brain-api-client.ts";
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

    app.context = {
        api,
        state: new AppState(activePath || "")
    };
}

bootstrapBrainExplorer();
