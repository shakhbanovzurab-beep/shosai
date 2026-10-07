import type { NoteParticipant } from "./types";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const sameEmail = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

/** "sam.stephenson@acme.com" → "Sam Stephenson" */
export function nameFromEmail(email: string) {
  const local = email.slice(0, email.indexOf("@"));
  const words = local.split(/[._-]+/).filter(Boolean);
  return words.length ? words.map((word) => word[0].toUpperCase() + word.slice(1)).join(" ") : email;
}

export type AttendeeProblem = "invalid" | "duplicate";

/** Why an address can't be added to the meeting, or null when it can. */
export function attendeeProblem(value: string, attendees: NoteParticipant[]): AttendeeProblem | null {
  if (!EMAIL.test(value.trim())) return "invalid";
  return attendees.some((person) => sameEmail(person.email, value)) ? "duplicate" : null;
}

export const isOwnEmail = (email: string, ownEmail: string) => sameEmail(email, ownEmail);
