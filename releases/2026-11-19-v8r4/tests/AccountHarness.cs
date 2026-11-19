using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text.Json;
using NinjaTrader.NinjaScript.Strategies;

class AccountHarness
{
    static int checks;
    static string root;
    static DateTime D(int offset = 0) { return new DateTime(2026, 11, 19).AddDays(offset); }
    static void Check(bool c, string message) { checks++; if (!c) throw new Exception(message); }
    static string Id(HYAccountProfileV8 p, string suffix) { return HYAccountReplayV8.Identity("SimTest"+suffix, "Strategy", p); }
    static string Seed(HYAccountProfileV8 p, string suffix, Action<HYAccountStateV8> amend = null)
    {
        string directory = Path.Combine(root, suffix);
        string identity = Id(p, suffix);
        var state = new HYAccountStateV8 { Identity = identity, Profile = p.ToString(), Epoch = suffix,
            EpochStartTicks = D().Ticks, Provenance = "explicit isolated harness seed" };
        if (amend != null) amend(state);
        HYAccountReplayV8.WriteSeed(Path.Combine(directory, "seeds", HYAccountReplayV8.FileName(identity)), state);
        return directory;
    }
    static HYAccountReplayV8 Open(HYAccountProfileV8 p, string suffix, string dir) { return new HYAccountReplayV8(dir, Id(p,suffix),p); }
    static void Fill(HYAccountReplayV8 b, string id, bool entry, int side, decimal price, DateTime time)
    { Check(b.Reserve(id),"reserve "+id); Check(b.Fill(id,entry,side,price,time),"fill "+id); }
    static void Structural()
    {
        foreach (HYAccountProfileV8 p in Enum.GetValues(typeof(HYAccountProfileV8)))
        {
            string key = p+"-restart", dir = Seed(p,key);
            long balance, floor;
            using (var b=Open(p,key,dir))
            {
                b.StartDay(D(),D().AddHours(17));
                Fill(b,"e",true,1,10000m,D().AddHours(10));
                Check(!b.CloseDay(D().AddHours(16),false,false),"no early EOD");
                Fill(b,"x",false,1,10010m,D().AddHours(11));
                balance=b.BalanceCents;
                Check(b.CloseDay(D().AddHours(17),true,false),"EOD"); floor=b.FloorCents;
                Check(!b.CloseDay(D().AddHours(18),true,false),"duplicate EOD");
                Check(b.BalanceCents==balance,"EOD does not invent balance");
            }
            using (var b=Open(p,key,dir))
            {
                Check(b.BalanceCents==balance&&b.FloorCents==floor,"restart exact account state");
                Check(b.Fill("x",false,1,10010m,D().AddHours(11)),"replayed exact execution no-op");
                Check(b.BalanceCents==balance,"duplicate fill no fee twice");
                Check(b.KnowsExecution("x",10010m,1,false)&&!b.KnowsExecution("x",10010.25m,1,false),"native fill amendment detected");
                bool locked=false;try { using(var other=Open(p,key,dir)){} }catch(IOException){locked=true;}Check(locked,"exclusive account lock");
                b.StartDay(D(1),D(1).AddHours(13));
                Fill(b,"e2",true,-1,10000m,D(1).AddHours(10));
            }
            using (var b=Open(p,key,dir)) Check(!b.CanEnter&&b.Side==-1&&b.Fault!=null,"open-position restart blocks without erasing exposure");
            string file=Path.Combine(dir,HYAccountReplayV8.FileName(Id(p,key)));
            File.WriteAllText(file,"corrupt"); bool corrupt=false;
            try { using(var b=Open(p,key,dir)){} }catch {corrupt=true;} Check(corrupt,"corrupt primary never rolls back to older backup");
            File.Delete(file);bool missing=false;try {using(var b=Open(p,key,dir)){} }catch{missing=true;}Check(missing,"missing initialized primary never resets account");
        }
        foreach (HYAccountProfileV8 p in Enum.GetValues(typeof(HYAccountProfileV8)))
        {
            bool td=p==HYAccountProfileV8.TradeDayEvaluation||p==HYAccountProfileV8.TradeDayFunded;
            string equal=p+"-equal",equalDir=Seed(p,equal,s=>s.BalanceCents=td?288:287);
            using(var b=Open(p,equal,equalDir))
            {
                b.StartDay(D(),D().AddHours(17));Fill(b,"equal-e",true,-1,10000m,D().AddHours(10));
                Check(b.BalanceCents==0,"profile exact entry fee");
                decimal boundary=10000m+(td?100m:40m);
                Check(b.Mark(boundary,boundary)==td,"exact floor touch differs by provider");
            }
            string key=p+"-floor",dir=Seed(p,key,s=>{s.BalanceCents=-200000;});
            using(var b=Open(p,key,dir))
            {
                b.StartDay(D(),D().AddHours(17));
                // Fill at flat price provides a deterministic post-fill breach for both profiles.
                Fill(b,"floor-e",true,1,10000m,D().AddHours(10));
                Check(b.Breached,"post-entry fee crossing is terminal");
            }
            using(var b=Open(p,key,dir)) Check(b.Breached&&!b.CanEnter,"breach survives restart");
        }
        string k="pending",d=Seed(HYAccountProfileV8.MffEvaluation,k);
        using(var b=Open(HYAccountProfileV8.MffEvaluation,k,d)){b.StartDay(D(),D().AddHours(17));Check(b.Reserve("entry-api-barrier"),"durable intent");}
        using(var b=Open(HYAccountProfileV8.MffEvaluation,k,d))Check(!b.CanEnter&&b.HasPending,"crash before/after API cannot fabricate flat new account");
        k="late";d=Seed(HYAccountProfileV8.TradeDayEvaluation,k);
        using(var b=Open(HYAccountProfileV8.TradeDayEvaluation,k,d)){b.StartDay(D(),D().AddHours(13));Fill(b,"e",true,1,100m,D().AddHours(10));Check(!b.CloseDay(D().AddHours(13),false,false)&&b.Fault!=null,"unflat half-day close blocks account");}
        k="catchup";d=Seed(HYAccountProfileV8.MffEvaluation,k);
        using(var b=Open(HYAccountProfileV8.MffEvaluation,k,d)){b.StartDay(D(),D().AddHours(17));Fill(b,"e",true,1,100m,D().AddHours(10));Fill(b,"x",false,1,101m,D().AddHours(11));}
        using(var b=Open(HYAccountProfileV8.MffEvaluation,k,d)){Check(b.CloseDay(D(4).AddHours(9),true,false),"offline EOD catches up before next entry");b.StartDay(D(4),D(4).AddHours(17));Check(b.CanEnter,"weekend catchup accepts next exchange day");}
        k="write-failure";d=Seed(HYAccountProfileV8.MffEvaluation,k);
        using(var b=Open(HYAccountProfileV8.MffEvaluation,k,d))
        {
            b.StartDay(D(),D().AddHours(17));string file=Path.Combine(d,HYAccountReplayV8.FileName(Id(HYAccountProfileV8.MffEvaluation,k)));
            File.Delete(file); Directory.CreateDirectory(file);
            Check(!b.Reserve("disk-failed")&&!b.CanEnter&&b.Fault!=null,"write failure blocks before API");
        }
        k="fee-mark";d=Seed(HYAccountProfileV8.TradeDayEvaluation,k);
        using(var b=Open(HYAccountProfileV8.TradeDayEvaluation,k,d))
        {
            b.StartDay(D(),D().AddHours(17));Fill(b,"fee-e",true,-1,10000m,D().AddHours(10));
            Check(!b.Mark(10099.75m,10099.75m),"open mark charges entry fee only");
            Check(b.Mark(10100m,10100m),"next tick breaches actual replay floor");
        }
        k="cancelled";d=Seed(HYAccountProfileV8.MffFunded,k);
        using(var b=Open(HYAccountProfileV8.MffFunded,k,d))
        {
            b.StartDay(D(),D().AddHours(17));Check(b.Reserve("first"),"reserve before confirmed cancel");
            b.ConfirmNoFill("different");Check(b.HasPending,"foreign cancel cannot clear durable intent");
            b.ConfirmNoFill("first");Check(!b.HasPending,"exact confirmed cancel releases journal");
            Check(b.Reserve("new"),"new send after confirmed cancel");b.ConfirmNoFill("first");Check(b.HasPending,"old cancel cannot clear newer send");
        }
        foreach(HYAccountProfileV8 p in Enum.GetValues(typeof(HYAccountProfileV8)))
        {
            k=p+"-rollback";d=Seed(p,k);string file=Path.Combine(d,HYAccountReplayV8.FileName(Id(p,k)));byte[] old;
            using(var b=Open(p,k,d))
            {
                b.StartDay(D(),D().AddHours(17));old=File.ReadAllBytes(file);
                Fill(b,"re",true,1,10000m,D().AddHours(10));Fill(b,"rx",false,1,10010m,D().AddHours(11));b.CloseDay(D().AddHours(17),true,false);
            }
            File.WriteAllBytes(file,old);bool rollback=false;try{using(var b=Open(p,k,d)){} }catch{rollback=true;}Check(rollback,"older checksum-valid primary rejected by durable head");
            k=p+"-fault-monitor";d=Seed(p,k);
            using(var b=Open(p,k,d))
            {
                b.StartDay(D(),D().AddHours(17));Fill(b,"me",true,-1,10000m,D().AddHours(10));b.Fail("explicit reconciliation test");
                Check(!b.Snapshot().ReviewRequired && b.Snapshot().ReconciliationReason=="explicit reconciliation test","technical reconciliation is separate from provider lifecycle review");
                bool td=p==HYAccountProfileV8.TradeDayEvaluation||p==HYAccountProfileV8.TradeDayFunded;
                decimal px=10000m+(td?100m:40m);Check(b.Mark(px,px),"fault retains in-memory breach monitoring");
            }
            using(var b=Open(p,k,d)) Check(!b.CanEnter && b.Fault=="explicit reconciliation test","exact reconciliation reason survives process load");
        }
    }
    static void Scenario(string file)
    {
        using(var doc=JsonDocument.Parse(File.ReadAllText(file)))
        foreach(var row in doc.RootElement.EnumerateArray())
        {
            var p=(HYAccountProfileV8)Enum.Parse(typeof(HYAccountProfileV8),row.GetProperty("profile").GetString());
            string key=row.GetProperty("key").GetString(),dir=Seed(p,key);var results=new List<object>();
            using(var b=Open(p,key,dir))
            {
                foreach(var day in row.GetProperty("days").EnumerateArray())
                {
                    int offset=day.GetProperty("offset").GetInt32();DateTime t=D(offset);
                    b.StartDay(t,t.AddHours(day.GetProperty("halfday").GetBoolean()?13:17));
                    long start=b.BalanceCents, low=0; int count=0;var path=new List<object[]>();
                    path.Add(new object[]{t.AddHours(9.5).Ticks,"session_start",0L,0L,null,null});
                    if(b.CanEnter)
                    foreach(var trade in day.GetProperty("trades").EnumerateArray())
                    {
                        int n=count++;bool nq=p==HYAccountProfileV8.TradeDayEvaluation||p==HYAccountProfileV8.TradeDayFunded;
                        int side=trade.GetProperty("side").GetInt32();decimal entry=20000m;
                        decimal move=trade.GetProperty("ticks").GetInt32()*.25m;
                        decimal adverse=trade.GetProperty("adverse").GetInt32()*.25m;
                        var time=t.AddHours(10).AddMinutes(n*10);string id=key+"-"+offset+"-"+n;
                        Fill(b,id+"e",true,side,entry,time);
                        long cash=b.BalanceCents-start;
                        path.Add(new object[]{time.Ticks,"fill_entry",cash,cash,n,2000000});low=Math.Min(low,cash);
                        decimal mark=entry-side*adverse;
                        long eq=cash+(long)(side*(mark-entry)*(nq?2000m:5000m));low=Math.Min(low,eq);
                        path.Add(new object[]{time.AddMinutes(1).Ticks,"quote",eq,cash,n,(long)(mark*100)});
                        b.Mark(mark,mark);
                        decimal exit=entry+side*move;
                        Fill(b,id+"x",false,side,exit,time.AddMinutes(2));
                        cash=b.BalanceCents-start;low=Math.Min(low,cash);
                        path.Add(new object[]{time.AddMinutes(2).Ticks,"fill_exit",cash,cash,n,(long)(exit*100)});
                        if(b.Breached||b.Snapshot().ReviewRequired)break;
                    }
                    long net=b.BalanceCents-start;var close=new DateTime(b.CloseTicks);
                    path.Add(new object[]{close.Ticks,"session_close",net,net,null,null});
                    b.CloseDay(close,true,false);var s=b.Snapshot();
                    results.Add(new{day=t.ToString("yyyy-MM-dd"),net,low,count,path,balance=s.BalanceCents,high=s.HighCents,floor=s.FloorCents,
                        breached=s.Breached,passed=s.EvaluationPassed,review=s.ReviewRequired,terminal=s.TerminalReason,paid=s.PaidNetCents,
                        waiting=s.WaitingNetCents,days=s.ActiveDays,winning=s.WinningDays,payouts=s.PayoutCount});
                    if(b.Breached||s.EvaluationPassed||s.ReviewRequired||!string.IsNullOrEmpty(s.TerminalReason))break;
                }
            }
            Console.WriteLine(JsonSerializer.Serialize(new{key,profile=p.ToString(),results}));
        }
    }
    static void Main(string[] args)
    {
        root=Path.Combine(Path.GetTempPath(),"hy-account-v8-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
        try{Structural();Console.Error.WriteLine("STRUCTURAL_PASS checks="+checks);Scenario(args[0]);}
        finally{Directory.Delete(root,true);}
    }
}
