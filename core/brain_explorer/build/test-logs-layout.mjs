import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const view = await readFile(new URL("../src/presentation/components/logs-view.ts", import.meta.url), "utf8");
const tree = await readFile(new URL("../src/presentation/components/structure-tree.ts", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/views.css", import.meta.url), "utf8");

assert.match(view, /#treeMode = "domain"/);
assert.match(view, /id: "tree-domain"[^\n]*active: this\.#treeMode === "domain"/);
assert.match(view, /id: "tree-date"[^\n]*active: this\.#treeMode === "date"/);
assert.match(view, /#dateTreeNodes\(\)/);
assert.match(view, /LOG_MONTH_LABELS/);
assert.match(view, /sortDirection: this\.#treeMode === "date" \? "desc" : "asc"/);
assert.match(view, /presentation: "log"/);
assert.match(view, /<details class="log-entry-card">/);
assert.doesNotMatch(view, /<details class="log-entry-card"\s+open/);
assert.match(view, /class="log-date-badge"/);
assert.match(view, /class="log-entry-tags"/);
assert.match(view, /class="log-entry-body"/);
assert.match(tree, /aria-pressed=/);
assert.match(tree, /sortKey \|\| left\.label/);
assert.match(styles, /\.log-entry-summary\s*\{[^}]*grid-template-columns:\s*88px minmax\(0, 1fr\) auto/s);
assert.match(styles, /\.log-entry-body\s*\{[^}]*grid-template-columns:\s*repeat\(auto-fit/s);
assert.match(styles, /\.log-entry-card\[open\] \.log-entry-chevron/);
assert.match(styles, /\.structure-tree-toolbar \.icon-action\.is-active/);

console.log("Logs tree and collapsible-card contract passed.");
