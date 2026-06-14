import { api } from "./api.js";

const FEATURES_URL = "/api/features/";

let draw_interaction = null;
let pending_geometry = null;
let _pending_type = "Point";

function deactivate_draw(state) {
  if (draw_interaction) {
    state.map.removeInteraction(draw_interaction);
    draw_interaction = null;
  }
}

function activate_draw(state, type) {
  const ol = window.ol;
  deactivate_draw(state);
  _pending_type = type;
  draw_interaction = new ol.interaction.Draw({
    source: state.source,
    type,
  });
  draw_interaction.on("drawend", (event) => {
    pending_geometry = event.feature.getGeometry();
    const modal = window.bootstrap?.Modal.getOrCreateInstance(document.getElementById("draw-name-modal"));
    const input = document.getElementById("draw-name-input");
    const save_button = document.getElementById("draw-name-save");
    input.value = "";
    save_button.disabled = true;
    document.getElementById("draw-name-alert")?.classList.add("d-none");
    modal?.show();
    setTimeout(() => input.focus(), 100);
  });
  state.map.addInteraction(draw_interaction);
}

async function save_new_feature(state) {
  const ol = window.ol;
  const input = document.getElementById("draw-name-input");
  const alert_box = document.getElementById("draw-name-alert");
  const save_button = document.getElementById("draw-name-save");
  const cancel_button = document.getElementById("draw-name-cancel");
  const name = input.value.trim();
  if (!name) return;
  save_button.disabled = true;
  cancel_button.disabled = true;
  alert_box?.classList.add("d-none");

  const format = new ol.format.GeoJSON();
  try {
    const geometry_geojson = format.writeGeometryObject(pending_geometry, {
      featureProjection: "EPSG:3857",
      dataProjection: "EPSG:4326",
    });
    const feature = await api.post(FEATURES_URL, {
      type: "Feature",
      geometry: geometry_geojson,
      properties: { name },
    });
    const ol_feature = new ol.format.GeoJSON().readFeature(feature);
    ol_feature.set("feature_id", feature.id);
    ol_feature.set("properties", feature.properties);
    state.source.addFeature(ol_feature);
    window.bootstrap?.Modal.getInstance(document.getElementById("draw-name-modal"))?.hide();
    pending_geometry = null;
    deactivate_draw(state);
  } catch (error) {
    alert_box.textContent = error?.message || "Save failed.";
    alert_box?.classList.remove("d-none");
  } finally {
    save_button.disabled = false;
    cancel_button.disabled = false;
  }
}

function discard_pending() {
  pending_geometry = null;
  document.getElementById("draw-name-input").value = "";
  document.getElementById("draw-name-alert")?.classList.add("d-none");
}

function initDraw(state) {
  const _ol = window.ol;
  document.getElementById("draw-point-button")?.addEventListener("click", () => activate_draw(state, "Point"));
  document.getElementById("draw-line-button")?.addEventListener("click", () => activate_draw(state, "LineString"));
  document.getElementById("draw-polygon-button")?.addEventListener("click", () => activate_draw(state, "Polygon"));

  const input = document.getElementById("draw-name-input");
  const save_button = document.getElementById("draw-name-save");
  input?.addEventListener("input", () => {
    save_button.disabled = !input.value.trim();
  });
  input?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && input.value.trim()) {
      event.preventDefault();
      save_new_feature(state);
    } else if (event.key === "Escape") {
      event.preventDefault();
      discard_pending();
      window.bootstrap?.Modal.getInstance(document.getElementById("draw-name-modal"))?.hide();
      deactivate_draw(state);
    }
  });
  document.getElementById("draw-name-save")?.addEventListener("click", () => save_new_feature(state));
  document.getElementById("draw-name-modal")?.addEventListener("hidden.bs.modal", () => {
    if (pending_geometry) {
      discard_pending();
      deactivate_draw(state);
    }
  });
}

export { activate_draw, deactivate_draw, initDraw };
