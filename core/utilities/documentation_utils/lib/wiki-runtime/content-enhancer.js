/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Enhances rendered markdown with links, Mermaid, Prism, TOC, and search.
 */

import {
    buildPageHash,
    getHeadingAnchor,
    normalizePosixPath,
    normalizeReferenceTerm,
    posixDirname,
    referenceTermVariants
} from './wiki-utils.js';

const PANNED_MERMAID_SVGS = new WeakSet();

/**
 * Configure Marked renderer and options.
 *
 * @returns {void}
 */
export function configureMarkdownRenderer() {
    const renderer = new marked.Renderer();

    renderer.heading = function({ text, depth, raw, tokens }) {
        const anchor = getHeadingAnchor(raw || text);
        const headingText = tokens ? this.parser.parseInline(tokens) : text;
        return `<h${depth} id="${anchor}">${headingText}</h${depth}>`;
    };

    marked.setOptions({
        renderer,
        gfm: true,
        breaks: false,
        pedantic: false
    });
}

/**
 * Render markdown to HTML.
 *
 * @param {string} markdown - Markdown source.
 * @returns {string} Rendered HTML.
 */
export function renderMarkdown(markdown) {
    return marked.parse(markdown || '');
}

/**
 * Run all post-render markdown enhancements.
 *
 * @param {object} params - Enhancement parameters.
 * @param {HTMLElement} params.root - Rendered markdown root.
 * @param {object} params.manifest - Wiki manifest.
 * @param {object|null} params.page - Current page.
 * @param {string|null} params.anchor - Target anchor.
 * @returns {void}
 */
export function enhanceRenderedMarkdown({ root, manifest, page, anchor }) {
    rewriteLocalMarkdownLinks({ root, manifest, page });
    enhanceReferenceLinks({ root, manifest, page });
    enhanceHeadingTextLinks({ root, manifest, page });
    enhanceMermaid();
    buildSidebarToc({ root, page });
    addCopyButtons(root);
    Prism.highlightAll();
    scrollToAnchor(anchor || window.location.hash.replace(/^#/, ''));
}

/**
 * Attach in-page search behavior.
 *
 * @param {HTMLElement} root - Rendered markdown root.
 * @returns {void}
 */
export function bindSearch(root) {
    const searchInput = document.getElementById('wiki-search');
    let originalContent = root.innerHTML;

    searchInput?.addEventListener('input', event => {
        const query = event.target.value.trim();
        root.innerHTML = originalContent;

        if (query.length < 2) {
            Prism.highlightAll();
            return;
        }

        highlightTextNodes(root, new RegExp(query, 'gi'));
        Prism.highlightAll();
    });

    return {
        refresh() {
            originalContent = root.innerHTML;
            if (searchInput) searchInput.value = '';
        }
    };
}

/**
 * Rewrite local markdown links to live reader routes.
 *
 * @param {object} params - Rewrite parameters.
 * @param {HTMLElement} params.root - Rendered markdown root.
 * @param {object} params.manifest - Wiki manifest.
 * @param {object|null} params.page - Active page.
 * @returns {void}
 */
function rewriteLocalMarkdownLinks({ root, manifest, page }) {
    if (!page) return;

    const pagesBySource = new Map(manifest.pages.map(item => [item.source.toLowerCase(), item]));
    const activeDir = posixDirname(page.source);

    root.querySelectorAll('a[href]').forEach(anchorElement => {
        const rawHref = anchorElement.getAttribute('href');
        if (!rawHref || /^[a-z][a-z0-9+.-]*:/i.test(rawHref)) return;

        const mdMatch = rawHref.match(/^([^#?]+?\.(?:md|markdown))([#?].*)?$/i);
        if (!mdMatch) return;

        const sourcePath = normalizePosixPath(activeDir, mdMatch[1]).toLowerCase();
        const targetPage = pagesBySource.get(sourcePath);
        if (!targetPage) return;

        const anchor = mdMatch[2]?.startsWith('#') ? mdMatch[2].slice(1) : null;
        anchorElement.setAttribute('href', buildPageHash(targetPage.id, anchor));
    });
}

/**
 * Enhance inline code references with heading links.
 *
 * @param {object} params - Link parameters.
 * @param {HTMLElement} params.root - Rendered markdown root.
 * @param {object} params.manifest - Wiki manifest.
 * @param {object|null} params.page - Active page.
 * @returns {void}
 */
function enhanceReferenceLinks({ root, manifest, page }) {
    const headingIndex = buildLocalHeadingIndex(root);

    root.querySelectorAll('code').forEach(codeElement => {
        if (codeElement.closest('pre, h1, h2, h3, h4, h5, h6, a')) return;

        const href = hrefForReferenceText({
            text: codeElement.textContent.trim(),
            headingIndex,
            manifest,
            page
        });

        if (!href) return;

        const link = document.createElement('a');
        link.href = href;
        link.className = 'inline-code-link';
        link.title = `Open ${codeElement.textContent.trim()}`;
        codeElement.replaceWith(link);
        link.appendChild(codeElement);
    });
}

/**
 * Build a map of local heading terms to anchors.
 *
 * @param {HTMLElement} root - Rendered markdown root.
 * @returns {Map<string, string>} Heading index.
 */
function buildLocalHeadingIndex(root) {
    const index = new Map();

    root.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(heading => {
        const key = normalizeReferenceTerm(heading.textContent);
        if (key && heading.id && !index.has(key)) index.set(key, heading.id);
    });

    return index;
}

/**
 * Resolve a reference text to a heading route.
 *
 * @param {object} params - Resolve parameters.
 * @param {string} params.text - Reference text.
 * @param {Map<string, string>} params.headingIndex - Local headings.
 * @param {object} params.manifest - Wiki manifest.
 * @param {object|null} params.page - Active page.
 * @returns {string|null} Href.
 */
function hrefForReferenceText({ text, headingIndex, manifest, page }) {
    if (!text) return null;

    for (const variant of referenceTermVariants(text)) {
        const localAnchor = headingIndex.get(normalizeReferenceTerm(variant));
        if (localAnchor && page) return buildPageHash(page.id, localAnchor);
    }

    const normalizedTerms = referenceTermVariants(text).map(normalizeReferenceTerm);
    const match = manifest.headings.find(heading => normalizedTerms.includes(heading.normalizedTerm));

    return match ? buildPageHash(match.pageId, match.anchor) : null;
}

/**
 * Enhance plain text heading mentions with links.
 *
 * @param {object} params - Enhancement parameters.
 * @param {HTMLElement} params.root - Rendered markdown root.
 * @param {object} params.manifest - Wiki manifest.
 * @param {object|null} params.page - Active page.
 * @returns {void}
 */
function enhanceHeadingTextLinks({ root, manifest, page }) {
    const candidates = buildHeadingCandidates({ root, manifest, page });
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
            return shouldSkipTextAutolink(node) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
        }
    });
    const textNodes = [];
    let node;

    while ((node = walker.nextNode())) {
        textNodes.push(node);
    }

    textNodes.forEach(textNode => linkHeadingTextNode(textNode, candidates));
}

/**
 * Build text-link candidates from local and manifest headings.
 *
 * @param {object} params - Candidate parameters.
 * @param {HTMLElement} params.root - Rendered root.
 * @param {object} params.manifest - Wiki manifest.
 * @param {object|null} params.page - Active page.
 * @returns {Array<object>} Candidates.
 */
function buildHeadingCandidates({ root, manifest, page }) {
    const candidates = [];
    const seen = new Set();

    root.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(heading => {
        if (heading.id && page) addHeadingCandidate({ candidates, seen, term: heading.textContent, href: buildPageHash(page.id, heading.id) });
    });

    manifest.headings.forEach(heading => {
        addHeadingCandidate({
            candidates,
            seen,
            term: heading.term,
            href: buildPageHash(heading.pageId, heading.anchor)
        });
    });

    return candidates.sort((left, right) => right.term.length - left.term.length);
}

/**
 * Add heading candidate variants.
 *
 * @param {object} params - Candidate parameters.
 * @returns {void}
 */
function addHeadingCandidate({ candidates, seen, term, href }) {
    referenceTermVariants(term).forEach(variant => {
        const normalizedTerm = normalizeReferenceTerm(variant);
        const key = `${normalizedTerm}:${href}`;

        if (!normalizedTerm || variant.length < 3 || seen.has(key)) return;

        seen.add(key);
        candidates.push({ term: variant, href, lowerTerm: variant.toLowerCase() });
    });
}

/**
 * Determine whether a text node should be skipped.
 *
 * @param {Text} textNode - Text node.
 * @returns {boolean} True when skipped.
 */
function shouldSkipTextAutolink(textNode) {
    const parent = textNode.parentElement;
    if (!parent || !textNode.nodeValue?.trim()) return true;

    return Boolean(parent.closest(
        'a, code, pre, h1, h2, h3, h4, h5, h6, script, style, textarea, button, select, option, input'
    ));
}

/**
 * Link one text node against heading candidates.
 *
 * @param {Text} textNode - Text node.
 * @param {Array<object>} candidates - Link candidates.
 * @returns {void}
 */
function linkHeadingTextNode(textNode, candidates) {
    const match = findHeadingTextMatch(textNode.nodeValue, candidates, textNode);
    if (!match || !textNode.parentNode) return;

    const fragment = document.createDocumentFragment();
    const before = textNode.nodeValue.slice(0, match.index);
    const matchedText = textNode.nodeValue.slice(match.index, match.index + match.candidate.term.length);
    const after = textNode.nodeValue.slice(match.index + match.candidate.term.length);
    const link = document.createElement('a');

    if (before) fragment.appendChild(document.createTextNode(before));
    link.href = match.candidate.href;
    link.className = 'text-heading-link';
    link.title = `Open ${match.candidate.term}`;
    link.textContent = matchedText;
    fragment.appendChild(link);
    if (after) fragment.appendChild(document.createTextNode(after));

    textNode.parentNode.replaceChild(fragment, textNode);
}

/**
 * Find the first valid heading text match.
 *
 * @param {string} text - Text content.
 * @param {Array<object>} candidates - Candidates.
 * @param {Text} textNode - Text node.
 * @returns {object|null} Match.
 */
function findHeadingTextMatch(text, candidates, textNode) {
    const lowerText = text.toLowerCase();
    const closestAnchor = textNode.parentElement?.closest('[id]');
    let best = null;

    candidates.forEach(candidate => {
        const index = lowerText.indexOf(candidate.lowerTerm);
        const isSelfAnchor = closestAnchor && candidate.href.endsWith(`anchor=${encodeURIComponent(closestAnchor.id)}`);

        if (index === -1 || isSelfAnchor) return;
        if (!hasTextMatchBoundary(text, index, candidate.term.length)) return;

        if (!best || index < best.index || candidate.term.length > best.candidate.term.length) {
            best = { index, candidate };
        }
    });

    return best;
}

/**
 * Check text match word boundaries.
 *
 * @param {string} text - Text content.
 * @param {number} index - Match index.
 * @param {number} length - Match length.
 * @returns {boolean} True when valid.
 */
function hasTextMatchBoundary(text, index, length) {
    const before = text[index - 1] || '';
    const after = text[index + length] || '';
    const first = text[index] || '';
    const last = text[index + length - 1] || '';

    if (/^[A-Za-z0-9_]$/.test(first) && /^[A-Za-z0-9_]$/.test(before)) return false;
    if (/^[A-Za-z0-9_]$/.test(last) && /^[A-Za-z0-9_]$/.test(after)) return false;

    return true;
}

/**
 * Convert Mermaid code blocks and initialize interactive diagrams.
 *
 * @returns {void}
 */
function enhanceMermaid() {
    document.querySelectorAll('pre code.language-mermaid').forEach(codeBlock => {
        const preBlock = codeBlock.parentElement;
        const mermaidDiv = document.createElement('div');
        mermaidDiv.className = 'mermaid';
        mermaidDiv.textContent = codeBlock.textContent;
        preBlock.replaceWith(mermaidDiv);
    });

    mermaid.initialize({ startOnLoad: false, theme: document.documentElement.dataset.theme === 'dark' ? 'dark' : 'default' });

    try {
        const mermaidContainers = document.querySelectorAll('.mermaid');
        if (mermaidContainers.length === 0) return;

        const initResult = mermaid.init(undefined, mermaidContainers);
        setupMermaidPanZoomWhenReady(initResult);
    } catch (error) {
        console.error('Mermaid render error:', error);
    }
}

/**
 * Attach pan/zoom after Mermaid has produced SVG diagrams.
 *
 * @param {Promise<void>|void} initResult - Mermaid initialization result.
 * @returns {void}
 */
function setupMermaidPanZoomWhenReady(initResult) {
    setupAllMermaidPanZoom();

    if (initResult && typeof initResult.then === 'function') {
        initResult.then(setupAllMermaidPanZoom).catch(error => {
            console.error('Mermaid promise error:', error);
        });
    }

    let attempts = 0;
    const interval = window.setInterval(() => {
        setupAllMermaidPanZoom();
        attempts += 1;

        if (attempts > 30) {
            window.clearInterval(interval);
        }
    }, 100);
}

/**
 * Attach pan/zoom to every rendered Mermaid SVG.
 *
 * @returns {void}
 */
function setupAllMermaidPanZoom() {
    getMermaidDiagramSvgs().forEach(setupMermaidPanZoom);
}

/**
 * Get Mermaid diagram SVG nodes, excluding control icons.
 *
 * @returns {SVGSVGElement[]} Rendered diagram SVGs.
 */
function getMermaidDiagramSvgs() {
    return Array.from(document.querySelectorAll('.mermaid > svg'))
        .filter(svg => !svg.closest('.mermaid-controls'));
}

/**
 * Attach svg-pan-zoom and floating controls to one Mermaid diagram.
 *
 * @param {SVGSVGElement} svg - Mermaid SVG.
 * @returns {void}
 */
function setupMermaidPanZoom(svg) {
    const container = svg.parentElement;

    if (!container || !container.classList.contains('mermaid') || PANNED_MERMAID_SVGS.has(svg)) {
        return;
    }

    if (typeof globalThis.svgPanZoom !== 'function') {
        return;
    }

    PANNED_MERMAID_SVGS.add(svg);
    prepareMermaidSvg({ svg, container });
    ensureMermaidControls(container);

    window.setTimeout(() => {
        try {
            const panZoom = globalThis.svgPanZoom(svg, {
                zoomEnabled: true,
                controlIconsEnabled: false,
                fit: true,
                center: true,
                minZoom: 0.5,
                maxZoom: 10
            });

            bindMermaidControls({ container, panZoom });
        } catch (error) {
            console.error('svgPanZoom init error:', error);
        }
    }, 100);
}

/**
 * Prepare one Mermaid SVG so svg-pan-zoom can own its viewport.
 *
 * @param {object} params - SVG parameters.
 * @param {SVGSVGElement} params.svg - Mermaid SVG.
 * @param {HTMLElement} params.container - Mermaid container.
 * @returns {void}
 */
function prepareMermaidSvg({ svg, container }) {
    let viewport = svg.querySelector('.svg-pan-zoom_viewport');

    if (!viewport) {
        viewport = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        viewport.setAttribute('class', 'svg-pan-zoom_viewport');

        Array.from(svg.childNodes).forEach(child => {
            const tagName = child.tagName ? child.tagName.toLowerCase() : '';
            if (tagName !== 'style' && tagName !== 'defs') viewport.appendChild(child);
        });

        svg.appendChild(viewport);
    }

    svg.classList.add('mermaid-diagram-svg');
    svg.style.userSelect = 'none';
    svg.style.webkitUserSelect = 'none';
    svg.style.cursor = 'grab';
    svg.style.width = '100%';
    svg.style.height = '100%';
    svg.removeAttribute('width');
    svg.removeAttribute('height');
    container.classList.add('mermaid-container');
}

/**
 * Ensure custom Mermaid diagram controls exist.
 *
 * @param {HTMLElement} container - Mermaid container.
 * @returns {void}
 */
function ensureMermaidControls(container) {
    if (container.querySelector('.mermaid-controls')) return;

    const controls = document.createElement('div');
    controls.className = 'mermaid-controls';
    controls.innerHTML = `
        <button class="mermaid-control-btn zoom-in" title="Acercar">
            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
        </button>
        <button class="mermaid-control-btn zoom-out" title="Alejar">
            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
        </button>
        <button class="mermaid-control-btn reset" title="Restaurar vista">
            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
                <polyline points="3 3 3 8 8 8"></polyline>
            </svg>
        </button>
    `;

    container.appendChild(controls);
}

/**
 * Bind custom control buttons to one svg-pan-zoom instance.
 *
 * @param {object} params - Control parameters.
 * @param {HTMLElement} params.container - Mermaid container.
 * @param {object} params.panZoom - svg-pan-zoom public instance.
 * @returns {void}
 */
function bindMermaidControls({ container, panZoom }) {
    const controls = container.querySelector('.mermaid-controls');
    if (!controls || controls.dataset.bound === 'true') return;

    controls.dataset.bound = 'true';
    controls.querySelector('.zoom-in')?.addEventListener('click', () => panZoom.zoomIn());
    controls.querySelector('.zoom-out')?.addEventListener('click', () => panZoom.zoomOut());
    controls.querySelector('.reset')?.addEventListener('click', () => {
        panZoom.reset();
        panZoom.fit();
        panZoom.center();
    });
}

/**
 * Build sidebar TOC for current page.
 *
 * @param {HTMLElement} root - Rendered markdown root.
 * @returns {void}
 */
function buildSidebarToc({ root, page }) {
    const tocOutput = document.getElementById('sidebar-toc');
    if (!tocOutput || !page) return;

    tocOutput.innerHTML = '';
    root.querySelectorAll('h2, h3').forEach(heading => {
        const link = document.createElement('a');
        link.href = buildPageHash(page.id, heading.id);
        link.className = `toc-link ${heading.tagName.toLowerCase()}`;
        link.textContent = heading.textContent;
        link.title = heading.textContent;
        tocOutput.appendChild(link);
    });
}

/**
 * Add copy buttons to code blocks.
 *
 * @param {HTMLElement} root - Rendered markdown root.
 * @returns {void}
 */
function addCopyButtons(root) {
    root.querySelectorAll('pre').forEach(preBlock => {
        const copyButton = document.createElement('button');
        copyButton.className = 'code-copy-btn';
        copyButton.textContent = 'Copy';
        copyButton.addEventListener('click', () => copyCodeBlock({ preBlock, copyButton }));
        preBlock.appendChild(copyButton);
    });
}

/**
 * Copy one code block.
 *
 * @param {object} params - Copy parameters.
 * @param {HTMLPreElement} params.preBlock - Code block.
 * @param {HTMLButtonElement} params.copyButton - Button.
 * @returns {void}
 */
function copyCodeBlock({ preBlock, copyButton }) {
    const code = preBlock.querySelector('code')?.textContent || '';
    navigator.clipboard.writeText(code).then(() => {
        copyButton.textContent = 'Copied';
        window.setTimeout(() => {
            copyButton.textContent = 'Copy';
        }, 2000);
    });
}

/**
 * Scroll to a heading anchor.
 *
 * @param {string|null} anchor - Target anchor.
 * @returns {void}
 */
function scrollToAnchor(anchor) {
    if (!anchor) return;

    window.setTimeout(() => {
        const target = document.getElementById(decodeURIComponent(anchor));
        target?.scrollIntoView({ block: 'start' });
    }, 0);
}

/**
 * Highlight search matches.
 *
 * @param {HTMLElement} root - Rendered markdown root.
 * @param {RegExp} regex - Search regex.
 * @returns {void}
 */
function highlightTextNodes(root, regex) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodesToReplace = [];
    let node;

    while ((node = walker.nextNode())) {
        if (node.parentElement?.closest('code, pre, .mermaid')) continue;
        if (node.nodeValue.match(regex)) nodesToReplace.push(node);
    }

    nodesToReplace.forEach(textNode => {
        const parent = textNode.parentNode;
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = textNode.nodeValue.replace(regex, match => `<mark class="search-highlight">${match}</mark>`);

        while (tempDiv.firstChild) {
            parent.insertBefore(tempDiv.firstChild, textNode);
        }
        parent.removeChild(textNode);
    });
}
