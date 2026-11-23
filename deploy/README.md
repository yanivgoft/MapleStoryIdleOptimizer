# Deploying the web app

Target layout (decided in the plan, `APP.md`): a **stateless Python API on Google Cloud Run** (`api/`, scale to zero, hard instance cap) and a
**static front end** (`web/`, built once with the API's URL baked in) on a free static host.  No database, no accounts, nothing to back up.

```
browser --HTTPS--> static host (web/dist)            e.g. https://<user>.github.io/<repo>/
   |
   +--HTTPS (fetch, CORS)--> Cloud Run service msi-api   e.g. https://msi-api-xxxx-uc.a.run.app   (container built from api/Dockerfile)
```

Everything here was written without access to Google, Docker or the network (see section 16 for exactly what was and was not tested).
**Every price, quota and limit below that I quote from memory is marked "(to be verified)"**: check the official pages in section 3 before
relying on any of them.

Files in this directory:

| file | purpose |
|---|---|
| `deploy_api.sh` | stage a minimal build context, build with Cloud Build, deploy to Cloud Run with the safe flags, print the URL |
| `deploy_web.sh` | build the front end with `VITE_API_URL`, publish to Cloudflare / Firebase (or build for GitHub Pages) |
| `smoke_test.sh` | curl-based check of a running API (health, every class the API lists, errors, CORS) - exit code 1 on any failure |
| `.env.example` | every setting of the three scripts (copy to `deploy/.env`, git-ignored) |
| `firebase/firebase.json` | Firebase Hosting + Firestore rules config (only used if you pick Firebase); `firebase/firestore.rules`, `firebase/firestore.indexes.json` (empty) belong to the optional accounts feature, section 17 |
| `firebase/rules-test/` | emulator tests + an offline lint of `firestore.rules` (`npm run test:emulator`, needs Java; section 17) |
| `../.github/workflows/deploy.yml` | manual (`workflow_dispatch`) deploy from GitHub Actions, section 12 |

---------------------------------------------------------------------------------------------------------------------------------------

> **Shortcut (this project):** `deploy/redeploy.sh` does the whole redeploy in one command and verifies every step: preflight (tools, gcloud + Firebase logins, git state), the local regression run, the API deploy + Cloud Run revision check, the API smoke test (all classes, CORS), the web build + Firebase Hosting + Firestore rules, and live-site checks (the page serves the new build, its bundle points at the API, the API lists as many classes as this checkout). It stops at the first failing step. Options: `--yes`, `--skip-tests`, `--api-only`, `--web-only`, `--no-rules`, `--dry-run` (stages and builds, sends nothing). The numbered sections below describe each step it runs.

## 1. What you need on your machine

* Google Cloud CLI (`gcloud`): <https://cloud.google.com/sdk/docs/install>, then `gcloud auth login`.
* Node.js 20+ (CI uses 22) and npm, for building `web/`.
* `curl` and `python3` (the smoke test).
* Optional: Docker, only to rehearse the image locally (`docker build -f api/Dockerfile -t msi-api .`); the deploy itself builds in Google's Cloud Build,
  so you do not need Docker installed to deploy.

## 2. Create the Google Cloud project and enable billing

A card is required to enable billing even if you never leave the free tier.

1. Console -> project picker -> **New project**.  Pick a **project ID** (globally unique, e.g. `msi-dps-yaniv`; it cannot be changed later).
   CLI alternative: `gcloud projects create msi-dps-yaniv`.
2. Console -> **Billing** -> create / link a billing account to the project (card, address).  CLI: `gcloud billing projects link msi-dps-yaniv --billing-account=XXXXXX-XXXXXX-XXXXXX`
   (`gcloud billing accounts list` shows the id).
3. `gcloud config set project msi-dps-yaniv`.
4. Do section 3 (budget + alert) **before** you deploy anything.

## 3. Budget alert and the free-tier numbers you must verify

### Budget (do this first)

Console -> Billing -> **Budgets & alerts** -> Create budget: scope = this project, amount **$5** (or $1), alert thresholds 20 % / 50 % / 100 % (actual) and
100 % (forecast), e-mail to you.  CLI (needs the Billing Budgets API and billing-admin rights):

```bash
gcloud billing budgets create --billing-account=XXXXXX-XXXXXX-XXXXXX --display-name="msi-dps" --budget-amount=5USD \
  --filter-projects=projects/msi-dps-yaniv --threshold-rule=percent=0.2 --threshold-rule=percent=0.5 --threshold-rule=percent=1.0
```

A budget **only e-mails you; it does not stop spending**.  The real brakes are `--max-instances`, the rate limiter, and scale-to-zero (section 10).  A hard stop
(a Pub/Sub budget notification that detaches billing) exists but also takes the whole project down; see Google's "Disable billing with budget notifications" guide
if you want it - not recommended for a hobby tool.

### Free-tier numbers: where to verify what

| thing | official page | look for | my recollection (to be verified) |
|---|---|---|---|
| Cloud Run | <https://cloud.google.com/run/pricing> (section "Free tier") | requests / month, vCPU-seconds / month, GiB-seconds / month, outbound data, which regions / billing model (request-based vs instance-based) it applies to | ~2 million requests, ~180,000 vCPU-seconds, ~360,000 GiB-seconds, ~1 GiB egress from North America (to be verified) |
| Cloud Run regions | <https://cloud.google.com/run/docs/locations> and the pricing page's tier table | Tier 1 vs Tier 2 regions; whether the free tier is limited to certain regions | us-central1, us-east1, us-west1 are the regions I remember as free-tier eligible (to be verified) |
| Cloud Build | <https://cloud.google.com/build/pricing> | free build minutes / month, default machine type | ~2,500 build-minutes / month on the default machine (to be verified; older docs said 120 min/day) |
| Artifact Registry | <https://cloud.google.com/artifact-registry/pricing> | free storage per month, price per GB after | ~0.5 GB free; a handful of ~150 MB images fits (to be verified) |
| Cloud Logging / Monitoring | <https://cloud.google.com/stackdriver/pricing> | free log ingestion per project per month; default retention; uptime-check quota | ~50 GiB / project / month free, 30 days default retention (to be verified) |
| Network egress (beyond free) | <https://cloud.google.com/vpc/network-pricing> and the Cloud Run pricing page | $ per GiB after the free amount | ~$0.12 / GiB, North America to internet, standard tier (to be verified) |
| Firebase Hosting | <https://firebase.google.com/pricing> (Spark plan) | stored GB, transfer per month / day, whether a card is needed | 10 GB storage, ~360 MB / day transfer, no card on Spark (to be verified) |
| Cloudflare Pages | <https://developers.cloudflare.com/pages/platform/limits/> and <https://www.cloudflare.com/plans/> | requests / bandwidth caps, builds per month, files per site | static requests and bandwidth unlimited on free, ~500 builds / month (to be verified) |
| GitHub Pages | <https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits> | site size, bandwidth soft limit; whether Pages works for **private** repos on a free account | 1 GB site, ~100 GB / month soft bandwidth, public repos only on the free plan (to be verified) |

## 4. Enable the APIs

```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com --project msi-dps-yaniv
```

(or set `ENABLE_APIS=1` for `deploy_api.sh`).  The first source deploy also asks to create an Artifact Registry repository named `cloud-run-source-deploy`
in the region and a storage bucket for the uploaded source; the script passes `--quiet`, which accepts those defaults.

## 5. Deploy the API

```bash
cp deploy/.env.example deploy/.env      # edit PROJECT_ID, REGION, CORS_ORIGINS
deploy/deploy_api.sh                    # DRY_RUN=1 deploy/deploy_api.sh  first, to see the staged files and the exact gcloud command
```

What the script does:

1. Copies exactly what `api/Dockerfile` needs (`api/*.py`, `api/requirements.txt`, `engine/`, the three `src/` modules the engine imports,
   `data/factor_table.json`, plus `data/cube_potential_data.json` if present) into a temp directory with the Dockerfile at its root.  Reason: `gcloud run deploy --source`
   uploads a directory and looks for `Dockerfile` **at its root** (ours is in `api/` and expects the repo layout), and it ignores `api/Dockerfile.dockerignore`
   (it reads `.gcloudignore`), so pointing it at the repo root would upload `.venv/`, `web/node_modules/`, the workbooks - hundreds of MB.
2. Fails if a file the Dockerfile COPYs is missing from the stage, if an `api/*.py` module is not in the Dockerfile's COPY list, or if `engine/cubes.py` exists but
   the Dockerfile does not copy the cube data (see "Dockerfile check" in section 16).
3. Writes the service environment to a temp YAML file (`--env-vars-file`; commas in `MSI_CORS_ORIGINS` would break `--set-env-vars`, which uses commas as separators unless you
   switch delimiters with `^@^`).  Any other `MSI_*` variable exported in your shell / `deploy/.env` is passed through.
4. Runs `gcloud run deploy`, then prints the URL (`API_URL=...`).

The equivalent by hand (stage the directory yourself, or build the image with Docker and use `--image`):

```bash
gcloud run deploy msi-api --source <stage-dir> --project msi-dps-yaniv --region us-central1 --platform managed --allow-unauthenticated \
  --max-instances 2 --min-instances 0 --concurrency 10 --cpu 1 --memory 512Mi --timeout 60 \
  --env-vars-file env.yaml     # env.yaml: MSI_CORS_ORIGINS: "https://me.github.io" / MSI_PROXY_HOPS: "1"
# image route (needs Docker + `gcloud auth configure-docker us-central1-docker.pkg.dev`):
#   docker build -f api/Dockerfile -t us-central1-docker.pkg.dev/PROJECT/msi/msi-api:1 .  &&  docker push ...  &&  gcloud run deploy msi-api --image ...
```

### The flags, and why

| flag | value | why |
|---|---|---|
| `--max-instances` | **2** | the spending cap: at most two containers ever run, whatever the traffic.  Excess requests queue briefly, then get 429 / 503 from Cloud Run |
| `--min-instances` | 0 | scale to zero: nothing is billed while nobody uses it.  Anything above 0 is billed around the clock |
| `--concurrency` | 10 (8-16 is fine) | requests handled in parallel per container.  The engine is CPU-bound on one vCPU, so a very high value only adds latency; the sensitivity endpoint also uses a small thread pool (`MSI_SENS_WORKERS`, default 2) |
| `--cpu` | 1 | one worker process (`api/Dockerfile` runs a single uvicorn worker) cannot use more |
| `--memory` | 512Mi | measured locally: the API process peaks around 60-65 MB RSS after importing the app and computing once for every class, and a sensitivity result is ~35 KB (cache: 128 entries by default).  512 MiB is far more than needed but is what I recall as the minimum Cloud Run accepts for a 1 vCPU instance (to be verified); do not raise it |
| `--timeout` | 60 | seconds per request; the API itself answers 504 after `MSI_SENS_TIMEOUT_S` (30) for a stuck sensitivity call |
| `--allow-unauthenticated` | | the browser calls the API directly.  An org policy ("domain restricted sharing") can block this on Workspace organisations; personal accounts are unaffected |
| (billing model) | request-based (the default) | CPU is only billed while a request is being handled.  Do **not** pass `--no-cpu-throttling` / instance-based billing |
| `MSI_CORS_ORIGINS` | your front end's origin(s) | the browser refuses responses from an origin that is not listed; see section 8 |
| `MSI_PROXY_HOPS` | 1 | section 6 |
| `MSI_RATE_LIMIT_PER_MINUTE` | 120 (API default) | per client IP, in memory, **per instance** (two instances = up to 2x) |

### Cold starts

With `--min-instances 0` the first request after ~15 idle minutes (the idle window is Google's choice, to be verified) starts a container: pulling the image, starting
Python, importing the engine.  Importing `api.main` takes ~0.3-0.5 s on a laptop, so I expect **roughly 1-3 s** for the first request on a 1 vCPU instance (an estimate;
measure it with `time curl -s $URL/api/health` after the service has been idle).  The front end sees a slow first compute and then normal ~20-100 ms answers.  If that
bothers you: `--cpu-boost` (more CPU during startup) is free of extra instance charges as far as I remember but check the pricing page, and `--min-instances 1` removes cold
starts for a standing charge (never "free").

## 6. `MSI_PROXY_HOPS` and the per-IP rate limiter (verify this)

The limiter and the access log key on the client IP.  Behind Cloud Run the socket peer is always a Google front end, so with `MSI_PROXY_HOPS=0` **every user shares one bucket**
(120 requests/minute for the whole world, per instance).  With `MSI_PROXY_HOPS=N` the API takes the N-th entry from the **right** of `X-Forwarded-For` (`api/middleware.py`
`client_ip`).

What I recall (to be verified): Cloud Run's front end appends the address of the connecting client to `X-Forwarded-For`, so the **rightmost** entry is trustworthy and
anything the client typed is to its left.  That means `MSI_PROXY_HOPS=1` when users reach the `*.run.app` URL directly.  If you later put a Google external load balancer or
a CDN in front, the count changes (+1 per trusted proxy that appends its own entry).

Rules: **never set the number higher than the real number of proxies** (a too-large value reads a client-supplied entry and the limit can be bypassed by spoofing); a value that is
too small or that makes `len(parts) < hops` degrades to "everyone shares the Google address", which is safe but too strict.

How to verify after the first deploy:

```bash
URL=$(gcloud run services describe msi-api --region us-central1 --format 'value(status.url)')
MYIP=$(curl -s https://api.ipify.org); echo "my IP: $MYIP"
curl -s -o /dev/null -H 'X-Forwarded-For: 9.9.9.9' "$URL/api/classes"          # a spoofed entry on the left
gcloud run services logs read msi-api --region us-central1 --limit 5            # the API's JSON line has "ip": ...
gcloud logging read 'logName:"run.googleapis.com%2Frequests"' --limit 1 --format 'value(httpRequest.remoteIp)'   # what Google saw
```

* `"ip"` in the API log equals `$MYIP`: **correct**, keep 1.
* `"ip"` is `9.9.9.9`: the platform did not append anything; the header is client-controlled.  Set `PROXY_HOPS=0`.
* `"ip"` is a Google / internal address: the entry count is not what was assumed; keep `0` until you understand the header (log it from a scratch deploy) and accept the shared bucket.

Change it later without rebuilding: `gcloud run services update msi-api --region us-central1 --update-env-vars MSI_PROXY_HOPS=0`.

## 7. Build and host the front end

`VITE_API_URL` is read **at build time** (`web/src/api.ts`); the bundle is plain static files.

```bash
VITE_API_URL=https://msi-api-xxxx-uc.a.run.app npm --prefix web run build      # -> web/dist
# or: API_URL=... STATIC_HOST=... deploy/deploy_web.sh   (also checks the URL really ended up in the bundle)
```

All three hosts below were evaluated from memory only (limits to be verified, section 3).  **None of the three needs a payment card** in my recollection (Firebase Hosting on
the Spark plan, Cloudflare Pages free, GitHub Pages free for public repos), so the "no card" criterion does not separate them.

**Recommendation: GitHub Pages** if the repository is (or may be) public: no extra account, deployed by the workflow in this repo, origin known in advance (`https://<user>.github.io`),
so the CORS value can be set before the API exists.  **Cloudflare Pages** if the repo is private (GitHub Pages needs a paid plan for private repos, to be verified) - generous
limits, direct upload with `wrangler`.  Firebase Hosting is fine but adds a second Google product and a service-account secret for CI.

### A. GitHub Pages (default in `deploy.yml`)

1. Repo -> Settings -> Pages -> Source: **GitHub Actions**.
2. A project site is served under `/<repo>/`, so the bundle must be built with that base (`npm run build -- --base=/<repo>/`; the workflow and `deploy_web.sh` do it,
   `WEB_BASE`).  A custom domain or a `<user>.github.io` repository uses base `/`.
3. Run Actions -> **Deploy** -> Run workflow (`web_target = github-pages`).  Origin for CORS: `https://<user>.github.io` (no path, lower case).

### B. Cloudflare Pages

```bash
STATIC_HOST=cloudflare CF_PAGES_PROJECT=msi-dps API_URL=https://... deploy/deploy_web.sh     # first: npx wrangler login
```

The first `wrangler pages deploy` creates the project.  Origin: `https://msi-dps.pages.dev`.  Or drag `web/dist` into Workers & Pages -> Create -> Pages -> Upload assets.

### C. Firebase Hosting

```bash
STATIC_HOST=firebase FIREBASE_PROJECT=my-firebase-project API_URL=https://... deploy/deploy_web.sh     # first: npx firebase-tools login
```

Needs a Firebase project (you can add Firebase to your existing Google Cloud project: console.firebase.google.com -> Add project -> pick it; the Spark plan is the
no-charge one - verify that Hosting alone does not require Blaze).  The script copies `web/dist` into `deploy/firebase/public` and runs `firebase deploy --only hosting,firestore:rules`
with `deploy/firebase/firebase.json` (the rules belong to the optional accounts feature, section 17; set `FIREBASE_DEPLOY_RULES=0` to deploy hosting only, e.g. before the Firestore database exists).  Origins: `https://<project>.web.app` and `https://<project>.firebaseapp.com`.

### Custom domain (optional)

All three hosts support one (GitHub: Settings -> Pages -> Custom domain, with base `/`; Cloudflare: Pages project -> Custom domains; Firebase: Hosting -> Add custom domain).
Add the new origin to `MSI_CORS_ORIGINS` (keep the old one while you migrate).  For the API itself, a custom domain on Cloud Run (domain mappings or a load balancer) is optional
and not needed; a load balancer adds a standing monthly charge - skip it.

## 8. CORS wiring, both ways

* **Browser -> API:** the API only answers browsers from origins in `MSI_CORS_ORIGINS` (exact match: scheme + host + port, no path, no trailing slash).  List every front-end origin,
  comma separated.  Update without rebuilding:
  `gcloud run services update msi-api --region us-central1 --update-env-vars ^@^MSI_CORS_ORIGINS=https://a.github.io,https://b.pages.dev`
  (the `^@^` prefix changes gcloud's separator so the commas inside the value survive).  `deploy_api.sh` handles this for you via the env file.
* **Front end -> API:** `VITE_API_URL` is baked into the bundle, so a changed API URL needs a front-end rebuild.  The `*.run.app` URL is stable for the life of the service
  (redeploys keep it), so this only happens if you delete / rename the service or move region.
* Order of the first deploy: GitHub Pages' origin is known in advance, so deploy the API with `CORS_ORIGINS=https://<user>.github.io`, then build the front end with the printed URL.
  For Cloudflare / Firebase use the project name you will create (`https://<name>.pages.dev` / `.web.app`) or fix the variable afterwards with the command above.
* Test: `SMOKE_ORIGIN=https://<user>.github.io deploy/smoke_test.sh <api-url>` checks the preflight for that origin (allowed) and for a foreign origin (refused).

## 9. Smoke test

```bash
deploy/smoke_test.sh https://msi-api-xxxx-uc.a.run.app          # SMOKE_ORIGIN=... adds the CORS checks; EXPECT_CLASSES=<n> pins the class count (default: every class listed, at least 12)
```

~35 requests (health, class list, per class `defaults` -> `compute` and `sensitivity` where modelled, the `{}` minimal body, a 422, a 404).  Exit code 0 only if everything passed.
It retries the first requests, so a cold start does not fail it.  Also usable locally: `API_URL=http://localhost:8000 deploy/smoke_test.sh`.

## 10. Cost-control checklist

- [ ] Budget with alerts at $1 / $5 exists (section 3) and the e-mail address is one you read.
- [ ] `--max-instances 2` (check: `gcloud run services describe msi-api --region us-central1 --format 'value(spec.template.metadata.annotations)'` shows `autoscaling.knative.dev/maxScale: '2'`).
- [ ] `--min-instances 0`; request-based billing (no `--no-cpu-throttling`).
- [ ] Rate limits on: `MSI_RATE_LIMIT_PER_MINUTE` (120) and the stricter sensitivity limit (`MSI_RATE_LIMIT_SENS_PER_MIN`, default 20, per IP) - and `MSI_PROXY_HOPS` verified (section 6), otherwise all users share one bucket.
- [ ] Request body cap `MSI_MAX_BODY_BYTES` (64 KiB), sensitivity timeout `MSI_SENS_TIMEOUT_S` (30) and result cache are API defaults.
- [ ] **No persistent storage**: no database, bucket, volume, Redis or secret in this project (nothing to be billed for at rest).  Check Console -> Billing -> Reports grouped by SKU after a week.
- [ ] Artifact Registry: each source deploy adds an image (~100-200 MB, estimate).  Keep few: add a cleanup policy
      (`gcloud artifacts repositories set-cleanup-policies cloud-run-source-deploy --location us-central1 --policy=policy.json`, keep-most-recent-N; see the Artifact Registry
      docs) or delete old digests by hand every few deploys.  The 0.5 GB free allowance (to be verified) fits only a few images.
- [ ] Logs: the API writes one JSON line per request to stdout (Cloud Logging).  Lower retention of the default bucket if you care:
      `gcloud logging buckets update _Default --location global --retention-days 7` (default is 30 days, to be verified).  Free ingestion allowance: section 3.
- [ ] No load balancer, no Cloud NAT, no VPC connector, no custom-domain load balancer (each has a standing monthly charge).
- [ ] Do not let an uptime checker hit `/api/classes/*/sensitivity`; `/api/health` is exempt from the rate limit and cheap.
- [ ] Once a month: Billing -> Reports; Cloud Run -> the service's Metrics (instance count, request count, billable instance time).

## 11. Monitoring

* **Logs (CLI):** `gcloud run services logs read msi-api --region us-central1 --limit 50` (add `--format json` for the structured form), or `gcloud logging read` with a filter such as
  `resource.type="cloud_run_revision" AND resource.labels.service_name="msi-api" AND jsonPayload.status>=500`.
* **Logs (console):** Cloud Run -> service -> Logs; Logs Explorer.  The API's own lines are JSON with `event` (`request`, `startup`, `compute_failed`, `sensitivity_timeout`, ...),
  `id` (also returned as the `x-request-id` header), `method`, `path`, `status`, `ms`, `ip` - Cloud Logging shows them as `jsonPayload.*`.  Useful filters:
  `jsonPayload.event="request" AND jsonPayload.status=429` (rate limiting working or too strict), `jsonPayload.ms>1000`, `jsonPayload.event="compute_failed"`.
  Cloud Run additionally writes its own request log (`httpRequest.*`, latency, remote IP) - the two correlate by time.
* **Uptime:** `GET /api/health` returns `{"status":"ok","version":...,"classes":<n>}` and is exempt from the rate limiter.  Create an uptime check (Monitoring -> Uptime checks, HTTPS,
  path `/api/health`, period **5 minutes or longer**, one or a few regions; verify the free quota) or use any external free pinger.  Note that a frequent checker keeps an instance alive
  (little cost under request-based billing, but it defeats scale-to-zero's cold starts - which may be what you want).
* **Alerts:** Monitoring -> Alerting -> policy on "Cloud Run request count" or "5xx ratio" and on the uptime check, e-mail channel.
* **Metrics worth a glance:** instance count (should be 0-2), request latencies, container memory utilisation (expect well under 50 %), billable instance time.

## 12. Deploying from GitHub Actions (`.github/workflows/deploy.yml`)

The workflow is `workflow_dispatch` only (inputs: environment, region, deploy_api, web_target); it **never runs on push**.  A `release: published` trigger exists but does nothing unless the
repository variable `DEPLOY_ON_RELEASE` is `true`.  Jobs: `test-python` + `test-web` (same steps as `app-tests.yml`; nothing deploys if red) -> `deploy-api` (keyless auth to Google,
`deploy/deploy_api.sh`, smoke test) -> `build-web` (builds against the deployed URL) -> `publish-pages` **or** `publish-firebase`.  Action versions are pinned to major tags (`@v4`, `@v2`, ...);
pin to commit SHAs if you want supply-chain hardening.

### One-time Google Cloud setup: Workload Identity Federation (no key file ever leaves Google)

Do the first deploy by hand (section 5) so the Artifact Registry repo and the source bucket exist; the CI identity then needs fewer rights.  Then, once:

```bash
export PROJECT_ID=msi-dps-yaniv GH_REPO=OWNER/REPO          # GH_REPO exactly as on GitHub, case sensitive
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud services enable iamcredentials.googleapis.com sts.googleapis.com cloudresourcemanager.googleapis.com --project $PROJECT_ID

gcloud iam service-accounts create gh-deployer --project $PROJECT_ID --display-name "GitHub Actions deployer"
SA=gh-deployer@$PROJECT_ID.iam.gserviceaccount.com
for role in roles/run.admin roles/cloudbuild.builds.editor roles/artifactregistry.writer roles/storage.admin roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding $PROJECT_ID --member "serviceAccount:$SA" --role $role --condition=None
done
# the deployer must be allowed to run the service as its runtime identity (the default Compute Engine service account):
gcloud iam service-accounts add-iam-policy-binding $PROJECT_NUMBER-compute@developer.gserviceaccount.com --project $PROJECT_ID \
  --member "serviceAccount:$SA" --role roles/iam.serviceAccountUser

gcloud iam workload-identity-pools create github --project $PROJECT_ID --location global --display-name "GitHub Actions"
gcloud iam workload-identity-pools providers create-oidc github-repo --project $PROJECT_ID --location global --workload-identity-pool github \
  --issuer-uri https://token.actions.githubusercontent.com \
  --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition "assertion.repository=='$GH_REPO'"
gcloud iam service-accounts add-iam-policy-binding $SA --project $PROJECT_ID --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/$GH_REPO"
gcloud iam workload-identity-pools providers describe github-repo --project $PROJECT_ID --location global --workload-identity-pool github --format 'value(name)'   # -> GCP_WORKLOAD_IDENTITY_PROVIDER
```

The `--attribute-condition` restricts the provider to **this repository only**.  The role list above is broad (`storage.admin`) because source deploys touch a bucket and Cloud Build; it is a
starting point I could not test: if the first run fails, the error names the missing permission - add that, then tighten.  Cloud Build may also need its own service account to have
`roles/cloudbuild.builds.builder` (newer projects build as the Compute Engine service account; to be verified).

### GitHub variables and secrets

Settings -> Secrets and variables -> Actions -> Variables (optionally per Environment `production` / `staging`; the Environment's value wins):

| variable | required | value |
|---|---|---|
| `GCP_PROJECT_ID` | yes (API) | `msi-dps-yaniv` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | yes (API) | `projects/<number>/locations/global/workloadIdentityPools/github/providers/github-repo` (printed by the last command above) |
| `GCP_SERVICE_ACCOUNT` | yes (API) | `gh-deployer@<project>.iam.gserviceaccount.com` |
| `CLOUD_RUN_SERVICE` | no | default `msi-api` |
| `CORS_ORIGINS` | no | default `https://<owner>.github.io`; comma list for several / other hosts |
| `MSI_PROXY_HOPS` | no | default `1` (verify, section 6) |
| `GCP_REGION` | no | default region for release-triggered runs (manual runs use the `region` input) |
| `API_URL` | only with `deploy_api=false` | URL of an existing API to build the front end against |
| `WEB_BASE` | no | GitHub Pages base path, default `/<repo-name>/`; `/` for a custom domain |
| `WEB_TARGET` | no | `github-pages` (default) or `firebase` for release-triggered runs |
| `FIREBASE_PROJECT` | only for Firebase | Firebase project id |
| `DEPLOY_ON_RELEASE` | no | `true` to also deploy when a release is published |

Secrets: **only** `FIREBASE_SERVICE_ACCOUNT` (JSON key of a service account with "Firebase Hosting Admin"; only if `web_target=firebase`).  The Google Cloud side needs no secret.
Also: Settings -> Pages -> Source: GitHub Actions (for the Pages target).  Optionally add required reviewers to the `production` Environment so a deploy needs an approval click.

## 13. Rollback

Every deploy creates an immutable revision; traffic can be moved back in seconds, without rebuilding:

```bash
gcloud run revisions list --service msi-api --region us-central1                      # newest first
gcloud run services update-traffic msi-api --region us-central1 --to-revisions msi-api-00007-abc=100    # back to a known-good revision
gcloud run services update-traffic msi-api --region us-central1 --to-latest            # return to "always the newest" afterwards
```

Roll out cautiously: `gcloud run deploy ... --no-traffic --tag canary` (adds a flag to `deploy_api.sh`'s command if you want it) gives a `https://canary---msi-api-....run.app` URL to smoke-test before
`update-traffic --to-tags canary=100`.  Front end: GitHub Pages / Cloudflare / Firebase keep earlier deployments (re-run the workflow on an older commit, or `firebase hosting:rollback`).
A config-only fix (CORS, proxy hops) is `gcloud run services update ... --update-env-vars` and creates a new revision as well.

## 14. Security note

* **Accounts are optional and live OUTSIDE the API** (section 17): with the `VITE_FIREBASE_*` variables set, Firebase Authentication (Google) + Firestore store each signed-in player's profiles and two settings, protected by `firestore.rules`
  (owner-only, shape- and size-limited).  The Cloud Run API never sees accounts or saved data.  Without those variables everything below applies unchanged.
* **Stateless API, no user data stored by it**: no database, no sessions, no cookies, no accounts in the API.  Inputs are game stats (levels, percentages) that live only in the request; profiles are in the
  visitor's own `localStorage`.  Logs contain method, path, status, timing and the **client IP address** (personal data in some jurisdictions; hence the short retention advice).
* **Protections that exist** (`api/`): request body cap, strict schema validation (unknown keys / out-of-range values -> 422), per-IP rate limit (stricter on sensitivity), sensitivity timeout
  and result cache, CORS allow-list, no stack traces in responses, container runs as a non-root user, image holds no secrets.
* **NOT protected**: the API is public and unauthenticated by design - anyone can call it directly (CORS only constrains browsers) and read the docs at `/api/docs`; the rate limiter is in memory
  per instance and keyed on an IP that a determined user can rotate, so it limits accidents, not attackers; there is no DDoS protection beyond Google's front end and `--max-instances`
  (a flood is capped in *cost* and answered with errors, not absorbed); no WAF; no bot protection; Dependabot / dependency updates for `fastapi`, `uvicorn` and the base image are not automated
  (`api/requirements.txt` pins ranges, the image is `python:3.12-slim` unpinned by digest); Pages / Firebase / Cloudflare serve plain static files.
* GitHub Actions auth is keyless and limited to this repository (`--attribute-condition`); keep the `production` Environment protected if others can run workflows.

## 15. What the free tier will NOT cover - and how to estimate it

All numbers are **estimates** from the measurements below plus remembered quotas (to be verified); plug your own in.

Measured / given: compute ~3-25 ms per class on a laptop (the World Boss case ~20 ms), a full sensitivity ~0.5 s for the heaviest case (FP-Mage measured only 0.04 s warm here), response sizes **uncompressed**:
compute 3-5 KB, `schema` 15-21 KB, `defaults` 0.7 KB, sensitivity ~35 KB (the API does not gzip, and Cloud Run does not compress for you).

Per request on Cloud Run with request-based billing (worst case = concurrency 1; overlapping requests share billed time, so real numbers are better):

```
billed_s        = max(0.1, wall_seconds)               # billed in 100 ms steps
vCPU_s          = CPU * billed_s                       # CPU = 1
GiB_s           = MEM_GiB * billed_s                   # MEM_GiB = 0.5

free requests per month  =  min(  REQ_FREE,                         # ~2,000,000          (to be verified)
                                  VCPU_FREE / vCPU_s,               # ~180,000 vCPU-s     (to be verified)
                                  GIB_S_FREE / GiB_s,               # ~360,000 GiB-s      (to be verified)
                                  EGRESS_FREE_BYTES / response_bytes )  # ~1 GiB = 1,073,741,824 B (to be verified)
```

Worked examples with those quotas:

| request type | billed_s | by CPU | by memory | by requests | by egress | **binding limit** |
|---|---|---|---|---|---|---|
| compute (20 ms, 5.3 KB) | 0.1 | 1.8 M | 7.2 M | 2.0 M | 0.20 M | **egress, ~200,000 / month** |
| compute, gzip-compressed (~1.2 KB, if the API adds `GZipMiddleware`) | 0.1 | 1.8 M | 7.2 M | 2.0 M | ~0.9 M | egress ~900,000 / month |
| sensitivity (0.5 s, 35 KB, uncached) | 0.5 | 0.36 M | 1.44 M | 2.0 M | 0.03 M | **egress, ~30,000 / month** (CPU would allow 360,000) |
| schema (21 KB, ~5 ms) | 0.1 | 1.8 M | 7.2 M | 2.0 M | 0.05 M | egress, ~50,000 / month |

Note the likely binding constraint is **outbound data, not CPU**.  A "session" like *open class -> 1 schema + 3 defaults + 50 computes + 2 sensitivity* is about 21 + 2 + 267 + 70 = **~360 KB**, i.e.
`sessions/month ~ EGRESS_FREE_BYTES / 360 KB ~ 3,000` before any egress is billed (to be verified; if Google's egress allowance differs, scale linearly).  Beyond the allowance Cloud Run bills egress per GiB, **not a cliff**:
cost ~ `(sessions * 0.36 MB - 1 GiB) * $0.12 / GiB`, e.g. 30,000 sessions ~ 10.5 GiB ~ $1.1 (rate to be verified).  Money for CPU / requests beyond the free tier (illustrative rates from memory, to be verified:
~$0.000024 / vCPU-s, ~$0.0000025 / GiB-s, ~$0.40 / million requests): 5 M computes of 0.1 s billed = 500,000 vCPU-s - 180,000 free = 320,000 x 0.000024 ~ $7.7, plus ~3 M requests over the free 2 M ~ $1.2, plus ~25 GiB egress ~ $3, i.e. roughly **$12 / month** for 5 M computes.

Other things outside the free tier or capacity:

* Cold starts: each scale-from-zero bills its startup (~1-3 s of 1 vCPU, estimate); 1,000 cold starts a month ~ 3,000 vCPU-s, negligible.
* `--max-instances 2` x one CPU-bound vCPU gives roughly 2 x (1 / 0.02 s) = ~100 computes/s of peak capacity, but only ~4 sensitivity calls/s; beyond that requests queue and then fail (a cap on cost, not on correctness).
* The per-IP limit (120/min, 20/min sensitivity) bounds one user at 2 requests/s.
* Artifact Registry storage (images accumulate), Cloud Logging above the free ingestion allowance (a JSON line is ~200 B; 1 M requests ~ 200 MB, nowhere near 50 GiB), a custom-domain load balancer, and `--min-instances` > 0 are
  billed regardless of traffic.
* Free-tier eligibility is per **billing account**; other Cloud Run services you may have share it.

Cheap fixes if egress binds: have the API gzip responses (a one-line `GZipMiddleware(minimum_size=1000)` - api/ is owned by someone else, so this is only a suggestion), serve the (static) schema JSON from the
static host instead of Cloud Run, and keep the front end's debounce.

## 16. What was tested here, what was not, and open questions

**Linted / run locally (no network to Google, no Docker, no ports):**
`bash -n` on all scripts; `deploy_api.sh` with `DRY_RUN=1` (staging, drift guards, env file, exact gcloud command; the staging dir and the env file are removed afterwards); `deploy_web.sh` with `DRY_RUN=1`
and a real `vite build` into a scratch directory (with `--base` and `VITE_API_URL`; the URL is found in the bundle, the base path is applied to the asset URLs); `smoke_test.sh` end to end against the real FastAPI app
through a shim `curl` that calls the app in-process (all checks pass; the failure paths - wrong class count, refused CORS origin, unreachable host - exit 1); the workflow parses as YAML and every `needs:` resolves.

**NOT tested:** any call to Google (auth, `gcloud run deploy`, Cloud Build of the Dockerfile, IAM roles, WIF, budgets, logging commands), Docker build of `api/Dockerfile` (the repository notes say it was never built either),
real cold-start time, real memory in the container, the `X-Forwarded-For` behaviour on Cloud Run, GitHub Actions execution of `deploy.yml` (no `actionlint` here), GitHub Pages / Firebase / Cloudflare publishing, the
`gcloud` flag spellings beyond what I remember of the CLI (check `gcloud run deploy --help` if an error says otherwise), every quota and price quoted.

**Dockerfile check (read-only, as of when this was written; `api/` is being edited by someone else, re-run `DRY_RUN=1 deploy/deploy_api.sh` - it repeats these checks):**
(a) **`api/cache.py` is imported by `api/main.py` but is not in the Dockerfile's `COPY api/__init__.py api/main.py ...` line - the container would crash at import.**  `deploy_api.sh` refuses to deploy while any `api/*.py` is missing from the Dockerfile.
(b) `engine/` (whole directory), the three `src/` modules (`companion_kits`, `companion_python_model`, `status_timeline`; `engine/_src.py` is the only importer, `src/status_timeline.py` imports `openpyxl` only inside an unused helper) and `data/factor_table.json` are covered.
(c) `data/cube_potential_data.json` exists in the repo but the image does **not** contain it; nothing reads it yet (`engine/cubes.py` does not exist).  When `engine/cubes.py` lands, add `COPY data/cube_potential_data.json /app/data/` to the Dockerfile and `!data/cube_potential_data.json` to `api/Dockerfile.dockerignore` (the staging in `deploy_api.sh` already ships the file and errors if `engine/cubes.py` exists without the COPY).
(d) The image is `python:3.12-slim`, while the engine goldens are generated and checked in CI with Python 3.11 (`app-tests.yml` notes that 3.12+ changes `sum()` rounding): production numbers may differ from the goldens in the last digits.  Consider `python:3.11-slim` for the image.
(e) `api/Dockerfile.dockerignore` is only honoured by BuildKit when building locally with the repo root as context; `deploy_api.sh` does not depend on it (it stages its own clean context).

**You need to decide / provide:** (1) Google Cloud **project ID**, (2) **region**, (3) the **static host** (GitHub Pages / Cloudflare / Firebase) - and for GitHub Pages whether the repository is public, (4) the front end's origin(s) for `MSI_CORS_ORIGINS`, (5) whether to deploy
from your machine only or also set up the GitHub Actions identity (section 12).

## 17. Accounts setup (optional: Google sign-in + cloud-saved profiles)

What it is: players sign in with Google and their saved profiles (+ theme, last class) follow them across browsers.  The web page talks to **Firebase Authentication** and **Cloud Firestore** directly; the rules in `deploy/firebase/firestore.rules`
let only the owner touch their documents; the Cloud Run API is untouched.  Design: `APP_ACCOUNTS_DESIGN.md`; behaviour, bundle sizes and tests: `web/README.md` ("Accounts").  It is **off** until you do step 5 (the four `VITE_FIREBASE_*` values).
Everything in the repo is built and tested without Google (fakes, no emulator); **what is left is your console clicks and a first real test.**

Checklist (Firebase console: <https://console.firebase.google.com/project/maplestoryidleoptimizer>; use your own project id if different):

1. [ ] **Enable Google sign-in.**  Build -> Authentication -> **Get started** -> Sign-in method -> **Google** -> Enable, choose a **project support e-mail** -> Save.
2. [ ] **Authorized domains.**  Authentication -> Settings -> **Authorized domains**: `maplestoryidleoptimizer.web.app` and `maplestoryidleoptimizer.firebaseapp.com` are there by default; **add `localhost`** for local development and any custom domain / other host
   you serve the app from (GitHub Pages / Cloudflare need their own domain listed, e.g. `<user>.github.io`; sign-in on an unlisted domain fails with "auth/unauthorized-domain").
3. [ ] **Create the database.**  Build -> **Firestore Database -> Create database -> Production mode** (the rules from step 6 replace the default deny-all).  Choose the **location now: it can NOT be changed later.**  `nam5 (us-central)` is the safe default,
   `eur3 (europe-west)` for European players; pick `me-west1` only if your players are mainly in Israel and you accept its pricing tier.  Native mode ("Firestore", not Datastore).
4. [ ] **Register the web app to get the config.**  Project settings (gear) -> General -> **Your apps** -> **Add app -> Web (`</>`)** -> nickname -> (do not tick Firebase Hosting here, the script does that) -> Register.  Copy the four values of the `firebaseConfig`
   snippet: `apiKey`, `authDomain`, `projectId`, `appId`.  They are **public identifiers, not secrets** (access is controlled by the rules, and the API key can additionally be restricted to your domains under Google Cloud console -> APIs & Services -> Credentials).
5. [ ] **Put the four values where the build sees them** (any one of these; all four or none):
   * `web/.env.production` (read by `vite build`; it is not git-ignored: the values are public identifiers, so committing it is fine - use the next option if you prefer to keep them out of git):
     ```
     VITE_FIREBASE_API_KEY=...
     VITE_FIREBASE_AUTH_DOMAIN=maplestoryidleoptimizer.firebaseapp.com
     VITE_FIREBASE_PROJECT_ID=maplestoryidleoptimizer
     VITE_FIREBASE_APP_ID=1:...:web:...
     ```
   * or the same four lines in `deploy/.env` (read by `deploy/deploy_web.sh`, git-ignored), or exported in your shell, or as GitHub Actions variables if you build in CI (the workflow does not pass them yet: add them to its build step's `env`).
   * local try-out: `web/.env.local` and `npm run dev` (needs `localhost` from step 2 and the API running or `npm run dev:mock`).
6. [ ] **Deploy rules + hosting:**  `STATIC_HOST=firebase FIREBASE_PROJECT=maplestoryidleoptimizer API_URL=https://msi-api-xxxx-uc.a.run.app deploy/deploy_web.sh`
   (= `firebase deploy --only hosting,firestore:rules`; `FIREBASE_DEPLOY_RULES=0` for hosting only).  Rules alone: `cd deploy/firebase && npx firebase-tools deploy --only firestore:rules --project maplestoryidleoptimizer`.
   The script prints `accounts: ENABLED in this build` when the config reached the bundle.  The GitHub Actions Firebase job deploys hosting only: deploy the rules from your machine whenever `firestore.rules` changes.
7. [ ] **Test it for real** (this is the part nothing here could verify): open the site -> **Sign in with Google** -> read the privacy note -> Continue -> pick the account.  Then: save a profile on the Profiles tab; the cloud icon shows *unsaved* and the avatar a dot ->
   **account menu > Save to account** -> the dot disappears and the document appears in Console -> Firestore Database (`users/<uid>/profiles/...`).  Open the site in another browser, sign in: the profile arrives.  Change it in both, press Refresh / Save and
   check the conflict notice + Version history.  Try **Download all my data** and, last, **Delete my account and data** with a throw-away Google account (the documents and the user disappear from the console: Authentication -> Users).
8. [ ] **Rules tests on the emulator** (optional but recommended before relying on the rules; needs Java 21+ and Node 20+): `cd deploy/firebase/rules-test && npm install && npm run test:emulator`.  `npm run lint` there is an offline syntax sanity check.
9. [ ] (Optional) **App Check** (reCAPTCHA v3 / Enterprise) for the web app: Build -> App Check -> Apps -> register -> then "Enforce" for Authentication and Firestore only after you add the App Check initialisation to the web code (not built; the owner-only rules already stop everyone but the signed-in owner).
10. [ ] **Cost watch.**  The free Firestore quota (about 1 GiB stored, 50,000 reads and 20,000 writes per day - **to be verified** on the Firebase pricing page) is ample: sign-in costs one read per cloud profile (+1), Save is a handful of writes, nothing is read or written on edits.  The project's budget alert (section 3) covers it.

Notes
* **Privacy policy**: the app has one (Help tab -> "Privacy policy", footer link, direct address `https://maplestoryidleoptimizer.web.app/#privacy`). If Google's OAuth consent screen (Google Cloud console -> APIs & Services -> OAuth consent screen) asks for a privacy-policy / home-page link, use that address. The contact point is the GitHub issues page (`CONTACT_URL` in `web/src/content/help.tsx`); edit the text there if the practice changes (e.g. you add analytics, change the Firestore region wording, or publish an e-mail address).
* Sign-in popups need the page's own domain in the authorized domains; if a browser blocks the popup the app falls back to the full-page redirect flow (which works best when the page is served from the Firebase Hosting domain of the same project).
* The privacy note and the Help tab's "Accounts" section are written for this setup; if you add a custom privacy policy page, link it there (`web/src/content/help.tsx`, `web/src/components/account/dialogs.tsx`).
* Account deletion (a user's own button) removes their documents and their Auth user.  Removing a user by hand in the console does **not** delete their Firestore documents (delete `users/<uid>` and its sub-collections yourself).
* Do not change the Firestore location or delete the database afterwards; rules changes can be redeployed at any time.
