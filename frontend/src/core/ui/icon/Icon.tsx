import type { CSSProperties } from "react";

import { cn } from "@/core/lib/cn";
import { CONTENT_GLYPHS } from "@/core/ui/icon/glyphsContent";
import { INTERFACE_GLYPHS } from "@/core/ui/icon/glyphsInterface";
import { MEDIA_GLYPHS } from "@/core/ui/icon/glyphsMedia";

const GLYPHS = { ...INTERFACE_GLYPHS, ...CONTENT_GLYPHS, ...MEDIA_GLYPHS };

/** Имя глифа набора. Закрытое: неизвестное имя — ошибка типов, а не пустое место на экране. */
export type IconName = keyof typeof GLYPHS;

/**
 * Глифы, которые указывают по ходу чтения, а не в сторону света: «назад»,
 * «вглубь», «отправить», «выйти». В письме справа налево они отражаются здесь,
 * а не на месте вызова. Диагональные, круговые, вертикальные глифы и знаки
 * отражать нельзя, а отличить их можно только по смыслу, поэтому список ручной.
 * Время записи течёт в одну сторону: play и pause не отражаются.
 */
const MIRRORED_IN_RTL: ReadonlySet<IconName> = new Set<IconName>([
  "chevron",
  "chevronLeft",
  "arrowLeft",
  "send",
  "logout",
]);

interface IconProps {
  readonly name: IconName;
  /** Размер в пикселях при кегле браузера по умолчанию; рисуется в em. */
  readonly size?: number;
  readonly stroke?: number;
  readonly className?: string;
  readonly style?: CSSProperties;
}

/**
 * Размер в em, а не в пикселях: значок следует кеглю своей строки, и пара
 * «значок + подпись» сохраняет пропорции при системном увеличении текста.
 * Делитель 16 — корневой кегль по умолчанию: `size={16}` даёт ровно 16px.
 */
const em = (px: number): string => `${px / 16}em`;

export function Icon({ name, size = 16, stroke = 1.8, className, style }: IconProps) {
  return (
    <svg
      width={em(size)}
      height={em(size)}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="square"
      strokeLinejoin="miter"
      // `block` последним: он выигрывает у класса вызывающего, как прежде
      // выигрывал встроенный display:block.
      className={cn(className, MIRRORED_IN_RTL.has(name) && "rtl-mirror", "block")}
      style={style}
      aria-hidden="true"
    >
      {GLYPHS[name]}
    </svg>
  );
}
