# P6 — Uskunalar, chop etish, AI vendor narxi (OQ-059, OQ-061, OQ-062, OQ-077)

**Partiya:** P6 (`00-inventar.md` §7, §12). · **Sana:** 2026-10-16. · **Usul:** desk-research (rasmiy vendor hujjatlari, caniuse/Chrome/WebKit hujjatlari, O'zbekiston savdo maydonlari, CBU kursi). · **Spec fayllari o'zgartirilmadi** — "Spec'ga ta'sir" bandlari faqat taklif. · `1c-ut11` MCP ishlatilmadi.

**Eslatma (manba cheklovi):** sessiyaning WebSearch kvotasi ish davomida tugadi — qolgan qidiruvlar WebFetch (sayt qidiruv sahifalari, vendor sahifalari) va Playwright orqali qilindi. Savdo maydonlari narxlari tez o'zgaradi — har narx yonida tekshirilgan sana va URL bor.

---

## Yig'ma

| OQ | Qisqa javob | Ishonch | Holat |
|---|---|---|---|
| OQ-059 | Bulut printerlar Toshkentda bor: Epson TM-m30III (SDP) 5,1–6,6 mln, Star TSP143IV (CloudPRNT) 7,1 mln so'm (OfficeMax.uz); Sunmi 58 mm cloud 1,15–1,23 mln (o'z API'si). Rasmiy distributor yo'q — import zahira. Elektron chek qonuniyligi → OQ-018 (P1). | O'rta-yuqori | **YOPILDI** |
| OQ-061 | EAN-13 `PP CCCCC VVVVV K`; prefiks sozlanadi, standart 22 = og'irlik (g), 21 = summa (so'm). Rongta 3,3–3,7 mln, CAS CL5000J 15,9 mln, Mertech PM 18,3 mln. PLU yuklash — CSV (brauzer TCP/UDP ocha olmaydi); jonli og'irlik — Web Serial (desktop). | Format — yuqori; prefiks standarti — o'rta | **YOPILDI** |
| OQ-062 | XP-365B (TSPL+ESC/POS, ZPL yo'q, ~0,5–0,65 mln) — bozor standarti; hamma modelda Windows drayveri ⇒ brauzer+drayver/PDF asosiy yo'l; o'lchamlar 58×40, 58×30, 43×25, 40×30, 30×20; server PDF — iOS/A4/ommaviy uchun past ustunlik. | Yuqori | **YOPILDI** |
| OQ-077 | Rasm tokeni = ⌈w/28⌉×⌈h/28⌉ (Claude 4.7+ da ≤ 4784, ≤ 2576 px); 2048 px'da ≈ 3 850–4 800 token (1500 emas). Haiku 5.5 $0,10/$0,50, Sonnet 5.5 $2/$10; AI-03 rasm: Sonnet ≈ 153 so'm, Haiku ≈ 7,7 so'm. CBU kursi 12 011,65 (2026-10-16). | Yuqori | **YOPILDI** |

**Qo'shimcha topilma (spec'ga muhim, OQ-060 bilan bog'liq):** `NetworkPrinterAdapter` faqat HTTP qabul qiluvchi printerlarda ishlaydi; arzon LAN ESC/POS printerlar (port 9100) brauzerdan ishlamaydi — pastdagi "Umumiy brauzer/platforma faktlari" bo'limi.

---

## Umumiy brauzer/platforma faktlari (OQ-059 va OQ-060 uchun asos)

| Fakt | Dalil (URL, 2026-10-16 da tekshirildi) | Ishonch |
|---|---|---|
| WebUSB: Chrome desktop 61+, Edge 79+, Chrome Android — bor; **Safari (macOS/iOS) va Firefox — yo'q** | https://caniuse.com/webusb | Yuqori |
| WebUSB himoyalangan (bloklangan) interfeys klasslari: `0x01 Audio, 0x03 HID, 0x08 Mass Storage, 0x09 Hub, 0x0B Smart Card, 0x0E Video, 0x10 Audio/Video, 0xE0 Wireless Controller` — **printer klassi `0x07` bloklanmagan** | WebUSB spetsifikatsiyasi, https://raw.githubusercontent.com/WICG/webusb/main/index.bs | Yuqori |
| Amaliy cheklov: Windows'da OS drayveri (usbprint) printer interfeysini egallab olsa, WebUSB `claimInterface` muvaffaqiyatsiz bo'ladi — WinUSB drayveri (masalan Zadig) o'rnatish kerak bo'ladi; Android'da bu muammo odatda yo'q | Chrome Serial hujjati ("polyfill only works with hardware accessible through WebUSB and not claimed by built-in drivers"), https://developer.chrome.com/docs/capabilities/serial | O'rta (pilotda tasdiqlanadi — OQ-060) |
| Web Serial: Chrome/Edge desktop 89+ (ChromeOS, Linux, macOS, Windows); Chrome Android — caniuse ma'lumotiga ko'ra joriy versiyada (154) bor; Safari/iOS — yo'q | https://developer.chrome.com/docs/capabilities/serial ; https://caniuse.com/web-serial | Desktop — yuqori; Android — o'rta |
| Web Bluetooth (faqat GATT/BLE): Chrome 56+, Edge 79+, Chrome Android — bor; Safari/iOS va Firefox — yo'q. Klassik Bluetooth SPP (ko'p arzon 58 mm printerlar) GATT emas — Web Bluetooth bilan ishlamaydi | https://caniuse.com/web-bluetooth | Yuqori (SPP qismi — o'rta) |
| **Brauzer xom TCP (port 9100) ocha olmaydi**: Direct Sockets API faqat Isolated Web Apps (IWA) uchun, oddiy sayt/PWA uchun emas | https://developer.chrome.com/docs/iwa/direct-sockets | Yuqori |
| Chrome 142+ — Local Network Access: ommaviy saytdan lokal tarmoq qurilmasiga so'rov uchun foydalanuvchi ruxsati so'raladi; xususiy IP literal / `.local` / `fetch(..., {targetAddressSpace: "local"})` so'rovlari mixed-content tekshiruvidan ozod | https://developer.chrome.com/blog/local-network-access | Yuqori |
| iOS: Safari 26'dan "Home Screen'ga qo'shilgan har qanday sayt standart bo'yicha web app sifatida ochiladi"; installability talabi yo'q | https://webkit.org/blog/17333/webkit-features-in-safari-26-0/ | Yuqori |
| iOS ITP: skript yozadigan xotira (IndexedDB, LocalStorage, SW kesh) 7 kun o'zaro ta'sirsiz bo'lsa o'chiriladi; **Home Screen web app domeni bu 7 kunlik cheklovdan ozod** | https://webkit.org/tracking-prevention/ | Yuqori |

**Xulosa (24 §6 uchun muhim tuzatish):** `NetworkPrinterAdapter` ("http tarmoq printeri") faqat **HTTP qabul qiladigan** printerlarda ishlaydi (Epson ePOS-Print/TM-m30 seriyasi, Star WebPRNT klassi). O'zbekistonda keng tarqalgan arzon LAN printerlar (Xprinter, Rongta va b.) faqat xom TCP 9100 (ESC/POS) qabul qiladi — brauzer/PWA ularga to'g'ridan-to'g'ri ulana olmaydi; ular uchun yo'l: USB (WebUSB/Web Serial), tizim printeri (QZ Tray yoki OS drayveri + `window.print`), yoki bulut-print.

---

## OQ-059 — Bulut printer (Star CloudPRNT / Epson Server Direct Print) O'zbekistonda mavjudligi va narxi

**Javob.** **Mavjud, lekin tor kanal orqali.** Toshkentda zaxirada sotilmoqda (asosan bitta reseller — OfficeMax.uz); Star/Epson'ning O'zbekiston bo'yicha rasmiy distributori topilmadi. Narx diapazoni: **Star/Epson bulut-mos 80 mm printerlar — ~4,7–7,1 mln so'm** (oddiy Xprinter 58 mm ~0,25–0,4 mln so'mdan 12–25× qimmat); **Sunmi 58 mm "cloud printer" — ~1,15–1,23 mln so'm**, lekin u CloudPRNT/SDP emas, Sunmi'ning o'z bulut API'si (alohida adapter). Mahalliy narx AQSh chakana narxidan ~1,5–2× yuqori (TSP143IV ~$290–400, TM-m30III ~$265–300 ⇒ import — zaxira kanal).

| Model | Bulut protokoli | Sotuvchi | Narx (so'm, QQS bilan) | URL (2026-10-16) |
|---|---|---|---|---|
| Star TSP143IV UE GY E+U | CloudPRNT (+ CloudPRNT Next/MQTT) | OfficeMax.uz | **7 123 000** (~$593) | https://officemax.uz/shop/orgtehnika/printery-i-mfu/chekovye-printery/star-micronics-tsp143iv-ue-gy-eu-thermal-printer-80mm-wide-paper-24vdc-direct-th-tsp143iv-ue-gy-eu_67470 |
| Epson TM-m30III USB+Ethernet (C31CK50112A0) | Server Direct Print | OfficeMax.uz (bozoro.uz'da 5 062 000) | **5 109 000** (~$425) | https://officemax.uz/shop/orgtehnika/printery-i-mfu/chekovye-printery/epson-tm-m30iii-receipt-printer-203x203-dpi-thermal-line-usb-and-ethernet-compac-c31ck50112a0_67464 |
| Epson TM-m30III USB/Eth/Wi-Fi/BT (C31CK50152A0) | Server Direct Print | OfficeMax.uz | **6 646 000** | https://officemax.uz/shop/orgtehnika/printery-i-mfu/chekovye-printery/epson-tm-m30iii-receipt-printer-thermal-line-printing-203-x-203-dpi-resolution-i-c31ck50152a0_70756 |
| Epson TM-m30II USB+Eth (C31CJ27122A0) | Server Direct Print (Epson sahifasida alohida tekshirilmadi) | OfficeMax.uz | **4 700 000** | https://officemax.uz/shop/orgtehnika/printery-i-mfu/chekovye-printery/epson-tm-m30-ii-pos-receipt-printer-3-thermal-receipt-printer-usb-ethernet-inter-c31cj27122a0_67438 |
| Sunmi NT311 80 mm Cloud | Sunmi bulut (CloudPRNT/SDP emas) | OfficeMax.uz | 4 468 000 | https://officemax.uz/shop/orgtehnika/printery-i-mfu/chekovye-printery/sunmi-nt311-80mm-kitchen-cloud-printer-bluetooth-lan-wi-fi-usb-connectivity-80mm-sun-cld-prnt-uewbt_67482 |
| Sunmi 58 mm Cloud Printer V2 | Sunmi bulut | micros.uz (POS integrator) | 1 233 000 | https://micros.uz/catalog/pos-sistemy-i-torgovoe-oborudovanie/printery-chekov-i-shtrikh-kodov/printer-chekov-sunmi-58mm-cloud-printer-v2-/ |
| Sunmi NT212 58 mm | Sunmi bulut | Uzum Market | 1 150 000 (faqat Google snippet — sahifa ochilmadi) | https://uzum.uz/ru/product/sunmi-58mm-printer-chekov-nt212-963918 |

- **Bulut-mos EMAS (adashtirmaslik uchun):** OfficeMax'dagi eski Star TSP143(100)/TSP143III (3,9–8,4 mln so'm) — CloudPRNT ro'yxatida yo'q; Xprinter XP-58IIT/XP-Q80AS va b. — oddiy USB/LAN/BT ESC/POS. Xprinter'ning bulut modellari (XP-58IINT, XP-C58H) mavjud, lekin UZ do'konlarida topilmadi.
- **Mahalliy topilmadi:** mC-Print3, mC-Print2, TM-T88VI/VII, TM-m50.
- **Arxitektura faktlari:** CloudPRNT — printer serverga **o'zi** davriy HTTP(S) POST yuboradi (standart interval **5 s**, server sozlaydi), ish bo'lsa GET bilan oladi va DELETE bilan tasdiqlaydi; HTTPS (TLS 1.2/1.3, Mozilla CA) qo'llab-quvvatlanadi; do'konda kiruvchi port/statik IP kerak emas; MQTT rejimida server push qiladi. Epson SDP — printer serverga davriy so'rov yuboradi (hujjat misoli "every 60 sec", integratorlar 1 s gacha qo'yadi), ma'lumot formati — **ePOS-Print XML** (ESC/POS emas).
- **Huquqiy qism** (faqat elektron chek bilan ishlash qonuniyligi) — **OQ-018 (P1)** ga tegishli; bu yerda yopilmaydi.

**Dalil.** Sotuvchi sahifalari (yuqoridagi jadval, 2026-10-16); Star CloudPRNT SDK: https://star-m.jp/products/s_print/CloudPRNTSDK/Documentation/en/articles/getting-started/getting-started.html (qo'llab-quvvatlanadigan modellar: mC-Print2, mC-Print3, TSP100IV, mC-Label2/3, HI01X/HI02X bilan TSP650II/700II/800II); https://www.starmicronics.com/product/tsp143iv-thermal-receipt-printer/ ("CloudPRNT Next technology with MQTT protocol"); polling: https://star-m.jp/products/s_print/sdk/StarCloudPRNT/manual/en/client.html va https://star-m.jp/products/s_print/sdk/StarCloudPRNT/manual/en/protocol-reference/http-method-reference/server-polling-post/polling-timing.html; Epson SDP: https://download4.epson.biz/sec_pubs/pos/reference_en/technology/server_direct_print.html, TM-m30III Technical Reference Guide ("Supports Server Direct Print that sends a request for print data from the product to the Web server at regular intervals"). Qidiruv cheklovi: uzum.uz qidiruvi 502 qaytardi, olcha.uz natija bermadi, texnomart/asaxiy/mediapark to'liq tekshirilmadi — boshqa sotuvchilar bo'lishi mumkin.

**Ishonch:** O'rta-yuqori (OfficeMax narxlari va vendor hujjatlari — yuqori; bozor qamrovi — o'rta; AQSh narxlari — Google Shopping snippetlari, tasdiqlanmagan).

**Spec'ga ta'sir (taklif):**
- `25-nofunksional-talablar.md` §7.2 oxirgi qator "| Bulut printer (Star CloudPRNT / Epson Server Direct Print klassi, iOS veb-kassa uchun majburiy) | **narx tasdiqlanmagan** |" → **"| Epson TM-m30III (Server Direct Print) | 5 109 000 (USB+Eth) – 6 646 000 (Wi-Fi/BT) — OfficeMax.uz, 2026-10-16 |"**, **"| Star TSP143IV (CloudPRNT) | 7 123 000 — OfficeMax.uz, 2026-10-16 |"**, **"| Sunmi 58 mm Cloud Printer (Sunmi bulut API, CloudPRNT emas) | 1 150 000–1 233 000 — micros.uz/Uzum |"**; jadval ostidagi "Bulut printerning O'zbekiston bozorida mavjudligi va narxi bu tekshiruvda topilmadi — ochiq savol" → **"Mavjud (asosan bitta reseller, rasmiy distributor yo'q) — zaxira kanal: import (AQSh narxi ~$265–400). Manba: `research_notes/ochiq-savollar/P6-uskuna-ai-narx.md` OQ-059."**
- `24-frontend-arxitekturasi.md` §6 `CloudPrintAdapter` jumlasiga qo'shimcha: **"CloudPrintAdapter — server tomon: printer o'zi so'raydigan polling endpoint (`/print/cloudprnt` — Star CloudPRNT HTTP, standart 5 s; `/print/epson-sdp` — Epson SDP, ePOS-Print XML). Frontend faqat chop etish ishini serverga navbatga qo'yadi. Sunmi bulut — MVP'dan keyin alohida adapter."** Shuningdek `NetworkPrinterAdapter` tavsifiga: **"faqat HTTP qabul qiluvchi printerlar (Epson ePOS-Print, Star WebPRNT); xom TCP 9100 ESC/POS printerlarga brauzer ulana olmaydi (Direct Sockets faqat IWA). Chrome 142+ Local Network Access ruxsati so'raladi."**
- `01-qarorlar.md` #21, `06-ekranlar-umumiy.md` §1.6 va OS12, `03-modullar-talablari.md` 75-qator va OS13: "(masalan Star CloudPRNT, Epson Server Direct Print — **taxmin**, aniq model tasdiqlanmagan)" → **"(Star TSP143IV — CloudPRNT, Epson TM-m30III — Server Direct Print; Toshkentda ~5,1–7,1 mln so'm, 2026-10-16)"**; ochiq savolning "mavjudligi/narxi" qismi o'chiriladi, "faqat-elektron-chek ruxsati" qismi OQ-018 ga havola bilan qoladi.
- `26-ochiq-savollar-reestri.md` B#11: "Bulut-print chek printerining O'zbekistonda narxi/mavjudligi" qismi yopiladi; yurist/OQ-018 qismi qoladi.
- `25` §11/§12 (unit-iqtisod) yoki onboarding matni: iOS kassa uchun uskuna to'plami narxi ~5–7 mln so'm ekanini mijozga oldindan ko'rsatish (savdo e'tirozi) — **iOS yo'li amalda asosiy emas, zahira** deb belgilash tavsiya etiladi; arzon variant — Android planshet + USB/BT Xprinter.

**Holat: YOPILDI** (mavjudlik va narx manbali; elektron chek qonuniyligi OQ-018/P1 da).

## OQ-061 — Tarozi og'irlik shtrix-kodi formati va ulanish protokoli

**Javob.**
1. **Format — amalda yagona tuzilma, prefiks esa har xil.** Barcha tekshirilgan vendor/raqobatchilar EAN-13 ni `PP CCCCC VVVVV K` ko'rinishida ishlatadi: 2 xonali prefiks (GS1 cheklangan muomala diapazoni 20–29), 5 xonali tovar (PLU) kodi, 5 xonali qiymat (og'irlik grammda yoki summa), EAN-13 nazorat raqami. Farq — **qaysi prefiks** va **qiymat og'irlikmi yoki summami**. GS1 Uzbekistan (gs1uz.org) 20–29 ichki tuzilmasi bo'yicha qo'llanma bermaydi — mahalliy kelishuv.
   - BuySale.uz (mahalliy O'zbekiston POS, yagona topilgan mahalliy precedent): **22 — og'irlik (gramm)**, **21 — summa (so'm)**; "сумма больше 99 999 сум в код не помещается" — shu sababli og'irlik rejimi tavsiya etiladi; bir tovarning ikki yorlig'i bitta qatorga jamlanadi.
   - MoySklad: "Весовой штрихкод имеет следующую структуру: ПП ККККК ВВВВВ Х" (misol `2020004023452` → prefiks 20, kod 20004, 2,345 kg); prefiks sozlanadi.
   - iiko, LiteBox+Shtrih-Print: 20 — vazn tovar, 21 — dona; Poster: birinchi 7 raqam = tovar shtrix-kodi, keyingi 5 = gramm; CAS CL misol formati `23IIIIIWWWWWC`; forumlarda 21/22/23/24/29 ham uchraydi ⇒ **prefiks — tenant sozlamasi, konstanta emas**.
2. **O'zbekistonda sotiladigan yorliqli tarozilar (2026-10-16):** Rongta RLS1000A/RLS1100/…B — **3,33–3,73 mln so'm** (scalesstore.gl.uz) — ommaviy arzon segment; CAS CL5000J — **15,9 mln** (a-one.uz; TCP/IP, RS-232); Mertech M-ER 725/727 PM (Android, Shtrih-Print protokoli) — **18,3 mln**, VISION-AI — 24,2 mln (mertech.uz); nomsiz 30 kg sensorli yorliq tarozisi (Wi-Fi/LAN, o'zbekcha yorliq) — 5,7–7,3 mln (Uzum/YES_POS); ishlatilgan CAS CL5000J / Shtrih — ~4,1 mln (OLX). DIGI, Mettler Toledo, Aclas, Massa-K — UZ savdo maydonlarida topilmadi. Mahalliy integrator: Bar Code Technologies (shtrih-m.uz, 3000+ tarozi o'rnatgan).
3. **Protokollar:**
   - PLU yuklash (yorliqli tarozi): CAS CL — TCP **port 20304** (CL-Works); Shtrih-Print — **UDP 1111** (jo'natish 2000) yoki RS-232, "Loader" CSV importi; Mertech PM — Shtrih-Print mos + "Менеджер весов"; Rongta/Aclas — Ethernet + PC dasturi/SDK (port topilmadi). **Brauzer xom TCP/UDP ocha olmaydi** ⇒ PLU yuklash MVP'da **CSV eksport** (vendor dasturi bilan import) yoki keyinroq mahalliy agent.
   - Kassada jonli og'irlik (yorliqsiz tarozi): CAS AP/ER ("CAS-M", RS-232, host ENQ 05h bilan so'raydi — to'liq freym tasdiqlanmagan), Mertech POS2-M/CAS2-M (RS-232/USB virtual COM), Massa-K "Протокол 100" (Ethernet/Wi-Fi/USB-COM/RS-232). Desktop Chrome/Edge'da **Web Serial** (89+, HTTPS, port bir marta tanlanadi, `getPorts()` eslab qoladi) orqali o'qish mumkin. Android Chrome'da Web Serial holati noaniq (caniuse joriy versiyada "supported" ko'rsatadi, Chrome hujjati esa faqat WebUSB+polyfill deydi) — Android'da Kotlin POS native USB-serial ishonchliroq.

**Dalil.** https://buysale.uz/ru/qollanma/vesovoy-shtrih-kod/ ; https://support.moysklad.ru ("Как использовать штрихкоды"); https://knowledge-base.joinposter.com/ru/how-to-add-a-barcode-to-products ; ru.iiko.help (topic-904, topic-3040 — Google snippet); https://litebox.ru/support/instructions/vesy-shtrikh-print/ ; Rarus CAS CL qo'llanmasi https://rarus.ru/downloads/2489/ (Menu 1261, `23IIIIIWWWWWC`, port 20304); https://gs1uz.org/support/barcode-implementation ; https://en.wikipedia.org/wiki/List_of_GS1_country_codes (020–029 restricted circulation); narxlar: https://scalesstore.gl.uz/ru/proposals/torgovie-vesi-11161/ , https://a-one.uz/vesy-i-tenzodatchiki/vesy/nastolnye-vesy/vesy-torgovye-s-pechatyu-etiketok-cl5000j , https://mertech.uz/electronic_scales_uz/scales_label_uz/ , https://uzum.uz/ru/product/torgovye-elektronnye-vesy-2890224 ; protokollar: https://mertech.ru/protokoly-obmena-s-vneshnimi-ustroystvami/ , https://massa.ru/soft/protokoly-obmena-s-vneshnimi-ustroystvami/protokol-100/ , https://developer.chrome.com/docs/capabilities/serial . Barcha 2026-10-16.

**Ishonch:** Format tuzilmasi — yuqori (bir nechta mustaqil manba bir xil); standart prefiks tanlovi — o'rta (mahalliy precedent bitta); narxlar — yuqori (Rongta, CAS, Mertech), OLX — o'rta; Rongta/Aclas bosma tartibi, CAS-M freymi, BILLZ/mDokon standartlari — **tasdiqlanmagan**.

**Spec'ga ta'sir (taklif):**
- `03-modullar-talablari.md` US-M09-06: "Kod formati — keng tarqalgan EAN-13 "2x" prefiksli og'irlik kodi: **taxmin**, real tarozi modellarida tekshiriladi." → **"Kod formati — EAN-13 `PP CCCCC VVVVV K` (PP — 20–29 dan sozlanadigan prefiks, CCCCC — 5 xonali PLU, VVVVV — og'irlik grammda yoki summa so'mda, K — nazorat raqami). Standart: 22 = og'irlik (g), 21 = summa (so'm, ≤ 99 999); 20, 23–29 qo'shimcha qo'shiladi. Manba: BuySale.uz, MoySklad, iiko, CAS CL qo'llanmalari (P6 OQ-061)."** + yangi AC: **"Given bir tovarning ikki og'irlik yorlig'i skanerlanadi, Then og'irliklar bitta chek qatorida jamlanadi"**; **"Given nazorat raqami mos kelmaydi, Then kod rad etiladi"**; **"Given summa prefiksi, Then miqdor = summa ÷ joriy narx, narx farq qilsa ogohlantirish"**.
- `19-api-ombor.md` §17 (`stock-settings` — "tarozi kod formati"): sozlama sxemasi **`weight_barcode_templates[]: {prefixes: string[], item_code_len: 4..6 (std 5), value_len: 5, value_kind: WEIGHT|AMOUNT, decimals: 0..3 (WEIGHT=3 → kg), enabled}`**, standart ikki shablon (22/WEIGHT, 21/AMOUNT); `11-malumotlar-modeli.md` OS3 / `12-db-sxema.md` ga tegishli JSONB sozlama.
- `06-ekranlar-umumiy.md` §1.6 "Tarozi: avtomatik protokol integratsiyasi tasdiqlanmagan (`06-fayl`, 3-bo'lim: "aniq protokol nomi topilmadi")" → **"Tarozi: (a) yorliqli tarozi — EAN-13 og'irlik kodi skanerlanadi (asosiy yo'l, protokolsiz); (b) yorliqsiz kassa tarozisi — desktop Chrome/Edge'da Web Serial orqali (CAS-M, Mertech POS2-M, Massa-K Протокол 100) — MVP'dan keyin; (c) qo'lda og'irlik — doimiy zahira."**; OS5 "protokoli aniqlanmagani sababli" → yopildi (format manbali), jonli o'qish — pilot/OQ-060.
- `25-nofunksional-talablar.md` §7.3 jadval: "AOTE 777 … manbada yo'q" / "Umumiy diapazon 250 000–750 000+ … ochiq manbada topilmadi" → **"Rongta RLS1000A/1100 — 3 330 600–3 727 100 (scalesstore.gl.uz); CAS CL5000J — 15 913 000 (a-one.uz, TCP 20304); Mertech M-ER 725 PM — 18 303 000 (mertech.uz, Shtrih-Print protokoli) — 2026-10-16"** (250–750 ming oralig'i — yorliqsiz oddiy tarozilar uchun qoladi); §OS5 va 14-bandi "tarozi protokoli … topilmadi" → yopildi.
- `03`/`19` PLU yuklash: **"MVP — PLU ro'yxatini CSV eksport (PLU kodi, nom, narx, yaroqlilik muddati) — vendor dasturi (CL-Works, Shtrih Loader, Rongta tool) bilan import; to'g'ridan-to'g'ri yuklash (CAS TCP 20304, Shtrih UDP 1111) brauzerdan mumkin emas — kelajakda mahalliy agent."**
- `26-ochiq-savollar-reestri.md` B#31 — "vendor so'rovi" o'rniga "desk-research bilan yopildi; pilot faqat tanlangan prefiksni tasdiqlaydi".

**Holat: YOPILDI** (format va prefiks sozlamasi manbali; jonli og'irlik o'qish transporti OQ-060 pilotiga qoladi — bloklamaydi).

## OQ-062 — Yorliq printeri protokoli, o'lchamlari va server PDF zahirasi chastotasi

**Javob.**
1. **Bozor standarti — Xprinter XP-365B** (~0,50–0,65 mln so'm; Uzum'da 905 sharhli eng ko'p sotiladigan pozitsiya; REGOS katalogidagi yagona yorliq printeri). Undan keyin XP-420B (~0,97–0,99 mln), XP-470B (~1,08 mln, USB+LAN), Gainscha GP-3121TUD (0,70 mln); omborxona/yirik do'kon segmenti — Mertech DT80 (1,77 mln), Godex G500 (1,94–2,23 mln), TSC TE200 (2,58 mln), Zebra ZD220d (3,88 mln).
2. **Buyruq tillari (rasmiy spec sahifalari):** XP-365B — **faqat TSPL + ESC/POS, ZPL yo'q** (76 mm bosma kengligi, 20–82 mm lenta, 203 dpi); XP-420B/470B — TSPL, ZPL, EPL, DPL (108 mm); Zebra ZD220 — ZPL II, EPL 2; TSC TE200 — TSPL-EZD + ZPL/EPL/DPL emulyatsiyasi; Mertech DT80 — ZPL; Godex G500 — EZPL (+GZPL/GEPL emulyatsiyasi — rasmiy sahifa ochilmadi, tasdiqlanmagan). **Barcha modellarda Windows drayveri bor** ⇒ brauzer `window.print()`/PDF yo'li hammasida ishlaydi. Xom-ZPL strategiyasi eng ommaviy XP-365B'da ishlamaydi.
3. **Ommaviy termo-yorliq o'lchamlari (Uzum'dagi eng ko'p sharhli lentalar bir xil to'plam taklif qiladi):** **58×40**, 58×30, 43×25, 40×30, 30×20 mm. Narxlar: 58×40 (450–500 dona) — ~13 500 so'm/rulon; 30×20 (1450 dona) — ~20 650; 43×25 — 16 000 (1000 dona); 40×30 (800 dona) — 17 940; 58×30 (500 dona) — 30 000. 100×150 mm (marketplace nakladnoyi) — UZ'da topilmadi, faqat 4 dyuymli printerlarga (XP-420B/470B) mos.
4. **Raqobatchilar:** MoySklad — brauzer shablon muharriri, qog'oz turi "А4 — для обычного принтера" yoki "термолента — для рулонного принтера этикеток", chiqish PDF/tizim dialogi orqali (ZPL/TSPL tilga olinmaydi); Poster — faqat PDF (oddiy printer), "Термопринтер кассы Poster для печати ценников не используется". BILLZ/Smartup — ommaviy hujjat topilmadi. Bozor amaliyoti — **drayver/PDF orqali chop etish**, xom til emas.
5. **Server PDF zahirasi chastotasi:** asosiy yo'l (brauzer + drayver) barcha bozor printerlarida ishlagani uchun server PDF faqat quyidagi holatlarda kerak: (a) iOS/Safari (drayverli yorliq printeriga to'g'ridan-to'g'ri yo'l yo'q) va A4 varaq tartibi; (b) ommaviy chop etish (masalan narx o'zgarishidan keyin yuzlab yorliq — brauzerni bloklamaslik uchun); (c) brauzer renderida shtrix-kod o'qilmasa. Aniq foiz manbada yo'q — **past ustunlik (§5 dagidek) to'g'ri**; o'lchov: `outbox_jobs(kind="label_pdf")` / brauzer chop etishlari nisbati pilotda yig'iladi.

**Dalil.** Narxlar (2026-10-16): https://uzum.uz/ru/product/termoprinter-etiketok-i-952771 (XP-365B 499 990), https://asaxiy.uz/ru/product/termoprinter-dlya-chekov-xprinter-xp-365b (649 000), https://regos.uz/ru/market/torgovoye-oborudovaniye/label-printers (620 000), https://asaxiy.uz/ru/product/termoprinter-dlya-chekov-xprinter-xp-420b-black (969 000), https://uzum.uz/ru/product/termoprinter-etiketok-i-1124498 (XP-470B 1 079 990), https://asaxiy.uz/ru/product/printer-etiketok-godex-g500 (2 229 000), a-one.uz (TSC TE200 2 583 000; Zebra ZD220d 3 875 000), https://mertech.uz/termoprinter-etiketok-mertech-dt80-ethernet-usb-rs-232-ru/ (1 768 400); lentalar: https://uzum.uz/ru/product/termoetiketki-58kh40-mm-2346259 va boshqa Uzum sahifalari (sharhlar soni 1 180 gacha). Tillar: https://www.xprintertech.com/xp-365b-xp-365bm-3-inch-label-printer , https://www.xprintertech.com/xp-420b.html , zebra.com ZD220 spec sheet, labelinn.com (TSC TE200). Raqobatchilar: support.moysklad.ru ("Как сделать ценники и этикетки в МоемСкладе"), https://knowledge-base.joinposter.com/ru/how-to-connect-and-set-up-price-tag-printing-in-poster .

**Ishonch:** Yuqori (bozor lideri, tillar, o'lchamlar, raqobatchi amaliyoti); o'rta — Godex tillari, Atol BP21/HPRT narxi, BILLZ amaliyoti (tasdiqlanmagan); PDF chastotasi — sifatiy xulosa, raqam emas.

**Spec'ga ta'sir (taklif):**
- `25-nofunksional-talablar.md` §7.4 "Narx va aniq protokol tadqiqotda **topilmadi** … Umumiy o'lcham taxmin (58×40 mm) — manba yo'q." → **"Bozor standarti — Xprinter XP-365B (TSPL + ESC/POS, ZPL yo'q; 499 990–649 000 so'm, Uzum/Asaxiy/REGOS, 2026-10-16); 4 dyuymli XP-420B/470B (TSPL/ZPL/EPL) 0,97–1,08 mln; Zebra/TSC/Godex 1,9–3,9 mln. Barchasida Windows drayveri bor. Ommaviy lentalar: 58×40, 58×30, 43×25, 40×30, 30×20 mm (Uzum). Manba: P6 OQ-062."**; §OS5/OS-band 5 "yorliq printeri protokoli … topilmadi" → yopildi.
- `03-modullar-talablari.md` US-M09-04 (376-qator): "Bir nechta o'lcham (masalan 58×40 mm); yorliq printeri protokoli — **ochiq savol**" → **"Standart o'lchamlar: 58×40 (asosiy narx yorlig'i), 58×30, 43×25, 40×30, 30×20 mm va A4 varaq (oddiy printer uchun). Chop etish — brauzerda (HTML/SVG + `bwip-js`, CSS `@page { size: Wmm Hmm; margin: 0 }`) tizim drayveri orqali; xom TSPL/ZPL — MVP'da yo'q (kelajakda TSPL birinchi — XP-365B/420B/470B/TSC qamrovi, ZPL ikkinchi)."**
- `19-api-ombor.md` §5 `GET /label-templates`: "standart shablonlar (58×40mm va h.k., US-M09-04)" → **"standart shablonlar: 58×40, 58×30, 43×25, 40×30, 30×20 mm, A4 (3×8 yoki 4×10 to'r) — 203 dpi uchun shtrix moduli butun nuqtaga (1 nuqta ≈ 0,125 mm) yaxlitlanadi"**; 844-qator OS5 → **"yopildi: server PDF — iOS, A4 va ommaviy (≥ N yorliq, sozlanadi) chop etish uchun; asosiy yo'l brauzer; nisbat pilotda o'lchanadi"**.
- `24-frontend-arxitekturasi.md` §6 jadval "Chop etish (A4, yorliq) | react-to-print" — o'zgarmaydi, qo'shimcha: **"yorliq printeri foydalanuvchi tomonidan drayverda bir marta mos qog'oz o'lchamiga sozlanadi (onboarding yo'riqnomasi)"**.
- `25` §7.3/§7.4 ga lenta narxi qatori (58×40 ~13 500 so'm/rulon) — unit-iqtisod uchun ixtiyoriy.

**Holat: YOPILDI** (protokol strategiyasi, o'lchamlar va narxlar manbali; PDF chastotasi raqami pilotda o'lchanadi, bloklamaydi).

## OQ-077 — Vision-LLM (AI-03) aniq narxi, rasm-boshiga token

**Javob.**
1. **Rasm tokeni formulasi (rasmiy):** rasm 28×28 px "patch"larga bo'linadi — `token = ⌈kenglik/28⌉ × ⌈balandlik/28⌉`. Eski `kenglik×balandlik/750` formulasi va "~1,15 MP" chegarasi **endi amal qilmaydi**. Har model uchun ikki chegara: **Claude 4.7 va undan keyingi modellar (Haiku 5.5, Sonnet 5.5 ham) — "high-resolution" daraja: uzun tomon ≤ 2576 px, ≤ 4784 vizual token**; eski modellar — 1568 px / 1568 token. Chegaradan oshsa avtomatik kichraytiriladi (nisbat saqlanadi).
2. **Bizning 2048 px siqish (26 A#28) bilan haqiqiy token soni:** 2048×1536 (4:3) → 74×55 = **4070 token**; 1448×2048 (A4 portret) → 52×74 = **3848 token**; 2048×2048 → limitga qisqartiriladi ≈ **4784 token**. Ya'ni spec'dagi "≈1500 token/rasm" taxmini **2,5–3 baravar past**. 1500 token darajasiga tushish uchun rasmni ~1092×1092 (1521 token) ga, 2350 token uchun 1568×1176 ga kichraytirish kerak (o'qilishi pilotda tekshiriladi).
3. **Joriy narxlar (rasmiy, 2026-10-16):**

| Model (API ID) | Kirish $/MTok | Chiqish $/MTok | Kesh yozish 5m / 1h | Kesh o'qish | Batch (−50%) kirish/chiqish |
|---|---|---|---|---|---|
| Claude Haiku 5.5 (`claude-haiku-5-5`), prompt ≤ 100 000 token | 0,10 | 0,50 | 0,125 / 0,20 | 0,01 (0,1×) | 0,05 / 0,25 |
| Claude Haiku 5.5, prompt > 100 000 token | 0,50 | 2,50 | 0,625 / 1,00 | 0,05 | 0,25 / 1,25 |
| Claude Sonnet 5.5 (`claude-sonnet-5-5`) | 2 | 10 | 2,50 / 4 | **0,10 (0,05×)** | 1 / 5 |
| Claude Sonnet 5 (`claude-sonnet-5`) | 2 | 10 | 2,50 / 4 | 0,20 | 1 / 5 |
| Claude Haiku 4.5 (legacy) | 1 | 5 | 1,25 / 2 | 0,10 | 0,50 / 2,50 |

   - Haiku 5.5 dagi "$0,10–0,50" diapazoni **hajmga (oylik sarfga) emas, bitta so'rovning prompt uzunligiga** bog'liq: prompt > 100 000 token bo'lsa butun so'rov yuqori narxda. Bizning AI chaqiruvlarimiz (≤ 6 000 token) doim pastki narxda.
   - Barcha joriy modellar (Haiku 5.5 ham) **rasm kirishini qo'llab-quvvatlaydi** ("Input → output: Text and images → text"). Spec'dagi "matn-faqat model vision qila olmaydi" (22 §2 jadval AI-03) — Haiku 5.5 uchun noto'g'ri.
   - Haiku 5.5 va Sonnet 5.5 yangi tokenizatorda (Claude 4.7+): bir xil matn Haiku 4.5'ga nisbatan ~30% ko'proq token — spec'dagi matn token taxminlari (3000/500 va b.) shu sababli ~1,3× oshishi mumkin.
4. **USD→UZS:** CBU rasmiy kursi **1 USD = 12 011,65 so'm (2026-10-16)**; 2026-10-01 da 11 808,76. Spec'dagi 12 500 — konservativ (≈4% yuqori), konfiguratsiya sifatida qoldirsa bo'ladi; hisob-kitobda joriy CBU kursi ishlatildi.
5. **AI-03 bitta rasm narxi** (4070 rasm tokeni + ~300 matn prompti kirish, 400 chiqish):
   - Sonnet 5.5: (4370×2 + 400×10)/1e6 = **$0,01274 ≈ 153 so'm/rasm** (spec taxmini 1800+400 bilan $0,0076 edi — ~1,7× qimmat).
   - Haiku 5.5: (4370×0,10 + 400×0,50)/1e6 = **$0,00064 ≈ 7,7 so'm/rasm** (~20× arzon).
6. **22 §13 jadvali qayta hisobi** (boshqa funksiyalar token taxminlari o'zgarmagan, kurs 12 011,65):

| Daraja | AI-03 Sonnet 5.5 bilan: jami USD / so'm / tarifdan % | AI-03 Haiku 5.5 bilan: jami USD / so'm / % |
|---|---|---|
| Yengil (AI-03 = 0) | $0,058 / **698 so'm** / 0,7% | xuddi shu |
| O'rta (15 rasm) | $0,488 / **5 856 so'm** / 5,9% | $0,306 / **3 675 so'm** / 3,7% |
| Og'ir (50 rasm) | $1,504 / **18 060 so'm** / 18,2% | $0,898 / **10 791 so'm** / 10,9% |

**Dalil.**
- Narx: https://platform.claude.com/docs/en/about-claude/pricing (Model pricing, Batch processing, Long context pricing bo'limlari; 2026-10-16). Sitata: "Claude Haiku 5.5 is priced by prompt length: a request whose prompt is over 100,000 tokens pays higher prices."; "Cache hits and refreshes on Claude Opus 5.5 and Claude Sonnet 5.5 are priced at 0.05x the base input price."
- Model: https://platform.claude.com/docs/en/models/haiku-5-5/overview (chiqarilgan 2026-10-07; "Input → output: Text and images → text"; "~30% more tokens than on Claude Haiku 4.5"); https://platform.claude.com/docs/en/about-claude/models/overview ("All current models support text and image input … vision").
- Vision: https://platform.claude.com/docs/en/build-with-claude/vision — "An image, therefore, costs `⌈width / 28⌉ × ⌈height / 28⌉` visual tokens."; jadval "High-resolution | Claude 4.7 and later models | 2576 px | 4784"; rasm ≤ 10 MB (API), ≤ 8000×8000 px, JPEG/PNG/GIF/WebP; >20 rasmli so'rovda har rasm ≤ 2000 px.
- Kurs: https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/2026-10-16/ → `"Rate":"12011.65","Date":"16.10.2026"`.

**Ishonch:** Yuqori (rasmiy narx/hujjat sahifalari, bir kunda tekshirildi). Hajm (so'rovlar soni) va matn token taxminlari — hamon taxmin (pilot `ai_requests`).

**Spec'ga ta'sir (taklif):**
- `26-ochiq-savollar-reestri.md` A#18: "Rasm ≈ 1500 token ekvivalenti" → **"Rasm tokeni = ⌈w/28⌉×⌈h/28⌉ (Claude 4.7+ modellarda ≤ 4784 token, uzun tomon ≤ 2576 px); 2048 px siqishda ≈ 3 850–4 800 token/rasm. Manba: platform.claude.com/docs/en/build-with-claude/vision (2026-10-16)."** — holat "yopildi".
- `22-ai-qatlami.md` §2 (model routing, 11-qator) va `09-ai-funksiyalar.md` 16/34/103/168-qatorlar: "Claude Haiku 5.5 ($0,10–0,50 kirish / $0,50–2,50 chiqish, 1M tok, hajmga qarab)" → **"Claude Haiku 5.5 (`claude-haiku-5-5`, $0,10 kirish / $0,50 chiqish per 1M token, prompt ≤ 100 000 token bo'lganda; undan uzun promptda $0,50/$2,50; kesh o'qish $0,01; Batch −50%)"**.
- `22-ai-qatlami.md` §2 jadval AI-03 qatori: "Sonnet 5.5 (vision-capable) | Har doim — matn-faqat model vision qila olmaydi | … **narx taxmin** — alohida vision-narx rasmiy sahifada yo'q" → **"Haiku 5.5 standart (vision qo'llab-quvvatlanadi), ishonch < chegara bo'lsa Sonnet 5.5 ga eskalatsiya | Rasm narxi = vizual token × kirish narxi (`⌈w/28⌉×⌈h/28⌉`, ≤ 4784) — rasmiy"**. (Haiku 5.5 aniqligi AI-03 chegaralariga (summa ≥95% va b.) pilotda tekshiriladi — o'tmasa Sonnet 5.5 qoladi.)
- `22-ai-qatlami.md` §6 band 2: "kesh o'qish ~0,1×" → **"kesh o'qish: Haiku 5.5 — 0,1×, Sonnet 5.5/Opus 5.5 — 0,05× (model jadvalidagi qiymat, konstanta emas)"**; band 3: `FX_USD_UZS = 12 500` (taxmin) → **"12 500 (konservativ; CBU 2026-10-16: 12 011,65 — https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/)"**; tavsiya: kursni CBU JSON API'dan kunlik olish.
- `22-ai-qatlami.md` §13 jadval: AI-03 qatori "1800 + 400" → **"4 070 rasm + 300 matn + 400 chiqish"**; natijalar yuqoridagi 6-banddagi jadval bilan almashtiriladi; OS1 o'chiriladi (yopildi).
- `09-ai-funksiyalar.md` OS1 va 62-qator ("aniq vision-narx … **taxmin**") → yopildi, manba — vision hujjati.
- `25-nofunksional-talablar.md` §11 AI qatori "~2 000–5 000 so'm" → **"~700–5 900 so'm (yengil–o'rta), og'ir tenant ~10 800–18 100 so'm"**.
- `26-ochiq-savollar-reestri.md` A#28 ("AI-03 rasm yuborishdan oldin max 2048px'ga siqiladi") — o'zgarmaydi, lekin qo'shimcha: **AI-03 uchun 1568 px (≈2 350 token) varianti pilotda A/B qilinadi** (narxni ~42% kamaytiradi).

**Holat: YOPILDI** (narx va token formulasi manbali; hajm taxminlari pilotga qoladi — bu OQ-077 doirasidan tashqari, 22 OS2).
