import { api } from "./api.js";

const FEATURES_URL = "/api/features/";

function read_file(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

function collect_features(collection) {
  if (collection?.type === "FeatureCollection" && Array.isArray(collection.features)) {
    return collection.features;
  }
  if (collection?.type === "Feature") {
    return [collection];
  }
  return [];
}

function show_import_status(imported, failed) {
  const status = document.getElementById("import-status");
  if (!status) return;
  status.textContent = `Imported ${imported} of ${imported + failed}; ${failed} failed.`;
  status.classList.remove("d-none", "alert-success", "alert-danger", "alert-warning");
  if (failed === 0) {
    status.classList.add("alert-success");
  } else if (imported === 0) {
    status.classList.add("alert-danger");
  } else {
    status.classList.add("alert-warning");
  }
}

async function import_file(state) {
  const file_input = document.getElementById("import-file-input");
  if (!file_input.files?.[0]) return;
  const text = await read_file(file_input.files[0]);
  const collection = JSON.parse(text);
  const features = collect_features(collection);

  const ol = window.ol;
  const format = ol ? new ol.format.GeoJSON() : null;
  let imported = 0;
  let failed = 0;
  for (const feature of features) {
    const body = {
      type: "Feature",
      geometry: feature.geometry,
      properties: feature.properties ?? {},
    };
    try {
      const created = await api.post(FEATURES_URL, body);
      if (state?.source && created) {
        const saved_feature = format
          ? format.readFeature(created, { featureProjection: "EPSG:3857" })
          : { feature_id: created.id, properties: created.properties, geometry: created.geometry };
        saved_feature.set("feature_id", created.id);
        saved_feature.set("properties", created.properties);
        state.source.addFeature(saved_feature);
      }
      imported += 1;
    } catch (error) {
      failed += 1;
      console.error("Import failed for feature", feature, error);
    }
  }
  console.info(`Imported ${imported} feature(s); ${failed} failed.`);
  show_import_status(imported, failed);
  window.dispatchEvent(new CustomEvent("map:reload"));
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
    import_file(state).catch((error) => {
      console.error("Import flow failed:", error);
    });
  });
  document.getElementById("export-button")?.addEventListener("click", () => export_features(state));
}

export { initImportExport };
