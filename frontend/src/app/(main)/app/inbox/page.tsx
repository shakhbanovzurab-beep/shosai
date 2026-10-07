import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { MailInbox } from "@/features/mail";
import { readMailLayout } from "@/features/mail/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("mail");
  return {
    title: t("meta.title"),
    description: t("meta.description"),
    alternates: {
      canonical: "/app/inbox",
    },
  };
}

export default async function Page() {
  return <MailInbox defaultLayout={await readMailLayout()} />;
}
