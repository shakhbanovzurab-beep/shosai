import type { components } from "@/lib/api/generated/schema";

// Settings › Leo — маршруты среза agent (`/v1/agent/settings`, docs/leo-api.md).
export type LeoSettings = components["schemas"]["AgentSettingsOut"];
export type LeoSettingsPatch = components["schemas"]["AgentSettingsPatch"];
