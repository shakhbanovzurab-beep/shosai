"""Process settings: read once from environment variables, checked, then passed in.

Settings never come from a dotenv file and are never held in a cached global: the entry
point builds them with `load_settings(os.environ)` and hands them to whoever needs them.
A production process refuses to start on an unsafe configuration (`gate`).
"""
