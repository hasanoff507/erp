# Nofunksional talablar

**Maqsad:** Tezlik (SLO), mavjudlik, sig'im/narx, masshtablash, lokalizatsiya, saqlash muddati, unit-iqtisod va qo'llab-quvvatlash modelini belgilash.
**Kim uchun:** Arxitektor, asoschi (biznes/narx qarorlari uchun).
**Bog'liq fayllar:** `10-umumiy-arxitektura.md`, `11-malumotlar-modeli.md`, `15-xavfsizlik-va-audit.md` (§7 backup), `21-integratsiyalar.md` (§1 fiskal, §16 Do'kon agenti), `22-ai-qatlami.md` (§13), `23-backend-arxitekturasi.md` (§7.3, §9), `24-frontend-arxitekturasi.md` (§6), `03-modullar-talablari.md`, `06-ekranlar-umumiy.md`, `33-1c-integratsiya.md` (§15), `34-1c-agent.md`, `01-qarorlar.md` #22, #43, #51, #58, #60, #65.
**Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. **Tezlik/sig'im ko'rsatkichlari (POS skan-dan-qatorgacha, chek yakunlash vaqti, API p95) — standart maqsadlar**, manbada raqam yo'q (mahsulot hali ishga tushmagan, raqobatchilar e'lon qilmaydi); pilot telemetriyasi bilan qayta sozlanadi (1-bo'lim).
2. **Qonuniy muddatlar**: offline chekning OFD'ga yetishi — **48 soat**, keyin kassa **avtomatik bloklanadi** (VMQ-943 1-ilova 31-band, 2-ilova 6-band; ogohlantirish shkalasi 24/40/46/48 soat — qaror #43); markirovkalangan tovar egalik o'tishi xabarnomasi (kirim) — **3 ish kuni**, ayrim tovar guruhlarida **72 soat** (VM 833 66–67-band; VM 631, VM 149, VM 23); davlat hisobotini tuzatish — **5 ish kuni** (SK 5-modda 7-qism, 81-modda).
3. **Sig'im rejasi** (100 → 1000 tenant) — UzCloud'ning manbali birlik narxlari (2026-10-16) ustida hisoblangan; 1000 tenant uchun boshlang'ich konfiguratsiya — qaror #58 (3-bo'lim). Tenant soni va yuklama — taxmin.
4. **Mavjudlik**: UzCloud — marketing da'vosi **99,982%**, K8s Control Plane — **99,9%**, ommaviy ofertada foizli SLA ham, kompensatsiya ham yo'q (shartnoma muzokarasi). MVP maqsadi — oylik **99,5%**. Backup — RPO ≤ 5 daqiqa (o'z WAL PITR), RTO ≤ 4 soat (qaror #51), nusxa boshqa provayderda ham (qaror #65).
5. **Uskunalar narxi va protokollari manbali** (2026-10-16): skaner, chek printeri (shu jumladan bulut printerlar — Toshkentda 4,7–7,1 mln so'm), yorliq printeri (bozor standarti Xprinter XP-365B, TSPL+ESC/POS), tarozi (EAN-13 og'irlik kodi, prefiks — tenant sozlamasi), Android terminal (7-bo'lim). Xom TCP 9100 LAN printerlar va lokal fiskal ko'prik uchun do'konda **Windows PK + Do'kon agenti** kerak (qaror #60).
6. **Lokalizatsiya**: o'zbek (lotin) — asosiy, rus — ikkinchi til; kirill qidiruv `pg_trgm` orqali; chek ikki tilda (qaror #29).
7. **Ma'lumot saqlash muddati**: buxgalteriya hujjatlari kamida **5 yil** (O'RQ-404, 29-modda), soliq hujjatlari **3 yil** (SK 84-modda); audit log va arxiv backup — 5 yil (10-bo'lim).
8. **Narx modeli — yagona tarif, 99 000 so'm/oy** (qaror #22): barcha modul, AI, Telegram + 1 virtual kassa; yillik −20%, 30 kunlik sinov. Bizning tenant-boshiga xarajatimiz (100 tenantda) ≈ 29 000–35 000 so'm, marja ≈ 64 000–70 000 so'm (support xodimisiz). **Fiskal modul haqi** — 1 BHM/yil (440 000 so'm ≈ 36 700 so'm/oy/kassa) — do'kon fiskal operatorga o'zi to'laydi (VMQ-943 1-ilova 55-band), tarifimizga kirmaydi. Qo'shimcha kassa narxi (+39 000 so'm/oy) va pilotdagi hamkor kassa haqi (chakana ~123 600 so'm/oy) qayta ko'riladi (11-bo'lim).
9. **Observability**: Prometheus + Grafana + Loki + Tempo, o'z-hosted (UzCloud'da tayyor xizmat yo'q; 26 #53); alerting — fiskal 24/40/46/48 soat bosqichlari, navbat, DB, UzCloud billing (5-bo'lim).
10. **Accessibility**: MVP'da semantik HTML/ARIA, katta shrift, yuqori kontrast, 48–56 dp teginish maydoni; to'liq WCAG audit — keyingi bosqich (26 #52).
11. **Do'kon agenti va 1C**: agent `.exe` Authenticode **OV kod-imzolash sertifikati** bilan imzolanadi — SSL.com OV $129/yil (5 yillikda $96,75/yil) eSigner bulut imzosi bilan; lokal fiskal ko'prik tanlansa Bosqich 5 dan oldin, aks holda Bosqich 7 dan oldin kerak. 1C hajm/vaqt maqsadlari (approve → `done` < 3/10 daqiqa) — pilot testi P-19 da o'lchanadi (13-bo'lim); mijozda 1C **ПРОФ/КОРП** litsenziyasi talab qilinadi (bizning xarajat emas).

---

## 1. Ishlash tezligi (SLO)

Qonuniy qatorlardan tashqari barcha raqamlar — standart maqsad (manbada son ko'rsatkich yo'q); pilot davrida POS event-log vaqt belgilari va backend telemetriyasi bilan qayta sozlanadi.

| Ko'rsatkich | Maqsad | Izoh |
|---|---|---|
| Shtrix-kod skanerlashdan chekka qator qo'shilishigacha (lokal, POS) | **< 100 ms** | Lokal IndexedDB operatsiyasi, server kutilmaydi |
| Chekni yakunlash (to'lov tasdig'idan chek chiqishigacha, lokal) | **< 1 s** (lokal ko'prikda FM imzosi bilan **< 2 s**) | Offline rejimda ham; hamkor bulut rejimida OFD yuborish asinxron navbatda |
| API javob vaqti, p95 (o'qish so'rovlari) | **< 300 ms** | Backend ichida, tashqi tizim kutilmaydi |
| API javob vaqti, p95 (yozuvchi so'rovlar, masalan sotuv posting) | **< 800 ms** | Bitta DB tranzaksiyada hujjat+registr+provodka; tashqi yuborish navbatga tushadi |
| AI chat javobi (AI-01) | **< 3 s** (birinchi token) | LLM API tashqi tarmoqqa bog'liq |
| Offline chekning OFD'ga yetishi | **≤ 48 soat** (100% talab); 48 soatda kassa bloklanadi (`FISCAL_OFFLINE_48H_BLOCKED`) | **Qonuniy majburiy** (VMQ-943 1-ilova 31-band, 2-ilova 6-band; qaror #43) |
| Markirovkalangan tovar kirimida egalik o'tishi xabarnomasi | **≤ 3 ish kuni** (suv/ichimlik, dori, o'simlik yog'i pilot — **≤ 72 soat**) | **Qonuniy majburiy** (VM 833 66–67-band; VM 631, VM 149, VM 23) — `marking_product_groups.acceptance_deadline` |
| 1C ga kunni yuborish (approve → `done`, M19) | oddiy do'kon **< 3 daqiqa**, katta do'kon **< 10 daqiqa** | *Taxmin*, P-19 da o'lchanadi — 13-bo'lim |
| Davlat hisoboti tafovutini hal qilish | **≤ 5 ish kuni**, hisobot topshirish muddatidan kechiktirmay | **Qonuniy majburiy** (SK 5-modda 7-qism, 81-modda) |

---

## 2. Mavjudlik, texnik xizmat oynasi va backup

- **UzCloud da'vosi**: 99,982% (Tier III Design sertifikati asosida) — marketing raqami; K8s Control Plane uchun 99,9% e'lon qilingan. Ommaviy ofertada foizli SLA ham, kompensatsiya ham **yo'q** — yuridik shaxs shartnomasida so'raladi. UzCloud status sahifasi (`uzcloud.uz/status`) — monitoring manbai sifatida runbook'da.
- **MVP mavjudlik maqsadi**: oylik **99,5%** (≈ 3,6 soat/oy) — ilova darajasidagi (API, deploy, bug) uzilishlarni ham hisobga oladi.
- **Texnik xizmat oynasi**: haftalik, yakshanba 02:00–04:00 (Toshkent). Kassa offline-first — rejali ish davomida savdo to'xtamaydi, faqat sinxron kechikadi (48 soatlik oyna ichida).
- **Backup (qaror #51)**: RPO ≤ **5 daqiqa** (o'z WAL arxivi — pgBackRest/WAL-G → UzCloud S3 Cold; DBaaS PITR rasmiy tasdiqlanmagan), RTO ≤ **4 soat**, staging'da to'liq restore sinovi **har chorakda** (`docs/ops/restore-log.md`), arxiv ≥ 5 yil. Kamida bitta oflayn nusxa **boshqa provayderda** (qaror #65).
- **Ops xavfi (UzCloud ofertasi 4.4)**: to'lov kechiksa server o'chiriladi, "Suspended" holatidan 20 kun o'tgach ma'lumot qaytarib bo'lmaydigan tarzda yo'q qilinadi; yuridik shaxslar — postpaid, hisob-faktura 5-sanagacha, to'lov 10 kun ichida. Shuning uchun UzCloud hisobi uchun avto-to'lov yoki oldindan to'lov va billing alerti majburiy (qaror #65).
- Offline-first arxitektura mijoz tomonidagi internet/elektr uzilishlarini (Qoraqalpog'iston 2022, mintaqaviy avariyalar, Toshkent 2024–2025) yutadi — bular backend SLA'siga kirmaydi.

---

## 3. Sig'im rejasi va UzCloud o'lchami/narxi

### 3.1 O'sish va yuklama (taxmin)

| Parametr | Qiymat (taxmin) | Izoh |
|---|---|---|
| Birinchi 3 oy (pilot) | 20–50 tenant | `05-mvp-chegarasi.md`, 3.2-bo'lim |
| 6-12 oy | ~100 tenant | Maqsad |
| 18-24 oy | ~1000 tenant | Maqsad |
| O'rtacha kassa/tenant | 1 (bazaga kiritilgan) + ixtiyoriy qo'shimcha (`addons.extra_register`) | `11-malumotlar-modeli.md` §2 |
| O'rtacha kunlik chek/kassa | 50–150 | Kichik chakana do'kon |
| O'rtacha AI so'rov/tenant/oy | ~300–500 | `22-ai-qatlami.md` §13 (o'rta profil) |
| **Soliq rejimi ulushi (QQS vs aylanma)** | **Oldindan taxmin yo'q — pilot ko'rsatkichi** | (qaror #32) Ikkala rejim teng birinchi toifali |

### 3.2 100 tenant uchun infratuzilma va narx (UzCloud birlik narxlari)

UzCloud birlik narxlari (2026-10-16, QQS bilan): vCPU — 85 000 so'm/oy; RAM — 12 000 so'm/GB; SSD — 2 000 so'm/GB; NVMe — 3 300 so'm/GB; HDD — 700 so'm/GB; ochiq IPv4 — 50 000 so'm; S3 Standard — 450 so'm/GB + 300 so'm/GB chiquvchi trafik; S3 Cold — 350 + 350 so'm/GB; Tas-IX va UzCloud ichki trafik bepul. K8s Control Plane — single-node 500 000, HA 1 500 000 so'm/oy (bosh sahifadagi "от 380к" bilan nomuvofiqlik — savdo bo'limidan).

| Komponent | O'lcham | Hisob | Narx/oy (so'm) |
|---|---|---|---|
| API VM (FastAPI, bir nechta nusxa) | 4 vCPU, 8 GB RAM, 50 GB NVMe | 4×85 000 + 8×12 000 + 50×3 300 | **601 000** |
| Worker VM (navbat, fon ishlari) | 2 vCPU, 4 GB RAM, 30 GB NVMe | 2×85 000 + 4×12 000 + 30×3 300 | **317 000** |
| PostgreSQL DBaaS (bitta tugun; HA/PITR shartnomada tasdiqlanmagan) | 4 vCPU, 16 GB RAM, 100 GB NVMe | 4×85 000 + 16×12 000 + 100×3 300 | **862 000** |
| WAL arxivi va backup (o'z PITR, S3 Cold) | ~200 GB | 200×350 | **70 000** |
| Redis VM (kesh/navbat/rate-limit) | 1 vCPU, 2 GB RAM, 10 GB NVMe | 85 000+24 000+33 000 | **142 000** |
| Ops VM (Prometheus/Grafana/Loki/Tempo + E-IMZO-SERVER) | 2 vCPU, 8 GB RAM, 100 GB SSD | 170 000+96 000+200 000 | **466 000** |
| S3 Standard (chek/faktura PDF, foto) | ~50 GB saqlash + ~10 GB chiquvchi | 50×450 + 10×300 | **25 500** |
| Ochiq IPv4 (API + zaxira) | 2 ta | 2×50 000 | **100 000** |
| **Jami infratuzilma/oy** | — | — | **≈ 2 583 500 so'm** |
| **Tenant-boshiga hosting (100 tenant)** | — | 2 583 500 ÷ 100 | **≈ 25 800 so'm/oy** |

*O'lchamlar va tenant soni — taxmin; birlik narxlar — manbali. Boshqa provayderdagi oflayn nusxa narxi kiritilmagan. E-IMZO-SERVER O'zbekiston IP'sidan ishlashi shart (`vpn.e-imzo.uz` faqat UZ ichidan) — UzCloud tanlovini tasdiqlaydi.*

### 3.3 1000 tenant — boshlang'ich konfiguratsiya (qaror #58)

300 to'lovchi tenantga yetganda haqiqiy yuklama bilan qayta o'lchanadi; UzCloud shartnoma narxlari kelganda raqamlar yangilanadi.

| Komponent | O'lcham | Narx/oy (so'm) |
|---|---|---|
| App VM × 2 (api + worker) | har biri 4 vCPU, 8 GB RAM, 50 GB NVMe | 2 × 601 000 = **1 202 000** |
| PostgreSQL asosiy + o'qish replikasi | har biri 8 vCPU, 32 GB RAM, 300 GB NVMe | 2 × 2 054 000 = **4 108 000** |
| Redis | 1 vCPU, 2 GB RAM, 10 GB NVMe | **142 000** |
| S3 Standard | ~500 GB + ~100 GB chiquvchi | **255 000** |
| WAL arxivi va backup (S3 Cold) | ~1 TB | **350 000** |
| Ops VM (monitoring stack) | 2 vCPU, 8 GB RAM, 200 GB SSD | **666 000** |
| E-IMZO-SERVER VM | 1 vCPU, 2 GB RAM, 20 GB SSD | **149 000** |
| Ochiq IPv4 | 2 ta | **100 000** |
| **Jami / tenant-boshiga** | — | **≈ 6 972 000 / ≈ 7 000 so'm** |

Formula: `infra_oy = Σ (vCPU×85 000 + GB_RAM×12 000 + GB_disk×disk_narx) + S3 + IPv4`; tenant-boshiga = `infra_oy ÷ faol_tenantlar`. Managed Kubernetes (HA CP 1 500 000 so'm/oy) — avtomatik masshtablash kerak bo'lganda (4-bo'lim).

---

## 4. Masshtablash yo'li (scalability)

1. **Multi-tenant model**: MVP — umumiy baza + `tenant_id` + RLS. Yirik mijozlar uchun **schema-per-tenant** yo'li ochiq qoladi.
2. **API/worker**: holatsiz — gorizontal masshtablash (ko'proq VM nusxasi, keyin Managed Kubernetes).
3. **Baza**: avval vertikal, keyin o'qish replikalari (hisobotlar/AI so'rovlari); yozuvchi tranzaksiyalar asosiy DBaaS'da (`11-malumotlar-modeli.md`, Asosiy xulosa #4).
4. **Navbat/fon ishlari**: Redis asosidagi **SAQ** — workerlar soni mustaqil masshtablanadi (`23-backend-arxitekturasi.md`).
5. **Fayl ombori**: UzCloud S3 (AWS S3 API mos, uch karra replikatsiya).
6. **Do'kon agenti long-poll**: 1 000 parallel async ulanish `api` ichida (uvicorn async + Redis pub/sub), alohida VM shart emas (13.1).

---

## 5. Kuzatuvchanlik (observability)

Stack — **Prometheus + Grafana + Loki + Tempo**, o'z-hosted (Ops VM; 26 #53). Kod tomoni — `23-backend-arxitekturasi.md` §8.

| Qatlam | Vosita | Maqsad |
|---|---|---|
| Strukturaviy loglar | structlog (JSON) → Loki; `tenant_id`/`request_id` har satrda, PII redaction | Tenant bo'yicha filtrlash, xato tezkor topish |
| Metrikalar | prometheus-client → Prometheus → Grafana | So'rov soni/kechikish/xato, DB pool, `outbox_jobs` navbat chuqurligi, AI xarajati |
| Tracing | OpenTelemetry → Tempo | So'rov → tranzaksiya → navbat ishi; OFD/EDO/AI tashqi chaqiruv kechikishi |
| Alerting | Grafana alerting → Telegram (platforma admin) | **Fiskal**: `ofd_acked_at` bo'lmagan eng eski chek 24/40/46/48 soat bosqichlari (qaror #43), `fm_state != ok`; **agent**: Do'kon agenti oflayn (lokal ko'prik rejimida > 15 daqiqa); navbat ishi muvaffaqiyatsizligi; DB/Redis mavjudligi; WAL arxivi kechikishi (> 5 daqiqa — RPO buzilishi); **UzCloud billing** (hisob-faktura muddati) |
| Tenant-boshiga sarf | `ai_requests`, `notifications_log` | Tarif limitlari (M17), unit-iqtisod |

---

## 6. Qo'llab-quvvatlanadigan brauzerlar va qurilmalar

- **Back-office PWA**: barcha zamonaviy brauzerlar (Chrome, Edge, Safari, Firefox) — uskunaga bog'liq emas.
- **Veb-kassa (PWA, offline)** — to'liq matritsa `24-frontend-arxitekturasi.md` §6.2:
  - **Windows PK, Chrome/Edge** — asosiy kassa platformasi: barcha printer transportlari (Web Serial, WebUSB, HTTP ePOS/WebPRNT, Do'kon agenti orqali xom TCP 9100, bulut, tizim printeri); lokal fiskal ko'prik — Do'kon agenti (.NET Framework 4.8, Windows 10/11).
  - **Android Chrome** — WebUSB, BLE, HTTP va bulut printerlar; fiskal kassa faqat fiskal hamkorning bulut rejimida.
  - **iPhone/iPad (Safari)** — **shartli**: kassa faqat fiskal hamkorning bulut rejimida va faqat o'rnatilgan PWA (Home Screen) sifatida; chop etish — faqat bulut printer yoki elektron chek zaxirasi. Aks holda iOS — faqat back-office.
- **Android POS (keyingi bosqich, native Kotlin)** — bozordagi terminallar (UZKASSA N5 — Android 7.1, PAX A930, Sunmi P3) asosida; minimal versiya `28-android-pos.md` da (minSdk 24); fiskal modul — SAM/NFC orqali (`21` §1).

---

## 7. Uskunalar ro'yxati (narx bilan)

### 7.1 Shtrix-kod skanerlari (USB HID / "keyboard wedge")

| Model | Narx (so'm) |
|---|---|
| Arzon simli modellar | ~554 100 dan |
| MERTECH CL-2310 HR P2D SUPERLEAD (simsiz) | 1 500 000 |
| MERTECH CL-2320 (simsiz) | 1 414 700 |
| MERTECH CL-2410 (simsiz) | 1 500 000–1 532 600 |
| Honeywell Youjie HF600 | 1 778 400 |
| Honeywell MS7120 Orbit | 2 696 844 |

### 7.2 Chek printerlari (ESC/POS)

| Model | Ulanish | Narx (so'm) |
|---|---|---|
| Xprinter XP-58IIT | USB | ~297 000–360 000 |
| GP-C180I | USB | 353 814 |
| MHT-P58C | USB | 355 000 |
| Xprinter LP-U58 | USB | 396 000 |
| Xprinter XP-Q200II | USB/LAN (xom TCP 9100 — Do'kon agenti orqali) | 1 607 976 |
| MITSU RP-809 | USB/LAN | 2 105 400 |
| Sewoo SLK-TS400 | USB/LAN | 2 382 186 |
| Bixolon SRP-330 II | USB/LAN | 2 977 733 |
| Sunmi 58 mm Cloud Printer V2 (Sunmi bulut API, CloudPRNT emas) | Bulut | 1 150 000–1 233 000 (micros.uz/Uzum) |
| Epson TM-m30II USB+Eth | Server Direct Print / ePOS-Print | 4 700 000 (OfficeMax.uz) |
| Epson TM-m30III | Server Direct Print / ePOS-Print | 5 109 000 (USB+Eth) – 6 646 000 (Wi-Fi/BT) (OfficeMax.uz) |
| Star TSP143IV UE | CloudPRNT (+ MQTT) | 7 123 000 (OfficeMax.uz) |

Bulut printerlar Toshkentda asosan bitta reseller orqali (rasmiy distributor yo'q), zaxira kanal — import (AQSh narxi ~$265–400). iOS kassa uchun uskuna to'plami ~5–7 mln so'm — mijozga oldindan ko'rsatiladi; arzon yo'l — Windows PK yoki Android planshet + USB printer. Narxlar 2026-10-16 holatiga.

### 7.3 Tarozilar

| Model | Turi | Narx (so'm) | Protokol |
|---|---|---|---|
| Oddiy savdo tarozilari (yorliqsiz) | Kassada tortish | 250 000–750 000+ | Ko'pi — protokolsiz (qo'lda og'irlik); RS-232/USB-COM modellari (CAS-M, Mertech POS2-M, Massa-K "Протокол 100") — Web Serial, MVP'dan keyin |
| Rongta RLS1000A / RLS1100 | Yorliqli | 3 330 600–3 727 100 (scalesstore.gl.uz) | Ethernet + vendor dasturi |
| CAS CL5000J | Yorliqli | 15 913 000 (a-one.uz) | TCP/IP (port 20304, CL-Works), RS-232 |
| Mertech M-ER 725/727 PM | Yorliqli (Android) | 18 303 000 (mertech.uz) | Shtrih-Print (UDP 1111 / RS-232) |

Og'irlik shtrix-kodi — EAN-13 `PP CCCCC VVVVV K`; prefiks — tenant sozlamasi (`weight_barcode_templates[]`), standart **22** — og'irlik (gramm), **21** — summa (so'm, ≤ 99 999). PLU yuklash — MVP'da CSV eksport, keyin Do'kon agentining `scale.plu_upload` vazifasi.

### 7.4 Yorliq printerlari

| Model | Buyruq tillari | Narx (so'm) |
|---|---|---|
| Xprinter XP-365B (bozor standarti) | TSPL + ESC/POS (ZPL yo'q), 76 mm | 499 990–649 000 (Uzum/Asaxiy/REGOS) |
| Gainscha GP-3121TUD | — | ~699 000 |
| Xprinter XP-420B / XP-470B (USB+LAN) | TSPL, ZPL, EPL, DPL, 108 mm | 969 000 / 1 079 990 |
| Mertech DT80 | ZPL | 1 768 400 |
| Godex G500 | EZPL | 1 940 000–2 229 000 |
| TSC TE200 | TSPL-EZD + ZPL/EPL/DPL emulyatsiyasi | 2 583 000 |
| Zebra ZD220d | ZPL II, EPL 2 | 3 875 000 |

Barcha modellarda Windows drayveri bor — yorliq brauzer + drayver/PDF orqali chop etiladi (`24` §6.3). Ommaviy lentalar: 58×40 (~13 500 so'm/rulon, 450–500 dona), 58×30, 43×25, 40×30, 30×20 mm.

### 7.5 Android POS terminallari

| Model | Narx (so'm) | Texnik |
|---|---|---|
| UZKASSA N5 | 3 315 000 | Android 7.1, 8GB/1GB |
| UZKASSA P100 | 1 950 000 | Android 5.1, Quad-Core 1.0GHz, 8GB/1GB |
| A-Pay P10 | 2 699 000 | — |
| Sunmi P3 ("terminal + fiskalizatsiya" to'plami) | 990 000 (Rahmat) | FM SAM slotda, API yopiq (MVP'dan keyin) |

### 7.6 Fiskal modul va Do'kon agenti

- **Fiskal modul (FM)** — fiskal operator/hamkor beradi (USB-ridyer + JavaCard yoki SAM); narxi va yetkazish tartibi — hamkordan. Xizmat haqi 1 BHM/yil (440 000 so'm) — do'kon operatorga to'laydi (VMQ-943 1-ilova 55-band).
- **Do'kon agenti** — do'konning mavjud Windows 10/11 kompyuterida (.NET Framework 4.8), qo'shimcha uskuna emas; lokal fiskal ko'prik va xom TCP 9100 printerlar uchun shart (qaror #60).

---

## 8. Lokalizatsiya

- **Asosiy til — o'zbek (lotin), ikkinchi til — rus** (i18next/react-i18next). Til almashtirish tugmasi barcha ekranlarda bir xil joyda (`06-ekranlar-umumiy.md`, 1.4-bo'lim).
- **Kirill qidiruv**: `pg_trgm` indeks (`11-malumotlar-modeli.md`, 1-bo'lim).
- Chek ikki tilda — o'zbek (birinchi, majburiy) + ixtiyoriy rus (`products.name_ru`), fiskal rekvizitlar operator formatida (qaror #29). Chek printerida o'zbek kirill harflari (Қ/Ғ/Ҳ) — raster rejimi (`24` §6.1).
- Shrift — tizim shrifti; U+02BB va kirill gliflari Bosqich 0 skrinshot-testida tekshiriladi, yetishmasa self-hosted Noto Sans (qaror #57).

---

## 9. Accessibility (asosiy)

MVP darajasi (26 #52): semantik HTML va ARIA (shadcn/Radix komponentlari), narx/summa raqamlari eng katta shrift (boshqa matndan ~1,5x), yuqori kontrast, teginish maydoni POS'da 48×48 dp (asosiy tugmalar 56 dp), mobil back-office'da 44×44 dp (26 #13), to'liq klaviatura navigatsiyasi POS'da (F-tugmalar). To'liq WCAG 2.1 AA audit — keyingi bosqich.

---

## 10. Ma'lumot saqlash muddati (retention)

| Ma'lumot turi | Muddat | Manba/holat |
|---|---|---|
| Buxgalteriya birlamchi hujjatlari va registrlari | **Kamida 5 yil** (hisobot yilidan keyin) | O'RQ-404, 29-modda (O'RQ-683 tahririda) — [lex.uz/docs/-2931253](https://lex.uz/docs/-2931253) |
| Soliq hujjatlari | **3 yil** (2024-01-01'dan) | Soliq kodeksi 22-modda (1-qism, 7-xatboshi), 84-modda, 88-modda — [lex.uz/docs/4674902](https://lex.uz/docs/4674902) |
| `audit_log` | **Kamida 5 yil** (ichki siyosat) | Buxgalteriya muddatiga tenglashtirilgan (`15-xavfsizlik-va-audit.md`, 6.3-bo'lim); insident izlari o'chirilmaydi (ЗРУ-764 16-modda) |
| WAL arxivi va operatsion backup (PITR oynasi) | **30 kun** (standart, sozlanadi) | `15-xavfsizlik-va-audit.md` §7.1; RPO ≤ 5 daqiqa — qaror #51 |
| Arxiv backup | **≥ 5 yil** | Qaror #51 |
| `ai_requests` (AI so'rov jurnali) | **1 yil** | Ichki siyosat — xarajat audit/billing nazorati |
| `notifications_log` (SMS/Telegram) | **1 yil** | Ichki siyosat |
| 1C eksporti: `onec_export_batches`, `onec_export_items` (`op_spec`siz), `onec_object_refs`, yozish vazifalari/natijalari, `onec_reconciliations` | **5 yil** | Buxgalteriya muddatiga mos (qaror #7), `33-1c-integratsiya.md` §15.1 |
| 1C: `onec_export_items.op_spec` / o'qish vazifalari va natijalari, `onec_agent_logs` / `onec_events` | **90 kun / 30 kun / 1 yil** | `onec_cleanup` cron (`33-1c-integratsiya.md` §4.4, §15.1) |

---

## 11. Tenant-boshiga xarajat va unit-iqtisod — yagona 99 000 so'm/oy tarif

**Narx modeli** (qaror #22): **bitta tarif — 99 000 so'm/oy** — barcha modul, AI oylik limiti, Telegram bot + **1 virtual kassa** (dastur); qo'shimcha virtual kassa — **+39 000 so'm/oy** (`addons.extra_register`); yillik to'lovda **−20%** (950 400 so'm/yil); **30 kunlik sinov**. Fiskal operatorga to'lanadigan FM haqi tarifga kirmaydi — uni do'kon to'laydi.

**Bizning xarajatimiz — bitta kassali tenant, oyiga:**

| Xarajat komponenti | 100 tenantda | 1000 tenantda | Manba/izoh |
|---|---|---|---|
| Hosting (UzCloud) | **~25 800 so'm** | **~7 000 so'm** | 3.2 va 3.3-bo'lim |
| AI (Haiku 5.5 standart, AI-03 Haiku → Sonnet eskalatsiya) | **~900–6 900 so'm** (yengil–o'rta) | xuddi shu | `22-ai-qatlami.md` §13 (CBU kursi 12 011,65); og'ir profil oylik token budjeti bilan cheklanadi |
| SMS (Eskiz, 95 so'm/SMS) — faqat zaxira kanal (qaror #34) | **~0 so'm** (asosiy holat) | xuddi shu | Telegram va Google'ga ulanmagan foydalanuvchida zaxira sifatida ~1 900–4 750 so'm |
| Click/Payme (billing komissiyasi, 1–2%) | **~1 000 so'm** | xuddi shu | 99 000 so'mdan |
| Agent OV kod-imzolash sertifikati ($129/yil ≈ 1,55 mln so'm/yil) | **~1 300 so'm** | **~130 so'm** | SSL.com OV + eSigner; platforma doimiy xarajati ÷ tenantlar |
| Fiskal modul (o'z reyestrimiz rejimida) | **0 so'm** — do'kon operatorga to'laydi | 0 | 1 BHM/yil = 440 000 so'm ≈ 36 700 so'm/oy/kassa (VMQ-943 1-ilova 55-band; interim — har kassa uchun) |
| **Jami xarajatimiz** | **≈ 29 000–35 000 so'm** | **≈ 9 000–15 000 so'm** | |
| **Marja (support xodimisiz)** | **≈ 64 000–70 000 so'm** | **≈ 84 000–90 000 so'm** | Support — 12-bo'lim |

**Do'konning umumiy oylik xarajati (1 kassa)**: 99 000 (tarif) + ~36 700 (FM haqi operatorga) ≈ **135 700 so'm** — onboarding va narx sahifasida ochiq ko'rsatiladi.

**Pilot davri (reyestr tasdiqlanguncha, fiskal hamkor orqali)**: hamkor kassa haqini biz to'laymiz — chakana narx **~123 600 so'm/oy/kassa** (Rahmat virtual kassa; ulgurji narx so'raladi); 20 kassa × 3 oy ≈ 7,4 mln so'm + ulanish (`21` §1). Bu davrda bitta kassali tenant bo'yicha marja manfiy — pilot xarajati sifatida qabul qilinadi.

**Qo'shimcha kassa narxi (+39 000 so'm/oy) — qayta ko'riladi**: narx kassa-boshiga fiskal xarajat ~35–39 ming so'm degan taxminga asoslangan. Faktlar: (a) o'z reyestrimizda bizning qo'shimcha kassa xarajatimiz deyarli nol (FM haqini do'kon to'laydi); (b) hamkor orqali ishlasak — hamkor narxi (chakana ~123 600) qo'shimcha kassa narxidan ancha yuqori, har qo'shimcha kassada zarar. Yakuniy narx hamkor ulgurji narxi va reyestr natijasidan keyin asoschi tomonidan belgilanadi (26 #168).

**Ogohlantirish**: so'rovlar soni, sig'im va tenant soni — taxmin; birlik narxlar (UzCloud, Claude, Eskiz, SSL.com, BHM) — manbali (2026-10-16). Pilotdan keyin real `ai_requests`, infratuzilma hisob-fakturalari va support vaqti bilan qayta hisoblanadi (26 #24).

---

## 12. Qo'llab-quvvatlash modeli (support)

**Boshlang'ich bosqich — faqat asoschi (qaror #35)**: alohida support operator ishga olinmaguncha barcha murojaatni asoschi shaxsan qabul qiladi.

| Band | Qaror (interim, pilotda tasdiqlanadi) |
|---|---|
| Kanallar | Telegram (bot ichida "/yordam") + bitta telefon raqami + **"kassa ishlamayapti" shoshilinch liniyasi** |
| Ish vaqti | **Har kuni 09:00–21:00** (Toshkent) |
| Javob maqsadi — kritik (fiskal/OFD, 48 soat bloki, Do'kon agenti, markirovka, lokaut) | **15 daqiqa** (ish vaqtida); ish vaqtidan tashqari shoshilinch liniya — navbatchi (asoschi) |
| Javob maqsadi — oddiy savol | **24 soat** |
| Sabab | 48 soatdan keyin kassa bloklanadi (qaror #43) — dam olish kunlari ham kritik muammo 40 soatlik ogohlantirishdan keyin hal qilinishi kerak |
| Xodim xarajati | Boshlang'ich bosqich — **0** (asoschi); keyin ~6,7–7 mln so'm/oy (1 operator) — 11-bo'limdagi marjadan alohida |
| Qayta ko'rib chiqish | **300** to'lovchi tenant (yoki asoschi ulgurmay qolganda) — operator yollanadi, narx/xodim nisbati qayta hisoblanadi |

Pilot o'lchovlari (30 kun): p95 checkout, sync kechikishi, tiket/do'kon/hafta, tenant xarajati (UzCloud + Claude + SMS) ↔ spec maqsadlari (26 #24).

---

## 13. 1C integratsiyasi (Bosqich 7) — hajm, vaqt, xarajat

Manba — `33-1c-integratsiya.md` §15; barcha raqamlar **taxmin**, pilot oldi testi P-19 da (real «Бухгалтерия для Узбекистана 3.0.64.x» fayl bazasi) o'lchanadi.

### 13.1 Hajm va vaqt

| Parametr | Qiymat (taxmin) |
|---|---|
| Kunlik chek (katta do'kon) | 2 000 (3.1-bo'lim) → 1C'da chek emas, kassa × kun bitta «Отчет о розничных продажах» (ОРП) |
| ОРП qatorlari | 300–1 500 (tovar × QQS × belgi); > 3 000 — bo'linadi |
| `ObjectSpec` hajmi | 1 500 qator ≈ 400 KB JSON, gzip ≈ 50 KB |
| Yozish + o'tkazish (fayl baza) | 1 500 qator: ≈ 12 000 COM chaqiruvi + o'tkazish 10–120 s |
| Oddiy do'kon (1 kassa, ~300 qator, 3–5 hujjat) approve → `done` | **< 3 daqiqa** |
| Katta do'kon (3 kassa, 1 500 qator, 10–20 hujjat) | **< 10 daqiqa** |
| Preview qurish (W-36 → `preview`) | **< 10 s** (2 000 chek) |
| Long-poll ulanishlari | 1 000 tenant × 1 agent = 1 000 parallel async ulanish (uvicorn async + Redis pub/sub) — `api` ichida, alohida VM shart emas |
| Server yuklamasi | `poll` — 1 so'rov / 25 s / agent; `hello` — 1 / 10 daq; `heartbeat` — faqat lease paytida; Do'kon agentining `fiscal.status` — 1 / 5 daq |
| Mavjudlik | Agent API — asosiy API bilan bir xil maqsad (2-bo'lim); agent API ishlamasa partiyalar kutadi, kassa ta'sirlanmaydi (lokal API internetsiz ishlaydi) |

### 13.2 Agent offline

- Do'kon kompyuteri o'chiq bo'lsa tasdiqlangan partiyalar **muddatsiz navbatda kutadi**; kompyuter qaytganda **sana tartibida**, har kun ketma-ket yuboriladi (D+1 D yakunlanmaguncha boshlanmaydi).
- Navbatda ish bor va agent 2 soat jim — Telegram `onec_agent_offline`, keyin kuniga bir marta (`onec_agent_offline_check`, har 15 daqiqa).
- 1C eksporti qonuniy muddatga bog'liq emas (48 soatlik OFD muddati — kassaning o'z kanali); kechikish faqat buxgalterning 1C'dagi ko'rinishini kechiktiradi. Lokal fiskal ko'prik rejimida esa agent kassaning ishlash sharti — oflayn bo'lsa POS chek chiqara olmaydi (`21` §1), alert 5-bo'limda.
- Alert chegaralari (*taxmin*): `onec_task_lease_expired_total` 15 daqiqada > 10; `onec_unknown_outcomes_total` sutkada > 20; har `ONEC_TASK_REJECTED`; bitta tenantda `failed` partiya > 24 soat (`33-1c-integratsiya.md` §15.4).

### 13.3 Xarajat va litsenziya

| Band | Qiymat | Izoh |
|---|---|---|
| Authenticode **OV kod-imzolash sertifikati** (Do'kon agenti `.exe`/o'rnatuvchi) | **SSL.com OV — $129/yil** (5 yillikda $96,75/yil), eSigner bulut imzosi (apparat tokenni O'zbekistonga jo'natish shart emas); Sectigo — ~$211 (reseller) – ~$536/yil (token bilan) | 2023-06-01 dan kalit faqat apparat token/HSM'da (CA/B Forum); Microsoft Artifact Signing O'zbekiston tashkilotlariga mavjud emas. Sertifikat MChJ nomiga — yuridik shaxs tashkil etilgach (26 #130). Kerak bo'ladigan vaqt: lokal fiskal ko'prik tanlansa — Bosqich 5 dan oldin, aks holda Bosqich 7 dan oldin. SmartScreen obro'si bir necha hafta va yuzlab o'rnatishda yig'iladi |
| 1C litsenziyasi | **Mijozning xarajati** | 1C **ПРОФ/КОРП** («Базовая»da COM yo'q, qaror #41); agent mijozning litsenziyali PK'sida, vositachi dastur litsenziya sonini kamaytirmaydi (1C FAQ IX.1-57). Agent alohida ish o'rni hisoblanadimi — 26 #100 (OQ-052) |
| Agent uchun alohida 1C foydalanuvchisi «ERP integratsiya» | Xarajat yo'q | Minimal huquq (`33-1c-integratsiya.md` §15.3) |
| Tarif | 99 000 so'm/oy ichida | Qaror #41 |
| Qo'llab-quvvatlash | Onboarding (agent o'rnatish, moslashtirish) asoschi vaqtini oladi — pilotda o'lchanadi | 12-bo'lim |

---

## Ochiq savollar

Faqat tashqi javob kerak bo'lgan bandlar:

1. **Pilot o'lchovlari** — SLO, sig'im, unit-iqtisod marjasi, support yuklamasi (1, 3, 11, 12-bo'limlar) — 26 #24 (OQ-098). Interim: shu fayldagi standart maqsadlar, telemetriya birinchi kundan.
2. **UzCloud shartnomasi** — SLA foizi va kompensatsiya, DBaaS HA/PITR, at-rest shifrlash, K8s CP narxi — 26 #51 (OQ-043). Interim: o'z WAL PITR, maqsad 99,5%.
3. **Fiskal hamkor narxi va qo'shimcha kassa narxi** — hamkor ulgurji narxi, +39 000 so'm qayta ko'rib chiqilishi — 26 #168; hamkor integratsiyasi — 26 #109 (OQ-012).
4. **Reyestr xarajatlari** — Kiberxavfsizlik markazi ekspertizasi narxi, muvofiqlik sertifikati, 1 BHM birligi (har kassa yoki subyekt) — 26 #42 (OQ-011).
5. **OV kod-imzolash sertifikati** — CA O'zbekiston MChJ'sini qabul qiladimi, hujjatlar, muddat — 26 #105; yuridik shaxs — 26 #130 (OQ-046).
6. **Printer transportlarining amaliy sinovi** (Bosqich 3 qabul testlari) — 26 #139 (OQ-060).
7. **Faqat elektron chek** ruxsati (iOS kassa yo'li) — 26 #112 (OQ-018).
8. **Eskiz.uz SMS** shartnomasi va yetkazish tezligi — 26 #45 (OQ-102).
9. **1C yozish tezligi** (13.1 maqsadlari) — 26 #135 (OQ-054).

## Manbalar

- `spec/kod-uchun/10-umumiy-arxitektura.md`, `11-malumotlar-modeli.md`, `15-xavfsizlik-va-audit.md`, `21-integratsiyalar.md`, `22-ai-qatlami.md`, `23-backend-arxitekturasi.md`, `24-frontend-arxitekturasi.md`
- `spec/kod-uchun/03-modullar-talablari.md`, `06-ekranlar-umumiy.md`, `09-ai-funksiyalar.md`, `05-mvp-chegarasi.md` (3.3-bo'lim — tariflar va unit-iqtisod talabi)
- `research_notes/ochiq-savollar/P1-soliq-fiskal.md` (48 soat bloki, reyestr muddatlari, 1 BHM, hamkor narxi), `P2-efaktura-markirovka.md` (markirovka muddatlari, E-IMZO-SERVER), `P4-huquq-hosting.md` §4 (UzCloud: SLA, S3, KMS, DBaaS, oferta 4.4, narxlar), `P6-uskuna-ai-narx.md` (bulut printerlar, tarozi, yorliq printerlari, AI narxi), `D-qarorlar-va-E-standartlar.md` (qaror #51, #58; OQ-046 OV sertifikat, OQ-098 support)
- `research_notes/texnik/04-arxitektura-va-stack.md`, `06-raqobatchilar-texnik-va-uskunalar.md`, `07-hosting-lokalizatsiya-xavfsizlik.md`
- `spec/kod-uchun/33-1c-integratsiya.md` §15; `research_notes/1c-integratsiya/04-integratsiya-arxitekturasi.md` §2.9
- uzcloud.uz/en/prices, /en/oferta, /en/status; officemax.uz, scalesstore.gl.uz, a-one.uz, mertech.uz, uzum.uz, asaxiy.uz (2026-10-16); ssl.com, cabforum.org (kod-imzolash); rhmt.uz/pos (hamkor kassa narxi)
