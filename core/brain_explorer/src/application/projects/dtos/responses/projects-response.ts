/**
 * Workspace registered as a consumer of the current agent core.
 */
export interface ProjectRecord {
    /**
     * Human-readable workspace name rendered by the shell selector.
     * @type {string}
     */
    name: string;
    /**
     * Canonical absolute workspace root accepted by the server.
     * @type {string}
     */
    path: string;
}

/**
 * Complete registered-workspace listing returned to the application shell.
 */
export interface ProjectsResponse {
    /**
     * Whether the project-registry query succeeded.
     * @type {boolean}
     */
    ok: boolean;
    /**
     * Workspaces authorized to consume the current agent core.
     * @type {ProjectRecord[]}
     */
    projects: ProjectRecord[];
}
