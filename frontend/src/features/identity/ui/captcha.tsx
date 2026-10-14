import { useEffect, useRef, useState } from "react";

import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { mountTurnstile, turnstileLanguage, turnstileSiteKey } from "../model/turnstile-host";

type CaptchaState = "loading" | "ready" | "failed";

/**
 * Проверка Turnstile: отдаёт токен, когда человек её прошёл, и null, когда токен истёк или проверка сломалась.
 * `onToken` должен быть стабильным (сеттер состояния); новая проверка — новый `key` у компонента. Сбой загрузки
 * назван словами и повторяем: проверка живёт в чужой сети, и молча запертая форма выглядела бы поломкой сайта.
 */
export function Captcha({ onToken }: { onToken: (token: string | null) => void }) {
  const [round, setRound] = useState(0);
  return <CaptchaWidget key={round} onToken={onToken} onRetry={() => setRound((current) => current + 1)} />;
}

function CaptchaWidget({ onToken, onRetry }: { onToken: (token: string | null) => void; onRetry: () => void }) {
  const t = useTranslations("identity");
  const locale = useLocale();
  const siteKey = turnstileSiteKey();
  const container = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<CaptchaState>("loading");

  useEffect(() => {
    const element = container.current;
    if (siteKey === null || element === null) return;
    let remove: (() => void) | null = null;
    let cancelled = false;
    mountTurnstile(element, {
      sitekey: siteKey,
      callback: onToken,
      "error-callback": () => {
        onToken(null);
        setState("failed");
      },
      "expired-callback": () => onToken(null),
      theme: "auto",
      language: turnstileLanguage(locale),
    })
      .then((unmount) => {
        if (cancelled) unmount();
        else {
          remove = unmount;
          setState("ready");
        }
      })
      .catch(() => {
        if (!cancelled) setState("failed");
      });
    return () => {
      cancelled = true;
      remove?.();
    };
  }, [siteKey, locale, onToken]);

  if (siteKey === null) {
    return (
      <p role="alert" className="text-destructive text-sm">
        {t("captcha.unavailable")}
      </p>
    );
  }
  return (
    <fieldset className="flex min-h-16 flex-col gap-2">
      <legend className="sr-only">{t("captcha.label")}</legend>
      <div ref={container} />
      {state === "loading" ? (
        <p aria-live="polite" className="text-muted-foreground text-sm">
          {t("captcha.loading")}
        </p>
      ) : null}
      {state === "failed" ? (
        <div role="alert" className="flex flex-col items-start gap-2 text-destructive text-sm">
          <p>{t("captcha.failed")}</p>
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            {t("captcha.retry")}
          </Button>
        </div>
      ) : null}
    </fieldset>
  );
}
