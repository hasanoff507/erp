# Dizayn tizimi (brand-neutral, shadcn/ui asosida)

**Maqsad:** Brand-neutral dizayn tizimi — token, komponent, layout, formatlash va chop etish qoidalari, shadcn/ui asosida.
**Kim uchun:** Frontend dasturchilar, UX dizaynerlar.
**Bog'liq fayllar:** `06-ekranlar-umumiy.md`, `07-ekran-tafsilotlari.md`, `24-frontend-arxitekturasi.md`, `16-offline-sync.md`, `14-autentifikatsiya-oauth2.md`, `33-1c-integratsiya.md` (§7 holatlar, §12 xato kodlari, §13 ekranlar), `01-qarorlar.md`.
**Holat:** joriy, 2026-10-16.

Bu hujjat brendsiz (neutral) boshlang'ich dizayn tizimi — mijoz logotipi/rang palettasi keyin ustiga qo'yiladi. Barcha token `shadcn/ui` (Radix + Tailwind) ustida ishlaydi, `apps/shell` va `packages/shared/ui`da yashaydi.

---

## 0. Asosiy qarorlar (qisqa)

1. **Pul qoidasi** (qaror #26): saqlash/API darajasida pul har doim **kasr-satr (decimal string)**, masalan `"12000.00"` (`NUMERIC(18,2)`, tiyingacha); narx/tannarx satrlari 4 xonali kasr (`"8333.3333"`), miqdor satrlari 3 xonali kasr (`"1.250"`) — pul uchun JSON `number` turi **taqiqlanadi**. Frontendda pul hisob-kitobi **faqat ikki holatda** ruxsat etiladi: offlayn POS chek jami va submitdan oldingi forma jami — `decimal.js`/`big.js` bilan, satr-satr amal (`Number`/`parseFloat` pul uchun taqiqlanadi, lint qoidasi). Dumalaklashtirish backend bilan **aynan bir xil** bo'lishi shart, yagona funksiya `shared/lib/money`da: `line_total = ROUND_HALF_UP(qty × unit_price − chegirma, 0)` (chek qatori butun so'mgacha, chunki narxlar butun so'm va naqdda tiyin yo'q), QQS summasi (soliq ichida) `= ROUND_HALF_UP(line_total × r/(100+r), 2)` (tiyingacha) — bu `SalePostingService` mantig'iga aynan mos, ikki tomonda umumiy test vektorlari (`shared/money-vectors.json`) bilan tasdiqlanadi (qonunda yaxlitlash qoidasi yo'q — muhandislik qarori, buxgalter tanishadi; eng kichik tanga 50 so'm). Ko'rsatish: `formatMoney(value: string)` **faqat ko'rsatish uchun** — butun so'mgacha ROUND_HALF_UP qiladi, bu qiymat hech qachon API'ga qaytarilmaydi va keyingi hisoblashda ishlatilmaydi; jadvaldagi jami har doim backend qaytargan jami, allaqachon dumalaklashtirilgan qatorlar yig'indisi emas. Istisno: fiskal chek va buxgalteriya/QQS hisobotlari 2 xonali kasr bilan ko'rsatiladi — `formatMoney(value, { precision: 2 })`; fiskal adapter OFD/hamkorga summani **butun son tiyinda** uzatadi (faqat adapter chegarasida) — hamkor protokoli bilan tasdiqlanadi (26 #109 (OQ-012)).
2. **Sana/vaqt**: `DD.MM.YYYY`, vaqt `HH:mm` (24 soat), `dayjs` + uz-latn lokal konfiguratsiyasi (tayyor `dayjs/locale/uz-latn` yo'q bo'lsa, `shared/lib/date` ichida qo'lda bir marta ro'yxatdan o'tkaziladi — bu "qo'lda formatlash" emas, lokal sozlama).
3. **Til**: o'zbek (lotin) — standart va majburiy birinchi til; rus — ikkinchi, almashtiriladigan. Fiskal chek har doim ikki tilli — o'zbek qatori birinchi, rus (`products.name_ru`) ikkinchi (qaror #29, chek shabloni); UI tili almashtirgichi faqat interfeys matnini almashtiradi, chekka ta'sir qilmaydi.
4. **Zichlik (density)**: ikki rejim — `touch` (POS, ≥48×48px nishon) va `compact` (back-office, ≥36×36px). Bitta komponent kutubxonasi, zichlik Tailwind context/`data-density` atributi orqali.
5. **Platformalar**: POS — to'liq ekran, klaviatura/skaner-birinchi; Back-office — sidebar+header, ish stoli birinchi, mobil brauzerda responsive; iOS/iPhone/iPad — o'rnatilgan PWA (Home Screen), chop etish faqat bulut-printer, printer bo'lmasa elektron chek zahirasi (`24-frontend-arxitekturasi.md` §6).

---

## 1. Rang tokenlari (CSS variables, shadcn formatida — HSL, `--foo: H S% L%`)

shadcn standart nomlashiga qo'shimcha semantik tokenlar qo'shiladi: `success`, `warning`, `offline`, `fiscal-pending`. Barcha ranglar **brand-neutral** (ko'k/kulrang asosida) — mijoz keyin `primary`ni almashtiradi.

### `apps/shell/src/app/ui/theme.css`

```css
:root {
  /* shadcn asosiy */
  --background: 0 0% 100%;
  --foreground: 222 20% 14%;
  --card: 0 0% 100%;
  --card-foreground: 222 20% 14%;
  --popover: 0 0% 100%;
  --popover-foreground: 222 20% 14%;
  --primary: 221 70% 45%;            /* neutral ko'k — brend almashtiradi */
  --primary-foreground: 0 0% 100%;
  --secondary: 220 14% 96%;
  --secondary-foreground: 222 20% 14%;
  --muted: 220 14% 96%;
  --muted-foreground: 220 9% 46%;
  --accent: 220 14% 96%;
  --accent-foreground: 222 20% 14%;
  --destructive: 0 72% 51%;
  --destructive-foreground: 0 0% 100%;
  --border: 220 13% 91%;
  --input: 220 13% 91%;
  --ring: 221 70% 45%;
  --radius: 0.5rem;

  /* Loyiha semantik qo'shimchalari */
  --success: 142 71% 35%;
  --success-foreground: 0 0% 100%;
  --warning: 38 92% 45%;
  --warning-foreground: 0 0% 10%;
  --offline: 38 92% 50%;              /* 🟡 offlayn */
  --offline-critical: 0 72% 51%;      /* 🔴 40 soatdan, ⛔ 48 soat blok */
  --offline-foreground: 0 0% 10%;
  --fiscal-pending: 221 70% 55%;      /* "OFD'ga yuborish kutilmoqda" belgisi */
  --fiscal-pending-foreground: 0 0% 100%;
  --awaiting-approval: 270 60% 55%;   /* 🟪 1C preview — tasdiq kutmoqda (BO-23) */
  --awaiting-approval-foreground: 0 0% 100%;
}

/* Ikki alohida blok: (1) qo'lda tanlangan dark — OS rejimidan qat'i nazar doim ishlaydi;
   (2) OS dark preferensi — faqat foydalanuvchi aniq "light"ni tanlamagan bo'lsa. */
:root[data-theme="dark"] {
  --background: 222 20% 10%;
  --foreground: 220 14% 96%;
  --card: 222 18% 13%;
  --card-foreground: 220 14% 96%;
  --popover: 222 18% 13%;
  --popover-foreground: 220 14% 96%;
  --primary: 221 70% 60%;
  --primary-foreground: 222 20% 10%;
  --secondary: 222 16% 18%;
  --secondary-foreground: 220 14% 96%;
  --muted: 222 16% 18%;
  --muted-foreground: 220 9% 65%;
  --accent: 222 16% 18%;
  --accent-foreground: 220 14% 96%;
  --destructive: 0 62% 55%;
  --destructive-foreground: 0 0% 100%;
  --border: 222 14% 22%;
  --input: 222 14% 22%;
  --ring: 221 70% 60%;
  --success: 142 60% 45%;
  --success-foreground: 0 0% 8%;
  --warning: 38 85% 55%;
  --warning-foreground: 0 0% 8%;
  --offline: 38 85% 58%;
  --offline-critical: 0 62% 55%;
  --offline-foreground: 0 0% 8%;
  --fiscal-pending: 221 70% 65%;
  --fiscal-pending-foreground: 0 0% 8%;
  --awaiting-approval: 270 55% 68%;
  --awaiting-approval-foreground: 0 0% 8%;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --background: 222 20% 10%;
    --foreground: 220 14% 96%;
    --card: 222 18% 13%;
    --card-foreground: 220 14% 96%;
    --popover: 222 18% 13%;
    --popover-foreground: 220 14% 96%;
    --primary: 221 70% 60%;
    --primary-foreground: 222 20% 10%;
    --secondary: 222 16% 18%;
    --secondary-foreground: 220 14% 96%;
    --muted: 222 16% 18%;
    --muted-foreground: 220 9% 65%;
    --accent: 222 16% 18%;
    --accent-foreground: 220 14% 96%;
    --destructive: 0 62% 55%;
    --destructive-foreground: 0 0% 100%;
    --border: 222 14% 22%;
    --input: 222 14% 22%;
    --ring: 221 70% 60%;
    --success: 142 60% 45%;
    --success-foreground: 0 0% 8%;
    --warning: 38 85% 55%;
    --warning-foreground: 0 0% 8%;
    --offline: 38 85% 58%;
    --offline-critical: 0 62% 55%;
    --offline-foreground: 0 0% 8%;
    --fiscal-pending: 221 70% 65%;
    --fiscal-pending-foreground: 0 0% 8%;
    --awaiting-approval: 270 55% 68%;
    --awaiting-approval-foreground: 0 0% 8%;
  }
}
```

**POS kiosk rejimi** (doim yorug'/kam yorug'lik do'kon muhiti, `06-ekranlar-umumiy.md` §1.5): POS qurilmasi odatda `data-theme="light"` bilan qulflanadi (yuqori kontrast, chalg'ituvchi dark-mode yo'q) — foydalanuvchi o'zgartira olmaydi; back-office tizim/foydalanuvchi tanloviga ergashadi.

### Semantik rang qo'llanishi

| Token | Qayerda ishlatiladi |
|---|---|
| `primary` | Asosiy tugmalar (TO'LOV, SAQLASH), faol tab, link |
| `success` | Muvaffaqiyatli chek, "mos keladi" (BO-10), tasdiqlangan holat belgisi |
| `warning` | Kam qoldiq, limitga yaqinlashish (84%), kutilayotgan tasdiqlash |
| `destructive` | Xato, bekor qilish, bloklash, farq topildi (BO-10) |
| `offline` / `offline-critical` | OfflineBadge — 🟡 24 soatdan sinxronlanmagan N chek / 🔴 40 soatdan / ⛔ 48 soat — kassa bloklangan (`offline-critical` + `Lock` ikon), qaror #43 |
| `fiscal-pending` | Offline chiqarilgan chek (shu jumladan markirovkali qator) — OFD'ga yuborish kutilmoqda belgisi |
| `awaiting-approval` | 1C kun partiyasi `preview` — tasdiq kutmoqda (BO-23 kalendari 🟪, §7.3) |

---

## 2. Tipografiya

Shrift: tizim shrifti (`-apple-system, Segoe UI, Roboto, sans-serif`) — qo'shimcha veb-shrift yuklanmaydi (tezlik, offline-first). U+02BB (ʻ — `oʻ`, `gʻ`) glifi va kirill — Bosqich 0 skrinshot testi (Windows/Android/iOS); yetishmasa self-hosted Noto Sans (offline keshda) ulanadi (qaror #57).

| Token | `font-size` / `line-height` | Back-office qo'llanishi | POS qo'llanishi |
|---|---|---|---|
| `text-display` | 40px / 48px, 700 | — | Chekdagi jami summa, PIN-pad sarlavha |
| `text-h1` | 28px / 36px, 700 | Sahifa sarlavhasi | Smena sarlavhasi |
| `text-h2` | 22px / 30px, 600 | Bo'lim sarlavhasi | Mahsulot nomi (qatorda) |
| `text-h3` | 18px / 26px, 600 | Karta sarlavhasi | Tugma yozuvi |
| `text-body` | 15px / 22px, 400 | Asosiy matn, jadval katakchasi | Yordamchi matn |
| `text-money` | 20px / 28px, 700, tabular-nums | Jadvaldagi summa ustuni | Chekdagi qator narxi — **kamida body'dan 1.5x katta** (`06-ekranlar-umumiy.md` §1.5) |
| `text-money-lg` | 32px / 40px, 700, tabular-nums | Dashboard KPI | To'lov ekranidagi "To'lanadigan" summa |
| `text-small` | 13px / 18px, 400 | Yordamchi izoh, vaqt belgisi | Status panel matni |
| `text-caption` | 11px / 16px, 500, uppercase | Badge, label | Offline hisoblagich |

Qoida: pul va miqdor har doim `tabular-nums` (raqamlar tekis joylashsin, jadval tez o'qilsin) va `font-variant-numeric: tabular-nums` Tailwind util (`tabular-nums` klassi).

---

## 3. Spacing, radius, elevation

- **Spacing** — Tailwind standart shkala (4px negizida: `1`=4px … `16`=64px), qo'shimcha token yo'q.
- **Radius** — `--radius: 0.5rem` (8px) shadcn standart; katta kartalar/dialoglar `rounded-lg` (`--radius`), tugmalar `rounded-md` (6px), POS katta tugmalar `rounded-xl` (12px, bosh barmoq uchun yumshoqroq nishon).
- **Elevation** (soya) — shadcn `shadow-sm/md/lg` to'g'ridan-to'g'ri; qo'shimcha `shadow-pos-sheet` (bottom sheet uchun, kuchliroq yuqori soya: `0 -8px 24px -4px rgb(0 0 0 / 0.12)`).
- **Z-index skeleti**: `z-dropdown:40`, `z-sticky-header:30`, `z-overlay:50`, `z-dialog:60`, `z-toast:70`, `z-pos-statusbar:80` (offline badge har doim eng tepada).

---

## 4. Ikon to'plami — lucide-react

Standart: `lucide-react`, 20px (compact) / 24px (touch) o'lcham, `stroke-width=2`.

| Vazifa | Ikon |
|---|---|
| Skanerlash | `ScanLine` |
| Qidirish | `Search` |
| Qo'shish | `Plus` |
| Chegirma | `Percent` |
| To'lov | `Wallet` / `CreditCard` (karta) / `Smartphone` (QR/Payme/Click) / `Banknote` (naqd) |
| Qaytarish | `Undo2` |
| Nasiya/qarz | `BookOpenText` |
| Smena | `Clock` / `LogIn` / `LogOut` |
| Offline/online | `WifiOff` / `Wifi` |
| Sinxronizatsiya | `RefreshCw` |
| Ombor | `Warehouse` |
| Ko'chirish | `ArrowLeftRight` |
| Inventarizatsiya | `ClipboardList` |
| Xarid | `Truck` |
| E-faktura | `FileSignature` |
| QQS/soliq | `Landmark` |
| Hisobotlar | `BarChart3` |
| AI chat | `Sparkles` |
| Sozlamalar | `Settings` |
| Foydalanuvchilar | `Users` |
| Filiallar | `Building2` |
| Xarajat | `Receipt` |
| Kassa pul harakati | `HandCoins` |
| Obuna/to'lov | `CreditCard` |
| Telegram | `Send` |
| Ogohlantirish | `TriangleAlert` |
| Muvaffaqiyat | `CircleCheck` |
| Xato | `CircleX` |
| Bloklash | `Lock` / `Unlock` |
| Chop etish | `Printer` |
| Yorliq | `Tag` |
| Eksport | `Download` |
| PIN/parol | `KeyRound` |
| Qurilma | `Smartphone` / `Monitor` |

---

## 5. Zichlik rejimlari (density)

| Jihat | `touch` (POS) | `compact` (back-office) |
|---|---|---|
| Min. teginish nishoni | **48×48px** (asosiy harakat tugmalari — 56×56px, 26 #13) | 36×36px |
| Tugma balandligi (`<Button>`) | `h-14` (56px) asosiy, `h-12` ikkinchi darajali | `h-9` (36px) standart, `h-8` kichik |
| Jadval qator balandligi | — (POS jadval kam) | 40px (DataTable standart) |
| Shrift bazasi | `text-body` (15px), summalar `text-money`/`text-money-lg` | `text-body` (15px), sarlavha `text-h2` |
| Input balandligi | `h-14` (raqamli klaviatura bilan) | `h-9` |
| Gap (tugmalar orasida) | `gap-3` (12px, tasodifiy bosilmasin) | `gap-2` (8px) |

Amalga oshirish: `<html data-density="touch">` POS shell'ida, `data-density="compact"` back-office shell'ida; Tailwind `data-[density=touch]:h-14` variant guruhi yoki CSS custom property orqali (`--tap-min: 48px`).

> **Eslatma (mobil back-office teginish nishoni)**: yuqoridagi jadvaldagi `compact` 36×36px qiymati **desktop** back-office uchun vakolatli standart (sichqoncha-birinchi, kursor aniq). 6.3-bo'limdagi mobil PWA (Egasi telefonida) — bu kursorsiz teginish ekrani, shuning uchun unga alohida **`compact-mobile/touch`** rejimi kerak: `@media (pointer: coarse)` yoki `<768px` breakpointda `data-density="touch"`ga o'tadi, lekin POS'ning 48px/56px emas, balki WCAG 2.5.5 bo'yicha **minimal 44×44px** teginish nishoniga mo'ljallanadi (desktop 36px kompakt qiymatidan katta, lekin POS'ning 48px'idan kichik — mobil veb-sahifa zichligi uchun amaliy minimum).

| Rejim | Min. teginish nishoni | Qo'llaniladi |
|---|---|---|
| `compact` (desktop) | 36×36px | Back-office, sichqoncha/klaviatura-birinchi ekran |
| `compact-mobile` / `touch` (mobil) | **44×44px** | Egasi mobil PWA (`@media (pointer: coarse)` yoki `<768px`) |
| `touch` (POS) | 48×48px (asosiy — 56×56px) | POS qurilmasi |

---

## 6. Layout gridlari

### 6.1 POS — to'liq ekran (full-screen app)

```
┌─────────────────────────────────────────┐
│ Status panel (offline badge, soat, UZ/RU)│ ← sticky, 48px, z-pos-statusbar
├─────────────────────────────────────────┤
│                                           │
│         Asosiy kontent (60%)             │ ← chek ro'yxati / forma
│                                           │
├─────────────────────────────────────────┤
│   Pastki harakat zonasi (40%)            │ ← katta tugmalar, raqamli klaviatura
│   [ TUGMA 1 ] [ TUGMA 2 ] [ TUGMA 3 ▶ ]  │
└─────────────────────────────────────────┘
```
Bir ustunli, skroll yo'q (yoki faqat kontent ro'yxati ichida); sichqonchasiz, klaviatura/skaner-birinchi; bottom-sheet dialoglar (`<Sheet side="bottom">`), modal o'rniga.

### 6.2 Back-office — sidebar + header

```
┌───────────┬─────────────────────────────┐
│           │ Header: sahifa nomi, filial │
│  Sidebar  │ tanlash, UZ/RU, foydalanuvchi│
│  (240px,  ├─────────────────────────────┤
│  modulga  │                             │
│  qarab    │   Kontent (max-w-7xl,        │
│  ikonka+  │   12-ustunli grid)           │
│  nom)     │                             │
│           │                             │
└───────────┴─────────────────────────────┘
```
`≥1024px`: sidebar doim ochiq; `768–1023px`: sidebar collapse (ikonka-only, `w-16`); `<768px`: sidebar `<Sheet>` (burger menyu), kontent bir ustun.

### 6.3 Mobil PWA (Egasi tezkor ko'rish)

Bitta ustun, pastki tab-bar (`Bosh sahifa / Hisobotlar / Qarzlar / AI / Sozlamalar`), header'da filial tanlovi dropdown. Og'ir jadvallar mobil uchun kartaga aylanadi (`DataTable` → `CardList` responsive variant).

---

## 7. Komponent inventari

### 7.1 shadcn/ui (to'g'ridan-to'g'ri, o'zgarishsiz yoki minimal tema bilan)

`Button`, `Input`, `Textarea`, `Select`, `Combobox` (cmdk asosida), `Checkbox`, `RadioGroup`, `Switch`, `Dialog`, `Sheet`, `AlertDialog`, `Popover`, `Tooltip`, `Tabs`, `Card`, `Badge`, `Avatar`, `Table` (TanStack bilan birga), `Calendar` (react-day-picker ^9.14), `Form` (react-hook-form + zod wrapper), `Toast`/`Sonner`, `Command` (cmdk), `DropdownMenu`, `NavigationMenu`/`Sidebar` (shadcn `sidebar` bloki), `Skeleton`, `Progress`, `Separator`, `ScrollArea`, `HoverCard`.

### 7.2 Maxsus (loyiha) komponentlar — `packages/shared/ui/`

| Komponent | Vazifa | Asosiy proplar |
|---|---|---|
| **`MoneyInput`** | Pul kiritish — ekranda butun son, minglik ajratgich avtomatik, so'm belgisi suffiks; chiqishda kasr-satr (`"12000.00"`) | `value: string`, `onChange`, `max?`, `allowNegative?` |
| **`PriceInput`** | Tannarx/xarid narxi kiritish — 4 xonagacha kasr (xarid qatori narxi, ochilish qoldig'i tannarxi kabi joylarda) | `value: string`, `onChange`, `max?`, `precision?: 4` |
| **`QtyInput`** | Miqdor kiritish — o'lchov birligiga qarab butun/kasr (dona=butun, kg=**3 xonali kasr**), +/− stepper tugmalari | `value`, `unit: "dona"\|"kg"\|"litr"...`, `step`, `onChange` |
| **`BarcodeField`** (`useBarcodeWedge` hook asosida) | Skaner-fokus maydoni — belgilar orasi <30ms + Enter suffiksini HID skaner sifatida taniydi, qo'lda yozishdan ajratadi | `onScan(code: string)`, `autoFocus`, `placeholder` |
| **`PinPad`** | 4–6 xonali PIN kiritish, raqamli grid, mahalliy/server tasdiqlash | `length`, `onComplete(pin)`, `loading`, `error` |
| **`OfflineBadge`** | Status panelidagi 🟢/🟡/🔴/⛔ ko'rsatkich + sinxronlanmagan son + 48 soat hisoblagichi (24 soat — `offline`, 40 soat — `offline-critical`, 48 soat — `blocked`; qaror #43, `06-ekranlar-umumiy.md` §1.3) | `status: "online"\|"offline"\|"offline-critical"\|"blocked"`, `pendingCount`, `hoursLeft?` |
| **`OfflineDeadlineModal`** | 46 soatdan har yangi chek oldidan ko'rinadigan modal «2 soatdan keyin kassa bloklanadi — internetga ulaning», faqat «Tushundim» bilan yopiladi, sotuvni to'xtatmaydi; ⛔ blok holatida — «Kassa bloklangan» to'liq panel, faqat «Qayta yuborish» (`FISCAL_OFFLINE_48H_BLOCKED`) | `hoursLeft`, `blocked`, `onResend` |
| **`CardDetailsFields`** | POS-03 «Karta» to'lovi maydonlari (qaror #64): karta turi `Select` (shaxsiy / korporativ / ijtimoiy / noma'lum; standart qiymat yo'q — kassir har to'lovda tanlaydi, `method='card'` da majburiy), karta niqobi (`NNNN****NNNN` maska) va RRN — ijtimoiy kartada majburiy | `cardType`, `cardMask`, `rrn`, `onChange` |
| **`PrinterSetup`** | POS-16 printer sozlash: transport tanlovi (Web Serial / WebUSB / Web Bluetooth BLE / Do'kon agenti / tizim / bulut), qog'oz kengligi, kod sahifasi, «Test chek» | `transport`, `width: 58\|80`, `onTest` |
| **`SyncStatus`** | POS-12 ro'yxati — har bir outbox voqeasi holati (kutmoqda/xato/muvaffaqiyatli) | `events: SyncEvent[]`, `onRetry` |
| **`ApprovalDialog`** | Limitdan oshgan amal uchun Menejer/Egasi PIN so'rovi (bottom sheet, POS) yoki modal (BO-16) | `reason`, `amount`, `onApprove(pin)`, `onReject(comment)` |
| **`DataTable`** preset'lari | TanStack Table ustida: `DataTable.Compact` (back-office, saralash/filtr/sahifalash/eksport), `DataTable.Mobile` (karta ko'rinishi) | `columns`, `data`, `isLoading`, `emptyState`, `onRowClick` |
| **`EmptyState`** | Bo'sh holat — ikon + sarlavha + qisqa izoh + ixtiyoriy CTA | `icon`, `title`, `description`, `action?` |
| **`ErrorState`** | Xato holati — ikon + xabar (i18n kaliti, raw JSON hech qachon) + "Qayta urinish" | `message`, `retryable`, `onRetry` |
| **`NoPermissionState`** | `403 PERMISSION_DENIED` — qulf ikon + "Sizda bu bo'limga kirish huquqi yo'q" | — |
| **`SubscriptionRestrictedState`** | `403 SUBSCRIPTION_RESTRICTED` — to'liq ekran banner, to'lov havolasi, eksport havolasi (D2) | `payUrl`, `amountDue` |
| **`MarkingBadge`** | Markirovka holati belgisi: `pending_verification` (fiscal-pending — chek bilan OFD'ga yuborish kutilmoqda), `verified`, `verify_failed` (`MARKING_PRECHECK=warn` — `warning`, `block` — `destructive`), `duplicate` (`destructive` — kod allaqachon sotilgan) | `status` |
| **`MoneyDisplay`** | Faqat ko'rsatish uchun (formatlangan, rangli — musbat/manfiy) | `value: string`, `currency="UZS"`, `tone?` |
| **`ReceiptPreview`** | 58/80mm chek oldindan ko'rish (ekranda, chop etishdan oldin); (qaror #29) har bir qatorni ikki tilda ("{name} / {name_ru}") render qiladi | `receipt`, `width: 58\|80` |
| **`DocStatusBadge`** | Hujjat holati belgisi (`draft` — muted «Qoralama», `posted` — success «O'tkazilgan», `cancelled` — destructive «Bekor qilingan»); BO-24 da `source='statement_import'` uchun qo'shimcha muted «Importdan» belgisi | `status`, `source?` |
| **`OnecRefBadge`** (Bosqich 7) | Hujjat ekranidagi «1C da» belgisi — W-54 natijasi: `1C: ОРП № 0000-000123 ✓`; bosilsa BO-23 partiyasi; `onec.view` yo'q yoki 1C bog'lanmagan — `null` render (§7.3) | `docType`, `docId` |
| **`OnecStatusChip`** (Bosqich 7) | Agent/integratsiya holati chipi (BO-23 sarlavhasi, BO-14 «1C» qatori, sidebar) — W-55 `state` (§7.3) | `state: "green"\|"yellow"\|"red"\|"none"`, `agentName?`, `version?` |
| **`OnecBatchStatusBadge`** / **`OnecItemStatusBadge`** (Bosqich 7) | Kun partiyasi va hujjat (item) holati belgilari, BO-23 kalendar katakchasi (§7.3) | `status`, `blocked?`, `accepted?` |

### 7.3 1C eksporti holat belgilari (Bosqich 7, BO-22/BO-23)

Holat nomlari — `33-1c-integratsiya.md` §7 (o'zgarishsiz); matn kalitlari `onec:status.batch.<status>`, `onec:status.item.<status>`.

**Kun partiyasi (`onec_export_batches.status`) → `OnecBatchStatusBadge` va kalendar katakchasi:**

| Holat | Token | Kalendar | uz | ru |
|---|---|---|---|---|
| (partiya yo'q, ERP hujjati bor) `not_prepared` | `muted` | ⬜ | Tayyorlanmagan | Не подготовлен |
| `draft` | `muted` | ⬜ | Qurilmoqda | Формируется |
| `preview` + `blocking_issues` bo'sh emas | `destructive` | 🟥 | Bloklangan | Заблокирован |
| `preview` | `awaiting-approval` | 🟪 | Tasdiq kutmoqda | Ожидает подтверждения |
| `approved`, `queued` | `primary` | 🟦 | Navbatda | В очереди |
| `sending` | `primary` | 🟦 | Yozilmoqda | Запись в 1С |
| `verifying` | `primary` | 🟦 | Tekshirilmoqda | Сверка |
| `done` | `success` | 🟩 | 1C da | В 1С |
| `partial` | `warning` | 🟨 | Qisman (xato bor) | Частично (есть ошибки) |
| `mismatch` | `warning` | 🟨 | Farq bor | Расхождение |
| `failed` | `warning` (belgi ichida `destructive` ikon) | 🟨 | Yuborilmadi | Не отправлено |
| `cancelled` | `muted` | ⬜ | Bekor qilingan | Отменён |
| `partial`/`mismatch` + `accepted_at` | `success` (contur) | 🟩 | Qabul qilingan | Принят |
| `needs_resync` (yakuniy holatda) | `warning` (qo'shimcha nuqta) | — | Kech ma'lumot — revision kerak | Поздние данные — нужна ревизия |
| (ERP hujjati yo'q) | — | bo'sh | — | — |

**Hujjat (`onec_export_items.status`) → `OnecItemStatusBadge`:** `pending`/`queued` — `muted` «Kutilmoqda» / «Ожидает»; `sending` — `primary` + spinner «Yozilmoqda» / «Записывается»; `retry_wait`/`unknown` — `warning` «Qayta urinish n/8» / «Повтор n/8»; `written` — `success` «✓ № {onec_number}»; `verified` — `success` «✓ Tekshirildi» / «✓ Сверено»; `mismatch` — `warning` «Farq» / «Расхождение»; `failed` — `destructive` «Xato» / «Ошибка» (+ `fix_hints.onec.*` maslahati); `skipped` — `muted` «O'tkazib yuborildi» / «Пропущен» (`unchanged` — «O'zgarishsiz» / «Без изменений»). Preview qatoridagi `action`: `create` — «yangi», `update` — «yangilanadi», `unchanged` — «o'zgarishsiz», `unpost_mark_delete` — `destructive` «1C da o'chirishga belgilanadi».

**`OnecStatusChip` (W-55 `state`):** `green` — `success` 🟢 «1C: ishlayapti»; `yellow` — `warning` 🟡 «1C: navbatda / ogohlantirish»; `red` — `destructive` 🔴 «1C: xato»; `none` — `muted` ⚪ «1C sozlanmagan». Agent oflayn bo'lsa chipda «{pc_name} aloqada emas {N} soat».

**`OnecRefBadge` (W-54 `state`):** `active` + `posted` — `success` «1C: {onec_type_short} № {onec_number} ✓»; hali yuborilmagan — `muted` «1C ga yuborilmagan»; `changed_in_1c` — `warning` «1C da o'zgartirilgan»; `unposted` — `warning` «1C da o'tkazilmagan»; `marked_deleted` — `warning` «1C da o'chirishga belgilangan»; `missing_in_1c` — `destructive` «1C da topilmadi». Ikon — lucide `link-2` (badge), `alert-triangle` (ogohlantirish).

Onboarding tekshiruvlari (BO-22 «Tekshiruv»): `pass` — `success` ✓, `warn` — `warning` ⚠, `fail` — `destructive` ✗, `skipped` — `muted` «—»; qamrovdan tashqari (`ONEC_EDITION_NO_COM`, `ONEC_CLOUD_BASE_UNSUPPORTED`, `ONEC_SALE_PRICE_ACCOUNTING_UNSUPPORTED`) — butun karta `destructive` fonida.

---

## 8. Son/pul/sana formatlash qoidalari

- **Pul** (qaror #26): saqlash/API — har doim kasr-satr (`"12000.00"`, `NUMERIC(18,2)`, tiyingacha; narx/tannarx 4 xonali, miqdor 3 xonali), JSON `number` pul uchun taqiqlanadi. Frontend hisob-kitobi faqat offlayn POS chek jami va submitdan oldingi forma jamida ruxsat etiladi (`decimal.js`/`big.js`, satr-satr; `Number`/`parseFloat` taqiqlanadi). Dumalaklashtirish `shared/lib/money`dagi yagona funksiyada, backend (`SalePostingService`) bilan aynan bir xil: `line_total = ROUND_HALF_UP(qty × unit_price − chegirma, 0)`, QQS `= ROUND_HALF_UP(line_total × r/(100+r), 2)` — `shared/money-vectors.json` test vektorlari bilan tasdiqlanadi (§0 band 1). Ko'rsatish: `formatMoney(value: string): string` → `Intl.NumberFormat("uz-UZ", { maximumFractionDigits: 0 })` + `" so'm"` suffiks qo'lda qo'shiladi (chunki `currency: "UZS"` formatlagich standart "сум"/"UZS" belgisini beradi, bizga "so'm" so'zi lotin orfografiyasida kerak) — bu natija **faqat ko'rsatish uchun**, hech qachon API'ga qaytarilmaydi. Natija: `1 240 000 so'm`. Manfiy: `−1 240 000 so'm` (minus belgisi, qavs ishlatilmaydi). Istisno: fiskal chek/QQS hisobotlari — `formatMoney(value, { precision: 2 })` (OFD spetsifikatsiyasi bilan yakunlanadi).
- **Kasr kerak bo'lgan joy** (foiz, kurs, AVECO o'rtacha narx ichki hisob-kitobda): vergul kasr ajratgich — `12,5%`. Backend API har doim `.` (nuqta) bilan kasr-**satr** qaytaradi (masalan `"12.50"`, JSON `number` emas — §0 band 1), frontend ko'rsatishda `,`ga aylantiradi — bu faqat ko'rsatish-formatlash qadami, hisoblash emas.
- **Miqdor** (qaror #26): o'lchov birligiga ko'ra — `dona`/`quti` butun son, `kg`/`litr` **3 xonali kasr** (vergul bilan: `1,250 kg`; API maydoni `NUMERIC(18,3)`, tarozi-shtrixkod aniqligiga — grammgacha — mos).
- **Sana**: `dayjs(value).format("DD.MM.YYYY")`; vaqt bilan birga `DD.MM.YYYY HH:mm`. Nisbiy vaqt (masalan "5 daqiqa oldin") — `dayjs().fromNow()` faqat "oxirgi yangilanish" kabi meta-matnlarda, hech qachon hujjat sanasi o'rnida.
- **Telefon**: `+998 XX XXX XX XX` maska (`react-hook-form` + input mask, qo'lda regex emas — `shared/lib/phone`).
- Har qanday formatlash **faqat** `shared/lib/format` orqali (`formatMoney`, `formatQty`, `formatDate`, `formatPhone`) — komponent ichida qo'lda `toLocaleString`/shablon satr taqiqlanadi (namunadagi kamchilikni takrorlamaslik, `24-frontend-arxitekturasi.md` Asosiy xulosa #7).

---

## 9. POS klaviatura qisqa yo'llari (F-tugmalar)

Veb-kassa klaviatura/skaner-birinchi (`24-frontend-arxitekturasi.md` §5). Standart xaritasi:

| Tugma | Amal | Ekran |
|---|---|---|
| `F1` | Skaner/qidiruv maydoniga fokus | POS-02 |
| `F2` | Chegirma kiritish | POS-02 |
| `F3` | Mijoz tanlash/qo'shish | POS-02 |
| `F4` | To'lovga o'tish | POS-02 |
| `F5` | Nasiyaga sotish | POS-02 |
| `F6` | Qaytarish ekrani | Global (POS shell) |
| `F7` | Qarz daftari | Global |
| `F8` | Smenani yopish | Global |
| `F9` | Mahsulot/narx qidirish (POS-11) | Global |
| `F12` | Sinxronizatsiya holati (POS-12) | Global |
| `Enter` | Skanerdan kelgan kodni qabul qilish / tanlangan qatorni tasdiqlash | Hamma joy |
| `Esc` | Joriy dialog/sheet'ni yopish, amalni bekor qilish | Hamma joy |
| `+` / `-` | Tanlangan qator miqdorini oshirish/kamaytirish | POS-02 |
| `Delete` | Tanlangan qatorni o'chirish | POS-02 |
| `Ctrl+P` | Chekni qayta chop etish | POS-04 |

Back-office'da F-tugmalar band qilinmaydi (brauzer standart xatti-harakati saqlanadi); o'rniga `cmdk` buyruq paneli — `Ctrl+K` / `Cmd+K` tezkor qidiruv/navigatsiya uchun.

---

## 10. Accessibility (asosiy)

1. **Kontrast**: matn/fon nisbati kamida **4.5:1** (WCAG AA), katta matn (≥24px) kamida 3:1. Token darajasida tasdiqlangan (yuqoridagi HSL qiymatlar shunga mos tanlangan).
2. **Teginish nishoni**: POS ≥48×48px, back-office ≥36×36px (5-bo'lim).
3. **Klaviatura navigatsiyasi**: har bir interaktiv element `Tab` bilan yetadigan, `focus-visible` halqasi (`ring-2 ring-ring`) ko'rinadigan bo'lishi shart — POS'da ham (tashqi klaviatura/skaner holatlari uchun).
4. **`aria-live`**: toast (Sonner) va offline holat o'zgarishi `aria-live="polite"`; fiskal/xavfsizlik ogohlantirishlari (40/46/48 soat, obuna tugashi) `aria-live="assertive"`.
5. **Rang yagona belgi emas**: har bir semantik rang (success/warning/destructive) doim ikon/matn bilan birga (masalan 🟡 + "Offlayn" matni, faqat rang emas) — rang ko'rlik uchun.
6. **Jadval**: `DataTable` klaviatura bilan qator o'tish (yuqori/past strelka) va `Enter` bilan ochish qo'llab-quvvatlaydi.
7. **Shrift o'lchami**: brauzer/OS darajasidagi zoom (`rem` asosida, `px` qulflanmagan) ishlaydi, maksimal 200% zoomda layout buzilmaydi (asosan back-office uchun, POS qurilmasi odatda qulflangan ekranda).
8. MVP'da semantik HTML/ARIA va yuqoridagi qoidalar; to'liq rasmiy WCAG audit — MVP'dan keyin (26 #52).
9. **Kritik/shoshilinch matn o'lchami**: `text-caption` (11px) offlayn 48 soatlik hisoblagich yoki boshqa kritik/shoshilinch holat matnini chiqarishda **hech qachon** ishlatilmaydi — bunday matn uchun minimal o'lcham `text-small` (13px), og'irligi 600.

---

## 11. i18n kalit nomlash konvensiyasi

`i18next`, namespace — har bir `@pages/*` paketi o'z namespace'iga ega (`pos`, `catalog`, `warehouse`, `debts`, `finance`, `reports`, `settings`, `billing`, `aiAssistant`, `onec`), umumiy — `common`. 1C integratsiyasi (Bosqich 7): ekran matnlari `onec:*`, `ONEC_*` xato kodlari — `common:errors.onec.<kod_kichik_harf>` (masalan `errors.onec.devices_not_synced`), tuzatish maslahatlari — `common:fix_hints.onec.<kod_kichik_harf>`, Telegram shablonlari — `notifications.onec_*` (`33-1c-integratsiya.md` §12, §13.3).

**Format**: `<namespace>:<ekran-yoki-modul>.<element-turi>.<nom>` — kichik harf, nuqta bilan ajratilgan, `camelCase` so'z ichida.

```
common:actions.save
common:actions.cancel
common:states.loading
common:states.empty
pos:sale.payButton
pos:sale.discountLabel
debts:bookScreen.title
debts:bookScreen.addDebtButton
settings:users.resetPinConfirm
```

Qoidalar:
- Tugma matnlari — `actions.*` (umumiy) yoki `<ekran>.<nom>Button`.
- Validatsiya xabarlari — `common:validation.required`, `common:validation.maxLength`, `common:validation.phoneFormat` (zod `errorMap` shu kalitlarga bog'lanadi).
- Server xatosi HTTP javobida `error.message_key` maydonini qaytaradi (masalan `"errors.debt_limit_exceeded"`) — bu satr **o'zgarishsiz** `common` namespace ichida i18n kalit sifatida ishlatiladi: `t('common:' + message_key)`. Agar kalit tarjima fayllarida topilmasa — `common:errors.internal_error`ga zahira qilinadi. Maydon darajasidagi validatsiya xatolari (`details[].message_key`, har bir noto'g'ri maydon uchun bitta) `validation.*` prefiksi bilan keladi — bu frontend zod `errorMap`i ishlatadigan kalitlar bilan bir xil. **Hech qachon** xom kod/JSON ekranga chiqmaydi.
- Rus tarjimasi har doim o'zbek kalit bilan bir fayl tuzilmasida (`uz.json`/`ru.json`, bir xil kalitlar), tarjima yo'q qolganda **o'zbekcha** fallback (hech qachon kalit nomi ko'rsatilmaydi).

---

## 12. Microcopy ohangi va standart xabarlar

**Ohang**: rasmiy-do'stona "Siz" (hurmat), qisqa buyruq fe'li tugmalarda ("Saqlash", "Bekor qilish" — infinitive emas), xato xabarlari ayblamaydi ("Noto'g'ri" emas, "Mos kelmadi"/"Tekshirib ko'ring"), har doim keyingi qadamni aytadi. Raqamlar hech qachon "taxminiy" ko'rsatilmaydi — backend aniq summani beradi.

### Standart xabarlar (uz / ru)

`message_key` ustuni §11'dagi qoidaga mos — server javobidagi `error.message_key` bilan bir xil kalit (yoki client-side holat uchun "—", server kaliti yo'q).

| # | Holat | O'zbek (lotin) | Rus | message_key |
|---|---|---|---|---|
| 1 | Saqlash muvaffaqiyatli | Saqlandi | Сохранено | — |
| 2 | O'chirish muvaffaqiyatli | O'chirildi | Удалено | — |
| 3 | Chek yakunlandi | Chek yakunlandi | Чек завершён | — |
| 4 | Sinxronlandi | Barcha ma'lumotlar sinxronlandi | Все данные синхронизированы | — |
| 5 | Tasdiqlandi | Tasdiqlandi | Подтверждено | — |
| 6 | Rad etildi | Rad etildi | Отклонено | — |
| 7 | Nusxalandi (clipboard) | Nusxalandi | Скопировано | — |
| 8 | Umumiy xato | Xatolik yuz berdi. Qayta urinib ko'ring | Произошла ошибка. Попробуйте снова | `errors.internal_error` |
| 9 | Tarmoq xatosi | Internet aloqasi yo'q. Offlayn rejimda davom etiladi | Нет подключения к интернету. Продолжаем в офлайн-режиме | — |
| 10 | Huquq yo'q | Sizda bu amal uchun huquq yo'q | У вас нет прав для этого действия | `errors.permission_denied` |
| 11 | Obuna tugagan | Obuna muddati tugagan. Davom etish uchun to'lang | Подписка истекла. Оплатите, чтобы продолжить | `errors.subscription_restricted` |
| 12 | Majburiy maydon | Bu maydonni to'ldirish shart | Это поле обязательно | `validation.required` |
| 13 | Noto'g'ri format (telefon) | Telefon raqami formatiga mos emas | Неверный формат номера телефона | `validation.phone_format` |
| 14 | Max uzunlik oshdi | Ruxsat etilgan uzunlikdan oshdi | Превышена допустимая длина | `validation.max_length` |
| 15 | Bekor qilishni tasdiqlash | Haqiqatan bekor qilasizmi? Bu amalni qaytarib bo'lmaydi | Вы уверены, что хотите отменить? Это действие необратимо | — |
| 16 | O'chirishni tasdiqlash | Haqiqatan o'chirasizmi? | Вы уверены, что хотите удалить? | — |
| 17 | PIN noto'g'ri | PIN kod noto'g'ri | Неверный PIN-код | `errors.pin_invalid` |
| 18 | Parol noto'g'ri | Telefon yoki parol noto'g'ri | Неверный телефон или пароль | `errors.invalid_credentials` |
| 19 | Limitdan oshdi | Limitdan oshdi — tasdiqlash kerak | Превышен лимит — требуется подтверждение | `errors.approval_required` (shu xabar `errors.approval_required` va beshta `errors.*_limit_exceeded` kodi bilan baham ko'riladi) |
| 20 | Chek topilmadi | Chek topilmadi | Чек не найден | `errors.not_found` (chek/qidiruv holati; `SALE_NOT_FOUND` — sinxronlanmagan sotuv uchun ishlatiladigan boshqa holat, bu kalitni baham ko'rmaydi) |
| 21 | Mahsulot topilmadi | Mahsulot topilmadi | Товар не найден | `errors.product_not_found` (shuningdek `errors.barcode_not_in_catalog`ni ham qamrab oladi) |
| 22 | Qoldiq yetarli emas | Omborda yetarli qoldiq yo'q | На складе недостаточно остатка | `errors.insufficient_stock` |
| 23 | Markirovka o'qilmadi | Markirovka kodi o'qilmadi, qayta urinilmoqda... | Код маркировки не считан, повторная попытка... | `errors.marking_code_invalid` |
| 24 | Offlaynda sotib bo'lmaydi | Offlaynda sotib bo'lmaydi — narx noma'lum | Нельзя продать офлайн — цена неизвестна | `errors.marking_price_unknown_offline` |
| 25 | Offlayn sotildi (markirovka) | Offlayn sotildi, kod chek bilan OFD'ga yuboriladi | Продано офлайн, код уйдёт в ОФД вместе с чеком | `marking.offline_pending_verification` |
| 26 | Qaytarish offlaynda yopiq | Qaytarish uchun internet kerak | Для возврата нужен интернет | `errors.return_requires_online` |
| 27 | Printer topilmadi | Printer topilmadi. Printerni tekshiring yoki elektron chek bering | Принтер не найден. Проверьте принтер или выдайте электронный чек | — |
| 28 | Smena ochildi | Smena ochildi | Смена открыта | — |
| 29 | Smena yopildi | Smena yopildi, Z-hisobot tayyor | Смена закрыта, Z-отчёт готов | — |
| 30 | Farq aniqlandi (kassa) | Kassada farq aniqlandi. Izoh yozing | Обнаружена разница в кассе. Укажите комментарий | `validation.variance_note_required` |
| 31 | Qarz yozildi | Qarz yozildi | Долг записан | — |
| 32 | To'lov qabul qilindi | To'lov qabul qilindi | Платёж принят | — |
| 33 | AI javob bera olmadi | Bu savolga aniq javob topa olmadim | Не удалось найти точный ответ на этот вопрос | — |
| 34 | Eksport tayyor | Eksport fayli tayyor, yuklab olish boshlandi | Файл экспорта готов, загрузка началась | — |
| 35 | Xodim bloklandi | Xodim bloklandi | Сотрудник блокирован | — |
| 36 | OTP yuborildi | Kod SMS orqali yuborildi | Код отправлен по SMS | — |
| 37 | OTP noto'g'ri | Kod noto'g'ri yoki eskirgan | Код неверный или устарел | `errors.otp_invalid` (shuningdek `errors.otp_expired`ni ham qamrab oladi) |
| 38 | Davlat hisoboti mos keldi | Davlat hisoboti ichki hisob bilan mos keldi | Отчёт государства совпал с внутренним учётом | `tax.reconciliation_matched` |
| 39 | Davlat hisobotida farq | Farq topildi — ko'rib chiqing | Обнаружено расхождение — проверьте | `tax.reconciliation_diff_found` |
| 26\* | Markirovkalangan tovarni offline qaytarish taqiqi | Qaytarish uchun internet kerak | Для возврата нужен интернет | `errors.marking_return_requires_online` |
| 40 | Imtiyoz davri | Obuna muddati o'tdi. {vaqt} ichida to'lang, aks holda kassa to'xtaydi | Подписка просрочена. Оплатите в течение {время}, иначе касса остановится | `billing.grace_banner` |
| 41 | Davr yopilgan | Bu oy yopilgan. Tuzatishni joriy oyda kiriting | Этот месяц закрыт. Внесите исправление в текущем месяце | `errors.period_closed` |
| 42 | Soat orqaga surilgan | Qurilma soatini to'g'rilang va internetga ulaning | Исправьте время на устройстве и подключитесь к интернету | `errors.device_clock_invalid` |
| 43 | Litsenziya tugagan (offline) | Obuna tasdiqlanmadi. Internetga ulaning | Подписка не подтверждена. Подключитесь к интернету | `errors.license_expired` |
| 44 | Masofaviy tasdiq yuborildi | Menejerga tasdiqlash uchun yuborildi. Kuting… | Отправлено менеджеру на подтверждение. Ожидайте… | `approvals.sent` |
| 45 | Offline nasiya limitdan oshdi | Limitdan oshdi — sotuv saqlandi, Egasiga xabar beriladi | Лимит превышен — продажа сохранена, владелец будет уведомлён | `debts.limit_exceeded_offline` |
| 46 | iOS o'rnatilmagan | Kassani ishlatish uchun uni Home ekranga o'rnating | Установите кассу на экран «Домой», чтобы работать | `install.ios_required` |
| 47 | Bank tushumi summasi yo'ldagi puldan katta | Summa bankka o'tmagan tushum qoldig'idan katta | Сумма больше остатка денег в пути | `validation.bank_settlement_exceeds_in_transit` |
| 48 | Bank tushumi o'tkazildi | Bank hisobiga o'tkazildi | Зачислено на расчётный счёт | — |
| 49 | 1C: kun yuborishga qo'yildi | {sana} kuni 1C ga yuborish navbatiga qo'yildi | {дата} поставлен в очередь выгрузки в 1С | — |
| 50 | 1C: preview o'zgardi | Ma'lumot o'zgardi — yangilangan ro'yxatni ko'rib qayta tasdiqlang | Данные изменились — проверьте обновлённый список и подтвердите снова | `errors.onec.preview_changed` |
| 51 | 1C: bajarildi | 1C ga {n} ta hujjat yozildi va o'tkazildi | В 1С записано и проведено документов: {n} | — |
| 52 | 1C: ogohlantirish belgilanmagan | Har bir ogohlantirishni «Ko'rdim» bilan belgilang | Отметьте «Ознакомлен» для каждого предупреждения | — |
| 53 | Offline 46 soat — blok yaqin | 2 soatdan keyin kassa bloklanadi — internetga ulaning | Через 2 часа касса будет заблокирована — подключитесь к интернету | `fiscal.offline_block_soon` |
| 54 | Offline 48 soat — kassa bloklangan | Kassa bloklangan: cheklar 48 soat davomida OFD'ga yuborilmadi. Internetga ulanib cheklarni yuboring | Касса заблокирована: чеки не отправлены в ОФД 48 часов. Подключитесь к интернету и отправьте чеки | `errors.fiscal_offline_48h_blocked` |
| 55 | Qarz to'lovi qarzdan ortiq | Summa joriy qarzdan katta. Ortig'ini naqd qaytaring | Сумма больше текущего долга. Верните остаток наличными | `errors.debt_payment_exceeds_balance` |
| 56 | Yetkazib beruvchiga ortiqcha to'lov taqiqlangan | Summa yetkazib beruvchiga qarzdan katta — sozlamada ortiqcha to'lov taqiqlangan | Сумма больше долга поставщику — переплата запрещена настройкой | `errors.supplier_overpay_blocked` |
| 57 | Yetkazib beruvchiga ortiqcha to'lov (ogohlantirish) | Summa qarzdan katta — ortig'i avans sifatida yoziladi | Сумма больше долга — остаток будет учтён как аванс | — |
| 58 | AI so'rov limiti | Juda ko'p so'rov. Birozdan keyin qayta urinib ko'ring | Слишком много запросов. Попробуйте чуть позже | `errors.rate_limited` |
| 59 | Ijtimoiy karta rekvizitlari | Ijtimoiy karta uchun karta niqobi va RRN majburiy | Для социальной карты обязательны маска карты и RRN | `validation.social_card_details_required` |
| 60 | Markirovka kodi takror | Bu markirovka kodi allaqachon sotilgan | Этот код маркировки уже продан | `errors.marking_code_already_sold` |
| 61 | Elektron chek berildi | Elektron chek yuborildi (sabab: {sabab}) | Электронный чек отправлен (причина: {причина}) | — |

Qator `26\*` — №26 ("Qaytarish offlaynda yopiq") dan farqli, maxsus holat: markirovkalangan tovarni offline qaytarish umuman taqiqlanadi (oddiy qaytarish faqat internet talab qiladi, lekin markirovka uchun bu qattiqroq qoida). Raqamlash ketma-ketligi 1–39 o'zgarmasin degan maqsadda bu qator jadval oxirida qo'shildi.

---

## 13. Chop etish qatlamalari

Adapter: `shared/lib/printer` — `WebUsbPrinterAdapter` / `WebSerialPrinterAdapter` / `WebBluetoothPrinterAdapter` (Chromium; Web Bluetooth — faqat BLE) + `NetworkPrinterAdapter` (faqat HTTP qabul qiluvchi printerlar — Epson ePOS-Print, Star WebPRNT) + **Do'kon agenti** orqali xom TCP 9100 LAN printerlar (qaror #60) + tizim printeri + `CloudPrintAdapter` (Star TSP143IV CloudPRNT / Epson TM-m30III Server Direct Print — iOS uchun yagona printer yo'li) + elektron chek zahirasi (`24-frontend-arxitekturasi.md` §6). Transport kassa qurilmasida POS-16 da tanlanadi.

**Chek berish siyosati**: standart — bosma chek; elektron chek (QR `ofd.soliq.uz` havolasi, Telegram/SMS) faqat printer ishlamasa yoki xaridor so'rasa, kassir tasdig'i bilan (`fiscal_receipts.delivery=electronic` + `delivery_reason`, audit) — VMQ-943 1-ilova 2-band (26 #112 (OQ-018)).

**Kodlash**: kod sahifasi cp866 (`ESC t 17`); chek matnida o'zbek kirill harflari Қ/Ғ/Ҳ bo'lsa (cp866'da yo'q) — chek avtomatik **raster** rejimida (rasm sifatida) chop etiladi; U+02BB (ʻ) har doim `'` ga almashtiriladi. Test matni: "Ўзбекистон Қўқон Ғалла Ҳисоб / Oʻzbekiston gʻalla".

### 13.1 Fiskal chek — 58mm / 80mm ESC/POS shablon

(qaror #29) Har bir tovar qatori, shuningdek sarlavha/yakun yorliqlari **"o'zbekcha / ruscha"** formatida (`name_ru` bo'sh bo'lsa faqat o'zbekcha qator qoladi, ikkinchi qator chiqmaydi). Fiskal rekvizitlar OFD talab qilgan formatda — tarjima qilinmaydi.

**Rekvizitlar (VMQ-943 1-ilova 7-band):** har qatorda — nom, (markirovka kodi), MXIK, katalog bo'yicha o'lchov birligi, shtrix kod, miqdor, narx, QQS stavkasi, QQS summasi; chek oxirida — **to'lov shakli** (naqd / bank kartalari (+ karta turi) / QR-kodli to'lov / aralash), jami summa, jami QQS, sana-vaqt, FM raqami, fiskal belgi, QR-kod (**≥30×30 mm**; kredit/bo'nak/bo'lib to'lash turidagi cheklarda QR va fiskal belgi yo'q). Ijtimoiy karta bilan to'lovda — karta niqobi (`NNNN****NNNN`) va RRN. Bosma kenglik **≥55 mm** (58 mm qog'oz). Stavka bo'yicha jamlanma qator — ixtiyoriy (chiqariladi).

```
       [Do'kon nomi]                 ← markazda, bold, 80mm: 32 belgi / 58mm: 24 belgi
   Manzil, telefon                   ← kichik shrift
   STIR: 000000000  Filial: Chilonzor-3
----------------------------------------
  Chek № K-01-2026-000154   12.10.2026 22:41
  Kassir: Dilnoza               Smena №7
----------------------------------------
  1. Non / Хлеб "Bekhurmon"
     2 x 12 000                        24 000
  2. Coca-Cola 1.5L                    ← name_ru yo'q, faqat bir qator
     1 x 18 000                        18 000
  3. Sut / Молоко "Oltin" 1L
     3 x 9 000                         27 000
----------------------------------------
  Jami / Итого:                      69 000 so'm
  Chegirma / Скидка:                     0 so'm
  QQS / НДС (12%, ichida):         7 392,86 so'm
----------------------------------------
  To'lov shakli / Форма оплаты: Naqd / Наличные
  Olingan / Получено:               100 000 so'm
  Qaytim / Сдача:                    31 000 so'm
----------------------------------------
  FM: <fm_number>   Chek FM №: <fm_receipt_seq>
      [Fiskal belgi: <fiscal_sign>]
      [QR-kod ≥30×30 mm — OFD tekshirish]
----------------------------------------
      Rahmat! Yana kuting. / Спасибо! Ждём вас.
      [NUSXA / КОПИЯ] ← faqat qayta chop etishda
```
MXIK, o'lchov birligi va shtrix kod har tovar qatori ostida kichik shrift bilan chiqariladi (rekvizitlar ro'yxati yuqorida). 58mm'da qator kengligi 24 belgi (nom ikkinchi qatorga tushishi mumkin — ikki tilli nom uzun bo'lsa ruscha qism alohida qatorga tushadi), 80mm'da 32 belgi.

**To'lov shakli yorliqlari (ikki tilda)**: Naqd/Наличные; Bank kartalari/Банковские карты (+ karta turi: shaxsiy/личная, korporativ/корпоративная, ijtimoiy/социальная); QR-kodli to'lov/Оплата по QR-коду (UzQR, Payme, Click, Uzum — provayder nomi qavsda); Aralash/Смешанная (bir chekda bir nechta shakl); Nasiya/В долг (faqat `debt_settlement` chekida ko'rinadi, oddiy sotuv chekida "Nasiya" qatori chiqmaydi — Q3, nasiya sotuvida bu shablonning o'zi chiqarilmaydi).

> **QQS qatori aniqligi** (qaror #26): qog'ozda QQS 2 xonali kasr bilan (`formatMoney(value, { precision: 2 })`); fiskal adapter OFD/hamkorga butun son tiyinda uzatadi — hamkor protokoli bilan tasdiqlanadi (26 #109 (OQ-012)).

**Markirovka qatori** (agar tovar markirovkalangan): qator ostida markirovka kodi (kod chek bilan OFD orqali Asl belgisiga ketadi — qaror #62).

**Qurilma/smena rekvizitlari**: STIR, kassa reg. raqami, smena raqami, ichki chek raqami (`receipt_seq`) va FM bergan raqam (`fm_receipt_seq`) alohida.

### 13.2 Label — 58×40mm (narx yorlig'i)

```
┌──────────────────────────┐
│ Non "Bekhurmon"           │  ← tovar nomi, 1-2 qator
│                            │
│      12 000 so'm          │  ← katta shrift (text-h2 ekvivalenti)
│      (eski: 10 000)       │  ← ixtiyoriy, kichik, chizilgan
│                            │
│  ▌▌▌  ▌ ▌▌ ▌  ▌▌▌  ▌ ▌   │  ← shtrix-kod (bwip-js, EAN-13/Code128)
│      4780000123456        │
└──────────────────────────┘
```
Render: `bwip-js` (brauzerda SVG/canvas) → `react-to-print` orqali, CSS `@page { size: Wmm Hmm; margin: 0 }`, tizim drayveri orqali (xom TSPL/ZPL MVP'da yo'q; yorliq printeri drayverda bir marta mos qog'oz o'lchamiga sozlanadi). Standart o'lchamlar: 58×40 (asosiy narx yorlig'i), 58×30, 43×25, 40×30, 30×20 mm va A4 varaq (3×8 yoki 4×10 to'r); 203 dpi uchun shtrix moduli butun nuqtaga (≈0,125 mm) yaxlitlanadi. Server PDF — faqat >200 yorliq yoki iOS (qaror #54). Ichki (tenant-generated) shtrix-kod uchun alohida raqam diapazoni (arxitektura qarori, `03-modullar-talablari.md` US-M09-05).

---

## Ochiq savollar

- **7.** Tashqi javob kerak: do'kon savdosida faqat elektron chekka rasmiy ruxsat — interim: bosma standart, elektron zahira (§13) — 26 #112 (OQ-018).
- **8.** Tashqi javob kerak: printer transportlari va raster rejimining real uskunada sinovi (Xprinter XP-58/XP-80, BT model; Windows/Android Chrome) — 26 #139 (OQ-060).

## Manbalar

- `spec/kod-uchun/06-ekranlar-umumiy.md` — 41 ekran, UX qoidalari, wireframelar
- `research_notes/ochiq-savollar/P1-soliq-fiskal.md` — chek rekvizitlari (OQ-009), 48 soat blok (OQ-004), elektron chek (OQ-018)
- `research_notes/ochiq-savollar/P6-uskuna-ai-narx.md` — printer transportlari, bulut printer, yorliq o'lchamlari (OQ-059/062)
- `research_notes/ochiq-savollar/D-qarorlar-va-E-standartlar.md` — qaror #57 (shrift), OQ-060 (printer kodlash)
- `spec/kod-uchun/33-1c-integratsiya.md` — 1C eksporti holatlari (§7), xato kodlari (§12), BO-22/BO-23 (§13)
- `spec/kod-uchun/24-frontend-arxitekturasi.md` — stack, kutubxonalar, chop etish strategiyasi
- `spec/kod-uchun/16-offline-sync.md` — offline/sync holatlari
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — login/lockout holatlari
- shadcn/ui (https://ui.shadcn.com), lucide (https://lucide.dev)
