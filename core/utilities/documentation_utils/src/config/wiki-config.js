/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * Static configuration for documentation utilities.
 */

export const MARKDOWN_EXTENSIONS = new Set(['.md', '.markdown']);

export const IGNORED_DIRECTORIES = new Set(['.git', 'node_modules', 'wiki']);

export const DOC_PRESETS = {
    readme: { title: 'Home', icon: '🏠' },
    'readme.es': { title: 'Inicio', icon: '🏠' },
    index: { title: 'Home', icon: '🏠' },
    architecture: { title: 'Architecture Blueprint', icon: '🏛️' },
    design: { title: 'Design & Theme', icon: '🎨' },
    interface: { title: 'UI Component Catalog', icon: '🖥️' },
    changelog: { title: 'Changelog History', icon: '🔄' },
    'agent-logs': { title: 'Agent Tech Logs', icon: '🤖' },
    backlog: { title: 'Project Backlog', icon: '📋' },
    api: { title: 'API Specification', icon: '🔌' },
    deployment: { title: 'Deployment Guide', icon: '🚀' },
    security: { title: 'Security Model', icon: '🔐' }
};

export const ASSETS_TO_COPY = [
    { source: 'svg-pan-zoom.min.js', target: 'scripts/svg-pan-zoom.min.js' },
    { source: 'marked.min.js', target: 'scripts/marked.min.js' },
    { source: 'mermaid.min.js', target: 'scripts/mermaid.min.js' },
    { source: 'prism.min.js', target: 'scripts/prism.min.js' },
    { source: 'prism-javascript.min.js', target: 'scripts/prism-javascript.min.js' },
    { source: 'prism-css.min.js', target: 'scripts/prism-css.min.js' },
    { source: 'prism-json.min.js', target: 'scripts/prism-json.min.js' },
    { source: 'prism-python.min.js', target: 'scripts/prism-python.min.js' },
    { source: 'prism-tomorrow.min.css', target: 'styles/prism-tomorrow.min.css' },
    { source: 'prism.min.css', target: 'styles/prism.min.css' },
    { source: 'wiki-core.css', target: 'styles/wiki-core.css' },
    { source: 'wiki-core.js', target: 'scripts/wiki-core.js' },
    { source: 'wiki-runtime/content-enhancer.js', target: 'scripts/wiki-runtime/content-enhancer.js' },
    { source: 'wiki-runtime/logs-reader.js', target: 'scripts/wiki-runtime/logs-reader.js' },
    { source: 'wiki-runtime/markdown-reader.js', target: 'scripts/wiki-runtime/markdown-reader.js' },
    { source: 'wiki-runtime/theme-service.js', target: 'scripts/wiki-runtime/theme-service.js' },
    { source: 'wiki-runtime/wiki-utils.js', target: 'scripts/wiki-runtime/wiki-utils.js' }
];
