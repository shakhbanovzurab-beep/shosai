import type { ReactNode } from "react";

import { ScrollArea } from "@/components/ui/scroll-area";

import type { InboxView, LeoMailView } from "../domain/leo-triage";
import type { Mail } from "../domain/mail";
import { mailActions } from "../model/mail-store";
import { useMail } from "../model/use-mail";
import { MailListItem } from "./mail-list-item";

type MailGroup = {
  id: string;
  /** The group's heading with its count: "Pinned (2)". */
  title: string;
  items: Mail[];
};

interface MailListProps {
  groups: MailGroup[];
  /** Leo's reading of each message, by mail id. */
  views: ReadonlyMap<string, LeoMailView>;
  inboxView: InboxView;
  /** Shown after the last group, inside the scroll area. */
  footer?: ReactNode;
  onSelectMail?: (mail: Mail) => void;
}

export function MailList({ groups, views, inboxView, footer, onSelectMail }: MailListProps) {
  const [mail, setMail] = useMail();

  const open = (item: Mail) => {
    setMail({ ...mail, selected: item.id });
    mailActions.markRead(item.id);
    onSelectMail?.(item);
  };

  return (
    <ScrollArea className="**:data-[slot=scroll-area-viewport]:scroll-fade min-h-0 flex-1">
      <div className="flex flex-col gap-1.5 pt-0">
        {groups.map((group) => (
          <section key={group.id} className="flex flex-col gap-1.5">
            <div className="mx-3 text-muted-foreground text-xs">{group.title}</div>

            <div className="flex flex-col">
              {group.items.map((item) => (
                <MailListItem
                  key={item.id}
                  mail={item}
                  view={views.get(item.id)}
                  inboxView={inboxView}
                  isSelected={mail.selected === item.id}
                  onOpen={() => open(item)}
                />
              ))}
            </div>
          </section>
        ))}
        {footer}
      </div>
    </ScrollArea>
  );
}
