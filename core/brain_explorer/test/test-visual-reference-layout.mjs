/**
 * @author Yoel David <yoeldcd@gmail.com>
 * @see https://x.com/SAY6267
 */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const viewSource = await readFile(new URL("../src/presentation/backlog/layouts/backlog-view.ts", import.meta.url), "utf8");
const layoutRendererSource = await readFile(new URL("../src/presentation/backlog/renderers/backlog-layout-renderer.ts", import.meta.url), "utf8");
const editorSource = await readFile(new URL("../src/presentation/backlog/layouts/visual-reference-editor.ts", import.meta.url), "utf8");
const controllerSource = await readFile(new URL("../src/presentation/backlog/controllers/backlog-visual-reference-controller.ts", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/views.css", import.meta.url), "utf8");
const markdownSource = await readFile(new URL("../src/presentation/shared/utils/html.ts", import.meta.url), "utf8");
const logParserSource = await readFile(new URL("../src/presentation/logs/formatters/log-entry-parser.ts", import.meta.url), "utf8");
const logViewSource = await readFile(new URL("../src/presentation/logs/layouts/logs-view.ts", import.meta.url), "utf8");
const resourceRoutesSource = await readFile(new URL("../../brain/src/brain/infrastructure/explorer/routes/resource_routes.py", import.meta.url), "utf8");
const backlogRoutesSource = await readFile(new URL("../../brain/src/brain/infrastructure/explorer/routes/backlog_routes.py", import.meta.url), "utf8");

assert.match(styles, /textarea\[data-role="modal-description"\]\s*\{[^}]*font-size:\s*17px;/, "The editor textarea must use a comfortably readable 17px size.");
assert.match(styles, /\.task-viewer-markdown\s*\{[^}]*font-size:\s*17px;/, "The Markdown viewer must use a comfortably readable 17px size.");
assert.match(layoutRendererSource, /id="backlog-modal"[\s\S]*?<textarea data-role="modal-description"/, "The editor must remain a dedicated textarea dialog.");
assert.match(layoutRendererSource, /id="task-viewer-modal"[\s\S]*?data-role="task-viewer-description"/, "Reading must use a separate Markdown viewer dialog.");
assert.doesNotMatch(layoutRendererSource, /show-task-write|show-task-preview|task-editor-mode-switch/, "The editor must not contain a Write/Preview toggle.");
assert.match(layoutRendererSource, /class="task-open-viewer" data-action="view-task"/, "Clicking a task title must open the read-only viewer.");
assert.match(viewSource, /data-viewer-task-action=\"edit\"/, "Editing must remain an explicit viewer-options action.");
assert.match(viewSource, /description\.innerHTML = renderMarkdown\(viewableBacklogDescription/, "The dedicated viewer must render the task as Markdown.");
assert.doesNotMatch(viewSource, /meta\.textContent = `\$\{task\.domain\} \|/u, "Viewer metadata must not use pipe-separated text.");
assert.match(viewSource, /task-viewer-domain-badge[\s\S]*task-viewer-priority-badge[\s\S]*task-viewer-state-badge/u, "Viewer metadata must render typed icon badges.");
assert.match(layoutRendererSource, /task-editor-title-field[^>]*><span>Title<\/span>/, "The task title control must expose a visible label.");
assert.match(layoutRendererSource, /task-editor-priority-field[^>]*><span>Priority<\/span>/, "The priority control must expose a visible label.");
assert.match(layoutRendererSource, /task-editor-tool-action[^>]*>[\s\S]*?camera[\s\S]*?<span>Image<\/span>/, "Image must use the shared borderless editor-tool action.");
assert.match(layoutRendererSource, /task-editor-tool-action task-draft-enrich-action/, "Image and Enrich must share the same action treatment.");
assert.match(layoutRendererSource, /task-dialog-close[\s\S]*?data-action="close-modal"/, "The editor titlebar must use the icon-only close control.");
assert.match(layoutRendererSource, /task-dialog-close[\s\S]*?data-action="close-task-viewer"/, "The viewer titlebar must use the icon-only close control.");
assert.match(layoutRendererSource, /task-viewer-footer[\s\S]*?<summary class="ghost-action task-footer-action"[\s\S]*?<span>Options<\/span>[\s\S]*?data-action="close-task-viewer"/, "The viewer footer must place the textual Options button beside Close.");
assert.match(viewSource, /data-viewer-task-status[\s\S]*?data-viewer-task-action=\"edit\"[\s\S]*?data-viewer-task-action=\"delete\"/, "Viewer Options must expose edit, state, and delete actions.");
assert.match(layoutRendererSource, /task-editor-header[\s\S]*?task-editor-status-indicator[\s\S]*?task-editor-heading[\s\S]*?data-action="close-modal"/, "Editor status must precede its task title.");
assert.match(layoutRendererSource, /task-viewer-header[\s\S]*?task-viewer-status-indicator[\s\S]*?task-viewer-heading[\s\S]*?data-action="close-task-viewer"/, "Viewer status must precede its title and badges.");
assert.match(styles, /task-(?:editor|viewer)-status-indicator\s*\{[^}]*width:\s*32px;[^}]*height:\s*32px;/s, "Both modal indicators must match the 32px task-row status size.");
assert.match(layoutRendererSource, /task-footer-action[^>]*>[\s\S]*?\$\{icon\("(?:close|save|edit)"\)\}[\s\S]*?<span/, "Footer actions must render icons before their labels.");
assert.match(styles, /\.task-dialog-close\s*\{[^}]*border:\s*0 !important;[^}]*background:\s*transparent !important;/s, "Titlebar close controls must have no border or background.");
assert.match(styles, /\.task-editor-field\s*\{[^}]*border-bottom:\s*1px solid var\(--border-strong\)/s, "Editor fields must use the searchbar underline treatment.");

assert.doesNotMatch(
    controllerSource,
    /imgUploadZone\.style\.display\s*=\s*["']grid["']/,
    "The visual-reference controller must not override its flex layout with an inline grid."
);
assert.match(
    controllerSource,
    /fileInput\.disabled\s*=\s*hasImage/,
    "The native file chooser must be disabled while an image is loaded."
);
assert.match(
    viewSource,
    /previewArea\.classList\.contains\(["']has-image["']\)\s*\|\|\s*fileInput\?\.disabled/,
    "Loaded canvas clicks must never invoke the native file chooser."
);
assert.match(
    styles,
    /\.visual-reference-upload\s*\{[^}]*display:\s*flex;[^}]*height:\s*100%;/s,
    "The upload region must consume the full available dialog height."
);
assert.match(
    styles,
    /\.image-preview-area\s*\{[^}]*flex:\s*1 1 0;[^}]*height:\s*100%;/s,
    "The empty dropzone must fill the remaining upload region."
);
assert.match(
    styles,
    /\.marking-container\s*\{[^}]*flex:\s*1 1 0;[^}]*width:\s*100%;/s,
    "The marking canvas must consume only the space remaining above the toolbar."
);
assert.match(
    styles,
    /\.marking-container\s*>\s*canvas\s*\{[^}]*max-width:\s*100%;[^}]*max-height:\s*100%;[^}]*width:\s*auto;[^}]*height:\s*auto;/s,
    "The natural-ratio canvas must fit the editor without stretching."
);
assert.match(editorSource, /<canvas data-role="marking-canvas"/, "The editor must use one canvas for image and mark rendering.");
assert.doesNotMatch(editorSource, /id="marking-svg"/, "A separate SVG overlay must not introduce a second coordinate system.");
assert.match(
    editorSource,
    /this\.#renderCanvas\(false\)[\s\S]*canvas\.toDataURL\("image\/png"\)/,
    "Export must use the same canvas renderer as the interactive preview."
);
assert.match(
    viewSource,
    /reader\.onload\s*=\s*\(\)\s*=>\s*\{[\s\S]*visualReferenceDialog\.showModal\(\);[\s\S]*const result = reader\.result;[\s\S]*typeof result !== "string"[\s\S]*this\.#visualReferenceController\.displayImage\(result\)/,
    "Pasting an image into the task description must open the marking editor with that image loaded."
);

const toolbarStart = editorSource.indexOf('<div class="marking-toolbar">');
const toolbarEnd = editorSource.indexOf("</div>", toolbarStart);
const toolbarMarkup = editorSource.slice(toolbarStart, toolbarEnd);
const toolbarActions = [
    "change-mark-color",
    "delete-selected-mark",
    "change-mark-shape",
    "change-mark-label"
];
assert.ok(toolbarStart >= 0, "The marking toolbar must exist.");
assert.deepEqual(
    toolbarActions.map(action => toolbarMarkup.indexOf(action)).every((position, index, positions) => position >= 0 && (index === 0 || position > positions[index - 1])),
    true,
    "Mark controls must be ordered as color, delete, shape, then label."
);
assert.match(editorSource, /<option value="label">LABEL<\/option>/, "LABEL must be an independent marking tool.");
assert.match(controllerSource, /fileInput\.disabled\s*=\s*hasImage/, "The native file chooser must remain disabled while editing marks.");
assert.match(editorSource, /filter\(mark\s*=>\s*mark\.type\s*!==\s*"label"\)/, "Standalone labels must not consume geometric mark numbers.");
assert.match(editorSource, /selected\?\.type\s*!==\s*"label"/, "The label field may edit only a selected LABEL mark.");
assert.doesNotMatch(editorSource, /data-action="clear-marks"/, "The editor must not expose destructive clear-all behavior.");
assert.match(styles, /\.mark-delete-control:not\(:disabled\):hover\s*\{[^}]*color:\s*var\(--danger\)/s, "The enabled delete icon must use the red hover treatment.");
assert.match(styles, /\.marking-toolbar\s*\{[^}]*grid-template-columns:\s*auto auto minmax\(130px, 180px\) minmax\(180px, 1fr\)/s, "The label control must receive the remaining toolbar space.");

assert.doesNotMatch(layoutRendererSource, /modal-reference-preview/, "The task modal must not render a detached reference toolbar block.");
assert.match(viewSource, /const imageMarkdown = `!\[Task visual reference\][\s\S]*?replaceAll\("\{ref_image\}", imageMarkdown\)/, "The viewer must render the image at the ref_image token position.");
assert.match(viewSource, /: `\$\{imageMarkdown\}\\n\\n\$\{editable\}`/, "Legacy tasks with an asset but no textual token must place the image above the narrative.");
assert.match(layoutRendererSource, /const imageUrl = workspaceScopedUrl\(`\/api\/backlog\/image\?taskId=/, "Rows must construct a workspace-scoped backlog image URL.");
assert.match(layoutRendererSource, /class="task-reference-thumbnail"/, "Rows whose task id exists in the image inventory must expose a functional thumbnail.");
assert.match(viewSource, /!editableDescription\.includes\("\{ref_image\}"\)[\s\S]*?\{ref_image\}/, "Legacy assets without a description reference must regain an editable placeholder.");
assert.match(viewSource, /editableBacklogDescription\(task\.description, task\.id\)/, "Persisted image paths must return to the editable ref_image token.");
assert.match(markdownSource, /safeMarkdownImageUrl\(target\)/, "Markdown images must be protected before narrative closure highlighting.");
assert.match(markdownSource, /\/api\/workspace\/image\?path=/, "Workspace-relative image labels must use the validated image endpoint.");
assert.match(resourceRoutesSource, /def _handle_workspace_image\(/, "The backend must serve validated workspace-relative images.");
assert.match(backlogRoutesSource, /def _save_backlog_image\([\s\S]*?base64\.b64decode[\s\S]*?write_bytes\(image_bytes\)[\s\S]*?def _find_backlog_image\(/, "Backlog image decoding and writing must remain owned by _save_backlog_image before the lookup method begins.");
assert.doesNotMatch(logParserSource, /pictureReferences\(/, "Logs must not discover task-owned image references.");
assert.doesNotMatch(logViewSource, /(?:log-entry-preview|\/api\/(?:logs|workspace)\/image)/, "Logs must not request task-owned images.");
assert.match(styles, /\.task-row:hover\s*\{[^}]*background:\s*var\(--surface-hover\)/s, "The complete task row must use one contrasting hover surface.");
assert.match(styles, /\.task-row:hover\s*>\s*\.task-open-viewer[\s\S]*?background:\s*transparent/s, "The nested title button must not paint a second hover layer.");

assert.match(styles, /input\[data-role="modal-title-input"\],[\s\S]*?select\[data-role="modal-priority"\][\s\S]*?border:\s*0 !important;[\s\S]*?border-radius:\s*0 !important;[\s\S]*?outline:\s*0 !important;/, "Task editor controls must use minifier-safe direct selectors and expose only the bottom line.");
assert.match(styles, /\.task-editor-toolbar \{[\s\S]*?z-index:\s*121;[\s\S]*?background:\s*var\(--surface\);/, "The toolbar and Pause control must remain visually above the content enrichment overlay.");
assert.match(viewSource, /\[data-action='open-visual-reference'\], \[data-action='close-modal'\], \[data-role='modal-submit-btn'\]/, "Draft enrichment must disable Image, editor close actions, and Save while preserving Pause.");
assert.match(styles, /\.task-viewer-options > summary \{[^}]*border-color:\s*transparent;[^}]*background:\s*transparent;[^}]*box-shadow:\s*none;/s, "Viewer Options must reuse the flat Cancel-button treatment without a box.");

console.log("visual reference layout contract passed");
