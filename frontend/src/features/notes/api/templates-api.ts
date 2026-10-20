import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

type Schemas = components["schemas"];
export type TemplateOut = Schemas["TemplateOut"];
export type TemplateIn = Schemas["TemplateIn"];

/** Шаблоны записи Leo на `/v1/notes/templates`: встроенные по кодам и свои шаблоны человека. */
export const templatesApi = {
  list: (): Promise<Schemas["TemplatesOut"]> => dataOf(apiClient.GET("/v1/notes/templates")),
  create: (body: TemplateIn): Promise<TemplateOut> => dataOf(apiClient.POST("/v1/notes/templates", { body })),
};
