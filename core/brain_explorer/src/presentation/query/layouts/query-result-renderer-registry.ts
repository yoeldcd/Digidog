/** Query source renderer registry contracts. */
import { escapeHtml, renderMarkdown } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { QueryEvidenceViewModel } from "../view_models/query-view-model.ts";
import { renderBacklogResult } from "./backlog-result-renderer.ts";
import { renderKnowledgeResult } from "./knowledge-result-renderer.ts";
import { renderLogResult } from "./log-result-renderer.ts";
import { renderMemoryResult } from "./memory-result-renderer.ts";
import { renderMessageResult } from "./message-result-renderer.ts";
import { renderPictureResult } from "./picture-result-renderer.ts";

/** Render one normalized query evidence item. */
export type QueryResultRenderer = (item: QueryEvidenceViewModel) => string;

/** Render evidence whose source has no specialized renderer. */
export const fallbackQueryResultRenderer: QueryResultRenderer = (item): string => `<li class="query-result-card generic-result-card"><article>
    <header class="query-card-header"><span class="query-card-icon">${icon("document")}</span><div><div class="query-card-badges"><span class="query-badge">${escapeHtml(item.source)}</span><span class="query-badge">${escapeHtml(item.mechanism)}</span></div><h3>${escapeHtml(item.title)}</h3></div></header>
    <div class="query-card-body">${renderMarkdown(item.markdown)}</div>
</article></li>`;

/** Immutable mapping from canonical source names to specialized renderers. */
export const queryResultRenderers: Readonly<Record<string, QueryResultRenderer>> = {
    memory: renderMemoryResult, knowledge: renderKnowledgeResult, messages: renderMessageResult,
    pictures: renderPictureResult, backlog: renderBacklogResult, logs: renderLogResult,
};

/** Resolve the specialized renderer for a source or the safe fallback. */
export function resolveQueryResultRenderer(source: string, registry: Readonly<Record<string, QueryResultRenderer>> = queryResultRenderers): QueryResultRenderer {
    return registry[source] ?? fallbackQueryResultRenderer;
}