// Google Tag Manager как транспорт (ADR 0047): тот же порядок, что у официального сниппета, но из
// модуля, а не inline-скриптом. Сначала Consent Mode v2 «всё запрещено», затем сохранённый выбор,
// и только потом gtm.js — так ни один тег не успевает поставить cookie до решения человека.
import { type ConsentChoice, consentSignals } from "../domain/consent";

/** Куда пишут команды: dataLayer страницы и вставка скрипта; в тестах — подделка. */
export type TagHost = {
  dataLayer: unknown[];
  appendScript: (src: string) => void;
};

// Сколько GTM ждёт обновления согласия, прежде чем запустить теги с умолчаниями.
const CONSENT_WAIT_MS = 500;

export function tagManagerUrl(containerId: string): string {
  return `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(containerId)}`;
}

// GTM понимает команды gtag только как объект arguments, массив он пропускает.
function pushArguments(this: unknown[], ..._command: unknown[]): void {
  // biome-ignore lint/complexity/noArguments: Consent Mode читает именно объект arguments.
  this.push(arguments);
}

function gtag(host: TagHost, ...command: unknown[]): void {
  pushArguments.apply(host.dataLayer, command);
}

/** Запускает контейнер: умолчания согласия, сохранённый выбор, событие старта и сам скрипт. */
export function startTagManager(host: TagHost, containerId: string, stored: ConsentChoice | null): void {
  gtag(host, "consent", "default", { ...consentSignals("denied"), wait_for_update: CONSENT_WAIT_MS });
  if (stored) gtag(host, "consent", "update", consentSignals(stored));
  host.dataLayer.push({ "gtm.start": Date.now(), event: "gtm.js" });
  host.appendScript(tagManagerUrl(containerId));
}

/** Передаёт GTM новое решение человека; теги перестраиваются без перезагрузки страницы. */
export function updateTagConsent(host: TagHost, choice: ConsentChoice): void {
  gtag(host, "consent", "update", consentSignals(choice));
}
