# ADR 0015 — The S3 client is aiobotocore, not aioboto3

- **Status:** accepted by the owner on 2026-10-02 (F1 step 5, decision F1-D10).
- **Package:** F1, backend foundation (`core/storage`); used by S08 and every slice that keeps objects.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §14 rule 8, §18.2; [ADR 0014](0014-one-object-store-in-russia.md); [CLAUDE.md](../../.claude/CLAUDE.md) "Dependencies"; [F1 plan](../plan/packages/F1-backend-foundation.md).

## Context

- §18.2 named aioboto3 15.5.0 as the S3 client. On 2026-10-02 that is still its latest release, published 2025-10-30. It pins `aiobotocore==2.25.1`, which pins `botocore<1.40.62` (October 2025).
- aiobotocore itself is maintained: 3.9.2 was released on 2026-10-01 against botocore 1.43.
- aioboto3 adds three things on top of aiobotocore: the resource API, managed file transfers (`upload_fileobj`, `download_fileobj`) and client-side encryption. The storage ports of F1 use none of them. Their operations are plain client calls: put, get, head, delete, delete many, list, presigned get and put, and multipart create, presign part, list parts, complete and abort.

## Decision

1. The backend uses **aiobotocore 3.9.2** directly, one client per process for the one bucket (ADR 0014). Its types come from `types-aiobotocore[s3]` 3.9.2, a dev dependency.
2. §18.2 names aiobotocore instead of aioboto3.

## Consequences

- botocore and aiobotocore fixes, security fixes included, arrive when aiobotocore releases them, not only after a new aioboto3 release.
- There is no `upload_fileobj`. Clients upload with presigned requests, the server stores bytes it holds in memory, and large objects go through the multipart operations of the port. A slice that needs a server-side streamed upload of a large file builds it on those operations.
- The client is configured explicitly: connect 2 s, read 20 s, standard retries with at most 3 attempts, path addressing, and checksums only where the S3 API requires them. A test counts the attempts against a failing endpoint.

## Revisit when

- aioboto3 catches up with current aiobotocore and a slice needs its resource API or managed transfers.
- aiobotocore stops being maintained.
