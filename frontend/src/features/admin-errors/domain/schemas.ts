import { z } from "zod";

/* Request validation of the Admin › Errors routes; the demo answers 422 with the first issue's message. */

/** PATCH /admin/errors/{id}: see `UpdateIssueRequest`. */
export const updateIssueSchema = z
  .strictObject({
    status: z.enum(["new", "in_progress", "resolved", "ignored"]).optional(),
    assignee: z.string().min(1).nullable().optional(),
  })
  .refine((patch) => patch.status !== undefined || patch.assignee !== undefined, "Передайте status и/или assignee.");

const breadcrumbSchema = z.object({
  timestamp: z.iso.datetime({ offset: true }),
  category: z.enum(["navigation", "http", "ui", "console", "system"]),
  level: z.enum(["info", "warning", "error"]),
  message: z.string().max(1000),
});

/** POST /admin/errors/ingest: see `IngestEventRequest` in `./ingest`. */
export const ingestEventSchema = z.object({
  platform: z.enum(["macos", "windows", "web", "api", "agent"]),
  app_version: z.string().trim().min(1).max(40),
  os_version: z.string().trim().min(1).max(120),
  message: z.string().trim().min(1).max(2000),
  exception_type: z.string().trim().max(200).optional(),
  stack: z.string().max(100_000),
  fingerprint: z.string().trim().min(1).max(200).optional(),
  user_id: z.string().max(100).nullable().optional(),
  severity: z.enum(["critical", "error", "warning"]).optional(),
  device: z.string().max(120).optional(),
  locale: z.string().max(35).optional(),
  breadcrumbs: z.array(breadcrumbSchema).max(100).optional(),
  tags: z.record(z.string().max(64), z.string().max(200)).optional(),
  timestamp: z.iso.datetime({ offset: true }).optional(),
});
