# Personalised Learning Management — F162

Updated 25 November 2026. Describes the current application source; deployment archives have not been rebuilt.

## Three-page navigation

| Order | Page | Audience | Current-app route |
| --- | --- | --- | --- |
| 1 | Learner What Next | Learner | `/lms/162/Learner%20what%20next` |
| 2 | Teacher Class Insights | Teacher / Coordinator | `/lms/162/Teacher%20class%20insights` |
| 3 | Personalisation Settings | Learner / Admin | `/lms/162/Personalisation%20settings` |

These replace the reference ERP destinations `#/what-next`, `#/class-insights` and `#/personalisation-settings` inside the current app. Legacy What next, Class insights and Preferences routes resolve to the new pages. The authenticated `/api/lms/personalisation-workflow` supplies the ordered labels, audiences, access flags and policy options. Unavailable destinations remain visible but disabled. Admin retains scoped reporting access; the learner feed requires a Learner role. Settings edit the signed-in user's preferences, including for Admin.

## Connected workflow

1. **Personalisation Settings:** save goals, pace, content language, interface language and new course-announcement notification preference. Saves update only edited fields, preserving other saved preferences. The API validates values and serializes updates on the account. Interface language updates after saving; content language is used by translation browsing. Discard restores saved values, and focus refresh does not overwrite a dirty form.
2. **Learner What Next:** fetches saved preferences and current authorized course records together. Candidates include the first uncompleted published lesson per accessible course, eligible low-scoring assessments with attempts available, and upcoming published discussions without a contribution by the learner. Only the latest submitted assessment attempt determines review eligibility. Goal terms of at least three characters rank candidates through substring matches against actual activity/course text. This is rule-based guidance, with reasons shown, rather than an AI response or semantic matching.
3. **Pace:** limits the number of suggestions. The upcoming discussion candidate pool is also limited by pace before goal ranking. Server process environment variables `PERSONALISATION_GENTLE_LIMIT`, `PERSONALISATION_STEADY_LIMIT` and `PERSONALISATION_INTENSIVE_LIMIT` configure the defaults of 3, 6 and 10 respectively. These process settings are distinct from the AI-only `.env` loader.
4. **Continue actual work:** lesson and assessment actions open the existing saved activity. Discussions open the exact authorized record at `/lms/167/Activities/{activity_id}/162`, with a return link to Learner What Next. Completing learning or contributing to a discussion changes the next fetched suggestions; no duplicate progress store is introduced.
5. **Teacher Class Insights:** choose a saved accessible cohort or inspect all assigned courses. Topic reports use submitted assessment evidence. Lesson reports count published lessons and completion records belonging to currently active/completed enrolled learners; removed learners and draft lessons do not inflate current counts. A lesson completion count is a count of learner/lesson pairs, not completed courses or a percentage.

`PERSONALISATION_REVIEW_BELOW_PERCENT` configures the shared assessment-review/topic-gap boundary (default 70). The comparison uses unrounded evidence; displayed accuracy is rounded. Topic evidence can include historical submissions, while current lesson completion is explicitly limited to current enrolments. Missing evidence produces empty results, not fabricated strengths or progress.

## Synchronization, access and limits

Preferences, enrolments, lessons, lesson completions, assessment attempts, discussions and posts remain the source of truth. Mutations, returning from work, window focus and Refresh personalisation fetch current data. There is no real-time push to an unattended session. The learner APIs enforce role and course scope; reports retain teaching permissions and course/cohort scope.

Disabling notifications suppresses future in-app course-announcement notifications for that account. Existing notifications remain. It does not add email/push delivery or silence unrelated notification types. No learner data, recommendations or reports were seeded for this change, and no schema migration is required.

This pass does not add AI planning, adaptive difficulty, automatic enrolment, institution-wide preference administration, scheduled reminders or predictive risk scoring. Possible follow-up features include learner feedback on recommendations, prerequisite-aware plans and configurable reporting periods, each using persisted evidence and explicit policy.

Six isolated backend tests cover partial settings preservation/validation, self scope, goal ranking and pace, exact discussion access/contribution, latest assessment evidence, configurable review boundaries, current completion/cohort scope, notification preference and role navigation. Frontend checks cover the requested three-page order and role access. Native browser interaction was not verified; see [verification](VERIFICATION.md).
