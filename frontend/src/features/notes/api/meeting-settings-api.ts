import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

/** Настройка встреч человека на `/v1/notes/settings` (план notes, шаг 12, MT-D6): хранить ли его встречи. */
export const meetingSettingsApi = {
  keepsMeetings: async (): Promise<boolean> => (await dataOf(apiClient.GET("/v1/notes/settings"))).keep_meetings,
  keepMeetings: async (keep: boolean): Promise<boolean> =>
    (await dataOf(apiClient.PUT("/v1/notes/settings", { body: { keep_meetings: keep } }))).keep_meetings,
};
