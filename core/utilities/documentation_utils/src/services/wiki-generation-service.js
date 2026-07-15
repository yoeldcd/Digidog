/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Generates the live markdown wiki shell and manifest.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

import { copyWikiAssets } from './asset-service.js';
import { resolveAgentDirectory } from './agent-workspace-service.js';
import { extractAllPageHeadings } from './heading-index-service.js';
import { buildLogsMarkdown } from './log-extraction-service.js';
import { buildMarkdownPages } from './markdown-discovery-service.js';
import { runReferenceHeaderCheck } from './reference-check-service.js';
import { WikiManifestDTO } from '../models/wiki-models.js';
import {
    ensureDirectory,
    escapeHtmlText,
    getProjectName,
    resolveExistingDocumentationPath,
    resolveWikiDir,
    stripTrailingWhitespace,
    writeFileIfChanged
} from '../utils/path-utils.js';

const SERVICE_DIR = path.dirname(fileURLToPath(import.meta.url));
const SNIPPET_DIR = path.resolve(SERVICE_DIR, '../..');
const INDEX_TEMPLATE_PATH = path.join(SNIPPET_DIR, 'wiki.template.html');

/**
 * Run the public generate command.
 *
 * @param {import('../models/wiki-models.js').CliCommandDTO} command - Parsed CLI command.
 * @returns {number} Exit code.
 */
export function generateDocumentationWiki(command) {
    const documentationPath = resolveExistingDocumentationPath(command.documentationPath);
    const wikiDir = resolveWikiDir(documentationPath);
    const projectName = getProjectName(documentationPath);
    const pages = buildMarkdownPages({ documentationPath, wikiDir });

    if (pages.length === 0) {
        console.warn(`Warning: No Markdown files found in: ${documentationPath}`);
        return 0;
    }

    console.log('========================================');
    console.log('Documentation Utils Live Markdown Wiki');
    console.log(`Source Path:      ${documentationPath}`);
    console.log(`Output Directory: ${wikiDir}`);
    console.log(`Log Domain:       ${command.logDomain || `heuristic (${projectName})`}`);
    console.log('========================================\n');

    runReferenceHeaderCheck(pages, { failOnMissing: false, maxItems: 25 });

    ensureDirectory(wikiDir);
    copyWikiAssets(wikiDir).forEach(assetPath => console.log(`Copied library asset: ${assetPath}`));

    const agentDir = resolveAgentDirectory(SNIPPET_DIR);
    const logsMarkdown = buildLogsMarkdown({
        agentDir,
        projectName,
        logDomain: command.logDomain || null
    });
    const manifest = new WikiManifestDTO({
        projectName,
        pages,
        headings: extractAllPageHeadings(pages),
        virtualPages: [
            {
                id: 'logs',
                title: 'Agent Tech Logs',
                icon: '🤖',
                href: 'logs.html'
            }
        ]
    });

    writeGeneratedFiles({ wikiDir, manifest, logsMarkdown });
    cleanupStaleHtmlFiles(wikiDir).forEach(relativePath => console.log(`Removed stale: ${relativePath}`));

    console.log('\nSuccess! Live markdown wiki generated successfully.');
    return 0;
}

/**
 * Write generated manifest and shell files.
 *
 * @param {object} params - Write parameters.
 * @param {string} params.wikiDir - Absolute wiki directory.
 * @param {WikiManifestDTO} params.manifest - Manifest DTO.
 * @param {string} params.logsMarkdown - Generated logs markdown.
 * @returns {void}
 */
function writeGeneratedFiles({ wikiDir, manifest, logsMarkdown }) {
    const dataDir = path.join(wikiDir, 'data');
    ensureDirectory(dataDir);

    const manifestContent = `${stripTrailingWhitespace(JSON.stringify(manifest, null, 2))}\n`;
    if (writeFileIfChanged(path.join(dataDir, 'index.json'), manifestContent, 'utf8')) {
        console.log('Updated: data/index.json');
    }

    const indexContent = `${buildIndexHtml({ title: 'Wiki Docs' })}\n`;
    if (writeFileIfChanged(path.join(wikiDir, 'index.html'), indexContent, 'utf8')) {
        console.log('Updated: index.html');
    }

    const logsContent = `${buildLogsHtml({ title: 'Agent Tech Logs', logsMarkdown })}\n`;
    if (writeFileIfChanged(path.join(wikiDir, 'logs.html'), logsContent, 'utf8')) {
        console.log('Updated: logs.html');
    }
}

/**
 * Build the generated live markdown reader shell.
 *
 * @param {object} params - Template parameters.
 * @param {string} params.title - HTML title.
 * @returns {string} HTML content.
 */
function buildIndexHtml({ title }) {
    const template = fs.readFileSync(INDEX_TEMPLATE_PATH, 'utf8');

    return stripTrailingWhitespace(template
        .replaceAll('{{TITLE}}', title)
        .replaceAll('{{PAGE_KIND}}', 'reader')
        .replaceAll('{{MARKDOWN_SOURCE}}', '')
        .replaceAll('{{MARKED_PATH}}', 'scripts/marked.min.js')
        .replaceAll('{{MERMAID_PATH}}', 'scripts/mermaid.min.js')
        .replaceAll('{{SVG_PAN_ZOOM_PATH}}', 'scripts/svg-pan-zoom.min.js')
        .replaceAll('{{PRISM_CSS_PATH}}', 'styles/prism-tomorrow.min.css')
        .replaceAll('{{PRISM_JS_PATH}}', 'scripts/prism.min.js')
        .replaceAll('{{PRISM_JS_JS_PATH}}', 'scripts/prism-javascript.min.js')
        .replaceAll('{{PRISM_CSS_JS_PATH}}', 'scripts/prism-css.min.js')
        .replaceAll('{{PRISM_JSON_JS_PATH}}', 'scripts/prism-json.min.js')
        .replaceAll('{{PRISM_PYTHON_JS_PATH}}', 'scripts/prism-python.min.js')
        .replaceAll('{{WIKI_CORE_CSS_PATH}}', 'styles/wiki-core.css')
        .replaceAll('{{WIKI_CORE_JS_PATH}}', 'scripts/wiki-core.js'));
}

/**
 * Build the generated logs page.
 *
 * @param {object} params - Template parameters.
 * @param {string} params.title - HTML title.
 * @param {string} params.logsMarkdown - Generated logs markdown.
 * @returns {string} HTML content.
 */
function buildLogsHtml({ title, logsMarkdown }) {
    const template = fs.readFileSync(INDEX_TEMPLATE_PATH, 'utf8');

    return stripTrailingWhitespace(template
        .replaceAll('{{TITLE}}', title)
        .replaceAll('{{PAGE_KIND}}', 'logs')
        .replaceAll('{{MARKDOWN_SOURCE}}', escapeHtmlText(logsMarkdown))
        .replaceAll('{{MARKED_PATH}}', 'scripts/marked.min.js')
        .replaceAll('{{MERMAID_PATH}}', 'scripts/mermaid.min.js')
        .replaceAll('{{SVG_PAN_ZOOM_PATH}}', 'scripts/svg-pan-zoom.min.js')
        .replaceAll('{{PRISM_CSS_PATH}}', 'styles/prism-tomorrow.min.css')
        .replaceAll('{{PRISM_JS_PATH}}', 'scripts/prism.min.js')
        .replaceAll('{{PRISM_JS_JS_PATH}}', 'scripts/prism-javascript.min.js')
        .replaceAll('{{PRISM_CSS_JS_PATH}}', 'scripts/prism-css.min.js')
        .replaceAll('{{PRISM_JSON_JS_PATH}}', 'scripts/prism-json.min.js')
        .replaceAll('{{PRISM_PYTHON_JS_PATH}}', 'scripts/prism-python.min.js')
        .replaceAll('{{WIKI_CORE_CSS_PATH}}', 'styles/wiki-core.css')
        .replaceAll('{{WIKI_CORE_JS_PATH}}', 'scripts/wiki-core.js'));
}

/**
 * Remove old generated per-markdown HTML pages.
 *
 * @param {string} wikiDir - Generated wiki directory.
 * @returns {string[]} Removed relative paths.
 */
function cleanupStaleHtmlFiles(wikiDir) {
    const expectedHtml = new Set(['index.html', 'logs.html']);
    const removed = [];

    collectGeneratedHtmlFiles(wikiDir, wikiDir).forEach(relativePath => {
        if (expectedHtml.has(relativePath)) return;

        fs.unlinkSync(path.join(wikiDir, relativePath));
        removed.push(relativePath);
    });

    return removed;
}

/**
 * Collect generated HTML files under a wiki directory.
 *
 * @param {string} currentDir - Current scan directory.
 * @param {string} outputRoot - Wiki root.
 * @returns {string[]} Relative POSIX HTML paths.
 */
function collectGeneratedHtmlFiles(currentDir, outputRoot) {
    if (!fs.existsSync(currentDir)) return [];

    const files = [];
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });

    entries.forEach(entry => {
        const absolutePath = path.join(currentDir, entry.name);

        if (entry.isDirectory()) {
            files.push(...collectGeneratedHtmlFiles(absolutePath, outputRoot));
            return;
        }

        if (entry.isFile() && path.extname(entry.name).toLowerCase() === '.html') {
            files.push(path.relative(outputRoot, absolutePath).split(path.sep).join('/'));
        }
    });

    return files;
}
