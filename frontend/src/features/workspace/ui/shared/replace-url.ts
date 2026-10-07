/** Mirrors a page's filters in the address bar without a navigation, so links and reloads keep them. */
export function replaceUrl(href: string) {
  window.history.replaceState(null, "", href);
}
