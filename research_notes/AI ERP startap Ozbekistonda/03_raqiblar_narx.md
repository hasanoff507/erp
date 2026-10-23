# Raqobat va Narx: Taftsiliy Tadqiqot (2026-10-10)

## SECTION A: Raqobat xaritasi — Asosiy Topishlar

### Raqiblar va AI Darajasi

#### Tasdiqlangan AI Funksiyalar
1. **REGOS**: AI-yordamchi (savdo dinamikasi, kam qolgan tovar, hisobot topish) — faqat o'z ma'lumoti ustida, Pro tarifda MCP
2. **Smartup**: Javon AI (fotodan Asl Belgisi tekshirish, taqdim analizi)
3. **Linko/PosPoint**: Chek skanerlash + bashoratli buyurtma
4. **K2Tech** (Rossiya, Oct 2026): 1C ichida tabiiy tilda AI-agent — og'ishlar sababini topadi, huquqlar doirasida, audit
5. **GPTZATOR**: 1C uchun AI-assistant platforma

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
| Chakana POS (mikro) | BILLZ, Linko, OX lite, MobiSklad | Yo'q/Asosiy | Hisobot, qarz, 1C aloqasiz | 100k–250k |
| Chakana POS (o'rta) | REGOS, HIPPO, MDokon | Asosiy | Hisobotning qisqaligi, qarz integratsiya yo'q | 250k–500k |
| Chakana POS (katta) | OX System, Paloma365, iiko | Yo'q | Mahalliy qarz/kredit yo'q | 350k–600k |
| FMCG/distribyutsiya | Smartup, Bito | Asosiy (Smartup) | Smartup 1C yonida qoladi; Bito — 1C yo'q | 600k–1.5M |
| ERP uchun | MoySklad | Yo'q | Mahalliy integratsiya cheklangan | 156k–1M (bepul start) |
| 1C asosida (Rossiya) | K2Tech, KT-Team, GPTZATOR, ARQA | Kuchli | Uzbek tilida yo'q; franchayzilar kerak | 500k+ (litsenziya) |

### Asosiy Bo'sh Joylari

1. **O'zbek tilida 1C ustida AI-assistant yo'q** — K2Tech faqat rus tilida; GPTZATOR shunga o'xshash. Mahalliy franchayzilar orqali kirishlari mumkin, lekin kafolat yo'q.
2. **Qarz integrasiyasi zaif** — BILLZ (TBC bilan) va Smartup keyslari; REGOS, OX, HIPPO — to'liq yo'q. Uzum, Click, Payme — API bilan, lekin QQS kalkulyatsiyasi shart.
3. **Proaktiv brifing va debitorlik ogohlantirishlari yo'q** — hech birisida eng muhim savdo sahalarini real vaqtda taqdim (forecasting, qarz risk) yo'q.
4. **Uzbek dastursini aqlliylashtirish niche** — Smartup faqat FMCG/farma; Bito — Exceldan o'tish; MoySklad — Rossiyaning o'rnini bosmasa, asli yo'q.

### Raqobilashni Stratehiyalar

- **BILLZ**: TBC Bank da qo'l chiqtirdi (53% 2025, $20M baholash); kreditlash + POS — mustahkam kombo. 4k do'kon; pul oqimi, qarz, P&L API'da bor ⚠
- **REGOS**: 5k do'kon; MCP, webhook, API; AI-yordamchi + asosiy integration
- **OX System**: 350+ do'kon (2023), hozir noma'lum; omnikanal + RFID; zaif bozor
- **Smartup**: 19.5k foydalanuvchi, 600+ kompaniya; Didox, 1C integratsiya; distribyutorlar debitorligi uning aloqasi
- **MoySklad**: 1k (2024), hozir noma'lum; eng yaxshi JSON API; bepul tarif kuchli
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
| **Paloma365** | Ha (15 kun) | — | 134.7k+ | ? | SaaS (Qozog'iston) |
| **1C:Enterprise** | Yo'q | 3.6M (БП) | 4.8M (УТ) | 6M–197M (ERP) | Lisenziya |

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
- **Uzum Business**: SME kredit (17k+); ARPU: kreditning 1–2% (noma'lum)
- **Afzalligi**: Qaynoq; **Kamchiligi**: O'zbekistan qanunchiligida QQS rivojlanayotgan

#### 4. **Embedded Lending / FinTech + SaaS (TBC-BILLZ Model)**
- BILLZ→TBC: 4k do'kon, kredit +300M so'mgacha, 12M garovli kredit
- Uzum Business→Seller: 17k+ sotuvchi; 1.7x o'sish 2024–2025 yil
- Smartup: distribyutor keyslari; debitorlikni qisqartirishdagi ma'lomotlar
- **Afzalligi**: Yuqori ARPU, churn kam (kredit majbur qiladi), upsell hayotiy; **Kamchiligi**: Regulyatsiya (QQS, kredit baholashi)

#### 5. **Lisenziyalash (1C Model)**
- **1C:Enterprise**: 3.6M–6M so'm (kichik); 197M (ERP) — bitta vaqtlik
- **ITS**: 0.3–2M so'm oyiga (davomiy qo'llab-quvvatlash)
- **Afzalligi**: Mazkur odam mahalliy; **Kamchiligi**: Bitta vaqtlik xaraj, bosqichma-bosqich davomiy xarajlar

#### 6. **Dealer / Franchise Komissiyasi (1C, OX, REGOS Model)**
- **1C franchayzi**: ~30 ta guruh; 10–20% komissiya (taqdin); ITS + qo'llab-quvvatlash
- **REGOS, OX System**: Diler tarmog'i orqali; bo'linish noma'lum
- **Afzalligi**: Tezda bozor qamrovi; **Kamchiligi**: Taqim tarmoq, savoyga zarur

---

### Tavsiyalangan Narx Tuzilishi: AIOS uchun 3 Sath

#### **Sath 1: Starter (Kichik Do'konga)**
- **Narx**: 149,000 so'm/oy (yillikda 20% chegirma = 1.79M)
- **Foydalanuvchi soni**: 1–2
- **Tovarlar**: QQS/OFD integrasiya, asosiy POS, bitta do'kon, 1C ma'lumot o'qish (faqat, yozish yo'q)
- **AI**: Yo'q
- **Tadbiq**: MobiSklad, Linko raqib

#### **Sath 2: Professional (O'rta Chakana Zanjir)**
- **Narx**: 299,000 so'm/oy (yillikda 15% chegirma = 3.89M)
- **Foydalanuvchi soni**: 3–5
- **Tovarlar**: QQS/OFD, POS, ombor, CRM, kredit integratsiyasi (Payme/Click API), 1C 2-yo'nalishli sync (optimallik), debitorlik monitoring
- **AI**: Asosiy (chek skanerlash, barobarlik taklifi)
- **Tadbiq**: REGOS Plus, BILLZ, Smartup kichik jamoa

#### **Sath 3: Enterprise (Zanjir, Ulgurji)**
- **Narx**: 500,000–750,000 so'm/oy (5–10 foydalanuvchi)
- **Foydalanuvchi soni**: 5–20 gacha
- **Tovarlar**: Hammasi + kichik omborlar, ish taqsimoti, davomiy brifing (AI proaktiv tahdidlar), 1C 2-yo'nalishli sync, dedikatsiya qo'llab-quvvatlash
- **AI**: Kuchli (qarz risk, savdo bashorati, inventory optimallik, 1C noma'lumlikni eng yaqinni topish)
- **Tadbiq**: REGOS Pro, Smartup, Bito, O'zbek 1C franchayzi + AIOS

### Tafsif: Nima Uchun Bu Narx?

| Asosiy faktor | Asosiy fikr |
|-----------|---------|
| **1C narxi** | Trade Management 4.8M so'm (10 xodim, bitta vaqtlik) → yillik 480k–960k so'm; **Starter** (149k) — 30% chegirmasi, **Pro** (500k) — 1C shunga tenglashirdi |
| **BILLZ raqib** | 299k–999k; Starter 149k (begona?), Professional 299k (BILLZ Lite), Enterprise 500k (BILLZ Standart+TBC kredit) |
| **REGOS + MoySklad** | REGOS 69k–859k; MoySklad bepul–1.1M → Professional 299k — oraliq, kuchli API + AI |
| **TBC-BILLZ kredit** | 4k do'kon; agar AIOS kredit integratsiyasini oshiritsa (+3–5% ARPU), upsell mantiqli |
| **Smartup per-user** | 120k/kishi; 5 kishi = 600k; **Enterprise 500k–750k** — o'xshash (Smartup cheklangan; AIOS — kuchli AI + 1C) |
| **SME bozori** | 1.2M biznes; 479k kichik korxona; **real taqqsim**: Starter (50k do'kon), Professional (100k do'kon), Enterprise (5k zanjir) |
| **1C franchayzi kanal** | 30 ta; per-do'kon marzhasi 10–15% → **AIOS 25% → dealer 30-40% oling** (1C: 60–70% — lekin davomiy; AIOS — bir vaqtlik + SaaS) |

### Kichik Biznesi Analitikasibunga Asoslangan Modellar

#### **Uzum Business** (Kabul - Qozog'iston maqol)
- 17k+ sotuvchi; 2025-yilda 1.7x o'sish
- ARPU: noma'lum (lekin 1–2% kredit komissiyasi + sotuv marzhasi)
- **Kitobxona**: Payme Nasiya bilan; seller himoyasi yo'q; QQS nayish

#### **TBC Business + BILLZ**
- 30k+ SME (30M so'mgacha raqamli kredit)
- BILLZ: 4k klient; TBC kredit: 12M garovli
- **Kombo**: Qarz (20% ehtimoli) × 5% olish = 1% nusxasi ARPU orqali (noma'lum)

---

## Toipriqtagi Manbalari

### Asosiy Tafsiliyat
- [BILLZ Pricing (1500+ do'kon, TBC $20M valuation, 2025-06-29 Acquisition)](https://billz.io/uz)
- [REGOS Pricing (5000+ do'kon, AI, $869k Pro tier, 2026)](https://regos.uz/ru/price)
- [MoySklad Uzbekistan (Free + 5 tiers, 1k client 2024, JSON API)](https://www.moysklad.uz/subscription/)
- [Smartup (120k/user, 19.5k employees, 600+ customers, 1C integratsiya)](https://www.greenwhite.uz/smartup-en)
- [1C Enterprise Pricing (3.6M–197M so'm, 30 franchayzi)](https://perfect-solutions.uz/vnedrenie-soprovozhdenie/stoimost-vnedreniya-1c-uzbekistan/)

### Fintech Model
- [TBC BILLZ Acquisition ($9M stake, $20M valuation, 53%, lending integration)](https://theasianbanker.com/press-releases/tbc-bank-group-acquires-majority-stake-in-billz-for-12m)
- [Uzum Business (17k sellers, $65.5M raised 2025, 1.7x growth SME credit)](https://techcrunch.com/2025/08/05/uzbekistans-first-unicorn-uzum-leaps-to-a-1-5b-valuation)
- [Click Business Transaction Fees (1–2.5%)](https://onedev.uz/en/blog/how-to-accept-online-payments-in-uzbekistan-click-payme-uzum-and-cards)

### Market & Regulation
- [Uzbekistan SME Market Size (1.2M businesses, 479k small firms, 2026-Q1)](https://stat.uz/en/press-center/news-of-committee/68103-zbekistonda-1-2-mlndan-orti-kichik-tadbirkorlik-subektlari-faoliyat-yuritmo-da-4)
- [K2Tech AI-Agent (1C, Oct 2026, CNews Russian)](https://www.cnews.ru/news/line/2026-10-07_k2teh_zapustil_ii-agenta)
- [GPTZATOR (1C AI assistants platform, Russian)](https://gptzator.ru/ai-1c)

### Hamkor Infrasructure
- [Didox EDO (250k companies, 1C integrations, 0.5% karta)](https://kun.uz/news/2026/09/10/didox-aloqabank-va-uzcard-hamkorlikda-yangi-avlod-korporativ-kartasini-taqdim-etdi)
- [Paloma365 (Kazakhstan HoReCa, $9–54/month, 20k businesses)](https://paloma365.com/en/tariffs)
- [Kaspi.kz Kasper AI (20% penetration in month 1; merchant tools MVP)](https://astanatimes.com/2026/07/mikhail-lomtadze-unveils-kasper-a-personal-ai-assistant-from-kaspi-kz-for-every-kazakh/)
