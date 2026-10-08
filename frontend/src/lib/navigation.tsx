import type { ComponentProps } from "react";

import { useQueryClient } from "@tanstack/react-query";
import {
  Link as RouterLink,
  useLocation,
  useNavigate,
  useRevalidator,
  useParams as useRouterParams,
  useSearchParams as useRouterSearchParams,
} from "react-router";

/**
 * Единственный API навигации для слайсов. Он сохраняет форму, под которую написаны экраны (`href`,
 * `router.push`, `scroll: false`), так что роутер за ним можно заменить, не трогая экраны.
 */

type LinkProps = Omit<ComponentProps<typeof RouterLink>, "to" | "prefetch"> & {
  href: string;
  /** Сохранить позицию прокрутки, а не прокручивать наверх. */
  scroll?: boolean;
  /** Оставлен для мест вызова под роутеры с предзагрузкой; код маршрута грузится при переходе. */
  prefetch?: boolean;
};

/** Ссылка внутри приложения: клиентская навигация и настоящий `<a href>` для новых вкладок и вспомогательных технологий. */
export function Link({ href, scroll, prefetch: _prefetch, ...props }: LinkProps) {
  return <RouterLink to={href} preventScrollReset={scroll === false} {...props} />;
}

interface NavigateOptions {
  /** Сохранить позицию прокрутки, а не прокручивать наверх. */
  scroll?: boolean;
}

/** Императивная навигация: перейти, заменить адрес, шагнуть назад или перезагрузить данные страницы. */
export function useRouter() {
  const navigate = useNavigate();
  const revalidator = useRevalidator();
  const queryClient = useQueryClient();
  return {
    push: (href: string, options?: NavigateOptions) =>
      void navigate(href, { preventScrollReset: options?.scroll === false }),
    replace: (href: string, options?: NavigateOptions) =>
      void navigate(href, { replace: true, preventScrollReset: options?.scroll === false }),
    back: () => void navigate(-1),
    /** Заново загружает данные страницы: loader-ы маршрутов и все кешированные запросы. */
    refresh: () => Promise.all([revalidator.revalidate(), queryClient.invalidateQueries()]).then(() => undefined),
  };
}

/** Текущий путь без строки запроса. */
export function usePathname(): string {
  return useLocation().pathname;
}

/** Текущая строка запроса, только для чтения. */
export function useSearchParams(): URLSearchParams {
  return useRouterSearchParams()[0];
}

/** Динамические сегменты текущего маршрута, декодированные. */
export function useParams<T extends Record<string, string>>(): Partial<T> {
  return useRouterParams() as Partial<T>;
}
