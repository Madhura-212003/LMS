# Live Class Management — F159

Updated 25 November 2026. This guide describes the current application source; deployment archives have not been rebuilt.

## Four-page navigation

| Order | Page | Primary audience | Current-app route |
| --- | --- | --- | --- |
| 1 | Class Schedule / Manage | Teacher / Coordinator / Admin | `/lms/159/Class%20schedule%20%2F%20Manage` |
| 2 | Live Class Room | Learner / Teacher / TA | `/lms/159/Live%20class%20room` |
| 3 | Attendance Summary | Teacher / Coordinator / Learner | `/lms/159/Attendance%20summary` |
| 4 | Learner Class Schedule | Learner | `/lms/159/Learner%20class%20schedule` |

These correspond to the reference ERP's `#/class-schedule`, `#/live-class-room`, `#/attendance-summary` and `#/learner-class-schedule` destinations within this application's Live Class Management module. They do not redirect to port 8001. The old Class schedule and Attendance routes resolve to the corresponding new views.

The authenticated `/api/lms/live-workflow` response supplies ordered labels, primary audiences, accessibility flags and policy values. All four destinations remain visible; unauthorized pages are disabled. Primary-audience labels preserve existing Admin/Coordinator oversight and TA attendance-report/correction access. A course assignment is still required for staff access outside Admin/Coordinator institution scope.

## Connected class workflow

1. **Class Schedule / Manage:** Teacher/Coordinator/Admin select an authorized course and one of its cohorts, set the title, description and timezone-aware start/end values, then save. The schedule assigns the cohort's persisted teacher. The form offers paginated course selection and clears cohort selection when the course changes. Class end must follow its start and must not already have passed. Meeting URLs require HTTPS and, in production, the configured institutional provider.
2. **Edit/cancel:** permitted staff can revise open schedules or cancel them. Closed/ended classes require a new schedule. Once attendance exists, a class cannot move to another cohort. Existing attendance and messages are retained. TA-only accounts now assist rooms but cannot create, edit or cancel schedules; this intentionally narrows the former scheduling behavior to the requested role split.
3. **Learner Class Schedule:** queries persisted schedules for the Learner's actual enrolled/completed cohorts, including server-derived Scheduled, Live, Ended and Cancelled state. Default sorting is by start time; teacher filtering uses the class teacher. Waitlisted or other-cohort enrolments do not grant entry.
4. **Live Class Room:** opening a schedule entry navigates to `/lms/159/Live%20class%20room/{class_id}` and loads authorized details without creating attendance. The class ID survives refresh. Join classroom explicitly checks role, cohort, server time, cancellation/end state and provider configuration. Only then does it record attendance and return the meeting URL/token. The room's participants and discussion cannot be read before joining.
5. **Participate/leave/resume:** joined accounts can read persisted discussion, send messages and raise/lower a hand. Leave records the departure and clears hand state. Chat/hand actions require an active joined record and an open classroom. Resuming uses the existing attendance row and preserves its original joined time and attendance status; it does not duplicate attendance. Refreshing the room page requires an explicit resume to reopen the local room/video interface.
6. **Attendance Summary:** shows actual records for enrolled/completed cohort members, with Not joined/Absent derived when there is no join. Learners see only their own records. Permitted staff retain audited Present/Absent/Late corrections. Cancelled classes display Cancelled, not Absent, and are not correction obligations. Staff/TA room attendance is retained but this learner report is scoped to enrolled cohort members.

## Video, policy and synchronization

Video remains user-activated: Open video room embeds the meeting URL returned by the join API. Institutional Jitsi/JWT configuration is still required for production moderation and provider-side access. Local application tests do not verify external video, recording, captions or provider room termination. Closing the application discussion is not a guarantee that a provider has terminated its video room.

The server derives availability from saved schedules and its clock. Configure `LIVE_LATE_AFTER_MINUTES` (nonnegative, default 10) and `LIVE_ROOM_POLL_SECONDS` (positive, default 5) as process environment variables before starting Django. They are not read by the AI-only `.env` loader. New attendance uses the lateness policy; existing attendance is preserved. Joined-room polling uses the server-provided interval, updates participants/discussion/availability, disables closed-room actions and removes the embedded video when the application room closes.

Successful actions reload the relevant data. Window focus and Refresh classes requery schedules/details/attendance; joined rooms also poll. Opening other sessions does not push updates without their next refresh/poll/request. No fake schedules, participants, attendance totals or messages were added to the local learner database. No database schema migration was introduced.

## Verification and boundaries

`lms.test_live_workflow` covers Teacher scheduling, explicit Learner joining, discussion, hand state, leave/resume and single-row attendance, Coordinator correction, TA assistance without scheduling, time/cohort denial, cancellation reporting and closed-room actions. Existing JWT moderation tests continue to apply. Test records are isolated from the local application database.

This pass does not add recurrence, calendar synchronization, invitations, recordings, captions, historical connected-duration analytics or real-time socket delivery. Attendance currently records initial join, latest departure, hand state and status; it does not claim accurate accumulated attendance duration across reconnects.
