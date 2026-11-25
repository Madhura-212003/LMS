# Learning content — F157

Updated 25 November 2026. This guide describes the current application source, not a rebuilt deployment archive.

## Four-page navigation

| Order | Page | Primary audience | Current-app route |
| --- | --- | --- | --- |
| 1 | Content Editor | Author | `/lms/157/Content%20editor` |
| 2 | Content Review | Reviewer | `/lms/157/Content%20review` |
| 3 | Course Viewer | Learner | `/lms/157/Course%20viewer` |
| 4 | Content Catalogue | Author | `/lms/157/Content%20catalogue` |

These replace the reference ERP navigation destinations `#/content-editor`, `#/content-review`, `#/learn` and `#/content` inside this application's Learning content section. They use the current frontend/backend rather than navigating to port 8001. The legacy `Lesson editor` route opens Content Editor.

The sidebar and primary navigation show all four destinations with role labels, using the authenticated `/api/lms/content-workflow` response. Unavailable actions are disabled; navigation does not grant a role. Authors enter at Content Editor, Reviewers at Content Review, and Learners at Course Viewer on the bare module route. Existing Teacher/Admin capabilities remain in effect. “Author” on Content Catalogue names its primary audience; Learners retain access to published lessons from their enrolled courses.

## Connected publication workflow

1. **Content Editor:** an Author with an owned/assigned course selects the course, writes the lesson, sets its order, attaches permitted files and optionally links assessments from that course. Saving creates a Draft. Changing the selected course clears previous attachments and quiz selections to avoid cross-course references. Existing course assignments are loaded from the server.
2. **Submit for review:** Draft and Needs Changes lessons can be submitted to In Review. Submitted, approved and published lessons cannot be edited through the draft form. Server validation remains authoritative.
3. **Content Review:** a Reviewer with course access opens an In Review lesson, reads its complete body and opens its attachments. Approval moves it to Approved. Requesting changes requires a comment and moves it to Needs Changes.
4. **Revision:** the Author opens the lesson for editing and sees its paginated review history, including reviewer, decision, comment and timestamp. The Author revises and resubmits it. Review comments remain scoped to content writers/reviewers with course access.
5. **Content Catalogue:** browse lessons by course/title, publication state and update order. A permitted Reviewer/Teacher/Admin publishes an Approved lesson here. The review-success notice links directly to the catalogue. Authors can inspect review history; they cannot approve or publish solely through an Author role.
6. **Course Viewer:** shows courses the current account can access, using persisted course metadata and learner progress. Opening a course selects its first accessible lesson and uses the existing ordered reader, media, linked quizzes, completion controls and AI companion. Learners see only Published lessons and need Enrolled/Completed access; waiting-list status is insufficient. Assigned staff retain their existing preview access.

## Data, authorization and synchronization

Course, Lesson, ContentReview, LessonCompletion, attachments and quiz records remain the source of truth. No demo records, fixed lesson content, fake progress or extra database schema were introduced. Static interface labels remain code. Navigation and accessibility flags come from the backend; publication options and the frontend's editable-state decisions use the same transition definition as the review service.

`GET /api/lms/content/{lesson_id}/reviews?list_page=1` returns authorized review history with the existing signed 20-row cursor, search/filter/sort contract. Learners and unassigned staff cannot use it; API checks apply to guessed IDs and direct requests. The compatibility array route is protected as well.

Successful content mutations reload the current list and refresh shared overview data. Changing workflow pages fetches saved records. Returning focus or using Refresh content/courses reloads the relevant view. This is request/focus-based synchronization; it does not push changes to an unattended open window. Course grants, file permissions, assessment-course validation and published-lesson visibility remain server-enforced.

## Verification and boundaries

`lms.test_content_workflow` covers Author → review → requested changes and private feedback → revision → approval → publication → Learner viewer/completion, plus denial for Learners/unassigned staff and the ordered role-labelled manifest. Frontend tests cover role-based default pages and the shared disabled navigation renderer.

This pass adds a viewer entry point and review-feedback handoff. It does not add a rich-text editor, lesson version snapshots, side-by-side revision diffs, scheduled publication, a new approval policy or real-time push updates. Existing published content cannot be directly edited; a versioned revision workflow would be a separate change.
