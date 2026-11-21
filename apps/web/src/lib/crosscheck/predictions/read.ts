import 'server-only';
import {Pool} from 'pg';
import {validBrier,validRate} from './format';
import {validateSnapshot} from './validate';
import type {SnapshotState,BacktestSummary} from './types';

// Dedicated publication connection only: NEVER fall back to DATABASE_URL or the
// shared deals/research pool. Fixed table allowlist; no live-ledger SQL or views.
const tables={predictions:'public.crosscheck_prediction_snapshots',backtest:'public.crosscheck_backtest_snapshots'} as const;
async function readSnapshot(kind:keyof typeof tables):Promise<unknown|null>{
 const url=process.env.CROSSCHECK_PUBLISHED_DATABASE_URL;
 if(!url)return null;
 const pool=new Pool({connectionString:url,max:1,connectionTimeoutMillis:4000});
 try{
  const conn=await pool.connect();
  try{
   await conn.query('BEGIN READ ONLY');
   await conn.query("SET LOCAL statement_timeout='5s'");
   const role=await conn.query<{role:string}>('SELECT current_user AS role');
   if(role.rows[0]?.role!=='dealtrace_web')throw new Error('Publication reader must use dealtrace_web');
   const result=await conn.query<{payload:unknown}>(`SELECT payload FROM ${tables[kind]} WHERE snapshot_id=$1`,['current']);
   return result.rows[0]?.payload??null;
  }finally{try{await conn.query('ROLLBACK');}finally{conn.release();}}
 }finally{await pool.end();}
}
export async function readPublishedPredictions():Promise<SnapshotState>{
 try{const raw=await readSnapshot('predictions');return raw?{kind:'ready',snapshot:validateSnapshot(raw)}:{kind:'missing'};}
 catch{return {kind:'invalid'};}
}
export async function readPublishedBacktest():Promise<BacktestSummary|null>{
 try{
  const raw=await readSnapshot('backtest') as BacktestSummary|null;
  if(!raw)return null;
  if(raw.kind!=='BACKTEST_PUBLIC_DATE_RECONSTRUCTION_NOT_LIVE'||!Number.isInteger(raw.summary?.n)||raw.summary.n<=0||!Number.isInteger(raw.company_count))throw new Error('Invalid backtest');
  const methods=['quarter-frequency-v1','quarter-frequency-laplace-v1','walk-forward-pooled-base-rate','uniform','always-above'];
  const count=(n:number)=>Number.isInteger(n)&&n>=0;
  for(const s of [raw.summary,raw.by_history_mode.company,raw.by_history_mode.pooled]){
   if(!count(s.n))throw new Error('Invalid count');
   for(const id of methods)if(!validBrier(s.mean_brier[id]))throw new Error('Invalid Brier');
  }
  if(raw.by_history_mode.company.n!==raw.summary.own_history_predictions||raw.by_history_mode.pooled.n!==raw.summary.pooled_predictions||raw.by_history_mode.company.n+raw.by_history_mode.pooled.n!==raw.summary.n)throw new Error('Invalid subgroup counts');
  for(const s of [raw.summary.below_guidance,...Object.values(raw.below_by_sector)])if(!count(s.n)||!count(s.below)||s.below>s.n||!validRate(s.rate)||!validRate(s.interval.low)||!validRate(s.interval.high))throw new Error('Invalid below statistics');
  if(raw.summary.below_guidance.n!==raw.summary.n||raw.summary.below_guidance.below!==raw.summary.outcomes.below)throw new Error('Invalid below count');
  const sectors=Object.values(raw.below_by_sector),companies=Object.values(raw.below_company_counts);
  if(companies.length!==raw.company_count||companies.some(c=>!count(c.n)||!count(c.below)||c.below>c.n)||sectors.reduce((n,s)=>n+s.n,0)!==raw.summary.n||companies.reduce((n,s)=>n+s.n,0)!==raw.summary.n||sectors.reduce((n,s)=>n+s.below,0)!==raw.summary.outcomes.below||companies.reduce((n,s)=>n+s.below,0)!==raw.summary.outcomes.below)throw new Error('Invalid descriptive groups');
  return raw;
 }catch{return null;}
}
