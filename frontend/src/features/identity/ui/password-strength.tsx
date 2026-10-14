import { cn } from "cn";
import { useTranslations } from "use-intl";

import { checkPassword, type PasswordStrength as Strength } from "../domain/password-rules";

const TONE: Record<Strength, string> = {
  weak: "bg-red-500",
  fair: "bg-amber-500",
  good: "bg-sky-500",
  strong: "bg-emerald-500",
};

const SEGMENTS = [1, 2, 3, 4] as const;

/**
 * Подсказка к новому паролю: полоса, уровень и то, что ещё можно добавить. Советует и не запрещает — сервер
 * требует только длину, и форма не спорит с ним. Пустое поле подсказку не показывает.
 */
export function PasswordStrength({ password }: { password: string }) {
  const t = useTranslations("identityRegistration");
  if (password.length === 0) return null;
  const { strength, score, unmet } = checkPassword(password);
  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      <div className="flex items-center gap-3">
        <div aria-hidden="true" className="flex h-1.5 flex-1 gap-1">
          {SEGMENTS.map((segment) => (
            <span
              key={segment}
              className={cn("flex-1 rounded-full bg-muted transition-colors", segment <= score && TONE[strength])}
            />
          ))}
        </div>
        <span className="text-muted-foreground text-xs">
          {t("strength.label", { level: t(`strength.levels.${strength}`) })}
        </span>
      </div>
      {unmet.length > 0 ? (
        <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-muted-foreground text-xs">
          {unmet.map((rule) => (
            <li key={rule} className="flex items-center gap-2">
              <span aria-hidden="true" className="size-1 shrink-0 rounded-full bg-muted-foreground/60" />
              {t(`strength.rules.${rule}`)}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
