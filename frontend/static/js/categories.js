// Single source of truth for the 11 Feature categories on the frontend.
//
// Keep the KEYS in sync with `features.models.Feature.Category` values
// (the wire format: "city", "town", ...). The LABELS match the enum's
// .label attribute exactly (e.g. "Nature reserve" for "nature_reserve").
//
// Both the /edit/ page and the /map/ side panel render the category
// <select> from this map so the two surfaces cannot drift.

import { api } from "./api.js";

const CATEGORIES_URL = "/api/categories/";

export const CATEGORY_LABELS = {
  city: "City",
  town: "Town",
  road: "Road",
  river: "River",
  canal: "Canal",
  rail: "Rail",
  park: "Park",
  lake: "Lake",
  province: "Province",
  nature_reserve: "Nature reserve",
  country: "Country",
};

let _cache = null;

export async function loadCategories() {
  if (_cache) return _cache;
  _cache = await api.get(CATEGORIES_URL);
  return _cache;
}

export function getCategoryLabel(value) {
  if (typeof value !== "string" || !value) return null;
  return CATEGORY_LABELS[value] ?? value;
}

export function renderCategorySelect({ current = null } = {}) {
  const select = document.createElement("select");
  select.className = "form-select form-select-sm";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "(none)";
  select.appendChild(placeholder);

  for (const [value, label] of Object.entries(CATEGORY_LABELS)) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    select.appendChild(option);
  }

  select.value = CATEGORY_LABELS[current] ? current : "";
  return select;
}
