# P7 — Buxgalteriya: NSBU №21 hisoblar rejasi va provodka qoidalari (OQ-066…074)

**Maqsad:** `00-inventar.md` §8/§12 dagi P7 partiyasi — OQ-066, 067, 068, 069, 070, 071, 073, 074 ni birlamchi manba (lex.uz to'liq matni) bilan yopish va `13-provodka-qoidalari.md` ga aniq provodka qatorlarini taklif qilish. · **Kim uchun:** spec'ni yangilovchi agent, backend (posting xizmatlari), buxgalter (yakuniy ko'rib chiqish, bloklamaydi). · **Bog'liq fayllar:** `spec/kod-uchun/13-provodka-qoidalari.md`, `01-qarorlar.md` #30/#42, `04-biznes-jarayonlar.md` BP-03/BP-11, `26-ochiq-savollar-reestri.md`, `research_notes/1c-integratsiya/02-…md`, `03-…md`. · **Holat:** desk-research, 2026-10-16. Spec fayllari **o'zgartirilmadi**.

---

## 0. Eng muhim topilmalar

1. **NSBU №21 ning to'liq rasmiy matni o'qildi.** `lex.uz/docs/7282737` — bu BHMS №21 ning o'zi (191-son buyruqning 1-ilovasi). Uning ichida **1-ILOVA = Hisobvaraqlar rejasi**, **2-ILOVA = Qo'llash yo'riqnomasi** (§1–§436) bor. Hujjatning joriy tahriri **16.03.2026** (oldingilari 24.09.2025 va 01.01.2025). Unga ikki o'zgartirish kiritilgan: **282-son buyruq** (26.08.2025, ro'yxat 3593-1, 24.09.2025 — 0870-hisob shu yerda) va **336-son buyruq** (04.03.2026, ro'yxat 3593-2, 13.03.2026). `13` boshidagi "faqat sarlavha o'qildi" degan ogohlantirish endi eskirgan.
2. **MVP subsetidagi barcha kodlar rasmiy rejada bor.** Bir nechta nom noaniq yozilgan (§2, OQ-066 jadvali). Spec'da yo'q, lekin kerak bo'ladigan hisoblar: **9390** (ortiqcha va boshqa operatsion daromad), **2920** (chakana savdodagi tovarlar), **4890**, **6610**, **8530**.
3. **Bank va ekvayring komissiyasi 9410 ga emas, 9430 ga yoziladi.** Asos: Yo'riqnoma §410, §412 jadvalining 12-qatori, VMQ-54 2.3.12. **Inkassatsiya** xarajati esa 9410 da qoladi (VMQ-54 2.1.2.18).
4. **Inventarizatsiyadagi ortiqcha 9390 ga yoziladi, 9320 ga emas** (§154 7-qator, §405 14-qator, BHMS 4 92-band). 9320 faqat aybdordan bozor qiymatida undirilganda farq uchun ishlatiladi (§203).
5. **Nasiyada daromad va QQS sotuv kuni tan olinadi — bu interim taxmin emas, qonun normasi:**
   - BHMS 2 16-band — xatar va afzalliklar o'tganda;
   - Soliq kodeksi **242-modda** — tovar jo'natilgan (berilgan) sana;
   - Soliq kodeksi 78-modda — hisoblash (accrual) usuli.

   Demak, `13` §2.14 dagi "kassa usuliga o'tish bayrog'i" buxgalteriya va QQS uchun qonuniy variant emas (§3.1).
6. **Shubhali qarz bo'yicha NSBU tartibi — 4910 rezervi** (§217–221): yil oxirida, har bir qarz bo'yicha alohida baholanadi. To'g'ridan-to'g'ri 9430 ga hisobdan chiqarish ham mumkin (VMQ-54 2.3.15.7). Soliqda esa rezerv chegirilmaydi; umidsiz qarz faqat SK 313-modda shartlari bajarilganda chegiriladi.

---

## 1. Holat jadvali

| OQ | Mavzu | Holat | Bir qatorda |
|---|---|---|---|
| OQ-066 | NSBU №21 to'liq matni ↔ MVP subset | **YOPILDI** | Barcha kodlar mavjud; 7 ta nom tuzatiladi; 9390/2920/4890/6610/8530 qo'shiladi |
| OQ-067 | QQS: 4410/6410 yoki maxsus hisob | **YOPILDI** | 4410/6410 to'g'ri (§190, §191, §275, §378); maxsus QQS hisobi yo'q; oylik `Dt 6410 / Kt 4410` qo'shiladi |
| OQ-068 | Xarajat toifalari → 9410/9420/9430; komissiya | **YOPILDI** | VMQ-54 2.1/2.2/2.3 + Yo'riqnoma §407–412 bo'yicha seed xaritasi; ekvayring → 9430, inkasso → 9410 |
| OQ-069 | Inventarizatsiya: ortiqcha/kamomad | **YOPILDI** | Ortiqcha → 9390 (joriy qiymatda); kamomad → 5910 → 9430 yoki 4730; kassa kamomadi → 4730 |
| OQ-070 | Shubhali qarz: 9430 yoki 4910 | **YOPILDI** | Ikkalasi ham qonuniy; 4910 — yil oxiri rezervi (§217–221), qaytarilgan qarz → 9390 |
| OQ-071 | Boshlang'ich qoldiq qarshi hisobi (8720) | **YOPILDI** (tavsiya + dalil) | NSBU'da maxsus hisob yo'q; 1C amaliyotidagi kabi texnik **0000** yordamchi hisob; 8720 noto'g'ri |
| OQ-073 | Egasi oldi / inkasso / smena farqi | **QISMAN** | Inkasso va smena farqi yopildi; "Egasi oldi" huquqiy shaklga bog'liq — interim: MChJ/XK → 4890, YaTT → 8720 (boshqaruv hisobi) |
| OQ-074 | Chegirma, "2+1", tekin tovar — QQS | **QISMAN** | Chek chegirmasi yopildi (SK 248 2-qism); "2+1" va sovg'a uchun interim berildi, buxgalter/soliq maslahatchisi tasdiqlaydi |

---

## 2. Manbalar (birlamchi → ikkilamchi)

| # | Manba | Nima uchun |
|---|---|---|
| S1 | **BHMS №21** «Хўжалик юритувчи субъектларда бухгалтерия ҳисобининг ҳисобварақлар режаси ва уни қўллаш бўйича йўриқнома», ro'yxat 3593, 27.12.2024; tahrir 16.03.2026 — [lex.uz/docs/7282737](https://lex.uz/docs/7282737) (rus interfeysi: [lex.uz/ru/docs/7282737](https://lex.uz/ru/docs/7282737); matn o'zbek kirillida) | 1-ilova (reja), 2-ilova (yo'riqnoma §1–436) |
| S2 | 191-son buyruq (14.11.2024) — [lex.uz/ru/docs/7282759](https://lex.uz/ru/docs/7282759) | BHMS 21 ni tasdiqlovchi buyruq, bekor qilingan hujjatlar |
| S3 | **BHMS №2** «Асосий хўжалик фаолиятидан даромадлар», 132-son buyruq 14.06.2024, ro'yxat 3542 (05.08.2024) — [lex.uz/ru/docs/7051181](https://lex.uz/ru/docs/7051181) | Daromadni tan olish (11, 13, 16, 17-bandlar) |
| S4 | **BHMS №4** «Товар-моддий захиралар», ro'yxat 3259 (30.06.2020) — [lex.uz/docs/4890446](https://lex.uz/docs/4890446) | FIFO/AVECO (62-band), ortiqcha bahosi (32), kamomad (91), ortiqcha → daromad (92) |
| S5 | **Soliq kodeksi** — [lex.uz/docs/4674902](https://lex.uz/docs/4674902) (rasmiy o'zbekcha), [lex.uz/ru/docs/4674893](https://lex.uz/ru/docs/4674893) (norasmiy ruscha) | 41, 78, 239, 242, 247, 248, 257, 299, 313, 315, 463, 464, 466-moddalar |
| S6 | **VMQ-54** (05.02.1999) «Xarajatlar tarkibi to'g'risidagi Nizom», oxirgi tahrir 05.04.2022 — [lex.uz/ru/docs/265675](https://lex.uz/ru/docs/265675) | Davr xarajatlari tasnifi: 2.1 sotish, 2.2 ma'muriy, 2.3 boshqa operatsion |
| S7 | «Buxgalteriya hisobi to'g'risida»gi Qonun (O'RQ-404 tahriri) — [lex.uz/docs/2931251](https://lex.uz/docs/2931251) | 6-modda — YaTT buxgalteriya hisobi subyekti emas |
| S8 | buxgalter.uz — «Как учитывать излишки и недостачи денежных средств» — [text180074](https://buxgalter.uz/publish/doc/text180074_kak_uchityvat_izlishki_i_nedostachi_denejnyh_sredstv) | Inkasso, kassa kamomadi/ortiqchasi — tayyor provodkalar |
| S9 | buxgalter.uz — «Налоговые последствия рекламных акций» (GNK vakili A. Xashimov) — [text168266](https://buxgalter.uz/publish/doc/text168266_nalogovye_posledstviya_reklamnyh_akciy) | Tekin berish, QQS, "iqtisodiy asoslangan" |
| S10 | saliq.uz — «Как рассчитать НДС при безвозмездной передаче» (MF vakili B. Boykabilov) — [saliq.uz/ru/271.html](https://saliq.uz/ru/271.html); gazeta.norma.uz [text172500](https://gazeta.norma.uz/publish/doc/text172500_kak_rasschitat_nds_pri_bezvozmezdnoy_peredache1) | Tekin topshirishda QQS bazasi, VMQ-489 3-ilova |
| S11 | buxgalter.uz savoli №32444 ("5+1" aksiyasi) — [question/32444](https://buxgalter.uz/question/32444) | Amaliyot: "N+1" ESF'da tekin birlik sifatida, import-QQS minimumi |
| S12 | buxgalter.uz — «Налоговые последствия при реализации товаров со скидкой» — [text202616](https://buxgalter.uz/publish/doc/text202616_kakie_nalogovye_posledstviya_voznikayut_pri_realizacii_tovarov_so_skidkoy) | Chegirma va SK 248 5-qism (import minimumi) |
| S13 | fmc.uz — 1C yo'riqnomasi «Ввод остатков по счетам» — [fmc.uz/main.php?op=vvod_ostatkov](http://fmc.uz/main.php?op=vvod_ostatkov) | Boshlang'ich qoldiqlar uchun yordamchi hisob "000" |
| S14 | perfect-solutions.uz — «Проводки по НДС в Узбекистане» (1C integratori, 25.09.2026) — [havola](https://perfect-solutions.uz/1c-buhgalteriya-nalogi/provodki-po-nds-uzbekistan-primery/) | 4410/6410 amaliyoti, oylik hisobga olish `Dt 6410 / Kt 4410` |
| S15 | `research_notes/1c-integratsiya/02-…md` (bss.uz [M10], 1C BP UZ) | Karta tushumi: 5710/5711 subhisob amaliyoti |

Cheklovlar:
- WebSearch kvotasi tugagan edi. Qidiruv DuckDuckGo HTML va `curl` orqali bajarildi, lex.uz matnlari to'liq yuklab olinib, mahalliy grep qilindi.
- buxgalter.uz Pro / gazeta.norma.uz maqolalarining ko'pi pullik obuna ortida. Faqat ochiq qismlar iqtibos qilindi.
- Soliq kodeksining ruscha matni norasmiy tarjima. 242 va 248-moddalar rasmiy o'zbekcha matn bilan ham solishtirildi.

---

## 3. Har OQ bo'yicha

### OQ-066 — NSBU №21 to'liq matni va MVP subset

**Javob:** `13` §1 dagi barcha 24 kod rasmiy rejada **bor**. Turlari: A (aktiv), P (passiv), KA (kontr-aktiv), T (tranzit, 9000-guruh). 7 ta nom rasmiy nomdan farq qiladi. "9300-oilasi" o'rniga aniq kod **9390**. Qo'shimcha kerakli hisoblar: 2920, 4890, 6610, 8530, 9390. **0870** «Operativ ijaraga olingan asosiy vositalarga kapital qo'yilmalar» rejada bor (282-son tahriri), lekin MVP'ga kerak emas.

**Dalil (S1, 1-ILOVA — reja jadvali; nomlar o'zbek kirillidan lotinga o'girildi):**

| Kod | Rasmiy nom (S1) | Tur | `13` §1 dagi nom → tuzatish |
|---|---|---|---|
| 2910 | Ombordagi tovarlar | A | mos |
| 2920 | Chakana savdodagi tovarlar | A | **yo'q → qo'shish** (§146: «чакана савдо ташкилотлари (магазинлар, палаткалар, киосклар…)… товарларнинг мавжудлиги ва ҳаракати») |
| 2970 | Yo'ldagi tovarlar | A | mos (§151 — "hisobot davri oxirida yo'lda qolgan" — filiallararo tranzit uchun talqin, quyida) |
| 4010 | Xaridorlar va buyurtmachilardan olinadigan to'lovlar | A | "Xaridorlardan olinadigan hisoblar (debitorlik)" → **rasmiy nom** |
| 4310 | Tovar-moddiy zaxiralar uchun mol yetkazib beruvchilar va pudratchilarga berilgan bo'naklar | A | "Yetkazib beruvchilarga berilgan avanslar" → **rasmiy nom** |
| 4410 | Byudjetga soliqlar va yig'imlar bo'yicha bo'nak to'lovlari (turlari bo'yicha) | A | mos (izoh — OQ-067) |
| 4730 | Moddiy zararni qoplash bo'yicha xodimlarning qarzi | A | "Kamomad bo'yicha moddiy javobgar shaxsdan…" → **rasmiy nom** |
| 4890 | Boshqa debitorlik qarzlar | A | **qo'shish** (OQ-073) |
| 4910 | Shubhali qarzlar bo'yicha rezerv | **KA** | mos |
| 5010 | Milliy valyutadagi pul mablag'lari | A | mos |
| 5110 | Hisob-kitob hisobvarag'i | A | mos |
| 5710 | Yo'ldagi pul mablag' (o'tkazma)lari | A | mos |
| 5910 | Kamomadlar va qiymatliklarning buzilishidan yo'qotishlar | A | "…(javobgar shaxs aniqlanmagan)" → **rasmiy nom**; aybdor aniqlangunga qadar ham ishlatiladi (BHMS 4 92-band) |
| 6010 | Mol yetkazib beruvchilar va pudratchilarga to'lovlar | P | mos |
| 6410 | Byudjetga to'lovlar bo'yicha qarzlar (turlari bo'yicha) | P | mos |
| 6610 | To'lanadigan dividendlar | P | **qo'shish** (OQ-073) |
| 6710 | Ish haqi bo'yicha xodimlar bilan hisob-kitoblar | P | mos |
| 8530 | Tekinga olingan mulk | P | **qo'shish** (OQ-074) |
| 8710 | Hisobot davrining taqsimlanmagan foydasi (qoplanmagan zarari) | P | mos |
| 8720 | Jamg'arilgan foyda (qoplanmagan zarar) | P | "To'plangan foyda" → **"Jamg'arilgan foyda"** |
| 9020 | Tovarlarni sotishdan daromadlar | T | mos |
| 9040 | Sotilgan tovarlar (mahsulotlar)ning qaytishi | T (kontr-passiv, §381) | "Sotilgan tovarni qaytarish (daromaddan chegirish)" → **rasmiy nom** |
| 9050 | Xaridorlar va buyurtmachilarga berilgan chegirmalar | T (kontr-passiv, §382) | mos |
| 9120 | Sotilgan tovarlarning tannarxi | T | mos |
| 9390 | Boshqa operatsion daromadlar | T | **"9300-oilasi" → 9390** (OQ-069) |
| 9410 / 9420 / 9430 | Sotish xarajatlari / Ma'muriy xarajatlar / Boshqa operatsion xarajatlar | T | mos (9430 nomidan "(shu jumladan shubhali qarz zahirasi)" olib tashlanadi — bu nom emas, foydalanish holati) |
| 9910 | Yakuniy moliyaviy natija (foyda yoki zarar) | T | mos |

**Ishonch:** yuqori (birlamchi matn, joriy tahrir 16.03.2026).

**Spec'ga ta'sir:**
- `13` boshidagi ogohlantirish 1-band, "Asosiy xulosa" 1-band, §1 kirish matni va "Manbalar" — "faqat sarlavha o'qildi" o'rniga: "to'liq matn [lex.uz/docs/7282737](https://lex.uz/docs/7282737), tahrir 16.03.2026 (282-son 24.09.2025, 336-son 16.03.2026 o'zgartirishlari bilan) bo'yicha solishtirildi".
- §1 jadvalidagi "Ishonchlilik" ustuni barcha qatorlarda "S1 (rasmiy matn)" bo'ladi.
- Yuqoridagi 7 ta nom tuzatiladi; 2920, 4890, 6610, 8530, 9390 qo'shiladi (append-only seed).
- "Tur" ustunida rasmiy belgi ishlatiladi: 9xxx → "T (tranzit)".
- **2920 bo'yicha alohida taklif:** `warehouses` ga `inventory_account` (standart 2910). Do'kon savdo zali (`kind=store`) uchun 2920 tavsiya qilinadi (§146). Barcha `2910` provodkalari "ombor hisobi" (`inv_acct(warehouse)`) deb parametrlashtiriladi. Bu 1C eksportiga ham ta'sir qiladi (`research_notes/1c-integratsiya/02` allaqachon 2910/2920/2980 ni eslatgan).
- **Holat: YOPILDI.** Buxgalter yakuniy ko'zdan kechiradi, bloklamaydi.

---

### OQ-067 — QQS: 4410/6410 yoki maxsus hisob

**Javob:** Maxsus QQS hisobi **yo'q va kerak emas**:
- kiruvchi (kiritiladigan) QQS → **4410** debeti;
- chiquvchi QQS → **6410** krediti (analitika — soliq turi);
- davr oxirida **`Dt 6410 / Kt 4410`** bilan hisobga olinadi;
- byudjetga to'lov → **`Dt 6410 / Kt 5110`**.

Spec'dagi 2.1, 2.3, 2.5, 2.6, 2.20 qatorlari rasmiy korrespondensiyaga mos. Faqat oylik hisobga olish (offset) provodkasi va soliq to'lovi provodkasi yetishmaydi.

**Dalil:**
- S1 §190: «4410 … ҳисобварағида бўнак сифатида тўланган солиқ суммалари, **шу жумладан, харид қилинган товар-моддий захиралар бўйича ҳисоб-китоб ҳужжатларида кўрсатилган қўшилган қиймат солиғи** ҳисобга олинади. Солиқлар суммасини ҳисобдан чиқариш 4410 … кредитида 6410 … билан боғланган ҳолда акс эттирилади.»
- S1 §191 jadvali:
  - 1-qator «Харид қилинган … товарлар … бўйича ҚҚС суммаси — **Дт 4410 / Кт 6010, 6120, 6990**»;
  - 3-qator «… ҚҚС ҳисобга олинди — **Дт 6410 / Кт 4410**».
- S1 §378: «Маҳсулот (товар…)ларни сотишдаги қўшилган қиймат солиғи … олинадиган ҳисобварақлар ёки пул маблағларини ҳисобга олувчи ҳисобварақларнинг дебетида ва … (6400) кредитида акс эттирилади.» Shu bilan `Dt 5010/5710/4010 / Kt 6410` tasdiqlanadi.
- S1 §275 jadvali:
  - 2-qator «… товарларни сотишда … ҚҚС … ҳисобланиши — Дт 4010 / Кт 6410»;
  - 7-qator «Бюджетга тўловлар ўтказиб берилиши — Дт 6410 / Кт 5010-5530»;
  - 8-qator «… ҚҚС суммаси ҳисобга олиниши — Дт 6410 / Кт 4410».
- S1 §274: «6410 … бўйича аналитик ҳисоб **ҳар бир солиқ турлари бўйича** алоҳида юритилади». Bu spec'dagi `tax_type` analitikasini tasdiqlaydi.
- S1 §381 (qaytarish): «олдин ҳисобланган қўшилган қиймат солиғи … бўйича … ҳисобварақларининг дебети ва пул маблағларини ҳисобга олувчи ҳисобварақлар, олинадиган ҳисобварақларнинг кредитида ёзув амалга оширилади». `13` §2.5 2-qatori aynan shu.
- S3 (BHMS 2) 11-band: «… билвосита солиқлар сингари суммалар асосий хўжалик фаолияти даромадига киритилмайди». Demak 9020 QQSsiz yoziladi.
- S14 (1C UZ amaliyoti): «Зачёт входного НДС: **Дт 6410 — Кт 4410** … Именно эта проводка «сводит» два НДС-счёта». Eslatma: 1C'da sotuv QQSini `Dt 9020 / Kt 6410` bilan ham yozishadi (avval brutto daromad). Natija bir xil, lekin §378 sof usulni ko'rsatadi. 1C eksportida farqni hisobga olish kerak.
- 6240 «Солиқлар ва йиғимлар бўйича кечиктирилган мажбуриятлар» (§266) faqat qonun bilan kechiktirilgan soliqlar uchun. Nasiyadagi QQS kechiktirilmaydi (SK 242, §3.1). Demak MVP'da 6240 kerak emas.

**Ishonch:** yuqori.

**Spec'ga ta'sir (`13`):**
- Ogohlantirish 2-band → "S1 §190/191/275/378 bilan tasdiqlandi" (ochiq savollar ro'yxatidan chiqariladi).
- **Yangi §2.26 "QQS davr hisob-kitobi"** (`vat_period_settlements` yoki `period_closings` ichida, oy yakunida; hujjat turi — D-qaror):

  | # | Dt | Kt | Summa | Analitika |
  |---|---|---|---|---|
  | 1 | 6410 | 4410 | `SUM(vat_moves.vat_amount WHERE kind=input, period)` (hisobga olinadigan kiruvchi QQS; "qizil" fakturaning to'lanmagan qismi kirmaydi — §4.1) | tax_type=QQS |

- **Soliq to'lovi:** `expense_categories` ga "Soliq to'lovi (byudjetga)" toifasi qo'shiladi → `Dt 6410 / Kt 5110` (`tax_type` majburiy). Bu xarajat emas, majburiyatni yopadi. §2.17 dagi "Soliq va yig'imlar → 6410/9420" yozuvi shu bilan almashtiriladi (S1 §275 7-qator).
- §4.1 mermaid diagrammasiga "oy yakuni: Dt 6410 / Kt 4410" tuguni qo'shiladi.
- **Holat: YOPILDI.**

---

### OQ-068 — Xarajat toifalari → 9410/9420/9430; bank komissiyasi

**Javob (seed xaritasi):**

| `expense_categories` (taklif) | Hisob | Asos |
|---|---|---|
| Ijara — savdo zali/do'kon/ombor | **9410** | VMQ-54 2.1.2.3 «Расходы на аренду, содержание и ремонт зданий, сооружений и помещений, используемых для торговых нужд» (2.1 «Расходы по реализации») |
| Ijara — ofis (ma'muriy) | **9420** | VMQ-54 2.2.8 «Плата за аренду зданий и помещений для административно-управленческих нужд»; S1 §409 «умумхўжалик аҳамиятидаги биноларнинг ижара тўловлари»; §412 7-qator «Бошқарув биносининг ижара тўлови — 9420 / 6910» |
| Kommunal (elektr, gaz, yoqilg'i) — do'kon | **9410** | VMQ-54 2.1.2.6 «Расходы на газ, топливо, электроэнергию» (savdo korxonalarining sotish xarajatlari) |
| Kommunal — ofis | 9420 | VMQ-54 2.2.4 (boshqaruv) — *talqin* |
| Aloqa, internet, telefon | **9420** | VMQ-54 2.2.6, 2.2.7 |
| Transport — tovar tashish/yetkazib berish | **9410** | VMQ-54 2.1.1; S1 §407 «маҳсулотни истеъмолчига етказиб бериш билан боғлиқ»; §412 1-qator «… транспорт харажатлари — 9410» |
| Transport — xizmat avtomobili | **9420** | VMQ-54 2.2.3 |
| Ish haqi — sotuvchi/kassir/omborchi | **9410** | VMQ-54 2.1.2.1 «… связанные с реализацией продукции … кроме административного управленческого персонала» |
| Ish haqi — boshqaruv (direktor, buxgalter) | **9420** | VMQ-54 2.2.1; S1 §409, §412 5-qator «Бошқарув ходимларининг иш ҳақи — 9420 / 6710» |
| Reklama, marketing | **9410** | VMQ-54 2.1.2.8, 2.1.3; S1 §412 2-qator |
| Ta'mirlash — savdo binosi/jihozlari | 9410 | VMQ-54 2.1.2.3 |
| Ta'mirlash — ma'muriy | 9420 | VMQ-54 2.2.9 |
| Tara, qadoqlash | 9410 | VMQ-54 2.1.2.10 |
| Inventar, xo'jalik buyumlari | 9410 / 9420 | VMQ-54 2.1.2.5 / 2.2.17 |
| **Bank xizmatlari, ekvayring, Click/Payme/Uzum komissiyasi** | **9430** | S1 §410 «… **банк ва депозитар хизматларининг тўловлари** …»; §412 12-qator «Банк ва аудиторлик хизматлари учун тўловлар — **9430** / 6990»; VMQ-54 2.3.12 «Оплата услуг банка» (2.3 «Прочие операционные расходы») |
| **Inkassatsiya xizmati** | **9410** | VMQ-54 2.1.2.18 «Издержки по ведению кассового хозяйства и инкассации выручки» (savdo korxonalari sotish xarajatlari) |
| Davr xarajatiga taalluqli soliq/yig'imlar | 9430 / Kt 6410 | S1 §275 1-qator «Давр харажатларига тааллуқли хар хил … солиқлар ва йиғимлар … — 9430 / 6410» |
| Jarimalar, penyalar | 9430 | S1 §412 16, 21-qatorlar; VMQ-54 2.3.15 |
| Audit, maslahat, o'qitish | 9430 | S1 §410 |
| Boshqa | 9430 | S1 §410 (qoldiq toifa) |

**Dalil (qo'shimcha):**
- S1 §406 — 9400 guruhi «ишлаб чиқариш жараёни билан бевосита боғлиқ бўлмаган сотиш харажатлари, бошқарув харажатлари, бошқа операцион харажатлар»ni umumlashtiradi.
- S1 §407: «9410 «Сотиш харажатлари» ҳисобварағида маҳсулотни сотиш бўйича харажатлар … акс эттирилади».
- VMQ-54 hozir amalda (S6, oxirgi tahrir 05.04.2022). Uning 2.1.2-bandi aynan savdo korxonalari uchun yozilgan.

**Ishonch:**
- yuqori — bank komissiyasi (ikki mustaqil birlamchi manba), ijara, ish haqi va transport (VMQ-54 savdo uchun aniq);
- o'rta — Click/Payme/Uzum komissiyasi. Ular bank emas, to'lov tashkiloti. "To'lov xizmati" sifatida 9430 ga o'xshatma bilan qo'yildi. Buxgalter 9410 (2.1.2.18 "kassa xo'jaligi") ni tanlashi ham mumkin, shuning uchun bu sozlanadigan bo'ladi.

**Spec'ga ta'sir:**
- `13` §2.17 dagi "Toifa → hisob moslashuvi (taxmin)" paragrafi yuqoridagi jadval bilan almashtiriladi (manba ustuni bilan). Seed `expense_categories(code, default_account, source_ref)` tuziladi, tenant o'zgartira oladi.
- §2.18a 2-qator: `9410 (taxmin)` → **`commission_account(method)`**:

  | # | Dt | Kt | Summa |
  |---|---|---|---|
  | 2 (`method ∈ card, uzqr, click, payme, uzum`) | **9430** | 5710 | `commission_amount` |
  | 2 (`method = collection`) | **9410** | 5710 | `commission_amount` (inkassatsiya xizmati) |

- §2.18a "Misol" matnida `Dt 9410 / Kt 5710 = "9500.00"` → `Dt 9430 / Kt 5710 = "9500.00"`.
- Ogohlantirish 3 va 6-bandlar → "S1 §407–412, VMQ-54 bilan yopildi".
- Ekvayer komissiyasiga QQS (agar provayder QQS bilan e-faktura bersa) qo'shimcha `Dt 4410 / Kt 5710` qatorini talab qiladi. Bank xizmatlari odatda QQSdan ozod (SK 244-modda — moliyaviy xizmatlar; bu yerda batafsil tekshirilmadi). MVP: QQSsiz. Agar provayder fakturasida QQS bo'lsa — keyingi bosqich.
- **Holat: YOPILDI** (seed xaritasi; buxgalter tenant darajasida o'zgartira oladi).

---

### OQ-069 — Inventarizatsiya: ortiqcha / kamomad

**Javob:**
- **Ortiqcha:** `Dt 2910 (2920) / Kt 9390`. Baholash — aniqlangan sanadagi **joriy qiymat**. 9320 ishlatilmaydi.
- **Kamomad, aybdor aniqlanmagan:** avval `Dt 5910 / Kt 2910` (balans qiymati). Rahbar qaroridan keyin `Dt 9430 / Kt 5910`.
- **Kamomad, aybdor aniq:** `Dt 4730 / Kt 2910` to'g'ridan-to'g'ri, yoki 5910 orqali (`Dt 4730 / Kt 5910`).
- **Kassa kamomadi** (smena yopish) to'g'ridan-to'g'ri **`Dt 4730 / Kt 5010`**. **Kassa ortiqchasi:** `Dt 5010 / Kt 9390`.

**Dalil:**
- S1 §154 (2900 jadvali):
  - 7-qator «Инвентаризация натижасида аниқланган ортиқча товарлар ва таралар — **2910-2990 / 9390**»;
  - 11-qator «… камомад, агар айбдор шахс аниқланмаган бўлса — **5910 / 2910-2990**»;
  - 14-qator «… моддий жавобгар шахс айби билан аниқланган камомад — **4730 / 2910-2990**».
- S1 §405 14-qator: «Инвентаризация натижасида аниқланган ортиқча маҳсулотлар, товарларнинг кирим қилиниши — 2810-2890, 2910-2990 / **9390**».
- S1 §247: 5910 krediti
  - «а) … аниқ айбдорлари аниқланганда — 4860 …, 4730 … дебети»;
  - «б) … аниқ айбдор шахси аниқланмаганда … — **9430** … дебетига ҳисобдан чиқарилиши».

  §249 4-qator «Ундирилмаган суммалар ҳисобдан чиқарилди … — 9430 / 5910».
- S1 §223 20-qator: «Пул маблағларининг камомади (инвентаризация натижасида) — **4730 / 5010, 5020**»; §206 10-qator ham shunday.
- S1 §203 (aybdordan bozor qiymatida undirish): bozor qiymati balansdan yuqori bo'lsa — «дебет 4730 — бозор қийматига; кредит 5910 — … зарар суммасига; **кредит 9310, 9320** — … фарқига». Past bo'lsa — farq «дебет 9430». 9320 aynan shu holat uchun. Oddiy ortiqcha uchun emas.
- S4 (BHMS 4):
  - 32-band «Инвентаризация натижасида аниқланган ортиқча … товар-моддий захираларининг таннархи **улар аниқланган санадаги жорий қийматдан** келиб чиққан ҳолда аниқланади»;
  - 91-band «… камомадлар уларнинг (баланс) қиймати бўйича ҳисобдан чиқарилади … айбдорлари аниқланмаган … ҳолларда … **бошқа операцион харажатларга**»;
  - 92-band «… ортиқча … кирим қилиш **бошқа операцион даромадлар** сифатида акс эттирилади. Камомади … айбдор шахслар аниқланишига қадар … (5910) … счётда акс эттирилади».
- VMQ-54: 2.1.2.9 «Потери товаров … при … хранении и реализации» (tabiiy kamayish me'yori doirasida) → 9410; 2.3.15.2 «Потери и недостачи … не относящиеся непосредственно к производственному процессу» → boshqa operatsion (9430).
- S8 (buxgalter.uz, inkasso amaliyoti): kamomad `5910/5710` → aybdor bo'lsa `4730/5910` → ish haqidan `6710/4730`; aybsiz bo'lsa `9430/5910` («такие расходы относятся к невычитаемым по налогу на прибыль»); ortiqcha `5710/9390` («Не забудьте включить … доход … Для плательщиков налога с оборота такой доход облагается…»).

**Ishonch:** yuqori (bir-biriga mos uchta birlamchi manba).

**Spec'ga ta'sir (`13` §2.11 to'liq almashtiriladi):**

| Holat | Dt | Kt | Summa | Izoh |
|---|---|---|---|---|
| Kamomad, javobgar shaxs ko'rsatilgan | 4730 | inv_acct (2910/2920) | Balans tannarxi (FIFO/AVECO) | S1 §154-14; xodim analitikasi |
| Kamomad, javobgar shaxs ko'rsatilmagan | 5910 | inv_acct | Balans tannarxi | S1 §154-11; BHMS 4 §92 |
| 5910 ni yopish (keyinroq, rahbar qarori) | 9430 **yoki** 4730 | 5910 | Qaror summasi | S1 §247, §249-3/4; alohida `ledger_adjustments` (2.23) yoki `stock_counts.resolve` (D) |
| Ortiqcha | inv_acct | **9390** | Joriy qiymat: MVP'da mahsulotning oxirgi kirim narxi (`last_purchase_cost`, yo'q bo'lsa `avg_cost`) — *interim taxmin*, BHMS 4 §32 "joriy qiymat"ga yaqinlashish | S1 §154-7, §405-14 |

- `13` §2.19 (smena farqi) almashtiriladi: kamomad `Dt 4730 / Kt 5010` (kassir analitikasi, S1 §223-20); ortiqcha `Dt 5010 / Kt 9390` (S1 §404, S8). Kamomad kechirilsa → `Dt 9430 / Kt 4730` (`ledger_adjustments`).
  - Soliq oqibatlari: kechirilgan summa — xodim daromadi; ortiqcha — aylanma solig'i bazasiga kiradi (S8). Bu buxgalter vazifasi.
- `13` §2.10 2-qator (ko'chirishda kam kelgan) — 5910 to'g'ri (S1 §249-1). Izohga "keyin 4730 (aybdor) yoki 9430" qo'shiladi.
- `13` §2.12 (hisobdan chiqarish): `9430` (aybdorsiz) / `4730` (aybdor) to'g'ri. `gift` uchun OQ-074 ga qarang.
- Ogohlantirish 4-band, OS4 → yopiladi.
- Eslatma — ochiq qolgan D-masala: tabiiy kamayish me'yorlari (VMQ-54 2.1.2.9 → 9410) MVP'da kuzatilmaydi; hammasi me'yordan ortiq deb hisoblanadi (eng xavfsiz).
- **Holat: YOPILDI.**

---

### OQ-070 — Shubhali/umidsiz qarz: 9430 yoki 4910

**Javob:** NSBU ikki usulni ham qo'llaydi.

**(A) Rezerv usuli (NSBU §217–221)** — rezerv **hisobot yili oxirida**, debitorlik qarzlari inventarizatsiyasi asosida, **har bir shubhali qarz bo'yicha alohida** tuziladi:
- rezerv tuzish: `Dt 9430 / Kt 4910`;
- qarzni rezerv hisobidan chiqarish: `Dt 4910 / Kt 4010`;
- keyingi yil oxirigacha ishlatilmagan rezerv: `Dt 4910 / Kt 9390`.

**(B) To'g'ridan-to'g'ri hisobdan chiqarish:** `Dt 9430 / Kt 4010`. Asos: VMQ-54 2.3.15.7 va BHMS 2 17-band (undirib bo'lmaydigan summa daromad kamayishi emas, **xarajat**).

Ilgari hisobdan chiqarilgan qarz qaytsa: `Dt 5010/5110/5710 / Kt 9390`.

Soliq qismi:
- rezerv foyda solig'ida **chegirilmaydi** — SK 315 faqat bank, NBKT va sug'urtachilarga tegishli;
- umidsiz qarz faqat SK **313** shartlarida chegiriladi: sud qarori, bankrotlik, tugatilish, vafot yoki da'vo muddati o'tgani **va** buxgalteriyada hisobdan chiqarilgan bo'lishi;
- QQS bazasini tuzatish — SK 257 3-qism + VMQ-489 (14.08.2020) Nizomi;
- aylanma solig'i to'lovchida umidsiz qarz bazani kamaytirmaydi: SK 466 ro'yxatida bunday holat yo'q.

**Dalil:**
- S1 §217: «… шубҳали қарзлари суммасига резерв ташкил қилинади ва **9430** … ҳисобварағига олиб борилади. Белгиланган муддатда қопланмаган ва тегишли кафолатлар билан таъминланмаган … дебиторлик қарзи шубҳали қарз сифатида тан олинади. Шубҳали қарзлар бўйича резерв **ҳисобот йили охирида** … дебиторлик қарзларининг инвентаризацияси натижалари асосида ташкил этилади.»
- S1 §218: «Резерв ҳажми **ҳар бир шубҳали қарз бўйича алоҳида**, қарздорнинг молиявий аҳволи … баҳолаш асосида аниқланади. Агар … резерв ташкил этилган йилдан кейинги йилнинг охиригача … ишлатилмаса, ишлатилмаган сумма … фойдасига қўшилади.»
- S1 §219, §221 jadvali: «9430 / 4910», «4910 / 4010, 4020», «4910 / 9390».
- S1 §405 11-qator: «Олдин ҳисобдан чиқарилган дебиторлик қарзларидан олинган даромадлар — Олинадиган ҳисобварақлар / **9390**».
- VMQ-54 2.3.15.6 «Отчисления в резерв по сомнительным долгам» va 2.3.15.7 «Убытки от списания дебиторской задолженности, по которой срок исковой давности истек и других долгов, не реальных для взыскания…» — ikkalasi ham "boshqa operatsion xarajatlar".
- S3 (BHMS 2) 17-band: «Даромадга киритилган суммани ундириш хусусида ноаниқлик вужудга келган тақдирда, қайтарилмаган сумма … дастлаб тан олинган даромад миқдорининг ўзгартирилиши сифатида эмас, балки **харажат сифатида** тан олинади.»
- S5 SK 313: «безнадежным признается долг, который не может быть погашен вследствие прекращения обязательства по решению суда, признания должника банкротом, ликвидации, смерти должника или вследствие истечения срока исковой давности … Вычет … допускается только в случае, если задолженность списана и отражена в бухгалтерской отчетности».
- SK 315 (rus. tahriri, O'RQ-1058): «Банки и небанковские кредитные организации, а также страховые организации создают резервные фонды…».
- SK 257 3-qism: «Корректировка налоговой базы … также производится в случаях, когда обязательство по оплате … признается безнадежной задолженностью … в соответствии со статьей 313».

**Ishonch:** yuqori.

**Spec'ga ta'sir:**
- `13` ogohlantirish 5-band: "NSBU №19 bo'yicha alohida zahira" → **"NSBU №21 Yo'riqnoma §217–221"** (BHMS 19 — inventarizatsiya standarti; havola noto'g'ri edi).
- `13` §2.15 jadvali:

  | # | Dt | Kt | Summa | Shart |
  |---|---|---|---|---|
  | 1a | 9430 | 4010 | Kechirilgan summa | `account_choice='direct'` (standart) |
  | 1b | 4910 | 4010 | Kechirilgan summa | `account_choice='reserve'`; server tekshiradi: shu kontragent bo'yicha 4910 qoldig'i ≥ summa |

- **Yangi §2.15a "Shubhali qarz rezervi" (yil oxiri, qo'lda):**

  | # | Dt | Kt | Summa |
  |---|---|---|---|
  | 1 | 9430 | 4910 | Buxgalter bahosi, har kontragent/hujjat bo'yicha (`analytics.counterparty_id`, `doc_id`) |
  | 2 (keyingi yil oxirida ishlatilmagan qism) | 4910 | 9390 | Qoldiq |

  MVP'da bu `ledger_adjustments` (2.23) orqali bajariladi. Alohida hujjat — MVP'dan keyin (D).
- **Yangi qoida — hisobdan chiqarilgan qarz bo'yicha to'lov:** `debt_payments` kelsa va qarz `debt_writeoffs` bilan yopilgan bo'lsa → `Dt 5010/5710/5110 / Kt 9390` (4010 emas). `debt_moves` da `direction=receivable` qayta ochilmaydi.
- `debt_writeoffs` ga ixtiyoriy maydon `tax_writeoff_basis` (`court`/`bankruptcy`/`liquidation`/`death`/`limitation`/`none`) — SK 313 bo'yicha chegirilishini buxgalter belgilashi uchun (kodda faqat hisobotga chiqadi).
- `01` #23 (#9) va 26 dagi tegishli band → yopiladi.
- **Holat: YOPILDI.**

---

### OQ-071 — Boshlang'ich qoldiqlar uchun qarshi hisob (8720?)

**Javob:** NSBU rejasida boshlang'ich qoldiqlar uchun maxsus hisob **yo'q**. 8720 ham bu maqsad uchun mo'ljallanmagan: u «Jamg'arilgan foyda», faqat 8710 dan o'tkazma va dividendlar bilan ishlaydi (§363–365). Boshlang'ich tovar va qarzni 8720 ga yozish kapitalni buzib ko'rsatadi. Masalan, MChJ'da ta'sischi kiritgan tovar aslida 4610/8330, yetkazib beruvchiga qarz esa majburiyat.

1C (UZ) amaliyotida NSBU'dan tashqari **yordamchi hisob "000"** ishlatiladi. Barcha qoldiqlar kiritilgach u **nolga teng bo'lishi shart**; nol bo'lmasa, qoldiqlar noto'g'ri kiritilgan.

**Tavsiya (D, dalil bilan):** texnik hisob **`0000` "Boshlang'ich qoldiqlar (yordamchi, NSBU'dan tashqari)"** kiritiladi.

**Dalil:**
- S1 1-ILOVA — 0000/000 kodi yo'q (to'liq ro'yxat tekshirildi).
- S1 §364: «… Ҳисобот давридаги тақсимланмаган фойдани тақсимлашдан кейин қолган сумма 8710 … ҳисобварағидан **8720 «Жамғарилган фойда (қопланмаган зарар)лар»** ҳисобварағига ўтказилади.»
- S1 §365 jadvali — 8720 faqat 8710 va 6610 bilan korrespondensiyada.
- S13 (fmc.uz, 1C yo'riqnomasi): «В качестве корреспондирующего счета используется **вспомогательный — 000** … Если в отчете присутствует вспомогательный счет 000, значит остатки введены неверно (баланс не сходится).»

**Ishonch:** yuqori ("8720 noto'g'ri"); o'rta-yuqori ("0000 yechimi" — keng tarqalgan 1C amaliyoti, normativ hujjat emas).

**Spec'ga ta'sir:**
- `13` §1 ga qator: `0000 | Boshlang'ich qoldiqlar (yordamchi) | Texnik (NSBU'dan tashqari) | hujjat | 1C amaliyoti (S13); nolga yopilishi shart`.
- §2.13:

  | Yo'nalish | Dt | Kt | Summa |
  |---|---|---|---|
  | Mijoz bizga qarzdor | 4010 | **0000** | Boshlang'ich summa |
  | Biz yetkazib beruvchiga qarzdor | **0000** | 6010 | Boshlang'ich summa |

- §2.21: `Dt inv_acct / Kt 0000`.
- `debt_openings`/`stock_openings` uchun `entry_date` = joriy ishlash boshlanishidan oldingi kun (S13: «последним днем предыдущего периода»). **D-qaror (taklif):** `tenants.go_live_date − 1`.
- **Yangi §5.5 "Boshlang'ich balansni yopish":** buxgalter qolgan balans moddalarini kiritadi — kassa 5010, bank 5110, kapital 8330/8720, boshqa majburiyatlar. Buning uchun `ledger_adjustments` (2.23) `0000` bilan ishlatiladi. Balans hisoboti (US-M11) `0000 ≠ 0` bo'lsa ogohlantirish ko'rsatadi: "Boshlang'ich qoldiqlar to'liq kiritilmagan". `period_closings` birinchi oyni `0000 ≠ 0` holatida yopishni bloklamaydi, faqat ogohlantiradi (MVP — D).
- 1C eksportida 0000 → 1C'ning "000" ga map qilinadi (`research_notes/1c-integratsiya/03` xaritasiga qator).
- Ogohlantirish 7, 12-bandlar, OS5 → yopiladi. Migratsiya — append-only seed, qayta yozish yo'q.
- **Holat: YOPILDI** (tavsiya + dalil). Buxgalter `0000` ni yopish sxemasini o'zi bajaradi.

---

### OQ-073 — "Egasi oldi", inkasso, smena farqi

**Javob:**

**Inkasso — YOPILDI.** `Dt 5710 / Kt 5010` (inkassatorga berildi). Bankka tushganda `Dt 5110 / Kt 5710`. Farq: kamomad `Dt 5910 / Kt 5710` (keyin 4730 yoki 9430), ortiqcha `Dt 5710 / Kt 9390`. Inkasso xizmati komissiyasi — **9410** (OQ-068).

**Karta/QR tushumini 5710 ga yozish (qaror #42) — tasdiqlandi.** §237 5710 ga "pul o'tkazish orqali mahsulot sotishdan olingan daromad"ni aniq kiritadi. Muqobil: `Dt 4010 / Kt 9020`, keyin `Dt 5710 / Kt 4010` (§239 2-qator). Ikkalasi ham qonuniy. Spec varianti soddaroq.

**Smena farqi — YOPILDI:** OQ-069 dagi kassa qoidasi (`4730` / `9390`).

**"Egasi oldi" — QISMAN.** NSBU'da "egasi bilan hisob-kitob" yoki "shaxsiy olish" hisobi **yo'q**. Yechim huquqiy shaklga bog'liq:

- **MChJ / AJ:** ta'sischiga pul faqat ma'lum yo'llar bilan beriladi:
  - dividend: `8710/8720 → 6610`, keyin `Dt 6610 / Kt 5010`; manbada soliq `Dt 6610 / Kt 6410`;
  - qarz yoki boshqa debitorlik: **4890** (ta'sischi xodim bo'lsa 4720/4790);
  - hisobdor summa: 4220–4290.

  Dividend qarori hali yo'q bo'lsa, kassadan olingan summa **debitorlik (4890)** bo'lib turadi. Keyin dividend e'lon qilinganda `Dt 6610 / Kt 4890` bilan yopiladi.
- **Xususiy korxona (XK):** SK 41-modda — egasiga foydadan to'lov **dividendga tenglashtiriladi**. Sxema MChJ bilan bir xil (4890 → 6610).
- **YaTT:** «Buxgalteriya hisobi to'g'risida»gi Qonun 6-moddasiga ko'ra YaTT buxgalteriya hisobining subyekti emas, hisobni «qonunchilikda belgilangan tartibda» yuritadi. Demak ERP ledgeri YaTT uchun **boshqaruv hisobi**. U yerda egasining olishi kapital kamayishi sifatida 8720 ga yozilishi mumkin. Bu qonun buzilishi emas, lekin NSBU hisoboti ham emas.

**Dalil:**
- S1 §238: «5710 … ҳисобварағида сақлаш жойидан чиқиб кетган, аммо мўлжалланган жойига етиб бормаган пул маблағлари (**инкассаторга берилган сотишдан олинган тушумлар**, пул ўтказмалари) ҳисобга олинади. Ушбу ҳисобварақ **транзит** ҳисобварақ…»
- S1 §237: «Йўлдаги пул маблағлари (**нақд пулга ва пул ўтказиш орқали маҳсулот сотишдан олинган даромад**) тўғрисидаги ахборотларни умумлаштириш 5710 … ҳисобварағида амалга оширилади.»
- S1 §239 jadvali:
  - 1-qator «Кассадаги нақд пуллар … инкассаторга топширилиши — **5710 / 5010, 5020**»;
  - 2-qator «Келиб тушган пул ўтказмалари бўйича харидорларнинг қарзлари қопланиши — 5710 / 4010»;
  - 7-qator «… банкдаги ҳисоб-китоб ҳисобварағига келиб тушиши — **5110 / 5710**».
- S8 — inkasso, kamomad va ortiqcha bo'yicha to'liq provodkalar jadvali (yuqorida, OQ-069).
- S15 — 1C BP UZ va bss.uz: karta tushumi `5710/5711` subhisobida.
- S1 §198, §285 jadvallari — ta'sischilar bilan faqat 4610 (ustav kapitali), 6610 (dividend), 6620/6630 (chiqish/ko'paytirish) orqali ishlanadi. "Shaxsiy olish" uchun hisob yo'q.
- S1 §215: «4890 «Бошқа дебиторлик қарзлар» ҳисобварағида юқоридаги ҳисобварақларда кўрсатилмаган жорий ҳисоб-китоблар ҳисобга олинади. Аналитик ҳисоб ҳар бир дебитор бўйича алоҳида юритилади.»
- S5 SK 41-modda 4-qism (O'RQ-1126, 29.06.2026 dan): «к дивидендам приравниваются доходы, выплачиваемые **собственнику частного предприятия** … из остающейся в распоряжении таких юридических лиц суммы прибыли».
- S7 6-modda: «Лица, занимающиеся предпринимательской деятельностью без образования юридического лица … ведут учет и представляют отчетность в порядке, установленном законодательством.»

**Ishonch:** yuqori (inkasso, smena); o'rta ("Egasi oldi" — huquqiy shaklga bog'liq talqin; soliq oqibati dividend solig'i, buxgalter va yurist ishi).

**Spec'ga ta'sir:**
- `13` §2.18 jadvali:

  | Sabab | Dt | Kt | Izoh |
  |---|---|---|---|
  | Inkasso | 5710 | 5010 | S1 §239-1 (o'zgarishsiz, endi manbali) |
  | Pul qo'yish (bankdan) | 5010 | 5110 | o'zgarishsiz |
  | Egasi oldi — `tenants.legal_form ∈ {llc, jsc, private_enterprise}` | **4890** | 5010 | analitika `counterparty_id` = ta'sischi (yangi `counterparties.kind='founder'`); keyin dividend e'lon qilinsa `Dt 6610 / Kt 4890` (`ledger_adjustments`) |
  | Egasi oldi — `legal_form = sole_proprietor` (YaTT) | 8720 | 5010 | Boshqaruv hisobi (YaTT — NSBU subyekti emas, S7 6-m.) |

  `owner_withdrawal_account` tenant sozlamasi saqlanadi (`research_notes/1c-integratsiya/03` `map(value)` bilan mos). Standarti yuqoridagi `legal_form` qoidasidan olinadi.
- §2.18a: inkassa farqlari uchun `bank_settlements` ga ixtiyoriy `variance_amount` maydoni: kamomad `Dt 5910 / Kt 5710`, ortiqcha `Dt 5710 / Kt 9390` (S8). D-qaror — MVP'da `ledger_adjustments` bilan ham bajarsa bo'ladi.
- `13` ogohlantirish 6-band (5710 qismi) → "S1 §237–239 bilan tasdiqlandi"; komissiya qismi → OQ-068.
- `01` #42 dagi "buxgalter tasdig'ini kutadi" → 5710 qismi uchun "S1 §237–239" havolasi.
- `13` OS8 → "huquqiy shaklga qarab" yangilanadi.
- **Holat: QISMAN.** Interim: yuqoridagi `legal_form` qoidasi. Buxgalter quyidagilarni tasdiqlaydi: MChJ uchun 4890 → 6610 sxemasini va dividend solig'i ushlanishini (bu ERP'dan tashqarida, buxgalterda); YaTT uchun 8720 ni boshqaruv hisobi sifatida.

---

### OQ-074 — Chegirma, "2+1", tekin olingan/berilgan tovar — QQS va hisob

**Javob:**

**1. Chek chegirmasi (MVP) — YOPILDI.**
- QQS bazasi — chegirmadan **keyingi** narx (SK 248 2-qism). Keyinroq berilgan chegirma — SK 257 4-band bilan tuzatish.
- Hisobda ikki to'g'ri variant bor:
  - (a) 9020 ga sof (chegirmali) summa;
  - (b) 9020 ga brutto narx, chegirma `Dt 9050` (§382, §383 9-qator).
- Tavsiya — **(b)**: 9050 rejada maxsus shu uchun bor, P&L'da chegirma ko'rinadi. QQS baribir chegirmali summadan hisoblanadi.

**2. "2+1" (US-M03-02, MVP'dan keyin) — QISMAN.** Tavsiya: "2+1" ni **3 birlikka taqsimlangan chegirma** deb modellashtirish (har qator narxi × 2/3, `9050` ga). Shunda hech qaysi birlik "tekin" bo'lmaydi va QQS bazasi haqiqiy to'langan summa bo'ladi (SK 248 2-qism). Amaliyotda esa ba'zi korxonalar "N+1" ni ESF'da tekin birlik sifatida rasmiylashtiradi (S11). Xavf: **import tovarlarida** QQS bazasi import QQS bazasidan past bo'lishi mumkin emas (SK 248 5-qism, S12). Chegirma bu chegaradan pastga tushirsa — farqga QQS qo'shimcha hisoblanadi.

**3. Tekin berilgan tovar (`write_offs.reason='gift'`) — QISMAN.**
- **Iqtisodiy asoslangan** (reklama aksiyasi, buyruq bilan, hujjatlashtirilgan): QQS obyekti emas (SK 239 1-qism 2-band, 3-qism). Kiruvchi QQS hisobga olinaveradi (S9). Provodka `Dt 9410 / Kt inv_acct` — reklama, VMQ-54 2.1.2.8.
- **Asoslanmagan:** QQS **bozor qiymatidan** hisoblanadi (SK 248 3-qism 2-band, VMQ-489 3-ilova). Provodka: `Dt 9430 / Kt inv_acct` (tannarx; NSBU'da tekin berish 9430 ga: §141 16-qator «Тайёр маҳсулотларнинг текинга берилиши — 9430 / 2810») + `Dt 9430 / Kt 6410` (QQS) + `vat_moves(kind=output, base=bozor qiymati)`.

**4. Tekin olingan tovar.**
- `Dt inv_acct / Kt 8530` (§154 6-qator «Текинга олинган товарларни кирим қилиш — 2910-2990 / 8530»), bozor qiymatida.
- Soliqda — daromad (SK 299, bozor qiymati). Aylanma solig'i to'lovchida jami daromadga kiradi (SK 463).
- **Yetkazib beruvchining bir fakturadagi "bonus" birliklari** tekin olish emas. Bu narx chegirmasi: partiya tannarxi = faktura summasi / umumiy miqdor (BHMS 4 — tannarx haqiqiy xarid qiymati). Provodka oddiy 2.6.

**Dalil:**
- S5 SK 248 2-qism (rasmiy o'zbekcha): «Харидорларга реализация қилиш бўйича айланмани амалга ошириш санасида чегирмалар (бошқа тижорат бонуслари) берган солиқ тўловчи солиқ базасини бундай чегирмалар (тижорат бонуслари) **чегириб ташланган ҳолдаги нархдан** … аниқлайди.»
- SK 248 3-qism: «Налоговая база определяется исходя из рыночной стоимости … при: … 2) безвозмездной передаче товаров (услуг), если иное не предусмотрено пунктом 2 части первой или пунктом 2 части второй статьи 239».
- SK 248 5-qism: «При реализации ввезенных (импортированных) … товаров налоговая база не может быть ниже стоимости, от которой исчислен налог, фактически уплаченный в бюджет при ввозе».
- SK 239: «Оборотом по реализации товаров является: … 2) безвозмездная передача товара, **за исключением случаев, когда такая передача является экономически оправданной**» + 3-qism shartlari (daromad olishga yo'naltirilgan; faoliyatni saqlash/rivojlantirish uchun zarur; qonundan kelib chiqadi).
- SK 257 1-qism 4-band: «предоставления скидки продавцом … уменьшает налоговую базу по ранее совершенной поставке…, если условия предоставления скидки предусмотрены условиями договора или ценовой (тарифной) политикой налогоплательщика».
- SK 466 (aylanma solig'i): «Доходы подлежат корректировке в случаях: … 3) изменения цены, использования скидки покупателем».
- S1 §382: «9050 … шартнома шартларига мувофиқ берилган **сотув чегирмалари** … ни ҳисобга олиш учун фойдаланилади … контр-пассив … унинг дебет айланмаси … даромадларни камайтиради»; §383 9-qator «Сотишдан ва нархдан чегирмалар бериш — 9050 / 4010».
- S9 (GNK): «Если безвозмездная передача товаров экономически оправдана, товары передаются без НДС … При этом «входящий» НДС вы вправе взять в зачет … Экономически неоправданная безвозмездная передача — это оборот по реализации товаров, облагаемый НДС. Налоговая база определяется исходя из рыночной стоимости». Yana: «… порядок проведения рекламной акции — закрепите приказом или другим локальным актом».
- S10 (MF): «… раздает покупателям образцы … Такая передача — экономически оправдана … объект обложения НДС в данной ситуации не возникает».
- S11 (amaliyot): «Организация проводит акцию 5+1 … 1 единицу отдаем бесплатно, что и отражается в ЭСФ … налоговая база НДС при реализации импортного товара не может быть меньше…».

**Ishonch:** yuqori (chek chegirmasi va QQS bazasi); o'rta ("2+1" modeli va sovg'ani "iqtisodiy asoslangan" deb tasniflash — soliq organi bahosiga bog'liq).

**Spec'ga ta'sir:**
- `13` §2.1–2.4 ga "chegirmali chek" qatori (tenant sozlamasi `discount_posting = 'gross_9050'`, standart):

  | # | Dt | Kt | Summa |
  |---|---|---|---|
  | 1 | 5010/5710/4010 | 9020 | Ro'yxat narxi − shu narxdagi QQS (brutto sof daromad) |
  | 1a | 9050 | 5010/5710/4010 | Chegirma − chegirmaga to'g'ri keladigan QQS |
  | 2 | 5010/5710/4010 | 6410 | QQS **chegirmali** summadan (qator-qator) |

  Natija `Dt pul = to'langan summa`. `vat_moves.base_amount` = chegirmali baza. `discount_posting='net'` bo'lsa, 1a qatori yo'q va 9020 = chegirmali sof summa.
- §4.3 (aylanma solig'i) formulasi: "9020 − 9040 − 9050" — allaqachon to'g'ri; SK 466 havolasi qo'shiladi.
- §2.12 `gift`: `write_offs.gift_kind ∈ {promo_justified, other}`:
  - `promo_justified` → `Dt 9410 / Kt inv_acct`, QQS yo'q, `promo_order_ref` majburiy;
  - `other` → `Dt 9430 / Kt inv_acct` + `Dt 9430 / Kt 6410` (QQS = bozor qiymati × stavka/100; MVP'da bozor qiymati = joriy chakana narx QQSsiz — *interim*) + `vat_moves(kind=output)`.
- Yangi qator (MVP'dan keyin, US-M03-02): "2+1" — chegirma sifatida taqsimlash; import tovarlarida minimum bazani tekshirish (`customs_vat_base` mavjud bo'lsa) — ogohlantirish.
- Tekin olingan tovar (2.6 ning varianti, `goods_receipts.kind='gratuitous'`): `Dt inv_acct / Kt 8530` bozor qiymatida; QQS yo'q.
- Ogohlantirish 11-band → "chegirma qismi yopildi; 2+1 va sovg'a — interim, buxgalter/soliq maslahatchisi tasdiqlaydi".
- **Holat: QISMAN.**
  - Interim: chegirma `gross_9050`; sovg'a standart `other` (QQS bilan — eng xavfsiz); `promo_justified` faqat buyruq raqami bilan.
  - Tasdiqlovchi: buxgalter / soliq maslahatchisi (bloklamaydi).
  - Diqqat: SK 239 ga **12.12.2026 dan kuchga kiradigan o'zgartirish** bor (lex.uz: «Cмотрите на изменения, вступающие в силу с 12 декабря 2026 года» — "iqtisodiy asoslangan" shartlari bandida). Matni bu tadqiqotda ochilmadi, chiqqach qayta tekshirilsin.

---

## 4. P7 doirasidagi qo'shimcha topilmalar (spec nomuvofiqliklari)

### 4.1 Nasiyada daromad/QQS tan olish vaqti (`01` #30/#42, `13` §2.14, `04` BP-03 6-qadam, BP-11 4-qadam)

**Javob:** daromad (9020) va QQS (6410) **sotuv kuni** tan olinadi. Bu qonundan kelib chiqadi; buxgalter tanlaydigan variant emas.

**Dalil:**
- S3 (BHMS 2) 16-band: «Товарларни сотишдан даромад қуйидаги шартлар бажарилганда тан олинади: товарларга эгалик қилишнинг хатар ва афзалликларининг катта қисми харидорга ўтганида; … назорат қилиш самарадорлигини йўқотганида; даромад суммасини … баҳолаш мумкин бўлганда; … иқтисодий наф олиши эҳтимоли мавжуд бўлганда…».
- SK 242 (rasmiy o'zbekcha): «… ҳисобварақ-фактура тақдим этилган сана ёки **товарлар жўнатилган (берилган) сана**, агар ушбу сана ҳисобварақ-фактура тақдим этилган санадан олдин келса, товарларни реализация қилиш бўйича айланма амалга оширилган санадир».
- SK 78: «… налогоплательщик … ведет учет в целях налогообложения … **по методу начисления**».
- SK 239 1-qism 4-band: «передача товара **на условиях рассрочки платежа**» — bu ham realizatsiya.

**Ta'sir:**
- `13` §2.14 "interim qoida" → "qoida (BHMS 2 §16, SK 242, 78)".
- "Agar buxgalter kassa usulini tanlasa…" jumlasi **olib tashlanadi**. `FiscalPolicy` bayrog'i faqat **fiskal chek** vaqtini boshqaradi (qaror #30), provodka va QQS vaqtini emas.
- `13` OS7, `01` #30 "⚠ Ochiq: daromad/QQS tan olish vaqti", `01` #42 ning 2-jumlasi, `04` BP-03 6-qadam va BP-11 4-qadamdagi "⚠ buxgalter/yurist tasdig'i kutilmoqda" — tan olish vaqti qismi yopiladi.
- Ochiq qoladi (P1 doirasi): fiskal chekni to'lov kunida chiqarishning OFD/virtual kassa qoidalariga mosligi. Bu `00-inventar` OQ-101 ning 4-nomuvofiqligini ham yopadi (BP-03 "tan olinmaydi" matni noto'g'ri; to'g'risi — sotuv kuni).
- Eslatma: BHMS 2 13-band (uzoq kechiktirilgan to'lovda diskontlash) — do'kon nasiyasi qisqa muddatli, ahamiyatsiz. MVP'da qo'llanmaydi.

### 4.2 Davr yopishda 9040/9050

S1 §383 10–12-qatorlari:
- «Ҳисобот даврининг охирида 9040 … ёпилиши — **9010, 9020 / 9040**»;
- «… 9050 … ёпилиши — 9010, 9020, 9030 / 9050»;
- so'ng «9010, 9020 … / 9910».

`13` §5.1 diagrammasi va matni 9040/9050 ni to'g'ridan-to'g'ri 9910 ga yopadi. To'g'risi: `9040, 9050 → 9020`, keyin `9020 → 9910`. Yakuniy natija bir xil, lekin 1C/NSBU bilan solishtirishda farq ko'rinadi.

### 4.3 Aylanma solig'i provodkasi (`13` §4.3 da yo'q)

S1 §275 1-qator: «Давр харажатларига тааллуқли хар хил ажратмалар, солиқлар ва йиғимлар бўйича бюджетга қарзлар — **9430 / 6410**».

Taklif (interim, buxgalter tasdiqlaydi; muqobil — 9820 «Фойдадан ҳисобланган бошқа солиқ мажбуриятлари бўйича харажатлар»):

| # | Dt | Kt | Summa | Analitika |
|---|---|---|---|---|
| 1 | 9430 | 6410 | Oylik aylanma solig'i | `tax_type=turnover` |

### 4.4 Qaytarish (`13` §2.5)

S1 §381 bilan to'liq mos (9040 / pul yoki 4010; 6410 / pul; tovar / 9120). O'zgarish kerak emas — faqat manba havolasi qo'shiladi.

### 4.5 Filiallararo 2970

S1 §151: «2970 … ҳисобот даври охирида йўлда қолган (омборга келиб тушмаган) товарлар ҳисобга олинади». Bitta yuridik shaxs ichidagi ko'chirishda tranzit hisob sifatida ishlatish — **talqin**, lekin mos. MChJ ichida 4110/6110 ("ajratilgan bo'linmalar") faqat alohida balansli filiallar uchun. MVP modelida bitta tenant = bitta balans (qaror #31), shuning uchun 2970 qoladi.

### 4.6 Yaxlitlash

NSBU, BHMS 2 va BHMS 21 da QQSni qator bo'yicha yaxlitlash qoidasi **yo'q**. `13` OS2 — P1 (OFD/soliq.uz) doirasida qoladi.

### 4.7 Rasmiy matndagi texnik xato

S1 §149 «9490 «Бошқа операцион харажатлар»» deb yozadi, lekin rejada 9490 yo'q (to'g'risi 9430). Bizga ta'siri yo'q, faqat qayd uchun.

---

## 5. Buxgalterga qisqa tasdiq ro'yxati (bloklamaydi)

1. 2920 ni do'kon savdo zali omborlari uchun standart qilish (§146) — rozimi?
2. Click/Payme/Uzum komissiyasi 9430 (bank xizmatiga o'xshatma) yoki 9410 (VMQ-54 2.1.2.18 "kassa xo'jaligi").
3. Ortiqchani baholash: `last_purchase_cost` "joriy qiymat" (BHMS 4 §32) o'rnida yetarlimi?
4. MChJ/XK "Egasi oldi" → 4890 → 6610 sxemasi; dividend solig'ini ushlash buxgalterda.
5. "2+1" — chegirma sifatida taqsimlash; sovg'a standarti — QQS bilan (`other`).
6. Aylanma solig'i: 9430 yoki 9820.
7. `0000` ni boshlang'ich balansni yopish uchun ishlatish tartibi.
