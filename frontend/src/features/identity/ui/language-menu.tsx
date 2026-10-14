import { Languages } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { DropdownMenuRadioGroup, DropdownMenuRadioItem } from "@/components/ui/dropdown-menu-items";
import { useSwitchLanguage } from "@/hooks/use-switch-language";
import { LANGUAGES } from "@/lib/language";

/** Язык интерфейса до входа: выбор живёт в cookie этого браузера, после регистрации он станет языком аккаунта. */
export function LanguageMenu() {
  const t = useTranslations("identity");
  const { language, switchLanguage } = useSwitchLanguage();
  const current = LANGUAGES.find((option) => option.code === language);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm">
          <Languages data-icon="inline-start" />
          <span className="sr-only">{t("screen.language")}</span>
          <span lang={language}>{current?.label}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-h-80 w-52 overflow-y-auto">
        <DropdownMenuRadioGroup value={language} onValueChange={switchLanguage}>
          {LANGUAGES.map((option) => (
            <DropdownMenuRadioItem key={option.code} value={option.code}>
              <span lang={option.code} dir="auto">
                {option.label}
              </span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
