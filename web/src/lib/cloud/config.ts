// Accounts feature flag.  The four VITE_FIREBASE_* variables (public web-app identifiers, set at BUILD time) switch the whole feature on; when any of them
// is missing the app behaves exactly as before: no sign-in button, no account code, no Firebase code is downloaded.
//
// `CLOUD_ENABLED` reads the variables with literal `import.meta.env.VITE_*` accesses on purpose: Vite replaces them at build time, so with no variables the
// bundler sees a constant `false` and drops the (lazy) account chunk altogether.

export interface FirebaseConfig {
  apiKey: string;
  authDomain: string;
  projectId: string;
  appId: string;
}

/** The config from four (possibly missing / blank) values; null unless all four are present. */
export function parseFirebaseConfig(v: Partial<Record<keyof FirebaseConfig, string | undefined>>): FirebaseConfig | null {
  const apiKey = v.apiKey?.trim();
  const authDomain = v.authDomain?.trim();
  const projectId = v.projectId?.trim();
  const appId = v.appId?.trim();
  return apiKey && authDomain && projectId && appId ? { apiKey, authDomain, projectId, appId } : null;
}

// `!!(a && b && c && d)` (not `Boolean(...)`) so that the minifier folds it to a constant `false` when the variables are unset
export const CLOUD_ENABLED: boolean = !!(
  import.meta.env.VITE_FIREBASE_API_KEY &&
  import.meta.env.VITE_FIREBASE_AUTH_DOMAIN &&
  import.meta.env.VITE_FIREBASE_PROJECT_ID &&
  import.meta.env.VITE_FIREBASE_APP_ID
);

export function cloudConfig(): FirebaseConfig | null {
  if (!CLOUD_ENABLED) return null;
  return parseFirebaseConfig({
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    appId: import.meta.env.VITE_FIREBASE_APP_ID,
  });
}
