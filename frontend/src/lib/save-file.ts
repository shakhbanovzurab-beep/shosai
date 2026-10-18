/**
 * Saves the file behind a same-origin link under `name`, without leaving the page: the `download` attribute
 * works only on the page's own origin, and the cabinet's download links are on it (FL-D9).
 */
export function saveFile(url: string, name: string) {
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
}
