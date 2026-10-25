# New product starter

A new product starts from two template repos and the `pinq_new-product` skill, not from an empty project. The templates contain the parts Rindle proved in production, built on the shared libraries (deveng-core-kmp, deveng-networking-kmp, pinqnuqets). Their own CI keeps them compiling, so the skill only copies and fills them in instead of generating hundreds of files.

| Part | Repo | What it is |
|---|---|---|
| Mobile template | `pinqponq/kmp-app-template` | Compose Multiplatform app (Android, iOS), green CI on every PR |
| Backend template | `pinqponq/backend-service-template` | .NET User/Auth service on pinqnuqets packages; the mobile template runs against it |
| Skill | `skills/pinq_new-product` + `scripts/new_product.py` | Copies a template, fills identity, keys, modules and theme, checks for leftovers |

## 1. Mobile template

Same layout as Rindle (`composeApp/src/commonMain/kotlin/core|feature|shared`, `iosApp/`), so every pinq-doq rule and script applies unchanged.

### Features

| Feature | Rindle source (develop) | Shared library it uses |
|---|---|---|
| Login, register, OTP | `feature/login`, `feature/register`, `feature/otp` | deveng-networking-kmp auth/session kit (pinqponq/org#216) |
| Google sign-in | `feature/login/presentation/component/SocialLoginButtons*` (kmpauth) | deveng-networking-kmp auth/session kit |
| Logout, account deletion (store requirement) | `feature/profile/presentation/settings`, `feature/profile/presentation/privacysecurity` (`DeleteAccountUseCase`) | deveng-networking-kmp auth/session kit |
| Onboarding | `feature/onboarding` | deveng-core UI components (deveng-core-kmp#86) |
| Profile: edit user info | `feature/profile/presentation/userinfo` | deveng-core UI components |
| Settings: language, notification permission, privacy and security | `feature/profile/presentation/settings`, `feature/profile/presentation/notifications`, `feature/profile/presentation/privacysecurity` | deveng-core language and deep link (deveng-core-kmp#87) |
| Paywall | `feature/premiumsubscription`, `core/subscription` | deveng-core subscription module (deveng-core-kmp#83) |

### Infrastructure

| Part | Rindle source | Shared library |
|---|---|---|
| BaseViewModel and interceptors | `com/deveng/rindle/core/presentation/baseviewmodel` | deveng-core (deveng-core-kmp#82) |
| Networking setup, base URL | `shared/domain/usecase/InitializeNetworkingUseCase.kt`, `core/Constants.kt` | deveng-networking-kmp |
| Push token registration | `core/data/datasource/remote/FirebaseDeviceTokenService.kt`, `core/data/repository/FirebaseDeviceTokenRepositoryImpl.kt` | deveng-networking-kmp auth/session kit |
| Deep link | `core/linking` | deveng-core (deveng-core-kmp#87) |
| Analytics, attribution | `core/analytics`, `core/attribution` | deveng-core (deveng-core-kmp#84) |
| pinqloq logging | `core/logolog` | pinqloq SDK |
| Test setup and Maestro kit | `composeApp/src/*Test`, `maestro/` | deveng-core-testing (deveng-core-kmp#85) |

Optional modules, off by default: ads (deveng-core-kmp#84), home screen widget (deveng-core-kmp#88, `references/widget/widget-setup.md`), background upload (deveng-core-kmp#89).

### Rules for the template

- No product code. Copy, colors and the app icon are neutral; Rindle's couple, gallery and chat features stay in Rindle.
- Library versions are the newest released ones in `gradle/libs.versions.toml`; Dependabot opens the bump PRs and CI must pass before they merge.
- Signing passwords and keystore paths live in a gitignored `keystore.properties` read by `build.gradle.kts`, never in the build file.
- CI on every PR: `./gradlew :composeApp:allTests :composeApp:assembleDebug`, the iOS framework link on a macOS runner, and `scripts/new_product.py --dry-run` against a sample product file so a manifest or placeholder mistake fails in the template, not in a new product.

## 2. Backend template

One ASP.NET service in the layout of `Rindle.User.Api` / `.Application` / `.Infrastructure` / `.Tests`, without Rindle's couple, media or chat services.

| Package | Used for |
|---|---|
| `Pinqponq.Identity`, `Pinqponq.Identity.Otp` | register, login, OTP, refresh, logout, account deletion |
| `Pinqponq.Auth.Sso.Google` | Google sign-in |
| `Pinqponq.ErrorHandling` | error response shape the mobile template expects |
| `Pinqponq.Observability` | logs to pinqloq |
| `Pinqponq.Billing.RevenueCat` | RevenueCat webhook (pinqponq/pinqnuqets#28) |
| `Pinqponq.Contracts` | shared request and response types (pinqponq/pinqnuqets#29) |
| `Pinqponq.Database.Postgres.EntityFrameworkCore` | user store |
| `Pinqponq.Mail`, `Pinqponq.Sms` | OTP delivery |
| `Pinqponq.Configuration.Vault` | settings and secrets (`references/dotnet/vault-configuration.md`) |

Endpoints are the ones the mobile template calls: register, login, OTP send and verify, Google sign-in, refresh, logout, account deletion, profile read and update, push token registration, RevenueCat webhook. `dotnet test` runs in CI on every PR; no secret is committed (Vault records are created per product).

## 3. Template manifest (`template.json`)

Each template has a `template.json` at its root. `new_product.py` reads it and drops it from the output.

```json
{
  "placeholders": {
    "app_name": "TemplateApp",
    "package": "com.pinqponq.templateapp",
    "bundle_id": "com.pinqponq.templateapp.TemplateApp",
    "api_base_url": "https://api-test.templateapp.example/"
  },
  "keys": {
    "REVENUECAT_ANDROID_KEY": {"secret": false},
    "REVENUECAT_IOS_KEY": {"secret": false},
    "GOOGLE_WEB_CLIENT_ID": {"secret": false},
    "PINQLOQ_API_KEY": {"secret": true, "file": "local.properties", "required": false}
  },
  "modules": {
    "paywall": {"paths": ["composeApp/src/commonMain/kotlin/feature/premiumsubscription"]},
    "widget": {"paths": ["iosApp/TemplateAppWidget"], "default": false}
  },
  "theme_file": "composeApp/src/commonMain/kotlin/core/presentation/theme/Color.kt"
}
```

- **placeholders:** every occurrence in file contents and in file and folder names is replaced, longest first. The lower-case app name (`templateapp`, e.g. a deep link scheme) and the package as a path (`com/pinqponq/templateapp`, the source folders) are replaced too.
- **keys:** a public key is written where `__<KEY_NAME>__` appears in the template; an optional one the product leaves out becomes an empty string. Secret keys are written as `KEY=value` to their `file`, which must be covered by the template's `.gitignore` (a path, a glob or a folder entry). The template's own copy of a secret file is never copied, so a template secret cannot reach a product. `required` defaults to true.
- **modules:** a removed module's `paths` are deleted, and every block between lines containing `template:<module>:start` and `template:<module>:end` (in any comment syntax) is cut. In kept modules only the marker lines go. `default` is the choice when the product file does not mention the module; it defaults to true.
- **theme_file:** the `Color.kt` whose `val <Token> = Color(0x…)` values the product's `theme` replaces.

Any placeholder or `__KEY__` token left after generation fails the run, and nothing is written.

## 4. Product file

```json
{
  "app_name": "Lumo",
  "package": "com.deveng.lumo",
  "bundle_id": "com.deveng.lumo.Lumo",
  "api_base_url": "https://api-test.lumo.app/",
  "keys": {"REVENUECAT_ANDROID_KEY": "…", "REVENUECAT_IOS_KEY": "…", "GOOGLE_WEB_CLIENT_ID": "…"},
  "modules": {"widget": false},
  "theme": {"PrimaryColor": "#12AB34"}
}
```

The file can hold keys: keep it outside both repos and delete it after the run.

A backend under `pinqponq.io` gets host names one level below it: `api-test-<product>.pinqponq.io` for test and `api-<product>.pinqponq.io` for prod, never `api-test.<product>.pinqponq.io`. The Cloudflare certificate of `pinqponq.io` covers only one level.

## 5. Order of work

The templates are built last, once the shared parts they use are released (pinqponq/org#215). Until then:

1. The manifest contract, `new_product.py` and the skill (this document) are ready and tested.
2. The two repos are created by the team; their first PR adds the manifest, CI and the infrastructure that is already released.
3. Each feature row above moves in when its shared library version is published, then the template bumps to it.
