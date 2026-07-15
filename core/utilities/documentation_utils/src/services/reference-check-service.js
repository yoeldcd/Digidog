/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Validates explicit markdown references against navigable heading anchors.
 */

import { buildMarkdownPages } from './markdown-discovery-service.js';
import { extractPageHeadings } from './heading-index-service.js';
import { ReferenceMentionDTO } from '../models/wiki-models.js';
import { resolveExistingDocumentationPath, resolveWikiDir } from '../utils/path-utils.js';
import { getReferenceTermVariants, normalizeReferenceTerm } from '../utils/text-utils.js';

const IGNORED_CHECK_TERMS = new Set([
    'true',
    'false',
    'null',
    'none',
    'yes',
    'no',
    'string',
    'number',
    'boolean',
    'array',
    'object',
    'int',
    'float',
    'dict',
    'list',
    'set',
    'value',
    'name',
    'type',
    'default'
]);

/**
 * Run the public reference-check command.
 *
 * @param {import('../models/wiki-models.js').CliCommandDTO} command - Parsed CLI command.
 * @returns {number} Exit code.
 */
export function checkDocumentationReferences(command) {
    const documentationPath = resolveExistingDocumentationPath(command.documentationPath);
    const pages = buildMarkdownPages({
        documentationPath,
        wikiDir: resolveWikiDir(documentationPath)
    });

    if (pages.length === 0) {
        console.warn(`Warning: No Markdown files found in: ${documentationPath}`);
        return 0;
    }

    return runReferenceHeaderCheck(pages);
}

/**
 * Run explicit-reference heading validation.
 *
 * @param {import('../models/wiki-models.js').WikiPageDTO[]} pages - Page DTOs.
 * @param {object} [options={}] - Check options.
 * @param {boolean} [options.failOnMissing=true] - Return non-zero when missing references exist.
 * @param {number} [options.maxItems] - Maximum missing items to print.
 * @returns {number} Exit code.
 */
export function runReferenceHeaderCheck(pages, options = {}) {
    const failOnMissing = options.failOnMissing !== false;
    const headingTerms = buildHeadingTermSet(pages);
    const missingByTerm = new Map();

    pages.flatMap(extractExplicitReferenceMentions).forEach(mention => {
        if (hasMatchingHeading(mention.term, headingTerms)) return;

        if (!missingByTerm.has(mention.normalizedTerm)) {
            missingByTerm.set(mention.normalizedTerm, {
                term: mention.term,
                type: mention.type,
                mentions: []
            });
        }

        missingByTerm.get(mention.normalizedTerm).mentions.push({
            page: mention.page,
            line: mention.line
        });
    });

    return reportMissingReferences({ missingByTerm, failOnMissing, maxItems: options.maxItems });
}

/**
 * Build a set of all valid heading lookup terms.
 *
 * @param {import('../models/wiki-models.js').WikiPageDTO[]} pages - Page DTOs.
 * @returns {Set<string>} Normalized terms.
 */
function buildHeadingTermSet(pages) {
    const terms = new Set();

    pages.flatMap(extractPageHeadings).forEach(heading => {
        getReferenceTermVariants(heading.term).forEach(variant => {
            terms.add(normalizeReferenceTerm(variant));
        });
    });

    return terms;
}

/**
 * Extract explicit backtick and bold mentions from one markdown page.
 *
 * @param {import('../models/wiki-models.js').WikiPageDTO} page - Page DTO.
 * @returns {ReferenceMentionDTO[]} Mention DTOs.
 */
function extractExplicitReferenceMentions(page) {
    const mentions = [];
    const lines = page.markdownText.split(/\r?\n/);
    let inFence = false;

    lines.forEach((line, index) => {
        if (/^\s*(```|~~~)/.test(line)) {
            inFence = !inFence;
            return;
        }

        if (inFence || /^\s*#{1,6}\s+/.test(line)) return;

        extractExplicitReferenceTerms(line).forEach(term => {
            if (!isCheckableReferenceTerm(term)) return;

            mentions.push(new ReferenceMentionDTO({
                term,
                normalizedTerm: normalizeReferenceTerm(term),
                type: getReferenceType(term),
                page: page.source,
                line: index + 1
            }));
        });
    });

    return mentions;
}

/**
 * Extract inline code and bold reference terms from one markdown line.
 *
 * @param {string} line - Markdown line.
 * @returns {string[]} Terms.
 */
function extractExplicitReferenceTerms(line) {
    return [
        ...extractTermsWithPattern(line, /`([^`]+)`/g),
        ...extractTermsWithPattern(line, /\*\*([^*\n]+)\*\*/g)
    ];
}

/**
 * Extract terms with a regular expression.
 *
 * @param {string} line - Markdown line.
 * @param {RegExp} pattern - Pattern with one capture group.
 * @returns {string[]} Terms.
 */
function extractTermsWithPattern(line, pattern) {
    const terms = [];
    let match;

    while ((match = pattern.exec(line)) !== null) {
        const term = match[1].trim();
        if (term) terms.push(term);
    }

    return terms;
}

/**
 * Determine whether a term should be checked against headings.
 *
 * @param {string} term - Reference term.
 * @returns {boolean} True when checkable.
 */
function isCheckableReferenceTerm(term) {
    const value = String(term || '').trim();
    const normalized = normalizeReferenceTerm(value);

    if (!value || value.length < 2) return false;
    if (IGNORED_CHECK_TERMS.has(normalized)) return false;
    if (/^-?\d+(?:\.\d+)?$/.test(value)) return false;

    return (
        /^-{1,2}[\w-]+$/.test(value)
        || /^<[^>]+>$/.test(value)
        || /[\\/]/.test(value)
        || /\.[A-Za-z0-9]+$/.test(value)
        || /[()]/.test(value)
        || /[_-]/.test(value)
        || /^[A-Z][A-Za-z0-9_]+$/.test(value)
    );
}

/**
 * Classify a reference term for diagnostics.
 *
 * @param {string} term - Reference term.
 * @returns {string} Reference type.
 */
function getReferenceType(term) {
    if (/^-{1,2}[\w-]+$/.test(term)) return 'flag';
    if (/[\\/]/.test(term) || /\.[A-Za-z0-9]+$/.test(term)) return 'file';
    if (/^[A-Za-z_]\w*(?:\([^)]*\))?$/.test(term)) return 'symbol';
    return 'term';
}

/**
 * Check whether a term variant has a matching heading.
 *
 * @param {string} term - Reference term.
 * @param {Set<string>} headingTerms - Valid heading terms.
 * @returns {boolean} True when matched.
 */
function hasMatchingHeading(term, headingTerms) {
    return getReferenceTermVariants(term).some(variant => {
        return headingTerms.has(normalizeReferenceTerm(variant));
    });
}

/**
 * Print missing reference diagnostics.
 *
 * @param {object} params - Report parameters.
 * @param {Map<string, object>} params.missingByTerm - Missing references grouped by term.
 * @param {boolean} params.failOnMissing - Whether missing references fail.
 * @param {number} [params.maxItems] - Max items to print.
 * @returns {number} Exit code.
 */
function reportMissingReferences({ missingByTerm, failOnMissing, maxItems }) {
    const missing = Array.from(missingByTerm.values()).sort((left, right) => {
        return left.term.localeCompare(right.term);
    });

    if (missing.length === 0) {
        console.log('OK: every explicit backtick/bold reference has a matching navigable heading.');
        return 0;
    }

    const visibleCount = Number.isInteger(maxItems) ? maxItems : missing.length;
    const visibleMissing = missing.slice(0, visibleCount);

    console.log(`Missing navigable headers for ${missing.length} explicit references:\n`);
    visibleMissing.forEach(item => printMissingReferenceItem(item));

    if (visibleMissing.length < missing.length) {
        console.log(`\n... ${missing.length - visibleMissing.length} more missing references. Run check mode for the full list.`);
    }

    console.log('\nAdd a matching Markdown heading for each reference inside the appropriate domain document.');
    return failOnMissing ? 1 : 0;
}

/**
 * Print one missing reference diagnostic item.
 *
 * @param {object} item - Missing item.
 * @returns {void}
 */
function printMissingReferenceItem(item) {
    console.log(`- \`${item.term}\` (${item.type})`);
    item.mentions.slice(0, 8).forEach(mention => {
        console.log(`  - ${mention.page}:${mention.line}`);
    });

    if (item.mentions.length > 8) {
        console.log(`  - ... ${item.mentions.length - 8} more`);
    }
}
