# ADR 0016 — The task broker is our own, on TaskIQ's broker interface, not taskiq-redis

- **Status:** accepted by the owner on 2026-10-02 (F1 step 6, decision F1-D13).
- **Package:** F1, backend foundation (`core/tasks`); used by every slice that queues work, by the outbox relay (F1 step 7) and by the scheduler (F1 step 8, F6).
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.3, §12, §14 rules 9 and 13, §16.4, §18.2; [F1 plan](../plan/packages/F1-backend-foundation.md) §3.8, §3.9; [CLAUDE.md](../../.claude/CLAUDE.md) "Dependencies".

## Context

§12 fixes TaskIQ on Redis Streams, and §18.2 named taskiq-redis 1.2.4 as the broker. Read against §4.3 and the lessons of the draft (which overrode most of the same class in its own `core/tasks/broker.py`), its `RedisStreamBroker` gives almost nothing the plan needs:

1. **Its own pool per broker.** Each broker builds a connection pool from a URL: four queues mean four pools to Valkey besides the process's one client (F1 plan §3.8), and the broker's commands are not traced, because tracing is set up per client.
2. **No enqueue deadline and silent loss when full.** `kick` waits as long as the socket allows, not the 50 ms of §4.3, and `MAXLEN ~` trimming drops the oldest *unfinished* tasks when the stream reaches its bound.
3. **Reads that do not survive the managed Valkey.** Nothing handles a connection error, the `TimeoutError` the managed service raises on a blocking read at 5 s, or `NOGROUP` after a reset or failover.
4. **No delivery limit.** Abandoned messages are claimed with `XAUTOCLAIM` whatever their delivery count, so a message no worker can finish returns forever.
5. **`XACK` without `XDEL`.** Finished tasks stay in the stream with their payloads until the bound trims them.

Using it would mean overriding `kick`, `listen`, acknowledgement, start-up and the pool — everything except the storage of its attributes — and following its internals across upgrades. TaskIQ itself has more gaps the broker must close: its receiver logs an unparseable message with its body, acknowledges a message of an unknown task with a warning (a silent drop, against §14 rule 9), and logs rejected parameters with their input; its decorator renames the task function and sets it as an attribute of its module.

## Decision

1. `core/tasks` has its own broker, `ValkeyStreamBroker`, a subclass of TaskIQ's `AsyncBroker`. TaskIQ 0.13.0 stays for the broker interface, the receiver (concurrency, acknowledgement after the run, graceful drain) and the middleware chain. taskiq-redis is not added.
2. Every broker works over the process's one Valkey client. One stream per queue holds only unfinished tasks: a finished task is acknowledged and deleted in one Lua script, so the stream's length is the queue's depth. Every step that must be atomic is one script, and a worker changes a message only while it still holds it; a successful run settles its message even after another worker took it.
3. Enqueue waits at most 50 ms; a full stream (500 000) or a silent Valkey refuses the task with 503 `queue_unavailable` instead of trimming.
4. A worker reads one message at a time, so a second worker of the queue is never starved. It admits only what it can run: a message that is not a task, or whose task is unknown, goes to the dead letter and is counted. Its receiver's own parameter parsing is off; the task function validates the payload and reports fields and kinds, never values.
5. A worker renews the lease of every message it holds every 15 s; a message idle longer than the lease (120 s) belongs to a dead worker and is claimed again, which counts one more delivery. A retry is a redelivery: a failed message is sent back with an idle time that makes it claimable after a pause of 5 s doubling up to 120 s, jittered to 50–100%, and no worker slot waits during the pause. At most five deliveries (§4.3); the last failure, or one the task's policy does not retry, moves the message and a redacted entry to the queue's dead letter in one script.
6. Connection errors, timeouts and `NOGROUP` are counted, logged at most once per 10 s and waited out; the group is recreated. A worker never stops on a Valkey outage.

## Consequences

- About 2 200 lines of our own code under `core/tasks`, covered by tests against Valkey 9.1.2 (stream operations, leases, retries, dead letter, outages, the group's loss). A TaskIQ upgrade reruns them.
- The broker depends on TaskIQ's public interface (`AsyncBroker`, `Receiver`, `TaskiqMiddleware`, `AsyncKicker`) and on one attribute of the decorated task class it fills itself. The stream commands it uses (`XPENDING … IDLE`, `XCLAIM … IDLE JUSTID`, `XTRIM MINID`) need a Redis 6.2 level server; Valkey 9.1 has them.
- §18.2 names the own broker instead of taskiq-redis.
- `XACKDEL`, which would replace the acknowledgement script, exists in Redis 8.2 but not in Valkey 9.1.

## Revisit when

- taskiq-redis gains a bounded enqueue with a deadline, a delivery limit, lease renewal and deletion on acknowledgement over an injected client.
- A consumer outside the application process needs the queues (§12 revisit triggers).
