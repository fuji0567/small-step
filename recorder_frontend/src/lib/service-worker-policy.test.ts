import { describe, expect, it } from "vitest";

import { shouldHandleWithAppCache } from "./service-worker-policy";

describe("service worker cache policy", () => {
  it("アプリシェルとバージョン付き静的資産だけを対象にする", () => {
    expect(
      shouldHandleWithAppCache(new Request(`${location.origin}/rec/`)),
    ).toBe(true);
    expect(
      shouldHandleWithAppCache(
        new Request(`${location.origin}/rec/assets/index-abc.js`),
      ),
    ).toBe(true);
    expect(
      shouldHandleWithAppCache(
        new Request(`${location.origin}/rec/manifest.webmanifest`),
      ),
    ).toBe(true);
  });

  it("API・認証・音声・非GETを明示的に除外する", () => {
    expect(
      shouldHandleWithAppCache(
        new Request(`${location.origin}/api/v1/recorder/sessions`),
      ),
    ).toBe(false);
    expect(
      shouldHandleWithAppCache(
        new Request(`${location.origin}/rec/auth/session`),
      ),
    ).toBe(false);
    expect(
      shouldHandleWithAppCache(
        new Request(`${location.origin}/rec/assets/a.webm`, {
          headers: { Accept: "audio/webm" },
        }),
      ),
    ).toBe(false);
    expect(
      shouldHandleWithAppCache(
        new Request(`${location.origin}/rec/`, { method: "POST" }),
      ),
    ).toBe(false);
  });
});
