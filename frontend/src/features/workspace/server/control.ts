import { deleteWorkspace, everyWorkspace } from "./demo-store";
import { logEvent, seatsUsed } from "./events";
import type { WorkspaceData } from "./types";

/*
 * What the platform's team can do to any workspace from the admin panel, in the demo. Their routes
 * live in the admin slice; messages are in Russian because only that panel shows them.
 */

export type ControlResult = { ok: true; data: WorkspaceData } | { ok: false; status: number; message: string };

const MAX_SEATS = 500;

const GONE: ControlResult = { ok: false, status: 404, message: "Пространство не найдено: возможно, его удалили." };

export const platformWorkspaces = () => everyWorkspace();

export const platformWorkspace = (id: string) => everyWorkspace().find((d) => d.workspace.id === id) ?? null;

/** Seats paid for; never fewer than members plus pending invitations. */
export function setSeats(id: string, seats: number): ControlResult {
  const data = platformWorkspace(id);
  if (!data) return GONE;
  const used = seatsUsed(data);
  if (seats < used)
    return {
      ok: false,
      status: 409,
      message: `Мест не может быть меньше, чем занято: ${used} (участники и приглашения).`,
    };
  if (seats > MAX_SEATS) return { ok: false, status: 422, message: `Не больше ${MAX_SEATS} мест.` };
  const before = data.workspace.plan.seats;
  if (before === seats) return { ok: true, data };
  data.workspace.plan.seats = seats;
  logEvent(data, "seats_changed", null, { value: `${before} → ${seats}` });
  return { ok: true, data };
}

/** Pauses access for every member; their own Personal data isn't touched. */
export function suspendWorkspace(id: string, reason: string): ControlResult {
  const data = platformWorkspace(id);
  if (!data) return GONE;
  if (data.control.suspended) return { ok: false, status: 409, message: "Пространство уже приостановлено." };
  data.control.suspended = { at: new Date().toISOString(), reason };
  logEvent(data, "suspended", null, { value: reason });
  return { ok: true, data };
}

export function resumeWorkspace(id: string): ControlResult {
  const data = platformWorkspace(id);
  if (!data) return GONE;
  if (!data.control.suspended) return { ok: false, status: 409, message: "Пространство не приостановлено." };
  data.control.suspended = null;
  logEvent(data, "resumed", null);
  return { ok: true, data };
}

/** Hands ownership to another member, e.g. when the owner left the company; the old owner becomes an admin. */
export function transferOwnership(id: string, memberId: string): ControlResult {
  const data = platformWorkspace(id);
  if (!data) return GONE;
  const next = data.members.find((m) => m.id === memberId);
  if (!next) return { ok: false, status: 404, message: "Этого участника уже нет в пространстве." };
  if (next.role === "owner") return { ok: false, status: 409, message: "Этот участник уже владелец пространства." };
  for (const member of data.members) if (member.role === "owner") member.role = "admin";
  next.role = "owner";
  logEvent(data, "owner_transferred", null, { target: next.name });
  return { ok: true, data };
}

/** Deletes it as its owner would: shared recordings and files stay with the people who own them. */
export const removeWorkspace = (id: string) => deleteWorkspace(id);
