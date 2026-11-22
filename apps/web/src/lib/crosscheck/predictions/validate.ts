import type {PublishedSnapshot} from './types';
import {validProbabilities,usd} from './format';
export function validateSnapshot(raw:unknown):PublishedSnapshot{
 const s=raw as PublishedSnapshot;
 if(!s||s.schema_version!=='crosscheck-public-predictions-v1'||!Array.isArray(s.predictions)||s.prediction_count!==s.predictions.length||!Number.isFinite(Date.parse(s.copied_at))||!/^[a-f0-9]{64}$/.test(s.ledger_sha256))throw new Error('Invalid snapshot');
 const ids=new Set<string>();
 for(const p of s.predictions){
  if(ids.has(p.id)||!p.id||!p.company||!p.name||!p.quarter||!['quarter-frequency-v1','quarter-frequency-laplace-v1'].includes(p.method)||!validProbabilities(p.probabilities)||!/^\d{4}-\d{2}-\d{2}$/.test(p.period_start)||p.period_start>p.period_end||!Number.isFinite(Date.parse(p.locked_at))||!/^\d{4}-\d{2}-\d{2}$/.test(p.announcement.release_date)||! /^[a-f0-9]{64}$/.test(p.evidence_sha256))throw new Error('Invalid prediction');
  if(p.guidance.unit!=='USD')throw new Error('Unsupported currency');
  usd(p.guidance.low);usd(p.guidance.high);
  for(const value of [p.guidance.source_url,p.announcement.source_url,...(p.result?.actual?[p.result.actual.source_url]:[])]){
   const url=new URL(value);if(url.protocol!=='https:'||url.username||url.password)throw new Error('Invalid evidence URL');
  }
  if(p.result?.status==='scored'){
   if(!p.result.actual||!p.result.outcome||!['below','within','above'].includes(p.result.outcome)||p.result.actual.unit!==p.guidance.unit||p.result.brier===null||p.result.actual.period_start!==p.period_start||p.result.actual.period_end!==p.period_end)throw new Error('Incomplete score');
   usd(p.result.actual.value);usd(p.result.brier);
  }
  ids.add(p.id);
 }
 return s;
}
