import type { LiveKitDevice } from "./contract";

/* Подпись устройства участника по атрибутам, что клиент заявил при входе; незаявленное не выдумывается. */

const OS_NAMES: Record<string, string> = {
  macos: "macOS",
  windows: "Windows",
  linux: "Linux",
  ios: "iOS",
  android: "Android",
};

/** «Leo для macOS 2.4.1 · macOS 15.1», «Chrome 141 · Ubuntu 24.04» или «Устройство не указано». */
export function deviceLabel(device: LiveKitDevice): string {
  const os = device.os === null ? null : (OS_NAMES[device.os] ?? device.os);
  const client =
    device.client === "web"
      ? (device.browser ?? "Браузер")
      : [os === null ? "Leo" : `Leo для ${os}`, device.client_version].filter(Boolean).join(" ");
  // В подписи приложения система уже названа; без версии системы она не повторяется.
  const app = device.client === "desktop" || device.client === "mobile";
  const system = device.os_version ?? (app ? null : os);
  const named = device.client !== null || device.browser !== null;
  return [named ? client : null, system].filter(Boolean).join(" · ") || "Устройство не указано";
}
