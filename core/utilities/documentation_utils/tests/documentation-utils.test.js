/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Focused contract tests for documentation utilities.
 */

import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';

import { checkDocumentationReferences } from '../src/services/reference-check-service.js';
import { buildBrainExportCommandArgs } from '../src/services/log-extraction-service.js';
import { generateDocumentationWiki } from '../src/services/wiki-generation-service.js';
import { serveDocumentationWiki } from '../src/services/static-server-service.js';

const TEMP_ROOTS = [];

after(() => {
    TEMP_ROOTS.forEach(tempRoot => {
        fs.rmSync(tempRoot, { recursive: true, force: true });
    });
});

test('wiki exports logs through the silent Brain runtime flag', () => {
    const commandArgs = buildBrainExportCommandArgs({
        activeLogDomain: 'core.documentation',
        logDate: '16-07-2026',
        logTime: null,
        logFrom: null,
        logTo: null
    });

    assert.deepEqual(commandArgs, [
        '--no-speak',
        'export-logs',
        '--domain',
        'core.documentation',
        '--date',
        '16-07-2026'
    ]);
});

test('generate writes only the live reader shell, logs page, manifest, and assets', () => {
    const documentationPath = createDocumentationFixture({
        files: {
            'README.md': '# Demo\n\nSee `Thing()`.\n\n## `Thing()`\n\nStable target.\n',
            'guide.md': '# Guide\n\nThe **Thing()** reference resolves.\n'
        }
    });
    const stalePage = path.join(documentationPath, 'wiki', 'readme.html');
    fs.mkdirSync(path.dirname(stalePage), { recursive: true });
    fs.writeFileSync(stalePage, '<p>stale</p>', 'utf8');

    const exitCode = generateDocumentationWiki({
        mode: 'generate',
        documentationPath,
        logDomain: 'demo'
    });

    assert.equal(exitCode, 0);
    assert.deepEqual(collectHtmlFiles(path.join(documentationPath, 'wiki')).sort(), ['index.html', 'logs.html']);
    assert.ok(fs.existsSync(path.join(documentationPath, 'wiki', 'scripts', 'wiki-core.js')));
    assert.ok(fs.existsSync(path.join(documentationPath, 'wiki', 'styles', 'wiki-core.css')));
    assert.ok(fs.existsSync(path.join(documentationPath, 'wiki', 'data', 'index.json')));

    const generatedReader = fs.readFileSync(
        path.join(documentationPath, 'wiki', 'scripts', 'wiki-runtime', 'markdown-reader.js'),
        'utf8'
    );
    const generatedEnhancer = fs.readFileSync(
        path.join(documentationPath, 'wiki', 'scripts', 'wiki-runtime', 'content-enhancer.js'),
        'utf8'
    );

    assert.match(generatedReader, /history\.pushState/);
    assert.match(generatedReader, /markdownCache/);
    assert.match(generatedEnhancer, /svgPanZoom/);
    assert.match(generatedEnhancer, /mermaid-control-btn/);
});

test('index.html loads the manifest externally instead of embedding site index JSON', () => {
    const documentationPath = createDocumentationFixture({
        files: {
            'README.md': '# Demo\n\n## Stable\n'
        }
    });

    generateDocumentationWiki({
        mode: 'generate',
        documentationPath,
        logDomain: 'demo'
    });

    const indexHtml = fs.readFileSync(path.join(documentationPath, 'wiki', 'index.html'), 'utf8');
    const manifest = JSON.parse(fs.readFileSync(path.join(documentationPath, 'wiki', 'data', 'index.json'), 'utf8'));

    assert.equal(indexHtml.includes('wiki-site-index'), false);
    assert.equal(indexHtml.includes('type="application/json"'), false);
    assert.match(indexHtml, /manifestPath:\s*'data\/index\.json'/);
    assert.equal(manifest.pages[0].source, 'README.md');
    assert.equal(manifest.headings.some(heading => heading.term === 'Stable'), true);
});

test('check reports missing explicit references', () => {
    const documentationPath = createDocumentationFixture({
        files: {
            'README.md': '# Demo\n\nThis mentions `MissingThing()` without a heading.\n'
        }
    });

    const exitCode = checkDocumentationReferences({
        mode: 'check',
        documentationPath,
        logDomain: null
    });

    assert.equal(exitCode, 1);
});

test('serve is strict, serves generated files, and rejects traversal', async () => {
    const documentationPath = createDocumentationFixture({
        files: {
            'README.md': '# Demo\n\n## Stable\n'
        }
    });

    generateDocumentationWiki({
        mode: 'generate',
        documentationPath,
        logDomain: 'demo'
    });

    const beforeManifest = fs.readFileSync(path.join(documentationPath, 'wiki', 'data', 'index.json'), 'utf8');
    const serverInfo = await serveDocumentationWiki({
        mode: 'serve',
        documentationPath,
        host: '127.0.0.1',
        port: 0
    });

    try {
        const baseUrl = `http://${serverInfo.host}:${serverInfo.port}`;
        const rootResponse = await fetch(`${baseUrl}/`, { redirect: 'manual' });
        const indexResponse = await fetch(`${serverInfo.url}`);
        const stylesResponse = await fetch(`${baseUrl}/wiki/styles/wiki-core.css`);
        const markdownResponse = await fetch(`${baseUrl}/README.md`);
        const traversalResponse = await fetch(`${baseUrl}/%2e%2e%2fpackage.json`);

        assert.equal(rootResponse.status, 302);
        assert.equal(rootResponse.headers.get('location'), '/wiki/index.html');
        assert.equal(serverInfo.url, `${baseUrl}/wiki/index.html`);
        assert.equal(indexResponse.status, 200);
        assert.match(indexResponse.headers.get('content-type'), /text\/html/);
        assert.equal(stylesResponse.status, 200);
        assert.match(stylesResponse.headers.get('content-type'), /text\/css/);
        assert.equal(markdownResponse.status, 200);
        assert.match(markdownResponse.headers.get('content-type'), /text\/markdown/);
        assert.equal(traversalResponse.status, 403);
        assert.equal(fs.readFileSync(path.join(documentationPath, 'wiki', 'data', 'index.json'), 'utf8'), beforeManifest);
    } finally {
        await new Promise(resolve => serverInfo.server.close(resolve));
    }
});

test('serve fails when generated wiki files are missing', async () => {
    const documentationPath = createDocumentationFixture({
        files: {
            'README.md': '# Demo\n'
        }
    });

    await assert.rejects(() => serveDocumentationWiki({
        mode: 'serve',
        documentationPath,
        host: '127.0.0.1',
        port: 0
    }), /Generated wiki file is missing/);
});

/**
 * Create a temporary documentation fixture.
 *
 * @param {object} params - Fixture parameters.
 * @param {Record<string, string>} params.files - Relative file content map.
 * @returns {string} Documentation path.
 */
function createDocumentationFixture({ files }) {
    const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'documentation-utils-'));
    const documentationPath = path.join(tempRoot, 'project', 'documentation');
    TEMP_ROOTS.push(tempRoot);

    Object.entries(files).forEach(([relativePath, content]) => {
        const filePath = path.join(documentationPath, relativePath);
        fs.mkdirSync(path.dirname(filePath), { recursive: true });
        fs.writeFileSync(filePath, content, 'utf8');
    });

    return documentationPath;
}

/**
 * Collect generated HTML files under a wiki directory.
 *
 * @param {string} wikiDir - Wiki directory.
 * @returns {string[]} Relative POSIX HTML files.
 */
function collectHtmlFiles(wikiDir) {
    const files = [];
    const entries = fs.readdirSync(wikiDir, { withFileTypes: true });

    entries.forEach(entry => {
        const absolutePath = path.join(wikiDir, entry.name);

        if (entry.isDirectory()) {
            collectHtmlFiles(absolutePath).forEach(child => {
                files.push(`${entry.name}/${child}`.replace(/\\/g, '/'));
            });
            return;
        }

        if (entry.isFile() && entry.name.endsWith('.html')) {
            files.push(entry.name);
        }
    });

    return files;
}
