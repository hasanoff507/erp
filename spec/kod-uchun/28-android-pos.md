# 28. Android POS (keyingi bosqich)

**Maqsad:** Veb-kassadan keyingi bosqichda boshlanadigan native Kotlin Android POS uchun texnologiya, modul tuzilishi va uskuna integratsiyasi rejasini hozirdan belgilash — veb bilan bitta backend/sync protokolini baham ko'rish, keyinroq boshlash tezroq bo'lishi uchun.
**Kim uchun:** Claude (Android POS bosqichi boshlanganda), asoschi.
**Bog'liq fayllar:** `16-offline-sync.md` (sinxronizatsiya protokoli), `24-frontend-arxitekturasi.md` (veb tomonidagi naqsh, API generatsiyasi), `06-ekranlar-umumiy.md` (POS-nn ekranlari), `27-backlog.md` (MVP'dan keyin ro'yxati), `01-qarorlar.md` (#12, #43, #44, #60, #62, #64), `26-ochiq-savollar-reestri.md`.
**Holat:** joriy, 2026-10-16 — faqat hujjat, amalga oshirish veb-kassadan keyingi bosqichda boshlanadi.

> Bu hujjat — **native Kotlin** Android POS (keyingi bosqich). U **Android Chrome'dagi veb-kassa PWA**dan (hozir ham mavjud, `24-frontend-arxitekturasi.md` §6) alohida: veb-kassa Android Chrome'da WebUSB/Web Serial/Web Bluetooth orqali uskunaga to'g'ridan-to'g'ri ulanadi, native Android POS esa shu hujjatdagi `hardware/*` adapterlari (4-bo'lim) orqali ishlaydi — ikkisi bir xil backend/sync protokolidan foydalanadi (3-bo'lim), lekin uskuna integratsiyasi usuli farq qiladi. iOS/iPadOS qo'llab-quvvatlash va bulut printer qarori native Android POS'ga ta'sir qilmaydi — bu faqat veb-kassa (brauzer) tomoniga tegishli.

## Asosiy xulosalar

1. **Kotlin + Jetpack Compose**, lokal baza — **Room (SQLite)**; sinxronizatsiya — veb-kassa bilan **AYNAN BIR XIL** protokol va voqea formati (`16-offline-sync.md`: `client_event_id`, `device_id`, `seq`, `type`, `created_at`, `payload`; `POST /sync/push`, `GET /sync/pull?cursor=`) — ikki klient bitta backend kontraktini baham ko'radi, dublikat mantiq yozilmaydi.
2. Fon sinxronizatsiya — **WorkManager**: tezkor (`expedited`) push — voqea yaratilganda darhol; davriy pull (**taxmin: 15 daqiqa**) + ulanish qaytganda darhol (NetworkCallback); `enqueueUniqueWork` bilan bir vaqtda ikki sync ishining yugurishi oldini oladi (veb'dagi Web Locks'ga mos vazifa).
3. **Uskunalar**: fiskal modul — veb bilan bir xil **`FiscalPort`** kontrakti (Kotlin): `AndroidIntentFiscalAdapter` (vendor SDK/intent), `ApduFiscalAdapter` (SAM/NFC'dagi FM "0400" applet'iga APDU — keyin), `FakeFiscalAdapter`; FM javobi veb bilan bir xil (`fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `qr_url`). Ommaviy SDK yo'q — vendor/hamkor javobi kutiladi (26 #63 (OQ-063), Xat 9). Android'da Do'kon agenti (qaror #60) kerak emas — FM qurilmaning o'zida.
4. **ESC/POS** — chek/yorliq chop etish uchun de-fakto standart (Epson, `06-fayl` §3); **shtrix-kod/markirovka skaneri** — ichki kamera (CameraX + ZXing/ML Kit, veb'dagi `@zxing/browser`ga mos) va tashqi USB/Bluetooth HID "keyboard wedge" (klaviatura emulyatsiyasi, qo'shimcha drayversiz) ikkisi ham qo'llab-quvvatlanadi.
5. **Tarozi** — og'irlik shtrix-kodi EAN-13 `PP CCCCC VVVVV K`, prefiks do'kon sozlamasi (`settings.weight_barcode_templates`; 22 = gramm, 21 = summa — 26 #31); jonli og'irlik — serial/Bluetooth adapter (keyin); **qo'lda og'irlik kiritish doimiy zahira**.
6. **Karta to'lovi** — MVP'da mustaqil terminal, kassir `card_type` (`personal/corporate/social/unknown`, `method='card'` da majburiy), ijtimoiy kartada `card_mask` + `rrn` kiritadi — veb bilan bir xil (qaror #64, 26 #65/#121); integratsiyalangan NFC terminal — keyin.
11. **48 soatlik fiskal blok** (qaror #43) Android'da ham bir xil: 24 soat 🟡, 40 soat 🔴 + M18, 46 soat modal, 48 soat — `ofd_acked_at IS NULL` eng eski chekdan hisoblanib yangi fiskal chek bloklanadi (`FISCAL_OFFLINE_48H_BLOCKED`); taymer **qurilmada ham** hisoblanadi (offline'da server yo'q), server qayta tekshiradi. Markirovka kodi chek ichida (qaror #62, `MARKING_PRECHECK=warn`).
12. **Auth**: qurilma tokeni veb bilan bir xil — access 15 daqiqa, refresh sliding 14 / mutlaq 180 kun (qaror #44).
7. **Modul tuzilishi** — clean architecture: `data` (Room, Retrofit/sync), `domain` (use case'lar, entity'lar), `ui` (Compose, ViewModel) qatlamlari, veb'dagi FSD'ga mos ravishda modul (Gradle modullari) bo'yicha ajratilgan (2-bo'lim).
8. **Shifrlash**: butun Room bazasini **SQLCipher** bilan shifrlash tavsiya etiladi (standart amaliyot, POS SDK'lari ko'pincha qo'llab-quvvatlaydi); muqobil — Android Keystore asosida maydon darajasida shifrlash (5-bo'lim).
9. **Tarqatish**: asosiy kanal — **MDM/APK** (vendor nazorati, GMS (Google Play Services) bo'lmagan PayDroid qurilmalarda ham ishlaydi); Play Store — faqat umumiy Android planshet/telefonlarda POS sifatida ishlatilsa, ikkinchi darajali kanal (6-bo'lim).
10. **Qo'llab-quvvatlanadigan qurilmalar** (`06-raqobatchilar-texnik-va-uskunalar.md`, `02-kassa-ofd-markirovka.md`): PAX A930 va UZKASSA N5 — Android 7.1; UZKASSA P100 — Android 5.1 (eski). Tavsiya qilingan `minSdk` — **24 (Android 7.0)** — P100'ni qamrovdan chiqaradi, bu **ochiq savol/biznes qarori** (7-bo'lim).

---

## 1. Texnologiya stacki

| Qatlam | Tanlov | Izoh |
|---|---|---|
| Til | Kotlin | Android native standarti |
| UI | Jetpack Compose | Zamonaviy, deklarativ; veb'dagi React/shadcn tamoyiliga mos (komponent-asosida) |
| Lokal baza | Room (SQLite ustida) | `04-arxitektura-va-stack.md` §2.1 — Android'da native, fiskal SDK'lar bilan mos |
| Fon ishlar | WorkManager | Tezkor push + davriy pull, tarmoq cheklovlari (`NetworkType.CONNECTED`) bilan |
| DI | Hilt | Google tavsiyasi, Compose bilan yaxshi integratsiya (26 #68) |
| Tarmoq | Retrofit + OkHttp | Backend REST API bilan aloqa, xuddi veb'dagi axios kabi |
| API tiplari | OpenAPI → Kotlin (openapi-generator) | Veb'da orval ishlatiladi (`24-frontend-arxitekturasi.md`); 26 #67 |
| Navigatsiya | Jetpack Navigation Compose | POS-nn ekranlari orasida |
| Test | JUnit, Turbine (Flow test), Espresso/Compose UI test | `16-offline-sync.md` §13'dagi chaos/tarmoq testlariga mos backend-mock bilan |

---

## 2. Modul tuzilishi (clean architecture)

```
android/
├── app/                        # Kirish nuqtasi, DI, navigation host
├── core/
│   ├── ui/                     # Compose dizayn tizimi (POS wireframelarga mos komponentlar)
│   ├── data/                   # Room DB, DataStore (sozlamalar), sync motor, outbox
│   ├── domain/                 # Entity'lar, use case'lar, repository interfeyslari
│   └── network/                # Retrofit klient, OpenAPI-generatsiya qilingan DTO'lar
├── feature/
│   ├── pos/                    # POS-01…04, 07, 11, 14, 15 — M01, M03, M09, M16
│   ├── warehouse/               # POS-08, 09, 10 — M05, M06, M07
│   ├── debts/                   # POS-13 — M08
│   └── sync-status/              # POS-12
└── hardware/
    ├── fiscal/                 # FiscalPort (veb bilan bir xil kontrakt) + AndroidIntent/Apdu/Fake adapterlari
    ├── scanner/                 # Kamera (CameraX+ZXing) va HID skaner abstraksiyasi
    ├── scale/                   # Tarozi: EAN-13 og'irlik kodi parseri + jonli og'irlik adapteri (keyin) + qo'lda kiritish
    └── card-terminal/            # Integratsiyalangan terminal (keyin); MVP — card_type/card_mask/rrn qo'lda
```

Har bir `feature/*` modul o'z ichida `data/domain/ui` uch qatlamiga bo'linadi (veb'dagi `model/ui` naqshiga mos, lekin Android idiomalariga moslashtirilgan): `ui/` — Compose ekran + ViewModel, `domain/` — use case (masalan `CreateSaleUseCase`, veb'dagi Effector `effect`siga mos), `data/` — Room DAO + repository implementatsiyasi.

**Import qoidasi**: `app → feature → core`, faqat pastga; `feature/*` modullari bir-birini bevosita import qilmaydi, faqat `core/domain` orqali bog'lanadi (veb'dagi FSD `app → pages → features → entities → shared` qoidasiga mos tamoyil).

---

## 3. Sinxronizatsiya — backend bilan baham ko'riladigan qism

Android POS **xuddi veb-kassa bilan bir xil** backend kontraktidan foydalanadi — alohida Android-specific sync API yozilmaydi:

| Baham ko'riladigan narsa | Tafsilot |
|---|---|
| REST API | Bitta FastAPI backend, bitta OpenAPI sxema (`10-umumiy-arxitektura.md` §1: "Hammasi bir xil REST API dan foydalanadi") |
| Sinxronizatsiya protokoli | `POST /sync/push`, `GET /sync/pull?cursor=` — so'rov/javob formati `16-offline-sync.md` §3 bilan bir xil |
| Outbox voqea formati | `client_event_id` (UUIDv7), `device_id`, `seq`, `type`, `created_at`, `payload` — `16-offline-sync.md` §2 bilan bir xil JSON tuzilma |
| Idempotentlik | `sync_receipts` jadvali backend tomonida umumiy — qaysi klient yuborishidan qat'i nazar bir xil tekshiruv |
| Huquq/rol modeli | `role_permissions`, `memberships` — bir xil kod (`permission_code`) |
| Lokal keshlanadigan ma'lumot toifalari | Katalog, narx, shtrix-kod, mijoz+qarz, limit, huquq, smena — `16-offline-sync.md` §1 bilan bir xil ro'yxat, Room jadvallarida saqlanadi (Dexie jadvallariga mos) |
| Konflikt qoidalari | Ombor overselling, qarz limiti, narx muzlatish, LWW+version — `16-offline-sync.md` §5 bilan bir xil, chunki qoidalar serverda amalga oshiriladi, klient faqat ko'rsatadi |
| 48 soatlik fiskal shkala va blok | Qoida bir xil (qaror #43): qurilma `ofd_acked_at IS NULL` eng eski chekdan hisoblaydi va 48 soatda yangi fiskal chekni bloklaydi (`FISCAL_OFFLINE_48H_BLOCKED`), server qayta tekshiradi; UI — POS-12 |
| To'lov rekvizitlari | `sale_payments`/`debt_payments`: `card_type`, `card_mask`, `rrn`, `qr_type`, `provider_tx_id` — veb bilan bir xil CHECK'lar (qaror #64) |
| Fiskal natija | `fiscal_receipts`: `receipt_seq` (qurilma) + `fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `fiscal_at`, `ofd_acked_at`, `payment_form` (qaror #12) |

Farq faqat **klient tomonidagi saqlash mexanizmi** (Room o'rniga Dexie) va **UI freymvorki** (Compose o'rniga React) — protokol darajasida farq yo'q. Bu bitta backend sync-engine kodini ikki marta yozmaslik imkonini beradi.

---

## 4. Uskunalar

### 4.1 Fiskal modul / printer SDK

- Bozorda ustun qurilmalar: **PAX A930** (Android 7.1/PayDroid, PCI PTS/EMV sertifikatlangan, Kapitalbank orqali tarqatiladi) va **UZKASSA** (N5, P100) — `research_notes/texnik/02-kassa-ofd-markirovka.md` §4, `06-fayl` §4.
- Ommaviy SDK yo'q; arxitektura ochiq: FM — JavaCard applet "0400" (SAM/NFC/USB), buyruqlar `RECEIPT_REGISTER`, `ZREPORT_OPEN/CLOSE`, `ACK`, `SYNC`, TLV chek (`TAG_LABEL` — markirovka kodi) — `github.com/qo0p/acrsim-android`. Sunmi P3 "terminal + fiskalizatsiya" to'plamlari bor, API yopiq. Vendor/hamkor javobi — 26 #63 (Xat 9).
- `hardware/fiscal` modulida veb bilan bir xil **`FiscalPort`**: `openShift()`, `closeShift(): ZReport`, `registerSale(receipt): FiscalResult{terminalId, receiptSeq, fiscalDatetime, fiscalSign, qrUrl}`, `registerRefund(receipt, refundRef)`, `getDeviceStatus()` (`fm_state`), `listUnsent()`, `resendUnsent()`; summalar port chegarasida tiyinda (`Long`). Adapterlar: `AndroidIntentFiscalAdapter`, `ApduFiscalAdapter` (keyin), `FakeFiscalAdapter`; runtime'da qurilma modeli bo'yicha tanlanadi. FM bloki (`fm_state='locked'`) → `FISCAL_DEVICE_LOCKED`.

### 4.2 ESC/POS chop etish

- Fiskal bo'lmagan chop etish (yorliq, qayta chop etish, Bluetooth kvitansiya printerlari) uchun **ESC/POS** buyruq to'plami — Epson de-fakto standarti, aksariyat printerlar (Xprinter, MERTECH, Bixolon) qo'llab-quvvatlaydi (`06-fayl` §3).
- `hardware/fiscal`dan ajratilgan alohida `EscPosPrinterAdapter` — USB/Bluetooth ulanish, veb'dagi "Chekni qayta chop etish" tugmasi mantiqiga mos (`06-ekranlar-umumiy.md` §1.6).

### 4.3 Shtrix-kod/markirovka skaneri

- **Ichki kamera**: CameraX + ML Kit Barcode Scanning yoki ZXing (veb'dagi `@zxing/browser` tanloviga mos, `24-frontend-arxitekturasi.md` §4).
- **Tashqi USB/Bluetooth HID skaner**: "keyboard wedge" rejimida ishlaydi — Android tizim darajasida klaviatura kiritish sifatida qabul qiladi, fokusda turgan matn maydoniga kod tushadi (veb'dagi `useBarcodeWedge` hook yondashuviga mos, `06-fayl` §3).
- Markirovka (DataMatrix) skanerlash xatosi yuqori bo'lgani uchun (`06-ekranlar-umumiy.md` §1.7) — avtomatik qayta urinish + qo'lda kiritish zahirasi (faqat online, 26 #14) shu modulda ham; kod GS ajratgichi bilan aynan chek qatoriga yoziladi, lokal takror-kod tekshiruvi, `MARKING_PRECHECK=warn` (qaror #62).

### 4.4 Tarozi

- Asosiy yo'l — yorliq chop etuvchi tarozining EAN-13 og'irlik kodi (`settings.weight_barcode_templates`, 26 #31) — skaner orqali, qo'shimcha protokolsiz.
- Jonli og'irlik (`ScaleAdapter.readWeight(): Flow<Weight?>`) — vendor protokoli bilan keyin; adapter bo'lmasa `null`, UI qo'lda kiritish maydonini ko'rsatadi (`06-ekranlar-umumiy.md` §1.6).

### 4.5 NFC / karta terminali

- MVP: mustaqil bank terminali bilan karta to'lovi kassada qo'lda belgilanadi (online va offline) — `card_type` majburiy, ijtimoiy kartada `card_mask` (`^[0-9]{4}\*+[0-9]{4}$`) va `rrn` (qaror #64, 26 #65/#121). Chekda to'lov shakli `payment_form` (`cash/card/qr/mixed`).
- Integratsiyalangan terminal (bank SDK, `hardware/card-terminal`) — keyin. Virtual kassa reyestri talabi (karta/UzQR "shu qurilma orqali") — 26 #170.
- UzQR: statik — qo'lda tasdiq; dinamik — `UzqrPort` (26 #49), veb bilan bir xil.

---

## 5. Lokal saqlash shifrlanishi

| Variant | Afzalligi | Kamchiligi |
|---|---|---|
| **SQLCipher** (butun Room bazasi) | Butun baza shaffof shifrlanadi, kod o'zgarishi minimal (Room + SQLCipher driver), POS SDK integratsiyalarida keng tarqalgan amaliyot | Ozgina ishlash (performance) xarajati, shifrlash kaliti boshqaruvi (Android Keystore'da saqlanadi) |
| **Android Keystore + maydon darajasida shifrlash** | Faqat eng nozik maydonlar (mijoz telefoni, qarz summasi) shifrlanadi, kamroq performance xarajati | Ko'proq qo'lda kod, qidiruv/filtr (masalan telefon bo'yicha) shifrlangan maydonda qiyinlashadi |

**Qaror**: SQLCipher (26 #69); benchmark — Faza 1 da.

- **Chiqishda (logout)**: Room bazasi to'liq o'chiriladi/qayta yaratiladi, shifrlash kaliti Android Keystore'dan bekor qilinadi — veb'dagi Dexie tozalash siyosatiga mos (`16-offline-sync.md` §12).
- Karta ma'lumotlari (PAN/CVV) hech qachon qurilmada saqlanmaydi — bank terminali/SDK orqali to'g'ridan-to'g'ri ishlanadi.

---

## 6. Yangilanish tarqatish

| Kanal | Afzalligi | Kamchiligi/xavf |
|---|---|---|
| **Play Store** | Avtomatik yangilanish, standart tarqatish infratuzilmasi | PAX/UZKASSA kabi PayDroid qurilmalarda to'liq Google Play Services (GMS) mavjudligi **tasdiqlanmagan** — ko'p fiskal POS qurilma AOSP-asosida, GMS'siz bo'lishi mumkin |
| **MDM (Mobile Device Management) / to'g'ridan-to'g'ri APK** | GMS'ga bog'liq emas, markazlashgan qurilma boshqaruvi (fleet), vendor tarqatish kanali bilan mos keladi, fiskal POS'larda odatiy amaliyot | Yangilanish tarqatish uchun qo'shimcha infratuzilma (MDM server) kerak |

**Tavsiya**: **MDM/APK** — asosiy kanal, chunki maqsadli qurilmalar (PAX, UZKASSA) maxsus POS uskunalari, GMS'ga tayanish xavfli. Play Store — faqat agar kelajakda umumiy Android planshet/telefon POS sifatida ishlatilsa (masalan kichik do'konlarda), ikkinchi darajali/ixtiyoriy kanal sifatida qo'shiladi.

---

## 7. Qo'llab-quvvatlanadigan qurilmalar

| Model | Android versiyasi | Manba |
|---|---|---|
| PAX A930 | 7.1 (PayDroid) | `research_notes/texnik/02-kassa-ofd-markirovka.md` §4 |
| UZKASSA N5 | 7.1 | `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md` §3 (smartpos.uz) |
| UZKASSA P100 | 5.1 | `06-fayl` §3 (smartpos.uz) |
| A-Pay P10 | Aniqlanmagan | `06-fayl` §3 |

**`minSdk`**: **API 24 (Android 7.0)** (26 #64) — PAX A930 va UZKASSA N5'ni (ikkisi ham 7.1) qamrab oladi, Jetpack Compose va zamonaviy kutubxonalar (CameraX, ML Kit) bilan to'liq mos; UZKASSA P100 (Android 5.1) qamrovdan chiqariladi. Sunmi P3 — FM SDK javobiga bog'liq (26 #63).

---

## 8. Bosqichlar rejasi

| Faza | Mazmuni |
|---|---|
| **Faza 0 (hozir)** | Faqat hujjat (bu fayl) — amalga oshirish boshlanmagan, veb-kassa birinchi bosqichda |
| **Faza 1** | Asosiy kassa oqimi (M01: smena, sotuv, to'lov — `card_type`/`card_mask`/`rrn`, statik UzQR; chek), offline-sync (`16-offline-sync.md` protokoli), 48 soatlik shkala va blok (qaror #43), bitta fiskal vendor bilan pilot (PAX **yoki** UZKASSA/Sunmi — ikkisini bir yo'la boshlamaslik; 26 #63 javobidan keyin) |
| **Faza 2** | Qaytarish (M02), qarz daftari (M08, POS-13), kassa pul harakati (M16, POS-14/15), ombor skanerlash (M05/M06/M07, POS-08/09/10) |
| **Faza 3** | Markirovka (kod chek ichida, qaror #62), ikkinchi fiskal vendor, dinamik UzQR (26 #49), jonli tarozi/integratsiyalangan karta terminali (agar protokol/hamkor aniqlansa) |
| **Faza 4** | To'liq tarqatish (MDM fleet boshqaruvi, ko'p do'kon), Play Store (agar kerak bo'lsa) ikkinchi kanal |

---

## Ochiq savollar

1. PAX/UZKASSA/Sunmi FM'iga uchinchi tomon ilovasidan kirish (SDK/intent/APDU), sertifikatlash talablari va test FM — 26 #63 (OQ-063), Xat 9. Android POS boshlanishini bloklaydi (MVP'dan keyin).
2. Hal qilingan: minSdk 24 (26 #64).
3. Hal qilingan: tarozi og'irlik shtrix-kodi formati (26 #31); jonli og'irlik protokoli — Faza 3.
4. Hal qilingan: integratsiyalangan karta terminali MVP'da yo'q, `card_type`/`card_mask`/`rrn` qo'lda (26 #65, qaror #64).
5. Hal qilingan: MDM/APK asosiy kanal (26 #66).
6. Hal qilingan: openapi-generator (26 #67).
7. Hal qilingan: Hilt (26 #68).
8. Hal qilingan: SQLCipher (26 #69).
9. Hal qilingan: bitta smena — bitta qurilma; FM raqami `fm_receipt_seq` alohida (qaror #12).
10. Hal qilingan: qurilma tokeni veb bilan bir xil (qaror #44, 26 #165).

## Manbalar

- `spec/README.md` — stack qarori (Android keyingi bosqich, hujjatlar hozirdan).
- `spec/kod-uchun/10-umumiy-arxitektura.md` — komponentlar, port/adapter naqshi.
- `spec/kod-uchun/16-offline-sync.md` — sinxronizatsiya protokoli, voqea formati, konflikt qoidalari (bu hujjat bilan baham ko'riladi).
- `spec/kod-uchun/24-frontend-arxitekturasi.md` — veb tomonidagi naqsh (taqqoslash uchun), API generatsiyasi.
- `research_notes/texnik/02-kassa-ofd-markirovka.md` — fiskal modul, OFD, PAX A930.
- `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md` — Android POS terminallari (UZKASSA N5/P100), ESC/POS, HID skaner, tarozi.
- `research_notes/texnik/12-taxminlar-va-murojaatlar.md` — CRPT Turon/vendor integratsiya noaniqligi (o'xshash taxmin naqshi).
- `spec/kod-uchun/03-modullar-talablari.md` — M01, M02, M05, M06, M07, M08, M16.
- `spec/kod-uchun/06-ekranlar-umumiy.md` — POS-nn ekranlari, uskuna UX qoidalari (§1.6, §1.7).
