/** Modern registry-backed picture browser and carousel. */

import type { PictureRecord } from "../../application/contracts/api-dtos.ts";
import { escapeHtml } from "../utils/html.ts";
import { icon } from "../utils/icons.ts";
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
        this.#hydrateSelection(picture);
        this.#focusSelectedThumbnail();
    }

    #render() {
        const selected = this.#selected();
        const selectedIndex = selected ? this.#pictures.findIndex(picture => picture.id === selected.id) : -1;
        this.innerHTML = `
            <section class="page-surface pictures-console">
                <div class="structure-layout pictures-layout">
                    <aside class="structure-tree pictures-domains" aria-label="Dominios de pictures">
                        <div class="tree-list scroll-list">
                            <brain-structure-tree data-role="pictures-domain-tree"></brain-structure-tree>
                        </div>
                    </aside>
                    <main class="pictures-stage">
                    ${this.#loading ? `<div class="loading-state"><span></span><strong>Sincronizando pictures...</strong></div>` : selected ? `
                        <section class="picture-carousel" aria-label="Carrusel de pictures">
                            <header>
                                <div><span class="status-pill" data-role="picture-domain">${escapeHtml(selected.domain)}</span><strong data-role="picture-filename">${escapeHtml(selected.filename)}</strong></div>
                                <span data-role="picture-position">${selectedIndex + 1} / ${this.#pictures.length}</span>
                            </header>
                            <div class="picture-viewport">
                                <button class="carousel-arrow is-previous" data-action="previous-picture" aria-label="Picture anterior">${icon("chevronRight")}</button>
                                <div class="picture-render-layer">
                                    <button class="picture-render-trigger" data-action="open-picture-viewer" aria-label="Abrir ${escapeHtml(selected.filename)} en visor fullscreen">
                                        <img data-role="selected-picture-image" src="${this.#api?.pictureUrl(selected.id) ?? ""}" alt="${escapeHtml(selected.description || selected.filename)}" loading="eager" decoding="async" fetchpriority="high">
                                    </button>
                                </div>
                                <button class="carousel-arrow is-next" data-action="next-picture" aria-label="Picture siguiente">${icon("chevronRight")}</button>
                            </div>
                            <div class="picture-thumbnails" role="listbox" aria-label="Miniaturas">
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
                                <div><dt>Ruta</dt><dd data-role="picture-path">${escapeHtml(selected.relative_path)}</dd></div>
                                <div><dt>Tipo</dt><dd data-role="picture-mime">${escapeHtml(selected.mime_type)}</dd></div>
                                <div><dt>Tamaño</dt><dd data-role="picture-size">${this.#formatBytes(selected.size_bytes)}</dd></div>
                                <div><dt>Descripción</dt><dd data-role="picture-description-source">${escapeHtml(selected.description_source || "pendiente")}</dd></div>
                            </dl>
                            <label>Descripción
                                <textarea data-role="picture-description" placeholder="Describe personas, escena, objetos, texto y contexto...">${escapeHtml(selected.description)}</textarea>
                            </label>
                            <button class="primary-button" data-action="save-picture-description">${icon("save")} Guardar descripción</button>
                        </aside>
                    ` : `<section class="search-empty">${icon("camera")}<h2>${this.#domainFocused ? "Sin pictures" : "Selecciona un dominio"}</h2><p>${this.#domainFocused ? "No hay imágenes registradas en este dominio." : "El árbol ya está disponible; las imágenes se cargarán al enfocar un elemento."}</p></section>`}
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
        this.#setText("picture-mime", picture.mime_type);
        this.#setText("picture-size", this.#formatBytes(picture.size_bytes));
        this.#setText("picture-description-source", picture.description_source || "pendiente");
        const textarea = this.querySelector<HTMLTextAreaElement>("[data-role='picture-description']");
        if (textarea) textarea.value = picture.description;
        const trigger = this.querySelector<HTMLElement>("[data-action='open-picture-viewer']");
        trigger?.setAttribute("aria-label", `Abrir ${picture.filename} en visor fullscreen`);
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
            <section class="picture-viewer" role="dialog" aria-modal="true" aria-label="Visor fullscreen de ${escapeHtml(selected.filename)}">
                <strong class="picture-viewer-title">${escapeHtml(selected.filename)}</strong>
                <button class="picture-viewer-close" data-action="close-picture-viewer" aria-label="Cerrar visor">${icon("close")}</button>
                <div class="picture-viewer-zoom-fabs" aria-label="Controles de zoom">
                    <button data-action="viewer-zoom-in" aria-label="Acercar">${icon("plus")}</button>
                    <button data-action="viewer-zoom-out" aria-label="Alejar">${icon("minus")}</button>
                    <button data-action="viewer-reset" aria-label="Restablecer zoom y posicion">${icon("refresh")}</button>
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
            toolbarActions: [{ id: "refresh", label: "Actualizar pictures", icon: "refresh" }],
            searchQuery: this.#search,
            searchPlaceholder: "Buscar pictures...",
            emptyText: this.#loading ? "Sincronizando pictures..." : "No hay dominios registrados.",
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
        this.querySelector("[data-action='save-picture-description']")?.addEventListener("click", () => void this.#saveDescription());
        this.querySelector("[data-action='open-picture-viewer']")?.addEventListener("click", () => this.#openViewer());
        this.#bindViewerEvents();
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
        if (!selected || !textarea || !this.#api) return;
        const response = await this.#api.describePicture(selected.id, textarea.value.trim());
        this.#state?.setLastResult(response);
        if (response.ok) await this.#loadDomain(this.#domain, true, selected.id);
    }

    #formatBytes(bytes: number) {
        if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
}

customElements.define(PicturesView.selector, PicturesView);
