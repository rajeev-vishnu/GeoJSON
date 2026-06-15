// Shared search core.
//
// Used by /map/ (dropdown + fly-to) and /edit/ (live table filter).
// Page-specific wiring lives in search-map.js and search-edit.js.

import { api } from "./api.js";
import { getCategoryLabel } from "./categories.js";

const DEBOUNCE_MS = 250;
const LIST_URL = "/api/features/";

function getName(properties) {
  const name = properties?.name;
  return typeof name === "string" && name ? name : "(unnamed)";
}

function getColor(properties) {
  const color = properties?.color;
  if (typeof color === "string" && /^#[0-9a-fA-F]{3,8}$|^rgb/.test(color)) {
    return color;
  }
  return "#cccccc";
}

async function fetchMatches(query) {
  const body = await api.get(`${LIST_URL}?search=${encodeURIComponent(query)}&page=1`);
  return body.results || [];
}

function renderDropdownRow(feature, { onClick }) {
  const properties = feature.properties || {};
  const name = getName(properties);
  const color = getColor(properties);
  const category_label = getCategoryLabel(properties?.category);
  const geometry_type = feature.geometry?.type || "Unknown";

  const row = document.createElement("li");
  row.className = "list-group-item search-result-row d-flex align-items-center gap-2";
  row.dataset.featureId = feature.id;

  const swatch = document.createElement("span");
  swatch.className = "swatch";
  swatch.style.background = color;

  const nameSpan = document.createElement("span");
  nameSpan.className = "flex-grow-1";
  nameSpan.textContent = name;

  if (category_label) {
    const badge = document.createElement("span");
    badge.className = "badge bg-secondary";
    badge.textContent = category_label;
    row.appendChild(badge);
  }

  const typeSpan = document.createElement("span");
  typeSpan.className = "text-muted small";
  typeSpan.textContent = geometry_type;

  row.appendChild(swatch);
  row.appendChild(nameSpan);
  row.appendChild(typeSpan);

  row.addEventListener("click", onClick);
  return row;
}

export { DEBOUNCE_MS, fetchMatches, renderDropdownRow };
