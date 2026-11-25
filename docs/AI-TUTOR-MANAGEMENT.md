# AI Tutor Management — F163

Updated 25 November 2026. This guide describes current application source; deployment archives have not been rebuilt.

## Three-page navigation

| Order | Page | Primary audience | Current-app route |
| --- | --- | --- | --- |
| 1 | AI Tutor Chat | Learner | `/lms/163/AI%20tutor%20chat` |
| 2 | Teacher Tutor Review | Teacher / Coordinator | `/lms/163/Teacher%20tutor%20review` |
| 3 | Tutor Policy / Settings | Coordinator / Admin | `/lms/163/Tutor%20policy%20%2F%20Settings` |

These correspond to the reference ERP destinations `#/tutor-chat`, `#/tutor-review` and `#/tutor-policy`. They use the current backend rather than redirecting to port 8001. Legacy AI assistant/Course tutor, Tutor review and Tutor settings routes resolve to their new destinations.

The authenticated `/api/lms/tutor-workflow` supplies ordered labels, audiences, access flags and model-derived policy defaults. Navigation shows unavailable destinations disabled. Dedicated `tutor_review` permits Teacher, Coordinator and Admin; `tutor_policy` permits Coordinator and Admin. These do not grant assessment authorship. Teacher policy editing has been removed to match the requested audience. Existing course assignments and tenant/campus scope still apply; Coordinators/Admins retain their existing institution scope.

## Connected workflow

1. **Tutor Policy / Settings:** choose an accessible saved course using authorized search/filter/sort/pagination. Load its saved policy, or server defaults without creating a record. Set allowed topic phrases, blocked phrases, tone and escalation guidance. Saves trim/deduplicate phrases, reject blank tone/guidance and retain one policy per course. Each phrase is limited to 200 characters, with at most 100 phrases per list. Discard restores saved values. Focus refresh preserves an unsaved draft, while choosing a different course opens that course's own form.
2. **AI Tutor Chat:** Learners select an enrolled accessible Published course and ask an independent question. The server loads its current policy, rejects blocked or outside-allowlist questions before the provider call, and uses Published lesson text ordered by lesson position/ID. Draft text is excluded. The existing provider context cap is 60,000 characters. No published text, unavailable configuration, denied access or provider failure produces a visible error; no fabricated answer is substituted.
3. **Actual generation:** the existing Gemini adapter uses server-side `AI_PROVIDER`, `AI_API_KEY` and `AI_MODEL` from environment/backend `.env`. Keys are not exposed to the frontend. Topic rules use case-insensitive phrase containment, with blocked phrases taking priority. Blocked phrases in a generated response cause it to be withheld with escalation guidance. Tone is a prompt instruction, and lesson grounding is a provider instruction rather than a guarantee of factual correctness. The existing per-user AI request quota still applies. This is a direct provider integration, without an autonomous agent or external tool execution.
4. **Flag for review:** the learner explicitly saves an answer excerpt (up to 10,000 characters) and reason (up to 2,000). Chat history is otherwise transient and each question is independent. The UI prevents submitting the same displayed answer twice in that session. The flag API accepts a learner-submitted excerpt; it is not cryptographic proof of a provider response, and independent duplicate API submissions are not deduplicated. No question transcript is automatically saved.
5. **Teacher Tutor Review:** authorized staff search/filter/paginate flagged excerpts from accessible courses. Save guidance to change a flag to Reviewed; empty guidance is rejected. Staff can revise the saved guidance, with review actions audited. This is not a versioned decision-history viewer.
6. **Back to the learner:** My flagged answers and staff guidance shows only that learner's flags in currently accessible courses, including the persisted review decision. Other learners' excerpts and decisions are excluded in both legacy and paginated list APIs. Reviewed guidance becomes visible on Refresh tutor, window focus or revisiting the page. It does not automatically alter course policy or send a notification.

## Synchronization and limits

TutorPolicy, TutorFlag, course/enrolment scope and Published lessons remain the source of truth. No demo answers, policies, flags or course lists were added. No schema migration is required. Course switches mount separate forms/chat state, preventing a pending response or old draft from appearing under another course. Policy changes apply to subsequent questions, including after returning to the same course; an already-running request uses the policy read when it began. Refresh/focus fetches lists and policy; it does not regenerate answers. There is no live push or persistent unflagged conversation memory.

These policies govern the course tutor endpoint. Existing General/Lesson assistant controls in the Course Viewer use separate endpoints and are not made subject to these course tutor rules by this change. No AI key/model editor was added to the browser.

Five isolated backend tests cover audience/capability access, Coordinator policy management without assessment escalation, phrase normalization, before/after-provider policy checks, Published source grounding, private learner flags, staff review return, foreign/unassigned scope, unpublished/waitlisted access and provider-error handling. AI calls are mocked in tests; real-provider generation and native browser interaction were not verified in this pass. See [verification](VERIFICATION.md).

Possible next additions: persistent learner-owned conversation threads with retention controls, lesson citations with direct source links, and versioned policy/decision history. Each should be scoped and backed by saved records.
