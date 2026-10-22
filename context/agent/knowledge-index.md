# Ajan Bilgi İndeksi

Bu dökümanı okuyan kişi, Pinq Center ajanının hangi pinqdoq dökümanını hangi konuda okuyacağını öğrenecektir. Ajanın `find_pinqdoq_guide` aracı bu tabloyu okur ve konuya uyan satırları döndürür. Dökümanın kendisi `read_pinqdoq_document` ile okunur.

Tablo biçimi: her satır `| Konu | Anahtar kelimeler | Yol | Özet |` sütunlarından oluşur. Anahtar kelimeler virgülle ayrılır. Yeni döküman eklerken satırı bu tabloya ekleyin; aksi halde ajan dökümanı bulamaz.

| Konu | Anahtar kelimeler | Yol | Özet |
|---|---|---|---|
| Sistem haritası | sistem, harita, repo, proje, ürün, backend, istemci, nerede, hangi repo, mimari | context/agent/sistem-haritasi.md | Ürünlerin repoları ve bir sorunun hangi repoda aranacağı |
| Proje portföyü | portföy, proje listesi, rindle, pinqloq, pinqponq, nacevent, turan, smartpark, iş modeli | context/projects/pinqponq-proje-portfoyu.md | Her projenin durumu, iş modeli ve projeler arası ilişki |
| Ekip ve sorumluluklar | ekip, üye, kim, sorumlu, atama, sahip, backend geliştirici, mobil | context/team/members.md | Ekip üyelerinin rolleri, yetenekleri ve görev atama yönergesi |
| Görev kuralları | görev, kart, pano, issue, pr, çalıştırıcı, runner, kabul ölçütü, inceleme, test | context/agent/gorev-kurallari.md | Görevin nasıl seçildiği, yürütüldüğü ve incelemeye alındığı |
| Sorun giderme | sorun, hata, log, arıza, çalışmıyor, araştır, pinqloq, koleksiyon, neden | context/agent/sorun-giderme.md | Logları ve kodu kullanarak bir sorunu araştırma adımları |
| Genel kod kuralları | kural, standart, kod, yorum, test, güvenlik, yazım, isimlendirme | rules/common.md | Tüm projelerde geçerli kod ve test kuralları |
| .NET kuralları | dotnet, c#, backend, controller, servis, api, hata yönetimi | rules/dotnet-conventions.md | .NET backend kod standartları |
| Kotlin mimarisi | kotlin, mimari, mvi, katman, viewmodel, mobil, kmp, cmp | rules/kotlin-architecture.md | Kotlin projelerinde katmanlar ve MVI düzeni |
| Kotlin test kuralları | kotlin, test, mutasyon, pit, ekran görüntüsü, maestro, cihaz | rules/kotlin-testing.md | Her değişikliğin neyi test etmesi gerektiği ve cihaz kanıtı |
| Web test kuralları | web, playwright, typescript, uçtan uca, e2e | rules/web-testing.md | Web projelerinde Playwright ile kanıt |
| Vault yapılandırması | vault, gizli anahtar, yapılandırma, secret, appsettings, token | references/dotnet/vault-configuration.md | .NET projelerinde gizli ayarların Vault'tan okunması |
| Vault kurulumu | vault, cli, giriş, kurulum, geliştirici makinesi | references/dotnet/vault-cli-setup.md | Vault CLI kurulumu ve sorun giderme |
| Yeni ürün başlatma | yeni ürün, şablon, template, başlangıç, kurulum | references/templates/new-product-starter.md | Mobil ve backend şablonlarıyla yeni ürün başlatma |
| Görev çalıştırıcısı | çalıştırıcı, runner, otomatik görev, rutin, panel | runner/README.md | Görev çalıştırıcısının ne yaptığı ve nasıl kurulduğu |
| Döküman yazma | döküman, yazım, rehber, kalite, açık, duru | meta/document-writing-guide.md | Döküman yazma ölçütleri |

## Bilerek Dışarıda Bırakılanlar

- `references/kotlin/*`: derin Kotlin başvuruları kod yazarken gerekir; şefin sorularına yanıt için çok uzun ve dolaylıdır. Ajan gerekirse `list_pinqdoq_documents` ile bulabilir.
- `skills/*` ve `scripts/*`: kod üretme araçlarıdır, bilgi dökümanı değildir.
- `runner/skill/*`: çalıştırıcının iç betikleri ve şablonları. Genel anlatım için `runner/README.md` yeterlidir.
- `tasks/*`: kurulum adımlarıdır; ajanın yanıtlayacağı bir soru konusu değildir.
- Henüz yazılmamış dökümanlar: bir otopark sisteminin cihaz ve işlem akışları, ürün bazlı sorun giderme listeleri ve her ürünün log koleksiyon adları. Bunlar için ürün sahiplerinden bilgi gerekir; yazıldıklarında bu tabloya eklenir.
