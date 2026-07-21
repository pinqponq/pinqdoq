# Android CLI Araştırması

Bu döküman, Android geliştirmesinin komut satırından (CLI) yürütülmesini araştırır: SDK komut satırı araçları, Gradle ile build/test, emülatörün başsız (headless) çalıştırılması ve `adb` ile cihaz yönetimi. Amaç, IDE olmadan — CI ortamında veya bir ajan/otomasyon akışında — Android + KMP projelerinin derlenip test edilebilmesi için gereken araç setini ve komutları netleştirmektir.

Bu bir derin referanstır (`references/`), otomatik yüklenmez; ihtiyaç duyulduğunda okunur.

---

## Özet (TL;DR)

- Android SDK'nın tüm CLI yetenekleri **`cmdline-tools`** paketiyle gelir: `sdkmanager`, `avdmanager`, `apkanalyzer`, `lint`, `retrace`.
- Paket kurulumu ve lisans yönetimi **`sdkmanager`** ile yapılır; build/test ise **Gradle wrapper** (`./gradlew`) üzerinden çalışır — Android Studio hiçbir aşamada gerekmez.
- Birim testler emülatörsüz (`testDebugUnitTest`), enstrümantasyon testleri ise cihaz/emülatör ister (`connectedDebugAndroidTest`) veya **Gradle Managed Devices** ile CI'da otomatik emülatörle koşulur.
- Emülatör CI'da **başsız** çalıştırılır: `-no-window -no-audio -gpu swiftshader_indirect`.
- KMP projelerinde CLI aynıdır; sadece Gradle görevleri modül yollarıyla (`:shared:...`, `:composeApp:...`) hedeflenir.

---

## 1. Kapsam

**Kapsam içi:**

- Android SDK komut satırı araçlarının kurulumu ve envanteri.
- Gradle CLI ile derleme, test, lint ve paketleme.
- Emülatör ve AVD yönetiminin başsız kullanımı.
- `adb` ile cihaz/uygulama yönetimi.
- KMP (Kotlin Multiplatform) projelerine özgü notlar.
- CI ve ajan otomasyonu için öneriler.

**Kapsam dışı:**

- Android Studio IDE kullanımı.
- Uygulama içi mimari kararlar (bunun için `references/kotlin/architecture.md`).
- Play Store yayın süreci (imzalama komutlarına değinilir, mağaza akışına girilmez).

---

## 2. Araç envanteri

Android'in CLI ekosistemi tek bir monolitik araç değildir; katmanlıdır.

| Araç | Geldiği paket | Görevi |
|---|---|---|
| `sdkmanager` | `cmdline-tools;latest` | SDK paketlerini kurar/günceller, lisansları kabul eder |
| `avdmanager` | `cmdline-tools;latest` | Android Virtual Device (AVD) oluşturur/siler/listeler |
| `apkanalyzer` | `cmdline-tools;latest` | APK/AAB boyut ve içerik analizi |
| `lint` | `cmdline-tools;latest` | Bağımsız statik analiz (genelde Gradle üzerinden çağrılır) |
| `adb` | `platform-tools` | Cihaz/emülatörle iletişim (install, shell, logcat) |
| `emulator` | `emulator` | AVD'leri çalıştıran sanal cihaz motoru |
| `gradle` / `./gradlew` | proje içi wrapper | Derleme, test, paketleme — asıl iş burada döner |

> **Not:** Eski `tools/` paketi (içinde `android` komutu vardı) kullanımdan kaldırılmıştır. Bugün doğru paket **`cmdline-tools`**'tur; içindeki ikililer `cmdline-tools/latest/bin/` altında yer alır.

---

## 3. Kurulum (başsız / CI)

### 3.1 Ortam değişkenleri

```bash
export ANDROID_HOME="$HOME/android-sdk"      # tercih edilen değişken
export ANDROID_SDK_ROOT="$ANDROID_HOME"      # eski isim; hâlâ okunur
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"
```

`ANDROID_HOME` güncel, `ANDROID_SDK_ROOT` ise geriye dönük uyumluluk içindir. İkisini de tanımlamak en güvenli yoldur.

### 3.2 `cmdline-tools` kurulumu

Komut satırı araçları zip olarak indirilir ve **`cmdline-tools/latest/`** düzenine yerleştirilir (bu dizin yapısı `sdkmanager`'ın kendini bulması için zorunludur):

```bash
mkdir -p "$ANDROID_HOME/cmdline-tools"
cd "$ANDROID_HOME/cmdline-tools"
# indirilen zip'i aç, klasörü 'latest' olarak yeniden adlandır
unzip -q commandlinetools-linux-*.zip
mv cmdline-tools latest
```

### 3.3 Paketleri kurma ve lisans kabulü

```bash
# Lisansları başsız kabul et (CI'da şart)
yes | sdkmanager --licenses

# Derleme için gereken temel paketler
sdkmanager "platform-tools" \
           "platforms;android-35" \
           "build-tools;35.0.0"
```

- `platforms;android-XX` → derleme hedefi (`compileSdk`).
- `build-tools;XX.Y.Z` → `aapt2`, `d8`, `zipalign`, `apksigner` gibi düşük seviye araçlar.
- Kurulu paketleri görmek: `sdkmanager --list_installed`.

> ✅ Sürümleri projenin `build.gradle` içindeki `compileSdk` / `buildToolsVersion` ile hizala.
> ❌ Lisansları interaktif beklemede bırakma; CI'da `yes | sdkmanager --licenses` olmadan build donar.

---

## 4. Gradle CLI ile build, test, lint

Asıl iş Gradle wrapper üzerinden döner. Wrapper (`./gradlew`) projeye pinlenmiş Gradle sürümünü kullandığı için ayrıca Gradle kurmaya gerek yoktur.

### 4.1 Derleme ve paketleme

```bash
./gradlew assembleDebug            # debug APK üretir
./gradlew assembleRelease          # release APK (imzalama config'i gerekir)
./gradlew bundleRelease            # Play Store için AAB üretir
```

### 4.2 Testler

```bash
./gradlew testDebugUnitTest        # JVM birim testleri — emülatör GEREKMEZ
./gradlew connectedDebugAndroidTest# enstrümantasyon testleri — cihaz/emülatör GEREKİR
./gradlew check                    # tüm doğrulama görevleri (unit test + lint)
```

- **Birim testler** JVM'de koşar; hızlıdır, CI'da her PR'da çalıştırılmalıdır.
- **Enstrümantasyon testleri** gerçek/sanal cihazda koşar; yavaştır ve emülatör altyapısı ister (bkz. §5, §6).

### 4.3 Lint

```bash
./gradlew lintDebug                # HTML/XML rapor üretir (build/reports/lint-results-*.html)
./gradlew lint                     # tüm varyantlar
```

### 4.4 Faydalı bayraklar

```bash
./gradlew assembleDebug --stacktrace   # hata izini tam göster
./gradlew testDebugUnitTest --info     # ayrıntılı log
./gradlew build --offline              # ağ olmadan, cache'ten
./gradlew --stop                       # takılan Gradle daemon'ları öldür
```

> ✅ CI'da `./gradlew` kullan (sürüm pinlenmiş, tekrarlanabilir).
> ❌ Sistemsel `gradle` komutuna güvenme; sürüm sürüklenmesine yol açar.

---

## 5. Emülatör ve AVD yönetimi (başsız)

### 5.1 Sistem imajı kurulumu

```bash
sdkmanager "system-images;android-35;google_apis;x86_64" "emulator"
```

### 5.2 AVD oluşturma

```bash
echo "no" | avdmanager create avd \
  -n ci_pixel \
  -k "system-images;android-35;google_apis;x86_64" \
  --device "pixel_7"

avdmanager list avd       # mevcut AVD'leri listele
```

### 5.3 Başsız çalıştırma (CI için)

```bash
emulator -avd ci_pixel \
  -no-window -no-audio -no-boot-anim \
  -gpu swiftshader_indirect \
  -no-snapshot &
```

- `-no-window` → GUI'siz (headless).
- `-gpu swiftshader_indirect` → yazılım GPU; ekran kartı olmayan CI makineleri için.
- `-no-snapshot` → temiz, tekrarlanabilir başlangıç durumu.

### 5.4 Emülatörün hazır olmasını bekleme

Emülatör başlar ama boot bitmeden test koşulamaz. Boot tamamlanana kadar beklemek gerekir:

```bash
adb wait-for-device
# sys.boot_completed 1 olana kadar bekle
until [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" = "1" ]; do sleep 2; done
```

> **CI tavsiyesi:** El ile emülatör ayağa kaldırmak yerine **Gradle Managed Devices** kullan (§7.2). Emülatör yaşam döngüsünü Gradle yönetir, boot bekleme mantığını sen yazmazsın.

---

## 6. `adb` ile cihaz ve uygulama yönetimi

```bash
adb devices                                   # bağlı cihaz/emülatörleri listele
adb install -r app/build/outputs/apk/debug/app-debug.apk   # kur (yeniden kur)
adb uninstall com.pinqponq.app                # kaldır
adb shell am start -n com.pinqponq.app/.MainActivity       # aktiviteyi başlat
adb logcat -v time                            # cihaz loglarını akıt
adb shell screencap -p /sdcard/shot.png && adb pull /sdcard/shot.png   # ekran görüntüsü
adb emu kill                                  # başsız emülatörü kapat
```

Birden fazla cihaz bağlıysa hedefi `-s` ile seç: `adb -s emulator-5554 install ...`.

---

## 7. KMP ve CI otomasyonu

### 7.1 KMP'ye özgü Gradle görevleri

CLI, saf Android ile aynıdır; yalnızca görevler modül yollarıyla hedeflenir:

```bash
./gradlew :shared:assemble                    # ortak (shared) modülü derle
./gradlew :shared:testDebugUnitTest           # ortak modülün Android birim testleri
./gradlew :shared:iosSimulatorArm64Test       # ortak modülün iOS testleri (macOS runner'da)
./gradlew :composeApp:assembleDebug           # Android uygulama modülü
./gradlew tasks --all                          # projedeki tüm görevleri keşfet
```

> **Not:** `iosSimulatorArm64Test` ve diğer iOS/Apple hedefleri yalnızca **macOS** runner'da çalışır; Linux CI yalnızca Android/JVM/JS hedeflerini derleyebilir.

### 7.2 Gradle Managed Devices (önerilen CI yolu)

Emülatörü el ile yönetmek yerine, sanal cihazı Gradle tanımlar ve yaşam döngüsünü kendi yönetir:

```kotlin
// build.gradle.kts (android { ... } bloğu içinde)
testOptions {
    managedDevices {
        localDevices {
            create("pixel7api35") {
                device = "Pixel 7"
                apiLevel = 35
                systemImageSource = "google_apis"
            }
        }
    }
}
```

```bash
./gradlew pixel7api35DebugAndroidTest   # emülatörü kurar, açar, testi koşar, kapatır
```

Bu yaklaşım tekrarlanabilir, boot-bekleme mantığı gerektirmez ve CI günlüğünde deterministiktir.

### 7.3 CI adım sıralaması (referans akış)

1. JDK 17+ ve `cmdline-tools` kurulumu, `ANDROID_HOME` ayarı (§3).
2. `yes | sdkmanager --licenses` ile lisans kabulü.
3. Gerekli paketleri kur (`platforms`, `build-tools`, gerekiyorsa `system-images`).
4. `./gradlew lintDebug` — statik analiz.
5. `./gradlew testDebugUnitTest` — hızlı birim testleri (her PR).
6. `./gradlew <device>DebugAndroidTest` — enstrümantasyon testleri (Managed Devices ile).
7. `./gradlew bundleRelease` — yayın adayı paketleme (yalnızca release dalında).

> ✅ Gradle build cache ve dependency cache'i CI'da persiste et (`~/.gradle/caches`) — süreyi ciddi düşürür.
> ❌ Her adımda ayrı bir Gradle daemon başlatma; `org.gradle.daemon=false` ile CI'da daemon'ı kapatmak daha öngörülebilirdir.

---

## 8. Ajan / otomasyon için notlar

Bir ajanın (ör. Claude Code) Android projesini başsız sürebilmesi için:

- **Derleme ve birim test** ağ + JVM ile yeterlidir; emülatör gerektirmez. Bir değişikliği doğrulamanın en ucuz yolu `./gradlew testDebugUnitTest` ve `./gradlew lintDebug`'dır.
- **Görsel/enstrümantasyon doğrulaması** gerekiyorsa Managed Devices tercih edilmeli; el ile emülatör yönetimi kırılgandır.
- **Ekran görüntüsü** ile UI doğrulaması `adb shell screencap` + `adb pull` ile alınabilir.
- Uzun süren komutlar (emülatör boot, connected test) arka planda çalıştırılıp durum bir koşulla beklenmelidir; sabit `sleep` yerine `sys.boot_completed` gibi gerçek sinyaller yoklanmalıdır.

---

## 9. Kaynaklar

- Android SDK Command-Line Tools — `developer.android.com/tools`
- `sdkmanager` — `developer.android.com/tools/sdkmanager`
- `avdmanager` — `developer.android.com/tools/avdmanager`
- `adb` (Android Debug Bridge) — `developer.android.com/tools/adb`
- Emulator komut satırı — `developer.android.com/studio/run/emulator-commandline`
- Gradle Managed Devices — `developer.android.com/studio/test/gradle-managed-devices`
- Gradle ile komut satırından build — `developer.android.com/build/building-cmdline`
