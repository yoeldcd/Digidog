/**
 * Regression contracts for URL-driven Backlog task navigation.
 */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { parseStartupRouteTarget } from "../src/application/shell/validators/startup-route-target.ts";
import { parseBacklogNavigationTarget } from "../src/presentation/backlog/validators/backlog-navigation-target.ts";

const startupTarget = parseStartupRouteTarget("?section=backlog&task=T634");
assert.deepEqual(startupTarget, {
    route: "backlog",
    target: { taskId: "t634" },
});

assert.deepEqual(parseStartupRouteTarget("?section=backlog&task=../../634"), {
    route: "backlog",
    target: {},
});
assert.equal(parseStartupRouteTarget("?section=unknown&task=t634"), null);
assert.deepEqual(parseBacklogNavigationTarget({ taskId: "T634" }), { taskId: "t634" });
assert.equal(parseBacklogNavigationTarget({ taskId: "634" }), null);
assert.equal(parseBacklogNavigationTarget(null), null);

const tree = await readFile(new URL("../src/presentation/shared/components/structure-tree.ts", import.meta.url), "utf8");
const backlogView = await readFile(new URL("../src/presentation/backlog/layouts/backlog-view.ts", import.meta.url), "utf8");
const appShell = await readFile(new URL("../src/presentation/shell/layouts/app-shell.ts", import.meta.url), "utf8");
const htmlUtilities = await readFile(new URL("../src/presentation/shared/utils/html.ts", import.meta.url), "utf8");
const searchableLayouts = await Promise.all([
    "messages", "memory", "pictures", "knowledge"
].map(feature => readFile(new URL(`../src/presentation/${feature}/layouts/${feature}-view.ts`, import.meta.url), "utf8")));
assert.match(tree, /query\.length >= 2 \? query : ""/,
    "Shared tree matching must not activate before two characters.");
assert.match(tree, /const expanded = Boolean\(this\.#activeSearchQuery\(\)\) \|\| this\.#model\.expandedPaths\.has/,
    "A tree search must reveal every visible matching hierarchy regardless of manual expansion state.");
assert.match(tree, /detail: \{ query: this\.#activeSearchQuery\(\) \}/,
    "Tree consumers must receive the same two-character search contract as the shared renderer.");
assert.match(backlogView, /if \(event\.detail\.expanded\)[\s\S]*this\.#expandedNodes\.add\(event\.detail\.path\)/,
    "Backlog must preserve expansion emitted by the shared tree across selection renders.");

assert.match(backlogView, /applyReactiveContentFilter\(query: string\)[\s\S]*#contentFilter = query\.trim\(\);[\s\S]*#refreshTaskContent\(\)/,
    "Global reactive search must update only the Backlog content projection.");
assert.match(backlogView, /searchQuery: this\.#filter/,
    "The tree must remain owned exclusively by its local filter.");
assert.doesNotMatch(appShell, /tree-filter/,
    "The global shell must never write into a layout tree filter.");
for (const source of [backlogView, ...searchableLayouts]) {
    assert.match(source, /applyReactiveContentFilter\(query: string\): void/,
        "Every searchable route layout must own the public reactive-content API.");
}
assert.doesNotMatch(searchableLayouts[3] ?? "", /data-role="kg-query"/,
    "Knowledge must rely on the global reactive search API instead of a duplicate searchbar.");
const knowledgeReactiveApi = (searchableLayouts[3] ?? "").match(/applyReactiveContentFilter\(query: string\): void \{([\s\S]*?)\n    \}/)?.[1] ?? "";
assert.match(knowledgeReactiveApi, /this\.drawCanvas\(\)/,
    "Knowledge reactive search must redraw the existing canvas incrementally.");
assert.doesNotMatch(knowledgeReactiveApi, /this\.render\(\)|innerHTML/,
    "Knowledge reactive search must not rebuild its mounted layout DOM.");
assert.match(htmlUtilities, /item\.dataset\.reactiveContent[\s\S]*content\.includes\(needle\)/,
    "Rendered-content filtering must include each item model's explicit hidden-content corpus.");
assert.match(htmlUtilities, /highlightRenderedContent[\s\S]*data-reactive-search-match[\s\S]*createTreeWalker[\s\S]*reactive-search-match/,
    "Reactive filtering must reversibly highlight every rendered text fragment that matches the query.");
assert.match(backlogView, /highlightRenderedContent\(this, this\.#contentFilter \|\| this\.#filter, "\[data-task-row-id\]:not\(\[hidden\]\)"\)/,
    "Backlog data-level filtering must highlight visible task identity text after projection.");
assert.match(searchableLayouts[0] ?? "", /data-reactive-content=[\s\S]*#messageReactiveContent/,
    "Collapsed Messages must expose complete message metadata to reactive filtering.");
assert.match(searchableLayouts[0] ?? "", /#syncReactiveExpandedMessages\(\)[\s\S]*#reactiveExpandedIds[\s\S]*#expandedIds\.add\(record\.id\)/,
    "Collapsed message matches must expand while preserving separately tracked manual state.");
assert.match(searchableLayouts[0] ?? "", /#refreshMessageList\(\)[\s\S]*#syncReactiveExpandedMessages\(\)[\s\S]*filterRenderedContent\(this, this\.#reactiveQuery/,
    "Message refreshes must preserve the active reactive filter and reveal matching details.");
assert.match(searchableLayouts[1] ?? "", /data-reactive-content="\$\{escapeHtml\(item\.path\)\}"/,
    "Memory content items must expose their complete canonical path, not only compact labels.");
assert.match(searchableLayouts[2] ?? "", /data-reactive-content=[\s\S]*picture\.description[\s\S]*picture\.description_source/,
    "Picture thumbnails must expose complete record descriptions and metadata to reactive filtering.");

console.log("backlog-navigation-contracts: ok");
