# Data Layer — Services, DTOs, Mappers, Repositories, DI

The data layer is uniform across every feature. Once you've built one feature's `data/` package, you've built them all — the shape never changes. For the full feature skeleton, see `architecture.md`.

## Folder Shape

```
feature/{featureName}/data/
├── datasource/remote/
│   ├── {Feature}Service.kt
│   └── model/
│       ├── request/   → {Entity}Request.kt   (only when the feature mutates)
│       ├── response/  → {Entity}Response.kt
│       └── mapper/    → {Entity}Mapper.kt
├── repository/
│   └── {Feature}RepositoryImpl.kt
└── di/
    └── {Feature}DataModule.kt
```

Rules:
- Every feature has `datasource/remote/`, `repository/`, and `di/`. No exceptions.
- `request/` is omitted when the feature is read-only.
- **No `local/` datasource in a feature.** Features are remote-only. Persisted state (auth token, user settings, session) lives in a shared `core` key-value store, never inside a feature.
- `model/` is always nested under `datasource/remote/`, never directly under `data/`.

## Service

The service is the only thing that talks to the network. **One concrete class per feature**, named `{Feature}Service`, taking the project's networking module (e.g. deveng-networking-kmp) as its single dependency. No interface — the class is the contract.

```kotlin
class EventsService(
    private val networkingModule: NetworkingModule
) {
    suspend fun fetchEvents(eventTypeId: Int? = null): List<EventListItemResponse> =
        networkingModule.sendRequest<Unit, List<EventListItemResponse>>(
            endpoint = "api/events",
            requestMethod = HttpMethod.GET,
            queryParameters = buildMap { eventTypeId?.let { put("eventTypeId", it) } }
        )
}
```

Conventions:
- Method names: `{verb}{Entity}()` — `fetch`, `send`, `create`, `update`, `delete` (see `naming.md`).
- Request/response generics are always explicit; use `Unit` for the request type on GETs.
- Endpoint strings are hardcoded inline. No constants file, no companion object.
- Path params: interpolate (`"api/events/$eventId/seats"`) or use the framework's path-parameter map.
- Query params: `buildMap { value?.let { put(...) } }`.
- Return type is the **response DTO directly** — never `Result<T>`, `Flow<T>`, or a custom wrapper. Exceptions propagate; the ViewModel's async wrapper handles them.

## DTOs — Requests & Responses

Plain `@Serializable` `data class`es under `model/request/` and `model/response/`.

```kotlin
@Serializable
data class EventDetailResponse(
    val id: Int,
    val name: String,
    val description: String? = null,
    val startDate: String,
    val eventHall: EventHallResponse,
    val blockSpecs: List<BlockSpecResponse> = emptyList()
)
```

Conventions:
- `@Serializable` on every DTO, including nested ones.
- `@SerialName("BackendField")` only when the backend name disagrees with Kotlin naming. Drop it when the backend already returns camelCase.
- Nullable fields default to `null`; list fields default to `emptyList()`. Never a sentinel string.
- Nested response objects get their own `data class` (co-located, or split out when reused).
- Paginated reads return a wrapper DTO mirroring the backend envelope (`data`, `page`, `size`, `rowCount`, `pageCount`, `hasNextPage`, …). Name it `Get{Entities}Response` or `{Entity}PageResponse`.
- Never use a `Dto` suffix — always `Request` or `Response`.

## Mappers

Mappers convert DTOs into domain models. **Each mapper is a class**, not a free-standing extension — keeping mapping injectable and composable.

```kotlin
class EventMapper {
    fun mapToDomain(response: EventListItemResponse): Event = Event(
        id = response.id,
        name = response.name,
        location = response.eventHallName,
        description = response.description.orEmpty()
    )
}

class EventsPageMapper(
    private val eventMapper: EventMapper
) {
    fun mapToDomain(response: GetEventsResponse): EventsPage = EventsPage(
        page = response.page,
        hasNextPage = response.hasNextPage,
        data = response.data.map(eventMapper::mapToDomain)
    )
}
```

Conventions:
- One file per mapper: `{Entity}Mapper.kt` under `datasource/remote/model/mapper/`.
- One public method `fun mapToDomain(response): Domain`; add `mapToRequest(domain): Request` when mapping both ways.
- Compose by **injection**, never by calling another mapper as a top-level function.
- Convert nullable DTO fields to non-null domain defaults here (`String?` → `.orEmpty()`, `List<T>?` → `?: emptyList()`). Don't let `null` leak into the domain unless the model accepts it.
- Date parsing happens here, not in the ViewModel.

## Repository

```kotlin
class EventsRepositoryImpl(
    private val eventsService: EventsService,
    private val eventMapper: EventMapper
) : EventsRepository {
    override suspend fun fetchActiveEvents(eventTypeId: Int?): List<Event> =
        eventsService.fetchEvents(eventTypeId).map(eventMapper::mapToDomain)
}
```

Conventions:
- `{Feature}RepositoryImpl` implements a `{Feature}Repository` interface in `domain/repository/`.
- Constructor takes the service + the mappers it needs. No `Dispatcher`, `CoroutineScope`, or settings store.
- Return domain types directly — no `Result<T>`, no wrappers.
- The repository does not orchestrate retries, caching, or fallbacks.

## Dependency Injection (if using Koin)

```kotlin
val eventsDataModule = module {
    singleOf(::EventsService)
    singleOf(::EventMapper)
    singleOf(::EventsPageMapper)
    singleOf(::EventsRepositoryImpl) bind EventsRepository::class
}
```

- Everything is a `single` — services, mappers, repositories are stateless and shareable.
- Bind the repository impl to its interface; the domain only ever sees the interface. Mappers need no interface.
- Module name `{feature}DataModule`. Register it at the DI root, or resolution fails at runtime with no compile-time signal.

## Shared Infrastructure

| Concern | Lives in | Notes |
|---|---|---|
| HTTP client | shared `core` networking module | single instance, injected into every service |
| Token attachment | networking module's `setToken(...)` | set once at login, cleared at logout |
| Persisted state | shared `core` key-value store | never per-feature |
| Pagination | per feature | each paginated response carries its own envelope |
| Error mapping | not centralized in data | services throw; the base ViewModel handles it |
| `Result<T>` wrappers | don't use | rely on exceptions + the ViewModel's async wrapper |

## Recipe — Adding a Feature's Data Layer

1. **Service** — inject the networking module; one method per endpoint, returns the response DTO.
2. **DTOs** — `@Serializable`, defaults for nullable/list fields.
3. **Mapper** — class with `mapToDomain(...)`; compose for pages/lists.
4. **Repository** — implements the domain interface; service + mapper in, domain types out.
5. **DI module** — register service, mappers, and the repo bound to its interface.
6. **Wire into the DI root** — or DI fails at runtime.

Every step is mechanical. If you're inventing structure not in the recipe, stop — either a convention covers it, or the new pattern must be added here first.

> The `data/` scaffold, DTOs, mappers, and DI registration can be generated with the pinq-doq scripts under `.pinq-doq/scripts/` (`generate_data_layer.py`, `generate_data_model.py`, `generate_mapper.py`, `register_mapper.py`, …; see `../../scripts/README.md`) and the `api-endpoint-integration` skill.
