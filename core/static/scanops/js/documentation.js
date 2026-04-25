(function () {
    const getHashSectionId = () => decodeURIComponent((window.location.hash || "").replace(/^#/, ""));

    const initDocumentationToc = () => {
        const toc = document.querySelector("[data-doc-toc]");
        const scrollRoot = document.querySelector("[data-doc-scrollspy]");
        if (!toc || !scrollRoot) return;

        const links = Array.from(toc.querySelectorAll("a.doc-toc-link[href^='#']"));
        if (!links.length) return;

        const sectionById = new Map();
        links.forEach((link) => {
            const targetId = (link.getAttribute("href") || "").replace(/^#/, "").trim();
            if (!targetId) return;
            const section = document.getElementById(targetId);
            if (!section) return;
            link.dataset.sectionId = targetId;
            sectionById.set(targetId, section);
        });
        if (!sectionById.size) return;

        const fallbackId = links.find((link) => link.dataset.sectionId)?.dataset.sectionId;
        if (!fallbackId) return;

        let activeSectionId = null;

        const setActiveSection = (sectionId, options = {}) => {
            const { syncHash = false, replaceHash = false } = options;
            if (!sectionById.has(sectionId)) return;
            const nextHash = "#" + encodeURIComponent(sectionId);
            if (activeSectionId === sectionId) {
                if (syncHash && window.location.hash !== nextHash) {
                    if (replaceHash) {
                        history.replaceState(null, "", nextHash);
                    } else {
                        history.pushState(null, "", nextHash);
                    }
                }
                return;
            }
            activeSectionId = sectionId;

            links.forEach((link) => {
                const isActive = link.dataset.sectionId === sectionId;
                link.classList.toggle("is-active", isActive);
                link.classList.toggle("active", isActive);
                if (isActive) {
                    link.setAttribute("aria-current", "location");
                } else {
                    link.removeAttribute("aria-current");
                }
            });

            if (!syncHash) return;
            if (window.location.hash === nextHash) return;
            if (replaceHash) {
                history.replaceState(null, "", nextHash);
            } else {
                history.pushState(null, "", nextHash);
            }
        };

        const resolveAndActivateFromHash = () => {
            const hashId = getHashSectionId();
            if (hashId && sectionById.has(hashId)) {
                setActiveSection(hashId, { replaceHash: true });
                return;
            }
            setActiveSection(fallbackId, { replaceHash: true });
        };

        links.forEach((link) => {
            link.addEventListener("click", (event) => {
                const sectionId = link.dataset.sectionId;
                const section = sectionById.get(sectionId);
                if (!section) return;
                event.preventDefault();
                setActiveSection(sectionId, { syncHash: true });
                section.scrollIntoView({ behavior: "smooth", block: "start" });
            });
        });

        window.addEventListener("hashchange", resolveAndActivateFromHash);

        const selectTopVisibleSection = (items) => {
            if (!items.length) return;
            items.sort((left, right) => {
                if (left.topDistance !== right.topDistance) {
                    return left.topDistance - right.topDistance;
                }
                return right.ratio - left.ratio;
            });
            setActiveSection(items[0].id, { syncHash: true, replaceHash: true });
        };

        const scrollSpySections = Array.from(sectionById.values());
        if ("IntersectionObserver" in window && scrollSpySections.length) {
            const visibility = new Map();
            const observer = new IntersectionObserver(
                (entries) => {
                    entries.forEach((entry) => {
                        visibility.set(entry.target.id, {
                            id: entry.target.id,
                            isIntersecting: entry.isIntersecting,
                            ratio: entry.intersectionRatio,
                            topDistance: Math.abs(entry.boundingClientRect.top),
                        });
                    });
                    const visible = Array.from(visibility.values()).filter((item) => item && item.isIntersecting);
                    selectTopVisibleSection(visible);
                },
                {
                    root: null,
                    rootMargin: "-18% 0px -58% 0px",
                    threshold: [0.1, 0.2, 0.4, 0.65],
                }
            );
            scrollSpySections.forEach((section) => observer.observe(section));
        } else {
            let ticking = false;
            const onScroll = () => {
                if (ticking) return;
                ticking = true;
                window.requestAnimationFrame(() => {
                    ticking = false;
                    const candidates = [];
                    scrollSpySections.forEach((section) => {
                        const rect = section.getBoundingClientRect();
                        const isVisible = rect.bottom > 80 && rect.top < window.innerHeight * 0.82;
                        if (!isVisible) return;
                        candidates.push({
                            id: section.id,
                            ratio: Math.max(0, Math.min(1, rect.height > 0 ? (window.innerHeight - rect.top) / rect.height : 0)),
                            topDistance: Math.abs(rect.top),
                        });
                    });
                    selectTopVisibleSection(candidates);
                });
            };
            window.addEventListener("scroll", onScroll, { passive: true });
            onScroll();
        }

        resolveAndActivateFromHash();
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initDocumentationToc, { once: true });
    } else {
        initDocumentationToc();
    }
})();
