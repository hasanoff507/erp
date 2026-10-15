# 18 MVP modul funksional talablari *(2026-10-14: 14 dan oshirildi — M15 Xarajatlar, M16 Kassa pul harakati, M17 Obuna va ro'yxatdan o'tish, M18 Bildirishnomalar qo'shildi)*

## Asosiy xulosalar

1. 18 modulning har biri uchun maqsad, kamida 3 foydalanuvchi hikoyasi (US-Mxx-nn), qabul mezonlari (Given/When/Then yoki tekshiriladigan ro'yxat), davlat tizimlari bog'liqligi, offline xatti-harakati va chekka holatlar yozilgan *(2026-10-14: 14 dan 18 ga oshdi, pastda M15-M18)*.
2. **M01 Kassa** — eng murakkab modul: offline-first (append-only event-log, 48 soat OFD chegarasi — `research_notes/texnik/02-kassa-ofd-markirovka.md`, 1-ilova 31-band), markirovka tekshiruvi va 2026-07-01'dan yuridik shaxslar uchun majburiy yagona QR (UzQR, bank) to'lov qabulini birlashtiradi *(2026-10-14: tekshiruv)*.
3. **M10 QQS** va **M12 Hisobotlar** — 2026-yildagi eng katta arxitektura o'zgarishini (davlat hisobotni o'zi tuzadi, **5 kalendar kun** ichida tuzatish *(2026-10-14: tuzatildi — avval "5 ish kuni" deb yozilgan, huquqiy asos endi aniq: Soliq kodeksi 81-moddasi, O'RQ-1108, 2025-12-25, lex.uz/docs/-7944527)*) tashuvchi modullar; rasmiy API yo'qligi sababli MVP'da bu jarayon **qo'lda/yarim-avtomatik** boshlanadi (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 86-qator).
4. Markirovka (Asl belgisi/CRPT Turon), e-faktura (Didox/Faktura.uz), e-TTN va MXIK bo'yicha rasmiy ochiq API hujjatlari yopiq yoki topilmagan — bu modullardagi ko'p qabul mezoni shartli ravishda "agar API ochilsa" deb belgilangan va ochiq savol sifatida qayd etilgan.
5. Offline xatti-harakati faqat **M01 (kassa)** uchun to'liq majburiy talab; boshqa modullarda (M04, M05, M06, M07) offline faqat qisman (mahalliy qoralama, keyin sinxronlash) qo'llab-quvvatlanadi, chunki ular odatda internet mavjud joyda (ofis/ombor) bajariladi.
6. Mavjud ERP tizimlarining jonli ma'lumotlar modeli faqat **struktura namunasi** sifatida ishlatildi — O'zbekiston-specific qiymatlar (QQS 12%, MXIK/IKPU, Asl belgisi) hech qachon ulardan emas, faqat O'zbekiston qonunchiligi manbalaridan olindi (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`, 2-band) *(2026-10-14: neytral ifodalandi — koordinator direktivasi)*.
7. Har bir modulda kamida bitta chekka holat davlat tizimi bilan bog'liq xavfni (markirovka jarimasi, offline sinxronlash kechikishi, AI xavf-baholash) aks ettiradi — bu `11-raqobatchilar-kamchiliklari.md`dagi real shikoyatlardan kelib chiqadi.
8. Aniq limit summalari, muddatlar va ba'zi API formatlari tadqiqotda yo'q — bular har bir modul ichida **"taxmin"** yoki **"ochiq savol"** deb aniq belgilangan, umumiy ro'yxat hujjat oxirida.

---

## M01 — Kassa (POS)

**Maqsad**: mijozga tez, aniq va fiskal talablarga mos sotuv amalga oshirish, internet bo'lmaganda ham ishlashni davom ettirish.

### Foydalanuvchi hikoyalari

**US-M01-01**: Kassir sifatida tovarni skanerlab/tanlab chek yaratmoqchiman, mijozga tez xizmat ko'rsatish uchun.
- Given kassir smena ochgan, When tovar shtrix-kodi skanerlanadi yoki qo'lda tanlanadi, Then tovar chekka narx va MXIK kodi bilan qo'shiladi.
- Given chekda bir yoki bir nechta tovar bor, When kassir to'lovni tanlaydi (naqd/karta/yagona QR (UzQR, bank)/Payme/Click/Uzum yoki aralash) *(2026-10-14: tekshiruv)*, Then chek yakunlanadi va fiskal belgi+QR-kod bilan chop etiladi/ko'rsatiladi (`research_notes/texnik/02-kassa-ofd-markirovka.md`, "Chek formati va majburiy rekvizitlar").
- *(2026-10-15: foydalanuvchi qarori)* Given do'konda mustaqil (bankka to'g'ridan-to'g'ri ulangan) karta terminali bor, lekin u veb-kassaga integratsiyalanmagan, When kassir "Karta" to'lov turini qo'lda belgilaydi (online va offline'da ham ruxsat), Then ixtiyoriy "terminal operatsiya raqami" maydoni kiritiladi (ixtiyoriy, terminal kvitansiyasi bilan solishtirish uchun) va chek "karta" to'lov turi bilan yakunlanadi; smena yopilganda Z-hisobotda "karta" jami alohida chiqadi (M16, US-M16-02/03), Egasi kun oxirida bank ko'chirmasi bilan solishtiradi.

**US-M01-02**: Kassir sifatida internet bo'lmaganda ham savdo qilishni, keyin avtomatik sinxronlanishini istayman.
- Given internet aloqasi yo'q, When kassir chek yaratadi, Then chek mahalliy append-only jurnalga yoziladi va "offline" belgisi bilan ko'rsatiladi.
- Given internet qaytdi, When tizim avtomatik sinxronlanadi, Then barcha offline cheklar OFD'ga 48 soat ichida yuboriladi (`research_notes/texnik/02-kassa-ofd-markirovka.md`, 1-ilova 31-band).
- Given offline davr 48 soatdan oshmoqda, When tizim buni aniqlaydi, Then kassir va Egasiga ogohlantirish ko'rsatiladi.

**US-M01-03**: Kassir sifatida markirovkalangan tovar (suv, ichimlik, tamaki va h.k.) sotishda kodni tekshirishni istayman.
- Given tovar Asl belgisi bilan markirovkalangan, When kassir DataMatrix kodini skanerlaydi, Then tizim (online bo'lsa) kodni CRPT Turon tizimi orqali tekshiradi va "chiqarish" (spisaniye) amalini bajaradi.
- Given kod noto'g'ri/takroriy/muddati o'tgan, When tekshiruv muvaffaqiyatsiz bo'ladi, Then MVP standart xatti-harakati sifatida **sotuv rad etiladi** (kassir qo'lda almashtirish/markirovkasiz tovar bilan davom etishi mumkin) — bu qat'iy taqiq siyosati **taxmin**, chunki CRPT Turon rasmiy API hujjati yopiq va aniq rasmiy talab topilmadi (`research_notes/texnik/02-kassa-ofd-markirovka.md`, 5-band; Ochiq savol 2, pastda).
- *(2026-10-15: foydalanuvchi qarori)* Given internet yo'q (offline) va tovar narxi qurilmada ma'lum (keshlangan katalog narxi, M09), When kassir DataMatrix kodini skanerlaydi, Then sotuv **ruxsat etiladi** — kod mahalliy jurnalga yoziladi, CRPT Turon'da haqiqiylik tekshiruvi va "chiqarish"/"sotildi" belgisi internet qaytganda amalga oshiriladi (batafsil — Offline xatti-harakati, pastda).
- Given internet yo'q va tovar narxi qurilmada ma'lum emas (hali sinxronlanmagan yangi tovar), When kassir shu tovarni sotishga harakat qiladi, Then sotuv **ruxsat etilmaydi** — narx online bo'lganda sinxronlangandan keyin sotiladi.

**US-M01-04**: Kassir sifatida smenani ochish va yopishni (Z-hisobot) istayman.
- Given ish kuni boshlanadi, When kassir boshlang'ich naqd summani kiritadi, Then smena "ochiq" holatga o'tadi.
- Given smena yakunlanmoqda, When kassir "smenani yopish"ni bosadi, Then Z-hisobot generatsiya qilinadi va OFD'ga yuboriladi.

**US-M01-05** *(2026-10-14: tekshiruv)*: Kassir sifatida yuridik shaxs bo'lgan do'konda mijozdan bank tomonidan generatsiya qilingan yagona QR kod (UzQR) orqali to'lov qabul qilishni istayman, chunki 2026-07-01'dan bu majburiy (PF-246-son, 10.12.2025, 3-band "b").
- Given tenant yuridik shaxs va filialga bank tomonidan berilgan yagona QR (statik yoki dinamik) ulangan, When kassir to'lov usuli sifatida "Yagona QR (UzQR)"ni tanlaydi, Then chek summasi bilan QR ko'rsatiladi (dinamik QR bo'lsa) yoki statik QR bo'yicha to'lov kutiladi va bank tasdig'i kelgach chek yakunlanadi.
- Given tenant yuridik shaxs va 2026-07-01 yoki undan keyingi sana, When filialda yagona QR sozlanmagan, Then tizim Egasi va kassirga "Yagona QR ulanmagan — savdo qoidalarini buzish xavfi" ogohlantirishini ko'rsatadi (sotuvni bloklamaydi).
- Given tenant YTT (yakka tartibdagi tadbirkor), When sozlamalar ochiladi, Then yagona QR ixtiyoriy deb ko'rsatiladi (PF-246 3-band "b" faqat yuridik shaxslarni nomlaydi).
- Yagona QR Click/Payme/Uzum'ning o'rnini bosmaydi: ular ixtiyoriy kanal sifatida qoladi ("ham majburiy").

**US-M01-06** *(2026-10-15: foydalanuvchi qarori — qo'shildi, ochiq savol 12 yopildi)*: Buxgalter sifatida fiskal chek bilan allaqachon sotilgan tovarga keyinroq yuridik shaxs (B2B) mijoz e-faktura so'rasa, shu sotuv uchun chiquvchi e-faktura chiqarishni istayman.
- Given tovar fiskal chek bilan (B2C yoki avvaldan e-fakturasiz) sotilgan, When mijoz (endi yuridik shaxs sifatida) keyinroq shu xaridga e-faktura talab qiladi, Then Buxgalter BO-15'da asl chekni tanlab yangi chiquvchi e-faktura yaratadi — bu e-faktura `einvoices.related_doc` orqali asl chekka bog'lanadi.
- Given e-faktura chekka bog'langan, Then QQS **ikkinchi marta hisoblanmaydi** — e-faktura faqat asl chekda allaqachon hisoblangan QQS summasini rasmiylashtiradi (hujjat ko'rinishida); `ledger_entries`/`vat_moves` registrlariga yangi yozuv qo'shilmaydi (append-only saqlanadi), bog'lanish faqat hujjat darajasida `einvoices.related_doc` orqali JOIN bilan quriladi (`02-provodka-qoidalari.md` §2.22) *(2026-10-15: qabul-5 O13 bo'yicha aniqlashtirildi)*.
- Given e-faktura E-IMZO bilan imzolanib EDO operatoriga yuborilgan, Then chek va e-faktura o'zaro ikki tomonlama ko'rinadi (chekdan e-fakturaga, e-fakturadan chekka).

### Davlat tizimlari bog'liqligi
OFD (fiskal operator — "Yangi texnologiyalar" DUK), Asl belgisi (CRPT Turon), MXIK (chekning majburiy rekviziti), 2026-07-01'dan yuridik shaxslar uchun bank tomonidan generatsiya qilingan yagona QR kod (UzQR) orqali to'lov qabul qilish majburiy (PF-246-son, 10.12.2025, 3-band "b", [lex.uz/uz/docs/-7897630](https://lex.uz/uz/docs/-7897630)); Click/Payme/Uzum — ixtiyoriy kanallar. *(2026-10-14: tekshiruv)*

*(2026-10-15: foydalanuvchi qarori)* **Fiskal yo'l**: birinchi kundanoq o'z virtual kassamizni Davlat reyestriga kiritish arizasi boshlanadi (VMQ-943, 4-ilova; ~50 ish kuni); ariza tasdiqlanguncha pilot (10–20 do'kon) bitta reyestr hamkori (Multikassa yoki E-POS Communicator) orqali o'tkaziladi, hamkor haqini biz to'laymiz — mijozga ko'rinmaydi (`06-mvp-chegarasi.md`, §3.3 va §5; `spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #2).

*(2026-10-15: foydalanuvchi qarori)* **CRPT Turon (Asl belgisi) integratsiyasi MVP'da**: har bir do'kon o'zining bepul "ishtirokchi" (Participant) kabinetidan "API Key Manager" roli bilan API kalit yaratadi va tizimimizga kiritadi (CRPT Turon yordam markazi — ishonch darajasi o'rta, sahifa 403 bo'lgani uchun faqat qidiruv parchalaridan ma'lum, Xat 2 javobi kutilmoqda). Agar bu yo'l rasman rad etilsa — **zahira: reyestr hamkori orqali proksi integratsiya**. Ikkalasi ham ishga tushmasa — markirovkalangan tovar sotuvi tizimda **bloklanadi** (CRPT'siz bu tovar sotilmaydi), US-M01-03 xatti-harakati shunga mos.

### Offline xatti-harakati
Majburiy: append-only event-log (outbox naqshi), 48 soat OFD chegarasi. Markirovka tekshiruvi (CRPT Turon'da real-vaqt tasdiqlash) offline ishlay olmaydi (markaziy tizimga bog'liq) — lekin *(2026-10-15: foydalanuvchi qarori — avvalgi "ochiq savol" hal qilindi)* **markirovkalangan tovarni offline sotish RUXSAT ETILADI**, agar tovar narxi qurilmada ma'lum bo'lsa (POS'ga oldindan sinxronlangan/keshlangan katalog narxi, M09): DataMatrix kod skanerlanadi, qurilmada **faqat mahalliy** (kod formati/nazorat raqami) tekshiriladi va kod mahalliy jurnalga yoziladi, CRPT Turon'da haqiqiylik tekshiruvi va "chiqarish" (spisaniye)/"sotildi" belgisi internet qaytganda amalga oshiriladi (asinxron, outbox). Agar tovar narxi qurilmada ma'lum **bo'lmasa** (hali sinxronlanmagan yangi tovar) — bu tovar bilan sotuv offline rejimda **ruxsat etilmaydi**. Qaytarish/ko'chirish uchun offline siyosati hali **ochiq savol** (pastda) — faqat sotuv (bu modul) uchun qaror qabul qilindi. *Eslatma: bu mahsulot qarori; yuridik tasdiq (huquqshunos bilan) tavsiya etiladi, lekin spec darajasidagi qaror allaqachon qabul qilingan.*

### Chekka holatlar
- Internet savdo o'rtasida uzilsa — chek offline rejimga avtomatik o'tishi kerak, mijoz kutib qolmasligi uchun.
- Fiskal modul texnik xatosi — chek berilmasligi huquqiy javobgarlik keltiradi (`research_notes/texnik/11-raqobatchilar-kamchiliklari.md`).
- Aralash to'lov (qisman naqd + qisman karta) qo'llab-quvvatlanishi kerak.
- Bir nechta kassa bir smenada parallel ishlashi (filial/do'kon ichida bir nechta POS).
- *(2026-10-14: tekshiruv)* Yagona QR to'lovi bank tasdig'i kelmay qolsa (internet uzilishi yoki to'lov kechikishi) — chek "to'lov kutilmoqda" holatida qoladi, kassir boshqa to'lov usuliga o'tishi yoki bekor qilishi mumkin; ikki marta to'lov tushishining oldini olish uchun provider_tx_id bo'yicha idempotentlik.
- *(2026-10-14: tekshiruv)* To'lovdan oldin qator o'chirilsa yoki chek bekor qilinsa (`sales.void`) — fiskal chek yo'q, lekin bekor qilingan qatorlar va summa `sale.draft_voided` voqeasi bilan audit uchun serverga yuboriladi; smena hisobotida bekor qilishlar soni va summasi ko'rsatiladi.
- *(2026-10-14: tekshiruv)* Chekni qayta chop etish — nusxada "NUSXA" belgisi, har qayta chop etish audit jurnaliga yoziladi (kim, qachon, qaysi chek); son cheklanmaydi.
- *(2026-10-15: foydalanuvchi qarori — talab sifatida belgilandi, ochiq savol 12 yopildi)* Chek bilan sotilgan tovarga keyinroq yuridik shaxs mijoz e-faktura so'rasa — bu **qo'llab-quvvatlanadi** (US-M01-06): shu chekka bog'langan chiquvchi e-faktura yaratiladi (`einvoices.related_doc`), QQS ikkinchi marta hisoblanmaydi.
- *(2026-10-15: foydalanuvchi qarori — D3, qurilma/chop etish qamrovi)* **iPhone/iPad (iOS)**: AIOS kassa/back-office **o'rnatilgan PWA** sifatida (Home Screen'ga qo'shilgan) ishlaydi. iOS'da chek chop etish faqat **bulut-print (cloud-print) printer** (masalan Star CloudPRNT, Epson Server Direct Print — model **taxmin**, tasdiqlanmagan) orqali yoki **elektron chek** (QR-kod/Telegram orqali yuborish) bilan mumkin — iOS Safari/PWA USB/Bluetooth printer ulanishini qo'llab-quvvatlamaydi. **Chrome/Edge (Windows, Android, shu jumladan Android Chrome)** — USB, Bluetooth, tarmoq (LAN/Wi-Fi) va bulut printerlarning barchasini qo'llab-quvvatlaydi (`04-ekranlar-va-ux.md` §1.6). Bulut-print printerlarining O'zbekistonda mavjudligi/narxi va faqat-elektron-chek bilan cheklanishning fiskal/huquqiy ruxsati — **ochiq savol** (pastda).

---

## M02 — Qaytarish

**Maqsad**: mijozdan tovarni qaytarib olish va pul/balansni to'g'ri tuzatish.

### Foydalanuvchi hikoyalari

**US-M02-01**: Kassir sifatida mijozdan tovarni asl chek bo'yicha qaytarib olishni istayman.
- Given mijozda asl chek (raqami/QR) bor, When kassir qaytarishni boshlaydi va chekni topadi, Then qaytarilgan tovar miqdori ombor balansiga qaytadi (M04) va pul naqd/kartaga qaytariladi yoki nasiya balansi tuzatiladi (M08).
- Given asl chek topilmaydi, When kassir shunga qaramay qaytarishga harakat qiladi, Then operatsiya Menejer tasdig'isiz yakunlanmaydi.

**US-M02-02**: Menejer sifatida belgilangan limitdan yuqori qaytarishni tasdiqlashni istayman.
- Given qaytarish summasi limitdan yuqori, When kassir qaytarishni yuboradi, Then operatsiya "kutilmoqda" holatiga o'tadi va Menejerga bildirishnoma boradi.
- Given Menejer tasdiqlaydi, When u "tasdiqlash" tugmasini bosadi, Then qaytarish yakunlanadi; rad etilsa, operatsiya bekor qilinadi va sabab yoziladi.
- *(2026-10-15: foydalanuvchi qarori)* **Standart limit**: asl chek bilan qaytarish — Kassir PIN'siz **100 000 so'mgacha** mustaqil amalga oshiradi; chek topilmasa (asl chek yo'q) — summadan qat'i nazar **har doim Menejer PIN** talab qilinadi (US-M02-01'dagi "topilmagan chek" holati bilan birga). Egasi istalgan paytda bu limitni (M13 orqali) o'zgartirishi mumkin (`01-rollar-va-ssenariylar.md`, 6-bo'lim izohi; `spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #1).

**US-M02-03**: Buxgalter sifatida qaytarilgan tovar bo'yicha QQS tuzatishini avtomatik ko'rishni istayman.
- Given qaytarish yakunlangan, When tizim buxgalteriya yozuvini yaratadi, Then sotuv summasi va unga mos QQS summasi manfiy yozuv bilan tuzatiladi (M10, M11).

### Davlat tizimlari bog'liqligi
Markirovkalangan tovar qaytarilganda Asl belgisi tizimida mos "qaytarish" operatsiyasi qayd etilishi talab qilinishi mumkin — rasmiy tasdiq topilmadi, **ochiq savol**.

### Offline xatti-harakati
Oddiy (markirovkalanmagan) tovar uchun qaytarish offline rejimda mahalliy jurnalga yoziladi (M01 bilan bir xil append-only naqsh), internet qaytganda sinxronlanadi. *(2026-10-15: foydalanuvchi qarori)* **Markirovkalangan (Asl belgisi) tovarni qaytarish faqat internet bor paytda mumkin** — offline rejimda bunday tovar uchun "Qaytarish" tugmasi bloklanadi (POS-05'da aniq xabar bilan): sabab — qaytarish uchun kod yozilgan rasmiy qaytarish cheki kerak (buxgalter.uz, tasdiqlangan fakt) va CRPT Turon markaziy tizimga bog'liq bo'lgani uchun offline tekshirib bo'lmaydi, firibgarlik xavfi yuqori (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #5).

### Chekka holatlar
- Qisman qaytarish (chekdagi bir nechta tovardan faqat bittasi).
- *(2026-10-15: hal qilindi — foydalanuvchi qarori)* Markirovkalangan tovarni qaytarish siyosati endi aniq: **faqat online** (yuqoridagi Offline xatti-harakati). Muddati o'tgan tovarni qaytarish siyosati hali ochiq.
- Nasiya bilan sotilgan tovarni qaytarish — balans tuzatish ikki tomonlama (ombor + qarz) bo'ladi.

---

## M03 — Chegirma

**Maqsad**: chegirma va promo aksiyalarini nazoratli tarzda qo'llash. (Loyallik/bonus kartasi dasturi — **keyingi bosqich**, CRM/sodiqlik moduli bilan birga; MVP'da emas — `spec/README.md`, `research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 2-band.)

### Foydalanuvchi hikoyalari

**US-M03-01**: Kassir sifatida ruxsat etilgan limit ichida chekka chegirma berishni istayman.
- Given chegirma foizi limitdan past, When kassir chegirmani kiritadi, Then chek summasi avtomatik qayta hisoblanadi.
- Given chegirma limitdan yuqori, When kassir kiritishga harakat qiladi, Then tizim Menejer PIN-kodini so'raydi.
- *(2026-10-15: foydalanuvchi qarori)* **Standart limit**: Kassir PIN'siz chekka **5% gacha** chegirma beradi; chekni bekor qilish (`sales.void`) Kassirga limitsiz ruxsat etiladi, lekin har doim audit yoziladi. Egasi istalgan raqamni (M13 orqali) o'zgartirishi mumkin — sabab: raqobatchilarning (Loyverse, Square, BILLZ, REGOS) birortasida ham tayyor standart raqam yo'q, kichik standart qiymat kundalik mayda amallarni to'xtatmaydi (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #1).

**US-M03-02**: Menejer sifatida avtomatik chegirma qoidalarini (kategoriya, muddat, mijoz toifasi bo'yicha) sozlashni istayman.
- Given yangi aksiya boshlanishi kerak, When Menejer qoida yaratadi (tovar/kategoriya, foiz, boshlanish-tugash sanasi), Then qoida saqlanadi va kassada avtomatik qo'llaniladi, muddat tugagach avtomatik to'xtaydi.

**US-M03-03**: Egasi sifatida chegirmalarning margin'ga ta'sirini hisobotda ko'rishni istayman.
- Given tanlangan davr, When Egasi hisobotni ochadi, Then berilgan chegirmalar summasi va ular tufayli kamaygan margin ko'rsatiladi (M12 bilan bog'liq).

### Davlat tizimlari bog'liqligi
Chegirmali (yakuniy) narx QQS bazasiga asos bo'ladi — QQS chegirmadan keyingi summadan hisoblanishi kerak (M10).

### Offline xatti-harakati
Chegirma qoidalari oldindan POS'ga sinxronlanadi; offline rejimda oxirgi yuklangan qoidalar bo'yicha ishlaydi, markaz bilan real-time aloqa shart emas.

### Chekka holatlar
- *(2026-10-15: hal qilindi — foydalanuvchi qarori)* ~~Bir nechta chegirma bir chekda birlashishi (stacking) — siyosat kerak~~ — endi aniq: chegirmalar **yig'ilmaydi**. Agar bir chekda bir nechta chegirma manbai to'qnashsa (masalan mijozning doimiy chegirma %'i — M09/US-M09-07, M08 — va kassir/aksiya chegirmasi), **faqat bittasi — mijozga eng katta foyda beradigani** qo'llaniladi (Odoo'ning "bitta eng mos qoida" modeliga mos, `spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #8).
- Chegirma tovar narxini manfiy qilib yubormasligi tekshirilishi kerak.
- Aksiya muddati offline paytda tugashi — POS eski qoidani ishlatib qolishi mumkin.
- *(2026-10-14: tekshiruv)* "2+1" turidagi aksiya — US-M03-02 qoidasi sifatida (uchinchi donaga 100% chegirma), alohida "bepul tovar" hujjati emas; QQS chegirmadan keyingi summadan (taxmin, buxgalter tasdig'i).
- *(2026-10-15: foydalanuvchi qarori)* **Optom narx jadvali yo'q**: MVP'da alohida "optom narx" turi yo'q (M09'ga qarang) — mijozning doimiy chegirmasi shu yerdagi "faqat bitta eng foydali chegirma" qoidasi bilan bir xil mantiqda ishlaydi.

---

## M04 — Ombor qoldig'i

**Maqsad**: har bir ombordagi tovar miqdorini real vaqtda to'g'ri ko'rsatish.

### Foydalanuvchi hikoyalari

**US-M04-01**: Omborchi sifatida tovar kelganda balansni avtomatik yangilashni istayman.
- Given xaridnoma bo'yicha tovar qabul qilindi (M07), When qabul hujjati tasdiqlanadi, Then ombor balansi (miqdor) avtomatik oshadi.

**US-M04-02**: Menejer sifatida minimal zaxira chegarasiga yetilganda ogohlantirish olishni istayman.
- Given tovar uchun minimal chegara belgilangan, When qoldiq shu chegaraga yetadi yoki pastga tushadi, Then Menejerga bildirishnoma yuboriladi.

**US-M04-03**: Egasi/Menejer sifatida barcha filiallar bo'yicha umumlashtirilgan qoldiqni ko'rishni istayman.
- Given bir nechta filial (M14) mavjud, When konsolidatsiyalangan hisobot ochiladi, Then har bir filial va umumiy jami qoldiq ko'rsatiladi.

**US-M04-04**: Egasi/Menejer sifatida tizimga birinchi marta kirganda boshlang'ich tovar/qoldiq ro'yxatini tizimga kiritishni istayman *(2026-10-14: qo'shildi — koordinator direktivasi, `07-tuzatishlar-va-yechimlar.md`)*.
- Given yangi tenant ro'yxatdan o'tgan, When Egasi/Menejer boshlang'ich katalog/qoldiqni kiritadi, Then uchta yo'l qo'llab-quvvatlanadi: (1) **qo'lda kiritish** (tovar-tovar), (2) **Excel/CSV shablon** orqali ommaviy import, (3) **AI-03** yordamida qog'oz katalog/qoldiq varag'i fotosidan kiritish (AI faqat o'qiydi, foydalanuvchi tasdiqlaydi).
- **Boshqa hech qanday tashqi buxgalteriya/ERP tizimi bu ro'yxatda yo'q va hech qachon bo'lmaydi** — AIOS boshqa tizimlarning fayllarini o'qimaydi, ular bilan sinxronlanmaydi, ulardan hech qanday ma'lumot import qilinmaydi (`06-mvp-chegarasi.md`, Won't ro'yxati). Mavjud tizimlar faqat ma'lumotlar modelini loyihalashda struktura namunasi sifatida ishlatilgan, mahsulotning o'zida ular bilan aloqa yo'q *(2026-10-14: neytral ifodalandi — koordinator direktivasi)*.
- *(2026-10-15: foydalanuvchi qarori)* (3)-yo'l (AI-03) — endi MVP ichida (2026-10-14'dagi "MVP'dan keyin" tekshiruv qarori bekor qilindi); MVP'da uchta yo'l (1), (2), (3) barchasi mavjud. Kiritilgan qoldiq "boshlang'ich qoldiq" hujjati sifatida o'tkaziladi (chek/faktura yo'q, `02-provodka-qoidalari.md` 2.21).
- *(2026-10-15: kamchiliklar-yakuniy #18/9.2 bo'yicha qo'shildi)* **Excel/CSV shablon formati** (2-yo'l, `import_jobs`): `products.csv` — ustunlar `name, barcode, unit_code, mxik_code, vat_rate, price, category, is_marked`; `opening_stock.csv` — `barcode, qty, unit_cost, expiry_date`; `opening_debts.csv` — `name, phone, amount, direction` (`receivable`/`payable`), `date`. Kodlash UTF-8, ustun ajratgichi `;`, kasr son nuqta (`.`) bilan; validatsiya xatolari qator/maydon darajasida `import_jobs.errors`ga yoziladi (validate→commit ikki bosqich).

**US-M04-05**: Egasi/Buxgalter sifatida tovar tannarxini hisoblash usulini korxonamga mos tanlashni istayman *(2026-10-14: qo'shildi — foydalanuvchi qarori: ikkala usul ham bo'lishi kerak)*.
- Given korxona sozlamalarida "Hisob siyosati → zaxira baholash usuli" bor, When Egasi/Buxgalter usulni tanlaydi, Then ikki variant mavjud: **O'rtacha narx (AVECO)** — standart (default), kichik do'konlar uchun soddaroq; **FIFO** — kattaroq do'konlar/ulgurji uchun, partiya bo'yicha aniqroq tannarx. Ikkalasi BHMS №4 ga mos (LIFO yo'q) (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`).
- Ikkala usul **barcha tariflarda** mavjud — buxgalteriya to'g'riligi tarifga bog'lanmaydi.
- Usul hisob davri ichida o'zgartirilmaydi; o'zgartirish faqat **keyingi hisobot yili boshidan** kuchga kiradi va tizim buni ogohlantirish bilan tasdiqlatadi (hisob siyosati izchilligi — buxgalter bilan tasdiqlanadi).
- Given usul tanlangan, When sotuv/qaytarish/ko'chirish/hisobdan chiqarish o'tkaziladi, Then sotilgan tovar tannarxi (COGS) tanlangan usul bo'yicha avtomatik hisoblanadi va M11 provodkasiga tushadi.

**US-M04-06** *(2026-10-14: tekshiruv)*: Omborchi/Egasi sifatida yaroqlilik muddati yaqinlashgan tovarni oldindan bilishni va muddati o'tganini hisobdan chiqarishni istayman.
- Given kirimda partiya uchun yaroqlilik muddati kiritilgan (ixtiyoriy maydon), When muddatga 7 kun qolganda (taxmin, sozlanadi), Then Egasi/Menejerga ro'yxat (tovar, partiya, qoldiq, muddat) M18 orqali boradi va BO-03'da belgi ko'rinadi.
- Given tovar muddati o'tgan/buzilgan yoki bepul berilgan (namuna, sovg'a), When Omborchi "Hisobdan chiqarish" hujjatini sabab bilan yaratadi, Then qoldiq kamayadi va tannarx xarajatga yoziladi (`02-provodka-qoidalari.md` 2.12); bepul berishning QQS oqibati — buxgalter tasdig'i (ochiq savol). Yetkazib beruvchi qaytarib olsa — US-M07-05.

### Davlat tizimlari bog'liqligi
Markirovkalangan tovarlar uchun balans kod (serial) darajasida, oddiy tovarlar uchun miqdor darajasida kuzatiladi — Asl belgisi tizimi bilan moslik talab qilinadi.

### Offline xatti-harakati
POS'dagi sotuv (kamayish) offline event-log orqali yoziladi va sinxronlanganda balansga qo'llaniladi; bu operatsiya faqat kamaytiruvchi bo'lgani uchun konflikt xavfi past (CRDT shart emas, `research_notes/texnik/04-arxitektura-va-stack.md`, 4-band).

### Chekka holatlar
- Manfiy balansga (overselling) yo'l qo'ymaslik siyosati — offline paytda ikki kassa bir xil oxirgi tovarni sota olishi mumkin, sinxronlashda konflikt yuzaga keladi.
- Bir mahsulotning bir nechta o'lchov birligi (dona/quti/kg) balansi.
- **Tannarx (US-M04-05) uchun texnik talablar** *(2026-10-14)*:
  - Har bir kirim **partiya (lot)** sifatida saqlanadi (sana, miqdor, kirim narxi, manba hujjat) — usul AVECO bo'lsa ham. Shunda keyingi yil FIFO'ga o'tish yoki tekshiruv uchun qayta hisoblash mumkin bo'ladi; partiya markirovka va yaroqlilik muddati kuzatuvi bilan ham bir xil tuzilma.
  - AVECO: har kirimda o'rtacha narx qayta hisoblanadi (ombor bo'yicha alohida).
  - FIFO: chiqimda eng eski partiyadan boshlab yechiladi; bitta chek bir nechta partiyaga bo'linishi mumkin.
  - **O'tgan sanali hujjat** (kechikkan kirim, offline sotuv kech sinxronlangani, qaytarish) kiritilsa — shu sanadan keyingi tannarx avtomatik **qayta hisoblanadi** (qayta o'tkazish) va yopilgan davrga tegsa bloklanadi.
  - Offline POS sotuv paytida tannarxni hisoblamaydi — faqat miqdorni yozadi; tannarx serverda sinxronlashdan keyin hisoblanadi.
  - Manfiy qoldiqda sotuv bo'lsa (offline konflikt) — tannarx vaqtincha oxirgi ma'lum narx bilan olinadi va keyingi kirimda tuzatiladi.
- *(2026-10-15: kamchiliklar-yakuniy #21 bo'yicha qo'shildi)* **Asosiy vosita vs tovar**: Asosiy vositalar (uskuna, jihoz va h.k.) M04 katalogiga tovar sifatida kiritilmaydi; ularning xaridi M15 (Xarajatlar) xarajati sifatida yoziladi, ombor/tannarx hisobiga kirmaydi. Tovar yaratish ekranida ogohlantirish matni ko'rsatiladi: "Agar bu uskuna/jihoz bo'lsa, uni Xarajatlar bo'limiga kiriting, tovar katalogiga emas."

---

## M05 — Inventarizatsiya

**Maqsad**: jismoniy sanash orqali haqiqiy qoldiqni tasdiqlash va farqni aniqlash.

### Foydalanuvchi hikoyalari

**US-M05-01**: Omborchi sifatida sanash varag'ini olib, haqiqiy sonlarni kiritishni istayman.
- Given inventarizatsiya boshlangan, When Omborchi har bir tovar bo'yicha haqiqiy sonni kiritadi, Then tizim haqiqiy son bilan tizimdagi qoldiqni solishtirib farqni ko'rsatadi.

**US-M05-02**: Menejer/Egasi sifatida aniqlangan farqni (ortiqcha/kamomad) ko'rib tasdiqlashni istayman.
- Given farq ro'yxati tayyor, When Menejer/Egasi ko'rib tasdiqlaydi, Then ombor balansi (M04) haqiqiy songa moslashtiriladi.

**US-M05-03**: Buxgalter sifatida kamomad/ortiqchani buxgalteriya yozuviga aks ettirishni istayman.
- Given inventarizatsiya tasdiqlangan, When tizim buxgalteriya yozuvini yaratadi, Then kamomad xarajat sifatida, ortiqcha daromad sifatida qayd etiladi (M11).

### Davlat tizimlari bog'liqligi
Markirovkalangan tovar inventarizatsiyasida kodlar soni CRPT tizimidagi holat bilan mos kelishi talab qilinishi mumkin — rasmiy tasdiq topilmadi, **ochiq savol**.

### Offline xatti-harakati
Mobil skanerlash (Android POS) offline ishlashi kerak (ombor sharoitida internet barqaror bo'lmasligi mumkin), natija keyin sinxronlanadi; lekin yakuniy tasdiqlash online rejimda amalga oshiriladi.

### Chekka holatlar
- Inventarizatsiya paytida savdo davom etishi — tovar bloklanishi (lock) yoki parallel hisoblash kerak.
- Partiyali/seriyali tovarlarni sanash murakkabroq.

---

## M06 — Ko'chirish

**Maqsad**: omborlar/filiallar orasida tovarni nazorat ostida ko'chirish.

### Foydalanuvchi hikoyalari

**US-M06-01**: Omborchi sifatida boshqa do'kon/omborga tovar yuborish hujjatini yaratishni istayman.
- Given tovar boshqa filialga kerak, When Omborchi ko'chirish hujjatini yaratadi (tovar, miqdor, manzil), Then yuboruvchi ombor balansi "yo'lda" holatiga o'tadi.

**US-M06-02**: Qabul qiluvchi Omborchi sifatida kelgan tovarni tasdiqlab qabul qilishni istayman.
- Given tovar manzilga yetib keldi, When qabul qiluvchi tomon miqdorni tasdiqlaydi, Then qabul qiluvchi ombor balansi oshadi, yuboruvchi ombordan "yo'lda" holati yopiladi.

**US-M06-03**: Menejer sifatida ko'chirishlar tarixini va bajarilish vaqtini ko'rishni istayman.
- Given tanlangan davr, When Menejer ro'yxatni ochadi, Then barcha ko'chirishlar holati (yo'lda/yetib kelgan/kechikkan) ko'rsatiladi.

### Davlat tizimlari bog'liqligi
Asl belgisi: markirovkalangan tovarni bir joydan ikkinchisiga ko'chirish muddati **72 soatdan oshmasligi** kerak (23-son qaror, 2026-01-23 — `research_notes/texnik/02-kassa-ofd-markirovka.md`, 106-qator); tizim bu muddatni kuzatib, yaqinlashganda ogohlantirishi kerak. *Eslatma: offline ko'chirishga ruxsat — mahsulot qarori (2026-10-15), yuridik tasdiq (huquqshunos bilan) tavsiya etiladi, lekin spec darajasidagi qaror allaqachon qabul qilingan.*

### Offline xatti-harakati
Qabul qiluvchi tomonda internet yo'q bo'lsa, qabul mahalliy qayd etilib keyin sinxronlanadi. *(2026-10-15: foydalanuvchi qarori)* **Markirovkalangan tovarni o'z filiallar/omborlar orasida ko'chirish offline rejimda ruxsat etiladi** (jo'natish ham, qabul ham) — hujjat mahalliy append-only jurnalga yoziladi, internet qaytganda Asl belgisi tizimiga sinxronlanadi, barcha amal audit bilan qayd etiladi; sabab — ichki ko'chirishda tovar egasi (yuridik shaxs) o'zgarmaydi, 72 soatlik qoida asosan subyektlar o'rtasidagi (tashqi) ko'chirishga tegishli ko'rinadi (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #5). 72 soatlik muddat hisoblagichi offline davrni ham hisobga oladi.

### Chekka holatlar
- Yo'lda tovar yo'qolishi/buzilishi — qisman qabul qilish imkoniyati kerak.
- 72 soatlik muddat buzilgani aniqlansa, huquqiy xavf haqida ogohlantirish (M12 hisobotida ham ko'rinishi kerak).

---

## M07 — Xarid

**Maqsad**: yetkazib beruvchidan tovar qabul qilish va hisob-kitobni yuritish.

### Foydalanuvchi hikoyalari

**US-M07-01**: Menejer/Omborchi sifatida yetkazib beruvchiga xaridnoma yaratishni istayman.
- Given kam qolgan tovarlar aniqlangan (M04), When Menejer xaridnoma yaratadi (yetkazib beruvchi, tovar, miqdor, narx), Then hujjat "yuborilgan" holatga o'tadi.

**US-M07-02**: Omborchi sifatida kelgan tovarni xaridnoma bilan solishtirib qabul qilishni istayman.
- Given tovar yetib keldi, When Omborchi haqiqiy miqdorni kiritib tasdiqlaydi, Then farq (kam/ko'p) belgilanadi va ombor balansi (M04) yangilanadi.

**US-M07-03**: Buxgalter sifatida yetkazib beruvchining e-fakturasini tizimga kiritib, QQS kreditini hisoblashni istayman.
- *(2026-10-15: foydalanuvchi qarori)* **E-faktura operatori — MVP'da faqat Faktura.uz**; Didox — MVP'dan keyingi birinchi integratsiya (sabab: Faktura.uz API hujjati ochiq va tekshirilgan, REGOS ham uni ishlatadi; Didox hujjati login ortida, faqat norasmiy SDK bor — `spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #4). Faktura.uz token `grant_type=password` bilan olinadi — tenant Faktura.uz login/parolini xavfsiz saqlash (`tenant_secrets`) kerak.
- Given e-faktura Faktura.uz orqali keldi yoki qo'lda kiritildi, When Buxgalter uni E-IMZO bilan tasdiqlaydi, Then faktura summasi va QQS buxgalteriya yozuviga (M11) va QQS hisobiga (M10) qo'shiladi.
- Given faktura AI xavf-baholash tizimida "yuqori xavfli" (qizil) deb belgilangan, When Buxgalter buni ko'radi, Then tizim QQS krediti to'lovdan keyin kreditlanishi haqida ogohlantiradi (`research_notes/texnik/03-efaktura-va-tolov.md`, 1.2-bo'lim).

**US-M07-04**: Buxgalter sifatida yetkazib beruvchiga bo'lgan kreditorlik qarzini to'lashni va buni tizimda qayd etishni istayman.
- Given yetkazib beruvchi fakturasi tasdiqlangan (M07, M11), When Buxgalter to'lovni (bank/naqd) amalga oshiradi, Then kreditorlik balansi shu summaga kamayadi.
- Given faktura "qizil" (yuqori xavfli) deb belgilangan, When to'lov amalga oshadi, Then shundan keyingina QQS krediti kreditlanishi tizimda aks etadi (US-M10-03 bilan bog'liq, `research_notes/texnik/03-efaktura-va-tolov.md`, 1.2-bo'lim).

**US-M07-05** *(2026-10-14: tekshiruv)*: Omborchi/Menejer sifatida muddati o'tgan, buzilgan yoki ortiqcha tovarni yetkazib beruvchiga qaytarishni istayman.
- Given tovar shu yetkazib beruvchidan kirim qilingan (US-M07-02), When Omborchi "Yetkazib beruvchiga qaytarish" hujjatini yaratadi (yetkazib beruvchi, asl kirim hujjati, tovar, miqdor, sabab), Then ombor qoldig'i (M04) kamayadi va yetkazib beruvchiga qarzimiz (US-M08-11) shu summaga kamayadi; qarz bo'lmasa — yetkazib beruvchi bizga qarzdor bo'ladi yoki pulni naqd/bank orqali qaytaradi.
- Given asl kirim QQS bilan bo'lgan, When qaytarish o'tkaziladi, Then kiritiladigan QQS (M10) shu qism bo'yicha kamayadi; yetkazib beruvchidan tuzatuvchi e-faktura talab qilinishi — **ochiq savol**.
- Given tovar markirovkalangan, When qaytariladi, Then Asl belgisi tizimidagi mos operatsiya — **ochiq savol** (M02 bilan bir xil).

### Davlat tizimlari bog'liqligi
E-faktura (*(2026-10-15: foydalanuvchi qarori)* **Faktura.uz — MVP'da yagona operator**, ochiq API; Didox — MVP'dan keyin, login talab qiladigan API), e-TTN (agar tashish bo'lsa), MXIK kod tekshiruvi, E-IMZO (imzolash), AI xavf-baholash (VM Qarori №830, 2025-12-26, 2026-01-01 dan to'liq — `research_notes/texnik/03-efaktura-va-tolov.md`, 32-qator). Yetkazib beruvchi vakili ishonchnoma bilan tovar topshirsa, 2026-01-01'dan Vakolat.uz orqali e-ishonchnomani tekshirish zarurligi **ochiq savol** (`research_notes/texnik/09-soliq-integratsiyasi.md`, 14-qator).

### Offline xatti-harakati
Majburiy emas — xarid odatda ofis/ombor sharoitida internet mavjud joyda amalga oshiriladi; agar offline bo'lsa, qabul hujjati mahalliy saqlanib keyin sinxronlanadi.

### Chekka holatlar
- Qisman yetkazib berish (buyurtma qilingan miqdordan kam/ko'p kelishi).
- Narx farqi (xaridnomadagi narx bilan fakturadagi narx mos kelmasligi).
- Markirovkalangan tovar xaridida CRPT kod tekshiruvi (rasmiy API yopiq — ochiq savol).
- *(2026-10-14: tekshiruv)* Yetkazib beruvchi bonus tovari (masalan "10 + 1 tekin") — kirim qatori **0 narx** bilan alohida partiya sifatida yoziladi; AVECO o'rtacha narxi shunga mos pasayadi.

---

## M08 — Nasiya (mijoz qarzi)

**Maqsad**: mijozga nazoratli tarzda qarzga sotish, limit va eslatmalarni boshqarish.

### Foydalanuvchi hikoyalari

**US-M08-01**: Kassir sifatida mijozga belgilangan limit ichida nasiyaga sotishni istayman.
- Given mijoz tanlangan, When kassir "nasiya" to'lov turini tanlaydi, Then tizim mijozning joriy qarzi + yangi summa kredit limitidan oshmasligini tekshiradi.
- Given limit yetarli, When kassir yakunlaydi, Then mijoz qarz balansi (M08) oshadi va chek shunga mos belgi bilan chiqadi.
- Given limit yetarli emas, When kassir yakunlashga harakat qiladi, Then operatsiya rad etiladi yoki Menejer tasdig'i so'raladi (online rejim). *(2026-10-15: foydalanuvchi qarori)* Given offline rejim va oxirgi ma'lum qoldiq bo'yicha limitdan oshib ketish aniqlansa, When kassir shunga qaramay sotishni tanlaydi, Then sotuv **bloklanmaydi** — qarz yoziladi, bayroq qo'yiladi, internet qaytganda Egasiga xabar boradi (M08 Offline xatti-harakati bo'limiga qarang).

**US-M08-02**: Menejer sifatida mijoz kredit limitini belgilash/o'zgartirishni istayman.
- Given mijoz tanlangan, When Menejer limitni kiritadi/o'zgartiradi, Then yangi limit darhol kuchga kiradi va barcha kassalarga sinxronlanadi.

**US-M08-03**: Egasi/Menejer sifatida muddati o'tgan qarzlar bo'yicha avtomatik eslatma matnini olishni istayman.
- Given mijoz qarzi to'lov muddatidan o'tgan, When tizim kunlik tekshiradi, Then AI yordamida tayyorlangan eslatma matni (o'zbek tilida) taklif qilinadi (AI funksiyalar bilan bog'liq, `05-ai-funksiyalar.md`).

**US-M08-04**: Kassir/Buxgalter sifatida mijozning nasiya qarzini keyinroq (qisman yoki to'liq) to'lashini qabul qilishni istayman.
- Given mijoz oldingi nasiya qarziga ega, When mijoz naqd/karta/QR orqali to'lov qiladi, Then qarz balansi (M08) shu summaga kamaytiriladi; qisman to'lovda qoldiq qarz saqlanadi.
- *Ochiq savol: qarz to'lovi uchun alohida fiskal chek chiqarilishi kerakligi (OFD talabi) aniq manbada tasdiqlanmagan — asl sotuv chekida QQS allaqachon hisoblangan, to'lov o'zi yangi soliqqa tortiladigan operatsiya emas, lekin bu MVP'dan oldin OFD/soliq.uz bilan aniqlashtirilishi tavsiya etiladi.*

**Qarz daftari (2026-10-14: qo'shildi — foydalanuvchi qarori: kichik do'konlarda qarzga berish odatiy, qog'oz "qarz daftari" to'liq raqamli bo'lishi kerak).** Quyidagilar US-M08-01…04 ni to'ldiradi; kichik do'konda Menejer yo'q bo'lishi mumkin, shuning uchun limit **ixtiyoriy**.

**US-M08-05**: Kassir/Egasi sifatida qarzga berishni 2–3 soniyada, xuddi daftarga yozgandek qilishni istayman.
- Given POS ekranida "Qarzga" tugmasi, When kassir mijozni ism yoki telefon bo'yicha qidiradi (yoki faqat **ism + telefon** bilan yangisini yaratadi), Then sotuv mijoz qarziga yoziladi; limit belgilanmagan bo'lsa tekshiruv o'tkazilmaydi.
- Ixtiyoriy izoh ("o'g'li olib ketdi", "oylikdan keyin beradi") va va'da qilingan to'lov sanasi kiritiladi.
- Internet yo'q bo'lsa ham to'liq ishlaydi (POS lokal bazasida), sinxronlanganda serverga tushadi.

**US-M08-06**: Egasi/Kassir sifatida har bir mijozning qarz daftarini qog'oz daftardek ko'rishni istayman.
- Given mijoz tanlangan, When "Qarz daftari" ochiladi, Then sana bo'yicha ro'yxat: har bir qarz (summa, **qaysi tovarlar olingan**, kim berdi, izoh), har bir to'lov va joriy qoldiq ko'rinadi; POS'da ham (tezkor ko'rish), back-office'da ham (BO-06).
- *(2026-10-14: tekshiruv)* Har bir qarz qatorida holat: ochiq / qisman yopilgan (qolgan summa) / to'liq yopilgan — qisman to'lov qaysi qarz(lar)ni yopgani `debt_payments.allocations` bo'yicha (eng eski qarzdan, US-M08-09) ko'rsatiladi.

**US-M08-07**: Egasi sifatida eski qog'oz daftardagi qarzlarni tizimga tez ko'chirishni istayman.
- Given yangi do'kon, When Egasi "Boshlang'ich qarzlar" ekranini ochadi, Then har bir mijoz uchun ism, telefon, qarz summasi va (ixtiyoriy) sana qatorma-qator yoki Excel shablon orqali kiritiladi; bu qarzlar "boshlang'ich qoldiq" deb belgilanadi (tovar tarkibisiz, chek chiqarilmaydi).
- Qo'lyozma daftar fotosidan o'qish (AI-04) — keyingi bosqich (`05-ai-funksiyalar.md`).

**US-M08-08**: Mijoz sifatida qancha qarzim borligini bilishni istayman (nizolarning oldini olish).
- Given mijozning telefoni bor va u rozilik bergan, When qarz yoki to'lov yoziladi, Then mijozga SMS/Telegram xabar ketadi: "Bugun 45 000 so'm qarz yozildi. Jami qarzingiz: 230 000 so'm. — [Do'kon nomi]" (sozlamada o'chirish mumkin).
- Mijoz Telegram havola orqali o'z qarz tarixini (faqat o'zinikini) ko'ra oladi.

**US-M08-09**: Egasi sifatida qarzlarni o'z vaqtida qaytarib olishni istayman.
- Given va'da sanasi keldi yoki o'tdi, When kunlik tekshiruv ishlaydi, Then Egasiga ro'yxat ("bugun to'lashi kerak: 5 kishi, 640 000 so'm") va mijozga eslatma yuborish taklifi chiqadi (matnni AI-06 yozadi yoki standart shablon; yuborishni odam tasdiqlaydi).
- To'lov qabul qilinganda summa **eng eski qarzdan boshlab** yopiladi (qisman to'lov qoldig'i saqlanadi).

**US-M08-10**: Egasi sifatida qarzlar holatini bir qarashda ko'rishni istayman.
- Given qarzdorlar bor, When hisobot ochiladi, Then: jami qarz, qarzdorlar soni, muddat bo'yicha guruhlar (0–30 / 31–60 / 60+ kun), eng katta qarzdorlar, bu oy berilgan va qaytgan qarz.
- *(2026-10-15: foydalanuvchi qarori)* **60 kunlik "eski qarzlar" eslatmasi**: qarz yaratilgan/oxirgi to'lovdan **60 kundan ortiq** o'tgan va hali yopilmagan qarzlar alohida ro'yxat sifatida Egasiga eslatma (M18) bilan ko'rsatiladi — bu faqat **eslatma**, tizim o'zi "shubhali qarz" deb avtomatik belgilamaydi.
- Qarzni kechib yuborish yoki "undirib bo'lmaydigan" (shubhali) deb yopish — **faqat Egasi, sabab bilan**, audit jurnaliga yoziladi; 60 kunlik ro'yxat (yuqorida) faqat shuni ko'rib chiqishni eslatadi, o'zi avtomatik harakat qilmaydi (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #9).

**US-M08-11**: Egasi sifatida **o'zim yetkazib beruvchilarga** qarzimni ham daftar kabi yuritishni istayman (mol qarzga olinadi).
- Given xarid nasiyaga qabul qilingan (M07), When yetkazib beruvchi tanlanadi, Then "Men qarzdorman" daftari: kimga, qancha, qachon to'lash kerak; to'lov BP-12 orqali yopiladi; to'lov sanasi yaqinlashganda eslatma.

**Qoidalar:**
- Qarzga **foiz qo'shilmaydi** (MVP'da bunday funksiya yo'q).
- Qarzli sotuv ham oddiy sotuv kabi fiskal chek bilan rasmiylashtiriladi (to'lov turi: nasiya, BP-03); "boshlang'ich qarz" (US-M08-07) bundan mustasno — u yangi sotuv emas.
- Mijoz telefon raqami shaxsiy ma'lumot: SMS/Telegram faqat mijoz roziligi bilan.

### Davlat tizimlari bog'liqligi
To'g'ridan-to'g'ri davlat talabi aniqlanmadi; QQS'ni hisobga olish vaqti (sotuv vaqti yoki to'lov vaqti) aniq emas — **ochiq savol**.

### Offline xatti-harakati
Offline rejimda nasiya yaratish mumkin, lekin limit tekshiruvi faqat oxirgi sinxronlashgan ma'lumot asosida bo'ladi — bir mijozga bir nechta kassada parallel nasiya berilsa, limitdan oshib ketish xavfi bor (**ochiq savol**, pastda). *(2026-10-15: foydalanuvchi qarori)* **Offline'da limitdan oshgan nasiya**: qurilma oxirgi ma'lum qoldiq bo'yicha ogohlantiradi, lekin kassir baribir sotishni tanlasa — sotuv **bekor qilinmaydi**, qarz limitdan oshgan holicha yoziladi, operatsiyaga **bayroq** qo'yiladi va internet qaytganda Egasiga xabar (M18) boradi; sabab — sotuv va fiskal chek allaqachon amalga oshgan, uni orqaga qaytarish buxgalteriyani buzadi, nazorat xabar/audit orqali amalga oshadi (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #7).

### Chekka holatlar
- Bir nechta kassa bir vaqtda bitta mijozga nasiya berishi (offline sinxronlash konflikti).
- Qarzni qisman to'lash va qoldiq balansni qayta hisoblash.
- Mijoz butunlay to'lamay qolganda qarzni "shubhali qarz" sifatida belgilash (M11 bilan bog'liq).

---

## M09 — Narxlar

**Maqsad**: chakana narxlarni, kategoriyalarni va narx tarixini boshqarish. *(2026-10-15: foydalanuvchi qarori)* **Alohida optom narx jadvali MVP'da yo'q** — ulgurji/doimiy mijozlar uchun o'rniga mijoz kartasida (M08/counterparty) "doimiy chegirma %" maydoni ishlatiladi (pastga qarang va M03 chekka holatlar).

### Foydalanuvchi hikoyalari

**US-M09-01**: Menejer sifatida tovar narxini yangilashni, eski narx tarixda saqlanishini istayman.
- Given tovar tanlangan, When Menejer yangi narxni kiritadi, Then eski narx "tarix" yozuviga ko'chadi, yangi narx amal qilish sanasi bilan saqlanadi.

**US-M09-02**: Egasi sifatida katta (masalan belgilangan foizdan yuqori) narx o'zgarishini tasdiqlashni istayman.
- Given narx o'zgarishi limitdan katta (limit — taxmin), When Menejer narxni kiritadi, Then o'zgarish Egasi tasdiqlamaguncha kuchga kirmaydi; *(2026-10-14: tekshiruv)* o'zgarish `pending_approval` holatida BO-16 navbatiga tushadi, rad etilsa sabab yoziladi.

**US-M09-03**: Kassir sifatida kassada joriy (amaldagi) narxni ko'rishni istayman, lekin o'zgartira olmasligim kerak.
- Given kassa ekrani ochiq, When tovar tanlanadi, Then joriy narx ko'rsatiladi, tahrirlash tugmasi yo'q/faol emas.

**US-M09-04** *(2026-10-14: qo'shildi)*: Menejer sifatida narxi o'zgargan tovarlarning javon yorliqlarini qayta chop etishni istayman.
- Given bir yoki bir nechta tovar narxi o'zgardi, When Menejer "Yorliqlar" bo'limini ochadi, Then narxi o'zgargan, lekin yorlig'i hali chop etilmagan tovarlar ro'yxati chiqadi; tanlab chop etiladi, chop etilganlar belgilanadi.
- Yorliq shabloni: tovar nomi, narx, (ixtiyoriy) eski narx, o'lchov birligi, shtrix-kod. Bir nechta o'lcham (masalan 58×40 mm); yorliq printeri protokoli — **ochiq savol** (`research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`, 3-bo'lim).

**US-M09-05** *(2026-10-14: qo'shildi)*: Menejer sifatida shtrix-kodi yo'q tovarga ichki shtrix-kod berishni istayman.
- Given tovar shtrix-kodsiz, When "Ichki shtrix-kod yaratish" bosiladi, Then tenant ichida noyob kod yaratiladi va yorliqda chop etiladi; kod ishlab chiqaruvchi kodlari bilan to'qnashmaydigan diapazonda bo'ladi (aniq diapazon — arxitektura qarori).

**US-M09-06** *(2026-10-14: qo'shildi)*: Kassir sifatida tarozida tortilgan tovarni (go'sht, meva) bitta skanerlash bilan sotishni istayman.
- Given yorliq chiqaradigan tarozi og'irlik kiritilgan shtrix-kod chop etgan, When kassir uni skanerlaydi, Then POS koddan tovar va og'irlikni ajratib chekka qo'shadi. Kod formati — keng tarqalgan EAN-13 "2x" prefiksli og'irlik kodi: **taxmin**, real tarozi modellarida tekshiriladi.
- Given yorliqli tarozi yo'q, When tovar tanlanadi, Then og'irlik qo'lda kiritiladi (mavjud zahira yo'l, `04-ekranlar-va-ux.md`, 1.6).

**US-M09-07** *(2026-10-15: foydalanuvchi qarori — qo'shildi)*: Menejer sifatida doimiy/ulgurji mijozga standart chegirma foizini mijoz kartasida belgilashni istayman.
- Given mijoz kartasi (M08/counterparty) ochilgan, When Menejer "doimiy chegirma %" maydoniga qiymat kiritadi, Then shu mijoz bilan qilingan har bir sotuvda bu chegirma avtomatik qo'llanadi.
- Given bir chekda doimiy chegirma va boshqa chegirma (kassir/aksiya) manbai to'qnashsa, Then **faqat bittasi — mijozga eng katta foyda beradigani** qo'llaniladi, ikkisi yig'ilmaydi (M03 chekka holatlar bilan bir xil qoida, `spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #8).

### Davlat tizimlari bog'liqligi
Narx QQS stavkasi (12%, 0%, ixtiyoriy 6%) bilan bog'liq — har bir tovar MXIK kodiga mos QQS toifasiga ega bo'lishi kerak (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`, "QQS" bandi).

### Offline xatti-harakati
Narxlar POS'ga oldindan sinxronlanadi (lokal keshda saqlanadi); offline paytida oxirgi sinxronlangan narx ishlatiladi — markazda narx o'zgargan bo'lsa, internet qaytguncha POS eski narxda sotishi mumkin (**chekka holat**).

### Chekka holatlar
- *(2026-10-15: hal qilindi — foydalanuvchi qarori)* ~~Optom va chakana narx bir vaqtda qo'llanilishi (mijoz turi/miqdorga bog'liq)~~ — endi aniq: alohida optom narx yo'q, faqat mijoz kartasidagi doimiy chegirma % (US-M09-07), eng foydali chegirma qoidasi bilan.
- Vaqtinchalik aksiya narxi muddati tugagandan keyin asl narxga avtomatik qaytishi.
- Offline POS'dagi eskirgan narx bilan sotilgan cheklarni keyin tuzatish kerak bo'lmasligi (narx chek yaratilish vaqtida "qotiriladi").
- *(2026-10-14: tekshiruv)* Onlayn ochiq chek davomida narx o'zgarsa — chekka allaqachon qo'shilgan qator narxi qo'shilgan paytdagidek qoladi, keyin qo'shilgan qator yangi narxni oladi (offline'dagi "qotirish" qoidasi bilan bir xil).

---

## M10 — QQS

**Maqsad**: QQS'ni to'g'ri hisoblash va 2026-yildan davlat tuzgan hisobotni ichki hisob bilan solishtirish.

### Foydalanuvchi hikoyalari

**US-M10-01**: Buxgalter sifatida har bir sotuvdan QQS avtomatik hisoblanishini istayman.
- Given tovar MXIK kodiga mos QQS toifasi (12% standart, 0% imtiyozli, 6% ixtiyoriy) belgilangan, When sotuv amalga oshadi, Then QQS summasi avtomatik hisoblanib chekka va buxgalteriya yozuviga kiritiladi (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`, "QQS" bandi — 12% standart stavka, Soliq kodeksi 258-modda).

**US-M10-02**: Buxgalter sifatida 2026-01-01'dan davlat tuzgan QQS hisobotini ichki hisob bilan **5 kalendar kun** ichida solishtirishni istayman *(2026-10-14: tuzatildi — to'liq qayta yozildi, quyida yechim)*.

**Huquqiy asos** *(2026-10-14: tuzatildi — endi birlamchi manba bilan)*: Soliq kodeksining 81-moddasi (O'RQ-1108-son Qonun, 2025-12-25, 2026-01-01 dan kuchda — [lex.uz/docs/-7944527](https://lex.uz/docs/-7944527)). Davlat (soliq organlari) QQS, aylanma solig'i, mol-mulk solig'i, yer solig'i, JShDS va ijtimoiy soliq hisobotlarini o'zida bor ma'lumot + shaxsiy kabinetning interaktiv xizmatiga soliq to'lovchi kiritgan ma'lumot asosida elektron shaklda shakllantiradi. **Foyda solig'i bu ro'yxatga kirmaydi.** Agar davlat shakllantirgan ma'lumot korxona hisobidan farq qilsa, korxona **besh kun ichida** (kalendar kun, lekin hisobotni topshirish muddatidan kechiktirmay) tuzatish kiritadi; tuzatilmasa — davlat shakllantirgan ko'rinishda topshirilgan hisoblanadi.

**Qamrov** (MVP): faqat **QQS va aylanma solig'i** — bu ikkisi uchun AIOS'da to'liq ichki ma'lumot bor (M01, M07, M09, M10, M11 dan). Mol-mulk, yer, JShDS va ijtimoiy soliq — davlat ularni ham o'zi tuzadi, lekin AIOS'da ichki solishtirish uchun kerakli ma'lumot (asosiy vositalar hisobi, kadrlar/ish haqi) MVP modullari qatorida yo'q, shuning uchun bu to'rttasi MVP'da faqat "davlat ko'rsatgan raqam" sifatida ko'rsatiladi, ichki solishtirish qilinmaydi (keyingi bosqich). Foyda solig'i — davlat o'zi tuzmaydi, AIOS'da ham alohida modul yo'q, MVP'dan tashqarida, korxonaning o'zi tayyorlaydigan hisobot sifatida qoladi.

**Holat mashinasi**: `kutilmoqda` (davlat hisoboti hali e'lon qilinmagan) → davlat hisoboti e'lon qilinishi bilan avtomatik solishtirish ishga tushadi → `mos keladi` (farq yo'q) YOKI `farq topildi` (tolerance'dan tashqari farq) → Buxgalter farqni ko'rib chiqadi → `tuzatish yuborildi` (Buxgalter E-IMZO bilan tuzatish yuborgan) YOKI `avtomatik qabul qilingan` (5 kalendar kun ichida javob berilmagan).

- Given my.soliq.uz'da davlat tomonidan tuzilgan QQS/aylanma hisoboti e'lon qilingan (qo'lda yuklab olinadi, rasmiy API yo'q — `00-xulosa-va-ochiq-savollar.md`, 86-qator), When Buxgalter uni tizimga kiritadi, Then tizim ichki hisoblangan summa bilan avtomatik solishtiradi va **5 kalendar kunlik hisoblagich davlat hisoboti e'lon qilingan kundan boshlab, lekin shu soliq turi uchun qonundagi hisobot topshirish muddatidan oshmaydigan tarzda** ishga tushadi.
- Given farq (belgilangan tolerance'dan tashqarida — tolerance qiymati taxmin) topilgan, Then tizim holatni `farq topildi`ga o'tkazadi va **1-, 3- va 4-kun**larda Buxgalter va Egasiga ogohlantirish yuboradi (kunlar — mahsulot qarori, manbada aniq raqam yo'q, **taxmin**; maqsad — muddat tugashidan oldin kamida uch marta eslatish).
- Given Buxgalter 5 kalendar kun ichida farqni tekshirib tasdiqlagan yoki e'tiroz/tuzatish yuborgan, When bu amalga oshadi, Then holat `tuzatish yuborildi`ga o'tadi va natija Egasiga yakuniy ko'rsatish uchun yuboriladi. Given 5 kalendar kun ichida hech qanday javob berilmagan, When muddat tugaydi, Then holat **`avtomatik qabul qilingan`**ga o'tadi (Soliq kodeksi 81-moddasi).
- *Eslatma: tuzatishni qayerga/qanday yuborish kerakligi (alohida ariza? my.soliq.uz shaxsiy kabinetida to'g'ridan-to'g'ri tuzatish?) ushbu tadqiqotda lex.uz'dan to'liq protsedura darajasida topilmadi — bu hali **ochiq savol** (pastda), lekin muddat va huquqiy asos endi aniq.*

**US-M10-03**: Buxgalter sifatida yuqori xavfli (AI risk-scoring "qizil") fakturalarning QQS kreditiga ta'sirini kuzatishni istayman.
- Given faktura "qizil" deb belgilangan (M07), When Buxgalter QQS hisobotini tayyorlaydi, Then bu fakturalar alohida ko'rsatiladi va ularning krediti hali tasdiqlanmagani belgilanadi (VM Qarori №830, 2025-12-26, 6- va 8-moddalar — `research_notes/texnik/03-efaktura-va-tolov.md`, 1.2-bo'lim).

**US-M10-04**: Buxgalter sifatida QQS to'lamaydigan, aylanma solig'i rejimidagi biznes uchun ham davlat tuzgan aylanma solig'i hisobotini ichki hisob bilan solishtirishni istayman.
- Given biznes aylanma solig'i to'lovchisi (QQS emas), When davlat 2026-01-01'dan aylanma solig'i hisobotini ham o'zi tuzadi (Soliq kodeksi 81-moddasi, O'RQ-1108 *(2026-10-14: tuzatildi)*), Then tizim xuddi QQS kabi ichki hisob bilan solishtirish jarayonini (US-M10-02 bilan bir xil mantiq, 5 kalendar kun) qo'llaydi.
- *(2026-10-14: tekshiruv)* Given tenant aylanma solig'i to'lovchisi (Soliq kodeksi 461-modda: jami daromad 1 mlrd so'mgacha), When oy yakunida ichki aylanma solig'i hisoblanadi, Then stavka 467-modda bo'yicha aniqlanadi: YTT/o'zini o'zi band qilgan — 1%; yuridik shaxs chakana savdosi — filialning "aholi punkti toifasi" bo'yicha 4% / 2% / 1% (tamaki savdosi aylanmasi har doim 4%, MXIK guruhi bo'yicha ajratiladi); boshqa faoliyat — 4%; summa filial va stavka bo'yicha alohida ko'rsatiladi.

*Qamrov chegarasi: MVP faqat **QQS va aylanma solig'i** hisobotlarini solishtiradi. Mol-mulk, yer, JShDS va ijtimoiy soliq hisobotlari ham 2026-01-01'dan davlat tomonidan avtomatik tuziladi, lekin bular MVP'dan **tashqarida** qoladi — sabab: JShDS/ijtimoiy soliq xodim/ish haqi hisobini, mol-mulk solig'i esa asosiy vositalar hisobini talab qiladi, ikkisi ham MVP 18 moduliga kiritilmagan (`spec/README.md`).*

### Davlat tizimlari bog'liqligi
my.soliq.uz (davlat hisoboti), e-faktura/EDO (QQS bazasi manbai — *(2026-10-15: foydalanuvchi qarori)* MVP'da Faktura.uz, Didox keyinroq), VM Qarori №830 (2025-12-26, AI xavf-baholash), Soliq kodeksi 81-moddasi/O'RQ-1108 (davlat hisobot shakllantirish va 5 kalendar kunlik tuzatish huquqi — lex.uz/docs/-7944527). Rasmiy dasturiy o'qish API'si **topilmadi** — bu modul MVP'da qo'lda/yarim-avtomatik ishlaydi (taxmin/ochiq savol). *(2026-10-14: tekshiruv)* Aylanma solig'i stavkalari — Soliq kodeksi 467-moddasi (O'RQ-1108 tahririda, 2026-01-01'dan), to'lovchilar va 1 mlrd so'm chegarasi — 461-modda ([lex.uz/docs/4674902](https://lex.uz/docs/4674902)).

### Offline xatti-harakati
Deklaratsiya/solishtirish jarayoni online tizim (my.soliq.uz) talab qiladi, shuning uchun offline ishlamaydi; faqat ichki QQS hisob-kitobi (sotuvlardan) offline tayyorlanib, online bo'lganda solishtiriladi.

### Chekka holatlar
- Davlat hisoboti kutilgandan kech e'lon qilinishi — 5 kalendar kunlik hisoblagich boshlanish sanasi noaniq bo'lib qolishi mumkin; lekin qonunga ko'ra hisoblagich hisobotni topshirish muddatidan oshmasligi kerak, shu sabab tizim ikkala chegarani (e'lon+5 kun, va qonuniy topshirish muddati) hisoblab, qaysi biri birinchi kelsa shuni qo'llashi kerak.
- Farq juda katta bo'lsa (masalan tizim xatosi natijasida) — eskalatsiya jarayoni kerak.
- Qaytarish (M02) va chegirma (M03) QQS bazasini orqaga qarab tuzatishi.

---

## M11 — Buxgalteriya

**Maqsad**: savdo/ombor operatsiyalaridan NSBU №21 (2024/2025) asosidagi buxgalteriya yozuvlarini avtomatik generatsiya qilish.

### Foydalanuvchi hikoyalari

**US-M11-01**: Buxgalter sifatida har bir sotuv/xariddan avtomatik provodka olishni istayman.
- Given sotuv yakunlangan (M01), When tizim buxgalteriya modulini ishga tushiradi, Then tegishli hisob toifalari (kassa, hisob-kitob, tovar-moddiy zaxira, QQS, daromad/xarajat) bo'yicha ikki tomonlama yozuv avtomatik yaratiladi. *Eslatma: aniq hisob raqamlari (masalan eski "5000"/"1000" guruhlari) 2002-yilgi, 2025-01-01'dan amal qilmaydigan **eski** NSBU rejasidan edi; yangi NSBU №21 (2024/2025) ning to'liq hisob jadvali bu tadqiqotda topilmagan, shuning uchun bu yerda aniq hisob raqami **keltirilmaydi** — faqat hisob toifasi nomi ko'rsatiladi (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`, 3.4-bo'lim va ochiq savol).*

**US-M11-02**: Buxgalter sifatida oy yakunida balans va daromad-xarajat hisobotini olishni istayman.
- Given oy yakunlangan, When Buxgalter "oy yopish"ni boshlaydi, Then barcha provodkalar yig'ilib balans va foyda-zarar hisoboti shakllanadi.
- *(2026-10-15: foydalanuvchi qarori)* **Yopilgan oy qayta ochilmaydi**: MVP'da yopilgan davr (oy) hech qanday rolga (shu jumladan Buxgalter/Egasiga) qayta ochilmaydi; shu davrga tegishli xato aniqlansa, tuzatish **joriy ochiq oyda tuzatuvchi hujjat** (storno/qo'shimcha yozuv) bilan kiritiladi, asl yopilgan davr o'zgarmaydi (append-only). Sabab: hozircha O'zbekistonda oldingi davr xatolarini tuzatish bo'yicha alohida standart yo'q (NSFO №2 faqat 2027-01-01'dan kuchga kiradi), shuning uchun eng xavfsiz yondashuv — xalqaro tizimlardagi "lock date" tamoyili. Keyinroq (buxgalter roziligi bilan) Odoo uslubidagi "faqat Buxgalter, sabab va muddat bilan, audit yozuvli" istisno qo'shilishi mumkin — MVP'da yo'q (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #15).

**US-M11-03**: Egasi sifatida asosiy moliyaviy ko'rsatkichlarni (foyda, aylanma) sodda ko'rinishda ko'rishni istayman.
- Given tanlangan davr, When Egasi dashboard'ni ochadi, Then aylanma, xarajat, sof foyda asosiy raqamlar sifatida ko'rsatiladi (texnik tafsilotsiz).

### Davlat tizimlari bog'liqligi
NSBU №21 (2024/2025, 191-son buyruq) hisob rejasi — eski 2002-yilgi reja **emas** (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`, 3.4-bo'lim).

### Offline xatti-harakati
Markazlashtirilgan serverda ishlaydi, offline kiritilmaydi; faqat sotuv/xarid ma'lumotlari kelib tushgandan keyin provodka yaratiladi.

### Chekka holatlar
- Avtomatik provodkada xato aniqlansa, qo'lda tuzatish imkoniyati (audit-trail bilan) kerak — yopilgan oyda esa faqat joriy ochiq oyda tuzatuvchi yozuv orqali (yuqoridagi US-M11-02).
- Ko'p filialli (M14) konsolidatsiyalangan balans.
- To'liq NSBU hisob rejasi (asosiy vositalar, ish haqi) MVP'dan tashqarida — faqat savdo/ombordan kelib chiqadigan asosiy hisoblar avtomatlashtiriladi (`spec/README.md`).

---

## M12 — Hisobotlar

**Maqsad**: savdo, ombor, buxgalteriya va QQS bo'yicha tushunarli hisobotlar berish.

### Foydalanuvchi hikoyalari

**US-M12-01**: Egasi sifatida kunlik savdo hisobotini (umumiy va filial bo'yicha) ko'rishni istayman.
- Given kun yakunlangan (yoki jarayonda), When Egasi hisobotni ochadi, Then jami savdo, chek soni, o'rtacha chek summasi filial bo'yicha ajratib ko'rsatiladi (M14 bilan bog'liq).

**US-M12-02**: Menejer sifatida eng ko'p/kam sotiladigan tovarlar hisobotini olishni istayman.
- Given tanlangan davr, When Menejer hisobotni so'raydi, Then tovarlar sotuv miqdori bo'yicha tartiblangan ro'yxat ko'rsatiladi.

**US-M12-03**: Buxgalter sifatida QQS va davlat solishtirish hisobotini eksport qilishni istayman.
- Given M10'dagi solishtirish yakunlangan, When Buxgalter "eksport" tugmasini bosadi, Then hisobot Excel/PDF formatda yuklab olinadi.

### Davlat tizimlari bog'liqligi
M10 bilan bog'liq hisobotlar davlat (my.soliq.uz) formatiga mos tarzda tayyorlanishi kerak — aniq format talabi **ochiq savol**.

### Offline xatti-harakati
Hisobotlar faqat online holatda to'liq va aniq; offline paytda faqat mahalliy keshdagi (sinxronlanmagan) ma'lumot bilan qisman ko'rsatiladi, bu holat foydalanuvchiga aniq bildiriladi.

### Chekka holatlar
- Katta hajmli ma'lumotni eksport qilishda vaqt/hajm chegarasi.
- Bir nechta filial turli vaqt zonasida bo'lmasa ham, smena vaqtlari mos kelmasligi hisobotni chalkashtirishi mumkin.

---

## M13 — Huquqlar

**Maqsad**: rol asosida foydalanuvchi huquqlarini (ko'rish/yaratish/tasdiqlash) boshqarish, kichik do'konda rol birlashuviga imkon berish; *(2026-10-15: foydalanuvchi qarori)* shu bilan birga — Egasi uchun xodim/foydalanuvchi va ularning sessiyalarini (kirgan qurilmalar) to'liq boshqarish paneli. Autentifikatsiya **o'z (mustaqil) OAuth 2.0 implementatsiyasi** asosida quriladi, hech qanday mock/soxta login yo'q — texnik arxitektura `spec/02-arxitektura/12-autentifikatsiya-oauth2.md`da (alohida jamoa tomonidan yoziladi).

### Foydalanuvchi hikoyalari

**US-M13-01**: Egasi sifatida yangi xodim qo'shib, unga bir yoki bir nechta rol (Kassir/Omborchi/Menejer/Buxgalter) belgilashni istayman.
- Given yangi xodim ma'lumoti kiritildi, When Egasi rol(lar)ni tanlaydi, Then xodim login huquqlari shu rol(lar)ga mos modul ruxsatlarini oladi (`01-rollar-va-ssenariylar.md`, 6-bo'lim, huquqlar matritsasi).

**US-M13-02**: Egasi sifatida kichik do'konda bitta xodimga bir nechta rolni birlashtirib berishni istayman.
- Given xodim bir vaqtning o'zida Kassir va Omborchi bo'lishi kerak, When Egasi ikkita rolni belgilaydi, Then xodim ikki rolning jamlangan huquqlariga ega bo'ladi.

**US-M13-03**: Menejer sifatida operatsiya chegaralarini (masalan chegirma/qaytarish limiti) rolga yoki shaxsga bog'lab sozlashni istayman.
- Given limit o'zgartirilishi kerak, When Menejer yangi limitni kiritadi, Then bu limit tegishli rol/xodim uchun darhol kuchga kiradi.

**US-M13-04** *(2026-10-15: foydalanuvchi qarori — qo'shildi; 2026-10-15: qabul-5 O10 bo'yicha tuzatildi — vaqtinchalik parol SMS'da ochiq yuborilmaydi)*: Egasi sifatida yangi xodimni admin panel orqali to'liq ma'lumoti bilan (telefon, ism, rol(lar), filial(lar)) qo'shishni istayman.
- Given "Foydalanuvchi qo'shish" ochildi, When Egasi telefon raqami, to'liq ism, rol(lar) va qaysi filial(lar)da ishlaydi (M14) kiritadi, Then xodim yaratiladi va unga SMS orqali bir martalik taklif kodi (OTP, `purpose=invite`) yuboriladi; xodim shu kod bilan o'zi parol va/yoki PIN o'rnatadi (parol/PIN hech qachon SMS'da ochiq matnda yuborilmaydi).
- Xodim faqat o'ziga tayinlangan filial(lar) ma'lumotini ko'radi/boshqaradi (boshqa filiallar yopiq).

**US-M13-05** *(2026-10-15: foydalanuvchi qarori — qo'shildi)*: Egasi sifatida xodimni vaqtincha bloklashni/blokdan chiqarishni istayman.
- Given xodim ro'yxatda tanlangan, When Egasi "Bloklash" bosadi, Then xodimning barcha faol sessiyalari/tokenlari darhol bekor qilinadi (revoke) va u qayta login qila olmaydi, toki Egasi "Blokdan chiqarish"ni bosmaguncha.
- Xodim ishdan bo'shaganda ham xuddi shu "Bloklash" amali ishlatiladi — bu M13'dagi avvalgi "huquqni darhol bekor qilish" chekka holatini yopadi.

**US-M13-06** *(2026-10-15: foydalanuvchi qarori — qo'shildi; 2026-10-15: qabul-5 O10 bo'yicha tuzatildi — vaqtinchalik parol SMS'da ochiq yuborilmaydi)*: Egasi sifatida xodimning parolini/PIN kodini qayta tiklashni (reset) istayman.
- Given xodim parolini/PIN'ini unutgan, When Egasi "Parolni tiklash" bosadi, Then eski parol/PIN bekor qilinadi, xodimning barcha faol sessiyalari tugatiladi va unga SMS orqali bir martalik tiklash kodi (OTP, `purpose=admin_reset`) yuboriladi; xodim shu kod bilan yangi parol/PIN o'rnatadi (parol/PIN hech qachon SMS'da ochiq matnda yuborilmaydi).
- Xodimning o'zi ham login ekranidan SMS OTP orqali parol tiklashni so'rashi mumkin (`04-ekranlar-va-ux.md`, BO-01/POS-01 login holatlari).

**US-M13-07** *(2026-10-15: foydalanuvchi qarori — qo'shildi)*: Egasi sifatida har bir xodimning faol sessiyalarini (qaysi qurilma, qachon kirgan, oxirgi faollik) ko'rishni va kerak bo'lsa bekor qilishni istayman.
- Given xodim tanlangan, When Egasi "Sessiyalar/qurilmalar" bo'limini ochadi, Then shu xodimning barcha faol sessiyalari (qurilma turi, IP/joylashuv — mavjud bo'lsa, kirgan vaqt, oxirgi faollik) ro'yxati ko'rinadi.
- Given bitta sessiya shubhali (masalan yo'qolgan qurilma), When Egasi "Bekor qilish" bosadi, Then shu sessiyaning tokeni darhol bekor qilinadi, qurilma login ekraniga qaytariladi, boshqa sessiyalarga ta'sir qilmaydi.

**US-M13-08** *(2026-10-15: foydalanuvchi qarori — qo'shildi; M17 US-M17-04 bilan bog'liq)*: Platforma admini sifatida tenantlar va ularning Egasi (owner) hisoblarini boshqarishni istayman.
- Given platforma admin paneli (ADM-01), When admin tenant tanlaydi, Then Egasi hisobini bloklash/blokdan chiqarish, Egasi parolini tiklash va Egasining faol sessiyalarini ko'rish/bekor qilish mumkin (masalan nizoli holatda yoki to'lov bo'yicha).
- Platforma admini oddiy tenant foydalanuvchilarining (Kassir/Menejer/Buxgalter) kundalik ma'lumotiga kirmaydi — faqat Egasi hisobi va obuna/texnik holat darajasida (`01-rollar-va-ssenariylar.md`, M15–M18 izohi: `platform.admin` tenant rollariga kirmaydi).

### Davlat tizimlari bog'liqligi
To'g'ridan-to'g'ri davlat talabi yo'q; lekin E-IMZO bilan imzolangan hujjatlar (e-faktura, hisobotlar) uchun aniq qaysi shaxs imzolagani audit maqsadida kerak.

### Offline xatti-harakati
Rol/huquqlar markazdan sinxronlanadi; offline rejimda faqat oxirgi sinxronlangan huquqlar amal qiladi, o'zgartirish faqat online holatda mumkin. *(2026-10-15: foydalanuvchi qarori)* Bloklash/sessiya bekor qilish amali internetga bog'liq — qurilma offline bo'lsa, bekor qilish shu qurilma keyingi marta internetga ulanganda kuchga kiradi.

### Chekka holatlar
- *(2026-10-15: hal qilindi — foydalanuvchi qarori)* ~~Xodim ishdan bo'shaganda huquqni darhol (real-time) bekor qilish zarurati~~ — endi US-M13-05/US-M13-07 orqali yechilgan: Egasi xodimni bloklaydi yoki aniq sessiyani bekor qiladi, token darhol amal qilmay qoladi.
- Bir xodimga berilgan ikki rol o'rtasida huquq ziddiyati (masalan bir modulda bir rol "T" beradi, ikkinchisi bermaydi) — yuqori huquq ustun bo'lishi kerak.
- Egasi o'zining yagona hisobini bloklay olmasligi kerak (tenant egasiz qolib ketmasin) — platforma admini orqali tiklash yo'li saqlanadi (US-M13-08).

---

## M14 — Filiallar

**Maqsad**: ko'p filialni (do'kon/ombor) bitta tizimda boshqarish va konsolidatsiyalangan hisobot berish.

### Foydalanuvchi hikoyalari

**US-M14-01**: Egasi sifatida barcha filiallar bo'yicha konsolidatsiyalangan savdo/ombor holatini ko'rishni istayman.
- Given 2 va undan ko'p filial mavjud, When Egasi umumiy dashboard'ni ochadi, Then har bir filial alohida va jami ko'rinishda ko'rsatiladi.

**US-M14-02**: Menejer sifatida bitta filialdan boshqasiga narx/chegirma siyosatini nusxalashni istayman.
- Given manba filial tanlangan, When Menejer "nusxalash"ni bosib maqsad filialni tanlaydi, Then narx/chegirma qoidalari maqsad filialga ko'chiriladi.

**US-M14-03**: Egasi sifatida yangi filial (do'kon) qo'shishni istayman.
- Given biznes yangi do'kon ochyapti, When Egasi yangi filialni ro'yxatdan o'tkazadi (nom, manzil, kassa soni), Then filial tenant ichida yangi mustaqil ombor/kassa birligi sifatida yaratiladi.

**US-M14-04** *(2026-10-14: tekshiruv)*: Egasi sifatida har bir filial uchun "aholi punkti toifasi"ni belgilashni istayman, chunki chakana savdoda aylanma solig'i stavkasi joylashuvga bog'liq (Soliq kodeksi 467-modda, O'RQ-1108 tahririda, 2026-01-01'dan).
- Given yangi filial yaratilmoqda yoki tahrirlanmoqda, When Egasi "aholi punkti toifasi"ni tanlaydi (Shahar, aholisi 100 ming+ / Boshqa aholi punkti / Borish qiyin yoki tog'li tuman), Then filialning chakana savdo aylanmasiga mos stavka (4% / 2% / 1%) qo'llanadi.
- Given toifa tanlanmagan, When filial saqlanadi, Then standart qiymat "Shahar, 100 ming+" (4%, eng ehtiyotkor) qo'yiladi va Egasiga tekshirish eslatmasi ko'rsatiladi.
- Given toifa o'zgartirildi, When saqlanadi, Then yangi stavka faqat `valid_from` sanasidan boshlab qo'llanadi, oldingi davrlar qayta hisoblanmaydi.

### Davlat tizimlari bog'liqligi
**Taxmin/ochiq savol**: har bir filial/kassa alohida Davlat reyestrida ro'yxatdan o'tishi kerakmi — manbada (`research_notes/texnik/02-kassa-ofd-markirovka.md`, 2-bo'lim) faqat virtual kassa **dasturini** reyestrga kiritish jarayoni tasvirlangan; filial/kassa darajasidagi alohida ro'yxatdan o'tish talabi aniq tasdiqlanmagan.

### Offline xatti-harakati
Har bir filial o'z offline event-log'iga ega; filiallar o'zaro real-time sinxronlanmaydi, markaziy serverga ulanganda sinxronlanadi (`spec/README.md`, offline-first qarori).

### Chekka holatlar
- Filiallar orasida bir xil tovarga turli narx siyosati (ruxsat etiladimi — biznes qoidasi).
- Bitta mijozning bir nechta filialdagi nasiya balansi — konsolidatsiya qilinishi kerakmi yoki filial bo'yicha alohidami (**ochiq savol**).
- Bir xil MXIK/QQS stavkasi barcha filiallarda bir xil bo'lishi (farqlanishi mumkin emas). *(2026-10-14: tekshiruv)* **Lekin aylanma solig'i stavkasi filiallar bo'yicha farq qilishi mumkin** (467-modda: chakana savdo joylashuvga qarab 4% / 2% / 1%) — turli toifadagi filiallari bor tenant uchun aylanma filial bo'yicha alohida hisoblanadi (468-modda "Alohida-alohida hisob yuritish" — batafsil talabi tasdiqlanmagan).

---

## M15 — Xarajatlar *(2026-10-14: qo'shildi)*

**Maqsad**: do'konning operatsion xarajatlarini (ijara, kommunal, ish haqi to'lovi, transport va h.k.) yozib borish, shunda Egasi **haqiqiy sof foydani** ko'radi.

### Foydalanuvchi hikoyalari

**US-M15-01**: Egasi/Menejer sifatida xarajatni 10 soniyada yozishni istayman.
- Given "Xarajat qo'shish" ochildi, When summa, toifa, to'lov manbai (kassa naqdi / bank / karta) va (ixtiyoriy) izoh kiritiladi, Then xarajat saqlanadi; manba "kassa naqdi" bo'lsa, M16'da avtomatik "kassadan chiqim" yozuvi yaratiladi.
- Toifalar standart ro'yxat bilan keladi (Ijara, Kommunal, Ish haqi, Transport, Soliq va yig'imlar, Ta'mirlash, Boshqa); Egasi o'zgartira oladi.
- Chek/hujjat fotosini biriktirish mumkin (ixtiyoriy).

**US-M15-02**: Egasi sifatida doimiy xarajatlarni (oylik ijara) har oy qayta kiritmaslikni istayman.
- Given takrorlanuvchi xarajat (summa, sana, davr) sozlangan, When muddat keladi, Then tizim "Ijara to'lash vaqti: 3 000 000 so'm" eslatmasini beradi; Egasi bir bosishda tasdiqlaydi (avtomatik to'lanmaydi).

**US-M15-03**: Egasi sifatida haqiqiy foydani ko'rishni istayman.
- Given davr tanlangan, When dashboard/hisobot ochiladi, Then **Sof foyda = Sotuv tushumi − Sotilgan tovar tannarxi (M04, FIFO/AVECO) − Xarajatlar (M15)**, toifalar bo'yicha xarajat taqsimoti bilan ko'rsatiladi.
- Xarajatlar M11 buxgalteriyada tegishli xarajat hisobiga o'tkaziladi (aniq hisob raqamlari — `spec/02-arxitektura` provodka qoidalarida).

### Davlat tizimlari bog'liqligi
To'g'ridan-to'g'ri yo'q. Ish haqi soliqlari (JShDS, ijtimoiy soliq) hisoblanmaydi — kadrlar/ish haqi moduli MVP'dan tashqarida; bu yerda faqat "ish haqi to'landi" summasi yoziladi.

### Offline xatti-harakati
Kassadan to'langan xarajat POS'da offline yoziladi (M16 bilan birga), sinxronlashda serverga tushadi.

### Chekka holatlar
- Xarajat bekor qilinsa — o'chirilmaydi, teskari yozuv bilan bekor qilinadi (audit).
- Bir xarajat bir nechta filialga tegishli (umumiy ijara) — MVP'da bitta filialga yoziladi, taqsimlash keyin.

---

## M16 — Kassa pul harakati (naqd pul) *(2026-10-14: qo'shildi)*

**Maqsad**: kassadagi naqd pulning har bir harakati yozilsin; smena oxirida "kassada qancha bo'lishi kerak" va "qancha bor" aniq solishtirilsin.

### Foydalanuvchi hikoyalari

**US-M16-01**: Kassir sifatida kassaga pul qo'yish va kassadan pul olishni sabab bilan yozishni istayman.
- Given smena ochiq, When kassir "Pul qo'yish" (maydalash uchun) yoki "Pul olish" ni tanlaydi, Then summa, sabab (Egasi oldi / Inkasso / Xarajat to'lovi → M15 / Boshqa) va kim bajargani yoziladi.
- *(2026-10-15: foydalanuvchi qarori)* **Standart limit**: Kassir PIN'siz kassadan pul olishni **50 000 so'mgacha** mustaqil amalga oshiradi; shundan katta "Pul olish" — Egasi/Menejer PIN tasdig'i bilan. Egasi istalgan raqamni (M13 orqali) o'zgartirishi mumkin (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #1).

**US-M16-02**: Kassir sifatida smena yopilganda kassadagi pulni sanab kiritishni istayman.
- Given smena yopilmoqda, When kassir sanalgan naqd summani kiritadi, Then tizim **kutilgan naqd** (boshlang'ich naqd + naqd sotuvlar − naqd qaytarishlar + naqd qarz to'lovlari + qo'yilgan − olingan) bilan solishtiradi va farqni (kamomad/ortiqcha) ko'rsatadi.
- Farq bo'lsa, kassir izoh yozadi va Egasiga xabar ketadi (M18).
- *(2026-10-15: foydalanuvchi qarori)* Smena yopilganda naqd bilan bir qatorda **"karta" jami** (qo'lda belgilangan "Karta" to'lovlari yig'indisi, terminal operatsiya raqamlari bilan) ham alohida ko'rsatiladi (POS-07 Z-hisobot, POS-15), Egasi kun oxirida bank ko'chirmasi bilan solishtirishi uchun (`02-modullar-talablari.md`, M01, US-M01-01).

**US-M16-03**: Egasi sifatida har bir smena va kassa bo'yicha naqd pul tarixini ko'rishni istayman.
- Given davr tanlangan, When "Kassa harakati" hisoboti ochiladi, Then har bir smena bo'yicha: boshlanish, sotuvlar, qo'yilgan/olingan (kim, nega), kutilgan va sanalgan naqd, farq.

### Davlat tizimlari bog'liqligi
Bu fiskal bo'lmagan operatsiyalar (sotuv emas). Onlayn kassa talablarida kassaga pul kiritish/chiqarishni alohida qayd etish shartmi — **ochiq savol** (`research_notes/texnik/02-kassa-ofd-markirovka.md` bilan tekshirish kerak).

### Offline xatti-harakati
To'liq offline ishlaydi (M01 bilan bir xil append-only jurnal).

### Chekka holatlar
- *(2026-10-14: tekshiruv)* Bir smenada kassir almashsa (masalan tushlik) — MVP'da joriy smena yopiladi (POS-15 sanash + Z-hisobot) va yangi kassir yangi smena ochadi; ochiq smena ichida topshirish — MVP'dan keyin.
- Aralash to'lovdagi naqd qismi kutilgan naqdga kiradi.

---

## M17 — Obuna va ro'yxatdan o'tish (platforma) *(2026-10-14: qo'shildi)*

**Maqsad**: do'kon tizimga o'zi ro'yxatdan o'tsin, sinab ko'rsin, obuna uchun to'lasin — bu bizning daromad oqimimiz. *(2026-10-15: foydalanuvchi qarori)* Tarif **yagona** (99 000 so'm/oy, hammasi narxga kiradi); Egasi faqat qo'shimcha kassa sonini va oylik/yillik to'lov davrini tanlaydi (`06-mvp-chegarasi.md`, 3.3).

### Foydalanuvchi hikoyalari

**US-M17-01**: Do'kon egasi sifatida 2 daqiqada ro'yxatdan o'tishni istayman.
- Given sayt ochildi, When telefon raqami kiritiladi va SMS kod tasdiqlanadi, Then do'kon nomi va faoliyat turi so'raladi; STIR, OFD, e-faktura ulash keyinroq (sozlamalarda, bosqichma-bosqich yo'riqnoma bilan).
- Ro'yxatdan o'tgach **30 kunlik bepul sinov** boshlanadi *(2026-10-15: foydalanuvchi qarori — endi yagona tarifning to'liq imkoniyatlari bilan, Biznes/Pro farqlanishi yo'q)*.

**US-M17-02**: Egasi sifatida tarifni tanlash va to'lashni istayman *(2026-10-15: foydalanuvchi qarori — qayta yozildi: uch pog'onali tanlov o'rniga yagona tarif + qo'shimcha kassa)*.
- Given sinov tugayapti yoki Egasi "Tarif" ni ochadi, Then **tarif tanlovi yo'q** — faqat bitta yagona tarif (99 000 so'm/oy, barcha modul+1 virtual kassa+AI+Telegram) va oylik/yillik (−20%) tanlanadi (`06-mvp-chegarasi.md`, 3.3); to'lov Click yoki Payme orqali amalga oshiriladi va obuna muddati uzayadi, to'lov uchun hujjat beriladi.
- Given Egasi qo'shimcha savdo nuqtasi (kassa) ochmoqchi, When "Qo'shimcha kassa qo'shish" tugmasini bosadi, Then har bir qo'shimcha kassa uchun **+39 000 so'm/oy** (taxmin) obuna summasiga qo'shiladi, keyingi to'lovdan qo'llanadi.
- Tarif limitlari tizimda qo'llanadi: faol kassalar soni (asosiy 1 + sotib olingan qo'shimchalar), AI oylik limiti; filiallar soni cheklanmaydi (filial — M14, kassa — M17 obunasi, ikkisi alohida tushuncha).

**US-M17-03**: Egasi sifatida to'lov muddatini unutmasligim va muddat o'tsa ham darhol to'xtab qolmasligimni istayman *(2026-10-14: foydalanuvchi qarori — 24 soatlik imtiyoz; 2026-10-15: foydalanuvchi qarori — imtiyozdan keyingi holat qayta belgilandi, quyida)*.
- **Eslatmalar (muddatdan oldin):** to'lov sanasidan **3 kun**, **1 kun** oldin va **to'lov kuni ertalab** — Egasiga Telegram (M18), ilova ichida banner va SMS (Telegram ulanmagan bo'lsa). Xabarda: summa, tarif, "To'lash" havolasi (Click/Payme).
- **Muddat o'tganda — 24 soatlik imtiyoz:** Given to'lov muddati o'tdi va to'lov kelmadi, Then tenant `grace` holatiga o'tadi va **24 soat davomida hamma narsa odatdagidek ishlaydi** (kassa, back-office, AI — barchasi to'liq ishlaydi); barcha ekranlarda qizil banner: "Obuna muddati o'tdi. 24 soat ichida to'lang, aks holda kassa to'xtaydi" + qolgan vaqt hisoblagichi.
- **Imtiyoz davomidagi eslatmalar:** muddat o'tishi bilan darhol, **12 soat qolganda** va **2 soat qolganda** — Telegram + banner + SMS.
- **24 soat o'tgach — to'liq to'xtash** *(2026-10-15: foydalanuvchi qarori — avvalgi "kassa ishlayveradi, back-office cheklanadi" taklifi va unga tegishli huquqiy ochiq savol bekor qilindi)*: Given 24 soatlik imtiyoz tugadi va to'lov hali kelmadi, Then tenant `restricted` holatiga o'tadi va butun tenant uchun kirish **to'liq yopiladi**: (a) tenant'ning barcha faol sessiya/tokenlari serverda bekor qilinadi (revoke); (b) har bir ochiq ekran — kassa (Android POS/veb-kassa) va back-office — darhol login sahifasiga qaytariladi; (c) login sahifasida "Obuna muddati tugagan" xabari va Click/Payme orqali to'lov havolasi ko'rsatiladi; (d) shu tenant hisoblaridan **yangi kirish ham rad etiladi**, to'lov amalga oshmaguncha. Boshqacha aytganda, kassa sotuvi ham, back-office ham — **hech biri** ishlamaydi (avvalgi "kassa ishlayveradi" taklifi va unga bog'liq huquqiy ochiq savol olib tashlandi).
- *(2026-10-15: foydalanuvchi qarori — D1, tor istisno)* **Lokautdan oldingi offline cheklarni yuborish (drain)**: yuqoridagi band bo'yicha `restricted` holatda yangi sotuv, login va boshqa barcha amal yopiq qoladi — lekin **lokautdan oldin** (24 soatlik imtiyoz davrida) offline qurilmada allaqachon yaratilgan, hali OFD'ga yuborilmagan cheklar fiskal 48 soatlik muddatni (VM 943) buzmasligi uchun fon rejimida (`sync.drain`) serverga va OFD'ga yuborilishda davom etadi. Bu yagona istisno: kassirga yangi ekran ochilmaydi, yangi sotuv qilib bo'lmaydi — faqat avval yaratilgan hujjatlar fonda yuboriladi.
- **Offline qurilmalar**: internetga ulanmagan kassa/POS qurilmasi serverdan signal kutmaydi — qurilmadagi mahalliy imzolangan litsenziya (`subscription_end + 24 soat` muddat bilan) tugagan payt qurilma **o'zi mahalliy ravishda qulflanadi**; internet qaytib, yangi muddatli litsenziya tasdiqlanmaguncha qurilma qayta ochilmaydi. *(2026-10-15: foydalanuvchi qarori — O2)* To'lov qilinganda qurilma tokenlari bekor qilinmaydi, balki `suspended` holatidan tiklanadi — qurilma keyingi onlayn bo'lishida jim (silent) ravishda yangi litsenziya oladi va kassir qayta parol kiritmasdan, PIN bilan ishni davom ettiradi.
- To'lov kelishi bilan darhol `active` holatiga qaytadi, kirish qayta ochiladi va "To'lov qabul qilindi, rahmat" xabari ketadi.
- Ma'lumotlarni eksport qilish (Excel) huquqi `active` holatda odatdagidek ishlaydi. `restricted` holatda back-office/kassaning o'zi butunlay yopiq *(2026-10-15: tuzatildi — avvalgi "eksport huquqi har doim saqlanadi" qoidasi endi amal qilmaydi)*, lekin *(2026-10-15: foydalanuvchi qarori — D2, tor istisno)* login sahifasidagi to'lov havolasi ochadigan **to'lov sahifasidan** "Ma'lumotlarimni yuklab olish" tugmasi orqali, telefon raqamiga yuboriladigan **SMS kod bilan tasdiqlangandan keyin**, to'liq eksport (US-M17-05'dagi kabi ZIP) so'rash mumkin — bu login yoki boshqa hech qanday ekranni ochmaydi, faqat eksport faylini tayyorlab beradi.
- **Foydalanish shartnomasi (ToS) eslatmasi** *(2026-10-15: foydalanuvchi qarori)*: xizmat shartlarida aniq ko'rsatilishi shart — to'lov kechiktirilib kassaga kirish to'xtatilgan davrda ham do'kon o'zining fiskal/soliq majburiyatlari uchun (agar savdo boshqa vosita bilan davom etsa) **to'liq o'zi javobgar** ekanligi; bu band huquqshunos bilan tasdiqlanishi tavsiya etiladi.

**US-M17-04**: Platforma admini sifatida (bizning jamoa) tenantlar, obunalar, to'lovlar va limitlarni ko'rishni istayman.
- Given ichki admin panel, When tenant tanlanadi, Then obuna holati, to'lov tarixi, AI sarfi, faol kassalar soni ko'rinadi; muddatni qo'lda uzaytirish (masalan pilot do'konlarga) mumkin.

**US-M17-05** *(2026-10-14: tekshiruv, Could)*: Egasi sifatida xizmatdan chiqsam ham barcha ma'lumotlarimni olib ketishni istayman.
- Given tenant **o'z xohishi bilan** `closed` holatga o'tgan (xizmatdan voz kechgan, obuna to'lovi kechikkani uchun emas), When Egasi "To'liq eksport"ni bosadi, Then barcha ma'lumotnomalar, hujjatlar va registrlar CSV (har jadval alohida) + asosiy hisobotlar PDF bitta ZIP faylda yuklanadi; amal audit jurnaliga yoziladi.
- Given tenant `closed`, Then ma'lumot kamida 90 kun (taxmin) eksport uchun saqlanadi; keyingi o'chirish tartibi huquqiy maslahatdan keyin (buxgalteriya hujjatlari muddati **kamida 5 yil (O'RQ-404, 29-modda)**).
- *(2026-10-15: foydalanuvchi qarori — aniqlashtirildi; 2026-10-15: D2 bilan tor istisno qo'shildi)* `restricted` holat (to'lov kechikkani uchun kirish to'xtatilgan, US-M17-03) bu **to'liq** hikoyaga asosan **kirmaydi** — back-office/kassaga umuman kirib bo'lmaydi. Lekin tor istisno sifatida US-M17-03'dagi kabi **faqat to'lov sahifasidan, SMS kod bilan tasdiqlangan** "Ma'lumotlarimni yuklab olish" yo'li mavjud (login yoki boshqa ekranlar ochilmaydi). To'liq (barcha jadval/hisobotlar bilan) eksport faqat to'lov qilib `active` holatga qaytgandan keyin yoki ixtiyoriy `closed` oqimida mavjud.

### Davlat tizimlari bog'liqligi
Mijozga bizning xizmatimiz uchun beriladigan hujjat — bizning yuridik shaxsimizning soliq majburiyati (mahsulot funksiyasi emas).

### Offline xatti-harakati
Ro'yxatdan o'tish va to'lov — faqat online. *(2026-10-15: foydalanuvchi qarori)* Offline qurilma (internetga ulanmagan kassa) serverdan signal kutmaydi — qurilmada mahalliy saqlangan, imzolangan litsenziya (`subscription_end + 24 soat` muddat bilan) bor; shu muddat tugaganda qurilma **o'zi mahalliy ravishda qulflanadi** (login ekraniga qaytadi), internet qaytib yangi muddatli litsenziya tasdiqlanmaguncha qayta ochilmaydi.

### Chekka holatlar
- To'lov o'tdi, lekin tizimga xabar kelmadi — Click/Payme holatini qayta tekshirish.
- *(2026-10-15: foydalanuvchi qarori bilan yangilandi)* **Qo'shimcha kassa sonini kamaytirish**: Egasi qo'shimcha kassalardan voz kechsa, faol kassalar soni yangi (kamroq) sonidan ko'p bo'lsa, ortiqcha kassa(lar)ni o'chirish/arxivlash so'raladi — ma'lumot (tarix, hujjatlar) o'chirilmaydi, faqat shu kassa yangi sotuv uchun yopiladi.

---

## M18 — Bildirishnomalar va Egasi uchun Telegram bot *(2026-10-14: qo'shildi)*

**Maqsad**: Egasi do'konda bo'lmasa ham asosiy raqamlar va muammolarni Telegram orqali bilsin.

### Foydalanuvchi hikoyalari

**US-M18-01**: Egasi sifatida Telegram akkauntimni do'konga ulashni istayman.
- Given back-office'da "Telegram ulash" bosildi, When Egasi bot havolasini ochib "Start" bosadi, Then akkaunt bir martalik kod orqali tenantga bog'lanadi; Menejerlarni ham ulash mumkin (huquqlariga qarab, M13).

**US-M18-02**: Egasi sifatida har kuni kechqurun qisqa hisobot olishni istayman.
- Given kun yopildi (yoki belgilangan soat keldi), Then bot yuboradi: bugungi savdo, sof foyda (M15 hisobga olingan), naqd (M16), yangi va qaytgan qarzlar, ertaga to'lashi kerak bo'lgan qarzdorlar (M08).

**US-M18-03**: Egasi sifatida muhim hodisalar haqida darhol xabar olishni istayman.
- Ogohlantirishlar (har birini yoqish/o'chirish mumkin): kam qolgan tovar (M04), smena kassa farqi (M16), limitdan katta qaytarish/chegirma (M02/M03), davlat hisobotidagi farq va **5 kalendar kunlik** muddat (M10), offline 48 soat chegarasiga yaqinlashish (M01), obuna to'lovi: muddatdan 3 kun va 1 kun oldin, to'lov kuni, muddat o'tganda va 24 soatlik imtiyozning 12 va 2 soati qolganda (M17, US-M17-03).

**US-M18-04**: Egasi sifatida botdan oddiy savol so'rashni istayman.
- Given bot ulangan, When Egasi "Bugun qancha sotdik?" deb yozadi, Then javob AI-01 orqali beriladi (raqamni kod hisoblaydi) va tarifning AI oylik limitidan hisoblanadi.

### Davlat tizimlari bog'liqligi
Yo'q.

### Offline xatti-harakati
Server tomonida ishlaydi; kassa offline bo'lsa, ma'lumotlar sinxronlangach xabarlar yangilanadi.

### Chekka holatlar
- Ulanmagan chatga hech qanday ma'lumot yuborilmaydi; xodim o'chirilsa, uning Telegram ulanishi ham bekor qilinadi.
- Mijozlarga qarz xabarlari (US-M08-08) alohida bot/kanal orqali — Egasi boti bilan aralashtirilmaydi.

---

## Ochiq savollar

1. *(2026-10-15: hal qilindi — foydalanuvchi qarori)* ~~Chegirma/qaytarish/nasiya limit summalari — ochiq manbada yo'q~~ — endi standart qiymatlar bor: chegirma PIN'siz 5% (M03), chek bilan qaytarish PIN'siz 100 000 so'm (M02), kassadan pul olish PIN'siz 50 000 so'm (M16); Egasi istalgan raqamni o'zgartirishi mumkin (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #1). Narx o'zgarishi tasdiqlash limiti (M09) hali ochiq (`taxmin`).
2. *(2026-10-15: hal qilindi — foydalanuvchi qarori)* ~~Markirovkalangan tovarni offline **sotish**/**qaytarish**/**ko'chirish** siyosati~~ — endi barcha uchi aniq: **sotish** — narx qurilmada ma'lum bo'lsa ruxsat, bo'lmasa taqiq (US-M01-03); **ko'chirish** (M06) — o'z filiallar/omborlari orasida offline ruxsat etiladi; **qaytarish** (M02) — faqat internet bor paytda (offline'da bloklanadi). CRPT Turon rasmiy API hujjatlari hamon yopiq, lekin bu mahsulot qarorlariga xalaqit bermaydi (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #5).
3. M10'dagi davlat hisobotini solishtirish uchun aniq tolerance (ruxsat etilgan farq) va eskalatsiya jarayoni — tadqiqotda yo'q, arxitektura jamoasi bilan birga ishlab chiqilishi kerak.
4. M11'dagi to'liq NSBU №21 hisob rejasi jadvali (barcha bo'lim/kichik hisob raqamlari) — tadqiqotda faqat qisman (I, II, V bo'lim) topildi, to'liq ro'yxat ochiq savol (`research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`).
5. M14'da ko'p filialli mijoz (nasiya) balansini konsolidatsiya qilish yoki filial bo'yicha ajratish — biznes qarori kerak.
6. M07/M10'da e-faktura va QQS hisobotini dasturiy (API) olish yo'li hali ochiq emas — MVP'da qo'lda/yarim-avtomatik boshlanishi taxmin qilingan.
7. Onlayn/QR to'lovda fiskal chekni kim chiqarishi (merchant yoki to'lov tizimi) — huquqiy talqin ziddiyatli, M01'ga tegishli (`research_notes/texnik/03-efaktura-va-tolov.md`, 2.5-bo'lim).
8. *(2026-10-14: qisman hal qilindi)* M10'dagi 5 kalendar kunlik tuzatish qoidasining qonun asosi endi aniq — Soliq kodeksi 81-moddasi, O'RQ-1108 (lex.uz/docs/-7944527). Hali ochiq qolgan qism: tuzatishni aniq qayerga/qanday (ariza shakli, my.soliq.uz shaxsiy kabineti orqalimi) yuborish kerakligi — bu protsedura darajasi manbada topilmadi.
9. M07'da yetkazib beruvchi vakili ishonchnoma bilan kelganda, 2026-01-01'dan majburiy e-ishonchnoma (Vakolat.uz) tekshiruvi kerakmi — API hujjati topilmadi (`research_notes/texnik/09-soliq-integratsiyasi.md`, 14-qator).
10. M08'da qarz to'lovi uchun alohida fiskal chek chiqarilishi kerakligi aniq manbada tasdiqlanmagan.
11. M01'da markirovka kodi tekshiruvi muvaffaqiyatsiz bo'lganda "sotuvni rad etish" qat'iy siyosat sifatida to'g'ri yechimmi, yoki ogohlantirish bilan davom ettirish amaliyotda qo'llanilarmi — CRPT Turon rasmiy hujjati yopiqligi sababli tasdiqlanmagan.
12. *(2026-10-15: hal qilindi — foydalanuvchi qarori)* ~~Fiskal chek bilan sotilgan tovarga keyinroq e-faktura berish ruxsati va tartibi (M01)~~ — endi mahsulot talabi sifatida qo'llab-quvvatlanadi: US-M01-06, `einvoices.related_doc` orqali chekka bog'lanadi, QQS ikkinchi marta hisoblanmaydi.
13. *(2026-10-15: foydalanuvchi qarori — D3)* Bulut-print (cloud-print) chek printerlarining O'zbekistonda mavjudligi/narxi va iOS'da faqat elektron (QR/Telegram) chek chiqarishning huquqiy/fiskal jihatdan ruxsat etilganligi — ochiq savol (M01, qurilma/chop etish qamrovi).

## Manbalar

- `spec/README.md` — asosiy qarorlar
- `research_notes/texnik/00-xulosa-va-ochiq-savollar.md`
- `research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`
- `research_notes/texnik/02-kassa-ofd-markirovka.md`
- `research_notes/texnik/03-efaktura-va-tolov.md`
- `research_notes/texnik/08-mahsulot-modullari.md`
- `research_notes/texnik/09-soliq-integratsiyasi.md`
- `research_notes/texnik/11-raqobatchilar-kamchiliklari.md`
- `spec/01-mahsulot/01-rollar-va-ssenariylar.md` (huquqlar matritsasi uchun o'zaro havola)
- `spec/02-arxitektura/12-autentifikatsiya-oauth2.md` — autentifikatsiya arxitekturasi (o'z OAuth 2.0 implementatsiyasi, mock yo'q) — Foydalanuvchi qarori, 2026-10-15
- `spec/tekshiruv/savollar-yakuniy-tavsiyalar.md` — 2026-10-15, 15 ta foydalanuvchi qarori (rol limitlari, fiskal yo'l, CRPT, e-faktura operatori, offline markirovka, karta, nasiya, narx/chegirma, yopilgan oy va h.k.)
