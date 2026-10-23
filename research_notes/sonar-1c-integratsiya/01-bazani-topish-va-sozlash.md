# Sonar AI v1.1.5 — 1C bazasini topish va sozlash: foydalanuvchi tajribasi (code study)

> Manba: `E:/Project/sonar/decompiled/` (decompiled C#/.NET/Avalonia kodi). Barcha havolalar fayl:qator ko'rinishida. Kod ikki marta uchraydi — ildizda (`Sonar.Core/`, `Sonar.Engine/`, `Sonar.Installer/`, `Sonar.Connector/`) va `src_app/` ichida (`src_app/Sonar.Engine/Sonar.Engine/...`, `src_app/Sonar.Core/Sonar.Core/...`, `src_app/Sonar/...`, `src_app/Sonar.Desktop.Core/...`). Ikkisi deyarli bir xil (diff — farqsiz); tahlilda asosan `src_app/` versiyasidan (haqiqiy desktop build) iqtibos keltirilgan, chunki u dastur sborkasida ishlatiladigan haqiqiy daraxt; ildizdagi versiyalar esa bitimlar tarixida saqlanib qolgan nusxalar.

---

## 0. Umumiy arxitektura (keyingi bo'limlarni tushunish uchun zarur)

Sonar bir nechta jarayondan iborat:

- **`Sonar.exe`** — Avalonia desktop GUI. O'z ichida **`ConnectorEngine`** (`Sonar.Engine/Sonar.Engine/ConnectorEngine.cs`) degan sinfni **in-process** ishga tushiradi — bu "Connector"/"Engine" deb ataladigan narsa aslida alohida servis emas, bitta `.exe` ichidagi background komponent (`WindowsEngineHost` — `src_app/Sonar/Sonar.Desktop.Services/WindowsEngineHost.cs:26-37`).
- **`ConnectorEngine`** ichida **`Agent`** (`Sonar.Core/Agent.cs`) server bilan hello/poll tsiklini yuritadi, **`OneCExecutor`** (`Sonar.Engine/OneCExecutor.cs`) esa haqiqiy 1C-ulanishlarni boshqaradi.
- 1C bilan COM orqali gaplashish **alohida process**da — `SonarWorker32.exe` / `SonarWorker64.exe` (`payload/workers/`). `OneCExecutor` ularni stdin/stdout JSON-protokol orqali boshqaradi (`Sonar.Engine/WorkerHost.cs`). Bitlik muammosi (32/64-bit COM) shu tufayli alohida process bilan izolyatsiya qilingan.
- **`SonarMcp.exe`** (`payload/mcp/`) — MCP (Model Context Protocol) relay; Desktop ichidagi named-pipe serverga ulanadi (`ConnectorHost.cs` — `McpPipeHost`), ya'ni tashqi AI klient (Claude Desktop kabi) Sonar orqali 1C ma'lumotiga murojaat qila oladi.
- **`uninstall.exe`** / **`Sonar.Installer`** — o'rnatish/o'chirish.

---

## 1. 1C bazalarini kompyuterdan topish (discovery)

### 1.1 Qayerdan o'qiladi

`IbasesParser.LoadForCurrentUser()` (`Sonar.Core/IbasesParser.cs:67-113`):

1. Asosiy fayl — joriy foydalanuvchining 1C ro'yxati:
   `%APPDATA%\1C\1CEStart\ibases.v8i`
   ```csharp
   string path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "1C", "1CEStart");
   List<string> list2 = new List<string> { Path.Combine(path, "ibases.v8i") };
   ```
   (`IbasesParser.cs:71-72`)
2. Qo'shimcha ravishda `%APPDATA%\1C\1CEStart\1CEStart.cfg` o'qiladi va undan `CommonInfoBases=` qatorlari qidiriladi — bu "umumiy ro'yxatlar" (`CommonInfoBases`) yo'llarini beradi, ular ham parse qilinadi (`IbasesParser.cs:75-87`):
   ```csharp
   if (text.StartsWith("CommonInfoBases=", StringComparison.OrdinalIgnoreCase))
       list2.Add(text.Substring("CommonInfoBases=".Length).Trim());
   ```
   Bu — 1C:Enterprise'ning "umumiy ma'lumotlar bazalari ro'yxati" mexanizmi (bir nechta foydalanuvchi bitta sentralizatsiyalashgan `.v8i` faylni ulashishi mumkin bo'lgan holat).
3. Har bir fayl mavjudligi tekshiriladi (`File.Exists`), bo'lmasa — `try/catch` ichida sekin o'tkazib yuboriladi (xatolik umuman ko'tarilmaydi, ro'yxat shunchaki bo'sh qoladi).

Diqqat: kod **faqat joriy foydalanuvchining** `%APPDATA%`sini ko'radi — `ProgramData`-dagi umumiy (`all-users`) ro'yxat yoki boshqa foydalanuvchining `ibases.v8i`si qidirilmaydi. Agar bir nechta Windows-foydalanuvchi bir xil kompyuterda ishlasa, har biri faqat o'zining 1C ro'yxatini ko'radi (Sonar odatda bitta Windows-foydalanuvchi ostida xizmat sifatida ishlaydi — muammosi yo'q, lekin cheklov sifatida yozib qo'yish kerak).

### 1.2 `ibases.v8i` formati va parser

Format — klassik Windows-INI'ga o'xshash, lekin 1C'ning o'z qoidalari bilan: har bir baza `[Nomi]` sarlavhasi bilan boshlanadi, undan keyin `key=value` qatorlari keladi.

`IbasesParser.Parse(string text)` (`Sonar.Core/IbasesParser.cs:10-65`):

```csharp
string[] array = text.Replace("\r\n", "\n").Split('\n');
...
if (text2.StartsWith("[") && text2.EndsWith("]"))
{
    ibaseEntry = new IbaseEntry { Name = text2.Substring(1, text2.Length - 2).Trim() };
    list.Add(ibaseEntry);
}
else
{
    int num = text2.IndexOf('=');
    string key = text2.Substring(0, num).Trim();
    string val = text2.Substring(num + 1).Trim();
    switch (key.ToLowerInvariant())
    {
        case "connect": ibaseEntry.Connect = val; break;
        case "id": ibaseEntry.Id = val; break;
        case "folder": ibaseEntry.Folder = val; break;
        case "version": ibaseEntry.Version = val; break;
    }
}
```

Muhim detallar:
- `;` bilan boshlangan qatorlar izoh sifatida o'tkazib yuboriladi (`text2.StartsWith(";")` — `IbasesParser.cs:22`).
- Bo'sh qatorlar o'tkazib yuboriladi.
- BOM (`\ufeff`) har bir qatordan tozalanadi (`TrimStart('\ufeff')` — `IbasesParser.cs:21`) — bu shuni ko'rsatadiki, fayl ba'zan UTF-16/UTF-8 BOM bilan kelishi kutilgan.
- Faylni o'qish `ReadText()` (`IbasesParser.cs:115-127`) orqali — UTF-16LE BOM (`0xFF 0xFE`), UTF-8 BOM (`0xEF 0xBB 0xBF`) yoki oddiy UTF-8 avtomatik aniqlanadi. Bu 1C'ning turli versiyalari faylni turli kodlashda yozishi mumkinligini hisobga oladi.
- Parser faqat 4 ta kalitni biladi: `connect`, `id`, `folder`, `version` — boshqa har qanday noma'lum kalit (masalan `OSAuthentication` yoki minglab 1C'ning real atributlari) jim o'tkazib yuboriladi.
- Oxirida: `list.RemoveAll(e => string.IsNullOrEmpty(e.Connect))` (`IbasesParser.cs:63`) — `Connect` maydoni bo'sh bo'lgan yozuvlar (masalan, sof papka-guruh belgisi, ulanish satrisiz) chiqarib tashlanadi.

### 1.3 `IbaseEntry` tuzilmasi

```csharp
// Sonar.Core/IbaseEntry.cs:3-21
public sealed class IbaseEntry {
    public string Name;      // [Nomi] sarlavhasidan
    public string Connect;   // "File=...;" yoki "Srvr=...;Ref=...;"
    public string Id;        // 1C bazaning ichki GUID'i (ishlatilmaydi deyarli)
    public string Folder;    // guruh/papka yo'li
    public string Version;   // oxirgi marta ishlatilgan platforma versiyasi
    public string Kind => OneCConnect.KindOf(Connect); // "file"/"server"/"web"/"unknown"
}
```

`Folder` maydoni **tekis satr** sifatida saqlanadi — bu 1C'ning ichki "guruh yo'li" formati (masalan `"Mening bazalarim\Savdo"`), lekin Sonar bu yerda hech qanday **daraxt** qurmaydi — guruhlash/ichma-ich papkalar logikasi butunlay **e'tiborga olinmaydi**. Yagona ishlatilishi — `LocalIbase.Folder` orqali oddiy matn sifatida ko'rsatish (pastga qarang).

### 1.4 `LocalIbase` — normallashtirilgan, "tozalangan" ko'rinish

```csharp
// Sonar.Core/LocalIbase.cs
public sealed class LocalIbase {
    public string Name = "";
    public string Connect = "";
    public string Folder = "";
}
```

`LocalIbase` — `IbaseEntry`dan farqli, **UI'ga ko'rsatish uchun** tozalangan DTO. Uni `ConnectorEngine.LocalIbases()` quradi (`src_app/Sonar.Engine/Sonar.Engine/ConnectorEngine.cs:1218-1251`):

```csharp
foreach (IbaseEntry item in IbasesParser.LoadForCurrentUser())
{
    string connect;
    try { connect = NormalizeConnect(item.Connect); }
    catch (ArgumentException) { continue; }   // filtr: faqat file/server
    list.Add(new LocalIbase { Name = item.Name ?? "", Connect = connect, Folder = item.Folder ?? "" });
}
```

`NormalizeConnect` (`ConnectorEngine.cs:1253-1265`) — **filtr va standartlashtirish**:

```csharp
internal static string NormalizeConnect(string connect)
{
    var dict = OneCConnect.ParseParams(connect ?? "");
    if (dict.TryGetValue("File", out var f) && f.Trim() != "") return OneCConnect.FileConnect(f.Trim());
    if (dict.TryGetValue("Srvr", out var s) && dict.TryGetValue("Ref", out var r) && s.Trim()!="" && r.Trim()!="")
        return OneCConnect.ServerConnect(s.Trim(), r.Trim());
    throw new ArgumentException("Faqat fayl yoki server bazasi qo'llanadi: File=\"…\"; yoki Srvr=\"…\";Ref=\"…\";");
}
```

Demak, **filtrlar**:
- Faqat **fayl (`File=`)** yoki **klient-server (`Srvr=`+`Ref=`)** bazalar qoldiriladi.
- **Veb (`ws=`)** bazalar chiqarib tashlanadi — COM-connector veb-servisga ulanolmaydi, shuning uchun ro'yxatdan chetlatiladi (xato bosilmaydi — shunchaki `continue`).
- Noto'g'ri/bo'sh ulanish satrlari o'tkazib yuboriladi.
- Platforma emas (`!Platform.IsWindows`) bo'lsa, butun ro'yxat bo'sh qaytadi (`ConnectorEngine.cs:1220-1223`) — chunki COM faqat Windows'da ishlaydi.

### 1.5 `OneCConnect` — ulanish satrini parse/qurish

`Sonar.Core/OneCConnect.cs` — 1C ulanish satrini (`File=...;Usr=...;Pwd=...;`) `key="quoted value";` formatida parse qiladigan mini-parser (`ParseParams`, `OneCConnect.cs:9-64`) — qo'shtirnoq ichidagi `""`-escaping'ni ham to'g'ri uqiydi. `KindOf()` (`OneCConnect.cs:66-82`) ulanish turini aniqlaydi: `File` kaliti bor bo'lsa `"file"`, `Srvr` bo'lsa `"server"`, `ws` bo'lsa `"web"`, aks holda `"unknown"`.

### 1.6 Dubllarni olib tashlash

`IbasesParser.LoadForCurrentUser()` da `HashSet<string> hashSet` orqali **`Connect`-satr bo'yicha** dublikatlar olib tashlanadi (`IbasesParser.cs:70, 102`):
```csharp
if (hashSet.Add(item2.Connect)) list.Add(item2);
```
Ya'ni, agar bitta baza ham shaxsiy `ibases.v8i`da, ham umumiy `CommonInfoBases` faylda bo'lsa — faqat birinchi uchragani qoladi.

### 1.7 "Allaqachon qo'shilgan baza bilan solishtirish" — bu faylarda emas

Bu fayllarda hech qanday solishtirish/mapping logikasi yo'q. Diqqat: solishtirish **UI darajasida** (`EngineBaseDialogViewModel`) sodir bo'ladi — foydalanuvchi ro'yxatdan bazani tanlab, uni **yangi `BaseConfig` yozuvi** sifatida saqlaydi. Agar foydalanuvchi bir xil bazani ikki marta qo'shsa — Sonar bunga qarshi hech narsa qilmaydi (ikkita alohida `Id` bilan ikkita yozuv paydo bo'ladi).

---

## 2. Platforma (1C:Enterprise) va COM-connectorni aniqlash

Fayl: `Sonar.Engine/Platform.cs` (/`src_app/Sonar.Engine/Sonar.Engine/Platform.cs`).

### 2.1 O'rnatilgan 1C platforma versiyalarini topish

`Platform.Installed()` (`Platform.cs:20-81`) — `Program Files` va `Program Files (x86)` papkalarini aylanib chiqadi:

```csharp
string pf64 = Environment.GetEnvironmentVariable("ProgramW6432");
string pf   = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
string pf86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
```
— har biri uchun `1cv8` va `1cv82` papkalarini qidiradi, ichidan `8.*` bilan boshlangan versiya papkalarini topadi, `bin\1cv8.exe` yoki `bin\1cv8c.exe` mavjudligini tekshiradi:

```csharp
if (File.Exists(Path.Combine(binDir, "1cv8.exe")) || File.Exists(Path.Combine(binDir, "1cv8c.exe")))
{
    string comDll = Path.Combine(binDir, "comcntr.dll");
    list.Add(new PlatformInfo { Version = fileName, Bits = item2, Dir = item4, ComDll = File.Exists(comDll) ? comDll : "" });
}
```
(`Platform.cs:64-76`)

Natija versiya bo'yicha kamayish tartibida saralanadi (`UpdateVerifier.Compare` orqali semver-tipdagi solishtirish — `Platform.cs:80`).

`PlatformInfo` (`Platform.cs` / `PlatformInfo.cs:3-17`): `Version`, `Bits` (32/64), `Dir`, `ComDll` (bo'sh — comcntr.dll topilmagan).

### 2.2 COM-connectorning ro'yxatdan o'tganini tekshirish

`Platform.Registrations()` (`Platform.cs:95-158`) — Windows registrini **ikki hiv (32/64-bit `RegistryView`)** bo'yicha tekshiradi:

```csharp
using RegistryKey root = RegistryKey.OpenBaseKey(RegistryHive.ClassesRoot, view);
using RegistryKey progKey = root.OpenSubKey(progId + "\\CLSID");          // masalan "V83.COMConnector\CLSID"
string clsid = progKey?.GetValue(null) as string;
using RegistryKey inproc = root.OpenSubKey("CLSID\\" + clsid + "\\InprocServer32");
string dllPath = inproc?.GetValue(null) as string;
```
(`Platform.cs:116-124`)

Tekshiriladigan ProgID'lar (`Platform.cs:16`):
```csharp
public static readonly string[] ProgIds = { "V85.COMConnector", "V83.COMConnector", "V82.COMConnector" };
```
— ya'ni Sonar 1C:Enterprise 8.2, 8.3 va yangi 8.5 (yangi ProgID nomlanishi) connector'larini biladi.

Topilgan DLL fayl versiyasi `FileVersionInfo.GetVersionInfo(dllPath).FileVersion` orqali olinadi (`Platform.cs:135`). Natija: `ComRegistration { ProgId, Bits, Path, Version }`.

32/64-bit ikkalasi ham alohida tekshiriladi — bu shuni bildiradi: **bitta kompyuterda ham 32-bit, ham 64-bit COM connector parallel ro'yxatdan o'tgan bo'lishi mumkin**, va Sonar ikkisini ham ko'radi.

### 2.3 Qaysi ProgID/bitlikni tanlash (runtime'da)

`Platform.ChooseProgId(BaseConfig b, regs)` (`Platform.cs:160-175`) — avval foydalanuvchi sozlamadagi `ProgId`ni tekshiradi, yo'q bo'lsa `ProgIds` ro'yxati bo'yicha mavjudini qidiradi (V85 → V83 → V82 ustunlik tartibida).

`Platform.ChooseBits(BaseConfig b, regs, progId)` (`Platform.cs:182-206`):
- Agar foydalanuvchi aniq `"32"` yoki `"64"` tanlagan bo'lsa (va OS mos bo'lsa) — shu qo'llaniladi.
- `"auto"` bo'lsa: 64-bit OS bo'lsa va 64-bit registratsiya bor bo'lsa → 64; aks holda mavjud 32-bit; aks holda OS bitligi bo'yicha fallback.

`OneCExecutor.OpenAsync` (`Sonar.Engine/OneCExecutor.cs:295-334`) ichida **runtime fallback** ham bor: agar tanlangan bitlik bilan `com_not_registered` xatosi chiqsa va OS 64-bit bo'lsa — avtomatik ikkinchi bitlikka o'tib qayta urinadi:
```csharp
catch (WorkerException ex) when (ex.Code == "com_not_registered" && attempt == 1 && Environment.Is64BitOperatingSystem)
{
    bits = (bits == 64) ? 32 : 64;
    _log.Warn($"«{b.Name}»: {bits}-bit COM ulagichi ro'yxatdan o'tmagan — {bits}-bit bilan urinib ko'rilmoqda");
}
```
Muvaffaqiyatli bo'lsa, `BaseConfig.Bits` avtomatik `"auto"`ga qaytariladi (`OneCExecutor.cs:313-317`) — foydalanuvchi qo'lda tanlagan noto'g'ri bitlik "o'zidan" tuzatiladi.

### 2.4 COM'ni avtomatik ro'yxatdan o'tkazish — `regsvr32` + UAC

Agar comcntr.dll ro'yxatdan o'tmagan bo'lsa, Sonar **o'zi** `regsvr32`ni ishga tushira oladi — bu admin huquqi talab qiladi va UAC-so'rov chiqadi:

```csharp
// Platform.cs:227-270
string regsvr32 = (p.Bits == 32 && Environment.Is64BitOperatingSystem)
    ? Path.Combine(winDir, "SysWOW64", "regsvr32.exe")
    : Path.Combine(winDir, (is64Proc || !is64OS) ? "System32" : "Sysnative", "regsvr32.exe");

Process.Start(new ProcessStartInfo(regsvr32, "/s \"" + p.ComDll + "\"")
{
    UseShellExecute = true,
    Verb = "runas",          // <-- UAC elevation so'raladi
    WindowStyle = ProcessWindowStyle.Hidden
});
```
Xatolar: foydalanuvchi UAC'ni rad etsa — Win32 xato kodi 1223 ushlanadi → `"Administrator ruxsati berilmadi"` (`Platform.cs:260-263`). comcntr.dll umuman topilmasa → `"Bu platformada comcntr.dll yo'q. 1C o'rnatuvchisida «1С:Предприятие» komponentini to'liq o'rnating."` (`Platform.cs:232`).

Bu funksiya UI'dan **"COM'ni ro'yxatdan o'tkazish"** tugmasi orqali chaqiriladi (`ThisPcTabViewModel.RegisterComAsync` — pastda) va baza qo'shish dialogida xato chiqsa **"Tuzatish"** havolasi orqali (`EngineBaseDialogViewModel.FixComAsync`, pastda).

**Foydalanuvchiga ko'rinadigan matn** (`Uz.ThisPc`): `ComTitle` → *"1C COM ulagichi"*; `ComText` → *"1C ga ulanib bo'lmasa (COM xatosi) — ulagichni ro'yxatdan o'tkazing. Windows administrator ruxsatini so'raydi."*; `ComFixHint` → *"Windows administrator ruxsatini so'raydi, keyin Sonar bazani o'zi qayta tekshiradi."* — ya'ni UAC-so'rov chiqishi oldindan tushuntiriladi, foydalanuvchi kutilmagan tizim dialogidan hayratga tushmaydi.

### 2.5 `EngineGuard` / `InstanceLock` — bitta mashina = bitta yadro

`EngineGuard` (`Sonar.Engine/EngineGuard.cs`) — Windows named-mutex orqali shuni ta'minlaydi, bir vaqtning o'zida faqat **bitta** Sonar nusxasi 1C'ga ulansin:

```csharp
public const string EngineMutex = "Local\\SonarEngine";
public const string LegacyMutex = "Local\\SonarConnector";
```
`TryAcquire()` (`EngineGuard.cs:45-61`):
1. Avval eski ("legacy") Connector ishlab turganini tekshiradi (`LegacyRunning()`); agar ishlab tursa — `"Eski Sonar Connector ishlayapti — uni yoping (tray → Chiqish)"` qaytadi va yangi Engine ishga tushmaydi.
2. Keyin `InstanceLock.TryAcquire("Local\\SonarEngine")` bilan mutex olishga urinadi; muvaffaqiyatsiz bo'lsa — `"Sonar'ning 1C yadrosi shu kompyuterda boshqa dasturda ishlayapti — u yopilguncha kutilmoqda"`.

`InstanceLock` (`Sonar.Engine/InstanceLock.cs`) texnik jihatdan qiziq: mutex **alohida background thread'da** ushlab turiladi (chunki .NET mutex egasi thread bo'ladi, process emas), `ManualResetEventSlim` orqali signal almashinadi (`InstanceLock.cs:18-73`). `Dispose()` chaqirilganda thread'ga signal beriladi va mutex bo'shatiladi.

### 2.6 "Legacy" — eski **mahsulot avlodi**, eski 1C versiyasi emas

Muhim topilma: `LegacyConnector`/`LegacyInfo`/`LegacyEnv` bu yerda **"eski 1C versiyasi"** haqida emas — bu **Sonar'ning oldingi mahsulot nomi — "Sonar Connector"** (alohida eski `.exe`, eski o'rnatuvchi) haqida:

```csharp
// Sonar.Engine/LegacyConnector.cs:14-34
public const string RunName = "SonarConnector";
public const string UninstallKey = "...\\Uninstall\\SonarConnector";
public const string ExeName = "SonarConnector.exe";
internal static readonly string[] KnownFiles = { "uninstall.exe", "SonarConnector.exe", ..., "SonarWorker32.exe", "SonarWorker64.exe", ..., "README.txt" };
```

`LegacyConnector.Detect()` (`LegacyConnector.cs:38-92`) tekshiradi:
- `HKCU\...\Uninstall\SonarConnector` yozuvi bormi (eski o'rnatuvchi qolgan izi);
- `HKCU\...\Run\SonarConnector` autostart yozuvi bormi;
- Start Menu/Desktop'da `Sonar Connector.lnk` yorliqlari bormi;
- eski `SonarConnector.exe` jarayoni ishlab turganmi yoki uning mutex'i (`Local\SonarConnector`) hali ham bormi.

`RemoveAsync()` (`LegacyConnector.cs:188-304`) — bu eski mahsulotni **toza tozalash**: jarayonni avval nazokat bilan (`SignalExit`, `Local\SonarConnector.Exit` event orqali) to'xtatishga urinadi, 15 soniya kutadi, javob bo'lmasa majburan `Kill()`, keyin registratsiya yozuvlarini, yorliqlarni, bilingan fayllarni o'chiradi. **Muhim xavfsizlik tekshiruvi** — `SafeInstallDir()` (`LegacyConnector.cs:151-172`): papka faqat nomi aniq `"Sonar Connector"` bo'lgan va foydalanuvchi sozlamalari joylashgan joylarga (`AppData\SonarConnector`, `LocalAppData\SonarConnector`) ustma-ust tushmagan taqdirda o'chiriladi — ya'ni o'chirish skripti tasodifan boshqa papkani yoki foydalanuvchi sozlamalarini o'chirib yubormasligi uchun himoya. Tozalashdan keyingi xabar aniq ta'kidlaydi: **"Sozlamalar, 1C bazalari va Sonar'ga ulanish joyida qoldi"** (`LegacyConnector.cs:322`) — ya'ni foydalanuvchi eski mahsulotdan yangisiga o'tganda hech narsa yo'qotmaydi (lekin bazalar/parollar avtomatik ko'chirilmaydi ham — chunki fayl formatlari/joylari farq qiladi, quyida 3-bo'limda).

Bu funksiyalar o'rnatish paytida (`AppInstaller.InstallAsync`, agar `o.RemoveLegacy=true`) va "This PC" sahifasida qo'lda chaqiriladi.

**Foydalanuvchiga ko'rinadigan matn** (`Uz.ThisPc`, `src_app/Sonar.Desktop.Core/Sonar.Desktop.Core.Text/Uz.cs`):
- `LegacyFound` → *"Eski Sonar Connector topildi — endi 1C bilan Sonar o'zi ishlaydi"*
- `LegacyText` → *"Eski dasturni Sonar o'zi xavfsiz olib tashlaydi: jarayonni yopadi, avtomatik ishga tushish, «Ilovalar» yozuvi, yorliqlar va dastur fayllarini o'chiradi. 1C bazalari, parollar va Sonar'ga ulanish joyida qoladi."*
- `ConflictHint` → *"Sonar eski Connector yopilishini kutyapti (10 soniyada bir tekshiradi) — yopilishi bilan o'zi ishga tushadi."*
- `ConflictNoUninstall` → *"Eski Connector'ni Windows «Ilovalar» ro'yxatidan o'chirmang: uning o'chiruvchisi ulanishni bekor qiladi va 1C bazalari sozlamalarini o'chirib yuboradi."*

Oxirgi ogohlantirish muhim: agar foydalanuvchi eski "Sonar Connector"ni **Windows'ning o'z "Dasturlar" ro'yxatidan** o'chirsa (Sonar'ning ichki tozalagichi orqali emas), eski o'rnatuvchining o'z uninstall-skripti `%AppData%\SonarConnector` papkasini (sozlamalar/parollar) o'chirib yuborishi mumkin — shuning uchun Sonar foydalanuvchini bundan aniq ogohlantiradi va buni **o'zi**, xavfsiz (`SafeInstallDir` tekshiruvi bilan) amalga oshiradi.

### 2.7 1C-ga haqiqiy ulanish qanday o'rnatiladi

`OneCExecutor.OpenAsync()` (`Sonar.Engine/OneCExecutor.cs:295-334`):
1. `Platform.Registrations()` orqali mavjud COM-registratsiyalar olinadi.
2. `ChooseProgId`/`ChooseBits` bilan haqiqiy ProgID va bitlik tanlanadi.
3. `WorkerHost` (alohida `SonarWorker32.exe`/`64.exe` jarayoni) ishga tushiriladi (`Platform.WorkerPath` — `Platform.cs:208-225`, avval `SonarWorker{bits}.exe`ni, keyin eski nom variantini qidiradi).
4. Workerga JSON-buyruq yuboriladi:
   ```csharp
   w.CallAsync(J.Make("cmd", "open", "progid", progId, "conn", ConnString(b)), TimeSpan.FromSeconds(120.0), ct)
   ```
   bu yerda `ConnString(b) = OneCConnect.Build(b.Connect, b.OsAuth ? "" : b.User, b.OsAuth ? "" : b.Password)` (`OneCExecutor.cs:228-230`) — ulanish satriga `Usr=`/`Pwd=` qo'shib beradi (agar Windows autentifikatsiyasi yoqilmagan bo'lsa).
5. Worker ichida (bu kod decompiled to'plamga kirmagan, lekin protokoldan ko'rinadi) haqiqiy `V8x.COMConnector` COM-obyekti yaratiladi va `.Connect(connString)` chaqiriladi.

Timeout — 120 soniya (birinchi ochish uchun), keyingi so'rovlar `task.TimeoutSeconds` bo'yicha (`OneCExecutor.cs:169`).

---

## 3. Baza konfiguratsiyasi va parollarni saqlash

### 3.1 Fayllar qayerda yotadi

| Nima | Joy | Kod |
|---|---|---|
| Engine (Connector) sozlamalari, bazalar ro'yxati | `%APPDATA%\SonarConnector\settings.json` | `AppSettings.Dir`/`DefaultPath` — `Sonar.Engine/AppSettings.cs:42-46` |
| Engine loglari | `%LOCALAPPDATA%\SonarConnector\logs\` | `AppSettings.LogDir` — `AppSettings.cs:44` |
| Desktop-app (UI) sozlamalari | `%APPDATA%\Sonar\settings.json` (`SettingsStore` orqali, fayl yo'li chaqiruvchi tomondan beriladi) | `Sonar.Installer/SetupPaths.cs:19` (`AppSettingsDir`) |
| Sessiya tokeni (login) | `%APPDATA%\Sonar\session.bin` (DPAPI bilan shifrlangan) | `TokenStores.CreateDefault` — `DpapiTokenStore.cs:12-23` |
| O'rnatilgan dastur fayllari | `%LOCALAPPDATA%\Programs\Sonar\` | `SetupPaths.DefaultInstallDir` — `SetupPaths.cs:17` |

Diqqat qiling: **ikki xil "ism"** ishlatiladi — `Sonar` (desktop UI, foydalanuvchi sozlamalari) va `SonarConnector` (ichki Engine — eski mahsulot nomidan meros, lekin hozir ham shunday saqlangan). Bu ataylab shunday qilingan — eski "Sonar Connector" dasturidan farqlash, ya'ni papka nomi tasodifiy emas, tarixiy.

### 3.2 `settings.json` formati va `BaseConfig` tuzilmasi

`AppSettings` (`Sonar.Engine/AppSettings.cs:10-124`) — oddiy JSON (`Json.ParseObject`/`Json.Write`, qo'l yozilgan minimal JSON kutubxona, `Sonar.Core/Json.cs`), BOM'siz UTF-8:

```csharp
File.WriteAllText(tmpPath, Json.Write(value), new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
```
Yozish **atomik**: avval `.tmp` fayl yoziladi, keyin eski fayl o'chirilib, `.tmp` asosiy nomga ko'chiriladi (`AppSettings.cs:110-117`) — demak jarayon o'chib qolsa (crash, elektr uzilishi) `settings.json` buzilib qolmaydi, eng yomon holatda eski holatda qoladi.

`AppSettings` maydonlari (`AppSettings.cs:14-36`): `Server` (default `https://sonar.shaxzoddev.uz/1c/api.php`), `TokenProtected` (DPAPI bilan shifrlangan server-token), `ConnectorId`, `Account`, `DeviceId` (GUID, bir marta generatsiya qilinadi), `AutoStart`, `Background`, `AutoUpdate`, `AllowWrite`, `Paused`, `Revoked`, `Bases: List<BaseConfig>`.

**`BaseConfig`** (`Sonar.Engine/BaseConfig.cs:7-123`) — har bir qo'shilgan 1C baza uchun to'liq maydon ro'yxati:

| Maydon | Tur | Izoh |
|---|---|---|
| `Id` | `string` (GUID, `"N"` format) | lokal, server bilmaydigan ID; `Guid.NewGuid()` bilan generatsiya |
| `Name` | `string` | foydalanuvchi bergan nom |
| `Connect` | `string` | normallashtirilgan `File=...;` yoki `Srvr=...;Ref=...;` |
| `User` | `string` | 1C foydalanuvchi nomi |
| `PasswordProtected` | `string` | **DPAPI bilan shifrlangan** parol (base64) |
| `Password` (property) | — | `get`/`set` orqali `PasswordProtected`ni avtomatik (un)protect qiladi |
| `OsAuth` | `bool` | Windows autentifikatsiyasidan foydalanish |
| `Bits` | `string` | `"auto"`/`"32"`/`"64"` |
| `ProgId` | `string` | default `"V83.COMConnector"` |
| `Enabled` | `bool` | |
| `Demo` | `bool` | demo-baza (haqiqiy 1C yo'q, soxta ma'lumot) |
| `Registered` | `bool` | serverga yuborilganmi |
| `ServerId` | `long` | server tomonidan qaytarilgan ID |
| `ConfigName`/`ConfigSynonym`/`ConfigVersion` | `string` | 1C konfiguratsiyasi haqida — ulanish testidan keyin to'ldiriladi |
| `Platform` | `string` | 1C platforma versiyasi (worker javobidan) |
| `LastOk`/`LastError` | `string` | oxirgi muvaffaqiyatli vaqt / oxirgi xato kodi |

`ToJson()`/`FromJson()` (`BaseConfig.cs:94-122`) — JSON maydonlari ingliz tilida, qisqa kalitlar (`id`, `name`, `connect`, `user`, `password`, `os_auth`, `bits`, `progid`, `enabled`, `demo`, `registered`, `server_id`, `config_name`, `config_synonym`, `config_version`, `platform`, `last_ok`, `last_error`).

### 3.3 DPAPI bilan shifrlash

`Sonar.Engine/Dpapi.cs` — Windows DPAPI (`System.Security.Cryptography.ProtectedData`), **`DataProtectionScope.CurrentUser`**:

```csharp
private static readonly byte[] Entropy = Encoding.UTF8.GetBytes("SonarConnector.v1");
private static byte[] WinProtect(byte[] data) => ProtectedData.Protect(data, Entropy, DataProtectionScope.CurrentUser);
private static byte[] WinUnprotect(byte[] data) => ProtectedData.Unprotect(data, Entropy, DataProtectionScope.CurrentUser);
```
(`Dpapi.cs:12, 51-61`)

- `CurrentUser` scope — ya'ni shifr faqat **aynan shu Windows foydalanuvchi + shu kompyuter** ostida ochiladi (Windows login master-key bilan bog'liq). Boshqa foydalanuvchi yoki boshqa kompyuterga ko'chirilgan `settings.json`dagi parol **o'qib bo'lmaydi**.
- "Entropy" qo'shimcha maxfiy emas — u ochiq literal satr (`"SonarConnector.v1"`), DPAPI API talab qilgani uchun qo'shilgan, xavfsizlikni oshirmaydi, faqat boshqa ilova bir xil foydalanuvchi profilida tasodifan buni ochib qo'yishining oldini oladigan "namespace" vazifasini bajaradi.
- Windows bo'lmagan platformalarda (`!Platform.IsWindows`) — shifr **umuman qo'yilmaydi**, faqat `"unprotected:" + base64`:
  ```csharp
  if (!Platform.IsWindows) return "unprotected:" + Convert.ToBase64String(Encoding.UTF8.GetBytes(plain));
  ```
  (`Dpapi.cs:20-24`) — bu amalda ahamiyatsiz, chunki 1C COM faqat Windows'da ishlaydi va bu kod yo'li faqat "degrade" holat uchun (build boshqa platformada compile bo'lsa ham ishlasin, deb).
- Xato bo'lsa (`Unprotect` muvaffaqiyatsiz — masalan fayl boshqa kompyuterdan ko'chirilgan, yoki Windows profil kalitlari almashtirilgan) — `catch (Exception) { return ""; }` (`Dpapi.cs:45-48`): **jim ravishda bo'sh parol** qaytariladi, foydalanuvchiga xato ko'rsatilmaydi (keyinroq 1C "noto'g'ri parol" xatosi sifatida chiqadi — qayta parolni kiritishga majbur qiladi).

**Desktop UI sessiya-tokeni** uchun alohida, lekin konseptual bir xil mexanizm — `DpapiTokenStore` (`src_app/Sonar.Desktop.Core/Sonar.Desktop.Core.Services/DpapiTokenStore.cs:12-61`):
```csharp
private static readonly byte[] Entropy = "Sonar Desktop token v1"u8.ToArray();
...
ProtectedData.Protect(JsonSerializer.SerializeToUtf8Bytes(_memory), Entropy, DataProtectionScope.CurrentUser);
```
Fayl: `session.bin` (`TokenStores.CreateDefault`, `TokenStores.cs:12`). Yozish ham atomik (`.tmp` + `Move(overwrite:true)`, `DpapiTokenStore.cs:52-56`).

### 3.4 Platformalararo abstraksiya: `ITokenStore`

```csharp
// ITokenStore.cs
public interface ITokenStore { string Mode { get; } string? Load(string scope); void Save(string token, string scope); void Clear(); }
```
Uch implementatsiya (`TokenStores.CreateDefault`, `TokenStores.cs:8-19`):
- **Windows** → `DpapiTokenStore` (fayl `session.bin`, DPAPI/CurrentUser).
- **macOS** → `KeychainTokenStore` (`KeychainTokenStore.cs:9-104`) — `/usr/bin/security find-generic-password`/`add-generic-password`/`delete-generic-password` buyruqlarini **tashqi process** sifatida chaqiradi (servis nomi `"Sonar Desktop"`, hisob — berilgan `account`, default `"session"`). Bu yerda haqiqiy "parol" emas — JSON (`StoredToken`) matn ko'rinishida saqlanadi (shell-escaping bilan, `add-generic-password -U -a <account> -s "Sonar Desktop" -w "<json>"`).
- **Boshqa (Linux va h.k.)** → `MemoryTokenStore` (`MemoryTokenStore.cs`) — shifrlanmagan, faqat RAM'da, process tugagach yo'qoladi. (macOS/Windows'da ham, agar DPAPI/Keychain mavjud bo'lmasa, oxir-oqibat shu fallback'ga tushishi mumkin — lekin kodda aniq fallback yo'q, `TokenStores.CreateDefault` to'g'ridan-to'g'ri OS turi bo'yicha tanlaydi.)

Bu holat foydalanuvchiga **yashirilmaydi** — agar xavfsiz saqlash (DPAPI/Keychain) ushbu kompyuterda ishlamasa, login ekranida ogohlantirish chiqadi (`Uz.Login.MemoryWarning`): *"Bu kompyuterda shifrlangan saqlash mavjud emas: kirish faqat dastur yopilguncha saqlanadi, keyingi safar yana kirishingiz kerak bo'ladi."* — ya'ni funksionallik pasaysa ham, foydalanuvchi buni oldindan biladi, kutilmagan "nega yana kirish so'radi" holati yuzaga kelmaydi.

Har uchtasi bitta `StoredToken` record'ini saqlaydi: `record StoredToken(int V, string Scope, string Token)` (`StoredToken.cs:3`) — `Scope` (`mock`/haqiqiy API bazasi) bo'yicha token tekshiriladi, bu "qaysi serverga ulangan edik" ni token bilan birga tasdiqlaydi (masalan mock-rejimdan haqiqiy serverга o'tishda eski token qabul qilinmaydi).

### 3.5 1C hisob ma'lumotlari — qayerda, qanday

- **1C login/parol** faqat `BaseConfig.User`/`BaseConfig.PasswordProtected` ichida — DPAPI bilan, yuqoridagi kabi. Server bu ma'lumotlarni **hech qachon ko'rmaydi** — `SyncPassAsync()` orqali serverga yuboriladigan `body` faqat `local_id`, `name`, `kind`, `config.*`, `platform`, `status` (`src_app/Sonar.Engine/Sonar.Engine/ConnectorEngine.cs:895`) — login/parol yo'q.
- `OneCConnect.Build()` (`Sonar.Core/OneCConnect.cs:89-114`) — ulanish satriga `Usr=`/`Pwd=` ni **faqat runtime'da, xotirada**, worker-processga yuborish vaqtida qo'shadi; diskda saqlanmaydi (parol alohida, shifrlangan holda saqlanadi, umumiy `Connect` satrida emas).
- `Secrets.Mask()` (`Sonar.Core/Secrets.cs:5-28`) — log yozuvlarida/xato xabarlarida parolni/tokenni avtomatik `***`ga almashtiradigan regex-filtr (`Pwd=...`, `Bearer ...`, JSON `"password":"..."`, va ichki token formati `sc1.<n>.<hash>`). Bu — loglarga tasodifan parol tushib qolmasligi uchun **mudofaa darajasi**.
- **`OsAuth=true`** bo'lsa — `User`/`Password` umuman ishlatilmaydi, saqlashda ham tozalanadi (`ApplyFields` — `ConnectorEngine.cs:1345-1348`: `if (b.OsAuth) b.PasswordProtected = ""`).

---

## 4. UI oqimi: o'rnatishdan tayyor bo'lgunga qadar

### 4.1 Kirish (login) — Telegram-bot orqali kod/QR, parol YO'Q

`LoginViewModel` (`src_app/Sonar.Desktop.Core/Sonar.Desktop.Core.ViewModels/LoginViewModel.cs`) — login email/parol emas, **polling-asosidagi pairing**:

1. Dastur ochilganda `AuthStartAsync` chaqiriladi (`LoginViewModel.cs:634-660`):
   ```csharp
   authStart = await _s.Api.AuthStartAsync(new DeviceInfo { Name = deviceName, Os = osName, AppVersion = appVersion }, ct);
   ```
   Server bir martalik `LoginId`, `PollSecret`, `Code` (qisqa matn-kod) va `BotLink` (Telegram deep-link) qaytaradi.
2. UI'da ikki narsa ko'rsatiladi: **QR-kod** (`BuildQr(authStart.BotLink)` — `QRCoder` kutubxonasi orqali qurilgan, `LoginViewModel.cs:812-829`) va matn-kod (`Start.Code`). Foydalanuvchi yo QR'ni telefon kamerasi bilan skanerlaydi, yo "Telegram'da ochish" tugmasini bosadi (`OpenTelegramCommand`), yo kodni qo'lda Telegram-botga yuboradi.
3. `PollAsync` (`LoginViewModel.cs:678-749`) har **2 soniyada** (`PollInterval = TimeSpan.FromSeconds(2)`) `AuthPollAsync(loginId, pollSecret)` chaqiradi. Javob holati: `"approved"` → token olinadi va saqlanadi (`_s.Session.Accept(token, scope)`), `"denied"` → rad etilgan holat, aks holda `"expired"`.
4. Countdown: kod amal qilish muddati (`_expiresAt`) har soniyada yangilanadi, vaqt tugaganda avtomatik `Expired` holatiga o'tadi.
5. Tarmoq xatosi bo'lsa — `PollTrouble=true`, lekin polling davom etadi (vaqtinchalik tarmoq nosozligi uchun chidamli); `403`/`404`/`410` status kodlari esa darhol `Expired` holatini bildiradi (kod allaqachon ishlatilgan/bekor qilingan).
6. Foydalanuvchi oferta shartlarini qabul qilmagunicha (`TermsAccepted`) kod umuman so'ralmaydi (`Begin()` faqat shartlar qabul qilingandan keyin ishga tushadi — `LoginViewModel.cs:626-632`).
7. Kod amal qilish muddati — server `ExpiresIn`/`ExpiresAt`dan olinadi, 1–3600s oralig'ida qisqartiriladi, hech narsa bo'lmasa 5 daqiqa (`LoginLogic.CodeTtlMs = 300000`, `LoginLogic.cs:8-32`) standart qiymat.

Bu bosqich — **Desktop-ilovaga kirish** (foydalanuvchi hisobi), 1C bilan hali bog'liq emas.

**Foydalanuvchiga ko'rinadigan matn** (`Uz.Login`, `Uz.cs:950-1015`):
- Sarlavha: *"Sonar'ga kirish"*; kichik matn: *"Parol kerak emas — kirishni Telegram'dagi Sonar botida tasdiqlaysiz."*
- Qadamlar: *"Telegram'da @sonar_aibot ni oching yoki QR kodni telefon bilan skanerlang"* → *"Bot so'raganda «Tasdiqlash» tugmasini bosing"* → *"Sonar Desktop o'zi ochiladi"*
- Holatlar: `Starting` → *"Kod tayyorlanmoqda…"*; `Waiting` → *"Botdagi tasdiq kutilmoqda…"*; `Approved` → *"Tasdiqlandi! Kirilmoqda…"*; `Denied` → *"Kirish rad etildi"* (+ `DeniedHint`: *"Botda «Rad etish» bosildi. Agar bu siz bo'lsangiz, yangi kod oling."*); `Expired` → *"Kod eskirdi"* (+ `ExpiredHint`: *"Kod 5 daqiqa amal qiladi. Yangi kod oling va qayta urinib ko'ring."*)
- Xatolar: `StartError` → *"Kirish kodini olib bo'lmadi"*; `PollTrouble` → *"Aloqa uzildi, qayta urinilmoqda…"* (tarmoq vaqtincha uzilsa ham polling davom etadi); `SessionExpired` → *"Sessiya tugadi. Iltimos, qayta kiring."*
- Sinov rejimi: `MockHint` → *"Sinov rejimi: bot o'rniga kirish bir necha soniyada avtomatik tasdiqlanadi."*
- Pastki eslatma (`Footer`): *"Hech narsa sizning tasdig'ingizsiz 1C da o'zgarmaydi."* — bu login ekranidanoq foydalanuvchiga butun mahsulotning asosiy xavfsizlik va'dasini bildiradi.

### 4.2 Ish turi tanlash — `DirectionChoiceViewModel`

Login'dan keyin, agar hali tanlanmagan bo'lsa, foydalanuvchiga ish turi tanlash so'raladi: **`"business"`** (sparkles) yoki **`"accounting"`** (calculator) (`DirectionChoiceViewModel.cs:117-121`). Bu UI matnini va keyingi bo'limlarni (qaysi menyular ko'rinishini) belgilaydi — 1C ulash bosqichiga bevosita ta'sir qilmaydi, lekin "Accounting" (buxgalteriya) rejimida 1C-integratsiyasi markaziy o'rinni egallaydi.

### 4.3 "Kompyuterni ulash" (Claim) — butunlay avtomatik pairing

Faqat Windows kompyuterda, Desktop ilovasining o'zi **kompyuterni hisobga ulashni** avtomatik amalga oshiradi — foydalanuvchidan hech qanday kod so'ralmaydi:

```csharp
// EngineCoordinator.cs:711-719
PairCode code = await _s.Api.ConnectorPairCodeAsync(_life.Token);   // server: bir martalik kod + apiUrl
if (reason == PairReason.Claim) await engine.UnpairAsync(_life.Token); // avval eski ulanishni uzadi
await engine.PairAsync(code.ApiUrl, code.Code, _life.Token);
```

`ConnectorEngine.PairAsync()` (`src_app/Sonar.Engine/Sonar.Engine/ConnectorEngine.cs:971-1045`) serverga `pair` so'rovini yuboradi:
```csharp
d = await api.CallAsync("pair", J.Make("code", text, "device", J.Make(
    "name", _deviceName, "os", _os, "version", _version,
    "machine", Platform.MachineHash(), "device_id", deviceId)), ct, auth: false);
```
— `Platform.MachineHash()` (`Platform.cs:296-313`) Windows registridagi `MachineGuid`dan SHA-256 orqali olingan barqaror, lekin anonim mashina-identifikatori (shaxsiy ma'lumot emas).

Natijada server `token` va `connector_id` qaytaradi, ular DPAPI bilan shifrlanib `settings.json`ga yoziladi, va `Agent` hello/poll tsikli (6-bo'lim) ishga tushadi. Bu barchasi **foydalanuvchi uchun shaffof** — "This PC" sahifasida faqat holat ko'rinadi.

**"Claim" tugmasi** — faqat kompyuter allaqachon **boshqa hisobga** ulangan bo'lsa ko'rinadi, tasdiq dialogi bilan: *"Kompyuterni o'zingizga ulaysizmi? Bu kompyuter boshqa hisobdan uziladi va sizning Sonar hisobingizga ulanadi. 1C bazalari va parollari saqlanadi."* (`ThisPcTabViewModel.cs:555`).

Hali umuman ulanmagan holatda ko'rinadigan matn (`Uz.ThisPc.NotPairedTitle`/`NotPairedText`): *"Bu kompyuter hali Sonar'ga ulanmagan"* / *"Kod kerak emas — Sonar hisobingiz orqali bir bosishda ulanadi. Ulangach botga «Kompyuter ulandi» xabari keladi."* — bu Telegram-pairing'dan tubdan farq qiladi: u yerda foydalanuvchi kod/QR bilan ishlaydi, bu yerda esa butunlay fon rejimida, hech qanday kod ko'rsatilmasdan amalga oshadi, faqat bot orqali tasdiqlovchi xabar keladi. Agar bekor qilingan ulanish qayta tiklanishi kerak bo'lsa: `RevokedAsk` → *"Bu kompyuterning 1C ulanishi bekor qilingan (botda uzilgan bo'lishi mumkin). Qayta ulaymi?"*

### 4.4 "This PC" sahifasi — `ThisPcTabView`/`ThisPcTabViewModel`

Ro'yxatlar/holatlar (`ThisPcTabViewModel.cs:88-516`):
- **Status qatorlari** (`StatusRows`): server manzili (host nomi), "Sonar'dagi nomi" (`Uz.ThisPc.ConnectorNo(id)` → `"#<id>"`), oxirgi aloqa vaqti (nisbiy, masalan "5 daqiqa oldin"), bajarilgan so'rovlar soni, oxirgi faoliyat matni, topilgan 1C platformalari ro'yxati, Engine (connector) versiyasi.
- **Bazalar ro'yxati** (`BaseRows: ObservableCollection<EngineBaseRow>`) — har bir qo'shilgan bazaning nomi, holati (Demo/Registered/O'chirilgan belgilari), oxirgi muvaffaqiyatli ulanish vaqti, oxirgi xato (agar bor bo'lsa, qizil banner bilan).
- **Boshqa kompyuterlar** (`ComputerRows`) — bir xil hisobga ulangan boshqa kompyuterlar (onlayn/offline nuqta bilan).
- Buyruqlar: `AddBaseCommand` (yangi baza qo'shish dialogini ochadi), `EditBaseCommand`, `AddDemoCommand` (demo-baza qo'shadi, haqiqiy 1C kerak emas — sinov uchun), `TestBaseCommand` (ulanishni qayta tekshiradi), `RemoveBaseCommand` (tasdiq bilan), `RegisterComCommand` ("COM'ni ro'yxatdan o'tkazish" — 2.4-bo'lim), `TogglePauseCommand` (butun Connectorni vaqtincha to'xtatish — "1C so'rovlari bajarilmaydi"), `ToggleAutoStartCommand` (Windows bilan birga ishga tushish).
- `AddDemoBase()` (`src_app/Sonar.Engine/Sonar.Engine/ConnectorEngine.cs:1504-1527`) — `Demo=true`, `Connect=""` bo'lgan `BaseConfig` yaratadi, haqiqiy COM chaqirilmaydi, o'rniga `DemoSession` soxta ma'lumot beradi — mahsulotni 1C'siz sinab ko'rish imkoniyati.
- Hali hech qanday baza qo'shilmagan holat (`Uz.ThisPc.NoBases`/`NoBasesText`): *"Hali baza qo'shilmagan"* / *"1C ro'yxatidagi bazani tanlang yoki ulanish qatorini kiriting. Sinab ko'rish uchun demo bazani qo'shing."* — bo'sh holat ham foydalanuvchini keyingi aniq harakatga (ro'yxatdan tanlash / qo'lda kiritish / demo) yo'naltiradi, shunchaki "bazalar yo'q" deb qo'ymaydi.

### 4.5 Baza qo'shish/tahrirlash dialogi — `EngineBaseDialogViewModel`

Bu — **eng muhim ekran** 1C ulash jarayonida. Sarlavha ustida izoh: **"Sonar avval ulanishni tekshiradi — muvaffaqiyatli bo'lsagina saqlaydi."** (`EngineBaseDialogViewModel.cs:90`).

Ikki manba (`Source`: `"list"`/`"manual"`):
- **`"list"`** (default, agar `LocalIbases()` bo'sh bo'lmasa) — `ThisPc`da avtomatik topilgan bazalar ro'yxatidan (`IbaseOption`) tanlash; birinchi element avtomatik tanlanadi, nom maydoniga uning nomi avtomatik yoziladi (`SelectIbase` — `EngineBaseDialogViewModel.cs:450-462`).
- **`"manual"`** — foydalanuvchi ulanish satrini (`Connect`) qo'lda kiritadi (fayl yo'li yoki server+baza nomi).

Maydonlar: `BaseName`, `Connect`, `User`, `Password` (mavjud bazani tahrirlashda bo'sh qoldirilsa — eski parol o'zgarmaydi: `PasswordWatermark = "O'zgartirmaslik uchun bo'sh qoldiring"`, `EngineBaseDialogViewModel.cs:154-164`), `OsAuth` (checkbox — yoqilsa login/parol maydonlari o'chiriladi, `CredentialsEnabled = !OsAuth`), `Bits` (`"auto"`/`"32"`/`"64"` — radio/dropdown, `BitsOptions`).

Agar avtomatik topilgan ro'yxat bo'sh bo'lsa (`Uz.ThisPc.ListEmpty`): *"1C ro'yxatida baza topilmadi (1C:Предприятие ishga tushirish oynasidagi ro'yxat). Ulanish qatorini kiriting."* — foydalanuvchi avtomatik qidiruv nega bo'sh bo'lganini (1C hali ro'yxatga qo'shilmagan) tushunadi va "manual" rejimga o'zi o'tadi. Qo'lda kiritish uchun yordamchi matnlar: `ConnectPlaceholder` → `File="C:\1C\Buxgalteriya";`; `ConnectHint` → *"Fayl bazasi: File=\"C:\\1C\\Baza\";  ·  Server bazasi: Srvr=\"server\";Ref=\"baza\";"*; `PasswordHint` → *"Parol faqat shu kompyuterda shifrlangan holda saqlanadi va Sonar serveriga yuborilmaydi."* — bu oxirgi jumla 3.3-3.5-bo'limlarda tasvirlangan DPAPI-himoyani foydalanuvchiga aniq, tushunarli tilda bildirib qo'yadi, ya'ni texnik mexanizm UI matniga bevosita ko'chirilgan.

**Saqlash = test qilish**: `SaveAsync()` (`EngineBaseDialogViewModel.cs:475-520`) tugmasi bosilganda matn `"Ulanish tekshirilmoqda…"`ga o'zgaradi (`SaveText` — `EngineBaseDialogViewModel.cs:168-178`), so'ng:
```csharp
EngineBase saved = await _engine.SaveBaseAsync(draft, password, ct);
```
`ConnectorEngine.SaveBaseAsync()` (`ConnectorEngine.cs:1267-1316`) ichida **saqlashdan oldin** `TestConnectionAsync(draft, ct)` chaqiriladi (`ConnectorEngine.cs:1284`) — ya'ni haqiqatan COM orqali 1C'ga ulanib ko'riladi, muvaffaqiyatli bo'lsa (`config.name/synonym/version`, `platform`, `bits` javob JSON'idan olinib) `BaseConfig`ga yoziladi va **shundan keyingina** disk ga saqlanadi. Agar ulanish muvaffaqiyatsiz bo'lsa — hech narsa saqlanmaydi, foydalanuvchiga xato ko'rsatiladi (`Error`), va agar xato aniq `com_not_registered` bo'lsa — `ComFix=true` bo'ladi, dialogda **"Tuzatish"** havolasi chiqadi (`FixComAsync()` → `RegisterComAsync()` → muvaffaqiyatli bo'lsa avtomatik qayta `SaveAsync()`ni chaqiradi, `EngineBaseDialogViewModel.cs:539-566`).

Xato bo'lganda, agar bu `ArgumentException` (ya'ni foydalanuvchi xatosi — bo'sh nom, bo'sh login) bo'lmasa, xato **avtomatik serverga hisobot** sifatida yuboriladi (`ReportAsync` — `EngineBaseDialogViewModel.cs:522-537`, kod/xabar/turi/bitlik/platforma bilan) — mahsulot sifatini kuzatish uchun telemetriya, lekin parol/login yuborilmaydi.

### 4.6 "AI ulagichi" / 1C tab — `OneCTabViewModel` va ikki pog'onali "Yozish" ruxsati

`OneCTabViewModel` (`src_app/Sonar.Desktop.Core/Sonar.Desktop.Core.ViewModels/OneCTabViewModel.cs`):
- `StatusTitle`/`StatusText` — agar hali baza ulanmagan bo'lsa: *"Hali 1C bazasi ulanmagan"* + *"Pastdagi ro'yxatdan bazani qo'shing va «Ish joyiga ulash» ni bosing."* (`OneCTabViewModel.cs:379-382`). Agar ulangan va onlayn: *"«Baza» ulangan"*. Agar ulangan, lekin kompyuter oflayn: *"«Baza» ulangan, lekin hozir aloqa yo'q"* + *"1C o'rnatilgan kompyuterda Sonar ochiq bo'lsin — raqamlar o'zi yangilanadi."* (`OneCTabViewModel.cs:384-397`, `Uz.Setup.Connected`/`Offline`).
- **"1C ga yozish" tugmasi — IKKI qulf**:
  ```csharp
  private bool CompanyWrite => Settings.Data?.WriteEnabled ?? false;   // server/kompaniya darajasi
  private bool PcWrite => Engine.HasEngine ? Engine.AllowWrite : true; // shu kompyuter darajasi
  public bool WriteOn => CompanyWrite && PcWrite;                      // ikkisi ham kerak
  ```
  (`OneCTabViewModel.cs:65-89`) — ya'ni 1C'ga yozish uchun **ikki alohida tasdiq** kerak: (a) kompaniya/buxgalteriya darajasida serverda yoqilgan bo'lishi (`CompanySettingsAsync`), (b) **va** aynan shu kompyuterdagi Engine'da `AllowWrite=true` bo'lishi. `WritePartial` holati ("Qisman yoqilgan") aynan shu ikki qulfning faqat bittasi yoqilganini ko'rsatadi.
  `ToggleWriteAsync()` (`OneCTabViewModel.cs:409-457`) ikkisini bir vaqtda almashtiradi: avval serverga `CompanySettingsAsync(companyId, enable)`, muvaffaqiyatli bo'lsa va `Engine.IsOwner` bo'lsa — `engine.SetAllowWrite(enable)` ham chaqiriladi. Yoqilganda xabar: *"Sonar endi 1C ga yoza oladi — har bir o'zgarish «Bajarish» dan keyin"* (ya'ni AI avtomatik emas, har safar aniq tasdiq bilan yozadi) — o'chirilganda: *"1C ga yozish o'chirildi — endi faqat o'qiladi"* (`OneCTabViewModel.cs:438`).
  `OneCExecutor`/`WriteGuard` darajasida bu `AllowWrite` qayta tekshiriladi (har bir "write" operatsiyasi uchun) — `ConnectorEngine.SetAllowWrite()` chaqirilganda log: *"1C'ga yozishga ruxsat YOQILDI — faqat buxgalter tasdiqlagan amallar bajariladi"* (`ConnectorEngine.cs:1209`) / *"1C'ga yozishga ruxsat o'chirildi — 1C dan faqat o'qiladi"* (`ConnectorEngine.cs:1213`).
- Mac eslatmasi: `ShowMacNote = !Engine.HasEngine` — Mac'da Engine umuman yo'q, shuning uchun maxsus matn ko'rsatiladi: *"1C (COM) faqat Windows'da ishlaydi. Ofisdagi Windows kompyuterga Sonar'ni o'rnating va shu hisob bilan kiring — u o'zi ulanadi…"* (`Uz.cs:3601`).

### 4.7 Uzbek matn namunalari (`Uz.cs`)

- `Uz.ThisPc.ConnectorNo(id) => $"#{id}"` (`Uz.cs:3611-3614`)
- `Uz.ThisPc.DemoAdded(name) => "«" + name + "» qo'shildi"` (`Uz.cs:3621-3624`)
- `Uz.ThisPc.Saved(name) => "«" + name + "» saqlandi — ulanish ishlayapti"` (`Uz.cs:3650-3653`)
- `Uz.ThisPc.RemoveText(name) => "«" + name + "» shu kompyuterdagi Sonar'dan o'chiriladi. 1C bazasining o'ziga tegilmaydi."` (`Uz.cs:3655-3658`)
- `Uz.Setup.Connected(name) => "«" + name + "» ulangan"` (`Uz.cs:4854-4857`)
- `Uz.Setup.Offline(name) => "«" + name + "» ulangan, lekin hozir aloqa yo'q"` (`Uz.cs:4859-4862`)
- `Uz.Setup.SwitchText(name) => "Ish joyi «" + name + "» bazasiga ulanadi. Hisobotlar va 1C dagi o'zgarishlar endi shu bazadan."` (`Uz.cs:4869-4872`)
- `Uz.Setup.NoBasesText == "1C o'rnatilgan kompyuterda Sonar'ni oching va bazani qo'shing — u shu yerda paydo bo'ladi."` (`Uz.cs:4840`)

### 4.8 Xato holatlari (foydalanuvchiga ko'rinadigan matnlar)

`BaseLink.Friendly()` (`src_app/Sonar.Desktop.Core/Sonar.Desktop.Core.Connector/BaseLink.cs:49-63`) — AI-asbob chaqirganda chiqadigan xato xabarlari xaritasi:
- `timeout` → *"1C so'rovi juda uzoq davom etdi — davrni qisqartiring yoki filtr qo'shing"*
- `base_locked` → *"1C bazasi band (monopol rejim yoki yangilanish) — birozdan keyin qayta urinib ko'ring"*
- `access_denied` → *"1C foydalanuvchingizda bu ma'lumotni o'qish huquqi yo'q"*
- `write_disabled` → *"1C ga yozish o'chiq — Sonar dasturida: Sozlamalar → 1C → «1C ga yozishga ruxsat» ni yoqing"*
- `auth_failed` → *"1C ga kirib bo'lmadi: foydalanuvchi nomi yoki paroli noto'g'ri — Sonar → Sozlamalar → 1C da tekshiring"*
- `com_not_registered` → *"1C COM ulagichi ro'yxatdan o'tmagan — Sonar → Sozlamalar → «Muammo bo'lsa» → «COM'ni ro'yxatdan o'tkazish»"*
- `windows_only` → *"1C faqat Windows kompyuterda ishlaydi"*

Bu — har qanday xato kodi ekranda **texnik kod sifatida emas, aniq keyingi harakat bilan** ko'rsatilishini ta'minlovchi markaziy "tarjima" qatlami.

---

## 5. O'rnatuvchi (installer)

Fayllar: `Sonar.Installer/Layout.cs`, `SetupPaths.cs`, `AppInstaller.cs`, `WinShortcuts.cs`, `WinRegistry.cs`, `SetupEnvironment.cs`.

### 5.1 Har-foydalanuvchi (per-user) o'rnatish, admin shart emas

Registratsiya **faqat `HKEY_CURRENT_USER`** ostida (`WinRegistry.cs:9-50` — barcha metodlar `Registry.CurrentUser`). O'rnatish papkasi:
```csharp
public string DefaultInstallDir => Path.Combine(LocalAppData, "Programs", "Sonar");
```
(`SetupPaths.cs:17`) — ya'ni `%LOCALAPPDATA%\Programs\Sonar\`. Bu klassik "per-user, admin kerak emas" Windows o'rnatish patterni (NSIS/Squirrel uslubi). Boshqa muhim yo'llar (`SetupPaths.cs:9-27`): dastur sozlamalari `%AppData%\Sonar`, Engine/Connector sozlamalari `%AppData%\SonarConnector`, Engine loglari `%LocalAppData%\SonarConnector`, yorliqlar — Start Menu (`%Programs%\Sonar.lnk`) va Desktop (`%Desktop%\Sonar.lnk`).

`Sonar.Installer/Program.cs:17-82` — kirish nuqtasi. O'rnatuvchining o'zi ham **bitta nusxada** ishlaydi — nomli mutex `"Local\SonarSetup"` orqali (`Program.cs:43`, `Layout.cs:29`). Ishlash rejimlari (`SetupMode.cs:3-8`): `Install`, `Uninstall`, `UninstallRun`; argumentlar `SetupArgs.cs:18-58`da parse qilinadi: `/S` (sukut/silent), `/restart` (o'rnatilgandan keyin ilovani qayta ishga tushirish — aynan auto-update shu bayroqni ishlatadi, 5.7-bo'limga qarang), `/hidden` (oynasiz, tray rejimida), `/uninstall`, `/uninstall-run <dir>`. Agar exe fayl nomi aynan `uninstall.exe` bo'lsa, rejim avtomatik `Uninstall`ga o'rnatiladi (`SetupArgs.cs:49-52`) — foydalanuvchi "Dasturlar va imkoniyatlar"dan bosganda qo'shimcha flag kerak emas.

### 5.2 Payload va fayllar

```csharp
// Layout.cs:41
public static readonly string[] KnownFiles = {
    "Sonar.exe",
    "workers/SonarWorker32.exe", "workers/SonarWorker32.exe.config",
    "workers/SonarWorker64.exe", "workers/SonarWorker64.exe.config",
    "mcp/SonarMcp.exe", "mcp/SonarMcp.exe.config",
    "uninstall.exe", "sonar-files.txt"
};
```
— payload ichida haqiqatan **4 ta ijrochi fayl** bor: asosiy Desktop GUI (`Sonar.exe`), ikki bitlikdagi 1C-worker (`SonarWorker32/64.exe` — COM-ulanish uchun, 2-bo'limda tasvirlangan izolyatsiya), va MCP-relay (`SonarMcp.exe` — tashqi AI klientlar uchun named-pipe ko'prigi).

`AppInstaller.Extract()` (`AppInstaller.cs:217-270`) payload'ni ZIP sifatida ochadi, har bir faylni avval `.new` qo'shimchasi bilan yozadi (`Sonar.exe.new` va h.k.), so'ng `ReplaceAsync()` orqali asl nom bilan almashtiradi (`AppInstaller.cs:272-293`, qulflangan faylga 10 marta qayta urinish bilan — `_env.ReplaceAttempts`). Bu — **ishlab turgan `.exe`ustiga yozib bo'lmaydi** muammosini chetlab o'tish usuli: avval yangi versiya qo'shni faylga yoziladi, ishlab turgan dastur yopilgandan keyingina asl faylga almashtiriladi.

Zip ichida yo'l-traversal himоyasi bor — `Layout.SafeRelative()` (`Layout.cs:43-60`) `..`, boshida `/`, disk harfini (`:`) yoki bo'sh segmentlarni rad etadi.

O'rnatuvchining kirish matni (`SetupTexts.cs`) foydalanuvchiga mahsulotning asosiy va'dalarini birinchi ekrandanoq aytib beradi: *"Sonar — Sonar AI ning kompyuter dasturi… Windows'da 1C ga ulanish Sonar'ning o'zida — alohida Connector kerak emas / 1C paroli faqat shu kompyuterda, shifrlangan holda saqlanadi / Administrator huquqi kerak emas."* Jarayon davomida ko'rsatiladigan qadamlar: *"Fayllar ochilmoqda…"* → *"Ishlab turgan Sonar yopilmoqda…"* → *"Fayllar almashtirilmoqda…"* → *"Yorliqlar yaratilmoqda…"* → *"«Dasturlar» ro'yxatiga yozilmoqda…"* → *"Tayyor"*.

### 5.3 Yorliqlar

`WinShortcuts.Create()` (`WinShortcuts.cs:10-43`) — **COM orqali** (`WScript.Shell` ProgID, `Type.GetTypeFromProgID`) `.lnk` fayl yaratadi, maqsad `Sonar.exe`, ish papkasi — dastur papkasi, tasvir ikonkasi — exe'ning o'zidan. Ikki joyga: Start Menu (`Programs\Sonar.lnk`) va, foydalanuvchi tanlasa, Desktop (`Desktop\Sonar.lnk`) — `AppInstaller.cs:140-152`.

### 5.4 Registratsiya yozuvlari

`WriteUninstallEntry()` (`AppInstaller.cs:322-340`) — standart Windows "Dasturlar va imkoniyatlar" yozuvi, `HKCU\...\Uninstall\Sonar`: `DisplayName`, `DisplayVersion`, `Publisher="Sonar AI"`, `InstallLocation`, `DisplayIcon`, `UninstallString` (`"<dir>\uninstall.exe" /uninstall`), `QuietUninstallString` (`... /uninstall /S`), `URLInfoAbout` (`https://t.me/sonar_aibot`), `NoModify=1`, `NoRepair=1`, `EstimatedSize` (fayllar yig'indisi, KB), `InstallDate`.

Avtostart (agar avval yoqilgan bo'lsa) — `HKCU\...\Run\Sonar = "<dir>\Sonar.exe" --hidden` (`AppInstaller.cs:158-164, 196-199`) — `--hidden` flag bilan, ya'ni avtomatik ishga tushganda oyna ko'rsatilmaydi, faqat tray.

### 5.5 Ishlab turgan nusxani yopish (yangilashdan oldin)

`CloseAppsAsync()` (`AppInstaller.cs:386-426`): avval `SignalExit()` orqali nazokatli chiqishga 15 soniya beradi (`GracefulTimeout`), javob bo'lmasa process'larni `Kill()` qiladi, keyin **worker process'larni ham** (`SonarWorker32`/`64`) papka bo'yicha o'chiradi (`KillWorkers(appDir)`) — ya'ni asosiy `.exe`dan tashqari uning bola-worker'larini ham tozalaydi.

### 5.6 O'chirish (uninstall)

`UninstallAsync()` (`AppInstaller.cs:442-549`): ishlab turgan nusxani yopadi → (agar `o.Unpair`, `UninstallOptions.cs:5-8`) **kompyuterni Sonar hisobidan uzadi** (`EnginePairing.UnpairAsync`, `EnginePairing.cs:9-22` → `ConnectorEngine.UnpairStoredAsync` — serverga `unpair` so'rovi yuboriladi, token tozalanadi; ekranda: *"Kompyuter Sonar'dan uzilmoqda…"*) → Run-key, yorliqlar, bilingan fayllar, bo'sh papkalar va registry-uninstall-kalitni o'chiradi. `o.KeepSettings` (default **true**) bayrog'i bo'yicha: agar **saqlash** tanlansa — `%APPDATA%\Sonar`, `%APPDATA%\SonarConnector`, `%LOCALAPPDATA%\SonarConnector` papkalari **tegilmaydi** (bazalar/parollar/token qoladi) va shunisi muhimki, keyingi o'rnatishda autostart o'zi yana yoqilib qolmasligi uchun `settings.json` ichidagi `"AutoStartInitialized": true` maydoni `false`ga qaytariladi (`ResetAutoStartFlag` — `AppInstaller.cs:201-215`). Aks holda barcha uchta papka butunlay o'chiriladi. UI matnida ikki variant aniq farqlanadi: saqlash — *"Qayta o'rnatilsa kirish, 1C bazalari, parollar va ulanish joyida bo'ladi."*; o'chirish — *"Kirish, 1C bazalari va ularning parollari, jurnallar o'chiriladi."*

O'rnatish paytida (agar `InstallOptions.RemoveLegacy`, default true) `EngineLegacy.Present()` (`EngineLegacy.cs:9-18`) orqali eski "Sonar Connector" borligi tekshiriladi va topilsa `LegacyConnector.RemoveAsync` chaqiriladi (2.6-bo'limdagi mexanizm bilan bir xil) — ya'ni yangi o'rnatish/yangilanish jarayonining o'zi eski mahsulotni avtomatik tozalaydi, foydalanuvchidan alohida harakat talab qilinmaydi.

`/uninstall` orqali to'g'ridan-to'g'ri chaqirilganda, o'chiruvchi **o'zini `%Temp%`ga nusxalab, o'sha nusxadan qayta ishga tushiradi** (`SonarUninstall-<guid8>.exe`, `Program.cs:108-121,139-160`) — shunday qilib asl `uninstall.exe` o'rnatish papkasi ichida bo'lsa ham, u o'zini-o'zi (ishlab turgan jarayon sifatida qulflangan fayl) muammosiz o'chira oladi.

### 5.7 Avtomatik yangilanish (auto-update)

Fayllar: `src_app/Sonar.Desktop.Core/Sonar.Desktop.Core.Update/{AppUpdater,UpdateService,UpdateCheck,UpdateInfo,UpdateOptions,UpdateStatus,UpdateTexts,ExitSignal}.cs`, `Sonar.Core/UpdateVerifier.cs`. Faqat Windows'da ishlaydi (`UpdateService.cs:46`: `Supported = OperatingSystem.IsWindows()`).

**Jadval**: `AppUpdater.Start()` (`AppUpdater.cs:216-231`) ishga tushgandan 1 daqiqa o'tgach birinchi tekshiruv, keyin har **6 soatda** bir (`FirstCheckDelay`/`CheckInterval`, `AppUpdater.cs:30-31`) — foydalanuvchi hech narsa qilmasa ham fonda o'zi tekshiradi.

**Manifest manzili**: qattiq kodlangan URL yo'q — `UpdateService.ManifestUrl` (`UpdateService.cs:68-78`) joriy API-server manzilidan **nisbiy** `"../app/version.json"` yo'li orqali hisoblanadi (masalan API `https://api.sonar.../v1/` bo'lsa, manifest `https://api.sonar.../app/version.json`). Faqat `https://` (yoki test uchun `http://localhost`) ruxsat etiladi, URL ichida login/parol (userinfo) bo'lishi rad etiladi. Shu tufayli manifest avtomatik ravishda foydalanuvchi ulangan muhitga (prod/staging) mos keladi.

**Tekshirish** (`UpdateService.CheckAsync`, `:81-131`): `GET`, `Cache-Control: no-cache`, `User-Agent: Sonar/<versiya> (update)`, 15 soniya timeout, javob 65536 baytdan oshsa kesib tashlanadi. JSON maydonlari: `version, url, sha256, size, notes, signature`.

**Raqamli imzo tekshiruvi** (`Sonar.Core/UpdateVerifier.cs`) — RSA-2048/PKCS1/SHA-256 imzo, kanonik satr ustidan: `"<product>|<version>|<url>|<sha256-lowercase>|<size>"` (`Canonical`, `:17-20`), `product = "sonar-desktop-win-x64"` (`UpdateService.cs:38`), dasturga **ichiga quyilgan** (hardcoded) RSA ochiq kaliti bilan tasdiqlanadi (`UpdateOptions.cs:13-17`). Imzo noto'g'ri bo'lsa — yangilanish **o'rnatilmaydi**: *"yangilanish imzosi tasdiqlanmadi — o'rnatilmaydi"*. Versiya qatori formati tekshiriladi: `^\d{1,5}(\.\d{1,5}){1,3}$`; eski/teng versiyalar e'tiborsiz qoldiriladi (`UpdateVerifier.Compare`).

**Yuklab olish** (`DownloadAsync`, `:133-186`): URL faqat `https://`, `size>0`, `sha256` uzunligi 64 bo'lishi shart; `%TEMP%\SonarSetup-<versiya>.exe.part` nomiga oqim sifatida yoziladi, SHA-256 bosqichma-bosqich hisoblanadi, deklaratsiya qilingan hajmdan oshsa — to'xtatiladi; yakunda hajm va hash **to'liq mos kelishi** talab qilinadi, aks holda: *"yuklangan fayl manifestga mos emas (SHA-256) — o'rnatilmaydi"*; muvofiq bo'lsagina `.part` yakuniy nomga ko'chiriladi. 1 kundan eski qolib ketgan `SonarSetup-*.exe*` fayllar avtomatik tozalanadi.

**O'rnatish** (`DownloadAndRunAsync`, `:188-213`): yuklangan `.exe` **xuddi oddiy o'rnatuvchi** sifatida ishga tushiriladi, argumentlar `"/S /restart"` (sukut + avtomatik qayta ishga tushirish), agar dastur hozir tray'da (oyna yashirin) bo'lsa qo'shimcha `" /hidden"`. Keyin ishlab turgan `Sonar.exe` `Local\Sonar.Exit` nomli event orqali yopiladi (5.5-bo'limdagi mexanizmning o'zi) — ya'ni **auto-update butunlay shu installer/payload mexanizmini qayta ishlatadi**, alohida "patch" formati yo'q.

**Foydalanuvchiga ko'rinadigan matn** (`UpdateTexts.cs`): Idle → *"Sonar yangi versiyani o'zi tekshirib turadi"*; Checking → *"Tekshirilmoqda…"*; Available → *"Yangi versiya bor: {0}"* (tugma: *"{0} ni o'rnatish"*); Downloading → *"Yuklanmoqda… {0}%"*; Starting → *"O'rnatuvchi ishga tushdi — Sonar yopiladi va yangi versiyada qayta ochiladi"*. Xatolar: Network → *"internet yoki server bilan aloqa yo'q"*; Timeout → *"server javob bermadi (vaqt tugadi)"*; NoAddress → *"server manzili yo'q (sinov rejimi yoki noto'g'ri manzil)"*; NoManifest → *"serverda yangilanish ma'lumoti hali yo'q"*; BadSignature → *"yangilanish imzosi tasdiqlanmadi — o'rnatilmaydi"*; NotSupported → *"Yangilanish hozircha faqat Windows'da"*.

Xulosa: yangilanish zanjiri **to'rt qatlamli himoyalangan** — HTTPS-only manifest, HTTPS-only yuklash, RSA imzo (manifest soxtalashtirilishiga qarshi) va SHA-256 (yuklash vaqtida buzilish/MITM'ga qarshi) — biror qadam yetishmasa, yangilanish shunchaki o'rnatilmay qoladi, hech qachon "yarim-tekshirilgan" fayl ishga tushirilmaydi.

---

## 6. Serverga bazalarni ro'yxatdan o'tkazish ("hello"/"base" protokoli)

### 6.1 `ApiClient` — transport

`Sonar.Core/ApiClient.cs` — HTTP `POST {server}?a={action}`, JSON body, `X-Sonar-Connector` va `X-Sonar-Token` sarlavhalari + `Authorization: Bearer <token>` (`ApiClient.cs:108-118`). 16 KB'dan katta body gzip bilan siqiladi (`ApiClient.cs:87-98`). Faqat `https://` (yoki `http://localhost`) ruxsat etiladi (`CheckUrl` — `ApiClient.cs:66-78`).

### 6.2 `Agent` — hello/poll sikli

`Sonar.Core/Agent.cs:65-138` — asosiy tsikl:
```csharp
while (!ct.IsCancellationRequested) {
    if (DateTime.UtcNow >= nextHello) { await HelloAsync(ct); nextHello = now + _opt.HelloEvery; } // har 10 daqiqada
    num = await PollAsync(ct);   // tasklarni so'raydi, 250ms–60s moslashuvchan interval
    ...
}
```
`HelloAsync()` (`Agent.cs:145-157`):
```csharp
d = await _api.CallAsync("hello", J.Make("version", opt.Version, "os", opt.Os, "platforms", opt.Platforms(), "bases", opt.Bases()), ct);
```
— ya'ni **har 10 daqiqada** ("HelloEvery" default) connector o'zining butun 1C-platforma ro'yxatini (`Platform.ServerInfo()` — versiya/bitlik/com-holat) va bazalar holatini serverga yuboradi; javobda yangilanish mavjudligi va server tomonidagi bazalar ro'yxati (`ServerBases` event) keladi.

Xato bo'lsa — eksponensial backoff: `{1,2,5,10,30,60}` soniya + tasodifiy jitter (`Agent.cs:24, 140-143`). Server tokenni rad etsa (`ApiException.Revoked`) — Agent butunlay to'xtaydi, holat `Revoked` (*"Ulanish bekor qilingan — botdan yangi kod olib, qayta ulang"*).

Alohida e'tibor: baza ro'yxati o'zgarganda (yangi baza qo'shilsa) Agent 10 daqiqalik taymerni kutib o'tirmaydi — `ConnectorEngine.RequestSync()` darhol navbatdagi `hello`ni so'raydi. Task-natijalarini yuborish (`SendResultAsync`, `Agent.cs:243-289`) alohida qayta-urinish siyosatiga ega: bir xil backoff jadvali bo'yicha 6 martagacha urinadi, lekin `409/404/413/Revoked` kodlarini **qayta urinmaydigan** deb belgilaydi — `413` (juda katta javob) holatida natija `"too_large"` xatosi sifatida qayd etilib, bir marta qayta yuboriladi, cheksiz tsiklga tushib qolmaydi.

### 6.3 Yangi baza — alohida sinxronlash navbati

`ConnectorEngine.SyncPassAsync()` (`src_app/Sonar.Engine/Sonar.Engine/ConnectorEngine.cs:875-930`) — `hello`dan mustaqil, har safar yangi baza qo'shilganda (`SaveBaseAsync` oxirida `SyncBasesAsync(wait:true)` chaqiriladi, `ConnectorEngine.cs:1310`) ishlaydigan navbat:
```csharp
list = _settings.Bases.Where(x => x.Enabled && !x.Registered).ToList();
foreach (b in list) {
    body = J.Make("local_id", b.Id, "name", b.Name, "kind", b.Kind,
                   "config", J.Make("name", b.ConfigName, "synonym", b.ConfigSynonym, "version", b.ConfigVersion),
                   "platform", b.Platform, "status", (b.LastError != "") ? "error" : "ok");
    serverId = await api.CallAsync("base", body, ct);
    b.Registered = true; b.ServerId = serverId;
}
```
(`ConnectorEngine.cs:886-908`) — server `local_id ↔ base_id` xaritasini qaytaradi, u `BaseConfig.ServerId`ga yoziladi va `Registered=true` qo'yiladi. **Login/parol bu yerda hech qachon yo'q** — faqat metama'lumot (nom, tur, konfiguratsiya versiyasi, oxirgi holat).

### 6.4 Serverdan qaytuvchi boshqaruv

`OnServerBases()` (`ConnectorEngine.cs:795-841`) — `hello` javobidagi `bases` massivi orqali server **masofadan** bazani o'chirib qo'yishi mumkin (masalan, Telegram-bot orqali "Bazani uzish" buyrug'i bilan):
```csharp
if (!J.Bool(item, "active", def: true) && baseConfig.Enabled) {
    baseConfig.Enabled = false;
    PostNotify("Baza uzildi", "«"+name+"» Telegram bot orqali Sonar'dan uzildi.");
}
```
(`ConnectorEngine.cs:817-822`) — ya'ni "manage" oqimi ikki tomonlama: Desktop serverni yangilaydi, server ham Desktop'ni masofadan boshqara oladi (masalan tarif tugashi, admin tomonidan bazani o'chirish).

### 6.5 UI darajasidagi DTO'lar (`Sonar.Desktop.Core.Api`/`.Connector`)

Bu qatlam — AI-asbob (MCP/tool-call) tomonidan **aniq qaysi bazaga** murojaat qilinayotganini yuritadi, server-registratsiyadan farqli (6.1-6.4 — Engine darajasi, bu esa UI/AI qatlami):

- `ConnectorInfo`/`ConnectorBaseInfo` (`Sonar.Desktop.Core.Api/ConnectorInfo.cs`, `ConnectorBaseInfo.cs`) — **boshqa kompyuterlar** haqida (ThisPc'dagi "Boshqa kompyuterlar" ro'yxati uchun): `Id`, `Name`, `Version`, `Online`, `LastSeen`, `Bases: List<ConnectorBaseInfo>` (har biri `Id`, `Name`, `Status`).
- `LocalBase` (record, `Sonar.Desktop.Core.Connector/LocalBase.cs:3`) — **joriy** (shu kompyuterdagi) bazaning o'zgarmas snapshoti: `Id, Name, Config, ConfigVersion, Platform, Demo, Enabled, LastOk, LastError`.
- `BaseLink` (`BaseLink.cs:9-73`) — `LocalBase` + `IOneCRunner` + `MetaCache` birlashtirilgan "ishlaydigan ulanish" — AI-asbob (`query`/`batch`) so'rovlari shu orqali `OneCExecutor.RunAsync`ga yuboriladi (`Runner.RunAsync(Base.Id, op, prms, timeout, ct)`).
- `BaseProfile` (record, `BaseProfile.cs:5-25`) — serverdan olinadigan, 1C konfiguratsiyasi bo'yicha "profil" (qaysi ma'lumot manbalari mavjud/yo'q — `Source(kind)`/`Missing(kind)`), 10 daqiqalik keshlanadi (`ConnectorHost.cs:23, 99-124`).

---

## Nima uchun foydalanuvchiga qulay

1. **Avtomatik topish — qo'lda ulanish satrini yozish shart emas.** `ibases.v8i`ni o'qish orqali, foydalanuvchi allaqachon 1C:Enterprise ishga tushirish oynasida ko'rayotgan bazalar ro'yxati **aynan shu ro'yxat** sifatida Sonar'da ham chiqadi — foydalanuvchi "server qayerda, baza nomi qanday" deb o'ylab o'tirmaydi.
2. **"Avval test, keyin saqlash" qoidasi** (`EngineBaseDialogViewModel.SaveAsync`) — foydalanuvchi hech qachon "ishlamaydigan baza" bilan qolmaydi: saqlash tugmasining o'zi sinov. Xato chiqsa, darhol tushunarli va amaliy maslahat (`BaseLink.Friendly`, `ErrorTexts`) — texnik kod emas.
3. **Bitlik/ProgID avtomatik tanlanadi va o'zi tuzatiladi** — foydalanuvchi "32 yoki 64-bit" deb bosh qotirmaydi (`"auto"` default), xato taxmin qilinsa tizim o'zi muqobil bitlikka o'tib ko'radi va sozlamani tuzatib qo'yadi.
4. **COM-registratsiya muammosi bitta tugma bilan hal qilinadi** ("Tuzatish"/"COM'ni ro'yxatdan o'tkazish") — foydalanuvchi `regsvr32`, registry, CLSID haqida bilishi shart emas.
5. **Login — parolsiz, Telegram-bot orqali kod/QR** — yangi parol o'ylab topish, uni unutish xavfi yo'q; ikkinchi faktor sifatida Telegram akkaunti ishlatiladi.
6. **Kompyuterni hisobga ulash (pairing) butunlay shaffof/avtomatik** — foydalanuvchi "kod kiritish" bilan ovora bo'lmaydi; bu faqat konflikt holatida (boshqa hisob allaqachon egalik qilganda) tasdiq so'raladi.
7. **Ikki bosqichli "1C ga yozish" qulfi** (kompaniya darajasi + shu kompyuter darajasi) — xavfli amal (1C ma'lumotini o'zgartirish) tasodifan yoqilib qolmaydi, lekin ikkala tomon ham (buxgalter serverda, texnik xodim kompyuterda) alohida nazorat qila oladi.
8. **Parollar hech qachon diskda ochiq yotmaydi va serverga yuborilmaydi** — DPAPI/CurrentUser shifrlash, faqat metama'lumot sinxronizatsiyasi.
9. **Eski mahsulot (Sonar Connector) bilan ziddiyat avtomatik aniqlanadi va tozalanadi**, foydalanuvchi sozlamalari/bazalari yo'qolmasligi alohida kafolatlangan (`SafeInstallDir` tekshiruvi).
10. **O'rnatish/yangilash admin huquqisiz** (per-user), fon rejimida avtomatik yangilanadi (RSA-imzo + SHA-256 bilan tasdiqlangan, 5.7-bo'lim) — foydalanuvchi versiya raqami haqida umuman o'ylamaydi va zararli/buzilgan yangilanish fayli hech qachon o'rnatilmaydi.

## O'z ilovamizda takrorlash uchun xulosa

Python (yoki boshqa) ilovada xuddi shunday "1C bazasini topish va sozlash" tajribasini qurish uchun:

1. **Discovery modul** — `%APPDATA%\1C\1CEStart\ibases.v8i` va `1CEStart.cfg`dagi `CommonInfoBases=` yo'llarini o'qiydigan kichik INI-parser (Python: `configparser` mos kelmaydi, chunki format qat'iy emas — qo'l yozilgan satr-parser kerak, yuqoridagi `IbasesParser.Parse` logikasi andoza bo'ladi). BOM-aniqlashni (`UTF-16LE`/`UTF-8`) unutmaslik kerak. Faqat `File=`/`Srvr=+Ref=` turlarini qoldirish, `ws=` (veb)ni chetlab o'tish, `Connect` satri bo'yicha dedup qilish.
2. **Platforma/COM-connector detektori** — Windows'da `winreg` moduli orqali `HKEY_CLASSES_ROOT\V8x.COMConnector\CLSID` va `HKEY_CLASSES_ROOT\CLSID\{...}\InprocServer32`ni ikkala `KEY_WOW64_32KEY`/`KEY_WOW64_64KEY` bilan o'qish; `Program Files`/`Program Files (x86)`dagi `1cv8\8.*\bin\comcntr.dll` mavjudligini tekshirish. Ro'yxatdan o'tmagan bo'lsa — `subprocess` orqali `regsvr32 /s <dll>`ni **administrator sifatida** (`ShellExecuteEx` + `runas`, Python'da `ctypes.windll.shell32.ShellExecuteW`) ishga tushirish, xatolik kodi 1223'ni "foydalanuvchi UAC'ni rad etdi" deb talqin qilish.
3. **1C bilan aloqa — alohida bitlik-mos worker-process orqali**, chunki Python (odatda 64-bit) 32-bit COM-serverga to'g'ridan-to'g'ri ulanolmaydi. Yechim: kichik .NET/C# (yoki alohida 32-bit Python) worker-exe yozib, unga stdin/stdout orqali JSON-RPC (xuddi `WorkerHost`dagi kabi, har bir xabar bitta qatorda, `id` bilan moslashtirilgan) protokol qurish. Bu — eng muhim arxitektura qarori, osonlik bilan chetlab o'tib bo'lmaydi.
4. **Config saqlash** — JSON fayl, `%APPDATA%\<AppName>\settings.json`, yozishda **atomik almashtirish** (`.tmp` + `os.replace`). Parollarni `pywin32`ning `win32crypt.CryptProtectData`/`CryptUnprotectData` (DPAPI, `CRYPTPROTECT_UI_FORBIDDEN`, entropy-bayt bilan) orqali shifrlash — Python ekvivalenti to'g'ridan-to'g'ri mavjud. Parolni hech qachon umumiy "connect string" ichida saqlamaslik — alohida maydon, runtime'da birlashtirish.
5. **Baza qo'shish UX** — "ro'yxatdan tanlash" (`list`) va "qo'lda kiritish" (`manual`) ikki rejimli forma, **"Saqlash" tugmasi = sinov ulanishi**; muvaffaqiyatsiz bo'lsa hech narsa saqlanmasin. Xato kodlarini inson tiliga tarjima qiluvchi markaziy lug'at (`dict[str, str]`) yuritish — texnik xato matnini to'g'ridan-to'g'ri ko'rsatmaslik.
6. **Login — parolsiz pairing** (QR + qisqa kod + Telegram/boshqa bot, 2 soniyalik poll, muddat bilan) — bu klassik "device authorization grant" (OAuth 2.0 Device Flow, RFC 8628)ga juda yaqin; tayyor kutubxona (`oauthlib`) yoki shunga o'xshash oqimni qo'lda yozish mumkin.
7. **Ikki darajali ruxsat** (global/kompaniya darajasi serverda + lokal/kompyuter darajasi) — har qanday "xavfli yozish" funksiyasi uchun umumiy patern sifatida takrorlash tavsiya etiladi: ikkisi ham `True` bo'lmaguncha amalni bajarmaslik.
8. **O'rnatuvchi** — per-user o'rnatish (`%LOCALAPPDATA%\Programs\<App>`), faqat `HKCU` registrini ishlatish — bu admin-huquqisiz ishlashni ta'minlaydi; `regsvr32` va DCOM uchun esa alohida, aniq belgilangan "elevation" so'rovi (faqat kerak bo'lganda).
9. **Auto-update** — imzolangan (RSA yoki Ed25519) manifest-fayl (`version.json`) + SHA-256 tekshiruv bilan yuklab olish, keyin yangi `.exe`ni jim rejimda (`/S /restart`) ishga tushirish; fon rejimida tray'da bo'lgandagina avtomatik o'rnatish, oyna ochiq bo'lsa foydalanuvchiga tanlov berish.
10. **Legacy-tozalash qatlami** — agar mahsulot nomi/formatini kelajakda o'zgartirish rejalashtirilsa, oldindan "eski versiya aniqlash + xavfsiz tozalash" modulini yozib qo'yish (yo'l-whitelist tekshiruvi bilan) — foydalanuvchi migratsiyasini og'riqsiz qiladi.
