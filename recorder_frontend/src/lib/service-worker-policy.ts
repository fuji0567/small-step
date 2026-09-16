export function shouldHandleWithAppCache(request: Request): boolean {
  if (request.method !== "GET") return false;
  const url = new URL(request.url);
  if (url.origin !== location.origin) return false;
  if (url.pathname.startsWith("/api/")) return false;
  if (url.pathname.includes("/auth/")) return false;
  if (
    url.protocol === "blob:" ||
    request.destination === "audio" ||
    request.headers.get("accept")?.startsWith("audio/") ||
    /\.(?:m4a|mp4|webm|ogg|wav)$/i.test(url.pathname)
  ) {
    return false;
  }
  return (
    url.pathname === "/rec/" ||
    url.pathname === "/rec/manifest.webmanifest" ||
    url.pathname === "/rec/icon.svg" ||
    url.pathname.startsWith("/rec/assets/")
  );
}
