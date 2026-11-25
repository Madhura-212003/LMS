# Release 0.3.1 verification

## Backend checks

- `python manage.py test lms --verbosity 1`: **94 passed** on Python 3.11 / Django 5.2.19 / SQLite.
- Django system check: no issues. `makemigrations --check --dry-run`: no changes.
- Fourteen additive migrations applied locally after a database snapshot. MigrationExecutor regression verifies historical question-evidence backfill preserves original answers, scores and references. Reconciliation command idempotency is tested.
- Role tests cover separate Author/Reviewer/TA permissions, combined staff roles, mixed learner/staff denial, scoped grants/revocations, inactive staff, translator review separation, private file reuse denial, submitted-answer/certificate privacy and TA classroom moderation.
- List tests cover SQL filtering/sorting before LIMIT, stable ties, reverse and nullable sorting, no OFFSET, signed cursor binding/tampering/revocation, started-path filtering, report plans and private cache headers. Existing domain/authentication/production adapter suites also pass. Provider responses are mocked without institution accounts.

## Frontend and browser checks

- `npm test`: **8 role-navigation tests passed**.
- `npm run build`: passed including TypeScript and standalone output. Windows traced-file copying required normal filesystem access after restricted EPERM errors.
- Latest migrated preview: Teacher Feedback list showed relevant search/status/sort/paging; Admin Course staff screen loaded real courses and eligible staff directory with separate assigned-staff list and owner/cohort-teacher warning. No security grants/revocations were executed in the browser. Screenshot: qa/role-list-review-0.3.0.jpg.
- Prior 0.2.1 evidence under qa covers distinct headings on all 25 primary module routes; it is historical, not a fresh action-by-action certification of this build. Latest role/list actions have automated regression proof.

## Deployment checks

- Compose example configuration validation and release.sh Bash syntax passed.
- Linux Docker engine was unavailable. No container build/run, PostgreSQL concurrency or real cloud/provider deployment is claimed.
- Release archive integrity and all manifest file hashes are verified by the packager. Source, locks, fourteen migrations, tests, exact environment examples, Entra role template, configuration checklist and runbooks are included. Actual secrets, learner database, uploads, snapshots and dependency/build caches are excluded.

## IT acceptance still required

Follow deploy/GO-LIVE-CHECKLIST.md and deploy/IT-HANDOFF.md: real Entra role assignment/course grants, Linux Python 3.13 images, PostgreSQL 16 plans/load/concurrency, Redis, private Blob/scanner, all execution runtimes, Gemini, Jitsi enforcement, backups/restore, monitoring, licensed content, approved UI Kit, language and accessibility acceptance. Passing local tests does not certify every SRS condition or live integration.

## Final role/module pass

See [FINAL-END-TO-END-CHECK.md](FINAL-END-TO-END-CHECK.md) for 250 primary browser checks, 166 allowed secondary tabs, every-role authorized API actions, the author/reviewer/learner browser write workflow and the fixes verified in this pass. Current gates: 94 backend tests, 8 frontend tests and production build passed. Earlier screenshot/module evidence remains historical.


## F156 connected course workflow — 25 November 2026

- `python manage.py test lms --noinput`: 98 tests passed, including four new isolated course/enrolment lifecycle tests.
- `python manage.py check`: passed.
- `python manage.py makemigrations --check --dry-run`: no changes detected; no schema migration or demo-data update.
- `npm test`: nine tests passed, including F156 capability-based navigation coverage.
- `npm run typecheck`: passed after the final UI refinements.
- `npm run build`: production compilation and route generation passed. The existing warning about the unrelated home-directory package-lock remains.
- Native Chrome inspection: learner My courses and Course catalogue render the existing database records, cohorts, enrolment badges and saved progress without the earlier configuration error. Learner navigation omits staff management pages. Staff writes and teaching metrics are covered by the API lifecycle tests; no live learner records were changed for verification.

See [Courses and enrolment](COURSES-AND-ENROLMENT.md) for metric definitions, refresh behavior, preserved scope boundaries and proposed follow-up work. Deployment ZIPs/checksums were not rebuilt.


### F156 navigation follow-up — 25 November 2026

The complete six-screen flow is returned by the server in the requested order with primary-role labels and per-account accessibility. Learners can see the staff destinations as disabled navigation; staff forms and server authorization remain protected. Notifications and Course staff are supporting links. Five focused backend workflow tests and eleven frontend navigation/render tests passed, including screen order, audience labels, disabled staff steps and unchanged denial of learner course creation. TypeScript checks and the production build passed.


## F158 Digital library workflow — 25 November 2026

- `python manage.py test lms --noinput`: 106 tests passed, including four new library workflow tests for publication/read/save/borrow/return, configurable due dates, idempotency, withdrawn-loan redaction/return, reader scope and the ordered manifest.
- `npm test`: 13 tests passed, including the five-page order and Librarian capability gates.
- `npm run build`: production compilation, TypeScript checks and route generation passed; the existing home-directory package-lock warning remains.
- Django system checks passed; `makemigrations --check --dry-run` reported no changes.
- Verification used isolated test data and did not add library resources or change loans in the local learner database. Native browser verification was not performed for this pass.

See [Digital library](DIGITAL-LIBRARY.md) for navigation routes, policy configuration, permission details and synchronization limits.


## F159 Live Class Management — 25 November 2026

- `python manage.py test lms --noinput`: 110 tests passed, including four new live workflow tests for explicit join/private-room access, persisted discussion/hand/leave/resume, single-row attendance and correction, TA assistance without scheduling, cohort/time isolation, cancellation reporting and closed-room actions.
- The older TA scheduling expectation was updated to denial (403) to implement the requested Teacher/Coordinator/Admin schedule-management split. Existing TA/JWT moderation coverage remains passing.
- `npm test`: 14 tests passed, including the ordered four-page flow and separate Learner/TA versus scheduling gates.
- `npm run build`: production compilation, TypeScript checks and route generation passed. The existing warning about the unrelated home-directory package-lock remains.
- Django system checks passed; `makemigrations --check --dry-run` reported no changes.
- HTTP smoke check for `/lms/159/Class%20schedule%20%2F%20Manage` returned 200. No native browser or external Jitsi audio/video verification was performed.
- Backend restarted with the updated routes. No local learner schedules, attendance or discussion records were seeded for verification.

See [Live Class Management](LIVE-CLASS-MANAGEMENT.md) for room-entry semantics, role-policy changes, configurable late/poll intervals, provider limitations and synchronization behavior.


## F160 Recorded Lecture Management — 25 November 2026

- `python manage.py test lms --noinput`: 114 tests passed, including four new lecture workflow tests for staff role authorization, draft/publication visibility, player details, notes-preserving playback saves, sticky completion, unpublishing, unrelated-account denial and video replacement protection.
- `npm test`: 17 tests passed, including the requested three-page navigation, TA lecture scope without assessment escalation, save-ordering and retry after a failed request.
- `npm run build`: production compilation, TypeScript checks and route generation passed. The existing home-directory package-lock warning remains.
- Django system checks passed; `makemigrations --check --dry-run` reported no changes.
- HTTP smoke check for the encoded Lecture Upload / Edit / Publish route returned 200. Backend restarted with the updated routes/capabilities.
- Media/API fixtures were isolated in temporary test storage; no local learner recordings or progress were seeded. Real codec playback, caption rendering, browser seeking and production signed-media delivery were not browser-verified.

See [Recorded Lecture Management](RECORDED-LECTURE-MANAGEMENT.md) for authoring/publication, player progress/notes, new role capability and deployment limits.


## F161 Learning Path Management — 25 November 2026

- `python manage.py test lms --noinput`: 120 tests passed, including six new path workflow tests for Coordinator authoring, actual lesson/quiz/lab/course completion, teacher-report alignment, explicit/idempotent starts, server prerequisite denial, stable started-path structure, metadata edits, duplicate/unpublished reference rejection, cross-course/foreign scope, paginated options and exact all-lesson course completion.
- `npm test`: 18 tests passed, including the requested four-page order and dedicated Coordinator path capability without assessment escalation.
- `npm run build`: final production compilation, TypeScript checks and route generation passed. The existing home-directory package-lock warning remains.
- Django system checks passed; `makemigrations --check --dry-run` reported no changes.
- HTTP smoke check for Path Catalogue / Search returned 200; backend restarted with the new routes and permissions.
- Verification used isolated test records and did not seed local learner paths or work. Native browser interaction was not performed.

See [Learning Path Management](LEARNING-PATH-MANAGEMENT.md) for reference/publication rules, path-context prerequisites, actual activity links, start/completion semantics, reports and synchronization limits.

## F162 Personalised Learning Management — 25 November 2026

- `python manage.py test lms --noinput`: 126 tests passed, including six new personalisation tests for partial preference saves, self scope, goal ranking/pace limits, exact discussion access, latest assessment evidence, configurable review boundaries, current cohort completion, notification preferences and role navigation.
- `npm test`: 19 tests passed, including the requested three-page order and learner/staff/settings access.
- `npm run build`: production compilation, TypeScript checks and route generation passed. The existing unrelated home-directory package-lock warning remains.
- Django system checks passed; `makemigrations --check --dry-run` reported no changes.
- Backend restarted with the new endpoints. HTTP smoke check for `/lms/162/Learner%20what%20next` returned 200.
- Tests used isolated records; no local learner preferences, notifications or work were seeded. Native browser interaction was not performed.

See [Personalised Learning Management](PERSONALISED-LEARNING-MANAGEMENT.md) for recommendation rules, settings behaviour, report scope and synchronization limits.

## F163 AI Tutor Management — 25 November 2026

- `python manage.py test lms --noinput`: 131 tests passed, including five new tutor tests for role/capability scope, Coordinator policy/review, phrase normalization, provider policy checks, Published lesson grounding, private learner flags and saved review return, unauthorized course/publication access and provider errors.
- `npm test`: 20 tests passed, including the requested three-page order and separate learner/review/policy access.
- `npm run build`: final production compilation, TypeScript checks and route generation passed. The existing home-directory package-lock warning remains.
- Django system checks passed; `makemigrations --check --dry-run` reported no changes.
- Backend restarted. Live health, AI Tutor Chat and encoded Tutor Policy / Settings HTTP routes returned 200; unauthenticated workflow access correctly returned 401.
- AI calls were mocked in isolated tests. No real-provider request or native browser interaction was performed, and no local learner flags/policies were seeded.

See [AI Tutor Management](AI-TUTOR-MANAGEMENT.md) for permissions, policy matching, chat retention and flagged-answer review semantics.

## F164 Multilingual Learning Support — 25 November 2026

- `python manage.py test lms --noinput`: 135 tests passed. Four new multilingual tests cover manifest audiences, saved language/preference preservation, translator/reviewer separation, Coordinator workflow, learner original fallback, approval/re-submission, source-edit invalidation, stale source/approval checks, scoped glossary filtering and Published-only coverage.
- The four multilingual tests were rerun after adding the translation-save timestamp conflict check; all passed.
- `npm test`: 21 tests passed, including the requested four-page order and role access.
- `npm run build`: final production compilation, TypeScript checks and route generation passed. The existing home-directory package-lock warning remains.
- Django system checks passed; `makemigrations --check --dry-run` reported no changes.
- Backend restarted. Health and the translated-content/encoded translation-editor HTTP routes returned 200; unauthenticated workflow access returned 401.
- Verification used isolated test data without seeding local translations or preferences. Native browser interaction was not performed.

See [Multilingual Learning Support](MULTILINGUAL-LEARNING-SUPPORT.md) for source invalidation, approval, role scope, language selection and synchronization limits.


## Repeated-screen navigation correction — 25 November 2026

- Course-reader and quiz overlay state now belongs to a particular route visit and signed-in account. A delayed response from an earlier visit cannot replace the currently selected screen, including after navigating away and back.
- Resource Reader and Learner Lecture Player have distinct entry screens when no resource/recording is selected, instead of repeating their catalogue grids.
- `npm test`: 24 tests passed, including three asynchronous navigation-scope regressions. `npm run build`: production compilation, TypeScript and route generation passed.
- Browser automation was unavailable, and native browser interaction rejected input; end-to-end clicking was not verified. This correction does not certify that every module is visually distinct or fully browser-tested. No backend/schema/business-record changes were made.


## Render shared-demo preparation — 25 November 2026

- Added a separate `LMS_ENV=demo` profile with validated hosts/origin, strong secret, HTTPS proxy handling, secure cookies, PostgreSQL TLS and an explicit media root. Institutional production validation remains separate.
- Added a root Render Blueprint for a paid backend, PostgreSQL 16 and persistent media disk; no resources were created or billed. Added a deployment guide and explicit shared-demo UI badge.
- `python manage.py test lms --noinput`: 138 tests passed, including three demo-configuration tests. The nearest production/configuration gate passed all 16 tests.
- `npm run build`: production compilation, TypeScript and route generation passed. `makemigrations --check --dry-run`: no changes.
- The Blueprint was not submitted to Render or validated by its API/CLI. Linux/Python 3.13 dependency installation, PostgreSQL/Render integration and hosted browser flows remain unverified. Local records, credentials and uploads were not exported or seeded remotely.
- This workspace is not a Git repository. Publishing still needs an approved repository destination and Render account access; paid resource selection must be reviewed before applying the Blueprint.

See [Render shared demo](../deploy/RENDER-DEMO.md).
