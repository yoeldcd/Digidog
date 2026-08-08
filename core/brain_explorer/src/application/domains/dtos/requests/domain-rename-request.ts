/**
 * Request contract for renaming one domain node or complete subtree.
 */
export interface DomainRenameRequest {
    /**
     * Existing canonical domain path.
     * @type {string}
     */
    source: string;
    /**
     * Replacement canonical domain path.
     * @type {string}
     */
    target: string;
    /**
     * Whether descendants must remain unchanged.
     * @type {boolean | undefined}
     */
    exact?: boolean;
}
