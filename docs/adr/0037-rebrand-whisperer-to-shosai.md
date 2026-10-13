# ADR 0037 — The product is renamed from Whisperer to Shosai

- **Status:** accepted by the owner on 2026-10-09.
- **Packages:** every package; F4 and M2 for the domain.
- **Context documents:** [CLAUDE.md](../../.claude/CLAUDE.md) "Rewrite from the draft"; [ADR 0022](0022-new-web-design-replaces-draft-parity.md); [contracts/README.md](../../contracts/README.md); [SEO strategy](../seo/STRATEGY.md) 5.

## Context

- ADR 0022 recorded a rebrand with a tentative name. The owner made it official: the product is **Shosai** (書斎, Japanese for a study or a home library — a room for reading, writing and quiet work).
- v2 is not deployed anywhere yet (F4 is open), so its internal names (packages, databases, keys, metrics) can change now at no migration cost. After the first deployment the same change would need a data migration.
- Shipped native clients keep working without an update (nfr-12). They depend on the domain, the WebSocket subprotocol names and their own identifiers, all of which carry the old name.
- The repository moved from `whisperer-v2` to `shosai` on GitHub and on disk (`/root/shosai`).

## Decision

1. **Brand.** Every name a person reads is Shosai: UI text in all 16 locales, documentation, the license, OpenAPI metadata, model-facing text. The name is written in Latin script in every language (i18n glossary).
2. **Internal identifiers are renamed** in the same change:

   | Was | Now |
   |---|---|
   | Python package `whisperer`, console command `whisperer` | `shosai`, `shosai` |
   | `whisperer-contracts`, `whisperer_contracts` | `shosai-contracts`, `shosai_contracts` |
   | PostgreSQL database `whisperer`, roles `whisperer_app`, `whisperer_migrator`, test databases `whisperer_test_<N>` | `shosai`, `shosai_app`, `shosai_migrator`, `shosai_test_<N>` |
   | Valkey keys `whisperer:<purpose>:…` | `shosai:<purpose>:…` |
   | Metrics `whisperer_*` | `shosai_*` |
   | Bucket `whisperer`, OTel `service.name` `whisperer` | `shosai`, `shosai` |
   | Compose projects `whisperer-v2-local`, `whisperer-parity` | `shosai-local`, `shosai-parity` |
   | Variables `WHISPERER_*` of the local init script | `SHOSAI_*` |

3. **Names that stay `whisperer`**, because changing them breaks something outside this repository or rewrites a record:
   - the domain `whisperer.one` and its subdomains (the test domain moved to `shosai.tech`, [ADR 0040](0040-shosai-tech-is-the-domain.md)): shipped clients call it and pin its certificate chain;
   - the WebSocket subprotocols `whisperer-bearer` and `whisperer-room-pass`, the `whisperer://` scheme, `WhispererKit`, installer and client file names: the contract of shipped clients;
   - the draft: its path `/root/whisperer`, its repository, and everything captured from it — `contracts/draft/*.json`, `parity/` fixtures, inventory and seeds, and draft facts quoted in the plan (NATS streams `WHISPERER_EVENTS`, `WHISPERER_DLQ`, keys `whisperer:taskiq:…`, `whisperer:dlq:…`, `whisperer:billing:…`);
   - the file-format identifiers `whisperer-draft-consumers/1`, `whisperer-websocket-catalogue/1` and `whisperer-contract-acceptances/1`, which the captured baseline carries.
4. **Accepted ADRs are updated in place** for names and code paths, so their references resolve; their decisions are unchanged.

## Consequences

- Local environments are recreated: the Compose project `shosai-local` has its own volumes, and the init script creates the new databases and roles. The volumes of `whisperer-v2-local` are left untouched and can be removed once nothing needs them (`docker volume ls --filter label=com.docker.compose.project=whisperer-v2-local`).
- A local `.env` copied from the old `.env.example` must be updated to the new database, role and bucket names.
- The brand and the canonical domain differ until a Shosai domain exists. SEO entity work (fact registry, `sameAs`, structured data) states the brand as Shosai and the official URL as `whisperer.one`.
- Native clients are unaffected.

## Revisited

- 2026-10-13: the owner acquired `shosai.tech` — [ADR 0040](0040-shosai-tech-is-the-domain.md). Point 3's domain item now reads: `whisperer.one` stays the draft's production server and, after cutover, the address of the shipped native clients; `one.whisperer.one` is no longer the test domain.

## Revisit when

- The owner acquires a Shosai domain: moving the canonical domain needs a release of every native client with the new host and pins first, then redirects, then the SEO migration.
- A native client release can drop the old subprotocol names: then v2 accepts both names first, and the old ones are removed after the old clients are gone.
