---
name: deveng-core-guide
description: Use the deveng-core-kmp library's existing APIs instead of reimplementing functionality. Covers UI components (CustomButton, CustomTextField, CustomDialog, CustomHeader, CustomDatePicker, PaginatedListView, etc.), platform utilities (MultiPlatformUtils for dial/clipboard/maps/URL/share/location), camera stack (CameraController, CameraKScreen, PhotoSaveUtils), media (RemoteMediaExportManager, MediaViewer, MarkdownContentParser), swipeable cards (SwipeCards), permissions (PermissionsController), pagination (PaginatedFlowLoader), and utility extensions (StringFormatter, date/time formatting, modifier helpers). Trigger whenever working on a Kotlin Multiplatform / Compose Multiplatform project that depends on deveng-core-kmp — before writing any UI component, platform operation, camera flow, media/share, or permission request, consult this guide to find the existing core API and avoid reinventing what the library already provides.
paths: ['**/*.kt', '**/*.kts']
---

# Deveng-Core Library Guide (Vibecoding)

Version: 1.0.3  
Owner: deveng-core-kmp  
Risk: Low

## Purpose

This guide ensures that when building or vibecoding an app that depends on **deveng-core-kmp**, the agent uses the library’s existing APIs instead of reimplementing or duplicating functionality. The agent should know what the core provides and choose the right API for each situation.

## Non-Goals

- Does not document parameters or teach “how to call” each API in detail.
- Does not define a strict I/O contract for the agent’s reply; the output is correct app code that uses core.
- Does not replace reading the codebase when in doubt; it directs *what to prefer* and *when*.

## Scope

### In-scope

- Before implementing a feature, check the **reference** for a matching situation and use the listed core API.
- When the user asks for dial, clipboard, maps, URL open, share, location, or platform info → use **MultiPlatformUtils**.
- When the app needs to **download remote media by URL** and **share as files** or **save to the device gallery** (photos/videos from URLs) → use **RemoteMediaExportManager** (`core.util.media`) and **`RemoteMediaFile`** for bulk lists—not `MultiPlatformUtils.shareText` (that API is for plain text).
- When the app needs to save captured photo bytes or add location EXIF → use **PhotoSaveUtils**.
- When the app needs **simple markdown lines** in Compose (headings, lists, bold/italic) with a **caller-controlled text color** → use **MarkdownContentParser** (`core.util.markdown`).
- When the app needs a **fullscreen image viewer** with zoom and swipe-to-dismiss → use **MediaViewer** (`core.presentation.component.mediaviewer`).
- When the app needs camera capture, preview, or recording → use **CameraController** / **CameraKScreen** / **rememberCameraKState** and related compose/domain APIs.
- When the app needs to stack or persist camera photos in temp storage (e.g. before upload, swipe-to-delete flow) → use core **CameraTempPhotoRepository** and **TempPhotoItem**; register **CameraTempDirProvider** in DI (or use default implementations from core).
- When the app needs permission request/check or app settings → use **PermissionsController** (and **rememberPermissionsControllerFactory** / **BindEffect**) or camera-domain **Permissions** where applicable.
- When the app needs paginated lists (load-more, pull-to-retry, empty/error UI) → use **PaginatedFlowLoader** + **PaginatedListView** and core pagination models.
- When the app needs shared UI (buttons, headers, dialogs, text fields, date pickers, lists, navigation, etc.) → use the core **presentation** composables and theme listed in the reference.
- When the app needs a **swipeable card stack** (e.g. approve/reject, gallery stack) → use **SwipeCards** + **rememberSwipeCardsState**; configure overlay buttons and **swipe-direction highlight colors** via **ComponentTheme** → **SwipeCardsTheme** (not ad-hoc colors on the composable).
- When the app needs date/time formatting or selection rules → use core **datetime** and **CustomSelectableDates**.
- When the app needs string/email validation, modifier helpers, or logging → use core **util** extensions and **CustomLogger**.

### Out-of-scope

- Inventing new core APIs or changing the library’s public contracts.
- Explaining every parameter of every function in the guide text.
- Using this guide for projects that do not depend on deveng-core-kmp (then the guide does not apply).

### Stop conditions

- **Prefer core:** If a feature clearly maps to a reference situation, use the core API; do not reimplement.
- **Assume:** If the reference lists an area (e.g. “dial / clipboard / share”) and the app needs that behavior, assume core’s API is intended unless the user explicitly asks for a different implementation.
- **Refuse:** Do not generate code that duplicates core behavior (e.g. custom “save photo to file” or “open URL” logic when PhotoSaveUtils / MultiPlatformUtils exist).

## Procedure

1. **Validate context:** Confirm the project depends on deveng-core-kmp (e.g. `deveng-core` in dependencies).
2. **Match situation:** For the requested feature, check the reference: “What exists and when to use it.”
3. **Plan:** Prefer the core module/API listed for that situation; only add app-specific wiring or UI that is not in core.
4. **Execute:** Write code that calls core APIs (MultiPlatformUtils, PhotoSaveUtils, camera, permissions, pagination, presentation components, SwipeCards where applicable, utils) instead of reimplementing their behavior.
5. **Verify:** Ensure no duplicate logic exists for dial, clipboard, maps, URL open, share text, remote URL media export (share/save gallery), location, platform config, photo save/EXIF, camera lifecycle, permissions, or pagination.

## Rules

### MUST

- Use **MultiPlatformUtils** for: dial, copy to clipboard, open maps with location, open URL, share text, get current location, get platform config. Do not implement these with platform-specific or custom code in the app.
- Use **RemoteMediaExportManager** for: download media from **HTTPS URLs** and invoke the system share sheet for **files** or persist to the **gallery** (bulk: `List<RemoteMediaFile>`). Do not reimplement URL fetch + FileProvider/MediaStore/Photos for that flow when this API fits. Do not confuse with **MultiPlatformUtils.shareText** (text-only).
- Use **PhotoSaveUtils** for saving photo bytes to a path and for adding location EXIF to image bytes (e.g. after camera capture). Do not reimplement file write or EXIF handling.
- Use core **camera** APIs (CameraController, builder, rememberCameraKState, CameraKScreen, DefaultCameraPreview, etc.) for capture, preview, and recording. Do not introduce a separate camera stack unless the user explicitly requests it.
- Use core **CameraTempPhotoRepository** (and **TempPhotoItem**, **CameraTempDirProvider** / **CameraTempFileOps**) for persisting captured photos in temp storage; do not reimplement temp photo storage in the app.
- Use **PermissionsController** (and **rememberPermissionsControllerFactory** / **BindEffect**) or camera **Permissions** for permission checks and requests; do not reimplement permission flows.
- Use **PaginatedFlowLoader** and **PaginatedListView** (and **PageResult** / **PaginatedListState**) for paginated lists with load-more and retry; do not reimplement pagination state or list UI that core already provides.
- Use core **presentation** components and **theme** (e.g. CustomButton, CustomHeader, CustomDialog, CustomTextField, CustomDatePicker, PaginatedListView, AppTheme, typography) when the UI need matches what they provide.
- For **SwipeCards** overlay actions and **left/right swipe button tint while dragging**, use **SwipeCardsTheme** inside **ComponentTheme** (`negativeSwipeHighlightColor`, `positiveSwipeHighlightColor`, `swipeHighlightIconTintBlend`, plus base `buttonBackgroundColor` / `buttonIconTint`). Do not fork that styling in the app unless the user explicitly wants a one-off.

### SHOULD

- When adding a new screen or flow, quickly scan the reference for “situation → use this” and align with it.
- Prefer core **util** (String extensions, Modifier extensions, datetime formatting, CustomLogger) over custom helpers for the same purpose.
- When **editing deveng-core** public APIs, match existing **KDoc** style: block comment above `@Composable` with a short summary and `@param` lines for each parameter (see `SearchField`, `LabeledSwitch`, `SwipeCards`); theme `data class` types use a **one-line class-level** description (see `SwipeCardsTheme`, `IconButtonTheme`).

### MUST NOT

- Implement “dial number,” “copy to clipboard,” “open map,” “open URL,” or “share text” without using MultiPlatformUtils.
- Implement “download URL → share file or save to gallery” without using **RemoteMediaExportManager** when the task is exactly that (plain text share remains **MultiPlatformUtils.shareText**).
- Implement “save image bytes to file” or “add GPS EXIF to image” without using PhotoSaveUtils.
- Implement camera capture/preview/recording with a different stack when core camera APIs are available.
- Implement temp photo stacking/storage (e.g. for pre-upload or swipe flows) without using core CameraTempPhotoRepository and related types.
- Implement permission request/check/settings navigation without using PermissionsController or core Permissions.
- Implement infinite-scroll paginated lists with custom state and list UI when PaginatedFlowLoader + PaginatedListView fit.
- Duplicate core presentation components (e.g. custom “theme” or “generic button” that mirrors AppTheme/CustomButton) without reason.

## Reference

See **deveng-core-reference.md** in this folder for: what exists in the library and which API to use in which situation. Use it to decide “use this from core” before writing app code.

## Architecture note (core library)

Core uses a **domain + data** split for camera temp storage: repository interface in **core.domain.camera.temp** (`CameraTempPhotoRepository`, `TempPhotoItem`), implementation and file/dir abstractions in **core.data.camera.temp** (`CameraTempPhotoRepositoryImpl`, `CameraTempDirProvider`, `CameraTempFileOps`). Apps depend on the interface and register platform-specific `CameraTempDirProvider` in DI.

**Sample app:** The `sample:composeApp` **ThemingDemo** screen includes a **SwipeCards** example at the top of the main lazy column for manual testing.

## Changelog

- 1.0.3: **RemoteMediaExportManager** / **RemoteMediaFile** (`core.util.media`); **MarkdownContentParser** (`textColor`); **MediaViewer** (`core.presentation.component.mediaviewer`); sample `App.kt` demo touch-up.
- 1.0.2: SwipeCards + SwipeCardsTheme (highlight colors); KDoc convention when editing core; sample SwipeCards location.
- 1.0.1: Camera temp storage (CameraTempPhotoRepository, TempPhotoItem); architecture note for domain/data split.
- 1.0.0: Initial guide; scope, procedure, rules, and reference pointer.
