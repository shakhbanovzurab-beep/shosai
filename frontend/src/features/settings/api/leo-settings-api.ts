import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type { LeoSettings, LeoSettingsPatch } from "../domain/leo-settings-contract";

// Settings › Leo — маршруты среза agent (`/v1/agent/settings`, план agent, шаг 3).

export const leoSettingsApi = {
  get: (): Promise<LeoSettings> => dataOf(apiClient.GET("/v1/agent/settings")),
  patch: (patch: LeoSettingsPatch): Promise<LeoSettings> =>
    dataOf(apiClient.PATCH("/v1/agent/settings", { body: patch })),
};
