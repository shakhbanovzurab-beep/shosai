"""The HTTP shell every public app shares: middlewares, the error envelope, the health route.

An app is built by a factory per role (`app.build_http_app`); nothing creates an app at
import time.
"""
