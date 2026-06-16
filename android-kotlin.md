---
paths: ['**/*.kt', '**/*.kts']
---

# Android / Kotlin / Compose Standards

Extends `common.md`. These rules apply to all Android and Kotlin Multiplatform projects.

---

## deveng-core-kmp

When the project depends on **deveng-core-kmp**, prefer the library's existing APIs over reimplementing functionality. Before adding UI, camera, platform (dial/clipboard/maps/URL/share/location), permissions, media, or pagination features, read the guide at `.claude/rules/references/deveng-core.md` (full API list in its `deveng-core-reference.md`) and use the core APIs it lists.

---

## File Naming

| Type | Pattern | Example |
|---|---|---|
| Screen | `[Feature]Screen.kt` | `DashboardScreen.kt` |
| ViewModel | `[Feature]ViewModel.kt` | `DashboardViewModel.kt` |
| Contract | `[Feature]Contract.kt` | `DashboardContract.kt` |
| UseCase | `[Action][Entity]UseCase.kt` | `FetchUserStatusTypesUseCase.kt` |

---

## Resource Naming (Android)

- `string.xml` IDs must include a module prefix.

```xml
<!-- ✅ Correct -->
<string name="onboarding_feat_too_much_connection">

<!-- ❌ Wrong -->
<string name="too_much_connection">
```

---

## MVI — State, Event & Effect

### State
- Use descriptive, state-representative names. Never generic names.
  - ✅ `branchDescription`, `userList`, `isRegistrationFormValid`
  - ❌ `description`, `user`, `isFormValid`
- Boolean fields: prefix with `is`, `has`, `should`, `can`.
- Lists: plural form or suffix with `List`.

### Event
- Use action-based, imperative verbs.
  - ✅ `ClickCompanyInfoButton`, `ClickLoginButton`, `EnterPhoneNumber`, `ToggleReceiptOption`
  - ❌ `ClickCompanyInfo`, `PhoneNumber`
- Navigation events: `NavigateToProfileScreen`, `NavigateBack`

### Effect
- Use outcome-based names.
  - Navigation: `NavigateToOtpScreen`
  - UI: `ShowError`, `ShowSuccess`
  - System: `RequestPermission`, `OpenExternalApp`

---

## Jetpack Compose

- Top-level composable: `[Feature]Screen(...)`
- Content composable: `[Feature]ScreenContent(...)`
- Composables must be logic-free. Pass UI instructions, not domain state.

```kotlin
// ❌ Wrong — implies domain logic
isMuted

// ✅ Correct — direct UI instruction
isMutedIconVisible
```

- Visibility states must use positive framing:

```kotlin
// ❌ Wrong
if (state.uiState.isProductListEmpty) { ... }

// ✅ Correct
if (state.uiState.isProductListVisible) { ... }
```

### Preview Standards
- Always wrap previews in `AppTheme`.
- Use preview parameter providers for dynamic data.
- Provide named previews for `empty`, `loading`, `error`, and `success` states.
- Include edge cases: long text, special characters.
- File under `preview/` directory.
- Naming: `[Entity]PreviewProvider`, `Fake[Entity]DataProvider`

---

## Class Structure & Member Ordering

Inside a class, maintain this order:
1. Fields
2. Properties
3. Constructors
4. Public methods
5. Private helper methods

Definitions must appear above their usage sites.

---

## Access Modifiers

- Default everything to `private`.
- Do not expose members unless strictly required.
- Public APIs must be intentional and minimal.

---

## Domain Layer Naming

- ✅ `saveBranchInfo()` — create or update
- ✅ `updateBranchInfo()` — update only
- ✅ `fetchBranchInfo()` — fetch a list or item
- ❌ Avoid `put`, `post` — these expose HTTP implementation details.

---

## Null Safety

- When using `!!`, add an inline comment explaining why it is safe — or refactor to avoid it.

---

## Dependency Management — Internal Libraries

`deveng-core-kmp` and `deveng-networking-kmp` are internal libraries that always exist locally. Never resolve them from Gradle's build cache — always reference them directly from the local file system.

To see live changes from an internal library in a consumer project, include it as a composite build:

```kotlin
// settings.gradle.kts
includeBuild("../deveng-core-kmp") {
    dependencySubstitution {
        substitute(module("global.deveng:core-kmp")).using(project(":deveng-core"))
    }
}
```
