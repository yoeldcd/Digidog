import { escapeHtml, renderMarkdown } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import type { QueryEvidenceViewModel } from "../view_models/query-view-model.ts";

/** Render one task result as an actionable backlog card. */
export function renderBacklogResult(item: QueryEvidenceViewModel): string {
    const identifier = escapeHtml(item.resourceId);
    return `<li class="query-result-card backlog-result-card" role="link" tabindex="0" data-route="backlog" data-target-id="${escapeHtml(item.resourceId)}" data-route-target="${escapeHtml(JSON.stringify(item.target))}"><article>
        <header class="query-card-header"><span class="query-card-icon">${icon("checkSquare")}</span><div><div class="query-card-badges"><span class="query-badge is-identity">${identifier}</span><span class="query-badge">Task</span></div><h3>${escapeHtml(item.title)}</h3></div></header>
        <div class="query-card-body">${renderMarkdown(item.markdown)}</div>
        <footer class="query-card-footer"><span>${escapeHtml(item.mechanism)} match</span><button type="button" class="query-card-open" data-route="backlog" data-target-id="${identifier}" data-route-target="${escapeHtml(JSON.stringify(item.target))}"><span>Open</span>${icon("chevronRight")}</button></footer>
    </article></li>`;
}