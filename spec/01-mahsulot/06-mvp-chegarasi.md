# MVP chegarasi, raqobatchilardan farq va muvaffaqiyat o'lchovlari

## Asosiy xulosalar

1. **14 modulning (M01-M14) hammasi MVP chegarasida (Must)** — bu `spec/README.md` va `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` (Asosiy xulosa #2) orqali allaqachon qabul qilingan qaror, bu hujjatda o'zgartirilmaydi. Har bir modulda kamida bitta Must-darajali foydalanuvchi hikoyasi bor.
2. **4 ta AI funksiya** (AI-01, AI-03, AI-05, AI-06) MVP ichida, lekin ularning o'zi Must emas — ular deterministik ("kod hisoblaydi") asosiy jarayonning ustiga qo'yilgan tushuntirish/matn qatlami, shuning uchun Should/Could darajasida (`spec/01-mahsulot/05-ai-funksiyalar.md`).
3. **Won't ro'yxati** aniq: kadrlar/ish haqi, CRM/sodiqlik (shu jumladan M03'dagi loyallik bonusi), ishlab chiqarish, boshqa tizimlardan ma'lumot ko'chirish konnektorlari, 7 ta AI funksiya (AI-02, 04, 07-11) — barchasi tadqiqot bilan tasdiqlangan qarorlar (`spec/README.md`, `00-xulosa-va-ochiq-savollar.md`) *(2026-10-14: neytral ifodalandi — koordinator direktivasi)*.
4. Raqobatchilardan eng aniq manbali farq — **AI funksiyasi**: tekshirilgan 9 mahsulotdan faqat 2 tasida (REGOS, Smartup) bor, qolgan 7 tasida rasmiy sahifada AI haqida da'vo yo'q (`research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`, 2-bo'lim).
5. **Muvaffaqiyat o'lchovlarining aksariyati "taxmin"** — mahsulot hali ishga tushmagan, O'zbekiston SaaS bozorida churn/retention/pilot-konversiya bo'yicha ochiq ma'lumot yo'q (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 1.1-bo'lim, 4-band). Faqat offline-sync va fiskal muddatlar kabi **qonuniy majburiy** ko'rsatkichlar (masalan 48 soat) manbali.
6. **Eng katta bloklovchi tashqi omillar** — barchasi tadqiqotning "Eng katta 5 texnik xavf" ro'yxatidan: Asl belgisi integrator API yopiq, my.soliq.uz rasmiy API yo'q, virtual kassa reyestr narxi/muddati noma'lum, ЗРУ-764 sertifikatlash noaniqligi, E-IMZO rasmiy dasturchi hujjati yo'q (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, "Eng katta 5 texnik xavf" bo'limi).
7. MoSCoW'dagi **hikoya darajasidagi** taqsimot (Must/Should/Could) — modul darajasidagi "14 modul MVP" qarorining ichidagi ustuvorlik — bu hujjatda **loyihaviy tavsiya** sifatida berilgan (jamoat tadqiqot fayllarida tayyor shaklda topilmagan), arxitektura/sprint rejalashtirish bosqichida qayta ko'rib chiqilishi mumkin.

---

## 1. MoSCoW taqsimoti

### 1.1 Modullar va foydalanuvchi hikoyalari (US-Mxx-nn)

Barcha 14 modul **Must** (MVP qarori, `spec/README.md`). Quyida har bir modulning hikoyalari (`spec/01-mahsulot/02-modullar-talablari.md`dan) ustuvorlik bo'yicha ajratilgan.

| Modul | Must | Should | Could |
|---|---|---|---|
| M01 Kassa | US-M01-01 (sotuv/chek), US-M01-02 (offline+sync), US-M01-03 (markirovka tekshirish), US-M01-04 (smena/Z-hisobot) | — | — |
| M02 Qaytarish | US-M02-01 (asl chek bo'yicha), US-M02-03 (QQS tuzatish) | US-M02-02 (limit tasdiqlash) | — |
| M03 Chegirma | US-M03-01 (limit ichida chegirma) | US-M03-02 (avtomatik qoida) | US-M03-03 (margin hisoboti) |
| M04 Ombor qoldig'i | US-M04-01 (kirim balans) | US-M04-02 (past qoldiq ogohlantirish), US-M04-03 (ko'p filial konsolidatsiya) | — |
| M05 Inventarizatsiya | US-M05-01 (sanash), US-M05-02 (farq tasdiqlash), US-M05-03 (buxgalteriya yozuvi) | — | — |
| M06 Ko'chirish | US-M06-01 (yuborish), US-M06-02 (qabul tasdiqlash) | US-M06-03 (tarix/72 soat kuzatuv) | — |
| M07 Xarid | US-M07-01 (xaridnoma), US-M07-02 (qabul), US-M07-03 (e-faktura+QQS), US-M07-04 (yetkazib beruvchiga to'lov) | — | — |
| M08 Nasiya / Qarz daftari | US-M08-01 (limitli sotuv), US-M08-02 (kredit limiti, ixtiyoriy), US-M08-04 (qarz to'lovi), **US-M08-05 (tez qarz yozish, offline), US-M08-06 (mijoz daftari), US-M08-07 (eski daftarni ko'chirish), US-M08-09 (va'da sanasi va eslatma), US-M08-10 (qarzlar hisoboti), US-M08-11 (yetkazib beruvchiga qarz)** *(2026-10-14)* | US-M08-03 (AI eslatma, AI-06ga bog'liq), US-M08-08 (mijozga SMS/Telegram — SMS narxi va provayder aniqlanishi kerak) | — |
| M09 Narxlar | US-M09-01 (narx+tarix), US-M09-03 (kassada ko'rish) | US-M09-02 (katta o'zgarish tasdiqlash), US-M09-04 (yorliq chop etish), US-M09-05 (ichki shtrix-kod), US-M09-06 (tarozi shtrix-kodi) *(2026-10-14)* | — |
| M10 QQS | US-M10-01 (avtomatik QQS), US-M10-02 (davlat hisobotini solishtirish, 5 kun), US-M10-04 (aylanma solig'i solishtirish) | US-M10-03 (qizil faktura kuzatuv) | — |
| M11 Buxgalteriya | US-M11-01 (avtomatik provodka), US-M11-02 (oy yakuni) | US-M11-03 (sodda dashboard) | — |
| M12 Hisobotlar | US-M12-01 (kunlik savdo), US-M12-03 (QQS solishtirish eksport) | US-M12-02 (eng ko'p/kam sotilgan) | — |
| M13 Huquqlar | US-M13-01 (xodim+rol), US-M13-02 (bir necha rol birlashuvi) | US-M13-03 (limit sozlash) | — |
| M14 Filiallar | US-M14-03 (yangi filial qo'shish) | US-M14-01 (konsolidatsiya) | US-M14-02 (narx/chegirma nusxalash) |
| M15 Xarajatlar *(2026-10-14)* | US-M15-01 (xarajat yozish), US-M15-03 (sof foyda) | US-M15-02 (takrorlanuvchi xarajat) | — |
| M16 Kassa pul harakati *(2026-10-14)* | US-M16-01 (qo'yish/olish), US-M16-02 (smena sanash va farq), US-M16-03 (tarix) | — | — |
| M17 Obuna va ro'yxatdan o'tish *(2026-10-14)* | US-M17-01 (ro'yxatdan o'tish + sinov), US-M17-02 (tarif va to'lov), US-M17-03 (kechikkan to'lov siyosati), US-M17-04 (ichki admin) | — | — |
| M18 Bildirishnomalar / Telegram bot *(2026-10-14)* | US-M18-01 (ulash), US-M18-02 (kunlik hisobot) | US-M18-03 (ogohlantirishlar) | US-M18-04 (botda AI savol) |

*Izoh: bu jadvaldagi Should/Could ajratmasi modulning MVP'da bo'lish-bo'lmasligiga ta'sir qilmaydi (hammasi MVP ichida) — faqat qaysi hikoya birinchi, qaysi biri ikkinchi navbatda qurilishini ko'rsatadi. Qabul mezoni ("Must ro'yxati 14 modulni qoplaydi") bajarilgan — jadvaldagi har bir modulda kamida bitta Must band bor.*

*US-M10-04 (aylanma solig'i solishtirish) va US-M07-04 (yetkazib beruvchiga to'lov) Must'ga ko'tarildi (dastlabki loyihada Should edi): (a) aylanma solig'i — maqsadli kichik do'konlarning qaysi ulushi QQS to'lovchi, qaysi ulushi aylanma solig'i to'lovchi ekani manbada aniqlanmagan (**taxmin/ochiq savol** — pastda), shuning uchun ikkisini ham Must deb olish xavfsizroq, aks holda aylanma solig'i to'lovchi mijozlar uchun markaziy qiymat taklifi ishlamay qoladi; (b) yetkazib beruvchiga to'lov — US-M10-03 (qizil faktura QQS krediti to'lovdan keyin) va US-M11-02 (oy yopish, Must) to'g'ridan-to'g'ri shu to'lov holatiga bog'liq, to'lovsiz bu ikkisi to'liq ishlay olmaydi.*

### 1.2 AI funksiyalar (AI-nn)

`spec/01-mahsulot/05-ai-funksiyalar.md`dagi "Hukm" ustuniga asoslanib (MVP → Should/Could, Keyingi bosqich/Hozircha real emas → Won't):

| AI ID | Funksiya | MoSCoW | Sabab |
|---|---|---|---|
| AI-01 | Umumiy biznes savol-javob chat | **Should** | Qimmatli farqlovchi, lekin asosiy savdo/ombor/soliq jarayoni AI'siz ham ishlaydi (`05-ai-funksiyalar.md`, AI-01) |
| AI-05 | Davlat hisoboti tafovutini tushuntirish | **Should** | Markaziy oqim (M10/US-M10-02) kod darajasida Must; AI-05 shu natijaning ustiga qo'yilgan tabiiy-til tushuntirish qatlami — hal qiluvchi funksiya emas, qo'shimcha qiymat (`05-ai-funksiyalar.md`, AI-05) |
| AI-03 | Qog'oz hujjat OCR (pilot bilan, torroq qamrov) | **Could** | Qamrov tor (faqat qog'oz/texnik uzilish holatlari), kirill-lotin aralash aniqlik tasdiqlanmagan, pilot talab qiladi (`05-ai-funksiyalar.md`, AI-03, Chegaralar) |
| AI-06 | Nasiya eslatma matni | **Could** | Qiymatli, lekin M08 (nasiya) asosiy funksiyasi (limit, qarz yozish) AI'siz ham to'liq ishlaydi; AI faqat matn yozadi (`05-ai-funksiyalar.md`, AI-06) |
| AI-02, 04, 07, 08, 09, 10, 11 | STT, qo'lyozma OCR, anomaliya, bank kategoriyalash, talab bashorati, narx optimallashtirish, TTS brifing | **Won't** | Barchasi `05-ai-funksiyalar.md`da "Keyingi bosqich" yoki "Hozircha real emas" deb manbali asoslangan |

### 1.3 Won't ro'yxati (MVP'dan tashqarida)

| Band | Sabab/manba |
|---|---|
| Kadrlar/ish haqi moduli | MVP 14 modul ro'yxatida yo'q (`spec/README.md`); JShDS/ijtimoiy soliq hisobotini solishtirish shu sababli ham MVP'dan tashqari (`02-modullar-talablari.md`, M10 qamrov eslatmasi) |
| CRM/sodiqlik (mijozlar bazasi, loyallik/bonus karta dasturi) | `00-xulosa-va-ochiq-savollar.md`, Asosiy xulosa #2; M03'dagi loyallik bonusi ham shu sababli olib tashlangan (`02-modullar-talablari.md`, M03) |
| Ishlab chiqarish (retsept, ishlab chiqarish buyurtmasi) | `00-xulosa-va-ochiq-savollar.md`, Asosiy xulosa #2 |
| Boshqa tizimlardan ma'lumot ko'chirish konnektorlari | MVP'dan tashqarida — AIOS noldan (from-scratch) qurilgan, mustaqil mahsulot; hech qanday tashqi buxgalteriya/ERP tizimi bilan integratsiya, migratsiya, import, eksport yoki sinxronizatsiya qilinmaydi va ular hech qachon ma'lumot manbai bo'lmaydi; mavjud tizimlar faqat ma'lumotlar modelini loyihalashda **struktura namunasi/benchmark** sifatida ishlatilgan (`01-erp-modullar-va-malumot-modeli.md`, 7-band; `spec/README.md`). Boshlang'ich ma'lumot kiritish (onboarding) faqat uch yo'l bilan: (1) qo'lda kiritish, (2) Excel/CSV shablon orqali import, (3) AI-03 yordamida qog'oz hujjat/fotosidan kiritish *(2026-10-14: aniqlashtirildi — koordinator direktivasi, `07-tuzatishlar-va-yechimlar.md`)* |
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
| Oylik obuna narxi (tariflar) | **Qaror (foydalanuvchi, 2026-10-14): O'zbekiston bozoridagi raqobatchilardan sezilarli arzon** — mijozlar ishlashi yaxshi va arzonrog'ini tanlaydi. Eski variantlar (149k/349k/699k va 69k–999k) bekor. **Taklif (raqamlar tasdiqlanishi kerak):** Start **49 000**, Biznes **129 000**, Pro **249 000 so'm/oy** (bir savdo nuqtasi uchun), yillik to'lovda −20%. Virtual kassa ichida (alohida haq yo'q). Batafsil — 3.3-bo'lim | Raqobatchilar narxi: `research_notes/texnik/06-raqobatchilar-texnik-va-uskunalar.md`, 1-bo'lim jadvali |
| To'lovga tayyorlik (oyiga qancha so'm) | **Taxmin** — manbada yo'q | "20-30 ta do'kon egasi bilan suhbat kerak" (`research_notes/texnik/00-xulosa-va-ochiq-savollar.md`, 1.1-bo'lim, 2-band) |
| NPS/mijoz mamnuniyati | **Taxmin** — manbada yo'q | Pilot davrida belgilanishi kerak |


### 3.3 Tariflar taklifi (2026-10-14)

**Tamoyil:** har bir pog'ona raqobatchilarning shunga o'xshash paketidan arzon bo'ladi va soliq integratsiyasi (virtual kassa) narxga kiradi — raqobatchilarda u ko'pincha alohida haq (masalan REGOS +75 000 so'm/oy). Buxgalteriya to'g'riligi (FIFO/AVECO, QQS) tarifga bog'lanmaydi.

| Tarif | Narx (so'm/oy, 1 nuqta) | Kimga | Ichida | Raqobatchilar (rasmiy sahifalar, 2026) |
|---|---|---|---|---|
| **Start** | **49 000** | Kichik do'kon, 1 kassa | Kassa + virtual kassa (OFD), ombor, nasiya, Excel import, AI asosiy (oylik limit bilan) | REGOS Start 69 000 + virtual kassa 75 000 = 144 000; mDokon 199 000 dan; HIPPO Base 247 200; BILLZ Start 299 000 |
| **Biznes** | **129 000** | 2–3 kassali do'kon, kichik ulgurji | + e-faktura, markirovka (Asl belgisi), davlat hisobotini solishtirish (QQS, aylanma), 3 kassagacha | REGOS Basic 149 000 / Plus 299 000; HIPPO Medium 412 000; BILLZ Advanced 499 000 |
| **Pro** | **249 000** | Katta do'kon, tarmoq, ulgurji | + cheksiz kassa, filiallar, to'liq buxgalteriya (NSBU 21), kengaytirilgan AI, API | HIPPO Pro 618 000; REGOS Pro 859 000; BILLZ Pro 999 000 |

- Yillik to'lov: −20%. Sinov muddati: 30 kun bepul (bepul doimiy tarif — MoySklad'da bor — alohida qaror: OFD/hosting xarajati sababli hozircha taklif qilinmaydi).
- **Shart:** raqamlar **unit-iqtisod hisobi** bilan tasdiqlanishi kerak — bir mijozga oylik xarajat (hosting, AI tokenlar, OFD/EDO operator haqlari bo'lsa, qo'llab-quvvatlash) Start narxidan past bo'lishi shart. Bu hisob hali yo'q (`spec/08-kamchiliklar-tahlili.md`).
- Raqobatchilar narxi har chorakda qayta tekshiriladi; asosiy xabar: "Hammasi bitta tizimda va arzonroq".

---

## 4. MVP'ga kirish uchun bloklovchi tashqi omillar

Barchasi `research_notes/texnik/00-xulosa-va-ochiq-savollar.md` ("Eng katta 5 texnik xavf (birinchi 90 kun)" bo'limidan):

1. **Asl belgisi (CRPT Turon) integrator API hujjatlari yopiq** (403 xatosi) — markirovkalangan tovar (suv, ichimlik, tamaki va h.k.) sotuvi birinchi kundanoq bloklanishi xavfi; M01/US-M01-03 shu omilga bog'liq. **Hali ochiq.**
2. **my.soliq.uz'dan rasmiy dasturiy o'qish yo'li yo'q** — mahsulotning markaziy qiymat taklifi (M10/US-M10-02, davlat hisobotini solishtirish) MVP'da qo'lda/yarim-avtomatik boshlanishiga majbur qiladi, to'liq avtomatlashtirish kechikadi. **Hali ochiq.**
3. *(2026-10-14: qisman hal qilindi)* ~~Virtual kassa reyestriga mustaqil dastur sifatida kiritish narxi/muddati noma'lum~~ — **muddat endi aniq**: VMQ-943 4-ilova bo'yicha reyestrga kiritish jarayoni to'rt bosqichdan iborat — Soliq qo'mitasi qarori 20 ish kuni, Kiberxavfsizlik markazi xulosasi 15 ish kuni, fiskal ma'lumotlar operatori xulosasi 10 ish kuni, texnik tartibga solish agentligi/"O'zeltexsanoat" xulosasi 5 ish kuni (bosqichlar ketma-ket bo'lsa — jami bir necha oy). **Narx qisman aniq**: zaxira mablag' talabi (100/500/1000 BHM) virtual kassaga **tegishli emas**, demak bu qo'shimcha xarajat yo'q. Hali ochiq: bosqichlar ketma-ket yoki parallel borishi, va qolgan tayyorgarlik (hujjatlar) xarajati.
4. **O'RQ-764 (Kiberxavfsizlik to'g'risidagi qonun) sertifikatlash talabining oddiy xususiy SaaS ERP'ga tegishliligi noaniq** — agar "ha" bo'lsa, butun MVP jadvaliga katta ta'sir qiladi. **Hali ochiq.**
5. **E-IMZO'ning rasmiy dasturchi hujjati yo'q** (faqat jamoatchilik GitHub repo) — e-faktura/e-TTN/hisobot imzolash integratsiyasi (M07, M10) kutilganidan ko'proq vaqt olishi mumkin. **Hali ochiq.**

Qo'shimcha (kichikroq, lekin hujjatlashtirish xavfi): *(2026-10-14: hal qilindi)* ~~M10'dagi 5 ish kunlik solishtirish/e'tiroz qoidasining aniq qonun/qaror raqami lex.uz'da topilmadi~~ — endi aniq: Soliq kodeksi 81-moddasi, O'RQ-1108 (2025-12-25), muddat **5 kalendar kun**; qolgan ochiq qism — tuzatishni yuborish protsedurasi/kanali (`02-modullar-talablari.md`, Ochiq savol 8).

---

## Ochiq savollar

1. Hikoya darajasidagi MoSCoW taqsimoti (1.1-bo'lim) — bu hujjatda loyihalashtirilgan tavsiya, jamoat tadqiqot fayllarida tayyor ustuvorlik jadvali sifatida topilmadi; Arxitektura jamoasi/sprint rejalashtirish bosqichida qayta ko'rib chiqilishi tavsiya etiladi.
2. Raqobatchilardan farqlar jadvalidagi "mahalliy support/barqaror narx" qatori (2-bo'lim) uchun aniq SLA/narx siyosati hali belgilanmagan.
3. Barcha biznes o'lchovlari (3.2-bo'lim) "taxmin" — bular MVP ishga tushgandan keyin birinchi pilot davrida haqiqiy ma'lumot bilan to'ldirilishi kerak.
4. *(2026-10-14: qisman hal qilindi)* Virtual kassa reyestriga kiritish muddati endi aniq (4-bo'lim, band 3 — VMQ-943 4-ilova), lekin bosqichlar ketma-ket/parallelligi hali ochiq; CRPT Turon integrator shartlari (band 1) hamon ochiq — bu ikkisi loyiha jadvaliga ta'sir qiladigan eng muhim meros ochiq savollar.
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
