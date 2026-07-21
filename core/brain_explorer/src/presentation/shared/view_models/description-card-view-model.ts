/**
 * Render-ready contracts for shared expandable description cards.
 *
 * @module presentation/shared/view_models/description-card-view-model
 */

/**
 * One parsed, addressable section contained by a description card.
 */
export interface DescriptionSection {
    /**
     * Stable section identity used by disclosure controls and anchors.
     * @type {string}
     */
    id: string;
    /**
     * Human-readable heading extracted from the source description.
     * @type {string}
     */
    title: string;
    /**
     * Markdown-capable section body excluding its heading marker.
     * @type {string}
     */
    body: string;
}

/**
 * Optional rendering policy supplied to the shared description-card renderer.
 */
export interface DescriptionCardOptions {
    /**
     * Fallback card title used when the source has no explicit heading.
     * @type {string | undefined}
     */
    title?: string;
    /**
     * Empty-state message rendered when the source contains no meaningful text.
     * @type {string | undefined}
     */
    emptyText?: string;
    /**
     * Whether the first parsed section starts expanded.
     * @type {boolean | undefined}
     */
    openFirst?: boolean;
}

/**
 * Intermediate heading boundary discovered while parsing a description source.
 */
export interface DescriptionMarker {
    /**
     * Inclusive source offset at which the heading marker begins.
     * @type {number}
     */
    index: number;
    /**
     * Exclusive source offset immediately after the heading text.
     * @type {number}
     */
    end: number;
    /**
     * Normalized human-readable heading title.
     * @type {string}
     */
    title: string;
}
