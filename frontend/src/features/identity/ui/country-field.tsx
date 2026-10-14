import { useLocale, useTranslations } from "use-intl";

import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";

import { COUNTRY_CODES, type CountryCode, isCountryCode } from "../domain/countries";

/** Страны с названиями на языке интерфейса, по алфавиту этого языка. */
function countryOptions(locale: string): { code: CountryCode; name: string }[] {
  const names = new Intl.DisplayNames([locale], { type: "region" });
  const collator = new Intl.Collator(locale);
  return COUNTRY_CODES.map((code) => ({ code, name: names.of(code) ?? code })).sort((a, b) =>
    collator.compare(a.name, b.name),
  );
}

/** Страна, которую человек подтверждает: она выбирает, где хранятся его данные. */
export function CountryField({
  id,
  value,
  onChange,
}: {
  id: string;
  value: CountryCode | null;
  onChange: (country: CountryCode) => void;
}) {
  const t = useTranslations("identityRegistration");
  const locale = useLocale();
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{t("country")}</Label>
      <NativeSelect
        id={id}
        className="w-full"
        required
        value={value ?? ""}
        aria-describedby={`${id}-hint`}
        onChange={(event) => {
          if (isCountryCode(event.target.value)) onChange(event.target.value);
        }}
      >
        <NativeSelectOption value="" disabled>
          {t("countryPlaceholder")}
        </NativeSelectOption>
        {countryOptions(locale).map((country) => (
          <NativeSelectOption key={country.code} value={country.code}>
            {country.name}
          </NativeSelectOption>
        ))}
      </NativeSelect>
      <p id={`${id}-hint`} className="text-muted-foreground text-xs">
        {t("countryHint")}
      </p>
    </div>
  );
}
