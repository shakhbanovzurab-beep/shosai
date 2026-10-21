export type ResourceState<T> =
  | { status: "loading" }
  | { status: "error"; message: string; cause?: unknown }
  | { status: "ready"; data: T; refreshing: boolean };

const POLL_MS = 1500;

/** One shared object: useSyncExternalStore needs a stable server snapshot. */
const LOADING = { status: "loading" } as const;

const never = () => false;

/**
 * A server resource as an external store for useSyncExternalStore: it loads when the first
 * component subscribes, re-fetches every 1.5 s while `isBusy(data)` (something is indexing or
 * syncing), and stops when nobody is listening. Keeps fetching out of effects and renders.
 * Without `isBusy` it loads once and refreshes only when asked.
 */
export function createPollingResource<T>(load: () => Promise<T>, isBusy: (data: T) => boolean = never) {
  let state: ResourceState<T> = LOADING;
  const listeners = new Set<() => void>();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let inFlight: Promise<void> | null = null;
  // Данные положены загрузчиком только что: первый подписчик не просит их второй раз.
  let seeded = false;

  const emit = () => {
    for (const listener of listeners) listener();
  };

  const schedule = () => {
    clearTimeout(timer);
    if (listeners.size > 0 && state.status === "ready" && isBusy(state.data))
      timer = setTimeout(() => void refresh(), POLL_MS);
  };

  function refresh(): Promise<void> {
    if (inFlight !== null) return inFlight;
    if (state.status === "ready") {
      state = { ...state, refreshing: true };
      emit();
    }
    inFlight = load()
      .then(
        (data) => {
          state = { status: "ready", data, refreshing: false };
        },
        (error: unknown) => {
          // The screen words the failure itself; this is only the backend's detail, if any.
          const message = error instanceof Error ? error.message : "";
          // Keep showing data we already have; only a first load failing is an error state.
          state = state.status === "ready" ? { ...state, refreshing: false } : { status: "error", message, cause: error };
        },
      )
      .finally(() => {
        inFlight = null;
        emit();
        schedule();
      });
    return inFlight;
  }

  return {
    subscribe(listener: () => void) {
      listeners.add(listener);
      if (listeners.size === 1) {
        if (seeded) schedule();
        else void refresh();
        seeded = false;
      }
      return () => {
        listeners.delete(listener);
        if (listeners.size === 0) clearTimeout(timer);
      };
    },
    getSnapshot: () => state,
    getServerSnapshot: (): ResourceState<T> => LOADING,
    refresh,
    /** Чтение, начатое уже после вызова: идущее могло уйти раньше изменения, и его ответ его не знает. */
    async reload(): Promise<void> {
      if (inFlight !== null) await inFlight;
      await refresh();
    },
    /** Drops the data (e.g. it belonged to a workspace the user left); it loads afresh when next needed. */
    reset() {
      clearTimeout(timer);
      state = LOADING;
      emit();
      // Components that go away with the data unsubscribe during this render; whoever still listens reloads.
      setTimeout(() => {
        if (listeners.size > 0 && state.status === "loading") void refresh();
      }, 0);
    },
    /** Кладёт данные, уже прочитанные в другом месте (загрузчиком маршрута), и опрашивает дальше, если нужно. */
    seed(data: T) {
      state = { status: "ready", data, refreshing: false };
      seeded = listeners.size === 0;
      emit();
      schedule();
    },
    /** Applies a local change straight away (e.g. a new upload) and resumes polling if it is now busy. */
    update(change: (data: T) => T) {
      if (state.status !== "ready") return;
      state = { ...state, data: change(state.data) };
      emit();
      schedule();
    },
  };
}

export type PollingResource<T> = ReturnType<typeof createPollingResource<T>>;
