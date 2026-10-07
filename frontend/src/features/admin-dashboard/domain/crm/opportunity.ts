import z from "zod";

const opportunitySchema = z.object({
  id: z.string(),
  account: z.string(),
  stage: z.string(),
  priority: z.number(),
  health: z.string(),
  value: z.string(),
});

export const opportunitiesSchema = z.array(opportunitySchema);

export type OpportunityRow = z.infer<typeof opportunitySchema>;

/** Filter options of the opportunities table, in display order; "all" clears the filter. */
export const stageOptions = ["all", "Proposal Sent", "Discovery", "Negotiation", "Qualified"] as const;
export const healthOptions = ["all", "On Track", "Needs Review", "At Risk", "On Hold"] as const;
