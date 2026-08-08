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
     * Canonical workspace root currently served by Explorer.
     * @type {string}
     */
    workspaceRoot: string;
    /**
     * Consumer-local agent directory within the active workspace.
     * @type {string}
     */
    agentHome: string;
}
