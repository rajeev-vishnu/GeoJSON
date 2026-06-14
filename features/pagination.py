"""Custom pagination for the features list endpoint.

`BboxPageNumberPagination` extends DRF's `PageNumberPagination` to
match the assignment's wire format:

- Hardcoded `page_size = 100` (not configurable via query string).
- The list response is exactly `{next, prev, results}` — no `count`.
- `next` and `prev` are built by `request.build_absolute_uri()` so
  they preserve the caller's query string params (bbox, ordering, search).
- `page` past the end returns 404 (DRF default).
- `page=0` returns 400 (DRF default for invalid page params).
"""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class BboxPageNumberPagination(PageNumberPagination):
    """Page-number pagination for the features list, hardcoded at 100 per page."""

    page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        """Return exactly `{next, prev, results}` — no `count` field."""
        return Response(
            {
                "next": self.get_next_link(),
                "prev": self.get_previous_link(),
                "results": data,
            }
        )
