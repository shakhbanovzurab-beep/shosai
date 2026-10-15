import { ShosaiMark } from "@/components/shosai-mark";

/**
 * Знак Shosai на страницах входа: логотип и «SHOSAI» узким Bebas Neue в одну компактную строку. Надпись обрезана
 * по высоте заглавных (text-box) и стоит ровно по центру логотипа.
 */
export function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <ShosaiMark className="size-8" />
      <div className="font-(family-name:--font-wordmark) text-[1.75rem] leading-none tracking-[0.05em] [text-box:trim-both_cap_alphabetic]">
        {/* i18n-ignore: написание знака, не текст интерфейса */}SHOSAI
      </div>
    </div>
  );
}
