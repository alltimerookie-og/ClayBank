# ADR 0006 — No auth UI for the hackathon; auth-shaped middleware instead

**Status:** Accepted · **Date:** 2026-10-31

## Context

The prototype includes a full sign-in flow (Google / Apple / email + password). Real auth (OIDC redirect flows, token refresh, password reset) is a week of work producing zero demo value, and multi-account sync is not needed for a one-user, one-device hackathon.

## Decision

For the hackathon build:

- The backend ships a **fixed `DEV_TOKEN`** accepted as `Authorization: Bearer DEV_TOKEN`.
- A **`X-Device-Id`** header middleware resolves the request to one **seeded user**; that user owns all saves/folders/notes.
- This keeps dates honest: API responses already require a bearer; routes enforce user scoping; the seeded user is a real row, not a null.

**Auth-shaped by design.** The bearer-token shape is exactly what a future JWT keeps (`auto Bearer <token>` swaps in one middleware). The sign-in screens are not deleted from the product: they are **documented as deferred in `PRD.md` §11 and `Phases.md` (post-hackathon item 5)**, so the deferred scope exists on paper even though no screen is built now.

## Rejected alternatives

- **Skip auth entirely** (no middleware): the API would be user-less, and adding real auth later would touch every route — the exact retrofit this ADR prevents.
- **Local-only mode, no accounts** until "real auth": breaks the demo story (sync exists; it's the partial-replica claim's foundation).
- **Firebase/Clerk now:** resolves auth at the cost of a dependency and vendor rewiring that the JWT swap gets for free later.

## Consequences

- `Phases.md` Phase 1 implements the middleware + seeding.
- Any future "multi-device" story must still pass through this same middleware contract; only the credential factory changes.
- Rules: no user-inventing UI in the hackathon build (no "current user" row in Settings is fine; Settings keeps a sync-state row instead).
