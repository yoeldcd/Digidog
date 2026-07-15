/**
 * @author Angi Ichiva
 * @version 2.0.0
 *
 * DTO contracts shared by the documentation utilities runtime.
 */

/**
 * @typedef {object} CliCommandDTO
 * @property {'generate'|'check'|'serve'|'help'} mode - Selected command mode.
 * @property {string} [documentationPath] - Absolute documentation directory path.
 * @property {string|null} [logDomain] - Optional log superdomain.
 * @property {string} [host] - Serve host.
 * @property {number} [port] - Serve port.
 */

/**
 * Data transfer object for one markdown source page.
 */
export class WikiPageDTO {
    /**
     * @param {object} params - Page values.
     * @param {string} params.id - Stable page identifier.
     * @param {string} params.source - POSIX markdown path relative to the documentation directory.
     * @param {string} params.absolutePath - Absolute markdown path.
     * @param {string} params.title - Reader-facing page title.
     * @param {string} params.icon - Sidebar icon.
     * @param {string} params.markdownText - Raw markdown content.
     */
    constructor({ id, source, absolutePath, title, icon, markdownText }) {
        this.id = id;
        this.source = source;
        this.absolutePath = absolutePath;
        this.title = title;
        this.icon = icon;
        this.markdownText = markdownText;
    }
}

/**
 * Data transfer object for one manifest heading entry.
 */
export class WikiHeadingDTO {
    /**
     * @param {object} params - Heading values.
     * @param {string} params.term - Display heading term.
     * @param {string} params.normalizedTerm - Normalized lookup key.
     * @param {number} params.level - Markdown heading level.
     * @param {string} params.pageId - Owning page id.
     * @param {string} params.pageTitle - Owning page title.
     * @param {string} params.source - Markdown source path.
     * @param {string} params.anchor - Browser heading anchor.
     */
    constructor({ term, normalizedTerm, level, pageId, pageTitle, source, anchor }) {
        this.term = term;
        this.normalizedTerm = normalizedTerm;
        this.level = level;
        this.pageId = pageId;
        this.pageTitle = pageTitle;
        this.source = source;
        this.anchor = anchor;
    }
}

/**
 * Data transfer object for the generated wiki manifest.
 */
export class WikiManifestDTO {
    /**
     * @param {object} params - Manifest values.
     * @param {string} params.projectName - Resolved project name.
     * @param {WikiPageDTO[]} params.pages - Markdown pages.
     * @param {WikiHeadingDTO[]} params.headings - Cross-page headings.
     * @param {Array<object>} params.virtualPages - Generated virtual pages.
     */
    constructor({ projectName, pages, headings, virtualPages }) {
        this.version = 2;
        this.projectName = projectName;
        this.generatedAt = new Date().toISOString();
        this.pages = pages.map(page => ({
            id: page.id,
            title: page.title,
            icon: page.icon,
            source: page.source,
            sourceHref: `../${page.source}`
        }));
        this.headings = headings;
        this.virtualPages = virtualPages;
    }
}

/**
 * Data transfer object for one explicit reference mention.
 */
export class ReferenceMentionDTO {
    /**
     * @param {object} params - Mention values.
     * @param {string} params.term - Mentioned reference term.
     * @param {string} params.normalizedTerm - Normalized term.
     * @param {string} params.type - Reference classifier.
     * @param {string} params.page - Source page path.
     * @param {number} params.line - One-based source line.
     */
    constructor({ term, normalizedTerm, type, page, line }) {
        this.term = term;
        this.normalizedTerm = normalizedTerm;
        this.type = type;
        this.page = page;
        this.line = line;
    }
}
