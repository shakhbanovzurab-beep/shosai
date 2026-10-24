import { APP_CONFIG } from "@/config/app-config";

// Высота заглавных Bebas Neue — 0,7em.
const CAP_HEIGHT_EM = 0.7;

/**
 * Название Shosai начертанием знака: заглавными, узким Bebas Neue, ровно по центру логотипа. `capHeight` — высота
 * заглавных в пикселях, размер шрифта выводится из неё; чётная высота в строке чётной высоты ставит буквы на целые
 * пиксели. Рамка обрезана по высоте заглавных (text-box). Где text-box нет (Firefox), строка остаётся 1em, а в ней
 * заглавные Bebas Neue занимают от 0,1em до 0,8em (по hhea- и по win-метрикам): надпись опущена на 0,05em, чтобы их
 * середина совпала с серединой строки. В тексте — «Shosai», заглавные даёт стиль: экранный диктор читает слово.
 */
export function ShosaiName({ capHeight }: { capHeight: number }) {
  return (
    <span
      className="font-(family-name:--font-wordmark) not-supports-[text-box:trim-both_cap_alphabetic]:relative not-supports-[text-box:trim-both_cap_alphabetic]:top-[0.05em] uppercase leading-none tracking-[0.05em] [text-box:trim-both_cap_alphabetic]"
      style={{ fontSize: `${capHeight / CAP_HEIGHT_EM}px` }}
    >
      {APP_CONFIG.name}
    </span>
  );
}
