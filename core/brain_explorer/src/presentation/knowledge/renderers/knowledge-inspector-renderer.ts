/**
 * Renders the Knowledge inspector without owning DOM lifecycle or graph state.
 *
 * The renderer preserves the layout's established HTML and action attributes while
 * isolating presentation formatting from `KnowledgeView` orchestration.
 *
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import type { AvatarMessageRecord } from "../../../application/messages/dtos/responses/messages-response.ts";
import type { PictureRecord } from "../../../application/pictures/dtos/responses/pictures-response.ts";
import { renderDescriptionCard } from "../../shared/components/description-card.ts";
import { escapeHtml } from "../../shared/utils/html.ts";
import type { KnowledgeGraphEdge, KnowledgeGraphNode, KnowledgeRankedNode } from "../view_models/knowledge-view-model.ts";

/**
 * Graph state and source resolvers required to render the Knowledge inspector.
 */
export interface KnowledgeInspectorRenderInput {
    /**
     * Currently projected graph nodes.
     * @type {readonly KnowledgeGraphNode[]}
     */
    readonly nodes: readonly KnowledgeGraphNode[];
    /**
     * Currently projected graph edges.
     * @type {readonly KnowledgeGraphEdge[]}
     */
    readonly edges: readonly KnowledgeGraphEdge[];
    /**
     * Identifier of the persistently selected node.
     * @type {string}
     */
    readonly selectedNodeId: string;
    /**
     * Identifier of the persistently selected relation.
     * @type {string}
     */
    readonly selectedRelationId: string;
    /**
     * Highest-connectivity nodes available as inspector shortcuts.
     * @type {readonly KnowledgeRankedNode[]}
     */
    readonly importantNodes: readonly KnowledgeRankedNode[];
    /**
     * Resolves a picture source associated with one node.
     * @type {(node: KnowledgeGraphNode) => PictureRecord | null}
     */
    readonly pictureForNode: (node: KnowledgeGraphNode) => PictureRecord | null;
    /**
     * Resolves a persisted avatar message associated with one node.
     * @type {(node: KnowledgeGraphNode) => AvatarMessageRecord | null}
     */
    readonly messageForNode: (node: KnowledgeGraphNode) => AvatarMessageRecord | null;
    /**
     * Returns whether a node represents semantic image-analysis metadata.
     * @type {(node: KnowledgeGraphNode) => boolean}
     */
    readonly isPictureTagNode: (node: KnowledgeGraphNode) => boolean;
    /**
     * Builds the browser URL used to preview one registered picture.
     * @type {(pictureId: string) => string}
     */
    readonly pictureUrl: (pictureId: string) => string;
}

/**
 * Produces inspector markup for empty, node, and relation selections.
 */
export class KnowledgeInspectorRenderer {
    /**
     * Render the inspector for the current persistent selection.
     * @param {KnowledgeInspectorRenderInput} input Graph state and source-resolution policies.
     * @returns {string} Inspector HTML preserving existing action contracts.
     */
    render(input: KnowledgeInspectorRenderInput): string {
        const selectedRelation = input.edges.find(edge => edge.id === input.selectedRelationId);
        if (selectedRelation) return this.#renderRelation(selectedRelation, input);
        const selectedNode = input.nodes.find(node => node.id === input.selectedNodeId);
        if (selectedNode) return this.#renderNode(selectedNode, input);
        return this.#renderEmpty(input);
    }

    /**
     * Render the unselected inspector and important-node shortcuts.
     * @param {KnowledgeInspectorRenderInput} input Current graph render input.
     * @returns {string} Empty-selection inspector HTML.
     */
    #renderEmpty(input: KnowledgeInspectorRenderInput): string {
        return `
            <div class="content-head">
                <strong>Inspector</strong>
                <span>${escapeHtml(String(input.nodes.length))} nodes · ${escapeHtml(String(input.edges.length))} relations</span>
            </div>
            <div class="node-inspector scroll-list">
                <p>Select a canvas node or relation. Nodes are draggable; the canvas supports pan and zoom.</p>
                <div class="source-chip-row important-node-chips" aria-label="Important entities">
                    ${input.importantNodes.map(node => `
                        <button data-action="focus-node" data-node-id="${escapeHtml(node.id)}" title="Focus ${escapeHtml(node.label)}" style="--entity-color: ${escapeHtml(node.color)}">
                            <strong>${escapeHtml(node.label)}</strong>
                            <small>${escapeHtml(String(node.degree))}</small>
                        </button>
                    `).join("")}
                </div>
            </div>
        `;
    }

    /**
     * Render one selected graph node and its source previews.
     * @param {KnowledgeGraphNode} selected Selected graph node.
     * @param {KnowledgeInspectorRenderInput} input Current graph render input.
     * @returns {string} Node inspector HTML.
     */
    #renderNode(selected: KnowledgeGraphNode, input: KnowledgeInspectorRenderInput): string {
        const picture = input.pictureForNode(selected);
        const message = input.messageForNode(selected);
        const pictureTag = input.isPictureTagNode(selected);
        return `
            <div class="content-head">
                <strong>${escapeHtml(selected.label)}</strong>
                <span>${escapeHtml(selected.domain)}</span>
            </div>
            <div class="node-inspector scroll-list">
                ${picture ? `
                    <button class="knowledge-source-preview" data-action="open-detail-source" data-route="pictures" data-picture-id="${escapeHtml(String(picture.id))}">
                        <img src="${escapeHtml(input.pictureUrl(String(picture.id)))}" alt="${escapeHtml(picture.description || picture.filename)}">
                        <span>Open in Pictures</span>
                    </button>
                ` : ""}
                ${message ? `
                    <blockquote class="knowledge-message-preview">${escapeHtml(String(message.text || ""))}</blockquote>
                    <button class="secondary-action" data-action="open-detail-source" data-route="messages" data-message-id="${escapeHtml(String(message.id))}">Open in Messages</button>
                ` : ""}
                <dl>
                    <dt>Context</dt><dd>${escapeHtml(selected.context)}</dd>
                    <dt>Domain</dt><dd>${escapeHtml(selected.domain)}</dd>
                    <dt>${pictureTag ? "Provenance" : "Source"}</dt><dd>${pictureTag
                        ? `Derived from image analysis · ${escapeHtml(selected.source)}`
                        : escapeHtml(selected.source)}</dd>
                    <dt>Suggested class</dt><dd>${escapeHtml(selected.classHint || "-")}</dd>
                    <dt>Confidence</dt><dd>${escapeHtml(String(selected.confidence || "-"))}</dd>
                </dl>
                ${renderDescriptionCard(selected.description || "", { title: picture ? "Image description" : "Entity description" })}
                ${this.#renderRelated(selected, input)}
            </div>
        `;
    }

    /**
     * Render one selected relation and its endpoint shortcuts.
     * @param {KnowledgeGraphEdge} relation Selected graph relation.
     * @param {KnowledgeInspectorRenderInput} input Current graph render input.
     * @returns {string} Relation inspector HTML.
     */
    #renderRelation(relation: KnowledgeGraphEdge, input: KnowledgeInspectorRenderInput): string {
        return `
            <div class="content-head"><strong>Relation</strong><span>${escapeHtml(relation.label)}</span></div>
            <div class="node-inspector relation-inspector scroll-list">
                <dl>
                    <dt>Name</dt><dd>${escapeHtml(relation.label)}</dd>
                    <dt>Source node</dt><dd>${escapeHtml(relation.fromLabel)}</dd>
                    <dt>Target node</dt><dd>${escapeHtml(relation.toLabel)}</dd>
                    <dt>Context</dt><dd>${escapeHtml(relation.context)}</dd>
                    <dt>Domain</dt><dd>${escapeHtml(relation.domain)}</dd>
                    <dt>Source</dt><dd>${escapeHtml(relation.source)}</dd>
                    <dt>Confidence</dt><dd>${escapeHtml(String(relation.confidence || "-"))}</dd>
                </dl>
                ${renderDescriptionCard(relation.description || "Relation detected by the CLI facade.", { title: "Relation description" })}
                <div class="graph-list">
                    ${[relation.from, relation.to].map(nodeId => {
                        const node = input.nodes.find(item => item.id === nodeId);
                        return node ? `
                            <button class="graph-list-item" data-action="select-node" data-node-id="${escapeHtml(node.id)}">
                                <span class="activity-dot" style="background: ${escapeHtml(node.color)}"></span>
                                <strong>${escapeHtml(node.label)}</strong>
                            </button>
                        ` : "";
                    }).join("")}
                </div>
            </div>
        `;
    }

    /**
     * Render visible relations connected to one selected node.
     * @param {KnowledgeGraphNode} selected Selected graph node.
     * @param {KnowledgeInspectorRenderInput} input Current graph render input.
     * @returns {string} Related-relation list HTML, or an empty string when isolated.
     */
    #renderRelated(selected: KnowledgeGraphNode, input: KnowledgeInspectorRenderInput): string {
        const related = input.edges.filter(edge => edge.from === selected.id || edge.to === selected.id).slice(0, 10);
        if (!related.length) return "";
        return `
            <h2>Visible relations</h2>
            <div class="graph-list">
                ${related.map(edge => {
                    const oppositeId = edge.from === selected.id ? edge.to : edge.from;
                    const opposite = input.nodes.find(node => node.id === oppositeId);
                    return opposite ? `
                        <button class="graph-list-item" data-action="select-relation" data-relation-id="${escapeHtml(edge.id)}">
                            <span class="activity-dot" style="background: ${escapeHtml(opposite.color)}"></span>
                            <strong>${escapeHtml(edge.label)} - ${escapeHtml(opposite.label)}</strong>
                        </button>
                    ` : "";
                }).join("")}
            </div>
        `;
    }
}
