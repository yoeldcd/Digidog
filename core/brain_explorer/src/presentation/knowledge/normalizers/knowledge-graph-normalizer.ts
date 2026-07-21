/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import { isRawKnowledgeItem, rawKnowledgeItems } from "../validators/knowledge-payload.ts";
import type {
    KnowledgeGraphCollection,
    KnowledgeMode,
    KnowledgeRecord,
    KnowledgeRelation,
    KnowledgeScope,
    KnowledgeVisualType,
    RawKnowledgeItem,
    RawKnowledgeNodeValue,
} from "../view_models/knowledge-view-model.ts";

/**
 * Immutable context required while translating an API payload into presentation
 * records. Keeping this context explicit makes normalization independent from the
 * Web Component lifecycle and prevents the normalizer from reading DOM state.
 */
export interface KnowledgeGraphNormalizationContext {
    /**
     * Active query mode, used to retain only the requested visual node kinds.
     * @type {KnowledgeMode}
     */
    mode: KnowledgeMode;
    /**
     * Active knowledge scope, used when a payload omits its own scope metadata.
     * @type {KnowledgeScope}
     */
    scope: KnowledgeScope;
    /**
     * Stable identifier factory shared with the graph projection layer.
     * @param {string} domain The high-level category or namespace of the node.
     * @param {string} label The descriptive name or type assigned to the node.
     * @param {number | undefined} index An optional numeric suffix used to differentiate multiple nodes with identical domains and labels.
     * @returns {string} A formatted string representing the unique identifier of the node.
     */
    nodeId(domain: string, label: string, index?: number): string;
}

/**
 * Converts loosely shaped knowledge API payloads into the strongly typed records
 * consumed by the presentation graph. The class owns payload interpretation only;
 * it never lays out nodes, renders markup, or mutates component state.
 */
export class KnowledgeGraphNormalizer {
    /**
     * Holds the immutable normalization context required for processing the knowledge graph.
     *
     * @type {KnowledgeGraphNormalizationContext}
     */
    readonly #context: KnowledgeGraphNormalizationContext;

    /**
     * Create a payload normalizer for one component-state snapshot.
     *
     * @param {KnowledgeGraphNormalizationContext} context Query mode, scope, and stable identifier contract.
     */
    constructor(context: KnowledgeGraphNormalizationContext) {
        this.#context = context;
    }

    /**
     * Convert an unknown command payload into normalized node and relation records.
     * Unsupported values are represented by empty collections, while malformed
     * relations are omitted rather than leaking partial edge contracts downstream.
     *
     * @param {unknown} data Untrusted data returned by the API facade.
     * @returns {KnowledgeGraphCollection} Fully typed node and relation collections.
     */
    collect(data: unknown): KnowledgeGraphCollection {
        const relations = this.#relationDataArray(data)
            .map((item, index) => this.#relationFromItem(item, index))
            .filter((relation): relation is KnowledgeRelation => relation !== null);
        const records = this.#nodeDataArray(data)
            .map((item, index) => this.#recordFromItem(item, index))
            .filter(record => Boolean(record.label));
        return { records, relations };
    }

    /**
     * Resolve payload arrays that represent visible nodes for the active mode.
     * @param {unknown} data The raw input data, which may be an array or an object containing knowledge items, to be normalized into node values.
     * @returns {RawKnowledgeNodeValue[]} An array of RawKnowledgeNodeValue objects extracted and typed from the input data.
     */
    #nodeDataArray(data: unknown): RawKnowledgeNodeValue[] {
        if (Array.isArray(data)) {
            return this.#withVisualType(data, this.#context.mode === "classes" ? "class" : "entity");
        }
        if (!isRawKnowledgeItem(data)) return [];
        if (this.#context.mode === "all") {
            const combined = [
                ...this.#withVisualType(data.entities || data.nodes || [], "entity"),
                ...this.#withVisualType(data.classes || [], "class"),
                ...this.#withVisualType(data.results || data.matches || [], "entity"),
            ];
            if (combined.length) return combined;
        }
        if (this.#context.mode === "classes" && Array.isArray(data.classes)) {
            return this.#withVisualType(data.classes, "class");
        }
        for (const key of ["entities", "nodes", "results", "matches"] as const) {
            const values = data[key];
            if (!Array.isArray(values)) continue;
            const filtered = this.#context.mode === "entities"
                ? values.filter(item => !this.#looksLikeClass(item))
                : values;
            return this.#withVisualType(filtered, "entity");
        }
        return Object.values(data)
            .filter(Array.isArray)
            .flat()
            .filter(item => !this.#looksLikeRelation(item))
            .flatMap(item => this.#withVisualType([item], this.#looksLikeClass(item) ? "class" : "entity"));
    }

    /**
     * Copy UI-only visual metadata onto object records without mutating API data.
     *
     * @param {unknown} items Candidate node values.
     * @param {KnowledgeVisualType} visualType Visual category assigned to accepted values.
     * @returns {RawKnowledgeNodeValue[]} String or object node values carrying a valid presentation shape.
     */
    #withVisualType(items: unknown, visualType: KnowledgeVisualType): RawKnowledgeNodeValue[] {
        if (!Array.isArray(items)) return [];
        return items
            .map((item: unknown) => isRawKnowledgeItem(item) ? { ...item, __visualType: visualType } : item)
            .filter((item): item is RawKnowledgeNodeValue => typeof item === "string" || isRawKnowledgeItem(item));
    }

    /**
     * Resolve payload arrays that represent graph relations.
     * @param {unknown} data The raw input object or value to be scanned for relation-like data structures.
     * @returns {RawKnowledgeItem[]} An array of validated RawKnowledgeItem objects extracted from the input.
     */
    #relationDataArray(data: unknown): RawKnowledgeItem[] {
        if (!isRawKnowledgeItem(data)) return [];
        for (const key of ["relations", "edges", "links"] as const) {
            if (Array.isArray(data[key])) return rawKnowledgeItems(data[key]);
        }
        return Object.values(data)
            .filter(Array.isArray)
            .flat()
            .filter(isRawKnowledgeItem)
            .filter(item => this.#looksLikeRelation(item));
    }

    /**
     * Convert one accepted node value into the complete graph-record contract.
     * @param {RawKnowledgeNodeValue} item The raw knowledge node data to be normalized.
     * @param {number} index The positional index of the item used for label generation and fallback ID creation.
     * @returns {KnowledgeRecord} A normalized KnowledgeRecord containing standardized identity, classification, and source metadata.
     */
    #recordFromItem(item: RawKnowledgeNodeValue, index: number): KnowledgeRecord {
        const raw: RawKnowledgeItem = isRawKnowledgeItem(item) ? item : { label: item };
        const label = this.#itemLabel(item, index);
        const sourcePath = String(raw.source_path || raw.path || raw.source || "");
        const domain = this.#domainFromRecord(raw, sourcePath);
        const entityId = raw.entity_id ?? raw.id ?? "";
        return {
            id: String(entityId || this.#context.nodeId(domain, label, index)),
            label,
            kind: "node",
            visualType: this.#looksLikeClass(raw) || raw.__visualType === "class" ? "class" : "entity",
            context: this.#contextFromRecord(raw, sourcePath),
            classHint: String(raw.entity_class || raw.class || raw.type || raw.kind || ""),
            domain,
            entityId: String(entityId),
            knowledgeScope: String(raw.knowledge_scope || this.#context.scope || "global"),
            source: sourcePath || String(raw.source_type || raw.source_title || "knowledge"),
            description: String(raw.description || raw.excerpt || raw.text || ""),
            confidence: raw.confidence ?? raw.score ?? "",
            raw,
        };
    }

    /**
     * Convert one relation object into an edge record with stable endpoint ids.
     * @param {RawKnowledgeItem} item The raw data record containing potential relation properties and metadata.
     * @param {number} index The zero-based position of the item used to generate fallback labels and unique identifiers.
     * @returns {KnowledgeRelation | null} A KnowledgeRelation object containing normalized identifiers, labels, and scope, or null if the transformation fails.
     */
    #relationFromItem(item: RawKnowledgeItem, index: number): KnowledgeRelation | null {
        const sourcePath = String(item.source_path || item.path || item.source_file || item.source || "");
        const domain = this.#domainFromRecord(item, sourcePath);
        const fromLabel = String(item.subject_name || item.source_name || item.source_label || item.subject || item.from || item.head || item.source || item.entity || `Origen ${index + 1}`);
        const toLabel = String(item.object_name || item.target_name || item.target_label || item.object || item.to || item.tail || item.target || item.related || `Destino ${index + 1}`);
        const label = String(item.relation || item.predicate || item.label || item.type || item.kind || "relation");
        const fromEntityId = item.subject_entity_id ?? item.source_entity_id ?? item.from_entity_id ?? item.head_entity_id ?? "";
        const toEntityId = item.object_entity_id ?? item.target_entity_id ?? item.to_entity_id ?? item.tail_entity_id ?? "";
        return {
            id: String(item.id || `relation:${domain}:${fromLabel}:${label}:${toLabel}:${index}`),
            kind: "relation",
            label,
            fromLabel,
            toLabel,
            from: String(fromEntityId || this.#context.nodeId(domain, fromLabel)),
            to: String(toEntityId || this.#context.nodeId(domain, toLabel)),
            fromEntityId: String(fromEntityId),
            toEntityId: String(toEntityId),
            knowledgeScope: String(item.knowledge_scope || this.#context.scope || "global"),
            fromClass: String(item.subject_class || item.source_class || item.from_class || ""),
            toClass: String(item.object_class || item.target_class || item.to_class || ""),
            domain,
            context: this.#contextFromRecord(item, sourcePath),
            source: sourcePath || String(item.source_type || item.source_title || "knowledge"),
            description: String(item.description || item.excerpt || item.text || ""),
            confidence: item.confidence ?? item.score ?? "",
            raw: item,
        };
    }

    /**
     * Return whether a raw value contains a recognized endpoint pair.
     * @param {unknown} item The unknown value to be validated as a relational knowledge item.
     * @returns {boolean} A type guard boolean indicating whether the item conforms to the RawKnowledgeItem structure and contains relational property pairs.
     */
    #looksLikeRelation(item: unknown): item is RawKnowledgeItem {
        return isRawKnowledgeItem(item) && (
            ("subject" in item && "object" in item)
            || ("source" in item && "target" in item)
            || ("from" in item && "to" in item)
            || ("head" in item && "tail" in item)
        );
    }

    /**
     * Return whether node metadata identifies a class rather than an entity.
     * @param {unknown} item The raw knowledge item to evaluate for class-like characteristics.
     * @returns {boolean} True if the item is identified as a class, otherwise false.
     */
    #looksLikeClass(item: unknown): boolean {
        if (!isRawKnowledgeItem(item)) return false;
        const marker = String(item.entity_type || item.node_type || item.type || item.kind || item.category || item.entity_class || item.class || "").toLowerCase();
        const identifier = String(item.entity_id || item.id || "").toLowerCase();
        return marker === "cls" || marker === "class" || marker === "clase" || /^cls[:_-]/.test(identifier);
    }

    /**
     * Resolve the preferred human-readable label for one node value.
     * @param {RawKnowledgeNodeValue} item The raw knowledge node value to be labeled, provided as either a string or an object containing identity properties.
     * @param {number} index The zero-based position of the item used to generate a fallback label.
     * @returns {string} The resolved string label derived from the node's metadata or its sequence index.
     */
    #itemLabel(item: RawKnowledgeNodeValue, index: number): string {
        if (typeof item === "string") return item;
        return String(item.canonical_name || item.name || item.title || item.entity || item.id || `Node ${index + 1}`);
    }

    /**
     * Derive a source-context label from path or record metadata.
     * @param {RawKnowledgeItem} item The raw knowledge record containing fallback metadata such as source type, domain, or kind.
     * @param {string} sourcePath The hierarchical path string used to extract the specific memory or knowledge context.
     * @returns {string} A string representing the resolved context, defaulting to 'knowledge' if no specific path or metadata is found.
     */
    #contextFromRecord(item: RawKnowledgeItem, sourcePath: string): string {
        if (sourcePath.includes("/")) {
            const parts = sourcePath.split("/").filter(Boolean);
            const memoryIndex = parts.indexOf("memory");
            if (memoryIndex >= 0) return parts.slice(memoryIndex, -1).join("/") || "memory";
            return parts.slice(0, -1).join("/") || parts[0] || "knowledge";
        }
        return String(item.source_type || item.domain || item.kind || "knowledge");
    }

    /**
     * Derive the canonical dotted domain from path or record metadata.
     * @param {RawKnowledgeItem} item The raw knowledge item containing potential fallback domain identifiers.
     * @param {string} sourcePath The file system or resource path used to derive the domain hierarchy.
     * @returns {string} The resolved domain string, defaulting to 'knowledge' or 'memory' if no specific domain is identified.
     */
    #domainFromRecord(item: RawKnowledgeItem, sourcePath: string): string {
        const normalizedPath = sourcePath.replaceAll("\\", "/");
        if (normalizedPath.includes("/")) {
            const parts = normalizedPath.split("/").filter(Boolean);
            const memoryIndex = parts.indexOf("memory");
            if (memoryIndex >= 0 && parts[memoryIndex + 1]) {
                const domainParts = parts.slice(memoryIndex + 1);
                const leafIndex = domainParts.length - 1;
                domainParts[leafIndex] = domainParts[leafIndex]?.replace(/\.[^.]+$/, "") || "";
                return domainParts.filter(Boolean).join(".") || "memory";
            }
            return parts[0] || "knowledge";
        }
        return String(item.domain || item.source_domain || item.source_type || "knowledge");
    }
}
