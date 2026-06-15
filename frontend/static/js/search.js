import { api } from "./api.js";
import { getCategoryLabel } from "./categories.js";

const DEBOUNCE_MS = 250;
const LIST_URL = "/api/features/";

let debounce_handle = null;
let _active_index = -1;

function isVisible() {
  const input = document.getElementById("search-input");
  return Boolean(input);
}

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

function getBadgeLabel(properties) {
  return getCategoryLabel(properties?.category);
}

function closeDropdown() {
  const dropdown = document.getElementById("search-dropdown");
  if (!dropdown) return;
  dropdown.classList.add("d-none");
  dropdown.innerHTML = "";
  _active_index = -1;
}

function renderRows(features) {
  const dropdown = document.getElementById("search-dropdown");
  if (!dropdown) return;
  dropdown.innerHTML = "";
  for (const feature of features) {
    const properties = feature.properties || {};
    const name = getName(properties);
    const color = getColor(properties);
    const category_label = getBadgeLabel(properties);
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

    row.addEventListener("click", () => {
      window.dispatchEvent(new CustomEvent("map:fly-to", { detail: { feature } }));
      closeDropdown();
    });
    dropdown.appendChild(row);
  }
  dropdown.classList.remove("d-none");
}

async function performSearch(query) {
  if (!query) {
    closeDropdown();
    return;
  }
  try {
    const body = await api.get(`${LIST_URL}?search=${encodeURIComponent(query)}&page=1`);
    renderRows(body.results || []);
  } catch (_error) {
    closeDropdown();
  }
}

function onInput(event) {
  if (debounce_handle) clearTimeout(debounce_handle);
  const query = event.target.value.trim();
  debounce_handle = setTimeout(() => performSearch(query), DEBOUNCE_MS);
}

function onKeyDown(event) {
  if (event.key === "Escape") {
    closeDropdown();
  }
}

function onDocumentClick(event) {
  const container = document.getElementById("search-container");
  if (container && !container.contains(event.target)) {
    closeDropdown();
  }
}

function initSearch() {
  if (!isVisible()) return;
  const input = document.getElementById("search-input");
  input.addEventListener("input", onInput);
  input.addEventListener("keydown", onKeyDown);
  document.addEventListener("click", onDocumentClick);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDropdown();
  });
}

initSearch();

export { initSearch };
