import { DEBOUNCE_MS, fetchMatches, renderDropdownRow } from "./search.js";

let debounce_handle = null;
let _active_index = -1;

function closeDropdown() {
  const dropdown = document.getElementById("map-search-dropdown");
  if (!dropdown) return;
  dropdown.classList.add("d-none");
  dropdown.innerHTML = "";
  _active_index = -1;
}

async function performSearch(query) {
  if (!query) {
    closeDropdown();
    return;
  }
  try {
    const results = await fetchMatches(query);
    const dropdown = document.getElementById("map-search-dropdown");
    if (!dropdown) return;
    dropdown.innerHTML = "";
    for (const feature of results) {
      dropdown.appendChild(
        renderDropdownRow(feature, {
          onClick: () => {
            window.dispatchEvent(new CustomEvent("map:fly-to", { detail: { feature } }));
            closeDropdown();
            const input = document.getElementById("map-search-input");
            if (input) {
              input.value = "";
              input.focus();
            }
          },
        }),
      );
    }
    dropdown.classList.remove("d-none");
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
  if (event.key === "Escape") closeDropdown();
}

function onDocumentClick(event) {
  const container = document.getElementById("map-search-container");
  if (container && !container.contains(event.target)) closeDropdown();
}

function initMapSearch() {
  const input = document.getElementById("map-search-input");
  if (!input) return;
  input.addEventListener("input", onInput);
  input.addEventListener("keydown", onKeyDown);
  document.addEventListener("click", onDocumentClick);
}

export { initMapSearch };
