import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const dto = await readFile(new URL("../src/application/dashboard/dtos/responses/context-response.ts", import.meta.url), "utf8");
const view = await readFile(new URL("../src/presentation/dashboard/layouts/dashboard-view.ts", import.meta.url), "utf8");

assert.match(dto, /interface ContextLastChange[\s\S]*retrieve_command: string;[\s\S]*title: string;[\s\S]*type: string;/);
assert.match(dto, /id\?: string \| number;/);
assert.match(dto, /last_change\?: ContextLastChange;/);
assert.match(dto, /name\?: string;/);
assert.match(dto, /retrieve_command\?: string;/);
assert.match(dto, /use_when\?: string;/);
assert.match(dto, /title\?: string;/);
assert.match(view, /section\.kind === "logs"\) return \{ domain: item\.domain \|\| "" \}/);
assert.match(view, /lastChange\?\.type/);
assert.match(view, /change\?\.retrieve_command/);
assert.match(view, /section\.kind === "profiles"\) return \{ profile: item\.name \|\| "" \}/);
assert.match(view, /item\.retrieve_command\?\.match/);
assert.doesNotMatch(view, /#sortLogsNewestFirst/);

console.log("Compact dashboard context contract passed.");
