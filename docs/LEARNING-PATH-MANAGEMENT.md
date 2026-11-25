# Learning Path Management — F161

Updated 25 November 2026. This guide describes the current application source; deployment archives have not been rebuilt.

## Four-page navigation

| Order | Page | Primary audience | Current-app route |
| --- | --- | --- | --- |
| 1 | Path Builder | Teacher / Coordinator / Admin | `/lms/161/Path%20builder` |
| 2 | Teacher Path Progress | Teacher / Coordinator | `/lms/161/Teacher%20path%20progress` |
| 3 | Learner Path View | Learner | `/lms/161/Learner%20path%20view` |
| 4 | Path Catalogue / Search | Learner / Teacher | `/lms/161/Path%20catalogue%20%2F%20Search` |

These correspond to the reference ERP's `#/path-builder`, `#/teacher-path-progress`, `#/learner-path` and `#/path-catalogue` destinations inside this application's Learning Path Management section. They use the current backend and do not redirect to port 8001. Path catalogue, My path and Path progress legacy routes resolve to the corresponding new destinations.

The authenticated `/api/lms/path-workflow` response supplies ordered labels, audience captions, access flags, publication options, supported activity types and the schema step limit. The full navigation remains visible with unavailable destinations disabled. `path_manage` permits Teacher/Coordinator/Admin to build paths within course scope; it does not grant assessment-authoring permissions. Teacher reports retain the existing `teaching_read` and course scope. Assigned staff can preview paths without creating a learner start record.

## Connected workflow

1. **Path Builder:** select a course, enter title/description and add saved lessons, quizzes, programming labs or courses. Activity selectors use `/api/lms/features/paths/options?kind={kind}&list_page=1` with authorized search/filter/sort and signed pagination. Staff can reach records beyond the first page. Activity names and IDs come from saved records; duplicate references and empty paths are rejected. Reorder/remove controls define the persisted sequence. New form entries default to Draft.
2. **Publish:** every linked activity and its course must be Published before a path can be published. References must exist and be within the staff account's course access. The API rechecks these rules for both create/edit and explicit publication. Paths may reference several authorized courses, but learners must separately have access to each target course.
3. **Path Catalogue / Search:** Learners discover Published paths in courses they can access, inspect the ordered view, and explicitly start a path. Start is idempotent: one PathProgress record and initial-start audit per learner/path. Waiting-list status does not grant learning access.
4. **Learner Path View:** `/lms/161/Learner%20path%20view/{path_id}` survives refresh. The unqualified view lists started paths. Saved steps show real completion, availability and prerequisite state. `POST /api/lms/features/paths/{path_id}/steps/{step_id}/open` requires a started path, checks that the step belongs to it, verifies earlier completion and rechecks target access/publication. Disabled buttons are not the only enforcement.
5. **Open actual work:** lesson/course steps open the existing course reader; quiz steps open their actual assessment; lab steps open `/lms/170/Lab%20catalogue/{lab_id}/{path_id}` with that exact saved notebook and a Back to learning path link. Course-reader and quiz-return controls preserve the path context. Returning to the path fetches the resulting saved completion.
6. **Teacher Path Progress:** shows each accessible path's cohort, learner, start state, ordered activity and completion from the same underlying work records. A path-specific route `/lms/161/Teacher%20path%20progress/{path_id}` filters the report; the report API also accepts cohort filtering. It does not invent percentages, time spent or enrolment records. A learner in multiple cohorts can appear once per relevant cohort.

## Completion and change rules

- A lesson step requires its LessonCompletion record.
- A quiz step requires at least one Submitted attempt with a positive score; no new configurable pass-threshold policy was introduced.
- A lab step requires a Completed LabSession.
- A course step requires at least one Published lesson and completion of every Published lesson, not a rounded display percentage. Learner projection and teacher SQL report use this exact rule.

Previously completed work can be credited even before starting a path. The teacher report shows start state separately from activity completion. Starting the path is still required to use path-context opening actions. Prerequisites govern navigation through the path; they do not revoke independent access to a lesson/quiz/lab through another authorized module.

Once any learner has started, activities, labels and sequence are locked to preserve evidence. Title, description and publication state can still be changed when the step structure is unchanged, without replacing step IDs. A structural revision requires a new path. Path start and structural updates use the same row lock; rejected edits roll back metadata as well as structure. Archiving/unpublishing retains learner work and path-start records while removing learner catalogue access.

## Synchronization and verification

LearningPath, PathStep, PathProgress, LessonCompletion, Attempt, LabSession and enrolled-course records remain the source of truth. No fake activities, progress or local learner records were added; no schema migration is required. Mutations, navigation back to a path, window focus and Refresh paths fetch current data. There is no real-time push to an unattended session.

`lms.test_path_workflow` exercises Coordinator building, publication, explicit start, prerequisite denial, actual lesson/quiz/lab/course completion, teacher-report alignment, metadata edits with stable step IDs, rejected structural changes, duplicate/unpublished reference validation, cross-course access, foreign scope, paginated options and exact all-lesson course completion. Tests use isolated Django data.

This pass does not add automatic enrolment into target courses, path version migration, branching conditions, timed release, recommendations, notifications or certified time-on-path analytics. Native browser interaction was not verified in this pass; API, navigation, TypeScript and build checks are recorded in [verification](VERIFICATION.md).
