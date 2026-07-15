/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Builds the cross-page heading index consumed by the live markdown reader.
 */

import { WikiHeadingDTO } from '../models/wiki-models.js';
import { getHeadingAnchor, headingTextToTerm, normalizeReferenceTerm } from '../utils/text-utils.js';

const HEADING_PATTERN = /^(#{1,6})\s+(.+)$/gm;

/**
 * Extract indexed headings from all pages.
 *
 * @param {import('../models/wiki-models.js').WikiPageDTO[]} pages - Markdown pages.
 * @returns {WikiHeadingDTO[]} Heading DTOs.
 */
export function extractAllPageHeadings(pages) {
    return pages.flatMap(extractPageHeadings);
}

/**
 * Extract indexed headings from one page.
 *
 * @param {import('../models/wiki-models.js').WikiPageDTO} page - Page DTO.
 * @returns {WikiHeadingDTO[]} Heading DTOs.
 */
export function extractPageHeadings(page) {
    const headings = [];
    let match;

    while ((match = HEADING_PATTERN.exec(page.markdownText)) !== null) {
        const level = match[1].length;
        const rawText = match[2].trim();
        const term = headingTextToTerm(rawText);

        if (!term) continue;

        headings.push(new WikiHeadingDTO({
            term,
            normalizedTerm: normalizeReferenceTerm(term),
            level,
            pageId: page.id,
            pageTitle: page.title,
            source: page.source,
            anchor: getHeadingAnchor(rawText)
        }));
    }

    HEADING_PATTERN.lastIndex = 0;
    return headings;
}
