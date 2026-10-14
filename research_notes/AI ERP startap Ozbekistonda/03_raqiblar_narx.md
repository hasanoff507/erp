# Raqobat va Narx: Taftsiliy Tadqiqot (2026-10-10)

## SECTION A: Raqobat xaritasi — Asosiy Topishlar

### Raqiblar va AI Darajasi

#### Tasdiqlangan AI Funksiyalar
1. **REGOS**: AI-yordamchi (savdo dinamikasi, kam qolgan tovar, hisobot topish) — faqat o'z ma'lumoti ustida, Pro tarifda MCP
2. **Smartup**: Javon AI (fotodan Asl Belgisi tekshirish, taqdim analizi)
3. **Linko/PosPoint**: Chek skanerlash + bashoratli buyurtma

#### Yo'q deb tasdiqlangan AI (yoki aniq yo'q):
- BILLZ: yo'q
- OX System: uchinchi tomondan shunaqa xabar
- HIPPO: yo'q
- MDokon: yo'q
- MoySklad: yo'q (ichki modullar bor, lekin AI to'g'ri emas)
- Paloma365: "AI" da'vo qilinadi, tafsilot yo'q

#### Xitoy va janubiy sharqdosh muqobila:
- Uzbekistonda hech biri topilmadi; ASEAN da Odoo, Toast variants mavjud

### Raqobilar bo'yicha jadvali (Segmentlar + AI)

| Segment | O'yinchilar | AI darajasi | Asosiy zaif tomon | Narx (so'm/oy) |
|---------|-----------|-----------|----------|------------|
| Chakana POS (mikro) | BILLZ, Linko, OX lite, MobiSklad | Yo'q/Asosiy | Hisobot, qarz integratsiyasi cheklangan | 100k–250k |
| Chakana POS (o'rta) | REGOS, HIPPO, MDokon | Asosiy | Hisobotning qisqaligi, qarz integratsiya yo'q | 250k–500k |
| Chakana POS (katta) | OX System, Paloma365, iiko | Yo'q | Mahalliy qarz/kredit yo'q | 350k–600k |
| FMCG/distribyutsiya | Smartup, Bito | Asosiy (Smartup) | Aniq zaif tomon manbada ko'rsatilmagan | 600k–1.5M |
| ERP uchun | MoySklad | Yo'q | AI yo'q; bitta tizimda hammasi birlashmagan (davlat hisobotini solishtirish, offline+markirovka chuqur integratsiyasi yo'q) *(2026-10-14 tekshiruvida tuzatildi: avval "Mahalliy integratsiya cheklangan" deb yozilgan edi — bu NOTO'G'RI, moysklad.uz o'z saytida E-POS orqali fiskal ro'yxatga olish va AslBelgisi/Didox integratsiyasini aniq reklama qiladi; haqiqiy zaif tomon integratsiya yo'qligi emas, balki AI va all-in-one birlashuv yo'qligi)* | 156k–1M (bepul start) |

### Asosiy Bo'sh Joylari

1. **Qarz integrasiyasi zaif** — BILLZ (TBC bilan) va Smartup keyslari; REGOS, OX, HIPPO — to'liq yo'q. Uzum, Click, Payme — API bilan, lekin QQS kalkulyatsiyasi shart.
2. **Proaktiv brifing va debitorlik ogohlantirishlari yo'q** — hech birisida eng muhim savdo sahalarini real vaqtda taqdim (forecasting, qarz risk) yo'q.
3. **Uzbek dastursini aqlliylashtirish niche** — Smartup faqat FMCG/farma; Bito — Exceldan o'tish; MoySklad — Rossiyaning o'rnini bosmasa, asli yo'q.

### Raqobilashni Stratehiyalar

- **BILLZ**: TBC Bank da qo'l chiqtirdi (53% 2025, $20M baholash); kreditlash + POS — mustahkam kombo. 4k do'kon ⚠ **ichki ziddiyat** *(2026-10-14 tekshiruvida qo'shildi: pastdagi Manbalar bo'limida xuddi shu BILLZ uchun "1500+ do'kon" deb yozilgan — bitta hujjatda ikki xil raqam, hech biri birlamchi manbada mustaqil tasdiqlanmagan, ikkisi ham "tasdiqlanmagan" deb qaraladi)*; pul oqimi, qarz, P&L API'da bor ⚠
- **REGOS**: 5k do'kon — ⚠ **manbasiz (rasmiy sahifada topilmadi)** *(2026-10-14 tekshiruvida qo'shildi: regos.uz'da bu raqam umuman yo'q, WebSearch ham tasdiqlamadi)*; MCP, webhook, API; AI-yordamchi + asosiy integration
- **OX System**: 350+ do'kon (2023), hozir noma'lum; omnikanal + RFID; zaif bozor
- **Smartup**: 19.5k foydalanuvchi, 600+ kompaniya — ⚠ **manbasiz (rasmiy sahifada topilmadi)** *(2026-10-14 tekshiruvida qo'shildi: greenwhite.uz/smartup-en sahifasida bu raqamlar yo'q)*; Didox integratsiya; distribyutorlar debitorligi uning aloqasi
- **MoySklad**: 1k (2024), hozir noma'lum — ⚠ **manbasiz (rasmiy sahifada topilmadi)** *(2026-10-14 tekshiruvida qo'shildi: moysklad.uz/subscription/'da bu raqam yo'q)*; eng yaxshi JSON API; bepul tarif kuchli
- **Kaspi.kz (Qozog'iston)**: Kasper AI ishga tushdi (20% miyillionchi birinchi oyda); merchant tools MVP

---

## SECTION B: Narx va Biznes Model — Asosiy Topishlar

### Narx Jadvali: Asosiy Raqiblar (Hajm bo'yicha)

| Mahsulot | Bepul tarif | Starter/Basic | O'rta (Pro/Plus) | Enterprise | Modelo |
|---------|-----------|--------------|------------|----------|--------|
| **BILLZ** | Yo'q ⚠ | 299k | 499k | 999k | SaaS + kredit |
| **REGOS** | Yo'q | 69k | 149k–300k | 687k–859k (Pro) | SaaS + API |
| **MoySklad** | Ha (5 xodim) | 69.3k (yillik) | 156k–196k | 1.1M–1.4M | SaaS + bepul |
| **Smartup** | Yo'q | — | 120k/foydalanuvchi | 600k+/jamoa (5-10 kishi) | Per-user |
| **Linko/PosPoint** | Yo'q ⚠ | <100k (esingdan) | 100k–200k | ? | SaaS |
| **OX System** | Ha (lite) | — | Sorov bo'yicha | Sorov bo'yicha | Jimlash + SaaS |
| **MDokon** | Yo'q | 199k | 299k | 399k | SaaS |
| **HIPPO** | Yo'q | 247k | 412k | 618k | SaaS |
| **Paloma365** | Ha (15 kun) | 134.7k (eng past tarif) | 224.5k–269.4k | 314.3k | SaaS (Qozog'iston kompaniyasi, narxlar **so'mda**, dollarda emas) *(2026-10-14 tekshiruvida tuzatildi: narxlar paloma365.com/en/tariffs'da so'mda — 134,700/224,500/269,400/314,300; "134.7k" eng PAST tarif, "o'rta" emas)* |

### Biznes Modellari va Ular Qanday Ishlamasi

#### 1. **SaaS Subscription (Asosiy)**
- **BILLZ, REGOS, MoySklad, Smartup, HIPPO, MDokon**
- Per-user yoki per-location tarifi
- **ARPU (Jami Taqsimlash Kelimlari)**: BILLZ 299k–999k, REGOS 254k–859k, MoySklad 156k–1.1M (bugun noma'lum)
- **Churn**: Muhammadjon verimlari topilmadi, lekin SME davrida 5–15% oy bo'lishi kutiladi
- **Foyda**: Shaxsi hisob-kitobga asoslangan; BILLZ TBC'dan kreditni qayta sotadi (chiq)

#### 2. **Free + Premium Upsell (MoySklad Model)**
- Bepul 5 xodim + 1 millionchi; paid tiers unlimited
- Uzbekistan SME'lari uchun qaytirish: 300k–500k oy (Basic+options)
- **Afzalligi**: Xemat, barobarlik; **Kamchiligi**: Churn (free dan premium) kuzatilmaydi

#### 3. **Transaction Fees (Bank, Fintech)**
- **Click**: 1–2.5% (Uzcard/Humo) dan Visa gacha; qo'shimcha himoya uchun
- **Payme**: 1–2% komissiya + Nasiya (qarz)
- **Uzum Business**: SME kredit (16,000 merchants); ARPU: kreditning 1–2% (noma'lum) *(2026-10-14 tekshiruvida tuzatildi: avval "17k+" edi)*
- **Afzalligi**: Qaynoq; **Kamchiligi**: O'zbekistan qanunchiligida QQS rivojlanayotgan

#### 4. **Embedded Lending / FinTech + SaaS (TBC-BILLZ Model)**
- BILLZ→TBC: 4k do'kon, kredit +300M so'mgacha, 12M garovli kredit
- Uzum Business→Seller: 16,000 merchants; kredit hajmi 3.4x o'sish *(2026-10-14 tekshiruvida tuzatildi: avval "17k+ sotuvchi; 1.7x o'sish" edi — techcrunch.com asl maqolasida "16,000 merchants" va kredit o'sishi "3.4x" deyilgan)*
- Smartup: distribyutor keyslari; debitorlikni qisqartirishdagi ma'lomotlar
- **Afzalligi**: Yuqori ARPU, churn kam (kredit majbur qiladi), upsell hayotiy; **Kamchiligi**: Regulyatsiya (QQS, kredit baholashi)

#### 5. **Dealer / Franchise Komissiyasi (OX, REGOS Model)**
- **REGOS, OX System**: Diler tarmog'i orqali; bo'linish noma'lum
- **Afzalligi**: Tezda bozor qamrovi; **Kamchiligi**: Taqim tarmoq, savoyga zarur

---

### Tavsiyalangan Narx Tuzilishi: AIOS uchun 3 Sath

#### **Sath 1: Starter (Kichik Do'konga)**
- **Narx**: 149,000 so'm/oy (yillikda 20% chegirma = 1.79M)
- **Foydalanuvchi soni**: 1–2
- **Tovarlar**: QQS/OFD integrasiya, asosiy POS, bitta do'kon
- **AI**: Yo'q
- **Tadbiq**: MobiSklad, Linko raqib

#### **Sath 2: Professional (O'rta Chakana Zanjir)**
- **Narx**: 299,000 so'm/oy (yillikda 15% chegirma = 3.89M)
- **Foydalanuvchi soni**: 3–5
- **Tovarlar**: QQS/OFD, POS, ombor, CRM, kredit integratsiyasi (Payme/Click API), debitorlik monitoring
- **AI**: Asosiy (chek skanerlash, barobarlik taklifi)
- **Tadbiq**: REGOS Plus, BILLZ, Smartup kichik jamoa

#### **Sath 3: Enterprise (Zanjir, Ulgurji)**
- **Narx**: 500,000–750,000 so'm/oy (5–10 foydalanuvchi)
- **Foydalanuvchi soni**: 5–20 gacha
- **Tovarlar**: Hammasi + kichik omborlar, ish taqsimoti, davomiy brifing (AI proaktiv tahdidlar), dedikatsiya qo'llab-quvvatlash
- **AI**: Kuchli (qarz risk, savdo bashorati, inventory optimallik)
- **Tadbiq**: REGOS Pro, Smartup, Bito + AIOS

### Tafsif: Nima Uchun Bu Narx?

| Asosiy faktor | Asosiy fikr |
|-----------|---------|
| **BILLZ raqib** | 299k–999k; Starter 149k (begona?), Professional 299k (BILLZ Lite), Enterprise 500k (BILLZ Standart+TBC kredit) |
| **REGOS + MoySklad** | REGOS 69k–859k; MoySklad bepul–1.1M → Professional 299k — oraliq, kuchli API + AI |
| **TBC-BILLZ kredit** | 4k do'kon; agar AIOS kredit integratsiyasini oshiritsa (+3–5% ARPU), upsell mantiqli |
| **Smartup per-user** | 120k/kishi; 5 kishi = 600k; **Enterprise 500k–750k** — o'xshash (Smartup cheklangan; AIOS — kuchli AI) |
| **SME bozori** | 1.2M biznes; 479k kichik korxona; **real taqqsim**: Starter (50k do'kon), Professional (100k do'kon), Enterprise (5k zanjir) |

### Kichik Biznesi Analitikasibunga Asoslangan Modellar

#### **Uzum Business** (Kabul - Qozog'iston maqol)
- 16,000 merchants; kredit hajmi 3.4x o'sish *(2026-10-14 tekshiruvida tuzatildi: avval "17k+ sotuvchi; 2025-yilda 1.7x o'sish" edi — techcrunch.com manbasida "16,000 merchants" va "3.4x" deyilgan)*
- ARPU: noma'lum (lekin 1–2% kredit komissiyasi + sotuv marzhasi)
- **Kitobxona**: Payme Nasiya bilan; seller himoyasi yo'q; QQS nayish

#### **TBC Business + BILLZ**
- 30k+ SME (30M so'mgacha raqamli kredit)
- BILLZ: 4k klient; TBC kredit: 12M garovli
- **Kombo**: Qarz (20% ehtimoli) × 5% olish = 1% nusxasi ARPU orqali (noma'lum)

---

## Toipriqtagi Manbalari

### Asosiy Tafsiliyat
- [BILLZ Pricing (1500+ do'kon ⚠ — boshqa joyda "4k do'kon" bilan ziddiyatli, hal qilinmagan, TBC $20M valuation, 2025-06-29 Acquisition)](https://billz.io/uz)
- [REGOS Pricing (859 000 so'm/oy Pro tarif ⚠ manbasiz "5000+ do'kon" raqami bilan, AI, 2026)](https://regos.uz/ru/price) *(2026-10-14 tekshiruvida tuzatildi: avval "$869k Pro tier" deb yozilgan edi — bu 859 000 SO'M/oy (~$68), dollar emas, ~12 700x kattalashtirilgan xato)*
- [MoySklad Uzbekistan (Free + 5 tiers, "1k client 2024" ⚠ manbasiz, JSON API)](https://www.moysklad.uz/subscription/)
- [Smartup (120k/user, "19.5k employees, 600+ customers" ⚠ manbasiz)](https://www.greenwhite.uz/smartup-en)

### Fintech Model
- [TBC BILLZ Acquisition ($9M stake, $20M valuation, 53%, lending integration)](https://theasianbanker.com/press-releases/tbc-bank-group-acquires-majority-stake-in-billz-for-12m)
- [Uzum Business (16,000 merchants, $65.5M raised 2025, 3.4x growth SME credit)](https://techcrunch.com/2025/08/05/uzbekistans-first-unicorn-uzum-leaps-to-a-1-5b-valuation) *(2026-10-14 tekshiruvida tuzatildi: avval "17k sellers... 1.7x growth" edi — asl maqolada "16,000 merchants" va "3.4x" deyilgan)*
- [Click Business Transaction Fees (1–2.5%)](https://onedev.uz/en/blog/how-to-accept-online-payments-in-uzbekistan-click-payme-uzum-and-cards)

### Market & Regulation
- [Uzbekistan SME Market Size (1.2M businesses, 479k small firms, 2026-Q1)](https://stat.uz/en/press-center/news-of-committee/68103-zbekistonda-1-2-mlndan-orti-kichik-tadbirkorlik-subektlari-faoliyat-yuritmo-da-4)

### Hamkor Infrasructure
- [Didox EDO (250k companies — tasdiqlanmagan, 0.5% karta)](https://kun.uz/news/2026/09/10/didox-aloqabank-va-uzcard-hamkorlikda-yangi-avlod-korporativ-kartasini-taqdim-etdi)
- [Paloma365 (Qozog'iston HoReCa, 134,700–314,300 so'm/oy, "20k businesses" ⚠ manbasiz)](https://paloma365.com/en/tariffs) *(2026-10-14 tekshiruvida tuzatildi: avval "$9–54/month, 20k businesses" edi — paloma365.com/en/tariffs'da narxlar so'mda (dollar yo'q), "20k businesses" raqami topilmadi)*
- [Kaspi.kz Kasper AI (20% penetration in month 1; merchant tools MVP)](https://astanatimes.com/2026/07/mikhail-lomtadze-unveils-kasper-a-personal-ai-assistant-from-kaspi-kz-for-every-kazakh/)
