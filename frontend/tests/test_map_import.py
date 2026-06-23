"""Behavioral contract tests for `frontend/static/js/map-import.js`.

These tests are file-content assertions (the same fidelity the rest of
`frontend/tests/test_static.py` uses). They lock in the import-flow
contract:

  - The import path does not touch `window.ol` / OpenLayers. Import
    sends the file's GeoJSON straight to the API.
  - Each feature is POSTed as `{type: "Feature", geometry, properties}`
    using the file's geometry and properties unchanged — no OL
    flattening, no re-projection.
  - The import flow surfaces per-feature failures and dispatches a
    `map:reload` event after the loop, so the map page can refresh.
  - The module still exports `initImportExport` for `map.js` to wire up.

Tests scope assertions to the `import_file` function body so the OL-
using `export_features` function in the same file is unaffected.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAP_IMPORT_JS = REPO_ROOT / "frontend" / "static" / "js" / "map-import.js"


def _read_map_import() -> str:
    """Return the contents of `map-import.js` as a string."""
    return MAP_IMPORT_JS.read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    """Return the source of the named top-level function, balanced for braces."""
    body = _read_map_import()
    pattern = rf"(?:async\s+)?function\s+{name}\s*\([^)]*\)\s*\{{"
    match = re.search(pattern, body)
    assert match is not None, f"could not locate function {name} in map-import.js"
    start = match.end() - 1  # index of the opening `{`
    depth = 0
    for index in range(start, len(body)):
        char = body[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return body[start + 1 : index]
    raise AssertionError(f"unterminated function {name} in map-import.js")


def _import_function_body() -> str:
    """Return the source of the `import_file` async function, balanced for braces."""
    return _function_body("import_file")


def test_module_exports_init_import_export() -> None:
    """`map-import.js` exports `initImportExport` for the map page to call."""
    body = _read_map_import()
    assert "export" in body
    assert "initImportExport" in body


def test_import_function_does_not_use_openlayers_to_read_the_input_file() -> None:
    """`import_file` does not pass the file through `ol.format.GeoJSON().readFeatures`/`readFeature`.

    Locked in after the bug where `ol.format.GeoJSON().readFeatures(...)`
    flattened each feature's `properties` onto the OL feature, then
    `ol_feature.get("properties")` returned `undefined`, so every
    imported row was saved with empty properties. The fix posts the
    parsed JSON to the API directly. The function may still use
    `ol.format.GeoJSON().readFeature` to convert the *server response*
    into an `ol.Feature` for adding to the map — that path doesn't
    read the file.
    """
    body = _import_function_body()
    # Must not project the input through OL: no layer/source creation,
    # no readFeatures on the file's parsed collection.
    assert "ol.layer" not in body, "import_file still creates OL layers"
    assert "ol.source" not in body, "import_file still creates OL sources"
    assert "readFeatures" not in body, "import_file still calls ol.format.GeoJSON().readFeatures on the input file"
    assert "writeGeometryObject" not in body, "import_file still re-projects geometry through writeGeometryObject"


def test_import_function_posts_each_feature_directly() -> None:
    """The import loop POSTs each feature to the features endpoint with the standard wire body."""
    body = _import_function_body()
    assert "/api/features/" in body or "FEATURES_URL" in body, "import loop should POST to the features endpoint"
    assert "api.post" in body, "import loop should call api.post"
    # The POST body must include type/geometry/properties — the same wire
    # shape the rest of the app uses for create. The implementation may
    # use the object-property shorthand `type: "Feature"` or the
    # quoted-key form `"type": "Feature"`.
    assert ('"type"' in body) or (re.search(r"\btype\s*:\s*[\"']Feature", body) is not None), (
        "POST body must include the GeoJSON 'type' field"
    )
    assert "geometry" in body
    assert "properties" in body


def test_import_function_uses_feature_properties_directly() -> None:
    """The loop must read properties from `feature.properties` — not via `ol_feature.get("properties")`."""
    body = _import_function_body()
    assert "feature.properties" in body, "loop must read `feature.properties` from the parsed file"
    assert 'get("properties")' not in body, (
        'import_file still calls `get("properties")`, which is undefined after OL flattens'
    )


def test_import_function_sends_geometry_as_is() -> None:
    """The loop must read geometry from `feature.geometry` — no `writeGeometryObject` round-trip."""
    body = _import_function_body()
    assert "feature.geometry" in body, "loop must read `feature.geometry` from the parsed file"
    assert "writeGeometryObject" not in body, "import_file still re-projects geometry"


def test_import_function_dispatches_map_reload_after_loop() -> None:
    """After the import loop finishes, the page dispatches `map:reload`."""
    body = _import_function_body()
    assert "map:reload" in body, "import_file must dispatch a map:reload event"


def test_import_function_surfaces_per_feature_failures() -> None:
    """Per-feature POST failures must be logged, not silently swallowed."""
    body = _import_function_body()
    assert "console.error" in body, (
        "import_file must log per-feature failures via console.error so they are not silently dropped"
    )


def test_import_function_does_not_use_confirm_dialog() -> None:
    """The import flow no longer blocks on `window.confirm(...)` — that was tied to the removed preview layer."""
    body = _import_function_body()
    assert "window.confirm" not in body, "import_file still uses window.confirm"


def test_import_function_writes_count_to_status_element() -> None:
    """`import_file` writes the success/failure count to a visible status element.

    Locked in after the bug where all 10 features silently failed with
    400s and the only feedback was a `console.info` line the user
    never saw — making it look like "import doesn't work" when in fact
    the server had rejected the categories.
    """
    body = _read_map_import()
    assert "import-status" in body, "map-import.js must reference `#import-status` to surface results"
    assert "show_import_status" in body, "map-import.js must call a status helper from inside import_file"
    # The status text must include both counts so the user knows whether
    # the import actually succeeded, partially succeeded, or all failed.
    assert "Imported" in body or "imported" in body, "status text must include the imported count"
    assert "failed" in body, "status text must include the failed count"


def test_template_declares_import_status_element() -> None:
    """The map template declares an `#import-status` element next to the import button."""
    template_path = REPO_ROOT / "frontend" / "templates" / "map.html"
    body = template_path.read_text(encoding="utf-8")
    assert 'id="import-status"' in body, "map.html must declare #import-status"
    # Should be hidden by default; the importer reveals it after each run.
    assert "d-none" in body, "import-status must start hidden (Bootstrap d-none class)"


def test_import_function_passes_ol_feature_to_addfeature() -> None:
    """`import_file` must pass an `ol.Feature` instance to `state.source.addFeature`, not a plain object.

    Locked in after the bug where `state.source.addFeature({feature_id, properties, geometry})`
    threw on every successful POST — the surrounding `try`/`catch` swallowed
    it, the `failed` counter incremented, and the user saw
    "Imported 0 of 10; 10 failed" even though every feature had been
    created server-side and showed up in /edit/.
    """
    body = _import_function_body()
    # The addFeature argument must be either an ol.Feature or the result
    # of format.readFeature(...). It must NOT be a plain object literal
    # whose first key is `feature_id`.
    add_match = re.search(r"state\.source\.addFeature\((?P<arg>[^)]*)\)", body, re.DOTALL)
    assert add_match is not None, "state.source.addFeature(...) call not found"
    arg = add_match.group("arg").strip()
    assert not (arg.startswith("{") and "feature_id" in arg), (
        f"addFeature is being called with a plain object literal: {arg!r}. "
        "It must be called with an ol.Feature instance."
    )
    # And the import_file body must construct a Feature (or readFeature) somewhere.
    assert "new ol.Feature" in body or "ol.format.GeoJSON" in body, (
        "import_file must construct an ol.Feature or use ol.format.GeoJSON().readFeature"
    )
