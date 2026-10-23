import { cn } from "cn";

import { APP_CONFIG } from "@/config/app-config";

/**
 * Название Shosai начертанием знака: заглавными, узким Bebas Neue, с рамкой по высоте заглавных (text-box), чтобы
 * стоять ровно по центру логотипа. Заглавные даёт стиль, а в тексте — «Shosai»: экранный диктор читает слово, а не
 * буквы. Размер задаёт `className`.
 */
export function ShosaiName({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "font-(family-name:--font-wordmark) uppercase leading-none tracking-[0.05em] [text-box:trim-both_cap_alphabetic]",
        className,
      )}
    >
      {APP_CONFIG.name}
    </span>
  );
}
