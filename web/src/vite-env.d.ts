/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_MOCK?: string;
  // accounts (optional; all four must be set, see lib/cloud/config.ts): the Firebase web config, public identifiers
  readonly VITE_FIREBASE_API_KEY?: string;
  readonly VITE_FIREBASE_AUTH_DOMAIN?: string;
  readonly VITE_FIREBASE_PROJECT_ID?: string;
  readonly VITE_FIREBASE_APP_ID?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
