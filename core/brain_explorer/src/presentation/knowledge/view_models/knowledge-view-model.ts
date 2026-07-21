/**
 * Strong presentation contracts for the interactive Knowledge graph layout.
 *
 * The Knowledge Web Component consumes these view-ready models but does not own
 * them. Keeping graph geometry, normalized records, tree metadata, viewport
 * state, and pointer state here makes the rendering contract explicit and
 * permits the oversized component to be decomposed without reintroducing
 * implicit `any` values.
 *
 * @module presentation/knowledge/view_models/knowledge-view-model
 */

import type { StructureTreeNode } from "../../shared/view_models/structure-tree-view-model.ts";

/**
 * Graph record scope selected by the user.
 */
export type KnowledgeScope = "all" | "global" | "local";
/**
 * Graph record mode selected by the user.
 */
export type KnowledgeMode = "all" | "entities" | "classes";
/**
 * Visual node category assigned after transport normalization.
 */
export type KnowledgeVisualType = "entity" | "class";
/**
 * Canonical physical source categories displayed in the Knowledge tree.
 */
export type KnowledgeSourceKind = "memory" | "pictures" | "logs" | "messages";

/**
 * Transport-tolerant knowledge item before normalization.
 *
 * Every known property remains `unknown` because CLI commands expose several
 * schemas. Normalization functions must convert each value before it reaches a
 * view-ready contract.
 */
export interface RawKnowledgeItem {
    [property: string]: unknown;
    /**
     * Presentation-only visual discriminator injected by a normalized source.
     * @type {unknown}
     */
    __visualType?: unknown;
    /**
     * Generic record identity emitted by canonical projections.
     * @type {unknown}
     */
    id?: unknown;
    /**
     * Snake-case entity identity emitted by CLI and persistence projections.
     * @type {unknown}
     */
    entity_id?: unknown;
    /**
     * Snake-case relation identity emitted by CLI and persistence projections.
     * @type {unknown}
     */
    relation_id?: unknown;
    /**
     * Primary human-readable record label.
     * @type {unknown}
     */
    label?: unknown;
    /**
     * Compatibility name used as an entity-label fallback.
     * @type {unknown}
     */
    name?: unknown;
    /**
     * Compatibility title used as a record-label fallback.
     * @type {unknown}
     */
    title?: unknown;
    /**
     * Generic scalar or textual record value.
     * @type {unknown}
     */
    value?: unknown;
    /**
     * Canonical dotted ownership domain.
     * @type {unknown}
     */
    domain?: unknown;
    /**
     * Compatibility dotted domain supplied by a physical source.
     * @type {unknown}
     */
    source_domain?: unknown;
    /**
     * Physical or semantic source classification.
     * @type {unknown}
     */
    source_type?: unknown;
    /**
     * Canonical path of the physical source artifact.
     * @type {unknown}
     */
    source_path?: unknown;
    /**
     * Compatibility source-file path.
     * @type {unknown}
     */
    source_file?: unknown;
    /**
     * Generic source identity, path, or nested source object.
     * @type {unknown}
     */
    source?: unknown;
    /**
     * Compatibility record or source path.
     * @type {unknown}
     */
    path?: unknown;
    /**
     * Physical global/local knowledge scope.
     * @type {unknown}
     */
    knowledge_scope?: unknown;
    /**
     * Primary human-readable record description.
     * @type {unknown}
     */
    description?: unknown;
    /**
     * Compatibility content body used as a description fallback.
     * @type {unknown}
     */
    content?: unknown;
    /**
     * Compatibility text body used as a description fallback.
     * @type {unknown}
     */
    text?: unknown;
    /**
     * Source-provided confidence score or classification.
     * @type {unknown}
     */
    confidence?: unknown;
    /**
     * Snake-case semantic class name.
     * @type {unknown}
     */
    class_name?: unknown;
    /**
     * Compatibility semantic class name or object.
     * @type {unknown}
     */
    class?: unknown;
    /**
     * Generic record or relation type discriminator.
     * @type {unknown}
     */
    type?: unknown;
    /**
     * Relation subject identity or label.
     * @type {unknown}
     */
    from?: unknown;
    /**
     * Relation object identity or label.
     * @type {unknown}
     */
    to?: unknown;
    /**
     * Compatibility relation-subject identity.
     * @type {unknown}
     */
    from_id?: unknown;
    /**
     * Compatibility relation-object identity.
     * @type {unknown}
     */
    to_id?: unknown;
    /**
     * Source-side relation endpoint identity.
     * @type {unknown}
     */
    source_id?: unknown;
    /**
     * Target-side relation endpoint identity.
     * @type {unknown}
     */
    target_id?: unknown;
    /**
     * Human-readable relation-subject label.
     * @type {unknown}
     */
    from_label?: unknown;
    /**
     * Human-readable relation-object label.
     * @type {unknown}
     */
    to_label?: unknown;
    /**
     * Generic relation predicate or nested relation projection.
     * @type {unknown}
     */
    relation?: unknown;
    /**
     * Semantic predicate label.
     * @type {unknown}
     */
    predicate?: unknown;
    /**
     * Nested entity collection carried by aggregate payloads.
     * @type {unknown}
     */
    entities?: unknown;
    /**
     * Nested class collection carried by aggregate payloads.
     * @type {unknown}
     */
    classes?: unknown;
    /**
     * Nested generic record collection.
     * @type {unknown}
     */
    records?: unknown;
    /**
     * Compatibility nested node collection.
     * @type {unknown}
     */
    nodes?: unknown;
    /**
     * Nested semantic relation collection.
     * @type {unknown}
     */
    relations?: unknown;
    /**
     * Compatibility nested edge collection.
     * @type {unknown}
     */
    edges?: unknown;
    /**
     * Compatibility nested link collection.
     * @type {unknown}
     */
    links?: unknown;
}

/**
 * Raw node value supported by CLI list projections.
 */
export type RawKnowledgeNodeValue = RawKnowledgeItem | string;

/**
 * Normalized entity or class record independent of canvas geometry.
 */
export interface KnowledgeRecord {
    /**
     * Stable identity used by graph relations and tree navigation.
     * @type {string}
     */
    id: string;
    /**
     * Human-readable entity or class label.
     * @type {string}
     */
    label: string;
    /**
     * Discriminator identifying a normalized graph node record.
     * @type {"node"}
     */
    kind: "node";
    /**
     * Visual category controlling shape and filtering.
     * @type {KnowledgeVisualType}
     */
    visualType: KnowledgeVisualType;
    /**
     * Supplemental type or source context shown by the inspector.
     * @type {string}
     */
    context: string;
    /**
     * Optional class hint used to resolve relation endpoints.
     * @type {string}
     */
    classHint: string;
    /**
     * Dot-delimited owning domain.
     * @type {string}
     */
    domain: string;
    /**
     * Canonical application entity identity when provided.
     * @type {string}
     */
    entityId: string;
    /**
     * Global or local knowledge scope.
     * @type {string}
     */
    knowledgeScope: string;
    /**
     * Canonical source path or source identifier.
     * @type {string}
     */
    source: string;
    /**
     * Human-readable record description.
     * @type {string}
     */
    description: string;
    /**
     * Optional confidence value retained from the CLI projection.
     * @type {unknown}
     */
    confidence: unknown;
    /**
     * Original normalized input retained for inspection and provenance.
     * @type {RawKnowledgeItem}
     */
    raw: RawKnowledgeItem;
}

/**
 * Normalized semantic relation independent of canvas geometry.
 */
export interface KnowledgeRelation {
    /**
     * Stable relation identity used by selection and canvas hit testing.
     * @type {string}
     */
    id: string;
    /**
     * Discriminator identifying a normalized semantic relation record.
     * @type {"relation"}
     */
    kind: "relation";
    /**
     * Human-readable predicate label.
     * @type {string}
     */
    label: string;
    /**
     * Canonical dotted ownership domain.
     * @type {string}
     */
    domain: string;
    /**
     * Physical global/local knowledge scope.
     * @type {string}
     */
    knowledgeScope: string;
    /**
     * Resolved visible subject node identity.
     * @type {string}
     */
    from: string;
    /**
     * Resolved visible object node identity.
     * @type {string}
     */
    to: string;
    /**
     * Canonical application entity identity for the subject endpoint.
     * @type {string}
     */
    fromEntityId: string;
    /**
     * Canonical application entity identity for the object endpoint.
     * @type {string}
     */
    toEntityId: string;
    /**
     * Human-readable subject label retained for endpoint resolution.
     * @type {string}
     */
    fromLabel: string;
    /**
     * Human-readable object label retained for endpoint resolution.
     * @type {string}
     */
    toLabel: string;
    /**
     * Semantic class hint for the subject endpoint.
     * @type {string}
     */
    fromClass: string;
    /**
     * Semantic class hint for the object endpoint.
     * @type {string}
     */
    toClass: string;
    /**
     * Canonical source path or source identifier.
     * @type {string}
     */
    source: string;
    /**
     * Supplemental relation type or provenance context.
     * @type {string}
     */
    context: string;
    /**
     * Human-readable relation description.
     * @type {string}
     */
    description: string;
    /**
     * Optional source-provided confidence retained without coercion.
     * @type {unknown}
     */
    confidence: unknown;
    /**
     * Original normalized input retained for inspection and provenance.
     * @type {RawKnowledgeItem}
     */
    raw: RawKnowledgeItem;
}

/**
 * Complete normalized graph projection returned by payload collection.
 */
export interface KnowledgeGraphCollection {
    /**
     * Normalized entity and class records.
     * @type {KnowledgeRecord[]}
     */
    records: KnowledgeRecord[];
    /**
     * Normalized semantic relations.
     * @type {KnowledgeRelation[]}
     */
    relations: KnowledgeRelation[];
}

/**
 * Records and relations selected by one virtual tree projection.
 */
export interface KnowledgeTreeProjection {
    /**
     * Records accepted by the current virtual tree selection.
     * @type {KnowledgeRecord[]}
     */
    records: KnowledgeRecord[];
    /**
     * Relations accepted by the selection or required to connect selected endpoints.
     * @type {KnowledgeRelation[]}
     */
    relations: KnowledgeRelation[];
}

/**
 * Same-name record merged across physical knowledge scopes.
 */
export interface MergedKnowledgeRecord extends KnowledgeRecord {
    /**
     * Alternate labels merged into the visible identity.
     * @type {string[]}
     */
    aliases: string[];
    /**
     * Physical scopes contributing records to the visible identity.
     * @type {string[]}
     */
    knowledgeScopes: string[];
    /**
     * Canonical source paths contributing to the visible identity.
     * @type {string[]}
     */
    sources: string[];
}

/**
 * Canonical physical-source entry projected beneath a tree category.
 */
export interface KnowledgeSourceEntry {
    /**
     * Ordered physical path segments rendered beneath the source category.
     * @type {string[]}
     */
    segments: string[];
    /**
     * Optional source path associated with each intermediate segment.
     * @type {string[] | undefined}
     */
    sourcePrefixes?: string[];
    /**
     * Canonical graph domain selected by the terminal entry.
     * @type {string}
     */
    domain: string;
    /**
     * Canonical physical source path selected by the terminal entry.
     * @type {string}
     */
    sourcePath: string;
    /**
     * Optional Explorer route opened by the terminal source action.
     * @type {string | undefined}
     */
    openRoute?: string;
    /**
     * Route-specific target values supplied to the opened feature.
     * @type {Record<string, string> | undefined}
     */
    openTarget?: Record<string, string>;
    /**
     * Optional source summary rendered as secondary tree content.
     * @type {string | undefined}
     */
    detail?: string;
}

/**
 * Mutable accumulator used while constructing physical-source tree branches.
 */
export interface KnowledgeSourceTreeAccumulator {
    /**
     * Visible label for the current physical path segment.
     * @type {string}
     */
    label: string;
    /**
     * Stable selection identity assembled from scope, category, and segments.
     * @type {string}
     */
    path: string;
    /**
     * Physical knowledge scope containing the source.
     * @type {KnowledgeScope}
     */
    scope: KnowledgeScope;
    /**
     * Canonical graph domain selected by this branch.
     * @type {string}
     */
    domain: string;
    /**
     * Physical source category represented by this branch.
     * @type {"" | KnowledgeSourceKind}
     */
    sourceKind: KnowledgeSourceKind | "";
    /**
     * Canonical source path when the branch maps to a physical artifact.
     * @type {string}
     */
    sourcePath: string;
    /**
     * Mutable child accumulator nodes keyed by their collision-safe segment identity.
     * @type {Map<string, KnowledgeSourceTreeAccumulator>}
     */
    children: Map<string, KnowledgeSourceTreeAccumulator>;
    /**
     * Optional physical prefixes associated with intermediate path segments.
     * @type {string[] | undefined}
     */
    sourcePrefixes?: string[];
    /**
     * Original ordered physical path segments.
     * @type {string[] | undefined}
     */
    segments?: string[];
    /**
     * Optional Explorer route opened by a terminal source action.
     * @type {string | undefined}
     */
    openRoute?: string;
    /**
     * Route-specific target values supplied to the opened feature.
     * @type {Record<string, string> | undefined}
     */
    openTarget?: Record<string, string>;
    /**
     * Optional physical source summary.
     * @type {string | undefined}
     */
    detail?: string;
    /**
     * Optional entity/class selection applied by virtual class branches.
     * @type {"" | KnowledgeVisualType | undefined}
     */
    visualType?: KnowledgeVisualType | "";
    /**
     * Optional stable sibling ordering key.
     * @type {string | undefined}
     */
    sortKey?: string;
}

/**
 * Canvas node containing normalized record data plus mutable geometry.
 */
export interface KnowledgeGraphNode extends KnowledgeRecord {
    /**
     * Horizontal graph-space center.
     * @type {number}
     */
    x: number;
    /**
     * Vertical graph-space center.
     * @type {number}
     */
    y: number;
    /**
     * Current connectivity-scaled node radius.
     * @type {number}
     */
    radius: number;
    /**
     * Stable radius before visible-connectivity scaling.
     * @type {number}
     */
    baseRadius: number;
    /**
     * Stable domain color used by node and related edge rendering.
     * @type {string}
     */
    color: string;
    /**
     * Alternate record labels merged into this visible node.
     * @type {string[]}
     */
    aliases: string[];
    /**
     * Physical scopes contributing to this visible node.
     * @type {string[]}
     */
    knowledgeScopes: string[];
    /**
     * Canonical physical sources contributing to this visible node.
     * @type {string[]}
     */
    sources: string[];
}

/**
 * Graph node enriched with its connectivity rank for inspector shortcuts.
 */
export interface KnowledgeRankedNode extends KnowledgeGraphNode {
    /**
     * Number of visible relations incident to the node in the active projection.
     * @type {number}
     */
    readonly degree: number;
}

/**
 * Canvas edge joining two visible graph-node identities.
 */
export interface KnowledgeGraphEdge extends KnowledgeRelation {
    /**
     * Visible subject node identity after record merging.
     * @type {string}
     */
    from: string;
    /**
     * Visible object node identity after record merging.
     * @type {string}
     */
    to: string;
    /**
     * Stable edge color derived from its owning domain.
     * @type {string}
     */
    color: string;
}

/**
 * Mutable camera transform in graph coordinates.
 */
export interface KnowledgeViewport {
    /**
     * Horizontal graph-space coordinate rendered at the viewport origin.
     * @type {number}
     */
    x: number;
    /**
     * Vertical graph-space coordinate rendered at the viewport origin.
     * @type {number}
     */
    y: number;
    /**
     * Screen-to-graph scale multiplier.
     * @type {number}
     */
    scale: number;
}
/**
 * Two-dimensional graph point.
 */
export interface KnowledgePoint {
    /**
     * Horizontal graph-space coordinate.
     * @type {number}
     */
    x: number;
    /**
     * Vertical graph-space coordinate.
     * @type {number}
     */
    y: number;
}
/**
 * Axis-aligned graph-space rectangle.
 */
export interface KnowledgeRectangle {
    /**
     * Minimum horizontal coordinate.
     * @type {number}
     */
    left: number;
    /**
     * Maximum horizontal coordinate.
     * @type {number}
     */
    right: number;
    /**
     * Minimum vertical coordinate.
     * @type {number}
     */
    top: number;
    /**
     * Maximum vertical coordinate.
     * @type {number}
     */
    bottom: number;
}
/**
 * Render rectangle enriched with center and circumscribed radius.
 */
export interface KnowledgeRenderFrustum extends KnowledgeRectangle {
    /**
     * Horizontal center used by radial edge-culling checks.
     * @type {number}
     */
    centerX: number;
    /**
     * Vertical center used by radial edge-culling checks.
     * @type {number}
     */
    centerY: number;
    /**
     * Circumscribed radius enclosing the complete viewport rectangle.
     * @type {number}
     */
    radius: number;
}
/**
 * Active visible graph subset.
 */
export interface KnowledgeGraphFocus {
    /**
     * Visible graph-node identities.
     * @type {Set<string>}
     */
    nodeIds: Set<string>;
    /**
     * Visible graph-edge identities.
     * @type {Set<string>}
     */
    edgeIds: Set<string>;
}

/**
 * Node drag operation captured between pointer down and pointer up.
 */
export interface KnowledgeNodeDrag {
    /**
     * Identity of the node being repositioned.
     * @type {string}
     */
    id: string;
    /**
     * Horizontal pointer-to-center offset captured on pointer down.
     * @type {number}
     */
    offsetX: number;
    /**
     * Vertical pointer-to-center offset captured on pointer down.
     * @type {number}
     */
    offsetY: number;
}
/**
 * Canvas pan operation captured between pointer down and pointer up.
 */
export interface KnowledgePanState {
    /**
     * Browser pointer identity owning the active capture.
     * @type {number}
     */
    pointerId: number;
    /**
     * Latest horizontal client coordinate.
     * @type {number}
     */
    clientX: number;
    /**
     * Latest vertical client coordinate.
     * @type {number}
     */
    clientY: number;
    /**
     * Camera horizontal origin captured when panning began.
     * @type {number}
     */
    startX: number;
    /**
     * Camera vertical origin captured when panning began.
     * @type {number}
     */
    startY: number;
}
/**
 * Candidate click retained until movement exceeds the drag threshold.
 */
export interface KnowledgePointerCandidate {
    /**
     * Candidate graph-node identity, or an empty string for a canvas click.
     * @type {string}
     */
    id: string;
    /**
     * Browser pointer identity owning the candidate gesture.
     * @type {number}
     */
    pointerId: number;
    /**
     * Horizontal client coordinate captured on pointer down.
     * @type {number}
     */
    clientX: number;
    /**
     * Vertical client coordinate captured on pointer down.
     * @type {number}
     */
    clientY: number;
    /**
     * Horizontal node drag offset captured on pointer down.
     * @type {number}
     */
    offsetX: number;
    /**
     * Vertical node drag offset captured on pointer down.
     * @type {number}
     */
    offsetY: number;
    /**
     * Whether movement exceeded the click-to-drag threshold.
     * @type {boolean}
     */
    moved: boolean;
}

/**
 * Snapshot used to restore one parent graph-region navigation level.
 */
export interface KnowledgeRegionHistoryEntry {
    /**
     * Node identities visible at the captured parent level.
     * @type {Set<string>}
     */
    nodeIds: Set<string>;
    /**
     * Edge identities visible at the captured parent level.
     * @type {Set<string>}
     */
    edgeIds: Set<string>;
    /**
     * Region-specific node positions persisted for exact restoration.
     * @type {Map<string, KnowledgePoint>}
     */
    positions: Map<string, KnowledgePoint>;
    /**
     * Complete graph positions captured before entering the child region.
     * @type {Map<string, KnowledgePoint>}
     */
    graphPositions: Map<string, KnowledgePoint>;
    /**
     * Root node identity of the captured region.
     * @type {string}
     */
    rootNodeId: string;
    /**
     * Selected node identity at the captured level.
     * @type {string}
     */
    selectedNodeId: string;
    /**
     * Selected relation identity at the captured level.
     * @type {string}
     */
    selectedRelationId: string;
    /**
     * Camera transform displayed at the captured level.
     * @type {KnowledgeViewport}
     */
    viewport: KnowledgeViewport;
}

/**
 * Domain/source tree node with Knowledge-specific selection metadata.
 */
export interface KnowledgeTreeNode extends StructureTreeNode {
    /**
     * Physical scope selected by this node.
     * @type {KnowledgeScope | undefined}
     */
    scope?: KnowledgeScope;
    /**
     * Canonical graph domain selected by this node.
     * @type {string | undefined}
     */
    domain?: string;
    /**
     * Physical source category selected by this node.
     * @type {string | undefined}
     */
    sourceKind?: string;
    /**
     * Canonical physical source path selected by this node.
     * @type {string | undefined}
     */
    sourcePath?: string;
    /**
     * Optional entity/class visual discriminator selected by virtual branches.
     * @type {"" | KnowledgeVisualType | undefined}
     */
    visualType?: KnowledgeVisualType | "";
    /**
     * Recursively nested Knowledge-specific child nodes.
     * @type {KnowledgeTreeNode[] | undefined}
     */
    children?: KnowledgeTreeNode[];
    /**
     * Optional Explorer route opened by the source action.
     * @type {string | undefined}
     */
    openRoute?: string;
    /**
     * Route-specific target values, or null when no navigation action exists.
     * @type {Record<string, string> | null | undefined}
     */
    openTarget?: Record<string, string> | null;
}

/**
 * Estimated screen footprint used by connected-component layout packing.
 */
export interface KnowledgeNodeFootprint {
    /**
     * Total estimated node and label width in graph units.
     * @type {number}
     */
    width: number;
    /**
     * Total estimated node and label height in graph units.
     * @type {number}
     */
    height: number;
    /**
     * Minimum packing gap required around the footprint.
     * @type {number}
     */
    gap: number;
    /**
     * Maximum incident relation-label width contributing to horizontal spacing.
     * @type {number}
     */
    relationLabelWidth: number;
}
/**
 * Bounding box used to pack a connected graph component.
 */
export interface KnowledgeComponentBounds {
    /**
     * Minimum horizontal graph coordinate occupied by the component.
     * @type {number}
     */
    minX: number;
    /**
     * Maximum horizontal graph coordinate occupied by the component.
     * @type {number}
     */
    maxX: number;
    /**
     * Minimum vertical graph coordinate occupied by the component.
     * @type {number}
     */
    minY: number;
    /**
     * Maximum vertical graph coordinate occupied by the component.
     * @type {number}
     */
    maxY: number;
    /**
     * Total component width including node-label footprints.
     * @type {number}
     */
    width: number;
    /**
     * Total component height including node-label footprints.
     * @type {number}
     */
    height: number;
}

/**
 * Connectivity projection used by graph sizing and arrow ranking.
 */
export interface KnowledgeConnectivityMetrics {
    /**
     * Visible relation degree keyed by graph-node identity.
     * @type {Map<string, number>}
     */
    degrees: Map<string, number>;
    /**
     * Highest visible degree, clamped to at least one.
     * @type {number}
     */
    maxDegree: number;
    /**
     * Return one node's degree normalized to the current maximum.
     *
     * @param {string} nodeId Visible graph-node identity whose connectivity is requested.
     * @returns {number} Normalized score between zero and one.
     */
    score(nodeId: string): number;
}
