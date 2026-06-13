"""Account-specific pytest fixtures and test helpers.

The `user` and `other_user` fixtures are defined in the root
`conftest.py` so they are auto-discovered by every test module in
the repo (accounts, features, config, frontend). This file exists
to host fixtures that are specific to the accounts app.
"""

from __future__ import annotations
