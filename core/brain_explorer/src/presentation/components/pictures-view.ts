/** Modern registry-backed picture browser and carousel. */

import type { ApiResponse, PictureDescriptionPayload, PictureRecord } from "../../application/contracts/api-dtos.ts";
import { escapeHtml } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";
import { renderDescriptionCard } from "./description-card.ts";
import { StructureTree } from "./structure-tree.ts";

void StructureTree;


export class PicturesView extends HTMLElement {
    static get selector() {
        return "brain-pictures-view";
    }

    #api = null;
    #state = null;
    #pictures: PictureRecord[] = [];
    #picturesByDomain = new Map<string, PictureRecord[]>();
    #domains: Record<string, number> = {};
    #domain = "";
    #domainFocused = false;
    #selectedId = "";
    #loading = false;
    #descriptionRequestPending = false;
    #descriptionEditing = false;
    #copyFeedbackTimer: ReturnType<typeof setTimeout> | null = null;
    #search = "";
    #expandedDomains = new Set<string>(["pictures:all"]);
    #imageHydrationToken = 0;
    #viewerOpen = false;
    #viewerScale = 1;
    #viewerX = 0;
    #viewerY = 0;
    #viewerPointerId: number | null = null;
    #viewerScaleTimer: ReturnType<typeof setTimeout> | null = null;
    #viewerPointerStart = { x: 0, y: 0, originX: 0, originY: 0 };
    #handleKeyDown = (event: KeyboardEvent) => {
        if (this.#viewerOpen) {
            if (event.key === "Escape") this.#closeViewer();
            if (event.key === "+" || event.key === "=") this.#zoomViewer(0.25);
            if (event.key === "-") this.#zoomViewer(-0.25);
            if (event.key === "0") this.#resetViewer();
            return;
        }
        if (event.key === "ArrowLeft") this.#selectRelative(-1);
        if (event.key === "ArrowRight") this.#selectRelative(1);
    };

    set context(context) {
        this.#api = context.api;
        this.#state = context.state;
        const target = this.#state?.consumeRouteTarget?.("pictures") || null;
        this.#selectedId = String(target?.pictureId || "");
        this.#render();
        void this.#loadStructure();
    }

    connectedCallback() {
        window.addEventListener("keydown", this.#handleKeyDown);
        this.#render();
    }

    disconnectedCallback() {
        window.removeEventListener("keydown", this.#handleKeyDown);
        if (this.#viewerScaleTimer !== null) clearTimeout(this.#viewerScaleTimer);
        if (this.#copyFeedbackTimer !== null) clearTimeout(this.#copyFeedbackTimer);
    }

    /** Load the complete hierarchy once without eagerly returning picture records. */
    async #loadStructure(forceRefresh = false) {
        if (!this.#api) return;
        this.#loading = true;
        this.#render();
        const response = await this.#api.pictures(
            { structure_only: true, refresh: forceRefresh },
            { forceRefresh: true, commandLabel: "Pictures structure" }
        );
        this.#domains = response.data?.domains ?? {};
        if (forceRefresh) this.#picturesByDomain.clear();
        this.#state?.setLastResult(response);
        this.#loading = false;
        this.#render();
        if (this.#selectedId) await this.#loadPictureTarget(this.#selectedId);
    }

    /** Resolve a routed picture to its domain without loading the global registry. */
    async #loadPictureTarget(pictureId: string) {
        if (!this.#api) return;
        const response = await this.#api.pictures(
            { picture_id: pictureId },
            { forceRefresh: true, commandLabel: "Picture target", silent: true }
        );
        const target = response.data?.pictures?.[0];
        if (!target) {
            this.#selectedId = "";
            return;
        }
        this.#domain = target.domain;
        this.#domainFocused = true;
        await this.#loadDomain(target.domain, false, pictureId);
    }

    /** Hydrate and cache one domain only when its tree item receives focus. */
    async #loadDomain(domain: string, forceRefresh = false, preferredId = "") {
        if (!this.#api) return;
        const cached = this.#picturesByDomain.get(domain);
        if (cached && !forceRefresh) {
            this.#pictures = cached;
            this.#selectLoadedDomain(preferredId);
            this.#render();
            return;
        }
        this.#loading = true;
        this.#render();
        const response = await this.#api.pictures(
            { domain },
            { forceRefresh: true, commandLabel: `Pictures domain: ${domain || "all"}` }
        );
        this.#pictures = response.data?.pictures ?? [];
        this.#picturesByDomain.set(domain, this.#pictures);
        this.#selectLoadedDomain(preferredId);
        this.#state?.setLastResult(response);
        this.#loading = false;
        this.#render();
    }

    /** Preserve a routed/current selection when it belongs to the loaded domain. */
    #selectLoadedDomain(preferredId = "") {
        const candidate = preferredId || this.#selectedId;
        this.#selectedId = this.#pictures.some(picture => picture.id === candidate)
            ? candidate
            : this.#pictures[0]?.id ?? "";
        this.#descriptionEditing = false;
    }

    #selected(): PictureRecord | null {
        return this.#pictures.find(picture => picture.id === this.#selectedId) ?? null;
    }

    #selectRelative(delta: number) {
        if (!this.#pictures.length) return;
        const index = Math.max(0, this.#pictures.findIndex(picture => picture.id === this.#selectedId));
        const next = (index + delta + this.#pictures.length) % this.#pictures.length;
        this.#selectPicture(this.#pictures[next].id);
    }

    /** Update an existing carousel in place and hydrate its raster when ready. */
    #selectPicture(pictureId: string) {
        const picture = this.#pictures.find(candidate => candidate.id === pictureId);
        if (!picture || picture.id === this.#selectedId) return;
        this.#selectedId = picture.id;
        this.#descriptionEditing = false;
        this.#hydrateSelection(picture);
        this.#focusSelectedThumbnail();
    }

    #render() {
        const selected = this.#selected();
        const selectedIndex = selected ? this.#pictures.findIndex(picture => picture.id === selected.id) : -1;
        this.innerHTML = `
            <section class="page-surface pictures-console">
                <div class="structure-layout pictures-layout">
                    <aside class="structure-tree pictures-domains" aria-label="Picture domains">
                        <div class="tree-list scroll-list">
                            <brain-structure-tree data-role="pictures-domain-tree"></brain-structure-tree>
                        </div>
                    </aside>
                    <main class="pictures-stage">
                    ${this.#loading ? `<div class="loading-state"><span></span><strong>Syncing pictures...</strong></div>` : selected ? `
                        <section class="picture-carousel" aria-label="Picture carousel">
                            <header>
                                <div><span class="status-pill" data-role="picture-domain">${escapeHtml(selected.domain)}</span><strong data-role="picture-filename">${escapeHtml(selected.filename)}</strong></div>
                                <span data-role="picture-position">${selectedIndex + 1} / ${this.#pictures.length}</span>
                            </header>
                            <div class="picture-viewport">
                                <button class="carousel-arrow is-previous" data-action="previous-picture" aria-label="Previous picture">${icon("chevronRight")}</button>
                                <div class="picture-render-layer">
                                    <button class="picture-render-trigger" data-action="open-picture-viewer" aria-label="Open ${escapeHtml(selected.filename)} in fullscreen viewer">
                                        <img data-role="selected-picture-image" src="${this.#api?.pictureUrl(selected.id) ?? ""}" alt="${escapeHtml(selected.description || selected.filename)}" loading="eager" decoding="async" fetchpriority="high">
                                    </button>
                                </div>
                                <button class="carousel-arrow is-next" data-action="next-picture" aria-label="Next picture">${icon("chevronRight")}</button>
                            </div>
                            <div class="picture-thumbnails" role="listbox" aria-label="Thumbnails">
                                ${this.#pictures.map(picture => `
                                    <button role="option" aria-selected="${picture.id === selected.id}" data-picture-id="${escapeHtml(picture.id)}" title="${escapeHtml(picture.filename)}">
                                        <img src="${this.#api?.pictureUrl(picture.id) ?? ""}" alt="" loading="lazy" decoding="async" fetchpriority="low">
                                    </button>
                                `).join("")}
                            </div>
                        </section>
                        <aside class="picture-inspector">
                            <header><strong>Inspector</strong><span data-role="picture-dimensions">${selected.width} × ${selected.height}</span></header>
                            <dl>
                                <div class="picture-path-row">
                                    <dt>Path</dt>
                                    <dd>
                                        <span data-role="picture-path">${escapeHtml(selected.relative_path)}</span>
                                        <button class="picture-copy-path" data-action="copy-picture-path" data-copy-path="${escapeHtml(selected.absolute_path || "")}" title="Copy absolute path" aria-label="Copy absolute picture path">
                                            ${icon("copy")}<span>Copy</span>
                                        </button>
                                    </dd>
                                </div>
                                <div><dt>Type</dt><dd data-role="picture-mime">${escapeHtml(selected.mime_type)}</dd></div>
                                <div><dt>Size</dt><dd data-role="picture-size">${this.#formatBytes(selected.size_bytes)}</dd></div>
                                <div><dt>Description</dt><dd data-role="picture-description-source">${escapeHtml(selected.description_source || "pending")}</dd></div>
                            </dl>
                            ${this.#renderDescriptionPanel(selected)}
                        </aside>
                    ` : `<section class="search-empty">${icon("camera")}<h2>${this.#domainFocused ? "No pictures" : "Select a domain"}</h2><p>${this.#domainFocused ? "No pictures are registered in this domain." : "The tree is ready; pictures load when an item is focused."}</p></section>`}
                    </main>
                </div>
                ${selected ? this.#renderViewer(selected) : ""}
            </section>
        `;
        this.#configureDomainTree();
        this.#bindEvents();
    }

    /** Center and focus the active option without rebuilding or animating from scroll origin. */
    #focusSelectedThumbnail() {
        const selected = this.querySelector<HTMLElement>('.picture-thumbnails [role="option"][aria-selected="true"]');
        selected?.scrollIntoView({ behavior: "auto", block: "nearest", inline: "center" });
        selected?.focus({ preventScroll: true });
    }

    /** Patch carousel metadata immediately and replace only the raster after it loads. */
    #hydrateSelection(picture: PictureRecord) {
        const position = this.#pictures.findIndex(candidate => candidate.id === picture.id) + 1;
        this.#setText("picture-domain", picture.domain);
        this.#setText("picture-filename", picture.filename);
        this.#setText("picture-position", `${position} / ${this.#pictures.length}`);
        this.#setText("picture-dimensions", `${picture.width} × ${picture.height}`);
        this.#setText("picture-path", picture.relative_path);
        const copyPath = this.querySelector<HTMLButtonElement>("[data-action='copy-picture-path']");
        if (copyPath) {
            copyPath.dataset.copyPath = picture.absolute_path || "";
            copyPath.disabled = !picture.absolute_path;
        }
        this.#setText("picture-mime", picture.mime_type);
        this.#setText("picture-size", this.#formatBytes(picture.size_bytes));
        this.#setText("picture-description-source", picture.description_source || "pending");
        this.#mountDescriptionPanel(picture);
        const trigger = this.querySelector<HTMLElement>("[data-action='open-picture-viewer']");
        trigger?.setAttribute("aria-label", `Open ${picture.filename} in fullscreen viewer`);
        this.querySelectorAll<HTMLElement>("[data-picture-id]").forEach(option => {
            option.setAttribute("aria-selected", String(option.dataset.pictureId === picture.id));
        });
        this.#hydrateSelectedRaster(picture);
    }

    /** Load the next raster off-DOM and commit only the newest completed request. */
    #hydrateSelectedRaster(picture: PictureRecord) {
        const token = ++this.#imageHydrationToken;
        const source = this.#api?.pictureUrl(picture.id) ?? "";
        const pending = new Image();
        pending.decoding = "async";
        pending.onload = () => {
            if (token !== this.#imageHydrationToken || picture.id !== this.#selectedId) return;
            const mounted = this.querySelector<HTMLImageElement>("[data-role='selected-picture-image']");
            if (!mounted) return;
            mounted.src = source;
            mounted.alt = picture.description || picture.filename;
        };
        pending.src = source;
    }

    /** Replace one render field without reconstructing its surrounding component. */
    #setText(role: string, value: string) {
        const element = this.querySelector<HTMLElement>(`[data-role='${role}']`);
        if (element) element.textContent = value;
    }

    /** Render the fullscreen viewer for the selected canonical picture. */
    #renderViewer(selected: PictureRecord) {
        if (!this.#viewerOpen) return "";
        return `
            <section class="picture-viewer" role="dialog" aria-modal="true" aria-label="Fullscreen viewer for ${escapeHtml(selected.filename)}">
                <strong class="picture-viewer-title">${escapeHtml(selected.filename)}</strong>
                <button class="picture-viewer-close" data-action="close-picture-viewer" aria-label="Close viewer">${icon("close")}</button>
                <div class="picture-viewer-zoom-fabs" aria-label="Zoom controls">
                    <button data-action="viewer-zoom-in" aria-label="Zoom in">${icon("plus")}</button>
                    <button data-action="viewer-zoom-out" aria-label="Zoom out">${icon("minus")}</button>
                    <button data-action="viewer-reset" aria-label="Reset zoom and position">${icon("refresh")}</button>
                </div>
                <output class="picture-viewer-scale" data-role="viewer-scale">${Math.round(this.#viewerScale * 100)}%</output>
                <div class="picture-viewer-viewport" data-role="picture-viewer-viewport">
                    <img data-role="picture-viewer-image" src="${this.#api?.pictureUrl(selected.id) ?? ""}" alt="${escapeHtml(selected.description || selected.filename)}" draggable="false"
                        style="transform: translate3d(${this.#viewerX}px, ${this.#viewerY}px, 0) scale(${this.#viewerScale})">
                </div>
            </section>
        `;
    }

    /** Open the selected picture in the fullscreen viewer. */
    #openViewer() {
        const selected = this.#selected();
        if (!selected || this.#viewerOpen) return;
        this.#viewerOpen = true;
        this.#resetViewerState();
        this.querySelector(".pictures-console")?.insertAdjacentHTML("beforeend", this.#renderViewer(selected));
        this.#bindViewerEvents();
        requestAnimationFrame(() => this.querySelector<HTMLElement>("[data-action='close-picture-viewer']")?.focus());
    }

    /** Close the fullscreen viewer and return focus to the carousel image. */
    #closeViewer() {
        this.#viewerOpen = false;
        this.#viewerPointerId = null;
        if (this.#viewerScaleTimer !== null) clearTimeout(this.#viewerScaleTimer);
        this.#viewerScaleTimer = null;
        this.querySelector(".picture-viewer")?.remove();
        requestAnimationFrame(() => this.querySelector<HTMLElement>("[data-action='open-picture-viewer']")?.focus());
    }

    /** Clamp and apply one relative viewer zoom step. */
    #zoomViewer(delta: number) {
        this.#viewerScale = Math.min(8, Math.max(0.5, this.#viewerScale + delta));
        if (this.#viewerScale === 1) {
            this.#viewerX = 0;
            this.#viewerY = 0;
        }
        this.#applyViewerTransform(true);
    }

    /** Restore the fullscreen image transform. */
    #resetViewer() {
        this.#resetViewerState();
        this.#applyViewerTransform(true);
    }

    /** Reset viewer coordinates without causing a component render. */
    #resetViewerState() {
        this.#viewerScale = 1;
        this.#viewerX = 0;
        this.#viewerY = 0;
    }

    /** Apply the current pan and zoom state to the mounted fullscreen image. */
    #applyViewerTransform(showScale = false) {
        const image = this.querySelector<HTMLElement>("[data-role='picture-viewer-image']");
        if (image) image.style.transform = `translate3d(${this.#viewerX}px, ${this.#viewerY}px, 0) scale(${this.#viewerScale})`;
        const scale = this.querySelector<HTMLOutputElement>("[data-role='viewer-scale']");
        if (scale) scale.value = `${Math.round(this.#viewerScale * 100)}%`;
        if (showScale) this.#showViewerScale();
    }

    /** Reveal the scale indicator and hide it three seconds after the latest zoom change. */
    #showViewerScale() {
        const scale = this.querySelector<HTMLElement>("[data-role='viewer-scale']");
        scale?.classList.add("is-visible");
        if (this.#viewerScaleTimer !== null) clearTimeout(this.#viewerScaleTimer);
        this.#viewerScaleTimer = setTimeout(() => {
            scale?.classList.remove("is-visible");
            this.#viewerScaleTimer = null;
        }, 3000);
    }

    /** Begin one mouse, pen, or touch panning gesture. */
    #startViewerPan(event: PointerEvent, viewport: HTMLElement) {
        this.#viewerPointerId = event.pointerId;
        this.#viewerPointerStart = { x: event.clientX, y: event.clientY, originX: this.#viewerX, originY: this.#viewerY };
        viewport.setPointerCapture(event.pointerId);
        viewport.classList.add("is-panning");
    }

    /** Continue the active panning gesture without rebuilding the carousel. */
    #moveViewerPan(event: PointerEvent) {
        if (this.#viewerPointerId !== event.pointerId) return;
        this.#viewerX = this.#viewerPointerStart.originX + event.clientX - this.#viewerPointerStart.x;
        this.#viewerY = this.#viewerPointerStart.originY + event.clientY - this.#viewerPointerStart.y;
        this.#applyViewerTransform();
    }

    /** Finish the active panning gesture. */
    #endViewerPan(event: PointerEvent, viewport: HTMLElement) {
        if (this.#viewerPointerId !== event.pointerId) return;
        this.#viewerPointerId = null;
        if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
        viewport.classList.remove("is-panning");
    }

    /** Project dot-separated picture domains into the shared Explorer tree contract. */
    #domainTreeNodes() {
        const root = { label: "Todo", path: "", ownCount: 0, children: new Map<string, any>() };
        Object.entries(this.#domains).forEach(([domain, count]) => {
            let parent = root;
            const parts = domain.split(".").filter(Boolean);
            parts.forEach((label, index) => {
                const path = parts.slice(0, index + 1).join(".");
                if (!parent.children.has(label)) {
                    parent.children.set(label, { label, path, ownCount: 0, children: new Map<string, any>() });
                }
                parent = parent.children.get(label);
            });
            parent.ownCount += count;
        });
        const project = (node: any): any => {
            const children = [...node.children.values()].map(project);
            const count = node.ownCount + children.reduce((total: number, child: any) => total + child.count, 0);
            return { id: `pictures:${node.path || "all"}`, path: node.path, label: node.label, icon: "folder", count, children };
        };
        return [project(root)];
    }

    /** Configure Pictures with the standardized structural tree component. */
    #configureDomainTree() {
        const tree = this.querySelector("[data-role='pictures-domain-tree']");
        if (!(tree instanceof StructureTree)) return;
        tree.model = {
            nodes: this.#domainTreeNodes(),
            selectedPath: this.#domain,
            expandedPaths: this.#expandedDomains,
            toggleOnBranchSelect: true,
            title: "Pictures",
            toolbarActions: [{ id: "refresh", label: "Refresh pictures", icon: "refresh" }],
            searchQuery: this.#search,
            searchPlaceholder: "Search pictures...",
            emptyText: this.#loading ? "Syncing pictures..." : "No registered domains.",
            defaultBranchIcon: "folder",
            defaultLeafIcon: "folder"
        };
        tree.addEventListener("brain-tree-select", event => {
            if ((event as CustomEvent).detail.clickedCaret) return;
            this.#domain = String((event as CustomEvent).detail.path || "");
            this.#domainFocused = true;
            void this.#loadDomain(this.#domain);
        });
        tree.addEventListener("brain-tree-toolbar-action", event => {
            if ((event as CustomEvent).detail.action === "refresh") void this.#loadStructure(true);
        });
        tree.addEventListener("brain-tree-search", event => {
            this.#search = String((event as CustomEvent).detail.query || "").trim();
        });
    }

    #bindEvents() {
        this.querySelector("[data-action='previous-picture']")?.addEventListener("click", () => this.#selectRelative(-1));
        this.querySelector("[data-action='next-picture']")?.addEventListener("click", () => this.#selectRelative(1));
        this.querySelectorAll("[data-picture-id]").forEach(button => button.addEventListener("click", () => {
            this.#selectPicture(button.getAttribute("data-picture-id") || "");
        }));
        this.#bindDescriptionEvents();
        this.querySelector("[data-action='copy-picture-path']")?.addEventListener("click", event => void this.#copyPicturePath(event.currentTarget as HTMLButtonElement));
        this.querySelector("[data-action='open-picture-viewer']")?.addEventListener("click", () => this.#openViewer());
        this.#bindViewerEvents();
    }

    /** Copy the server-resolved canonical image path and expose feedback in place. */
    async #copyPicturePath(button: HTMLButtonElement) {
        const absolutePath = button.dataset.copyPath || "";
        if (!absolutePath || !navigator.clipboard?.writeText) return;
        if (this.#copyFeedbackTimer !== null) clearTimeout(this.#copyFeedbackTimer);
        try {
            await navigator.clipboard.writeText(absolutePath);
            button.innerHTML = `${icon("check")}<span>Copied</span>`;
            button.title = absolutePath;
            this.#copyFeedbackTimer = setTimeout(() => {
                button.innerHTML = `${icon("copy")}<span>Copy</span>`;
                button.title = "Copy absolute path";
                this.#copyFeedbackTimer = null;
            }, 2200);
        } catch (_error) {
            button.innerHTML = `${icon("warning")}<span>Copy failed</span>`;
        }
    }

    /** Render the mutually exclusive read and edit states for one description. */
    #renderDescriptionPanel(picture: PictureRecord) {
        if (!this.#descriptionEditing) {
            return `
                <section class="picture-description-panel" data-role="picture-description-panel" data-mode="read">
                    <div class="picture-description-toolbar">
                        <strong>Description</strong>
                        <button class="secondary-action" data-action="edit-picture-description">${icon("edit")} Edit</button>
                    </div>
                    ${renderDescriptionCard(picture.description, { title: "Image analysis" })}
                </section>
            `;
        }
        return `
            <section class="picture-description-panel" data-role="picture-description-panel" data-mode="edit">
                <label>Description editor
                    <textarea data-role="picture-description" placeholder="Describe people, scene, objects, text, and context...">${escapeHtml(picture.description)}</textarea>
                </label>
                <div class="picture-description-actions">
                    <button class="secondary-action" data-action="cancel-picture-description">${icon("close")} Cancel</button>
                    <button class="secondary-action" data-action="generate-picture-description">${icon("camera")} Regenerate</button>
                    <button class="primary-button" data-action="save-picture-description">${icon("save")} Save</button>
                </div>
            </section>
        `;
    }

    /** Replace only the description surface so carousel and image state remain mounted. */
    #mountDescriptionPanel(picture: PictureRecord) {
        const panel = this.querySelector<HTMLElement>("[data-role='picture-description-panel']");
        if (!panel) return;
        panel.outerHTML = this.#renderDescriptionPanel(picture);
        this.#bindDescriptionEvents();
    }

    /** Bind controls owned by the current description mode. */
    #bindDescriptionEvents() {
        this.querySelector("[data-action='edit-picture-description']")?.addEventListener("click", () => this.#setDescriptionEditing(true));
        this.querySelector("[data-action='cancel-picture-description']")?.addEventListener("click", () => this.#setDescriptionEditing(false));
        this.querySelector("[data-action='save-picture-description']")?.addEventListener("click", () => void this.#saveDescription());
        this.querySelector("[data-action='generate-picture-description']")?.addEventListener("click", () => void this.#generateDescription());
        this.querySelectorAll("[data-action='resolve-description-entity']").forEach(button => {
            button.addEventListener("click", () => {
                this.#state?.setRouteTarget?.("knowledge", { entityLabel: button.getAttribute("data-entity-label") || "" });
            });
        });
    }

    /** Toggle between the structured card and textarea without changing selection. */
    #setDescriptionEditing(editing: boolean) {
        const selected = this.#selected();
        if (!selected || this.#descriptionRequestPending) return;
        this.#descriptionEditing = editing;
        this.#mountDescriptionPanel(selected);
        if (editing) requestAnimationFrame(() => this.querySelector<HTMLTextAreaElement>("[data-role='picture-description']")?.focus());
    }

    /** Bind controls owned only by a mounted fullscreen viewer. */
    #bindViewerEvents() {
        this.querySelector("[data-action='close-picture-viewer']")?.addEventListener("click", () => this.#closeViewer());
        this.querySelector("[data-action='viewer-zoom-in']")?.addEventListener("click", () => this.#zoomViewer(0.25));
        this.querySelector("[data-action='viewer-zoom-out']")?.addEventListener("click", () => this.#zoomViewer(-0.25));
        this.querySelector("[data-action='viewer-reset']")?.addEventListener("click", () => this.#resetViewer());
        const viewer = this.querySelector<HTMLElement>("[data-role='picture-viewer-viewport']");
        viewer?.addEventListener("wheel", event => {
            event.preventDefault();
            this.#zoomViewer(event.deltaY < 0 ? 0.25 : -0.25);
        }, { passive: false });
        viewer?.addEventListener("dblclick", () => this.#viewerScale === 1 ? this.#zoomViewer(1) : this.#resetViewer());
        viewer?.addEventListener("pointerdown", event => this.#startViewerPan(event, viewer));
        viewer?.addEventListener("pointermove", event => this.#moveViewerPan(event));
        viewer?.addEventListener("pointerup", event => this.#endViewerPan(event, viewer));
        viewer?.addEventListener("pointercancel", event => this.#endViewerPan(event, viewer));
    }

    async #saveDescription() {
        const selected = this.#selected();
        const textarea = this.querySelector<HTMLTextAreaElement>("[data-role='picture-description']");
        if (!selected || !textarea || !this.#api || this.#descriptionRequestPending) return;
        await this.#submitDescription(
            selected,
            () => this.#api.describePicture(selected.id, textarea.value.trim()),
            "Saving..."
        );
    }

    /** Generate a model-backed description without overwriting the mounted draft on failure. */
    async #generateDescription() {
        const selected = this.#selected();
        if (!selected || !this.#api || this.#descriptionRequestPending) return;
        await this.#submitDescription(
            selected,
            () => this.#api.generatePictureDescription(selected.id),
            "Generating..."
        );
    }

    /** Serialize description mutations and patch the cached record without rebuilding the carousel. */
    async #submitDescription(selected: PictureRecord, request: () => Promise<ApiResponse<PictureDescriptionPayload>>, pendingLabel: string) {
        this.#descriptionRequestPending = true;
        this.#setDescriptionActionsBusy(true, pendingLabel);
        try {
            const response = await request();
            this.#state?.setLastResult(response);
            const updated = response.data?.picture as PictureRecord | undefined;
            if (!response.ok || !updated) return;
            const index = this.#pictures.findIndex(picture => picture.id === updated.id);
            if (index >= 0) this.#pictures[index] = updated;
            this.#picturesByDomain.set(this.#domain, this.#pictures);
            if (this.#selectedId === updated.id) {
                this.#descriptionEditing = false;
                this.#hydrateSelection(updated);
            }
        } finally {
            this.#descriptionRequestPending = false;
            this.#setDescriptionActionsBusy(false);
        }
    }

    /** Keep both mutually exclusive description actions synchronized and accessible. */
    #setDescriptionActionsBusy(busy: boolean, pendingLabel = "") {
        const generate = this.querySelector<HTMLButtonElement>("[data-action='generate-picture-description']");
        const save = this.querySelector<HTMLButtonElement>("[data-action='save-picture-description']");
        if (generate) {
            generate.disabled = busy;
            generate.setAttribute("aria-busy", String(busy));
            generate.innerHTML = busy && pendingLabel === "Generating..."
                ? `${icon("refresh")} ${pendingLabel}`
                : `${icon("camera")} Regenerate`;
        }
        if (save) {
            save.disabled = busy;
            save.setAttribute("aria-busy", String(busy));
            save.innerHTML = busy && pendingLabel === "Saving..."
                ? `${icon("refresh")} ${pendingLabel}`
                : `${icon("save")} Save description`;
        }
    }

    #formatBytes(bytes: number) {
        if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
}

customElements.define(PicturesView.selector, PicturesView);
