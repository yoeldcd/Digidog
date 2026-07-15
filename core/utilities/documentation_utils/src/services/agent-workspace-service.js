/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Locates the local $agent workspace for optional log extraction.
 */

import fs from 'fs';
import path from 'path';

/**
 * Resolve the nearest agent workspace directory.
 *
 * @param {string} startDir - Directory to search from.
 * @returns {string|null} Agent directory or null.
 */
export function resolveAgentDirectory(startDir) {
    const candidates = [
        path.resolve(startDir, '..'),
        path.resolve(startDir, '../../$agent')
    ];

    for (const candidate of candidates) {
        if (isAgentDirectory(candidate)) return candidate;
    }

    let current = startDir;
    while (current !== path.dirname(current)) {
        const potentialAgent = path.join(current, '$agent');
        if (isAgentDirectory(potentialAgent)) return potentialAgent;
        current = path.dirname(current);
    }

    return null;
}

/**
 * Check whether a directory looks like the workspace agent directory.
 *
 * @param {string} candidate - Candidate directory.
 * @returns {boolean} True when a supported workspace data folder exists.
 */
function isAgentDirectory(candidate) {
    return ['database', 'logs', 'data'].some((directory) => fs.existsSync(path.join(candidate, directory)));
}
