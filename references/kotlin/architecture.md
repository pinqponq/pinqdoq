# Architecture (KMP / Compose)

The standard structure is **Clean Architecture** with an **MVI (Model-View-Intent)** presentation layer.

For the conventions *inside* the `data/` package — Service, DTOs, Mapper, Repository, DI — see `data-layer.md`. This file is the skeleton; that file is the body. For the presentation split, see `mvi-pattern.md`.

## Feature Package Structure

```
feature/{featureName}/
├── data/
│   ├── datasource/remote/
│   │   ├── {Feature}Service.kt
│   │   └── model/
│   │       ├── request/    → {Entity}Request.kt   (only when the feature mutates)
│   │       ├── response/   → {Entity}Response.kt
│   │       └── mapper/     → {Entity}Mapper.kt
│   ├── repository/
│   │   └── {Feature}RepositoryImpl.kt
│   └── di/
│       └── {Feature}DataModule.kt
├── domain/
│   ├── model/              → {Entity}.kt (clean names, no suffix)
│   ├── repository/
│   │   └── {Feature}Repository.kt (interface)
│   ├── usecase/
│   │   └── {Verb}{Entity}UseCase.kt
│   └── di/
│       └── {Feature}DomainModule.kt
└── presentation/
    ├── {Feature}Screen.kt
    ├── {Feature}ScreenContent.kt
    ├── {Feature}ViewModel.kt
    ├── {Feature}Contract.kt
    ├── component/          → feature-specific composables (one per file)
    ├── model/
    │   ├── {Entity}UiModel.kt
    │   └── mapper/
    │       └── {Entity}UiMapper.kt
    └── di/
        └── {Feature}PresentationModule.kt
```

## Layer Dependency Rule

- Application/Presentation depends only on Domain.
- Domain depends on nothing outward — only on other Domain modules.
- The data layer implements domain-layer interfaces; the domain never sees a DTO or a service.

## Data Flow (Unidirectional)

```
User interaction
  → ScreenContent emits Event via onEventSent(...)
  → Screen forwards to viewModel.setEvent(event)
  → ViewModel.handleEvents(event)
  → setState { copy(...) }            OR   setEffect { Effect.Navigation... }
  → StateFlow updated                      Channel sends one-time effect
  → Screen collects state                  Screen collects effect in a LaunchedEffect
  → ScreenContent recomposes               navigation / side effect runs
```

State flows down, events flow up. The UI never reaches into the ViewModel directly, and the ViewModel never reaches into the UI. This invariant is what makes every feature testable and predictable.

> The exact base-class APIs (`setState` / `setEffect` / `setError` / the async `launch` wrapper, pagination loaders, dispatcher injection) come from the project's base ViewModel / the deveng-core-kmp library — see `../../rules/kotlin-deveng-core.md` and `deveng-core-reference.md`. This document covers the structure those APIs plug into, not the APIs themselves.
