/** @odoo-module **/

import { registry } from "@web/core/registry";

const MSG_LOAD_ERROR =
    "No se pudo cargar Permisos. Verifique derechos de administración.";
const MSG_APPLY_PARTIAL =
    "El usuario fue creado, pero no fue posible aplicar todos los permisos. Reintente desde esta pestaña.";
const PENDING_STORAGE_KEY = "justech_jx_pending_permissions";

/**
 * Resolve the edited res.users id from the current URL.
 * New-user forms (/users/new, no numeric id) correctly return null.
 */
function userIdFromPage() {
    const path = location.pathname || "";
    const pathMatch = path.match(/\/users\/(\d+)(?:\/|$|\?)/);
    if (pathMatch) {
        return parseInt(pathMatch[1], 10);
    }
    const search = `${location.search || ""}${location.hash || ""}`;
    const idMatch = search.match(/[?#&]id=(\d+)\b/);
    if (idMatch) {
        return parseInt(idMatch[1], 10);
    }
    return null;
}

function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) {
        node.className = cls;
    }
    if (text != null) {
        node.textContent = text;
    }
    return node;
}

function normalizeNotes(notes) {
    if (notes == null || notes === false) {
        return [];
    }
    if (typeof notes === "string") {
        const t = notes.trim();
        return t ? [t] : [];
    }
    if (!Array.isArray(notes)) {
        return [];
    }
    if (
        notes.length > 1 &&
        notes.every((n) => typeof n === "string" && n.length === 1)
    ) {
        const joined = notes.join("").trim();
        return joined ? [joined] : [];
    }
    return notes
        .filter((n) => typeof n === "string" && n.trim())
        .map((n) => n.trim());
}

function loadPending() {
    try {
        const raw = sessionStorage.getItem(PENDING_STORAGE_KEY);
        if (!raw) {
            return null;
        }
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === "object" ? parsed : null;
    } catch (err) {
        console.warn("[justech_security_ux] pending read failed", err);
        return null;
    }
}

function savePending(state) {
    try {
        sessionStorage.setItem(PENDING_STORAGE_KEY, JSON.stringify(state || {}));
    } catch (err) {
        console.warn("[justech_security_ux] pending write failed", err);
    }
}

function clearPending() {
    try {
        sessionStorage.removeItem(PENDING_STORAGE_KEY);
    } catch (err) {
        /* ignore */
    }
}

/**
 * @param {HTMLElement} root
 * @param {object} orm
 * @param {number|null} uid  null = CREATE MODE (client pending only)
 * @param {Array} catalog
 * @param {object} state
 * @param {{ createMode?: boolean }} options
 */
function buildUI(root, orm, uid, catalog, state, options = {}) {
    const createMode = !!options.createMode || !uid;
    const mount = root.querySelector(".justech-jx-mount");
    if (!mount) {
        return;
    }
    mount.innerHTML = "";

    const toolbar = el("div", "justech-jx-toolbar justech-jx-nav-widget");
    const searchRow = el("div", "justech-jx-search-row");
    const label = el("label", "justech-jx-search-label", "Buscar");
    label.setAttribute("for", "justech_jx_search");
    const search = el("input", "form-control justech-jx-search");
    search.id = "justech_jx_search";
    search.type = "search";
    search.placeholder = "Ventas, pagos, fiscal…";
    searchRow.append(label, search);

    const chipRow = el("div", "justech-jx-chip-row");
    chipRow.setAttribute("role", "tablist");
    const hint = el("div", "justech-jx-search-hint text-muted");
    toolbar.append(searchRow, chipRow, hint);
    mount.appendChild(toolbar);

    if (createMode) {
        const banner = el(
            "div",
            "alert alert-secondary py-2 px-3 mb-2 justech-jx-create-banner",
            "Los permisos se aplicarán al guardar el usuario."
        );
        banner.setAttribute("role", "status");
        mount.appendChild(banner);
    }

    const body = el("div", "justech-jx-body");
    mount.appendChild(body);

    let active = catalog[0] ? catalog[0].key : null;
    let currentState = state;

    const persistIfCreate = () => {
        if (createMode) {
            savePending(currentState);
        }
    };

    const refresh = async () => {
        if (createMode) {
            rebuild();
            return;
        }
        currentState = await orm.call("res.users", "jx_permission_state", [[uid]]);
        rebuild();
    };

    const renderSection = (sec) => {
        const wrap = el("div", "justech-jx-section");
        wrap.dataset.jxModule = sec.key;
        if (sec.key !== active) {
            wrap.classList.add("justech-jx-section-hidden");
        }
        wrap.appendChild(
            el("div", "o_horizontal_separator mt-1 mb-2 text-uppercase fw-bolder small", sec.label)
        );
        const grid = el("div", "justech-jx-module-grid");
        const colL = el("div", "justech-jx-col");
        const colR = el("div", "justech-jx-col");
        const st = currentState[sec.key] || { level: "none", caps: {} };

        if (sec.levels && sec.levels.length) {
            colL.appendChild(el("div", "text-muted small mb-1", "Nivel"));
            for (const level of sec.levels) {
                const item = el("div", "form-check o_radio_item");
                const input = document.createElement("input");
                input.type = "radio";
                input.className = "form-check-input";
                input.name = `jx_lvl_${sec.key}`;
                input.value = level.code;
                input.checked = st.level === level.code;
                input.addEventListener("change", async () => {
                    if (!input.checked) {
                        return;
                    }
                    input.disabled = true;
                    try {
                        if (createMode) {
                            if (!currentState[sec.key]) {
                                currentState[sec.key] = { level: "none", caps: {} };
                            }
                            currentState[sec.key].level = level.code;
                            const caps = {};
                            for (const c of sec.caps || []) {
                                caps[c.code] = false;
                            }
                            for (const code of level.default_caps || []) {
                                caps[code] = true;
                            }
                            currentState[sec.key].caps = caps;
                            persistIfCreate();
                            rebuild();
                        } else {
                            currentState = await orm.call("res.users", "jx_apply_level", [
                                [uid],
                                sec.key,
                                level.code,
                            ]);
                            rebuild();
                        }
                    } catch (err) {
                        console.error(err);
                        await refresh();
                    } finally {
                        input.disabled = false;
                    }
                });
                item.append(input, el("label", "form-check-label", level.label));
                if (level.warning) {
                    item.appendChild(el("div", "justech-jx-note justech-jx-note-warn mt-1", level.warning));
                }
                colL.appendChild(item);
            }
        }

        if (sec.caps && sec.caps.length) {
            colR.appendChild(
                el(
                    "div",
                    "o_horizontal_separator mb-2 text-uppercase fw-bolder small",
                    sec.caps_title || "Adicionales"
                )
            );
            for (const cap of sec.caps) {
                const row = el("div", "justech-jx-cap-row form-check");
                const input = document.createElement("input");
                input.type = "checkbox";
                input.className = "form-check-input";
                input.checked = !!(st.caps || {})[cap.code];
                input.addEventListener("change", async () => {
                    input.disabled = true;
                    try {
                        if (createMode) {
                            if (!currentState[sec.key]) {
                                currentState[sec.key] = { level: "none", caps: {} };
                            }
                            if (!currentState[sec.key].caps) {
                                currentState[sec.key].caps = {};
                            }
                            currentState[sec.key].caps[cap.code] = !!input.checked;
                            persistIfCreate();
                            rebuild();
                        } else {
                            currentState = await orm.call("res.users", "jx_apply_cap", [
                                [uid],
                                cap.code,
                                input.checked,
                            ]);
                            rebuild();
                        }
                    } catch (err) {
                        console.error(err);
                        await refresh();
                    } finally {
                        input.disabled = false;
                    }
                });
                row.append(input, el("label", "form-check-label", cap.label));
                colR.appendChild(row);
                if (cap.warning) {
                    colR.appendChild(el("div", "justech-jx-note justech-jx-note-warn", cap.warning));
                }
            }
        }

        for (const note of normalizeNotes(sec.notes)) {
            const p = el("p", "justech-jx-note", note);
            colR.appendChild(p);
        }

        if (!colL.childNodes.length) {
            grid.appendChild(colR);
        } else if (!colR.childNodes.length) {
            grid.appendChild(colL);
        } else {
            grid.append(colL, colR);
        }
        wrap.appendChild(grid);
        body.appendChild(wrap);
    };

    const selectModule = (key) => {
        active = key;
        body.querySelectorAll("[data-jx-module]").forEach((section) => {
            section.classList.toggle("justech-jx-section-hidden", section.dataset.jxModule !== key);
        });
        chipRow.querySelectorAll(".justech-jx-chip").forEach((btn) => {
            const on = btn.dataset.jxKey === key;
            btn.classList.toggle("btn-primary", on);
            btn.classList.toggle("btn-secondary", !on);
            btn.setAttribute("aria-selected", on ? "true" : "false");
        });
    };

    const rebuild = () => {
        const keep = active;
        body.innerHTML = "";
        chipRow.innerHTML = "";
        catalog.forEach((sec) => {
            const btn = el("button", "btn btn-secondary justech-jx-chip", sec.label);
            btn.type = "button";
            btn.dataset.jxKey = sec.key;
            btn.setAttribute("role", "tab");
            btn.addEventListener("click", () => {
                hint.textContent = "";
                selectModule(sec.key);
            });
            chipRow.appendChild(btn);
            renderSection(sec);
        });
        selectModule(keep || (catalog[0] && catalog[0].key));
    };

    rebuild();
    persistIfCreate();

    search.addEventListener("input", () => {
        const q = (search.value || "").trim().toLowerCase();
        body.querySelectorAll(".justech-jx-hit").forEach((n) => n.classList.remove("justech-jx-hit"));
        if (q.length < 2) {
            hint.textContent = "";
            return;
        }
        let target = null;
        for (const sec of catalog) {
            const blob = `${sec.label} ${normalizeNotes(sec.notes).join(" ")} ${(sec.levels || [])
                .map((l) => `${l.label} ${l.warning || ""}`)
                .join(" ")} ${(sec.caps || [])
                .map((c) => `${c.label} ${c.warning || ""}`)
                .join(" ")}`.toLowerCase();
            if (blob.includes(q)) {
                target = sec.key;
                break;
            }
        }
        if (!target) {
            if (q.includes("aplicar") || q.includes("pago")) {
                target = "payments";
            } else if (q.includes("ncf") || q.includes("anular") || q.includes("fiscal")) {
                target = "fiscal";
            } else if (q.includes("b11") || q.includes("b13") || q.includes("b17")) {
                target = "purchase";
            }
        }
        if (!target) {
            hint.textContent = `Sin resultados para «${q}».`;
            return;
        }
        selectModule(target);
        body.querySelector(`[data-jx-module="${target}"]`)?.classList.add("justech-jx-hit");
        const lab = (catalog.find((c) => c.key === target) || {}).label || target;
        hint.textContent = lab;
    });
}

async function enhance(root, orm) {
    if (!root || root.dataset.jxEnhanced === "1") {
        return;
    }
    if (!orm) {
        return;
    }
    const uid = userIdFromPage();
    const mount = root.querySelector(".justech-jx-mount");
    root.dataset.jxEnhanced = "1";
    try {
        const catalog = await orm.call("res.users", "jx_catalog", []);
        if (!uid) {
            delete root.dataset.jxWaiting;
            const pending = loadPending();
            const defaults =
                pending ||
                (await orm.call("res.users", "jx_default_permission_state", []));
            buildUI(root, orm, null, catalog, defaults, { createMode: true });
            return;
        }
        // Existing / just-saved user
        delete root.dataset.jxWaiting;
        const pending = loadPending();
        if (pending) {
            try {
                await orm.call("res.users", "jx_apply_permission_state", [[uid], pending]);
                clearPending();
            } catch (err) {
                console.error("[justech_security_ux] apply pending failed", err);
                root.dataset.jxApplyWarn = "1";
                // Keep pending in sessionStorage for retry; still show server state
            }
        }
        const state = await orm.call("res.users", "jx_permission_state", [[uid]]);
        buildUI(root, orm, uid, catalog, state, { createMode: false });
        if (mount && root.dataset.jxApplyWarn === "1") {
            const banner = el("div", "alert alert-warning mb-2", MSG_APPLY_PARTIAL);
            banner.setAttribute("role", "alert");
            mount.prepend(banner);
            delete root.dataset.jxApplyWarn;
        }
    } catch (err) {
        console.warn("[justech_security_ux] enhance failed", err);
        if (mount) {
            mount.textContent = MSG_LOAD_ERROR;
        }
        delete root.dataset.jxEnhanced;
    }
}

export const __justechJxTest = {
    userIdFromPage,
    loadPending,
    savePending,
    clearPending,
    PENDING_STORAGE_KEY,
    MSG_LOAD_ERROR,
    MSG_APPLY_PARTIAL,
};

registry.category("services").add("justech_permissions_ux", {
    dependencies: ["orm"],
    start(env) {
        const orm = env.services.orm;
        const scan = () => {
            document.querySelectorAll(".justech-jx-page[data-jx-root]").forEach((page) => {
                // Re-enhance when navigating from /new → /<id>
                const uid = userIdFromPage();
                if (page.dataset.jxEnhanced === "1" && page.dataset.jxBoundUid !== String(uid || "")) {
                    delete page.dataset.jxEnhanced;
                }
                page.dataset.jxBoundUid = String(uid || "");
                enhance(page, orm);
            });
        };
        scan();
        setInterval(scan, 1500);
        return {};
    },
});
