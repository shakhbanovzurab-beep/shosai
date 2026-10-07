"use server";

import { cookies } from "next/headers";

import { getPreferencePersistence, PREFERENCE_REGISTRY, type PreferenceKey } from "../domain/registry";

// Only registered server-cookie preferences with a known value can be written. The cookie lands in the
// caller's own browser and is not httpOnly, so the action grants nothing the caller can't already do.
// react-doctor-disable-next-line react-doctor/server-auth-actions
export async function setPreferenceCookie(key: PreferenceKey, value: string): Promise<void> {
  const definition: { values: readonly string[] } | undefined = PREFERENCE_REGISTRY[key];
  if (!definition || getPreferencePersistence(key) !== "server-cookie" || !definition.values.includes(value)) {
    throw new Error("Invalid preference");
  }

  const cookieStore = await cookies();
  cookieStore.set(key, value, {
    path: "/",
    maxAge: 60 * 60 * 24 * 7, // 7 days
  });
}
