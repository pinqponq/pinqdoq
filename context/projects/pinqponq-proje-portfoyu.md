# Pinqponq Proje Portföyü

Bu dökümanı okuyan kişi Pinqponq'un mevcut proje portföyünü, her projenin durumunu, iş modelini ve projeler arasındaki stratejik ilişkiyi öğrenecektir.

## Genel Bakış

Pinqponq şu anda 7 aktif proje üzerinde çalışmaktadır. Bu projeler üç ana kategoriye ayrılabilir:

- **Müşteri projeleri:** Turan
- **Ürünleştirilmiş / satılabilir hale getirilen projeler:** Rindle, Pinqponq, Pinqloq, NacEvent
- **Değerlendirme aşamasındaki veya kısıtlı projeler:** Smartpark, Discord Bot

Aşağıdaki bölümlerde her proje ayrı ayrı ele alınmış, ardından projeler arasındaki bağlantılar özetlenmiştir.

---

## Projeler

### Smartpark

- Şu anda yatırıma açık bir proje değildir.

### Turan

- Bir müşteri için geliştirilip teslim edilmiş, tamamlanmış bir projedir.
- Şirket portföyünde gösterge (referans) niteliğinde tutulmaktadır.
- Forex verilerinin anlık (real-time) olarak gösterilmesini sağladığı için değerli kabul edilmektedir.

### Discord Bot

- Teknik olarak hazır durumdadır.
- Şu an itibarıyla satılabilir bir halde değildir; bunun nedeni ödeme sağlayıcı şirketlerin Discord üzerinden abonelik açılmasına izin vermemesidir.
- Yüksek ihtimalle ücretsiz olarak yayınlanması planlanmaktadır.

### Pinqloq

- NacEvent, Pinqponq ve Rindle projeleriyle birbirine bağlı çalışan bir altyapı (infrastructure) bileşenidir.
- Amacı, tüm client projelerinin ve bu projelere ait backend'lerin loglanabilmesi, kullanıcı alışkanlıklarının tespit edilebilmesi ve sahada karşılaşılan bugların daha hızlı çözülebilmesidir.
- Satılabilir bir ürüne dönüştürülmüştür: kullanıcıların kayıt olup kendilerine ait bir secret key oluşturarak istedikleri projelerde loglama yapabilmelerini sağlayan bir panel geliştirilmiştir.
- Simpra şirketine ücretsiz pilot olarak sunulması planlanmaktadır.

### Rindle

- Şirketin en çok değer verdiği, büyük uygulama mağazalarında (store) yayınlanması planlanan bir uygulamadır.
- Rindle'a ve ileride geliştirilecek diğer uygulamalara chat özelliği eklenmesi hedeflenmektedir; Rindle özelinde bu entegrasyon kesinleşmiş durumdadır.

### Pinqponq

- Rindle'a entegre edilecek chat özelliğini sağlamak amacıyla geliştirilen bir chat SDK'sıdır.
- Dışarıya da satılabilmesi için ayrı bir panel geliştirilmiştir; bu panel sayesinde kullanıcılar kendi uygulamalarına kolayca chat entegrasyonu yapabilmektedir.
- Şu anda Kotlin/Compose Multiplatform first olarak tasarlanmıştır.
- İleriki aşamada Kotlin Multiplatform kullanılarak platformlara özel native SDK'ların çıkarılması hedeflenmektedir.

### NacEvent

- Şu anda aktif olarak satılan bir projedir.
- Düğünlerde masalara konulan QR kodunu okutan misafirlerin çektikleri fotoğrafların tek bir yerde toplanmasını sağlar.
- Gelir getirici olmasının yanında ikinci bir amacı daha bulunmaktadır: QR kodu okutan misafirlerin e-posta adreslerinin toplanması. Toplanan bu e-postaların Rindle'ın tanıtımı amacıyla kullanılması planlanmaktadır.

---

## Projeler Arası İlişki

- **Pinqloq**, NacEvent, Pinqponq ve Rindle projelerinin ortak altyapısı konumundadır; bu üç projenin backend'lerinin loglanmasını ve izlenmesini sağlar.
- **Pinqponq**, doğrudan **Rindle**'ın chat ihtiyacı için geliştirilmiştir ve Rindle'a entegre edilecektir.
- **NacEvent**, hem bağımsız bir gelir kaynağı hem de **Rindle**'ın kullanıcı tanıtımı için bir kanal (e-posta toplama) olarak konumlandırılmıştır.
- **Pinqloq**, Simpra şirketine ücretsiz pilot olarak sunularak saha kullanımıyla test edilecektir.
- **Turan**, aktif geliştirme kapsamında olmayıp portföy göstergesi olarak referans niteliğindedir.

---

## Özet Tablo

| Proje | Durum | Model |
|---|---|---|
| Smartpark | Yatırıma açık değil | Değerlendirme aşamasında |
| Turan | Tamamlanmış, teslim edilmiş | Portföy göstergesi |
| Discord Bot | Teknik olarak hazır, satılabilir değil | Muhtemelen ücretsiz yayın |
| Pinqloq | Aktif, satılabilir panel mevcut, Simpra'ya ücretsiz pilot verilecek | Loglama altyapısı (SaaS) |
| Rindle | Geliştirme aşamasında | Store uygulaması (flagship) |
| Pinqponq | Geliştirme aşamasında, panel mevcut | Chat SDK (SaaS + iç kullanım) |
| NacEvent | Aktif satışta | Etkinlik uygulaması + pazarlama kanalı |
