# Testing — Setup and Worked Examples

Deep reference for `rules/kotlin-testing.md`. The first working setup is rindle-cmp (`chore/test-infrastructure`); copy from there when adding tests to another KMP app.

## 1. Gradle setup (single KMP module)

`gradle/libs.versions.toml`:

```toml
[versions]
kotlinx-coroutines-test = "1.10.2"
turbine = "1.2.1"
kover = "0.9.11"
roborazzi = "1.76.0"   # pick the release whose ui-test-junit4-desktop matches your Compose Multiplatform minor

[libraries]
kotlinx-coroutines-test = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-test", version.ref = "kotlinx-coroutines-test" }
turbine = { module = "app.cash.turbine:turbine", version.ref = "turbine" }
roborazzi-compose-desktop = { module = "io.github.takahirom.roborazzi:roborazzi-compose-desktop", version.ref = "roborazzi" }

[plugins]
kover = { id = "org.jetbrains.kotlinx.kover", version.ref = "kover" }
roborazzi = { id = "io.github.takahirom.roborazzi", version.ref = "roborazzi" }
```

Module `build.gradle.kts`:

```kotlin
plugins {
    // …
    alias(libs.plugins.kover)
    alias(libs.plugins.roborazzi)
}

kotlin {
    sourceSets {
        commonTest.dependencies {
            implementation(kotlin("test"))
            implementation(libs.kotlinx.coroutines.test)
            implementation(libs.turbine)
        }
        val desktopTest by getting {
            dependencies {
                @OptIn(ExperimentalComposeLibrary::class)
                implementation(compose.uiTest)
                implementation(libs.roborazzi.compose.desktop)
            }
        }
    }
}

// Screenshot baselines and resource lookups depend on the JVM locale; pin it.
tasks.withType<Test>().configureEach {
    systemProperty("user.language", "en")
    systemProperty("user.country", "US")
}
```

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

A `BaseViewModel` that injects collaborators itself (`KoinComponent` + `by inject()`) needs Koin running in tests. Wrap that in one class, used by composition (not inheritance, which kotlin.test does not reliably support across targets):

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
class ViewModelTestEnvironment {
    val testDispatcher: TestDispatcher = UnconfinedTestDispatcher()
    val logologRepository = FakeLogologRepository()
    val conversionAnalyticsClient = FakeConversionAnalyticsClient()
    // … one fake per collaborator BaseViewModel injects

    fun start(additionalModules: List<Module> = emptyList()) {
        Dispatchers.setMain(testDispatcher)
        startKoin { modules(listOf(createBaseViewModelModule()) + additionalModules) }
    }

    fun stop() {
        stopKoin()
        Dispatchers.resetMain()
    }
}
```

`by inject()` is lazy, so only register what the base class resolves on common paths; document the rest (e.g. a sign-out use case resolved only on `UnauthorizedError`) and let the tests that need it pass an extra module.

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
- Effects are a `Channel`: always read them with Turbine inside `effect.test { }`, started **before** sending the event.
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

Configurable results as `var`s, recorded calls as lists, no behavior beyond what the interface promises. Repositories return domain types directly (no `Result` wrappers — see `data-layer.md`), so fakes do too.

## 5. Compose UI behavior test with a robot

```kotlin
@OptIn(ExperimentalTestApi::class)
class LoginScreenRobot(private val composeUiTest: ComposeUiTest) {
    val sentEvents = mutableListOf<LoginContract.Event>()

    fun setContent(uiState: LoginContract.State = LoginContract.State()) = apply {
        composeUiTest.setContent {
            AppTheme { LoginScreenContent(state = State(uiState), onEventSent = { sentEvents += it }) }
        }
    }

    fun typeEmail(email: String) = apply { composeUiTest.onNode(hasSetTextAction()).performTextInput(email) }

    fun clickContinueWithMailButton() = apply {
        val buttonText = runBlocking { getString(Res.string.login_feat_continue_with_mail) }
        composeUiTest.onNodeWithText(buttonText).performClick()
    }
}
```

Test `ScreenContent` (stateless) with a recorded `onEventSent`, never the `Screen` that owns the ViewModel.

## 6. Screenshot test

```kotlin
@Test
fun invalidEmail() = runDesktopComposeUiTest(width = 1080, height = 2400) {
    setContent {
        CompositionLocalProvider(LocalDensity provides Density(density = 2.625f, fontScale = 1f)) {
            AppTheme { LoginScreenContent(state = State(LoginContract.State(email = "not-an-email", isEmailErrorVisible = true)), onEventSent = {}) }
        }
    }
    onRoot().captureRoboImage(filePath = "src/desktopTest/screenshots/login_invalid_email.png")
}
```

Screen-level: main states on a phone canvas plus a `fontScale = 1.5` variant. Google's guidance adds nine window sizes (widths 400/610/900 dp × heights 400/500/1000 dp) — apply it to apps that ship adaptive layouts (tablet/desktop/web), not to phone-only screens.

## 7. Known pitfalls

- **Platform SDKs inside composables** (sign-in buttons, ads, maps) may throw on desktop when their provider was never initialized. Initialize them with placeholder test values once per test JVM (rindle: `TestGoogleAuthProvider.ensureCreated()`), or keep the SDK composable out of `ScreenContent`.
- **iOS test binaries** link CocoaPods frameworks the app gets from the Xcode project; a pod the Gradle cocoapods block does not declare (e.g. `GoogleSignIn` via KMPAuth) makes `iosSimulatorArm64Test` fail to link. Until linker options are added, verify `commonTest` on the JVM targets.
- **Build side effects:** tasks hooked to `assemble*` (like an iOS version sync) can touch tracked files during test runs; don't commit those changes.

## 8. Device scenarios with Maestro

First working setup: rindle-cmp `maestro/` (pinqponq/rindle-cmp#389). Install on the machine with the official script from maestro.dev (needs a JDK); set `MAESTRO_CLI_NO_ANALYTICS=1`.

Layout:

```
maestro/
├── config.yaml              ← which flow folders a directory run includes
├── scripts/run-flow.sh      ← <android|ios> <flow>: picks the booted device, passes APP_ID, writes build/maestro/<platform>/
├── subflows/                ← reusable steps (open-<tab>, seed-<data>, dismiss-interstitials, …)
└── <feature>/<scenario>.yaml
```

Flow skeleton:

```yaml
appId: ${APP_ID}            # Android and iOS bundle ids differ; the runner script passes the right one
name: Gallery bulk delete ignores repeated confirm taps (#377)
tags: [gallery, destructive]
---
- launchApp:
    stopApp: false           # keep the signed-in session
    permissions: { photos: allow, camera: allow }
- runFlow: ../subflows/open-gallery.yaml
- runFlow: ../subflows/remember-newest-media-id.yaml
- runFlow: ../subflows/seed-three-photos.yaml
- runFlow: ../subflows/wait-for-seeded-media.yaml
- startRecording: gallery-bulk-delete
- longPressOn: ${output.newestMediaId}
# …
- tapOn: { text: "Delete", repeat: 3, delay: 50, waitToSettleTimeoutMs: 0 }   # rapid repeated taps
- stopRecording
```

Patterns and pitfalls:

- Platform differences go inside one flow with `runFlow: { when: { platform: iOS }, commands: [...] }`. The iOS simulator has no camera: seed media through the photo-library import (Maestro can drive the system picker) after `xcrun simctl addmedia`.
- Screens that never settle (live camera preview) make every `tapOn` wait for its settle timeout; pass `waitToSettleTimeoutMs: 500` there and avoid `waitForAnimationToEnd`.
- Compose on iOS exposes a container and its child with the same label, so `index` on a repeated selector counts differently per platform. Select by a unique label (e.g. a copied id) instead of by index.
- One-time screens (onboarding, promos) appear depending on account state; close them in a `dismiss-interstitials` subflow guarded by `when: visible`.
- Maestro runs in unattended sessions, where interactive simulator tools are not available.
