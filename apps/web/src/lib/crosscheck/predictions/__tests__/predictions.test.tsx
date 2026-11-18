import React from 'react';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {renderToStaticMarkup} from 'react-dom/server';
import {describe,it,expect,vi} from 'vitest';
import {percent,usd,validProbabilities,compactUsd,periodLabel,leadDays,highestDisplayedBuckets} from '../format';
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
 it('formats compact money, calendar dates and release-zone lead times',()=>{
  expect(compactUsd('813000000')).toBe('$813M');expect(compactUsd('817000000')).toBe('$817M');
  expect(compactUsd('11420000000')).toBe('$11.42B');expect(compactUsd('11500000000')).toBe('$11.50B');
  expect(compactUsd('309500000')).toBe('$309.5M');
  expect(periodLabel('2026-08-01','2026-10-31')).toBe('Aug 1 – Oct 31, 2026');
  expect(periodLabel('2025-11-01','2026-01-31')).toBe('Nov 1, 2025 – Jan 31, 2026');
  expect(leadDays('2026-11-17T10:56:43.445442Z','2026-12-01','America/New_York')).toBe(14);
  expect(leadDays('2026-11-17T01:00:00Z','2026-12-01','America/New_York')).toBe(15);
 });
 it('emphasizes displayed leaders and all displayed ties without changing rates',()=>{
  const p={below:'0.090909090909090909090909',within:'0.454545454545454545454545',above:'0.454545454545454545454546'};
  const original=JSON.stringify(p);expect(highestDisplayedBuckets(p)).toEqual(['within','above']);expect(JSON.stringify(p)).toBe(original);
  expect(highestDisplayedBuckets({below:'0',within:'0',above:'1'})).toEqual(['above']);
 });
 it('renders the requested question, compact ranges, lead times and two-sentence footer',()=>{
  const snapshot=validateSnapshot(source());const before=JSON.stringify(snapshot);
  const html=renderToStaticMarkup(<Predictions state={{kind:'ready',snapshot}}/>);
  expect(html).toContain('$813M');expect(html).toContain('$817M');expect(html).toContain('$11.42B');expect(html).toContain('$11.50B');
  expect(html).toContain('Aug 1 – Oct 31, 2026');expect(html).toContain('days before results');
  expect(html).toContain('Will each company');expect(html).toContain('management');expect(html).toContain('own guidance range?');
  expect(html).toContain('not calibrated forecasts. Scored with Brier score (0 best, 2 worst) after results are published.');
  expect(html).toContain('/crosscheck/predictions/methodology');expect(html.match(/data-leading-probability="true"/g)).toHaveLength(10);
  expect(html).not.toContain('`');expect(JSON.stringify(snapshot)).toBe(before);
 });

 it('keeps scoped classes and explicit separators in server-rendered content',()=>{
  const html=renderToStaticMarkup(<Predictions state={{kind:'ready',snapshot:validateSnapshot(source())}}/>);
  expect(html).toMatch(/class="[^"]+"[^>]*data-crosscheck-predictions="true"/);
  expect(html).toMatch(/<section class="[^"]+"[^>]*data-prediction-id=/);
  expect(html).toContain(' · </span>');expect(html).toContain('Locked management range:</span> <strong>');
 });

});
