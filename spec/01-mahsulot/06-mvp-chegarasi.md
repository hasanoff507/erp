# MVP chegarasi, raqobatchilardan farq va muvaffaqiyat o'lchovlari

## Asosiy xulosalar

1. **18 modulning (M01-M18) hammasi MVP chegarasida** — M01-M14 `spec/README.md` va `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` (Asosiy xulosa #2) orqali qabul qilingan, M15-M18 2026-10-14 da foydalanuvchi qarori bilan qo'shilgan (`07-tuzatishlar-va-yechimlar.md`, #12, #13, #15, #16). Har bir modulda kamida bitta Must-darajali hikoya bor; modul ichidagi ayrim hikoyalar Should/Could (1.1-jadval).
2. *(2026-10-15: foydalanuvchi qarori)* **4 ta AI funksiya** (AI-01, AI-03, AI-05, AI-06) MVP ichida — AI-03 (qog'oz hujjat OCR) 2026-10-14'dagi tekshiruv bosqichida vaqtincha "MVP'dan keyin"ga surilgan edi, 2026-10-15'da foydalanuvchi qarori bilan MVP'ga qaytarildi. Ularning o'zi Must emas — ular deterministik ("kod hisoblaydi") asosiy jarayonning ustiga qo'yilgan tushuntirish/matn qatlami, shuning uchun Should/Could darajasida (`spec/01-mahsulot/05-ai-funksiyalar.md`).
3. **Won't ro'yxati** aniq: kadrlar/ish haqi, CRM/sodiqlik (shu jumladan M03'dagi loyallik bonusi), ishlab chiqarish, boshqa tizimlardan ma'lumot ko'chirish konnektorlari, 7 ta AI funksiya (AI-02, 04, 07-11) — barchasi tadqiqot bilan tasdiqlangan qarorlar (`spec/README.md`, `00-xulosa-va-ochiq-savollar.md`) *(2026-10-14: neytral ifodalandi — koordinator direktivasi)*.
4. Raqobatchilardan eng aniq manbali farq — **AI funksiyasi**: tekshirilgan 9 mahsulotdan faqat 2 tasida (REGOS, Smartup) bor, qolgan 7 tasida rasmiy sahifada AI haqida da'vo yo'q (`research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`, 2-bo'lim).
5. **Muvaffaqiyat o'lchovlarining aksariyati "taxmin"** — mahsulot hali ishga tushmagan, O'zbekiston SaaS bozorida churn/retention/pilot-konversiya bo'yicha ochiq ma'lumot yo'q (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 1.1-bo'lim, 4-band). Faqat offline-sync va fiskal muddatlar kabi **qonuniy majburiy** ko'rsatkichlar (masalan 48 soat) manbali.
6. **Eng katta bloklovchi tashqi omillar** — barchasi tadqiqotning "Eng katta 5 texnik xavf" ro'yxatidan: Asl belgisi integrator API yopiq, my.soliq.uz rasmiy API yo'q, virtual kassa reyestr narxi/muddati noma'lum, ЗРУ-764 sertifikatlash noaniqligi, E-IMZO rasmiy dasturchi hujjati yo'q (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, "Eng katta 5 texnik xavf" bo'limi).
7. MoSCoW'dagi **hikoya darajasidagi** taqsimot (Must/Should/Could) — modul darajasidagi "18 modul MVP" qarorining ichidagi ustuvorlik — bu hujjatda **loyihaviy tavsiya** sifatida berilgan (jamoat tadqiqot fayllarida tayyor shaklda topilmagan), arxitektura/sprint rejalashtirish bosqichida qayta ko'rib chiqilishi mumkin.
8. *(2026-10-15: foydalanuvchi qarori)* **Narx modeli tubdan o'zgardi — yagona tarif**: 2026-10-14'dagi Start/Biznes/Pro (49 000/129 000/249 000 so'm) uchburchagi **bekor qilindi**. Endi **bitta tarif — 99 000 so'm/oy, hammasi (18 modul, 1 virtual kassa/fiskal, AI oylik limiti, Telegram bot) narxga kiradi**; qo'shimcha har bir kassa — **+39 000 so'm/oy** (taxmin, qo'shimcha xizmat). Yillik to'lovda −20% va 30 kunlik bepul sinov saqlanadi. Unit-iqtisod: 1 kassali tenant xarajati taxminan **60 000–68 000 so'm/oy** → marja taxminan **31 000–39 000 so'm** (taxmin, `spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #13). Batafsil — 3.3-bo'lim.

---

## 1. MoSCoW taqsimoti

### 1.1 Modullar va foydalanuvchi hikoyalari (US-Mxx-nn)

Barcha 18 modul MVP ichida (MVP qarori, `spec/README.md`); har birida kamida bitta Must hikoya bor, qolganlari Should/Could. Quyida har bir modulning hikoyalari (`spec/01-mahsulot/02-modullar-talablari.md`dan) ustuvorlik bo'yicha ajratilgan.

| Modul | Must | Should | Could |
|---|---|---|---|
| M01 Kassa | US-M01-01 (sotuv/chek), US-M01-02 (offline+sync), US-M01-03 (markirovka tekshirish), US-M01-04 (smena/Z-hisobot) | — | — |
| M02 Qaytarish | US-M02-01 (asl chek bo'yicha), US-M02-03 (QQS tuzatish) | US-M02-02 (limit tasdiqlash) | — |
| M03 Chegirma | US-M03-01 (limit ichida chegirma) | US-M03-02 (avtomatik qoida) | US-M03-03 (margin hisoboti) |
| M04 Ombor qoldig'i | US-M04-01 (kirim balans) | US-M04-02 (past qoldiq ogohlantirish), US-M04-03 (ko'p filial konsolidatsiya), US-M04-06 (yaroqlilik muddati, hisobdan chiqarish) *(2026-10-14: tekshiruv)* | — |
| M05 Inventarizatsiya | US-M05-01 (sanash), US-M05-02 (farq tasdiqlash), US-M05-03 (buxgalteriya yozuvi) | — | — |
| M06 Ko'chirish | US-M06-01 (yuborish), US-M06-02 (qabul tasdiqlash) | US-M06-03 (tarix/72 soat kuzatuv) | — |
| M07 Xarid | US-M07-01 (xaridnoma), US-M07-02 (qabul), US-M07-03 (e-faktura+QQS), US-M07-04 (yetkazib beruvchiga to'lov) | US-M07-05 (yetkazib beruvchiga qaytarish) *(2026-10-14: tekshiruv)* | — |
| M08 Nasiya / Qarz daftari | US-M08-01 (limitli sotuv), US-M08-02 (kredit limiti, ixtiyoriy), US-M08-04 (qarz to'lovi), **US-M08-05 (tez qarz yozish, offline), US-M08-06 (mijoz daftari), US-M08-07 (eski daftarni ko'chirish), US-M08-09 (va'da sanasi va eslatma), US-M08-10 (qarzlar hisoboti), US-M08-11 (yetkazib beruvchiga qarz)** *(2026-10-14)* | US-M08-03 (AI eslatma, AI-06ga bog'liq), US-M08-08 (mijozga SMS/Telegram — SMS narxi va provayder aniqlanishi kerak) | — |
| M09 Narxlar | US-M09-01 (narx+tarix), US-M09-03 (kassada ko'rish) | US-M09-02 (katta o'zgarish tasdiqlash), US-M09-04 (yorliq chop etish), US-M09-05 (ichki shtrix-kod), US-M09-06 (tarozi shtrix-kodi) *(2026-10-14)* | — |
| M10 QQS | US-M10-01 (avtomatik QQS), US-M10-02 (davlat hisobotini solishtirish, 5 kun), US-M10-04 (aylanma solig'i solishtirish) | US-M10-03 (qizil faktura kuzatuv) | — |
| M11 Buxgalteriya | US-M11-01 (avtomatik provodka), US-M11-02 (oy yakuni) | US-M11-03 (sodda dashboard) | — |
| M12 Hisobotlar | US-M12-01 (kunlik savdo), US-M12-03 (QQS solishtirish eksport) | US-M12-02 (eng ko'p/kam sotilgan) | — |
| M13 Huquqlar | US-M13-01 (xodim+rol), US-M13-02 (bir necha rol birlashuvi) | US-M13-03 (limit sozlash) | — |
| M14 Filiallar | US-M14-03 (yangi filial qo'shish) | US-M14-01 (konsolidatsiya) | US-M14-02 (narx/chegirma nusxalash) |
| M15 Xarajatlar *(2026-10-14)* | US-M15-01 (xarajat yozish), US-M15-03 (sof foyda) | US-M15-02 (takrorlanuvchi xarajat) | — |
| M16 Kassa pul harakati *(2026-10-14)* | US-M16-01 (qo'yish/olish), US-M16-02 (smena sanash va farq), US-M16-03 (tarix) | — | — |
| M17 Obuna va ro'yxatdan o'tish *(2026-10-14)* | US-M17-01 (ro'yxatdan o'tish + sinov), US-M17-02 (tarif va to'lov), US-M17-03 (kechikkan to'lov siyosati), US-M17-04 (ichki admin) | — | US-M17-05 (to'liq eksport) *(2026-10-14: tekshiruv)* |
| M18 Bildirishnomalar / Telegram bot *(2026-10-14)* | US-M18-01 (ulash), US-M18-02 (kunlik hisobot) | US-M18-03 (ogohlantirishlar) | US-M18-04 (botda AI savol) |

*Izoh: bu jadvaldagi Should/Could ajratmasi modulning MVP'da bo'lish-bo'lmasligiga ta'sir qilmaydi (hammasi MVP ichida) — faqat qaysi hikoya birinchi, qaysi biri ikkinchi navbatda qurilishini ko'rsatadi. Qabul mezoni ("Must ro'yxati 18 modulni qoplaydi") bajarilgan — jadvaldagi har bir modulda kamida bitta Must band bor.*

*MVP'dan keyinga surilgan hikoyalar (2026-10-14, `11-backlog.md` bilan muvofiq): US-M03-02 (avtomatik chegirma qoidasi), US-M14-02 (narx/chegirma nusxalash), US-M08-08 (mijozga SMS/Telegram), US-M17-05 (to'liq eksport). *(2026-10-15: foydalanuvchi qarori)* US-M04-04 (3)-yo'l (AI-03) endi MVP ichida — AI-03 qaytadan MVP'ga kiritildi, bu yo'l backlog ro'yxatidan olib tashlandi. Qolgan barcha Should/Could hikoyalar (shu jumladan US-M14-01, US-M04-03 — 4-sprint) MVP sprintlarida.*

*US-M10-04 (aylanma solig'i solishtirish) va US-M07-04 (yetkazib beruvchiga to'lov) Must'ga ko'tarildi (dastlabki loyihada Should edi): (a) aylanma solig'i — maqsadli kichik do'konlarning qaysi ulushi QQS to'lovchi, qaysi ulushi aylanma solig'i to'lovchi ekani manbada aniqlanmagan (**taxmin/ochiq savol** — pastda), shuning uchun ikkisini ham Must deb olish xavfsizroq, aks holda aylanma solig'i to'lovchi mijozlar uchun markaziy qiymat taklifi ishlamay qoladi; (b) yetkazib beruvchiga to'lov — US-M10-03 (qizil faktura QQS krediti to'lovdan keyin) va US-M11-02 (oy yopish, Must) to'g'ridan-to'g'ri shu to'lov holatiga bog'liq, to'lovsiz bu ikkisi to'liq ishlay olmaydi.*

### 1.2 AI funksiyalar (AI-nn)

`spec/01-mahsulot/05-ai-funksiyalar.md`dagi "Hukm" ustuniga asoslanib (MVP → Should/Could, Keyingi bosqich/Hozircha real emas → Won't):

| AI ID | Funksiya | MoSCoW | Sabab |
|---|---|---|---|
| AI-01 | Umumiy biznes savol-javob chat | **Should** | Qimmatli farqlovchi, lekin asosiy savdo/ombor/soliq jarayoni AI'siz ham ishlaydi (`05-ai-funksiyalar.md`, AI-01) |
| AI-05 | Davlat hisoboti tafovutini tushuntirish | **Should** | Markaziy oqim (M10/US-M10-02) kod darajasida Must; AI-05 shu natijaning ustiga qo'yilgan tabiiy-til tushuntirish qatlami — hal qiluvchi funksiya emas, qo'shimcha qiymat (`05-ai-funksiyalar.md`, AI-05) |
| AI-03 | Qog'oz hujjat OCR (pilot bilan, torroq qamrov) | **Should** *(2026-10-15: foydalanuvchi qarori — qaytadan MVP'ga kiritildi; 2026-10-14'dagi "Could → MVP'dan keyin" tekshiruv qarori bekor qilindi)* | Qamrov tor (faqat qog'oz/texnik uzilish holatlari), kirill-lotin aralash aniqlik tasdiqlanmagan, pilot talab qiladi (`05-ai-funksiyalar.md`, AI-03, Chegaralar); asosiy savdo/ombor jarayoni AI-03'siz ham ishlaydi (qo'lda/Excel-CSV kiritish muqobili bor), shuning uchun Must emas — lekin endi MVP sprintlarida quriladi |
| AI-06 | Nasiya eslatma matni | **Could** | Qiymatli, lekin M08 (nasiya) asosiy funksiyasi (limit, qarz yozish) AI'siz ham to'liq ishlaydi; AI faqat matn yozadi (`05-ai-funksiyalar.md`, AI-06) |
| AI-02, 04, 07, 08, 09, 10, 11 | STT, qo'lyozma OCR, anomaliya, bank kategoriyalash, talab bashorati, narx optimallashtirish, TTS brifing | **Won't** | Barchasi `05-ai-funksiyalar.md`da "Keyingi bosqich" yoki "Hozircha real emas" deb manbali asoslangan |

### 1.3 Won't ro'yxati (MVP'dan tashqarida)

| Band | Sabab/manba |
|---|---|
| Kadrlar/ish haqi moduli | MVP 18 modul ro'yxatida yo'q (`spec/README.md`; M15 faqat "ish haqi to'landi" summasini xarajat sifatida yozadi, ish haqi hisoblanmaydi); JShDS/ijtimoiy soliq hisobotini solishtirish shu sababli ham MVP'dan tashqari (`02-modullar-talablari.md`, M10 qamrov eslatmasi) |
| CRM/sodiqlik (mijozlar bazasi, loyallik/bonus karta dasturi) | `00-xulosa-va-ochiq-savollar.md`, Asosiy xulosa #2; M03'dagi loyallik bonusi ham shu sababli olib tashlangan (`02-modullar-talablari.md`, M03) |
| Ishlab chiqarish (retsept, ishlab chiqarish buyurtmasi) | `00-xulosa-va-ochiq-savollar.md`, Asosiy xulosa #2 |
| Boshqa tizimlardan ma'lumot ko'chirish konnektorlari | MVP'dan tashqarida — AIOS noldan (from-scratch) qurilgan, mustaqil mahsulot; hech qanday tashqi buxgalteriya/ERP tizimi bilan integratsiya, migratsiya, import, eksport yoki sinxronizatsiya qilinmaydi va ular hech qachon ma'lumot manbai bo'lmaydi; mavjud tizimlar faqat ma'lumotlar modelini loyihalashda **struktura namunasi/benchmark** sifatida ishlatilgan (`01-erp-modullar-va-malumot-modeli.md`, 7-band; `spec/README.md`). Boshlang'ich ma'lumot kiritish (onboarding) faqat uch yo'l bilan: (1) qo'lda kiritish, (2) Excel/CSV shablon orqali import, (3) AI-03 yordamida qog'oz hujjat/fotosidan kiritish *(2026-10-14: aniqlashtirildi — koordinator direktivasi, `07-tuzatishlar-va-yechimlar.md`; 2026-10-15: foydalanuvchi qarori bilan AI-03 MVP'ga qaytarildi, shuning uchun (3)-yo'l ham endi MVP'da mavjud, "MVP'dan keyin" emas)* |
| Mol-mulk va yer solig'i hisobotini solishtirish | Asosiy vositalar hisobi MVP'da yo'q, shu sababli bu hisobotlarni solishtirish mazmunsiz (`02-modullar-talablari.md`, M10 qamrov eslatmasi) |
| AI-02, 04, 07, 08, 09, 10, 11 (yuqoridagi 1.2-jadval) | `05-ai-funksiyalar.md` |

---

## 2. Raqobatchilardan farqlar

| Raqobatchi(lar) | Ularda yo'q/zaif | Bizning MVP javobi | ID |
|---|---|---|---|
| BILLZ, MoySklad, HIPPO, Bito ERP, mDokon, iiko, Poster POS (7/9 tekshirilgan mahsulot) | Rasmiy sahifada AI funksiyasi haqida hech qanday da'vo yo'q; faqat REGOS (Pro tarif) va Smartup (fotodan tovar tanish)da bor, ular ham tor qamrovda (`research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`, 2-bo'lim) | O'zbek tilida biznes savol-javob chat, hujjat OCR, soliq tafovutini tushuntirish, nasiya eslatma matni | AI-01, AI-03, AI-05, AI-06 |
| REGOS, MoySklad, HIPPO (3/9) | Nasiya/qarz moduli rasmiy sahifada aniq ko'rsatilmagan (`06-raqobatchilar-texnik-va-uskunalar.md`, 2-bo'lim — "bu yo'q degani emas, balki marketing sahifasida tilga olinmagan" degan ehtiyot bilan) | Nasiya markaziy MVP moduli: kredit limiti, qisman/to'liq to'lov, AI eslatma | US-M08-01…04 |
| Butun bozor (markirovkalangan tovar sotuvchilari) | Markirovka skanerlari "muntazam ishlamaydi", mahsulot narxini 2-4% oshiradi, jarima 2-20% aylanmaga (`research_notes/texnik/11-raqobatchilar-kamchiliklari.md`) | Aniq MVP siyosati (xato holatda sotuvni rad etish — taxmin), 72 soatlik ko'chirish muddatini kuzatish/ogohlantirish, qabul paytidagi skanerlash xatosini aniq ko'rsatish | US-M01-03, US-M06-03 |
| MoySklad, Poster POS (import/xorijiy tizimlar) | Zaif telefon support, shartlar/narx beqarorligi, geopolitik to'xtatish xavfi (hisob muzlatish, mintaqaviy bloklanish) — **taxmin/qamrov eslatmasi**: bu shikoyatlar (`research_notes/texnik/11-raqobatchilar-kamchiliklari.md`) asosan Rossiya/Qozog'iston bozoridagi sharhlardan (otzovik.com, startpack.ru) olingan; O'zbekistondagi aynan shu mahsulotlar foydalanuvchilariga tatbiqi mustaqil tasdiqlanmagan. (ЮKassa O'zbekiston raqobatchisi sifatida `06-raqobatchilar-texnik-va-uskunalar.md`da yo'q — jadvaldan olib tashlandi.) | Mahalliy (O'zbekistonda) joylashgan xizmat, o'zbek tilidagi support — **taxmin**: aniq support/SLA siyosati bu hujjatda belgilanmagan, MVP'dan keyin ishlab chiqilishi kerak | — (ochiq savol) |
| Barcha 9 tekshirilgan mahsulot | Davlat tuzgan soliq hisobotini ichki hisob bilan avtomatik solishtirish funksiyasi haqida hech birining rasmiy sahifasida da'vo topilmadi | Markaziy MVP oqimi: QQS/aylanma solig'i hisobotini **5 kalendar kun** ichida solishtirish *(2026-10-14: tuzatildi)* | US-M10-02, AI-05 |

*Eslatma (oxirgi qator uchun taxmin belgisi): bu talab 2026-01-01'dan boshlangan juda yangi davlat talabi; raqobatchilarning bu funksiyani hali reklama qilmagani ularda **umuman yo'qligini** mustaqil tasdiqlamaydi — faqat `06-raqobatchilar-texnik-va-uskunalar.md` va `11-raqobatchilar-kamchiliklari.md` tekshirilgan sahifalarida bu haqida hech qanday matn topilmaganini bildiradi.*

**Pozitsiyalashni aniqlashtirish** *(2026-10-14: tuzatildi — yuqoridagi birinchi qator haddan oshirilgan edi)*: avvalgi tezis "hech bir raqobatchi OFD/e-faktura/Asl belgisi bilan integratsiya qilmagan" edi — bu **noto'g'ri**: MoySklad o'z rasmiy saytida "Регистрация продаж в налоговой Узбекистана через один клик" (OFD) va AslBelgisi (markirovka) integratsiyasini ochiq da'vo qiladi, Didox orqali e-faktura ham bor. REGOS ham Didox bilan integratsiyalangan. To'g'ri farqlanish: (1) AIOS'da bu integratsiyalar **bitta tizim ichida**, uchinchi tomon kassa/EDO dasturisiz; (2) **davlat tuzgan soliq hisobotini ichki hisob bilan solishtirish** (yuqoridagi jadval qatori) — bu haqiqatan hech bir raqobatchida yo'q, chunki bu 2026-01-01'dan boshlangan butunlay yangi talab; (3) offline-first + markirovka maxsus holatlari; (4) o'zbek tilidagi AI. Batafsil: `07-tuzatishlar-va-yechimlar.md`.

---

## 3. Muvaffaqiyat o'lchovlari

### 3.1 Mahsulot o'lchovlari

| O'lchov | Maqsad qiymat | Holat/manba |
|---|---|---|
| Offline chekning OFD'ga yetib borish muddati | 48 soatdan oshmasligi — **100%** | Qonuniy majburiy chegara, manbali (`research_notes/texnik/02-kassa-ofd-markirovka.md`, 1-ilova 31-band) |
| Markirovkalangan tovarni ko'chirish muddati | 72 soatdan oshmasligi — **100%** | Qonuniy majburiy chegara (23-son qaror, `02-kassa-ofd-markirovka.md`, 106-qator) |
| O'rtacha chek yaratish vaqti (kassada) | **Taxmin** — manbada aniq raqam yo'q; raqobatchilar ham bu ko'rsatkichni rasmiy sahifalarida e'lon qilmaydi | **O'lchash formulasi**: birinchi tovar skanerlanishidan to'lov tasdiqlanishigacha o'tgan vaqt (soniya), M01 POS event-log vaqt belgilaridan hisoblanadi (ichki telemetriya, tashqi manba yo'q) — pilot davrida o'lchanishi kerak |
| Davlat hisoboti tafovutlarining 5 kalendar kun ichida hal qilinish darajasi *(2026-10-14: "5 ish kuni" tuzatildi)* | **Taxmin** — manbada aniq raqam yo'q, chunki bu funksiya hali hech qayerda ishlatilmagan (yangi 2026 talabi) | **O'lchash formulasi**: (5 kalendar kun ichida Buxgalter tomonidan tasdiqlangan yoki tuzatish kiritilgan tafovutlar soni ÷ shu davrda aniqlangan jami tafovutlar soni) × 100%, M10 holat jurnalidan (US-M10-02) hisoblanadi — pilot davrida o'lchanishi kerak |
| Markirovka kodi tekshirish muvaffaqiyat darajasi (POS'da) | **Taxmin** | **O'lchash formulasi**: (muvaffaqiyatli tekshirilgan/qabul qilingan markirovka kodlari soni ÷ jami skanerlangan markirovka kodlari soni) × 100%, M01 POS event-logidan kunlik hisoblanadi. Bozorda umumiy skanerlash xatosi qabul zanjirida 80-90% (`00-xulosa-va-ochiq-savollar.md`, 6-band) — bu POS darajasidagi ko'rsatkich uchun faqat kontekst, bizning aniq qiymatimiz mustaqil o'lchanmagan |

### 3.2 Biznes o'lchovlari

| O'lchov | Maqsad qiymat | Holat/manba |
|---|---|---|
| Pilot mijozlar soni (birinchi 3 oy) | **Taxmin** — manbada yo'q | Bozor hujjatida ham aniq raqam yo'q (`research_notes/AI ERP startap Ozbekistonda/00_oldingi_hujjat.md`, "Tekshirilmagan ma'lumotlar") |
| Oylik mijoz yo'qotish (churn) darajasi | **Taxmin** — manbada yo'q | "Mahalliy SME SaaS'da churn darajasi ochiq manbada yo'q, pilot mijozlarda o'lchanishi kerak" (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 1.1-bo'lim, 4-band) |
| Oylik obuna narxi (tarif) | *(2026-10-15: foydalanuvchi qarori — oldingi uch pog'onali taklif bekor qilindi, #13 ham shu bilan superseded)* **Yagona tarif — 99 000 so'm/oy, hammasi narxga kiradi**: 18 modul, 1 virtual kassa (fiskal), AI oylik limiti, Telegram bot. Qo'shimcha kassa — **+39 000 so'm/oy** (taxmin). Yillik to'lovda −20%, 30 kun bepul sinov. Eski variantlar (Start/Biznes/Pro 49k/129k/249k; ilgarigi 149k/349k/699k; 69k–999k) — barchasi bekor, faqat tarixiy ma'lumot sifatida 3.3-bo'limda saqlanadi. Batafsil — 3.3-bo'lim | Raqobatchilar narxi: `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`, 1-bo'lim jadvali; `spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #13 |
| To'lovga tayyorlik (oyiga qancha so'm) | **Taxmin** — manbada yo'q | "20-30 ta do'kon egasi bilan suhbat kerak" (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 1.1-bo'lim, 2-band) |
| NPS/mijoz mamnuniyati | **Taxmin** — manbada yo'q | Pilot davrida belgilanishi kerak |


### 3.3 Tarif taklifi — yagona tarif *(2026-10-15: foydalanuvchi qarori — 2026-10-14'dagi uch pog'onali Start/Biznes/Pro taklifi butunlay bekor qilindi)*

**Qaror:** uch pog'onali tarif (Start/Biznes/Pro) o'rniga **bitta tarif** — barcha mijoz uchun bir xil narx va to'liq funksiya to'plami. Tamoyil endi "pog'ona bo'yicha arzon" emas, balki **"hammasi bitta narxda, qo'shimcha kassa — alohida haq"**.

| | Narx (so'm/oy) | Kimga | Ichida |
|---|---|---|---|
| **Yagona tarif** | **99 000** | Har qanday hajmdagi do'kon — 1 savdo nuqtasi (1 virtual kassa) bilan boshlanadi | **Barcha 18 modul** (kassa, qaytarish, chegirma, ombor, inventarizatsiya, ko'chirish, xarid, nasiya, narxlar, QQS, buxgalteriya, hisobotlar, huquqlar, filiallar, xarajatlar, kassa pul harakati, obuna, bildirishnomalar), **1 virtual kassa (fiskal, OFD)**, **AI oylik limiti** (AI-01/03/05/06), **Telegram bot** |
| **Qo'shimcha kassa** | **+39 000**/kassa (taxmin) | 2-, 3-, ...-kassali do'kon, filiallar | Har bir qo'shimcha virtual kassa (fiskal modul to'lovi ~35 000 + ~4 000 zahira — `spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, (b)-bo'lim va tavsiya #2) |

- **Yillik to'lov: −20%** (o'zgarmadi). **Sinov muddati: 30 kun bepul** (o'zgarmadi).
- Filiallar/ko'p kassa: bitta obuna ichida istalgancha qo'shimcha kassa qo'shiladi, har biri +39 000 so'm/oy; modul funksiyasi (buxgalteriya, AI, Telegram) hammasi uchun bir xil — kassa soniga qarab cheklanmaydi.
- O'z fiskal kassasi (mustaqil onlayn-NKM) bor do'kon virtual kassa qo'shimchasini olmaydi (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, (b)-bo'lim, band 3).
- **Eski tariflar (bekor qilindi, faqat tarixiy ma'lumot sifatida):**

  | ~~Eski tarif~~ | ~~Narx~~ | Bekor qilingan sana |
  |---|---|---|
  | ~~Start~~ | ~~49 000~~ | 2026-10-15 |
  | ~~Biznes~~ | ~~129 000~~ | 2026-10-15 |
  | ~~Pro~~ | ~~249 000~~ | 2026-10-15 |
  | ~~(ilgarigi birinchi taklif) Start/Biznes/Pro~~ | ~~149 000 / 349 000 / 699 000~~ | 2026-10-14 |
  | ~~(dastlabki, izohsiz) diapazon~~ | ~~69 000–999 000~~ | 2026-10-14 |

- **Raqobatchilar bilan taqqoslash (rasmiy sahifalar, 2026):**

  | Raqobatchi | Narx (so'm/oy) | Izoh |
  |---|---|---|
  | **AIOS (bizning yagona tarif)** | **99 000** (+39 000/qo'shimcha kassa) | Hammasi bitta narxda — virtual kassa, e-faktura, markirovka, davlat hisobotini solishtirish, AI, Telegram bot |
  | REGOS Start | 69 000 + virtual kassa 75 000 = **144 000** | Virtual kassa alohida haq, bizdan ~45 000 qimmat 1-kassali tenant uchun |
  | REGOS Basic/Plus | 149 000 / 299 000 | Bizning yagona tarifdan 50 000–200 000 qimmat |
  | mDokon | 199 000 dan | Bizdan 2x qimmat |
  | HIPPO Base/Medium/Pro | 247 200 / 412 000 / 618 000 | Bizdan 2,5x–6x qimmat |
  | BILLZ Start/Advanced/Pro | 299 000 / 499 000 / 999 000 | Bizdan 3x–10x qimmat |
  | Multikassa/E-POS (hamkor orqali virtual kassa, pilot yo'li) | ~96 000 so'm/kassa (+~335 000 bir martalik) | Bizning pilotdagi virtual kassa xarajati — mijozga ko'rinmaydi, biz to'laymiz (3.3-bo'lim pastda, pilot bosqichi) |

- **Unit-iqtisod** *(2026-10-15: foydalanuvchi qarori bilan yangilandi)*: 1 kassali tenant xarajati — hosting ~20 500 + AI ~2 000–5 000 + SMS (Eskiz, 95 so'm/SMS) ~1 900–4 750 + Click/Payme ~1 000 + fiskal modul (pilot bosqichida hamkor haqi, keyin o'z reyestr yo'lida ~35 000) ≈ **60 000–68 000 so'm/oy** → **marja ≈ 31 000–39 000 so'm** (taxmin, `spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #13). Support xodimi xarajati (~7 mln so'm/oy) dastlabki bosqichda zarar sifatida qabul qilinadi, 300 to'lovchi tenantga yetganda narx qayta ko'riladi (tavsiya #13).
- **Fiskal yo'l (virtual kassa narxining asosi)** *(2026-10-15: foydalanuvchi qarori)*: birinchi kundanoq **o'z virtual kassamizni Davlat reyestriga kiritish arizasi** boshlanadi (VMQ-943, 4-ilova, ~50 ish kuni ≈ 2,5–3 oy); ariza tasdiqlanguncha **pilot (10–20 do'kon)** bitta reyestr hamkori (Multikassa yoki E-POS Communicator) orqali o'tkaziladi, hamkor haqini (≤ ~13 mln so'm, 3 oyga) **biz to'laymiz** — pilot mijozi uchun narx ko'rinmaydi. Pilot uskunasi: mavjud telefon/PC + USB skaner + 58 mm ESC/POS printer (Xprinter XP-58 klassi), ~0,9 mln so'm/kassa; tarozi va Android POS terminal pilotda shart emas. Ommaviy sotuv o'z reyestrimiz tasdiqlangach boshlanadi; agar reyestr 6 oydan ko'p cho'zilsa — hamkor orqali davom etiladi, qo'shimcha narxi ochiq "o'tkaziladigan to'lov" sifatida ko'rsatiladi (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, (b)-bo'lim).
- Raqobatchilar narxi har chorakda qayta tekshiriladi; asosiy xabar: **"Hammasi bitta narxda — hech qanday yashirin qo'shimcha haq yo'q, faqat qo'shimcha kassa alohida"**.

---

## 4. MVP'ga kirish uchun bloklovchi tashqi omillar

Barchasi `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` ("Eng katta 5 texnik xavf (birinchi 90 kun)" bo'limidan):

1. *(2026-10-15: mahsulot qarori bilan yumshatildi — foydalanuvchi qarori)* **Asl belgisi (CRPT Turon) integrator API hujjatlari yopiq** (403 xatosi) — markirovkalangan tovar (suv, ichimlik, tamaki va h.k.) sotuvi birinchi kundanoq bloklanishi xavfi; M01/US-M01-03 shu omilga bog'liq. Endi yo'l xaritasi bor: har bir do'kon o'zining bepul "ishtirokchi" API kalitidan foydalanadi, rad etilsa reyestr hamkori orqali proksi, ikkalasi ham ishlamasa markirovkalangan tovar sotuvi bloklanadi (`02-modullar-talablari.md`, M01). **Rasmiy API kaliti yo'lining tasdig'i hali ochiq** (Xat 2 javobi kutilmoqda).
2. **my.soliq.uz'dan rasmiy dasturiy o'qish yo'li yo'q** — mahsulotning markaziy qiymat taklifi (M10/US-M10-02, davlat hisobotini solishtirish) MVP'da qo'lda/yarim-avtomatik boshlanishiga majbur qiladi, to'liq avtomatlashtirish kechikadi. **Hali ochiq.**
3. *(2026-10-14: qisman hal qilindi)* ~~Virtual kassa reyestriga mustaqil dastur sifatida kiritish narxi/muddati noma'lum~~ — **muddat endi aniq**: VMQ-943 4-ilova bo'yicha reyestrga kiritish jarayoni to'rt bosqichdan iborat — Soliq qo'mitasi qarori 20 ish kuni, Kiberxavfsizlik markazi xulosasi 15 ish kuni, fiskal ma'lumotlar operatori xulosasi 10 ish kuni, texnik tartibga solish agentligi/"O'zeltexsanoat" xulosasi 5 ish kuni (bosqichlar ketma-ket bo'lsa — jami bir necha oy). **Narx qisman aniq**: zaxira mablag' talabi (100/500/1000 BHM) virtual kassaga **tegishli emas**, demak bu qo'shimcha xarajat yo'q. Hali ochiq: bosqichlar ketma-ket yoki parallel borishi, va qolgan tayyorgarlik (hujjatlar) xarajati.
4. **O'RQ-764 (Kiberxavfsizlik to'g'risidagi qonun) sertifikatlash talabining oddiy xususiy SaaS ERP'ga tegishliligi noaniq** — agar "ha" bo'lsa, butun MVP jadvaliga katta ta'sir qiladi. **Hali ochiq.**
5. **E-IMZO'ning rasmiy dasturchi hujjati yo'q** (faqat jamoatchilik GitHub repo) — e-faktura/e-TTN/hisobot imzolash integratsiyasi (M07, M10) kutilganidan ko'proq vaqt olishi mumkin. **Hali ochiq.**

Qo'shimcha (kichikroq, lekin hujjatlashtirish xavfi): *(2026-10-14: hal qilindi)* ~~M10'dagi 5 ish kunlik solishtirish/e'tiroz qoidasining aniq qonun/qaror raqami lex.uz'da topilmadi~~ — endi aniq: Soliq kodeksi 81-moddasi, O'RQ-1108 (2025-12-25), muddat **5 kalendar kun**; qolgan ochiq qism — tuzatishni yuborish protsedurasi/kanali (`02-modullar-talablari.md`, Ochiq savol 8).

---

## 5. Qo'llab-quvvatlash (support) va xavfsizlik testi rejasi *(2026-10-15: foydalanuvchi qarori)*

### 5.1 Support modeli

- **Kanal:** Telegram (mavjud botda "/yordam" buyrug'i) + bitta telefon raqami.
- **Ish vaqti:** ish kunlari 09:00–19:00.
- **Javob muddati (SLA, taxmin):** fiskal/OFD, markirovka va bloklanish muammosi — ish vaqtida **1 soat ichida** birinchi javob; oddiy savol — **24 soat ichida**.
- **Dam olish kunlari:** faqat kritik muammolar (fiskal/OFD, markirovka, bloklanish) uchun Telegram orqali **navbatchi (asoschi), 4 soat ichida** javob — sabab: juma 19:00 dan dushanba 09:00 gacha 62 soat, bu 48 soatlik OFD muddatidan uzun, shuning uchun navbatchiliksiz dam olish kunidagi muammo qonuniy muddatni buzishi mumkin.
- **Manba/ishonch:** kanallar (Telegram+telefon) — BILLZ/mDokon amaliyotiga mos, yuqori ishonch; aniq SLA soat raqamlari — taxmin, pilotda tasdiqlanadi (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #12).

### 5.2 Pentest (xavfsizlik testi) rejasi

- **Pilotdan oldin:** bepul avtomatik skaner (OWASP ZAP) + ichki OAuth/to'lov/fiskal tekshiruv ro'yxati.
- **Ommaviy sotuvdan oldin:** mahalliy firma (Celion yoki ONESEC, Toshkent — ikkalasidan narx so'rab) orqali OWASP ASVS L2 bo'yicha to'liq pentest (veb, API, OAuth, Android).
- **Byudjet rezervi:** ~60 mln so'm (~$5 000), xalqaro oraliqdan (~$1 500–7 000) kelib chiqib (taxmin, ishonch o'rta-past — narx manbasi xalqaro, mahalliy firmalar narxni ochiq bermaydi).
- Keyin tekshiriladi: Celion/ONESEC rasmiy takliflari; ЗРУ-764 bo'yicha majburiy sertifikatlash (csec.uz, Xat 3) bizga tegishli bo'lsa reja o'zgaradi (`spec/tekshiruv/savollar-yakuniy-tavsiyalar.md`, tavsiya #14).

---

## Ochiq savollar

1. Hikoya darajasidagi MoSCoW taqsimoti (1.1-bo'lim) — bu hujjatda loyihalashtirilgan tavsiya, jamoat tadqiqot fayllarida tayyor ustuvorlik jadvali sifatida topilmadi; Arxitektura jamoasi/sprint rejalashtirish bosqichida qayta ko'rib chiqilishi tavsiya etiladi.
2. *(2026-10-15: hal qilindi — foydalanuvchi qarori)* ~~Raqobatchilardan farqlar jadvalidagi "mahalliy support/barqaror narx" qatori (2-bo'lim) uchun aniq SLA/narx siyosati hali belgilanmagan~~ — endi aniq: Telegram+telefon, ish kunlari 09:00–19:00, kritik muammoga 1 soat, oddiyga 24 soat, dam olish kunida kritikka navbatchi 4 soat (5.1-bo'lim). Pilotda aniq raqamlar tasdiqlanishi kerak (taxmin qolib turadi).
3. Barcha biznes o'lchovlari (3.2-bo'lim) "taxmin" — bular MVP ishga tushgandan keyin birinchi pilot davrida haqiqiy ma'lumot bilan to'ldirilishi kerak.
4. *(2026-10-14/15: qisman hal qilindi)* Virtual kassa reyestriga kiritish muddati endi aniq (4-bo'lim, band 3 — VMQ-943 4-ilova), lekin bosqichlar ketma-ket/parallelligi hali ochiq; fiskal yo'l (pilot hamkor + o'z reyestr) va CRPT Turon integratsiya yo'li (API kalit + zahira hamkor) endi mahsulot qarori sifatida aniq (4-bo'lim, band 1; §5), lekin ikkisining ham **rasmiy tasdig'i** (reyestr narxi, CRPT API kalit yo'lining ruxsati) hamon ochiq — bu loyiha jadvaliga ta'sir qiladigan eng muhim meros ochiq savollar.
5. *(2026-10-14: hal qilindi)* M10'dagi 5 kalendar kunlik qoidaning qonun asosi aniq (Soliq kodeksi 81-moddasi, O'RQ-1108, lex.uz/docs/-7944527); tuzatish yuborish yo'li (protsedura/kanal) hali ochiq — Buxgalteriya/Arxitektura jamoasi bilan birga aniqlashtirilishi kerak.
6. Maqsadli kichik do'konlarning qaysi ulushi QQS to'lovchi, qaysi ulushi aylanma solig'i to'lovchi ekani manbada aniqlanmagan (1.1-bo'lim, US-M10-04 izohi) — bu segment nisbati pilot tanlovi va ustuvorlikka ta'sir qiladi.

## Manbalar

- `spec/README.md`
- `spec/01-mahsulot/02-modullar-talablari.md`
- `spec/01-mahsulot/05-ai-funksiyalar.md`
- `research_notes/texnik/00-xulosa-va-ochiq-savollar.md`
- `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`
- `research_notes/texnik/11-raqobatchilar-kamchiliklari.md`
- `research_notes/texnik/01-erp-modullar-va-malumot-modeli.md`
- `research_notes/texnik/02-kassa-ofd-markirovka.md`
- `research_notes/AI ERP startap Ozbekistonda/00_oldingi_hujjat.md`
- `spec/tekshiruv/savollar-yakuniy-tavsiyalar.md` — 2026-10-15, 15 ta foydalanuvchi qarori (yagona tarif, fiskal yo'l, CRPT, support, pentest va h.k.)
