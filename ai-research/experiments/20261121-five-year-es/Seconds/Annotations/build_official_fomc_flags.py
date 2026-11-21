"""Descriptive official Fed date annotations; no strategy/labels/models/filter."""
from pathlib import Path
from datetime import date
import hashlib,json

TASK=Path(__file__).resolve().parents[1]
URL='https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'
# Exact decision date and stated minutes RELEASE date, transcribed from the
# official calendar retrieved 2026-11-21. Press Conference links are present
# for each of these completed regularly scheduled meetings. Do not infer a
# minutes release by mechanically adding 21 days (holidays can change it).
PAIRS='''2021-01-27 2021-02-17
2021-03-17 2021-04-07
2021-04-28 2021-05-19
2021-06-16 2021-07-07
2021-07-28 2021-08-18
2021-09-22 2021-10-13
2021-11-03 2021-11-24
2021-12-15 2022-01-05
2022-01-26 2022-02-16
2022-03-16 2022-04-06
2022-05-04 2022-05-25
2022-06-15 2022-07-06
2022-07-27 2022-08-17
2022-09-21 2022-10-12
2022-11-02 2022-11-23
2022-12-14 2023-01-04
2023-02-01 2023-02-22
2023-03-22 2023-04-12
2023-05-03 2023-05-24
2023-06-14 2023-07-05
2023-07-26 2023-08-16
2023-09-20 2023-10-11
2023-11-01 2023-11-21
2023-12-13 2024-01-03
2024-01-31 2024-02-21
2024-03-20 2024-04-10
2024-05-01 2024-05-22
2024-06-12 2024-07-03
2024-07-31 2024-08-21
2024-09-18 2024-10-09
2024-11-07 2024-11-26
2024-12-18 2025-01-08
2025-01-29 2025-02-19
2025-03-19 2025-04-09
2025-05-07 2025-05-28
2025-06-18 2025-07-09
2025-07-30 2025-08-20
2025-09-17 2025-10-08
2025-10-29 2025-11-19
2025-12-10 2025-12-30
2026-01-28 2026-02-18
2026-03-18 2026-04-08
2026-04-29 2026-05-20
2026-06-17 2026-07-08
2026-07-29 2026-08-19
2026-09-16 2026-10-07
2026-10-28 2026-11-18'''


def main():
    pairs=[line.split() for line in PAIRS.splitlines()]
    assert len(pairs)==47 and len({p[0] for p in pairs})==47
    assert all(date.fromisoformat(a)<date.fromisoformat(b) for a,b in pairs)
    counts={year:sum(a.startswith(str(year)) for a,b in pairs) for year in range(2021,2027)}
    assert counts=={2021:8,2022:8,2023:8,2024:8,2025:8,2026:7}
    assert dict(pairs)['2024-11-07']=='2024-11-26'
    assert dict(pairs)['2025-12-10']=='2025-12-30'
    lo='2021-11-01';hi='2026-10-31';events={}
    def add(day,kind,meeting):
        if lo<=day<hi:events.setdefault(day,[]).append(dict(event_type=kind,associated_decision_date=meeting,evidence_url=URL))
    for decision,minutes in pairs:
        add(decision,'scheduled_FOMC_policy_decision',decision)
        add(decision,'FOMC_press_conference_linked_on_official_calendar',decision)
        add(minutes,'FOMC_minutes_actual_release_date_listed',decision)
    add('2025-08-22','FOMC_long_run_strategy_notation_vote_no_regular_policy_meeting','2025-08-22')
    rows=[]
    for day,listed in sorted(events.items()):
        types={e['event_type'] for e in listed}
        rows.append(dict(day=day,scheduled_FOMC_decision_day='scheduled_FOMC_policy_decision' in types,FOMC_press_conference_day='FOMC_press_conference_linked_on_official_calendar' in types,FOMC_minutes_release_day='FOMC_minutes_actual_release_date_listed' in types,other_FOMC_notation_vote_day='FOMC_long_run_strategy_notation_vote_no_regular_policy_meeting' in types,events=listed))
    report=dict(schema='official-fed-descriptive-day-flags-v1',status='OFFICIAL_CALENDAR_DESCRIPTIVE_ONLY_NO_FILTER_CHANGE',retrieved_UTC_date='2026-11-21',official_page_last_update='2026-11-18',source_url=URL,scope_start_inclusive=lo,scope_end_exclusive=hi,timezone_scope='UScivilmeeting/releasedates;day-onlyannotation;nointradaywindowsreconstructed',full_source_meeting_counts=counts,meetings_in_scope=sum(lo<=a<hi for a,b in pairs),minutes_releases_in_scope=sum(lo<=b<hi for a,b in pairs),event_days=len(rows),days=rows,source_pairs_all47=[dict(decision_day=a,minutes_release_day=b,press_conference_link_present=True) for a,b in pairs],limitations=['Officialcurrenthistoricalcalendar,notarchivedpoint-in-timeadvanceannouncementproof','NoNFP/CPI/PPI/PCE/GDP/speeches/unschedulednewsinventory;othernewscoverageUNKNOWN','Noexactintradaynewswindowororiginalhistoricalnewsfilterreconstruction','AbsenceoflistedFOMCeventdoesNOTproveanews-freeday','Annotationsarenotmodelinputsanddonotexcludeorchangeanycandidate','2025-08-22isnotationvotestrategystatement,notregularpolicymeeting'],research_policy='PrimarynoNewsconsistentlyacrossyears;descriptiveflagsONLY',frozen_strategy_source_unchanged=True,no_price_or_label_or_model_inputs_read=True,annotation_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    path=TASK/'Public/fomc-descriptive-day-flags.json'
    assert not path.exists(),'Retain prior annotation rather than overwrite'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),event_days=len(rows),meetings_in_scope=report['meetings_in_scope'],minutes_releases_in_scope=report['minutes_releases_in_scope'])))


if __name__=='__main__':main()
