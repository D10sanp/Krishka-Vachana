# Krishka Vachana Backend (SIH26032)

Backend API for the project, owned by the Backend role (see
`team_work_division.md` at the repo root). Built with **FastAPI + Python**,
per the repo's `technology_stack.md` (the tech stack in the initial project
PPT is out of date - this repo's own docs are the source of truth).

## Scope of this package

This directory contains **backend only**. It does not touch:
- `frontend/` (Next.js + React + TypeScript) - Frontend role
- Firebase project config, Firestore schema/security rules, CI/CD - Database
  & Infrastructure role
- ML models - AI/ML role (this backend exposes a placeholder integration
  point for their predictions once ready; see roadmap below)

## Current status: Phase 4 of 4 (100%)

Implemented so far - all four stages of the product flow
(`Farmer -> Smart Slot -> Predicted Arrival -> Dynamic Queue -> ...`),
built to be deployable as-is rather than a throwaway prototype:

- Project scaffold (FastAPI app, settings, error handling)
- Auth dependency that verifies Firebase ID tokens (an explicitly enabled
  dev-only fallback keeps local work unblocked before Firebase is available)
- Repository abstraction (`app/repositories/`) with an in-memory
  implementation for local dev/tests and a Firestore implementation ready
  to wire in once the Infra teammate confirms collection names/schema
- **Farmer ID / Aadhaar-linked identification**: registration + profile
  endpoints. Full Aadhaar numbers are validated on input but never stored
  or returned in plaintext - only a keyed fingerprint and the last 4 digits.
- **Crop and quantity registration**: endpoints to register a crop +
  quantity against a farmer and list a farmer's registered crops.
- **Procurement-centre selection**: endpoints to list procurement centres
  (with optional district/state filters) and fetch one by id. Centre
  records are reference data - the in-memory fallback seeds a handful of
  sample centres for dev/tests; production data is expected to live in
  Firestore once Infra wires that collection up.
- **Smart Slot booking**: book/list/get/cancel a slot against a centre +
  date + fixed daily time window (`app/schemas/centre.py:SLOT_WINDOWS`).
  Capacity per (centre, date, window) is enforced atomically - two farmers
  racing for the last seat in a window can't both win (same
  reserve-then-create pattern already used for Aadhaar uniqueness), and
  cancelling frees the seat back up. Optionally links a booking to a
  previously registered crop.
- **Congestion-prediction integration point**: `GET
  /api/v1/centres/{centre_id}/congestion` - a stable contract AI/ML's real
  model can sit behind once it exists (`CONGESTION_PREDICTION_API_URL`).
  Until then (and if that endpoint is ever unreachable), it falls back to
  a deterministic heuristic computed from actual booked/capacity ratios,
  plus a basic "quieter centre in the same district" suggestion - same
  graceful-degradation shape the Firebase integration already uses.
- **Dynamic Queue system**: a Smart Slot booking reserves capacity ahead
  of time; checking in (`POST /api/v1/queue/check-in`) represents a
  farmer's actual, live arrival-order position at the centre on the day
  of their slot. Live position, people-ahead count, and a simple
  estimated-wait heuristic are computed on every read - see
  `app/services/queue_service.py`. There's no separate "centre staff"
  role in this system yet (see `team_work_division.md`), so status
  changes are self-reported and ownership-checked: a farmer checks
  themselves in, then later marks their own entry served (procurement
  complete) or left (leaving without being served) - the same pattern
  Smart Slot cancellation already uses.
- **Printable issued token**: `GET /api/v1/queue/{queue_id}/token` - a
  branded, printer-friendly HTML page (same spirit/disclaimer as `/docs`
  and `/status` below) showing a farmer's token number, centre, and live
  status, for farmers without a smart device (or whoever is helping them)
  to print or show at the centre.
- **SMS gateway / phone-number OTP verification**: `app/core/sms.py` is a
  generic SMS gateway client (no vendor chosen yet - see its docstring for
  the placeholder payload shape and how to swap it in later). It's used
  for two things: best-effort transactional notifications (booking
  confirmed, checked-in-with-token-number) whose delivery failures do not
  fail the primary action, and a proper OTP flow
  (`POST /api/v1/farmers/me/phone/otp/request` /
  `.../otp/verify`) that verifies a farmer's registered phone number
  independently of Firebase Authentication (Infra's domain, used for
  login/identity) - see `app/services/otp_service.py`.
- **Production/deployment readiness**:
  - Liveness (`/api/v1/health`) and readiness (`/api/v1/health/ready`)
    endpoints, matching the standard container-platform health-check split
  - Custom-branded interactive docs at `/docs`, ReDoc at `/redoc`, and a
    human-friendly `/status` page (now also reporting whether the
    congestion-prediction integration is wired to a real model or running
    on the fallback heuristic) - all can be fully disabled in production
    via `ENABLE_DOCS=false` (verified: returns 404 while
    `/api/v1/health` keeps working)
  - `Dockerfile` (non-root user, `HEALTHCHECK`, gunicorn + uvicorn
    workers) and a `Procfile` for platforms that use one instead
  - Config fully via environment variables (`.env.example`), no
    hardcoded secrets
- Test suite (149 test functions / 161 parametrized test cases) covering all of the above.

### Roadmap (remaining phases, future PRs)

| Phase | Scope |
|---|---|
| ~~2~~ | ~~Procurement-centre listing, Smart Slot booking, congestion-prediction integration point (consumes AI/ML's endpoint)~~ done |
| ~~3~~ | ~~Dynamic Queue system (position, printable token generation), SMS/OTP integration~~ done |
| ~~4~~ | ~~Payment tracking, Historical farm record, Village Cluster Booking, polish~~ done |

## API surface (Phase 1 + 2 + 3 + 4)

All endpoints are versioned under `/api/v1`. Farmer endpoints require
`Authorization: Bearer <firebase-id-token>`; health endpoints are public, and
the payment webhook authenticates with `X-Payment-Signature` instead.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Liveness check (always 200 while the process is up) |
| GET | `/api/v1/health/ready` | Readiness check (verifies Firestore connectivity when configured; 503 if degraded) |
| POST | `/api/v1/farmers/register` | Register the authenticated farmer's profile |
| GET | `/api/v1/farmers/me` | Get the authenticated farmer's profile |
| PATCH | `/api/v1/farmers/me` | Update the authenticated farmer's profile |
| POST | `/api/v1/crops` | Register a crop + quantity for the authenticated farmer |
| GET | `/api/v1/crops/me` | List the authenticated farmer's registered crops |
| GET | `/api/v1/centres` | List procurement centres (optional `?district=` / `?state=` filters) |
| GET | `/api/v1/centres/{centre_id}` | Get one procurement centre |
| GET | `/api/v1/centres/{centre_id}/congestion?slot_date=YYYY-MM-DD` | Predicted per-window congestion + alternative centres |
| POST | `/api/v1/bookings` | Book a Smart Slot (centre + date + time window, optional crop link) |
| GET | `/api/v1/bookings/me` | List the authenticated farmer's bookings |
| GET | `/api/v1/bookings/{booking_id}` | Get one of the authenticated farmer's bookings |
| POST | `/api/v1/bookings/{booking_id}/cancel` | Cancel a booking and free its slot capacity |
| POST | `/api/v1/farmers/me/phone/otp/request` | Send a one-time verification code to the farmer's registered phone number |
| POST | `/api/v1/farmers/me/phone/otp/verify` | Verify a submitted OTP code; marks `phone_verified` true |
| POST | `/api/v1/queue/check-in` | Check the farmer in to their booked centre's live queue |
| GET | `/api/v1/queue/me` | Get the farmer's active queue entry and live position |
| GET | `/api/v1/queue/{queue_id}` | Get a specific queue entry owned by the farmer |
| POST | `/api/v1/queue/{queue_id}/complete` | Self-report the farmer's own entry as served (procurement complete) |
| POST | `/api/v1/queue/{queue_id}/leave` | Cancel the farmer's own queue entry without being served |

(remaining Phase 3/4 endpoints - bookings/cluster, payments, history, queue token page - are unchanged by this PR and omitted here for brevity; see the routers under `app/api/v1/` for the full list.)

## Local setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

For local development without Firebase credentials, explicitly set
`ALLOW_DEV_AUTH_FALLBACK=true` to use the in-memory store and dev-only auth
mode (any non-empty Bearer token is accepted as the farmer's uid). Set
`FIREBASE_SERVICE_ACCOUNT_PATH` (or `FIREBASE_EMULATOR_HOST`) once real
credentials or an emulator are available. Farmer registration also requires
a stable, 32-byte-or-longer key in Google Secret Manager; configure its full
version resource as `AADHAAR_HMAC_SECRET_NAME`.

## Running tests

```bash
pip install -r requirements.txt
pytest -q
```

## Deploying

### Docker (any container host: Cloud Run, Fly.io, Render, ECS, etc.)

```bash
docker build -t krishka-vachana-backend .
test -n "${PAYMENT_GATEWAY_WEBHOOK_SECRET:-}" || { echo "PAYMENT_GATEWAY_WEBHOOK_SECRET must be set" >&2; exit 1; }
docker run -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e ENABLE_DOCS=false \
  -e AADHAAR_HMAC_SECRET_NAME=projects/PROJECT_ID/secrets/aadhaar-hmac-key/versions/1 \
  -e PAYMENT_GATEWAY_WEBHOOK_SECRET="${PAYMENT_GATEWAY_WEBHOOK_SECRET}" \
  -e FIREBASE_SERVICE_ACCOUNT_PATH=/secrets/firebase.json \
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-service-account.json \
  -v /path/to/firebase-service-account.json:/secrets/firebase.json:ro \
  -v /path/to/gcp-service-account.json:/secrets/gcp-service-account.json:ro \
  krishka-vachana-backend
```

Generate `PAYMENT_GATEWAY_WEBHOOK_SECRET` once with a cryptographically
secure generator such as `openssl rand -base64 48`, store it in the hosting
platform's managed secret store, and inject it under that environment-variable
name. Do not generate it at application startup: the gateway and all backend
instances must share the same stable value.

`FIREBASE_SERVICE_ACCOUNT_PATH` only configures Firebase Admin (Firestore /
Auth) - it does nothing for Secret Manager. `app/core/secrets.py` creates a
plain `SecretManagerServiceClient()`, which authenticates via [Application
Default Credentials
(ADC)](https://cloud.google.com/docs/authentication/application-default-credentials),
completely separately from Firebase. Give it credentials one of two ways:

- **Off-GCP hosts** (Fly.io, Render, ECS, etc., as in the example above): set
  `GOOGLE_APPLICATION_CREDENTIALS` to a mounted service-account key JSON for
  an account with `roles/secretmanager.secretAccessor` on the Aadhaar secret.
  This can be the same project as Firebase but does not have to be the same
  key as `FIREBASE_SERVICE_ACCOUNT_PATH`.
- **On GCP** (Cloud Run, GKE, Compute Engine): skip
  `GOOGLE_APPLICATION_CREDENTIALS` entirely and instead attach the
  platform's own identity (the Cloud Run service's runtime service account,
  a GKE workload-identity binding, etc.) with that same role - ADC picks it
  up automatically, no key file needed.

Without one of these, farmer registration returns `503` the first time it
tries to load the Aadhaar HMAC key (see `get_aadhaar_hmac_key` - it fails
closed rather than crashing the process).

The image runs as a non-root user, serves via gunicorn with uvicorn
workers (`Dockerfile` `CMD`), and has a built-in `HEALTHCHECK` against
`/api/v1/health`.

### Platforms that use a Procfile instead (Railway, Heroku-style)

The included `Procfile` runs the same gunicorn command; just set the same
environment variables in the platform's dashboard.

### Vercel

The repo's `technology_stack.md` lists Vercel + Firebase for deployment.
Vercel's Python support targets serverless functions rather than a long-
running ASGI process - wiring that up (e.g. via an ASGI adapter and
`vercel.json`) is an infra/deployment decision I've left for the Database
& Infrastructure teammate to confirm, since they own the deployment
pipeline per `team_work_division.md`. The Docker/Procfile paths above work
on any container-based host in the meantime.


## Design notes for teammates

- **Frontend**: request/response shapes are the `FarmerCreate`/`FarmerOut`,
  `CropRegistrationCreate`/`CropOut`, `CentreOut`, `SlotBookingCreate`/
  `SlotBookingOut`, `CongestionOut`, `QueueCheckInCreate`/`QueueEntryOut`/
  `QueueCentreStatusOut`, and `OtpVerifyRequest`/`OtpRequestOut`/
  `OtpVerifyOut` models in `app/schemas/`. Errors come back as
  `{"error": {"code": "...", "message": "..."}}` with an appropriate HTTP
  status, matching the error-state pattern in `UI_rules.md` section 22.
  Booking a full slot window returns `409 conflict` (not a generic error) -
  a good case to route to a "pick a different time" UI rather than a bare
  "something went wrong" message; the same is true of checking in twice or
  checking in before your slot date. `FarmerOut.phone_verified` is new -
  false until a farmer completes the OTP flow. `GET
  /api/v1/queue/{queue_id}/token` is plain HTML (not JSON) and isn't in
  the OpenAPI schema - it's a backend-rendered fallback page, not meant to
  be fetched/parsed by the frontend app itself (see its docstring in
  `app/api/v1/queue.py`).
- **Database & Infrastructure**: `app/repositories/firestore.py` is a
  placeholder using `farmers`/`crops`/`centres`/`slot_bookings` as
  collection names and flat documents matching the schemas above - please
  review against whatever schema/security rules you set up and flag any
  mismatch. New in Phase 2: `centres` is expected to hold procurement-centre
  reference data (please seed real centres there once it exists - Backend
  only ships a small in-memory sample set for dev/tests, not production
  data), and `slot_capacity_counters` is a small counter-per-(centre, date,
  window) collection the backend uses to keep capacity checks O(1) instead
  of counting booking documents on every request - flag if that pattern
  conflicts with your Firestore setup. New in Phase 3: `queue_entries`
  holds live check-ins, with `active_farmer_queue_entries` /
  `active_booking_queue_entries` as small uniqueness-index collections
  (same reserve-then-create pattern as `aadhaar_reservations`) and
  `queue_daily_counters` as the token-sequence counter (same shape as
  `slot_capacity_counters`). Before deploying the backend, run
  `firebase deploy --only firestore:indexes` from the repository root;
  `firebase.json` points the CLI at `firestore.indexes.json`, which covers
  the sequence-based `count_waiting_ahead` query. Also see the Vercel note
  above re: final deployment target.
- **AI/ML**: `GET /api/v1/centres/{centre_id}/congestion` is the
  integration point mentioned in `team_work_division.md` ("expose model
  predictions via an API endpoint...works closely with Backend Developer
  to integrate into FastAPI"). Point `CONGESTION_PREDICTION_API_URL` at
  your model's HTTP endpoint once it exists; the backend `POST`s
  `{centre_id, date, capacity_per_slot, slot_windows}` and expects back
  `{windows: [{slot_window, booked_count, capacity_per_slot,
  congestion_level}], alternative_centres: [{centre_id, name, district,
  congestion_level}]}` (see `app/schemas/congestion.py` for the exact
  shape and `app/services/congestion_service.py` for the current
  heuristic it's replacing). Until then, the backend serves a deterministic
  fallback computed from real booking data so the endpoint is fully usable
  today - no frontend changes needed when the real model comes online. No
  changes from Phase 3.
- **Whoever picks an SMS vendor**: `app/core/sms.py` sends a generic
  `{"to": ..., "message": ...}` JSON POST with a Bearer `Authorization`
  header to `SMS_GATEWAY_BASE_URL` - update the payload shape in that one
  file once a vendor is chosen; nothing else in the codebase needs to
  change (same integration-point pattern as the congestion endpoint
  above). Until then it logs only a generic skipped-delivery event, so local
  dev/tests never need a real gateway or expose message contents.
- **Whoever manages the Secret Manager entry**: `AADHAAR_HMAC_SECRET_NAME`
  must pin an explicit numeric version (`.../versions/7`, not
  `.../versions/latest`) - the app rejects a mutable alias outright. This
  is deliberate, not an oversight: rotating this key has a real trade-off
  documented at the top of `app/core/secrets.py` (short version: because
  we never store the plaintext Aadhaar number, rotating the key means new
  registrations stop being checked for duplicates against farmers who
  registered under the old version). Read that comment before rotating.
