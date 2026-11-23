## 0.1.3

- Refresh generation/editing model choices to all 24 IDs in the current public contracts, with a reproducible local contract generator.
- Omit blank quality/size parameters; preserve explicit saved values and node/widget/output compatibility. Validate DALL-E quality, canvas and output counts before submission.
- Keep URL-based editing, require one reference for DALL-E 2, and reject separate masks that require the multipart API. Static PNG/JPEG/WebP formats remain unchanged.
- Verify all 48 model/operation default requests at the mocked HTTP boundary without paid calls.

# Changelog

## 0.1.2 — 2026-10-19

- Fix stale pending results by refreshing read-only task lookups on every execution.
- Preserve paid/destructive request caching and same-task IDs; no implicit resubmission.

## 0.1.1 — 2026-10-19

- Service-first discovery and exact Ace Registry/source identity.
- Illustrated English/Chinese Applications/API Token onboarding and supported four-field attribution links.
- Explicit stable selection, same-task retrieval and native media examples; current access/price and troubleshooting guidance.
- Respect ComfyUI local cancellation at same-task polling/retry boundaries while preserving accepted task IDs.

The GitHub versioned package and Registry publication are recorded separately. No new model, price, fallback, API permission or dependency is introduced.
