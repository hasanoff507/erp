# API katalogi — 2. Ombor, katalog va xarid

**Maqsad:** Mahsulot katalogi, narxlar, yorliqlar, import, qoldiq/partiyalar, kirim, yetkazib beruvchilar, xaridnoma, to'lov, qaytarish, ko'chirish, inventarizatsiya, hisobdan chiqarish, boshlang'ich qoldiq, baholash sozlamalari, qayta hisoblash ishlari, kiruvchi e-faktura, e-TTN va e-ishonchnoma uchun API kontrakti.
**Kim uchun:** Backend/frontend/Android ishlab chiquvchilar, QA.
**Bog'liq fayllar:** `17-api-umumiy.md` (konventsiyalar), `11-malumotlar-modeli.md` (§4 katalog/narx, §5 kontragentlar, §6 hujjatlar, §7 registrlar, §9), `13-provodka-qoidalari.md` (2.6–2.8, 2.12, 2.20, 2.21, §3 FIFO/AVECO), `21-integratsiyalar.md` (§2 e-faktura, §3 E-TTN, §4 Asl belgisi, §5 E-IMZO, §6 e-ishonchnoma, §7 MXIK), `16-offline-sync.md` (§1, §7), `15-xavfsizlik-va-audit.md` (§2.1–2.2), `23-backend-arxitekturasi.md`, `03-modullar-talablari.md` (M04, M05, M06, M07, M09), `04-biznes-jarayonlar.md` (BP-01, BP-09, BP-10, BP-12), `06-ekranlar-umumiy.md` (BO-02…05, BO-08, BO-18, POS-08…12), `09-ai-funksiyalar.md` (AI-03), `34-1c-agent.md` (Do'kon agenti, qaror #60).
**Holat:** joriy, 2026-10-16.

> Bu API — noldan quriladigan tizimning o'z interfeysi; hech qanday tashqi buxgalteriya/ERP formatiga moslashtirilmagan.

## Asosiy xulosalar

1. Bu fayl **ombor/katalog/xarid** qatlamini qamrab oladi: mahsulot katalogi, narxlar, yorliqlar, import, qoldiq/partiyalar, kirim, yetkazib beruvchilar, xaridnoma, to'lov, qaytarish, ko'chirish, inventarizatsiya, hisobdan chiqarish, boshlang'ich qoldiq, baholash sozlamalari, qayta hisoblash ishlari, kiruvchi e-faktura, e-TTN, e-ishonchnoma.
2. Barcha hujjat turlari (`goods-receipts`, `supplier-returns`, `transfers`, `stock-counts`, `write-offs`, `stock-openings`) umumiy hayot sikliga amal qiladi: `POST /{resource}` (draft) → `POST /{id}/post` → `POST /{id}/cancel` (storno — registrlarga teskari yozuv, alohida teskari hujjat yo'q, `11-malumotlar-modeli.md` §1/§6). `price-changes` bundan mustasno — o'z holat mashinasi bor (`draft → pending_approval-ekvivalenti (202) → posted/rejected`, §4).
3. Ma'lumotnomalar (`products`, `product-categories`, `suppliers`) — `archive`/`unarchive` bilan, hech qachon `DELETE` qilinmaydi; `PATCH` optimistik qulflash (`version`) talab qiladi → mos kelmasa `409 VERSION_CONFLICT`.
4. **Import oqimi** (`import-jobs`) uch bosqichli: `upload` (fayl) → `validate` (qator/maydon xatolari) → `commit` (bitta tranzaksiyada `stock-openings`/`debt-openings` yaratiladi). Mahsulot (US-M04-04) va qarz (US-M08-07) importi shu bir yo'l orqali.
5. **Partiya (lot) — tannarxning yagona manbai**: har kirim (qo'lda, e-fakturadan, AI-03 OCR'dan, boshlang'ich qoldiqdan) `stock-lots` yozuvi yaratadi; FIFO/AVECO (`valuation-settings`) shu ma'lumotdan hisoblanadi. Usul faqat **keyingi hisobot yili boshidan** o'zgartiriladi (US-M04-05).
6. **AI-03 (OCR)** — yagona oqim `20-api-moliya-admin.md` #73–75 (`POST /ai/ocr/jobs`, `GET /ai/ocr/jobs/{job_id}`, `POST /ai/ocr/jobs/{job_id}/confirm`); bu faylda alohida OCR endpoint yo'q. `confirm` `doc_type_hint=purchase` uchun to'g'ridan-to'g'ri `goods-receipts` qoralamasini yaratadi — AI hech qachon to'g'ridan-to'g'ri hujjat yozmaydi.
7. **Offline — faqat ikki joyda**: (a) `transfers` — o'z filiallar/omborlar orasida jo'natish **va** qabul qilish offline ruxsat etilgan (`16-offline-sync.md` §7), lekin avtotransportda tashish uchun e-TTN majburiy — offline yaratilgan ko'chirishga e-TTN internet qaytgach, **tashish boshlanishidan oldin** rasmiylashtiriladi (qaror #63, §13); (b) `stock-counts` — skanerlash/sanash to'liq offline (POS-10), lekin yakuniy `review`/`post` online. Qolgan barcha hujjat (kirim, qaytarish, xaridnoma, to'lov, narx, import, hisobdan chiqarish, e-faktura, e-TTN, e-ishonchnoma) — **faqat online**, chunki ular ofis/ombor sharoitida (internet mavjud) yoki tashqi tizim (E-IMZO, Faktura.uz) bilan sinxron ishlaydi. Offline `transfers`/`stock-counts` bu REST endpoint'lar o'rniga `POST /sync/push` outbox voqealari (`transfer.sent`/`transfer.received`, `stock_count.line_recorded`) orqali keladi — bu faylda shu voqea payload'lari hujjat sxemasiga mos qilib ko'rsatiladi, alohida `/sync/push` yo'li `16-offline-sync.md`da.
8. **MXIK** (`tasnif.soliq.uz`) — sinxron, keshlangan qidiruv; chekning/fakturaning majburiy rekviziti, tovar yaratishda bloklovchi emas (saqlanadi, lekin sotishdan oldin to'ldirilishi shart — bu tekshiruv sotuv API'sida, `18-api-kassa.md`).
9. Barcha pul maydonlari `"12000.00"` (decimal string, tiyingacha), miqdor `"10.000"` (3 kasr), narx/tannarx 4 kasr (`"8333.3333"`) — `11-malumotlar-modeli.md` §3 bilan bir xil.
10. **E-TTN va e-ishonchnoma — e-faktura operatori orqali** (MVP'da Faktura.uz, `EInvoicePort`; qaror #63): ichki ko'chirish ("Ombordan omborga") e-TTN'i `transfers` `post`ida yaratiladi, e-TTN ro'yxatdan o'tmaguncha jo'natish taqiqlanadi (`409 ETTN_REQUIRED`); kiruvchi e-TTN'ni yetkazib beruvchi chiqaradi, do'kon elektron tasdiqlaydi/rad etadi; e-ishonchnomani do'kon o'z xodimiga operator orqali beradi (§8, §20).
11. **MVP UI'da filialda bitta ombor** (avtomatik yaratiladi, `warehouse_id` UI'da tanlanmaydi); API va model bir nechta omborni cheklamaydi (qaror #54).

---

## 0. Konventsiyalar (qisqa eslatma)

To'liq konventsiyalar — `17-api-umumiy.md`: base `/api/v1`, resurs nomlari kebab-case ko'plik, ID — UUIDv7, pul — decimal string (2 kasr), miqdor — decimal string (3 kasr), ISO sanalar, cursor pagination (`?cursor=&limit=` → `{items, next_cursor}`), sarlavhalar `X-Branch-Id` (filial scoping, barcha so'rovlarda majburiy — bu fayldagi deyarli barcha resurslar filialga/omborga bog'langan), `Idempotency-Key` (yozuvchi so'rovlarda majburiy, `/sync/push`dan tashqari), `X-CSRF-Token` (cookie-autentifikatsiyali so'rovlarda), xato konverti `{error:{code, message_key, details, request_id}}`, `version` optimistik qulflash → `409 VERSION_CONFLICT`, hujjat sikli `draft → post → cancel` (storno), asinxron Excel import/eksport ishlari.

Bu faylda har bir endpoint uchun: Maqsad, Ruxsat, So'rov, Javob, Xatolar, Idempotentlik, Offline, Bog'liq (US/ekran).

---

## Indeks

| Bo'lim | Resurs | Asosiy endpointlar |
|---|---|---|
| 1 | `products` | `GET/POST /products`, `GET/PATCH /products/{id}`, `POST /products/{id}/archive`, barcode'lar, MXIK qidiruv |
| 2 | `product-categories` | `GET/POST /product-categories`, `PATCH/POST archive` |
| 3 | `units` | `GET /units` (global, faqat o'qish) |
| 4 | `prices`, `price-changes` | narx tarixi, narx o'zgarishi hujjati |
| 5 | `label-print-queue`, `label-print-jobs`, `label-templates` | yorliq navbati, chop etish ishi |
| 6 | `import-jobs` | `products`/`opening_stock`/`opening_debts` Excel/CSV import |
| 7 | `stock-balances`, `stock-lots`, `stock-moves` | qoldiq, partiya, harakat tarixi, kam qoldiq |
| 8 | `goods-receipts` | kirim hujjati (qo'lda / e-fakturadan / AI-03'dan), posting |
| 9 | `counterparties?is_supplier=true` | yetkazib beruvchi ko'rinishi, STIR qidiruv |
| 10 | `purchase-orders` | xaridnoma hayot sikli |
| 11 | `supplier-payments` | to'lov, "qizil" faktura QQS krediti |
| 12 | `supplier-returns` | yetkazib beruvchiga qaytarish |
| 13 | `transfers` | e-TTN bilan jo'natish/qabul/farq (offline) |
| 14 | `stock-counts` | sanash varag'i, skaner, review, post |
| 15 | `write-offs` | hisobdan chiqarish (sabab bilan) |
| 16 | `stock-openings` | boshlang'ich qoldiq |
| 17 | `valuation-settings`, `stock-settings` | FIFO/AVECO, tarozi kod formati, kam qoldiq chegarasi |
| 18 | `recost-jobs` | qayta hisoblash holati |
| 19 | `einvoices` (direction=in) | kiruvchi e-faktura ro'yxati, qabul/rad, E-IMZO imzolash |
| 20 | `ettn-documents` | e-TTN: ichki ko'chirish (chiquvchi) imzolash/yuborish, kiruvchi e-TTN tasdiqlash/rad etish |

---

## 1. Mahsulot katalogi (`products`)

### `GET /products`

**Maqsad**: katalogni ro'yxatlash/qidirish (BO-03, BO-04, BO-05, BO-18 uchun manba).
**Ruxsat**: `stock.view`.
**So'rov**:

| Parametr | Tur | Majburiy | Izoh |
|---|---|---|---|
| `search` | string | yo'q | Kirill/lotin aralash, `pg_trgm` orqali nom/shtrix-kod bo'yicha qidiruv |
| `category_id` | UUID | yo'q | — |
| `archived` | bool | yo'q | standart `false` |
| `is_weighed` | bool | yo'q | — |
| `low_stock` | bool | yo'q | `true` — faqat `qty <= min_stock` bo'lgan tovarlar (ombor join, X-Branch-Id ombori) |
| `page`, `size` | int | yo'q | **page pagination** (ma'lumotnoma, cursor emas), standart `size=50`, max `200` |

**Javob**: `200 {items:[Product], total, page, size}`. `Product`: `id, name, name_ru, category_id, unit_code, mxik_code, package_code, vat_rate, vat_exemption_code, is_marked, is_weighed, min_stock, archived_at, version, barcodes:[{id,barcode,kind,units_per_barcode}]` — `name_ru` ixtiyoriy.
**Xatolar**: — (bo'sh ro'yxat — oddiy `200`).
**Idempotentlik**: shart emas (o'qish).
**Offline**: POS uchun katalog `/sync/pull?scope=catalog` orqali keshlanadi (`16-offline-sync.md` §1); bu endpoint faqat online back-office uchun.
**Bog'liq**: BO-03, BO-04, BO-05, BO-18.

### `POST /products`

**Maqsad**: yangi tovar yaratish.
**Ruxsat**: `catalog.manage`.
**So'rov**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `name` | string | ha | 1–255 belgi (o'zbek, asosiy) |
| `name_ru` | string\|null | yo'q | 0–255 belgi — ixtiyoriy (qaror #29), chek/UI qatorida `"{name} / {name_ru}"` |
| `category_id` | UUID | yo'q | mavjud, arxivlanmagan kategoriya |
| `unit_code` | string | ha | `units` jadvalida mavjud |
| `mxik_code` | string\|null | yo'q | `NULL` ruxsat — 17 raqam agar berilsa; chekka chiqarishdan oldin majburiy (bu yerda bloklanmaydi). MXIK'siz tovar sotuv voqeasida `VALIDATION_ERROR` (`params.reason="mxik_missing"`) |
| `package_code` | string | yo'q | — |
| `vat_rate` | string | ha | `"12.00"` / `"0.00"` |
| `vat_exemption_code` | string\|null | yo'q | imtiyoz kodi — `vat_rate` yoki shu ikkisidan kamida bittasi to'ldirilgan bo'lishi shart |
| `is_marked` | bool | ha | standart `false` |
| `is_weighed` | bool | ha | standart `false` |
| `min_stock` | decimal(3dp) | yo'q | ≥ 0 |
| `barcode` | string | yo'q | birinchi shtrix-kod, kind=`ean` |

**Javob**: `201` to'liq `Product` (yuqoridagi sxema, `version=1`).
**Xatolar**: `422 VALIDATION_ERROR`, `409 BARCODE_DUPLICATE` (tenant ichida shtrix-kod takror), `422 MXIK_CODE_INVALID` (format 17 raqamdan farq qiladi).
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q.
**Bog'liq**: US-M09-05 (shtrix-kod), BO-04 (AI-03 orqali to'ldirilgan qatorlardan ham shu endpoint chaqiriladi, lekin odatda `goods-receipts` oqimi ichida — bu yerda mustaqil qo'lda yaratish).

### `GET /products/{id}` · `PATCH /products/{id}`

**Ruxsat**: `stock.view` (GET), `catalog.manage` (PATCH).
**So'rov**: `PATCH` tanasi — yuqoridagi maydonlarning istalgan to'plami + **majburiy** `version`.
**Xatolar**: `404 NOT_FOUND` (`params.resource="product"`), `409 VERSION_CONFLICT`, `409 RESOURCE_ARCHIVED` (arxivlangan tovarni tahrirlashga urinish — avval `unarchive`).

### `POST /products/{id}/archive` · `POST /products/{id}/unarchive`

**Ruxsat**: `catalog.manage`.
**So'rov**: `{reason?: string}`. Soft-delete — `archived_at`; `unarchive` → `archived_at=null`. Arxivlangan tovar POS katalogida ko'rinmaydi, lekin eski hujjatlarda (`sale_lines.product_id`) saqlanadi (`11-malumotlar-modeli.md` §1).
**Offline**: tovar offline sotuv paytida serverda arxivlangan bo'lsa — hujjat baribir qabul qilinadi, bayroq qo'yiladi (`16-offline-sync.md` §5) — bu `/sync/push` tomonida, bu yerda emas.

### Shtrix-kodlar — `GET/POST /products/{id}/barcodes` · `DELETE /products/{id}/barcodes/{barcode_id}`

**Ruxsat**: `catalog.manage`.
**So'rov**: `POST` tana: `{barcode: string, kind: "ean"|"internal"|"weighed_prefix", units_per_barcode?: decimal(3dp)}`. `units_per_barcode` — qadoq/quti koeffitsienti (`11-malumotlar-modeli.md` §4 birlik konversiyasi qoidasi); standart `1.000`.
**Xatolar**: `409 BARCODE_DUPLICATE` (tenant ichida noyob bo'lishi shart).

### `POST /products/{id}/barcodes/internal-generate`

**Maqsad**: shtrix-kodsiz tovarga ichki kod berish (US-M09-05).
**Ruxsat**: `catalog.manage`.
**So'rov**: `{}` (parametrsiz). Server `internal_barcode_seq`dan keyingi qiymatni oladi, EAN-13 nazorat raqami bilan to'liq kod yaratadi, `kind="internal"` bilan yozadi.
**Javob**: `201 {barcode, kind:"internal", units_per_barcode:"1.000"}`.
**Idempotentlik**: `Idempotency-Key` majburiy (ikki marta bosilsa ikki kod berilmasligi uchun).
**Bog'liq**: US-M09-05, BO-18.

### MXIK qidiruv/tekshirish

#### `GET /mxik-codes?query=<matn>&limit=20`

**Ruxsat**: `catalog.manage`. Sinxron, keshlangan (`tasnif.soliq.uz`, `21-integratsiyalar.md` §7).
**Javob**: `{items:[{code, name, vat_hint}]}` — `next_cursor` yo'q (oddiy massiv, max 20).

#### `GET /mxik-codes/{code}`

Kodni tasdiqlash + QQS toifasi.
**Xatolar**: `404 NOT_FOUND` (`params.resource="mxik_code"`) agar kod kesh/tashqi tizimda topilmasa; tashqi tizim ishlamasa — `200` lekin `{items:[], source:"stale_cache"}` (3-urinishdan keyin oxirgi ma'lum kesh, `21-integratsiyalar.md` §7 qayta urinish siyosati). Qattiq xato yo'q — foydalanuvchi kodni qo'lda kiritadi.
**Bog'liq**: BO-04, M09.

---

## 2. Kategoriyalar (`product-categories`)

### `GET /product-categories`

**Ruxsat**: `stock.view`. **So'rov**: `?parent_id=&page=&size=` — daraxt, `parent_id=null` — ildiz; **page pagination**.

### `POST /product-categories`

**Ruxsat**: `catalog.manage`. **So'rov**: `{name, parent_id?}`.

### `PATCH /product-categories/{id}`

**So'rov**: `{name?, parent_id?, version}`.

### `POST /product-categories/{id}/archive`

**So'rov**: `{}`. Arxivlashdan oldin server tekshiradi: agar arxivlanmagan tovar shu kategoriyaga bog'langan bo'lsa → `409 CATEGORY_HAS_PRODUCTS` (avval tovarlarni boshqa kategoriyaga ko'chirish/arxivlash kerak).
**Xatolar**: `404 NOT_FOUND` (`params.resource="product_category"`), `409 VERSION_CONFLICT`, `409 CATEGORY_HAS_PRODUCTS`.
**Offline**: kategoriyalar `/sync/pull?scope=catalog` bilan birga keshlanadi.

---

## 3. Birliklar (`units`)

### `GET /units`

**Ruxsat**: `stock.view`. Global jadval (`tenant_id` yo'q, RLS istisnosi), faqat o'qish; tenant o'zi yangi birlik qo'sha olmaydi (MVP cheklovi).
**Javob**: `{items:[{code, is_fractional}]}` (sahifalashsiz, ro'yxat kichik).

---

## 4. Narxlar (`prices`, `price-changes`)

### `GET /products/{id}/prices`

**Maqsad**: narx tarixi (US-M09-01).
**Ruxsat**: `stock.view`.
**So'rov**: `branch_id?` (bo'sh — barcha filial uchun umumiy narxlar).
**Javob**: `{items:[{price, valid_from, valid_to, set_by, price_change_doc_id, branch_id}], next_cursor}` — `valid_to` hisoblanadigan maydon (keyingi yozuvning `valid_from`'i, oxirgisida `null`).

### `POST /price-changes`

**Maqsad**: narx o'zgarishi hujjatini yaratish (draft).
**Ruxsat**: `prices.edit`.
**So'rov**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `doc_date` | date | ha | — |
| `lines[].product_id` | UUID | ha | — |
| `lines[].new_price` | decimal(4dp) | ha | > 0 (4 xonali satr) |
| `lines[].valid_from` | timestamptz\|null | yo'q | `null` = `post` paytidan boshlab kuchga kiradi |
| `lines[].branch_id` | UUID\|null | yo'q | `null` = barcha filial |
| `comment` | string | yo'q | — |

**Javob**: `201 {id, status:"draft", number:null, lines:[...]}` (`version` yo'q — bu hujjatda optimistik qulflash ishlatilmaydi).
**Xatolar**: `422 VALIDATION_ERROR` (manfiy/nol narx).

### `POST /price-changes/{id}/post`

**Maqsad**: hujjatni o'tkazish. Har qator uchun server joriy narx bilan farqni (%) hisoblaydi va `prices.approve` limitiga (`role_permissions.limit_value`) solishtiradi:
- Limit ichida → darhol `product_prices` yangilanadi, hujjat `status="posted"`, `label_print_queue`ga `reason="price_changed"` qatorlari qo'shiladi (US-M09-04).
- Limitdan katta → `202 {status:"draft", approval_request_id}` (`APPROVAL_REQUIRED`) — `approval_requests` yozuvi yaratiladi (`kind="price_change"`, `linked_doc_type="price_changes"`), hujjat **`draft`da qoladi** (bu hujjat turi boshqa `pending_approval`ga o'tmaydigan yagona istisno); `product_prices` hali o'zgarmaydi.

**Ruxsat**: `prices.edit`.
**Xatolar**: `404 {code:"NOT_FOUND", params:{resource:"price_changes"}}`, `409 {code:"DOC_NOT_DRAFT"}`.
**Idempotentlik**: `Idempotency-Key` majburiy.
**Bog'liq**: US-M09-01, US-M09-02, BO-05.

**Tasdiqlash — faqat `approval-requests` orqali** (`18-api-kassa.md` §9, `kind=price_change`): `POST /approval-requests/{id}/approve` (`{pin}`) — `product_prices` yangilanadi, hujjat server tomonidan `post` qilinadi, yorliq navbatiga qo'shiladi; `POST /approval-requests/{id}/reject` (`{reason}`) — hujjat `draft`da qoladi, narx o'zgarmaydi. `POST /price-changes/{id}/approve`/`reject` bu faylda **yo'q**. Tasdiqlovchi — `prices.approve`, **faqat Egasi** (`15-xavfsizlik-va-audit.md` §2.2).

**Eslatma**: `price-changes` umumiy `draft→post→cancel` naqshidan **farqlanadi** — `post` natijasi shartli (`posted` yoki yuqoridagi `202 APPROVAL_REQUIRED`), va `posted` holatdan keyin `cancel` yo'q (narxni orqaga qaytarish — yangi `price-changes` hujjati bilan, teskari emas).

---

## 5. Yorliqlar (`label-print-queue`, `label-print-jobs`, `label-templates`)

### `GET /label-print-queue`

**Maqsad**: narxi o'zgargan/yangi, hali chop etilmagan tovarlar ro'yxati (BO-18).
**Ruxsat**: `labels.print`.
**So'rov**: `?reason=&cursor=&limit=` (`reason` ∈ `price_changed`/`new`).
**Javob**: `{items:[{product_id, product_name, reason, current_price, old_price?, barcode, created_at}], next_cursor}`.

### `GET /label-templates`

**Ruxsat**: `labels.print`.
**So'rov**: page pagination.
**Javob**: `{items:[{id, name, width_mm, height_mm, fields:[...]}], total, page, size}` — `platform.label_templates` global jadvalidan (tenant'siz, RLS istisnosi), tenant o'zgartira olmaydi (MVP, global ro'yxat). Standart shablonlar (US-M09-04): **58×40** (asosiy narx yorlig'i), 58×30, 43×25, 40×30, 30×20 mm va **A4** (3×8 yoki 4×10 to'r, oddiy printer uchun); 203 dpi uchun shtrix moduli butun nuqtaga (1 nuqta ≈ 0,125 mm) yaxlitlanadi. Chop etish — tizim drayveri orqali (brauzer HTML/SVG yoki PDF); xom TSPL/ZPL buyruqlari MVP'da yo'q.

### `POST /label-print-jobs`

**Maqsad**: tanlangan tovarlar uchun yorliq chop etish ishini yaratish va serverda PDF generatsiya qilish. Asosiy chop etish — brauzerda (`bwip-js` + tizim drayveri); server PDF (`python-barcode`+`zxing-cpp`, `23-backend-arxitekturasi.md` §5) **faqat** ommaviy chop etish (>200 yorliq, `product_ids × copies_per_product`, standart, sozlanadi) yoki iOS/Safari klienti uchun ishlatiladi (qaror #54; Bosqich 2 oxiri). Klient shu shartdan tashqarida server yo'lini chaqirmaydi.
**Ruxsat**: `labels.print`.
**So'rov**:

| Maydon | Tur | Majburiy | Izoh |
|---|---|---|---|
| `template_id` | UUID | ha | — |
| `product_ids` | UUID[] | ha | 1–500 |
| `copies_per_product` | int | yo'q | standart `1` |

**Javob**: `202 {job_id, status:"queued"}` → poll `GET /label-print-jobs/{id}` → `{status:"done", file_url}` (PDF, `attachments`) — `job_id` = `outbox_jobs.id` (`kind="label_pdf"`; alohida job jadvali shart emas). Muvaffaqiyatli chop etilgandan keyin klient `POST /label-print-queue/mark-printed {product_ids}` chaqiradi — navbatdan olib tashlaydi (`printed_at` o'rnatiladi).
**Xatolar**: `404 NOT_FOUND` (`params.resource="label_template"`).
**Idempotentlik**: `Idempotency-Key` majburiy (job yaratishda).
**Offline**: "Offline — lokal printer bilan ishlaydi" (BO-18 ekran holati) — bu brauzerdagi `bwip-js` yo'li, server endpoint'i shart emas agar printer to'g'ridan-to'g'ri lokal ulangan bo'lsa; server yo'li faqat online. LAN (raw TCP 9100) yorliq printerlari brauzerdan to'g'ridan-to'g'ri ishlamaydi — ular **Do'kon agenti** orqali ulanadi (qaror #60).
**Bog'liq**: US-M09-04, BO-18.

---

## 6. Import ishlari (`import-jobs`)

Uchta `kind`: `products` (US-M04-04), `opening_stock` (US-M04-04), `opening_debts` (US-M08-07) — format `11-malumotlar-modeli.md` §10 va `03-modullar-talablari.md` M04 bo'yicha.

> **BO-21 "Foto (AI-03)" muqobil yo'li** — ommaviy Excel import o'rniga: `POST /ai/ocr/jobs` (`20-api-moliya-admin.md` #73, `doc_type_hint="catalog"`) → `POST /ai/ocr/jobs/{job_id}/confirm` `products` va (miqdor ko'rsatilgan bo'lsa) `stock-openings` qoralamalarini yaratadi.

### `GET /import-jobs/templates/{kind}`

**Ruxsat**: `stock.opening.manage` (`opening_stock`/`opening_debts`) yoki `catalog.manage` (`products`).
**Javob**: CSV fayl (`Content-Disposition: attachment`), UTF-8, `;` ajratgich — ustunlar `kind`ga qarab (`11-malumotlar-modeli.md` §10 jadvali): `products.csv` → `name;barcode;unit_code;mxik_code;vat_rate;price;category;is_marked`; `opening_stock.csv` → `barcode;qty;unit_cost;expiry_date`; `opening_debts.csv` → `name;phone;amount;direction;date`.

### `POST /import-jobs`

**Maqsad**: fayl yuklash, job yaratish (`status="uploaded"`).
**Ruxsat**: `catalog.manage` (`kind=products`) / `stock.opening.manage` (`kind=opening_stock`, `kind=opening_debts`).
**So'rov**: `multipart/form-data`: `kind` (enum), `file` (CSV/XLSX, max 10 MB, max 20 000 qator — standart, sozlanadi, qaror #54).
**Javob**: `201 {id, kind, status:"uploaded", total_rows:null}`.
**Xatolar**: `422 IMPORT_FILE_INVALID` (format/kodlash xato), `413 FILE_TOO_LARGE`.
**Idempotentlik**: `Idempotency-Key` majburiy.

### `POST /import-jobs/{id}/validate`

**Maqsad**: asinxron ish — har qatorni sxema + biznes qoida bo'yicha tekshiradi (masalan `products` — shtrix-kod takrori, MXIK format; `opening_stock` — shtrix-kod katalogda topildimi; `opening_debts` — `direction` qiymati `receivable`/`payable`), natijani `import_jobs.errors` JSONB'ga (qator, maydon, xato kodi) yozadi, `status="validated"` (yoki hamma qator xato bo'lsa `status="failed"`).
**Javob**: `202 {job_id, status:"validating"}` → poll `GET /import-jobs/{id}` → `{status:"validated", total_rows, ok_rows, error_rows}`.

### `GET /import-jobs/{id}/errors`

**So'rov**: `?cursor=&limit=`. **Javob**: `{items:[{row, field, code, message}], next_cursor}`.

### `POST /import-jobs/{id}/commit`

**Maqsad**: faqat **xatosiz** qatorlarni (yoki foydalanuvchi "xatolarsiz davom et" deb tasdiqlagan qismni) bitta tranzaksiyada hujjatlarga aylantirish: `products` → yangi `products`+`product_barcodes`; `opening_stock` → bitta `stock-openings` hujjati (§7 bilan bir xil posting, `13-provodka-qoidalari.md` §2.21); `opening_debts` → bitta `debt-openings` hujjati (`18-api-kassa.md` §12.4 — faqat `import_jobs.kind=opening_debts` shu yerda hosil bo'ladi).
**Ruxsat**: `validate`dagi bilan bir xil.
**So'rov**: `{skip_error_rows: bool}` (standart `true`).
**Javob**: `202 {job_id, status:"committing"}` → poll `GET /import-jobs/{id}` → `{status:"committed", result:{created_doc_ids:[...]}}`.
**Xatolar**: `409 IMPORT_JOB_NOT_VALIDATED` (avval `validate` chaqirilmagan), `409 IMPORT_JOB_ALREADY_COMMITTED`.
**Idempotentlik**: `commit` tabiatan bir martalik — qayta chaqirilsa `409 IMPORT_JOB_ALREADY_COMMITTED` (ikkinchi marta hujjat yaratilmaydi); shuningdek `Idempotency-Key` ham talab qilinadi (ikki marta tasodifiy bosilganda).
**Offline**: yo'q (fayl yuklash, online).
**Bog'liq**: US-M04-04, US-M08-07, BO-21 (ro'yxatdan o'tish oqimida).

---

## 7. Ombor qoldig'i (`stock-balances`, `stock-lots`, `stock-moves`)

### `GET /stock-balances`

**Maqsad**: BO-03 asosiy ro'yxati.
**Ruxsat**: `stock.view`.
**So'rov**: `warehouse_id?` (berilmasa — `X-Branch-Id`ning ombori; **barcha filiallar bo'yicha konsolidatsiya kerak bo'lsa** — bu endpoint emas, `20-api-moliya-admin.md` #20 `GET /reports/stock` ishlatiladi, US-M04-03), `product_id?`, `low_stock?` (bool), `search?`, `cursor`, `limit`.
**Javob**: `{items:[{product_id, product_name, warehouse_id, qty, value, min_stock, is_low, updated_at}], next_cursor}`. Manfiy `qty` — `⚠` bayrog'i (`is_negative:true`) bilan qaytariladi (overselling, `16-offline-sync.md` §5).

### `GET /stock-lots`

**Maqsad**: partiya/yaroqlilik muddati ko'rinishi (US-M04-06, BO-03).
**Ruxsat**: `stock.view`.
**So'rov**: `warehouse_id?`, `product_id?`, `expiring_within_days?` (int — masalan `7`, US-M04-06 standart), `cursor`, `limit`.
**Javob**: `{items:[{id, product_id, warehouse_id, received_at, qty_in, qty_left, unit_cost, expiry_date, receipt_line_id}], next_cursor}`.

### `GET /stock-moves`

**Maqsad**: harakat tarixi (audit/tekshiruv uchun).
**Ruxsat**: `stock.view`.
**So'rov**: `warehouse_id?`, `product_id?`, `doc_type?`, `from?`, `to?` (ISO sana), `cursor`, `limit`.
**Javob**: `{items:[{id, warehouse_id, product_id, lot_id, qty, cost_amount, doc_type, doc_id, line_id, moved_at}], next_cursor}`. `qty`/`cost_amount` — ishora bilan (`±`).

**Xatolar** (uchtasi uchun): — (faqat o'qish, bo'sh ro'yxat qaytadi).
**Idempotentlik**: shart emas.
**Offline**: faqat ko'rish, IndexedDB'dagi oxirgi nusxa (BO-03 ekran holati).
**Bog'liq**: US-M04-01…03, US-M04-06, BO-03.

---

## 8. Omborga kirim (`goods-receipts`) va AI-03 OCR

> **AI-03 (OCR) — bu yerda emas.** OCR to'liq oqimi — `20-api-moliya-admin.md` #73–75: fayl `POST /attachments`ga yuklanadi (≤10 MB, `17-api-umumiy.md` §12) → `POST /ai/ocr/jobs` (`doc_type_hint=purchase`) → poll `GET /ai/ocr/jobs/{job_id}` → `POST /ai/ocr/jobs/{job_id}/confirm` shu yerdagi `POST /goods-receipts` shakli bilan **to'g'ridan-to'g'ri** `goods-receipts` qoralamasini yaratadi (ruxsat `ai.ocr.use` + `purchases.receive`). Sariq belgi chegaralari (summa <95%, sana <90%, miqdor/nom <80%) saqlanadi. AI-03 rasmlari tenant chegaradan tashqari uzatishga rozilik bermaguncha (`ai.cross_border_enabled=false`) yuborilmaydi — `403 AI_CONSENT_REQUIRED` (qaror #61).

### `POST /goods-receipts`

**Maqsad**: kirim hujjatini draft sifatida yaratish — qo'lda, PO asosida yoki OCR draftdan.
**Ruxsat**: `purchases.receive`.
**So'rov**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `supplier_id` | UUID | ha | `counterparties`da mavjud, `is_supplier=true` (§9) |
| `warehouse_id` | UUID | ha | `X-Branch-Id`ga tegishli |
| `po_id` | UUID | yo'q | mavjud bo'lsa `purchase_orders.status IN (sent, partially_received)` |
| `doc_date` | date | ha | — |
| `lines[].product_id` | UUID | ha | — |
| `lines[].qty` | decimal(3dp) | ha | > 0 |
| `lines[].cost` | decimal(4dp) | ha | ≥ 0 (QQS'siz birlik narx) |
| `lines[].vat_rate` | string | ha | `"12.00"`/`"0.00"` |
| `lines[].vat_exemption_code` | string\|null | yo'q | imtiyoz kodi, `vat_rate="0.00"` bo'lsa ishlatiladi |
| `lines[].expiry_date` | date | yo'q | — |
| `paid_immediately` | bool | yo'q | standart `false` — `true` bo'lsa `13-provodka-qoidalari.md` §2.6 yo'li (naqd/darhol to'lov), aks holda §2.8 (kreditorlik) |
| `kind` | enum | yo'q | `purchase` (standart) / `gratuitous` (bepul olingan tovar — provodka `13-provodka-qoidalari.md` bo'yicha) |
| `ettn_ref` | string | yo'q | kiruvchi e-TTN raqami (operator hujjati); birlashtirilgan EHF+TTN bo'lsa `from-einvoice` yo'lida avtomatik to'ldiriladi, aks holda qo'lda (masalan e-TTN rouming orqali kechikkan) |
| `poa_number` | string | yo'q | do'kon o'z xodimiga (qabul qiluvchi Omborchiga) e-faktura operatori orqali bergan e-ishonchnoma raqami (qaror #63) |

**Javob**: `201 {id, status:"draft", number:null, lines}` (`version` yo'q — hujjat `draft`ligi `PATCH` bilan butunicha almashtiriladi).
**Xatolar**: `422 VALIDATION_ERROR`, `404 {code:"NOT_FOUND", params:{resource:"counterparties"}}`, `409 {code:"PURCHASE_ORDER_CLOSED"}` (agar `po_id` berilgan va PO yopiq/bekor bo'lsa).

**E-ishonchnoma** (qaror #63): do'kon o'z xodimiga e-ishonchnomani e-faktura operatori orqali (Faktura.uz `PowerOfAttorney`, `EInvoicePort.send_power_of_attorney`, `21-integratsiyalar.md` §6; alohida Vakolat.uz integratsiyasi yo'q) **e-fakturadan oldin** beradi; kirimda uning raqami `poa_number`da qayd etiladi; yetkazib beruvchi uni tekshirib, e-fakturani shu ishonchnoma asosida shakllantiradi, e-fakturani ishonchli shaxs E-IMZO bilan imzolaydi. Ishonchnomasiz kirim bloklanmaydi — e-fakturani Buxgalter (direktor ERI) imzolaydi.

### `POST /goods-receipts/from-einvoice/{einvoice_id}`

**Maqsad**: qabul qilingan kiruvchi e-faktura (§19) asosida draft kirim hujjatini oldindan to'ldirish (qatorlar, summalar, QQS, markirovka kodlari — e-faktura `payload`dan); `source="einvoice"`, `einvoice_id` saqlanadi — "qizil" faktura QQS kechiktirish yo'li shu bog'lanish orqali aniqlanadi. E-faktura birlashtirilgan EHF+TTN shaklida bo'lsa, `ettn_ref` shu fakturaga bog'langan kiruvchi `ettn_documents` yozuvidan (`direction="in"`, operator poll'ida yaratiladi, §20) to'ldiriladi (alohida e-TTN emas, EHF'ning bir qismi).
**Ruxsat**: `purchases.receive`.
**So'rov**: `{warehouse_id}` (qolgan maydonlar e-fakturadan olinadi, foydalanuvchi keyin `PATCH` bilan tahrirlaydi — masalan `expiry_date` qo'shadi).
**Xatolar**: `404 NOT_FOUND` (`params.resource="einvoice"`), `409 {code:"EINVOICE_NOT_ACCEPTED"}` (faqat `status=accepted` fakturadan kirim yaratiladi).

### `GET /goods-receipts` · `GET /goods-receipts/{id}` · `PATCH /goods-receipts/{id}`

**Ruxsat**: `stock.view` (GET), `purchases.receive` (PATCH, faqat `draft` holatda).
**So'rov** (GET ro'yxat): `supplier_id?`, `status?`, `from?`, `to?`, `cursor`, `limit`.
**Javob** (qo'shimcha hosila maydonlar): `ettn_status` (`none`/`received`/`accepted`/`rejected`, §20), `marking_acceptance: {status: "not_required"|"pending"|"accepted"|"overdue", due_at, deadline_kind: "3_business_days"|"72_hours"}|null` — pastdagi "Markirovkalangan tovar qabuli" bandiga qarang.

### `POST /goods-receipts/{id}/post`

**Maqsad**: hujjatni o'tkazish — yangi `stock_lots` yaratiladi, `stock_balances`/`stock_moves` +, yetkazib beruvchiga qarz + (nasiya bo'lsa), kiritiladigan QQS (`13-provodka-qoidalari.md` 2.6–2.8; "qizil" faktura bo'lsa QQS yozuvi to'lovgacha kechiktiriladi, §2.8).
**Ruxsat**: `purchases.post` — Buxgalter/Egasi; Egasi BO-11'da Omborchi roliga `purchases.post`ni qo'shishi mumkin (≤3 FTE do'konlar, qaror #49).
**So'rov**: `{}`.
**Javob**: `200 {id, status:"posted", number:"M-01-2026-000154", posted_at, lots_created:[{lot_id, product_id, qty_in, unit_cost}]}` (`M` = `goods_receipts`, `12-db-sxema.md` §2.9).
**Xatolar**: `404 NOT_FOUND` (`params.resource="goods_receipt"`), `409 DOC_NOT_DRAFT` (allaqachon `posted`), `409 PERIOD_CLOSED` (agar `doc_date` yopilgan davrda bo'lsa).
**Idempotentlik**: `Idempotency-Key` majburiy.

### `POST /goods-receipts/{id}/cancel`

**Ruxsat**: `purchases.post`.
**So'rov**: `{reason: string}` (majburiy). Storno: `stock_moves`/`stock_lots.qty_left` teskari, kreditorlik qarzi teskari, QQS teskari (`13-provodka-qoidalari.md` §5.2). Agar partiyadan allaqachon chiqim bo'lgan bo'lsa (masalan sotilgan) — `409 {code:"LOT_ALREADY_CONSUMED"}` (bekor qilish taqiqlanadi, avval sotuvni ko'rib chiqish kerak).
**Offline**: **yo'q** — markirovkalangan tovar qabulida egalik o'zgaradi, shuning uchun kirim (offline o'z filiallari orasidagi `transfers`dan farqli) faqat online ruxsat etiladi (Asosiy xulosa 7, qaror #23 — tavsiya #5). Mobil skaner (POS-08) ham **shu REST endpoint'lardan online rejimda** foydalanadi — alohida offline outbox voqeasi yo'q. Omborchi `draft` yaratadi (`purchases.receive`), `post`ni Buxgalter/Egasi bajaradi (`purchases.post`) — qoldiq shu paytda oshadi; Egasi `purchases.post`ni Omborchiga bergan bo'lsa, Omborchi o'zi o'tkazadi (qaror #49).

**Kiruvchi e-TTN** (qaror #63): e-TTN'ni **yuk jo'natuvchi (yetkazib beruvchi)** chiqaradi — odatda e-faktura bilan birlashtirilgan; do'kon (yuk oluvchi) tashish yakunida uni **elektron tasdiqlaydi yoki rad etadi** — birlashtirilgan shaklda §19 `accept`/`reject` bilan birga, alohida e-TTN bo'lsa §20 `accept`/`reject`. E-TTN'siz kirim bloklanmaydi, lekin `ettn_status="none"` BO-04/BO-15'da "E-TTN yo'q" belgisi bilan ko'rsatiladi.

**Markirovkalangan tovar qabuli** (`is_marked=true` qatorlar): markirovka kodlari (e-faktura `payload`idan yoki POS-08 skaneridan) `marking_codes`ga yoziladi va `post`da Asl belgisi'da **CRPT API orqali** qabul qilinadi (`MarkingPort`, `outbox_jobs(kind="marking_accept")`; CRPT API ishlatiladigan joylardan biri — chakana sotuvdan farqli, qaror #62). Qabul muddati — tovar guruhi bo'yicha sozlanadi (`marking_product_groups.acceptance_deadline`): umumiy standart **3 ish kuni** (VM 833 66–67-band), o'simlik yog'i, suv/ichimlik va dori vositalari guruhlarida — **72 soat**; hisoblagich jo'natish (e-faktura/e-TTN) sanasidan boshlanadi. Tizim muddatni kuzatadi (`marking_acceptance.due_at`) va BO-04/BO-14'da ogohlantiradi, `post`ni bloklamaydi. Real CRPT adapteri — Bosqich 5, unggacha stub (26 #40 (OQ-025)).
**Bog'liq**: US-M04-01, US-M07-01…03, BP-01, BO-04, POS-08.

---

## 9. Yetkazib beruvchilar (`counterparties?is_supplier=true`)

> **`/suppliers` sifatida alohida resurs yo'q** — mijoz ham, yetkazib beruvchi ham bitta `counterparties` jadvali/resursi, `is_supplier`/`is_customer` bayroqlari bilan ajratiladi (`11-malumotlar-modeli.md` §5). Bu bo'lim faqat xarid oqimida kerak bo'lgan **yetkazib beruvchiga xos** ko'rinish/endpoint'larni tasvirlaydi; umumiy CRUD (`name`, `phone`, mijoz maydonlari — `credit_limit` va h.k.) `18-api-kassa.md`da (kontragent — qarz/mijoz modulining bir qismi).

### `GET /counterparties?is_supplier=true&search=&archived=&cursor=&limit=`

**Ruxsat**: `stock.view`.

### `POST /counterparties` (`is_supplier=true`)

**Ruxsat**: `purchases.create`.
**So'rov**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `name` | string | ha | — |
| `phone` | string | yo'q | — |
| `is_supplier` | bool | ha | `true` |
| `kind` | enum | ha | `person`/`company` |
| `stir` | string | `company` bo'lsa shart | 9 raqam |
| `legal_address`, `bank_account`, `bank_mfo` | string | yo'q | B2B e-faktura chiqarish uchun shart (qabul qilinmasa ham saqlanadi, faqat chiquvchi e-faktura bloklanadi — `18-api-kassa.md` §14a) |
| `vat_payer` | bool | yo'q | AI-03 qamrovini aniqlashda ishlatiladi |

### `GET/PATCH /counterparties/{id}`

`PATCH` `version` talab qiladi.

### `POST /counterparties/{id}/archive`

**Ruxsat**: `purchases.create`.

### `GET /counterparties/{id}/debt-balance`

**Ruxsat**: `stock.view`. **Javob**: `{payable: "1250000.00", receivable: "0.00"}` (`debt_balances`, `direction=payable/receivable`).

### `POST /counterparties/lookup-by-stir`

**Ruxsat**: `purchases.create`. **So'rov**: `{stir: string}` — yaratishdan **oldin** ham ishlaydi (mavjud yozuvga bog'lanmagan). Faktura.uz `CheckCompanyExist/:inn` orqali rekvizitlarni (`legal_address`, bank) avto-to'ldiradi, javobda **taklif** qilinadi — saqlamaydi, foydalanuvchi tasdiqlagandan keyin `POST`/`PATCH`ga yuboradi.

**Xatolar** (bo'lim uchun): `404 {code:"NOT_FOUND", params:{resource:"counterparties"}}`, `409 VERSION_CONFLICT`, `503 {code:"EINVOICE_PROVIDER_UNAVAILABLE"}` (lookup uchun).
**Offline**: yo'q.
**Bog'liq**: M07, BO-04.

---

## 10. Xaridnomalar (`purchase-orders`)

### `POST /purchase-orders`

**Ruxsat**: `purchases.create`.
**So'rov**:

| Maydon | Tur | Majburiy |
|---|---|---|
| `supplier_id` | UUID | ha |
| `warehouse_id` | UUID | ha |
| `doc_date` | date | ha |
| `lines[].product_id` | UUID | ha |
| `lines[].qty` | decimal(3dp) | ha |
| `lines[].price` | decimal(4dp) | yo'q (rejalashtirish, taxminiy) |

**Javob**: `201 {id, status:"draft", ...}`.

### `POST /purchase-orders/{id}/send`

**Ruxsat**: `purchases.create`. `draft→sent`. **So'rov**: `{}`.

### `GET /purchase-orders` · `GET /purchase-orders/{id}`

**Ruxsat**: `stock.view`. Javobda `status` — **saqlangan** ustun (hisoblanadigan emas): `draft`/`sent`/`partially_received`/`closed`/`cancelled`, `GoodsReceiptPostingService` shu kirim `post` tranzaksiyasida yangilaydi; `received_lines:[{product_id, ordered_qty, received_qty}]` hosila (javobda qo'shiladi, saqlanmaydi).

### `PATCH /purchase-orders/{id}`

**Ruxsat**: `purchases.create`. Faqat `draft`/`sent` holatda. `version` talab qiladi.

### `POST /purchase-orders/{id}/cancel`

**Ruxsat**: `purchases.create`. **So'rov**: `{reason}`. `closed`dan keyin tahrir/bekor qilish taqiqlanadi → `409 {code:"PURCHASE_ORDER_CLOSED"}`.
**Xatolar**: `404 NOT_FOUND` (`params.resource="purchase_order"`), `409 PURCHASE_ORDER_CLOSED`, `409 VERSION_CONFLICT`.
**Idempotentlik**: `Idempotency-Key` majburiy (`send`/`cancel`).
**Offline**: yo'q.
**Bog'liq**: US-M07-01, BO-04.

---

## 11. Yetkazib beruvchiga to'lovlar (`supplier-payments`)

### `POST /supplier-payments`

**Maqsad**: kreditorlik qarzini to'lash, "qizil" faktura bo'lsa shu bilan birga kechiktirilgan QQS kreditini ochish (`13-provodka-qoidalari.md` 2.16). **Bir bosqichli hujjat** (`17-api-umumiy.md` §9) — yaratilishi bilanoq o'tkaziladi, alohida `draft`/`post` yo'q; shunga qaramay `cancel` mavjud, chunki xato to'lov storno qilinishi kerak bo'lishi mumkin.
**Ruxsat**: `purchases.pay` (Buxgalter).
**So'rov**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `supplier_id` | UUID | ha | — |
| `amount` | decimal(2dp) | ha | > 0; joriy kreditorlik qoldig'idan oshishi mumkin — `tenants.settings.supplier_overpay_policy` bo'yicha (pastga qarang, qaror #47) |
| `method` | enum | ha | `cash`/`bank` |
| `cash_register_id` | UUID | `method=cash` bo'lsa shart | — |
| `shift_id` | UUID | `method=cash` bo'lsa shart | faol smena |
| `allocations[].target_doc_type` | string | ha | `"goods_receipts"` (jadval nomi) |
| `allocations[].target_doc_id` | UUID | ha | qaysi kirim hujjatini yopadi |
| `allocations[].amount` | decimal(2dp) | ha | — |
| `doc_date` | date | ha | — |

**Qarzdan ortiq to'lov** (qaror #47): `tenants.settings.supplier_overpay_policy` — `'warn'` (standart) yoki `'block'`. `warn`da summa joriy kreditorlik qoldig'idan oshsa to'lov o'tkaziladi, ortiqcha qism yetkazib beruvchiga berilgan avans sifatida `4310`ga yoziladi (`13-provodka-qoidalari.md` 2.16) va javobda `warnings:[{code:"SUPPLIER_OVERPAY_ADVANCE", params:{debt, amount, advance}}]` qaytadi; `block`da — `422 SUPPLIER_OVERPAY_BLOCKED` (`params:{debt, amount}`), hujjat yaratilmaydi.
**Javob**: `201 {id, status:"posted", number, vat_credit_unlocked: [{einvoice_id, vat_amount}], advance_amount, warnings:[]}` — agar `allocations` ichida "qizil" (yoki `risk_flag="unknown"`) fakturaga tegishli kirim bo'lsa, shu qismga mos `4410/6010` QQS yozuvi ham qo'shiladi va `vat_credit_unlocked`da ko'rsatiladi (qisman to'lovda proporsional, `13-provodka-qoidalari.md` 2.16 — taxmin, buxgalter tasdig'i kerak); `advance_amount` — `4310`ga tushgan ortiqcha qism (`"0.00"` bo'lishi mumkin).
**Xatolar**: `422 VALIDATION_ERROR`, `422 SUPPLIER_OVERPAY_BLOCKED` (faqat `supplier_overpay_policy='block'`), `409 PERIOD_CLOSED`.

### `POST /supplier-payments/{id}/cancel`

**Ruxsat**: `purchases.pay`. **So'rov**: `{reason}`. Storno: kreditorlik qarzi orqaga, QQS krediti ochilgan bo'lsa u ham storno.
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q.
**Bog'liq**: US-M07-04, US-M10-03, BP-12, BO-04.

---

## 12. Yetkazib beruvchiga qaytarish (`supplier-returns`)

### `POST /supplier-returns`

**Ruxsat**: `purchases.return`.
**So'rov**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `receipt_id` | UUID | ha | asl kirim hujjati, `status=posted` |
| `doc_date` | date | ha | — |
| `lines[].receipt_line_id` | UUID | ha | asl kirim qatoriga tegishli |
| `lines[].lot_id` | UUID | ha | shu qatordan yaratilgan partiya |
| `lines[].qty` | decimal(3dp) | ha | ≤ `stock_lots.qty_left` |
| `reason` | enum | ha | `expired`/`damaged`/`excess`/`other` — sarlavha darajasida |

`lines[].cost`, `lines[].vat_amount` — javobda **hosila** (server asl kirim qatoridan oladi, kiritilmaydi).
**Javob**: `201 {id, status:"draft", ...}`.

### `POST /supplier-returns/{id}/post`

Ombor qoldig'i − (asl partiyadan), yetkazib beruvchiga qarz − (yoki debitorlik +), kiritiladigan QQS − (`13-provodka-qoidalari.md` 2.20).
**Ruxsat**: `purchases.post`.
**Xatolar**: `422 {code:"INSUFFICIENT_STOCK", params:{lot_id, available}}` (`qty` > `qty_left`), `409 PERIOD_CLOSED`.

### `POST /supplier-returns/{id}/cancel`

**Ruxsat**: `purchases.post`. **So'rov**: `{reason}`.
**Xatolar**: `404 NOT_FOUND` (`params.resource="supplier_return"`), `409 VERSION_CONFLICT`.
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q (ofis/ombor, internet mavjud joy).
**Bog'liq**: US-M07-05, BO-04.
**Markirovka**: markirovkalangan tovarni yetkazib beruvchiga qaytarish — subyektlar o'rtasida egalik o'tishi, shuning uchun Asl belgisi'ga xabarnoma **3 ish kuni** ichida (VM 833 85-band) **CRPT API orqali** (`MarkingPort`, `outbox_jobs(kind="marking_return")`) yuboriladi; chakana chek yo'li (OFD) bu yerda ishlatilmaydi (qaror #62). Aniq CRPT metodi/hujjat turi — tashqi javob kutilmoqda (Ochiq savollar #1); unggacha stub, qaytarish faqat online.

---

## 13. Ko'chirish (`transfers`)

> **E-TTN majburiy** (qaror #63): o'z filiallari/omborlari orasidagi ko'chirish ham e-TTN bilan rasmiylashtiriladi — tashish turi **"Ombordan omborga"** (`ettn_documents.transport_type="warehouse_to_warehouse"`): jo'natuvchi bir vaqtda yuk oluvchi, e-faktura chiqarilmaydi (VM 249 31-ilova, VM 168 tahriri, 13-band). E-TTN e-faktura operatori orqali (MVP'da Faktura.uz, `EInvoicePort`, `21-integratsiyalar.md` §3) shakllantiriladi; e-TTN'siz yuk tashishga topshirish taqiqlanadi (16-band). Istisno — qo'lda yoki jamoat transportida tashish (24-band): `transport_mode="on_foot_or_public"`, e-TTN talab qilinmaydi.
>
> **Markirovka**: ichki ko'chirish Asl belgisi'ga xabar qilinmaydi — VM 833 66–67-band xabarnomalari faqat subyektlar o'rtasida egalik o'tishiga tegishli; ko'chirishda markirovka muddati hisoblagichi yo'q (qabul muddati — §8, §12).

**Holatlar**: `draft` → `posted` (e-TTN yaratildi) → `sent` (jo'natildi, "yo'lda") → `received` / `discrepancy`; `cancelled`.

### `POST /transfers`

**Maqsad**: ko'chirish hujjatini `draft` sifatida yaratish.
**Ruxsat**: `transfer.create`.
**So'rov**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `from_warehouse_id` | UUID | ha | — |
| `to_warehouse_id` | UUID | ha | boshqa filial/ombor, shu tenant |
| `doc_date` | date | ha | — |
| `transport_mode` | enum | yo'q | `vehicle` (standart) / `on_foot_or_public` (e-TTN talab qilinmaydi) |
| `vehicle_plate` | string | `transport_mode=vehicle` bo'lsa `post`da shart | e-TTN rekviziti |
| `driver_name` | string | yo'q | e-TTN rekviziti |
| `lines[].product_id` | UUID | ha | — |
| `lines[].qty` | decimal(3dp) | ha | > 0 |

`client_event_id` bu REST tanasida **yo'q** — faqat offline `transfer.sent`/`transfer.received` sync voqealarida ishlatiladi (pastga qarang).
**Javob**: `201 {id, status:"draft", number:null, transport_mode, ettn:null, lines}`.

### `POST /transfers/{id}/post`

**Maqsad**: `draft→posted` — hujjat o'tkaziladi va `ettn_documents` yozuvi yaratiladi (`transfer_id`, `direction="out"`, `transport_type="warehouse_to_warehouse"`, `status="pending_signature"`; yozuvchi — shu `post`, `TransferPostingService`). Keyin e-TTN §20 bo'yicha E-IMZO bilan imzolanadi va operatorga yuboriladi (`outbox_jobs(kind="ettn_send")`) → operator ro'yxatga olgach `status="registered"`, `operator_doc_id` → `transfers.ettn_ref`. `transport_mode="on_foot_or_public"` bo'lsa e-TTN yaratilmaydi. Qoldiq bu bosqichda o'zgarmaydi.
**Ruxsat**: `transfer.create`.
**So'rov**: `{}`.
**Javob**: `200 {id, status:"posted", number, ettn:{id, status:"pending_signature"}|null}`.
**Xatolar**: `404 NOT_FOUND` (`params.resource="transfer"`), `409 DOC_NOT_DRAFT`, `422 VALIDATION_ERROR` (`params.field="vehicle_plate"`), `409 PERIOD_CLOSED`.

### `POST /transfers/{id}/send`

**Maqsad**: `posted→sent` (yuk tashishga topshirildi): `stock_moves` (jo'natuvchi −, "yo'lda"), partiya ma'lumoti saqlanadi.
**Ruxsat**: `transfer.create`.
**Shart**: `transport_mode="vehicle"` bo'lsa e-TTN `status="registered"` bo'lishi shart, aks holda `409 ETTN_REQUIRED` (`params:{ettn_status}`) — jo'natish rad etiladi.
**Xatolar**: `404 NOT_FOUND`, `409 DOC_INVALID_STATE` (`posted`dan tashqari holat), `409 ETTN_REQUIRED`.

### `POST /transfers/{id}/receive`

**Maqsad**: qabul qilish (US-M06-02).
**Ruxsat**: `transfer.receive`.
**So'rov**:

| Maydon | Tur | Majburiy |
|---|---|---|
| `lines[].transfer_line_id` | UUID | ha |
| `lines[].qty_received` | decimal(3dp) | ha |

Agar barcha qatorlar `qty_received = qty` → `status="received"`; farq bo'lsa → `status="discrepancy"` (`stock_moves` qabul qiluvchida +, farq — kamomad/ortiqcha provodkasi, `13-provodka-qoidalari.md` 2.10). Qabul qiluvchi e-TTN'ni tashish yakunida elektron tasdiqlaydi (§20 `accept`, online) — qabulning o'zi buni kutmaydi.
**Xatolar**: `404 NOT_FOUND` (`params.resource="transfer"`), `409 DOC_INVALID_STATE` (`sent`dan tashqari holat, masalan allaqachon `received`).

### `GET /transfers` · `GET /transfers/{id}`

**Ruxsat**: `stock.view`. **So'rov**: `status?` (`draft`/`posted`/`sent`/`received`/`discrepancy`/`cancelled`), `ettn_status?`. **Javob**: hujjat + `transport_mode`, `ettn_ref`, `ettn:{id, status, operator_doc_id}|null` (BO-03 "Ko'chirishlar" tabi — "E-TTN kutilmoqda" belgisi).

### `POST /transfers/{id}/cancel`

**Ruxsat**: `transfer.create`. Faqat `draft`/`posted`/`sent` (hali qabul qilinmagan) holatda; `received` bo'lgandan keyin bekor qilish taqiqlanadi (`409 DOC_INVALID_STATE`) — tuzatish uchun yangi teskari ko'chirish yaratiladi. E-TTN allaqachon `registered` bo'lsa, javobda `warnings:["ETTN_CANCEL_IN_OPERATOR"]` — e-TTN operator kabinetida bekor qilinadi/tuzatiladi (yuk oluvchi tasdiqlaguncha tuzatuvchi e-TTN, 27-band).

**Idempotentlik**: `Idempotency-Key` majburiy (yoki offline'da `client_event_id`, pastga qarang).
**Offline**: **ruxsat etilgan** — jo'natish ham, qabul ham, faqat **o'z filiallar/omborlar orasida** (`16-offline-sync.md` §7, markirovkalangan tovar uchun ham, egalik o'zgarmagani uchun; qaror #23 — tavsiya #5). Offline yaratilgan `transfers` bu REST endpoint'lar o'rniga `POST /sync/push` outbox voqealari orqali keladi — server tomoni bir xil `TransferPostingService`, idempotentlik `client_event_id` orqali (`Idempotency-Key` o'rniga). **E-TTN offline rasmiylashtirilmaydi**: offline yaratilgan avtotransport ko'chirishi uchun e-TTN internet qaytgach, **tashish boshlanishidan oldin** imzolanadi va ro'yxatdan o'tkaziladi (qaror #63); POS/ombor ilovasi offline'da `transport_mode="vehicle"` ko'chirishni "E-TTN kutilmoqda — tashishni boshlamang" holatida ko'rsatadi. Oldindan online `post` qilingan va e-TTN'i `registered` ko'chirishni jo'natish offline ham mumkin.

**Sync voqea payload'lari** (hujjat sxemasiga moslab qayta ko'rsatiladi):
- **`transfer.sent`** — huquq `transfer.create`; payload: `{id (UUIDv7), temp_number, doc_date, from_warehouse_id, to_warehouse_id, transport_mode, vehicle_plate?, lines: [{line_id, product_id, qty_sent}]}` yoki mavjud hujjat uchun `{transfer_id}`; javob `{id, number, status}`. Server: `transport_mode="on_foot_or_public"` yoki e-TTN allaqachon `registered` bo'lsa — darhol `sent` (`stock_moves`); aks holda hujjat `posted` qiladi, `ettn_documents` yaratadi va `status="posted"` + `warnings:["ETTN_REQUIRED"]` qaytaradi — jo'natish online `send` bilan e-TTN ro'yxatdan o'tgach bajariladi. Markirovkali qator — faqat o'z tenant omborlari orasida, aks holda `VALIDATION_ERROR`.
- **`transfer.received`** — huquq `transfer.receive`; payload: `{transfer_id, lines: [{transfer_line_id, qty_received}]}`; javob `{status:"received"|"discrepancy"}`; javobda `lines[].lot_allocations`, `unit_cost` (bitta qator bir nechta partiyadan FIFO bo'yicha chiqishi mumkin). Boshqa qurilmadagi jo'natma hali kelmagan bo'lsa (`transfer_id` topilmasa) — `422 {code:"DEPENDENCY_NOT_SYNCED", params:{entity:"transfers"}}` (retryable), `DOC_INVALID_STATE` — takror qabul yoki hali `sent` bo'lmagan ko'chirish.

**Bog'liq**: US-M06-01…03, BP-09, BO-03, §20.

---

## 14. Inventarizatsiya (`stock-counts`)

### `POST /stock-counts`

**Maqsad**: sanashni boshlash — `counting` holatida; server `stock_counts.started_at` (server vaqti) ni yozadi va `count_lines` ni shu paytdagi qoldiq bilan oldindan to'ldiradi (`count_lines.snapshot_qty`).
**Ruxsat**: `stock.count.create`.
**So'rov**: `{warehouse_id, doc_date, product_ids?: UUID[], responsible_user_id?: UUID}` (`product_ids` bo'sh — butun ombor; `responsible_user_id` — moddiy javobgar shaxs, kamomad `4730`ga yoziladi, berilmasa `5910`, `13-provodka-qoidalari.md` 2.11).
**Javob**: `201 {id, status:"counting", started_at, lines:[{id, product_id, snapshot_qty, counted:null, counted_at:null}]}`.

### `POST /stock-counts/{id}/lines` (skaner kiritish)

**Maqsad**: skaner/qo'lda sonlarni kiritish (POS-10, bir yoki ko'p qator birdan).
**Ruxsat**: `stock.count.create`.
**So'rov**: `{lines: [{product_id, counted, barcode?}]}` — mavjud qatorni yangilaydi yoki (agar `product_id` ro'yxatda yo'q, masalan kutilmagan tovar topildi) yangi qator qo'shadi (`snapshot_qty` — `started_at` dagi qoldiq, odatda `0`). Har yozuvda `count_lines.counted_at` = qator kiritilgan server vaqti (qaror #53).
**Xatolar**: `409 {code:"BARCODE_NOT_IN_CATALOG"}` (POS-10 ekran xato holati).

### `PATCH /stock-counts/{id}/lines/{line_id}`

Bitta qatorni tuzatish (`counted` qiymatini qayta kiritish; `counted_at` yangilanadi).

### `POST /stock-counts/{id}/submit-for-review`

`counting→review`. **Ruxsat**: `stock.count.create`.

### `POST /stock-counts/{id}/post`

**Maqsad**: farq bo'yicha balansni moslashtirish (US-M05-02/03). Har qator uchun (qaror #53):
`expected = snapshot_qty(started_at) + Σ stock_moves.qty(product, warehouse, started_at < moved_at ≤ count_lines.counted_at)` — ya'ni har qator o'z sanash vaqtigacha bo'lgan harakatlar (sanash davomidagi sotuv/kirim) bilan solishtiriladi; farq `counted − expected`. Provodka (`13-provodka-qoidalari.md` 2.11): kamomad — `4730` (`responsible_user_id` berilgan) yoki `5910`; ortiqcha — `9390`, joriy qiymatda; tovar hisobi — ombor sozlamasi `warehouses.inventory_account` (`2910` ombor / `2920` savdo zali).
**Ruxsat**: `stock.count.post` (Egasi/Menejer).
**Javob**: `200 {status:"posted", shortage_lines:[{product_id, expected, counted, diff, amount}], surplus_lines:[...]}`.
**Xatolar**: `409 DOC_INVALID_STATE` (`post` faqat `review` holatidan), `409 PERIOD_CLOSED`.

### `POST /stock-counts/{id}/cancel`

**Ruxsat**: `stock.count.post`. Faqat `posted` bo'lgandan keyin — storno (balans orqaga). `counting`/`review` holatda shunchaki hujjatni `cancelled` qilish mumkin (registrga ta'siri yo'q).

### `GET /stock-counts` · `GET /stock-counts/{id}`

**Ruxsat**: `stock.view`.

**Idempotentlik**: `Idempotency-Key` (`post`/`submit-for-review`/`cancel`da majburiy; `lines` skaner kiritishda offline bo'lsa `client_event_id` bilan, pastga qarang).
**Offline**: sanash/skaner (POS-10, `type:"stock_count.line_recorded"` outbox voqeasi) **to'liq offline** ishlaydi — internet talab qilinmaydi; `submit-for-review`/`post` esa online back-office/Menejer amali (yakuniy tasdiqlash).

**`stock_count.line_recorded` payload**: huquq `stock.count.create`; `{count_id, product_id, counted (shu qurilmadagi **mutlaq** son, 3dp), barcode?, recorded_at}`; bir qator bir necha marta kelsa — oxirgi `recorded_at` g'olib (idempotent upsert); katalogda yo'q shtrix-kod — `status="accepted"`, `warnings:["BARCODE_NOT_IN_CATALOG"]` ichida (xato emas). **MVP: bitta inventarizatsiya — bitta qurilma** (`stock_counts.device_id`); boshqa qurilmadan voqea kelsa — `409 {code:"DOC_INVALID_STATE", params:{reason:"count_device_mismatch"}}`. Server voqeani yozganda `count_lines.counted_at` ni o'rnatadi; `post`dagi `expected` formulasi yuqorida (qaror #53).

**Bog'liq**: US-M05-01…03, BP-10, POS-10, BO-03.

---

## 15. Hisobdan chiqarish (`write-offs`)

### `POST /write-offs`

**Ruxsat**: `stock.writeoff`.
**So'rov**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `warehouse_id` | UUID | ha | — |
| `doc_date` | date | ha | — |
| `lines[].product_id` | UUID | ha | — |
| `lines[].lot_id` | UUID | **yo'q** | ixtiyoriy — berilmasa server FIFO/AVECO bo'yicha o'zi taqsimlaydi |
| `lines[].qty` | decimal(3dp) | ha | ≤ `stock_lots.qty_left` |
| `lines[].reason` | enum | ha | `expired`/`damaged`/`gift`/`expired_return`/`other` — qator darajasida |
| `lines[].gift_kind` | enum | `reason=gift` bo'lsa shart | `promo_justified` (iqtisodiy asoslangan reklama/aksiya, buyruq bilan — QQS obyekti emas) / `other` (asoslanmagan — QQS bozor qiymatidan, `13-provodka-qoidalari.md` 2.12) |
| `promo_order_ref` | string | `gift_kind=promo_justified` qatori bo'lsa shart | aksiya buyrug'i raqami/sanasi |
| `responsible_user_id` | UUID | yo'q | belgilansa `4730`, aks holda `5910`→`9430` (`13-provodka-qoidalari.md` 2.12) |

`reason="expired_return"` — muddati o'tgan tovarni xaridordan qaytarishda (`restock=false`) server **avtomatik** yaratadigan qoralama; `write_offs.source_return_id` qaytarish hujjatiga bog'lanadi, qo'lda bu sabab tanlanmaydi (qaror #48, `18-api-kassa.md` qaytarish bo'limi).
**Javob**: `201 {id, status:"draft", source_return_id:null, ...}`.

### `POST /write-offs/{id}/post`

**Maqsad**: qoldiq −, xarajat (`13-provodka-qoidalari.md` 2.12; kredit — ombor tovar hisobi `warehouses.inventory_account`, `2910` ombor / `2920` savdo zali). Limitdan katta summa — `stock.writeoff` `limit_value`sidan katta bo'lsa `202 {status:"draft", approval_request_id}` (`kind=write_off_over_limit`), tasdiqlanganda server o'zi `post`ni bajaradi — BO-16 umumiy navbati orqali, alohida PIN-only oqim emas.
**Ruxsat**: `stock.writeoff`.
**Xatolar**: `422 {code:"INSUFFICIENT_STOCK", params:{lot_id, available}}`, `409 PERIOD_CLOSED`, `403 {code:"WRITE_OFF_LIMIT_EXCEEDED"}` (limit cheksiz emas, lekin tasdiq so'ralmagan holatda — odatda yuqoridagi `202` yo'li ishlaydi).

### `POST /write-offs/{id}/cancel`

**Ruxsat**: `stock.writeoff`. **So'rov**: `{reason}`.
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q — hisobdan chiqarish faqat online back-office amali, outbox voqea turi yo'q (qaror #54); Android POS bosqichida qayta ko'riladi.
**Bog'liq**: US-M04-06, BO-03.

---

## 16. Boshlang'ich qoldiq (`stock-openings`)

### `POST /stock-openings`

**Maqsad**: qo'lda (tovar-tovar) boshlang'ich qoldiq kiritish — `import-jobs` (§6) orqali ommaviy yo'lning qo'lda muqobili (US-M04-04, 1-yo'l).
**Ruxsat**: `stock.opening.manage`.
**So'rov**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `warehouse_id` | UUID | ha | — |
| `doc_date` | date | ha | — |
| `lines[].product_id` | UUID | ha | — |
| `lines[].qty` | decimal(3dp) | ha | > 0 |
| `lines[].unit_cost` | decimal(4dp) | ha | ≥ 0 |
| `lines[].expiry_date` | date | yo'q | — |

### `POST /stock-openings/{id}/post`

Yangi partiya yaratadi, qoldiq +, `Dt 2910/2920 (warehouses.inventory_account) / Kt 0000` — texnik yordamchi hisob (`13-provodka-qoidalari.md` 2.21). Chek/faktura **yo'q**.
**Ruxsat**: `stock.opening.manage`. Bir mahsulotga bir nechta marta boshlang'ich kiritish mumkin (masalan qo'shimcha partiya) — bu cheklanmaydi, faqat umumiy validatsiya xatolari qaytadi.

### `POST /stock-openings/{id}/cancel`

**Ruxsat**: `stock.opening.manage`. **So'rov**: `{reason}`.
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q.
**Bog'liq**: US-M04-04, BO-21.

---

## 17. Baholash va ombor sozlamalari (`valuation-settings`, `stock-settings`)

### `GET /valuation-settings`

**Ruxsat**: `stock.view`.
**Javob**: `{current_method: "aveco"|"fifo", effective_from, pending_change: {method, effective_from}|null}` — `valuation_method_history` jadvalidan (enum kichik harf, DB qiymati bilan bir xil).

### `PATCH /valuation-settings`

**Maqsad**: FIFO↔AVECO almashtirish (US-M04-05).
**Ruxsat**: `valuation.settings.manage` (Egasi/Buxgalter).
**So'rov**: `{method: "aveco"|"fifo"}`.
Server joriy sanani tekshiradi: agar joriy hisobot yili ichida bo'lsa — darhol kuchga **kirmaydi**, `pending_change` sifatida saqlanadi, `effective_from = <keyingi yil 1-yanvar>` (`valuation_method_history.valid_from`); agar so'rov yil boshida (masalan yanvar birinchi kunlari, aniq oyna — taxmin) yuborilsa — darhol qo'llanadi.
**Javob**: `200 {current_method, pending_change}`.
**Xatolar**: `409 {code:"VALUATION_METHOD_CHANGE_NOT_ALLOWED"}` — agar allaqachon shu yil uchun `pending_change` mavjud bo'lsa (bir yilda bir marta o'zgartirish so'raladi, qayta so'rov eskisini yangilaydi, xato emas — bu kod faqat ikki marta **turli** metodga ketma-ket so'rov yuborilganda, taxmin).
**Bog'liq**: US-M04-05.

### `GET/PATCH /stock-settings`

**Maqsad**: tarozi shtrix-kod formati/versiyasi (US-M09-06), kam qoldiq ogohlantirish standart kuni (US-M04-02/06 — "7 kun qolganda", sozlanadi).
**Ruxsat**: `stock.view` (GET), `catalog.manage` (PATCH).
**So'rov/Javob maydonlari**: `{weight_barcode_templates: [...], low_stock_check_enabled: bool, expiry_warning_days: int}` — saqlash joyi: `tenants.settings` JSONB kalitlari, alohida jadval emas; `PATCH` tanasidagi `version` = `tenants.version`.

`weight_barcode_templates[]` — tarozi EAN-13 og'irlik kodi `PP CCCCC VVVVV K` shablonlari:

| Maydon | Tur | Validatsiya |
|---|---|---|
| `prefixes` | string[] | har biri `20`–`29` oralig'ida 2 raqam, shablonlar orasida takrorlanmaydi |
| `item_code_len` | int | 4..6, standart `5` (PLU kodi) |
| `value_len` | int | `5` |
| `value_kind` | enum | `WEIGHT` (og'irlik) / `AMOUNT` (summa, so'm) |
| `decimals` | int | 0..3; `WEIGHT` uchun `3` (grammdan kg) |
| `enabled` | bool | — |

Standart ikki shablon: `{prefixes:["22"], value_kind:"WEIGHT", decimals:3}` (og'irlik grammda) va `{prefixes:["21"], value_kind:"AMOUNT", decimals:0}` (summa so'mda, miqdor = summa ÷ joriy narx); prefiks — do'kon sozlamasi. Nazorat raqami mos kelmagan kod rad etiladi (`03-modullar-talablari.md` US-M09-06).
**Offline**: `/sync/pull?scope=settings` orqali POS'ga keshlanadi; shablonlar o'zgarsa majburiy pull (`16-offline-sync.md` §1).

### `GET /stock-settings/plu-export`

**Maqsad**: yorliqli tarozilarga PLU ro'yxatini yuklash uchun CSV eksport — MVP'da yagona yo'l: fayl vendor dasturi (CL-Works, Shtrih Loader, Rongta tool) bilan tarozi(lar)ga import qilinadi. Tarozi(lar)ga to'g'ridan-to'g'ri yuklash (CAS TCP 20304, Shtrih UDP 1111) brauzerdan mumkin emas — MVP'da yo'q (keyin Do'kon agenti orqali, qaror #60).
**Ruxsat**: `catalog.manage`.
**So'rov**: `?category_id=` (ixtiyoriy).
**Javob**: CSV (`Content-Disposition: attachment`, UTF-8, `;` ajratgich) — `is_weighed=true` faol tovarlar: `plu_code;name;price;shelf_life_days`.
**Bog'liq**: US-M09-06, BO-18.

---

## 18. Qayta hisoblash ishlari (`recost-jobs`)

### `GET /recost-jobs`

**Maqsad**: o'tgan sanali hujjat kelganda ishga tushadigan tannarx qayta hisoblash ishlarini kuzatish (`13-provodka-qoidalari.md` §3.3, `23-backend-arxitekturasi.md` §2.4).
**Ruxsat**: `stock.view`.
**So'rov**: `status?` (`queued`/`running`/`done`/`failed`/`rejected_period_closed`), `warehouse_id?`, `product_id?`, `cursor`, `limit`.
**Javob**: `{items:[{id, warehouse_id, product_id, from_date, status, reason_doc_type, reason_doc_id, attempts, last_error, created_at, finished_at}], next_cursor}`.

### `GET /recost-jobs/{id}`

Bitta ish tafsiloti (tuzatilgan `ledger_entries`/`stock_moves` yozuvlari ro'yxati bilan).

### `POST /recost-jobs/{id}/retry`

**Ruxsat**: `accounting.post` (Buxgalter — ledger'ga ta'sir qiluvchi amal). Faqat `status="failed"` bo'lgan ishni qayta navbatga qo'yadi (`rejected_period_closed`ni qayta urinib bo'lmaydi — avval davr ochilishi kerak, bu MVP'da mumkin emas, `13-provodka-qoidalari.md` §5.1).
**Xatolar**: `404 NOT_FOUND` (`params.resource="recost_job"`), `409 DOC_INVALID_STATE` (`failed`dan tashqari holat).
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q.
**Bog'liq**: BO-08 ichidagi **"Qayta hisoblash navbati"** bloki (ustunlar: mahsulot, ombor, holat, navbatga qo'yilgan, tugagan, xato) + BO-14 holat qatori (qaror #56c).

---

## 19. Kiruvchi e-faktura (`einvoices`, `direction=in`)

### `GET /einvoices?direction=in&status=&risk_flag=&cursor=&limit=`

**Maqsad**: BO-15 ro'yxati. Operator — MVP'da Faktura.uz (`EInvoicePort`, qaror #23 tavsiya #4); kiruvchi hujjatlar operatordan poll bilan olinadi (`UpdatedFrom` bo'yicha inkremental, webhook yo'q, `21-integratsiyalar.md` §2).
**Ruxsat**: `purchases.post` (Buxgalter).
**Javob**: `{items:[{id, operator, operator_doc_id, counterparty_id, status, risk_flag, factura_type, related_einvoice_id, signed_at, total_amount, vat_amount}], next_cursor}`. Kiruvchi faktura dastlabki holati — `status="received"`.
- `risk_flag` — `green`/`red`/`unknown` (standart `unknown`). VM 830 xavf darajasi EHF rasmiylashtirilayotganda avtomatik shakllanadi va EDO oqimida hamda my.soliq.uz kabinetida ko'rinadi; operator API'si uni qaytarsa — avtomatik, qaytarmasa (Faktura.uz — tasdiqlanmagan) `unknown` qoladi. `unknown` **qizil kabi** hisoblanadi (QQS krediti to'lovgacha kechiktiriladi, §11); Buxgalter kabinetdan ko'rib `PATCH /einvoices/{id}/risk-flag` (`{risk_flag:"green"|"red", note}`, `purchases.post`, audit) bilan qo'lda belgilaydi.
- `factura_type` — `standard`/`additional`/`corrected`/… (operator turi); `related_einvoice_id` — `additional`/`corrected` faktura qaysi asl fakturaga tegishli (masalan yetkazib beruvchiga qaytarishdagi salbiy qo'shimcha EHF, §12).

### `GET /einvoices/{id}`

To'liq `payload` (tovar qatorlari, MXIK, QQS) bilan.

### `POST /einvoices/{id}/accept`

**Maqsad**: imzolangan kiruvchi fakturani qabul qilish (operatorga tasdiq yuborish, `21-integratsiyalar.md` §2). Birlashtirilgan EHF+TTN bo'lsa, shu tasdiq e-TTN'ni ham tasdiqlaydi (bog'langan `ettn_documents.status="accepted"`).
**Ruxsat**: `purchases.post`.
Avval imzolash shart — `sign-challenge`/`submit-signed` (pastda) o'tmagan hujjat uchun `409 {code:"EINVOICE_NOT_SIGNED"}`.
**Javob**: `202 {status:"queued"}` → `outbox_jobs(kind=einvoice_accept)` → worker orqali operatorga yuboriladi → `status="accepted"` (yashil bo'lsa `vat_moves(kind=input)` darhol; qizil yoki `unknown` bo'lsa to'lovgacha kutiladi, §11).

### `POST /einvoices/{id}/reject`

**Ruxsat**: `purchases.post`. **So'rov**: `{reason: string}` (majburiy). Birlashtirilgan EHF+TTN bo'lsa e-TTN ham rad etiladi (`ettn_documents.status="rejected"`).

### `POST /einvoices/{id}/sign-challenge`

**Maqsad**: E-IMZO imzolash uchun hujjat xeshini (signing payload) qaytarish — brauzer shu payload'ni lokal E-IMZO.exe'ga yuboradi (`21-integratsiyalar.md` §5).
**Ruxsat**: `einvoice.sign`.
**Javob**: `200 {document_hash: "...", challenge_id: "..."}`.

### `POST /einvoices/{id}/submit-signed`

**Maqsad**: brauzerdan qaytgan PKCS#7 imzoni qabul qilish va tasdiqlash.
**Ruxsat**: `einvoice.sign`.
**So'rov**: `{challenge_id, signature_pkcs7: "<base64>"}`.
**Javob**: `200 {status:"signed", signed_at}` — `audit_log(action=sign)` yoziladi.
**Xatolar**: `422 {code:"EIMZO_SIGN_FAILED"}` (imzo tekshiruvi muvaffaqiyatsiz — sertifikat muddati/parol), `409 {code:"EINVOICE_ALREADY_SIGNED"}`, `404 NOT_FOUND` (`params.resource="einvoice"`).
**Idempotentlik**: `Idempotency-Key` majburiy (`accept`/`reject`/`submit-signed`); `document_hash` orqali ham qo'shimcha himoya (bitta hujjat bir necha marta imzolansa, oxirgisi amal qiladi, `21-integratsiyalar.md` §5).
**Offline**: yo'q — imzolash E-IMZO OCSP/TSA tekshiruvi orqali online talab qiladi.
**Bog'liq**: US-M07-03, BP-01, BO-15.

> Chiquvchi e-faktura (B2B nasiya sotuvdan, BP-03) va chek asosida keyinroq chiquvchi e-faktura (BP-13) — `18-api-kassa.md` §14a (sotuv/qarz modulidan tetiklanadi); bu yerda faqat **kiruvchi** (xarid) oqimi.

---

## 20. E-TTN (`ettn-documents`)

> E-TTN faqat e-faktura operatori orqali (MVP'da Faktura.uz, `EInvoicePort`; TTN hujjat turi operator API'sida aniqlanmaguncha — qo'lda ro'yxatga olish yo'li, pastda) shakllantiriladi (qaror #63, `21-integratsiyalar.md` §3). Yozuvchilar: chiquvchi (`direction="out"`, `transport_type="warehouse_to_warehouse"`) — **faqat `transfers` `post`** (§13); kiruvchi (`direction="in"`) — operatordan poll (birlashtirilgan EHF+TTN bo'lsa `einvoice_id` bilan, §19). `ettn_documents.status`: `pending_signature` → `sending` → `registered` → `accepted`/`rejected` (chiquvchi); `received` → `accepted`/`rejected` (kiruvchi); `failed` — operator xatosi (qayta urinish).

### `GET /ettn-documents?direction=&status=&transfer_id=&cursor=&limit=` · `GET /ettn-documents/{id}`

**Ruxsat**: `stock.view`.
**Javob**: `{items:[{id, direction, transport_type, status, operator_doc_id, transfer_id, einvoice_id, counterparty_id, doc_date, created_at}], next_cursor}`; `GET /{id}` — operator `payload` bilan.

### `POST /ettn-documents/{id}/sign-challenge` · `POST /ettn-documents/{id}/submit-signed`

**Maqsad**: chiquvchi e-TTN'ni (§13 `post` yaratgan) E-IMZO bilan imzolash va operatorga yuborish — oqim §19 `sign-challenge`/`submit-signed` bilan bir xil (`{document_hash, challenge_id}` → `{challenge_id, signature_pkcs7}`). `submit-signed` muvaffaqiyatli bo'lsa `status="sending"`, `outbox_jobs(kind="ettn_send")` → operator ro'yxatga olgach `status="registered"`, `operator_doc_id` va `transfers.ettn_ref` to'ldiriladi. `received`/`registered` holatdagi hujjat uchun `sign-challenge` tasdiq/rad payload'ini qaytaradi (`?action=accept|reject`) — imzo `accept`/`reject` tanasida yuboriladi.
**Ruxsat**: `einvoice.sign`.
**Xatolar**: `404 NOT_FOUND` (`params.resource="ettn_document"`), `409 DOC_INVALID_STATE` (`submit-signed` — `pending_signature`/`failed`dan tashqari holat), `422 EIMZO_SIGN_FAILED`, `503 EINVOICE_PROVIDER_UNAVAILABLE`.

### `POST /ettn-documents/{id}/register-manual`

**Maqsad**: e-TTN operator kabinetida qo'lda rasmiylashtirilgan bo'lsa (operator API'sida TTN turi mavjud bo'lmaganda yoki operator ishlamay qolganda), uning raqamini tizimga bog'lash — `status="registered"`, `transfers.ettn_ref` to'ldiriladi, `audit_log` yoziladi.
**Ruxsat**: `transfer.create`.
**So'rov**: `{operator_doc_id: string, ettn_date: date}`.
**Xatolar**: `404 NOT_FOUND`, `409 DOC_INVALID_STATE` (allaqachon `registered`/`accepted`), `422 VALIDATION_ERROR`.

### `POST /ettn-documents/{id}/accept` · `POST /ettn-documents/{id}/reject`

**Maqsad**: tashish yakunida yuk oluvchi e-TTN'ni **elektron tasdiqlaydi yoki rad etadi** — kiruvchi (yetkazib beruvchi chiqargan, alohida e-TTN) va ichki ko'chirish (qabul qiluvchi filial, §13 `receive`dan keyin). Birlashtirilgan EHF+TTN §19 `accept`/`reject` bilan birga tasdiqlanadi — bu yerda emas. Imzo — `sign-challenge?action=accept|reject` dan olingan payload E-IMZO bilan imzolanib shu so'rov tanasida yuboriladi, so'ng `outbox_jobs(kind="ettn_accept")`.
**Ruxsat**: `purchases.receive` (kiruvchi) / `transfer.receive` (ichki); imzo — `einvoice.sign`.
**So'rov**: `accept` — `{challenge_id, signature_pkcs7}`; `reject` — `{reason: string, challenge_id, signature_pkcs7}`.
**Javob**: `202 {status:"queued"}` → `status="accepted"`/`"rejected"`.
**Xatolar**: `404 NOT_FOUND`, `409 DOC_INVALID_STATE` (`received`/`registered`dan tashqari holat yoki birlashtirilgan EHF+TTN), `422 EIMZO_SIGN_FAILED`.

**Idempotentlik**: `Idempotency-Key` majburiy (barcha yozuvchi amallar).
**Offline**: yo'q — operator va E-IMZO online talab qiladi; offline ko'chirish uchun e-TTN internet qaytgach, tashishdan oldin (§13).
**Bog'liq**: US-M06-01…02, US-M07-01, BP-01, BP-09, BO-03, BO-04, BO-15.

---

## Ishlatilgan xato kodlari

> Umumiy/konventsiyaga oid kodlar (`VERSION_CONFLICT`, `PERIOD_CLOSED`, `IDEMPOTENCY_IN_PROGRESS`, `IDEMPOTENCY_KEY_REUSED`, `CSRF_INVALID`, `SUBSCRIPTION_RESTRICTED`, `VALIDATION_ERROR`, `NOT_FOUND`, `PERMISSION_DENIED`, `RATE_LIMITED`) — `17-api-umumiy.md`da ta'riflangan, bu yerda faqat qayerda ishlatilgani qayd etiladi. Quyida — shu faylga **xos** kodlar.

| Kod | Qayerda | Ma'nosi |
|---|---|---|
| `RESOURCE_ARCHIVED` | §1 | Arxivlangan mahsulotni tahrirlashga urinish |
| `BARCODE_DUPLICATE` | §1 | Shtrix-kod tenant ichida takror |
| `MXIK_CODE_INVALID` | §1 | MXIK format noto'g'ri (17 raqam emas) |
| `CATEGORY_HAS_PRODUCTS` | §2 | Arxivlanmagan tovarlar bog'langan kategoriyani arxivlash |
| `DOC_NOT_DRAFT` | §4, §8, §13 | Qayta `post` chaqirilishi (allaqachon `posted`) |
| `IMPORT_FILE_INVALID` | §6 | Fayl formati/kodlash xato |
| `FILE_TOO_LARGE` | §6 | Hajm/qator chegarasidan oshdi |
| `IMPORT_JOB_NOT_VALIDATED` | §6 | `commit` dan oldin `validate` o'tmagan |
| `IMPORT_JOB_ALREADY_COMMITTED` | §6 | Qayta commit |
| `PURCHASE_ORDER_CLOSED` | §8, §10 | Yopiq/bekor PO'ga kirim/tahrir |
| `LOT_ALREADY_CONSUMED` | §8 | Allaqachon chiqim bo'lgan partiyali kirimni bekor qilish |
| `EINVOICE_NOT_ACCEPTED` | §8 | Faqat qabul qilingan fakturadan kirim yaratiladi |
| `EINVOICE_NOT_SIGNED` | §19 | `accept`dan oldin imzolanmagan |
| `EINVOICE_ALREADY_SIGNED` | §19 | — |
| `EIMZO_SIGN_FAILED` | §19, §20 | E-IMZO imzo tekshiruvi muvaffaqiyatsiz |
| `EINVOICE_PROVIDER_UNAVAILABLE` | §9, §20 | Faktura.uz (operator) ishlamadi — STIR qidiruvi yoki e-TTN yuborish |
| `SUPPLIER_OVERPAY_BLOCKED` | §11 | 422 — `supplier_overpay_policy='block'` tenant'da to'lov kreditorlik qoldig'idan oshdi (qaror #47) |
| `SUPPLIER_OVERPAY_ADVANCE` | §11 | 200, `warnings[]` — `'warn'` siyosatida ortiqcha qism avans `4310`ga yozildi (qaror #47) |
| `INSUFFICIENT_STOCK` | §12, §15 | Qaytarish/hisobdan chiqarish miqdori qolgan partiyadan ko'p |
| `DEPENDENCY_NOT_SYNCED` | §13 | Boshqa qurilmadagi jo'natma hali sinxronlanmagan (`transfer.received`, retryable) |
| `ETTN_REQUIRED` | §13 | 409 — `transport_mode=vehicle` ko'chirishni e-TTN `registered` bo'lmaguncha jo'natish (`send`); offline `transfer.sent`da — `warnings[]` (hujjat `posted`da qoladi) (qaror #63) |
| `ETTN_CANCEL_IN_OPERATOR` | §13 | 200, `warnings[]` — ro'yxatdan o'tgan e-TTN'li ko'chirish bekor qilindi, e-TTN operator kabinetida bekor qilinishi/tuzatilishi kerak |
| `BARCODE_NOT_IN_CATALOG` | §14 | Inventarizatsiyada skanerlangan kod katalogda yo'q |
| `DOC_INVALID_STATE` | §13, §14, §18, §20 | Ko'chirish holati amalga mos emas — `posted`dan tashqari `send`, `sent`dan tashqari qabul, qabul qilinganini bekor qilish (§13); `post` faqat `review` holatidan yoki `count_device_mismatch` — boshqa qurilmadan voqea (§14); `failed`dan tashqari holatdagi recost ishini qayta urinish (§18); e-TTN holati imzolash/qo'lda ro'yxatga olish/tasdiqlashga mos emas (§20) |
| `WRITE_OFF_LIMIT_EXCEEDED` | §15 | Limitdan katta — endi `202 APPROVAL_REQUIRED` yo'liga yo'naltiradi, bu kod faqat tasdiq so'ralmagan holatda |
| `VALUATION_METHOD_CHANGE_NOT_ALLOWED` | §17 | Shu yil uchun qarama-qarshi so'rov takrori |

---

## Ochiq savollar

1. **Tashqi javob kerak** — markirovkalangan tovar kirimini qabul qilish va yetkazib beruvchiga qaytarishda CRPT Turon (Asl belgisi) API metodi/hujjat turi, SaaS-integrator uchun API kaliti va test muhiti, CRPT Turon (Xat 2) — interim: `MarkingPort` stub, qaytarish faqat online, qabul muddati (3 ish kuni / 72 soat) kuzatiladi va ogohlantiriladi (§8, §12) — 26 #40 (OQ-025).
2. **Tashqi javob kerak** — Faktura.uz API'si kiruvchi e-faktura VM 830 xavf darajasini qaytaradimi, Faktura.uz (Xat 4) — interim: `risk_flag="unknown"` qizil kabi hisoblanadi (QQS krediti to'lovgacha kechiktiriladi), Buxgalter my.soliq.uz kabinetidan ko'rib qo'lda belgilaydi (§11, §19) — 26 #47 (OQ-019).

## Manbalar

Fayl boshidagi "Bog'liq fayllar" ro'yxati + `17-api-umumiy.md` (parallel yozilgan konventsiya fayli).
