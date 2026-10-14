import { useTranslations } from "use-intl";

import { ShosaiMark } from "@/components/shosai-mark";
import { APP_CONFIG } from "@/config/app-config";

import { PosterScene } from "./poster-scene";

/**
 * Левая колонка страниц входа: встреча, которую Shosai превращает в факты и напоминания. Всегда тёмная, в любой
 * теме (`dark` переключает токены внутри колонки), и целиком декоративна: читатель экрана её пропускает. Колонка —
 * контейнер, кегли сцены считаются от её ширины (cqi), а не от окна.
 */
export function AuthPoster() {
  const t = useTranslations("identityPoster");
  return (
    <aside
      aria-hidden="true"
      className="@container dark relative hidden flex-col overflow-hidden bg-background px-14 py-11 text-foreground lg:flex"
    >
      <div className="flex items-center gap-3.5">
        <ShosaiMark className="size-11" />
        <div>
          <div className="font-semibold text-2xl tracking-tight">{APP_CONFIG.name}</div>
          <div className="mt-0.5 font-bold font-mono text-[0.6875rem] text-yellow-300 uppercase tracking-widest">
            {t("tagline")} · v{APP_CONFIG.version}
          </div>
        </div>
      </div>
      <PosterScene />
      <div className="mt-9 font-semibold text-[0.65625rem] text-muted-foreground uppercase tracking-wider">
        {APP_CONFIG.copyright}
      </div>
    </aside>
  );
}
