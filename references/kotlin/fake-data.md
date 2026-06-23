# Fake / Mock Data Pattern

## Overview

Use `Fake{Entity}DataProvider` objects to supply hardcoded mock data. These are Kotlin `object` singletons located under `presentation/component/preview/` within each feature. They serve two purposes:

- A temporary bridge for features that do not have a real API yet.
- The data source for `@Preview` composables (see `formatting.md` for preview placement).

## The Pattern

### 1. FakeDataProvider — The Data Source

Located at `feature/{featureName}/presentation/component/preview/Fake{Entity}DataProvider.kt`:

```kotlin
object FakeProductDataProvider {
    val products: List<Product> = listOf(
        Product(id = 1, name = "Sample Product A", price = 49.90, isAvailable = true),
        Product(id = 2, name = "Sample Product B", price = 19.00, isAvailable = false),
    )
}
```

### 2. UseCase — Consumes the Fake Data

`FetchProductListUseCase` returns data from the provider directly instead of calling a repository:

```kotlin
class FetchProductListUseCase {
    operator fun invoke(): List<Product> {
        return FakeProductDataProvider.products
    }
}
```

This is the **temporary / pre-API pattern**. Once the real API is integrated, the use case swaps to a repository call — no ViewModel changes needed.

### 3. ViewModel — Receives the UseCase via DI

The ViewModel depends on the use case, not on the provider. The base ViewModel API (`setState`, the async `launch` wrapper) and dispatcher injection come from the project's base ViewModel / the deveng-core-kmp library — see `../../rules/kotlin-deveng-core.md` and `deveng-core-reference.md`.

```kotlin
class ProductsViewModel(
    private val ioDispatcher: CoroutineDispatcher,
    private val fetchProductListUseCase: FetchProductListUseCase
) : BaseViewModel<State, Event, Effect>(State()) {
    override fun handleEvents(event: Event) {
        when (event) {
            is Event.Init -> {
                launch(dispatcher = ioDispatcher) {
                    val productList = fetchProductListUseCase()
                    setState { copy(products = productList) }
                }
            }
        }
    }
}
```

### 4. Composable Previews — Direct Access to Fake Data

```kotlin
@Preview
@Composable
fun ProductListPreview() {
    ProductList(
        products = FakeProductDataProvider.products,
        onProductClick = {}
    )
}
```

## Flow

```
FakeProductDataProvider  -->  UseCase  -->  ViewModel  -->  UI
         |
         +------------------------------------->  @Preview composables (direct access)
```

## Key Points

- **Temporary bridge**: Fake providers stand in until real API integration. The use case currently returns fake data directly. When the API is ready, the use case swaps to a repository call — no ViewModel changes needed. That is the main benefit of funneling the data through a use case instead of letting the ViewModel touch the provider directly.
- **Two consumers**: Both use cases (for runtime) and `@Preview` functions (for design-time) read from the providers.
- **Consistent location**: Always at `feature/{featureName}/presentation/component/preview/Fake{Entity}DataProvider.kt`.
- For naming of providers, use cases, and entities, see `naming.md`.
