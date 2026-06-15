import { DEBOUNCE_MS } from "./search.js";

let debounce_handle = null;

function readQuery() {
  const input = document.getElementById("edit-search-input");
  return input ? input.value.trim() : "";
}

function onInput(event, { onChange }) {
  if (debounce_handle) clearTimeout(debounce_handle);
  const query = event.target.value.trim();
  debounce_handle = setTimeout(() => onChange({ search: query }), DEBOUNCE_MS);
}

function initEditSearch({ onChange }) {
  const input = document.getElementById("edit-search-input");
  if (!input) return;
  input.addEventListener("input", (event) => onInput(event, { onChange }));
}

export { initEditSearch, readQuery };
