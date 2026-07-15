/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Discovers markdown documentation sources and converts them into page DTOs.
 */

import fs from 'fs';
import path from 'path';

import { DOC_PRESETS, IGNORED_DIRECTORIES, MARKDOWN_EXTENSIONS } from '../config/wiki-config.js';
import { WikiPageDTO } from '../models/wiki-models.js';
import { isPathInside, toPosixPath } from '../utils/path-utils.js';

/**
 * Collect markdown files recursively under a documentation directory.
 *
 * @param {string} currentDir - Directory currently being scanned.
 * @param {string} outputRoot - Generated wiki output root.
 * @returns {string[]} Absolute markdown file paths.
 */
export function collectMarkdownFiles(currentDir, outputRoot) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });
    const files = [];

    entries.forEach(entry => {
        const absolutePath = path.join(currentDir, entry.name);

        if (entry.isDirectory()) {
            if (IGNORED_DIRECTORIES.has(entry.name)) return;
            if (absolutePath === outputRoot || isPathInside(absolutePath, outputRoot)) return;

            files.push(...collectMarkdownFiles(absolutePath, outputRoot));
            return;
        }

        if (entry.isFile() && MARKDOWN_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) {
            files.push(absolutePath);
        }
    });

    return files;
}

/**
 * Build page DTOs from discovered markdown files.
 *
 * @param {object} params - Build parameters.
 * @param {string} params.documentationPath - Absolute documentation path.
 * @param {string} params.wikiDir - Absolute wiki output path.
 * @returns {WikiPageDTO[]} Page DTOs.
 */
export function buildMarkdownPages({ documentationPath, wikiDir }) {
    const markdownFiles = collectMarkdownFiles(documentationPath, wikiDir).sort((left, right) => {
        return toPosixPath(path.relative(documentationPath, left))
            .localeCompare(toPosixPath(path.relative(documentationPath, right)));
    });

    return markdownFiles.map(filePath => buildMarkdownPage({ documentationPath, filePath }));
}

/**
 * Build one markdown page DTO.
 *
 * @param {object} params - Page build parameters.
 * @param {string} params.documentationPath - Absolute documentation path.
 * @param {string} params.filePath - Absolute markdown file path.
 * @returns {WikiPageDTO} Page DTO.
 */
function buildMarkdownPage({ documentationPath, filePath }) {
    const source = toPosixPath(path.relative(documentationPath, filePath));
    const extension = path.extname(filePath);
    const basename = path.basename(filePath, extension);
    const id = source.replace(/\.(md|markdown)$/i, '').toLowerCase();
    const markdownText = fs.readFileSync(filePath, 'utf8');
    const presetKey = resolvePresetKey({ id, basename });
    const preset = presetKey ? DOC_PRESETS[presetKey] : null;

    return new WikiPageDTO({
        id,
        source,
        absolutePath: filePath,
        title: preset ? preset.title : getFirstHeading(markdownText) || titleFromBasename(basename),
        icon: preset ? preset.icon : '📄',
        markdownText
    });
}

/**
 * Resolve the preset key for a page.
 *
 * @param {object} params - Preset lookup parameters.
 * @param {string} params.id - Page id.
 * @param {string} params.basename - Source basename.
 * @returns {string|null} Preset key.
 */
function resolvePresetKey({ id, basename }) {
    if (DOC_PRESETS[id]) return id;

    const basenameKey = basename.toLowerCase();
    if (DOC_PRESETS[basenameKey]) return basenameKey;

    return null;
}

/**
 * Extract the first H1 heading from markdown content.
 *
 * @param {string} markdownText - Markdown source.
 * @returns {string|null} H1 text when present.
 */
function getFirstHeading(markdownText) {
    const match = markdownText.match(/^#\s+(.+)$/m);
    return match ? match[1].trim() : null;
}

/**
 * Build a readable title from a markdown filename.
 *
 * @param {string} basename - Filename without extension.
 * @returns {string} Human-readable title.
 */
function titleFromBasename(basename) {
    return basename
        .split(/[-_]/)
        .filter(Boolean)
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}
