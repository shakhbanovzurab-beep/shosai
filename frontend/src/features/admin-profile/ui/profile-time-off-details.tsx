import { Separator } from "@/components/ui/separator";

import type { ProfileRecord } from "../domain/profile";

export function TimeOffDetails({ profile }: { profile: ProfileRecord }) {
  return (
    <>
      <div className="flex flex-col gap-2">
        <h2 className="font-heading font-medium text-base">Баланс отпуска</h2>
        <dl className="grid gap-8 sm:grid-cols-2 xl:grid-cols-3 xl:gap-12">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Политика</dt>
              <dd className="text-sm">{profile.leavePolicy}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Перенесено</dt>
              <dd className="text-sm">{profile.carriedOverLeave}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Годовой лимит</dt>
              <dd className="text-sm">{profile.annualLeaveAllowance}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Использовано в этом году</dt>
              <dd className="text-sm">{profile.usedLeave}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Осталось</dt>
              <dd className="text-sm">{profile.remainingLeave}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Запланировано</dt>
              <dd className="text-sm">{profile.scheduledLeave}</dd>
            </div>
          </div>
        </dl>
      </div>

      <Separator className="my-4" />

      <div className="flex flex-col gap-2">
        <h2 className="font-heading font-medium text-base">Ближайшие отпуска и согласования</h2>
        <dl className="grid gap-8 sm:grid-cols-2 xl:grid-cols-3 xl:gap-12">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Следующий отпуск</dt>
              <dd className="text-sm">{profile.nextLeave}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Заявки на рассмотрении</dt>
              <dd className="text-sm">{profile.pendingLeaveRequests}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Отпускной год</dt>
              <dd className="text-sm">{profile.leaveYear}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Согласующий</dt>
              <dd className="text-sm">{profile.manager.name}</dd>
            </div>
          </div>
        </dl>
      </div>
    </>
  );
}
