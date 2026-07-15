/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Filesystem and path helpers for the documentation utilities.
 */

import fs from 'fs';
import path from 'path';

/**
 * Convert a platform path into POSIX path separators for browser manifests.
 *
 * @param {string} value - Path to normalize.
 * @returns {string} POSIX path.
 */
export function toPosixPath(value) {
    return value.split(path.sep).join('/');
}

/**
 * Check whether one path is nested inside another path.
 *
 * @param {string} childPath - Candidate child path.
 * @param {string} parentPath - Candidate parent path.
 * @returns {boolean} True when the child is inside the parent.
 */
export function isPathInside(childPath, parentPath) {
    const relativePath = path.relative(parentPath, childPath);
    return relativePath !== '' && !relativePath.startsWith('..') && !path.isAbsolute(relativePath);
}

/**
 * Resolve the project name from a documentation directory path.
 *
 * @param {string} documentationPath - Absolute documentation directory path.
 * @returns {string} Project name.
 */
export function getProjectName(documentationPath) {
    const normalized = path.normalize(documentationPath);
    const segments = normalized.split(path.sep).filter(Boolean);

    if (segments.length === 0) {
        return 'default';
    }

    const lastSegment = segments[segments.length - 1];

    if (lastSegment.toLowerCase() === 'documentation' && segments.length > 1) {
        return segments[segments.length - 2];
    }

    return lastSegment;
}

/**
 * Resolve the required wiki output directory.
 *
 * @param {string} documentationPath - Absolute documentation directory path.
 * @returns {string} Absolute wiki output directory.
 */
export function resolveWikiDir(documentationPath) {
    return path.join(documentationPath, 'wiki');
}

/**
 * Ensure a directory exists.
 *
 * @param {string} directoryPath - Directory to create.
 * @returns {void}
 */
export function ensureDirectory(directoryPath) {
    fs.mkdirSync(directoryPath, { recursive: true });
}

/**
 * Remove trailing horizontal whitespace from text.
 *
 * @param {string} text - Text to normalize.
 * @returns {string} Text without trailing spaces or tabs.
 */
export function stripTrailingWhitespace(text) {
    return text.replace(/[ \t]+$/gm, '');
}

/**
 * Write a file only when content changed.
 *
 * @param {string} destPath - Destination path.
 * @param {string} content - Text content.
 * @param {BufferEncoding} [encoding='utf8'] - File encoding.
 * @returns {boolean} True when the file changed.
 */
export function writeFileIfChanged(destPath, content, encoding = 'utf8') {
    if (fs.existsSync(destPath)) {
        const currentContent = fs.readFileSync(destPath, encoding);
        if (currentContent === content) {
            return false;
        }
    }

    ensureDirectory(path.dirname(destPath));
    fs.writeFileSync(destPath, content, encoding);
    return true;
}

/**
 * Copy a file only when bytes changed.
 *
 * @param {string} srcPath - Source file.
 * @param {string} destPath - Destination file.
 * @returns {boolean} True when the file changed.
 */
export function copyFileIfChanged(srcPath, destPath) {
    if (fs.existsSync(destPath)) {
        const srcBuffer = fs.readFileSync(srcPath);
        const destBuffer = fs.readFileSync(destPath);

        if (srcBuffer.equals(destBuffer)) {
            return false;
        }
    }

    ensureDirectory(path.dirname(destPath));
    fs.copyFileSync(srcPath, destPath);
    return true;
}

/**
 * Escape text for safe HTML insertion.
 *
 * @param {string} value - Raw text.
 * @returns {string} Escaped text.
 */
export function escapeHtmlText(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/**
 * Resolve and validate an existing documentation directory.
 *
 * @param {string} documentationPath - Absolute documentation directory path.
 * @returns {string} Resolved documentation path.
 */
export function resolveExistingDocumentationPath(documentationPath) {
    const resolvedPath = path.resolve(documentationPath);

    if (!fs.existsSync(resolvedPath)) {
        throw new Error(`Documentation path does not exist: ${resolvedPath}`);
    }

    if (!fs.statSync(resolvedPath).isDirectory()) {
        throw new Error(`Documentation path is not a directory: ${resolvedPath}`);
    }

    return resolvedPath;
}
