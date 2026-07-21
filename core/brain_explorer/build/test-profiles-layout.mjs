import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const view = await readFile(new URL("../src/presentation/profiles/layouts/profiles-view.ts", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/views.css", import.meta.url), "utf8");

assert.match(view, /class="structure-layout profiles-layout"/);
assert.match(view, /class="structure-tree"/);
assert.match(view, /class="structure-content"/);
assert.match(styles, /\.profiles-layout\s*\{[^}]*grid-template-columns:\s*auto minmax\(0, 1fr\)/s);
assert.match(styles, /\.profiles-layout > \.structure-content\s*\{[^}]*min-width:\s*0[^}]*isolation:\s*isolate/s);
assert.doesNotMatch(styles, /\.profiles-layout\s*\{[^}]*grid-template-columns:\s*minmax\(190px, 20%\)/s);

console.log("Profiles layout contract passed.");
