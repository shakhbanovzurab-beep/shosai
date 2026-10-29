"use client";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { pickDriveFiles, preloadGooglePicker } from "@/lib/google-picker";

import { connectorsApi } from "../api/connectors-api";
import type { DrivePickerSetup } from "../domain/connectors-contract";
import { describeConnectorFailure } from "./connector-actions";

// Настройку Picker и скрипты Google тянем заранее, когда человек открывает меню строки: иначе окно согласия Google
// откроется позже жеста и браузер его заблокирует.
let setup: Promise<DrivePickerSetup> | null = null;

const setupOnce = () => {
  setup ??= connectorsApi.drivePicker().catch((error: unknown) => {
    setup = null;
    throw error;
  });
  return setup;
};

/** Google's Picker for the connected Drive: the files and folders chosen become open to Shosai. */
export function useDrivePicker() {
  const t = useTranslations("settingsConnectors");

  const prepare = () => {
    void setupOnce().catch(() => undefined);
    void preloadGooglePicker().catch(() => undefined);
  };

  const choose = async () => {
    try {
      const found = await setupOnce();
      const picked = await pickDriveFiles({
        developerKey: found.developer_key,
        appId: found.app_id,
        clientId: found.client_id,
        loginHint: found.login_hint,
      });
      if (picked && picked.length > 0) toast.success(t("toasts.filesChosen"));
    } catch (error) {
      toast.error(t("toasts.pickerFailed"), { description: describeConnectorFailure(error, t) });
    }
  };

  return { prepare, choose };
}
