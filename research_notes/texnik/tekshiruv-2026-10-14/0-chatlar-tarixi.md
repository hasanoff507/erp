# Chat-history knowledge digest — AI ERP+POS Uzbekistan project

Scope: all `C:/Users/YuDix/.claude/projects/E--Project-erp/*.jsonl` (18 files) + their `*/subagents/*.jsonl`,
excluding the current chat (`5c546060-...`). Cross-checked against `E:/Project/erp/.toa/brain/*` (persistent
project memory) and the working tree (`git diff`, current `research_notes/` and `spec/` files).

Architecture of the history: one "mega-lead" session (**ebe4fb8c-73e8-4e66-b664-9b318df0e1ab**, Oct 10–12) is
where the human speaks directly and where team leads' questions are relayed ("Fleet mail"). Three persistent
teams exist, each with its own repeated/continued Claude Code sessions:
- **Research** (ports 4110-4119) — lead **Architect** (sessions 2218f2da, 23d55085, 54b05405, 7f075a94,
  b1217379, bb22ded9, all team-bridge `ae497854`), workers **Fiskal** (28228613), **Modelchi** (573973f6),
  **Integrator** (a2b0a4c6), reviewer **Tekshiruvchi** (8d7f8c5d). Produced `research_notes/texnik/*`.
- **Mahsulot** (product, ports 4150-4159) — lead **Architect** (65ba0d36), scout/planner **Mahsulotchi**
  (19a7e373), workers **UX** (09d65ca2), **Jarayonchi** (33e775d5), **AI-mahsulot** (a258f890), reviewer
  **Tekshiruvchi** (08e25695). Produced `spec/kod-uchun/*`.
- **Arxitektura** (ports 4160-4169) — per `.toa/brain/teams/arxitektura-975bf7.md`, **never produced anything**
  ("Recently accepted: none yet"); `spec/kod-uchun/` does not exist on disk. No session file for it was
  found among the 18 transcripts — it may not have logged, or its folder is simply absent.

Two Claude Docs artifacts matter:
- `https://claude.ai/code/artifact/6ae6f454-7251-499a-bf21-06a2ce40db5b` — **original market-research doc**
  (created ~Oct 10, pricing tiers 149k/349k/699k so'm/mo, target segment Tashkent grocery/wholesale). This is
  the artifact the human first pasted at ebe4fb8c L10 and named again in the `/objective` command (ebe4fb8c L150).
- `https://claude.ai/code/artifact/e57e7cd7-1117-40a7-8af5-8154a8d22540` — **"asosiy, tekshirilgan versiya"**
  (main, fact-checked version) that the Research team wrote technical findings into (modules, 8 mandatory tax
  systems, competitor tax-integration gaps, open questions for the user). Per brain note
  `texnik-tadqiqot-qayerda-nima-bor.md`, this doc supersedes `research_notes/texnik/08-11` as the source of truth.
- Two other `claude.ai/artifact/...` short-ids (`VLf6CQ4ixdbaHkw3aLCdd1`, `ECeGqhywp9N9o9rN1yBv1Q`) were opened
  once each with no content change — likely re-opens of the same docs, content not distinguishable from the
  above two.

---

## 1. Human user directives (verbatim + gloss, with transcript id and date)

All quotes are from direct human turns (role=user, plain string, not a tool-result/task-notification/fleet-mail
relay). Human writes casual Uzbek (Latin), no punctuation discipline.

1. **ebe4fb8c-73e8-4e66-b664-9b318df0e1ab.jsonl, L10, 2026-10-10T07:06:44Z**
   > "https://claude.ai/code/artifact/20fb80e9-ebef-4ab4-abf6-197005e7f587#... shu yerda artifact bor shularni yaxshilab organib chiqishin kerka boladi"
   Gloss: "There's an artifact here, you need to study it well." (Kickoff — read the existing market-research artifact first.)

2. **ebe4fb8c..., L97, 2026-10-10T07:41:35Z**
   Gloss: Core product vision — an AI-native POS/ERP startup for Uzbekistan, built because competing startups have little AI. Qaror: loyihada 1C ishlatilmaydi va tilga olinmaydi (2026-10-12, 2026-10-14).

3. **ebe4fb8c..., L141, 2026-10-10T07:44:22Z**
   > "team yaratvotganinda haiku modelni ishlatsan hamma narsaga"
   Gloss: "When creating a team, use the Haiku model for everything." → directly backs MEMORY.md's "team-agents-haiku-artifact" note.

4. **ebe4fb8c..., L150, 2026-10-10T07:44:33Z** (the `/objective` command text)
   > "Barcha agentlar uchun haiku modeli ishlatilsin. Natijalar Claude Docs hujjatiga yoziladi: https://claude.ai/code/artifact/6ae6f454-..."
   Gloss: reaffirms haiku-for-all-agents and names the Claude Docs artifact as the single output target.

5. **bb22ded9-3de2-4489-9dbc-a3b861421694.jsonl, L85, 2026-10-12T06:16:18Z** — the key product/scope directive:
   Gloss: Qaror: loyihada 1C ishlatilmaydi va tilga olinmaydi (2026-10-12, 2026-10-14). There's currently no ERP/POS service in the Uzbek market that integrates with the tax authority, so ours must have tax integration built in — this is the core differentiator; find what's missing in competitors and research it. → directly matches MEMORY.md's "no-1c-integration" note (tax integration is the differentiator) and is the origin of the "2026-10-12 yo'nalish o'zgarishi" (direction change) cited throughout `research_notes/texnik/01, 00`.

6. **bb22ded9..., L558, 2026-10-12T07:30:24Z**
   > "bu yerda artifactlarni docslarga yozib yuribsanmi yoki faqat artifictlarni ozida turiptimi"
   Gloss: "Are you writing the artifacts into Docs, or are they just staying as artifacts?"

7. **bb22ded9..., L565, 2026-10-12T07:33:42Z**
   > "artifictlarni hammasini san dockslarga yozishi kerka boladi, buni nega bunday deyap,man spefikatsiyalar yozish uchun yaxshi boladi"
   Gloss: "You must write ALL artifacts into Docs — I'm saying this because it's good for writing specifications [from]." → backs MEMORY.md "agents write straight into the shared doc".

8. **b1217379-c04c-48ef-af9c-0b8a5c40e4c5.jsonl, L68, 2026-10-12T08:43:29Z**
   > "manga uzbekchada ber"
   Gloss: "Give it to me in Uzbek." (Language directive — matches all deliverables being in Uzbek Latin.)

9. **b1217379..., L74, 2026-10-12T08:58:55Z**
   > "endi bu yerda biz spefikatsa yozsak boladimi yoki yana resaerh qilish kerka boladimi? ... balki qandaydur kamchiligi bolishi mumkin"
   Gloss: "Can we write the spec now, or is more research needed? There might be some deficiency [in research] — check again."

10. **b1217379..., L99 and L103, 2026-10-12T09:04–09:05Z**
    > "ha shu rejani boshlaver" / "... bunga ham ozing bilib teamlarga bolishin kerka boladi, bu yerda sandan tashqari yana 2ta team bor yani mahsulot va arxitektura team bor, ularga ham ish bolsa berish kerka boladi"
    Gloss: "Yes, start that plan — you decide how to split it among teams; besides you (Research) there are 2 more teams, Mahsulot and Arxitektura — give them work too if there's any." → authorizes the 3-team structure and spec-writing phase.

11. **2218f2da-5a7e-4678-8cd7-5f24adaed7ad.jsonl, L57, 2026-10-10T10:58:58Z**
    > "bu yerda jamoalarni ishga tushirsang boladi, bu yerda hali veri researchlar qilish kerak boladi"
    Gloss: "You can start the teams here; real research still needs to be done here."

12. **bb22ded9..., L382 / L413 / L452 / L483 / L731** (2026-10-12, 06:43–08:41Z): a run of process check-ins —
    "jamoaga qara nega tohtab qolgan ishga tushirishin kerka boladi" (check why the team stopped, restart it),
    "jamoaga qarachi nimalar qilyapti" (what's the team doing), "tekshirib chiq" (check it),
    "teamlar hammasini bajardimi qolib ketgan narsalar qolmadimi?" (did the teams finish everything, anything left?).
    Gloss: repeated human intervention to un-stick stalled teams — this is the concrete evidence behind
    MEMORY.md's "team-review-bottleneck" note (see §4 below for the mechanism: unreviewed work blocks dependents).

13. **ebe4fb8c..., L469, 2026-10-10T08:02:36Z** (system-generated, not human, but defines human/agent relationship):
    "Coder made this conversation my mega-lead automatically... you speak for me to its teams." Establishes
    ebe4fb8c as the relay hub for the rest of the project.

---

## 2. Project decisions and where they came from

| Decision | Source | Status on disk |
|---|---|---|
| **Qaror: loyihada 1C ishlatilmaydi va tilga olinmaydi (2026-10-12, 2026-10-14)** | Human, bb22ded9 L85 (2026-10-12); reaffirmed 2026-10-14 | Landed: `01-erp-modullar-va-malumot-modeli.md` contains only vendor-neutral ERP concepts; `00-xulosa-va-ochiq-savollar.md` main finding #1 states the no-integration rule; `spec/kod-uchun/*` never proposes any such integration. |
| **Tax-system integration is the core differentiator** (no Uzbek ERP/POS competitor currently integrates with tax systems) | Human, bb22ded9 L85 | Landed: `09-soliq-integratsiyasi.md`, `10-bozorda-soliq-integratsiyasi.md` (competitor gap table), `00-fayl` main finding #1, `spec/kod-uchun/04-biznes-jarayonlar.md` point 8 ("bozorda hech bir mahsulot ...birgalikda to'liq qoplamaydi — bu tizim uchun farqlanish nuqtasi"). |
| **All team agents run on Claude Haiku** | Human, ebe4fb8c L141, L150 | Process decision, not file content — confirmed by `.toa/brain` notes authored "Architect (architect)" etc. and the gotcha note about Haiku's research errors (§4). |
| **All research output written into a shared Claude Docs artifact** | Human, bb22ded9 L565 | Followed — artifact `e57e7cd7-...` is cited as primary source throughout `00-13` files. |
| **MVP = 14 modules** (kassa, qaytarish, chegirma, ombor qoldig'i, inventarizatsiya, ko'chirish, xarid, nasiya, narxlar, QQS, buxgalteriya, hisobotlar, huquqlar, filiallar); payroll/CRM/manufacturing deferred | Research team, `00-xulosa-va-ochiq-savollar.md` main finding #2 | Matches `spec/kod-uchun/03-modullar-talablari.md` and `05-mvp-chegarasi.md`. |
| **8 mandatory government systems**: virtual kassa/OFD, e-faktura, e-TTN, Asl belgisi (markirovka), MXIK, e-ishonchnoma (Vakolat.uz), E-IMZO, soliq hisobotlari (my.soliq.uz) | `00-fayl` main finding #3 | `spec/kod-uchun/04-biznes-jarayonlar.md` builds a matrix explicitly noting 6 of the 8 are "required" in the strict sense and 2 (e-ishonchnoma, soliq hisobotlari) are added as extra columns — see §7 for the "6 vs 8" nuance. |
| **Architecture**: multi-tenant single DB + `tenant_id` + Postgres RLS; offline-first append-only event log (no CRDT); Android-native (Kotlin) POS, PWA back-office; Postgres via UzCloud DBaaS; hosting on UzCloud/Uztelecom is a *business* choice, not a legal mandate (only biometric/genetic/telecom data must stay local) | `00-fayl` §2 table, from `research_notes/texnik/04, 07` | No contradiction found in spec files; Arxitektura team (who owns `spec/kod-uchun/`) never started, so this is still only in research notes, not yet a ratified architecture spec. |
| **Pricing**: original tiers 149k/349k/699k so'm/month (from the Oct 10 market-research doc, `.toa/brain/notes/ai-erp-market-research-doc.md`) | Mega-lead brain note, Oct 10 | **Not carried forward as fixed tiers** — `spec/kod-uchun/05-mvp-chegarasi.md` line 99 instead gives a "loose anchor" range of 69,000–999,000 so'm/month derived from competitor pricing (REGOS Start–BILLZ Pro) and explicitly marks ARPU as **"Taxmin"** (assumption), not a decided price. This is a drift from the original directive worth flagging (see §7). |
| **New central value proposition (2026 tax-law change)**: from 2026-01-01 the tax committee itself drafts VAT/other declarations from receipts/e-invoices, giving the business 5 working days to review/object; product's core value becomes *reconciling the government's report against internal books*, not declaration-writing | Research team, `.toa/brain/notes/soliq-2026-dan-hisobotlarni-davlat-o-zi-tuzadi.md`; `00-fayl` main finding #5 | Landed in `spec/kod-uchun/01, 02, 03, 06` (all reference the 5-day reconciliation flow); law/decree number for the 5-day rule was **never found** (flagged open in `03-modullar-talablari.md` point 8 and `00-fayl` open question #... — still open, see §5). |

---

## 3. Facts found WRONG and corrected (verified against current files with grep/diff)

All of these are visible in the **uncommitted working-tree diff** (`git diff` vs commit `6dc83ce`) — i.e. they are
corrections that **landed** in the current files. Source of the correction work: Research team's internal review
pass on 2026-10-12 (tasks "Tekshiruv: fiskal/soliq fayllari", "Tekshiruv: integratsiya va arxitektura fayllari",
"Tekshiruv: modullar, AI va raqobatchilar fayllari" — per `.toa/brain/teams/research-6b7ac5.md`), driven by Fiskal
and Integrator agents.

1. **Qaror: loyihada 1C ishlatilmaydi va tilga olinmaydi (2026-10-12, 2026-10-14).**
   The old technical reference file was rewritten as a vendor-neutral ERP data-model note
   (`01-erp-modullar-va-malumot-modeli.md`); no migration/integration path to any third-party accounting
   product is part of the plan. **Landed: yes.**

2. **Virtual-kassa registration timeline — "15 kun" (15 days) was a secondary-source number, wrong/unverifiable.**
   File: `02-kassa-ofd-markirovka.md` point 2. Corrected to: the *device*-registration step (via TXKM) takes
   "4 ish soati" + "8 ish soati" (~12 working hours total) per the primary source (VM qarori 943, 1-ilova,
   16–18-bandlar) — but the *software-certification* timeline for a vendor (not an end-user device) was **never
   found in the primary law text** and is left as an explicit open question. **Landed: yes**, plus the exact
   price is flagged as still unfound ("bu bozor hujjatidagi eng muhim ochiq savol hamon ochiq qolmoqda").

3. **"48-hour offline rule" — was marked "unconfirmed", is now confirmed from the primary source.**
   Files: `02-kassa-ofd-markirovka.md` point 3, `09-soliq-integratsiyasi.md` (Fiskal modul row). Correction:
   confirmed via VM qarori №943, 1-ilova, 31-band (lex.uz/docs/4603329). **Landed: yes** in both files, and
   re-confirmed in `00-xulosa-va-ochiq-savollar.md` main finding #4.

4. **Asl belgisi (markirovka) rollout dates — vague "2021-yildan"/"2022-yildan" replaced with exact decree numbers.**
   File: `02-kassa-ofd-markirovka.md` point 4 and the rollout table. Old: generic years, no decree citations.
   New: VM qarori №737 (2020-11-20, general system), №833 (2020-12-31, phased rollout), №322 (2021-05-20, pilot
   expansion), №665 (2021-11-02, tobacco/alcohol), №148 (2022-04-02, appliances), №149 (2022-04-02, pharma), with
   lex.uz links for each. Water/beverages (2024-03-01) kept with a caveat that its decree number (631) is still
   second-hand. "O'simlik yog'i 2026-10-24" row explicitly marked **unconfirmed** ("bu sessiyada hech qanday
   manbada qayta topilmadi"). **Landed: yes**, including matching additions to `09-soliq-integratsiyasi.md`.

5. **QR payment — "ixtiyoriy/majburiy" (optional/mandatory) was self-contradictory across files.**
   Files: `02-kassa-ofd-markirovka.md` row (now "Yagona QR-kod orqali to'lov qabul qilish"), `03-efaktura-va-tolov.md`
   §2, `09-soliq-integratsiyasi.md`. Correction: phased mandate — starts 2026-01-01, **fully mandatory
   2026-07-01**, legal basis = Presidential Decree (2025-12-10) + CBU Qarori №3817 (2026-04-15, technical rules
   only, does not itself impose the mandate). This exact confusion ("Markaziy bank qoidalarini QR majburiyligi
   manbasi deb ko'rsatdi, aslida Prezident farmoni") is explicitly named as a Haiku research-agent error in brain
   note `tuzoq-haiku-tadqiqot-agentlari-manbalarni-noto-g-ri-talqin-qiladi.md`. **Landed: yes**, in all three files.

6. **E-IMZO legal basis — previously "not independently confirmed".**
   File: `03-efaktura-va-tolov.md` §1.5, `09-soliq-integratsiyasi.md`. Correction: O'RQ-793-son Qonun
   "Elektron raqamli imzo to'g'risida" (2022-10-12), in force 2023-01-14 (lex.uz/docs/-6234904). **Landed: yes.**

7. **Inventory valuation method — "FIFO/LIFO" was wrong; LIFO is not in the Uzbek standard at all.**
   File: `08-mahsulot-modullari.md` (Ombor qoldig'i row). Correction: NSBU 4-sonli standard (lex.uz/docs/-4890446)
   recognizes only 3 methods — identified cost, weighted-average (AVECO), FIFO. "Avvalgi 'FIFO/LIFO' yozuvi
   noto'g'ri edi" (the previous FIFO/LIFO note was wrong), stated explicitly in the diff. **Landed: yes.**

8. **VAT rate citation — was sourced only from secondary blogs (kovchegpremium.com, uz24.uz), not lex.uz directly.**
   File: `08-mahsulot-modullari.md` (QQS row): rate corrected/clarified to 12% standard (down from 15% as of
   2026), 0% for some categories, optional 6% from 2026-06-01, citing Tax Code art. 258 — **but the primary-source
   text of article 258 was still never independently read**. This remains an open/contested item — see §5 item 1.
   **Partially landed**: the row text improved, but the underlying sourcing gap persists and is explicitly
   flagged by the Research team's own fact-check (`13-spec-faktlar-tekshiruvi.md`, finding #1).

9. **Source-system object-name transliteration/spelling errors fixed, then the whole reference generalized.**
   File: `08-mahsulot-modullari.md` Manbalar section: early typo fixes to object names were later superseded
   when the section was rewritten to use generic, vendor-neutral ERP terminology instead. **Landed: yes.**

10. **Competitor-complaints table (`11-raqobatchilar-kamchiliklari.md`) contained an irrelevant/miscategorized row.**
    Original table included a complaint about **ЮKassa** (Yandex's *payment* system, Russia) as if it were an
    Uzbek ERP/POS competitor weakness — removed with an explicit note: "bu O'zbekiston ERP/POS raqobatchisi EMAS
    ... fayl mavzusiga aloqasiz edi, shuning uchun olib tashlandi" (not an Uzbekistan competitor, unrelated to
    the file's topic, so removed). Also: all MoySklad/Poster complaints were re-labeled as **"RF bozori sharhi"**
    (Russia-market reviews) with an explicit caveat that they may not apply to Uzbekistan, and the "markirovka
    tizimi xatolari" framing was corrected from "biz skanerlashni olib tashlaymiz" style claims to "scanning
    hardware is legally required by Asl belgisi, our opportunity is software-level error prevention, not
    removing the scanner." **Landed: yes.**

11. **Scanning-error statistic (80–90%) — risk of being misread as a per-scan POS failure rate.**
    Originates in `00-xulosa-va-ochiq-savollar.md` main finding #6 (supply-chain/batch level, from gazeta.uz
    2026-04-14). The Mahsulot team's reviewer flagged (proposed gotcha, see §4 below) that spec drafts could
    misstate this as a POS-level scan-failure rate. **Landed: yes** — current `spec/kod-uchun/01-rollar...md`
    line 138, `06-ekranlar-umumiy.md` line 454, and `05-mvp-chegarasi.md` line 91 all correctly qualify it as
    supply-chain/batch-level and explicitly say the POS-level rate is a separate, unmeasured quantity.

12. **Risk-assessment decree for e-invoices — was called "PQ-830"; correct form is "VM Qarori №830-son".**
    Flagged by Mahsulot team reviewer (proposed gotcha note, §4). **Landed: yes** — `spec/kod-uchun/02, 03`
    both consistently use "VM Qarori №830-son" now.

13. **E-ishonchnoma (Vakolat.uz) dropped from "6 mandatory systems" lists.**
    Flagged by Mahsulot team reviewer. **Landed: yes** — `04-biznes-jarayonlar.md` explicitly explains the
    6-vs-8 discrepancy (the matrix's "6 required systems" are the process-matrix minimum; e-ishonchnoma and
    soliq-hisobotlari are 2 more of the 8 overall, added as extra columns for representative/reconciliation cases).

**Not corrected / stale as of end of history:**
- `research_notes/texnik/10-bozorda-soliq-integratsiyasi.md` has had **zero commits/diffs** since the initial
  commit (verified via `git log --follow`), even though the Research-team fleet mail (ebe4fb8c L495, 2026-10-12)
  explicitly named it alongside 09 as having errors ("09 va 10 da xatolar bor"). File 10 does contain its own
  internal "Xatolar (tuzatilgan)" self-correction section from when it was first written, so the errors the
  fleet mail meant may already have been pre-corrected before the commit — but no later verification pass
  touched this file, unlike 09.

---

## 4. Reviewer rejections / disputes

1. **Mahsulot-team reviewer (Tekshiruvchi) — proposed gotcha note, status still "proposed" (never promoted to
   accepted) as of end of history**: `.toa/brain/proposals/tuzoq-spec-yozishda-takrorlangan-manba-xatolari.md`
   (2026-10-12T08:57:25Z, author "Tekshiruvchi (reviewer)", team Mahsulot). Flags 5 recurring errors found while
   reviewing specs 01/03/04/05:
   1. 80–90% scanning-error stat risked being read as per-scan POS rate, not supply-chain/batch rate.
   2. Government-report reconciliation: a report is auto-accepted if unanswered within 5 working days; the
      decree number for this rule was never found in lex.uz; no MVP data exists yet for personal-income/social/
      property/land tax reports (payroll/fixed-assets are out of MVP scope); it's unconfirmed whether the
      government's reconciliation data arrives at document level (which receipt/invoice); the objection channel
      is not described in any source.
   3. Incoming invoices are never paper — Tax Code requires e-invoices only; OCR should only apply to paper
      waybills/receipts, not to incoming invoices.
   4. The e-invoice risk-assessment decree is "VM Qarori №830", not "PQ-830".
   5. E-ishonchnoma (Vakolat.uz), mandatory from 2026-01-01, kept falling out of "6 mandatory systems" lists even
      though the README counts 8.
   **Verification against current files**: all 5 items are in fact addressed in the current `spec/kod-uchun/*`
   content (see §3 items 11–13 above, plus OCR scope confirmed limited to receipts/waybills in `04/05-fayl`
   cross-references). So although the proposal note itself was never formally "accepted" in the brain (status
   stays "proposed" — nobody promoted it), **the underlying corrections were made** in the spec files. This is a
   process gap worth flagging: the brain's bookkeeping (proposal status) lags the actual work.

2. **Research-team Architect — self-identified review bottleneck.** `bb22ded9-3de2-4489-9dbc-a3b861421694.jsonl`,
   assistant turn at L480 (2026-10-12, ~07:27Z): "To'g'ri aytdingiz, jamoa yana men tufayli kutib qolgan ekan.
   Integrator 04 (arxitektura) ni soat 12:00 da topshirgan, u esa mening tekshiruvimni kutib turgan. Fiskal ham
   00 ni boshlay olmagan, chunki 00 aynan 04 ga bog'liq." (You were right, the team was stuck again because of
   me. Integrator submitted file 04 at 12:00 and was waiting on my review; Fiskal couldn't start file 00 because
   it depends on 04.) This was triggered directly by human nudges at L382/413/452/483 ("jamoaga qara nega
   tohtab qolgan", "tekshirib chiq"). The Architect commits to reviewing immediately going forward ("Bundan keyin
   hisobotlar kelishi bilan darhol tekshiraman, jamoa menga qarab kutib qolmaydi"). **This is the direct source
   of MEMORY.md's "team-review-bottleneck" lesson** ("tasks without a reviewer stall in review; settle reviews
   immediately").

3. No outright **rejected/"request changes" verdict** with a blocked task surfaced in the extracted data —
   the disputes found were review-queue delays (process) and fact corrections (content), not formal
   reviewer-vs-worker disagreements that went through multiple rounds.

---

## 5. Facts still unverified or contested at the end of the history

From `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` §"Ochiq savollar" and `13-spec-faktlar-tekshiruvi.md`
(the Research team's own fact-check of the Mahsulot team's spec, dated 2026-10-12, the last research activity
in the history):

1. **VAT standard rate 12% (Tax Code art. 258)** — never independently read from lex.uz; the whole chain
   (`01-fayl` → `08-fayl` → `spec/03-modullar-talablari.md` US-M10-01 → `spec/06-ekranlar-umumiy.md` BO-07) all
   cite the same two secondary sources (kovchegpremium.com, uz24.uz). Flagged as the **highest-impact** open
   item because it underlies all VAT computation logic (M09, M10, BP-02…08).
2. **"5 ish kuni" (5 working days) government-report-reconciliation rule** — law/decree number never found
   (only uz.kursiv.media, a secondary news source); if the real period differs (e.g. 3 or 10 days), the
   central architecture flow (the 5-day counter) would need a full rework.
3. **Virtual-kassa registry registration price and timeline for a standalone software vendor** — still
   completely unknown; explicitly called "the most important open question in the whole market document, still
   open."
4. **CRPT Turon (Asl belgisi) integrator registration terms and API** — help.crpt-turon.uz's technical sections
   return 403; no registration terms found.
5. **ЗРУ/O'RQ-764 (cybersecurity law) mandatory certification applicability** to an ordinary private SaaS ERP
   (vs. state bodies / critical info infrastructure only) — unresolved; if "yes," has the single largest
   potential schedule/budget impact of all open items.
6. **Programmatic read access to my.soliq.uz government-generated tax reports** — no official API found; MVP
   assumption is manual upload/entry (this is a *working assumption with fallback*, documented in the new file
   `12-taxminlar-va-murojaatlar.md`, not a resolved fact).
7. **Fiscal-receipt issuer in QR/card payment flows (merchant vs. payment-system)** — legal ambiguity, both
   interpretations documented, left unresolved by design (`03-efaktura-va-tolov.md` §2.5, `spec/03-biznes-
   jarayonlar.md` BP-05).
8. **Policy for selling marked (Asl belgisi) goods while offline** — no ruling found; working assumption +
   fallback drafted in `12-taxminlar-va-murojaatlar.md` item 6, needs internal/legal sign-off before the
   offline-first architecture is finalized.
9. **Competitor customer-count disputes** (BILLZ 4,000+ vs 1,700+; OX System 350+ vs 2,000+; Bito ERP now
   claims a *third*, "1000+", number) — explicitly "cannot be independently verified," needs direct merchant
   interviews, left open.
10. **Didox "250,000 companies" claim** — never re-verified, carried as an unverified fragment since the
    original market research.
11. **Local POS competitor complaints (BILLZ, REGOS, Smartup, UZKASSA, mDokon)** — no genuine customer
    complaints found in any open source (Google Play, forums, infostart.ru all returned nothing /429 errors);
    recommendation to interview 10–15 shop owners directly remains undone.
12. **`spec/kod-uchun/` was never written** — the Research team's fact-check in `13-fayl` could only cover
    `spec/kod-uchun/`, explicitly noting Arxitektura's output needs its own separate fact-check once it exists.
    As of the end of the history it still does not exist.

---

## 6. Claude Docs artifact URLs and what each holds

| URL | What it holds |
|---|---|
| `https://claude.ai/code/artifact/6ae6f454-7251-499a-bf21-06a2ce40db5b` | Original market-research document (Oct 10): "no local all-in-one POS+inventory+credit+accounting product with built-in AI; start with Tashkent grocery stores and small wholesalers; proposed tiers 149k/349k/699k so'm/month." Named by the human in the `/objective` command as the base research; later superseded in practice by the artifact below for *technical* findings. Per `.toa/brain/notes/ai-erp-market-research-doc.md`. |
| `https://claude.ai/code/artifact/e57e7cd7-1117-40a7-8af5-8154a8d22540` | The "asosiy, tekshirilgan versiya" (main, fact-checked doc) the Research team actually wrote technical findings into: modules, the 8 mandatory tax systems, competitors' tax-integration gaps, product shortcomings, and a list of questions for the user. Cited as the primary external reference throughout `research_notes/texnik/00, 01, 09, 12, 13`. Per `.toa/brain/notes/texnik-tadqiqot-qayerda-nima-bor.md`. |
| `https://claude.ai/code/artifact/20fb80e9-ebef-4ab4-abf6-197005e7f587` | The artifact the human pasted at the very start of the project (ebe4fb8c L10, "study this well") — content not independently distinguishable from the two above in the transcripts; likely an early/precursor version of the market-research doc. |
| `https://claude.ai/artifact/Rp9naXUCj2xozpUkyQy19W` | Not a content doc — this is the **Artifact *type*/template** ("Claude Docs document") used by Coder/Claude to instantiate the two docs above; its own id is irrelevant to content. |
| `https://claude.ai/artifact/VLf6CQ4ixdbaHkw3aLCdd1`, `https://claude.ai/artifact/ECeGqhywp9N9o9rN1yBv1Q` | Each opened exactly once ("Opened the Artifact ... for the user. Nothing was published or changed") — no distinguishing content captured; most likely re-opens of one of the docs above by id alias. |

---

## 7. Contradictions between the chat history and current files on disk

1. **Pricing tiers drifted.** Oct 10 directive/brain-note fixed tiers at 149k/349k/699k so'm/month. The current
   `spec/kod-uchun/05-mvp-chegarasi.md` (line 99) does **not** use these numbers — it gives a much wider,
   explicitly-labeled "Taxmin" (assumption) range of 69,000–999,000 so'm/month anchored to *competitor* pricing
   (REGOS Start–BILLZ Pro), not the original research doc's tiers. No transcript shows an explicit decision to
   abandon the original tiers; it appears to have been silently superseded during the Mahsulot team's spec work.
2. **"6 majburiy tizim" vs "8 majburiy tizim" terminology is inconsistent across spec files** (`02-modullar-
   talablari.md` and `04-biznes-jarayonlar.md` both explain the discrepancy inline, but a reader skimming only
   `02-fayl`'s "Davlat tizimlari bog'liqligi" section would see "6" without the explanation visible in `03-fayl`).
   Already flagged by the Mahsulot reviewer (§3 item 13) and reconciled, but the terminology split (6 "process-
   matrix-required" vs 8 "overall mandatory") is not uniformly labeled across every file that uses either number.
3. **Brain note `texnik-tadqiqot-qayerda-nima-bor.md` (created 2026-10-12T07:28:20Z) says files 08–11 are "old
   drafts... still have errors, rely on the [Claude Docs] document instead."** This is now stale: the current
   working tree shows 08, 09, and 11 were in fact corrected later the same day (per `git diff`, all after the
   note's timestamp — the note predates the Fiskal/Integrator review-and-fix tasks listed in
   `.toa/brain/teams/research-6b7ac5.md`). The brain note itself was never updated to reflect this, so a future
   reader trusting the brain index verbatim would wrongly discount now-corrected files.
4. **Team roster drift**: `.toa/brain/teams/research-6b7ac5.md` crew list is Architect, Fiskal, Integrator,
   Tekshiruvchi — **it does not list "Modelchi,"** even though a dedicated session (573973f6, team-bridge
   `30567d1d`) ran as "Modelchi, a worker" on the same team (teamId `6b7ac535-...`, confirmed via fleet mail at
   ebe4fb8c L526 naming Modelchi's retries). The brain's roster reflects a later/final snapshot after Modelchi's
   role ended or was dropped; historical transcripts still show Modelchi as an active team member.
5. **`spec/kod-uchun/` referenced as existing/non-empty in places it should not be**: `13-spec-faktlar-
   tekshiruvi.md` point 1 correctly notes it was empty at check time; this is consistent with disk state (folder
   does not exist). No contradiction here, just confirming the Arxitektura team's output never materialized by
   the end of the captured history.

---

## Files referenced in this digest
- Transcripts: `C:\Users\YuDix\.claude\projects\E--Project-erp\ebe4fb8c-73e8-4e66-b664-9b318df0e1ab.jsonl`,
  `bb22ded9-3de2-4489-9dbc-a3b861421694.jsonl`, `b1217379-c04c-48ef-af9c-0b8a5c40e4c5.jsonl`,
  `2218f2da-5a7e-4678-8cd7-5f24adaed7ad.jsonl`, and the other 14 team-session files (roles mapped in §intro).
- Project brain: `E:\Project\erp\.toa\brain\{index.md,direction.md,log.md}`,
  `.toa\brain\notes\*.md` (4 files), `.toa\brain\proposals\tuzoq-spec-yozishda-takrorlangan-manba-xatolari.md`,
  `.toa\brain\teams\{research-6b7ac5,mahsulot-e0d2ae,arxitektura-975bf7}.md`.
- Research notes: `E:\Project\erp\research_notes\texnik\00` through `13` (`.md`).
- Spec: `E:\Project\erp\spec\01-mahsulot\01` through `06` (`.md`).
- Verification method: `git diff` against commit `6dc83ce` (research_notes changes) + `git log --follow` (file
  10 untouched) + `Grep` over current spec files for reviewer-flagged terms.
