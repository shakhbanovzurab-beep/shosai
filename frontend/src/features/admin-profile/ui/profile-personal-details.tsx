import { LockKeyhole } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

import type { ProfileRecord } from "../domain/profile";

export function PersonalDetails({ profile }: { profile: ProfileRecord }) {
  return (
    <>
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <h2 className="font-heading font-medium text-base">Личная информация</h2>
          <Badge className="rounded-sm" variant="outline">
            <LockKeyhole data-icon="inline-start" />
            Конфиденциально
          </Badge>
        </div>
        <dl className="grid gap-8 sm:grid-cols-2 xl:grid-cols-3 xl:gap-12">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Предпочитаемое имя</dt>
              <dd className="text-sm">{profile.preferredName}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Дата рождения</dt>
              <dd className="text-sm">{profile.dateOfBirth}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Полное имя</dt>
              <dd className="text-sm">{profile.legalName}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Личная почта</dt>
              <dd className="text-sm">{profile.personalEmail}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Местоимения</dt>
              <dd className="text-sm">{profile.pronouns}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Рабочий телефон</dt>
              <dd className="text-sm">{profile.workPhone}</dd>
            </div>
          </div>
        </dl>
      </div>

      <Separator className="my-4" />

      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <h2 className="font-heading font-medium text-base">Адрес и контакт для экстренной связи</h2>
          <Badge className="rounded-sm" variant="outline">
            <LockKeyhole data-icon="inline-start" />
            Конфиденциально
          </Badge>
        </div>
        <dl className="grid gap-8 sm:grid-cols-2 xl:grid-cols-3 xl:gap-12">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Домашний адрес</dt>
              <dd className="text-sm">{profile.address}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Экстренный контакт</dt>
              <dd className="text-sm">{profile.emergencyContact}</dd>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <dt className="text-muted-foreground text-xs">Экстренный телефон</dt>
              <dd className="text-sm">{profile.emergencyPhone}</dd>
            </div>
          </div>
        </dl>
      </div>
    </>
  );
}
