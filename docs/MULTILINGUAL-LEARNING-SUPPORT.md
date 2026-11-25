# Multilingual Learning Support — F164

Updated 25 November 2026. Describes current application source; deployment archives have not been rebuilt.

## Four-page navigation

| Order | Page | Primary audience | Current-app route |
| --- | --- | --- | --- |
| 1 | Language Preference | Learner | `/lms/164/Language%20preference` |
| 2 | Translated Content View | Learner | `/lms/164/Translated%20content%20view` |
| 3 | Translation Queue / Editor | Translator / Reviewer / Coordinator | `/lms/164/Translation%20queue%20%2F%20Editor` |
| 4 | Glossary and Coverage | Coordinator / Admin | `/lms/164/Glossary%20and%20coverage` |

These correspond to the reference ERP's language-preference, translated-content, translation-queue and glossary-coverage destinations. They use the current application backend. Legacy Translation queue and Glossary routes map to their new destinations. The authenticated `/api/lms/language-workflow` supplies labels, audiences, access flags and saved language suggestions. Unavailable destinations remain visible but disabled.

## Connected workflow

1. **Language Preference:** save only the signed-in learner's content language, preserving goals, pace, notifications and interface language. Content language is separate from UI localization. Suggestions come from the current preference and accessible translation/glossary records; users can enter another language instead of relying on a fixed language list. Names are trimmed and exact spelling/case identifies each language.
2. **Translated Content View:** defaults to the saved content language when opened. Browse authorized Published lessons with search, sorting, status filtering and signed pagination. An approved translation is shown when available; otherwise the original is shown explicitly. The original/translation toggle is per lesson. In-progress translation bodies are never returned to learners. Trying another language here does not save the preference automatically.
3. **Translation Queue / Editor:** Translators edit, Reviewers approve, and Coordinators can perform both. Admin and existing Teacher translation capabilities remain available. Translators/Reviewers need an existing course assignment; Coordinator/Admin retain institution scope. Reviewer-only accounts do not receive editing controls. Draft source lessons can be translated, but learner visibility still requires a Published source lesson.
4. **Submit and review:** saving creates/updates the unique lesson/language Translation and marks it In translation. Revisions remove its previous learner approval until reviewed again. The current UI sends source and translation timestamps to reject a stale draft; approval sends the reviewed translation timestamp to reject approval of text changed after it was loaded. Legacy API callers can omit these optional timestamps, so they do not gain the same stale-edit protection. Lesson-row locking coordinates translation saves, approval and source editing.
5. **Source changes:** editing lesson title/body through the content API marks its existing translations In translation. The translation text is preserved for revision, and learners fall back to the original until approval is renewed. Position-only edits do not invalidate translation approval. This rule does not automatically detect direct database changes outside the application API.
6. **Glossary and Coverage:** Coordinator/Admin can add scoped terminology with validated nonblank term, definition and language. Both paginated and legacy glossary reads honor language filtering. Coverage counts Published source lessons and approved translations for the selected language, consistently across reports. It counts approval availability, not linguistic quality. Glossary records remain readable through scoped APIs; creation now requires dedicated `glossary_manage` rather than Teacher/Translator access.

## Synchronization and limits

Preference, Translation, GlossaryTerm and lesson/course records are the source of truth. There are no generated lesson records, fake translations or fixed frontend language catalogues. No migration is required. Mutations, window focus, revisiting a page and Refresh languages fetch updated records; there is no live push to an unattended session. Changing the selected language resets the local translation draft; use Submit or Discard before switching. A typed working language is preserved on focus refresh. Draft translation text remains local until submitted.

Interface language choices and the localization system are unchanged. This feature uses human-entered translations; it adds no machine-translation provider, automatic glossary substitution, document translation, translation version history, rejection-comment workflow or linguistic quality scoring. Coordinators may translate and approve; independent reviewer separation is not enforced.

Four isolated backend tests cover manifest audiences, arbitrary saved languages and preference preservation, translator/reviewer separation, Coordinator submission, approval and re-submission visibility, stale approval/source protection, source-edit invalidation, foreign scope, language-filtered glossary reads and Published-only coverage. Frontend tests cover the requested order and role navigation. Native browser interaction was not performed; see [verification](VERIFICATION.md).

Possible next additions: reviewer rejection comments, versioned translations with source diffs, and translation-quality checks using institution terminology. Each should preserve the existing approval and course-access rules.
