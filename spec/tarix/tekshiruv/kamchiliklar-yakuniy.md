# Kamchiliklar tahlili — yakuniy qabul (Opus)

*2026-10-15 · Qabul agenti (Opus) · Manba: `spec/tarix/kamchiliklar-tahlili.md`, Haiku auditlari (`kamchiliklar-1-2.md`, `-3-4.md`, `-5-7.md`, `-xulosa-biznes.md`). Har qator joriy spec'ga (kod-uchun/*, kod-uchun/00–12, `kod-uchun/01-qarorlar.md`, `research_notes/texnik/12-taxminlar-va-murojaatlar.md`, `git diff` — 2026-10-15 commit qilinmagan o'zgarishlar) qarab qayta tekshirildi.*

**Hurmat qilingan qarorlar:** markirovkalangan tovar offline narx ma'lum bo'lsa sotiladi (2026-10-15); chekdan keyin e-faktura (US-M01-06, BP-13); obuna 24 soatdan keyin to'liq lokaut; o'z OAuth 2.0 + admin panel (`14-autentifikatsiya-oauth2.md`); AI-03 MVP'da; nasiyaga foiz yo'q (M08); FIFO+AVECO; tariflar qabul qilingan (unit-iqtisod tasdiqlanmagan); 18 modul; saqlash ≥5 yil.

**Holat ta'riflari:** HAL QILINGAN — spec'da yechim bor (qolgan "taxmin" raqamlar pilotda sozlanadi); QISMAN — yechimning bir qismi bor, aniq qoldiq bor; OCHIQ — asosiy savol javobsiz; ESKIRGAN — band endi ma'noga ega emas.

## Spec'da topilgan ziddiyatlar (Haiku sezmagan) — birinchi navbatda tuzatish kerak

1. **`16-offline-sync.md` 2026-10-15 markirovka qaroriga yangilanmagan**: Asosiy xulosa 7, §7 ("qaror kassirga qoldiriladi", narx sharti yo'q) va Ochiq savol 2 hali eski taxmin. Haiku #25 uchun "16-offline-sync.md §4" deb iqtibos keltirgan — bu matn aslida `21-integratsiyalar.md` (Asosiy xulosa 5, §4)da. Qaror `03-modullar-talablari.md` US-M01-03, `21-integratsiyalar.md` §4'da.
2. **`27-backlog.md` "MVP'dan keyin" #2'da AI-03 hali turibdi**, 6-sprintda AI-03 yo'q — AI-03 MVP'da degan 2026-10-15 qaroriga zid.
3. **`15-xavfsizlik-va-audit.md` §7.3**: "obuna to'xtagan taqdirda ham eksport saqlanadi (US-M17-03)" — 2026-10-15 qaroriga zid (`restricted` holatda eksport yo'q, `03-modullar-talablari.md` US-M17-03).
4. **`21-integratsiyalar.md` §2 "Ma'lumot moslashtirish"**: "qizil faktura → `vat_moves.status` kutilmoqda" — `01-qarorlar.md` #5'ga zid (`status` ustuni yo'q).
5. **`15-xavfsizlik-va-audit.md` §8**: "bcrypt/argon2" — endi faqat argon2id (`12-...` §4.1).
6. **`27-backlog.md` "MVP'dan keyin" #1: Asl belgisi (CRPT) MVP'dan keyin** — lekin markirovkalangan tovarni (offline ham) sotish MVP talabi (US-M01-03). Bu ziddiyat foydalanuvchi qarorini talab qiladi (Q5).
7. `16-offline-sync.md` §3.5 (offline lokautda "ko'rish/eksport ochiq qoladi") vs `03-modullar-talablari.md` US-M17-03 ("qurilma login ekraniga qaytadi") — mayda nomuvofiqlik.

---

## 1. Konsolidatsiyalangan jadval

Belgilar: **Δ** — Haiku hukmi o'zgartirildi.

### A. Asosiy xulosalar

| 08-band | Qisqa | Yakuniy holat | Dalil (fayl:bo'lim) | Nima qoldi | Kim yopadi | Ust. |
|---|---|---|---|---|---|---|
| A1 | 02-arxitektura bo'sh | HAL QILINGAN | `kod-uchun/00…12` mavjud | — | — | — |
| A2 | 5 ish kuni → 5 taqvim kuni | HAL QILINGAN | `07-tuzatishlar` #1; `02-modullar` M10 (US-M10-02); `03-biznes` BP-08 | E'tiroz kanali → #31 | rasmiy xat | — |
| A3 | FIFO/AVECO tanlanmagan | HAL QILINGAN | `02-modullar` US-M04-05; `02-provodka` §3 | — | — | — |
| A4 | To'liq NSBU №21 hisob rejasi yo'q | QISMAN | `02-provodka` §1 (MVP subset), ogohlantirish 1–12 | 191-son buyruq ilovalari bilan solishtirish | buxgalter | P0 |
| A5 | Sandbox/API kontrakt aniq emas | QISMAN | `03-integratsiyalar` Asosiy xulosa 2, §13 | 9 tizim uchun rasmiy javob | rasmiy xat / vendor | P0 |
| A6 | NFR raqamlari yo'q | HAL QILINGAN **Δ** (Haiku: QISMAN → HAL, sabab: band "kamida ichki maqsad" so'ragan — `06-nofunksional` §1 SLO jadvali, §2 99,5% bor) | `06-nofunksional` §1–3 | Pilot telemetriyasi bilan tasdiqlash | pilot | P2 |
| A7 | AI eval/chegara/xarajat limiti "umuman yo'q" | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: eval to'plami, metrikalar, CI gate, tenant token budjeti yozilgan) | `07-ai-qatlami` §5, §8 | AI-03 qabul chegarasi (#59), overage (#60) | foydalanuvchi qarori / pilot | P0 |
| A8 | Biznes/huquqiy qatlam bo'sh | QISMAN | `06-mvp` 3.3 (narx); `06-nofunksional` §11 (unit-iqtisod 1-versiya); US-M04-04 (onboarding) | Support SLA, ToS, merchant shartnomalari, unit-iqtisod tasdig'i (§9) | foydalanuvchi / yurist / vendor | P0 |
| A9 | "61 kamchilik, 24/26/11" | ESKIRGAN **Δ** (Haiku: HAL → ESKIRGAN, sabab: bu meta-statistika, kamchilik emas; hisob endi shu faylda) | — | — | — | — |

### B. Bandlar 1–61

| 08-band | Qisqa | Yakuniy holat | Dalil (fayl:bo'lim) | Nima qoldi | Kim yopadi | Ust. |
|---|---|---|---|---|---|---|
| 1 | ER/jadvallar | HAL QILINGAN | `01-malumotlar` §1–12 | — | — | — |
| 2 | Hujjat raqamlash | HAL QILINGAN | `01-malumotlar` §11; `00-qarorlar` #12 | — | — | — |
| 3 | Holat-mashinalari | QISMAN | `01-malumotlar` §8 (chek, kirim, ko'chirish, smena, e-faktura…) | `purchase_orders` va nasiya holatlari yo'q | spec | P0 |
| 4 | Ko'p ombor/filial | HAL QILINGAN | `01-malumotlar` §3 `warehouses` (MVP 1/filial, model 1:N), Ochiq savol 4 | Ko'p ombor — `11-backlog` MVP'dan keyin | — | — |
| 5 | O'lchov birligi konversiyasi | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: `units.is_fractional`, `product_barcodes.units_per_barcode`, `NUMERIC(18,3)`, US-M09-06 og'irlik kodi bor; konversiya qoidasi va yaxlitlash yozilmagan) | `01-malumotlar` §4; `02-provodka` §5.3 | Asosiy birlik, qadoq koeffitsienti, kasr/butun validatsiyasi qoidasi | spec | P1 |
| 6 | MXIK katalog manbasi | HAL QILINGAN | `03-integratsiyalar` §7 (tasnif.soliq.uz, SDK, qo'lda zaxira) | — | — | — |
| 7 | Narx ro'yxati (optom/chakana, stacking) | QISMAN **Δ** (Haiku: HAL → QISMAN, sabab: `product_prices`da narx turi yo'q; M09 chekka holati "optom va chakana bir vaqtda" hal qilinmagan; stacking — faqat `discount_rules` "taxmin") | `01-malumotlar` §4; `02-modullar` M09 chekka holatlar, M03 | Optom narx MVP'dami; stacking qoidasi | foydalanuvchi qarori | P1 |
| 8 | Qisman qaytarish, double-refund | QISMAN **Δ** (Haiku: HAL → QISMAN, sabab: `return_lines.sale_line_id` bor, lekin "qaytarilgan ≤ sotilgan" invarianti va offline ikki qurilmadan qaytarish to'qnashuvi yozilmagan; chek topilmagan qaytarish modeli yo'q) | `01-malumotlar` §6, §8 (chek qatori); `02-modullar` US-M02-01 | Invariant + xato kodi | spec | P1 |
| 9 | Nasiya: foiz, grafik, shubhali | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: "foiz qo'shilmaydi" — qaror, `02-modullar` M08 Qoidalar; kechish `debt_writeoffs`, aging 0–30/31–60/60+ bor) | `02-modullar` M08 (US-M08-09/10, Qoidalar); `02-provodka` 2.15 | Bo'lib to'lash grafigi yo'q (qaror kerak); "shubhali" mezoni | foydalanuvchi qarori | P2 |
| 10 | Mijoz B2B rekvizitlari | QISMAN **Δ** (Haiku: HAL → QISMAN, sabab: `counterparties`da faqat `stir`; yuridik manzil, bank hisobi/MFO yo'q — e-faktura uchun shart) | `01-malumotlar` §5 | Rekvizit maydonlari / STIR bo'yicha avto-to'ldirish | spec | P1 |
| 11 | Yetkazib beruvchi QQS to'lovchi holati | QISMAN **Δ** (Haiku: HAL → QISMAN, sabab: `counterparties`da QQS to'lovchi belgisi yo'q; AI-03 qamrovi shunga bog'liq) | `01-malumotlar` §5; `05-ai-funksiyalar` AI-03 | `vat_payer` maydoni | spec | P1 |
| 12 | Audit-trail | HAL QILINGAN | `01-malumotlar` §10; `05-xavfsizlik` §6 | — | — | — |
| 13 | To'liq NSBU hisob rejasi | QISMAN | `02-provodka` ogohlantirish, §1 | Rasmiy ilova bilan solishtirish, 12 band javobi | buxgalter | P0 |
| 14 | Dt/Kt jadvali | HAL QILINGAN | `02-provodka` §2.1–2.21 | Buxgalter tasdig'i #13 doirasida | buxgalter (#13) | — |
| 15 | Baholash usuli | HAL QILINGAN | US-M04-05; `02-provodka` §3 | — | — | — |
| 16 | Davr yopish, retro tuzatish | QISMAN | `02-provodka` §3.3–3.4, §5.1 (yopilgan davrga tuzatish — faqat joriy davrda storno) | Davrni qayta ochish siyosati (kim, mumkinmi); tuzatish hujjati UI | spec + buxgalter | P1 |
| 17 | QQS imtiyoz/0% ro'yxati | OCHIQ | `01-malumotlar` §4 `products.vat_rate`; `02-modullar` M09 | MXIK → stavka/imtiyoz kodi jadvali (SK 243-modda) | buxgalter | P0 |
| 18 | QQS vs aylanma rejimi, almashinuv | QISMAN | `02-provodka` §4.3, §5.4; `01-malumotlar` `branch_tax_settings` | Tenant rejimi maydoni/tarixi yo'q (BO-14'da "soliq rejimi" bor, modelda yo'q); davr ichida o'tish qoidasi | buxgalter + spec | P1 |
| 19 | Retro QQS tuzatish | QISMAN | `02-provodka` §2.5, §5.2 (storno — joriy davr sanasi) | Keyingi davrdagi qaytarishning QQS davri — huquqiy tasdiq | buxgalter | P1 |
| 20 | Inventarizatsiya kamomadi QQS | QISMAN | `02-provodka` §2.11 (ortiqcha kodi tasdiqlanmagan) | Javobgar/zarar tanlash qoidasi, ortiqcha hisobi, QQS ta'siri | buxgalter | P2 |
| 21 | Asosiy vosita vs tovar validatsiyasi | OCHIQ | `02-provodka` Asosiy xulosa 2 (MVP'dan tashqari) | Validatsiya/UI izohi yo'q | spec | P2 |
| 22 | Sandbox'lar | QISMAN | `03-integratsiyalar` §13 (Faktura.uz, Payme, E-IMZO, Uzum Checkout) | OFD, CRPT, Didox, my.soliq, Vakolat, Click; Didox/Faktura/Vakolat/Click/Uzum xatlari yozilmagan | rasmiy xat / vendor | P0 |
| 23 | Virtual kassa reyestri narxi | QISMAN | `03-integratsiyalar` §1 (muddat ~50 ish kuni), Ochiq savol 4 | Narx | rasmiy xat | P0 |
| 24 | CRPT Turon API yopiq | OCHIQ | `03-integratsiyalar` §4; `11-backlog` "MVP'dan keyin" #1 | API; backlog bilan ziddiyat (Q5) | rasmiy xat / vendor / foydalanuvchi | P0 |
| 25 | Offline markirovka sotuvi | HAL QILINGAN | `02-modullar` US-M01-03, M01 Offline; `03-integratsiyalar` §4; `07-tuzatishlar` #25 | `04-offline-sync` §7 eskirgan (ziddiyat 1); offline qaytarish/ko'chirish siyosati ochiq (Q8); yuridik tasdiq tavsiya | spec + foydalanuvchi | P0 |
| 26 | E-faktura operatori tanlovi | QISMAN **Δ** (Haiku jadvalda OCHIQ, xulosada QISMAN — ziddiyatli; QISMAN: ikkalasi adapter ortida, zaxira "Faktura.uz bilan boshlash" yozilgan, lekin qaror emas) | `03-integratsiyalar` §2 MVP bosqichi | Rasmiy tanlov + narx | foydalanuvchi qarori / vendor | P0 |
| 27 | e-TTN ichki ko'chirishda | OCHIQ | `03-integratsiyalar` §3 (MVP: keyin, qo'lda belgi) | Majburiylik javobi | rasmiy xat | P1 |
| 28 | Vakolat.uz | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: MVP siyosati qaror qilingan — qo'lda raqam/izoh, ogohlantirish bilan davom; faqat API ochiq) | `03-integratsiyalar` §6 | API usuli | rasmiy xat | P2 |
| 29 | my.soliq.uz API yo'q | OCHIQ | `03-integratsiyalar` §8 (MVP — fayl yuklash zaxirasi) | Dasturiy yo'l | rasmiy xat | P0 |
| 30 | Hisobot: hujjat vs yig'ma | QISMAN | `01-malumotlar` §9 `state_report_diffs` (ko'rsatkich darajasi) | Davlat formati tasdig'i | rasmiy xat | P1 |
| 31 | E'tiroz/tuzatish kanali | QISMAN | `03-biznes` BP-08 (244-qator), `04-ekranlar` OS 10 | Kanal va shakl | rasmiy xat | P1 |
| 32 | QR/Click/Payme chekini kim chiqaradi | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: arxitektura ikkala talqinni konfiguratsiya bilan qo'llab-quvvatlashni belgilagan; huquqiy javob yo'q) | `03-integratsiyalar` §9, Ochiq savol 5 | Huquqiy aniqlik; konfiguratsiya maydoni spec'da yo'q | yurist / rasmiy xat | P0 |
| 33 | Retry/circuit-breaker | QISMAN | `03-integratsiyalar` §0 + har bo'lim backoff | Davlat integratsiyalari uchun circuit-breaker | spec | P1 |
| 34 | Xato kodlari katalogi | QISMAN | `03-integratsiyalar` §1 (704031 namunasi) | Umumiy xato tasnifi + vendor kodlari | spec + vendor | P1 |
| 35 | ЗРУ-764 sertifikatlash | OCHIQ | `05-xavfsizlik` §9.1; `03-integratsiyalar` OS 8 | csec.uz javobi | rasmiy xat | P0 |
| 36 | 48 soatdan keyin bloklash/ogohlantirish | QISMAN | `04-offline-sync` §6 (taklif: bloklamaslik + audit + M18); `12-auth` §8 | Yozma huquqiy xulosa | yurist | P0 |
| 37 | Offline karta terminali | OCHIQ | `04-ekranlar` OS 11; `10-android-pos` §4.5; `03-integratsiyalar` §9 ("offline faqat naqd/nasiya") | Mustaqil terminal bilan offline "karta" yozish | foydalanuvchi qarori / vendor | P1 |
| 38 | Overselling | HAL QILINGAN | `04-offline-sync` §5 | — | — | — |
| 39 | Nasiya limiti offline oshishi | QISMAN | `04-offline-sync` §5 (ruxsat + `limit_exceeded` + M18) | Ortiqcha summa bo'yicha keyingi amal | foydalanuvchi qarori | P1 |
| 40 | POS lokal sig'im | QISMAN | `04-offline-sync` §10 (7/90 kun, Chromium, `storage.persist()`) | Sig'im hisobi, "disk to'ldi" stsenariysi | spec | P1 |
| 41 | Sync backpressure | OCHIQ | `04-offline-sync` §3.1 (50 voqea/so'rov); `09-backend` slowapi faqat login/OTP/AI | 429/Retry-After, tenant konkurentlik chegarasi | spec | P2 |
| 42 | Markirovka offline audit-log | QISMAN | `04-offline-sync` §7 (UI belgi); `01-malumotlar` `marking_codes` | Audit voqealari va maydonlari; `05-xavfsizlik` §6.1'da markirovka yo'q | spec | P0 |
| 43 | Huquqlar matritsasi tasdig'i | QISMAN **Δ** (Haiku: HAL → QISMAN, sabab: band aynan "tasdiqlanmagan" haqida; `01-rollar` OS 1 hali "foydalanuvchi bilan tasdiqlanishi kerak", limitlar taxmin) | `05-xavfsizlik` §2; `01-rollar` §6, OS 1–2 | Rasmiy tasdiq + limit qiymatlari | foydalanuvchi qarori | P0 |
| 44 | Tenant provisioning | QISMAN | `11-backlog` 0-bosqich seed, 1-sprint (rollar, filial, ombor avtomatik) | Ro'yxatdan o'tishda nima yaratilishi ro'yxati | spec | P1 |
| 45 | Audit-log sxemasi/muddati | HAL QILINGAN | `05-xavfsizlik` §6.1–6.3 (append-only, DB huquqi, ≥5 yil ichki siyosat) | — | — | — |
| 46 | AI-03 rasmlari chet el LLM'ga | QISMAN | `05-xavfsizlik` §5.2, §9.2 | ZRU-547 15-modda transfer asosi; AI-03 rasmdagi imzo/ism | yurist | P1 |
| 47 | RPO/RTO | QISMAN | `05-xavfsizlik` §7.1 (RPO "bir necha daqiqa" taxmin) | RTO yo'q | spec | P0 |
| 48 | Restore test sikli | QISMAN | `05-xavfsizlik` §7.2 (choraklik — taxmin) | Runbook/mas'ul | spec | P1 |
| 49 | PCI-DSS | QISMAN | `05-xavfsizlik` §9.3; `04-offline-sync` §12 | Acquirer tasdig'i | vendor | P2 |
| 50 | Parol/PIN/sessiya siyosati | HAL QILINGAN **Δ** (Haiku: QISMAN → HAL, sabab: argon2id, lokaut 5/15 daq progressiv, OTP limitlari, PIN 5 urinish, sessiya 12 soat/7 kun, refresh 14/180 kun — siyosat to'liq, raqamlar sozlanadigan) | `12-auth` §4, §7, §12–13; `00-qarorlar` #3 | — | — | — |
| 51 | Shifrlash/kalitlar | QISMAN | `05-xavfsizlik` §4.2 (envelope AES-256-GCM); `12-auth` §15 | KEK saqlash joyi (UzCloud KMS yo'q bo'lsa), rotatsiya sikli | spec + vendor | P1 |
| 52 | Pentest rejasi | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: "ishga tushirishdan oldin kamida bir marta mustaqil pentest" yozilgan; kim/byudjet yo'q) | `05-xavfsizlik` §8 | Ijrochi, sana, byudjet | foydalanuvchi qarori | P2 |
| 53 | Bo'shagan xodim huquqini bekor qilish | HAL QILINGAN **Δ** (Haiku: QISMAN → HAL, sabab: US-M13-05/07 bloklash/sessiya bekor; offline'da keyingi ulanishda kuchga kirishi — aniq qaror; qurilma bekor → PIN reset) | `02-modullar` M13 (US-M13-05/07, Offline); `12-auth` §7, §18.2; `04-offline-sync` §9 | — | — | — |
| 54 | Ichki SLO | HAL QILINGAN | `06-nofunksional` §1 | Pilot telemetriyasi | pilot | P2 |
| 55 | FM/chek printeri ro'yxati | QISMAN | `06-nofunksional` §7 (narxli ro'yxat, ESC/POS, HID; virtual kassada jismoniy FM shart emas — §7.5) | Pilot uchun qo'llab-quvvatlanadigan modellar tanlovi | foydalanuvchi qarori / pilot | P1 |
| 56 | Tarozi protokoli | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: yorliqli tarozi EAN-13 "2x" og'irlik kodi yo'li (US-M09-06) va qo'lda kiritish zaxirasi bor; protokol pilotda) | `02-modullar` US-M09-06; `06-nofunksional` §7.3 | Kod formati va COM protokoli | pilot / vendor | P1 |
| 57 | Ikki tilli chek | OCHIQ **Δ** (Haiku: QISMAN → OCHIQ, sabab: hech qanday qaror yo'q, faqat "ochiq savol") | `06-nofunksional` §8; `04-ekranlar` OS 1 | Talab bormi | rasmiy xat | P2 |
| 58 | Sig'im rejasi | HAL QILINGAN **Δ** (Haiku: QISMAN → HAL, sabab: band aynan "boshlang'ich hajm-reja, masalan 100 tenant" so'ragan — §3.1–3.2 bor) | `06-nofunksional` §3 | 1000 tenant — keyingi bosqich | pilot | P2 |
| 59 | AI eval va chegara | QISMAN | `07-ai-qatlami` §8; §10 (ishonch 90% taxmin) | AI-03 ishga tushirish chegarasi | foydalanuvchi qarori / pilot | P0 |
| 60 | AI xarajat limiti | HAL QILINGAN | `07-ai-qatlami` §5 | Overage (OS 3) | foydalanuvchi qarori | P2 |
| 61 | AI review/feedback | HAL QILINGAN **Δ** (Haiku: QISMAN → HAL, sabab: `ai_feedback`, haftalik ko'rib chiqish, eval'ga qaytarish — §8.4, §12; guard_failed chastotasi — kuzatuv ochiq savoli, kamchilik emas) | `07-ai-qatlami` §8.4, §12 | — | — | — |

### C. §8 Arxitektura hujjatlari

Hammasi **mavjud** (Haiku bilan bir xil — HAL QILINGAN). Lekin §8 tavsiflari ortiqcha da'vo qiladi; Haiku B-jadvalidagi izohlarda xatolar bor ("02 §3 Dt/Kt jadval xaali" — noto'g'ri, §2'da bor; "band 42 hal qilindi" — noto'g'ri; "36 = overselling" — noto'g'ri).

| 08-band | Qisqa | Yakuniy holat | Dalil | Nima qoldi (tavsifni tuzatish) | Kim | Ust. |
|---|---|---|---|---|---|---|
| 8.1 | 01-malumotlar-modeli | HAL QILINGAN | fayl bor | Holat-mashinalari to'liq emas (#3) | spec | — |
| 8.2 | 02-provodka | HAL QILINGAN | fayl bor | "To'liq NSBU" emas — MVP subset (#13) | buxgalter | — |
| 8.3 | 03-integratsiyalar | HAL QILINGAN | fayl bor | Xato katalogi to'liq emas (#34) | spec/vendor | — |
| 8.4 | 04-offline-sync | HAL QILINGAN | fayl bor | §7 eskirgan (ziddiyat 1) | spec | — |
| 8.5 | 05-xavfsizlik | HAL QILINGAN | fayl bor | §7.3, §8 eskirgan (ziddiyat 3, 5) | spec | — |
| 8.6 | 06-nofunksional | HAL QILINGAN | fayl bor | "Tasdiqlangan uskuna ro'yxati" emas — narx ro'yxati (#55) | pilot | — |
| 8.7 | 07-ai-qatlami | HAL QILINGAN | fayl bor | AI-03 chegara (#59) | foydalanuvchi | — |
| 8.8 | 11-backlog + qo'shimchalar | HAL QILINGAN | fayl bor + `12-auth` | AI-03 joylashuvi eskirgan (ziddiyat 2) | spec | — |

### D. §9 Biznes

| 08-band | Qisqa | Yakuniy holat | Dalil | Nima qoldi | Kim yopadi | Ust. |
|---|---|---|---|---|---|---|
| 9.1 | Unit-iqtisod | QISMAN | `06-nofunksional` §11 (~28–36k so'm/tenant, marja 13–21k); `07-ai-qatlami` §13 | Support, EDO/CRPT haqlari, SMS narxi kiritilmagan | foydalanuvchi + vendor + pilot | P0 |
| 9.2 | Onboarding (Excel/qog'oz) | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: US-M04-04 uch yo'l, US-M08-07, `import_jobs` (validate→commit) bor; shablon ustunlari yo'q) | `02-modullar` US-M04-04, US-M08-07; `01-malumotlar` §10 | CSV shablon formati | spec | P1 |
| 9.3 | Support SLA | OCHIQ | hech qayerda yo'q | Kanal, soat, javob vaqti | foydalanuvchi qarori | P1 |
| 9.4 | Yuridik javobgarlik/ToS | OCHIQ | `02-modullar` US-M17-03 (faqat ToS eslatmasi) | ToS/SLA loyihasi, javobgarlik chegarasi | yurist | P1 |
| 9.5 | Payme/Click/Uzum merchant shartnomasi | OCHIQ **Δ** (Haiku bu qatorni o'tkazib yuborgan) | `03-integratsiyalar` §9 (faqat komissiya stavkalari) | Platforma merchant hisobi, shartnomalar | vendor | P1 |

### E. Keyingi qadamlar

| 08-band | Qisqa | Yakuniy holat | Dalil | Nima qoldi | Kim yopadi | Ust. |
|---|---|---|---|---|---|---|
| K1 | 4 faylni yangilash | HAL QILINGAN | `07-tuzatishlar` #1 | #31 | rasmiy xat | — |
| K2 | Rasmiy xatlarni yuborish | OCHIQ | `12-taxminlar` (faqat Xat 1–3 loyihasi; yuborilgani haqida dalil yo'q); `11-backlog` 0-bosqich | Didox/Faktura/Vakolat/Click/Uzum xatlari yozilishi va hammasi yuborilishi | foydalanuvchi / rasmiy xat | P0 |
| K3 | Huquqiy maslahat | OCHIQ | `11-backlog` 0-bosqich ((a) bekor) | 48 soat, QR chek, offline markirovka (tavsiya), chek→e-faktura, ToS | yurist | P0 |
| K4 | Buxgalter: NSBU + FIFO/AVECO | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: FIFO/AVECO qaror qilingan) | US-M04-05; `02-provodka` | Hisob rejasi tasdig'i | buxgalter | P0 |
| K5 | Huquqlar matritsasi + narx tasdig'i | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: narx 2026-10-14 qabul qilingan) | `06-mvp` 3.3 | Matritsa (#43) | foydalanuvchi qarori | P0 |
| K6 | 02-arxitektura yozish | HAL QILINGAN | 00–12 | — | — | — |
| K7 | Sandbox tekshiruvi + xavf qaydi | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: ochiq manbalar tekshirilgan va §13'da xavf sifatida qayd etilgan) | `03-integratsiyalar` §13 | Rasmiy javoblar | rasmiy xat | P0 |
| K8 | AI eval + xarajat limiti | QISMAN **Δ** (Haiku: OCHIQ → QISMAN, sabab: `07-ai-qatlami` §5, §8 loyihalangan) | `07-ai-qatlami` | AI-03 chegarasi (#59) | foydalanuvchi / pilot | P0 |
| K9 | SLO jadvalini e'lon qilish | HAL QILINGAN **Δ** (Haiku: QISMAN → HAL, sabab: jadval "taxmin, ichki maqsad" sifatida e'lon qilingan — aynan so'ralgani) | `06-nofunksional` §1 | — | — | — |
| K10 | FM/printer ta'minotchisi | OCHIQ | `11-backlog` 0-bosqich, OS 2 (fiskal yo'l: o'z reyestri vs hamkor) | Fiskal yo'l qarori; pilot uskunasi | foydalanuvchi qarori | P0 |

**Haiku auditidagi boshqa xatolar:** `kamchiliklar-1-2.md` statistikasida "HAL 14" deyilib 11 band sanalgan, "QISMAN 5" deyilib 6 sanalgan; `-3-4.md` "Jami: 10 OCHIQ" deyilib 8 ta sanalgan.

---

## 2. Spec yozish bilan hozir yopish mumkin

Har biri — qo'shiladigan aniq matn/bo'lim (taxmin qiymatlar "taxmin" deb belgilansin).

1. **Ziddiyat 1 / #25 / #42 (P0)** — `16-offline-sync.md`: Asosiy xulosa 7, §7 va Ochiq savol 2'ni almashtirish: "*(2026-10-15: foydalanuvchi qarori)* Offline markirovkalangan tovar: narx qurilmada ma'lum bo'lsa sotuv ruxsat, noma'lum bo'lsa taqiq (US-M01-03). Qurilmada faqat format/nazorat raqami tekshiriladi; kod `marking_codes.status='pending_verification'` bilan yoziladi; internet qaytganda `marking_verify`+`marking_sell`. Offline qaytarish/ko'chirish — ochiq (Q8)." §7'ga audit qatori: "Audit voqealari: `marking.offline_sold` (actor_user_id, device_id, code, sale_id, price_source=`cache`, created_at), `marking.offline_refused_no_price`, `marking.verify_failed` (sync'dan keyin: noto'g'ri/takroriy kod, CRPT xatosi → M18 Egasiga). Bu voqealar `05-xavfsizlik` §6.1 ro'yxatiga qo'shiladi." `01-malumotlar` §9 `marking_codes.status`ga `pending_verification` qo'shilsin.
2. **Ziddiyat 2 (P0)** — `27-backlog.md`: "MVP'dan keyin #2"dan AI-03'ni olib tashlash, 6-sprintga: "AI-03 OCR quvuri (`07-ai-qatlami` §10), US-M04-04 (3)-yo'l, M07 kirim loyihasi — pilot chegarasi bilan *(2026-10-15: foydalanuvchi qarori)*".
3. **Ziddiyat 3–5, 7 (P1)** — `05-xavfsizlik` §7.3: "eksport faqat `active` holatda yoki ixtiyoriy `closed` oqimida (US-M17-03, US-M17-05)"; `03-integratsiyalar` §2: "qizil faktura → kiruvchi QQS `vat_moves`ga to'lovgacha yozilmaydi (`00-qarorlar` #5)"; `05` §8: "argon2id"; `04-offline-sync` §3.5'ni US-M17-03 bilan tenglashtirish (qurilma login ekraniga qaytadi; ko'rish/eksport yo'q yoki aksincha — bitta variant).
4. **#3 (P0)** — `01-malumotlar` §8 ga qatorlar: "Xaridnoma (`purchase_orders`): `draft` → `sent` → `partially_received` → `closed` / `cancelled`; holat `goods_receipts.po_id` yig'indisidan; `closed`dan keyin tahrir taqiq." "Nasiya qarzi (har `debt_moves` receivable qatori, hisoblangan): `open` → `partially_paid` → `paid`; `written_off` (`debt_writeoffs`, faqat Egasi); `overdue` — `due_date < bugun` bo'lsa hisoblangan bayroq, holat emas."
5. **#5 (P1)** — `01-malumotlar` §4 izoh: "Qoldiq har doim `products.unit_code` (asosiy birlik)da. Qadoq (quti) — `product_barcodes.units_per_barcode` koeffitsienti bilan asosiy birlikka ko'paytiriladi. `units.is_fractional=false` birlikda miqdor butun son (validatsiya), `true`da 3 xona. Qator summasi = narx × miqdor, tiyingacha ROUND_HALF_UP."
6. **#8 (P1)** — `01-malumotlar` §6 `returns` izohi: "Invariant: `SUM(return_lines.qty) WHERE sale_line_id=X AND status=posted ≤ sale_lines.qty` — `ReturnPostingService` sotuv qatorini qulflab tekshiradi; oshsa `RETURN_QTY_EXCEEDED` (offline'da POS-12'da rad). Chek topilmagan qaytarish: `sale_line_id=NULL`, faqat Menejer PIN bilan, narx — joriy narx, alohida hisobot."
7. **#10, #11 (P1)** — `counterparties`ga: `legal_address`, `bank_account`, `bank_mfo`, `vat_payer BOOL`, `vat_payer_checked_at`; "STIR kiritilganda rekvizitlar EDO operatoridan (Faktura.uz `CheckCompanyExist/:inn`) avto-to'ldiriladi; B2B e-faktura bu maydonlarsiz yaratilmaydi; `vat_payer=false` yetkazib beruvchi — AI-03 qamrovi."
8. **#18 (P1, buxgalter tasdig'i bilan)** — `tenant_tax_regimes(tenant_id, valid_from (oy 1-sanasi), regime: vat|turnover)`; "Rejim faqat oy boshidan o'zgaradi, o'tgan davrlar qayta hisoblanmaydi; 1 mlrd chegarasi oshganini tizim ogohlantiradi, o'tishni Buxgalter belgilaydi."
9. **#16 (P1)** — `02-provodka` §5.1: "MVP'da yopilgan davr qayta ochilmaydi; tuzatish — joriy davrda tuzatuvchi hujjat (`correction_of_period` maydoni bilan) + audit. Qayta ochish — buxgalter tasdig'idan keyin ko'rib chiqiladi."
10. **#21 (P2)** — `02-modullar` M04 chekka holat: "Asosiy vositalar (uskuna, jihoz) katalogga kiritilmaydi; ularning xaridi M15 xarajati sifatida yoziladi. Tovar yaratishda ogohlantirish matni."
11. **#33 (P1)** — `03-integratsiyalar` §0: "Circuit-breaker (har adapter, tenant'dan mustaqil): 1 daqiqada 5 ketma-ket vaqtinchalik xato → ochiq (chaqiruv yo'q, joblar `retry`da qoladi), 5 daqiqadan keyin half-open bitta sinov; ochiq holat BO-14'da 🔴 va M18 alert. OFD 48 soat taymeri breaker'dan mustaqil (taxmin)."
12. **#34 (P1)** — §0'ga umumiy xato tasnifi: `transient` (timeout/5xx/429 → retry), `auth` (401/403 → `failed`, BO-14 "kredensial"), `validation` (4xx → `failed`, foydalanuvchiga matn), `duplicate` (idempotent muvaffaqiyat); vendor kodlari ilova sifatida hujjat kelganda.
13. **#40 (P1)** — `04-offline-sync` §10: "Hajm taxmini: voqea ~2 KB; 1 000 chek/kun × 2 kun ≈ 4 MB; `navigator.storage.estimate()` 80% bo'lsa ogohlantirish, 95% — kesh (chek tarixi) qisqartiriladi; `pending` outbox hech qachon o'chirilmaydi."
14. **#41 (P2)** — `04-offline-sync` §3.1: "Server: qurilma boshiga 5 so'rov/s, tenant boshiga bir vaqtda 4 ta push (taxmin); oshsa `429` + `Retry-After`; klient eksponensial backoff + jitter."
15. **#44 (P1)** — `05-xavfsizlik` §1.1 yoki M17: "Ro'yxatdan o'tganda bitta tranzaksiyada: `tenants`, `subscriptions(trial, 30 kun)`, Egasi `memberships`, 5 tizim roli + `role_permissions` (`05` §2.2), standart filial + ombor + kassa, `doc_sequences`, standart xarajat toifalari, `valuation_method=AVECO`. Hisob rejasi va `units`, `plans` — global, nusxalanmaydi; MXIK — tasnif.soliq.uz."
16. **#47, #48 (P0/P1)** — `05-xavfsizlik` §7: "Ichki maqsad: RPO ≤ 5 daqiqa (PITR), RTO ≤ 4 soat (taxmin). Choraklik staging'da to'liq restore sinovi; mas'ul — DevOps; natija (vaqt, muvaffaqiyat) operatsion jurnalga; RTO oshsa — insident."
17. **#51 (P1)** — `05` §4.2: "MVP: KEK — deploy sirlari orqali muhit o'zgaruvchisi, faqat API/worker konteynerida; yillik rotatsiya (`key_version`); UzCloud KMS tasdiqlansa unga ko'chiriladi."
18. **9.2 (P1)** — `02-modullar` US-M04-04 / `import_jobs`: CSV shablonlari — `products.csv`: name, barcode, unit_code, mxik_code, vat_rate, price, category, is_marked; `opening_stock.csv`: barcode, qty, unit_cost, expiry_date; `opening_debts.csv`: name, phone, amount, direction (`receivable`/`payable`), date. UTF-8, ajratgich `;`, kasr nuqta bilan; xatolar qator/maydon bo'yicha (`import_jobs.errors`).
19. **§8 tavsiflari (P2)** — 08 §8 qatorlarini to'g'rilash (C jadvalidagi "Nima qoldi" ustuni).

## 3. Foydalanuvchi qarori kerak

1. **#43** — `05-xavfsizlik` §2.2 standart matritsani tasdiqlaysizmi? Limitlar: kassir chegirmasi (%), PIN'siz qaytarish summasi, kassadan pul olish summasi — qancha?
2. **K10/#55/#23** — Fiskal yo'l: o'z virtual kassamizni reyestrga kiritamizmi (~50 ish kuni + noma'lum narx) yoki reyestrdagi hamkor (E-POS/UZKASSA) orqali boshlaymizmi? Pilot uchun qaysi printer/skaner/tarozi modellari?
3. **Q5 (#24 vs backlog)** — CRPT integratsiyasi MVP'dan keyin bo'lsa, MVP'da markirovkalangan tovar umuman sotiladimi (online ham CRPT'siz)? Yoki CRPT MVP'ga (proksi integrator orqali) kiradimi?
4. **#26** — E-faktura: MVP'da faqat Faktura.uz (API ochiq), Didox keyin — rozimisiz?
5. **Q8 (#25a)** — Offline markirovkalangan tovarni qaytarish va ko'chirish: ruxsat (sotuv kabi, keyin tasdiqlash) yoki taqiq?
6. **#37** — Mustaqil bank terminali bilan offline'da "karta" to'lovini qo'lda belgilashga ruxsat beramizmi?
7. **#39** — Offline'da limitdan oshgan nasiya: qarz shundayligicha qoladi + bayroq + xabar (taklif) — yetarlimi?
8. **#7** — Optom narx MVP'da kerakmi (mijoz turi bo'yicha narx turi)? Bir chekda bir nechta chegirma — faqat eng yuqori ustuvorlikli bittasi (taklif)?
9. **#9** — Nasiyani bo'lib to'lash grafigi kerakmi yoki bitta va'da sanasi yetarli? "Shubhali qarz" — Egasi qo'lda belgilaydi (taklif) yoki N kundan keyin avtomatik?
10. **#59** — AI-03 ishga tushirish sharti: 100 holatli to'plamda summa/sana/miqdor maydonlari bo'yicha ≥ 90% aniqlik (taklif) — qabul qilasizmi?
11. **#60** — AI limiti tugaganda qo'shimcha to'lov (overage) bo'ladimi?
12. **9.3** — Support: kanallar (Telegram/telefon), ish vaqti, birinchi javob vaqti (masalan fiskal/markirovka muammosida 1 soat)?
13. **9.1** — Unit-iqtisod: marja tor (13–21k so'm/Start); support xarajati qo'shilganda Start narxi qayta ko'riladimi?
14. **#52** — Pentest: kim (tashqi kompaniya), qachon (pilotdan oldin), byudjet?
15. **#16** (buxgalter bilan) — Yopilgan oyni qayta ochishga ruxsat bormi?
16. **K2** — Rasmiy xatlarni kim imzolaydi va qaysi yuridik shaxs nomidan yuboriladi?

## 4. Tashqi ishlar

**Buxgalter:** #13/A4/K4 (191-son buyruq ilovalari bilan hisob rejasi, `02-provodka` ogohlantirish 1–12), #14 tekshiruvi, #17 (SK 243-modda imtiyozlar → MXIK/stavka jadvali), #18 (rejim o'tish qoidasi), #19 (keyingi davr qaytarishi QQS davri), #20 (kamomad/ortiqcha hisoblari, QQS), #16 (qayta ochish).

**Yurist:** #36 (48 soatdan keyin bloklamaslik), #32 (QR/Click/Payme chek javobgarligi), #46 (AI'ga chet elga uzatish asosi, ZRU-547 15-modda), 9.4 (ToS, javobgarlik chegarasi, obuna lokauti fiskal oqibati bandi), #25 (offline markirovka — tavsiya), chekdan keyin e-faktura (tavsiya), ma'lumot buzilishi haqida xabar berish tartibi.

**Rasmiy xat:** #35 (csec.uz — Xat 3), #23/#22 (Soliq qo'mitasi/"Yangi texnologiyalar" — reyestr narxi, OFD sinov kaliti — Xat 1), #29/#30/#31 (my.soliq.uz — API, hisobot darajasi, e'tiroz kanali), #24 (CRPT Turon — Xat 2), #27 (e-TTN ichki ko'chirish), #28 (Vakolat.uz API), #57 (ikki tilli chek).

**Vendor:** #26 (Didox/Faktura.uz — narx, sandbox), 9.5 (Payme/Click/Uzum merchant shartnomasi, platforma hisobi), #34 (xato kodlari), #49/#37 (acquirer — PCI qamrovi, terminal offline), #51 (UzCloud KMS), SMS provayder (narx — 9.1), #56 (tarozi ishlab chiqaruvchisi).

**Pilot:** #54/A6 (SLO telemetriyasi), #58 (sig'im), #59 (AI-03 aniqlik), 9.1 (real xarajat), #56 (og'irlik kodi formati), #40 (lokal hajm).

## 5. `kamchiliklar-tahlili.md` statuslarini yangilash ko'rsatmasi

Qoida: har band matni boshidagi mavjud kursiv prefiksni (agar bor bo'lsa) **almashtirish**, yo'q bo'lsa qo'shish. Format: `✅ *Hal qilindi (…): dalil.*` / `*Qisman (…): dalil. Qoladi: …*` / `⛔ *Ochiq (2026-10-15): … Kim: …*`. Hal qilinganlarda asl matnni `~~…~~` bilan o'chirish ixtiyoriy.

**Asosiy xulosalar**
- 4: `*Qisman (2026-10-14): 02-provodka §1 MVP subset. Qoladi: buxgalter tasdig'i (191-son ilovalari).*`
- 5: `*Qisman (2026-10-14/15): 03-integratsiyalar §13. Qoladi: 9 tizim bo'yicha rasmiy javob.*`
- 6: `✅ *Hal qilindi (2026-10-14): 06-nofunksional §1–3 ichki SLO (taxmin), pilotda tasdiqlanadi.*`
- 7: `*Qisman (2026-10-14): 07-ai-qatlami §5, §8. Qoladi: AI-03 qabul chegarasi, overage.*`
- 8: `*Qisman (2026-10-15): narx qabul qilingan; unit-iqtisod 1-versiya 06-nofunksional §11; onboarding US-M04-04. Qoladi: support SLA, ToS, merchant shartnomalari.*`
- 9: `*Eskirgan (2026-10-15): yakuniy holat hisobi — tekshiruv/kamchiliklar-yakuniy.md.*`

**Bandlar**
- 3: mavjud prefiks qoladi.
- 4: `✅ *Hal qilindi (2026-10-14): 01-malumotlar §3 — model 1:N, MVP'da filialga 1 ombor.*`
- 5: `*Qisman (2026-10-15): units.is_fractional, units_per_barcode, US-M09-06. Qoladi: konversiya/yaxlitlash qoidasi.*`
- 6: `✅ *Hal qilindi (2026-10-14): 03-integratsiyalar §7 (tasnif.soliq.uz).*`
- 7: `*Qisman (2026-10-15): product_prices (tarix, filial). Qoladi: optom narx va stacking — foydalanuvchi qarori.*`
- 8: `*Qisman (2026-10-14): return_lines.sale_line_id. Qoladi: "qaytarilgan ≤ sotilgan" invarianti, chek topilmagan qaytarish.*`
- 9: `*Qisman (2026-10-14): foiz qo'shilmaydi (M08), kechish va aging bor. Qoladi: bo'lib to'lash, shubhali qarz mezoni.*`
- 10: `*Qisman (2026-10-15): counterparties (stir). Qoladi: yuridik manzil, bank rekvizitlari.*`
- 11: `*Qisman (2026-10-15): yetkazib beruvchi — counterparties. Qoladi: vat_payer belgisi.*`
- 13: `*Qisman (2026-10-14): 02-provodka §1. Qoladi: buxgalter tasdig'i.*`
- 14: `✅ *Hal qilindi (2026-10-14): 02-provodka §2.1–2.21 (tasdiq — 13-band doirasida).*`
- 16: `*Qisman (2026-10-14): 02-provodka §3.4, §5.1. Qoladi: davrni qayta ochish siyosati.*`
- 17: `⛔ *Ochiq (2026-10-15): MXIK → QQS stavka/imtiyoz jadvali yo'q. Kim: buxgalter.*`
- 18: `*Qisman (2026-10-14): branch_tax_settings, §4.3. Qoladi: tenant QQS/aylanma rejimi va o'tish qoidasi.*`
- 19: `*Qisman (2026-10-14): storno joriy davrda (§5.2). Qoladi: buxgalter tasdig'i.*`
- 20: `*Qisman (2026-10-14): 02-provodka §2.11. Qoladi: ortiqcha hisobi, QQS ta'siri.*`
- 21: `⛔ *Ochiq (2026-10-15): MVP'da asosiy vosita yo'q; validatsiya matni yozilmagan. Kim: spec.*`
- 22: mavjud prefiks qoladi.
- 23: `*Qisman (2026-10-14): muddat ~50 ish kuni (03-integratsiyalar §1). Qoladi: narx — rasmiy xat.*`
- 24: `⛔ *Ochiq (2026-10-15): API yopiq; 11-backlog'da CRPT MVP'dan keyin — US-M01-03 bilan ziddiyat, foydalanuvchi qarori kerak.*`
- 25: `✅ *Hal qilindi (2026-10-15: foydalanuvchi qarori): narx ma'lum bo'lsa offline sotuv ruxsat, aks holda taqiq — US-M01-03, 03-integratsiyalar §4. Qoladi: 04-offline-sync §7'ni yangilash; offline qaytarish/ko'chirish.*`
- 26: `*Qisman (2026-10-14): ikkalasi adapter ortida, zaxira — Faktura.uz bilan boshlash. Qoladi: rasmiy tanlov.*`
- 27: `⛔ *Ochiq (2026-10-15): MVP'da e-TTN keyin (03-integratsiyalar §3). Kim: rasmiy xat.*`
- 28: `*Qisman (2026-10-14): MVP — qo'lda raqam/izoh (03-integratsiyalar §6). Qoladi: API.*`
- 29: `⛔ *Ochiq (2026-10-15): MVP — fayl yuklash zaxirasi (03-integratsiyalar §8). Kim: rasmiy xat.*`
- 30: `*Qisman (2026-10-14): state_report_diffs — ko'rsatkich darajasi. Qoladi: davlat formati tasdig'i.*`
- 31: `*Qisman (2026-10-14): 5 taqvim kun tuzatildi. Qoladi: e'tiroz kanali.*`
- 32: `*Qisman (2026-10-14): ikkala talqin konfiguratsiya bilan (03-integratsiyalar §9). Qoladi: huquqiy javob.*`
- 33: prefiksni `*Qisman (2026-10-14): …*`ga almashtirish (✅ olib tashlansin).
- 34: `*Qisman (2026-10-15): bitta namuna kod. Qoladi: umumiy xato tasnifi + vendor kodlari.*`
- 35: `⛔ *Ochiq (2026-10-15): csec.uz javobi yo'q (Xat 3).*`
- 36: mavjud prefiks qoladi.
- 37: `⛔ *Ochiq (2026-10-15): 04-ekranlar OS 11, 10-android §4.5. Kim: foydalanuvchi qarori/acquirer.*`
- 39: `*Qisman (2026-10-14): 04-offline-sync §5 (ruxsat + bayroq + M18). Qoladi: ortiqcha summa siyosati.*`
- 40: `*Qisman (2026-10-14): 04-offline-sync §10 (7/90 kun, Chromium). Qoladi: sig'im hisobi.*`
- 41: `⛔ *Ochiq (2026-10-15): 429/backpressure yo'q. Kim: spec.*`
- 42: `*Qisman (2026-10-14): UI belgi (04-offline-sync §7). Qoladi: audit voqealari.*`
- 43: `*Qisman (2026-10-14): 05-xavfsizlik §2.2 matritsa. Qoladi: foydalanuvchi tasdig'i, limitlar.*`
- 44: `*Qisman (2026-10-14): 11-backlog seed/1-sprint. Qoladi: provisioning ro'yxati.*`
- 45: prefiksni almashtirish: `✅ *Hal qilindi (2026-10-14): 05-xavfsizlik §6 — append-only, ≥5 yil (ichki siyosat, O'RQ-404 29-m.).*`
- 46: `*Qisman (2026-10-14): 05-xavfsizlik §5.2, §9.2. Qoladi: transfer asosi — yurist.*`
- 47: `*Qisman (2026-10-14): RPO taxmin (05 §7.1). Qoladi: RTO.*`
- 48: `*Qisman (2026-10-14): choraklik sinov taklifi (05 §7.2). Qoladi: runbook.*`
- 49: `*Qisman (2026-10-14): karta ma'lumoti saqlanmaydi (05 §9.3). Qoladi: acquirer tasdig'i.*`
- 50: `✅ *Hal qilindi (2026-10-15): 12-autentifikatsiya-oauth2 §4, §7, §12–13.*`
- 51: `*Qisman (2026-10-14): envelope encryption (05 §4.2). Qoladi: KEK saqlash joyi.*`
- 52: `*Qisman (2026-10-14): ishga tushirishdan oldin pentest (05 §8). Qoladi: ijrochi/byudjet.*`
- 53: `✅ *Hal qilindi (2026-10-15: foydalanuvchi qarori): US-M13-05/07, offline'da keyingi ulanishda kuchga kiradi.*`
- 55: `*Qisman (2026-10-14): 06-nofunksional §7 (virtual kassada jismoniy FM shart emas). Qoladi: pilot uskunasi tanlovi.*`
- 56: `*Qisman (2026-10-14): US-M09-06 og'irlik kodi + qo'lda kiritish. Qoladi: protokol — pilot.*`
- 57: `⛔ *Ochiq (2026-10-15). Kim: rasmiy xat.*`
- 58: `✅ *Hal qilindi (2026-10-14): 06-nofunksional §3 (100 tenant rejasi).*`
- 59, 60, 61: mavjud prefikslar qoladi (59 — qisman; 60, 61 — hal).
- 1, 2, 12, 15, 38, 54: mavjud ✅ prefikslar qoladi.

**§8:** sarlavha `*(2026-10-14: hammasi yozildi; qamrov — tekshiruv/kamchiliklar-yakuniy.md C jadvali)*`; 2-qatordagi "to'liq NSBU №21 hisob rejasi" → "NSBU №21 MVP subset (buxgalter tasdig'i kerak)"; 6-qatordagi "tasdiqlangan uskuna ro'yxati" → "uskuna narx ro'yxati".

**§9 (har qatorning "Kamchilik" ustuni boshiga):**
- 9.1: `*Qisman (2026-10-14): 06-nofunksional §11 1-versiya. Qoladi: support/EDO/SMS xarajatlari, pilot.*`
- 9.2: `*Qisman (2026-10-14): US-M04-04, US-M08-07, import_jobs. Qoladi: CSV shablon formati.*`
- 9.3: `⛔ *Ochiq (2026-10-15). Kim: foydalanuvchi qarori.*`
- 9.4: `⛔ *Ochiq (2026-10-15): faqat ToS eslatmasi (US-M17-03). Kim: yurist.*`
- 9.5: `⛔ *Ochiq (2026-10-15): faqat komissiya stavkalari (03-integratsiyalar §9). Kim: vendor.*`

**Keyingi qadamlar:** 2 — `⛔ *(ochiq: yuborilgani tasdiqlanmagan; 5 ta xat hali yozilmagan)*`; 3 — `⛔ *(ochiq; obuna bandi bekor qilindi, 2026-10-15)*`; 4 — `*(qisman: FIFO/AVECO qaror qilindi)*`; 5 — `*(qisman: narx qabul qilindi)*`; 7 — `*(qisman: 03-integratsiyalar §13)*`; 8 — `*(qisman: 07-ai-qatlami §5, §8)*`; 9 — `✅ *(bajarildi: 06-nofunksional §1)*`; 10 — `⛔ *(ochiq: fiskal yo'l qarori)*`.
