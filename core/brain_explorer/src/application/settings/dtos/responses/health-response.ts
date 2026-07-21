/**
 * Runtime and workspace identity returned by the Explorer health endpoint.
 */
export interface HealthStatus {
    /**
     * Whether the Explorer server reports a healthy runtime.
     * @type {boolean}
     */
    ok: boolean;
    /**
     * Human-readable service name.
     * @type {string}
     */
    name: string;
    /**
     * Absolute path from which compiled frontend assets are served.
     * @type {string}
     */
    distDir: string;
    /**
     * Canonical workspace root currently served by Explorer.
     * @type {string}
     */
    workspaceRoot: string;
    /**
     * Canonical shared agent-home directory used by the server.
     * @type {string}
     */
    agentHome: string;
}
