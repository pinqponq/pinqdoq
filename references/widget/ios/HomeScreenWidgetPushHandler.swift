// Template — widget extension target (iOS 26+).
import Foundation
import WidgetKit

/// Sends the widget's push token to the server, which then reloads the widget with a WidgetKit push
/// (apns-push-type: widgets). Unlike the app's notifications this needs no notification permission.
@available(iOS 26.0, *)
struct HomeScreenWidgetPushHandler: WidgetPushHandler {
    init() {}

    func pushTokenDidChange(_ pushInfo: WidgetPushInfo, widgets: [WidgetInfo]) {
        // No placed widget left: nothing reads this token; the server drops it once APNs reports it gone.
        guard !widgets.isEmpty else { return }

        HomeScreenWidgetSession.updatePushToken(pushInfo.token.map { String(format: "%02.2hhx", $0) }.joined())
        Task {
            await HomeScreenWidgetApi.registerWidgetPushTokenIfOutdated()
        }
    }
}
