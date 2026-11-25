# Admiezo production deployment handoff

This release prepares the application and its production integration paths for institution IT. It does not create a subscription, register an Entra application, publish a hostname, obtain licensed exam material or claim a live production deployment. Docker is installed on the authoring workstation, but its Linux engine was not running; container, PostgreSQL and external-service acceptance must be performed by IT.

Read [the final 0.3.1 SRS/LLD review](../docs/FINAL-SRS-LLD-REVIEW.md) before staging acceptance. It maps all 93 feature requirements and records remaining implementation decisions. Use the 0.3.1 archive and checksum, superseding 0.2.0 and 0.2.1.

## Release contents

- Next.js standalone frontend image definition and Python 3.13/Gunicorn backend image definition.
- Production Compose topology: private backend/frontend/quiz worker and a Caddy TLS edge. Only ports 80/443 are exposed. Database, identity, cache, scanner, storage, video and execution services belong to the institution environment.
- Production configuration validation, `/api/lms/health/live` and `/api/lms/health/ready`, plus `deployment_check --live-services`.
- Additive migrations preserve existing answers, course references, submissions and progress. No demo seed or destructive reset is part of deployment.
- Interface language preferences and shared English/Hindi/Kannada label catalogues, advanced assessment question types, structured marking rubric controls and private activity-group membership.

## IT values to supply

Create `deploy/.env.production` from `.env.production.example`. Keep its permission mode 0600 and store the equivalent secrets in the institution secret manager. The release ZIP excludes this file.

| Service | Required institution configuration |
| --- | --- |
| Public access | DNS name, PUBLIC_APP_URL as an HTTPS origin, public ports 80/443, TLS contact/policy and permitted Django hostnames. Include backend and loopback hostnames for private proxy/readiness requests. |
| Database | Azure Database for PostgreSQL Flexible Server 16, dedicated database/user, TLS required, backups/PITR and private network/firewall access from the application host. |
| Cache | Private Redis-compatible service, shared by all backend/worker replicas. Use a TLS `rediss://` connection for a managed remote cache. Sessions and quotas must not use per-process memory in production. |
| Entra | Tenant ID, web application client ID, client secret/certificate policy, API audience, app-role assignments and the redirect URI below. External ID/custom authorities must supply issuer and JWKS overrides from their verified metadata. |
| Storage | Private Azure Blob container, managed/workload identity and least-privilege data access. The signing identity needs user-delegation SAS permission. Configure HTTPS-only access and GET/HEAD CORS for the exact frontend origin when using video captions. |
| Upload scanning | Private ClamAV `clamd` TCP endpoint. Set StreamMaxLength and scanner file/scan limits to at least the configured upload limit. Do not expose clamd publicly. Scanning failures block uploads. |
| AI | Institution-owned Gemini API key and an entitled model. Define budget alerts and shared quota monitoring. Neither the release nor the browser contains an API key. |
| Code execution | An authenticated HTTPS gateway to an isolated Piston-compatible service. Supported contract: POST `/api/v2/execute`, Bearer token, Python/JavaScript/Java/C++ runtimes. See the execution section. |
| Live video | Institution-owned self-hosted Jitsi or an approved Jitsi service. Set JITSI_BASE_URL, JWT app ID/secret and, if different, the XMPP JWT subject. The public meet.jit.si testing service is rejected by production validation. |
| Design/content | Approved Admiezo UI Kit revision, approved translations, real course material/recordings and exam question/paper distribution rights. These cannot be inferred from the SRS. |

## Entra registration and authorisation

1. Register a confidential web application. Add the exact redirect URI `https://YOUR_LMS_DOMAIN/api/lms/auth/entra/callback`. Configure the equivalent tenant-specific authority/issuer/JWKS values if using Entra External ID.
2. Define app roles with these exact values: Admin, Coordinator, Teacher, Reviewer, Author, TA, Librarian, Translator, Seller, Learner. Assign roles through the enterprise application. The app rejects identities without a recognised role; it does not default every directory user into LMS access. Multiple staff roles combine explicit capabilities; primary-role priority only controls display. Learner plus any staff role is rejected: use separate learner/staff identity contexts. Admin/Coordinator must also assign narrow staff to courses; an app role alone does not grant every course. See [the exact role setup and upgrade checklist](GO-LIVE-CHECKLIST.md).
3. Set ENTRA_API_AUDIENCE to the registered API audience for bearer tokens. Tokens require valid RS256 signatures, issuer, audience, expiry, tenant and object ID. Use directory-issued API tokens, not arbitrary ID tokens, for API clients.
4. Browser login uses MSAL's authorization-code flow with stored state/nonce/PKCE. Its resulting app session retains CSRF enforcement. Production password/demo login is disabled. Legacy local sessions without a federated binding are rejected.
5. Institution scope is server configuration INSTITUTION_ID and DEFAULT_CAMPUS, not an arbitrary browser field. Provisioning keys users by directory tenant and object ID. It never takes over an existing user solely because an email matches.
6. For a migrated real learner, review the database user ID and verified directory object ID, then run `python manage.py bind_entra_identity --user-id ID --object-id DIRECTORY_UUID --role Learner --confirm`. This keeps existing course/submission foreign keys and disables password login. Test on a restored staging copy first. Do not bind sample/demo accounts as real learner identities.

## Build and publish images

From the release root on a Linux CI builder:

```sh
docker build -t YOUR_REGISTRY/admiezo-backend:RELEASE ./backend
docker build --build-arg BACKEND_INTERNAL_URL=http://backend:8017 -t YOUR_REGISTRY/admiezo-frontend:RELEASE ./frontend
docker push YOUR_REGISTRY/admiezo-backend:RELEASE
docker push YOUR_REGISTRY/admiezo-frontend:RELEASE
```

Record registry-returned digests in LMS_BACKEND_IMAGE and LMS_FRONTEND_IMAGE. `release.sh` requires `@sha256:` digests, so a mutable `latest` tag cannot silently change the application. BACKEND_INTERNAL_URL is a frontend build argument for the Next.js API rewrite and a runtime value for server-side certificate verification; rebuild when changing that private service address.

Review/pin base-image digests and scan the final images according to the institution's supply-chain policy. The source manifest records file hashes; it is not a container-signing or vulnerability-attestation claim.

## Execution service

Run the execution provider on a separate hardened worker host or isolated infrastructure tier. Do not mount the Docker socket or host directories into the Django application. Do not execute learner source directly on the LMS host.

The adapter sends the selected language, main source filename, standard input, a 10-second compile timeout, a 3-second execution timeout, 256 MiB compile memory and 128 MiB run memory. It rejects compile failures, signals, nonzero exits, invalid provider payloads and output beyond 20,000 characters. The provider/gateway must enforce its own global queue, CPU/process/filesystem/network limits and authentication. Install approved runtime versions and record them as release infrastructure configuration. Runtime version selection currently requests the installed compatible version (`*`); pin the provider's installed runtimes for reproducibility.

Production never falls back to the development AST teaching interpreter. Verify a function-based Python program, a JavaScript program, Java compilation and a C++ compilation; verify runaway loops and network/file access are constrained by the provider. A successful `print(2+3)` smoke test alone is not an isolation/security audit.

## Jitsi configuration

Use JWT authentication with matching app ID/secret, reject empty/unauthenticated tokens, disable automatic owner assignment, and configure the token-affiliation/moderation policy supported by the selected Jitsi version. The app issues short-lived room-specific tokens and marks only authorised teaching/admin roles as moderators. JWT claims alone do not prove the server enforces moderator permissions: explicitly test a learner cannot become moderator or enter another room.

Configure recording/caption services, retention, consent and network/UDP requirements on the Jitsi side. The application does not silently create provider contracts or enable microphone/camera permissions. Test actual video and leave/attendance flows in the target browser.

## Deploy and validate

1. Restore a recent data backup to staging. Run all tests there against PostgreSQL 16, including concurrent enrolment/credential/attempt submissions. Validate that the new schema and older answers retain their meaning.
2. Establish and test the private services above. Confirm the Blob container has public access disabled; confirm unapproved/private files cannot be obtained through an LMS route.
3. From an IT-managed Linux host run `bash deploy/release.sh`. It validates Compose/image digests and production environment, stops application writers for a planned maintenance window, creates a pre-migration PostgreSQL custom-format backup, applies all fourteen migrations, reconciles derived question evidence with `rebuild_question_evidence`, starts services, and runs database/cache/execution/General-AI/Lesson-AI/blob-storage smoke tests.
4. Copy the pre-migration backup to the institution's encrypted backup vault. Configure scheduled backups/PITR and perform a restore drill. Keep backups and `.env.production` out of source control and public storage.
5. Complete browser checks for every role, cross-course and cross-campus denials, SSO callback failures, cookie/CSRF behavior, all 25 modules, private study groups, rubric totals, choice/multiple/numerical scoring, resumption/timer expiry, upload scanning, large video seeking/captions and certificate QR/revocation.
6. Check Hindi/Kannada labels with your language reviewers. Authored lesson content is translated through its review workflow and is never changed by interface localisation. English is the fallback for a missing UI catalogue entry.
7. Perform keyboard/focus, screen-reader, mobile, load and security reviews. Obtain the required business/UX/QA sign-off from the SRS/LLD owners before production learner access.

## Rollback and recovery

Keep the prior immutable application image digests and environment revision. Migrations in this release are additive. If application rollout fails, stop the new worker, restore prior image references and restart the prior application while preserving the database. Do not edit applied migrations or automatically drop columns/tables. Older images do not understand the new narrow roles: a rollback is not authorization-compatible without IT review. Quiesce writers, review old-version permissions, and reconcile question evidence after upgrading again; follow GO-LIVE-CHECKLIST.md.

For corrupt data or an incompatible release, stop writes, restore the verified PostgreSQL backup/PITR point into a replacement database, restore matching Blob versions and switch configuration after validation. Restoring overwrites data created after the backup, so IT must assess and approve that recovery step. The release script never deletes or resets a database.

## Evidence and limits

Unit/integration-style tests run on the authoring machine cover authentication contracts, configuration failure behavior, scoring, access rules, storage/scanner adapters and existing module workflows. Mocks do not constitute live Entra/Azure/Piston/Jitsi proof. Container execution, PostgreSQL concurrency, TLS/DNS, actual identity consent, provider cost controls, recording, accessibility and infrastructure recovery remain the IT acceptance gates.

Official references: [Microsoft identity code samples](https://learn.microsoft.com/en-us/azure/active-directory/develop/web-api), [Azure user-delegation SAS](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-user-delegation-sas-create-python), [Jitsi self-hosting](https://jitsi.github.io/handbook/docs/devops-guide/devops-guide-docker/), [Piston source and API](https://github.com/engineer-man/piston), [Docker security](https://docs.docker.com/engine/security/), [ClamAV documentation](https://docs.clamav.net/).

## Mandatory configuration sign-off

Use [GO-LIVE-CHECKLIST.md](GO-LIVE-CHECKLIST.md) as the release 0.3.1 input sheet. It lists exact environment keys, ten Entra role values, course assignments, maintenance/migration steps and live acceptance gates. Neither this runbook nor passing local tests authorizes opening production access before these checks.
