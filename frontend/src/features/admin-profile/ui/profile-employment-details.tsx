import { Separator } from "@/components/ui/separator";

import type { ProfileRecord } from "../domain/profile";
import { engagementStatusLabels } from "../domain/profile-labels";

export function EmploymentDetails({ profile }: { profile: ProfileRecord }) {
  return (
    <>
      <div className="flex flex-col gap-2">
        <h2 className="font-heading font-medium text-base">Должность и подразделение</h2>
        <dl className="grid gap-8 sm:grid-cols-2 xl:grid-cols-3 xl:gap-12">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Должность</dt>
              <dd className="text-sm">{profile.jobTitle}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Команда</dt>
              <dd className="text-sm">{profile.team}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Грейд</dt>
              <dd className="text-sm">{profile.jobLevel}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Руководитель</dt>
              <dd className="text-sm">{profile.manager.name}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Отдел</dt>
              <dd className="text-sm">{profile.department}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Текущий проект</dt>
              <dd className="text-sm">{profile.currentProject}</dd>
            </div>
          </div>
        </dl>
      </div>

      <Separator className="my-4" />

      <div className="flex flex-col gap-2">
        <h2 className="font-heading font-medium text-base">Условия договора</h2>
        <dl className="grid gap-8 sm:grid-cols-2 xl:grid-cols-3 xl:gap-12">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">ID подрядчика</dt>
              <dd className="text-sm">{profile.contractorId}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Статус сотрудничества</dt>
              <dd className="text-sm">{engagementStatusLabels[profile.engagementStatus]}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Тип занятости</dt>
              <dd className="text-sm">{profile.employmentType}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Юрлицо-заказчик</dt>
              <dd className="text-sm">{profile.contractingEntity}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Дата начала</dt>
              <dd className="text-sm">{profile.startDate}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Последний рабочий день</dt>
              <dd className="text-sm">{profile.lastWorkingDay}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Срок уведомления</dt>
              <dd className="text-sm">{profile.noticePeriod}</dd>
            </div>
          </div>
        </dl>
      </div>

      <Separator className="my-4" />

      <div className="flex flex-col gap-2">
        <h2 className="font-heading font-medium text-base">Формат работы</h2>
        <dl className="grid gap-8 sm:grid-cols-2 xl:grid-cols-3 xl:gap-12">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Место работы</dt>
              <dd className="text-sm">{profile.workplace}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Часовой пояс</dt>
              <dd className="text-sm">{profile.timeZone}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Часов в неделю</dt>
              <dd className="text-sm">{profile.weeklyHours}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">График</dt>
              <dd className="text-sm">{profile.schedule}</dd>
            </div>
          </div>
        </dl>
      </div>
    </>
  );
}
