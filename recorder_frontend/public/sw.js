const CACHE_NAME = "small-step-recorder-shell-v1";
const APP_SHELL = ["/rec/", "/rec/manifest.webmanifest", "/rec/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter(
              (key) =>
                key.startsWith("small-step-recorder-shell-") &&
                key !== CACHE_NAME,
            )
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

function cacheable(request) {
  if (request.method !== "GET") return false;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return false;
  if (url.pathname.startsWith("/api/") || url.pathname.includes("/auth/"))
    return false;
  if (
    url.protocol === "blob:" ||
    request.destination === "audio" ||
    request.headers.get("accept")?.startsWith("audio/") ||
    /\.(?:m4a|mp4|webm|ogg|wav)$/i.test(url.pathname)
  )
    return false;
  return (
    url.pathname === "/rec/" ||
    url.pathname === "/rec/manifest.webmanifest" ||
    url.pathname === "/rec/icon.svg" ||
    url.pathname.startsWith("/rec/assets/")
  );
}

self.addEventListener("fetch", (event) => {
  if (!cacheable(event.request)) return;
  const url = new URL(event.request.url);
  if (event.request.mode === "navigate" || url.pathname === "/rec/") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            void caches
              .open(CACHE_NAME)
              .then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => caches.match(event.request)),
    );
    return;
  }
  event.respondWith(
    caches.match(event.request).then(
      (cached) =>
        cached ??
        fetch(event.request).then((response) => {
          if (!response.ok) return response;
          const copy = response.clone();
          void caches
            .open(CACHE_NAME)
            .then((cache) => cache.put(event.request, copy));
          return response;
        }),
    ),
  );
});
