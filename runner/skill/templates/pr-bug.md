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
- Web: <video link of the Playwright proof run, for a web project; also the old-code proof run and, when it failed, its trace in a private repo (public repo: the failing step and its screenshot)>

## Ekran görüntüleri
<only if they show something the video does not; otherwise omit this section>

## UI inceleme
<UI change only; omit otherwise. Paste the output of `ui_review_report.py section` from the last round.>

## Testler
- `<TestClass>`: <what it proves, one line each>
- `<exact command>` → <result>
- Mutation (PIT, değişen satırlar): <skor>% (<öldürülen>/<toplam>); kalan: <dosya:satır → tek satır gerekçe, yoksa "yok">

## Notlar
<only if needed, one line each: scenario differences (table only when reality could not be matched), human follow-ups, `Merge ortamı: <environment the base deploys to on push>` when the repository deploys from the base, `pinq_code-review origin/<base>...HEAD: <result>`>
Otomatik merge: kapılar <✅/❌ her kapı, references/implementation.md → "Auto-merge rubric">
Risk: <düşük | düşük değil: neden>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
