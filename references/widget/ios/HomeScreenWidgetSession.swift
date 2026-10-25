// Template — widget extension target. Replace <APP_GROUP_IDENTIFIER> with the App Group both targets use.
import Foundation

/// What the app hands the widget through the App Group (deveng-widget HomeScreenWidgetSessionStorageImpl writes
/// these keys): the widget runs in its own process and has no access to the app's session.
enum HomeScreenWidgetSession {
    static let appGroupIdentifier = "<APP_GROUP_IDENTIFIER>"

    /// Written by the Kotlin side; the names must stay in sync with HomeScreenWidgetSessionStorageImpl.kt.
    private static let widgetTokenKey = "home_screen_widget_token"
    private static let deviceIdentifierKey = "home_screen_widget_device_identifier"
    private static let apiBaseUrlKey = "home_screen_widget_api_base_url"

    /// Written only by the extension.
    private static let pushTokenKey = "home_screen_widget_push_token"
    private static let pushTokenRegisteredWidgetTokenKey = "home_screen_widget_push_token_registered_widget_token"

    private static var sharedDefaults: UserDefaults? {
        UserDefaults(suiteName: appGroupIdentifier)
    }

    static var widgetToken: String? {
        readNonEmptyValue(forKey: widgetTokenKey)
    }

    static var deviceIdentifier: String? {
        readNonEmptyValue(forKey: deviceIdentifierKey)
    }

    static var apiBaseUrl: URL? {
        readNonEmptyValue(forKey: apiBaseUrlKey).flatMap(URL.init(string:))
    }

    /// Called when the server rejects the token (revoked on logout or unpair). The app issues a new one
    /// the next time it starts signed in; until then the widget shows the signed-out state.
    static func forgetWidgetToken() {
        sharedDefaults?.removeObject(forKey: widgetTokenKey)
    }

    /// The widget's latest APNs push token (iOS 26+), kept so it can be registered again for a new owner.
    static var pushTokenHex: String? {
        readNonEmptyValue(forKey: pushTokenKey)
    }

    /// A rotated push token has never been registered, whoever the widget token belongs to.
    static func updatePushToken(_ newPushTokenHex: String) {
        guard newPushTokenHex != pushTokenHex else { return }
        sharedDefaults?.set(newPushTokenHex, forKey: pushTokenKey)
        sharedDefaults?.removeObject(forKey: pushTokenRegisteredWidgetTokenKey)
    }

    /// The server stores the push token under the widget token's owner. When the widget token changes (a
    /// different account signs in, or unpair issued a new one) — or the first registration failed because
    /// the widget was placed before the app handed over a token — the push token must be sent again.
    static var isPushTokenRegistrationOutdated: Bool {
        guard pushTokenHex != nil, let widgetToken else { return false }
        return sharedDefaults?.string(forKey: pushTokenRegisteredWidgetTokenKey) != widgetToken
    }

    static func markPushTokenRegistered() {
        sharedDefaults?.set(widgetToken, forKey: pushTokenRegisteredWidgetTokenKey)
    }

    private static func readNonEmptyValue(forKey key: String) -> String? {
        guard let value = sharedDefaults?.string(forKey: key), !value.isEmpty else { return nil }
        return value
    }
}
