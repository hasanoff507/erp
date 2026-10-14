# Research fakt-tekshiruvi — umumiy xulosa (2026-10-14)

*6 ta mustaqil tekshiruvchi (sonnet) + koordinator. Har bir da'vo birlamchi manbada (lex.uz, rasmiy saytlar) ochib tekshirildi. Batafsil jadvallar: `tekshiruv-2026-10-14/` papkasida (0 — chatlar tarixi, 1–5 — sohalar bo'yicha).*

## Umumiy baho

Research **ishonchli asosga ega, lekin ~25 ta aniq xato bor**, ulardan 4 tasi mahsulot qaroriga ta'sir qiladi. Huquqiy asos (48 soat offline, E-IMZO, QR to'lov PF-246, markirovka qarorlari, BHMS-4, NSBU 21) asosan to'g'ri. Eng zaif joylar: raqobatchilar va bozor raqamlari (ko'p manbasiz yoki noto'g'ri o'qilgan), hamda soliq hisobotlari islohoti tafsilotlari.

| Soha | To'g'ri | Qisman | Noto'g'ri |
|---|---|---|---|
| Fiskal / kassa / markirovka (02, 09, 10) | ~26 | ~15 | ~11 |
| E-faktura / to'lov / hosting (03, 07) | ~22 | 6 | 1 |
| Arxitektura / AI (04, 05) | ko'pchilik | — | 5 |
| Raqobat / bozor (06, 11, bozor fayllari) | ko'pchilik | bir nechta | ~10 |
| Buxgalteriya/ERP ma'lumotlar modeli (01, 08) | ko'pchilik | bir nechta | 6 |

## 1. Mahsulot qaroriga ta'sir qiladigan topilmalar

1. **Asosiy tezis zaiflashdi.** "Hech bir raqobatchi soliq tizimlari bilan integratsiya qilmagan" — NOTO'G'RI. moysklad.uz o'z saytida (koordinator qayta tekshirdi): E-POS orqali "Регистрация продаж в налоговой Узбекистана через один клик", "Интеграция с ... AslBelgisi", Didox orqali e-faktura. REGOS ham Didox bilan integratsiyalangan. Farq "integratsiya bor/yo'q" emas, balki: hammasi bitta tizimda (uchinchi tomon kassasi/EDO'siz), davlat hisobotini ichki hisob bilan solishtirish, offline + markirovka, o'zbek tilida AI.
2. **Davlat hisobot tuzishi — huquqiy asos topildi va aniqlashtirildi.** O'RQ-1108 (2025-12-25, 2026-01-01 dan kuchda), Soliq kodeksi 81-moddasiga o'zgartirish (koordinator lex.uz matnidan o'qidi):
   - Davlat tuzadi: **QQS, aylanma solig'i, mol-mulk, yer, JShDS, ijtimoiy soliq**. **Foyda solig'i yo'q.**
   - Farq bo'lsa, korxona **"besh kun ichida"** (kalendar kun — "ish kuni" emas), lekin hisobot muddatidan kechiktirmay tuzatadi.
   - Tuzatilmasa — davlat tuzgan holida topshirilgan hisoblanadi.
   - Fayllardagi "5 ish kuni", "Soliq kodeksi 227-modda / VM 522" asoslari — noto'g'ri.
3. **Virtual kassa reyestriga kiritish muddati — ochiq savol emas.** VMQ-943, 4-ilova: Soliq qo'mitasi 20 ish kuni + Kiberxavfsizlik markazi 15 + FMO 10 + texnik tartibga solish 5 ish kuni. Zaxira mablag' talabi virtual kassaga tegishli emas. (943-son qarorda 3 emas, kamida 5 ta ilova bor.)
4. **AI modellar ro'yxati eskirgan.** claude.com/pricing (koordinator tekshirdi): Sonnet 5.5 ($2/$10) va Haiku 5.5 ($0,10–0,50 / $0,50–2,50) chiqqan. Spec'dagi Haiku 4.5 ($1/$5) endi legacy va qimmatroq — AI xarajat hisobi qayta ko'rilishi kerak.

## 2. Tuzatilishi kerak bo'lgan faktik xatolar

| Fayl | Xato | To'g'risi |
|---|---|---|
| 02 | Suv/ichimlik — fakturada kod muddati 2026-04-01 | **2027-04-01** (631-son, lex.uz/docs/-6266709) |
| 02 | Muddati o'tgan markirovkali tovar cheklovi — 833-son asosida | 943-son 1-ilova 6-band + 23-son (2026-01-23) |
| 09 | PQ-830, QQ-825, QQ-249 | Hammasi **VM** qarorlari |
| 09 | E-ishonchnoma: "E-IMZO majburiy" | E-IMZO **yoki** Face ID |
| 09 | E-TTN majburiyligi faqat 249-son | + **673-son (2023-12-21)** majburiylik muddatlari |
| 09/03 | CBU "№3817" | lex.uz ro'yxat raqami; CBU ichki qarori raqami alohida (5/11?) |
| 10 | REGOS e-faktura "noma'lum"; BILLZ "Ha/Ha/Ha" | REGOS — Ha (Didox); BILLZ — dalil yo'q |
| 03 | "48 mezon / 71 idora" → gazeta.uz 2025-10-15 | Manba aslida gazeta.uz **2025-09-04** |
| 05 + spec 05 | GPT-5 OCR ">96%" | Manbada ~88% |
| 05 | ABBYY 99,5%, Google Vision 63,4% | Manbada yo'q / 70–75% |
| 05 | Tilmoch $1,5M — 2026-oktyabr | 2025-sentyabr |
| 01 | QQS 15%→12% "2026 dan" | 2023-01-01 dan; 2026 da o'zgarmagan. **12% to'g'ri** (SK 258-modda) |
| 06_integratsiyalar | QQS 15%; onlayn kassa — VM 522 | 12%; **VMQ-943** |
| 06_integratsiyalar | report.gov.uz, "105 hisobot" | hisobot.gov.uz; "105" manbasiz |
| 06 / 03_raqiblar | REGOS Pro "$869k" | **859 000 so'm/oy** |
| 02 / bozor | Markirovka uskunasi 300–500 ming so'm | Manbada **300–500 ming dollar** |
| 06 | MoySklad bepul — 2 savdo nuqtasi | 1 savdo nuqtasi |
| 03_raqiblar | BILLZ 1 500+ va 4k do'kon (bir faylda) | Bittasini manba bilan tanlash |
| 03_raqiblar | Uzum 1,7x, 17k sotuvchi | 3,4x, 16 000 |
| 01_bozor | "World Bank 2022" | Havola MDPI maqolasiga — noto'g'ri manba |
| bozor fayllari | Savdo korxonalari 150 695 vs 164 481 | Fayllar orasida ziddiyat |
| 06/03 | Smartup 19,5k, REGOS 5000+, Paloma365 20k, MoySklad 1k | Rasmiy sahifalarda yo'q — "manbasiz" |

## 3. Yopilgan ochiq savollar

- QQS 12% — SK 258-modda, lex.uz'dan tasdiqlandi.
- "5 ish kuni" qoidasi — O'RQ-1108 / SK 81-modda; aslida **5 kalendar kun**.
- QR to'lov majburiyligi — **PF-246 (2025-12-10)**.
- Virtual kassa reyestri muddati — VMQ-943 4-ilova.
- Paloma365 — Qozog'iston kompaniyasi (narxi so'mda, USD emas).

## 4. Hali ochiq

- CRPT Turon integrator shartlari va API; offline paytda markirovkali tovar sotish qoidasi.
- my.soliq.uz'dan davlat tuzgan hisobotni dasturiy o'qish (API yo'q).
- ЗРУ-764 sertifikatlash xususiy SaaS'ga tegishlimi.
- Tariflar: dastlab 149k/349k/699k so'm edi, spec'da izohsiz 69k–999k oralig'iga almashgan — foydalanuvchi qarori kerak.
- `spec/02-arxitektura/` hali yozilmagan.
