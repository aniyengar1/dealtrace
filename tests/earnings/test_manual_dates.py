from datetime import datetime,timezone
import pytest
from earnings.manual_dates import confirmation

BASE={'company':'PD','supplied_by':'project owner','source_url':'https://investor.pagerduty.com/news/default.aspx',
      'release_date':'2026-11-24','timezone':None,'time_precision':'date','release_time':None}


def test_manual_observation_records_real_entry_time_and_preserves_precision():
    before=datetime.now(timezone.utc);r=confirmation(BASE);after=datetime.now(timezone.utc)
    assert before<=datetime.fromisoformat(r['entered_at'])<=after
    assert r['verification_status']=='user_verified' and r['independently_checked'] is False
    assert r['announcement_issued_at'] is None and r['timezone'] is None and r['release_time'] is None
    assert r['supplied_by']=='project owner' and r['event_kind']=='results_release'


@pytest.mark.parametrize('updates',[{'entered_at':'2020-01-01T00:00:00Z'},{'independently_checked':True},
    {'source_url':'https://example.com/'},{'release_time':'16:00'},
    {'time_precision':'minute','release_time':'16:00','timezone':None},
    {'time_precision':'hour','release_time':'16:30','timezone':'America/New_York'}])
def test_no_backdating_implied_times_or_false_verification(updates):
    with pytest.raises(ValueError):confirmation({**BASE,**updates})


def test_market_session_is_not_fabricated_into_an_exact_clock_time():
    r=confirmation({**BASE,'timezone':'America/New_York','time_precision':'market_session','release_time':'after_market_close'})
    assert r['release_time']=='after_market_close' and r['time_precision']=='market_session'
