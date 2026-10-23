# P5 — 1C platforma xulqi (COM tashqi ulanish) va БП UZ 3.0 bo'yicha oldindan desk-research (OQ-048, 051 + 049, 050, 052)

**Maqsad:** `00-inventar.md` §6/§12 dagi P5 partiyasi. R-bandlar OQ-048 va OQ-051 ni manba bilan yopish. E-bandlar OQ-049, 050 va 052 bo'yicha pilotdan oldin ochiq manbalardan olinadigan hamma narsani yig'ish. Shunda real bazadagi sinov (`1c-integratsiya/00-xulosa.md` §10) faqat tasdiqlaydi, kashf qilmaydi.
**Kim uchun:** `33-1c-integratsiya.md` / `34-1c-agent.md` muallifi, agent (C#) dasturchisi, pilot sinovchisi, asoschi (litsenziya bandi).
**Bog'liq fayllar:** `research_notes/1c-integratsiya/00-xulosa.md` (§10 testlar, §14 V-jadval), `01`–`06`; `spec/kod-uchun/01-qarorlar.md` #36–#41.
**Holat:** desk-research, 2026-10-16. Spec fayllari **o'zgartirilmadi**. Hech narsa publish qilinmadi. `1c-ut11` MCP ishlatilmadi. WebSearch limiti tugagani uchun qidiruv Playwright (Google) va to'g'ridan-to'g'ri `curl` bilan qilindi.

**Asosiy cheklov — #36 ga muvofiq:** quyidagi barcha xulosalar faqat **COM tashqi ulanish** (`V83.COMConnector`, in-proc, Windows agenti) uchun. OData, HTTP-servis va publish ko'rib chiqilmadi.

---

## 0. Eng muhim topilmalar

1. **`УстановитьСсылкуНового` + `ПолучитьСсылку(GUID)` COM tashqi ulanishida ishlaydi — bu endi taxmin emas.** Sintaksis yordamchisida ikkala metod uchun ham `Доступность: Сервер, толстый клиент, внешнее соединение…` deb yozilgan. Infostart'da **УТ 11.4 → БП 3.0 ga COM orqali** aynan shu usul bilan ishlab turgan kod e'lon qilingan. **Tuzoq:** `УникальныйИдентификатор` **ulangan baza tomonida** yaratilishi shart: `conn.NewObject("УникальныйИдентификатор", "<guid>")`. Chaqiruvchi tomondagi qiymat yoki satr berilsa — `Несоответствие типов` xatosi.
2. **Platforma o'zi dublikatga yo'l qo'ymaydi:** «Значение не может равняться ссылке какого-либо из имеющихся в базе данных объекта данного типа. Уникальность ссылки проверяется при записи объекта». Demak, GUID bo'yicha qidiruv adashsa ham, ikkinchi `Записать()` dublikat yaratmaydi — **xato beradi**. Bu bizning idempotentlikka platforma darajasidagi qo'shimcha kafolat.
3. **Litsenziya — texnik javob topildi** (ИТС Руководство администратора, 10.2.5.7, 1C hamkori forumda iqtibos keltirgan). COM ulanish litsenziyani avval **mahalliy klient litsenziyalaridan** qidiradi. Bir foydalanuvchilik klient litsenziyasi «**позволяют запускать произвольное количество клиентских приложений на одном компьютере**». Demak, odatiy do'konda (fayl baza, mahalliy pin-kod yoki USB HASP, 1C va agent bitta Windows foydalanuvchisida) agent **qo'shimcha litsenziya olmaydi**. Istisnolar: litsenziyani 1C serveri tarqatsa («один сеанс – одна лицензия»), RDP bilan bir foydalanuvchilik HASP, veb-server orqali ochilgan baza. Huquqiy tomon (IX.1-57: «не меньше числа пользователей, в действительности одновременно работающих») hamon hamkor talqinini talab qiladi.
4. **БП UZ 3.0 reliz eslatmalari ommaviy — 99 ta versiya (3.0.3.2 … 3.0.64.8) yuklab olindi** (`dl05.1c.ru/content/AccountingUz/<ver>/news.htm`). Ulardan aniq topilgani:
   - ОРП'da «**Безналичные оплаты**» jadval qismi va unda «**Вид оплаты**» maydoni bor;
   - «**Касса**» rekviziti faqat «По кассам» bayrog'i yoqilganda chiqadi;
   - «**Не формировать проводки по кассе**» bayrog'i bor (3.0.64.1);
   - alohida «**Отчет о розничных продажах (Серийный учет)**» hujjati bor;
   - ИКПУ — Номенклатура'ning «ЭДО» bo'limida, «**Упаковка (ЭДО)**» bilan;
   - QQS imtiyozlari 3.0.63 dan boshlab Номенклатура'da emas, «**Льготы по НДС**» registrida;
   - «Виды оплат» ma'lumotnomasi kontragent, shartnoma va **komissiya foizi** bilan;
   - oy yopish — «**Закрытие месяца**» + «**Перепроведение документов за месяц**» (ketma-ketlik chegarasi bilan).
5. **ОРП qaytarishlari uchun ruscha БП 3.0 da alohida jadval qismi `Возвраты` bor** (`ДатаРеализации` maydoni bilan). Platforma qaytarishni sotuvga solishtirib tekshiradi: «было реализовано … на 1 ед. меньше, чем возвращается». Demak, «ОРП'da manfiy miqdorli qator» (test 7) yo'li ehtimoldan yiroq. To'g'ri yo'l — `Возвраты` jadval qismi (UZ'da bormi — `meta_sync` tekshiradi) yoki `Возврат товаров от покупателя` (UZ'da «Продажа через онлайн-ККМ» bayrog'i bilan).
6. **Qoldiq nazorati sozlamasi tasdiqlandi:** БП 3.0: Администрирование → Проведение документов → «**Разрешить списание запасов при отсутствии остатков по данным учета**». Bayroq o'chiq bo'lsa, qoldiq yetmagan hujjat o'tkazilmaydi. Bayroq yoqilgan bo'lsa, o'tkaziladi, lekin «Проводка будет сформирована только в количественном выражении без суммы». Bu bizning `sales_only` rejim va tannarx solishtiruvi uchun muhim.
7. **Agentni admin huquqisiz o'rnatish (#38) uchun yangi xavf:** `comcntr.dll` kerakli bitlik uchun ro'yxatdan o'tmagan bo'lsa — «Недопустимая строка с указанием класса» (0x800401F3). `regsvr32` admin huquqini talab qiladi (HKLM). Onboarding preflight'i buni aniqlashi va bir martalik admin qadamini taklif qilishi kerak.

---

## 1. Holat jadvali

| OQ | Mavzu | Klass | Holat | Qolgan ish (pilot testi, `1c §10`) |
|---|---|---|---|---|
| **OQ-048** | GUID berish COM orqali (`ПолучитьСсылку`/`УстановитьСсылкуНового`/`ПолучитьОбъект`) | R | **YOPILDI** (desk) | Testlar 1, 2, 20 faqat tasdiqlaydi: BP UZ'ning `ПередЗаписью` handlerlari `Ссылка`ni almashtirmasligi |
| **OQ-051** | Platforma xatolari va holatlari | R | **QISMAN** | Mexanizmlar va platforma matnlari topildi. BP UZ'ning aniq matnlari (qoldiq yetmasligi, taqiq sanasi) va monopol rejim matni → testlar 10, 11, 15, 16, 17 da regex sifatida yoziladi |
| **OQ-052** | Litsenziya: agent alohida ish o'rnimi | E | **QISMAN** (texnik javob bor, huquqiy talqin yo'q) | Test 14 + hamkorning yozma javobi (IX.1-57 talqini) |
| **OQ-049** | БП UZ 3.0.64 metadata nomlari | E | **QISMAN** (sinonimlar va tuzilma rasmiy reliz eslatmalaridan; identifikatorlar ruscha БП 3.0 dan xulosa) | Testlar 3, 4, 8, 9 — `meta_sync` dump |
| **OQ-050** | ОРП o'tkazish xulqi, schyot to'ldirish, qaytarish, yaxlitlash, oy yopish turi | E | **QISMAN** (oy yopish turi va qoldiq sozlamasi aniqlandi) | Testlar 5, 6, 7, 12 + buxgalter «oltin namuna» |

---

## 2. Manbalar

**Birlamchi (1C rasmiy):**
- [S1] `dl05.1c.ru/content/AccountingUz/<versiya>/news.htm` — «Бухгалтерия для Узбекистана, редакция 3.0» reliz eslatmalari. 99 ta versiya ochiq yuklab olindi: 3.0.3.2 … 3.0.64.8. Iqtiboslarda versiya ko'rsatilgan. Masalan: https://dl05.1c.ru/content/AccountingUz/3_0_64_8/news.htm, https://dl05.1c.ru/content/AccountingUz/3_0_58_8/news.htm
- [S2] v8.1c.ru — «Ответы на типовые вопросы по лицензированию 1С:Предприятия 8», IX.1-57: https://v8.1c.ru/priobretenie-i-vnedrenie/otvety-na-tipovye-voprosy-po-litsenzirovaniyu-1s-predpriyatiya-8/
- [S3] ИТС, Руководство администратора 8.3, glava «Защита от несанкционированного использования». Kontent login bilan; matn Google snippet va hamkor iqtibosi orqali olindi: https://its.1c.ru/db/v837doc/bookmark/adm/TI000000261 , 8.5.4: https://its.1c.ru/db/v854doc/bookmark/adm/TI000000261
- [S4] ИТС «Отвечает специалист 1С»: «Как в 1С:Бухгалтерии 8 отключить контроль отрицательных остатков при списании МПЗ» (27.09.2024): https://its.1c.ru/db/answers1c/content/225/hdoc
- [S5] its.1c.eu — «1С:Бухгалтерия для Узбекистана. Редакция 3.0. Руководство по ведению учета». Mundarija ochiq, matn login bilan (401). Google snippetlari: 6.3 «Продажи», 6.3.8 «Розничная торговля», «Дата запрета изменения данных»: https://its.1c.eu/uz/db/buhuz30/content/104/hdoc

**Sintaksis yordamchisi (forumlarda to'liq iqtibos qilingan):**
- [S6] infostart topic307507 — `УстановитьСсылкуНового` va `ПолучитьСсылку` sintaksis yordamchisi matni, «Доступность»: https://forum.infostart.ru/forum9/topic307507/
- [S7] cyberforum thread1175552, mista (bir nechta mavzu) — xuddi shu «Доступность: … внешнее соединение» matni (Google snippet).

**Amaliy dalil (COM kodi):**
- [S8] infostart 1089773 «Перенос кассовых документов из УТ 11.4 в БП 3.0 через СОМ-соединение. Механизм переноса GUID документа» (14.07.2019): https://infostart.ru/1c/tools/1089773/
- [S9] infostart topic255986 «Обмен через COM Соединение» (05.02.2021): https://forum.infostart.ru/forum9/topic255986/
- [S10] infostart topic52697 «Как через COM-соединение работать с ГУИД?» (2012): https://forum.infostart.ru/forum9/topic52697/
- [S11] mista topic 851846 — «ДокументСсылка.ПолучитьОбъект(), согласно документации может вернуть НЕОПРЕДЕЛЕНО»: https://forum.mista.ru/topic/851846
- [S12] infostart topic199649 — ruscha БП 3.0 (3.0.64.54) da ОРП'ni dasturiy yaratish: `Товары`, `Оплата`, `Возвраты`, xatolar: https://forum.infostart.ru/forum9/topic199649/
- [S13] infostart topic328655 — `ОбъектДок.Оплата`, `ВидОплаты = Справочники.ВидыОплатОрганизаций…`, `СуммаОплаты` (2025): https://forum.infostart.ru/forum9/topic328655/

**Litsenziya amaliyoti:**
- [S14] infostart topic287820 «Проблемы с лицензированием» (2022). Unda Online-Ufa (1C franchayzi) ИТС 10.2.5.7 ni iqtibos qiladi va bir foydalanuvchilik kalit bo'yicha izoh beradi: https://forum.infostart.ru/forum86/topic287820/
- [S15] online-ufa.ru «Как лучше активировать клиентскую лицензию 1С» — 256 jarayon / 256 OS sessiyasi: https://www.online-ufa.ru/content/articles/license-1c-on-server-or-client/
- [S16] klerk.ru «Взаимодействие между базами 1С через COM» — «с оговорками является внешнее соединение»: https://www.klerk.ru/soft/articles/430201/
- [S17] infostart topic258045 «COM соединение и 1С лицензии» (qarama-qarshi holat): https://forum.infostart.ru/forum28/topic258045/

**Xato matnlari va boshqa:**
- [S18] infostart topic148517 — Connect: «Начало сеанса с информационной базой запрещено», `UC=` parametri: https://forum.infostart.ru/forum9/topic148517/
- [S19] infostart topic100706, helpf.pro, efsol.ru — «Класс не зарегистрирован» / «Недопустимая строка с указанием класса», `regsvr32 comcntr.dll` (Google snippetlari).
- [S20] otr-soft.ru — «Редактирование данных этого периода запрещено. Изменения не могут быть записаны»: https://otr-soft.ru/faq-common/oshibki-1s/izmeneniya-ne-mogut-byt-zapisany/
- [S21] fastcode.im — BSP `ДатыЗапретаИзменения.НайденЗапретИзмененияДанных`: https://fastcode.im/Templates/BspDetails/obshhijmodul-datyzapretaizmeneniya-najdenzapretizmeneniyadannyx/najden-zapret-izmeneniya-dannyx
- [S22] wiseadvice-it.ru, buhexpert8.ru, infostart 2362653, voly.codes — БП 3.0 qoldiq nazorati: https://wiseadvice-it.ru/o-kompanii/blog/articles/kontrol-otricatelnyh-ostatkov-v-1s-8-3-buhgalteriya/ , https://infostart.ru/1c/articles/2362653/ , https://voly.codes/stati/kontrol-otricatelnyh-ostatkov-1s/
- [S23] its.1c.ru (edtdoc) — tashqi ulanish ta'rifi: fayl bazada kod COMConnector yaratilgan kompyuterda bajariladi. Manba S14 da iqtibos qilingan: https://its.1c.ru/db/edtdoc/content/10397/hdoc@118bd7fe

---

## 3. Har OQ bo'yicha

### OQ-048 — GUID'ni COM orqali berish

**Savol:** COM orqali `ПолучитьСсылку(Новый УникальныйИдентификатор(...))` ishlaydimi? Yo'q obyektda `ПолучитьОбъект()` → `Неопределено` bo'ladimi? `УстановитьСсылкуНового` + `Записать` shu GUID'ni beradimi? Handlerlar `Ссылка`ni o'zgartirmaydimi? Uzilishdan keyin qayta yozishda dublikat bo'lmaydimi?

**Javob:**
1. **Metodlar tashqi ulanishda mavjud.** `ПолучитьСсылку(<УникальныйИдентификатор>)` — «Формирует ссылку из значения типа УникальныйИдентификатор…». `УстановитьСсылкуНового(<Ссылка>)` — «Устанавливает значение для нового (созданного и еще не записанного) объекта, которое будет назначено при записи в качестве ссылки». Ikkalasida ham «Доступность: Сервер, толстый клиент, **внешнее соединение**…» [S6][S7].
2. **COM'da ishlaydigan kod (ishlab chiqarishda ishlatilgan, УТ 11.4 → БП 3.0) [S8]:**
   ```
   СсылкаНового = СОМ.Документы.ПриходныйКассовыйОрдер.ПолучитьСсылку(
                      СОМ.NewObject("УникальныйИдентификатор", СтрокаGUID));
   Об = СОМ.Документы.ПриходныйКассовыйОрдер.СоздатьДокумент();
   Об.УстановитьСсылкуНового(СсылкаНового);
   ```
   Xuddi shu naqsh `РеализацияТоваровУслуг` uchun [S9] da ham bor («Лучший ответ»). Agent (C#) uchun xulosa: GUID satri **ulanish obyektining `NewObject`** metodi orqali `УникальныйИдентификатор`ga aylantiriladi. Satr yoki chaqiruvchi tomondagi obyekt berilsa — «Несоответствие типов (параметр номер '1')» [S9][S10].
3. **Mavjudligini tekshirish:**
   - `ПолучитьСсылку(GUID)` har doim «ссылка»ni qaytaradi, hatto obyekt yo'q bo'lsa ham. Bunday ssylkaning ko'rinishi «<Объект не найден> (…)» bo'ladi [S6, 16- va 22-postlar].
   - `ДокументСсылка.ПолучитьОбъект()` yo'q obyekt uchun `Неопределено` qaytaradi va istisno chiqarmaydi: «согласно документации может вернуть НЕОПРЕДЕЛЕНО, и так проверяют битые ссылки» [S11].
   - Muqobil (S8 muallifi ishlatgan): `СОМ.String(Ссылка)` ichida «Объект не найден» qidirish. Biz `ПолучитьОбъект() = Неопределено` ni asosiy, satr tekshiruvini esa faqat diagnostika sifatida ishlatamiz (lokalizatsiyaga bog'liq).
4. **Dublikat platforma darajasida taqiqlangan:** «Значение не может равняться ссылке какого-либо из имеющихся в базе данных объекта данного типа. Уникальность ссылки проверяется при записи объекта» [S6]. Demak, «noma'lum natija»dan keyin agent avval tekshirmasdan qayta yozsa ham, ikkinchi yozuv dublikat emas, **xato** beradi. Bu xato `ONEC_DUPLICATE_REF` deb tasniflanadi va «GUID bo'yicha o'qib, yangilash» yo'liga o'tiladi.
5. **Atomarlik (test 20):** `Записать(РежимЗаписиДокумента.Проведение)` yozuvni va harakatlarni bitta tranzaksiyada bajaradi (platformaning standart xulqi). Worker o'ldirilsa, hujjat yo yozilgan (shu GUID bilan), yo umuman yo'q. Keyingi urinishdagi «avval GUID bo'yicha tekshir» (`04` §5.3) dublikatni istisno qiladi. *Ishonch: yuqori, platforma xulqi; amaliy tasdiq — test 20.*
6. **Handlerlar `Ссылка`ni o'zgartirmasligi (test 2):**
   - Tipik БСП/ДО kodi `ПередЗаписью`da avval `ПолучитьСсылкуНового()`ni tekshiradi va ssylka **bo'sh bo'lsagina** o'z ssylkasini beradi: `Если Не ЗначениеЗаполнено(ПолучитьСсылкуНового()) Тогда УстановитьСсылкуНового(...)` [S6, 1-post].
   - Hech bir manbada БП 3.0 ning `ПередЗаписью` handleri tashqaridan berilgan ssylkani almashtirishi qayd etilmagan.
   - BP UZ uchun bu faqat pilotda tasdiqlanadi.
7. **`ОбменДанными.Загрузка` shart emas.** [S9] dagi foydalanuvchi uni yoqqan, lekin `УстановитьСсылкуНового` usuli usiz ham ishlaydi [S8]. Bu `00-xulosa` §6 bilan mos («Загрузка ishlatilmaydi»).

**UUIDv5 haqida:** 1C `УникальныйИдентификатор` har qanday 36 belgili hex GUID satrini qabul qiladi. Versiya bitlari tekshirilmaydi (S8 manba bazaning GUID'ini aynan ko'chiradi). Unikallik **har obyekt turi ichida** tekshiriladi. Bizning `{kind}:` prefiksli UUIDv5 sxemamiz bunga mos.

**Dalil:** S6, S7, S8, S9, S10, S11.
**Ishonch:** **yuqori** (1–4, 7); **o'rta-yuqori** (5); **o'rta** (6 — BP UZ handlerlari ko'rilmagan).

**Spec'ga ta'sir (taklif):**
- `34-1c-agent.md`: GUID → `conn.NewObject("УникальныйИдентификатор", s)` (chaqiruvchi tomondagi obyekt emas); mavjudlik `Manager.ПолучитьСсылку(uid).ПолучитьОбъект() == Неопределено`. Yangi xato kodi `ONEC_DUPLICATE_REF` («Уникальность ссылки» buzilishi) → avtomatik «o'qish + yangilash» yo'li.
- `00-xulosa` §14 V8: «tasdiqlanmadi (taxmin)» → **«tasdiqlandi (desk)»**, manbalar S6/S8/S11.
- `01 #40` matniga tegilmaydi (qaror to'g'ri).

**Holat: YOPILDI.** Pilot testlari 1, 2, 20 Bosqich A qabul mezoni sifatida faqat **tasdiqlaydi**. Test 2 (BP UZ handlerlari) yagona qolgan noaniqlik. U salbiy chiqsa, zaxira — `Комментарий` markeri (`00-xulosa` §6).

---

### OQ-051 — Platforma xulqi va xato holatlari

**Javob — holat bo'yicha:**

| Holat | Mexanizm (tasdiqlangan) | Xato matni (manba) | Agent tasnifi / harakat |
|---|---|---|---|
| **Qoldiq yetmaydi** (test 10) | БП 3.0: Администрирование → Проведение документов → «Разрешить списание запасов при отсутствии остатков по данным учета». O'chiq — hujjat o'tkazilmaydi [S4][S22]. Tekshiruv **hujjat sanasidagi** qoldiq bo'yicha, orqa sana ham tekshiriladi [S22, voly.codes — ikkilamchi] | Aniq matn BP UZ'da topilmadi. Ruscha БП'da nomenklatura, ombor va yetishmagan miqdorli xabar [S22] | `ONEC_STOCK_SHORTAGE`. Matn `ПолучитьСообщенияПользователю()` dan olinadi (o'tkazish xabarlari istisno matniga kirmaydi) |
| **«Дата запрета изменения»** (test 11) | BP UZ'da bor (ИТС UZ qo'llanmasi «Дата запрета изменения данных» [S5]; reliz 3.0.50.1 «даты запрета изменения данных»). BSP mexanizmi: `ОбщийМодуль.ДатыЗапретаИзменения.НайденЗапретИзмененияДанных(...)`, `ШаблонДанныхДляПроверки` [S21] | «Редактирование данных этого периода запрещено. Изменения не могут быть записаны» (2.0 tipidagi xabar [S20]). 3.0 da BSP xabari foydalanuvchi va sana bilan; aniq matn — pilot | `ONEC_PERIOD_CLOSED`. **Preflight'da o'qish:** BSP funksiyasi bir COM chaqiruvida chaqiriladi (versiyaga bog'liq API) yoki `РегистрСведений.ДатыЗапретаИзменения` so'rovi (*taxmin — `meta_sync` tasdiqlaydi*) |
| **«Блокировка работы пользователей»** (test 16) | Connect paytida rad etiladi | «Ошибка при вызове метода контекста (Connect): Произошла исключительная ситуация (V83.COMConnector.1): **Начало сеанса с информационной базой запрещено.**» [S18]. Ruxsat kodi ulanish satrida `UC="<код>"` bilan beriladi [S18] | `ONEC_BASE_LOCKED` (qayta urinish + Telegram). `UC` ni ishlatmaymiz — bu buxgalter blokirovkasini chetlab o'tish bo'ladi |
| **Monopol rejim / Konfigurator DB konfiguratsiyasini yangilamoqda** (test 16) | Fayl bazada `1Cv8.1CD` monopol egallanadi | «Ошибка совместного доступа к файлу …» oilasi [S19 izlash natijalari]. Aniq COM matni topilmadi → pilot | `ONEC_BASE_EXCLUSIVE` (qayta urinish). Konfigurator oddiy ochiq turishi COM'ni bloklamaydi (*taxmin*) |
| **Hujjat formada ochiq va tahrirlanmoqda** (test 17) | Boshqariladigan forma tahrir boshlanganda obyektni pessimistik bloklaydi; boshqa sessiya `Записать` qilsa — blokirovka xatosi | «**Ошибка блокировки объекта. Объект уже заблокирован**…» (sessiya ma'lumoti bilan) [S19 izlash natijalari: buh.ru, forum-baza, 1cFresh video] | `ONEC_OBJECT_LOCKED` (keyinroq qayta urinish; preview'da «hujjat 1C'da ochiq» ogohlantirishi) |
| **Optimistik konflikt** (qo'lda o'zgartirilgan) | `ВерсияДанных` bizning `onec_object_refs` da saqlanadi. Platforma ham o'qish va yozish orasida boshqa sessiya yozsa xato beradi | «**Данные были изменены или удалены другим пользователем**» (8.3 platformasi yangi matni, downloads.v8.1c.ru reliz eslatmasi) | `ONEC_CONFLICT` (`00-xulosa` §6 — ustiga yozilmaydi) |
| **32/64-bit `V83.COMConnector`** (test 15) | In-proc: `comcntr.dll` bitligi jarayon bitligiga teng bo'lishi shart (`00-xulosa` V5). Har bitlik uchun alohida `regsvr32` | «**Класс не зарегистрирован**» / «**Недопустимая строка с указанием класса**» (HRESULT `0x800401F3`) [S19] | `ONEC_COM_NOT_REGISTERED`. Supervisor ikkinchi bitlikdagi worker'ni sinaydi; ikkalasi ham bo'lmasa — admin qadami (pastga qarang) |
| **Bir PK'da ikki platforma versiyasi** | ProgID `V83.COMConnector` oxirgi ro'yxatdan o'tkazilgan `comcntr.dll` ga ishora qiladi | — | Agent registrdan `CLSID → InprocServer32` yo'lini o'qib, versiyani logga yozadi (`00-xulosa` §8 «ProgID registrdan qidiriladi» bilan mos) |
| **Klient-server versiya nomuvofiqligi** | Klient-server bazada `comcntr.dll` versiyasi server versiyasiga teng bo'lishi shart | «Различаются версии клиента и сервера (…)» [S19 izlash natijalari: infostart topic205870, mista] | `ONEC_VERSION_MISMATCH` — matndan ikkala versiya ajratiladi, foydalanuvchiga «platforma X.Y.Z ni o'rnating» |
| **Tashqi ulanish huquqi yo'q** | Foydalanuvchida «Внешнее соединение» huquqi bo'lishi shart (`00-xulosa` §7) | Aniq matn — pilot (test 18) | `ONEC_NO_RIGHTS` |

**Muhim nozik jihatlar:**
- **Fayl bazada barcha kod agent PK'sida bajariladi** («В случае файловой базы код на встроенном языке исполняется на том компьютере, на котором создается объект V83.COMConnector (и в контексте клиента, и в контексте сервера)» [S23 S14 orqali]). Demak, ОРП o'tkazish tezligi (OQ-054) va xotira — do'kon PK'sining resursi.
- **O'tkazish xatolari ikki joyda keladi:** COM istisnosi (`ОписаниеОшибки`: «Ошибка при вызове метода контекста (Записать): Ошибка при выполнении обработчика - 'ОбработкаПроведения'…» [S12]) va foydalanuvchi xabarlari (masalan, «Документом … было реализовано … меньше, чем возвращается» [S12]). Agent `Записать`dan keyin **har doim** `ПолучитьСообщенияПользователю(Истина)` ni o'qib natijaga qo'shishi kerak.

**Dalil:** S4, S5, S12, S14, S18–S23 va S1 (3.0.50.1).
**Ishonch:** mexanizmlar **yuqori**; platforma xato matnlari **o'rta-yuqori** (forumlardagi real loglar); BP UZ konfiguratsiyasining matnlari **past** (pilot).

**Spec'ga ta'sir (taklif):**
- `17` (xato katalogi) / `33` §xato tasnifi: `ONEC_STOCK_SHORTAGE`, `ONEC_PERIOD_CLOSED`, `ONEC_BASE_LOCKED`, `ONEC_BASE_EXCLUSIVE`, `ONEC_OBJECT_LOCKED`, `ONEC_CONFLICT`, `ONEC_DUPLICATE_REF`, `ONEC_COM_NOT_REGISTERED`, `ONEC_VERSION_MISMATCH`, `ONEC_NO_RIGHTS`, `ONEC_LICENSE_UNAVAILABLE`. Tasnif **server profilidagi regex jadvali** bilan (kod emas, ma'lumot) — pilotda matnlar qo'shiladi.
- `34-1c-agent.md`: `Записать`dan keyin `ПолучитьСообщенияПользователю` majburiy. `UC=` parametri hech qachon ishlatilmaydi.
- **#38 ga xavf:** `comcntr.dll` ro'yxatdan o'tmagan PK'da admin huquqisiz o'rnatish yetmaydi. Taklif: onboarding preflight `ONEC_COM_NOT_REGISTERED` ni aniqlaydi va **bir martalik** «admin sifatida ro'yxatdan o'tkazish» (UAC, `regsvr32 "<bin>\comcntr.dll"`) tugmasini ko'rsatadi. Agentning o'zi baribir admin'siz ishlaydi. 1C o'rnatuvchisi odatda `comcntr.dll` ni o'zi ro'yxatdan o'tkazadi (*taxmin — pilot PK'larida tekshiriladi*).

**Holat: QISMAN.** Mexanizmlar va platforma xatolari yopildi. BP UZ'ga xos matnlar (qoldiq, taqiq sanasi, monopol rejim, huquq) → testlar 10, 11, 16, 17, 18 da yig'ilib, profil regex jadvaliga kiritiladi. Tasnifsiz xato `ONEC_UNKNOWN` bo'lib, xom matni bilan ko'rsatiladi — kodni bloklamaydi.

---

### OQ-052 — 1C litsenziyasi: agent alohida ish o'rni hisoblanadimi (oldindan desk-research)

**Texnik javob (rasmiy hujjat bo'yicha):**
1. **COM ulanish litsenziyani qaysi tartibda qidiradi** (ИТС Руководство администратора, 10.2.5.7, [S14] da so'zma-so'z):
   - 32-bit: «локальные клиентские лицензии; локальные серверные лицензии (как 32-разрядные, так и 64-разрядные); сетевые клиентские лицензии; клиентские лицензии на сервере «1С:Предприятия» (в клиент-серверном варианте) или веб-сервере (в случае файлового варианта, подключенного через веб-сервер)».
   - 64-bit: xuddi shunday, faqat «локальная серверная лицензия (только 64-разрядные)».
2. **Bir foydalanuvchilik klient litsenziyasi bitta kompyuterda istalgancha klient ilovaga yetadi.** «Программные лицензии бывают: ○ Однопользовательские клиентские. Позволяют запускать произвольное количество клиентских приложений на одном компьютере» [S3 snippet]. Litsenziya fayli bo'yicha: «Из одного сеанса операционной системы к одному файлу программной лицензии могут получить одновременный доступ не более 256 процессов; На одном компьютере доступ к одному файлу программной лицензии можно получить не более чем из 256 сеансов операционной системы» [S15].
3. **Hamkorning amaliy izohi** (Online-Ufa, 1C franchayzi): «Однопользовательский ключ при локальном запуске дает запустить на рабочем месте несколько сеансов (**в том числе и COMConnector**), но если лицензия с этого ключа была выдана сервером 1С, то локальные сеансы уже запустить будет невозможно (в том числе и COMConnector)» [S14].
4. **«С оговорками»** [S16] — bu shu istisno. Litsenziyani 1C serveri tarqatsa, «каждое клиентское приложение и внешнее соединение может захватывать свою собственную лицензию» [S16]. ИТС: «В этом случае лицензии расходуются из расчета «один сеанс – одна лицензия»» [S3 snippet].
5. **Qarama-qarshi holat** [S17]: fayl УТ PK'da turibdi, ikki boshqa PK veb-server orqali ulanadi, ТСД dasturi COM orqali kiradi → «нужна дополнительная клиентская лицензия». Bu «veb-server orqali ochilgan fayl baza» va «litsenziyani server tarqatadi» istisnosiga to'g'ri keladi.

**Xulosa — bizning odatiy do'kon uchun:**

| Muhit | Agent alohida litsenziya oladimi | Ishonch |
|---|---|---|
| Fayl baza, PK'da mahalliy bir foydalanuvchilik pin-kod yoki USB HASP, 1C va agent **bitta Windows foydalanuvchisida** | **Yo'q** — mahalliy klient litsenziyasini bo'lishadi | o'rta-yuqori (ИТС + hamkor; test 14 tasdiqlaydi) |
| Xuddi shunday, lekin agent **boshqa Windows foydalanuvchisida** | Texnik jihatdan yo'q (256 OS sessiyasigacha), **agar** litsenziya fayli `ProgramData` da va ikkala foydalanuvchiga ochiq bo'lsa. Foydalanuvchi profilida bo'lsa — topolmaydi [S14, 112-post] | o'rta |
| Litsenziyani 1C serveri tarqatadi (klient-server, «Выдача лицензий сервером»), RDP + bir foydalanuvchilik HASP | **Ha**, sessiyaga bitta | yuqori |
| Fayl baza veb-server orqali | **Ha** (veb-server litsenziyasi) | yuqori |

**Huquqiy tomon:** IX.1-57: «использование программных или аппаратных средств, уменьшающих количество пользователей, которые имеют непосредственный доступ к «1С:Предприятию 8», не уменьшает количества требуемых лицензий. Организация должна приобрести такое количество клиентских лицензий, которое будет **не меньше числа пользователей, в действительности одновременно работающих** с системой» [S2]. Bizning holatda agent kassirlar uchun real vaqtli vositachi emas. U kun oxirida bitta texnik foydalanuvchi (`ERP integratsiya`) nomidan partiya yozadi. Kassirlar 1C bilan ishlamaydi. Bu «multipleksatsiya» hisoblanmasligi kerak — **lekin bu bizning talqinimiz**, rasmiy javob emas.

**Dalil:** S2, S3, S14, S15, S16, S17.
**Ishonch:** texnik xulq **o'rta-yuqori**; huquqiy talqin **past-o'rta** (hamkor tasdig'i kerak).

**Spec'ga ta'sir (taklif):**
- `01 #38` va `00-xulosa` §7: «texnik jihat tasdiqlanmagan» → «ИТС 10.2.5.7 bo'yicha mahalliy bir foydalanuvchilik litsenziyasi bo'lishiladi; istisnolar: server tarqatadi / RDP+HASP / veb-server». Qoida (agent litsenziyali PK'da, foydalanuvchi sessiyasida, qisqa ulanish) **o'zgarmaydi** — endi u manbali.
- Onboarding preflight: (a) baza turi (`File=` va `Srvr=`), (b) litsenziya xatosi `ONEC_LICENSE_UNAVAILABLE` bo'lsa, maslahat matni: «1C litsenziyani serverdan oladi — agent uchun alohida klient litsenziyasi yoki 1C ochiq bo'lmagan vaqtda yuborish kerak».
- `00-xulosa` V3: «amaliy xulq taxmin» → «hujjatlashtirilgan (ИТС 10.2.5.7), test 14 tasdiqlaydi».
- Hamkorga savol (Xat, 1C §13.8): «Kunda bir marta, bitta texnik foydalanuvchi nomidan, 1C litsenziyasi bor PK'da COM orqali partiya yozish — IX.1-57 dagi «уменьшение количества пользователей» hisoblanadimi?»

**Holat: QISMAN.** Yopish uchun: **test 14** (1 litsenziyali fayl baza; 1C ochiq va agent bitta OS sessiyasida → agent ulanadi va 1C ishlashda davom etadi; agent boshqa Windows foydalanuvchisida → natija) + **1C rasmiy hamkorining yozma javobi** (huquqiy talqin).

---

### OQ-049 — БП UZ 3.0.64 metadata nomlari (oldindan desk-research)

**Rasmiy reliz eslatmalaridan [S1] tasdiqlangan** (bu foydalanuvchiga ko'rinadigan **sinonimlar**, metadata identifikatorlari emas):

| Obyekt | Topilgan fakt | Versiya |
|---|---|---|
| ОРП hujjati | «Отчет о розничных продажах» bor. Alohida «**Отчет о розничных продажах (Серийный учет)**» hujjati ham bor | 3.0.62.1 |
| ОРП to'lov jadvali | «табличной части «**Безналичные оплаты**»», maydon «**Вид оплаты**» | 3.0.58.8 |
| ОРП tovar jadvali | «табличную часть «**Товары**»» (Excel'dan yuklash); qo'shimcha maydon «**Таможенная стоимость (НДС)**» | 3.0.45.1, 3.0.62.1 |
| ОРП bayroqlari | «**Не формировать проводки по кассе**» (naqd tushum alohida «Поступление наличных» / «Прочая выручка» bilan) | 3.0.64.1 |
| | «**Продажа через маркетплейс**» (QQS hisobotining 0104-satri) | 3.0.60.12 |
| | «**Товар маркирован**» | 3.0.50.1 |
| | Nol narx bilan o'tkazish mumkin | 3.0.57.1 |
| | Valyutada QQS 0% bilan | 3.0.55.1 |
| | «Заполнить – по остаткам» | 3.0.33.1 |
| Kassa | «Касса» rekviziti ОРП, «Поступление наличных», «Выдача наличных» da **faqat** Администрирование → Параметры учета → Настройка плана счетов → «Учет движения денежных средств» → «**По кассам**» bayrog'i yoqilganda; kassa prefiksi bilan alohida raqamlash | 3.0.23.1 |
| КассаККМ | Reliz eslatmalarida `КассаККМ` ma'lumotnomasi **uchramaydi**; faqat «Продажа через онлайн-ККМ» bayroqlari (Отчет комиссионера, Возврат товаров от покупателя) | 3.0.51.1, 3.0.58.1 |
| Viды oplat | «справочника «**Виды оплат**» с указанным **контрагентом, договором и процентом комиссии**»; valyuta «Вид оплаты» shartnomasi bo'yicha | 3.0.57.1, 3.0.55.1, 3.0.25.1 |
| Karta tushumi (bank) | «Поступление на расчетный счет» vid «**Поступления от продаж по платежным картам и банковским кредитам**» + Контрагент/Договор, komissiya avtomatik | 3.0.57.1 |
| Karta hujjati | «**Операции по платежным картам**» / «Операция по платежной карте». Vid «Услуги по платежным картам»; valyutada | 3.0.18.1, 3.0.25.1 |
| Chakana qaytarish | «**Возврат товаров от покупателя**» + bayroq «**Продажа через онлайн-ККМ**» (chakana qaytarish QQS 0102-satriga) | 3.0.58.1 |
| Cheklar | «Розничные продажи (чеки)», «**Чек (Продажа)**» (Продажи – Розничные продажи) mavjud | 3.0.9.1, 3.0.33.1 |
| QQS stavkasi | «В список ставок НДС добавлена ставка 12%»; avval 15% «добавлена и по умолчанию установлена» → stavka konfiguratsiya relizi bilan qo'shiladi, ya'ni **sanoq (Перечисление)** ehtimoli yuqori | 3.0.34.5, 3.0.9.1 |
| ИКПУ | Номенклатура shaklida «**ЭДО**» bo'limi: ИКПУ va shtrix-kod, «Код из классификатора», «Выбрать из списка» | 3.0.18.12 |
| | «**Упаковка (ЭДО)**» | 3.0.54.1, 3.0.57.1 |
| | ИКПУ bo'yicha qidiruv (Excel/ЭДО) | 3.0.60.12, 3.0.28.1 |
| QQS imtiyozi | 3.0.63.1 dan boshlab imtiyoz Номенклатура, ОС va ЭДО hisobidan **olib tashlandi** → yangi registr «**Льготы по НДС**» (ЭДО bo'limi), sotuv hujjatlarida to'ldiriladi | 3.0.63.1 |
| Schyot sozlamasi | registr «**Счета учета номенклатуры**» (Справочники bo'limiga chiqarildi) | 3.0.35.4 |
| Chakana nuqta turlari | Avtomatlashtirilgan (АТТ — absoft.uz «6.9 Как оформить отчет о розничных продажах в автоматизированной торговой точке») va **avtomatlashtirilmagan** («неавтоматизированную торговую точку», 2980.3 «Торговая наценка в неавтоматизированных…») | 3.0.33.1, 3.0.55.1 |
| Tannarx | ФИФО va АВЕКО («Корректировка остатков при переходе с ФИФО на АВЕКО»); oy yopishida «Корректировка стоимости номенклатуры» | 3.0.19.1, 3.0.43.1, 3.0.55.1 |

**Ruscha БП 3.0 dagi identifikatorlar** (UZ БП shu oiladan — UZ eslatmalarida RU БП 3.0 bilan bir xil hujjat va bo'lim nomlari, «Закрытие месяца», БСП). COM orqali dasturiy ОРП yaratish kodidan olingan [S12][S13]:
```
Документы.ОтчетОРозничныхПродажах.СоздатьДокумент()
  .ВидОперации = Перечисления.ВидыОперацийОтчетОРозничныхПродажах.ОтчетККМОПродажах   // АТТ
  .Организация, .Дата, .Склад, .ТипЦен, .ВалютаДокумента, .ДокументБезНДС,
  .СтатьяДвиженияДенежныхСредств, .СчетКасса, .Ответственный
  .Товары   : Номенклатура, Количество, Цена, Сумма, СчетУчета, СчетРасходов, СчетДоходов,
              Субконто (НоменклатурныеГруппы), СтавкаНДС (Перечисления.СтавкиНДС)
  .Возвраты : …как Товары + ДатаРеализации
  .Оплата   : ВидОплаты (Справочники.ВидыОплатОрганизаций), СуммаОплаты
```
→ **UZ uchun eng ehtimoliy xarita:** «Безналичные оплаты» = `Оплата`, «Виды оплат» = `ВидыОплатОрганизаций`, `СтавкиНДС` — sanoq. Bular `profile bp30_uz` dagi **standart nomlar** bo'ladi. `meta_sync` farq topsa, profil-ma'lumot yangilanadi.

**Topilmagan (faqat dump):**
- ИКПУ va «Упаковка (ЭДО)» rekvizitlarining identifikatorlari: rekvizit, alohida ma'lumotnoma yoki registr;
- `СтавкиНДС` sanoq qiymatlarining nomlari (`НДС12`?);
- `Касса` rekvizitining tipi («По кассам» yoqilganda `Справочник.Кассы`?);
- ОРП'da `Возвраты` jadval qismi UZ'da bormi;
- kartaga qaytarish vid operatsiyasi;
- 3.0.64.8 dagi `ВидыОперацийОтчетОРозничныхПродажах` qiymatlari.

**Dalil:** S1 (har qator versiya bilan), S12, S13; absoft.uz videodarslar ro'yxati.
**Ishonch:** sinonimlar va mavjudlik — **yuqori** (rasmiy); identifikatorlar — **o'rta** (RU БП dan xulosa).

**Spec'ga ta'sir (taklif):**
- `03-malumot-moslashtirish.md` §3.1 / `33` profil `bp30_uz`:
  - to'lov jadvali `Оплата(ВидОплаты, СуммаОплаты)` (`ОплатаПлатежнымиКартами` emas);
  - `Касса` ixtiyoriy («По кассам» bayrog'iga bog'liq, `meta_sync` aniqlaydi);
  - `КассаККМ` xaritasi **olib tashlanadi**.
- **Kassa xaritasi (BO-22):** ERP kassasi ↔ 1C «Касса» faqat «По кассам» yoqilgan bo'lsa. Aks holda ОРП kun × kassa bo'yicha qoladi, lekin 1C'da kassa farqi faqat `Комментарий`da.
- **QQS imtiyozi** Номенклатура xaritasidan chiqariladi. Imtiyozli sotuv ОРП'da qanday aks etishi — pilot savoli (ОРП «Льготы по НДС» registriga yozadimi yoki faqat Реализация?).
- **Profil detektori:** «Отчет о розничных продажах (Серийный учет)» va oddiy ОРП — `meta_sync` qaysi biri ishlatilishini so'raydi (standart — oddiy).
- `00-xulosa` §5 BO-22 ustasi: «kassa ↔ Касса/КассаККМ» → «kassa ↔ Касса (agar «По кассам»)».

**Holat: QISMAN.** Yopish uchun: **testlar 3, 4, 8, 9** — `meta_sync` dump (ОРП rekvizitlari va jadval qismlari, Номенклатура ИКПУ/упаковка, `СтавкиНДС` turi va qiymatlari, `ВидыОплатОрганизаций` tuzilmasi, `Возврат товаров от покупателя` va karta qaytarish vidi).

---

### OQ-050 — ОРП o'tkazish xulqi (oldindan desk-research)

| Kichik savol | Topilgan javob | Ishonch | Pilot testi |
|---|---|---|---|
| **Oy yopish turi** — БП 3.0 yoki 2.0 «Восстановление последовательности» (test 13) | BP UZ 3.0 — **«Закрытие месяца»** (БП 3.0 tipida). Uning ichida «**Перепроведение документов за месяц**» bor: ketma-ketligi buzilgan hujjatlar ro'yxati («Показать подробно», 3.0.45.1), «**Изменить контрольную дату**» — «перенос границы последовательности на конец месяца без перепроведения» (3.0.44.1), «Корректировка стоимости номенклатуры» (3.0.43.1, 3.0.55.1) | **yuqori** (S1) | 13 → **yopildi (desk)**; pilot faqat ko'rsatadi |
| Oy yopishning bizga ta'siri | Biz yozgan kech/orqa sanali ОРП ketma-ketlik chegarasini buzadi → buxgalter shu oy uchun «Закрытие месяца»ni (perepro bilan) qayta bajaradi. Bu 1C §13.6 savoliga javob: «oyni qayta yopish — buxgalter ishi, 1C o'zi ko'rsatadi» | o'rta-yuqori | — |
| **Qoldiq nazorati** (test 10) | «Разрешить списание запасов при отсутствии остатков по данным учета» (Администрирование → Проведение документов). O'chiq — hujjat o'tmaydi. Yoqilgan — o'tadi, lekin «Проводка будет сформирована только в количественном выражении без суммы» [S4][S22]. Bu RU БП uchun tasdiqlangan; BP UZ'da shu sozlama borligi — *taxmin* (UZ eslatmalarida bu bayroq tilga olinmagan; faqat davalchi materiallari uchun «при проведении документа осуществляется контроль остатков в разрезе контрагента» bor, 3.0.52.1) | RU: yuqori; UZ: o'rta | 10 |
| Oqibat (`sales_only` rejimi) | Bayroq yoqilgan bazada ОРП o'tadi, ammo tannarx 0 bo'ladi → `verify_totals` buni ko'rmaydi (biz faqat sotuv summasini solishtiramiz). Taklif: preflight shu sozlamani o'qiydi; «yoqilgan + kirim 1C'da yo'q» holatida ogohlantiradi («1C tannarxi nol bo'ladi») | o'rta | 10 |
| **Manfiy miqdorli qator** (test 7) | RU БП 3.0 ОРП'da qaytarish uchun **alohida jadval qismi `Возвраты`** (`ДатаРеализации` bilan) bor. Platforma qaytarishni sotuvga solishtiradi: «было реализовано "…" на "1" ед. меньше, чем возвращается» [S12]. Manfiy qator haqida hech bir manba yo'q → **ehtimoli past**. 3.0.64.54 (RU) da shu kungi qaytarishda konfiguratsiya xatosi qayd etilgan (support: «ошибка 10197456», УСН bilan) [S12] | o'rta | 7 + 8 |
| Shu kungi qaytarishning standart yo'li | (a) ОРП `Возвраты` (UZ'da bo'lsa); (b) sof summa (sotuvdan ayirish, `00-xulosa` §4 standarti); (c) `Возврат товаров от покупателя` + «Продажа через онлайн-ККМ». **Taklif:** profil standarti — (b) sof, chunki u eng kam bog'liqlikka ega; (a) — `meta_sync` `Возвраты`ni topsa | o'rta | 7 |
| **Bo'sh `СчетУчета…` → 1C o'zi to'ldiradimi** (test 5) | Hisoblar manbai — registr «Счета учета номенклатуры» (UZ'da bor, 3.0.35.4). RU kodda [S12] hisoblar **qo'lda** berilgan (`СчетУчета`, `СчетДоходов`, `СчетРасходов`, `Субконто`). Bu bo'sh hisoblar bilan ishonchli o'tkazishning yo'qligiga ishora. Platforma `Заполнить()` / forma handlerlari COM'da avtomatik chaqirilmaydi | o'rta | 5 |
| Taklif (test 5 salbiy chiqsa) | Agent `meta_sync`da «Счета учета номенклатуры» registrini o'qiydi (organizatsiya × ombor × nomenklatura/tur → hisoblar) va server profil qoidasi bilan har qatorga `СчетУчета/СчетДоходов/СчетРасходов/Субконто`ni **o'zi** qo'yadi (`.epf`siz, #41 bilan mos). Ustuvorlik: registrning eng aniq yozuvi → bo'sh o'lchamli yozuv | o'rta | 5, 6 |
| COM ОРП provodkalari = qo'lda kiritilgan (test 6) | Desk'da javob yo'q. Faqat «oltin namuna» bilan solishtirish | — | 6 |
| `Цена×Количество≠Сумма`, QQS yaxlitlash (test 12) | RU kod `Сумма = Цена*Количество` deb hisoblaydi [S12]. Nol narxga ruxsat bor (UZ 3.0.57.1). Desk'da yaxlitlash qoidasi topilmadi | past | 12 |

**Dalil:** S1 (3.0.43.1, 3.0.44.1, 3.0.45.1, 3.0.35.4, 3.0.52.1, 3.0.57.1, 3.0.64.1), S4, S12, S22.

**Spec'ga ta'sir (taklif):**
- `00-xulosa` §4 «Shu kungi qaytarish → ОРП ichida manfiy qator» → «**sof summa** (standart) yoki `Возвраты` jadval qismi (`meta_sync` topsa); manfiy qator ishlatilmaydi».
- `33` preflight: «Разрешить списание запасов…» sozlamasini o'qish (Константа — nomi `meta_sync`da). `full`/`sales_only` rejimiga qarab blok yoki ogohlantirish.
- `33` profil: schyotlar `Счета учета номенклатуры`dan agentda to'ldiriladi (test 5 natijasiga ko'ra yoqiladi/o'chiriladi — `onec_settings.fill_accounts`).
- 1C §13.6 javobi (buxgalter tasdiqlaydi): kech hujjatdan keyin «Закрытие месяца» → «Перепроведение документов за месяц» qayta bajariladi. BO-23 «yozildi» bannerida: «X oyi uchun 1C'da oyni qayta yopish kerak bo'lishi mumkin».

**Holat: QISMAN.** Oy yopish turi yopildi (test 13 → desk). Qoldiq sozlamasi va qaytarish yo'li manbali taxminga aylandi. Testlar **5, 6, 7, 10, 12** va buxgalterning «oltin namunasi» hamon kerak (Bosqich A gacha kod yozilmaydi — #37).

---

## 4. Pilot test rejasiga aniqlik kiritish (`00-xulosa` §10 uchun taklif)

| Test | O'zgarish |
|---|---|
| 1 | GUID'ni **faqat** `conn.NewObject("УникальныйИдентификатор", s)` bilan yaratish. Mavjudlik: `ПолучитьОбъект() = Неопределено`. Qo'shimcha: mavjud GUID bilan yangi obyektni `Записать` → xato matnini yozib olish (`ONEC_DUPLICATE_REF` regex) |
| 3 | Dump ro'yxatiga qo'shiladi: `Оплата`, `Возвраты` jadval qismlari, «Отчет о розничных продажах (Серийный учет)», `ВидыОперацийОтчетОРозничныхПродажах` qiymatlari, «По кассам» bayrog'i va `Касса` tipi, «Не формировать проводки по кассе» rekviziti |
| 4 | + «Льготы по НДС» registri tuzilmasi; ИКПУ/«Упаковка (ЭДО)» qayerda saqlanadi |
| 5 | + registr «Счета учета номенклатуры» o'lchamlari |
| 7 | Manfiy qator **o'rniga**: (a) `Возвраты` jadval qismi, (b) sof summa — ikkalasining provodkasi |
| 10 | Ikkala holat: bayroq o'chiq (xato matni) va yoqilgan (tannarx 0 provodkasi) |
| 13 | Faqat tasdiq: «Закрытие месяца» + «Перепроведение документов за месяц» kech ОРП'dan keyin chegarani ko'rsatadimi |
| 14 | Uch holat: (i) 1C ochiq + agent bitta Windows foydalanuvchisida; (ii) agent boshqa Windows foydalanuvchisida, litsenziya `ProgramData`da; (iii) bazada «выдача лицензий сервером» yoqilgan. «О программе → лицензия» ekrani skrinshoti |
| 15 | + `comcntr.dll` ro'yxatdan o'tmagan holat (onboarding UAC qadami) |

---

## 5. Ishonch va cheklovlar

- ИТС matnlari (S3, S5) login ortida. Iqtiboslar Google snippetlari va 1C hamkorining forumdagi so'zma-so'z ko'chirmasi (S14) orqali olindi. Rasmiy sahifa ochilganda so'zma-so'z tekshirish tavsiya qilinadi (bloklamaydi).
- БП UZ konfiguratsiyasining manba kodi va metadata'si ommaviy emas. RU БП 3.0 identifikatorlari faqat **standart taxmin**. Yakuniy haqiqat — `meta_sync` (#36: agent metadata'ni o'zi o'qiydi, xaritalar profil-ma'lumot).
- Forum dalillari (S8–S13, S17) — amaliy, lekin rasmiy emas. Har biri pilot testiga bog'langan.
