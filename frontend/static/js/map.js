import { api } from "./api.js";
import { auth } from "./auth.js";
import { initDraw } from "./map-draw.js";
import { initImportExport } from "./map-import.js";
import { initPanel } from "./map-panel.js";

const LIST_URL = "/api/features/";
const DEBOUNCE_MS = 250;
const _PAGE_SIZE = 100;

const map_state = {
  map: null,
  source: null,
  in_flight_bbox: null,
  current_page: 1,
  has_next: false,
};

let moveend_handle = null;

function build_ol_map() {
  const ol = window.ol;
  const map_element = document.getElementById("map");
  if (!map_element || !ol) return null;
  map_state.source = new ol.source.Vector();
  const layer = new ol.layer.Vector({ source: map_state.source, style: feature_style });
  const view = new ol.View({
    center: ol.proj.fromLonLat([5.2913, 52.1326]),
    zoom: 7,
  });
  return new ol.Map({
    target: map_element,
    layers: [new ol.layer.Tile({ source: new ol.source.OSM() }), layer],
    view,
  });
}

function hex_to_rgba(color, alpha) {
  if (typeof color !== "string") return color;
  const match = color.trim().match(/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/);
  if (!match) return color;
  const hex = match[1];
  const full =
    hex.length === 3
      ? hex
          .split("")
          .map((ch) => ch + ch)
          .join("")
      : hex;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function feature_style(feature) {
  const ol = window.ol;
  const properties = feature.get("properties") || {};
  const color = typeof properties.color === "string" && properties.color ? properties.color : "#888888";
  return new ol.style.Style({
    stroke: new ol.style.Stroke({ color, width: 2 }),
    fill: new ol.style.Fill({ color: hex_to_rgba(color, 0.15) }),
    image: new ol.style.Circle({
      radius: 6,
      fill: new ol.style.Fill({ color }),
      stroke: new ol.style.Stroke({ color: "#ffffff", width: 1.5 }),
    }),
  });
}

function get_view_bbox() {
  const ol = window.ol;
  const view = map_state.map.getView();
  const extent = view.calculateExtent(map_state.map.getSize());
  const top_left = ol.proj.toLonLat(ol.extent.getTopLeft(extent));
  const bottom_right = ol.proj.toLonLat(ol.extent.getBottomRight(extent));
  return [
    Math.min(top_left[0], bottom_right[0]),
    Math.min(top_left[1], bottom_right[1]),
    Math.max(top_left[0], bottom_right[0]),
    Math.max(top_left[1], bottom_right[1]),
  ].join(",");
}

function render_features(features) {
  const ol = window.ol;
  map_state.source.clear();
  const format = new ol.format.GeoJSON();
  for (const feature of features) {
    const ol_feature = format.readFeature(feature, { featureProjection: "EPSG:3857" });
    ol_feature.set("feature_id", feature.id);
    ol_feature.set("properties", feature.properties);
    map_state.source.addFeature(ol_feature);
  }
}

async function load_page(bbox, page) {
  const url = `${LIST_URL}?bbox=${encodeURIComponent(bbox)}&page=${page}`;
  const body = await api.get(url);
  return body;
}

async function reload() {
  const bbox = get_view_bbox();
  map_state.in_flight_bbox = bbox;
  const body = await load_page(bbox, 1);
  if (map_state.in_flight_bbox !== bbox) return;
  map_state.current_page = 1;
  map_state.has_next = Boolean(body.next);
  render_features(body.results || []);
  document.getElementById("load-more-button")?.classList.toggle("d-none", !map_state.has_next);
}

async function load_more() {
  if (!map_state.has_next) return;
  const bbox = get_view_bbox();
  const next_page = map_state.current_page + 1;
  const body = await load_page(bbox, next_page);
  if (map_state.in_flight_bbox !== bbox) return;
  map_state.current_page = next_page;
  map_state.has_next = Boolean(body.next);
  const ol = window.ol;
  const format = new ol.format.GeoJSON();
  for (const feature of body.results || []) {
    const ol_feature = format.readFeature(feature, { featureProjection: "EPSG:3857" });
    ol_feature.set("feature_id", feature.id);
    ol_feature.set("properties", feature.properties);
    map_state.source.addFeature(ol_feature);
  }
  document.getElementById("load-more-button")?.classList.toggle("d-none", !map_state.has_next);
}

function on_moveend() {
  if (moveend_handle) clearTimeout(moveend_handle);
  moveend_handle = setTimeout(() => {
    reload().catch(() => {
      // swallow: next moveend retries
    });
  }, DEBOUNCE_MS);
}

function fly_to_feature(feature) {
  const ol = window.ol;
  const view = map_state.map.getView();
  const format = new ol.format.GeoJSON();
  const ol_feature = format.readFeature(feature, { featureProjection: "EPSG:3857" });
  const extent = ol_feature.getGeometry()?.getExtent();
  if (extent) {
    view.fit(extent, { duration: 500, maxZoom: 16, padding: [50, 50, 50, 50] });
  }
  window.dispatchEvent(new CustomEvent("map:open-panel", { detail: { feature } }));
}

function initMap() {
  if (!auth.requireAuth()) return;
  map_state.map = build_ol_map();
  if (!map_state.map) return;
  window.__geojsonMap = map_state;
  map_state.map.on("moveend", on_moveend);
  map_state.map.on("click", (event) => {
    const hit = map_state.map.forEachFeatureAtPixel(event.pixel, (candidate) => candidate);
    if (!hit) return;
    const feature_id = hit.get("feature_id") || hit.getId();
    if (!feature_id) {
      console.error("Cannot open panel: clicked feature has no id", hit);
      return;
    }
    const shallow_properties = hit.get("properties") || _properties_from_ol(hit);
    const feature = {
      id: feature_id,
      geometry: new window.ol.format.GeoJSON().writeGeometryObject(hit.getGeometry(), {
        featureProjection: "EPSG:3857",
        dataProjection: "EPSG:4326",
      }),
      properties: shallow_properties,
      type: "Feature",
    };
    window.dispatchEvent(new CustomEvent("map:open-panel", { detail: { feature } }));
  });
  window.addEventListener("map:fly-to", (event) => {
    fly_to_feature(event.detail.feature);
  });
  window.addEventListener("map:reload", () => {
    reload().catch(() => {
      // swallow: a follow-up moveend retries
    });
  });
  document.getElementById("load-more-button")?.addEventListener("click", () => {
    load_more().catch(() => {
      // swallow: button stays clickable
    });
  });
  initDraw(map_state);
  initImportExport(map_state);
  initPanel(map_state);
  reload().catch(() => {
    // swallow: a follow-up moveend retries
  });
}

initMap();

function _properties_from_ol(ol_feature) {
  const attrs = { ...ol_feature.getProperties() };
  delete attrs.geometry;
  delete attrs.feature_id;
  delete attrs.properties;
  return attrs;
}

export { initMap, map_state };
