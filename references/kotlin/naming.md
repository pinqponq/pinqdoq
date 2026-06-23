# Naming — Delta for Clean Architecture / MVI

This file covers only the naming rules that are specific to the layered KMP structure (see `architecture.md`, `data-layer.md`, `mvi-pattern.md`). The base naming conventions — variables, constants, events, packages, callbacks/lambdas — already live in `../../rules/common.md` and `../../rules/kotlin-naming.md` and are not repeated here.

## Classes & Interfaces

The conventions file already names `{Feature}Screen`, `{Feature}ScreenContent`, `{Feature}ViewModel`, `{Feature}Contract`, and `{Verb}{Entity}UseCase`. The rows below complete the set across the data, domain, and presentation layers.

| Type                   | Convention                  | Example                          |
| ---------------------- | --------------------------- | -------------------------------- |
| Repository (interface) | `{Feature}Repository`       | `OrderRepository`                |
| Repository (impl)      | `{Feature}RepositoryImpl`   | `OrderRepositoryImpl`            |
| Service                | `{Feature}Service`          | `ProfileService`                 |
| Domain Model           | `{Entity}` (clean name)     | `UserInfo`, `Notification`       |
| Request Model          | `{Entity}Request`           | `RegisterRequest`, `LoginRequest`|
| Response Model         | `{Entity}Response`          | `UserInfoResponse`               |
| UI Model               | `{Entity}UiModel`           | `CountryUiModel`, `UserInfoUiModel` |
| Mapper (data layer)    | `{Entity}Mapper`            | `UserInfoMapper`                 |
| Mapper (presentation)  | `{Entity}UiMapper`          | `CountryUiMapper`                |
| DI Module              | `{Feature}{Layer}Module`    | `OrderPresentationModule`        |
| Preview Provider       | `{Entity}PreviewProvider`   | `ProductPreviewProvider`         |
| Fake Data Provider     | `Fake{Entity}DataProvider`  | `FakeProductDataProvider`        |

Rules:
- Never use a `Dto` suffix — always `Request` or `Response`.
- Domain models carry no suffix — clean business names (`UserInfo`, not `UserInfoModel` / `UserInfoDto`).

## Functions

| Context              | Convention              | Example                                   |
| -------------------- | ----------------------- | ----------------------------------------- |
| ViewModel handler    | `handleEvents(event)`   | Always this exact name                    |
| Private helpers      | `{verb}{Entity}()`      | `validateLoginCredential()`, `loadProductDetail()` |
| UseCase execution    | `operator fun invoke()` | `suspend operator fun invoke(id: String): User` |
| Repository methods   | `{verb}{Entity}()`      | `fetchUserInfo()`, `uploadProfilePhoto()` |
| Service methods      | `{verb}{Entity}()`      | `fetchUserSettings()`, `deleteNotification()` |
| Mapper methods       | `mapTo{TargetType}()`   | `mapToDomain()`, `mapToCountryUiModel()`  |
| Composable functions | `{ComponentName}()`     | `LoginInputSection()`, `CredentialTypeTabs()` |

### Verb usage in domain / repository

| Verb           | Meaning              | Example                  |
| -------------- | -------------------- | ------------------------ |
| `fetch`        | Get data from remote | `fetchUserInfo()`        |
| `send`         | Send data to remote  | `sendSmsOtp()`           |
| `save`         | Create or update     | `saveBranchInfo()`       |
| `update`       | Modify existing data | `updateUserSettings()`   |
| `create`       | Create new record    | `createCollection()`     |
| `delete`       | Remove data          | `deleteNotification()`   |
| `upload`       | Send file            | `uploadProfilePhoto()`   |
| `submit`       | Send form data       | `submitQuestion()`       |
| `verify`       | Validate / confirm   | `verifyOtp()`            |
| `authenticate` | Login / auth action  | `authenticateEmailOtp()` |

**Never use HTTP verbs** (`get`, `post`, `put`) in domain or repository method names. They expose the transport and leak technical detail into the domain.

## Effects — Navigation Nesting

Effect names are outcome-based (covered in `../../rules/kotlin-naming.md`). Navigation effects are nested under a `Navigation` subtype so the ViewModel and the collector can branch on navigation versus other side effects:

```kotlin
sealed class Effect : ViewSideEffect {
    sealed class Navigation : Effect() {
        data object Back : Navigation()
        data class NavigateToOtpScreen(val data: OtpData) : Navigation()
        data object NavigateToRegisterScreen : Navigation()
    }
    // Non-navigation effects
    data object OpenCamera : Effect()
    data object OpenGalleryPicker : Effect()
    data object RequestPermission : Effect()
}
```

## String Resources

Resource names follow the triad `{feature}_{context}_{purpose}` in snake_case, extending the module-prefix rule in `../../rules/kotlin-naming.md`:

```xml
<!-- CORRECT -->
<string name="onboarding_feat_connection_lost">...</string>
<string name="login_feat_enter_email">...</string>
<string name="events_edit_dialog_title_edit">...</string>

<!-- WRONG -->
<string name="connection_lost">...</string>
<string name="enter_email">...</string>
```

Symbolic characters (arrows, checkmarks, close icons) must be implemented as `DrawableResource` vector drawables under `composeResources/drawable/`, never as unicode text literals.

## UseCase Naming — Verb Prefixes

All use cases follow `{Verb}{Entity}UseCase`. Pick the verb by what the use case *does* to the entity, not how it is technically implemented.

| Verb                 | Meaning                          | Example                              |
| -------------------- | -------------------------------- | ------------------------------------ |
| **Fetch**            | Retrieve data (local or remote)  | `FetchActiveEventListUseCase`        |
| **Add**              | Create a new entity              | `AddProductUseCase`                  |
| **Update**           | Modify an existing entity        | `UpdateProductUseCase`               |
| **Delete**           | Remove an entity                 | `DeleteBranchPhotoUseCase`           |
| **Change**           | Modify order / state             | `ChangeProductPhotoOrderUseCase`     |
| **Send**             | Transmit / push data             | `SendEmailOtpUseCase`                |
| **Reply**            | Respond to something             | `ReplyCommentUseCase`                |
| **Post**             | Submit a form                    | `PostProblemFormUseCase`             |
| **Handle**           | Orchestrate multiple actions     | `HandleProductPhotoListActionsUseCase` |
| **Authenticate**     | Verify identity                  | `AuthenticateEmailUseCase`           |
| **Initialize / End** | Session lifecycle                | `InitializeUserSessionUseCase`, `EndUserSessionUseCase` |
| **Create**           | Create a domain entity (not API) | `CreateEventUseCase`                 |
| **Build**            | Construct / generate something   | `BuildQrUseCase`                     |

> **Fetch vs Get.** `Fetch` is the standard prefix for **all** data retrieval, whether the source is local (fake data, cache) or remote (network API). Do **not** use `Get` — always use `Fetch`.

### UseCase Class Structure

Every use case exposes a single `operator fun invoke()`:

```kotlin
// Simple (no dependencies, no suspend)
class FetchActiveEventListUseCase {
    operator fun invoke(): List<Event> { ... }
}

// Standard (repository dependency, suspend)
class FetchBranchInfoListUseCase(
    private val dashboardRepository: DashboardRepository
) {
    suspend operator fun invoke(userId: Int): List<BranchInfo> {
        return dashboardRepository.fetchBranchList(userId)
    }
}
```
