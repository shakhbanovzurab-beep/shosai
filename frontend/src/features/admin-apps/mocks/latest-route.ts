import { z } from "zod";

import { detail, JsonResponse } from "@/mocks/runtime";

import {
  APP_PLATFORMS,
  type AppArch,
  type LatestRelease,
  MACOS_ARCHS,
  RELEASE_CHANNELS,
  WINDOWS_ARCHS,
} from "../domain/contract";
import { latestRelease } from "./demo-store";

const querySchema = z.object({
  platform: z.enum(APP_PLATFORMS),
  channel: z.enum(RELEASE_CHANNELS).default("stable"),
  arch: z.enum([...MACOS_ARCHS, ...WINDOWS_ARCHS]).optional(),
  install_id: z.string().min(1).max(200).optional(),
});

/** /api/apps/latest */
export const latestAppReleaseRoute = {
  /**
   * Public, read-only: the newest published build for the download page and the apps' auto-updaters.
   * GET /api/apps/latest?platform=macos|windows&channel=stable|beta[&arch=…][&install_id=…]
   */
  async GET(request: Request) {
    const url = new URL(request.url);
    const query = querySchema.safeParse(Object.fromEntries(url.searchParams));
    if (!query.success) return detail("Укажите platform=macos|windows и, при необходимости, channel=stable|beta.", 422);
    const { platform, channel, arch, install_id } = query.data;
    const latest = latestRelease(platform, channel, (arch as AppArch | undefined) ?? null, install_id ?? null);
    if (!latest) return detail("Опубликованных сборок нет.", 404);
    return JsonResponse.json<LatestRelease>(latest, { headers: { "cache-control": "public, max-age=60" } });
  },
};
