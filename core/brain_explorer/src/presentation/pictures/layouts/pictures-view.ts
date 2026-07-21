/**
 * Modern registry-backed picture browser and carousel.
 */

import type { ApiResponse } from "../../../application/shared/contracts/api-response-contract.ts";
import type { PictureDescriptionPayload, PictureRecord } from "../../../application/pictures/dtos/responses/pictures-response.ts";
import { escapeHtml } from "../../shared/utils/html.ts";
import { icon } from "../../shared/utils/icons.ts";
import { renderDescriptionCard } from "../../shared/components/description-card.ts";
import { StructureTree } from "../../shared/components/structure-tree.ts";
import type { BrainApiClient } from "../../../infrastructure/shared/http/clients/brain-api-client.ts";
import type { AppState } from "../../shell/state/app-state.ts";
import type { ComponentContext } from "../../shared/view_models/component-context-view-model.ts";
import { PictureDomainTreeProjector } from "../projectors/picture-domain-tree-projector.ts";

void StructureTree;


/**
 * A custom HTML element that manages the browsing, selection, and viewing of picture records organized by domains via an API.
 */
export class PicturesView extends HTMLElement {
    /**
     * Provides the unique CSS selector string used to identify the PicturesView component in the DOM.
     * @returns {string} A string representing the component's DOM selector.
     */
    static get selector() {
        return "brain-pictures-view";
    }

    /**
     * Holds a reference to the BrainApiClient instance used for data operations within the PicturesView, defaulting to null.
     *
     * @type {BrainApiClient | null}
     */
    #api: BrainApiClient | null = null;
    /**
     * Holds the current application state for the pictures view or remains null if the state is not yet initialized.
     *
     * @type {AppState | null}
     */
    #state: AppState | null = null;
    /**
     * Maintains a private collection of picture records used within the view layout.
     *
     * @type {PictureRecord[]}
     */
    #pictures: PictureRecord[] = [];
    /**
     * Maintains a private mapping of domain identifiers to their associated collections of picture records.
     *
     * @type {Map<string, PictureRecord[]>}
     */
    #picturesByDomain = new Map<string, PictureRecord[]>();
    /**
     * Maintains a mapping of domain identifiers to their associated numerical counts.
     *
     * @type {Record<string, number>}
     */
    #domains: Record<string, number> = {};
    /**
     * Stores the current domain identifier used for filtering or scoping the pictures view.
     *
     * @type {string}
     */
    #domain = "";
    /**
     * Tracks whether the domain-specific focus state is currently active within the pictures view.
     *
     * @type {boolean}
     */
    #domainFocused = false;
    /**
     * Maintains the unique identifier of the currently selected picture within the view state.
     *
     * @type {string}
     */
    #selectedId = "";
    /**
     * Tracks the loading state of the pictures view to manage the visibility of loading indicators.
     *
     * @type {boolean}
     */
    #loading = false;
    /**
     * Tracks whether a request to fetch picture descriptions is currently in progress.
     *
     * @type {boolean}
     */
    #descriptionRequestPending = false;
    /**
     * Tracks whether the picture description is currently in an editing state.
     *
     * @type {boolean}
     */
    #descriptionEditing = false;
    /**
     * Tracks the active timeout reference for the copy-to-clipboard feedback duration.
     *
     * @type {number | null}
     */
    #copyFeedbackTimer: ReturnType<typeof setTimeout> | null = null;
    /**
     * Maintains the current search query string used to filter the pictures view.
     *
     * @type {string}
     */
    #search = "";
    /**
     * Maintains a set of currently expanded domain identifiers, initialized with the global pictures collection.
     *
     * @type {Set<string>}
     */
    #expandedDomains = new Set<string>(["pictures:all"]);
    /**
     * Initializes a private numeric token used to track or trigger the hydration process of images within the view.
     *
     * @type {number}
     */
    #imageHydrationToken = 0;
    /**
     * Tracks the visibility state of the image viewer component.
     *
     * @type {boolean}
     */
    #viewerOpen = false;
    /**
     * Maintains the current magnification level of the picture viewer.
     *
     * @type {number}
     */
    #viewerScale = 1;
    /**
     * Stores the horizontal coordinate of the picture viewer.
     *
     * @type {number}
     */
    #viewerX = 0;
    /**
     * Tracks the vertical coordinate offset of the picture viewer.
     *
     * @type {number}
     */
    #viewerY = 0;
    /**
     * Stores the unique identifier of the currently active viewer pointer, or null if no pointer is active.
     *
     * @type {number | null}
     */
    #viewerPointerId: number | null = null;
    /**
     * Holds the reference to a timeout timer used to manage the scaling state of the picture viewer.
     *
     * @type {number | null}
     */
    #viewerScaleTimer: ReturnType<typeof setTimeout> | null = null;
    /**
     * Stores the initial coordinate state and origin offsets for the viewer's pointer interaction.
     *
     * @type {{ x: number; y: number; originX: number; originY: number; }}
     */
    #viewerPointerStart = { x: 0, y: 0, originX: 0, originY: 0 };
    /**
     * Processes keyboard input to control image viewer navigation, zooming, and visibility based on the current viewer state.
     *
     * @type {(event: KeyboardEvent) => void}
     */
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

    /**
     * Assigns the component context to initialize API and state references, synchronize the selected picture ID from the route target, and trigger the initial render and data load.
     * @param {ComponentContext} context The component context providing access to the application API and state management.
     */
    set context(context: ComponentContext) {
        this.#api = context.api;
        this.#state = context.state;
        const target = this.#state?.consumeRouteTarget?.("pictures") || null;
        this.#selectedId = String(target?.pictureId || "");
        this.#render();
        void this.#loadStructure();
    }

    /**
     * Registers a global keyboard event listener and triggers the initial component rendering when the element is added to the DOM.
     */
    connectedCallback() {
        window.addEventListener("keydown", this.#handleKeyDown);
        this.#render();
    }

    /**
     * Cleans up global event listeners and active timers when the component is removed from the DOM.
     */
    disconnectedCallback() {
        window.removeEventListener("keydown", this.#handleKeyDown);
        if (this.#viewerScaleTimer !== null) clearTimeout(this.#viewerScaleTimer);
        if (this.#copyFeedbackTimer !== null) clearTimeout(this.#copyFeedbackTimer);
    }

    /**
     * Load the complete hierarchy once without eagerly returning picture records.
     * @param {boolean} forceRefresh A boolean flag indicating whether to bypass cached data and clear the existing pictures-by-domain mapping.
     */
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

    /**
     * Resolve a routed picture to its domain without loading the global registry.
     * @param {string} pictureId The unique identifier of the picture to be retrieved.
     */
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

    /**
     * Hydrate and cache one domain only when its tree item receives focus.
     * @param {string} domain The unique identifier of the domain to load pictures from.
     * @param {boolean} forceRefresh A flag indicating whether to bypass the local cache and fetch fresh data from the API.
     * @param {string} preferredId The identifier of the specific picture to be selected after the domain data is loaded.
     */
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

    /**
     * Preserve a routed/current selection when it belongs to the loaded domain.
     * @param {string} preferredId The optional identifier of the picture to be selected.
     */
    #selectLoadedDomain(preferredId = "") {
        const candidate = preferredId || this.#selectedId;
        this.#selectedId = this.#pictures.some(picture => picture.id === candidate)
            ? candidate
            : this.#pictures[0]?.id ?? "";
        this.#descriptionEditing = false;
    }

    /**
     * Retrieves the picture record that matches the currently stored selected identifier.
     * @returns {PictureRecord | null} The matching PictureRecord if found, otherwise null.
     */
    #selected(): PictureRecord | null {
        return this.#pictures.find(picture => picture.id === this.#selectedId) ?? null;
    }

    /**
     * Updates the currently selected picture by shifting the selection index by a specified offset, wrapping around the collection boundaries.
     * @param {number} delta The numeric offset to move the selection forward or backward.
     */
    #selectRelative(delta: number) {
        if (!this.#pictures.length) return;
        const index = Math.max(0, this.#pictures.findIndex(picture => picture.id === this.#selectedId));
        const next = (index + delta + this.#pictures.length) % this.#pictures.length;
        const picture = this.#pictures[next];
        if (picture) this.#selectPicture(picture.id);
    }

    /**
     * Update an existing carousel in place and hydrate its raster when ready.
     * @param {string} pictureId The unique identifier of the picture to be selected.
     */
    #selectPicture(pictureId: string) {
        const picture = this.#pictures.find(candidate => candidate.id === pictureId);
        if (!picture || picture.id === this.#selectedId) return;
        this.#selectedId = picture.id;
        this.#descriptionEditing = false;
        this.#hydrateSelection(picture);
        this.#focusSelectedThumbnail();
    }

    /**
     * Updates the component's innerHTML to render the pictures gallery interface, including the domain tree, image carousel, and inspector panel, based on the current selection and loading state.
     */
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

    /**
     * Center and focus the active option without rebuilding or animating from scroll origin.
     */
    #focusSelectedThumbnail() {
        const selected = this.querySelector<HTMLElement>('.picture-thumbnails [role="option"][aria-selected="true"]');
        selected?.scrollIntoView({ behavior: "auto", block: "nearest", inline: "center" });
        selected?.focus({ preventScroll: true });
    }

    /**
     * Patch carousel metadata immediately and replace only the raster after it loads.
     * @param {PictureRecord} picture The picture record containing the metadata and identifiers used to populate the UI.
     */
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

    /**
     * Load the next raster off-DOM and commit only the newest completed request.
     * @param {PictureRecord} picture The picture record containing the identifier and metadata used to fetch and display the image.
     */
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

    /**
     * Replace one render field without reconstructing its surrounding component.
     * @param {string} role The unique identifier used in the data-role attribute to locate the target element.
     * @param {string} value The string to be assigned to the element's text content.
     */
    #setText(role: string, value: string) {
        const element = this.querySelector<HTMLElement>(`[data-role='${role}']`);
        if (element) element.textContent = value;
    }

    /**
     * Render the fullscreen viewer for the selected canonical picture.
     * @param {PictureRecord} selected The picture record containing the metadata and identifier used to populate the viewer's content and source URL.
     * @returns {string} An HTML string representing the viewer dialog, or an empty string if the viewer is closed.
     */
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

    /**
     * Open the selected picture in the fullscreen viewer.
     */
    #openViewer() {
        const selected = this.#selected();
        if (!selected || this.#viewerOpen) return;
        this.#viewerOpen = true;
        this.#resetViewerState();
        this.querySelector(".pictures-console")?.insertAdjacentHTML("beforeend", this.#renderViewer(selected));
        this.#bindViewerEvents();
        requestAnimationFrame(() => this.querySelector<HTMLElement>("[data-action='close-picture-viewer']")?.focus());
    }

    /**
     * Close the fullscreen viewer and return focus to the carousel image.
     */
    #closeViewer() {
        this.#viewerOpen = false;
        this.#viewerPointerId = null;
        if (this.#viewerScaleTimer !== null) clearTimeout(this.#viewerScaleTimer);
        this.#viewerScaleTimer = null;
        this.querySelector(".picture-viewer")?.remove();
        requestAnimationFrame(() => this.querySelector<HTMLElement>("[data-action='open-picture-viewer']")?.focus());
    }

    /**
     * Clamp and apply one relative viewer zoom step.
     * @param {number} delta The numeric value to add to the current scale factor.
     */
    #zoomViewer(delta: number) {
        this.#viewerScale = Math.min(8, Math.max(0.5, this.#viewerScale + delta));
        if (this.#viewerScale === 1) {
            this.#viewerX = 0;
            this.#viewerY = 0;
        }
        this.#applyViewerTransform(true);
    }

    /**
     * Restore the fullscreen image transform.
     */
    #resetViewer() {
        this.#resetViewerState();
        this.#applyViewerTransform(true);
    }

    /**
     * Reset viewer coordinates without causing a component render.
     */
    #resetViewerState() {
        this.#viewerScale = 1;
        this.#viewerX = 0;
        this.#viewerY = 0;
    }

    /**
     * Apply the current pan and zoom state to the mounted fullscreen image.
     * @param {boolean} showScale Determines whether the scale indicator visibility should be triggered.
     */
    #applyViewerTransform(showScale = false) {
        const image = this.querySelector<HTMLElement>("[data-role='picture-viewer-image']");
        if (image) image.style.transform = `translate3d(${this.#viewerX}px, ${this.#viewerY}px, 0) scale(${this.#viewerScale})`;
        const scale = this.querySelector<HTMLOutputElement>("[data-role='viewer-scale']");
        if (scale) scale.value = `${Math.round(this.#viewerScale * 100)}%`;
        if (showScale) this.#showViewerScale();
    }

    /**
     * Reveal the scale indicator and hide it three seconds after the latest zoom change.
     */
    #showViewerScale() {
        const scale = this.querySelector<HTMLElement>("[data-role='viewer-scale']");
        scale?.classList.add("is-visible");
        if (this.#viewerScaleTimer !== null) clearTimeout(this.#viewerScaleTimer);
        this.#viewerScaleTimer = setTimeout(() => {
            scale?.classList.remove("is-visible");
            this.#viewerScaleTimer = null;
        }, 3000);
    }

    /**
     * Begin one mouse, pen, or touch panning gesture.
     * @param {PointerEvent} event The pointer event containing the unique pointer identifier and initial screen coordinates.
     * @param {HTMLElement} viewport The HTML element used to capture the pointer and receive the panning CSS class.
     */
    #startViewerPan(event: PointerEvent, viewport: HTMLElement) {
        this.#viewerPointerId = event.pointerId;
        this.#viewerPointerStart = { x: event.clientX, y: event.clientY, originX: this.#viewerX, originY: this.#viewerY };
        viewport.setPointerCapture(event.pointerId);
        viewport.classList.add("is-panning");
    }

    /**
     * Continue the active panning gesture without rebuilding the carousel.
     * @param {PointerEvent} event The pointer event containing the current client coordinates and unique pointer identifier.
     */
    #moveViewerPan(event: PointerEvent) {
        if (this.#viewerPointerId !== event.pointerId) return;
        this.#viewerX = this.#viewerPointerStart.originX + event.clientX - this.#viewerPointerStart.x;
        this.#viewerY = this.#viewerPointerStart.originY + event.clientY - this.#viewerPointerStart.y;
        this.#applyViewerTransform();
    }

    /**
     * Finish the active panning gesture.
     * @param {PointerEvent} event The pointer event triggering the end of the pan operation.
     * @param {HTMLElement} viewport The HTML element acting as the panning container and pointer capture target.
     */
    #endViewerPan(event: PointerEvent, viewport: HTMLElement) {
        if (this.#viewerPointerId !== event.pointerId) return;
        this.#viewerPointerId = null;
        if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
        viewport.classList.remove("is-panning");
    }

    /**
     * Project dot-separated picture domains into the shared Explorer tree contract.
     * @returns {import("D:/.agents/@Angi/core/brain_explorer/src/presentation/shared/view_models/structure-tree-view-model").StructureTreeNode[]} The result of the projection process from the PictureDomainTreeProjector.
     */
    #domainTreeNodes() {
        return new PictureDomainTreeProjector(this.#domains).project();
    }

    /**
     * Configure Pictures with the standardized structural tree component.
     */
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
            if (!(event instanceof CustomEvent)) return;
            if (event.detail.clickedCaret) return;
            this.#domain = String(event.detail.path || "");
            this.#domainFocused = true;
            void this.#loadDomain(this.#domain);
        });
        tree.addEventListener("brain-tree-toolbar-action", event => {
            if (event instanceof CustomEvent && event.detail.action === "refresh") void this.#loadStructure(true);
        });
        tree.addEventListener("brain-tree-search", event => {
            if (event instanceof CustomEvent) this.#search = String(event.detail.query || "").trim();
        });
    }

    /**
     * Attaches click event listeners to navigation controls, picture selection buttons, and viewer actions within the component's DOM.
     */
    #bindEvents() {
        this.querySelector("[data-action='previous-picture']")?.addEventListener("click", () => this.#selectRelative(-1));
        this.querySelector("[data-action='next-picture']")?.addEventListener("click", () => this.#selectRelative(1));
        this.querySelectorAll("[data-picture-id]").forEach(button => button.addEventListener("click", () => {
            this.#selectPicture(button.getAttribute("data-picture-id") || "");
        }));
        this.#bindDescriptionEvents();
        this.querySelector("[data-action='copy-picture-path']")?.addEventListener("click", event => {
            if (event.currentTarget instanceof HTMLButtonElement) void this.#copyPicturePath(event.currentTarget);
        });
        this.querySelector("[data-action='open-picture-viewer']")?.addEventListener("click", () => this.#openViewer());
        this.#bindViewerEvents();
    }

    /**
     * Copy the server-resolved canonical image path and expose feedback in place.
     * @param {HTMLButtonElement} button The HTML button element containing the path to be copied in its data-copy-path attribute.
     */
    async #copyPicturePath(button: HTMLButtonElement) {
        const absolutePath = button.dataset.copyPath || "";
        if (!absolutePath || !navigator.clipboard?.writeText) return;
        if (this.#copyFeedbackTimer !== null) clearTimeout(this.#copyFeedbackTimer);
        try {
            await navigator.clipboard.writeText(absolutePath);
            button.innerHTML = `${icon("checkSquare")}<span>Copied</span>`;
            button.title = absolutePath;
            this.#copyFeedbackTimer = setTimeout(() => {
                button.innerHTML = `${icon("copy")}<span>Copy</span>`;
                button.title = "Copy absolute path";
                this.#copyFeedbackTimer = null;
            }, 2200);
        } catch (_error) {
            button.innerHTML = `${icon("pulse")}<span>Copy failed</span>`;
        }
    }

    /**
     * Render the mutually exclusive read and edit states for one description.
     * @param {PictureRecord} picture The picture record containing the description text to be displayed or edited.
     * @returns {string} An HTML string representing the rendered description panel.
     */
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

    /**
     * Replace only the description surface so carousel and image state remain mounted.
     * @param {PictureRecord} picture The picture record containing the data to be displayed in the description panel.
     */
    #mountDescriptionPanel(picture: PictureRecord) {
        const panel = this.querySelector<HTMLElement>("[data-role='picture-description-panel']");
        if (!panel) return;
        panel.outerHTML = this.#renderDescriptionPanel(picture);
        this.#bindDescriptionEvents();
    }

    /**
     * Bind controls owned by the current description mode.
     */
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

    /**
     * Toggle between the structured card and textarea without changing selection.
     * @param {boolean} editing A boolean flag indicating whether to enable or disable the description editing mode.
     */
    #setDescriptionEditing(editing: boolean) {
        const selected = this.#selected();
        if (!selected || this.#descriptionRequestPending) return;
        this.#descriptionEditing = editing;
        this.#mountDescriptionPanel(selected);
        if (editing) requestAnimationFrame(() => this.querySelector<HTMLTextAreaElement>("[data-role='picture-description']")?.focus());
    }

    /**
     * Bind controls owned only by a mounted fullscreen viewer.
     */
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

    /**
     * Asynchronously persists the trimmed text from the description textarea to the API for the currently selected picture, provided no request is already pending.
     */
    async #saveDescription() {
        const selected = this.#selected();
        const textarea = this.querySelector<HTMLTextAreaElement>("[data-role='picture-description']");
        const api = this.#api;
        if (!selected || !textarea || !api || this.#descriptionRequestPending) return;
        await this.#submitDescription(
            () => api.describePicture(selected.id, textarea.value.trim()),
            "Saving..."
        );
    }

    /**
     * Generate a model-backed description without overwriting the mounted draft on failure.
     */
    async #generateDescription() {
        const selected = this.#selected();
        const api = this.#api;
        if (!selected || !api || this.#descriptionRequestPending) return;
        await this.#submitDescription(
            () => api.generatePictureDescription(selected.id),
            "Generating..."
        );
    }

    /**
     * Serialize description mutations and patch the cached record without rebuilding the carousel.
     * @param {() => Promise<ApiResponse<PictureDescriptionPayload>>} request A function that returns a promise resolving to an API response containing the picture description payload.
     * @param {string} pendingLabel The text label to display while the description request is in progress.
     */
    async #submitDescription(request: () => Promise<ApiResponse<PictureDescriptionPayload>>, pendingLabel: string) {
        this.#descriptionRequestPending = true;
        this.#setDescriptionActionsBusy(true, pendingLabel);
        try {
            const response = await request();
            this.#state?.setLastResult(response);
            const updated = response.data?.picture;
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

    /**
     * Keep both mutually exclusive description actions synchronized and accessible.
     * @param {boolean} busy A boolean indicating whether the description actions are currently executing and should be disabled.
     * @param {string} pendingLabel An optional string used to set the button text when the action is in a busy state.
     */
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

    /**
     * Converts a byte count into a human-readable string formatted as either kilobytes or megabytes.
     * @param {number} bytes The total number of bytes to be formatted.
     * @returns {string} A string representing the size in KB or MB based on the input magnitude.
     */
    #formatBytes(bytes: number) {
        if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
}

customElements.define(PicturesView.selector, PicturesView);
