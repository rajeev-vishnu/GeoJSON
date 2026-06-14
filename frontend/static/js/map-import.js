import { api } from "./api.js";

const FEATURES_URL = "/api/features/";

let import_layer = null;

function read_file(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

async function import_file(state) {
  const ol = window.ol;
  const file_input = document.getElementById("import-file-input");
  if (!file_input.files?.[0]) return;
  const text = await read_file(file_input.files[0]);
  const collection = JSON.parse(text);
  if (import_layer) state.map.removeLayer(import_layer);
  import_layer = new ol.layer.Vector({ source: new ol.source.Vector() });
  const format = new ol.format.GeoJSON();
  const features = format.readFeatures(collection, { featureProjection: "EPSG:3857", dataProjection: "EPSG:4326" });
  import_layer.getSource().addFeatures(features);
  state.map.addLayer(import_layer);

  if (!window.confirm(`Import ${features.length} features to the server?`)) {
    state.map.removeLayer(import_layer);
    import_layer = null;
    return;
  }

  const writer = new ol.format.GeoJSON();
  for (const ol_feature of features) {
    const geometry = writer.writeGeometryObject(ol_feature.getGeometry(), {
      featureProjection: "EPSG:3857",
      dataProjection: "EPSG:4326",
    });
    const properties = ol_feature.get("properties") || {};
    try {
      const created = await api.post(FEATURES_URL, {
        type: "Feature",
        geometry,
        properties,
      });
      const saved_feature = new ol.format.GeoJSON().readFeature(created);
      saved_feature.set("feature_id", created.id);
      saved_feature.set("properties", created.properties);
      state.source.addFeature(saved_feature);
    } catch (_error) {
      // continue with remaining features
    }
  }
  state.map.removeLayer(import_layer);
  import_layer = null;
  file_input.value = "";
}

function export_features(state) {
  const ol = window.ol;
  const format = new ol.format.GeoJSON();
  const features = state.source.getFeatures().map((ol_feature) => {
    const cloned = new ol.Feature({
      geometry: ol_feature.getGeometry()?.clone(),
    });
    cloned.set("feature_id", ol_feature.get("feature_id"));
    cloned.set("properties", ol_feature.get("properties") || {});
    return cloned;
  });
  const geojson = format.writeFeatures(features, {
    featureProjection: "EPSG:3857",
    dataProjection: "EPSG:4326",
  });
  const blob = new Blob([geojson], { type: "application/geo+json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "features.geojson";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function initImportExport(state) {
  document.getElementById("import-button")?.addEventListener("click", () => {
    document.getElementById("import-file-input").click();
  });
  document.getElementById("import-file-input")?.addEventListener("change", () => {
    import_file(state).catch(() => {
      // ignore: file picker stays available
    });
  });
  document.getElementById("export-button")?.addEventListener("click", () => export_features(state));
}

export { initImportExport };
