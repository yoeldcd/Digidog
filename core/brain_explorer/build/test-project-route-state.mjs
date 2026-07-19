/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const stateSource = await readFile(new URL("../src/presentation/state/app-state.ts", import.meta.url), "utf8");
const appSource = await readFile(new URL("../src/app.ts", import.meta.url), "utf8");
const appShellSource = await readFile(
    new URL("../src/presentation/components/app-shell.ts", import.meta.url),
    "utf8"
);

assert.match(
    stateSource,
    /PROJECT_ROUTE_STORAGE_PREFIX[\s\S]*projectRouteStorageKey\(projectPath/,
    "Project routes must use isolated local-storage keys."
);
assert.match(
    stateSource,
    /PERSISTABLE_ROUTES[\s\S]*restoreProjectRoute/,
    "Only stable Explorer views may be restored."
);
assert.match(
    stateSource,
    /#persistProjectRoute\(route\)[\s\S]*localStorage\.setItem\(projectRouteStorageKey/,
    "Route navigation must persist against the active project."
);
assert.match(
    appSource,
    /new AppState\(activePath \|\| ""\)/,
    "Bootstrap must restore state using the selected project path."
);
assert.doesNotMatch(
    appSource,
    /setWorkspaceRootOverride\(activePath\)/,
    "Bootstrap must not send an unvalidated persisted workspace to a newly bound server."
);
assert.match(
    appShellSource,
    /activeProjectIsRegistered[\s\S]*!activeProjectIsRegistered[\s\S]*localStorage\.setItem\("active_project_path", defaultPath\)/,
    "The project selector must replace a stale cross-agent workspace with the current server default."
);
assert.doesNotMatch(
    stateSource.match(/PERSISTABLE_ROUTES[^;]+;/s)?.[0] ?? "",
    /"query"/,
    "Transient search results must not replace a project's stable view."
);

console.log("project route state contract passed");
