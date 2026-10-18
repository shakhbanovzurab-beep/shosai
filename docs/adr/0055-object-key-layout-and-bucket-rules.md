# ADR 0055 — Object key layout and bucket rules

- **Status:** accepted by the owner on 2026-10-18 (files slice plan, decision FL-D7, with FL-D1, FL-D4 and FL-D5).
- **Packages:** `files` (owner of the layout); every slice that stores bytes (meetings, capture, agent, support, workspaces, releases, billing's invoice PDFs); M1 (draft keys), the account data registry and workspaces' data registry.
- **Context documents:** [files plan](../plan/slices/files.md); [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.1, §4.3, §6, §8.1, inv-11, §10 Upload, §14 rules 1, 7, 8, §19; [ADR 0044](0044-a-bucket-per-data-home.md); [ADR 0006](0006-draft-bucket-becomes-russian-home-bucket.md); [DATA_MAPPING](../plan/DATA_MAPPING.md) §6.

## Context

Each home has its own bucket (ADR 0044), and a key does not name the home, so an account transfer copies objects with identical keys. The draft's keys (`u-{owner_id[:8]}/{file_id}/{name}`) carry the file's name and only eight characters of the owner's id, which collide between users (ADR 0006). DATA_MAPPING §6.2 proposed a v2 layout for `files` to confirm. No bucket has a lifecycle rule today, so an abandoned multipart upload keeps its parts for ever.

## Decision

1. **Keys of v2 objects.**
   - A person's file: `u/{user_id}/f/{file_id}`; a workspace's file: `o/{org_id}/f/{file_id}`; ids are full UUIDs.
   - A slice's other objects of an owner take the same prefix with their own segment: `u/{user_id}/<segment>/…` or `o/{org_id}/<segment>/…`. Identity's avatars keep their `avatars/{user_id}/…` keys (ADR 0045) until identity moves them.
   - An upload another slice claims (recording, Leo attachment, ticket attachment, workspace upload, app build): `transient/{purpose}/{upload_id}`; the claimer moves or copies it to its own key.
   - The platform's objects: `platform/…` in the EU home's bucket (ADR 0005, 0044).
2. **No name and no home in a key.** The file's name travels in the presigned link's `Content-Disposition`; the home is the bucket.
3. **The pointer is the truth.** Each object has a row that stores its full key; a key is never parsed for an owner. Draft keys stay verbatim in their pointers and are copied, erased and checked only through those pointers, never by prefix (ADR 0006).
4. **Several rows may point at one object.** Objects are immutable, so a File Manager copy is a new row with the same key (FL-D4); the object is deleted after the commit that removes its last row.
5. **Uploads write to the final key.** A File Manager upload is created on the file's key; the multipart upload completes, its size is checked by `HEAD`, and only then is the pointer committed (§8.1).
6. **Bucket rules on both homes:** abort incomplete multipart uploads after 24 hours; expire objects under `transient/` after 3 days; a CORS rule lets the cabinet's origin `PUT` presigned parts and read their `ETag`. The `shosai files bucket-rules` command applies them to each home's bucket; the owner runs it on the managed buckets with keys that may configure them.
7. **Deletion.** A row goes first (a file is hidden for 7 days, then its row is purged, FL-D5); the object is deleted after that commit, from a pending-deletion record retried until done.
8. **Downloads go through the edge** (owner's decision, 2026-10-18). A presigned link cannot add response headers beyond the type, disposition, cache, language, encoding and expiry, so the API answers a link on Shosai's own address; the edge streams the presigned object from the home's bucket and adds `X-Content-Type-Options: nosniff` and `Content-Security-Policy: sandbox` to every file's bytes. The API process holds no download; uploads still go straight to the bucket (point 5).

## Consequences

- A person's v2 objects share `u/{user_id}/`, so the account data registry copies and erases them by prefix; workspace objects share `o/{org_id}/` for workspaces' data registry.
- Listing a bucket reveals no names and no home.
- Draft objects keep their old keys for as long as they exist; v2 objects never use the `u-` form.
- Download traffic crosses the compute plane; a Russian person's file travels from the Russian bucket through the EU edge and back.
- A copy costs no bytes and no time; deletion checks for other rows of the key in the same transaction.

## Revisit when

- Identity's avatars or another slice's objects need to move under the owner prefix for one-prefix erasure.
- A provider offers server-side copy that makes per-row objects cheap enough to drop shared keys.
