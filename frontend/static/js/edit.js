import { api } from "./api.js";
import { auth } from "./auth.js";
import { renderCategorySelect } from "./categories.js";

const LIST_URL = "/api/features/";
const ALLOWED_ORDERING = ["created_at", "-created_at", "updated_at", "-updated_at"];
const _MISSING_COLOR = "#cccccc";

let current_page = 1;
let current_ordering = "-updated_at";
let next_url = null;
let prev_url = null;

function show_alert(message) {
  const box = document.getElementById("edit-alert");
  if (!box) return;
  box.textContent = message;
  box.classList.remove("d-none");
}

function clear_alert() {
  document.getElementById("edit-alert")?.classList.add("d-none");
}

function clear_table() {
  document.getElementById("features-tbody").innerHTML = "";
}

function render_property_row(feature_id, key, value) {
  const tbody = document.getElementById("features-tbody");
  const row = document.createElement("tr");
  row.dataset.key = key;
  const key_cell = document.createElement("td");
  key_cell.textContent = key;
  key_cell.className = "text-muted small";
  const value_cell = document.createElement("td");
  const action_cell = document.createElement("td");
  const delete_button = document.createElement("button");
  delete_button.type = "button";
  delete_button.className = "btn btn-sm btn-outline-danger";
  delete_button.textContent = "×";
  action_cell.appendChild(delete_button);

  row.appendChild(key_cell);
  row.appendChild(value_cell);
  row.appendChild(action_cell);
  tbody.appendChild(row);

  if (typeof value === "boolean") {
    const select = document.createElement("select");
    select.className = "form-select form-select-sm";
    for (const option_value of ["true", "false"]) {
      const option = document.createElement("option");
      option.value = option_value;
      option.textContent = option_value;
      if (String(value) === option_value) option.selected = true;
      select.appendChild(option);
    }
    value_cell.appendChild(select);
    select.addEventListener("change", async () => {
      const next = select.value === "true";
      try {
        await api.patch(`/api/features/${feature_id}/`, {
          properties: { [key]: next },
        });
        clear_alert();
      } catch (error) {
        show_alert(error?.message || "Save failed.");
        select.value = String(value);
      }
    });
    return row;
  }

  value_cell.contentEditable = "true";
  value_cell.spellcheck = false;
  value_cell.textContent = value === null || value === undefined ? "" : String(value);
  value_cell.dataset.original = value_cell.textContent;
  value_cell.dataset.type = typeof value;

  value_cell.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      value_cell.blur();
    } else if (event.key === "Escape") {
      event.preventDefault();
      value_cell.textContent = value_cell.dataset.original;
      value_cell.blur();
    }
  });
  value_cell.addEventListener("blur", async () => {
    const next_text = value_cell.textContent;
    if (next_text === value_cell.dataset.original) return;
    let parsed = next_text;
    if (value_cell.dataset.type === "number") {
      const as_number = Number(next_text);
      if (Number.isNaN(as_number)) {
        show_alert(`Value for "${key}" must be numeric.`);
        value_cell.textContent = value_cell.dataset.original;
        return;
      }
      parsed = as_number;
    }
    try {
      const updated = await api.patch(`/api/features/${feature_id}/`, {
        properties: { [key]: parsed },
      });
      value_cell.dataset.original = String(updated.properties?.[key] ?? "");
      value_cell.textContent = value_cell.dataset.original;
      clear_alert();
    } catch (error) {
      show_alert(error?.message || "Save failed.");
      value_cell.textContent = value_cell.dataset.original;
    }
  });
  delete_button.addEventListener("click", async () => {
    try {
      await api.patch(`/api/features/${feature_id}/`, { properties: { [key]: null } });
      row.remove();
      clear_alert();
    } catch (error) {
      show_alert(error?.message || "Delete failed.");
    }
  });
  return row;
}

function render_add_new_row(feature_id, parent_tbody) {
  const row = document.createElement("tr");
  row.dataset.addNew = "true";
  const key_cell = document.createElement("td");
  const key_input = document.createElement("input");
  key_input.type = "text";
  key_input.maxLength = 100;
  key_input.className = "form-control form-control-sm";
  key_input.placeholder = "key";
  key_cell.appendChild(key_input);

  const type_cell = document.createElement("td");
  const type_select = document.createElement("select");
  type_select.className = "form-select form-select-sm";
  for (const value of ["str", "int", "float", "bool"]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    type_select.appendChild(option);
  }
  type_cell.appendChild(type_select);

  const value_cell = document.createElement("td");
  let value_input = document.createElement("input");
  value_input.className = "form-control form-control-sm";
  value_cell.appendChild(value_input);

  const action_cell = document.createElement("td");
  const save_button = document.createElement("button");
  save_button.type = "button";
  save_button.className = "btn btn-sm btn-primary me-1";
  save_button.textContent = "Save";
  save_button.disabled = true;
  const cancel_button = document.createElement("button");
  cancel_button.type = "button";
  cancel_button.className = "btn btn-sm btn-outline-secondary";
  cancel_button.textContent = "×";
  action_cell.appendChild(save_button);
  action_cell.appendChild(cancel_button);

  row.appendChild(key_cell);
  row.appendChild(type_cell);
  row.appendChild(value_cell);
  row.appendChild(action_cell);
  parent_tbody.appendChild(row);

  function update_save_button() {
    save_button.disabled = !key_input.value.trim();
  }
  function update_value_input() {
    value_input.innerHTML = "";
    if (type_select.value === "bool") {
      const select = document.createElement("select");
      select.className = "form-select form-select-sm";
      for (const value of ["true", "false"]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }
      value_input.replaceWith(select);
      value_input = select;
      value_input.value = "true";
    } else {
      const input = document.createElement("input");
      input.type = type_select.value === "str" ? "text" : "number";
      if (type_select.value === "float") input.step = "any";
      input.className = "form-control form-control-sm";
      value_input.replaceWith(input);
      value_input = input;
    }
  }
  key_input.addEventListener("input", update_save_button);
  type_select.addEventListener("change", update_value_input);
  cancel_button.addEventListener("click", () => row.remove());
  save_button.addEventListener("click", async () => {
    const key = key_input.value.trim();
    if (!key) return;
    let value;
    if (type_select.value === "str") {
      value = value_input.value;
    } else if (type_select.value === "int") {
      const as_int = parseInt(value_input.value, 10);
      if (Number.isNaN(as_int) || String(as_int) !== String(value_input.value)) {
        show_alert(`Value for "${key}" must be an integer.`);
        return;
      }
      value = as_int;
    } else if (type_select.value === "float") {
      const as_float = parseFloat(value_input.value);
      if (Number.isNaN(as_float)) {
        show_alert(`Value for "${key}" must be a number.`);
        return;
      }
      value = as_float;
    } else if (type_select.value === "bool") {
      value = value_input.value === "true";
    }
    try {
      const updated = await api.patch(`/api/features/${feature_id}/`, {
        properties: { [key]: value },
      });
      clear_alert();
      row.remove();
      render_property_row(feature_id, key, updated.properties?.[key]);
    } catch (error) {
      show_alert(error?.message || "Save failed.");
    }
  });
  update_save_button();
  update_value_input();
}

function render_feature(feature) {
  const tbody = document.getElementById("features-tbody");
  const row = document.createElement("tr");
  row.dataset.featureId = feature.id;
  row.className = "feature-row";

  const name_cell = render_name_cell(feature);
  const color_cell = render_color_cell(feature);
  const category_cell = render_category_cell(feature);
  const type_cell = document.createElement("td");
  type_cell.textContent = feature.geometry?.type || "";

  const properties_cell = document.createElement("td");
  const properties_table = document.createElement("table");
  properties_table.className = "table table-sm mb-0";
  const properties_tbody = document.createElement("tbody");
  properties_table.appendChild(properties_tbody);
  properties_cell.appendChild(properties_table);

  const add_button = document.createElement("button");
  add_button.type = "button";
  add_button.className = "btn btn-sm btn-outline-primary mt-2";
  add_button.textContent = "+ add new property";
  add_button.addEventListener("click", () => render_add_new_row(feature.id, properties_tbody));
  properties_cell.appendChild(add_button);

  row.appendChild(name_cell);
  row.appendChild(color_cell);
  row.appendChild(category_cell);
  row.appendChild(type_cell);
  row.appendChild(properties_cell);
  tbody.appendChild(row);

  for (const [key, value] of Object.entries(feature.properties || {})) {
    if (key === "_audit" || key === "name" || key === "color" || key === "category") continue;
    render_property_row(feature.id, key, value);
  }
}

function render_name_cell(feature) {
  const cell = document.createElement("td");
  cell.contentEditable = "true";
  cell.spellcheck = false;
  const original = (feature.properties?.name || "").toString();
  cell.textContent = original || "(unnamed)";
  cell.dataset.original = original;

  cell.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      cell.blur();
    } else if (event.key === "Escape") {
      event.preventDefault();
      cell.textContent = cell.dataset.original || "(unnamed)";
      cell.blur();
    }
  });
  cell.addEventListener("blur", async () => {
    const next = cell.textContent === "(unnamed)" ? "" : cell.textContent;
    if (next === cell.dataset.original) return;
    if (!next) {
      show_alert("Name must be a non-empty string.");
      cell.textContent = cell.dataset.original || "(unnamed)";
      return;
    }
    try {
      const updated = await api.patch(`/api/features/${feature.id}/`, {
        properties: { name: next },
      });
      cell.dataset.original = updated.properties?.name ?? next;
      cell.textContent = cell.dataset.original;
      clear_alert();
    } catch (error) {
      show_alert(error?.message || "Save failed.");
      cell.textContent = cell.dataset.original || "(unnamed)";
    }
  });
  return cell;
}

function render_color_cell(feature) {
  const cell = document.createElement("td");
  const wrapper = document.createElement("div");
  wrapper.className = "d-flex align-items-center gap-2";
  const swatch = document.createElement("span");
  swatch.className = "swatch";
  const stored = feature.properties?.color;
  const fallback = stored && /^#[0-9a-fA-F]{6}$/.test(stored) ? stored : _MISSING_COLOR;
  swatch.style.background = fallback;
  const picker = document.createElement("input");
  picker.type = "color";
  picker.className = "form-control form-control-color form-control-sm";
  picker.value = fallback;
  picker.dataset.original = stored || "";
  picker.title = "Pick a color";
  picker.addEventListener("change", async () => {
    const next = picker.value;
    if (next === picker.dataset.original) return;
    try {
      const updated = await api.patch(`/api/features/${feature.id}/`, {
        properties: { color: next },
      });
      const server_color = updated.properties?.color;
      swatch.style.background = server_color || next;
      picker.dataset.original = server_color || next;
      picker.value = server_color || next;
      clear_alert();
    } catch (error) {
      show_alert(error?.message || "Save failed.");
      picker.value = picker.dataset.original || _MISSING_COLOR;
      swatch.style.background = picker.dataset.original || _MISSING_COLOR;
    }
  });
  wrapper.appendChild(swatch);
  wrapper.appendChild(picker);
  cell.appendChild(wrapper);
  return cell;
}

function render_category_cell(feature) {
  const cell = document.createElement("td");
  const select = renderCategorySelect({ current: feature.properties?.category });
  select.dataset.original = feature.properties?.category || "";
  select.addEventListener("change", async () => {
    const next = select.value || null;
    const original = select.dataset.original || null;
    if (next === original) return;
    try {
      const updated = await api.patch(`/api/features/${feature.id}/`, {
        properties: { category: next },
      });
      select.dataset.original = updated.properties?.category || "";
      select.value = select.dataset.original;
      clear_alert();
    } catch (error) {
      show_alert(error?.message || "Save failed.");
      select.value = original || "";
    }
  });
  cell.appendChild(select);
  return cell;
}

async function load_page() {
  try {
    const url = `${LIST_URL}?page=${current_page}&ordering=${encodeURIComponent(current_ordering)}`;
    const body = await api.get(url);
    clear_table();
    for (const feature of body.results || []) {
      render_feature(feature);
    }
    next_url = body.next;
    prev_url = body.prev;
    document.getElementById("page-prev").disabled = !prev_url;
    document.getElementById("page-next").disabled = !next_url;
    document.getElementById("page-indicator").textContent = `Page ${current_page}`;
    clear_alert();
  } catch (error) {
    show_alert(error?.message || "Failed to load features.");
  }
}

function initEdit() {
  if (!auth.requireAuth()) return;
  document.getElementById("sort-order")?.addEventListener("change", (event) => {
    const next = event.target.value;
    if (ALLOWED_ORDERING.includes(next)) {
      current_ordering = next;
      current_page = 1;
      load_page();
    }
  });
  document.getElementById("page-prev")?.addEventListener("click", () => {
    if (current_page > 1) {
      current_page -= 1;
      load_page();
    }
  });
  document.getElementById("page-next")?.addEventListener("click", () => {
    current_page += 1;
    load_page();
  });
  load_page();
}

initEdit();

export { initEdit, render_add_new_row, render_property_row };
