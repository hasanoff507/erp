# R5 — Bozor va raqobatchilar: "POS/ERP → 1C" eksporti qanday qilinadi va undan saboqlar

> **Yakuniy tavsiya ustun (accept gate, 2026-10-15):** shu papkadagi fayllar orasidagi ziddiyatlar `00-xulosa.md` da hal qilingan (§«Hal qilingan ziddiyatlar»). Bu fayl bilan `00-xulosa.md` farq qilsa — **00-xulosa'dagi yakuniy tavsiya ustun**. Kanonik nomlar: jadvallar — `04` §3.3; idempotentlik algoritmi — `04` §5.3; maydon xaritalari va ketma-ketlik — `03` §3, §5.1.

**Maqsad:** O'zbekiston va MDH'dagi POS/ERP mahsulotlari kun yakunidagi savdo va boshqa hujjatlarni mijozning 1C bazasiga qanday uzatishini o'rganish; ularning mexanizmi, 1C'da yaratiladigan hujjatlar, agregatsiya, ma'lumotnomalarni moslashtirish, narx va ma'lum muammolarini jamlash; bizning integratsiyamiz uchun saboqlar va ustunliklarni aniqlash.
**Kim uchun:** asoschi; 1C integratsiya moduli (qaror #36) loyihachisi; mahsulot/marketing.
**Bog'liq fayllar:** `spec/kod-uchun/00-README.md` (qoida 6), `research_notes/sonar-1c-integratsiya/00-xulosa.md`, `05-mahsulot-funksiyalari-va-server-api.md`; shu papkadagi `04-integratsiya-arxitekturasi.md` (R4), `06-1c-ga-yozish-texnikasi.md` (R6).
**Holat:** tadqiqot, 2026-10-15. Hech narsa publish qilinmagan. Har da'vo yonida URL bor; *taxmin* — manbada tasdiqlanmagan xulosa.

> **Asoschi qarori (2026-10-15):** bizning integratsiya **faqat COM** orqali, mijoz kompyuteridagi Windows agenti bilan ishlaydi (OData yo'q, 1C'dan hech narsa publish qilinmaydi). Raqobatchilarning mexanizmlari quyida qanday bo'lsa shunday yozilgan, ammo §6–§8 dagi saboq va ustunliklar **COM-agent nuqtai nazaridan** baholangan.

**Tadqiqot usuli:** Google qidiruvi (brauzer orqali) + rasmiy sahifalar, yordam markazlari, ilova do'konlari, forumlar. Yopiq manbalar (1С:ИТС'ning pullik bo'limlari) faqat qidiruv parchasi bo'yicha keltirilgan va shunday belgilangan.

---

## 0. Asosiy xulosalar (10 ta)

1. **Bozor standarti — "kun/smena bo'yicha bitta «Отчет о розничных продажах» (ORP)".** Evotor, Kontur.Market, iiko, Poster, r_keeper, 1С:Розница→БП — hammasi savdoni chek-chek emas, kun yoki kassa smenasi bo'yicha yig'ma ORP qilib yozadi (manbalar §2). Bizning eksportimiz ham shu shaklda bo'lishi kerak.
2. **Asosiy mexanizm — 1C ichida ishlaydigan tashqi qayta ishlash (`.epf`) yoki kengaytma, API/token orqali bulutdan ma'lumot tortadi** (Evotor ilovalari, Kontur, Poster, iiko, REGOS). Fayl almashinuvi (EnterpriseData XML, CSV) — ikkinchi yo'l (MoySklad, iiko). Ma'lumotlarni tashqi COM-agent bilan yozadigan tayyor POS mahsulotini topmadik. Bu "1C ichiga hech narsa o'rnatilmaydi" degan ustunlik bo'lishi mumkin (*taxmin*).
3. **O'zbekistonda POS→1C uchun hujjatlashtirilgan tayyor konnektor deyarli yo'q.** BILLZ'da faqat API bor ("BI yoki 1C ga eksport" — integrator yozadi). REGOS'da yo'nalish teskari (1C→REGOS). E-POS, Rahmat, Smartup "1C bilan integratsiya" deb da'vo qiladi, lekin tafsilot ochiq emas. Amalda bu ishni integratorlar 5–20 mln so'mga buyurtma asosida qiladi.
4. **Eng ko'p uchraydigan og'riq — nomenklatura dublikatlari.** MoySklad hujjatida aytilishicha, birinchi moslashtirish nom bo'yicha qilinadi: nom o'zgarsa, 1C'da yangi kartochka yaratiladi. iiko va Kontur bo'yicha ham sabab — moslashtirilmagan pozitsiyalar.
5. **Ikkinchi og'riq — hujjatlarning takroran yuklanishi.** Evotor'da "за период" rejimi qayta yuklashni nazorat qilmaydi, iiko'da ПКО qayta yuklashda har safar yangidan yaratiladi. Natijada buxgalter dublikatlarni "Сторно" orqali qo'lda tuzatadi va soliq hisobotiga tuzatish kiritadi.
6. **Uchinchi og'riq — 1C yangilanishi va versiyalar mos kelmasligi.** Hujjatlarda "1C yangilangach qayta ishlashni ham yangilang", "xato 400 → konfiguratsiyani 11.4 dan 11.5 ga yangilang" deyilgan. Bundan tashqari "УТ11 Узбекистан → Бухгалтерия для Узбекистана" EnterpriseData almashinuvi format versiyalari (1.8 va 1.5) mos kelmagani uchun "hech qachon ishlamagan".
7. **To'rtinchi og'riq — 1C cheklovlari.** Kod va raqam 11 belgidan, nom 100 belgidan oshmasligi kerak; har bir chakana nuqtaga alohida ombor kerak; prefiks majburiy; manfiy qoldiqda ORP o'tkazilmaydi; davr yopilgan bo'lsa yozib bo'lmaydi. Raqobatchilar bularni yozish **paytida** xato sifatida chiqaradi. Biz ularni **oldindan** (preflight) tekshira olamiz.
8. **Narx:** MDH'da alohida pullik qo'shimcha (Evotor ilovalari 630–640 ₽/oy/terminal). MoySklad'da bepul (fayl). O'zbekistonda integrator loyihasi 5–20 mln so'mdan. **Integratsiyani tarifga kiritish — aniq ustunlik.**
9. **Yaxshi naqshlar (nusxa olishga arziydi):** Kontur'dagi "faqat moslashtirilmaganlarni ko'rsatish" va "1C'da tovar yaratish" tugmasi, hamda o'zgargan hisobotni "qayta to'ldirish". Tusoft'dagi "faqat yaratish / yaratish + o'tkazish" tanlovi, kun yoki smena bo'yicha ORP, `Комментарий` markeri. iiko'dagi "har bir hujjat turini avval alohida sozlab oling, keyin o'tkazing" tartibi.
10. **COM-agent uchun asosiy xavflar:** mijoz kompyuteri yoqiq bo'lishi va platforma/COM ro'yxatdan o'tgan bo'lishi kerak; bulutdagi 1C (1С:Fresh, hosting) COM bilan yetib bo'lmaydi (Kontur ham bulutli 1C'ni qo'llamaydi); "Базовая" versiyalar COM'ni qo'llamaydi (R6 §7). Bularni onboarding'da birinchi tekshiruv qilish kerak.

---

## 1. Umumiy jadval

| Mahsulot (mamlakat) | Mexanizm | 1C'da yaratiladigan hujjatlar | Agregatsiya | Ma'lumotnomalarni moslashtirish | Qo'lda / avto | Narx | Manba |
|---|---|---|---|---|---|---|---|
| **BILLZ** (UZ) | Faqat REST API; tayyor 1C konnektori yo'q | — (integrator qaror qiladi) | API: do'kon × sana yig'ma (`general-report-table`) yoki tranzaksiyalar | — | Integrator skripti | API bepul (*taxmin*) | [docs: sales-export](https://docs.billz.io/guides/sales-export/), [scenarios](https://docs.billz.io/start/scenarios/), [integration](https://billz.io/integration) |
| **REGOS** (UZ) | 1C ichida "REGOS" bo'limi (kengaytma/qayta ishlash), API kalitlari | Yo'nalish **1C → REGOS**: 1C'dagi chakana savdo → REGOS'dagi "агрегированные операции" | — | — | Sozlanadi | Hamkor (Leading) orqali, narx yo'q | [regos.uz blog](https://regos.uz/ru/blog/sistema-regos/sovmestnaya-rabota-servisa-regos-i-1c) |
| **Smartup** (UZ) | "1C, SAP bilan integratsiya" da'vosi; hamkorlar (BA-IT) loyihasi | Ochiq emas | Ochiq emas | Ochiq emas | — | Loyiha | [greenwhite.uz/smartup](https://www.greenwhite.uz/smartup), [ba-it.uz](https://ba-it.uz/product/sobstvennye-resheniya/dlya-malogo-i-srednego-biznesa/integratsiya-1s-s-smart-up-dlya-distribyutorskikh-kompaniy/) |
| **MoySklad (UZ/RU)** | Fayl eksporti: EnterpriseData (1.17 gacha) yoki "БП 3.0" formati; yoki 1С:Fresh'ga to'g'ridan-to'g'ri | Hujjatlar va ma'lumotnomalar (tur bo'yicha tanlanadi), chakana savdo ham | Chakana nuqta = ombor | 1C qoidalari: avval kod yoki nom bo'yicha, keyin GUID bo'yicha | Qo'lda (tugma), davr tanlanadi | Bepul | [support.moysklad.ru](https://support.moysklad.ru/hc/ru/%D0%B8%D0%BD%D1%82%D0%B5%D0%B3%D1%80%D0%B0%D1%86%D0%B8%D0%B8/%D1%8D%D0%BA%D1%81%D0%BF%D0%BE%D1%80%D1%82_%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D1%85_%D0%B2_1%D1%81_%D0%B1%D1%83%D1%85%D0%B3%D0%B0%D0%BB%D1%82%D0%B5%D1%80%D0%B8%D1%8E), [moysklad.uz app](https://www.moysklad.uz/integratsii/apps/1s-bukhgalteriya/) |
| **iiko** (RU, UZ dilerlar) | 1C'dagi `.epf` yuklagich: CSV fayl yoki iiko serveriga to'g'ridan-to'g'ri ulanish | Акт реализации → ORP + Отчет производства за смену + ПКО; Приходная → Поступление + СФ; Акт списания → Требование-накладная va h.k. | Smena / kun | Alohida "Сопоставление справочников" bosqichi | Qo'lda, davr bo'yicha | Yuklagich iiko bilan birga (*taxmin*); UZ'da dilerlar sozlaydi | [iiko: 780](https://ru.iiko.help/articles/iikochain-8-0/topic-780), [786](https://ru.iiko.help/articles/iikochain-8-0/topic-786), [iiko-1](https://ru.iiko.help/articles/iikochain-8-0/iiko-1), [kafesoft.uz](https://kafesoft.uz/ru/technicalsupport/) |
| **Poster** (UA/global, UZ'da bor) | 1C'da tashqi qayta ishlash + Poster tokeni, "Стартовый помощник" | ORP, Отчет производства за смену, Поступление, Перемещение, Списание, ПКО/РКО | Smena | Ustaxona: nomenklatura sinxronizatsiyasi, "avto yaratish" bayrog'i | Avto/qo'lda | Narx ko'rsatilmagan | [joinposter.com/applications](https://joinposter.com/applications/1c-integration), [KB](https://knowledge-base.joinposter.com/ru/how-to-integrate-poster-with-1c-enterprise-management-1.3), [tour](https://joinposter.com/tour/addons/1c-integration) |
| **Evotor** — "Интеграция Эвотор и 1С:Бухгалтерия" (A-System) | `.epf` tashqi qayta ishlash + bulut servisi | Sotuv, qaytarish, hisobdan chiqarish, qabul, inventarizatsiya, kassa operatsiyalari | Smena / davr | Nomenklatura 1C → kassa | Qo'lda yoki jadval bo'yicha | 630 ₽/oy dan | [market.evotor.ru](https://market.evotor.ru/store/apps/79aaebe4-9238-4cc3-8224-95efc8d3f0ab) |
| **Evotor** — "1С-Эвотор" (rasmiy, Softehno) | 1C'ning standart "ККМ-Офлайн" drayveri (БПО 2.0.4.18+), token | **Faqat ORP** | Smena | Nomenklatura, narx, qoldiq 1C → kassa | Standart oflayn-almashinuv | 630 ₽/oy/terminal | [market.evotor.ru](https://market.evotor.ru/store/apps/bd84ea6e-c4b8-438a-b2be-efe62b9da912) |
| **Evotor** — "Обмен с 1С" (Tusoft) | `.epf` + login/parol | ORP (sotuv + qaytarish), ПКО/РКО, karta to'lovlari, Поступление, Списание, Инвентаризация | **Kun yoki smena** (tanlanadi) | Universal rekvizitlar (asosiy xaridor/tovar) | Qo'lda yoki jadval | Ilova obunasi | [tusoft.ru](https://tusoft.ru/support-evotor-1c/category/obmen-s-1c/nachalo-raboty-s-obmenom-s-1s-registraciya-i-obnovlenie-modulya/dopolnitelnyj-modul-obmen-s-1s/) |
| **Kontur.Market** (RU) | 1C moduli (tashqi qayta ishlash) + token | ORP, xaridor qaytarishlari, avans to'lovlari, hisobdan chiqarish aktlari | **Kun**, bitta nuqtaga bitta hisobot | "Faqat moslashtirilmaganlar", "1C'da tovar yaratish" | Qo'lda (kun tanlab) | Market tarifida (*taxmin*) | [support.kontur.ru 39523](https://support.kontur.ru/market/39523-zagruzka_v_1s_otchetov_o_prodazhax_vozvratax_i), [39527](https://support.kontur.ru/market/39527-nastrojka_integracii_modulya_marketa_s_1c) |
| **r_keeper / StoreHouse Pro** (RU) | 1C'dagi tashqi qayta ishlash (SH Pro → 1C) | SH "Расходная накладная" ("Розничная продажа" turi) → ORP; boshqa ko'p hujjatlar | Hujjat bo'yicha | Ma'lumotnomalarni yuklash va moslashtirish | Qo'lda | Litsenziya kaliti kerak (forum) | [docs.rkeeper.ru](https://docs.rkeeper.ru/sh5/otchet-o-roznichnyh-prodayoah-vygruzka-sh-pro-v-1s-2-0-19608572.html), [infostart forum](https://forum.infostart.ru/forum9/topic147235/) |
| **1С:Розница ↔ 1С:БП** (1C standarti) | Standart sinxronizatsiya (EnterpriseData / almashinuv qoidalari) | Faqat ORP o'tadi; qaytarishlar o'tmaydi (qidiruv parchasi) | Smena/kun | GUID | Avto, jadval bo'yicha | 1C litsenziyasiga kiradi | [its.1c.ru (yopiq, parcha)](https://its.1c.ru/db/content/metod81/src/appsolutionselffinanced/small%20business/data%20exchange/i8107984.htm), [retaildoc 11.4](https://its.1c.ru/db/retaildoc/content/73/hdoc) |
| **Wildberries/Ozon → 1С:БП** | БП ichidagi o'rnatilgan "Загрузить из личного кабинета" | Отчет комиссионера | Hisobot davri | Marketpleys kartochkalarini moslashtirish | Qo'lda | БП'ga kiritilgan | [its.1c.ru metod81 (parcha)](https://its.1c.ru/db/metod81/src/sales/marketplaces), [marketplace.is1c.ru](https://marketplace.is1c.ru/tpost) |
| **OFD → 1C** (RU, "Платформа ОФД") | 1C uchun modul, OFD shaxsiy kabinetidan cheklar | Cheklardan ORP + ПКО | Smena/kun | — | Avto | Litsenziya | [portal.1c.ru PDF](https://portal.1c.ru/download/public/instruction/Instructions_1S-Cheki-OFD_UNF_Retail.pdf), [klerk.ru](https://www.klerk.ru/blogs/platformaofd/703970/) |
| **1C-Bitrix / saytlar** | CommerceML (XML) protokoli: katalog 1C → sayt, buyurtmalar sayt → 1C | Buyurtmalar | Buyurtma bo'yicha | Ichki ID | Avto | Bitrix'ga kiradi | [v8.1c.ru CommerceML](https://v8.1c.ru/tekhnologii/obmen-dannymi-i-integratsiya/standarty-i-formaty/standarty-commerceml/), [dev.1c-bitrix.ru](https://dev.1c-bitrix.ru/learning/course/?COURSE_ID=42&LESSON_ID=3644) |
| **E-POS** (UZ) | "ERP va hisob: 1C" ro'yxatda; tafsilot yo'q; hamkor BA-IT "1C ↔ virtual kassalar" | Ochiq emas | Ochiq emas | — | "Avtomatik" (da'vo) | Buyurtma asosida | [epos.uz/integrations](https://epos.uz/integrations), [ba-it.uz](https://ba-it.uz/product/sobstvennye-resheniya/dlya-malogo-i-srednego-biznesa/obmen-1s-s-virtualnymi-kassami-e-pos-arka-/) |
| **Rahmat POS** (UZ) | "Tranzaksiyalarni 1C bazasiga darhol yuklash" (da'vo); 1С:Розница 3.0 — to'lov terminali integratsiyasi | Ochiq emas | Ochiq emas | — | — | — | [rhmt.uz](https://rhmt.uz/pos/integration/), [gazeta.uz](https://www.gazeta.uz/ru/2026/08/06/rahmat/) |
| **Loyverse** (global) | Faqat CSV eksporti, 1C yo'q | — | — | — | Qo'lda | — | [help.loyverse.com](https://help.loyverse.com/help/how-export-data-loyverse-account) (*URL qidiruv natijasidan, sahifa ochilmagan*) |
| **Multikassa** (UZ) | Virtual kassa protokoli (tashqi POS'lar uchun); 1C konnektori topilmadi | — | — | — | — | — | [docs-virtual-kassa.multibank.uz](https://docs-virtual-kassa.multibank.uz/) |
| **Sonar AI** (UZ) | Buxgalter kompyuterida Windows dasturi, **COM**, AI taklifi → tasdiq → yozish | POS eksporti emas; AI orqali bitta hujjat (ПКО va h.k.) | — | Faqat **topadi**, yaratmaydi | Tasdiq bilan | 500 000 so'm/oy (mock) | `research_notes/sonar-1c-integratsiya/00-xulosa.md`, `04` |

---

## 2. Tafsilotlar — O'zbekiston

### 2.1 BILLZ
- Integratsiyalar sahifasining sarlavhasi "Интеграция с 1С, Телеграм ботами и платежными системами", sahifada 1C logotipi bor, lekin 1C haqida matn yo'q — https://billz.io/integration
- Ishlab chiquvchi hujjatlarida 1C faqat API orqali ma'lumot oladigan tizim sifatida tilga olinadi: "Аналитика: выгрузка данных в BI или 1С — Выручка, чеки, транзакции, движение товара — наружу, на чтение" — https://docs.billz.io/start/scenarios/
- Savdo eksporti: `GET /v1/general-report-table` (do'kon × sana), `GET /v1/transaction-report-table` (to'lov turlari bo'yicha), Excel varianti; qoida: **"Вчерашний день забирается целиком один раз: продажа может быть отредактирована или возвращена задним числом"** — https://docs.billz.io/guides/sales-export/
- Xulosa: BILLZ'da tayyor 1C konnektori yo'q. 1C'ga yozishni mijoz yoki integrator o'zi qiladi (*taxmin*: shuning uchun BILLZ mijozlari 1C uchun alohida integratorga pul to'laydi). BILLZ API'dan olinadigan saboq: "kecha"ni bir marta va to'liq olish, chunki savdo orqaga qarab tahrirlanishi mumkin. Bizda esa davrni **muzlatish** (smena yopilgach o'zgartirib bo'lmaydi) yoki o'zgarganda **qayta eksport (hujjatni yangilash)** qilish kerak.

### 2.2 REGOS
- Integratsiya 1C ichidagi "REGOS" bo'limi orqali ishlaydi: ApiLogin, AppKey, Token, login/parol kiritiladi. Yo'nalish **1C → REGOS**: Поступление → kirim, Перемещение → ko'chirish, Реализация оптом → "Отгрузка контрагенту", **Розничные продажи → "Док. агрегированных операций"**, Списание → hisobdan chiqarish. Hamkor — Leading — https://regos.uz/ru/blog/sistema-regos/sovmestnaya-rabota-servisa-regos-i-1c
- REGOS'ning o'zi ham chakana savdoni agregatsiya qiladi ("суммировать данные о продажах, возвратах и платежах с множества касс") — https://regos.uz/ru/blog/sistema-regos/agregatsiya-v-sisteme-regos-podvedenie-itogov-po-prodazham-i-platezham
- Integratsiyalar katalogida (apps.regos.uz) POS→1C konnektori ko'rinmadi — https://apps.regos.uz/
- Xulosa: REGOS 1C'ni ma'lumot **manbasi** sifatida ishlatadi (aksincha). Bizning yo'nalishimizda (ERP → mijoz 1C'si) REGOS raqobatchi emas (*taxmin*).

### 2.3 Smartup (Green White Solutions)
- "Smartup легко интегрируется с такими системами как 1С, SAP" — https://www.greenwhite.uz/smartup ; mijozlar 1C integratsiyasini tanlov sababi deb aytadi — https://www.greenwhite.uz/partner , https://www.greenwhite.uz/clients
- 2019-yilgi reklama maqolasi: "Интеграция Smartup Trade и 1С избавляет … от необходимости вести учет в разных программах, дублировать операции" — https://www.gazeta.uz/ru/2019/07/22/smartup/
- BA-IT "Интеграция 1С с Smart Up для дистрибьюторских компаний" mahsulotini sotadi — https://ba-it.uz/product/sobstvennye-resheniya/dlya-malogo-i-srednego-biznesa/integratsiya-1s-s-smart-up-dlya-distribyutorskikh-kompaniy/
- Mexanizm ochiq emas. Smartup — distribyutsiya ERP'si, kichik do'kon POS'i emas (*taxmin*: to'g'ridan-to'g'ri raqobatchi emas, lekin "1C bilan ishlaydi" degan bozor kutilmasini shakllantiradi).

### 2.4 MoySklad (O'zbekiston)
- "1С: Бухгалтерия — импорт и экспорт данных" ilovasi (Lognex), "Бесплатное решение", 2.0/3.0 va EnterpriseData formatlari — https://www.moysklad.uz/integratsii/apps/1s-bukhgalteriya/
- Yordam markazidagi rasmiy maqola (ru-domen, "MoySklad O'zbekiston" sarlavhasi bilan) — https://support.moysklad.ru/hc/ru/%D0%B8%D0%BD%D1%82%D0%B5%D0%B3%D1%80%D0%B0%D1%86%D0%B8%D0%B8/%D1%8D%D0%BA%D1%81%D0%BF%D0%BE%D1%80%D1%82_%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D1%85_%D0%B2_1%D1%81_%D0%B1%D1%83%D1%85%D0%B3%D0%B0%D0%BB%D1%82%D0%B5%D1%80%D0%B8%D1%8E :
  - Sozlamalar: faqat hujjatlar, faqat ma'lumotnomalar yoki hammasi; hujjat turlari; "Документы за период" **yoki** "Изменения за период"; tashkilot; format; "Выгрузить в онлайн-бухгалтерию" (1С:Fresh — URL, login, parol).
  - **Chakana savdo bo'yicha qat'iy talablar:** "каждая розничная точка продаж должна быть привязана к отдельному складу… иначе выгрузка завершится с ошибкой"; "префикс точки продаж должен быть указан".
  - **Maydon uzunligi chegaralari:** Номенклатура.Код 11, Номенклатура.Наименование 100, Контрагенты.Наименование 150, Склады.Наименование 50, Документ.Номер 11 va h.k.
  - Import 1C'da "Администрирование → Синхронизация данных → Загрузка данных Enterprise Data" orqali qilinadi ("не через обработку Универсальный обмен в формате XML").
  - **Identifikatsiya:** "первичная идентификация товаров может осуществляться по наименованию, в дальнейшем — по GUID"; "Если в МоемСкладе название товара изменилось после выгрузки… товар будет считаться новым и будет создан заново". Kontragent — INN, keyin GUID; hujjat — raqam (yil/tashkilot bilan), keyin GUID.
  - "МойСклад отдает данные, но никак их не обрабатывает. Правила обработки данных устанавливает 1С:Бухгалтерия" — ya'ni natija 1C konfiguratsiyasining versiyasiga bog'liq.
  - QQS 5% va 7% bo'lgan hujjatlar faqat EnterpriseData 1.17 formatida chiqariladi.
- MoySklad'ning o'zi rasmiy YouTube videosida muammoni tan oladi: "Ручная выгрузка данных из МоегоСклада в 1С, дубли товаров, захламленная номенклатура... Знакомо?" — https://www.youtube.com/results?search_query=Интеграция+1С+Бухгалтерия+и+МойСклад (*video sarlavhasi Google parchasidan; aniq video URL olinmagan*)
- moysklad.uz bosh sahifasidagi mijoz fikri: "Самописная система на 1С была дорогой, а готовых интеграций не хватало" — https://www.moysklad.uz/
- **O'zbekiston uchun ochiq savol:** «Бухгалтерия для Узбекистана» qabul qiladigan EnterpriseData versiyasi MoySklad eksport qiladigan versiyaga mos keladimi? Infostart maqolasiga ko'ra (2023), БП Узбекистан'da formatning oxirgi versiyasi 1.5 bo'lgan, УТ11 Узбекистан'da esa 1.8, va ular orasidagi almashinuv "hech qachon ishlamagan" — https://infostart.ru/1c/articles/1955638/ . Demak MoySklad.uz → БП Узбекистан fayl almashinuvi ham muammoli bo'lishi ehtimoli yuqori (*taxmin*, sinab ko'rilmagan).

### 2.5 iiko (O'zbekistondagi dilerlar orqali)
- iiko yuklagichi rasman faqat "1С:Бухгалтерия предприятия 2.0/3.0" uchun — https://ru.iiko.help/articles/iikochain-8-0/topic-780 . «Бухгалтерия для Узбекистана» ro'yxatda yo'q. UZ dilerlari (kafesoft.uz) "Настроим интеграции iiko с 1С, Epos, Rahmat" xizmatini taklif qiladi — https://kafesoft.uz/ru/technicalsupport/ (*taxmin*: UZ BP uchun yuklagich dilerlar tomonidan moslashtiriladi).
- UZ integratori ai-it.uz'ning maslahati: "Ресторану редко нужно передавать в 1С каждый чек… Обычно достаточно сводной выручки за день по точке и способу оплаты (наличные, карты, Payme, Click)"; "Обмен обычно запускают раз в день после закрытия кассовых смен. Должен быть журнал"; tipik xatolar: "Не назначить ответственного за справочник соответствий", "Исправлять данные в 1С вместо того, чтобы исправить их в iiko и перезагрузить" — https://ai-it.uz/blog/integraciya-ayko-s-1s
- MDH qismidagi tafsilotlar — §3.3.

### 2.6 Poster
- Mexanizm: tashqi qayta ishlash. "Вам не понадобится вносить изменения в ваши конфигурации… Обновление до новой версии произойдет автоматически" — https://joinposter.com/applications/1c-integration
- Hozirgi rasmiy ro'yxatdagi konfiguratsiyalar: Ukraina uchun Бухгалтерия 1.2/2.0, BAS, Ukraina uchun Общепит — https://joinposter.com/tour/addons/1c-integration ; yana УПП 1.3 — https://knowledge-base.joinposter.com/ru/how-to-integrate-poster-with-1c-enterprise-management-1.3 (u yerda "❗️1С — российский продукт, мы поддерживаем интеграцию, потому что многие клиенты еще пользуются 1С").
- «Бухгалтерия для Узбекистана» ro'yxatda yo'q, garchi Poster O'zbekistonda faol bo'lsa ham (https://www.instagram.com/joinposter.uzbekistan/). Poster ilovalari orasida Multikassa (UZ fiskalizatsiyasi) bor — https://joinposter.com/applications/1c-integration
- Yaxshi UX: "Стартовый помощник", fiskal yoki nofiskal cheklarni tanlash, "Автоматически создавать новую номенклатуру при импорте" bayrog'i, ORP asosida ПКО yaratish, har bir muassasa uchun tashkilot, kassa va ekvayring sozlamalari — KB havolasi yuqorida.

### 2.7 E-POS, Multikassa, Rahmat, Click/Payme, "Soliq kassa"
- **E-POS:** "ERP и учёт: 1C, Bitrix24, MoySklad, Billz"; boshqa ehtiyojlar uchun "соберём через E-POS API или возьмём в roadmap" — https://epos.uz/integrations . BA-IT "Обмен 1С с виртуальными кассами (E-POS, ARKA)" ni "готовое решение" sifatida sotadi, narxi ko'rsatilmagan — https://ba-it.uz/product/sobstvennye-resheniya/dlya-malogo-i-srednego-biznesa/obmen-1s-s-virtualnymi-kassami-e-pos-arka-/
- **Multikassa:** tashqi kassa tizimlari uchun virtual kassa protokoli — https://docs-virtual-kassa.multibank.uz/ ; 1C konnektori topilmadi.
- **Rahmat:** "мгновенную выгрузку транзакций в базу 1С… исключает пересортицу" (da'vo, tafsilotsiz) — https://rhmt.uz/pos/integration/ ; Venkon "1С:Розница 3.0 ↔ Rahmat POS terminal" integratsiyasini qilgan (bu to'lov terminali, buxgalteriya eksporti emas) — https://www.gazeta.uz/ru/2026/08/06/rahmat/
- **Click/Payme/Uzum:** 1C bilan to'lov integratsiyasini integratorlar (Leading) qiladi — https://leading.uz/articles/integratsiya_1s_s_natsionalnymi_platezhnymi_sistemami_click_payme_i_uzum/
- **"Soliq kassa" / virtual kassa ilovalari:** 1C'ga eksport bo'yicha ochiq ma'lumot topilmadi (soliq.uz'da faqat virtual kassalar reyestri bor — https://soliq.uz/page/virtual-kassa-reestri ). Soliq-servis e-faktura uchun 1C:Бухгалтерия 3.0 ga integratsiya e'lon qilgan — https://api.soliq-servis.uz/news/1c-bugalteriya/ (POS emas).
- **Loyverse:** faqat CSV eksporti (mahsulotlar, mijozlar, cheklar, hisobotlar) — help.loyverse.com (Google parchasi).

### 2.8 Integratorlar bozori (O'zbekiston) — narx mo'ljali
- Bit-box (sayt ↔ 1C): bazaviy 5 mln so'mdan, standart 10 mln, premium 20 mln so'mdan ("+ hujjatlar + monitoring 24/7"); qo'llab-quvvatlanadi: "1C:Savdo boshqaruvi 11, 1C:Buxgalteriya 3.0, 1C:ERP 2, 1C:KA 2, 1C:Chakana savdo 2.3" — https://bit-box.uz/uz/uslugi/1c-integratsiya/
- BA-IT, Leading, 1cba.uz, brix.uz — "integratsiya buyurtma asosida", narx so'rov bo'yicha — https://ba-it.uz/services/professionalnaya-razrabotka-na-1s/integratsiya-1s-i-storonnikh-sistem/ , https://1cba.uz/uslugi/integratsiya-1s , https://brix.uz/catalog/business-and-it-services/buhgalteriya-i-1s/1c-services
- Xulosa: O'zbekistonda "POS → 1C" — **xizmat bozori, mahsulot bozori emas**. Kichik do'kon uchun 5 mln so'm — bizning 99 000 so'mlik tarifimizning ~50 oyligi (*hisob: 5 000 000 / 99 000 ≈ 50*).

### 2.9 Sonar AI (UZ, mahalliy tahlil)
- 1C ustidagi AI qatlami. COM orqali alohida worker jarayonida ishlaydi; 1C tomonda hech narsa o'rnatilmaydi; yozish "taklif → preview (yozmasdan) → tasdiq → `ВерсияДанных` tekshiruvi → `Записать`" tartibida; takror yozishdan himoya — `Комментарий = "Sonar #<id>"` markeri va jurnal; havolalarni faqat **topadi**, 0 ta yoki 2+ ta topilsa xato beradi — `research_notes/sonar-1c-integratsiya/00-xulosa.md` §2.4, `04-…md`.
- POS eksportini qilmaydi, lekin **"1C tomonda hech narsa o'rnatilmaydi" COM naqshining bozordagi yagona namunasi** shu. Asoschi qarori ham aynan shu naqshni tanlagan.

---

## 3. Tafsilotlar — MDH namunalari

### 3.1 Evotor (uchta yondashuv)
1. **"1С-Эвотор" (rasmiy, Softehno):** 1C'ning standart "ККМ-Офлайн" mexanizmi (drayver "1С:Эвотор Офлайн", БПО 2.0.4.18+). "Из смарт-терминала в программу «1С» загружаются **только отчеты о розничных продажах**". Birinchi sinxronizatsiyada "Данные об остатках товаров в Эвоторах будут удалены". Nostandart konfiguratsiyalarni 1C hamkori sozlaydi. Narx 630 ₽/oy/terminal. Sharhlar: "вылетает ошибка 400 при загрузке отчета о РП, так ответ обновите конфигурацию с 11.4 до 11.5"; "Установлен отбор… выгружает все подряд. Нормальной инструкции… нет" — https://market.evotor.ru/store/apps/bd84ea6e-c4b8-438a-b2be-efe62b9da912
2. **A-System "Интеграция Эвотор и 1С:Бухгалтерия":** `.epf` yuklab olinadi va "Дополнительные отчёты и обработки" orqali ochiladi; 13+ konfiguratsiya; sotuv, qaytarish, hisobdan chiqarish, qabul, inventarizatsiya, kassa operatsiyalari ("документы, которые были созданы в течение года"); "вручную или настроить автоматическую отправку"; nostandart 1C'ga moslashtirish ham bor. 630 ₽/oy dan, 812 ta sharh — https://market.evotor.ru/store/apps/79aaebe4-9238-4cc3-8224-95efc8d3f0ab
3. **Tusoft "Обмен с 1С":** ORP (sotuv va qaytarish), ПКО/РКО, karta to'lovi, kirim, qaytarish, hisobdan chiqarish, inventarizatsiya. Sozlamalar: "разрешать или запрещать перезаписывать документы"; "только создавать или создавать и проводить"; "Создавать Отчеты о розничных продажах **за день или по кассовым сменам**"; tannarxni hisobdan chiqarish usuli (1C, ilova yoki narxdan foiz); yuklangan hujjatlar **"Комментарий" maydonida belgilanadi** — https://tusoft.ru/support-evotor-1c/category/obmen-s-1c/nachalo-raboty-s-obmenom-s-1s-registraciya-i-obnovlenie-modulya/dopolnitelnyj-modul-obmen-s-1s/
- **Dublikat muammosi (AkiTorg FAQ):** "Вид загрузки «За период» не контролирует повторной загрузки документов" — "По закрытию смен" rejimini tanlash va bir nechta operator bo'lsa "Контроль повторной загрузки документов" ni yoqish tavsiya qilinadi — https://wiki.evotor.akitorg.ru/index.php?title=%D0%92_1%D0%A1_%D0%B7%D0%B0%D0%B3%D1%80%D1%83%D0%B6%D0%B0%D1%8E%D1%82%D1%81%D1%8F_%D0%B4%D1%83%D0%B1%D0%BB%D0%B8_%D0%B4%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D0%BE%D0%B2_%C2%AB%D0%9E%D1%82%D1%87%D0%B5%D1%82_%D0%BE_%D1%80%D0%BE%D0%B7%D0%BD%D0%B8%D1%87%D0%BD%D1%8B%D1%85_%D0%BF%D1%80%D0%BE%D0%B4%D0%B0%D0%B6%D0%B0%D1%85%C2%BB
- AkiTorg FAQ ro'yxatidagi boshqa muammolar: "В отчете о розничных продажах пустые строки в Наименование, отчет не проводится", "Обновление файла обработки в 1С", "расширение должно быть подписано тем же ключом, что и конфигурация", "Несколько магазинов с разным налогообложением", "Проверка правильности Отчета о розничных продажах и наличия закрытия смены", ошибки 404/429 — https://wiki.evotor.akitorg.ru/index.php?title=%D0%A7%D0%90%D0%92%D0%9E_%D0%B4%D0%BB%D1%8F_%D0%98%D0%BD%D1%82%D0%B5%D0%B3%D1%80%D0%B0%D1%86%D0%B8%D1%8F_1%D0%A1
- Forum: "У эватора есть выгрузка для каждой конфигурации 1С. Правда платная 360 руб/мес" (2021) — https://forum.infostart.ru/forum72/topic255515

### 3.2 MoySklad → 1С:Бухгалтерия — §2.4 da.

### 3.3 iiko → 1С
- Ikki yo'l: CSV fayl (tarmoq diski yoki email orqali) yoki "Сервер iiko – прямое подключение к серверу" ("будут загружены только проведенные документы") — https://ru.iiko.help/articles/iikochain-8-0/topic-780 , https://ru.iiko.help/articles/iikochain-8-0/iiko-1
- **Hujjatlar xaritasi** (https://ru.iiko.help/articles/iikochain-8-0/topic-786): Приходная накладная → Поступление товаров и услуг + СФ полученный (har bir omborga bitta hujjat); Акт реализации → **Отчет производства за смену + Отчет о розничных продажах + ПКО**; Акт списания → Отчет производства за смену + Требование-накладная; Внутреннее перемещение → Перемещение товаров; Возвратная накладная → Возврат товаров поставщику. Muhim: **"создаваемые в 1С документы «ПКО» не замещаются, всегда создаются новые документы при повторной загрузке"**.
- **Ishga tushirish tartibi** (iiko-1): "Не загружайте одновременно все типы документов… Загрузите один тип документов. Отладьте их перенос. Проведите… Перейдите к следующему"; ketma-ketlik: kirim → qaytarish → ishlab chiqarish → ko'chirish → sotuv → hisobdan chiqarish; "Проводить документы" bayrog'ini faqat sozlash tugagach yoqish; **"Документы с номером более 11 символов и элементы номенклатуры с артикулом более 11 символов невозможно загрузить в 1С"**.
- Integrator ro'yxatidagi xatolar (open-s.info): hujjatlar o'tkazilmagan, smena yopilmagan, "Не настроено соответствие справочников… Результат — либо ошибка загрузки, либо дубли позиций", o'lchov birliklari (kg va dona) mos kelmaydi, kodirovka yoki format xatosi, **"После обновления 1С обработку загрузки тоже нужно обновить"**, **"Дубли документов. Возникают при повторной выгрузке пересекающихся периодов"** — https://open-s.info/blog/kak_vygruzit_dannye_iz_iiko_v_1s_poshagovaya_instruktsiya_nastroiki_i_oshibki/
- 1C tomonidan alternativa: 1С:Общепит'dagi "Загрузка продаж из iiko" qayta ishlashi — https://its.1c.ru/db/content/obshmod25/src/6.6.%20загрузка%20продаж%20из%20iiko.htm (yopiq, faqat qidiruv parchasi).

### 3.4 Kontur.Market → 1С (eng yaxshi UX namunasi)
- Konfiguratsiyalar: БП 3.0, УТ 11.4/11.5, УПП 1.3, КА 1.2; **"Интеграция недоступна при работе с облачной 1С"**. O'rnatish: modul yuklanadi → Marketda token olinadi → modul o'rnatilib token kiritiladi → tashkilot, savdo nuqtasi va o'lchov birliklari moslashtiriladi → kontragentlar va tovar guruhlari sozlanadi — https://support.kontur.ru/market/39527-nastrojka_integracii_modulya_marketa_s_1c
- Ish oqimi (https://support.kontur.ru/market/39523-zagruzka_v_1s_otchetov_o_prodazhax_vozvratax_i):
  - "Если в торговой точке несколько касс, отчет будет один, он запишется на одну из касс в 1С" — nuqtaga kuniga bitta ORP.
  - **"Товар в отчете будет иметь ставку НДС, которая указана в номенклатуре 1С"** — QQS 1C'dan olinadi, POS'dan emas.
  - Davr "не более месяца"; ma'lumot kunlar bo'yicha ko'rsatiladi; "Номенклатура 1С" va "Наименование" ustunlari yonma-yon turadi.
  - **"Показать только несопоставленные"** → **"Создать товар 1С"** → "Создать документ продажи в 1С".
  - **"Если в Маркете изменился отчет… «Перезаполнить документ продажи 1С»"** — dublikat yaratmasdan yangilaydi.
- Hisobdan chiqarish va qabul aktlari ham shu tartibda — https://support.kontur.ru/market/39526-zagruzka_aktov_spisaniya_i_postanovki_iz_marketa_v

### 3.5 r_keeper / StoreHouse Pro
- SH'dagi "Расходная накладная" ("Тип документа 1С = Розничная продажа", operatsiya nomi bo'yicha moslashtiriladi) 1C'da ORP bo'ladi, "в базовых единицах измерения"; naqdsiz to'lov bo'lsa "Платежные карты и банковские кредиты" bo'limi to'ldiriladi — https://docs.rkeeper.ru/sh5/otchet-o-roznichnyh-prodayoah-vygruzka-sh-pro-v-1s-2-0-19608572.html
- Alohida versiyalar: "Выгрузка в 1С 8 редакции 3.0.37+ Проф и Корп / Базовая / 2.0.66.64+ Базовая", "Выгрузка в 1С:Фреш" (o'sha sahifadagi menyu).
- Forum: SH4 dan eksport qilish uchun kalit (litsenziya) kerak — https://forum.infostart.ru/forum9/topic147235/

### 3.6 1С:Розница ↔ 1С:Бухгалтерия (1C'ning o'z standarti)
- 1С:Розница 2.3 qo'llanmasida "Обмен данными с конфигурацией «Бухгалтерия предприятия»" bo'limi bor — https://its.1c.ru/db/retaildoc/content/73/hdoc
- Qidiruv parchasi (sahifaning o'zi yopiq): "Переносится только Отчет о розничных продажах. Отчет о розничных возвратах, …, Чеки ККМ на возврат не переносятся" — https://its.1c.ru/db/content/metod81/src/appsolutionselffinanced/small%20business/data%20exchange/i8107984.htm (*parcha; kontekst — 1С:Розница/УНФ sinxronizatsiyasi; to'liq matn tekshirilmagan*).
- O'zbekiston versiyalari: «1С:Розница 8 для Узбекистана» — https://1c.uz/v8/generic_products/uz_retail.php ; «1С:Бухгалтерия 8 для Узбекистана» — https://1c.uz/v8/generic_products/uz_accounting.php ; УТ UZ hujjatlarida "Синхронизация данных" paneli bor — https://its.1c.eu/db/content/ukuz30/src/12.11.%20%D1%81%D0%B8%D0%BD%D1%85%D1%80%D0%BE%D0%BD%D0%B8%D0%B7%D0%B0%D1%86%D0%B8%D1%8F%20%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D1%85.htm
- UZ'dagi format muammosi: §2.4 (Infostart 1955638).

### 3.7 EnterpriseData (rasmiy)
- "Формат основан на XML и является бизнес-ориентированным"; almashinuv kanallari: "веб-сервис, файловый обмен через каталог, …через FTP, обмен через электронную почту"; "обеспечивает совместимость снизу вверх". Qo'llab-quvvatlovchilar ro'yxatida ERP 2, БП 3.0, Розница 2.0, УТ 11, ЗУП КОРП 3 bor; **UZ konfiguratsiyalari ro'yxatda yo'q** — https://v8.1c.ru/tekhnologii/obmen-dannymi-i-integratsiya/standarty-i-formaty/format-enterprisedata/
- Amalda "pastdan yuqoriga moslik" va'dasi ishlamagan holat: UZ'da УТ11 (1.8) → БП (1.5) — https://infostart.ru/1c/articles/1955638/

### 3.8 CommerceML / 1C-Bitrix
- 2000-yildan beri XML standart; asosan katalog va narxlar 1C → sayt, buyurtmalar sayt → 1C — https://v8.1c.ru/tekhnologii/obmen-dannymi-i-integratsiya/standarty-i-formaty/standarty-commerceml/ , https://v8.1c.ru/tekhnologii/obmen-dannymi-i-integratsiya/standarty-i-formaty/protokol-obmena-s-saytom/
- Kassaning kunlik savdosi uchun mos emas. Ba'zi integratorlar iiko uchun "CSV, XML, CommerceML" formatlarini sanaydi — open-s.info (yuqorida).

### 3.9 Wildberries/Ozon → 1С:БП
- БП ichida o'rnatilgan: "Продажи → Отчеты комиссионеров → Загрузить → Из личного кабинета…" — https://marketplace.is1c.ru/tpost ; ommaviy yuklash "Комиссионные продажи" ish joyidan — https://its.1c.ru/db/metod81/src/sales/marketplaces (parcha).
- Og'riq: "При первой загрузке… некорректно сопоставили номенклатуру с маркетплейсом, и теперь в отчете некорректно отражается" — https://buhexpert8.ru/voprosy/voprosy-1s-buhgalteriya/sopostavlenie-nomenklatury-pri-zagruzke-otchetov-rvb.html ; "неправильное сопоставление номенклатуры при загрузке… из личного кабинета ОЗОН" — https://www.buhonline.ru/forum/index?g=posts&t=839530
- O'zbekistonda Uzum va Yandex Market ↔ 1C integratsiyasini ham integratorlar qiladi — https://brix.uz/product/integratsiya-1s-s-marketpleysami-uzum-yandex-market , https://www.olx.uz/d/obyavlenie/1c-integratsiya-uzum-sayt-integratsiya-1s-s-uzum-i-saytom-ID4tAzN.html

### 3.10 OFD → 1C (RU)
- "Программа автоматически составит из загруженных чеков Отчет о розничных продажах и сделает все необходимые проводки" — https://portal.1c.ru/download/public/instruction/Instructions_1S-Cheki-OFD_UNF_Retail.pdf ; "Платформа ОФД" moduli: "отчёты о продажах в розницу с учетом системы налогообложения; приходные ордера…" — https://online-kassa.info/blog/servis-integratsiya-ofd-v-1s-ot-platformy-ofd-prosto-podklyuchit-i-legko-ispolzovat/
- O'zbekistonda OFD → 1C mahsuloti topilmadi (*taxmin*: bu bo'sh joy, lekin bizning manbamiz OFD emas, ERP'ning o'z cheklari).

---

## 4. Ma'lum og'riqli nuqtalar — jamlanma

| # | Muammo | Qayerda kuzatilgan | Ildiz sababi |
|---|---|---|---|
| P1 | **Nomenklatura dublikatlari** | MoySklad (nom → yangi kartochka), iiko ("дубли позиций"), MoySklad videosi, WB/Ozon moslashtirish | Birinchi moslashtirish nom bo'yicha; 1C havolasi (GUID) POS tomonda saqlanmaydi |
| P2 | **Hujjatlar takroran yuklanadi** | Evotor "за период", iiko ПКО, iiko kesishgan davrlar; buxgalterning "Сторно" bilan tuzatishi — https://buhexpert8.ru/voprosy/voprosy-1s-buhgalteriya/korrektirovka-otchetov-roznichnyh-prodazhah.html | Idempotentlik kaliti yo'q; davr bo'yicha qayta yuklash |
| P3 | **1C yangilanishi integratsiyani buzadi** | open-s.info ("обработку… нужно обновить"), Evotor sharhi (xato 400 → 11.5 ga yangilash), AkiTorg ("Обновление файла обработки/расширения", imzo kaliti) | `.epf` yoki kengaytma konfiguratsiya versiyasiga bog'liq |
| P4 | **Format versiyalari mos kelmaydi** | УТ11 UZ → БП UZ, EnterpriseData 1.8 va 1.5 — https://infostart.ru/1c/articles/1955638/ ; MoySklad QQS 5/7% → faqat 1.17 | Ikki konfiguratsiyani turli kompaniyalar yozadi; UZ versiyalari orqada qoladi |
| P5 | **Maydon uzunligi va formati** | MoySklad jadvali (Kod 11, Raqam 11, Nom 100), iiko (11 belgi) | 1C metadata cheklovlari |
| P6 | **Tuzilma talablari** | MoySklad: nuqta = alohida ombor, prefiks majburiy; Kontur: nuqtada bir nechta kassa → bitta kassa | 1C ORP modeli (ombor/kassa ККМ) |
| P7 | **ORP o'tkazilmaydi (manfiy qoldiq, bo'sh qatorlar)** | Infostart forum: "Контроль остатков не дает провести документ Отчет о розничных продажах" — https://forum.infostart.ru/forum81/topic234801/ ; AkiTorg: "пустые строки в Наименование, отчет не проводится" | Kirim 1C'ga sotuvdan keyin tushadi yoki umuman tushmaydi; moslashtirilmagan qatorlar |
| P8 | **QQS/soliq rejimi** | Kontur: QQS 1C nomenklaturasidan olinadi; AkiTorg: "Несколько магазинов с разным налогообложением" | Ikki tizimda turli manbalar |
| P9 | **Orqaga qarab o'zgarishlar** | BILLZ: "продажа может быть отредактирована или возвращена задним числом"; ai-it.uz: "ручные правки задним числом" | Davr muzlatilmagan |
| P10 | **Bulutdagi 1C bilan ishlamaydi** | Kontur: "недоступна при работе с облачной 1С" | Lokal modul/ulanish talab qilinadi |
| P11 | **Qaytarishlar yo'qoladi** | 1С:Розница→БП: qaytarish hujjatlari o'tmaydi (parcha) | Standart qoidalar cheklangan |
| P12 | **Mas'ul shaxs yo'q, xato jurnalini hech kim ko'rmaydi** | ai-it.uz tipik xatolar ro'yxati | Jarayon/UX muammosi |

---

## 5. Saboqlar va eng yaxshi amaliyotlar (bozordan)

1. **Kun yoki smena bo'yicha yig'ma ORP** — standart (Evotor, Kontur, iiko, Poster, Tusoft). Chek-chek eksport faqat aniq talab bo'lsa (ai-it.uz: "редко нужно… каждый чек").
2. **Sozlanadigan agregatsiya:** "kun" yoki "kassa smenasi" (Tusoft), nuqtaga bitta hisobot (Kontur).
3. **Avval moslashtirish, keyin hujjat:** "faqat moslashtirilmaganlar" ko'rinishi va "1C'da yaratish" tugmasi (Kontur); avtomatik yaratish bayrog'i (Poster). Moslashtirish tugamaguncha hujjat yaratilmaydi.
4. **POS tomonda 1C havolasini (GUID) saqlash.** Nom faqat birinchi moslashtirishda ishlatiladi (MoySklad'ning nom bo'yicha identifikatsiyasidan saboq).
5. **Qayta yuklash = yangilash, yangi hujjat emas** ("Перезаполнить документ продажи 1С" — Kontur; "перезаписывать документы" — Tusoft).
6. **Takroriy yuklashni nazorat qilish standart yoqilgan bo'lsin** (AkiTorg'da u ixtiyoriy bo'lgani uchun dublikatlar paydo bo'lgan).
7. **"Faqat yaratish" yoki "yaratish + o'tkazish" tanlovi** (Tusoft, iiko "Проводить документы"). Yangi mijozda avval yozib, keyin o'tkazish.
8. **Hujjat turlarini bosqichma-bosqich yoqish:** avval kirimlar, keyin sotuv, keyin hisobdan chiqarish (iiko tartibi; ai-it.uz: "Сначала… выручки по одной точке и проверьте её на прошедшем месяце").
9. **Belgilash:** yuklangan hujjatda `Комментарий` markeri bo'lishi kerak (Tusoft, Sonar).
10. **Xatolar jurnali va mas'ul shaxs:** har kuni ko'riladi; oyiga bir marta tizimlar solishtiriladi (ai-it.uz).
11. **Konfiguratsiyani o'zgartirmaslik** (Poster, A-System'dagi tashqi qayta ishlash) — 1C yangilanishlari xavfsiz qoladi.
12. **QQS manbasini aniq belgilash** (Kontur: 1C nomenklaturasidan).

---

## 6. Keng tarqalgan nosozliklar va ularning oldini olish (COM-agent nuqtai nazaridan)

| Nosozlik | Raqobatchilarda | Bizda COM-agent bilan oldini olish | Izoh |
|---|---|---|---|
| Dublikat hujjat | P2 | O'zimiz bergan GUID (`ПолучитьСсылку(UUID)` + `УстановитьСсылкуНового`), `Комментарий` markeri, agent jurnali, ERP'da `(baza, nuqta, sana/smena, tur)` bo'yicha unikal kalit | Texnikasi R6 §0 p.2 da. Qayta eksportda avval qidiramiz, topilsa **yangilaymiz** |
| Dublikat nomenklatura | P1 | Mapping jadvali `erp_item_id ↔ 1C Ref GUID`; nom faqat birinchi taklif uchun. Moslashtirish: shtrix-kod → artikul → kod → nom (taklif sifatida, inson tasdig'i bilan). Nom o'zgarishi havolaga ta'sir qilmaydi | COM orqali 1C ma'lumotnomasini **jonli o'qib**, yonma-yon solishtiruvchi ekran (Kontur UX) |
| 1C yangilanishi buzadi | P3 | 1C'da `.epf` yoki kengaytma **o'rnatilmaydi**; yangilash bizning agentda va serverda qilinadi. Har seansdan oldin **metadata preflight**: kerakli hujjat, rekvizit va jadval qismlari borligi tekshiriladi, konfiguratsiya nomi va versiyasi o'qiladi; noma'lum versiya bo'lsa → "sinov rejimi" va ogohlantirish | COM ham konfiguratsiya obyekt modeliga bog'liq — xavf yo'qolmaydi, faqat **erta aniqlanadi**. Profil "konfiguratsiya × reliz" bo'yicha (R6) |
| Format versiyasi | P4 | EnterpriseData ishlatilmaydi — COM to'g'ridan-to'g'ri obyektlar bilan ishlaydi | UZ BP'dagi EnterpriseData kechikishi bizga ta'sir qilmaydi |
| Maydon uzunligi | P5 | Eksportdan oldin 1C metadata'dan (`Метаданные…ДлинаКода`, `ДлинаНомера`, rekvizit turi) chegaralarni o'qib, ERP tomonda tekshirish; xato — aniq qator va maydon nomi bilan | Raqobatchilar xatoni 1C ichida, yozish paytida chiqaradi |
| Tuzilma (ombor, kassa ККМ, prefiks) | P6 | Onboarding ustasi: ERP filiali ↔ 1C `Склад` + `КассаККМ` + `Организация` + `Подразделение`; nuqtaga bitta yoki kassaga bitta ORP — sozlanadi | |
| Manfiy qoldiq, o'tkazilmagan ORP | P7 | Tartib: avval kirim, ko'chirish, keyin ORP. Preflight'da COM so'rovi bilan 1C qoldig'i o'qiladi va kamomad haqida ogohlantiriladi. Tanlov: "yozish, o'tkazmaslik" yoki "o'tkazish" | 1C qoldiq nazorati sozlamasini ham o'qish (*taxmin*: konfiguratsiyaga bog'liq) |
| QQS va soliq rejimi | P8 | Sozlama: QQS manbasi (ERP yoki 1C nomenklaturasi); farq bo'lsa — ogohlantirish | Bizning ERP'da QQS bor (qaror: 13-provodka) |
| Orqaga qarab o'zgarish | P9 | ERP'da smena yopilgach hujjat muzlatiladi; tuzatish faqat qaytarish yoki tuzatish hujjati bilan → keyingi eksportda yangi hujjat yoki eski hujjat yangilanadi. 1C'dagi "Дата запрета изменения" o'qiladi, yopiq davrga yozilmaydi | |
| Bulutdagi 1C | P10 | COM bilan **yetib bo'lmaydi** — onboarding'da aniqlab, ochiq aytiladi (agent hosting serveriga o'rnatilishi — *taxmin*, hosting provayderiga bog'liq; masalan UZ'dagi Clobus — https://t.me/s/Clobus_uz?before=360 ) | Raqobatchilar (Kontur) ham qo'llamaydi |
| Qaytarishlar | P11 | Qaytarishlar alohida hujjat sifatida eksport qilinadi (konfiguratsiyaga qarab ORP'da manfiy qator yoki "Возврат товаров от покупателя", *taxmin*, R6 bilan aniqlanadi) | |
| Jurnalni hech kim ko'rmaydi | P12 | Har kuni Telegram'ga xulosa: "N hujjat yozildi, M xato — moslashtiring"; BO'da eksport holati ekrani; mas'ul rol | Sonar digest naqshi |
| Kompyuter o'chiq yoki 1C band | COM'ga xos | Navbat va "catch-up": agent yoqilganda o'tkazib yuborilgan kunlar eskidan yangiga qarab yoziladi; har vazifa idempotent | R4 pull arxitekturasi |
| "Базовая" versiya, COM ro'yxatdan o'tmagan, 32/64-bit | COM'ga xos | Onboarding'dagi 1-tekshiruv: platforma, `comcntr`, versiya turi; "Tuzatish" tugmasi (Sonar naqshi) | Базовая COM'ni qo'llamaydi — R6 §7 |

---

## 7. COM-agent yondashuvining bozordagi o'rni (raqobatchilar bilan solishtirish)

| Mezon | `.epf` / kengaytma (Evotor, Kontur, Poster, iiko) | Fayl (MoySklad EnterpriseData, iiko CSV) | **Bizning COM-agent** |
|---|---|---|---|
| 1C ichiga o'rnatish | Kerak (har yangilanishda qayta) | Kerak emas, lekin import qo'lda | **Kerak emas** |
| Avtomatlashtirish | 1C ochiq bo'lganda yoki 1C jadvali bilan | Qo'lda | Agent jadvali bo'yicha, 1C yopiq bo'lsa ham (fon seansi) |
| Bulutdagi 1C | Ba'zilarida bor (Fresh) | Fresh — to'g'ridan-to'g'ri (MoySklad) | **Yo'q** (zaif tomon) |
| Konfiguratsiya mantiqi (hisoblar, QQS to'ldirish) | 1C ichida, tabiiy | 1C qoidalari bilan | COM'da forma hodisalari ishlamaydi — o'zimiz to'ldiramiz yoki 1C'ga vaqtincha `.epf` yuklaymiz (R6 §0 p.4, §8) |
| Yozishdan oldin tekshiruv | Yo'q (xato yozish paytida) | Yo'q | **Bor** (metadata, qoldiq, yopiq davr, uzunlik) |
| Yozishdan keyin tekshiruv | Kam | Yo'q | **O'qib solishtirish** (summalar, qatorlar) |
| Litsenziya | 1C foydalanuvchisi seansi | — | COM seans litsenziya egallaydi (R6 §7, *taxmin*) — qisqa seanslar |

**Xulosa:** COM'ning bozordagi asosiy ustunligi — **1C tomonda hech narsa o'rnatilmaydi va yangilanmaydi** hamda **preflight + reconciliation**. Asosiy zaif tomonlari — bulutdagi 1C va "Базовая" versiyalar. Bu cheklovlar sotuvdan oldin aytilishi va onboarding'ning birinchi qadamida tekshirilishi kerak.

---

## 8. Bizning integratsiyani aniq yaxshiroq qiladigan ustunliklar

1. **«Бухгалтерия для Узбекистана 3.0» birinchi navbatda.** Ko'rib chiqilgan POS mahsulotlarining birortasida UZ BP uchun hujjatlashtirilgan tayyor konnektor topilmadi (iiko — BP 2.0/3.0 RU; Poster — UA/BAS/УПП; Evotor/Kontur — RU; MoySklad — EnterpriseData, UZ BP'da versiya muammosi bor) (*taxmin*, to'liq bozor tekshirilmagan).
2. **Tarifga kiritilgan.** Evotor'dagi 630 ₽/oy/terminal yoki UZ integratorining 5–20 mln so'mi o'rniga "1C eksporti" tarif ichida (yoki arzon qo'shimcha) bo'ladi.
3. **1C'ga hech narsa o'rnatilmaydi** (COM-agent): `.epf` yoki kengaytmani yangilash, imzo kaliti, "обработку нужно обновить" muammolari yo'q.
4. **Dublikatlar kafolatli yo'q:** o'zimiz bergan GUID + marker + ERP'dagi unikal kalit; qayta eksport hujjatni yangilaydi. Marketingda: "Bitta kun — bitta hujjat. Qayta yuborsangiz ham ikkita bo'lmaydi".
5. **Nomenklatura dublikatlari yo'q:** mapping GUID'da saqlanadi; nom o'zgarsa ham bog'lanish saqlanadi; shtrix-kod bo'yicha avtomatik taklif; "faqat moslashtirilmaganlar" ekrani; "1C'da yaratish" — **faqat tasdiq bilan** (Sonar: "taxmin qilinmaydi").
6. **Preflight hisoboti** eksportdan oldin: uzunliklar, ombor/kassa xaritasi, yopiq davr, manfiy qoldiq xavfi, moslashtirilmagan pozitsiyalar — hammasi bitta ekranda, o'zbek tilida, keyingi aniq qadam bilan.
7. **Preview va tasdiq** (birinchi haftalarda yoki summa chegarasidan oshganda): "1C'da quyidagi hujjatlar yaratiladi" ro'yxati; buxgalter tasdiqlaydi; rol tekshiriladi (Sonar'ning zaif joyi takrorlanmaydi).
8. **Reconciliation:** yozilgandan keyin COM orqali o'qib, ERP summasi bilan solishtirish (kun × nuqta × to'lov turi: naqd, karta, Click, Payme, Uzum). Farq bo'lsa — ogohlantirish.
9. **Davrni muzlatish va tuzatish oqimi:** ERP'da yopilgan smena o'zgarmaydi; tuzatish alohida hujjat bilan qilinadi va 1C'ga yangilanish sifatida boradi. Buxgalter 1C'da "Сторно" qilmaydi.
10. **Qaytarishlar, kassa (ПКО) va to'lov turlari** to'liq: 1С:Розница→БП standart almashinuvidagi bo'shliq (qaytarishlar o'tmasligi) yopiladi.
11. **Kunlik Telegram xulosasi** (yozildi / xato / moslashtirish kerak) va BO'da eksport tarixi — "jurnalni hech kim ko'rmaydi" muammosiga yechim.
12. **Bosqichma-bosqich yoqish ustasi:** avval 1 nuqta va o'tgan oy (sinov, "yozish, o'tkazmaslik"), solishtirish, keyin avtomatik rejim (iiko va ai-it.uz tajribasi mahsulotga aylanadi).
13. **Halol cheklovlar:** bulutdagi 1C va "Базовая" versiya onboarding'ning birinchi ekranida aniqlanadi — "ulandi, lekin ishlamaydi" holati bo'lmaydi.

---

## 9. Ochiq savollar va tasdiqlanmagan joylar

1. BILLZ, E-POS, Rahmat, Smartup aslida 1C'ga qanday hujjat yozadi? (ochiq hujjat yo'q; demo yoki mijoz suhbati kerak) — *taxmin*: integrator `.epf` orqali.
2. MoySklad.uz eksportini «Бухгалтерия для Узбекистана» hozir (2026) qabul qiladimi? — sinov bazasida tekshirish kerak.
3. 1С:Розница UZ → БП UZ standart almashinuvida qaytarishlar o'tadimi? (ИТС sahifasi yopiq, faqat parcha bor; RU kontekstida).
4. UZ'dagi bulutli 1C (Clobus va boshqalar) ulushi qancha? Agar katta bo'lsa, COM-only qaror sotuvga ta'sir qiladi — bozor tadqiqoti kerak.
5. "Soliq kassa" / virtual kassa ilovalarida 1C eksporti bormi — ma'lumot topilmadi.
6. Evotor sharhlarining umumiy statistikasi (812 ta sharh) tahlil qilinmadi; faqat ko'ringan 5–8 ta sharh keltirildi.

---

## 10. Manbalar (asosiylar)

- BILLZ: https://billz.io/integration · https://docs.billz.io/guides/sales-export/ · https://docs.billz.io/start/scenarios/
- REGOS: https://regos.uz/ru/blog/sistema-regos/sovmestnaya-rabota-servisa-regos-i-1c · https://regos.uz/ru/blog/sistema-regos/agregatsiya-v-sisteme-regos-podvedenie-itogov-po-prodazham-i-platezham · https://apps.regos.uz/
- Smartup: https://www.greenwhite.uz/smartup · https://www.gazeta.uz/ru/2019/07/22/smartup/ · https://ba-it.uz/product/sobstvennye-resheniya/dlya-malogo-i-srednego-biznesa/integratsiya-1s-s-smart-up-dlya-distribyutorskikh-kompaniy/
- MoySklad: https://www.moysklad.uz/integratsii/apps/1s-bukhgalteriya/ · support.moysklad.ru maqolasi (to'liq URL §1 jadvalida) · https://www.moysklad.uz/
- iiko: https://ru.iiko.help/articles/iikochain-8-0/topic-780 · https://ru.iiko.help/articles/iikochain-8-0/topic-786 · https://ru.iiko.help/articles/iikochain-8-0/iiko-1 · https://open-s.info/blog/kak_vygruzit_dannye_iz_iiko_v_1s_poshagovaya_instruktsiya_nastroiki_i_oshibki/ · https://ai-it.uz/blog/integraciya-ayko-s-1s · https://kafesoft.uz/ru/technicalsupport/
- Poster: https://joinposter.com/applications/1c-integration · https://joinposter.com/tour/addons/1c-integration · https://knowledge-base.joinposter.com/ru/how-to-integrate-poster-with-1c-enterprise-management-1.3
- Evotor: https://market.evotor.ru/store/apps/79aaebe4-9238-4cc3-8224-95efc8d3f0ab · https://market.evotor.ru/store/apps/bd84ea6e-c4b8-438a-b2be-efe62b9da912 · https://tusoft.ru/support-evotor-1c/category/obmen-s-1c/nachalo-raboty-s-obmenom-s-1s-registraciya-i-obnovlenie-modulya/dopolnitelnyj-modul-obmen-s-1s/ · AkiTorg wiki (URL'lar §3.1 da) · https://forum.infostart.ru/forum72/topic255515
- Kontur.Market: https://support.kontur.ru/market/39523-zagruzka_v_1s_otchetov_o_prodazhax_vozvratax_i · https://support.kontur.ru/market/39527-nastrojka_integracii_modulya_marketa_s_1c
- r_keeper: https://docs.rkeeper.ru/sh5/otchet-o-roznichnyh-prodayoah-vygruzka-sh-pro-v-1s-2-0-19608572.html
- 1C standartlari: https://v8.1c.ru/tekhnologii/obmen-dannymi-i-integratsiya/standarty-i-formaty/format-enterprisedata/ · https://v8.1c.ru/tekhnologii/obmen-dannymi-i-integratsiya/standarty-i-formaty/standarty-commerceml/ · https://its.1c.ru/db/retaildoc/content/73/hdoc · https://infostart.ru/1c/articles/1955638/
- Og'riqlar: https://buhexpert8.ru/voprosy/voprosy-1s-buhgalteriya/korrektirovka-otchetov-roznichnyh-prodazhah.html · https://forum.infostart.ru/forum81/topic234801/ · https://buhexpert8.ru/voprosy/voprosy-1s-buhgalteriya/sopostavlenie-nomenklatury-pri-zagruzke-otchetov-rvb.html
- UZ boshqalar: https://epos.uz/integrations · https://ba-it.uz/product/sobstvennye-resheniya/dlya-malogo-i-srednego-biznesa/obmen-1s-s-virtualnymi-kassami-e-pos-arka-/ · https://rhmt.uz/pos/integration/ · https://www.gazeta.uz/ru/2026/08/06/rahmat/ · https://docs-virtual-kassa.multibank.uz/ · https://bit-box.uz/uz/uslugi/1c-integratsiya/ · https://leading.uz/articles/integratsiya_1s_s_natsionalnymi_platezhnymi_sistemami_click_payme_i_uzum/
- Sonar: `research_notes/sonar-1c-integratsiya/00-xulosa.md`, `04-1c-ga-yozish-va-tasdiqlash.md`, `05-mahsulot-funksiyalari-va-server-api.md`
