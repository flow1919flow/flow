using System;
using System.Collections.Generic;
using System.IO;
using HY.News;
using NinjaTrader.NinjaScript.Strategies;

class FreeCalendarHarness
{
    static int tests;
    static void Check(bool ok,string text) { tests++;if(!ok)throw new Exception(text); }
    static void Reject(Action action,string text) { bool rejected=false;try{action();}catch{rejected=true;}Check(rejected,text); }
    static string Fred(int id,string a,string b) { return "<release_dates count='2' offset='0'><release_date release_id='"+id+"'>"+a+"</release_date><release_date release_id='"+id+"'>"+b+"</release_date></release_dates>"; }
    static void Main(string[] args)
    {
        string samples=args[0],baseManifest=args[1],dest=args[2];
        var first=new DateTime(2026,11,1);var last=new DateTime(2026,12,31);var now=new DateTime(2026,11,20,20,30,0,DateTimeKind.Utc);
        string nfp=Fred(50,"2026-11-06","2026-12-04"),cpi=Fred(10,"2026-11-10","2026-12-10");
        var e=FreeCalendar.ParseFred(nfp,50,first,last);Check(e.Count==2,"NFP parsed");
        Check(e[1].Utc==new DateTime(2026,12,4,13,30,0,DateTimeKind.Utc),"winter DST 08:30 ET -> 13:30 UTC");
        var summer=FreeCalendar.ParseFred(Fred(50,"2026-05-08","2026-06-05"),50,new DateTime(2026,5,1),new DateTime(2026,6,30));
        Check(summer[0].Utc.Hour==12,"summer DST 08:30 ET -> 12:30 UTC");
        Reject(delegate{FreeCalendar.ParseFred(nfp.Replace("count='2'","count='3'"),50,first,last);},"pagination refused");
        Reject(delegate{FreeCalendar.ParseFred(nfp.Replace("2026-12-04","2026-11-04"),50,first,last);},"missing future month refused");
        Reject(delegate{FreeCalendar.ParseFred(nfp.Replace("release_id='50'","release_id='10'"),50,first,last);},"wrong id refused");
        Reject(delegate{FreeCalendar.ParseFred(nfp.Replace("2026-12-04","2026-12-05"),50,first,last);},"weekend refused");
        Reject(delegate{FreeCalendar.ParseFred("<error code='403'>Access Denied</error>",50,first,last);},"source failure refused");
        e.AddRange(FreeCalendar.ParseFred(cpi,10,first,last));
        string nov=File.ReadAllText(Path.Combine(samples,"fed-november.html"));
        string dec=File.ReadAllText(Path.Combine(samples,"fed-december.html"));
        var ne=FreeCalendar.ParseFed(nov,2026,11);Check(ne.Count==1 && ne[0].Label=="fomc_minutes" && ne[0].Utc.Day==18,"real Fed November");
        var de=FreeCalendar.ParseFed(dec,2026,12);Check(de.Count==3,"real Fed December");e.AddRange(ne);e.AddRange(de);
        Reject(delegate{FreeCalendar.ParseFed(dec,2026,11);},"wrong Fed month refused");
        Reject(delegate{FreeCalendar.ParseFed(dec.Replace("2:30 p.m.","3:30 p.m."),2026,12);},"changed Fed time refused");
        Reject(delegate{FreeCalendar.ParseFed(dec.Replace("col-xs-7","different"),2026,12);},"empty malformed Fed refused");
        string proof="<FreeNewsSources version='HY-FRED-FED-1' purpose='SYNTHETIC_UNIT_TEST_NOT_LIVE_FRED_API'/>";
        string pointer=FreeCalendar.Publish(baseManifest,dest,e,first,last,now,proof);
        var cal=HYNewsCalendarV5.Load(pointer,FreeCalendar.Eastern());
        Check(cal.CoveredThrough>=last && cal.ExpiresAtUtc==now.AddHours(24),"native reader accepts generation");
        Check(cal.GateReason("ES_RAPID_FUNDED",new DateTime(2026,12,9,13,57,49),false)==null,"before dispatch lead open");
        Check(cal.GateReason("ES_RAPID_FUNDED",new DateTime(2026,12,9,13,57,50),false)!=null,"dispatch T-130 blocks");
        Check(cal.GateReason("NQ_TRADEDAY_BOTH",new DateTime(2026,12,9,14,2,0),false)!=null,"T+120 blocks");
        Check(cal.GateReason("NQ_TRADEDAY_BOTH",new DateTime(2026,12,9,14,2,1),false)==null,"T+121 opens");
        Check(cal.GateReason("NQ_TRADEDAY_BOTH",new DateTime(2026,12,9,14,30,0),false)==null,"TradeDay no extra press conference");
        Check(cal.GateReason("ES_RAPID_FUNDED",new DateTime(2026,12,9,14,30,0),false)!=null,"frozen ES press conference");
        byte[] before=File.ReadAllBytes(pointer);
        var missing=new List<NewsEvent>();foreach(var x in e)if(x.Label!="cpi")missing.Add(x);
        Reject(delegate{FreeCalendar.Publish(pointer,dest,missing,first,last,now.AddMinutes(1),proof);},"known event deletion refused");
        Check(FreeCalendar.Hash(before)==FreeCalendar.Hash(File.ReadAllBytes(pointer)),"failed refresh leaves manifest identical");
        string pointer2=FreeCalendar.Publish(pointer,dest,e,first,last,now.AddMinutes(2),proof);
        Check(HYNewsCalendarV5.Load(pointer2,FreeCalendar.Eastern()).VerifiedAtUtc==now.AddMinutes(2),"atomic replacement accepted");
        Console.WriteLine("PASS "+tests+" assertions; actual Fed HTML fixtures, synthetic FRED XML; no API/Windows/live-order acceptance claimed.");
    }
}
