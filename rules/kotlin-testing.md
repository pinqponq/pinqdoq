---
paths: ['**/*.kt', '**/*.kts']
---

# Kotlin / KMP — Testing

Extends `common.md`. How Android and Kotlin Multiplatform code is tested: the stack, where tests live, what every change must cover, and how UI changes are proven. Worked examples and setup recipes: `.pinq-doq/references/kotlin/testing.md`. Aligned with Google's official Android `testing-setup` skill (github.com/android/skills), translated to KMP.

---

## Stack

| Concern | Use | Not |
|---|---|---|
| Framework & assertions | `kotlin.test` (`@Test`, `@BeforeTest`, `assertEquals`) | JUnit 5 (does not run in `commonTest`) |
| Coroutines | `kotlinx-coroutines-test` (`runTest`, `UnconfinedTestDispatcher`, `Dispatchers.setMain`) | real dispatchers, `delay`-based waiting |
| Flows / effects | Turbine (`flow.test { awaitItem() }`) | collecting into lists with sleeps |
| Test doubles | hand-written **fakes** | MockK (JVM-only); Mokkery only when a fake is impossible |
| Compose behavior | Compose Multiplatform UI test (`runComposeUiTest`) | Espresso, Robolectric |
| Screenshots | Roborazzi (`captureRoboImage`) on the desktop JVM | device screenshots as the only check |
| Coverage | Kover | Jacoco |

---

## Where tests live

- `commonTest` — ViewModels, use cases, repositories, mappers, fakes. Must stay platform-free so it runs on every target.
- `desktopTest` (JVM) — Compose UI behavior tests, screenshot tests, and tests needing JVM-only APIs. It is the fast, default target (`./gradlew :<module>:desktopTest`).
- Test packages mirror the code under test. Fakes go in `<package>.fake`, named `Fake<Interface>` (e.g. `feature.login.fake.FakeLoginRepository`).
- Shared test infrastructure (ViewModel environment, core fakes) lives in `commonTest` under `core.testing`.

---

## What every change must test

- **MUST:** a change to ViewModel, use case, repository, or mapper logic adds or updates unit tests for the changed behavior, including the error path.
- **MUST:** a UI change that alters what a state renders updates or adds a screenshot for that state; a change in what a user action sends adds a UI behavior test.
- **MUST:** a bug fix starts with a test that fails without the fix.
- **SHOULD:** a new screen gets screenshot tests for its main states (content, empty, error, loading as applicable) plus one large-font (`fontScale = 1.5`) variant.
- **Do not** unit-test Composables' layout, DI modules, Koin wiring, platform entry points, or generated code.
- A PR states which tests it added and the command that ran them; a PR that cannot be tested says why.

---

## Writing tests

- Test **behavior through public API**: send `Event`s to the ViewModel, assert on `State` and `Effect`. Never reach into private members or add `@VisibleForTesting` hooks.
- Name tests `action_condition_expectedResult` in camelCase segments (e.g. `clickLoginButton_withInvalidEmail_showsEmailErrorWithoutRequestingOtp`).
- Arrange-Act-Assert, one behavior per test. Put constants for test data in a `private companion object`, not as magic literals repeated across tests.
- Build the real use cases around fake repositories; fake only the boundary (repository interfaces, storages, platform seams).
- Inject `CoroutineDispatcher` only where the class already takes one (e.g. `@Dispatcher(IO)`); pass the test dispatcher there. Don't add dispatcher parameters just for tests to ViewModels using `viewModelScope`.
- Compose tests: match by semantics (text from `getString(Res.string.…)`, roles, `hasSetTextAction()`); fall back to `testTag` only when a matcher would need more than three conditions.
- Use a **robot** (`<Screen>Robot`) once a screen has three or more UI tests or shared interaction steps; every robot function returns `this`.
- Screenshot baselines are committed. Re-record them only for an intended UI change and say so in the PR.

---

## Proving UI changes on a device

Tests are required but not sufficient for UI work: run the change on an Android emulator and/or iOS simulator and attach screenshots or a short recording to the PR. Device interaction (taps, rapid repeated taps, scrolling) is scripted with `adb` / Google's `android` CLI (`android screen capture --annotate`, `android layout`) and `xcrun simctl`; "needs a real device" is only acceptable for hardware the emulator cannot provide (camera image quality, real push delivery, store purchases, biometrics).
