# Ekran tafsilotlari — 41 ekran (implementatsiyaga tayyor)

**Maqsad:** har bir ekran (POS-01…16, BO-01…24, ADM-01) uchun implementatsiyaga tayyor tafsilot — maqsad, rol/ruxsat, route, maket, maydonlar, amallar, API, holatlar, klaviatura, audit, US.
**Kim uchun:** frontend ishlab chiquvchilar.
**Bog'liq fayllar:** `06-ekranlar-umumiy.md` (41 ekran ro'yxati, wireframelar, UX qoidalari, navigatsiya), `21-integratsiyalar.md` (OFD/fiskal, e-faktura, E-TTN, markirovka, to'lovlar), `34-1c-agent.md` (Do'kon agenti, qaror #60), `33-1c-integratsiya.md` (§10 W-xx, §11 ruxsatlar, §13 BO-22/BO-23), `13-provodka-qoidalari.md` §2.18a (BO-24), `20-api-moliya-admin.md`, `03-modullar-talablari.md` (US-Mxx-nn), `04-biznes-jarayonlar.md` (BP-nn), `08-dizayn-tizimi.md` (tokenlar, komponentlar), `24-frontend-arxitekturasi.md` (FSD/Effector/route), `16-offline-sync.md`, `14-autentifikatsiya-oauth2.md`, `05-mvp-chegarasi.md` (tarif).
**Holat:** joriy, 2026-10-16.

## Qanday o'qish kerak

- **Route** — `apps/shell` routeri ichida, `@pages/*` paketiga mos (`24-frontend-arxitekturasi.md` §1). POS yo'llari `/pos/...`, back-office `/app/...`, login `/login`, onboarding `/onboarding`, platforma admin `/platform/...` (alohida `admin-bff`, `14-autentifikatsiya-oauth2.md` §18.1).
- **Ruxsat (permission)** — `role_permissions.permission_code` formatida, scope prefiksi `14-autentifikatsiya-oauth2.md` §10 jadvaliga mos (`sales.*`, `stock.*`, `debts.*`,...). Kod nomlari `15-xavfsizlik-va-audit.md` ruxsat katalogiga mos.
- **Egasi — barcha ekranlarga kirish** (qaror #28): har bir ekran tafsilotidagi "Rollar/ruxsat" qatorida faqat shu ekranning odatiy (operatsion) roli ko'rsatilgan; Egasi tenantning barcha ruxsatlarining supersetiga ega bo'lgani uchun (`02-rollar-va-ssenariylar.md`, 6-bo'lim) quyida alohida sanalmagan bo'lsa ham **har doim** har qanday ekranga (shu jumladan POS-01…16) kira oladi va shu ekrandagi har qanday `Y`/`T` amalni bajara oladi; faqat `platform.admin` (ADM-01) bundan mustasno.
- **Ma'lumot manbai** — REST `/api/v1/<resource>` uslubida, kebab-case ko'plik yo'l (`/goods-receipts`), `17-api-umumiy.md`–`20-api-moliya-admin.md` katalogiga mos nomlar bilan; `/auth/*`, `/billing/pay`, `/billing/export-my-data` — `/api/v1`siz.
- **Holatlar** — har ekranda quyidagi yetti holatning tegishlilari ko'rsatiladi: `loading` (skeleton), `empty` (`EmptyState`), `error` (`ErrorState`), `offline` (`OfflineBadge` + funksional cheklov), `no-permission` (`NoPermissionState`, 403 `PERMISSION_DENIED`), `subscription-restricted` (`SubscriptionRestrictedState`, 403 `SUBSCRIPTION_RESTRICTED` — faqat `/login`, to'lov va POS-01 bundan mustasno, chunki ular bu holatning o'zini ko'rsatadi), **`subscription-grace`** — `GET /billing/subscription` → `status=grace`: barcha ekran odatdagidek ishlaydi, shell tepasida qizil `aria-live="assertive"` banner «Obuna muddati o'tdi. {HH:mm} ichida to'lang, aks holda kassa to'xtaydi» + "To'lash" havolasi (BO-19); muddatdan 3/1/0 kun oldin sariq banner «Obuna {sana} da tugaydi» (US-M17-03).
- **Audit/analytics** — `audit_log.action` — nuqtali `domen.fe'l` uslubida (masalan `sale.draft_voided`); mahsulot-analitika (faqat ichki telemetriya) voqealari — `snake_case` (masalan `receipt_printed`); ikkisi aralashtirilmaydi.
- **«1C da» belgisi (Bosqich 7)** — tenantda 1C bazasi bog'langan va foydalanuvchida `onec.view` bo'lsa, ERP hujjati tafsiloti ko'rsatiladigan ekranlarda (POS-04/POS-05 chek tafsiloti, BO-03 ko'chirishlar, BO-04 kirim/qaytarish/to'lov, BO-06 qarz to'lovi, BO-17 xarajat, BO-24 bank tushumi, inventarizatsiya va hisobdan chiqarish hujjatlari) sarlavha yonida `OnecRefBadge` (`08-dizayn-tizimi.md`) — «1C: ОРП № 0000-000123 ✓»; manba `GET /api/v1/onec-object-refs?doc_type=&doc_id=` (W-54); bosilsa BO-23 shu kun partiyasi. `onec.view` yo'q yoki 1C bog'lanmagan — belgi chizilmaydi (`06-ekranlar-umumiy.md` §1.8). Har ekran bo'limida alohida takrorlanmaydi.
- **Offline fiskal shkala** (qaror #43) — barcha POS ekranlarining status paneli shu kassadagi OFD tasdig'ini olmagan (`ofd_acked_at IS NULL`) eng eski fiskal chekning `created_at`idan hisoblanadi: **24 soat** — 🟡 sariq; **40 soat** — 🔴 qizil + Egasiga M18 (Telegram) xabari; **46 soat** — har yangi chek oldidan yopiladigan modal «2 soatdan keyin kassa bloklanadi — internetga ulaning» ("Tushundim"); **48 soat** — ⛔ "Bloklangan": yangi fiskal chek (sotuv, qaytarish, `debt_settlement`) yaratilmaydi (`FISCAL_OFFLINE_48H_BLOCKED`), faqat sinxronlash/qayta yuborish, qoldiq ko'rish, smenani yopish va naqd sanash ishlaydi; `audit_log` yozuvi + Egasiga M18 xabari; barcha kutilayotgan cheklar OFD tasdig'ini olgach blok avtomatik yechiladi, qo'lda chetlab o'tish yo'q. Quyidagi ekranlarda bu holat `fiscal-blocked` deb ko'rsatiladi.
- **Validatsiya** — `react-hook-form` + `zod`; backend bir xil xato shaklini (`field`, `code`) qaytaradi (`24-frontend-arxitekturasi.md` §3).

---

# A. Android POS / veb-kassa ekranlari (POS-01…16)

## POS-01 — Kassaga kirish / Smena ochish

- **Maqsad**: kassirni (yoki har qanday POS foydalanuvchisini) autentifikatsiya qilish (PIN, qurilma OAuth sessiyasi ichida), so'ng rolga qarab smenani ochish yoki to'g'ridan-to'g'ri ombor menyusiga yo'naltirish. Ekran ikki qadamga bo'linadi: ① **"PIN bilan kirish"** — har qanday POS foydalanuvchisi (Kassir, Omborchi); ② rolga qarab: `shift.open` huquqi bor bo'lsa (Kassir) — "Smenani ochish" qadami; `shift.open` yo'q bo'lsa (Omborchi) — to'g'ridan-to'g'ri POS-08/POS-09/POS-10 menyusiga o'tadi, smena ochmaydi.
- **Rollar/ruxsat**: Kassir, Omborchi (PIN kirish — ruxsatsiz, autentifikatsiya o'zi); smena ochish — `shift.open`; huquqsiz foydalanuvchi (hech qaysi POS roli bo'lmagan) kira olmaydi.
- **Route**: `/pos/login`
- **Maket** (ASCII — `06-ekranlar-umumiy.md` §6 asosida):

```
┌───────────────────────────────────────┐
│  ERP Kassa               [UZ·RU]  🔴   │
├───────────────────────────────────────┤
│        Filial: "Chilonzor-3" (qurilmaga bog'langan, faqat ko'rsatiladi) │
│   PIN kod:  [ * * * * ]                │
│        [ 1 ][ 2 ][ 3 ]  [ 4 ][ 5 ][ 6 ]│
│        [ 7 ][ 8 ][ 9 ]  [  ][ 0 ][ ⌫ ] │
│         [  SMENANI OCHISH  ]  (Kassirda)│
│   Boshlang'ich naqd:  [ 500 000 ]      │
│   PIN/parolni unutdim?                 │
└───────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `branchId` | Filial | Филиал | Faqat ko'rsatish (matn) | — | — | `devices.cash_register_id` orqali avtomatik aniqlangan filial | — |
| `pin` | PIN kod | PIN-код | `PinPad` (4–6 raqam) | Ha | Faqat raqam, 4–6 ta | — | 6 |
| `openingCash` | Boshlang'ich naqd | Начальная наличность | `MoneyInput` | Ha (`shift.open` bor foydalanuvchida smena ochishda) | ≥0, 2 kasr xonasi | Oxirgi yopilgan smenaning sanalgan naqd qoldig'i (yo'q bo'lsa 0) | 9 999 999 999 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| PIN bilan kirish | — | Yo'q | PIN tasdiqlanadi; `shift.open` bor bo'lsa "Smenani ochish" qadami ko'rsatiladi, yo'q bo'lsa (Omborchi) to'g'ridan-to'g'ri POS-08/09/10 menyusiga o'tadi |
| Smenani ochish | `shift.open` | Yo'q | `shift.opened` voqeasi, POS-02ga o'tish |
| ⚙ Uskunalar | — | Yo'q | POS-16 (printer, skaner, tarozi sozlamasi) |
| PIN/parolni unutdim | — | (qaror #34) OTP oynasi (`purpose=recovery`) — kod birinchi navbatda Telegram botga, ulanmagan bo'lsa SMS'ga (zaxira) | Yangi PIN/parol o'rnatish seansi |

- **Ma'lumot manbai**: `POST /auth/pin/verify` (online qo'shimcha tasdiq, 4.3-bo'lim), outbox: `shift.opened` (`16-offline-sync.md` §2), `GET /auth/license` (litsenziya tokeni, offline qurilma).
- **Holatlar**: `loading` (qurilma/filial ma'lumoti yuklanmoqda) · `empty` — yo'q (smena ochish bo'sh bo'lmaydi) · `error` (PIN noto'g'ri — standart xabar #17/#18) · `offline` (PIN mahalliy heshga qarshi tekshiriladi, litsenziya token amal qilsa) · `no-permission` — yo'q (login ekrani) · `subscription-restricted` — butun ekran qizil banner, PIN maydoni o'chirilgan; "Ma'lumotlarimni yuklab olish" tugmasi PIN ekranida emas — `/login?reason=subscription_expired`ga yo'naltiradi (telefon+parol identifikatsiyasi + `purpose=data_export` OTP — (qaror #34) Telegram bot birinchi, SMS zaxira, D2) (`14-autentifikatsiya-oauth2.md` §16) · **`subscription-grace`** — ekran odatdagidek ishlaydi, tepada qizil banner (yuqoridagi "Qanday o'qish kerak").
- **Klaviatura**: raqam tugmalari PIN kiritadi, `Enter` tasdiqlaydi, `Esc` tozalaydi.
- **Audit/analitika**: `login_success`, `login_failed`, `account_locked`, `shift.opened`, `pos_login_screen_viewed`.
- **Bog'liq US**: US-M01-04, US-M01-07 (uskunalar sozlamasiga kirish), US-M17-03 (lockout holati), US-M13-06 (parol/PIN tiklash).

---

## POS-02 — Sotish paneli (asosiy chek)

- **Maqsad**: tovarlarni chekka qo'shish, chegirma qo'llash, jami summani ko'rsatish.
- **Rollar/ruxsat**: Kassir (`sales.create`, `discount.give`).
- **Route**: `/pos/sale`
- **Maket**: `06-ekranlar-umumiy.md` §6 POS-02 wireframe'i. Ikki ustun: **chapda — tovar paneli**: tepada skaner/qidiruv maydoni (`BarcodeField`, F1), uning yonida ko'rinish almashtirgich **«Kartochka» / «Ro'yxat»**; ostida **kategoriya tablari** («Hammasi» + `product_categories`, birinchi daraja); so'ng tovarlar — kartochka ko'rinishida to'r (grid: bosh harf tayli, nom, narx, tur chipi «dona» / «tarozi» / «markirovka»), ro'yxat ko'rinishida ixcham qatorlar (nom, tur chipi, narx). **O'ngda — chek paneli**: chek raqami, «+ Mijoz» (F3), qatorlar (nom, `narx × miqdor` yoki chegirma/markirovka izohi, `−`/`+` miqdor tugmalari, qator summasi), yakun bloki (Oraliq summa, Chegirma, «Shu jumladan QQS» stavka bo'yicha, **Jami** — eng katta shrift), pastda CHEGIRMA, NASIYA, BEKOR va asosiy «TO'LOVGA O'TISH» (F4). Status panel (yuqori panel): filial · kassa, smena raqami va boshlangan vaqti, offline holat chipi (1.3-bo'lim), printer holati chipi (POS-16), «UZ · RU», kassir. **Skaner har doim faol**: ko'rinish (kartochka/ro'yxat), tanlangan kategoriya yoki fokusdagi element qanday bo'lmasin, USB HID skaner kiritmasi `BarcodeField` ga yo'naltiriladi va qator qo'shadi (1.6-bo'lim); skanerlash kategoriya/ko'rinish tanlovini o'zgartirmaydi.
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `customerId` | Mijoz | Клиент | `Combobox` | Yo'q | Mavjud mijoz yoki yangi | Bo'sh (anonim) | — |
| `barcode` | Skanerlash/qidiruv | Сканирование/поиск | `BarcodeField` | — | Katalogda mavjud kod; matn kiritilsa tovar paneli nom/kod bo'yicha filtrlanadi | — | 64 belgi |
| `categoryId` | Kategoriya | Категория | Tablar | Yo'q | Lokal `product_categories` (arxivlanmagan) | «Hammasi» | — |
| `viewMode` | Ko'rinish | Вид | `SegmentedControl` (Kartochka / Ro'yxat) | Yo'q | `grid\|list` — qurilmada saqlanadi (`localStorage`) | `grid` | — |
| `lines[].qty` | Miqdor | Количество | `QtyInput` | Ha | >0, o'lchov birligiga mos kasr | 1 | 99 999 |
| `discountPercent` | Chegirma % | Скидка % | `Input` (number) | Yo'q | 0–100, PIN'siz ≤5% (standart, M13 orqali sozlanadi); butun chek chegirmasi qatorlarga `line_gross` ulushida taqsimlanadi (qoldiq eng katta qatorga), har qatorda `discount_source='manual'`; limit `Σ discount_manual / Σ line_gross × 100` | 0 | 100 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Skanerlash | `sales.create` | Yo'q | Qator qo'shiladi; markirovkalangan tovarda `MarkingBadge` |
| Qidirish | `sales.create` | Yo'q | `Combobox` natija ro'yxati |
| Tovar kartochkasi/qatori (bosish) | `sales.create` | Yo'q | «dona» tovar — qator qo'shiladi (bor bo'lsa miqdor +1); «tarozi» tovar — og'irlik kiritish oynasi (qo'lda og'irlik, 1.6-bo'lim); «markirovka» tovar — qator qo'shilmaydi, «Markirovka kodini skanerlang» so'rovi (kodsiz markirovkali qator taqiqlangan) |
| Kategoriya tabi / Kartochka–Ro'yxat | — | Yo'q | Tovar paneli filtrlanadi/ko'rinish almashadi; chek va skaner fokusiga ta'sir qilmaydi |
| `−` / `+` (qatorda) | `sales.create` | Yo'q | Miqdor ±1 (tarozi tovarida — og'irlik oynasi); `−` 1 dan pastga tushirmaydi (qatorni o'chirish — BEKOR) |
| CHEGIRMA | `discount.give` (>5% — `discount.approve`, `ApprovalDialog`) | >5%da Menejer/Egasi PIN | Chek summasi qayta hisoblanadi |
| BEKOR (qator/chek) | `sales.void` | "Haqiqatan bekor qilasizmi?" (#15) | `sale.draft_voided` audit voqeasi, fiskal chek yo'q |
| TO'LOV ▶ | `sales.create` | Yo'q (46 soat modali — POS-03 "TASDIQLASH" oldidan); 48 soatdan keyin tugma o'chiq (qaror #43) | POS-03ga o'tish |
| + Mijoz | `debts.create` yoki `sales.create` | Yo'q | Mijoz tanlash/yaratish bottom sheet; "+ Mijoz" bosilganda `counterparty.created` voqeasi |
| NASIYA | `debts.create` | Yo'q | POS-06 (mijoz, limit) → POS-03 (to'lov usuli = "Nasiya") |
| 📒 Qarz daftari | `debts.payment.accept` yoki `debts.create` | Yo'q | POS-13 (bosh ekranda doimiy tugma) |

- **Markirovka** (qaror #62): markirovka kodi chakana sotuvda **fiskal chek ichida** OFD orqali Asl belgisiga uzatiladi (`sale_lines[].marking_code` → `FiscalPort` `items[].marking_codes[]`) — kassa CRPT'ni alohida chaqirmaydi. Skanerda: (1) **lokal takror-kod nazorati** har doim (online va offline) — shu chekda dublikat yoki tenantda avval sotilgan kod (sinxronlangan `marking_codes`) bo'lsa qator **rad etiladi**; kodsiz markirovkali qator bilan chek yopilmaydi; (2) online bo'lsa sotuvdan oldingi tekshiruv `POST /api/v1/marking-codes/verify` — tenant sozlamasi `MARKING_PRECHECK` (`off` | `warn` | `block`, standart `warn`, BO-14): `warn` — muvaffaqiyatsiz javobda sariq ogohlantirish + audit `marking.precheck_failed`, sotuv davom etadi; `block` — qator rad etiladi; offline — tekshiruv o'tkazib yuboriladi, kod chekda FM tomonidan imzolanadi. Tashqi tasdiq — 26 #40 (OQ-025).
- **Ma'lumot manbai**: lokal Dexie `catalog`/`prices`/`customers`/`marking_codes` (`16-offline-sync.md` §1); outbox `sale.created` (payload: `sales`+`sale_lines`+`sale_payments`); `GET /api/v1/products?search=` (online qidiruv zahira); `POST /api/v1/marking-codes/verify` (online sotuvdan oldingi tekshiruv); `counterparty.created` voqeasi.
- **Holatlar**: `loading` (katalog snapshot yuklanmoqda) · `empty` ("Chekni boshlang, skanerlang") · `error` ("Mahsulot topilmadi" #21; "Markirovka o'qilmadi" (#23) → 3 urinishdan keyin **DataMatrix kodini qo'lda kiritish** maydoni — faqat online, `POST /marking-codes/verify` bilan tekshiriladi, offline'da qo'lda kiritish taqiq, audit `marking.manual_entry`; MXIK — tovar katalogi rekviziti, markirovka kodi emas; "Bu kod allaqachon sotilgan" — lokal takror-kod nazorati) · `offline` (status panel 🟡/🔴, TO'LOV faol qoladi, markirovkali qator `fiscal-pending` belgisi bilan sotiladi) · `fiscal-blocked` (48 soat, qaror #43 — ⛔ banner «Kassa bloklangan: cheklar 48 soatdan beri OFD'ga yuborilmagan. Internetga ulaning»; qator qo'shish va TO'LOV o'chiq, "Sinxronlash" → POS-12) · `no-permission` — modul butunlay yopiq bo'lmaydi (Kassir uchun asosiy ekran) · `subscription-restricted` — ekran ochilmaydi, `/pos/login`ga redirect.
- **Klaviatura**: `F1` skaner fokus, `F2` chegirma, `F3` mijoz, `F4` to'lov, `F5` nasiya, `+`/`-` miqdor, `Delete` qatorni o'chirish, `Enter` skaner natijasini qabul qilish.
- **Audit/analitika**: `sale_line_added`, `discount_applied`, `sale.draft_voided`, `marking.offline_sold`, `marking.offline_refused_no_price`, `marking.manual_entry`, `marking.precheck_failed`, `marking.duplicate_rejected`, `fiscal.offline_warning_shown`.
- **Bog'liq US**: US-M01-01, US-M01-02, US-M01-03, US-M03-01, US-M09-03, US-M09-07.

---

## POS-03 — To'lov usuli va hisoblash

- **Maqsad**: to'lov turini tanlash (naqd / karta — integratsiyalangan terminal yoki qo'lda / UzQR / Payme / Click / Uzum / aralash / nasiya), qaytimni hisoblash, chekni yakunlash. Karta to'lovida kassaga terminal bog'langan bo'lsa summa terminalga avtomatik yuboriladi va natija (niqob, RRN, tasdiq kodi, karta turi) terminaldan olinadi — kassir karta ma'lumotini yozmaydi (qaror #71).
- **Rollar/ruxsat**: Kassir (`sales.create`); karta rekvizitlarini zaxira sifatida qo'lda kiritishga tasdiq va natijasi noma'lum tranzaksiyani qo'lda yopish — `card.manual_entry.approve` (Menejer, Egasi; `ApprovalDialog`, tasdiq turi `card_manual_entry`).
- **Route**: `/pos/sale/payment`
- **Maket**: POS-02 ustida modal dialog (1080 × 660, overlay). Chap ustun: sarlavha "To'lov" + chek raqami chipi + yopish (✕); to'lov usullari tugmalar to'ri (4 × 2: Naqd — "qaytim hisoblanadi", Karta — "terminalga yuboriladi" / qo'lda rejimda "qo'lda belgilash", UzQR — "statik / dinamik", Click, Payme, Uzum — "QR-kodli to'lov", Aralash — "bir nechta usul", Nasiya — "mijoz qarziga", amber ohangda); tanlangan usul paneli. O'ng ustun (`aside`): "Chek tarkibi" (qatorlar, oraliq summa, chegirma, "Shu jumladan QQS 12%"), "To'lanadigan" yirik summa, to'lov taqsimoti ("Karta · terminal", "Qoldiq"), asosiy tugma va "Sotishga qaytish (Esc)". Qo'lda belgilash rejimining ixcham ko'rinishi — `06-ekranlar-umumiy.md` §6 POS-03 wireframe'lari.
- **Karta — integratsiyalangan terminal paneli** (qaror #71; `CardTerminalPanel`, `08-dizayn-tizimi.md`):
  - sarlavha qatori: holat matni ("Summa terminalga yuborildi" / "Bank javobi kutilmoqda" / "To'lov tasdiqlandi" / "Karta rad etildi" / "Terminal javobini tekshiring") + izoh ("Mijoz kartani terminalga tegizsin yoki kiritsin va PIN kodni tersin") + **terminal holati chipi** (`TerminalStatusChip`: "Wi-Fi · ulangan" — `online`, "Band" — `busy`, "Ulanmagan" — `offline`/`error`, "Tekshirilmoqda" — `unknown`);
  - terminal qatori: "Terminal: {nom} · TID {tid}" va ulanish yo'li ("Simsiz tarmoq orqali · Do'kon agenti" — `adapter='agent_ecr'`; "Bulut orqali" — `cloud`; "Shu qurilmadagi to'lov ilovasi" — `android_intent`; "Telefon (SoftPOS)" — `softpos`; "Sinov terminali" — `fake`);
  - **4 qadamli indikator** (`StepIndicator`): ① "Summa yuborildi" (summa · yuborilgan vaqt) → ② "Mijoz kartani tegizadi" ("PIN kutilmoqda…") → ③ "Bank javobi" ("tasdiq yoki rad") → ④ "Fiskal chek" ("avtomatik chiqadi"); holatlar: bajarildi / faol / keyingi / xato;
  - natija maydonlari (faqat o'qish, terminal javobigacha punktir chegara va "terminaldan keladi" matni): "Karta (niqob)" (`card_mask`), "RRN / tasdiq kodi" (`rrn` / `approval_code`), "Karta turi" (`card_type`; natijada bo'lmasa `platform.card_bin_rules` dan, u ham topilmasa — bitta bosishli `SegmentedControl` "Shaxsiy / Korporativ / Ijtimoiy / Noma'lum");
  - tugmalar: **"Terminalda bekor qilish"** (faqat kutish paytida faol) va **"Qayta yuborish"** (faqat urinish yakuniy `declined` bo'lganda faol — yangi `attempt_id` bilan yangi urinish; kutish va `unknown` holatida o'chiq); o'ngda kutish taymeri "Kutish: mm:ss / mm:ss" (chegarasi — `purchase` taymauti, `21-integratsiyalar.md` §9.4);
  - eslatma (info): "Karta raqami qo'lda kiritilmaydi — summa, natija va RRN terminal bilan avtomatik almashadi. Terminal javob bermasa, natija avtomatik tekshiriladi; rad etilsa — «Qayta yuborish» yoki boshqa to'lov usuli";
  - o'ng ustundagi asosiy tugma kutish paytida o'chiq holat ko'rinishida — "Bank javobi kutilmoqda…"; `approved` dan keyin fiskal chek kassir bosmasdan chiqadi va POS-04 ga o'tiladi; "Bank tasdiqlagach fiskal chek avtomatik chiqadi" izohi.
- **Karta oqimi (holat mashinasi, qaror #71)**:
  1. "Karta" bosilganda POS kassaning standart terminalini (`card_terminals.is_default`, aks holda yagona faol terminal) tanlaydi va `health` holatini tekshiradi (agent `GET /v1/card/health`, ≤ 3 s; `18-api-kassa.md` §16a.1); `online` bo'lsa yangi `attempt_id` (UUIDv7) bilan `purchase` yuboriladi (Windows veb-kassa — `POST 127.0.0.1:47110/v1/card/purchase`, `CardTerminalPort`, `@shared/lib/cardTerminal`); aralash to'lovda karta qismi summasi yuboriladi.
  2. Kutish: ② qadam faol, taymer ishlaydi; "Terminalda bekor qilish" → `POST /v1/card/cancel-pending` → urinish `declined`.
  3. `approved` va tasdiqlangan summa (`amount`) = so'ralgan summa → niqob/RRN/tasdiq kodi/karta turi to'ladi, ③ ✓, darhol `sale.created` ga tayyorlanadi: fiskal chek (`payment_form='card'` yoki `mixed`, `card_type`, `card_mask`, `rrn`) → ④ ✓ → POS-04. Tartib qat'iy: karta tasdig'i → fiskal chek → `sale.created`.
  4. Tasdiqlangan summa (`amount`) ≠ so'ralgan summa → `CARD_AMOUNT_MISMATCH`, avtomatik `void`, xato holati.
  5. `declined` → ③ xato, `decline_message` ko'rsatiladi; "Qayta yuborish" yoki boshqa usul.
  6. Taymaut yoki aloqa uzildi → `unknown`: ekran "Terminal javobini tekshiring" holatiga o'tadi, POS avtomatik `GET /v1/card/tx/{attempt_id}` (`get_status` / `get_last_transaction`) so'raydi; `approved` → 3-band, `declined`/topilmadi → 5-band. Natija aniqlanmaguncha shu chekka yangi karta urinishi **bloklanadi** (`CARD_OUTCOME_UNKNOWN`), "Qayta yuborish" o'chiq, `purchase` hech qachon avtomatik takrorlanmaydi. Aniqlanmasa "Menejer tasdig'i bilan yopish" tugmasi: terminal chekidagi natijaga qarab Menejer/Egasi `ApprovalDialog` orqali "tasdiqlangan" (niqob/RRN kiritiladi, `resolved_by='manager'`) yoki "o'tmagan" deb yopadi.
  7. Tasdiqdan keyin fiskal chek chiqmasa: sotuv "To'lov qabul qilingan, chek kutilmoqda" holatida qoladi (savat saqlanadi), fiskal qayta urinish (POS-04/POS-12); kassir sotuvni bekor qilsa — karta tranzaksiyasi avtomatik `void` (settlementgacha) yoki `refund`; `void` muvaffaqiyatsiz — `CARD_VOID_FAILED` (audit `card.void.failed`), sotuv bekor qilinmaydi.
  8. Terminal `offline`/`error`/`busy` yoki agent ulanmagan: Karta tugmasi ostida sabab ("Terminal ulanmagan", "Terminal band"); qo'lda belgilash `tenants.settings.card_manual_fallback` bo'yicha — `allow`: "Karta (qo'lda)" maydonlari ochiladi; `manager_approval` (faol terminal bog'langan kassada standart): avval sabab (`manual_reason`) va `ApprovalDialog` (`card.manual_entry.approve`), tasdiqsiz — `CARD_MANUAL_APPROVAL_REQUIRED`; `forbid`: qo'lda kiritish yopiq (`CARD_MANUAL_NOT_ALLOWED`), boshqa usul tanlanadi.
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `paymentMethod` | To'lov usuli | Способ оплаты | Tugmalar to'ri (4 × 2) | Ha | `cash\|card\|uzqr\|payme\|click\|uzum\|mixed\|debt` (`mixed` — UI rejimi, bir nechta `sale_payments` qatori) | — | — |
| `cashReceived` | Olingan naqd | Полученная наличность | `MoneyInput` | Ha (naqd bo'lsa) | ≥ to'lanadigan summa | To'lanadigan summa | 9 999 999 999 |
| `cardEntryMode` | — | — | Avtomatik (ko'rinmaydi) | Ha (karta bo'lsa) | `integrated\|manual`; `integrated` — kassaga faol terminal bog'langan va `online`; `manual` — terminal yo'q yoki zaxira | Terminal bor bo'lsa `integrated` | — |
| `cardTerminalResult` | Karta (niqob), RRN / tasdiq kodi | Маска карты, RRN / код авторизации | `CardTerminalPanel` (faqat o'qish) | Ha (`integrated`) | Terminal natijasi: `attempt_id`, `status`, `rrn`, `approval_code`, `card_mask`, `card_scheme`, `tid`, `mid`, `tx_at` | — | — |
| `cardType` | Karta turi | Тип карты | `integrated` — natijadan / BIN qoidasidan, topilmasa bitta bosishli `SegmentedControl`; `manual` — `SegmentedControl` (Shaxsiy / Korporativ / Ijtimoiy / Noma'lum) | Ha (karta bo'lsa) | `personal\|corporate\|social\|unknown`; manba `card_type_source` = `terminal\|bin_table\|cashier` | — (qo'lda rejimda har safar so'raladi, qaror #64) | — |
| `cardMask` | Karta raqami (niqob) | Маска карты | `integrated` — faqat o'qish; `manual` — `Input` (`8600****1234`) | `integrated` — ha (natijadan); `manual` — ijtimoiy kartada ha | `^[0-9]{4}\*+[0-9]{4}$` | — | 19 |
| `rrn` | Tranzaksiya raqami (RRN) | Номер транзакции (RRN) | `integrated` — faqat o'qish; `manual` — `Input` | `integrated` — ha; `manual` — ijtimoiy kartada ha | Max 40 belgi | — | 40 |
| `manualReason` | Qo'lda kiritish sababi | Причина ручного ввода | `Select` (Terminal ulanmagan / Terminal xatosi / Natija noma'lum / Mustaqil terminal) | Ha (`manual`) | `terminal_offline\|terminal_error\|unknown_result\|standalone_terminal`; terminal bog'lanmagan kassada avtomatik `standalone_terminal` | — | — |
| `qrType` | UzQR turi | Тип UzQR | `SegmentedControl` (Statik / Dinamik) | Ha (UzQR bo'lsa) | `static\|dynamic` | `static` | — |
| `terminalRef` | To'lov/terminal raqami | Номер операции | `Input` | Yo'q (ixtiyoriy; statik UzQR to'lov raqami ham shu yerga) | Max 40 belgi | — | 40 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| NAQD/KARTA/UzQR/Payme/Click/Uzum/ARALASH/NASIYA | `sales.create` | Nasiya limitdan oshsa `ApprovalDialog` | To'lov biriktiriladi; KARTA (`integrated`) — summa darhol terminalga yuboriladi |
| Terminalda bekor qilish | `sales.create` | Yo'q | Kutish bekor qilinadi (`/v1/card/cancel-pending`), urinish `declined` |
| Qayta yuborish | `sales.create` | Yo'q | Faqat oldingi urinish `declined` bo'lsa: yangi `attempt_id` bilan `purchase` |
| Menejer tasdig'i bilan yopish (`unknown`) | `card.manual_entry.approve` | `ApprovalDialog` (lokal PIN yoki masofaviy) | Tranzaksiya `approved` (niqob/RRN terminal chekidan) yoki o'tmagan deb yopiladi, `resolved_by='manager'` |
| Karta (qo'lda) — zaxira | `sales.create` (+ `manager_approval` siyosatida `card.manual_entry.approve`) | Siyosatga ko'ra `ApprovalDialog` | `card_entry_mode='manual'`, `manual_reason`; `forbid` da tugma yo'q |
| To'lov qabul qilindi (statik UzQR) | `sales.create` | "Mijoz to'lovini ko'rdingizmi?" | Kassir qo'lda tasdiqlaydi, faqat online; `provider_tx_id` talab qilinmaydi (`qr_type='static'`) |
| TASDIQLASH | `sales.create` | 46–48 soat oralig'ida offline modal (qaror #43) | `sale.created` outbox, POS-04ga o'tish; javobdagi `fiscal.status` ∈ `pending\|fiscalized\|deferred` (lokal ko'prikda chek FM'da imzolanadi va `fiscal_result` voqeaga qo'shiladi, qaror #68). Integratsiyalangan kartada alohida bosilmaydi — `approved` dan keyin avtomatik |
| Sotishga qaytish | — | Karta urinishi `pending`/`unknown` bo'lsa yopilmaydi ("Terminal javobini kuting") | POS-02 |

- **To'lov rekvizitlari** (qaror #64, #71): integratsiyalangan terminalda `sale_payments` ga `card_entry_mode='integrated'`, `card_terminal_transaction_id`, `rrn`, `card_mask`, `approval_code`, `card_scheme`, `card_type`, `card_type_source` terminal natijasidan yoziladi. Qo'lda belgilashda (mustaqil terminal — qonuniy, VMQ-943 1-ilova 6-band) kassir terminal chekidan `cardType` (har doim), `cardMask` va `rrn` (ijtimoiy kartada majburiy) ni kiritadi → `card_entry_mode='manual'`, `manual_reason`. Fiskal chekdagi to'lov shakli (`fiscal_receipts.payment_form`): naqd → `cash` "naqd"; karta → `card` "bank kartalari" (+ karta turi, niqob, RRN); UzQR/Click/Payme/Uzum → `qr` "QR-kodli to'lov"; bir nechta usul → `mixed` "aralash". Terminal cheki (slip) terminalning o'zida chiqadi; ikkala chek beriladi. **UzQR**: statik QR — kassa bilan integratsiyasiz, to'lov faktini kassir qo'lda tasdiqlaydi; dinamik QR — `UzqrPort` orqali (real adapter POS API hujjatidan keyin, hozir stub), `provider_tx_id` majburiy — 26 #49 (OQ-032). Yakka tadbirkor tenantda (`tenants.legal_form='sole_proprietor'`) "UzQR" tugmasi o'rniga to'lov tashkiloti maxsus QR'i (Click/Payme/Uzum) ishlatiladi. Har qanday to'lov usulida fiskal chekni **bizning kassa** chiqaradi; provayderga faqat chek havolasi uzatiladi (Click — `submit_qrcode`).
- **Ma'lumot manbai**: karta — Do'kon agenti lokal API `127.0.0.1:47110/v1/card/*` (`purchase`, `tx/{attempt_id}`, `cancel-pending`; agent imkoniyati `card_terminal`) yoki bulut adapteri orqali server; kassa terminallari — lokal Dexie keshi (`GET /api/v1/card-terminals?cash_register_id=`); online bo'lsa natija darhol `POST /api/v1/card-terminal-transactions` bilan yoziladi (bulut adapterida — natijasiz boshlanadi va `GET /api/v1/card-terminal-transactions/{id}` poll), offline — `sale.created` ichida `payments[].card_result` (`CardResult`, `18-api-kassa.md` §2.7, §16a); `POST /api/v1/payments/checkouts` (`provider` tanada; dinamik UzQR/Click/Payme/Uzum, statik UzQR — checkout'siz) → poll `GET /api/v1/payments/checkouts/{checkout_ref}` (webhook — server tomoni, ekran o'zi chaqirmaydi); outbox `sale.created` (`sale_payments.method`, `card_entry_mode`, `card_type`, `card_mask`, `rrn`, `qr_type`, `terminal_ref`).
- **Holatlar**: `loading` (provayder javobi kutilmoqda) · **`card-waiting`** (summa terminalga yuborilgan: ② faol, taymer, "Bank javobi kutilmoqda…", "Qayta yuborish" o'chiq) · **`card-approved`** (③ ✓, natija maydonlari to'lgan, fiskal chek chiqmoqda) · **`card-declined`** (`CARD_DECLINED`, sabab, "Qayta yuborish" faol) · **`card-unknown`** (`CARD_OUTCOME_UNKNOWN` — "Terminal javobini tekshiring", avtomatik holat so'rovi, yangi urinish bloklangan) · **`card-terminal-unavailable`** (`CARD_TERMINAL_UNREACHABLE` / `CARD_TERMINAL_BUSY` — chip "Ulanmagan"/"Band", zaxira siyosati) · **`receipt-pending`** (karta tasdiqlangan, fiskal chek chiqmagan — "To'lov qabul qilingan, chek kutilmoqda") · `empty` (summa 0) · `error` ("Payme javob bermadi...", yetarli naqd yo'q; "Ijtimoiy karta uchun karta raqami va RRN majburiy"; `CARD_AMOUNT_MISMATCH`; `CARD_VOID_FAILED`) · `offline` — UzQR (statik ham — tasdiq faqat online)/Payme/Click/Uzum tugmalari o'chirilgan (kulrang); naqd, karta (integratsiyalangan — Do'kon agenti va terminal ishlasa; qo'lda) va nasiya faol · `fiscal-blocked` (48 soat, qaror #43) — TASDIQLASH va karta yuborish o'chiq, `FISCAL_OFFLINE_48H_BLOCKED` · `no-permission` — yo'q · `subscription-restricted` — bu ekranga kirilmaydi.
- **Klaviatura**: raqam tugmalari olingan naqdni kiritadi, `Enter` tasdiqlaydi, `Esc` POS-02ga qaytaradi (karta urinishi `pending`/`unknown` bo'lsa ishlamaydi).
- **Audit/analitika**: `payment_method_selected`, `sale.created`, `payment_provider_timeout`, `payment.static_qr_confirmed`, `card.purchase.approved`, `card.purchase.declined`, `card.purchase.unknown`, `card.void.auto`, `card.void.failed`, `card.manual_entry`, `card.outcome.resolved_manual`; analitika — `card_terminal_wait_ms`.
- **Bog'liq US**: US-M01-01, US-M01-05 (UzQR), US-M01-08 (integratsiyalangan karta terminali), US-M08-01 (nasiya).

---

## POS-04 — Chekni chop etish (elektron chek — zahira)

- **Maqsad**: fiskal chekni chop etish (standart — bosma chek), zahira sifatida elektron chek berish, qayta chop etish.
- **Rollar/ruxsat**: Kassir (`sales.create`; qayta chop etish ham `sales.create` — tugma yashirilmaydi, har chop audit yoziladi).
- **Route**: `/pos/sale/receipt`
- **Maket**:

```
┌───────────────────────────────────────┐
│ 🟢 ONLAYN                    22:43    │
├───────────────────────────────────────┤
│   Chek № K-01-2026-000154              │
│   Fiskal belgi: ****  QR: [▦]          │
│   Summa: 69 000 so'm                   │
│                                         │
│   [ 🔁 QAYTA CHOP ETISH  Ctrl+P ]      │
│   [ 📱 ELEKTRON CHEK (zahira) ]        │
│   [  YANGI CHEK  Enter  ]              │
└───────────────────────────────────────┘
```

Ikki ustun: **chapda** — «Chek chop etildi» sarlavhasi, chek raqami/sana/kassir, «To'landi» summasi, fiskal rekvizitlar ro'yxati, «Qayta chop etish», «Elektron chek» bloki (sabab: «Printer ishlamayapti» / «Xaridor so'radi»; yetkazish: QR ekranda / Telegram / SMS havola), printer xatosida ogohlantirish + «Uskunalarni sozlash», «Yangi chek»; **o'ngda** — `ReceiptPreview` (58/80 mm, ikki tilli chek ko'rinishi).

- **Maydonlar**: yo'q (faqat ko'rsatish ekrani) — `ReceiptPreview` komponenti chekni render qiladi (`08-dizayn-tizimi.md` §13.1). (qaror #29) `ReceiptPreview` har bir tovar qatorini **ikki tilda** chiqaradi: `"{name} / {name_ru}"` (`name_ru` bo'sh bo'lsa faqat `name`), shuningdek sarlavha/yakun matnlari ikki tilda ("Jami / Итого", "Naqd / Наличные" va h.k., to'liq ro'yxat — `08-dizayn-tizimi.md` chek shabloni bo'limi).
- (qaror #30) **Nasiyaga sotuvda bu ekran ochilmaydi**: to'lov usuli to'liq "Nasiya" bo'lgan sotuvda fiskal chek shu zahotda chiqarilmaydi (`fiscal_receipts` yaratilmaydi; sotuv `posted`, `fiscal.status='deferred'` (fiskal chek yo'q)) — POS-03 to'g'ridan-to'g'ri POS-06 (yoki POS-02'ga qaytish) ga o'tadi, bu ekran faqat **naqd/karta qismi bo'lgan** (to'liq yoki aralash to'lovning naqd qismi) sotuvlarda ko'rsatiladi. Qarz to'langanda chiqariladigan fiskal chek — alohida oqim, POS-13/BO-06 (`debt_settlement`). Daromad va QQS sotuv kuni tan olinadi, chek — to'lov kuni; sotuv paytidagi "kredit" turidagi chek (`kind='credit_sale'`) `FiscalPolicy.credit_sale_receipt` ortida (standart `none`) — 26 #9 (OQ-002).
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Chop etish | `sales.create` | Yo'q | `shared/lib/printer` runtime tanlovi: Chromium (Windows/Android) — WebUSB/Serial/Bluetooth/tarmoq; **iOS o'rnatilgan PWA — faqat `CloudPrintAdapter`** (Star CloudPRNT/Epson Server Direct Print klassi); LAN (raw 9100) printer — Do'kon agenti orqali (qaror #60); hech biri sozlanmagan bo'lsa "Elektron chek (zahira)" va "Uskunalarni sozlash" ko'rsatiladi |
| Elektron chek (zahira) | `sales.create` | Sabab tanlash: "Printer ishlamayapti" / "Xaridor so'radi" | Ekranda `ofd.soliq.uz` QR havolasi yoki Telegram/SMS havola; `sale.created.delivery='electronic'` va `delivery_reason` (`printer_failure\|customer_request`) → `fiscal_receipts.delivery`, audit `receipt.electronic_issued` |
| Uskunalarni sozlash | — | Yo'q | POS-16 (printer xatosida ko'rsatiladi) |
| Qayta chop etish | `sales.create` | Yo'q | "NUSXA" belgisi bilan chop, `receipt.reprinted` audit |
| Yangi chek boshlash | `sales.create` | Yo'q | POS-02ga qaytish |

- **Chek berish siyosati**: standart — **bosma chek** (`delivery='printed'`); elektron chek faqat (a) printer ishlamay qolganda yoki (b) xaridor o'zi so'raganda, kassir tasdig'i bilan zahira (`delivery='electronic'`, `delivery_reason` audit qilinadi). Do'kon savdosida faqat-elektron chekka rasmiy ruxsat — 26 #112 (OQ-018).
- **Fiskal holat** (qaror #68): `pending` (server/hamkor bulut chekni chiqarmoqda — "Fiskal belgi kutilmoqda") · `fiscalized` (fiskal belgi va QR ko'rsatiladi; lokal ko'prik rejimida chek FM'da imzolangan va `fiscal_result` `sale.created` voqeasiga qo'shilgan) · `deferred` (faqat-qarz sotuv — chek yo'q, bu ekran ochilmaydi).
- **Ma'lumot manbai**: `GET /api/v1/fiscal-receipts?sale_id=` yoki `?debt_payment_id=` (online, qayta chop etish uchun ham), lokal Dexie (offline); voqea `receipt.reprinted {fiscal_receipt_id}`.
- **Holatlar**: `loading` (fiskal belgi kutilmoqda — online) · `empty` — yo'q · `error` (printer ulanmagan/qog'oz tugagan → "Elektron chek (zahira)" va "Uskunalarni sozlash" (POS-16) taklifi, #27) · `offline` (chek lokal saqlanadi, "offlayn" belgisi, fiskal belgi keyin) · `no-permission` — qayta chop etish huquqi yo'q bo'lsa tugma ko'rinmaydi · `subscription-restricted` — bu ekranga kirilmaydi · **iOS, bulut printer sozlanmagan** — «Chop etish uchun bulut-printerni ulang» + `/install#cloud-print` havolasi; elektron chek zahira rejimi ogohlantirish bilan.
- **Klaviatura**: `Ctrl+P` qayta chop etish, `Enter` yangi chek.
- **Audit/analitika**: `receipt.reprinted`, `receipt.electronic_issued`, `receipt_printed`, `receipt_print_failed`, `electronic_receipt_sent`.
- **Bog'liq US**: US-M01-01, US-M01-07, chekka holat "qayta chop etish" (`03-modullar-talablari.md` M01).

---

## POS-05 — Mijozdan tovar qaytarish

- **Maqsad**: asl chek bo'yicha to'liq/qisman qaytarish.
- **Rollar/ruxsat**: Kassir (`returns.create`); limitdan yuqori/chek topilmagan — `returns.approve` (Menejer).
- **Route**: `/pos/returns`
- **Maket**: `06-ekranlar-umumiy.md` §6 POS-05 wireframe'i.
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `receiptQuery` | Chekni qidirish | Поиск чека | `Input`/skaner | Ha | Chek raqami yoki QR | — | 40 |
| `lines[].selected` | Qaytariladigan qator | Возвращаемая строка | `Checkbox` | Ha (≥1) | — | Belgilanmagan | — |
| `lines[].returnQty` | Qaytariladi | Возвращается | `QtyInput` (`−`/`+`) | Ha (belgilangan qatorda) | 0 < qiymat ≤ `qty − returned_qty`; o'lchov birligiga mos kasr | Qaytarilmagan qoldiq miqdori | — |
| `reason` | Sabab | Причина | `Select` | Ha | `defective` (Nuqsonli) / `wrong_item` (Mos kelmadi) / `customer_changed_mind` (Fikri o'zgardi) / `other` (Boshqa) | — | — |
| `refundMethod` | Qaytarish usuli | Способ возврата | Tugmalar | Ha | `cash\|card\|uzqr\|click\|payme\|uzum\|debt_adjustment`; Click/Payme/Uzum pulni qaytarish provayder kabinetida qo'lda, tizim qayd etadi | Asl to'lov usuli | — |
| `lines[].restock` | Sotuvga qaytadi | Вернуть в продажу | `Checkbox` | — | Muddati o'tgan tovar (`expiry_date < bugun`) — majburan `false`, o'zgartirilmaydi | `true` | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| QAYTARISHNI TASDIQLA | `returns.create` | 100 000 so'mdan yuqori, chek topilmagan yoki muddati o'tgan tovar qatori bor — `ApprovalDialog` (`returns.approve`, Menejer/Egasi PIN) | `return.created` outbox, ombor/qarz/pul tuzatiladi; muddati o'tgan qator `restock=false` — qoldiqqa qaytmaydi, avtomatik `write_offs` qoralamasi (sabab `expired_return`) yaratiladi (qaror #48) |

- **Qaytarish summasi va chek**: qarzli sotuvni qaytarishda avval shu sotuvning ochiq qarzi kamayadi (`debt_part = min(return_amount, open_debt_of_sale)`, chek yo'q, `Kt 4010`); qolgan `money_part = return_amount − debt_part` `refundMethod` bo'yicha pul bilan qaytariladi va faqat shu qismga `kind='return'` chek chiqadi (`fiscal_refund ≤ fiscalized_amount(sale) − already_fiscally_refunded(sale)`). `money_part = 0` bo'lsa `return.created.receipt_seq = null`, chek yo'q. Qator summasi server tomonidan hisoblanadi: `refund_line = ROUND_HALF_UP(sale_line.line_total × ret_qty / sale_line.qty, 0)`, qatorning oxirgi qaytarilishi qoldiqni oladi. Markirovkasiz tovarni qaytarish offline ham ruxsat (lokal Menejer/Egasi PIN limit qoidasi bilan); markirovkali qaytarish — faqat online (qaror #23).
- **Ma'lumot manbai**: `GET /api/v1/sales?number=` → tanlangach `GET /api/v1/sales/{id}` (qatorlar, `returned_qty`) (online) yoki lokal keshi; outbox `return.created`.
- **Holatlar**: `loading` · `empty` (chek topilmagan, #20) · `error` ("Bu chek allaqachon qaytarilgan") · `offline` — markirovkasiz tovar lokal yoziladi; **markirovkalangan tovar qatori uchun "Qaytarish" tugmasi bloklanadi** ("Qaytarish uchun internet kerak", #26 — markirovkali qaytarish faqat online, qaror #23) · `fiscal-blocked` (48 soat, qaror #43) — qaytarish cheki yaratilmaydi · `no-permission` — ekran ochilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F6` (global) ekranni ochadi, `Enter` chekni qidiradi.
- **Audit/analitika**: `return.created`, `return_blocked_offline_marking`.
- **Bog'liq US**: US-M02-01, US-M02-02.

---

## POS-06 — Nasiyaga sotish

- **Maqsad**: mijozga kredit limiti ichida (yoki limitsiz, offline bayroq bilan) qarzga sotish.
- **Rollar/ruxsat**: Kassir (`debts.create`); limitdan oshganda `debts.approve` (Menejer).
- **Route**: `/pos/sale/credit`
- **Maket**: `06-ekranlar-umumiy.md` §6 POS-06 wireframe'i.
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `customerId` | Mijoz | Клиент | `Combobox` + `+ Yangi` | Ha | Mavjud yoki yangi (ism+telefon) | — | — |
| `promiseDate` | Va'da sanasi | Обещанная дата оплаты | `Calendar` + tezkor tugmalar (7/14/30 kun) | Yo'q | ≥ bugun | Bo'sh | — |
| `comment` | Izoh | Комментарий | `Textarea` | Yo'q | — | — | 1000 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| NASIYAGA RASMIYLASHTIR | `debts.create` | Limitdan oshsa `ApprovalDialog` (Menejer PIN; offlaynda bayroq bilan davom) | `sale.created` (`sale_payments.method=debt`, `due_date`=`promiseDate`); sotuv `posted`, `fiscal.status='deferred'` (fiskal chek yo'q) — (qaror #30) **fiskal chek chiqarilmaydi**, POS-04 ekrani ochilmaydi; chek qarz to'langanda (POS-13/BO-06, `debt_settlement`) chiqadi |

- **Ma'lumot manbai**: lokal `customers` (`receivable_balance`, `16-offline-sync.md` §1); B2B mijozda server `sale.created` postingida `einvoices(direction='out', status='draft', related_doc_type='sales')` ni o'zi yaratadi (BO-15da imzolanadi); POS chaqirmaydi.
- **Holatlar**: `loading` · `empty` (mijoz tanlanmagan) · `error` ("Limitdan oshdi — Menejer PIN kiriting") · `offline` (limit oxirgi sinxron ma'lumot asosida, sotuv **bloklanmaydi**, server `sales.debt_limit_exceeded=true` bayrog'ini qo'yadi) · `no-permission` — tugma ko'rinmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F5` (global) ochadi.
- **Audit/analitika**: `debt_sale_created`, `debt_limit_exceeded_offline`.
- **Bog'liq US**: US-M08-01, US-M08-02, US-M01-06 (B2B e-faktura eslatmasi).

---

## POS-07 — Smena yopish, Z-hisobot

- **Maqsad**: kunlik savdo jamlanmasini ko'rsatish va smenani yopish.
- **Rollar/ruxsat**: Kassir (`shift.close`).
- **Route**: `/pos/shift/close`
- **Maket**:

```
┌───────────────────────────────────────┐
│ 🟢 ONLAYN                    21:58    │
├───────────────────────────────────────┤
│  Smena №7 — 09:02 dan boshlab          │
│  Naqd: 2 100 000  Karta: 1 500 000     │
│  Nasiya: 650 000  Jami: 4 250 000      │
│  Cheklar: 112   Bekor qilingan: 2      │
│          [  SMENANI YOPISH  ]          │
└───────────────────────────────────────┘
```

Bloklar: sarlavha (smena raqami, ochilgan–joriy vaqt, `F8`); KPI kartalari — Jami savdo, Cheklar (o'rtacha chek), Qaytarishlar, Sof tushum; **«To'lov usullari bo'yicha»** jadvali (usul, cheklar soni, savdo, qaytarish, sof; jami qatori) — `running_totals.totals_by_method`, QR usullari (UzQR/Click/Payme/Uzum) bitta «QR-kodli to'lov» qatorida, nasiya qatori izohi «fiskal chek to'lovda»; **«Kassadagi naqd»** — boshlang'ich naqd, naqd savdo, naqd qaytarish, kassaga qo'yildi, kassadan olindi, **kutilgan naqd** (`expected_cash`; keyingi qadamda POS-15 da sanaladi); **«Fiskal holat»** — fiskal cheklar soni (sotuv + qaytarish), OFD tasdiqlagan, yuborilmagan (eng eski vaqti bilan), FM raqami; sinxronlanmagan chek bo'lsa ogohlantirish + «Sinxronlash» (POS-12) — yopishni bloklamaydi.

- **Maydonlar**: yo'q (jamlanma faqat ko'rsatish) — naqd sanash POS-15da alohida.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Smenani yopish | `shift.close` | "Smenani yopasizmi? Keyin qayta ocholmaysiz" | POS-15ga o'tadi (naqd sanash) → tasdiq → **bitta** `shift.closed` voqeasi (`counted_cash`, `counted_card_total`, `variance_note`) → Z-hisobot |

- **Ma'lumot manbai**: `GET /api/v1/shifts/{id}` (+ `running_totals`; lokal jamlanma offline ham hisoblanadi) → yopilgandan keyin `GET /api/v1/shifts/{id}/z-report`; outbox `shift.closed`.
- **Holatlar**: `loading` · `empty` (savdo bo'lmagan kun) · `error` (sinxronlanmagan cheklar bor — ogohlantirish, lekin yopishni bloklamaydi) · `offline` (Z-hisobot lokal shakllanadi, OFD'ga ulanganda yuboriladi) · `fiscal-blocked` (48 soat, qaror #43) — smenani yopish va naqd sanash ishlaydi · `no-permission` — yo'q · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F8` (global) ochadi.
- **Audit/analitika**: `shift.closed`, `z_report_generated`, `cash_discrepancy_flagged`.
- **Bog'liq US**: US-M01-04.

---

## POS-08 — Yetkazib beruvchidan tovar qabul qilish (kirim)

- **Maqsad**: xaridnoma bo'yicha kelgan tovarni skanerlab solishtirish, qabul qilish.
- **Rollar/ruxsat**: Omborchi (`purchases.receive`).
- **Route**: `/pos/warehouse/receive`
- **Maket**: `06-ekranlar-umumiy.md` §6 POS-08 wireframe'i.
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `purchaseOrderId` | Xaridnoma | Заказ на закупку | `Select` | Ha | Ochiq xaridnomalardan biri | — | — |
| `lines[].receivedQty` | Kelgan miqdor | Полученное количество | `QtyInput` | Ha | >0; 0 bo'lsa qator yuborilmaydi | Buyurtma miqdori | — |
| `lines[].discrepancyReason` | Nomuvofiqlik sababi | Причина несоответствия | `Select` (`short\|excess\|damaged\|wrong_item\|other`) | Farq bo'lsa Ha | → API `lines[].discrepancy_reason` | — | — |
| `poaNumber` | E-ishonchnoma | Эл. доверенность | `Input` | Yo'q | — | `GET /api/v1/powers-of-attorney?purchase_order_id=` dagi `sent\|accepted` yozuvning `number`i; saqlanadi `goods_receipts.poa_id`/`poa_number` | — |

- **E-ishonchnoma va qabul muddati**: yetkazib beruvchidan tovar olish uchun ishonchnomani **do'kon o'z Omborchisiga** EDO operatori orqali e-fakturadan oldin beradi (BO-04, qaror #63); ekranda uning raqami oldindan to'ldiriladi (`poaNumber`), ishonchnoma yo'qligi qabulni bloklamaydi (e-fakturani Buxgalter imzolaydi). Markirovkalangan tovar qabulida Asl belgisi qabul xabarnomasi (EHF) tovar guruhi muddatida imzolanishi kerak — umumiy **3 ish kuni**, ayrim guruhlarda (suv/ichimlik, dori, o'simlik yog'i) **72 soat** (tovar guruhi bo'yicha sozlanadigan muddat, qaror #63); ekran qolgan vaqtni hisoblagich bilan ko'rsatadi, muddat yaqinlashsa ogohlantiradi, bloklamaydi.

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Markirovkani skanerlash | `purchases.receive` | 2–3 urinishdan keyin DataMatrix kodini qo'lda kiritish | Kod `POST/PATCH /goods-receipts` `lines[].marking_codes[]` ga (soni = qty, GS ajratgichlari aynan) |
| Keyinroq davom etish | `purchases.receive` | Yo'q | Qabul qoralamasi saqlanadi (`POST`/`PATCH /goods-receipts`, faqat online; offline — skanerlangan qatorlar qurilmada qoladi), keyin shu xaridnoma tanlanganda davom ettiriladi |
| QABULNI YAKUNLASH | `purchases.receive` | Farq bo'lsa "Nomuvofiqlik bilan yakunlaysizmi?" | `POST /goods-receipts` (draft) → Buxgalter BO-04 "Kirimlar" tabida `POST /goods-receipts/{id}/post` (`purchases.post`) bilan o'tkazadi — qoldiq shu paytda oshadi |

- **Ma'lumot manbai**: `GET /api/v1/purchase-orders/{id}` → `POST /api/v1/goods-receipts` (`po_id` bilan) → `PATCH /api/v1/goods-receipts/{id}` → `POST /api/v1/goods-receipts/{id}/post` (online); offline outbox voqeasi yo'q; `marking_codes`.
- **Holatlar**: `loading` · `empty` (xaridnoma tanlanmagan) · `error` (markirovka o'qilmadi, miqdor mos kelmadi) · `offline` — **qabul yopiq** ("Tovar qabul qilish uchun internet kerak"); sanash/skanerni lokal davom ettirish mumkin, yakunlash faqat online (markirovkalangan tovar qabulida egalik o'zgaradi, kirim faqat online — 13-2 Asosiy xulosa 7) · `no-permission` — ekranga kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F1` skaner fokus.
- **Audit/analitika**: `goods_receipt.drafted`, `marking_scan_failed`, `receive_discrepancy_flagged`, `marking.acceptance_deadline_warned`.
- **Bog'liq US**: US-M07-02, US-M04-01.

---

## POS-09 — Omborlar orasida tovar ko'chirish

- **Maqsad**: filial/ombor ichida/orasida tovar yuborish va qabul qilish.
- **Rollar/ruxsat**: Omborchi (`transfer.create`, `transfer.receive`).
- **Route**: `/pos/warehouse/transfer`
- **Maket**:

```
┌───────────────────────────────────────┐
│ 🟡 OFFLAYN · 1 chek kutmoqda           │
├───────────────────────────────────────┤
│  Manba: Asosiy ombor ▾  →  Manzil: ▾   │
│  [ 📷 Skanerlash ]                     │
│  ┌─────────────────────────────────┐   │
│  │ Coca-Cola 1.5L         x10      │   │
│  └─────────────────────────────────┘   │
│          [  YUBORISH  ]                │
└───────────────────────────────────────┘
```

Ikki ustun: **chapda** — manba/manzil ombor, skaner maydoni (`F1`), qatorlar jadvali (tovar, manbada qoldiq, miqdor `−`/`+`, markirovka kodlari soni; qoldiq yetarli bo'lmasa qatorda sariq ogohlantirish «… kam — davom etish mumkin»), jami (pozitsiya, miqdor, markirovka kodlari); **o'ngda** — hujjat raqami va holati, «Tashish» bloki (`transportMode`, avtomobil raqami, haydovchi, e-TTN izohi) va **holat bosqichlari**: Qoralama (Omborchi) → O'tkazildi (Omborchi) → E-TTN imzosi (Egasi / Buxgalter; `on_foot_or_public` da yo'q) → Yuborildi (Omborchi) → Qabul qilindi (qabul tomoni); pastda «O'tkazish» va «Yuborish».

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `fromWarehouseId` | Manba ombor | Склад-источник | `Select` (MVP: filial tanlanadi, ombor avtomatik — qaror #54) | Ha | ≠ `toWarehouseId` | Joriy filial ombori | — |
| `toWarehouseId` | Manzil ombor | Склад-назначение | `Select` (MVP: filial tanlanadi, ombor avtomatik — qaror #54) | Ha | ≠ `fromWarehouseId` | — | — |
| `lines[].qty` | Miqdor | Количество | `QtyInput` | Ha | ≤ mavjud qoldiq (overselling ogohlantiradi, bloklamaydi) | — | — |
| `transportMode` | Tashish usuli | Способ перевозки | `SegmentedControl` (Avtotransport / Piyoda yoki jamoat transporti) | Ha | `vehicle\|on_foot_or_public` | `vehicle` | — |
| `vehiclePlate` | Avtomobil raqami | Госномер | `Input` | `transportMode=vehicle` da Ha | — | — | 16 |
| `driverName` | Haydovchi | Водитель | `Input` | Yo'q | — | — | — |

- **E-TTN** (qaror #63): o'z filiallari/omborlari orasidagi ko'chirishda ham e-TTN **majburiy** ("Ombordan omborga" turi). `transportMode=vehicle` bo'lsa server `post`da `ettn_documents(status='pending_signature')` (`transfer_id`, `transport_type=warehouse_to_warehouse`) yaratadi; Egasi/Buxgalter BO-03 «Ko'chirishlar» tabida E-IMZO bilan imzolaydi; Omborchi ekranida holat «E-TTN imzo kutilmoqda»; qabul tomonida e-TTN BO-03 da tasdiqlanadi. `on_foot_or_public` — e-TTN talab qilinmaydi. Offline yaratilgan ko'chirish tashish boshlanishidan oldin (internet qaytgach) e-TTN bilan rasmiylashtirilishi kerak — ekran "Tashishdan oldin e-TTN kerak" ogohlantirishini ko'rsatadi. Ichki ko'chirish CRPT'ga xabar qilinmaydi, muddat yo'q.

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| O'TKAZISH (online) | `transfer.create` | Qoldiq yetarli emasligida ogohlantirish (davom etish mumkin) | `POST /api/v1/transfers` → `POST /api/v1/transfers/{id}/post`; `vehicle` da e-TTN `pending_signature` yaratiladi, holat «E-TTN imzo kutilmoqda» — «Yuborish» e-TTN `registered` bo'lgach ochiladi; `on_foot_or_public` da «Yuborish» darhol ochiq |
| YUBORISH | `transfer.create` | Qoldiq yetarli emasligida ogohlantirish (davom etish mumkin) | `transfer.sent`; `vehicle` va e-TTN `registered` emas → hujjat `posted`, holat «E-TTN imzo kutilmoqda» (jo'natish e-TTN ro'yxatdan o'tgach) |
| QABUL QILISH (qabul tomonda) | `transfer.receive` | Yo'q | `transfer.received`, manzil ombor oshadi; e-TTN qabul tomonida tasdiqlanadi |

- **Ma'lumot manbai**: `GET /api/v1/stock-balances?warehouse_id=`; offline — event `transfer.sent`/`transfer.received` (payload — `19-api-ombor.md` §13); online — `POST /api/v1/transfers` → `POST /api/v1/transfers/{id}/post` → (e-TTN `registered`) → `POST /api/v1/transfers/{id}/send`; `POST /api/v1/transfers/{id}/receive`.
- **Holatlar**: `loading` · `empty` (ombor tanlanmagan) · `error` (qoldiq yetarli emas) · `offline` (markirovkalangan tovar ham o'z filiallar orasida offline ko'chirilishi **ruxsat etiladi**, audit bilan; e-TTN holati "kutilmoqda" — tashishdan oldin online rasmiylashtiriladi) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F1` skaner fokus.
- **Audit/analitika**: `transfer.created`, `transfer.received`, `marking.transfer_offline`, `ettn.created`, `ettn.confirmed`.
- **Bog'liq US**: US-M06-01, US-M06-02.

---

## POS-10 — Inventarizatsiya (jismoniy sanash)

- **Maqsad**: ombordagi tovarni jismoniy sanab, tizim qoldig'i bilan solishtirish.
- **Rollar/ruxsat**: Omborchi (`stock.count.create`).
- **Route**: `/pos/warehouse/stocktake`
- **Maket**: `06-ekranlar-umumiy.md` §6 POS-10 wireframe'i. **Chapda** — sarlavha (ombor, sana, filial), skaner/qidiruv maydoni (`F1`) va «Qo'lda kiritish», xato banneri («Bu shtrix-kod tizimda yo'q: …»), filtr tablari **Hammasi / Farqli · N / Sanalmagan · N / Mos**, jadval (tovar, shtrix-kod, tizimda, sanalgan, farq). **O'ngda** — progress «Sanalgan N / M tovar» va hisoblagichlar (Kam / Ortiq / Qoldi), «Joriy tovar» kartasi (nom, markirovka chipi, shtrix-kod, tizimdagi miqdor, `−`/`+` bilan sanalgan miqdor, farq, «Qatorni saqlash» `Enter`), offline izohi, «Sanashni yakunlash».
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `lines[].countedQty` | Sanalgan miqdor | Подсчитанное количество | `QtyInput` | Ha | ≥0 | Bo'sh | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Skanerlash / Qo'lda kirit | `stock.count.create` | Yo'q | Qator "sanalgan" deb belgilanadi |
| SANASHNI YAKUNLASH | `stock.count.create` | "Barcha tovarlar sanaldimi?" | `POST /api/v1/stock-counts/{id}/submit-for-review` → BO-03 "Inventarizatsiyalar" tabiga farq tasdiqlash uchun tushadi |

- **Ma'lumot manbai**: `GET /api/v1/stock-counts/{id}`; offline — event `stock_count.line_recorded` (payload — `19-api-ombor.md` §14), online — `POST /api/v1/stock-counts/{id}/lines`.
- **Holatlar**: `loading` · `empty` (sanash boshlanmagan) · `error` ("Bu shtrix-kod tizimda yo'q") · `offline` (to'liq lokal ishlaydi) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F1` skaner fokus.
- **Audit/analitika**: `stock_count.line_recorded`, `stock_count_completed`.
- **Bog'liq US**: US-M05-01.

---

## POS-11 — Mahsulot va narxni tez qidirish

- **Maqsad**: narx/qoldiqni faqat ko'rish (sotuvsiz tezkor tekshirish).
- **Rollar/ruxsat**: Kassir, Omborchi (`stock.view`).
- **Route**: `/pos/lookup`
- **Maket**:

```
┌───────────────────────────────────────┐
│  🔍 [ Qidiruv: nom/kod/shtrix-kod ]     │
├───────────────────────────────────────┤
│  Coca-Cola 1.5L     18 000 so'm        │
│  Qoldiq: 12 dona   (5 daq. oldin)      │
└───────────────────────────────────────┘
```

Sarlavhada «Faqat ko'rish — sotuv yaratilmaydi» izohi. **Chapda** — natijalar jadvali (tovar, kod, turi: dona/tarozi/markirovka, qoldiq (jami), narx), natijalar soni; offline bo'lsa sariq banner «narx va qoldiq oxirgi sinxron holatida» + oxirgi yangilanish vaqti. **O'ngda** — tanlangan tovar kartasi: nom, narx (birlik bilan), shtrix-kod, ichki kod, QQS stavkasi (narx ichida), markirovka belgisi («Sotuvda markirovka kodi skanerlanadi»), shu filial omboridagi qoldiq (lokal `stock` keshi — faqat shu filial omborlari, `16-offline-sync.md` §1; MVP'da filialda bitta ombor, qaror #54) va qoldiq vaqti.

- **Maydonlar**: `query` — Qidiruv — Поиск — `BarcodeField`/`Input` — majburiy emas — max 64.
- **Amallar**: yo'q (faqat ko'rish ekrani).
- **Ma'lumot manbai**: lokal `catalog`/`prices`/`stock` keshi.
- **Holatlar**: `loading` · `empty` (natija yo'q) · `error` — yo'q · `offline` (oxirgi sinxronlangan narx/qoldiq + "oxirgi yangilanish" vaqti) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F9` (global) ochadi.
- **Audit/analitika**: `price_lookup_viewed`.
- **Bog'liq US**: US-M09-03.

---

## POS-12 — Offline/sinxronizatsiya holati

- **Maqsad**: sinxronlanmagan hujjatlarni va 48 soatlik fiskal muddatni (qaror #43) ko'rsatish.
- **Rollar/ruxsat**: Barcha POS rollari — ruxsat tekshiruvi yo'q, har autentifikatsiyalangan POS foydalanuvchisi.
- **Route**: `/pos/sync`
- **Maket**: `06-ekranlar-umumiy.md` §6 POS-12 wireframe'i.
- **Maydonlar**: yo'q.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| QAYTA ULANISHGA URINISH | — | Yo'q | `POST /api/v1/sync/push` qayta chaqiriladi |

- **48 soat hisoblagichi**: OFD tasdig'ini olmagan eng eski fiskal chekdan o'tgan vaqt va blokkacha qolgan vaqt; bosqichlar — 24 soat 🟡, 40 soat 🔴 (Egasiga M18), 46 soat — har chekdan oldin modal, 48 soat ⛔ "Bloklangan" (`FISCAL_OFFLINE_48H_BLOCKED`, faqat sinxronlash ishlaydi). Fiskal modul holati (`cash_registers.fm_state`: `ok`/`locked`/`ack_overdue`/`memory_full`/`unknown`) ham shu ekranda ko'rsatiladi.
- **Ma'lumot manbai**: Dexie `outbox` (`16-offline-sync.md` §1–2), `POST /api/v1/sync/push` natijalari.
- **Holatlar**: `loading` · `empty` (hammasi sinxron — ekran ko'rinmaydi/kichik ko'k belgi) · `error` ("Ulanish muvaffaqiyatsiz, 2 daqiqadan keyin qayta urinadi") · `offline` (asosiy holat — ro'yxat va 48 soat hisoblagichi) · `fiscal-blocked` (⛔ qizil banner, "QAYTA ULANISHGA URINISH" asosiy amal; cheklar OFD tasdig'ini olgach blok avtomatik yechiladi) · `no-permission` — yo'q · `subscription-restricted` — `sync.drain` holatida ham ko'rsatiladi (fonda drain ishlaydi, UI login sahifasini ko'rsatadi, `14-autentifikatsiya-oauth2.md` §16.4).
- **Klaviatura**: `F12` (global) ochadi.
- **Audit/analitika**: `sync_retry_clicked`, `sync_drain_started`, `sync_drain_completed`, `fiscal.offline_blocked`, `fiscal.offline_unblocked`.
- **Bog'liq US**: US-M01-02.

---

## POS-13 — Qarz daftari (tezkor)

- **Maqsad**: mijoz qarzini ism/telefon bo'yicha tezkor ko'rish, to'lov qabul qilish; yangi qarz POS-02 orqali oddiy sotuv sifatida (tovar qatorlari bilan) yoziladi — tovarsiz, erkin summali qarz yo'q. (qaror #30) Fiskal chek bu bosqichda **chiqarilmaydi** (sotuv `posted`, `fiscal.status='deferred'` (fiskal chek yo'q)) — chek faqat qarz to'langanda chiqadi (pastda, TO'LOV QABUL QILISH).
- **Rollar/ruxsat**: Kassir, Egasi (`debts.create` yoki `debts.payment.accept` — ko'rish; `debts.create` — yozish; `debts.payment.accept` — to'lov qabul qilish).
- **Route**: `/pos/debts`
- **Maket**:

```
┌───────────────────────────────────────┐
│  🔍 Mijoz: [ ism yoki telefon    ]     │
├───────────────────────────────────────┤
│  Aliyev Botir — Qarzi: 350 000 so'm    │
│  12.10 +45 000 (non, sut)  izoh: ...   │
│  08.10 -100 000 (to'lov)               │
│  [ TO'LOV QABUL QILISH ] [ QARZ YOZISH]│
└───────────────────────────────────────┘
```

Uch ustun: **chapda** — qidiruv (ism/telefon), qarzdorlar soni va jami qarz, qarzdorlar ro'yxati (ism, telefon, qarz, limit, holat chipi «muddati o'tgan» / «va'da bugun»); **o'rtada** — tanlangan mijoz: joriy qarz, limitdan bo'sh qism, to'lash va'dasi, «Tezkor qarz yozish» (= QARZ YOZISH, izoh: «Yangi qarz faqat tovar bilan yoziladi…»), qarz daftari jadvali (sana, hujjat/izoh, summa, qoldiq); **o'ngda** — «To'lov qabul qilish» paneli: summa (≤ joriy qarz izohi), to'lov usuli tugmalari, **«To'lov yopadigan sotuvlar»** (allokatsiya — hujjat, «to'liq yopiladi» / «qisman · qoldiq N»), to'lovdan keyingi qarz, yangi va'da sanasi, «To'langan N so'mga fiskal chek chiqariladi» izohi va «To'lovni qabul qilish» (`Enter`).

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `search` | Ism yoki telefon | Имя или телефон | `Combobox` | Ha | — | — | 64 |
| `payment.amount` | To'lov summasi | Сумма платежа | `MoneyInput` | Ha (to'lovda) | >0; online — ≤ joriy qarz (ortig'i rad — `debt_payment_exceeds_balance`, qaytim naqd; qaror #45); offline — oxirgi sinxron qoldiq bo'yicha ogohlantirish, ortig'ini server `debt_payments.unallocated_amount` ga yozadi (qaror #67) | — | — |
| `payment.method` | To'lov usuli | Способ оплаты | Tugmalar | Ha (to'lovda) | `cash\|card\|uzqr\|click\|payme\|uzum` (`bank` yo'q — bank o'tkazmasi faqat BO-06) | `cash` | — |
| `payment.cardType` / `cardMask` / `rrn` / `qrType` | Karta turi / niqob / RRN / UzQR turi | — | POS-03 bilan bir xil | POS-03 qoidasi (qaror #64) | POS-03 qoidasi | — | — |
| `promiseDate` | Yangi va'da sanasi | Новая обещанная дата | `Calendar` | Yo'q (qoldiq qolsa ixtiyoriy) | ≥ bugun | Bo'sh | — |

Tovarsiz, erkin summali qarz yozish yo'q — qarzga sotuv tovar qatorlari bilan oddiy sotuv hujjati sifatida yoziladi, faqat fiskal chek to'lovgacha kechiktiriladi.

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| QARZ YOZISH | `debts.create` | Yo'q | POS-02ni shu mijoz tanlangan holda ochadi, to'lov usuli oldindan `debt` (POS-06 oqimi); natija — `sale.created` (`payments[].method=debt`); sotuv `posted`, `fiscal.status='deferred'` (fiskal chek yo'q) — (qaror #30) **fiskal chek bu bosqichda chiqarilmaydi** |
| TO'LOV QABUL QILISH | `debts.payment.accept` | Yo'q | `debt_payment.created` — server darhol o'tkazadi (alohida `/post` yo'q); qoldiq qolsa `promiseDate` bilan joriy va'da yangilanadi. (qaror #30) **To'langan summaga fiskal chek chiqariladi** (`fiscal_receipts.kind=debt_settlement`) shu kassa FM'ida: bitta to'lov — **bitta** chek, tovar qatorlari yopilgan sotuv(lar)dan proporsional (qaror #45); natijada POS-04 (chek) ekraniga o'tiladi |

- **Allokatsiya va chek qatorlari** (qaror #67): qurilmada `shared/lib/debt-allocation` bilan (offline ham) lokal `customers.open_debt_docs[]` bo'yicha hisoblanadi — avval `sales` + `debt_openings` ochiq qoldiqlari `ORDER BY COALESCE(due_date, doc_date), doc_date, doc_id`, keyin `debt_writeoffs`; ekranda to'lov qaysi sotuvlarni (to'liq/qisman) yopishi ko'rsatiladi. Chek qatorlari: `ratio = alloc_amount / sales.total_amount`, `amt_i = ROUND_HALF_UP(line_total_i × ratio, 2)` (≤ `line_total_i − settled_amount_i`, yaxlitlash qoldig'i eng katta `line_total` qatoriga), sotuvni to'liq yopuvchi chekda — qolgan summa va miqdor; markirovka kodi faqat qatorni to'liq yopuvchi chekda; `debt_openings`/`debt_writeoffs` qismi — bitta umumiy qator "Qarz to'lovi (boshlang'ich qoldiq) / Погашение долга (начальный остаток)". `debt_payment.created` voqeasida: `branch_id`, `cash_register_id`, `shift_id`, `receipt_seq`, `allocations[]`, `fiscal_lines[]`, `fiscal_result` (lokal ko'prik rejimida, qaror #68). Server registrlarni o'z allokatsiyasi bo'yicha qayta hisoblaydi; farq — `sync_exceptions(kind='debt_allocation_mismatch')`.

Tovarsiz "eski qarz"ni kiritish faqat BO-06 → "Boshlang'ich qarz" (`POST /api/v1/debt-openings`; ruxsat `stock.opening.manage` yoki `debts.limit.manage`, `18-api-kassa.md` §12.4) orqali amalga oshadi.

- **Ma'lumot manbai**: lokal `customers` (`receivable_balance`, `open_debt_docs[]`) + online `GET /api/v1/counterparties/{id}/debt-ledger`; voqea `debt_payment.created`.
- **Holatlar**: `loading` · `empty` (qarzdor yo'q) · `error` (telefon formati noto'g'ri, #13; online: "To'lov joriy qarzdan oshmasligi kerak" — `debt_payment_exceeds_balance`) · `offline` (to'liq ishlaydi; qarzdan ortiq summa qabul qilinadi — server `sync_exceptions(kind='debt_overpayment_offline')` va Egasiga M18, hal qilish BO-06 da) · `fiscal-blocked` (48 soat, qaror #43) — TO'LOV QABUL QILISH o'chiq (`debt_settlement` cheki yaratilmaydi), ko'rish ishlaydi · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `F7` (global) ochadi.
- **Audit/analitika**: `debt_sale_created` (POS-02/06 oqimi orqali), `debt_payment_collected`.
- **Bog'liq US**: US-M08-05, US-M08-06, US-M08-09, US-M08-11.

---

## POS-14 — Kassaga pul qo'yish / kassadan pul olish

- **Maqsad**: naqd pul harakatini sabab bilan yozish.
- **Rollar/ruxsat**: Kassir — qo'yish `cash.deposit`, olish `cash.withdraw` (limit); >50 000 so'm olishda tasdiqlovchining `cash.withdraw` limiti summani qoplashi shart (alohida `cash.approve` kodi yo'q, `18-api-kassa.md` §2.4).
- **Route**: `/pos/cash-movement`
- **Maket**:

```
┌───────────────────────────────────────┐
│ [ Pul qo'yish ] [ Pul olish ] [Xarajat]│
├───────────────────────────────────────┤
│  Summa:  [        ]                    │
│  Sabab:  [ Inkasso              ▾ ]    │
│  Izoh:   [                      ]      │
│          [  TASDIQLASH  ]              │
└───────────────────────────────────────┘
```

**Chapda** — rejim almashtirgich (Pul qo'yish / Pul olish / Xarajat), summa + raqamli klaviatura (`000`, `⌫`), sabab chiplari, ta'sischi, izoh; limitdan ortiq olishda shu formaning ichida tasdiqlovchi (ism, rol) va PIN maydoni (`ApprovalDialog` inline), «Tasdiqlash — N so'm olish» (`Enter`). **O'ngda** — «Kassadagi naqd»: boshlang'ich qoldiq, naqd sotuv, naqd qaytarish, qo'yilgan, olingan, **hozir** va **bu amaldan keyin** (lokal hisob; online — `running_totals`); «Smenadagi harakatlar» ro'yxati (lokal `cash_movement.created` voqealari: vaqt, sabab, izoh, kim tasdiqlagan, summa); izoh «Kassa puli harakati fiskal hujjat emas — OFD'ga yuborilmaydi, offlayn ham ishlaydi».

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `direction` | Yo'nalish | Направление | Tugmalar | Ha | `in\|out` | — | — |
| `amount` | Summa | Сумма | `MoneyInput` | Ha | >0 | — | 9 999 999 999 |
| `reason` | Sabab | Причина | `Select` | Ha (pul harakati rejimida) | `owner_withdrawal` (Egasi oldi) / `collection` (Inkasso) — faqat `out`; `deposit` (Qo'yish) — faqat `in`; `other` (Boshqa) — ikkalasi | — | — |
| `founderId` | Ta'sischi | Учредитель | `Select` (`counterparties.is_founder=true`) | `reason=owner_withdrawal` da va `tenants.legal_form ≠ sole_proprietor` bo'lsa Ha | → payload `counterparty_id` | — | — |
| `account` | Hisob | Счёт | `Select` (`9430`/`9390`/`6310`/`4010`/`4730`) | Yo'q (faqat `reason=other`, faqat Buxgalter/Egasi uchun ko'rinadi) | `6310`/`4010` da `counterparty_id`, `4730` da `employee_id` majburiy | Yo'nalishga ko'ra: `out` → `9430`, `in` → `9390` | — |
| `expenseCategoryId` | Xarajat toifasi | Категория расхода | `Select` (`GET /expense-categories` keshidan) | Ha (faqat "Xarajat" rejimida) | — | — | — |
| `comment` | Izoh | Комментарий | `Textarea` | `reason=other` da Ha | — | — | 1000 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| TASDIQLASH | `cash.deposit` (qo'yish) / `cash.withdraw` (olish) | >50 000 so'm olishda `ApprovalDialog` (tasdiqlovchining `cash.withdraw` limiti summani qoplashi shart) | `cash_movement.created` |
| Xarajat (alohida tugma/rejim) | `cash.withdraw` (limit, standart 50 000 so'm — qaror #23) | Limitdan oshsa `ApprovalDialog` (`kind='cash_withdrawal_over_limit'`) | `expense.created` voqeasi (`source='cash'`; `category_id`, `amount`, `comment`, `tax_type?`, `approval?`) — server `ExpensePostingService` bilan darhol `posted` (`expenses` + `cash_moves`); Kassirda `expenses.create` yo'q — bu yo'l faqat `source='cash'` uchun |

- **Ma'lumot manbai**: outbox `cash_movement.created` / `expense.created`.
- **Holatlar**: `loading` · `empty` — yo'q · `error` (PIN noto'g'ri) · `offline` (to'liq ishlaydi; kassa pul harakati fiskal hujjat emas, OFD'ga yuborilmaydi) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: raqamlar summa kiritadi, `Enter` tasdiqlaydi.
- **Audit/analitika**: `cash_movement.created`, `expense.created`.
- **Bog'liq US**: US-M16-01.

---

## POS-15 — Smena yopishda naqdni sanash

- **Maqsad**: jismoniy sanalgan naqdni kutilgan naqd bilan solishtirish, farqni qayd etish.
- **Rollar/ruxsat**: Kassir (`cash.count.shift`).
- **Route**: `/pos/shift/cash-count`
- **Maket**: `06-ekranlar-umumiy.md` tasvirlangan mazmunga mos sodda forma.

```
┌───────────────────────────────────────┐
│  Kutilgan naqd:     2 100 000 so'm     │
│  Sanalgan naqd:     [            ]     │
│  Karta — terminal:  1 100 000 so'm     │
│  Karta — qo'lda:      400 000 so'm     │
│  Farq:              0 so'm             │
│  Izoh (farq bo'lsa): [            ]    │
│          [  DAVOM ETISH (Z-hisobot) ]  │
└───────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `denominations[].count` | {N} so'mlik kupyuralar soni | Количество купюр {N} сум | `QtyInput` (`−`/`+`) har kupyura nominali uchun | Yo'q | Butun son ≥0; faqat qurilmada hisoblash yordamchisi — voqeaga faqat `counted_cash` ketadi | 0 | 9 999 |
| `countedCash` | Sanalgan naqd | Подсчитанная наличность | `MoneyInput` (kupyuralar kiritilsa — avtomatik Σ nominal × soni, faqat ko'rsatish) | Ha | ≥0 | — | 9 999 999 999 |
| `note` | Izoh | Комментарий | `Textarea` | Farq ≠0 bo'lsa Ha | — | — | 200 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| DAVOM ETISH | `cash.count.shift` | Farq bo'lsa izohsiz bloklanadi | `counted_cash`/`variance_note` lokal saqlanadi; POS-07 "SMENANI YOPISH" bosilganda **bitta** `shift.closed` voqeasi (`counted_cash`, `counted_card_total`, `variance_note`) yuboriladi — `cash_count.recorded` voqeasi **yo'q**; keyin Z-hisobot |

- **Ma'lumot manbai**: lokal hisob + online `GET /api/v1/shifts/{id}` → `running_totals.expected_cash` (kutilgan naqd — boshlang'ich + naqd sotuv − naqd qaytarish + naqd qarz to'lov + qo'yilgan − olingan); `counted_cash`/`variance_note` `shift.closed` payload'ida yuboriladi.
- **Holatlar**: `loading` · `empty` — yo'q · `error` (izohsiz farq — saqlanmaydi) · `offline` (to'liq ishlaydi) · `fiscal-blocked` — to'liq ishlaydi (qaror #43) · `no-permission` — kirilmaydi · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Enter` davom ettiradi.
- **Audit/analitika**: `shift.closed`, `cash_discrepancy_flagged`.
- **Bog'liq US**: US-M16-02.

---

## POS-16 — Uskunalar sozlamasi (printer, skaner, tarozi)

- **Maqsad**: shu kassa qurilmasida chek printerini tanlash va sinash, skanerni tekshirish, tarozi shtrix-kod shablonlari va Do'kon agenti holatini ko'rish, shu kassaga karta terminalini topish, bog'lash va aloqasini tekshirish (qaror #71).
- **Rollar/ruxsat**: kassaga kirgan har qanday POS foydalanuvchisi — printer tanlash/sinov (qurilma-lokal sozlama, serverga yozilmaydi, ruxsat talab qilinmaydi); tarozi prefikslari va Do'kon agenti — faqat ko'rish; tarozi prefikslarini o'zgartirish BO-14 da (`catalog.manage`, `PATCH /stock-settings`), Do'kon agentini boshqarish BO-14 "Do'kon agenti" blokida (`onec.settings.manage`); karta terminalini kassaga bog'lash — `cash_register.manage` (to'liq reyestr — BO-12), terminal holatini ko'rish va aloqani tekshirish — har qanday POS foydalanuvchisi.
- **Route**: `/pos/settings/devices` (kirish — POS-01 "⚙ Uskunalar" va POS-04 printer xatosidagi "Uskunalarni sozlash").
- **Maket**:

```
┌───────────────────────────────────────┐
│ 🟢 ONLAYN       Uskunalar sozlamasi    │
├───────────────────────────────────────┤
│ Chek printeri                          │
│  Ulanish: (•) Web Serial ( ) WebUSB    │
│           ( ) Bluetooth (BLE) ( ) Tizim│
│           ( ) Do'kon agenti (LAN)      │
│           ( ) Bulut printer            │
│  Qog'oz: (•) 58 mm ( ) 80 mm           │
│  Kod sahifa: cp866   Raster: avto      │
│  [ PRINTERNI ANIQLASH ] [ SINOV CHEK ] │
│ Skaner: [ skanerlang...        ] ✓     │
│ Tarozi: 22 = og'irlik (g), 21 = summa  │
│ Do'kon agenti: 🟢 ulangan              │
│ Karta terminali (qaror #71)            │
│  Humo P3 · TID 12345678  (Wi-Fi·ulangan)│
│  Do'kon agenti orqali · 192.168.1.40   │
│  [ TERMINALNI ANIQLASH ] [ ALOQANI     │
│                            TEKSHIRISH ]│
│              [  SAQLASH  ]             │
└───────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `printer.transport` | Ulanish turi | Тип подключения | `RadioGroup` | Ha | `agent_raw\|webserial\|webusb\|webbluetooth\|http_epos\|http_webprnt\|cloud\|system_print` (platformada mavjudlari faol; `24-frontend-arxitekturasi.md` §6.1) | Avto-aniqlash: `agent_raw` (agent topilsa va LAN printer sozlangan bo'lsa) → Web Serial → WebUSB → `http_*` → bulut → tizim printeri | — |
| `printer.paper_width` | Qog'oz kengligi | Ширина ленты | `SegmentedControl` | Ha | `58\|80` (mm) | `58` | — |
| `printer.codepage` | Kod sahifa | Кодовая страница | `Select` | Ha | `cp866` (ESC t 17) | `cp866` | — |
| `printer.render_mode` | Chop rejimi | Режим печати | `Select` | Ha | `auto\|text\|raster` — `auto`: chekda Қ/Ғ/Ҳ bo'lsa raster | `auto` | — |
| `printer.lan_address` | Printer manzili (LAN) | Адрес принтера | `Input` (IP:port) | `agent_raw`, `http_epos`, `http_webprnt` da Ha | IPv4 + port (xususiy LAN) | `:9100` (`agent_raw`) | 32 |
| `printer.cloud_id` | Bulut printer | Облачный принтер | `Select` (BO-14 da ro'yxatga olingan) | `cloud` da Ha | — | — | — |
| `scannerTest` | Skaner sinovi | Проверка сканера | `BarcodeField` | Yo'q | Har qanday kod — o'qilgan qiymat va turi (EAN-13, DataMatrix GS1) ko'rsatiladi | — | 256 |
| `scaleTemplates` | Tarozi shtrix-kodi | Весовой штрихкод | Faqat ko'rsatish | — | `settings.weight_barcode_templates[]` (EAN-13 `PP CCCCC VVVVV K`, prefiks 20–29) | 22 = og'irlik (g), 21 = summa (so'm) | — |
| `agentStatus` | Do'kon agenti | Агент магазина | Faqat ko'rsatish | — | 🟢 ulangan / 🔴 javob yo'q / ⚪ o'rnatilmagan | — | — |
| `cardTerminal` | Karta terminali | Платёжный терминал | Faqat ko'rsatish (`TerminalStatusChip`) | — | Shu kassaga bog'langan faol terminal(lar) (`card_terminals.cash_register_id`, standart — `is_default`): nom, vendor/model, TID, ulanish turi (`adapter`: `agent_ecr`/`cloud`/`android_intent`/`softpos`/`fake`), LAN manzili; holat `online`/`busy`/`offline`/`error`/`unknown` va oxirgi tekshiruv vaqti | — | — |
| `cardTerminalPairing` | Topilgan terminallar | Найденные терминалы | Ro'yxat (`adapter='agent_ecr'` da) | — | Agent `capabilities.card_terminal.devices[]` (`local_id`, `driver`, holat) — `GET 127.0.0.1:47110/v1/card/terminals`; ro'yxatdagi xususiy LAN manzillar | — | — |

- **Qoidalar**: brauzer LAN printerning xom TCP 9100 portiga to'g'ridan-to'g'ri ulana olmaydi — bunday printerlar faqat Do'kon agenti (do'kon Windows kompyuteridagi lokal dastur, qaror #60) orqali; HTTP qabul qiluvchi printerlar (Epson ePOS-Print, Star WebPRNT) va bulut printerlar (Star CloudPRNT — TSP143IV, Epson Server Direct Print — TM-m30III) agentsiz ishlaydi. Web Bluetooth faqat BLE printerlar bilan ishlaydi (klassik SPP — yo'q). Chek matnidagi U+02BB (ʻ) printerga `'` sifatida yuboriladi. Printer sozlamasi shu brauzer/qurilmada saqlanadi. **Karta terminali** (qaror #71): brauzer (https PWA) LAN'dagi terminalga to'g'ridan-to'g'ri ulana olmaydi (xom TCP yo'q, mixed-content va Private Network Access bloklaydi) — Windows veb-kassada terminal faqat Do'kon agenti orqali (`127.0.0.1:47110/v1/card/*`, agent imkoniyati `card_terminal`); terminal manzili faqat xususiy LAN IP. Terminal bog'lanishi qurilmada emas, serverda (`app.card_terminals`) saqlanadi — kassa qurilmasi almashsa ham saqlanib qoladi. Sinov uchun pulli "1 so'm" tranzaksiya qilinmaydi — faqat `health`. MVP'da `FakeCardTerminalAdapter` (`adapter='fake'`, faqat dev/test/staging va demo-tenant) sinov terminali sifatida tanlanadi; real drayver vendor hamkor bilan shartnomadan keyin.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| PRINTERNI ANIQLASH | — | Brauzer qurilma tanlash oynasi (WebUSB/Web Serial/Bluetooth) | Qurilma tanlanadi, `printer.transport` to'ldiriladi |
| SINOV CHEK | — | Yo'q | Sinov matni chop etiladi: «Ўзбекистон Қўқон Ғалла Ҳисоб / Oʻzbekiston gʻalla» — kirill harflari va ʻ to'g'ri chiqishini kassir ko'z bilan tekshiradi |
| TERMINALNI ANIQLASH (qaror #71) | — | Yo'q | Agentdan topilgan terminallar ro'yxati (`/v1/card/terminals`); agent ulanmagan yoki `card_terminal` imkoniyati yo'q — "Do'kon agentini o'rnating / yangilang" |
| Bu kassaga bog'lash | `cash_register.manage` (Egasi; boshqa foydalanuvchida — `ApprovalDialog` orqali Egasi PIN) | "{terminal} shu kassaga bog'lansinmi?" | Tanlangan agent qurilmasi uchun `card_terminals` yozuvi yaratiladi yoki yangilanadi (`POST`/`PATCH /api/v1/card-terminals`, filial va kassa avtomatik, TID terminal javobidan); bitta faol terminal bo'lsa u standart (`is_default`). To'liq tahrir (MID, ekvayer bank, nom) — BO-12 |
| ALOQANI TEKSHIRISH (qaror #71) | — | Yo'q | `health` (pulli tranzaksiya emas): holat chipi yangilanadi (`online`/`busy`/`offline`/`error`), javob vaqti va xato sababi ko'rsatiladi; natija `card_terminals.health_status` ga yuboriladi |
| SAQLASH | — | Yo'q | Lokal sozlama saqlanadi; POS-04 shu sozlama bilan chop etadi |

- **Ma'lumot manbai**: lokal qurilma sozlamasi (alohida Dexie bazasi `erp-device`, `device_settings` — logout'da o'chirilmaydi, `16-offline-sync.md` §12); `GET /api/v1/stock-settings` (`weight_barcode_templates`); Do'kon agenti — lokal HTTP holat so'rovi (`34-1c-agent.md`, qaror #60); karta terminali — `GET /api/v1/card-terminals?cash_register_id=` (lokal keshda ham), agent `GET /v1/card/terminals`, `health` natijasi (qaror #71).
- **Holatlar**: `loading` (qurilmalar aniqlanmoqda) · `empty` (printer topilmadi — "USB/Bluetooth ulanishini tekshiring yoki Do'kon agentini o'rnating") · `error` (Windows'da WebUSB "Could not claim interface" — yo'riqnoma: Web Serial'ni tanlang yoki Zadig bilan WinUSB drayveri; agent javob bermadi; karta terminali javob bermadi — `CARD_TERMINAL_UNREACHABLE`, terminal band — `CARD_TERMINAL_BUSY`; kassaga terminal bog'lanmagan — "Karta qo'lda belgilanadi; terminalni bog'lang") · `offline` (to'liq ishlaydi — sozlama lokal; bulut printer va agent holati oxirgi ma'lum qiymat) · **iOS** — faqat bulut printer yoki elektron chek zahirasi; Web Serial/WebUSB/Bluetooth va tarozi Web Serial yo'q · `no-permission` — yo'q · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Tab` maydonlar bo'ylab, `Enter` saqlaydi, `Esc` orqaga.
- **Audit/analitika**: `device.printer_configured` (lokal, keyingi sinxronda `audit_log`ga), `printer_test_printed`, `printer_test_failed`, `card_terminal_health_checked`.
- **Bog'liq US**: US-M01-07, US-M09-06 (tarozi kodi), US-M01-08 (karta terminali).

---

# B. Back-office PWA ekranlari (BO-01…24)

**Umumiy qobiq** (BO-01, BO-21 dan tashqari; `06-ekranlar-umumiy.md`, `08-dizayn-tizimi.md` §6.2): topbar — sahifa sarlavhasi, qidiruv (`Ctrl+K`), filial tanlovi, bildirishnomalar, til almashtirgich «UZ · RU»; foydalanuvchi kartasi (avatar, ism, rol; bosilganda — chiqish) faqat sidebar pastida, topbar'da yo'q. Sidebar guruhlari — ASOSIY, SAVDO, OMBOR, MOLIYA, BOSHQARUV.

## BO-01 — Kirish (login), tenant/filial tanlash

- **Maqsad**: back-office foydalanuvchilarini (Egasi/Menejer/Buxgalter) autentifikatsiya qilish.
- **Rollar/ruxsat**: Barcha (login ekrani — ruxsat talab qilinmaydi).
- **Route**: `/login`
- **Maket**: (qaror #34)

```
┌─────────────────────────────────────────┐
│               ERP                         │
│         [UZ·RU]                           │
│   Telefon:  [ +998 __ ___ __ __ ]          │
│   Parol:    [ ************ ]               │
│          [  KIRISH  ]                      │
│   ──────────── yoki ────────────           │
│   [  G  Google bilan kirish  ]             │
│   Parolni unutdim?                         │
└─────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `phone` | Telefon | Телефон | `Input` (mask `+998 XX XXX XX XX`) | Ha (telefon yo'li) | `+998` bilan 9 raqam | — | 17 |
| `password` | Parol | Пароль | `Input type=password` | Ha (telefon yo'li) | ≥1 belgi (backend tekshiradi) | — | 128 |
| `branchId` (login'dan keyin, bir nechta filial bo'lsa) | Filial | Филиал | `Select` | Ha (ko'p filial bo'lsa) | — | Birinchi filial | — |

- **Amallar** (qaror #34):

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| KIRISH | — | Yo'q | Front-channel Authorization Code+PKCE (`14-autentifikatsiya-oauth2.md` §2.1) → BFF cookie |
| **Google bilan kirish** | — | Yo'q | Google OIDC'ga redirect (bizning OAuth AS'da tashqi provayder) → qaytgach BFF cookie; birinchi marta kirishda hisob telefon raqami bilan bog'lanishi so'raladi (STIR/fiskal uchun) |
| Parolni unutdim | — | Yo'q | OTP oynasi (`purpose=recovery`) — kod birinchi navbatda **Telegram bot**ga, Telegram ulanmagan bo'lsa **SMS**ga (zaxira) → yangi parol o'rnatish |
| Ma'lumotlarimni yuklab olish (faqat `subscription-restricted`da ko'rinadi) | — | OTP (`purpose=data_export`) — Telegram bot birinchi, SMS zaxira | Bir martalik eksport havolasi (24 soat, qaror #51) |
| To'lash (Click/Payme, faqat `subscription-restricted`da) | — | Yo'q | `pay_url`ga o'tish |

- **Ma'lumot manbai**: `POST /auth/login`, `GET /auth/google/start` → `GET /auth/google/callback` (qaror #34), `POST /auth/otp/request`, `POST /auth/otp/verify`, `GET /billing/pay`, `POST /billing/export-my-data`.
- **Holatlar**: `loading` · `empty` — yo'q · `error` ("Telefon yoki parol noto'g'ri", #18 — qaysi qism xato ekani oshkor qilinmaydi) · `offline` (PWA offline ombor/hisobot ko'rishga ruxsat beradi, lekin yangi login internetsiz ishlamaydi) · `no-permission` — yo'q · `subscription-restricted` — banner + to'lov havolasi + eksport havolasi, parol maydoni faol (identifikatsiya uchun), token berilmaydi.
- **Klaviatura**: `Enter` kirishni yuboradi.
- **Audit/analitika**: `login_success`, `login_failed`, `account_locked`, `otp_requested`, `otp_verified`, `data_export_during_restriction`.
- **Bog'liq US**: US-M13-06, US-M17-03.

---

## BO-02 — Dashboard (Egasi/Menejer)

- **Maqsad**: kunlik/haftalik savdo, qoldiq, qarzdorlik, ogohlantirishlarni bir joyda ko'rsatish.
- **Rollar/ruxsat**: Egasi, Menejer (`reports.sales.view` + `reports.finance.view`).
- **Route**: `/app/dashboard`
- **Maket**: `06-ekranlar-umumiy.md` §6 BO-02 wireframe'i.
- **Maydonlar**: `periodFilter` — Davr — Период — `Select` (Bugun/Hafta/Oy) — majburiy emas — default "Bugun"; `branchFilter` — Filial — Филиал — `Select` — majburiy emas — default "Barchasi".
- **Joylashuv**: salomlashish (sana, «Xayrli kun, {ism}») va davr tugmalari (Bugun / Hafta / Oy); filial — topbar tanlovidan. KPI kartalari: **Bugungi savdo** (kecha bilan), **Cheklar** (o'rtacha chek), **Mijozlar qarzi** (qarzdorlar soni, muddati o'tganlar), **Ombor qiymati** (kam qolgan tovarlar soni); **«Savdo — oxirgi 7 kun»** ustunli grafik (mln so'm, bugungi ustun ajratilgan); **«Diqqat talab qiladi»** — ogohlantirishlar ro'yxati (offline kassa, davlat hisoboti farqi, imzo kutayotgan e-fakturalar, tasdiqlash so'rovlari va h.k.; har biri tegishli ekranga havola); **«Eng ko'p sotilgan»** (top-5, miqdor bilan); **«AI yordamchi»** mini-paneli (`ai.chat.use` bo'lsa): kunning qisqa tushuntirishi, tez savol chiplari, savol maydoni va «So'rash» → BO-13 da davom etadi.
- **Amallar**: karta/ogohlantirish bosilganda tegishli ekranga o'tish (masalan "Davlat hisoboti" → BO-10).
- **Ma'lumot manbai**: `GET /api/v1/reports/dashboard?period=today|week|month&branch_id=` (savdo, cheklar, o'rtacha chek, top tovarlar, `alerts[]`); 7 kunlik grafik — `GET /api/v1/reports/sales?group_by=day&date_from=&date_to=&branch_id=`; mijozlar qarzi — `GET /api/v1/reports/debts-aging?direction=receivable`; ombor qiymati — `GET /api/v1/reports/stock?branch_id=`; AI paneli — `POST /api/v1/ai/chat`.
- **Holatlar**: `loading` (skeleton kartalar) · `empty` (yangi tenant, ma'lumot yo'q) · `error` (hisoblash xatosi, "qayta urinish") · `offline` ("Oxirgi yangilanish: N daqiqa oldin" belgisi) · `no-permission` — Kassir/Omborchi/Buxgalter uchun ko'rinmaydi (sidebar'da yo'q) · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K` tezkor navigatsiya.
- **Audit/analitika**: `dashboard_viewed`.
- **Bog'liq US**: US-M12-01, US-M11-03.

---

## BO-03 — Ombor qoldig'i (+ Ko'chirishlar tab)

- **Maqsad**: qoldiqni ko'rish/boshqarish, ko'chirishlar va ularning e-TTN holatini kuzatish, inventarizatsiya farqini tasdiqlash, hisobdan chiqarish. MVP UI'da filialda bitta ombor (avtomatik tanlanadi, qaror #54).
- **Inventarizatsiya farqi** (qaror #53): har qator uchun `expected = snapshot_qty(started_at) + Σ stock_moves(started_at < moved_at ≤ counted_at)` (`count_lines.counted_at` — qator sanalgan qurilma vaqti, offline sanashda ham, `server_time` ofseti bilan tuzatilgan), farq `counted − expected`; sanash davomidagi sotuv/kirim farqqa kirmaydi.
- **Rollar/ruxsat**: Menejer, Omborchi (`stock.view`); ko'chirish ro'yxati — `stock.view`; ko'chirish yaratish/jo'natish — `transfer.create`; e-TTN imzolash — `einvoice.sign` (Egasi/Buxgalter); hisobdan chiqarish — `stock.writeoff`; inventarizatsiya farqini tasdiqlash — `stock.count.post`.
- **Route**: `/app/warehouse/stock`
- **Maket**: `06-ekranlar-umumiy.md` §6 BO-03 wireframe'i + "Ko'chirishlar" tab (holat: yo'lda/qabul qilindi/farq bilan; **e-TTN ustuni** — `transfers.ettn_ref` va `ettn_documents.status`: imzo kutilmoqda (`pending_signature`) / yuborilmoqda (`sending`) / ro'yxatdan o'tdi (`registered`) / qabul tomon tasdiqladi (`accepted`) / rad etildi (`rejected`) / xato (`failed`) / talab qilinmaydi (`transport_mode='on_foot_or_public'`), qaror #63) + **"Inventarizatsiyalar" tab**: ro'yxat `GET /api/v1/stock-counts?status=review`, qator — kutilgan/sanalgan/farq/summa; tugmalar "Farqni tasdiqlash" (`stock.count.post`, `POST /stock-counts/{id}/post`, dialog «Kamomad X so'm, ortiqcha Y so'm hisobga olinadi») va "Bekor qilish" (`POST /stock-counts/{id}/cancel`).
- **Joylashuv**: tablar «Qoldiq» / «Ko'chirishlar» (yo'ldagi/kechikkan soni badge'i) / «Inventarizatsiyalar» (`review` soni badge'i); sahifa amallari — Eksport, Hisobdan chiqarish, Inventarizatsiya, Ko'chirish; kam qoldiq va muddati yaqin partiyalar banneri («Faqat kamlarini ko'rsatish» → `lowStockOnly`, «Xaridnoma tuzish» → BO-04 yangi xaridnoma, `purchases.create`); KPI kartalari — Ombor qiymati (tannarxda, pozitsiyalar soni), Kam qoldiq, Muddati yaqin partiyalar (7 kun), Yo'ldagi ko'chirishlar; qoldiq jadvali ustunlari — tovar (birlik, kategoriya, markirovka belgisi), shtrix-kod, qoldiq, min., tannarx (o'rtacha), qiymat, holat («Kam qoldi» / «Yetarli» + «Muddati N kunda»); pastda sahifadagi jami, oxirgi yangilanish vaqti, sahifalash. «Qoldiq» tabi ostida «Ko'chirishlar va e-TTN» qisqa bloki (oxirgi 7 kun: hujjat, yo'nalish, tashish usuli, yuborilgan, pozitsiyalar, summa, holat, e-TTN holati, qator amali — «E-TTN imzolash» / «Qabul qilish» / «Farqni ko'rish» / «Qo'lda ro'yxatga olish»; «Barcha ko'chirishlar» → «Ko'chirishlar» tabi).
- **Maydonlar**: `search` — Qidirish — Поиск — `Input` — yo'q — max 64; `branchId` — Ombor/filial — Склад/филиал — `Select` (**"Barchasi" varianti bor**, bo'sh = konsolidatsiya) — ha — default joriy filial; `lowStockOnly` — Faqat kam qoldiq — Только низкий остаток — `Switch` — yo'q — default o'chiq; `expiringWithinDays` — "Muddati 7 kunda tugaydi" filtri — `GET /stock-lots?expiring_within_days=7` — yo'q — default o'chiq.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Ko'chirish | `transfer.create` | Yo'q | BO-04 uslubidagi forma/sheet |
| E-TTN imzolash ("Ko'chirishlar" tabi, `posted` ko'chirish qatorida) | `einvoice.sign` | E-IMZO kalit tanlash | `POST /api/v1/ettn-documents/{id}/sign-challenge` → E-IMZO → `POST /api/v1/ettn-documents/{id}/submit-signed` |
| Qo'lda ro'yxatga olish | `transfer.create` | Operator hujjat raqami va sanasi | `POST /api/v1/ettn-documents/{id}/register-manual` (`{operator_doc_id, doc_date}`) |
| Jo'natish | `transfer.create` | Yo'q | `POST /api/v1/transfers/{id}/send` — faqat e-TTN `registered` yoki `transport_mode='on_foot_or_public'` |
| E-TTN tasdiqlash / rad etish (qabul tomonida) | `transfer.receive` + `einvoice.sign` | E-IMZO; rad etishda sabab | `POST /api/v1/ettn-documents/{id}/sign-challenge?action=accept\|reject` → `POST /api/v1/ettn-documents/{id}/accept` \| `/reject` |
| Inventarizatsiya | `stock.count.create` | "Inventarizatsiyani boshlaysizmi?" | `POST /api/v1/stock-counts` (`{warehouse_id, doc_date, product_ids?, responsible_user_id?}`, `stock.count.create`) → POS-10 |
| Hisobdan chiqarish | `stock.writeoff` | — | Partiya, miqdor, sabab (`expired\|damaged\|gift\|other`; `expired_return` — POS-05 dan avtomatik qoralama); `reason=gift` tanlanganda `giftKind` (`promo_justified\|other`, standart `other`) va `promoOrderRef` (`promo_justified` da majburiy) → `POST /write-offs` → `/post`; faqat online (qaror #54) |
| Eksport | `reports.export` | Yo'q | `POST /api/v1/reports/stock/export` → poll `GET /api/v1/reports/export-jobs/{job_id}` |

- **Ma'lumot manbai**: `GET /api/v1/stock-balances?warehouse_id=&low_stock=&search=`; "Barchasi" filial — `GET /api/v1/reports/stock?branch_id=` (bo'sh = konsolidatsiya); `GET /api/v1/transfers?status=`, `GET /api/v1/ettn-documents?transfer_id=`; "Inventarizatsiyalar" tab — `GET /api/v1/stock-counts?status=review`; `GET /stock-lots?expiring_within_days=7`.
- **Holatlar**: `loading` · `empty` (ombor bo'sh — yangi filial) · `error` (ma'lumot sinxron emas, "Oxirgi yangilanish") · `offline` (faqat ko'rish, IndexedDB oxirgi nusxa; hisobdan chiqarish o'chiq) · `no-permission` — Kassir/Buxgalterga faqat ko'rish (K), yaratish/tasdiqlash yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K` qidiruv.
- **Audit/analitika**: `stock_viewed`, `transfer_list_viewed`, `stock_count_review_viewed`, `stock_count.posted`, `write_off.posted`.
- **Bog'liq US**: US-M04-01, US-M04-02, US-M04-03, US-M06-03, US-M04-06, US-M05-02, US-M05-03.

---

## BO-04 — Xaridnoma yaratish, yetkazib beruvchiga to'lov/qaytarish

- **Maqsad**: xarid buyurtmasi yaratish, AI-03 OCR orqali qog'oz hujjat kiritish, to'lov va qaytarish qayd etish, kirimlarni o'tkazish, yetkazib beruvchiga bo'lgan qarzni ko'rish.
- **Rollar/ruxsat**: Menejer — `purchases.create`; Omborchi — `purchases.receive`; Buxgalter — `purchases.post`, `purchases.pay`, `purchases.return`; AI-03 tugmasi — `purchases.receive` + `ai.ocr.use`.
- **Route**: `/app/purchases`
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│ [Xaridnomalar] [Kirimlar] [Yetkazib beruvchiga to'lov]│
│ [Qaytarish] [Men qarzdorman]                       │
├──────────────────────────────────────────────────┤
│  Yetkazib beruvchi: [ "Mega Trade" MChJ  ▾ ]       │
│  [ 📷 Qog'oz hujjatdan o'qish (AI-03) ]            │
│  ┌────────────────────────────────────────────┐   │
│  │ Tovar          Miqdor    Narx     Jami      │   │
│  │ Coca-Cola 1.5L   50    12 000   600 000     │   │
│  └────────────────────────────────────────────┘   │
│         [  XARIDNOMANI YUBORISH  ]                │
└──────────────────────────────────────────────────┘
```

Joylashuv: sahifa amallari — «Qog'oz hujjatdan o'qish (AI)», «Yangi xaridnoma»; markirovkali kirim qabul xabarnomasi muddati yaqin bo'lsa sariq banner (hujjat, tovar, qolgan vaqt) + «Imzolashga o'tish» → «Kirimlar» tabidagi shu hujjat. «Xaridnomalar» tabi — ro'yxat–tafsilot: chapda xaridnomalar ro'yxati (qidiruv: raqam yoki yetkazib beruvchi; raqam, sana, summa, yetkazib beruvchi, holat chipi), o'ngda tanlangan xaridnoma: sarlavha (yetkazib beruvchi, STIR, sana, kim tuzdi), holat bosqichlari, qatorlar jadvali (tovar, miqdor, narx (QQS bilan), jami; QQSsiz summa, QQS, jami), bog'langan e-faktura kartasi (holat, raqam, kim imzolagan), bog'langan kirim kartasi (holat, provodka izohi, «Kirimni ochish» / «Kirimni o'tkazish» — faqat `purchases.post`), «Yetkazib beruvchiga to'lov» paneli (joriy qarzimiz 6010 va kirim o'tkazilgandan keyingi qarz, to'lov usuli, summa, sana, taqsimot jadvali, provodka izohi, «To'lovni qayd etish»), «E-ishonchnoma» kartasi (holat, raqam, ishonchli shaxs, muddat, kim imzolagan; «Ko'rish», «Yangi ishonchnoma»).

Beshinchi tab **"Men qarzdorman"** — yetkazib beruvchiga bo'lgan qarzimiz ro'yxati: `GET /api/v1/reports/debts-aging?direction=payable` (yetkazib beruvchi, summa, muddat), qatordan "To'lash" → mavjud "To'lov qayd etish" formasi; ruxsat `purchases.pay` (ko'rish — `reports.finance.view`).

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `supplierId` | Yetkazib beruvchi | Поставщик | `Combobox` | Ha | Mavjud/yangi | — | — |
| `lines[].qty` | Miqdor | Количество | `QtyInput` | Ha | >0 | — | — |
| `lines[].price` | Narx | Цена | `MoneyInput` | Ha | >0 | — | — |
| `ocrPhoto` | Hujjat fotosi | Фото документа | Fayl yuklash (`POST /attachments`) | Yo'q | JPEG/PNG, ≤10MB (`17-api-umumiy.md` §12) | — | — |
| `payment.method` | To'lov usuli | Способ оплаты | `Select` | Ha (to'lov tabida) | `cash\|bank` | — | — |
| `payment.cashRegisterId` | Kassa | Касса | `Select` | Ha (`method=cash`da) | — | — | — |
| `payment.shiftId` | Smena | Смена | `Select` | Ha (`method=cash`da) | Tanlangan kassaning ochiq smenasi | Ochiq smena | — |
| `payment.allocations[]` | Taqsimot (kirim hujjati + summa) | Распределение | Jadval | Ha | Standart — eng eskisidan avtomatik | Avtomatik | — |
| `payment.docDate` | Hujjat sanasi | Дата документа | `Calendar` | Ha | — | Bugun | — |
| `payment.amount` | To'lov summasi | Сумма платежа | `MoneyInput` | Ha (to'lov tabida) | >0; qarzdan oshsa — ogohlantirish bilan ruxsat, ortig'i avans (4310); `settings.supplier_overpay_policy='block'` bo'lsa `422 SUPPLIER_OVERPAY_BLOCKED` (qaror #47) | — | — |
| `poa.employeeId` | Ishonchli shaxs (xodim) | Доверенное лицо | `Select` (xodimlar) | Ha (e-ishonchnoma berishda) | Tenant xodimi | Xaridnomadagi Omborchi | — |
| `poa.validTo` | Amal qilish muddati | Срок действия | `Calendar` | Ha (e-ishonchnoma berishda) | ≥ bugun | +10 kun | — |
| `return.receiptId` | Kirim hujjati | Документ поступления | `Select` (`goods_receipts`, `posted`) | Ha (qaytarish tabida) | — | — | — |
| `return.docDate` | Hujjat sanasi | Дата документа | `Calendar` | Ha (qaytarish tabida) | — | Bugun | — |
| `return.lines[]` | Qaytariladigan qatorlar (`receiptLineId`, `lotId`, `qty`) | Строки возврата | Jadval | Ha (≥1) | `qty` >0, ≤ partiya qoldig'i | — | — |
| `return.reason` | Qaytarish sababi | Причина возврата | `Select` | Ha (qaytarish tabida) | `expired\|damaged\|excess\|other` | — | — |

AI-03 sariq belgi chegarasi: summa <95%, sana <90%, miqdor/nom <80%; past ishonch — xato emas, `200` javobdagi `low_confidence_fields[]` bo'yicha maydon sariq (qaror #55); model — Haiku 5.5, past ishonchda Sonnet 5.5 ga ko'tariladi; **har bir hujjat** foydalanuvchi "Tasdiqlash" bosmaguncha saqlanmaydi. Tugma ko'rinishi: `ai.ocr_enabled=false` (aniqlik sinovi o'tilmaguncha — 26 #19 (OQ-078)) bo'lsa ko'rinmaydi; tenant AI xizmatiga chet elga uzatishga rozilik bermagan bo'lsa (`settings.ai_cross_border_enabled=false`, qaror #61) tugma o'chiq va «Rasmni AI'ga yuborish uchun BO-14 da rozilik bering» izohi ko'rsatiladi.

**E-ishonchnoma** (qaror #63): yetkazib beruvchidan tovar olish uchun do'kon **o'z xodimiga** (odatda Omborchi) EDO operatori orqali (Faktura.uz PowerOfAttorney) e-ishonchnoma beradi — e-fakturadan **oldin**; yetkazib beruvchi uni tekshirib e-fakturani shu asosda shakllantiradi, e-fakturani ishonchli shaxs E-IMZO bilan imzolaydi. Ishonchnoma bo'lmasa e-fakturani Buxgalter (rahbar ERI) imzolaydi — tizim bloklamaydi. Saqlanadi: `powers_of_attorney` (holatlar `draft → pending_signature → sending → sent → accepted | rejected`; `sending → failed → sending`; `draft | pending_signature → cancelled`), kirimda `goods_receipts.poa_id`/`poa_number`.

**Kirim muddati (markirovka)**: markirovkalangan tovar kirimida Asl belgisi qabul xabarnomasi tovar guruhi muddatida imzolanishi kerak — umumiy 3 ish kuni, ayrim guruhlarda (suv/ichimlik, dori, o'simlik yog'i) 72 soat; "Kirimlar" tabida qolgan vaqt ustuni va ogohlantirish, bloklamaydi.

**Yetkazib beruvchiga qaytarish va QQS**: asl kirim QQS bilan bo'lgan va 12 oy ichida qaytarilsa, hujjat "yetkazib beruvchidan qo'shimcha (salbiy) e-faktura kutilmoqda" holatiga o'tadi; kiruvchi QQS kamaytirilishi qo'shimcha e-faktura qabul qilingan davrda yoziladi (BO-15). 12 oydan keyin — "teskari realizatsiya" ogohlantirishi (chiquvchi e-faktura, Buxgalter tasdig'i bilan).

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Qog'oz hujjatdan o'qish (AI-03) | `purchases.receive` + `ai.ocr.use` | Past-ishonchli maydonlar sariq, foydalanuvchi "Tasdiqlash" bosmaguncha saqlanmaydi | `POST /api/v1/attachments` → `POST /api/v1/ai/ocr/jobs` (`doc_type_hint=purchase`) → poll `GET /api/v1/ai/ocr/jobs/{job_id}` → `POST /api/v1/ai/ocr/jobs/{job_id}/confirm` |
| XARIDNOMANI YUBORISH | `purchases.create` | Yo'q | `POST /api/v1/purchase-orders` → `POST /api/v1/purchase-orders/{id}/send` |
| O'tkazish (Kirimlar tabida) | `purchases.post` | Yo'q | `GET /goods-receipts?status=draft` dan tanlangan hujjatni `POST /goods-receipts/{id}/post` bilan o'tkazadi — qoldiq shu paytda oshadi |
| E-fakturadan kirim | `purchases.receive` | Yo'q | BO-15'dan `POST /goods-receipts/from-einvoice/{einvoice_id}` |
| To'lov qayd etish | `purchases.pay` | Qarzdan oshsa: «Ortiqcha {summa} avans sifatida yoziladi» | `POST /api/v1/supplier-payments`, kreditorlik kamayadi |
| E-ishonchnoma berish | `purchases.create` (yaratish), `einvoice.sign` (imzo) | Xodim + muddat; E-IMZO imzo | `POST /api/v1/powers-of-attorney` (`purchases.create`) → `sign-challenge` → E-IMZO → `submit-signed` (`einvoice.sign`); raqam operator qabul qilgach (`sent`) xaridnomaga bog'lanadi |
| Qaytarish qoralamasi | `purchases.return` | Yo'q | `POST /api/v1/supplier-returns` (qoralama) |
| Qaytarishni o'tkazish | `purchases.post` | "Qaytarishni tasdiqlaysizmi?" | `POST /api/v1/supplier-returns/{id}/post`, ombor/kreditorlik tuzatiladi |

- **Ma'lumot manbai**: `GET/POST /api/v1/purchase-orders` + `POST /api/v1/purchase-orders/{id}/send`; `GET /api/v1/counterparties?is_supplier=true`, `GET /api/v1/counterparties/{id}/debt-balance`; `GET /api/v1/goods-receipts`, `POST /api/v1/goods-receipts/{id}/post`; `POST /api/v1/attachments` → `POST /api/v1/ai/ocr/jobs` (`doc_type_hint=purchase`) → poll → `/confirm` (AI-03); `POST /api/v1/supplier-payments`; `POST /api/v1/supplier-returns` + `POST /api/v1/supplier-returns/{id}/post`; `POST /api/v1/powers-of-attorney` + `/sign-challenge` + `/submit-signed`; `GET /api/v1/reports/debts-aging?direction=payable`.
- **Holatlar**: `loading` · `empty` (yangi xaridnoma) · `error` (AI OCR noto'g'ri o'qidi — qo'lda tuzatish shart; `SUPPLIER_OVERPAY_BLOCKED`) · `offline` (PWA'da yangi xaridnoma yaratish cheklangan, internet talab qilinadi) · `no-permission` — Kassir/Omborchiga to'lov/qaytarish yopiq (faqat Omborchi — qabul, bu ekranda emas POS-08da) · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `purchase_order.created`, `ai_ocr_used`, `goods_receipt.posted`, `supplier_payment.created`, `supplier_return.created`, `power_of_attorney.issued`.
- **Bog'liq US**: US-M07-01, US-M07-02, US-M07-03, US-M07-04, US-M07-05, US-M08-11.

---

## BO-05 — Narxlar va chegirma qoidalarini boshqarish

- **Maqsad**: tovar narxini yangilash (tarix bilan), avtomatik chegirma qoidalarini sozlash.
- **Rollar/ruxsat**: Menejer (`prices.edit`, `discount.rule.manage`); >limit narx o'zgarishi — `prices.approve` (Egasi).
- **Route**: `/app/catalog/prices`
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│ [Narxlar] [Chegirma qoidalari]                     │
├──────────────────────────────────────────────────┤
│  Tovar              Joriy narx   Yangi narx         │
│  Coca-Cola 1.5L      18 000      [ 19 000 ]        │
│                                [ SAQLASH ]          │
└──────────────────────────────────────────────────┘
```

- **"Chegirma qoidalari" bloki** (`rule.*` maydonlari, "Qoida yaratish" amali, `discount-rules` manbai) — **MVP'dan keyin** (qaror #33, US-M03-02); MVP'da tab ko'rsatilmaydi.
- **Joylashuv (MVP)**: filtrlar — kategoriya (`category_id`), tovar qidirish (nom yoki shtrix-kod), amal qilish sanasi (`effectiveFrom`, butun partiya uchun bitta); limitdan katta o'zgarish bo'lsa sariq banner («N ta o'zgarish 10% dan katta — Egasi tasdig'i kerak», tovar, eski → yangi narx, foiz; «Tasdiqlash navbati» → BO-16); «Chakana narxlar» jadvali — tovar (rus nomi bilan), tannarx, joriy narx, ustama %, yangi narx (`newPrice`, tahrirlanadi), o'zgarish %, holat (o'zgarmagan / o'zgaradi / tasdiq kerak); pastda «N ta o'zgarish · {sana} dan amal qiladi», «Bekor qilish», «Saqlash» (`Ctrl+S`). O'ng panel — tanlangan tovar: **«Narx tarixi»** (`GET /products/{id}/prices`: narx, o'zgarish, sana/kim) va `nameRu` maydoni; **«Doimiy mijoz chegirmasi»** — `standingDiscountPct` belgilangan mijozlar ro'yxati (faqat ko'rish; tahrirlash — BO-06 «Mijoz kartasi»).
- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `newPrice` | Yangi narx | Новая цена | `MoneyInput` | Ha | >0 | Joriy narx | — |
| `effectiveFrom` | Amal qilish sanasi | Дата применения | `Calendar` | Ha | ≥ bugun | Bugun | — |
| `nameRu` (qaror #29) | Rus tilidagi nomi | Название на русском | `Input` | Yo'q (ixtiyoriy) | Max 255 | Bo'sh | 255 — chekda "{name} / {nameRu}" ko'rinishida chiqadi (bo'sh bo'lsa faqat `name`), `products.name_ru` |
| `rule.category` | Kategoriya | Категория | `Select` | Ha (qoida) | — | — | — |
| `rule.percent` | Chegirma % | Скидка % | `Input` number | Ha (qoida) | 0–100 | — | 100 |
| `rule.startDate`/`endDate` | Boshlanish/tugash | Начало/Конец | `Calendar` | Ha (qoida) | `endDate` ≥ `startDate` | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| SAQLASH (narx) | `prices.edit` | Limitdan katta o'zgarishda `pending_approval` → BO-16 | `POST /api/v1/price-changes` → `POST /api/v1/price-changes/{id}/post` (javob `posted` yoki `pending_approval`; BO-16 da rad etilsa — `rejected`) — eski narx tarixga, yangi narx saqlanadi |
| SAQLASH (`nameRu`) (qaror #29) | `catalog.manage` | Yo'q | `PATCH /api/v1/products/{id}` (`name_ru`) — tasdiqlash shart emas, darhol kuchga kiradi |
| Qoida yaratish | `discount.rule.manage` | Yo'q | `discount_rule.created` |

- **Ma'lumot manbai**: `GET /api/v1/products/{id}/prices` (tarix) + `POST /api/v1/price-changes` → `POST /api/v1/price-changes/{id}/post`; `GET/POST /api/v1/discount-rules` (+ `PATCH /{id}`, `POST /{id}/archive`).
- **Holatlar**: `loading` · `empty` (narx belgilanmagan) · `error` (manfiy narx/chegirma) · `offline` (faqat ko'rish) · `no-permission` — Kassir/Omborchiga faqat ko'rish · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `price_changed`, `price_change_pending_approval`, `discount_rule.created`.
- **Bog'liq US**: US-M09-01, US-M09-02, US-M03-02.

---

## BO-06 — Nasiya/qarzdorlar ro'yxati va eslatmalar

- **Maqsad**: qarzdorlarni ko'rish, mijoz kartasi/kredit limitini boshqarish, AI-06 eslatma matnini tasdiqlash, to'lov qabul qilish, shubhali qarzni belgilash/kechish.
- **Rollar/ruxsat**: Menejer, Buxgalter — ko'rish `reports.finance.view` (eskirish hisoboti) + `reports.sales.view` (qarz daftari); to'lov qabul qilish `debts.payment.accept`; eslatma yuborish `debts.remind`; mijoz kartasi/limit `debts.limit.manage`; shubhali belgilash/kechish — `debts.forgive` (faqat Egasi).
- **Route**: `/app/debts`
- **Maket**: `06-ekranlar-umumiy.md` tasvirlangan mazmunga mos jadval + AI eslatma paneli + **"Mijoz kartasi" Sheet**.

```
┌──────────────────────────────────────────────────┐
│  [Bugun/o'tgan va'da] [60+ kun] [Barchasi]         │
│  Mijoz          Qarz       Muddat   AI eslatma     │
│  Aliyev Botir   450 000    15 kun   [Ko'rish/Yubor]│
│  [ TO'LOV QABUL QILISH ] [ Mijoz kartasi ]         │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `periodFilter` — `Select`; **"Bugun/o'tgan va'da" tab** — `due_date ≤ bugun` (US-M08-09); **"60+ kun" tab** — eslatma ro'yxati, tizim avtomatik belgilamaydi (US-M08-10, tavsiya #9); `limit_exceeded_offline=true` filtri (Egasi); `payment.amount` — To'lov summasi — Сумма платежа — `MoneyInput` — ha — >0, ≤ joriy qarz (ortig'i rad — `debt_payment_exceeds_balance`; qaror #45); `payment.method` — faqat `bank` (bank o'tkazmasi, kassasiz, fiskal chek yo'q — qaror #67; naqd/karta/QR qarz to'lovi — faqat POS-13); `payment.docDate`, `payment.branchId` (majburiy).

  **Joylashuv**: tepada «Jami debitorlik (4010)» kartasi va eskirish guruhlari (guruh, qarzdorlar soni, summa, ulush — `debts-aging` bucket'lari); tablar «Bugun/o'tgan va'da» · «60+ kun» · «Limitdan oshgan» (`limit_exceeded_offline=true`, Egasi) · «Barchasi» (har birida soni); mijoz qidirish (ism yoki telefon); jadval — mijoz (telefon), qarz, limit (oshgan bo'lsa «oshgan (offline)» belgisi), oxirgi to'lov (summa, sana), va'da sanasi (holat chipi), kun, eslatma; sahifalash va ko'rsatilganlar jami. O'ng panel — tanlangan mijoz: ism, telefon, Telegram ulanganligi, «Mijoz kartasi» (Sheet), qarz, limit · chegirma; **«AI eslatma qoralamasi · ko'rib chiqing»** — matn, «Telegram orqali yuborish», «Tahrirlash», izoh «Telegram ulanmagan mijozga SMS orqali (zaxira). Matn avtomatik yuborilmaydi»; **«To'lov qabul qilish»** — summa, sana, usul «Bank o'tkazmasi», filial, izoh «Kassasiz, fiskal chek chiqmaydi · Dt 5110 / Kt 4010. Naqd, karta yoki QR bilan qarz to'lovi — kassada (Qarz daftari)»; pastda «Ortiqcha to'lovlar» bloki.

  **"Ortiqcha to'lovlar" bloki** (qaror #67): offline POS qarz to'lovida qarzdan ortiq qabul qilingan summalar — `sync_exceptions(kind='debt_overpayment_offline')` ro'yxati (mijoz, `debt_payments.unallocated_amount`, sana, kassa); ortig'i `Kt 6310` (olingan bo'nak) da turadi; amallar "Qaytarish" va "Keyingi qarzga hisoblash" (Buxgalter/Egasi, `accounting.post`).

  **"Mijoz kartasi" Sheet**: `name`, `phone`, `kind` (`person|company`), `stir`, `legal_address`, `bank_account`, `bank_mfo` (B2B e-faktura uchun), `creditLimit` (`MoneyInput`, bo'sh = limitsiz), `standingDiscountPct` (0–100), `notifyConsent` (`Switch`); saqlash — `PATCH /api/v1/counterparties/{id}` (`version` bilan), ruxsat `debts.limit.manage`.

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| AI eslatmani ko'rish/yuborish | qoralama — `ai.chat.use`; yuborish — `debts.remind` | Yo'q (matn ko'rib chiqiladi, keyin yuboriladi) | (qaror #34) Telegram orqali birinchi navbatda, SMS — zaxira |
| TO'LOV QABUL QILISH (bank o'tkazmasi) | `debts.payment.accept` | Yo'q | `POST /debt-payments` (`method='bank'`; boshqa qiymat → `422 VALIDATION_ERROR`, `validation.debt_payment_backoffice_bank_only`) — kassasiz, **fiskal chek yo'q**, provodka `Dt 5110 / Kt 4010` (qaror #67); daromad/QQS sotuv kuni allaqachon tan olingan. Naqd/karta/QR qarz to'lovi va uning `debt_settlement` cheki — POS-13 |
| Ortiqcha to'lovni qaytarish ("Ortiqcha to'lovlar" bloki) | `accounting.post` | Summa va sabab | POS-14 yoki `POST /api/v1/cash-movements` (`reason='other'`, `direction='out'`, `account='6310'`, `counterparty_id`) |
| Keyingi qarzga hisoblash ("Ortiqcha to'lovlar" bloki) | `accounting.post` | «{summa} keyingi qarzga hisoblanadi» | `POST /api/v1/ledger-adjustments` (`Dt 6310 / Kt 4010`, `analytics.counterparty_id`) |
| Shubhali deb belgilash | `debts.forgive` (faqat Egasi) | Sabab majburiy | `POST /debt-doubtful-flags` — provodka **yo'q**, faqat belgi |
| Belgini olib tashlash | `debts.forgive` | Yo'q | `POST /debt-doubtful-flags/{id}/unflag` |
| Qarzni kechish (hisobdan chiqarish) | `debts.forgive` (faqat Egasi) | Sabab majburiy + "Bu amal provodka yaratadi" | `POST /debt-writeoffs` → `/post` |

- **Ma'lumot manbai**: `GET /api/v1/reports/debts-aging?direction=receivable&bucket=` (+ `limit_exceeded_offline=`, `branch_id=`); `POST /api/v1/ai/debt-reminders/draft` → `POST /api/v1/ai/debt-reminders/send` (AI-06); `POST /api/v1/debt-payments` (`method='bank'`); `GET /api/v1/sync-exceptions?kind=debt_overpayment_offline`, `POST /api/v1/cash-movements`, `POST /api/v1/ledger-adjustments`; `POST /api/v1/debt-doubtful-flags`, `POST /api/v1/debt-doubtful-flags/{id}/unflag`; `GET /api/v1/counterparties/{id}/debt-ledger`; `PATCH /api/v1/counterparties/{id}`.
- **Holatlar**: `loading` · `empty` (qarzdor yo'q) · `error` (aloqa ma'lumoti yo'q; `debt_payment_exceeds_balance`) · `offline` (faqat ko'rish) · `no-permission` — Kassir/Omborchiga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `debt_reminder_sent`, `debt_payment.created`, `debt_doubtful_flagged`, `debt_doubtful_unflagged`, `debt_writeoff.posted`.
- **Bog'liq US**: US-M08-03, US-M08-06, US-M08-09, US-M08-10, US-M08-04, US-M08-11.

---

## BO-07 — QQS ichki hisob-kitobi

- **Maqsad**: QQS bazasi/summasini ko'rish, qizil faktura kreditini kuzatish.
- **Rollar/ruxsat**: Buxgalter (`tax.vat.view`).
- **Route**: `/app/tax/vat`
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│  Davr: [ 2026-sentyabr ▾ ]                         │
│  QQS (12%) bazasi: 18 420 000   Summa: 2 210 400   │
│  Kutilayotgan QQS krediti (qizil fakturalar):       │
│                            96 000 so'm (≤10% limit) │
└──────────────────────────────────────────────────┘
```

- **Joylashuv**: BO-07 sidebar'da alohida punkt emas — «QQS va davlat hisoboti» bo'limidagi «QQS ichki hisobi» tabi (yonida «Davlat hisoboti bilan solishtirish» tabi — BO-10, farqlar soni badge'i bilan). Davr tanlovi va soliq rejimi chipi («QQS to'lovchi · 12%»); BO-10 da farq bo'lsa qizil banner (farq summasi, sabab — e-faktura darajasida, qolgan ish kunlari, «Solishtirishni ochish»); KPI kartalari (hisob raqami bilan: chiquvchi QQS 4410, kiruvchi QQS, to'lanadigan QQS va h.k.); «stavkalar bo'yicha» jadvali (ko'rsatkich, stavka, baza, QQS); «Riskli kiruvchi e-fakturalar» jadvali (e-faktura, yetkazib beruvchi, sana, baza, QQS, risk chipi; «E-faktura markazi» → BO-15); «Kutilayotgan QQS krediti» kartasi (summa, davr kiruvchi QQSdagi ulushi, 10% limit); «Soliq hisob-kitobi (ST)» kartasi (holat, hujjat, turi, davr, baza, stavka, provodka, o'tkazishdan keyingi 6410 qoldig'i; «Qayta hisoblash», «Bekor qilish», «O'tkazish»).
- **Maydonlar**: `period` — Davr — Период — `Select` (`YYYY-MM`; "chorak" — 3 oyni klient tomonda yig'adi, API faqat oylik qaytaradi) — ha.
- **"Soliq hisob-kitobi (ST)" bloki** (`tax_settlements`, hujjat kodi `ST`): davr tanlanadi → "Qoralama hisoblash" (server `tax_kind` bo'yicha qoralama: `vat_offset` — QQS to'lovchida chiquvchi va kiruvchi QQS hisob-kitobi `Dt 6410 / Kt 4410`; `turnover_tax` — aylanma solig'i rejimida `Dt 9430 / Kt 6410`; ustunlar `period`, `base_amount`, `rate`, `amount`, `expense_account`) → Buxgalter ko'rib "O'tkazish" yoki "Bekor qilish". Ruxsat — Buxgalter/Egasi.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Qoralama hisoblash | `accounting.post` | Yo'q | `POST /api/v1/tax-settlements` (`{period, tax_kind}`) — server hisoblagan qoralama |
| O'tkazish | `accounting.post` | «{davr} uchun {amount} so'm provodka yoziladi» | `POST /api/v1/tax-settlements/{id}/post` |
| Bekor qilish | `accounting.post` | Sabab majburiy | `POST /api/v1/tax-settlements/{id}/cancel` |
| Solishtirishni ochish | `tax.vat.view` | Yo'q | BO-10 |

- **Ma'lumot manbai**: `GET /api/v1/reports/vat-summary?period=YYYY-MM` (+ `GET /api/v1/vat-moves`); `GET/POST /api/v1/tax-settlements`, `/post`, `/cancel`.
- **Holatlar**: `loading` · `empty` (davr yopilmagan) · `error` (hisoblashda nomuvofiqlik) · `offline` (faqat ko'rish) · `no-permission` — faqat Buxgalterda Y/T, Egasi/Menejerda K · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `vat_summary_viewed`, `tax_settlement.posted`, `tax_settlement.cancelled`.
- **Bog'liq US**: US-M10-01, US-M10-03, US-M10-04, US-M11-01.

---

## BO-08 — Buxgalteriya jurnali, provodkalar

- **Maqsad**: hisob rejasi bo'yicha avtomatik provodkalarni ko'rish, filtrlash, eksport qilish, davrni (oyni) yopish, tuzatuvchi yozuv kiritish.
- **Rollar/ruxsat**: Buxgalter (`accounting.post`, `reports.export`); davrni yopish — `accounting.period.close`.
- **Route**: `/app/accounting/journal`
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│  Sana: [ ... ]  Hisob: [ ... ]   [ Eksport ]       │
├──────────────────────────────────────────────────┤
│  12.10.2026  Sotuv #K-000154   Kassa +69 000       │
│                                 Daromad −69 000     │
├──────────────────────────────────────────────────┤
│  [ Davrni yopish ]   [ Tuzatuvchi yozuv ]          │
└──────────────────────────────────────────────────┘
```

- **Joylashuv**: filtrlar — sana (dan/gacha), hisob, hujjat turi (Sotuv / Z-hisobot, Kirim, To'lov, Tuzatuvchi yozuv); «Eksport (XLSX)», «Tuzatuvchi yozuv»; provodkalar jadvali (`entry_date` bo'yicha: sana, hujjat (filial bilan), mazmun, Dt, Kt, summa; jami qatori «Dt oboroti = Kt oboroti»); o'ng panel — «Hisob qoldiqlari» (sana holatiga, `GET /reports/trial-balance`), **«Davrni yopish»** kartasi (eng eski ochiq oy, readiness blokerlari va ogohlantirishlari, «{Oy}ni yopish», izoh «Yopilgan oy qayta ochilmaydi — keyingi tuzatishlar joriy ochiq oyda tuzatuvchi yozuv bilan»); pastda «Qayta hisoblash navbati».
- **"Qayta hisoblash navbati" bloki** (qaror #56 c): `recost_jobs` ro'yxati — ustunlar (`19-api-ombor.md` §18 `GET /recost-jobs` javobi) `product_id`, `warehouse_id`, `from_date`, `status`, `attempts`, `created_at`, `finished_at`, `last_error`; navbatda ish bo'lsa "Davrni yopish" readiness'ida `recost_pending` bloker sifatida ko'rinadi. Manba — `GET /api/v1/recost-jobs?status=`; xato bo'lgan ish uchun "Qayta urinish" — `POST /api/v1/recost-jobs/{id}/retry` (`accounting.post`).
- **Maydonlar**: `dateFrom`/`dateTo` — `Calendar`; `accountFilter` — `Select` — majburiy emas; `adjustment.docDate` — Tuzatuvchi yozuv sanasi — faqat joriy **ochiq** davr (istisno — `0000` hisobli boshlang'ich balans yozuvi `go_live_date − 1`) — ha (tuzatuvchi yozuvda); `adjustment.accountDt`, `adjustment.accountKt` — Debet/Kredit hisobi — 4 raqam, majburiy, `≠`; `adjustment.amount` — Summa — `MoneyInput`, >0, majburiy; `adjustment.branchId` — Filial — majburiy, standart joriy filial; `adjustment.correctionOfPeriod` — Tuzatilayotgan davr — ixtiyoriy, `YYYY-MM`; `adjustment.comment` — Izoh — majburiy (tuzatuvchi yozuvda).
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Eksport | `reports.export` | Yo'q | `POST /api/v1/reports/ledger-entries/export` (`format: xlsx\|pdf`) → poll `GET /api/v1/reports/export-jobs/{job_id}` |
| Davrni yopish | `accounting.period.close` | Faqat **eng eski ochiq oy** tanlanadi (aks holda `409 PERIOD_CLOSE_OUT_OF_ORDER`). Avval `GET /period-closings/{period}/readiness` (qaror #69): blokerlar `recost_pending`, `fiscal_pending`, `devices_unsynced` (sinxronlanmagan qurilmalar ro'yxati — `cash_register_name`, `outbox_pending_count`, `outbox_oldest_pending_at`; "Qurilmani bekor qilish" havolasi BO-11 ga) — bloker bo'lsa tugma o'chiq; ogohlantirishlar (`tax_settlement_missing`, `opening_0000_nonzero`, `open_shifts`, `drafts_in_period`, `devices_not_synced_after_period_end`) tasdiqlash dialogida ro'yxat bilan; so'ng «{oy} yopiladi. Yopilgan oy **qayta ochilmaydi** — keyingi tuzatishlar joriy ochiq oyda tuzatuvchi yozuv bilan kiritiladi» | `POST /period-closings` |
| Tuzatuvchi yozuv | `accounting.post` | Yo'q | `POST /ledger-adjustments` (`doc_date` faqat ochiq davr, `account_dt`, `account_kt`, `amount`, `branch_id`, `correction_of_period?`, `comment` majburiy) |

- **Ma'lumot manbai**: `GET /api/v1/ledger-entries?entry_date__gte=&entry_date__lte=&account_dt=&account_kt=`; `GET /period-closings/{period}/readiness`, `POST /period-closings`, `POST /ledger-adjustments`, `POST /api/v1/reports/ledger-entries/export`.
- **Holatlar**: `loading` · `empty` (yozuv yo'q) · `error` (balans mos kelmadi, `PERIOD_CLOSED` — tuzatish yopilgan davrga kiritilmoqchi bo'lsa) · `offline` (faqat ko'rish) · `no-permission` — faqat Buxgalterda to'liq, boshqa rollarda yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `ledger_viewed`, `ledger_exported`, `period_closing.posted`, `ledger_adjustment.posted`.
- **Bog'liq US**: US-M11-01, US-M11-02.

---

## BO-09 — Hisobotlar markazi

- **Maqsad**: savdo/ombor/buxgalteriya/QQS hisobotlarini tanlab, davr bo'yicha ko'rish va eksport qilish.
- **Rollar/ruxsat**: Egasi, Menejer, Buxgalter (`reports.sales.view` savdo/ombor hisobotlari uchun, `reports.finance.view` moliya/QQS/P&L uchun; `reports.export`).
- **Route**: `/app/reports`
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│  Hisobot turi: [ Kunlik savdo ▾ ]  Davr: [ ... ]   │
│                                [ PDF ] [ Excel ]    │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `reportType` — Hisobot turi — Тип отчёта — `Select` — ha (ro'yxatda **"Kassa/smena tarixi"**, **"QQS registri (qaytarishlar bilan)"** (`tax.vat.view` — Buxgalter/Egasi; Menejerda ko'rinmaydi) va rasmiy shakl tayyorlov eksportlari — QQS (DSQ №3221 1-ilova), aylanma solig'i (9-ilova), moliyaviy hisobot (MEF №181 1-/2-ilova): satr kodlari bilan Excel/PDF, topshirish emas — Buxgalter shaxsiy kabinetda topshiradi); `period` — `Calendar range` — ha.
- **Joylashuv**: davr tez tugmalari (Bugun / Hafta / Oy / Chorak / Boshqa) + «Dan»/«Gacha»; hisobotlar katalogi guruhlar bo'yicha kartalarda (har hisobot: nom, qisqa izoh, chip «Excel · PDF» / «Buxgalter» (`reports.finance.view` yoki `tax.vat.view`) / «Shakl» (rasmiy shakl tayyorlovi)), ruxsat yo'q hisobot ko'rinmaydi:
  - **Savdo** — Kunlik savdo (`GET /reports/sales?group_by=day`), Top tovarlar (`/reports/top-products`), Kassa / smena tarixi (`/cash-registers/{id}/cash-history`), Kassirlar bo'yicha savdo (`/reports/sales?group_by=cashier`);
  - **Ombor** — Ombor qoldig'i (`/reports/stock`), Tovar harakati (`GET /stock-moves`), Kam qolgan tovarlar (`/stock-balances?low_stock=true`), Inventarizatsiya farqlari (`/stock-counts`);
  - **Moliya** — Foyda va zarar (`/reports/profit-and-loss`), Sinov balansi (`/reports/trial-balance`), Buxgalteriya balansi (`/reports/balance-sheet`), Qarzdorlik muddati (`/reports/debts-aging`);
  - **Soliq** — QQS registri (qaytarishlar bilan), QQS hisoboti (DSQ №3221, 1-ilova), Aylanma solig'i (9-ilova), Moliyaviy hisobot (MEF №181).
  Eksport navbati holati (hisobot, format, progress; tayyor bo'lgach yuklab olish havolasi). Tanlangan hisobot ko'rinishi: sarlavha (davr, filial, yaratilgan vaqt), «PDF», «Excel ga eksport», KPI kartalari va jadval (jami qatori bilan); ustunlar — tanlangan hisobot API javobidagi maydonlar.
- **Amallar**: PDF/Excel eksport (`reports.export`).
- **Ma'lumot manbai**: hisobotga qarab — `sales`/`top-products` — `?date_from=&date_to=`; `trial-balance`/`profit-and-loss` — `?period=`; `balance-sheet`/`debts-aging` — `?as_of=`; **"Kassa/smena tarixi"** — `GET /api/v1/cash-registers/{id}/cash-history`; **"QQS registri (qaytarishlar bilan)"** — `GET /api/v1/vat-moves?doc_type=returns`; eksport — `POST /api/v1/reports/{report-kod}/export` + poll `GET /api/v1/reports/export-jobs/{job_id}`.
- **Holatlar**: `loading` · `empty` (ma'lumot yo'q) · `error` (eksport muvaffaqiyatsiz) · `offline` (faqat oxirgi keshlangan hisobot) · `no-permission` — Kassir (faqat o'z smenasi), Omborchi (faqat ombor) cheklangan ko'rinishda · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `report_viewed`, `report_exported`.
- **Bog'liq US**: US-M12-01, US-M12-02, US-M12-03, US-M16-03, US-M02-03.

---

## BO-10 — Davlat hisobotini ichki hisob bilan solishtirish

- **Maqsad**: davlat hisobotini (fayl yuklash orqali) tizimga kiritish, QQS/aylanma solig'i hisobotini ichki hisob bilan **5 ish kuni** ichida (hisobot shaxsiy kabinetga joylashtirilgan kundan keyingi kundan, hisobot topshirish muddatidan kechiktirmay — QQS: keyingi oyning 20-sanasi, aylanma: 15-sana) solishtirish, AI-05 bilan farqni tushuntirish.
- **Mexanizm**: Buxgalter my.soliq.uz shaxsiy kabinetida hisobotni **tasdiqlaydi** yoki **tuzatish kiritib taqdim etadi** (alohida e'tiroz arizasi yo'q); 5 ish kunida javob bo'lmasa hisobot davlat shakllantirgan ko'rinishda qabul qilingan hisoblanadi; muddatdan keyin — aniqlashtirilgan hisobot (SK 83-modda). Tizim ichki hisob va farqlar ro'yxatini tayyorlaydi, avtomatik yuborish yo'q. Davlat hisoboti fayli kabinetdan yuklab olinib qo'lda yuklanadi — ommaviy API yo'q, 26 #41 (OQ-014).
- **Granulyarlik**: QQS — hujjat darajasida (e-faktura reyestri: STIR + faktura raqami + sana bo'yicha moslashtirish) va yig'indi darajasida; aylanma solig'i — faqat yig'indi darajasida, 5 manba satri (0101 e-faktura / 0102 NKM (fiskal chek) / 0103 marketplace / 0104 eksport / 0105 boshqa) va stavka bo'yicha. Ichki 0102 = Σ `fiscal_receipts` (`sale`/`return`/`debt_settlement`) chek sanasi bo'yicha; ledger bilan farq — «qarzga sotuv vaqt farqi» izoh qatori.
- **Eslatmalar** (qaror #50): farq chegarasi `tenants.settings.vat_diff_tolerance_amount` (standart `"1000.00"` so'm — har qanday farq ko'rsatiladi, "farq topildi" holati shu chegaradan boshlanadi); Buxgalterga eslatma 1-, 3- va 4-ish kunida; 3-ish kunida yopilmagan farq bo'lsa Egasiga ham eskalatsiya banneri. **"10-sanagacha interaktiv ma'lumotlar"** bloki — har oy 10-sanagacha kabinetga kiritiladigan ma'lumotlar uchun tizim tayyorlagan raqamlar: aylanma — soliq solinmaydigan daromad, chegirmalar, imtiyozlar; QQS — hisobga olinadigan QQS tuzatishlari, imtiyozlar.
- **Rollar/ruxsat**: Buxgalter va Egasi — `tax.compare.review` (ko'rish/farq/yuklash), `tax.correction.submit` (tuzatish/tasdiqni qayd etish).
- **Route**: `/app/tax/reconciliation`
- **Maket**: `06-ekranlar-umumiy.md` §6 BO-10 wireframe'i. Sahifa amallari — «QQS ichki hisobi» (BO-07), «Davlat hisobotini yuklash» (yuklash formasi — o'ng panelda). Soliq turi tablari holat chipi bilan (QQS «Farq» / Aylanma — tenant rejimiga mos bo'lmasa «Rejimda yo'q»); tanlangan hisobot kartasi: sarlavha (tur, davr, holat), kabinetga joylashtirilgan sana, yuklangan fayl/kim, farq chegarasi, **holat bosqichlari** (Yuklandi → Solishtirildi → Farq topildi → Tuzatish qayd etildi → Tasdiqlandi), **5 ish kuni** hisoblagichi (har ish kuni sanasi bilan, qolgan kunlar, oxirgi kun; topshirish muddatidan keyingi ish kuni hisobga olinmasligi izohi), «Eslatmalar» (1-, 3-, 4-ish kuni); «Yig'ma solishtirish» jadvali (ko'rsatkich, davlat, ichki, farq; «Kutilayotgan kredit» alohida qator); «Hujjat darajasi — kiruvchi e-faktura reyestri» (moslashtirish natijasi «N tadan M tasi mos», filtr «Farqli va tekshiriladigan» / «Barchasi», jadval: hujjat · kontragent, sana, davlat QQS, ichki QQS, farq, holat; jami); qizil e-faktura izohi (→ BO-15); «Oldingi davrlar» ro'yxati; «10-sanagacha interaktiv ma'lumotlar» bloki. O'ng panel — «Farq tushuntirishi» (AI-05 matni + «AI tushuntirish — raqamlar tizim hisobidan»), «Javobni qayd etish» (`comment`, `portalRef`, «Tuzatish qayd etish», «Kabinetda tuzatish (E-IMZO)» havolasi, «Tasdiqlangan deb belgilash» — farq chegaradan katta bo'lsa o'chiq va izoh), «Davlat hisobotini yuklash» formasi.
- **Maydonlar**: `taxTypeTab` — `Tabs` (**QQS/Aylanma** — `tax_type` API'da faqat `vat|turnover`; mol-mulk/yer/JShDS/ijtimoiy soliq tablari MVP'da yo'q, 05 §1.3 Won't); `uploadForm.taxType` — `vat|turnover`; `uploadForm.period` — `YYYY-MM`; `uploadForm.publishedAt` — sana (5 ish kunlik hisoblagich keyingi kundan boshlanadi); `uploadForm.file` — PDF/XLSX ≤5MB; `comment` — Tuzatish izohi — Комментарий к исправлению — `Textarea` — tuzatish qayd etilganda ha — max 1000; `portalRef` — Kabinetdagi hujjat raqami — Номер в кабинете — `Input` — ixtiyoriy.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Davlat hisobotini yuklash | `tax.compare.review` | Yo'q | `POST /state-reports` → avtomatik `POST /state-reports/{id}/compare` |
| Farqni ko'rib chiqish | `tax.compare.review` | Yo'q | Hujjat darajasidagi farq ro'yxati ochiladi |
| Farqni tushuntirish (AI-05) | `tax.compare.review` | Yo'q | `POST /ai/vat-diffs/{diff_id}/explain`; matn ostida «AI tushuntirish — raqamlar tizim hisobidan» belgisi |
| Tuzatish qayd etish | `tax.correction.submit` | Yo'q | `POST /api/v1/state-reports/{id}/correction` `{comment, portal_ref?}` (imzosiz qayd) — holat `correction_sent`; my.soliq.uz kabinetiga havola (tuzatish kabinetda kiritiladi) |
| Tasdiqlangan deb belgilash | `tax.correction.submit` | Yo'q | `POST /api/v1/state-reports/{id}/confirm` `{comment?}` — `match`/`diff_found` (tolerance ichida) holatdan; holat `confirmed` ("Tasdiqlandi") |

- **Holat nomlari** (`state_reports.status`): `uploaded` (Yuklandi), `compared` (Solishtirildi), `match` (Mos), `diff_found` (Farq topildi), `correction_sent` (Tuzatish qayd etildi), `confirmed` (Tasdiqlandi), `auto_accepted` (Avtomatik qabul qilindi).
- **Ma'lumot manbai**: `GET /api/v1/state-reports?tax_type=&period=` + `GET /api/v1/state-reports/{id}` + `GET /api/v1/state-reports/{id}/diffs`; `POST /api/v1/state-reports` (fayl yuklash), `POST /api/v1/state-reports/{id}/compare`, `POST /api/v1/state-reports/{id}/correction`, `POST /api/v1/state-reports/{id}/confirm`, `POST /api/v1/ai/vat-diffs/{diff_id}/explain`.
- **Holatlar**: `loading` · `empty` (davlat hisoboti hali e'lon qilinmagan, "Kutilmoqda") · `error` ("⚠ Farq topildi") · `offline` (faqat ichki ustun ko'rinadi, davlat ustuni "internet kerak") · `no-permission` — Buxgalter va Egasidan boshqa rollarga yopiq · `subscription-restricted` — kirilmaydi. Qo'shimcha holat: **"Muddat o'tdi — avtomatik qabul qilindi"** (5 ish kuni ichida javob berilmagan); **3-ish kunida** yopilmagan farq bo'lsa Egasiga ham eskalatsiya banneri ko'rsatiladi (qaror #50).
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `state_report.uploaded`, `tax_reconciliation_viewed`, `tax_correction_submitted`, `tax_auto_accepted`, `ai_vat_diff_explained`, `tax_reconciliation_escalated_to_owner`.
- **Bog'liq US**: US-M10-02, US-M10-04, AI-05.

---

## BO-11 — Foydalanuvchilar, huquqlar va sessiyalar

- **Maqsad**: xodim qo'shish/bloklash, rol/limit sozlash, parol/PIN tiklash, sessiya/qurilma boshqaruvi.
- **Rollar/ruxsat**: Egasi (`settings.users`); "Qurilmalar" tabida qurilmani bekor qilish — Egasi/Menejer (`devices.revoke`).
- **Route**: `/app/settings/users`
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│ [Xodimlar] [Rollar] [Qurilmalar] [Sessiyalar]      │
├──────────────────────────────────────────────────┤
│  Dilnoza   Kassir    Chilonzor-3   [●Faol]         │
│  [Bloklash][Parolni tiklash][PINni tiklash][Seanslar]│
│                                [ + Xodim qo'shish ] │
└──────────────────────────────────────────────────┘
```

**"Rollar" tab**: `GET /roles`, rol ichida `PUT /roles/{id}/permissions` — limitlar **rolga** bog'langan (`discount.give` limit 5%, `returns.approve` 100 000, `cash.withdraw` 50 000 — standart qiymatlar). Omborchi standart holatda kirimni faqat `draft` qiladi; ≤3 xodimli do'konda Egasi Omborchi roliga `purchases.post` ni qo'shishi mumkin (qaror #49).

**"Qurilmalar" tab** (qaror #56 a): `devices` ro'yxati — `cash_register_name` (hisoblanadi), `kind`, `app_version`, `last_sync_at`, `outbox_pending_count` (sinxronlanmagan voqealar soni); "Bekor qilish" (`devices.revoke`, Egasi/Menejer); `outbox_pending_count > 0` bo'lsa `has-pending` ogohlantirishi «Qurilmada N ta yuborilmagan voqea bor — avval sinxronlang» + `sync.drain` taklifi; "Yangi qurilma qo'shish" → `/install`.

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `phone` | Telefon | Телефон | `Input` (mask) | Ha | `+998` formati | — | 17 |
| `fullName` | To'liq ism | Полное имя | `Input` | Ha | 2–100 belgi | — | 100 |
| `roleIds` | Rol(lar) | Роль(и) | `Select` (multi) | Ha (≥1) | Kassir/Omborchi/Menejer/Buxgalter | — | — |
| `branchIds` | Filial(lar) | Филиал(ы) | `Select` (multi) | Ha (≥1) | — | Joriy filial | — |

Limitlar "Rollar" tabida — xodim formasida faqat `roleIds`, `branchIds`.

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| + Xodim qo'shish | `settings.users` | Yo'q | (qaror #34) Taklif kodi (`purpose=invite`) — Telegram bot birinchi, SMS zaxira |
| Bloklash/Blokdan chiqarish | `settings.users` | "Xodimni bloklaysizmi?" | Sessiyalar darhol revoke |
| Parolni tiklash | `settings.users` | Yo'q | (qaror #34) Tiklash kodi (`purpose=admin_reset`) — Telegram bot birinchi, SMS zaxira |
| PINni qayta o'rnatish | `settings.users` | Yo'q | Eski PIN bekor, keyingi kirishda yangi PIN majburiy |
| Seanslarni tugatish | `settings.users` | Yo'q | Tanlangan sessiya/barcha sessiya bekor |
| Qurilmani bekor qilish | `devices.revoke` (Egasi/Menejer) | "Qurilmani bekor qilasizmi?" — `reason` (majburiy); `outbox_pending_count > 0` bo'lsa «Yuborilmagan voqealar yo'qolishi mumkin» ogohlantirishi va `confirm_pending_loss` checkbox (belgilanmaguncha tasdiqlash o'chiq) | `POST /api/v1/devices/{id}/revoke` (`{reason, confirm_pending_loss}`) → `devices.revoked_at`, token/litsenziya bekor |

- **Ma'lumot manbai**: `POST /api/v1/admin/users`, `PATCH /api/v1/admin/users/{id}`, `GET /api/v1/admin/users/{id}/sessions`, `GET /api/v1/admin/users/{id}/devices`, `GET /api/v1/devices` (Qurilmalar tabi: `cash_register_name`, `kind`, `app_version`, `last_sync_at`, `outbox_pending_count`), `POST /api/v1/devices/{id}/revoke`, `POST /api/v1/admin/users/{id}/reset-password`, `POST /api/v1/admin/users/{id}/reset-pin`, `POST /api/v1/admin/users/{id}/revoke-sessions`; `GET /api/v1/roles`, `GET/PUT /api/v1/roles/{id}/permissions`, `GET /api/v1/permissions-catalog`.
- **Holatlar**: `loading` · `empty` (faqat Egasi mavjud) · `error` (bir xil telefon takror) · `offline` (faqat ko'rish) · `no-permission` — faqat Egasida, boshqalarga butunlay yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `user_created`, `user_blocked`, `password_reset`, `pin_reset_forced`, `session_revoked`, `device_revoked`.
- **Bog'liq US**: US-M13-01…08.

---

## BO-12 — Filiallar boshqaruvi

- **Maqsad**: filiallarni ro'yxatlash, aholi punkti toifasini (aylanma solig'i stavkasi uchun) belgilash, yangi filial qo'shish, kassalarni boshqarish va har bir kassaga integratsiyalangan karta terminalini bog'lash (qaror #71).
- **Rollar/ruxsat**: Egasi (`settings.branches`).
- **Route**: `/app/settings/branches`
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│  Chilonzor-3   Shahar, 100 ming+ (4%)   [Tahrir]   │
│  Yunusobod-1   Boshqa aholi punkti (2%) [Tahrir]   │
│                                [ + Filial qo'shish ]│
└──────────────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `name` | Filial nomi | Название филиала | `Input` | Ha | 2–100 | — | 100 |
| `address` | Manzil | Адрес | `Input` | Yo'q | — | — | 200 |
| `settlementCategory` | Aholi punkti toifasi | Категория населённого пункта | `Select` | Ha | `city_100k_plus\|other\|remote_mountain` (chakana aylanma solig'i 4% / 2% / 1%, SK 467-modda; tog'li/borish qiyin hududni Egasi tanlaydi) | `city_100k_plus` (eng ehtiyotkor) | — |
| `warehouseType` ("+ Filial qo'shish" dialogida) | Ombor turi | Тип склада | `SegmentedControl` | Ha | `store\|stock` | `store` | — |
| `warehouses[].inventoryAccount` | Tovar hisobi | Счёт учёта товара | `Select` | Ha | `2910` (ombor) \| `2920` (savdo zali); saqlash — `PATCH /api/v1/warehouses/{id}` (`settings.branches`); omborda harakat bo'lsa `409 WAREHOUSE_ACCOUNT_LOCKED` | Server `type` dan qo'yadi: `store` → `2920`, `stock` → `2910` | — |
| `cashRegisters[].fiscalAgent` | Fiskal agent | Фискальный агент | `Select` (shu tenant Do'kon agentlari, `capabilities.fiscal.devices[]` dan `local_id`) | Yo'q (lokal fiskal ko'prik kassasida Ha) | Agent tanlansa `local_id` majburiy | — | — |
| `cardTerminal.name` ("Terminalni bog'lash" dialogi, qaror #71) | Terminal nomi | Название терминала | `Input` | Ha | 2–100 | "{kassa} — {model}" | 100 |
| `cardTerminal.vendor` / `model` | Ta'minotchi / model | Поставщик / модель | `Select` / `Input` | Ha / Yo'q | `vendor` ~ `^[a-z0-9_]{2,32}$` (`rahmat`, `era`, `humo`, `smartone`, `mayasoft`, `fake`) | — | 32 / 100 |
| `cardTerminal.adapter` | Ulanish turi | Тип подключения | `SegmentedControl` | Ha | `agent_ecr` (Do'kon agenti orqali LAN/Wi-Fi) \| `cloud` (vendor bulut API) \| `android_intent` (Kotlin POS shu smart-terminalda) \| `softpos` (NFC telefon/planshet) \| `fake` (sinov; prod'da yo'q) | `agent_ecr` | — |
| `cardTerminal.driver` | Drayver | Драйвер | `Select` (tanlangan agentning `capabilities.card_terminal` dan) | Ha | `^[a-z0-9_]{2,40}$`; `fake` ↔ `adapter='fake'` | — | 40 |
| `cardTerminal.agentDevice` | Do'kon agenti va qurilma | Агент и устройство | `Select` (agent → `devices[].local_id`) | `agent_ecr` da Ha | `agent_id` + `local_id` (bitta agent qurilmasi — bitta faol terminal) | — | — |
| `cardTerminal.host` / `port` | LAN manzili | Адрес в сети | `Input` (IP) / `Input` (raqam) | `agent_ecr` da Ha (host) | Faqat xususiy IPv4 (10/8, 172.16/12, 192.168/16); port 1–65535 | — | 15 / 5 |
| `cardTerminal.vendorTerminalRef` | Bulutdagi terminal ID | ID терминала в облаке | `Input` | `cloud` da Ha | — | — | 64 |
| `cardTerminal.tid` / `mid` | TID / MID | TID / MID | `Input` | TID — faol real terminalda Ha; MID — Yo'q | TID `^[0-9A-Za-z]{1,16}$` (tenant ichida takrorlanmaydi); MID `^[0-9A-Za-z]{1,20}$` | Aloqa tekshiruvidan (bo'lsa) | 16 / 20 |
| `cardTerminal.acquirer` | Ekvayer bank | Банк-эквайер | `Combobox` (kontragentlar, bank) | Yo'q (BO-24 `rrn` moslashtirishi uchun tavsiya) | `acquirer_counterparty_id` | — | — |
| `cardTerminal.isDefault` | Kassada standart | По умолчанию для кассы | `Switch` | — | Kassada bitta standart faol terminal | Kassadagi birinchi terminal — ha | — |
| `cardTerminal.status` | Holat | Статус | `Select` | Ha | `active\|disabled\|archived` | `active` | — |
| `cardManualFallback` (do'kon darajasi) | Kartani qo'lda kiritish | Ручной ввод карты | `RadioGroup` (Ruxsat / Menejer tasdig'i bilan / Taqiqlangan) | — | `tenants.settings.card_manual_fallback` = `allow\|manager_approval\|forbid` | Qiymat yo'q: faol terminal bog'langan kassada `manager_approval`, boshqa kassada `allow` | — |

Filial ichida "Kassalar" ro'yxati: har bir kassa qatorida soliq ro'yxatidan o'tish holati (`tax_registered_at`, TXKM shartnomasi `txkm_contract_ref`), fiskal modul holati (`fm_state`), "Fiskal agent" `Select` (lokal fiskal ko'prik kassasiga xizmat qiluvchi Do'kon agenti va uning fiskal qurilmasi — `cash_registers.fiscal_agent_id`, `fiscal_local_device_id`), **"Karta terminali"** ustuni (qaror #71: bog'langan terminal nomi, TID, ulanish turi va `TerminalStatusChip` — `health_status` va `health_checked_at`; bo'lmasa "Yo'q — karta qo'lda" va "Terminalni bog'lash" havolasi; kassada bir nechta terminal bo'lsa soni va standarti) va "Arxivlash" amali. Kassalar jadvali ostida do'kon darajasidagi "Kartani qo'lda kiritish" siyosati (`card_manual_fallback`) — integratsiyalangan terminal ishlamaganda kassir karta rekvizitlarini qo'lda kiritishi mumkinmi. Har bir kassa savdodan oldin filial manzili bo'yicha alohida ro'yxatdan o'tadi; filial manzili o'zgartirilsa shu filial kassalari uchun «3 ish kunida qayta ro'yxatdan o'tkazing» eslatmasi chiqadi. Omborning tovar hisobi (`warehouses.inventory_account`) — Buxgalter/Egasi o'zgartiradi.

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| + Filial qo'shish | `settings.branches` | Yo'q | `POST /api/v1/branches` (`warehouse: {type: warehouseType}`) |
| Fiskal agentni bog'lash (kassa qatori) | `cash_register.manage` | Yo'q | `PATCH /api/v1/cash-registers/{id}` `{fiscal_agent_id, fiscal_local_device_id, version}` (qaror #66) |
| Tahrir/Saqlash | `settings.branches` | Toifa o'zgartirilsa "Yangi stavka faqat shu sanadan qo'llanadi"; manzil o'zgartirilsa — kassalarni qayta ro'yxatdan o'tkazish eslatmasi | `branch_tax_settings` yangi yozuv (`valid_from`) |
| + Kassa qo'shish | `cash_register.manage` | `ADDON_REQUIRED` bo'lsa dialog «Qo'shimcha kassa — +39 000 so'm/oy. Obunaga qo'shasizmi?» → BO-19 | `POST /cash-registers` |
| Arxivlash (kassa) | `cash_register.manage` | Yo'q | `POST /api/v1/cash-registers/{id}/archive` (`{}`) |
| Terminalni bog'lash / tahrirlash (kassa qatori, qaror #71) | `cash_register.manage` | Yo'q | `POST /api/v1/card-terminals` yoki `PATCH /api/v1/card-terminals/{id}` (`version`); terminal filialga tegishli, `cash_register_id` — shu kassa; `agent_ecr` da agent qurilmalari ro'yxati agent `hello.capabilities.card_terminal` dan |
| Aloqani tekshirish (terminal) | `cash_register.manage` | Yo'q | `health` (pulli tranzaksiya emas) — agent/bulut orqali; `health_status` yangilanadi |
| Terminalni uzish / arxivlash | `cash_register.manage` | "Kassa {nom} kartani qo'lda qabul qiladi. Davom etasizmi?"; `pending`/`unknown` tranzaksiyasi bor terminalda — rad, `CARD_OUTCOME_UNKNOWN` (avval natijani aniqlang) | `PATCH /api/v1/card-terminals/{id}` `{status: 'disabled'\|'archived'}` |
| Kartani qo'lda kiritish siyosati — Saqlash | `settings.tenant` | `forbid` tanlansa: "Terminal ishlamasa karta to'lovi qabul qilinmaydi" | `PATCH /api/v1/tenant/settings` `{card_manual_fallback}` |

- **Ma'lumot manbai**: `GET/POST /api/v1/branches`, `PATCH /api/v1/branches/{id}` + `GET/POST /api/v1/cash-registers`, `PATCH /api/v1/cash-registers/{id}`, `POST /api/v1/cash-registers/{id}/archive`, `GET /api/v1/branches/{id}/tax-settings`, `GET /api/v1/warehouses?branch_id=`, `PATCH /api/v1/warehouses/{id}`; karta terminallari — `GET/POST /api/v1/card-terminals`, `PATCH /api/v1/card-terminals/{id}`; `GET/PATCH /api/v1/tenant/settings` (`card_manual_fallback`) (qaror #71).
- **Holatlar**: `loading` · `empty` (bitta filial; kassada terminal yo'q — "Karta qo'lda belgilanadi") · `error` (terminal: agent ulanmagan, TID boshqa terminalda band — `409`, xususiy bo'lmagan IP — `422 VALIDATION_ERROR`) · `offline` (faqat ko'rish) · `no-permission` — faqat Egasida, boshqa rollar K · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `branch.created`, `branch_tax_category_changed`, `card_terminal.created`, `card_terminal.updated`, `card_terminal.archived` (audit); analitika — `card_terminal_health_checked`.
- **Bog'liq US**: US-M14-01, US-M14-03, US-M14-04, US-M01-08 (karta terminali bog'lash).

---

## BO-13 — AI yordamchi — savol-javob chat

- **Maqsad**: biznes savollariga (AI-01) tabiiy tilda javob, raqamni kod hisoblaydi.
- **Rollar/ruxsat**: Egasi, Menejer, Buxgalter (`ai.chat.use`).
- **Route**: `/app/ai`
- **Maket**: `06-ekranlar-umumiy.md` §6 BO-13 wireframe'i. Sarlavha izohi «Raqamni tizim hisoblaydi, AI faqat o'zbek tilida tushuntiradi. Javobda hisoblash manbasi ko'rsatiladi»; «Yangi suhbat» (joriy suhbatni tozalaydi). Chat: savol (kim, vaqt), javob — asosiy raqam ajratilgan, hisoblash tarkibi (masalan savdo / tannarx / xarajat / sof foyda) yoki kichik jadval, «Manba: Hisobotlar → …» qatori; javob topilmasa «aniq javob topa olmadim» matni (raqamsiz); «AI yozmoqda…» indikatori; tez savol chiplari; xabar maydoni (`Enter` yuborish, `Shift+Enter` yangi qator, belgi hisoblagichi «N / 500»). O'ng panel — **«Foydalanish limiti»** (`GET /api/v1/ai/usage`: oylik so'rovlar sarfi/limit, yangilanish sanasi; bugungi do'kon so'rovlari / 300, «foydalanuvchiga 10 ta/daqiqa»), **«Maxfiylik»** (maskalanadigan maydonlar ro'yxati, «Buni o'chirib bo'lmaydi»; chet elga uzatish roziligi holati va sanasi, «Rozilikni boshqarish — Sozlamalar» → BO-14), offline/rate-limit holatlari izohi.
- **Maydonlar**: `message` — Xabar — Сообщение — `Textarea`/`Input` — ha (yuborishda) — max 500 (API chegarasi 2000).
- **Amallar**: tez savol tugmalari (preset), yuborish (`Enter`/`➤`).
- **Ma'lumot manbai**: `GET /api/v1/ai/usage` (limit paneli); `POST /api/v1/ai/chat` (backend SQL hisoblaydi, LLM faqat tushuntiradi; promptdagi shaxsiy maydonlar — mijoz/kontragent ismi, telefon, JSHSHIR, YaTT STIR, manzil — har doim maskalanadi, qaror #61).
- **Holatlar**: `loading` (AI yozmoqda) · `empty` (suhbat boshlanmagan — tez savol tugmalari) · `error` ("Bu savolga aniq javob topa olmadim", #33) · `offline` (chat butunlay o'chirilgan, "AI uchun internet kerak") · `no-permission` — Kassir/Omborchiga yopiq · `subscription-restricted` — kirilmaydi; AI oylik limiti tugaganda alohida xabar ("AI limiti tugadi, keyingi oy boshigacha kutilmoqda"); tezlik chegarasi — foydalanuvchiga 10 so'rov/daqiqa, tenantga 300 so'rov/kun, oshsa `429 RATE_LIMITED` → «Juda ko'p so'rov — biroz kuting» (qaror #55).
- **Klaviatura**: `Enter` yuboradi, `Shift+Enter` yangi qator.
- **Audit/analitika**: `ai_chat_message_sent`, `ai_chat_no_answer`, `ai_quota_exceeded`.
- **Bog'liq US**: AI-01, US-M18-04 (bot orqali bir xil backend).

---

## BO-14 — Tenant/do'kon sozlamalari

- **Maqsad**: do'kon nomi, til, valyuta, soliq rejimi, integratsiyalar holatini boshqarish.
- **Rollar/ruxsat**: Egasi (`settings.tenant` — 05+, yangi kod, faqat Egasi; zaxira usuli — `valuation.settings.manage`).
- **Route**: `/app/settings/tenant`
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│  Do'kon nomi:   [ "Mega Market" ]                  │
│  Soliq rejimi:  [ QQS to'lovchi ▾ ]                │
│  Zaxira usuli:  [ O'rtacha narx (AVECO) ▾ ]        │
│  Tarozi kodi: 22 = og'irlik (g), 21 = summa [Tahrir]│
│  Markirovka tekshiruvi: [ Ogohlantirish ▾ ]        │
│  AI'ga uzatish roziligi: [● Berilgan] 12.10.2026   │
│  Do'kon agenti: 🟢 DOKON-PC  (fiskal, printer)     │
│  OFD:       🟢 ulangan   OFD yuborilmagan: 0 ta    │
│  E-faktura: 🟢 Faktura.uz  Asl belgisi: 🟡 kalit yo'q│
│  1C:        🟢 Do'kon BP · oxirgi kun 15.10 ·      │
│             navbatda 0 · xato 0      [Tafsilot →]   │
└──────────────────────────────────────────────────┘
```

Sahifa tepasida Sozlamalar ichki tablari (Do'kon · Xodimlar · Filiallar · Telegram · Obuna · 1C — `06-ekranlar-umumiy.md` §1.9); sarlavha «Do'kon sozlamalari», izoh «O'zgartirish faqat Egasida», «Bekor qilish» / «Saqlash». BO-14 ichidagi bo'lim tablari: **Do'kon** (nom, til) · **Soliq rejimi** (`taxRegime`, `costingMethod`, `vatDiffToleranceAmount`; izoh «Rejim o'zgarishi keyingi oydan, zaxira usuli — keyingi hisobot yilidan kuchga kiradi») · **Integratsiyalar** (kartalar ro'yxati: Faktura.uz, Asl belgisi (CRPT), Click, Payme, Uzum, UzQR, Telegram (→ BO-20), 1C (→ BO-23/BO-22) — har birida maqsad, holat chipi «Ulangan» / «Kalit yo'q» / «Tasdiq kerak», tafsilot, «Sozlash» / «Kalit kiritish» / «Tafsilot»; Click/Payme/Uzum kartasida `providerFiscalizationOff` belgisi; tasdiqlanmagan provayder bo'lsa qizil banner va saqlash o'chiq; sarlavhada «N ulangan · M ta e'tibor talab qiladi») · **Fiskal** (OFD holati, yuborilmagan cheklar, `markingPrecheck`, tarozi shablonlari, **Do'kon agenti** bloki) · **Chek** (chek shabloni ko'rinishi — `08-dizayn-tizimi.md` chek shabloni) · **Xavfsizlik** (`aiCrossBorderEnabled`, `supplierOverpayPolicy`, «Sinxron istisnolari»).

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `storeName` | Do'kon nomi | Название магазина | `Input` | Ha | 2–100 | — | 100 |
| `taxRegime` | Soliq rejimi | Налоговый режим | `Select` | Ha | `vat\|turnover`; saqlash — `POST /api/v1/tenant/tax-regimes` (40c, keyingi oydan) | — | — |
| `costingMethod` | Zaxira baholash usuli | Метод оценки запасов | `Select` | Ha | `aveco\|fifo` (yorliq katta harfda: AVECO / FIFO) | `aveco` | — |
| `crptApiKey` | Asl belgisi API kaliti | API-ключ Asl belgisi | `Input` (masked) | Yo'q | Saqlash — `PUT /api/v1/tenant/integrations/crpt` (40d) | — | 256 |
| `fakturaUz.login` | Faktura.uz login | Логин Faktura.uz | `Input` (masked) | Yo'q | Saqlash — `PUT /api/v1/tenant/integrations/faktura-uz` (40d), to'rt maydon birga | — | — |
| `fakturaUz.password` | Faktura.uz parol | Пароль Faktura.uz | `Input` (masked) | Yo'q | — | — | — — serverda shifrlangan saqlanadi, qayta ko'rsatilmaydi |
| `fakturaUz.clientId` | Faktura.uz API mijozi ID | Client ID Faktura.uz | `Input` (masked) | Yo'q | — | — | — |
| `fakturaUz.clientSecret` | Faktura.uz API mijozi siri | Client secret Faktura.uz | `Input` (masked) | Yo'q | — | — | — — qayta ko'rsatilmaydi |
| `weightBarcodeTemplates[]` | Tarozi shtrix-kod shablonlari | Шаблоны весового штрихкода | Jadval (`prefixes`, `item_code_len` 4–6, `value_kind` WEIGHT/AMOUNT, `decimals`, `enabled`) | Yo'q | EAN-13 `PP CCCCC VVVVV K`, prefiks 20–29 | 22 / WEIGHT (gramm), 21 / AMOUNT (so'm) | — |
| `markingPrecheck` | Markirovka tekshiruvi | Проверка маркировки | `SegmentedControl` (O'chiq / Ogohlantirish / Bloklash) | Ha | `off\|warn\|block` (qaror #62) | `warn` | — |
| `vatDiffToleranceAmount` | QQS farq chegarasi | Порог расхождения НДС | `MoneyInput` | Ha | ≥0 → `settings.vat_diff_tolerance_amount` (BO-10 «Farq topildi» chegarasi, qaror #50) | `1000.00` | — |
| `supplierOverpayPolicy` | Yetkazib beruvchiga ortiqcha to'lov | Переплата поставщику | `SegmentedControl` («Ogohlantirish (avans)» = `warn`, «Bloklash» = `block`) | Ha | `warn\|block` → `settings.supplier_overpay_policy` (qaror #47): `warn` — ortig'i avans 4310, `block` — `SUPPLIER_OVERPAY_BLOCKED` | `warn` | — |
| `aiCrossBorderEnabled` | Ma'lumotni AI xizmatiga (chet elga) uzatishga rozilik | Согласие на передачу данных AI-сервису (за рубеж) | `Switch` | — | Yoqishda rozilik matni ko'rsatiladi; `POST /api/v1/tenant/consents` (`purpose=ai_cross_border`, `terms_version`, `accepted`) — `PATCH` bilan o'zgartirilmaydi | O'chiq (BO-21 da berilmagan bo'lsa) | — |
| `providerFiscalizationOff` | Provayder avto-fiskallashtirishi o'chirilgan | Автофискализация провайдера отключена | `Checkbox` (Click / Payme / Uzum alohida) | Ha (shu provayder yoqilganda) | Egasi merchant kabinetida tekshirganini tasdiqlaydi → API `provider_autofiscal_disabled_confirmed: true` (`PUT /api/v1/tenant/integrations/{click\|payme\|uzum}`, 40d, majburiy); belgilanmasa saqlash o'chiq | O'chiq | — |

- **Amallar**: Saqlash (`settings.tenant`) → `PATCH /tenant/settings`; soliq rejimi — `POST /tenant/tax-regimes` (40c); integratsiya kalitlari — `PUT /tenant/integrations/{provider}` (40d); zaxira usuli — `PATCH /valuation-settings` (`valuation.settings.manage`), javobdagi `pending_change.effective_from`ni ko'rsatish; «1C» qatori (Bosqich 7, `onec.view` bo'lsa) — holat 🟢/🟡/🔴/⚪, oxirgi muvaffaqiyatli kun (`last_done_date`), navbatdagi kunlar (`pending_days`), xato hujjatlar (`failed_items`), «Tafsilot» → BO-23, ⚪ (sozlanmagan) bo'lsa «Sozlash» → BO-22; zaxira usulini o'zgartirish — "Bu o'zgarish faqat keyingi hisobot yili boshidan kuchga kiradi" tasdiqlash dialogi; tarozi shablonlari — `PATCH /stock-settings` (US-M09-06; PLU ro'yxati tarozi dasturiga BO-18 "PLU eksport (CSV)" orqali); "OFD: N ta chek yuborilmagan" qatori → ro'yxat + "Qayta urinish" (`POST /fiscal-receipts/{id}/retry`), kassalar fiskal modul holati (`fm_state`).

**Fiskal va to'lov integratsiyasi**: fiskal chek `FiscalPort` orqali — hamkor bulut API yoki do'kon Windows kompyuteridagi **Do'kon agenti** (fiskal modul ko'prigi, LAN printerlar va tarozi uchun ham — qaror #60); agent holati va ulash shu ekranda (1C moduli — shu agentning qo'shimcha imkoniyati, BO-22). Click/Payme/Uzum yoqilganda Egasi provayder kabinetida provayder tomonidagi avtomatik fiskallashtirish o'chirilganini tasdiqlaydi (`providerFiscalizationOff`) — aks holda bitta to'lovga ikki chek chiqadi; chekni har doim bizning kassa chiqaradi. UzQR: yuridik shaxs — bank UzQR (statik/dinamik, dinamik uchun kalit har kassa uchun alohida); yakka tadbirkor — to'lov tashkiloti maxsus QR'i.

**"Do'kon agenti" bloki** (qaror #66, Bosqich 5): agentlar ro'yxati — `GET /api/v1/onec-agents` (W-01; nom, versiya, holat, `capabilities` — fiskal/printer); "Kompyuterni ulash" — ulash kodi bo'yicha PK ma'lumoti `GET /api/v1/onec-agents/pairing-requests/{user_code}` (W-03) → "Ulash" `POST /api/v1/onec-agents/pair` (W-04) yoki "Rad etish" `POST /api/v1/onec-agents/pairing-requests/{user_code}/deny` (agent poll'iga `access_denied`); "Uzish" — `POST /api/v1/onec-agents/{id}/revoke` (W-05); "Diagnostika" — `POST /api/v1/onec-agents/{id}/diagnostics-requests` (W-07); "Loglar" — `GET /api/v1/onec-agents/{id}/logs` (W-08). Ruxsatlar: ko'rish — `onec.view`, ulash/uzish/diagnostika — `onec.settings.manage` (Egasida bor, qaror #28). Kassaga bog'lash — BO-12 "Fiskal agent". BO-22 (1C) shu agentdan foydalanadi.

**AI roziligi** (qaror #61): AI'ga shaxsiy maydonlar har doim maskalanadi (o'chirib bo'lmaydi); hujjat rasmlari (AI-03) maskalab bo'lmagani uchun faqat `ai_cross_border_enabled=true` bo'lsa yuboriladi — rozilik yo'q bo'lsa AI-03 o'chiq. Rozilikni faqat Egasi beradi/qaytarib oladi, har o'zgarish `consents` va audit'ga yoziladi. Rozilik va foydalanish shartlari matnining yuridik tasdig'i — 26 #127 (OQ-042).

**"Sinxron istisnolari" bloki** (qaror #56 b): sinxronizatsiyada qabul qilingan, lekin istisno sifatida belgilangan voqealar (`sync_exceptions`) ro'yxati; har qator "Ko'rib chiqildi" — izoh majburiy (`POST /api/v1/sync-exceptions/{id}/review`, `reviewed_at/reviewed_by/review_note`, audit); provodkaga ta'sir qilmaydi. Shu yerda "Qayta hisoblash navbati" holat qatori (BO-08 ga havola).
- **Ma'lumot manbai**: tenant sozlamalari — `GET/PATCH /api/v1/tenant/settings` (`marking_precheck`, `supplier_overpay_policy`, `vat_diff_tolerance_amount`; `ai_cross_border_enabled` — faqat o'qish, o'zgarishi `POST /api/v1/tenant/consents` orqali); soliq rejimi — `POST /api/v1/tenant/tax-regimes` (40c); integratsiyalar — `PUT /api/v1/tenant/integrations/{provider}` (40d); zaxira usuli — `GET/PATCH /api/v1/valuation-settings`; tarozi — `GET/PATCH /api/v1/stock-settings` (`catalog.manage`); Do'kon agenti — W-01, W-03, W-04, W-05, W-07, W-08 (`33-1c-integratsiya.md` §10); OFD — `GET /api/v1/fiscal-receipts?status=failed` + `POST /api/v1/fiscal-receipts/{id}/retry`; sinxron istisnolari — `GET /api/v1/sync-exceptions`, `POST /api/v1/sync-exceptions/{id}/review`; 1C qatori — `GET /api/v1/onec-status` (W-55, `33-1c-integratsiya.md` §10).
- **Holatlar**: `loading` · `empty` (sozlanmagan) · `error` (integratsiya ulanmagan) · `offline` (faqat ko'rish) · `no-permission` — faqat Egasida · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `tenant_settings_updated`, `costing_method_change_scheduled`, `integration_connected`, `fiscal_receipt.retry_requested`, `consent.ai_cross_border_changed`, `sync_exception.reviewed`, `marking_precheck_changed`.
- **Bog'liq US**: US-M04-05, US-M09-06, US-M01-03, US-M01-07, US-M17-01; 1C qatori — US-M19-15.

---

## BO-15 — Kiruvchi va chiquvchi e-faktura markazi

- **Maqsad**: kiruvchi e-fakturalarni qabul/E-IMZO imzolash, chiquvchi (B2B nasiya + chekdan keyingi) e-fakturalarni boshqarish.
- **Rollar/ruxsat**: Buxgalter (`purchases.post` — kiruvchi ro'yxat/qabul/rad, `einvoice.create` — chiquvchi e-faktura yaratish, `einvoice.sign` — imzolash/yuborish/bekor qilish, `purchases.receive` — e-fakturadan kirim va kiruvchi e-TTN).
- **Route**: `/app/einvoices`
- **Maket**: `06-ekranlar-umumiy.md` §6 BO-15 wireframe'i. Sahifa amallari — «Chek asosida e-faktura», «Chiquvchi e-faktura»; tablar **Kiruvchi · Chiquvchi · E-TTN · E-ishonchnomalar** (har birida soni); KPI kartalari — kiruvchi (oy: soni, summa, QQS), imzo kutmoqda, kechiktirilgan QQS krediti (qizil va noma'lum), chiquvchi yuborilmagan. Kiruvchi ro'yxat filtrlari — xavf darajasi (Barchasi / Yashil / Qizil / Noma'lum), holat (Barchasi / Imzo kutmoqda / Qabul qilingan / Rad etilgan); ustunlar — faktura · yetkazib beruvchi, sana, summa, QQS, xavf chipi, holat; ostida kechiktirilgan QQS krediti izohi (VM 830; «Faktura.uz xavf belgisini bermaydi — noma'lumni kabinetdan tekshirib qo'lda belgilang»); «Kiruvchi e-TTN» qisqa bloki (Tasdiqlash / Rad etish). O'ng panel — tanlangan e-faktura: rekvizitlar, qatorlar, QQSsiz/QQS/jami; «Xavf darajasini belgilash» (Yashil / Qizil, izoh majburiy, «Kabinetda tekshirdim» belgisi, «Belgilashni saqlash»); E-IMZO kaliti (egasi, roli, amal muddati), «Imzolab qabul qilish» / «Rad etish»; oldingi urinish xatosi; izoh «Qabul qilingach — «Kirim yaratish»».
- **Maydonlar**: `receiptSearch` — Chekni qidirish (chekdan e-faktura chiqarishda) — Поиск чека — `Input` — ha — chek raqami/sana; `riskFlag` — Xavf darajasi — Уровень риска — `Select` (qo'lda belgilash, `unknown` bo'lganda) — `green|red`.
- **Xavf darajasi** (VM 830): kiruvchi e-faktura `risk_flag` — `green` / `red` / `unknown` (standart). Faktura.uz API'si xavf maydonini qaytarmaydi — `unknown` QQS krediti uchun **qizil kabi** (to'lovgacha kechiktiriladi) hisoblanadi; Buxgalter my.soliq.uz kabinetidan ko'rib qo'lda `green`/`red` belgilaydi (audit). Operator tasdig'i — 26 #47 (OQ-019).
- **Chiquvchi e-faktura**: jismoniy shaxsga chek berilgan sotuvda e-faktura kerak emas; yuridik shaxsga (B2B, `counterparty.kind='company'`; STIR'li YaTT ham `company` sifatida kiritiladi) — majburiy.
- **Qo'shimcha (salbiy) e-faktura**: yetkazib beruvchiga qaytarishda yetkazib beruvchi chiqargan qo'shimcha e-faktura (`factura_type=additional`, `related_einvoice_id` — asl e-faktura) shu yerda qabul qilinadi; qabul qilingan davrda kiruvchi QQS kamaytiriladi.
- **E-ishonchnomalar**: do'kon bergan e-ishonchnomalar ro'yxati — manba `GET /api/v1/powers-of-attorney?status=`; holatlar `draft` (Qoralama), `pending_signature` (Imzo kutilmoqda), `sending` (Yuborilmoqda), `sent` (Yuborildi), `accepted` (Yetkazib beruvchi tasdiqladi), `rejected` (Rad etildi), `cancelled` (Bekor qilindi), `failed` (Xato — qayta imzolash/yuborish); BO-04 dan berilgan.
- **Kiruvchi e-TTN**: `GET /api/v1/ettn-documents?direction=in` ro'yxati — "Tasdiqlash"/"Rad etish" amallari.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Qabul qilish | `purchases.post` | Yo'q | `POST /api/v1/einvoices/{id}/accept` |
| Rad etish | `purchases.post` | Sabab majburiy | `POST /api/v1/einvoices/{id}/reject` (`{reason}`) |
| E-IMZO imzo | `einvoice.sign` | Sertifikat/parol | `POST /api/v1/einvoices/{id}/sign-challenge` → E-IMZO → `POST /api/v1/einvoices/{id}/submit-signed` → `POST /api/v1/einvoices/{id}/send` |
| Yuborish (chiquvchi) | `einvoice.sign` | Yo'q | `POST /api/v1/einvoices/{id}/send` |
| Bekor qilish (chiquvchi) | `einvoice.sign` | Sabab majburiy | `POST /api/v1/einvoices/{id}/cancel` |
| Kiruvchi e-TTN: Tasdiqlash / Rad etish | `purchases.receive` + `einvoice.sign` | E-IMZO; rad etishda sabab | `POST /api/v1/ettn-documents/{id}/sign-challenge?action=accept\|reject` → `POST /api/v1/ettn-documents/{id}/accept` \| `/reject` |
| Chek asosida e-faktura chiqarish | `einvoice.create` | Yo'q | `POST /api/v1/einvoices/from-receipt` — `{sale_id, counterparty_id}`; `einvoices.related_doc_type`/`related_doc_id` bilan chekka bog'langan yangi hujjat, QQS qayta hisoblanmaydi; xatolar `EINVOICE_ALREADY_LINKED`, `EINVOICE_AMOUNT_EXCEEDS_RECEIPT`, `EINVOICE_COUNTERPARTY_INCOMPLETE` (→ BO-06 "Mijoz kartasi"ga havola, E-06) |
| Kirim yaratish | `purchases.receive` | Yo'q | `POST /goods-receipts/from-einvoice/{einvoice_id}` (US-M07-03) |
| Xavf darajasini belgilash | `purchases.post` | «Kabinetda tekshirdingizmi?» + `note` (`Textarea`, majburiy) | `PATCH /api/v1/einvoices/{id}/risk-flag` (`{risk_flag, note}`), audit |

- **Ma'lumot manbai**: `GET /api/v1/einvoices?direction=in|out`, `POST /api/v1/einvoices` (`einvoice.create`; B2B sotuv qoralamasini server `sale.created` postingida o'zi yaratadi), `POST /api/v1/einvoices/{id}/sign-challenge` → `POST /api/v1/einvoices/{id}/submit-signed`, `POST /api/v1/einvoices/{id}/send`, `POST /api/v1/einvoices/{id}/cancel`, `POST /api/v1/einvoices/{id}/accept`/`reject`, `GET /api/v1/ettn-documents?direction=in`, `GET /api/v1/powers-of-attorney?status=`, `POST /api/v1/einvoices/from-receipt`, `POST /goods-receipts/from-einvoice/{einvoice_id}`.
- **Holatlar**: `loading` · `empty` (faktura yo'q) · `error` (E-IMZO imzolashda xato — sertifikat/parol; `EINVOICE_ALREADY_LINKED`/`EINVOICE_AMOUNT_EXCEEDS_RECEIPT`/`EINVOICE_COUNTERPARTY_INCOMPLETE`) · `offline` (faqat ko'rish, imzolash internet talab qiladi) · `no-permission` — faqat Buxgalterda · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `einvoice_signed`, `einvoice_accepted`, `einvoice_rejected`, `einvoice_from_receipt_created`, `goods_receipt.created_from_einvoice`, `einvoice.risk_flag_set`.
- **Bog'liq US**: US-M07-03, US-M07-05, US-M01-06, US-M10-03.

---

## BO-16 — Tasdiqlash navbati (limitdan oshgan so'rovlar)

- **Maqsad**: chegirma/qaytarish/nasiya/narx/katta pul olish/katta xarajat/limitdan katta hisobdan chiqarish so'rovlarini bitta navbatda ko'rish va PIN bilan tasdiqlash.
- **Rollar/ruxsat**: Egasi, Menejer — `kind`ga mos: `discount.approve` / `returns.approve` / `debts.approve` / `prices.approve` / `cash.withdraw` (limit) / `expenses.approve` / `stock.writeoff` (`write_off_over_limit`); foydalanuvchi faqat o'z `*.approve` huquqiga mos `kind`ni ko'radi.
- **Route**: `/app/approvals`
- **Maket**: `06-ekranlar-umumiy.md` §6 BO-16 wireframe'i + `kind` ustuni (chegirma/qaytarish/nasiya/narx/pul olish/**katta xarajat**/**limitdan katta hisobdan chiqarish**).
- **Joylashuv**: sarlavha izohi «Rol limitidan oshgan so'rovlar. Tasdiqlash — PIN bilan, rad etish — sabab bilan. Natija darhol kassaga qaytadi»; `kind` bo'yicha filtr tablari (soni bilan); har so'rov kartasi — tur chipi, muddati (`expires_at` gacha qolgan vaqt), sarlavha va tafsilot (masalan chek/tovar), kim so'radi (ism, rol, filial · kassa, vaqt), so'ralgan summa/foiz va **rol limiti**, kassir sababi; amallar — PIN maydoni + «Tasdiqlash», «Rad etish» (ochilganda «Rad etish sababi (majburiy)» + «Bekor» / «Rad etishni yuborish»); PIN xatosida «PIN noto'g'ri — yana N ta urinish qoldi». O'ng panel — «Bugun hal qilinganlar» (so'rov, kim/qachon, natija chipi), «{Rol} roli limitlari» (faqat ko'rish; «Limitlarni Rollar bo'limida o'zgartirish» → BO-11 «Rollar» tabi), offline va muddati o'tgan so'rov izohi.
- **Maydonlar**: `pin` — PIN — PIN — `Input` (4–6 raqam) — ha (tasdiqlashda) — raqam.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Tasdiqlash | `kind`ga mos `*.approve` | PIN kiritish | `POST /api/v1/approval-requests/{id}/approve` (`{pin}`) |
| Rad etish | `kind`ga mos `*.approve` | Sabab majburiy | `POST /api/v1/approval-requests/{id}/reject` (`{reason}`) |

- **Ma'lumot manbai**: `GET /api/v1/approval-requests?status=pending`, `POST /api/v1/approval-requests/{id}/approve`, `POST /api/v1/approval-requests/{id}/reject`; `kind` enumida `expense_over_limit`, `write_off_over_limit` ham bor.
- **Holatlar**: `loading` · `empty` (navbat bo'sh) · `error` (PIN noto'g'ri) · `offline` (PWA'da yangi tasdiqlash cheklangan — Menejer Android POSda inline tasdiqlaydi) · `no-permission` — Buxgalter/Omborchi/Kassirga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `approval_approved`, `approval_rejected`.
- **Bog'liq US**: US-M02-02, US-M03-01, US-M08-01, US-M09-02, US-M16-01.

---

## BO-17 — Xarajatlar

- **Maqsad**: operatsion xarajatlarni (ijara, kommunal, transport) yozish, takrorlanuvchi xarajatlarni sozlash.
- **Rollar/ruxsat**: Egasi, Menejer, Buxgalter (`expenses.create`).
- **Route**: `/app/expenses`
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│  Sana        Toifa        Summa      Manba         │
│  12.10.2026  Ijara        3 000 000  Bank           │
│                                [ + Xarajat qo'shish ]│
└──────────────────────────────────────────────────┘
```

Tablar «Xarajatlar» / «Takrorlanuvchi (N)» / «Toifalar»; «Xarajat qo'shish». Takrorlanuvchi xarajat muddati kelganda banner («{Nom} to'lash vaqti — {summa}», davr, manba, filial; «Keyinroq» / «Tasdiqlash va yozish»). KPI kartalari; «toifalar bo'yicha o'tkazilgan» (toifa, summa, ulush; jami) va «Oylar kesimida» ustunli grafik; izoh «Naqd xarajatlar kassada (POS) yoziladi va shu yerga avtomatik tushadi». Ro'yxat filtrlari — toifa, manba (Bank / Karta / Kassa (POS)), holat (O'tkazilgan / Qoralama / Tasdiq kutmoqda / Bekor qilingan); ustunlar — sana, toifa (izoh), hisob, filial, manba, summa, holat, amallar menyusi; pastda «O'tkazilgan» va «Kutilmoqda» jamlari (bekor qilinganlar kirmaydi). O'ng panel — **«Yangi xarajat»** formasi (summa, toifa → buxgalteriya hisobi avtomatik ko'rsatiladi, sana, filial, to'lov manbai, izoh, hujjat fotosi, takrorlanish davri va oyning kuni), rol limiti izohi («Menejer uchun xarajat limiti N so'm. Oshsa — o'tkazishda Egasi tasdig'iga yuboriladi»), «Qoralama» / «Saqlash va o'tkazish».

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `amount` | Summa | Сумма | `MoneyInput` | Ha | >0 | — | — |
| `categoryId` | Toifa | Категория | `Select` (`GET /expense-categories`dan, UUID) | Ha | — | — | — |
| `taxType` | Soliq turi | Вид налога | `Select` | Toifa `default_account=6410` bo'lsa Ha, aks holda yashirin | `vat\|turnover\|pit\|social\|property\|land\|other` | — | — |
| `docDate` | Sana | Дата | `Calendar` | Ha | — | Bugun | — |
| `branchId` | Filial | Филиал | `Select` | Ha | Foydalanuvchi filiallari | Topbar'dagi filial | — |
| `source` | To'lov manbai | Источник оплаты | `SegmentedControl` (Bank hisobi / Korporativ karta) | Ha | `bank\|card` (naqd xarajat BO-17'da emas — POS-14 "Xarajat" rejimi, `expense.created` orqali yoziladi) | — | — |
| `comment` | Izoh | Комментарий | `Textarea` | Yo'q | — | — | 1000 |
| `receiptPhoto` | Hujjat fotosi | Фото документа | Fayl yuklash (`POST /attachments`) | Yo'q | JPEG/PNG ≤10MB | — | — |
| `period` | Takrorlanish davri | Период повторения | `Select` | Yo'q | `none\|month\|quarter\|year` | `none` | — |
| `dayOfMonth` | Oyning kuni | День месяца | `Input` number | Takrorlanuvchida Ha | 1–28 | — | 28 |

- **Amallar**: + Xarajat qo'shish (`expenses.create`); takrorlanuvchi xarajat eslatmasini tasdiqlash ("Ijara to'lash vaqti" — bir bosishda, `POST /api/v1/recurring-expenses/{id}/confirm`); O'tkazish (`POST /api/v1/expenses/{id}/post`, limitdan oshsa «Egasi tasdig'iga yuborildi»); Bekor qilish (`POST /api/v1/expenses/{id}/cancel`, `cancel_reason` — majburiy, 3–500 belgi).
- **Ma'lumot manbai**: `GET/POST /api/v1/expenses` + `POST /api/v1/expenses/{id}/post`, `POST /api/v1/expenses/{id}/cancel`, `GET /api/v1/expense-categories`, `POST /api/v1/attachments`; `GET/POST /api/v1/recurring-expenses`, `PATCH /{id}`, `POST /api/v1/recurring-expenses/{id}/confirm`.
- **Holatlar**: `loading` · `empty` (xarajat yo'q) · `error` — standart validatsiya · `offline` (faqat ko'rish; kassadan to'langan xarajat POSda yoziladi) · `no-permission` — Kassir/Omborchiga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `expense.created`, `expense.posted`, `expense.cancelled`.
- **Bog'liq US**: US-M15-01, US-M15-02, US-M15-03.

---

## BO-18 — Yorliq va shtrix-kod chop etish

- **Maqsad**: narxi o'zgargan tovarlar uchun yorliq chop etish, ichki shtrix-kod yaratish.
- **Rollar/ruxsat**: Menejer (`labels.print`, `catalog.manage`).
- **Route**: `/app/catalog/labels`
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│  Narxi o'zgargan, chop etilmagan tovarlar:          │
│  [x] Coca-Cola 1.5L   19 000 so'm                   │
│  Shablon: [ 58×40mm ▾ ]        [ CHOP ETISH ]       │
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `template` — Shablon — Шаблон — `Select` (58×40 asosiy narx yorlig'i, 58×30, 43×25, 40×30, 30×20 mm; A4 varaq — 3×8 yoki 4×10 to'r, oddiy printer uchun) — ha — default 58×40; `selectedProducts` — `Checkbox` ro'yxat («Hammasini tanlash» bilan) — ha (≥1); `copies` — Nusxa — Копий — `QtyInput` (`−`/`+`) har qatorda — ha — ≥1, default 1; `printMethod` — Chop etish usuli — Способ печати — `RadioGroup` («Printer drayveri orqali» / «PDF fayl (serverda)» — faqat >200 yorliq yoki iOS'da faol) — ha — default drayver. Ro'yxat filtrlari: «Narxi o'zgargan» (`label_print_queue`) / «Yangi tovarlar» / «Barcha tovarlar» + qidiruv (nom yoki shtrix-kod); ustunlar — tovar (shtrix-kod), eski narx, yangi narx, o'zgargan sana, nusxa. Shtrix-kodsiz tovar qatorida «Shtrix-kod yo'q» + «Ichki kod yaratish» (shtrix-kodsiz chop etilmaydi). O'ng panel — shablon kartalari, chop etish usuli, printer holati, haqiqiy nisbatdagi yorliq ko'rinishi (do'kon nomi, sana, nom, narx/birlik, shtrix-kod), jami (N yorliq · M tovar), «PDF yuklab olish» / «Chop etish»; izoh «Chop etilgach tovarlar navbatdan olinadi», oxirgi chop etish vaqti.
- **Chop etish usuli**: brauzerda HTML/SVG + `bwip-js` (shtrix moduli 203 dpi uchun butun nuqtaga yaxlitlanadi), CSS `@page { size: Wmm Hmm; margin: 0 }`, yorliq printerining tizim drayveri orqali (drayverda qog'oz o'lchami bir marta sozlanadi — onboarding yo'riqnomasi); xom TSPL/ZPL buyruqlari MVP'da yo'q. Server PDF — faqat >200 yorliq yoki iOS uchun (qaror #54).
- **Amallar**: Ichki shtrix-kod yaratish (`catalog.manage`) → `POST /api/v1/products/{id}/barcodes/internal-generate` (EAN-13: `04` + 10 raqam + nazorat raqami — GS1 RCN 040–049, tartib raqami `internal_barcode_seq`; tarozi prefikslari 20–29 bilan to'qnashmaydi); CHOP ETISH (`labels.print`) → chop etilgandan keyin `POST /api/v1/label-print-queue/mark-printed`; **PLU eksport (CSV)** (`catalog.manage`) — tarozi uchun PLU ro'yxati (PLU kodi, nom, narx, yaroqlilik muddati) vendor dasturiga (CL-Works, Shtrih Loader, Rongta) import qilish uchun; to'g'ridan-to'g'ri tarozi yuklash brauzerdan mumkin emas.
- **Ma'lumot manbai**: `GET /api/v1/label-print-queue`, `GET /api/v1/label-templates`, `POST /api/v1/products/{id}/barcodes/internal-generate`, `POST /api/v1/label-print-queue/mark-printed`, PLU eksport — `GET /api/v1/stock-settings/plu-export`; chop etish — `react-to-print` + `bwip-js` (frontendda); >200 yorliq yoki iOS — server PDF.
- **Holatlar**: `loading` · `empty` (chop etiladigan yorliq yo'q) · `error` (printer topilmadi) · `offline` (lokal printer bilan ishlaydi) · `no-permission` — Kassir/Omborchiga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `label_printed`, `internal_barcode_generated`, `scale_plu_exported`.
- **Bog'liq US**: US-M09-04, US-M09-05, US-M09-06.

---

## BO-19 — Obuna va to'lov

- **Maqsad**: yagona tarif holatini, qo'shimcha kassa sonini, AI sarfini ko'rsatish, to'lovni amalga oshirish.
- **Rollar/ruxsat**: Egasi (`billing.manage`).
- **Route**: `/app/billing`
- **Maket**: `06-ekranlar-umumiy.md` BO-19 tasvirlangan mazmunga mos.

```
┌──────────────────────────────────────────────────┐
│  Tarif: Yagona — 99 000 so'm/oy                     │
│  Faol kassalar: 2 (1 asosiy + 1 qo'shimcha)         │
│  Keyingi to'lov: 15.11.2026                         │
│  AI limiti: 24% ishlatildi                          │
│  [ − ] 1 [ + ]  Qo'shimcha kassa   [ Oylik/Yillik ▾ ]│
│                      [  TO'LASH (Click/Payme)  ]    │
│  To'lovlar tarixi:  15.10.2026  99 000  [Kvitansiya]│
└──────────────────────────────────────────────────┘
```

- **Maydonlar**: `billingCycle` — To'lov davri — Период оплаты — `Select` (`month\|year`; yillik −20% faqat asosiy tarifga) — ha; to'lov summasi (`amount_breakdown` dan, qaror #70): oy — `99000 + 39000 × extraRegisters`, yil — `950400 + 39000 × 12 × extraRegisters`; `extraRegisters` — Qo'shimcha kassa soni — Количество дополнительных касс — **+/− stepper** — yo'q — ≥0.
- **Amallar**: + Qo'shimcha kassa — oshirish `POST /billing/addons` (`{addon_code:"extra_register", quantity}`); kamaytirish — `POST /billing/addons/extra_register/reduce` (`{quantity}`) (`requires_archiving` bo'lsa BO-12ga yo'naltirish); TO'LASH (Click/Payme checkout, tana `{provider:"click"|"payme", period:"month"|"year"}`); Kvitansiya — `GET /billing/invoices/{payment_id}`.
- **Ma'lumot manbai**: `GET /api/v1/billing/addons`, `GET /api/v1/billing/plan`, `GET /api/v1/ai/usage` (`pct_used` — "AI limiti: {pct_used}% ishlatildi", token qaytaradi), `POST /billing/checkout` (javobda `amount`, `amount_breakdown = {plan, period, addons:[{code, qty, unit_price, months}], discount}`), `GET /api/v1/billing/subscription`, `GET /api/v1/billing/payments` (to'lovlar tarixi), `GET /api/v1/billing/invoices/{payment_id}`.
- **Obuna holatlari** (qaror #70): `trial` (30 kun) → `grace` (24 soat) → `restricted`; to'lov → `active`; muvaffaqiyatli to'lovda `new_end = max(current_period_end, now()) + 1 oy | 12 oy`; `closed` — faqat platforma admini (avtomatik yo'q).
- **Holatlar**: `loading` · `empty` — yo'q (har doim obuna mavjud) · `error` (to'lov o'tmadi) · `offline` (faqat ko'rish) · `no-permission` — faqat Egasida · `subscription-restricted` — bu ekran `restricted` holatda **ochilmaydi** — sessiya bekor qilingan; to'lov faqat BO-01'ning `reason=subscription_expired` variantidagi `GET /billing/pay` tor sahifasida · **`subscription-grace`** — to'liq ishlaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `billing_checkout_started`, `subscription_payment_succeeded`, `extra_register_added`, `extra_register_removed`, `billing_invoice_viewed`.
- **Bog'liq US**: US-M17-02, US-M17-03.

---

## BO-20 — Telegram va bildirishnomalar

- **Maqsad**: Egasi/Menejer Telegram akkauntini ulash (Telegram ulash joyi — shu ekran, qaror #56 d), kunlik hisobot vaqtini va ogohlantirish turlarini sozlash.
- **Rollar/ruxsat**: Egasi (`telegram.link`, `notifications.manage`), Menejer (`telegram.link` — o'z hisobi, Egasi ruxsati bilan).
- **Route**: `/app/settings/telegram`
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│  Telegram: 🟢 ulangan (@egasi_username)             │
│  Kunlik hisobot vaqti: [ 21:00 ▾ ]                  │
│  Ogohlantirishlar:                                  │
│   [x] Kam qolgan tovar     [x] Kassa farqi          │
│   [x] Limitdan oshgan      [x] Davlat hisoboti      │
│   [x] Offline 40/48 soat   [x] Obuna eslatmasi      │
└──────────────────────────────────────────────────┘
```

- **Joylashuv**: tepada Sozlamalar ichki tablari (aktiv — Telegram), «Bekor qilish» / «Saqlash». **«Telegram akkaunt»** kartasi — joriy foydalanuvchi: holat chipi («Ulangan · @username»), ulangan sana (`GET /notifications/telegram/status`), oxirgi xabar va shu oy yuborilgan xabarlar soni (`GET /notifications-log`, `notifications.manage`), «Uzish»; ulanmagan bo'lsa yoki «Boshqa akkauntni ulash» — QR + `bot_url` havolasi, «Havola 10 daqiqa amal qiladi · HH:mm gacha», «Nusxa olish», «Yangi havola»; xato banneri «bot ulanmadi — havola muddati o'tgan yoki botda «Start» bosilmagan» + «Qayta urinish». **«Ogohlantirishlar»** — guruhlangan `alertToggles` («N / M yoqilgan»). **«Kunlik hisobot»** — vaqt tanlovi (20:00 / 21:00 / 22:00 / 23:00, Toshkent vaqti; izoh «Smenalar yopilmagan bo'lsa ham shu vaqtgacha bo'lgan savdo yuboriladi») va **xabar ko'rinishi** namunasi (savdo, cheklar, o'rtacha chek, to'lov usullari bo'yicha, kecha bilan farq, «Diqqat» qatori).
- **Maydonlar**: `dailyReportTime` — Kunlik hisobot vaqti — Время ежедневного отчёта — `Select` (soat) — ha — default 21:00; `alertToggles.*` — Ogohlantirish turlari — Типы уведомлений — `Switch` (har biri) — yo'q — default barcha yoqilgan.
- **Amallar**: Telegram ulash (QR/havola orqali `Start`) — `telegram.link` → `POST /api/v1/notifications/telegram/link-start`; uzish — `DELETE /api/v1/notifications/telegram/link`; sozlamalarni saqlash — `notifications.manage`.
- **Ma'lumot manbai**: `POST /api/v1/notifications/telegram/link-start` (+ `GET /api/v1/notifications/telegram/status`, `DELETE /api/v1/notifications/telegram/link`), `GET/PATCH /api/v1/notification-settings`.
- **Holatlar**: `loading` · `empty` — yo'q · `error` (bot ulanmadi) · `offline` — ekran ochilmaydi (ulash online talab qiladi) · `no-permission` — Kassir/Omborchi/Buxgalterga yopiq · `subscription-restricted` — kirilmaydi.
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `telegram_linked`, `notification_settings_updated`.
- **Bog'liq US**: US-M18-01, US-M18-02, US-M18-03.

---

## BO-21 — Ro'yxatdan o'tish va birinchi sozlash (onboarding wizard)

- **Maqsad**: yangi Egasini 2 daqiqada ro'yxatdan o'tkazish (tenant ①② dan keyin darhol yaratiladi), boshlang'ich katalog/qoldiq/qarzlarni kiritish, OFD/e-faktura ulash yo'riqnomasini ko'rsatish, iOS/Android o'rnatish bo'yicha yo'naltirish.
- **Rollar/ruxsat**: Yangi foydalanuvchi (ruxsatsiz, o'z-o'ziga ro'yxatdan o'tish).
- **Route**: `/onboarding`
- **Maket** (bosqichlar — wizard, `Tabs`/step indikator bilan):

```
┌──────────────────────────────────────────────────┐
│  ① Telefon+parol yoki Google → ② Do'kon →           │
│  ③ Tovarlar/Qoldiq → ④ Boshlang'ich qarzlar →        │
│  ⑤ OFD/e-faktura → ⑥ Qurilma o'rnatish (/install)    │
├──────────────────────────────────────────────────┤
│   [ Joriy bosqich kontenti ]                        │
│                      [ Orqaga ]   [ Davom ]         │
└──────────────────────────────────────────────────┘
```

Sahifa (sidebarsiz, 1440×900): **chap panel** — «ERP» logotipi, «2 daqiqada ro'yxatdan o'ting», izoh (do'kon hisobi 1–2-bosqichdan keyin yaratiladi, 30 kunlik bepul sinov, karta talab qilinmaydi, qolgan bosqichlarni keyin Sozlamalarda bajarish mumkin), bosqichlar ro'yxati — har bosqichda nom, qisqa izoh va holat (`bajarildi` / `joriy` / `keyingi` / `ixtiyoriy` — ④⑤⑥), pastda «Yordam kerakmi?» (qo'llab-quvvatlash Telegram boti va ish vaqti); **o'ng panel** — progress («N-bosqich / 6»), «30 kunlik bepul sinov» chipi, «UZ · RU», bajarilgan bosqich xulosasi («O'zgartirish» havolasi bilan), joriy bosqich formasi, «Orqaga» / «Davom» (`Enter`). Bosqich izohlari: ① «Telegram/SMS kod, parol, ism»; ② «Nom, faoliyat turi, shakl, rozilik»; ③ «Qo'lda, Excel/CSV yoki foto (AI)»; ④ «Ism, telefon, summa»; ⑤ «Ulash yo'riqnomasi, Telegram bot»; ⑥ «Android, iOS yoki Windows». ② da «Davom» ostida sinov davri sanalari ko'rsatiladi (boshlanish – tugash sanasi, 30 kun).

- **Maydonlar** (bosqich bo'yicha) — (qaror #34):

| Bosqich | Maydon | Label (uz) | Label (ru) | Tur | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|---|
| ① | `signupMethod` | Usul | Способ | Tugmalar: "Telefon + parol" / "**Google bilan kirish**" | Ha | — | Telefon + parol | — |
| ①-telefon | `phone` | Telefon | Телефон | `Input` mask | Ha (telefon yo'li) | `+998` | — | 17 |
| ①-telefon | `otp` | Tasdiqlash kodi | Код подтверждения | `Input` 6 raqam | Ha (telefon yo'li) | 6 raqam, 5 daq TTL; kod **Telegram bot**ga yuboriladi, foydalanuvchi hali botga ulanmagan bo'lsa bot havolasi ko'rsatiladi; Telegram mavjud bo'lmasa **SMS** (zaxira) | — | 6 |
| ①-telefon | `password` | Parol | Пароль | `Input type=password` | Ha (telefon yo'li) | 8–128 belgi (`14` §4) | — | 128 — login telefon+parol bilan, parolsiz hisob kira olmaydi |
| ① | `ownerName` | Ism | Имя | `Input` | Ha | 2–100 | — | 100 |
| ①-Google | — | — | — | Google OIDC redirect tugmasi | Ha (Google yo'li) | — | — | Qaytgandan keyin telefon raqami (STIR/fiskal uchun) so'raladi |
| ② | `storeName` | Do'kon nomi | Название магазина | `Input` | Ha | 2–100 | — | 100 |
| ② | `businessType` | Faoliyat turi | Вид деятельности | `Select` | Ha | Ro'yxatdan biri | — | — |
| ② | `legalForm` | Tashkiliy-huquqiy shakl | Организационно-правовая форма | `RadioGroup` kartalari (MChJ / AJ / Xususiy korxona / Yakka tadbirkor, har birida qisqa izoh) | Ha | `llc\|jsc\|private_enterprise\|sole_proprietor` (yakka tadbirkorda QR to'lov — to'lov tashkiloti maxsus QR'i, bank UzQR emas) | `llc` | — |
| ② | `acceptTerms` | Foydalanish shartlariga roziman | Принимаю условия использования | `Checkbox` + shartlar matni havolasi (o'zbek tilida, versiyali) | **Ha** | Belgilanmasa "Davom" o'chiq | O'chiq | — |
| ② | `aiCrossBorderConsent` | Ma'lumotlarni AI xizmatiga (chet elga — Anthropic, AQSh) uzatishga roziman | Согласен на передачу данных AI-сервису (за рубеж) | `Checkbox` (alohida, ixtiyoriy) + tushuntirish | Yo'q | Belgilanmasa AI-03 (hujjat rasmini o'qish) o'chiq qoladi, keyin BO-14 da yoqiladi; matnli AI maskalangan holda ishlaydi | O'chiq | — |
| ③a "Tovarlar" | `method` | Kiritish usuli | Способ ввода | Tugmalar | Ha | Qo'lda/Excel-CSV/Foto (AI-03) | — | — |
| ③b "Boshlang'ich qoldiq" | `openingStockMethod` | Kiritish usuli | Способ ввода | Tugmalar | Yo'q | Excel-CSV/qo'lda | — | — |
| ④ | `debts[]` | Boshlang'ich qarzlar | Начальные долги | Jadval/Excel | Yo'q | ism+telefon+summa | — | — |
| ⑤ | `connectNow` | Hozir ulashni istaysizmi? | Подключить сейчас? | `Switch` | Yo'q | — | Yo'q (keyin ham mumkin) | — |
| ⑥ | `platform` | Qurilma turi | Тип устройства | Tugmalar | Yo'q | Android/iOS/Windows | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Davom (② dan keyin) | — | Yo'q | `POST /auth/signup` `{phone\|google_id_token, otp, password, owner_name, store_name, business_type, legal_form, accepted_terms_version, ai_cross_border_consent}` — tenant ①② dan keyin darhol yaratiladi, ③–⑥ dan oldin (aks holda import qiladigan tenant yo'q); ② da `tenants.accepted_terms_version/accepted_terms_at/accepted_terms_ip` va (rozilik berilgan bo'lsa) `POST /api/v1/tenant/consents` → `consents` yozuvi + `settings.ai_cross_border_enabled=true` (qaror #61) |
| Davom (①, ③–⑥ bosqichlarida) | — | Yo'q | Keyingi bosqich |
| Orqaga | — | Yo'q | Oldingi bosqich |
| O'tkazib yuborish (④,⑤,⑥ bosqichlarida) | — | Yo'q | Keyinroq sozlamalarda bajarish mumkin |
| Yakunlash | — | Yo'q | 30 kunlik sinov boshlangan, BO-02ga yo'naltiriladi |

- **UX-INSTALL (⑥ bosqich)**: `<InstallGuide embedded />` — bu bosqich `/install` route'ini ichiga oladi (nusxasi emas), batafsil — yuqoridagi **UX-INSTALL** bo'limi.
- **Owner Telegram link**: ⑤ bosqichda (yoki keyin BO-20 orqali) "Telegram botni ulash" tezkor havolasi — BO-20 bilan bir xil oqim, lekin onboarding ichida qisqartirilgan (faqat QR, batafsil sozlama BO-20da).
- **Ma'lumot manbai**: `POST /auth/signup` (telefon yo'li) yoki `GET /auth/google/start` → `GET /auth/google/callback` (Google yo'li, qaror #34); `POST /auth/otp/request` (`purpose=signup`, Telegram bot birinchi/SMS zaxira) + `POST /auth/otp/verify`; Excel/CSV: `GET /api/v1/import-jobs/templates/products` → `POST /api/v1/import-jobs` (`kind=products`) → `/validate` → `/commit`; qo'lda — `POST /api/v1/products`; boshlang'ich qoldiq — `POST /api/v1/import-jobs` (`kind=opening_stock`) yoki qo'lda `POST /stock-openings`; boshlang'ich qarzlar — `POST /api/v1/import-jobs` (`kind=opening_debts`) → `/validate` → `/commit`, qo'lda — `POST /api/v1/debt-openings` → `/post`; AI-03 foto — `POST /api/v1/attachments` → `POST /api/v1/ai/ocr/jobs` (`doc_type_hint=catalog`) → poll `GET /api/v1/ai/ocr/jobs/{id}` → `POST /api/v1/ai/ocr/jobs/{id}/confirm`, ruxsat `ai.ocr.use` + `catalog.manage`.
- **Holatlar**: `loading` (OTP kutilmoqda — Telegram yoki SMS) · `empty` — yo'q (wizard har doim bo'sh boshlanadi) · `error` (OTP kelmadi — qayta yuborish/zaxira kanalga o'tish, `OTP_INVALID`, telefon allaqachon ro'yxatda — `VALIDATION_ERROR`; Google yo'lida — "Google autorizatsiyasi muvaffaqiyatsiz") · `offline` — wizard online talab qiladi (ro'yxatdan o'tish) · `no-permission` — yo'q · `subscription-restricted` — tegishli emas (hali obuna yo'q, 30 kun sinov avtomatik). (qaror #34)
- **Klaviatura**: `Enter` keyingi bosqichga o'tadi.
- **Audit/analitika**: `onboarding_started`, `onboarding_step_completed`, `onboarding_completed`, `onboarding_skipped_step`, `terms_accepted`, `consent.ai_cross_border_changed`.
- **Bog'liq US**: US-M17-01, US-M04-04, US-M08-07. Oferta/rozilik matnining yuridik tasdig'i — 26 #127 (OQ-042).

---

## BO-22 — 1C integratsiyasi sozlamalari va moslashtirish (M19, Bosqich 7)

- **Maqsad**: kompyuterni (ERP 1C Agent) ulash, 1C bazasini tekshirish, filiallarni bog'lash, rejim/jadval sozlash va ERP ↔ 1C moslashtirish ustasini o'tish; jurnal va diagnostika. Yagona manba — `33-1c-integratsiya.md` §13.1 (nomlar o'zgarishsiz).
- **Rollar/ruxsat**: ko'rish — `onec.view` (Egasi, Menejer, Buxgalter); «Kompyuter», «Bazalar», «Sozlamalar» yorliqlaridagi o'zgartirish — `onec.settings.manage` (Egasi); «Moslash» — `onec.mapping.edit` (Egasi, Buxgalter); «1C da yaratish» tasdig'i — `onec.refs.create` (Egasi, Buxgalter); avto-tasdiq kaliti — faqat Egasi (`OWNER_ONLY`, qaror #40).
- **Route**: `/app/settings/onec` (yorliqlar `?tab=computer|bases|checks|mapping|settings|log`), ulash sahifasi `/app/settings/onec/pair?user_code=` (agentdagi `verification_uri`).
- **Maket**:

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ 1C integratsiyasi        [Kompyuter] [Bazalar] [Tekshiruv] [Moslash] [Sozlamalar] [Jurnal] │
├───────────────────────────────────────────────────────────────────────────────┤
│ Kompyuter: 🟢 DOKON-PC · ERP 1C Agent v1.4.2 · oxirgi aloqa 18:02            │
│   Windows 10 · 1C 8.3.25 (64-bit) · COM ✓       [Diagnostika]  [Uzish]        │
│   [+ Kompyuterni ulash]  → kod: [ WDJB-MJHT ]  [Tekshirish]                     │
├───────────────────────────────────────────────────────────────────────────────┤
│ Baza: «Do'kon BP» · Бухгалтерия для Узбекистана 3.0.64.8 · D:\1C\Shop          │
│   Holat: ✓ tayyor   1C ga yozishga ruxsat: [● ON]   Kompyuterda ruxsat: ✓     │
│   Filiallar: [Chilonzor ▾ → Do'kon BP] [Yunusobod ▾ → —]                       │
├───────────────────────────────────────────────────────────────────────────────┤
│ Moslash (ustoz)  1 Tashkilot ✓ · 2 Omborlar ✓ · 3 Kassalar ✓ · 4 To'lov turlari ⚠1 │
│                  5 QQS ✓ · 6 Birliklar ✓ · 7 Tovarlar ⚠ 12 · 8 Kontragentlar ✓ · 9 Qoldiq │
│ Tovarlar: [Moslanmagan ▾] [qidirish…]          [1C dan o'qish] [Avto-moslash]  │
│ ┌ ERP tovar ──────────── MXIK ───── Shtrix ── 1C taklif ─────────── Holat ───┐ │
│ │ Coca-Cola 1,5 l      02202001… 4780… Кока-Кола 1,5л (aniq)    [✓]      │ │
│ │ Non "Bo'lka"         —         —     —                        [1C da yaratish] [Tanlash] │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ [Barcha aniq moslarni tasdiqlash (38)]   1C da yaratiladi: 3 ta  [Ko'rib tasdiqlash] │
└───────────────────────────────────────────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `user_code` | Ulash kodi | Код подключения | `Input` (mask `XXXX-XXXX`) | Ha (ulashda) | 8 belgi, alifbo `BCDFGHJKLMNPQRSTVWXZ` | — | 9 |
| `name` | Kompyuter nomi | Имя компьютера | `Input` | Yo'q | — | `pc_name` | 64 |
| `write_enabled` | 1C ga yozishga ruxsat | Разрешить запись в 1С | `Switch` | — | faqat `ready`/`error` holatidagi bazada yoqiladi | o'chiq | — |
| `branch_bindings[].base_id` | Filial → 1C bazasi | Филиал → база 1С | `Select` | Yo'q | bitta filial — bitta faol baza | — | — |
| `bound_from` | Qaysi sanadan | С какой даты | `DatePicker` | Ha (bog'lashda) | ≥ `start_date` | — | — |
| `mode` | Yuborish rejimi | Режим выгрузки | `RadioGroup` (`To'liq` / `Faqat sotuv`) | Ha | `full`\|`sales_only`; `sales_only` tanlanganda ogohlantirish matni | `full` | — |
| `start_date` | Boshlanish sanasi | Дата начала | `DatePicker` | Ha | 1C taqiq sanasidan keyin (aks holda ogohlantirish); `done` partiyalardan keyin o'zgarmaydi | — | — |
| `orp_grouping` | ОРП guruhlash | Группировка ОРП | `Select` (`kassa × kun` / `filial × kun`) | Ha | `register_day`\|`branch_day` | `register_day` | — |
| `schedule_mode` | Yuborish vaqti | Время выгрузки | `RadioGroup` (`Qo'lda` / `Smena yopilganda` / `Har kuni soat`) | Ha | `manual`\|`on_shift_close`\|`at_time` | `manual` | — |
| `schedule_time` | Soat | Время | `TimePicker` | `at_time` da Ha | Toshkent vaqti, `HH:mm` | — | — |
| `auto_approve` | Ogohlantirishsiz kunni avtomatik tasdiqlash | Автоподтверждение без предупреждений | `Switch` | — | faqat Egasi; `manual` rejimda yashirin | o'chiq | — |
| `readiness_policy` | Ochiq smena bo'lsa | При открытой смене | `Select` (`Kutish` / `Ogohlantirib davom etish`) | Ha | `all_shifts_closed`\|`allow_open` | `all_shifts_closed` | — |
| `ref_create_policy` | 1C da yangi element yaratish | Создание элементов в 1С | `Select` (`Tasdiq bilan` / `Taqiq`) | Ha | `ask`\|`deny` | `ask` | — |
| `send_bank_payments`, `send_bank_settlements`, `send_shift_variance` | Qo'shimcha hujjatlar | Дополнительные документы | `Checkbox` | — | har biri yonida «bank-klient bilan dublikat bo'lishi mumkin» izohi | o'chiq | — |
| `same_day_returns`, `card_refund_mode`, `stock_preflight` | Kengaytirilgan | Расширенные | `Select` («Kengaytirilgan» ochiladigan blokda) | — | `33` §5.4 enum'lari | `33` §5.4 standartlari | — |
| `notify_user_ids` | Xabar oluvchilar | Получатели уведомлений | `MultiSelect` | Yo'q | faqat `onec.view` ruxsatli xodimlar | — | — |
| moslash qatori `onec_guid` | 1C elementi | Элемент 1С | `Combobox` (W-22 qidiruv) | — | turi `entity`ga mos; o'chirishga belgilangan va papkalar ko'rsatilmaydi | — | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Kompyuterni ulash → Tekshirish → Ulash | `onec.settings.manage` | PK nomi, IP, OS, so'rov vaqti: «Bu sizning kompyuteringizmi?» | `GET /api/v1/onec-agents/pairing-requests/{user_code}` (W-03) → `POST /api/v1/onec-agents/pair` (W-04) |
| Uzish | `onec.settings.manage` | Sabab tanlash; «Navbatdagi kunlar shu kompyuter qayta ulanmaguncha kutadi» | `POST /api/v1/onec-agents/{id}/revoke` (W-05) |
| Bazalarni qayta qidirish | `onec.settings.manage` | Yo'q | `POST /api/v1/onec-agents/{id}/discover-bases` (W-06) |
| Diagnostika | `onec.settings.manage` | Kunlar soni | `POST /api/v1/onec-agents/{id}/diagnostics-requests` (W-07) |
| 1C ga yozishga ruxsat (kalit) | `onec.settings.manage` | Yoqishda: «1C bazasiga ERP hujjatlari yoziladi va o'tkaziladi» | `PATCH /api/v1/onec-bases/{id}` (W-11) |
| Tekshiruvlarni qayta ishga tushirish / Litsenziya sinovi | `onec.settings.manage` | Litsenziya sinovida: «1C ni shu kompyuterda oching, so'ng Davom etish» | `POST /api/v1/onec-bases/{id}/checks` (W-12) |
| Bu kompyuterga o'tkazish | `onec.settings.manage` | «Moslashtirish va tarix saqlanadi» | `POST /api/v1/onec-bases/{id}/reassign` (W-14) |
| Arxivlash | `onec.settings.manage` | Sabab | `POST /api/v1/onec-bases/{id}/archive` (W-15) |
| Filial bog'lash / bog'lanishni olib tashlash | `onec.settings.manage` | Yo'q | `PUT` / `DELETE /api/v1/onec-branch-bindings/{branch_id}` (W-17 / W-18) |
| Sozlamalarni saqlash | `onec.settings.manage` (+ avto-tasdiq — faqat Egasi) | `mode='sales_only'`: «Kirimlarni buxgalter 1C'da o'zi kiritadi, qoldiq tekshiruvi majburiy» | `PATCH /api/v1/onec-settings/{base_id}` (W-20) |
| 1C dan o'qish | `onec.mapping.edit` | Yo'q | `POST /api/v1/onec-catalog-items/refresh` (W-21) |
| Avto-moslash | `onec.mapping.edit` | Yo'q | `POST /api/v1/onec-mappings/auto-match` (W-25) |
| Tasdiqlash (qator) / Barcha aniq moslarni tasdiqlash | `onec.mapping.edit` | Ommaviyda soni ko'rsatiladi | `POST /api/v1/onec-mappings/confirm` (W-26) |
| Tanlash (qo'lda) | `onec.mapping.edit` | Yo'q | `GET /api/v1/onec-catalog-items` (W-22) → W-26 |
| Bog'lanishni olib tashlash | `onec.mapping.edit` | Sabab | `DELETE /api/v1/onec-mappings/{id}` (W-27) |
| Qiymatlarni saqlash (to'lov turi, QQS, hisoblar) | `onec.mapping.edit` | 5710 bo'lmagan to'lov turida ogohlantirish (`ONEC_PAYMENT_ACCOUNT_NOT_TRANSIT`) | `PUT /api/v1/onec-value-mappings` (W-29) |
| 1C da yaratish (taklif) | `onec.mapping.edit` | Karta: qaysi maydonlar bilan yaratiladi | `POST /api/v1/onec-ref-create-requests` (W-31) |
| Ko'rib tasdiqlash / Rad etish (yaratish) | `onec.refs.create` | Ro'yxat (before/after karta), «1C da N ta element yaratiladi» | `POST /api/v1/onec-ref-create-requests/approve` (W-32) / `POST …/{id}/reject` (W-33) |
| Qoldiqni solishtirish (ustoz 9-qadam) | `onec.export.prepare` | `start_date` holatiga | `POST /api/v1/onec-reconciliations` (W-53, `kind='opening_stock'`) |

- **Ma'lumot manbai**: `GET /api/v1/onec-agents` (W-01), `GET /api/v1/onec-agents/{id}` (W-02), `GET /api/v1/onec-agents/{id}/logs` (W-08), `GET /api/v1/onec-bases`, `GET /api/v1/onec-bases/{id}` (W-09, W-10), `GET /api/v1/onec-bases/{id}/checks` (W-13), `GET /api/v1/onec-branch-bindings` (W-16), `GET /api/v1/onec-settings/{base_id}` (W-19), `GET /api/v1/onec-catalog-items` (W-22), `GET /api/v1/onec-mappings/summary` (W-23), `GET /api/v1/onec-mappings` (W-24), `GET /api/v1/onec-value-mappings` (W-28), `GET /api/v1/onec-ref-create-requests` (W-30), `GET /api/v1/onec-reconciliations` (W-52, jurnal/drift); agent holati `GET /api/v1/onec-status` (W-55, har 30 s). To'liq shakllar — `33-1c-integratsiya.md` §10.
- **Holatlar**: `loading` · `empty` (agent ulanmagan — «ERP 1C Agent ni yuklab oling» + o'rnatish yo'riqnomasi havolasi) · `error` (tekshiruv `fail` — har biri matn va tuzatish maslahati bilan, `errors.onec.*` / `fix_hints.onec.*`; `ONEC_EDITION_NO_COM`, `ONEC_CLOUD_BASE_UNSUPPORTED`, `ONEC_SALE_PRICE_ACCOUNTING_UNSUPPORTED` — «qamrovdan tashqari» qizil kartasi) · `offline` (faqat ko'rish, amallar o'chiq) · `no-permission` (Kassir/Omborchiga yopiq; Menejer — faqat ko'rish) · `subscription-restricted` (kirilmaydi).
- **Klaviatura**: `Ctrl+K`; moslash jadvalida `↑/↓` — qator, `Enter` — taklifni tasdiqlash, `/` — qidiruv.
- **Audit/analitika**: audit (`33` §11.3) — `onec.agent.*`, `onec.base.*`, `onec.binding.changed`, `onec.settings.changed`, `onec.auto_approve.changed`, `onec.mapping.*`, `onec.value_mapping.changed`, `onec.ref_create.*`; analitika — `onec_pairing_started`, `onec_mapping_wizard_step_completed`.
- **Bog'liq US**: US-M19-01, US-M19-02, US-M19-03, US-M19-04, US-M19-05, US-M19-13, US-M19-17 (va US-M19-18 — «Jurnal» yorlig'idagi drift ro'yxati).

---

## BO-23 — 1C ga yuborish (kunlar) (M19, Bosqich 7)

- **Maqsad**: kun yopilgach preview'ni ko'rish, tayyorlikni tekshirish, tasdiqlash va 1C ga yuborish; progress, natija, xatolarni tuzatish, kalendar tarixi (BP-14). Yagona manba — `33-1c-integratsiya.md` §13.2.
- **Rollar/ruxsat**: ko'rish — `onec.view` (Egasi, Menejer, Buxgalter); tayyorlash/qayta qurish/sinov ko'rinishi/qayta solishtirish — `onec.export.prepare`; tasdiqlash/bekor qilish/qurilmani istisno qilish — `onec.export.approve`; qayta yuborish/o'tkazib yuborish/qabul/yangi revision/tuzatuvchi hujjat — `onec.export.correct` (Egasi, Buxgalter). Tugmalar `<Can>` bilan ruxsat darajasida yashiriladi.
- **Route**: `/app/onec/exports` (kalendar + standart kun), `/app/onec/exports/:batchId`.
- **Maket**:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ 1C ga yuborish   Baza: [Do'kon BP ▾]   Sana: [15.10.2026 ▾]   🟢 DOKON-PC v1.4.2 │
├────────────────────────────────────────────────────────────────────────────────┤
│ Tayyorlik:  ✓ 3/3 smena yopilgan   ✗ Kassa-2 (Android) oxirgi sinxron 14:05       │
│             [Qurilmani istisno qilish…]   ✓ agent onlayn   ⚠ 5 ta tovar moslanmagan [Moslash] │
├────────────────────────────────────────────────────────────────────────────────┤
│ ERP jami 45 230 000.00  =  1C ga yoziladi 45 230 000.00                           │
│ #  Hujjat (1C)                         Filial/Kassa   Qator   Summa         Holat   │
│ 1  Поступление · M-01-…231 · Oziq MChJ  Chilonzor       14   5 600 000.00   yangi  │
│ 2  ОРП · Kassa-1                        Chilonzor      312  44 100 000.00   yangi  │
│ 3  Реализация · K-01-…154 · Aliyev      Chilonzor        3   1 130 000.00   yangi  │
│ 4  ПКО · qarz to'lovi · Aliyev          Chilonzor        —     500 000.00   yangi  │
│ ⚠ Z-hisobot farqi Kassa-2: 12 000.00   ☐ Ko'rdim                                │
│                                         [Bekor qilish]  [ 1C ga yuborish ]        │
├────────────────────────────────────────────────────────────────────────────────┤
│ Progress: 1 ✓ № 0000-000231 · 2 ⏳ o'tkazilmoqda (60%) · 3 kutilmoqda · 4 kutilmoqda │
├────────────────────────────────────────────────────────────────────────────────┤
│ Oktabr 2026:  … 12🟩 13🟩 14🟨 15🟦 16⬜ …                                         │
└────────────────────────────────────────────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `base_id` | Baza | База | `Select` | Ha | bitta baza bo'lsa yashirin | yagona/oxirgi tanlangan baza | — |
| `business_date` | Sana | Дата | `DatePicker` + oy kalendari | Ha | `start_date ≤ D ≤ bugun` (Toshkent) | eng eski tayyorlanmagan/yakunlanmagan kun; yo'q bo'lsa kecha | — |
| `acknowledged_warnings[]` | Ko'rdim | Ознакомлен | `Checkbox` (har ogohlantirish yonida) | har ogohlantirish uchun Ha | barchasi belgilanmaguncha «1C ga yuborish» o'chiq | — | — |
| `exclude.device_ids[]` | Istisno qilinadigan qurilmalar | Исключаемые устройства | `Checkbox` ro'yxati (`ONEC_DEVICES_NOT_SYNCED` qurilmalari) | Ha (istisnoda) | kamida 1 ta | — | — |
| `exclude.reason` | Istisno sababi | Причина исключения | `Textarea` | Ha (istisnoda) | ≥ 10 belgi | — | 500 |
| `cancel.reason`, `accept.reason`, `skip.note`, `correction.reason` | Sabab | Причина | `Textarea` | Ha | ≥ 10 belgi | — | 500 |
| `correction_date` | Tuzatish sanasi (1C) | Дата корректировки (1С) | `DatePicker` | Ha (tuzatishda) | > 1C taqiq sanasi | bugun | — |
| `overwrite_changed_in_1c` | ERP bilan almashtirish | Заменить данными ERP | `Checkbox` (yangi revision dialogida, `changed_in_1c` obyekt bo'lsa) | Yo'q | — | o'chiq | — |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Tayyorlash | `onec.export.prepare` | Yo'q | `POST /api/v1/onec-export-batches` (W-36); `422 ONEC_NOTHING_TO_EXPORT` — «Bu kunda 1C ga yuboriladigan hujjat yo'q» |
| Yangilash (qayta qurish) | `onec.export.prepare` | Yo'q | `POST /api/v1/onec-export-batches/{id}/rebuild` (W-41) |
| Qurilmani istisno qilish | `onec.export.approve` | Qurilma ro'yxati + sabab; «Bu qurilmaning kech cheklari yangi revision bilan yuboriladi» | `POST /api/v1/onec-export-batches/{id}/exclude-devices` (W-42) |
| **1C ga yuborish** | `onec.export.approve` | «"Do'kon BP" bazasiga N ta hujjat yoziladi va o'tkaziladi. Davom etasizmi?» (+ `ONEC_UNPOST_REQUIRED` bo'lsa o'chirishga belgilanadiganlar ro'yxati) | `POST /api/v1/onec-export-batches/{id}/approve` (W-43, `{preview_hash, acknowledged_warnings}`); `409 ONEC_PREVIEW_CHANGED` → yangi preview yuklanadi + «Ma'lumot o'zgardi» banneri (forma xatosi emas) |
| Bekor qilish | `onec.export.approve` | Sabab | `POST /api/v1/onec-export-batches/{id}/cancel` (W-44); `sending` da — joriy hujjat tugagach to'xtaydi, yozilganlari 1C da qoladi |
| Sinov ko'rinishi (hujjat) | `onec.export.prepare` | Yo'q | `POST /api/v1/onec-export-batches/{id}/items/{item_id}/preview` (W-40) — 1C da qanday ko'rinishi (maydonlar) |
| Faqat xatolarni qayta yuborish | `onec.export.correct` | Yo'q | `POST /api/v1/onec-export-batches/{id}/resend-failed` (W-45) |
| O'tkazib yuborish (hujjat) | `onec.export.correct` | Sabab; «1C ga yozilmaydi» (bog'liq to'lov hujjatlari ham) | `POST /api/v1/onec-export-batches/{id}/items/{item_id}/skip` (W-46) |
| Qabul qilish (`partial`/`mismatch`) | `onec.export.correct` | Sabab; farq jadvali | `POST /api/v1/onec-export-batches/{id}/accept` (W-47) — keyingi kunlar navbatga chiqadi |
| Yangi revision | `onec.export.correct` | `changed_in_1c` bo'lsa «ERP bilan almashtirish» belgisi | `POST /api/v1/onec-export-batches/{id}/new-revision` (W-48) |
| Tuzatuvchi hujjat | `onec.export.correct` | Sana + sabab; «1C'da {D} uchun faqat farq {correction_date} sanasida yoziladi» | `POST /api/v1/onec-export-batches/{id}/correction` (W-49) |
| Qayta solishtirish | `onec.export.prepare` | Yo'q | `POST /api/v1/onec-export-batches/{id}/reconcile` (W-50) |
| Moslash / 1C da yaratish | `onec.mapping.edit` / `onec.refs.create` | Yo'q | BO-22 `?tab=mapping` (`params.by_entity` filtri bilan) |

- **Ma'lumot manbai**: `GET /api/v1/onec-export-batches` (W-34), `GET /api/v1/onec-export-batches/calendar` (W-35, oy kalendari), `GET /api/v1/onec-export-batches/{id}` (W-37 — `preview`, `readiness`, `blocking_issues`, `warnings`, `preview_hash`), `GET /api/v1/onec-export-batches/{id}/items` (W-38; ExportItem ustunlari stepper uchun `attempts`/`max_attempts` — «qayta urinish n/8», `progress` — yozish foizi), `GET /api/v1/onec-export-batches/{id}/items/{item_id}` (W-39 — 1C ning asl xabari, o'zbekcha izoh, maslahat), `GET /api/v1/onec-export-batches/{id}/events` (W-51); progress — har 2 s so'rov, faqat `queued`/`sending`/`verifying` holatida (SSE — keyinroq); sarlavha chipi — `GET /api/v1/onec-status` (W-55), agent nomi/versiyasi — W-37 `agent.name`, `agent.agent_version`.
- **Holatlar**: `loading` · `empty` (`not_prepared` — «Kun tayyorlanmagan» + [Tayyorlash]; hujjat yo'q — «Bu kunda 1C ga yuboriladigan hujjat yo'q»; 1C bazasi ulanmagan — BO-22 ga havola) · `blocked` (`blocking_issues` — qizil checklist, «1C ga yuborish» o'chiq) · `waiting` (`approved`/`queued` — «Navbatda: oldingi kunlar / kompyuter o'chiq») · `progress` (`sending`/`verifying`, hujjat stepper: kutilmoqda / yozilmoqda / ✓ № … / ⚠ qayta urinish n/8 / ✗ xato + maslahat) · `success` (yashil banner, 1C raqamlari) · `partial` (sariq, xatolar ro'yxati, [Faqat xatolarni qayta yuborish]) · `mismatch` (ERP vs 1C farq jadvali) · `failed` · `stale` (`needs_resync` — «N ta kech hujjat — revision tavsiya etiladi») · `error` (API) · `offline` (faqat ko'rish) · `no-permission` (Kassir/Omborchi; Menejer — faqat ko'rish) · `subscription-restricted` (kirilmaydi). Kalendar ranglari (`08-dizayn-tizimi.md`): 🟩 `done`; 🟨 `partial`/`mismatch`/`failed`; 🟦 `approved`/`queued`/`sending`/`verifying`; 🟪 `preview` (tasdiq kutmoqda); 🟥 bloklangan (`blocking_issues`); ⬜ `not_prepared` / `draft` / `cancelled`; bo'sh — hujjat yo'q.
- **Klaviatura**: `Ctrl+K`; `←/→` — oldingi/keyingi kun; `Ctrl+Enter` — «1C ga yuborish» dialogini ochish (faqat ruxsat va tayyorlik bo'lsa).
- **Audit/analitika**: audit (`33` §11.3) — `onec.export.prepared`, `onec.export.approved`, `onec.export.auto_approved`, `onec.export.cancelled`, `onec.export.resent`, `onec.export.item_skipped`, `onec.export.accepted`, `onec.export.revision_created`, `onec.export.correction_created`, `onec.export.devices_excluded`, `onec.item.*`; analitika — `onec_export_approved` (soni, summa), `onec_export_duration_ms`.
- **Bog'liq US**: US-M19-06, US-M19-07, US-M19-08, US-M19-09, US-M19-10, US-M19-11, US-M19-12, US-M19-14, US-M19-15, US-M19-16, US-M19-18.

---

## BO-24 — Bank tushumi tasdig'i (yo'ldagi pul → bank)

- **Maqsad**: bank ko'chirmasi / ekvayer hisob-kitob hisoboti bo'yicha karta, UzQR, Click, Payme, Uzum tushumlari va inkassani yo'ldagi pul mablag'laridan (5710) bank hisobiga (5110) o'tkazish, komissiyani xarajatga (**9430**) yozish (BP-15, qaror #42, `13-provodka-qoidalari.md` §2.18a). Hujjat kodi `BT` (`BT-{filial}-{yil}-{ketma-ket}`).
- **Rollar/ruxsat**: Buxgalter, Egasi — `bank_settlements.manage` (ro'yxat, yaratish, o'tkazish, bekor qilish). Menejer, Kassir, Omborchi — yopiq. Faqat back-office (POS'da yo'q, sync voqeasi yo'q).
- **Route**: `/app/finance/bank-settlements` (ro'yxat), `/app/finance/bank-settlements/new`, `/app/finance/bank-settlements/:id` (forma/tafsilot).
- **Maket**:

```
┌──────────────────────────────────────────────────────────────────┐
│ Bank tushumi   Filial: [Chilonzor ▾]  Usul: [Hammasi ▾]  [Ko'chirmani yuklash] [+ Yangi] │
├──────────────────────────────────────────────────────────────────┤
│ Yo'ldagi pul (bankka o'tmagan):  Karta 950 000.00 · UzQR 120 000.00 │
│                                  Click 0.00 · Inkassa 2 000 000.00   │
├──────────────────────────────────────────────────────────────────┤
│ Sana        Raqam            Usul    Davr          Yalpi      Komissiya  Sof        Holat   │
│ 16.10.2026  BT-01-2026-000012 Karta  15.10–15.10   950 000.00  9 500.00  940 500.00 o'tkazilgan [1C da ✓] │
├──────────────────────────────────────────────────────────────────┤
│ Forma: Sana [16.10.2026]  Usul [Karta ▾]  Davr [15.10] – [15.10]  │
│        Yalpi [ 950 000.00 ]  Komissiya [ 9 500.00 ]  Sof: 940 500.00│
│        Bank hujjati № [ 123456 ]  Ko'chirma fayli [📎]  Izoh [...] │
│                         [ Saqlash ]  [ O'tkazish ]  [ Bekor qilish ] │
└──────────────────────────────────────────────────────────────────┘
```

- **Maydonlar**:

| Maydon | Label (uz) | Label (ru) | Tur/komponent | Majburiy | Validatsiya | Default | Max |
|---|---|---|---|---|---|---|---|
| `branch_id` | Filial | Филиал | `Select` | Ha | foydalanuvchi filiallari | joriy filial | — |
| `doc_date` | Bankka tushgan sana | Дата поступления в банк | `DatePicker` | Ha | yopilmagan davr; ≥ `settled_to` | bugun | — |
| `method` | To'lov usuli | Способ оплаты | `Select` (Karta / UzQR / Click / Payme / Uzum / Inkassa) | Ha | `card`\|`uzqr`\|`click`\|`payme`\|`uzum`\|`collection` | — | — |
| `settled_from` | Davr boshi | Период с | `DatePicker` | Ha | ≤ `settled_to` | kecha | — |
| `settled_to` | Davr oxiri | Период по | `DatePicker` | Ha | ≥ `settled_from` | kecha | — |
| `gross_amount` | Yalpi summa (yo'ldagi puldan yopiladi) | Валовая сумма | `MoneyInput` | Ha | > 0; `post`da filial × usul bo'yicha `doc_date` holatidagi yo'ldagi pul qoldig'idan oshmaydi | tanlangan usul/filial yo'ldagi pul qoldig'i (taklif) | — |
| `commission_amount` | Komissiya | Комиссия | `MoneyInput` | Ha | ≥ 0 va < `gross_amount` | `0.00` | — |
| `varianceAmount` | Farq (inkassa) | Расхождение (инкассация) | `MoneyInput` (±) | Yo'q | faqat `method=collection`; manfiy — kamomad, musbat — ortiqcha | `0.00` | — |
| `net_amount` | Bankka tushgan (sof) | Поступило в банк | Faqat ko'rsatish | — | `net = gross − commission + variance` (server generatsiya qiladi; formada `shared/lib/money` bilan ko'rsatiladi) | — | — |
| `bank_ref` | Bank hujjati raqami | Номер банковского документа | `Input` | Yo'q | — | — | 64 |
| `attachment_id` | Ko'chirma fayli | Файл выписки | Fayl yuklash (`POST /api/v1/attachments`, `kind='import'`) | Yo'q | PDF/XLSX/CSV/JPEG/PNG ≤ 10 MB | — | — |
| `comment` | Izoh | Комментарий | `Textarea` | Yo'q | — | — | 500 |
| `cancel_reason` | Bekor qilish sababi | Причина отмены | `Textarea` (dialogda) | Ha (bekor qilishda) | ≥ 10 belgi | — | 500 |

- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| + Yangi / Saqlash | `bank_settlements.manage` | Yo'q | `POST /api/v1/bank-settlements` (`draft`, `source='manual'`) |
| Ko'chirmani yuklash | `bank_settlements.manage` | Fayl tanlash (`.txt`, 1CClientBankExchange) | `POST /api/v1/bank-settlements/imports` — parser faqat kirim qatorlarini o'qiydi va `bank_settlements` **qoralamalarini** (`source='statement_import'`) taklif qiladi: `method` to'lovchi (ekvayer bank / Click / Payme / Uzum / MUNIS STIR) va to'lov maqsadi bo'yicha aniqlanadi; `gross_amount` ni server shu usul/filial bo'yicha yo'ldagi pul (5710) ochiq qoldig'idan FIFO bilan taklif qiladi (20 #55g), `commission_amount = gross − kirim`; natija dialogi — `drafts_created`, `duplicates`, `unmatched_lines`; qoralamani tahrirlash — `PATCH /api/v1/bank-settlements/{id}` (55h); qoralamalar odatdagi "O'tkazish" bilan tasdiqlanadi |
| O'tkazish | `bank_settlements.manage` | «Bank hisobiga {net_amount} o'tkaziladi, komissiya {commission_amount} xarajatga yoziladi» | `POST /api/v1/bank-settlements/{id}/post` → `posted`, raqam `BT-…`; `422 VALIDATION_ERROR` (summa yo'ldagi pul qoldig'idan katta / komissiya ≥ yalpi) — maydon xatosi `gross_amount`/`commission_amount`; `PERIOD_CLOSED` — sana yopilgan davrda |
| Bekor qilish | `bank_settlements.manage` | Sabab majburiy; «Storno yoziladi» | `POST /api/v1/bank-settlements/{id}/cancel` (`{reason}`) → `cancelled` |
| Ko'chirma faylini ochish | `bank_settlements.manage` | Yo'q | `attachment_id` bo'yicha yuklab olish |

- **Ma'lumot manbai**: `GET /api/v1/bank-settlements?branch_id=&method=&status=&doc_date__gte=&doc_date__lte=` (ro'yxat), `GET /api/v1/bank-settlements/{id}`, `POST /api/v1/bank-settlements`, `PATCH /api/v1/bank-settlements/{id}` (qoralama), `POST /api/v1/bank-settlements/{id}/post`, `POST /api/v1/bank-settlements/{id}/cancel` (`20-api-moliya-admin.md`); «Yo'ldagi pul» paneli — 5710 qoldig'i filial × `payment_method` bo'yicha: `GET /api/v1/bank-settlements/transit-balances?branch_id=&as_of=`; ko'chirma importi — `POST /api/v1/bank-settlements/imports`; `POST /api/v1/attachments`. 1C bog'langan bo'lsa — «1C da» belgisi (W-54; `bank_settlement` standart 1C ga yuborilmaydi, `send_bank_settlements`).
- **Holatlar**: `loading` · `empty` (hujjat yo'q — «Bank ko'chirmasi kelganda yangi hujjat yarating») · `error` (`VALIDATION_ERROR` — maydon ostida; `PERIOD_CLOSED`; import fayli formati noto'g'ri — «Fayl 1CClientBankExchange formatida emas») · `offline` (faqat ko'rish, yaratish/o'tkazish o'chiq) · `no-permission` (Menejer/Kassir/Omborchi — `NoPermissionState`) · `subscription-restricted` (kirilmaydi). Holat belgilari: `draft` — «Qoralama», `posted` — «O'tkazilgan», `cancelled` — «Bekor qilingan»; `source='statement_import'` — «Importdan» belgisi.
- **Klaviatura**: `Ctrl+K`; formada `Ctrl+S` — saqlash, `Ctrl+Enter` — o'tkazish dialogi.
- **Audit/analitika**: audit `entity='bank_settlements'` — yaratish, import, o'tkazish, bekor qilish (`after`: `method`, `gross_amount`, `commission_amount`, `bank_ref`; `15-xavfsizlik-va-audit.md`); analitika — `bank_settlement_posted`, `bank_statement_imported`.
- **Bog'liq US**: US-M11-04.

---

## UX-INSTALL — Qurilmani o'rnatish yo'riqnomasi (41 ta biznes ekranga kirmaydi, yordamchi route)

- **Route**: `/install` (ochiq, autentifikatsiyasiz — login'dan oldin ham kerak); BO-21 ⑥ bosqichi shu komponentni ichiga oladi (`<InstallGuide embedded />`), alohida nusxa yo'q.
- **Kim ochadi**: (a) BO-21 ⑥; (b) iOS Safari'da `/pos/*` yoki `/app/*` **o'rnatilmagan** holatda ochilsa (`navigator.standalone !== true` va `display-mode: standalone` emas) — POS yo'llari bloklanadi, `/install?platform=ios`ga yo'naltiriladi, back-office'da faqat yuqori banner; (c) BO-11 "Qurilmalar" tab → "Yangi qurilma qo'shish"; (d) POS-04 "bulut printer sozlanmagan" havolasi (`/install#cloud-print`).
- **Bo'limlar**: platforma avtomatik aniqlanadi (iOS / Android Chrome / Windows-Chrome), qo'lda almashtirish tugmalari; iOS: 3 qadam rasm bilan (Safari → Ulashish → "Home ekranga qo'shish") + «O'rnatilmasa ma'lumotlar o'chib ketishi mumkin» ogohlantirishi; Android/Chrome: `beforeinstallprompt` orqali "O'rnatish" tugmasi; **Bulut printer**: Star CloudPRNT (TSP143IV) / Epson Server Direct Print (TM-m30III) — printer URL'ini sozlash qadamlari, "Sinov cheki"; printer yo'q bo'lsa — elektron chek zahirasi (QR/Telegram). **Windows**: Do'kon agentini o'rnatish (LAN printer, fiskal modul, tarozi — qaror #60); yorliq printeri drayverida qog'oz o'lchamini sozlash.
- **Holatlar**: `loading` — yo'q; `offline` — matn keshdan (service worker precache); `no-permission`/`subscription-restricted` — tegishli emas.
- **Audit/analitika**: `install_guide_viewed`, `pwa_installed` (`appinstalled` hodisasi), `cloud_printer_test_printed`.
- **Sabab**: iOS'da o'rnatish **majburiy** (ITP IndexedDB'ni tozalaydi, `24-frontend-arxitekturasi.md` §6) va qurilma almashtirilganda login'dan keyin ham qayta kerak — wizard ichida qolib ketsa topib bo'lmaydi.

---

# C. Platforma admin paneli

## ADM-01 — Ichki admin panel

- **Maqsad**: platforma jamoasi tomonidan tenantlar, obunalar, to'lovlar, AI sarfini boshqarish; Egasi hisobi darajasida xavfsizlik amallari.
- **Rollar/ruxsat**: Platforma admin (`platform.admin`, alohida `aud=urn:erp:platform`, majburiy TOTP MFA — `14-autentifikatsiya-oauth2.md` §18.1).
- **Route**: `/platform/tenants` (alohida `admin-bff`, asosiy tenant domenidan izolyatsiyalangan)
- **Maket**:

```
┌──────────────────────────────────────────────────┐
│  Tenantlar          Obuna      To'lov    AI sarfi   │
│  "Mega Market"      active     15.11     1 240/5000 │
│  [Tafsilot] [Muddatni uzaytirish] [Xavfsizlik]       │
├──────────────────────────────────────────────────┤
│  Tafsilot → [Egasi hisobi] [Barcha sessiyalarni tugatish]│
└──────────────────────────────────────────────────┘
```

- **Joylashuv**: alohida platforma shell'i (tenant BO sidebar'i emas): sidebar guruhi **PLATFORMA** — Tenantlar (ADM-01; obuna, to'lov, AI sarfi shu ekranning ustun/filtrlari sifatida); topbar — sarlavha, qidiruv, bildirishnoma. KPI kartalari — Faol tenantlar (sinovdagilar, jami), MRR so'm (faqat `active`; yillik tarif oylikka keltirilgan: 950 400 / 12), Grace / restricted soni, AI sarfi (oy, limitning 90%+ dagi tenantlar soni). «Barcha tenantlar» jadvali — tenant (STIR), obuna holati chipi, davr (oylik/yillik), muddat (izoh bilan), kassalar (qo'shimcha kassalar izohi), oylik summa, AI sarfi (ming token, % limit), 1C agent holati (Bosqich 7), amallar (Tafsilot / Uzaytirish / Xavfsizlik); jadval ostida MRR jami va holatlar izohi (`trial` 30 kun · `grace` 24 soat · `restricted` — faqat to'lov sahifasi · `closed` — faqat platforma admini). O'ng panel — **«Tenant tafsiloti»** (Egasi ismi va niqoblangan telefoni, STIR, davr tugashi, grace tugashi, oxirgi to'lov), **«Muddatni qo'lda uzaytirish»** (`extendDays`, `extendReason`, yangi tugash sanasi hisobi, «To'lovlar tarixiga `manual_extension` · 0,00 so'm» izohi), **«Egasi hisobi xavfsizligi»** (faol sessiyalar — qurilma, vaqt, «Bekor qilish»; «Parolni tiklash kodi (Telegram, zaxira SMS)», «Barcha sessiyalarni tugatish», «Egasini bloklash»).
- **Maydonlar**: `search`/`statusFilter`/`addonFilter` ("qo'shimcha kassasi bor") — ro'yxat filtri — `Input`/`Select` — yo'q; `extendDays` — Muddatni uzaytirish (kun) — Продлить срок (дней) — `Input` number — ha (amalda) — >0; `extendReason` — Sabab — Причина — `Textarea` — ha (amalda) — max 500.
- **Amallar**:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Muddatni qo'lda uzaytirish | `platform.admin` | Sabab majburiy | `subscriptions.current_period_end` uzayadi; `billing_payments(kind='manual_extension', amount="0.00", actor_user_id, reason)` yoziladi — tenant BO-19 to'lovlar tarixida ko'radi (qaror #56 e) |
| Barcha sessiyalarni tugatish | `platform.admin` | "Tenantning barcha sessiyalari bekor qilinadi" | Insident javobi — audit |
| Egasi hisobini bloklash/blokdan chiqarish | `platform.admin` | "Egasi hisobini bloklaysizmi?" | Sessiyalar bekor (bloklashda) |
| Egasi parolini tiklash | `platform.admin` | Yo'q | (qaror #34) Tiklash kodi (`purpose=admin_reset`) — Telegram bot birinchi, SMS zaxira |
| Egasi sessiyalarini ko'rish/bekor qilish | `platform.admin` | Yo'q | `POST /platform/tenants/{id}/owner/sessions/{sid}/revoke` |

- **Ma'lumot manbai**: `GET /platform/tenants`, `GET /platform/tenants/{id}`, `POST /platform/tenants/{id}/extend-subscription`, `POST /platform/tenants/{id}/revoke-all-sessions`, `GET /platform/tenants/{id}/ai-usage`, `POST /platform/tenants/{id}/owner/block`, `/unblock`, `/reset-password`, `GET /platform/tenants/{id}/owner/sessions`, `POST /platform/tenants/{id}/owner/sessions/{sid}/revoke`.
- **Holatlar**: `loading` · `empty` (tenant yo'q) · `error` (TOTP noto'g'ri — login rad) · `offline` — ekran online talab qiladi · `no-permission` — `aud=urn:erp:api` token bilan 403 (tenant foydalanuvchisi kira olmaydi) · `subscription-restricted` — tegishli emas (bu ekran obunadan mustaqil).
- **Klaviatura**: `Ctrl+K`.
- **Audit/analitika**: `platform_admin_access`, `subscription_extended`, `owner_blocked`, `owner_password_reset`.
- **Bog'liq US**: US-M13-08, US-M17-04.

---

## Yakuniy eslatma — qamrov

Barcha 41 ekran (POS-01…16 = 16, BO-01…24 = 24, ADM-01 = 1) `06-ekranlar-umumiy.md`dagi ro'yxatga mos yozilgan; BO-22, BO-23 — M19, MVP'dan keyin (Bosqich 7), qolgan 39 tasi — MVP — har biri Maqsad, Rollar/ruxsat, Route, Maket, Maydonlar jadvali, Amallar, Ma'lumot manbai, Holatlar, Klaviatura, Audit va Bog'liq US bilan to'liq. Ruxsat kodlari (`permission_code`) — `15-xavfsizlik-va-audit.md` ruxsat katalogiga, API yo'llari — `17-api-umumiy.md`–`20-api-moliya-admin.md` katalogiga mos.

## Manbalar

- `spec/kod-uchun/06-ekranlar-umumiy.md` — 41 ekran ro'yxati, wireframelar, navigatsiya
- `spec/kod-uchun/21-integratsiyalar.md` — OFD/fiskal, e-faktura, E-TTN, markirovka, to'lovlar; `34-1c-agent.md` — Do'kon agenti (qaror #60)
- `research_notes/ochiq-savollar/` — P1–P7, D-qarorlar, qo'llash yo'riqnomasi (qarorlar #43–#65 asosi)
- `spec/kod-uchun/33-1c-integratsiya.md` — BO-22, BO-23 (§13), W-01…W-55 (§10), ruxsatlar (§11)
- `spec/kod-uchun/13-provodka-qoidalari.md` §2.18a — BO-24
- `spec/kod-uchun/03-modullar-talablari.md` — US-Mxx-nn
- `spec/kod-uchun/04-biznes-jarayonlar.md` — BP-nn
- `spec/kod-uchun/08-dizayn-tizimi.md` — tokenlar, komponentlar
- `spec/kod-uchun/24-frontend-arxitekturasi.md`, `16-offline-sync.md`, `14-autentifikatsiya-oauth2.md`
- `spec/kod-uchun/05-mvp-chegarasi.md` — yagona tarif
