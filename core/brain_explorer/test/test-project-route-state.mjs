/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { BrainApiClient } from "../src/infrastructure/shared/http/clients/brain-api-client.ts";

const stateSource = await readFile(new URL("../src/presentation/shell/state/app-state.ts", import.meta.url), "utf8");
const appSource = await readFile(new URL("../src/app.ts", import.meta.url), "utf8");
const indexSource = await readFile(new URL("../src/index.html", import.meta.url), "utf8");
const appShellSource = await readFile(
    new URL("../src/presentation/shell/layouts/app-shell.ts", import.meta.url),
    "utf8"
);

assert.match(indexSource, /rel="icon" type="image\/png" sizes="256x256" href="\.\/brain-explorer-favicon\.png"/,
    "Brain Explorer must ship its generated representative favicon.");
assert.match(indexSource, /meta name="theme-color" content="#0d1728"/,
    "The browser chrome color must match the Explorer dark surface.");

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
assert.match(
    appShellSource,
    /mountedElement\s*=\s*host\.firstElementChild[\s\S]*activeRouteIsMounted\s*=\s*mountedElement\s*!==\s*null[\s\S]*if\s*\(activeRouteIsMounted\s*&&\s*!refreshPendingQuery\)/,
    "The default route must mount into an empty host even when its id already matches the initial route field."
);
assert.doesNotMatch(
    stateSource.match(/PERSISTABLE_ROUTES[^;]+;/s)?.[0] ?? "",
    /"query"/,
    "Transient search results must not replace a project's stable view."
);
assert.match(appShellSource, /data-search-select-all="search-source"[\s\S]*data-search-select-all="search-mechanism"/, "Both search option groups require bulk-selection controls.");
assert.match(appShellSource, /value="backlog" checked>Backlog/, "Backlog must be an explicit search source.");
assert.match(appShellSource, /<legend>Methods<\/legend>/, "Retrieval choices must use the Methods terminology.");
assert.match(appShellSource, /master\.indeterminate = checkedCount > 0 && checkedCount < children\.length/, "Bulk-selection controls must expose partial state.");
assert.match(appShellSource, /normalized\.length >= 2[\s\S]*}, 200\);/, "Reactive search must start at two characters and remain debounced.");
assert.match(appShellSource, /mountedElement\?\.querySelector\("\.query-results"\)[\s\S]*#preservedQueryView = mountedElement/, "Search Results must only be preserved after a real result view exists.");
assert.doesNotMatch(appShellSource, /if \(route\.id === "query"\) this\.#preservedQueryView = element/, "An empty QueryView must not expose Search Results navigation.");
assert.match(appShellSource, /Please select at least one source and method\./, "Imperative search must reject empty option groups.");
assert.match(appShellSource, /#activeRouteId === "query"[\s\S]*applyReactiveContentFilter/, "The shell searchbar must forward reactive text to QueryView.");

const originalFetch = globalThis.fetch;
const directSystemResponses = new Map([
    ["/api/health", {
        ok: true,
        name: "brain_explorer",
        distDir: "D:/agent/core/brain_explorer/dist",
        workspaceRoot: "D:/agent",
        agentHome: "D:/agent"
    }],
    ["/api/projects", {
        ok: true,
        projects: [{ name: "Agent", path: "D:/agent" }]
    }],
    ["/api/wikis", {
        ok: true,
        wikis: [{ name: "Agent", path: "D:/agent/documentation", hasWiki: true }]
    }]
]);
globalThis.fetch = async (path) => {
    const payload = directSystemResponses.get(String(path));
    assert.ok(payload, `Unexpected system route request: ${String(path)}`);
    return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" }
    });
};
try {
    const api = new BrainApiClient();
    const health = await api.health({ silent: true });
    const projects = await api.getProjects({ silent: true });
    const wikis = await api.getWikis({ silent: true });

    assert.equal(health.data?.workspaceRoot, "D:/agent", "Direct health fields must be normalized into response data.");
    assert.deepEqual(projects.data?.projects, [{ name: "Agent", path: "D:/agent" }], "Direct mirror records must reach the selector contract.");
    assert.equal(wikis.data?.wikis[0]?.hasWiki, true, "Direct wiki records must reach the Wikis view contract.");
} finally {
    globalThis.fetch = originalFetch;
}

console.log("project route and system response contracts passed");
