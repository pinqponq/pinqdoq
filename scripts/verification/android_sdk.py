"""Points Gradle at the Android SDK when the shell did not.

A fresh worktree has no local.properties, and non-interactive shells miss ANDROID_HOME when it is only
exported in .zshrc, so Android Gradle builds started by the runner could not find the SDK.
"""
import os

DEFAULT_ANDROID_SDK_DIR = os.path.expanduser("~/Library/Android/sdk")


def ensure_android_sdk_environment():
    if os.environ.get("ANDROID_HOME") or not os.path.isdir(DEFAULT_ANDROID_SDK_DIR):
        return
    os.environ["ANDROID_HOME"] = DEFAULT_ANDROID_SDK_DIR
    os.environ.setdefault("ANDROID_SDK_ROOT", DEFAULT_ANDROID_SDK_DIR)
