# pinqloq Task Runner — run mail format (step 4)

Read this file before writing a run mail (step 4, or the finishing mail in step 6).

One mail per run, subject `Görev önerileri — <date>` when there are new proposals, otherwise `Durum — <date>`. Sections, in order, omit empty ones:
1. **Yeni öneriler** — numbered cards (numbers unique within this mail): title + link, repo, assignee, plan (2–4 bullets), doability/risk badge, human-required parts, open questions (A/B/C + öneri).
2. **Sorular** — questions for already-selected tasks (a question already mailed is repeated at most once per day, as a short reminder) (also sent this way instead of separate mails when the run has several).
3. **Tamamlananlar** — PR links, what was tested, thumbnails (attach up to 5 screenshots, total < 20 MB). A mistake made although a pinqdoq rule already covered it goes under its own heading "Kurala rağmen yapılan hatalar" (rule file:line, why it was missed, what was done; see `references/lessons.md`). Lesson PRs opened in pinqdoq go here too (`Ders PR'ı: <link>, <rule in one line>`); a lesson that only concerns the runner's own procedure goes under "Runner için öneri".
4. **İnsan gerekiyor** — blocked items and exactly what a person must do.
5. **Yoksayılan yorumlar** — comments from non-members, per trust rules.
6. **Duyurular** — every entry of `state.json` `pending_announcements` (after sending, remove the entries that were sent).
7. Footer: how to answer — "Bu mail otomatik gönderilir, cevaplar okunmaz. Karar için ilgili issue'ya yorum yazın: `Yap`, `Yapma` veya `S1: B`. Açılan bir PR'da değişiklik için PR'a review/yorum bırakın ya da issue'ya `Düzelt: <ne değişmeli>` yazın." Every card and question links its issue so the answer is one click away.

Write HTML with inline styles only (mail clients strip `<style>`), max width 680px, primary accent `#FFC964`, badges: Low=green `#2e7d32`, Medium=amber `#b26a00`, High=red `#c62828`. Keep a plain-text alternative with the same content.
Send with `python3 scripts/mailer.py send --subject … --html … --text … [--attach …]`; store the returned `message_id` in `proposals[]` and each task's `proposal_message_id` / `question_message_id`.
