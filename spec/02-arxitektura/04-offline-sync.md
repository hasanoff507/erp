# Offline sinxronizatsiya

*2026-10-14 · Asos: `research_notes/texnik/04-arxitektura-va-stack.md` (2-, 6-bo'lim), `02-kassa-ofd-markirovka.md` (48 soat, 1-ilova 31-band), `12-taxminlar-va-murojaatlar.md` (6-band, markirovka offline taxmini), `spec/02-arxitektura/01-malumotlar-modeli.md` (`client_event_id`, `sync_receipts`, `devices`, `stock_lots`, `recost_jobs`), `08-frontend-arxitekturasi.md` (Dexie, vite-plugin-pwa, Idempotency-Key), `spec/01-mahsulot/02-modullar-talablari.md` (M01, M02, M04, M08, M16), `04-ekranlar-va-ux.md` (POS-02…POS-15).*

## Asosiy xulosalar

1. Sinxronizatsiya **append-only event-log (outbox naqshi)** asosida, CRDT emas — fiskal chek raqami smena ichida qat'iy ketma-ket bo'lishi shart, bu CRDT'ning "istalgan tartibda birlashish" modeliga mos kelmaydi (`research_notes/texnik/04-arxitektura-va-stack.md`, §2.2).
2. Qurilma (veb-kassa/Android POS) **katalog, narx, mijoz+qarz, limit/huquq va smena** ma'lumotlarini lokal saqlaydi; dastlabki to'liq nusxa (snapshot) + keyin `updated_at`/`version` kursori bo'yicha o'sib boruvchi (delta) yangilanish bilan yangilanadi (1-bo'lim).
3. Har bir lokal amal **outbox voqeasi** (JSON: `client_event_id`, `device_id`, `type`, `created_at`, `payload`, `seq`) sifatida yoziladi; yuklash — `POST /sync/push` (partiyali, idempotent, har voqea uchun alohida natija), yuklab olish — `GET /sync/pull?cursor=` (2-, 3-bo'lim).
4. Rad etilgan voqea **o'chirilmaydi** — lokal outbox'da xato belgisi bilan qoladi, foydalanuvchi uni ko'radi (POS-12) va amal qiladi (qayta urinish, qo'lda tuzatish yoki Menejerga eskalatsiya); boshqa (bog'liq bo'lmagan) voqealar bu orada davom etadi.
5. To'qnashuvlar **delta (harakat) qo'shish** tamoyili bilan hal qilinadi, qiymatni to'g'ridan-to'g'ri almashtirish bilan emas: ombor qoldig'i manfiy bo'lsa ham sotuv **ruxsat etiladi**, qarz limiti oshsa ham sotuv **ruxsat etiladi** — ikkisi ham bayroq (flag) bilan belgilanadi va Egasi/Menejerga bildirishnoma boradi; faqat ma'lumotnoma (reference) maydonlari — ism, telefon, izoh kabilar — `version` ustuni bilan **last-writer-wins** (5-bo'lim).
6. 48 soatlik fiskal muddat (`02-kassa-ofd-markirovka.md`, 1-ilova 31-band) — taymer birinchi offline voqea yaratilgan paytdan boshlanadi; 24/40 soatda ogohlantirish (**taxmin**, aniq soat manbada yo'q) qo'yilgan, lekin 48 soatda **yangi sotuvni bloklash qonunda topilmadi** — shu sabab bloklash emas, majburiy eskalatsiya + audit belgisi taklif qilinadi (6-bo'lim, ochiq savol).
7. Markirovkalangan tovar offline sotuvi — `12-taxminlar-va-murojaatlar.md` (6-band) ishchi taxminiga ko'ra **vaqtincha cheklanadi, ogohlantirish bilan** (taqiq emas, lekin tavsiya — kechiktirish); internet qaytganda kod avtomatik tekshiriladi (7-bo'lim).
8. Veb-kassada bir nechta tab ochilishi xavfli (ikki tab bitta lokal `seq` raqamini ikki marta bersa) — **Web Locks API** bilan yagona yozuvchi tab saylanadi, **BroadcastChannel** bilan holat (online/offline, yangi ma'lumot) boshqa tablarga tarqatiladi (10-bo'lim).
9. Lokal ma'lumot shifrlanishi brauzerda OS darajasida (disk shifrlash tavsiyasi) + chiqishda (logout) Dexie bazasi to'liq tozalanadi; Android'da (keyingi bosqich) SQLCipher bilan butun Room bazasini shifrlash tavsiya etiladi (`10-android-pos.md`) (11-bo'lim).
10. Test strategiyasi — tarmoq xatosi, soat farqi, ikki qurilmaning bir vaqtda to'qnashuvi, qayta yuborilgan voqea (duplicate), qurilma bekor qilinishi kabi stsenariylar uchun **chaos/tarmoq testlari** (Playwright network emulation, MSW) (12-bo'lim).

---

## 1. Qurilmada saqlanadigan ma'lumotlar va yangilash

| Ma'lumot toifasi | Lokal jadval (Dexie, veb) | Dastlabki yuklash | Yangilanish usuli |
|---|---|---|---|
| Katalog (`products`, `product_categories`, `units`) | `catalog` | To'liq snapshot, login/qurilma ro'yxatdan o'tganda | Delta: `GET /sync/pull?scope=catalog&cursor=<updated_at,id>` |
| Shtrix-kodlar (`product_barcodes`) | `barcodes` | To'liq snapshot | Delta, `cursor` bo'yicha |
| Narxlar (`product_prices`, faqat amaldagi) | `prices` | To'liq snapshot (faqat joriy, tarix emas) | Delta |
| Mijozlar + qarz balansi (`counterparties`, `debt_balances`) | `customers` | To'liq snapshot (shu filialga tegishli/umumiy) | Delta — balans qiymati serverda hisoblanadi, qurilma faqat o'qiydi |
| Limitlar (kredit limiti, chegirma/qaytarish limiti — `role_permissions.limit_value`, `counterparties.credit_limit`) | `limits` | Katalog bilan birga | Delta |
| Huquqlar (`role_permissions`, `memberships`) | `permissions` | Login paytida to'liq | Delta; o'zgarsa darhol pull (login session yangilanishi) |
| Joriy smena (`shifts`) | `shift` | Smena ochilganda yaratiladi (lokal) | Push orqali serverga, server tasdiqlagandan keyin doimiy holatga o'tadi |
| Outbox (chek, qaytarish, qarz to'lovi, kassa harakati) | `outbox` | — | Faqat push (2-bo'lim) |
| Do'kon sozlamalari va qoidalar (`tenants.settings`: tarozi shtrix-kod formati va uning versiyasi; faol `discount_rules`; obuna holati `subscriptions.status`) | `settings` | Login/snapshot bilan | Delta; tarozi formati versiyasi o'zgarsa majburiy pull *(2026-10-14: tekshiruv)* |

**Dastlabki to'liq nusxa (snapshot)**: qurilma birinchi marta ro'yxatdan o'tganda (`devices` yozuvi yaratilganda) yoki lokal baza tozalanganda (`GET /sync/pull?scope=all&cursor=` bo'sh kursor bilan) — sahifalab (`page_size`, **taxmin: 500 qator/sahifa**) yuklanadi, `has_more=true` bo'lsa davom etiladi.

**Delta yangilanish**: har bir jadvalda `updated_at` (yoki ma'lumotnomalarda `version`) bo'yicha kursor; qurilma oxirgi ko'rgan `(updated_at, id)` juftligini saqlaydi va keyingi so'rovda yuboradi (sahifalashda barqaror tartib uchun ikkilik kursor — faqat `updated_at` bilan bir xil millisekundda bir nechta yozuv bo'lsa tartib buzilmasligi uchun). Chastota — veb-kassa fon rejimida har **5 daqiqada** (taxmin) + internet qaytganda darhol + `pageMounted`/smena ochilganda majburiy.

---

## 2. Outbox voqea formati (JSON schema)

```json
{
  "client_event_id": "018f2c3a-9b7e-7a41-8e2f-6b1a2c3d4e5f",
  "device_id": "018f2c2e-11aa-7b00-9c3d-aa11bb22cc33",
  "seq": 142,
  "type": "sale.created",
  "created_at": "2026-10-14T09:12:03.482+05:00",
  "actor_user_id": "018f2c3a-aa11-7b00-9c3d-aa11bb22cc33",
  "payload": { "...": "hujjat turiga mos tuzilma, quyida" }
}
```

| Maydon | Tur | Izoh |
|---|---|---|
| `client_event_id` | UUIDv7 | Qurilmada yaratiladi (`01-malumotlar-modeli.md` §2 — vaqt bo'yicha tartiblangan); `sync_receipts.client_event_id` bilan idempotentlik ta'minlanadi |
| `device_id` | UUIDv7 | `devices` jadvaliga mos, ro'yxatdan o'tgan qurilma |
| `seq` | integer | Qurilma ichidagi lokal monoton ketma-ket raqam (restart/qayta ishga tushirishda ham davom etadi, lokal bazada saqlanadi) — server global tartib emas, faqat shu qurilma ichidagi nisbiy tartibni tasdiqlash uchun ishlatadi |
| `type` | enum | `shift.opened`, `shift.closed`, `sale.created`, `sale.draft_voided` (to'lovdan oldin chek/qator bekor qilish — audit, registrga ta'sir yo'q), `receipt.reprinted` (chekni qayta chop etish — audit), `return.created`, `debt_payment.created`, `cash_movement.created`, `stock_count.line_recorded` (M05, mobil rejim) — to'liq ro'yxat `09-backend-arxitekturasi.md`da yakunlanadi (**ochiq savol**) *(2026-10-14: tekshiruv)* |
| `created_at` | ISO 8601, qurilma soati | Fiskal 48-soat hisobi va buxgalteriya sanasi shu maydondan olinadi (8-bo'lim, soat farqi) |
| `actor_user_id` | UUID | Amalni bajargan kassir (offline PIN bilan kirgan); server uning `created_at` paytida faol membership'ini tekshiradi; push qilgan sessiya foydalanuvchisi farq qilsa, ikkalasi audit'ga yoziladi *(2026-10-14: tekshiruv)* |
| `payload` | object | Hujjat turiga mos (masalan `sale.created` uchun `sales` + `sale_lines` + `sale_payments`, `01-malumotlar-modeli.md` §6 tuzilishiga mos); `sale.created`da `fiscal.receipt_seq` — qurilma beradi (3.3-bo'lim) *(2026-10-14: tekshiruv)* |

Qarzga sotish alohida voqea turi emas — `sale.created` ichida `sale_payments.method = "debt"` sifatida yuboriladi (US-M08-01, US-M08-05); qarz daftaridagi tezkor yozuv (POS-13) ham shu yo'l bilan amalga oshadi.

---

## 3. Yuklash protokoli

### 3.1 `POST /sync/push`

```json
// So'rov
{
  "device_id": "018f2c2e-...",
  "events": [
    { "client_event_id": "...", "seq": 141, "type": "sale.created", "created_at": "...", "payload": {...} },
    { "client_event_id": "...", "seq": 142, "type": "return.created", "created_at": "...", "payload": {...} }
  ]
}
```

```json
// Javob
{
  "results": [
    { "client_event_id": "...", "status": "accepted", "server": { "id": "...", "number": "K-01-2026-000154" } },
    { "client_event_id": "...", "status": "rejected", "error_code": "SALE_NOT_FOUND", "message": "Asl chek hali sinxronlanmagan", "retryable": true }
  ]
}
```

- **Partiya hajmi**: taxmin — 50 voqea/so'rov (katta hujjat ro'yxatlari uchun kam, tarmoq kechikishi uchun ko'p emas); aniq raqam yuklama sinovida tasdiqlanadi.
- **Idempotentlik**: server har bir `client_event_id`ni `sync_receipts`da tekshiradi (`01-malumotlar-modeli.md` §10). Oldin qabul qilingan voqea qayta yuborilsa — `status: "duplicate"`, bir xil natija (server raqami) qaytariladi, ikkinchi marta yozilmaydi.
- **Fiskal raqam**: `receipt_seq` qurilmadan keladi; server uni o'zgartirmaydi, faqat `UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)` bilan tekshiradi. Takror — `rejected`, `error_code: RECEIPT_SEQ_CONFLICT`, `retryable: false` (eskalatsiya). *(2026-10-14: tekshiruv)*
- **Partiya "hammasi yoki hech narsa" emas** — har voqea alohida tranzaksiyada qayta ishlanadi; bittasi rad etilsa, qolganlari (bog'liq bo'lmasa) baribir qabul qilinadi (`results` massivi buni ko'rsatadi).

### 3.2 `GET /sync/pull?cursor=<token>&scope=catalog,prices,customers,permissions&page_size=500`

```json
{
  "cursor": "eyJ1cGRhdGVkX2F0IjoiMjAyNi0xMC0xNFQw...",
  "has_more": false,
  "catalog": [ { "id": "...", "name": "...", "updated_at": "..." } ],
  "prices": [ ... ],
  "customers": [ { "id": "...", "name": "...", "receivable_balance": 350000, "credit_limit": 500000, "version": 4 } ]
}
```

`receivable_balance` = `debt_balances.balance WHERE direction='receivable'` (yozuv bo'lmasa 0; musbat son mijoz bizga qarzdor ekanini bildiradi). `payable` kassaga yuborilmaydi. *(2026-10-14: tekshiruv)*

### 3.3 Tartib kafolatlari

- Bitta qurilma ichida voqealar **har doim `seq` tartibida** yuboriladi va shu tartibda serverga yetib boradi (bir partiya ichida massiv tartibi saqlanadi).
- **Bog'liq voqealar** (masalan `return.created` o'zi tegishli `sale.created`ga bog'liq, agar asl chek hali sinxronlanmagan bo'lsa): server `SALE_NOT_FOUND` + `retryable: true` qaytaradi; qurilma bu voqeani keyingi push'da qayta yuboradi, lekin undan **keyingi, bog'liq bo'lmagan** voqealarni bloklamaydi.
- Qoldiq/qarz kabi **delta-asosida** registrlar (`stock_moves`, `debt_moves`) uchun qat'iy global tartib shart emas — harakatlar qo'shiladi, tartib natijaga ta'sir qilmaydi (`04-arxitektura-va-stack.md`, §2.3).
- Fiskal chek raqami (`fiscal_receipts.receipt_seq`) — **qurilma beradi** (offline ham), outbox `seq` bilan bir Web Lock ichida; kassa + smena ichida ketma-ket. **Bitta smena — bitta qurilma** (`shifts.device_id`): boshqa qurilmadan shu smenaga voqea `rejected SHIFT_DEVICE_MISMATCH`. *(2026-10-14: tekshiruv)*

### 3.4 Server validatsiyasi va rad etish

Server har bir voqeani: (1) sxema (JSON shakli, majburiy maydonlar), (2) qurilma/tenant autentifikatsiyasi (`device_id` faol va shu tenant'ga tegishlimi), (3) idempotentlik (`sync_receipts`), (4) biznes qoidalari (5-bo'lim to'qnashuv jadvali) bo'yicha tekshiradi.

**Rad etilganda**: voqea serverga yozilmaydi, lekin **qurilmadagi outbox'dan o'chirilmaydi** — `rejected` holatida, xato kodi va xabar bilan saqlanadi. POS-12 ekranida ("Sinxronlanmagan hujjatlar") bu voqea qizil belgi va aniq xato matni bilan ko'rinadi. Foydalanuvchi amali: (a) `retryable: true` bo'lsa — avtomatik/qo'lda qayta urinish, (b) `retryable: false` (masalan doimiy validatsiya xatosi) — qo'lda tuzatish yoki Menejerga/qo'llab-quvvatlashga eskalatsiya; hujjat hech qachon jim o'chirilmaydi (audit yaxlitligi uchun).

**401 (sessiya tugagan)** — rad etish emas: voqealar `pending` holatida qoladi, `rejected` bo'lmaydi; push to'xtatiladi. POS ustida qayta kirish oynasi (parol yoki PIN) ochiladi, bunda **Dexie tozalanmaydi** — bu logout emas. Qayta kirishda server yangi sessiyani avvalgi `device_id`ga bog'laydi (boshqa tenant/qurilma bo'lsa push'ga ruxsat yo'q), keyin push `seq` tartibida davom etadi. `403 device_revoked` — 9-bo'lim. Veb-kassa uchun alohida qurilma tokeni/cookie yo'q — offline davr server autentifikatsiyasini talab qilmaydi (lokal PIN, 12-bo'lim), sessiya mutlaq muddati (7 kun) 48 soatdan uzun. Qurilma tokeni (Bearer) faqat Android uchun (`05-xavfsizlik-va-audit.md` §1.3). Veb-kassaning cookie-autentifikatsiyali so'rovlari (shu jumladan `/sync/push`/`/sync/pull`) `X-CSRF-Token` talab qiladi (`05-xavfsizlik-va-audit.md` §1.3). *(2026-10-14: tekshiruv)*

---

## 4. Diagrammalar

### 4.1 Onlayn sotuv

```mermaid
sequenceDiagram
    participant K as Kassir (POS-02/03/04)
    participant L as Lokal baza (Dexie)
    participant API as Backend API
    participant DB as PostgreSQL
    participant WK as Worker
    participant OFD as OFD

    K->>L: Chekni yakunlash (client_event_id = UUIDv7)
    L->>L: Outbox'ga yozish (seq+1, type=sale.created)
    L->>API: POST /sync/push {events:[sale.created]}
    API->>DB: Bitta tranzaksiya: hujjat + stock_moves + debt_moves + ledger_entries
    DB-->>API: OK (id, number)
    API-->>L: results: [{status: accepted, server:{id, number}}]
    API->>WK: outbox_jobs: ofd_send navbatga qo'yiladi
    WK->>OFD: Fiskal chekni yuborish
    OFD-->>WK: Fiskal belgi + QR
    WK->>DB: fiscal_receipts.status = "fiscalized"
    L->>K: Chek fiskal belgi/QR bilan chop etiladi (keyingi pull'da yoki push javobida)
```

### 4.2 Offline sotuv + keyinroq sinxron

```mermaid
sequenceDiagram
    participant K as Kassir
    participant L as Lokal baza (outbox)
    participant API as Backend API
    participant DB as PostgreSQL

    Note over K,L: Internet yo'q — status 🔴/🟡
    K->>L: Chek 1 (seq=141) — offline belgisi bilan
    Note over L: 48 soatlik taymer shu voqeadan boshlanadi
    K->>L: Chek 2…7 (seq=142..147)
    Note over K,L: Internet qaytdi
    L->>API: POST /sync/push {events: seq 141..147, xronologik tartibda}
    API->>DB: Har voqea: sync_receipts tekshiruvi → tranzaksiya
    DB-->>API: natijalar
    API-->>L: results[7] — hammasi "accepted", server id/number
    L->>L: "accepted" voqealar outbox'da 7 kun saqlanadi (taxmin), keyin tozalanadi
    API->>API: outbox_jobs: ofd_send (48 soatlik deadline bilan)
```

### 4.3 Rad etilgan voqea

```mermaid
sequenceDiagram
    participant K as Kassir
    participant L as Lokal baza
    participant API as Backend API
    participant DB as PostgreSQL

    L->>API: POST /sync/push {events:[return.created, seq=89]}
    API->>DB: Asl chek (sale) qidiriladi
    DB-->>API: Topilmadi (hali sinxronlanmagan)
    API-->>L: {status: rejected, error_code: SALE_NOT_FOUND, retryable: true}
    L->>L: Voqea outbox'da "xato" belgisi bilan qoladi (o'chirilmaydi)
    L->>K: POS-12: "Qaytarish — asl chek topilmadi. Qayta urinilmoqda / Menejerga murojaat"
    Note over K: Foydalanuvchi: kutish (avtomatik qayta urinish) yoki qo'lda eskalatsiya
```

---

## 5. To'qnashuv (konflikt) qoidalari

| Stsenariy | Qoida | Manba |
|---|---|---|
| Ombor qoldig'ida overselling (ikki qurilma oxirgi donani oflaynda sotgan) | Sotuv **ruxsat etiladi**; qoldiq manfiy bo'lishi mumkin, `stock_balances`ga manfiy qiymat yoziladi, BO-03'da "⚠ manfiy qoldiq" belgisi; tannarx `pending_cost` sifatida oxirgi ma'lum narxda, keyingi kirimda qayta hisoblanadi | `01-malumotlar-modeli.md` §7; `04-arxitektura-va-stack.md` §2.3 |
| Qarz limiti offline oshib ketgan | Sotuv **ruxsat etiladi** (allaqachon bo'lib o'tgan); server qayta tekshiradi, `limit_exceeded=true` bayrog'i qo'yiladi, Egasi/Menejerga M18 orqali bildirishnoma | US-M08-01; `04-arxitektura-va-stack.md` §2.3 |
| Narx offline o'zgargan (server narxi yangilangan, qurilma eski narxda sotgan) | Chekdagi narx **"qotiriladi"** — avtomatik tuzatilmaydi; farq Buxgalter ko'rib chiqadigan **istisno** sifatida belgilanadi | M09 chekka holatlar (`02-modullar-talablari.md`); `04-arxitektura-va-stack.md` §2.3 |
| Mahsulot offline sotuv vaqtida arxivlangan (serverda keyin arxivlangan, qurilma bilmagan) | Hujjat **qabul qilinadi** (tovar sotuv vaqtida faol edi); "arxivlangan tovar bilan yozilgan" bayrog'i, Menejerga ko'rinadi, bloklanmaydi | Qat'iy siyosat **ochiq savol** (pastda) |
| Bir xil mijoz ikki joyda tahrirlangan (ism/telefon/izoh) | **Last-writer-wins**, `counterparties.version` bilan optimistik qulflash; kech kelgan `client_event_id` server qabul vaqti bo'yicha g'olib, eski qiymat `audit_log`ga | `01-malumotlar-modeli.md` §1 (`version INT`) |
| Mijoz qarz balansi/kredit limiti | **Hech qachon LWW emas** — balans faqat `debt_moves` delta sifatida qo'shiladi (konflikt yo'q, hisoblanadigan registr); limit maydoni (reference) — LWW + version | `01-malumotlar-modeli.md` §7 |
| Smena bir vaqtda ikki joyda yopilmoqchi (nazariy) | Server tomonida `shifts.status` optimistik tekshiruv bilan himoyalanadi — ikkinchisi "smena allaqachon yopilgan" xatosi oladi | Amaliyotda kam uchraydi (bitta smena — bitta qurilma) |
| Qaytarish yoki chegirma limiti offline oshgan | Sotuvdan farqli — **lokal Menejer/Egasi PIN'isiz yakunlanmaydi** (BO-16 offline ishlamaydi); PIN bilan tasdiqlangan bo'lsa server qabul qiladi va qayta tekshiradi, `limit_exceeded=true` bayrog'i + M18 xabar *(2026-10-14: tekshiruv)* | `05-xavfsizlik-va-audit.md` §2.3 |

---

## 6. Fiskal 48 soat qoidasi

- **Huquqiy asos**: VM 943-son qarori, 1-ilova, 31-band — offline rejimda shakllangan birinchi chek **48 soat ichida** OFD'ga yetib borishi shart (`research_notes/texnik/02-kassa-ofd-markirovka.md`, §1).
- **Taymer**: birinchi offline voqea (`created_at`, qurilma soati) yaratilgan paytdan boshlanadi — "chek yaratilgan payt, OFD'ga yetib borish payti emas" (`04-arxitektura-va-stack.md`, §2.2, 3-band). Har bir uzluksiz offline davr uchun alohida taymer; internet qaytib hammasi sinxronlanganda taymer to'xtaydi.
- **Ogohlantirishlar**: 24 soatda birinchi signal, 40 soatda ikkinchi (kuchli) signal (**taxmin** — aniq soat manbada yo'q, `04-ekranlar-va-ux.md` §1.3 ham shu holatni "taxmin" deb belgilagan; maqsad — muddat tugashidan oldin kamida ikki marta ogohlantirish, M18 orqali Egasiga ham).
- **48 soatda yangi sotuvni bloklash — ochiq savol**: qonun matnida (1-ilova 31-band) faqat "chek 48 soat ichida yetib borishi zarur" deyilgan, yangi sotuvni to'xtatish talabi **topilmadi**. **Taklif**: yangi sotuvni **bloklamaslik** (do'kon ishini to'xtatish mijozga xizmat ko'rsatish va boshqa huquqiy/biznes xavflarni kuchaytiradi), lekin 48 soat chegarasi buzilganda: (1) audit_log'ga qat'iy huquqiy-xavf yozuvi, (2) Egasiga Telegram orqali zudlik bilan xabar (M18), (3) back-office'da doimiy ko'rinadigan "huquqiy xavf" bayrog'i. Bu band — `12-taxminlar-va-murojaatlar.md` (6-band) kabi — yakuniy huquqiy maslahat bilan tasdiqlanishi kerak.
- **Hisob-kitob asosi**: taymer qiymati `created_at` (qurilma soati) asosida hisoblanadi, lekin 8-bo'limdagi soat farqi qoidalari bilan himoyalanadi (soatni "orqaga surish" orqali muddatni cho'zishga urinishning oldini olish uchun).

---

## 7. Markirovkalangan tovar — offline siyosati

Ishchi taxmin (`research_notes/texnik/12-taxminlar-va-murojaatlar.md`, 6-band; `04-arxitektura-va-stack.md` §2.4): markirovka (Asl belgisi/CRPT Turon) kodini offline tekshirish **mumkin emas** (markaziy tizimga bog'liq). Shu sabab:

- Offline holatda markirovkalangan tovar skanerlanganda, kassir kodni **kiritadi**, lekin tizim "chiqarish" (spisaniye) amalini **kechiktiradi** — chekka "⚠ markirovka tekshirilmagan, internet qaytganda tasdiqlanadi" belgisi qo'yiladi (POS-02/08/09/10, `04-ekranlar-va-ux.md` §1.7, §1.3).
- Sotuvning o'zi **bloklanmaydi** (taqiq emas, ogohlantirish bilan ruxsat) — kassir sotuvni davom ettirishi yoki (agar vaqti bo'lsa) internet kutib keyinroq sotishni tanlashi mumkin; qaror kassirga qoldiriladi, tizim faqat ogohlantiradi.
- Internet qaytganda, synced bo'lgan `sale.created` voqeasidagi markirovka kodlari fon rejimida (worker, `outbox_jobs.kind="marking_sell"`) CRPT Turon'ga yuboriladi; kod noto'g'ri/takroriy chiqsa — Egasi/Menejerga ogohlantirish (bu holatda tovar allaqachon sotilgan, orqaga qaytarib bo'lmaydi — faqat qayd va keyingi tekshiruv uchun belgi).
- **Qat'iy taqiq siyosati rasmiy manbada tasdiqlanmagan** — bu taxmin, huquqiy maslahat bilan yakunlanishi kerak (`02-modullar-talablari.md`, US-M01-03; `04-ekranlar-va-ux.md`, Ochiq savol #3).

---

## 8. Soat farqi (clock skew)

- Qurilma soati noto'g'ri bo'lishi mumkin (batareya, qo'lda o'zgartirish). Server har API javobida `Date` sarlavhasini yuboradi; qurilma internetga ulanganda o'z soatini server bilan solishtiradi.
- Farq **taxmin: 5 daqiqadan** oshsa — qurilma UI'da ogohlantirish ko'rsatadi ("Qurilma soati noto'g'ri, sinxronlang") va `audit_log`ga yoziladi.
- **48 soatlik hisob-kitobda firibgarlikdan himoya**: agar `created_at` (qurilma soati) server qabul qilish vaqtidan (`received_at`) ancha oldin bo'lsa va bu farq amaldagi offline sessiya davomiyligidan katta bo'lsa (ya'ni soat "orqaga surilgan" bo'lishi mumkin) — server `created_at`ni **qisqartiradi** (clamp: `max(created_at, received_at - taxminiy_offline_oyna)`) va holatni audit uchun belgilaydi, shunda qurilma soatini o'zgartirib 48 soatlik muddatni cho'zib bo'lmaydi.
- Ikki yo'nalishda ham (orqaga va oldinga surish) xom `created_at` va tuzatilgan qiymat alohida saqlanadi — tekshiruv/audit uchun.

---

## 9. Qurilmani ro'yxatdan o'tkazish va bekor qilish

- Qurilma birinchi marta login qilganda `devices` yozuvi avtomatik yaratiladi (`tenant_id`, `cash_register_id`, `kind`, `app_version`) — kichik do'kon uchun qo'shimcha tasdiqlash qadam qo'shilmaydi (tezkor ishga tushirish).
- Egasi/Menejer qurilmalar ro'yxatini ko'radi va kerak bo'lsa **bekor qiladi** (masalan o'g'irlangan/eskirgan qurilma) — aniq ekran hozircha `04-ekranlar-va-ux.md`da yo'q, **ochiq savol** (pastda).
- **Bekor qilingan qurilma**: keyingi `POST /sync/push` va `GET /sync/pull` so'rovlari `403 device_revoked` bilan rad etiladi. Lokal outbox'dagi hali yuborilmagan hujjatlar **jim yo'qolmaydi** — UI "Qurilma bloklandi, ma'lumotlarni eksport qiling" xabarini ko'rsatadi va Excel eksport imkoniyatini beradi (qog'oz chekka tushgan savdoni yo'qotmaslik uchun), shundan keyingina lokal baza tozalanadi. Aniq UX oqimi **ochiq savol**.
- Qurilma bekor qilinganda shu qurilmada oxirgi 30 kun (taxmin) ichida PIN bilan kirgan barcha xodimlarning PIN'i serverda bekor qilinadi va keyingi kirishda yangi PIN majburiy (lokal 4 raqamli PIN hashlari offline buzilishi oson). Ro'yxat va "Bekor qilish" — BO-11 "Qurilmalar" tabi. Ochiq savol 3 qisman hal qilindi. *(2026-10-14: tekshiruv)*

---

## 10. Saqlash chegaralari va tozalash

- Katalog/narx/mijoz keshlari — delta-sync bilan doimiy yangilanadi, qo'lda tozalash shart emas (hajm tenant ma'lumot hajmiga bog'liq).
- Outbox voqealari — `accepted`/`duplicate` natija olgandan keyin darhol o'chirilmaydi, **taxmin: 7 kun** xavfsizlik buferi bilan saqlanadi (foydalanuvchi ko'rib chiqishi/eksport qilishi uchun), keyin avtomatik tozalanadi.
- Sotuv/chek tarixi (UI ko'rsatish uchun lokal kesh) — **taxmin: 90 kunlik** aylanma oyna; eskisi serverdan talab bo'yicha olinadi (online bo'lganda).
- Brauzer IndexedDB hajmi/tozalanishi (ayniqsa Safari/iOS'da ITP agressiv tozalashi) sababli **veb-kassa faqat Chromium**: Chrome/Edge (desktop) va Android Chrome, o'rnatilgan PWA sifatida; ishga tushganda `navigator.storage.persist()` so'raladi. Safari/iOS veb-kassa uchun qo'llab-quvvatlanmaydi (IndexedDB tozalanish xavfi, WebUSB/Web Serial yo'q). Back-office — barcha zamonaviy brauzerlar (`08-frontend-arxitekturasi.md` Ochiq savol #2 qarori). *(2026-10-14: tekshiruv)*

---

## 11. Ko'p-tab xavfsizligi (veb)

- Bitta foydalanuvchi veb-kassani ikki tab'da ochishi mumkin — bu lokal `seq` raqamini ikki marta berish va outbox'ga ikki marta yozish xavfini keltiradi.
- **Yechim**: `navigator.locks.request("aios-outbox-writer", async () => { ... })` (Web Locks API) bilan outbox'ga yozish + `seq` oshirish + sync push triggeri **yagona qulf** ichida bajariladi — faqat bitta tab bir vaqtda yozuvchi bo'ladi, boshqalari navbatda kutadi (yozish tezkor bo'lgani uchun UI kechikishi sezilmaydi).
- **`BroadcastChannel("aios-sync")`** — barcha tablarga: online/offline holat o'zgarishi, yangi pull natijasi (katalog/narx yangilandi — UI qayta render qilsin), outbox holati o'zgarishi (boshqa tab POS-12'da ko'rsatadigan ro'yxatni yangilash uchun) xabar qiladi.
- Faqat o'qish (masalan BO-03 qoldiqni ko'rish) alohida qulf talab qilmaydi — IndexedDB o'qish operatsiyalari tabiatan xavfsiz.

---

## 12. Lokal ma'lumot xavfsizligi

- **Veb (Dexie/IndexedDB)**: brauzer IndexedDB'ni o'zi shifrlamaydi — maxfiylik asosan OS/profil darajasidagi sandboxing va **OS disk shifrlashi** (BitLocker/FileVault, tashkiliy siyosat sifatida tavsiya) orqali ta'minlanadi, ilova darajasidan majburlab bo'lmaydi.
- **Logout** — Dexie bazasi to'liq o'chiriladi (`Dexie.delete()` / `indexedDB.deleteDatabase`), shu jumladan mijoz telefon raqami, qarz balansi keshi va outbox (agar hammasi sinxronlangan bo'lsa; sinxronlanmagan bo'lsa ogohlantirish bilan eksport taklif qilinadi, 9-bo'limdagi kabi).
- **Offline PIN login** (internet yo'qligida kassaga kirish) — faqat salt bilan heshlangan PIN lokal saqlanadi, muvaffaqiyatsiz urinishlar soni cheklanadi (**taxmin: 5 urinish**), oshsa qurilma vaqtincha bloklanadi.
- **Android (keyingi bosqich)** — `10-android-pos.md`da batafsil: butun Room bazasini **SQLCipher** bilan shifrlash tavsiya etiladi (yoki Android Keystore asosida maydon darajasida shifrlash, agar SQLCipher xarajati ortiqcha topilsa).
- Karta/to'lov ma'lumotlari (PAN, CVV) hech qachon qurilmada saqlanmaydi — to'lov terminali/bank SDK'si orqali to'g'ridan-to'g'ri ishlanadi, bu tizim faqat tranzaksiya natijasi (muvaffaqiyat/summasi) bilan ishlaydi.

---

## 13. Testlash strategiyasi

| Test turi | Nima tekshiriladi | Vosita |
|---|---|---|
| Tarmoq emulyatsiyasi (chaos) | Online↔offline↔online tez almashinuvi, sekin 3G, uzilish o'rtada | Playwright network conditions (`08-frontend-arxitekturasi.md` testlar ro'yxati) |
| Idempotentlik | Bir xil `client_event_id` ikki marta yuborilsa — ikkinchi marta yozilmasligi, `duplicate` natija | MSW bilan backend simulyatsiyasi + backend integratsion test |
| Ikki qurilma to'qnashuvi | Ikki kassa bir vaqtda oxirgi donani oflaynda sotadi — ikkisi ham qabul qilinadi, qoldiq manfiy va bayroqlanadi | Backend integratsion test (parallel push) |
| 48 soat chegarasi | Simulyatsiya qilingan 50 soatlik offline davr — 24/40 soat ogohlantirish, 48 soatda audit bayrog'i to'g'ri ishga tushishi | Vaqtni soxtalashtiruvchi (fake clock) unit/integratsion test |
| Soat farqi | Qurilma soati +3 kun qilib qo'yilganda, server `created_at`ni to'g'ri "clamp" qilishi | Backend unit test |
| Ko'p-tab | Ikki tab ochilganda faqat bittasi yozuvchi bo'lishi, `seq` takrorlanmasligi | Playwright (ikki context, bitta profil) |
| Qurilma bekor qilinishi | Push/pull sinxronida qurilma bekor qilinsa `403` va UI eksport taklifi | E2E test + backend test |
| Rad etilgan voqea oqimi | `retryable`/`non-retryable` xatolar UI'da to'g'ri ko'rsatilishi, boshqa voqealarni bloklamasligi | Playwright + MSW |

Backend tomonida `/sync/push` va `/sync/pull` uchun OpenAPI sxemasiga mos kontrakt testlari (`09-backend-arxitekturasi.md`da belgilanadi) va worker→OFD orasidagi kechikish/uzilishni simulyatsiya qiluvchi chaos-vosita (masalan toxiproxy) tavsiya etiladi — aniq vosita tanlovi backend hujjatida.

---

## Ochiq savollar

1. 48 soatda yangi sotuvni bloklash yoki faqat ogohlantirish — qonunda aniq topilmadi, taklif (6-bo'lim) huquqiy maslahat bilan tasdiqlanishi kerak.
2. Markirovkalangan tovarni offline sotish siyosati (cheklash/ogohlantirish) — rasmiy manbada tasdiqlanmagan taxmin (7-bo'lim, `12-taxminlar-va-murojaatlar.md` 6-band).
3. Qurilmani bekor qilish UX oqimi (qaysi ekranda, kim bekor qiladi, eksport jarayoni) — mahsulot ekranlarida hali yo'q (9-bo'lim).
4. ~~Bitta smenani ikki qurilma baham ko'rganda fiskal chek raqamlash tartibi.~~ **Yopildi**: bitta smena — bitta qurilma (`shifts.device_id`, 3.3-bo'lim). *(2026-10-14: tekshiruv)*
5. Aniq partiya hajmi (`/sync/push` necha voqea), `page_size` (`/sync/pull`), delta-sync chastotasi, outbox saqlash muddati (7 kun), chek tarixi oynasi (90 kun), PIN urinish soni (5) — barchasi **taxmin**, yuklama sinovida/pilotda aniqlanadi.
6. Chekdagi narx yoki arxivlangan tovar istisnolarini Buxgalter qanday "yopish" (tasdiqlash) jarayoni — UI darajasida hali loyihalashtirilmagan.

## Manbalar

- `research_notes/texnik/04-arxitektura-va-stack.md` — §2 (offline-first, event-log, konflikt), §6 (davlat hisoboti, bevosita bog'liq emas, lekin arxitektura uslubi).
- `research_notes/texnik/02-kassa-ofd-markirovka.md` — §1 (48 soat, 1-ilova 31-band; OFD, fiskal modul).
- `research_notes/texnik/12-taxminlar-va-murojaatlar.md` — 6-band (markirovka offline taxmini).
- `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md` — uskunalar, ESC/POS, HID skaner (Android hujjatiga ham tegishli).
- `spec/02-arxitektura/00-umumiy-arxitektura.md`, `01-malumotlar-modeli.md` (`client_event_id`, `sync_receipts`, `devices`, `stock_lots`, `recost_jobs`, `fiscal_receipts`).
- `spec/02-arxitektura/08-frontend-arxitekturasi.md` (Dexie, vite-plugin-pwa, Idempotency-Key, Web Locks/BroadcastChannel yondashuvi shu yerga mos kelishi uchun moslashtirildi).
- `spec/01-mahsulot/02-modullar-talablari.md` — M01, M02, M04, M08, M16 offline bo'limlari.
- `spec/01-mahsulot/04-ekranlar-va-ux.md` — POS-02…POS-15, offline indikator qoidasi (§1.3).
