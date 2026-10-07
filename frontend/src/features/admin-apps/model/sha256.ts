/**
 * Web Crypto only exists in a secure context (HTTPS or localhost). On plain http the browser can't
 * hash the file, and the server's own checksum is used instead.
 */
export const canHashInBrowser = () => typeof window !== "undefined" && window.isSecureContext && !!crypto?.subtle;

/** Hex SHA-256 of a file. Web Crypto has no streaming digest, so the file is read whole once. */
export async function sha256Hex(file: Blob) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}
