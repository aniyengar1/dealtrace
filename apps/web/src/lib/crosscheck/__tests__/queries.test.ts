import {beforeEach,describe,it,expect,vi} from 'vitest';
vi.mock('server-only',()=>({}));
vi.mock('@/lib/db',()=>({query:vi.fn(),queryOne:vi.fn()}));
import {query,queryOne} from '@/lib/db';
import {companyData,listCompanies} from '../queries';
import {GET} from '@/app/api/crosscheck/[ticker]/route';
const one=vi.mocked(queryOne),many=vi.mocked(query);
beforeEach(()=>{vi.resetAllMocks();vi.unstubAllEnvs();});
describe('Crosscheck read path',()=>{
 it('never substitutes a different historical cutoff',async()=>{
  one.mockResolvedValueOnce({ticker:'PD',name:'PagerDuty',cik:'0001568100'}).mockResolvedValueOnce(null);
  many.mockResolvedValue([{as_of:'2026-11-11'}]);
  const result=await companyData('pd','2026-11-12');
  expect(result?.report).toBeNull();expect(result?.dates).toEqual(['2026-11-11']);
  expect(one.mock.calls[1][0]).toContain('r.as_of=$2::date');expect(one.mock.calls[1][1]).toEqual(['PD','2026-11-12']);
 });
 it('does not fabricate unsupported company data',async()=>{
  one.mockResolvedValueOnce(null);
  expect(await companyData('MSFT')).toBeNull();expect(one).toHaveBeenCalledTimes(1);
 });
 it('returns exact Decimal strings in opt-in JSON reports',async()=>{
  vi.stubEnv('CROSSCHECK_EXPERIMENTAL_ANNUAL_FORECAST','true');
  one.mockResolvedValueOnce({ticker:'PD'}).mockResolvedValueOnce({payload:{forecast:{estimate:'496974919.123456789123456789'},as_of:'2026-11-11',company:{period_start:'2026-02-01',period_end:'2027-01-31'}}});
  many.mockResolvedValue([]);
  const res=await GET(new Request('http://localhost/api/crosscheck/PD?asOf=2026-11-11'),{params:Promise.resolve({ticker:'PD'})});
  expect(res.status).toBe(200);expect((await res.json()).forecast.estimate).toBe('496974919.123456789123456789');
 });
 it('has honest unsupported, invalid-date, and sanitized error responses',async()=>{
  one.mockResolvedValueOnce(null);
  expect((await GET(new Request('http://localhost/api/crosscheck/MSFT'),{params:Promise.resolve({ticker:'MSFT'})})).status).toBe(404);
  expect((await GET(new Request('http://localhost/api/crosscheck/PD?asOf=tomorrow'),{params:Promise.resolve({ticker:'PD'})})).status).toBe(400);
  one.mockRejectedValueOnce(new Error('private driver details'));
  const response=await GET(new Request('http://localhost/api/crosscheck/PD'),{params:Promise.resolve({ticker:'PD'})});
  expect(response.status).toBe(503);expect(JSON.stringify(await response.json())).not.toContain('private');
 });
});

it('does not expose forecast or evaluation in downloads by default',async()=>{
 const payload={as_of:'2026-11-11',company:{period_start:'2026-02-01',period_end:'2027-01-31'},
  forecast:{estimate:'496974919.12345'},forecast_display:{estimate:'496.975'},evaluation:{sample_size:1},evaluation_display:{mape:'1.65%'},
  hurdle:{state:'ok',growth_low:'0.5'},selected_inputs:{ytd:{value:'700000000'}},
  changes:{causes:['forecast_estimate_changed','historical_evaluation_changed','guidance_changed'],input_versions:{}},coverage_notes:['Experimental forecast','SEC financial sources']};
 one.mockResolvedValueOnce({ticker:'PD'}).mockResolvedValueOnce({payload}).mockResolvedValueOnce(null);many.mockResolvedValue([]);
 const response=await GET(new Request('http://localhost/api/crosscheck/PD'),{params:Promise.resolve({ticker:'PD'})});
 const data=await response.json();expect(data.forecast).toBeUndefined();expect(data.forecast_display).toBeUndefined();
 expect(data.evaluation).toBeUndefined();expect(data.evaluation_display).toBeUndefined();
 expect(data.hurdle.growth_low).toBe('0.5');expect(data.selected_inputs.ytd.value).toBe('700000000');
 expect(data.changes.causes).toEqual(['guidance_changed']);expect(payload.forecast.estimate).toBe('496974919.12345');
});
it('strips forecast summaries before search results reach the client',async()=>{
 many.mockResolvedValue([{ticker:'PD',name:'PagerDuty',as_of:'2026-11-11',hurdle_state:'ok',forecast_status:'experimental',verdict:'beat'}]);
 const rows=await listCompanies();expect(rows[0].forecast_status).toBeUndefined();expect(rows[0].verdict).toBeUndefined();expect(rows[0].hurdle_state).toBe('ok');
});
