// Template — widget extension target. Replace the <…> paths with the product backend's widget endpoints and
// HomeScreenWidgetContentResponse with the product's own response model.
import Foundation

enum HomeScreenWidgetApiError: Error {
    case notSignedIn
    case tokenRejected
    case requestFailed(statusCode: Int)
    case nonHttpResponse
}

/// Calls authenticated with the widget token instead of the app session (the Kotlin service sends the same header).
enum HomeScreenWidgetApi {
    private static let widgetTokenHeaderName = "X-Widget-Token"
    private static let unauthorizedStatusCode = 401
    private static let requestTimeoutSeconds: TimeInterval = 20

    static func fetchWidgetContent() async throws -> HomeScreenWidgetContentResponse {
        var request = try buildAuthorizedRequest(path: "<WIDGET_CONTENT_PATH>")
        request.httpMethod = "GET"
        let responseData = try await sendRequest(request)
        return try JSONDecoder().decode(HomeScreenWidgetContentResponse.self, from: responseData)
    }

    /// Registers the stored push token when its registration is missing or belongs to an older widget
    /// token. Failures are left for the next timeline refresh to retry.
    static func registerWidgetPushTokenIfOutdated() async {
        guard HomeScreenWidgetSession.isPushTokenRegistrationOutdated,
              let pushTokenHex = HomeScreenWidgetSession.pushTokenHex else { return }
        do {
            try await registerWidgetPushToken(pushTokenHex)
            HomeScreenWidgetSession.markPushTokenRegistered()
        } catch {
            print("[HomeScreenWidget] Widget push token registration failed, retried on next refresh: \(error)")
        }
    }

    private static func registerWidgetPushToken(_ pushTokenHex: String) async throws {
        guard let deviceIdentifier = HomeScreenWidgetSession.deviceIdentifier else { throw HomeScreenWidgetApiError.notSignedIn }

        var request = try buildAuthorizedRequest(path: "<WIDGET_PUSH_TOKEN_PATH>")
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let requestBody: [String: Any] = [
            "token": pushTokenHex,
            "deviceIdentifier": deviceIdentifier,
            "isSandbox": isSandboxBuild
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)
        _ = try await sendRequest(request)
    }

    /// Debug builds are signed with the development APNs environment; their tokens only work against the sandbox.
    private static var isSandboxBuild: Bool {
        #if DEBUG
        return true
        #else
        return false
        #endif
    }

    private static func buildAuthorizedRequest(path: String) throws -> URLRequest {
        guard let widgetToken = HomeScreenWidgetSession.widgetToken,
              let apiBaseUrl = HomeScreenWidgetSession.apiBaseUrl else {
            throw HomeScreenWidgetApiError.notSignedIn
        }

        var request = URLRequest(url: apiBaseUrl.appendingPathComponent(path), timeoutInterval: requestTimeoutSeconds)
        request.setValue(widgetToken, forHTTPHeaderField: widgetTokenHeaderName)
        return request
    }

    /// A 401 means the token was revoked; it is forgotten so the extension stops retrying with it.
    private static func sendRequest(_ request: URLRequest) async throws -> Data {
        let (responseData, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw HomeScreenWidgetApiError.nonHttpResponse
        }

        let statusCode = httpResponse.statusCode
        if statusCode == unauthorizedStatusCode {
            HomeScreenWidgetSession.forgetWidgetToken()
            throw HomeScreenWidgetApiError.tokenRejected
        }
        guard (200..<300).contains(statusCode) else {
            throw HomeScreenWidgetApiError.requestFailed(statusCode: statusCode)
        }
        return responseData
    }
}
