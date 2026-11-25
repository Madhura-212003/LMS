# IT go-live configuration — release 0.3.1

This is the deployment input sheet for the IT team. The application has not been deployed to an institution environment. Complete the configuration below in staging, retain the test evidence, then use the approved release procedure for production. Source SRS/LLD approval, real content, UI/language/accessibility acceptance and live provider checks remain separate gates.

## 1. Infrastructure and exact environment values

Copy `.env.production.example` to `deploy/.env.production` on the deployment host. Store actual secrets in the institution secret manager and inject them into this private file or the equivalent deployment environment. No production credentials are included in the ZIP. Keep this file private, outside source control; the supplied deployment script uses file permissions restricted to the operator.

| Configuration | IT must supply | Check before production access |
| --- | --- | --- |
| Linux runtime | Docker Linux engine, Compose, image registry and approved Python 3.13 / Node 22 container builds | Build both images in Linux CI, scan them and run the staging suite. Host-machine SQLite checks are not PostgreSQL/container proof. |
| Release images | `LMS_BACKEND_IMAGE`, `LMS_FRONTEND_IMAGE` as registry references ending in `@sha256:...` | `release.sh` rejects mutable application image tags. Pin/review infrastructure and base images according to institution policy. |
| Domain/TLS | `LMS_DOMAIN`; `PUBLIC_APP_URL=https://your-real-domain` as an origin; matching `DJANGO_ALLOWED_HOSTS` including `backend,localhost,127.0.0.1` | DNS resolves to the edge, HTTPS certificate is valid, only edge ports 80/443 are public. API/frontend ports remain private. |
| Django | `LMS_ENV=production`, `DJANGO_DEBUG=0`, unique random `DJANGO_SECRET_KEY` of at least 50 characters | Production startup fails when required configuration is missing. Check HTTPS cookies, CSRF and sign-out. |
| Institution/campus | Stable `INSTITUTION_ID`, `DEFAULT_CAMPUS`, `LMS_TIME_ZONE` | Configure one institution/campus context for this deployment. Verify real migrated records carry that same scope. Use separate database/cache contexts for independent campus deployments. |
| PostgreSQL | `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SSLMODE=require` or verified TLS mode | PostgreSQL **16**, private connectivity, deployment/migration privileges, backups/PITR and successful restore drill. Confirm the CA/client configuration if using `verify-full`. |
| Redis | `REDIS_URL` for a private shared Redis-compatible service; use `rediss://` with the correct credentials/certificate trust for managed remote service | All backend/worker replicas share sessions and quotas. Database/cache health and multi-replica session behavior pass. Cache keys include institution and campus. |
| Entra | Values in section 2 below | Each approved role can sign in; no-role/wrong-tenant/wrong-audience users are rejected. |
| Azure Blob | `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_CONTAINER` and a compute managed/workload identity; standard `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` only if using a dedicated service principal instead | Container public access disabled; application can upload/read/sign/delete its test blob. A nonenrolled learner cannot retrieve another learner's private file. |
| Antivirus | Private `CLAMAV_HOST`, `CLAMAV_PORT`; `MAX_UPLOAD_BYTES` (default 536870912, 512 MiB) | Configure scanner stream/file/scan limits so accepted files are actually scanned. Test a clean upload, an oversized upload, a scanner outage and an institution-approved antivirus test fixture. Uploads fail closed on scanner error. |
| AI | `AI_PROVIDER=gemini`, institution-owned `AI_API_KEY`, entitled `AI_MODEL` | One real General and one real Lesson request; quota/budget alerts and lesson-data processing approval. Provider key remains server-side. |
| Execution | `EXECUTION_SERVICE_URL` as HTTPS base URL, `EXECUTION_SERVICE_TOKEN`; hardened isolated Piston-compatible gateway | `/api/v2/execute` accepts the configured Bearer token. Install/pin Python, JavaScript, Java and C++ runtimes. Test all four, timeout/output limits and isolation. Production does not use the development interpreter. |
| Jitsi | Institutional `JITSI_BASE_URL`, `JITSI_JWT_APP_ID`, `JITSI_JWT_SECRET`; optional `JITSI_JWT_SUB` matching the configured XMPP/JWT subject | Enforce room tokens and the approved moderator/affiliation policy. Test learner denial of moderation/other rooms. Public `meet.jit.si` is rejected in production configuration. |
| Content and design | Approved UI Kit revision, reviewed labels/translations, real learning media/captions and licensed exam content | Replace original sample learning material with institution-approved content; obtain UX, language, accessibility and QA sign-off. |

The supplied Caddy body limit is 550,000,000 bytes, providing multipart overhead above the default 512 MiB file limit. Keep edge, Django upload and scanner limits consistent when changing `MAX_UPLOAD_BYTES`. Test seeking/resuming a long private lecture after the five-minute signed URL lifetime.

For Azure signing, the identity needs data access plus the `Microsoft.Storage/storageAccounts/blobServices/generateUserDelegationKey` action at an appropriate storage-account scope. A container-only data grant does not itself establish account-level signing permission. Use approved RBAC grants and verify signing from inside the backend container. See [Microsoft's delegation-SAS guidance](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-user-delegation-sas-create-cli).

## 2. Entra registration and role assignment

1. Register the institution web/API application. Set the exact web redirect URI to `https://YOUR_DOMAIN/api/lms/auth/entra/callback`.
2. Set `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET` and `ENTRA_API_AUDIENCE`. The audience must match access tokens issued for this API. Browser authentication uses the web application; API integrations use API access tokens.
3. For Entra External ID/custom authorities, provide `ENTRA_AUTHORITY`, `ENTRA_ISSUER` and `ENTRA_JWKS_URL` from that directory's verified metadata. Check issuer, audience, tenant/object ID, signatures and expiry in staging.
4. Define the exact app-role **values** below. [entra-app-roles.json](entra-app-roles.json) is a merge template, not a replacement for the whole application manifest. **Retain existing role IDs and assignments when the values already exist.** Add missing values; do not recreate existing roles merely to match template GUIDs. Microsoft describes definition/assignment and token claims in its [app-role guide](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps).
5. Assign approved people/groups through the enterprise application. Bootstrap a real institution Admin through Entra, then sign in. There is no seeded production administrator or production password login.

| App-role value | Application authority |
| --- | --- |
| `Admin` | Institution/campus-wide LMS administration. |
| `Coordinator` | Courses, cohorts, rosters, schedules, course-staff assignments and teaching reports; assessment/content authoring and marking remain separate permissions. |
| `Teacher` | Full teaching authority in assigned courses, including authoring, review, assessments and marking. |
| `Author` | Assigned-course lesson drafts and submission for review; approval/publication requires review authority. |
| `Reviewer` | Assigned-course content review/approval/publication and translation approval; draft authorship requires author authority. |
| `TA` | Assigned-classroom assistance and marking/re-evaluation of assigned learner work; assessment authoring and staff management are separate. |
| `Librarian` | Campus library resources/loans; private learner work is excluded. |
| `Translator` | Assigned-course translation submission and glossary editing; translation approval requires review authority. |
| `Seller` | Own course/marketplace management; settlement remains preview-only. |
| `Learner` | Own enrolled learning, submissions, results and credentials. |

Staff app roles can combine their explicit capabilities; a combination such as Author + Reviewer does not become Teacher or gain marking/staff management. The primary display role follows the priority in `permissions.ROLES`. **Use a separate Learner identity for learner journeys:** mixing `Learner` with staff/seller/library roles is rejected to keep the SRS learner/staff login contexts unambiguous.

Existing Teacher accounts retain Teacher authority. IT must review each real person's directory assignment and select Author, Reviewer or TA where that narrower job is intended; the application does not infer a person's job from existing content ownership.

## 3. Course access after sign-in

An Entra app role grants an action category. It does not assign a course.

1. Have the real staff identity sign in once so its directory tenant/object binding and profile exist.
2. As Admin or Coordinator, open **Learning workspace → Course staff**, choose the course and staff member, and assign access. Author, Reviewer, TA and Translator queries then see that assigned course. Grants/revocations are audited.
3. Existing course ownership and cohort-teacher links remain independent assignment sources. When transferring responsibility, review those links as well; revoking a secondary staff-assignment row alone does not remove an owner/cohort-teacher grant.
4. Enrol learners using the course/cohort roster (or the institution's approved Admission/ERP integration). A learner app role without an active enrolment does not permit learner work submission.
5. Test an unassigned Author/Reviewer/TA/Translator, then assign, test the approved action, revoke and test denial again. Include another course, another campus and another learner's private file/results.

For existing real accounts, use `bind_entra_identity --user-id ID --object-id VERIFIED_DIRECTORY_UUID --role ROLE --confirm` only after reviewing the identity mapping. It retains record IDs and disables local password login; directory app-role assignment remains an Entra administrative step. Test real data migration and institution/campus mapping on a restored staging copy. Sample accounts are not production identities.

## 4. SQL list contract and client configuration

No external list service or browser data store is required. Interactive catalogues, rosters, queues and report tables use ORM-backed search/filter/sort and signed keyset cursors with a fixed **20-record page**. The cursor is bound to the user, roles, institution/campus, route, filters and sort; scope is checked again on every request.

- Existing catalogues/supporting routes accept `list_page=1`, `cursor`, `q`, `status`, `sort` and their documented domain filters. New `/api/lms/lists/{list_name}` routes return this contract directly.
- Response: `items`, `total`, `next_cursor`, `previous_cursor`, `page_size`, permitted `sort_fields`, `statuses`, `status_label` and catalogue facets.
- Use returned cursor strings unchanged. Changing filters/sort/user requires starting from the first page. Cursors expire after one hour; the UI provides First page recovery.
- No SQL `OFFSET` is used in this paged contract. Search/filter/sort/aggregates run before the database page limit. Finite rubric/code-test/answer arrays embedded inside a detail remain presentation tables rather than independent record catalogues.
- Legacy array/page contracts remain for older clients/selection controls during migration. They are not the interactive list implementation. Move institution API clients to the paged contract; the `_search/_status/_sort` aliases from 0.2.1 remain accepted.
- Disable public/CDN caching of `/api/lms/*`. Application responses already set `private, no-store` and vary by Cookie/Authorization. Preserve those headers at the edge.
- Run PostgreSQL 16 query-plan/load checks with representative volumes. Confirm stable next/previous pages for duplicate/null sort values, changed filters, expired/tampered cursors and revoked grants.

## 5. Deploy, verify and release access

Use [IT-HANDOFF.md](IT-HANDOFF.md) for image build commands, execution-host isolation and Jitsi details. On a staging restore first:

```sh
bash deploy/release.sh
```

The script validates immutable image references and configuration, stops application writers for the maintenance window, takes a PostgreSQL backup, applies **14 additive migrations**, reconciles derived question evidence, starts the services and runs live service smoke checks. Backfill/index timing depends on real data volume; measure the maintenance window in staging.

Retain evidence for all of these before approving learner access:

- Backend and frontend tests pass in the Linux/PostgreSQL staging environment. Concurrent enrolment/waitlist, quiz expiry/submission and credential awards pass.
- All ten roles pass sign-in/navigation and API positive/negative tests, including wrong tenant/campus, unassigned courses, revoked grants, conflicting learner/staff roles and private files/answers.
- Real General/Lesson AI, private Blob upload/download/signing, scanner blocking, four execution languages, Jitsi video/moderation, long-video seek/resume/captions and certificate QR/revocation work.
- Worker process stays running and finalises timed-out attempts with the browser closed. Health readiness is monitored; provider failures and certificate/secret expiry have named operational owners.
- Backups/PITR, Blob retention/versioning, restore drill, alerting, logs, security/load checks, accessibility and language/content/UX approvals are complete.

`deployment_check --live-services` checks PostgreSQL 16, Redis, Python execution, General/Lesson AI and a Blob round-trip. It does **not** certify Entra consent/roles, Jitsi moderation, antivirus limits, all execution runtimes or accessibility; the checks above cover those remaining gates.

Rollback uses prior immutable images with the preserved database. Older images do not understand the new narrow roles. Preserve those directory grants during recovery and fix forward; expanding people to Teacher to compensate is not the rollback procedure. After an older writer has run, the next 0.3.1 rollout reruns `rebuild_question_evidence` so reporting catches up without changing saved answers/scores. Do not edit applied migrations or drop learner data.
