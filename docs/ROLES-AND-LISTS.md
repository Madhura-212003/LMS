# Roles and list design — 0.3.1

## Role boundaries

App roles and course assignments are separate. Admin/Coordinator manage the Course staff screen. Teacher, Author, Reviewer, TA and Translator require an owned course, cohort-teacher relationship or active explicit course grant in their institution/campus. A course grant never adds capabilities. Removing one grant does not revoke independent ownership/cohort-teacher access; transfer those references separately.

| Capability | Roles |
| --- | --- |
| Manage courses | Admin, Coordinator, Teacher, Seller (own marketplace scope) |
| Manage rosters | Admin, Coordinator, Teacher |
| Write lessons / submit review | Admin, Teacher, Author |
| Approve/reject/publish content | Admin, Teacher, Reviewer |
| Schedule/edit/cancel live classes | Admin, Teacher, Coordinator |
| Assist live classrooms / existing attendance correction | Admin, Teacher, Coordinator, TA |
| Upload/edit/publish recorded lectures | Admin, Teacher, Coordinator, TA (`lecture_manage`) |
| Build/edit/publish learning paths | Admin, Teacher, Coordinator (`path_manage`) |
| Author assessments | Admin, Teacher |
| Mark / re-mark / request resubmission | Admin, Teacher, TA |
| Teaching reports | Admin, Teacher, Coordinator, TA |
| Submit translations | Admin, Teacher, Translator |
| Review translations | Admin, Teacher, Reviewer |
| Manage library | Admin, Librarian |
| Assign/revoke course staff | Admin, Coordinator |
| Submit learner work | Learner with active course enrolment |

Multiple staff roles combine only their named capabilities. Author+Reviewer is not promoted to Teacher. Learner with any staff role is rejected; use separate operational identity contexts. Existing legacy single-role profiles remain valid through the roles fallback. Entra saves all recognized staff roles; primary priority controls display, not capability escalation. Existing broad Teacher accounts are not silently downgraded: IT must review job responsibilities and deliberately reassign roles.

Author/Reviewer/Translator cannot inspect private learner submissions/files, other learners' quiz solutions or private credential QR identifiers. Guessed private file IDs cannot be reused in lessons/library records. Translator cannot approve their translation unless separately assigned a review-capable role. Learner writes always require real enrolment. Server checks apply even when a user bypasses the navigation.

## Record lists

Record-screen lists use authorized QuerySets with SQL search, relevant filters, allowlisted sorting and keyset pagination before serialization. Page size is 20. Stable sort-field/primary-key ties and NULLS LAST support forward/back navigation. No OFFSET is used in the new cursor contract. Totals/facets and report aggregates execute in SQL; only the bounded page is serialized.

`list_page=1` selects this contract on compatibility endpoints; `/api/lms/lists/{list_name}` always uses it. Shared query fields are `cursor`, `q`, `status`, `sort`; domain-specific filters apply before pagination. Existing `_search/_status/_sort` aliases remain supported. Signed cursors expire after one hour and bind user, role set, institution/campus, endpoint and filters. Access is re-evaluated on every request, including after course revocation. If a cursor expires or the query changes, start from the first page. Private API responses use no-store and vary by session/bearer identity.

Roster, marking, question bank, catalogues, translation, path/skill progress, attendance/participation and assessment/learning reports use this design. Persisted derived question evidence supports SQL topic reports; additive backfill and `rebuild_question_evidence` preserve original attempt answers/scores. Finite embedded rubric criteria, code test definitions and attempt-answer arrays remain display components, not separate record catalogues. Legacy array responses are retained for older clients and finite selection compatibility; they are not a production record-screen paging strategy.

SQL portability is covered locally on SQLite. IT must validate PostgreSQL 16 plans/indexes and load/concurrency using realistic institution data. Fourteen migrations are additive; release.sh reconciles derived evidence after migration. Review rollback authorization compatibility before returning to images that predate narrow roles.

## Courses and enrolment update — 25 November 2026

F156 now separates Course editor (`course_manage`), Cohort setup and Enrolment roster (`roster_manage`), and Teaching dashboard (`course_manage`) from the learner catalogue/My courses views. Existing institutional and explicit course grants are retained. My courses can display Waitlisted records through `mine=true`, but course/lesson access still requires Enrolled or Completed status. See [the workflow guide](COURSES-AND-ENROLMENT.md) for synchronization, metric definitions and retained compatibility.

## Learning content update — 25 November 2026

F157 shows Content Editor (Author / `content_write`), Content Review (Reviewer / `content_review`), Course Viewer (Learner) and Content Catalogue (Author primary audience) in that order. Role labels do not expand capabilities. Learner catalogue/viewer access remains limited to published lessons in enrolled courses; assigned staff retain their preview scope. Paginated review history requires a content-writing/review capability plus course access, and is denied to Learners and unassigned staff. The old Lesson editor URL resolves to Content Editor. See [Learning content](LEARNING-CONTENT.md).

## Digital library update — 25 November 2026

F158 now displays Library Catalogue, Resource Management, My Library, Resource Reader and Librarian Dashboard in that order. The authenticated workflow manifest supplies primary-audience labels and access flags. Management/report pages retain the `library_manage` gate; reader access rechecks course/publication scope. Withdrawn active loans remain returnable through redacted My Library records. See [Digital library](DIGITAL-LIBRARY.md).

## Live Class Management update — 25 November 2026

F159 displays Class Schedule / Manage, Live Class Room, Attendance Summary and Learner Class Schedule in that order, using the server manifest. Teacher/Coordinator/Admin manage schedules; TA-only accounts can assist rooms and retain existing attendance-report/correction access but cannot schedule/edit/cancel classes. Room participants/chat require an explicit active join, and Learners require the exact class cohort. See [Live Class Management](LIVE-CLASS-MANAGEMENT.md) for policy and synchronization details.

## Recorded Lecture Management update — 25 November 2026

F160 displays Lecture Upload / Edit / Publish, Learner Lecture Player and Lecture Library / Search. The new `lecture_manage` capability permits Teacher/TA/Coordinator/Admin to author recordings within course scope. TA module navigation/read scope now includes recordings; assessment-writing permissions are unchanged. Learners require published lectures and actual enrolment; staff preview does not create learner progress. See [Recorded Lecture Management](RECORDED-LECTURE-MANAGEMENT.md).

## Learning Path Management update — 25 November 2026

F161 displays Path Builder, Teacher Path Progress, Learner Path View and Path Catalogue / Search in the requested order. Dedicated `path_manage` adds Coordinator path authoring without assessment escalation. Activities/options and step-opening requests recheck course/publication scope; started-path structure is protected. Existing teaching-read report access remains scoped. See [Learning Path Management](LEARNING-PATH-MANAGEMENT.md).

## Personalised Learning Management update — 25 November 2026

F162 displays Learner What Next (Learner), Teacher Class Insights (Teacher / Coordinator) and Personalisation Settings (Learner / Admin). Admin retains scoped teaching reports; a Learner role is required for the next-step feed. Preferences always belong to the signed-in account. Cohort and report lists use existing authorized pagination; exact discussion links recheck course visibility. See [Personalised Learning Management](PERSONALISED-LEARNING-MANAGEMENT.md).

## AI Tutor Management update — 25 November 2026

F163 displays AI Tutor Chat (Learner), Teacher Tutor Review (Teacher / Coordinator) and Tutor Policy / Settings (Coordinator / Admin). Dedicated `tutor_review` permits Teacher/Coordinator/Admin; `tutor_policy` permits Coordinator/Admin. Teacher no longer edits policy; Coordinator does not acquire assessment-writing access. Chat/flag creation require learner enrolment; staff review rechecks course scope. Both paginated and legacy flags APIs share the same authorization, with learners restricted to their own records. See [AI Tutor Management](AI-TUTOR-MANAGEMENT.md).

## Multilingual Learning Support update — 25 November 2026

F164 displays Language Preference, Translated Content View, Translation Queue / Editor and Glossary and Coverage. Learners use the first two; Translators edit and Reviewers approve within assigned courses. Coordinator now has `translate` and `translation_review`, without content/assessment authorship. Existing Teacher/Admin translation capabilities remain. Dedicated `glossary_manage` restricts glossary creation and management navigation to Coordinator/Admin. Learners never receive in-progress translation bodies. Coverage consistently counts Published source lessons. See [Multilingual Learning Support](MULTILINGUAL-LEARNING-SUPPORT.md).
