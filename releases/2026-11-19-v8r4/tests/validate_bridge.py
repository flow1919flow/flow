from pathlib import Path
import sys, json, subprocess, hashlib
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'ES-NQ-Combined-V71-20261119'))
from build_combined import member
SDK=Path('/private/tmp/es-tickzeit-dotnet')
PREFIX='''using System;using System.IO;using System.Collections.Generic;using System.Globalization;
namespace NinjaTrader.Core {public static class Globals {public static string UserDataDir;}}
namespace NinjaTrader.NinjaScript.Strategies {
enum MarketPosition{Flat,Long,Short} enum OrderAction{Buy,BuyToCover,Sell,SellShort}enum OrderState{Cancelled,Rejected,Filled}
class Master{public string Name="ES";}class Inst{public Master MasterInstrument=new Master();}
class Order{public OrderAction OrderAction;public Intent Owner;}class Execution{public Order Order;public Inst Instrument;public DateTime Time;public string ExecutionId;public double Price;public int Quantity=1;}
class Acct{public string Name;public List<Execution> Executions=new List<Execution>();}
class Pos{public int Quantity;public MarketPosition MarketPosition=MarketPosition.Flat;}
class SessionIterator{public static bool Mismatch,Invalid;public static int FalseGaps,Confirmations;private bool confirm;public DateTime ActualTradingDayExchange,ActualSessionBegin,ActualSessionEnd;public SessionIterator(object b){}public bool GetNextSession(DateTime q,bool inc){if(Invalid)return false;if(confirm){Confirmations++;confirm=false;if(Mismatch){ActualSessionEnd=ActualSessionEnd.AddMinutes(1);return true;}return true;}var d=q.Date;bool gap=false;while(d.DayOfWeek==DayOfWeek.Saturday||d.DayOfWeek==DayOfWeek.Sunday||d.Month==12&&d.Day==25){d=d.AddDays(1);gap=true;}ActualTradingDayExchange=d;ActualSessionBegin=d.AddDays(-1).AddHours(18);ActualSessionEnd=d.AddHours(17);if(gap){FalseGaps++;confirm=true;}return !gap;}}
class Intent{public bool IsEntry;public int Side;public string Reason;public Intent(bool e,int s,string r,DateTime t,double stop){IsEntry=e;Side=s;Reason=r;}}
'''
COMMON='''
bool FundedPhase,entryBlocked,modelLossLatched,exitSubmissionFailed;
public bool Permission=true;
double modelRealized,bid,ask,positionStop;int positionSide;long bidSize,askSize;
DateTime bidClock,askClock;DateTime now=new DateTime(2026,11,19,10,0,0);
DateTime sessionOpen=new DateTime(2026,11,19,9,30,0),sessionEnd=new DateTime(2026,11,19,17,0,0);
Intent pending,submitted;Acct Account;Inst Instrument=new Inst();Pos PositionAccount=new Pos(),Position=new Pos();
object Bars=new object();TimeZoneInfo easternZone=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"),platformZone=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
private bool IsOrderAccount(){return Permission;}private bool HasWorkingOrder(){return false;}
private Intent OwnedOrderIntent(Order o){return o.Owner;}private Intent NewsOrderIntent(Order o){return o.Owner;}
private DateTime EasternNow(){return now;}private DateTime PlatformToEastern(DateTime t){return t;}
private bool MarketTimeAgrees(DateTime a,DateTime b){return b!=default(DateTime)&&(a-b).Duration()<TimeSpan.FromSeconds(5);}
SET_RETURN_OUTCOME private void Print(string s){}private void Queue(Intent i){pending=i;}
public double Balance{get{return modelRealized;}}public bool Latched{get{return modelLossLatched;}}
public string Error{get{return accountReplayFailure;}}public bool Ready{get{return AccountReplayReady();}}
public long Floor{get{return accountReplay.FloorCents;}}
public void Init(Acct a,bool funded){Account=a;FundedPhase=funded;Instrument.MasterInstrument.Name=ROOT_NAME;InitializeAccountReplay();}
public void Entry(string id,double p){var i=new Intent(true,1,"FirstReturn",now,0);if(!ReserveAccountIntent(i,now))throw new Exception("entry reserve");RecordAccountExecution(id,i,p,now);Account.Executions.Add(new Execution{Order=new Order{OrderAction=OrderAction.Buy},Instrument=Instrument,Time=now,ExecutionId=id,Price=p,Quantity=1});positionSide=1;PositionAccount.Quantity=Position.Quantity=1;PositionAccount.MarketPosition=Position.MarketPosition=MarketPosition.Long;}
public void Exit(string id,double p){var i=new Intent(false,1,"Ziel",now,0);if(!ReserveAccountIntent(i,now))throw new Exception("exit reserve");RecordAccountExecution(id,i,p,now);Account.Executions.Add(new Execution{Order=new Order{OrderAction=OrderAction.Sell},Instrument=Instrument,Time=now,ExecutionId=id,Price=p,Quantity=1});positionSide=0;PositionAccount.Quantity=Position.Quantity=0;PositionAccount.MarketPosition=Position.MarketPosition=MarketPosition.Flat;pending=submitted=null;}
public void Eod(){now=sessionEnd;AdvanceAccountReplay(now);}public void Close(){CloseAccountReplay();}
public bool OwnExitAfterFault(){return ReserveAccountIntent(new Intent(false,1,"Stop",now,0),now);}
public Order ReserveForCancel(){var i=new Intent(true,1,"FirstReturn",now,0);if(!ReserveAccountIntent(i,now))throw new Exception("cancel reserve");return new Order{Owner=i};}
public void ConfirmCancelled(Order o){ResolveAccountOrderTerminal(o,1,0,OrderState.Cancelled);}
public bool JournalPending{get{return accountReplay.HasPending;}}
public void SetClock(DateTime t){now=t;sessionOpen=t.Date.AddHours(9.5);sessionEnd=t.Date.AddHours(17);}
public void AdvanceClock(DateTime t){SetClock(t);AdvanceAccountReplay(t);}
public long JournalDay{get{return accountReplay.DayTicks;}}
public int PayoutCount{get{return accountReplay.Snapshot().PayoutCount;}}
public void BreakJournalWrite(){var profile=PROFILE_EXPR;string id=HYAccountReplayV8.Identity(Account.Name,GetType().Name,profile);string file=Path.Combine(NinjaTrader.Core.Globals.UserDataDir,"HY-AccountReplay-v8",HYAccountReplayV8.FileName(id));File.Delete(file);Directory.CreateDirectory(file);}
'''
METHODS=['InitializeAccountReplay','AccountReplayReady','AccountReplayStatus','AdvanceAccountReplay','ReserveAccountIntent',
         'RecordAccountExecution','CloseAccountReplay','CheckModelLoss','CatchUpAccountCalendar','ResolveAccountOrderTerminal',
         'AdvanceAccountReplayCore','RecordAccountExecutionCore','BlockAccountException','ReconcileNativeAccountExecutions','VerifyNativeAccountNegativeProbe']

def main():
    classes=[]
    names=['HY104RapidEvalSim','HY104C2803FundedSim','HY3TradeDayFastPassSim']
    for name in names:
        src=(HERE.parent/'Strategies'/(name+'.cs')).read_text(encoding='utf-8-sig')
        body='\n'.join(member(src,m) for m in METHODS)
        fields='private HYAccountReplayV8 accountReplay;private string accountReplayFailure;private DateTime accountCalendarCheckedDay;private Intent accountReservedIntent;private string accountReservationToken;'
        profile='FundedPhase?HYAccountProfileV8.TradeDayFunded:HYAccountProfileV8.TradeDayEvaluation' if name.startswith('HY3') else 'HYAccountProfileV8.MffEvaluation' if name==names[0] else 'HYAccountProfileV8.MffFunded'
        classes.append('class '+name+'{'+fields+COMMON.replace('ROOT_NAME','"NQ"' if name.startswith('HY3') else '"ES"').replace('PROFILE_EXPR',profile).replace('SET_RETURN_OUTCOME','private void SetReturnOutcome(Intent i,string s){}' if name.startswith('HY3') else '')+body+'}')
    tests='''class BridgeTest{
static int n;static void C(bool b,string s){n++;if(!b)throw new Exception(s);}
static void Main(){string dir=Path.Combine(Path.GetTempPath(),"hy-v8-bridge-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(dir);NinjaTrader.Core.Globals.UserDataDir=dir;
try {TESTS Console.WriteLine("BRIDGE_PASS checks="+n);} finally{Directory.Delete(dir,true);}}
static void Seed(string a,string strategy,HYAccountProfileV8 p){string id=HYAccountReplayV8.Identity(a,strategy,p);HYAccountReplayV8.WriteSeed(Path.Combine(NinjaTrader.Core.Globals.UserDataDir,"HY-AccountReplay-v8","seeds",HYAccountReplayV8.FileName(id)),new HYAccountStateV8{Identity=id,Profile=p.ToString(),Epoch=a,EpochStartTicks=new DateTime(2026,11,19).Ticks,Provenance="bridge fixture"});}}
'''
    cases=[]
    profiles=[('HY104RapidEvalSim','MffEvaluation',False,50,287),('HY104C2803FundedSim','MffFunded',False,50,287),
              ('HY3TradeDayFastPassSim','TradeDayEvaluation',False,20,288),('HY3TradeDayFastPassSim','TradeDayFunded',True,20,288)]
    for i,(name,p,funded,point,fee) in enumerate(profiles):
        cases.append('''{var a=new Acct{Name="SimBridgeINDEX"};Seed(a.Name,"CLASS",HYAccountProfileV8.PROFILE);
var x=new CLASS();x.Init(a,FUNDED);C(x.Ready,"initialized");x.Entry("e",10000);C(Math.Abs(x.Balance+FEE/100.0)<.001,"entry fee");x.Exit("x",10010);double expected=POINT*10-2*FEE/100.0;C(Math.Abs(x.Balance-expected)<.001,"actual bridge fee and pnl");x.Eod();C(x.Floor==(long)Math.Round(expected*100)-200000,"actual bridge EOD trail");x.Close();
x=new CLASS();x.Init(a,FUNDED);C(x.Ready&&Math.Abs(x.Balance-expected)<.001,"flat restart preserves actual ledger");x.Close();
a.Executions.Add(new Execution{Order=new Order{OrderAction=OrderAction.Buy},Instrument=new Inst{MasterInstrument=new Master{Name="ROOT"}},Time=new DateTime(2026,11,19,12,0,0),ExecutionId="foreign",Price=10001,Quantity=1});
x=new CLASS();x.Init(a,FUNDED);C(!x.Ready&&x.Error!=null,"native unmatched execution blocks restart");C(x.OwnExitAfterFault(),"fault never disables an existing owned exit");x.Close();
a.Executions.Clear();x=new CLASS();x.SetClock(new DateTime(2026,11,20,10,0,0));x.Init(a,FUNDED);C(!x.Ready,"reconciliation fault survives next-day empty execution collection");x.Close();}
'''.replace('INDEX',str(i)).replace('CLASS',name).replace('PROFILE',p).replace('FUNDED',str(funded).lower()).replace('FEE',str(fee)).replace('POINT',str(point)).replace('ROOT','NQ' if point==20 else 'ES'))
        cases.append('''{var a=new Acct{Name="SimCancelINDEX"};Seed(a.Name,"CLASS",HYAccountProfileV8.PROFILE);var x=new CLASS();x.Init(a,FUNDED);
var old=x.ReserveForCancel();C(x.JournalPending,"durable cancel intent exists");x.ConfirmCancelled(old);C(!x.JournalPending,"actual terminal callback clears exact book reservation");
var current=x.ReserveForCancel();x.ConfirmCancelled(old);C(x.JournalPending,"old terminal cannot erase newer durable intent");x.ConfirmCancelled(current);C(!x.JournalPending,"new terminal releases its own reservation");
x.AdvanceClock(new DateTime(2026,11,23,10,0,0));C(x.Ready&&x.JournalDay==new DateTime(2026,11,23).Ticks,"actual bridge catches up Friday and weekend before Monday entry");x.Close();}
'''.replace('INDEX',str(i)).replace('CLASS',name).replace('PROFILE',p).replace('FUNDED',str(funded).lower()))
        for fault in ('Mismatch','Invalid'):
            cases.append('''{var a=new Acct{Name="SimCalendarFAULTINDEX"};Seed(a.Name,"CLASS",HYAccountProfileV8.PROFILE);var x=new CLASS();x.Init(a,FUNDED);SessionIterator.FAULT=true;
x.AdvanceClock(new DateTime(2026,11,23,10,0,0));C(!x.Ready&&x.Error!=null,"invalid or unconfirmed calendar blocks before entry");x.Close();SessionIterator.FAULT=false;}
'''.replace('FAULT',fault).replace('INDEX',str(i)).replace('CLASS',name).replace('PROFILE',p).replace('FUNDED',str(funded).lower()))
        cases.append('''{var a=new Acct{Name="SimExitDiskINDEX"};Seed(a.Name,"CLASS",HYAccountProfileV8.PROFILE);var x=new CLASS();x.Init(a,FUNDED);x.Entry("e",10000);x.BreakJournalWrite();x.Exit("x",10001);C(!x.Ready&&x.Error!=null,"owned exit does not touch disk before API; subsequent fill-write failure blocks entries");x.Close();}
'''.replace('INDEX',str(i)).replace('CLASS',name).replace('PROFILE',p).replace('FUNDED',str(funded).lower()))
        cases.append('''{var x=new CLASS();x.Permission=false;x.Init(new Acct{Name="SignalWithoutSeed"},FUNDED);C(x.Ready,"non-order mode keeps raw signal eligibility and never opens a journal");x.Close();}
'''.replace('CLASS',name).replace('FUNDED',str(funded).lower()))
    cases.append('''C(SessionIterator.FalseGaps>=4&&SessionIterator.Confirmations>=4,"weekend false-return cases truly exercised");
{var c=new SessionIterator(null);C(!c.GetNextSession(new DateTime(2026,12,25,9,30,0),true),"full holiday returns false with populated next bounds");var b=c.ActualSessionBegin;var e=c.ActualSessionEnd;C(c.GetNextSession(b.AddSeconds(1),false)&&c.ActualSessionBegin==b&&c.ActualSessionEnd==e,"holiday candidate confirmed from its interior");}
''')
    code=PREFIX+'\n'.join(classes)+tests.replace('TESTS',''.join(cases))+'}\n'
    (HERE/'BridgeHarness.cs').write_text(code)
    target=HERE/'BridgeHarness.dll'
    cmd=[str(SDK/'dotnet'),str(SDK/'sdk/8.0.428/Roslyn/bincore/csc.dll'),'/nologo','/warn:0','/langversion:7.3','/target:exe','/out:'+str(target)]
    cmd+=['/r:'+str(p) for p in (SDK/'packs/Microsoft.NETCore.App.Ref/8.0.34/ref/net8.0').glob('*.dll')]
    cmd+=[str(HERE/'BridgeHarness.cs'),str(HERE.parent/'Strategies/HYAccountReplayV8.cs')]
    r=subprocess.run(cmd,capture_output=True,text=True);(HERE/'bridge-compile.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
    target.with_suffix('.runtimeconfig.json').write_text(json.dumps({'runtimeOptions':{'tfm':'net8.0','framework':{'name':'Microsoft.NETCore.App','version':'8.0.34'}}}))
    r=subprocess.run([str(SDK/'dotnet'),str(target)],capture_output=True,text=True);(HERE/'bridge-run.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
    result={'status':r.stdout.strip(),'actual_candidate_methods':METHODS,'scope':'Actual C# integration methods and account book/store. Explicit vendor/account/intent stubs; no orders and no native NinjaTrader acceptance.',
            'harness_sha256':hashlib.sha256(code.encode()).hexdigest()}
    (HERE.parent/'evidence/bridge-tests.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
