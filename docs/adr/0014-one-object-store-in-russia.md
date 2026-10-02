# ADR 0014 — One object store in Russia for both homes

- **Status:** one bucket in Russia accepted by the owner on 2026-10-02; the key layout, configuration and revisit path (items 2–5) proposed with this ADR and open to objection.
- **Package:** architecture change; implemented by F1 step 5 (storage client and settings), F3 (local bucket), S08 (storage), M1 (migration) and every slice that keeps objects.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) nfr-4, §4.1, §6, §8.1, §9 (inv-2, inv-11), §13.1, §20, §22; [ADR 0005](0005-data-without-owner-in-eu-home.md); [ADR 0006](0006-draft-bucket-becomes-russian-home-bucket.md); [DATA_MAPPING.md](../plan/DATA_MAPPING.md) section 6.

## Context

- The architecture gave each data home its own S3 bucket (§4.1 rule 2): bytes live only in the owner's home (inv-11).
- The owner is adding a PostgreSQL cluster in Russia and one in the EU, and managed Redis in the EU. Object storage will exist **only in Russia**; there will be no bucket in the EU.
- The draft already keeps every object of every user in one Timeweb bucket in `ru-1`, and ADR 0006 keeps that bucket for v2.
- The EU home holds platform data (ADR 0005), including desktop builds, which are files.

## Decision

1. **One bucket in Russia** — the draft's Timeweb bucket of ADR 0006 — holds the objects of both homes and of the platform. Databases stay per home; only the bytes are shared.
2. **The home is not part of an object key.** Keys are prefixed by their owner (§8.1, decided in detail by S08); platform objects live under `platform/`. The pointer row in the owner's home database holds the full key and is the only way to an object (DATA_MAPPING 6.2). An account transfer between homes moves pointer rows and no bytes.
3. **One storage configuration:** `S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` replace the per-home `HOME_<H>_S3_*` variables; one client per process. The production gate requires `https` for it.
4. **Files of people and companies of the EU home are stored in Russia.** This is an exception to nfr-4 and inv-2, added to the legal review of §22: a transfer of personal data from the EU to Russia needs a legal basis, since there is no adequacy decision.
5. **The way back** to a bucket per home: per-home storage settings, then a copy of the objects referenced by the EU home's pointer rows to the EU bucket with identical keys, then the switch. Keys need no rewrite, because they do not name a bucket.

## Alternatives

- **Keep per-home storage settings with both homes pointing at the same bucket.** The code would stay ready for a second bucket, but every transfer, copy and deletion path would need a "same bucket" branch that production uses and local tests with two buckets never exercise. Rejected: the way back above costs one configuration change and one copy.
- **A bucket in the EU at another provider.** Not available; the provider is the owner's choice.

## Consequences

- inv-11 becomes "bytes live in the one bucket in Russia; the storage quota is not exceeded"; nfr-4, §4.1, §4.2, §6, §8.1, §18.2, §19, §20 and §22 are updated.
- The bucket is a single point of failure for the files of both homes (§13.1); its outage stops uploads and downloads for everyone, while the rest of the EU home keeps working.
- Server-side work on EU users' files (recordings, documents, OCR) reads them across the border from the compute plane, like Russian users' files.
- Lifecycle rules, quotas and the deletion registry (§14 rule 7) work over one bucket; deletion still goes through pointers.
- F1 step 5 replaces the `HOME_<H>_S3_*` settings and the per-home storage client; the local environment keeps one bucket. ADR 0005 and ADR 0006 point here.

## Revisit when

- The legal review rules EU users' files in Russia inadmissible, or a company contract requires EU storage.
- A bucket in the EU becomes available and the owner wants per-home storage back.
