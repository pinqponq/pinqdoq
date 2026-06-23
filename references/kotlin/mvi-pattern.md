# MVI Pattern — State, Contract, and Screen/ScreenContent/ViewModel Split

This file covers the presentation-layer structure. For the feature package skeleton, see `architecture.md`; for the data layer, see `data-layer.md`; for naming, see `naming.md`; for ViewModel event-handling and helper patterns, see `viewmodel-patterns.md`. The concrete base-ViewModel APIs (`setState` / `setEffect` / `setError`, the async wrapper, pagination) live in deveng-core-kmp — see `../../rules/kotlin-deveng-core.md` and `deveng-core-reference.md`.

## Core Principle

**All UI state lives in the Contract. ScreenContent NEVER holds its own state.** Every piece of data displayed or used for UI decisions must come from `state.uiState.*`. There is no `remember { }` or `mutableStateOf()` in ScreenContent for domain/business data.

This is the invariant that keeps features testable and makes recomposition predictable. Once ScreenContent starts holding domain state locally, state drifts out of sync with the ViewModel and bugs become unreproducible.

## Contract Structure

Every feature has exactly one Contract file containing three sealed/data types:

```kotlin
class ProfileContract {

    // 1. EVENTS - What the user does
    sealed class Event : ViewEvent {
        data class Init(val isInit: Boolean) : Event()
        data class EnterDisplayName(val displayName: String) : Event()
        data object ClickSaveButton : Event()
        data object RequestRegionDialogDismiss : Event()
    }

    // 2. STATE - What the UI shows
    data class State(
        val displayName: String = String.EMPTY,
        val isDisplayNameErrorVisible: Boolean = false,
        val isDisplayNameFieldVisible: Boolean = true,
        val regionList: List<RegionUiModel> = emptyList(),
        val selectedRegion: RegionUiModel = DEFAULT_REGION_UI_MODEL
    ) : UiState {
        // Computed properties for derived UI logic
        fun isRegionSelected(region: RegionUiModel): Boolean {
            return selectedRegion == region
        }
    }

    // 3. EFFECTS - One-time side effects
    sealed class Effect : ViewSideEffect {
        sealed class Navigation : Effect() {
            data class NavigateToDetailScreen(
                val itemId: Int
            ) : Navigation()
            data object NavigateBack : Navigation()
        }
    }
}
```

Rules:
- One Contract per feature.
- `Event`, `State`, and `Effect` are nested under the single Contract type.
- State properties always have default values.
- Computed properties (derived from state fields) go inside the `State` class body — not in the ViewModel or the UI.
- Navigation effects are nested under `sealed class Navigation : Effect()`. Non-navigation effects (e.g. open camera, open gallery picker) are direct children of `Effect`.

> For `State` property naming (`is…Visible` instead of `isValid`/`isEmpty`), see the MVI State section in `../../rules/kotlin-naming.md`.

## Wrapping UiState With Loading / Error

The contract's `State` (a `UiState`) is wrapped by the base ViewModel in a generic state holder that adds cross-cutting `isLoading` and error flags. ScreenContent then reads:

- feature data via `state.uiState.*`
- loading via `state.isLoading`
- error via `state.showError`

Treat the wrapper as a black box — its exact shape comes from the base ViewModel in deveng-core-kmp. Do not redefine it per feature, and do not store user-facing error copy in it; see `error-handling.md` and `deveng-core-reference.md`.

## Why This Matters

- **Single source of truth**: only the ViewModel mutates state.
- **Predictability**: given a `State`, the UI always renders the same way.
- **Testability**: test ViewModels by sending events and asserting state.
- **No side effects in UI**: ScreenContent is a pure function of state.

---

## What Goes Where: Screen, ScreenContent, Contract, ViewModel

### Contract (`{Feature}Contract.kt`)

**Purpose**: define the communication protocol between ViewModel and UI.

**Contains**:
- `Event` sealed class — every user action
- `State` data class — every piece of UI data with defaults
- `Effect` sealed class — navigation and one-time side effects

---

### Screen (`{Feature}Screen.kt`)

**Purpose**: wire up the ViewModel, navigation, lifecycle, and state collection. This is the **glue layer**.

**Responsibilities**:
1. Obtain the ViewModel (e.g. via the DI framework).
2. Collect state.
3. Fire the `Init` event on first composition.
4. Listen to effects and handle navigation.
5. Wrap content in the shared loading/error layout.
6. Pass state and the `onEventSent` callback to ScreenContent.

**Template**:

```kotlin
@Composable
fun ProfileScreen(
    navController: NavController,
    viewModel: ProfileViewModel = /* resolve from DI */
) {
    val state = viewModel.getState()

    // 1. Lifecycle: fire the Init event once on first composition
    LaunchedEffect(Unit) {
        viewModel.setEvent(ProfileContract.Event.Init(isInit = true))
    }

    // 2. Effects: collect one-time effects and handle navigation
    LaunchedEffect(Unit) {
        viewModel.effect.onEach { effect ->
            when (effect) {
                is ProfileContract.Effect.Navigation.NavigateToDetailScreen -> {
                    // navigate to the detail destination with effect.itemId
                }
                is ProfileContract.Effect.Navigation.NavigateBack -> {
                    // pop the back stack
                }
            }
        }.collect()
    }

    // 3. Layout: wrap in the shared loading/error layout, then render content
    // StateLayout(...) { ProfileScreenContent(...) }
    ProfileScreenContent(
        state = state,
        onEventSent = { event -> viewModel.setEvent(event) }
    )
}
```

**Rules**:
- No UI layout code here — that belongs in ScreenContent.
- `navController`, external callbacks, and `MutableState` parameters come through here.
- The Screen is the only place that knows about the navigation controller.

---

### ScreenContent (`{Feature}ScreenContent.kt`)

**Purpose**: pure composable UI. Receives state, emits events. That's it.

**Signature**:

```kotlin
@Composable
fun ProfileScreenContent(
    state: State<ProfileContract.State>,
    onEventSent: (event: ProfileContract.Event) -> Unit
)
```

**Rules**:
- **ZERO** local mutable state for domain data (no `remember { mutableStateOf(...) }`).
- **ZERO** side effects (no `LaunchedEffect`, no coroutines).
- **ZERO** navigation logic.
- **ZERO** ViewModel references.
- All data comes from `state.uiState.*`.
- All user actions go through `onEventSent(Contract.Event.SomeEvent(...))`.
- Dialogs are controlled by state (e.g. `isDialogVisible = state.uiState.isRegionDialogVisible`).
- Previews wrap in the app theme and pass `State(Contract.State())` with an empty `onEventSent`.

**Example — how user actions become events**:

```kotlin
// Text input -> Event with new value
CustomTextField(
    value = state.uiState.displayName,
    onValueChange = { displayName ->
        onEventSent(ProfileContract.Event.EnterDisplayName(displayName))
    }
)

// Button click -> Event
CustomButton(
    text = saveButtonText,
    onClick = {
        keyboardController?.hide()
        onEventSent(ProfileContract.Event.ClickSaveButton)
    }
)

// Dialog visibility driven by state
OptionItemLazyListDialog(
    isDialogVisible = state.uiState.isRegionDialogVisible,
    onDismissRequest = {
        onEventSent(ProfileContract.Event.RequestRegionDialogDismiss)
    }
)
```

**Preview Standard**:

```kotlin
@Preview
@Composable
fun ProfileScreenContentPreview() {
    AppTheme {
        ProfileScreenContent(
            state = State(ProfileContract.State()),
            onEventSent = {}
        )
    }
}
```

---

### ViewModel (`{Feature}ViewModel.kt`)

**Purpose**: the only writer of state. Handles every event, runs use cases, emits effects.

It extends the project's base ViewModel and uses its `setState` / `setEffect` / `setError` and async wrapper. Those APIs and the event-handling templates are documented in `../../rules/kotlin-deveng-core.md` and `deveng-core-reference.md` — do not re-derive them per feature.

---

## Summary Table

| Concern              | Screen              | ScreenContent       | Contract            | ViewModel           |
| -------------------- | ------------------- | ------------------- | ------------------- | ------------------- |
| ViewModel reference  | Yes                 | No                  | N/A                 | N/A                 |
| NavController        | Yes                 | No                  | N/A                 | N/A                 |
| State collection     | Yes (`getState()`)  | Receives as param   | Defines it          | Updates it          |
| Event emission       | Passes callback     | Calls `onEventSent` | Defines events      | Handles events      |
| Effect handling      | Yes (LaunchedEffect)| No                  | Defines effects     | Emits effects       |
| UI layout            | No                  | Yes                 | N/A                 | N/A                 |
| Business logic       | No                  | No                  | N/A                 | Yes                 |
| Error/Loading UI     | State layout wrapper| No                  | N/A                 | `setError/Progress` |
