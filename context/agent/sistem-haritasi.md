# Sistem Haritası

Bu dökümanı okuyan kişi, Pinqponq ürünlerinin hangi repolardan oluştuğunu, repoların birbiriyle nasıl bağlandığını ve bir sorunun hangi repoda aranacağını öğrenecektir. Ürünlerin iş tarafı için `context/projects/pinqponq-proje-portfoyu.md` dökümanına bakın.

## Nasıl Okunur

- Her ürünün bir backend'i, bir veya birkaç istemcisi (mobil, web) ve gerekirse bir SDK'sı vardır.
- Repo adları `pinqponq` organizasyonundaki adlardır. Bu dökümanda anlatılmayan bir repo hakkında bilgi yoksa bunu açıkça söyleyin; tahmin etmeyin.
- Backend repoları C# (.NET) ile, mobil ve web istemciler Kotlin Multiplatform / Compose Multiplatform (KMP/CMP) ile yazılır. Web sitelerinin bir kısmı TypeScript'tir.

## Ürünler ve Repoları

### Pinqloq (log altyapısı)

Diğer ürünlerin istemcilerini ve backend'lerini loglar. Hata ayıklamada ilk bakılacak yer burasıdır.

| Parça | Repo |
|---|---|
| Log toplama backend'i | `pinqloq-backend` |
| Dashboard backend'i (kayıt, proje, API anahtarı yönetimi) | `pinqloq-dashboard-backend` |
| Dashboard web sitesi | `pinqloq-dashboard` |
| Log paneli (WASM) | `pinqloq` |
| MCP sunucusu (logları araçlarla sorgulamak için) | `pinqloq-mcp-server` |
| SDK'lar | `pinqloq-go-sdk`, `pinqloq-nodejs-sdk`, `pinqloq-ruby-sdk` ve .NET NuGet paketi |

### Pinqponq (sohbet SDK'sı)

Rindle'ın sohbet ihtiyacı için geliştirilmiş, ayrıca dışarıya satılabilen sohbet SDK'sıdır.

| Parça | Repo |
|---|---|
| Backend | `pinqponq-server` |
| Mobil SDK (KMP) | `pinqponq-chat-kmp` |
| Dashboard | `pinqponq-dashboard` |
| Web istemcisi | `pinqponq-web-kmp` |

### Rindle

| Parça | Repo |
|---|---|
| Mobil uygulama (CMP) | `rindle-cmp` |
| Backend | `rindle-backend` |
| Tanıtım sitesi | `rindle.app` |

`rindle-backend` için `develop` ve `master` dallarına yapılan push yayına alma (deploy) başlatır; bu dallara doğrudan yazılmaz.

### NacEvent

Düğün masalarındaki QR kodla fotoğraf toplayan ürün. Repo: `NACEVENT`.

### Pinq Center

Otopark şeflerinin sohbet ederek sorun sorduğu ve geliştiricilerin vakaları gördüğü ürün.

| Parça | Repo |
|---|---|
| Backend: sohbet, ajan, vakalar, geliştirici API'si | `pinq-center-backend` |
| Uygulama (Android, iOS, web) | `pinq-center-kmp` |

Ajan, sorulara Pinqloq loglarından, repo kaynak kodundan ve pinqdoq dökümanlarından yanıt verir; yalnızca okur, hiçbir sistemi değiştirmez.

### Otomasyon ve ajanlar

| Parça | Repo |
|---|---|
| Orkestratör (sahibin konuştuğu Claude Code oturumunun klasörü) | `pinq-orchestrator` |
| Görev çalıştırıcısının yerel web paneli | `pinq-agents-dashboard` |
| Ajan uygulaması (KMP) ve backend'i | `pinqagents`, `pinqagents-backend` |
| Dökümanlar, kurallar, beceriler (skill), görev çalıştırıcısı | `pinqdoq` |

### Ortak kütüphaneler ve altyapı

| Parça | Repo |
|---|---|
| KMP ortak bileşen kütüphanesi | `deveng-core-kmp` |
| Açık kaynak .NET altyapı paketleri (kimlik, OTP, SSO, önbellek, SMS, e-posta, veritabanı, RabbitMQ, hata yönetimi) | `pinqnuqets` |
| Kapalı sunucular için dağıtım (deploy) aracı | `pinqops` |
| Yeni ürün şablonları | `backend-service-template`, `kmp-app-template` |

### Müşteri projesi

`Turan` ve `TuranBackoffice`: bir müşteri için teslim edilmiş proje. Aktif geliştirme kapsamında değildir.

## Bir Sorun Nerede Aranır

1. Hata bir istemcide görülüyorsa önce ürünün Pinqloq loglarına bakın (`sorun-giderme.md`).
2. Log bir backend isteğinin başarısız olduğunu gösteriyorsa ilgili backend reposunun kodunu okuyun.
3. Davranışın kuralı soruluyorsa `rules/` altındaki dökümanlara bakın (`knowledge-index.md` hangisinin ne anlattığını söyler).
4. Hangi repoda aranacağı belli değilse bu tabloyu kullanın; tabloda yoksa bunu söyleyin.

## Referanslar

- `context/projects/pinqponq-proje-portfoyu.md`
- `README.md` (pinqdoq yerleşimi)
