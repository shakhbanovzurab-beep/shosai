"use client";

import { useSyncExternalStore } from "react";

// The platform never changes while the page is open, so there is nothing to subscribe to.
const noSubscribe = () => () => undefined;
const isMacClient = () => /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

/** ⌘ ⌥ on Apple devices, Ctrl Alt elsewhere. The server renders the non-Mac labels. */
export const useIsMac = () => useSyncExternalStore(noSubscribe, isMacClient, () => false);
