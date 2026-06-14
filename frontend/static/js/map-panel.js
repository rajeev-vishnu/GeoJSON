import { api } from "./api.js";
import { categories } from "./search.js";

function open() {
  document.getElementById("panel").classList.add("open");
  document.getElementById("panel").setAttribute("aria-hidden", "false");
}

function close() {
  document.getElementById("panel").classList.remove("open");
  document.getElementById("panel").setAttribute("aria-hidden", "true");
}

function show_alert(message) {
  const box = document.getElementById("panel-alert");
  if (!box) return;
  box.textContent = message;
  box.classList.remove("d-none");
}

function clear_alert() {
  document.getElementById("panel-alert")?.classList.add("d-none");
}

function clear_table() {
  document.getElementById("panel-properties-tbody").innerHTML = "";
}

function render_property_row(key, value) {
  const tbody = document.getElementById("panel-properties-tbody");
  const row = document.createElement("tr");
  row.dataset.key = key;

  const key_cell = document.createElement("td");
  key_cell.textContent = key;
  key_cell.className = "text-muted";

  const value_cell = document.createElement("td");
  value_cell.contentEditable = "true";
  value_cell.spellcheck = false;
  value_cell.textContent = value === null || value === undefined ? "" : String(value);
  value_cell.dataset.original = value_cell.textContent;

  const action_cell = document.createElement("td");
  const delete_button = document.createElement("button");
  delete_button.type = "button";
  delete_button.className = "btn btn-sm btn-outline-danger";
  delete_button.textContent = "×";
  delete_button.title = "Delete property";
  action_cell.appendChild(delete_button);

  row.appendChild(key_cell);
  row.appendChild(value_cell);
  row.appendChild(action_cell);
  tbody.appendChild(row);

  value_cell.addEventListener("keydown", async (event) => {
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
    const next = value_cell.textContent;
    if (next === value_cell.dataset.original) return;
    const feature_id = row.closest("aside").dataset.featureId;
    let parsed = next;
    if (typeof value_cell.dataset.original === "string") {
      const original = value_cell.dataset.original;
      const original_number = Number(original);
      if (original.trim() !== "" && !Number.isNaN(original_number)) {
        const as_number = Number(next);
        if (!Number.isNaN(as_number)) parsed = as_number;
      }
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
    const feature_id = row.closest("aside").dataset.featureId;
    try {
      await api.patch(`/api/features/${feature_id}/`, {
        properties: { [key]: null },
      });
      row.remove();
      clear_alert();
    } catch (error) {
      show_alert(error?.message || "Delete failed.");
    }
  });
}

function render_category_row(feature) {
  const tbody = document.getElementById("panel-properties-tbody");
  const row = document.createElement("tr");
  row.dataset.key = "category";

  const key_cell = document.createElement("td");
  key_cell.textContent = "category";
  key_cell.className = "text-muted";

  const value_cell = document.createElement("td");
  const select = document.createElement("select");
  select.className = "form-select form-select-sm";
  const current = feature.properties?.category || "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "(none)";
  select.appendChild(placeholder);
  for (const value of categories) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
  const other = document.createElement("option");
  other.value = "__other__";
  other.textContent = "other…";
  select.appendChild(other);
  if (current && ![...select.options].some((opt) => opt.value === current)) {
    const custom = document.createElement("option");
    custom.value = current;
    custom.textContent = `${current} (custom)`;
    select.insertBefore(custom, other);
  }
  select.value =
    current && [...select.options].some((opt) => opt.value === current) ? current : current ? "__other__" : "";
  if (select.value === "__other__") {
    const custom_input = document.createElement("input");
    custom_input.type = "text";
    custom_input.className = "form-control form-control-sm mt-1";
    custom_input.value = current && select.querySelector(`option[value="${current}"]`) ? "" : current;
    custom_input.placeholder = "Custom category";
    value_cell.appendChild(select);
    value_cell.appendChild(custom_input);
  } else {
    value_cell.appendChild(select);
  }

  const action_cell = document.createElement("td");

  row.appendChild(key_cell);
  row.appendChild(value_cell);
  row.appendChild(action_cell);
  tbody.appendChild(row);

  async function commit() {
    const feature_id = row.closest("aside").dataset.featureId;
    let next = select.value;
    if (next === "__other__") {
      next = value_cell.querySelector("input")?.value || "";
    }
    try {
      const updated = await api.patch(`/api/features/${feature_id}/`, {
        properties: { category: next || null },
      });
      select.value = updated.properties?.category || "";
      clear_alert();
    } catch (error) {
      show_alert(error?.message || "Save failed.");
    }
  }
  select.addEventListener("change", commit);
  select.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    } else if (event.key === "Escape") {
      event.preventDefault();
      select.value = feature.properties?.category || "";
    }
  });
}

async function open_feature(feature) {
  const panel = document.getElementById("panel");
  panel.dataset.featureId = feature.id;
  clear_alert();
  clear_table();
  let detail = feature;
  try {
    detail = await api.get(`/api/features/${feature.id}/`);
  } catch (_error) {
    // fall back to the shallow feature
  }
  for (const [key, value] of Object.entries(detail.properties || {})) {
    if (key === "_audit") continue;
    if (key === "category") {
      render_category_row(detail);
    } else {
      render_property_row(key, value);
    }
  }
  open();
}

async function delete_feature() {
  const panel = document.getElementById("panel");
  const feature_id = panel.dataset.featureId;
  if (!feature_id) return;
  if (!window.confirm("Delete this feature?")) return;
  try {
    await api.delete(`/api/features/${feature_id}/`);
    close();
    window.dispatchEvent(new CustomEvent("map:reload"));
  } catch (error) {
    show_alert(error?.message || "Delete failed.");
  }
}

function initPanel(_state) {
  document.getElementById("panel-close")?.addEventListener("click", close);
  document.getElementById("panel-delete")?.addEventListener("click", delete_feature);
  window.addEventListener("map:open-panel", (event) => {
    open_feature(event.detail.feature).catch((error) => {
      show_alert(error?.message || "Failed to load feature.");
    });
  });
}

export { initPanel };
