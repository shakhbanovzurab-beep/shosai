# ADR 0044 — A bucket per data home

- **Status:** accepted by the owner on 2026-10-14. Supersedes [ADR 0014](0014-one-object-store-in-russia.md); amends [ADR 0001](0001-local-environment.md), [ADR 0009](0009-test-databases-claimed-by-advisory-lock.md) and [ADR 0015](0015-aiobotocore-instead-of-aioboto3.md).
- **Package:** architecture change; implemented in core storage, settings, composition, the local environment and the test harness; F4 connects the managed buckets; M1 places the draft's objects.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) nfr-4, §4.1, §6, §9 (inv-2, inv-11), §13.1, §18, §21, §22; [ADR 0004](0004-migrated-accounts-start-in-russian-home.md); [ADR 0005](0005-data-without-owner-in-eu-home.md); [ADR 0006](0006-draft-bucket-becomes-russian-home-bucket.md); [DATA_MAPPING.md](../plan/DATA_MAPPING.md) section 6.

## Context

- ADR 0014 put the files of both homes in one bucket in Russia, because object storage was available only there. It named the files of the EU home in Russia an exception to nfr-4 and inv-2, made the one bucket a single point of failure for every file, and described the way back: per-home settings, a copy of the EU home's objects with identical keys, the switch.
- The owner has rented two Timeweb buckets, one per home. For the time of development the EU home's bucket is also in Timeweb `ru-1`; before launch the owner rents an S3 store in the EU and moves the EU home's bucket there.

## Decision

1. **Each data home has its own bucket.** The bytes of an object live only in the bucket of the home that holds its pointer row (inv-11). The platform's own objects (ADR 0005, `platform/`) live in the EU home's bucket, like the platform's rows.
2. **Per-home storage settings:** `HOME_<RU|EU>_S3_ENDPOINT_URL`, `_S3_REGION`, `_S3_BUCKET`, `_S3_ACCESS_KEY_ID`, `_S3_SECRET_ACCESS_KEY` replace `S3_*`. Endpoint and credentials are per home, because the homes may sit at different providers. One client per home and process. The production gate requires `https` for each.
3. **The home is still not part of an object key.** Keys are prefixed by their owner (§8.1); the home of an object is the home of its pointer. An account transfer between homes (§22) copies the account's objects to the target home's bucket with identical keys before it switches the pointers, and deletes the source copies through the deletion registry (§14 rule 7) after.
4. **Slices ask for the home's storage:** `CoreServices.objects[home]` and `CoreServices.uploads[home]`, the home taken from the tenancy scope, as a transaction is. A bucket out of reach stops the file operations of its home only (`storage_unavailable`, 503); readiness reports `storage.ru` and `storage.eu`; storage metrics carry the `home` label.
5. **Interim placement:** until the owner moves it, the EU home's bucket is in Russia (Timeweb `ru-1`). While it is, the files of the EU home remain in Russia, and the legal review item of §22 stays open. Moving it is a change of `HOME_EU_S3_*` plus a copy of the bucket's objects with identical keys; before launch there are no EU users' files to copy.
6. **Local environment and tests:** SeaweedFS serves two buckets, `shosai-ru` and `shosai-eu`, from one store with one key pair (ADR 0001 amended). Tests read `TEST_HOME_<RU|EU>_S3_*` and write only under `tests/slot-<N>/` of each bucket (ADR 0009 amended).
7. **The draft's objects** (ADR 0006) go to the Russian home's bucket, where every migrated account starts (ADR 0004); the platform files of ADR 0005 go to the EU home's bucket.

## Alternatives

- **Keep ADR 0014's one bucket.** Rejected by the owner: the files of EU users belong in the EU home, and one bucket stops every file when it fails.
- **Per-home settings with the EU home pointing at the Russian bucket.** Rejected for the reason ADR 0014 gave: a "same bucket" branch production would use and two-bucket tests would never exercise. Two real buckets keep every path the same from the start.

## Consequences

- nfr-4 regains the files: of the EU home's data, only derived copies remain an exception once its bucket is in the EU; inv-11 reads "bytes live only in the bucket of their pointer's home".
- The single point of failure of ADR 0014 is gone: each bucket is a dependency of its own home.
- An account transfer moves bytes as well as rows; quotas, lifecycle rules and the deletion registry work per bucket.
- Server-side work on files still reads them from the compute plane in the EU: Russian users' files across the border, as before.
- Until the EU bucket moves, nothing changes for residency: the files of the EU home are in Russia (point 5).

## Revisit when

- The EU bucket moves to an EU provider: update `HOME_EU_S3_*`, copy its objects, close the §22 item for files.
- The legal review requires a different placement for a group of users or companies.
