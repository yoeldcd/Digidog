/**
 * Owns mutable Knowledge canvas state shared by rendering and interaction collaborators.
 */
import type { ApiResponse } from "../../../application/shared/contracts/api-response-contract.ts";
import type { AvatarMessageRecord, AvatarMessageSession } from "../../../application/messages/dtos/responses/messages-response.ts";
import type { PictureRecord } from "../../../application/pictures/dtos/responses/pictures-response.ts";
import type { LogEntryPayload } from "../../../application/logs/dtos/responses/logs-response.ts";
import type { ComponentContext } from "../../shared/view_models/component-context-view-model.ts";
import type { KnowledgeGraphEdge, KnowledgeGraphNode, KnowledgeMode, KnowledgeNodeDrag, KnowledgePanState, KnowledgePoint, KnowledgePointerCandidate, KnowledgeRankedNode, KnowledgeRecord, KnowledgeRectangle, KnowledgeRegionHistoryEntry, KnowledgeRelation, KnowledgeRenderFrustum, KnowledgeScope, KnowledgeTreeNode, KnowledgeViewport, KnowledgeVisualType, KnowledgeSourceKind } from "../view_models/knowledge-view-model.ts";

/**
 * State-bearing base contract for Knowledge canvas presentation collaborators.
 */
export abstract class KnowledgeCanvasState extends HTMLElement {
    /**
     * Stores the shared Knowledge canvas api state used by rendering and interaction collaborators.
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/infrastructure/shared/http/clients/brain-api-client").BrainApiClient | null}
     */
    protected api: ComponentContext["api"] | null = null;
    /**
     * Stores the shared Knowledge canvas state state used by rendering and interaction collaborators.
     * @type {import("D:/.agents/@Angi/core/brain_explorer/src/presentation/shell/state/app-state").AppState | null}
     */
    protected state: ComponentContext["state"] | null = null;
    /**
     * Stores the shared Knowledge canvas scope state used by rendering and interaction collaborators.
     * @type {KnowledgeScope}
     */
    protected scope: KnowledgeScope = "all";
    /**
     * Stores the shared Knowledge canvas selecte copes state used by rendering and interaction collaborators.
     * @type {Set<"global" | "local">}
     */
    protected selectedScopes = new Set<Exclude<KnowledgeScope, "all">>(["global", "local"]);
    /**
     * Stores the shared Knowledge canvas tre cope state used by rendering and interaction collaborators.
     * @type {KnowledgeScope}
     */
    protected treeScope: KnowledgeScope = "all";
    /**
     * Stores the shared Knowledge canvas mode state used by rendering and interaction collaborators.
     * @type {KnowledgeMode}
     */
    protected mode: KnowledgeMode = "all";
    /**
     * Stores the shared Knowledge canvas domain state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected domain = "all";
    /**
     * Stores the shared Knowledge canvas query state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected query = "";
    /**
     * Stores the shared Knowledge canvas output state used by rendering and interaction collaborators.
     * @type {ApiResponse<unknown> | null}
     */
    protected output: ApiResponse | null = null;
    /**
     * Stores the shared Knowledge canvas records state used by rendering and interaction collaborators.
     * @type {KnowledgeRecord[]}
     */
    protected records: KnowledgeRecord[] = [];
    /**
     * Stores the shared Knowledge canvas relations state used by rendering and interaction collaborators.
     * @type {KnowledgeRelation[]}
     */
    protected relations: KnowledgeRelation[] = [];
    /**
     * Stores the shared Knowledge canvas nodes state used by rendering and interaction collaborators.
     * @type {KnowledgeGraphNode[]}
     */
    protected nodes: KnowledgeGraphNode[] = [];
    /**
     * Stores the shared Knowledge canvas edges state used by rendering and interaction collaborators.
     * @type {KnowledgeGraphEdge[]}
     */
    protected edges: KnowledgeGraphEdge[] = [];
    /**
     * Stores the shared Knowledge canvas selecte od d state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected selectedNodeId = "";
    /**
     * Stores the shared Knowledge canvas selecte elatio d state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected selectedRelationId = "";
    /**
     * Stores the shared Knowledge canvas hovere elatio d state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected hoveredRelationId = "";
    /**
     * Stores the shared Knowledge canvas hovere od d state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected hoveredNodeId = "";
    /**
     * Stores the shared Knowledge canvas regio od ds state used by rendering and interaction collaborators.
     * @type {Set<string>}
     */
    protected regionNodeIds = new Set<string>();
    /**
     * Stores the shared Knowledge canvas regio dg ds state used by rendering and interaction collaborators.
     * @type {Set<string>}
     */
    protected regionEdgeIds = new Set<string>();
    /**
     * Stores the shared Knowledge canvas regio ositions state used by rendering and interaction collaborators.
     * @type {Map<string, KnowledgePoint>}
     */
    protected regionPositions = new Map<string, KnowledgePoint>();
    /**
     * Stores the shared Knowledge canvas regio istory state used by rendering and interaction collaborators.
     * @type {KnowledgeRegionHistoryEntry[]}
     */
    protected regionHistory: KnowledgeRegionHistoryEntry[] = [];
    /**
     * Stores the shared Knowledge canvas regio oo od d state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected regionRootNodeId = "";
    /**
     * Stores the shared Knowledge canvas dra ode state used by rendering and interaction collaborators.
     * @type {KnowledgeNodeDrag | null}
     */
    protected dragNode: KnowledgeNodeDrag | null = null;
    /**
     * Stores the shared Knowledge canvas pa tate state used by rendering and interaction collaborators.
     * @type {KnowledgePanState | null}
     */
    protected panState: KnowledgePanState | null = null;
    /**
     * Stores the shared Knowledge canvas camer nimatio rame state used by rendering and interaction collaborators.
     * @type {number}
     */
    protected cameraAnimationFrame = 0;
    /**
     * Stores the shared Knowledge canvas viewport state used by rendering and interaction collaborators.
     * @type {KnowledgeViewport}
     */
    protected viewport: KnowledgeViewport = { x: 0, y: 0, scale: 1 };
    /**
     * Stores the shared Knowledge canvas rende rustum state used by rendering and interaction collaborators.
     * @type {KnowledgeRenderFrustum | null}
     */
    protected renderFrustum: KnowledgeRenderFrustum | null = null;
    /**
     * Stores the shared Knowledge canvas edg abe ounds state used by rendering and interaction collaborators.
     * @type {Map<string, KnowledgeRectangle>}
     */
    protected edgeLabelBounds = new Map<string, KnowledgeRectangle>();
    /**
     * Stores the shared Knowledge canvas nod abe ounds state used by rendering and interaction collaborators.
     * @type {Map<string, KnowledgeRectangle>}
     */
    protected nodeLabelBounds = new Map<string, KnowledgeRectangle>();
    /**
     * Stores the shared Knowledge canvas viewpor od ds state used by rendering and interaction collaborators.
     * @type {Set<string>}
     */
    protected viewportNodeIds = new Set<string>();
    /**
     * Stores the shared Knowledge canvas viewpor adg ignature state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected viewportBadgeSignature = "";
    /**
     * Stores the shared Knowledge canvas viewpor nspecto imer state used by rendering and interaction collaborators.
     * @type {number}
     */
    protected viewportInspectorTimer = 0;
    /**
     * Stores the shared Knowledge canvas viewpor adg ankin rozen state used by rendering and interaction collaborators.
     * @type {boolean}
     */
    protected viewportBadgeRankingFrozen = false;
    /**
     * Stores the shared Knowledge canvas expande omains state used by rendering and interaction collaborators.
     * @type {Set<string>}
     */
    protected expandedDomains = new Set<string>(["global::all", "local::all"]);
    /**
     * Stores the shared Knowledge canvas resiz bserver state used by rendering and interaction collaborators.
     * @type {ResizeObserver | null}
     */
    protected resizeObserver: ResizeObserver | null = null;
    /**
     * Stores the shared Knowledge canvas loa cheduled state used by rendering and interaction collaborators.
     * @type {boolean}
     */
    protected loadScheduled = false;
    /**
     * Stores the shared Knowledge canvas grap us epth state used by rendering and interaction collaborators.
     * @type {number}
     */
    protected graphBusyDepth = 0;
    /**
     * Stores the shared Knowledge canvas grap us abel state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected graphBusyLabel = "Loading graph";
    /**
     * Stores the shared Knowledge canvas need iewpor it state used by rendering and interaction collaborators.
     * @type {boolean}
     */
    protected needsViewportFit = true;
    /**
     * Stores the shared Knowledge canvas filter pen state used by rendering and interaction collaborators.
     * @type {boolean}
     */
    protected filtersOpen = false;
    /**
     * Stores the shared Knowledge canvas domai re odes state used by rendering and interaction collaborators.
     * @type {KnowledgeTreeNode[]}
     */
    protected domainTreeNodes: KnowledgeTreeNode[] = [];
    /**
     * Stores the shared Knowledge canvas memor aths state used by rendering and interaction collaborators.
     * @type {string[]}
     */
    protected memoryPaths: string[] = [];
    /**
     * Stores the shared Knowledge canvas pictures state used by rendering and interaction collaborators.
     * @type {PictureRecord[]}
     */
    protected pictures: PictureRecord[] = [];
    /**
     * Stores the shared Knowledge canvas messages state used by rendering and interaction collaborators.
     * @type {AvatarMessageRecord[]}
     */
    protected messages: AvatarMessageRecord[] = [];
    /**
     * Stores the shared Knowledge canvas messag essions state used by rendering and interaction collaborators.
     * @type {AvatarMessageSession[]}
     */
    protected messageSessions: AvatarMessageSession[] = [];
    /**
     * Stores the shared Knowledge canvas lo ntries state used by rendering and interaction collaborators.
     * @type {LogEntryPayload[]}
     */
    protected logEntries: LogEntryPayload[] = [];
    /**
     * Stores the shared Knowledge canvas selecte re ath state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected selectedTreePath = "";
    /**
     * Stores the shared Knowledge canvas sourc ath state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected sourcePath = "";
    /**
     * Stores the shared Knowledge canvas sourc ind state used by rendering and interaction collaborators.
     * @type {"" | KnowledgeSourceKind}
     */
    protected sourceKind: KnowledgeSourceKind | "" = "";
    /**
     * Stores the shared Knowledge canvas tre isua ype state used by rendering and interaction collaborators.
     * @type {"" | KnowledgeVisualType}
     */
    protected treeVisualType: KnowledgeVisualType | "" = "";
    /**
     * Stores the shared Knowledge canvas focu iewport state used by rendering and interaction collaborators.
     * @type {KnowledgeViewport | null}
     */
    protected focusViewport: KnowledgeViewport | null = null;
    /**
     * Stores the shared Knowledge canvas relatio ove iewport state used by rendering and interaction collaborators.
     * @type {KnowledgeViewport | null}
     */
    protected relationHoverViewport: KnowledgeViewport | null = null;
    /**
     * Stores the shared Knowledge canvas badg ove iewport state used by rendering and interaction collaborators.
     * @type {KnowledgeViewport | null}
     */
    protected badgeHoverViewport: KnowledgeViewport | null = null;
    /**
     * Stores the shared Knowledge canvas pointe andidate state used by rendering and interaction collaborators.
     * @type {KnowledgePointerCandidate | null}
     */
    protected pointerCandidate: KnowledgePointerCandidate | null = null;
    /**
     * Stores the shared Knowledge canvas domai olors state used by rendering and interaction collaborators.
     * @type {Map<string, string>}
     */
    protected domainColors = new Map<string, string>();
    /**
     * Stores the shared Knowledge canvas use omai olors state used by rendering and interaction collaborators.
     * @type {Set<string>}
     */
    protected usedDomainColors = new Set<string>();
    /**
     * Stores the shared Knowledge canvas pendin ntit abel state used by rendering and interaction collaborators.
     * @type {string}
     */
    protected pendingEntityLabel = "";


    /**
     * Render inspector markup owned by the concrete Knowledge facade.
     * @returns {string} A string containing the rendered details of the knowledge canvas.
     */
    protected abstract renderDetails(): string;
    /**
     * Redraw the current canvas after an interaction mutation.
     */
    protected abstract drawCanvas(): void;
    /**
     * Handle canvas pointer-down input.      * @param {PointerEvent} event The event value used by this operation.
     * @param {HTMLCanvasElement} canvas The canvas value used by this operation.
     */
    protected abstract onPointerDown(event: PointerEvent, canvas: HTMLCanvasElement): void;
    /**
     * Handle canvas pointer movement.      * @param {PointerEvent} event The event value used by this operation.
     * @param {HTMLCanvasElement} canvas The canvas value used by this operation.
     */
    protected abstract onPointerMove(event: PointerEvent, canvas: HTMLCanvasElement): void;
    /**
     * Finish canvas pointer input.      * @param {PointerEvent} event The event value used by this operation.
     * @param {HTMLCanvasElement} canvas The canvas value used by this operation.
     */
    protected abstract onPointerUp(event: PointerEvent, canvas: HTMLCanvasElement): void;
    /**
     * Apply wheel zoom input.      * @param {WheelEvent} event The event value used by this operation.
     * @param {HTMLCanvasElement} canvas The canvas value used by this operation.
     */
    protected abstract onWheel(event: WheelEvent, canvas: HTMLCanvasElement): void;
    /**
     * Reset the currently visible viewport.
     */
    protected abstract resetVisibleGraphViewport(): void;
    /**
     * Refresh the inspector DOM without rebuilding the layout.
     */
    protected abstract renderInspector(): void;
    /**
     * Rank visible graph nodes by connectivity.      * @param {KnowledgeGraphNode[]} candidates The candidates value used by this operation.
     *
     * @returns {KnowledgeRankedNode[]} An ordered list of nodes associated with their calculated importance ranks.
     */
    protected abstract rankImportantNodes(candidates: KnowledgeGraphNode[]): KnowledgeRankedNode[];
    /**
     * Render the transient relation preview.
     * @returns {string} A string containing the rendered relation preview.
     */
    protected abstract renderRelationPreview(): string;
    /**
     * Bind inspector actions after partial rendering.
     */
    protected abstract bindInspectorButtons(): void;
    /**
     * Resume viewport badge ranking after hover navigation.
     */
    protected abstract releaseViewportBadgeRanking(): void;
    /**
     * Reload all Knowledge records.      * @param {boolean | undefined} forceRefresh The force refresh value used by this operation.
     *
     * @returns {Promise<void>} A promise that resolves once the records have been processed and displayed.
     */
    protected abstract showRecords(forceRefresh?: boolean): Promise<void>;
    /**
     * Execute the active Knowledge query.
     * @returns {Promise<void>} A promise that resolves once the record query operation has completed.
     */
    protected abstract queryRecords(): Promise<void>;
    /**
     * Load pending Knowledge deltas.
     * @returns {Promise<void>} A promise that resolves once the delta review process is complete.
     */
    protected abstract reviewDeltas(): Promise<void>;
    /**
     * Apply current form filters.
     * @returns {Promise<void>} A promise that resolves once the filtering process is complete.
     */
    protected abstract applyFilters(): Promise<void>;
    /**
     * Apply the selected source-tree projection.
     * @returns {Promise<void>} A promise that resolves once the tree selection has been applied.
     */
    protected abstract applyTreeSelection(): Promise<void>;
    /**
     * Read current filter controls into view state.
     */
    protected abstract readControls(): void;
    /**
     * Rebuild graph nodes and edges from filtered records.
     */
    protected abstract prepareGraph(): void;
    /**
     * Begin a bounded graph operation.      * @param {string} label The label value used by this operation.
     */
    protected abstract beginGraphBusy(label: string): void;
    /**
     * Finish a bounded graph operation.
     */
    protected abstract endGraphBusy(): void;
    /**
     * Normalize and store one graph payload.      * @param {unknown} data The data value used by this operation.
     */
    protected abstract ingestGraph(data: unknown): void;
    /**
     * Render the complete Knowledge layout.
     */
    protected abstract render(): void;
    /**
     * Resolve a route-targeted entity after graph preparation.
     */
    protected abstract resolvePendingEntity(): void;
}
