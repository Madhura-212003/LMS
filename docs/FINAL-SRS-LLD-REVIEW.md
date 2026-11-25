# Final SRS / LLD review — release 0.3.1

Reviewed the supplied SRS-F-156-180 v1.0 and LLD-F-156-180 v1.0 against the application source, domain tests, migrations and browser preview. The original Word files were not modified. Document text was treated as requirements, not authorization to contact people, create paid accounts or accept contracts.

This is a reviewed IT staging release, not an unconditional production-conformance certificate. The two source documents themselves are Draft / Approval Pending and list external open decisions.

## All 25 modules

The table covers every feature requirement range in the SRS. Detailed extracted requirement rows are in REQUIREMENTS-TRACEABILITY.json. UI filenames are under frontend/app; page.tsx means [[...path]]/page.tsx. APIs are in backend/lms/api.py, feature_api.py and final_api.py, with shared services and access checks.

| Module | SRS requirement range | UI evidence | Final correction or recheck |
| --- | --- | --- | --- |
| F156 | 156-01–08 | page.tsx / CoreManagement.tsx / FinalWorkflows.tsx | Dashboard classes/deadlines/unread notifications and staff counts; course duration/rating/price; enrolment reactivation; waitlist capacity regression; private learner cohorts; managed image covers. |
| F157 | 157-01–04 | ContentWorkspace.tsx / page.tsx | In-page media rendering and validated same-course quiz links; draft/review/publish transitions preserved. |
| F158 | 158-01–05 | LearningModules.tsx | Subject/type/language catalogue facets before pagination; archived-resource loans can still be returned; private reader/file access preserved. |
| F159 | 159-01–04 | LearningModules.tsx / FinalWorkflows.tsx | Cohort-only learner schedule; correct cohort teacher; time-derived Live/Ended states; audited manual attendance correction; cancelled/ended room interactions rejected. |
| F160 | 160-01–03 | LearningModules.tsx | Course/topic/teacher catalogue search and filters; signed media access, playback/progress/notes retained. |
| F161 | 161-01–04 | LearningModules.tsx | Per-learner, per-cohort, per-step evidence includes learners who have not started; ordered path references and completion preserved. |
| F162 | 162-01–03 | LearningModules.tsx / FinalWorkflows.tsx | Positive but low percentage scores now produce recommendations; upcoming activities included; real topic strengths/gaps exposed. |
| F163 | 163-01–04 | page.tsx / ManagementModules.tsx | General/Lesson and course tutor paths rechecked for access-first calls, disclosure, limits, flags and stale-response guards; no invented provider output. |
| F164 | 164-01–04 | LearningModules.tsx | Independent per-course approved translation coverage; supporting translation list controls; original-content fallback and review access retained. |
| F165 | 165-01–03 | page.tsx / FinalWorkflows.tsx | Draft/Published/Archived assignment lifecycle; validated edit form; used assignments retain original marking scale; nonpublished submissions rejected. |
| F166 | 166-01–03 | page.tsx / feature-shared.tsx | Rubric totals retained; blank feedback/criteria and nonfinite scores rejected; marking blocked while waiting for resubmission; history preserved. |
| F167 | 167-01–03 | LearningModules.tsx | Participation includes zero-contribution learners, replies and reactions; private membership boundaries preserved. |
| F168 | 168-01–04 | page.tsx / CoreManagement.tsx / FinalWorkflows.tsx | Quiz settings lifecycle; reusable question editing; used-question/scoring immutability; locking against new attempts; empty/oversize question-set guards; saved-answer/solution review. |
| F169 | 169-01–03 | PracticeModules.tsx | Topic/difficulty/language filters before pagination; supporting result controls; existing run/submit/scoring path retained. |
| F170 | 170-01–03 | PracticeModules.tsx / FinalWorkflows.tsx | Experiment inputs persist on resume; completed notebook cannot regress; explicit teacher score/feedback; submitted code and output visible. |
| F171 | 171-01–03 | PracticeModules.tsx / FinalWorkflows.tsx | Cohort learner skill evidence includes Not started, In progress and Completed; sequential completion retained. |
| F172 | 172-01–03 | PracticeModules.tsx | Speaking/writing response, recording/file submission and review flows retained; supporting work list controls added. |
| F173 | 173-01–03 | PracticeModules.tsx | Pack filters and saved-attempt solution review; submitted weak-topic evidence; timed scoring path retained. |
| F174 | 174-01–04 | PracticeModules.tsx | NEET subjects filtered server-side before paging; saved solutions/weak topics; configurable negative scoring retained. |
| F175 | 175-01–04 | PracticeModules.tsx | JEE subject/level filters before paging; numerical tolerance and fractional authoring input; multiple-choice/numerical scoring preserved. |
| F176 | 176-01–03 | PracticeModules.tsx | Prelims configurable fractional negative marks; saved solutions and weak areas; Mains teacher-reviewed writing retained. |
| F177 | 177-01–03 | PracticeModules.tsx | Dedicated aptitude packs plus Interview/GD responses; saved mock solutions and reviewed practice evidence retained. |
| F178 | 178-01–03 | PracticeModules.tsx | Dedicated resume/portfolio/workplace practice; response evidence and teacher scoring retained; supporting lists improved. |
| F179 | 179-01–05 | ManagementModules.tsx / page.tsx | Credential wall/certificate/rule supporting lists; existing automatic/manual awards, progress, QR and revocation paths rechecked. |
| F180 | 180-01–04 | ManagementModules.tsx / FinalWorkflows.tsx | Enrolment-gated, one-per-learner editable course reviews; actual review average/count/content, duration and listing metadata; no payment settlement added. |

## Global rules

- G01: persistent module/sub-feature navigation and mobile menu remain in the shared shell. All 25 primary route headings were re-opened in the browser.
- G02: separate Author/Reviewer/TA capabilities and explicit course-staff assignments now supplement institution/campus, owner/cohort-teacher and learner-enrolment checks. Role and list details are in ROLES-AND-LISTS.md. Server guards enforce these rules independently of navigation. Final regression tests additionally cover private cohort schedules, revoked enrolment, own submitted answers, scoped attendance correction, and library/translation denial of private student work and files.
- G03: record-screen query plans apply institution/course/learner scope, search, filters and allowlisted ordering in SQL before a 20-row keyset LIMIT. Signed one-hour cursors bind actor, roles, scope, endpoint and query; stable primary-key ties, reverse navigation and NULL ordering are tested. Computed reports use SQL aggregates/subqueries. Finite embedded rubric/test/answer arrays are presentation only. Legacy array responses remain for old API/selection consumers, not as the record-screen pagination implementation.
- G04: writes use disabled/loading controls, success/failure feedback and preserve drafts on errors. Validation now names the invalid fields. New lifecycle forms enforce publication states and preserve used marking scales.
- G05: app actions archive or change status instead of cascading deletion of learner work; confirmations and audit entries remain. Applied migrations were not rewritten. Unstarted path-step definitions can be replaced; started paths cannot be reordered.
- G06: generated responses retain disclosure and escaped text rendering. Provider grounding is prompted/tested with mocked responses, not a factual guarantee about arbitrary model output.
- G07 and AI-01–AI-10: production uses access-checked stored lessons; pasted lesson and response state is transient, with no automatic saved chat. Explicit flagged excerpts are retained for review. Provider keys remain server-side.

## Acceptance criteria AC-001–AC-025

Backend suites cover the named access, content review, AI limits/access, submission, server expiry, award, verifier, classroom attendance, lecture progress, library, preview enrolment, execution/lab and exam scoring contracts. AC-001 navigation and changed form controls received browser smoke checks. Provider-dependent AC-005–007, AC-014–015 and production AC-018–019 require real target-service tests. AC-023–024 cannot be certified universally from a route smoke test; IT QA must exercise the role/action matrix in staging. No criterion is marked passed merely because a screen exists.

## Remaining acceptance items and implementation limits

1. Institution Entra/Azure/PostgreSQL/Redis/ClamAV, full execution service, Gemini and institutional Jitsi must be provisioned and live-tested using deploy/IT-HANDOFF.md. Docker Linux engine was unavailable here; Linux Python 3.13 image execution and PostgreSQL concurrency remain unverified.
2. Full official exam syllabus, licensed papers/solutions, real lecture media/captions and provider recording/caption operations require institution content and provider configuration. Existing original samples are not presented as official exam material.
3. The approved Admiezo UI Kit revision/hash was not supplied. Managed course cover uploads are implemented; the approved visual treatment still needs UX review. The lesson layout uses the current responsive panel rather than a certified UI Kit bottom-sheet revision. UX sign-off remains open.
4. Hindi/Kannada shared labels and preferences work, but uncatalogued strings fall back to English. Full language coverage and translation quality are not certified. Authored content is translated through the reviewed-content workflow, not automatically.
5. IT must assign the ten exact Entra app roles and narrow course grants before rollout. Existing Teacher identities retain their broad role until IT deliberately reassigns them. Mixed Learner/staff claims are rejected. This replaces the prior role-consolidation gap with an explicit configuration gate.
6. Keyboard/focus trapping in the custom mobile navigation, complete screen-reader/accessibility behavior, large-video seeking, microphone capture and load/security/recovery drills require dedicated acceptance. These are not proven by TypeScript or API tests.
7. Literal REST paths/schema shapes differ in places from the illustrative LLD: feature routes share catalogue/actions and normalized assessment/practice engines. Record screens now use SQL keyset plans; old array response shapes are retained for compatibility. Review those implementation decisions with the architect; the supplied LLD does not have a signed exception for them.

These items prevent a claim of zero remaining SRS/LLD gaps. They are explicitly carried into the IT handoff rather than hidden behind placeholder screens.

## Release integrity

Fourteen additive migrations, dependency locks, source, tests, environment examples and deployment runbooks are packaged. Learner database, uploads, private configuration, backups, node_modules and build caches are excluded. The manifest records each packaged file hash; the ZIP has a separate SHA-256 checksum. Use release 0.3.1 instead of earlier 0.2.x archives. The final gate passed 94 backend tests, 8 frontend navigation tests and the production build; see VERIFICATION.md. The deployment input sheet is deploy/GO-LIVE-CHECKLIST.md.
