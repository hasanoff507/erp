# R1 — 1C:Enterprise 8.3 ga tashqi tizimdan yozish: COM (tashqi ulanish) chuqur tahlili

> **Yakuniy tavsiya ustun (accept gate, 2026-10-15):** shu papkadagi fayllar orasidagi ziddiyatlar `00-xulosa.md` da hal qilingan (§«Hal qilingan ziddiyatlar»). Bu fayl bilan `00-xulosa.md` farq qilsa — **00-xulosa'dagi yakuniy tavsiya ustun**. Kanonik nomlar: jadvallar — `04` §3.3; idempotentlik algoritmi — `04` §5.3; maydon xaritalari va ketma-ketlik — `03` §3, §5.1.

**Holat:** 2026-10-15. Hech narsa publish qilinmagan. Joylashuv: `research_notes/1c-integratsiya/`.
**Kim uchun:** asoschi va ERP'ning «1C integratsiyasi» bo'limi (kun/smena oxirida tugma → savdolar mijozning o'z 1C bazasiga tartib bilan yoziladi).
**Asoschi qarori (ushbu hujjatning asosi):** kanal — **faqat COM** (`V83.COMConnector`, tashqi ulanish), mijoz kompyuteridagi **Windows agent** orqali. 1C tomonda **hech narsa publish qilinmaydi** (veb-server, OData, HTTP/web-servis yo'q). Boshqa kanallar faqat 7-bo'limdagi «rad etilgan variantlar» jadvalida qisqa.
**Belgilar:** har bir faktga manba havolasi (oxirida «Manbalar» ro'yxati, `[M#]`). `[Sonar]` — bizning `research_notes/sonar-1c-integratsiya/` dagi dekompilyatsiya tahlili (birlamchi kod dalili). Tekshirilmagan da'volar — ***taxmin***.
**Cheklov eslatmasi:** ushbu tadqiqot paytida veb-qidiruv limiti tugagan, shuning uchun ba'zi da'volar (ayniqsa klient-server versiya mosligi, fayl bazadagi qulflar) rasmiy hujjat bilan emas, amaliy bilim bilan berilgan va *taxmin* deb belgilangan. Ularni demo-bazada sinash (8-bo'lim) majburiy.

---

## 0. Qisqa xulosa (1 daqiqada)

1. **COM tashqi ulanish — 1C ga yozishning eng to'g'ridan-to'g'ri yo'li**: 1C'ning o'z obyekt modeli orqali hujjat yaratiladi va **o'tkaziladi** (`Записать(РежимЗаписиДокумента.Проведение)`), konfiguratsiyani o'zgartirish, veb-server, port, VPN kerak emas [M1][M3]. Raqobatchi Sonar ham aynan shu yo'lni tanlagan [Sonar].
2. **Eng katta to'siq — 1C «Базовая версия»**: bazaviy versiyalarda tashqi ulanish (COM) **umuman ishlamaydi** — bu platforma cheklovi [M4][M5][M6]. Kichik do'konlarda bazaviy versiya ko'p uchraydi (*taxmin*), demak onboarding'da birinchi tekshiruv — «ПРОФ mi?».
3. **Litsenziya**: COM ulanish 1C litsenziyasini oladi [M2][M7][M8]. Mahalliy litsenziya bilan bitta OS sessiyasidagi klient ilovalar odatda bitta litsenziyani bo'lishadi («с оговорками» — tashqi ulanish uchun shart bilan) [M3]; amaliyotda bitta litsenziyali fayl bazada tashqi dastur COM orqali ulanganda foydalanuvchi 1C'ni ocholmay qolgan holat bor [M9]. → Agent **foydalanuvchining interaktiv sessiyasida** (tray ilova) ishlashi va ulanishni **qisqa** ushlashi kerak; Windows-servis sifatida emas.
4. **Bitlik**: in-process COM'da klient jarayon va `comcntr.dll` bitligi bir xil bo'lishi shart [M3] → agent 32 va 64-bit worker bilan keladi (Sonar shunday qilgan [Sonar]).
5. **COM ro'yxatdan o'tmagan / platforma yangilangan** — eng ko'p uchraydigan nosozlik; davo `regsvr32` admin huquqi (UAC) bilan, 64-bit OS'da 32-bit uchun `SysWOW64\regsvr32` [M10].
6. **Fayl baza + foydalanuvchilar ishlab turganda** yozish mumkin (tashqi ulanish — oddiy sessiya), lekin yozish tranzaksiyasi qisqa bo'lishi kerak (fayl variantda qulflar yirik — *taxmin*). Monopol rejim/yangilanish paytida ulanish rad etiladi → navbatda kutish va qayta urinish.
7. **Tavsiya**: asosiy kanal — COM agent (32/64-bit worker; texnologiya — standart **C# / .NET Framework 4.8**, `04` §2.1, `00-xulosa` bo'yicha), **kun × kassa bo'yicha jamlangan hujjatlar** (chek bo'yicha emas; smena bo'yicha — sozlama), idempotentlik — **deterministik GUID** (asosiy) + `Комментарий` markeri + bulutdagi `onec_object_refs` daftari, alohida minimal huquqli 1C foydalanuvchisi. Fallback yo'q (asoschi qarori) — bazaviy versiya va 1C:Fresh/ijaradagi bulut 1C mijozlari **qamrovdan tashqarida** qoladi (ochiq savol, 9-bo'lim).

---

## 1. COM tashqi ulanish nima va qanday ishlaydi

### 1.1 Mexanizm
- Rasmiy ta'rif: «Внешнее соединение — это один из механизмов интеграции с другими системами. Основная задача… — обеспечение надежного и быстрого программного доступа к данным 1С:Предприятия 8 из внешних приложений» [M1].
- Tashqi ulanishda to'liq 1C ilovasi ishga tushmaydi — «запускается относительно небольшой внутрипроцессный COM-сервер»; UI imkoniyatlari mavjud emas; ilova moduli o'rniga **«модуль внешнего соединения»** ishlaydi [M1].
- Automation-serverga (`V83.Application`) nisbatan afzalliklari: tezroq ulanish, obyekt xususiyatlariga tezroq murojaat (jarayonlararo aloqa yo'q), kamroq resurs [M1].
- Ketma-ketlik: `V83.COMConnector` (ulanishlar menejeri) yaratiladi → `.Connect("File=""C:\Base"";Usr=""…"";Pwd=""…"";")` yoki `Srvr=…;Ref=…` → qaytgan obyekt orqali `Справочники`, `Документы`, `Запрос` va h.k. bilan ishlanadi [M1][M3].
- Yaratish/o'zgartirish/o'tkazish 1C'ning **o'z biznes-logikasi** orqali bo'ladi (obyekt modullari, o'tkazish protsedurasi, huquq tekshiruvi) — to'g'ridan-to'g'ri SQL'dan farqli o'laroq. 1C litsenziya shartlari bazaga **to'g'ridan-to'g'ri** (DBMS yoki tashqi komponent orqali) murojaatni taqiqlaydi: «Нельзя обращаться к данным информационной базы напрямую, минуя уровень объектов работы с данными «1С:Предприятия»» [M7, savol X.6-65]. COM — ruxsat etilgan «штатное средство».

### 1.2 Biz uchun arxitektura (Sonar'dan olingan g'oya, kod emas)
```
ERP bulut (FastAPI)                         Mijoz PC (Windows, 1C o'rnatilgan)
 smena yopildi → "1C ga yuborish" tugmasi     ERP-agent (tray ilova, foydalanuvchi sessiyasida)
 → vazifa navbati (tartiblangan paketlar)  ◄── pull: hello / poll / result (HTTPS, chiquvchi)
                                              │ stdin/stdout JSON
                                              ▼
                                         worker32.exe / worker64.exe
                                              │ COM in-proc (V83.COMConnector)
                                              ▼
                                         1C baza (File=… yoki Srvr=…;Ref=…)
```
- **Pull** modeli: agent bulutga o'zi chiqadi, mijoz tarmog'ida kiruvchi port ochilmaydi [Sonar].
- COM alohida **worker jarayonida**: 1C qotsa/yiqilsa worker o'ldiriladi, agent ishlayveradi; timeout'da `Kill()` [Sonar].

---

## 2. Talablar (mijoz tomonida nima bo'lishi kerak)

| # | Talab | Izoh / manba |
|---|---|---|
| 1 | Windows | COM — Windows texnologiyasi; COM yondashuvining kamchiligi sifatida «Привязка к семейству операционных систем (платформе) Windows» qayd etilgan [M3]. |
| 2 | 1C:Enterprise 8.3 platformasi (yoki 8.5) **shu PC'ga o'rnatilgan** | `comcntr.dll` platforma bilan birga o'rnatiladi; `V8X.ComConnector` «регистрируется при установке платформы с опцией «Внешнее соединение»» [M3]. Sonar `V85`/`V83`/`V82.COMConnector` ni ustunlik tartibida qidiradi [Sonar] — 1C:Enterprise 8.5 allaqachon chiqqan [M11]. |
| 3 | **ПРОФ (yoki KORP) litsenziya**, bazaviy emas | Bazaviy versiyalarda «не поддерживается работа в режиме внешнего соединения (COM-соединение, Automation-сервер)» [M5]; rasmiy sahifada ham: «не поддерживается COM-соединение и Automation-сервер» [M4]; amaliy holat: БП bazaviyda COM ulanishda «Не найдена лицензия…» xatosi [M6]. |
| 4 | Bo'sh litsenziya o'rni (yoki 1C ochiq bo'lgan sessiyani bo'lishish) | 3-bo'lim. |
| 5 | Alohida 1C foydalanuvchisi (login/parol) — integratsiya uchun | 6-bo'lim. |
| 6 | Fayl baza bo'lsa — agent o'rnatilgan PC'dan baza papkasiga **yozish** huquqi | Fayl variantda barcha ma'lumot bitta faylda, uni platformaning fayl DBMS'i bevosita o'qiydi/yozadi [M12]. |
| 7 | Klient-server bo'lsa — LAN'dagi istalgan Windows PC, platforma versiyasi server bilan **bir xil** | *taxmin* (4.3-bo'lim). |
| 8 | Bir martalik admin huquqi (faqat `regsvr32` kerak bo'lsa) | [M10]; Sonar buni bitta «Tuzatish» tugmasi + UAC bilan qiladi [Sonar]. |

**Kerak emas:** konfiguratsiyani o'zgartirish yoki kengaytma (.cfe), veb-server (IIS/Apache), publikatsiya, port, VPN, statik IP. COM'ning afzalliklari ro'yxatida aynan «Отсутствие необходимости изменять конфигурацию баз» va «Не требуется разворачивать и поддерживать веб-сервер» bor [M3].

---

## 3. Litsenziya iste'moli (eng muhim xavf)

### 3.1 Faktlar
- **COM ulanish litsenziya oladi.** Rasmiy 1C litsenziyalash FAQ (1c.uz), savol **IX.1-57** («доступ к «1С:Предприятию 8» осуществляется с помощью COM-соединения»): foydalanuvchilar sonini kamaytiruvchi vositalar «не уменьшает количества требуемых лицензий» [M7] — *tasdiqlandi (accept gate WebFetch)*. ~~XI.1-66 (mobil server, COM)~~ — accept gate tekshiruvida 1c.uz sahifasida COM bilan bog'liq holda **topilmadi**; da'vo *tasdiqlanmagan*.
- **COM uchun litsenziya qidirish tartibi** (1C hujjatiga asoslangan sharh): 32-bit COM — mahalliy klient litsenziyalari → mahalliy server litsenziyalari (32 va 64) → tarmoq klient litsenziyalari → 1C serveridagi (klient-server) yoki veb-serverdagi klient litsenziyalari; 64-bit COM — xuddi shunday, server litsenziyasi faqat 64-bit. «При COM-соединении могут использоваться как клиентские лицензии, так и серверные» [M8].
- **Bitta OS sessiyasida bitta litsenziya (shart bilan)**: «всем клиентским приложениям, частным случаем которого являются Automation-сервер и с оговорками является внешнее соединение, в одном сеансе ОС требуется всего лишь одна на всех лицензия». Agar mahalliy HASP/dasturiy litsenziya topilmasa va litsenziya 1C serveridan olinsa — «каждое клиентское приложение и внешнее соединение может захватывать свою собственную лицензию» [M3].
- **Amaliy salbiy holat**: fayl UT 11 bitta PC'da, shu PC'da ishlashadi; TSD dasturi shu PC'da COM orqali ulanganidan keyin «на этом компьютере… 1С выдает сообщение о нехватке лицензий» [M9]. Forumdagi javob: «под COM-соединение необходима дополнительная клиентская лицензия» [M9]. Hamjamiyat maqolalarida ham «на каждое COM-соединение 1С затрачивается одна лицензия» deyiladi [M2][M13].

### 3.2 Talqin va bizning qoidalarimiz
- Ziddiyat [M3] va [M9] o'rtasida — ehtimoliy sabab: TSD dasturi boshqa OS foydalanuvchisi/servis sessiyasida ishlagan yoki litsenziya boshqa manbadan olingan (*taxmin*). Shuning uchun:
  1. **Agent Windows-servis emas, foydalanuvchi sessiyasidagi tray ilova** bo'lsin (Sonar ham shunday) — 1C bilan bir OS sessiyasida litsenziyani bo'lishish ehtimoli yuqori [M3] (*taxmin*, sinov shart).
  2. **Ulanish qisqa**: faqat yuborish paytida ochiladi, paket tugashi bilan yopiladi (Sonar 10 daqiqa bo'sh tursa yopadi [Sonar]). Smena oxiridagi yuborish bir necha daqiqa — litsenziyani doimiy band qilmaydi.
  3. **Litsenziya xatosini aniq ko'rsatish**: «1C litsenziyasi yetmadi — 1C'ni shu kompyuterda yoping yoki keyinroq qayta urining», vazifa navbatda qoladi.
  4. Onboarding'da **«ulanishni sinash»** bir vaqtning o'zida 1C ochiq turganda ham bajarilsin — shu mijozda litsenziya bo'lishilishi darhol aniqlanadi.
- Klient-server bazada litsenziya odatda server tomonda — agent ulanishi **+1 litsenziya** olishi mumkin [M3] (*taxmin*: mijozda zaxira litsenziya bo'lmasa muammo).

---

## 4. Texnik tafsilotlar

### 4.1 32/64-bit
- In-process rejimda: «Должен быть зарегистрирован класс V8X.ComConnector той же разрядности, что и COM-клиент» [M3]. Ya'ni 64-bit Python 32-bit 1C'ning `comcntr.dll` ini yuklay olmaydi.
- Muqobil: COM+ «серверное приложение» (dllhost surrogate) — har qanday bitlik, lekin `dcomcnfg` sozlamasi kerak, chaqiruvlar sekinroq (yaratish ~0,06 s vs 0,01 s) [M3]. Kichik do'kon uchun noqulay → **rad**.
- **Qaror**: ikki worker (32 va 64-bit), registrdan qaysi bitlik ro'yxatdan o'tganini aniqlash, xato bo'lsa ikkinchisiga avtomatik o'tish — Sonar aynan shunday [Sonar: `Platform.ChooseBits`, `OneCExecutor.OpenAsync` fallback].
- Texnologiya: (a) **.NET Framework 4.8 worker** x86/x64 (Windows 10/11 da odatda oldindan bor — *taxmin*) yoki (b) **ikki embedded Python** (32 va 64-bit) + `pywin32`. Orkestr (bulut bilan aloqa, navbat, UI) — Python. Tanlov 9-bo'limdagi ochiq savol.

### 4.2 COM ro'yxatdan o'tkazish (regsvr32 / UAC)
- Tipik nosozlik: platforma yangilangandan keyin ro'yxatdagi `comcntr.dll` eski papkaga ishora qiladi yoki umuman ro'yxatda yo'q. Davolash (rasmiy bo'lmagan, lekin standart) [M10]:
  - 64-bit 1C: `regsvr32 "<1C>\bin\comcntr.dll"`;
  - 64-bit OS'da 32-bit 1C: `C:\Windows\SysWOW64\regsvr32 "<1C>\bin\comcntr.dll"`;
  - admin huquqi bilan (UAC yoqilgan bo'lsa «Запуск от имени администратора»); yordam bermasa `/u` bilan o'chirib qayta ro'yxatdan o'tkazish, platformani «Исправить» rejimida qayta o'rnatish, so'ng «Службы компонентов» (DCOM) huquqlari [M10].
- Agent buni **bitta tugma** bilan qiladi: `ShellExecuteW(... "runas" ...)` → `regsvr32 /s`; UAC rad etilsa (Windows kodi 1223) — tushunarli xabar [Sonar].
- Agent **o'zi admin huquqisiz** o'rnatiladi (`%LOCALAPPDATA%`, HKCU), admin faqat `regsvr32` uchun so'raladi [Sonar].

### 4.3 Platforma versiyasi mosligi
- Bir PC'da bir nechta platforma versiyasi bo'lishi odatiy; COM uchun **oxirgi ro'yxatdan o'tgan** `comcntr.dll` ishlatiladi (*taxmin*). Agent registrdan `InprocServer32` yo'lini o'qib, versiyani ko'rsatsin [Sonar].
- **Fayl baza**: konfiguratsiya talab qilgan minimal platforma versiyasidan eski `comcntr` bilan ulanish xato beradi (*taxmin*). → «Tuzatish»: yangi platforma `comcntr.dll` ini ro'yxatdan o'tkazish.
- **Klient-server**: `comcntr` versiyasi 1C server klasteri versiyasi bilan **aynan bir xil** bo'lishi kerak, aks holda «несоответствие версий клиента и сервера» turidagi xato (*taxmin* — keng ma'lum amaliyot, rasmiy manba topilmadi). Server yangilanganda agent PC'dagi platformani ham yangilash kerak.
- 1C-dan-1C COM uchun: «Если издание платформы COM-клиента совпадает с изданием платформы COM-сервера, то также требуется равенство сборки» [M3] — bu ichki 1C mijozlarga tegishli, lekin klient-server holatda xuddi shu qat'iylikni kutish kerak (*taxmin*).

### 4.4 Fayl baza va server baza
| | Fayl baza (kichik do'kon odatda) | Klient-server |
|---|---|---|
| Ulanish satri | `File="C:\…\Base";Usr=…;Pwd=…;` | `Srvr="host";Ref="base";Usr=…;Pwd=…;` [M1][Sonar] |
| Agent qayerda | Afzal — baza fayli turgan PC'da (tarmoq ulushi orqali emas) | LAN'dagi istalgan Windows PC |
| Litsenziya | Mahalliy (PC'dagi) | Ko'pincha server litsenziyasi → +1 sessiya [M3] |
| Versiya | Konfiguratsiya talabi ≥ | Server bilan aynan bir xil (*taxmin*) |
| Xavf | Tarmoq ulushidagi fayl bazaga ulanish uzilsa, baza buzilishi mumkin (*taxmin*) | Kamroq |
- Fayl variant «рассчитан на персональную работу одного пользователя или работу небольшого количества пользователей в локальной сети»; barcha ma'lumot bitta faylda; zaxira nusxa — faylni oddiy nusxalash [M12]. → Agent birinchi yuborishdan oldin **zaxira nusxa** taklif qilsin (faylni ishlab turgan bazadan nusxalash xavfli — 1C yopiq paytda yoki 1C'ning o'z «Выгрузить информационную базу» vositasi orqali, *taxmin*).

### 4.5 Foydalanuvchilar bilan bir vaqtda ishlash, monopol rejim, qulflar
- Tashqi ulanish — bazaga oddiy sessiya; foydalanuvchilar ishlayotganda ham ulanish mumkin (Sonar'ning butun modeli shunga qurilgan [Sonar]; [M9] dagi holatda ham baza ishlatilayotgan paytda COM ulangan).
- **Monopol rejim / konfiguratsiya yangilanishi** paytida ulanish rad etiladi; Sonar buni `base_locked` → «1C bazasi band (monopol rejim yoki yangilanish) — birozdan keyin qayta urinib ko'ring» deb ko'rsatadi [Sonar]. → Vazifa navbatda qoladi, backoff bilan qayta urinish.
- Teskari ta'sir: agent ulanishi **ochiq turganda** buxgalter 1C'ni yangilay olmaydi (monopol rejimga o'tish uchun barcha sessiyalar yopilishi kerak) (*taxmin*) → ulanishni qisqa ushlash (3.2) yana bir sabab.
- «Блокировка работы пользователей» (BSP) yoqilgan bo'lsa yangi sessiyalar taqiqlanadi; ruxsat kodi ulanish satrida `UC=<kod>` bilan beriladi (*taxmin*) — agent bu holatni alohida xato bilan ko'rsatsin, kodni so'ramasin.
- **Qulflar (fayl variant)**: fayl DBMS'da yozish qulflari jadval darajasida yirik, yozuvchi tranzaksiya boshqa yozuvchilarni kuttiradi (*taxmin*). → Har hujjat **alohida qisqa tranzaksiya** (bitta katta tranzaksiyada butun smena emas); smenani jamlangan bir nechta hujjat sifatida yozish; foydalanuvchiga «1C'ga yozilmoqda, 1–2 daqiqa» holatini ko'rsatish.

### 4.6 Tezlik
- O'lchov ma'lumotlari [M3]: in-proc COM obyekt yaratish ~0,01 s (birinchi) / 0,001 s; `Connect` — «Создание сеанса – 1 сек» + sessiya initsializatsiyasi (modul `ПриНачалеРаботыСистемы`, sessiya parametrlari, metadata) — tipik konfiguratsiyada bir necha soniya bo'lishi mumkin (*taxmin*).
- Har bir COM chaqiruv marshaling bilan qimmatroq; tavsiya — «минимум COM-вызовов», yirik chaqiruvlar [M3]. Bu muallif konfiguratsiyani o'zgartirmaslik uchun COM orqali **tashqi qayta ishlash (.epf)** ni yuklab, unga bitta katta chaqiruv yuborishni taklif qiladi («Сервисный процессор») [M3]. Bu bizda optimallashtirish varianti; lekin tashqi qayta ishlash xavfsiz rejim/«Защита от опасных действий» cheklovlariga tushishi mumkin (*taxmin*) → MVP'da shart emas.
- Bizning hajm: smena = bir necha yuz chek, lekin 1C ga **jamlangan** hujjat(lar) — masalan «Отчет о розничных продажах» smena/do'kon bo'yicha (*taxmin*: o'zbek tahrirlarida hujjat nomi va tuzilishi tekshirilsin, bu R-mavzu boshqa hujjatda). 100 qatorli hujjatni COM orqali yozish + o'tkazish fayl bazada bir necha soniya (*taxmin*, 8-bo'limda o'lchanadi). Smena oxiri uchun yetarli.
- Ulanishni paket davomida ochiq ushlab, keyin yopish (har hujjat uchun qayta `Connect` qilmaslik).

### 4.7 Barqarorlik
- 1C ichidagi xato yoki modal dialog kutish worker'ni osib qo'yishi mumkin → **alohida jarayon + timeout + Kill** (Sonar: open 120 s, yozish 10–1800 s, timeout'da jarayonni o'ldirish, bir marta qayta urinish) [Sonar].
- COM chaqiruvini o'rtada to'xtatib bo'lmaydi va jarayon haqida progress yo'q — «Нельзя прервать поток COM-Клиента… пока не завершится вызов COM-сервера» [M3] → timeout faqat jarayon darajasida.
- Timeout bo'lsa natija **noma'lum**: «yozildimi yo'qmi noma'lum — tekshiraman» → keyingi ulanishda marker bo'yicha qidirish (5-bo'lim) [Sonar].
- Uzoq yashovchi ulanishda xotira o'sishi (*taxmin*) → worker har paketdan keyin yopiladi.
- Tipik konfiguratsiyaning ba'zi kod yo'llari interaktiv kontekstni kutadi; tashqi ulanishda UI yo'q [M1] → bunday joylarda xato; har hujjat turi demo-bazada sinovdan o'tkaziladi.

---

## 5. Hujjat yaratish + o'tkazish, idempotentlik, xato qaytarish

- **Yaratish va o'tkazish**: `Документы.<Тип>.СоздатьДокумент()` → rekvizitlar, jadval qismlari → `Записать(РежимЗаписиДокумента.Проведение)`; o'tkazish xatosi (masalan qoldiq yetmasa) COM istisnosi sifatida keladi — matni ERP'ga qaytariladi (*taxmin*: o'tkazish xabarlari `ПолучитьСообщенияПользователю()` orqali ham olinishi kerak). Sonar `write|post` rejimi aynan shu [Sonar].
- **Havolalar** (tovar, kontragent, ombor): faqat **topiladi** (kod/shtrix-kod/INN bo'yicha); topilmasa yoki 2+ bo'lsa — xato, o'zi yaratmaydi (yoki aniq siyosat bilan yaratadi — bu mapping R-mavzusi) [Sonar].
- **Idempotentlik** (konfiguratsiyani o'zgartirmasdan). *Accept gate:* yakuniy tartib — (0) **deterministik GUID** (`УстановитьСсылкуНового`, `04` §5.2–5.3) asosiy; quyidagi marker — inson uchun iz va GUID usuli pilotda ishlamasa zaxira; xarita — `onec_object_refs`:
  1. 1C ichida marker: `Комментарий = "ERP #<smena_id>/<hujjat_kaliti>"` — yozishdan oldin shu marker bo'yicha so'rov; topilsa qayta yaratilmaydi [Sonar: `Sonar #<id>` markeri].
  2. Bulutda xarita: ERP hujjat ID ↔ 1C `Ссылка.УникальныйИдентификатор()` — keyingi qayta urinishlar ref orqali.
  3. Optimistik qulf: o'zgartirishda `ВерсияДанных` solishtiriladi [Sonar].
  4. Ixtiyoriy kengaytma (.cfe) bilan alohida «ERP ID» rekviziti yoki axborot registri — **shart emas**, faqat mijoz rozi bo'lsa (bazaviy versiyada kengaytmalar umuman yo'q [M5]).
- **Tartib**: paket ichida qat'iy tartib (avval ma'lumotnomalar, keyin kirim, keyin sotuv, keyin pul) — har qadam natijasi bulutga `result` bilan; xatoda paket to'xtaydi, keyingilari yuborilmaydi (tartib buzilmasin).
- **Xato qaytarish**: worker JSON `{code, message, doc_key}` → bulutdagi «1C integratsiyasi» ekranida qator bo'yicha holat (yuborildi / o'tkazildi / xato + 1C matni), «Qayta yuborish» tugmasi.

---

## 6. Xavfsizlik

- **Alohida 1C foydalanuvchisi** (masalan «ERP integratsiya»): faqat kerakli hujjat turlarini yaratish/o'tkazish va ma'lumotnomalarni o'qish huquqi + platformaning «Внешнее соединение» huquqi (*taxmin*: BSP konfiguratsiyalarida bu huquq qaysi rol/profilda ekanini demo-bazada aniqlash kerak). «Полные права» bermaslik.
- Bazaviy RLS saqlanadi: ma'lumot faqat 1C obyektlari orqali → 1C huquq tekshiruvi ishlaydi [M1]; to'g'ridan-to'g'ri DB murojaati litsenziya bo'yicha taqiqlangan [M7].
- Parol: Windows DPAPI (CurrentUser) bilan shifrlangan, bulutga **hech qachon** yuborilmaydi; ulanish satri loglarda `Pwd=***` [Sonar].
- **Agent ixtiyoriy kod bajarmaydi**: bulutdan faqat oq ro'yxatdagi operatsiyalar (`create_doc` turi X, bizning mapping bo'yicha) keladi; COM `Выполнить`/ixtiyoriy so'rov matni yo'q. Vazifalar imzolangan/TLS, agent tokeni bekor qilinadigan.
- Avto-yangilanish imzolangan manifest + SHA-256 bilan [Sonar].
- Yozish uchun ikki qulf (kompaniya sozlamasi + shu PC) — tasodifiy yoqilishdan himoya [Sonar].

---

## 7. Rad etilgan variantlar (qisqa)

| Variant | Bir qatorli sabab |
|---|---|
| OData standart interfeysi (REST) | Veb-serverga publikatsiya kerak («достаточно включить поддержку OData при публикации на веб-сервере») [M14] — asoschi rad etgan; bazaviy versiyada internet-servislar yo'q [M5]. |
| HTTP-servislar | Kengaytma/konfiguratsiya o'zgarishi + publikatsiya («аналогично тому, как публикуются web-сервисы») [M15] — rad etilgan. |
| Web-servislar (SOAP) | Xuddi shu: konfiguratsiyada servis + publikatsiya [M15] — rad etilgan. |
| EnterpriseData (KD 3.0) | Foydalanuvchi 1C'da sinxronizatsiyani sozlashi kerak; rasmiy qo'llab-quvvatlash ro'yxatida faqat RF konfiguratsiyalari (ERP, БП 3.0, Розница 2.0, УТ 11…) [M16]; O'zbekiston tahrirlarida mavjudligi tekshirilmagan (*taxmin*). |
| Universal XML almashinuv (KD 2.0 qoidalari) | Har konfiguratsiya/versiya uchun qoidalar yozish va qo'llab-quvvatlash, foydalanuvchi faylni qo'lda yuklaydi — ko'p mehnat, xatoga moyil. |
| Tashqi qayta ishlash (.epf) 1C ichidan bizning API'ni tortadi | Agent kerak emas, lekin foydalanuvchi har gal 1C'ni ochib bosishi kerak; xavfsiz rejim cheklovlari (*taxmin*); asoschi COM'ni tanladi. **Bazaviy versiya uchun yagona realistik zaxira** bo'lishi mumkin (*taxmin*: bazaviyda tashqi qayta ishlash ishlaydi). |
| Automation-server (`V83.Application`) | To'liq 1C ilovasini ishga tushiradi — sekinroq va og'irroq [M1]; bazaviyda ham yo'q [M5]. |
| 1C:Fresh / ijaraga olingan bulut 1C | Baza mijoz PC'sida emas → COM imkonsiz; Fresh'da faqat OData [M14] (rad etilgan). O'zbekistonda bunday xizmatlar bor (clobus.uz 1C:Fresh, uzcloud.uz «Аренда 1С») [M17] — bu mijozlar qamrovdan tashqarida. |
| To'g'ridan-to'g'ri DB (SQL/1CD fayl) | Litsenziya bo'yicha taqiqlangan [M7, X.6-65]. |
| Konfiguratsiya kengaytmasi (.cfe) | Shart emas; faqat ixtiyoriy optimallashtirish (5-bo'lim). Bazaviyda kengaytmalar yo'q [M5]. |

---

## 8. Tavsiya va keyingi qadamlar

**Asosiy kanal:** COM tashqi ulanish, Windows tray-agent, pull modeli, 32/64-bit worker, qisqa ulanish, jamlangan hujjatlar, 1C marker + bulut xaritasi bilan idempotentlik, alohida minimal huquqli 1C foydalanuvchisi.

**Onboarding tekshiruvlari (agent avtomatik):**
1. 1C platformasi o'rnatilganmi, qaysi versiya/bitlik, `comcntr.dll` ro'yxatdami → yo'q bo'lsa «Tuzatish» (UAC).
2. `ibases.v8i` dan bazalar ro'yxati, tanlash [Sonar].
3. «Saqlash = ulanishni sinash» — 1C **ochiq turgan holda** ham.
4. Bazaviy versiya aniqlansa — aniq xabar: «1C bazaviy versiyasi tashqi ulanishni qo'llab-quvvatlamaydi; ПРОФ kerak» [M4][M5].
5. Konfiguratsiya nomi/versiyasi (БП/УТ/Розница/УНФ «для Узбекистана») → mapping profili tanlanadi.

**Demo-bazada majburiy sinovlar (bu hujjatdagi *taxmin*larni yopish uchun):**
- 1 litsenziyali fayl baza: 1C ochiq + agent ulanadi (bir OS sessiyasi) → ikkinchi foydalanuvchi ocha oladimi? Agent servis sifatida → farq?
- 32-bit va 64-bit platforma; ikki versiya o'rnatilgan PC.
- 100/500 qatorli hujjatni yozish + o'tkazish vaqti; foydalanuvchi parallel hujjat o'tkazayotganda kutish.
- Monopol rejim, «Блокировка работы пользователей», klient-server versiya nomuvofiqligi xatolari matni.
- Minimal huquqli foydalanuvchi bilan ulanish va o'tkazish.

---

## 9. Ochiq savollar (asoschi uchun)
1. **Bazaviy versiya** mijozlari: qamrovdan chiqaramizmi yoki zaxira sifatida .epf (1C ichidan tortish) qilamizmi? (COM'da texnik yo'l yo'q.)
2. **1C:Fresh / ijaradagi bulut 1C** mijozlari: qamrovdan tashqari deb belgilaymizmi?
3. Worker texnologiyasi: .NET Framework 4.8 (x86/x64) yoki ikkita embedded Python (`pywin32`)? — *standart tavsiya: .NET Framework 4.8 (`00-xulosa` savol 1).*
4. Ixtiyoriy kengaytma (ERP ID rekviziti) — mijoz rozi bo'lsa taklif qilamizmi yoki umuman tegmaymizmi?

---

## Manbalar
- [M1] 1C rasmiy: «Внешнее соединение» — https://v8.1c.ru/platforma/vneshnee-soedinenie/
- [M2] Koderline, «Платформа 1С: Строка подключения» (2023) — https://www.koderline.ru/expert/narabotki/article-platforma-1s-stroka-podklyucheniya/
- [M3] Klerk, «Взаимодействие между базами 1С через COM» (o'lchovlar, bitlik, litsenziya, kamchiliklar) — https://www.klerk.ru/soft/articles/430201/ (shu matn: https://infostart.ru/1c/articles/387577/)
- [M4] 1C rasmiy, «Базовая версия» (БГУ misolida bazaviy cheklovlar) — https://v8.1c.ru/stateacc/bazovaya-versiya-bgu/
- [M5] Online-UFA (1C partnyori), «Отличия Базовых и ПРОФ версий» — https://www.online-ufa.ru/content/articles/1c_baz/
- [M6] Infostart forum, «1С БП 3.0 Базовая версия, com-соединение» — https://forum.infostart.ru/forum9/topic289927/
- [M7] 1C Uzbekistan, litsenziyalash bo'yicha savol-javoblar (XI.1-66 — COM litsenziya; X.6-65 — to'g'ridan-to'g'ri DB taqiqi) — https://1c.uz/v8/questions_licence.php
- [M8] Online-UFA, «Алгоритм поиска лицензий 1С» (6-bo'lim: COM) — https://www.online-ufa.ru/content/articles/1c-license-search/
- [M9] Infostart forum, «COM соединение и 1С лицензии» (2021) — https://forum.infostart.ru/forum28/topic258045/
- [M10] HelpMe1s, «Решение проблем с COM-библиотекой» (bazaviy versiya, regsvr32, SysWOW64, UAC, DCOM) — https://helpme1s.ru/obnovlyator-1s-reshenie-problem-s-com-bibliotekoj-dlya-vneshnego-podklyucheniya-k-baze
- [M11] 1C rasmiy, «1С:Предприятие 8.5: новый дизайн» — https://v8.1c.ru/platforma/new-ui-85/
- [M12] 1C rasmiy, «Файловый вариант работы» — https://v8.1c.ru/platforma/faylovyy-variant-raboty/
- [M13] WiseAdvice, «COM-соединение в 1С 8.3» (2025) — https://wiseadvice-it.ru/o-kompanii/blog/articles/com-soedinenie-v-1s-8-3/
- [M14] 1C:Fresh, «Работа с данными… через стандартный интерфейс OData» — https://1cfresh.com/articles/data_odata ; 1C rasmiy REST interfeysi — https://v8.1c.ru/platforma/rest-interfeys/
- [M15] 1C rasmiy, «HTTP-сервисы» — https://v8.1c.ru/platforma/http-servisy/
- [M16] 1C rasmiy, «Формат EnterpriseData» — https://v8.1c.ru/tekhnologii/obmen-dannymi-i-integratsiya/standarty-i-formaty/format-enterprisedata/
- [M17] Qidiruv natijalari: clobus.uz («Программы 1С в облаке (1С:Фреш)»), uzcloud.uz («1С в облаке в Узбекистане — Аренда 1С от 220 000 сум/мес»); 1C O'zbekiston mahsulotlari ro'yxati — https://1c.uz/v8/generic_products/index.php
- [Sonar] `research_notes/sonar-1c-integratsiya/00-xulosa.md`, `01-bazani-topish-va-sozlash.md` (§2.2–2.4, regsvr32/UAC, bitlik fallback), `02-1c-dan-malumot-oqish.md` (§1.5 timeout/Kill/idle), `04-1c-ga-yozish-va-tasdiqlash.md` (§2.5–2.6 ВерсияДанных, marker).
