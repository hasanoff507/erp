# Android POS (keyingi bosqich)

*2026-10-14 · Asos: foydalanuvchi qarori (Kotlin, keyingi bosqich — veb birinchi), `spec/02-arxitektura/04-offline-sync.md` (bitta sinxronizatsiya protokoli), `08-frontend-arxitekturasi.md` (umumiy naqsh, API generatsiyasi), `research_notes/texnik/02-kassa-ofd-markirovka.md` (fiskal modul, PAX/UZKASSA), `06-raqobatchilar-texnik-va-uskunalar.md` (uskunalar, ESC/POS, Android POS terminallari), `spec/01-mahsulot/04-ekranlar-va-ux.md` (POS-nn ekranlari).*

> Bu hujjat **hozirdan tayyorlanadi, lekin amalga oshirish veb-kassadan keyingi bosqichda boshlanadi** (`spec/README.md`). Maqsad — veb bilan bitta backend/protokolni baham ko'rish, keyinroq boshlash tezroq bo'lishi uchun.

> **Eslatma** *(2026-10-15: foydalanuvchi qarori, D3)*: bu hujjat — **native Kotlin** Android POS (keyingi bosqich). U **Android Chrome'dagi veb-kassa PWA**dan (hozir ham mavjud, `08-frontend-arxitekturasi.md` §6) alohida: veb-kassa Android Chrome'da WebUSB/Web Serial/Web Bluetooth orqali uskunaga to'g'ridan-to'g'ri ulanadi, native Android POS esa shu hujjatdagi `hardware/*` adapterlari (4-bo'lim) orqali ishlaydi — ikkisi bir xil backend/sync protokolidan foydalanadi (3-bo'lim), lekin uskuna integratsiyasi usuli farq qiladi. D3 qarori (iOS/iPadOS qo'llab-quvvatlash, bulut printer) native Android POS'ga ta'sir qilmaydi — bu faqat veb-kassa (brauzer) tomoniga tegishli.

## Asosiy xulosalar

1. **Kotlin + Jetpack Compose**, lokal baza — **Room (SQLite)**; sinxronizatsiya — veb-kassa bilan **AYNAN BIR XIL** protokol va voqea formati (`04-offline-sync.md`: `client_event_id`, `device_id`, `seq`, `type`, `created_at`, `payload`; `POST /sync/push`, `GET /sync/pull?cursor=`) — ikki klient bitta backend kontraktini baham ko'radi, dublikat mantiq yozilmaydi.
2. Fon sinxronizatsiya — **WorkManager**: tezkor (`expedited`) push — voqea yaratilganda darhol; davriy pull (**taxmin: 15 daqiqa**) + ulanish qaytganda darhol (NetworkCallback); `enqueueUniqueWork` bilan bir vaqtda ikki sync ishining yugurishi oldini oladi (veb'dagi Web Locks'ga mos vazifa).
3. **Uskunalar**: fiskal modul/printer SDK (PAX, UZKASSA — bozorda ustun, `research_notes/texnik/02-kassa-ofd-markirovka.md` §4, `06-fayl` §3) adapter (port/adapter) naqshi bilan abstraksiyalanadi; rasmiy texnik API hujjatlari ikkisida ham ochiq manbada **topilmadi** (CRPT Turon kabi, 403/yopiq) — integratsiyadan oldin vendor bilan rasmiy aloqa shart (ochiq savol).
4. **ESC/POS** — chek/yorliq chop etish uchun de-fakto standart (Epson, `06-fayl` §3); **shtrix-kod/markirovka skaneri** — ichki kamera (CameraX + ZXing/ML Kit, veb'dagi `@zxing/browser`ga mos) va tashqi USB/Bluetooth HID "keyboard wedge" (klaviatura emulyatsiyasi, qo'shimcha drayversiz) ikkisi ham qo'llab-quvvatlanadi.
5. **Tarozi** — ulanish protokoli ochiq manbada aniqlanmagan (`06-fayl` §3: "aniq protokol nomi topilmadi"); **qo'lda og'irlik kiritish doimiy zahira** sifatida saqlanadi, protokol aniqlanganda adapter qo'shiladi.
6. **NFC/karta terminali** — ushbu tadqiqotda hech qanday manba topilmadi; bank/to'lov hamkori SDK'si orqali alohida integratsiya talab qiladi, **ochiq savol**.
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
| DI | Hilt (taklif) | Google tavsiyasi, Compose bilan yaxshi integratsiya — **tanlov tasdiqlanmagan, ochiq savol** |
| Tarmoq | Retrofit + OkHttp | Backend REST API bilan aloqa, xuddi veb'dagi axios kabi |
| API tiplari | OpenAPI → Kotlin (openapi-generator yoki qo'lda) | Veb'da orval ishlatiladi (`08-frontend-arxitekturasi.md`); Kotlin tomonida vosita tanlovi **ochiq savol** (7-bo'lim) |
| Navigatsiya | Jetpack Navigation Compose | POS-nn ekranlari orasida |
| Test | JUnit, Turbine (Flow test), Espresso/Compose UI test | `04-offline-sync.md` §13'dagi chaos/tarmoq testlariga mos backend-mock bilan |

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
    ├── fiscal/                 # Fiskal modul/printer adapter interfeysi + PAX/UZKASSA implementatsiyalari
    ├── scanner/                 # Kamera (CameraX+ZXing) va HID skaner abstraksiyasi
    ├── scale/                   # Tarozi interfeysi (protokol aniqlanmaguncha stub + qo'lda kiritish)
    └── card-terminal/            # NFC/karta terminali interfeysi (ochiq savol, 6-bo'lim)
```

Har bir `feature/*` modul o'z ichida `data/domain/ui` uch qatlamiga bo'linadi (veb'dagi `model/ui` naqshiga mos, lekin Android idiomalariga moslashtirilgan): `ui/` — Compose ekran + ViewModel, `domain/` — use case (masalan `CreateSaleUseCase`, veb'dagi Effector `effect`siga mos), `data/` — Room DAO + repository implementatsiyasi.

**Import qoidasi**: `app → feature → core`, faqat pastga; `feature/*` modullari bir-birini bevosita import qilmaydi, faqat `core/domain` orqali bog'lanadi (veb'dagi FSD `app → pages → features → entities → shared` qoidasiga mos tamoyil).

---

## 3. Sinxronizatsiya — backend bilan baham ko'riladigan qism

Android POS **xuddi veb-kassa bilan bir xil** backend kontraktidan foydalanadi — alohida Android-specific sync API yozilmaydi:

| Baham ko'riladigan narsa | Tafsilot |
|---|---|
| REST API | Bitta FastAPI backend, bitta OpenAPI sxema (`00-umumiy-arxitektura.md` §1: "Hammasi bir xil REST API dan foydalanadi") |
| Sinxronizatsiya protokoli | `POST /sync/push`, `GET /sync/pull?cursor=` — so'rov/javob formati `04-offline-sync.md` §3 bilan bir xil |
| Outbox voqea formati | `client_event_id` (UUIDv7), `device_id`, `seq`, `type`, `created_at`, `payload` — `04-offline-sync.md` §2 bilan bir xil JSON tuzilma |
| Idempotentlik | `sync_receipts` jadvali backend tomonida umumiy — qaysi klient yuborishidan qat'i nazar bir xil tekshiruv |
| Huquq/rol modeli | `role_permissions`, `memberships` — bir xil kod (`permission_code`) |
| Lokal keshlanadigan ma'lumot toifalari | Katalog, narx, shtrix-kod, mijoz+qarz, limit, huquq, smena — `04-offline-sync.md` §1 bilan bir xil ro'yxat, Room jadvallarida saqlanadi (Dexie jadvallariga mos) |
| Konflikt qoidalari | Ombor overselling, qarz limiti, narx muzlatish, LWW+version — `04-offline-sync.md` §5 bilan bir xil, chunki qoidalar serverda amalga oshiriladi, klient faqat ko'rsatadi |
| 48 soatlik fiskal taymer | Hisoblash mantiqi serverda; Android UI faqat ko'rsatadi (POS-12 ekraniga mos) |

Farq faqat **klient tomonidagi saqlash mexanizmi** (Room o'rniga Dexie) va **UI freymvorki** (Compose o'rniga React) — protokol darajasida farq yo'q. Bu bitta backend sync-engine kodini ikki marta yozmaslik imkonini beradi.

---

## 4. Uskunalar

### 4.1 Fiskal modul / printer SDK

- Bozorda ustun qurilmalar: **PAX A930** (Android 7.1/PayDroid, PCI PTS/EMV sertifikatlangan, Kapitalbank orqali tarqatiladi) va **UZKASSA** (N5, P100) — `research_notes/texnik/02-kassa-ofd-markirovka.md` §4, `06-fayl` §4.
- Rasmiy, ochiq texnik SDK hujjatlari **ikkisida ham topilmadi** — CRPT Turon'dagi kabi integrator maqomi/shartnoma talab qilinishi mumkin (`12-taxminlar-va-murojaatlar.md`, 1-band bilan bir xil holat).
- **Tavsiya**: `hardware/fiscal` modulida `FiscalPrinterAdapter` interfeysi (port/adapter naqshi, `00-umumiy-arxitektura.md` §1, 4-band bilan bir xil tamoyil — "tashqi tizim ishlamasa navbatga tushadi va qayta uriniladi"): `openShift()`, `printReceipt(payload)`, `getUnsentCount()` (FM xato kodi 704031'ga mos), `printZReport()`. Har vendor uchun alohida implementatsiya (`PaxFiscalAdapter`, `UzkassaFiscalAdapter`), runtime'da qurilma modeli aniqlanib tanlanadi.

### 4.2 ESC/POS chop etish

- Fiskal bo'lmagan chop etish (yorliq, qayta chop etish, Bluetooth kvitansiya printerlari) uchun **ESC/POS** buyruq to'plami — Epson de-fakto standarti, aksariyat printerlar (Xprinter, MERTECH, Bixolon) qo'llab-quvvatlaydi (`06-fayl` §3).
- `hardware/fiscal`dan ajratilgan alohida `EscPosPrinterAdapter` — USB/Bluetooth ulanish, veb'dagi "Chekni qayta chop etish" tugmasi mantiqiga mos (`04-ekranlar-va-ux.md` §1.6).

### 4.3 Shtrix-kod/markirovka skaneri

- **Ichki kamera**: CameraX + ML Kit Barcode Scanning yoki ZXing (veb'dagi `@zxing/browser` tanloviga mos, `08-frontend-arxitekturasi.md` §4).
- **Tashqi USB/Bluetooth HID skaner**: "keyboard wedge" rejimida ishlaydi — Android tizim darajasida klaviatura kiritish sifatida qabul qiladi, fokusda turgan matn maydoniga kod tushadi (veb'dagi `useBarcodeWedge` hook yondashuviga mos, `06-fayl` §3).
- Markirovka (DataMatrix) skanerlash xatosi yuqori bo'lgani uchun (`04-ekranlar-va-ux.md` §1.7) — avtomatik qayta urinish + qo'lda MXIK kiritish zahirasi shu modulda ham amalga oshiriladi.

### 4.4 Tarozi

- Ulanish protokoli (RS-232/Bluetooth, masalan "CAS" yoki "Shtrix-M" kabi standart) ochiq manbada **topilmadi** (`06-fayl` §3: faqat "Frontol/LiteBox bilan integratsiya" umumiy da'vosi bor).
- `hardware/scale` moduli hozircha **stub interfeys** (`ScaleAdapter.readWeight(): Flow<Weight?>`) — protokol aniqlanmaguncha har doim `null` qaytaradi, UI qo'lda kiritish maydonini ko'rsatadi (`04-ekranlar-va-ux.md` §1.6 bilan bir xil zahira tamoyili).

### 4.5 NFC / karta terminali

- Ushbu tadqiqotning hech bir faylida NFC/karta terminali integratsiyasi haqida ma'lumot **topilmadi** — bu talab vazifa tavsifida berilgan, lekin spetsifikatsiya manbalarida yo'q.
- **Taklif** (tasdiqlanmagan): mustaqil aloqaga ega bank terminali (Humo/Uzcard/Visa/Mastercard EMV) bilan integratsiya — bank SDK'si orqali, xuddi to'lov adapterlari (Click/Payme) kabi alohida `hardware/card-terminal` moduli. Bu **ochiq savol** — tanlangan bank/to'lov hamkori bilan alohida aniqlashtirish kerak (`04-ekranlar-va-ux.md` Ochiq savol #11'dagi "mustaqil aloqaga ega karta terminali offlayn rejimda ishlashi" muammosiga ham bog'liq).

---

## 5. Lokal saqlash shifrlanishi

| Variant | Afzalligi | Kamchiligi |
|---|---|---|
| **SQLCipher** (butun Room bazasi) | Butun baza shaffof shifrlanadi, kod o'zgarishi minimal (Room + SQLCipher driver), POS SDK integratsiyalarida keng tarqalgan amaliyot | Ozgina ishlash (performance) xarajati, shifrlash kaliti boshqaruvi (Android Keystore'da saqlanadi) |
| **Android Keystore + maydon darajasida shifrlash** | Faqat eng nozik maydonlar (mijoz telefoni, qarz summasi) shifrlanadi, kamroq performance xarajati | Ko'proq qo'lda kod, qidiruv/filtr (masalan telefon bo'yicha) shifrlangan maydonda qiyinlashadi |

**Tavsiya**: SQLCipher — standart, kamroq xato xavfi. Yakuniy tanlov va benchmark **ochiq savol**.

- **Chiqishda (logout)**: Room bazasi to'liq o'chiriladi/qayta yaratiladi, shifrlash kaliti Android Keystore'dan bekor qilinadi — veb'dagi Dexie tozalash siyosatiga mos (`04-offline-sync.md` §12).
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

**`minSdk` tavsiyasi**: **API 24 (Android 7.0)** — PAX A930 va UZKASSA N5'ni (ikkisi ham 7.1) qamrab oladi, Jetpack Compose va zamonaviy kutubxonalar (CameraX, ML Kit) bilan to'liq mos. Bu tanlov **UZKASSA P100'ni (Android 5.1, API 22) qamrovdan chiqaradi** — **ochiq savol/biznes qarori**: (a) P100'ni qo'llab-quvvatlamaslik (eski/arzon model deb hisoblash), (b) alohida yengil "legacy" rejim yozish, (c) `minSdk`ni 22'ga tushirib Compose/kutubxona cheklovlariga rozi bo'lish. Yakuniy qaror — pilot do'konlardagi real qurilma flotini tekshirgandan keyin.

---

## 8. Bosqichlar rejasi

| Faza | Mazmuni |
|---|---|
| **Faza 0 (hozir, 2026-10-14)** | Faqat hujjat (bu fayl) — amalga oshirish boshlanmagan, veb-kassa birinchi bosqichda |
| **Faza 1** | Asosiy kassa oqimi (M01: smena, sotuv, to'lov, chek), offline-sync (`04-offline-sync.md` protokoli), bitta fiskal vendor bilan pilot (PAX **yoki** UZKASSA — ikkisini bir yo'la boshlamaslik) |
| **Faza 2** | Qaytarish (M02), qarz daftari (M08, POS-13), kassa pul harakati (M16, POS-14/15), ombor skanerlash (M05/M06/M07, POS-08/09/10) |
| **Faza 3** | Markirovka (Asl belgisi) integratsiyasi, ikkinchi fiskal vendor qo'llab-quvvatlash, tarozi/NFC (agar protokol/hamkor aniqlansa) |
| **Faza 4** | To'liq tarqatish (MDM fleet boshqaruvi, ko'p do'kon), Play Store (agar kerak bo'lsa) ikkinchi kanal |

---

## Ochiq savollar

1. PAX/UZKASSA fiskal SDK'larining rasmiy texnik hujjatlari ochiq manbada topilmadi (403/yopiq, CRPT Turon bilan bir xil holat) — integratsiyadan oldin vendor bilan rasmiy aloqa/shartnoma kerak.
2. `minSdk` tanlovi — UZKASSA P100 (Android 5.1) qamrovdan tushib qolishi mumkin; pilot flotini tasdiqlash kerak (7-bo'lim).
3. Tarozi ulanish protokoli aniqlanmagan (`06-fayl` §3) — qo'lda kiritish doimiy zahira bo'lib qoladi.
4. NFC/karta terminali integratsiyasi — tadqiqot manbalarida umuman yo'q, bank/to'lov hamkori bilan alohida aniqlashtirilishi kerak.
5. Play Store'da GMS mavjudligi maqsadli POS qurilmalarida tasdiqlanmagan — shu sabab MDM/APK asosiy kanal deb taklif qilindi, yakuniy qaror pilotdan keyin.
6. OpenAPI'dan Kotlin klient generatsiya vositasi (openapi-generator vs qo'lda Retrofit+kotlinx.serialization) — hali tanlanmagan.
7. DI vositasi (Hilt vs Koin) — tasdiqlanmagan, boshlang'ich taklif Hilt.
8. SQLCipher vs Android Keystore maydon-darajasida shifrlash — ishlash tezligi/hajm bo'yicha sinov o'tkazilmagan.
9. Bitta smenani ikki Android qurilma baham ko'rganda fiskal chek raqamlash tartibi — `04-offline-sync.md` §3.3'dagi bilan bir xil ochiq savol.

## Manbalar

- `spec/README.md` — stack qarori (Android keyingi bosqich, hujjatlar hozirdan).
- `spec/02-arxitektura/00-umumiy-arxitektura.md` — komponentlar, port/adapter naqshi.
- `spec/02-arxitektura/04-offline-sync.md` — sinxronizatsiya protokoli, voqea formati, konflikt qoidalari (bu hujjat bilan baham ko'riladi).
- `spec/02-arxitektura/08-frontend-arxitekturasi.md` — veb tomonidagi naqsh (taqqoslash uchun), API generatsiyasi.
- `research_notes/texnik/02-kassa-ofd-markirovka.md` — fiskal modul, OFD, PAX A930.
- `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md` — Android POS terminallari (UZKASSA N5/P100), ESC/POS, HID skaner, tarozi.
- `research_notes/texnik/12-taxminlar-va-murojaatlar.md` — CRPT Turon/vendor integratsiya noaniqligi (o'xshash taxmin naqshi).
- `spec/01-mahsulot/02-modullar-talablari.md` — M01, M02, M05, M06, M07, M08, M16.
- `spec/01-mahsulot/04-ekranlar-va-ux.md` — POS-nn ekranlari, uskuna UX qoidalari (§1.6, §1.7).
