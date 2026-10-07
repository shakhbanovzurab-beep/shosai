import { getTranslations } from "next-intl/server";

/** The title of the demo summary's section of notes from the user, in the request's interface language. */
export async function notesTitle() {
  const t = await getTranslations("settingsApi");
  return t("notesFromYou");
}
