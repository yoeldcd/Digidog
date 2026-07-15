/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Generated logs page renderer.
 */

import {
    bindSearch,
    configureMarkdownRenderer,
    enhanceRenderedMarkdown,
    renderMarkdown
} from './content-enhancer.js';
import { buildPageHash, escapeHtml, loadManifest } from './wiki-utils.js';

/**
 * Start the generated logs page.
 *
 * @returns {Promise<void>} Resolves after render.
 */
export async function startLogsPage() {
    configureMarkdownRenderer();

    const manifest = await loadManifest();
    const output = document.getElementById('markdown-output');
    const logsMarkdown = document.getElementById('markdown-source')?.textContent || '';
    const entries = parseLogs(logsMarkdown);

    renderSidebar(manifest);
    renderLogExplorer({ output, entries, manifest });
    bindSearch(output).refresh();
}

/**
 * Render logs sidebar navigation.
 *
 * @param {object} manifest - Wiki manifest.
 * @returns {void}
 */
function renderSidebar(manifest) {
    const sidebar = document.getElementById('sidebar-menu');
    const pageItems = manifest.pages.map(page => `
        <div class="nav-item-wrapper">
            <a href="index.html${buildPageHash(page.id)}" class="sidebar-item">
                <span class="sidebar-icon">${escapeHtml(page.icon)}</span>
                <span class="sidebar-title">${escapeHtml(page.title)}</span>
            </a>
        </div>
    `).join('');

    sidebar.innerHTML = `
        ${pageItems}
        <div class="nav-item-wrapper">
            <a href="logs.html" class="sidebar-item active">
                <span class="sidebar-icon">🤖</span>
                <span class="sidebar-title">Agent Tech Logs</span>
            </a>
        </div>
    `;
}

/**
 * Parse generated log markdown into records.
 *
 * @param {string} rawMarkdown - Logs markdown.
 * @returns {Array<object>} Log entries.
 */
function parseLogs(rawMarkdown) {
    const entries = [];
    const dateSections = rawMarkdown.split(/^##\s+/m);

    for (let index = 1; index < dateSections.length; index += 1) {
        entries.push(...parseDateSection(dateSections[index]));
    }

    return entries;
}

/**
 * Parse one date section.
 *
 * @param {string} section - Raw date section.
 * @returns {Array<object>} Log entries.
 */
function parseDateSection(section) {
    const trimmedSection = section.trim();
    if (!trimmedSection) return [];

    const lines = trimmedSection.split(/\r?\n/);
    const dateTimeStr = lines[0].trim();
    const dateMatch = dateTimeStr.match(/^(\d{2}-\d{2}-\d{4})\s+(.*)$/);
    const date = dateMatch ? dateMatch[1] : dateTimeStr;
    const time = dateMatch ? dateMatch[2] : '';
    const rawEntries = lines.slice(1).join('\n').split(/^###\s+/m);

    return rawEntries.slice(1).map(rawEntry => parseLogEntry({ rawEntry, dateTimeStr, date, time })).filter(Boolean);
}

/**
 * Parse one log entry.
 *
 * @param {object} params - Parse parameters.
 * @param {string} params.rawEntry - Raw entry markdown.
 * @param {string} params.dateTimeStr - Date-time label.
 * @param {string} params.date - Date label.
 * @param {string} params.time - Time label.
 * @returns {object|null} Parsed entry.
 */
function parseLogEntry({ rawEntry, dateTimeStr, date, time }) {
    const entryLines = rawEntry.trim().split(/\r?\n/);
    const headerLine = entryLines[0]?.trim();
    if (!headerLine) return null;

    const headerMatch = headerLine.match(/^\(([^)]+)\)\s*\[([^\]]+)\]/);
    const bodyText = entryLines.slice(1).join('\n');

    return {
        dateTime: dateTimeStr,
        date,
        time,
        domain: headerMatch ? headerMatch[1] : 'general',
        title: headerMatch ? headerMatch[2] : headerLine,
        type: getField({ bodyText, fieldName: 'Type' }).toLowerCase() || 'general',
        why: getField({ bodyText, fieldName: 'Why' }),
        description: getField({ bodyText, fieldName: 'Description' }),
        impact: getField({ bodyText, fieldName: 'Impact' })
    };
}

/**
 * Extract one field from a log entry body.
 *
 * @param {object} params - Field parameters.
 * @param {string} params.bodyText - Entry body.
 * @param {string} params.fieldName - Field label.
 * @returns {string} Field content.
 */
function getField({ bodyText, fieldName }) {
    const regex = new RegExp(`\\*\\*${fieldName}:?\\*\\*([\\s\\S]*?)(?=\\*\\*|$)`, 'i');
    const match = bodyText.match(regex);
    return match ? match[1].trim() : '';
}

/**
 * Render the log explorer UI.
 *
 * @param {object} params - Render parameters.
 * @param {HTMLElement} params.output - Output element.
 * @param {Array<object>} params.entries - Log entries.
 * @param {object} params.manifest - Wiki manifest.
 * @returns {void}
 */
function renderLogExplorer({ output, entries, manifest }) {
    const domains = Array.from(new Set(entries.map(entry => entry.domain))).sort();
    const types = Array.from(new Set(entries.map(entry => entry.type))).sort();

    output.innerHTML = buildToolbar({ domains, types });
    bindLogToolbar({ output, entries, manifest });
}

/**
 * Build toolbar markup.
 *
 * @param {object} params - Toolbar values.
 * @param {string[]} params.domains - Domains.
 * @param {string[]} params.types - Types.
 * @returns {string} HTML.
 */
function buildToolbar({ domains, types }) {
    return `
        <div class="logs-container">
            <h1 style="font-family: var(--font-display); font-weight: 800; margin-bottom: 8px;">Agent Tech Logs</h1>
            <p style="color: var(--text-muted); margin-bottom: 16px; font-size: 0.95rem;">Explore, filter, and analyze the agent change history.</p>
            <div class="logs-toolbar">
                <div class="toolbar-group logs-search-toolbar">
                    <span class="toolbar-label">Search</span>
                    <input type="text" id="logs-search" class="logs-input" placeholder="Search logs...">
                </div>
                <div class="toolbar-group">
                    <span class="toolbar-label">Type</span>
                    <select id="logs-type" class="logs-select">
                        <option value="all">All types</option>
                        ${types.map(type => `<option value="${escapeHtml(type)}">${escapeHtml(type.toUpperCase())}</option>`).join('')}
                    </select>
                </div>
                <div class="toolbar-group">
                    <span class="toolbar-label">Domain</span>
                    <select id="logs-domain" class="logs-select">
                        <option value="all">All domains</option>
                        ${domains.map(domain => `<option value="${escapeHtml(domain)}">${escapeHtml(domain)}</option>`).join('')}
                    </select>
                </div>
                <div class="toolbar-group">
                    <span class="toolbar-label">Sort</span>
                    <select id="logs-sort" class="logs-select">
                        <option value="desc">Newest first</option>
                        <option value="asc">Oldest first</option>
                    </select>
                </div>
            </div>
            <div id="logs-list-container" class="logs-list"></div>
        </div>
    `;
}

/**
 * Bind toolbar events and render log cards.
 *
 * @param {object} params - Bind parameters.
 * @param {HTMLElement} params.output - Output element.
 * @param {Array<object>} params.entries - Log entries.
 * @param {object} params.manifest - Wiki manifest.
 * @returns {void}
 */
function bindLogToolbar({ output, entries, manifest }) {
    const searchInput = document.getElementById('logs-search');
    const typeSelect = document.getElementById('logs-type');
    const domainSelect = document.getElementById('logs-domain');
    const sortSelect = document.getElementById('logs-sort');
    const listContainer = document.getElementById('logs-list-container');

    const updateList = () => {
        const filtered = filterEntries({
            entries,
            query: searchInput.value.toLowerCase().trim(),
            selectedType: typeSelect.value,
            selectedDomain: domainSelect.value,
            sortOrder: sortSelect.value
        });

        if (filtered.length === 0) {
            listContainer.innerHTML = '<div class="logs-empty">No log entries match the active filters.</div>';
            return;
        }

        listContainer.innerHTML = filtered.map(renderLogCard).join('');
        enhanceRenderedMarkdown({ root: output, manifest, page: null, anchor: null });
    };

    searchInput.addEventListener('input', updateList);
    typeSelect.addEventListener('change', updateList);
    domainSelect.addEventListener('change', updateList);
    sortSelect.addEventListener('change', updateList);
    updateList();
}

/**
 * Filter and sort log entries.
 *
 * @param {object} params - Filter parameters.
 * @returns {Array<object>} Filtered entries.
 */
function filterEntries({ entries, query, selectedType, selectedDomain, sortOrder }) {
    return entries.filter(entry => {
        const matchesQuery = !query || [entry.title, entry.why, entry.description, entry.impact, entry.domain]
            .some(value => String(value || '').toLowerCase().includes(query));
        const matchesType = selectedType === 'all' || entry.type === selectedType;
        const matchesDomain = selectedDomain === 'all' || entry.domain === selectedDomain;
        return matchesQuery && matchesType && matchesDomain;
    }).sort((left, right) => {
        return sortOrder === 'desc'
            ? parseEntryDateTime(right).getTime() - parseEntryDateTime(left).getTime()
            : parseEntryDateTime(left).getTime() - parseEntryDateTime(right).getTime();
    });
}

/**
 * Parse a log entry date.
 *
 * @param {object} entry - Log entry.
 * @returns {Date} Parsed date.
 */
function parseEntryDateTime(entry) {
    const parts = entry.date.split('-');
    return parts.length === 3 ? new Date(parts[2], parts[1] - 1, parts[0]) : new Date(0);
}

/**
 * Render one log card.
 *
 * @param {object} entry - Log entry.
 * @returns {string} HTML.
 */
function renderLogCard(entry) {
    return `
        <div class="log-card">
            <div class="log-card-header">
                <div class="log-meta-left">
                    <span class="badge badge-type ${escapeHtml(entry.type)}">${escapeHtml(entry.type)}</span>
                    <span class="badge badge-domain">${escapeHtml(entry.domain)}</span>
                </div>
                <div class="log-meta-right">${escapeHtml(entry.dateTime)}</div>
                <h2 class="log-title">${escapeHtml(entry.title)}</h2>
            </div>
            <div class="log-body">
                ${renderLogSection({ label: 'Why', value: entry.why })}
                ${renderLogSection({ label: 'Description', value: entry.description })}
                ${renderLogSection({ label: 'Impact', value: entry.impact })}
            </div>
        </div>
    `;
}

/**
 * Render one optional log section.
 *
 * @param {object} params - Section parameters.
 * @param {string} params.label - Section label.
 * @param {string} params.value - Section markdown.
 * @returns {string} HTML.
 */
function renderLogSection({ label, value }) {
    if (!value) return '';

    return `
        <div class="log-section">
            <span class="log-section-label">${escapeHtml(label)}:</span>
            <div class="log-section-content">${renderMarkdown(value.replace(/\\n/g, '\n').trim())}</div>
        </div>
    `;
}
