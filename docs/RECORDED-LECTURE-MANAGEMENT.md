# Recorded Lecture Management — F160

Updated 25 November 2026. This guide describes the application source; deployment archives have not been rebuilt.

## Three-page navigation

| Order | Page | Primary audience | Current-app route |
| --- | --- | --- | --- |
| 1 | Lecture Upload / Edit / Publish | Teacher / TA / Coordinator / Admin | `/lms/160/Lecture%20upload%20%2F%20Edit%20%2F%20Publish` |
| 2 | Learner Lecture Player | Learner | `/lms/160/Learner%20lecture%20player` |
| 3 | Lecture Library / Search | Teacher / Coordinator / Learner | `/lms/160/Lecture%20library%20%2F%20Search` |

These correspond to the reference ERP's `#/lecture-editor`, `#/lecture-player` and `#/lecture-library` destinations inside this application's Recorded Lecture Management module. They use the current application's records and APIs, rather than redirecting to port 8001. The old Upload lecture and Lecture library URLs resolve to the new authoring/library pages.

The authenticated `/api/lms/lecture-workflow` response supplies role-labelled navigation, accessibility flags, publication policy, upload accept types and the player save interval. All three entries are visible; unavailable authoring controls remain disabled. TA and Coordinator lecture authoring uses a dedicated `lecture_manage` capability and does not grant assessment-writing permissions. Staff still require owned/assigned course access, except Admin/Coordinator institution scope. TA accounts retain staff preview access even though the library's primary-audience caption does not list TA.

## Connected lecture workflow

1. **Lecture Upload / Edit / Publish:** authorized staff select an assigned course using a searchable paginated list, enter title/description/topic, upload an MP4/WebM and optionally WebVTT captions, then save a Draft. Uploads use the existing scoped file API and configured storage/scanning. Changing the course clears selected media references. Publication is a separate explicit action on the saved lecture.
2. **Edit/publish/archive:** edit a saved lecture's metadata or captions, publish/unpublish it, or archive it while retaining learner records. A video cannot be replaced after learner progress exists; create a new lecture for a replacement recording. This prevents stored resume positions/completion from silently referring to another video. The course cannot be changed on an existing lecture.
3. **Lecture Library / Search:** search accessible recordings by title, description, course and topic, or use server facets/status filters and signed 20-row pagination. Learners see only Published lectures from courses where they are Enrolled/Completed. Waiting-list status alone grants no access; staff can inspect assigned draft/archived records.
4. **Learner Lecture Player:** selecting a recording navigates to `/lms/160/Learner%20lecture%20player/{lecture_id}` and fetches it from `/api/lms/features/lectures/resources/{lecture_id}`. The lecture ID survives refresh. The player uses the uploaded video and optional captions; it does not substitute sample footage. Saved position is restored after video metadata loads, clamped to the available duration. Playback speed is a local control.
5. **Progress/notes:** playback saves position at the configured interval and on pause/end. Explicit Save notes and progress includes the current notes; playback-only requests omit notes, so they do not clear or overwrite a newer notes save. Client saves are serialized in event order and can recover after a failed request. Server updates lock the lecture/progress record, preserve omitted notes, and keep completion true once recorded. An explicit empty notes string clears notes. Back to Library saves the current position and notes before navigating; failure leaves the player open to retry.
6. **Staff preview:** authorized staff can preview recordings, but the new player does not record learner progress or notes for staff accounts. Progress writes require a Learner account and accessible Published lecture. Unpublishing/archiving blocks new learner reads/writes while retaining existing database progress and notes.

## Policy and synchronization

Lecture, LectureProgress and Attachment records remain the source of truth. No fake lecture content, duration, completion count or local demo record was added, and no schema migration is required. Static interface labels and playback controls remain code.

Configure the positive process environment variable `LECTURE_PROGRESS_SAVE_SECONDS` before starting Django; its server default is 15 seconds. Restart Django after changing it. This is not read by the AI-only `.env` loader. The player obtains the interval from the server rather than embedding an independent fixed interval.

Successful authoring actions refresh the library; moving between pages or returning focus fetches saved records. Private notes/progress belong to the signed-in account. Requests use the existing same-origin session and CSRF protections. Abrupt browser/process termination is not a guaranteed save point; use pause, Save notes and progress, or the player's Back button to persist work. There is no real-time push across unattended sessions.

## Verification and limitations

`lms.test_lecture_workflow` covers draft/publication visibility, video/caption references, player details, notes preservation on playback-only writes, sticky completion, single-row progress, staff authoring roles without assessment escalation, unpublishing, unrelated-account denial, invalid media references and safe replacement after progress. Frontend tests exercise role-labelled page order and serialized-save ordering/retry.

Media API tests use temporary isolated fixtures; they do not certify codec playback, long-file seeking, captions rendering or cloud signed-URL/range behavior in a real browser. Institution staff must upload playable licensed recordings, and deployment media playback still requires integration verification. This pass does not add transcoding, automatic captions, recording capture, playlists, lecture version history or certified watch-duration/anti-cheating analytics.


## Player navigation correction — 25 November 2026

Opening Learner Lecture Player without a lecture now shows a dedicated player entry screen linking to Lecture Library / Search. It no longer repeats the library grid. Choosing a saved lecture still opens its existing player, progress and notes workflow.
