# Final local end-to-end check — release 0.3.1

Reviewed 25 modules against all ten supported roles on 25 November 2026. Local verification passed after the fixes below. This is an IT staging handoff, not a certificate that unconfigured cloud providers work.

## Results and scope

- **94 backend tests passed**: isolated Django HTTP/domain integration, authentication/CSRF, role/campus/course denials, submissions/marking, assessment scoring/expiry, awards, migration preservation and provider adapter contracts. Provider calls are mocked when no institution service is available. Actual development code execution also has local regression proof.
- **8 frontend tests passed**: all 250 role/module visibility combinations, all 250 role-aware default-tab selections, combined staff roles and specific staff/learner tab boundaries.
- **250 primary module/role browser checks**: each applicable screen loaded; forbidden module URLs showed the explicit role denial. **166 allowed secondary tabs** loaded without observed access/render errors. These are screen smoke checks, not 416 separately completed write workflows. Detailed records: qa/final-role-module-matrix.json.
- **Cross-role browser workflow**: Author created a temporary lesson, saved and submitted it; Reviewer saw the real review queue, approved and published it; Learner opened the published source, completed it and reopened it after a reload with completion retained. This exercises UI forms, same-origin CSRF, API permissions, database persistence and a role handoff.
- **Positive API actions for every role**: Admin and Coordinator course assignment; Teacher assessment creation; Author draft creation; Reviewer approval; TA marking/resubmission; Librarian resource creation; Translator submission; Seller own-course listing; Learner resubmission. Separate tests deny unauthorized actions, foreign scope and private learner data.
- Production frontend build passed; fourteen migrations remain additive with no model drift. No new schema migration was needed for this pass.

## Fixes made

1. Hide Seller dashboard from Learner/Coordinator and other unauthorized roles while retaining Teacher/Admin/Seller access.
2. Preserve library/marketplace modules when a user has combined staff roles; combining roles does not grant broad Teacher powers.
3. Select the first role-allowed tab for bare module URLs. This fixes TA lab/practice entry routes that previously selected an inaccessible generic catalogue. Explicit forbidden tab URLs remain denied.
4. Allow Reviewers to filter all content review states and use accurate role guidance.
5. Disable learner-only enrolment/linked-quiz actions for narrow staff actors; course creation follows the server course-management capability.

## Role/browser matrix

| Role | Available primary screens | Expected module denials | Allowed secondary tabs |
| --- | ---: | ---: | ---: |
| Admin | 25 | 0 | 49 |
| Coordinator | 25 | 0 | 31 |
| Teacher | 25 | 0 | 46 |
| Reviewer | 3 | 22 | 5 |
| Author | 2 | 23 | 3 |
| TA | 10 | 15 | 4 |
| Librarian | 1 | 24 | 3 |
| Translator | 2 | 23 | 4 |
| Seller | 2 | 23 | 3 |
| Learner | 25 | 0 | 18 |

## Module workflow evidence

The suites below exercise persistent workflows through HTTP or the domain service, using isolated test databases. Every module also has all ten actor read/scope checks in test_role_module_matrix.py and browser route evidence. Tests do not imply every role should be able to perform every module action.

| Module | Workflow proof in backend/lms |
| --- | --- |
| F156 Workspace | tests.py: enrolment_capacity_and_idempotency; tenant_and_learner_access; test_final.py: waitlist/cohort scope |
| F157 Content | tests.py: review_state_machine_and_audit; lesson_editor_preserves_reviewed_content; cross-role browser flow |
| F158 Library | test_features.py: library_save_borrow_return_reader_and_scope; test_role_module_matrix.py: Librarian creation |
| F159 Live classes | test_features.py: live_schedule_join_chat_hand_leave_and_attendance; test_final.py: attendance correction; TA role checks |
| F160 Lectures | test_features.py: lecture_upload_publish_and_progress; private file boundaries |
| F161 Paths | test_features.py: path_progress_comes_from_completed_underlying_work; SQL My-path filtering |
| F162 Personalisation | test_features.py: preferences_and_rule_based_recommendations; test_final.py: positive low-score/topic evidence |
| F163 AI tutor | tests.py: AI access/grounding/limits; test_features.py: tutor_policy_blocks_before_provider_and_flag_review |
| F164 Languages | test_features.py: translation_review_and_glossary; role tests: separate Translator/Reviewer scope |
| F165 Assignments | tests.py: assignment_marking_validation; test_final.py: draft/lifecycle/immutable marking scales |
| F166 Feedback | test_role_module_matrix.py: TA mark/resubmission → Learner resubmit; test_features.py: rubric/history/re-evaluation |
| F167 Activities | test_features.py: discussion_reply_reaction_and_participation; private membership groups; zero contributors |
| F168 Quizzes | tests.py: answer secrecy/scoring/expiry; test_features.py: question bank and copy; immutable question solutions |
| F169 Coding | test_features.py: code_runner_actual_execution_scoring_and_host_access_denial; execution/output limits |
| F170 Labs | test_features.py: lab_requires_every_observation_and_persists_real_output; test_final.py: retained inputs/completion/marking |
| F171 Digital skills | test_features.py: skill_steps_are_ordered_and_idempotent; cohort progress including not-started learners |
| F172 Communication | test_features.py: communication_career_placement_and_mains_review (172) |
| F173 Competitive exams | test_features.py: each_exam_module_has_its_own_pack_and_scoring_rules (173) |
| F174 NEET | same module-specific pack/scoring test (174), saved solutions and subject filtering |
| F175 JEE | same module-specific pack/scoring test (175), multiple/numerical answers and tolerance |
| F176 UPSC | exam pack/scoring (176) and Mains writing/review |
| F177 Placement | exam pack/scoring (177) and interview/GD response/review |
| F178 Career skills | communication_career_placement_and_mains_review (178) |
| F179 Credentials | completion_awards_once_and_verifies; credential_rules_manual_award_revocation_and_notifications |
| F180 Marketplace | marketplace_preview_is_idempotent_without_payment; learner reviews; Seller scope |

## Still required before go-live

IT must complete deploy/GO-LIVE-CHECKLIST.md: real Entra sign-in/role claims and course grants; Linux Python 3.13 containers; PostgreSQL 16 query plans/load/concurrency; Redis; private Azure Blob/ClamAV; Gemini; isolated execution for all four runtimes; Jitsi token/moderation/recording/captions; TLS; backups/restore; security, accessibility and approved UI/language/content acceptance. Docker Linux engine and institution services were unavailable here. No live deployment or universal end-to-end provider pass is claimed.

The local preview's DEVELOPMENT label is intentional. Production mode disables password/demo sign-in and requires institution configuration. Marketplace settlement remains preview-only within the source requirement scope. Do not seed demonstration users in production.

## QA cleanup and release integrity

All ten temporary QA accounts, their isolated enrolments/grants/logs and the one temporary lesson/review/completion were removed after the browser run. Cleanup verified that all original primary keys remained in every model. QA credentials were discarded and are not packaged. See qa/browser-cleanup-proof.json and qa/browser-workflow-proof.json. The completed workflow screenshot is qa/final-workflow-0.3.1.jpg. The ZIP manifest hashes every included source/document/test file; its separate checksum identifies the complete archive.
