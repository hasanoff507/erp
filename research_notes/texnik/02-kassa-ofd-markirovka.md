# Onlayn/virtual kassa (OFD, fiskal modul, reyestr) va Asl belgisi markirovka — texnik talablar

*Tadqiqot sanasi: 2026-10-10. Tadqiqotchi: Fiskal (team worker).*

## Asosiy xulosalar

1. Onlayn-NKM/virtual kassa majburiyligining huquqiy asosi — VMning 2019-11-23 943-son qarori (pilot: 2019-02-21 150-son qaror, Toshkent). O'zbekistonda **bitta davlat OFD operatori** bor — Soliq qo'mitasi qaramog'idagi "Yangi texnologiyalar" ilmiy-axborot markazi DUK; Rossiyadagi kabi ko'plab raqobatdosh OFD kompaniyalari yo'q. UZKASSA, E-POS, REGOS VCR, Rahmat POS kabi nomlar — OFD emas, balki Davlat reyestriga kiritilgan virtual kassa **dastur/uskuna vendorlari**.
2. Dasturiy kassani Davlat reyestriga kiritish uchun 10 ta hujjat turi aniqlangan (muvofiqlik sertifikati, Kiberxavfsizlik markazi xulosasi, fiskal operator xulosasi va boshqalar). *Tuzatish (arxitektor tekshiruvidan so'ng): avval yozilgan "15 kun" muddati ikkilamchi manbadan edi va noto'g'ri chiqdi — 943-son qarorning asl matnida (16–18-bandlar) **faqat tadbirkorning o'z qurilmasini foydalanish uchun ro'yxatga oldirish jarayoni** uchun "4 ish soati" (dastlabki qayd) + "8 ish soati" (ko'rib chiqish) muddati bor; **dastur ishlab chiquvchining mahsulotini Davlat reyestriga kiritish/sertifikatlash muddati asosiy qonun matnida alohida band sifatida topilmadi** — bu haligacha ochiq savol.* **Aniq narx (so'mda) ham ochiq manbada topilmadi** — bu bozor hujjatidagi eng muhim ochiq savol hamon ochiq qolmoqda.
3. Fiskal modul (FM) milliy standartlarga (O'zDST 1106:2009, O'zDST 1092:2009) va xalqaro kripto algoritmlarga (3DES, AES, RSA, SHA) mos kripto-himoyalangan qurilma; offlayn rejimda shakllangan birinchi chek **48 soat ichida** OFD'ga yuborilishi kerak — bu endi 943-son qarorning 1-ilovasi, 31-bandi bilan birlamchi manbadan tasdiqlangan.
4. Asl belgisi — CRPT Turon operatori boshqaradi; alkogol/tamaki (2021), maishiy texnika/dori (2022), suv/ichimlik (2024-03-01 sotuvda, 2026-04-01 ishlab chiqaruvchilar uchun hisob-fakturada majburiy) bosqichma-bosqich joriy etilgan. 2026-01-23dagi yangi 23-son qaror bilan 2026-07-01dan elektron hisob-fakturada markirovka kodini avtomatik tekshirish va kassada avtomatik kiritish majburiy qilindi, tovar ko'chirish muddati 72 soatdan oshmasligi belgilandi.
5. Asl belgisi uchun rasmiy, ochiq API texnik hujjatlari ushbu tadqiqot davomida topilmadi — yordam portali (help.crpt-turon.uz) ba'zi sahifalari ochiq, lekin integratorlar uchun to'liq texnik spetsifikatsiya qismi kirish cheklovi (403) bilan yopiq chiqdi.
6. "Ruxsat etilgan fiskal printer/Android POS terminal modellari"ning yagona statik ro'yxati (jadval) ochiq manbada topilmadi — bu Davlat reyestrining o'zi (dinamik veb-sahifa) orqali yuritiladi; bozorda PAX A930 (Android/PayDroid), UZKASSA qurilmalari, Rahmat POS kabi takliflar bor.

---

## 1) Onlayn-NKM / virtual kassa: qonunchilik, fiskal modul, OFD, chek, offlayn rejim

### Huquqiy asos
- **VM qarori No. 150 (2019-02-21)** — "Toshkent shahrida onlayn nazorat-kassa mashinalarini qo'llash bo'yicha tajriba loyihasini amalga oshirish chora-tadbirlari to'g'risida" — pilot bosqich. ([lex.uz/docs/4210424](https://lex.uz/docs/4210424) va [lex.uz/docs/4210436](https://lex.uz/docs/4210436))
- **VM qarori No. 943 (2019-11-23)** — "Onlayn nazorat-kassa mashinalari va virtual kassa tizimi qo'llanilishini ta'minlash chora-tadbirlari to'g'risida" — asosiy, hozir ham amaldagi hujjat. Uchta ilova:
  - 1-ilova: Aholi bilan pulli hisob-kitoblarda onlayn-NKM va virtual kassa tizimini qo'llash tartibi to'g'risida Nizom.
  - 2-ilova: Onlayn-NKM, virtual kassa va fiskal modulga qo'yiladigan Texnik talablar.
  - 3-ilova: Texnik xizmat ko'rsatish markazlarining Davlat reyestrini yuritish va ularga qo'yiladigan talablar.
  ([lex.uz/docs/4603329](https://lex.uz/docs/4603329); 2026-01-23dagi holatga ONDATE bilan amaldagi versiya: [lex.uz/en/docs/4603329?ONDATE=23.01.2026](https://lex.uz/en/docs/4603329?ONDATE=23.01.2026))
- Rasmiy loyihaviy/tahliliy versiya: [regulation.gov.uz/oz/document/8344](https://regulation.gov.uz/oz/document/8344).
- Alohida ilovalarning matni: [buxgalter.uz — 2-ilova (texnik talablar)](https://buxgalter.uz/uz/doc?id=606697_o%E2%80%98zbekiston_respublikasi_hududida_qo%E2%80%98llanilishi_ruhsat_etilgan_onlayn_nazorat-kassa_mashinalari_virtual_kassa_va_fiskal_modulga_qo%E2%80%98yiladigan_tehnik_talablar), [kadrovik.uz — 1-ilova (Nizom)](https://kadrovik.uz/en/doc?id=606743_aholi_bilan_pulli_hisob-kitoblarni_amalga_oshirishda_onlayn_nazorat-kassa_mashinalari_va_virtual_kassa_tizimini_qo%E2%80%98llash_tartibi_to%E2%80%98g%E2%80%98risida_nizom), [nrm.uz — 3-ilova (texnik xizmat markazlari)](https://nrm.uz/contentf?doc=606706_onlayn_nazorat-kassa_mashinalari_virtual_kassa_va_fiskal_modulga_tehnik_hizmat_ko%E2%80%98rsatish_markazlarining_davlat_reestrini_yuritish_hamda_ularga_qo%E2%80%98yiladigan_alohida_talablar).
- Umumiy sharh (kimlar uchun majburiy, jarimalar mavjudligi): kassasiz savdo yoki ro'yxatdan o'tmagan uskuna/dastur ishlatish uchun javobgarlik ko'zda tutilgan, lekin ushbu tadqiqotda aniq jarima summasi topilmadi ([azma.uz sharhi](https://azma.uz/tpost/u1lyuxv711-onlain-kassi-v-uzbekistane-komu-obyazate)).

### Fiskal modul (FM) qanday ishlaydi
- FM — OFD tomonidan ishlab chiqilgan, himoyalangan dasturiy ta'minotga ega maxsus qurilma; milliy standartlar asosida fiskal ma'lumotlarni kriptografik himoya qiladi ([regos.uz tushuntirishi](https://regos.uz/ru/blog/polezno-znat/chto-takoe-fiskalnyj-modul-pofm)).
- Qarorning 2-ilovasiga (nrm.uz) ko'ra, FM aqlli karta T=0 va T=1 aloqa protokollarini hamda quyidagi kripto-algoritmlarni qo'llab-quvvatlashi kerak: **O'zDST 1106:2009, O'zDST 1092:2009, 3DES, AES, RSA, SHA-1, SHA-224, SHA-256** ([nrm.uz — Texnik talablar matni](https://nrm.uz/contentf?doc=579928_tehnicheskie_trebovaniya_k_fiskalnomu_modulyu)). *Eslatma: hujjatning to'liq matnida chek rekvizitlari va OFD aloqa protokoli bo'yicha batafsil texnik bandlar ushbu tadqiqotda to'liq ajratib olinmadi — faqat kripto/raqamlash qismi tasdiqlandi.*
- Onlayn-NKM va virtual kassa FM bilan o'zaro ishlaydi: FM chekni shifrlaydi, elektron raqamli imzo bilan tasdiqlaydi va OFD serveriga xavfsiz yuboradi.
- FM o'z xotira resursiga ega; yuborilmagan cheklar soni (xato kodi 704031) va Z-hisobotlar soni (xato kodi 704032) tizim tomonidan kuzatiladi; Z-hisobot smena yakunida operator tomonidan qo'lda yopilishi kerak ([regos.uz](https://regos.uz/ru/blog/polezno-znat/chto-takoe-fiskalnyj-modul-pofm)).

### OFD operatorlari
- O'zbekistonda **yagona davlat OFD operatori** mavjud: **"Yangi texnologiyalar" ilmiy-axborot markazi DUK**, Soliq qo'mitasi qaramog'ida; onlayn rejimda fiskal ma'lumotlarni mustaqil qabul qiladi, qayta ishlaydi, kriptografik himoya qiladi va saqlaydi ([soliq.uz — tashkilot sahifasi](https://soliq.uz/about/subordinate-organizations/gup-nauchno-informacionnyj-centr-yangi-tehnologiyalar)).
- Oldingi tadqiqot qaydlarida "UZKASSA, e-POS, QPos — OFD operatorlari" deb yozilgan edi — bu **noto'g'ri/aniqlashtirishga muhtoj**: ushbu kompaniyalar aslida Davlat reyestriga kiritilgan virtual kassa dasturi/uskunasi yetkazib beruvchilari, ular yagona davlat OFD orqali ishlaydi, o'zlari alohida OFD emas ([soliq.uz tashkilot sahifasi](https://soliq.uz/about/subordinate-organizations/gup-nauchno-informacionnyj-centr-yangi-tehnologiyalar) + bozor manbalarining o'zaro solishtirilishi). Rossiyadagi kabi raqobatdosh ko'p-OFD modeli O'zbekistonda tasdiqlanmadi.

### Chek formati va majburiy rekvizitlar
- Chekda **fiskal belgi va QR-kod** bo'lishi shart (marketpleys/bank ilovalari ham shu talabga bo'ysunadi; mijoz to'liq yoki soddalashtirilgan ko'rinishni tanlashi mumkin, 2026-yildagi yangilanish) ([buxgalter.uz — chek haqida](https://buxgalter.uz/uz/publish/doc/text188570_nima_uchun_chek_soliqqa_doir_ahborotni_uz_ichiga_olmasligi_mumkin)).
- Chekdagi tovar (xizmat) nomi, miqdori va narxi haqiqiy ma'lumotga mos kelishi, **MXIK (IKPU) kodi va o'lchov birligi** tasnif.soliq.uz'dagi joriy versiyaga mos bo'lishi shart — MXIK onlayn-kassa chekining majburiy rekvizitidir ([buxgalter.uz — MXIK qidirish](https://buxgalter.uz/uz/publish/doc/text191011_tasnif_soliq_uz_saytida_tugri_mhik_qanday_topiladi)). **MXIK kod uzunligi — 17 raqam, tasdiqlandi** (bir nechta mustaqil manbada izchil tasnif bilan: 2–3-pozitsiya tovar guruhi, 4–5 sinf, 6–8 pozitsiya, 9–11 subpozitsiya, 12–14 brend, 15–17 atribut) ([azma.uz — IKPU/MXIK kodlari](https://azma.uz/tpost/ikpu-mxik-kodlari-ozbekiston), [moysklad.uz — IKPU kodlari](https://www.moysklad.uz/uz/poleznoe/shkola-torgovli/kody-ikpu/)). *Eslatma: bu tasnif.soliq.uz'ning tasnif tuzilishi, qonun matni emas — lekin manbalar o'zaro mos keladi.*
- Rasmiy chek namunasi va rekvizitlar ro'yxatining to'liq matni soliq.uz'ning tegishli sahifasida ([gov.uz/oz/soliq/page/onlayn-nkm](https://www.gov.uz/oz/soliq/page/onlayn-nkm) — sahifa mavjud, lekin WebFetch orqali to'liq matn (faqat bo'lim sarlavhalari) olindi; aniq rekvizitlar jadvali sahifani to'g'ridan-to'g'ri brauzerda ochib tekshirishni talab qiladi).

### Chekni yuborish protokoli/API
- Rasmiy, ochiq "OFD API spetsifikatsiyasi" hujjati (Rossiyadagi ofd.ru/razrabotchikam/ofd kabi ochiq texnik API hujjati) O'zbekiston uchun ochiq manbalarda **topilmadi**. Virtual kassa ishlab chiquvchilari integratsiya uchun to'g'ridan-to'g'ri "Yangi texnologiyalar" DUK (fiskal ma'lumotlar operatori) bilan integratsiya shartnomasi asosida ishlashadi ([buxgalter.uz — integratsiya talablari](https://buxgalter.uz/uz/publish/doc/text195345_avtomatlashtirish_dasturlarini_soliq_organlarining_ahborot_tizimlari_bilan_integraciya_qilish_talablari)).
- Uchinchi tomon tizimlar (REGOS VCR, Rahmat POS, E-POS) o'z API/SDK'lari orqali fiskalizatsiyani "qora quti" sifatida taqdim etadi; ularning ichki OFD protokoli ochiq hujjatlashtirilmagan.

### Offlayn rejim talablari
- Internet aloqasi bo'lmaganda chek offlayn shakllantirish mumkin. **Tasdiqlandi (birlamchi manba):** 943-son qarorning **1-ilovasi, 31-band**i — "birinchi offlayn rejimda shakllangan chekni 48 soat ichida operatorga uzatilishi ta'minlanishi zarur" ([lex.uz/docs/4603329](https://lex.uz/docs/4603329), 1-ilova, 31-band). Demak, **48 soat** muddati 2-ilovada (texnik talablar) emas, balki 1-ilovada (qo'llash tartibi to'g'risidagi Nizom) belgilangan ekan — ilgari bu band 2-ilovada izlangan va topilmagan edi, aslida 1-ilovada bor ekan. REGOS blogidagi ikkilamchi ta'rif ([regos.uz](https://regos.uz/ru/blog/polezno-znat/chto-takoe-fiskalnyj-modul-pofm)) shu bilan mos keladi va endi birlamchi manba bilan tasdiqlangan.

---

## 2) Dasturiy kassani Davlat reyestriga kiritish — organ, hujjatlar, muddat, narx

**Bu bozor hujjatidagi eng muhim ochiq savol edi. Quyida topilgan va topilmagan narsalar aniq ko'rsatilgan.**

### Mas'ul organ
- **O'zbekiston Respublikasi Davlat soliq qo'mitasi** — virtual kassa dasturlarini Davlat reyestriga kiritadi va reyestrni yuritadi. Reyestr ro'yxati rasman shu yerda e'lon qilinadi: [soliq.uz/page/virtual-kassa-reestri](https://soliq.uz/page/virtual-kassa-reestri?lang=uz) (301 redirekt orqali yangi manzilga yo'naltiriladi: [www.gov.uz/oz/soliq/page/virtual-kassa-reestri](https://www.gov.uz/oz/soliq/page/virtual-kassa-reestri?lang=uz)).
- Texnik xizmat ko'rsatish markazlari uchun alohida Davlat reyestri ham yuritiladi (943-son qarorning 3-ilovasi) ([nrm.uz](https://nrm.uz/contentf?doc=606706_onlayn_nazorat-kassa_mashinalari_virtual_kassa_va_fiskal_modulga_tehnik_hizmat_ko%E2%80%98rsatish_markazlarining_davlat_reestrini_yuritish)).

### Kerakli hujjatlar (10 ta band)
Manba: [buxgalter.uz — "Avtomatlashtirish dasturlarini soliq organlarining axborot tizimlari bilan integratsiya qilish talablari"](https://buxgalter.uz/uz/publish/doc/text195345_avtomatlashtirish_dasturlarini_soliq_organlarining_ahborot_tizimlari_bilan_integraciya_qilish_talablari):
1. Dasturning qolip (demo) namunasi
2. Muvofiqlik sertifikati (akkreditlangan sertifikatlash organi tomonidan berilgan)
3. Davlat reyestriga kiritish uchun ariza
4. Shakllantirilgan chek namunasi
5. Dasturning texnik pasporti
6. Foydalanish bo'yicha hujjatlar (qo'llanma)
7. Kafolat xati (ehtiyot qismlar/texnik xizmat bo'yicha)
8. "Kiberxavfsizlik markazi" DUKning xulosasi
9. Fiskal ma'lumotlar operatorining ("Yangi texnologiyalar" DUK) integratsiya xulosasi
10. Mualliflik huquqini tasdiqlovchi hujjat (patent/guvohnoma)

### Jarayon (manbalar sinteziga asoslangan rekonstruksiya)
1. Dastur ishlab chiquvchi fiskal ma'lumotlar operatoriga ("Yangi texnologiyalar" DUK) integratsiya qilish to'g'risida ariza bilan murojaat qiladi.
2. Sinov integratsiyasi amalga oshiriladi; operator xulosa beradi.
3. "Kiberxavfsizlik markazi" DUKdan axborot xavfsizligi bo'yicha xulosa olinadi.
4. Muvofiqlik sertifikati akkreditlangan sertifikatlash organidan olinadi.
5. To'liq hujjatlar to'plami bilan Soliq qo'mitasiga Davlat reyestriga kiritish uchun ariza beriladi.
([buxgalter.uz, yuqoridagi manba](https://buxgalter.uz/uz/publish/doc/text195345_avtomatlashtirish_dasturlarini_soliq_organlarining_ahborot_tizimlari_bilan_integraciya_qilish_talablari))

### Muddat
- **Tuzatilgan ma'lumot (asl 943-son qaror matni, lex.uz/docs/4603329, 16–18-bandlar asosida):** Qarorda **ikki xil jarayon** bor va ularni aralashtirib yubormaslik kerak:
  - **(A) Tadbirkorning o'z onlayn-NKM/virtual kassasini foydalanish uchun ro'yxatga oldirishi** — texnik xizmat ko'rsatish markazi (ТХКМ) orqali ariza topshirilgach, ma'lumotlar **"4 iш соати ичида"** (4 ish soati ichida) maxsus axborot tizimida qayd etiladi, so'ng soliq organi **"саккиз иш соати ичида"** (8 ish soati ichida) ko'rib chiqadi va qabul qiladi — jami ~12 ish soati ([lex.uz/docs/4603329](https://lex.uz/docs/4603329), 16–18-bandlar).
  - **(B) Dastur ishlab chiquvchining o'z mahsulotini Davlat reyestriga kiritishi (sertifikatlash)** — bu asosiy qonun matnida (A) jarayonidan alohida, aniq muddat bilan ko'rsatilmagan. Oldingi versiyada yozilgan "15 kun" raqami ikkinchi darajali (ikkilamchi) veb-manbadan olingan edi va 943-son qarorning asl matnida **topilmadi** — shuning uchun olib tashlandi. (B) jarayon uchun aniq muddat hamon **ochiq savol**.

### Narx
- Soliq qo'mitasi tomonidan taqdim etiladigan **asosiy (bazaviy) dasturiy komponent biznes subyektlariga bepul** beriladi (ro'yxatdan o'tish jarayonining o'zi ham "bepul" deb tavsiflangan — ariza berish, reyestrdan qurilma tanlash, texnik xizmat markazi bilan shartnoma, soliq organida ro'yxatdan o'tish) ([azma.uz sharhi](https://azma.uz/tpost/u1lyuxv711-onlain-kassi-v-uzbekistane-komu-obyazate)).
- Biroq **mustaqil dasturiy mahsulot** (startap o'z virtual kassa funksiyasini qo'shmoqchi bo'lsa) uchun sertifikatlash organi xizmati, Kiberxavfsizlik markazi ekspertizasi va fiskal operator bilan integratsiya ehtimol pullik bo'lishi mumkin — **aniq narx (so'mda) ochiq ommaviy manbalarda topilmadi**. Bu hali ham ochiq savol bo'lib qolmoqda; aniqlashtirish uchun "Yangi texnologiyalar" DUK yoki akkreditlangan sertifikatlash organlariga to'g'ridan-to'g'ri so'rov yuborish kerak bo'ladi.

### Reyestrdagi mavjud dasturlar namunalari
Reyestr ro'yxatining o'zi soliq.uz/gov.uz sahifasida dinamik jadval sifatida yuritiladi; veb-qidiruv orqali topilgan alohida yozuvlar:
- E-POS (versiya 1.0.0) — 2020-03-31 sanada ro'yxatga olingan.
- SOFT TECH SOLUTIONS MChJ, "Virtual kassa POS2K V5.0" — 2020-04-30 sanada ro'yxatga olingan.
- CASHBOX, UZKASSA, Rahmat POS, REGOS VCR va boshqa bir qancha dastur/uskuna ham reyestrda mavjud deb bozor manbalarida qayd etilgan (lekin bu ro'yxat sessiya davomida sahifaning o'zidan to'liq qayta tekshirilmadi — sahifa WebFetch orqali faqat qisman o'qildi).

---

## 3) Asl belgisi (aslbelgisi.uz) — majburiy tovar guruhlari, POS API, integratorga talablar

### Operator va huquqiy asos
- Operator: **CRPT Turon** (crpt-turon.uz; yordam portali [help.crpt-turon.uz](https://help.crpt-turon.uz/hc/en-us)) — Rossiyaning "Chestny Znak" (CRPT) texnologiyasi negizida ishlaydigan milliy raqamli markirovka tizimi operatori.
- Tizimni joriy etish asosi: Vazirlar Mahkamasining **2020-11-20dagi 737-son qarori**.
- Yangi: **23-son qaror (2026-01-23)** — "Majburiy raqamli markirovkalash tizimi samaradorligini oshirishga oid qo'shimcha chora-tadbirlar to'g'risida" ([lex.uz/docs/8012407](https://www.lex.uz/docs/8012407)):
  - **2026-yil 1-iyuldan** elektron hisob-fakturalarda markirovka kodlari avtomatik tekshirilishi va nazorat-kassa texnikasida markirovka ma'lumotlari avtomatik kiritilishi majburiy bo'ladi.
  - Tovarni bir joydan ikkinchisiga ko'chirish (masalan, ombordan savdo nuqtasiga) **72 soatdan oshmasligi** kerak.
  - Mintaqalararo nazorat bo'linmasi tashkil etilib, raqamli markirovka qoidalariga rioya etilishini nazorat qiladi.
  - Qarorda aniq jarima summalari ko'rsatilmagan — "nazorat va profilaktika" orqali javobgarlik ko'zda tutilgan.

### Majburiy tovar guruhlari va muddatlar (bosqichma-bosqich)
| Tovar guruhi | Muddat | Izoh |
|---|---|---|
| Tamaki mahsulotlari | 2021-yildan | Birinchi bosqich |
| Alkogol/pivo mahsulotlari | 2021-yildan | Birinchi bosqich |
| Maishiy texnika | 2022-yildan | |
| Dori vositalari, tibbiy buyumlar | 2022-yildan | |
| Suv va alkogolsiz (salqin) ichimliklar | 2024-03-01 (sotuvda majburiy) | Ishlab chiqaruvchilar uchun hisob-fakturada kod ko'rsatish muddati 2026-04-01 ga uzaytirilgan ([help.crpt-turon.uz — 631-son qaror sharhi](https://help.crpt-turon.uz/hc/en-us/articles/10459257827345-Water-and-Beverages-Cabinet-Resolution-No-631-Stages-of-Implementing-Mandatory-Digital-Labeling-and-List-of-HS-Codes)) |
| O'simlik yog'i | 2026-10-24 (maslahat tartibida) | **Tasdiqlanmagan** — oldingi tadqiqot qaydida bor edi, bu sessiyada hech qanday manbada qayta topilmadi |

Manbalar: [optelgroup.com — Asl Belgisi yangilanishi (farmatsevtika)](https://www.optelgroup.com/en/blog/uzbekistan-asl-belgisi-update-mandatory-serialization-of-pharmaceutical-products/), [rfxcel.com — Asl Belgisi farma muddati](https://rfxcel.com/uzbekistan-asl-belgisi/), [help.crpt-turon.uz — suv va ichimliklar bosqichlari](https://help.crpt-turon.uz/hc/en-us/articles/10459257827345-Water-and-Beverages-Cabinet-Resolution-No-631-Stages-of-Implementing-Mandatory-Digital-Labeling-and-List-of-HS-Codes).

*Tuzatish: "2026-03-01 dan muddati o'tgan tovar bloklanadi" degan ma'lumot endi **qisman tasdiqlandi** — yaroqlilik muddati o'tgan markirovkalangan tovarlarning QR kodi skanerlanganda kassa tizimi sotuvni ro'yxatga olishga va chek berishga ruxsat bermasligi, hamda 2026-03-01 dan boshlab bunday tovarlar savdosi cheklanishi va jarima yuqori minimal ish haqining 30 barobarigacha (12,36 mln so'm) oshirilgani yangiliklarda tasdiqlangan ([spot.uz — 2026-yil 1-martdan nimalar o'zgaradi](https://www.spot.uz/oz/2026/02/26/march-changes), [aniq.uz](https://aniq.uz/uz/yangiliklar/2026-yildan-yaroqlilik-muddati-utgan-tovarlarning-savdosi-cheklanadi)); bu chora 2020-12-31dagi 833-son qarorga asoslanadi ([lex.uz/uz/docs/-5205248](https://lex.uz/uz/docs/-5205248?ONDATE=23.01.2026)), lekin 833-son qarorning aniq moddasi (band raqami) bu sessiyada to'liq matndan ajratib olinmadi — faqat yangiliklar orqali tasdiqlandi, birlamchi band matni bilan emas. **"2026-10-24 dan o'simlik yog'i" muddati esa bu sessiyada hech qanday manbada qayta topilmadi — tasdiqlanmagan holicha qoldiriladi.**

### POS uchun ishlash jarayoni (tekshirish va sotuvni chiqarish)
Rasmiy, ochiq API texnik spetsifikatsiyasi (so'rov/javob formati, endpointlar) ushbu tadqiqot davomida **topilmadi**: `help.crpt-turon.uz` ning asosiy hujjat sahifalariga kirishda **HTTP 403 (kirish taqiqlangan)** xatoligi chiqdi — bu, ehtimol, hisob qaydnomasi yoki integrator sifatida ro'yxatdan o'tishni talab qiladi.

Uchinchi tomon (vositachi) manbalardan tiklangan umumiy jarayon:
1. POS/kassa qurilmasi mahsulot qadog'idagi **DataMatrix** kodini 2D-skaner bilan o'qiydi.
2. Kod OFD ("Yangi texnologiyalar" DUK) orqali Asl Belgisi milliy tizimiga yuboriladi.
3. Tizim kodning haqiqiyligini, oldin sotilmaganligini tekshiradi va "chiqarish" (spisaniye) amalini bajaradi.
4. Noto'g'ri, takroriy yoki muddati o'tgan kod aniqlansa — sotuv rad etilishi yoki bloklanishi mumkin.

(Manbalar: [mertech.uz — Asl Belgisi tizimi sharhi](https://mertech.uz/shopblog/torgovoe-oborudovanie/asl-belgisi-ru/), [moysklad.uz — Asl Belgisi integratsiyasi yangiligi](https://www.moysklad.uz/news/podderzhka-markirovki-asl-belgisi/), [buxgalter.uz — markirovkalangan tovar sotuvini aks ettirish](https://buxgalter.uz/publish/doc/text202867_kak_otrajat_informaciyu_o_prodaje_markirovannyh_tovarov_v_sisteme_asl_belgisi).)

### Integratorga qo'yiladigan talablar
Rasmiy, to'liq ro'yxat (ro'yxatdan o'tish shartlari, shartnoma namunasi, texnik sertifikatlash) **ochiq manbada topilmadi** — help.crpt-turon.uz portalining tegishli bo'limlari kirish cheklovi tufayli o'qib bo'lmadi. Bozordagi integratorlar (E-POS, MoySklad, Smartup) "Asl Belgisi" bilan integratsiyani tayyor funksiya sifatida reklama qiladi, lekin ularning CRPT Turon bilan qanday shartnoma/sertifikat asosida ishlashi ochiq hujjatlashtirilmagan.

### Hujjatlar havolasi
- Yordam markazi: [help.crpt-turon.uz/hc/en-us](https://help.crpt-turon.uz/hc/en-us) (ba'zi maqolalar ochiq, masalan suv/ichimlik bosqichlari haqida; asosiy API/integratsiya bo'limlari ushbu sessiyada 403 xatosi bilan yopiq chiqdi).
- Iste'molchi ilovasi: [ASL BELGISI — Google Play](https://play.google.com/store/apps/details?id=asllikbelgisi.uz) — kodni skanerlab mahsulot haqiqiyligini tekshirish uchun.

---

## 4) Kassa uskunalari — fiskal printer/terminal modellari, Android POS terminallar

- O'zbekistonda "faqat shu modellar ruxsat etilgan" tarzidagi **yagona statik jadval/hujjat ochiq manbada topilmadi**. Amalda sertifikatlash dastur **va** uskuna birgalikda (yoki alohida fiskal modul sifatida) Davlat reyestriga kiritiladi; reyestrning o'zi — soliq.uz/gov.uz'dagi dinamik veb-sahifa — "ruxsat etilgan" ro'yxat vazifasini bajaradi.
- Bozorda O'zbekiston uchun moslashtirilgan/sertifikatlangan deb reklama qilinayotgan asosiy takliflar (mustaqil ravishda reyestr sahifasida tasdiqlanmadi, faqat vendor saytlaridan):
  - **PAX A930** — Android 7.1 (PayDroid) asosidagi simsiz smart-POS, PCI PTS 5.x va EMV sertifikatlangan; Kapitalbank orqali tarqatiladi ([kapitalbank.uz](https://www.kapitalbank.uz/ru/corporate/terminals/onlayn-kkm/)).
  - **UZKASSA** (N5, P100 va boshqa modellar) — O'zbekistonda ishlab chiqarilgan/yig'ilgan deb da'vo qilinadi, soliq qo'mitasi talablariga mos ([uzkassa.uz](https://uzkassa.uz/), [smartpos.uz](https://smartpos.uz/kassy)).
  - **Rahmat POS** — to'lov terminali + fiskalizatsiya + ombor boshqaruvini birlashtiradi, 943-son qarorga mos deb da'vo qiladi, ofd.uz reyestrida ko'rsatilgan ([rhmt.uz](https://rhmt.uz/pos/smart-kassa/)).
  - **REGOS VCR** — Windows uchun virtual kassa dasturi, fiskal chek va UzQR chiqaradi (apparat emas, dasturiy yechim) ([regos.uz](https://regos.uz/ru/product/regos-vcr/info)).
  - **E-POS Systems** — kassa + fiskalizatsiya + integratsiyalar (Click, Payme, Uzum Pay, Humo, Uzcard, 1C, Bitrix24, MoySklad, Billz, Asl Belgisi, DMed); aniq apparat modeli ko'rsatilmagan, so'rov asosida integratsiya taklif qiladi ([epos.uz/en/integrations](https://epos.uz/en/integrations)).
- Android POS terminallar bozorda keng tarqalgan (asosan xitoylik OEM — PAX va shunga o'xshash ishlab chiqaruvchilarning qurilmalari, mahalliy brendlash bilan sotiladi), lekin "qaysi aniq model raqamlari rasman ruxsat etilgan" degan rasmiy, mustaqil tekshirilgan ro'yxat ushbu tadqiqotda tuzilmadi — buning uchun reyestr sahifasini to'g'ridan-to'g'ri (brauzerda, JS-renderlangan holatda) ochib, jadvalni qo'lda ko'rib chiqish kerak bo'ladi.

---

## Ochiq savollar

1. Mustaqil ishlab chiqilgan virtual kassa dasturini Davlat reyestriga kiritishning **aniq narxi** (sertifikatlash organi xizmati, Kiberxavfsizlik markazi ekspertizasi) — ochiq ommaviy manbalarda topilmadi. Qidirilgan joylar: buxgalter.uz, azma.uz, regulation.gov.uz, soliq.uz — hech birida narx ko'rsatilmagan.
2. **Dastur ishlab chiquvchining mahsulotini Davlat reyestriga kiritish (sertifikatlash) muddati** 943-son qarorning asl matnida alohida band sifatida topilmadi (faqat tadbirkorning qurilmasini ro'yxatga oldirish uchun 4+8 ish soati bor, bu boshqa jarayon — yuqoridagi tuzatishga qarang). Bu hali ham ochiq savol.
3. Fiskal modulning joriy narxi yoki uni biznes subyektlariga bepul berish amaliyoti hali ham davom etayotgani (2019-yilgi tajriba loyihasi davrida bepul berilgan edi) — joriy holat aniqlanmadi.
4. Asl Belgisi uchun rasmiy, texnik jihatdan to'liq API hujjatlari (endpoint, so'rov/javob formati, autentifikatsiya) — help.crpt-turon.uz portalining tegishli bo'limlari 403 xatosi bilan yopiq chiqdi; buni ochish uchun rasmiy integrator sifatida ro'yxatdan o'tish yoki CRPT Turon bilan to'g'ridan-to'g'ri bog'lanish kerak bo'lishi mumkin.
5. "O'simlik yog'i — 2026-10-24" muddati ushbu sessiyada hech qanday manbada qayta topilmadi — tasdiqlanmagan.
6. ~~Offlayn rejimda chekni yuborish muddati~~ — **Yechildi (2026-10-12):** 943-son qarorning 1-ilovasi, 31-bandida "48 soat" aniq tasdiqlangan ([lex.uz/docs/4603329](https://lex.uz/docs/4603329)).
7. "Ruxsat etilgan fiskal printer/Android POS terminal" rasman e'lon qilingan statik ro'yxati topilmadi — reyestr sahifasining o'zini (soliq.uz/gov.uz) brauzerda to'liq ochib, jadvalni qo'lda tekshirish talab etiladi (ushbu sessiyada WebFetch orqali faqat matn qismi olindi, jadval render qilinmadi).
8. Texnik xizmat ko'rsatish markazlariga (943-son qarorning 3-ilovasi) qo'yiladigan aniq talablar va ularning joriy Davlat reyestri ro'yxati ushbu tadqiqotda ochilmadi.
9. 833-son qarorning (2020-12-31) "muddati o'tgan tovar 2026-03-01 dan bloklanadi" degan aniq bandi birlamchi matndan to'liq iqtibos qilinmadi — faqat yangiliklar (spot.uz, aniq.uz) orqali tasdiqlandi.

---

## Manbalar

- [lex.uz/docs/4603329](https://lex.uz/docs/4603329) — VM qarori No. 943 (2019-11-23), onlayn-NKM/virtual kassa asosiy hujjati.
- [lex.uz/docs/4210424](https://lex.uz/docs/4210424), [lex.uz/docs/4210436](https://lex.uz/docs/4210436) — VM qarori No. 150 (2019-02-21), pilot loyiha.
- [regulation.gov.uz/oz/document/8344](https://regulation.gov.uz/oz/document/8344) — 943-son qaror loyihasi/tahlili.
- [buxgalter.uz — 2-ilova, texnik talablar](https://buxgalter.uz/uz/doc?id=606697_o%E2%80%98zbekiston_respublikasi_hududida_qo%E2%80%98llanilishi_ruhsat_etilgan_onlayn_nazorat-kassa_mashinalari_virtual_kassa_va_fiskal_modulga_qo%E2%80%98yiladigan_tehnik_talablar)
- [kadrovik.uz — 1-ilova, Nizom](https://kadrovik.uz/en/doc?id=606743_aholi_bilan_pulli_hisob-kitoblarni_amalga_oshirishda_onlayn_nazorat-kassa_mashinalari_va_virtual_kassa_tizimini_qo%E2%80%98llash_tartibi_to%E2%80%98g%E2%80%98risida_nizom)
- [nrm.uz — 3-ilova, texnik xizmat markazlari](https://nrm.uz/contentf?doc=606706_onlayn_nazorat-kassa_mashinalari_virtual_kassa_va_fiskal_modulga_tehnik_hizmat_ko%E2%80%98rsatish_markazlarining_davlat_reestrini_yuritish)
- [nrm.uz — fiskal modulga texnik talablar](https://nrm.uz/contentf?doc=579928_tehnicheskie_trebovaniya_k_fiskalnomu_modulyu)
- [buxgalter.uz — reyestrga kiritish hujjatlari (10 band)](https://buxgalter.uz/uz/publish/doc/text195345_avtomatlashtirish_dasturlarini_soliq_organlarining_ahborot_tizimlari_bilan_integraciya_qilish_talablari)
- [soliq.uz/page/virtual-kassa-reestri](https://soliq.uz/page/virtual-kassa-reestri?lang=uz) → [gov.uz/oz/soliq/page/virtual-kassa-reestri](https://www.gov.uz/oz/soliq/page/virtual-kassa-reestri?lang=uz) — Davlat reyestri.
- [soliq.uz/page/onlayn-nkm](https://soliq.uz/page/onlayn-nkm?lang=ru) → [gov.uz/oz/soliq/page/onlayn-nkm](https://www.gov.uz/oz/soliq/page/onlayn-nkm?lang=ru) — rasmiy sahifa.
- [soliq.uz — "Yangi texnologiyalar" DUK (OFD operatori)](https://soliq.uz/about/subordinate-organizations/gup-nauchno-informacionnyj-centr-yangi-tehnologiyalar)
- [azma.uz — onlayn kassalar sharhi](https://azma.uz/tpost/u1lyuxv711-onlain-kassi-v-uzbekistane-komu-obyazate)
- [regos.uz — fiskal modul (POFM) tushuntirishi](https://regos.uz/ru/blog/polezno-znat/chto-takoe-fiskalnyj-modul-pofm)
- [buxgalter.uz — chek rekvizitlari](https://buxgalter.uz/uz/publish/doc/text188570_nima_uchun_chek_soliqqa_doir_ahborotni_uz_ichiga_olmasligi_mumkin)
- [buxgalter.uz — MXIK qidirish](https://buxgalter.uz/uz/publish/doc/text191011_tasnif_soliq_uz_saytida_tugri_mhik_qanday_topiladi)
- [lex.uz/docs/8012407](https://www.lex.uz/docs/8012407) — 23-son qaror (2026-01-23), markirovka samaradorligi.
- [help.crpt-turon.uz/hc/en-us](https://help.crpt-turon.uz/hc/en-us) — Asl Belgisi yordam markazi (qisman kirish).
- [help.crpt-turon.uz — suv/ichimlik bosqichlari (631-son qaror)](https://help.crpt-turon.uz/hc/en-us/articles/10459257827345-Water-and-Beverages-Cabinet-Resolution-No-631-Stages-of-Implementing-Mandatory-Digital-Labeling-and-List-of-HS-Codes)
- [optelgroup.com — Asl Belgisi farma yangilanishi](https://www.optelgroup.com/en/blog/uzbekistan-asl-belgisi-update-mandatory-serialization-of-pharmaceutical-products/)
- [rfxcel.com — Asl Belgisi farma muddati](https://rfxcel.com/uzbekistan-asl-belgisi/)
- [mertech.uz — Asl Belgisi tizimi va skanerlar](https://mertech.uz/shopblog/torgovoe-oborudovanie/asl-belgisi-ru/)
- [moysklad.uz — Asl Belgisi integratsiyasi](https://www.moysklad.uz/news/podderzhka-markirovki-asl-belgisi/)
- [buxgalter.uz — markirovkalangan tovar sotuvi](https://buxgalter.uz/publish/doc/text202867_kak_otrajat_informaciyu_o_prodaje_markirovannyh_tovarov_v_sisteme_asl_belgisi)
- [kapitalbank.uz — PAX A930](https://www.kapitalbank.uz/ru/corporate/terminals/onlayn-kkm/)
- [uzkassa.uz](https://uzkassa.uz/), [smartpos.uz](https://smartpos.uz/kassy)
- [rhmt.uz — Rahmat POS](https://rhmt.uz/pos/smart-kassa/)
- [regos.uz — REGOS VCR](https://regos.uz/ru/product/regos-vcr/info)
- [epos.uz/en/integrations](https://epos.uz/en/integrations)
- [azma.uz — IKPU/MXIK kodlari tuzilishi](https://azma.uz/tpost/ikpu-mxik-kodlari-ozbekiston), [moysklad.uz — IKPU kodlari](https://www.moysklad.uz/uz/poleznoe/shkola-torgovli/kody-ikpu/) — MXIK 17 raqam tasdig'i
- [spot.uz — 2026-yil 1-martdan nimalar o'zgaradi](https://www.spot.uz/oz/2026/02/26/march-changes), [aniq.uz — yaroqlilik muddati o'tgan tovar savdosi cheklanishi](https://aniq.uz/uz/yangiliklar/2026-yildan-yaroqlilik-muddati-utgan-tovarlarning-savdosi-cheklanadi), [lex.uz/uz/docs/-5205248 — 833-son qaror (2020-12-31)](https://lex.uz/uz/docs/-5205248?ONDATE=23.01.2026) — 2026-03-01 muddati o'tgan tovar bloklanishi
