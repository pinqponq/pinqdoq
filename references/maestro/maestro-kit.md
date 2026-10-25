# Maestro Kit — Device Scenarios for a New App

Scripts and subflows every KMP app needs for Maestro device scenarios (Android emulator + iOS simulator), without product values. First user: rindle-cmp (`maestro/`). Copy the kit into the app; the app adds its own texts in thin wrapper subflows.

## 1. Layout in the app

```
maestro/
├── app-ids.env              ← ANDROID_APP_ID=… / IOS_APP_ID=… (the app's, committed)
├── config.yaml              ← which flow folders a directory run includes
├── scripts/                 ← copied from scripts/ here, unchanged
│   ├── run-flow.sh
│   ├── with-test-account.sh
│   ├── slow-network-from-step.sh
│   └── slow-proxy.py
├── subflows/
│   ├── kit/                 ← copied from subflows/ here, unchanged
│   ├── login.yaml           ← app wrapper: passes the app's texts to kit/login.yaml
│   ├── logout.yaml          ← app wrapper: navigates to the log-out button, then kit/logout.yaml
│   └── dismiss-interstitials.yaml   ← one kit/dismiss-interstitial.yaml call per one-time screen
└── <feature>/<scenario>.yaml
```

Keep the kit files unchanged so a newer kit can be copied over them; everything app-specific goes into the wrappers and `app-ids.env`.

## 2. Scripts

| Script | What it does |
|---|---|
| `run-flow.sh <android\|ios> <flow> [maestro args]` (from the app root) | Picks the booted device (requires `ANDROID_SERIAL` when several Android devices are connected), resets a snapshot's stale clock on Android, passes `APP_ID`, writes JUnit + screenshots to `build/maestro/<platform>/` |
| `with-test-account.sh <account> <android\|ios> <flow>` | Reads the test account from a local, never committed file (`TEST_ACCOUNTS_FILE`), passes `TEST_EMAIL` / `TEST_OTP` and masks them in the console output |
| `slow-network-from-step.sh <step> <delay> -- <command>` | Slows the Android emulator's traffic once the flow reaches a step (through `slow-proxy.py`), to widen race windows; puts the previous proxy setting back at the end |

## 3. Subflows

| Subflow | Parameters (env) |
|---|---|
| `kit/login.yaml` — e-mail + one-time code sign-in | `TEST_EMAIL`, `TEST_OTP` (from `with-test-account.sh`); `LOGIN_EMAIL_ENTRY_TEXT`, `LOGIN_EMAIL_FIELD_TEXT`, `LOGIN_CHANGE_EMAIL_TEXT`, `LOGIN_CODE_SCREEN_TEXT`, `LOGIN_CODE_FIELD_POINT`, `LOGIN_SIGNED_IN_TEXT` |
| `kit/logout.yaml` — confirm log-out, wait for the login screen | `LOGOUT_BUTTON_TEXT`, `LOGOUT_CONFIRM_QUESTION`, `LOGIN_EMAIL_ENTRY_TEXT` |
| `kit/dismiss-interstitial.yaml` — close one one-time screen if it is visible | `INTERSTITIAL_TEXT`, `INTERSTITIAL_DISMISS_TEXT` |
| `kit/answer-notification-prompt.yaml` — answer the system notification prompt on either platform | `PROMPT_ANSWER` (`allow` / `deny`) |

App wrapper example (`maestro/subflows/login.yaml`):

```yaml
appId: ${APP_ID}
---
- runFlow:
    file: kit/login.yaml
    env:
      LOGIN_EMAIL_ENTRY_TEXT: "Continue with mail"
      LOGIN_EMAIL_FIELD_TEXT: "Email*"
      LOGIN_CHANGE_EMAIL_TEXT: "Change email"
      LOGIN_CODE_SCREEN_TEXT: "Verify"
      LOGIN_CODE_FIELD_POINT: "50%,27%"
      LOGIN_SIGNED_IN_TEXT: "Bottom navigation icon"
- runFlow: dismiss-interstitials.yaml
```

The rules for proving a change on a device are in `rules/kotlin-testing.md` → "Proving UI changes on a device".
