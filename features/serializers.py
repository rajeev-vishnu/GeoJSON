"""Feature serializers: GeoJSON wire format with the `_audit` wrapper.

`FeatureSerializer` is the detail serializer. It emits the GeoJSON
envelope (`type: "Feature"`, `id`, `geometry`, `properties`) and
injects an `_audit` block into `properties` containing `created_at`,
`updated_at`, and `created_by` (rendered as the user's email).

`FeatureListItemSerializer` is the list serializer used by the
paginator. It strips the `_audit` block from `properties` for list
responses (per the Feature API spec §2, "No `created_at` /
`updated_at` / `created_by` on the list wire").

Both serializers ignore the incoming `type` field on input (we always
emit `"Feature"` on output) and treat `properties=None` as `{}` on
input (per the spec §6 validation rules).
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers
from rest_framework_gis.serializers import GeometryField

from features.models import Feature


class FeatureSerializer(serializers.ModelSerializer):
    """Detail serializer: GeoJSON envelope + `_audit` inside `properties`."""

    geometry = GeometryField()
    properties = serializers.JSONField()

    class Meta:
        """ModelSerializer metadata for the Feature model."""

        model = Feature
        fields = ("id", "geometry", "properties", "created_at", "updated_at", "created_by")
        read_only_fields = ("id", "created_at", "updated_at", "created_by")

    def to_representation(self, instance: Feature) -> dict[str, Any]:
        """Build `{type, id, geometry, properties}` with `_audit` inside `properties`."""
        body = super().to_representation(instance)
        created_at = body.pop("created_at")
        updated_at = body.pop("updated_at")
        body.pop("created_by")
        created_by_user = instance.created_by
        properties = dict(body.get("properties") or {})
        properties["_audit"] = {
            "created_at": created_at,
            "updated_at": updated_at,
            "created_by": created_by_user.email if created_by_user else None,
        }
        body["properties"] = properties
        body["type"] = "Feature"
        return body

    def validate_properties(self, value: Any) -> dict[str, Any]:
        """Validate `properties`: dict shape, JSON-serializable values, non-empty string keys.

        Per the Feature API spec §6:
        1. Treats `None` as `{}`.
        2. Rejects non-dict values with 400 ("properties must be a JSON object").
        3. Recursively checks all values are JSON-serializable.
        4. Validates keys are non-empty strings.
        5. Strips the `_audit` block injected by `to_representation` so
           a round-trip (serialize → deserialize → save) does not persist
           the metadata into the database.
        """
        if value is None:
            return {}

        if not isinstance(value, dict):
            raise serializers.ValidationError("properties must be a JSON object")
        value = {key: val for key, val in value.items() if key != "_audit"}
        for key in value:
            if not isinstance(key, str) or not key:
                raise serializers.ValidationError("property keys must be non-empty strings")

        if not _is_json_serializable(value):
            raise serializers.ValidationError("property values must be JSON-serializable")
        return value


class FeatureListItemSerializer(FeatureSerializer):
    """List serializer: extends FeatureSerializer and strips `_audit` from `properties`."""

    def to_representation(self, instance: Feature) -> dict[str, Any]:
        """Call super, then pop `_audit` from `properties` before returning."""
        body = super().to_representation(instance)
        properties = body.get("properties") or {}
        properties.pop("_audit", None)
        body["properties"] = properties
        return body


_JSON_PRIMITIVES = (str, int, float, bool, type(None))


def _is_json_serializable(value: Any) -> bool:
    """Recursively check that `value` is JSON-serializable."""
    if isinstance(value, _JSON_PRIMITIVES):
        return True
    if isinstance(value, list):
        return all(_is_json_serializable(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and key and _is_json_serializable(item) for key, item in value.items())
    return False
