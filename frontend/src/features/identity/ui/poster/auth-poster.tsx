import { ShosaiMark } from "@/components/shosai-mark";
import { APP_CONFIG } from "@/config/app-config";

import { PosterScene } from "./poster-scene";

/**
 * Левая колонка страниц входа: встреча, которую Shosai превращает в факты и напоминания. Всегда тёмная, в любой
 * теме (`dark` переключает токены внутри колонки), и целиком декоративна: читатель экрана её пропускает. Колонка —
 * контейнер, кегли сцены считаются от её ширины (cqi), а не от окна.
 */
export function AuthPoster() {
  return (
    <aside
      aria-hidden="true"
      className="@container dark relative isolate hidden flex-col overflow-hidden bg-background px-14 py-11 text-foreground lg:flex"
    >
      {/* Тонкая сетка, гаснущая к краям, — тот же фон, что у страницы «не найдено» в кабинете. */}
      <div
        aria-hidden="true"
        className="mask-[radial-gradient(ellipse_at_center,black_10%,transparent_70%)] absolute inset-0 -z-10 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-size-[56px_56px] opacity-40"
      />
      <div className="flex items-center gap-3">
        <ShosaiMark className="size-10" />
        {/* Знак «SHOSAI» набран узким Bebas Neue; подпись под ним — мелкая разреженная строка по ширине знака. Строки
            обрезаны по высоте заглавных (text-box), и блок ровно в высоту логотипа: текст не выходит за его края. */}
        <div className="flex h-10 w-fit flex-col justify-between py-px">
          <div className="font-(family-name:--font-wordmark) text-[2.5rem] leading-none tracking-[0.04em] [text-box:trim-both_cap_alphabetic]">
            {/* i18n-ignore: написание знака, не текст интерфейса */}SHOSAI
          </div>
          <div className="text-[0.5rem] text-muted-foreground uppercase leading-none tracking-[0.06em] [text-box:trim-both_cap_alphabetic]">
            {APP_CONFIG.tagline} · v{APP_CONFIG.version}
          </div>
        </div>
      </div>
      <PosterScene />
      <div className="mt-9 text-muted-foreground text-xs">{APP_CONFIG.copyright}</div>
    </aside>
  );
}
