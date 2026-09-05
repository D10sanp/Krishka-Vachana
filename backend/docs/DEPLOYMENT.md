# Deployment Runbook - Krishka Vachana Backend

## Overview

This is the FastAPI + Python backend for Krishka Vachana (SIH problem
statement 26032): farmer/crop registration, procurement-centre listing,
Smart Slot booking, a Dynamic Queue system, payment tracking, and farm
history. It depends on **Firebase Authentication** (verifying ID tokens
issued by the Frontend's Firebase SDK), **Firestore** (all persistent
data), **Google Secret Manager** (the Aadhaar-fingerprint HMAC key), an
**SMS gateway** (OTP + transactional notifications, generic client not
yet bound to a vendor), and an **optional AI/ML congestion-prediction
HTTP endpoint** (falls back to a built-in heuristic if unset/unreachable).
None of these are hard-coded - the backend runs in a degraded-but-usable
mode locally without any of them configured (see `ALLOW_DEV_AUTH_FALLBACK`
below).

## Prerequisites

| Item | Owned by |
|---|---|
| Firebase project (Auth + Firestore) provisioned | Database & Infrastructure |
| Firestore composite indexes deployed (`firestore.indexes.json` at repo root) | Database & Infrastructure |
| A GCP service account with `roles/secretmanager.secretAccessor`, and a Secret Manager secret holding a 32+ byte Aadhaar HMAC key, pinned to an explicit numeric version | Database & Infrastructure (secret contents are Backend's concern - see `app/core/secrets.py`) |
| A `PAYMENT_GATEWAY_WEBHOOK_SECRET` value, shared with whichever payment gateway is chosen | Backend + payment gateway integrator |
| An SMS gateway account/API key (once a vendor is chosen) | Whoever picks the vendor (currently unassigned - see backend README "Design notes for teammates") |
| A container host (Cloud Run recommended - see below) | Database & Infrastructure |

## Environment Variables Reference

| Variable | Required in prod | Default | Who provisions it | Description |
|---|---|---|---|---|
| `ENVIRONMENT` | Yes | `development` | Backend/Infra (deploy config) | `production` or `development`. Gates the dev-auth fallback. |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Yes (or use ADC on GCP) | `./secrets/firebase-service-account.json` | Database & Infrastructure | Path to a Firebase Admin service-account key file. |
| `FIREBASE_PROJECT_ID` | Yes | `krishka-vachana` | Database & Infrastructure | Firebase project id. |
| `FIREBASE_EMULATOR_HOST` | No | empty | Backend (local dev only) | Convenience: sets both Auth + Firestore emulator host:port. |
| `FIRESTORE_EMULATOR_HOST` | No | empty | Backend (local dev only) | Overrides just the Firestore emulator host. |
| `FIREBASE_AUTH_EMULATOR_HOST` | No | empty | Backend (local dev only) | Overrides just the Auth emulator host. |
| `ALLOW_DEV_AUTH_FALLBACK` | **No - must be `false`** | `false` | Backend (local dev only) | If `true` and Firebase isn't configured, accepts any bearer token as the farmer's uid and uses an in-memory store. Never enable in a real deployment. |
| `AADHAAR_HMAC_SECRET_NAME` | Yes | empty | Database & Infrastructure (secret), Backend (pins the version) | Full Secret Manager resource name, pinned to an explicit numeric version (not `latest`). |
| `CORS_ORIGINS` | Yes | `http://localhost:3000` | Backend + Frontend | Comma-separated list of allowed origins. Update when the Frontend's deployed domain changes. |
| `SMS_GATEWAY_API_KEY` | Yes once a vendor is chosen | empty | Whoever picks the SMS vendor | Bearer token for the SMS gateway. |
| `SMS_GATEWAY_BASE_URL` | Yes once a vendor is chosen | empty | Whoever picks the SMS vendor | Base URL for the SMS gateway. Unset = notifications log only (safe default for dev). |
| `SMS_GATEWAY_TIMEOUT_SECONDS` | No | (see `.env.example`) | Backend | HTTP timeout for SMS gateway calls. |
| `OTP_LENGTH` | No | (see `.env.example`) | Backend | Digits in a generated OTP code. |
| `OTP_TTL_SECONDS` | No | (see `.env.example`) | Backend | How long an OTP stays valid. |
| `OTP_MAX_ATTEMPTS` | No | (see `.env.example`) | Backend | Incorrect attempts allowed before lockout. |
| `OTP_REQUEST_COOLDOWN_SECONDS` | No | (see `.env.example`) | Backend | Minimum time between OTP requests for one farmer. |
| `OTP_HMAC_SECRET` | Yes | empty | Backend/Infra (generate + store, not Secret-Manager-fetched today - a plain env var) | Key used to hash OTP codes at rest. Generate with `openssl rand -base64 32` or similar. |
| `CONGESTION_PREDICTION_API_URL` | No | empty | AI/ML | URL of the real congestion-prediction model. Unset = heuristic fallback (fully functional). |
| `CONGESTION_PREDICTION_API_TIMEOUT_SECONDS` | No | (see `.env.example`) | Backend | HTTP timeout for the congestion-prediction call. |
| `PAYMENT_GATEWAY_WEBHOOK_SECRET` | Yes | empty (rejected in production if unset/weak) | Backend + payment gateway integrator | Shared secret verifying `X-Payment-Signature` on the payment webhook. Generate with `openssl rand -base64 48`. |
| `API_V1_PREFIX` | No | `/api/v1` | Backend | API path prefix. |
| `APP_VERSION` | No | `0.1.0` | Backend | Shown in `/api/v1/health` and `/status`. |
| `ENABLE_DOCS` | Recommended `false` in prod if docs shouldn't be public | `true` | Backend/Infra (deploy config) | Disables `/docs`, `/redoc`, `/openapi.json`, `/status` entirely (404) while `/api/v1/health` keeps working. |

(Full descriptions and generation notes for every variable are also
inline as comments in `backend/.env.example`, which is kept in sync with
this table.)

## What Infra/DB Team Must Give to Backend Before Deployment

1. **Firebase Admin service-account key** (JSON) for the backend's own use, or confirmation that the host runs on GCP with an attached identity that has Firestore/Auth access (Application Default Credentials) - goes to `FIREBASE_SERVICE_ACCOUNT_PATH` or is skipped entirely on GCP.
2. **Firebase project id** - goes to `FIREBASE_PROJECT_ID`.
3. **Confirmation that `firestore.indexes.json` (repo root) has been deployed** via `firebase deploy --only firestore:indexes` - several queries (payment/queue pagination, `count_waiting_ahead`) depend on the composite indexes it defines.
4. **A GCP service account with `roles/secretmanager.secretAccessor`** on the Aadhaar HMAC secret, either as a mounted key file (`GOOGLE_APPLICATION_CREDENTIALS`, off-GCP hosts) or as the platform's own runtime identity (on GCP, no key file needed).
5. **The pinned Secret Manager resource name** for the Aadhaar HMAC key (`projects/.../secrets/.../versions/<N>` - an explicit number, never `latest`) - goes to `AADHAAR_HMAC_SECRET_NAME`.
6. **The deployed Frontend's origin(s)**, so Backend can set `CORS_ORIGINS` correctly.

## What Backend Gives to Other Teams

### To Frontend

- **Base API URL pattern**: `https://<deployed-host>/api/v1/...`
- **Auth header**: `Authorization: Bearer <firebase-id-token>` on every endpoint except health checks and the payment webhook.
- **Error shape** (identical on every endpoint): `{"error": {"code": "...", "message": "..."}}` with a matching HTTP status (404/409/422/401/403/503/500).
- **OpenAPI schema**: `https://<deployed-host>/openapi.json` (disabled if `ENABLE_DOCS=false`).
- **Endpoints**:

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/health` | none | Liveness |
| GET | `/api/v1/health/ready` | none | Readiness |
| POST | `/api/v1/farmers/register` | farmer | Register profile |
| GET | `/api/v1/farmers/me` | farmer | Get profile |
| PATCH | `/api/v1/farmers/me` | farmer | Update profile |
| POST | `/api/v1/farmers/me/phone/otp/request` | farmer | Request phone OTP |
| POST | `/api/v1/farmers/me/phone/otp/verify` | farmer | Verify phone OTP |
| GET | `/api/v1/farmers/me/history` | farmer | Aggregated farm history (paginated) |
| POST | `/api/v1/crops` | farmer | Register a crop |
| GET | `/api/v1/crops/me` | farmer | List own crops |
| GET | `/api/v1/centres` | farmer | List procurement centres |
| GET | `/api/v1/centres/{centre_id}` | farmer | Get one centre |
| GET | `/api/v1/centres/{centre_id}/congestion` | farmer | Predicted congestion + alternatives |
| POST | `/api/v1/bookings` | farmer | Book a Smart Slot |
| GET | `/api/v1/bookings/me` | farmer | List own bookings |
| GET | `/api/v1/bookings/{booking_id}` | farmer | Get one booking |
| POST | `/api/v1/bookings/{booking_id}/cancel` | farmer | Cancel a booking |
| POST | `/api/v1/bookings/cluster` | farmer | Village cluster booking |
| POST | `/api/v1/queue/check-in` | farmer | Check in to live queue |
| GET | `/api/v1/queue/me` | farmer | Own active queue entry |
| GET | `/api/v1/queue/{queue_id}` | farmer | Get one queue entry |
| POST | `/api/v1/queue/{queue_id}/complete` | farmer | Self-report served |
| POST | `/api/v1/queue/{queue_id}/leave` | farmer | Self-report left |
| GET | `/api/v1/queue/{queue_id}/token` | farmer | Printable HTML token (not JSON, not in OpenAPI schema) |
| GET | `/api/v1/queue/centre/{centre_id}` | farmer | Aggregate centre queue status |
| GET | `/api/v1/payments/me` | farmer | List own payments (paginated) |
| POST | `/api/v1/payments` | farmer, dev-only | Mock payment recording (development only) |
| POST | `/api/v1/payments/webhook` | `X-Payment-Signature` (not farmer bearer token) | Real payment-gateway webhook |

### To Infra/DB

- **Docker build**: `docker build -t krishka-vachana-backend .` (run from `backend/`).
- **Port**: `8000` (`EXPOSE 8000` in the Dockerfile; override with `PORT`).
- **Health check for readiness probes**: `GET /api/v1/health` (liveness, always 200) and `GET /api/v1/health/ready` (readiness; 200 `{"status": "ok", ...}` or 503 `{"status": "degraded", ...}`).
- **Firestore collections read/written**: `farmers`, `crops`, `centres`, `slot_bookings`, `active_slot_bookings`, `slot_capacity_counters`, `queue_entries`, `active_farmer_queue_entries`, `active_booking_queue_entries`, `queue_daily_counters`, `payments`, `payment_booking_reservations`, `aadhaar_reservations`.
- **Secret Manager secrets accessed**: one - the Aadhaar HMAC key at `AADHAAR_HMAC_SECRET_NAME`. (`OTP_HMAC_SECRET` and `PAYMENT_GATEWAY_WEBHOOK_SECRET` are plain environment variables today, not Secret-Manager-fetched - flag if that should change.)

## Deployment Steps (Cloud Run)

1. Confirm all items in "What Infra/DB Team Must Give to Backend" above are ready.
2. Build and push the image: `docker build -t <registry>/krishka-vachana-backend:<tag> backend/` then push to your registry (Artifact Registry for Cloud Run).
3. Deploy to Cloud Run, setting every "Required in production" env var from the table above. On Cloud Run, skip `GOOGLE_APPLICATION_CREDENTIALS`/`FIREBASE_SERVICE_ACCOUNT_PATH` and instead grant the Cloud Run service's runtime service account both Firestore/Auth access and `roles/secretmanager.secretAccessor`.
4. Set the Cloud Run health check to `GET /api/v1/health/ready`.
5. Set `ENABLE_DOCS=false` unless the team wants `/docs`/`/status` public.
6. Verify: `curl https://<service-url>/api/v1/health` returns 200, and `curl https://<service-url>/api/v1/health/ready` returns 200 once Firestore is reachable.
7. For non-Cloud-Run container hosts (Fly.io, Render, ECS), the same Dockerfile works - mount a Firebase service-account key and a GCP key with Secret Manager access instead of relying on ambient GCP identity (see backend README "Deploying" section for the exact `docker run` invocation). The included `Procfile` covers Heroku-style platforms.

## Team Secrets and Shared Configuration - Compact Reference

*(copy-paste into a team channel/doc)*

**Backend service URLs** (once deployed):
- API base: `https://<deployed-host>/api/v1`
- Health check: `GET https://<deployed-host>/api/v1/health/ready`
- Docs (if enabled): `https://<deployed-host>/docs`

**CORS**: Backend currently allows `http://localhost:3000` only (`CORS_ORIGINS`). **Frontend: tell Backend as soon as your deployed domain is known** so it can be added.

**What Backend needs from Infra/DB** (checklist, names/format only - no values here):
- [ ] Firebase Admin service-account key (JSON) or confirmation of GCP ambient identity
- [ ] `FIREBASE_PROJECT_ID`
- [ ] Confirmation `firestore.indexes.json` has been deployed
- [ ] GCP identity with `roles/secretmanager.secretAccessor` on the Aadhaar secret
- [ ] Pinned `AADHAAR_HMAC_SECRET_NAME` (explicit numeric version)

**What Backend needs from whoever picks the SMS vendor**:
- [ ] `SMS_GATEWAY_BASE_URL`
- [ ] `SMS_GATEWAY_API_KEY`

**What Backend needs from the payment gateway integration**:
- [ ] Shared `PAYMENT_GATEWAY_WEBHOOK_SECRET` value (generate with `openssl rand -base64 48`, store in the platform's secret manager, never commit it)

**What AI/ML can plug in whenever ready** (optional, has a working fallback):
- [ ] `CONGESTION_PREDICTION_API_URL`
