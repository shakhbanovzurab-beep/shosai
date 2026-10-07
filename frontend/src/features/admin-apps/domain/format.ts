import type { AppArch, AppPlatform, ReleaseChannel, ReleaseStatus } from "./contract";

export const PLATFORM_LABELS: Record<AppPlatform, string> = { macos: "macOS", windows: "Windows" };
export const CHANNEL_LABELS: Record<ReleaseChannel, string> = { stable: "Стабильный", beta: "Бета" };
export const STATUS_LABELS: Record<ReleaseStatus, string> = {
  draft: "Черновик",
  published: "Опубликован",
  revoked: "Отозван",
};
export const ARCH_LABELS: Record<AppArch, string> = {
  apple_silicon: "Apple Silicon",
  intel: "Intel",
  universal: "Universal",
  x64: "x64",
  arm64: "ARM64",
};
export const MIN_OS_PLACEHOLDER: Record<AppPlatform, string> = { macos: "13.0", windows: "10.0.19045" };

const SIZE_OPTIONS = { style: "unit", unitDisplay: "short", maximumFractionDigits: 1 } as const;
/** Byte, kilobyte, megabyte, gigabyte — one formatter each, created once. */
const sizeFormats = [
  new Intl.NumberFormat("ru-RU", { ...SIZE_OPTIONS, unit: "byte" }),
  new Intl.NumberFormat("ru-RU", { ...SIZE_OPTIONS, unit: "kilobyte" }),
  new Intl.NumberFormat("ru-RU", { ...SIZE_OPTIONS, unit: "megabyte" }),
  new Intl.NumberFormat("ru-RU", { ...SIZE_OPTIONS, unit: "gigabyte" }),
] as const;
const countFormat = new Intl.NumberFormat("ru-RU");
const dateTimeFormat = new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" });
const dateFormat = new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium" });

/** 1024-based, e.g. «186,7 МБ». */
export function formatBytes(bytes: number) {
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < sizeFormats.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return sizeFormats[unit].format(value);
}

export const formatCount = (n: number) => countFormat.format(n);
export const formatDateTime = (iso: string) => dateTimeFormat.format(new Date(iso));
export const formatDate = (iso: string) => dateFormat.format(new Date(iso));
