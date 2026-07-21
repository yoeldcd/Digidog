/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const knowledgeViewSource = await readFile(
    new URL("../src/presentation/knowledge/layouts/knowledge-view.ts", import.meta.url),
    "utf8"
);
const knowledgeNormalizerSource = await readFile(
    new URL("../src/presentation/knowledge/normalizers/knowledge-graph-normalizer.ts", import.meta.url),
    "utf8"
);
const sourceTreeProjectorSource = await readFile(
    new URL("../src/presentation/knowledge/projectors/knowledge-source-tree-projector.ts", import.meta.url),
    "utf8"
);
const collaboratorSources = await Promise.all([
    "state/knowledge-canvas-state.ts",
    "renderers/knowledge-canvas-renderer.ts",
    "controllers/knowledge-canvas-interaction-controller.ts",
    "controllers/knowledge-tree-interaction-controller.ts",
    "renderers/knowledge-inspector-renderer.ts",
    "layout_engines/knowledge-graph-layout-engine.ts",
].map(path => readFile(new URL(`../src/presentation/knowledge/${path}`, import.meta.url), "utf8")));
const knowledgeSource = [collaboratorSources[0], knowledgeViewSource, sourceTreeProjectorSource, ...collaboratorSources.slice(1)]
    .join("\n")
    .replaceAll("this.", "this.#")
    .replace(/protected\s+async\s+/g, "async #")
    .replace(/protected\s+/g, "#");
const knowledgeProjectionSource = `${knowledgeSource}\n${sourceTreeProjectorSource}`;
const messagesSource = await readFile(
    new URL("../src/presentation/messages/layouts/messages-view.ts", import.meta.url),
    "utf8"
);
const structureTreeSource = await readFile(
    new URL("../src/presentation/shared/components/structure-tree.ts", import.meta.url),
    "utf8"
);
const viewsStyles = await readFile(new URL("../src/styles/views.css", import.meta.url), "utf8");

assert.match(knowledgeSource, /#scope(?:: KnowledgeScope)? = "all"/);
assert.match(knowledgeSource, /#selectedScopes[^\n]*\["global", "local"\]/);
assert.match(knowledgeProjectionSource, /"Global knowledge"[\s\S]*"Local knowledge"/);
assert.match(knowledgeProjectionSource, /"memory", "Global memory", memoryEntries[\s\S]*"pictures", "Pictures"/);
assert.match(knowledgeProjectionSource, /"memory", "Local memory", \[\][\s\S]*"logs", "Logs"[\s\S]*"messages", "Messages"/);
assert.match(knowledgeProjectionSource, /selectedScopes[\s\S]*\.has\(root\.scope/);
assert.match(knowledgeSource, /data-filter-kind='kg-scope'[\s\S]*change", \(\) => this\.#applyFilters\(\)/);
assert.match(knowledgeProjectionSource, /#classProjection\([\s\S]*visualType: "class"/);
assert.match(knowledgeProjectionSource, /sortKey: `\$\{\(\{ memory: 0/);
assert.match(knowledgeSource, /#treeProjection\([\s\S]*endpointIds[\s\S]*endpointLabels/);

assert.match(knowledgeSource, /this\.#api\.pictures\(/);
assert.match(knowledgeSource, /#pictureEntry\(picture[^)]*\)[\s\S]*alreadyPrefixed[\s\S]*sourcePrefixes:/);
assert.match(knowledgeSource, /branchSourcePath = String\(entry\.sourcePrefixes\?\.\[index\][\s\S]*sourcePath: branchSourcePath/);
assert.match(knowledgeSource, /folder: children\.length > 0 \|\| \(!node\.sourcePath && !node\.openRoute\)/);
assert.match(knowledgeSource, /this\.#api\.getVoiceMessages\(\{ all: "true" \}/);
assert.match(knowledgeSource, /this\.#api\.logIndex\(/);
assert.match(knowledgeSource, /detail: body/);
assert.match(knowledgeSource, /openRoute: "pictures"/);
assert.match(knowledgeSource, /openRoute: "messages"/);
assert.match(knowledgeSource, /#pictureForNode\([\s\S]*knowledge-source-preview/);
assert.match(knowledgeSource, /renderDescriptionCard\([\s\S]*title: picture \? "Image description" : "Entity description"/);
assert.match(knowledgeSource, /data-action='resolve-description-entity'[\s\S]*#focusEntityByLabel/);
assert.match(knowledgeSource, /consumeRouteTarget\?\.\("knowledge"\)[\s\S]*entityLabel/);
assert.match(knowledgeSource, /#messageForNode\([\s\S]*knowledge-message-preview/);
assert.match(messagesSource, /consumeRouteTarget\?\.\("messages"\)/);
assert.match(messagesSource, /target\.messageId[\s\S]*#expandedIds\.add/);

assert.match(knowledgeSource, /#mergeScopeRecords\(this\.#filteredRecords\(\)\)/);
assert.match(knowledgeSource, /#importantNodes\(\)[\s\S]*data-action="focus-node"/);
assert.match(knowledgeSource, /#hoveredRelationId = ""[\s\S]*#renderRelationPreview\(\)[\s\S]*#hoveredRelationId \|\| this\.#selectedRelationId/);
assert.match(knowledgeSource, /data-action='select-relation'[\s\S]*pointerenter[\s\S]*#showHoveredRelation[\s\S]*pointerleave/);
assert.match(knowledgeSource, /#showHoveredRelation\(relationId[^)]*\)[\s\S]*relationPreviewHost\.innerHTML = this\.#renderRelationPreview\(\)/);
assert.match(knowledgeSource, /data-action="navigate-relation-endpoint"[\s\S]*graph-relation-connector[\s\S]*data-action="navigate-relation-endpoint"/);
assert.doesNotMatch(knowledgeSource, /graph-relation-arrow/);
assert.match(knowledgeSource, /#showHoveredEndpoint\(nodeId\)[\s\S]*#badgeHoverViewport[\s\S]*#animateCameraToNode/);
assert.match(knowledgeSource, /#showHoveredEndpoint\(nodeId\)[\s\S]*#viewportBadgeRankingFrozen = true[\s\S]*clearTimeout\(this\.#viewportInspectorTimer\)[\s\S]*#animateViewport\(previousViewport, \(\) => this\.#releaseViewportBadgeRanking\(\)\)/);
assert.match(knowledgeSource, /#releaseViewportBadgeRanking\(\)[\s\S]*#viewportBadgeRankingFrozen = false[\s\S]*#syncViewportBadgeCandidates\(\)/);
assert.match(knowledgeSource, /#syncViewportBadgeCandidates\(\)[\s\S]*if \(this\.#viewportBadgeRankingFrozen\) return;[\s\S]*if \(!this\.#viewportBadgeRankingFrozen && !this\.#selectedNodeId/);
assert.match(knowledgeSource, /#animateViewport\(target[^)]*onComplete[^)]*\)[\s\S]*onComplete\?\.\(\)/);
assert.match(knowledgeSource, /data-action='focus-node'[\s\S]*pointerenter[\s\S]*#showHoveredEndpoint[\s\S]*pointerleave[\s\S]*#focusNode/);
assert.match(knowledgeSource, /#focusNode\(nodeId[\s\S]*#focusViewport = this\.#badgeHoverViewport[\s\S]*this\.#badgeHoverViewport = null[\s\S]*this\.#hoveredNodeId = ""/);
assert.match(knowledgeSource, /#navigateRelationEndpoint\(nodeId\)[\s\S]*#badgeHoverViewport = null[\s\S]*#animateCameraToNode/);
assert.match(knowledgeSource, /#animateCameraToRelation\(relation[^)]*targetScale[^)]*\)[\s\S]*source\.x \+ target\.x[\s\S]*source\.y \+ target\.y/);
assert.match(knowledgeSource, /activeRelationId = this\.#hoveredRelationId \|\| this\.#selectedRelationId/);
assert.match(knowledgeSource, /#edgeLabelBounds = new Map(?:<[^;]+>)?\(\)[\s\S]*#drawEdgeLabel[\s\S]*#edgeLabelBounds\.set\(edge\.id/);
assert.match(knowledgeSource, /#onPointerDown\(event[^)]*canvas[^)]*\)[\s\S]*#hitTestEdgeLabel[\s\S]*#hitTestNode[\s\S]*#hitTestEdge/);
assert.match(knowledgeSource, /#nodeOwnsPoint\(node[^)]*x[^)]*y[^)]*\)[\s\S]*node\.radius \+ \(4 \/ this\.#viewport\.scale\)/);
assert.match(knowledgeSource, /#nodeLayoutFootprints\(\)[\s\S]*nodeLabelWidth[\s\S]*relationLabelWidth[\s\S]*connectivity/);
assert.match(knowledgeSource, /#positionComponent\(component[^)]*footprints[^)]*\)[\s\S]*rowsPerColumn[\s\S]*columnGap[\s\S]*layerGap/);
assert.match(knowledgeSource, /#componentBounds\(component[^)]*footprints[^)]*\)[\s\S]*footprint\.width[\s\S]*footprint\.height/);
assert.match(knowledgeSource, /#layoutDomainGrid\(nodes[^)]*footprints[^)]*\)[\s\S]*columnWidth[\s\S]*cellHeight/);
assert.match(knowledgeSource, /#fitViewport\(rect[^)]*\)[\s\S]*this\.#viewport = this\.#fittedViewport\(rect\)/);
assert.match(knowledgeSource, /#fittedViewport\(rect[^)]*\)[\s\S]*Math\.max\(0\.005,[\s\S]*\(rect\.height - 72\) \/ height[\s\S]*return \{[\s\S]*scale/);
assert.match(knowledgeSource, /#syncViewportBadgeCandidates\(\)[\s\S]*#nodeIntersectsRenderFrustum[\s\S]*#viewportNodeIds = new Set\(visibleIds\)[\s\S]*setTimeout/);
assert.match(knowledgeSource, /#importantNodes\(\)[\s\S]*#viewportBadgeSignature[\s\S]*#viewportNodeIds\.has\(node\.id\)[\s\S]*#nodeDegrees/);
assert.match(knowledgeSource, /#rankImportantNodes\(candidates\)[\s\S]*right\.degree - left\.degree[\s\S]*slice\(0, 12\)/);
assert.match(knowledgeSource, /rankedNodeIds = new Set\(this\.#rankImportantNodes\(visibleNodes\)[\s\S]*#nodeLabelIsVisible\(node, degrees, maxDegree, selected \|\| focused, ranked\)/);
assert.match(knowledgeSource, /#drawNodeLabel\(context[^)]*occupiedBounds[^)]*\)[\s\S]*context\.measureText\(label\)[\s\S]*#roundedRect/);
assert.match(knowledgeSource, /#nodeLabelBounds = new Map(?:<[^;]+>)?\(\)[\s\S]*#drawNodes\(context[^)]*\)[\s\S]*#nodeLabelBounds\.clear\(\)/);
assert.match(knowledgeSource, /#drawNodeLabel[\s\S]*#nodeLabelBounds\.set\(node\.id,[\s\S]*left:[\s\S]*bottom:/);
assert.match(knowledgeSource, /#onPointerDown[\s\S]*#hitTestNodeExpansionBadge[\s\S]*#hitTestNodeLabel[\s\S]*#hitTestEdgeLabel/);
assert.match(knowledgeSource, /#hitTestNodeLabel\(x[^)]*y[^)]*\)[\s\S]*#nodeLabelBounds\.entries\(\)[\s\S]*return this\.#nodes\.find/);
assert.match(knowledgeSource, /#rankedLabelPlacement\(node[^)]*occupiedBounds[^)]*\)[\s\S]*const candidates = \[[\s\S]*const overlaps[\s\S]*occupiedBounds\.push/);
assert.match(knowledgeSource, /#renderGraphBusyState\(\)[\s\S]*graph-busy-overlay[\s\S]*graph-busy-spinner/);
assert.match(knowledgeSource, /#beginGraphBusy\(label[^)]*\)[\s\S]*#graphBusyDepth \+= 1[\s\S]*#syncGraphBusyState/);
assert.match(knowledgeSource, /async #showRecords[\s\S]*#beginGraphBusy[\s\S]*finally[\s\S]*#endGraphBusy/);
assert.match(knowledgeSource, /async #applyFilters\(\)[\s\S]*#waitForGraphPaint[\s\S]*#prepareGraph[\s\S]*finally/);
assert.match(viewsStyles, /\.graph-busy-overlay \{[\s\S]*position: absolute;[\s\S]*backdrop-filter: blur\(2px\)/);
assert.match(viewsStyles, /@keyframes graph-busy-spin/);
assert.match(knowledgeSource, /#renderRelationPreview\(\)[\s\S]*graph-relation-endpoint[\s\S]*relation\.label[\s\S]*graph-relation-endpoint/);
assert.match(knowledgeSource, /#pictureForNode\(node[^)]*\)[\s\S]*#isPictureTagNode\(node\)[\s\S]*return null/);
assert.match(knowledgeSource, /#isPictureTagNode\(node[^)]*\)[\s\S]*misc\.tag/);
assert.match(knowledgeSource, /pictureTag \? "Provenance" : "Source"[\s\S]*Derived from image analysis/);
assert.match(knowledgeSource, /data-role="relation-preview-host"/);
assert.match(viewsStyles, /\.graph-relation-preview \{[\s\S]*grid-template-columns:[\s\S]*border-radius: 10px/);
assert.match(knowledgeSource, /#selectRelation\(relationId[^)]*\)[\s\S]*#selectedRelationId = relationId[\s\S]*#animateCameraToRelation\(relation[\s\S]*#renderInspector\(\)/);
assert.match(knowledgeSource, /addEventListener\("dblclick"[\s\S]*event\.preventDefault\(\)[\s\S]*#resetVisibleGraphViewport\(\)/);
assert.match(knowledgeSource, /#resetVisibleGraphViewport\(\)[\s\S]*cancelAnimationFrame[\s\S]*#viewportBadgeRankingFrozen = true[\s\S]*#fittedViewport[\s\S]*#animateViewport\(target, \(\) => this\.#releaseViewportBadgeRanking\(\)\)/);
assert.match(knowledgeSource, /#graphRegionForNode\(nodeId[^)]*\)[\s\S]*nodeIds = new Set[\s\S]*edgeIds = new Set/);
assert.match(knowledgeSource, /#navigateGraphRegion\(nodeId[^)]*\)[\s\S]*#regionHistory\.push\(this\.#captureGraphRegionLevel\(\)\)[\s\S]*this\.#regionNodeIds = child\.nodeIds[\s\S]*#needsViewportFit = true/);
assert.match(knowledgeSource, /#hitTestNodeExpansionBadge\(point\.x, point\.y\)[\s\S]*#navigateGraphRegion\(expansionNode\.id\)/);
assert.match(knowledgeSource, /if \(selected && this\.#nodeCanExpand\(node\.id\)\)[\s\S]*#drawNodeExpansionBadge/);
assert.match(knowledgeSource, /data-action="navigate-region-back"[\s\S]*icon\("chevronLeft"\)[\s\S]*Back/);
assert.match(knowledgeSource, /#navigateBackGraphRegion\(\)[\s\S]*#regionHistory\.pop\(\)[\s\S]*previous\.graphPositions\.forEach[\s\S]*this\.#viewport = \{ \.\.\.previous\.viewport \}/);
assert.match(knowledgeSource, /const progress = Math\.max\(0, Math\.min\(1, \(now - startedAt\) \/ duration\)\)/);
assert.doesNotMatch(knowledgeSource, /#expandGraphRegion\(/);
assert.match(knowledgeSource, /relationEndpoint = selectedRelation\?\.from === node\.id \|\| selectedRelation\?\.to === node\.id/);
assert.doesNotMatch(knowledgeSource, /expandGraphRegionFromEdge/);
assert.match(knowledgeSource, /style="--entity-color: \$\{escapeHtml\(node\.color\)\}"/);
assert.match(knowledgeSource, /distance >= 4[\s\S]*this\.#dragNode/);
assert.match(knowledgeSource, /candidate && !candidate\.moved[\s\S]*#focusNode/);
assert.match(knowledgeSource, /#restoreFocusViewport\(\)[\s\S]*previousViewport/);
assert.match(knowledgeNormalizerSource, /domainParts = parts\.slice\(memoryIndex \+ 1\)[\s\S]*replace\(\/\\\.\[\^\.\]\+\$\//);
assert.match(knowledgeSource, /key === "memory"[\s\S]*entry\.segments\.slice\(0, index \+ 1\)\.join\("\."\)/);
assert.match(knowledgeSource, /#recordMatchesTreeSelection\([\s\S]*record\.domain\.startsWith\(`\$\{domain\}\.\`\)/);
assert.match(knowledgeSource, /#graphCountLabel\([\s\S]*#mergeScopeRecords[\s\S]*#edgesFromRelations[\s\S]*E: \$\{records\.length\} R: \$\{edges\.length\}/);
assert.match(knowledgeSource, /#applyTreeSelection\(\)[\s\S]*#syncDomainTreeSelection\(\)[\s\S]*#drawCanvas\(\)/);
assert.match(knowledgeSource, /#onDomainTreeSelected\(event\)[\s\S]*#applyTreeSelection\(\)/);
assert.doesNotMatch(knowledgeSource, /event\.detail\.branch && event\.detail\.clickedCaret/);
assert.match(knowledgeSource, /#domainColors = new Map(?:<[^;]+>)?\(\)[\s\S]*#usedDomainColors = new Set(?:<[^;]+>)?\(\)/);
assert.match(structureTreeSource, /node\.folder === true[\s\S]*is-empty-folder/);
assert.match(viewsStyles, /\.knowledge-filter-options \{ display: grid; grid-template-columns: minmax\(0, 1fr\);/);
assert.match(viewsStyles, /\.structure-tree \{[\s\S]*resize: none;/);
assert.match(structureTreeSource, /structure-tree-resize-handle[\s\S]*pointermove[\s\S]*TREE_WIDTH_STORAGE_KEY/);
assert.match(viewsStyles, /\.structure-tree-resize-handle \{[\s\S]*height: 100%;/);
assert.match(viewsStyles, /\.knowledge-source-preview \{[\s\S]*max-width: 100%;[\s\S]*overflow: hidden;/);
assert.match(viewsStyles, /\.knowledge-canvas-layout \{[\s\S]*grid-template-columns: minmax\(0, 1fr\) minmax\(250px, clamp\(250px, 28%, 420px\)\)[\s\S]*max-width: 100%/);
assert.match(viewsStyles, /@media \(max-width: 820px\)[\s\S]*\.knowledge-canvas-layout \{[\s\S]*grid-template-columns: minmax\(0, 1fr\)[\s\S]*grid-template-rows:/);
assert.match(viewsStyles, /@media \(max-width: 820px\)[\s\S]*\.graph-toolbar \{[\s\S]*grid-template-columns: minmax\(0, 1fr\) 38px 38px/);
assert.match(viewsStyles, /\.graph-detail-list > \*[\s\S]*max-width: 100%/);
assert.match(viewsStyles, /\.important-node-chips \{[\s\S]*display: flex;[\s\S]*flex-wrap: wrap;[\s\S]*justify-content: space-between/);
assert.match(viewsStyles, /\.important-node-chips button \{[\s\S]*flex: 1 1 max-content;[\s\S]*justify-content: center;[\s\S]*width: auto;[\s\S]*max-width: 100%[\s\S]*text-align: center/);
assert.match(viewsStyles, /\.important-node-chips strong \{[\s\S]*overflow: visible;[\s\S]*overflow-wrap: anywhere;[\s\S]*text-overflow: clip;[\s\S]*white-space: normal;/);

console.log("knowledge graph layout contract passed");
