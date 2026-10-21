"use client";

import { useState } from "react";

import { useLocale, useTranslations } from "use-intl";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { browserTimeZone } from "@/i18n/time-zone";

import { shownZones, timeZoneOptions, zoneClock } from "../../model/time-zone-options";

/**
 * Список поясов с поиском. У каждого — его время сейчас: «Europe/Kirov» от «Europe/Moscow» по имени не отличить,
 * а по часам видно сразу. Фильтрует сам (`shouldFilter={false}`) и рисует не больше 50 строк.
 */
export function TimeZoneList({ fixed, onChoose }: { fixed: string | null; onChoose: (zone: string | null) => void }) {
  const t = useTranslations("settings");
  const locale = useLocale();
  const [query, setQuery] = useState("");
  // Время на момент открытия списка: у каждого пояса — свои часы, и тикать им незачем.
  const [openedAt] = useState(() => Date.now());
  const options = timeZoneOptions(locale);
  const automatic = t("profile.timeZoneAutomatic");
  const showsAutomatic = automatic.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
  const { zones, more } = shownZones(options, query, fixed);

  return (
    <Command shouldFilter={false}>
      <CommandInput placeholder={t("profile.timeZoneSearch")} value={query} onValueChange={setQuery} />
      <CommandList className="max-h-80">
        <CommandEmpty>{t("profile.timeZoneNoMatch")}</CommandEmpty>
        {showsAutomatic ? (
          <>
            <CommandGroup>
              <CommandItem value="automatic" data-checked={fixed === null} onSelect={() => onChoose(null)}>
                <ZoneLine label={automatic} clock={zoneClock(browserTimeZone(), locale).format(openedAt)} />
              </CommandItem>
            </CommandGroup>
            <CommandSeparator />
          </>
        ) : null}
        <CommandGroup>
          {zones.map((option) => (
            <CommandItem
              key={option.zone}
              value={option.zone}
              data-checked={option.zone === fixed}
              onSelect={() => onChoose(option.zone)}
            >
              <ZoneLine label={option.label} clock={zoneClock(option.zone, locale).format(openedAt)} dir="ltr" />
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
      {more ? <p className="border-t px-3 py-2 text-muted-foreground text-xs">{t("profile.timeZoneMore")}</p> : null}
    </Command>
  );
}

// Имя слева, время справа; отметка выбранного пункта — следом, у самого края.
function ZoneLine({ label, clock, dir }: { label: string; clock: string; dir?: "ltr" }) {
  return (
    <span className="flex min-w-0 flex-1 items-center justify-between gap-3">
      <span dir={dir} className="truncate">
        {label}
      </span>
      <span className="shrink-0 text-muted-foreground text-xs tabular-nums">{clock}</span>
    </span>
  );
}
