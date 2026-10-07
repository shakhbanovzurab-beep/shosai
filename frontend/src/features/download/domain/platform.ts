import type { DesktopBuild, DesktopPlatform } from "./contract";

/** The visitor's system, as far as the request tells: a desktop platform we build for, or not. */
export type VisitorSystem = DesktopPlatform | "linux" | "mobile" | "unknown";

/**
 * From the `Sec-CH-UA-Platform` client hint (Chromium browsers send it by default) or the user agent.
 * iPads that ask for the desktop site report macOS; they're treated as macOS, which the page handles.
 */
export function detectSystem(userAgent: string | null, platformHint: string | null): VisitorSystem {
  const hint = platformHint?.replaceAll('"', "").toLowerCase();
  if (hint === "macos") return "macos";
  if (hint === "windows") return "windows";
  if (hint === "android" || hint === "ios") return "mobile";
  if (hint === "linux" || hint === "chrome os") return "linux";

  const ua = userAgent ?? "";
  if (/iPhone|iPad|iPod|Android|Mobile/i.test(ua)) return "mobile";
  if (/Macintosh|Mac OS X/i.test(ua)) return "macos";
  if (/Windows/i.test(ua)) return "windows";
  if (/Linux|X11|CrOS/i.test(ua)) return "linux";
  return "unknown";
}

export const PLATFORM_NAME: Record<DesktopPlatform, string> = { macos: "macOS", windows: "Windows" };

/** A universal build runs on both Mac chips; the UI words that, since it is a phrase rather than a name. */
export const UNIVERSAL_ARCH = "universal";

/** Chip and architecture names stay as they are in every language. */
const ARCH_NAME: Record<string, string> = {
  apple_silicon: "Apple silicon",
  intel: "Intel",
  x64: "x64",
  arm64: "ARM64",
};
export const archName = (arch: string) => ARCH_NAME[arch] ?? arch;

/** The build most visitors on the platform need first: Universal on macOS, x64 on Windows. */
const PREFERENCE: Record<DesktopPlatform, readonly string[]> = {
  macos: ["universal", "apple_silicon", "intel"],
  windows: ["x64", "arm64"],
};

/** The primary build and the others, in the platform's order of preference. */
export function orderBuilds(platform: DesktopPlatform, files: DesktopBuild[]) {
  const rank = (arch: string) => {
    const index = PREFERENCE[platform].indexOf(arch);
    return index === -1 ? PREFERENCE[platform].length : index;
  };
  const [primary, ...others] = files.toSorted((a, b) => rank(a.arch) - rank(b.arch));
  return { primary, others };
}

const MACOS_NAMES: Record<string, string> = {
  "11": "Big Sur",
  "12": "Monterey",
  "13": "Ventura",
  "14": "Sonoma",
  "15": "Sequoia",
  "26": "Tahoe",
};

/** The oldest system a build runs on, by name: "macOS 13 Ventura", "Windows 10". */
export function minimumSystem(platform: DesktopPlatform, minOsVersion: string) {
  if (platform === "macos") {
    const major = minOsVersion.split(".")[0] ?? minOsVersion;
    const name = MACOS_NAMES[major];
    return `macOS ${major}${name ? ` ${name}` : ""}`;
  }
  // Windows 11 shares the 10.0 version number and starts at build 22000.
  const build = Number(minOsVersion.split(".")[2] ?? 0);
  return `Windows ${build >= 22000 ? 11 : 10}`;
}
