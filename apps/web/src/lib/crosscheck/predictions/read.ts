import 'server-only';
import {Pool} from 'pg';
import {validBrier} from './format';
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
  for(const id of ['quarter-frequency-v1','quarter-frequency-laplace-v1','uniform','always-above'])if(!validBrier(raw.summary.mean_brier[id]))throw new Error('Invalid Brier');
  return raw;
 }catch{return null;}
}
