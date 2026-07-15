/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Browser bootstrap for live documentation wiki pages.
 */

import { initializeTheme } from './wiki-runtime/theme-service.js';
import { startLogsPage } from './wiki-runtime/logs-reader.js';
import { startMarkdownReader } from './wiki-runtime/markdown-reader.js';

initializeTheme();

const pageKind = document.body.dataset.pageKind || 'reader';

if (pageKind === 'logs') {
    startLogsPage();
} else {
    startMarkdownReader();
}
