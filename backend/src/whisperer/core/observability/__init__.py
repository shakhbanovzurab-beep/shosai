"""Logs, traces and metrics of a process (target architecture §16).

Telemetry never blocks work: logs and spans leave through bounded queues, and what does
not fit is dropped and counted. No personal data, meeting text or secret reaches a log
line, a span attribute or a metric label (§16.8).
"""
