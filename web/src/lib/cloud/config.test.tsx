import { describe, expect, it, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { CLOUD_ENABLED, cloudConfig, parseFirebaseConfig } from "./config";

// no @types/node guarantee in this project: read the sources with node:fs through file URLs (same trick as ThemeToggle.test.tsx)
// @ts-ignore node:fs has no type declarations unless @types/node is installed (it arrives transitively with firebase)
const fs = (await import("node:fs")) as { readFileSync(u: URL, enc: string): string; readdirSync(u: URL, o: { withFileTypes: true }): { name: string; isDirectory(): boolean }[] };
const SRC = new URL("../../", import.meta.url);
function walk(dir: URL, out: string[] = []): string[] {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.isDirectory()) walk(new URL(`${e.name}/`, dir), out);
    else if (/\.(ts|tsx)$/.test(e.name)) out.push(new URL(e.name, dir).href);
  }
  return out;
}
const read = (href: string) => fs.readFileSync(new URL(href), "utf8");
const isTest = (href: string) => /\.test\.tsx?$|testkit\.ts$/.test(href);

describe("feature flag", () => {
  it("needs all four values", () => {
    const all = { apiKey: "k", authDomain: "d.firebaseapp.com", projectId: "p", appId: "1:2:web:3" };
    expect(parseFirebaseConfig(all)).toEqual(all);
    expect(parseFirebaseConfig({ ...all, apiKey: "" })).toBeNull();
    expect(parseFirebaseConfig({ ...all, appId: undefined })).toBeNull();
    expect(parseFirebaseConfig({ ...all, projectId: "   " })).toBeNull();
    expect(parseFirebaseConfig({})).toBeNull();
    expect(parseFirebaseConfig({ ...all, apiKey: "  k " })?.apiKey).toBe("k");
  });
  it("is off in the test / default build (no VITE_FIREBASE_* variables)", () => {
    expect(CLOUD_ENABLED).toBe(false);
    expect(cloudConfig()).toBeNull();
  });
});

describe("accounts on (the four VITE_FIREBASE_* variables set)", () => {
  it("the flag turns on, the config is read, and the Help tab gains the Accounts section", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_FIREBASE_API_KEY", "key");
    vi.stubEnv("VITE_FIREBASE_AUTH_DOMAIN", "p.firebaseapp.com");
    vi.stubEnv("VITE_FIREBASE_PROJECT_ID", "p");
    vi.stubEnv("VITE_FIREBASE_APP_ID", "1:2:web:3");
    try {
      const cfg = await import("./config");
      expect(cfg.CLOUD_ENABLED).toBe(true);
      expect(cfg.cloudConfig()).toEqual({ apiKey: "key", authDomain: "p.firebaseapp.com", projectId: "p", appId: "1:2:web:3" });
      const { HelpPanel } = await import("../../components/HelpPanel");
      const html = renderToString(<HelpPanel classes={[]} schema={null} />);
      expect(html).toContain('id="help-accounts"');
      expect(html).toContain('href="#help-accounts"');
      expect(html).toContain("Delete my account and data");
      vi.stubEnv("VITE_FIREBASE_APP_ID", "");
      vi.resetModules();
      expect((await import("./config")).CLOUD_ENABLED).toBe(false); // one missing value switches it off
    } finally {
      vi.unstubAllEnvs();
      vi.resetModules();
    }
  });
});

describe("accounts off: the app behaves as before and never reaches Firebase", () => {
  it("rendering the whole App with the flag off shows no sign-in control and loads nothing from firebase", async () => {
    const boom = () => {
      throw new Error("a firebase module was imported although accounts are off");
    };
    vi.doMock("firebase/app", boom);
    vi.doMock("firebase/auth", boom);
    vi.doMock("firebase/firestore", boom);
    vi.doMock("firebase/firestore/lite", boom);
    const { default: App } = await import("../../App");
    const html = renderToString(<App />);
    expect(html).toContain("MapleStory Idle DPS");
    expect(html).not.toMatch(/Sign in with Google|acct-/);
    vi.doUnmock("firebase/app");
  });
  it("no source file imports the Firebase SDK statically; only lib/cloud/firebase.ts imports it, dynamically", () => {
    const files = walk(SRC).filter((f) => !isTest(f));
    expect(files.length).toBeGreaterThan(50);
    const dynamic: string[] = [];
    for (const f of files) {
      const text = read(f).replace(/^\s*\/\/.*$/gm, ""); // comments may mention the package
      expect(text, f).not.toMatch(/(?:from|import)\s+["']firebase/);
      if (/import\(\s*["']firebase/.test(text)) dynamic.push(f.replace(SRC.href, ""));
    }
    expect(dynamic).toEqual(["lib/cloud/firebase.ts"]);
  });
  it("the always-loaded files only touch the tiny parts of lib/cloud (config, bridge, merge types); the account UI is reached through a flag-gated lazy import", () => {
    const main = ["main.tsx", "App.tsx", "components/ProfilesPanel.tsx", "components/HelpPanel.tsx", "components/CloudStatusIcon.tsx", "components/ThemeToggle.tsx", "lib/profiles.ts"];
    for (const rel of main) {
      const text = read(new URL(rel, SRC).href);
      const used = [...text.matchAll(/from\s+["'][./]*(?:lib\/)?cloud\/(\w+)["']/g)].map((m) => m[1]);
      for (const u of used) expect(["config", "bridge", "merge"], `${rel} imports cloud/${u}`).toContain(u);
      expect(text, rel).not.toMatch(/from\s+["'][./]*components\/account/);
    }
    const app = read(new URL("App.tsx", SRC).href);
    expect(app).toMatch(/CLOUD_ENABLED \? lazy\(\(\) => import\("\.\/components\/account\/AccountRoot"\)\) : null/);
    for (const t of ["merge", "store", "sync", "auth", "localPorts", "firestoreDb"]) expect(app).not.toContain(`cloud/${t}`);
  });
});
