using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Xml;

namespace NinjaTrader.NinjaScript.Strategies
{
    // Immutable, offline snapshot. No HTTP, subscriptions, credentials or order API.
    internal sealed class HYNewsCalendarV5
    {
        internal const string ESFunded = "ES_RAPID_FUNDED";
        internal const string NQBoth = "NQ_TRADEDAY_BOTH";
        internal sealed class Window
        {
            internal readonly DateTime BeginUtc, EndUtc;
            internal readonly string Label;
            internal DateTime PrecloseUtc { get { return BeginUtc.AddSeconds(-10); } }
            internal Window(DateTime begin, DateTime end, string label)
            { BeginUtc = begin; EndUtc = end; Label = label; }
        }

        internal readonly DateTime CoveredFrom, CoveredThrough, VerifiedAtUtc, ExpiresAtUtc;
        internal readonly string CsvSha256, ProvenanceSha256;
        private readonly TimeZoneInfo eastern;
        private readonly Dictionary<string, HashSet<DateTime>> coverage;
        private readonly Dictionary<string, List<Window>> windows;
        private static readonly DateTime Epoch = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);

        private HYNewsCalendarV5(DateTime first, DateTime last, DateTime verified, DateTime expires,
            string csvHash, string provenanceHash, TimeZoneInfo zone,
            Dictionary<string, HashSet<DateTime>> covered, Dictionary<string, List<Window>> events)
        {
            CoveredFrom = first; CoveredThrough = last; VerifiedAtUtc = verified; ExpiresAtUtc = expires;
            CsvSha256 = csvHash; ProvenanceSha256 = provenanceHash; eastern = zone;
            coverage = covered; windows = events;
        }

        private static void Require(bool ok, string message)
        { if (!ok) throw new InvalidDataException(message); }
        private static DateTime Day(string text)
        {
            DateTime result;
            Require(DateTime.TryParseExact(text, "yyyy-MM-dd", CultureInfo.InvariantCulture,
                DateTimeStyles.None, out result), "Ungültiges Kalenderdatum");
            return result.Date;
        }
        private static DateTime Utc(string text)
        {
            DateTime result;
            Require(DateTime.TryParseExact(text, "yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture,
                DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out result), "Ungültiger UTC-Prüfzeitpunkt");
            return result;
        }
        private static string Hash(byte[] bytes)
        {
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }
        private static string RequiredAttribute(XmlElement element, string name)
        {
            string value = element.GetAttribute(name);
            Require(!string.IsNullOrEmpty(value), "Kalendermanifest: Attribut fehlt " + name);
            return value;
        }
        private static string SafeCompanion(string folder, string name)
        {
            Require(Path.GetFileName(name) == name && name.IndexOfAny(new[] { '/', '\\', ':' }) < 0,
                "Kalenderdatei muss im selben Ordner liegen");
            return Path.Combine(folder, name);
        }

        internal static HYNewsCalendarV5 Load(string manifestPath, TimeZoneInfo easternZone)
        {
            Require(easternZone != null, "Eastern-Zeitzone fehlt");
            var settings = new XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null };
            var document = new XmlDocument { XmlResolver = null };
            using (var reader = XmlReader.Create(manifestPath, settings)) document.Load(reader);
            XmlElement root = document.DocumentElement;
            Require(root != null && root.Name == "HYNewsCalendar" && RequiredAttribute(root, "schema") == "HY-T1-PARITY-1",
                "Unbekanntes Nachrichtenkalender-Schema");
            Require(RequiredAttribute(root, "timezone") == "America/New_York", "Kalenderzeitzone muss America/New_York sein");
            Require(RequiredAttribute(root, "scope") == "frozen_named_t1_only", "Unbekannter Nachrichtenumfang");
            DateTime first = Day(RequiredAttribute(root, "coveredFrom")), last = Day(RequiredAttribute(root, "coveredThrough"));
            DateTime verified = Utc(RequiredAttribute(root, "verifiedAtUtc")), expires = Utc(RequiredAttribute(root, "expiresAtUtc"));
            Require(first <= last && verified < expires && expires <= verified.AddHours(24), "Kalenderabdeckung oder Ablauf ungültig");
            string csvHash = RequiredAttribute(root, "csvSha256"), evidenceHash = RequiredAttribute(root, "provenanceSha256");
            Require(Regex.IsMatch(csvHash, "^[0-9a-f]{64}$") && Regex.IsMatch(evidenceHash, "^[0-9a-f]{64}$"), "Kalenderprüfsumme ungültig");
            string folder = Path.GetDirectoryName(manifestPath);
            byte[] bytes = File.ReadAllBytes(SafeCompanion(folder, RequiredAttribute(root, "csvFile")));
            byte[] provenance = File.ReadAllBytes(SafeCompanion(folder, RequiredAttribute(root, "provenanceFile")));
            Require(Hash(bytes) == csvHash && Hash(provenance) == evidenceHash, "Kalender- oder Herkunftsprüfsumme stimmt nicht");
            var covered = new Dictionary<string, HashSet<DateTime>> {
                { ESFunded, new HashSet<DateTime>() }, { NQBoth, new HashSet<DateTime>() } };
            var events = new Dictionary<string, List<Window>> {
                { ESFunded, new List<Window>() }, { NQBoth, new List<Window>() } };
            var noEvents = new Dictionary<string, HashSet<DateTime>> {
                { ESFunded, new HashSet<DateTime>() }, { NQBoth, new HashSet<DateTime>() } };
            var lastDates = new Dictionary<string, DateTime>();
            using (var csv = new StringReader(Encoding.UTF8.GetString(bytes).TrimStart('\uFEFF')))
            {
                Require(csv.ReadLine() == "model,date_et,window_start_utc_ns,window_end_utc_ns,label", "Kalender-CSV-Kopf ungültig");
                string line;
                while ((line = csv.ReadLine()) != null)
                {
                    Require(line.Length > 0 && !line.Contains("\""), "Leere oder zitierte Kalenderzeile");
                    string[] f = line.Split(','); Require(f.Length == 5 && covered.ContainsKey(f[0]), "Kalender-CSV-Spalten/Modell ungültig");
                    string model = f[0]; DateTime day = Day(f[1]);
                    Require(day >= first && day <= last, "Tageszeile außerhalb Manifestabdeckung");
                    DateTime previousDate;
                    Require(!lastDates.TryGetValue(model, out previousDate) || day >= previousDate, "Kalendertage nicht geordnet");
                    lastDates[model] = day;
                    if (f[4] == "NO_EVENTS")
                    {
                        Require(f[2] == "" && f[3] == "" && !covered[model].Contains(day), "Doppelte/widersprüchliche Leertagesbestätigung");
                        noEvents[model].Add(day); covered[model].Add(day); continue;
                    }
                    Require(!noEvents[model].Contains(day), "Event widerspricht Leertagesbestätigung");
                    Require(f[4] == "employment" || f[4] == "cpi" || f[4] == "fomc" || f[4] == "fomc_minutes"
                        || (model == ESFunded && f[4] == "fomc_press_conference"), "Unbekannte T1-Kategorie");
                    long lo = 0, hi = 0;
                    Require(long.TryParse(f[2], NumberStyles.None, CultureInfo.InvariantCulture, out lo)
                        && long.TryParse(f[3], NumberStyles.None, CultureInfo.InvariantCulture, out hi), "Ungültige UTC-Nanosekunden");
                    Require(lo >= 0 && hi > lo && hi - lo == 240000000000L && lo % 100 == 0 && hi % 100 == 0,
                        "T1-Fenster muss exakt 240 Sekunden und DateTime-kompatibel sein");
                    DateTime begin = Epoch.AddTicks(lo / 100), end = Epoch.AddTicks(hi / 100);
                    Require(TimeZoneInfo.ConvertTimeFromUtc(begin.AddSeconds(120), easternZone).Date == day, "Fensterdatum/Zeitzone widersprüchlich");
                    List<Window> list = events[model];
                    Require(list.Count == 0 || begin.AddSeconds(-10) > list[list.Count - 1].EndUtc, "Nachrichtenfenster überschneiden sich");
                    list.Add(new Window(begin, end, f[4])); covered[model].Add(day);
                }
            }
            Require(covered[ESFunded].Count > 0 && covered[NQBoth].Count > 0, "Kalender enthält keine eindeutige Tagesabdeckung");
            return new HYNewsCalendarV5(first, last, verified, expires, csvHash, evidenceHash, easternZone, covered, events);
        }

        internal DateTime ToUtc(DateTime timeEt)
        { return TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(timeEt, DateTimeKind.Unspecified), eastern); }
        internal string GateReason(string model, DateTime timeEt, bool realtime)
        {
            DateTime utc = ToUtc(timeEt);
            if (realtime && utc < VerifiedAtUtc) return "NEWS-KALENDER PRÜFZEIT IN DER ZUKUNFT";
            if (realtime && utc >= ExpiresAtUtc) return "NEWS-KALENDER ABGELAUFEN · Aktualisierung erforderlich";
            if (!coverage.ContainsKey(model) || !coverage[model].Contains(timeEt.Date))
                return "NEWS-KALENDER FEHLT · " + timeEt.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
            Window active = Active(model, utc);
            return active == null ? null : "T1-NEWS · " + active.Label + " · bis "
                + TimeZoneInfo.ConvertTimeFromUtc(active.EndUtc, eastern).ToString("HH:mm:ss", CultureInfo.InvariantCulture) + " ET gesperrt";
        }
        internal Window Active(string model, DateTime utc)
        {
            List<Window> list;
            if (!windows.TryGetValue(model, out list)) return null;
            foreach (Window w in list)
            {
                if (utc < w.PrecloseUtc) break;
                if (utc <= w.EndUtc) return w;
            }
            return null;
        }
        internal IEnumerable<Window> CrossedOrActive(string model, DateTime fromUtc, DateTime throughUtc)
        {
            List<Window> list;
            if (!windows.TryGetValue(model, out list)) yield break;
            foreach (Window w in list)
            {
                if (w.EndUtc < fromUtc) continue;
                if (w.PrecloseUtc > throughUtc) yield break;
                yield return w;
            }
        }
    }
}
