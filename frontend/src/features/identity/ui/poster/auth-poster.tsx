import { APP_CONFIG } from "@/config/app-config";

import { Wordmark } from "../wordmark";
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
      <Wordmark />
      <PosterScene />
      <div className="mt-9 text-muted-foreground text-xs">{APP_CONFIG.copyright}</div>
    </aside>
  );
}
