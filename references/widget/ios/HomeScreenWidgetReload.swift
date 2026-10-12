// Template — app target. Register the reload handler at launch (AppDelegate didFinishLaunching):
//
//     IosHomeScreenWidgetBridge.shared.setReloadHandler {
//         HomeScreenWidgetReload.reloadHomeScreenWidgets()
//     }
//
// IosHomeScreenWidgetBridge is a one-function Kotlin object in the app's own iosMain that forwards to
// deveng-widget's IosHomeScreenWidgetReloader.setReloadHandler (the app framework does not export the library).
import Foundation
import WidgetKit

/// Reloads the home screen widget from the app. Reloads made while the app is in the foreground do not count
/// against the widget's daily refresh budget, so the app reloads whenever it may have news.
enum HomeScreenWidgetReload {
    /// Keep in sync with homeScreenWidgetKind in the widget extension.
    private static let homeScreenWidgetKind = "<APP_NAME>HomeScreenWidget"

    static func reloadHomeScreenWidgets() {
        WidgetCenter.shared.reloadTimelines(ofKind: homeScreenWidgetKind)
    }
}
