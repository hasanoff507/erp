# R2 — O'zbekistondagi 1C konfiguratsiyalari va chakana savdo ma'lumotlari 1C ichida qanday ko'rinishi kerak

> **Yakuniy tavsiya ustun (accept gate, 2026-10-15):** shu papkadagi fayllar orasidagi ziddiyatlar `00-xulosa.md` da hal qilingan (§«Hal qilingan ziddiyatlar»). Bu fayl bilan `00-xulosa.md` farq qilsa — **00-xulosa'dagi yakuniy tavsiya ustun**. Kanonik nomlar: jadvallar — `04` §3.3; idempotentlik algoritmi — `04` §5.3; maydon xaritalari va ketma-ketlik — `03` §3, §5.1.

**Holat:** 2026-10-15, tadqiqot (R2). Hech narsa publish qilinmagan.
**Kim uchun:** ERP «1C integratsiyasi» bo'limi (kun/smena oxirida ERP'dagi savdo va boshqa operatsiyalarni do'konning o'z 1C bazasiga tartib bilan yozish).
**Asoschi qarori (koordinator orqali):** yozish kanali — **faqat COM, Windows agenti orqali**. OData, veb-publikatsiya, 1C tomonda hech narsa nashr qilinmaydi. Shu sababli bu hujjat OData/veb-servis jihatlarini ko'rib chiqmaydi.
**Belgilar:** har bir faktdan keyin manba `[Mx]` (oxirida ro'yxat). *taxmin* — manba bilan tasdiqlanmagan, mantiq yoki Rossiya «Бухгалтерия предприятия 3.0» (БП 3.0) analogiyasi bo'yicha xulosa; pilotda haqiqiy bazada tekshirilishi shart.

**Cheklov:** 1C:ИТС'dagi «Бухгалтерия для Узбекистана 3.0» qo'llanmasining **mundarijasi** ochiq (bo'lim va kichik bo'lim nomlari, operatsiya turlari ro'yxati) — undan foydalanildi `[M1]`. Bo'limlarning **matni** obuna (401) ortida — o'qilmadi. Shuning uchun metadata nomlari (`Документ.ОтчетОРозничныхПродажах` va h.k.) va rekvizitlar ro'yxati — Rossiya БП 3.0 analogiyasi bo'yicha *taxmin*. Integratsiya kodi ularni **qattiq yozmasligi**, balki ulanishda bazaning metadata'sidan o'qib xarita tuzishi kerak (8-bo'lim).

---

## 0. Qisqa xulosa (10 band)

1. O'zbekistonda «1С» (Firma 1C) rasmiy tipovoy mahsulotlari: **Бухгалтерия 8 для Узбекистана (ред. 3.0)**, **Бухгалтерия 8 КОРП МСФО для Узбекистана**, **Управление торговлей 8 для Узбекистана** (faqat ПРОФ), **Управление компанией 8 для Узбекистана**, **Розница 8 для Узбекистана (ред. 3.0)**, ЗУП (ПРОФ/КОРП) `[M2][M3][M4][M5][M6]`. «Комплексная автоматизация» va «ERP» O'zbekiston uchun tipovoylar ro'yxatida yo'q `[M2]`.
2. Joriy relizlar (1C:ИТС its.1c.eu yangiliklar lentasi; accept gate WebFetch bilan qayta tekshirildi — e'lon sanalari **2026-yil iyul**: БП UZ 3.0.64.8 — 14.07, УТ UZ 11.0.0.24 — 12.07, Розница UZ 3.0.17.1 — 24.07): БП Узбекистан **3.0.64.8**, УТ Узбекистан **11.0.0.24**, Розница Узбекистан (va «базовая») **3.0.17.1**, Управление компанией Узбекистан **3.0.17.1** `[M7]`. Pilotdan oldin ИТС'da yangi reliz bor-yo'qligi qayta qaralsin.
3. Kichik/o'rta do'konlarda **asosiy nishon — «Бухгалтерия для Узбекистана 3.0»** (buxgalteriya va soliq hisoboti aynan shu yerda; Sonar ham faqat shunga mo'ljallangan `[M8]`). УТ/Розница/УК — ikkinchi navbat (*taxmin*, bozor ulushi bo'yicha ochiq statistika topilmadi).
4. БП Узбекистан 3.0 tuzilishi Rossiya БП 3.0 bilan deyarli bir xil: «Розничная торговля» bo'limida **«Продажи в розничном магазине»** (avtomatlashtirilgan nuqta, ОРП) va **НТТ** (xarid narxi yoki sotish narxi bo'yicha) rejimlari; «Поступление наличных» → **«Розничная выручка»**; «Поступление на расчетный счет» → **«Поступления от продаж по платежным картам и банковским кредитам»**; alohida **«Операции по платежным картам»** hujjati; **«Корректировка задолженности»**; **«Дата запрета изменения данных»** `[M1]`.
5. **Tavsiya etilgan chakana model:** har kun (yoki smena) × har ombor (do'kon) × har kassa uchun **bitta «Отчет о розничных продажах» (ОРП)** — tovar qatorlari jamlangan, naqd va naqdsiz (karta/QR/Click/Payme) to'lovlar alohida. Cheklar 1C'ga alohida yuborilmaydi (1C'da «Чек ККМ» БП'da yo'q, УТ/Розница'da esa fiskal qurilma bilan bog'liq — undan qochish kerak).
6. Hisob raqamlari (NSBU №21, 191-son buyruq, 2024-12-27 ro'yxatdan o'tgan, rasmiy matn lex.uz'da o'qildi) `[M9]`: tovar — **2910** (ombor) / **2920** (chakana savdo) / **2980** (savdo ustamasi, sotish narxida hisoblaganda); daromad **9020**, qaytarish **9040**, chegirma **9050**, tannarx **9120**; kassa **5010**, bank **5110**, **5710** «Yo'ldagi pul mablag'lari (o'tkazmalar)» — rasmiy ta'rifi bo'yicha karta/terminal tushumlari bankka tushguncha shu tranzit hisobda turishi mantiqiy; QQS — **6410** (byudjetga qarz), kiritiladigan QQS — **4410**; debitorlar **4010**, kreditorlar **6010**.
7. **Karta/QR/Click/Payme:** ОРП'ning «безналичные оплаты» qismi orqali «вид оплаты» → 5710 (yoki buxgalter tanlagan boshqa hisob), keyin bank ko'chirmasida «Поступление на р/с — по платежным картам» 5110 ↔ 5710 yopiladi, komissiya xarajatga. bss.uz amaliy maqolasi ham chakana tushumni `Дт 5010, 5711, 4010 Кт 9020` deb ko'rsatadi `[M10]`.
8. **Nasiya** (aniq xaridorga qarzga sotish): ОРП'ga sig'maydi — alohida **«Реализация товаров и услуг»** (kontragent = jismoniy shaxs, ПИНФЛ bilan) → 4010. Qarzni to'lashi — «Поступление наличных: Оплата от покупателя» yoki bank. (*taxmin*, ammo hujjat va operatsiya turlari `[M1]` mundarijasida bor.)
9. **Tannarx (COGS):** 1C o'zi hisoblaydi — БП Узбекистанда tovar baholash usuli **FIFO yoki o'rtacha** (hisob siyosati) `[M3][M1]`, oy yopishda «Корректировка стоимости номенклатуры» va (sotish narxida bo'lsa) «Расчет торговой наценки» `[M1]`. **Tavsiya:** 1C ichida buxgalteriya tannarxining manbasi — 1C'ning o'zi; ERP tannarxni 1C'ga yubormaydi, faqat miqdor va summalarni; ERP tannarxi — boshqaruv hisobi. Farqni solishtirish hisoboti kerak.
10. **Дата запрета изменения данных** (1C xizmati, `[M1]` 15.2.4) yopilgan davrga yozishni bloklaydi — kechikkan yuborish xatoga tushadi. ERP: (a) yuborishdan oldin sanani tekshirish, (b) bloklangan paketni «buxgalter qarori kerak» holatiga o'tkazish (davrni ochish yoki joriy sanaga tuzatuvchi hujjat), hech qachon jimgina sanani o'zgartirmaslik.

---

## 1. O'zbekistonda ishlatiladigan 1C konfiguratsiyalari

### 1.1 Rasmiy tipovoy mahsulotlar (Firma «1С», 1c.uz)

| Konfiguratsiya | Tahrir / joriy reliz | Ishlab chiquvchi | Chakana savdoga aloqasi | Manba |
|---|---|---|---|---|
| **1С:Бухгалтерия 8 для Узбекистана** | ред. 3.0; reliz **3.0.64.8** (ИТС, 2026-oktabr), oldingi 3.0.64.5, 3.0.64.1 | Firma «1С» | «Для розничной торговли поддерживается как оперативное отражение розничной реализации, так и отражение продаж по результатам инвентаризации»; zaxira baholash — o'rtacha va FIFO; QQS bo'yicha alohida hisob; ESF, ЭТТН, gibrid ESF | `[M3][M7]` |
| 1С:Бухгалтерия 8 КОРП МСФО для Узбекистана | bitta tahrir | Firma «1С» | MSFO parallel hisob; chakana bo'yicha qo'shimcha narsa yo'q | `[M4]` |
| **1С:Управление торговлей 8 для Узбекистана** | faqat **ПРОФ**; reliz **11.0.0.24** (ИТС, 2026-oktabr) | Firma «1С» | ekvayring («регистрация отчетов от банков по зачислению платежей, списанию возвратов, удержанию комиссии»), chakana narxda hisob; **«предусмотрена возможность выгрузки данных на уровне первичных документов в конфигурацию "Бухгалтерия для Узбекистана"»** | `[M5][M7]` |
| **1С:Розница 8 для Узбекистана** | ред. 3.0; reliz **3.0.17.1** (+ «базовая» 3.0.17.1, 2026-sentabr) | Firma «1С» | kassir ish o'rni (РМК), fiskal registratorlar, karta/kredit/sertifikat bilan to'lov; «в связке с программами "1С:Бухгалтерия 8"» | `[M6][M7]` |
| **1С:Управление компанией 8 для Узбекистана** | ПРОФ; reliz **3.0.17.1** (2026-sentabr) | Firma «1С» | savdo uskunalari, chakana narxdagi sotuv hisoboti, «учет операций по платежным картам (операции эквайринга)»; БП bilan almashuv sahifada aytilmagan | `[M11][M7]` |
| 1С:ЗУП для Узбекистана (ПРОФ/КОРП) | 3.1.24.1 / 3.1.37.1 | Firma «1С» (КОРП uchun hamkor LEADING BUSINESS SOFTWARE muvofiqlik sertifikati) | yo'q (ish haqi) | `[M2][M7][M12]` |

Izohlar:
- «Управление компанией для Узбекистана» va «Розница для Узбекистана» bir xil reliz raqamida (3.0.17.1) chiqadi — umumiy kod bazasi (Rossiyadagi УНФ/Розница 3.0 oilasi) ekanini ko'rsatadi (*taxmin*). Sonar ham «УНФ 3.0» uchun alohida oy yopish chaqiruvini saqlaydi `[M8]`, ya'ni amaliyotda УНФ-oilasi bazalari uchraydi.
- 1C:ИТС ro'yxatida УТ Узбекистан uchun ilgari `TradeUz` nomli liniya ko'rinadi; joriy versiya raqami 11.0.0.24 — yangi, «yosh» liniya (*taxmin*: УТ 11 asosidagi O'zbekiston lokalizatsiyasi nisbatan yaqinda qayta chiqarilgan).
- «Комплексная автоматизация» va «ERP» O'zbekiston tipovoylari ro'yxatida yo'q `[M2]`; 1c.uz bosh sahifasida umumiy «1C:ERP» havolasi bor, lekin «для Узбекистана» sifatida emas `[M13]`.
- Eski **БП Узбекистан 1.5** uchun ham ИТС'da qo'llanma bor `[M14]` — eski bazalar hali uchrashi mumkin (*taxmin*). Bizning integratsiya **faqat 3.0** ni qo'llab-quvvatlashi kerak (1.5 — oddiy formalar, boshqa obyekt modeli).

### 1.2 Bozor ulushi (kichik/o'rta do'konlar) — *taxmin*

Ochiq statistika topilmadi. Bilvosita belgilar:
- Bulutli ijara xizmatlari (uzcloud.uz, clobus.uz — «1С:Фреш») faqat 2–3 konfiguratsiyani taklif qiladi: **Бухгалтерия для Узбекистана**, **Управление компанией (для Узбекистана 3.0)**, **Розница для Узбекистана 3.0** `[M15][M16]` — talab shu uchtasida ekanini ko'rsatadi.
- Sonar (raqobatchi) faqat «Бухгалтерия для Узбекистана, ред. 3.0» ga mo'ljallangan `[M8]`.
- Hamkor saytlarida (koderline.uz) УТ 11 для Узбекистана bo'yicha ko'p maqolalar bor `[M17]` — o'rta savdo korxonalarida УТ ishlatiladi.

Taxminiy manzara (*taxmin*, pilotda so'rovnoma bilan tekshirish kerak): kichik do'konlarning buxgalteriyasi bor bo'lsa — ~70–80% **БП Узбекистан 3.0** (ko'pincha autsors buxgalterning kompyuterida yoki uning serverida); savdo/ombor uchun alohida 1C (УТ/Розница/УК) — ozchilik, ular odatda allaqachon boshqa POS bilan ishlaydi. «O'zi yozilgan»/franchayzi konfiguratsiyalar (БП asosida qayta ishlangan) uchraydi — ular uchun metadata-xarita (8-bo'lim) majburiy.

### 1.3 Baza turi va platforma

- **Fayl bazasi** — kichik biznes va autsors buxgalterlarda eng ko'p tarqalgan (*taxmin*); Sonar ham `File=` va `Srvr=+Ref=` bazalarni qo'llab-quvvatlaydi, `ws=` (veb) bazalarni chiqarib tashlaydi `[M8]`.
- **Server** (1C:Предприятие server + MS SQL/PostgreSQL) — o'rta korxonalarda.
- **Bulut (1С:Фреш / uzcloud / clobus)** — brauzer orqali, «только типовые конфигурации, доработки не поддерживаются» `[M15]`. **Muhim:** asoschi qarori bo'yicha yozish faqat COM orqali bo'lgani uchun, bulutdagi Fresh bazasiga bizning Windows agentimiz COM bilan ulana olmaydi (*taxmin*: Fresh'da COM-connector mijozga berilmaydi). Bunday mijozlar uchun yo'l: «Перенос данных между локальной версией и сервисом» `[M1]` 15.8 — ya'ni lokal nusxa — yoki qo'llab-quvvatlanmaydi deb belgilash. **Ochiq savol asoschiga.**
- **Platforma:** 1С:Предприятие 8.3 (barcha mahsulot sahifalarida «1С:Предприятие 8») `[M3][M5][M6]`; aniq minimal versiya relizlar sahifasida (login ortida). COM-connector: `V83.COMConnector` (32/64 bit) — Sonar shuni ishlatadi `[M8]`. 8.5 platformasi bo'yicha O'zbekiston konfiguratsiyalari uchun ma'lumot topilmadi.

---

## 2. «Бухгалтерия для Узбекистана 3.0» — chakana savdo uchun obyektlar

### 2.1 Qo'llanma mundarijasidan tasdiqlangan faktlar `[M1]`

1C:ИТС: «1С:Бухгалтерия для Узбекистана. Редакция 3.0. Руководство по ведению учета» — tegishli bo'limlar:

- **4.2.1.2 «Учет товаров в рознице»**, **4.3.3 «Способ оценки товаров в рознице»** (xarid narxi yoki sotish narxi), **4.3.2 «Способ оценки МПЗ»**, **4.3.8 «Учет себестоимости продаж»**, **4.2.13 «НДС»**, **4.2.8 «Настройки налогового учета»**, **4.2.15** «Показывать продажу ниже себестоимости…».
- **5.1.3 «Кассы»**; **5.2.5 «Поступление на расчетный счет»** — operatsiya turlari: Оплата от покупателя, Возврат от поставщика, Инкассация, **Поступления от продаж по платежным картам и банковским кредитам**, Прочие поступления va b.
- **5.3.2 «Поступление наличных»** — turlari: Оплата от покупателя, **Розничная выручка**, Прочая выручка, Получение наличных в банке, Прочий приход va b.; **5.3.3 «Выдача наличных»** — Оплата поставщику, **Возврат покупателю**, **Взнос наличными в банк**, **Инкассация**, Прочий расход va b.
- **5.3.5 «Операции по платежным картам»**.
- **6.1.1 «Справочник контрагентов»**, 6.1.2 «Договоры контрагентов», **6.1.7 «Корректировка задолженности»** (Зачет аванса, Зачет задолженности, Перенос задолженности, **Списание задолженности**, Прочие корректировки), 6.1.9 «Акт сверки».
- **6.2.3 «Поступление (акты, накладные)»** (+ «Регистрация счетов-фактур полученных»), 6.2.6 «Возврат товаров поставщику», 6.2.7 «Корректировка поступления».
- **6.3.2 «Реализация товаров и услуг»** (+ «Счет-фактура выданный»), **6.3.4 «Возврат товаров от покупателя»**, 6.3.5 «Корректировка реализации».
- **6.3.8 «Розничная торговля»**: «Продажи в розничном магазине»; «Продажи в неавтоматизированных торговых точках (учет по стоимости приобретения)»; «… (учет по продажной стоимости)».
- **6.4** ЭДО (ESF); **7** «Учет маркировки» (Asl belgisi: kodlarni hujjatga kiritish, o'tkazishda kodlar soni va dublikat tekshiruvi — 7.3.4).
- **8.1.1 «Справочник Номенклатура»**, 8.1.2 «Номенклатурные группы», **8.1.3 «Установка счетов учета номенклатуры»**, 8.1.4 «Установка цен», **8.1.5 «Переоценка товаров в рознице»**; **8.2.2 «Перемещение товаров»**; **8.4.1 «Инвентаризация товаров на складах»**, **8.4.2 «Оприходование товаров»**, **8.4.4 «Списание товаров»**.
- **12.1.2 «Сторно документа»**; **12.2 «Закрытие месяца»**: 12.2.6 **«Корректировка стоимости номенклатуры»**, 12.2.8 **«Расчет торговой наценки по проданным товарам»**, 12.2.11 «Определение финансовых результатов».
- **15.2.4 «Дата запрета изменения данных»**; 15.7 «Настройки синхронизации данных»; 15.8 «Перенос данных между локальной версией и сервисом».

Sonar'ning demo hisob rejasi ham shu kodlarni ishlatadi: 2910 «Товары на складе» (subkonto Номенклатура, Склады), 4010, 5010, 5110, 5530, 6010, 6410 «Задолженность по НДС», 9020, 9120 `[M8]` (demo ma'lumot — mustaqil isbot emas, faqat mos kelishi).

### 2.2 ERP voqeasi → 1C hujjati xaritasi

Metadata nomlari — Rossiya БП 3.0 analogiyasi (*taxmin*). Sonar'ning o'zida ham kassa kirimi uchun ikki xil nom uchraydi: demo'da `Документ.ПриходныйКассовыйОрдер`, mock'da `Документ.ПоступлениеНаличных` `[M8]` — ya'ni **nom bazadan o'qilishi kerak**, sinonim («Поступление наличных») bo'yicha qidirish zaxira yo'l.

| ERP voqeasi | 1C hujjati (sinonim, `[M1]`) | Kutilgan metadata nomi (*taxmin*) | Asosiy rekvizitlar (*taxmin*, БП 3.0 analog) | Provodka (NSBU 21 `[M9]`) |
|---|---|---|---|---|
| Kunlik/smenalik chakana savdo (naqd + karta) | Отчет о розничных продажах («Продажи в розничном магазине») | `ОтчетОРозничныхПродажах` | Шапка: Дата, Организация, **Склад** (turi «розничный магазин»), **КассаККМ**, Счет кассы, Подразделение. ТЧ «Товары»: Номенклатура, Количество, Цена, Сумма, **СтавкаНДС**, СуммаНДС, Счет учета, Счет доходов. ТЧ «Безналичные оплаты»: **ВидОплаты**, Сумма | Дт 5010 / Дт 5710 (karta) — Кт 9020; QQS — Кт 6410; tannarx Дт 9120 — Кт 2920 (yoki 2910) |
| Naqd tushum kassaga (ОРП bo'yicha) | Поступление наличных → «Розничная выручка» | `ПриходныйКассовыйОрдер` / `ПоступлениеНаличных` | Касса, Склад, Сумма, Статья ДДС | Avtomatik nuqtada ОРП kassani allaqachon debetlaydi — ПКО provodka bermasligi mumkin (БП 3.0 RU'da shunday `[M18]`) — *taxmin* |
| Karta/QR tushumi bankka tushdi | Поступление на расчетный счет → «Поступления от продаж по платежным картам и банковским кредитам» | `ПоступлениеНаРасчетныйСчет` | БанковскийСчет, Контрагент (bank/ekvayer), ВидОплаты, Сумма, Комиссия | Дт 5110 — Кт 5710; komissiya Дт 94xx — Кт 5710 |
| Karta operatsiyasi (alohida qayd) | Операции по платежным картам | `ОплатаПлатежнойКартой` | ВидОплаты, Сумма, ВидОперации («Розничная выручка»/«Оплата от покупателя») | Дт 5710 — Кт 4010 yoki chakana tushum (*taxmin*) |
| Nasiya (aniq xaridorga) | Реализация товаров и услуг | `РеализацияТоваровУслуг` | Контрагент, **Договор** (с покупателем), Склад, ТЧ Товары (СтавкаНДС, Счет учета), Счет расчетов 4010 | Дт 4010 — Кт 9020, Кт 6410; Дт 9120 — Кт 29xx |
| Nasiya to'lovi | Поступление наличных «Оплата от покупателя» / Поступление на р/с «Оплата от покупателя» | `ПриходныйКассовыйОрдер` / `ПоступлениеНаРасчетныйСчет` | Контрагент, Договор, Сумма, Документ расчетов | Дт 5010/5110 — Кт 4010 |
| Qaytarish (o'sha kuni) | ОРП ichida manfiy miqdor (*taxmin*, БП 3.0 RU amaliyoti) yoki alohida hujjat | — | — | Дт 9040 — Кт 5010… |
| Qaytarish (oldingi kun cheki) | Возврат товаров от покупателя + Выдача наличных «Возврат покупателю» | `ВозвратТоваровОтПокупателя`, `РасходныйКассовыйОрдер`/`ВыдачаНаличных` | Контрагент («Розничный покупатель» yoki aniq shaxs), Договор, asos hujjat | Дт 9040, Дт 6410 — Кт 5010/4010; Дт 29xx — Кт 9120 |
| Tovar kirimi | Поступление (акты, накладные) | `ПоступлениеТоваровУслуг` | Контрагент (STIR), Договор, Склад, ТЧ Товары (Номенклатура, Кол-во, Цена, СтавкаНДС, СуммаНДС), ESF raqami/sanasi, marka kodlari | Дт 2910/2920 — Кт 6010; Дт 4410 — Кт 6010 |
| Yetkazib beruvchiga qaytarish | Возврат товаров поставщику | `ВозвратТоваровПоставщику` | Контрагент, Договор, Склад, Товары | teskari |
| Filiallar/omborlar orasida ko'chirish | Перемещение товаров | `ПеремещениеТоваров` | СкладОтправитель, СкладПолучатель, Товары | 2910 ↔ 2920 (ombor → do'kon) |
| Hisobdan chiqarish (buzilish, muddati o'tgan) | Списание товаров | `СписаниеТоваров` | Склад, Товары, Счет затрат | Дт 5910/94xx — Кт 29xx |
| Inventarizatsiya | Инвентаризация товаров на складах → Оприходование / Списание | `ИнвентаризацияТоваровНаСкладе`, `ОприходованиеТоваров`, `СписаниеТоваров` | Склад, Товары (учет/факт) | ortiqcha — daromad; kamomad — 5910/4730 |
| Qarzni hisobdan chiqarish / o'zaro hisob | Корректировка задолженности | `КорректировкаДолга` | ВидОперации, Контрагент, Договор, Суммы | — |
| Inkassatsiya | Выдача наличных «Инкассация» / «Взнос наличными в банк» → Поступление на р/с «Инкассация» | — | Касса, Сумма | Дт 5710 — Кт 5010; Дт 5110 — Кт 5710 `[M9]` |

### 2.3 Ma'lumotnomalar (справочники) va majburiy maydonlar

| Ma'lumotnoma | Nima kerak | Izoh |
|---|---|---|
| **Организации** | STIR (ИНН) | Sonar `Справочник.Организации.ИНН` bo'yicha qidiradi `[M8]`. ERP tenant ↔ 1C organizatsiyasi — STIR bo'yicha 1:1 bog'lash. |
| **ПодразделенияОрганизаций** | filial | ERP `branch` ↔ bo'linma (ixtiyoriy, hisob siyosatiga bog'liq: `[M1]` 4.2.1.3 «Учет подразделений»). |
| **Склады** | **turi**: ombor (ulgurji) / chakana magazin / НТТ | Turi ОРП rejimini belgilaydi (*taxmin*, БП 3.0 RU). ERP do'koni → «розничный магазин» turidagi ombor. |
| **Кассы** | naqd kassa | `[M1]` 5.1.3; Sonar `Справочник.Кассы` ni taniydi `[M8]`. |
| **КассыККМ** | ОРП'dagi «Касса ККМ» elementi | *taxmin*: ОРП (avtomatlashtirilgan nuqta) da majburiy, lekin bu **faqat ma'lumotnoma elementi** — haqiqiy uskunaga ulanmaydi. ERP har POS-kassa uchun bitta element yaratadi/bog'laydi. |
| **Контрагенты** | **ИНН** (STIR, yuridik shaxs — 9 raqam), jismoniy shaxs uchun **ПИНФЛ** (14 raqam) | Sonar `Контрагенты` da `ИНН`, `ПолноеНаименование`, **`ИдентификационныйКодЛичности`** rekvizitlarini qidiradi `[M8]` — ПИНФЛ maydon nomi ehtimol shu (*taxmin*, metadata'dan tekshirish). Chakana anonim xaridor uchun bitta «Розничный покупатель» kontragenti (*taxmin*). |
| **ДоговорыКонтрагентов** | «с покупателем»/«с поставщиком» | Реализация/Поступление uchun majburiy (*taxmin*, БП 3.0). ERP har kontragent uchun «Asosiy shartnoma» yaratadi yoki mavjudini topadi. |
| **Номенклатура** | Наименование, **ед. изм.**, **Ставка НДС** (12% / 0% / «Без НДС»), **ИКПУ (MXIK, 17 belgi)**, вид номенклатуры (tovar/xizmat), shtrix-kod, markirovka belgisi | ИКПУ — 17 xonali davlat kodi, tasnif.soliq.uz katalogi `[M19][M20]`. 1C'dagi aniq rekvizit nomi topilmadi (*taxmin*: «КодИКПУ»/«ИКПУ» yoki qo'shimcha rekvizit) — metadata'dan aniqlanadi. ERP mos kelishni **ИКПУ + shtrix-kod + nom** bo'yicha qiladi; topilmasa — avtomatik yaratish emas, «xaritalash kerak» navbati (Sonar qoidasi ham shunday: havola faqat topiladi, 0 yoki 2+ bo'lsa xato `[M8]`). |
| **Счета учета номенклатуры** (registr) | tovar hisobi (2910/2920), daromad/tannarx hisoblari | `[M1]` 8.1.3 — 1C o'zi qo'yadi; ERP hisob raqamini yubormaydi. |
| **Виды оплат** (karta/Click/Payme/Uzum) | har biri uchun hisob (5710 yoki 5110) va kontragent-bank | *taxmin*: БП 3.0'da «Виды оплат организаций». ERP to'lov usuli ↔ 1C «вид оплаты» xaritasi sozlamada. |
| **Единицы измерения** | kod | Sonar `Справочник.ЕдиницыИзмерения` ni ishlatadi `[M8]`. |

---

## 3. Chakana savdo 1C'da qanday aks etadi (O'zbekiston)

### 3.1 Daromad — kunlik ОРП

- БП Узбекистан 3.0 ikki rejimni qo'llab-quvvatlaydi: **operativ (kunlik) aks ettirish** va **inventarizatsiya natijalari bo'yicha sotuv** `[M3]`; qo'llanmada «Продажи в розничном магазине» va НТТ (xarid narxi / sotish narxi) `[M1]`.
- Rossiya БП 3.0 analogi: avtomatlashtirilgan nuqta (АТТ) — ОРП smena yopilganda tovar qatorlari bilan; НТТ — avval kassa kirimi «Розничная выручка», keyin inventarizatsiya asosida ОРП `[M18]`.
- **Tavsiya (bizning holat):** ERP — haqiqiy POS (har chek ERP'da). Shuning uchun **avtomatlashtirilgan nuqta (АТТ) rejimi**: kun/smena × ombor × kassa uchun bitta ОРП, tovarlar jamlangan (nomenklatura × narx × QQS stavkasi bo'yicha guruhlangan), to'lovlar turi bo'yicha. Chek darajasidagi tafsilot 1C'ga kerak emas — u ERP'da va soliq OFD'sida.
- УТ 11 для Узбекистана'da ham xuddi shu mantiq: «при закрытии смены система консолидирует все данные по продажам из чеков ККМ в один документ — Отчет о розничных продажах» `[M17]`.

### 3.2 Tovarni xarid yoki sotish narxida hisoblash

NSBU 21 rasmiy matni: 2920 «Chakana savdodagi tovarlar» — magazin, kiosklardagi tovarlar; chakana savdoda tovar sotish narxida hisoblansa, ustama **2980 «Savdo ustamasi»** da yig'iladi, sotilgan tovarga tegishli qismi `Дт 2980 — Кт 9120` bilan yopiladi `[M9]`. БП Узбекистанда bu «Способ оценки товаров в рознице» sozlamasi (4.3.3), «Переоценка товаров в рознице» (8.1.5) va oy yopishdagi «Расчет торговой наценки» (12.2.8) orqali `[M1]`.

**Integratsiya uchun ta'siri:** ERP 1C'ning bu sozlamasini **o'qib** bilishi kerak. Sotish narxida hisoblanadigan bazada ERP narx o'zgarishini «Переоценка товаров в рознице» bilan yubormasa, 2920 qoldig'i buziladi (*taxmin*). MVP tavsiyasi: faqat **xarid narxida hisob** rejimidagi bazalarni qo'llab-quvvatlash, sotish narxidagi bazalarni ulanishda aniqlab, ogohlantirish.

### 3.3 Karta, QR, Click, Payme, Uzum

- NSBU 21: **5710 «Yo'ldagi pul mablag'lari (o'tkazmalar)»** — «saqlash joyidan chiqib ketgan, ammo mo'ljallangan joyiga yetib bormagan pul mablag'lari (inkassatorga berilgan tushumlar, pul o'tkazmalari)», tranzit hisob; misol: `Дт 5710 — Кт 4010` (kelgan pul o'tkazmalari bo'yicha xaridor qarzi qoplanishi) `[M9]`.
- Amaliy maqola (bss.uz, 2024): chakana tushum `Дт 5010, 5711, 4010 — Кт 9020`, QQS `… Кт 6410`, bank tushumi `Дт 5110 — Кт 4010, 5710, 5711` `[M10]` — ya'ni karta tushumi uchun 5710/5711 (subhisob) ishlatiladi.
- 5530 «Boshqa maxsus hisobvaraqlar» — rasmiy ta'rifi maqsadli mablag'lar uchun `[M9]`; karta tushumiga mos emas (Sonar demo'sidagi 5530 — boshqa maqsadda).
- БП Узбекистанда: «Операции по платежным картам» (5.3.5) va «Поступление на р/с — по платежным картам и банковским кредитам» (5.2.5) `[M1]`; УТ Узбекистанda ekvayring bank hisobotlari va komissiya `[M5]`; УК Узбекистанda «операции эквайринга» `[M11]`.
- **Tavsiya:** ОРП'da karta/QR to'lovlari «вид оплаты» bo'yicha → 5710 (buxgalter sozlaydi). Bank ko'chirmasini 1C'ga kim kiritadi — ERP yoki buxgalter — **ochiq savol**; MVP'da ERP faqat ОРП yuboradi, bankni buxgalter kiritadi (1C'ning bank-klient almashuvi orqali, 5.2.7). ERP'ning `13-provodka-qoidalari.md` dagi to'g'ridan-to'g'ri 5110 (2.2-bo'lim) bilan nomuvofiqlik — buxgalter tasdig'i uchun qayd qilindi (u hujjat ham 6-bandda klirinig hisob kerakligini aytadi).
- Click/Payme/Uzum odatda **pul o'tkazish (to'lov tashkiloti)** — hisobga tushish kechikadi va komissiya ushlanadi; har biri uchun alohida «вид оплаты»/kontragent (*taxmin*).

### 3.4 Nasiya (qarzga sotish)

- ОРП — anonim chakana sotuv; unda kontragent yo'q (*taxmin*, БП 3.0 RU). Aniq xaridor qarzini kuzatish uchun **«Реализация товаров и услуг»** (kontragent — jismoniy shaxs, ПИНФЛ bilan; shartnoma «с покупателем»), `Дт 4010 — Кт 9020/6410` `[M9]` va keyin to'lovlar. bss.uz ham `Дт 4010 Кт 9020` ni chakana sotuv varianti sifatida ko'rsatadi `[M10]`.
- Aralash to'lov (qisman naqd + qisman nasiya) — bitta chekni ikkiga bo'lmaslik uchun: butun chekni Реализация qilib, naqd qismini «Поступление наличных — Оплата от покупателя» bilan yopish (*taxmin*, buxgalter bilan kelishish).
- Jismoniy shaxs-kontragentlar soni ko'payadi — ERP mijozlar bazasidan faqat **nasiyasi bor** mijozlarni 1C'ga yaratadi (*taxmin*).

### 3.5 Fiskallashtirish — 1C qayta fiskallashtirmasligi kerak

- Fiskal chek ERP (virtual/onlayn kassa, OFD) tomonida bir marta chiqadi. 1C'ga faqat **buxgalteriya hujjati** boradi.
- БП'da «Чек ККМ» hujjati yo'q (qo'llanma mundarijasida yo'q `[M1]`) — ОРП qo'lda/COM bilan uskunasiz yaratiladi; «Касса ККМ» faqat ma'lumotnoma elementi (*taxmin*).
- УТ/Розница/УК'da РМК va «Чек ККМ» fiskal registrator bilan ishlaydi `[M6][M17]` — u yerda ERP **«Чек ККМ» yaratmasligi**, faqat ОРП (yoki УТ'ning «Отчет о розничных продажах») yaratishi kerak; kassa smenasi/fiskal uskuna bilan bog'liq rekvizitlar bo'sh qoldiriladi (*taxmin*, pilotda tekshirish).
- Tekshiruv ro'yxati (*taxmin*): «Касса ККМ» elementida uskuna (подключаемое оборудование) belgilanmagan; ОРП'ni COM orqali `Записать(Проведение)` qilganda fiskal qurilmaga murojaat bo'lmasligi; 1C'da «Использовать подключаемое оборудование» o'chiq yoki shu kassa uchun bog'lanmagan.

### 3.6 Markirovka (Asl belgisi)

БП Узбекистан 3.0'da markirovka kodlari hujjat qatorlarida, o'tkazishda kodlar soni va dublikatlar tekshiriladi (7.3.4) `[M1]`. Agar tovar markirovkali bo'lsa va tekshiruv yoqilgan bo'lsa, ОРП/Реализация'ni kodsiz o'tkazish **rad etilishi** mumkin (*taxmin*). MVP: markirovka kodlarini yubormaslik, ammo 1C'dagi tekshiruv sozlamasini o'qib, yoqilgan bo'lsa ogohlantirish; keyingi bosqichda kodlarni ham yuborish.

---

## 4. QQS (12%) va aylanma solig'i

- QQS stavkasi **nomenklatura** darajasida (standart) va hujjat qatorida (`СтавкаНДС`, `СуммаНДС`) — *taxmin*, БП 3.0 analog; BP Узбекистанда «раздельный учет входящего НДС», 0% stavka qo'llab-quvvatlanadi `[M3]`; QQS sozlamalari 4.2.13 `[M1]`.
- Provodka: `Кт 6410` (QQS byudjetga qarz) — NSBU 21 da 6410 «Byudjetga to'lovlar bo'yicha qarzlar (turlari bo'yicha)» `[M9]`; amaliy maqolada `Дт 5010… Кт 6410 — начислен НДС` `[M10]`. Kiritiladigan QQS — 4410 `[M9]`.
- **Aylanma solig'i to'lovchilar:** nomenklatura/hujjat «Без НДС»; aylanma solig'i 1C'da hujjat bo'yicha emas, oy oxiridagi hisob-kitob/hisobot orqali (*taxmin*; 4.2.8 «Настройки налогового учета» `[M1]`).
- **ERP qoidasi:** ERP qatordagi QQS summasini **yuboradi** (fiskal chekdagi bilan bir xil bo'lishi uchun), 1C qayta hisoblasa farq chiqishi mumkin (yaxlitlash). Yozgandan keyin 1C hujjatidagi `СуммаНДС` jami ERP'dagi bilan solishtiriladi; farq > 1 so'm bo'lsa — ogohlantirish (*taxmin*: chegarani buxgalter belgilaydi).
- **Muvofiqlik tekshiruvi:** ERP tenant soliq rejimi (QQS / aylanma) ↔ 1C organizatsiyasining hisob siyosati — ulanishda solishtirish, farq bo'lsa yuborishni bloklash.

---

## 5. Tannarx (COGS) — kim haqiqat manbai

- БП Узбекистан: zaxira baholash **o'rtacha va FIFO** `[M3]`; hisob siyosatida «Способ оценки МПЗ», «Учет себестоимости продаж» `[M1]` 4.3.2/4.3.8. ОРП/Реализация o'tkazilganda 1C tannarxni o'zi hisoblab `Дт 9120 — Кт 29xx` yozadi; oy yopishda «Корректировка стоимости номенклатуры» (12.2.6) qayta hisoblaydi `[M1]` (*taxmin*: o'rtacha usulda aniq tannarx oy oxirida shakllanadi — БП 3.0 RU'dagi kabi).
- ERP ham tannarxni FIFO/AVECO bo'yicha hisoblaydi (`spec/kod-uchun/13-provodka-qoidalari.md`, 4-xulosa). **Ikki tizim har doim bir xil chiqmaydi**: kirim sanalari, qayta baholash, 1C'da qo'lda tuzatishlar, o'rtacha usulning davr bo'yicha hisoblanishi, sotish narxidagi hisob (2980).
- **Tavsiya:**
  1. **1C ichidagi buxgalteriya va soliq hisobotlari uchun haqiqat manbai — 1C** (uning tannarxi, oy yopishi). ERP tannarxni 1C'ga **yubormaydi** (ОРП'da tannarx maydoni yo'q; 1C o'zi qo'yadi).
  2. 1C to'g'ri tannarx hisoblashi uchun ERP **barcha kirimlarni** (Поступление, xarid narxi va QQS bilan), ko'chirishlar, hisobdan chiqarishlar, inventarizatsiya natijalarini ham yuborishi shart — aks holda 1C'da **manfiy qoldiq** va noto'g'ri tannarx bo'ladi. Shu sababli yuborish tartibi: ma'lumotnomalar → kirimlar → ko'chirish → sotuv (ОРП) → qaytarish → hisobdan chiqarish/inventarizatsiya → pul hujjatlari.
  3. ERP tannarxi — boshqaruv hisobi (marja, dashboard). Har oy «ERP vs 1C tannarx/qoldiq» solishtiruvi (1C'dan COM orqali ОСВ 2910/2920/9120 o'qiladi) — farq hisoboti buxgalterga.
  4. 1C'da «manfiy qoldiqqa ruxsat» sozlamasi o'chiq bo'lsa, kirim yetib kelmagan ОРП o'tkazilmaydi (*taxmin*) — yuborish navbati bu xatoni «kirim yetishmaydi» deb ko'rsatishi kerak.

---

## 6. Davr yopish va «Дата запрета изменения данных»

- БП Узбекистан 3.0'da xizmat bor: 15.2.4 «Дата запрета изменения данных» `[M1]`. Bu 1C'ning standart kutubxonasi mexanizmi (*taxmin*, БП 3.0 RU analog): belgilangan sanagacha (shu sana ham) hujjatlarni yozish/o'tkazish/o'chirish **foydalanuvchi va organizatsiya bo'yicha** taqiqlanadi; tekshiruv obyekt yozilayotganda server tomonda ishlaydi — ya'ni **COM orqali yozish ham bloklanadi**, agar integratsiya foydalanuvchisi istisno qilinmagan bo'lsa.
- Oy yopish (12.2) — «Корректировка стоимости номенклатуры», «Расчет торговой наценки», «Определение финансовых результатов» `[M1]`; oy yopilgandan keyin o'tgan sanaga hujjat qo'shilsa, yopishni qayta bajarish kerak (*taxmin*). Sonar ham oy yopishni AI'ga bermaydi, alohida jamoaviy oqim qiladi `[M8]`.
- **Kechikkan yuborish oqibatlari va tavsiya:**
  1. Agent yozishdan oldin 1C'dan joriy **taqiq sanasini o'qiydi** (*taxmin*: «ДатыЗапретаИзменения» registri) va paket sanasi ≤ taqiq sanasi bo'lsa — yozmaydi, holat «davr yopilgan — buxgalter qarori kerak».
  2. Buxgalter variantlari: (a) 1C'da sanani vaqtincha ochish va qayta yuborish; (b) ERP paketni **joriy ochiq sanaga tuzatuvchi hujjat** sifatida yuborishi (izohda asl sana); (c) o'tkazib yuborish (faqat ERP'da qoladi). Avtomatik sana almashtirish — **yo'q**.
  3. Integratsiya foydalanuvchisini taqiqdan istisno qilish **tavsiya etilmaydi** (buxgalterning yopilgan davrini buzadi).
  4. Oy yopilgandan keyin yuborilgan hujjat (taqiq sanasi qo'yilmagan bo'lsa ham) — 1C oy yopishini qayta bajarish kerakligi haqida ogohlantirish.
- ERP tomonda ham `period_closings` bor (`13-provodka-qoidalari.md`, 6-xulosa) — ERP davrini yopish va 1C taqiq sanasini **moslashtirish** (masalan, 1C'ga yuborish tugamaguncha ERP davrini yopmaslik) — ochiq savol.

---

## 7. УТ / Розница / Управление компанией bazalari uchun farqlar (qisqa)

| | УТ 11 для Узбекистана | Розница 3.0 / Управление компанией 3.0 для Узбекистана |
|---|---|---|
| Chakana sotuv hujjati | «Чек ККМ» → smena yopilganda «Отчет о розничных продажах» `[M17]` | РМК, fiskal registrator `[M6]`; chakana sotuv hisoboti `[M11]` |
| ERP nimani yozadi | ОРП (Чек ККМ emas) | ОРП analogi (*taxmin*: «Отчет о розничных продажах»; УНФ-oilasida hujjat nomi boshqacha bo'lishi mumkin) |
| Ekvayring | bank hisobotlari, komissiya `[M5]` | «операции эквайринга» `[M11]` |
| Tannarx | «в разрезе организаций» `[M5]` | — |
| Buxgalteriya | БП Узбекистанga **birlamchi hujjatlar darajasida** yuklash `[M5]` | Розница — «в связке с 1С:Бухгалтерия 8» `[M6]` |

**Xulosa:** agar mijozda УТ/Розница + БП bo'lsa, ERP **faqat bitta** bazaga yozishi kerak (odatda БП), aks holda 1C'ning o'z almashuvi orqali hujjatlar ikki marta tushadi. Ulanishda «bu bazaga boshqa 1C dan almashuv kelyaptimi» savoli (sinxronizatsiya sozlamalari 15.7 `[M1]`) tekshirilishi kerak. MVP: faqat **БП Узбекистан 3.0**.

---

## 8. Integratsiya uchun amaliy tavsiyalar (shu tadqiqotdan)

1. **Metadata-xarita, qattiq kod emas.** Ulanishda agent bazaning metadata'sini o'qiydi (Sonar ham shunday qiladi, konfiguratsiya versiyasi o'zgarsa yangilaydi `[M8]`) va «ERP voqeasi → 1C hujjat + operatsiya turi + rekvizitlar» xaritasini quradi: avval nom bo'yicha (`ОтчетОРозничныхПродажах`…), keyin sinonim bo'yicha («Отчет о розничных продажах»). Topilmasa — bu baza qo'llab-quvvatlanmaydi.
2. **Qo'llab-quvvatlanadigan konfiguratsiya ro'yxati:** `Бухгалтерия для Узбекистана` 3.0.x (MVP), keyin `Управление торговлей для Узбекистана` 11.x, `Розница`/`Управление компанией для Узбекистана` 3.0.x. Konfiguratsiya nomi va versiyasi (`Метаданные.Имя`, `Метаданные.Версия`) ulanishda saqlanadi.
3. **Ulanish tekshiruvi (onboarding):** organizatsiya STIR mosligi; soliq rejimi (QQS/aylanma) mosligi; tovar baholash usuli (xarid/sotish narxi); manfiy qoldiqqa ruxsat; taqiq sanasi; markirovka tekshiruvi; «Касса ККМ» uskunaga bog'lanmagani; boshqa 1C dan almashuv bormi.
4. **Xaritalar (buxgalter tasdiqlaydi):** ERP do'koni ↔ Склад (+ Подразделение); ERP kassa ↔ Касса va Касса ККМ; to'lov usuli ↔ Вид оплаты; mahsulot ↔ Номенклатура (ИКПУ/shtrix-kod/nom); mijoz ↔ Контрагент (STIR/ПИНФЛ). 1C'da yangi element yaratish — **jimgina avtomatik emas**: faqat preview'da ro'yxat bilan ko'rsatilib, `onec.mapping.edit` ruxsatli inson tasdiqlagandan keyin (yakuniy qoida — `00-xulosa` §5; Tashkilot va QQS stavkasi hech qachon yaratilmaydi).
5. **Kunlik paket = ОРП lar + nasiya Реализация lari + qaytarishlar + kirimlar/ko'chirishlar/hisobdan chiqarishlar**, tartib — 5-bo'lim 2-band. Har hujjatda idempotentlik markeri (`Комментарий`/qo'shimcha rekvizit, Sonar naqshi `[M8]`) — qayta yuborishda ikki marta yaratilmaydi.
6. **Hujjat o'tkazilgandan keyin** jamilarni qayta o'qish (summa, QQS, miqdor) va ERP bilan solishtirish.

---

## 9. Ochiq savollar

1. Bulutdagi (1С:Фреш, uzcloud, clobus) БП bazalari — COM-faqat qarori bilan qo'llab-quvvatlanmaydi; bu mijozlar segmentini qoldiramizmi?
2. Bank/ekvayring tushumlari (5110 ↔ 5710) ni ERP yuboradimi yoki buxgalter 1C'da o'zi kiritadimi?
3. Nasiya mijozlarini 1C'da alohida kontragent qilish (ПИНФЛ bilan) yoki bitta «Розничный покупатель (nasiya)» kontragentida analitikasiz yig'ish?
4. Sotish narxida hisoblanadigan (2920/2980) bazalarni MVP'da qo'llab-quvvatlaymizmi?
5. ERP davri yopilishi va 1C taqiq sanasi qanday moslashtiriladi?
6. Pilot uchun haqiqiy БП Узбекистан 3.0.64.x bazasining metadata eksportini olish (ОРП rekvizitlari, ПИНФЛ/ИКПУ maydon nomlari, «Виды оплат» tuzilishi) — barcha *taxmin* larni yopadi.

---

## Manbalar

- `[M1]` 1C:ИТС — «1С:Бухгалтерия для Узбекистана. Редакция 3.0. Руководство по ведению учета», mundarija (bo'lim va kichik bo'lim nomlari, operatsiya turlari): https://its.1c.eu/uz/db/buhuz30 (masalan https://its.1c.eu/uz/db/buhuz30/content/104/hdoc — 6.3 Продажи; matnlar obuna ortida)
- `[M2]` 1c.uz — Типовые продукты: https://1c.uz/v8/generic_products/index.php
- `[M3]` 1c.uz — 1С:Бухгалтерия 8 для Узбекистана: https://1c.uz/v8/generic_products/uz_accounting.php
- `[M4]` 1c.uz — 1С:Бухгалтерия 8 КОРП МСФО для Узбекистана: https://1c.uz/v8/generic_products/uz_accountingcorpifrs.php
- `[M5]` 1c.uz — 1С:Управление торговлей для Узбекистана: https://1c.uz/v8/generic_products/uz_trade_management.php
- `[M6]` 1c.uz — 1С:Розница 8 для Узбекистана: https://1c.uz/v8/generic_products/uz_retail.php
- `[M7]` 1C:ИТС (its.1c.eu) — «опубликована новая версия» lentasi (БП Узбекистан 3.0.64.8/3.0.64.5/3.0.64.1, УТ Узбекистан 11.0.0.24, Розница Узбекистан 3.0.17.1, Управление компанией Узбекистан 3.0.17.1, ЗУП 3.1.24.1/3.1.37.1): https://its.1c.eu/ ; reliz havolalari (login talab qiladi): https://releases.1c.ru/version_files?nick=AccountingUz30&ver=3.0.64.8 , https://releases.1c.ru/version_files?nick=TradeUz&ver=11.0.0.24 , https://releases.1c.ru/version_files?nick=RetailUz3&ver=3.0.17.1
- `[M8]` Sonar AI dekompilyatsiyasi va tahlili: `research_notes/sonar-1c-integratsiya/00-xulosa.md`, `04-1c-ga-yozish-va-tasdiqlash.md`, `05-mahsulot-funksiyalari-va-server-api.md`; kod: `E:/Project/sonar/decompiled/src_app/Sonar.Core/Sonar.Core/DemoSession.cs` (demo hisob rejasi, `ПриходныйКассовыйОрдер`), `.../Sonar.Desktop.Core.Mock/MockChanges.cs:13-15` (`ПоступлениеНаличных`/`ВыдачаНаличных`), `.../Sonar.Desktop.Core.Connector/OneCRead.cs:75-89,881` (ma'lumotnoma nomlari, `ИдентификационныйКодЛичности`)
- `[M9]` lex.uz — НСБУ №21 «Хўжалик юритувчи субъектларнинг бухгалтерия ҳисоби счётлари режаси ва уни қўллаш бўйича Йўриқнома» (Ilova №1, o'zbek tilida; 191-son buyruq): https://lex.uz/docs/7282737 ; buyruq: https://lex.uz/ru/docs/7282759 (o'qilgan bandlar: hisoblar ro'yxati 2910/2920/2980, 4010, 4410, 5010, 5110, 5530, 5710, 6410, 9010–9050, 9110–9120; 145, 146, 152, 233, 237–239-bandlar)
- `[M10]` bss.uz (Главбух Узбекистан), «Розничная торговля: особенности учета в рознице», 2024-10-09: https://www.bss.uz/article/2327-roznichnaya-torgovlya-osobennosti-ucheta-v-roznitse
- `[M11]` 1c.uz — 1С:Управление компанией 8 для Узбекистана: https://1c.uz/v8/generic_products/uz_small_company.php
- `[M12]` 1c.uz — bosh sahifa (ЗУП muvofiqlik sertifikatlari, mahsulotlar): https://1c.uz/
- `[M13]` 1c.uz bosh sahifa havolalari (1C:ERP umumiy): https://1c.uz/
- `[M14]` 1C:ИТС — «1С:Бухгалтерия 8 для Узбекистана. Руководство пользователя. Ред. 1.5», «Учет товаров в розничной торговле»: https://its.1c.eu/uz/db/buhuz15/content/116/hdoc
- `[M15]` uzcloud.uz — «1С в облаке в Узбекистане»: https://uzcloud.uz/business/1c
- `[M16]` clobus.uz — «Программы 1С в облаке (1С:Фреш)»: https://clobus.uz
- `[M17]` koderline.uz — «Управление продажами в 1С Управление торговлей 11 для Узбекистана» (2023-09-19): https://koderline.uz/expert/narabotki/article-upravlenie-prodazhami-v-1s-upravlenie-torgovley-11-dlya-uzbekistana/
- `[M18]` buhexpert8.ru — «Отчет о розничных продажах в 1С 8.3: заполнение и проводки» (Rossiya БП 3.0 analogi; АТТ/НТТ, «Безналичные оплаты», ПКО «Розничная выручка»): https://buhexpert8.ru/obuchenie-1s/1s-buhgalteriya-8-3/otchet-o-roznichnyh-prodazhah-v-1s-8-3-zapolnenie-i-provodki.html
- `[M19]` buxgalter.uz — «Какой ИКПУ применить в документах» (17 belgili tuzilma): https://buxgalter.uz/publish/doc/text172265_kakoy_ikpu_primenit_v_dokumentah
- `[M20]` spot.uz — «Как будут добавлять коды в единый электронный каталог ИКПУ» (2025-04-30): https://spot.uz/ru/2025/04/30/code-catalog/
- Ichki: `spec/kod-uchun/13-provodka-qoidalari.md` (ERP provodkalari, 5110 karta va klirinig hisob ogohlantirishi, FIFO/AVECO, `period_closings`).
