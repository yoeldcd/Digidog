/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Shared browser helpers for the live wiki runtime.
 */

/**
 * Fetch and parse the external wiki manifest.
 *
 * @returns {Promise<object>} Manifest JSON.
 */
export async function loadManifest() {
    const manifestPath = window.WIKI_CONFIG?.manifestPath || 'data/index.json';
    const response = await fetch(manifestPath, { cache: 'no-store' });

    if (!response.ok) {
        throw new Error(`Unable to load wiki manifest: ${response.status}`);
    }

    return response.json();
}

/**
 * Build a source href from a manifest page source path.
 *
 * @param {string} source - POSIX source path.
 * @returns {string} Browser href.
 */
export function sourceToHref(source) {
    return `../${String(source || '').split('/').map(encodeURIComponent).join('/')}`;
}

/**
 * Normalize a reference term.
 *
 * @param {string} value - Raw term.
 * @returns {string} Normalized term.
 */
export function normalizeReferenceTerm(value) {
    return String(value || '').trim().replace(/\s+/g, ' ').toLowerCase();
}

/**
 * Match the Node-generated heading slug contract.
 *
 * @param {string} rawText - Heading text.
 * @returns {string} Heading anchor.
 */
export function getHeadingAnchor(rawText) {
    return String(rawText || '').toLowerCase().replace(/[^\w]+/g, '-');
}

/**
 * Build lookup variants for a term.
 *
 * @param {string} text - Reference text.
 * @returns {string[]} Variants.
 */
export function referenceTermVariants(text) {
    const value = String(text || '').trim();
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
 * Parse the current hash route.
 *
 * @returns {{pageId: string|null, anchor: string|null}} Route values.
 */
export function parseHashRoute() {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    return {
        pageId: params.get('page'),
        anchor: params.get('anchor')
    };
}

/**
 * Build a hash route for a page and optional heading.
 *
 * @param {string} pageId - Target page id.
 * @param {string|null} [anchor=null] - Optional anchor.
 * @returns {string} Hash route.
 */
export function buildPageHash(pageId, anchor = null) {
    const params = new URLSearchParams();
    params.set('page', pageId);

    if (anchor) {
        params.set('anchor', anchor);
    }

    return `#${params.toString()}`;
}

/**
 * Normalize a POSIX path against a POSIX base directory.
 *
 * @param {string} baseDir - Base directory.
 * @param {string} target - Target path.
 * @returns {string} Normalized path.
 */
export function normalizePosixPath(baseDir, target) {
    const parts = [];
    const joined = `${baseDir ? `${baseDir}/` : ''}${target}`;

    joined.split('/').forEach(part => {
        if (!part || part === '.') return;
        if (part === '..') {
            parts.pop();
            return;
        }
        parts.push(part);
    });

    return parts.join('/');
}

/**
 * Get the POSIX directory portion of a path.
 *
 * @param {string} source - POSIX path.
 * @returns {string} Directory path.
 */
export function posixDirname(source) {
    const index = String(source || '').lastIndexOf('/');
    return index === -1 ? '' : source.slice(0, index);
}

/**
 * Escape text for HTML insertion.
 *
 * @param {string} value - Raw value.
 * @returns {string} Escaped value.
 */
export function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
