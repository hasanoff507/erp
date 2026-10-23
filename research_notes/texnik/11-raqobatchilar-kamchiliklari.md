# Raqobatchilar kamchiliklari

*Tadqiqot sanasi: 2026-10-12. Tadqiqotchi: Claude Haiku (research agent).*

O'zbekistondagi soliq va savdo tizimlarining asosiy muammolari: fiskal kassa qoidabuzarliklari, markirovka tizimining texnik va moliyaviy og'irligi. Bundan tashqari, O'zbekiston bozoridagi mahalliy POS/ERP raqobatchilari (BILLZ, REGOS va h.k.) haqida ochiq mijoz shikoyati topilmadi — quyida Rossiya Federatsiyasi bozorida ishlagan tizimlar (MoySklad, Poster) haqidagi sharhlar ham keltirilgan, ular **faqat RF bozoriga oid** va O'zbekistonga to'g'ridan-to'g'ri tatbiq etilmasligi mumkin — bu alohida ko'rsatilgan.

## Shikoyatlar jadvali

| Mahsulot yoki tizim | Shikoyat (iqtibos + mazmuni) | Manba | Bizga imkoniyat (faqat manba tasdiqlagan darajada) |
| --- | --- | --- | --- |
| Nazorat kassa (O'zbekiston) | Bir hafta davomida 400 dan ortiq tekshirish o'tkazilib, barchasida qoidabuzarlik aniqlangan (fiskal xatolari, naqdsiz to'lovni qabul qilmaslik, chek bermaslik) *(2026-10-14 tekshiruvida tuzatildi: avval so'zma-so'z tirnoqli iqtibos "400 dan ortiq qoidabuzarlik holatlari topilgan" edi — bu parafraz, aslida manbada "bir hafta davomida 400 dan ortiq tekshirish o'tkazilib, barchasida qoidabuzarlik aniqlangan" deyilgan)* | [kun.uz — kassa tekshiruvi](https://kun.uz/28393917) | Dasturda sotuvchiga chek berish/naqdsiz to'lov qabul qilish majburiyatini eslatish va nazorat qilish — bu qoidabuzarlikni kamaytirishga yordam beradi, lekin to'liq yo'q qilishni kafolatlamaydi |
| Markirovka tizimi (O'zbekiston) | "Skanerlar muntazam ishlamaydi, uskuna o'rnatish qiyin, xarajat 300 ming dollardan ortiq (ba'zan 0,5 mln dollardan ko'proq), mahsulot narxi 2–4% oshgan" *(2026-10-14 tekshiruvida tuzatildi: avval "300–500 ming so'm" edi — manbada bu korxona/zavod darajasidagi uskunalashtirish xarajati bo'lib, 300–500 ming AQSH DOLLARI, so'm emas — ~10 000x farq)* | [gazeta.uz — markirovka muammolari, 2026-04-14](https://www.gazeta.uz/oz/2026/04/14/marking/) | **Tuzatish**: skaner uskunasini yo'q qilib bo'lmaydi — Asl belgisi qonunan DataMatrix 2D-skanerlashni talab qiladi (`02-fayl`). Bizning imkoniyatimiz — dastur darajasida xato oldini olish: kodni skanerlashdan oldin formatini tekshirish, mos uskuna ro'yxatini aniq ko'rsatish, muvaffaqiyatsiz skanerlashda tushunarli xabar berish |
| Markirovka jarimalari (O'zbekiston) | "Talabni buzish uchun 2–20% jarima — bitta xodimning xatosi butun brendni bankrotlikka olib kelishi mumkin" | [gazeta.uz — markirovka jarimalari, 2026-03-31](https://www.gazeta.uz/oz/2026/03/31/marking-fine/) | Sotuvdan oldin kodni avtomatik tekshirish (noto'g'ri/muddati o'tgan/takroriy kodni kassada bloklash) orqali jarima xavfini kamaytirish |
| MoySklad (**RF bozori sharhi, O'zbekistonga tatbiqi tasdiqlanmagan**) | "Отсутствует телефонная техподдержка" — faqat chat/elektron pochta orqali yordam, telefon qo'llab-quvvatlash yo'q | [startpack.ru — MoySklad sharhlari](https://startpack.ru/application/my-sklad/reviews) | O'zbek va rus tilida telefon/Telegram orqali qo'llab-quvvatlash — bu RF sharhidagi bo'shliqqa javob, O'zbekiston mijozlari uchun mustaqil tasdiqlanmagan |
| MoySklad (**RF bozori sharhi**) | "Цены повышают, функционал выводят в отдельную опцию за отдельную плату" — narx oshishi, funksiyalarning alohida pullik optsiyaga chiqarilishi | [otzovik.com — MoySklad sharhlari](https://otzovik.com/reviews/moy_sklad_torgovlya_sklad_i_crm_onlayn/) | Oddiy, barqaror narx tuzilmasi — asosiy funksiyalarni bitta tarifga kiritish |
| Poster POS (**RF bozori sharhi, geopolitik voqea**) | "После начала стычек с их страной был отключен доступ для клиентов из РФ на несколько дней" — RF mijozlari uchun kirish bir necha kunga uzilgan *(2026-10-14 tekshiruvida tuzatildi: avval iqtibos "с Украиной" deb berilgan edi — manbada aniq "с их страной" deyilgan, kontekst — 2022, Poster — mos keladi, lekin so'zma-so'z iqtibos noto'g'ri edi)* | [startpack.ru — Poster sharhlari](https://startpack.ru/application/poster-automation/reviews) | Mahalliy (O'zbekiston) hosting va offlayn-first kassa — xorijiy siyosiy/texnik uzilishlarga bog'liq emas (`04-fayl`dagi offline-first arxitektura bilan mos) |

*Eslatma: avvalgi versiyada bu jadvalga ЮKassa (Yandex to'lov tizimi, Rossiya) haqidagi shikoyat qator sifatida kiritilgan edi — bu O'zbekiston ERP/POS raqobatchisi EMAS (Yandex to'lov xizmati O'zbekistonda faol ekanligi tasdiqlanmagan) va fayl mavzusiga (raqobatchilar kamchiliklari) aloqasiz edi, shuning uchun olib tashlandi.*

## Eng ko'p takrorlanadigan muammolar

- **Markirovka tizimining texnik va moliyaviy og'irligi** (O'zbekiston, birlamchi manbali) — skaner ishlamasligi, uskuna xarajati, jarima xavfi.
- **Fiskal kassa qoidabuzarliklari** (O'zbekiston) — chek bermaslik, naqdsiz to'lov qabul qilmaslik.
- **Texnik qo'llab-quvvatlash va narx shaffofligi bo'yicha shikoyatlar** — faqat RF bozori sharhlarida topildi (MoySklad, Poster); O'zbekiston mahalliy raqobatchilari (BILLZ, REGOS, Smartup, UZKASSA) bo'yicha ochiq shikoyat **topilmadi** — bu haqiqiy bo'shliq, lekin manba yo'qligi sababli "O'zbekistonda ham shunday" deb taxmin qilinmaydi.

*(2026-10-14 tekshiruvida qo'shildi: ushbu jadvaldagi MoySklad shikoyatlari (telefon qo'llab-quvvatlash yo'qligi, narx oshishi) faqat RF bozoriga oid va MoySklad'ning O'zbekistondagi soliq integratsiyasi haqida xulosa chiqarmaydi — moysklad.uz o'z saytida E-POS orqali fiskal ro'yxatga olish va AslBelgisi/Didox integratsiyasini aniq reklama qiladi (`06-fayl`da batafsil). Shuningdek REGOS ham Didox bilan integratsiyalangan. Loyihaning asl kamchiligi "integratsiya umuman yo'q" emas, balki: bitta tizimda hammasi birlashmagan (uchinchi tomon kassa/EDOsiz), davlat tuzgan hisobotni ichki hisob bilan solishtirish yo'q, offline+markirovka zaif, o'zbek tilida AI yo'q — bular hali tasdiqlanmagan gipoteza sifatida qaraladi.)*

## Ochiq savollar

- Mahalliy POS raqobatchilari (BILLZ, REGOS, Smartup, UZKASSA, mDokon) bo'yicha haqiqiy mijoz shikoyatlari — Google Play, forumlar va infostart.ru'da qidirildi, topilmadi (infostart.ru so'rovlarni 429 xatosi bilan cheklab qo'ydi). **Kim bilan bog'lanish**: 10–15 ta do'kon egasi bilan to'g'ridan-to'g'ri suhbat (Claude Docs asosiy hujjatida ham shu tavsiya bor).
- MoySklad/Poster'ning RF sharhlaridagi kamchiliklari O'zbekiston filiali/mijozlari uchun ham amal qiladimi — mustaqil tasdiqlanmadi.

## Manbalar

- [kun.uz](https://kun.uz/) — O'zbekiston yangiliklar portali
- [gazeta.uz](https://www.gazeta.uz/oz/) — O'zbekiston gazetasi
- [otzovik.com](https://otzovik.com/) — rus sharhlar portali (RF bozori)
- [startpack.ru](https://startpack.ru/) — SaaS/dastur sharhlari (RF bozori)
