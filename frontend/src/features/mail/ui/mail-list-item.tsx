import { cn } from "cn";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";

import type { InboxView, LeoMailView } from "../domain/leo-triage";
import type { Mail } from "../domain/mail";
import { LeoMailTags } from "./leo-mail-tags";
import { MailContextMenu } from "./mail-menu";
import { useMailDates } from "./use-mail-dates";

type MailListItemProps = {
  mail: Mail;
  view: LeoMailView | undefined;
  inboxView: InboxView;
  isSelected: boolean;
  onOpen: () => void;
};

/** One message in the list. In the "Needs you" view, Leo's next step takes the place of the preview. */
export function MailListItem({ mail, view, inboxView, isSelected, onOpen }: MailListItemProps) {
  const { listDate } = useMailDates();
  const nextStep = inboxView === "focus" ? view?.insight.next_step : null;

  return (
    <MailContextMenu mail={mail} onOpen={onOpen}>
      <button
        type="button"
        className={cn(
          "group relative w-full border-transparent border-y p-3 text-start transition-colors",
          "hover:bg-muted/60",
          isSelected &&
            "border-border bg-muted/70 before:absolute before:-inset-y-px before:start-0 before:w-0.5 before:bg-primary",
        )}
        onClick={(event) => {
          event.currentTarget.blur();
          onOpen();
        }}
      >
        <div className="flex items-start gap-3">
          <Avatar className="size-9 after:rounded-sm">
            <AvatarFallback className="rounded-sm bg-background">{mail.from.name[0]}</AvatarFallback>
          </Avatar>

          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div
                  className={cn("flex items-center gap-2 truncate font-normal text-sm", !mail.isRead && "font-medium")}
                >
                  <span dir="auto">{mail.from.name}</span>
                  {!mail.isRead && <span className="size-2 rounded-full bg-blue-600" />}
                </div>
                <div
                  dir="auto"
                  className={cn(
                    "truncate font-medium text-foreground text-xs",
                    mail.isRead && "font-normal text-muted-foreground",
                  )}
                >
                  {mail.subject}
                </div>
              </div>

              <div className={cn("shrink-0 text-muted-foreground text-xs", isSelected && "text-foreground")}>
                {listDate(mail.receivedAt).text}
              </div>
            </div>

            {nextStep ? (
              <p dir="auto" className="mt-2 line-clamp-2 text-foreground text-xs leading-5">
                {nextStep}
              </p>
            ) : (
              <p dir="auto" className="mt-2 line-clamp-2 text-muted-foreground text-xs leading-5">
                {mail.body}
              </p>
            )}

            <LeoMailTags mail={mail} view={view} inboxView={inboxView} />
          </div>
        </div>
      </button>
    </MailContextMenu>
  );
}
