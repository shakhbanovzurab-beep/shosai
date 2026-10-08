import { type ComponentType, lazy, type ReactNode, Suspense } from "react";

type Loaded<P> = ComponentType<P> | { default: ComponentType<P> };

interface LazyOptions {
  /** Показывается, пока грузится код компонента. */
  loading?: () => ReactNode;
}

/**
 * Компонент, код которого грузится при первой отрисовке отдельным чанком, а пока показывается заглушка.
 * Объявляется на уровне модуля, как любой компонент: `const Chart = lazyComponent(() => import("./chart").then((m) => m.Chart))`.
 */
export function lazyComponent<P extends object>(load: () => Promise<Loaded<P>>, options: LazyOptions = {}) {
  const Lazy = lazy(async () => {
    const loaded = await load();
    return { default: "default" in loaded ? loaded.default : loaded };
  });
  const Loading = options.loading;
  function LazyComponent(props: P) {
    return (
      <Suspense fallback={Loading ? <Loading /> : null}>
        <Lazy {...props} />
      </Suspense>
    );
  }
  return LazyComponent;
}
