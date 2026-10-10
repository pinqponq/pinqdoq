Closes #<n>

## Bug
<1–3 sentences: what the user saw, and the root cause.>

## Çözüm
- <2–4 bullets, behaviour level, not a file list>

## pinqloq: önce
<incident time (UTC) + the query used, one table, max 5 rows>

| Zaman | Endpoint / olay | Durum | Adet |
|---|---|---|---|

## pinqloq: sonra
<same queries on the fixed build's device run windows, same table shape; one line per platform>

## Test videosu
- Android: <link>
- iOS: <link, if the change touches shared UI>

## Ekran görüntüleri
<only if they show something the video does not; otherwise omit this section>

## Testler
- `<TestClass>`: <what it proves, one line each>
- `<exact command>` → <result>
- Mutation (PIT, değişen satırlar): <skor>% (<öldürülen>/<toplam>); kalan: <dosya:satır → tek satır gerekçe, yoksa "yok">

## Notlar
<only if needed, one line each: scenario differences (table only when reality could not be matched), human follow-ups, `pinq_code-review origin/<base>...HEAD: <result>`>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
