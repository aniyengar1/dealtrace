import {describe,it,expect,vi,beforeEach} from 'vitest';
import {readFileSync} from 'node:fs';
import path from 'node:path';
const fixture=(name:string)=>JSON.parse(readFileSync(path.resolve(process.cwd(),`../../earnings/publication/${name}.json`),'utf8'));
const mock=vi.hoisted(()=>({query:vi.fn(),end:vi.fn(),release:vi.fn(),constructor:vi.fn()}));
vi.mock('server-only',()=>({}));
vi.mock('pg',()=>({Pool:class{constructor(config:unknown){mock.constructor(config)}connect(){return Promise.resolve({query:mock.query,release:mock.release})}end(){mock.end();return Promise.resolve()}}}));
import {readPublishedPredictions,readPublishedBacktest} from '../read';
beforeEach(()=>{vi.clearAllMocks();vi.stubEnv('CROSSCHECK_PUBLISHED_DATABASE_URL','postgresql://publication-only');mock.query.mockImplementation(async(sql:string)=>({rows:sql.includes('current_user')?[{role:'dealtrace_web'}]:sql.includes('prediction_snapshots')?[{payload:fixture('predictions')}]:sql.includes('backtest_snapshots')?[{payload:fixture('backtest')}]:[]}))});
describe('snapshot-only SQL reader',()=>{
 it('queries only publication tables inside READ ONLY and ignores the live URL',async()=>{
  vi.stubEnv('DATABASE_URL','DO_NOT_USE');expect((await readPublishedPredictions()).kind).toBe('ready');expect((await readPublishedBacktest())?.summary.n).toBe(532);
  expect(mock.constructor).toHaveBeenCalledWith(expect.objectContaining({connectionString:'postgresql://publication-only'}));
  const sql=mock.query.mock.calls.map(x=>x[0]).join('\n');expect(sql).toContain('BEGIN READ ONLY');expect(sql).toContain('ROLLBACK');expect(sql).not.toContain('earnings_live');expect(sql).not.toContain('guidance_versions');
 });
 it('rejects an administrative role rather than silently using it',async()=>{
  mock.query.mockImplementation(async(sql:string)=>({rows:sql.includes('current_user')?[{role:'postgres'}]:[]}));expect((await readPublishedPredictions()).kind).toBe('invalid');expect(mock.query.mock.calls.some(x=>x[0].includes('prediction_snapshots'))).toBe(false);
 });
 it('fails closed for malformed publication and missing configuration',async()=>{
  mock.query.mockImplementation(async(sql:string)=>({rows:sql.includes('current_user')?[{role:'dealtrace_web'}]:sql.includes('SELECT payload')?[{payload:{}}]:[]}));expect((await readPublishedPredictions()).kind).toBe('invalid');expect(await readPublishedBacktest()).toBeNull();
  vi.stubEnv('CROSSCHECK_PUBLISHED_DATABASE_URL','');mock.constructor.mockClear();expect((await readPublishedPredictions()).kind).toBe('missing');expect(mock.constructor).not.toHaveBeenCalled();
 });
 it('does not publish an old or incomplete backtest without the pooled comparator and subgroup counts',async()=>{
  for(const alter of [(r:ReturnType<typeof fixture>)=>delete r.summary.mean_brier['walk-forward-pooled-base-rate'],(r:ReturnType<typeof fixture>)=>{r.by_history_mode.company.n++},(r:ReturnType<typeof fixture>)=>{r.summary.below_guidance.interval.high='1.1'},(r:ReturnType<typeof fixture>)=>{r.below_company_counts.LULU.below=8}]){
   const payload=fixture('backtest');alter(payload);
   mock.query.mockImplementation(async(sql:string)=>({rows:sql.includes('current_user')?[{role:'dealtrace_web'}]:sql.includes('SELECT payload')?[{payload}]:[]}));
   expect(await readPublishedBacktest()).toBeNull();
  }
 });
});
