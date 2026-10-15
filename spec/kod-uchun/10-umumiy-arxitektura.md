# Umumiy arxitektura

**Maqsad:** Tizimning yuqori darajadagi arxitekturasi — komponentlar, asosiy oqimlar, muhitlar va hujjatlar xaritasi.
**Kim uchun:** Backend/frontend dasturchilar, arxitektura qarorlarini qabul qiluvchilar.
**Bog'liq fayllar:** `11-malumotlar-modeli.md`, `14-autentifikatsiya-oauth2.md`, `16-offline-sync.md`, `21-integratsiyalar.md`, `22-ai-qatlami.md`, `23-backend-arxitekturasi.md`, `24-frontend-arxitekturasi.md`, `26-ochiq-savollar-reestri.md`, `27-backlog.md`, `33-1c-integratsiya.md`, `34-1c-agent.md`.
**Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. **Bitta backend (Python + FastAPI) — modulli monolit**, mikroservislar emas: 18 modul bitta kod bazasida, lekin har modul o'z papkasi, o'z jadvallari va o'z ichki API'si bilan (`23-backend-arxitekturasi.md`). Kichik jamoa va SME yuklamasi uchun eng sodda va arzon yo'l; kerak bo'lsa keyin ajratiladi.
2. **Bitta PostgreSQL baza, ko'p tenant**: har jadvalda `tenant_id` + Row-Level Security (`15-xavfsizlik-va-audit.md`).
3. **Mijozlar (klientlar)**: (a) veb ilova — back-office + veb-kassa (birinchi bosqich), (b) Android POS — Kotlin (keyingi bosqich), (c) Telegram bot (Egasi), (d) ichki admin panel. Hammasi **bir xil REST API** dan foydalanadi.
4. **Davlat va tashqi tizimlar backend orqali** ulanadi (e-faktura operatori, e-TTN, Asl belgisi, Click/Payme/Uzum, UzQR, SMS, Telegram, Claude API) — har biri alohida adapter (port/adapter naqshi), tashqi tizim ishlamasa navbatga tushadi va qayta uriniladi (`21-integratsiyalar.md`). Ikki istisno: **E-IMZO** imzosi brauzerda; **fiskal chek** — ochiq bulut OFD API yo'q, chekni fiskal modul (FM) imzolaydi va OFD'ga yuboradi, POS unga **Do'kon agenti** fiskal ko'prigi orqali yoki hamkor bulut API'si orqali yetadi (§2, qaror #60).
5. **Ikki xil "haqiqat"**: hujjatlar (chek, kirim, qaytarish, qarz, xarajat) — o'zgarmas, faqat teskari hujjat bilan bekor qilinadi; qoldiqlar, qarz balanslari, buxgalteriya — hujjatlardan **hisoblanadigan registrlar** (`11-malumotlar-modeli.md`, `13-provodka-qoidalari.md`).
6. **Offline-first kassa**: kassa avval o'z lokal bazasiga yozadi (veb: IndexedDB, Android: SQLite), keyin append-only outbox orqali serverga; server idempotent qabul qiladi (`16-offline-sync.md`).
7. **Fon ishlari** (OFD'ga yuborish, e-faktura, hisobot solishtirish, eslatmalar, Telegram xabarlar, AI) — alohida worker jarayonlar, Redis navbati orqali; API so'rovi tashqi tizimni kutib turmaydi.
8. **AI — chekka qatlam**: `AiProvider` porti (fake | cli | api), pul va soliqni hech qachon AI hisoblamaydi (`22-ai-qatlami.md`); Claude'ga yuborishdan oldin shaxsiy maydonlarni maskalash majburiy, chegaradan tashqari uzatish tenant roziligi bilan (qaror #61).
9. **Autentifikatsiya — o'z OAuth 2.0 implementatsiyamiz**: API komponenti ham AS, ham RS; mock yo'q (`14-autentifikatsiya-oauth2.md`, qaror #14). Google — tashqi OIDC identity-provider sifatida **qo'shimcha** (majburiy emas) kirish yo'li, telefon+parolni almashtirmaydi (§2.2, qaror #34). Obuna muddati 24 soatlik imtiyozdan o'tganda kassa va kirish **to'liq to'xtaydi** (barcha sessiya/token bekor, faqat to'lov havolasi ochiq) (qaror #15).
10. **Do'kon agenti — do'kon PK'sidagi yagona lokal komponent** (qaror #60): C# / .NET Fx 4.8 tray-ilova, admin huquqisiz; imkoniyatlari — fiskal ko'prik (Bosqich 5), xom TCP 9100 printer va tarozi (Bosqich 5), 1C (Bosqich 7). Serverga faqat chiquvchi HTTPS; POS bilan — `127.0.0.1` lokal API.
11. **1C integratsiyasi — alohida modul, faqat COM** (qaror #36–#42, Bosqich 7): server moduli `onec_integration` imzolangan vazifalar navbatini (`onec_agent_tasks`) yuritadi; Do'kon agentining 1C imkoniyati vazifalarni faqat chiquvchi HTTPS **long-poll (pull)** bilan tortadi va 1C bazasiga COM orqali yozadi. Kiruvchi port, OData, 1C ichida publish yo'q; ERP → 1C bir tomonlama; yadro 1C'siz ishlaydi (`33-1c-integratsiya.md`, `34-1c-agent.md`).
12. **Jamoa — asoschi + Claude (2 kishi)** (qaror #35): butun spec va backlog shu tarkibga mo'ljallangan — ketma-ket vertikal bo'laklar, qat'iy kalendar muddatlar yo'q, parallel ish oqimi yo'q (`27-backlog.md`); qo'llab-quvvatlash ham boshlang'ich bosqichda faqat asoschi (`25-nofunksional-talablar.md` §12).

---

## 1. Komponentlar

```mermaid
flowchart LR
  subgraph Klientlar
    W[Veb ilova<br/>React PWA<br/>back-office + veb-kassa]
    A[Android POS<br/>Kotlin — keyin]
    T[Telegram bot]
    ADM[Ichki admin]
  end
  subgraph Dokon["Do'kon PK (Windows)"]
    AG[Do'kon agenti<br/>tray, .NET Fx 4.8<br/>127.0.0.1 lokal API]
    FM[Fiskal modul FM<br/>+ hamkor lokal xizmati]
    PR[LAN printer 9100<br/>tarozi]
    C1[(1C bazasi<br/>БП UZ 3.0)]
  end
  subgraph Server["Backend (UzCloud)"]
    API[FastAPI<br/>REST API]
    ONEC[onec_integration moduli<br/>vazifa navbati, /api/v1/onec-agent/*]
    WK[Worker'lar<br/>navbat ishlari]
    SCH[Rejalashtiruvchi<br/>kunlik/davriy]
    PG[(PostgreSQL<br/>RLS)]
    R[(Redis<br/>navbat, kesh, rate-limit)]
    S3[(Fayl ombori<br/>S3-mos: foto, PDF)]
  end
  subgraph Tashqi["Tashqi tizimlar"]
    OFD[OFD]
    FCL[Fiskal hamkor<br/>bulut API — bo'lsa]
    EF[E-faktura operatori<br/>Faktura.uz / Didox<br/>e-TTN, e-ishonchnoma]
    AB[Asl belgisi<br/>CRPT Turon]
    EI[E-IMZO]
    PAY[Click / Payme / Uzum<br/>UzQR]
    SMS[SMS provayder]
    TG[Telegram API]
    CL[Claude API]
  end
  W & A & ADM --> API
  T --> API
  API --> PG & R & S3
  WK --> PG & R & S3
  SCH --> R
  WK --> EF & AB & PAY & SMS & TG & CL
  WK -. fiskal yo'l b .-> FCL --> OFD
  W -. E-IMZO imzo brauzerda .-> EI
  API --- ONEC
  AG ==>|faqat chiquvchi HTTPS<br/>long-poll pull| ONEC
  AG -->|V8x.COMConnector<br/>Bosqich 7| C1
  W -. fiskal yo'l a: 127.0.0.1 .-> AG
  AG -->|chek imzosi| FM -->|paket| OFD
  AG -->|ESC/POS, PLU| PR
```

| Komponent | Texnologiya | Vazifa |
|---|---|---|
| Veb ilova | React + Vite + TS, FSD, Effector, shadcn/ui, PWA | Back-office va veb-kassa (`24-frontend-arxitekturasi.md`) |
| Android POS | Kotlin, SQLite (Room) | Keyingi bosqich (`28-android-pos.md`) |
| API | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic | Barcha biznes amallar, huquqlar; **shuningdek o'z OAuth 2.0 Authorization Server + Resource Server** (`14-autentifikatsiya-oauth2.md`, qaror #14) — uchinchi tomon auth xizmati yo'q |
| Worker'lar | Python, `SAQ` (Redis navbati; `23-backend-arxitekturasi.md`, qaror #2) | Tashqi tizimlarga yuborish, qayta urinish, AI, xabarlar |
| Rejalashtiruvchi | worker ichida cron (masalan `SAQ` cron) | Kunlik hisobot, eslatmalar, obuna muddati, davlat hisobotini tekshirish |
| Baza | PostgreSQL 16+ (UzCloud DBaaS) | Hamma ma'lumot, RLS bilan tenant ajratish |
| Kesh/navbat | Redis | Navbat, rate-limit, sessiya keshi |
| Fayllar | S3-mos ombor | Xarajat cheki fotosi, OCR rasmlari, PDF hisobotlar |
| Telegram bot | Python (aiogram), API'ning mijozi sifatida | M18 |
| 1C integratsiya moduli | `backend/app/modules/onec_integration` (FastAPI moduli + SAQ job'lar) | M19: kunlik partiyalar, moslashtirish, imzolangan vazifalar navbati (`onec_agent_tasks`), agent API `/api/v1/onec-agent/*` (`aud=urn:erp:onec-agent`) — `33-1c-integratsiya.md` §3–§4 (Bosqich 7) |
| Do'kon agenti | C# / .NET Framework 4.8, per-user tray + alohida worker jarayonlari (fiskal, qurilmalar, x86/x64 COM), DPAPI; repo `agent-1c/` (`34-1c-agent.md` → `34-dokon-agenti.md` ga kengaytiriladi) | Do'kon PK'sida (qaror #60): (1) **fiskal ko'prik** — POS'dan `127.0.0.1` orqali chek oladi, FM/hamkor lokal xizmatiga (FiscalDriveService / Multikassa localhost) beradi, `fiscal_sign`/`qr_url`/`fm_receipt_seq` qaytaradi; (2) xom TCP 9100 ESC/POS printerlar, tarozi (PLU, jonli og'irlik); (3) 1C — vazifani long-poll bilan tortadi, `V8x.COMConnector` orqali yozadi (qaror #38). Serverga kiruvchi ulanish yo'q; Authenticode OV imzosi (26 #105) |
| Fiskal qatlam | `FiscalPort` (backend + POS tomonida), adapterlar `fake` / `multikassa_local` / `fiscaldrive_local` / hamkor bulut; alohida, kam o'zgaradigan paket | Chek → FM → OFD; port chegarasida summa tiyinda; 48 soatlik blok (qaror #43) va `fm_state` nazorati (qaror #60, `21` §1) |

**Nima uchun E-IMZO brauzerda:** E-IMZO kaliti foydalanuvchi kompyuterida (E-IMZO dasturi/plagin) — hujjatni imzolash brauzerda bajariladi, server faqat imzolangan hujjatni oladi va operatorga yuboradi (`research_notes/texnik/03-efaktura-va-tolov.md`).

## 2. Asosiy oqimlar

**Kassa sotuvi (onlayn):** veb-kassa → lokal yozuv (Dexie outbox, `client_event_id`) → `POST /sync/push` (darhol, bitta voqea) → backend: hujjat + qoldiq registri + qarz/kassa harakati + buxgalteriya provodkasi **bitta tranzaksiyada**. POS uchun alohida `POST /sales` yo'q — onlayn va offline yo'l bitta (`16-offline-sync.md` §4.1). Markirovka kodi chek qatorida (qaror #62).

**Fiskal yo'l (qaror #60) — `FiscalPort` ikki turdagi adapter bilan:**

| Yo'l | Oqim | Qachon | Platforma |
|---|---|---|---|
| (a) Do'kon ko'prigi (Local Bridge) | POS → `127.0.0.1` Do'kon agenti → FM / hamkor lokal xizmati (imzo, `fiscal_sign`, QR) → OFD (FM paket bilan yuboradi); natija POS → `/sync/push` bilan serverga | Asosiy yo'l (hamkor lokal ko'prikka ruxsat bersa — 26 #109) | Windows PK'li do'kon; Chrome/Edge veb-kassa |
| (b) Hamkor bulut API | POS → backend → worker → hamkor bulut API → OFD | Faqat hamkorda PK'siz bulut rejimi bo'lsa | iPhone/iPad uchun yagona fiskal yo'l (qaror #21); aks holda iOS — back-office + elektron chek |
| MVP ishlab chiqish | `FISCAL_PROVIDER=fake` — `FakeFiscalAdapter` + FM emulyatori | Bosqich 3–4, CI | Hammasi |

FM tarmoqsiz ham imzolaydi; yuborilmagan cheklar `ofd_acked_at IS NULL` bilan kuzatiladi; eng eskisidan 48 soat o'tsa yangi fiskal chek bloklanadi (qaror #43). Chek raqami: qurilma `receipt_seq` (idempotentlik) + FM `fm_receipt_seq` (qaror #12). Provayder (Click/Payme/Uzum) tomonidagi avtofiskalizatsiya o'chiq — chekni har doim bizning kassa chiqaradi (qaror #64).

**Kassa sotuvi (offline):** lokal yozuv → outbox kutadi → internet qaytgach yuboriladi; fiskal shkala 24/40/46 soat ogohlantirish, 48 soat blok (qaror #43, `16-offline-sync.md` §6).

**Davlat hisobotini solishtirish (M10):** foydalanuvchi davlat hisobotini yuklaydi (API yo'q, MVP'da qo'lda/fayl) → backend ichki hisobdan xuddi shu ko'rsatkichni hisoblaydi → farq jadvali → AI-05 tushuntirish → 5 ish kunlik taymer va eslatmalar 1/3/4-ish kuni (M18, qaror #50).

**Kunni 1C ga yuborish (M19, BP-14, Bosqich 7):** smena yopilishi/jadval → `onec_integration` partiya va preview quradi → Buxgalter BO-23 da preview xeshi bilan tasdiqlaydi → vazifalar `onec_agent_tasks` ga (Ed25519 imzo) → Do'kon agenti `POST /onec-agent/poll` bilan tortadi → COM worker 1C'ga GUID bilan yozadi va o'tkazadi → natija → `read_totals` solishtiruvi → `done`/`partial`/`mismatch` + Telegram. Agentga ish berish `outbox_jobs` (push) orqali emas — pull kanali (`33-1c-integratsiya.md` §3.2–§3.3).

## 3. Muhitlar va deploy

| Muhit | Maqsad | AI rejimi |
|---|---|---|
| local | Dasturchi kompyuteri, docker compose | `fake` yoki `cli` |
| staging | Sinov, davlat tizimlarining test muhitlari (bo'lsa) | `api` (alohida kalit, past limit) |
| production | Mijozlar | faqat `api` |

Deploy: Docker konteynerlar (api, worker, scheduler, web statik, bot) + PostgreSQL va Redis; hosting — UzCloud (`research_notes/texnik/07-hosting-lokalizatsiya-xavfsizlik.md`). UzCloud'da KMS/secret store yo'q — sirlar SOPS/age (yoki o'z-hosted Vault), ilova darajasida envelope shifrlash, o'z WAL PITR, zaxira nusxa boshqa provayderda, UzCloud hisobida avto-to'lov (qaror #65); trace — o'z-hosted Grafana Tempo. CI: testlar, lint, OpenAPI sxemasidan frontend tiplarini qayta generatsiya tekshiruvi. Do'kon agenti serverda deploy qilinmaydi — Authenticode OV bilan imzolangan o'rnatuvchi sifatida tarqatiladi, yangilanishi Ed25519 imzoli manifest (`GET /onec-agent/update-manifest`) orqali (`34-1c-agent.md`, `32-kod-qoidalari.md`).

## 4. Hujjatlar ro'yxati (`spec/kod-uchun/`)

| Fayl | Mazmuni | Holat |
|---|---|---|
| 10-umumiy-arxitektura.md | Shu hujjat | ✅ |
| 11-malumotlar-modeli.md | Jadvallar, hujjatlar, registrlar, holatlar, raqamlash | ✅ |
| 12-db-sxema.md | PostgreSQL 16 DDL, RLS, SECURITY DEFINER funksiyalar, seed, migratsiya tartibi | ✅ |
| 13-provodka-qoidalari.md | BHMS №21 hisoblar, har hujjat uchun Dt/Kt, FIFO/AVECO, davr yopish | ✅ — buxgalter tasdig'i kerak |
| 14-autentifikatsiya-oauth2.md | OAuth 2.0 AS+RS, token, admin panel, obuna lokauti, offline litsenziya | ✅ (qaror #14) |
| 15-xavfsizlik-va-audit.md | Auth, RLS, rollar/ruxsatlar, audit jurnali, backup | ✅ |
| 16-offline-sync.md | Outbox protokoli, to'qnashuvlar, 48 soat, markirovka offline | ✅ |
| 17-api-umumiy.md | API konventsiyalari, xato konverti, yagona xato kodlari katalogi | ✅ |
| 18-api-kassa.md | Kassa, sotuv, qaytarish, qarz, to'lov seanslari API | ✅ |
| 19-api-ombor.md | Katalog, ombor, xarid, ko'chirish, inventarizatsiya, e-faktura (kiruvchi), e-TTN API | ✅ |
| 20-api-moliya-admin.md | QQS, buxgalteriya, hisobotlar, sozlamalar, xarajat, kassa, bank, obuna, AI API | ✅ |
| 21-integratsiyalar.md | Har tashqi tizim: adapter, navbat, qayta urinish, test muhiti holati | ✅ |
| 22-ai-qatlami.md | AiProvider, limitlar, xarajat, eval, ma'lumot to'plash | ✅ |
| 23-backend-arxitekturasi.md | FastAPI modulli monolit, qatlamlar, kutubxonalar | ✅ |
| 24-frontend-arxitekturasi.md | Veb: FSD, Effector, shadcn/ui, kutubxonalar | ✅ |
| 25-nofunksional-talablar.md | Tezlik, sig'im, uskunalar, mavjudlik | ✅ |
| 26-ochiq-savollar-reestri.md | OQ-001…OQ-102 va 1C savollari: Yopildi / Tashqi javob kerak | ✅ |
| 27-backlog.md | Ketma-ket bosqichlar (2 kishilik jamoa — asoschi + Claude), tartib | ✅ (qaror #35) |
| 28-android-pos.md | Kotlin POS (keyingi bosqich) | ✅ |
| 29-atamalar-lugati.md | Atamalar lug'ati (uz/ru/en ↔ kod) | ✅ |
| 30-izchillik-matritsasi.md | US ↔ BP ↔ ekran ↔ endpoint ↔ jadval izchilligi | ✅ |
| 31-qabul-testlari.md | Qabul testlari (QT-*) | ✅ |
| 32-kod-qoidalari.md | Kod yozish qoidalari, CI | ✅ |
| 33-1c-integratsiya.md | 1C integratsiyasi: `onec_integration` moduli, jadvallar, agent protokoli, veb API, ekranlar | ✅ (qaror #36–#42, Bosqich 7) |
| 34-1c-agent.md | Do'kon agenti ichki tuzilishi (`agent-1c/`) — 1C imkoniyati; fiskal ko'prik, printer, tarozi — "Kengaytirish" bo'limi | ✅ (qaror #38, #60) |

## Ochiq savollar

- Fiskal yo'l: hamkor lokal ko'prikka ruxsat beradimi va PK'siz bulut rejimi bormi (iOS) — 26 #109 (OQ-012); VMQ-393 "ikkilamchi tizim" xavfi — 26 #169. Vaqtinchalik standart: `FISCAL_PROVIDER=fake`, yo'l (a) asosiy.
- UzCloud shartnoma SLA va DBaaS PITR — 26 #51 (OQ-043). Vaqtinchalik standart: o'z WAL PITR va boshqa provayderdagi zaxira nusxa (qaror #65).
- Foydalanish shartlari / oferta matni (chegaradan tashqari uzatish roziligi bilan) — 26 #127 (OQ-042).

## Manbalar

- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — OAuth 2.0 AS/RS, obuna lokauti.
- `research_notes/texnik/04-arxitektura-va-stack.md` (multi-tenant, offline-first, event-log, Android, PostgreSQL).
- `research_notes/texnik/07-hosting-lokalizatsiya-xavfsizlik.md` (UzCloud, lokalizatsiya).
- `spec/kod-uchun/03-modullar-talablari.md` (M01–M19), `09-ai-funksiyalar.md` (5-bo'lim).
