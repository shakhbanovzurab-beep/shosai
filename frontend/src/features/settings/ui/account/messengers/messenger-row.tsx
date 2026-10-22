import type { ReactNode } from "react";

import { useFormatter, useTranslations } from "use-intl";

import { MessengerTile } from "@/components/brand/messenger-mark";
import type { LinkedMessenger, MessengerLink } from "@/features/identity/domain/messenger-links-contract";

/** Строка мессенджера: знак, что это за аккаунт и в каком он состоянии, действия; на телефоне действия ниже. */
export function MessengerRow({
  messenger,
  title,
  status,
  children,
}: {
  messenger: LinkedMessenger;
  title: ReactNode;
  status: ReactNode;
  children?: ReactNode;
}) {
  return (
    <li className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <MessengerTile messenger={messenger} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate font-medium text-sm">{title}</span>
          <span className="text-muted-foreground text-xs">{status}</span>
        </div>
      </div>
      {children ? <div className="flex shrink-0 flex-wrap gap-2 ps-11 sm:ps-0">{children}</div> : null}
    </li>
  );
}

/** «@mara · Mara Ivanova»: ник и имя так, как их показывает мессенджер. */
export function AccountName({ account }: { account: MessengerLink["account"] }) {
  return (
    <bdi>
      {account.handle ? `${account.handle} · ` : null}
      {account.name}
    </bdi>
  );
}

/** «@mara · Mara Ivanova · Linked on Oct 22, 2026». */
export function LinkedStatus({ link }: { link: MessengerLink }) {
  const t = useTranslations("settings");
  const format = useFormatter();
  return (
    <>
      <AccountName account={link.account} />
      {link.linked_at
        ? ` · ${t("messengers.linkedOn", { date: format.dateTime(new Date(link.linked_at), "medium") })}`
        : null}
    </>
  );
}
