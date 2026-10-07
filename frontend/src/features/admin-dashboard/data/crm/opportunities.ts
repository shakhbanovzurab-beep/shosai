import { opportunitiesSchema } from "../../domain/crm/opportunity";
import opportunitiesData from "./opportunities.json";

export const opportunities = opportunitiesSchema.parse(opportunitiesData);
