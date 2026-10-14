# Fakt-tekshiruv: raqobatchilar va bozor hajmi fayllari

*Tekshiruv sanasi: 2026-10-14. Tekshirilgan fayllar: `texnik/06-raqobatchilar-texnik-va-uskunalar.md`, `texnik/11-raqobatchilar-kamchiliklari.md`, `AI ERP startap Ozbekistonda/01_bozor_hajmi.md`, `03_raqiblar_narx.md`, `04_sohalar.md`. Metod: har bir da'voning asl manbasi WebFetch/WebSearch orqali qayta ochildi, aniq iqtibos bilan solishtirildi.*

---

## Muhim xatollar (eng kritik 12 ta)

1. **Valyuta xatosi — REGOS "$869k Pro tier"** (`03_raqiblar_narx.md`, Manbalar): aslida regos.uz/ru/price'da Pro tarif **859 000 so'm/oy** (≈$68 AQSh dollari), DOLLAR EMAS. "$869 000" — raqam ham, valyuta ham noto'g'ri. ~12 700x kattalashtirilgan xato.
2. **Valyuta xatosi — markirovka uskuna xarajati "300–500 ming so'm"** (`11-raqobatchilar-kamchiliklari.md`): gazeta.uz (2026-04-14) asl matnda **"300 ming dollardan ortiq"** va "0,5 mln dollardan ko'proq" deyilgan — SO'M emas, DOLLAR. ~10 000x xato, eng jiddiy topilma.
3. **Asosiy tezisga zid dalil — MoySklad o'z saytida Asl belgisi va OFD integratsiyasini ochiq tasdiqlaydi**: moysklad.uz bosh sahifasida so'zma-so'z "Регистрация продаж в налоговой Узбекистана через один клик" va "Интеграция с Национальной системой цифровой маркировки товаров AslBelgisi" deyilgan. Bu loyihaning "hech bir raqobatchi to'liq soliq integratsiyasini qilmagan" tezisini kamida bitta raqib (marketing darajasida) uchun yolg'onga chiqaradi. Batafsil pastda, alohida bo'limda.
4. **Tasdiqlanmagan da'vo — BILLZ'ning soliq integratsiyalari** (`06-fayl`): billz.io/uz/for-developers sahifasida OFD, e-faktura va Asl belgisi haqida HECH QANDAY matn yo'q — faqat amoCRM/RetailCRM integratsiyasi bor. Hujjatdagi "OFD, e-faktura... Asl belgisi" ustuni manbada tasdiqlanmagan taxmin.
5. **Ichki ziddiyat — BILLZ do'kon soni**: `03_raqiblar_narx.md`'ning o'zida Manbalar bo'limida "1500+ do'kon", jadvalda "4k do'kon" — bitta hujjat ichida ikki xil raqam.
6. **Manbasiz raqamlar — Smartup "19.5k foydalanuvchi, 600+ kompaniya"**: greenwhite.uz/smartup-en sahifasida bu raqamlar umuman yo'q.
7. **Noto'g'ri raqam — MoySklad bepul tarif "2 savdo nuqtasi"**: moysklad.uz/subscription/'da aslida **1 savdo nuqtasi**, 5 xodim.
8. **Noto'g'ri/aloqasiz manba — "12.6% kichik firmalar raqamli (World Bank 2022)"** (`01_bozor_hajmi.md`): havola MDPI akademik maqolasiga (2071-1050/15/13/10696) — bu World Bank hisobotining o'zi emas, noto'g'ri manba ulangan.
9. **Manbada topilmagan raqamlar — e-savdo "$2,649 mln (2025)" / "$680 mln (2023)"** (`01_bozor_hajmi.md`): Unimall.ai'da $1.5 mlrd (2024), WORLDEF'da $1.3 mlrd (sanasi noaniq) — hujjatdagi ikkala raqam ham ikkala manbada topilmadi.
10. **Noto'g'ri raqam — Uzum Business "1.7x o'sish"** (`03_raqiblar_narx.md`): techcrunch.com asl maqolasida kredit o'sishi **3.4x** deyilgan (va "17k sotuvchi" o'rniga maqolada "16,000 merchants").
11. **Ichki mantiqiy ziddiyat — avto ehtiyot qismlar import** (`04_sohalar.md`): "1.44K import shipments (jami)" va "JSC UZAUTO MOTORS... 1,883 shipments (largest buyer)" — 1,883 > 1,440, ya'ni bitta kompaniyaning ulushi "jami"dan katta chiqadi — matematik mumkin emas. Tashqi manbalar (importyeti.com, trademo.com, volza.com) ham bir-biriga zid raqamlar beradi (6,081 / 11,223 / 12,630 shipments) — hech biri hujjatdagi 1,883/1.44K bilan mos kelmaydi.
12. **Fayllar orasidagi ziddiyat — savdo korxonalari soni**: `01_bozor_hajmi.md`: "Savdo (retail+wholesale) 150,695, 32.2%"; `04_sohalar.md`: "164,481 trade businesses, ... largest sector". stat.uz WebSearch natijasi `04_sohalar.md`ning raqamini (164,481, 27.4%) tasdiqlaydi, lekin bu `01_bozor_hajmi.md`dagi raqamdan (150,695, 32.2%) farq qiladi — ikki fayl bir xil ko'rsatkichni turlicha beradi, sana/davr farqi aniqlashtirilmagan.

---

## Asosiy tezis (soliq integratsiyasi) tekshiruvi

**Loyihaning markaziy da'vosi**: "hech bir raqobatchi O'zbekiston soliq tizimlari (OFD/virtual kassa, e-faktura, Asl belgisi markirovka) bilan to'liq integratsiya qilmagan."

Raqobatchilarning o'z rasmiy saytlarini bevosita tekshirganda natija **aralash** chiqdi — tezis bir xilda hamma uchun to'g'ri emas:

| Raqib | Rasmiy sayt OFD/virtual kassa haqida nima deydi | Asl belgisi haqida nima deydi | Xulosa |
|---|---|---|---|
| **MoySklad** | "Регистрация продаж в налоговой Узбекистана через один клик" — so'zma-so'z tasdiqlangan | "Интеграция с Национальной системой цифровой маркировки товаров AslBelgisi" — so'zma-so'z tasdiqlangan | **Tezisga ZID** — MoySklad o'z saytida ikkala integratsiyani ham aniq da'vo qiladi |
| **HIPPO** | "...с 2024 года официально функционирует... как законное... средство виртуальной кассы" — tasdiqlangan (virtual kassa reyestrida) | Sahifada tilga olinmagan | Qisman tezisni qo'llab-quvvatlaydi (markirovka yo'q) |
| **BILLZ** | billz.io/uz/for-developers'da OFD/e-faktura haqida HECH NARSA yo'q | Shu sahifada yo'q | Tezisni qo'llab-quvvatlaydi, lekin hujjat buni noto'g'ri "bor" deb yozgan |
| **Smartup** | Rasmiy sahifada OFD/virtual kassa aniq ko'rsatilmagan | "Integrate with any system" — umumiy, Asl belgisi nomi aniq tilga olinmagan | Tezisni qo'llab-quvvatlaydi, lekin hujjatning "Asl belgisi, Faktura.uz" da'vosi eski/tasdiqlanmagan manbadan |
| **Poster (xorijiy)** | Faqat uchinchi tomon qo'shimchasi (Multikassa, $5–8/oy + $28 bir martalik ulanish) orqali — o'zi mahalliy integratsiyaga ega emas | Yo'q | Tezisni kuchli qo'llab-quvvatlaydi |
| **iiko** | IIKOFISCAL mavjudligi tasdiqlangan, lekin "real vaqtda" tafsiloti mustaqil tasdiqlanmadi | — | Qisman |

**Xulosa**: tezis *aksariyat* mahalliy va xorijiy raqiblar uchun to'g'ri (ayniqsa BILLZ, Poster, Smartup — ularning rasmiy saytlari bu integratsiyalarni aniq da'vo qilmaydi), **lekin MoySklad bu qoidadan aniq istisno** — uning o'z sayti OFD/fiskal ro'yxatga olish va Asl belgisi integratsiyasini bevosita va aniq reklama qiladi. Hujjatlarda bu tezis "hech kim" (universal) shaklida yozilgan joylarni "aksariyat raqiblar, MoySklad bundan mustasno" ga tuzatish tavsiya etiladi.

---

## To'liq jadval

| Fayl:bo'lim | Da'vo | Holat | Dalil | Tuzatish |
|---|---|---|---|---|
| 06:BILLZ narx | Start 299k, Advanced 499k, Pro 999k so'm/oy | TO'G'RI | billz.io/uz/prices — aynan shu uch raqam | — |
| 06:BILLZ integratsiya | OFD, e-faktura, Payme/Click/Uzum, Asl belgisi | NOTO'G'RI | billz.io/uz/for-developers'da bu integratsiyalar yo'q, faqat amoCRM/RetailCRM bor | "⚠ manbada topilmadi, tasdiqlanmagan" deb belgilash |
| 03:BILLZ do'kon soni | "1500+ do'kon" (Manbalar) vs "4k do'kon" (jadval) | NOTO'G'RI (ichki ziddiyat) | Bitta faylda ikki xil raqam | Bitta raqamga kelish yoki ikkisini "tasdiqlanmagan" deb belgilash |
| 03:BILLZ/TBC bitimi | "$9M stake, $20M valuation, 53%" | TO'G'RI | theasianbanker.com: "$9 million for 53%... post-money valuation of $20 million... up to $12 million" ($12M — kelajakdagi maksimal, ziddiyat emas) | — |
| 06:REGOS narx | Start 69k, Basic 149k, Plus 299k/254.6k, Pro 859k/687.2k, EasyTrade 7.2mln/10.5mln | TO'G'RI | regos.uz/ru/price — aynan mos | — |
| 06:REGOS virtual kassa qo'shimchasi | "+75k/oy" | QISMAN | Sahifada bu band topilmadi — "texnik xizmat 100k/oy", "fiskal adapter o'rnatish 250k" bor | Band nomini aniqlashtirish yoki "topilmadi" deb belgilash |
| 06:REGOS AI-yordamchi | "AI-yordamchi... Pro tarifida MCP" | QISMAN | MCP narx jadvalida tasdiqlangan, lekin "AI-yordamchi" tasviri narx sahifasida yo'q | Manba aniqlashtirish kerak |
| 03:REGOS Pro tarif | "$869k Pro tier" | NOTO'G'RI | regos.uz: Pro = 859 000 **so'm**/oy (≈$68), dollar emas | "859 000 so'm/oy" ga tuzatish |
| 03:REGOS do'kon soni | "5000+ do'kon" | TEKSHIRIB BO'LMADI | regos.uz'da bu raqam umuman yo'q, WebSearch ham tasdiqlamadi | Manbasiz deb belgilash |
| 06/03:Smartup narx | 120 000 so'm/foydalanuvchi/oy | TO'G'RI | greenwhite.uz/smartup-en: "120 000 sum/month" | — |
| 03:Smartup mijozlar | "19.5k foydalanuvchi, 600+ kompaniya" | NOTO'G'RI | greenwhite.uz'da bu raqamlar yo'q | Manbasiz/tasdiqlanmagan deb belgilash |
| 06:Smartup integratsiya | "SAP, Asl belgisi, Faktura.uz" | QISMAN | Joriy saytda faqat umumiy "Integrate with any system" bor, aniq nomlar yo'q (eski manbadan meros) | "(eski manba, joriy saytda tasdiqlanmagan)" izohi qo'shish |
| 06:MoySklad bepul tarif | "2 savdo nuqtasi, 5 xodimgacha, muddatsiz" | NOTO'G'RI | moysklad.uz/subscription/: aslida **1 savdo nuqtasi**, 5 xodim | "1 savdo nuqtasi" ga tuzatish |
| 03:MoySklad mijoz soni | "1k client 2024" | NOTO'G'RI | moysklad.uz/subscription/'da bu raqam yo'q | Manbasiz deb belgilash |
| 06:MoySklad soliq integratsiyasi | E-POS, Asl belgisi, Uzum/Click/Payme/Didox | TO'G'RI | moysklad.uz: "Регистрация продаж в налоговой Узбекистана", "Интеграция... AslBelgisi" — so'zma-so'z | **Asosiy tezisga zid dalil** — yuqoridagi bo'limga qarang |
| 06:HIPPO narx | Base 247.2k, Medium 412k, Pro 618k so'm/oy | TO'G'RI | hippo.uz/ru/pos — aynan mos | — |
| 06:HIPPO virtual kassa | "2024-yildan reyestrda" | TO'G'RI | hippo.uz: "с 2024 года официально функционирует... как... средство виртуальной кассы" | — |
| 06:HIPPO nasiya | "nasiya moduli ko'rsatilmagan" | TO'G'RI | Sahifada bunday modul yo'q | — |
| 06:Bito ERP modullar | Savdo/CRM/ta'minot/HR/logistika/ombor/analitika; Click/Payme/Play Mobile/amoCRM/kuryer | TO'G'RI | bito.uz — barchasi mos | — |
| 06:Bito ERP nasiya | "nasiya/kredit savdosi aniq biznes turi sifatida qo'llab-quvvatlanadi" | NOTO'G'RI | bito.uz'da kredit/nasiya haqida hech narsa topilmadi | "Tasdiqlanmagan" deb belgilash |
| 06:Bito ERP narx | "300 000 so'mdan" (eski tadqiqot) | TEKSHIRIB BO'LMADI | Joriy saytda aniq summa yo'q, faqat aksiya matni | "Eski manba, joriy saytda ko'rsatilmagan" deb qoldirish |
| 00/06:Bito ERP mijozlar | 600+ / 2000+ ziddiyati | QISMAN (uchinchi raqam tasdiqlandi) | bito.uz: "1000+ mijozlar" — uchinchi, yangi raqam | Uch xil raqam (600+/1000+/2000+) borligini aniq qayd etish |
| 06:mDokon narx | 199k/299k/399k so'm/nuqta/oy | TO'G'RI | mdokon.uz — aynan mos | — |
| 06:mDokon nasiya | "yuqori tarifda" | QISMAN | Aslida Business (o'rta, 299k) tarifdan boshlab mavjud | "O'rta va yuqori tarifda (Business'dan boshlab)" ga tuzatish |
| 06:mDokon offline | "sotuvlar odatdagidek o'tadi... internet tiklanishi bilan sinxronlashadi" | TO'G'RI | mdokon.uz — deyarli so'zma-so'z mos | — |
| 06:iiko narx (⚠) | 484–500k / 1.01–1.05mln / 1.35–1.39mln (dilerlardan) | TO'G'RI | kafesoft.uz: 500k/1 012 500/1 350 000; soft24.uz/itdo.uz ($ dan o'girilganda) ham shu oraliqda | Hujjatning o'z ⚠ ogohlantirishi (rasmiy emas, diler narxi) ham to'g'ri |
| 06:iiko IIKOFISCAL | "OFD'ga real vaqtda uzatish" | TEKSHIRIB BO'LMADI | Sahifa to'g'ridan-to'g'ri ochilmadi (xavfsizlik bloki); mavjudligi tasdiqlandi, "real vaqtda" so'zi mustaqil tasdiqlanmadi | — |
| 06:Poster fiskalizatsiya | "E-POS $10/oy, Multikassa $5/oydan" | QISMAN | Multikassa: $28 bir martalik + $8/oy xizmat + $5/oy integratsiya (joinposter.com) — "$5/oydan" to'g'ri, lekin jami xarajat yuqoriroq; E-POS $10/oy birlamchi manbadan to'liq tasdiqlanmadi | Multikassa uchun to'liq xarajat tarkibini ko'rsatish |
| 03:Paloma365 narx | "$9–54/oy, 20k businesses" | NOTO'G'RI | paloma365.com/en/tariffs: narxlar so'mda (134.7k/224.5k/269.4k/314.3k), dollar yo'q; "20k businesses" topilmadi | So'm narxlariga va manbasiz "20k" ni olib tashlashga tuzatish |
| 03:Paloma365 "o'rta tarif" | "134.7k — o'rta tarif" | NOTO'G'RI | 134 700 — eng PAST tarif (Startup), o'rta emas | "Eng past tarif" deb tuzatish |
| 00:Paloma365 kelib chiqishi | "Qozog'iston kelib chiqishi — hal qilinmadi" (ochiq savol) | ✅ HAL QILINDI | paloma365.com: Astana vaqti, +7 (747) kod, Kaspi.kz to'lovi, Qozog'iston banklari | Ochiq savollar ro'yxatidan olib tashlash, "Qozog'iston mahsuloti" deb belgilash |
| 06:Hardware — MERTECH CL-2310 | 1 500 000 so'm | TO'G'RI | mertech.uz — aynan mos (chegirmali narx) | — |
| 06:Hardware — UZKASSA N5 | 3 315 000 so'm, Android 7.1 | TO'G'RI (URL eskirgan) | Asl URL 404/redirect beradi, lekin kesh/boshqa sahifada raqam tasdiqlangan | URL'ni yangilash |
| 06:Hardware — Xprinter XP-58IIT | 225 000 so'm | NOTO'G'RI/eskirgan | glotr.uz'da bu model/narx topilmadi; joriy narx ~297k–360k so'm | Narxni 297k–360k oralig'iga yangilash |
| 11:Nazorat kassa | "'400 dan ortiq qoidabuzarlik holatlari topilgan'" (tirnoqli iqtibos) | QISMAN | kun.uz/28393917: "bir hafta davomida 400 dan ortiq tekshirish o'tkazilib, barchasida qoidabuzarlik aniqlangan" — mazmunan to'g'ri, lekin so'zma-so'z iqtibos emas | Tirnoqdan chiqarib parafraz sifatida berish |
| 11:Markirovka uskuna xarajati | "300–500 ming SO'M" | NOTO'G'RI | gazeta.uz (2026-04-14): "300 ming DOLLARDAN ortiq", "0,5 mln dollardan ko'proq" | "300–500 ming AQSH DOLLARI" ga tuzatish (10 000x farq) |
| 11:Markirovka narx oshishi | "mahsulot narxi 2–4% oshgan" | TO'G'RI | gazeta.uz: "2−4 foizli qimmatlashuvga duch kelyapmiz" | — |
| 11:Markirovka jarimalari | "2–20% jarima... bitta xodimning xatosi... bankrotlik" | TO'G'RI | gazeta.uz (2026-03-31): Soliq kodeksi 227-1-modda, ombudsman vakili: "2 foizdan 20 foizgacha... 100 foiz bankrotlik degani" | — |
| 11:MoySklad telefon qo'llab-quvvatlash | "Отсутствует телефонная техподдержка" | TEKSHIRIB BO'LMADI | startpack.ru 403 bilan to'g'ridan-to'g'ri ochilmadi; boshqa qidiruv orqali mazmunan tasdiqlandi | — |
| 11:MoySklad narx oshishi | "Цены повышают, функционал... отдельную плату" | TO'G'RI | otzovik.com: to'liqroq matn ("который раньше входил в основной тариф") — qisqartirilgan, lekin mazmun saqlangan | — |
| 11:Poster RF kirish uzilishi | "После начала стычек с Украиной..." | QISMAN | startpack.ru'da aniq "с Украиной" emas, "с их страной" deyilgan — kontekst (Poster, 2022) mos keladi | Aniq iqtibosni "с их страной" deb tuzatish |
| 11:YUKassa eslatmasi | Oldingi versiyada RF-faqat shikoyat xato kiritilgan, olib tashlangan | TO'G'RI | Joriy versiyada qoldiq instansiya topilmadi | — |
| 01:Kichik biznes subyektlari | 1,208,341 / 507,138 / 701,203 (2026-04-01) | TO'G'RI | stat.uz press-relizi — aynan mos | — |
| 01:Yuridik shaxslar | 471,700 (2025-12-01), 85.1%/401,500 | TEKSHIRIB BO'LMADI/shubhali | Manba URL yo'q; topilgan yaqin raqam (570,400, 2024-01-01) kattaroq va teskari yo'nalishda | Aniq manba topish yoki olib tashlash |
| 01:Sohalar jadvali | Savdo 150,695/32.2%, va h.k. (umumiy "stat.uz" citation) | TEKSHIRIB BO'LMADI | Aniq URL yo'q; topilgan yaqin raqamlar (32.7%, 151,443) to'liq mos emas | Aniq URL/sana qo'shish |
| 01:QQS to'lovchilari | 201,000+ (2025-01-01, +5.7%) | TO'G'RI | kun.uz: "exceeded 201,000... 5.7% increase" | — |
| 01/04:Didox "250,000 kompaniya" | Tasdiqlanmagan deb belgilangan | TEKSHIRIB BO'LMADI (to'g'ri belgilangan) | didox.uz'da raqam yo'q; uchinchi tomon manbalar ziddiyatli (250k vs 350k) | Status o'zgarmaydi, lekin 04-faylda bu raqam "fakt" sifatida qayta ishlatilgan — u yerda ham ⚠ belgisi qo'shish kerak |
| 01:Raqamlashtirish 12.6% | "World Bank 2022 MSME" → MDPI havolasi | NOTO'G'RI | MDPI (2071-1050/15/13/10696) — akademik maqola, World Bank hisobotining o'zi emas | To'g'ri World Bank hisobotiga havola topish |
| 01:OECD 51.2%/26% | OECD 2023 hisoboti | TEKSHIRIB BO'LMADI | PDF o'qib bo'lmadi (binary) | Qo'lda PDF matnini tekshirish kerak |
| 01:"70% startaplar SaaS" | 2025 | TEKSHIRIB BO'LMADI | Hech qanday aniq manbada topilmadi | Manbasiz deb belgilash |
| 01:Buxgalter maoshi | "6–7 mln so'm (2026)" | QISMAN | Flexa.jobs: "6.8 mln so'm" — mos; Paylab.uz: 4.0–16.8 mln, o'rtacha (5 yil tajriba) 12.7 mln — ancha kengroq/yuqoriroq | Diapazonni kengaytirish yoki manba nomuvofiqligini qayd etish |
| 01:E-savdo | "$2,649 mln (2025)" / "$680 mln (2023)" | NOTO'G'RI | Unimall.ai: $1.5 mlrd (2024); WORLDEF: $1.3 mlrd (sana noaniq) — ikkala raqam ham manbalarda topilmadi | Raqamlarni manbaga mos qayta yozish yoki olib tashlash |
| 01:Farmatsevtika hajmi | "$204.9 mln (2025-09), +36.4% yoy" | TO'G'RI | timesca.com — aynan mos | — |
| 01:Farmatsevtika zanjir ulushi | "40.6% savdolari (2025-Q1), 70% mustaqil" | NOTO'G'RI | timesca.com maqolasida bu raqamlar umuman yo'q | Manba topish yoki olib tashlash |
| 01:TAM/SAM/SOM | BILLZ 4k + REGOS 5k + Bito 2k = 11k | QISMAN | Arifmetika to'g'ri, lekin kirish raqamlari (BILLZ 4k/1.7k, Bito 600+/1000+/2000+) loyihaning o'z fayllarida "hal qilinmagan ziddiyat" deb belgilangan; past variantlar olinsa SOM ~7,300 (≈34% past) | SOM hisobida qaysi raqamlar tanlangani va ularning bahsliligini aniq ogohlantirish |
| 04:Savdo korxonalari soni | "164,481 trade businesses (2026)" | TO'G'RI (lekin 01-fayl bilan mos emas) | stat.uz WebSearch: "164,481... 27.4%... highest result" | 01_bozor_hajmi.md'dagi "150,695/32.2%" bilan solishtirib, sana/davr farqini aniqlashtirish |
| 04:Sanoat korxonalari soni | "63,861 industrial enterprises (2026)" | QISMAN | stat.uz: 2026-yil davomida 60,600 (fev)→62,000 (iyun) — o'sish tendentsiyasi bilan mos, lekin aniq "63,861" topilmadi | Aniq sana/manba qo'shish |
| 04:Avto ehtiyot qismlar import | "1.44K jami (Mar2025–Feb2026); UZAUTO MOTORS 1,883 (largest buyer)" | NOTO'G'RI (ichki mantiqiy xato) | 1,883 > 1,440 — matematik mumkin emas; tashqi manbalar (importyeti/trademo/volza) 6,081–12,630 oralig'ida turli raqamlar beradi, hech biri mos kelmaydi | Butun statistika klasterini qayta tekshirish/olib tashlash |
| 04:Fake invoice detection AI | "pilot Dec 22, 2025; full Jan 1, 2026" | QISMAN/TO'G'RI | WebSearch: pilot 2025-12-22 boshlanadi, test rejimi 2026-01-01gacha (bu kungacha sanksiya yo'q) — sana mos, "full" so'zi "sanksiya boshlanishi"ni anglatishi aniqlashtirilishi kerak | Aniq lex.uz/soliq.uz manba qo'shish |
| 04:Cashless mandates | "Apr 1, 2026 — real estate, vehicles, utilities" | TO'G'RI | zamin.uz, uzdaily.uz: 2026-04-01 dan ko'chmas mulk, avtomobil (M/N/O/G toifa, 10 yoshgacha), kommunal, 25 mln so'mdan yuqori tovar/xizmat — naqd pulsiz | — |
| 04:UzQR majburiyligi | "mandatory Jul 1, 2026" | TO'G'RI | 00-xulosa faylida allaqachon tasdiqlangan (Prezident farmoni 2025-12-10, 2026-07-01 to'liq majburiy) — mos | — |

---

## Qo'shimcha izoh

- `04_sohalar.md` faylining aksariyat sektor bo'limlarida (ishlab chiqarish, qurilish mollari, apteka, xizmatlar, HoReCa) aniq manba URL yo'q — faqat umumiy raqamlar keltirilgan. Bular tekshirib bo'linmaydigan toifada qoladi, lekin bu "TEKSHIRIB BO'LMADI" emas, balki "manba umuman keltirilmagan" muammosi — hujjatga qo'shimcha havolalar qo'shish tavsiya etiladi.
- "Known pitfall" (haiku agentlarining muvaffaqiyat xabarini "firibgarlik"/"shikoyat" deb atashi) `11-raqobatchilar-kamchiliklari.md`ning JORIY versiyasida topilmadi — bu muammo avvalgi versiyada (ЮKassa qatori) bo'lgan va to'g'ri olib tashlangan. `03_raqiblar_narx.md`da ham BILLZ/Uzum moliyalashtirish yangiliklari to'g'ri ijobiy voqea sifatida qolgan — faqat ichidagi raqamlar (o'sish koeffitsienti, dollar summalari) noto'g'ri.
