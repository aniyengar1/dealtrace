import React from 'react';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {renderToStaticMarkup} from 'react-dom/server';
import {describe,it,expect,vi} from 'vitest';
import {percent,usd,validProbabilities} from '../format';
import {validateSnapshot} from '../validate';
import Predictions from '@/app/crosscheck/predictions/Predictions';
vi.mock('server-only',()=>({}));
import {readPublishedPredictions} from '../read';
const source=()=>JSON.parse(readFileSync(path.resolve(process.cwd(),'../../earnings/publication/predictions.json'),'utf8'));
describe('publication copy',()=>{
 it('renders exactly eight real locks and four company groups',()=>{
  const snapshot=validateSnapshot(source());const html=renderToStaticMarkup(<Predictions state={{kind:'ready',snapshot}}/>);
  expect(html.match(/data-prediction-id=/g)).toHaveLength(8);expect(html).toContain('8 locked predictions');expect(html).toContain('4 companies');expect(html).toContain('Pending · results Dec 1, 2026');expect(html).toContain('Pending · results Dec 3, 2026');expect(html).toContain('never the live ledger');
  for(const r of snapshot.predictions){expect(html).toContain(r.evidence_sha256);expect(html).toContain(r.id);}
 });
 it('shows copied actuals and Brier after scoring without changing predictions',()=>{
  const raw=source();const p=raw.predictions[0];p.result={id:'score',status:'scored',outcome:'within',brier:'0.5',scored_at:'2026-12-04T00:00:00Z',supersedes_id:null,evidence_hash:'a'.repeat(64),actual:{value:p.guidance.low,unit:'USD',period_start:p.period_start,period_end:p.period_end,accession:'actual-acc',filed:'2026-12-03',source_url:'https://www.sec.gov/Archives/test-result'}};p.score_versions=1;
  const html=renderToStaticMarkup(<Predictions state={{kind:'ready',snapshot:validateSnapshot(raw)}}/>);
  expect(html).toContain('Reported revenue');expect(html).toContain('within the locked range');expect(html).toContain('Unscaled Brier');expect(html).toContain('0.5');expect(html).toContain('1 reviewed scores');
 });
 it('fails closed for invalid probabilities, duplicate ids and incomplete scores',()=>{
  let r=source();r.predictions[0].probabilities.above='0.4';expect(()=>validateSnapshot(r)).toThrow();
  r=source();r.predictions[1].id=r.predictions[0].id;expect(()=>validateSnapshot(r)).toThrow();
  r=source();r.predictions[0].result={status:'scored',outcome:'above',brier:null,actual:null};expect(()=>validateSnapshot(r)).toThrow();
 });
 it('renders missing and invalid copies without database fallback',()=>{
  for(const kind of ['missing','invalid'] as const){const html=renderToStaticMarkup(<Predictions state={{kind}}/>);expect(html).toContain('No live database fallback');expect(html).not.toContain('data-prediction-id');}
 });
 it('keeps financial arithmetic exact beyond JavaScript safe integers',()=>{
  expect(usd('9007199254740993123.000')).toBe('$9,007,199,254,740,993,123');expect(percent('0.454545454545454545454546')).toBe('45.45%');expect(percent('0.00005')).toBe('0.00%');expect(percent('0.00015')).toBe('0.02%');expect(validProbabilities({below:'0.1',within:'0.1',above:'0.8'})).toBe(true);
 });
 it('reads the file copy even when DATABASE_URL is unusable',async()=>{
  vi.stubEnv('DATABASE_URL','not-a-database');const r=await readPublishedPredictions();expect(r.kind).toBe('ready');vi.unstubAllEnvs();
 });
});
