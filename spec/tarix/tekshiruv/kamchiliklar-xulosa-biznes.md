# Kamchiliklar-tahlili auditi: Asosiy xulosalar, arxitektura, biznes

*2026-10-15 · Tekshiruv manbai: `spec/tarix/kamchiliklar-tahlili.md` (Asosiy xulosalar, 8. Arxitektura hujjatlari, 9. Biznes, Keyingi qadamlar)*

---

## (A) Asosiy xulosalar — 9 band (lines 5–18)

| # | Band (qisqa) | 08-dagi belgi | Haqiqiy holat | Dalil | Nima qoldi / kim yopadi |
|---|---|---|---|---|---|
| 1 | Arxitektura hujjatlari 00–11 yozilgan | ✅ HAL QILINGAN | HAL QILINGAN | spec/kod-uchun/: 00-umumiy, 01-malumotlar-modeli, 02-provodka-qoidalari, 03-integratsiyalar, 04-offline-sync, 05-xavfsizlik-va-audit, 06-nofunksional-talablar, 07-ai-qatlami, 08-frontend, 09-backend, 10-android, 11-backlog, 12-autentifikatsiya — 13 ta fayl yozildi | — |
| 2 | 2026-10-14 tekshiruv natijalari kod-uchun/dagi 4 faylga kiritildi (5 ish kuni → 5 taqvim kuni, soliq kodeksi 81-modda) | ✅ HAL QILINGAN | HAL QILINGAN | 02-rollar-va-ssenariylar.md, 03-modullar-talablari.md (M10), 04-biznes-jarayonlar.md (BP-08), 06-ekranlar-umumiy.md (BO-10) — qo'shilgan; tuzatishlar-va-yechimlar.md row 1 | Qoldi: e'tiroz/tuzatish yuborish kanali (07-tuzatishlar #1 "Qolgani: e'tiroz/tuzatish yuborish kanali (band 31)"); kim yopadi: Mahsulot (my.soliq.uz bilan aniqlashtirish) |
| 3 | FIFO/AVECO baholash usuli tanlanmagan (→ US-M04-05) | ✅ HAL QILINGAN | HAL QILINGAN | tuzatishlar-va-yechimlar.md #9: "Foydalanuvchi qarori (2026-10-14): FIFO va o'rtacha narx (AVECO) ikkalasi ham"; 03-modullar-talablari.md US-M04-05 | — |
| 4 | To'liq NSBU №21 hisob rejasi spec/research'da yo'q | QISMAN | QISMAN | 13-provodka-qoidalari.md mavjud, lekin ogohlantirish: "Bu hujjatdagi hisob raqamlari...lex.uz'dagi 191-son buyruq...to'liq rasmiy matnidan emas, balki...ikkinchi darajali huquqiy ma'lumot bazalari (nrm.uz, buxgalter.uz) orqali qisman o'qildi" | Qoldi: (1) to'liq rasmiy ro'yxat lex.uz #7282759 Ilova 1-2 bilan solishtirish, (2) hisoblar #4410, #5910, #6410 tasdig'i; Kim yopadi: Buxgalter (rasmiy manbaning to'liq nusxasi bilan tekshirish) |
| 5 | Har bir davlat integratsiyasi uchun sandbox/test muhiti topilmagan | QISMAN | QISMAN | 21-integratsiyalar.md §1: "Faqat 3 tizimda to'liq ochiq...API: Faktura.uz, Payme, E-IMZO"; "Qolgan 9 tasida hujjat yopiq, login talab qiladi yoki umuman topilmadi" | Qoldi: OFD, CRPT Turon, Didox/Faktura.uz, my.soliq.uz, Vakolat.uz, Click, Uzum sandbox mavjudligini tekshirish; Kim yopadi: Rasmiy murojaat (Mahsulot/Teknik) |
| 6 | Nofunksional talablar (tezlik, sig'im, uptime) deyarli "taxmin" | QISMAN | QISMAN | 25-nofunksional-talablar.md §1: "Barcha tezlik/sig'im ko'rsatkichlari...manbada raqam bilan tasdiqlanmagan — hammasi `taxmin`"; faqat 3 ta qonuniy raqam (48 soat OFD, 72 soat markirovka, 5 kun davlat hisoboti) manbali | Qoldi: (1) ichki SLO jadval e'lon qilish (hatto "taxmin" qiymatlar bilan), (2) sig'im rejasi aniqlash (100→1000 tenant), (3) tarozi protokoli tekshiruvi; Kim yopadi: Arxitektura (ichki SLO) |
| 7 | AI uchun eval-dataset, aniqlik chegarasi, xarajat limiti umuman yo'q | OCHIQ | OCHIQ | 22-ai-qatlami.md §7 (Asosiy xulosalar): "Baholash o'zbek tili uchun rasmiy benchmark yo'qligi"; band 59 (jadval): "eval-dataset...minimal aniqlik chegarasi hech qayerda belgilanmagan"; band 8 (Asosiy xulosalar): "Tenant oylik token budjeti tarifga bog'liq" lekin "aniq raqam pilotda tasdiqlanishi shart (barcha hajm/token taxminlari **taxmin**, manbada yo'q)" | Qoldi: (1) AI-03 OCR minimal aniqlik chegarasi, (2) AI eval test to'plami (50–100 holatli), (3) tenant rate-limit siyosati; Kim yopadi: Mahsulot+AI jamoasi (MVP oldidan) |
| 8 | Narx qarori qabul qilindi (49k/129k/249k, 2026-10-14); unit-iqtisod hisobi qoldi | QISMAN | QISMAN | 05-mvp-chegarasi.md §3.3: "Taklif: Start 49k / Biznes 129k / Pro 249k"; lekin 25-nofunksional-talablar.md §1.8: "unit-iqtisod hisobi — hisoblanadi, lekin to'liq taxmin zanjiri"; "SMS narxi taxmin — pilot ma'lumoti bilan tasdiqlanmaguncha sotuv narxlari yakuniy emas" | Qoldi: (1) hosting xarajati hisob-kitobi (UzCloud narxiga +'taxmin sig'im), (2) AI xarajati (token hajmiga bog'liq, "taxmin"), (3) SMS narxi (manbada yo'q); Kim yopadi: Moliya/Arquitektura (tenant-boshiga xarajat modeli) |
| 9 | 61 ta kamchilik P0/P1/P2 bo'yicha ro'yxatlangan | HAL QILINGAN | HAL QILINGAN | Jadvallari kamchiliklar-tahlili.md, 7 bo'lim (Domen/ma'lumotlar, Buxgalteriya, Soliq integratsiya, Offline-POS, Multi-tenancy/xavfsizlik, Nofunksional, AI) | — |

**Natijalari band (A)**: 3 HAL QILINGAN + 4 QISMAN + 2 OCHIQ

---

## (B) Arxitektura hujjatlari (lines 129–141) — 8 fayl + qo'shimchalar

| # | Hujjat | 08-dagi belgi | Faylning holati | Tayyor miqdori | Nima qoldi / kim yopadi |
|---|---|---|---|---|---|
| 1 | `11-malumotlar-modeli.md` — ER, jadvallar, ID, holatlar | ✅ Hal qilindi (1-12 band) | **MAVJUD** | Band 1-7: §1-12 yozilgan (jadvallar §6, registrlar §7, audit §10, RLS §1, holat-mashinalari §7 bo'limidagi tafsilot) | Qoldi: §11 (status lifecycle, xaridnoma/nasiya/ko'chirish state-diagram butun tafsiloti yozilishi kerak — hozir qisman: M02/M06/M08 holatlar tilga olingan), band 3-12 jadvallarida. Manba: 11-malumotlar-modeli.md satrlar 1–100 tekshirildi |
| 2 | `13-provodka-qoidalari.md` — NSBU №21, Dt/Kt jadval, baholash | ✅ Hal qilindi (13-21 band) | **MAVJUD** | Band 13: NSBU №21 manbasi yozilgan (lekin ogohlantirish bilan); §1 (Asosiy xulosalar); §1 (Hisob rejasi MVP subset) | Qoldi: (1) To'liq rasmiy hisoblar rejasi lex.uz buxgalter tasdiqlanmagan, (2) §3 (Hujjat turi uchun Dt/Kt jadval) xaali | Manba: 13-provodka-qoidalari.md satrlar 1–50 |
| 3 | `21-integratsiyalar.md` — API kontraktlar, sandbox, xato katalogi, retry | ✅ Qisman (22-35 band, 5 tasida kirish bor) | **MAVJUD** | Band 22: Faktura.uz/Payme/E-IMZO sandbox tekshirilgan; §0-9 yozilgan (umumiy naqsh, holat-mashinasi, BO-14 talab) | Qoldi: (1) OFD/CRPT/Didox/my.soliq.uz/Vakolat.uz sandbox mavjudligini rasmiy murojaatlar bilan tekshirish, (2) har integratsiya uchun xato katalogi to'liq olmagan (§0.9, band 34 "xato kodlari katalogi to'liq emas") | Manba: 21-integratsiyalar.md satrlar 1–100+ |
| 4 | `16-offline-sync.md` — event-log, konflikt hal qilish, 48h/markirovka | ✅ Hal qilindi (36-42 band) | **MAVJUD** | Band 36: overseeling siyosati ✅ hal qilindi; band 42: markirovka audit-log spetsifikatsiyasi hal qilindi; §5–6 yozilgan | Qoldi: offline qaytarish/ko'chirish siyosati (band 25 "offline markirovka siyosati qaror qilinmagandan keyin ham...audit-log...spetsifikatsiyalanmagan") | Manba: 16-offline-sync.md mavjudligi tasdiqlandi |
| 5 | `15-xavfsizlik-va-audit.md` — RLS, audit-log, shifrlash, PCI-DSS | ✅ Hal qilindi (43-53 band, band 45 audit qisman) | **MAVJUD** | Band 45: audit-log sxemasi §6'da yozilgan; lekin band 43/45 Asosiy xulosalar qoladi | Qoldi: (1) Audit-log qonuniy minimal saqlash muddati yurist tasdig'i kerak, (2) tamper-evidence (o'zgartirib bo'lmaslik) mekanizmi spetsifikatsiyalangan lekin teknik amalashtirish — qismani | Manba: 15-xavfsizlik-va-audit.md mavjudligi tasdiqlandi |
| 6 | `25-nofunksional-talablar.md` — SLO (tezlik, sig'im), uskuna ro'yxati | ✅ Hal qilindi (54-58 band, ichki SLO taxmin) | **MAVJUD** | Band 54: ichki SLO jadval yozilgan (lekin "taxmin" deb belgilangan) | Qoldi: (1) tasdiqlangan uskuna ro'yxati (FM/chek printeri) — hali tanlov yo'q, (2) tarozi protokoli noma'lum | Manba: 25-nofunksional-talablar.md satrlar 1–100+ |
| 7 | `22-ai-qatlami.md` — eval, xarajat, monitoring | ✅ Hal qilindi (59-61 band, eval-dataset va aniqlik ochiq) | **MAVJUD** | Band 59: monitoring feedback ✅ hal qilindi (§8.4); lekin band 59: "minimal aniqlik chegarasi belgilanmagan" | Qoldi: (1) eval-dataset va aniqlik chegarasi (threshold), (2) xarajat limiti siyosati (tenant rate-limit) | Manba: 22-ai-qatlami.md satrlar 1–100+ |
| 8 | `27-backlog.md` bajarildi | ✅ Hal qilindi | **MAVJUD** | Backlog ro'yxati yozilgan; qo'shimcha: 10-umumiy-arxitektura.md, 24-frontend-arxitekturasi.md, 23-backend-arxitekturasi.md, 28-android-pos.md, 14-autentifikatsiya-oauth2.md | Qo'shimcha hujjatlar ham mavjud | Manba: spec/kod-uchun/ barcha fayllar tasdiqlandi |

**Natijalari band (B)**: 8 HAL QILINGAN (lekin har biri QISMAN/OCHIQ sub-bandlari bilan)

---

## (C) Biznes (lines 144–152) — 4 band

| # | Band (qisqa) | 08-dagi belgi | Haqiqiy holat | Dalil | Nima qoldi / kim yopadi |
|---|---|---|---|---|---|
| 1 | Narx: Start 49k/Biznes 129k/Pro 249k qaror (2026-10-14); unit-iqtisod QOLDI | Qaror qabul qilindi | QISMAN | 05-mvp-chegarasi.md §3.3 tariflar qabul qilingan; lekin 25-nofunksional-talablar.md §8: "unit-iqtisod hisobi — hisoblanadi, lekin to'liq TAXMIN zanjiri: hosting, AI, SMS"; tuzatishlar-va-yechimlar.md #7 "narx...tasdiqlanishi kerak" | Qoldi: (1) Hosting xarajati (UzCloud +taxmin sig'im), (2) AI xarajati (token hajmiga bog'liq), (3) SMS narxi (manbada yo'q); Kim yopadi: Moliya/Arkitektura |
| 2 | Onboarding jarayoni (qog'oz/Excel → AIOS, boshlang'ich ma'lumot kiritish) | Butunlay yo'q | OCHIQ | 05-mvp-chegarasi.md§1.3 jadvali "Boshqa tizimlardan ma'lumot ko'chirish konnektorlari" Won't ro'yxatida; lekin tuzatishlar-va-yechimlar.md #8 band 34 "onboarding uch yo'li aniq ko'rsatildi (qo'lda/Excel-CSV/AI foto)" — bu spec darajasida aniqlangan, lekin **onboarding jarayoni spetsifikatsiyasi** butunlay yo'q | 05-mvp-chegarasi.md wo't jadvali: "Boshqa tizimlardan ma'lumot ko'chirish konnektorlari" / 07-tuzatishlar #8: US-M04-04 yangi yo'l (3) AI-03 orqali — lekin onboarding UI/ish oqimi spec faylida yo'q | Qoldi: Excel/CSV shablon formati, qo'lda kiritish BO ekrani, AI-03 OCR qabul-radetstish oqimi, vaqt shartnomasi; Kim yopadi: Mahsulot (onboarding spetsifikatsiyasi) |
| 3 | Support modeli (kanal, SLA, ish vaqti) | Faqat "taxmin" | OCHIQ | 05-mvp-chegarasi.md §2: "Tezkor support kutilgan farqlovchi" — lekin SLA yo'q | Support SLA yo'q | Qoldi: Kanal (Chat/Email/Phone), SLA (birinchi javob vaqti, hal qilish vaqti), ish vaqti, escalation, FAQ; Kim yopadi: Biznes |
| 4 | Yuridik shaxs / litsenziya / javobgarlik (markirovka/fiskal jarima AIOS'ning shartnoma javobgarligi) | Hech qayerda muhokama qilinmagan | OCHIQ | tuzatishlar-va-yechimlar.md #23: "kassa to'liq to'xtaydi" qaror — lekin ToS (foydalanish shartnomasi) hali loyiha qilinmagan | 07-tuzatishlar row 23: "o'rniga ToS eslatmasi qo'shildi — do'kon kirish to'xtatilgan davrdagi fiskal/soliq majburiyati uchun o'zi javobgar" | Qoldi: (1) Shartnoma draftasi (ToS, SLA), (2) javobgarlik taqsimoti jadvali (dastur xatosi, davlat jarima, network uzilishi), (3) sug'urta talabi yoki minimal liability; Kim yopadi: Yurist/Biznes |

**Natijalari band (C)**: 1 QISMAN + 3 OCHIQ

---

## Keyingi qadamlar (lines 156–168) — 10 band

| # | Qadam | 08-dagi belgi | Haqiqiy holat | Status |
|---|---|---|---|---|
| 1 | `spec/kod-uchun/`dagi 4 fayl yangilash (5 ish kuni → 5 taqvim kuni, O'RQ-1108/SK 81-modda) | ✅ (bajarildi) | ✅ HAL QILINGAN | 02-rollar-va-ssenariylar.md, 03-modullar-talablari.md, 04-biznes-jarayonlar.md, 06-ekranlar-umumiy.md — tuzatildi (tuzatishlar-va-yechimlar.md #1 dalili) |
| 2 | Rasmiy murojaatlarni zudlik bilan yuborish (csec.uz, CRPT Turon, Soliq qo'mitasi, Didox/Faktura.uz — band 22-24, 29, 35) | OCHIQ | OCHIQ | Qoldi: xat shablonlari 12-taxminlar-va-murojaatlar.md'da tayyor, lekin rasmiy yuboriluvi shart; Kim yopadi: Mahsulot/Teknik |
| 3 | Huquqiy maslahat (offline markirovka, QR/Click/Payme chek javobgarligi, 48 soatdan keyin kassa holati, shartnoma javobgarligi) | OCHIQ | OCHIQ | 07-tuzatishlar #25 (markirovka — softing ruxsat), #32 (QR chek), #36 (48 soat), "Biznes" bo'limi; Kim yopadi: Yurist |
| 4 | Buxgalter/tashqi maslahatchi bilan NSBU №21 to'liq rejasi + FIFO/AVECO tanlash | OCHIQ | OCHIQ | Band 4 (Asosiy xulosalar) — to'liq hisob rejasi lex.uz bilan solishtirish; 13-provodka-qoidalari.md ogohlantirish; Kim yopadi: Buxgalter |
| 5 | Mahsulot egasi bilan huquqlar matritzasi va narx tasdiqlanishi (2026-10-14 qaror) | OCHIQ | OCHIQ | Band 43 (Jadvallar), "Biznes" birinchi qatori — "rasmiy tasdiqlash sessiyasi"; Kim yopadi: Mahsulot egasi |
| 6 | `spec/kod-uchun/` hujjatlarini yozishni boshlash | ✅ (bajarildi) | ✅ HAL QILINGAN | 13 ta hujjat yozildi (00-12); band (B) jadvali bilan solishtirish |
| 7 | Har bir davlat integratsiyasi uchun sandbox mavjudligini tekshirish | OCHIQ | OCHIQ | 21-integratsiyalar.md §1: 3 ta topilgan (Faktura, Payme, E-IMZO), 9 tasi noaniq; Kim yopadi: Mahsulot/Teknik (rasmiy murojaatlar) |
| 8 | AI eval-dataset va xarajat-limit siyosatini loyihalash | OCHIQ | OCHIQ | 22-ai-qatlami.md band 7/59 — "eval-dataset...minimal aniqlik chegarasi hech qayerda belgilanmagan"; Kim yopadi: Mahsulot+AI jamoasi |
| 9 | Ichki nofunksional maqsadlar (SLO) jadvalini e'lon qilish | QISMAN | QISMAN | 25-nofunksional-talablar.md §1.20-33 "Barcha quyidagi raqamlar — **taxmin**"; lekin jadvali mavjud; Kim yopadi: Arxitektura (tasdiqlanish) |
| 10 | Fiskal modul (FM)/chek printeri ta'minotchisini tanlash (sertifikatlash yo'li) | OCHIQ | OCHIQ | 25-nofunksional-talablar.md band 55: "uskuna ro'yxati yo'q — AIOS qaysi uskuna bilan rasman integratsiya qilishini tanlamagan"; Kim yopadi: Arxitektura+Biznes |

**Natijalari band (Keyingi qadamlar)**: 3 HAL QILINGAN + 1 QISMAN + 6 OCHIQ

---

## Umumiy hisobot

| Status | (A) Asosiy xulosalar | (B) Arxitektura | (C) Biznes | (D) Keyingi qadamlar | **Jami** |
|---|---|---|---|---|---|
| **HAL QILINGAN** | 3 | 8 | 0 | 3 | **14** |
| **QISMAN** | 4 | 8 (sub-bandlari bilan) | 1 | 1 | **14** |
| **OCHIQ** | 2 | — | 3 | 6 | **11** |
| **JAMI** | 9 | 8 | 4 | 10 | **39** |

---

## OCHIQ va QISMAN bandlar ro'yxati (kim yopadi?)

### OCHIQ bandlar (11 ta) — **qabul talabi**:

1. **E'tiroz/tuzatish yuborish kanali** (A.2) — Mahsulot (my.soliq.uz bilan aniqlashtirish, 5 taqvim kunlik muddat mexanizmi)
2. **Davlat integratsiyalari sandbox** (A.5) — Mahsulot/Teknik (rasmiy murojaat: OFD, CRPT Turon, Didox/Faktura.uz, my.soliq.uz, Vakolat.uz, Click, Uzum)
3. **AI eval-dataset va aniqlik chegarasi** (A.7) — Mahsulot+AI jamoasi (MVP oldidan, 50–100 holatli test to'plami, threshold definitsiya)
4. **Unit-iqtisod tasdig'i** (A.8 / C.1) — Moliya (xarajat modeli: hosting taxminan, AI token hajmi, SMS narxi)
5. **Onboarding spetsifikatsiyasi** (C.2) — Mahsulot (Excel/CSV shablon, qo'lda kiritish BO, AI-03 oqimi)
6. **Support SLA** (C.3) — Biznes (kanal, vaqtlar, eskalatsiya, FAQ)
7. **Yuridik shartnoma (ToS, javobgarlik)** (C.4) — Yurist/Biznes (ToS draftasi, javobgarlik jadvali, sug'urta)
8. **Rasmiy murojaatlar** (Keyingi qadamlar #2) — Mahsulot/Teknik (csec.uz, CRPT, Soliq qo'mitasi, operatorlar)
9. **Huquqiy maslahat** (Keyingi qadamlar #3) — Yurist (offline markirovka, QR chek, 48 soat kassa holati)
10. **Mahsulot egasi tasdiqlanishi** (Keyingi qadamlar #5) — Mahsulot egasi (huquqlar matritsasi, narx)
11. **FM ta'minotchisi tanlashi** (Keyingi qadamlar #10) — Arxitektura+Biznes (sertifikatlash yo'li, narx, integratsiya muddati)

### QISMAN bandlar (14 ta) — **kimdan**: 

1. **NSBU №21 to'liq rejasi** (A.4 / B.2) — Buxgalter (lex.uz #7282759 Ilova 1-2 rasmiy matn, hisoblar #4410/#5910/#6410 tasdig'i)
2. **Davlat integratsiyalari xato katalogi** (A.5 / B.3) — Mahsulot/Teknik (16 ta integratsiya uchun xato kodlari ro'yxati)
3. **Sig'im rejasi (100→1000 tenant)** (A.6 / B.6) — Arxitektura (riskli tovarlar analiz, ultramilyon tenant masshtabi)
4. **Tarozi protokoli tadqiqoti** (A.6 / B.6) — Teknik (mashhur modellar, COM/serial, GOST standartlar)
5. **Offline qaytarish/ko'chirish siyosati** (B.4) — Mahsulot/Teknik (CRPT Turon API yopiqligi sababli, huquqiy maslahat bilan)
6. **Audit-log qonuniy muddat + tamper-evidence** (B.5) — Yurist+Arkitektura (minimal saqlash muddati, o'zgartirib bo'lmaslik mekanizmi)
7. **Tasdiqlangan uskuna ro'yxati** (B.6) — Arxitektura (FM/chek printeri ta'minotchisi tanlovi bilan birga)
8. **Hujjat turi uchun Dt/Kt jadval (provodka)** (B.2) — Buxgalter (BP-01…BP-12 har biri uchun debet/kredit chuftligi)
9. **AI xarajat-limit siyosati** (A.7 / B.7) — Arkitektura (tenant rate-limit, overage siyosati)
10. **Narx-qoldiq manfiy balansi hal qilish** (B.4 — offline overselling) — Arkitektura (konflikt-resolution qoidasi, offline parallel cheklar)
11. **Markirovka offline siyosati audit-log spetsifikatsiyasi** (B.4) — Arkitektura (kim, qachon "keyinroq tekshirish" belgisi, yozuv formati)
12. **SLO jadvali e'lon qilish** (Keyingi qadamlar #9) — Arkitektura (ichki maqsad, hatto "taxmin" bo'lsa ham, rasmiy)
13. **Onboarding: Excel/CSV shablon + AI-03 oqimi** — Mahsulot (kichik detall, lekin spec kerak)
14. **Support kanal va protsedura** (C.3) — Biznes (Chat/Email/Phone, first-response time, resolution SLA)

---

## Xulosa

**Spektakul holat**: 14 ta HAL QILINGAN (36%), 14 ta QISMAN (36%), 11 ta OCHIQ (28%)

**Eng katta bloklovchi tashqi omillar** (0 ga har qadam):
- Asl belgisi integrator API yopiq (CRPT Turon) — markirovka moduli (M01/M02/M06) texnik xavf
- my.soliq.uz rasmiy API yo'q — davlat hisoboti solishtirish (M10 markaziy oqimi) manual ishlanadi
- Virtual kassa reyestri narxi/muddat noma'lum — MVP jadvali 50 ish kuniga surishi mumkin
- ЗРУ-764 sertifikatlash noaniqlik — eng katta moliyaviy xavf
- E-IMZO rasmiy dasturchi hujjati yo'q — e-faktura/hisobot imzolash integratsiyasi

**Eng katta ichki qarors (MVP boshlanishidan oldin tal qilinishi shart)**:
- Mahsulot egasi: huquqlar matritsasi, narx, onboarding ish oqimi
- Yurist: offline markirovka, QR chek javobgarligi, ToS javobgarlik taqsimoti
- Buxgalter: NSBU №21 hisob rejasi (lex.uz rasmiy manbadan)
- Arkitektura: FM ta'minotchisi, SLO jadvali, tarozi protokoli

**Suv bilan tushish** (ya'ni, aniqlik) tekshiruv oxira: ≈ 6–8 hafta rasmiy murojaat + huquqiy mashvara + ichki tasdiq siqligi = MVP boshlanish sanasi mavjud bo'lmaydigan ehtimoli yoki tashqi blokeriga ulanish.
