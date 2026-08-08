import { escapeHtml, renderMarkdown } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { QueryEvidenceViewModel } from "../view_models/query-view-model.ts";

/** Render one graph-backed result as a knowledge entity card. */
export function renderKnowledgeResult(item: QueryEvidenceViewModel): string {
    const scope = escapeHtml(item.origin.scope || "all");
    return `<li class="query-result-card knowledge-result-card" role="link" tabindex="0" data-route="knowledge" data-target-id="${escapeHtml(item.resourceId)}" data-route-target="${escapeHtml(JSON.stringify(item.target))}"><article>
        <header class="query-card-header"><span class="query-card-icon">${icon("graph")}</span><div><div class="query-card-badges"><span class="query-badge is-scope">${scope}</span><span class="query-badge">Knowledge</span></div><h3>${escapeHtml(item.title)}</h3></div></header>
        <div class="query-card-body">${renderMarkdown(item.markdown)}</div>
        <footer class="query-card-footer"><span>${escapeHtml(item.mechanism)} relation</span><button type="button" class="query-card-open" data-route="knowledge" data-target-id="${escapeHtml(item.resourceId)}" data-route-target="${escapeHtml(JSON.stringify(item.target))}"><span>Open</span>${icon("chevronRight")}</button></footer>
    </article></li>`;
}