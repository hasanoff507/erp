# R6 — 1C'ga yozish texnikasi (COM orqali, kun yakunida)

> **Yakuniy tavsiya ustun (accept gate, 2026-10-15):** shu papkadagi fayllar orasidagi ziddiyatlar `00-xulosa.md` da hal qilingan (§«Hal qilingan ziddiyatlar»). Bu fayl bilan `00-xulosa.md` farq qilsa — **00-xulosa'dagi yakuniy tavsiya ustun**. Kanonik nomlar: jadvallar — `04` §3.3; idempotentlik algoritmi — `04` §5.3; maydon xaritalari va ketma-ketlik — `03` §3, §5.1.

> **Vazifa**: kun oxirida ERP do'kon savdolarini (va kerak bo'lsa boshqa hujjatlarni) do'konning 1C:Enterprise 8.3 bazasiga yozadi. Nishon konfiguratsiya: «Бухгалтерия для Узбекистана 3.0», shuningdek БП 3.0 / УТ 11 / Розница / УНФ.
> **Asoschi qarori (2026-10-15)**: faqat **COM (V83.COMConnector, tashqi ulanish)** — do'kon kompyuteridagi Windows agent orqali. 1C'dan hech narsa nashr qilinmaydi (veb-server, OData, HTTP-servislar yo'q).
> Manba asosi: `research_notes/sonar-1c-integratsiya/02` va `04` (Sonar'ning COM o'qish/yozish yo'li: `ObjectSpec`, `Записать`siz preview, `ВерсияДанных`, `"Sonar #id"` markeri, `РежимЗаписиДокумента.Проведение`).
> Belgilar: **[tasdiqlangan]** — rasmiy hujjat yoki Sonar kodida ko'rilgan; ***taxmin*** — tajriba/umumiy bilimga asoslangan, real bazada tekshirilishi shart.

---

## 0. Qisqa xulosa (TL;DR)

1. **Yo'l**: Windows agent (alohida worker jarayon, bitta STA oqim; *accept gate:* agent tili standart **C# / .NET Framework 4.8** — `04` §2.1; bu fayldagi Python/pywin32 kodi COM chaqiruvlar ketma-ketligini ko'rsatuvchi **namuna**, C# `dynamic` bilan aynan shu chaqiruvlar) → `V83.COMConnector.Connect(...)` → `Документы.ОтчетОРозничныхПродажах.СоздатьДокумент()` → rekvizitlar + `Товары`/`Оплата` jadvallari → `Записать(РежимЗаписиДокумента.Проведение, РежимПроведенияДокумента.Неоперативный)` → o'qib solishtirish (reconciliation).
2. **Idempotentlik — asosiy usul**: hujjat GUID'ini **o'zimiz beramiz** — `Документы.X.ПолучитьСсылку(Новый УникальныйИдентификатор("<bizning uuid5>"))` + `Объект.УстановитьСсылкуНового(Ссылка)`. Qayta yuborishda avval shu GUID bo'yicha borligi tekshiriladi. Ikkinchi qatlam — `Комментарий`ga `"ERP #<id>"` markeri (Sonar uslubi), uchinchi — agentdagi mahalliy jurnal. Konfiguratsiya o'zgartirilmaydi.
3. **`ОбменДанными.Загрузка = Истина` ishlatmaymiz** (savdo hujjatlari uchun): u konfiguratsiyaning tekshiruv/to'ldirish mantig'ini o'chiradi, hujjat "yarim tayyor" bo'lib qoladi. Faqat ma'lumotnomalarni (masalan, yangi nomenklatura) majburan yozish kerak bo'lgan kamdan-kam holatda.
4. **Konfiguratsiyaning hisoblash mantig'i** (hisob schyotlari, НДС, narx turlari) COM orqali yaratilgan hujjatda **avtomatik ishlamaydi** — forma hodisalari chaqirilmaydi. Yo `Заполнить()` + menejer modulining eksport protseduralari (konfiguratsiyaga bog'liq, ***taxmin***), yo hamma narsani o'zimiz to'ldirib, keyin 1C hisoblaganini o'qib solishtiramiz. Eng ishonchli va tez yo'l — **tashqi qayta ishlash (.epf)** ni `ВнешниеОбработки.Создать()` orqali yuklab, butun mantiqni 1C ichida bajarish (8-bo'lim). *Accept gate:* `.epf` — MVP'da **yo'q** (mijoz bazasida bizning 1C kodini bajaradi, huquq/«Защита от опасных действий» xavfi); avval T-4 sinovi (1C o'zi schyotlarni to'ldiradimi), keyin «oltin namuna»/`СчетаУчетаНоменклатуры`; `.epf` — C bosqichi optimallashtirishi, asoschi roziligi bilan.
5. **Bitta hujjat = bitta tranzaksiya** (posting o'zi tranzaksiya). Bir nechta hujjatni bitta COM tranzaksiyasiga o'rash — faqat haqiqatan atomiklik kerak bo'lsa; uzun tranzaksiya foydalanuvchilarni bloklaydi.
6. **Yopiq davr**: «Дата запрета изменения» dan oldingi sanaga yozish xato beradi — biz faqat ochiq davrga yozamiz; o'tgan davrga yozish (masalan internet uzilgandan keyin) → БП'da oyni qayta yopish kerak bo'ladi.
7. **Litsenziya**: COM tashqi ulanish seans davomida **mijoz litsenziyasini egallaydi** ***(texnik jihati taxmin; huquqiy qoida tasdiqlangan — "vositachi" litsenziya sonini kamaytirmaydi)***; `Базовая` versiya COM'ni qo'llamaydi — 7-bo'lim.
8. **OData yozish**: rad etilgan (asoschi qarori). EnterpriseData — faqat qisqa eslatma (4-bo'lim).

---

## 1. COM orqali hujjat yaratish va o'tkazish — mexanika

### 1.1. Ulanish

```python
import pythoncom, win32com.client

pythoncom.CoInitialize()                       # har bir oqimda (STA) bir marta
connector = win32com.client.Dispatch("V83.COMConnector")   # yoki "V85.COMConnector" (8.5)
# fayl baza:
conn = connector.Connect('File="D:\\1C\\Shop1";Usr="erp_agent";Pwd="***";')
# server baza:
# conn = connector.Connect('Srvr="srv1c";Ref="shop1";Usr="erp_agent";Pwd="***";')
```

- **ProgID** — `V83.COMConnector` (8.3), `V82.COMConnector` (eski). 1C platformasi o'rnatilganda `comcntr.dll` **ro'yxatdan o'tgan bo'lishi** shart (`regsvr32 "C:\Program Files\1cv8\8.3.xx\bin\comcntr.dll"` — administrator huquqi bilan). Python bitligi (32/64) **platforma bitligiga mos** bo'lishi kerak — 64-bit Python faqat 64-bit `comcntr.dll`ni ko'radi. Sonar ham shuni hal qiladi: ikkala bitlikdagi worker'ni olib yuradi va reestrdan qaysi biri borligini o'qiydi (`Platform.ChooseBits`, 02-hujjat §1.5). **[tasdiqlangan — Sonar kodi]**
- Ulanish satridagi qiymatlar qo'shtirnoqda, ichki `"` ikkilanadi (Sonar `OneCConnect.Q()`). **[tasdiqlangan — Sonar]**
- Platforma versiyasi bazaning versiyasiga mos bo'lishi kerak; aks holda `"версия ... отличается"` xatosi (Sonar `ErrorMap` → `version_mismatch`). Bazada **konfiguratsiya yangilanishi kutilayotgan** bo'lsa (`"обновлени" + "конфигурац"`), COM ulanish rad etilishi mumkin — agent buni alohida xato kodi bilan ko'rsatishi kerak.
- **Agent uchun alohida 1C foydalanuvchisi** (`erp_agent`): huquqlar — kerakli hujjatlarni yozish/o'tkazish, **"Внешнее соединение"** huquqi (rol `ВнешнееСоединение` / standart rollarda "Запуск внешнего соединения") ***taxmin — aniq rol nomi konfiguratsiyaga bog'liq***. Shu foydalanuvchi hujjatlarning `Ответственный`/`Автор` maydonida ko'rinadi — buxgalter "buni ERP yozgan" deb darhol biladi.

### 1.2. Havolalarni topish (ma'lumotnoma elementlari)

| Usul | Kod (1C tili) | Izoh |
|---|---|---|
| Kod bo'yicha | `Справочники.Номенклатура.НайтиПоКоду("000123")` | Topilmasa → `ПустаяСсылка()` (istisno emas!). Ierarxik kod bo'lsa — to'liq kod. |
| Nom bo'yicha | `Справочники.Номенклатура.НайтиПоНаименованию("Coca-Cola 1L", Истина)` | 2-parametr `Истина` = aniq moslik. Bir xil nomli bir nechta element bo'lsa — **birinchisini** qaytaradi (xavfli!). |
| Rekvizit bo'yicha | `Справочники.Номенклатура.НайтиПоРеквизиту("Артикул", "4780001234567")` | Faqat indekslangan/oddiy turdagi rekvizit; ko'p topilsa — birinchisi. |
| GUID bo'yicha | `Справочники.Номенклатура.ПолучитьСсылку(Новый УникальныйИдентификатор(guid))` | Element mavjud bo'lmasa ham "havola" qaytadi — mavjudligini alohida tekshirish kerak (2.3). |
| So'rov | `ВЫБРАТЬ ПЕРВЫЕ 2 Ссылка ИЗ Справочник.Номенклатура ГДЕ Код = &Код И НЕ ПометкаУдаления` | **Tavsiya** — 2 ta qaytaramiz: 0 → topilmadi, 2 → noaniq (Sonar `PickRef` qoidasi). |

**Qoida (Sonar'dan olingan, §2.4)**: **yozish paytida** havola **faqat topiladi (mapping jadvalidan), hech qachon avtomatik yaratilmaydi**; 0 ta yoki 2+ ta topilsa — xato, `ref_not_found`. **[tasdiqlangan — Sonar kodi]** *Accept gate:* 1C'da yangi element yaratish faqat moslashtirish ustasida, preview + inson tasdig'i bilan alohida qadamda (`03` §4.3).

**Ommaviy topish (1000+ qator uchun muhim)**: har bir nomenklatura uchun alohida `НайтиПоКоду` chaqiruvi — 1000 ta COM chaqiruvi + 1000 ta SQL so'rov. Buning o'rniga **bitta so'rov** bilan hamma kodlarni massiv parametr orqali topamiz:

```
ВЫБРАТЬ Т.Ссылка, Т.Код, Т.Артикул
ИЗ Справочник.Номенклатура КАК Т
ГДЕ Т.Код В (&Коды) И НЕ Т.ПометкаУдаления
```
`&Коды` — 1C `Массив` (`conn.NewObject("Массив")` + `.Добавить(...)`), Sonar `ToOneC` shunday qiladi. **[tasdiqlangan — Sonar]** Natijani Python lug'atiga (`kod → COM-havola`) olamiz va qatorlarni to'ldirishda qayta ishlatamiz.

**Mapping jadvali (tavsiya)**: ERP'da `onec_mapping(base_id, erp_entity, erp_id, onec_type, onec_guid)` jadvali — bir marta moslashtirilgan (kod/shtrix-kod/qo'lda) GUID saqlanadi; keyingi kunlari `ПолучитьСсылку(guid)` bilan to'g'ridan-to'g'ri olinadi (so'rovsiz), lekin mavjudligi/`ПометкаУдаления` haftada bir tekshiriladi.

### 1.3. Hujjatni yaratish va jadval qismini to'ldirish

```
// 1C tili (COM orqali Python'dan aynan shu chaqiruvlar ketadi)
Док = Документы.ОтчетОРозничныхПродажах.СоздатьДокумент();
Док.Заполнить(Неопределено);           // ОбработкаЗаполнения — sukut bo'yicha qiymatlar (Организация, ...) — ixtiyoriy
Док.Дата        = '20261015235900';
Док.Организация = СсылкаОрганизации;
Док.Склад       = СсылкаСклада;        // БП'da chakana savdo nuqtasi = Склад (тип "Розничный магазин")
Док.Комментарий = "ERP #shop17/2026-10-15/ORP";

Стр = Док.Товары.Добавить();
Стр.Номенклатура = СсылкаТовара;
Стр.Количество   = 3;
Стр.Цена         = 12000;
Стр.Сумма        = 36000;
Стр.СтавкаНДС    = СсылкаСтавки;       // БП 3.0 RU: Перечисление.СтавкиНДС; Узбекистан: ***taxmin*** — Справочник.СтавкиНДС
Стр.СуммаНДС     = 3857.14;

Док.Записать(РежимЗаписиДокумента.Проведение, РежимПроведенияДокумента.Неоперативный);
```

Muhim nuqtalar:

- **`СоздатьДокумент()` bazaga hech narsa yozmaydi** — obyekt faqat xotirada; `Записать()`gacha uni tashlab yuborish mumkin. Sonar'ning "preview" usuli aynan shunga asoslangan: qiymatlar qo'yiladi, `Записать` chaqirilmaydi, before/after o'qiladi, obyekt tashlanadi (04-hujjat §2.2). **[tasdiqlangan — Sonar]**
- **`Номер`ni bermang** — yozish paytida avtomatik raqamlanadi (prefiks bilan). Raqamni o'zimiz bersak, unikallik nazorati (`КонтрольУникальности`) xatosi yoki 1C'ning raqamlash ketma-ketligi buziladi.
- **Forma hodisalari ishlamaydi**: buxgalter 1C formasida `Номенклатура`ni tanlaganda `ПриИзменении` handler narx, `СтавкаНДС`, `СчетУчета`, `СчетДоходов` va h.k.ni avtomatik to'ldiradi — **COM orqali bu chaqirilmaydi**. Obyekt modulidagi hodisalar (`ОбработкаЗаполнения`, `ПередЗаписью`, `ОбработкаПроверкиЗаполнения`*, `ОбработкаПроведения`, `ПриЗаписи`) esa **ishlaydi**. (*`ОбработкаПроверкиЗаполнения` — faqat `ПроверитьЗаполнение()` chaqirilganda yoki interaktiv yozishda; dasturiy `Записать()` uni **avtomatik chaqirmaydi** — biz o'zimiz chaqiramiz, 1.5.) **[tasdiqlangan — platforma hujjati, umumiy bilim]**
- **Schyotlar (БП)**: `Товары` qatorida `СчетУчета`, `СчетДоходов`, `СубконтоДоходов`, `СчетУчетаНДСПоРеализации`, `СчетРасходов` kabi ustunlar bor ***(taxmin — RU БП 3.0 bo'yicha; Uzbek БП 3.0 nomlari metadata'dan o'qilsin)***. Ular bo'sh qolsa, hujjat o'tadi, lekin **noto'g'ri provodka** beradi yoki `ОбработкаПроверкиЗаполнения` xato beradi. Yechimlar (1.4).

### 1.4. Hisob-kitob va schyotlarni to'ldirish — konfiguratsiya protseduralari

Bu eng nozik joy, chunki **har konfiguratsiyada boshqacha**:

| Konfiguratsiya | Qayerda to'ldiriladi (***taxmin***, bazaning o'zida tekshirilsin) |
|---|---|
| БП 3.0 (RU) | Hujjat menejer moduli/umumiy modullar: `СчетаУчетаВДокументах.ЗаполнитьРеквизитыСтроки...`, `ОбработкаТабличныхЧастей...`, `УчетНДСПереопределяемый...`; forma modulidagi `ТоварыНоменклатураПриИзменении` |
| УТ 11 / Розница | `ОбработкаТабличнойЧастиСервер.ОбработатьТЧ(ТабличнаяЧасть, СтруктураДействий, Кэш)` — `СтруктураДействий` ichida `"ЗаполнитьСтавкуНДС"`, `"ПересчитатьСуммуНДС"`, `"ПересчитатьСумму"` va h.k. (БСП-ga o'xshash umumiy modul) |
| УНФ | `ОбработкаТабличнойЧастиСервер` ga o'xshash, lekin boshqa kalitlar |
| Бухгалтерия для Узбекистана 3.0 | **noma'lum** — konfiguratsiya metadata'si va modullari (`Конфигуратор`da yoki `Метаданные` orqali) o'rganilishi kerak |

**COM'dan umumiy modulni chaqirish sharti**: umumiy modul xususiyatlarida **"Внешнее соединение"** (`ВнешнееСоединение`) belgisi yoqilgan bo'lishi shart — aks holda `conn.ИмяМодуля` COM orqali **ko'rinmaydi** ("Метод объекта не обнаружен"). Ko'p standart konfiguratsiyalarda bunday "Сервер"-faqat modullar tashqi ulanishga ochilmagan. Menejer modulining eksport protseduralari (`Документы.X.Процедура(...)`) esa tashqi ulanishda odatda mavjud. **[platforma qoidasi — tasdiqlangan; konkret modullar — taxmin]**

**Shuning uchun uch strategiya:**

1. **"Hammasini o'zimiz to'ldiramiz"** — ERP o'zi `СтавкаНДС`, `СуммаНДС` (1C'ning yaxlitlash qoidasi bilan, 2 xona), schyotlarni hisoblaydi. Schyotlarni olish uchun **"oltin namuna"**: shu bazadagi oxirgi qo'lda kiritilgan `ОтчетОРозничныхПродажах`ning qatorlarini so'rov bilan o'qib, nomenklatura/nomenklatura guruhi bo'yicha schyotlarni takrorlash; yoki `РегистрСведений.СчетаУчетаНоменклатуры` (БП) dan so'rov ***taxmin***. Kamchiligi — konfiguratsiya yangilansa mantiq mos kelmay qolishi mumkin.
2. **"1C hisoblasin, biz tekshiramiz"** — kerakli protseduralarni (agar tashqi ulanishga ochiq bo'lsa) chaqiramiz, keyin qiymatlarni **qayta o'qib** ERP hisobi bilan solishtiramiz; farq > 0.01 bo'lsa — yozmaymiz, preview'da ko'rsatamiz (Sonar'ning `Verify/Same` g'oyasi, 04 §2.5).
3. **Tashqi qayta ishlash (.epf) — tavsiya** (8-bo'lim): butun yaratish mantig'ini 1C tilida, 1C serverining ichida bajaramiz — barcha umumiy modullar (`ВнешнееСоединение` belgisidan qat'i nazar) mavjud, COM chaqiruvlari soni minimal.

### 1.5. Yozish/o'tkazish rejimlari

```
Док.Записать(РежимЗаписиДокумента.Проведение, РежимПроведенияДокумента.Неоперативный);
```

| Parametr | Qiymatlar | Izoh |
|---|---|---|
| `РежимЗаписиДокумента` | `Запись` / `Проведение` / `ОтменаПроведения` | `Проведение` — yozish + `ОбработкаПроведения` (harakatlar registrlarga) bitta tranzaksiyada. **[tasdiqlangan — Sonar `ComHandle.Write`]** |
| `РежимПроведенияДокумента` | `Оперативный` / `Неоперативный` | **Оперативный** faqat hujjat sanasi **bugungi** bo'lsa va metadata'da `ОперативноеПроведение = Разрешить` bo'lsa ma'noli; o'tgan sanali hujjatni operativ o'tkazishga urinish xato beradi ***(aniq matn — taxmin: «Оперативное проведение документа задним числом невозможно»)***. УТ 11'da qoldiq nazorati asosan **operativ** rejimda ishlaydi. Kun yakuni yarim tundan keyin ishlasa — **har doim `Неоперативный`**. |

**O'tkazishdan oldin tekshiruv**:
```
Если Не Док.ПроверитьЗаполнение() Тогда
    Сообщения = ПолучитьСообщенияПользователю(Истина);   // nima to'ldirilmagan
    // ... yozmaymiz, xatoni ERP'ga qaytaramiz
КонецЕсли;
```
`ПроверитьЗаполнение()` — `ОбработкаПроверкиЗаполнения` + metadata'dagi "Проверка заполнения = Выдавать ошибку" rekvizitlari. Interaktiv o'tkazishda platforma buni o'zi chaqiradi, dasturiy `Записать()`da — **yo'q** (shuning uchun dasturiy yozilgan hujjat "to'liq bo'lmagan" bo'lishi mumkin). **[platforma xatti-harakati — tasdiqlangan, umumiy bilim]**

**Hujjat sanasi va tartib**: bir kunning bir nechta hujjati bo'lsa, 1C ularni `Дата` (soniyagacha) + `Ссылка` bo'yicha tartiblaydi. Kun yakuni hujjatini `23:59:00` (yoki do'kon yopilish vaqti) bilan yozamiz — shu kunning kirim hujjatlaridan **keyin** turishi kerak, aks holda qoldiq yetmaydi.

### 1.6. `ОбменДанными.Загрузка` — nima o'chiriladi, qachon ishlatiladi

```
Док.ОбменДанными.Загрузка = Истина;
Док.Записать();
```

- **Bu asosan konfiguratsiya qoidasi, platforma emas** **[tasdiqlangan — ITS standarti №773, https://its.1c.ru/db/v8std/content/773/hdoc]**: platforma `ПередЗаписью`, `ПриЗаписи`, `ПередУдалением` handlerlarini **baribir chaqiradi**, lekin standart har bir handler (va obunalar) boshida `Если ОбменДанными.Загрузка Тогда Возврат; КонецЕсли;` bo'lishini talab qiladi. Standartdan iqtibos: «никакая бизнес-логика объекта не выполнялась при записи объекта через механизм обмена данными… все данные загружаются в ИБ «как есть», без искажений (изменений), проверок или каких-либо других дополнительных действий». Chaqiruvchi «берет на себя ответственность за целостность данных».
- Ya'ni: **to'ldirish, tekshiruv, sana taqiqlari (oddiy), hisob-kitoblar o'tkazib yuboriladi**. БСП almashuvi bu rejimda ham boshqa tugunlarga ro'yxatga olishni davom ettiradi; o'chirish uchun `Объект.ДополнительныеСвойства.Вставить("ОтключитьМеханизмРегистрацииОбъектов")` **[tasdiqlangan — std773]**.
- Platforma darajasidagi qo'shimcha ta'sirlar ***taxmin***: `ПроверитьЗаполнение` chaqirilmaydi; kod/raqam unikalligi nazorati o'tkaziladi-o'tkazilmasligi aniq emas; bo'sh raqam baribir avtomatik beriladi; `Записать(Проведение)` bilan `ОбработкаПроведения` **baribir chaqiriladi** (std773 qoidasi faqat ПередЗаписью/ПриЗаписи/ПередУдалением ga tegishli) — lekin ПередЗаписью'dagi tayyorgarlik (masalan, jami summani hisoblash) o'tkazib yuborilgani uchun natija noto'g'ri bo'lishi mumkin.
- Universal almashuvda (КД2/КД3, EnterpriseData) hujjatlar odatda shu rejimda yuklanadi, so'ng **alohida** `Проведение` bilan (yoki "отложенное проведение") o'tkaziladi.
- **Bizning qaror**: savdo hujjatlari uchun **ishlatmaymiz** — bizga 1C'ning to'liq mantig'i (provodkalar, НДС, qoldiqlar nazorati, sana taqiqi) kerak. Ishlatilsa ham, keyin `Записать(Проведение)`ni **Загрузка = Ложь** bilan qayta chaqirish kerak. Istisno: ma'lumotnomani (masalan `Номенклатура`) handlerlar to'sqinlik qilganda majburan yozish — faqat administrator ruxsati bilan.

### 1.7. Tranzaksiyalar COM orqali

Tashqi ulanishning global konteksti `НачатьТранзакцию()`, `ЗафиксироватьТранзакцию()`, `ОтменитьТранзакцию()`, `ТранзакцияАктивна()` ni beradi:

```python
conn.НачатьТранзакцию()
try:
    for spec in docs_of_the_day:          # masalan: ОРП + ПКО (inkassatsiya)
        write_one(conn, spec)
    conn.ЗафиксироватьТранзакцию()
except Exception:
    if conn.ТранзакцияАктивна():
        conn.ОтменитьТранзакцию()
    raise
```

Qoidalar va tuzoqlar:

- **Har bir `Записать(Проведение)` o'zi tranzaksiya** — bitta hujjat uchun tashqi tranzaksiya **kerak emas**.
- Tranzaksiya ichida biror `Записать` istisno tashlasa, tranzaksiya **"buzilgan"** deb belgilanadi: keyingi har qanday yozish "**В данной транзакции уже происходили ошибки**" xatosini beradi — faqat `ОтменитьТранзакцию()` qilish mumkin. Ya'ni tranzaksiya ichida "xatoni ushlab, davom etish" **ishlamaydi**. **[tasdiqlangan — umumiy 1C bilimi]**
- **Boshqariladigan qulflar** (managed locks) tranzaksiya oxirigacha ushlanadi. Uzun tranzaksiya (1000 hujjat) — foydalanuvchilar o'sha registrlarga yozolmay qoladi → "**Конфликт блокировок при выполнении транзакции: Превышено максимальное время ожидания предоставления блокировки**" (sukut bo'yicha ~20 soniya). **Tavsiya**: bitta hujjat = bitta tranzaksiya; atomiklikni **idempotentlik** bilan ta'minlaymiz (qayta yuborish xavfsiz), katta tranzaksiya bilan emas.
- Fayl bazada qulf — butun jadval darajasida (fayl rejimida boshqariladigan qulf ham jadval darajasiga "kattalashadi" ***taxmin***) — shuning uchun fayl bazaga kun yakuni yozuvini **ish vaqtidan tashqari** (masalan 23:30–06:00) qilish kerak.
- **Qulf konflikti — qayta urinish xavfsiz** (tranzaksiya to'liq bekor bo'lgan): 3 marta, 5/15/45 soniya kechikish bilan.

### 1.8. Xatolar va xabarlar matnini olish

Python tomonida COM istisnosi `pywintypes.com_error` keladi:

```python
import pywintypes

try:
    doc.Записать(write_mode_post, posting_mode_nonop)
except pywintypes.com_error as e:
    hr, msg, exc, arg = e.args
    text = exc[2] if exc else msg          # exc = (wcode, source, description, helpfile, helpctx, scode)
    msgs = drain_messages(conn)            # 1C xabarlari (Сообщить / СообщениеПользователю)
    raise OneCWriteError(classify(text), text, msgs)
```

- `exc[2]` — 1C xato matni, odatda shakli: `{Документ.ОтчетОРозничныхПродажах.МодульОбъекта(123)}: Ошибка при вызове метода контекста (Записать): Операция не выполнена` va h.k. **Asl sabab ko'pincha xabarlar navbatida**, istisnoda emas: masalan `ОбработкаПроведения` ichida `Отказ = Истина` + `ОбщегоНазначения.СообщитьПользователю("Недостаточно товара ...")` bo'lsa, istisno matni faqat "Не удалось провести ..." / "Операция не выполнена" bo'ladi.
- **Xabarlarni yig'ish**: `ПолучитьСообщенияПользователю(Удалять)` — tashqi ulanish kontekstida ham ishlaydi, `ФиксированныйМассив` (`СообщениеПользователю`: `.Текст`, `.Поле`, `.КлючДанных`) qaytaradi. Sonar har bir yozishdan oldin `TakeMessages()` bilan navbatni tozalaydi, xatoda esa uni xato matniga qo'shadi (02 §1.4, 04 §2.2). **[tasdiqlangan — Sonar]**

```python
def drain_messages(conn) -> list[str]:
    arr = conn.ПолучитьСообщенияПользователю(True)
    out = []
    for i in range(arr.Количество()):
        out.append(str(arr.Получить(i).Текст))
    return out
```

- `ОписаниеОшибки()` / `ИнформацияОбОшибке()` — faqat 1C kodi ichida (masalan .epf'da `Попытка ... Исключение`) mavjud; COM mijozida o'rniga `com_error` ishlatiladi. .epf yondashuvida (8-bo'lim) `ПодробноеПредставлениеОшибки(ИнформацияОбОшибке())` bilan to'liq stack olish mumkin.
- **Xato tasnifi** (Sonar `ErrorMap` asosida, kengaytirilgan):

| Matn qismi (rus) | Bizning kod | Qayta urinish? |
|---|---|---|
| `Конфликт блокировок`, `Превышено максимальное время ожидания` | `locked` | ha (backoff) |
| `Недостаточно`, `не хватает`, `остаток` | `insufficient_stock` | yo'q — buxgalter qarori |
| `дата запрета`, `запрет изменения`, `закрыт период` | `period_closed` | yo'q |
| `Недостаточно прав`, `Нарушение прав доступа` | `access_denied` | yo'q |
| `Не заполнено поле`, `Поле ... не заполнено` | `bad_field` | yo'q |
| `Оперативное проведение` | `bad_posting_mode` | ha, `Неоперативный` bilan |
| `лиценз` | `license` | ha, keyinroq |
| `монопольн`, `установлена блокировка` | `base_locked` (yangilanish/konfigurator ochiq) | ha, keyinroq |
| COM `-2147417848` / `-2147023174` | `connection_lost` | ha — **idempotentlik tekshiruvidan keyin** |
| boshqasi | `write_failed` | yo'q |

### 1.9. Boshqa foydalanuvchilar bilan bir vaqtda ishlash

- 1C server rejimida (`Режим управления блокировкой = Управляемый`) — konfiguratsiya hujjat o'tkazishda kerakli registr diapazonlarini qulflaydi (`БлокировкаДанных`). Kassir/buxgalter bir vaqtda shu ombor bo'yicha hujjat o'tkazsa — biri kutadi (20s) yoki xato oladi. Kun yakunida — muammo kam.
- **Obyektni tahrirlash qulfi**: agar buxgalter shu hujjatni formada ochib, o'zgartirib turgan bo'lsa (`Заблокировать()`), COM'dan uni yozish xato beradi ("Ошибка блокировки объекта. Объект уже заблокирован"). Yangi hujjat yaratishda bu yo'q; mavjudini tuzatishda — `Заблокировать()` + `ВерсияДанных` tekshiruvi (Sonar `ExpectVersion`, 04 §2.5).
- **Optimistik qulf**: mavjud hujjatni yangilashda preview vaqtidagi `ВерсияДанных`ni saqlaymiz, yozishdan oldin solishtiramiz — mos kelmasa `changed`, qayta preview. **[tasdiqlangan — Sonar]**

### 1.10. 1000+ qator — ishlash tezligi

COM chaqiruvlari (fayl bazada — jarayon ichida, server bazada — 1C server bilan tarmoq orqali) har biri arzon, lekin ko'p: 1000 qator × ~8 maydon = ~8 000 `IDispatch` chaqiruvi + har bir rus nomi uchun `GetIDsOfNames`. Amaliy maslahatlar:

1. **Kun savdosini agregatlash**: ОРП qatori = (nomenklatura, narx, stavka) bo'yicha guruhlangan kunlik yig'indi — chek emas. Odatda 1000 chek → 150–400 qator.
2. **Havolalarni bitta so'rov bilan** oldindan topish (1.2).
3. **Enum/havola obyektlarini keshlash**: `conn.РежимЗаписиДокумента.Проведение`, stavka havolalari — bir marta olinadi.
4. **`ТаблицаЗначений` + `Загрузить()`**: Python'da 1C `ТаблицаЗначений`ni to'ldirib (`conn.NewObject("ТаблицаЗначений")`), keyin `Док.Товары.Загрузить(ТЗ)` — chaqiruvlar soni deyarli bir xil, foyda kam ***taxmin***.
5. **Eng katta foyda — .epf** (8-bo'lim): Python bitta JSON satrini uzatadi, butun loop 1C ichida — COM chaqiruvlari ~10 taga tushadi.
6. **Juda katta hujjatni bo'lish**: 1C'da 5 000+ qatorli hujjat formada sekin ochiladi, o'tkazish uzoq tranzaksiya — ОРПni kassa/smena yoki tovar guruhi bo'yicha bo'lish mumkin ***taxmin — buxgalter bilan kelishilsin***.
7. Pywin32'da **`win32com.client.Dispatch`** (dinamik) ishlatiladi — `gencache.EnsureDispatch` (early binding) 1C uchun ishlamaydi, chunki 1C obyektlari type library bermaydi (har bir konfiguratsiya o'z metadata'si).

### 1.11. COM obyektlarini bo'shatish va jarayon gigiyenasi

- Python'da COM obyekt havola soni nolga tushganda `Release` chaqiriladi — katta loop'larda vaqtinchalik obyektlarni (`row`, `ref`) `del` qilish yoki funksiya doirasida saqlash yetarli. Sonar C#'da har birini `Marshal.ReleaseComObject` qiladi (02 §2.2). **[tasdiqlangan — Sonar]**
- **Ulanishni yopish**: 1C tashqi ulanishida `Disconnect` metodi yo'q — `conn = None; connector = None; gc.collect()` → seans yopiladi (va **litsenziya bo'shaydi**). Agar Python jarayoni "osilib" qolsa, seans 1C serverida qoladi va litsenziya band bo'ladi ***taxmin — server seansni TCP uzilishida tozalaydi, lekin kechikish bilan***.
- **Tavsiya (Sonar modeli)**: 1C bilan ishlovchi kod **alohida worker jarayonda** (masalan `erp_onec_worker.exe`, stdin/stdout JSON-lines), asosiy agent uni boshqaradi: timeout bo'lsa — jarayonni o'ldiradi (`Kill`), keyingi chaqiruvda yangisini ochadi; bo'sh turganda 10 daqiqadan keyin yopadi; **yozish amallarini avtomatik qayta urinmaydi** (idempotentlik tekshiruvisiz). **[tasdiqlangan — Sonar 02 §1.5]**
- Xotira oqishi: uzun yashovchi COM ulanish (soatlab) xotira to'playdi ***taxmin*** — har kun yakuni uchun yangi worker jarayon ochish eng soddasi.

### 1.12. Python pywin32 xususiyatlari

| Mavzu | Tafsilot |
|---|---|
| Rus nomlar | Python 3 identifikatorlarida kirill harflari **ruxsat etilgan** — `conn.Документы.ОтчетОРозничныхПродажах` to'g'ridan-to'g'ri yoziladi. Dinamik nom uchun `getattr(conn.Документы, doc_name)`. Ingliz nomlari ham ishlaydi (`conn.Documents`) — Sonar ikkalasini sinaydi. |
| Metod vs xususiyat | Argumentsiz metod — qavs bilan: `.СоздатьДокумент()`, `.Количество()`. pywin32 dinamik dispatch ba'zan argumentsiz metodni xususiyat deb chaqiradi — natija COM-obyekt bo'lsa, qavs bilan qayta chaqirish kerak ***taxmin***. |
| Xususiyat yozish | `doc.Дата = ...` — pywin32 `__setattr__` orqali `DISPATCH_PROPERTYPUT`. Dinamik nom uchun `setattr(doc, "Дата", v)`. |
| Sanalar | `datetime.datetime(2026,10,15,23,59,0)` — **naive (tz'siz)** uzating. pywin32 qaytargan sanalar `pywintypes.datetime` (ba'zi versiyalarda tz=UTC belgisi bilan, lekin qiymat **mahalliy vaqt**) — qayta solishtirishda `.replace(tzinfo=None)`. "Bo'sh sana" = `0001-01-01` (Sonar: yil ≤ 100 → `null`). Ishonchli muqobil: `conn.XMLЗначение(conn.Тип("Дата"), "2026-10-15T23:59:00")`. |
| Sonlar | COM orqali sonlar `double` bo'lib qaytadi — 15 xonagacha aniq. Pul uchun: Python'da `Decimal`, uzatishda `float(round(x,2))` yoki aniq bo'lishi uchun `conn.XMLЗначение(conn.Тип("Число"), "36000.00")`. Sonar ham `Число("...")` orqali qaytadan konvertatsiya qiladi (02 §2.6.1). **[tasdiqlangan — Sonar]** |
| Boolean | `True/False` → 1C `Булево`. |
| `Неопределено` / bo'sh havola | `None` → `Неопределено`. Bo'sh havola: `Справочники.X.ПустаяСсылка()`. Havolaning bo'shligini tekshirish: `ref.Пустая()`. |
| GUID | `str(conn.XMLСтрока(ref))` → `"a1b2c3d4-..."`; yoki `ref.УникальныйИдентификатор()` → `conn.String(...)`. Teskari: `conn.NewObject("УникальныйИдентификатор", "a1b2...")`. |
| `Новый` | `Новый X(...)` o'rniga `conn.NewObject("X", ...)` (yoki `conn.НовыйОбъект`) — `Запрос`, `Массив`, `Структура`, `ТаблицаЗначений`, `УникальныйИдентификатор`. |
| Threading | 1C COM — **STA**. Har bir oqimda `pythoncom.CoInitialize()`; ulanishni **yaratgan oqimdan tashqari** ishlatmang (marshalling kerak bo'ladi va 1C'da ishonchsiz). Bitta baza = bitta oqim = bitta ulanish (Sonar: bazaga `SemaphoreSlim(1,1)`). asyncio'dan foydalansangiz — 1C ishini `ThreadPoolExecutor(max_workers=1)` ichida. |
| Xizmat (service) sifatida | Windows xizmati `LocalSystem` ostida ishlasa, 1C mijoz fayllari/`%APPDATA%` va tarmoq ulanishlari boshqacha — agentni **maxsus foydalanuvchi** ostida ishga tushiring ***taxmin***. |

---

## 2. Python ishlaydigan misol — «Отчет о розничных продажах»

> Quyidagi kod "deyarli haqiqiy": rekvizit nomlari **RU БП 3.0** asosida (***taxmin*** — Uzbek БП 3.0'da metadata'dan tekshiriladi; agent ishga tushganda `Метаданные.Документы.ОтчетОРозничныхПродажах` dan rekvizit/ТЧ ro'yxatini o'qib, mapping konfiguratsiyasini tasdiqlaydi).

```python
"""onec_writer.py — kun yakuni ОРП'ni 1C'ga yozish (Windows agent, worker jarayon ichida)."""
from __future__ import annotations
import uuid, datetime as dt
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
import pythoncom, pywintypes, win32com.client

ERP_NS = uuid.UUID("6f1d3c2a-0000-4000-8000-0000000e5b01")   # bizning doimiy namespace

@dataclass
class Line:
    sku_code: str          # 1C Номенклатура.Код (mapping orqali)
    qty: Decimal
    price: Decimal
    amount: Decimal
    vat_rate: str          # "12%" / "Без НДС"
    vat_amount: Decimal

@dataclass
class Payment:
    kind_code: str         # ВидыОплатОрганизаций.Код (Uzcard/Humo terminal)
    amount: Decimal

@dataclass
class DailySales:
    shop_id: str
    day: dt.date
    org_inn: str
    warehouse_code: str
    lines: list[Line]
    payments: list[Payment]   # kartadan to'lovlar; naqd = jami - kartalar

    @property
    def doc_uuid(self) -> str:
        # Deterministik: bir xil do'kon+kun+tur → bir xil GUID → idempotent
        return str(uuid.uuid5(ERP_NS, f"{self.shop_id}|{self.day.isoformat()}|ORP"))

    @property
    def marker(self) -> str:
        return f"ERP #{self.shop_id}/{self.day.isoformat()}/ORP"


class OneCError(Exception):
    def __init__(self, code: str, text: str, messages: list[str] | None = None):
        super().__init__(f"{code}: {text}")
        self.code, self.text, self.messages = code, text, messages or []


def connect(conn_str: str):
    pythoncom.CoInitialize()
    connector = win32com.client.Dispatch("V83.COMConnector")
    return connector, connector.Connect(conn_str)


def num(conn, d: Decimal):
    # pul qiymatlarini double xatosiz uzatish
    return conn.XMLЗначение(conn.Тип("Число"), format(d, "f"))


def drain_messages(conn) -> list[str]:
    arr = conn.ПолучитьСообщенияПользователю(True)
    return [str(arr.Получить(i).Текст) for i in range(arr.Количество())]


def find_refs(conn, catalog: str, codes: list[str]) -> dict[str, object]:
    """Bitta so'rov bilan kod → havola. 0 yoki 2+ → xato (taxmin qilinmaydi)."""
    q = conn.NewObject("Запрос")
    q.Текст = f"""
        ВЫБРАТЬ Т.Ссылка КАК Ссылка, Т.Код КАК Код
        ИЗ Справочник.{catalog} КАК Т
        ГДЕ Т.Код В (&Коды) И НЕ Т.ПометкаУдаления И НЕ Т.ЭтоГруппа"""
    arr = conn.NewObject("Массив")
    for c in codes:
        arr.Добавить(c)
    q.УстановитьПараметр("Коды", arr)
    sel = q.Выполнить().Выбрать()
    found: dict[str, list] = {}
    while sel.Следующий():
        found.setdefault(str(sel.Код).strip(), []).append(sel.Ссылка)
    missing = [c for c in codes if c not in found]
    dup = [c for c, v in found.items() if len(v) > 1]
    if missing or dup:
        raise OneCError("ref_not_found", f"{catalog}: topilmadi={missing[:20]}, noaniq={dup[:20]}")
    return {c: v[0] for c, v in found.items()}


def existing_doc(conn, doc_uuid: str, marker: str):
    """1-qatlam: GUID bo'yicha; 2-qatlam: Комментарий markeri bo'yicha (masalan, qo'lda nusxa)."""
    ref = conn.Документы.ОтчетОРозничныхПродажах.ПолучитьСсылку(
        conn.NewObject("УникальныйИдентификатор", doc_uuid))
    q = conn.NewObject("Запрос")
    q.Текст = """
        ВЫБРАТЬ ПЕРВЫЕ 2 Д.Ссылка КАК Ссылка, Д.Проведен КАК Проведен, Д.ПометкаУдаления КАК ПУ
        ИЗ Документ.ОтчетОРозничныхПродажах КАК Д
        ГДЕ Д.Ссылка = &Ссылка ИЛИ Д.Комментарий ПОДОБНО &Маркер"""
    q.УстановитьПараметр("Ссылка", ref)
    q.УстановитьПараметр("Маркер", "%" + marker + "%")
    sel = q.Выполнить().Выбрать()
    rows = []
    while sel.Следующий():
        rows.append((sel.Ссылка, bool(sel.Проведен), bool(sel.ПУ)))
    if len(rows) > 1:
        raise OneCError("duplicate", f"{marker}: 1C'da 2+ hujjat — qo'lda tekshiring")
    return ref, (rows[0] if rows else None)


# Accept gate: bu namuna "posted bo'lsa — already_exists" qiladi; kanonik algoritm (revision'da yangilash,
# kontent xeshi, expect_version / ВерсияДанных) — 04 §5.3. Vaqt sloti 23:59 o'rniga 03 §5.1 (ОРП 23:50:00).
def write_orp(conn, s: DailySales, *, preview: bool = False) -> dict:
    conn.ПолучитьСообщенияПользователю(True)          # navbatni tozalash (Sonar TakeMessages)
    ref, ex = existing_doc(conn, s.doc_uuid, s.marker)
    if ex is not None:
        doc_ref, posted, deleted = ex
        if posted and not deleted:
            return {"status": "already_exists", **read_back(conn, doc_ref)}
        # yozilgan, lekin o'tkazilmagan (oldingi urinish yarim qolgan) → ochib qayta o'tkazamiz
        doc = doc_ref.ПолучитьОбъект()
        if deleted:
            doc.УстановитьПометкуУдаления(False)
        doc.Товары.Очистить(); doc.Оплата.Очистить()
    else:
        doc = conn.Документы.ОтчетОРозничныхПродажах.СоздатьДокумент()
        doc.УстановитьСсылкуНового(ref)                # GUID = bizning uuid5
        doc.Заполнить(None)                            # ОбработкаЗаполнения: sukut qiymatlari

    org = conn.Справочники.Организации.НайтиПоРеквизиту("ИНН", s.org_inn)
    if org.Пустая():
        raise OneCError("ref_not_found", f"Организация ИНН={s.org_inn}")
    wh = find_refs(conn, "Склады", [s.warehouse_code])[s.warehouse_code]
    items = find_refs(conn, "Номенклатура", sorted({l.sku_code for l in s.lines}))
    pay_kinds = find_refs(conn, "ВидыОплатОрганизаций", sorted({p.kind_code for p in s.payments})) if s.payments else {}

    doc.Дата = dt.datetime.combine(s.day, dt.time(23, 59, 0))
    doc.Организация = org
    doc.Склад = wh
    doc.СуммаВключаетНДС = True                       # chakana narxlar НДС bilan  (taxmin: rekvizit nomi)
    doc.Комментарий = s.marker

    for l in s.lines:
        r = doc.Товары.Добавить()
        r.Номенклатура = items[l.sku_code]
        r.Количество = num(conn, l.qty)
        r.Цена = num(conn, l.price)
        r.Сумма = num(conn, l.amount)
        r.СтавкаНДС = vat_ref(conn, l.vat_rate)       # konfiguratsiyaga bog'liq (enum yoki katalog)
        r.СуммаНДС = num(conn, l.vat_amount)
        # Schyotlar: strategiya 1.4 — bu yerda "oltin namuna" keshidan:
        # r.СчетУчета, r.СчетДоходов, r.СубконтоДоходов, r.СчетУчетаНДСПоРеализации = accounts_for(...)
    for p in s.payments:
        r = doc.Оплата.Добавить()
        r.ВидОплаты = pay_kinds[p.kind_code]
        r.Сумма = num(conn, p.amount)

    # Preview: 1C'ning o'zi hisoblagan qiymatlarni o'qib, yozmasdan qaytamiz (Sonar uslubi)
    if preview:
        return {"status": "preview", "after": snapshot(doc)}   # doc tashlanadi — bazaga tegmaydi

    if not doc.ПроверитьЗаполнение():
        raise OneCError("bad_field", "Проверка заполнения", drain_messages(conn))

    try:
        doc.Записать(conn.РежимЗаписиДокумента.Проведение,
                     conn.РежимПроведенияДокумента.Неоперативный)
    except pywintypes.com_error as e:
        text = (e.excepinfo[2] if e.excepinfo else None) or str(e)
        raise OneCError(classify(text), text, drain_messages(conn)) from None

    result = read_back(conn, doc.Ссылка)
    check_totals(s, result)                            # farq bo'lsa — alert (hujjat allaqachon o'tgan!)
    return {"status": "created", **result}


def read_back(conn, ref) -> dict:
    """Reconciliation: o'tkazilgan hujjatning jamilari + provodkalar soni."""
    q = conn.NewObject("Запрос")
    q.Текст = """
        ВЫБРАТЬ Д.Номер КАК Номер, Д.Проведен КАК Проведен, Д.ВерсияДанных КАК Версия,
               ЕСТЬNULL(Т.Сумма, 0) КАК Сумма, ЕСТЬNULL(Т.СуммаНДС, 0) КАК СуммаНДС,
               ЕСТЬNULL(Т.Строк, 0) КАК Строк, ЕСТЬNULL(О.Сумма, 0) КАК Оплата
        ИЗ Документ.ОтчетОРозничныхПродажах КАК Д
        ЛЕВОЕ СОЕДИНЕНИЕ (ВЫБРАТЬ Ссылка, СУММА(Сумма) КАК Сумма, СУММА(СуммаНДС) КАК СуммаНДС,
                                  КОЛИЧЕСТВО(*) КАК Строк
                          ИЗ Документ.ОтчетОРозничныхПродажах.Товары ГДЕ Ссылка = &Ссылка
                          СГРУППИРОВАТЬ ПО Ссылка) КАК Т ПО Т.Ссылка = Д.Ссылка
        ЛЕВОЕ СОЕДИНЕНИЕ (ВЫБРАТЬ Ссылка, СУММА(Сумма) КАК Сумма
                          ИЗ Документ.ОтчетОРозничныхПродажах.Оплата ГДЕ Ссылка = &Ссылка
                          СГРУППИРОВАТЬ ПО Ссылка) КАК О ПО О.Ссылка = Д.Ссылка
        ГДЕ Д.Ссылка = &Ссылка;

        ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Проводок, СУММА(Х.Сумма) КАК Оборот
        ИЗ РегистрБухгалтерии.Хозрасчетный КАК Х
        ГДЕ Х.Регистратор = &Ссылка"""
    q.УстановитьПараметр("Ссылка", ref)
    res = q.ВыполнитьПакет()
    a = res.Получить(0).Выбрать(); a.Следующий()
    b = res.Получить(1).Выбрать(); b.Следующий()
    return {
        "guid": str(conn.XMLСтрока(ref)), "number": str(a.Номер), "posted": bool(a.Проведен),
        "version": str(a.Версия), "lines": int(a.Строк),
        "total": Decimal(str(a.Сумма)).quantize(Decimal("0.01")),
        "vat": Decimal(str(a.СуммаНДС)).quantize(Decimal("0.01")),
        "paid_card": Decimal(str(a.Оплата)).quantize(Decimal("0.01")),
        "gl_entries": int(b.Проводок or 0),
    }


def check_totals(s: DailySales, r: dict) -> None:
    exp_total = sum((l.amount for l in s.lines), Decimal(0))
    exp_vat = sum((l.vat_amount for l in s.lines), Decimal(0))
    if not r["posted"] or r["gl_entries"] == 0:
        raise OneCError("not_posted", f"Hujjat {r['number']} o'tmagan yoki provodka yo'q")
    if abs(r["total"] - exp_total) > Decimal("0.01") or abs(r["vat"] - exp_vat) > Decimal("0.01"):
        raise OneCError("mismatch", f"ERP {exp_total}/{exp_vat} ≠ 1C {r['total']}/{r['vat']}")
```

Izohlar:
- `vat_ref`, `snapshot`, `classify`, `accounts_for` — konfiguratsiyaga bog'liq yordamchilar (qisqartirildi).
- `Хозрасчетный` — БП registr nomi; Uzbek БП 3.0'da ham shunday bo'lishi ehtimoli yuqori ***taxmin***. УТ 11/Розница'da provodka yo'q — o'rniga `РегистрНакопления.ТоварыНаСкладах` / `ВыручкаИСебестоимостьПродаж` harakatlari tekshiriladi.
- `doc.Заполнить(None)` dan **keyin** bizning qiymatlarni qo'yamiz (aks holda sukut qiymatlar bizning qiymatlarni bosib ketadi). Sonar ham `fill`dan keyin "metod sizning qiymatingizni o'zgartirdi" ogohlantirishini beradi (04 §2.7).
- Naqd tushum alohida qator emas: БП'da `Оплата` jadvali — faqat naqdsiz (karta/sertifikat); qolgani avtomatik naqd (50-schyot / Uzbek 5010) deb hisoblanadi ***taxmin — RU БП mantig'i***. Inkassatsiya — alohida `РасходныйКассовыйОрдер`.
- **Muhim tuzoq — qoldiq**: agar 1C bazada tovar kirimi (`ПоступлениеТоваровУслуг`) kiritilmagan bo'lsa, ОРП o'tishi **manfiy qoldiq** beradi yoki rad etiladi (БП'da "Разрешить списание запасов при отсутствии остатков" sozlamasiga bog'liq). Demak ERP faqat savdoni emas, **kirimlarni ham** 1C'ga yozishi kerakmi — mahsulot qarori (R-boshqa bo'lim).

---

## 3. OData orqali yozish

**Rad etilgan (asoschi qarori, 2026-10-15)** — 1C'dan hech narsa nashr qilinmaydi; faqat COM.

---

## 4. EnterpriseData — qisqa eslatma

Asosiy yo'l emas (asoschi qarori — faqat COM), lekin bilish foydali:

- EnterpriseData XDTO sxemasida **`Документ.ОтчетОРозничныхПродажах` bor** **[tasdiqlangan — XSD, https://github.com/MaxiStyle/1c-enterprise-data]**: `КлючевыеСвойства` (`Ссылка` UUID, `Дата`, `Номер`, `Организация`), sarlavha (`Склад`, `ТипЦен`, `СуммаВключаетНДС`, `Налогообложение`, `СтатьяДДС`, `Комментарий`...), `Товары/Строка` (`ДанныеНоменклатуры{Номенклатура, Характеристика, Упаковка, Штрихкод}`, `Количество`, `Цена`, `Сумма`, `СтавкаНДС`, `СуммаНДС`, `СчетУчета`, `СчетДоходов`...), `ОплатаПлатежнымиКартами`, `ОплатаСертификатами`, `ОплатаБанковскимиКредитами`. Alohida `Документ.ПКОРозничнаяВыручка` ham bor.
- **Tuzoq**: sxemadagi `СтавкиНДС` enum — faqat Rossiya stavkalari (НДС0/10/18/20, БезНДС); **12% (O'zbekiston) yo'q** → Uzbek konfiguratsiyalari uchun format kengaytmasi kerak ***taxmin***.
- Qabul qiluvchi 1C: «Синхронизация данных → Другая программа» yoki `ВыгрузкаЗагрузкаEnterpriseData.epf`; moslashtirish avval `Ссылка` UUID bo'yicha (`РегистрСведений.ПубличныеИдентификаторыСинхронизируемыхОбъектов`), keyin qidiruv maydonlari bo'yicha — bir xil UUID qayta yuklansa **yangilanadi** (idempotent) ***taxmin***. Yuklash `ОбменДанными.Загрузка` rejimida, keyin o'tkazish/отложенное проведение.
- 1c.uz'dagi O'zbekiston mahsulotlari (БП 8 для Узбекистана ред. 3.0, УТ, Розница 3.0) sahifalarida EnterpriseData haqida hech narsa yo'q (https://1c.uz/v8/generic_products/index.php) — qo'llab-quvvatlash **tasdiqlanmagan**.
- **Xulosa**: EnterpriseData'ni COM ustidan ham ishlatish mumkin (fayl yaratib, 1C ichida yuklash), lekin u o'zi `Загрузка` rejimi + moslashtirish qoidalari + Uzbek stavkalari muammosini olib keladi. To'g'ridan-to'g'ri COM/`.epf` soddaroq va nazoratliroq.

---

## 5. Idempotentlik va tashqi ID — konfiguratsiyani o'zgartirmasdan

### 5.1. Variantlar

| # | Usul | Konf. o'zgaradimi | Ishonchlilik | Izoh |
|---|---|---|---|---|
| A | **O'z GUID'imiz**: `ПолучитьСсылку(Новый УникальныйИдентификатор(uuid5))` + `УстановитьСсылкуНового` | yo'q | **eng yuqori** — 1C'da `Ссылка` unikal, ikkinchi marta shu GUID bilan yozish fizik jihatdan imkonsiz (PK buzilishi) | **Asosiy usul** |
| B | `Комментарий` markeri `"ERP #..."` (Sonar uslubi) | yo'q | o'rta — buxgalter kommentariyani o'zgartirishi/o'chirishi mumkin; `ПОДОБНО` qidiruvi sekin (indekssiz) | Ikkinchi qatlam + inson uchun ko'rinadigan iz |
| C | Agent mahalliy jurnali (`idem` → natija, SQLite) | yo'q | o'rta — "javob kelmadi" holatini qoplamaydi | Sonar `TaskJournal` (04 §4.3) |
| D | Kengaytma (`.cfe`) bilan `РегистрСведений.ERPВнешниеИдентификаторы` (`ERP_ID` → `Ссылка`) | **ha** (kengaytma — konfiguratsiyani "qo'llab-quvvatlashdan" chiqarmaydi, lekin baza tuzilmasi o'zgaradi) | yuqori | Faqat GUID usuli mumkin bo'lmasa (masalan bitta ERP hujjati → bir nechta 1C hujjati, yoki 1C hujjati keyin qo'lda qayta yaratilgan) |
| E | `Номер`ni o'zimiz berish (`ERP-0001`) | yo'q | past — raqamlash/prefiks/unikallik 1C qoidalari bilan to'qnashadi | Tavsiya etilmaydi |

### 5.2. GUID usuli — mexanika va tuzoqlar

```
Ссылка = Документы.ОтчетОРозничныхПродажах.ПолучитьСсылку(Новый УникальныйИдентификатор("3f6c...-..."));
Объект = Ссылка.ПолучитьОбъект();     // mavjud bo'lmasa → Неопределено (istisno emas) — 8.3 (tasdiqlansin, §5.4)
Если Объект = Неопределено Тогда
    Объект = Документы.ОтчетОРозничныхПродажах.СоздатьДокумент();
    Объект.УстановитьСсылкуНового(Ссылка);
    // ... to'ldirish
    Объект.Записать(РежимЗаписиДокумента.Проведение);
КонецЕсли;
```

- `ПолучитьСсылку(УИД)` — **bazaga murojaat qilmaydi**, shunchaki havola qiymati quradi; obyekt yo'q bo'lsa, havola "buzilgan" (`<Объект не найден>`) bo'ladi. Mavjudligini **so'rov** (`ГДЕ Ссылка = &Ссылка`) yoki `ПолучитьОбъект()` bilan tekshiramiz.
- `УстановитьСсылкуНового(Ссылка)` — faqat **hali yozilmagan yangi** obyektda, birinchi `Записать()`dan oldin. Keyin `Объект.Ссылка` aynan shu GUID bo'ladi. Universal almashuv qoidalari (КД2) va РИБ aynan shu mexanizm bilan obyektlarni boshqa bazada **bir xil GUID** bilan yaratadi. **[tasdiqlangan — 1C almashuv amaliyoti, sintaksis yordamchisi]**
- `ПолучитьНовуюСсылку` / `ПолучитьСсылкуНового()` — shu belgilangan havolani o'qish.
- **Deterministik UUID**: `uuid5(NAMESPACE, f"{shop_id}|{date}|ORP")` — qayta hisoblaganda o'sha GUID; ERP o'z jadvalida ham saqlaydi. Agar bitta kun uchun hujjat **tuzatilsa** (qaytarish, kech kelgan chek), yangi hujjat (`|ORP|v2`) yoki mavjudini qayta yozish (2-bo'limdagi "yarim qolgan" yo'l kabi) — mahsulot qarori.
- **Tuzoq 1 — o'chirilgan hujjat**: buxgalter hujjatni o'chirishga belgilasa (`ПометкаУдаления`) — biz uni "bor" deb ko'ramiz va qayta yaratmaymiz (to'g'ri: ERP'da ogohlantirish chiqaramiz). Agar "Удаление помеченных" bilan **butunlay o'chirilsa** — o'sha GUID bo'sh, keyingi yuborishda **qayta yaratiladi** (bu kutilgan xatti-harakatmi — buxgalter bilan kelishilsin).
- **Tuzoq 2 — buxgalter hujjatni nusxalasa** (Копировать): yangi nusxa boshqa GUID oladi, lekin `Комментарий` markeri ko'chadi → B-usul "2 ta topildi" deydi → `duplicate` xatosi (bu yaxshi — inson tekshiradi).
- **Tuzoq 3 — RIB/almashuv**: agar do'kon bazasi boshqa 1C bazaga (masalan markaziy) almashuv bilan ulangan bo'lsa, GUID o'sha bazaga ham ko'chadi — muammo emas, aksincha tracability.
- **Tuzoq 4 — hech qachon tasodifiy `uuid4`** — qayta urinishda boshqa GUID bo'lib, dublikat yaratiladi.

### 5.3. Tavsiya

**A (GUID) + B (marker) + C (jurnal)**, D — faqat kerak bo'lganda. Konfiguratsiya o'zgarmaydi; buxgalter hujjatda `ERP #shop17/2026-10-15/ORP` ni ko'radi; texnik dublikat imkonsiz.

### 5.4. Tasdiqlanishi kerak (real bazada test)

- `ПолучитьОбъект()` mavjud bo'lmagan havolada 8.3.2x'da `Неопределено` qaytarishi (eski versiyalarda istisno bo'lgan bo'lishi mumkin ***taxmin***).
- `УстановитьСсылкуНового` COM orqali `conn.NewObject("УникальныйИдентификатор", s)` bilan ishlashi.
- Uzbek БП 3.0'da `ОтчетОРозничныхПродажах` ning `ПередЗаписью`/`ПриЗаписи` handlerlari `Ссылка`ni o'zgartirmasligi.

---

## 6. Yopiq davrlar, o'tgan davrga yozish, qayta o'tkazish

### 6.1. «Дата запрета изменения» (БСП)

- БСП asosidagi konfiguratsiyalarda (БП 3.0, УТ 11, Розница, УНФ — va ***taxmin***, Uzbek БП 3.0) — `Администрирование → Поддержка и обслуживание`/`Настройки программы` ichida **«Даты запрета изменения»**: umumiy sana yoki foydalanuvchi/bo'lim (organizatsiya) bo'yicha. Saqlanadi: `РегистрСведений.ДатыЗапретаИзменения`. Tekshiruv obyekt `ПередЗаписью`da (БСП `ДатыЗапретаИзменения` umumiy moduli, obunalar orqali) ishlaydi.
- Taqiq sanasidan **oldin yoki teng** sanali hujjatni yozish/o'tkazish/o'chirish → xato, matn taxminan: «**Нельзя изменять данные (документ ...) за период до ...** / Дата запрета изменения: ...» ***(aniq matn — taxmin)***. COM'da bu `ОбработкаПроведения`/`ПередЗаписью`da `Отказ = Истина` + xabar → `com_error` "Не удалось записать" + xabar navbatida asl matn (1.8).
- **Alohida "загрузка" sanasi**: БСП'da almashuv tugunlari uchun **«Дата запрета загрузки»** ham bor — `ОбменДанными.Загрузка` rejimida yozilganda ishlatiladi ***taxmin***. Biz Загрузка ishlatmaymiz, shuning uchun oddiy taqiq sanasi amal qiladi.
- Agent foydalanuvchisi (`erp_agent`) uchun alohida taqiq sanasi qo'yish mumkin — masalan buxgalter oyni yopgach, ERP o'sha oyga yoza olmasligi uchun. **Tavsiya**: agent yozishdan oldin taqiq sanasini **o'qiydi** (so'rov `РегистрСведений.ДатыЗапретаИзменения`, ***struktura taxmin***) va yopiq kunga yozishni umuman urinmaydi, ERP'da "1C'da davr yopilgan — buxgalterga murojaat" holatini ko'rsatadi.

### 6.2. O'tgan davrga yozish (kechikkan sinxronizatsiya)

Internet/kompyuter o'chiq bo'lib, 3 kunlik savdo bir yo'la yuborilsa:
- **Sanalar tartibida** yozish (eng eskisidan) — qoldiqlar to'g'ri hisoblansin.
- **БП 3.0**: tannarx va moliyaviy natija **oyni yopish** (`Закрытие месяца`) bilan hisoblanadi. Agar o'sha oy allaqachon yopilgan bo'lsa, o'tgan sanali yangi hujjat → yopilish **eskiradi**; БП 3.0'da «Закрытие месяца» ekranida "требуется перезакрытие" / operatsiyalar "неактуальна" holatiga o'tadi ***taxmin — RU БП 3.0 xatti-harakati***, buxgalter oyni **qayta yopishi** kerak (Sonar `month.close` — `Обработки.ЗакрытиеМесяца.ЗакрытьМесяцПоЗагруженнымДанным`, 04 §5).
- **«Восстановление последовательности»**: bu — **БП 2.0** (va eski УПП/УТ 10) mexanizmi (`Последовательность.ВосстановитьПоследовательность`, FIFO partiyalari uchun). **БП 3.0, УТ 11, Розница 2/3, УНФ**'da hujjatlar ketma-ketligini tiklash o'rniga tannarx oy yopilishida hisoblanadi (УТ 11 — `Расчет себестоимости`). ***Taxmin***: Uzbek БП 3.0 RU БП 3.0'ga yaqin bo'lsa — ketma-ketlik yo'q; agar u eski БП 2.0 asosida bo'lsa (`Бухгалтерия для Узбекистана, ред. 2.0`) — **partiyalar ketma-ketligi** bor va o'tgan sanaga har bir yozuvdan keyin buxgalter «Восстановление последовательности»ni (yoki «Групповое перепроведение»ni) bajarishi kerak bo'ladi. **Buni pilot bazada aniqlash shart.**
- **«Перепроведение»** (`Групповое перепроведение документов`): o'tgan davrga kech kelgan hujjat keyingi hujjatlarning qoldiq/partiya natijasini o'zgartirsa, ular qayta o'tkazilishi kerak. Biz buni **avtomatik qilmaymiz** — faqat ERP'da "N kunlik kechikkan sinxronizatsiya — 1C'da oyni qayta yopish/qayta o'tkazish talab qilinishi mumkin" ogohlantirishi va (keyinroq) Sonar uslubidagi tasdiqlanadigan "oyni yopish" amali.

### 6.3. Mavjud hujjatni qayta yozish (tuzatish)

- O'tkazilgan hujjatni o'zgartirish → `Записать(Проведение)` qayta chaqiriladi; eski harakatlar o'chiriladi va yangi yoziladi (bitta tranzaksiyada) — alohida `ОтменаПроведения` shart emas (Sonar ham shunday, 04 §2.9).
- Buxgalter hujjatni qo'lda tuzatgan bo'lsa (`ВерсияДанных` biz saqlaganidan boshqacha) — **ustidan yozmaymiz**, `changed` holati, tasdiqlash so'raladi.

---

## 7. Litsenziyalar

### 7.1. Rasmiy (huquqiy) qoida — tasdiqlangan

1C litsenziyalash FAQ (https://v8.1c.ru/priobretenie-i-vnedrenie/otvety-na-tipovye-voprosy-po-litsenzirovaniyu-1s-predpriyatiya-8/, IX bo'lim):
- **IX.1-57 (COM-ulanish orqali kirish)**: «Использование программных или аппаратных средств, уменьшающих количество пользователей, которые имеют непосредственный доступ к «1С:Предприятию 8», не уменьшает количества требуемых лицензий.»
- **IX.3-59**: «Каждое рабочее место, с которого тем или иным способом осуществляется доступ к данным информационной базы «1С:Предприятия 8», должно быть обеспечено отдельной клиентской лицензией.»

Bizning holatda: ERP agenti **avtomatik integratsiya**, uning orqasida 1C'da ishlaydigan qo'shimcha "foydalanuvchilar" yo'q (kassirlar 1C'ga emas, ERP POS'ga kiradi). Huquqiy jihatdan agent — **bitta ish o'rni** deb qaralishi ***taxmin*** — lekin kassirlar ERP orqali 1C ma'lumotlariga "bilvosita" kirmaydi (biz faqat kun yakunida yozamiz) — buni 1C hamkori/litsenziya bo'yicha rasmiy javob bilan tasdiqlash kerak (do'konlarning ko'pchiligida baribir buxgalter uchun 1 ta litsenziya bor).

### 7.2. Texnik xatti-harakat — ***taxmin*** (ITS «Руководство администратора → Лицензирование» bilan tekshirilsin)

- **COM tashqi ulanish = seans turi «COM-соединение» → mijoz litsenziyasini egallaydi** (fayl va mijoz-server rejimida). Konfigurator va fon vazifalari egallamaydi.
- **Fayl rejimi**: litsenziya COM ishlayotgan kompyuterdan (USB kalit yoki dasturiy litsenziya) olinadi; **bir kompyuterdagi bir nechta seans bitta litsenziyani bo'lishadi** (oddiy mijozlar kabi). Ya'ni agent **buxgalterning o'z kompyuterida** ishlasa — qo'shimcha litsenziya kerak bo'lmasligi mumkin; boshqa kompyuterda — +1 litsenziya.
- **Mijoz-server rejimi**: server litsenziyasi (ПРОФ/КОРП) shart; mijoz litsenziyasi lokal yoki server pulidan ("Выдавать клиентские лицензии сервером"). Bir mashinadan bir nechta COM seansi bitta litsenziyami yoki har biri alohida — aniqlanmagan.
- **Bazaviy versiya** (`Базовая`) — **tashqi ulanish/COM'ni umuman qo'llab-quvvatlamaydi** **[tasdiqlandi — v8.1c.ru «Базовая версия»: «не поддерживается COM-соединение и Automation-сервер»; online-ufa.ru]** → mahsulot uchun muhim cheklov: kichik do'konlarning bir qismi "Базовая" versiyada ishlaydi — ular bilan COM integratsiyasi mumkin emas (faqat fayl almashuvi/qo'lda yuklash).
- **ПРОФ vs КОРП** **[tasdiqlangan — https://v8.1c.ru/static/rasshirennaya-funktsionalnost-urovnya-korp/]**: ПРОФ — max 500 bir vaqtdagi seans va 12 protsessor yadrosi; COM'ga xos ПРОФ cheklovi topilmadi. Do'konlar uchun ahamiyatsiz.

### 7.3. Amaliy oqibatlar

1. Agent seansni **qisqa** ushlaydi: ulanadi → yozadi → uziladi (litsenziya tez bo'shaydi; buxgalter 1C'ga kira olmay qolmasin). Litsenziya yetmasa xato matni `"Не обнаружена свободная лицензия"` / `"лиценз"` → `license` kodi, 10–15 daqiqadan keyin qayta urinish va ERP'da ogohlantirish ***(matn taxmin)***.
2. Kun yakuni oynasi — buxgalter ishlamaydigan vaqt (masalan 23:30 yoki ertalab 07:00), shunda litsenziya raqobati bo'lmaydi.
3. Onboarding tekshiruvida: 1C versiyasi `Базовая`mi (COM ishlamaydi), fayl/server, bo'sh litsenziya bormi — agent `probe` + sinov ulanish bilan aniqlaydi.

---

## 8. Tavsiya etilgan arxitektura: COM + tashqi qayta ishlash (.epf)

Konfiguratsiyani o'zgartirmasdan 1C ichida kod bajarishning standart yo'li:

```python
proc = conn.ВнешниеОбработки.Создать(r"C:\ProgramData\ERPAgent\erp_writer.epf", False)  # 2-param: БезопасныйРежим
result_json = proc.ЗаписатьОРП(payload_json)    # .epf modulidagi Экспорт funksiya
```

`.epf` ichida (1C tili):

```
Функция ЗаписатьОРП(ТекстJSON) Экспорт
    Чтение = Новый ЧтениеJSON; Чтение.УстановитьСтроку(ТекстJSON);
    Д = ПрочитатьJSON(Чтение, Ложь);
    Ссылка = Документы.ОтчетОРозничныхПродажах.ПолучитьСсылку(Новый УникальныйИдентификатор(Д.guid));
    Если Ссылка.ПолучитьОбъект() <> Неопределено Тогда   // yoki БСП: ОбщегоНазначения.СсылкаСуществует(Ссылка)
        Возврат СформироватьОтвет("already_exists", Ссылка);
    КонецЕсли;
    Об = Документы.ОтчетОРозничныхПродажах.СоздатьДокумент();
    Об.УстановитьСсылкуНового(Ссылка);
    Об.Заполнить(Неопределено);
    // ... qatorlar; konfiguratsiyaning o'z protseduralari:
    // ОбработкаТабличнойЧастиСервер.ОбработатьТЧ(...) (УТ/Розница) yoki БП analoglari — server kontekstida mavjud
    Попытка
        Об.Записать(РежимЗаписиДокумента.Проведение, РежимПроведенияДокумента.Неоперативный);
    Исключение
        Возврат СформироватьОшибку(ПодробноеПредставлениеОшибки(ИнформацияОбОшибке()),
                                   ПолучитьСообщенияПользователю(Истина));
    КонецПопытки;
    Возврат СформироватьОтвет("created", Об.Ссылка);
КонецФункции
```

Afzalliklari: COM chaqiruvlari ~5 ta (1000 qatorga ham); konfiguratsiyaning **barcha** server umumiy modullari mavjud (`ВнешнееСоединение` belgisi shart emas — .epf obyekt moduli tashqi ulanish kontekstida bajariladi ***taxmin — tekshirilsin***); xato matni to'liq (`ПодробноеПредставлениеОшибки`); har konfiguratsiya (БП/УТ/Розница/УНФ/Uzbek БП) uchun **alohida .epf** — Python qismi o'zgarmaydi.

Shartlar / tuzoqlar (***taxmin, tekshirilsin***):
- Foydalanuvchida «Использование внешних обработок»/«Интерактивное открытие внешних отчетов и обработок» kabi huquq — dasturiy `Создать` uchun admin rol yoki maxsus rol kerak bo'lishi mumkin.
- 8.3.9+ «**Защита от опасных действий**» — foydalanuvchi sozlamasida yoqilgan bo'lsa, tashqi faylni ochish ogohlantirish/taqiq beradi; agent foydalanuvchisi uchun o'chirilishi kerak.
- `БезопасныйРежим = Истина` bo'lsa, .epf ichida `ПривилегированныйРежим`, fayl, COM va boshqalar taqiqlanadi; DB yozish odatda mumkin. Bizga privilegiya shart emas → **xavfsiz rejimda ishlatish** afzal ***taxmin***.
- Server bazasida .epf faylini 1C server ko'rishi kerak emas — `Создать` faylni mijoz (COM jarayoni) tomonidan o'qib, serverga uzatadi ***taxmin***; muqobil — `ПоместитьВоВременноеХранилище(Новый ДвоичныеДанные(path))` + `ВнешниеОбработки.Подключить(adres)`.
- Kod imzosi/versiyasi: .epf'ni agent bilan birga tarqatamiz, SHA-256 bilan tekshiramiz.

---

## 9. Manbalar

**Tasdiqlangan (ochildi/o'qildi):**
- ITS standarti №773 «Использование признака ОбменДанными.Загрузка в обработчиках событий объекта»: https://its.1c.ru/db/v8std/content/773/hdoc (matn: https://its.1c.ru/db/content/v8std/src/200/400/i8100773.htm)
- 1C litsenziyalash FAQ, IX bo'lim: https://v8.1c.ru/priobretenie-i-vnedrenie/otvety-na-tipovye-voprosy-po-litsenzirovaniyu-1s-predpriyatiya-8/
- КОРП darajasi funksiyalari (ПРОФ cheklovlari): https://v8.1c.ru/static/rasshirennaya-funktsionalnost-urovnya-korp/
- EnterpriseData XSD (1.0.1) va namuna xabar: https://github.com/MaxiStyle/1c-enterprise-data
- 1C O'zbekiston mahsulotlari: https://1c.uz/v8/generic_products/index.php
- Sonar AI dekompilyatsiyasi tahlili: `research_notes/sonar-1c-integratsiya/02-1c-dan-malumot-oqish.md`, `04-1c-ga-yozish-va-tasdiqlash.md` (COM late-binding, `ComHandle.Write`, `ВерсияДанных`, `"Sonar #id"` marker, `ErrorMap`, worker jarayon modeli)

**Tekshirilishi kerak (ochilmadi — ITS login talab qiladi yoki qidiruv limiti tugadi):**
- Sintaksis yordamchisi: `УстановитьСсылкуНового`, `ПолучитьСсылку`, `ПолучитьОбъект`, `РежимПроведенияДокумента`, `ПолучитьСообщенияПользователю`, `ВнешниеОбработки.Создать` — https://its.1c.ru/db/v8323doc (yoki Конфигуратор → Синтакс-помощник)
- «Руководство администратора → Лицензирование» (seans turlari va litsenziya olish): https://its.1c.ru/db/v8323doc
- БСП «Даты запрета изменения» hujjati: https://its.1c.ru/db/bspdoc
- pywin32 COM: https://github.com/mhammond/pywin32 (`win32com.client.Dispatch`, `pythoncom.CoInitialize`)

---

## 10. Pilot bazada tekshirish ro'yxati (birinchi hafta)

1. Uzbek БП 3.0'da `ОтчетОРозничныхПродажах` metadata'si: rekvizitlar, ТЧ nomlari (`Товары`, `Оплата`?), `СтавкаНДС` turi, schyotlar ustunlari, `ОперативноеПроведение`.
2. COM orqali yaratilgan ОРП'ning provodkalari qo'lda kiritilgan ОРП bilan **bir xilmi** (schyotlar, НДС, tannarx).
3. `УстановитьСсылкуНового` + qayta yuborish → dublikat yo'qligi; `ПолучитьОбъект()` → `Неопределено`.
4. Yopiq davrga yozish xatosi matni; litsenziya yetmaganda xato matni; buxgalter hujjatni ochib turganda xato matni.
5. `.epf` ni `ВнешниеОбработки.Создать(path, Истина)` bilan agent foydalanuvchisidan yuklash (huquqlar, «Защита от опасных действий»).
6. Konfiguratsiya qaysi asosda — БП 3.0 tipidagi (oy yopilishi) yoki БП 2.0 tipidagi (`Восстановление последовательности`).
7. 1000 qatorli ОРП: COM-to'g'ridan vs `.epf` vaqtini o'lchash.
