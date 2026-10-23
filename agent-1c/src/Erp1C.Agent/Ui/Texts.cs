using System.Collections.Generic;

namespace Erp1C.Agent.Ui
{
    /// <summary>UI texts uz / ru (34 §10.5). Every user-visible string exists in both languages.</summary>
    public static class Texts
    {
        public static string Language { get; set; } = "uz";

        private static readonly Dictionary<string, (string Uz, string Ru)> All = new Dictionary<string, (string, string)>
        {
            ["app.title"] = ("ERP Do'kon agenti", "ERP Агент магазина"),
            ["tray.open"] = ("Ochish", "Открыть"),
            ["tray.pos_code"] = ("Kassani ulash kodi", "Код подключения кассы"),
            ["tray.diag"] = ("Diagnostika paketini saqlash", "Сохранить пакет диагностики"),
            ["tray.exit"] = ("Chiqish", "Выход"),
            ["state.not_paired"] = ("Kompyuterni ERP'ga ulash kerak", "Нужно подключить компьютер к ERP"),
            ["state.connecting"] = ("Serverga ulanmoqda…", "Подключение к серверу…"),
            ["state.online"] = ("Ulangan: {0}", "Подключено: {0}"),
            ["state.offline"] = ("Server bilan aloqa yo'q ({0} dan)", "Нет связи с сервером (с {0})"),
            ["state.restricted"] = ("Obuna cheklangan — vazifalar to'xtatilgan", "Подписка ограничена — задания остановлены"),
            ["state.update"] = ("Agentni yangilash kerak", "Требуется обновление агента"),
            ["state.revoked"] = ("Kompyuter uzilgan — qayta ulang", "Компьютер отключён — подключите заново"),
            ["state.key"] = ("Kompyuterdagi kalit ochilmadi — kompyuterni qayta ulang", "Ключ на компьютере не открылся — подключите компьютер заново"),
            ["tab.status"] = ("Holat", "Состояние"),
            ["tab.pos"] = ("Ulangan kassalar", "Подключённые кассы"),
            ["tab.devices"] = ("Uskunalar", "Оборудование"),
            ["pair.button"] = ("Kompyuterni ulash", "Подключить компьютер"),
            ["pair.unpair"] = ("Kompyuterni uzish", "Отключить компьютер"),
            ["pair.code_hint"] = ("Egasi ERP'da Sozlamalar → Do'kon agentlari → «Kompyuterni ulash» bo'limida shu kodni kiritsin. Kodni hech kimga telefonda aytmang.", "Владелец вводит этот код в ERP: Настройки → Агенты магазина → «Подключить компьютер». Никому не сообщайте код по телефону."),
            ["pair.open_browser"] = ("Brauzerda ochish", "Открыть в браузере"),
            ["pair.timer"] = ("Kod amal qiladi: {0}", "Код действует: {0}"),
            ["pair.expired"] = ("Kod muddati tugadi", "Срок кода истёк"),
            ["pair.denied"] = ("Ulash rad etildi", "Подключение отклонено"),
            ["pair.rate_limited"] = ("Juda ko'p urinish — 1 soatdan keyin qayta urinib ko'ring", "Слишком много попыток — повторите через час"),
            ["pair.new_code"] = ("Yangi kod", "Новый код"),
            ["pair.done"] = ("Ulandi: {0}", "Подключено: {0}"),
            ["pair.confirm_unpair"] = ("Kompyuter ERP'dan uziladi. Davom etilsinmi?", "Компьютер будет отключён от ERP. Продолжить?"),
            ["pos.code"] = ("Kassani ulash kodi: {0} (5 daqiqa amal qiladi)", "Код подключения кассы: {0} (действует 5 минут)"),
            ["pos.new_code"] = ("Kassa uchun kod", "Код для кассы"),
            ["pos.remove"] = ("O'chirish", "Удалить"),
            ["pos.none"] = ("Ulangan kassa yo'q", "Подключённых касс нет"),
            ["dev.printers"] = ("Printerlar (TCP 9100)", "Принтеры (TCP 9100)"),
            ["dev.terminals"] = ("Karta terminallari", "Карточные терминалы"),
            ["dev.fiscal"] = ("Fiskal modul", "Фискальный модуль"),
            ["dev.add"] = ("Qo'shish", "Добавить"),
            ["dev.remove"] = ("O'chirish", "Удалить"),
            ["dev.name"] = ("Nomi", "Название"),
            ["dev.host"] = ("IP manzil (lokal tarmoq)", "IP-адрес (локальная сеть)"),
            ["dev.port"] = ("Port", "Порт"),
            ["dev.driver"] = ("Drayver", "Драйвер"),
            ["dev.provider"] = ("Provayder", "Провайдер"),
            ["dev.invalid_host"] = ("Faqat lokal tarmoq IPv4 manzili (10.x, 172.16–31.x, 192.168.x)", "Только IPv4-адрес локальной сети (10.x, 172.16–31.x, 192.168.x)"),
            ["dev.printer_port"] = ("Printer porti faqat 9100", "Порт принтера только 9100"),
            ["common.ok"] = ("OK", "OK"),
            ["common.cancel"] = ("Bekor qilish", "Отмена"),
            ["clock.skew"] = ("Kompyuter soati {0} daqiqaga noto'g'ri — Windows vaqt sinxronlashini yoqing", "Часы компьютера ошибаются на {0} мин — включите синхронизацию времени Windows"),
            ["diag.saved"] = ("Diagnostika paketi saqlandi: {0}", "Пакет диагностики сохранён: {0}"),
            ["tls.win7"] = ("Windows 7 da TLS 1.2 yoqilmagan — administrator KB3140245 yangilanishini o'rnatsin", "В Windows 7 не включён TLS 1.2 — администратор должен установить обновление KB3140245"),
        };

        public static string T(string key) =>
            All.TryGetValue(key, out var v) ? (Language == "ru" ? v.Ru : v.Uz) : key;

        public static string F(string key, params object[] args) =>
            string.Format(System.Globalization.CultureInfo.CurrentCulture, T(key), args);

        /// <summary>Test hook: every key has both languages.</summary>
        internal static IEnumerable<KeyValuePair<string, (string Uz, string Ru)>> Entries => All;
    }
}
