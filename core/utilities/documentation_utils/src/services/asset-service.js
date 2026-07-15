/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Copies static wiki runtime assets.
 */

import path from 'path';
import { fileURLToPath } from 'url';

import { ASSETS_TO_COPY } from '../config/wiki-config.js';
import { copyFileIfChanged } from '../utils/path-utils.js';

const SERVICE_DIR = path.dirname(fileURLToPath(import.meta.url));
const SNIPPET_DIR = path.resolve(SERVICE_DIR, '../..');

/**
 * Copy all static assets required by the wiki reader.
 *
 * @param {string} wikiDir - Absolute wiki output directory.
 * @returns {string[]} Relative asset paths copied or updated.
 */
export function copyWikiAssets(wikiDir) {
    const copied = [];

    ASSETS_TO_COPY.forEach(asset => {
        const sourcePath = path.join(SNIPPET_DIR, 'lib', asset.source);
        const targetPath = path.join(wikiDir, asset.target);

        if (copyFileIfChanged(sourcePath, targetPath)) {
            copied.push(asset.target);
        }
    });

    return copied;
}
