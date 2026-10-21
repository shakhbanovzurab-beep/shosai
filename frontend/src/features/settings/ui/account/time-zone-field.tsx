"use client";

import { useEffect, useState } from "react";

import { ChevronsUpDown } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Me } from "@/features/identity/domain/session";
import { browserTimeZone } from "@/i18n/time-zone";

import { saveTimeZoneChoice } from "../../model/account-actions";
import { prepareTimeZoneOptions, zoneLabel } from "../../model/time-zone-options";
import { TimeZoneList } from "./time-zone-list";

/**
 * Пояс профиля: «Автоматически» следует за браузером, выбранный вручную остаётся, пока человек не вернёт
 * автоматику. Список поясов готовится в простое браузера, пока раздел открыт, и рисуется, только когда его открыли.
 */
export function TimeZoneField({ id, me }: { id: string; me: Me }) {
  const t = useTranslations("settings");
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  useEffect(() => prepareTimeZoneOptions(locale), [locale]);
  const fixed = me.timezone_auto ? null : me.timezone;

  const choose = (zone: string | null) => {
    setOpen(false);
    if (zone !== fixed) void saveTimeZoneChoice(zone, t);
  };

  return (
    // Модальный: внутри диалога настроек иначе блокировка прокрутки съедает колесо мыши.
    <Popover open={open} onOpenChange={setOpen} modal>
      <PopoverTrigger asChild>
        <Button
          id={id}
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between font-normal sm:w-64"
        >
          <span className="truncate">
            {fixed === null
              ? t("profile.timeZoneAutomaticValue", { zone: zoneLabel(browserTimeZone()) })
              : zoneLabel(fixed)}
          </span>
          <ChevronsUpDown className="opacity-50" aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0" aria-label={t("profile.timeZone")}>
        <TimeZoneList fixed={fixed} onChoose={choose} />
      </PopoverContent>
    </Popover>
  );
}
