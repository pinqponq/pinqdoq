# ViewModel Patterns — Event Handling & Helpers

This file covers the *portable* ViewModel patterns: how to shape event handling and private helpers. For the Contract / State / Screen / ScreenContent split that the ViewModel plugs into, see `mvi-pattern.md`.

The base ViewModel itself — `setState` / `setEffect` / `setError`, the async `launch` wrapper, dispatcher injection, and `PaginatedFlowLoader` — comes from the deveng-core-kmp library. This file does **not** re-document those APIs. For them, see `../../rules/kotlin-deveng-core.md` and `deveng-core-reference.md`.

## What the Base ViewModel Gives You (concept)

A feature ViewModel extends the project's base ViewModel, typed on its `State` / `Event` / `Effect`. From the base you get:

| Capability | What it does |
|---|---|
| State writer | Thread-safe `copy(...)` update of the current state. |
| Effect emitter | Sends a one-time effect (navigation, toast) the Screen consumes once. |
| Error / progress hooks | Toggle loading and surface errors without per-call boilerplate. |
| Async wrapper | Runs a suspend block on an injected dispatcher with automatic progress + error handling. |

Treat these as given. The exact method names and signatures live in the deveng-core reference — do not re-spell them here, and do not hand-roll a parallel base class.

## handleEvents — the Single Entry Point

Every ViewModel overrides one `handleEvents(event)` and dispatches on the sealed `Event` type. The body of each branch is small: it either updates state, emits an effect, or kicks off an async block. Keep real logic in private helpers (below), not inline in the `when`.

```kotlin
override fun handleEvents(event: Event) {
    when (event) {
        is Event.Init -> { /* load initial data */ }
        is Event.EnterText -> { /* immediate state update */ }
        is Event.ClickSubmitButton -> { /* validate + action / navigate */ }
        Event.ClickSecondaryAction -> { /* navigate */ }
    }
}
```

## Event-Handling Shapes

Four recurring branch shapes cover almost every event.

### 1. Init — Data Loading

Load on `Init`, map to UI models, write to state. Run inside the base async wrapper so progress and errors are handled for you.

```kotlin
is Event.Init -> {
    launch(dispatcher = ioDispatcher) {
        val items = fetchItemsUseCase()
        val mapped = items.map(itemUiMapper::mapToUiModel)
        setState { copy(itemList = mapped) }
    }
}
```

### 2. Input — Immediate State Update

Input events write straight to state, no async. Do any cheap normalization here (trim, strip whitespace) — heavier sanitization belongs to a core helper (see `deveng-core-reference.md`).

```kotlin
is Event.EnterText -> {
    setState { copy(text = event.text.trim()) }
}
```

### 3. Click — Action or Navigation

A bare navigation click just emits an effect. An action click validates first, then runs the work and navigates on success.

```kotlin
// Simple navigation
Event.ClickSecondaryAction -> {
    setEffect { Effect.Navigation.NavigateToNextScreen }
}

// Action with validation
is Event.ClickSubmitButton -> {
    launch(dispatcher = ioDispatcher) {
        val isValid = validateInput()
        if (isValid) {
            submitUseCase(currentState.text)
            setEffect { Effect.Navigation.NavigateToNextScreen }
            hideErrors()
        }
    }
}
```

### 4. Dialog — Toggle Visibility

Dialog open/dismiss/select are pure state writes flipping a `is…Visible` boolean. Selection events both apply the choice and close the dialog in one `copy`.

```kotlin
is Event.ClickPicker -> {
    setState { copy(isPickerDialogVisible = true) }
}

is Event.RequestPickerDismiss -> {
    setState { copy(isPickerDialogVisible = false) }
}

is Event.SelectOption -> {
    setState {
        copy(
            selectedOption = event.option,
            isPickerDialogVisible = false
        )
    }
}
```

## Internal Tracking State (Non-UI)

Values the ViewModel needs only for its own bookkeeping — never rendered, never read by ScreenContent (e.g. `message.id`, `trackId`) — are **not** Contract State. Hold them as a `private var` on the ViewModel instead of adding them to `State`. See the "Non-Displayed State Stays in the ViewModel" section in `mvi-pattern.md` for the rule and an example.

## Private Helper Functions

Extract anything non-trivial out of `handleEvents` into well-named private functions. Common shapes:

```kotlin
// Validation — returns Boolean, sets the error flag as a side effect
private fun validateInput(): Boolean {
    val isValid = currentState.text.isNotBlank()
    if (!isValid) {
        setState { copy(isInputErrorVisible = true) }
    }
    return isValid
}

// Async loader — a suspend function called from an async block
private suspend fun loadDetail(itemId: Int) {
    val detail = fetchItemDetailUseCase(itemId)
    setState { copy(itemName = detail.name) }
}

// Cleanup helper — reset a group of flags in one place
private fun hideErrors() {
    setState {
        copy(
            isInputErrorVisible = false,
            isSecondaryErrorVisible = false
        )
    }
}
```

Conventions:
- A `validate…` helper returns `Boolean` and sets the relevant `is…Visible` flag; the caller branches on the return. (Error state is a boolean flag, never a stored string — see `../../rules/kotlin-conventions.md`.)
- `suspend` loaders are called from the base async wrapper, never started with a raw coroutine builder.
- Group related flag resets into one cleanup helper instead of scattering `copy(...)` calls.

## Pagination

For paginated lists use the deveng-core `PaginatedFlowLoader` rather than hand-rolling page tracking. The loader produces a paginated state you mirror into your feature state. Setup, page-source wiring, and the state model are documented in `../../rules/kotlin-deveng-core.md` and `deveng-core-reference.md` — do not reimplement pagination state in the ViewModel.

## File-Level Private Constants

Pull magic numbers out as file-level private constants, named so the value's meaning is in the identifier:

```kotlin
private const val PAGE_SIZE = 10
private const val ROW_COUNT = 5
```
