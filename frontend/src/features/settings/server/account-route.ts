import { NextResponse } from "next/server";

import { getLocale, getTranslations } from "next-intl/server";
import { z } from "zod";

import { formatBytes } from "@/i18n/format-units";
import { detail, forwardToBackend } from "@/server/backend-proxy";

import { AVATAR_MAX_BYTES, AVATAR_TYPES, type UserSettings } from "../domain/settings-contract";
import { getSettings, setAvatar } from "./demo-settings";
import { readJson, refuse } from "./problems";

const AVATAR_PATH = "/v1/settings/avatar";

/** /api/settings/account/delete */
export const deleteAccountRoute = {
  /**
   * Deletes the account and everything in it once the typed email matches. The demo has no account to
   * delete, so after checking the email it says so instead of pretending.
   */
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/settings/account/delete");
    if (upstream) return upstream;
    const body = z.object({ confirm_email: z.string().trim() }).safeParse(await readJson(request));
    if (!body.success) return refuse("invalidRequest", 422);
    if (body.data.confirm_email.toLowerCase() !== getSettings().email.toLowerCase()) {
      return refuse("emailMismatch", 422);
    }
    return refuse("deletionUnavailable", 501);
  },
};

/** /api/settings/avatar */
export const avatarRoute = {
  /** multipart/form-data with the already-scaled image in `file`. */
  async PUT(request: Request) {
    const upstream = await forwardToBackend(request, AVATAR_PATH);
    if (upstream) return upstream;
    const form = await request.formData().catch(() => null);
    const file = form?.get("file");
    if (!(file instanceof File)) return refuse("avatarMissing", 422);
    if (!(AVATAR_TYPES as readonly string[]).includes(file.type)) return refuse("avatarType", 422);
    if (file.size > AVATAR_MAX_BYTES) {
      const [t, locale] = await Promise.all([getTranslations("settingsApi"), getLocale()]);
      return detail(t("avatarTooLarge", { size: formatBytes(locale, AVATAR_MAX_BYTES) }), 413);
    }
    const base64 = Buffer.from(await file.arrayBuffer()).toString("base64");
    return NextResponse.json<UserSettings>(setAvatar(`data:${file.type};base64,${base64}`));
  },

  async DELETE(request: Request) {
    const upstream = await forwardToBackend(request, AVATAR_PATH);
    if (upstream) return upstream;
    return NextResponse.json<UserSettings>(setAvatar(null));
  },
};
