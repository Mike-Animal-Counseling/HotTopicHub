import assert from "node:assert/strict";
import { test, beforeEach } from "node:test";
import { safeExternalUrl } from "../src/safe-url.js";
import { api, hasAdminToken, setAdminToken } from "../src/api.js";

function storage() {
  const entries = new Map();
  return { getItem: (key) => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value), removeItem: (key) => entries.delete(key) };
}
beforeEach(() => {
  globalThis.localStorage = storage();
  globalThis.sessionStorage = storage();
});

test("untrusted source and image URLs reject executable schemes and credentials", () => {
  for (const value of ["javascript:alert(1)", "data:text/html,evil", "file:///etc/passwd", "/relative", "https://user:pass@example.com", "not a URL"]) {
    assert.equal(safeExternalUrl(value), undefined);
  }
  assert.equal(safeExternalUrl("https://example.com/article"), "https://example.com/article");
});

test("old persistent admin credentials are discarded", () => {
  localStorage.setItem("ADMIN_TOKEN", "old-token");
  assert.equal(hasAdminToken(), false);
  assert.equal(localStorage.getItem("ADMIN_TOKEN"), null);
  setAdminToken("tab-token");
  assert.equal(sessionStorage.getItem("ADMIN_TOKEN"), "tab-token");
  setAdminToken("");
  assert.equal(hasAdminToken(), false);
});

test("visitor requests include cookies without disclosing admin credentials", async () => {
  setAdminToken("admin-secret");
  let captured;
  globalThis.fetch = async (url, options) => {
    captured = { url, options };
    return { ok: true, headers: { get: () => "application/json" }, json: async () => ({}) };
  };
  await api.likeTopic(1);
  assert.equal(captured.options.credentials, "include");
  assert.equal(captured.options.headers["X-ADMIN-TOKEN"], undefined);
  await api.refreshRealtimeFeed();
  assert.equal(captured.options.headers["X-ADMIN-TOKEN"], "admin-secret");
});
