# Rollar va kundalik ssenariylar

## Asosiy xulosalar

1. MVP uchun **5 rol** aniqlangan: **Egasi, Menejer, Kassir, Omborchi, Buxgalter**. Har biri uchun maqsad, og'riq, kundalik/haftalik/oylik ssenariy va huquqlar aniqlangan.
2. Kichik do'konda (1-3 xodim) **bitta odam bir necha rolni bajaradi** — eng tipik kombinatsiya: Egasi = Menejer + Buxgalter (qisman), Kassir = Omborchi. Tizim rolni xodimga emas, **vazifaga** biriktiradi, shuning uchun bitta login bir nechta rol huquqiga ega bo'lishi mumkin (`03-modullar-talablari.md`, M13 — huquqlar).
3. Kassir va Omborchi — **Android POS** qurilmasida ishlaydi (tez, offline-bardosh, bir qo'l bilan boshqariladigan interfeys talab qiladi); Menejer, Buxgalter, Egasi — asosan **back-office PWA** (brauzer, o'rnatishsiz) orqali, lekin Egasi mobilda ham tezkor ko'rish (dashboard) ehtiyojiga ega.
4. Eng katta umumiy og'riq — **mavjud buxgalteriya/ERP tizimlarining narxi va murakkabligi** (litsenziya millionlab so'm, joriy etish narxi litsenziyadan oshishi mumkin, qo'shimcha foydalanuvchi uchun alohida to'lov) va **qog'oz/Excel/WhatsApp orqali qo'lda yuritiladigan hisob** (`research_notes/AI ERP startap Ozbekistonda/04_sohalar.md`) *(2026-10-14: neytral ifodalandi — koordinator direktivasi)*.
5. Ikkinchi katta og'riq — **davlat tizimlaridagi texnik xatolar va jarima xavfi**: markirovkalangan yuklarning qabul qilinishida 80–90%i skanerlash xatosi bilan qaytadi — bu ko'rsatkich **bitta yirik ishlab chiqaruvchining tajribasi** (gazeta.uz, 2026-04-14), tizim bo'yicha umumiy statistika sifatida tasdiqlanmagan *(2026-10-14: tuzatildi)* (`research_notes/texnik/tekshiruv-2026-10-14/1-fiskal-kassa-markirovka.md`); jarima **birinchi buzilishda** choraklik aylanmaning 2%i, **takroriy buzilishda** 20%igacha *(2026-10-14: tuzatildi)*. Bu ayniqsa Omborchi (tovar qabulida) va Egasi (jarima javobgarligi) uchun kundalik xavf; kassada esa skanerlarning umuman ishlamay qolishi muammosi bor (11-fayl).
6. 2026-yildan boshlangan yangi markaziy jarayon — davlat QQS, aylanma, mol-mulk, yer, JShDS va ijtimoiy soliq hisobotlarini **o'zi tuzadi** (Soliq kodeksi 81-moddasi, O'RQ-1108-son Qonun, 2025-12-25, 2026-01-01 dan kuchda — lex.uz/docs/-7944527), korxonaga **5 kalendar kun** (hisobot topshirish muddatidan kechiktirmay) ichida tuzatish kiritish imkoni beriladi; javobsiz qolsa, davlat shakllantirgan ko'rinishda topshirilgan hisoblanadi. **Foyda solig'i bu ro'yxatga kirmaydi** — u korxonaning o'z mas'uliyatida qoladi *(2026-10-14: tuzatildi — avval "5 ish kuni" va manba sifatida ikkinchi darajali OAV ko'rsatilgan edi; endi birlamchi qonun manbasi topildi)*. Bu **Buxgalter** rolining markaziy kundalik/haftalik vazifasiga aylanadi.
7. Huquqlar matritsasi 18 modulning (M01–M18) barchasini qamrab oladi *(2026-10-14: M15–M18 qo'shildi, `kod-uchun/15-xavfsizlik-va-audit.md` §2 bilan izchil)*; har bir katakda rol shu modulda **ko'rish (K) / yaratish (Y) / tasdiqlash (T)** huquqlaridan qaysilariga ega ekani ko'rsatilgan.
8. Rollar va ssenariylar bo'yicha raqamli ma'lumot (masalan aniq limit summalari, eslatma vaqti) tadqiqot fayllarida yo'q — bular **taxmin** deb belgilangan va "Ochiq savollar"da qayd etilgan; keyingi bosqichda biznes-qoida sifatida sozlanishi tavsiya etiladi.

---

## 0. Kichik do'konda rollarning birlashuvi

Bozor tadqiqoti shuni ko'rsatadi: 1-3 xodimli do'konlarda alohida "buxgalter" yoki "menejer" lavozimi odatda yo'q — egasi o'zi ko'p vazifani bajaradi (`research_notes/AI ERP startap Ozbekistonda/04_sohalar.md`). Shu sababli tizim quyidagi **tipik kombinatsiyalarni** qo'llab-quvvatlashi kerak (M13 — huquqlar moduli orqali, bitta foydalanuvchiga bir nechta rol biriktirilishi mumkin):

| Do'kon hajmi | Tipik birlashuv |
|---|---|
| 1 xodim (faqat egasi) | Egasi + Menejer + Kassir + Omborchi + Buxgalter — hammasi bitta login |
| 2-3 xodim | Egasi (Menejer + Buxgalter), 1-2 Kassir (ayni paytda Omborchi) |
| 4+ xodim (filialli) | Alohida rollar ajratiladi, Egasi faqat tasdiqlovchi/ko'ruvchi bo'ladi |

*Taxmin: aniq xodim soni chegaralari (1-3, 4+) tadqiqotda raqam bilan tasdiqlanmagan — bu segmentatsiya bozor hujjatidagi umumiy tasvirdan (kichik chakana savdo) kelib chiqqan taxminiy guruhlash.*

---

## 1. Egasi

### Maqsadlar
- Biznesning umumiy holatini (savdo, foyda, qarz, soliq) bir joydan ko'rish.
- Katta qarorlarni (narx, chegirma siyosati, filial ochish, xodim huquqi) tasdiqlash.
- Davlat jarima xavfidan (markirovka, soliq) himoyalanish.

### Og'riqlar (manba bilan)
- Mavjud buxgalteriya/ERP tizimlarining litsenziyasi va joriy etish narxi yuqori, qo'shimcha foydalanuvchi uchun alohida to'lov *(2026-10-14: neytral ifodalandi — koordinator direktivasi)*.
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

**Haftalik**
1. Haftalik savdo va eng ko'p/kam sotilgan tovarlar hisobotini ko'radi (**M12**).
2. Mijozlar qarzdorligi (nasiya) ro'yxatini ko'rib, muddati o'tganlarga eslatma yuborilishini tasdiqlaydi (**M08**).
3. Narx/chegirma siyosatidagi katta o'zgarishlarni tasdiqlaydi (**M09**, **M03**).

**Oylik**
1. Oy yakunida moliyaviy hisobot (foyda-zarar, balans) ni ko'radi (**M11**, **M12**).
2. Davlat tuzgan QQS/boshqa hisobotlar bilan ichki hisob solishtirilgan natijani (5 kalendar kunlik jarayon *(2026-10-14: tuzatildi)*) Buxgalterdan ko'rib, yakuniy tasdiqlaydi (**M10**).
3. Inventarizatsiya natijasidagi kamomad/ortiqchani tasdiqlaydi (**M05**).
4. Yangi filial ochish yoki xodim/rol qo'shish kerak bo'lsa, amalga oshiradi (**M13**, **M14**).

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
- Internet uzilganda savdo to'xtab qolishi xavfi (offline-first yo'q bo'lgan tizimlarda) — O'zbekistonda internet uzilishlari tarixi tufayli bu kundalik xavf (`spec/README.md`, offline-first qarori).
- Fiskal modul/OFD texnik xatosi tufayli chek bermaslik holatlari — bu kassirning shaxsiy javobgarligiga aylanishi mumkin (`research_notes/texnik/11-raqobatchilar-kamchiliklari.md`).

### Qurilma
Android POS (asosiy va yagona ish quroli) — bir qo'l bilan, tez, offline-bardosh interfeys talab qilinadi.

### Ssenariylar

**Kundalik**
1. Smena boshida boshlang'ich naqd summani kiritib, smenani ochadi (**M01**).
2. Mijozga tovar sotadi: skanerlash → chek → to'lov (naqd/karta/yagona QR (UzQR, bank)/Payme/Click/Uzum) *(2026-10-14: tekshiruv)* (**M01**).
3. Markirovkalangan tovar sotganda kod avtomatik tekshiriladi (online bo'lsa); xato chiqsa, belgilangan siyosatga ko'ra harakat qiladi (**M01**).
4. Mijoz tovarni qaytarganda, asl chek bo'yicha qaytarish amalga oshiradi; limitdan oshsa Menejerdan tasdiq so'raydi (**M02**).
5. Kichik chegirma (limit ichida) berishi mumkin; kattaroq chegirma uchun Menejer PIN kodi kerak (**M03**).
6. Tanish mijozga limit ichida nasiyaga sotadi (**M08**).
7. Smena oxirida Z-hisobotni yopadi (**M01**, **M12**).

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
- Markirovkalangan tovarni bir joydan ikkinchisiga ko'chirish endi **72 soat** qat'iy muddatga bog'langan (23-son qaror, 2026-01-23), bu muddatni qo'lda kuzatish qiyin (`research_notes/texnik/02-kassa-ofd-markirovka.md`, 3-bo'lim, 106-qator).
- Tovar kelganda xaridnoma bilan solishtirish, farq (kam/ko'p yetkazib berilgan) ni qo'lda aniqlash vaqt oladi.

### Qurilma
Android POS (mobil skanerlash uchun; ombor sharoitida qo'l terminal sifatida) va/yoki back-office PWA (katalog/hisobot ko'rish uchun).

### Ssenariylar

**Kundalik**
1. Yetkazib beruvchidan kelgan tovarni xaridnoma bilan solishtirib qabul qiladi, balansga kirim qiladi (**M07**, **M04**); yetkazib beruvchi vakili ishonchnoma bilan kelsa, 2026-01-01 dan Vakolat.uz orqali e-ishonchnomani tekshirish zarurligi **ochiq savol** (pastda).
2. Boshqa filialdan kelgan ko'chirish hujjatini tasdiqlab qabul qiladi (**M06**).
3. Kam qolgan tovar haqida Menejerga signal beradi (**M04**).

**Haftalik**
1. Boshqa do'konga/omborga yuborilishi kerak bo'lgan tovar uchun ko'chirish hujjati yaratadi, markirovkalangan tovar uchun 72 soatlik muddatni hisobga oladi (**M06**).
2. Tez buziladigan/muddati yaqinlashgan tovarlarni ko'rib chiqadi (**M04**).

**Oylik**
1. Inventarizatsiya varag'ini olib, jismoniy sanashni amalga oshiradi, natijani tizimga kiritadi (**M05**).
2. Aniqlangan farqni (kamomad/ortiqcha) Menejer/Egasiga tasdiqlash uchun yuboradi (**M05**).

---

## 5. Buxgalter

### Maqsadlar
- Savdo/ombor operatsiyalaridan to'g'ri buxgalteriya yozuvlarini olish, QQS va boshqa soliqlarni to'g'ri hisoblash.
- 2026-yildan davlat tuzgan hisobotni ichki hisob bilan **5 kalendar kun** ichida solishtirish va farqni hal qilish *(2026-10-14: tuzatildi)*.

### Og'riqlar (manba bilan)
- Yangi NSBU №21 (2024/2025) hisob rejasiga o'tish — eski 2002-yilgi reja 2025-01-01'dan amal qilmaydi, ko'p kichik biznes buni hali to'liq bilmaydi (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`, 3.4-bo'lim).
- E-faktura AI xavf-baholash tizimi (2026-01-01 dan to'liq) tufayli "qizil" (yuqori xavfli) faktura bo'lsa, QQS krediti sotuvchi/xaridor to'lagandan keyin kreditlanadi — bu naqd pul oqimiga ta'sir qiladi va tezkor kuzatuvni talab qiladi (`research_notes/texnik/03-efaktura-va-tolov.md`, 1.2-bo'lim).
- 2026-yildan davlat QQS va boshqa hisobotlarni **o'zi tuzadi**, korxonaga faqat **5 kalendar kun** tekshirish/tuzatish vaqti beriladi (Soliq kodeksi 81-moddasi, O'RQ-1108) *(2026-10-14: tuzatildi)* — bu avvalgi "deklaratsiya yozish" ishini "solishtirish va tezkor javob berish" ishiga aylantiradi, rasmiy API yo'qligi sababli bu jarayon hozircha qo'lda/yarim-avtomatik (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 5-band va 86-qator).
- Mavjud tizimlarda buxgalteriya hisob rejasi savdo modulidan butunlay alohida bo'lishi odatiy muammo — ikki tizim orasida ma'lumot ko'chirish odatda qo'lda/Excel orqali bo'ladi (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`, 4-band) *(2026-10-14: neytral ifodalandi — koordinator direktivasi)*.

### Qurilma
Back-office PWA (yagona ish muhiti).

### Ssenariylar

**Kundalik**
1. Kechagi savdo/xarid hujjatlaridan avtomatik yaratilgan provodkalarni (kassa, hisob-kitob, tovar) ko'rib chiqadi (**M11**).
2. Yuqori xavfli ("qizil") e-fakturalar bo'yicha bildirishnomalarni kuzatadi (**M10**, **M07**).
3. Kassa smenasi Z-hisobotlari bilan kassadagi naqd pul mosligini tekshiradi (**M01**, **M11**).

**Haftalik**
1. Haftalik QQS bazasi va summasini ko'rib chiqadi, kelayotgan davlat hisoboti bilan solishtirishga tayyorlanadi (**M10**).
2. Yetkazib beruvchi hisob-fakturalarini (Didox/Faktura.uz orqali kelgan) tizimga kiritadi va E-IMZO bilan imzolaydi (**M07**).

**Oylik**
1. Oy yakunida moliyaviy hisobotlarni (foyda-zarar, balans) shakllantiradi (**M11**, **M12**).
2. Davlat qo'mitasi tuzgan QQS/aylanma/boshqa hisobotni my.soliq.uz'dan olib, ichki hisob bilan solishtiradi; farq topilsa **5 kalendar kun** ichida tekshirib, kerak bo'lsa tuzatish kiritadi, Egasiga yakuniy natijani tasdiqlash uchun yuboradi (**M10**). Agar 5 kalendar kun ichida javob berilmasa, hisobot davlat shakllantirgan ko'rinishda topshirilgan hisoblanadi (Soliq kodeksi 81-moddasi, O'RQ-1108 — [lex.uz/docs/-7944527](https://lex.uz/docs/-7944527)) *(2026-10-14: tuzatildi)* — shu sababli tizim muddat tugashidan oldin (1-/3-/4-kunlarda) Buxgalter va Egasiga ogohlantirish yuborishi kerak.
3. Inventarizatsiya natijasini (**M05**, ko'rish) buxgalteriya yozuviga aks ettiradi (**M11**, yaratish).

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

*Izoh: jadvaldagi aniq huquq taqsimoti (masalan, Kassir M08'ga Y huquqiga ega) bozor/texnik tadqiqotda tayyor matritsa sifatida topilmagan — bu hujjat ERP ma'lumotlar modeli namunasi (`01-erp-modullar-va-malumot-modeli.md`) va modul funksiyalari (`08-mahsulot-modullari.md`) asosida, odatiy chakana savdo amaliyotidan kelib chiqib **loyihalashtirilgan**; MVP oldidan Egasi/arxitektor bilan tasdiqlanishi tavsiya etiladi (pastda, ochiq savol 1).*

*(2026-10-15: asoschi qarori)* **Egasi ustuni — barcha tenant ruxsatlarining supersetiga ega** (`platform.admin`dan tashqari — bu platforma admini uchun, tenant rollariga kirmaydi), limitlar cheksiz: avvalgi versiyada Egasida `sales.create`, `shift.open/close`, `returns.create`, `stock.count.create`, `transfer.*`, `purchases.*`, `cash.count.shift`, `accounting.*` kabi `Y`/yaratish huquqlari yo'q edi — 1–3 xodimli do'konda Egasi ko'pincha o'zi kassada/omborda ishlagani uchun bu amaliy emas edi (`spec/tarix/tekshiruv/qabul-7-ekran-api.md`, X-02; `spec/kod-uchun/01-qarorlar.md`, Founder ko'rib chiqishi #1). Yuqoridagi jadval shu standart bo'yicha yangilandi — tasdiqlandi ("Hamma narsani egasi boshqaradi", `spec/tarix/tekshiruv/asoschi-qarorlari-2026-10-15.md`, Q1).

*Standart limitlar (2026-10-15: foydalanuvchi qarori)*: M03 (chegirma) — Kassir PIN'siz **5% gacha**; M02 (qaytarish) — chek bilan PIN'siz **100 000 so'mgacha** (chek yo'q bo'lsa har doim PIN); M16 (kassa pul harakati) — "Pul olish" PIN'siz **50 000 so'mgacha**; chekni bekor qilish (void) Kassirga limitsiz, audit bilan. Bu raqamlar **standart** qiymat — Egasi M13 (Huquqlar) orqali istalgan paytda o'zgartirishi mumkin (`03-modullar-talablari.md`, US-M02-02/US-M03-01/US-M16-01; `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #1).

*M15–M18 izohi (2026-10-14): Kassir xarajatni faqat M16 "Pul olish → Xarajat to'lovi" orqali yozadi (M15'ga avtomatik tushadi); M17 `billing.manage` faqat Egasi; platforma admini (ADM-01, `platform.admin`) tenant rollariga kirmaydi — `15-xavfsizlik-va-audit.md` §3.4.*

*M13 izohi (2026-10-15: foydalanuvchi qarori): M13 endi faqat rol/huquq emas — Egasi uchun to'liq foydalanuvchi boshqaruvi (xodim qo'shish, bloklash, parol/PIN tiklash, faol sessiya/qurilmalarni ko'rish va bekor qilish — US-M13-04…07) ham shu modulga kiradi; platforma admini (ADM-01) faqat tenant Egasi (owner) hisobi darajasida shu funksiyalarga ega (US-M13-08). Autentifikatsiya — o'z OAuth 2.0 implementatsiyasi, mock yo'q (`spec/kod-uchun/14-autentifikatsiya-oauth2.md`).*

---

## Ochiq savollar

1. Huquqlar matritsasidagi aniq taqsimot (6-bo'lim) tadqiqot fayllarida tayyor jadval sifatida topilmadi — bu hujjatda loyihalashtirilgan taxmin; MVP ishlab chiqishdan oldin foydalanuvchi bilan tasdiqlanishi kerak.
2. *(2026-10-15: hal qilindi — foydalanuvchi qarori)* ~~Chegirma/qaytarish/nasiya uchun aniq summa limitlari~~ — endi standart qiymatlar bor (6-bo'lim yangi izoh: chegirma 5%, qaytarish 100 000, pul olish 50 000), Egasi tomonidan o'zgartiriladi.
3. *(2026-10-15: hal qilindi — foydalanuvchi qarori)* Markirovkalangan tovar offline sotilganda kassir nima qilishi kerak — endi aniq: narx qurilmada ma'lum bo'lsa sotuvga ruxsat (CRPT tekshiruvi internet qaytganda), narx noma'lum bo'lsa taqiq (`03-modullar-talablari.md`, US-M01-03). Qaytarish/ko'chirish uchun siyosat hali ochiq.
4. Kichik do'konda bir necha rol birlashuvi uchun aniq segment chegaralari (1-3 xodim, 4+ xodim) — bu hujjatdagi 0-bo'limdagi guruhlash taxminiy, tadqiqotda raqam bilan tasdiqlanmagan.
5. Buxgalterning **5 kalendar kunlik** davlat hisobotini solishtirish jarayonida aniq ish oqimi (kim birinchi ko'radi, qanday eskalatsiya) — `02-arxitektura` jamoasi bilan birga ishlab chiqilishi kerak *(2026-10-14: "5 ish kuni" → "5 kalendar kun" tuzatildi, muddatning o'zi va huquqiy asosi endi aniq)*.
6. Omborchi tovar qabul qilganda, yetkazib beruvchi vakilining ishonchnomasini 2026-01-01 dan majburiy Vakolat.uz orqali tekshirish kerakmi — `research_notes/texnik/09-soliq-integratsiyasi.md` (E-ishonchnoma bandi) bu talabni qayd etadi, lekin API hujjati topilmagan va bu jarayonning M07 moduliga aniq qanday integratsiya qilinishi ochiq.

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
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — autentifikatsiya arxitekturasi — Foydalanuvchi qarori, 2026-10-15
- `spec/tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` — 2026-10-15, tavsiya #1 (standart rol limitlari)
