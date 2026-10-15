# Sonar AI (v1.1.5) — mahsulot funksiyalari va server API tahlili

> Manba: `E:/Project/sonar/decompiled/` (dekompilyatsiya qilingan C#/Avalonia/.NET kodi). Tahlil **faqat o'qish** asosida, kod ishga tushirilmagan. Har bir da'vo `fayl:qator` havolasi bilan tasdiqlangan. Sonar — O'zbekiston "1C: Buxgalteriya" konfiguratsiyasi ustida ishlaydigan AI-yordamchi/SaaS: desktop ilova (Avalonia) + alohida "connector" jarayoni (1C bilan bog'lanadi) + markaziy server (`sonar.shaxzoddev.uz`) + Telegram bot (`@sonar_aibot`).

---

## 0. Umumiy arxitektura (qisqa)

- **Desktop ilova** (`src_app/Sonar`, `Sonar.Desktop.Core`) — Avalonia MVVM: `Views/*` + `ViewModels/*`.
- **Connector** (`src_app/Sonar.Engine`) — foydalanuvchi kompyuterida ishlaydigan alohida jarayon, real 1C bazasiga COM/OData orqali ulanadi, serverdan buyruq oladi.
- **Mock/Demo qatlami** — ikki bosqichda: `Sonar.Desktop.Core.Mock` (butun server API'ni simulyatsiya qiladi, `SONAR_MOCK=1`) va `Sonar.Core/DemoSession.cs` (1C bazasining o'zini simulyatsiya qiladi — haqiqiy 1C o'rniga sintetik savdo kompaniyasi).
- **Server**: yagona endpoint `https://sonar.shaxzoddev.uz/api/v1.php`, har bir chaqiriq `?a=<action>` bilan POST qilinadi (REST emas, action-dispatch uslubi) — `HttpTransport.cs:70-82`, `AppSettings.cs:5`.
- **Login**: parol yo'q — Telegram bot orqali QR/kod bilan kirish (`auth.start`/`auth.poll`).
- **To'lov**: ilova ichida emas, Telegram botda (`t.me/sonar_aibot?start=tarif`).

---

## 1. Mahsulot funksiyalari — katalog

### 1.1 Dashboard (Bosh sahifa)

| | |
|---|---|
| **Maqsad** | Bir qarashda holat: 1C ulanishi, 4 KPI plitkasi, tarif holati, Checks xulosasi, valyuta kurslari, tasdiqqa kutilayotgan AI o'zgarishlar, so'nggi faoliyat, onboarding checklist. |
| **Manba** | `SonarApi.CompanyDashboardAsync` → `company.dashboard` (`SonarApi.cs:137-140`) → `Dashboard{OneC, DashboardCounts, Recent}`. KPI plitkalari alohida `reports.run` (`cash`/`receivables`/`payables`/`sales`) chaqiradi — `KpiTileViewModel.cs:174-182`. |
| **Mantiq** | `KpiLogic.ForModules` — yoqilgan modullardan 4 tagacha KPI tanlaydi (`KpiLogic.cs:13-34`). `Extract()` 1C hisob-kitob kodlarini biladi: kassa = "50"*, bank = "51"/"52"/"55"* (`KpiLogic.cs:102-138`) — haqiqiy 1C hisoblar rejasi bilimi mijoz kodiga yozilgan. `DashboardViewModel.Rebuild()` kun vaqtiga qarab salom beradi, 1C offline/ulanmagan banner, 3 qadamli checklist (`DashboardViewModel.cs:1109-1191`). |
| **UI matnlar** | `Dashboard.Greeting`: "Xayrli tong/kun/kech/tun" (`Uz.cs:1127-1141`); `Home.AskPlaceholder` = *"Masalan: Bugun «Anvar Savdo» dan 2 500 000 so'm naqd kirim — PKO yarat"* (`Uz.cs:4526`); `Home.AwaitingText(n)` = *"AI 1C uchun {n} ta o'zgarish tayyorladi — ko'rib chiqib, «Bajarish» ni bosing."* (`Uz.cs:4581-4588`). |
| **UX** | KPI max 4 ta; kutilayotgan tasdiqlar ro'yxati max 3 ta; bo'sh/offline holatlar uchun alohida matnlar. |

### 1.2 Digest — kunlik Telegram hisoboti

| | |
|---|---|
| **Maqsad** | Tanlangan kunlari Telegram'ga (`@sonar_aibot`) qisqa hisobot yuborish: kassa/bank, qarzlar, ombor, tekshiruv natijasi, valyuta kurslari — ilovani ochmasdan nazorat. |
| **Manba** | `automation.get` (`AutomationInfo.Digest`), saqlash `automation.digest_set` (`company_id, enabled, time, days[], items[]`), sinov yuborish `automation.digest_test` → `DigestTestResult.Sent` (`SonarApi.cs:504-524`). |
| **Mantiq** | `DigestLogic.cs`: 5 bo'lim (`cash,debts,stock,checks,rates`), 48 yarim-soatlik slot, `Next()` 7 kun oldinga qarab Toshkent vaqti bo'yicha keyingi yuborish vaqtini hisoblaydi. Tarif faol bo'lmasa bloklanadi. |
| **UI matnlar** | `Lead` = *"Tanlangan kunlari Telegram'ga qisqa hisobot: kassa, qarzlar, ombor, tekshiruv va kurslar."*; `TariffTitle` = *"Telegram hisoboti Buxgalter tarifi bilan ishlaydi"*; `TariffText` = *"Tekshiruv va eslatmalar tarifsiz ham ishlaydi."* (`Uz.cs:115-189`). |
| **UX** | Kamida 1 kun + 1 bo'lim tanlanishi shart; "hozir yubor" tugmasi bloklanganda o'chiq. |

### 1.3 Checks ("Tekshiruv") — 1C ma'lumot sifati

| | |
|---|---|
| **Maqsad** | 1C dagi raqamlarni qoida asosida tekshirish — oy yopishdan oldin xatolarni topish. |
| **Manba** | `checks.run` (`company_id, refresh`) → `ChecksResult`; eksport `checks.file` (`SonarApi.cs:485-497`). |
| **Har bir tekshiruv turi** (server-mantig'i mock orqali ochiladi, `MockAutomation.cs:144-319`): `no_base` (1C ulanmagan), `data_fresh` (ma'lumot yangi/eski), `cash_positive/negative` (kassa-bank manfiy bo'lmasligi), `negative_stock` (ombordagi manfiy qoldiq), `low_stock` (0-5 birlik — kam qoldiq), `debt_concentration` (debitorlik >25% bitta kontragentda), `advances_received`/`advances_given` (avanslar), `tax_overpaid` (soliq ortiqcha to'langan), `trial_balance` (aylanma-saldo Dt=Kt), `active_credit` (aktiv hisobda noto'g'ri tomonda qoldiq). |
| **Mantiq** | `ChecksLogic.cs`: darajalar error>warn>info>ok (`:27-35`); `Visible()` yangilash paytida eski natijani ko'rsatib, UI "miltillashini" oldini oladi (`:140-171`) — puxta UX hiylasi; har tekshiruv jadvali max 10 qator; poll 3.5s, max 2 daqiqa kutish. |
| **UI matnlar** | `Lead` = *"Sonar 1C dagi raqamlarni qoida bilan tekshiradi: manfiy qoldiq, Dt ≠ Kt, qarzlar, soliqlar."*; `Slow` = *"1C javobi kechikmoqda..."*; `AllGood` = *"Hammasi joyida"* (`Uz.cs:25-95`). |

### 1.4 Month — Oylik (payroll oy kesimi)

| | |
|---|---|
| **Maqsad** | Tanlangan oy uchun har bir xodim bo'yicha hisoblangan/ushlangan/qo'lga tegadigan/qarz — **faqat o'qish** rejimida, 1C'dan. |
| **Manba** | `payroll.month` (`company_id, period, refresh`) → `PayrollMonthResult` (`SonarApi.cs:438-446`); hisob varaqalari eksporti `payroll.payslips_file`. |
| **Mantiq** | `PayrollLogic.RefetchInterval` — birinchi 20 poll 3s, keyin 5s; `ViewState` server holatini (`ready/refreshing/loading/error/no_base/unsupported/not_found`) UI holatiga aylantiradi; oy tanlash oxirgi 60 oy bilan cheklangan, kelajakka o'tish mumkin emas. |
| **UI matnlar** | `WriteNote` = *"Oylikni 1C da hisoblash (yozish) keyingi bosqichda qo'shiladi — hozircha 1C dagi natijalar faqat o'qiladi."* (`Uz.cs:1631`) — **yozish funksiyasi hali yo'q, rejada.** `NotCalculated` = *"Bu oyda hali hisoblash kiritilmagan..."* |

### 1.5 BankCompare — bank ko'chirmasini solishtirish

| | |
|---|---|
| **Maqsad** | Bank-mijoz eksport faylini (`.txt`/`.xlsx`/`.csv`, ≤5MB) 1C dagi bank yozuvlari bilan qator-qator solishtirish. |
| **Manba** | `bank.compare` (`company_id, name, data(base64), refresh`) → `BankCompareResult{Rows, Days, Summary,...}` (`SonarApi.cs:575-584`). |
| **Mantiq** | Qator holatlari: `diff` (summa farq), `not_in_1c`, `not_in_bank`, `ok`/`ok_amount` — rang-kodlash `BankCompareLogic.ToneOf`; UI'da 300 qatorgacha, qolgani faqat Excel eksportida. |
| **UI matnlar** | `FormatHint` = *"Bank-mijozdan «1C ga yuklash» fayli (kl_to_1c.txt) yoki Excel..."*; `OldXls` = eski `.xls` formatini rad etadi, `.xlsx`ga saqlab qayta yuklashni so'raydi. |

### 1.6 InventoryCompare — inventarizatsiya

| | |
|---|---|
| **Maqsad** | Jismoniy sanoq (CSV/Excel) bilan 1C ombor qoldig'ini solishtirish — ortiqcha/kamomad/sanalmagan. |
| **Manba** | `inventory.compare` (`company_id, name, data(base64), warehouse`) → `InventoryCompareResult` (`SonarApi.cs:564-573`). |
| **Mantiq** | `CompareLogic.Ordered` — diff→not_in_1c→not_counted→ok tartibida saralaydi; shtrix-kod bo'yicha, keyin SKU/kod bo'yicha moslashtirish (mock: `MockAutomation.cs:562-598`); ombor bo'yicha filtr. |
| **UI matnlar** | `FormatHint` = *"Ustunlar: Shtrix-kod; Nomi; Kod; Miqdor"*; `NotCountedSumTip` = *"Sanalmagan tovarlarning 1C dagi qiymati — qisman sanoq kamomad emas"*. |

### 1.7 DebtLetters — qarzdorlarga xat / akt sverki

| | |
|---|---|
| **Maqsad** | Qarzdorlik hisobotidan ommaviy Word hujjat generatsiyasi: eslatma xati ("reminder") yoki hisob-kitob akti ("confirm"/akt sverki). |
| **Manba** | Debitorlar ro'yxati — oldin olingan hisobotdan client tomonda chiqariladi (`LettersLogic.Debtors`); hujjat yaratish `letters.debts` (`company_id, kind, min_amount, parties[], date, side`) → `ServerFile` (`SonarApi.cs:595-606`). |
| **Mantiq** | `Kind`="reminder"/"confirm", `Side`="receivables"/"payables" (faqat confirm uchun); minimal qarz filtri (`ParseMin`); faqat belgilanganlarni tanlash imkoni. |
| **UI matnlar** | `Description` = *"Har bir qarzdorga alohida bet — bitta Word faylida."*; `NeedSelection` = *"Kamida bitta qarzdorni belgilang"*. |

### 1.8 Payslip/Payroll — xodimlar va hisob varaqalari

| | |
|---|---|
| **Maqsad** | 1C'dagi xodimlar ro'yxati, oylik yig'ma hisob (Month) va har bir xodim uchun bosma hisob varaqasi — hammasi **faqat o'qish**. |
| **Manba** | `payroll.employees`, `payroll.month`, `payroll.payslip` (`company_id, period, employee`), bulk eksport `payroll.payslips_file` (`SonarApi.cs:429-456,586-589`). |
| **Mantiq** | `PayrollLogic.GroupLines` — 4 guruh: accrual/deduction/payment/other; xodim 1C-ref bo'yicha bog'lanadi, topilmasa ism bo'yicha fallback va `"(1C ro'yxatida yo'q)"` belgisi; qidiruv o'zbek apostrof variantlarini normallashtiradi. |
| **UI matnlar** | `Subtitle` = *"1C dagi xodimlar, oylik hisob-kitoblari va hisob varaqalari — Sonar orqali o'qiladi."*; `LinkMissingTitle` = *"Xodim 1C da topilmadi"*. |

### 1.9 Budget — Byudjet (smeta/ijro)

| | |
|---|---|
| **Maqsad** | Byudjet rejasi ("smeta") va haqiqiy xarajat ("ijro") solishtirish, xarajat kodlari bo'yicha. **1C/server bilan aloqasi yo'q — to'liq offline, faqat mahalliy fayl bilan ishlaydi.** |
| **Manba** | Yo'q — faqat lokal fayl tanlash/saqlash (`PickFilesAsync`/`SaveFileAsync`). Hisoblash to'liq `BudgetImport.cs` ichida. |
| **Mantiq** | `.xlsx`/`.csv` (≤10MB) qo'lda yozilgan parser (tashqi kutubxonasiz); Excel formulalarini rad etadi (faqat qiymat), dublikat kodlarni, noaniq ming/o'nlik ajratgichlarni tekshiradi. `Compare()` — plan/actual kod bo'yicha left-join: "Smetada yo'q", "Smetadan oshgan", "Manfiy ijro — tekshiring", "Ijro yo'q", "Mos". Eksport ham qo'lda yozilgan minimal OOXML (`.xlsx`) generatori. |
| **UX** | Alohida `Uz.Budget` matn klassi yo'q — matnlar C# kodiga to'g'ridan-to'g'ri yozilgan (lokalizatsiya bo'yicha boshqa modullardan farqli, texnik qarz belgisi). 300 qatorgacha jadval. |

### 1.10 Reminder — Eslatmalar

| | |
|---|---|
| **Maqsad** | Soliq/hisobot muddatlari uchun qaytariluvchi/bir martalik eslatmalar — Telegram'ga oldindan va o'z kunida keladi. |
| **Manba** | `automation.get` (Reminders/Templates), `automation.reminder_save`, `automation.reminder_delete` (`SonarApi.cs:504-561`). |
| **Mantiq** | Jadval turlari: `monthly` (kun 31 = "oxirgi kun"), `quarterly`, `yearly`, `once`; `Next()` 24 oygacha oldinga qarab hisoblaydi; `Validate` sarlavha 2-120 belgi, oldindan ogohlantirish 0-7 kun. Tayyor shablonlar: QQS hisoboti, Foyda solig'i, Moliyaviy hisobot, Statistika hisoboti, Inventarizatsiya va h.k. (`MockAutomation.cs:97-108`). |
| **UI matnlar** | `Lead` = *"Soliq va hisobot muddatlari — Telegram'da oldindan va o'sha kuni eslatiladi."*; **max 20 ta eslatma** kompaniya uchun (`Uz.Reminders.Max`). |

### 1.11 Report / ReportView — hisobotlar moduli

| | |
|---|---|
| **Maqsad** | AI'siz, to'g'ridan-to'g'ri 1C raqamlarini ko'rish va Excel/Word/PDF'ga saqlash — 10 modulning (ish_haqi va byudjetdan tashqari) umumiy sahifasi. |
| **Manba** | `reports.list`, `reports.run` (`company_id, report, period, refresh`), `reports.file` (eksport) (`SonarApi.cs:458-474`). |
| **Mantiq** | `ReportCatalog` — 21 hisobot kaliti, modul bo'yicha taqsimlangan (masalan `cash`→kassa+bank, `receivables/payables`→hisob_kitob, `stock/low_stock/items`→ombor, `taxes`→soliq+hisobot, `staff/hr_moves/hr_leave`→kadrlar, `production`→tannarx) va modul ichida qattiq tab tartibi. Davr tanlash: joriy / 3 oy. `stock`/`bank_book` hisobotlari ichiga InventoryCompare/BankCompare va qarz xatlari tugmasi joylashgan. |
| **UI matnlar** | *"AI-siz ishlaydi: 1C dagi haqiqiy raqamlarni ko'ring va Excel, Word yoki PDF saqlang. AI limiti sarflanmaydi."* (`ReportsModuleViewModel.cs:58-60`) — mahsulotning asosiy pozitsiyasi: hisobotlar AI kvotasini yemaydi. |

### 1.12 Tariff — tarif/narx

| | |
|---|---|
| **Maqsad** | Yagona tarif — **"Buxgalter tarifi"**: narx, holat, AI limiti, bepul operatsiya qoldig'i ko'rsatiladi, sotib olish Telegram botga yo'naltiriladi. |
| **Manba** | `account.tariff` → `Tariff{Key,Name,Active,Until,Price,Period,Docs,DocsLeft,Ai,Free,BuyUrl,DownloadUrl}` (`SonarApi.cs:117`). |
| **Mantiq** | `TariffState` 10 daqiqada bitta so'raydi, sotib olishdan keyin 15 daqiqa davomida 15 soniyada tezkor tekshiradi (faollashganini tez bilish uchun); `BuyAsync()` doim `t.me/sonar_aibot?start=tarif` ga ochadi — **to'lov butunlay ilova tashqarisida**. Mock'dagi real raqamlar: narx **500 000 so'm/oy**, 39 kunlik sinov, oyiga 30 bepul operatsiya (`MockServer.cs:5416-5446`). |
| **UI matnlar** | `TabLead` = *"Tarif Sonar dasturini ochadi... 7 kun bepul — Sonar botidagi «🎁 7 kun bepul» tugmasi. To'lov — Sonar botida."*; `ChatBlockedTitle` = *"AI yordamchi Buxgalter tarifi bilan ishlaydi"*. |

### 1.13 BusinessShell vs Shell — ikki rejim (buxgalter / biznes egasi)

| | |
|---|---|
| **Maqsad** | Ikkita butunlay boshqa qobiq: **Shell** (to'liq buxgalter ish joyi — modullar, hisobotlar, 1C) va **BusinessShell** (buxgalter bo'lmagan egalar uchun yupqa "tanishtiruv" ekrani). |
| **Qaror zanjiri** | `AppServices.BusinessEnabled`/`AiChatEnabled` — `init`-only bool'lar (`AppServices.cs:36,54`), lekin **`AppHost.Create()`da hech qachon `true`ga o'rnatilmaydi** (`AppHost.cs:66-69`) — butun repo bo'ylab qidiruv hech qayerda `BusinessEnabled = true` topmadi. Natijada `WorkMode.Resolve` doim `"accounting"`ni majburlaydi (`WorkMode.cs:20-35`) — **DirectionChoiceView (biznes/buxgalter tanlash ekrani) va BusinessShell shu build'da amalda o'likdir**, lekin kodda to'liq mavjud. |
| **Farq (kod bo'yicha)** | `ShellViewModel` — to'liq navigatsiya: modullar, hisobotlar, Assistant, Tarix, Automation, Sozlamalar, 1C holati, tarif. `BusinessShellViewModel` — faqat 3 bo'lim: "qanday ishlaydi" (statik `WorkflowCard`lar: hujjatlar/excel/savdo), "manbalar" (AI provayder tanlash), "sozlamalar"; yagona real amal — `OpenBot()` → Telegram botga yo'naltirish. |
| **UI matnlar** | Buxgalter: *"1C bilan ishlaydigan buxgalterlar uchun"*; Biznes (Beta belgisi bilan): *"Biznes vazifalari uchun AI ish joyi. Buxgalteriya va 1C kerak emas."* (`UiLocale.cs:39-42`). |

### 1.14 Assistant — AI chat

| | |
|---|---|
| **Maqsad** | Oddiy tilda savol/vazifa yozish — AI 1C raqamlari bilan javob beradi va o'zgarishlarni tasdiqqa taklif qiladi. **Shuningdek, bu build'da `AiChatEnabled=false` bo'lgani uchun, Assistant sahifasi va Sozlamalar→AI tab o'rniga doim AiApps (MCP) sahifasi ochiladi** (`ShellViewModel.cs:1080-1087`). |
| **Manba** | `chat.usage`, `chat.send` (`company_id, thread_id?, message, files[]`), `chat.cancel`, `chat.upload`/`chat.file`, `chat.threads`/`chat.thread`; mahalliy Claude-obuna rejimi uchun `chat.local_pending/take/reply/fail` (`SonarApi.cs:328-424`). |
| **Nima so'rash mumkin** | Erkin matn (≤4000 belgi) + 5 tagacha fayl (≤10MB, rasm/PDF/Word/Excel). Modulga mos namuna so'rovlar (`ChatTemplates.For`): kassa→PKO/RKO yaratish, hisob_kitob→kontragent yaratish/"kim ko'p qarzdor", savdo→bugungi sotuv, ish_haqi→oylik hisob, ombor→kam qoldiq. |
| **AI amallar** | `ActionKinds.All` = create, update, post, unpost, mark_delete, unmark_delete, fill, delete, close_month — har biri `ActionItem` sifatida chatda karta bo'lib chiqadi va tasdiqni talab qiladi (`actions.approve`/`actions.reject`, hash-himoyali — eskirgan preview rad etiladi). Ko'p-tasdiqli zanjirlar rol darajasi bo'yicha: xodim(0)<buxgalter(1)<bosh_buxgalter(2)<admin(3). |
| **UI matnlar** | `Subtitle` = *"Vazifani oddiy tilda yozing — Sonar AI 1C dagi raqamlar bilan javob beradi, o'zgarishlarni esa tasdiqqa taklif qiladi."*; `StopHint` = *"Vazifani to'xtatish — limitga qaytadi..."* (to'xtatish kvotani qaytaradi). |

### 1.15 Workspace / History / Automation / AiApps / Settings — qisqa

| Bo'lim | Mohiyati |
|---|---|
| **Workspace** | Yuqori darajadagi holat mashinasi: Loading/Error/Choice/Onboarding/Shell/Business (`WorkspaceViewModel.cs`). |
| **History** | `audit.list` orqali hamma amallar jurnali, kun bo'yicha guruhlangan, rolga qarab ko'rinish cheklangan (admin/bosh_buxgalter — hammasi, boshqalar — faqat o'ziniki). |
| **Automation** | 3 tab-xost: Checks/Digest/Reminders (yuqorida). |
| **AiApps (MCP)** | Tashqi AI ilovalar (Claude Desktop, ChatGPT, Cursor, va h.k.) lokal MCP-relay (`SonarMcp.exe`) orqali 1C'ga ulanishi — `account.mcp`/`account.mcp_revoke`. Bu build'da Assistant o'rnini bosuvchi asosiy AI-interfeys. Standart holat — **faqat o'qish** (*"1C ga yozish: o'chiq — AI faqat o'qiydi"*); ulanish ham tarifni talab qiladi. |
| **Settings** | Yo'nalishlar (modul tanlash), 1C ulanish, AI tab (faqat `AiChatEnabled` yoqilganda), Tarif, ilova haqida/ko'rinish/xodimlar/ish turi. |
| **Onboarding** | Yakka (solo) foydalanuvchilar uchun — kamida 1 modul tanlab `company.create(..., "yakka", modules)` chaqiradi. |
| **Login/Consent** | Parolsiz — Telegram QR/kod orqali kirish; foydalanish shartlari versiyasi (`2026-10-04`) qabul qilinmaguncha ish maydoni ochilmaydi. |

---

## 2. Server API — to'liq katalog

### 2.1 Asosiy transport

- **Bazaviy manzil**: `https://sonar.shaxzoddev.uz/api/v1.php` (standart/fallback, `AppSettings.cs:5`, `SettingsLogic.cs:15`). REST emas — **bitta endpoint**, har chaqiriq `?a=<action>` bilan POST (`HttpTransport.cs:70-82`).
- **Sozlanuvchanlik**: Sozlamalar→Ulanish tabida o'zgartirilishi mumkin, `settings.json`da saqlanadi (`%APPDATA%\Sonar`); faqat `https://` qabul qilinadi, `http://` faqat localhost uchun (`SettingsLogic.cs:60-83`). Alohida staging/prod belgisi yo'q, lekin **Mock rejimi** bor (`SONAR_MOCK=1` yoki sozlamada) — shunda butun chaqiriqlar jarayon ichidagi `MockTransport`ga yo'naladi (`AppHost.cs:47`, `SwitchingTransport.cs`).
- **Timeout**: odatiy 15s, fayl amallari (yuklash/eksport) uchun 3 daqiqa; javob hajmi cheklovi 10MB (16MB fayl amallari uchun) (`HttpTransport.cs:17-23,113-138`).
- **Serializatsiya**: `snake_case` maydon nomlari, null maydonlar yozilmaydi, `LenientStringConverter` — serverdan raqam/bool kelsa ham string maydonga moslab oladi (zaif tipli PHP backendga qarshi himoya) (`ApiJson.cs:10-20`, `LenientStringConverter.cs`).

### 2.2 Autentifikatsiya va qurilma

Parolsiz, Telegram-bot orqali QR/kod bilan kirish:

1. `auth.start` — `{device:{name,os,app_version}}` → `AuthStart{LoginId,Code,PollSecret,ExpiresAt,BotLink}` (`SonarApi.cs:92-95`).
2. `auth.poll` — har 2 soniyada, `{login_id, poll_secret}` → `AuthPoll{Status,Token?,User?}` (`SonarApi.cs:97-100`).
3. Tasdiqlangach token `Session.Accept()` orqali saqlanadi — Windows'da **DPAPI** (`%APPDATA%\Sonar\session.bin`), macOS'da **Keychain** (`DpapiTokenStore.cs`, `KeychainTokenStore.cs`).
4. Har so'rovda token **ikki marta** yuboriladi: `Authorization: Bearer <token>` **va** `X-Sonar-Token: <token>` header (`HttpTransport.cs:108-112`).
5. `auth.logout` — tokensiz ham ruxsat etiladi.
6. Qurilma identifikatori — faqat `Name` (Windows kompyuter nomi), `Os` (`"Windows 11 (22631)"` kabi qo'pol satr), `AppVersion` (`DeviceInfo.cs`). **Apparat barmoq izi (MAC/disk/CPU seriyasi) yig'ilmaydi** — haqiqiy identifikatsiya server bergan sessiya tokeni orqali.
7. Connector (1C agenti) uchun alohida juftlash: `connector.pair_code` → 8-belgili kod, `connectors.mine` — ulangan connectorlar ro'yxati.

### 2.3 Endpointlar jadvali (guruhlangan)

| Guruh | Action | So'rov | Javob |
|---|---|---|---|
| **Foydalanuvchi** | `me` | `{}` | `MeResult{User, Company[], Tariff?}` |
| **Hisob** | `account.tariff`, `account.mcp`, `account.mcp_revoke`, `account.consent` | — | `Tariff`, `McpInfo`, `McpApp[]`, — |
| **Kompaniya** | `company.create`, `company.dashboard`, `company.update`, `company.settings`, `company.bases`, `company.set_base`, `company.ai`, `company.ai_set`, `company.ai_test` | `company_id,...` | `Company`, `Dashboard`, `CompanySettings`, `OneCBase[]`, `CompanyAi` |
| **A'zolar** *(DTO bor, UI dan chaqirilmaydi — "Jamoa" ekrani hali ulanmagan)* | `members.list/invite/update/remove` | `company_id,...` | `Member[]`, `Invite`, `Member` |
| **1C/Connector** | `onec.connect_error`, `onec.profile`, `connector.pair_code`, `connectors.mine` | — | — , raw JSON, `PairCode`, `ConnectorInfo[]` |
| **Chat/AI** | `chat.usage`, `chat.send`, `chat.cancel`, `chat.upload`, `chat.file`, `chat.threads`, `chat.thread`, `chat.local_pending/take/reply/fail` | `company_id, thread_id?, message, files[]` | `ChatUsage`, `ChatSendResult`, `ChatFile`, `ChatThread[]`, `ChatThreadResult` |
| **Hisobotlar** | `reports.list`, `reports.run`, `reports.file` | `company_id, report, period?, refresh?` | `ReportInfo[]`, `ReportRunResult`, `ReportFile` |
| **Avtomatlashtirish** | `automation.get`, `automation.digest_set`, `automation.digest_test`, `automation.reminder_save/delete` | `company_id,...` | `AutomationInfo`, `Digest`, bool, `Reminder` |
| **Oylik (Payroll)** | `payroll.employees`, `payroll.month`, `payroll.payslip`, `payroll.payslips_file` | `company_id, period?, employee?` | `PayrollEmployeesResult`, `PayrollMonthResult`, `PayrollPayslipResult`, `ServerFile` |
| **Audit** | `audit.list` | `company_id, before_id?` | `AuditPage{AuditItem[], NextBeforeId?}` |
| **Modullar** | `modules` | `{}` | `ModuleInfo[]` |
| **Tekshiruv** | `checks.run`, `checks.file` | `company_id, refresh?` | `ChecksResult`, `ServerFile` |
| **Solishtirish** | `bank.compare`, `inventory.compare` | `company_id, name, data(base64),...` | `BankCompareResult`, `InventoryCompareResult` |
| **Amallar/Ishlar** | `jobs.list` *(ulanmagan)*, `jobs.get`, `actions.list`, `actions.approve`, `actions.reject`, `actions.preview` *(ulanmagan)*, `actions.get` | `job_id`/`action_id,...` | `Job[]`, `JobDetails`, `ActionItem[]`, `ActionItem` |
| **Kurslar** | `rates.today` | `{}` | `RatesResult{Date, CurrencyRate[]}` |
| **Xatlar** | `letters.debts` | `company_id, kind, min_amount?, parties?, date?, side?` | `ServerFile` |

*(To'liq request/response maydonlari, fayl:qator havolalari — `SonarApi.cs:92-616`.)*

### 2.4 Envelope / Xatolar / Qayta urinish

- **Muvaffaqiyat**: `{"ok":true, ...}`; **xato**: `{"ok":false,"error":{"code","message"}}` — `Envelope.Parse`, `Envelope.cs:9-77`.
- **Xato kodlari** (HTTP status → kod): `400 bad_request, 401 unauthorized, 402 tariff_required, 403 forbidden, 404 not_found, 409 conflict, 413 too_large, 422 invalid, 429 rate_limited, 500 server_error, 501 not_implemented`; mijoz-mahalliy kodlar: `free_limit, network, timeout, bad_response` (`ApiErrors.cs:7-52`). Barcha kodlar o'zbek tilidagi tayyor xabarga ega.
- **`ApiException.Transient`** — faqat `network`/`timeout`/5xx va 429 (lekin `free_limit`/`ai_limit` bundan mustasno — **kvota tugashi qayta urinib bo'lmaydigan xato deb hisoblanadi**) (`ApiException.cs:87-111`).
- **Qayta urinish** — transport darajasida avtomatik retry yo'q; har bir ekran o'zi vaqt-asosli pollingni boshqaradi (login — 2s, job — 10s, action/preview — moslashuvchan interval, payroll/report — "loading/refreshing" holatida tezlashtirilgan poll).

---

## 3. Biznes model — tariflar, limitlar, rollar

| Jihat | Tafsilot |
|---|---|
| **Tarif** | Yagona reja — **"Buxgalter"**, narx **500 000 so'm/oy** (demo ma'lumotda), `BuyUrl` doim Telegram botga (`t.me/sonar_aibot?start=tarif`) — **to'lov ilova ichida emas**. |
| **Sinov muddati** | 39 kunlik trial (mock'da `AddDays(39)`), shuningdek "7 kun bepul" UI xabarlari ham ko'rinadi — ikki xil sinov matni bor ekan, bu tarif variantlari (yoki eski/yangi matn) orasidagi nomuvofiqlik bo'lishi mumkin. |
| **Bepul operatsiyalar (Free)** | Oyiga **30 operatsiya**, tarif faol bo'lmaganda ishlatiladi; `TariffFree{Limit,Used,Remaining,ResetsAt}`; amal xato bersa kvota qaytariladi. |
| **AI chat limiti** | Haftalik+oylik kvotalar (`TariffAi{Week,Month}`, `ChatUsage{Weekly,Monthly,Available,NextAvailableAt,Reason}`); `Mode="own_key"`/`"connector"` (o'z API kaliti yoki mahalliy Claude obunasi) tanlansa — Sonar kvotasi **umuman sarflanmaydi**. Vazifani to'xtatish ishlatilgan kvotani qaytaradi. |
| **Modul tizimi** | 12 modul kaliti: `ish_haqi, kadrlar, kassa, bank, hisob_kitob, savdo, ombor, asosiy_vosita, tannarx, soliq, hisobot, byudjet`. Uch bosqichli qaror: ruxsat yo'q→"biriktirilmagan"; ruxsat bor-lekin tayyor emas→"tez kunda"; tayyor→haqiqiy sahifa. `byudjet` doim majburan "tayyor" qilib ko'rsatiladi (server holatidan qat'i nazar) — mahalliy feature-flag. |
| **Ko'p kompaniya** | `MeResult.Companies` ro'yxati — bir foydalanuvchi bir nechta kompaniya (shu jumladan "autsorsing mijoz" turdagi, yozish o'chirilgan) bilan ishlashi mumkin. |
| **Rollar** | Qattiq ierarxiya: `xodim`(0) < `buxgalter`(1) < `bosh_buxgalter`(2) < `admin`(3). `admin`/`bosh_buxgalter` — hamma modul; `buxgalter` — faqat biriktirilgan modullar; `xodim` — desktop/API orqali hech narsa ko'rmaydi (faqat Telegram bot). Yakka (solo) rejimda hatto admin ham faqat o'zi tanlagan modullarga cheklanadi. |
| **Taklif (Invite)** | `members.invite/update/remove/list` DTOlari mavjud, lekin **bu build'da hech bir ViewModel ulamagan** — "Jamoa" boshqaruv ekrani kodda yo'q (yoki hali tayyor emas). |
| **Ikki tasdiq (second approval)** | `CompanySettings.SecondApproval` — tanlangan amal turlari (masalan `post`, `mark_delete`) uchun 2 tasdiq (bosh_buxgalter VA buxgalter) talab qilinadi; rol-darajasi bo'yicha moslashtirish (yuqori rol pastroq talabni qoplaydi). Tasdiq faqat joriy preview hash'iga mos bo'lsa va 1 soatdan oshmagan bo'lsa amal qiladi; 1C'ga yuborishdan oldin 24 soatdan keyin eskirgan tasdiq bekor qilinadi. |
| **Yozish ruxsati** | `CompanySettings.WriteEnabled` — standart holatda ko'p joyda o'chiq; faqat `connector` turidagi baza (OData emas) va holati "active" bo'lsa yozish mumkin. |

---

## 4. Logic va Mock papkalari — nima ochiladi

### 4.1 `Sonar.Desktop.Core.Logic` (68 fayl)

Bu — taqdimot qatlami, lekin bir qator fayllar haqiqiy biznes qoidalarini ochadi:

- **`Permissions.cs`** — yuqoridagi rol/modul qoidalarining mijoz tomoni aynan nusxasi.
- **`ApprovalsLogic.cs`** — serverdagi (mock) bilan **bir xil** rang-darajali tasdiq moslashtirish algoritmi — demak, bu mantiq server va mijozda ikki marta yozilgan (duplikatsiya).
- **`WorkMode.cs`** — `businessEnabled=false` bo'lsa, rejim doim `"accounting"`ga majburlanadi (yuqorida 1.13-bandda).
- **`TariffLogic.cs`** — `Free.Limit==0` bo'lsa "7 kun bepul" degan boshqa turdagi tarif xabari chiqadi — demak kelajakda "bepul operatsiyasiz, faqat trial" tarif varianti rejalashtirilgan bo'lishi mumkin.
- **`Legal.cs`** — foydalanish shartlari versiyasi `"2026-10-04"` qattiq yozilgan, mock serverdagi bilan bir xil bo'lishi shart.
- **`ChecksLogic.Visible()`** — eski/yangi natijani `Key` bo'yicha birlashtirib, UI "miltillashini" oldini oladi — puxta UX yechimi.
- **`BudgetImport.cs`** (614 qator, eng katta fayl) — tashqi kutubxonasiz, qo'lda yozilgan XLSX/CSV o'qish-yozish (zip+XML darajasida), formulalarni rad etish, ikki tilli (uz/ru) sarlavha moslashtiruvi.
- **`KpiLogic.Extract`** — 1C hisoblar rejasi kodlarini (50/51/52/55 va h.k.) bilimini mijoz kodiga joylashtirgan.
- **`SettingsLogic.cs`** — faqat `https://` manzil qabul qiladi (localhost'dan tashqari); INN'ni 9 (STIR) yoki 14 (JShShIR) raqam sifatida tekshiradi.

### 4.2 `Sonar.Desktop.Core.Mock` (MockServer.cs, MockSeed.cs) — "server naqshasi"

Mock qatlami butun server data modelini ochib beradi (chunki u haqiqiy backend o'rniga ishlaydi):

- **Obyektlar**: User/Member/Company (kind=`firma`|`yakka`), Base/Connector (1C ulanishi), Thread/ChatMessage (AI), Action/Job/Step/Approval/Audit (AI→1C yozish oqimi), Payroll/Reports/Bank/Checks, McpApp.
- **Simulyatsiya ma'lumoti**: namuna kompaniya **"Namuna Savdo MChJ"** (INN 305123456, 1C konfiguratsiyasi — *"Бухгалтерия для Узбекистана, ред. 3.0"* — mahsulot aynan shu konfiguratsiyaga mo'ljallangan, umumiy 1C emas), 4 xodim (oylik 4.1-8.0 mln so'm), bank **"Kapitalbank"**.
- **Qoidalar**: 30/soat tekshiruv yangilash, 10/soat digest-test/AI-kalit tekshirish/juftlash kodi, 30/soat chat yuborish, 60/soat yuklash; fayl ≤10MB (chat)/≤5MB (bank/ombor solishtirish), max 5 fayl/xabar; audit ko'rinishi rolga bog'liq.
- **Simulyatsiya kechikishlari** — preview 3s, navbatga 3s, bajarilish 9s (baza online) / 20s timeout (offline) — haqiqiy 1C round-trip kechikishini taqlid qiladi.
- **AI provayderlar** (mock): `openai` ("GPT-6 Luna/Sol"), `claude` ("Claude Opus 5/Sonnet 5"), `gemini` (4 model), `claude_cli` (lokal Claude Code obunasi, "sonnet"/"opus") — bular aniq placeholder nomlar (ilovaning ichki "2026" sanasiga mos), haqiqiy model ID'lari emas.

### 4.3 `DemoSession.cs` (`Sonar.Core/Sonar.Core/`) — 1C ning o'zini simulyatsiya qilish

Bu alohida, pastroq darajadagi demo — `IOneCSession`/`IObjectAccess` interfeysini amalga oshirib, **1C COM/OData obyekt modelining o'zini** qalbakilashtiradi (katalog/hujjat/buxgalterlik yozuvlari Dt/Kt hisoblar bilan). ~120 kunlik realistik O'zbekiston savdo-kompaniyasi ma'lumotini generatsiya qiladi: hisoblar rejasi (2900 Tovarlar, 4000/6000 debitor/kreditor, 5000/5100 kassa/bank, 8300 kapital, 9000/9100 daromad/tannarx, OS 0100-0260, soliq 6400, ish haqi 6700/6900, ishlab chiqarish 1000-2800), savdo/xarid hujjatlari, ish haqi, asosiy vositalar amortizatsiyasi, va non-pishiriqxona ishlab chiqarishi (masalan "Patir non", "Pechenye «Sonar»"). Demak, demo rejimi **ikki qatlamda** ishlaydi: (1) `Mock` — Sonar SaaS backend'ini, (2) `DemoSession` — 1C bazasining o'zini taqlid qiladi — ikkisi birga butun ilovani infratuzilmasiz ishlatishga imkon beradi.

---

## 5. Yangilanish mexanizmi va telemetriya

### 5.1 Avtomatik yangilanish

- **Tekshirish**: ishga tushgandan 1 daqiqadan keyin, keyin har 6 soatda (`AppUpdater.cs:27-29`); faqat Windows'da (`UpdateService.cs:56`).
- **Manzil**: API manzilidan hisoblanadi — `{apiBase}/../app/version.json` → amalda `https://sonar.shaxzoddev.uz/app/version.json` (`UpdateService.cs:67-82`).
- **Tasdiqlash**: manifest **RSA imzo** bilan tekshiriladi (qattiq yozilgan public kalit, `UpdateOptions.cs:10-12`); yuklangan `.exe` **SHA-256** xeshi manifestdagi bilan mos kelishi shart — ikkisidan biri mos kelmasa, o'rnatish rad etiladi (*"yangilanish imzosi tasdiqlanmadi — o'rnatilmaydi"*).
- **O'rnatish**: `/S /restart` bilan jim o'rnatish; agar ilova oyna ko'rinmas holatda bo'lsa — **so'rovsiz avtomatik** o'rnatiladi; ko'rinadigan bo'lsa — foydalanuvchi "Tekshirish"/"O'rnatish" tugmasini bosishi kerak.
- Yagona kanal (beta/stable ajratish yo'q); xatolar o'zbek tilida tushuntiriladi.

### 5.2 Loglash va maxfiylik

- **Yagona logger**: `FileLog.cs` — mahalliy matn fayllarga yozadi (`%LOCALAPPDATA%\SonarConnector\logs\{prefix}-yyyyMMdd.log`), 7 kundan keyin avtomatik tozalanadi, so'nggi 400 qator xotirada saqlanadi (UI log ko'rish uchun).
- **Masking**: `Secrets.cs` har qator yozilishidan oldin 1C ulanish parollari, `Bearer` token, `token/password/secret` JSON maydonlari va ilovaning o'z sessiya-token formatini **majburiy** maskalaydi; o'chirish sozlamasi yo'q.
- **Nima yuboriladi serverga**: Sentry/Application Insights/Crash-reporter kabi **hech qanday alohida telemetriya tizimi topilmadi**. Butun repoda chiquvchi HTTP so'rovlar faqat: (a) Sonar API, (b) yangilanish manifesti/fayli, (c) O'zbekiston MB valyuta kursi feed'i (`cbu.uz`), (d) Telegram deep-link'lar. **Log fayllari yoki xato hisobotlari serverga yuklanmaydi** — loglash to'liq mahalliy.
- **Log tarkibi** (bir nechta fayl bo'yicha tanlab tekshirildi, to'liq audit emas): faqat boshqaruv-darajasidagi xabarlar — connector holati, 1C baza nomi/ulanish tasviri (parolsiz), hisob nomi, AI vazifa ID/davomiyligi/xato kodi. **Chat matni yoki 1C qator-darajasidagi buxgalteriya ma'lumoti log'da uchramaydi** (topilgan namunalar bo'yicha).

---

## Bozor va raqobat nuqtai nazaridan xulosa

**Sonar nimada kuchli:**
1. **Aniq tor nisha** — faqat O'zbekiston "1C: Buxgalteriya 3.0" konfiguratsiyasi ustida, umumiy "har qanday ERP" emas. Bu chuqur integratsiya (hisob kodlari, Dt/Kt, soliq hisobotlari) imkonini beradi.
2. **Xavfsiz yozish modeli** — AI hech qachon to'g'ridan-to'g'ri 1C'ga yozmaydi: preview → hash-himoyali tasdiq → rolga bog'liq ikki-tasdiq qoidasi → 24 soatlik eskirish nazorati → optimistik concurrency ("1C da o'zgargan — yozilmadi"). Bu kompetitorlar ko'pincha e'tiborsiz qoldiradigan jiddiy muhandislik.
3. **AI'siz ham ishlaydigan "zaxira qatlam"** — Report/Checks/BankCompare/InventoryCompare moduli AI kvotasini sarflamaydi; mahsulot faqat "chat ustiga qurilgan wrapper" emas.
4. **Telegram-markazli UX** — login, digest, eslatmalar, to'lov — hammasi joriy O'zbek foydalanuvchi odatiga mos (Telegram deyarli har kimda bor, alohida mobil ilova shart emas).
5. **Yangilanish xavfsizligi** — RSA imzo + SHA-256 — o'rta hajmdagi SaaS uchun yetarlicha puxta.
6. **Maxfiylik** — loglash mahalliy, maskalangan, chat/1C tarkibi serverga alohida telemetriya sifatida yuborilmaydi (kuzatilgan namunalarda).

**Zaif/tugallanmagan joylar:**
1. **Business-shell va to'liq Assistant chat — amalda o'chiq** (`BusinessEnabled`/`AiChatEnabled` hech qayerda `true`ga o'rnatilmagan) — reklama qilingan "ikki rejim" aslida bitta rejim bo'lib qolmoqda, bu versiyada.
2. **"Jamoa" boshqaruvi yo'q** — `members.invite/update/remove` API'si bor, lekin UI ulamagan — ko'p-foydalanuvchili kompaniyalarni real boshqarish imkoni hali ekranda yo'q.
3. **Payroll yozish yo'q** — "oylik hisoblash 1C'da" hali faqat o'qish, yozish keyingi bosqichga qoldirilgan — to'liq avtomatlashtirish vadasi hali bajarilmagan.
4. **To'lov oqimi uzilgan** — ilova ichida karta/billing yo'q, hammasi Telegram botga chiqarilgan — bu konversiyani pasaytiradi va enterprise mijozlar uchun noqulay (shartnoma/hisob-faktura yo'q ko'rinadi).
5. **Yagona backend endpoint, versiyalanmagan API** — `v1.php` nomigagina versiya, haqiqiy versiyalash yo'q — kelajakda breaking change qilish qiyinroq bo'ladi.
6. **Budget modulida lokalizatsiya texnik qarzi** — matnlar kodga qotirilgan, boshqa modullardagi markazlashgan `Uz.*` tizimidan chetga chiqilgan.
7. **Tarif tizimi juda sodda** — bitta tarif, narxi qattiq yozilgan mock'da; ko'p bosqichli (masalan xodim soniga qarab) narxlash yo'q — o'sish bilan moslashish qiyin bo'lishi mumkin.

**AI + 1C raqobatchisi bo'lish uchun nima kerak** (ERP loyihasi nuqtai-nazaridan; ERP'ga 1C integratsiyasi qo'shiladi — 2026-10-15 asoschi qarori):
- Sonar 1C ustiga **qoplama** (overlay) sifatida ishlaydi — mijoz hali 1C litsenziyasini ham to'laydi. Sizning "noldan ERP" strategiyangiz (Python/FastAPI, FIFO+AVECO) bu qo'shimcha litsenziya xarajatini olib tashlaydi — bu **tuzilma jihatidan ustunlik**, chunki Sonar hech qachon 1C'ni almashtirmaydi, faqat "aqlli qatlam" qo'shadi.
- Lekin Sonar'ning kuchli tomonlarini takrorlash kerak: (a) har qanday AI yozishni **preview+tasdiq+hash** bilan himoyalash (soliq integratsiyasi uchun bu ayniqsa muhim — noto'g'ri yozilgan soliq hujjati jarima keltiradi); (b) Checks-kabi qoidabozor tekshiruv modulini **AI'siz** ham ishlaydigan qilib qurish (ishonch va tezlik uchun); (c) Telegram-birinchi UX'ni saqlab qolish (O'zbekiston bozori uchun to'g'ri tanlov); (d) rol/tasdiq ierarxiyasini boshidanoq loyihalash (xodim/buxgalter/bosh buxgalter/admin), Sonar buni keyin qo'shmagan, boshidan qurgan.
- Ustunlik olish nuqtalari: to'liq ichki billing (Telegram'ga chiqarmasdan), real jamoa/invite boshqaruvi (Sonar'da hali yo'q), yozish qobiliyatli payroll (Sonar'da hali o'qish-only), va versiyalangan, hujjatlashtirilgan ochiq API (Sonar'da yo'q) — bular B2B/korporativ mijozlar uchun hal qiluvchi farq bo'ladi.
