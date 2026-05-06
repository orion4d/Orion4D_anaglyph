import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const EXT_NAME = "orion4d.anaglyph.presets.v2_2";
const TARGET_COMFY_CLASS = "Orion4D_DepthAnaglyph";
const ROUTE_BASE = "/orion4d/anaglyph";

const PRESET_UI_WIDGETS = new Set([
    "orion4d_preset",
    "orion4d_refresh_presets",
    "orion4d_load_preset",
    "orion4d_save_new_preset",
    "orion4d_update_preset",
    "orion4d_delete_preset",
    "orion4d_reset_defaults",
]);

function findWidget(node, name) {
    return node.widgets?.find((w) => w.name === name) || null;
}

function isSerializableValue(value) {
    if (value === undefined) return false;
    if (typeof value === "function") return false;

    try {
        JSON.stringify(value);
        return true;
    } catch (e) {
        return false;
    }
}

function getWidgetValue(widget) {
    if (!widget) return undefined;
    return widget.value;
}

function setWidgetValue(widget, value, node) {
    if (!widget) return;

    widget.value = value;

    try {
        if (widget.callback) {
            widget.callback.call(widget, value, node, widget);
        }
    } catch (e) {
        console.warn("[Orion4D] widget callback failed:", widget.name, e);
    }

    try {
        if (node?.onWidgetChanged) {
            node.onWidgetChanged(widget.name, value, widget);
        }
    } catch (e) {
        console.warn("[Orion4D] onWidgetChanged failed:", widget.name, e);
    }
}

function collectNodeValues(node) {
    const values = {};

    for (const widget of node.widgets || []) {
        if (!widget || !widget.name) continue;
        if (PRESET_UI_WIDGETS.has(widget.name)) continue;
        if (widget.type === "button") continue;

        const value = getWidgetValue(widget);
        if (!isSerializableValue(value)) continue;

        values[widget.name] = value;
    }

    return values;
}

function applyNodeValues(node, values) {
    if (!values || typeof values !== "object") return;

    let count = 0;

    for (const [name, value] of Object.entries(values)) {
        const widget = findWidget(node, name);
        if (!widget) {
            console.warn("[Orion4D] preset value ignored, widget not found:", name);
            continue;
        }

        setWidgetValue(widget, value, node);
        count++;
    }

    node.setDirtyCanvas?.(true, true);
    node.graph?.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);

    return count;
}

async function getJSON(url, opts = {}) {
    const res = await api.fetchApi(url, opts);

    if (!res.ok) {
        let text = "";

        try {
            text = await res.text();
        } catch (e) {}

        throw new Error(text || `HTTP ${res.status}`);
    }

    return await res.json();
}

function showMessage(msg) {
    try {
        app.extensionManager.toast?.add({
            severity: "info",
            summary: "Orion4D",
            detail: msg,
            life: 2500,
        });
    } catch (e) {
        console.log("[Orion4D]", msg);
    }
}

function showError(msg) {
    try {
        app.extensionManager.toast?.add({
            severity: "error",
            summary: "Orion4D",
            detail: msg,
            life: 4500,
        });
    } catch (e) {
        console.error("[Orion4D]", msg);
    }
}

function selectedPresetName(node) {
    const presetWidget = findWidget(node, "orion4d_preset");
    if (!presetWidget) return null;

    const raw = presetWidget.value;

    if (!raw || raw === "<no preset>" || raw === "<loading...>") return null;

    return String(raw).trim();
}

async function refreshPresetChoices(node) {
    const presetWidget = findWidget(node, "orion4d_preset");
    if (!presetWidget) return;

    const data = await getJSON(`${ROUTE_BASE}/presets`);
    const choices = (data.presets || []).map((p) => p.name);

    node.__orion4dSuppressPresetAutoLoad = true;

    presetWidget.options = presetWidget.options || {};
    presetWidget.options.values = choices.length ? choices : ["<no preset>"];

    if (!choices.length) {
        presetWidget.value = "<no preset>";
    } else if (!choices.includes(presetWidget.value)) {
        presetWidget.value = choices[0];
    }

    node.__orion4dSuppressPresetAutoLoad = false;

    node.setDirtyCanvas?.(true, true);
    node.graph?.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

async function loadSelectedPreset(node) {
    const name = selectedPresetName(node);

    if (!name) {
        showError("Aucun preset sélectionné.");
        return;
    }

    const data = await getJSON(`${ROUTE_BASE}/preset/${encodeURIComponent(name)}`);

    if (!data.ok || !data.preset) {
        throw new Error(data.error || "Impossible de charger le preset.");
    }

    const changed = applyNodeValues(node, data.preset.values);

    showMessage(`Preset chargé : ${name} (${changed || 0} réglages appliqués)`);
}

async function resetDefaults(node) {
    const data = await getJSON(`${ROUTE_BASE}/defaults`);

    if (!data.ok || !data.defaults) {
        throw new Error(data.error || "Impossible de charger les valeurs par défaut.");
    }

    const changed = applyNodeValues(node, data.defaults);

    showMessage(`Réglages par défaut restaurés (${changed || 0} réglages appliqués).`);
}

async function savePreset(node, name) {
    const payload = {
        name,
        values: collectNodeValues(node),
    };

    const data = await getJSON(`${ROUTE_BASE}/save`, {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
            "Content-Type": "application/json",
        },
    });

    if (!data.ok) {
        throw new Error(data.error || "Impossible d'enregistrer le preset.");
    }

    await refreshPresetChoices(node);

    const presetWidget = findWidget(node, "orion4d_preset");
    if (presetWidget) presetWidget.value = data.preset.name;

    return data.preset;
}

async function saveNewPreset(node) {
    const input = prompt("Nom du nouveau preset :", "My Preset");

    if (!input) return;

    const preset = await savePreset(node, input);

    showMessage(`Preset enregistré : ${preset.name}`);
}

async function updatePreset(node) {
    const name = selectedPresetName(node);

    if (!name) {
        showError("Aucun preset sélectionné.");
        return;
    }

    const preset = await savePreset(node, name);

    showMessage(`Preset mis à jour : ${preset.name}`);
}

async function deletePreset(node) {
    const name = selectedPresetName(node);

    if (!name) {
        showError("Aucun preset sélectionné.");
        return;
    }

    if (!confirm(`Supprimer le preset "${name}" ?`)) return;

    const data = await getJSON(`${ROUTE_BASE}/delete`, {
        method: "POST",
        body: JSON.stringify({ name }),
        headers: {
            "Content-Type": "application/json",
        },
    });

    if (!data.ok) {
        throw new Error(data.error || "Impossible de supprimer le preset.");
    }

    await refreshPresetChoices(node);

    showMessage(`Preset supprimé : ${name}`);
}

function attachPresetWidgets(node) {
    if (node.__orion4dPresetWidgetsAttached) return;
    node.__orion4dPresetWidgetsAttached = true;

    node.addWidget(
        "combo",
        "orion4d_preset",
        "<loading...>",
        async () => {
            if (node.__orion4dSuppressPresetAutoLoad) return;

            try {
                await loadSelectedPreset(node);
            } catch (e) {
                showError(e.message || String(e));
            }
        },
        {
            values: ["<loading...>"],
        }
    );

    node.addWidget("button", "orion4d_refresh_presets", "Refresh Presets", async () => {
        try {
            await refreshPresetChoices(node);
            showMessage("Liste des presets rechargée.");
        } catch (e) {
            showError(e.message || String(e));
        }
    });

    node.addWidget("button", "orion4d_load_preset", "Load Preset", async () => {
        try {
            await loadSelectedPreset(node);
        } catch (e) {
            showError(e.message || String(e));
        }
    });

    node.addWidget("button", "orion4d_save_new_preset", "Save New Preset", async () => {
        try {
            await saveNewPreset(node);
        } catch (e) {
            showError(e.message || String(e));
        }
    });

    node.addWidget("button", "orion4d_update_preset", "Update Selected Preset", async () => {
        try {
            await updatePreset(node);
        } catch (e) {
            showError(e.message || String(e));
        }
    });

    node.addWidget("button", "orion4d_delete_preset", "Delete Selected Preset", async () => {
        try {
            await deletePreset(node);
        } catch (e) {
            showError(e.message || String(e));
        }
    });

    node.addWidget("button", "orion4d_reset_defaults", "Reset Defaults", async () => {
        try {
            await resetDefaults(node);
        } catch (e) {
            showError(e.message || String(e));
        }
    });

    refreshPresetChoices(node).catch((e) => showError(e.message || String(e)));
}

app.registerExtension({
    name: EXT_NAME,

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData?.name !== TARGET_COMFY_CLASS) return;

        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const result = originalOnNodeCreated?.apply(this, arguments);
            attachPresetWidgets(this);
            return result;
        };
    },
});
