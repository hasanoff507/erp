# MVP chegarasi, raqobatchilardan farq va muvaffaqiyat o'lchovlari

**Maqsad:** 18 MVP modulining MoSCoW taqsimotini, MVP'dan keyingi M19 «1C integratsiyasi» (Bosqich 7) qamrovini, Won't ro'yxatini, raqobatchilardan farqlarni, muvaffaqiyat o'lchovlarini, yagona tarif modelini va MVP'ga kirish bloklovchi tashqi omillarni belgilash.
**Kim uchun:** mahsulot/arxitektura jamoasi, bosqich rejalashtiruvchilar.
**Bog'liq fayllar:** `01-qarorlar.md`, `03-modullar-talablari.md`, `09-ai-funksiyalar.md`, `27-backlog.md`, `33-1c-integratsiya.md`.
**Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. **18 modulning (M01-M18) hammasi MVP chegarasida** — M01-M14 `spec/README.md` va `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` (Asosiy xulosa #2) orqali qabul qilingan, M15-M18 (`tuzatishlar-va-yechimlar.md`, #12, #13, #15, #16) qo'shilgan. Har bir modulda kamida bitta Must-darajali hikoya bor; modul ichidagi ayrim hikoyalar Should/Could (1.1-jadval).
2. **4 ta AI funksiya** (AI-01, AI-03, AI-05, AI-06) MVP ichida, shu jumladan AI-03 — qog'oz hujjat OCR (qaror #16). Ularning o'zi Must emas — ular deterministik ("kod hisoblaydi") asosiy jarayonning ustiga qo'yilgan tushuntirish/matn qatlami, shuning uchun Should/Could darajasida (`spec/kod-uchun/09-ai-funksiyalar.md`).
3. **Won't ro'yxati** aniq: kadrlar/ish haqi, CRM/sodiqlik (shu jumladan M03'dagi loyallik bonusi), ishlab chiqarish, boshqa tizimlardan ma'lumot ko'chirish konnektorlari, 7 ta AI funksiya (AI-02, 04, 07-11) — barchasi tadqiqot bilan tasdiqlangan qarorlar (`spec/README.md`, `00-xulosa-va-ochiq-savollar.md`).
4. Raqobatchilardan eng aniq manbali farq — **AI funksiyasi**: tekshirilgan 9 mahsulotdan faqat 2 tasida (REGOS, Smartup) bor, qolgan 7 tasida rasmiy sahifada AI haqida da'vo yo'q (`research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`, 2-bo'lim).
5. **Biznes o'lchovlari — pilot ko'rsatkichlari**: mahsulot hali ishga tushmagan, O'zbekiston SaaS bozorida churn/retention/pilot-konversiya bo'yicha ochiq ma'lumot yo'q; qiymatlar pilotning 30 kunlik telemetriyasi bilan to'ldiriladi (26 #24 (OQ-098)). Qonuniy majburiy ko'rsatkichlar (48 soat, 5 ish kuni, markirovka qabul muddati, e-TTN) manbali.
6. **MVP kodini (Bosqich 0–6) to'xtatadigan tashqi omil yo'q** — hammasi port+stub/sozlama ortida (4-bo'lim). Eng muhim tashqi bog'liqliklar: fiskal hamkor (bulutdan OFD'ga ochiq API yo'q — Do'kon agenti yoki hamkor bulut rejimi, qaror #60; real adapter Bosqich 5), CRPT Turon (`verify`/`writeoff` real adapteri; chakana sotuvda kod chek orqali ketadi — qaror #62), virtual kassa reyestri uchun Kiberxavfsizlik markazi ekspertizasi narxi, foydalanish shartlari (oferta) yakuniy matni — birinchi real tenantdan oldin. ЗРУ-764 sertifikatlash bizga majburiy emas (P4 OQ-039).
7. MoSCoW'dagi **hikoya darajasidagi** taqsimot (Must/Should/Could) — modul darajasidagi "18 modul MVP" qarorining ichidagi ustuvorlik — tasdiqlangan (26 #23); bosqich rejalashtirishda `27-backlog.md` bilan birga ishlatiladi.
8. **M19 «1C integratsiyasi» — MVP'dan keyin, Bosqich 7** (qaror #37): pilot do'konlar bilan birinchi navbat, ERP → 1C bir tomonlama yozish, birinchi konfiguratsiya «Бухгалтерия для Узбекистана 3.0» (3.0.64+), 99 000 tarif ichida (qaror #41). Qamrov va qamrovdan tashqari ro'yxat — 1.4-bo'lim.
9. **Narx modeli — yagona tarif** (qaror #22): **bitta tarif — 99 000 so'm/oy, hammasi (18 modul, 1 virtual kassa/fiskal, AI oylik limiti, Telegram bot) narxga kiradi**; qo'shimcha har bir kassa — **+39 000 so'm/oy** (qaror #22; hamkor kassa narxi ma'lum bo'lgach qayta ko'riladi — 26 #168). Yillik to'lovda −20% va 30 kunlik bepul sinov. Unit-iqtisod: 1 kassali tenant xarajati taxminan **60 000–68 000 so'm/oy** → marja taxminan **31 000–39 000 so'm** (pilotda tasdiqlanadi — 26 #24 (OQ-098)). Batafsil — 3.3-bo'lim.

---

## 1. MoSCoW taqsimoti

### 1.1 Modullar va foydalanuvchi hikoyalari (US-Mxx-nn)

Barcha 18 modul MVP ichida (MVP qarori, `spec/README.md`); har birida kamida bitta Must hikoya bor, qolganlari Should/Could. Quyida har bir modulning hikoyalari (`spec/kod-uchun/03-modullar-talablari.md`dan) ustuvorlik bo'yicha ajratilgan.

| Modul | Must | Should | Could |
|---|---|---|---|
| M01 Kassa | US-M01-01 (sotuv/chek), US-M01-02 (offline+sync), US-M01-03 (markirovka tekshirish), US-M01-04 (smena/Z-hisobot), US-M01-05 (UzQR to'lov — yuridik shaxslar uchun 2026-07-01'dan majburiy), US-M01-06 (chekdan keyin e-faktura, qaror #18), US-M01-07 (chek printeri va tarozini sozlash, POS-16) | — | — |
| M02 Qaytarish | US-M02-01 (asl chek bo'yicha), US-M02-03 (QQS tuzatish) | US-M02-02 (limit tasdiqlash) | — |
| M03 Chegirma | US-M03-01 (limit ichida chegirma) | — | US-M03-03 (margin hisoboti) |
| M04 Ombor qoldig'i | US-M04-01 (kirim balans), US-M04-04 (boshlang'ich katalog/qoldiq), US-M04-05 (tannarx usuli FIFO/AVECO) | US-M04-02 (past qoldiq ogohlantirish), US-M04-03 (ko'p filial konsolidatsiya), US-M04-06 (yaroqlilik muddati, hisobdan chiqarish) | — |
| M05 Inventarizatsiya | US-M05-01 (sanash), US-M05-02 (farq tasdiqlash), US-M05-03 (buxgalteriya yozuvi) | — | — |
| M06 Ko'chirish | US-M06-01 (yuborish, e-TTN "Ombordan omborga" — qaror #63), US-M06-02 (qabul va e-TTN tasdiqlash) | US-M06-03 (tarix, e-TTN holati) | — |
| M07 Xarid | US-M07-01 (xaridnoma), US-M07-02 (qabul), US-M07-03 (e-faktura+QQS), US-M07-04 (yetkazib beruvchiga to'lov) | US-M07-05 (yetkazib beruvchiga qaytarish) | — |
| M08 Nasiya / Qarz daftari | US-M08-01 (limitli sotuv), US-M08-02 (kredit limiti, ixtiyoriy), US-M08-04 (qarz to'lovi), **US-M08-05 (tez qarz yozish, offline), US-M08-06 (mijoz daftari), US-M08-07 (eski daftarni ko'chirish), US-M08-09 (va'da sanasi va eslatma), US-M08-10 (qarzlar hisoboti), US-M08-11 (yetkazib beruvchiga qarz)** | US-M08-03 (AI eslatma, AI-06ga bog'liq) | — |
| M09 Narxlar | US-M09-01 (narx+tarix), US-M09-03 (kassada ko'rish) | US-M09-02 (katta o'zgarish tasdiqlash), US-M09-04 (yorliq chop etish), US-M09-05 (ichki shtrix-kod), US-M09-06 (tarozi shtrix-kodi), US-M09-07 (mijoz kartasida standart chegirma %) | — |
| M10 QQS | US-M10-01 (avtomatik QQS), US-M10-02 (davlat hisobotini solishtirish, 5 ish kuni), US-M10-04 (aylanma solig'i solishtirish) | US-M10-03 (qizil faktura kuzatuv) | — |
| M11 Buxgalteriya | US-M11-01 (avtomatik provodka), US-M11-02 (oy yakuni), US-M11-04 (bank tushumi tasdig'i — yo'ldagi pul → bank, qaror #42) | US-M11-03 (sodda dashboard) | — |
| M12 Hisobotlar | US-M12-01 (kunlik savdo), US-M12-03 (QQS solishtirish eksport) | US-M12-02 (eng ko'p/kam sotilgan) | — |
| M13 Huquqlar | US-M13-01 (xodim+rol), US-M13-02 (bir necha rol birlashuvi), US-M13-04 (admin panel orqali xodim qo'shish), US-M13-05 (bloklash), US-M13-06 (parol/PIN tiklash), US-M13-07 (sessiyalarni ko'rish/bekor qilish), US-M13-08 (platforma admini — qaror #14) | US-M13-03 (limit sozlash) | — |
| M14 Filiallar | US-M14-03 (yangi filial qo'shish), US-M14-04 (aholi punkti toifasi — aylanma solig'i stavkasi) | US-M14-01 (konsolidatsiya) | — |
| M15 Xarajatlar | US-M15-01 (xarajat yozish), US-M15-03 (sof foyda) | US-M15-02 (takrorlanuvchi xarajat) | — |
| M16 Kassa pul harakati | US-M16-01 (qo'yish/olish), US-M16-02 (smena sanash va farq), US-M16-03 (tarix) | — | — |
| M17 Obuna va ro'yxatdan o'tish | US-M17-01 (ro'yxatdan o'tish + sinov), US-M17-02 (tarif va to'lov), US-M17-03 (kechikkan to'lov siyosati), US-M17-04 (ichki admin) | — | — |
| M18 Bildirishnomalar / Telegram bot | US-M18-01 (ulash), US-M18-02 (kunlik hisobot) | US-M18-03 (ogohlantirishlar) | US-M18-04 (botda AI savol) |

*Izoh: bu jadvaldagi Should/Could ajratmasi modulning MVP'da bo'lish-bo'lmasligiga ta'sir qilmaydi (hammasi MVP ichida) — faqat qaysi hikoya birinchi, qaysi biri ikkinchi navbatda qurilishini ko'rsatadi. Qabul mezoni ("Must ro'yxati 18 modulni qoplaydi") bajarilgan — jadvaldagi har bir modulda kamida bitta Must band bor.*

*MVP'dan keyinga surilgan hikoyalar — yagona, yuqoridagi jadval bilan ziddiyatsiz ro'yxat (qaror #33): **US-M03-02** (avtomatik chegirma qoidasi), **US-M14-02** (narx/chegirma nusxalash), **US-M08-08** (mijozga SMS/Telegram), **US-M17-05** (to'liq eksport) — bu to'rttasi yuqoridagi jadvalda ko'rsatilmaydi (`27-backlog.md` bilan muvofiq). US-M04-04 (3)-yo'l (AI-03) MVP ichida (qaror #16). Qolgan barcha Should/Could hikoyalar (shu jumladan US-M14-01, US-M04-03) MVP bosqichlarida.*

*M19 (1C integratsiyasi) bu jadvalda yo'q — MVP'dan keyin, Bosqich 7 (1.4-bo'lim).*

*US-M10-04 (aylanma solig'i solishtirish) va US-M07-04 (yetkazib beruvchiga to'lov) Must darajasida: (a) aylanma solig'i — QQS va aylanma solig'i rejimlari **teng darajada** qo'llab-quvvatlanadi (qaror #32), segmentning aniq ulushi pilotda o'lchanadi (3.2-bo'lim, pilot ko'rsatkichi); (b) yetkazib beruvchiga to'lov — US-M10-03 (qizil faktura QQS krediti to'lovdan keyin) va US-M11-02 (oy yopish, Must) to'g'ridan-to'g'ri shu to'lov holatiga bog'liq, to'lovsiz bu ikkisi to'liq ishlay olmaydi.*

### 1.2 AI funksiyalar (AI-nn)

`spec/kod-uchun/09-ai-funksiyalar.md`dagi "Hukm" ustuniga asoslanib (MVP → Should/Could, Keyingi bosqich/Hozircha real emas → Won't):

| AI ID | Funksiya | MoSCoW | Sabab |
|---|---|---|---|
| AI-01 | Umumiy biznes savol-javob chat | **Should** | Qimmatli farqlovchi, lekin asosiy savdo/ombor/soliq jarayoni AI'siz ham ishlaydi (`09-ai-funksiyalar.md`, AI-01) |
| AI-05 | Davlat hisoboti tafovutini tushuntirish | **Should** | Markaziy oqim (M10/US-M10-02) kod darajasida Must; AI-05 shu natijaning ustiga qo'yilgan tabiiy-til tushuntirish qatlami — hal qiluvchi funksiya emas, qo'shimcha qiymat (`09-ai-funksiyalar.md`, AI-05) |
| AI-03 | Qog'oz hujjat OCR (pilot bilan, torroq qamrov) | **Should** | Qamrov tor (faqat qog'oz/texnik uzilish holatlari), kirill-lotin aralash aniqlik tasdiqlanmagan, pilot talab qiladi (`09-ai-funksiyalar.md`, AI-03, Chegaralar); asosiy savdo/ombor jarayoni AI-03'siz ham ishlaydi (qo'lda/Excel-CSV kiritish muqobili bor), shuning uchun Must emas — lekin MVP bosqichlarida quriladi |
| AI-06 | Nasiya eslatma matni | **Could** | Qiymatli, lekin M08 (nasiya) asosiy funksiyasi (limit, qarz yozish) AI'siz ham to'liq ishlaydi; AI faqat matn yozadi (`09-ai-funksiyalar.md`, AI-06) |
| AI-02, 04, 07, 08, 09, 10, 11 | STT, qo'lyozma OCR, anomaliya, bank kategoriyalash, talab bashorati, narx optimallashtirish, TTS brifing | **Won't** | Barchasi `09-ai-funksiyalar.md`da "Keyingi bosqich" yoki "Hozircha real emas" deb manbali asoslangan |

### 1.3 Won't ro'yxati (MVP'dan tashqarida)

| Band | Sabab/manba |
|---|---|
| Kadrlar/ish haqi moduli | MVP 18 modul ro'yxatida yo'q (`spec/README.md`; M15 faqat "ish haqi to'landi" summasini xarajat sifatida yozadi, ish haqi hisoblanmaydi); JShDS/ijtimoiy soliq hisobotini solishtirish shu sababli ham MVP'dan tashqari (`03-modullar-talablari.md`, M10 qamrov eslatmasi) |
| CRM/sodiqlik (mijozlar bazasi, loyallik/bonus karta dasturi) | `00-xulosa-va-ochiq-savollar.md`, Asosiy xulosa #2; M03'dagi loyallik bonusi ham shu sababli olib tashlangan (`03-modullar-talablari.md`, M03) |
| Ishlab chiqarish (retsept, ishlab chiqarish buyurtmasi) | `00-xulosa-va-ochiq-savollar.md`, Asosiy xulosa #2 |
| Boshqa tizimlardan ma'lumot ko'chirish konnektorlari | MVP'dan tashqarida — tizim noldan (from-scratch) qurilgan, mustaqil mahsulot; yadro tashqi buxgalteriya/ERP tizimlariga bog'liq emas. 1C bilan bog'lanish — faqat alohida **1C integratsiya moduli** (M19) orqali, faqat **ERP → 1C yozish**, MVP'dan keyin Bosqich 7 (qaror #36, #37; 1.4-bo'lim); 1C → ERP ko'chirish/migratsiya yo'q. Boshlang'ich ma'lumot kiritish (onboarding) faqat uch yo'l bilan: (1) qo'lda kiritish, (2) Excel/CSV shablon orqali import, (3) AI-03 yordamida qog'oz hujjat/fotosidan kiritish (qaror #16) |
| Mol-mulk va yer solig'i hisobotini solishtirish | Asosiy vositalar hisobi MVP'da yo'q, shu sababli bu hisobotlarni solishtirish mazmunsiz (`03-modullar-talablari.md`, M10 qamrov eslatmasi) |
| AI-02, 04, 07, 08, 09, 10, 11 (yuqoridagi 1.2-jadval) | `09-ai-funksiyalar.md` |
| M19 1C integratsiyasi | MVP'da yo'q — **MVP'dan keyin, Bosqich 7** (1.4-bo'lim) |

### 1.4 MVP'dan keyin (Bosqich 7) — M19 «1C integratsiyasi»

`33-1c-integratsiya.md` (§2, §17.1), qaror #36–#42. Bosqich 7 — MVP'dan keyingi birinchi bosqich, pilot do'konlar bilan birinchi navbat (`27-backlog.md`).

| Band | Qiymat |
|---|---|
| Hikoyalar | US-M19-01…US-M19-18 (`03-modullar-talablari.md`, M19) — hammasi Bosqich 7 da |
| Jarayon / ekranlar | BP-14; BO-22 (sozlamalar va moslashtirish), BO-23 (1C ga yuborish), BO-14 «1C» qatori, hujjat ekranlarida «1C da» belgisi |
| Yo'nalish | ERP → 1C bir tomonlama yozish; 1C'dan faqat moslashtirish, tekshiruv va solishtirish uchun o'qiladi |
| Kanal | Faqat COM — do'kon kompyuteridagi Windows agenti (C# / .NET Framework 4.8, per-user tray, faqat chiquvchi HTTPS); 1C'da hech narsa publish qilinmaydi, OData yo'q (qaror #36, #38) |
| Konfiguratsiya | «1С:Бухгалтерия 8 для Узбекистана», ред. 3.0 (3.0.64+), platforma 8.3/8.5, 32/64-bit, fayl va klient-server baza; litsenziya ПРОФ/КОРП |
| Eksport modeli | Har kassa × kun bitta «Отчет о розничных продажах»; qarzga va yuridik shaxsga sotuv — alohida «Реализация»; rejim standart `full` (kirim, qaytarish, ko'chirish, hisobdan chiqarish, inventarizatsiya, pul hujjatlari), `sales_only` — buxgalter so'rasa (qaror #39) |
| Ma'lumotnomalar | Hech qachon jim yaratilmaydi — faqat ko'rib tasdiqlangandan keyin (`onec.refs.create`); tashkilot va QQS stavkasi hech qachon yaratilmaydi; avto-tasdiq standart o'chiq (qaror #40) |
| Tarif | 99 000 so'm/oy ichida, qo'shimcha to'lovsiz (qaror #41) |
| Kirish sharti | Bosqich 6 tayyor; real bazada pilot oldi testlari P-01…P-22; Authenticode OV kod-imzolash sertifikati (qaror #38) |

**Qamrovdan tashqari** (qaror #41, `33-1c-integratsiya.md` §2.2) — onboarding tekshiruvi aniq aytadi, sotuvdan oldin mijozga ma'lum qilinadi:

| Band | Holat |
|---|---|
| 1C «Базовая» versiyalar | COM yo'q — qo'llab-quvvatlanmaydi (`ONEC_EDITION_NO_COM`) |
| Bulutdagi 1C (1С:Фреш, uzcloud, clobus, ijara) | Qo'llab-quvvatlanmaydi (`ONEC_CLOUD_BASE_UNSUPPORTED`) |
| Tovarni sotish narxida hisoblaydigan bazalar (2920/2980) | Qo'llab-quvvatlanmaydi (`ONEC_SALE_PRICE_ACCOUNTING_UNSUPPORTED`) |
| БП UZ 1.5 / 2.0, o'zi yozilgan konfiguratsiyalar | Qo'llab-quvvatlanmaydi (`ONEC_PROFILE_UNSUPPORTED`) |
| УТ UZ 11, Розница UZ 3.0, УК UZ 3.0 | Keyingi bosqich (profil yo'q) |
| 1C ichiga `.epf`/`.cfe` kengaytma, HTTP-servis, OData | Hech qachon (qaror #36, #41) |
| 1C → ERP yozish/migratsiya, 1C ma'lumotini AI bilan tahlil | Modul qamrovida emas |
| Provodka, QQS registri, tannarx, fiskal cheklar, Z-hisobot, markirovka kodlari, e-faktura obyektlari | 1C ga yuborilmaydi — 1C hujjatni o'zi o'tkazadi (qaror #39) |
| Narx o'zgarishi, qarzni kechish, boshlang'ich qoldiqlar | Bosqich 7 da yuborilmaydi (keyingi bosqich) |
| Smena bo'yicha ОРП, server-PK (Task Scheduler) rejimi, WPAD/PAC proksi | Keyingi bosqich |
| Bir filialning ikki 1C bazasiga parallel yozilishi | Taqiq |

---

## 2. Raqobatchilardan farqlar

| Raqobatchi(lar) | Ularda yo'q/zaif | Bizning MVP javobi | ID |
|---|---|---|---|
| BILLZ, MoySklad, HIPPO, Bito ERP, mDokon, iiko, Poster POS (7/9 tekshirilgan mahsulot) | Rasmiy sahifada AI funksiyasi haqida hech qanday da'vo yo'q; faqat REGOS (Pro tarif) va Smartup (fotodan tovar tanish)da bor, ular ham tor qamrovda (`research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`, 2-bo'lim) | O'zbek tilida biznes savol-javob chat, hujjat OCR, soliq tafovutini tushuntirish, nasiya eslatma matni | AI-01, AI-03, AI-05, AI-06 |
| REGOS, MoySklad, HIPPO (3/9) | Nasiya/qarz moduli rasmiy sahifada aniq ko'rsatilmagan (`06-raqobatchilar-texnik-va-uskunalar.md`, 2-bo'lim — "bu yo'q degani emas, balki marketing sahifasida tilga olinmagan" degan ehtiyot bilan) | Nasiya markaziy MVP moduli: kredit limiti, qisman/to'liq to'lov, AI eslatma | US-M08-01…04 |
| Butun bozor (markirovkalangan tovar sotuvchilari) | Markirovka skanerlari "muntazam ishlamaydi", mahsulot narxini 2-4% oshiradi, jarima 2-20% aylanmaga (`research_notes/texnik/11-raqobatchilar-kamchiliklari.md`) | Aniq MVP siyosati: kod fiskal chek ichida OFD orqali ketadi, oldindan tekshiruv `MARKING_PRECHECK=warn`, lokal takror-kod nazorati (qaror #62); kirimda qabul xabarnomasi muddatini (3 ish kuni / 72 soat) kuzatish va ogohlantirish; qabul paytidagi skanerlash xatosini aniq ko'rsatish | US-M01-03, US-M07-02 |
| MoySklad, Poster POS (import/xorijiy tizimlar) | Zaif telefon support, shartlar/narx beqarorligi, geopolitik to'xtatish xavfi (hisob muzlatish, mintaqaviy bloklanish) — **taxmin/qamrov eslatmasi**: bu shikoyatlar (`research_notes/texnik/11-raqobatchilar-kamchiliklari.md`) asosan Rossiya/Qozog'iston bozoridagi sharhlardan (otzovik.com, startpack.ru) olingan; O'zbekistondagi aynan shu mahsulotlar foydalanuvchilariga tatbiqi mustaqil tasdiqlanmagan. (ЮKassa O'zbekiston raqobatchisi sifatida `06-raqobatchilar-texnik-va-uskunalar.md`da yo'q — jadvaldan olib tashlandi.) | Mahalliy (O'zbekistonda) joylashgan xizmat, o'zbek tilidagi support — Telegram, har kuni 09:00–21:00 + "kassa ishlamayapti" shoshilinch liniyasi (5.1-bo'lim) | — |
| Barcha 9 tekshirilgan mahsulot | Davlat tuzgan soliq hisobotini ichki hisob bilan avtomatik solishtirish funksiyasi haqida hech birining rasmiy sahifasida da'vo topilmadi | Markaziy MVP oqimi: QQS/aylanma solig'i hisobotini **5 ish kuni** ichida solishtirish | US-M10-02, AI-05 |

*Eslatma (oxirgi qator uchun taxmin belgisi): bu talab 2026-01-01'dan boshlangan juda yangi davlat talabi; raqobatchilarning bu funksiyani hali reklama qilmagani ularda **umuman yo'qligini** mustaqil tasdiqlamaydi — faqat `06-raqobatchilar-texnik-va-uskunalar.md` va `11-raqobatchilar-kamchiliklari.md` tekshirilgan sahifalarida bu haqida hech qanday matn topilmaganini bildiradi.*

**Pozitsiyalashni aniqlashtirish**: MoySklad o'z rasmiy saytida "Регистрация продаж в налоговой Узбекистана через один клик" (OFD) va AslBelgisi (markirovka) integratsiyasini ochiq da'vo qiladi, Didox orqali e-faktura ham bor; REGOS ham Didox bilan integratsiyalangan — ya'ni raqobatchilar bu davlat tizimlari bilan umuman integratsiya qilmagan, degan tezis noto'g'ri. To'g'ri farqlanish: (1) tizimda bu integratsiyalar **bitta tizim ichida**, uchinchi tomon kassa/EDO dasturisiz; (2) **davlat tuzgan soliq hisobotini ichki hisob bilan solishtirish** (yuqoridagi jadval qatori) — bu haqiqatan hech bir raqobatchida yo'q, chunki bu 2026-01-01'dan boshlangan butunlay yangi talab; (3) offline-first + markirovka maxsus holatlari; (4) o'zbek tilidagi AI. Batafsil: `tuzatishlar-va-yechimlar.md`.

---

## 3. Muvaffaqiyat o'lchovlari

### 3.1 Mahsulot o'lchovlari

| O'lchov | Maqsad qiymat | Holat/manba |
|---|---|---|
| Offline chekning OFD'ga yetib borish muddati | 48 soatdan oshmasligi — **100%** | Qonuniy majburiy chegara, manbali (`research_notes/texnik/02-kassa-ofd-markirovka.md`, 1-ilova 31-band) |
| Markirovkalangan tovar kirimida qabul xabarnomasi muddati | Tovar guruhi muddatidan (umumiy 3 ish kuni; suv/ichimlik, dori, o'simlik yog'i — 72 soat) oshmasligi — **100%** | Qonuniy majburiy chegara (VM 833 66–67-band; VM 631, VM 149, VM 23 sxemalari — `research_notes/ochiq-savollar/P2-efaktura-markirovka.md`, OQ-027) |
| Filiallararo ko'chirishda avtotransportda tashishdan oldin e-TTN | **100%** | Qonuniy majburiy (VM 249 31-ilova 13, 16-band; qaror #63) |
| O'rtacha chek yaratish vaqti (kassada) | **Taxmin** — manbada aniq raqam yo'q; raqobatchilar ham bu ko'rsatkichni rasmiy sahifalarida e'lon qilmaydi | **O'lchash formulasi**: birinchi tovar skanerlanishidan to'lov tasdiqlanishigacha o'tgan vaqt (soniya), M01 POS event-log vaqt belgilaridan hisoblanadi (ichki telemetriya, tashqi manba yo'q) — pilot davrida o'lchanishi kerak |
| Davlat hisoboti tafovutlarining 5 ish kuni ichida hal qilinish darajasi | **Pilot ko'rsatkichi** — manbada raqam yo'q, chunki bu funksiya hali hech qayerda ishlatilmagan (yangi 2026 talabi) | **O'lchash formulasi**: (5 ish kuni ichida Buxgalter tomonidan tasdiqlangan yoki tuzatish kiritilgan tafovutlar soni ÷ shu davrda aniqlangan jami tafovutlar soni) × 100%, M10 holat jurnalidan (US-M10-02) hisoblanadi — pilot davrida o'lchanishi kerak |
| Markirovka kodi tekshirish muvaffaqiyat darajasi (POS'da) | **Taxmin** | **O'lchash formulasi**: (muvaffaqiyatli tekshirilgan/qabul qilingan markirovka kodlari soni ÷ jami skanerlangan markirovka kodlari soni) × 100%, M01 POS event-logidan kunlik hisoblanadi. Bozorda umumiy skanerlash xatosi qabul zanjirida 80-90% (`00-xulosa-va-ochiq-savollar.md`, 6-band) — bu POS darajasidagi ko'rsatkich uchun faqat kontekst, bizning aniq qiymatimiz mustaqil o'lchanmagan |

### 3.2 Biznes o'lchovlari

| O'lchov | Maqsad qiymat | Holat/manba |
|---|---|---|
| Pilot mijozlar soni (birinchi 3 oy) | **Taxmin** — manbada yo'q | Bozor hujjatida ham aniq raqam yo'q (`research_notes/AI ERP startap Ozbekistonda/00_oldingi_hujjat.md`, "Tekshirilmagan ma'lumotlar") |
| Oylik mijoz yo'qotish (churn) darajasi | **Taxmin** — manbada yo'q | "Mahalliy SME SaaS'da churn darajasi ochiq manbada yo'q, pilot mijozlarda o'lchanishi kerak" (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 1.1-bo'lim, 4-band) |
| Oylik obuna narxi (tarif) | (qaror #22) **Yagona tarif — 99 000 so'm/oy, hammasi narxga kiradi**: 18 modul, 1 virtual kassa (fiskal), AI oylik limiti, Telegram bot. Qo'shimcha kassa — **+39 000 so'm/oy** (qaror #22). Yillik to'lovda −20%, 30 kun bepul sinov. Batafsil — 3.3-bo'lim | Raqobatchilar narxi: `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`, 1-bo'lim jadvali; `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #13 |
| To'lovga tayyorlik (oyiga qancha so'm) | **Taxmin** — manbada yo'q | "20-30 ta do'kon egasi bilan suhbat kerak" (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 1.1-bo'lim, 2-band) |
| NPS/mijoz mamnuniyati | **Taxmin** — manbada yo'q | Pilot davrida belgilanishi kerak |
| Pilot mijozlar rejimlar ulushi (QQS vs aylanma solig'i) (qaror #32) | **Taxmin yo'q — pilot ko'rsatkichi** | **O'lchash formulasi**: (aylanma solig'i rejimidagi tenant soni ÷ jami pilot tenant soni) × 100%, M17 (obuna) onboarding ma'lumotidan (soliq rejimi tanlovi) hisoblanadi; QQS va aylanma rejimlari spec darajasida teng qo'llab-quvvatlanadi (M10, US-M10-02/US-M10-04) — bu ko'rsatkich faqat haqiqiy pilot segmentini kuzatish uchun, ustuvorlikka ta'sir qilmaydi |

### 3.3 Tarif taklifi — yagona tarif (qaror #22)

**Qaror:** uch pog'onali tarif (Start/Biznes/Pro) o'rniga **bitta tarif** — barcha mijoz uchun bir xil narx va to'liq funksiya to'plami. Tamoyil endi "pog'ona bo'yicha arzon" emas, balki **"hammasi bitta narxda, qo'shimcha kassa — alohida haq"**.

| | Narx (so'm/oy) | Kimga | Ichida |
|---|---|---|---|
| **Yagona tarif** | **99 000** | Har qanday hajmdagi do'kon — 1 savdo nuqtasi (1 virtual kassa) bilan boshlanadi | **Barcha 18 modul** (kassa, qaytarish, chegirma, ombor, inventarizatsiya, ko'chirish, xarid, nasiya, narxlar, QQS, buxgalteriya, hisobotlar, huquqlar, filiallar, xarajatlar, kassa pul harakati, obuna, bildirishnomalar), **1 virtual kassa (fiskal, OFD)**, **AI oylik limiti** (AI-01/03/05/06), **Telegram bot**; Bosqich 7 dan — **1C integratsiyasi (M19)** ham shu narx ichida (qaror #41) |
| **Qo'shimcha kassa** | **+39 000**/kassa (qaror #22) | 2-, 3-,...-kassali do'kon, filiallar | Har bir qo'shimcha virtual kassa — har biri soliq organida alohida ro'yxatdan o'tadi va alohida fiskal modulga ega (VMQ-943 1-ilova 16–20-band). Fiskal modul haqi — 1 BHM/yil (440 000 so'm ≈ **36 700 so'm/oy/kassa**, VMQ-943 1-ilova 55-band); hamkor kassasining chakana narxi ~123 600 so'm/oy (Rahmat) — hamkor ulgurji narxi kelgach +39 000 qayta ko'riladi (26 #168) |

- **Yillik to'lov: −20%** (o'zgarmadi). **Sinov muddati: 30 kun bepul** (o'zgarmadi).
- Filiallar/ko'p kassa: bitta obuna ichida istalgancha qo'shimcha kassa qo'shiladi, har biri +39 000 so'm/oy; modul funksiyasi (buxgalteriya, AI, Telegram) hammasi uchun bir xil — kassa soniga qarab cheklanmaydi.
- O'z fiskal kassasi (mustaqil onlayn-NKM) bor do'kon virtual kassa qo'shimchasini olmaydi (`spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md`, (b)-bo'lim, band 3).
- **Raqobatchilar bilan taqqoslash (rasmiy sahifalar, 2026):**

  | Raqobatchi | Narx (so'm/oy) | Izoh |
  |---|---|---|
  | **Bizning yagona tarif** | **99 000** (+39 000/qo'shimcha kassa) | Hammasi bitta narxda — virtual kassa, e-faktura, markirovka, davlat hisobotini solishtirish, AI, Telegram bot |
  | REGOS Start | 69 000 + virtual kassa 75 000 = **144 000** | Virtual kassa alohida haq, bizdan ~45 000 qimmat 1-kassali tenant uchun |
  | REGOS Basic/Plus | 149 000 / 299 000 | Bizning yagona tarifdan 50 000–200 000 qimmat |
  | mDokon | 199 000 dan | Bizdan 2x qimmat |
  | HIPPO Base/Medium/Pro | 247 200 / 412 000 / 618 000 | Bizdan 2,5x–6x qimmat |
  | BILLZ Start/Advanced/Pro | 299 000 / 499 000 / 999 000 | Bizdan 3x–10x qimmat |
  | Multikassa/E-POS (hamkor orqali virtual kassa, pilot yo'li) | ~96 000 so'm/kassa (+~335 000 bir martalik) | Bizning pilotdagi virtual kassa xarajati — mijozga ko'rinmaydi, biz to'laymiz (3.3-bo'lim pastda, pilot bosqichi) |

- **Unit-iqtisod**: 1 kassali tenant xarajati — hosting ~20 500 + AI ~700–5 900 (og'ir tenant ~10 800–18 100; AI-03 standart modeli Haiku 5.5, rasm tokeni ⌈w/28⌉×⌈h/28⌉ — P6 OQ-077) + SMS (Eskiz, 95 so'm/SMS) ~1 900–4 750 + Click/Payme ~1 000 + fiskal modul (pilot bosqichida hamkor haqi, keyin o'z reyestr yo'lida 1 BHM/yil ≈ 36 700) ≈ **60 000–68 000 so'm/oy** → **marja ≈ 31 000–39 000 so'm** (pilotda o'lchanadi — 26 #24 (OQ-098); `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #13). Support xodimi xarajati (~7 mln so'm/oy) dastlabki bosqichda zarar sifatida qabul qilinadi, 300 to'lovchi tenantga yetganda narx qayta ko'riladi (tavsiya #13).
- **Fiskal yo'l (virtual kassa narxining asosi)**: birinchi kundanoq **o'z virtual kassamizni Davlat reyestriga kiritish arizasi** boshlanadi (VMQ-943 4-ilova: operator xulosasi 10 ish kuni va Kiberxavfsizlik markazi ekspertizasi 15 ish kuni arizadan oldin parallel, DSQ qarori 20 ish kuni — reja **35 ish kuni**, eng yomon 45; virtual kassa zaxira mablag'idan ozod); fiskal modul kodi alohida, kam o'zgaradigan paket — fiskal qismdagi har o'zgarish qayta xulosa talab qiladi (2-ilova 6-band); ariza tasdiqlanguncha **pilot (10–20 do'kon)** bitta reyestr hamkori (Multikassa yoki E-POS Communicator) orqali o'tkaziladi, hamkor haqini (≤ ~13 mln so'm, 3 oyga) **biz to'laymiz** — pilot mijozi uchun narx ko'rinmaydi. Xavf: 2026-10-22 dan reyestrdagi onlayn-NKT'ga "ikkilamchi" axborot tizimini QR chek chop etish uchun integratsiya qilish TXKM'ni reyestrdan chiqarish asosi (VMQ-943 3-ilova 25-band, VMQ-393) — "ERP + hamkor kassa" modeli hamkor va DSQ'dan so'raladi (Xat 1, 26 #169). Pilot uskunasi: do'kon Windows kompyuteri (Do'kon agenti — fiskal ko'prik, LAN printer, qaror #60) + USB skaner + 58 mm ESC/POS printer (Xprinter XP-58 klassi), ~0,9 mln so'm/kassa; tarozi va Android POS terminal pilotda shart emas. iOS kassa uchun bulut printer (Epson TM-m30III / Star TSP143IV, Toshkentda ~5,1–7,1 mln so'm) — iOS yo'li asosiy emas, zahira. Ommaviy sotuv o'z reyestrimiz tasdiqlangach boshlanadi; agar reyestr 6 oydan ko'p cho'zilsa — hamkor orqali davom etiladi, qo'shimcha narxi ochiq "o'tkaziladigan to'lov" sifatida ko'rsatiladi (`spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md`, (b)-bo'lim).
- Raqobatchilar narxi har chorakda qayta tekshiriladi; asosiy xabar: **"Hammasi bitta narxda — hech qanday yashirin qo'shimcha haq yo'q, faqat qo'shimcha kassa alohida"**.

---

## 4. MVP'ga kirish uchun bloklovchi tashqi omillar

MVP kodini (Bosqich 0–6) to'liq to'xtatadigan tashqi omil yo'q — har biri port+stub yoki sozlama ortida, javob kelganda migratsiyasiz almashtiriladi (`research_notes/ochiq-savollar/D-qarorlar-va-E-standartlar.md` §5.3). Bosqichlar bo'yicha:

1. **Fiskal integratsiya (Bosqich 5, real adapter):** bulutdan OFD'ga chek yuboradigan ochiq API yo'q — veb-kassa fiskal modulga Do'kon agenti (Local Bridge, do'kon Windows kompyuterida) yoki hamkorning bulut rejimi orqali yetadi (qaror #60). MVP kodi `FISCAL_PROVIDER=fake` bilan yoziladi; iOS'da fiskal chek faqat hamkor bulut rejimida, aks holda iOS — back-office + elektron chek zahira. Arxitektura savoli (lokal ko'prik/bulut rejimi) — Bosqich 3 dan oldin; hamkor protokoli, sertifikatlash va narx — 26 #109 (OQ-012).
2. **Asl belgisi (CRPT Turon) (Bosqich 5):** chakana sotuv va xaridordan qaytarishda kod fiskal chek ichida OFD orqali ketadi — sotuv uchun CRPT API kerak emas (qaror #62). CRPT API faqat kirim qabuli, tekshiruv, yetkazib beruvchiga qaytarish va hisobdan chiqarish uchun (`MarkingPort` stub, `MARKING_PRECHECK=warn`) — 26 #40 (OQ-025).
3. **Virtual kassa reyestri (Bosqich 0 dan ariza):** muddat — 35 ish kuni (eng yomon 45), zaxira mablag' talab qilinmaydi; Kiberxavfsizlik markazi ekspertizasi va sertifikat narxi noma'lum — byudjetda zahira — 26 #42 (OQ-011).
4. **Davlat hisobotini dasturiy olish (Bosqich 5/6):** ommaviy API yo'q — MVP'da Buxgalter faylni kabinetdan yuklab tizimga yuklaydi (yakuniy MVP qarori) (26 #41). Tuzatish mexanizmi aniq: 5 ish kuni ichida kabinetda tasdiqlash yoki tuzatib taqdim etish (SK 81-modda 6–8-qism).
5. **E-IMZO (Bosqich 0 dan shartnoma arizasi):** prod uchun API-KEY (har prod domen uchun alohida), VPN-kalit va E-IMZO-SERVER litsenziyasi — "Yangi texnologiyalar" (yt.uz) shartnomasi; imzolash bitta umumiy domenda; dev/test — TestCA va "Режим разработчика" bilan bloklanmaydi. Narx va muddat so'rov bilan — 26 #118 (OQ-028).
6. **Foydalanish shartlari (oferta) va AI'ga uzatish roziligi (Bosqich 6 oxiri — birinchi real tenantdan oldin):** ro'yxatdan o'tishda shartlar va chegaradan tashqari uzatishga rozilik qayd etiladi, AI'ga shaxsiy maydonlar maskalanadi (qaror #61); yurist imzolagan yakuniy matn — 26 #127 (OQ-042).

ЗРУ-764 bo'yicha majburiy ekspertiza va sertifikatlash bizga tegishli emas (tizim KAI reyestrida yo'q — `research_notes/ochiq-savollar/P4-huquq-hosting.md` §1); yagona tegishli talab — 3-banddagi reyestr ekspertizasi.

---

## 5. Qo'llab-quvvatlash (support) va xavfsizlik testi rejasi

### 5.1 Support modeli

- **Kanal:** Telegram (mavjud botda "/yordam" buyrug'i) + bitta telefon raqami.
- **Ish vaqti:** har kuni 09:00–21:00 + "kassa ishlamayapti" shoshilinch liniyasi (fiskal/OFD, markirovka, bloklanish) — 48 soatlik OFD muddati va 48 soatlik kassa bloki (qaror #43) dam olish kunlarini ham qamraydi.
- **Javob muddati (SLA):** shoshilinch liniya — **15 daqiqa** ichida birinchi javob; oddiy savol — **24 soat ichida**.
- **Manba:** kanallar (Telegram+telefon) — BILLZ/mDokon amaliyotiga mos (mDokon — 24/7 Telegram); soatlar va javob maqsadi — standart, asoschi yuklamasi pilotda o'lchanadi (26 #24 (OQ-098); `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #12).

### 5.2 Pentest (xavfsizlik testi) rejasi

- **Pilotdan oldin:** bepul avtomatik skaner (OWASP ZAP) + ichki OAuth/to'lov/fiskal tekshiruv ro'yxati.
- **Ommaviy sotuvdan oldin:** mahalliy firma (Celion yoki ONESEC, Toshkent — ikkalasidan narx so'rab) orqali OWASP ASVS L2 bo'yicha to'liq pentest (veb, API, OAuth, Android).
- **Byudjet rezervi:** ~60 mln so'm (~$5 000), xalqaro oraliqdan (~$1 500–7 000) kelib chiqib (taxmin, ishonch o'rta-past — narx manbasi xalqaro, mahalliy firmalar narxni ochiq bermaydi).
- Keyin tekshiriladi: Celion/ONESEC rasmiy takliflari. ЗРУ-764 bo'yicha majburiy sertifikatlash bizga tegishli emas (P4 OQ-039); virtual kassa reyestri uchun Kiberxavfsizlik markazi ekspertizasi alohida (4-bo'lim, 3-band) (`spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #14).

---

## Ochiq savollar

Faqat tashqi javob kutayotgan bandlar (raqamlar barqaror):

- **3.** Tashqi javob kerak: biznes o'lchovlari (3.2-bo'lim), unit-iqtisod va support yuklamasi — interim: joriy maqsadlar, telemetriya birinchi kundan; pilot 30 kun bilan tasdiqlanadi — 26 #24 (OQ-098).
- **4.** Tashqi javob kerak: virtual kassa reyestri — Kiberxavfsizlik markazi ekspertizasi va sertifikat narxi, 1 BHM fiskal modul haqi har modul uchunmi — interim: byudjetda zahira, jadval 45 ish kuni bilan — 26 #42 (OQ-011).
- **6.** Tashqi javob kerak: fiskal hamkor — lokal ko'prik yoki bulut rejimi, autentifikatsiya, sertifikatlash talabi, kassa boshiga ulgurji narx (+39 000 qo'shimcha kassa narxiga ta'sir), "ikkilamchi tizim" xavfi — interim: `FISCAL_PROVIDER=fake`, Do'kon agenti (qaror #60) — 26 #109 (OQ-012), #168, #169.
- **7.** Tashqi javob kerak: CRPT Turon — oldindan onlayn tekshiruv majburiyligi, `label` formati, hisobdan chiqarish metodi, SaaS integrator kaliti — interim: `MARKING_PRECHECK=warn`, `MarkingPort` stub — 26 #40 (OQ-025).
- **8.** Tashqi javob kerak: foydalanish shartlari (oferta) va AI'ga chegaradan tashqari uzatish roziligi matni — interim: `terms_versions`, `ai_cross_border_enabled=false` rozilikgacha — 26 #127 (OQ-042).
- **9.** Tashqi javob kerak: E-IMZO prod kalitlari (API-KEY, VPN-kalit, E-IMZO-SERVER) narxi va muddati — interim: dev/test TestCA, prod jadvalida ~1 oy bufer — 26 #118 (OQ-028).
- **10.** Tashqi javob kerak: virtual kassa reyestri uchun karta-ekvayring va UzQR integratsiyasi qaysi bosqichda majburiy (VMQ-943 2-ilova 6-band, VMQ-393) — interim: mustaqil terminal + statik UzQR (qaror #64) — 26 #170.

## Manbalar

- `spec/README.md`
- `spec/kod-uchun/03-modullar-talablari.md`
- `spec/kod-uchun/09-ai-funksiyalar.md`
- `spec/kod-uchun/33-1c-integratsiya.md` — M19 qamrovi (§2), Bosqich 7 (§17.1)
- `research_notes/texnik/00-xulosa-va-ochiq-savollar.md`
- `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`
- `research_notes/texnik/11-raqobatchilar-kamchiliklari.md`
- `research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`
- `research_notes/texnik/02-kassa-ofd-markirovka.md`
- `research_notes/AI ERP startap Ozbekistonda/00_oldingi_hujjat.md`
- `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` — 15 ta tasdiqlangan tavsiya, qaror #23 (yagona tarif, fiskal yo'l, CRPT, support, pentest va h.k.)
- `research_notes/ochiq-savollar/` — P1 (OQ-011, OQ-013, OQ-014), P2 (OQ-027, OQ-028), P4 (OQ-039), P6 (OQ-059, OQ-077), D-qarorlar (§5 E-bandlar, OQ-098)
