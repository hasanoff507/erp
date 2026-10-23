# A — Havolalar va sonlar (mustaqil tekshiruv)

**Maqsad:** `spec/kod-uchun/` (35 fayl, commit 00dd8aa) dagi o'zaro havolalar, ID'lar, e'lon qilingan sonlar, sarlavha bloklari, "Ochiq savollar" bo'limlari va tarix qoldiqlarini mexanik tekshirish. · **Kim uchun:** spec tuzatuvchi agentlar, asoschi. · **Holat:** faqat o'qish, spec fayllari o'zgartirilmagan, 2026-10-16.

Skriptlar: `research_notes/mustaqil-tekshiruv/_scripts/refs.py` (fayl, § bo'lim, qaror, 26, US/BP/ekran/QT havolalari), `26rows.json`, `codes17.txt`. Natijalar qo'lda tekshirildi: qonun bandlari (`S1 §410`, `NSBU №21 §237`) va tashqi tadqiqot fayllariga `§` havolalar xato hisoblanmadi.

## Yig'ma

| Daraja | Soni |
|---|---|
| kritik | 0 |
| o'rta | 8 |
| kichik | 23 |
| **Jami** | **31** |

### Tasdiqlangan (mos) sonlar

| Da'vo | Qayerda | Haqiqiy | Natija |
|---|---|---|---|
| 104 US (86 M01–M18 + 18 M19; M01 — 7) | 00, 03, 30 | 104 (86 + 18; M01 = 7) | mos |
| BP-01…15 | 00, 04 | 15 | mos |
| 41 ekran / 39 MVP | 00, 06, 07, 30 | 07 da 41 (16 + 24 + 1); 06 va 30 da ham 41 | mos |
| Qarorlar #1–#65 | 00, 01 | 65 qator, 1…65 uzluksiz | mos |
| 256 QT = 45 + 182 (M19 = 24) + 14 + 15; Bosqich 7 da 26 ta | 31 §0, §0.7 | 256; modullar bo'yicha har bir son §0.7 bilan mos; ID'lar takrorlanmagan | mos |
| Xato kodlari katalogi 191 / `ONEC_*` 81 | 17 §15, 21, 33 | 191 / 81; 17 dagi 81 ta = 33 §12 dagi 81 ta | mos |
| Ruxsatlar 67, `onec.*` 7 ta | 30 | 15 §2.1 da 67 / 7 | mos |
| 20: 100+ endpoint, guruh sonlari (12/10/7/8/11/8/11/4/7/11/6/8) | 20:10 | indeksda 103 qator, har guruh mos | mos |
| 19: ~110 endpoint | 30:331 | 110 ta noyob metod+yo'l | mos |
| W-01…W-55, A-01…A-10, P-01…P-22 | 33 | barchasi aniqlangan, diapazondan tashqarisi yo'q | mos |
| 26: A — 129, B — 40; OQ-001…102: 75 / 27; 1C 1 / 11 | 26 Yig'ma | 129 / 40 (#44 bo'sh — 26:268 da izohlangan); indeks 75 / 27; 1 / 11 | mos |
| 12: 1C jadvallari 19 (18 `app` + 1 `auth`) | 12:2486 | 19 ta `CREATE TABLE … onec_*` | mos |
| US, BP, ekran, QT, qaror, 26 # havolalarining hammasi mavjud ID'ga ishora qiladi | barcha fayllar | singan ID topilmadi | mos |
| `26 #N (OQ-0xx)` juftliklari 26 dagi OQ ustuni bilan | barcha fayllar | nomuvofiqlik yo'q | mos |
| "Ochiq savollar" bo'limlari faqat Jadval B bandlarini keltiradi | 02–34 | hamma bandda 26 raqami bor va B da; A ga havola yo'q | mos |
| Sarlavha bloki Maqsad/Kim uchun/Bog'liq fayllar/Holat | 01–34 | hammasida bor (faqat 00 da yo'q — A-024) | mos |
| `AIOS`, `universal_ai`, `TODO`, `TBD`, `???`, `~~`, `(2026-10-1x:` | barcha fayllar | topilmadi | mos |

## Topilmalar

| ID | Fayl:qator | Muammo | Aniq tuzatish | Daraja |
|---|---|---|---|---|
| A-001 | `01-qarorlar.md`:24, 38, 40, 41, 55, 56, 74, 75, 76, 90, 91, 100, 101 | "Qayerda qo'llanilgan" ustunida eski `OSn` ko'rsatkichlari ("`17` OS2", "`29` OS1", "`10` OS3", "`27` OS4", "`15` OS5/OS6/OS8", "`20` OS2/OS3/OS4/OS6", "`03` OS3", "`13` OS6", "`19` OS3/OS4/OS5/OS6", "`23` OS7", "`32` OS3–5", "`08` OS2", "`06` OS2", "`11` OS4"…). 26 tasi mavjud bo'lmagan bandni ko'rsatadi: 10, 17, 27, 29 da "Ochiq savollar" bandlari yo'q, boshqalarida raqamlar boshqacha (masalan, 20 da faqat 1-band, 15 da 1–4). Qolgan `OSn`lar tasodifan mos keladi, lekin ma'nosi boshqa: `16` OS2 = 26 #89 (FM holat kodlari), u esa 01 #56 mavzusi emas. Sabab: README 4-qoidasi bo'yicha yopilgan savollar bo'limlardan olib tashlangan, ko'rsatkichlar esa qolib ketgan. | 01 dagi barcha `OSn` (15 qator) ni olib tashlash. Kerak joyda shu mavzu yozilgan bo'lim raqami bilan almashtirish: `` `17` OS2 `` → `` `17` §15.1 ``, `` `10` OS3 `` → `` `10` §1 ``. Mavzu bo'lim emas, 26 da yopilgan bo'lsa → `` `26` #N `` | o'rta |
| A-002 | `26-ochiq-savollar-reestri.md`:103 (#84) | `` `08` §13 /OS6 `` — 08 da OS6 yo'q (bandlar 7, 8). 26:103 dagi `` `18`/OS3 `` ham eski raqamlash. | `` `08` §13 `` qoldiriladi, `/OS6` va `/OS3` olib tashlanadi | kichik |
| A-003 | `26-ochiq-savollar-reestri.md`:104; `27-backlog.md`:178 | `` `18` §15a `` / `` `18-api-kassa.md` §15a `` — 18 da §15a yo'q. Chiquvchi e-faktura — `## 14a.` (18:747); §15 — markirovka. | `§15a` → `§14a` (ikkala joyda) | o'rta |
| A-004 | `01-qarorlar.md`:24 (#56); `26-ochiq-savollar-reestri.md`:153 (#56 qatori) | `` `14` §1.4 `` "Telegram ulash" — 14 da §1.4 yo'q. "Telegram ulash" — `15-xavfsizlik-va-audit.md` §1.4. | `` `14` §1.4 `` → `` `15` §1.4 `` | kichik |
| A-005 | `19-api-ombor.md`:266 | `` `17-api-umumiy.md` §attachments `` — bunday bo'lim yo'q; `attachments` — 17 §12 "Fayl yuklash". | `§attachments` → `§12` | kichik |
| A-006 | `23-backend-arxitekturasi.md`:226 | "(13-0 §8)" — mavjud bo'lmagan fayl nomi. Mazmuni (`version`, `draft` PATCH) — 17 §8 "Optimistik qulflash". | "(13-0 §8)" → "(`17-api-umumiy.md` §8)" | kichik |
| A-007 | `29-atamalar-lugati.md`:14 | `` `10-umumiy-arxitektura.md` §Qoidalar, 2-band `` — 10 da "Qoidalar" bo'limi yo'q; "Spec o'zgarsa…" 2-qoidasi `00-README.md` da. | → `` `00-README.md` §Qoidalar, 2-band `` | kichik |
| A-008 | `07-ekran-tafsilotlari.md`:957 | "06 §1.3 Won't" — 06 §1.3 "Offline indikatori". Won't ro'yxati — 05 §1.3. | "06 §1.3 Won't" → "05 §1.3 Won't" | kichik |
| A-009 | `12-db-sxema.md`:22, 52, 1893, 3867 | DDL izohlarida fayllarning eski raqamlari qolgan: "05-xavfsizlik §3.2/§3.3/§2.3" (05 — MVP chegarasi), "12-auth §19" (12 — shu faylning o'zi), "04-offline-sync §5" (04 — biznes jarayonlar). Migratsiya yozuvchi noto'g'ri faylga boradi. | "05-xavfsizlik §3.2" → "15 §3.2"; "05-xavfsizlik §3.3" → "15 §3.3"; "05-xavfsizlik §2.3" → "15 §2.3"; "12-auth §19" → "14 §19"; "04-offline-sync §5" → "16 §5" | o'rta |
| A-010 | `12-db-sxema.md`:4016 | `` `15-xavfsizlik-va-audit.md` §3.3/§19 `` — 15 da §19 yo'q. Auth jadvallari — 14 §19. | → `` `15-xavfsizlik-va-audit.md` §3.3, `14-autentifikatsiya-oauth2.md` §19 `` | kichik |
| A-011 | `11-malumotlar-modeli.md`:173; `12-db-sxema.md`:3530, 3610, 3611; `15-xavfsizlik-va-audit.md`:408; `20-api-moliya-admin.md`:1301; `23-backend-arxitekturasi.md`:233; 14 ichida: 362, 364, 368, 416, 420, 440, 471 | "§16.1.1", "§16.1.2", "§16.1.3", "§16.1.5" — 14 da bunday sarlavhalar yo'q. 16.1 — 1–5 raqamli ro'yxat, yagona kichik sarlavha esa `16.1.1a`. Havola ro'yxat bandini bo'lim sifatida ko'rsatadi. | "§16.1.N" → "§16.1 N-band" (masalan, "§16.1 3-band"). Yoki 14 §16.1 bandlarini `#### 16.1.1 …16.1.5` sarlavhalariga aylantirish (bitta tuzatish, havolalar o'zgarmaydi) | kichik |
| A-012 | `01-qarorlar.md`:87; `32-kod-qoidalari.md`:206, 225, 473 | `` `08-dizayn-tizimi.md` §0.1 `` — 08 da §0.1 sarlavhasi yo'q; "## 0." ichidagi 1-band (pul qoidasi). | → `` `08-dizayn-tizimi.md` §0 (1-band) `` | kichik |
| A-013 | `26-ochiq-savollar-reestri.md`:53, 68, 128 | `` `05` §4.3 / §4.2 / §4.4 `` — 05 §4 da kichik bo'limlar yo'q (raqamli ro'yxat). #41 (my.soliq.uz) uchun "§4.2" ma'nosi ham xato: bu 4-band (2-band — Asl belgisi). #125 (ZRU-764) uchun "§4.4" ham xato: ZRU-764 ro'yxatdan keyingi xatboshida. | 53: → `` `05` §4 (3-band) ``; 68: → `` `05` §4 (4-band) ``; 128: → `` `05` §4 (oxirgi xatboshi) `` | kichik |
| A-014 | `01-qarorlar.md`:91; `26-ochiq-savollar-reestri.md`:141 | `` `12` §7.12 `` — 12 da §7.12 sarlavhasi yo'q (§7 ning 12-bandi, `doc_sequences.doc_type`). | → `` `12` §7 (12-band) `` | kichik |
| A-015 | `20-api-moliya-admin.md`:1375, 1382; `15-xavfsizlik-va-audit.md`:373 | Fayl prefiksisiz "§16.5" (20 da) va "§16.5", "§18.1" (15 da). Bu bo'limlar ikkala faylda ham yo'q, ular 14 da. | → "`14` §16.5", "`14` §18.1" | kichik |
| A-016 | `12-db-sxema.md` §2.11 DDL izohlari: 2696, 2697, 2719, 2820, 2821, 2827, 2834, 2869, 2872, 2873, 2875, 2934, 2936, 2942, 2943, 2955, 2957, 2958, 3012, 3022, 3028, 3053, 3062, 3075, 3112 | Prefiksisiz "FK §5.21", "§9.5", "§7.3", "§8.1"… — bu bo'limlar 12 da yo'q, 33 da bor. 12 o'quvchisi uchun noaniq. | Har izohda "§" → "33 §" (masalan, "FK 33 §5.21") | kichik |
| A-017 | `27-backlog.md`:235; `33-1c-integratsiya.md`:3930 | "Qabul testlari (`31-qabul-testlari.md` M19): §14 qabul mezonlari" — 31 da §14 yo'q; ma'nosi 33 §14 (hikoyalar va qabul mezonlari). | → "Qabul testlari (`31` M19; `33` §14 qabul mezonlari)" | kichik |
| A-018 | `01-qarorlar.md`:77 (#60); `10-umumiy-arxitektura.md`:89; `34-1c-agent.md`:1586 | Mavjud bo'lmagan `34-dokon-agenti.md` ga havola ("…ga kengaytiriladi"). Bu kelajak rejasi, joriy haqiqat emas (README 4-qoida). Kod yozuvchi yo'q faylni qidiradi. | 3 joyda ham "`34-dokon-agenti.md` ga kengaytiriladi" iborasini olib tashlash; "fiskal ko'prik va qurilmalar — `34-1c-agent.md` «Kengaytirish» bo'limi" deb yozish | o'rta |
| A-019 | `26-ochiq-savollar-reestri.md`:202 (#133) | Interim standartda 33 yoki 17 da yo'q nomlar ishlatilgan: `fill_accounts_mode='flag_then_verify'`, xato kodi `ONEC_ACCOUNTS_UNRESOLVED` (81 ta `ONEC_*` katalogida yo'q), `vat_round='per_line_2dp'`. 33 §16.2 (33:3895) dagi o'sha #133: `fill_accounts=true`, `orp_returns_section`; yaxlitlash — `vat_rounding_mode` (33:2074). 1C nomlari bo'yicha 33 yagona manba. | 26:202 dagi interimni 33:3895 bilan tenglashtirish: "`fill_accounts=true`; qaytarish — `orp_returns_section`; QQS yaxlitlash — profil `vat_rounding_mode` (33 §8); to'ldirilmagan schyot → `ONEC_FILL_CHECK_FAILED`; Bosqich A gacha kod yozilmaydi" | o'rta |
| A-020 | `26-ochiq-savollar-reestri.md`:8 | "Yangi bandlar oxirgi raqamdan keyin qo'shiladi (#106 dan)" — jadvallarda #170 gacha raqam bor. Yangi band #106 olsa, mavjud #106 bilan to'qnashadi. | "(#106 dan)" → "(#171 dan)" | o'rta |
| A-021 | `23-backend-arxitekturasi.md`:15, 324, 389 | "README qarori" (AI port `fake`/`cli`/`api`, Claude API) — 01 da bunday qaror yo'q. Manba `spec/README.md`, u `kod-uchun` dan tashqarida, 00 esa "kod faqat shu hujjatlarga tayanadi" deydi. Prod'dagi `ValueError` matni ham shunga tayanadi. | "README qarori" → "qaror #16; `22-ai-qatlami.md` §1". Agar `fake/cli/api` rejimlari qaror bo'lishi kerak bo'lsa — 01 ga yangi qator (#66) qo'shish | o'rta |
| A-022 | `31-qabul-testlari.md`:187 (va §0.3) | "Har qator — bitta Must US uchun kamida bitta ssenariy" deyiladi, lekin MVP'dan keyingilarga kirmaydigan **US-M01-07** (printer/tarozi, qaror #60), **US-M17-03** (to'lov muddati / `restricted`) va **US-M19-04** (moslashtirish) uchun bironta QT yo'q (31 da umuman tilga olinmagan). 27, 30, 05 da uchalasi bor. | Uchala US uchun QT qatorlari qo'shish (masalan, QT-M01-22, QT-M17-09, QT-M19-25) va 31:67, §0.7 dagi sonlarni (182 → 185, 256 → 259, M19 24 → 25, Bosqich 7 26 → 27) yangilash. Yoki §0.3 da istisno sifatida asoslab yozish | o'rta |
| A-023 | `31-qabul-testlari.md`:501–504 | `QT-AI-GUARD-01` yo'q (02, 04, 03 tartibida). Raqamlash uzluksiz emas, tartib buzilgan. | 02 → 01, 03 → 02, 04 → 03 deb qayta raqamlash va tartiblash (boshqa fayllarda havola yo'q) | kichik |
| A-024 | `00-README.md`:1–3 | README 5-qoidasi ("har fayl boshida Maqsad · Kim uchun · Bog'liq fayllar · Holat") 00 ning o'zida bajarilmagan. | 1-qatordan keyin qo'shish: "**Maqsad:** kod uchun spec'ga kirish nuqtasi va o'qish tartibi. · **Kim uchun:** hammasi. · **Bog'liq fayllar:** 01–34. · **Holat:** joriy, 2026-10-16." | kichik |
| A-025 | `07-ekran-tafsilotlari.md`:429, 1357; `14-autentifikatsiya-oauth2.md`:484, 533; `19-api-ombor.md`:962; `01-qarorlar.md`:13 | Tarix qoldiqlari: "yangi qarz yozish **endi** POS-02 orqali", "bu bosqich **endi** … (nusxasi emas)", "`/admin/users` bilan **endi** aralashmaydi", "`users` (mavjud, tozalanadi) … `user_credentials`ga **ko'chirildi**", "Limitdan katta — **endi** `202 APPROVAL_REQUIRED`…", "#10: UzQR … **qo'shildi**". | Joriy holatni yozish: 07:429 "yangi qarz POS-02 orqali oddiy sotuv sifatida yoziladi"; 07:1357 "bu bosqich `/install` route'ini ichiga oladi"; 14:484 "(tenant `/admin/users` dan alohida)"; 14:533 "`users` — id, phone, name, locale; parol/PIN heshlari `user_credentials` da"; 19:962 "Limitdan katta — `202 APPROVAL_REQUIRED` yo'li; bu kod faqat tasdiq so'ralmaganda"; 01:13 "M01 to'lov turlarida UzQR bor" | kichik |
| A-026 | `12-db-sxema.md`:3867 | Lotin matn ichida kirill qo'shimcha: "Kassir rol**ига**". | → "Kassir roliga" | kichik |
| A-027 | `32-kod-qoidalari.md`:377 | "`spec/kod-uchun-atamalar` (joriy branch nomi shu uslubga mos)" — joriy branch `spec/tekshiruv-va-mahsulot`. Bu vaqtga bog'liq, eskirgan ma'lumot. | Qavs ichidagi izohni olib tashlash; namuna sifatida `spec/<qisqa-tavsif>` qoldirish | kichik |
| A-028 | `09-ai-funksiyalar.md`:11, 12, 13, 15, 27, 40, 54, 55, 68, 69, 70, 95, 109, 119, 133, 143, 153, 155 | `` `texnik/05-ozbek-tilidagi-ai.md` ``, `` `texnik/00-…` ``, `` `texnik/03-…` `` — prefiks yetishmaydi (`research_notes/texnik/…` da mavjud), boshqa fayllar to'liq yo'l yozadi. | `texnik/` → `research_notes/texnik/` | kichik |
| A-029 | `23-backend-arxitekturasi.md`:366 | `postgres:17-alpine` — 12 sarlavhasi va DDL "PostgreSQL 16" (`uuidv7` izohi 12:65 PG16 ga asoslangan). Dev va prod versiyalari farq qiladi. | → `postgres:16-alpine` | kichik |
| A-030 | `14-autentifikatsiya-oauth2.md`:622 | "`01-qarorlar.md` (#3 veb-kassa autentifikatsiyasi …)" — #3 "(o'rniga #14)" belgilangan; asosiy qaror #14. | → "(#14 veb-kassa autentifikatsiyasi, #3 — 401 qayta kirish qismi, #4 CSRF, #13 obuna holati)" | kichik |
| A-031 | `02-rollar-va-ssenariylar.md`:112, 255; `03-modullar-talablari.md`:125, 460, 511, 616, 883; `05-mvp-chegarasi.md`:10, 12; `17-api-umumiy.md`:5 (Bog'liq fayllar) | Manba sifatida `kod-uchun` dan tashqaridagi `spec/README.md` keltirilgan, 00 esa "kod faqat shu hujjatlarga tayanadi" deydi. 17 da u "Bog'liq fayllar" ro'yxatida turibdi. | 17:5 dan `spec/README.md` ni olib tashlash (`00-README.md` qo'yish). 02/03/05 da tegishli 01 qaror raqamiga almashtirish (masalan, offline-first → qaror #21/#43) yoki `research_notes/…` manbasini keltirish | kichik |

## Tekshirilgan, lekin xato emas

- 3–34 fayllardagi tadqiqot fayllariga qisqa nom bilan havolalar (`04-arxitektura-va-stack.md`, `03-efaktura-va-tolov.md`, `00-inventar.md`, `research_notes/1c-integratsiya/02`, `…/P1`): hammasi `research_notes/` ichida mavjud.
- Qonun bandlari: `S1 §146…§412`, `NSBU №21 Yo'riqnoma §237–239`, `D §5.0`, `sonar-…/01 §5.7`.
- 12:2467 "0028 onec_integration — 13 jadval": 19 jadvaldan `updated_at` trigger'li 13 tasi (massivda sanalgan) — to'g'ri. Aniqroq bo'lishi uchun "13 ta `updated_at`li jadval" deb yozish mumkin.
- 26 #44 bo'sh: 26:268 da izohlangan.
- `ONEC_*` dan boshqa barcha HTTP-xato kodlari (18, 19, 20 dagi "Ishlatilgan xato kodlari" bo'limlari) 17 §15 katalogida bor. `MARKING_PRECHECK`, `FX_USD_UZS_FALLBACK`, `AI_PII_ROUTE` — sozlama yoki flag, xato kodi emas.
- 07:477 `cash.approve` — "alohida kod yo'q" deb atayin tilga olingan.
- `(avval yozilgan bo'lsa)` (12:2936) — shart, tarix belgisi emas.

## Eng muhim 10 ta

1. **A-001** — 01 dagi `OSn` ko'rsatkichlari eskirgan: 26 tasi mavjud bo'lmagan bandni ko'rsatadi, qolganlari esa boshqa mavzuni.
2. **A-019** — 26 #133 dagi interim nomlar (`ONEC_ACCOUNTS_UNRESOLVED`, `fill_accounts_mode`, `vat_round`) 33 yagona manbasi va 81 ta kod katalogiga zid.
3. **A-022** — 31 "har Must US uchun kamida bitta test" deydi, lekin US-M01-07, US-M17-03, US-M19-04 uchun test yo'q.
4. **A-009** — 12 DDL izohlarida fayllarning eski raqamlari (05-xavfsizlik, 12-auth, 04-offline-sync).
5. **A-021** — 23 dagi "README qarori" `kod-uchun` dan tashqaridagi hujjatga tayanadi, 01 da qaror yo'q.
6. **A-003** — `18` §15a mavjud emas (to'g'risi §14a), 26 va 27 da.
7. **A-018** — mavjud bo'lmagan `34-dokon-agenti.md` ga 3 ta havola.
8. **A-020** — 26 da "yangi bandlar #106 dan" (#170 gacha band) raqam to'qnashuviga olib keladi.
9. **A-011** — 14 §16.1.1/16.1.3/16.1.5 sarlavha sifatida mavjud emas (6 ta fayldagi 14 ta havola).
10. **A-004 / A-013** — noto'g'ri bo'limga havolalar: `14` §1.4 → `15` §1.4; `05` §4.2/§4.4 noto'g'ri bandni ko'rsatadi.
