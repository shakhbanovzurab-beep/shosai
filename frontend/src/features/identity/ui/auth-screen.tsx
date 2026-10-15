import type { ReactNode } from "react";

import { useTranslations } from "use-intl";

import { Card } from "@/components/ui/card";

import { LanguageMenu } from "./language-menu";
import { AuthPoster } from "./poster/auth-poster";
import { Wordmark } from "./wordmark";

/**
 * Страницы входа, регистрации, сброса пароля и подключения приложения: слева афиша (на широком экране), справа
 * форма. Каркас общий для всех этих страниц, поэтому афиша не начинается заново при переходе между ними.
 */
export function AuthScreen({ children }: { children: ReactNode }) {
  const t = useTranslations("identity");
  return (
    <main className="grid min-h-dvh bg-background lg:grid-cols-[1.2fr_1fr]">
      <AuthPoster />
      {/* Колонка формы прокручивается сама: высокая форма регистрации не прячет кнопку за край окна. */}
      <div className="flex min-w-0 flex-col bg-muted/40 px-5 py-6 sm:px-10 lg:max-h-dvh lg:overflow-y-auto">
        <header className="flex items-center justify-between gap-3">
          <div className="lg:invisible">
            <Wordmark />
          </div>
          <LanguageMenu />
        </header>
        <section className="mx-auto my-auto w-full max-w-sm py-10">
          {/* Одна строгая фраза над карточкой шрифтом знака SHOSAI — то, ради чего Shosai существует. */}
          <p className="font-(family-name:--font-wordmark) mb-5 text-balance text-center text-2xl uppercase leading-none tracking-[0.04em]">
            {t("screen.motto")}
          </p>
          {/* Весь шаг входа — в одной карточке кабинета: кнопки сервисов, почта, код, согласия. */}
          <Card className="gap-0 px-6 py-7 shadow-sm sm:px-8">{children}</Card>
        </section>
      </div>
    </main>
  );
}
