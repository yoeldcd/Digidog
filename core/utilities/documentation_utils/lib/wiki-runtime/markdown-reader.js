/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Live markdown reader application.
 */

import {
    bindSearch,
    configureMarkdownRenderer,
    enhanceRenderedMarkdown,
    renderMarkdown
} from './content-enhancer.js';
import { buildPageHash, escapeHtml, loadManifest, parseHashRoute, sourceToHref } from './wiki-utils.js';

/**
 * Start the live markdown reader.
 *
 * @returns {Promise<void>} Resolves after initial render.
 */
export async function startMarkdownReader() {
    configureMarkdownRenderer();

    const manifest = await loadManifest();
    const output = document.getElementById('markdown-output');
    const searchController = bindSearch(output);
    const readerState = {
        manifest,
        output,
        searchController,
        markdownCache: new Map(),
        currentPageId: null,
        currentRouteKey: null,
        renderedPageReady: false,
        renderId: 0
    };

    renderSidebar({ manifest, activePageId: null });
    bindInternalNavigation(readerState);
    await renderCurrentPage(readerState);

    window.addEventListener('hashchange', () => {
        renderCurrentPage(readerState);
    });

    window.addEventListener('popstate', () => {
        renderCurrentPage(readerState);
    });
}

/**
 * Render the current hash-selected page.
 *
 * @param {object} params - Render parameters.
 * @param {object} params - Reader state.
 * @returns {Promise<void>} Resolves after render.
 */
async function renderCurrentPage(params) {
    const { manifest, output, searchController, markdownCache } = params;
    const route = parseHashRoute();
    const page = resolveActivePage({ manifest, pageId: route.pageId });
    const routeKey = `${page.id}:${route.anchor || ''}`;

    if (params.currentPageId === page.id && params.renderedPageReady) {
        params.currentRouteKey = routeKey;
        scrollToRenderedAnchor(route.anchor);
        return;
    }

    renderSidebar({ manifest, activePageId: page.id });

    if (!markdownCache.has(page.source)) {
        output.innerHTML = `<p class="wiki-loading">Loading ${escapeHtml(page.title)}...</p>`;
    }

    const renderId = params.renderId + 1;
    params.renderId = renderId;

    try {
        const markdown = await fetchMarkdown({ page, markdownCache });
        if (renderId !== params.renderId) return;

        output.innerHTML = renderMarkdown(markdown);
        enhanceRenderedMarkdown({ root: output, manifest, page, anchor: route.anchor });
        searchController.refresh();
        params.currentPageId = page.id;
        params.currentRouteKey = routeKey;
        params.renderedPageReady = true;
        document.title = `Wiki - ${page.title}`;
    } catch (error) {
        if (renderId !== params.renderId) return;
        output.innerHTML = `<p class="wiki-error">${escapeHtml(error.message)}</p>`;
        params.renderedPageReady = false;
    }
}

/**
 * Bind wiki-route links to in-place rendering.
 *
 * @param {object} readerState - Reader state.
 * @returns {void}
 */
function bindInternalNavigation(readerState) {
    document.addEventListener('click', event => {
        const link = event.target.closest('a[href]');
        const nextHash = resolveInternalPageHash({ event, link });

        if (!nextHash) return;

        event.preventDefault();

        if (window.location.hash !== nextHash) {
            window.history.pushState(null, '', nextHash);
        }

        renderCurrentPage(readerState);
    });
}

/**
 * Resolve a clicked link to an internal reader hash when possible.
 *
 * @param {object} params - Navigation parameters.
 * @param {MouseEvent} params.event - Click event.
 * @param {HTMLAnchorElement|null} params.link - Clicked link.
 * @returns {string|null} Internal page hash.
 */
function resolveInternalPageHash({ event, link }) {
    if (!link || event.defaultPrevented || event.button !== 0) return null;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return null;
    if (link.target && link.target !== '_self') return null;

    const href = link.getAttribute('href');
    if (!href) return null;
    if (href.startsWith('#page=')) return href;
    if (href.startsWith('index.html#page=')) return href.slice('index.html'.length);

    try {
        const targetUrl = new URL(href, window.location.href);
        const currentPath = normalizeIndexPath(window.location.pathname);
        const targetPath = normalizeIndexPath(targetUrl.pathname);

        if (targetUrl.origin === window.location.origin && currentPath === targetPath && targetUrl.hash.startsWith('#page=')) {
            return targetUrl.hash;
        }
    } catch {
        return null;
    }

    return null;
}

/**
 * Normalize index document paths for same-page routing checks.
 *
 * @param {string} pathname - URL pathname.
 * @returns {string} Normalized path.
 */
function normalizeIndexPath(pathname) {
    return pathname.replace(/\/index\.html$/i, '/');
}

/**
 * Resolve the active page from route or default.
 *
 * @param {object} params - Resolve parameters.
 * @param {object} params.manifest - Wiki manifest.
 * @param {string|null} params.pageId - Requested page id.
 * @returns {object} Page manifest item.
 */
function resolveActivePage({ manifest, pageId }) {
    return manifest.pages.find(page => page.id === pageId) || manifest.pages[0];
}

/**
 * Fetch source markdown for a page.
 *
 * @param {object} params - Fetch parameters.
 * @param {object} params.page - Page manifest item.
 * @param {Map<string, string>} params.markdownCache - Per-session markdown cache.
 * @returns {Promise<string>} Markdown source.
 */
async function fetchMarkdown({ page, markdownCache }) {
    if (markdownCache.has(page.source)) {
        return markdownCache.get(page.source);
    }

    const response = await fetch(sourceToHref(page.source), { cache: 'no-store' });

    if (!response.ok) {
        throw new Error(`Unable to load ${page.source}: ${response.status}`);
    }

    const markdown = await response.text();
    markdownCache.set(page.source, markdown);
    return markdown;
}

/**
 * Scroll within the current rendered markdown page.
 *
 * @param {string|null} anchor - Target anchor.
 * @returns {void}
 */
function scrollToRenderedAnchor(anchor) {
    window.setTimeout(() => {
        if (!anchor) {
            window.scrollTo({ top: 0, left: 0 });
            return;
        }

        const target = document.getElementById(decodeURIComponent(anchor));
        target?.scrollIntoView({ block: 'start' });
    }, 0);
}

/**
 * Render sidebar navigation.
 *
 * @param {object} params - Sidebar parameters.
 * @param {object} params.manifest - Wiki manifest.
 * @param {string|null} params.activePageId - Active page id.
 * @returns {void}
 */
function renderSidebar({ manifest, activePageId }) {
    const sidebar = document.getElementById('sidebar-menu');
    const pageItems = manifest.pages.map(page => buildPageNavItem({ page, activePageId })).join('');
    const virtualItems = (manifest.virtualPages || []).map(page => buildVirtualNavItem(page)).join('');

    sidebar.innerHTML = `${pageItems}${virtualItems}`;
}

/**
 * Build a page navigation item.
 *
 * @param {object} params - Item parameters.
 * @param {object} params.page - Page manifest item.
 * @param {string|null} params.activePageId - Active page id.
 * @returns {string} HTML.
 */
function buildPageNavItem({ page, activePageId }) {
    const isActive = page.id === activePageId;

    return `
        <div class="nav-item-wrapper">
            <a href="${buildPageHash(page.id)}" class="sidebar-item ${isActive ? 'active' : ''}">
                <span class="sidebar-icon">${escapeHtml(page.icon)}</span>
                <span class="sidebar-title">${escapeHtml(page.title)}</span>
            </a>
            ${isActive ? '<div class="sidebar-toc-container" id="sidebar-toc"></div>' : ''}
        </div>
    `;
}

/**
 * Build a virtual-page navigation item.
 *
 * @param {object} page - Virtual page manifest item.
 * @returns {string} HTML.
 */
function buildVirtualNavItem(page) {
    return `
        <div class="nav-item-wrapper">
            <a href="${page.href}" class="sidebar-item">
                <span class="sidebar-icon">${escapeHtml(page.icon)}</span>
                <span class="sidebar-title">${escapeHtml(page.title)}</span>
            </a>
        </div>
    `;
}
