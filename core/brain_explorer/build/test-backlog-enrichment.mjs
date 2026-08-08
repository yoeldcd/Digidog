import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const renderer = readFileSync(new URL("../src/presentation/backlog/renderers/backlog-layout-renderer.ts", import.meta.url), "utf8");
const view = readFileSync(new URL("../src/presentation/backlog/layouts/backlog-view.ts", import.meta.url), "utf8");
const client = readFileSync(new URL("../src/infrastructure/shared/http/clients/brain-api-client.ts", import.meta.url), "utf8");
const action = readFileSync(new URL("../src/application/backlog/dtos/requests/backlog-mutation-request.ts", import.meta.url), "utf8");

assert.match(renderer, /data-action="enrich-task-draft"/u, "task editor must expose the enrich control");
assert.match(renderer, /data-role="task-enrichment-overlay"[^>]*role="status"/u, "task editor must expose a visible enrichment status layer");
assert.match(renderer, /class="task-open-viewer"/u, "compact task titles must open the read-only viewer");
assert.doesNotMatch(renderer, /class="task-description-rich"/u, "compact rows must not render task descriptions");
assert.match(view, /async #enrichTaskDraft\(\): Promise<void>/u, "view must own one typed draft enrichment workflow");
assert.match(view, /new AbortController\(\)/u, "draft enrichment must own a cancellable request");
assert.match(view, /this\.#draftEnrichmentController\.abort\(\)/u, "the Pause state must abort the active request");
assert.match(view, /control\.disabled = active/u, "draft fields must lock while enrichment is active");
assert.match(view, /<span>Pause<\/span>/u, "the enrich action must become Pause while active");
assert.match(client, /enrichBacklogTask\(taskId: string\): Promise<ApiResponse<BacklogEnrichmentPayload>>/u, "client must return a typed enrichment payload");
assert.match(client, /enrichBacklogDraft\([\s\S]*?draft: BacklogDraftEnrichmentRequest,[\s\S]*?signal\?: AbortSignal[\s\S]*?Promise<ApiResponse<BacklogDraftEnrichmentPayload>>/u, "client must expose a typed cancellable draft contract");
assert.match(action, /"enrich-draft"/u, "the mutation action vocabulary must include draft enrichment");
assert.doesNotMatch(client, /enrichBacklogTask\([^)]*any/u, "enrichment must not weaken TypeScript contracts");

console.log("Backlog enrichment contracts passed.");
