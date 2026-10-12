# Testing — Setup and Worked Examples

Deep reference for `rules/kotlin-testing.md`. The shared test infrastructure ships with deveng-core-kmp: the `global.deveng.testing` Gradle plugin and the `global.deveng:core-testing-kmp` library (test environment, fakes, robot base, screenshot defaults, string escape check). First user: rindle-cmp.

## 1. Gradle setup (single KMP module)

One line in the module's `plugins` block turns the whole setup on:

```toml
# gradle/libs.versions.toml — same version as global.deveng:core-kmp
[plugins]
deveng-testing = { id = "global.deveng.testing", version.ref = "devengCoreKmp" }
```

```kotlin
// root build.gradle.kts
plugins {
    alias(libs.plugins.deveng.testing) apply false
}

// module build.gradle.kts — by id: the root already loaded it with its version, and an id without
// a version also resolves when deveng-core-kmp is a local composite build
plugins {
    // …
    id("global.deveng.testing")
}
```

The plugin (only on Kotlin Multiplatform modules) applies Kover and Roborazzi, adds `kotlin-test` and `core-testing-kmp` to `commonTest` (which brings `kotlinx-coroutines-test`, Turbine and, on desktop, Compose UI test) and `roborazzi-compose-desktop` to `desktopTest`, and pins every `Test` task to the `en_US` locale so screenshot baselines and string lookups match on every machine. Do not declare those dependencies or plugins again; keep only project-specific test dependencies (e.g. `multiplatform-settings-test`). The root `apply false` line replaces separate `kover` / `roborazzi` entries there, so the plugins load once.

Kover provides a variant per JVM target automatically (`koverHtmlReportDesktop`); do not `createVariant("desktop")` — the name is reserved.

Commands:

| Command | Purpose |
|---|---|
| `./gradlew :composeApp:desktopTest` | all `commonTest` + `desktopTest` tests on the JVM |
| `./gradlew :composeApp:testDebugUnitTest` | `commonTest` on the Android JVM |
| `./gradlew :composeApp:verifyRoborazziDesktop` | compare screenshots to committed baselines (writes `*_compare.png` on mismatch) |
| `./gradlew :composeApp:recordRoborazziDesktop` | re-record baselines |
| `./gradlew :composeApp:koverHtmlReportDesktop` / `koverLogDesktop` | coverage |

## 2. ViewModel test environment

`core.testing.ViewModelTestEnvironment` (core-testing) runs a deveng-core `BaseViewModel` outside the app: `start()` sets `Dispatchers.Main` to `testDispatcher` (unconfined) and replaces the process-wide `ViewModelInterceptors` registry with its `RecordingInterceptor` plus the interceptors you pass; `stop()` empties the registry and resets `Main`. Use it by composition (not inheritance, which kotlin.test does not reliably support across targets):

```kotlin
private val environment = ViewModelTestEnvironment()

@BeforeTest fun setUp() = environment.start()
@AfterTest fun tearDown() = environment.stop()
```

- `environment.recordingInterceptor.recordedEvents` / `recordedEffects` / `recordedErrors` / `recordedSilentErrors` show what every view model reported to the interceptors, each with the view model's name. `RecordingInterceptor(errorDecision = ErrorDecision.HANDLED)` passed to `start` lets a test act as an app interceptor that swallows errors.
- `environment.errorPrinter` is a `FakeErrorPrinter` (prints the exception message) for view models that take an `ErrorPrinter`.
- App-specific interceptors (logging, analytics, session) that need Koin: the app keeps a thin wrapper that starts Koin with fakes, then calls `start(additionalInterceptors = listOf(…))` (rindle: `RindleViewModelTestEnvironment`). Register only what common paths resolve; let tests that need more pass an extra module.

## 3. ViewModel test

```kotlin
class LoginViewModelTest {
    private val environment = ViewModelTestEnvironment()
    private val loginRepository = FakeLoginRepository()

    @BeforeTest fun setUp() = environment.start()
    @AfterTest fun tearDown() = environment.stop()

    @Test
    fun clickLoginButton_withValidEmail_navigatesToOtpScreen() = runTest {
        loginRepository.loginOtpSent = LoginOtpSent(remainingTime = 90)
        val viewModel = createViewModel()

        viewModel.effect.test {
            viewModel.setEvent(Event.EnterEmail(email = VALID_EMAIL))
            viewModel.setEvent(Event.ClickLoginButton)

            assertEquals(Effect.Navigation.NavigateToOtpScreen(credentialInfo = expectedCredentialInfo), awaitItem())
        }
        assertFalse(viewModel.currentState.isLoading)
    }

    private fun createViewModel() = LoginViewModel(
        ioDispatcher = environment.testDispatcher,
        sendLoginOtpUseCase = SendLoginOtpUseCase(loginRepository = loginRepository),
        // real use cases around fakes
    )
}
```

- Synchronous state changes can be asserted directly on `currentUiState` / `currentState` because the dispatcher is unconfined.
- Effects are a `Channel`: always read them with Turbine inside `effect.test { }`, started **before** sending the event. For one event and one effect, `viewModel.awaitEffectAfterEvent(event)` (core-testing) does exactly that; `viewModel.testUiStates { … }` runs Turbine over the distinct `uiState` values.
- Errors: throw the same exception type the networking layer throws (`DevengException(DevengUiError.NotFoundError(...))`) from the fake.

## 4. Fakes

```kotlin
class FakeLoginRepository : LoginRepository {
    var loginOtpSent = LoginOtpSent(remainingTime = DEFAULT_REMAINING_TIME_SECONDS)
    var sendLoginOtpFailure: Exception? = null
    val sentOtpIdentifiers = mutableListOf<String>()

    override suspend fun sendLoginOtp(identifier: String): LoginOtpSent {
        sentOtpIdentifiers += identifier
        sendLoginOtpFailure?.let { failure -> throw failure }
        return loginOtpSent
    }
}
```

Configurable results as `var`s, recorded calls as lists, no behavior beyond what the interface promises. Fakes for deveng-core interfaces come with core-testing — `FakeErrorPrinter`, `FakeTempFileRepository` (in memory) and, on desktop, `FakePermissionsController` (all in `core.testing.fake`); never copy them into a project. A library that adds an interface ships its fake with it. Repositories return domain types directly (no `Result` wrappers — see `data-layer.md`), so fakes do too.

## 5. Compose UI behavior test with a robot

Robots extend `core.testing.ScreenRobot<Event>` (core-testing, desktop): it keeps `sentEvents`, records them through `recordEvent`, and resolves string resources with `resolveString`.

```kotlin
@OptIn(ExperimentalTestApi::class)
class LoginScreenRobot(composeUiTest: ComposeUiTest) : ScreenRobot<LoginContract.Event>(composeUiTest) {

    fun setContent(uiState: LoginContract.State = LoginContract.State()) = apply {
        composeUiTest.setContent {
            AppTheme { LoginScreenContent(state = State(uiState), onEventSent = ::recordEvent) }
        }
    }

    fun typeEmail(email: String) = apply { composeUiTest.onNode(hasSetTextAction()).performTextInput(email) }

    fun clickContinueWithMailButton() = apply {
        composeUiTest.onNodeWithText(resolveString(Res.string.login_feat_continue_with_mail)).performClick()
    }
}
```

Test `ScreenContent` (stateless) with a recorded `onEventSent`, never the `Screen` that owns the ViewModel.

## 6. Screenshot test

```kotlin
@Test
fun invalidEmail() = runDesktopComposeUiTest(width = PHONE_SCREENSHOT_WIDTH_PX, height = PHONE_SCREENSHOT_HEIGHT_PX) {
    setContent {
        CompositionLocalProvider(LocalDensity provides Density(density = PHONE_SCREENSHOT_DENSITY, fontScale = 1f)) {
            AppTheme { LoginScreenContent(state = State(LoginContract.State(email = "not-an-email", isEmailErrorVisible = true)), onEventSent = {}) }
        }
    }
    onRoot().captureRoboImage(filePath = screenshotPath(name = "login_invalid_email"))
}
```

The canvas, density, `LARGE_FONT_SCALE` and `screenshotPath` come from `core.testing` (core-testing, desktop). Screen-level: main states on a phone canvas plus a `fontScale = LARGE_FONT_SCALE` variant. Google's guidance adds nine window sizes (widths 400/610/900 dp × heights 400/500/1000 dp) — apply it to apps that ship adaptive layouts (tablet/desktop/web), not to phone-only screens.

## 7. String resource escapes

Compose resources show `\'` and `\"` literally (only `\uXXXX`, `\n`, `\t` and `\\` are converted). Every project with Compose resources adds the shared check once in `desktopTest`:

```kotlin
class AppComposeResourceStringEscapeTest : ComposeResourceStringEscapeTest()   // core.testing.resources
```

It scans every `strings.xml` under `src/commonMain/composeResources` (pass another path to the constructor for a different module layout) and fails with the file, key and escape it found.

## 8. Known pitfalls

- **Platform SDKs inside composables** (sign-in buttons, ads, maps) may throw on desktop when their provider was never initialized. Initialize them with placeholder test values once per test JVM (rindle: `TestGoogleAuthProvider.ensureCreated()`), or keep the SDK composable out of `ScreenContent`.
- **iOS test binaries** link CocoaPods frameworks the app gets from the Xcode project; a pod the Gradle cocoapods block does not declare (e.g. `GoogleSignIn` via KMPAuth) makes `iosSimulatorArm64Test` fail to link. Until linker options are added, verify `commonTest` on the JVM targets.
- **Build side effects:** tasks hooked to `assemble*` (like an iOS version sync) can touch tracked files during test runs; don't commit those changes.
