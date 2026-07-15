/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Strict static HTTP server for already generated documentation wikis.
 */

import fs from 'fs';
import http from 'http';
import path from 'path';

import { isPathInside, resolveExistingDocumentationPath, resolveWikiDir } from '../utils/path-utils.js';

const CONTENT_TYPES = new Map([
    ['.html', 'text/html; charset=utf-8'],
    ['.json', 'application/json; charset=utf-8'],
    ['.js', 'text/javascript; charset=utf-8'],
    ['.css', 'text/css; charset=utf-8'],
    ['.md', 'text/markdown; charset=utf-8'],
    ['.markdown', 'text/markdown; charset=utf-8'],
    ['.svg', 'image/svg+xml; charset=utf-8'],
    ['.png', 'image/png'],
    ['.jpg', 'image/jpeg'],
    ['.jpeg', 'image/jpeg'],
    ['.gif', 'image/gif'],
    ['.webp', 'image/webp']
]);

/**
 * Start a strict static server for a generated documentation wiki.
 *
 * @param {import('../models/wiki-models.js').CliCommandDTO} command - Parsed CLI command.
 * @returns {Promise<{server: http.Server, url: string, host: string, port: number}>} Server info.
 */
export async function serveDocumentationWiki(command) {
    const documentationPath = resolveExistingDocumentationPath(command.documentationPath);
    validateGeneratedWiki(documentationPath);

    const server = http.createServer((request, response) => {
        handleStaticRequest({ request, response, documentationPath });
    });

    await listen(server, command.port, command.host);
    const address = server.address();
    const port = typeof address === 'object' && address ? address.port : command.port;

    return {
        server,
        host: command.host,
        port,
        url: `http://${command.host}:${port}/wiki/index.html`
    };
}

/**
 * Validate required generated wiki files without writing anything.
 *
 * @param {string} documentationPath - Absolute documentation path.
 * @returns {void}
 */
function validateGeneratedWiki(documentationPath) {
    const wikiDir = resolveWikiDir(documentationPath);
    const requiredFiles = [
        path.join(wikiDir, 'index.html'),
        path.join(wikiDir, 'logs.html'),
        path.join(wikiDir, 'data', 'index.json')
    ];

    requiredFiles.forEach(requiredFile => {
        if (!fs.existsSync(requiredFile) || !fs.statSync(requiredFile).isFile()) {
            throw new Error(`Generated wiki file is missing: ${requiredFile}`);
        }
    });
}

/**
 * Handle one static HTTP request.
 *
 * @param {object} params - Request parameters.
 * @param {http.IncomingMessage} params.request - Incoming request.
 * @param {http.ServerResponse} params.response - Server response.
 * @param {string} params.documentationPath - Static root.
 * @returns {void}
 */
function handleStaticRequest({ request, response, documentationPath }) {
    try {
        const redirectTarget = getRootRedirectTarget(request);

        if (redirectTarget) {
            writeRedirect({ response, location: redirectTarget });
            return;
        }

        const filePath = resolveRequestPath({ request, documentationPath });

        if (!filePath) {
            writeResponse({ response, statusCode: 403, body: 'Forbidden' });
            return;
        }

        if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
            writeResponse({ response, statusCode: 404, body: 'Not Found' });
            return;
        }

        response.writeHead(200, {
            'Content-Type': CONTENT_TYPES.get(path.extname(filePath).toLowerCase()) || 'application/octet-stream',
            'Cache-Control': 'no-store'
        });
        fs.createReadStream(filePath).pipe(response);
    } catch (error) {
        writeResponse({ response, statusCode: 400, body: error.message });
    }
}

/**
 * Resolve root requests to the canonical generated wiki document.
 *
 * @param {http.IncomingMessage} request - Incoming request.
 * @returns {string|null} Redirect location.
 */
function getRootRedirectTarget(request) {
    const requestUrl = new URL(request.url || '/', 'http://local');
    return requestUrl.pathname === '/' ? `/wiki/index.html${requestUrl.search}` : null;
}

/**
 * Resolve a request URL to a filesystem path inside documentationPath.
 *
 * @param {object} params - Resolve parameters.
 * @param {http.IncomingMessage} params.request - Incoming request.
 * @param {string} params.documentationPath - Static root.
 * @returns {string|null} Absolute file path or null when forbidden.
 */
function resolveRequestPath({ request, documentationPath }) {
    const requestUrl = new URL(request.url || '/', 'http://local');
    const decodedPath = decodeURIComponent(requestUrl.pathname);
    const relativePath = decodedPath === '/' ? 'wiki/index.html' : decodedPath.replace(/^\/+/, '');
    const candidatePath = path.resolve(documentationPath, relativePath);

    if (candidatePath !== documentationPath && !isPathInside(candidatePath, documentationPath)) {
        return null;
    }

    return candidatePath;
}

/**
 * Write a plain-text response.
 *
 * @param {object} params - Response parameters.
 * @param {http.ServerResponse} params.response - Server response.
 * @param {number} params.statusCode - HTTP status code.
 * @param {string} params.body - Response body.
 * @returns {void}
 */
function writeResponse({ response, statusCode, body }) {
    response.writeHead(statusCode, { 'Content-Type': 'text/plain; charset=utf-8' });
    response.end(body);
}

/**
 * Write a redirect response.
 *
 * @param {object} params - Redirect parameters.
 * @param {http.ServerResponse} params.response - Server response.
 * @param {string} params.location - Redirect location.
 * @returns {void}
 */
function writeRedirect({ response, location }) {
    response.writeHead(302, {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store',
        Location: location
    });
    response.end(`Redirecting to ${location}`);
}

/**
 * Await server listen.
 *
 * @param {http.Server} server - HTTP server.
 * @param {number} port - Port.
 * @param {string} host - Host.
 * @returns {Promise<void>} Resolves when listening.
 */
function listen(server, port, host) {
    return new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(port, host, () => {
            server.off('error', reject);
            resolve();
        });
    });
}
