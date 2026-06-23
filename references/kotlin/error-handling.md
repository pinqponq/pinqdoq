# Validation Error State (Presentation)

> **Scope.** This document governs **presentation-layer validation state** — the boolean flags a screen reads to decide whether to show an inline error. It is *not* about error signalling in the domain or data layers. There, the rule in `../../rules/common.md` still holds: missing-but-required values throw real exceptions; never use sentinels (`-1`, `0`, `null`, empty string) to signal failure. A `is…Visible` flag is UI display state, not an error sentinel.

Validation errors never flow through the state as a `String?`. Instead:

1. Each distinct error condition is a `Boolean` flag in the `State`, prefixed with `is…Visible` (e.g. `isEmailEmptyErrorVisible`).
2. The ViewModel toggles those flags during validation — it never stores localized strings.
3. The screen content resolves the message at render time:

   ```kotlin
   CustomTextField(
       errorMessage = if (state.isEmailEmptyErrorVisible) {
           stringResource(Res.string.login_email_empty_error)
       } else null,
       // ...
   )
   ```

## Why it matters

This keeps ViewModels free of UI/localization concerns. If the ViewModel held error strings, every locale change and every copy tweak would touch presentation logic. By keeping errors as boolean flags, the ViewModel describes *what happened* and the UI decides *how to phrase it*. Every error string lives in the app module's compose resources.

Use one flag per distinct error condition. Don't collapse "empty" and "invalid format" into a single `isEmailErrorVisible` — give each its own flag (`isEmailEmptyErrorVisible`, `isEmailInvalidErrorVisible`) so the UI can show the right message and tests can distinguish the cases.

## See also

- `mvi-pattern.md` — where these flags live in the Contract's `State`.
- `naming.md` — the `is…Visible` flag convention and string-resource naming.
- `../../rules/kotlin-deveng-core.md`, `deveng-core-reference.md` — `CustomTextField` and other components that take an `errorMessage`.
