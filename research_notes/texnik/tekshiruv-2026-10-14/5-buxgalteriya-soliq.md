# Fakt-tekshiruv: buxgalteriya/soliq da'volari

Tekshirilgan sana: 2026-10-14. Manbalar: lex.uz (birlamchi), stat.uz, pivot.uz, techcrunch.com, gazeta.uz va boshqalar (har bir qatorda ko'rsatilgan).

Tekshirilgan fayllar:
- research_notes/texnik/01-erp-modullar-va-malumot-modeli.md
- research_notes/texnik/08-mahsulot-modullari.md
- research_notes/AI ERP startap Ozbekistonda/00_oldingi_hujjat.md
- research_notes/AI ERP startap Ozbekistonda/06_integratsiyalar.md
- spec/01-mahsulot/02-modullar-talablari.md (faqat buxgalteriya/soliq da'volari: QQS, BHMS/NSBU, hisob rejasi)

---

## Muhim xatolar

| # | Fayl:bo'lim | Xato | To'g'risi |
|---|---|---|---|
| 1 | `06_integratsiyalar.md`, "Soliq va Hojxojaliq Hisobi" | "Vergilash stavkalari 2026: ... QQS 15%" | 2026-yilda QQS standart stavkasi **12%** (Soliq kodeksi 258-modda, lex.uz/docs/4674902) — bu qayd eskirgan/noto'g'ri, loyihaning o'z `01-fayl`i buni allaqachon tuzatgan edi, lekin `06-fayl`ning o'zi yangilanmagan. |
| 2 | `01-erp-modullar-va-malumot-modeli.md`, `02-modullar-talablari.md` (M10) | "QQS 12%... 2026-yildan avvalgi 15%'dan tushirilgan" | Tarixiy izoh noto'g'ri: 15%→12% o'tish **2023-yil 1-yanvarda** bo'lgan (gazeta.uz, kun.uz), 2026-yilda stavka shunchaki o'zgarishsiz 12%da qoladi — "2026-yildan tushirilgan" degan ta'rif chalkashtiradi. |
| 3 | `06_integratsiyalar.md`, "Online/Virtual Kassa" | "Muhim qonun: Soliq qo'mitasi Rezolyutsiyasi No. 522 (2019-06-25)" | 522-son qaror (25.06.2019) — elektron hisobvaraq-fakturaga oid, onlayn kassaga **aloqasi yo'q**. Onlayn/virtual kassaning asosiy huquqiy asosi — **VMQ-943 (2019-11-23)**. |
| 4 | `06_integratsiyalar.md`, "Soliq va Hojxojaliq Hisobi" | "Tax Code 2026: 105 ta report electronically report.gov.uz" | Portal nomi xato — bunday domen yo'q; haqiqiy yagona hisobot tizimi **hisobot.gov.uz**. "105 ta hisobot" raqami hech qanday manbada tasdiqlanmadi. |
| 5 | `06_integratsiyalar.md`, "E-invoicing" | "Qonun No. ZRU-1108 (2025-12-25)" — e-hisob-faktura qonuni sifatida | ZRU/O'RQ-1108 (25.12.2025) — bu maxsus e-faktura qonuni emas, **"2026-yilga mo'ljallangan soliq-byudjet siyosati asosiy yo'nalishlari"** haqidagi keng qonun (unda QQS stavkalari ham o'zgargan). Raqam/sana to'g'ri, lekin tavsif noto'g'ri. |

---

## To'liq jadval

| Fayl:bo'lim | Da'vo | Holat | Dalil | Tuzatish |
|---|---|---|---|---|
| `08-mahsulot-modullari.md`, "Ombor qoldig'i" qatori | "4-sonli BHMS 'Tovar-moddiy zaxiralar' faqat 3 usulni ko'rsatadi — identifikatsiyalangan tannarx, AVECO, FIFO; LIFO standartda umuman ko'rsatilmagan" | TO'G'RI | lex.uz/docs/-4890446 = "BHMS №4 'Tovar-moddiy zaxiralar'" (Moliya vaziri buyrug'i №24, 28.05.2020; Adliya ro'yxati №3259, 30.06.2020), 7-bob 62-band: "identifikatsiyalangan tannarxi bo'yicha", "o'rtacha tortilgan qiymat bo'yicha (AVECO)", "FIFO". LIFO so'zi matnda yo'q. | — |
| `01-erp-modullar-va-malumot-modeli.md`, 3.4-bo'lim | Eski NSBU №21: "Moliya vazirligi 103-son buyrug'i, 23.10.2002, Adliya vazirligida 1181-son bilan ro'yxatga olingan"; 2025-01-01'dan amal qilmaydi | QISMAN | lex.uz/ru/docs/417624: buyruq imzolangan sanasi — **09.09.2002**, "23.10.2002" esa Adliya vazirligidagi ro'yxatga olish sanasi (№1181). Hujjat 01.01.2025'dan amal qilmasligi tasdiqlandi. | "23.10.2002" ni buyruq sanasi emas, "Adliya ro'yxatga olish sanasi" deb aniqlashtirish (buyruqning o'zi 09.09.2002) |
| `01-erp-modullar-va-malumot-modeli.md`, 3.4-bo'lim | Yangi NSBU №21: Iqtisodiyot va moliya vazirligi 191-son buyrug'i (14.11.2024), Adliya ro'yxati 3593-son (27.12.2024), 2025-01-01'dan amalda, eskisini almashtiradi | TO'G'RI | lex.uz/ru/docs/7282759: "Приказ №191", "14 ноября 2024 г."; "рег. номер 3593", "27.12.2024"; kuchga kirish 01.01.2025; ilova №2'da eski buyruqlar (shu jumladan 2002-yilgi) bekor qilingan | — |
| `01-erp-modullar-va-malumot-modeli.md`, 3.4-bo'lim | "2025-yil sentyabrida yana tuzatilgan (0870-hisob qo'shilgan)" | TEKSHIRIB BO'LMADI | Faqat ikkinchi darajali manbalarda (buxgalter.uz, bss.uz) topildi; lex.uz'da bu aniq tuzatish hujjatini (taxminan №3593-1) alohida ochib mustaqil tasdiqlab bo'lmadi | Mazmuni ehtimol to'g'ri, lekin birlamchi manbada tasdiqlanmagani aniq belgilansin |
| `01-erp-modullar-va-malumot-modeli.md`, 3.4-bo'lim | ПП-282-son, 15.09.2025, IFRS'ga bosqichma-bosqich o'tish; aniq mezon (aylanma/aktiv) ko'rsatilmagan — ochiq savol | TO'G'RI | lex.uz/uz/docs/7728927: Prezident Qarori №ПП-282, 15.09.2025, "О мерах по совершенствованию системы финансового учета в соответствии с международными требованиями и стандартами". Aniq miqdoriy mezon hujjatda yo'q — "Iqtisodiyot va moliya vazirligi Markaziy bank bilan birgalikda mezonlarni belgilaydi" deb vazirlikka havola qilingan. Reestrga kiritilgandan keyingi yildan hisobotga o'tish, 2-yil oxirida IFRS audit. | — |
| `spec/02-modullar-talablari.md`, M11 (Buxgalteriya) | "NSBU №21 (2024/2025, 191-son buyruq) — eski 2002-yilgi reja emas"; aniq hisob raqamlari berilmagan | TO'G'RI | Yuqoridagi ikki qator bilan izchil — 191-son buyruq (14.11.2024) haqiqatan ham eski 103-son/1181-ro'yxat rejasini 01.01.2025'dan rasman almashtirgan | — |
| `01-erp-modullar-va-malumot-modeli.md` / `02-modullar-talablari.md` (US-M10-01) | "QQS standart stavkasi 12% (Soliq kodeksi 258-modda); 2026-yildan avvalgi 15%'dan tushirilgan" | QISMAN | lex.uz/docs/4674902: 258-modda ("Солиқ ставкалари") 35-bob (QQS)da, joylashuv to'g'ri; 2026-yil uchun 12% tasdiqlangan (ihisobchi.uz). LEKIN: 15%→12% o'tish aslida **2023-yil 1-yanvarda** bo'lgan (gazeta.uz, kun.uz), 2026-yilda o'zgarish yo'q — stavka shunchaki o'zgarishsiz qoladi | "2026-yildan avvalgi 15%'dan tushirilgan" jumlasini olib tashlash yoki "2023-yildan amalda, 2026-yilda o'zgarishsiz qoladi" deb tuzatish |
| `01-erp-modullar-va-malumot-modeli.md` / `08-mahsulot-modullari.md` | "2026-yil 1-yanvardan qishloq xo'jaligi mahsulotlariga (paxta/g'alladan tashqari) 0% QQS" | TO'G'RI | ihisobchi.uz: "2026-yil 1-yanvardan... qishloq xo'jaligi mollar ishlab chiqaruvchilari (paxta va g'alladan tashqari)... 0% QQS stavkasi", O'RQ-1108-son Qonun (25.12.2025) asosida | — |
| `01-erp-modullar-va-malumot-modeli.md` / `08-mahsulot-modullari.md` | "2026-yil 1-iyundan ayrim toifalar (aylanmasi 5 mlrd so'mgacha chakana/umumiy ovqatlanish) uchun ixtiyoriy 6% stavka" | TO'G'RI | ihisobchi.uz: ixtiyoriy soddalashtirilgan 6% stavka "2026-yil 1-iyundan" chakana savdo va umumiy ovqatlanish uchun, aylanmasi 5 mlrd so'mgacha bo'lganlar uchun | — |
| `06_integratsiyalar.md`, "Soliq va Hojxojaliq Hisobi" | "Vergilash stavkalari 2026: Korporativ 15%, shaxsi 12%, EPI 8%, QQS 15%" | QISMAN NOTO'G'RI | pinkod.uz: "Corporate Profit Tax: 15%" va "Personal Income Tax (JSHDS): 12%" — bu ikkisi TO'G'RI. "QQS 15%" — NOTO'G'RI (haqiqiysi 12%, yuqoriga qarang). "EPI 8%" — haqiqiy ijtimoiy soliq/yagona ijtimoiy to'lov stavkalari 12% (byudjetdan tashqari tashkilotlar) / 25% (byudjet tashkilotlari); 8% raqami hech qanday manbada topilmadi | "QQS 15%" → "QQS 12%"; "EPI 8%" qatorini qayta tekshirish yoki olib tashlash — bunday stavka topilmadi |
| Umumiy (aylanma solig'i rejimi) | QQS to'lamaydigan kichik biznes uchun "aylanma solig'i" muqobil rejimi 2026-da ham mavjud | TO'G'RI | azma.uz: "2026-yilda aylanmadan olinadigan soliqning bazaviy stavkasi 4 foiz miqdorida saqlanib qolmoqda" (yillik aylanmasi 1 mlrd so'mgacha bo'lgan subyektlar uchun, ba'zi hududlarda 1%gacha pasaytirilgan) | — |
| Umumiy (IFRS talabi) | Aksiyadorlik jamiyatlari, tijorat banklari, sug'urta tashkilotlari va yirik soliq to'lovchilar 2021-yil natijalaridan boshlab IFRS asosida hisobot tuzishi majburiy | TO'G'RI | PP-4611 (24.02.2020) asosida (bss.uz sharhi) | — |
| `06_integratsiyalar.md`, "Online/Virtual Kassa" | "Muhim qonun: Soliq qo'mitasi Rezolyutsiyasi No. 522 (2019-06-25), qo'shimchasi VMQ-943" | NOTO'G'RI | 522-son qaror (25.06.2019, lex.uz/docs/-4386769) — elektron hisobvaraq-fakturadan foydalanishni takomillashtirishga oid, onlayn kassaga aloqasi yo'q. Onlayn kassaning asosiy huquqiy asosi — VMQ-943 (23.11.2019, lex.uz/docs/4603340) | "522-son"ni olib tashlab, faqat "VMQ-943 (2019-11-23)"ni qoldirish |
| `06_integratsiyalar.md`, "E-invoicing" | "Qonun No. ZRU-1108 (2025-12-25), VMQ-168 (2025-03-18)" | QISMAN TO'G'RI | VMQ-168 (18.03.2025) — to'g'ri, e-hisobvaraq-faktura va e-TTYUXni birlashtiradi. ZRU/O'RQ-1108 (25.12.2025) raqam/sana to'g'ri, LEKIN bu maxsus "e-hisob-faktura qonuni" emas — "2026-yilga mo'ljallangan soliq-byudjet siyosati asosiy yo'nalishlari" haqidagi keng qonun (lex.uz/docs/-7944527) | ZRU-1108'ni "e-hisob-faktura qonuni" deb atashni to'g'rilab, "2026-yil soliq-byudjet siyosati o'zgartirishlar qonuni" deb yozish |
| `00_oldingi_hujjat.md`, "Bozor hajmi" | "1,21 mln kichik biznes subyekti, shundan 479 000 kichik korxona/mikrofirma; YaIMning 52,2%" | TO'G'RI | stat.uz: "As of October 1, 2025, there were 1,212.0 thousand small business entities... of which 479.0 thousand were small enterprises and microfirms... share... 52.2%" | — |
| `00_oldingi_hujjat.md`, "ERP va distribyutsiya" / "Infratuzilma" | "BILLZ: 2025-06-27 TBC Bank 53% ulush $9M ga, jami $12M, baholash $20M" | TO'G'RI | gazeta.uz/spot.uz (27.06.2025): "TBC Bank Group... 53% акций BILLZ... На первом этапе — 53% за $9 млн... сумма сделки до $12 млн... оценка $20 млн" | — |
| `00_oldingi_hujjat.md`, "ERP va distribyutsiya" | "Bito ERP: 2025-dekabr MOST Ventures $10M baholash; 2026-09-24 AloqaVentures $300k" | TO'G'RI | timesca.com/pivot.uz: MOST Ventures bitimi $10M baholashda, 25.12.2025 Toshkentda yakunlangan; spot.uz/aloqabank: Bito 24.09.2026'da AloqaVentures'dan $300k oldi | — |
| `00_oldingi_hujjat.md`, "Infratuzilma va fintech" | "Uzum Business: Uzum $1,5B baholashda $65,5M oldi" | TO'G'RI | TechCrunch (05.08.2025): "Uzum raised $65.5 million... post-money valuation... approximately $1.5 billion" | — |
| `00_oldingi_hujjat.md`, "Investitsiyalar" | "2025: O'zbekiston startaplariga $329M (140 bitim); AI ulushi 24,4%, ERP/CRM/B2B ~10%" | QISMAN TO'G'RI | Pivot.uz/uzdaily.uz: "$329 million", "140" bitim, "AI... 24.4%" — bularning barchasi mos. LEKIN "ERP/CRM/B2B ~10%" aniq shu nom bilan topilmadi — Pivot ma'lumotida boshqa kategoriyalar ko'rsatilgan: "E-Commerce 12,5%" va "SaaS 11,7%" | "ERP/CRM/B2B ~10%" o'rniga "SaaS 11,7%, E-commerce 12,5%" aniq kategoriyalarini ishlatish |
| `00_oldingi_hujjat.md`, "Chakana savdo dasturlari" | "HIPPO: 2025-oktabr Vchasno Group'dan $1M oldi" | TO'G'RI | dev.ua/forbes.ua (21.10.2025): "Ukrainian Vchasno Group invested $1 million in Uzbek startup Hippo" | — |
| `01-erp-modullar-va-malumot-modeli.md` / `08-mahsulot-modullari.md` | MXIK 17 xonali kod tuzilishi: "1-3 guruh, 4-5 sinf, 6-8 pozitsiya, 9-11 subpozitsiya, 12-14 brend, 15-17 belgi" | TO'G'RI | moysklad.uz: "Digits 1-3... group; 4-5... class; 6-8... position; 9-11... subposition; 12-14... brand; 15-17... attribute" — tuzilish aynan mos | — |

---

## Qamrovdan tashqari qoldirilgan/cheklangan tekshiruvlar

- "2025-yil sentyabrida NSBU №21'ga 0870-hisob qo'shilgani" — faqat ikkinchi darajali manbalarda (bss.uz, buxgalter.uz) tasdiqlandi, lex.uz'da aniq tuzatish hujjatini alohida ochib bo'lmadi.
