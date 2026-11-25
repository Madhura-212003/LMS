# Admiezo Learning Management

Release 0.3.1: Next.js/React/TypeScript/MUI and Django Ninja project spanning all 25 Section F modules, with a production deployment package. Every module has relevant domain screens and persistent actions. See [feature coverage](docs/FEATURES.md) for exact implemented workflows and remaining production/SRS differences.

See [final SRS/LLD review](docs/FINAL-SRS-LLD-REVIEW.md) for all 93 feature requirement mappings, corrections and acceptance limits.

## IT deployment

For a separate password-login shared demo on Render, see [Render demo deployment](deploy/RENDER-DEMO.md). The root Blueprint provisions paid services only when applied; it has not been deployed.

Start with the [go-live configuration checklist](deploy/GO-LIVE-CHECKLIST.md), then [IT handoff](deploy/IT-HANDOFF.md). See [roles and list design](docs/ROLES-AND-LISTS.md). It covers Entra, PostgreSQL, Redis, private Azure Blob storage, ClamAV, isolated execution, institutional Jitsi, Gemini, immutable containers, backup, migration, rollback and acceptance. Supply institution-owned endpoints/secrets outside source control. Production fails closed when required services are missing. No live deployment has been performed.

## Run on Windows

Requirements: Node.js 20.9+ and Python 3.11+. The LLD production runtime targets Python 3.13 and PostgreSQL 16.

Backend terminal:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_demo
.venv\Scripts\python manage.py seed_features
.venv\Scripts\python manage.py runserver 127.0.0.1:8017
```

The seed command prints generated passwords for newly created local accounts. Existing users/passwords are preserved. Accounts include student@admiezo.demo, teacher@admiezo.demo, admin@admiezo.demo, librarian@admiezo.demo, coordinator@admiezo.demo, translator@admiezo.demo and seller@admiezo.demo. Set LMS_DEMO_PASSWORD in the terminal before seeding to choose an initial password. No fixed account password is committed.

Frontend terminal:

```powershell
cd frontend
npm ci
npm run build
npm run start
```

Use `npm run dev` during development. Open http://127.0.0.1:3000. The frontend proxies API requests to port 8017 with same-origin session cookies and CSRF protection. API docs: http://127.0.0.1:8017/api/lms/docs.

Quiz expiry worker in a third terminal, from backend:

```powershell
.venv\Scripts\python manage.py expire_attempts --watch
```

The worker finalises expired attempts every five seconds, even if the browser is closed. API handlers independently reject late answers. Without --watch the command performs one sweep, suitable for a scheduler.

For the updated F156 screens and their connected lifecycle, see [Courses and enrolment](docs/COURSES-AND-ENROLMENT.md).

For the four-page author/reviewer/learner content workflow, see [Learning content](docs/LEARNING-CONTENT.md).

For the five-page resource and loan workflow, see [Digital library](docs/DIGITAL-LIBRARY.md).

For staff scheduling, room entry and attendance, see [Live Class Management](docs/LIVE-CLASS-MANAGEMENT.md).

For recording uploads, publication and saved playback, see [Recorded Lecture Management](docs/RECORDED-LECTURE-MANAGEMENT.md).

For ordered learning activities and progress reporting, see [Learning Path Management](docs/LEARNING-PATH-MANAGEMENT.md).

For saved learning preferences, next steps and class evidence, see [Personalised Learning Management](docs/PERSONALISED-LEARNING-MANAGEMENT.md).

For course-grounded chat, flagged-answer review and course policies, see [AI Tutor Management](docs/AI-TUTOR-MANAGEMENT.md).

For language preferences, approved translations and terminology coverage, see [Multilingual Learning Support](docs/MULTILINGUAL-LEARNING-SUPPORT.md).

## Try the workflows

- Student: borrow/read a resource, join an in-time class, watch an uploaded lecture, start a path, save goals/language, discuss an activity, complete skills, run/submit code, save a lab notebook, submit speaking/writing/career practice, attempt a dedicated exam pack, verify credentials and preview marketplace enrolment.
- Teacher: create/edit/publish content, review drafts/translations, author assignments and quizzes, reuse bank questions, mark/re-evaluate, inspect participation/results, define credential rules, schedule classes, upload recordings and post announcements.
- Admin/librarian: manage resource text or real uploaded documents, review usage/overdue loans, and manage institution records.

Sample material is original demonstration content. Upload real videos, captions and licensed previous-year papers through management screens. Empty lists represent absent records, not a placeholder implementation.

## AI configuration

Copy backend/.env.example to backend/.env. Set AI_PROVIDER=gemini, AI_MODEL to an available model, and AI_API_KEY. Config reloads on every request; environment variables override the file. Keys stay on the server. General/lesson requests do not store chat history; only explicitly flagged excerpts are retained for teacher review. A valid key is required for real generation; no simulated answer is returned when config is missing.

## Live classes and execution

Production classrooms require institutional Jitsi and room-scoped JWT authentication. Development can use public Jitsi for review. Chat, attendance and hand raising persist independently. Provider moderation, recording and captions require IT configuration and live verification.

Production code/lab execution supports Python, JavaScript, Java and C++ through the authenticated Piston-compatible adapter. Deploy it on an isolated execution host as described in the handoff. The bounded Python teaching subset is a development-only fallback.

## Data and deployment

- Local progress: backend/db.sqlite3. Uploads: backend/media. Both are ignored by source control. Preserve both when retaining learner work.
- PostgreSQL selection: set POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST and POSTGRES_PORT, then migrate. PostgreSQL concurrency still needs integration verification.
- Certificate QR links use PUBLIC_APP_URL on the backend, default http://127.0.0.1:3000, followed by /verify/<code>. Public verification is local until deployed.
- Production includes Entra OIDC/JWT, shared Redis sessions/cache, private signed Blob downloads, antivirus scanning and HTTPS container configuration. IT provisions the services and performs live acceptance; approved UI theme review remains outstanding.
- Marketplace payments are preview-only as required by the source scope.
- Fourteen append-only Django migrations describe the current schema. Do not rewrite already applied migrations.

## Verify

```powershell
cd backend
python manage.py test lms
python manage.py check
python manage.py makemigrations --check --dry-run
```

```powershell
cd frontend
npm run typecheck
npm run build
```

See docs/VERIFICATION.md for executed checks. The original Word documents remain unchanged; extracted text is under docs/.

References: [Next.js](https://nextjs.org/docs/app/getting-started/installation), [Django Ninja authentication](https://django-ninja.dev/guide/authentication/), [Jitsi iframe API](https://jitsi.github.io/handbook/docs/dev-guide/dev-guide-iframe/), [Jitsi service limits](https://jitsi.org/api/), [Jitsi moderator sign-in](https://jitsi.github.io/handbook/docs/user-guide/user-guide-join-jitsi-meeting/).

Final handoff verification: [25-module / ten-role check](docs/FINAL-END-TO-END-CHECK.md). Use the 0.3.1 ZIP and checksum; it supersedes the earlier archives.
