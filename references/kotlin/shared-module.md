# Shared Module

When and how to use a `shared` module instead of putting code in a feature. The terse rule is in `../../rules/kotlin-architecture.md`; this is the decision checklist, package structure, and examples.

## Reuse before create

**Before adding any service, model, mapper, or use case, check whether it already exists** — look in `shared/` first, then in the feature you'd expect it in. If an equivalent is already in `shared/`, **depend on it; do not create a second copy.** Duplicating an artifact that already exists in `shared/` is a defect, not a new artifact. When unsure, grep `shared/` for the concept name (e.g. `Auth`, `Profile`) before generating anything.

## When to put something in shared

Put an artifact in `shared` when two or more feature modules use it — **or, as part of the work you're doing right now, will use it and you can name the second feature.** The trigger is concrete reuse you can point to. Ask:

> *"Is this exact service method (or data model, or use case) used by two or more feature modules — or will it be, in the work I'm doing now, by a second feature I can name?"*

- ✅ **Yes, and you can name the second consumer** → put it in `shared` instead of building it twice.
- ❌ **"Same backend service / API"** → not a reason on its own.
- ❌ **"Might be reused someday"** → speculative. Keep it feature-local and **promote later** (below).

Evaluate **per artifact**: the same **service method** (e.g. `loginDashboard()`), the same **data model** (e.g. `LoginRequest`), or the same **use case**.

### Counter-example (same API, different features → NOT shared)

Three endpoints on the same API — `POST /api/DashboardUser/loginDashboard`, `POST /api/DashboardUser/registerDashboard`, `POST /api/DashboardUser/verifyCode` — used only by login, register, and otp respectively. No artifact is used by two features → integrate in **feature/login**, **feature/register**, and **feature/otp**; do not introduce shared.

## Promote later (the default path)

Default to feature-local. When a **second** feature genuinely needs an existing feature-local artifact, **promote it to `shared/`**: move the artifact, then repoint both features' imports and DI. Promotion is the normal, expected path — do **not** pre-emptively put single-use code in `shared` just to avoid it.

## Structure

The shared module is **not** feature-packaged: it has no feature name in the path and contains only `data`, `domain`, and `presentation` layers.

- **Path**: `composeApp/src/commonMain/kotlin/shared` (adjust to the project's common source root).
- **Packages**: `shared.data`, `shared.domain`, `shared.presentation` (and subpackages such as `shared.data.datasource.remote`, `shared.domain.repository`, `shared.presentation.model`).

```
shared/
├── data/
│   ├── datasource/remote/   → services (e.g. AuthService, ProductsService) + request/response models
│   ├── repository/          → impls (e.g. AuthRepositoryImpl, ProductsRepositoryImpl)
│   └── di/SharedDataModule.kt
├── domain/
│   ├── repository/          → interfaces (e.g. AuthRepository, ProductsRepository)
│   ├── usecase/             → use cases (e.g. LoginUseCase, FetchProductsUseCase)
│   └── di/SharedDomainModule.kt
└── presentation/
    ├── model/, component/   → shared UI models / components
    └── di/SharedPresentationModule.kt
```

## Naming under shared

The shared folder can contain **multiple** repositories, services, and use cases — not a single "SharedRepository" or "SharedService". Give each a **domain/concept name** (`AuthRepository`, `AuthService`, `AuthRepositoryImpl`; `ProductsRepository`, `ProductsService`).

Only the **DI modules** use the `Shared` prefix: `SharedDataModule`, `SharedDomainModule`, `SharedPresentationModule`. Register them in `initKoin.kt` if not already present.

## Generating shared code

The pinq-doq scripts and the `api-endpoint-integration` skill take a `--shared` flag (and `--entity <Concept>` where the script needs the class name) so generated files land under `shared/` with `shared.*` packages. See `../../scripts/README.md`.
