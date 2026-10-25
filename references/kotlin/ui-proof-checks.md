# UI proof checks (Compose)

The rule is `rules/ui-proof-review.md`. These are the mechanical checks that back the touch target and contrast rows of its checklist. Put them next to the screen's other behavior tests and call them for each screen state.

## 1. Touch targets

A clickable node must be at least 48dp wide and high. `touchBoundsInRoot` is the area that takes a tap, including the padding that `minimumInteractiveComponentSize` adds.

```kotlin
@OptIn(ExperimentalTestApi::class)
fun ComposeUiTest.assertClickableNodesAreTouchTargets(minimum: Dp = 48.dp) {
    val density = Density(density = 1f)
    onAllNodes(hasClickAction()).fetchSemanticsNodes().forEach { node ->
        val bounds = node.touchBoundsInRoot
        val width = with(density) { bounds.width.toDp() }
        val height = with(density) { bounds.height.toDp() }
        assertTrue(width >= minimum && height >= minimum, "Node ${node.id} is $width x $height, below $minimum")
    }
}
```

Call it after `setContent`: `composeUiTest.assertClickableNodesAreTouchTargets()`. The helper uses a density of 1 so a pixel counts as a dp on the desktop test target; pass the real density where a test sets one.

## 2. Contrast

```kotlin
fun contrastRatio(foreground: Color, background: Color): Float {
    val lighter = max(foreground.luminance(), background.luminance())
    val darker = min(foreground.luminance(), background.luminance())
    return (lighter + 0.05f) / (darker + 0.05f)
}

@Test
fun bodyTextHasEnoughContrastInBothThemes() {
    listOf(lightColorScheme(), darkColorScheme()).forEach { scheme ->
        assertTrue(contrastRatio(scheme.onSurface, scheme.surface) >= 4.5f)
        assertTrue(contrastRatio(scheme.onSurfaceVariant, scheme.surface) >= 4.5f)
    }
}
```

Use the app's own colour schemes instead of the Material defaults, and list the pairs the screen draws text or icons with. Use 3.0 for large text and icons.

## 3. Large font

Render the screen once with `LocalDensity provides Density(density, fontScale = 2f)` and assert that the main text nodes are still displayed (`assertIsDisplayed`). Add it only for a screen that is new or about text size (`kotlin-testing.md` → "What every change must test").
