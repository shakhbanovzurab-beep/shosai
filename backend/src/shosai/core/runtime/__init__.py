"""How a process runs: its HTTP servers, its scheduled loops and its stop on a signal (§5).

Composition decides what a role runs; this package runs it on one event loop and stops it
in order, so in-flight work finishes before clients and pools close.
"""
