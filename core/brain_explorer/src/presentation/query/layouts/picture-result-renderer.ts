import { escapeHtml } from "../../shared/utils/html.ts";
import { renderDescriptionCard } from "../../shared/components/description-card.ts";
import type { QueryEvidenceViewModel } from "../view_models/query-view-model.ts";

/** Render one image result as a navigable square tile with structured analysis on focus. */
export function renderPictureResult(item: QueryEvidenceViewModel): string {
    const resourceId = escapeHtml(item.resourceId);
    const title = escapeHtml(item.title);
    const imageUrl = `/api/pictures/file?id=${encodeURIComponent(item.resourceId)}`;

    return `<li class="query-result-card picture-result-card" role="link" tabindex="0" data-route="pictures" data-target-id="${resourceId}" data-route-target="${escapeHtml(JSON.stringify(item.target))}" aria-label="Open ${title}">
        <img src="${escapeHtml(imageUrl)}" alt="" loading="lazy" decoding="async">
        <span class="picture-result-title">${title}</span>
        <div class="picture-result-description">${renderDescriptionCard(item.markdown, { title: "Image analysis", openAll: true })}</div>
    </li>`;
}