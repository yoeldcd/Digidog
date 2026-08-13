import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../src/presentation/query/layouts/query-view.ts", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/views.css", import.meta.url), "utf8");
const rendererNames = ["memory", "knowledge", "message", "picture", "log", "backlog"];
const renderers = await Promise.all(rendererNames.map((name) => readFile(new URL(`../src/presentation/query/layouts/${name}-result-renderer.ts`, import.meta.url), "utf8")));
const rendererSource = renderers.join("\n");

assert.match(source, /query-source-tabs|query-source-tab/);
assert.match(source, /query-source-section/);
assert.match(source, /query-pagination|query-page-size|query-page-status/);
assert.match(source, /PAGE_SIZES[^;]*\[10, 25, 50, 100\]/);
assert.match(source, /pageSize: "0"/);
assert.match(source, /#localResponse/);
assert.match(source, /implements ReactiveContentFilterLayout/);
assert.match(source, /applyReactiveContentFilter\(query: string\)[\s\S]*#reactiveQuery = query\.trim\(\)[\s\S]*#render\(\)/);
assert.match(source, /sourceItems[\s\S]*#reactiveQuery\.toLocaleLowerCase\(\)[\s\S]*\.includes\(needle\)/);
assert.doesNotMatch(source, /#syncTruncatedBodies|is-truncated/);
assert.doesNotMatch(source, /\["all", \.\.\.sources\]|data-view-all-results|>All</);
assert.doesNotMatch(source, /data-source-tab[\s\S]{0,400}#runQuery/);
assert.match(source, /setRouteTarget/);
assert.match(source, /dataset\.routeTarget/);
assert.match(source, /JSON\.parse\(serializedTarget\)/);
assert.match(rendererSource, /data-route-target=/);
assert.match(source, /<article class="query-results"[\s\S]*query-results-header[\s\S]*query-source-tabs[\s\S]*query-results-toolbar-region[\s\S]*query-results-panel/);
assert.doesNotMatch(source, /<\/article>\s*\$\{this\.#renderSourcePanel\(\)\}/);
assert.doesNotMatch(source, />Response</);

assert.match(rendererSource, /query-result-card/);
assert.match(rendererSource, /query-card-badges/);
assert.match(rendererSource, /data-route=/);
assert.match(rendererSource, /data-target-id=/);
assert.match(rendererSource, /picture-result-card/);
assert.match(rendererSource, /api\/pictures\/file\?id=/);
assert.match(rendererSource, /picture-result-title/);
assert.match(rendererSource, /picture-result-description/);
assert.match(rendererSource, /renderDescriptionCard\(item\.markdown, \{ title: "Image analysis", openAll: true \}\)/);
assert.doesNotMatch(rendererSource, /query-card-context/);

const queryStylesStart = styles.indexOf(".query-source-tabs");
const queryStylesEnd = styles.indexOf(".logs-layout", queryStylesStart);
const queryStyles = styles.slice(queryStylesStart, queryStylesEnd);
assert.notEqual(queryStyles, styles, "query CSS region must be present");
assert.match(queryStyles, /\.query-results-header\s*\{[\s\S]*position:\s*sticky/);
assert.match(queryStyles, /\.query-result-card\s*\{[\s\S]*border:\s*1px solid var\(--border\)/);
assert.match(queryStyles, /\.query-card-body\s*\{[\s\S]*font-size:\s*15px/);
assert.match(queryStyles, /\.query-card-open\s*\{[\s\S]*border:\s*0/);
assert.match(queryStyles, /\.query-source-list\.is-source-pictures\s*\{[\s\S]*grid-template-columns:\s*repeat\(4/);
assert.match(queryStyles, /\.picture-result-overlay[\s\S]*transform:\s*translateY/);
assert.match(queryStyles, /\.picture-result-link:hover \.picture-result-overlay[\s\S]*translateY\(0\)/);
assert.match(queryStyles, /@media \(max-width: 720px\)[\s\S]*\.query-source-list\.is-source-pictures\s*\{\s*grid-template-columns:\s*1fr/);
assert.match(queryStyles, /\.query-pagination\s*\{/);
assert.match(queryStyles, /\.query-card-body\s*\{[^}]*max-height:\s*none;[^}]*overflow:\s*visible/s);
assert.doesNotMatch(queryStyles, /is-truncated|content:\s*"…"|max-height:\s*80rem/);

console.log("query results layout contract passed");
