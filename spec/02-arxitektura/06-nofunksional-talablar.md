# Nofunksional talablar

*2026-10-14 · Asos: `spec/02-arxitektura/00-umumiy-arxitektura.md`, `01-malumotlar-modeli.md`, `08-frontend-arxitekturasi.md`, `05-xavfsizlik-va-audit.md` (5-bo'lim — AI xarajat taxmini), `spec/01-mahsulot/02-modullar-talablari.md`, `04-ekranlar-va-ux.md` (tezlik/UX taxminlari), `06-mvp-chegarasi.md` (tariflar), `05-ai-funksiyalar.md` (5-bo'lim — AI narx hisob-kitobi), `research_notes/texnik/07-hosting-lokalizatsiya-xavfsizlik.md` (UzCloud narxlari, saqlash muddati), `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md` (uskuna narxlari).*

## Asosiy xulosalar

1. **Barcha tezlik/sig'im ko'rsatkichlari (POS skan-dan-qatorgacha, chek yakunlash vaqti, API p95) manbada raqam bilan tasdiqlanmagan — hammasi `taxmin`**, chunki mahsulot hali ishga tushmagan va O'zbekiston raqobatchilari ham bu ko'rsatkichlarni rasmiy sahifalarida e'lon qilmaydi (`04-ekranlar-va-ux.md`, Asosiy xulosa #10; `06-mvp-chegarasi.md`, 3.1-bo'lim).
2. **Qonuniy majburiy, manbali muddatlar ikkitagina**: offline chekning OFD'ga yetib borishi — **48 soat** (VM 943-son qaror, 1-ilova, 31-band) va markirovkalangan tovarni ko'chirish — **72 soat** (23-son qaror, 2026-01-23); boshqa barcha "tezlik maqsadi" taxmin (`06-mvp-chegarasi.md`, 3.1-bo'lim).
3. **Sig'im rejasi (100 → 1000 tenant) va o'rtacha ko'rsatkichlar (kassa soni, kunlik savdo) manbada yo'q — taxmin**; shu taxminlar ustiga UzCloud'ning manbali narx jadvali (`07-hosting-...md`, 2.1-bo'lim) qo'llanib, VM/DB o'lchami va narxi hisoblab chiqiladi.
4. **Mavjudlik maqsadi uchun rasmiy shartnoma SLA raqami yo'q** — UzCloud faqat infratuzilma darajasidagi da'vo (**99,982%**, <1,5 soat/yil) beradi, bu rasmiy oferta SLA'si emas (`07-fayl`, 2.1-bo'lim); MVP maqsadi shu sababli **taxmin**.
5. **Uskunalar narxi va protokollari manbali**: shtrix-kod skaner (USB HID/keyboard-wedge), chek printeri (ESC/POS), Android POS terminal (UZKASSA N5/P100, A-Pay P10) — barchasi narx bilan `06-raqobatchilar-texnik-va-uskunalar.md`dan; **tarozi protokoli va yorliq printeri protokoli tadqiqotda topilmadi — ochiq savol**.
6. **Lokalizatsiya**: o'zbek (lotin) — asosiy, rus — ikkinchi til (allaqachon qaror, `08-frontend-arxitekturasi.md`); kirill qidiruv `pg_trgm` indeks orqali (`01-malumotlar-modeli.md`, 1-bo'lim) — bu allaqachon qabul qilingan texnik yechim.
7. **Ma'lumot saqlash muddati**: buxgalteriya hujjatlari hisobot yilidan keyin kamida **5 yil** (Buxgalteriya hisobi to'g'risidagi qonun, O'RQ-404, 29-modda), soliq hujjatlari **3 yil** (2024-01-01'dan) — bu ikkinchisi qonuniy, manbali (`07-fayl`, 3.3-bo'lim); audit log va backup muddatlari buxgalteriya muddatiga tenglashtirilgan ichki siyosat (`05-xavfsizlik-va-audit.md`, 6.3 va 7.1-bo'lim). *(2026-10-14: tekshiruv)*
8. **Tenant-boshiga xarajat jadvali — hisoblanadi, lekin to'liq taxmin zanjiri**: hosting (UzCloud narxlaridan hisoblangan, manbali kirish narxlari + taxmin sig'im), AI (`05-ai-funksiyalar.md`, 5-bo'lim: ~2-5 ming so'm/oy/do'kon, Haiku 5.5 asosida), SMS (manbada narx yo'q — **to'liq taxmin**); bu jadval `06-mvp-chegarasi.md` (3.3-bo'lim)dagi "unit-iqtisod hisobi hali yo'q" bo'shlig'ini to'ldiradi.
9. **Observability (log, metrika, tracing, alerting) va qo'llab-quvvatlanadigan brauzerlar ro'yxati manbada yo'q** — ikkala band ham sanoat amaliyoti/ichki arxitektura qarori sifatida **taxmin** taklif qilinadi.
10. **Accessibility** uchun faqat UX darajasidagi umumiy tamoyillar bor (katta shrift, yuqori kontrast, 56×56dp teginish maydoni — hammasi taxmin, `04-ekranlar-va-ux.md`, 1.4-1.5-bo'lim); rasmiy WCAG audit **tadqiqotda yo'q — ochiq savol**.

---

## 1. Ishlash tezligi (SLO)

Barcha quyidagi raqamlar — **taxmin**, manbada son ko'rsatkich topilmagani sababli (`04-ekranlar-va-ux.md`, Asosiy xulosa #10; `06-mvp-chegarasi.md`, 3.1-bo'lim: "O'rtacha chek yaratish vaqti — taxmin, manbada aniq raqam yo'q"). Pilot davrida ichki telemetriya (POS event-log vaqt belgilari) orqali real raqamga almashtiriladi.

| Ko'rsatkich | Maqsad (taxmin) | Izoh |
|---|---|---|
| Shtrix-kod skanerlashdan chekka qator qo'shilishigacha (lokal, POS) | **< 100 ms** | Lokal SQLite/IndexedDB operatsiyasi, server kutilmaydi |
| Chekni yakunlash (to'lov tasdig'idan chek chiqishigacha, lokal) | **< 1 s** | Offline rejimda ham — fiskal/OFD yuborish **asinxron navbatda**, foydalanuvchini kutdirmaydi (`00-umumiy-arxitektura.md`, 7-band: "fon ishlari... API so'rovi tashqi tizimni kutib turmaydi") |
| API javob vaqti, p95 (o'qish so'rovlari, masalan qoldiq/narx) | **< 300 ms** | Backend ichida, tashqi tizim kutilmaydi |
| API javob vaqti, p95 (yozuvchi so'rovlar, masalan sotuv posting) | **< 800 ms** | Bitta DB tranzaksiyada hujjat+registr+provodka (`01-malumotlar-modeli.md`, Asosiy xulosa #4) — OFD/EDO yuborish bu vaqtga kirmaydi (navbatga tushadi) |
| AI chat javobi (AI-01) | **< 3 s** (birinchi token) | LLM API chaqiruvi tashqi tarmoqqa bog'liq, qonuniy/manbali chegara emas |
| Offline chekning OFD'ga yetib borishi | **≤ 48 soat** (100% talab) | **Qonuniy majburiy** (VM 943-son qaror, 1-ilova, 31-band — `research_notes/texnik/02-kassa-ofd-markirovka.md`) |
| Markirovkalangan tovar ko'chirish muddati | **≤ 72 soat** (100% talab) | **Qonuniy majburiy** (23-son qaror, 2026-01-23) |
| Davlat hisoboti tafovutini hal qilish | **≤ 5 kalendar kun** | **Qonuniy majburiy** (Soliq kodeksi 81-moddasi, O'RQ-1108, lex.uz/docs/-7944527) |

---

## 2. Mavjudlik va texnik xizmat ko'rsatish oynasi

- **Infratuzilma darajasidagi da'vo**: UzCloud 99,982% (<1,5 soat/yil uzilish) — bu data-markaz infratuzilmasining o'zi uchun da'vo, **rasmiy shartnoma (oferta) SLA raqami emas** (`07-fayl`, 2.1-bo'lim: "Rasmiy ommaviy oferta hujjatida aniq foizli SLA topilmadi").
- **MVP mavjudlik maqsadi (taxmin)**: oylik **99,5%** (≈ 3,6 soat/oy ruxsat etilgan uzilish) — bu UzCloud'ning o'z infratuzilma da'vosidan pastroq, chunki ilova darajasidagi (API, deploy, bug) uzilishlar ham hisobga olinadi; manbada aniq shartnoma SLA topilmaganidan kelib chiqib **taxmin** sifatida belgilanadi.
- **Texnik xizmat oynasi (taxmin)**: haftalik, past-trafik vaqtida (masalan yakshanba 02:00–04:00 Toshkent vaqti) — manbada yo'q, odatiy SaaS amaliyoti. Kassa **offline-first** bo'lgani uchun rejali texnik ish davomida ham savdo to'xtamaydi (local-first arxitektura, `04-arxitektura-va-stack.md`, 4-band) — faqat sinxronizatsiya kechikadi.
- Offline-first arxitektura o'zi mavjudlik riskini kamaytiradi: internet/elektr uzilishi dalolatlangan (2022 Qoraqalpog'iston, yillik imtihon kuni to'xtatilishi, 2022 mintaqaviy elektr avariyasi, 2024-2025 Toshkent uzilishlari — `07-fayl`, 4-bo'lim) — bu uzilishlar backend emas, mijoz tarafidagi tarmoq uzilishi, shuning uchun backend SLA'siga kiritilmaydi, lekin mahsulot darajasida "mavjudlik" tushunchasini kengaytiradi.

---

## 3. Sig'im rejasi va UzCloud o'lchami/narxi

### 3.1 Taxminiy o'sish va yuklama (hammasi **taxmin**, manbada yo'q)

| Parametr | Qiymat (taxmin) | Izoh |
|---|---|---|
| Birinchi 3 oy (pilot) | 20–50 tenant | `06-mvp-chegarasi.md`, 3.2-bo'lim: "Pilot mijozlar soni — taxmin, manbada yo'q" |
| 6-12 oy | ~100 tenant | Maqsad, manbasiz |
| 18-24 oy | ~1000 tenant | Maqsad, manbasiz |
| O'rtacha kassa/tenant | 1–2 (Start/Biznes), 3+ (Pro) | `06-mvp-chegarasi.md`, 3.3-bo'lim tarif tafsilotlariga mos (Biznes — 3 kassagacha) |
| O'rtacha kunlik chek/kassa | 50–150 | Kichik chakana do'kon uchun odatiy taxmin, manbasiz |
| O'rtacha AI so'rov/tenant/oy | ~300 | `05-ai-funksiyalar.md`, 5-bo'lim hisob-kitobida ishlatilgan taxmin |

### 3.2 100 tenant uchun misoliy infratuzilma va narx (UzCloud, manbali birlik narxlar)

UzCloud birlik narxlari (`07-hosting-lokalizatsiya-xavfsizlik.md`, 2.1-bo'lim, 2026-10-10 holatiga, QQS bilan): vCPU — 85 000 so'm/oy; RAM — 12 000 so'm/oy/GB; SSD NVMe — 3 300 so'm/oy/GB; ochiq IPv4 — 50 000 so'm/oy; S3 Standard — 450 so'm/GB/oy saqlash + 300 so'm/GB chiquvchi trafik.

| Komponent | O'lcham (taxmin) | Hisob | Narx/oy (so'm) |
|---|---|---|---|
| API VM (FastAPI, bir nechta nusxa) | 4 vCPU, 8 GB RAM, 50 GB NVMe | 4×85 000 + 8×12 000 + 50×3 300 | 340 000+96 000+165 000 = **601 000** |
| Worker VM (navbat, fon ishlari) | 2 vCPU, 4 GB RAM, 30 GB NVMe | 2×85 000 + 4×12 000 + 30×3 300 | 170 000+48 000+99 000 = **317 000** |
| PostgreSQL DBaaS (HA, PITR) | 4 vCPU, 16 GB RAM, 100 GB NVMe | 4×85 000 + 16×12 000 + 100×3 300 | 340 000+192 000+330 000 = **862 000** |
| Redis VM (kesh/navbat/rate-limit) | 1 vCPU, 2 GB RAM, 10 GB NVMe | 85 000+24 000+33 000 | **142 000** |
| S3 (chek/faktura PDF, foto) | ~50 GB saqlash + ~10 GB chiquvchi | 50×450 + 10×300 | 22 500+3 000 = **25 500** |
| Ochiq IPv4 (API + zahira) | 2 ta | 2×50 000 | **100 000** |
| **Jami infratuzilma/oy** | — | — | **≈ 2 047 500 so'm** |
| **Tenant-boshiga hosting (100 tenant uchun)** | — | 2 047 500 ÷ 100 | **≈ 20 500 so'm/oy** |

*Eslatma: bu — **to'liq taxmin zanjiri** (o'lchamlar ham, tenant soni ham manbasiz); faqat birlik narxlar (`07-fayl`dan) manbali. Managed Kubernetes (HA boshqaruv paneli 1 500 000 so'm/oy, `07-fayl`) bu hisobga kiritilmagan — MVP bosqichida oddiy VM yetarli deb taxmin qilinadi, Kubernetes 4-bo'limdagi kengaytirish yo'lida.*

### 3.3 1000 tenant uchun masshtablash yo'nalishi

- Chiziqli emas: 100→1000 tenantda API/worker VM **gorizontal** ko'payadi (bir nechta nusxa, load balancer), DBaaS **vertikal** kattalashadi (ko'proq vCPU/RAM) va/yoki o'qish replikalari qo'shiladi; S3/Redis xarajati trafikka proporsional o'sadi.
- Taxminiy 1000 tenant uchun infratuzilma **~6-8x** (100 tenant narxidan), chunki DBaaS va API VM o'lchami ham kattalashadi, faqat sodda chiziqli ko'paytirish emas — **aniq raqam yo'q, keyingi moliyaviy rejalashtirish bosqichida hisoblanadi** (taxmin, bu hujjatda yakuniy raqam berilmaydi).
- Managed Kubernetes (`07-fayl`, HA boshqaruv paneli 1 500 000 so'm/oy) — 1000 tenant bosqichida API/worker avtomatik masshtablash uchun ko'rib chiqiladi (4-bo'lim).

---

## 4. Masshtablash yo'li (scalability)

1. **Multi-tenant model**: MVP — umumiy baza + `tenant_id` + RLS (past xarajat, tez ishga tushirish, `04-arxitektura-va-stack.md`, 1-bo'lim). Yirik/nozik mijozlar uchun **schema-per-tenant**ga o'tish yo'li ochiq qoldiriladi (PostgreSQL'da schema qo'shish downtime'siz).
2. **API/worker**: statelesness tufayli gorizontal masshtablash (ko'proq VM nusxasi, Managed Kubernetes'ga o'tish) — yuklama oshganda birinchi qadam.
3. **Baza**: vertikal kattalashtirish (ko'proq vCPU/RAM) birinchi, keyin o'qish replikalari (hisobotlar/AI so'rovlari uchun) — yozuvchi tranzaksiyalar asosiy DBaaS'da qoladi (bitta tranzaksiya qoidasi, `01-malumotlar-modeli.md`, Asosiy xulosa #4 buzilmasligi uchun).
4. **Navbat/fon ishlari**: Redis asosidagi navbat (**SAQ** — `09-backend-arxitekturasi.md`) workerlar sonini mustaqil masshtablashga imkon beradi. *(2026-10-14: tekshiruv)*
5. **Fayl ombori**: S3-mos, chegarasiz masshtablanadi (UzCloud S3, `07-fayl`, 2.1-bo'lim).

---

## 5. Kuzatuvchanlik (observability)

Manbada aniq vosita/qaror topilmadi — quyidagi tavsiya **taxmin**, loyihaning boshqa texnologik qarorlari (Python/FastAPI, Redis, PostgreSQL) bilan izchil:

| Qatlam | Tavsiya (taxmin) | Maqsad |
|---|---|---|
| Strukturaviy loglar | JSON formatda, `tenant_id`/`request_id` bilan har satrda | Tenant bo'yicha filtrlash, xato tezkor topish |
| Metrikalar | So'rov soni/kechikish/xato darajasi (API, worker), DB ulanish pool holati | Kengaytirish qarorlariga asos |
| Tracing | So'rov → tranzaksiya → navbat ishi zanjiri | Ayniqsa OFD/EDO/AI kabi tashqi chaqiruvlar kechikishini kuzatish |
| Alerting | Offline kassa 24/48 soat chegarasiga yaqinlashganda, navbat ishi muvaffaqiyatsiz urinishlar soni, DB/Redis mavjudligi | 48/72 soatlik qonuniy chegaralar bilan bog'liq (1-bo'lim) — bu signal `04-arxitektura-va-stack.md`, 2.4-bo'limda allaqachon talab qilingan ("kassa X soat sinxronlanmasa, markaziy tizim ogohlantirish yuborishi shart") |
| Tenant-boshiga sarf | AI tokeni/xarajati (`ai_requests` jadvali, `01-malumotlar-modeli.md`), SMS/Telegram xabar soni (`notifications_log`) | Tarif limitlarini kuzatish (M17), billing bilan bog'lanish |

Aniq vosita tanlovi (masalan Prometheus/Grafana/Loki yoki boshqa) — **ochiq savol**, `09-backend-arxitekturasi.md`da hal qilinadi.

---

## 6. Qo'llab-quvvatlanadigan brauzerlar va qurilmalar

- **Back-office PWA**: zamonaviy Chromium-asosli brauzerlar (Chrome, Edge) — asosiy maqsad; Safari/Firefox'da to'liq PWA/IndexedDB testdan o'tmagan (`08-frontend-arxitekturasi.md`, Ochiq savol 2: "Brauzer IndexedDB hajmi va tozalanishi (Safari/iOS cheklovlari) — veb-kassa uchun qo'llab-quvvatlanadigan brauzerlar ro'yxati, taklif: Chrome/Edge, Android Chrome").
- **Veb-kassa (PWA, offline)**: Chrome/Edge desktop, Android Chrome — **taklif, hali yakuniy qaror emas** (xuddi shu ochiq savol).
- **Android POS (keyingi bosqich)**: bozordagi uskunalar (UZKASSA N5 — Android 7.1, UZKASSA P100 — Android 5.1, PAX A930 — Android 7.1/PayDroid) asosida minimal **Android 5.1+** qo'llab-quvvatlanishi taxmin qilinadi (`06-raqobatchilar-texnik-va-uskunalar.md`, "Android POS terminallari" jadvali) — aniq minimal versiya `10-android-pos.md`da tasdiqlanadi.
- Chek printeriga chop etish usuli (WebUSB/Web Serial — faqat Chrome) brauzer tanlovini yanada Chrome/Edge tomon siljitadi (`08-frontend-arxitekturasi.md`, Ochiq savol 1).

---

## 7. Uskunalar ro'yxati (narx bilan, `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`dan)

### 7.1 Shtrix-kod skanerlari (USB HID / "keyboard wedge" protokoli)

| Model | Narx (so'm) |
|---|---|
| Arzon simli modellar | ~554 100 dan |
| MERTECH CL-2310 HR P2D SUPERLEAD (simsiz) | 1 500 000 |
| MERTECH CL-2320 (simsiz) | 1 414 700 |
| MERTECH CL-2410 (simsiz) | 1 500 000–1 532 600 |
| Honeywell Youjie HF600 | 1 778 400 |
| Honeywell MS7120 Orbit | 2 696 844 |

### 7.2 Chek printerlari (ESC/POS protokoli)

| Model | Narx (so'm) |
|---|---|
| Xprinter T80 | ~$40 |
| Xprinter XP-58IIT | ~297 000–360 000 |
| GP-C180I | 353 814 |
| MHT-P58C | 355 000 |
| Xprinter LP-U58 | 396 000 |
| Xprinter XP-Q200II | 1 607 976 |
| MITSU RP-809 | 2 105 400 |
| Sewoo SLK-TS400 | 2 382 186 |
| Bixolon SRP-330 II | 2 977 733 |

### 7.3 Shtrix-kodli savdo tarozilari

| Model | Narx (so'm) | Izoh |
|---|---|---|
| AOTE 777 (40 kg, 5 g aniqlik) | manbada yo'q | — |
| Umumiy diapazon | 250 000–750 000+ | Aniq ulanish protokoli (masalan CAS/Shtrix-M) **ochiq manbada topilmadi** — faqat "Frontol/LiteBox bilan integratsiya" umumiy da'vosi bor |

### 7.4 Yorliq printeri

- Narx va aniq protokol tadqiqotda **topilmadi** — `spec/01-mahsulot/02-modullar-talablari.md` (US-M09-04) buni ochiq savol deb belgilagan. Umumiy o'lcham taxmin (58×40 mm) — manba yo'q.

### 7.5 Android POS terminallari

| Model | Narx (so'm) | Texnik |
|---|---|---|
| UZKASSA N5 | 3 315 000 | Android 7.1, 8GB/1GB |
| UZKASSA P100 | 1 950 000 | Android 5.1, Quad-Core 1.0GHz, 8GB/1GB |
| A-Pay P10 | 2 699 000 | — |

*Virtual kassa rejimida alohida jismoniy fiskal modul shart emas — internetga ulangan qurilma (smartfon/planshet/PC) + dastur yetarli; chek printeri/skaner ixtiyoriy, lekin amalda deyarli barcha vendorlar tavsiya qiladi (`06-fayl`, "Virtual kassa uchun minimal uskuna talabi").*

---

## 8. Lokalizatsiya

- **Asosiy til — o'zbek (lotin), ikkinchi til — rus** (allaqachon qaror, `08-frontend-arxitekturasi.md`, i18next/react-i18next). Til almashtirish tugmasi barcha ekranlarda bir xil joyda (`04-ekranlar-va-ux.md`, 1.4-bo'lim).
- **Kirill qidiruv**: nomlar lotin/kirill/rus aralash bo'lishi mumkin, qidiruv `pg_trgm` indeks orqali (`01-malumotlar-modeli.md`, 1-bo'lim — allaqachon qaror).
- Chekni ikki tilda chiqarish — **ochiq savol/taxmin** (`04-ekranlar-va-ux.md`, Ochiq savol 1).

---

## 9. Accessibility (asosiy)

Rasmiy WCAG audit tadqiqotda yo'q — faqat UX darajasidagi umumiy tamoyillar (`04-ekranlar-va-ux.md`, 1.4-1.5-bo'lim), hammasi **taxmin**:

- Narx/summa raqamlari — eng katta shrift (boshqa matndan kamida ~1,5x).
- Yuqori kontrast (oq fonda qora/to'q ko'k matn; xato — qizil, muvaffaqiyat — yashil).
- Teginish maydoni kamida **56×56 dp** (taxmin, aniq standart manbada yo'q).
- To'liq ekran o'quvchi (screen reader) yoki klaviatura-only navigatsiya darajasidagi rasmiy audit — **MVP'da qilinmagan, keyingi bosqich/ochiq savol**.

---

## 10. Ma'lumot saqlash muddati (retention)

| Ma'lumot turi | Muddat | Manba/holat |
|---|---|---|
| Buxgalteriya birlamchi hujjatlari va registrlari | **Kamida 5 yil** (hisobot yilidan keyin) | "Buxgalteriya hisobi to'g'risida"gi Qonun (O'RQ-404, 13.04.2016, yangi tahrir), 29-modda (O'RQ-683 tahririda) — birlamchi manba [lex.uz/docs/-2931253](https://lex.uz/docs/-2931253) *(2026-10-14: tekshiruv)* |
| Soliq hujjatlari | **3 yil** (2024-01-01'dan) | Soliq kodeksi 22-modda (1-qism, 7-xatboshi) va 84-modda (saqlash, kamida 3 yil), 88-modda (3 yillik da'vo muddati; 84-moddaning 2-qismidagi shartli imtiyozlarda uzayadi) — birlamchi manba [lex.uz/docs/4674902](https://lex.uz/docs/4674902). "13 yilgacha" — tasdiqlanmagan (270/306-moddalarda saqlash qoidasi yo'q) *(2026-10-14: tekshiruv)* |
| `audit_log` | **Kamida 5 yil** (ichki siyosat) | Qonuniy minimum topilmadi — buxgalteriya hujjat muddatiga tenglashtirildi (`05-xavfsizlik-va-audit.md`, 6.3-bo'lim) *(2026-10-14: tekshiruv)* |
| Operatsion backup | **30 kun** (taxmin) | `05-xavfsizlik-va-audit.md`, 7.1-bo'lim |
| Arxiv backup | **≥ 5 yil** (buxgalteriya muddatiga mos) | `04-arxitektura-va-stack.md`, 7-bo'lim tavsiyasi *(2026-10-14: tekshiruv)* |
| `ai_requests` (AI so'rov jurnali) | **Taxmin — 1 yil** | Manbada yo'q, xarajat audit/billing nazorati uchun ichki qaror |
| `notifications_log` (SMS/Telegram) | **Taxmin — 1 yil** | Manbada yo'q |

---

## 11. Tenant-boshiga xarajat taxmini va unit-iqtisod

`06-mvp-chegarasi.md` (3.3-bo'lim) shart qo'yadi: "bir mijozga oylik xarajat (hosting, AI tokenlar, OFD/EDO operator haqlari, qo'llab-quvvatlash) Start narxidan (49 000 so'm) past bo'lishi shart" — bu hisob hali yo'q edi, quyida birinchi taxminiy versiyasi:

| Xarajat komponenti | Taxminiy summa/tenant/oy | Manba/izoh |
|---|---|---|
| Hosting (UzCloud, 100 tenant sig'imida) | **~20 500 so'm** | 3.2-bo'lim hisobi, UzCloud birlik narxlaridan (`07-fayl`) — sig'im/o'lcham taxmin |
| AI (Claude Haiku 5.5, ~300 so'rov/oy) | **~2 000–5 000 so'm** | `05-ai-funksiyalar.md`, 5-bo'lim: "1 do'kon oyiga 300 so'rov × (3000 kirish+500 chiqish token) ≈ $0,2 (~2-3 ming so'm), OCR bilan ~5 ming so'm/oy" |
| SMS (nasiya eslatma, OTP) | **~5 000–10 000 so'm** (**to'liq taxmin**) | Manbada SMS provayder narxi yo'q — `02-modullar-talablari.md` (M08, Ochiq savol: "SMS narxi va provayder aniqlanishi kerak"); taxminiy 20–50 SMS/oy × taxminiy 150–300 so'm/SMS (provayder va aniq narx tasdiqlanmagan) |
| **Jami taxminiy xarajat/tenant/oy** | **~28 000–36 000 so'm** | Hammasi yuqoridagi taxminlarning yig'indisi |
| Start tarifi narxi (`06-mvp-chegarasi.md`, 3.3-bo'lim) | **49 000 so'm/oy** | Foydalanuvchi qarori, raqobatchilardan arzon bo'lishi talabi bilan |
| Taxminiy marja (Start) | **~13 000–21 000 so'm/oy** | **Ijobiy, lekin tor** — qo'llab-quvvatlash xodimi xarajati, EDO/CRPT integrator haqlari (agar bo'lsa) hali kiritilmagan |

**Muhim ogohlantirish**: bu jadvaldagi deyarli barcha raqam (sig'im, SMS narxi, so'rov soni) **taxmin zanjiri** — faqat UzCloud birlik narxlari va AI narx formulasi manbali. Marja tor va qo'llab-quvvatlash/integrator xarajatlari hali kiritilmagani uchun **Start tarifi narxini real pilot ma'lumoti bilan qayta tasdiqlash shart** (`06-mvp-chegarasi.md`, 3.3-bo'lim: "raqamlar unit-iqtisod hisobi bilan tasdiqlanishi kerak" — shu talab bu jadval bilan **qisman** yopildi, to'liq emas).

---

## Ochiq savollar

1. Barcha tezlik maqsadlari (1-bo'lim, qonuniy majburiy 48/72 soat/5 kun bundan mustasno) — manbada raqam yo'q, pilot davrida ichki telemetriya bilan tasdiqlanishi shart.
2. Aniq mavjudlik SLA foizi — UzCloud'ning rasmiy oferta hujjatida topilmadi, sotuvchi bilan to'g'ridan-to'g'ri so'rov kerak (`07-fayl`, Ochiq savol 6).
3. Sig'im rejasidagi tenant soni, o'rtacha kassa/tenant, kunlik chek soni — barchasi taxmin, pilot ma'lumoti bilan qayta hisoblanishi kerak.
4. 1000 tenant uchun aniq infratuzilma o'lchami/narxi — bu hujjatda hisoblanmadi, keyingi moliyaviy rejalashtirish bosqichida.
5. Tarozi va yorliq printeri protokoli — ochiq manbada topilmadi, pilot uskunalarida aniqlanadi (`04-ekranlar-va-ux.md`, Ochiq savol 5; `02-modullar-talablari.md`, US-M09-04).
6. Qo'llab-quvvatlanadigan brauzerlar/Android versiyasi ro'yxati — hali yakuniy qaror emas (`08-frontend-arxitekturasi.md`, Ochiq savol 2).
7. SMS provayder va aniq narx — tanlanmagan, bu 11-bo'limdagi xarajat jadvalining eng zaif qismi.
8. Rasmiy accessibility (WCAG) audit — MVP'da qilinmagan, keyingi bosqich sifatida qoldirilgan.
9. Observability vositasi (Prometheus/Grafana yoki boshqa) — `09-backend-arxitekturasi.md`da tanlanadi.
10. Tenant-boshiga xarajat jadvalidagi (11-bo'lim) marja qo'llab-quvvatlash/integrator xarajatlarini hisobga olmagani — bu raqamlar pilot va real operatsion xarajat bilan qayta tasdiqlanishi shart, aks holda tarif narxi (`06-mvp-chegarasi.md`) qayta ko'rib chiqilishi kerak bo'lishi mumkin.

## Manbalar

- `spec/02-arxitektura/00-umumiy-arxitektura.md`, `01-malumotlar-modeli.md`, `08-frontend-arxitekturasi.md`, `05-xavfsizlik-va-audit.md`
- `spec/01-mahsulot/02-modullar-talablari.md`, `04-ekranlar-va-ux.md`, `05-ai-funksiyalar.md` (5-bo'lim — AI narx hisobi), `06-mvp-chegarasi.md` (3.3-bo'lim — tariflar va unit-iqtisod talabi)
- `research_notes/texnik/04-arxitektura-va-stack.md` (multi-tenant, masshtablash, backup)
- `research_notes/texnik/07-hosting-lokalizatsiya-xavfsizlik.md` (UzCloud narx jadvali, saqlash muddatlari, internet/elektr uzilishlari)
- `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md` (uskunalar narxi, protokollar)
- `research_notes/texnik/02-kassa-ofd-markirovka.md` (48 soat, 72 soat qonuniy muddatlar)
