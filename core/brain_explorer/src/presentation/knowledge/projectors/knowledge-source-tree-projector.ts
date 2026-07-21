/**
 * Projects Knowledge persistence sources into the shared structure-tree contract.
 *
 * The projector owns source-specific hierarchy construction while the Knowledge layout
 * remains responsible for selection, navigation, and asynchronous data acquisition.
 *
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import type { LogEntryPayload } from "../../../application/logs/dtos/responses/logs-response.ts";
import type { AvatarMessageRecord, AvatarMessageSession } from "../../../application/messages/dtos/responses/messages-response.ts";
import type { PictureRecord } from "../../../application/pictures/dtos/responses/pictures-response.ts";
import type { IconName } from "../../shared/utils/icons.ts";
import type { StructureTreeAction } from "../../shared/view_models/structure-tree-view-model.ts";
import { shortKnowledgeLabel } from "../formatters/knowledge-graph-formatter.ts";
import type {
    KnowledgeScope,
    KnowledgeSourceEntry,
    KnowledgeSourceKind,
    KnowledgeSourceTreeAccumulator,
    KnowledgeTreeNode,
    KnowledgeVisualType,
} from "../view_models/knowledge-view-model.ts";

/**
 * Supplies the records and presentation policies required to project a source tree.
 */
export interface KnowledgeSourceTreeProjectionInput {
    /**
     * Physical Knowledge scopes currently enabled by the user.
     * @type {ReadonlySet<"global" | "local">}
     */
    readonly selectedScopes: ReadonlySet<Exclude<KnowledgeScope, "all">>;
    /**
     * Canonical global-memory dotted paths returned by the memory index.
     * @type {readonly string[]}
     */
    readonly memoryPaths: readonly string[];
    /**
     * Registered picture records exposed beneath the global source root.
     * @type {readonly PictureRecord[]}
     */
    readonly pictures: readonly PictureRecord[];
    /**
     * Persisted avatar messages exposed beneath local message sessions.
     * @type {readonly AvatarMessageRecord[]}
     */
    readonly messages: readonly AvatarMessageRecord[];
    /**
     * Session metadata used to group persisted avatar messages.
     * @type {readonly AvatarMessageSession[]}
     */
    readonly messageSessions: readonly AvatarMessageSession[];
    /**
     * Local log-index records exposed beneath their canonical domains.
     * @type {readonly LogEntryPayload[]}
     */
    readonly logEntries: readonly LogEntryPayload[];
    /**
     * Returns the visible graph count for one tree projection.
     * @type {(domain: string, scope: KnowledgeScope, sourceKind?: KnowledgeSourceKind | "", sourcePath?: string, visualType?: KnowledgeVisualType | "") => string}
     */
    readonly graphCountLabel: (
        domain: string,
        scope: KnowledgeScope,
        sourceKind?: KnowledgeSourceKind | "",
        sourcePath?: string,
        visualType?: KnowledgeVisualType | "",
    ) => string;
    /**
     * Assigns the stable graph color associated with one canonical tree path.
     * @type {(domain: string) => string}
     */
    readonly domainColor: (domain: string) => string;
}

/**
 * Builds the complete global/local source hierarchy consumed by `StructureTree`.
 */
export class KnowledgeSourceTreeProjector {
    /**
     * Project enabled physical scopes into shared tree nodes.
     *
     * @param {KnowledgeSourceTreeProjectionInput} input Source records and graph presentation policies.
     * @returns {KnowledgeTreeNode[]} Root nodes ordered as global then local scope.
     */
    project(input: KnowledgeSourceTreeProjectionInput): KnowledgeTreeNode[] {
        return [
            this.#scopeRoot("global", "Global knowledge", input.memoryPaths, input),
            this.#scopeRoot("local", "Local knowledge", [], input),
        ].filter(root => input.selectedScopes.has(root.scope === "global" ? "global" : "local"));
    }

    /**
     * Build one physical-scope root without hiding canonical empty sources.
     * @param {"global" | "local"} scope Physical persistence scope.
     * @param {string} label User-facing root label.
     * @param {readonly string[]} canonicalPaths Canonical memory paths owned by the scope.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode} A KnowledgeTreeNode object representing the root of the specified scope.
     */
    #scopeRoot(
        scope: Exclude<KnowledgeScope, "all">,
        label: string,
        canonicalPaths: readonly string[],
        input: KnowledgeSourceTreeProjectionInput,
    ): KnowledgeTreeNode {
        const children = scope === "global"
            ? this.#globalChildren(canonicalPaths, input)
            : this.#localChildren(input);
        return {
            id: `${scope}::all`,
            path: `${scope}::all`,
            label,
            icon: "database",
            count: input.graphCountLabel("all", scope),
            children,
            actions: [{ id: "filter-source", label: "FILTER", icon: "filter" }],
            scope,
            domain: "all",
            sourceKind: "",
            sourcePath: "",
            visualType: "",
        };
    }

    /**
     * Build source categories owned by global persistence.
     * @param {readonly string[]} canonicalPaths Canonical global-memory paths.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode[]} An array of KnowledgeTreeNode objects representing the global memory, class projections, and picture categories.
     */
    #globalChildren(
        canonicalPaths: readonly string[],
        input: KnowledgeSourceTreeProjectionInput,
    ): KnowledgeTreeNode[] {
        const leaves = new Set(canonicalPaths.filter(path => !canonicalPaths.some(candidate => candidate.startsWith(`${path}.`))));
        const memoryEntries = canonicalPaths.map(path => ({
            segments: this.#domainParts(path),
            domain: path,
            sourcePath: leaves.has(path) ? `memory/${path.replaceAll(".", "/")}.md` : "",
        }));
        const pictureEntries = input.pictures.map(picture => this.#pictureEntry(picture));
        return [
            this.#sourceCategory("global", "memory", "Global memory", memoryEntries, "database", input),
            this.#classProjection("global", input),
            this.#sourceCategory("global", "pictures", "Pictures", pictureEntries, "camera", input),
        ];
    }

    /**
     * Build source categories owned by local workspace persistence.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode[]} An array of KnowledgeTreeNode objects representing the local source hierarchy.
     */
    #localChildren(input: KnowledgeSourceTreeProjectionInput): KnowledgeTreeNode[] {
        return [
            this.#sourceCategory("local", "memory", "Local memory", [], "database", input),
            this.#classProjection("local", input),
            this.#sourceCategory("local", "logs", "Logs", this.#logEntries(input.logEntries), "document", input),
            this.#sourceCategory("local", "messages", "Messages", this.#messageEntries(input), "messageCircle", input),
        ];
    }

    /**
     * Build one canonical picture entry without duplicating its domain prefix.
     * @param {PictureRecord} picture Picture registry record to project.
     *
     * @returns {KnowledgeSourceEntry} A knowledge source entry object containing the resolved path segments, routing targets, and descriptive details.
     */
    #pictureEntry(picture: PictureRecord): KnowledgeSourceEntry {
        const sourcePath = String(picture.relative_path || picture.filename || "").replaceAll("\\", "/");
        const sourceSegments = sourcePath.split("/").filter(Boolean);
        const domainSegments = this.#domainParts(String(picture.domain || "no-domain"));
        const alreadyPrefixed = domainSegments.every((segment, index) => (
            String(sourceSegments[index] || "").toLowerCase() === segment.toLowerCase()
        ));
        const segments = alreadyPrefixed ? sourceSegments : [...domainSegments, ...sourceSegments];
        return {
            segments,
            sourcePrefixes: segments.map((_unusedSegment, index) => segments.slice(0, index + 1).join("/")),
            domain: "pictures",
            sourcePath,
            openRoute: "pictures",
            openTarget: { pictureId: String(picture.id) },
            detail: String(picture.description || ""),
        };
    }

    /**
     * Build a canonical source category from filesystem or registry entries.
     * @param {"global" | "local"} scope Physical persistence scope.
     * @param {KnowledgeSourceKind} key Canonical source family.
     * @param {string} label User-facing category label.
     * @param {readonly KnowledgeSourceEntry[]} entries Source entries to arrange hierarchically.
     * @param {"edit" | "settings" | "home" | "database" | "graph" | "search" | "messageCircle" | "sliders" | "users" | "document" | "plus" | "documentPlus" | "folderPlus" | "copy" | "trash" | "save" | "refresh" | "pulse" | "folder" | "moon" | "sun" | "terminal" | "close" | "collapseLeft" | "expandRight" | "eye" | "filter" | "checkSquare" | "chevronRight" | "chevronLeft" | "chevronDown" | "minus" | "more" | "clock" | "camera" | "book" | "volume" | "play" | "pause" | "download"} categoryIcon Shared icon assigned to the root.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode} A KnowledgeTreeNode representing a categorized folder of knowledge sources with associated metadata and children.
     */
    #sourceCategory(
        scope: Exclude<KnowledgeScope, "all">,
        key: KnowledgeSourceKind,
        label: string,
        entries: readonly KnowledgeSourceEntry[],
        categoryIcon: IconName,
        input: KnowledgeSourceTreeProjectionInput,
    ): KnowledgeTreeNode {
        const root: KnowledgeSourceTreeAccumulator = {
            label: "",
            path: "",
            scope,
            domain: "all",
            sourceKind: key,
            sourcePath: "",
            children: new Map<string, KnowledgeSourceTreeAccumulator>(),
        };
        entries.forEach(entry => this.#appendEntry(root, scope, key, entry));
        return {
            id: `${scope}::source:${key}`,
            path: `${scope}::source:${key}`,
            label,
            icon: categoryIcon,
            count: input.graphCountLabel("all", scope, key),
            children: this.#treeNodes([...root.children.values()], input),
            actions: [{ id: "filter-source", label: "FILTER", icon: "filter" }],
            scope,
            domain: "all",
            sourceKind: key,
            folder: true,
            sortKey: `${({ memory: 0, pictures: 2, logs: 2, messages: 3 } satisfies Record<KnowledgeSourceKind, number>)[key]}:${label}`,
        };
    }

    /**
     * Append one source entry to its hierarchical accumulator.
     * @param {KnowledgeSourceTreeAccumulator} root Mutable accumulator root.
     * @param {"global" | "local"} scope Physical persistence scope.
     * @param {KnowledgeSourceKind} key Canonical source family.
     * @param {KnowledgeSourceEntry} entry Source entry to append.
     */
    #appendEntry(
        root: KnowledgeSourceTreeAccumulator,
        scope: Exclude<KnowledgeScope, "all">,
        key: KnowledgeSourceKind,
        entry: KnowledgeSourceEntry,
    ): void {
        let node = root;
        entry.segments.forEach((part, index) => {
            const terminal = index === entry.segments.length - 1;
            const branchSourcePath = String(entry.sourcePrefixes?.[index] || "");
            const baseId = `${scope}::source:${key}/${entry.segments.slice(0, index + 1).join("/")}`;
            const id = terminal && entry.sourcePath ? `${baseId}::${entry.sourcePath}` : baseId;
            const childKey = terminal && entry.sourcePath ? `${part}::${entry.sourcePath}` : part;
            const branchDomain = key === "memory" ? entry.segments.slice(0, index + 1).join(".") : entry.domain;
            if (!node.children.has(childKey)) {
                node.children.set(childKey, {
                    label: part,
                    path: id,
                    scope,
                    domain: branchDomain,
                    sourceKind: key,
                    sourcePath: branchSourcePath,
                    children: new Map(),
                });
            }
            const child = node.children.get(childKey);
            if (!child) throw new Error(`Unable to create Knowledge source node: ${id}`);
            node = child;
            if (key === "memory") node.domain = branchDomain;
            if (terminal) Object.assign(node, entry);
        });
    }

    /**
     * Build a non-owning class projection while retaining canonical source ownership.
     * @param {"global" | "local"} scope Physical persistence scope.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode} A KnowledgeTreeNode configured as a folder for classes with associated metadata and filter actions.
     */
    #classProjection(
        scope: Exclude<KnowledgeScope, "all">,
        input: KnowledgeSourceTreeProjectionInput,
    ): KnowledgeTreeNode {
        return {
            id: `${scope}::classes`,
            path: `${scope}::classes`,
            label: "Classes",
            icon: "graph",
            count: input.graphCountLabel("all", scope, "", "", "class"),
            children: [],
            actions: [{ id: "filter-source", label: "FILTER", icon: "filter" }],
            scope,
            domain: "all",
            sourceKind: "",
            visualType: "class",
            folder: true,
            sortKey: "1:Classes",
        };
    }

    /**
     * Project persisted messages beneath their canonical sessions.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeSourceEntry[]} An array of KnowledgeSourceEntry objects containing formatted segments, routing metadata, and message details.
     */
    #messageEntries(input: KnowledgeSourceTreeProjectionInput): KnowledgeSourceEntry[] {
        const sessions = new Map(input.messageSessions.map(session => [`${session.date}:${session.chatId}`, session]));
        return input.messages.map(message => {
            const session = sessions.get(`${message.date}:${message.chat_id}`) || null;
            const date = String(session?.date || message.created_at || "no-date").slice(0, 10);
            const sessionLabel = String(session?.label || session?.chatId || message.chat_id || "session");
            const body = String(message.text || "Message has no body");
            return {
                segments: [...date.split("-"), sessionLabel, shortKnowledgeLabel(body.replace(/\s+/g, " "), 54)],
                domain: "messages",
                sourcePath: `messages/${message.id}`,
                openRoute: "messages",
                openTarget: { messageId: String(message.id), sessionId: String(session?.id || "") },
                detail: body,
            };
        });
    }

    /**
     * Project persisted log-index entries as canonical local sources.
     * @param {readonly LogEntryPayload[]} entries Log-index records to project.
     *
     * @returns {KnowledgeSourceEntry[]} An array of KnowledgeSourceEntry objects containing calculated segments, source paths, and routing targets.
     */
    #logEntries(entries: readonly LogEntryPayload[]): KnowledgeSourceEntry[] {
        return entries.map((entry, index) => {
            const domain = String(entry.domain || "logs");
            const timestamp = String(entry.timestamp || "");
            const [date = "", ...timeParts] = timestamp.split(" ");
            return {
                segments: [...this.#domainParts(domain), String(entry.title || timestamp || `log-${index + 1}`)],
                domain: "logs",
                sourcePath: `logs/${domain}/${timestamp || "undated"}/${index}`,
                openRoute: "logs",
                openTarget: { domain, date, time: timeParts.join(" ") },
                detail: String(entry.title || ""),
            };
        });
    }

    /**
     * Convert accumulated source branches into shared tree nodes.
     * @param {readonly KnowledgeSourceTreeAccumulator[]} nodes Accumulated source branches.
     * @param {KnowledgeSourceTreeProjectionInput} input Complete projection input.
     *
     * @returns {KnowledgeTreeNode[]} A sorted array of KnowledgeTreeNode objects representing the projected hierarchy.
     */
    #treeNodes(
        nodes: readonly KnowledgeSourceTreeAccumulator[],
        input: KnowledgeSourceTreeProjectionInput,
    ): KnowledgeTreeNode[] {
        return nodes.map(node => {
            const children = this.#treeNodes([...node.children.values()], input);
            const actions: StructureTreeAction[] = [
                { id: "consolidate-source", label: "CONSOLIDATE", icon: "graph" },
                { id: "filter-source", label: "FILTER", icon: "filter" },
                ...(node.openRoute ? [{ id: "open-source", label: "OPEN", icon: "chevronRight" } satisfies StructureTreeAction] : []),
            ];
            return {
                id: node.path,
                path: node.path,
                label: node.label,
                color: input.domainColor(node.path),
                count: input.graphCountLabel(node.domain, node.scope, node.sourceKind, node.sourcePath || ""),
                children,
                actions,
                scope: node.scope,
                domain: node.domain,
                sourceKind: node.sourceKind || "",
                visualType: node.visualType ?? "",
                ...(node.sortKey === undefined ? {} : { sortKey: node.sortKey }),
                sourcePath: node.sourcePath || "",
                openRoute: node.openRoute || "",
                openTarget: node.openTarget || null,
                detail: node.detail || "",
                folder: children.length > 0 || (!node.sourcePath && !node.openRoute),
            };
        }).sort((left, right) => left.label.localeCompare(right.label));
    }

    /**
     * Split a domain into non-empty canonical path segments.
     * @param {string} domain Dotted or filesystem-like domain path.
     *
     * @returns {string[]} An array of cleaned string segments extracted from the domain.
     */
    #domainParts(domain: string): string[] {
        return domain.split(/[./\\]+/).map(part => part.trim()).filter(Boolean);
    }
}
