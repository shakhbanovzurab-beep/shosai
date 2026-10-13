# ADR 0042 — Valkey without TLS, only inside the private network

- **Status:** accepted by the owner on 2026-10-13. Amends the F1 audit's decisions OD-6 ("TLS stays required on these links") and OD-7 for the Valkey link only, and F1-D12 of the [F1 plan](../plan/packages/F1-backend-foundation.md).
- **Packages:** F1 (production gate), F4 (staging and production), F5 (alerting).
- **Context documents:** [F1 audit](../plan/audits/F1-audit.md) OD-6, OD-7; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.2, §13.2, §15; [ADR 0041](0041-platform-services-replanned-from-the-product.md).

## Context

- The managed Valkey of the EU home runs at Timeweb Cloud, on its own machine, reached from the production server over a private network (OD-6).
- Timeweb's managed Valkey offers no TLS: its documentation lists connection by public or private IP only, and none of its twelve configurable parameters concerns TLS. A probe of the instance on 2026-10-13 confirmed it: no TLS handshake on port 6379; a new connection with AUTH and PING took 3.3 ms (median, p95 4.6 ms) from this network.
- The production gate allowed only `rediss://`, so staging and production could not start against it.
- The link carries task payloads (ids), transcript lines (personal data) and meeting state.

## Decision

1. **Valkey is reached over TLS, or in plain text only at a private-network address.** The gate accepts `rediss://` to any host, and `redis://` only when the host is an IP literal in 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 or fc00::/7. A host name, a public address or loopback with `redis://` refuses the start and names `VALKEY_URL`; a name is refused because where it resolves cannot be checked at start.
2. **Compensating controls, set up by F4:** public access to the Valkey instance is off in Timeweb's panel; the backend connects as its own ACL user with a long password and only the commands it uses, not as `default`; the private network holds only the plane's machines.
3. Every other link leaving the plane keeps TLS: each home's database with `sslmode=verify-full`, the bucket over HTTPS.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Wait for TLS from Timeweb | Staging cannot start until then; TLS is not offered |
| A self-hosted Valkey with TLS | Loses the managed replica and failover OD-6 and §4.2 rely on |
| A TLS tunnel (stunnel) | TLS must end on the server side, which the managed service does not let us run |
| Accept any `redis://` | A wrong address would send transcript lines over the internet in plain text |

## Consequences

- Inside the private network the link is plain text; its protection is the network's isolation, the ACL user and the closed public access. Interception needs access to the provider's network, from which TLS would protect only partly, since the provider runs the server.
- The legal review of §22 includes this link: transcript lines are personal data in transit inside one data centre.

## Revisit when

- Timeweb offers TLS for managed Valkey: return to `rediss://` and remove the exception.
- Valkey or the application moves out of this private network or data centre.
- The legal review requires encryption in transit inside the data centre.
