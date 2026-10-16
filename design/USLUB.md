# Dizayn uslubi — "Zamonaviy premium" (barcha ekranlar uchun majburiy)

Manba ekran tarkibi: `spec/kod-uchun/07-ekran-tafsilotlari.md` (har ekran bo'limi: maydonlar, amallar, holatlar). Namuna artboardlar: `design/canvas/project/Main.dc.html` (POS) va `design/canvas/project/Bo02Dashboard.dc.html` (back-office) — ularni o'qing va AYNAN shu uslubni takrorlang.

## Fayl formati
Har ekran — `design/canvas/project/<Nom>.dc.html`, `.dc.html` formatida (namunalardagi skelet: `<script src="./support.js"></script>`, `<x-dc>`, `<helmet>`, `<script type="text/x-dc" data-dc-script data-props='{"$preview":{...}}'>` va `class Component extends DCLogic { renderVals() {...} }`). Qoidalar: har element yopiladi, atributlar qo'shtirnoqda; `{{hole}}` faqat nuqtali qidiruv (ifoda emas — hisoblashni `renderVals()` da qiling); takrorlanuvchi qatorlar `<sc-for list="{{x}}" as="i" hint-placeholder-count="N">`; UI faqat markup (innerHTML yo'q); emoji yo'q; `<iframe>` yo'q; inline `style="..."`; `<helmet><style>` faqat body/a va font link uchun. Haqiqiy `<button>`, `<a href>`, `<input>`+`<label>`; ikonka-tugmada `aria-label`. Matn — o'zbek lotin (`lang="uz"`), kerak joyda rus ikkinchi.

## O'lchamlar
- POS ekranlari: QAT'IY 1366×768 (root `width:1366px;height:768px`), `$preview` shu.
- Back-office (BO-xx, ADM-01): SAHIFA — root suyuq (`min-height` px, kenglik yo'q), sidebar + kontent: `display:flex;flex-wrap:wrap`, sidebar `flex:1 1 240px;max-width:260px`, kontent `flex:999 1 560px;min-width:0`; `$preview` 1440×(sahifa balandligi, odatda 960–1200). Telefonda menyu ustiga tushadi, keng jadval `overflow-x:auto` qutida.
- Login/onboarding (BO-01, BO-21): 1440×900 sahifa, sidebarsiz.

## Shrift
`<helmet>` ichida: `<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">`. Root: `font-family: 'Manrope', system-ui, sans-serif`. Raqam/pul: `font-variant-numeric: tabular-nums`.
O'lchamlar: sahifa sarlavhasi 26px/800; bo'lim sarlavhasi 17px/700; asosiy matn 14px (BO) / 16px (POS); izoh 12–13px; KPI raqam 28px/800; POS jami 46px/800.

## Ranglar (tokenlar)
| Token | Qiymat | Qo'llanish |
|---|---|---|
| bg | #F4F6F8 | sahifa foni |
| surface | #FFFFFF | kartalar |
| surface-2 | #F8FAFB | ichki bloklar, jadval sarlavhasi |
| ink | #0F1B2D | asosiy matn |
| ink-2 | #3D4A5C | ikkinchi darajali matn |
| muted | #6B7686 | izoh, label |
| line | #E7EAEE | chegara |
| brand | #0E7C66 | asosiy amal, aktiv menyu |
| brand-strong | #0A5E4D | hover, bosilgan |
| brand-soft | #E3F2EE | aktiv fon, chip |
| sidebar | #0F1B2D (matn #C9D2DC, aktiv fon #1C2A3F, aktiv matn #FFFFFF, aktiv chap belgi yo'q — fon bilan) |
| amber | #B7791F / soft #FDF3E1 | nasiya, ogohlantirish, offline 24 soat |
| danger | #C8372D / soft #FBEAE8 | xato, blok, o'chirish |
| info | #2F6FDB / soft #E8F0FC | ma'lumot, OFD kutilmoqda |
| violet | #6D4AD8 / soft #EFEAFC | tasdiq kutmoqda (1C, approval) |
| success | #1F8A4C / soft #E5F5EC | muvaffaqiyat |
Gradient, neon, chap-chegarali karta — ISHLATILMAYDI.

## Shakl
- Karta: `background:#fff;border:1px solid #E7EAEE;border-radius:16px;box-shadow:0 1px 2px rgba(15,27,45,.04),0 6px 20px rgba(15,27,45,.05)`; ichki padding 20–24px.
- Tugma asosiy: `height:44px (BO) / 56–64px (POS);border-radius:12px;background:#0E7C66;color:#fff;font-weight:700`. Ikkinchi: oq fon, `border:1px solid #E7EAEE`, matn ink. Xavfli: danger rangida matn, soft fon.
- Input: `height:44px (BO) / 52px (POS);border:1px solid #DCE1E7;border-radius:12px;padding:0 14px;background:#fff`; label ustida 13px/600 ink-2.
- Chip/badge: `padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700` soft fon + kuchli rang matn.
- Jadval: sarlavha qatori surface-2 fonda 12px/600 muted UPPERCASE yo'q (oddiy); qatorlar 52–56px, ajratuvchi `#F0F2F5`; pul ustunlari o'ngga, tabular-nums.
- Bo'shliq: 8 px grid (8/12/16/20/24/32).
- Sidebar (BO): logo «ERP» + do'kon nomi, ikonkali menyu guruhlari (Savdo, Ombor, Moliya, Hisobot, Sozlamalar), pastda foydalanuvchi kartasi. Yuqori panel (topbar): sahifa sarlavhasi, qidiruv, filial tanlash, bildirishnoma ikonkasi.
- POS: yuqori panel 64px (do'kon/kassa/smena, holat chipi online/offline, kassir), kontent kartalarda; asosiy amal tugmalari katta, pastda klaviatura yorlig'i belgisi (kichik kbd uslubi: `padding:2px 6px;border:1px solid #DCE1E7;border-radius:6px;font-size:11px`).

## Ikonkalar (24×24, `fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"`, `aria-hidden="true"`)
| nom | path |
|---|---|
| home | `<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>` |
| cart | `<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M3 4h2l2.5 11h11L21 7H6.2"/>` |
| box | `<path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/>` |
| truck | `<path d="M3 6h11v10H3z"/><path d="M14 10h4l3 3v3h-7"/><circle cx="7" cy="18" r="1.8"/><circle cx="17" cy="18" r="1.8"/>` |
| users | `<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5"/><path d="M16 4.5a3.5 3.5 0 010 7M18 14.5c2 .7 3.2 2.6 3.5 5.5"/>` |
| book | `<path d="M5 4h11a3 3 0 013 3v13H8a3 3 0 01-3-3z"/><path d="M5 17a3 3 0 013-3h11"/>` |
| receipt | `<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>` |
| chart | `<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>` |
| wallet | `<path d="M3 7h16a2 2 0 012 2v9a2 2 0 01-2 2H3z"/><path d="M3 7V5a2 2 0 012-2h11"/><circle cx="16.5" cy="13.5" r="1.3"/>` |
| bank | `<path d="M3 10l9-6 9 6"/><path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/>` |
| tag | `<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.3"/>` |
| doc | `<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 13h6M9 17h6"/>` |
| shield | `<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/>` |
| gear | `<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>` |
| bell | `<path d="M6 16V11a6 6 0 0112 0v5l1.5 2h-15z"/><path d="M10 20a2 2 0 004 0"/>` |
| search | `<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>` |
| plus | `<path d="M12 5v14M5 12h14"/>` |
| check | `<path d="M5 12.5l4.5 4.5L19 7"/>` |
| x | `<path d="M6 6l12 12M18 6L6 18"/>` |
| alert | `<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17v.5"/>` |
| sync | `<path d="M20 11a8 8 0 00-14.5-4.5L4 8"/><path d="M4 4v4h4M4 13a8 8 0 0014.5 4.5L20 16"/><path d="M20 20v-4h-4"/>` |
| wifi-off | `<path d="M3 3l18 18"/><path d="M8.5 16.5a5 5 0 017 0M5 12.5a10 10 0 015.5-2.8M19 12.5a10 10 0 00-2.6-1.8M12 20h.01"/>` |
| printer | `<path d="M7 9V3h10v6"/><path d="M6 18H4v-7a2 2 0 012-2h12a2 2 0 012 2v7h-2"/><path d="M7 14h10v7H7z"/>` |
| scan | `<path d="M4 8V5a1 1 0 011-1h3M16 4h3a1 1 0 011 1v3M20 16v3a1 1 0 01-1 1h-3M8 20H5a1 1 0 01-1-1v-3M7 12h10"/>` |
| card | `<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M7 15h4"/>` |
| cash | `<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/>` |
| qr | `<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><path d="M14 14h2v2h-2zM18 18h2v2h-2zM14 18h2M18 14h2"/>` |
| sparkle (AI) | `<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>` |
| link (1C) | `<path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1"/>` |
| logout | `<path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10"/>` |
| telegram | `<path d="M21 4L3 11l6 2 2 6 3-4 5 4z"/><path d="M9 13l8-6"/>` |

## Ma'lumotlar (namuna kontent)
Do'kon: «[Do'kon nomi]» · filiallar Chilonzor-3, Yunusobod-1 · kassir Dilnoza R., egasi Akmal K., buxgalter Gulnora T. Tovarlar: Non «Patir» 4 000, Sut 2,5% 1 l 13 500, Guruch «Lazer» 18 000/kg, Choy ko'k 100 g 21 000, Gazli ichimlik 1,5 l 9 000 (markirovkali), Shakar 12 500/kg, Tuxum 10 dona 16 000, Kungaboqar yog'i 1 l 24 000, Makaron 500 g 8 500, Pishloq 200 g 28 000. Pul formati: «94 500 so'm» (bo'shliq bilan, BO jadvallarida 2 kasr «94 500,00»). Sana DD.MM.YYYY, vaqt HH:mm. Hech qanday haqiqiy kompaniya/brend logotipi, soxta statistika "foiz o'sish" emas — real hisob-kitobga mos raqamlar. Noma'lumlar `[...]`.

## Har ekran
- `07` dagi o'sha ekran bo'limini o'qing: maydonlar, amallar, holatlar (bo'sh/xato/offline), ruxsat. Asosiy (oddiy) holatni chizing; muhim holatni (xato/offline/bo'sh) ekranning bir qismida kichik banner sifatida ko'rsating.
- Matn tugmalarda o'zbekcha, klaviatura yorlig'i bor joyda kbd chip.
- Sarlavhaga ekran nomi (ID'siz), `<title>` ga ham.

## Fayl nomlari va sidebar havolalari (hamma agent bir xil ishlatadi)
POS: Main.dc.html (POS-02 Sotish), Pos01Kirish, Pos03Tolov, Pos04Chek, Pos05Qaytarish, Pos06Nasiya, Pos07Smena, Pos08Kirim, Pos09Kochirish, Pos10Inventar, Pos11Qidiruv, Pos12Offline, Pos13Qarz, Pos14KassaPul, Pos15Sanash, Pos16Uskunalar (har biri `.dc.html`).
BO: Bo01Kirish, Bo02Dashboard, Bo03Ombor, Bo04Xarid, Bo05Narxlar, Bo06Qarzdorlar, Bo07Qqs, Bo08Jurnal, Bo09Hisobotlar, Bo10DavlatHisobot, Bo11Xodimlar, Bo12Filiallar, Bo13Ai, Bo14Sozlamalar, Bo15Efaktura, Bo16Tasdiqlash, Bo17Xarajatlar, Bo18Yorliq, Bo19Obuna, Bo20Telegram, Bo21Royxat, Bo22OneCSozlama, Bo23OneC, Bo24Bank, Adm01Admin.
Sidebar: Bo02Dashboard dagi `menu` massivini AYNAN ko'chiring, faqat `href` larni haqiqiy fayllarga qo'ying va joriy sahifani `active` qiling: Dashboard→Bo02Dashboard, AI yordamchi→Bo13Ai, Tasdiqlash navbati→Bo16Tasdiqlash, Kassa (POS)→Main, Qarzdorlar→Bo06Qarzdorlar, Tovarlar va narxlar→Bo05Narxlar, Qoldiq va ko'chirish→Bo03Ombor, Xaridlar→Bo04Xarid, Yorliqlar→Bo18Yorliq, Xarajatlar→Bo17Xarajatlar, Bank tushumi→Bo24Bank, E-faktura→Bo15Efaktura, QQS va davlat hisoboti→Bo10DavlatHisobot (QQS ichki hisob BO-07 — shu sahifa ichidan tab/havola), Buxgalteriya→Bo08Jurnal, Hisobotlar→Bo09Hisobotlar, 1C integratsiyasi→Bo23OneC, Sozlamalar→Bo14Sozlamalar (Sozlamalar ichida ichki tablar: Do'kon, Xodimlar→Bo11Xodimlar, Filiallar→Bo12Filiallar, Telegram→Bo20Telegram, Obuna→Bo19Obuna, 1C→Bo22OneCSozlama). Bir menyu bandiga tegishli bir nechta sahifa bo'lsa (masalan Bo07 va Bo10) — mantiqan eng yaqin bandni aktiv qiling.
Ekranlar orasidagi havolalar `<a href="Fayl.dc.html">` bilan (POS oqimi: Pos01Kirish → Main → Pos03Tolov → Pos04Chek → Main).
