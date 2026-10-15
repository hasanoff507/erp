# Rollar va kundalik ssenariylar

**Maqsad:** 5 rol (Egasi, Menejer, Kassir, Omborchi, Buxgalter) uchun maqsad, og'riq, kundalik/haftalik/oylik ssenariy va huquqlar matritsasini belgilash. · **Kim uchun:** hammasi (backend — ruxsat modeli, frontend — ekran/rol UX). · **Bog'liq fayllar:** 03, 13, 14, 15, 17, 33. · **Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. MVP uchun **5 rol** aniqlangan: **Egasi, Menejer, Kassir, Omborchi, Buxgalter**. Har biri uchun maqsad, og'riq, kundalik/haftalik/oylik ssenariy va huquqlar aniqlangan.
2. Kichik do'konda (1-3 xodim) **bitta odam bir necha rolni bajaradi** — eng tipik kombinatsiya: Egasi = Menejer + Buxgalter (qisman), Kassir = Omborchi. Tizim rolni xodimga emas, **vazifaga** biriktiradi, shuning uchun bitta login bir nechta rol huquqiga ega bo'lishi mumkin (`03-modullar-talablari.md`, M13 — huquqlar).
3. Kassir va Omborchi — **Android POS** qurilmasida ishlaydi (tez, offline-bardosh, bir qo'l bilan boshqariladigan interfeys talab qiladi); Menejer, Buxgalter, Egasi — asosan **back-office PWA** (brauzer, o'rnatishsiz) orqali, lekin Egasi mobilda ham tezkor ko'rish (dashboard) ehtiyojiga ega.
4. Eng katta umumiy og'riq — **mavjud buxgalteriya/ERP tizimlarining narxi va murakkabligi** (litsenziya millionlab so'm, joriy etish narxi litsenziyadan oshishi mumkin, qo'shimcha foydalanuvchi uchun alohida to'lov) va **qog'oz/Excel/WhatsApp orqali qo'lda yuritiladigan hisob** (`research_notes/AI ERP startap Ozbekistonda/04_sohalar.md`).
5. Ikkinchi katta og'riq — **davlat tizimlaridagi texnik xatolar va jarima xavfi**: markirovkalangan yuklarning qabul qilinishida 80–90%i skanerlash xatosi bilan qaytadi — bu ko'rsatkich **bitta yirik ishlab chiqaruvchining tajribasi** (gazeta.uz, 2026-04-14), tizim bo'yicha umumiy statistika sifatida tasdiqlanmagan (`research_notes/texnik/tekshiruv-2026-10-14/1-fiskal-kassa-markirovka.md`); jarima **birinchi buzilishda** choraklik aylanmaning 2%i, **takroriy buzilishda** 20%igacha. Bu ayniqsa Omborchi (tovar qabulida) va Egasi (jarima javobgarligi) uchun kundalik xavf; kassada esa skanerlarning umuman ishlamay qolishi muammosi bor (11-fayl).
6. 2026-yildan boshlangan yangi markaziy jarayon — davlat QQS, aylanma, mol-mulk, yer, JShDS va ijtimoiy soliq hisobotlarini **o'zi tuzadi** (Soliq kodeksi 81-moddasi, O'RQ-1108-son Qonun, 2025-12-25, 2026-01-01 dan kuchda — lex.uz/docs/-7944527), korxonaga **5 ish kuni** (SK 5-modda 7-qism; hisobot topshirish muddatidan kechiktirmay) ichida my.soliq.uz shaxsiy kabinetida tasdiqlash yoki tuzatib taqdim etish imkoni beriladi; javobsiz qolsa, davlat shakllantirgan ko'rinishda topshirilgan hisoblanadi (SK 81-modda 6–8-qism). **Foyda solig'i bu ro'yxatga kirmaydi** — u korxonaning o'z mas'uliyatida qoladi. Bu **Buxgalter** rolining markaziy kundalik/haftalik vazifasiga aylanadi.
7. Huquqlar matritsasi 19 modulning (M01–M19; M19 «1C integratsiyasi» — MVP'dan keyin, Bosqich 7) barchasini qamrab oladi (`15-xavfsizlik-va-audit.md` §2 va `33-1c-integratsiya.md` §11 bilan izchil); har bir katakda rol shu modulda **ko'rish (K) / yaratish (Y) / tasdiqlash (T)** huquqlaridan qaysilariga ega ekani ko'rsatilgan.
8. Rollar bo'yicha raqamli qoidalar — standart qiymatlar, Egasi sozlaydi: rol limitlari (qaror #23), rollar birlashuvi chegarasi (26 #2), BO-10 eslatma kunlari 1-, 3-, 4-ish kuni (qaror #50); huquqlar matritsasi tasdiqlangan (26 #1, qaror #28).

---

## 0. Kichik do'konda rollarning birlashuvi

Bozor tadqiqoti shuni ko'rsatadi: 1-3 xodimli do'konlarda alohida "buxgalter" yoki "menejer" lavozimi odatda yo'q — egasi o'zi ko'p vazifani bajaradi (`research_notes/AI ERP startap Ozbekistonda/04_sohalar.md`). Shu sababli tizim quyidagi **tipik kombinatsiyalarni** qo'llab-quvvatlashi kerak (M13 — huquqlar moduli orqali, bitta foydalanuvchiga bir nechta rol biriktirilishi mumkin):

| Do'kon hajmi | Tipik birlashuv |
|---|---|
| 1 xodim (faqat egasi) | Egasi + Menejer + Kassir + Omborchi + Buxgalter — hammasi bitta login |
| 2-3 xodim | Egasi (Menejer + Buxgalter), 1-2 Kassir (ayni paytda Omborchi) |
| 4+ xodim (filialli) | Alohida rollar ajratiladi, Egasi faqat tasdiqlovchi/ko'ruvchi bo'ladi |

*Standart chegara (26 #2): ≤3 FTE — Kassir+Omborchi+Menejer bitta xodimda birlashishi mumkin; 4+ FTE — rollar alohida shaxslarga beriladi.*

---

## 1. Egasi

### Maqsadlar
- Biznesning umumiy holatini (savdo, foyda, qarz, soliq) bir joydan ko'rish.
- Katta qarorlarni (narx, chegirma siyosati, filial ochish, xodim huquqi) tasdiqlash.
- Davlat jarima xavfidan (markirovka, soliq) himoyalanish.

### Og'riqlar (manba bilan)
- Mavjud buxgalteriya/ERP tizimlarining litsenziyasi va joriy etish narxi yuqori, qo'shimcha foydalanuvchi uchun alohida to'lov.
- Markirovka (Asl belgisi) jarimasi — bitta xodimning xatosi butun brendga 2-20% jarima va **"100% bankrotlik xavfi"** keltirishi mumkin (`research_notes/texnik/11-raqobatchilar-kamchiliklari.md`).
- Fiskal kassa buzilishlari (chek bermaslik, naqdsiz to'lovni qabul qilmaslik) davlat tekshiruvida 400+ holatda aniqlangan — obro' va jarima xavfi (`research_notes/texnik/11-raqobatchilar-kamchiliklari.md`, kun.uz manbasi).
- Hisob-kitob ko'p tizim (Excel + WhatsApp + qog'oz) orasida tarqoq, yagona manzara yo'q (`research_notes/AI ERP startap Ozbekistonda/04_sohalar.md`).

### Qurilma
Back-office PWA (asosiy), mobil brauzerda tezkor dashboard ko'rish.

### Ssenariylar

**Kundalik**
1. Ertalab PWA'da kechagi kunlik savdo/foyda hisobotini ko'radi (**M12**).
2. Kassa qoldig'i va naqd balansni tekshiradi (**M01**, **M04**).
3. Limitdan yuqori chegirma/qaytarish so'rovlari bo'lsa, ularni tasdiqlaydi yoki rad etadi (**M02**, **M03**).
4. Markirovka/fiskal xato bo'yicha ogohlantirish bo'lsa, ko'rib chiqadi (**M01**).
5. *(Bosqich 7, 1C ishlatsa)* Telegram'dagi «1C ga yuborildi» / muammo xabarini ko'radi; buxgalter yo'q do'konda kechagi kunni BO-23 da ko'rib «1C ga yuborish»ni tasdiqlaydi (**M19**, BP-14).

**Haftalik**
1. Haftalik savdo va eng ko'p/kam sotilgan tovarlar hisobotini ko'radi (**M12**).
2. Mijozlar qarzdorligi (nasiya) ro'yxatini ko'rib, muddati o'tganlarga eslatma yuborilishini tasdiqlaydi (**M08**).
3. Narx/chegirma siyosatidagi katta o'zgarishlarni tasdiqlaydi (**M09**, **M03**).

**Oylik**
1. Oy yakunida moliyaviy hisobot (foyda-zarar, balans) ni ko'radi (**M11**, **M12**).
2. Davlat tuzgan QQS/boshqa hisobotlar bilan ichki hisob solishtirilgan natijani (5 ish kunlik jarayon; 3-ish kunida farq yopilmasa BO-10 banneri Egasiga ham chiqadi) Buxgalterdan ko'rib, yakuniy tasdiqlaydi (**M10**).
3. Inventarizatsiya natijasidagi kamomad/ortiqchani tasdiqlaydi (**M05**).
4. Yangi filial ochish yoki xodim/rol qo'shish kerak bo'lsa, amalga oshiradi (**M13**, **M14**).
5. *(Bosqich 7, bir martalik)* Do'kon kompyuterini (1C o'rnatilgan) ERP'ga ulaydi, 1C bazasini filialga bog'laydi, rejim/jadvalni va kerak bo'lsa avto-tasdiqni sozlaydi (**M19**, BO-22).

---

## 2. Menejer

### Maqsadlar
- Kundalik operatsiyalarni (narx, chegirma, xarid, qaytarish) boshqarish, Egasiga faqat strategik qarorlarni qoldirish.
- Ombor va savdo samaradorligini optimallashtirish (qaysi tovar ko'p/kam sotiladi, qachon buyurtma berish kerak).

### Og'riqlar (manba bilan)
- Talab bashorati va zaxira rejalashtirish uchun vosita yo'q — qaysi variant/o'lcham qanday sotilishini oldindan bilmaydi, ko'pchilik qo'lda Excel/Telegram bot orqali hisobot yuritadi (`research_notes/AI ERP startap Ozbekistonda/04_sohalar.md`, chakana savdo bo'limi, 18 va 21-qatorlar — "Demand forecasting by variant/size/color").
- Yetkazib beruvchilar bilan hisob-kitob ko'p sohalarda qo'lda Excel va WhatsApp orqali yuritiladi, yagona manzara yo'q (`research_notes/AI ERP startap Ozbekistonda/04_sohalar.md`, 45 va 99-qatorlar — "manual Excel + WhatsApp updates").
- Mijoz qarzdorligini kim qachon to'lamasligini oldindan bilish imkoni yo'q — `taxmin`: ulgurji distributor segmentida xuddi shunga o'xshash "Debtor prediction" ehtiyoji qayd etilgan (`research_notes/AI ERP startap Ozbekistonda/04_sohalar.md`, 102-qator), lekin bu to'g'ridan-to'g'ri chakana Menejer roli uchun tasdiqlangan manba emas.

### Qurilma
Back-office PWA (asosiy); zarurat bo'lganda Android POS'da kassir sifatida ham ishlashi mumkin (rol birlashuvi).

### Ssenariylar

**Kundalik**
1. Kecha kiritilgan savdo/ombor ma'lumotlarini ko'radi, past qoldiqli tovarlarni aniqlaydi (**M04**).
2. Kassirlardan kelgan limitdan yuqori chegirma/qaytarish so'rovlarini tasdiqlaydi (**M02**, **M03**).
3. Kechagi nasiya (qarz) operatsiyalarini ko'rib, muddati yaqinlashgan mijozlarga eslatma yuborilishini boshqaradi (**M08**).

**Haftalik**
1. Kam qolgan tovarlar bo'yicha yetkazib beruvchiga xaridnoma yaratadi (**M07**).
2. Ombor orasida (filiallar) tovar ko'chirish zaruratini aniqlab, hujjat yaratadi (**M06**).
3. Narx va chegirma qoidalarini (aksiya, sezon) yangilaydi (**M09**, **M03**).

**Oylik**
1. Oylik savdo/ombor samaradorlik hisobotini ko'rib, Egasiga taqdim etadi (**M12**).
2. Inventarizatsiya jarayonini boshlab, Omborchi natijalarini ko'rib tasdiqqa yuboradi (**M05**).
3. Xodimlar (kassirlar) huquq/limitlarini ko'rib chiqadi (**M13**).

---

## 3. Kassir

### Maqsadlar
- Mijozga tez va xatosiz xizmat ko'rsatish (chek, to'lov, qaytarish, nasiya).
- Fiskal/markirovka qoidalarini buzmasdan sotuvni yakunlash.

### Og'riqlar (manba bilan)
- Markirovka skanerlari amalda **muntazam ishlamaydi**, uskuna o'rnatish qiyin — bu kassada navbatni to'xtatadi va mijoz noroziligini keltiradi (`research_notes/texnik/11-raqobatchilar-kamchiliklari.md`, gazeta.uz 2026-04-14 iqtibosi).
- Internet uzilganda savdo to'xtab qolishi xavfi (offline-first yo'q bo'lgan tizimlarda) — O'zbekistonda internet uzilishlari tarixi tufayli bu kundalik xavf (`spec/README.md`, offline-first qarori). Offline savdo qonuniy, lekin OFD tasdig'ini olmagan eng eski chekdan 48 soat o'tsa kassa avtomatik bloklanadi (VMQ-943 2-ilova 6-band) — tizim 24/40/46 soatda ogohlantiradi (qaror #43).
- Fiskal modul/OFD texnik xatosi tufayli chek bermaslik holatlari — bu kassirning shaxsiy javobgarligiga aylanishi mumkin (`research_notes/texnik/11-raqobatchilar-kamchiliklari.md`).

### Qurilma
Android POS (asosiy va yagona ish quroli) — bir qo'l bilan, tez, offline-bardosh interfeys talab qilinadi.

### Ssenariylar

**Kundalik**
1. Smena boshida boshlang'ich naqd summani kiritib, smenani ochadi (**M01**).
2. Mijozga tovar sotadi: skanerlash → to'lov (naqd/karta/yagona QR (UzQR, bank)/Payme/Click/Uzum) → bosma chek (**M01**). Mustaqil terminalda karta to'lovida terminal chekidan karta turini (shaxsiy/korporativ/ijtimoiy) belgilaydi; ijtimoiy kartada karta niqobi va RRN ni kiritadi (qaror #64). Statik UzQR to'lovini mijoz telefonidagi tasdiqni ko'rib qo'lda tasdiqlaydi. Printer ishlamasa yoki xaridor so'rasa — elektron chek (QR/Telegram) zahira sifatida.
3. Markirovkalangan tovar sotganda kod skanerlanadi va fiskal chek ichida OFD orqali Asl belgisiga ketadi; online bo'lsa kod oldindan tekshiriladi — muvaffaqiyatsiz bo'lsa ogohlantirish chiqadi (standart `MARKING_PRECHECK=warn`), dublikat yoki avval sotilgan kod rad etiladi (qaror #62) (**M01**).
4. Mijoz tovarni qaytarganda, asl chek bo'yicha qaytarish amalga oshiradi; limitdan oshsa Menejerdan tasdiq so'raydi (**M02**).
5. Kichik chegirma (limit ichida) berishi mumkin; kattaroq chegirma uchun Menejer PIN kodi kerak (**M03**).
6. Tanish mijozga limit ichida nasiyaga sotadi (**M08**).
7. Smena oxirida Z-hisobotni yopadi (**M01**, **M12**).
8. Yangi kassa qurilmasida bir marta chek printeri va tarozini sozlab, sinov chek chiqaradi (POS-16, US-M01-07).

**Haftalik** — odatda Kassir uchun alohida haftalik vazifa yo'q (kundalik takrorlanuvchi ish); istisno: smena jadvali almashinuvi paytida kassa hisobini topshirish-qabul qilish.

**Oylik** — kassir rolida alohida oylik vazifa yo'q; agar bitta xodim Kassir+Omborchi bo'lsa, oylik inventarizatsiyada qatnashadi (**M05**, pastga qarang).

---

## 4. Omborchi

### Maqsadlar
- Ombordagi tovar qoldig'ini aniq yuritish, kelgan/ketgan tovarni o'z vaqtida qayd etish.
- Inventarizatsiya va filiallar orasi ko'chirishni to'g'ri bajarish.

### Og'riqlar (manba bilan)
- Markirovkalangan yuklarni qabul qilishda **80–90%i skanerlash xatosi bilan qaytadi**, bu tovar qabulini sezilarli kechiktiradi va jarima xavfini oshiradi (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 6-band; `research_notes/texnik/11-raqobatchilar-kamchiliklari.md`, gazeta.uz 2026-04-14 iqtibosi).
- Ko'p kichik do'konlarda ombor hisobi hali ham **qo'lda yozilgan daftar** yoki Excel orqali yuritiladi, muddati o'tgan tovarni oldindan bilish imkoni yo'q (`research_notes/AI ERP startap Ozbekistonda/04_sohalar.md`, "handwritten batch registers", "Expiry prediction + auto-alert").
- Markirovkalangan tovar kirimida Asl belgisi qabul xabarnomasini tovar guruhi muddatida imzolash kerak — umumiy **3 ish kuni** (VM 833 66–67-band), suv/ichimlik, dori va o'simlik yog'i sxemalarida **72 soat**; muddatni qo'lda kuzatish qiyin (`research_notes/ochiq-savollar/P2-efaktura-markirovka.md`, OQ-027).
- O'z filiallari orasidagi ko'chirishda ham e-TTN ("Ombordan omborga") majburiy (VM 249 31-ilova 13-band; qaror #63).
- Tovar kelganda xaridnoma bilan solishtirish, farq (kam/ko'p yetkazib berilgan) ni qo'lda aniqlash vaqt oladi.

### Qurilma
Android POS (mobil skanerlash uchun; ombor sharoitida qo'l terminal sifatida) va/yoki back-office PWA (katalog/hisobot ko'rish uchun).

### Ssenariylar

**Kundalik**
1. Yetkazib beruvchidan kelgan tovarni xaridnoma bilan solishtirib qabul qiladi, balansga kirim qiladi (**M07**, **M04**); markirovkalangan tovar qabul xabarnomasini guruh muddatida tasdiqlaydi. Tovarni do'kon nomidan qabul qilish uchun do'kon Omborchiga e-faktura operatori orqali e-ishonchnoma beradi (e-fakturadan oldin), Omborchi e-fakturani E-IMZO bilan imzolaydi (qaror #63).
2. Boshqa filialdan kelgan ko'chirish hujjatini va uning e-TTN'ini tasdiqlab qabul qiladi (**M06**).
3. Kam qolgan tovar haqida Menejerga signal beradi (**M04**).

**Haftalik**
1. Boshqa do'konga/omborga yuborilishi kerak bo'lgan tovar uchun ko'chirish hujjati yaratadi; jo'natishda e-TTN ("Ombordan omborga") shakllanadi — avtotransportda tashishdan oldin rasmiylashtirilgan bo'lishi shart, qo'lda/jamoat transportida tashishda talab qilinmaydi (`transport_mode`, qaror #63) (**M06**).
2. Tez buziladigan/muddati yaqinlashgan tovarlarni ko'rib chiqadi (**M04**).

**Oylik**
1. Inventarizatsiya varag'ini olib, jismoniy sanashni amalga oshiradi, natijani tizimga kiritadi (**M05**).
2. Aniqlangan farqni (kamomad/ortiqcha) Menejer/Egasiga tasdiqlash uchun yuboradi (**M05**).

---

## 5. Buxgalter

### Maqsadlar
- Savdo/ombor operatsiyalaridan to'g'ri buxgalteriya yozuvlarini olish, QQS va boshqa soliqlarni to'g'ri hisoblash.
- 2026-yildan davlat tuzgan hisobotni ichki hisob bilan **5 ish kuni** ichida (topshirish muddatidan kechiktirmay) solishtirish va farqni hal qilish.

### Og'riqlar (manba bilan)
- Yangi NSBU №21 (2024/2025) hisob rejasiga o'tish — eski 2002-yilgi reja 2025-01-01'dan amal qilmaydi, ko'p kichik biznes buni hali to'liq bilmaydi (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`, 3.4-bo'lim).
- E-faktura AI xavf-baholash tizimi (2026-01-01 dan to'liq) tufayli "qizil" (yuqori xavfli) faktura bo'lsa, QQS krediti sotuvchi/xaridor to'lagandan keyin kreditlanadi — bu naqd pul oqimiga ta'sir qiladi va tezkor kuzatuvni talab qiladi (`research_notes/texnik/03-efaktura-va-tolov.md`, 1.2-bo'lim).
- 2026-yildan davlat QQS va boshqa hisobotlarni **o'zi tuzadi**, korxonaga faqat **5 ish kuni** tekshirish/tuzatish vaqti beriladi (Soliq kodeksi 81-moddasi, 5-modda 7-qism; O'RQ-1108) — bu avvalgi "deklaratsiya yozish" ishini "solishtirish va tezkor javob berish" ishiga aylantiradi, davlat hisobotini dasturiy olish yo'li yo'qligi sababli hisobot fayli kabinetdan yuklab olinib tizimga yuklanadi (26 #41) (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 5-band va 86-qator).
- Mavjud tizimlarda buxgalteriya hisob rejasi savdo modulidan butunlay alohida bo'lishi odatiy muammo — ikki tizim orasida ma'lumot ko'chirish odatda qo'lda/Excel orqali bo'ladi (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`, 4-band).

### Qurilma
Back-office PWA (yagona ish muhiti).

### Ssenariylar

**Kundalik**
1. Kechagi savdo/xarid hujjatlaridan avtomatik yaratilgan provodkalarni (kassa, hisob-kitob, tovar) ko'rib chiqadi (**M11**).
2. Yuqori xavfli ("qizil") e-fakturalar bo'yicha bildirishnomalarni kuzatadi; operator xavf darajasini bermagan (`unknown`) fakturalarni my.soliq.uz kabinetidan ko'rib BO-15 da qo'lda belgilaydi (**M10**, **M07**).
3. Kassa smenasi Z-hisobotlari bilan kassadagi naqd pul mosligini tekshiradi (**M01**, **M11**).
4. Bank ko'chirmasi / ekvayer hisob-kitob hisoboti kelganda karta, QR, Click/Payme/Uzum tushumlari va inkassa bo'yicha **bank tushumi tasdig'i**ni yaratib o'tkazadi — yo'ldagi pul mablag'lari bank hisobiga o'tadi, komissiya 9430 xarajatiga yoziladi; bank ko'chirmasini (1CClientBankExchange .txt) BO-24 ga yuklab, taklif qilingan qoralamalarni tekshiradi (**M11**, BO-24, BP-15, qaror #42).
5. *(Bosqich 7, 1C ishlatsa)* Kun yopilgach BO-23 da 1C ga yoziladigan hujjatlar preview'ini, tayyorlikni (smenalar yopilgan, kassalar sinxronlangan, moslashtirish to'liq) ko'rib «1C ga yuborish»ni tasdiqlaydi; xato/farq bo'lsa tuzatib qayta yuboradi yoki sabab bilan qabul qiladi (**M19**, BP-14).

**Haftalik**
1. Haftalik QQS bazasi va summasini ko'rib chiqadi, kelayotgan davlat hisoboti bilan solishtirishga tayyorlanadi (**M10**).
2. Yetkazib beruvchi hisob-fakturalarini (MVP'da Faktura.uz orqali kelgan) qabul qiladi va E-IMZO bilan imzolaydi; kerak bo'lsa Omborchiga tovar qabul qilish uchun e-ishonchnoma chiqaradi (qaror #63) (**M07**).
3. *(Bosqich 7, 1C ishlatsa)* Yangi tovar/kontragentlarni 1C bilan moslaydi, 1C da yaratish takliflarini ko'rib tasdiqlaydi (**M19**, BO-22).

**Oylik**
1. Oy yakunida moliyaviy hisobotlarni (foyda-zarar, balans) shakllantiradi (**M11**, **M12**).
2. Oyning 10-sanasigacha davlat hisobotiga kiradigan interaktiv ma'lumotlarni (aylanma — soliq solinmaydigan daromad, chegirmalar, imtiyozlar; QQS — hisobga olinadigan QQS tuzatishlari) tizim tayyorlagan raqamlar asosida kabinetga kiritadi (**M10**).
3. Davlat qo'mitasi tuzgan QQS/aylanma/boshqa hisobot faylini my.soliq.uz kabinetidan yuklab olib tizimga yuklaydi va ichki hisob bilan solishtiradi (QQS — e-faktura darajasida va yig'indi; aylanma — 5 manba bo'yicha yig'indi); farq topilsa **5 ish kuni** ichida (topshirish muddatidan kechiktirmay) kabinetda tasdiqlaydi yoki tuzatib taqdim etadi, Egasiga yakuniy natijani tasdiqlash uchun yuboradi (**M10**). Javob berilmasa, hisobot davlat shakllantirgan ko'rinishda topshirilgan hisoblanadi (Soliq kodeksi 81-moddasi, O'RQ-1108 — [lex.uz/docs/-7944527](https://lex.uz/docs/-7944527)); muddatdan keyin — SK 83-modda bo'yicha aniqlashtirilgan hisobot. Tizim 1-, 3- va 4-ish kunida Buxgalterga, 3-ish kunidan Egasiga ham ogohlantiradi (qaror #50).
4. Davr oxirida server hisoblagan soliq hisob-kitobi hujjatini (`tax_settlements`, ST: QQS hisobga olish yoki aylanma solig'i) ko'rib o'tkazadi (**M10**, **M11**).
5. Inventarizatsiya natijasini (**M05**, ko'rish) buxgalteriya yozuviga aks ettiradi (**M11**, yaratish).

---

## 6. Huquqlar matritsasi (rol × modul)

Belgilar: **K** = ko'rish, **Y** = yaratish, **T** = tasdiqlash. "–" = huquq yo'q. Bir katakda bir nechta harf bo'lishi mumkin (masalan "KYT").

| Modul | Egasi | Menejer | Kassir | Omborchi | Buxgalter |
|---|---|---|---|---|---|
| M01 Kassa | K, Y, T | K, Y | Y | – | K |
| M02 Qaytarish | K, Y, T | Y, T | Y | K | K |
| M03 Chegirma | K, Y, T | Y, T | Y | – | K |
| M04 Ombor qoldig'i | K, Y, T | K | K | Y | K |
| M05 Inventarizatsiya | K, Y, T | Y, T | – | Y | K |
| M06 Ko'chirish | K, Y, T | Y, T | – | Y | K |
| M07 Xarid | K, Y, T | Y, T | – | Y | K, Y |
| M08 Nasiya | K, Y, T | Y, T | Y | – | K |
| M09 Narxlar | K, Y, T | Y | K | K | K |
| M10 QQS | K, Y, T | K | – | – | Y, T |
| M11 Buxgalteriya | K, Y, T | K | – | – | Y, T |
| M12 Hisobotlar | K, Y, T | K | K (faqat o'z smenasi) | K (faqat ombor) | Y, K |
| M13 Huquqlar | K, Y, T | K | – | – | K |
| M14 Filiallar | K, Y, T | K | – | K | K |
| M15 Xarajatlar | K, Y, T | K, Y | – | – | K, Y |
| M16 Kassa pul harakati | K, Y, T | K, Y, T | Y (K faqat o'z smenasi) | – | K |
| M17 Obuna va ro'yxatdan o'tish | K, Y, T | – | – | – | – |
| M18 Bildirishnomalar / Telegram | K, Y, T | K (o'z Telegram'ini ulash, Egasi ruxsati bilan) | – | – | – |
| M19 1C integratsiyasi (MVP'dan keyin, Bosqich 7) | K, Y, T | K | – | – | K, Y, T (sozlash va kompyuter ulashsiz) |

*Izoh: matritsa tasdiqlangan (26 #1, qaror #28); ruxsat kodlari darajasidagi to'liq jadval — `15-xavfsizlik-va-audit.md` §2.2. Omborchi kirimni faqat `draft` qiladi, `post` — Buxgalter/Egasi; Egasi BO-11 da Omborchi roliga `purchases.post` ni qo'shishi mumkin (qaror #49).*

*(qaror #28)* **Egasi ustuni — barcha tenant ruxsatlarining supersetiga ega** (`platform.admin`dan tashqari — bu platforma admini uchun, tenant rollariga kirmaydi), limitlar cheksiz: sotuv, smena, qaytarish, buxgalteriya, sozlamalar ham kiradi.

*Standart limitlar (qaror #23):* M03 (chegirma) — Kassir PIN'siz **5% gacha**; M02 (qaytarish) — chek bilan PIN'siz **100 000 so'mgacha** (chek yo'q bo'lsa har doim PIN); M16 (kassa pul harakati) — "Pul olish" PIN'siz **50 000 so'mgacha**; chekni bekor qilish (void) Kassirga limitsiz, audit bilan. Bu raqamlar **standart** qiymat — Egasi M13 (Huquqlar) orqali istalgan paytda o'zgartirishi mumkin (`03-modullar-talablari.md`, US-M02-02/US-M03-01/US-M16-01).

*M15–M18 izohi:* Kassir xarajatni faqat M16 "Pul olish → Xarajat to'lovi" orqali yozadi (M15'ga avtomatik tushadi); M17 `billing.manage` faqat Egasi; platforma admini (ADM-01, `platform.admin`) tenant rollariga kirmaydi — `15-xavfsizlik-va-audit.md` §3.4.

*M11 — bank tushumi tasdig'i:* `bank_settlements` (BO-24) — ruxsat `bank_settlements.manage` (Egasi, Buxgalter); Menejer, Kassir, Omborchi yaratmaydi (`13-provodka-qoidalari.md` §2.18a).

*M19 izohi (`33-1c-integratsiya.md` §11):* ruxsatlar `onec.view` (Egasi, Menejer, Buxgalter), `onec.settings.manage` (faqat Egasi — kompyuterni ulash/uzish, bazalar, «1C ga yozishga ruxsat», filial bog'lash, rejim/jadval), `onec.mapping.edit`, `onec.refs.create`, `onec.export.prepare`, `onec.export.approve`, `onec.export.correct` (Egasi, Buxgalter). Avto-tasdiqni yoqish — faqat Egasi (qaror #40). Egasi Buxgalterga `onec.settings.manage` ni BO-11 orqali qo'shishi mumkin. Kassir va Omborchi M19 ga kirmaydi.

*M13 izohi (qaror #14):* M13 endi faqat rol/huquq emas — Egasi uchun to'liq foydalanuvchi boshqaruvi (xodim qo'shish, bloklash, parol/PIN tiklash, faol sessiya/qurilmalarni ko'rish va bekor qilish — US-M13-04…07) ham shu modulga kiradi; platforma admini (ADM-01) faqat tenant Egasi (owner) hisobi darajasida shu funksiyalarga ega (US-M13-08). Autentifikatsiya — o'z OAuth 2.0 implementatsiyasi, mock yo'q (`14-autentifikatsiya-oauth2.md`).

---

## Ochiq savollar

Tashqi javob kerak bo'lgan band yo'q — rollar va ssenariylar bo'yicha savollar qaror bilan yopilgan (26 #1, #2, #3; qaror #28, #49, #50, #63).

## Manbalar

- `spec/README.md` — asosiy qarorlar
- `research_notes/texnik/00-xulosa-va-ochiq-savollar.md`
- `research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`
- `research_notes/texnik/02-kassa-ofd-markirovka.md`
- `research_notes/texnik/03-efaktura-va-tolov.md`
- `research_notes/texnik/08-mahsulot-modullari.md`
- `research_notes/texnik/11-raqobatchilar-kamchiliklari.md`
- `research_notes/AI ERP startap Ozbekistonda/04_sohalar.md`
- `research_notes/texnik/tekshiruv-2026-10-14/` — 2026-10-14 fakt-tekshiruv natijalari
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — autentifikatsiya arxitekturasi (qaror #14)
- `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` — tavsiya #1 (standart rol limitlari, qaror #23)
- `research_notes/ochiq-savollar/` — P1 (OQ-004, OQ-013), P2 (OQ-021, OQ-024, OQ-027), P3 (OQ-033), D-qarorlar (#43–#59)
