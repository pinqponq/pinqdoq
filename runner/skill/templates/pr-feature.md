Closes #<n>

## Özet
<1–3 sentences in plain words for a reader who has not seen the task: what the user can do now and which tickets it covers.>

## Değişiklikler
- <2–5 bullets, behaviour level>

## Test videosu
- Android: <link>
- iOS: <link, if the change touches shared UI>
- Web: <video link of the Playwright proof run, for a web project>

## Ekran görüntüleri
<only the new/changed states; omit if the video covers it>

## pinqloq
<the new flow's requests/events on the device run window, one table, max 5 rows; errors = 0 or explained>

## UI inceleme
<UI change only; omit otherwise. Paste the output of `ui_review_report.py section` from the last round.>

## Testler
<result lines only, never the full test list>
- `<TestClass>`: <what it proves, one line each, at most 5>
- `<exact command>` → <result>
- Mutation (PIT, değişen satırlar): <skor>% (<öldürülen>/<toplam>); kalan: <dosya:satır → tek satır gerekçe, yoksa "yok">

## Notlar
<only if needed, one line each: human follow-ups, `Merge ortamı: <environment the base deploys to on push>` when the repository deploys from the base>
pinq_code-review origin/<base>...HEAD: <result>; denetlenen: <n> yorum bloğu, <m> composable
Otomatik merge: kapılar <✅/❌ her kapı, references/implementation.md → "Auto-merge rubric">
Risk: <düşük | düşük değil: neden>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
