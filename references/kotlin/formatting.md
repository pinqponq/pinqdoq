# Code Formatting & Structure

This file covers two layout rules. State-update hoisting (unconditional fields outside conditional branches) lives in `../../rules/common.md`, and Compose preview standards live in `../../rules/kotlin-conventions.md` — they are not repeated here.

## Empty Line After Closing Braces and Parentheses

Place an empty line after a closing `}` or `)` block, unless:
- It is immediately followed by another closing brace or the end of the file.
- The next line is directly related (e.g., a chained call like `.collect()`, `.map()`, or an extension function).

```kotlin
// CORRECT - empty line separates unrelated statements
fun loadData() {
    launch(dispatcher = ioDispatcher) {
        val data = fetchDataUseCase()
        setState { copy(data = data) }
    }

    setState { copy(isInitialized = true) }
}

is Event.ClickLoginButton -> {
    validateCredentials()
}

is Event.ClickSignUpText -> {
    setEffect { Effect.Navigation.NavigateToRegisterScreen }
}

// CORRECT - no empty line because the next line is a chained/related call
viewModel.effect.onEach { effect ->
    when (effect) { ... }
}.collect()

fetchItemsUseCase()
    .filter { it.isActive }
    .map(itemUiMapper::mapToItemUiModel)

// WRONG - missing empty line after closing brace
fun loadData() {
    launch(dispatcher = ioDispatcher) {
        val data = fetchDataUseCase()
        setState { copy(data = data) }
    }
    setState { copy(isInitialized = true) }
}

is Event.ClickLoginButton -> {
    validateCredentials()
}
is Event.ClickSignUpText -> {
    setEffect { Effect.Navigation.NavigateToRegisterScreen }
}
```

---

## ScreenContent Component Extraction

**Strict rule: A ScreenContent file must only contain the ScreenContent composable itself and its `@Preview` — nothing else.** Every custom composable used within the screen content must live in its own file inside the feature's `component/` folder. This applies regardless of how small or closely related the composables are. The folder must be named `component/` (singular, no trailing "s").

**When to extract:**
- The screen has multiple logical sections (e.g., a form with personal info fields, address fields, and payment fields).
- A group of UI elements shares the same context (e.g., all fields related to "contact info").

**When NOT to extract:**
- The screen is simple — e.g., only a `LazyColumn` and its item composable. In that case, just extract the list item into the `component/` folder.
- Extracting would create a component with only one element.

**One composable per file** — even if two composables are closely related (e.g., a section and its list item), each gets its own file in `component/`.

```
feature/register/
└── presentation/
    ├── RegisterScreen.kt
    ├── RegisterScreenContent.kt       ← ONLY the ScreenContent + preview
    ├── RegisterViewModel.kt
    ├── RegisterContract.kt
    └── component/
        ├── PersonalInfoSection.kt     ← name, surname, email fields
        ├── AddressSection.kt          ← city, district, address fields
        └── ContactInfoSection.kt      ← phone, country code picker
```

```kotlin
// RegisterScreenContent.kt
@Composable
fun RegisterScreenContent(
    state: State<RegisterContract.State>,
    onEventSent: (RegisterContract.Event) -> Unit
) {
    Column {
        PersonalInfoSection(
            name = state.uiState.name,
            surname = state.uiState.surname,
            email = state.uiState.email,
            onEventSent = onEventSent
        )

        AddressSection(
            city = state.uiState.city,
            district = state.uiState.district,
            onEventSent = onEventSent
        )

        ContactInfoSection(
            phoneNumber = state.uiState.phoneNumber,
            selectedCountry = state.uiState.selectedPhoneCountry,
            onEventSent = onEventSent
        )
    }
}
```

```kotlin
// Simple screen — no need to extract sections, just the list item
feature/notifications/
└── presentation/
    ├── NotificationsScreenContent.kt  ← just a LazyColumn
    └── component/
        └── NotificationItem.kt        ← the item composable
```

> The `State<T>` wrapper, `onEventSent`, and the `Contract` structure shown above come from the project's base ViewModel / the deveng-core-kmp library. For those APIs see `../../rules/kotlin-deveng-core.md` and `deveng-core-reference.md`; for the presentation split see `mvi-pattern.md`.
