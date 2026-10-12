// Template — widget extension target. Only the parts every widget needs: the kind, the timeline loader that
// re-registers the push token, and the iOS 26 push handler. The entry view and state are product-specific.
import SwiftUI
import WidgetKit

/// Keep in sync with HomeScreenWidgetReload.homeScreenWidgetKind in the app target, which reloads this widget by kind.
let homeScreenWidgetKind = "<APP_NAME>HomeScreenWidget"

/// Fallback for widget pushes that never arrive; WidgetKit may stretch it under its refresh budget.
private let timelineRefreshInterval: TimeInterval = 30 * 60

struct HomeScreenWidgetEntry: TimelineEntry {
    let date: Date
    let widgetState: HomeScreenWidgetState
}

struct HomeScreenWidgetProvider: TimelineProvider {
    func placeholder(in context: Context) -> HomeScreenWidgetEntry {
        HomeScreenWidgetEntry(date: Date(), widgetState: .signedOut)
    }

    func getSnapshot(in context: Context, completion: @escaping (HomeScreenWidgetEntry) -> Void) {
        completion(placeholder(in: context))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<HomeScreenWidgetEntry>) -> Void) {
        Task {
            let widgetState = await loadState()
            let now = Date()
            let entry = HomeScreenWidgetEntry(date: now, widgetState: widgetState)
            completion(Timeline(entries: [entry], policy: .after(now.addingTimeInterval(timelineRefreshInterval))))
        }
    }

    /// Every timeline refresh also re-registers the push token when its owner changed (account switch, unpair).
    private func loadState() async -> HomeScreenWidgetState {
        do {
            let contentResponse = try await HomeScreenWidgetApi.fetchWidgetContent()
            await HomeScreenWidgetApi.registerWidgetPushTokenIfOutdated()
            return HomeScreenWidgetState(contentResponse: contentResponse)
        } catch HomeScreenWidgetApiError.notSignedIn, HomeScreenWidgetApiError.tokenRejected {
            return .signedOut
        } catch {
            print("[HomeScreenWidget] Widget content could not be fetched: \(error)")
            return .signedOut
        }
    }
}

struct HomeScreenWidget: Widget {
    /// `.pushHandler` exists only on iOS 26+. Widget.body has no result builder, so each branch returns
    /// explicitly; that is what lets the two branches be different configuration types.
    var body: some WidgetConfiguration {
        if #available(iOS 26.0, *) {
            return StaticConfiguration(kind: homeScreenWidgetKind, provider: HomeScreenWidgetProvider()) { entry in
                HomeScreenWidgetEntryView(entry: entry)
            }
            .pushHandler(HomeScreenWidgetPushHandler.self)
        } else {
            return StaticConfiguration(kind: homeScreenWidgetKind, provider: HomeScreenWidgetProvider()) { entry in
                HomeScreenWidgetEntryView(entry: entry)
            }
        }
    }
}
