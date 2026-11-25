# Digital library — F158

Updated 25 November 2026. This guide describes the application source; deployment archives have not been rebuilt.

## Five-page navigation

| Order | Page | Primary audience | Current-app route |
| --- | --- | --- | --- |
| 1 | Library Catalogue | Learner | `/lms/158/Library%20catalogue` |
| 2 | Resource Management | Librarian | `/lms/158/Resource%20management` |
| 3 | My Library | Learner | `/lms/158/My%20library` |
| 4 | Resource Reader | Learner | `/lms/158/Resource%20reader` |
| 5 | Librarian Dashboard | Librarian | `/lms/158/Librarian%20dashboard` |

These correspond to the reference ERP's `#/library`, `#/library-manage`, `#/my-library`, `#/reader` and `#/librarian` destinations inside this application's Digital library section. They use this application's records and APIs, not redirects to port 8001.

The sidebar and main navigation show all five destinations with role labels, supplied by `/api/lms/library-workflow`. Resource Management and Librarian Dashboard require `library_manage`; unauthorized destinations remain visible but disabled. Existing Admin and combined Librarian-role capabilities remain valid. Navigation does not grant permissions.

## Connected resource workflow

1. **Resource Management:** a Librarian/Admin selects an institution course and creates a resource with metadata and reader text or an uploaded document. Existing edit, draft/publication, unpublish and archive actions remain available. Server checks enforce institution, course and file access.
2. **Library Catalogue:** Learners discover Published resources belonging to courses they can access. Search, status/facet filters, sorting and signed cursor pagination use the existing catalogue API. No resources are invented when a list is empty.
3. **Resource Reader:** select a resource from Catalogue, My Library, or the standalone reader's selection list. Opening it uses `/lms/158/Resource%20reader/{resource_id}` and fetches an authorized resource from `/api/lms/features/library/resources/{resource_id}`. The ID survives refresh. The reader displays the resource's text and attached document, with an open-document link. Draft or inaccessible resource IDs are rejected for Learners.
4. **Save/borrow/return:** saving adds a Saved entry to My Library; borrowing creates an active loan with a server-calculated due date. Saving an active loan preserves Borrowed status and its due date. Repeating a borrow preserves the existing due date instead of extending it. Returning an active loan removes it from My Library and updates active-loan counts. Repeating the same action is idempotent; returning without a loan is rejected.
5. **My Library:** displays the current user's saved resources and active loans, with stored due dates. If a borrowed resource is unpublished or archived, its loan remains returnable, but body, attachment and original description are redacted and its reader action is disabled. Withdrawn saved-only resources are hidden. Guessed reader/file IDs do not bypass publication/access checks.
6. **Librarian Dashboard:** shows database-derived resource inventory, Published count, Saved-entry count, active Borrowed loans and overdue Borrowed loans. The usage list counts unique resource/user loan records, including previous Returned records; it is not a fabricated read count or a historical action-event count.

## Policy and synchronization

Course, LibraryResource, LibraryLoan and Attachment records remain the source of truth. No live demo records or schema migration were added. The server supplies the navigation, capability flags, metric labels and configured loan duration. Static interface labels remain code.

Set the process environment variable `LIBRARY_LOAN_DAYS` to a positive integer before starting Django to configure the policy. The server default is 14 days. This setting is not read from the AI-only `backend/.env` loader. Restart Django after changing it. New loans use the current policy; existing active due dates are preserved. The UI shows the server policy rather than a fixed client duration.

Successful library actions refresh the reader, current lists and relevant summary. Moving between pages fetches persisted records; window focus and Refresh library reload the view. Other open sessions receive changes on their next refresh/focus/request; there is no real-time push. Loan mutations lock the resource and existing loan row within a transaction; production PostgreSQL concurrency still needs integration validation.

## Verification and limits

`lms.test_library_workflow` verifies create/publish/read/save/borrow/return, My Library membership, dashboard counts, configurable loan duration, repeated-action invariants, withdrawn-resource redaction/return, navigation order and denial for Learners/unrelated accounts. Test records are created only in Django's isolated test database. Frontend tests cover the five-page order and Librarian capability gates.

This pass does not add reservations, physical-copy inventory, fines/payments, renewal requests, annotations or historical reading analytics. Those require separate policies and data models. Existing private-file storage and document rendering still depend on the configured deployment adapters.


## Reader navigation correction — 25 November 2026

Opening Resource Reader without a selected resource now shows a dedicated reading entry screen, with actions for Library Catalogue and My Library. It no longer repeats the catalogue grid. Selecting a real resource still opens its existing authorized reader route; no resource is selected or fabricated automatically.
