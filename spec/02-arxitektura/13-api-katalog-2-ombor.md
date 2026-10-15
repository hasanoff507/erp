# API katalog — 2: Ombor, katalog va xarid

*2026-10-15 · Asos: `13-api-katalog-0-umumiy.md` (konventsiyalar, xato konverti — parallel yozilmoqda, shu fayl unga mos), `01-malumotlar-modeli.md` (§4 katalog/narx, §5 kontragentlar, §6 hujjatlar, §7 registrlar, §9), `02-provodka-qoidalari.md` (2.6–2.8, 2.12, 2.20, 2.21, 3-bo'lim FIFO/AVECO), `03-integratsiyalar.md` (§4 Asl belgisi, §5 E-IMZO, §6 Vakolat.uz, §7 MXIK), `04-offline-sync.md` (§1, §7), `05-xavfsizlik-va-audit.md` (§2.1–2.2 ruxsatlar), `09-backend-arxitekturasi.md` (posting service, navbat), `spec/01-mahsulot/02-modullar-talablari.md` (M04, M05, M06, M07, M09), `03-biznes-jarayonlar.md` (BP-01, BP-09, BP-10, BP-12), `04-ekranlar-va-ux.md` (BO-02…05, BO-18, POS-08…12), `05-ai-funksiyalar.md` (AI-03).*

> **1C bilan bog'liqlik yo'q.** Bu API — noldan quriladigan tizimning o'z interfeysi; hech qanday tashqi buxgalteriya/ERP formatiga moslashtirilmagan.

## Asosiy xulosalar

1. Bu fayl **ombor/katalog/xarid** qatlamini qamrab oladi: mahsulot katalogi, narxlar, yorliqlar, import, qoldiq/partiyalar, kirim, yetkazib beruvchilar, xaridnoma, to'lov, qaytarish, ko'chirish, inventarizatsiya, hisobdan chiqarish, boshlang'ich qoldiq, baholash sozlamalari, qayta hisoblash ishlari, kiruvchi e-faktura.
2. Barcha hujjat turlari (`goods-receipts`, `supplier-returns`, `transfers`, `stock-counts`, `write-offs`, `stock-openings`) umumiy hayot sikliga amal qiladi: `POST /{resource}` (draft) → `POST /{id}/post` → `POST /{id}/cancel` (storno — registrlarga teskari yozuv, alohida teskari hujjat yo'q, `01-malumotlar-modeli.md` §1/§6). `price-changes` bundan mustasno — o'z 4-holatli mashinasi bor (`draft → pending_approval → posted/rejected`, 4-bo'lim).
3. Ma'lumotnomalar (`products`, `product-categories`, `suppliers`) — `archive`/`unarchive` bilan, hech qachon `DELETE` qilinmaydi; `PATCH` optimistik qulflash (`version`) talab qiladi → mos kelmasa `409 VERSION_CONFLICT`.
4. **Import oqimi** (`import-jobs`) uch bosqichli: `upload` (fayl) → `validate` (qator/maydon xatolari) → `commit` (bitta tranzaksiyada `stock-openings`/`debt-openings` yaratiladi). Mahsulot (US-M04-04) va qarz (US-M08-07) importi shu bir yo'l orqali.
5. **Partiya (lot) — tannarxning yagona manbai**: har kirim (qo'lda, e-fakturadan, AI-03 OCR'dan, boshlang'ich qoldiqdan) `stock-lots` yozuvi yaratadi; FIFO/AVECO (`valuation-settings`) shu ma'lumotdan hisoblanadi. Usul faqat **keyingi hisobot yili boshidan** o'zgartiriladi (US-M04-05).
6. **AI-03 (OCR)** — alohida tizim emas, `goods-receipts` oqimining bir qismi: qog'oz hujjat fotosi `POST /purchase-ocr-drafts`ga yuklanadi, AI maydonlarni chiqaradi (ishonch darajasi bilan), foydalanuvchi tasdiqlagandan keyin `POST /goods-receipts/from-ocr-draft/{id}` draft kirim hujjati yaratadi — AI hech qachon to'g'ridan-to'g'ri hujjat yozmaydi.
7. **Offline — faqat ikki joyda**: (a) `transfers` — o'z filiallar/omborlar orasida jo'natish **va** qabul qilish offline ruxsat etilgan (`04-offline-sync.md` §7); (b) `stock-counts` — skanerlash/sanash to'liq offline (POS-10), lekin yakuniy `review`/`post` online. Qolgan barcha hujjat (kirim, qaytarish, xaridnoma, to'lov, narx, import, e-faktura) — **faqat online**, chunki ular ofis/ombor sharoitida (internet mavjud) yoki tashqi tizim (E-IMZO, Faktura.uz) bilan sinxron ishlaydi. Offline `transfers`/`stock-counts` ushbu REST endpoint'lar orqali emas, `POST /sync/push` outbox voqealari (`transfer.created`/`transfer.received`, `stock_count.line_recorded`) orqali keladi — bu faylda shu voqea payload'lari hujjat sxemasiga mos qilib ko'rsatiladi, lekin alohida `/sync/push` yo'li `04-offline-sync.md`da.
8. **MXIK** (`tasnif.soliq.uz`) — sinxron, keshlangan qidiruv; chekning/fakturaning majburiy rekviziti, tovar yaratishda bloklovchi emas (saqlanadi, lekin sotishdan oldin to'ldirilishi shart — bu tekshiruv sotuv API'sida, boshqa katalog faylida).
9. **Yangi ruxsat kodlari kerak** (`05-xavfsizlik-va-audit.md` §2.1 katalogida yo'q edi): `catalog.manage`, `stock.opening.manage`, `valuation.settings.manage` — 3 ta, "Ma'lumotlar modeliga kerakli qo'shimchalar" bo'limida asoslangan.
10. Barcha pul maydonlari `"12000.00"` (decimal string, tiyingacha), miqdor `"10.000"` (3 kasr), narx/tannarx 4 kasr (`"8333.3333"`) — `01-malumotlar-modeli.md` §3 bilan bir xil.

---

## 0. Konventsiyalar (qisqa eslatma)

To'liq konventsiyalar — `13-api-katalog-0-umumiy.md`: base `/api/v1`, resurs nomlari kebab-case ko'plik, ID — UUIDv7, pul — decimal string (2 kasr), miqdor — decimal string (3 kasr), ISO sanalar, cursor pagination (`?cursor=&limit=` → `{items, next_cursor}`), sarlavhalar `X-Branch-Id` (filial scoping, barcha so'rovlarda majburiy — bu fayldagi deyarli barcha resurslar filialga/omborga bog'langan), `Idempotency-Key` (yozuvchi so'rovlarda majburiy, `/sync/push`dan tashqari), `X-CSRF-Token` (cookie-autentifikatsiyali so'rovlarda), xato konverti `{error:{code, message_key, details, request_id}}`, `version` optimistik qulflash → `409 VERSION_CONFLICT`, hujjat sikli `draft → post → cancel` (storno), asinxron Excel import/eksport ishlari.

Bu faylda har bir endpoint uchun: metod+yo'l, maqsad, ruxsat, so'rov sxemasi, javob, xatolar, idempotentlik, offline izoh, US/ekran ID.

---

## Indeks

| Bo'lim | Resurs | Asosiy endpointlar |
|---|---|---|
| 1 | `products` | `GET/POST /products`, `GET/PATCH /products/{id}`, `POST /products/{id}/archive`, barcode'lar, MXIK qidiruv |
| 2 | `product-categories` | `GET/POST /product-categories`, `PATCH/POST archive` |
| 3 | `units` | `GET /units` (global, faqat o'qish) |
| 4 | `prices`, `price-changes` | narx tarixi, narx o'zgarishi hujjati (`pending_approval`) |
| 5 | `label-print-queue`, `label-print-jobs`, `label-templates` | yorliq navbati, chop etish ishi |
| 6 | `import-jobs` | `products`/`opening_stock`/`opening_debts` Excel/CSV import |
| 7 | `stock-balances`, `stock-lots`, `stock-moves` | qoldiq, partiya, harakat tarixi, kam qoldiq |
| 8 | `goods-receipts`, `purchase-ocr-drafts` | kirim hujjati (qo'lda / e-fakturadan / AI-03'dan), posting |
| 9 | `suppliers` | yetkazib beruvchi CRUD, STIR qidiruv |
| 10 | `purchase-orders` | xaridnoma hayot sikli |
| 11 | `supplier-payments` | to'lov, "qizil" faktura QQS krediti |
| 12 | `supplier-returns` | yetkazib beruvchiga qaytarish |
| 13 | `transfers` | jo'natish/qabul/farq (offline) |
| 14 | `stock-counts` | sanash varag'i, skaner, review, post |
| 15 | `write-offs` | hisobdan chiqarish (sabab bilan) |
| 16 | `stock-openings` | boshlang'ich qoldiq |
| 17 | `valuation-settings`, `stock-settings` | FIFO/AVECO, tarozi kod formati, kam qoldiq chegarasi |
| 18 | `recost-jobs` | qayta hisoblash holati |
| 19 | `einvoices` (direction=in) | kiruvchi e-faktura ro'yxati, qabul/rad, E-IMZO imzolash |

---

## 1. Mahsulot katalogi (`products`)

### `GET /products`

**Maqsad**: katalogni ro'yxatlash/qidirish (BO-03, BO-04, BO-05, BO-18 uchun manba).
**Ruxsat**: `stock.view`.

| Parametr | Tur | Majburiy | Izoh |
|---|---|---|---|
| `search` | string | yo'q | Kirill/lotin aralash, `pg_trgm` orqali nom/shtrix-kod bo'yicha qidiruv |
| `category_id` | UUID | yo'q | — |
| `archived` | bool | yo'q | standart `false` |
| `is_weighed` | bool | yo'q | — |
| `low_stock` | bool | yo'q | `true` — faqat `qty <= min_stock` bo'lgan tovarlar (ombor join, X-Branch-Id ombori) |
| `cursor`, `limit` | string, int | yo'q | standart `limit=50`, max `200` |

**Javob** `200`: `{items:[Product], next_cursor}`. `Product`: `id, name, category_id, unit_code, mxik_code, package_code, vat_rate, is_marked, is_weighed, min_stock, archived_at, version, barcodes:[{id,barcode,kind,units_per_barcode}]`.
**Xatolar**: — (bo'sh ro'yxat — oddiy `200`).
**Idempotentlik**: shart emas (o'qish).
**Offline**: POS uchun katalog `/sync/pull?scope=catalog` orqali keshlanadi (`04-offline-sync.md` §1); bu endpoint faqat online back-office uchun.
**US/Ekran**: BO-03, BO-04, BO-05, BO-18.

### `POST /products`

**Maqsad**: yangi tovar yaratish.
**Ruxsat**: `catalog.manage` (yangi kod, pastda asoslangan).

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `name` | string | ha | 1–255 belgi |
| `category_id` | UUID | yo'q | mavjud, arxivlanmagan kategoriya |
| `unit_code` | string | ha | `units` jadvalida mavjud |
| `mxik_code` | string | yo'q* | 17 raqam; `*` — chekka chiqarishdan oldin majburiy (bu yerda bloklanmaydi, 8-xulosa) |
| `package_code` | string | yo'q | — |
| `vat_rate` | enum | ha | `12` / `0` / imtiyoz kodi |
| `is_marked` | bool | ha | standart `false` |
| `is_weighed` | bool | ha | standart `false` |
| `min_stock` | decimal(3dp) | yo'q | ≥ 0 |
| `barcode` | string | yo'q | birinchi shtrix-kod, kind=`ean` |

**Javob** `201`: to'liq `Product` (yuqoridagi sxema, `version=1`).
**Xatolar**: `422 VALIDATION_ERROR`, `409 BARCODE_DUPLICATE` (tenant ichida shtrix-kod takror), `422 MXIK_CODE_INVALID` (format 17 raqamdan farq qiladi).
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q.
**US/Ekran**: US-M09-05 (shtrix-kod), BO-04 (AI-03 orqali to'ldirilgan qatorlardan ham shu endpoint chaqiriladi, lekin odatda `goods-receipts` oqimi ichida — bu yerda mustaqil qo'lda yaratish).

### `GET /products/{id}` · `PATCH /products/{id}`

**Ruxsat**: `stock.view` (GET), `catalog.manage` (PATCH).
`PATCH` tanasi — yuqoridagi maydonlarning istalgan to'plami + **majburiy** `version`. Mos kelmasa `409 VERSION_CONFLICT`.
**Xatolar**: `404 PRODUCT_NOT_FOUND`, `409 PRODUCT_ARCHIVED` (arxivlangan tovarni tahrirlashga urinish — avval `unarchive`).

### `POST /products/{id}/archive` · `POST /products/{id}/unarchive`

**Ruxsat**: `catalog.manage`. Tana: `{reason?: string}`. Soft-delete — `archived_at`; `unarchive` → `archived_at=null`. Arxivlangan tovar POS katalogida ko'rinmaydi, lekin eski hujjatlarda (`sale_lines.product_id`) saqlanadi (`01-malumotlar-modeli.md` §1).
**Offline chekka holat**: tovar offline sotuv paytida serverda arxivlangan bo'lsa — hujjat baribir qabul qilinadi, bayroq qo'yiladi (`04-offline-sync.md` §5) — bu `/sync/push` tomonida, bu yerda emas.

### Shtrix-kodlar — `GET/POST /products/{id}/barcodes` · `DELETE /products/{id}/barcodes/{barcode_id}`

**Ruxsat**: `catalog.manage`.
`POST` tana: `{barcode: string, kind: "ean"|"internal"|"weighed_prefix", units_per_barcode?: decimal(3dp)}`. `units_per_barcode` — qadoq/quti koeffitsienti (`01-malumotlar-modeli.md` §4 birlik konversiyasi qoidasi); standart `1.000`.
**Xatolar**: `409 BARCODE_DUPLICATE` (tenant ichida noyob bo'lishi shart).

### `POST /products/{id}/barcodes/internal-generate`

**Maqsad**: shtrix-kodsiz tovarga ichki kod berish (US-M09-05).
**Ruxsat**: `catalog.manage`.
Tana: `{}` (parametrsiz). Server `internal_barcode_seq`dan keyingi qiymatni oladi, EAN-13 nazorat raqami bilan to'liq kod yaratadi, `kind="internal"` bilan yozadi.
**Javob** `201`: `{barcode, kind:"internal", units_per_barcode:"1.000"}`.
**Idempotentlik**: `Idempotency-Key` majburiy (ikki marta bosilsa ikki kod berilmasligi uchun).
**US/Ekran**: US-M09-05, BO-18.

### MXIK qidiruv/tekshirish

`GET /mxik-codes?query=<matn>&limit=20` — **Ruxsat**: `catalog.manage`. Sinxron, keshlangan (`tasnif.soliq.uz`, `03-integratsiyalar.md` §7). Javob: `{items:[{code, name, vat_hint}]}` — `next_cursor` yo'q (oddiy massiv, max 20).
`GET /mxik-codes/{code}` — kodni tasdiqlash + QQS toifasi. `404 MXIK_CODE_NOT_FOUND` agar kod kesh/tashqi tizimda topilmasa.
**Xatolar**: tashqi tizim ishlamasa — `200` lekin `{items:[], source:"stale_cache"}` (3-urinishdan keyin oxirgi ma'lum kesh, `03-integratsiyalar.md` §7 qayta urinish siyosati). Qattiq xato yo'q — foydalanuvchi kodni qo'lda kiritadi.
**US/Ekran**: BO-04, M09.

---

## 2. Kategoriyalar (`product-categories`)

`GET /product-categories?parent_id=&cursor=&limit=` — **Ruxsat**: `stock.view`. Daraxt, `parent_id=null` — ildiz.
`POST /product-categories` — **Ruxsat**: `catalog.manage`. Tana: `{name, parent_id?}`.
`PATCH /product-categories/{id}` — `{name?, parent_id?, version}`.
`POST /product-categories/{id}/archive` — tana: `{}`. Arxivlashdan oldin server tekshiradi: agar arxivlanmagan tovar shu kategoriyaga bog'langan bo'lsa → `409 CATEGORY_HAS_PRODUCTS` (avval tovarlarni boshqa kategoriyaga ko'chirish/arxivlash kerak).
**Xatolar**: `404 CATEGORY_NOT_FOUND`, `409 VERSION_CONFLICT`.
**Offline**: kategoriyalar `/sync/pull?scope=catalog` bilan birga keshlanadi.

---

## 3. Birliklar (`units`)

`GET /units` — **Ruxsat**: `stock.view`. Global jadval (`tenant_id` yo'q, RLS istisnosi), faqat o'qish; tenant o'zi yangi birlik qo'sha olmaydi (MVP cheklovi). Javob: `{items:[{code, is_fractional}]}` (sahifalashsiz, ro'yxat kichik).

---

## 4. Narxlar (`prices`, `price-changes`)

### `GET /products/{id}/prices`

**Maqsad**: narx tarixi (US-M09-01).
**Ruxsat**: `stock.view`.
Parametr: `branch_id?` (bo'sh — barcha filial uchun umumiy narxlar). Javob: `{items:[{price, valid_from, valid_to, set_by, price_change_doc_id, branch_id}], next_cursor}` — `valid_to` hisoblanadigan maydon (keyingi yozuvning `valid_from`'i, oxirgisida `null`).

### `POST /price-changes`

**Maqsad**: narx o'zgarishi hujjatini yaratish (draft).
**Ruxsat**: `prices.edit`.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `doc_date` | date | ha | — |
| `lines[].product_id` | UUID | ha | — |
| `lines[].new_price` | decimal(2dp) | ha | > 0 |
| `lines[].branch_id` | UUID\|null | yo'q | `null` = barcha filial |
| `comment` | string | yo'q | — |

**Javob** `201`: `{id, status:"draft", number:null, lines:[...], version:1}`.
**Xatolar**: `422 VALIDATION_ERROR` (manfiy/nol narx).

### `POST /price-changes/{id}/post`

**Maqsad**: hujjatni o'tkazish. Har qator uchun server joriy narx bilan farqni (%) hisoblaydi va `prices.approve` limitiga (taxmin, `role_permissions.limit_value`) solishtiradi:
- Limit ichida → darhol `product_prices` yangilanadi, hujjat `status="posted"`, `label_print_queue`ga `reason="price_changed"` qatorlari qo'shiladi (US-M09-04).
- Limitdan katta → `status="pending_approval"`, BO-16 navbatiga tushadi (US-M09-02); `product_prices` **hali o'zgarmaydi**.

**Ruxsat**: `prices.edit`.
**Xatolar**: `404 PRICE_CHANGE_NOT_FOUND`, `409 {code:"PRICE_CHANGE_ALREADY_POSTED"}`.
**Idempotentlik**: `Idempotency-Key` majburiy.
**US/Ekran**: US-M09-01, US-M09-02, BO-05.

### `POST /price-changes/{id}/approve` · `POST /price-changes/{id}/reject`

**Ruxsat**: `prices.approve` (faqat Egasi, 2.2-jadval bo'yicha Menejer ham).
`approve` — tana `{}`: `product_prices` yangilanadi, `status="posted"`, yorliq navbatiga qo'shiladi. `reject` — tana `{reason: string}` (majburiy): `status="rejected"`, narx o'zgarmaydi.
**Xatolar**: `409 {code:"PRICE_CHANGE_NOT_PENDING"}` (faqat `pending_approval` holatidagi hujjat tasdiqlanadi/rad etiladi).
**US/Ekran**: US-M09-02, BO-16.

> **Eslatma**: `price-changes` umumiy `draft→post→cancel` naqshidan **farqlanadi** — `post` natijasi shartli (`posted` yoki `pending_approval`), va posted holatdan keyin `cancel` yo'q (narxni orqaga qaytarish — yangi `price-changes` hujjati bilan, teskari emas).

---

## 5. Yorliqlar (`label-print-queue`, `label-print-jobs`, `label-templates`)

### `GET /label-print-queue`

**Maqsad**: narxi o'zgargan/yangi, hali chop etilmagan tovarlar ro'yxati (BO-18).
**Ruxsat**: `labels.print`.
Parametrlar: `reason?` (`price_changed`/`new`), `cursor`, `limit`. Javob: `{items:[{product_id, product_name, reason, current_price, old_price?, barcode, created_at}], next_cursor}`.

### `GET /label-templates`

**Ruxsat**: `labels.print`. Javob: `{items:[{id, name, width_mm, height_mm, fields:[...]}]}` — standart shablonlar (58×40mm va h.k., US-M09-04), tenant o'zgartira olmaydi (MVP, global ro'yxat).

### `POST /label-print-jobs`

**Maqsad**: tanlangan tovarlar uchun yorliq chop etish ishini yaratish va serverda PDF generatsiya qilish (zahira yo'l — asosiy chop etish brauzerda `bwip-js`; server `python-barcode`+`zxing-cpp` orqali ham PDF beradi, `09-backend-arxitekturasi.md` §5).

| Maydon | Tur | Majburiy | Izoh |
|---|---|---|---|
| `template_id` | UUID | ha | — |
| `product_ids` | UUID[] | ha | 1–500 |
| `copies_per_product` | int | yo'q | standart `1` |

**Javob** `202`: `{job_id, status:"queued"}` → poll `GET /label-print-jobs/{id}` → `{status:"done", file_url}` (PDF, `attachments`). Muvaffaqiyatli chop etilgandan keyin klient `POST /label-print-queue/mark-printed {product_ids}` chaqiradi — navbatdan olib tashlaydi (`printed_at` o'rnatiladi).
**Xatolar**: `404 LABEL_TEMPLATE_NOT_FOUND`.
**Idempotentlik**: `Idempotency-Key` majburiy (job yaratishda).
**Offline**: "Offline — lokal printer bilan ishlaydi" (BO-18 ekran holati) — bu brauzerdagi `bwip-js` yo'li, server endpoint'i shart emas agar printer to'g'ridan-to'g'ri lokal ulangan bo'lsa; server yo'li faqat online.
**US/Ekran**: US-M09-04, BO-18.

---

## 6. Import ishlari (`import-jobs`)

Uchta `kind`: `products` (US-M04-04), `opening_stock` (US-M04-04), `opening_debts` (US-M08-07) — format `01-malumotlar-modeli.md` §10 va `02-modullar-talablari.md` M04 (2026-10-15 qo'shimchasi) bo'yicha.

### `GET /import-jobs/templates/{kind}`

**Ruxsat**: `stock.opening.manage` (`opening_stock`/`opening_debts`) yoki `catalog.manage` (`products`).
Javob: CSV fayl (`Content-Disposition: attachment`), UTF-8, `;` ajratgich — ustunlar `kind`ga qarab (`01-malumotlar-modeli.md` §10 jadvali): `products.csv` → `name;barcode;unit_code;mxik_code;vat_rate;price;category;is_marked`; `opening_stock.csv` → `barcode;qty;unit_cost;expiry_date`; `opening_debts.csv` → `name;phone;amount;direction;date`.

### `POST /import-jobs`

**Maqsad**: fayl yuklash, job yaratish (`status="uploaded"`).
**Ruxsat**: `catalog.manage` (`kind=products`) / `stock.opening.manage` (`kind=opening_stock`, `kind=opening_debts`).
`multipart/form-data`: `kind` (enum), `file` (CSV/XLSX, max 10 MB, max 20 000 qator — taxmin).
**Javob** `201`: `{id, kind, status:"uploaded", total_rows:null}`.
**Xatolar**: `422 IMPORT_FILE_INVALID` (format/kodlash xato), `413 {code:"IMPORT_FILE_TOO_LARGE"}`.
**Idempotentlik**: `Idempotency-Key` majburiy.

### `POST /import-jobs/{id}/validate`

Asinxron ish (`202`): har qatorni sxema + biznes qoida bo'yicha tekshiradi (masalan `products` — shtrix-kod takrori, MXIK format; `opening_stock` — shtrix-kod katalogda topildimi; `opening_debts` — `direction` qiymati `receivable`/`payable`), natijani `import_jobs.errors` JSONB'ga (qator, maydon, xato kodi) yozadi, `status="validated"` (yoki hamma qator xato bo'lsa `status="failed"`).
**Javob**: `{job_id, status:"queued"}` → poll `GET /import-jobs/{id}` → `{status:"validated", total_rows, ok_rows, error_rows}`.

### `GET /import-jobs/{id}/errors?cursor=&limit=`

Javob: `{items:[{row, field, code, message}], next_cursor}`.

### `POST /import-jobs/{id}/commit`

**Maqsad**: faqat **xatosiz** qatorlarni (yoki foydalanuvchi "xatolarsiz davom et" deb tasdiqlagan qismni) bitta tranzaksiyada hujjatlarga aylantirish: `products` → yangi `products`+`product_barcodes`; `opening_stock` → bitta `stock-openings` hujjati (7-bo'lim bilan bir xil posting, §2.21 provodka); `opening_debts` → bitta `debt-openings` hujjati (debts katalogida, bu faylda emas — faqat `import_jobs.kind=opening_debts` shu yerda hosil bo'ladi).
**Ruxsat**: `validate`dagi bilan bir xil.
**Tana**: `{skip_error_rows: bool}` (standart `true`).
**Javob** `200`: `{status:"committed", created_doc_ids:[...]}`.
**Xatolar**: `409 IMPORT_JOB_NOT_VALIDATED` (avval `validate` chaqirilmagan), `409 IMPORT_JOB_ALREADY_COMMITTED`.
**Idempotentlik**: `commit` tabiatan bir martalik — qayta chaqirilsa `409 IMPORT_JOB_ALREADY_COMMITTED` (ikkinchi marta hujjat yaratilmaydi); shuningdek `Idempotency-Key` ham talab qilinadi (ikki marta tasodifiy bosilganda).
**Offline**: yo'q (fayl yuklash, online).
**US/Ekran**: US-M04-04, US-M08-07, BO-21 (ro'yxatdan o'tish oqimida).

---

## 7. Ombor qoldig'i (`stock-balances`, `stock-lots`, `stock-moves`)

### `GET /stock-balances`

**Maqsad**: BO-03 asosiy ro'yxati.
**Ruxsat**: `stock.view`.
Parametrlar: `warehouse_id?` (standart — `X-Branch-Id`ning ombori), `product_id?`, `low_stock?` (bool), `search?`, `cursor`, `limit`.
Javob: `{items:[{product_id, product_name, warehouse_id, qty, value, min_stock, is_low, updated_at}], next_cursor}`. Manfiy `qty` — `⚠` bayrog'i (`is_negative:true`) bilan qaytariladi (overselling, `04-offline-sync.md` §5).

### `GET /stock-lots`

**Maqsad**: partiya/yaroqlilik muddati ko'rinishi (US-M04-06, BO-03).
**Ruxsat**: `stock.view`.
Parametrlar: `warehouse_id?`, `product_id?`, `expiring_within_days?` (int — masalan `7`, US-M04-06 standart), `cursor`, `limit`.
Javob: `{items:[{id, product_id, warehouse_id, received_at, qty_in, qty_left, unit_cost, expiry_date, receipt_line_id}], next_cursor}`.

### `GET /stock-moves`

**Maqsad**: harakat tarixi (audit/tekshiruv uchun).
**Ruxsat**: `stock.view`.
Parametrlar: `warehouse_id?`, `product_id?`, `doc_type?`, `from?`, `to?` (ISO sana), `cursor`, `limit`.
Javob: `{items:[{id, warehouse_id, product_id, lot_id, qty, cost_amount, doc_type, doc_id, line_id, moved_at}], next_cursor}`. `qty`/`cost_amount` — ishora bilan (`±`).

**Xatolar** (uchtasi uchun): — (faqat o'qish, bo'sh ro'yxat qaytadi).
**Idempotentlik**: shart emas.
**Offline**: faqat ko'rish, IndexedDB'dagi oxirgi nusxa (BO-03 ekran holati).
**US/Ekran**: US-M04-01…03, US-M04-06, BO-03.

---

## 8. Omborga kirim (`goods-receipts`) va AI-03 OCR

### `POST /purchase-ocr-drafts`

**Maqsad**: qog'oz hujjat (yuk xati/faktura) fotosidan AI-03 orqali maydon chiqarish — faqat QQS to'lovchi bo'lmagan/norasmiy yetkazib beruvchi yoki texnik uzilish holatlari uchun (standart QQS to'lovchilar o'rtasidagi e-faktura OCR qilinmaydi, `05-ai-funksiyalar.md` AI-03 qamrov cheklovi).
**Ruxsat**: `purchases.receive`.
`multipart/form-data`: `image` (JPEG/PNG/PDF, max 15 MB).
**Javob** `202`: `{id, status:"processing"}` → poll `GET /purchase-ocr-drafts/{id}` → `200`:
```json
{
  "id": "...", "status": "ready",
  "fields": {
    "supplier_name": {"value": "Mega Trade MChJ", "confidence": 0.97},
    "doc_date": {"value": "2026-10-12", "confidence": 0.91},
    "lines": [
      {"product_name": {"value": "Coca-Cola 1.5L", "confidence": 0.88},
       "qty": {"value": "48.000", "confidence": 0.95},
       "cost": {"value": "9500.00", "confidence": 0.93}}
    ]
  },
  "low_confidence_fields": ["lines[0].product_name"]
}
```
`low_confidence_fields` — maydon bo'yicha chegaradan past (summa <95%, sana <90%, miqdor/nom <80%, `05-ai-funksiyalar.md` AI-03 Chegaralar) — UI'da sariq belgilanadi, foydalanuvchi qo'lda tuzatadi, **avtomatik hujjatga kirmaydi**.
**Xatolar**: `422 {code:"OCR_IMAGE_UNREADABLE"}`, `503 AI_UNAVAILABLE` (Claude API vaqtincha ishlamasa — foydalanuvchi qo'lda kiritishga yo'naltiriladi, `03-integratsiyalar.md` §12).
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q (AI chaqiruvi online talab qiladi).
**US/Ekran**: US-M04-04 (3-yo'l), BO-04 AI-03 bandi.

### `POST /goods-receipts`

**Maqsad**: kirim hujjatini draft sifatida yaratish — qo'lda, PO asosida yoki OCR draftdan.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `supplier_id` | UUID | ha | `suppliers`da mavjud, `is_supplier=true` |
| `warehouse_id` | UUID | ha | `X-Branch-Id`ga tegishli |
| `po_id` | UUID | yo'q | mavjud bo'lsa `purchase_orders.status IN (sent, partially_received)` |
| `doc_date` | date | ha | — |
| `lines[].product_id` | UUID | ha | — |
| `lines[].qty` | decimal(3dp) | ha | > 0 |
| `lines[].cost` | decimal(4dp) | ha | ≥ 0 (QQS'siz birlik narx) |
| `lines[].vat_rate` | enum | ha | `12`/`0`/imtiyoz |
| `lines[].expiry_date` | date | yo'q | — |
| `ettn_ref` | string | yo'q | qo'lda belgilash (e-TTN API yo'q, MVP, `03-integratsiyalar.md` §3) |
| `poa_number` | string | yo'q | vakil ishonchnomasi raqami, qo'lda (`03-integratsiyalar.md` §6) |

**Javob** `201`: `{id, status:"draft", number:null, lines, version:1}`.
**Xatolar**: `422 VALIDATION_ERROR`, `404 SUPPLIER_NOT_FOUND`, `409 {code:"PURCHASE_ORDER_CLOSED"}` (agar `po_id` berilgan va PO yopiq/bekor bo'lsa).

### `POST /goods-receipts/from-einvoice/{einvoice_id}`

**Maqsad**: qabul qilingan kiruvchi e-faktura (19-bo'lim) asosida draft kirim hujjatini oldindan to'ldirish (qatorlar, summalar, QQS — e-faktura `payload`dan).
**Ruxsat**: `purchases.receive`.
Tana: `{warehouse_id}` (qolgan maydonlar e-fakturadan olinadi, foydalanuvchi keyin `PATCH` bilan tahrirlaydi — masalan `expiry_date` qo'shadi).
**Xatolar**: `404 EINVOICE_NOT_FOUND`, `409 {code:"EINVOICE_NOT_ACCEPTED"}` (faqat `status=accepted` fakturadan kirim yaratiladi).

### `POST /goods-receipts/from-ocr-draft/{ocr_draft_id}`

**Maqsad**: tasdiqlangan AI-03 draftidan kirim hujjati yaratish.
**Ruxsat**: `purchases.receive`.
Tana: `{warehouse_id, supplier_id, lines: [...]}` — foydalanuvchi tasdiqlagan/tuzatgan qiymatlar (OCR natijasi faqat **taklif**, server AI maydonlarini o'zi ko'chirmaydi — klient `fields`ni o'qib, tuzatib, shu formatda yuboradi).
**Xatolar**: `404 {code:"OCR_DRAFT_NOT_FOUND"}`, `409 {code:"OCR_DRAFT_NOT_READY"}`.

### `GET /goods-receipts` · `GET /goods-receipts/{id}` · `PATCH /goods-receipts/{id}`

**Ruxsat**: `stock.view` (GET), `purchases.receive` (PATCH, faqat `draft` holatda).
Parametrlar (GET ro'yxat): `supplier_id?`, `status?`, `from?`, `to?`, `cursor`, `limit`.

### `POST /goods-receipts/{id}/post`

**Maqsad**: hujjatni o'tkazish — yangi `stock_lots` yaratiladi, `stock_balances`/`stock_moves` +, yetkazib beruvchiga qarz + (nasiya bo'lsa), kiritiladigan QQS (`02-provodka-qoidalari.md` 2.6–2.8; "qizil" faktura bo'lsa QQS yozuvi to'lovgacha kechiktiriladi, 2.8).
**Ruxsat**: `purchases.post` (Buxgalter).
Tana: `{}`.
**Javob** `200`: `{id, status:"posted", number:"K-01-2026-000154", posted_at, lots_created:[{lot_id, product_id, qty_in, unit_cost}]}`.
**Xatolar**: `404 GOODS_RECEIPT_NOT_FOUND`, `409 {code:"GOODS_RECEIPT_ALREADY_POSTED"}`, `409 PERIOD_CLOSED` (agar `doc_date` yopilgan davrda bo'lsa).
**Idempotentlik**: `Idempotency-Key` majburiy.

### `POST /goods-receipts/{id}/cancel`

**Ruxsat**: `purchases.post`. Tana: `{reason: string}` (majburiy). Storno: `stock_moves`/`stock_lots.qty_left` teskari, kreditorlik qarzi teskari, QQS teskari (`02-provodka-qoidalari.md` §5.2). Agar partiyadan allaqachon chiqim bo'lgan bo'lsa (masalan sotilgan) — `409 {code:"LOT_ALREADY_CONSUMED"}` (bekor qilish taqiqlanadi, avval sotuvni ko'rib chiqish kerak).
**Offline**: yo'q (BO-04, online). Mobil skaner (POS-08) orqali qabul qilish esa `/sync/push` outbox yo'li bilan ishlaydi (Asosiy xulosa 7) — server tomoni bir xil `*PostingService`.
**US/Ekran**: US-M04-01, US-M07-01…03, BP-01, BO-04, POS-08.

---

## 9. Yetkazib beruvchilar (`suppliers`)

`counterparties` jadvalining `is_supplier=true` ko'rinishi (mijozlar bilan bir xil jadval, `01-malumotlar-modeli.md` §5).

`GET /suppliers?search=&archived=&cursor=&limit=` — **Ruxsat**: `stock.view`.
`POST /suppliers` — **Ruxsat**: `purchases.create`.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `name` | string | ha | — |
| `phone` | string | yo'q | — |
| `kind` | enum | ha | `person`/`company` |
| `stir` | string | `company` bo'lsa shart | 9 raqam |
| `legal_address`, `bank_account`, `bank_mfo` | string | yo'q | B2B e-faktura chiqarish uchun shart (qabul qilinmasa ham saqlanadi, faqat chiquvchi e-faktura bloklanadi — boshqa katalogda) |
| `vat_payer` | bool | yo'q | AI-03 qamrovini aniqlashda ishlatiladi |

`GET/PATCH /suppliers/{id}` — `PATCH` `version` talab qiladi.
`POST /suppliers/{id}/archive` — **Ruxsat**: `purchases.create`.
`GET /suppliers/{id}/debt-balance` — **Ruxsat**: `stock.view`. Javob: `{payable: "1250000.00", receivable: "0.00"}` (`debt_balances`, `direction=payable/receivable`).
`POST /suppliers/{id}/lookup-by-stir` — **Ruxsat**: `purchases.create`. Tana: `{}` (STIR allaqachon `suppliers.stir`da). Faktura.uz `CheckCompanyExist/:inn` orqali rekvizitlarni (`legal_address`, bank) avto-to'ldiradi, javobda taklif qilinadi (foydalanuvchi tasdiqlagandan keyin `PATCH`ga yuboradi).
**Xatolar**: `404 SUPPLIER_NOT_FOUND`, `409 VERSION_CONFLICT`, `503 {code:"EINVOICE_PROVIDER_UNAVAILABLE"}` (lookup uchun).
**Offline**: yo'q.
**US/Ekran**: M07, BO-04.

---

## 10. Xaridnomalar (`purchase-orders`)

### `POST /purchase-orders`

**Ruxsat**: `purchases.create`.

| Maydon | Tur | Majburiy |
|---|---|---|
| `supplier_id` | UUID | ha |
| `warehouse_id` | UUID | ha |
| `doc_date` | date | ha |
| `lines[].product_id` | UUID | ha |
| `lines[].qty` | decimal(3dp) | ha |
| `lines[].price` | decimal(4dp) | yo'q (rejalashtirish, taxminiy) |

**Javob** `201`: `{id, status:"draft", ...}`.

### `POST /purchase-orders/{id}/send`

**Ruxsat**: `purchases.create`. `draft→sent`. Tana `{}`.

### `GET /purchase-orders` · `GET /purchase-orders/{id}`

**Ruxsat**: `stock.view`. Javobda `status` — hisoblanadigan maydon: `draft`/`sent`/`partially_received`/`closed`/`cancelled` (`goods_receipts.po_id` yig'indisidan, `01-malumotlar-modeli.md` §8); `received_lines:[{product_id, ordered_qty, received_qty}]` ham qo'shiladi.

### `PATCH /purchase-orders/{id}`

**Ruxsat**: `purchases.create`. Faqat `draft`/`sent` holatda. `version` talab qiladi.

### `POST /purchase-orders/{id}/cancel`

**Ruxsat**: `purchases.create`. Tana: `{reason}`. `closed`dan keyin tahrir/bekor qilish taqiqlanadi → `409 {code:"PURCHASE_ORDER_CLOSED"}`.
**Xatolar**: `404 PURCHASE_ORDER_NOT_FOUND`, `409 PURCHASE_ORDER_CLOSED`, `409 VERSION_CONFLICT`.
**Idempotentlik**: `Idempotency-Key` majburiy (`send`/`cancel`).
**Offline**: yo'q.
**US/Ekran**: US-M07-01, BO-04.

---

## 11. Yetkazib beruvchiga to'lovlar (`supplier-payments`)

### `POST /supplier-payments`

**Maqsad**: kreditorlik qarzini to'lash, "qizil" faktura bo'lsa shu bilan birga kechiktirilgan QQS kreditini ochish (`02-provodka-qoidalari.md` 2.16).
**Ruxsat**: `purchases.pay` (Buxgalter).

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `supplier_id` | UUID | ha | — |
| `amount` | decimal(2dp) | ha | > 0, ≤ joriy kreditorlik qoldig'i (oshsa ogohlantirish, bloklanmaydi — avans sifatida qabul qilinadi, `4310`) |
| `source` | enum | ha | `cash`/`bank` |
| `cash_register_id` | UUID | `source=cash` bo'lsa shart | — |
| `allocations[].receipt_id` | UUID | ha | qaysi kirim hujjatini yopadi |
| `allocations[].amount` | decimal(2dp) | ha | — |
| `doc_date` | date | ha | — |

Bu endpoint **yaratilishi bilanoq o'tkaziladi** (alohida `draft`/`post` yo'q — to'lov darhol amal, `02-provodka-qoidalari.md` 2.16'da alohida holat mashinasi yo'q; shunga qaramay `cancel` mavjud, chunki xato to'lov storno qilinishi kerak bo'lishi mumkin).
**Javob** `201`: `{id, status:"posted", number, vat_credit_unlocked: [{einvoice_id, vat_amount}]}` — agar `allocations` ichida "qizil" fakturaga tegishli kirim bo'lsa, shu qismga mos `4410/6010` QQS yozuvi ham qo'shiladi va `vat_credit_unlocked`da ko'rsatiladi (qisman to'lovda proporsional, `02-provodka-qoidalari.md` 2.16 — taxmin).
**Xatolar**: `422 VALIDATION_ERROR`, `409 {code:"SUPPLIER_PAYMENT_EXCEEDS_DEBT"}` (standart siyosat — ogohlantirish bilan ruxsat, qattiq bloklash **emas**; bu kod faqat tenant sozlamasida "qattiq nazorat" yoqilgan bo'lsa qaytadi — taxmin, ochiq savol), `409 PERIOD_CLOSED`.

### `POST /supplier-payments/{id}/cancel`

**Ruxsat**: `purchases.pay`. Tana: `{reason}`. Storno: kreditorlik qarzi orqaga, QQS krediti ochilgan bo'lsa u ham storno.
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q.
**US/Ekran**: US-M07-04, US-M10-03, BP-12, BO-04.

---

## 12. Yetkazib beruvchiga qaytarish (`supplier-returns`)

### `POST /supplier-returns`

**Ruxsat**: `purchases.return`.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `receipt_id` | UUID | ha | asl kirim hujjati, `status=posted` |
| `doc_date` | date | ha | — |
| `lines[].receipt_line_id` | UUID | ha | asl kirim qatoriga tegishli |
| `lines[].lot_id` | UUID | ha | shu qatordan yaratilgan partiya |
| `lines[].qty` | decimal(3dp) | ha | ≤ `stock_lots.qty_left` |
| `reason` | enum | ha | `expired`/`damaged`/`excess`/`other` |

**Javob** `201`: `{id, status:"draft", ...}`.

### `POST /supplier-returns/{id}/post`

Ombor qoldig'i − (asl partiyadan), yetkazib beruvchiga qarz − (yoki debitorlik +), kiritiladigan QQS − (`02-provodka-qoidalari.md` 2.20).
**Ruxsat**: `purchases.post`.
**Xatolar**: `409 {code:"SUPPLIER_RETURN_QTY_EXCEEDED"}` (`qty` > `qty_left`), `409 PERIOD_CLOSED`.

### `POST /supplier-returns/{id}/cancel`

**Ruxsat**: `purchases.post`. Tana: `{reason}`.
**Xatolar**: `404 {code:"SUPPLIER_RETURN_NOT_FOUND"}`, `409 VERSION_CONFLICT`.
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q (ofis/ombor, internet mavjud joy).
**US/Ekran**: US-M07-05, BO-04.
**Ochiq savol**: markirovkalangan tovarni yetkazib beruvchiga qaytarishda Asl belgisi operatsiyasi — manbada topilmadi (`02-modullar-talablari.md` M07 chekka holatlar).

---

## 13. Ko'chirish (`transfers`)

### `POST /transfers`

**Maqsad**: jo'natish (draft → sent, jo'natuvchi ombordan chiqim).
**Ruxsat**: `transfer.create`.

| Maydon | Tur | Majburiy |
|---|---|---|
| `from_warehouse_id` | UUID | ha |
| `to_warehouse_id` | UUID | ha (boshqa filial/ombor) |
| `doc_date` | date | ha |
| `lines[].product_id` | UUID | ha |
| `lines[].qty` | decimal(3dp) | ha |
| `client_event_id` | UUID | offline yaratilganda | `01-malumotlar-modeli.md` §6 idempotentlik |

`POST`ning o'zi hujjatni `draft` qiladi; jo'natishni rasmiylashtirish uchun:

### `POST /transfers/{id}/send`

`draft→sent`: `stock_moves` (jo'natuvchi −, "yo'lda"), partiya ma'lumoti saqlanadi. **Ruxsat**: `transfer.create`.

### `POST /transfers/{id}/receive`

**Maqsad**: qabul qilish (US-M06-02).
**Ruxsat**: `transfer.receive`.

| Maydon | Tur | Majburiy |
|---|---|---|
| `lines[].transfer_line_id` | UUID | ha |
| `lines[].qty_received` | decimal(3dp) | ha |

Agar barcha qatorlar `qty_received = qty` → `status="received"`; farq bo'lsa → `status="discrepancy"` (`stock_moves` qabul qiluvchida +, farq — kamomad/ortiqcha provodkasi, `02-provodka-qoidalari.md` 2.10).
**Xatolar**: `404 TRANSFER_NOT_FOUND`, `409 {code:"TRANSFER_ALREADY_RECEIVED"}`.

### `GET /transfers` · `GET /transfers/{id}`

**Ruxsat**: `stock.view`. Parametr `status?` (`sent`/`received`/`discrepancy`), markirovkalangan tovar bo'lsa `marking_hours_remaining` (72 soat hisoblagich, US-M06-03/BO-03 "Ko'chirishlar" tabi).

### `POST /transfers/{id}/cancel`

**Ruxsat**: `transfer.create`. Faqat `draft`/`sent` (hali qabul qilinmagan) holatda; `received` bo'lgandan keyin bekor qilish taqiqlanadi (`409 {code:"TRANSFER_ALREADY_RECEIVED"}`) — tuzatish uchun yangi teskari ko'chirish yaratiladi.

**Idempotentlik**: `Idempotency-Key` majburiy (yoki offline'da `client_event_id`, pastga qarang).
**Offline**: **ruxsat etilgan** — jo'natish ham, qabul ham (`04-offline-sync.md` §7, markirovkalangan tovar uchun ham, egalik o'zgarmagani uchun). Offline yaratilgan `transfers` bu REST endpoint'lar o'rniga `POST /sync/push` outbox voqeasi (`type: "transfer.created"`/`"transfer.received"`) orqali keladi — server tomoni bir xil `TransferPostingService`, idempotentlik `client_event_id` orqali (`Idempotency-Key` o'rniga). 72 soatlik hisoblagich offline davrni ham qamrab oladi.
**US/Ekran**: US-M06-01…03, BP-09, BO-03.

---

## 14. Inventarizatsiya (`stock-counts`)

### `POST /stock-counts`

**Maqsad**: sanashni boshlash — `counting` holatida, `count_lines` tizimdagi joriy qoldiq (`expected`) bilan oldindan to'ldiriladi.
**Ruxsat**: `stock.count.create`.
Tana: `{warehouse_id, doc_date, product_ids?: UUID[]}` (bo'sh — butun ombor).
**Javob** `201`: `{id, status:"counting", lines:[{product_id, expected, counted:null}]}`.

### `POST /stock-counts/{id}/lines` (skaner kiritish)

**Maqsad**: skaner/qo'lda sonlarni kiritish (POS-10, bir yoki ko'p qator birdan).
**Ruxsat**: `stock.count.create`.
Tana: `{lines: [{product_id, counted, barcode?}]}` — mavjud qatorni yangilaydi yoki (agar `product_id` ro'yxatda yo'q, masalan kutilmagan tovar topildi) yangi qator qo'shadi (`expected=0`).
**Xatolar**: `409 {code:"BARCODE_NOT_IN_CATALOG"}` (POS-10 ekran xato holati).

### `PATCH /stock-counts/{id}/lines/{line_id}`

Bitta qatorni tuzatish (`counted` qiymatini qayta kiritish).

### `POST /stock-counts/{id}/submit-for-review`

`counting→review`. **Ruxsat**: `stock.count.create`.

### `POST /stock-counts/{id}/post`

**Maqsad**: farq bo'yicha balansni moslashtirish (US-M05-02/03) — kamomad `4730`/`5910`, ortiqcha `9300`-oilasi (`02-provodka-qoidalari.md` 2.11).
**Ruxsat**: `stock.count.post` (Egasi/Menejer).
**Javob** `200`: `{status:"posted", shortage_lines:[...], surplus_lines:[...]}`.
**Xatolar**: `409 {code:"STOCK_COUNT_NOT_IN_REVIEW"}`, `409 PERIOD_CLOSED`.

### `POST /stock-counts/{id}/cancel`

**Ruxsat**: `stock.count.post`. Faqat `posted` bo'lgandan keyin — storno (balans orqaga). `counting`/`review` holatda shunchaki hujjatni `cancelled` qilish mumkin (registrga ta'siri yo'q).

### `GET /stock-counts` · `GET /stock-counts/{id}`

**Ruxsat**: `stock.view`.
**Idempotentlik**: `Idempotency-Key` (`post`/`submit-for-review`/`cancel`da majburiy; `lines` skaner kiritishda offline bo'lsa `client_event_id` bilan, pastga qarang).
**Offline**: sanash/skaner (POS-10, `type:"stock_count.line_recorded"` outbox voqeasi) **to'liq offline** ishlaydi — internet talab qilinmaydi; `submit-for-review`/`post` esa online back-office/Menejer amali (yakuniy tasdiqlash).
**US/Ekran**: US-M05-01…03, BP-10, POS-10, BO-03.

---

## 15. Hisobdan chiqarish (`write-offs`)

### `POST /write-offs`

**Ruxsat**: `stock.writeoff`.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `warehouse_id` | UUID | ha | — |
| `doc_date` | date | ha | — |
| `lines[].product_id` | UUID | ha | — |
| `lines[].lot_id` | UUID | ha | FIFO/AVECO uchun aniq partiya |
| `lines[].qty` | decimal(3dp) | ha | ≤ `stock_lots.qty_left` |
| `reason` | enum | ha | `expired`/`damaged`/`gift`/`other` |
| `responsible_user_id` | UUID | yo'q | belgilansa `4730`, aks holda `5910`→`9430` (`02-provodka-qoidalari.md` 2.12) |

**Javob** `201`: `{id, status:"draft", ...}`.

### `POST /write-offs/{id}/post`

Qoldiq −, xarajat (`02-provodka-qoidalari.md` 2.12). Limitdan katta summa `stock.writeoff` `limit_value`siga qarab `pending_approval`ga tushishi — **taxmin, bu endpoint hozircha to'g'ridan-to'g'ri postlaydi, limit tekshiruvi `role_permissions` darajasida 403 qaytaradi** (BO-16 navbatiga chiqarish keyingi bosqich, ochiq savol).
**Ruxsat**: `stock.writeoff`.
**Xatolar**: `409 {code:"WRITE_OFF_QTY_EXCEEDS_LOT"}`, `409 PERIOD_CLOSED`, `403 {code:"WRITE_OFF_LIMIT_EXCEEDED"}` (limitdan katta, PIN tasdiqlanmagan).

### `POST /write-offs/{id}/cancel`

**Ruxsat**: `stock.writeoff`. Tana: `{reason}`.
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q (hozircha faqat online back-office/ombor ilovasi — mobil offline write-off uchun maxsus outbox turi aniqlanmagan, **ochiq savol**).
**US/Ekran**: US-M04-06, BO-03.

---

## 16. Boshlang'ich qoldiq (`stock-openings`)

### `POST /stock-openings`

**Maqsad**: qo'lda (tovar-tovar) boshlang'ich qoldiq kiritish — `import-jobs` (6-bo'lim) orqali ommaviy yo'lning qo'lda muqobili (US-M04-04, 1-yo'l).
**Ruxsat**: `stock.opening.manage`.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `warehouse_id` | UUID | ha | — |
| `doc_date` | date | ha | — |
| `lines[].product_id` | UUID | ha | — |
| `lines[].qty` | decimal(3dp) | ha | > 0 |
| `lines[].unit_cost` | decimal(4dp) | ha | ≥ 0 |
| `lines[].expiry_date` | date | yo'q | — |

### `POST /stock-openings/{id}/post`

Yangi partiya yaratadi, qoldiq +, `Dt 2910 / Kt 8720` (`02-provodka-qoidalari.md` 2.21). Chek/faktura **yo'q**.
**Ruxsat**: `stock.opening.manage`.
**Xatolar**: `409 {code:"STOCK_OPENING_PRODUCT_ALREADY_HAS_STOCK"}` — **yo'q, bu cheklov qo'yilmaydi** (bir mahsulotga bir nechta marta boshlang'ich kiritish mumkin, masalan qo'shimcha partiya); shu sababli bu kod ishlatilmaydi, faqat umumiy validatsiya xatolari.

### `POST /stock-openings/{id}/cancel`

**Ruxsat**: `stock.opening.manage`. Tana: `{reason}`.
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q.
**US/Ekran**: US-M04-04, BO-21.

---

## 17. Baholash va ombor sozlamalari (`valuation-settings`, `stock-settings`)

### `GET /valuation-settings`

**Ruxsat**: `stock.view`.
Javob: `{current_method: "AVECO"|"FIFO", effective_from, pending_change: {method, effective_from}|null}`.

### `PATCH /valuation-settings`

**Maqsad**: FIFO↔AVECO almashtirish (US-M04-05).
**Ruxsat**: `valuation.settings.manage` (yangi kod, Egasi/Buxgalter).
Tana: `{method: "AVECO"|"FIFO"}`.
Server joriy sanani tekshiradi: agar joriy hisobot yili ichida bo'lsa — darhol kuchga **kirmaydi**, `pending_change` sifatida saqlanadi, `effective_from = <keyingi yil 1-yanvar>`; agar so'rov yil boshida (masalan yanvar birinchi kunlari, aniq oyna — taxmin) yuborilsa — darhol qo'llanadi.
**Javob** `200`: `{current_method, pending_change}`.
**Xatolar**: `409 {code:"VALUATION_METHOD_CHANGE_NOT_ALLOWED"}` — agar allaqachon shu yil uchun `pending_change` mavjud bo'lsa (bir yilda bir marta o'zgartirish so'raladi, qayta so'rov eskisini yangilaydi, xato emas — bu kod faqat ikki marta **turli** metodga ketma-ket so'rov yuborilganda, taxmin).
**US/Ekran**: US-M04-05.

### `GET/PATCH /stock-settings`

**Maqsad**: tarozi shtrix-kod formati/versiyasi (US-M09-06), kam qoldiq ogohlantirish standart kuni (US-M04-02/06 — "7 kun qolganda", sozlanadi).
**Ruxsat**: `stock.view` (GET), `catalog.manage` (PATCH).
Maydonlar: `{scale_barcode_prefix: string, scale_barcode_version: int, low_stock_check_enabled: bool, expiry_warning_days: int}`.
**Offline**: `/sync/pull?scope=settings` orqali POS'ga keshlanadi; format versiyasi o'zgarsa majburiy pull (`04-offline-sync.md` §1).

---

## 18. Qayta hisoblash ishlari (`recost-jobs`)

### `GET /recost-jobs`

**Maqsad**: o'tgan sanali hujjat kelganda ishga tushadigan tannarx qayta hisoblash ishlarini kuzatish (`02-provodka-qoidalari.md` 3.3, `09-backend-arxitekturasi.md` §2.4).
**Ruxsat**: `stock.view`.
Parametrlar: `status?` (`queued`/`running`/`done`/`failed`/`rejected_period_closed`), `warehouse_id?`, `product_id?`, `cursor`, `limit`.
Javob: `{items:[{id, warehouse_id, product_id, from_date, status, reason_doc_type, reason_doc_id, attempts, last_error, created_at, finished_at}], next_cursor}`.

### `GET /recost-jobs/{id}`

Bitta ish tafsiloti (tuzatilgan `ledger_entries`/`stock_moves` yozuvlari ro'yxati bilan).

### `POST /recost-jobs/{id}/retry`

**Ruxsat**: `accounting.post` (Buxgalter — ledger'ga ta'sir qiluvchi amal).
Faqat `status="failed"` bo'lgan ishni qayta navbatga qo'yadi (`rejected_period_closed`ni qayta urinib bo'lmaydi — avval davr ochilishi kerak, bu MVP'da mumkin emas, `02-provodka-qoidalari.md` §5.1).
**Xatolar**: `404 RECOST_JOB_NOT_FOUND`, `409 {code:"RECOST_JOB_NOT_RETRYABLE"}`.
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: yo'q.
**US/Ekran**: ochiq — hozircha mustaqil ekran yo'q, BO-03/BO-08 ichida ko'rinishi mumkin (ochiq savol, pastda).

---

## 19. Kiruvchi e-faktura (`einvoices`, `direction=in`)

### `GET /einvoices?direction=in&status=&risk_flag=&cursor=&limit=`

**Maqsad**: BO-15 ro'yxati.
**Ruxsat**: `purchases.post` (Buxgalter).
Javob: `{items:[{id, operator, operator_doc_id, counterparty_id, status, risk_flag, signed_at, amount, vat_amount}], next_cursor}`.

### `GET /einvoices/{id}`

To'liq `payload` (tovar qatorlari, MXIK, QQS) bilan.

### `POST /einvoices/{id}/accept`

**Maqsad**: imzolangan kiruvchi fakturani qabul qilish (operatorga tasdiq yuborish, `03-integratsiyalar.md` §2).
**Ruxsat**: `purchases.post`.
Avval imzolash shart — `sign-challenge`/`submit-signed` (pastda) o'tmagan hujjat uchun `409 {code:"EINVOICE_NOT_SIGNED"}`.
**Javob** `202`: `{status:"queued"}` → `outbox_jobs(kind=einvoice_accept)` → worker orqali operatorga yuboriladi → `status="accepted"` (yashil bo'lsa `vat_moves(kind=input)` darhol; qizil bo'lsa to'lovgacha kutiladi, 11-bo'lim).

### `POST /einvoices/{id}/reject`

**Ruxsat**: `purchases.post`. Tana: `{reason: string}` (majburiy).

### `POST /einvoices/{id}/sign-challenge`

**Maqsad**: E-IMZO imzolash uchun hujjat xeshini (signing payload) qaytarish — brauzer shu payload'ni lokal E-IMZO.exe'ga yuboradi (`03-integratsiyalar.md` §5).
**Ruxsat**: `einvoice.sign`.
**Javob** `200`: `{document_hash: "...", challenge_id: "..."}`.

### `POST /einvoices/{id}/submit-signed`

**Maqsad**: brauzerdan qaytgan PKCS#7 imzoni qabul qilish va tasdiqlash.
**Ruxsat**: `einvoice.sign`.
Tana: `{challenge_id, signature_pkcs7: "<base64>"}`.
**Javob** `200`: `{status:"signed", signed_at}` — `audit_log(action=sign)` yoziladi.
**Xatolar**: `422 {code:"EINVOICE_SIGN_FAILED"}` (imzo tekshiruvi muvaffaqiyatsiz — sertifikat muddati/parol), `409 {code:"EINVOICE_ALREADY_SIGNED"}`, `404 EINVOICE_NOT_FOUND`.
**Idempotentlik**: `Idempotency-Key` majburiy (`accept`/`reject`/`submit-signed`); `document_hash` orqali ham qo'shimcha himoya (bitta hujjat bir necha marta imzolansa, oxirgisi amal qiladi, `03-integratsiyalar.md` §5).
**Offline**: yo'q — imzolash E-IMZO OCSP/TSA tekshiruvi orqali online talab qiladi.
**US/Ekran**: US-M07-03, BP-01, BO-15.

> **Eslatma**: chiquvchi e-faktura (B2B nasiya sotuvdan, BP-03) va chek asosida keyinroq chiquvchi e-faktura (BP-13) — sotuv/qarz katalogida (bu fayl doirasidan tashqarida), chunki ular `sales`/`debts` modulidan tetiklanadi; bu yerda faqat **kiruvchi** (xarid) oqimi.

---

## Ma'lumotlar modeliga kerakli qo'shimchalar

*(`01-malumotlar-modeli.md`ning o'zi tahrirlanmaydi — shu fayl talab qiladigan qo'shimchalar ro'yxati, keyinroq arxitektura jamoasi tomonidan asosiy faylga kiritiladi.)*

1. **Yangi ruxsat kodlari** (`05-xavfsizlik-va-audit.md` §2.1 katalogiga qo'shiladi):
   - `catalog.manage` (M09) — mahsulot/kategoriya CRUD, shtrix-kod/ichki kod yaratish, ombor sozlamalari (`stock-settings`). Standart matritsa: Egasi ✓, Menejer ✓ (xuddi `prices.edit` bilan bir xil rollar).
   - `stock.opening.manage` (M04) — qo'lda `stock-openings` yaratish/posting va `import-jobs(kind=opening_stock|opening_debts)` yaratish/commit. Standart matritsa: Egasi ✓, Menejer ✓.
   - `valuation.settings.manage` (M04/M11) — `valuation-settings` o'zgartirish. Standart matritsa: Egasi ✓, Buxgalter ✓.
2. **`purchase_ocr_drafts` jadvali** (yangi, AI-03 oqimi uchun): `id, tenant_id, created_by, image_attachment_id, status (processing/ready/failed), fields JSONB, low_confidence_fields TEXT[], created_at, expires_at` (taxmin: 7 kun saqlanadi, keyin tozalanadi — vaqtinchalik buferdan boshqa narsa emas, `ai_requests`ga `feature=AI-03` yozuvi alohida saqlanadi).
3. **`supplier_return_lines`ga `reason` qo'shimcha qiymati**: 01-malumotlar-modeli §6 jadvalida `supplier_return_lines`ning `reason` ustuni ko'rsatilmagan — `write_off_lines.reason` bilan bir xil enum (`expired`/`damaged`/`excess`/`other`) qo'shilishi kerak (bu faylda 12-bo'limda ishlatildi).
4. **`goods_receipts`ga ixtiyoriy maydonlar**: `ettn_ref TEXT` (qo'lda e-TTN belgisi, MVP), `poa_number TEXT` (qo'lda ishonchnoma raqami, MVP) — `03-integratsiyalar.md` §3/§6 "qo'lda belgilash" zahira yo'liga mos, avtomatik tekshiruv keyingi bosqich.
5. **`label_templates` jadvali** (yangi, global, `tenant_id`siz, `plans`/`units` kabi RLS istisnosi): `id, name, width_mm, height_mm, fields JSONB` — standart shablonlar seed orqali keladi (US-M09-04).
6. **`import_jobs.kind`ga `opening_debts` allaqachon bor** (`01-malumotlar-modeli.md` §10) — o'zgarish shart emas, faqat shu faylda ishlatilgani qayd etiladi.
7. **`stock_counts`/`write_offs`/`stock_openings`/`supplier_returns`/`transfers` statuslariga umumiy `cancelled_at/cancelled_by/cancel_reason`** — bular hujjat umumiy sarlavhasida (`01-malumotlar-modeli.md` §6) allaqachon bor, qo'shimcha kerak emas (faqat tasdiqlash uchun qayd etildi).

---

## Ishlatilgan xato kodlari

> Umumiy/konventsiyaga oid kodlar (`VERSION_CONFLICT`, `PERIOD_CLOSED`, `IDEMPOTENCY_IN_PROGRESS`, `IDEMPOTENCY_KEY_REUSED`, `CSRF_INVALID`, `SUBSCRIPTION_RESTRICTED`, `VALIDATION_ERROR`, `NOT_FOUND`, `FORBIDDEN`, `RATE_LIMITED`) — `13-api-katalog-0-umumiy.md`da ta'riflangan, bu yerda faqat qayerda ishlatilgani qayd etiladi. Quyida — shu faylga **xos** kodlar.

| Kod | Qayerda | Ma'nosi |
|---|---|---|
| `PRODUCT_NOT_FOUND` | 1 | Mahsulot topilmadi |
| `PRODUCT_ARCHIVED` | 1 | Arxivlangan mahsulotni tahrirlashga urinish |
| `BARCODE_DUPLICATE` | 1 | Shtrix-kod tenant ichida takror |
| `MXIK_CODE_INVALID` | 1 | MXIK format noto'g'ri (17 raqam emas) |
| `MXIK_CODE_NOT_FOUND` | 1 | MXIK kod kesh/tashqi tizimda topilmadi |
| `CATEGORY_NOT_FOUND` | 2 | — |
| `CATEGORY_HAS_PRODUCTS` | 2 | Arxivlanmagan tovarlar bog'langan kategoriyani arxivlash |
| `PRICE_CHANGE_NOT_FOUND` | 4 | — |
| `PRICE_CHANGE_ALREADY_POSTED` | 4 | Qayta `post` chaqirilishi |
| `PRICE_CHANGE_NOT_PENDING` | 4 | `approve`/`reject` faqat `pending_approval`ga |
| `LABEL_TEMPLATE_NOT_FOUND` | 5 | — |
| `IMPORT_FILE_INVALID` | 6 | Fayl formati/kodlash xato |
| `IMPORT_FILE_TOO_LARGE` | 6 | Hajm/qator chegarasidan oshdi |
| `IMPORT_JOB_NOT_VALIDATED` | 6 | `commit` dan oldin `validate` o'tmagan |
| `IMPORT_JOB_ALREADY_COMMITTED` | 6 | Qayta commit |
| `OCR_IMAGE_UNREADABLE` | 8 | AI-03 rasmni tanimadi |
| `AI_UNAVAILABLE` | 8 | Claude API vaqtincha ishlamayapti |
| `OCR_DRAFT_NOT_FOUND` / `OCR_DRAFT_NOT_READY` | 8 | — |
| `SUPPLIER_NOT_FOUND` | 8, 9 | — |
| `PURCHASE_ORDER_CLOSED` | 8, 10 | Yopiq/bekor PO'ga kirim/tahrir |
| `GOODS_RECEIPT_NOT_FOUND` | 8 | — |
| `GOODS_RECEIPT_ALREADY_POSTED` | 8 | — |
| `LOT_ALREADY_CONSUMED` | 8 | Allaqachon chiqim bo'lgan partiyali kirimni bekor qilish |
| `EINVOICE_NOT_FOUND` | 8, 19 | — |
| `EINVOICE_NOT_ACCEPTED` | 8 | Faqat qabul qilingan fakturadan kirim yaratiladi |
| `EINVOICE_NOT_SIGNED` | 19 | `accept`dan oldin imzolanmagan |
| `EINVOICE_ALREADY_SIGNED` | 19 | — |
| `EINVOICE_SIGN_FAILED` | 19 | E-IMZO imzo tekshiruvi muvaffaqiyatsiz |
| `EINVOICE_PROVIDER_UNAVAILABLE` | 9 | Faktura.uz STIR qidiruvi ishlamadi |
| `PURCHASE_ORDER_NOT_FOUND` | 10 | — |
| `SUPPLIER_PAYMENT_EXCEEDS_DEBT` | 11 | Qattiq nazorat yoqilgan tenant'da (ochiq savol) |
| `SUPPLIER_RETURN_NOT_FOUND` | 12 | — |
| `SUPPLIER_RETURN_QTY_EXCEEDED` | 12 | Qaytarish miqdori qolgan partiyadan ko'p |
| `TRANSFER_NOT_FOUND` | 13 | — |
| `TRANSFER_ALREADY_RECEIVED` | 13 | Qabul qilingan ko'chirishni qayta qabul/bekor qilish |
| `BARCODE_NOT_IN_CATALOG` | 14 | Inventarizatsiyada skanerlangan kod katalogda yo'q |
| `STOCK_COUNT_NOT_FOUND` | 14 | — |
| `STOCK_COUNT_NOT_IN_REVIEW` | 14 | `post` faqat `review` holatidan |
| `WRITE_OFF_NOT_FOUND` | 15 | — |
| `WRITE_OFF_QTY_EXCEEDS_LOT` | 15 | — |
| `WRITE_OFF_LIMIT_EXCEEDED` | 15 | Limitdan katta, PIN tasdiqlanmagan |
| `STOCK_OPENING_NOT_FOUND` | 16 | — |
| `VALUATION_METHOD_CHANGE_NOT_ALLOWED` | 17 | Shu yil uchun qarama-qarshi so'rov takrori |
| `RECOST_JOB_NOT_FOUND` | 18 | — |
| `RECOST_JOB_NOT_RETRYABLE` | 18 | `failed`dan tashqari holatni qayta urinish |

---

## Ochiq savollar

1. `write-offs/{id}/post`da limitdan katta summa uchun BO-16 "kutilmoqda" oqimi kerakmi (`price-changes`dagi `pending_approval` kabi), yoki faqat PIN inline tasdiq (POS) yetarlimi — mahsulot hujjatida aniq ko'rsatilmagan (§15).
2. `supplier-payments` summasi joriy kreditorlik qoldig'idan oshganda qattiq bloklash yoki ogohlantirish bilan ruxsat (avans sifatida, `4310`) — buxgalter tasdig'i kerak (§11).
3. Markirovkalangan tovarni yetkazib beruvchiga qaytarishda Asl belgisi operatsiyasi — API yopiq, qaror topilmadi (§12, `02-modullar-talablari.md` M07).
4. Mobil (Android/POS) orqali `write-offs` yaratish offline bo'lishi kerakmi — hozircha faqat online back-office ko'zda tutilgan, maxsus outbox event turi yo'q (§15).
5. `recost-jobs` uchun mustaqil mahsulot ekrani yo'q (04-ekranlar-va-ux.md'da) — BO-03/BO-08 ichida ko'rinishi taklif qilinadi, tasdiqlanishi kerak (§18).
6. `label-print-jobs` serverda PDF generatsiyasi qancha chastota bilan kerak bo'ladi (asosiy yo'l brauzer `bwip-js`) — zahira sifatida qoldirilgan, ustunlik past (§5).

## Manbalar

Fayl boshidagi sarlavha ostida ko'rsatilgan barcha manbalar + `13-api-katalog-0-umumiy.md` (parallel yozilgan konventsiya fayli).
