import { BrainApiClient } from "./infrastructure/api/brain-api-client.ts";
import { AppState } from "./presentation/state/app-state.ts";
import { BrainExplorerApp } from "./presentation/components/app-shell.ts";

/**
 * Bootstrap the Brain Explorer browser application.
 *
 * @returns {void}
 */
function bootstrapBrainExplorer() {
    const app = document.querySelector(BrainExplorerApp.selector);
    if (!app) {
        return;
    }
    const api = new BrainApiClient();
    const activePath = localStorage.getItem("active_project_path");
    if (activePath) {
        api.setWorkspaceRootOverride(activePath);
    }
    app.context = {
        api,
        state: new AppState()
    };
}

bootstrapBrainExplorer();
