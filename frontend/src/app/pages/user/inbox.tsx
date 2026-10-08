import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import { MAIL_LAYOUT_COOKIE, parseMailLayout } from "@/features/mail/domain/mail-layout";
import { MailInbox } from "@/features/mail/ui/mail-inbox";
import { readClientCookie } from "@/lib/cookie.client";

export function Component() {
  const t = useTranslations("mail");
  // Размеры панелей, сохранённые в cookie, читаются один раз при открытии страницы.
  const defaultLayout = parseMailLayout(readClientCookie(MAIL_LAYOUT_COOKIE) ?? undefined);
  return (
    <>
      <PageMeta title={t("meta.title")} description={t("meta.description")} />
      <MailInbox defaultLayout={defaultLayout} />
    </>
  );
}
