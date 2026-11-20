// Free, deterministic news calendar input. C# 5 / .NET Framework 4 compatible.
// This code has no NinjaTrader/order/account API. It only publishes V5 data.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Xml;
using NinjaTrader.NinjaScript.Strategies;

namespace HY.News
{
    public sealed class NewsEvent
    {
        public DateTime Utc;
        public string Label;
        public NewsEvent(DateTime utc, string label) { Utc = utc; Label = label; }
    }

    public static class FreeCalendar
    {
        public const string Version = "HY-FRED-FED-1";
        private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        private static readonly Encoding Utf8 = new UTF8Encoding(false);
        private static readonly DateTime Epoch = new DateTime(1970,1,1,0,0,0,DateTimeKind.Utc);
        private const string Header = "model,date_et,window_start_utc_ns,window_end_utc_ns,label";
        private static readonly string[] Models = { "ES_RAPID_FUNDED", "NQ_TRADEDAY_BOTH" };

        public static TimeZoneInfo Eastern()
        {
            try { return TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); }
            catch (TimeZoneNotFoundException) { return TimeZoneInfo.FindSystemTimeZoneById("America/New_York"); }
        }
        private static void Need(bool ok, string message)
        { if (!ok) throw new InvalidDataException(message); }
        private static string Day(DateTime value) { return value.ToString("yyyy-MM-dd", Inv); }
        private static string Z(DateTime value) { return value.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'",Inv); }
        public static string Hash(byte[] bytes)
        { using (var h=SHA256.Create()) return BitConverter.ToString(h.ComputeHash(bytes)).Replace("-","").ToLowerInvariant(); }
        private static XmlDocument Xml(string text)
        {
            var doc = new XmlDocument { XmlResolver = null };
            var settings = new XmlReaderSettings { DtdProcessing=DtdProcessing.Prohibit, XmlResolver=null };
            using (var sr=new StringReader(text)) using (var xr=XmlReader.Create(sr,settings)) doc.Load(xr);
            return doc;
        }
        private static DateTime ParseDay(string text)
        {
            DateTime d;
            Need(DateTime.TryParseExact(text,"yyyy-MM-dd",Inv,DateTimeStyles.None,out d),"Invalid release date");
            return d.Date;
        }
        private static void SourceBody(string text)
        {
            Need(text!=null && text.Length>=100 && text.Length<=3000000,"Empty/oversized official response");
            Need(!Regex.IsMatch(text,"access denied|request rejected|captcha|403 forbidden",RegexOptions.IgnoreCase),"Official source refused access");
        }

        // FRED gives source release DATES, not release clock times. The 08:30 ET
        // mapping is a frozen, explicitly reviewed BLS schedule assumption.
        public static List<NewsEvent> ParseFred(string xml, int id, DateTime first, DateTime last)
        {
            Need(id==50 || id==10,"Unapproved FRED release id");
            SourceBody(xml);
            var root=Xml(xml).DocumentElement;
            Need(root!=null && root.Name=="release_dates","FRED response is not release_dates");
            var rows=root.SelectNodes("release_date"); int count,offset;
            Need(Int32.TryParse(root.GetAttribute("count"),out count) && Int32.TryParse(root.GetAttribute("offset"),out offset)
                && offset==0 && count==rows.Count && count>0,"Incomplete/paginated/empty FRED response");
            var days=new SortedSet<DateTime>();
            foreach (XmlElement row in rows)
            {
                Need(row.GetAttribute("release_id")==id.ToString(Inv),"Wrong FRED release id");
                var d=ParseDay(row.InnerText.Trim());
                Need(d>=first && d<=last,"FRED date outside requested range");
                Need(d.DayOfWeek!=DayOfWeek.Saturday && d.DayOfWeek!=DayOfWeek.Sunday,"Unexpected weekend release needs review");
                Need(days.Add(d),"Duplicate FRED release date");
            }
            for (var m=first; m<=last; m=m.AddMonths(1))
            {
                int n=0; foreach(var d in days) if (d.Year==m.Year && d.Month==m.Month) n++;
                Need(n==1,"FRED must confirm one named monthly release per covered month; exceptions need review");
            }
            var result=new List<NewsEvent>();
            foreach(var d in days)
            {
                var et=DateTime.SpecifyKind(d.AddHours(8).AddMinutes(30),DateTimeKind.Unspecified);
                result.Add(new NewsEvent(TimeZoneInfo.ConvertTimeToUtc(et,Eastern()),id==50?"employment":"cpi"));
            }
            return result;
        }

        private static string Text(string html)
        { return Regex.Replace(WebUtility.HtmlDecode(Regex.Replace(html,"<[^>]+>"," ")),"\\s+"," ").Trim(); }
        public static List<NewsEvent> ParseFed(string html, int year, int month)
        {
            SourceBody(html);
            string heading=new DateTime(year,month,1).ToString("MMMM yyyy",Inv);
            Need(Regex.IsMatch(html,@"class=[""']row-title text-center[""'][\s\S]*?<h4[^>]*>\s*"+Regex.Escape(heading)+@"\s*</h4>"),"Fed month identity changed");
            var section=Regex.Match(html,@"<h4[^>]*>\s*FOMC Meetings\s*</h4>([\s\S]*?)<h4[^>]*>\s*Statistical Releases\s*</h4>");
            Need(section.Success,"Fed FOMC section missing; not evidence of a no-event month");
            var rows=Regex.Matches(section.Groups[1].Value,@"<div class=""col-xs-2"">\s*<p>([\s\S]*?)</p>\s*</div>\s*<div class=""col-xs-7"">([\s\S]*?)</div>\s*<div class=""col-xs-3"">\s*<p>([\s\S]*?)</p>\s*</div>");
            var events=new List<NewsEvent>(); var seen=new HashSet<string>();
            foreach (Match row in rows)
            {
                string clock=Text(row.Groups[1].Value), desc=Text(row.Groups[2].Value), day=Text(row.Groups[3].Value);
                string label;
                // Fed lists this in the same section, but neither frozen
                // provider profile includes it. Explicit exclusion, no catch-all.
                if(desc=="Beige Book") continue;
                if (desc.StartsWith("FOMC Minutes",StringComparison.Ordinal)) label="fomc_minutes";
                else if (desc.StartsWith("FOMC Press Conference",StringComparison.Ordinal)) label="fomc_press_conference";
                else if (desc.StartsWith("FOMC Meeting",StringComparison.Ordinal)) label="fomc";
                else throw new InvalidDataException("Unrecognized Fed FOMC row: "+desc);
                Need(clock==(label=="fomc_press_conference"?"2:30 p.m.":"2:00 p.m."),"Changed/unspecified Fed clock needs review");
                int n; Need(Int32.TryParse(day,NumberStyles.None,Inv,out n),"Ambiguous Fed release day");
                var et=new DateTime(year,month,n,14,label=="fomc_press_conference"?30:0,0,DateTimeKind.Unspecified);
                Need(seen.Add(day+"/"+label),"Duplicate Fed event");
                events.Add(new NewsEvent(TimeZoneInfo.ConvertTimeToUtc(et,Eastern()),label));
            }
            // If event text exists but the layout changed, never publish an empty month.
            int expected=Regex.Matches(section.Groups[1].Value,@"<div class=""col-xs-7"">").Count;
            Need(rows.Count==expected,"Fed row layout changed");
            Need(expected>0 || Regex.IsMatch(Text(section.Groups[1].Value),"No (scheduled )?(FOMC )?(meetings|events)",RegexOptions.IgnoreCase),
                "Fed empty section lacks explicit no-event statement");
            return events;
        }

        public static string Download(string url)
        {
            var uri=new Uri(url);
            Need(uri.Scheme=="https" && (uri.Host=="api.stlouisfed.org" || uri.Host=="www.federalreserve.gov"),"Only approved HTTPS sources");
            var request=(HttpWebRequest)WebRequest.Create(uri);
            request.UserAgent="HY-ResearchCalendar/1.0 (+https://github.com/flow1919flow/flow)";
            request.Timeout=25000; request.ReadWriteTimeout=25000; request.AllowAutoRedirect=false;
            // Do not log exception URLs: FRED credentials are in its API query.
            try
            {
                using(var reply=(HttpWebResponse)request.GetResponse())
                {
                    Need(reply.StatusCode==HttpStatusCode.OK,"Official HTTP status was not 200");
                    using(var stream=reply.GetResponseStream()) using(var reader=new StreamReader(stream,Encoding.UTF8))
                    { string text=reader.ReadToEnd(); SourceBody(text); return text; }
                }
            }
            catch(WebException e)
            {
                var reply=e.Response as HttpWebResponse;
                throw new IOException("Official fetch failed: "+uri.Host+uri.AbsolutePath+" HTTP "+(reply==null?"network/timeout":((int)reply.StatusCode).ToString(Inv)));
            }
        }
        private static void WriteNew(string path, string content)
        {
            byte[] bytes=Utf8.GetBytes(content);
            using(var fs=new FileStream(path,FileMode.CreateNew,FileAccess.Write,FileShare.Read))
            { fs.Write(bytes,0,bytes.Length); fs.Flush(true); }
        }
        private static string EventRow(string model,NewsEvent e)
        {
            long ns=checked((e.Utc.Ticks-Epoch.Ticks)*100);
            return model+","+Day(TimeZoneInfo.ConvertTimeFromUtc(e.Utc,Eastern()))+","+(ns-120000000000L).ToString(Inv)+","+(ns+120000000000L).ToString(Inv)+","+e.Label;
        }

        // Keep history immutable and never erase/move a previously announced
        // future event automatically. That requires a new explicit source review.
        public static string Publish(string manifest, string destination, List<NewsEvent> events,
            DateTime first, DateTime last, DateTime checkedUtc, string provenanceXml)
        {
            Need(checkedUtc.Kind==DateTimeKind.Utc,"UTC verification clock required");
            var nowEt=TimeZoneInfo.ConvertTimeFromUtc(checkedUtc,Eastern());
            Need(first.Day==1 && last==new DateTime(last.Year,last.Month,1).AddMonths(1).AddDays(-1)
                && first<=nowEt.Date && last>=nowEt.Date.AddDays(28),"Insufficient complete-month forward coverage");
            var old=HYNewsCalendarV5.Load(manifest,Eastern());
            var root=Xml(File.ReadAllText(manifest)).DocumentElement;
            string csvPath=Path.Combine(Path.GetDirectoryName(manifest),root.GetAttribute("csvFile"));
            var all=new SortedDictionary<string,string>(StringComparer.Ordinal);
            var regenerated=new HashSet<string>(StringComparer.Ordinal);
            foreach(var model in Models)
            {
                var byDay=new Dictionary<string,List<string>>();
                foreach(var e in events)
                {
                    var d=TimeZoneInfo.ConvertTimeFromUtc(e.Utc,Eastern()).Date;
                    Need(d>=first && d<=last,"Extracted event outside source coverage");
                    if(e.Label=="fomc_press_conference" && model!="ES_RAPID_FUNDED") continue;
                    string row=EventRow(model,e), day=Day(d);
                    Need(regenerated.Add(row),"Duplicate extracted event");
                    if(!byDay.ContainsKey(day)) byDay.Add(day,new List<string>());
                    byDay[day].Add(row);
                }
                for(var d=nowEt.Date;d<=last;d=d.AddDays(1))
                {
                    List<string> rows;
                    if(!byDay.TryGetValue(Day(d),out rows)) rows=new List<string>{model+","+Day(d)+",,,NO_EVENTS"};
                    rows.Sort(StringComparer.Ordinal);
                    for(int i=0;i<rows.Count;i++) all.Add(model+"/"+Day(d)+"/"+i.ToString("D3",Inv),rows[i]);
                }
            }
            string[] oldRows=File.ReadAllLines(csvPath);
            for(int i=1;i<oldRows.Length;i++)
            {
                var f=oldRows[i].Split(','); var day=ParseDay(f[1]);
                if(day>=nowEt.Date && day<=last)
                {
                    if(f[4]!="NO_EVENTS") Need(regenerated.Contains(oldRows[i]),"Known future event disappeared/moved; manual primary-source review required");
                }
                else all.Add(f[0]+"/"+f[1]+"/old"+i.ToString("D8",Inv),oldRows[i]);
            }
            var csv=new StringBuilder(Header+"\n"); foreach(var row in all.Values) csv.Append(row).Append('\n');
            Directory.CreateDirectory(destination);
            string stamp=checkedUtc.ToString("yyyyMMdd'T'HHmmss'Z'",Inv), stem="HYNewsCalendarV5-"+stamp;
            string csvNew=Path.Combine(destination,stem+".csv"), evidence=Path.Combine(destination,stem+".xml");
            // Provenance has no credentials and is validated before any file write.
            var proof=Xml(provenanceXml);
            Need(proof.DocumentElement.GetAttribute("version")==Version,"Provenance version missing");
            WriteNew(csvNew,csv.ToString()); WriteNew(evidence,provenanceXml);
            var doc=new XmlDocument(); var r=doc.CreateElement("HYNewsCalendar"); doc.AppendChild(r);
            string[,] attrs={{"schema","HY-T1-PARITY-1"},{"timezone","America/New_York"},{"scope","frozen_named_t1_only"},
                {"coveredFrom",Day(old.CoveredFrom<first?old.CoveredFrom:first)},
                {"coveredThrough",Day(old.CoveredThrough>last?old.CoveredThrough:last)},
                {"verifiedAtUtc",Z(checkedUtc)},{"expiresAtUtc",Z(checkedUtc.AddHours(24))},
                {"csvFile",Path.GetFileName(csvNew)},{"csvSha256",Hash(File.ReadAllBytes(csvNew))},
                {"provenanceFile",Path.GetFileName(evidence)},{"provenanceSha256",Hash(File.ReadAllBytes(evidence))}};
            for(int i=0;i<attrs.GetLength(0);i++) r.SetAttribute(attrs[i,0],attrs[i,1]);
            string pending=Path.Combine(destination,"HYNewsCalendarV5."+stamp+".pending.xml");
            WriteNew(pending,doc.OuterXml);
            HYNewsCalendarV5.Load(pending,Eastern()); // Same reader used by the actual four Sims.
            string final=Path.Combine(destination,"HYNewsCalendarV5.xml");
            // Manifest is the commit point. Both immutable companion files exist first.
            if(File.Exists(final)) File.Replace(pending,final,Path.Combine(destination,"HYNewsCalendarV5.before-"+stamp+".xml"));
            else File.Move(pending,final);
            return final;
        }

        public static string Refresh(string manifest, string destination, string key, string receipts, DateTime nowUtc)
        {
            Need(Regex.IsMatch(key??"","^[a-z0-9]{32}$"),"FRED personal API key missing/invalid");
            var today=TimeZoneInfo.ConvertTimeFromUtc(nowUtc,Eastern()).Date;
            var first=new DateTime(today.Year,today.Month,1); var last=first.AddMonths(2).AddDays(-1);
            var events=new List<NewsEvent>(); var doc=new XmlDocument(); var proof=doc.CreateElement("FreeNewsSources"); doc.AppendChild(proof);
            proof.SetAttribute("version",Version); proof.SetAttribute("startedAtUtc",Z(nowUtc));
            proof.SetAttribute("coverageFrom",Day(first)); proof.SetAttribute("coverageThrough",Day(last));
            proof.SetAttribute("historicalScheduleVintages","not_established");
            proof.SetAttribute("blsReleaseClock","08:30 America/New_York; frozen reviewed schedule mapping; FRED API dates only");
            proof.SetAttribute("scope","frozen named T1 only; MFF broader wording remains unresolved");
            string receipt=Path.Combine(receipts,nowUtc.ToString("yyyyMMdd'T'HHmmss'Z'",Inv)); Directory.CreateDirectory(receipt);
            foreach(int id in new[]{50,10})
            {
                string publicUrl="https://api.stlouisfed.org/fred/release/dates?release_id="+id.ToString(Inv)+"&file_type=xml&include_release_dates_with_no_data=true&realtime_start="+Day(first)+"&realtime_end="+Day(last)+"&limit=10000&offset=0&sort_order=asc";
                string body=Download(publicUrl+"&api_key="+Uri.EscapeDataString(key));
                events.AddRange(ParseFred(body,id,first,last));
                string file="fred-release-"+id.ToString(Inv)+".xml"; WriteNew(Path.Combine(receipt,file),body);
                var source=doc.CreateElement("source");source.SetAttribute("urlWithoutCredential",publicUrl);
                source.SetAttribute("file",file);source.SetAttribute("sha256",Hash(Utf8.GetBytes(body)));source.SetAttribute("checkedAtUtc",Z(DateTime.UtcNow));proof.AppendChild(source);
            }
            for(var m=first;m<=last;m=m.AddMonths(1))
            {
                string url="https://www.federalreserve.gov/newsevents/"+m.ToString("yyyy-MMMM",Inv).ToLowerInvariant()+".htm";
                string body=Download(url); events.AddRange(ParseFed(body,m.Year,m.Month));
                string file="fed-"+m.ToString("yyyy-MM",Inv)+".html";WriteNew(Path.Combine(receipt,file),body);
                var source=doc.CreateElement("source");source.SetAttribute("urlWithoutCredential",url);source.SetAttribute("file",file);
                source.SetAttribute("sha256",Hash(Utf8.GetBytes(body)));source.SetAttribute("checkedAtUtc",Z(DateTime.UtcNow));proof.AppendChild(source);
            }
            var verified=DateTime.UtcNow;
            Need(verified>=nowUtc && verified-nowUtc<TimeSpan.FromMinutes(10),"Clock changed/stale source acquisition");
            proof.SetAttribute("verifiedAtUtc",Z(verified));
            WriteNew(Path.Combine(receipt,"sources.xml"),doc.OuterXml);
            return Publish(manifest,destination,events,first,last,verified,doc.OuterXml);
        }
    }
}
