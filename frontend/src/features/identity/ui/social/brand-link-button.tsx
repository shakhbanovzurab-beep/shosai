import type { CSSProperties, ReactNode } from "react";

import { cn } from "cn";
import { siGithub, siVk } from "simple-icons";
import { useLocale, useTranslations } from "use-intl";

import { providerName, type SocialProvider, socialStartUrl } from "../../domain/social-providers";
import { GOOGLE_BUTTON_FILL } from "../../model/brand-widgets";

// Знак Google — официальные четыре цвета; простой одноцветной иконки Google по правилам бренда недостаточно.
function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="size-5" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}

function SimpleMark({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" className="size-5 fill-current" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

// Знак Яндекса с кнопки «Войти с Яндекс ID» — те же контуры, цвет и размер 24 px, что у кнопки SDK Яндекса, поэтому
// ссылка сменяется кнопкой SDK без скачка: «Я» на русском экране, «Y» на остальных (так же выбирает знак и SDK).
const YANDEX_GLYPH_RU =
  "M24.7407 33.9778H29.0889V9.04443H22.7592C16.3929 9.04443 13.0538 12.303 13.0538 17.1176C13.0538 21.2731 15.2187 23.6163 19.0532 26.1609L21.3832 27.6987L18.3927 25.1907L12.4667 33.9778H17.1818L23.5115 24.5317L21.3098 23.0671C18.6496 21.2731 17.3469 19.8818 17.3469 16.8613C17.3469 14.2068 19.2183 12.4128 22.7776 12.4128H24.7223V33.9778H24.7407Z";
const YANDEX_GLYPH_LATIN =
  "M22.9515 24.2897C24.2907 27.223 24.737 28.2433 24.737 31.7665V36.4375H19.9544V28.5621L10.9313 8.9375H15.9211L22.9515 24.2897ZM28.8501 8.9375L22.9994 22.2332H27.8617L33.7284 8.9375H28.8501Z";

function YandexMark() {
  const glyph = useLocale() === "ru" ? YANDEX_GLYPH_RU : YANDEX_GLYPH_LATIN;
  return (
    <svg viewBox="0 0 44 44" className="size-6" aria-hidden="true">
      <circle cx="22" cy="22" r="22" fill="#FC3F1D" />
      <path fill="white" d={glyph} />
    </svg>
  );
}

// Цвета брендов VK и GitHub берутся из данных их знаков (simple-icons), а не набираются руками.
// `markAtStart` — знак у начала кнопки, текст по центру: так рисуют свои кнопки виджеты Яндекса и Google, и ссылка,
// стоящая на их месте, пока виджет грузится, сменяется им без скачка.
const BRANDS: Record<
  SocialProvider,
  { className: string; style?: CSSProperties; mark: ReactNode; markAtStart?: boolean }
> = {
  // Цвета — как у кнопки SDK Яндекса: чёрная в светлой теме, белая в тёмной.
  yandex: { className: "bg-black text-white dark:bg-white dark:text-black", mark: <YandexMark />, markAtStart: true },
  vk: { className: "text-white", style: { backgroundColor: `#${siVk.hex}` }, mark: <SimpleMark path={siVk.path} /> },
  google: {
    className: "border-zinc-300 bg-white text-zinc-900 dark:border-white/20 dark:bg-(--google-fill) dark:text-white",
    style: { "--google-fill": GOOGLE_BUTTON_FILL } as CSSProperties,
    mark: <GoogleMark />,
    markAtStart: true,
  },
  github: {
    className: "text-white dark:border-white/20",
    style: { backgroundColor: `#${siGithub.hex}` },
    mark: <SimpleMark path={siGithub.path} />,
  },
};

/**
 * Кнопка сервиса в его фирменном виде — для VK ID и GitHub (у них нет виджета для сайтов) и как запасная, если
 * виджет Яндекса или Google не загрузился. Это ссылка: уход к сервису — переход документа через бэкенд.
 */
export function BrandLinkButton({ provider, next }: { provider: SocialProvider; next: string }) {
  const t = useTranslations("identity");
  const language = useLocale();
  const brand = BRANDS[provider];
  return (
    <a
      href={socialStartUrl(provider, next, language)}
      style={brand.style}
      className={cn(
        "relative flex h-11 w-full items-center justify-center gap-2.5 rounded-lg border border-transparent font-medium text-sm outline-none transition-opacity hover:opacity-90 focus-visible:ring-3 focus-visible:ring-ring/50",
        brand.className,
      )}
    >
      {brand.markAtStart ? <span className="absolute start-3 flex">{brand.mark}</span> : brand.mark}
      {t("social.continueWith", { provider: providerName(provider, language) })}
    </a>
  );
}
