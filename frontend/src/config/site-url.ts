/**
 * The site's public address without a trailing slash, e.g. `https://example.com`, from `SITE_URL`.
 * Read at build time; when it is unset the sitemap is empty and absolute metadata URLs are left out.
 */
export const SITE_URL = process.env.SITE_URL?.trim().replace(/\/+$/, "") || null;
