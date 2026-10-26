import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type { Skill, SkillSearchResponse, SkillsResponse } from "../domain/contract";

/* Хранилище навыков Leo (`/v1/agent/skills*`, agent шаг 15): установленные, поиск в skills.sh, скан репозитория. */

const path = (id: string) => ({ params: { path: { skill_id: id } } });

export const skillsApi = {
  list: (): Promise<SkillsResponse> => dataOf(apiClient.GET("/v1/agent/skills")),
  search: (q: string): Promise<SkillSearchResponse> =>
    dataOf(apiClient.GET("/v1/agent/skills/search", { params: { query: { q } } })),
  scan: (repository: string): Promise<SkillSearchResponse> =>
    dataOf(apiClient.POST("/v1/agent/skills/scan", { body: { repository } })),
  install: (reference: string): Promise<Skill> => dataOf(apiClient.POST("/v1/agent/skills", { body: { reference } })),
  update: (id: string): Promise<Skill> => dataOf(apiClient.POST("/v1/agent/skills/{skill_id}/update", path(id))),
  uninstall: async (id: string): Promise<void> => {
    await dataOf(apiClient.DELETE("/v1/agent/skills/{skill_id}", path(id)));
  },
};
