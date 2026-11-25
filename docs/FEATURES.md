# Section F implementation coverage

All 25 module routes now render relevant domain screens and persistent backend actions. The previous roadmap panels have been removed. An empty list means that records have not yet been uploaded or created.

Release 0.3.1 includes production deployment adapters and an IT handoff. Live infrastructure acceptance is required before claiming production SRS/LLD conformance.

| ID | Screens and working actions | Data and evidence |
| --- | --- | --- |
| F156 LMS | Ordered, role-labelled six-page navigation: Course Catalogue, Course Editor, Cohort Setup, Enrolment Roster, My Courses and Teaching Dashboard; locked destinations remain visible; explicit cohort selection, visible waiting status, idempotent roster updates, database-derived teaching metrics; existing announcements/notifications | Course/Cohort/Enrolment/LessonCompletion; connected workflow, capacity, progress and permission tests; see [workflow guide](COURSES-AND-ENROLMENT.md) |
| F157 Content | Ordered Content Editor, Content Review, Course Viewer and Content Catalogue navigation with role labels; assigned-course drafts/files/quizzes, revision feedback history, review/approval/publication, enrolled-course reader and completion | Lesson/ContentReview/Completion; connected Author–Reviewer–Learner lifecycle and private-history denial tests; see [workflow guide](LEARNING-CONTENT.md) |
| F158 Library | Ordered Library Catalogue, Resource Management, My Library, Resource Reader and Librarian Dashboard; reloadable reader URLs, saved/borrowed/returned state, preserved active due dates, returnable redacted withdrawals, live database summaries | Resource/Loan; connected lifecycle, policy, idempotency and scoped-reader tests; see [workflow guide](DIGITAL-LIBRARY.md) |
| F159 Live classes | Ordered Class Schedule / Manage, Live Class Room, Attendance Summary and Learner Class Schedule; staff scheduling, explicit joined-room access, cohort/time checks, persisted chat/hand/leave/resume, cancellation-aware attendance and user-activated video | LiveClass/Attendance/RoomMessage; workflow/access/policy tests; external video not live-tested; see [workflow guide](LIVE-CLASS-MANAGEMENT.md) |
| F160 Recorded lectures | Ordered Lecture Upload / Edit / Publish, Learner Lecture Player and Lecture Library / Search; dedicated staff capability, draft publication, scoped media, reloadable player, serialized progress/notes and staff preview | Lecture/Attachment/Progress; publication, note preservation, role/scope and replacement tests; see [workflow guide](RECORDED-LECTURE-MANAGEMENT.md) |
| F161 Paths | Ordered Path Builder, Teacher Path Progress, Learner Path View and Path Catalogue / Search; Coordinator management, paginated saved-activity selection, publication validation, server prerequisite checks, exact lab links, locked started structure and real completion/report evidence | Path/Step/Progress and underlying learning records; connected lifecycle, scope, lock and completion tests; see [workflow guide](LEARNING-PATH-MANAGEMENT.md) |
| F162 Personalisation | Ordered Learner What Next, Teacher Class Insights and Personalisation Settings; saved goals/pace ranking, exact activity links, current cohort completion, shared review policy and partial preference saves | Persisted preferences and actual learning evidence; six workflow tests; see [workflow guide](PERSONALISED-LEARNING-MANAGEMENT.md) |
| F163 AI tutor | Ordered AI Tutor Chat, Teacher Tutor Review and Tutor Policy / Settings; course-grounded generation, scoped Coordinator review/policy capabilities, private learner flags and saved staff guidance | TutorPolicy/TutorFlag and Published lessons; five workflow tests with mocked generation; see [workflow guide](AI-TUTOR-MANAGEMENT.md) |
| F164 Languages | Ordered Language Preference, Translated Content View, Translation Queue / Editor and Glossary and Coverage; saved language suggestions, Coordinator translation/review, source-change invalidation and stale-edit checks | Translation/Glossary/Preference and actual lesson scope; four workflow tests; see [workflow guide](MULTILINGUAL-LEARNING-SUPPORT.md) |
| F165 Submissions | Assignment authoring with deadline/marks/attachments, text/file submission, late and resubmit states, teacher work links | Assignment/Submission/Attachment with validation and ownership checks |
| F166 Feedback | Separate marking queue and learner feedback, score bounds, structured rubric editor and API, marking history, re-evaluation and re-mark, resubmit permission | MarkingHistory/Reevaluation; lifecycle tested |
| F167 Activities | Prompts, due dates and private membership groups, discussion thread, replies/reactions, contribution counts and participation table | Activity/Post/Reaction; thread lifecycle tested |
| F168 Quizzes | Questions/marking/time/attempt limits, bank with topic/difficulty search and copy, multi-question assembly through bank, single/multiple-choice and numerical answers, per-question marks, timed attempt, save/resume, expiry worker, solutions/results | Quiz/Question/Attempt; no answer leak before submission; timing and scoring tests |
| F169 Coding | Problem authoring, code/input editor, real output, test evaluation, persisted scores and learner/teacher results | Problem/Attempt and isolated Piston-compatible production adapter; bounded Python fallback only in development |
| F170 Labs | Lab authoring, ordered instructions, experiment code/inputs, per-step observations, save/resume, completion and results | Lab/Session with real output and all-step validation |
| F171 Digital skills | Track authoring, ordered practical steps, idempotent completion and teacher aggregation | Skill/Progress; sequence tests and browser authoring proof |
| F172 Communication | Speaking/writing prompts and rubric, text/file response, optional microphone recording/preview/upload, teacher score/feedback | Practice records scoped to 172; submission/review tested |
| F173 Competitive exams | Dedicated packs, subject filters, timed mocks, configured scoring, solutions and weak-question/topic evidence | ExamPack scoped to 173 and shared tested assessment engine |
| F174 NEET | Dedicated packs, Physics/Chemistry/Botany/Zoology filters, seeded +4/-1 marking, timed attempts/results, paper upload/reader and insights | ExamPack scoped to 174; negative scoring tested |
| F175 JEE | Separate packs, Physics/Chemistry/Maths and Main/Advanced filters, configured marking, timed mocks/solutions, papers and insights | ExamPack scoped to 175; separate module data tested |
| F176 UPSC | Prelims packs and subject filters, Mains answer-writing prompts, text submission, teacher review and evidence | ExamPack and Practice records scoped to 176 |
| F177 Placement | Aptitude mocks, interview/GD prompts, text/audio/file response, teacher review and evidence | ExamPack and Practice records scoped to 177 |
| F178 Career | Resume-summary and portfolio activities, response/evidence attachment, teacher review and career evidence | Practice records scoped to 178 |
| F179 Credentials | Wall, progress/streak, course/quiz/assignment threshold rules, automatic/manual awards, certificate detail/print/QR, public verifier and revocation | Rule/Award/Certificate; idempotency, trigger, QR and revoked verification tests |
| F180 Marketplace | Search/free filter, details/syllabus, preview confirmation/enrol/waitlist, seller listings and preview earnings | Listing/Purchase/Enrolment; idempotency tested; no actual payments |

## Production implementation and acceptance boundaries

- Entra authorization-code SSO and RS256 bearer authentication use directory/object identity, role checks and institution scoping. Production disables local password login. Explicit legacy identity binding preserves existing learner records.
- Python 3.13 containers, PostgreSQL 16 configuration, shared Redis sessions/cache, private Azure Blob signed URLs, fail-closed ClamAV scanning, HTTPS and hardened cookies are packaged. Upload limits are configurable; production defaults to 512 MiB.
- Python, JavaScript, Java and C++ execution uses an authenticated isolated Piston-compatible service. Production refuses the development subset fallback. IT must provision and harden the execution service.
- Institutional Jitsi uses short-lived room-specific JWTs. IT must enforce token affiliation/moderation and configure recording/caption services as required. Actual provider video/recording is not verified here.
- Gemini generation requires institution credentials. Missing configuration produces an error rather than simulated answers. Shared Redis supplies production request quotas; IT must configure billing/cost controls.
- Hindi/Kannada shared UI catalogues and saved interface preferences are implemented. Uncatalogued strings fall back to English; language review remains necessary. Authored content uses the separate manual translation/approval workflow; automatic translation is not provided.
- Single-choice, multiple-choice and numerical assessments, tolerance and per-question marks are implemented. Structured marking rubric totals and private activity-group membership/access are validated. Teacher assignment selectors support managed course/cohort ownership.
- Sample exam material is original, not official or a complete licensed syllabus. Institution staff must supply permitted papers, courses, videos and captions.
- Marketplace payments remain preview-only, matching the source scope. Approved theme, accessibility/security/load reviews and live service verification remain acceptance gates.

See [IT handoff](../deploy/IT-HANDOFF.md) and [verification](VERIFICATION.md). This release has not been deployed to a live institution environment.

## Final review corrections in 0.3.1

See FINAL-SRS-LLD-REVIEW.md and REQUIREMENTS-TRACEABILITY.json for all 25 modules and 93 feature requirements. This pass adds role-specific dashboard updates, cohort isolation, waitlist fixes, managed course covers/duration/reviews, in-page lesson media/quiz links, assessment editing/publication, saved solutions/weak topics, question-bank editing and immutability, server catalogue facets and supporting-list signed cursors, lab inputs/teacher marking, per-cohort path/skill evidence, per-course translation coverage, audited attendance corrections and stronger denial of private student work/files to library/translation roles.

94 backend tests, 8 frontend navigation tests and the frontend production build pass. The final review explicitly lists remaining implementation decisions and external acceptance requirements; this is not a zero-gap production certification.

## Role and list corrections in 0.3.1

Author, Reviewer and TA are separate least-privilege roles with explicit course assignments. Frontend tabs/actions follow server capabilities. Record screens use authorized SQL search/filter/sort and signed keyset cursors with 20-row pages, including computed reports. See ROLES-AND-LISTS.md for the permission matrix and compatibility boundaries.
