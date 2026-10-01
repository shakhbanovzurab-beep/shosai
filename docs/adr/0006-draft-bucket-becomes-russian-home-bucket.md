# ADR 0006 — The draft's bucket becomes the Russian home bucket; object keys are kept

- **Status:** accepted by the owner on 2026-10-01 (D3, decision U-3 in [DATA_MAPPING.md](../plan/DATA_MAPPING.md#10-decisions-for-the-user)).
- **Package:** D3; applied by M1, S08 and every slice with object pointers.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.1, §8.1 (File), §14 rule 7; [DATA_MAPPING.md](../plan/DATA_MAPPING.md) section 6.

## Context

The draft keeps all objects in one Timeweb bucket in `ru-1`, the same provider and region the architecture names for the Russian home. Its keys follow nine layouts, listed in DATA_MAPPING section 6:

- some start with an owner prefix of 8 hex characters, `u-{id[:8]}`;
- some carry the full owner id;
- ticket attachments carry no owner at all.

§8.1 asks for keys prefixed by their owner. Re-keying would mean copying every object and rewriting every pointer during or before the cutover. It would also risk losing objects, and it gives users nothing.

## Decision

1. **The draft's bucket serves as the Russian home bucket** in v2. The Russian home moves no objects at cutover.
2. **Migrated objects keep their draft keys.** Pointer columns store the full key, and v2 code never derives an owner from a key.
3. **New objects follow the v2 layout**, owner-prefixed with the full owner id, as S08 decides.
4. **Objects without a migrated pointer are not carried.** They are deleted after M1's report (U-4).
5. **Fallback:** if the draft's bucket cannot be used (provider, credentials or separation reasons), objects are copied with identical keys and metadata. The copy runs before the window and catches up by `LastModified` inside it.

## Consequences

- The cutover window spends no time on objects.
- Two key layouts coexist. Deletion goes through pointers, as the deletion registry does anyway (§14 rule 7), and never by prefix for legacy keys: an 8-character owner prefix can match several users.
- "Key prefixed by owner" (§8.1) holds for objects v2 writes; legacy keys are an accepted exception, noted in §8.1.
- Lifecycle rules that v2 adds to the bucket target v2 prefixes only. Legacy transient objects (meeting audio, raw recognition output) are deleted by v2 through their pointers.
- Production credentials for the bucket move from the draft to v2 at cutover. The draft keeps no write access after the freeze.

## Revisit when

- The Russian storage provider changes.
- Legacy keys block a capability, for example a lifecycle or replication rule that must select objects by owner prefix.
