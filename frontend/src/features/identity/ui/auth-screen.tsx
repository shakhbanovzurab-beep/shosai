import type { ReactNode } from "react";

import { ShosaiMark } from "@/components/shosai-mark";
import { APP_CONFIG } from "@/config/app-config";

import { LanguageMenu } from "./language-menu";
import { AuthPoster } from "./poster/auth-poster";

/**
 * Страницы входа, регистрации, сброса пароля и подключения приложения: слева афиша (на широком экране), справа
 * форма. Каркас общий для всех этих страниц, поэтому афиша не начинается заново при переходе между ними.
 */
export function AuthScreen({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-dvh bg-background lg:grid-cols-[1.2fr_1fr]">
      <AuthPoster />
      {/* Колонка формы прокручивается сама: высокая форма регистрации не прячет кнопку за край окна. */}
      <div className="flex min-w-0 flex-col px-5 py-6 sm:px-10 lg:max-h-dvh lg:overflow-y-auto">
        <header className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 font-semibold lg:invisible">
            <ShosaiMark className="size-5" />
            {APP_CONFIG.name}
          </div>
          <LanguageMenu />
        </header>
        <section className="mx-auto my-auto flex w-full max-w-sm flex-col py-10">{children}</section>
      </div>
    </main>
  );
}
