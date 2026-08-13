import assert from "node:assert/strict";

import { normalizeActiveQuerySource } from "../src/presentation/query/view_models/query-source-selection.ts";

const selectedMemory = normalizeActiveQuerySource("memory", ["memory", "knowledge"]);
assert.equal(selectedMemory, "memory", "a present source remains selected");

const knowledgeOnlyResponse = normalizeActiveQuerySource(selectedMemory, ["knowledge"]);
assert.equal(knowledgeOnlyResponse, "all", "a stale Memory tab resets when the new response only contains Knowledge");

console.log("query source selection contract passed");