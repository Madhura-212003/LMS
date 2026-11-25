# Courses and enrolment — F156

Updated 25 November 2026. This guide describes the implemented repository workflow; the deployment archives have not been rebuilt.

## Navigation inside Courses and enrolment

The primary navigation and sidebar display the complete six-page flow in this order, supplied by the authenticated `/api/lms/course-workflow` response:

| Page | Primary audience | Current-app route |
| --- | --- | --- |
| Course Catalogue | Learner | `/lms/156/Course%20catalogue` |
| Course Editor | Teacher | `/lms/156/Course%20editor` |
| Cohort Setup | Teacher | `/lms/156/Cohort%20setup` |
| Enrolment Roster | Coordinator | `/lms/156/Enrolment%20roster` |
| My Courses | Learner | `/lms/156/My%20courses` |
| Teaching Dashboard | Teacher | `/lms/156/Teaching%20dashboard` |

These correspond to the reference ERP's `#/courses`, `#/course-editor`, `#/cohorts`, `#/enrolment`, `#/my-courses` and `#/teaching` destinations, using this application's own pages and backend. They do not navigate away to port 8001. The bare module route opens the first page permitted for the current account in this order.

All six destinations are visible for orientation. A page outside the current account's capabilities is disabled and labelled with its primary audience and “Staff access required.” No role switching, new grants or mock records are introduced. Primary-audience labels do not remove existing authorized Admin, Coordinator or delegated staff capabilities; server checks remain authoritative. Notifications and Course staff are separate supporting links, rather than replacements for the six primary destinations.

## Connected workflow

1. **Course editor:** a permitted teacher creates a course with title, description, subject, level, duration, outcomes and syllabus modules. Save as Draft while preparing it; publish when ready. Admin/Coordinator may select or transfer its teacher/owner. Covers attach to an existing course. Archiving preserves dependent work.
2. **Cohort setup:** authorized staff select an assigned course, set a cohort name, capacity and dates, and assign a teacher. Omitting the teacher uses the persisted course owner. A new cohort must end after it starts and cannot already have ended. Cohorts may be prepared for draft courses; learners cannot join until the course is published.
3. **Course catalogue:** learners see published courses in their institution/campus, inspect outcomes and modules, then explicitly choose a cohort by teacher, dates and available seats. The application no longer silently joins the first cohort. An ended cohort is unavailable. A full cohort offers a waiting list.
4. **Enrolment roster:** staff select a cohort, inspect its paginated roster, enrol eligible learners or remove enrolments. Capacity decides Enrolled versus Waitlisted. Repeating an enrolment preserves Completed status and waiting-list order. Removing an occupied enrolment promotes the earliest active waiting learner, with ID as a deterministic tie-breaker. Progress and submissions are retained.
5. **My courses:** learners see active/completed enrolments and waiting-list entries. Waitlisting alone never grants access to lessons or submission APIs. Once promoted, the same course becomes available for learning. Published-lesson completion updates saved progress. Staff visiting this page preview assigned courses rather than seeing learner progress as their teaching metric.
6. **Teaching dashboard:** each assigned course shows persisted cohort counts, unique active/completed learners, waiting enrolments, published lesson count, and average learner completion. Average completion is completed published lessons divided by published lessons times unique enrolled/completed learners. With no learners or published lessons it is zero. There are no sample dashboard totals.

## Ownership and synchronization

Course, Cohort, Enrolment and LessonCompletion records remain the source of truth; no new database schema or seed records were introduced. Course details, cohort seats, enrolment status and teaching metrics come from the backend. `/api/lms/course-workflow` supplies course publication options, schema capacity limits, capability information and metric labels. Static interface labels and domain status identifiers remain application code.

Successful actions refresh the current lists and the overview data. Returning focus to a workflow window refreshes its lists. **Refresh data** explicitly reloads the view. Other open sessions receive changes on their next refresh/focus/request; this release does not push real-time updates to a continuously open inactive view. Every write and read rechecks server authorization.

The roster and course lists retain the existing search/filter/sort and signed 20-row cursor contract. Course/cohort selectors expose paging so staff can select records beyond the first page. Teacher/learner selectors reuse the existing institution directory endpoints. Teachers can select learners already linked to their assigned courses; Coordinators/Admin can enrol new institution learners. Existing Course staff and Notifications pages remain available as supporting links. The old `Cohorts` URL resolves to Cohort setup.

## Permissions and boundaries

| Action | Existing server capability / scope |
| --- | --- |
| Browse catalogue / self-enrol | Learner; same institution/campus; published, unarchived course; open cohort |
| View lessons / submit work | Enrolled or Completed learner; waiting-list status is insufficient |
| Create/edit/archive course | `course_manage`; owned/assigned course, or Admin/Coordinator scope; Seller retains existing own-course scope |
| Create cohort / manage roster | `roster_manage`; owned/assigned course or Admin/Coordinator scope |
| Teaching dashboard | `course_manage`; assigned course scope |
| Assign course staff | Existing `staff_assign` capability |

Course publication controls catalogue discovery and new self-enrolment. Returning a course to Draft preserves existing learner enrolments and access, matching the current course-access policy. Capacity includes Completed enrolments. Cohort dates are institution-local calendar dates. SQLite verifies functional behavior locally; PostgreSQL locking under concurrent enrolment still requires deployment integration testing.

## Verification

`lms.test_course_workflow` exercises create/publish, explicit second-cohort selection, full-cohort waitlisting, denied lesson access before promotion, removal/promotion, lesson completion and resulting dashboard figures. It also checks repeated roster actions, ended cohorts, blank descriptions, campus and teacher isolation, and server-derived options/default teacher assignment. Test data is created only in Django's isolated test database.

## Suggested next increments (not implemented)

- Cohort editing with safe capacity changes and learner transfers between cohorts.
- Self-service withdrawal, with explicit retention and waiting-list promotion rules.
- In-app enrolment/promotion notifications and optional configured email delivery.
- CSV roster import with preview, duplicate detection and per-row validation.
- Approval-based enrolment and prerequisites configured per course.
- Real-time roster refresh after a server event, if cross-session updates must appear without focus or manual refresh.

These are separate product decisions and have not been added to this feature pass.
