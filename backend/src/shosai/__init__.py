"""Shosai backend: one modular monolith with the api, ws, workers and scheduler roles.

Layers and the direction of dependencies (target architecture §5, import-linter in
pyproject.toml): `entrypoints` → `composition` → `features` → `core`.
"""
