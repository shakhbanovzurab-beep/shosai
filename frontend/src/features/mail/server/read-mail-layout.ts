import { cookies } from "next/headers";

import { MAIL_LAYOUT_COOKIE, parseMailLayout } from "../domain/mail-layout";

/** The inbox's saved panel sizes from the layout cookie, falling back to the default split. */
export async function readMailLayout(): Promise<number[]> {
  const cookieStore = await cookies();
  return parseMailLayout(cookieStore.get(MAIL_LAYOUT_COOKIE)?.value);
}
