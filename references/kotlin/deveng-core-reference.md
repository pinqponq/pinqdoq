# Deveng-Core: What Exists and When to Use It

Use this as a quick map: **situation → use this from core**. No parameter details; see the library
sources for those.

---

## MultiPlatformUtils

| Situation                                        | Use                                                       |
|--------------------------------------------------|-----------------------------------------------------------|
| Dial a phone number (or fallback copy)           | `MultiPlatformUtils.dialPhoneNumber`                      |
| Copy text to clipboard                           | `MultiPlatformUtils.copyToClipBoard`                      |
| Open maps at lat/lon                             | `MultiPlatformUtils.openMapsWithLocation`                 |
| Open a URL in browser / external app             | `MultiPlatformUtils.openUrl`                              |
| Get platform, language, device id, version, etc. | `MultiPlatformUtils.getPlatformConfig` → `PlatformConfig` |
| Get current device location (lat/lon)            | `MultiPlatformUtils.getCurrentLocation` (suspend)         |
| Share text (system share sheet)                  | `MultiPlatformUtils.shareText`                            |

**Do not:** Implement dial, clipboard, maps, URL open, share **text**, or location with custom/platform code
in the app.

---

## RemoteMediaExportManager (`core.util.media`)

| Situation                                                                 | Use                                                                 |
|---------------------------------------------------------------------------|---------------------------------------------------------------------|
| Download a **remote file** (image/video) by URL and open the **system share sheet** (file intent) | `RemoteMediaExportManager.shareSingleFileFromUrl` / `shareMultipleFilesFromUrls` |
| Download by URL and **save to the device gallery** (MediaStore / Photos) | `RemoteMediaExportManager.saveSingleFileFromUrl` / `saveMultipleFilesFromUrls` |
| Model for bulk URL + file name + MIME                                     | `RemoteMediaFile`                                                   |

**Android:** Host app must configure **FileProvider** paths for cache when using share. **Desktop / wasmJs:** implementations are no-ops (return false / 0) unless extended later.

**Do not:** Use `MultiPlatformUtils.shareText` for “share this image URL as a file.” Use **RemoteMediaExportManager** when the product needs actual file share or gallery save from URLs.

**Contrast:** **PhotoSaveUtils** operates on **image bytes** and a target path (e.g. after capture); **RemoteMediaExportManager** starts from **remote URLs**.

---

## PhotoSaveUtils

| Situation                                             | Use                                                                 |
|-------------------------------------------------------|---------------------------------------------------------------------|
| Save captured image bytes to a file path              | `PhotoSaveUtils.savePhoto`                                          |
| Add GPS EXIF to image bytes (e.g. before save)        | `PhotoSaveUtils.addLocationExif`                                    |
| Notify Android MediaStore so photo appears in Gallery | `PhotoSaveUtils.setApplicationContext` (call once with app context) |

**Do not:** Reimplement “write image to file” or “add location to EXIF” in the app. After camera
capture, use `PhotoSaveUtils` (and optionally `addLocationExif` then `savePhoto`).

---

## Camera

| Situation                                                     | Use                                                                                                                                                          |
|---------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Compose entry: get camera state and lifecycle                 | `rememberCameraKState`                                                                                                                                       |
| Full screen: loading / error / ready + preview + content slot | `CameraKScreen`                                                                                                                                              |
| Custom preview UI                                             | `DefaultCameraPreview` or `CameraPreview`                                                                                                                    |
| Focus indicator overlay                                       | `FocusIndicator`                                                                                                                                             |
| Build a controller with lens, flash, format, plugins, etc.    | Platform builder: `AndroidCameraControllerBuilder`, `IOSCameraControllerBuilder`, `DesktopCameraControllerBuilder` (all implement `CameraControllerBuilder`) |
| Capture image (bytes; app saves via PhotoSaveUtils)           | `CameraController.takePictureToFile` (prefer over deprecated `takePicture`)                                                                                  |
| Flash / torch, zoom, switch lens, start/stop recording        | `CameraController` methods                                                                                                                                   |
| Camera-specific permission checks/requests                    | `Permissions` (hasCameraPermission, RequestCameraPermission, etc.)                                                                                           |
| Plugins (e.g. analysis)                                       | `CameraPlugin` and builder `addPlugin`                                                                                                                       |

**Do not:** Implement a separate camera capture/preview/recording stack when these APIs are
available.

### Generic temp file storage (repository pattern)

| Situation                                                       | Use                                                                 |
|-----------------------------------------------------------------|---------------------------------------------------------------------|
| Persist any temp files (e.g. photos, documents) before upload   | `TempFileRepository` (saveBytes(byteArray, fileExtension), loadAll, getCount, loadBytes, delete) in **core.domain.temp** |
| Model for a stored item                                         | `TempFileItem` (id, fileName) in **core.domain.temp**               |
| Provide temp directory path (one per use case, e.g. camera vs docs) | Register `TempStorageDirProvider` in DI; core provides `AndroidTempStorageDirProvider(context, subdir)`, `DesktopTempStorageDirProvider.forApp(appName, subdir)` (e.g. ".brindle/camera_temp"), `IosTempStorageDirProvider(subdir)` in **core.data.temp** — no app-specific provider class needed |
| File I/O (platform)                                             | `TempFileOps` (expect/actual in **core.data.temp**); app registers single instance in DI |

Implementation: **core.data.temp** — `TempFileRepositoryImpl(dirProvider, fileOps)`; app binds `TempStorageDirProvider` (e.g. camera path: `"camera_temp"` or `".brindle/camera_temp"`) and `TempFileOps()`.

**Camera use case:** Use the same API with a camera-specific path. Optional backward-compat: `CameraTempPhotoRepository` (typealias), `TempPhotoItem` (typealias), and extension `TempFileRepository.savePhoto(byteArray)` in **core.domain.camera.temp** (deprecated; prefer `TempFileRepository.saveBytes(byteArray, "jpg")`).

**Whole implementation (app wiring):**

- **Core (deveng-core):**
  - **commonMain:** `core.domain.temp` — `TempFileItem`, `TempFileRepository`; `core.data.temp` — `TempStorageDirProvider` (interface), `TempFileOps` (expect), `TempFileIndex`, `TempFileRepositoryImpl`. Optional: `core.domain.camera.temp` / `core.data.camera.temp` — deprecated type aliases + `savePhoto` extension.
  - **androidMain:** `AndroidTempStorageDirProvider(context, subdir)`, `TempFileOps` actual.
  - **desktopMain:** `DesktopTempStorageDirProvider(subdir)` and `DesktopTempStorageDirProvider.forApp(appName, subdir)`, `TempFileOps` actual.
  - **nativeMain:** `IosTempStorageDirProvider(subdir)`, `TempFileOps` actual.
  - **wasmJsMain:** `TempFileOps` actual (throws; temp storage not supported).

- **App (e.g. brindle) — one use case (e.g. camera):**
  - **commonMain DI:** `single { TempFileOps() }`, `singleOf(::TempFileRepositoryImpl).bind<TempFileRepository>()`. (Repository needs `TempStorageDirProvider` + `TempFileOps` from platform.)
  - **Android:** `single<TempStorageDirProvider> { AndroidTempStorageDirProvider(get(), "camera_temp") }`.
  - **Desktop:** `single<TempStorageDirProvider> { DesktopTempStorageDirProvider.forApp("brindle", "camera_temp") }` — no custom provider class.
  - **iOS:** `single<TempStorageDirProvider> { IosTempStorageDirProvider("camera_temp") }`.
  - **ViewModel:** Inject `TempFileRepository` (or deprecated `CameraTempPhotoRepository`); use `saveBytes(bytes, "jpg")` or `savePhoto(bytes)`; state uses `TempFileItem` (or `TempPhotoItem`).

---

## Permissions

| Situation                                                           | Use                                                                                                           |
|---------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| Request any permission, check granted, get state, open app settings | `PermissionsController` (`providePermission`, `isPermissionGranted`, `getPermissionState`, `openAppSettings`) |
| Obtain controller in Compose                                        | `rememberPermissionsControllerFactory()` then `createPermissionsController()`                                 |
| Bind controller to Android activity (required for request flow)     | `BindEffect(permissionsController)`                                                                           |
| Camera permission only                                              | `Permissions.hasCameraPermission` + `RequestCameraPermission`                                                 |
| Storage permission only                                             | `Permissions.hasStoragePermission` + `RequestStoragePermission`                                               |

**Do not:** Reimplement permission request/check or “open settings” without using these.

---

## Pagination

| Situation                                                                              | Use                                                           |
|----------------------------------------------------------------------------------------|---------------------------------------------------------------|
| Load pages from a key-based source (e.g. cursor/offset), track items + loading + error | `PaginatedFlowLoader` (pageSource, getNextKey, state)         |
| UI: lazy list + load-more + pull-to-retry + empty/error messages                       | `PaginatedListView` with `PaginatedListState` from the loader |
| Page result from API                                                                   | `PageResult(items, hasNextPage)`                              |
| Server-style paged response (page, totalPageCount, etc.)                               | `PagedList` / `PagedListResponse` and `mapItems`              |

**Do not:** Reimplement infinite-scroll state and list-with-retry UI when `PaginatedFlowLoader` +
`PaginatedListView` fit.

---

## Presentation (UI components and theme)

| Situation                                     | Use                                                                                                                                                                                                                                                                                                                                                                   |
|-----------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| App-wide theme (Material, typography, colors) | `AppTheme`                                                                                                                                                                                                                                                                                                                                                            |
| Typography                                    | `CoreRegularTextStyle`, `CoreMediumTextStyle`, `CoreSemiBoldTextStyle`, `CoreBoldTextStyle`                                                                                                                                                                                                                                                                           |
| Buttons                                       | `CustomButton`, `CustomIconButton`                                                                                                                                                                                                                                                                                                                                    |
| Header with title / leading / trailing        | `CustomHeader`                                                                                                                                                                                                                                                                                                                                                        |
| Dialogs                                       | `CustomDialog`, `CustomAlertDialog`, `CustomDialogHeader`, `CustomDialogBody`                                                                                                                                                                                                                                                                                         |
| Text input                                    | `CustomTextField`; transformations: `DateTimeVisualTransformation`, `InlineSuffixTransformation`                                                                                                                                                                                                                                                                      |
| Date / range picker                           | `CustomDatePicker`, `CustomDateRangePicker`; selectable dates: `CustomSelectableDates`                                                                                                                                                                                                                                                                                |
| Single/multi choice from list                 | `OptionItemList`, `OptionItem`, `OptionItemListDialog`, `OptionItemLazyListDialog`, `OptionItemMultiSelectLazyListDialog`                                                                                                                                                                                                                                             |
| Dropdown                                      | `CustomDropDownMenu`                                                                                                                                                                                                                                                                                                                                                  |
| Chips                                         | `ChipItem`                                                                                                                                                                                                                                                                                                                                                            |
| Search field                                  | `SearchField`                                                                                                                                                                                                                                                                                                                                                         |
| Picker with label                             | `PickerField`                                                                                                                                                                                                                                                                                                                                                         |
| Switch with label                             | `LabeledSwitch`                                                                                                                                                                                                                                                                                                                                                       |
| Label + content slot                          | `LabeledSlot`                                                                                                                                                                                                                                                                                                                                                         |
| Rating UI                                     | `RatingRow`, `RatingIcon`                                                                                                                                                                                                                                                                                                                                             |
| Navigation (collapsed/expanded/horizontal)    | `NavigationMenu`, `NavigationMenuContentCollapsed`, `NavigationMenuContentExpanded`, `NavigationMenuContentHorizontal` + item composables                                                                                                                                                                                                                             |
| Scrollbar tied to scroll state                | `scrollbarWithScrollState`, `scrollbarWithLazyListState`                                                                                                                                                                                                                                                                                                              |
| Rounded surface                               | `RoundedSurface`                                                                                                                                                                                                                                                                                                                                                      |
| Progress bars                                 | `ProgressIndicatorBars`                                                                                                                                                                                                                                                                                                                                               |
| OTP input                                     | `OtpView`, `OtpDigit`; `rememberShakeOffset` for shake                                                                                                                                                                                                                                                                                                                |
| JSON display                                  | `JsonViewer`; `formatJson` for formatting                                                                                                                                                                                                                                                                                                                             |
| Simple markdown (headings, lists, bold/italic) | `MarkdownContentParser` (`core.util.markdown`); pass **`textColor`** so text matches theme/surface |
| Fullscreen image viewer (zoom, swipe dismiss, paging) | `MediaViewer`, `MediaViewerState`, `MediaViewerDefaults` (`core.presentation.component.mediaviewer`) |
| Swipeable card stack (Tinder-style)           | `SwipeCards`, `SwipeCardsState`, `rememberSwipeCardsState`, `SwipeCardsScope` (`items` / `itemsIndexed`, `onSwiping` / `onSwiped`); optional overlay icon buttons: `showSwipeButtons` + `negativeButtonIcon` / `positiveButtonIcon` / `revertButtonIcon`. **Theme:** `ComponentTheme` → `swipeCards` (`SwipeCardsTheme` in `core.presentation.theme` / `ComponentTheme.kt`): `buttonBackgroundColor`, `buttonIconTint`, `buttonSize`, `buttonShadowElevation`, and swipe-direction highlights `negativeSwipeHighlightColor`, `positiveSwipeHighlightColor`, `swipeHighlightIconTintBlend` (tint while dragging left/right). **Revert:** `state.canRevert` + `animateBackSwipe`, or **`pendingRevertKey`** if the list changed and internal revert state was lost. **Optional:** `SwipeCardsState.swipeNegativeButtonHighlight` / `swipePositiveButtonHighlight` (0..1) for custom UI tied to drag progress. |

Use these instead of reimplementing equivalent generic components.

---

## Utils (common)

| Situation                                          | Use                                                                                                                                                                  |
|----------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Trim/normalize whitespace                          | `String.clearWhiteSpace`                                                                                                                                             |
| Strip non-numeric (optional allowlist)             | `String.clearNonNumeric`                                                                                                                                             |
| Email validation                                   | `String.isValidEmail`                                                                                                                                                |
| Combined clickable with debounce                   | `Modifier.debouncedCombinedClickable`                                                                                                                                |
| Conditional modifier                               | `Modifier.ifTrue`                                                                                                                                                    |
| Disable split motion events                        | `Modifier.disableSplitMotionEvents`                                                                                                                                  |
| Date/time formatting (daily vs full, locale-aware) | `formatDateTime`, `formatDateToString`, `formatToDayMonth`, `formatDateRange`, `getMonthAbbreviationDateFormat`, `getMonthDateFormat`, `getMonthNames`, `getDayName` |
| Date arithmetic / epoch                            | `LocalDateTime.minus`, `LocalDate.toEpochMillis`                                                                                                                     |
| Text width in Dp                                   | `calculateTextWidthAsDp`                                                                                                                                             |
| Logging                                            | `CustomLogger`                                                                                                                                                       |
| String formatting (e.g. placeholders)              | `StringFormatter`                                                                                                                                                    |

---

## Data / config

| Situation                                | Use                                                                 |
|------------------------------------------|---------------------------------------------------------------------|
| Store/read device-related key-value info | `DeviceInfoStorage` / `DeviceInfoStorageImpl`                       |
| Temp file storage (camera stack, documents, etc.) | `TempFileRepository`, `TempFileItem` in **core.domain.temp**; DI: `TempStorageDirProvider`, `TempFileOps` from **core.data.temp** (see [Generic temp file storage](#generic-temp-file-storage-repository-pattern)) |

---

When vibecoding, match the current task to a row above and use the indicated core API rather than
generating equivalent logic in the app.
