# Ekranlar va UX — veb-kassa (POS) va Back-office PWA

**Maqsad:** veb-kassa (POS, PWA) va Back-office PWA'ning 41 ekranini (rol, modul, maqsad, asosiy elementlar, holatlar), umumiy UX qoidalarini, navigatsiyani va asosiy oqimlarni belgilash.
**Kim uchun:** frontend ishlab chiquvchilar, UX/dizayn tizimi.
**Bog'liq fayllar:** `01-qarorlar.md`, `07-ekran-tafsilotlari.md`, `08-dizayn-tizimi.md`, `03-modullar-talablari.md`, `24-frontend-arxitekturasi.md`, `33-1c-integratsiya.md` (§13).
**Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. Ikki interfeys: **veb-kassa (POS, PWA)** (asosan Kassir, qisman Omborchi — skanerlash vazifalari; Android Chrome/planshet/PK) va **back-office PWA** (Egasi, Menejer, Buxgalter, qisman Omborchi). Kotlin Android POS ilovasi — MVP'dan keyin, xuddi shu POS-nn ekranlari bilan (`28-android-pos.md`).
2. **Jami 41 ekran** (16 ta POS-nn, 24 ta BO-nn, 1 ta ADM-nn) — 19 modulning har biri kamida bitta ekranga ega (pastdagi 3- va 4-bo'lim jadvallari). MVP'da 39 ta (POS-16 «Uskunalar sozlamasi» va BO-24 «Bank tushumi tasdig'i» — M11, qaror #42 — shu jumladan); **BO-22, BO-23 — M19 «1C integratsiyasi», MVP'dan keyin, Bosqich 7** (`33-1c-integratsiya.md` §13).
3. **Offline indikatori majburiy va har bir POS ekranining status panelida bir xil joyda** turadi — offline holatda birinchi chek 48 soat ichida OFD'ga yetishi shart bo'lgani uchun (`research_notes/texnik/02-kassa-ofd-markirovka.md`, 1-bo'lim: 943-son qaror, 1-ilova, 31-band), kassir doim qancha chek sinxronlanmaganini va vaqt chegarasigacha necha soat qolganini ko'rishi kerak. 48 soatda kassa yangi fiskal chek chiqarmaydi (qaror #43, 1.3-bo'lim).
4. **Bir qo'l bilan ishlash** — POS asosiy ekranlarida barcha harakat tugmalari ekranning pastki yarmida, katta teginish maydoni bilan joylashtiriladi (POS tugmasi kamida 48×48 dp, asosiy tugmalar 56 dp — 26 #13); raqamli summa kiritish va to'lov tasdiqlash bosh barmoq zonasida.
5. **Asl belgisi markirovkasi skanerlash xatosi — yuqori ehtimolli muammo**: manba (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 6-band) bu raqamni **yetkazib berish zanjiridagi yuklarning 80–90%i skanerlash xatosi bilan qaytishi** sifatida beradi (yuk/partiya darajasida — har bir kassadagi yakka skanerlash urinishining xato ehtimoli emas). Shunga qaramay, bu umumiy nosog'lom holatni ko'rsatadi, shuning uchun har bir skanerlash ekranida majburiy "qayta urinish" va eskalatsiya yo'li UX darajasida ko'zda tutiladi (1.7-bo'lim) — qo'lda **MXIK** (tovar klassifikator kodi) kiritish mumkin; **DataMatrix (markirovka) kodini** qo'lda kiritish — faqat online, tekshiruv va audit bilan (26 #14). Markirovka kodi Asl belgisiga fiskal chek ichida OFD orqali boradi (qaror #62).
6. **O'zbek (lotin) — asosiy til, rus — ikkinchi til**; til almashtirish tugmasi barcha ekranlarning yuqori panelida bir xil joyda. Fiskal chek — ikki tilli (o'zbek/rus), har doim (qaror #29, 1.4-bo'lim).
7. **Uskunalar**: shtrix-kod skaneri ko'pincha USB HID "Keyboard Wedge" rejimida ishlaydi (qo'shimcha drayversiz, klaviatura kabi), chek printerlari ESC/POS protokolida (`research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`, 3-bo'lim) — bu UI'da "skaner fokus maydoni" va "chekni qayta chop etish" tugmasi sifatida aks etadi. Printer, tarozi va skaner kassa qurilmasida POS-16 ekranida sozlanadi. Tarozi tovari asosan EAN-13 og'irlik yorlig'i orqali sotiladi; **qo'lda og'irlik kiritish** — doimiy zahira (1.6-bo'lim).
8. **Davlat hisobotini solishtirish** (BO-10) — 2026 yildagi eng markaziy yangi ekran: har bir soliq turi uchun alohida **5 ish kunlik** hisoblagich (hisobot topshirish muddatidan kechiktirmay; Soliq kodeksi 5-modda 7-qism, 81-moddasi, O'RQ-1108, lex.uz/docs/-7944527) va qator darajasidagi farq ko'rsatuvi.
9. **AI yordamchi chat** (BO-13) — "kod hisoblaydi, AI tushuntiradi" tamoyili asosida: javobdagi raqam har doim backend hisob-kitobidan, AI faqat o'zbek tilida tushuntirish matnini yozadi (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim).
10. Teginish/vaqt parametrlari — 26 #13 standarti (tugma o'lchami, chek ekranining 5 soniyada qaytishi); offline ogohlantirish bosqichlari — qaror #43; qolgan tezlik maqsadlari — umumiy tamoyil ("kam teginish, kam skroll").
11. **1C integratsiyasi** (Bosqich 7): BO-22 — kompyuterni ulash, bazani tekshirish, filial bog'lash, ERP ↔ 1C moslashtirish ustasi; BO-23 — kun preview'i, tayyorlik, «1C ga yuborish», progress va kalendar; BO-14 «Integratsiyalar holati»ga «1C» qatori; ERP hujjat ekranlarida «1C da» belgisi (1.8-bo'lim). Telegram'da tasdiqlash tugmasi yo'q — faqat BO-23 havolasi.

---

## 1. UX qoidalari (umumiy, barcha ekranlarga tegishli)

### 1.1 Tezlik
- Sotuv cheki — kamida teginish sonini minimal qilish: mahsulot qo'shish → chegirma (ixtiyoriy) → to'lov → chek. To'rt qadamdan oshmasligi maqsad qilinadi (ichki UX maqsadi).
- Tugma o'lchami: POS — kamida 48×48 dp, asosiy tugmalar 56 dp; mobil back-office — 44×44 dp. Chek ekrani chop etish/QR muvaffaqiyatli bo'lgandan 5 soniya keyin asosiy holatga qaytadi (printer xatosida qaytmaydi) — 26 #13.
- Qidirish maydonlari avtomatik fokusda, skaner natijasi qo'shimcha tasdiqlashsiz ro'yxatga qo'shiladi.

### 1.2 Bir qo'l bilan boshqarish
- POS ekranlarida asosiy harakat tugmalari (TO'LOV, BEKOR, CHEGIRMA, SKANERLASH) pastki 40% zonada, katta o'lchamda.
- Raqamli klaviatura (summa, miqdor kiritish) ekran markazida, bosh barmoq bilan yetadigan joyda.
- Ko'p bosqichli dialog (masalan, tasdiqlash oynasi) o'rniga pastdan chiqadigan panel (bottom sheet) afzal — ikkinchi qo'l bilan ushlab turish shart bo'lmasin.

### 1.3 Offline indikatori (majburiy, har bir POS ekranida)
- Status panelida doimiy ko'rinadigan holatlar (hisob — shu kassada OFD tasdig'ini olmagan eng eski fiskal chekning `created_at`idan; qaror #43):
  - 🟢 **Onlayn** — kutilayotgan chek yo'q.
  - 🟡 **Offlayn** (sinxronlanmagan N chek) — 24 soatdan boshlab sariq ma'lumot.
  - 🔴 **Offlayn, muddat yaqin** — 40 soatdan qizil; Egasiga M18 (Telegram) xabari ketadi. 46 soatdan har yangi chek oldidan yopib bo'lmaydigan modal: "2 soatdan keyin kassa bloklanadi — internetga ulaning" ("Tushundim" bilan yopiladi, sotuvni to'xtatmaydi).
  - ⛔ **Bloklangan** — 48 soat o'tdi: yangi fiskal chek (sotuv, qaytarish, qarz to'lovi, kredit cheki) chiqarib bo'lmaydi (`FISCAL_OFFLINE_48H_BLOCKED`); faqat sinxron/"Qayta yuborish", qoldiqni ko'rish, smenani yopish va naqd sanash ishlaydi. Barcha kutilayotgan cheklar OFD tasdig'ini olgach blok avtomatik yechiladi; qo'lda chetlab o'tish yo'q. Blok `audit_log` ga yoziladi va Egasiga M18 xabari ketadi (VMQ-943 2-ilova 6-band).
- Offlayn holatda markirovkalangan tovar sotiladi: kod chek ichida saqlanadi va chek bilan OFD orqali Asl belgisiga ketadi (qaror #62), qatorda "fiskal-pending" belgisi; narx qurilmada ma'lum bo'lmasa — "Offlaynda sotib bo'lmaydi, narx noma'lum" (taqiqlangan), `03-modullar-talablari.md` M01 Offline xatti-harakati.

### 1.4 Til (o'zbek/rus)
- Standart til — o'zbek (lotin). Til almashtirish — yuqori o'ng burchakda bir xil almashtirgich «UZ · RU» barcha ekranlarda.
- (qaror #29) **Chek tili — ikki tilli (bilingual) qator**: fiskal chek (shu jumladan QR orqali elektron chek) **o'zbek (lotin) va rus tilida bir vaqtda** chiqariladi — har bir tovar qatorida ikki nom "o'zbekcha / ruscha" formatida ko'rsatiladi (masalan "non / хлеб"), rus nomi (`products.name_ru`, ixtiyoriy) kiritilmagan tovarlarda faqat o'zbekcha nom ko'rsatiladi. Chekning sarlavha/yakun matnlari (masalan "Jami" / "Итого", "Naqd" / "Наличные", "Qaytim" / "Возврат") ham ikki tilda chiqariladi; fiskal rekvizitlar (OFD talab qilgan maydonlar — STIR, MXIK, QQS, fiskal belgi) OFD talab qilgan formatda, o'zgarmaydi. Davlat tili talabi buzilmaydi, chunki o'zbekcha qator har doim birinchi va mavjud. Interfeys (UI) tili almashtirish tugmasi (yuqorida) bundan mustasno va mustaqil — u faqat ekran matnini almashtiradi, chekka ta'sir qilmaydi. Batafsil shablon — `08-dizayn-tizimi.md`, chek shabloni bo'limi; maydon — `07-ekran-tafsilotlari.md`, BO-05 (`nameRu`).

### 1.5 Katta shrift va kontrast
- Narx va summa raqamlari — ekrandagi eng katta shrift (do'kon yorug'ligi/charchagan ko'z uchun, **taxmin**: boshqa matndan kamida 1.5x katta).
- Yuqori kontrast ranglar (oq fonda qora/to'q ko'k matn), skaner xatosi — qizil, muvaffaqiyat — yashil belgilar bilan.

### 1.6 Uskunalar: skaner, tarozi, printer
- **Shtrix-kod/markirovka skaneri**: USB HID keyboard-wedge rejimi — har qanday matn kiritish maydoni skanerlash natijasini qabul qiladi, lekin asosiy sotuv ekranida alohida "faol skaner maydoni" ajratiladi, shunda tasodifiy boshqa maydonga tushib ketmaydi (`06-fayl`, 3-bo'lim).
- **Chek printeri (ESC/POS)** — ulanish yo'li kassa qurilmasida **POS-16** da tanlanadi va tekshiriladi (test chek):
  - **Web Serial / WebUSB** — desktop Chrome/Edge va Chrome Android (Windows'da WebUSB uchun WinUSB drayveri kerak bo'lishi mumkin); **Web Bluetooth** — faqat BLE printerlar (klassik Bluetooth SPP ishlamaydi);
  - **LAN printer (xom TCP 9100)** — brauzerdan to'g'ridan-to'g'ri ishlamaydi, faqat do'kon kompyuteridagi **Do'kon agenti** orqali (qaror #60); HTTP qabul qiluvchi printerlar (Epson ePOS-Print, Star WebPRNT) — brauzerdan;
  - **tizim printeri** (OS drayveri) — zahira;
  - **bulut printer** — Star TSP143IV (CloudPRNT), Epson TM-m30III (Server Direct Print); Toshkentda ~5,1–7,1 mln so'm.
  - Kodlash: kod sahifasi cp866; o'zbek kirill harflari (Қ/Ғ/Ҳ) bo'lsa chek avtomatik **raster** rejimida chop etiladi; U+02BB (ʻ) → `'`.
- **Chek berish siyosati**: standart — **bosma chek**. Elektron chek (ekranda `ofd.soliq.uz` QR havolasi, Telegram yoki SMS havola) faqat zahira — (a) printer ishlamay qolganda yoki (b) xaridor o'zi so'raganda, kassir tasdig'i bilan; `fiscal_receipts.delivery = electronic` va `delivery_reason` audit qilinadi (VMQ-943 1-ilova 2-band — chek elektron shaklda bo'lishi mumkin). "Chekni qayta chop etish" tugmasi har doim mavjud.
- **Tarozi**: (a) **yorliqli tarozi** — asosiy yo'l: tarozi bosgan EAN-13 og'irlik kodi `PP CCCCC VVVVV K` skanerlanadi (PP — do'kon sozlamasidagi prefiks: standart 22 = og'irlik grammda, 21 = summa so'mda; CCCCC — PLU; K — nazorat raqami), protokol kerak emas; PLU ro'yxati tarozi dasturiga CSV orqali yuklanadi; (b) **yorliqsiz kassa tarozisi** — desktop Chrome/Edge'da Web Serial orqali jonli og'irlik — MVP'dan keyin; (c) **qo'lda og'irlik kiritish** — doimiy zahira, avtomatik qiymat kelganda oldindan to'ldiriladi.
- **Yorliq printeri** (BO-18): brauzerdan tizim drayveri yoki PDF orqali chop etiladi; xom TSPL/ZPL MVP'da yo'q.
- **iPhone/iPad (iOS)** (qaror #21): kassa/back-office iOS'da **o'rnatilgan PWA** sifatida (Home Screen'ga qo'shilgan) ishlaydi; iOS Safari USB/Bluetooth printer ulanishini qo'llab-quvvatlamaydi va Do'kon agentiga yeta olmaydi. Fiskal chek iOS'da faqat fiskal hamkor bulut rejimi bo'lsa mumkin; aks holda iOS — back-office va bulut printer, printer bo'lmasa elektron chek zahirasi (ogohlantirish bilan). **Chrome/Edge (Windows, Android)** — yuqoridagi barcha yo'llar.

### 1.7 Markirovka (Asl belgisi) maxsus holati
- Manbada keltirilgan 80–90% xato ko'rsatkichi **yetkazib berish zanjiridagi yuklar darajasida** (`00-xulosa-va-ochiq-savollar.md`, 6-band), har bir alohida skanerlash urinishining xato ehtimoli sifatida emas (Asosiy xulosalar #5). Shunga qaramay, markirovka skanerlashning umuman nosog'lom ekanligini ko'rsatadi, shuning uchun har bir markirovka skaneri ekranida (POS-02, POS-08, POS-09, POS-10): (a) birinchi urinish muvaffaqiyatsiz bo'lsa avtomatik qayta urinish, (b) 2–3 urinishdan keyin DataMatrix kodini qo'lda kiritish (faqat online, `POST /marking-codes/verify`, audit `marking.manual_entry`); markirovkali tovarni kodsiz sotish taqiqlanadi (offline rejimda qo'lda kiritilgan kod bilan sotish ham taqiqlanadi — 26 #14), (c) kod butunlay o'qilmasa, menejerga eskalatsiya tugmasi ko'rsatiladi.
- **Sotuvda kod qayerga ketadi** (qaror #62): chakana sotuvda markirovka kodi Asl belgisiga **fiskal chek ichida OFD orqali** boradi (fiskal modul offline'da ham imzolaydi); CRPT API faqat qabul, tekshiruv, yetkazib beruvchiga qaytarish va hisobdan chiqarish uchun.
- **Sotuvdan oldingi tekshiruv** — standart `MARKING_PRECHECK=warn`: online bo'lsa kod tekshiriladi, muvaffaqiyatsiz natija sariq ogohlantirish va audit bilan ko'rsatiladi, sotuv davom etadi; tenant BO-14 da `block` rejimini yoqishi mumkin (bunda yaroqsiz kod rad etiladi). **Lokal takror-kod nazorati** har doim (offline ham): bitta chekda bir xil kod yoki tenantda avval sotilgan kod — qator qo'shilmaydi ("Bu kod allaqachon sotilgan"); kodsiz markirovkali qator bilan chek chiqmaydi.
- **Qaytarish** — markirovkalangan tovarni qaytarish faqat online (POS-05).

### 1.8 «1C da» belgisi (hujjat ekranlari, Bosqich 7)
- Tenantda 1C bazasi bog'langan va foydalanuvchida `onec.view` bo'lsa, ERP hujjati ko'rinadigan ekranlarda (sotuv/chek tafsiloti, qaytarish, kirim BO-04, ko'chirish, hisobdan chiqarish, inventarizatsiya, qarz to'lovi BO-06, yetkazib beruvchiga to'lov, xarajat BO-17, kassa pul harakati, bank tushumi BO-24) sarlavha yonida **«1C da» belgisi** (`OnecRefBadge`, `08-dizayn-tizimi.md`) ko'rsatiladi: `1C: ОРП № 0000-000123 ✓` — manba `GET /onec-object-refs` (W-54, `33-1c-integratsiya.md` §10).
- Holatlar: `active` — yashil ✓ (1C raqami bilan); hali yuborilmagan — kulrang «1C ga yuborilmagan»; `changed_in_1c` / `unposted` / `marked_deleted` / `missing_in_1c` — sariq ⚠ (drift, «1C da o'zgartirilgan» va h.k.); jamlangan hujjat (chek ОРП ichida) — ОРП raqami ko'rsatiladi. Belgi bosilsa — BO-23 shu kun partiyasi.
- 1C bog'lanmagan tenant yoki `onec.view` yo'q — belgi umuman chizilmaydi.

### 1.9 Back-office navigatsiyasi (sidebar)
Sidebar (`08-dizayn-tizimi.md` §6.2) — to'q fon; tepada «ERP» logotipi va do'kon nomi, so'ng ikonkali menyu guruhlari, pastda foydalanuvchi kartasi (avatar, ism, rol; bosilganda — chiqish; til almashtirish — topbar'da, 1.4-bo'lim). Har punkt ruxsat bo'yicha ko'rinadi (ruxsat yo'q — punkt yo'q; guruhda birorta punkt qolmasa — guruh sarlavhasi ham yo'q). Joriy sahifa punkti fon bilan ajratiladi.

| Guruh | Punktlar (ekran) |
|---|---|
| ASOSIY | Dashboard (BO-02); AI yordamchi (BO-13); Tasdiqlash navbati (BO-16) — punktda kutilayotgan so'rovlar soni badge'i (`GET /api/v1/approval-requests?status=pending`, foydalanuvchining `*.approve` huquqiga mos `kind`lar) |
| SAVDO | Kassa (POS) — veb-kassani ochadi (`/pos/login`, POS-01; foydalanuvchida POS ruxsati bo'lsa — masalan `sales.create`); Qarzdorlar (BO-06); Tovarlar va narxlar (BO-05) |
| OMBOR | Qoldiq va ko'chirish (BO-03); **Tovarlar** — tovarlar katalogi (`/app/catalog/products`; tovar kartasi va import shu punkt ostida, `19` §1–§3): `stock.view` bilan ko'rinadi (ro'yxat `GET /api/v1/products` shu huquqni talab qiladi, `19` §1) — narx huquqi yo'q foydalanuvchi (masalan omborchi) tovarlar ro'yxatiga shu punkt orqali kiradi; `catalog.manage` faqat tahrirlash va import huquqini qo'shadi, o'zi bilan punktni ko'rsatmaydi; Xaridlar (BO-04); Yorliqlar (BO-18) |
| MOLIYA | Xarajatlar (BO-17); **Bank tushumi (BO-24)**; E-faktura (BO-15); QQS va davlat hisoboti (BO-10; QQS ichki hisob-kitobi BO-07 — shu bo'lim ichidagi tab/havola; punkt `tax.vat.view` egasiga BO-07 «QQS ichki hisobi» tabini, qolganlarga BO-10 ni ochadi) — punktda «Farq topildi» holatidagi davlat hisobotlari soni badge'i (`GET /api/v1/state-reports?status=diff_found`, `tax.vat.view`); Buxgalteriya (BO-08) |
| BOSHQARUV | Hisobotlar (BO-09); **1C integratsiyasi** (Bosqich 7) → BO-23 «1C ga yuborish» — `onec.view`; 1C bazasi hali ulanmagan bo'lsa ham ko'rinadi (bo'sh holat → BO-22 ga havola); sarlavha chipida agent holati 🟢/🟡/🔴/⚪; Sozlamalar (BO-14) — ichki tablarining birortasi ruxsatini beruvchi huquq bilan ko'rinadi (`notifications.manage` ham), punkt foydalanuvchiga ruxsat etilgan **birinchi** tabni ochadi (`@shared/lib/settings-tabs`) |

**Sozlamalar ichki tablari** (sidebar'da alohida punkt emas): Do'kon (BO-14), Xodimlar (BO-11), Filiallar (BO-12), Telegram (BO-20), Obuna (BO-19), **1C (BO-22)** — `onec.view`. Har tab o'z route'iga ega (`07-ekran-tafsilotlari.md`), aktiv sidebar punkti — «Sozlamalar».

**Yuqori panel (topbar)** — barcha BO ekranlarida (BO-01, BO-21 dan tashqari) bir xil: chapda sahifa sarlavhasi (ekran nomi, ID'siz); o'ngda (1) **qidiruv** maydoni — `Ctrl+K` buyruq paneli (`cmdk`, `08-dizayn-tizimi.md` §9): tovar (`GET /api/v1/products?search=`), kontragent/mijoz (`GET /api/v1/counterparties?search=`) va ekranlar bo'yicha navigatsiya, natijalar ruxsat bo'yicha filtrlanadi; (2) **filial tanlovi** (`Select`: foydalanuvchiga biriktirilgan filiallar + bir nechta filialga kirishi bo'lsa «Barcha filiallar» — konsolidatsiya; tanlov ekran filtrlari uchun standart qiymat bo'ladi); (3) **bildirishnomalar** ikonkasi — ogohlantirishlar ro'yxati (BO-02 «Diqqat talab qiladi» bloki bilan bir manba: `GET /api/v1/reports/dashboard` → `alerts[]`; `reports.sales.view` yo'q foydalanuvchida ikonka ko'rinmaydi), har ogohlantirish tegishli ekranga havola; (4) **til almashtirish** «UZ · RU» (1.4-bo'lim). Obuna `grace` banneri topbar ustida (`07-ekran-tafsilotlari.md`, «Qanday o'qish kerak»).

Route'lar — `07-ekran-tafsilotlari.md` va `24-frontend-arxitekturasi.md` §1.1.

---

## 2. Rollar va platforma xaritasi

| Rol | Asosiy platforma | Qo'shimcha platforma | Izoh |
|---|---|---|---|
| **Kassir** | Veb-kassa (POS) | — | Kundalik ish — faqat kassa ilovasi, BO'ga kirish kerak emas |
| **Omborchi** | Veb-kassa (POS, skaner rejimi) | Back-office PWA (ombor hisobotlari) | Kirim, ko'chirish, inventarizatsiya — skaner bilan POS ekranlarida; qoldiq ko'rish — back-office |
| **Menejer** | Back-office PWA | Veb-kassa (narx tekshirish, tezkor nazorat) | Narx, xarid, nasiya, hisobotlarni boshqaradi |
| **Buxgalter** | Back-office PWA | — | QQS, buxgalteriya, davlat hisobotini solishtirish |
| **Egasi** | Back-office PWA (dashboard) | — | Mobil brauzerda ham ochiladi (PWA, responsive), alohida ilova emas |

(qaror #21) Back-office PWA (va Egasi dashboard) iPhone/iPad'da ham **o'rnatilgan PWA** sifatida (Home Screen) ishlaydi; kassa funksiyasida chek chop etish uchun qurilma/printer cheklovlari — 1.6-bo'lim.

---

## 3. Veb-kassa ekranlari (POS-nn)

| ID | Rol | Modul | Maqsad | Asosiy elementlar | Holatlar |
|---|---|---|---|---|---|
| POS-01 | Kassir | M01 | Kassaga kirish, smena ochish | Login/PIN, kassa/filial tanlash, "Smena ochish" tugmasi, boshlang'ich naqd summa kiritish; (qaror #34) "PIN/parolni unutdim" havolasi — OTP orqali tiklash, kod birinchi navbatda **Telegram bot**ga, Telegram ulanmagan bo'lsa **SMS** (zaxira) ga yuboriladi | Bo'sh: boshlang'ich holat; Xato: PIN noto'g'ri, kassa band; **Obuna muddati tugagan**: tenant `restricted` holatida — login butunlay rad etiladi, "Obuna muddati tugagan" xabari, Click/Payme to'lov havolasi va (qaror #20, #34) "Ma'lumotlarimni yuklab olish" (Telegram bot/zaxira SMS kod bilan tasdiqlangan eksport) havolasi ko'rsatiladi (US-M17-03); shu holatda ham, lokautdan oldin yaratilgan, hali yuborilmagan cheklar fon rejimida (`sync.drain`) OFD'ga yuborilishda davom etadi — kassir ekranida ko'rinmaydi, yangi sotuv ochilmaydi (qaror #19); Offline: PIN lokal tekshiriladi (agar qurilma litsenziyasi muddati o'tmagan bo'lsa), keyin sinxronlanadi — litsenziya muddati o'tgan bo'lsa qurilma mahalliy qulflangan bo'ladi |
| POS-02 | Kassir | M01, M03, M09 | Asosiy sotish paneli — mahsulot qo'shish, chegirma, jami summa | Skaner/qidiruv maydoni (skaner har doim faol — tanlangan ko'rinish va kategoriyadan qat'i nazar), tovar paneli: kategoriya tablari + **kartochka/ro'yxat** ko'rinishi almashtirgichi; chek paneli: mijoz, qatorlar (miqdor/narx, `−`/`+`), oraliq summa, chegirma, QQS, jami; Chegirma, Nasiya, Bekor, "To'lov" tugmalari; "📒 Qarz daftari" (POS-13) | Bo'sh: "Chekni boshlang" holati; Xato: mahsulot topilmadi / markirovka o'qilmadi; Offline: status panel 🟡/🔴 |
| POS-03 | Kassir | M01 | To'lov usulini tanlash va hisoblash | Naqd/**Karta (terminal / terminalsiz)**/**Yagona QR (UzQR)**/Payme/Click/Uzum/Aralash/Nasiya tugmalari. **"Karta" — integratsiyalangan terminal** (qaror #71): kassaga terminal bog'langan bo'lsa summa terminalga avtomatik yuboriladi, 4 qadamli holat ("Summa yuborildi" → "Mijoz kartani tegizadi / PIN" → "Bank javobi" → "Fiskal chek"), terminal holati chipi (Wi-Fi · ulangan / ulanmagan / band), karta niqobi, RRN / tasdiq kodi va karta turi terminaldan keladi (kassir yozmaydi), "Terminalda bekor qilish" / "Qayta yuborish", kutish taymeri; javob noma'lum bo'lsa holat so'rovi, yangi urinish bloklanadi; bank tasdig'idan keyin fiskal chek avtomatik; terminal ishlamasa terminalsiz karta (rekvizitsiz) faqat `card_manual_fallback` siyosati bo'yicha (standart — Menejer/Egasi tasdig'i). Batafsil — `07` POS-03 — (qaror #30) "Nasiya" tanlansa (to'liq yoki aralash) fiskal chek darhol chiqmaydi, nasiya qismi qarz to'langanda chek oladi, qaytim hisoblagichi, "Tasdiqlash". Har qanday to'lov usulida (QR/Click/Payme/Uzum/UzQR/karta) fiskal chekni **bizning kassa** chiqaradi (VMQ-943 1-ilova 6-band; 1a-ilova 2-band); provayderga faqat chek havolasi yuboriladi. **"Karta (terminalsiz)"** — kassaga terminal bog'lanmagan bo'lsa (tasdiqsiz) yoki zaxira sifatida (siyosat bo'yicha) karta to'lovi ilovadan tashqarida, do'konning o'z terminalida qabul qilinadi (qaror #64, #71): ilova faqat summani yozadi va hech qanday karta ma'lumotini so'ramaydi — karta turi, niqob, RRN, tasdiq kodi maydonlari yo'q; ekranda faqat "Karta terminalsiz qabul qilindi" tasdig'i (siyosat talab qilsa — ApprovalDialog); fiskal chek "bank kartalari" to'lov shakli bilan, karta rekvizitlarisiz (26 #178); online va offline'da mavjud. **UzQR**: statik QR (`qr_type=static`, faqat online) — kassir to'lovni qo'lda tasdiqlaydi (ixtiyoriy tranzaksiya raqami bilan); dinamik QR (`qr_type=dynamic`) — `UzqrPort` (API olingunga qadar stub), `provider_tx_id` faqat dinamik QR'da majburiy. Yakka tadbirkor (`tenants.legal_form=sole_proprietor`) uchun QR to'lov to'lov tashkiloti platformasining maxsus QR'i (Click/Payme/Uzum) bilan bajariladi (PQ-247) | Bo'sh: summa 0; Kutish: summa terminalga yuborilgan, bank javobi kutilmoqda; Xato: yetarli naqd yo'q, to'lov tizimi javob bermadi, karta rad etildi (`CARD_DECLINED`), terminal javobi noma'lum (`CARD_OUTCOME_UNKNOWN`), terminal ulanmagan (`CARD_TERMINAL_UNREACHABLE`), terminalsiz karta tasdig'i kerak (`CARD_MANUAL_APPROVAL_REQUIRED`) yoki taqiqlangan (`CARD_MANUAL_NOT_ALLOWED`); ⛔ 48 soat blokida "Tasdiqlash" va karta yuborish o'chiq (`FISCAL_OFFLINE_48H_BLOCKED`); Offline: **UzQR (statik ham — faqat online)/Payme/Click/Uzum to'lovlari o'chirilgan** — onlayn tasdiq (bank/push/Prepare-Complete/webhook) talab qiladi; offlaynda **naqd, integratsiyalangan "Karta" (Do'kon agenti va terminal ishlasa — terminal bankka o'z kanali bilan chiqadi), terminalsiz "Karta" (siyosat tasdig'i kerak bo'lsa — lokal PIN), nasiya** mavjud (qaror #23, #71) |
| POS-04 | Kassir | M01 | Chekni chop etish / elektron chek (zahira) | Standart — bosma chek avtomatik; "Qayta chop etish ('NUSXA' belgisi, audit)", **"Elektron chek"** (QR/Telegram/SMS havola) — faqat printer ishlamasa yoki xaridor so'rasa, sabab tanlanadi (`delivery=electronic`, `delivery_reason`, audit); yangi chek boshlash | Bo'sh: —; Xato: printer ulanmagan/qog'oz tugagan → elektron chek taklifi va POS-16 havolasi; Offline: chek lokal saqlanadi, fiskal modul imzolaydi, OFD'ga yuborish "kutilmoqda" deb ko'rsatiladi |
| POS-05 | Kassir | M02 | Mijozdan tovar qaytarish | Asl chekni qidirish (raqam/QR), qaytariladigan tovar(lar), sabab tanlash, balans/naqd qaytarish | Bo'sh: chek topilmagan; Xato: chek allaqachon qaytarilgan; Offline: oddiy tovar — qaytarish lokal yoziladi, serverga sinxronda tasdiqlanadi; **markirovkalangan tovar — "Qaytarish" tugmasi offline rejimda bloklanadi** ("Qaytarish uchun internet kerak" xabari), faqat online'da mumkin |
| POS-06 | Kassir | M08 | Nasiyaga sotish | Mijoz tanlash/qo'shish, joriy qarz va limit ko'rsatish, to'lov muddati, tasdiqlash; mijoz yuridik shaxs (B2B) bo'lsa — chiquvchi e-faktura avtomatik yaratilishi haqida eslatma (Buxgalter BO-15'da E-IMZO bilan imzolaydi, BP-03) | Bo'sh: mijoz tanlanmagan; Xato: limitdan oshib ketdi — **Menejer PIN/tasdig'i talab qilinadi**, sotuv Menejer tasdiqlamaguncha yakunlanmaydi (`02-rollar-va-ssenariylar.md`ga mos; Menejer uzoqda bo'lsa so'rov BO-16 navbatiga tushadi); Offline: limit oxirgi sinxron ma'lumot asosida tekshiriladi, Menejer PIN'i lokal tasdiqlaydi, server qayta tekshiradi |
| POS-07 | Kassir | M01 | Smena yopish, Z-hisobot | Kunlik savdo jamlanmasi, naqd/karta/nasiya taqsimoti (karta — "integratsiyalangan" va "Karta (terminalsiz)" alohida), "Smenani yopish" | Bo'sh: savdo bo'lmagan; Xato: sinxronlanmagan cheklar bor — ogohlantirish; Offline: Z-hisobot lokal shakllanadi, OFD'ga ulanganda yuboriladi |
| POS-13 | Kassir, Egasi | M08 | Qarz daftari (tezkor) (qaror #30) | Mijoz qidirish (ism/telefon), joriy qarz, oxirgi yozuvlar (sana, summa, tovarlar), "To'lov qabul qilish" (**to'langanda fiskal chek chiqadi**, `debt_settlement`), "Qarz yozish" (fiskal chek **chiqarilmaydi**, `deferred`); bosh ekranda doimiy "📒 Qarz daftari" tugmasi | Bo'sh: qarzdor yo'q; Xato: telefon formati noto'g'ri; Offline: to'liq ishlaydi (lokal baza), sinxron belgisi ko'rsatiladi |
| POS-14 | Kassir | M16 | Kassaga pul qo'yish / kassadan pul olish | Summa, sabab (Egasi oldi / Inkasso / Xarajat / Boshqa), izoh; katta summada Menejer/Egasi PIN | Xato: PIN noto'g'ri; Offline: to'liq ishlaydi |
| POS-15 | Kassir | M16 | Smena yopishda naqdni sanash | Sanalgan naqd, kutilgan naqd, farq, izoh, **shu smenadagi "Karta (integratsiyalangan)" va "Karta (terminalsiz)" jamlari** alohida ko'rsatuvi; keyin POS-07 (Z-hisobot) | Xato: farq bor — izoh majburiy; Offline: to'liq ishlaydi |
| POS-08 | Omborchi | M07 | Yetkazib beruvchidan tovar qabul qilish (kirim) | Xaridnoma tanlash, shtrix-kod/markirovka skaneri, miqdor solishtirish (buyurtma vs kelgan), nomuvofiqlik belgilash; e-ishonchnoma raqami (do'kon Omborchiga EDO operatori orqali bergan, qaror #63); markirovkalangan tovar uchun Asl belgisi qabul xabarnomasi muddati (tovar guruhi bo'yicha: umumiy 3 ish kuni, ayrim guruhlarda 72 soat — ogohlantiradi, bloklamaydi) | Bo'sh: xaridnoma tanlanmagan; Xato: markirovka o'qilmadi (1.7-bo'lim), miqdor mos kelmadi; Offline: skanerlash/sanash lokal davom etadi, lekin **"QABULNI YAKUNLASH" internet talab qiladi** — offline qabul (kirim) voqeasi yo'q |
| POS-09 | Omborchi | M06 | Omborlar orasida tovar ko'chirish | Manba/manzil ombor tanlash, skanerlash, miqdor, tashish usuli (`transport_mode`: avtotransport / qo'lda yoki jamoat transporti), "Yuborish"; **e-TTN ("Ombordan omborga")** holati — avtotransportda majburiy, ko'chirish o'tkazilganda EDO operatori orqali shakllantiriladi (`ettn_ref`), qabul qiluvchi filial tasdiqlaydi (qaror #63) | Bo'sh: ombor tanlanmagan; Xato: qoldiq yetarli emas, e-TTN yuborilmadi; Offline: harakat lokal yoziladi, qoldiq serverda qayta hisoblanadi; markirovkalangan tovar ham offline ko'chirilishi mumkin (ichki ko'chirish CRPT'ga xabar qilinmaydi), lekin avtotransportda tashish e-TTN rasmiylashtirilgandan keyin boshlanadi — "Tashishdan oldin internetga ulaning" ogohlantirishi |
| POS-10 | Omborchi | M05 | Inventarizatsiya — jismoniy sanash | Tovar ro'yxati (hali sanalmagan/sanalgan), skanerlash, qo'lda miqdor kiritish, farq ko'rsatuvi | Bo'sh: sanash boshlanmagan; Xato: tizimda yo'q shtrix-kod; Offline: sanash to'liq lokal, yakunida sinxron |
| POS-11 | Kassir, Omborchi | M09 | Mahsulot va narxni tez qidirish | Qidiruv (nom/kod/shtrix-kod), narx, qoldiq ko'rsatuvi (faqat ko'rish) | Bo'sh: natija yo'q; Xato: —; Offline: oxirgi sinxronlangan narx/qoldiq ko'rsatiladi, "oxirgi yangilanish" vaqti bilan |
| POS-12 | Barcha (tizim) | — | Offline/sinxronizatsiya holati va tafsilotlari | Sinxronlanmagan cheklar/hujjatlar ro'yxati, 48 soat hisoblagichi (24/40/46 soat bosqichlari, qaror #43), "Qayta urinish" tugmasi | Bo'sh: hammasi sinxron; Xato: sinxronizatsiya muvaffaqiyatsiz; ⛔ Bloklangan (48 soat): "Yangi chek chiqarib bo'lmaydi — cheklarni OFD'ga yuboring", faqat "Qayta yuborish" faol; Offline: asosiy holat — ro'yxat va hisoblagich faol |
| POS-16 | Kassir, Egasi | M01 | Uskunalar sozlamasi (printer, tarozi, skaner) | Chek printeri: ulanish yo'li (Web Serial / WebUSB / Web Bluetooth (BLE) / Do'kon agenti orqali LAN 9100 / tizim printeri / bulut printer), qog'oz kengligi (58/80 mm), kod sahifasi (cp866), raster rejim (avtomatik), "Test chek"; tarozi: EAN-13 prefikslari (do'kon sozlamasidan, faqat ko'rish), jonli og'irlik (Web Serial — MVP'dan keyin); skaner: test maydoni; Do'kon agenti holati (qaror #60); **karta terminali** (qaror #71): shu kassaga bog'langan terminal (BO-12 dan — nom, TID, drayver, ulanish yo'li), holat (`online`/`busy`/`offline`/`error`), "Terminalni aniqlash" (agentning `card_terminal` imkoniyatidagi qurilmalar ro'yxati) va "Aloqani tekshirish" (`health`; pulli test tranzaksiya emas). Printer sozlamasi qurilmada saqlanadi; terminal bog'lanishi — serverda (BO-12) | Bo'sh: printer tanlanmagan — "Printer ulang yoki elektron chek zahirasi ishlatiladi"; terminal bog'lanmagan — "Karta qo'lda belgilanadi; terminalni back-office'da (Filiallar → Kassa) bog'lang"; Xato: printer topilmadi / ruxsat berilmadi / agent javob bermadi / terminal javob bermadi (`CARD_TERMINAL_UNREACHABLE`); Offline: lokal transportlar (USB/Serial/BLE/agent) va agent orqali terminal tekshiruvi ishlaydi, bulut printer — yo'q |

---

## 4. Back-office PWA ekranlari (BO-nn)

| ID | Rol | Modul | Maqsad | Asosiy elementlar | Holatlar |
|---|---|---|---|---|---|
| BO-01 | Barcha | — | Kirish (login), tenant/filial tanlash | (qaror #34) Kirish ikki usulda: **telefon + parol** yoki **"Google bilan kirish"** (OIDC tugmasi); filial tanlash, til almashtirish; "Parolni unutdim" havolasi — OTP kod birinchi navbatda **Telegram bot**ga, ulanmagan bo'lsa **SMS**ga (zaxira) yuboriladi, shu kod bilan yangi parol o'rnatiladi | Bo'sh: —; Xato: parol noto'g'ri; **Obuna muddati tugagan**: tenant `restricted` holatida — har qanday login (shu jumladan to'g'ri parol yoki Google bilan ham) rad etiladi, "Obuna muddati tugagan" xabari + Click/Payme to'lov havolasi ko'rsatiladi, to'lov qilinishi bilan kirish darhol ochiladi (US-M17-03); (qaror #20, #34) shu sahifada **"Ma'lumotlarimni yuklab olish"** havolasi ham ko'rsatiladi — bosilganda tasdiqlash kodi Telegram botga (ulangan bo'lsa) yoki SMS'ga (zaxira) yuboriladi, kod tasdiqlangandan keyin to'liq eksport tayyorlanadi (login ochilmaydi); Offline: PWA offline ombor/hisobot ko'rishga ruxsat beradi (IndexedDB, `04-fayl`), lekin yangi kirish internetsiz cheklangan |
| BO-02 | Egasi, Menejer | M12 | Dashboard — kunlik/haftalik savdo, qoldiq, qarzdorlik umumiy ko'rinishi | Savdo grafigi, top mahsulotlar, kassa holati (filiallar bo'yicha), ogohlantirishlar paneli | Bo'sh: ma'lumot yo'q (yangi tenant); Xato: hisoblash xatosi; Offline: oxirgi sinxronlangan ma'lumot "N daqiqa oldin" belgisi bilan |
| BO-03 | Menejer, Omborchi | M04 | Ombor qoldig'ini ko'rish va boshqarish | Ombor/filial tanlash, tovar ro'yxati (qoldiq, minimal daraja), filtr/qidiruv; **'Ko'chirishlar' tabi** (US-M06-03): holat (yo'lda / qabul qilindi / farq bilan), yuborilgan vaqt, **e-TTN holati** (yuborildi / tasdiqlandi / talab qilinmaydi / xato — qaror #63), kechikkanlar qizil; yaroqlilik muddati yaqin partiyalar belgisi (US-M04-06) | Bo'sh: ombor bo'sh; Xato: —; Offline: faqat ko'rish, IndexedDB'dagi oxirgi nusxa |
| BO-04 | Menejer, Omborchi, Buxgalter | M07 | Xaridnoma yaratish, yetkazib beruvchiga to'lov | Yetkazib beruvchi tanlash, tovar ro'yxati, **AI-03: qog'oz yuk xati/faktura fotosidan avtomatik to'ldirish** (qaror #16) — faqat QQS'ga tortilmagan/norasmiy yetkazib beruvchi yoki texnik uzilish holatida (standart QQS to'lovchilar orasidagi e-faktura EDO operatoridan import qilinadi, OCR qilinmaydi — `spec/kod-uchun/09-ai-funksiyalar.md`, AI-03), tasdiqlash, **"Yetkazib beruvchiga to'lov" bo'limi** (summasi, muddati, to'lov qayd etish — BP-12; qarzdan ortiq summa — ogohlantirish bilan ruxsat, ortig'i avans; `supplier_overpay_policy=block` bo'lsa rad, `SUPPLIER_OVERPAY_BLOCKED` — qaror #47), Omborchiga e-ishonchnoma berish (EDO operatori orqali — qaror #63), **'Yetkazib beruvchiga qaytarish'** (US-M07-05) | Bo'sh: yangi xaridnoma; Xato: AI OCR noto'g'ri o'qidi — qo'lda tuzatish shart; Offline: PWA'da yangi xaridnoma yaratish cheklangan (internet talab qilinadi) |
| BO-05 | Menejer | M09, M03 | Narxlar va chegirma qoidalarini boshqarish | Tovar narxi (chakana/optom), chegirma qoidasi, narx tarixi | Bo'sh: narx belgilanmagan; Xato: manfiy narx/chegirma; Offline: faqat ko'rish |
| BO-06 | Menejer, Buxgalter | M08 | Nasiya/qarzdorlar ro'yxati, eslatmalar va qarz undirish | Qarzdorlar ro'yxati (summa, muddat), **AI-06: debitorlik eslatma matni** (LLM generatsiya, `spec/kod-uchun/09-ai-funksiyalar.md`: "kod hisoblaydi, AI tushuntiradi") — matn avtomatik yuborilmaydi, Menejer/Buxgalter ko'rib chiqib tasdiqlaydi, **"To'lov qabul qilish"** tugmasi (mijozdan nasiya qarzini yopish, summa/sana — BP-11); (qaror #30) to'lov qabul qilinganda to'langan summaga **fiskal chek** chiqariladi (`debt_settlement`), tovar qatorlari yopilgan sotuv(lar)dan proporsional | Bo'sh: qarzdor yo'q; Xato: aloqa ma'lumoti yo'q; Offline: faqat ko'rish |
| BO-07 | Buxgalter | M10 | QQS ichki hisob-kitobi | Davr tanlash, QQS stavkalari (12%, 0%), ichki hisoblangan summa, **davlat hisoboti holati** (2026 dan deklaratsiyani davlat tuzadi — bu ekran "deklaratsiya topshirish" emas, ichki hisob-kitobni kuzatish; yakuniy solishtirish BO-10'da); **"Soliq hisob-kitobi (ST)" qoralama → o'tkazish** (`tax_settlements`: QQS hisobga olish Dt 6410 / Kt 4410, aylanma solig'i Dt 9430 / Kt 6410); **kutilayotgan QQS krediti** — qizil e-fakturalar bo'yicha to'lovgacha hisobga olinmagan QQS summasi va davr ulushi (VM 830, ≤10%), US-M10-03 | Bo'sh: davr yopilmagan; Xato: hisoblashda nomuvofiqlik; Offline: faqat ko'rish |
| BO-08 | Buxgalter | M11 | Buxgalteriya jurnali, provodkalar | Hisob rejasi bo'yicha jurnal, filtr (sana/hisob), eksport; **"Qayta hisoblash navbati"** bloki (`recost_jobs`: tovar, ombor, holat, navbatga qo'yilgan/tugagan vaqt, xato — qaror #56) | Bo'sh: yozuv yo'q; Xato: balans mos kelmadi; Offline: faqat ko'rish |
| BO-09 | Egasi, Menejer, Buxgalter | M12 | Hisobotlar markazi (savdo, ombor, buxgalteriya, QQS) | Hisobot turi tanlash, davr, eksport (PDF/Excel) | Bo'sh: ma'lumot yo'q; Xato: eksport muvaffaqiyatsiz; Offline: faqat oxirgi keshlangan hisobot |
| BO-10 | Buxgalter, Egasi | M12 | **Davlat hisobotini ichki hisob bilan solishtirish** | Soliq turi bo'yicha tablar: **QQS / Aylanma** (MVP) — ichki ma'lumot bilan to'liq solishtiriladi (MVP modullari buni qoplaydi, `spec/kod-uchun/04-biznes-jarayonlar.md`, Asosiy xulosalar #1); QQS tabida ichki ustunda **"kutilayotgan kredit"** alohida qator; **mol-mulk, yer, JShDS, ijtimoiy soliq** — API qabul qiladi, solishtirish yo'q (MVP'dan keyin; asosiy vositalar/kadr modullari MVP'da yo'q, qaror #52). Davlat hisoboti fayli (my.soliq.uz kabinetidan yuklab olingan PDF/Excel) foydalanuvchi tomonidan yuklanadi. Har bir tur uchun **5 ish kunlik** hisoblagich (hisobot kabinetga joylashtirilgan kundan keyingi kundan, hisobot topshirish muddatidan oshmaydi — SK 5-modda 7-qism; `04-biznes-jarayonlar.md`, BP-08), ogohlantirish **1-, 3- va 4-ish kunida** (qaror #50; 3-ish kunidan Egasiga ham ko'rinadi — 26 #3), "Farq topildi" holati `vat_diff_tolerance_amount` (standart `"1000.00"` so'm) dan boshlanadi; **har oyning 10-sanasida interaktiv ma'lumotlar eslatmasi** (ichki eslatma sanasi, sozlanadi; qonuniy muddat emas) — tizim aylanma (soliq solinmaydigan daromad, chegirmalar, imtiyozlar) va QQS (hisobga olinadigan QQS tuzatishlari, imtiyozlar) raqamlarini tayyorlab beradi; **AI-05: tafovutni tushuntirish** (`spec/kod-uchun/09-ai-funksiyalar.md`), "Kutilmoqda"/"Farq topildi"/"Tuzatish kiritildi"/"Muddat o'tdi — avtomatik qabul qilindi" holat belgisi. Ko'rinish darajasi: avval yig'ma, "Batafsil" — qator darajasi (26 #16); **QQS** — e-faktura darajasida (STIR + faktura raqami + sana bo'yicha moslashtirish) va yig'indi; **aylanma** — faqat yig'indi, manba (0101–0105: e-faktura / NKM / marketplace / eksport / boshqa) va stavka bo'yicha. "Kabinetda tuzatish" havolasi — tuzatish my.soliq.uz shaxsiy kabinetida "tasdiqlash" yoki "tuzatish kiritib taqdim etish" orqali (E-IMZO bilan) bajariladi, tizim farqlar ro'yxatini tayyorlaydi; muddat o'tgach — aniqlashtirilgan hisobot (SK 83-modda) | Bo'sh: davlat hisoboti hali yuklanmagan ("Kutilmoqda"); Xato: farq topildi; **Muddat o'tdi: "avtomatik qabul qilindi" belgisi** (5 ish kuni ichida javob berilmagan — SK 81-modda 6–7-qism); Offline: faqat ichki ustun ko'rinadi, davlat ustuni "internet kerak" bilan bo'sh |
| BO-11 | Egasi | M13 | Foydalanuvchilar, huquqlar va sessiyalar | Xodim ro'yxati (telefon, ism, rol(lar), filial(lar) — US-M13-04), rol tayinlash (Kassir/Omborchi/Menejer/Buxgalter), operatsiya cheklovlari, har xodim qatorida **'Bloklash/Blokdan chiqarish'** va **'Parol/PIN tiklash'** amallari (US-M13-05/06); **'Qurilmalar' tabi** (qaror #56): qurilma nomi, turi, oxirgi sinxron vaqti, sinxronlanmagan voqealar soni, 'Bekor qilish' (yo'qolgan/o'g'irlangan; Egasi/Menejer) — sinxronlanmagan voqea bo'lsa ogohlantirish va `sync.drain` taklifi (`kod-uchun/16-offline-sync.md` §9); **'Sessiyalar' tabi**: har xodimning faol login sessiyalari (qurilma turi, kirgan vaqt, oxirgi faollik), 'Bekor qilish' tugmasi (US-M13-07) — bu foydalanuvchi login sessiyalari uchun, 'Qurilmalar' tabidagi kassa POS qurilmalaridan farqli; texnik asos `spec/kod-uchun/14-autentifikatsiya-oauth2.md` | Bo'sh: faqat Egasi; Xato: bir xil login takror; Offline: faqat ko'rish |
| BO-12 | Egasi | M14 | Filiallar boshqaruvi | Filiallar ro'yxati, har biri bo'yicha konsolidatsiyalangan hisob, yangi filial qo'shish; kassalar jadvalida har kassa uchun **karta terminali** ustuni va "Terminalni bog'lash" dialogi (nom, vendor/model, ulanish turi — Do'kon agenti / bulut / Android ilova / SoftPOS / sinov, drayver, agent va lokal qurilma, LAN manzili, TID/MID, ekvayer bank, holat; kassada bir nechta terminal bo'lishi mumkin, bittasi standart — POS avtomatik tanlaydi) va do'kon darajasidagi "Terminalsiz karta (rekvizitsiz)" siyosati (`card_manual_fallback`: ruxsat / Menejer tasdig'i bilan / taqiqlangan; faqat faol terminal bog'langan kassalarga taalluqli) (qaror #71) | Bo'sh: bitta filial; kassada terminal yo'q — "Karta terminalsiz qabul qilinadi (faqat summa)"; Xato: agent ulanmagan / TID band; Offline: faqat ko'rish |
| BO-13 | Egasi, Menejer, Buxgalter | AI-01 | AI yordamchi — savol-javob chat | Chat oynasi, tez savollar ("Bugun qancha foyda?", "Qaysi tovar tugayapti?"), javobda manba/hisob-kitob ko'rsatuvi | Bo'sh: suhbat boshlanmagan; Xato: AI javob bera olmadi — "aniq emas" deb ko'rsatiladi (raqam o'ylab topilmaydi); Offline: AI chat ishlamaydi (internet/LLM API talab qiladi) |
| BO-14 | Egasi | — | Tenant/do'kon sozlamalari | Do'kon nomi, til, valyuta, soliq rejimi, integratsiyalar holati (OFD, e-faktura, Asl belgisi; Bosqich 7 dan **«1C» qatori** — holat 🟢/🟡/🔴/⚪, oxirgi muvaffaqiyatli kun, navbatdagi kunlar, xato hujjatlar soni, «Tafsilot» → BO-23; manba W-55); **Do'kon agenti** holati (fiskal ko'prik, LAN printer, tarozi — qaror #60); to'lov provayderlari kabinetida **provayder tomonidagi avto-fiskallashtirish o'chirilgani** tasdiq belgisi (Click/Payme/Uzum); markirovka tekshiruvi rejimi `MARKING_PRECHECK` (`warn` standart / `block`, qaror #62); tarozi EAN-13 prefikslari (22 — og'irlik g, 21 — summa so'm); **AI va shaxsiy ma'lumot**: chet elga uzatish roziligi (`tenants.settings.ai_cross_border_enabled`; rozilik berilmaguncha AI-03 rasmlari yuborilmaydi, matnli so'rovlarda shaxsiy maydonlar har doim maskalanadi — qaror #61), foydalanish shartlari versiyasi; **"Sinxron istisnolari"** ro'yxati — har qator "Ko'rib chiqildi" (izoh majburiy, audit; provodkaga ta'sir yo'q — qaror #56) | Bo'sh: sozlanmagan; Xato: integratsiya ulanmagan; Offline: faqat ko'rish |
| BO-15 | Buxgalter | M07, M10 | Kiruvchi va chiquvchi e-faktura markazi | Kiruvchi e-fakturalar ro'yxati (**Faktura.uz'dan — MVP'da yagona operator**; Didox'ni asoschi qayta ko'rishi tavsiya etiladi — 26 #167; BP-01), har biri uchun qabul/rad etish, E-IMZO bilan imzolash, **VM Qarori №830-son xavf-belgisi** (`risk_flag`: yashil / qizil / noma'lum — qizil yoki noma'lum bo'lsa QQS krediti to'lovgacha kechiktiriladi; noma'lumni Buxgalter my.soliq kabinetidan ko'rib qo'lda yashil qilishi mumkin, audit bilan); B2B nasiya sotuvidan avtomatik yaratilgan chiquvchi e-fakturalar ro'yxati (holati: yaratildi/imzolandi/yuborildi, BP-03); **"Chek asosida e-faktura chiqarish"** tugmasi — Buxgalter asl fiskal chekni (raqam/sana bo'yicha) qidirib tanlaydi va shu chekka bog'langan (`einvoices.related_doc_type`/`related_doc_id`) yangi chiquvchi e-faktura yaratadi (BP-13, US-M01-06); QQS qayta hisoblanmasligi ekranda aniq ko'rsatiladi | Bo'sh: faktura yo'q; Xato: E-IMZO imzolashda xato (sertifikat/parol); Offline: faqat ko'rish, imzolash internet talab qiladi (E-IMZO serverga bog'lanadi) |
| BO-16 | Egasi, Menejer | M02, M03, M08, M09, M16 | Tasdiqlash navbati (limitdan oshgan so'rovlar) | Kutilayotgan so'rovlar ro'yxati (turi: chegirma/qaytarish/nasiya/**narx o'zgarishi (US-M09-02)**/**limitdan katta pul olish (US-M16-01)**, kim so'rayotgani, summa, sabab), "Tasdiqlash"/"Rad etish" tugmalari, PIN orqali tasdiqlash | Bo'sh: navbat bo'sh; Xato: PIN noto'g'ri; Offline: back-office'da yangi tasdiqlash cheklangan — Menejer kassada PIN bilan inline tasdiqlaydi (masalan POS-06) |
| BO-17 | Egasi, Menejer, Buxgalter | M15 | Xarajatlar | Xarajatlar ro'yxati (sana, toifa, summa, manba), "Xarajat qo'shish", takrorlanuvchi xarajatlar, toifalar, foto biriktirish | Bo'sh: xarajat yo'q; Offline: faqat ko'rish |
| BO-18 | Menejer | M09 | Yorliq va shtrix-kod chop etish | Narxi o'zgargan tovarlar ro'yxati, shablon tanlash (58×40, 58×30, 43×25, 40×30, 30×20 mm, A4 varaq 3×8 / 4×10), ichki shtrix-kod yaratish, chop etish — brauzerda tizim drayveri orqali (HTML/SVG); server PDF — faqat >200 yorliq yoki iOS (qaror #54); tarozi uchun PLU ro'yxatini CSV eksport | Xato: printer topilmadi; Offline: lokal printer bilan ishlaydi |
| BO-19 | Egasi | M17 | Obuna va to'lov | **Yagona tarif: 99 000 so'm/oy** (hammasi narxga kiradi — tarif tanlash yo'q), joriy davr/muddat, faol kassalar soni va AI limiti sarfi, **"Qo'shimcha kassa qo'shish"** (+39 000 so'm/kassa/oy, qaror #22), oylik/yillik (−20%) almashtirish, Click/Payme bilan to'lash, to'lov tarixi | Xato: to'lov o'tmadi; Offline: faqat ko'rish |
| BO-20 | Egasi, Menejer | M18 | Telegram va bildirishnomalar | Telegram ulash (QR/havola — qaror #56), kunlik hisobot vaqti, ogohlantirish turlarini yoqish/o'chirish | Xato: bot ulanmadi; Offline: — |
| BO-21 | Yangi foydalanuvchi | M17 | Ro'yxatdan o'tish va birinchi sozlash (qaror #34) | **Telefon + parol (Telegram bot/zaxira SMS OTP bilan tasdiqlash) yoki "Google bilan kirish"** → **foydalanish shartlari (o'zbek tilida) qabul belgisi** (`accepted_terms_version`, vaqt, IP) va alohida **AI uchun chet elga uzatish roziligi** belgisi (ixtiyoriy; berilmasa AI-03 rasm OCR o'chiq — qaror #61) → do'kon nomi, faoliyat turi, yuridik shakli (YaTT/yuridik shaxs) → boshlang'ich tovarlar (US-M04-04) → boshlang'ich qarzlar (US-M08-07) → OFD/e-faktura ulash yo'riqnomasi (keyinroq ham mumkin) | Xato: OTP kelmadi (Telegram ham, SMS zaxira ham); Offline: — |
| BO-22 | Egasi, Buxgalter (Menejer — faqat ko'rish) | M19 | **1C integratsiyasi sozlamalari va moslashtirish** (Bosqich 7) | Yorliqlar: Kompyuter (ulash kodi, agent holati, diagnostika, uzish), Bazalar («1C ga yozishga ruxsat» kaliti, filial → baza bog'lash, qaysi sanadan), Tekshiruv (onboarding ✓/⚠/✗ + tuzatish maslahati), Moslash (ustoz: tashkilot, omborlar, kassalar, to'lov turlari, QQS, birliklar, tovarlar, kontragentlar, qoldiq; avto-moslash, «Barcha aniq moslarni tasdiqlash», «1C da yaratish» taklifi va tasdig'i), Sozlamalar (rejim `full`/`sales_only`, boshlanish sanasi, ОРП guruhlash, jadval, avto-tasdiq — faqat Egasi, ochiq smena siyosati, qo'shimcha hujjatlar), Jurnal (voqealar, drift) | Bo'sh: agent ulanmagan — «ERP 1C Agent ni yuklab oling»; Xato: tekshiruv `fail` (qamrovdan tashqari — qizil karta); Offline: faqat ko'rish |
| BO-23 | Egasi, Buxgalter (Menejer — faqat ko'rish) | M19 | **1C ga yuborish (kunlar)** (Bosqich 7) | Baza va sana tanlovi, agent holati chipi, tayyorlik checklisti (smenalar, qurilma sinxroni + istisno, moslashtirish), «ERP jami = 1C ga yoziladi» jami, 1C hujjatlari ro'yxati (turi, filial/kassa, qatorlar, summa, holat), ogohlantirishlar «Ko'rdim» bilan, «1C ga yuborish», progress (har hujjat: kutilmoqda / yozilmoqda / ✓ № / xato), natija, «Faqat xatolarni qayta yuborish», o'tkazib yuborish, qabul qilish, yangi revision, tuzatuvchi hujjat; oy kalendari (holat ranglari) | Bo'sh: kun tayyorlanmagan / hujjat yo'q; Xato: bloklovchi muammo (qizil checklist), `partial`/`mismatch`/`failed`; Offline: faqat ko'rish |
| BO-24 | Buxgalter, Egasi | M11 | **Bank tushumi tasdig'i** (yo'ldagi pul → bank, qaror #42) | Ro'yxat (sana, raqam, filial, to'lov usuli, davr, yalpi/komissiya/sof summa, bank raqami, holat), filtrlar; usul × filial bo'yicha **yo'ldagi pul qoldig'i** paneli (`GET /api/v1/bank-settlements/transit-balances`); **"Ko'chirmani import qilish"** — 1CClientBankExchange `.txt` fayli (`POST /api/v1/bank-settlements/imports`): faqat kirimlar o'qiladi va qoralama tasdiqlarga aylanadi, Buxgalter yalpi summani 5710 qoldig'idan tanlaydi, komissiya = yalpi − kirim (hisob 9430); forma: filial, sana, usul (karta/UzQR/Click/Payme/Uzum/inkassa), qamralgan davr, yalpi summa, komissiya, sof summa (avtomatik), bank raqami, ko'chirma fayli, izoh; «Saqlash», «O'tkazish», «Bekor qilish» (sabab) | Bo'sh: hujjat yo'q; Xato: summa yo'ldagi pul qoldig'idan katta; Offline: faqat ko'rish |
| ADM-01 | Platforma admini | M17, M13 | Ichki admin panel | Tenantlar, obuna holati, to'lovlar, AI sarfi, muddatni qo'lda uzaytirish (`billing_payments(kind='manual_extension', amount="0.00")` yozuvi, sabab bilan — qaror #56); tenant Egasi (owner) hisobini bloklash/blokdan chiqarish, parolini tiklash, faol sessiyalarini ko'rish/bekor qilish (US-M13-08) | — |

---

## 5. Asosiy oqimlar (UX nuqtai nazaridan, qisqa)

**Sotuv (naqd/karta/aralash naqd qismi):** POS-01 (smena ochiq) → POS-02 (mahsulot qo'shish, skaner) → POS-03 (to'lov usuli) → POS-04 (bosma fiskal chek; elektron — zahira) → POS-02 (yangi chek). Birinchi ishga tushirishda printer/tarozi — POS-16.

**Nasiyaga sotish** (qaror #30): POS-02 → POS-06 (mijoz, limit tekshiruvi) → POS-03 (to'lov usuli = "Nasiya") → **POS-02'ga qaytish (yangi chek)** — to'liq nasiya bo'lsa POS-04 **ochilmaydi**, fiskal chek chiqarilmaydi (sotuv `posted`, fiskal holat `fiscal.status='deferred'`). Aralash to'lovda (naqd+nasiya) naqd qismiga POS-04 ochiladi, nasiya qismi uchun yo'q.

**Qaytarish:** POS-05 (chekni topish) → tovar/sabab tanlash → naqd/balans qaytarish tasdiqlash.

**Kirim (xarid qabul):** BO-04 (xaridnoma yaratish, ofis; kerak bo'lsa Omborchiga e-ishonchnoma) → BO-15 (kiruvchi e-faktura qabul/E-IMZO imzo) → POS-08 (ombor, jismoniy qabul, skanerlash) → BO-03 (qoldiq yangilanadi) → BO-04 (yetkazib beruvchiga to'lov, BP-12).

**Inventarizatsiya:** BO-03 (joriy qoldiqni ko'rish) → POS-10 (jismoniy sanash) → BO-03 (farq tasdiqlangandan keyin yangilanadi).

**Limitdan oshgan so'rov (chegirma/qaytarish/nasiya):** POS-02/05/06 (Kassir so'raydi) → Menejer yaqinda bo'lsa POS'da PIN bilan darhol tasdiqlaydi, aks holda BO-16 (tasdiqlash navbati) → natija POS ekraniga qaytadi.

**Nasiya qarzini undirish** (qaror #30): BO-06 (qarzdor tanlanadi) → "To'lov qabul qilish" → qarz kamayadi (BP-11) → **shu to'langan summaga fiskal chek chiqariladi** (`debt_settlement`, POS-13'da xuddi shunday) → BO-06'ga qaytish.

**Bank tushumi tasdig'i** (qaror #42): bank ko'chirmasi keladi → BO-24 «Ko'chirmani import qilish» (qoralamalar) yoki «Yangi» → filial va usulni tanlash (panelda yo'ldagi pul qoldig'i) → summa/komissiya/davr/bank raqami → «O'tkazish» → yo'ldagi pul kamayadi, bank hisobi ortadi (BP-15).

**Kunni 1C ga yuborish** (Bosqich 7, BP-14): kassalar smenani yopadi (POS-07) → Telegram «kun tayyor» havolasi yoki sidebar → BO-23 (tayyorlik checklisti; blok bo'lsa — BO-22 «Moslash» yoki qurilmani istisno qilish) → ogohlantirishlarni «Ko'rdim» → «1C ga yuborish» tasdiq modali → progress → natija (Telegram); xato bo'lsa — BO-23 da tuzatish/qayta yuborish/qabul. Bir martalik sozlash: BO-22 (kompyuterni ulash → tekshiruv → filial bog'lash → moslashtirish ustasi → «1C ga yozishga ruxsat»).

**Davlat hisobotini solishtirish:** 10-sanagacha interaktiv ma'lumotlar eslatmasi (tizim raqamlarni tayyorlaydi) → davlat hisoboti kabinetga joylashtiriladi → Buxgalter faylni BO-10 ga yuklaydi, **5 ish kunlik** hisoblagich (topshirish muddatidan oshmagan holda — SK 5-modda 7-qism, 81-modda) → QQS/aylanma uchun avtomatik solishtirish, qolganlarida faqat davlat raqami → farq bo'lsa 1-, 3-, 4-ish kunida Buxgalter/Egasiga ogohlantirish (qaror #50) → Buxgalter BO-15'da hujjatlarni ko'rib chiqadi → my.soliq.uz kabinetida tasdiqlash yoki tuzatish kiritib taqdim etish (E-IMZO) yoki muddat o'tganda davlat shakllantirgan ko'rinishda avtomatik qabul.

---

## 6. Matnli (ASCII) wireframelar

### POS-01 — Kassaga kirish / Smena ochish

```
┌───────────────────────────────────────┐
│  ERP Kassa               [UZ·RU]  🔴   │
├───────────────────────────────────────┤
│                                         │
│        Filial: "Chilonzor-3"  ▾        │
│                                         │
│   PIN kod:  [ * * * * ]                │
│                                         │
│        [ 1 ][ 2 ][ 3 ]                 │
│        [ 4 ][ 5 ][ 6 ]                 │
│        [ 7 ][ 8 ][ 9 ]                 │
│        [  ][ 0 ][ ⌫ ]                  │
│                                         │
│         [  SMENANI OCHISH  ]           │
│                                         │
└───────────────────────────────────────┘
Holat: Bo'sh — PIN kiritilmagan | Xato — "PIN noto'g'ri" qizil matn |
Offline — status 🔴, pastda "Internet yo'q, lokal tekshiriladi"
Qo'shimcha holat — "Obuna muddati tugagan": butun ekran
qizil banner bilan to'siladi, faqat "Click/Payme orqali to'lash" va "Ma'lumotlarimni
yuklab olish" (qaror #20, #34 — Telegram bot/zaxira SMS tasdiq) havolalari
faol, PIN maydoni o'chirilgan; "PIN/parolni unutdim"
havolasi — (qaror #34) OTP orqali tiklash oynasini ochadi (kod birinchi
navbatda Telegram botga, ulanmagan bo'lsa SMS'ga). Fonda (qaror #19): lokautdan oldingi
yuborilmagan cheklar `sync.drain` orqali OFD'ga yuborilishda davom etadi (ekranda ko'rinmaydi).
```

### POS-02 — Sotish paneli (asosiy chek)

```
┌──────────────────────────────────────────────────────────────────────┐
│ Chilonzor-3 · Kassa 1 · Smena #214   🟡 OFFLAYN · 3 chek  🖨  [UZ·RU] Kassir│
├────────────────────────────────────────┬─────────────────────────────┤
│ [ Skanerlang yoki tovar nomi/kodi  F1 ] │ Chek #000483     [+ Mijoz F3]│
│                 [Kartochka | Ro'yxat]   │ Non «Patir»   4 000×2 [−][+] 8 000│
│ [Hammasi][Non][Sut][Bakaleya][Ichimlik] │ Guruch 1,250 kg×18 000   22 500│
│ ┌────────┐┌────────┐┌────────┐┌───────┐ │ Gazli ichimlik  markirovka 18 000│
│ │ NP     ││ S      ││ GL     ││ GI    │ │                              │
│ │Non     ││Sut 1 l ││Guruch  ││Gazli  │ │ Oraliq summa         96 500  │
│ │4 000   ││13 500  ││18 000  ││9 000  │ │ Chegirma             −2 000  │
│ │ dona   ││ dona   ││ tarozi ││markir.│ │ Shu jumladan QQS 12% 10 125  │
│ └────────┘└────────┘└────────┘└───────┘ │ JAMI            94 500 so'm  │
│                        [📒 Qarz daftari] │ [CHEGIRMA] [NASIYA] [BEKOR]  │
│                                         │ [   TO'LOVGA O'TISH  F4    ] │
└────────────────────────────────────────┴─────────────────────────────┘
Holat: Bo'sh — "Chekni boshlang, skanerlang" | Xato — "Markirovka
o'qilmadi, qayta urinilmoqda..." → 3 urinishdan keyin "Qo'lda kirit"
maydoni | Offline — status panel 🟡/🔴, TO'LOV tugmasi faol qoladi
BEKOR — qator o'chirish / chekni bekor qilish (`sales.void`), audit voqeasi
Skaner har doim faol: kartochka yoki ro'yxat ko'rinishida, istalgan kategoriyada
skanerlangan kod chekka qator qo'shadi (tafsilot — `07-ekran-tafsilotlari.md`, POS-02)
```

### POS-03 — To'lov usuli va hisoblash

Integratsiyalangan karta terminali (qaror #71) — karta tanlangan, bank javobi kutilmoqda:

```
┌──────────────────────────────────────────────────────────┬──────────────────────────┐
│ To'lov  [Chek #000483]                              [✕]  │ Chek tarkibi             │
│ [Naqd] [■ Karta — terminalga yuboriladi] [UzQR] [Click]  │ Non «Patir» ×2     8 000 │
│ [Payme] [Uzum] [Aralash] [Nasiya]                        │ ...                      │
│ ┌──────────────────────────────────────────────────────┐ │ Oraliq summa      96 500 │
│ │ Summa terminalga yuborildi        (Wi-Fi · ulangan)  │ │ Chegirma          −2 000 │
│ │ Mijoz kartani tegizsin yoki kiritsin va PIN tersin   │ │ Shu jumladan QQS 12%     │
│ │ Terminal: [Bank] POS · TID ...   Do'kon agenti orqali│ │ To'lanadigan  94 500 so'm│
│ │ (1✓ Summa yuborildi)(2● Kartani tegizadi / PIN)      │ │ Karta · terminal  94 500 │
│ │ (3 Bank javobi)     (4 Fiskal chek — avtomatik)      │ │ Qoldiq                 0 │
│ │ Karta (niqob) | RRN / tasdiq kodi | Karta turi       │ │ Bank tasdiqlagach fiskal │
│ │  terminaldan keladi (kassir yozmaydi)                │ │ chek avtomatik chiqadi   │
│ │ [Terminalda bekor qilish] [Qayta yuborish — o'chiq]  │ │ [ Bank javobi kutilmoqda…]│
│ │                              Kutish: 00:18 / 02:00   │ │ [ Sotishga qaytish  Esc ]│
│ └──────────────────────────────────────────────────────┘ │                          │
│ ⓘ Karta raqami qo'lda kiritilmaydi — summa, natija va RRN│                          │
│   terminal bilan avtomatik almashadi                     │                          │
└──────────────────────────────────────────────────────────┴──────────────────────────┘
Holat: Kutish — 2-qadam faol, "Qayta yuborish" o'chiq | Tasdiq — 3–4-qadam ✓, niqob/RRN/
tur to'ladi, fiskal chek avtomatik → POS-04 | Rad — sabab, "Qayta yuborish" (yangi urinish)
yoki boshqa usul | Noma'lum (taymaut/aloqa uzildi) — "Terminal javobini tekshiring",
holat so'rovi; yangi urinish bloklangan; aniqlanmasa — Menejer terminal chekiga qarab
o'tgan/o'tmaganini tasdiqlaydi (hech narsa yozmaydi) | Terminal ulanmagan — Karta tugmasida
sabab; terminalsiz karta `card_manual_fallback` bo'yicha | ⛔ 48 soat bloki — karta yuborish va TASDIQLASH o'chiq
```

Terminalsiz karta (rekvizitsiz; terminal bog'lanmagan kassa yoki zaxira, qaror #64), offline:

```
┌───────────────────────────────────────┐
│ 🟡 OFFLAYN                   22:42    │
├───────────────────────────────────────┤
│         To'lanadigan: 69 000 so'm      │
│                                         │
│  [ 💵 NAQD ] [ 💳 KARTA (terminalsiz) ]│
│  [ 📱 PAYME (o'chiq) ] [📱 CLICK (o'chiq)]│
│  [ 📱 UZUM (o'chiq) ]  [ 📒 NASIYA ]   │
│  [ ✓ Karta terminalsiz qabul qilindi ] │
│    (faqat summa — karta ma'lumoti      │
│    so'ralmaydi; CardManualConfirm)     │
│  (zaxira bo'lsa: sabab + Menejer PIN)  │
│  ⓘ Elektron to'lovlar onlayn tasdiq    │
│    talab qiladi — offlaynda mavjud emas│
│                                         │
│  Olingan naqd:  [  100 000  ]          │
│  Qaytim:         31 000 so'm           │
│                                         │
│         [   TASDIQLASH   ]             │
└───────────────────────────────────────┘
Holat: Bo'sh — usul tanlanmagan | Xato — "Payme javob bermadi, qayta
urinish yoki naqd/karta/nasiya tanlang" | Offline — Payme/Click/Uzum va UzQR
(statik ham) tugmalari o'chirilgan (kulrang), naqd/karta/nasiya faol | ⛔ 48 soat
bloki — TASDIQLASH o'chiq, "Cheklarni OFD'ga yuboring" (POS-12)
```

### POS-05 — Qaytarish

```
┌───────────────────────────────────────┐
│ 🟢 ONLAYN                    22:50    │
├───────────────────────────────────────┤
│  Chekni qidirish:  [ #000481  ] [🔍]   │
│                                         │
│  Chek #000481 — 12.10.2026, 69 000 so'm│
│  ┌─────────────────────────────────┐   │
│  │ [x] Coca-Cola 1.5L   x1  18 000 │   │
│  │ [ ] Non "Bekhurmon"  x2  24 000 │   │
│  └─────────────────────────────────┘   │
│  Sabab:  [ Nuqsonli tovar     ▾ ]      │
│                                         │
│  Qaytariladigan: 18 000 so'm           │
│         [  QAYTARISHNI TASDIQLA  ]     │
└───────────────────────────────────────┘
Holat: Bo'sh — chek topilmagan | Xato — "Bu chek allaqachon qaytarilgan"
| Offline — qaytarish lokal yoziladi, "serverga yuborilganda tasdiqlanadi"
```

### POS-06 — Nasiyaga sotish

```
┌───────────────────────────────────────┐
│ 🟢 ONLAYN                    22:55    │
├───────────────────────────────────────┤
│  Mijoz:  [ Aliyev Botir      ▾ ] [+Yangi]│
│                                         │
│  Joriy qarz:       350 000 so'm        │
│  Kredit limiti:     500 000 so'm       │
│  Shu sotuvdan keyin: 419 000 so'm      │
│                                         │
│  ⚠ Limitga yaqinlashdi (84%)           │
│                                         │
│  To'lov muddati:  [ 30 kun     ▾ ]     │
│         [  NASIYAGA RASMIYLASHTIR  ]   │
└───────────────────────────────────────┘
Holat: Bo'sh — mijoz tanlanmagan | Xato — "Limitdan oshdi — Menejer PIN
kiriting" (sotuv Menejer tasdiqlamaguncha yakunlanmaydi) | Offline — limit
oxirgi sinxron ma'lumot asosida, Menejer PIN'i lokal tasdiqlaydi, "server
qayta tekshiradi" eslatmasi bilan
```

### POS-08 — Ombor qabul (kirim) skaneri

```
┌───────────────────────────────────────┐
│ 🟢 ONLAYN                    09:05    │
├───────────────────────────────────────┤
│  Xaridnoma: #XN-0231 — "Mega Trade" MChJ│
│  ┌─────────────────────────────────┐   │
│  │ Tovar          Buyurtma  Keldi  │   │
│  │ Coca-Cola 1.5L    50      48 ⚠ │   │
│  │ Sut "Oltin" 1L    30      30 ✓ │   │
│  └─────────────────────────────────┘   │
│  [ 📷 Markirovkani skanerlash ]        │
│                                         │
│  ⚠ 2 dona kam keldi — sabab belgilang  │
│         [  QABULNI YAKUNLASH  ]        │
└───────────────────────────────────────┘
Holat: Bo'sh — xaridnoma tanlanmagan | Xato — "Markirovka kodi o'qilmadi,
qo'lda kiriting" (1.7-bo'lim) | Offline —
skanerlash/miqdor solishtirish lokal davom etishi mumkin, lekin
"QABULNI YAKUNLASH" tugmasi internet talab qiladi — offline qabul
(kirim) voqeasi sinxronizatsiya protokolida yo'q (`03-modullar-talablari.md`,
M07 Offline xatti-harakati; `spec/tarix/tekshiruv/qabul-7-ekran-api.md`, K2-02)
```

### POS-10 — Inventarizatsiya skaneri

```
┌───────────────────────────────────────┐
│ 🟡 OFFLAYN · 0 chek kutmoqda           │
├───────────────────────────────────────┤
│  Ombor: "Asosiy ombor"   Sanalgan: 128/310│
│  ┌─────────────────────────────────┐   │
│  │ Tovar            Tizimda  Sanalgan│  │
│  │ Non "Bekhurmon"     40      40  ✓│  │
│  │ Coca-Cola 1.5L      22      19  ⚠│  │
│  └─────────────────────────────────┘   │
│  [ 📷 Skanerlash ]  [ ✏ Qo'lda kirit ] │
│                                         │
│         [  SANASHNI YAKUNLASH  ]       │
└───────────────────────────────────────┘
Holat: Bo'sh — sanash boshlanmagan | Xato — "Bu shtrix-kod tizimda yo'q"
| Offline — to'liq lokal ishlaydi, internet talab qilinmaydi
```

### POS-12 — Offline/sinxronizatsiya holati

```
┌───────────────────────────────────────┐
│ 🔴 OFFLAYN — 26 soat 10 daqiqa         │
├───────────────────────────────────────┤
│  48 soatgacha qoldi: 21 soat 50 daqiqa │
│  ████████████████░░░░░  (muddat chizig'i)│
│                                         │
│  Sinxronlanmagan hujjatlar: 7           │
│  ┌─────────────────────────────────┐   │
│  │ Chek #000479   22:41   Kutmoqda │   │
│  │ Chek #000480   22:44   Kutmoqda │   │
│  │ Qabul #0231    09:05   Kutmoqda │   │
│  └─────────────────────────────────┘   │
│         [  QAYTA ULANISHGA URINISH  ]  │
└───────────────────────────────────────┘
Holat: Bo'sh — hammasi sinxron (ekran ko'rinmaydi) | Xato — "Ulanish
muvaffaqiyatsiz, 2 daqiqadan keyin qayta urinadi" | Offline — asosiy holat;
24 soat 🟡, 40 soat 🔴 (+ Egasiga Telegram), 46 soatdan modal "2 soatdan keyin
kassa bloklanadi" | ⛔ 48 soat — sarlavha "KASSA BLOKLANGAN — yangi chek
chiqarib bo'lmaydi", faqat [ QAYTA YUBORISH ] faol; barcha cheklar OFD
tasdig'ini olgach blok avtomatik yechiladi (qaror #43)
```

### BO-02 — Egasi/Menejer dashboardi

```
┌──────────────────────────────────────────────────┐
│ ERP             Bugun ▾   Chilonzor-3 ▾   [UZ·RU] │
├──────────────────────────────────────────────────┤
│  Bugungi savdo: 4 250 000 so'm   (↑ 12% kecha)    │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────┐│
│  │ Naqd: 2.1 mln│ │ Karta: 1.5mln│ │ Nasiya:650k││
│  └──────────────┘ └──────────────┘ └────────────┘│
│                                                    │
│  ⚠ Ogohlantirishlar (3)                           │
│   • "Coca-Cola 1.5L" qoldig'i tugayapti (12 dona) │
│   • Davlat hisoboti: QQS'da farq topildi (BO-10)  │
│   • Filial "Yunusobod-1" 26 soat offlayn           │
│                                                    │
│  Top mahsulotlar:  1. Non  2. Sut  3. Coca-Cola    │
└──────────────────────────────────────────────────┘
Holat: Bo'sh — yangi tenant, ma'lumot yo'q | Xato — hisoblash xatosi
(ma'lumot ko'rsatilmaydi, "qayta urinish" tugmasi) | Offline — "Oxirgi
yangilanish: 18 daqiqa oldin" belgisi butun panel ustida
```

### BO-10 — Davlat hisobotini solishtirish

```
┌──────────────────────────────────────────────────┐
│ [QQS ⚠Farq] [Aylanma · rejimda yo'q]              │
│ Mol-mulk, yer, JShDS, ijtimoiy soliq — MVP'dan keyin│
│ Yuklandi → Solishtirildi → Farq topildi →          │
│   Tuzatish qayd etildi → Tasdiqlandi               │
├──────────────────────────────────────────────────┤
│  QQS — 2026-yil sentyabr                          │
│  Holat: ⚠ FARQ TOPILDI                            │
│  Tuzatish uchun qoldi: 3 ish kuni (19-okt,         │
│  qonuniy topshirish muddatidan oshmagan holda)     │
│                                                     │
│  Hujjat darajasi (e-faktura reyestri, Batafsil):   │
│  ┌────────────────────────────────────────────┐   │
│  │ Qator          Davlat     Ichki     Farq    │   │
│  │ E-faktura #882  480 000   480 000    0 ✓   │   │
│  │ E-faktura #883  120 000   96 000  -24 000 ⚠│   │
│  │ Chek #000481     18 000    18 000    0 ✓   │   │
│  └────────────────────────────────────────────┘   │
│  Yig'ma (davr) darajasi:                           │
│  Davlat: 2 324 000   Ichki: 2 300 000  Farq: 24 000│
│                                                     │
│   [ Farqni ko'rib chiqish ]  [ Kabinetda tuzatish ]│
└──────────────────────────────────────────────────┘
Holat: Bo'sh — davlat hisoboti hali e'lon qilinmagan ("Kutilmoqda")
| Xato — farq topildi (yuqoridagi ko'rinish) | Muddat o'tdi — "Avtomatik
qabul qilindi" belgisi (5 ish kuni ichida javob berilmagan) | Offline —
faqat ichki ustun ko'rinadi, davlat ustuni "internet kerak" bilan bo'sh
```

### BO-13 — AI yordamchi chat

```
┌──────────────────────────────────────────────────┐
│  AI yordamchi                              [UZ·RU]│
├──────────────────────────────────────────────────┤
│  Siz: Bugun qancha foyda qildim?                   │
│                                                     │
│  AI: Bugungi (12.10.2026) sof foyda — 890 000      │
│      so'm. Bu savdo (4 250 000) minus tovar        │
│      tannarxi va xarajatlar asosida hisoblangan.   │
│      [Hisoblash manbasi: Hisobotlar → Kunlik P&L]  │
│                                                     │
│  [ Bugun qancha foyda? ] [ Qaysi tovar tugayapti? ]│
│  ┌─────────────────────────────────────────────┐  │
│  │ Xabar yozing...                      [ ➤ ]  │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
Holat: Bo'sh — "Nimadan boshlashni bilmasangiz, tugmalardan birini
tanlang" | Xato — "Bu savolga aniq javob topa olmadim, Hisobotlar
bo'limiga qarang" (raqam o'ylab topilmaydi) | Offline — chat butunlay
o'chirilgan, "AI uchun internet kerak" xabari
```

### BO-03 — Ombor qoldig'i

```
┌──────────────────────────────────────────────────┐
│  Ombor: Asosiy ombor ▾        [ 🔍 Qidir ] [+Yangi]│
├──────────────────────────────────────────────────┤
│  Tovar              Qoldiq   Min. daraja   Holat   │
│  Non "Bekhurmon"       40         20        ✓      │
│  Coca-Cola 1.5L        12         20        ⚠ Kam  │
│  Sut "Oltin" 1L        85         30        ✓      │
├──────────────────────────────────────────────────┤
│  [ Ko'chirish ]  [ Inventarizatsiya ]  [ Eksport ] │
└──────────────────────────────────────────────────┘
Holat: Bo'sh — ombor bo'sh (yangi filial) | Xato — ma'lumot sinxron
emas, "Oxirgi yangilanish" ko'rsatiladi | Offline — faqat ko'rish rejimi,
IndexedDB'dagi oxirgi nusxa (`04-fayl`, 2.1-bo'lim)
```

### BO-15 — Kiruvchi/chiquvchi e-faktura markazi

```
┌──────────────────────────────────────────────────┐
│  [ Kiruvchi (3) ]   [ Chiquvchi (1) ]             │
├──────────────────────────────────────────────────┤
│  #882  "Mega Trade" MChJ   480 000   🟢 Yashil    │
│  #883  "AgroFood" XK       120 000   🔴 Qizil      │
│        ⚠ QQS krediti to'lovdan keyin beriladi     │
│  #884  "Baraka" MChJ        75 000   ⚪ Noma'lum   │
│        [ Yashil deb belgilash ] (kabinetdan ko'rib)│
│  [ Qabul qilish ]  [ Rad etish ]  [ E-IMZO imzo ]  │
└──────────────────────────────────────────────────┘
Holat: Bo'sh — faktura yo'q | Xato — E-IMZO imzolashda xato
(sertifikat/parol) | Offline — faqat ko'rish, imzolash internet talab
qiladi (E-IMZO backend serverga bog'lanadi)
```

### BO-16 — Tasdiqlash navbati

```
┌──────────────────────────────────────────────────┐
│  Kutilayotgan so'rovlar (2)                        │
├──────────────────────────────────────────────────┤
│  Nasiya limiti — Kassir Dilnoza, 419 000 so'm      │
│  [ PIN: ____ ]  [ Tasdiqlash ]  [ Rad etish ]      │
│                                                     │
│  Chegirma 25% — Kassir Aziz, sabab: "doimiy mijoz" │
│  [ PIN: ____ ]  [ Tasdiqlash ]  [ Rad etish ]      │
└──────────────────────────────────────────────────┘
Holat: Bo'sh — navbat bo'sh | Xato — "PIN noto'g'ri" | Offline — PWA'da
yangi tasdiqlash cheklangan, Menejer kassada PIN bilan inline
tasdiqlaydi
```

---

## Ochiq savollar

- **12.** Tashqi javob kerak: do'kon savdosida faqat elektron (qog'ozsiz) chekka rasmiy ruxsat — hozircha bosma standart, elektron zahira (1.6-bo'lim) — 26 #112 (OQ-018).
- **13.** Tashqi javob kerak: printer transportlari (Web Serial/WebUSB/BLE/agent) va raster rejimining real uskunadagi sinovi (POS-16) — 26 #139 (OQ-060).

## Manbalar

- `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` — markirovka skanerlash xatosi (80–90%, yetkazib berish zanjiri darajasida), markaziy soliq oqimi
- `research_notes/texnik/02-kassa-ofd-markirovka.md` — 48 soatlik offlayn qoidasi (943-son qaror, 1-ilova, 31-band), fiskal modul xato kodlari, MXIK (17 raqam)
- `research_notes/texnik/03-efaktura-va-tolov.md` — Payme/Click/Uzum protokollari (onlayn tasdiq talabi), VM Qarori №830-son (e-faktura xavf-baholash)
- `research_notes/texnik/04-arxitektura-va-stack.md` — Android POS / PWA platforma qarori, offline-first event-log, davlat hisobotini solishtirish oqimi (6-bo'lim), offlayn markirovka xavfi (10-bo'lim)
- `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md` — skaner (USB HID keyboard-wedge), chek printeri (ESC/POS)
- `research_notes/texnik/08-mahsulot-modullari.md` — dastlabki 14 MVP modul ro'yxati (tarixiy; joriy 18 modul ro'yxati — `spec/README.md`, `03-modullar-talablari.md`)
- `spec/README.md` — umumiy qoidalar va asosiy qarorlar
- `research_notes/ochiq-savollar/P1-soliq-fiskal.md` — 48 soatlik blok (OQ-004), chek formati (OQ-009), davlat hisobotiga tuzatish 5 ish kuni (OQ-013/014), elektron chek (OQ-018)
- `research_notes/ochiq-savollar/P2-efaktura-markirovka.md` — e-TTN ichki ko'chirishda (OQ-021), e-ishonchnoma (OQ-024), markirovka chek orqali (OQ-026), qabul muddati (OQ-027)
- `research_notes/ochiq-savollar/P3-tolovlar-bank.md` — karta turi/niqob/RRN — faqat integratsiyalangan to'lovda (OQ-033; terminalsiz chek — 26 #178), UzQR statik/dinamik (OQ-032), ko'chirma importi (OQ-038)
- `research_notes/ochiq-savollar/P6-uskuna-ai-narx.md` — bulut printer, tarozi EAN-13, yorliq o'lchamlari (OQ-059/061/062)
- `research_notes/ochiq-savollar/D-qarorlar-va-E-standartlar.md` — qarorlar #43–#59
- `spec/kod-uchun/02-rollar-va-ssenariylar.md` — rollar, huquqlar matritsasi, limitdan oshganda Menejer tasdig'i
- `spec/kod-uchun/04-biznes-jarayonlar.md` — BP-01…BP-15, davlat tizimlari × jarayon matritsasi, BO-10'ning jarayon asosi
- `spec/kod-uchun/33-1c-integratsiya.md` — §13 (BO-22, BO-23, BO-14 «1C» qatori, «1C da» belgisi, Telegram xabarlari)
- `spec/kod-uchun/13-provodka-qoidalari.md` — §2.18a (BO-24, bank tushumi tasdig'i)
- `spec/kod-uchun/09-ai-funksiyalar.md` — AI-01…AI-11 ro'yxati va qamrovi (AI-03 OCR, AI-05 tafovut tushuntirish, AI-06 debitorlik eslatma)
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — autentifikatsiya arxitekturasi (o'z OAuth 2.0, sessiyalar)
- `spec/kod-uchun/01-qarorlar.md` — qaror #14/#15 (OAuth, obuna lokauti), #16 (AI-03), #17 (markirovka offline), #18 (chekdan keyingi e-faktura), #29/#30/#34 (chek tili, qarz to'lovi, Google/Telegram), #43 (offline 48 soat), #47, #50, #54, #56, #57, #60–#64 (Do'kon agenti, AI rozilik, markirovka, e-TTN, karta to'lovi)
- `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` — tavsiya #4 (Faktura.uz), #5 (offline qaytarish/ko'chirish), #6 (terminalsiz karta), #13 (yagona tarif)
