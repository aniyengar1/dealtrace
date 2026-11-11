import {beforeEach,describe,it,expect,vi} from 'vitest';
vi.mock('server-only',()=>({}));
vi.mock('@/lib/db',()=>({query:vi.fn(),queryOne:vi.fn()}));
import {query,queryOne} from '@/lib/db';
import {companyData} from '../queries';
import {GET} from '@/app/api/crosscheck/[ticker]/route';
const one=vi.mocked(queryOne),many=vi.mocked(query);
beforeEach(()=>vi.resetAllMocks());
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
 it('returns exact Decimal strings in JSON reports',async()=>{
  one.mockResolvedValueOnce({ticker:'PD'}).mockResolvedValueOnce({payload:{forecast:{estimate:'496974919.123456789123456789'},as_of:'2026-11-11'}});
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
