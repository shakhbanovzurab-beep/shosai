import { useTranslations } from "use-intl";

import { APP_CONFIG } from "@/config/app-config";

/**
 * Заголовок и описание страницы в <head>; их отрисовывает сама страница (React поднимает их в head). Без них
 * действуют заголовок и описание продукта по умолчанию. Кабинет не индексируется: index.html отдаёт `noindex`,
 * граница добавляет `X-Robots-Tag`.
 */
export function PageMeta({ title, description }: Readonly<{ title?: string; description?: string }>) {
  const t = useTranslations("pages");
  return (
    <>
      <title>{title ?? APP_CONFIG.meta.title}</title>
      <meta name="description" content={description ?? t("meta.description")} />
    </>
  );
}
