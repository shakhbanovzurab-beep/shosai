import type { KanbanDemo } from "../store/types";

/*
 * Время задач доски «Work» (ADR 0061): секундомер, пробывший день в «Planned» и идущий в «Building», таймер в ходе
 * и таймер, время которого вышло; план и факт — в пределах и сверх плана.
 */

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;

export function seedWorkClocks(demo: KanbanDemo) {
  const now = Date.now();
  demo.clocks.set("w-schema", [
    { column_id: "planned", started_at: now - 30 * HOUR, stopped_at: now - 6 * HOUR },
    { column_id: "building", started_at: now - 6 * HOUR, stopped_at: null },
  ]);
  demo.clocks.set("w-salary-import", [
    { column_id: "planned", started_at: now - 50 * HOUR, stopped_at: now - 26 * HOUR },
    { column_id: "building", started_at: now - 26 * HOUR, stopped_at: now - 2 * HOUR },
  ]);
  demo.timers.set("w-sso-crash", {
    length_ms: 4 * HOUR,
    ends_at: new Date(now + 80 * MINUTE).toISOString(),
    paused_left_ms: null,
  });
  demo.timers.set("w-pricing-deck", {
    length_ms: HOUR,
    ends_at: new Date(now - 20 * MINUTE).toISOString(),
    paused_left_ms: null,
  });
  const schema = demo.tasks.get("w-schema");
  if (schema) Object.assign(schema, { plan_minutes: 16 * 60, fact_minutes: 9 * 60 + 30 });
  const salary = demo.tasks.get("w-salary-import");
  if (salary) Object.assign(salary, { plan_minutes: 8 * 60, fact_minutes: 10 * 60 });
}
