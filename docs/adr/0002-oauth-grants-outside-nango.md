# ADR 0002 — OAuth grants outside Nango

- **Status:** accepted by the owner on 2026-10-01 (D4, decision FM-3 in [FEATURE_MAP.md](../plan/FEATURE_MAP.md#7-decisions-keep-merge-drop)).
- **Scope:** S12 Connectors and calendar, S01 (deletion registry), M1.

## Context

The target architecture places Nango as the OAuth proxy for connectors, one instance per data home (§4.2), and requires account deletion to revoke every external grant (§14.7). It does not say whether every OAuth grant of the product goes through Nango.

The draft has two kinds of grants:

- through Nango: Leo's connectors (mail, files, notes, trackers, CRM) and knowledge-base sources;
- its own OAuth, tokens encrypted in the database: calendars (Google, Microsoft; CalDAV with credentials), Jira Cloud for the tracker, and the push of meeting results to Notion, Slack, HubSpot and Attio.

Users of the draft hold live grants of the second kind. Moving them into Nango means either importing every token during data migration (M1) or asking users to reconnect.

## Decision

v2 keeps the split.

- Nango serves Leo's connectors and knowledge sources.
- Calendars, Jira and meeting-result push keep their own OAuth. Tokens stay encrypted in the user's home database, like any other primary data.
- The deletion and export registry (§14.7) lists every grant of both kinds and revokes it on account deletion.

## Consequences

- No user reconnects anything after the switch to v2; M1 moves these tokens like other rows.
- S12 maintains two OAuth mechanisms: Nango, and its own flows with state and PKCE storage.
- Revisit when a new provider needs both a Nango connector and one of the own flows for the same account, or when Nango supports a provider whose own flow costs more to maintain than a migration.
