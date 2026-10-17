# Dizayn tizimi («Zamonaviy premium», shadcn/ui asosida)

**Maqsad:** «Zamonaviy premium» dizayn tizimi — token, tipografiya, komponent, layout, formatlash va chop etish qoidalari, shadcn/ui asosida.
**Kim uchun:** Frontend dasturchilar, UX dizaynerlar.
**Bog'liq fayllar:** `design/USLUB.md` (uslub qo'llanmasi — vizual qiymatlar manbai), `design/canvas/project/*.dc.html` (41 ta tasdiqlangan maket; namuna — `Main.dc.html` POS, `Bo02Dashboard.dc.html` back-office), `06-ekranlar-umumiy.md`, `07-ekran-tafsilotlari.md`, `24-frontend-arxitekturasi.md`, `16-offline-sync.md`, `14-autentifikatsiya-oauth2.md`, `33-1c-integratsiya.md` (§7 holatlar, §12 xato kodlari, §13 ekranlar), `01-qarorlar.md`.
**Holat:** joriy, 2026-10-16.

Vizual uslub — `design/USLUB.md` va maketlar: teal brend rangi (`#0E7C66`), oq kartalar ochiq-kulrang fonda, to'q (ink) sidebar, Manrope shrifti, yumshoq soyalar va katta radiuslar; gradient, neon va chap-chegarali karta ishlatilmaydi. Bu hujjat o'sha qiymatlarni `shadcn/ui` (Radix + Tailwind) tokenlariga o'giradi; tokenlar `apps/shell` va `packages/shared/ui`da yashaydi. Funksional qoidalar (kontrast, teginish nishoni, §5, §10) maket qiymatlaridan ustun — ular to'qnashgan joyda shu hujjatdagi qiymat qo'llanadi.

---

## 0. Asosiy qarorlar (qisqa)

1. **Pul qoidasi** (qaror #26): saqlash/API darajasida pul har doim **kasr-satr (decimal string)**, masalan `"12000.00"` (`NUMERIC(18,2)`, tiyingacha); narx/tannarx satrlari 4 xonali kasr (`"8333.3333"`), miqdor satrlari 3 xonali kasr (`"1.250"`) — pul uchun JSON `number` turi **taqiqlanadi**. Frontendda pul hisob-kitobi **faqat ikki holatda** ruxsat etiladi: offlayn POS chek jami va submitdan oldingi forma jami — `decimal.js`/`big.js` bilan, satr-satr amal (`Number`/`parseFloat` pul uchun taqiqlanadi, lint qoidasi). Dumalaklashtirish backend bilan **aynan bir xil** bo'lishi shart, yagona funksiya `shared/lib/money`da: `line_total = ROUND_HALF_UP(qty × unit_price − chegirma, 0)` (chek qatori butun so'mgacha, chunki narxlar butun so'm va naqdda tiyin yo'q), QQS summasi (soliq ichida) `= ROUND_HALF_UP(line_total × r/(100+r), 2)` (tiyingacha) — bu `SalePostingService` mantig'iga aynan mos, ikki tomonda umumiy test vektorlari (`shared/money-vectors.json`) bilan tasdiqlanadi (qonunda yaxlitlash qoidasi yo'q — muhandislik qarori, buxgalter tanishadi; eng kichik tanga 50 so'm). Ko'rsatish: `formatMoney(value: string)` **faqat ko'rsatish uchun** — butun so'mgacha ROUND_HALF_UP qiladi, bu qiymat hech qachon API'ga qaytarilmaydi va keyingi hisoblashda ishlatilmaydi; jadvaldagi jami har doim backend qaytargan jami, allaqachon dumalaklashtirilgan qatorlar yig'indisi emas. Istisno: fiskal chek va buxgalteriya/QQS hisobotlari 2 xonali kasr bilan ko'rsatiladi — `formatMoney(value, { precision: 2 })`; fiskal adapter OFD/hamkorga summani **butun son tiyinda** uzatadi (faqat adapter chegarasida) — hamkor protokoli bilan tasdiqlanadi (26 #109 (OQ-012)).
2. **Sana/vaqt**: `DD.MM.YYYY`, vaqt `HH:mm` (24 soat), `dayjs` + uz-latn lokal konfiguratsiyasi (tayyor `dayjs/locale/uz-latn` yo'q bo'lsa, `shared/lib/date` ichida qo'lda bir marta ro'yxatdan o'tkaziladi — bu "qo'lda formatlash" emas, lokal sozlama).
3. **Til**: o'zbek (lotin) — standart va majburiy birinchi til; rus — ikkinchi, almashtiriladigan. Fiskal chek har doim ikki tilli — o'zbek qatori birinchi, rus (`products.name_ru`) ikkinchi (qaror #29, chek shabloni); UI tili almashtirgichi faqat interfeys matnini almashtiradi, chekka ta'sir qilmaydi.
4. **Zichlik (density)**: ikki rejim — `touch` (POS, ≥48×48px nishon) va `compact` (back-office, ≥36×36px). Bitta komponent kutubxonasi, zichlik Tailwind context/`data-density` atributi orqali.
5. **Platformalar**: POS — to'liq ekran, klaviatura/skaner-birinchi; Back-office — sidebar+topbar, ish stoli birinchi, mobil brauzerda responsive; iOS/iPhone/iPad — o'rnatilgan PWA (Home Screen), chop etish faqat bulut-printer, printer bo'lmasa elektron chek zahirasi (`24-frontend-arxitekturasi.md` §6).
6. **Uslub**: shrift Manrope (ilova bilan bundle, CDN yo'q — qaror #57), brend `#0E7C66`, ikonlar lucide-react (chiziqli, `strokeWidth` 1.8); barcha raqam va pul `tabular-nums`.

---

## 1. Rang tokenlari (CSS variables, shadcn formatida — HSL, `--foo: H S% L%`)

Qiymatlar manbai — `design/USLUB.md` «Ranglar» jadvali va maketlar; hex — vakolatli qiymat, HSL — undan hisoblangan (butun songa yaxlitlangan, farq ≤ 1/255). shadcn standart nomlariga loyiha tokenlari qo'shiladi. Har bir semantik rang uchtadan iborat: **`X`** — asosiy rang (ikonka, nuqta, chegara, grafik, to'ldirilgan tugma), **`X-soft`** — yumshoq fon (chip, banner, aktiv fon), **`X-strong`** — yumshoq fon va oq fon ustidagi matn (kamida 4.5:1, §10). Chip/banner doim juftlik: `bg-X-soft text-X-strong`.

### Palitra (light)

| Token | USLUB nomi | Hex | HSL | Qo'llanish |
|---|---|---|---|---|
| `--background` | bg | `#F4F6F8` | `210 22% 96%` | Sahifa foni |
| `--card`, `--popover`, `--secondary` | surface | `#FFFFFF` | `0 0% 100%` | Kartalar, dialog, ikkinchi darajali tugma |
| `--muted` | surface-2 | `#F8FAFB` | `200 27% 98%` | Ichki bloklar, jadval sarlavhasi, chek paneli pastki qismi |
| `--accent` | bg | `#F4F6F8` | `210 22% 96%` | Hover foni, neytral chip, qty stepper foni |
| `--foreground` | ink | `#0F1B2D` | `216 50% 12%` | Asosiy matn; tanlangan kategoriya/davr tabining to'ldirilgan foni |
| `--foreground-secondary` | ink-2 | `#3D4A5C` | `215 20% 30%` | Ikkinchi darajali matn, input label |
| `--muted-foreground` | muted | `#6B7686` | `216 11% 47%` | Izoh, label, jadval sarlavhasi matni (faqat oq fonda — §10) |
| `--border` | line | `#E7EAEE` | `214 17% 92%` | Karta va panel chegarasi |
| `--input` | — | `#DCE1E7` | `213 19% 88%` | Input, select, kbd chegarasi |
| `--divider` | — | `#F0F2F5` | `216 20% 95%` | Jadval/ro'yxat qatorlari ajratuvchisi |
| `--track` | — | `#EEF1F4` | `210 21% 95%` | Progress izi, kutilayotgan qadam nuqtasi |
| `--disabled-foreground` | — | `#9AA4B1` | `214 13% 65%` | Faqat o'chirilgan (disabled) element matni |
| `--primary`, `--ring` | brand | `#0E7C66` | `168 80% 27%` | Asosiy amal, aktiv menyu, fokus halqasi, link |
| `--primary-strong` | brand-strong | `#0A5E4D` | `168 81% 20%` | Hover/bosilgan; `primary-soft` ustidagi matn |
| `--primary-soft` | brand-soft | `#E3F2EE` | `164 37% 92%` | Aktiv fon, tanlangan segment, fokus halosi |
| `--primary-soft-border` | — | `#CFE7E0` | `162 33% 86%` | Bajarilgan qadam chegarasi, brend-chip chegarasi |
| `--success` | success | `#1F8A4C` | `145 63% 33%` | Ikonka, nuqta, grafik (matn emas) |
| `--success-strong` | — | `#1F6B3E` | `144 55% 27%` | Success matni (chip, banner, chegirma summasi), to'ldirilgan success tugma |
| `--success-soft` | success soft | `#E5F5EC` | `146 44% 93%` | «Online», «Tasdiqlandi» chip foni |
| `--warning` | amber | `#B7791F` | `36 71% 42%` | Ikonka, progress, grafik (matn emas) |
| `--warning-strong` | — | `#8A5A12` | `36 77% 31%` | Amber matn; to'ldirilgan amber tugma (Nasiya) foni |
| `--warning-soft` | amber soft | `#FDF3E1` | `39 88% 94%` | Nasiya, ogohlantirish, offline 24 soat foni |
| `--warning-border` | — | `#F1D7A3` | `40 74% 79%` | Amber tugma/karta chegarasi |
| `--destructive` | danger | `#C8372D` | `4 63% 48%` | Xato, blok, o'chirish; to'ldirilgan xavfli tugma, oq fondagi xavfli matn |
| `--destructive-strong` | — | `#A82B22` | `4 66% 40%` | `destructive-soft` ustidagi matn |
| `--destructive-soft` | danger soft | `#FBEAE8` | `6 70% 95%` | Xato banneri, xavfli chip foni |
| `--destructive-border` | — | `#F3CFCB` | `6 62% 87%` | Xavfli ikkinchi tugma chegarasi («Bekor», «Terminalda bekor qilish») |
| `--info` | info | `#2F6FDB` | `218 70% 52%` | Ikonka, «tarozi» chipi nuqtasi, OFD kutilmoqda belgisi |
| `--info-strong` | — | `#1F4FA8` | `219 69% 39%` | Info chip/banner matni |
| `--info-soft` | info soft | `#E8F0FC` | `216 77% 95%` | Ma'lumot banneri foni |
| `--awaiting-approval`, `-strong` | violet | `#6D4AD8` | `255 65% 57%` | Tasdiq kutmoqda (1C preview, approval), markirovka; soft fonda matn sifatida ham (4.9:1) |
| `--awaiting-approval-soft` | violet soft | `#EFEAFC` | `257 75% 95%` | Violet chip foni |
| `--sidebar-background` | sidebar | `#0F1B2D` | `216 50% 12%` | Back-office sidebar foni |
| `--sidebar-foreground` | sidebar matn | `#C9D2DC` | `212 21% 83%` | Menyu bandi matni |
| `--sidebar-muted-foreground` | — | `#8C99A8` | `212 14% 60%` | Guruh sarlavhasi, do'kon nomi, rol |
| `--sidebar-accent` | sidebar aktiv fon | `#1C2A3F` | `216 38% 18%` | Aktiv band foni, foydalanuvchi kartasi |
| `--sidebar-accent-foreground` | sidebar aktiv matn | `#FFFFFF` | `0 0% 100%` | Aktiv band matni |
| `--sidebar-border` | — | `#2E3E56` | `216 30% 26%` | Sidebar/qorong'i panel ichidagi chegara |
| `--sidebar-ring` | — | `#7FD6C1` | `166 51% 67%` | Qorong'i fondagi brend urg'usi (ikonka, fokus) |
| `--overlay` | — | `#0F1B2D` / 55% | `216 50% 12%` | Modal orqa fon: `hsl(var(--overlay) / 0.55)` |

### `packages/shared/ui/src/styles/theme.css`

```css
:root {
  /* shadcn asosiy */
  --background: 210 22% 96%;            /* #F4F6F8 */
  --foreground: 216 50% 12%;            /* #0F1B2D ink */
  --foreground-secondary: 215 20% 30%;  /* #3D4A5C ink-2 */
  --card: 0 0% 100%;
  --card-foreground: 216 50% 12%;
  --popover: 0 0% 100%;
  --popover-foreground: 216 50% 12%;
  --primary: 168 80% 27%;               /* #0E7C66 brand */
  --primary-foreground: 0 0% 100%;
  --primary-strong: 168 81% 20%;        /* #0A5E4D */
  --primary-soft: 164 37% 92%;          /* #E3F2EE */
  --primary-soft-border: 162 33% 86%;   /* #CFE7E0 */
  --secondary: 0 0% 100%;
  --secondary-foreground: 216 50% 12%;
  --muted: 200 27% 98%;                 /* #F8FAFB surface-2 */
  --muted-foreground: 216 11% 47%;      /* #6B7686 */
  --accent: 210 22% 96%;
  --accent-foreground: 216 50% 12%;
  --destructive: 4 63% 48%;             /* #C8372D */
  --destructive-foreground: 0 0% 100%;
  --destructive-strong: 4 66% 40%;      /* #A82B22 */
  --destructive-soft: 6 70% 95%;        /* #FBEAE8 */
  --destructive-border: 6 62% 87%;      /* #F3CFCB */
  --border: 214 17% 92%;                /* #E7EAEE */
  --input: 213 19% 88%;                 /* #DCE1E7 */
  --ring: 168 80% 27%;
  --radius: 0.75rem;                    /* 12px */

  /* Loyiha qo'shimchalari */
  --divider: 216 20% 95%;               /* #F0F2F5 */
  --track: 210 21% 95%;                 /* #EEF1F4 */
  --disabled-foreground: 214 13% 65%;   /* #9AA4B1 */
  --overlay: 216 50% 12%;
  --success: 145 63% 33%;               /* #1F8A4C */
  --success-foreground: 0 0% 100%;
  --success-strong: 144 55% 27%;        /* #1F6B3E */
  --success-soft: 146 44% 93%;          /* #E5F5EC */
  --warning: 36 71% 42%;                /* #B7791F amber */
  --warning-foreground: 0 0% 100%;
  --warning-strong: 36 77% 31%;         /* #8A5A12 */
  --warning-soft: 39 88% 94%;           /* #FDF3E1 */
  --warning-border: 40 74% 79%;         /* #F1D7A3 */
  --info: 218 70% 52%;                  /* #2F6FDB */
  --info-foreground: 0 0% 100%;
  --info-strong: 219 69% 39%;           /* #1F4FA8 */
  --info-soft: 216 77% 95%;             /* #E8F0FC */
  --awaiting-approval: 255 65% 57%;     /* #6D4AD8 violet — 1C preview, approval */
  --awaiting-approval-foreground: 0 0% 100%;
  --awaiting-approval-strong: 255 65% 57%;
  --awaiting-approval-soft: 257 75% 95%; /* #EFEAFC */

  /* Holat aliaslari (qiymat yuqoridagi juftliklardan, dark rejimda ham avtomatik) */
  --offline: var(--warning);            /* 🟡 24 soatdan sinxronlanmagan */
  --offline-strong: var(--warning-strong);
  --offline-soft: var(--warning-soft);
  --offline-foreground: var(--warning-foreground);
  --offline-critical: var(--destructive); /* 🔴 40 soatdan, ⛔ 48 soat blok */
  --offline-critical-strong: var(--destructive-strong);
  --offline-critical-soft: var(--destructive-soft);
  --fiscal-pending: var(--info);        /* "OFD'ga yuborish kutilmoqda" */
  --fiscal-pending-strong: var(--info-strong);
  --fiscal-pending-soft: var(--info-soft);
  --fiscal-pending-foreground: var(--info-foreground);

  /* Sidebar (shadcn sidebar bloki) — light va dark rejimda qorong'i */
  --sidebar-background: 216 50% 12%;    /* #0F1B2D */
  --sidebar-foreground: 212 21% 83%;    /* #C9D2DC */
  --sidebar-muted-foreground: 212 14% 60%; /* #8C99A8 */
  --sidebar-primary: 168 80% 27%;
  --sidebar-primary-foreground: 0 0% 100%;
  --sidebar-accent: 216 38% 18%;        /* #1C2A3F */
  --sidebar-accent-foreground: 0 0% 100%;
  --sidebar-border: 216 30% 26%;        /* #2E3E56 */
  --sidebar-ring: 166 51% 67%;          /* #7FD6C1 */
}

/* Ikki alohida blok: (1) qo'lda tanlangan dark — OS rejimidan qat'i nazar doim ishlaydi;
   (2) OS dark preferensi — faqat foydalanuvchi aniq "light"ni tanlamagan bo'lsa.
   USLUB faqat light qiymatlarni beradi; dark qiymatlar shu palitradan (bir xil ton) kontrast qoidasi (§10) bo'yicha olingan. */
:root[data-theme="dark"] {
  --background: 216 45% 8%;
  --foreground: 212 25% 92%;
  --foreground-secondary: 212 20% 78%;
  --card: 216 40% 11%;
  --card-foreground: 212 25% 92%;
  --popover: 216 40% 11%;
  --popover-foreground: 212 25% 92%;
  --primary: 166 51% 60%;
  --primary-foreground: 216 50% 10%;
  --primary-strong: 166 55% 72%;
  --primary-soft: 168 45% 15%;
  --primary-soft-border: 168 40% 24%;
  --secondary: 216 40% 11%;
  --secondary-foreground: 212 25% 92%;
  --muted: 216 35% 14%;
  --muted-foreground: 212 14% 66%;
  --accent: 216 35% 16%;
  --accent-foreground: 212 25% 92%;
  --destructive: 4 70% 60%;
  --destructive-foreground: 216 50% 10%;
  --destructive-strong: 4 85% 78%;
  --destructive-soft: 4 45% 16%;
  --destructive-border: 4 40% 28%;
  --border: 216 30% 20%;
  --input: 216 28% 26%;
  --ring: 166 51% 60%;
  --divider: 216 30% 16%;
  --track: 216 30% 18%;
  --disabled-foreground: 212 12% 45%;
  --success: 145 50% 50%;
  --success-foreground: 216 50% 10%;
  --success-strong: 145 55% 70%;
  --success-soft: 145 40% 14%;
  --warning: 36 75% 55%;
  --warning-foreground: 216 50% 10%;
  --warning-strong: 38 85% 70%;
  --warning-soft: 36 50% 14%;
  --warning-border: 36 45% 28%;
  --info: 218 75% 64%;
  --info-foreground: 216 50% 10%;
  --info-strong: 218 85% 80%;
  --info-soft: 218 45% 17%;
  --awaiting-approval: 255 70% 70%;
  --awaiting-approval-foreground: 216 50% 10%;
  --awaiting-approval-strong: 255 80% 82%;
  --awaiting-approval-soft: 255 35% 19%;
  --sidebar-background: 216 50% 6%;
  --sidebar-accent: 216 38% 14%;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --background: 216 45% 8%;
    --foreground: 212 25% 92%;
    --foreground-secondary: 212 20% 78%;
    --card: 216 40% 11%;
    --card-foreground: 212 25% 92%;
    --popover: 216 40% 11%;
    --popover-foreground: 212 25% 92%;
    --primary: 166 51% 60%;
    --primary-foreground: 216 50% 10%;
    --primary-strong: 166 55% 72%;
    --primary-soft: 168 45% 15%;
    --primary-soft-border: 168 40% 24%;
    --secondary: 216 40% 11%;
    --secondary-foreground: 212 25% 92%;
    --muted: 216 35% 14%;
    --muted-foreground: 212 14% 66%;
    --accent: 216 35% 16%;
    --accent-foreground: 212 25% 92%;
    --destructive: 4 70% 60%;
    --destructive-foreground: 216 50% 10%;
    --destructive-strong: 4 85% 78%;
    --destructive-soft: 4 45% 16%;
    --destructive-border: 4 40% 28%;
    --border: 216 30% 20%;
    --input: 216 28% 26%;
    --ring: 166 51% 60%;
    --divider: 216 30% 16%;
    --track: 216 30% 18%;
    --disabled-foreground: 212 12% 45%;
    --success: 145 50% 50%;
    --success-foreground: 216 50% 10%;
    --success-strong: 145 55% 70%;
    --success-soft: 145 40% 14%;
    --warning: 36 75% 55%;
    --warning-foreground: 216 50% 10%;
    --warning-strong: 38 85% 70%;
    --warning-soft: 36 50% 14%;
    --warning-border: 36 45% 28%;
    --info: 218 75% 64%;
    --info-foreground: 216 50% 10%;
    --info-strong: 218 85% 80%;
    --info-soft: 218 45% 17%;
    --awaiting-approval: 255 70% 70%;
    --awaiting-approval-foreground: 216 50% 10%;
    --awaiting-approval-strong: 255 80% 82%;
    --awaiting-approval-soft: 255 35% 19%;
    --sidebar-background: 216 50% 6%;
    --sidebar-accent: 216 38% 14%;
  }
}
```

**POS kiosk rejimi** (doim yorug'/kam yorug'lik do'kon muhiti, `06-ekranlar-umumiy.md` §1.5): POS qurilmasi `data-theme="light"` bilan qulflanadi (maketlar light rejimda, yuqori kontrast, chalg'ituvchi dark-mode yo'q) — foydalanuvchi o'zgartira olmaydi; back-office tizim/foydalanuvchi tanloviga ergashadi.

### Semantik rang qo'llanishi

| Token | Qayerda ishlatiladi |
|---|---|
| `primary` | Asosiy tugmalar (TO'LOVGA O'TISH, SAQLASH), aktiv menyu, tanlangan to'lov usuli, link, fokus |
| `foreground` (to'ldirilgan) | Tanlangan kategoriya tabi (POS-02), tanlangan davr tabi (BO-02) — ink fon + oq matn |
| `success` | Muvaffaqiyatli chek, «Online · OFD sinxron», "mos keladi" (BO-10), tasdiqlangan holat belgisi, chegirma summasi |
| `warning` | Nasiya, kam qoldiq, limitga yaqinlashish (84%), offline 24 soat, imtiyoz davri |
| `destructive` | Xato, bekor qilish, bloklash, o'chirish, farq topildi (BO-10), sidebar hisoblagich belgisi |
| `info` | Ma'lumot banneri, «tarozi» chipi, OFD kutilmoqda, e-faktura imzo kutmoqda |
| `awaiting-approval` | Tasdiq kutmoqda (BO-16 navbati), 1C kun partiyasi `preview` (BO-23 kalendari 🟪, §7.3), markirovka chipi |
| `offline` / `offline-critical` | OfflineBadge — 🟡 24 soatdan sinxronlanmagan N chek / 🔴 40 soatdan / ⛔ 48 soat — kassa bloklangan (`offline-critical` + `Lock` ikon), qaror #43 |
| `fiscal-pending` | Offline chiqarilgan chek (shu jumladan markirovkali qator) — OFD'ga yuborish kutilmoqda belgisi |

Gradient, neon rang va chap-chegarali (rangli chap chiziqli) karta ishlatilmaydi (USLUB).

---

## 2. Tipografiya

Shrift: **Manrope** (400, 500, 600, 700, 800) — ilova bilan birga bundle qilingan woff2 (`@fontsource-variable/manrope`, subsetlar latin, latin-ext, cyrillic, cyrillic-ext; ulash — `24-frontend-arxitekturasi.md` §4.1); runtime'da CDN/Google Fonts yuklanmaydi (CSP `default-src 'self'`, offline PWA keshi — qaror #57). Stek: `font-family: 'Manrope Variable', 'Manrope', 'Noto Sans Variable', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`. Manrope'da U+02BB/U+02BC (ʻ ʼ — `oʻ`, `gʻ`) va `Ққ Ғғ Ҳҳ` gliflari **yo'q** (`Ўў` va rus kirill bor) — ular self-hosted Noto Sans zaxirasidan chiqadi (`@fontsource-variable/noto-sans`: ʻ ʼ — `latin` fayli, `Ққ Ғғ Ҳҳ` — `cyrillic-ext` fayli; `@font-face` `unicode-range` faqat shu 8 belgi bilan cheklangan, shuning uchun Noto faqat shu belgi ekranda bo'lganda yuklanadi; PWA precache'da; `apps/shell/src/noto-sans-fallback.css`, test `e2e/font-glyphs.spec.ts`). Asoschi qarori — 26 #141 (qaror #57).

| Token | `font-size` / `line-height`, og'irlik | Back-office qo'llanishi | POS qo'llanishi |
|---|---|---|---|
| `text-display` | 46px / 52px, 800, `letter-spacing: -0.5px`, tabular-nums | — | Chek jami (POS-02), "To'lanadigan" (POS-03), PIN-pad sarlavha |
| `text-h1` | 26px / 34px, 800 | Sahifa sarlavhasi | Ekran/dialog sarlavhasi |
| `text-h2` | 17px / 24px, 700 | Bo'lim va karta sarlavhasi | Panel sarlavhasi ("Chek #000483") |
| `text-kpi` | 28px / 34px, 800, tabular-nums | KPI kartadagi raqam | Smena/kassa jami (POS-07, POS-14, POS-15) |
| `text-money` | 24px / 32px, 800, tabular-nums | — | Chekdagi qator summasi — **kamida body'dan 1.5x katta** (`06-ekranlar-umumiy.md` §1.5) |
| `text-body` | 14px / 20px, 400 | Asosiy matn, jadval katakchasi (pul ustuni — tabular-nums, o'ngga) | — |
| `text-body-pos` | 16px / 24px, 400 | — | Asosiy matn, tovar nomi |
| `text-label` | 13px / 18px, 600, `foreground-secondary` | Input label (input ustida) | Input label |
| `text-small` | 13px / 18px, 400 | Izoh, vaqt belgisi, KPI izohi | Status panel matni, qator meta matni |
| `text-caption` | 12px / 16px, 700 | Chip/badge, jadval sarlavhasi (600, katta harf emas) | Chip, segment matni |
| `text-overline` | 11px / 16px, 700, `letter-spacing: 0.6px`, katta harf | Sidebar guruh sarlavhasi | — |
| `text-kbd` | 11px / 14px, 600 | — | Klaviatura yorlig'i belgisi (`Kbd`) |

Qoidalar:
- **Barcha raqam va pul** — `font-variant-numeric: tabular-nums` (Tailwind `tabular-nums` klassi): summa, miqdor, sana-vaqt, chek/hujjat raqami, KPI, jadval raqamli ustunlari (o'ngga tekislanadi). `MoneyDisplay`, `MoneyInput`, `QtyInput`, `DataTable` raqamli ustunlari buni o'zi qo'yadi.
- Og'irliklar faqat 400/500/600/700/800; sarlavha va summalar 700–800.
- `rem` asosida (bazaviy 16px), `px` qulflanmaydi (§10 band 7).

---

## 3. Spacing, radius, elevation

- **Spacing** — 8px grid (USLUB): layout bo'shliqlari `2`/`3`/`4`/`5`/`6`/`8` (8/12/16/20/24/32px); `1` (4px) va `1.5` (6px) — faqat chip, kbd va ikonka-matn oralig'i ichida. Karta ichki padding'i 20–24px (`p-5`/`p-6`), POS kontent maydoni `p-4` + `gap-4`, back-office kontenti `px-7 py-6`.
- **Radius** — `--radius: 0.75rem` (12px). Tailwind preset xaritasi:

| Klass | Qiymat | Qayerda |
|---|---|---|
| `rounded-sm` | 6px | `Kbd` belgisi, kichik ichki tugma (qty stepper) |
| `rounded-md` | 10px | Sidebar bandi, ikonka plitasi (34–40px), kichik tugma (≤ 40px), segment ichidagi tugma |
| `rounded-lg` | 12px (`--radius`) | Tugma, input, select, banner, ichki blok, qadam kartasi |
| `rounded-xl` | 14px | POS katta tugmalari (56–64px), skaner/qidiruv maydoni, to'lov usuli tugmasi, segmentli boshqaruv qutisi |
| `rounded-2xl` | 16px | Karta (KPI, bo'lim, POS tovar kartasi), POS chek paneli |
| `rounded-3xl` | 20px | Modal dialog (POS-03) |
| `rounded-full` | 999px | Chip/badge, kategoriya tabi, avatar, holat nuqtasi |

- **Elevation** (soya; `rgb(15 27 45 / …)` — ink asosida, qora emas):

| Token | Qiymat | Qayerda |
|---|---|---|
| `shadow-card` | `0 1px 2px rgb(15 27 45 / .04), 0 6px 20px rgb(15 27 45 / .05)` | Barcha kartalar (standart) |
| `shadow-raised` | `0 1px 2px rgb(15 27 45 / .04), 0 10px 28px rgb(15 27 45 / .06)` | POS chek paneli, yopishqoq panel |
| `shadow-popover` | `0 1px 2px rgb(15 27 45 / .04), 0 12px 32px rgb(15 27 45 / .10)` | Dropdown, popover, combobox, toast |
| `shadow-dialog` | `0 24px 60px rgb(15 27 45 / .30)` | Modal dialog; orqa fon `hsl(var(--overlay) / 0.55)` |
| `shadow-cta` | `0 8px 20px rgb(14 124 102 / .28)` | Faqat POS asosiy CTA ("To'lovga o'tish", "To'lovni yakunlash") |
| `shadow-pos-sheet` | `0 -8px 24px -4px rgb(15 27 45 / .12)` | Bottom sheet (kuchliroq yuqori soya) |
| `ring-focus-soft` | `border-2 border-primary` + `0 0 0 4px hsl(var(--primary-soft))` | Faol skaner/qidiruv maydoni (POS-02 F1), fokusdagi input |

- **Z-index skeleti**: `z-dropdown:40`, `z-sticky-header:30`, `z-overlay:50`, `z-dialog:60`, `z-toast:70`, `z-pos-statusbar:80` (offline badge har doim eng tepada). Portal orqali ochiladigan suzuvchi qatlamlar (`Select`, `Popover`, `DropdownMenu`, `Combobox`) `z-dialog` dan foydalanadi — `Sheet`/`Dialog` ustida ochilishi uchun; `z-dropdown` faqat portal'siz menyular uchun.

---

## 4. Ikon to'plami — lucide-react

Maketlar va USLUB lucide uslubidagi chiziqli ikonlardan foydalanadi (24×24 viewBox, `fill="none"`, `stroke="currentColor"`, yumaloq uch va burchak); kodda — **`lucide-react`** (nomli import, tree-shaking — `24-frontend-arxitekturasi.md` §4.2). Qoidalar:
- `strokeWidth={1.8}` — barcha joyda (USLUB); `absoluteStrokeWidth` ishlatilmaydi. Istisno: bajarilgan qadamdagi belgi (`Check`) — 2.2.
- O'lcham: 16px — chip ichida; 18px — sidebar bandi, KPI plitasi, topbar qidiruvi; 20px — ikonka-tugma (40–44px), dialog yopish; 22–24px — POS (skaner maydoni, to'lov usuli tugmasi, terminal paneli).
- Rang `currentColor` (matn rangidan); ikonka plitasi: `rounded-md` 34–44px kvadrat, `X-soft` fon + `X-strong` (yoki `primary-strong`) ikonka.
- Dekorativ ikonkada `aria-hidden="true"`; faqat ikonkadan iborat tugmada `aria-label` majburiy. Emoji UI'da ishlatilmaydi (holat jadvallaridagi 🟢/🟡/🔴 — faqat hujjatdagi belgi, UI'da `StatusChip` + ikonka).

| Vazifa | USLUB nomi | Ikon (lucide-react) |
|---|---|---|
| Dashboard | home | `House` |
| Kassa (POS), savat | cart | `ShoppingCart` |
| Skanerlash | scan | `ScanLine` |
| Qidirish | search | `Search` |
| Qo'shish | plus | `Plus` |
| Chegirma | — | `Percent` |
| To'lov: karta / naqd / QR / aralash | card / cash / qr / wallet | `CreditCard` / `Banknote` / `QrCode` / `Wallet` |
| Karta terminali qurilmasi | — | `Smartphone` |
| Nasiya/qarz, buxgalteriya | book | `BookOpen` |
| Qaytarish | — | `Undo2` |
| Smena | — | `Clock` / `LogIn` / `LogOut` |
| Chiqish | logout | `LogOut` |
| Online / offline, terminal aloqasi | wifi-off | `Wifi` / `WifiOff` |
| Sinxronizatsiya | sync | `RefreshCw` |
| Ombor qoldig'i | box | `Package` |
| Ko'chirish | — | `ArrowLeftRight` |
| Inventarizatsiya | — | `ClipboardList` |
| Xarid | truck | `Truck` |
| E-faktura | receipt | `Receipt` |
| Xarajat | wallet | `Wallet` |
| Bank tushumi | bank | `Landmark` |
| QQS va davlat hisoboti | shield | `Shield` |
| Hisobotlar | chart | `ChartColumn` |
| Yorliqlar, hujjat | doc | `FileText` |
| Tovarlar va narxlar | tag | `Tag` |
| AI yordamchi | sparkle | `Sparkles` |
| 1C integratsiyasi | link | `Link2` |
| Sozlamalar | gear | `Settings` |
| Bildirishnomalar | bell | `Bell` |
| Foydalanuvchilar, mijozlar | users | `Users` |
| Filiallar | — | `Building2` |
| Kassa pul harakati | — | `HandCoins` |
| Obuna/to'lov | — | `CreditCard` |
| Telegram | telegram | `Send` |
| Tasdiq, muvaffaqiyat | check | `Check` / `CircleCheck` |
| Yopish, xato | x | `X` / `CircleX` |
| Ogohlantirish | alert | `TriangleAlert` |
| Bloklash | — | `Lock` / `Unlock` |
| Chop etish | printer | `Printer` |
| Eksport | — | `Download` |
| PIN/parol | — | `KeyRound` |
| Qurilma | — | `Smartphone` / `Monitor` |

---

## 5. Zichlik rejimlari (density)

| Jihat | `touch` (POS) | `compact` (back-office) |
|---|---|---|
| Min. teginish nishoni | **48×48px** (asosiy harakat tugmalari — 56×56px, 26 #13) | 36×36px |
| Tugma balandligi (`<Button>`) | asosiy `h-14`–`h-16` (56–64px; CTA "To'lovga o'tish" — 64px), ikkinchi darajali `h-12` (48px) | `h-11` (44px) standart, `h-9` (36px) kichik |
| Jadval qator balandligi | — (POS jadval kam) | 52–56px (`min-h-[52px]`), ajratuvchi `divider` |
| Shrift bazasi | `text-body-pos` (16px), summalar `text-money`/`text-display` | `text-body` (14px), sarlavha `text-h1`/`text-h2` |
| Input balandligi | 52px (`h-[52px]`; skaner/qidiruv maydoni — 56px) | `h-11` (44px) |
| Gap (tugmalar orasida) | `gap-3` (12px, tasodifiy bosilmasin) | `gap-2` (8px) |

`touch` rejimida (`data-density="touch"`) har bir `<Button>` — `min-height: var(--tap-min)` (48px), ikon-tugma — `min-width: var(--tap-min)`; `Input`/`NativeSelect` — 52px; POS holat qatoridagi chip'lar — 48px balandlik; offline va 48 soat shkalasi chip'i — 13px / 600 (`StatusChip size="md"`).

Amalga oshirish: `<html data-density="touch">` POS shell'ida, `data-density="compact"` back-office shell'ida; Tailwind `data-[density=touch]:h-14` variant guruhi yoki CSS custom property orqali (`--tap-min: 48px`).

> **Eslatma (mobil back-office teginish nishoni)**: yuqoridagi jadvaldagi `compact` 36×36px qiymati **desktop** back-office uchun vakolatli minimum (sichqoncha-birinchi, kursor aniq). 6.3-bo'limdagi mobil PWA (Egasi telefonida) — bu kursorsiz teginish ekrani, shuning uchun unga alohida **`compact-mobile/touch`** rejimi kerak: `@media (pointer: coarse)` yoki `<768px` breakpointda `data-density="touch"`ga o'tadi, lekin POS'ning 48px/56px emas, balki WCAG 2.5.5 bo'yicha **minimal 44×44px** teginish nishoniga mo'ljallanadi (desktop 36px kompakt qiymatidan katta, lekin POS'ning 48px'idan kichik — mobil veb-sahifa zichligi uchun amaliy minimum).

| Rejim | Min. teginish nishoni | Qo'llaniladi |
|---|---|---|
| `compact` (desktop) | 36×36px | Back-office, sichqoncha/klaviatura-birinchi ekran |
| `compact-mobile` / `touch` (mobil) | **44×44px** | Egasi mobil PWA (`@media (pointer: coarse)` yoki `<768px`) |
| `touch` (POS) | 48×48px (asosiy — 56×56px) | POS qurilmasi |

---

## 6. Layout gridlari

### 6.1 POS — to'liq ekran (full-screen app)

Mo'ljal o'lchami — 1366×768 (maketlar), kattaroq ekranda kontent cho'ziladi, chek paneli kengligi o'zgarmaydi.

```
┌──────────────────────────────────────────────────────────────────────┐
│ Yuqori panel 64px: [E] do'kon · kassa / smena │ Online chip │ Printer │ ← z-pos-statusbar
│ chip │ UZ·RU │ kassir avatar                                          │
├───────────────────────────────────────────────┬──────────────────────┤
│ [Skaner / qidiruv 56px  F1] [Kartochka│Ro'yxat]│ Chek #000483  +Mijoz │
│ (Hammasi)(Non va un)(Sut mahsulotlari)…        │ qator: nom · − 2 + · │
│ ┌────┐┌────┐┌────┐┌────┐  tovar to'ri:         │ summa                │
│ │    ││    ││    ││    │  4 ustun, 132px       │ …                    │
│ └────┘└────┘└────┘└────┘  (yoki ro'yxat)       │ Oraliq / Chegirma /  │
│                                                │ QQS / JAMI (46px)    │
│                                                │ [Chegirma][Nasiya]   │
│                                                │ [Bekor]              │
│                                                │ [ To'lovga o'tish F4]│
└───────────────────────────────────────────────┴──────────────────────┘
        katalog (moslashuvchan)                    chek paneli 420px
```
Ikki ustun: chapda katalog (skaner/qidiruv, ko'rinish almashtirgichi, kategoriya tablari, tovar to'ri yoki ro'yxati — `24-frontend-arxitekturasi.md` §5.1), o'ngda chek paneli (`rounded-2xl`, `shadow-raised`; jami va amal tugmalari pastda `muted` fonda). Kontent `p-4 gap-4`; sahifa skrolli yo'q — skroll faqat tovar to'ri va chek qatorlari ichida; sichqonchasiz, klaviatura/skaner-birinchi, har asosiy amal yonida `Kbd` belgisi. Katta oqimlar (POS-03 to'lov) — markaziy modal (`rounded-3xl`, `shadow-dialog`, overlay 55%; chapda usul va panel, o'ngda `muted` fonli "Chek tarkibi" ustuni); qisqa tasdiq va tanlovlar (`ApprovalDialog`, PIN) — `<Sheet side="bottom">`.

### 6.2 Back-office — sidebar + topbar

```
┌────────────┬──────────────────────────────────────────────────────┐
│ [E] ERP    │ Sarlavha · · [Qidiruv] [Filial ▾] [🔔] [UZ│RU]        │
│ do'kon nomi├──────────────────────────────────────────────────────┤
│ GURUH      │                                                      │
│  ▣ Band    │   Kontent (px-7 py-6, kartalar, KPI to'ri            │
│  ▣ Band  4 │   repeat(auto-fit, minmax(210px, 1fr)))              │
│ GURUH      │                                                      │
│  ▣ Band    │                                                      │
│ ┌────────┐ │                                                      │
│ │AK Akmal│ │                                                      │
│ └────────┘ │                                                      │
└────────────┴──────────────────────────────────────────────────────┘
 240–260px, qorong'i (sidebar-background)
```
Sidebar (`--sidebar-*` tokenlari, `p-5 px-3.5`): yuqorida logo plitasi (36px, `rounded-md`, `primary` fon, oq «E») + «ERP» + do'kon nomi (`sidebar-muted-foreground`); guruhlar — guruh sarlavhasi `text-overline` (`sidebar-muted-foreground`), bandlar `text-body` 600, 18px ikon, `px-3 py-2.5 rounded-md`; aktiv band — `sidebar-accent` fon + oq matn (chap chiziqli belgi yo'q); hisoblagich — `destructive` to'ldirilgan pill (11px/800); pastda foydalanuvchi kartasi (`sidebar-accent` fon, avatar `primary-soft`/`primary-strong`, ism + rol). Guruhlar va bandlar tarkibi — `06-ekranlar-umumiy.md` §1.9 (ruxsat bo'yicha). Topbar: oq fon, pastki `border`, `px-7 py-4`; sahifa sarlavhasi (`text-h1`), qidiruv (min 240px, `muted` fon), filial `Select`, bildirishnoma ikonka-tugmasi, eng o'ngda til almashtirgichi «UZ · RU» (segmentli guruh, aktiv — `foreground` fon + oq matn). Foydalanuvchi topbar'da ko'rsatilmaydi — faqat sidebar pastidagi kartada (bosilganda menyu: chiqish). Tarkib va tartib — `06-ekranlar-umumiy.md` §1.9.
`≥1024px`: sidebar doim ochiq; `768–1023px`: sidebar collapse (ikonka-only, `w-16`); `<768px`: sidebar `<Sheet>` (burger menyu) kontent ustiga tushadi, kontent bir ustun, keng jadval `overflow-x-auto` qutida.
Login/onboarding (BO-01, BO-21) — sidebarsiz, to'liq sahifa.

### 6.3 Mobil PWA (Egasi tezkor ko'rish)

Bitta ustun, pastki tab-bar (`Bosh sahifa / Hisobotlar / Qarzlar / AI / Sozlamalar`), header'da filial tanlovi dropdown. Og'ir jadvallar mobil uchun kartaga aylanadi (`DataTable` → `CardList` responsive variant).

---

## 7. Komponent inventari

### 7.1 shadcn/ui (to'g'ridan-to'g'ri, o'zgarishsiz yoki minimal tema bilan)

`Button`, `Input`, `Textarea`, `Select`, `Combobox` (cmdk asosida), `Checkbox`, `RadioGroup`, `Switch`, `Dialog`, `Sheet`, `AlertDialog`, `Popover`, `Tooltip`, `Tabs`, `Card`, `Badge`, `Avatar`, `Table` (TanStack bilan birga), `Calendar` (react-day-picker ^9.14), `Form` (react-hook-form + zod wrapper), `Toast` (Radix — Sonner qat'iy CSP bilan mos emas), `Command` (cmdk), `DropdownMenu`, `NavigationMenu`/`Sidebar` (shadcn `sidebar` bloki), `Skeleton`, `Progress`, `Separator`, `ScrollArea`, `HoverCard`.

### 7.2 Maxsus (loyiha) komponentlar — `packages/shared/ui/`

| Komponent | Vazifa | Asosiy proplar |
|---|---|---|
| **`MoneyInput`** | Pul kiritish — ekranda butun son, minglik ajratgich avtomatik, so'm belgisi suffiks; chiqishda kasr-satr (`"12000.00"`) | `value: string`, `onChange`, `max?`, `allowNegative?` — `precision` 0 da yozilgan `,`/`.` e'tiborsiz qoldiriladi, joylashtirilgan `1240000,50` → 1 240 000 (ajratgich sonni tugatadi). `PhoneInput` 9 ta milliy raqam qaytaradi — API'ga `toE164()` bilan yuboriladi |
| **`PriceInput`** | Tannarx/xarid narxi kiritish — 4 xonagacha kasr (xarid qatori narxi, ochilish qoldig'i tannarxi kabi joylarda) | `value: string`, `onChange`, `max?`, `precision?: 4` |
| **`QtyInput`** | Miqdor kiritish — o'lchov birligiga qarab butun/kasr (dona=butun, kg=**3 xonali kasr**), +/− stepper tugmalari | `value`, `unit: "dona"\|"kg"\|"litr"...`, `step`, `onChange` |
| **`BarcodeField`** (`useBarcodeWedge` hook asosida) | Skaner-fokus maydoni — belgilar orasi <30ms + Enter suffiksini HID skaner sifatida taniydi, qo'lda yozishdan ajratadi | `onScan(code: string)`, `autoFocus`, `placeholder` |
| **`PinPad`** | 4–6 xonali PIN kiritish, raqamli grid, mahalliy/server tasdiqlash | `length`, `onComplete(pin)`, `loading`, `error` |
| **`OfflineBadge`** | Status panelidagi 🟢/🟡/🔴/⛔ ko'rsatkich + sinxronlanmagan son + 48 soat hisoblagichi (24 soat — `offline`, 40 soat — `offline-critical`, 48 soat — `blocked`; qaror #43, `06-ekranlar-umumiy.md` §1.3) | `status: "online"\|"offline"\|"offline-critical"\|"blocked"`, `pendingCount`, `hoursLeft?` |
| **`OfflineDeadlineModal`** | 46 soatdan har yangi chek oldidan ko'rinadigan modal «2 soatdan keyin kassa bloklanadi — internetga ulaning», faqat «Tushundim» bilan yopiladi, sotuvni to'xtatmaydi; ⛔ blok holatida — «Kassa bloklangan» to'liq panel, faqat «Qayta yuborish» (`FISCAL_OFFLINE_48H_BLOCKED`) | `hoursLeft`, `blocked`, `onResend` |
| **`CardManualConfirm`** | POS-03 «Karta (terminalsiz)» to'lovi bloki (`card_entry_mode='manual'`, qaror #64; integratsiyalangan rejimda ishlatilmaydi — natija `CardTerminalPanel`da, #71): **karta kiritish maydoni yo'q** — karta turi, niqob, RRN, tasdiq kodi so'ralmaydi; faqat summa va «Karta terminalsiz qabul qilindi» tugmasi (`CheckCircle2`); `ApprovalDialog` (`kind='card_manual_entry'`) faqat kassaga faol terminal bog'langan va siyosat `manager_approval` bo'lganda ochiladi (sabab `manual_reason`: terminal ulanmagan / xato / natija noma'lum); terminal bog'lanmagan kassada — tasdiqsiz | `amount`, `manualReason`, `requiresApproval`, `onConfirm` |
| **`PrinterSetup`** | POS-16 printer sozlash: transport tanlovi (Web Serial / WebUSB / Web Bluetooth BLE / Do'kon agenti / tizim / bulut), qog'oz kengligi, kod sahifasi, «Test chek» | `transport`, `width: 58\|80`, `onTest` |
| **`SyncStatus`** | POS-12 ro'yxati — har bir outbox voqeasi holati (kutmoqda/xato/muvaffaqiyatli) | `events: SyncEvent[]`, `onRetry` |
| **`ApprovalDialog`** | Limitdan oshgan amal uchun Menejer/Egasi PIN so'rovi (bottom sheet, POS) yoki modal (BO-16) | `reason`, `amount`, `onApprove(pin)`, `onReject(comment)` |
| **`DataTable`** preset'lari | Bosqich 1: server tomonida boshqariladigan (sahifalash/saralash/filtr sahifa modelida, page/cursor — 17 §4); TanStack Table — mijoz saralashi/virtualizatsiya kerak bo'lganda: `DataTable.Compact` (back-office, saralash/filtr/sahifalash/eksport), `DataTable.Mobile` (karta ko'rinishi) | `columns`, `data`, `isLoading`, `emptyState`, `onRowClick` |
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
| **`StatusChip`** | Umumiy holat chipi: nuqta yoki 16px ikonka + matn, `X-soft` fon + `X-strong` matn (`tone`); POS yuqori panelidagi «Online · OFD sinxron», «Printer tayyor», tovar turi chipi (dona / tarozi / markirovka), hujjat holati | `tone: "neutral"\|"primary"\|"success"\|"warning"\|"destructive"\|"info"\|"awaiting-approval"`, `icon?`, `dot?` |
| **`TerminalStatusChip`** | Karta terminali aloqa holati (qaror #71; POS-03 `CardTerminalPanel`, POS-16, BO-12): `online` — `success` + `Wifi` «Wi-Fi · ulangan»; `busy` — `warning` + `Wifi` «Band»; `offline`/`error` — `destructive` + `WifiOff` «Ulanmagan»; natija aniqlanmoqda — `info` + `RefreshCw` (aylanadi) «Tekshirilmoqda»; manba — `$agentStatus.card_terminals[]` va `health` (`24-frontend-arxitekturasi.md` §6.5) | `status: "online"\|"busy"\|"offline"\|"error"\|"unknown"`, `transportLabel?` |
| **`CardTerminalPanel`** | POS-03 integratsiyalangan karta paneli (qaror #71): sarlavha + izoh + `TerminalStatusChip`, terminal qatori, `StepIndicator` (4 qadam), natija maydonlari (faqat o'qish, javobgacha punktir chegara va "terminaldan keladi"), "Terminalda bekor qilish" / "Qayta yuborish", kutish taymeri | `attempt`, `terminal`, `onCancel`, `onRetry`, `onManagerResolve` |
| **`StepIndicator`** | Qadamli jarayon: `horizontal` — POS-03 karta oqimi (har qadam alohida kichik karta: raqamli 26px doira, sarlavha, izoh); `vertical` — onboarding/sozlash ustasi (BO-21, BO-22: 30px doira + sarlavha + izoh, joriy qadam fon bilan). Holatlar: `done` / `active` / `next` / `error` (§7.4) | `steps: {title, sub?, state}[]`, `orientation` |
| **`KpiCard`** | Dashboard KPI kartasi: label (13px/600 `muted-foreground`) + o'ngda 34px ikonka plitasi (`X-soft`/`X-strong`), qiymat `text-kpi`, izoh (12px/600, ohangli) | `label`, `value: string`, `icon`, `tone`, `note?`, `noteTone?` |
| **`Kbd`** | Klaviatura yorlig'i belgisi (F1, F3, F4, Esc …) — tugma yoki maydon ichida, amal nomidan keyin | `keys: string`, `inverted?` (to'ldirilgan tugma ichida) |
| **`SegmentedControl`** | 2–4 variantli tanlov (oq quti ichida segmentlar): POS-02 ko'rinish almashtirgichi «Kartochka / Ro'yxat», BO-02 davr «Bugun / Hafta / Oy», UzQR turi va boshqalar (`07`) | `options`, `value`, `onChange`, `variant: "soft"\|"solid"` |
| **`CategoryTabs`** | POS-02 kategoriya tablari (`role="tablist"`, pill shakli; birinchisi «Hammasi») | `categories`, `activeId`, `onChange` |
| **`ProductTile`** / **`ProductRow`** | POS-02 katalog elementi: `ProductTile` — kartochka ko'rinishi (4 ustunli to'r, 132px: bosh harfli 40px plitka, tovar turi chipi, nom, narx); `ProductRow` — ro'yxat ko'rinishi (bir qator: nom, shtrix-kod/meta, tur chipi, narx o'ngda); ikkalasi butun maydoni bosiladigan `<button>` | `product`, `price: string`, `onAdd` |
| **`Banner`** | Ekran ichidagi qisqa xabar (muhim holat: xato/offline/bo'sh) — ikonka + matn (+ ixtiyoriy havola), `X-soft` fon + `X-strong` matn, `rounded-lg` | `tone`, `icon`, `children`, `action?` |

### 7.3 1C eksporti holat belgilari (Bosqich 7, BO-22/BO-23)

Holat nomlari — `33-1c-integratsiya.md` §7 (o'zgarishsiz); matn kalitlari `onec:status.batch.<status>`, `onec:status.item.<status>`. Jadvallardagi «Token» ustuni ohangni bildiradi — belgi `StatusChip` retsepti bilan chiziladi (`X-soft` fon + `X-strong` matn; `muted` — `bg-accent text-foreground-secondary`; `primary` — `bg-primary-soft text-primary-strong`), §7.4.

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

### 7.4 Komponent uslubi (USLUB retseptlari)

Har komponent shu tokenlar bilan quriladi (`packages/shared/ui` dagi shadcn variantlari); inline rang/hex yozilmaydi — faqat token klasslari.

| Element | Uslub |
|---|---|
| **Karta** (`Card`) | `bg-card border border-border rounded-2xl shadow-card`, padding 20–24px (`p-5`/`p-6`); sarlavha `text-h2`; ichki blok — `bg-muted border rounded-lg` (yoki `rounded-2xl` katta panel) |
| **Tugma — asosiy** (`Button` default) | `bg-primary text-primary-foreground font-bold rounded-lg`, BO `h-11`, POS `h-14`–`h-16` `rounded-xl`; hover/bosilgan `bg-primary-strong`; POS asosiy CTA (64px, 19px/800) + `shadow-cta` + `Kbd inverted` |
| **Tugma — ikkinchi** (`secondary`/`outline`) | `bg-card border border-border text-foreground font-bold rounded-lg` |
| **Tugma — xavfli** (`destructive-outline`) | `bg-card border border-destructive-border text-destructive` («Bekor», «Terminalda bekor qilish»); to'ldirilgan `destructive` — faqat qaytarib bo'lmaydigan tasdiq dialogida |
| **Tugma — amber** (`warning`) | Ikkinchi darajada `bg-warning-soft border border-warning-border text-warning-strong` («Nasiya» POS-02); to'ldirilgan (POS-06 asosiy amal) — `bg-warning-strong text-warning-foreground` |
| **Tugma — punktir** (`dashed`) | `border border-dashed border-muted-foreground/50 bg-card text-foreground-secondary rounded-md`, BO 36px, POS 48px (§5) — «+ Mijoz» |
| **Ikonka-tugma** | BO 40–44px, POS 48px kvadrat, `border border-input rounded-lg`, ikon 20px `foreground-secondary`, `aria-label` majburiy |
| **Input / Select** | BO `h-11`, POS `h-[52px]`; `bg-card border border-input rounded-lg px-3.5`; label ustida `text-label`; fokus — `ring-focus-soft`; xato — `border-destructive` + `text-small text-destructive` ostida; placeholder `muted-foreground` |
| **Skaner/qidiruv maydoni** (POS-02) | 56px, `rounded-xl`, doim fokusda `ring-focus-soft` (2px `primary` chegara + 4px `primary-soft` halo), chapda `ScanLine` 22px `primary`, o'ngda `Kbd` «F1» |
| **Chip / badge** (`Badge`, `StatusChip`) | `rounded-full px-2.5 py-1 text-caption` (12px/700), `bg-X-soft text-X-strong`; neytral — `bg-accent text-foreground-secondary`; ichida nuqta (8px doira, `X`) yoki 16px ikonka, `gap-1.5`; tovar kartasi ichida ixcham variant `px-2 py-0.5 text-[11px]` |
| **Kbd belgisi** (`Kbd`) | `px-1.5 py-0.5 border border-input rounded-sm text-kbd text-muted-foreground`; to'ldirilgan tugma ichida `inverted`: `border-white/50 text-primary-foreground` |
| **Segmentli boshqaruv** (`SegmentedControl`) | Quti `bg-card border border-border rounded-xl p-1`; segment `rounded-md` (POS 48px, BO 36px, 13px/700); `soft` variant (POS-02 ko'rinish) — tanlangan `bg-primary-soft text-primary-strong font-extrabold`; `solid` variant (davr) — tanlangan `bg-foreground text-background`; tanlanmagan — shaffof, `text-muted-foreground`/`text-foreground-secondary`; `aria-pressed` yoki `role="tab"` + `aria-selected` |
| **Kategoriya tablari** (`CategoryTabs`) | Pill: 48px (`touch` minimumi), `px-4 rounded-full border text-[13px] font-bold`; tanlangan `bg-foreground text-background border-foreground`; boshqalar `bg-card border-border text-foreground-secondary` |
| **POS tovar kartasi** (`ProductTile`) | Karta retsepti (`rounded-2xl shadow-card p-3.5`), 132px balandlik, 4 ustunli to'r `gap-3`; yuqorida 40px bosh harfli plitka (`rounded-lg`, `X-soft`/`X-strong`, ohang aylanadi: primary, info, warning, awaiting-approval, destructive) va tur chipi; nom 14px/700; narx pastda 15px/800 tabular-nums |
| **POS tovar qatori** (`ProductRow`) | 56px qator, `border-b border-divider`, nom 16px/700 + meta 12px `muted-foreground`, tur chipi, narx o'ngda 16px/800 tabular-nums; butun qator bosiladi |
| **Chek qatori** (POS-02) | `py-2.5 border-b border-divider`; nom 14px/700 (bir qator, ellipsis) + meta 12px (chegirma — `success-strong`, markirovka — `awaiting-approval`); qty stepper — `bg-accent rounded-lg p-0.5`, ichida oq tugmalar (`touch` minimumi — §5) va 14px/700 son; summa o'ngda `text-money` |
| **Sidebar** | §6.2: guruh sarlavhasi `text-overline text-sidebar-muted-foreground px-2.5 pt-3.5 pb-1.5`; band `flex gap-2.5 px-3 py-2.5 rounded-md text-sm font-semibold text-sidebar-foreground`; aktiv `bg-sidebar-accent text-sidebar-accent-foreground`; hisoblagich `rounded-full px-2 bg-destructive text-destructive-foreground text-[11px] font-extrabold`; foydalanuvchi kartasi `bg-sidebar-accent rounded-lg p-3` |
| **KPI karta** (`KpiCard`) | Karta retsepti, `px-5 py-[18px] gap-2`; label 13px/600 `muted-foreground`, ikonka plitasi 34px `rounded-md` (`X-soft`/`X-strong`), qiymat `text-kpi`, izoh 12px/600 (`X-strong` yoki `muted-foreground`); to'r `grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-3.5` |
| **Qadam indikatori** (`StepIndicator`) | `horizontal` (POS-03): `<ol>` 4 ustunli to'r `gap-2`, har qadam `rounded-lg p-3`; `done` — `bg-card border border-primary-soft-border`, doira `bg-primary text-primary-foreground` + `Check`, izoh `success-strong`; `active` — `bg-primary-soft border-2 border-primary`, doira `bg-card text-primary-strong`, izoh `primary-strong`; `next` — `bg-card border-border`, doira `bg-track text-muted-foreground`; `error` — `bg-destructive-soft border-destructive-border`, doira `bg-destructive` + `X`, izoh `destructive-strong`. `vertical` (BO-21/BO-22): 30px doira (2px chegara), joriy qadam `aria-current="step"` va fon bilan ajratiladi |
| **Terminal holati chipi** (`TerminalStatusChip`) | `StatusChip` retsepti, `px-3 py-1.5`, 16px ikon (`Wifi` / `WifiOff` / `RefreshCw`); holat xaritasi — §7.2 |
| **Jadval** (`DataTable`) | Sarlavha qatori `bg-muted border-t border-border py-3 px-5 text-caption font-semibold` (katta harf emas, matn — §10 band 1); qatorlar `min-h-[52px] px-5 border-t border-divider text-body`; pul/miqdor ustunlari o'ngga, `tabular-nums`, `font-extrabold`; keng jadval `overflow-x-auto` qutida; tanlangan/urg'uli qator foni `primary-soft/40` |
| **Dialog** | Modal: `bg-card rounded-3xl shadow-dialog`, overlay `hsl(var(--overlay) / 0.55)`, sarlavha `text-h1` (POS 24px/800), yopish — ikonka-tugma (POS 48px); POS to'lov dialogida `Esc` faqat kutish holati bo'lmasa yopadi; bottom sheet — `rounded-t-3xl shadow-pos-sheet` |
| **Banner** | `flex gap-2.5 items-center px-4 py-3 rounded-lg text-[13px] font-semibold`, `bg-X-soft text-X-strong`, ikon 18px |
| **Progress** | Iz `h-1.5`–`h-2 rounded-full bg-track`; to'ldirish `bg-primary` (75%+ — `warning`, 90%+ — `destructive`) |
| **Avatar** | Doira 34–36px, `bg-primary-soft text-primary-strong`, bosh harflar 12–13px/800 |
| **Holat nuqtasi** | 8px doira `X` rangida, chip ichida matndan oldin |

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
| `F9` | Mahsulot/narx qidirish (POS-11) | Global; istisno — ombor ekranlari (`/pos/warehouse*`: POS-08/09/10) — u yerda `F9` hujjatni yakunlash/yuborish, POS-11 esa ombor sahifasidagi «Narx/qoldiq» plitkasidan (`stock.view`) ochiladi |
| `F12` | Sinxronizatsiya holati (POS-12) | Global |
| `Enter` | Skanerdan kelgan kodni qabul qilish / tanlangan qatorni tasdiqlash | Hamma joy |
| `Esc` | Joriy dialog/sheet'ni yopish, amalni bekor qilish | Hamma joy |
| `+` / `-` | Tanlangan qator miqdorini oshirish/kamaytirish | POS-02 |
| `Delete` | Tanlangan qatorni o'chirish | POS-02 |
| `Ctrl+P` | Chekni qayta chop etish | POS-04 |

Qoidalar (veb-kassa, joriy holat):
- Global tugmalar (`F6`, `F8`, `F9`, `F12`) faqat hech qanday dialog ochiq bo'lmaganda va ekran klaviaturani o'zi ushlab turmaganda ishlaydi (masalan POS-05 da karta terminalida qaytarish bajarilayotganda — tugmalar va «Orqaga» o'chiq).
- `/pos/*` da `F1`–`F12` ning brauzer standart amallari (yordam, qidiruv, sahifani qayta yuklash va h.k.) har doim bekor qilinadi.
- Fokusdagi tugma, havola yoki radio ustida `Enter`/`Space` — shu elementning o'z amali (ekran qisqa yo'li emas); dialog ichida bosilgan tugmalar faqat o'sha dialogga tegishli.
- POS-11 va POS-12 da `Esc` — oldingi POS ekraniga qaytish (tarix bo'lmasa POS-02, `sales.create` huquqi yo'q foydalanuvchi uchun `/pos/warehouse`).

Back-office'da F-tugmalar band qilinmaydi (brauzer standart xatti-harakati saqlanadi); o'rniga `cmdk` buyruq paneli — `Ctrl+K` / `Cmd+K` tezkor qidiruv/navigatsiya uchun.

---

## 10. Accessibility (asosiy)

1. **Kontrast**: matn/fon nisbati kamida **4.5:1** (WCAG AA), katta matn (≥24px) kamida 3:1. Token darajasida tasdiqlangan: yumshoq fondagi matn doim `X-strong` (`success-strong` 5.8:1, `warning-strong` 5.4:1, `info-strong` 6.7:1, `destructive-strong` 6.0:1, `primary-strong` 6.7:1, `awaiting-approval` 4.9:1); `warning` (`#B7791F`) va `success` (`#1F8A4C`) asosiy ranglari matn uchun ishlatilmaydi (oq fonda ham 4.5:1 dan past) — matnda `-strong`; to'ldirilgan amber/success tugma foni — `-strong`. `muted-foreground` (`#6B7686`, oq fonda 4.6:1) faqat oq (`card`) fonda; `background`/`muted`/`accent`/`track` fonlarida ikkinchi darajali matn — `foreground-secondary`. `disabled-foreground` faqat o'chirilgan element matni (WCAG istisnosi). Sidebar: matn 11.3:1, guruh sarlavhasi `sidebar-muted-foreground` 6.0:1.
2. **Teginish nishoni**: POS ≥48×48px, back-office ≥36×36px (5-bo'lim) — maket o'lchami bundan kichik bo'lsa (qty stepper, kategoriya tabi, ikonka-tugma, segment), komponent minimumgacha kattalashtiriladi.
3. **Klaviatura navigatsiyasi**: har bir interaktiv element `Tab` bilan yetadigan, `focus-visible` halqasi (`ring-2 ring-ring`) ko'rinadigan bo'lishi shart — POS'da ham (tashqi klaviatura/skaner holatlari uchun).
4. **`aria-live`**: toast (Radix Toast) va offline holat o'zgarishi `aria-live="polite"`; fiskal/xavfsizlik ogohlantirishlari (40/46/48 soat, obuna tugashi) `aria-live="assertive"`.
5. **Rang yagona belgi emas**: har bir semantik rang (success/warning/destructive) doim ikon/matn bilan birga (masalan 🟡 + "Offlayn" matni, faqat rang emas) — rang ko'rlik uchun.
6. **Jadval**: `DataTable` klaviatura bilan qator o'tish (yuqori/past strelka) va `Enter` bilan ochish qo'llab-quvvatlaydi.
7. **Shrift o'lchami**: brauzer/OS darajasidagi zoom (`rem` asosida, `px` qulflanmagan) ishlaydi, maksimal 200% zoomda layout buzilmaydi (asosan back-office uchun, POS qurilmasi odatda qulflangan ekranda).
8. MVP'da semantik HTML/ARIA va yuqoridagi qoidalar; to'liq rasmiy WCAG audit — MVP'dan keyin (26 #52).
9. **Kritik/shoshilinch matn o'lchami**: `text-caption` (12px), `text-overline` va `text-kbd` (11px) offlayn 48 soatlik hisoblagich yoki boshqa kritik/shoshilinch holat matnini chiqarishda **hech qachon** ishlatilmaydi — bunday matn uchun minimal o'lcham `text-small` (13px), og'irligi 600.

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
- Validatsiya xabarlari — `common:validation.required`, `common:validation.max_length`, `common:validation.phone_format` (zod `errorMap` shu kalitlarga bog'lanadi).
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
| 26 | Asl chek lokal keshda yo'q (offline qaytarish) | Bu chekni qaytarish uchun internet kerak | Для возврата этого чека нужен интернет | `errors.return_requires_online` |
| 27 | Printer topilmadi | Printer topilmadi. Printerni tekshiring yoki elektron chek bering | Принтер не найден. Проверьте принтер или выдайте электронный чек | — |
| 28 | Smena ochildi | Smena ochildi | Смена открыта | — |
| 29 | Smena yopildi | Smena yopildi, Z-hisobot tayyor | Смена закрыта, Z-отчёт готов | — |
| 30 | Farq aniqlandi (kassa) | Kassada farq aniqlandi. Izoh yozing | Обнаружена разница в кассе. Укажите комментарий | `validation.variance_note_required` |
| 31 | Qarz yozildi | Qarz yozildi | Долг записан | — |
| 32 | To'lov qabul qilindi | To'lov qabul qilindi | Платёж принят | — |
| 33 | AI javob bera olmadi | Bu savolga aniq javob topa olmadim | Не удалось найти точный ответ на этот вопрос | — |
| 34 | Eksport tayyor | Eksport fayli tayyor, yuklab olish boshlandi | Файл экспорта готов, загрузка началась | — |
| 35 | Xodim bloklandi | Xodim bloklandi | Сотрудник блокирован | — |
| 36 | OTP yuborildi (Telegram; `channel_used='telegram'`) | Kod Telegram orqali yuborildi | Код отправлен в Telegram | `otp_sent_telegram` |
| 36a | OTP yuborildi (SMS; `channel_used='sms'`) | Kod SMS orqali yuborildi | Код отправлен по SMS | `otp_sent_sms` |
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
| 59 | Terminalsiz karta rekvizitlari | Terminalsiz karta to'lovida karta ma'lumoti (turi, niqob, RRN, tasdiq kodi) yuborilmaydi | Для оплаты картой без терминала данные карты (тип, маска, RRN, код авторизации) не передаются | `validation.card_manual_details_forbidden` |
| 60 | Markirovka kodi takror | Bu markirovka kodi allaqachon sotilgan | Этот код маркировки уже продан | `errors.marking_code_already_sold` |
| 61 | Elektron chek berildi | Elektron chek yuborildi (sabab: {sabab}) | Электронный чек отправлен (причина: {причина}) | — |

Qator `26\*` — №26 (asl chek lokal POS chek tarixida — 90 kun, qaror #54 — topilmaganda) dan farqli, markirovkali tovar uchun maxsus holat: faqat markirovkali qaytarish online (qaror #23); markirovkasiz tovarni qaytarish offline ruxsat etiladi. Raqamlash ketma-ketligi 1–39 o'zgarmasligi uchun bu qator jadval oxirida turadi. OTP xabari (№36/36a) kalit bo'yicha `channel_used` qiymatiga qarab tanlanadi.

---

## 13. Chop etish qatlamalari

Adapter: `shared/lib/printer` — `WebUsbPrinterAdapter` / `WebSerialPrinterAdapter` / `WebBluetoothPrinterAdapter` (Chromium; Web Bluetooth — faqat BLE) + `NetworkPrinterAdapter` (faqat HTTP qabul qiluvchi printerlar — Epson ePOS-Print, Star WebPRNT) + **Do'kon agenti** orqali xom TCP 9100 LAN printerlar (qaror #60) + tizim printeri + `CloudPrintAdapter` (Star TSP143IV CloudPRNT / Epson TM-m30III Server Direct Print — iOS uchun yagona printer yo'li) + elektron chek zahirasi (`24-frontend-arxitekturasi.md` §6). Transport kassa qurilmasida POS-16 da tanlanadi.

**Chek berish siyosati**: standart — bosma chek; elektron chek (QR `ofd.soliq.uz` havolasi, Telegram/SMS) faqat printer ishlamasa yoki xaridor so'rasa, kassir tasdig'i bilan (`fiscal_receipts.delivery=electronic` + `delivery_reason`, audit) — VMQ-943 1-ilova 2-band (26 #112 (OQ-018)).

**Kodlash**: kod sahifasi cp866 (`ESC t 17`); chek matnida o'zbek kirill harflari Қ/Ғ/Ҳ bo'lsa (cp866'da yo'q) — chek avtomatik **raster** rejimida (rasm sifatida) chop etiladi; U+02BB (ʻ) har doim `'` ga almashtiriladi. Test matni: "Ўзбекистон Қўқон Ғалла Ҳисоб / Oʻzbekiston gʻalla".

### 13.1 Fiskal chek — 58mm / 80mm ESC/POS shablon

(qaror #29) Har bir tovar qatori, shuningdek sarlavha/yakun yorliqlari **"o'zbekcha / ruscha"** formatida (`name_ru` bo'sh bo'lsa faqat o'zbekcha qator qoladi, ikkinchi qator chiqmaydi). Fiskal rekvizitlar OFD talab qilgan formatda — tarjima qilinmaydi.

**Rekvizitlar (VMQ-943 1-ilova 7-band):** har qatorda — nom, (markirovka kodi), MXIK, katalog bo'yicha o'lchov birligi, shtrix kod, miqdor, narx, QQS stavkasi, QQS summasi; chek oxirida — **to'lov shakli** (naqd / bank kartalari (+ integratsiyalangan to'lovda karta turi) / QR-kodli to'lov / aralash), jami summa, jami QQS, sana-vaqt, FM raqami, fiskal belgi, QR-kod (**≥30×30 mm**; kredit/bo'nak/bo'lib to'lash turidagi cheklarda QR va fiskal belgi yo'q). Karta turi, karta niqobi (`NNNN****NNNN`) va RRN faqat integratsiyalangan terminal to'lovida (`card_entry_mode='integrated'`) terminal natijasidan avtomatik chiqariladi; terminalsiz karta to'lovida chekda faqat «Bank kartalari» to'lov shakli — karta rekvizitlarisiz (bunday chekning yetarliligi — 26 #178). Bosma kenglik **≥55 mm** (58 mm qog'oz). Stavka bo'yicha jamlanma qator — ixtiyoriy (chiqariladi).

```
       [Do'kon nomi]                 ← markazda, bold, ikki baravar shrift: 58mm — 16, 80mm — 24 belgi
   Manzil, telefon                   ← kichik shrift
   STIR: 000000000  Filial: Chilonzor-3
----------------------------------------
  Chek № K-01-2026-000154   12.10.2026 22:41
  Kassir: Dilnoza               Smena №7
----------------------------------------
  1. Non / Хлеб "Bekhurmon"
     2 x 12 000                        24 000
     MXIK 10202001001000000 · dona · 4780000123456 · QQS 12%: 2 571,43
  2. Coca-Cola 1.5L                    ← name_ru yo'q, faqat bir qator
     1 x 18 000                        18 000
     MXIK <mxik> · dona · <shtrix kod> · QQS 12%: 1 928,57
  3. Sut / Молоко "Oltin" 1L
     3 x 9 000                         27 000
     MXIK <mxik> · dona · <shtrix kod> · QQS 12%: 2 892,86
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
MXIK, o'lchov birligi, shtrix kod va **QQS stavkasi/summasi** (qator darajasida, qaror #26 formulasi) har tovar qatori ostida kichik shrift bilan chiqariladi (rekvizitlar ro'yxati yuqorida; 1-qator: 24 000 × 12/112 = 2 571,43). QQSsiz qatorda: `· QQSsiz (imtiyoz: <kod>)`. Chek oxiridagi "QQS / НДС (12%, ichida)" jami qatori — qator QQSlari yig'indisi. 58mm'da qator kengligi 32 belgi (Font A, 384 nuqta; ruscha nom alohida kichik qatorda), 80mm'da 48 belgi (576 nuqta; `"{name} / {name_ru}"` sig'sa bitta qatorda); kichik shrift (Font B) — 42/64 belgi (`24-frontend-arxitekturasi.md` §6.1).

**To'lov shakli yorliqlari (ikki tilda)**: Naqd/Наличные; Bank kartalari/Банковские карты (+ faqat integratsiyalangan to'lovda karta turi: shaxsiy/личная, korporativ/корпоративная, ijtimoiy/социальная, noma'lum/не определён; terminalsiz kartada karta turi chiqmaydi — 26 #178); QR-kodli to'lov/Оплата по QR-коду (UzQR, Payme, Click, Uzum — provayder nomi qavsda); Aralash/Смешанная (bir chekda bir nechta shakl). `debt_settlement` chekida to'lov shakli `debt_payments.method` dan; chek sarlavhasi «Qarz to'lovi / Погашение долга» (nasiya sotuvida bu shablonning o'zi chiqarilmaydi).

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
- `design/USLUB.md` — «Zamonaviy premium» uslub qo'llanmasi (tokenlar, shrift, shakl, ikonlar); `design/canvas/project/*.dc.html` — 41 ta maket (`Main.dc.html`, `Pos03Tolov.dc.html`, `Bo02Dashboard.dc.html`, `Bo21Royxat.dc.html` — komponent namunalari)
- shadcn/ui (https://ui.shadcn.com), lucide (https://lucide.dev), Fontsource Manrope (https://fontsource.org/fonts/manrope)
