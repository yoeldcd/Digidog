/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Text normalization helpers used across Node services and generated manifests.
 */

/**
 * Extract the top-level log domain from a domain value.
 *
 * @param {string} value - Raw log domain.
 * @returns {string} Superdomain.
 */
export function getLogSuperdomain(value) {
    return String(value || '').split('.')[0].trim();
}

/**
 * Normalize a reference term for exact-but-case-insensitive matching.
 *
 * @param {string} value - Raw term.
 * @returns {string} Normalized term.
 */
export function normalizeReferenceTerm(value) {
    return String(value || '').trim().replace(/\s+/g, ' ').toLowerCase();
}

/**
 * Convert inline Markdown heading text into a plain lookup term.
 *
 * @param {string} headingText - Raw heading text.
 * @returns {string} Plain heading term.
 */
export function headingTextToTerm(headingText) {
    return String(headingText || '')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/\*\*([^*\n]+)\*\*/g, '$1')
        .replace(/\*([^*\n]+)\*/g, '$1')
        .replace(/~~([^~\n]+)~~/g, '$1')
        .trim();
}

/**
 * Match the browser renderer heading id generation.
 *
 * @param {string} rawHeadingText - Raw heading text.
 * @returns {string} Heading anchor id.
 */
export function getHeadingAnchor(rawHeadingText) {
    return String(rawHeadingText || '').toLowerCase().replace(/[^\w]+/g, '-');
}

/**
 * Build equivalent lookup terms for symbols with or without empty parentheses.
 *
 * @param {string} term - Reference term.
 * @returns {string[]} Lookup variants.
 */
export function getReferenceTermVariants(term) {
    const value = String(term || '').trim();
    const variants = new Set([value]);
    const functionMatch = value.match(/^([A-Za-z_]\w*)\((?:[^)]*)\)$/);

    if (functionMatch) {
        variants.add(functionMatch[1]);
        variants.add(`${functionMatch[1]}()`);
    } else if (/^[A-Za-z_]\w*$/.test(value)) {
        variants.add(`${value}()`);
    }

    return Array.from(variants).filter(Boolean);
}

/**
 * Compare two domain names with conservative word-overlap heuristics.
 *
 * @param {string} leftDomain - First domain.
 * @param {string} rightDomain - Second domain.
 * @returns {boolean} True when domains match.
 */
export function domainsMatch(leftDomain, rightDomain) {
    const leftWords = String(leftDomain || '').toLowerCase().split(/[-_.]/).filter(word => word.length > 2);
    const rightWords = String(rightDomain || '').toLowerCase().split(/[-_.]/).filter(word => word.length > 2);
    const intersection = leftWords.filter(word => rightWords.includes(word));

    if (intersection.length >= 2) return true;
    if (leftWords.length === 1 && rightWords.includes(leftWords[0])) return true;
    if (rightWords.length === 1 && leftWords.includes(rightWords[0])) return true;

    return String(leftDomain || '').toLowerCase() === String(rightDomain || '').toLowerCase();
}
