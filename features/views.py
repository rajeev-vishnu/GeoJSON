"""Feature API views: FeatureViewSet and the categories endpoint.

`FeatureViewSet` is a `ModelViewSet` with all six CRUD actions. The
list response uses `FeatureListItemSerializer` (strips `_audit`); the
detail and write responses use `FeatureSerializer` (includes `_audit`).
The `get_queryset()` method chains three optional filters: bbox
(via `apply_bbox`), search (case-insensitive substring on
`properties->>'name'`), and ordering (whitelist of 4 values; default
`-updated_at, id`).

`categories_view` is a small function-based view that returns the
`Feature.Category` enum values as a flat JSON array of strings, in
declaration order.
"""

from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from features.filters import apply_bbox
from features.models import Feature
from features.pagination import BboxPageNumberPagination
from features.serializers import FeatureListItemSerializer, FeatureSerializer

ALLOWED_ORDERING = ("created_at", "-created_at", "updated_at", "-updated_at")
DEFAULT_ORDERING = ("-updated_at", "id")


class FeatureViewSet(viewsets.ModelViewSet):
    """CRUD over the Feature model with bbox / search / ordering filters."""

    pagination_class = BboxPageNumberPagination

    def get_serializer_class(self):
        """Return the list-item serializer for `list`, the detail serializer otherwise."""
        if self.action == "list":
            return FeatureListItemSerializer
        return FeatureSerializer

    def get_queryset(self):
        """Apply the bbox, search, and ordering filters in order.

        Bbox: chained via `apply_bbox()` which returns the queryset
        unchanged when `?bbox=` is absent.
        Search: case-insensitive substring on `properties->>'name'`,
        chained as `properties__name__icontains`.
        Ordering: whitelist of 4 values; default `-updated_at, id`
        (the trailing `id` makes the sort an index-only scan thanks to
        the BTree index on `(updated_at, id)`).

        Invalid `ordering` values raise `ValidationError`, which DRF
        renders as a 400 with `{"detail": "..."}`.
        """
        queryset = Feature.objects.all()
        queryset = apply_bbox(queryset, raw_bbox=self.request.query_params.get("bbox"))

        search_term = self.request.query_params.get("search")
        if search_term:
            queryset = queryset.filter(properties__name__icontains=search_term)

        ordering_param = self.request.query_params.get("ordering", "")
        if ordering_param:
            if ordering_param not in ALLOWED_ORDERING:
                raise ValidationError(
                    f"Invalid ordering value: {ordering_param}. Allowed: {', '.join(ALLOWED_ORDERING)}"
                )
            return queryset.order_by(ordering_param, "id")

        return queryset.order_by(*DEFAULT_ORDERING)

    def perform_create(self, serializer):
        """Set `created_by` to the request user before saving."""
        serializer.save(created_by=self.request.user)

    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Apply a JSON merge patch to `properties`: missing keys are preserved, `null` deletes.

        Per the Frontend spec §5.2.1, PATCH is additive — keys not in the
        body are preserved, and `null` deletes a key. This matches RFC 7396
        (JSON merge patch) and lets the edit page update one property at
        a time without losing the rest. The system-managed `name` key is
        therefore never disturbed by an `+ add new` PATCH that doesn't
        include `name` in its body.
        """
        instance = self.get_object()
        existing_properties = dict(instance.properties or {})
        incoming_properties = request.data.get("properties") or {}
        merged_properties = _merge_properties(
            existing=existing_properties,
            incoming=incoming_properties,
        )
        request_data = dict(request.data)
        request_data["properties"] = merged_properties
        serializer = self.get_serializer(
            instance=instance,
            data=request_data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def categories_view(request):
    """Return the `Feature.Category` enum values as a flat JSON array of strings."""
    return Response(Feature.Category.values, status=status.HTTP_200_OK)


def _merge_properties(
    existing: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    """Apply an RFC 7396-style JSON merge patch to `properties`.

    - Keys present in `incoming` overwrite or are added to `existing`.
    - Keys whose incoming value is `None` are removed from the result.
    - Keys absent from `incoming` are preserved unchanged.
    """
    merged: dict[str, object] = dict(existing)
    for key, value in incoming.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value

    return merged
