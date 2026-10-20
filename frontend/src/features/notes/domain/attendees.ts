const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const sameEmail = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

export type AttendeeProblem = "invalid" | "duplicate";

/** Почему адрес нельзя добавить на встречу; null, если можно. */
export function attendeeProblem(value: string, attendees: readonly { email: string | null }[]): AttendeeProblem | null {
  if (!EMAIL.test(value.trim())) return "invalid";
  return attendees.some((person) => person.email !== null && sameEmail(person.email, value)) ? "duplicate" : null;
}

export const isOwnEmail = (email: string, ownEmail: string) => sameEmail(email, ownEmail);
