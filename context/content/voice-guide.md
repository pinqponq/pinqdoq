# PinqPonq Content Voice Guide

Read by `pinq_article-writer` and `pinq_social-post` before drafting anything. Defines tone, language handling, and platform-specific formatting so output stays consistent across writers and sessions instead of drifting per session.

## Tone

**Technical, conversational.** Written by an engineer, for engineers — jargon is fine, but explain the *why* behind a decision, not just the *what*. First-person plural ("we hit this problem, here's how we solved it") over impersonal third-person. Avoid marketing language ("revolutionary", "game-changing", "seamless") and avoid dry textbook phrasing. A good test: if it sounds like a senior engineer explaining a real decision to a peer over coffee, it's right; if it sounds like a press release or a lecture, rewrite it.

## Write like a human, not like an AI

The single biggest tell that content was AI-generated is its *rhythm*, not its vocabulary. Fix the rhythm and the rest follows.

- **No em dashes ("—" or " - " used as a clause connector).** This is the single most recognizable AI tic. Rewrite as two sentences, or use a comma, colon, or parenthesis instead. A hyphen inside a compound word (`well-known`) is fine — that's not what this rule targets.
- **No formulaic transition openers**: "Moreover", "Furthermore", "In conclusion", "It's worth noting that", "Additionally". If a paragraph needs a transition, let the content itself carry it.
- **No rule-of-three padding**: "fast, reliable, and scalable" / "increases efficiency, reduces costs, and improves outcomes." If three adjectives or clauses are stacked and only one is doing real work, cut the other two.
- **No hedge-everything balance**: "While X has benefits, it's important to consider Y" as a reflexive pattern on every claim. Take an actual position; note real caveats only when they're real.
- **No generic framing openers**: "In today's fast-paced world", "In the ever-evolving landscape of...". Open with the actual concrete thing (see Structural defaults below).
- **Vary sentence length on purpose.** A string of same-length, same-structure sentences reads like a generator. Short sentence after a long one. Fragment when it earns its place.
- **Cut the summary-of-what-was-just-said.** Don't restate a section's content in its own closing line ("As we've seen, X is important because..."). Say it once.
- **Specifics over adjectives.** "Cut build time from 4 minutes to 40 seconds" beats "significantly faster." If a concrete number or example is available from grounding, use it instead of an intensifier.

## Deveng Group document standard (baseline quality bar)

This applies on top of everything above and comes from Deveng Group's internal "Document Writing Standard" — a document that fails it is treated as invalid, so it's the floor, not a nice-to-have:

- **Clear (açık):** stays on the stated purpose, matches the target reader's level, uses real headings to break up sections.
- **Understandable (anlaşılır):** plain language; a technical term gets a short gloss on first use unless the audience is guaranteed to already know it.
- **Plain (duru):** no padding, no decorative language, no repeated points. Prefer a short list over a long sentence when a topic is genuinely enumerable — but don't force lists where prose reads more naturally (over-listing is its own AI tell).
- **Information reliability:** every claim must be true and current; see Grounding below — this repo's version of it is stricter (session-verified, not just "believed true").
- **Source attribution:** anything not the writer's own idea gets an in-text citation, and every link used gets listed under a References section at the end.
- **Spelling and grammar:** zero tolerance — errors here invalidate the document under this standard.
- **Consistency:** one term for one concept throughout; established English technical terms (interface, class, data layer, presentation layer, etc.) are never translated into Turkish mid-document, even in the Turkish version.
- **Purpose stated up front:** the reader should know, from the opening, what they'll know by the end.
- **Author identity:** the writer's name goes at the end of the document, bold, properly capitalized (first-letter-uppercase, not all-caps).

## Language policy

Every deliverable ships as **two separate files**: one English, one Turkish. Turkish is a **natural adaptation**, not a literal translation — idioms, sentence rhythm, and technical-term choices (mixing English loanwords where that's how Turkish engineers actually talk, e.g. "deploy ettik", "commit atmak") should read as if originally written in Turkish. Keep code identifiers, library names, and product names unchanged in both versions.

## Emoji & hashtag policy: minimal

- **Medium/long-form article:** no emoji, no hashtags.
- **LinkedIn:** no emoji; 2–3 hashtags at the end of the post, relevant to the specific topic (not generic tags like `#tech`).
- **X (Twitter):** no emoji; 0–1 hashtag, only if genuinely relevant (e.g. a specific technology name).
- **Instagram:** no emoji in the main caption; 3–5 hashtags at the end (Instagram discovery depends on hashtags more than the other platforms, so it gets slightly more).

If a draft leans on emoji or hashtags to carry meaning or energy, that's a signal to fix the sentence, not decorate it.

## Link placement per platform

This is the part that's easy to get wrong, so it's explicit:

- **LinkedIn:** never put the article URL in the post body — LinkedIn's algorithm suppresses reach on posts with outbound links. The post body ends with a line pointing to the comments (e.g. "Full writeup linked in the comments."), and the URL is delivered as a **separate first-comment text**, not inside the post.
- **X:** the URL goes directly in the post (single tweet) or the final tweet of a thread. X does not penalize links the way LinkedIn does.
- **Instagram:** captions cannot contain clickable links. End with "Link in bio" (or the actual bio-link-tool destination if the user names one) — never paste a raw URL into the caption.

## Structural defaults

- **Article (Medium-style):** hook opening (a concrete problem or moment, not "In this article we will..."), then body with real headers, code snippets only where they clarify a decision (not full file dumps), and a short closing takeaway — not a generic "in conclusion" summary.
- **LinkedIn post:** 3–6 short paragraphs (1–2 sentences each), no bullet-point walls. Should stand alone as a complete thought, not read like a trailer.
- **X:** either one tweet (≤280 chars) or a thread where the first tweet is the hook and stands alone if nothing else gets read.
- **Instagram:** caption reads more narratively than LinkedIn — slightly warmer, still no fluff — roughly 100–150 words.

## Grounding

Every technical claim in the output must trace back to something actually read this session — real code, a real diff, a real README, or something the user stated directly. Never invent metrics, quotes, benchmark numbers, or feature behavior. If a detail is missing, state the gap and ask rather than filling it in.
