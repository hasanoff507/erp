# Ekranlar va UX — Android POS va Back-office PWA

**Maqsad:** Android POS va Back-office PWA'ning 37 ekranini (rol, modul, maqsad, asosiy elementlar, holatlar), umumiy UX qoidalarini va asosiy oqimlarni belgilash.
**Kim uchun:** frontend ishlab chiquvchilar, UX/dizayn tizimi.
**Bog'liq fayllar:** `01-qarorlar.md`, `07-ekran-tafsilotlari.md`, `08-dizayn-tizimi.md`, `03-modullar-talablari.md`.
**Holat:** joriy, 2026-10-15.

## Asosiy xulosalar

1. Ikki platforma: **Android-native POS** (asosan Kassir, qisman Omborchi — skanerlash vazifalari) va **back-office PWA** (Egasi, Menejer, Buxgalter, qisman Omborchi) — arxitektura qarori bo'yicha (`research_notes/texnik/04-arxitektura-va-stack.md`, 3-bo'lim).
2. **Jami 37 ekran** (15 ta POS-nn, 21 ta BO-nn, 1 ta ADM-nn) — 18 MVP modulning har biri kamida bitta ekranga ega (pastdagi 3- va 4-bo'lim jadvallari); reviewdan keyin kiruvchi/chiquvchi e-faktura markazi (BO-15) va limitdan oshgan so'rovlar tasdiqlash navbati (BO-16) qo'shildi (7-band, quyida).
3. **Offline indikatori majburiy va har bir POS ekranining status panelida bir xil joyda** turadi — offline holatda birinchi chek 48 soat ichida OFD'ga yetishi shart bo'lgani uchun (`research_notes/texnik/02-kassa-ofd-markirovka.md`, 1-bo'lim: 943-son qaror, 1-ilova, 31-band), kassir doim qancha chek sinxronlanmaganini va vaqt chegarasigacha necha soat qolganini ko'rishi kerak.
4. **Bir qo'l bilan ishlash** — POS asosiy ekranlarida barcha harakat tugmalari ekranning pastki yarmida, katta (taxmin: kamida 56×56 dp) teginish maydoni bilan joylashtiriladi; raqamli summa kiritish va to'lov tasdiqlash bosh barmoq zonasida. Aniq o'lcham standarti manbada yo'q — **taxmin**.
5. **Asl belgisi markirovkasi skanerlash xatosi — yuqori ehtimolli muammo**: manba (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 6-band) bu raqamni **yetkazib berish zanjiridagi yuklarning 80–90%i skanerlash xatosi bilan qaytishi** sifatida beradi (yuk/partiya darajasida — har bir kassadagi yakka skanerlash urinishining xato ehtimoli emas). Shunga qaramay, bu umumiy nosog'lom holatni ko'rsatadi, shuning uchun har bir skanerlash ekranida majburiy "qayta urinish" va eskalatsiya yo'li UX darajasida ko'zda tutiladi (1.7-bo'lim) — qo'lda **MXIK** (tovar klassifikator kodi) kiritish mumkin, lekin **DataMatrix (markirovka) kodini** qo'lda kiritish huquqiy/texnik jihatdan ruxsat etilganmi — **ochiq savol**.
6. **O'zbek (lotin) — asosiy til, rus — ikkinchi til**; til almashtirish tugmasi barcha ekranlarning yuqori panelida bir xil joyda. Fiskal chek — ikki tilli (o'zbek/rus), har doim (qaror #29, 1.4-bo'lim).
7. **Uskunalar**: shtrix-kod skaneri ko'pincha USB HID "Keyboard Wedge" rejimida ishlaydi (qo'shimcha drayversiz, klaviatura kabi), chek printerlari ESC/POS protokolida (`research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`, 3-bo'lim) — bu UI'da "skaner fokus maydoni" va "chekni qayta chop etish" tugmasi sifatida aks etadi. Tarozi protokoli manbada aniqlanmagan, shuning uchun har bir og'irlik bilan sotiladigan tovar ekranida **qo'lda og'irlik kiritish** zahira maydoni bor.
8. **Davlat hisobotini solishtirish** (BO-10) — 2026 yildagi eng markaziy yangi ekran: har bir soliq turi uchun alohida **5 kalendar kunlik** hisoblagich (Soliq kodeksi 81-moddasi, O'RQ-1108, lex.uz/docs/-7944527) va qator darajasidagi farq ko'rsatuvi.
9. **AI yordamchi chat** (BO-13) — "kod hisoblaydi, AI tushuntiradi" tamoyili asosida: javobdagi raqam har doim backend hisob-kitobidan, AI faqat o'zbek tilida tushuntirish matnini yozadi (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 4-bo'lim).
10. Tezlik maqsadlari (masalan, "chek N soniyada yopilishi kerak") tadqiqotda raqam bilan tasdiqlanmagan — barcha vaqt ko'rsatkichlari ushbu hujjatda **taxmin** deb belgilangan, faqat umumiy tamoyil ("kam teginish, kam skroll") amal qiladi.

---

## 1. UX qoidalari (umumiy, barcha ekranlarga tegishli)

### 1.1 Tezlik (taxmin)
- Sotuv cheki — kamida teginish sonini minimal qilish: mahsulot qo'shish → chegirma (ixtiyoriy) → to'lov → chek. To'rt qadamdan oshmasligi maqsad qilinadi (**taxmin**, manbasiz raqam).
- Qidirish maydonlari avtomatik fokusda, skaner natijasi qo'shimcha tasdiqlashsiz ro'yxatga qo'shiladi.

### 1.2 Bir qo'l bilan boshqarish
- POS ekranlarida asosiy harakat tugmalari (TO'LOV, BEKOR, CHEGIRMA, SKANERLASH) pastki 40% zonada, katta o'lchamda.
- Raqamli klaviatura (summa, miqdor kiritish) ekran markazida, bosh barmoq bilan yetadigan joyda.
- Ko'p bosqichli dialog (masalan, tasdiqlash oynasi) o'rniga pastdan chiqadigan panel (bottom sheet) afzal — ikkinchi qo'l bilan ushlab turish shart bo'lmasin.

### 1.3 Offline indikatori (majburiy, har bir POS ekranida)
- Status panelida doimiy ko'rinadigan uch holat: 🟢 Onlayn / 🟡 Offlayn (sinxronlanmagan N chek) / 🔴 Offlayn, muddat yaqinlashdi. 48 soatlik qonuniy chegaraning o'zi `research_notes/texnik/02-kassa-ofd-markirovka.md`dan (943-son qaror, 1-ilova, 31-band), lekin rang o'zgarishi uchun "necha soat qolganda" ogohlantirish boshlanishi — **taxmin**: `research_notes/texnik/04-arxitektura-va-stack.md` (2.4-bo'lim) faqat "kassa X soat sinxronlanmasa, markaziy tizim ogohlantirish yuborishi shart" deb umumiy signal haqida yozadi, aniq soat raqamini belgilamaydi.
- Offlayn holatda markirovkalangan tovar sotuvida maxsus belgi: narx qurilmada ma'lum bo'lsa — "Offlayn sotildi, CRPT tekshiruvi kutilmoqda" (keyinroq tekshirish); narx ma'lum bo'lmasa — "Offlaynda sotib bo'lmaydi, narx noma'lum" (taqiqlangan), `03-modullar-talablari.md` M01 Offline xatti-harakati.

### 1.4 Til (o'zbek/rus)
- Standart til — o'zbek (lotin). Til almashtirish — yuqori o'ng burchakda bir xil belgi (masalan "UZ/RU") barcha ekranlarda.
- (qaror #29) **Chek tili — ikki tilli (bilingual) qator**: fiskal chek (shu jumladan QR orqali elektron chek) **o'zbek (lotin) va rus tilida bir vaqtda** chiqariladi — har bir tovar qatorida ikki nom "o'zbekcha / ruscha" formatida ko'rsatiladi (masalan "non / хлеб"), rus nomi (`products.name_ru`, ixtiyoriy) kiritilmagan tovarlarda faqat o'zbekcha nom ko'rsatiladi. Chekning sarlavha/yakun matnlari (masalan "Jami" / "Итого", "Naqd" / "Наличные", "Qaytim" / "Возврат") ham ikki tilda chiqariladi; fiskal rekvizitlar (OFD talab qilgan maydonlar — STIR, MXIK, QQS, fiskal belgi) OFD talab qilgan formatda, o'zgarmaydi. Davlat tili talabi buzilmaydi, chunki o'zbekcha qator har doim birinchi va mavjud. Interfeys (UI) tili almashtirish tugmasi (yuqorida) bundan mustasno va mustaqil — u faqat ekran matnini almashtiradi, chekka ta'sir qilmaydi. Batafsil shablon — `08-dizayn-tizimi.md`, chek shabloni bo'limi; maydon — `07-ekran-tafsilotlari.md`, BO-05 (`nameRu`).

### 1.5 Katta shrift va kontrast
- Narx va summa raqamlari — ekrandagi eng katta shrift (do'kon yorug'ligi/charchagan ko'z uchun, **taxmin**: boshqa matndan kamida 1.5x katta).
- Yuqori kontrast ranglar (oq fonda qora/to'q ko'k matn), skaner xatosi — qizil, muvaffaqiyat — yashil belgilar bilan.

### 1.6 Uskunalar: skaner, tarozi, printer
- **Shtrix-kod/markirovka skaneri**: USB HID keyboard-wedge rejimi — har qanday matn kiritish maydoni skanerlash natijasini qabul qiladi, lekin asosiy sotuv ekranida alohida "faol skaner maydoni" ajratiladi, shunda tasodifiy boshqa maydonga tushib ketmaydi (`06-fayl`, 3-bo'lim).
- **Chek printeri (ESC/POS)**: "Chekni qayta chop etish" tugmasi har doim mavjud (printer qog'oz tugashi/bog'lanish uzilishi odatiy holat); printer ulanmagan bo'lsa, ekranda aniq xato va "QR orqali elektron chek" muqobili taklif etiladi (muqobil — **taxmin**, manbada yo'q).
- **Tarozi**: avtomatik protokol integratsiyasi tasdiqlanmagan (`06-fayl`, 3-bo'lim: "aniq protokol nomi topilmadi") — shu sabab UX darajasida **har doim** "og'irlikni qo'lda kiriting" maydoni zahira sifatida ko'rsatiladi, avtomatik qiymat kelganda bu maydon oldindan to'ldiriladi.
- **iPhone/iPad (iOS)** (qaror #21): kassa/back-office iOS'da **o'rnatilgan PWA** sifatida (Home Screen'ga qo'shilgan) ishlaydi. Chek chop etish faqat **bulut-print (cloud-print) printer** (masalan Star CloudPRNT, Epson Server Direct Print — **taxmin**, aniq model tasdiqlanmagan) orqali yoki **elektron chek** (QR-kod/Telegram orqali yuborish) bilan mumkin — iOS Safari/PWA USB/Bluetooth printer ulanishini qo'llab-quvvatlamaydi. **Chrome/Edge (Windows, Android)** — USB, Bluetooth, tarmoq (LAN/Wi-Fi) va bulut printerlarning barchasini qo'llab-quvvatlaydi. Bulut-print printerlarining O'zbekistonda mavjudligi/narxi va faqat-elektron-chek bilan cheklanishning fiskal/huquqiy ruxsati — **ochiq savol** (pastda).

### 1.7 Markirovka (Asl belgisi) maxsus holati
- Manbada keltirilgan 80–90% xato ko'rsatkichi **yetkazib berish zanjiridagi yuklar darajasida** (`00-xulosa-va-ochiq-savollar.md`, 6-band), har bir alohida skanerlash urinishining xato ehtimoli sifatida emas (Asosiy xulosalar #5). Shunga qaramay, markirovka skanerlashning umuman nosog'lom ekanligini ko'rsatadi, shuning uchun har bir markirovka skaneri ekranida (POS-02, POS-08, POS-09, POS-10): (a) birinchi urinish muvaffaqiyatsiz bo'lsa avtomatik qayta urinish, (b) 2-3 muvaffaqiyatsiz urinishdan keyin "qo'lda MXIK kodini kiriting" maydoni ochiladi — **MXIK (IKPU)** 17 raqamli tovar klassifikator kodi (`research_notes/texnik/02-kassa-ofd-markirovka.md`, chek rekvizitlari bo'limi), **markirovka (DataMatrix) kodi emas** — qo'lda kiritilsa tovar tanib olinadi, lekin Asl belgisi "chiqarish" operatsiyasi bajarilmaydi, (c) **DataMatrix (markirovka) kodini qo'lda kiritish — faqat online, va faqat `POST /marking/verify` muvaffaqiyatli tasdiqlasa**: shundan keyingina tovar markirovkasi haqiqiy deb qabul qilinadi va sotuvga qo'shiladi; **offline rejimda qo'lda kiritilgan kod bilan sotish taqiqlanadi** (aks holda bu 2026-07-01'dagi avtomatik tekshirish talabini chetlab o'tish yo'li bo'lib qolardi — `spec/tarix/tekshiruv/qabul-7-ekran-api.md`, R-02), (d) kod butunlay o'qilmasa, menejerga eskalatsiya tugmasi ko'rsatiladi.

---

## 2. Rollar va platforma xaritasi

| Rol | Asosiy platforma | Qo'shimcha platforma | Izoh |
|---|---|---|---|
| **Kassir** | Android POS | — | Kundalik ish — faqat kassa ilovasi, BO'ga kirish kerak emas |
| **Omborchi** | Android POS (skaner rejimi) | Back-office PWA (ombor hisobotlari) | Kirim, ko'chirish, inventarizatsiya — skaner bilan Android; qoldiq ko'rish — PWA |
| **Menejer** | Back-office PWA | Android POS (narx tekshirish, tezkor nazorat) | Narx, xarid, nasiya, hisobotlarni boshqaradi |
| **Buxgalter** | Back-office PWA | — | QQS, buxgalteriya, davlat hisobotini solishtirish |
| **Egasi** | Back-office PWA (dashboard) | — | Mobil brauzerda ham ochiladi (PWA, responsive), alohida ilova emas |

(qaror #21) Back-office PWA (va Egasi dashboard) iPhone/iPad'da ham **o'rnatilgan PWA** sifatida (Home Screen) ishlaydi; kassa funksiyasida chek chop etish uchun qurilma/printer cheklovlari — 1.6-bo'lim.

---

## 3. Android POS ekranlari (POS-nn)

| ID | Rol | Modul | Maqsad | Asosiy elementlar | Holatlar |
|---|---|---|---|---|---|
| POS-01 | Kassir | M01 | Kassaga kirish, smena ochish | Login/PIN, kassa/filial tanlash, "Smena ochish" tugmasi, boshlang'ich naqd summa kiritish; (qaror #34) "PIN/parolni unutdim" havolasi — OTP orqali tiklash, kod birinchi navbatda **Telegram bot**ga, Telegram ulanmagan bo'lsa **SMS** (zaxira) ga yuboriladi | Bo'sh: boshlang'ich holat; Xato: PIN noto'g'ri, kassa band; **Obuna muddati tugagan**: tenant `restricted` holatida — login butunlay rad etiladi, "Obuna muddati tugagan" xabari, Click/Payme to'lov havolasi va (qaror #20, #34) "Ma'lumotlarimni yuklab olish" (Telegram bot/zaxira SMS kod bilan tasdiqlangan eksport) havolasi ko'rsatiladi (US-M17-03); shu holatda ham, lokautdan oldin yaratilgan, hali yuborilmagan cheklar fon rejimida (`sync.drain`) OFD'ga yuborilishda davom etadi — kassir ekranida ko'rinmaydi, yangi sotuv ochilmaydi (qaror #19); Offline: PIN lokal tekshiriladi (agar qurilma litsenziyasi muddati o'tmagan bo'lsa), keyin sinxronlanadi — litsenziya muddati o'tgan bo'lsa qurilma mahalliy qulflangan bo'ladi |
| POS-02 | Kassir | M01, M03, M09 | Asosiy sotish paneli — mahsulot qo'shish, chegirma, jami summa | Skaner maydoni, mahsulot ro'yxati (miqdor/narx), qidiruv, chegirma tugmasi, jami summa, "To'lov" tugmasi | Bo'sh: "Chekni boshlang" holati; Xato: mahsulot topilmadi / markirovka o'qilmadi; Offline: status panel 🟡/🔴 |
| POS-03 | Kassir | M01 | To'lov usulini tanlash va hisoblash | Naqd/**Karta (qo'lda belgilash)**/**Yagona QR (UzQR)**/Payme/Click/Uzum/Nasiya tugmalari — (qaror #30) "Nasiya" tanlansa (to'liq yoki aralash) fiskal chek darhol chiqmaydi, nasiya qismi qarz to'langanda chek oladi, qaytim hisoblagichi, "Tasdiqlash"; QR/Click/Payme to'lovida fiskal chekni kim chiqarishi (to'lov tizimi "komissioner" sifatida yoki merchant kassasi) huquqiy jihatdan ziddiyatli (`research_notes/texnik/03-efaktura-va-tolov.md`, 2.5-bo'lim) — UI bu ikki holatni ajratmaydi, **ochiq savol**. "Karta" tugmasi bosilganda — mustaqil (kassa tizimiga integratsiyalanmagan) bank terminali orqali to'lov qabul qilingani qo'lda belgilanadi, ixtiyoriy **"terminal operatsiya raqami"** maydoni ochiladi; bu online va offline'da ham mavjud (`03-modullar-talablari.md`, US-M01-01) | Bo'sh: summa 0; Xato: yetarli naqd yo'q, to'lov tizimi javob bermadi; Offline: **UzQR/Payme/Click/Uzum QR to'lovlari o'chirilgan** — barchasi onlayn tasdiq (bank/push/Prepare-Complete/webhook) talab qiladi, provayder tasdig'isiz sotuvni yopishga manbada asos yo'q (`03-efaktura-va-tolov.md`, 2.1–2.3-bo'lim); offlaynda **naqd, qo'lda belgilangan "Karta" va nasiya** mavjud (qaror #23, tavsiya #6) |
| POS-04 | Kassir | M01 | Chekni chop etish / QR orqali yuborish | "Chop etish", "QR chek", "Qayta chop etish ('NUSXA' belgisi, audit)", yangi chek boshlash | Bo'sh: —; Xato: printer ulanmagan/qog'oz tugagan; Offline: chek lokal saqlanadi, fiskal belgisi "offlayn" deb ko'rsatiladi |
| POS-05 | Kassir | M02 | Mijozdan tovar qaytarish | Asl chekni qidirish (raqam/QR), qaytariladigan tovar(lar), sabab tanlash, balans/naqd qaytarish | Bo'sh: chek topilmagan; Xato: chek allaqachon qaytarilgan; Offline: oddiy tovar — qaytarish lokal yoziladi, serverga sinxronda tasdiqlanadi; **markirovkalangan tovar — "Qaytarish" tugmasi offline rejimda bloklanadi** ("Qaytarish uchun internet kerak" xabari), faqat online'da mumkin |
| POS-06 | Kassir | M08 | Nasiyaga sotish | Mijoz tanlash/qo'shish, joriy qarz va limit ko'rsatish, to'lov muddati, tasdiqlash; mijoz yuridik shaxs (B2B) bo'lsa — chiquvchi e-faktura avtomatik yaratilishi haqida eslatma (Buxgalter BO-15'da E-IMZO bilan imzolaydi, BP-03) | Bo'sh: mijoz tanlanmagan; Xato: limitdan oshib ketdi — **Menejer PIN/tasdig'i talab qilinadi**, sotuv Menejer tasdiqlamaguncha yakunlanmaydi (`02-rollar-va-ssenariylar.md`ga mos; Menejer uzoqda bo'lsa so'rov BO-16 navbatiga tushadi); Offline: limit oxirgi sinxron ma'lumot asosida tekshiriladi, Menejer PIN'i lokal tasdiqlaydi, server qayta tekshiradi |
| POS-07 | Kassir | M01 | Smena yopish, Z-hisobot | Kunlik savdo jamlanmasi, naqd/karta/nasiya taqsimoti, "Smenani yopish" | Bo'sh: savdo bo'lmagan; Xato: sinxronlanmagan cheklar bor — ogohlantirish; Offline: Z-hisobot lokal shakllanadi, OFD'ga ulanganda yuboriladi |
| POS-13 | Kassir, Egasi | M08 | Qarz daftari (tezkor) (qaror #30) | Mijoz qidirish (ism/telefon), joriy qarz, oxirgi yozuvlar (sana, summa, tovarlar), "To'lov qabul qilish" (**to'langanda fiskal chek chiqadi**, `debt_settlement`), "Qarz yozish" (fiskal chek **chiqarilmaydi**, `deferred`); bosh ekranda doimiy "📒 Qarz daftari" tugmasi | Bo'sh: qarzdor yo'q; Xato: telefon formati noto'g'ri; Offline: to'liq ishlaydi (lokal baza), sinxron belgisi ko'rsatiladi |
| POS-14 | Kassir | M16 | Kassaga pul qo'yish / kassadan pul olish | Summa, sabab (Egasi oldi / Inkasso / Xarajat / Boshqa), izoh; katta summada Menejer/Egasi PIN | Xato: PIN noto'g'ri; Offline: to'liq ishlaydi |
| POS-15 | Kassir | M16 | Smena yopishda naqdni sanash | Sanalgan naqd, kutilgan naqd, farq, izoh, **shu smenadagi "karta" (qo'lda belgilangan) jami** alohida ko'rsatuvi; keyin POS-07 (Z-hisobot) | Xato: farq bor — izoh majburiy; Offline: to'liq ishlaydi |
| POS-08 | Omborchi | M07 | Yetkazib beruvchidan tovar qabul qilish (kirim) | Xaridnoma tanlash, shtrix-kod/markirovka skaneri, miqdor solishtirish (buyurtma vs kelgan), nomuvofiqlik belgilash | Bo'sh: xaridnoma tanlanmagan; Xato: markirovka o'qilmadi (1.7-bo'lim), miqdor mos kelmadi; Offline: skanerlash/sanash lokal davom etadi, lekin **"QABULNI YAKUNLASH" internet talab qiladi** — offline qabul (kirim) voqeasi yo'q |
| POS-09 | Omborchi | M06 | Omborlar orasida tovar ko'chirish | Manba/manzil ombor tanlash, skanerlash, miqdor, "Yuborish" | Bo'sh: ombor tanlanmagan; Xato: qoldiq yetarli emas; Offline: harakat lokal yoziladi, qoldiq serverda qayta hisoblanadi; markirovkalangan tovar ham o'z filiallar/omborlari orasida offline ko'chirilishi **ruxsat etiladi** (jo'natish va qabul), Asl belgisiga keyin sinxronlanadi |
| POS-10 | Omborchi | M05 | Inventarizatsiya — jismoniy sanash | Tovar ro'yxati (hali sanalmagan/sanalgan), skanerlash, qo'lda miqdor kiritish, farq ko'rsatuvi | Bo'sh: sanash boshlanmagan; Xato: tizimda yo'q shtrix-kod; Offline: sanash to'liq lokal, yakunida sinxron |
| POS-11 | Kassir, Omborchi | M09 | Mahsulot va narxni tez qidirish | Qidiruv (nom/kod/shtrix-kod), narx, qoldiq ko'rsatuvi (faqat ko'rish) | Bo'sh: natija yo'q; Xato: —; Offline: oxirgi sinxronlangan narx/qoldiq ko'rsatiladi, "oxirgi yangilanish" vaqti bilan |
| POS-12 | Barcha (tizim) | — | Offline/sinxronizatsiya holati va tafsilotlari | Sinxronlanmagan cheklar/hujjatlar ro'yxati, 48 soat hisoblagichi, "Qayta urinish" tugmasi | Bo'sh: hammasi sinxron; Xato: sinxronizatsiya muvaffaqiyatsiz; Offline: asosiy holat — ro'yxat va hisoblagich faol |

---

## 4. Back-office PWA ekranlari (BO-nn)

| ID | Rol | Modul | Maqsad | Asosiy elementlar | Holatlar |
|---|---|---|---|---|---|
| BO-01 | Barcha | — | Kirish (login), tenant/filial tanlash | (qaror #34) Kirish ikki usulda: **telefon + parol** yoki **"Google bilan kirish"** (OIDC tugmasi); filial tanlash, til almashtirish; "Parolni unutdim" havolasi — OTP kod birinchi navbatda **Telegram bot**ga, ulanmagan bo'lsa **SMS**ga (zaxira) yuboriladi, shu kod bilan yangi parol o'rnatiladi | Bo'sh: —; Xato: parol noto'g'ri; **Obuna muddati tugagan**: tenant `restricted` holatida — har qanday login (shu jumladan to'g'ri parol yoki Google bilan ham) rad etiladi, "Obuna muddati tugagan" xabari + Click/Payme to'lov havolasi ko'rsatiladi, to'lov qilinishi bilan kirish darhol ochiladi (US-M17-03); (qaror #20, #34) shu sahifada **"Ma'lumotlarimni yuklab olish"** havolasi ham ko'rsatiladi — bosilganda tasdiqlash kodi Telegram botga (ulangan bo'lsa) yoki SMS'ga (zaxira) yuboriladi, kod tasdiqlangandan keyin to'liq eksport tayyorlanadi (login ochilmaydi); Offline: PWA offline ombor/hisobot ko'rishga ruxsat beradi (IndexedDB, `04-fayl`), lekin yangi kirish internetsiz cheklangan |
| BO-02 | Egasi, Menejer | M12 | Dashboard — kunlik/haftalik savdo, qoldiq, qarzdorlik umumiy ko'rinishi | Savdo grafigi, top mahsulotlar, kassa holati (filiallar bo'yicha), ogohlantirishlar paneli | Bo'sh: ma'lumot yo'q (yangi tenant); Xato: hisoblash xatosi; Offline: oxirgi sinxronlangan ma'lumot "N daqiqa oldin" belgisi bilan |
| BO-03 | Menejer, Omborchi | M04 | Ombor qoldig'ini ko'rish va boshqarish | Ombor/filial tanlash, tovar ro'yxati (qoldiq, minimal daraja), filtr/qidiruv; **'Ko'chirishlar' tabi** (US-M06-03): holat (yo'lda / qabul qilindi / farq bilan), yuborilgan vaqt, markirovkali tovar uchun 72 soat hisoblagichi, kechikkanlar qizil; yaroqlilik muddati yaqin partiyalar belgisi (US-M04-06) | Bo'sh: ombor bo'sh; Xato: —; Offline: faqat ko'rish, IndexedDB'dagi oxirgi nusxa |
| BO-04 | Menejer, Omborchi, Buxgalter | M07 | Xaridnoma yaratish, yetkazib beruvchiga to'lov | Yetkazib beruvchi tanlash, tovar ro'yxati, **AI-03: qog'oz yuk xati/faktura fotosidan avtomatik to'ldirish** (qaror #16) — faqat QQS'ga tortilmagan/norasmiy yetkazib beruvchi yoki texnik uzilish holatida (standart QQS to'lovchilar orasidagi e-faktura EDO operatoridan import qilinadi, OCR qilinmaydi — `spec/kod-uchun/09-ai-funksiyalar.md`, AI-03), tasdiqlash, **"Yetkazib beruvchiga to'lov" bo'limi** (summasi, muddati, to'lov qayd etish — BP-12), **'Yetkazib beruvchiga qaytarish'** (US-M07-05) | Bo'sh: yangi xaridnoma; Xato: AI OCR noto'g'ri o'qidi — qo'lda tuzatish shart; Offline: PWA'da yangi xaridnoma yaratish cheklangan (internet talab qilinadi) |
| BO-05 | Menejer | M09, M03 | Narxlar va chegirma qoidalarini boshqarish | Tovar narxi (chakana/optom), chegirma qoidasi, narx tarixi | Bo'sh: narx belgilanmagan; Xato: manfiy narx/chegirma; Offline: faqat ko'rish |
| BO-06 | Menejer, Buxgalter | M08 | Nasiya/qarzdorlar ro'yxati, eslatmalar va qarz undirish | Qarzdorlar ro'yxati (summa, muddat), **AI-06: debitorlik eslatma matni** (LLM generatsiya, `spec/kod-uchun/09-ai-funksiyalar.md`: "kod hisoblaydi, AI tushuntiradi") — matn avtomatik yuborilmaydi, Menejer/Buxgalter ko'rib chiqib tasdiqlaydi, **"To'lov qabul qilish"** tugmasi (mijozdan nasiya qarzini yopish, summa/sana — BP-11); (qaror #30) to'lov qabul qilinganda to'langan summaga **fiskal chek** chiqariladi (`debt_settlement`), tovar qatorlari yopilgan sotuv(lar)dan proporsional | Bo'sh: qarzdor yo'q; Xato: aloqa ma'lumoti yo'q; Offline: faqat ko'rish |
| BO-07 | Buxgalter | M10 | QQS ichki hisob-kitobi | Davr tanlash, QQS stavkalari (12%, 0%), ichki hisoblangan summa, **davlat hisoboti holati** (2026 dan deklaratsiyani davlat tuzadi — bu ekran endi "deklaratsiya topshirish" emas, ichki hisob-kitobni kuzatish; yakuniy solishtirish BO-10'da); **kutilayotgan QQS krediti** — qizil e-fakturalar bo'yicha to'lovgacha hisobga olinmagan QQS summasi va davr ulushi (VM 830, ≤10%), US-M10-03 | Bo'sh: davr yopilmagan; Xato: hisoblashda nomuvofiqlik; Offline: faqat ko'rish |
| BO-08 | Buxgalter | M11 | Buxgalteriya jurnali, provodkalar | Hisob rejasi bo'yicha jurnal, filtr (sana/hisob), eksport | Bo'sh: yozuv yo'q; Xato: balans mos kelmadi; Offline: faqat ko'rish |
| BO-09 | Egasi, Menejer, Buxgalter | M12 | Hisobotlar markazi (savdo, ombor, buxgalteriya, QQS) | Hisobot turi tanlash, davr, eksport (PDF/Excel) | Bo'sh: ma'lumot yo'q; Xato: eksport muvaffaqiyatsiz; Offline: faqat oxirgi keshlangan hisobot |
| BO-10 | Buxgalter, Egasi | M12 | **Davlat hisobotini ichki hisob bilan solishtirish** | Soliq turi bo'yicha tablar: **QQS va aylanma solig'i** — ichki ma'lumot bilan to'liq solishtiriladi (MVP modullari buni qoplaydi, `spec/kod-uchun/04-biznes-jarayonlar.md`, Asosiy xulosalar #1); QQS tabida ichki ustunda **"kutilayotgan kredit"** alohida qator; **mulk, yer, JShDS, ijtimoiy soliq** — faqat davlat ko'rsatgan raqam ko'rsatiladi, ichki ustun "Keyingi bosqich — ichki ma'lumot yo'q" belgisi bilan bo'sh qoladi (asosiy vositalar/kadr modullari MVP'da yo'q, `spec/README.md`). Har bir tur uchun **5 kalendar kunlik** hisoblagich (boshlanish nuqtasi — **davlat hisoboti tuzilgan/e'lon qilingan payt**, lekin qonuniy topshirish muddatidan oshmaydi — `04-biznes-jarayonlar.md`, BP-08), **1-/3-/4-kunlarda ogohlantirish** (taxmin, aniq kun manbada yo'q), **AI-05: tafovutni tushuntirish** (`spec/kod-uchun/09-ai-funksiyalar.md`), "Kutilmoqda"/"Farq topildi"/"Tuzatish yuborildi"/"Muddat o'tdi — avtomatik qabul qilindi" holat belgisi. Qator-ma-qator farq jadvali — **faraz**: davlatdan hujjat (chek/e-faktura) darajasidagi ma'lumot kelishini taxmin qiladi, tasdiqlanmagan (`00-xulosa-va-ochiq-savollar.md`, texnik xavf #2, ochiq savol #7) — shu sabab **yig'ma (davr/toifa) darajasidagi ko'rinish ham zahira sifatida** ko'rsatiladi, qaysi daraja kelishi aniqlanmaguncha ikkisi ham **ochiq savol**. "E-IMZO bilan tuzat" havolasi — tuzatishni yuborish mexanizmi manbada tasvirlanmagan, **ochiq savol** | Bo'sh: davlat hisoboti hali e'lon qilinmagan ("Kutilmoqda"); Xato: farq topildi; **Muddat o'tdi: "avtomatik qabul qilindi" belgisi** (5 kalendar kun ichida javob berilmagan); Offline: faqat ichki ustun ko'rinadi, davlat ustuni "internet kerak" bilan bo'sh |
| BO-11 | Egasi | M13 | Foydalanuvchilar, huquqlar va sessiyalar | Xodim ro'yxati (telefon, ism, rol(lar), filial(lar) — US-M13-04), rol tayinlash (Kassir/Omborchi/Menejer/Buxgalter), operatsiya cheklovlari, har xodim qatorida **'Bloklash/Blokdan chiqarish'** va **'Parol/PIN tiklash'** amallari (US-M13-05/06); **'Qurilmalar' tabi**: kassa, oxirgi sinxron vaqti, 'Bekor qilish' (yo'qolgan/o'g'irlangan) — `kod-uchun/16-offline-sync.md` §9; yangi **'Sessiyalar' tabi**: har xodimning faol login sessiyalari (qurilma turi, kirgan vaqt, oxirgi faollik), 'Bekor qilish' tugmasi (US-M13-07) — bu foydalanuvchi login sessiyalari uchun, 'Qurilmalar' tabidagi kassa POS qurilmalaridan farqli; texnik asos `spec/kod-uchun/14-autentifikatsiya-oauth2.md` | Bo'sh: faqat Egasi; Xato: bir xil login takror; Offline: faqat ko'rish |
| BO-12 | Egasi | M14 | Filiallar boshqaruvi | Filiallar ro'yxati, har biri bo'yicha konsolidatsiyalangan hisob, yangi filial qo'shish | Bo'sh: bitta filial; Xato: —; Offline: faqat ko'rish |
| BO-13 | Egasi, Menejer, Buxgalter | AI-01 | AI yordamchi — savol-javob chat | Chat oynasi, tez savollar ("Bugun qancha foyda?", "Qaysi tovar tugayapti?"), javobda manba/hisob-kitob ko'rsatuvi | Bo'sh: suhbat boshlanmagan; Xato: AI javob bera olmadi — "aniq emas" deb ko'rsatiladi (raqam o'ylab topilmaydi); Offline: AI chat ishlamaydi (internet/LLM API talab qiladi) |
| BO-14 | Egasi | — | Tenant/do'kon sozlamalari | Do'kon nomi, til, valyuta, soliq rejimi, integratsiyalar holati (OFD, e-faktura, Asl belgisi) | Bo'sh: sozlanmagan; Xato: integratsiya ulanmagan; Offline: faqat ko'rish |
| BO-15 | Buxgalter | M07, M10 | Kiruvchi va chiquvchi e-faktura markazi | Kiruvchi e-fakturalar ro'yxati (**Faktura.uz'dan — MVP'da yagona operator, Didox keyinroq**, BP-01), har biri uchun qabul/rad etish, E-IMZO bilan imzolash, **VM Qarori №830-son xavf-belgisi** (yashil/qizil — qizil bo'lsa QQS krediti to'lovgacha kechiktirilishi haqida ogohlantirish, `research_notes/texnik/03-efaktura-va-tolov.md`, 1.2-bo'lim); B2B nasiya sotuvidan avtomatik yaratilgan chiquvchi e-fakturalar ro'yxati (holati: yaratildi/imzolandi/yuborildi, BP-03); **"Chek asosida e-faktura chiqarish"** tugmasi — Buxgalter asl fiskal chekni (raqam/sana bo'yicha) qidirib tanlaydi va shu chekka bog'langan (`einvoices.related_doc`) yangi chiquvchi e-faktura yaratadi (BP-13, US-M01-06); QQS qayta hisoblanmasligi ekranda aniq ko'rsatiladi | Bo'sh: faktura yo'q; Xato: E-IMZO imzolashda xato (sertifikat/parol); Offline: faqat ko'rish, imzolash internet talab qiladi (E-IMZO serverga bog'lanadi) |
| BO-16 | Egasi, Menejer | M02, M03, M08, M09, M16 | Tasdiqlash navbati (limitdan oshgan so'rovlar) | Kutilayotgan so'rovlar ro'yxati (turi: chegirma/qaytarish/nasiya/**narx o'zgarishi (US-M09-02)**/**limitdan katta pul olish (US-M16-01)**, kim so'rayotgani, summa, sabab), "Tasdiqlash"/"Rad etish" tugmalari, PIN orqali tasdiqlash | Bo'sh: navbat bo'sh; Xato: PIN noto'g'ri; Offline: PWA'da yangi tasdiqlash cheklangan — Menejer Android POS'da PIN bilan inline tasdiqlaydi (masalan POS-06) |
| BO-17 | Egasi, Menejer, Buxgalter | M15 | Xarajatlar | Xarajatlar ro'yxati (sana, toifa, summa, manba), "Xarajat qo'shish", takrorlanuvchi xarajatlar, toifalar, foto biriktirish | Bo'sh: xarajat yo'q; Offline: faqat ko'rish |
| BO-18 | Menejer | M09 | Yorliq va shtrix-kod chop etish | Narxi o'zgargan tovarlar ro'yxati, shablon tanlash, ichki shtrix-kod yaratish, chop etish | Xato: printer topilmadi; Offline: lokal printer bilan ishlaydi |
| BO-19 | Egasi | M17 | Obuna va to'lov | **Yagona tarif: 99 000 so'm/oy** (hammasi narxga kiradi — tarif tanlash yo'q), joriy davr/muddat, faol kassalar soni va AI limiti sarfi, **"Qo'shimcha kassa qo'shish"** (+39 000 so'm/kassa/oy, taxmin), oylik/yillik (−20%) almashtirish, Click/Payme bilan to'lash, to'lov tarixi | Xato: to'lov o'tmadi; Offline: faqat ko'rish |
| BO-20 | Egasi, Menejer | M18 | Telegram va bildirishnomalar | Telegram ulash (QR/havola), kunlik hisobot vaqti, ogohlantirish turlarini yoqish/o'chirish | Xato: bot ulanmadi; Offline: — |
| BO-21 | Yangi foydalanuvchi | M17 | Ro'yxatdan o'tish va birinchi sozlash (qaror #34) | **Telefon + parol (Telegram bot/zaxira SMS OTP bilan tasdiqlash) yoki "Google bilan kirish"** → do'kon nomi, faoliyat turi → boshlang'ich tovarlar (US-M04-04) → boshlang'ich qarzlar (US-M08-07) → OFD/e-faktura ulash yo'riqnomasi (keyinroq ham mumkin) | Xato: OTP kelmadi (Telegram ham, SMS zaxira ham); Offline: — |
| ADM-01 | Platforma admini | M17, M13 | Ichki admin panel | Tenantlar, obuna holati, to'lovlar, AI sarfi, muddatni qo'lda uzaytirish; tenant Egasi (owner) hisobini bloklash/blokdan chiqarish, parolini tiklash, faol sessiyalarini ko'rish/bekor qilish (US-M13-08) | — |

---

## 5. Asosiy oqimlar (UX nuqtai nazaridan, qisqa)

**Sotuv (naqd/karta/aralash naqd qismi):** POS-01 (smena ochiq) → POS-02 (mahsulot qo'shish, skaner) → POS-03 (to'lov usuli) → POS-04 (fiskal chek) → POS-02 (yangi chek).

**Nasiyaga sotish** (qaror #30): POS-02 → POS-06 (mijoz, limit tekshiruvi) → POS-03 (to'lov usuli = "Nasiya") → **POS-02'ga qaytish (yangi chek)** — to'liq nasiya bo'lsa POS-04 **ochilmaydi**, fiskal chek chiqarilmaydi (sotuv holati `deferred`). Aralash to'lovda (naqd+nasiya) naqd qismiga POS-04 ochiladi, nasiya qismi uchun yo'q.

**Qaytarish:** POS-05 (chekni topish) → tovar/sabab tanlash → naqd/balans qaytarish tasdiqlash.

**Kirim (xarid qabul):** BO-04 (xaridnoma yaratish, ofis) → BO-15 (kiruvchi e-faktura qabul/E-IMZO imzo) → POS-08 (ombor, jismoniy qabul, skanerlash) → BO-03 (qoldiq yangilanadi) → BO-04 (yetkazib beruvchiga to'lov, BP-12).

**Inventarizatsiya:** BO-03 (joriy qoldiqni ko'rish) → POS-10 (jismoniy sanash) → BO-03 (farq tasdiqlangandan keyin yangilanadi).

**Limitdan oshgan so'rov (chegirma/qaytarish/nasiya):** POS-02/05/06 (Kassir so'raydi) → Menejer yaqinda bo'lsa POS'da PIN bilan darhol tasdiqlaydi, aks holda BO-16 (tasdiqlash navbati) → natija POS ekraniga qaytadi.

**Nasiya qarzini undirish** (qaror #30): BO-06 (qarzdor tanlanadi) → "To'lov qabul qilish" → qarz kamayadi (BP-11) → **shu to'langan summaga fiskal chek chiqariladi** (`debt_settlement`, POS-13'da xuddi shunday) → BO-06'ga qaytish.

**Davlat hisobotini solishtirish:** Davlat hisoboti e'lon qilinadi → BO-10'da shu paytdan **5 kalendar kunlik** hisoblagich boshlanadi (qonuniy topshirish muddatidan oshmagan holda — Soliq kodeksi 81-moddasi, O'RQ-1108) → QQS/aylanma uchun avtomatik solishtirish, qolganlarida faqat davlat raqami ko'rsatiladi → farq bo'lsa 1-/3-/4-kunlarda Egasi/Buxgalterga ogohlantirish → Buxgalter BO-15'da tegishli hujjatlarni ko'rib chiqadi → E-IMZO orqali tuzatish (mexanizmi ochiq savol) yoki muddat o'tganda davlat shakllantirgan ko'rinishda avtomatik qabul.

---

## 6. Matnli (ASCII) wireframelar

### POS-01 — Kassaga kirish / Smena ochish

```
┌───────────────────────────────────────┐
│  ERP Kassa               [UZ/RU]  🔴   │
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
┌───────────────────────────────────────┐
│ 🟡 OFFLAYN · 3 chek kutmoqda · 22:41  │
├───────────────────────────────────────┤
│ Mijoz: tanlanmagan        [+ Mijoz]    │
│ ┌─────────────────────────────────┐   │
│ │ 1. Non "Bekhurmon"   x2   24 000 │   │
│ │ 2. Coca-Cola 1.5L    x1   18 000 │   │
│ │ 3. Sut "Oltin" 1L    x3   27 000 │   │
│ └─────────────────────────────────┘   │
│  [ 📷 Skanerlash ]   [ 🔍 Qidirish ]   │
├───────────────────────────────────────┤
│  JAMI:                   69 000 so'm   │
│  [ CHEGIRMA ]  [ BEKOR ]  [ TO'LOV ▶ ] │
└───────────────────────────────────────┘
Holat: Bo'sh — "Chekni boshlang, skanerlang" | Xato — "Markirovka
o'qilmadi, qayta urinilmoqda..." → 3 urinishdan keyin "Qo'lda kirit"
maydoni | Offline — status panel 🟡/🔴, TO'LOV tugmasi faol qoladi
BEKOR — qator o'chirish / chekni bekor qilish (`sales.void`), audit voqeasi
```

### POS-03 — To'lov usuli va hisoblash

```
┌───────────────────────────────────────┐
│ 🟡 OFFLAYN                   22:42    │
├───────────────────────────────────────┤
│         To'lanadigan: 69 000 so'm      │
│                                         │
│  [ 💵 NAQD ]  [ 💳 KARTA (qo'lda) ]    │
│  [ 📱 PAYME (o'chiq) ] [📱 CLICK (o'chiq)]│
│  [ 📱 UZUM (o'chiq) ]  [ 📒 NASIYA ]   │
│  Terminal operatsiya raqami (ixtiyoriy):│
│  [                              ]      │
│  ⓘ Elektron to'lovlar onlayn tasdiq    │
│    talab qiladi — offlaynda mavjud emas│
│                                         │
│  Olingan naqd:  [  100 000  ]          │
│  Qaytim:         31 000 so'm           │
│                                         │
│         [   TASDIQLASH   ]             │
└───────────────────────────────────────┘
Holat: Bo'sh — usul tanlanmagan | Xato — "Payme javob bermadi, qayta
urinish yoki naqd/karta/nasiya tanlang" | Offline — Payme/Click/Uzum tugmalari
o'chirilgan (kulrang), naqd/karta (qo'lda)/nasiya faol (`03-efaktura-va-tolov.md`,
2.1–2.3-bo'lim)
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
muvaffaqiyatsiz, 2 daqiqadan keyin qayta urinadi" | Offline — asosiy holat
```

### BO-02 — Egasi/Menejer dashboardi

```
┌──────────────────────────────────────────────────┐
│ ERP             Bugun ▾   Chilonzor-3 ▾   [UZ/RU] │
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
│ [QQS] [Aylanma] [Mulk*] [Yer*] [JShDS*] [Ijtimoiy*]│
│ * = faqat davlat raqami, ichki solishtirish yo'q   │
├──────────────────────────────────────────────────┤
│  QQS — 2026-yil sentyabr                          │
│  Holat: ⚠ FARQ TOPILDI                            │
│  Tuzatish uchun qoldi: 3 kalendar kun (18-okt,     │
│  qonuniy topshirish muddatidan oshmagan holda)     │
│                                                     │
│  Hujjat darajasi (ⓘ taxmin — davlatdan shu darajada│
│  ma'lumot kelishi tasdiqlanmagan, ochiq savol):    │
│  ┌────────────────────────────────────────────┐   │
│  │ Qator          Davlat     Ichki     Farq    │   │
│  │ E-faktura #882  480 000   480 000    0 ✓   │   │
│  │ E-faktura #883  120 000   96 000  -24 000 ⚠│   │
│  │ Chek #000481     18 000    18 000    0 ✓   │   │
│  └────────────────────────────────────────────┘   │
│  Yig'ma (davr) darajasi — zahira ko'rinish:        │
│  Davlat: 2 324 000   Ichki: 2 300 000  Farq: 24 000│
│                                                     │
│   [ Farqni ko'rib chiqish ]  [ Tuzatish — kanal    │
│                                 ochiq savol ]       │
└──────────────────────────────────────────────────┘
Holat: Bo'sh — davlat hisoboti hali e'lon qilinmagan ("Kutilmoqda")
| Xato — farq topildi (yuqoridagi ko'rinish) | Muddat o'tdi — "Avtomatik
qabul qilindi" belgisi (5 kalendar kun ichida javob berilmagan) | Offline —
faqat ichki ustun ko'rinadi, davlat ustuni "internet kerak" bilan bo'sh
```

### BO-13 — AI yordamchi chat

```
┌──────────────────────────────────────────────────┐
│  AI yordamchi                              [UZ/RU]│
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
yangi tasdiqlash cheklangan, Menejer Android POS'da PIN bilan inline
tasdiqlaydi
```

---

## Ochiq savollar

- **2.** Aniq teginish/vaqt maqsadlari (chek N soniyada yopilishi, tugma o'lchami dp'da, offline ogohlantirish qancha soat oldin boshlanishi) — hech bir tadqiqot faylida raqam yo'q, bu hujjatdagi barcha shunga o'xshash son ko'rsatkichlari **taxmin**.
- **5.** Tarozi bilan integratsiya protokoli aniqlanmagani sababli BO/POS ekranlarida "qo'lda og'irlik kiritish" doimiy zahira sifatida qoldirilgan — avtomatik integratsiya aniqlangach, UX qayta ko'rib chiqilishi kerak.
- **6.** AI chatning offlayn qisman ishlashi (masalan, oxirgi javoblarni keshlab ko'rsatish) — bu hujjatda "to'liq o'chirilgan" deb soddalashtirilgan, kelajakda UX tadqiqoti kerak bo'lishi mumkin.
- **7.** Davlat hisobotini solishtirish ekranidagi (BO-10) "farqni ko'rib chiqish" oqimining to'liq bosqichlari (kim tasdiqlaydi, qanday eskalatsiya) — `spec/kod-uchun/04-biznes-jarayonlar.md`, BP-08 bilan muvofiqlashtirilishi kerak.
- **8.** QR/Click/Payme to'lovida fiskal chekni kim chiqarishi (to'lov tizimi yoki merchant kassasi) — huquqiy ziddiyatli, POS-03/04'da ikki holat ajratilmagan (`03-efaktura-va-tolov.md`, 2.5-bo'lim).
- **9.** Davlat hisobotini solishtirish (BO-10) qator (hujjat) darajasida yoki faqat yig'ma (davr) darajasida ma'lumot berishi — tasdiqlanmagan, ikkisi ham UI'da zahira sifatida ko'rsatilgan; aniqlanguncha ochiq.
- **10.** BO-10'dagi tuzatish/e'tiroz yuborish mexanizmi (shakl, kanal) manbada tasvirlanmagan.
- **12.** Bulut-print (cloud-print) chek printerlarining O'zbekistonda mavjudligi/narxi va iOS'da faqat elektron (QR/Telegram) chek bilan cheklanishning huquqiy/fiskal ruxsati — ochiq savol (qaror #21, 1.6-bo'lim).

## Manbalar

- `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` — markirovka skanerlash xatosi (80–90%, yetkazib berish zanjiri darajasida), markaziy soliq oqimi
- `research_notes/texnik/02-kassa-ofd-markirovka.md` — 48 soatlik offlayn qoidasi (943-son qaror, 1-ilova, 31-band), fiskal modul xato kodlari, MXIK (17 raqam)
- `research_notes/texnik/03-efaktura-va-tolov.md` — Payme/Click/Uzum protokollari (onlayn tasdiq talabi), fiskal chekni kim chiqarishi ziddiyati (2.5-bo'lim), VM Qarori №830-son (e-faktura xavf-baholash)
- `research_notes/texnik/04-arxitektura-va-stack.md` — Android POS / PWA platforma qarori, offline-first event-log, davlat hisobotini solishtirish oqimi (6-bo'lim), offlayn markirovka xavfi (10-bo'lim)
- `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md` — skaner (USB HID keyboard-wedge), chek printeri (ESC/POS), tarozi protokoli noaniqligi
- `research_notes/texnik/08-mahsulot-modullari.md` — dastlabki 14 MVP modul ro'yxati (tarixiy; joriy 18 modul ro'yxati — `spec/README.md`, `03-modullar-talablari.md`)
- `spec/README.md` — umumiy qoidalar va asosiy qarorlar
- `spec/kod-uchun/02-rollar-va-ssenariylar.md` — rollar, huquqlar matritsasi, limitdan oshganda Menejer tasdig'i
- `spec/kod-uchun/04-biznes-jarayonlar.md` — BP-01…BP-13, davlat tizimlari × jarayon matritsasi, BO-10'ning jarayon asosi
- `spec/kod-uchun/09-ai-funksiyalar.md` — AI-01…AI-11 ro'yxati va qamrovi (AI-03 OCR, AI-05 tafovut tushuntirish, AI-06 debitorlik eslatma)
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — autentifikatsiya arxitekturasi (o'z OAuth 2.0, sessiyalar)
- `spec/kod-uchun/01-qarorlar.md` — qaror #14/#15 (OAuth, obuna lokauti), #16 (AI-03), #17 (markirovka offline), #18 (chekdan keyingi e-faktura), #29/#30/#34 (chek tili, qarz to'lovi, Google/Telegram)
- `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` — tavsiya #4 (Faktura.uz), #5 (offline qaytarish/ko'chirish), #6 (qo'lda karta), #13 (yagona tarif)
