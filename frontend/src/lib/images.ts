export function resolveImageUrl(
  path: string | null | undefined,
): string | null {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  // Storage-relative paths are owner-private: fetch them through the
  // authenticated BFF media proxy instead of the backend origin directly.
  return `/api/media${path.startsWith("/") ? path : `/${path}`}`;
}
