# Render shared demo

Prepared 25 November 2026. This is a deployment template, not a live deployment or a production-readiness claim.

## What the template provisions

The root `render.yaml` defines a Python backend, PostgreSQL 16 and a persistent upload disk, in the same Singapore region. It uses paid compute/database/storage plans. Review Render's cost estimate before applying; this file has not been applied to an account. Service names and region are infrastructure defaults and can be changed consistently in the template. Credentials, frontend origin and allowed hosts are supplied separately.

`LMS_ENV=demo` uses a separate settings profile. It retains password-based demo login, disables debug output, requires a strong secret, uses PostgreSQL with TLS, enables HTTPS/secure cookies and validates the frontend origin and media path. Institutional Entra, Redis, Azure Blob, Jitsi JWT, execution and antivirus services are not required to boot this demo. Production configuration is unchanged and remains stricter.

The demo uses one Gunicorn worker, database-backed Django sessions and the existing process-local cache. It does not have production Redis-based coordination or distributed AI-quota enforcement. Private upload access still goes through the existing authorized API; files reside on `/var/data/media`, on the attached disk. Back up PostgreSQL and uploads separately.

## Deploy the backend

1. Push the project to a repository accessible to Render. Keep `.env`, SQLite, `.venv`, uploads, logs and secrets out of Git. Review the repository contents before the first push.
2. In Render, create a Blueprint from that repository and its root `render.yaml`. Review the resources and cost estimate before applying. Automatic deploys are disabled in the template.
3. Set `PUBLIC_APP_URL` to the frontend origin. For a local frontend, use `http://localhost:3000` (or the exact loopback origin used). For a shared frontend, use its actual HTTPS origin without a path. Only that origin is trusted for CSRF.
4. Set `DJANGO_ALLOWED_HOSTS` to the actual backend hostname assigned by Render, plus `localhost,127.0.0.1` if the frontend proxy forwards loopback host headers. Add the real frontend hostname if its proxy forwards that Host. Do not use `*`. Verify the assigned hostname and update this setting if necessary.
5. Render generates a new Django secret and injects database credentials through Blueprint references. Python is selected through `backend/.python-version` (latest 3.13 patch). Confirm the build log selected Python 3.13; if necessary set Render's `PYTHON_VERSION` to a reviewed fully qualified 3.13 patch. Install uses `requirements.lock`; Linux/Python 3.13 package installation remains a hosted build verification gate.
6. The pre-deploy command runs `python manage.py migrate --noinput`. It does not seed records or create accounts. Gunicorn binds to `$PORT`. Readiness is `/api/lms/health/ready`; Render terminates HTTPS and supplies the forwarded-protocol header.
7. Check readiness and authentication denial without a session. Then test issued-account sign-in, CSRF, course scope, file upload/read, and persistence after a restart. A successful health check alone does not verify these workflows.

## Connect the existing Next.js frontend

Set `BACKEND_INTERNAL_URL` in the frontend environment to the actual HTTPS Render backend origin, without a trailing slash. Restart/redeploy Next.js so its proxy configuration is rebuilt. Keep the browser using the frontend `/api/lms/...` paths; it should not call the backend cross-origin directly. No new CORS bypass is needed for this proxy topology.

Deploying only the backend does not publish the frontend. If the frontend stays on this laptop, other people cannot use its localhost URL. A shared website needs a separately hosted Next.js frontend, with its origin configured as `PUBLIC_APP_URL` in the backend. Verify secure-cookie and CSRF behaviour through the chosen frontend proxy.

## Accounts, data and optional integrations

The new PostgreSQL database starts empty. This template does not transfer this laptop's data, passwords or uploaded files. Decide separately whether to migrate approved local data or create new demonstration accounts; do not copy secrets into source control. No seeding command runs automatically. The existing `seed_demo`/`seed_features` commands insert labelled sample records only if explicitly chosen for a disposable demo; they are not necessary for normal persisted workflows and are prohibited in production mode.

For tutor responses, set `AI_PROVIDER=gemini`, `AI_MODEL` and `AI_API_KEY` in the Render backend's secret environment settings. Do not commit them. Without these, the tutor reports a configuration error while ordinary LMS endpoints remain available.

Without the optional execution service, only the existing restricted Python teaching interpreter is available. Without antivirus, demo uploads do not receive the production scan gate. Demo live-class links are not equivalent to a validated institutional meeting service. Use demonstration content, not real confidential learner records.

For automatic finalization of quizzes while browsers are closed, configure a separate background worker or scheduler running `python manage.py expire_attempts --watch` (or a periodic one-shot `expire_attempts`) against the same database. This worker is not provisioned by the initial backend template and may incur additional cost. Answer endpoints still enforce deadlines independently.

## Scope and verification

Configuration tests check strict demo validation, secure cookies, proxy/TLS settings, storage path and separation from production. No Render resources, payments, accounts, remote records or secrets were created. Linux dependency installation, PostgreSQL integration, Render Blueprint acceptance, hosted authentication and persistence must be verified after a repository/account is connected.

References: [Render Django deployment](https://render.com/docs/deploy-django), [Blueprint fields](https://render.com/docs/blueprint-spec), [persistent disks](https://render.com/docs/disks), [Python version selection](https://render.com/docs/python-version). Render's ephemeral filesystem does not preserve uploads across restarts; this template therefore uses a paid persistent disk rather than pretending a free service provides durable local media.
