# Accounts and cloud-saved profiles: design

**Status (2026-11-23): built; needs console setup** (enable Google sign-in, create Firestore, register the web app, set `VITE_FIREBASE_*`, deploy the rules: `deploy/README.md` section 17).  Implementation: `web/src/lib/cloud/`, `web/src/components/account/`, `deploy/firebase/firestore.rules` (+ `rules-test/`); notes on where the build deviates from this sketch are at the end of this file.

Decisions (user, 2026-11-23): **Google sign-in only**; sync **profiles + small settings** (theme, last-used class); build later, one agent at a time.

## Goal
A player signs in once and their saved profiles (stats, artifacts, companions, cube gear, Equipment Compare lines) are there on any browser or device. Signed-out use keeps working exactly as today (localStorage).

## Architecture (no new server)
- **Firebase Authentication** with the **Google** provider. The page already lives on Firebase Hosting in the project `maplestoryidleoptimizer`, so Auth and Firestore are in the same console.
- **Cloud Firestore** (native mode) holds the data. The web page talks to Firestore **directly** (Firebase JS SDK, modular, lazy-loaded) and **security rules** enforce "only the owner can read/write their own documents". The Cloud Run API stays stateless and unchanged: it never sees accounts or saved data (it just computes).
- Why not store data through the API: more code, an auth-verification layer, and Cloud Run cost for no benefit at this scale. Rules + the SDK are the standard pattern for this size.

## Data model
```
users/{uid}                         { createdAt, lastSeenAt, schema: 1 }         (small)
users/{uid}/profiles/{profileId}    { classId, name, updatedAt, deleted?, state: <FormState JSON as exported by lib/profiles.ts> }
users/{uid}/settings/app            { theme, lastClassId, lastProfileId, updatedAt }
```
- `profileId` = the client-generated id the app already uses. One Firestore document per profile (limit 1 MiB per document; a profile is ~10-60 KB).
- `state` is the same JSON the app already exports/imports (`lib/profiles.ts` `exportProfile`), versioned (`schema`), so the cloud and file formats stay one thing.

## Security rules (sketch)
```
rules_version = '2';
service cloud.firestore {
  match /databases/{db}/documents {
    match /users/{uid} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
      match /profiles/{pid} {
        allow read: if request.auth != null && request.auth.uid == uid;
        allow create, update: if request.auth != null && request.auth.uid == uid
          && request.resource.size() < 200 * 1024            // keep documents small
          && request.resource.data.keys().hasOnly(['classId','name','updatedAt','deleted','state'])
          && request.resource.data.name is string && request.resource.data.name.size() <= 80;
        allow delete: if request.auth != null && request.auth.uid == uid;
      }
      match /settings/{doc} {
        allow read, write: if request.auth != null && request.auth.uid == uid && request.resource.size() < 4 * 1024;
      }
    }
  }
}
```
- Profile-count cap (e.g. 50 per account) is enforced client-side and, if wanted, with a counter document in the rules; Firestore rules cannot count a collection directly, so a `users/{uid}.profileCount` guard is the usual trick.
- **App Check** (reCAPTCHA v3) is optional hardening against scripted abuse of the project's Firestore quota; decide at build time.

## Sync behaviour (local-first)
1. The app keeps using localStorage as the working copy (fast, offline, works signed-out).
2. On sign-in: fetch the cloud profiles and settings, then **merge** by `profileId` using `updatedAt` (newer wins). Local-only profiles are uploaded (with a one-time "upload your N local profiles?" confirmation the first time), cloud-only profiles are downloaded.
3. **Explicit save (user decision 2026-11-23, to keep Firestore reads/writes low):** edits are autosaved to the LOCAL working copy only; the cloud is written when the user presses a **Save to account** button (writes only the profiles that changed since the last save, in one batched commit). The header shows an 'unsaved changes' dot and the app warns before closing/leaving the tab with unsaved changes. Optional later: a conservative auto-sync (e.g. 60 s after the last edit, changed profiles only) behind a settings toggle, off by default. Failures queue and retry when back online (the SDK's offline persistence helps). Reads: one read per cloud profile on sign-in/refresh (plus one for settings), no live listeners, plus a manual 'Refresh from account' button.
4. Deletes are soft (`deleted: true`, with `updatedAt`) so another device learns about the deletion, then purged server-side after 30 days by a simple client sweep.
5. Conflicts (same profile edited on two devices): last write wins per profile by `updatedAt`, with the losing version kept in a local "history" slot so nothing is silently lost; a small notice says "updated from another device".
6. Sign-out clears the in-memory account state but leaves the signed-out local profiles untouched (choice offered: keep local copies or clear this browser).

## UI
- Header: "Sign in with Google" button (avatar + menu when signed in: Sync status, Download all my data (JSON), Delete my account and data).
- Profiles panel: a cloud icon per profile showing synced/pending/error; a one-time first-login migration dialog.
- Privacy line: what is stored (game stats you typed, nothing else beyond the Google account's id/email), where, how to delete.

## Privacy and compliance
- Stored: Google account uid, email (Auth), display name/photo URL if the SDK exposes it (not copied into Firestore), plus the profile JSON. No analytics or ad cookies added.
- "Delete my account and data": deletes all `users/{uid}` documents, then the Auth user (needs a recent sign-in: the SDK asks to re-authenticate).
- Show a short consent/privacy note at first sign-in. A real privacy-policy page is advisable if the site is public (user's call).

## Cost and limits (to verify on the Firebase/Firestore pricing pages; figures from memory)
- Firestore free quota: about 1 GiB stored, 50,000 reads and 20,000 writes per day. With ~10 profiles per active user and debounced writes, thousands of daily users stay within it. Firebase Auth's Google provider has no per-user charge on the free tier. Budget alert already exists for the project.

## Build plan (one agent, ~1 day of agent time, light on evaluations: none)
1. `web/src/lib/cloud/` (firebase init lazy-loaded behind the sign-in button so signed-out users do not download the SDK), `auth.ts`, `sync.ts` (merge, debounce, retry), `schema` migration helpers; env config via `VITE_FIREBASE_*` (public web config, not secrets).
2. UI: account menu, sync status, first-login migration dialog, delete-account flow.
3. `deploy/firebase/firestore.rules` + `firestore.indexes.json` + `firebase.json` updated; `deploy/deploy_web.sh` also deploys the rules (`firebase deploy --only hosting,firestore:rules`).
4. Tests: pure sync/merge logic with vitest (conflicts, soft deletes, offline queue), rules tests with the **Firebase emulator** (`@firebase/rules-unit-testing`: owner can read/write; others cannot; size/shape limits), UI render smoke tests. All offline; no live Google calls needed for CI.
5. Docs: `APP.md`, `web/README.md`, Help tab section 'Accounts', `deploy/README.md` console checklist.

## What YOU need to click once (Firebase console, https://console.firebase.google.com/project/maplestoryidleoptimizer)
1. **Build -> Authentication -> Get started -> Sign-in method -> Google -> Enable** (choose a support email).
2. **Authentication -> Settings -> Authorized domains**: confirm `maplestoryidleoptimizer.web.app` and `maplestoryidleoptimizer.firebaseapp.com` are listed (they are by default); add `localhost` for local development.
3. **Build -> Firestore Database -> Create database -> Production mode**, location **nearest to your players** (cannot be changed later; `nam5`/`us-central` is the safe default, or `eur3`/`europe-west`; pick `me-west1` only if players are mainly in Israel and you accept the pricing tier).
4. **Project settings -> Your apps -> Add app (Web)** to get the web config (apiKey, authDomain, projectId, appId); the agent puts it in `web/.env` as `VITE_FIREBASE_*` (these values are public identifiers, not secrets).
5. (Optional) enable **App Check** for the web app.

## Risks / open points
- Free-tier numbers unverified; the budget alert is the safety net.
- Firestore location is permanent: decide before step 3.
- Profile JSON may contain a user's real numbers: private by rules, but anyone with account access sees them; no sharing feature is planned (a 'share a profile link' feature is a separate design).
- Account deletion and data export are required behaviours before inviting the public.

## Implementation notes (deviations from the sketch above)
- `state` is stored as a canonical JSON **string**, not a map (Firestore rejects nested arrays / `undefined` and indexes every map field; a string cannot break when the profile format changes).  The `schema` version lives in `users/{uid}.schema`.
- The size guard is `state.size() <= 180000` characters (+ name <= 80, classId <= 64, ids <= 64): `request.resource.size()` of the sketch does not exist in the rules language.  Tombstones carry an empty `state`.
- The 50-profile cap is client-side only (documented in `firestore.rules`); there is no `profileCount` counter.
- `firebase/firestore/lite` is used (no listeners, no offline cache, ~5x smaller), so there is no SDK offline persistence; the dirty state is persisted by the app and a failed Save is retried.
- Save is last-write-wins at document level with no pre-read (it reads nothing); conflicts are detected and resolved by Refresh / sign-in (history kept).
- Settings `lastProfileId` is stored but only `theme` and `lastClassId` are applied on sign-in.
