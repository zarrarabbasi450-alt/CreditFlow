# Frontend architecture

## Boundaries

`src/app` owns routing and layouts, `src/features` owns product workflows, `src/components` owns reusable UI and layout primitives, `src/hooks` owns React Query integration, `src/store` owns client auth state, `src/mocks` owns realistic datasets and MSW handlers, and `src/lib/api/` is the single Gateway boundary.

MSW returns the future Gateway envelope with `success`, `data` or standardized `error`, request and correlation IDs, and pagination metadata. The same handlers run in browser development and Node tests. The Axios client adds bearer authorization, timeout and retry behavior, token refresh, error normalization, and request/correlation IDs. The streaming generator mirrors an SSE token stream through an async iterator so a future EventSource adapter can replace it without changing the AI Studio UI.

## Access model

The shell protects workspace routes and filters navigation for Owner, Admin, Member, and SuperAdmin. Account-scoped mock users carry an `accountId`; the platform user carries the `platform` scope. UI visibility is not a substitute for gateway authorization once real services exist.

## Route model

Public and auth routes are explicit. Workspace product routes share a protected route group and accept one optional feature subsection. Central configuration keeps page composition consistent while dedicated forms own complex validation such as recurrence and image publishing.

## State and accessibility

TanStack Query owns all remote state and mutations. Authentication and development role switching are isolated in the auth provider, which exposes the current user, permissions, tenant, workspace, and refresh lifecycle. Forms use associated labels and inline alert semantics; dialogs and mobile navigation expose names; reduced-motion preferences disable transitions.
