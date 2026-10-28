# ADR 0075 — Connections on Shosai's own OAuth core, without Nango

- **Status:** points 1–3 decided by the owner on 2026-10-28 (the brief of the `connectors` planning session); **the slice plan approved by the owner on 2026-10-28** ([connectors plan](../plan/slices/connectors.md) §2): CN-D1–CN-D4 and CN-D6–CN-D12 as proposed, CN-D2 with a revisit point, CN-D5 amended by the owner (no money for CASA now), and a step-by-step app-password screen for Yandex Calendar — points 4–9 below.
- **Supersedes:** [ADR 0002](0002-oauth-grants-outside-nango.md) (the split between Nango and own OAuth). **Amends:** [ADR 0038](0038-feature-slices-derived-from-the-product.md) point 5 and SLICE_MAP SM-11 (meeting-result push runs over `connectors`' own core, not Nango); [ADR 0004](0004-migrated-accounts-start-in-russian-home.md) points 1 and the consequence on Nango connections (a connection is a row of its home and moves with the account like any other).
- **Packages:** `connectors` (owner); `tasks` (the Jira grant, TK-D8 unchanged in substance); `chats` (Slack installations, ADR 0062, ADR 0063); `calendar`, `mail`, `knowledge` (their grants and provider reads); `identity` (the deletion registry revokes every grant); M1 (Nango's grants carried without re-consent); F4 (no Nango service, no `/nango/*` edge route).
- **Context documents:** [connectors plan](../plan/slices/connectors.md); [SLICE_MAP](../plan/SLICE_MAP.md) §3, §4.2.13, SM-11, SM-13; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.2, §5, §6, §9 (inv-2), §14 rule 7, §17, §18.2; [DATA_MAPPING](../plan/DATA_MAPPING.md) §5.11, §7.4; [ADR 0011](0011-rate-limits-gcra-in-valkey.md); [ADR 0045](0045-identity-sessions-registration-and-deletion.md) point 7.

## Context

The target architecture placed Nango as the OAuth proxy for Leo's connectors and knowledge sources, one instance per data home with its state in that home's database, beside Shosai's own OAuth flows for calendars, Jira and meeting-result push (ADR 0002). Planning `connectors` showed what that split costs:

- **Two OAuth mechanisms** for one registry: Nango's connect sessions, proxy and webhooks, and Shosai's own flows with state, PKCE and encrypted tokens. Every provider quirk, every revoke path and every health rule is written twice.
- **A stateful service per home** with its own schema, migrations and pinned versions, released with the plane (§17), and a key that cannot be rotated: `NANGO_ENCRYPTION_KEY` encrypts every token in the `nango` schema (DATA_MAPPING §7.4, R6), while Shosai's own secrets rotate through core's Fernet key ring (`core/crypto`).
- **Account transfer** must move a person's Nango connections as a separate step of the saga (ADR 0004), outside the table registry that moves every other row.
- **Deletion** must reach into Nango to revoke grants (§14 rule 7), through Nango's API rather than the slice's own handler.

The owner decided on 2026-10-28 to drop Nango and build every connection on one core of Shosai's own.

## Decision

1. **No Nango.** Every external grant of Shosai — a person's connection in Settings › Connectors, a workspace's installation (Slack for team chats), the Jira grant of `tasks`, calendars, mailboxes, knowledge sources and meeting-result destinations — is made and kept by `connectors`' own OAuth core, which extends the own-flow approach of ADR 0002 to every provider:
   - **sign-in at the provider with PKCE** (S256) wherever the provider supports it; the state is server-side, used once, lives 10 minutes and is bound to the browser that started the flow;
   - **tokens encrypted with core's key ring** (`FERNET_KEY`, `FERNET_KEYS_PREVIOUS`) in the database of the owner's home, like any primary data; never in Valkey, logs, spans, events or task payloads;
   - **refresh** of access tokens, one refresh at a time per connection, with rotating refresh tokens written once and never lost to a race;
   - **revocation** at the provider on disconnect and on account erasure, where the provider offers it; where it does not, Shosai forgets the grant and tells the person where to remove the app;
   - **limits per provider**: the provider's quotas kept by GCRA in Valkey (ADR 0011) and its `Retry-After` honoured by every process at once;
   - **deletion with the account** through the deletion registry (ADR 0045 point 7): the slice's handler revokes and erases every grant of the person;
   - **health of a connection**: a connection that can no longer act — a refused refresh, a revoked app, a missing scope — becomes `needs_reconnect` and emits `connectors.broken`, which the person sees in Settings › Connectors and Leo can bring up once.
2. **Providers as adapters**, added one at a time behind the same core:
   - mail: Gmail, Outlook, Yandex Mail, Mail.ru Mail (Yandex and Mail.ru probably over IMAP);
   - calendars: Google Calendar, Outlook Calendar, Yandex Calendar (probably over CalDAV);
   - files and documents: Google Drive, Dropbox, Yandex Disk, Notion, Confluence;
   - development: GitHub, GitLab;
   - tasks: Jira — designed in `tasks` (TK-D8); `connectors` holds only its grant in the common registry;
   - communication: Slack (Telegram and other messengers belong to `chats`);
   - CRM and meeting-result push (SM-11): HubSpot, Attio, Affinity, Zapier.
3. **Order of the work:** the common core first; then Google (Calendar, Gmail, Drive) and Microsoft (Outlook, Calendar); then Yandex (Mail, Calendar, Disk) and Mail.ru; then Notion, Slack, GitHub; Dropbox, Confluence, GitLab and the CRMs last.

4. **The shape of the registry (CN-D1–CN-D4, plan §3).** Connectors owns every provider's quirks behind typed capability ports (`Mailboxes`, `Calendars`, `FileSources`, `PageSources`, `CodeHosts`, `ChatWorkspaces`, `Destinations`, `Resources`); Jira is the exception — tasks keeps its Jira client over connectors' authorized `ProviderSession`. **A connection is an app; a grant is a provider account's consent shared by that account's apps** (Google revokes a whole Cloud project at once, Microsoft consents per app, Yandex keeps one token per app); the provider's revocation runs when the grant's last app is disconnected; one account per app per person at launch, and **the decision is revisited when people need several connections of one service — a work and a personal account**. A personal connection is the person's and never becomes the workspace's; a workspace installation (Slack for chats) is the workspace's, made and removed by its admins with an audit row. An app is offered only once a consumer uses it.
5. **Google without CASA for now (CN-D5, amended by the owner).** Google Drive uses `drive.file` and Google's Picker: Shosai reads the files the person chooses and the files it creates. Gmail is built on `gmail.modify` in its own Google project, kept in Google's Testing status (at most 100 test users), and **public Gmail stays off behind a flag until CASA has a budget** (connectors plan §5.2: about $1 000–2 000 for the first year at AL1, $540–1 800 a year after, $5 000–8 000 a year at AL2; 2–3 months from the budget to public Gmail). The main Google project (Calendar and Drive) needs only the free brand and sensitive review. Outlook, Yandex Mail and Mail.ru are open to everyone at once.
6. **Providers without an HTTP API (CN-D7).** Yandex Mail and Mail.ru over IMAP and SMTP with XOAUTH2 (Mail.ru by an app password where its OAuth is refused); Yandex Calendar over CalDAV with an app password — its connect screen explains step by step how to make one; a generic CalDAV connection keeps the draft's iCloud, Nextcloud and Fastmail calendars.
7. **GitHub (CN-D6):** a GitHub App with read-only permissions for new connections; the draft's OAuth App only for migrated grants.
8. **Leo (CN-D8):** a `connected` toolset — list, search, read, destinations and the meeting-result push through the Action Gateway; no other external writes in this slice.
9. **Order, migration, health and cuts (CN-D9–CN-D12).** The Jira grant comes right after the core. M1 carries the draft's own grants byte for byte, Nango's grants from its stopped database, and the meeting-push grants except Slack's webhook URLs (SM-11's "reconnect once" revised); production reuses the draft's OAuth applications. Health is learned on use and by keep-alive refreshes, never by scanning providers. SharePoint, OneDrive and self-managed GitLab are not in this slice.

## Alternatives considered

- **Nango per home, as planned.** A second OAuth mechanism beside the own flows that calendars and Jira need anyway, a stateful component per home with an unrotatable key, and a transfer step outside the table registry. Rejected by the owner.
- **A hosted OAuth broker (Nango Cloud or a similar service).** Tokens of Russian users would live outside their home (inv-2), and every provider call would cross a third party. Rejected.
- **Nango for some providers and own flows for others** (ADR 0002 as written). Keeps both costs for the providers each side serves. Rejected.
- **One Google project, Drive by `drive.readonly` and one CASA for Gmail and Drive** (the plan's first proposal for CN-D5). Whole-folder Drive sync and public Gmail at once, for a yearly assessment. Rejected by the owner for now: no budget for CASA.
- **One OAuth client per app, so each app holds its own grant** (the plan's first draft of CN-D2). Google revokes every client of a project at once and Yandex keeps one token per app, so the grants would not be independent. Rejected.

## Consequences

- One OAuth mechanism, one registry, one revoke path and one health rule for every provider; adding a provider is an adapter, not a new mechanism.
- The compute plane loses the Nango component (§4.2), its pinned version (§17) and its row of §18.2; the homes lose the `nango` schema; the edge loses `/nango/*`.
- An account transfer moves a person's connections as rows of the table registry, ciphertexts unchanged, since one key ring serves both homes.
- Shosai now owns every provider's quirks: token lifetimes, rotating refresh tokens, revocation endpoints, quotas, app verification. The OAuth applications, their keys and their reviews are the owner's to register (connectors plan §5).
- M1 carries the draft's Nango grants without re-consent: at cutover, once the draft's Nango is stopped (it refreshes tokens daily and on every read), their tokens are read from its database with its key and written as Shosai's own ciphertexts; they keep working because Shosai refreshes them with the same OAuth applications that issued them (connectors plan §6, CN-D10).
- **Revisit when** a provider's own flow costs more to maintain than a broker would, and a broker exists that keeps tokens in each home.
