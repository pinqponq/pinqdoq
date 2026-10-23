# Home Screen Widget — Setup Guide

How to add a home screen widget to a KMP app with **deveng-widget** (`global.deveng:widget-kmp`, in deveng-core-kmp) and the Swift templates in `ios/`. First production user: Rindle (`composeApp/.../widget`, `iosApp/RindleWidget`). The widget's look and content model are always product code; everything below is the part that is the same for every widget.

## 1. What lives where

| Part | Where | Why |
|---|---|---|
| Widget session storage (`HomeScreenWidgetSessionStorage(Impl)`), token use cases (`Initialize…`, `End…`, `SendWidgetTokenRequestUseCase`), `HomeScreenWidgetTokenRepository`, `WidgetTokenRejectedException` | deveng-widget `commonMain` | Same contract on every platform |
| Reload bridge (`HomeScreenWidgetReloader`, `DisabledHomeScreenWidgetReloader`, `IosHomeScreenWidgetReloader`, `AndroidHomeScreenWidgetRefreshScheduler`) | deveng-widget | |
| Push update (`ApplyHomeScreenWidgetPushUseCase`, `HomeScreenWidgetSessionlessDrawer`) | deveng-widget | |
| Image pipeline (`HomeScreenWidgetImageStore`, `HomeScreenWidgetImageDownloader`, `HomeScreenWidgetBitmaps`) | deveng-widget `androidMain` | |
| Widget API service, DTOs, repository (`…Repository : HomeScreenWidgetTokenRepository`), content model, Glance UI, refresh worker, push payload keys | app | Product endpoints and content |
| Session, API, push handler, timeline, reload (Swift) | app, copied from `ios/` | Swift cannot ship in a Kotlin library |

The library has no Koin, no networking and no product strings; the app wires it in its own DI modules.

## 2. Session hand-off (app → widget)

The widget runs in a separate process (always on iOS, and on Android it must not wait on the app's session), so it calls the API with its own **widget token**, not the user's session.

1. Backend: an endpoint that issues a widget token for `deviceIdentifier` with the user's session, one that revokes it, and widget endpoints that accept it in the `X-Widget-Token` header and answer `401` once it is revoked (logout, unpair).
2. App: implement `HomeScreenWidgetTokenRepository` in the widget repository and bind it.
3. Bind `HomeScreenWidgetSessionStorageImpl` to a `Settings` that the widget can read:
   - Android: the app's own `Settings` (the widget runs in the app process).
   - iOS: `NSUserDefaultsSettings(NSUserDefaults(suiteName = "<APP_GROUP_IDENTIFIER>"))` — the App Group the extension reads in `HomeScreenWidgetSession.swift`. The key names are shared with Swift; never rename them on one side.
   - desktop / web: any `Settings`, with `DisabledHomeScreenWidgetReloader`.
4. Call `InitializeHomeScreenWidgetSessionUseCase` **every time a signed-in session starts**, not only after login, so users who were signed in before the widget shipped get a token too. Give it `apiBaseUrl` and a device identifier provider (`MultiPlatformUtils.getPlatformConfig().uuid`).
5. Call `EndHomeScreenWidgetSessionUseCase` on logout and before re-pairing. It drops the local token even when the revoke call fails, so the widget empties either way.
6. Every widget request goes through `SendWidgetTokenRequestUseCase`: it returns null without a session and forgets the token on `WidgetTokenRejectedException` (map the service's `401` to it), so the next signed-in start issues a fresh token instead of retrying a dead one.

## 3. Reloading the widget

`HomeScreenWidgetReloader.reloadHomeScreenWidgets()` (or `RefreshHomeScreenWidgetsUseCase`) after anything that may change what the widget shows.

- **Android:** `AndroidHomeScreenWidgetRefreshScheduler(context, <AppRefreshWorker>::class.java, immediateRefreshWorkName, periodicRefreshWorkName)`. The app's worker fetches the content, stores it and redraws. The work names are WorkManager unique names: never change them after release, or installs keep the old periodic job next to the new one. The periodic job (30 min) catches pushes that never arrive; cancel it when the widget is signed out.
- **iOS:** `WidgetCenter` is Swift-only. Copy `ios/HomeScreenWidgetReload.swift` into the app target and register it at launch through a one-function Kotlin object in the app (`IosHomeScreenWidgetBridge.setReloadHandler`) that forwards to `IosHomeScreenWidgetReloader.setReloadHandler`. Reloads made in the foreground do not count against the widget's refresh budget.

## 4. Updating from a push

- **Android:** send the widget push **data-only** (no `notification` block), so the app receives it in the background and after a swipe-away; the app shows the notification itself. Draw the widget **inside** `onMessageReceived`: `runBlocking { applyHomeScreenWidgetPushUseCase { … store content, HomeScreenWidgetSessionlessDrawer.drawAllWidgets(…) } }`. On `FallbackRequired`, log it and call `enqueueImmediateRefresh()`.
- **iOS 26+:** add `.pushHandler(HomeScreenWidgetPushHandler.self)` (`ios/HomeScreenWidget.swift`). The server sends a WidgetKit push (`apns-push-type: widgets`) to the widget's push token; it needs no notification permission. Older iOS versions reload from the app's notification handler and the timeline policy.

## 5. Images (Android)

Store the image with `HomeScreenWidgetImageStore.downloadAndReplaceImage` and draw it with `HomeScreenWidgetBitmaps.decodeImageForWidget(context, file, layoutCount)`. Glance may redraw at any time, so the widget only decodes the local copy, never the network. Use short timeouts in the push path (Rindle: 4 s connect / 6 s read inside a 12 s push budget) and longer ones in the worker (10 s / 15 s).

## 6. iOS project setup

1. Widget extension target; copy the files in `ios/` and fill the `<…>` placeholders.
2. Same App Group in the app's and the extension's entitlements (Debug and Release), `aps-environment` in the extension's entitlements for widget pushes.
3. The widget kind string is defined in the extension and in the app's reload helper; keep them identical.

## 7. Lessons from production (do not relearn these)

- **Samsung + Android 16 held push-triggered work back.** A WorkManager job (and a Glance `update()`, which also runs as a WorkManager job) enqueued from the push callback did not run until the app was opened again. Hence the widget is drawn inside the push callback with `compose()` straight to `AppWidgetManager`, and the worker is only the fallback.
- **iOS 26 widget push token belongs to an account.** The server stores it under the widget token's owner. When a different account signs in, or unpair issues a new widget token, the push token must be registered again — `HomeScreenWidgetSession.isPushTokenRegistrationOutdated` compares the token it was last registered with. Without it, pushes keep going to the previous account. A rotated push token is always registered again.
- **A widget placed before sign-in has nothing to register with.** The first push token registration fails without a widget token; the next timeline refresh retries it.
- **RemoteViews bitmap limit.** An update whose bitmaps exceed about 1.5 × screen width × height × 4 bytes crashes the whole widget update; a responsive widget carries the bitmap once per size. `HomeScreenWidgetBitmaps` stays within half of that, split across the layout sizes.
- **Two refreshes at once.** The immediate and the periodic refresh can run together; a shared temporary file name made one of them lose its image. `HomeScreenWidgetImageStore` uses a temporary file per call and an atomic rename.
- **Commit, not apply.** The worker process may end right after storing the content; write widget content with `SharedPreferences.edit(commit = true)`.
- **Revoked token.** A `401` with the widget token means signed out: forget the token (Kotlin and Swift do), show the signed-out state, and let the next signed-in app start issue a new one.
