import type { ReactNode } from "react";

import { useTranslations } from "use-intl";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

import type { Consents } from "../domain/consents";
import { LEGAL_PAGES } from "../domain/legal-pages";

function LegalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener" className="text-foreground underline underline-offset-4">
      {children}
    </a>
  );
}

function ConsentRow({
  id,
  checked,
  onChange,
  children,
}: {
  id: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  children: ReactNode;
}) {
  return (
    <div className="flex items-start gap-3">
      <Checkbox id={id} checked={checked} onCheckedChange={(value) => onChange(value === true)} className="mt-0.5" />
      <Label htmlFor={id} className="block font-normal text-muted-foreground text-sm leading-snug">
        {children}
      </Label>
    </div>
  );
}

/**
 * Согласия регистрации: обработка персональных данных — обязательно; трансграничная передача — обязательно для
 * аккаунта в России (данные живут в российском доме, обрабатываются в ЕС); новости — по желанию и сняты.
 */
export function ConsentChecks({
  id,
  value,
  crossBorder,
  onChange,
}: {
  id: string;
  value: Consents;
  crossBorder: boolean;
  onChange: (consents: Consents) => void;
}) {
  const t = useTranslations("identityRegistration");
  return (
    <div className="flex flex-col gap-3">
      <ConsentRow
        id={`${id}-personal-data`}
        checked={value.personalData}
        onChange={(personalData) => onChange({ ...value, personalData })}
      >
        {t.rich("consents.personalData", {
          terms: (chunks) => <LegalLink href={LEGAL_PAGES.terms}>{chunks}</LegalLink>,
          privacy: (chunks) => <LegalLink href={LEGAL_PAGES.privacy}>{chunks}</LegalLink>,
        })}
      </ConsentRow>
      {crossBorder ? (
        <ConsentRow
          id={`${id}-cross-border`}
          checked={value.crossBorder}
          onChange={(next) => onChange({ ...value, crossBorder: next })}
        >
          {t("consents.crossBorder")}
        </ConsentRow>
      ) : null}
      <ConsentRow
        id={`${id}-marketing`}
        checked={value.marketing}
        onChange={(marketing) => onChange({ ...value, marketing })}
      >
        {t("consents.marketing")}
      </ConsentRow>
    </div>
  );
}
