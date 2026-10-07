import type { Breadcrumb } from "../domain/contract";
import type { ErrorSource, PlatformComponent } from "../domain/dimensions";
import { culpritOf, hash, mulberry32, toFrames } from "./frames";
import { ENVIRONMENTS, SERVER_ENVIRONMENT, USER_IDS, VERSIONS } from "./reference";
import { MACOS_TEMPLATES } from "./templates-macos";
import { PLATFORM_TEMPLATES } from "./templates-platform";
import { WINDOWS_TEMPLATES } from "./templates-windows";
import { DAY, HOUR, type Store, type StoredEvent, type StoredIssue } from "./types";

const RESEED_AFTER = 12 * HOUR;
const TEMPLATES = [...PLATFORM_TEMPLATES, ...MACOS_TEMPLATES, ...WINDOWS_TEMPLATES];

type Step = [category: Breadcrumb["category"], message: string];

const WEB_STEPS: Step[] = [
  ["navigation", "/chat → /chat/c_8f21"],
  ["http", "GET /api/leo/conversations/c_8f21 → 200 (182 мс)"],
  ["ui", "Клик: кнопка «Отправить»"],
  ["http", "POST /api/leo/conversations/c_8f21/messages → 200 (stream)"],
  ["console", 'Warning: Each child in a list should have a unique "key" prop'],
];
const SERVER_STEPS: Step[] = [
  ["http", "POST /v1/leo/conversations/c_8f21/messages"],
  ["system", "Задача поставлена в очередь worker-3"],
  ["http", "→ provider POST /v1/messages (stream)"],
  ["system", "Повторная попытка 1 из 2"],
];
const desktopSteps = (source: ErrorSource): Step[] => [
  ["system", "Приложение активировано"],
  ["navigation", "Открыт чат «Отчёт за квартал»"],
  ["http", "GET https://api.leo.app/v1/leo/conversations → 200"],
  ["ui", "Нажата кнопка микрофона"],
  ["system", source === "macos" ? "AVAudioSession: смена маршрута звука" : "WASAPI: устройство по умолчанию изменено"],
];

function stepsFor(source: ErrorSource, component: PlatformComponent | null): Step[] {
  if (source !== "platform") return desktopSteps(source);
  return component === "web" ? WEB_STEPS : SERVER_STEPS;
}

function breadcrumbsFor(issue: Pick<StoredIssue, "source" | "component" | "message" | "severity">, at: number) {
  const steps = stepsFor(issue.source, issue.component);
  const crumbs: Breadcrumb[] = steps.map(([category, message], index) => ({
    timestamp: new Date(at - (steps.length - index) * 7_000).toISOString(),
    category,
    level: category === "console" ? "warning" : "info",
    message,
  }));
  crumbs.push({
    timestamp: new Date(at).toISOString(),
    category: "system",
    level: issue.severity === "warning" ? "warning" : "error",
    message: issue.message,
  });
  return crumbs;
}

function environmentFor(source: ErrorSource, component: PlatformComponent | null) {
  return source === "platform" && component !== "web" ? SERVER_ENVIRONMENT : ENVIRONMENTS[source];
}

function versionWeights(ageDays: number) {
  if (ageDays < 2) return [0.05, 0.2, 0.75];
  if (ageDays < 10) return [0.3, 0.6, 0.1];
  return [0.85, 0.15, 0];
}

/** Older events ran older builds: picks a version by the event's age. */
function versionAt(versions: string[], ageDays: number, random: () => number) {
  const weights = versionWeights(ageDays);
  let roll = random();
  for (let i = 0; i < versions.length; i++) {
    roll -= weights[i] ?? 0;
    if (roll <= 0) return versions[i];
  }
  return versions[versions.length - 1];
}

function seed(now: number): Store {
  const random = mulberry32(20261005);
  const pickFrom = <T>(items: readonly T[]) => items[Math.floor(random() * items.length)] as T;
  const issues = new Map<string, StoredIssue>();
  const events: StoredEvent[] = [];

  for (const template of TEMPLATES) {
    const frames = toFrames(template.frames, template.context);
    const fingerprint = hash(`${template.source}:${template.exception_type}:${culpritOf(frames)}`);
    const id = `err_${fingerprint.slice(0, 6)}`;
    const env = environmentFor(template.source, template.component);
    const userPool = USER_IDS.slice(0, template.users).sort(() => random() - 0.5);
    const first = now - template.first_days_ago * DAY;
    const last = now - template.last_hours_ago * HOUR;
    const count = Math.max(2, Math.min(700, Math.round(template.rate * ((last - first) / DAY + 0.3))));

    for (let i = 0; i < count; i++) {
      // The first and last events pin first/last seen; the rest fall in between.
      let at = first + random() * (last - first);
      if (i === 0) at = first;
      if (i === count - 1) at = last;
      events.push({
        id: `evt_${hash(`${id}:${i}`)}`,
        issue_id: id,
        at,
        app_version: versionAt(VERSIONS[template.source], (now - at) / DAY, random),
        os_version: pickFrom(env.os),
        device: pickFrom(env.devices),
        user_id: template.component === "api" && random() < 0.2 ? null : pickFrom(userPool),
      });
    }

    const platformServer = template.source === "platform" && template.component !== "web";
    const stored: StoredIssue = {
      id,
      fingerprint,
      exception_type: template.exception_type,
      message: template.message,
      culprit: culpritOf(frames),
      source: template.source,
      component: template.component,
      severity: template.severity,
      status: template.status,
      assignee_id: template.assignee_id,
      frames,
      breadcrumbs: [],
      tags: template.source === "platform" ? { region: "eu-central-1" } : { release_channel: "stable" },
      locale: platformServer ? null : "ru-RU",
      ticket: template.ticket ?? null,
    };
    stored.breadcrumbs = breadcrumbsFor(stored, last);
    issues.set(id, stored);
  }

  events.sort((a, b) => a.at - b.at);
  return { seededAt: now, issues, events };
}

const shared = globalThis as typeof globalThis & { adminErrorsDemo?: Store };

/** The demo store, kept across hot reloads and re-seeded when it gets stale. */
export function store(): Store {
  const now = Date.now();
  if (!shared.adminErrorsDemo || now - shared.adminErrorsDemo.seededAt > RESEED_AFTER)
    shared.adminErrorsDemo = seed(now);
  return shared.adminErrorsDemo;
}
