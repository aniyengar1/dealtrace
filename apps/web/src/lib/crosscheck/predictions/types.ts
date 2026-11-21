export type PublishedPrediction={
 id:string;company:string;name:string;quarter:string;period_start:string;period_end:string;method:string;locked_at:string;sample_size:number;evidence_sha256:string;evidence_hash_version:string;score_versions:number;
 probabilities:Record<'below'|'within'|'above',string>;
 guidance:{id:string;low:string;high:string;unit:string;basis:string;source_url:string;accession:string;filed:string;quote:string};
 announcement:{source_url:string;source_sha256:string;release_date:string;timezone:string;verification_status:string};
 result:null|{id:string;status:'scored'|'blocked';outcome:'below'|'within'|'above'|null;brier:string|null;scored_at:string;supersedes_id:string|null;evidence_hash:string;actual:null|{value:string;unit:string;period_start:string;period_end:string;accession:string;filed:string;source_url:string}};
};
export type PublishedSnapshot={schema_version:'crosscheck-public-predictions-v1';copied_at:string;prediction_count:number;ledger_sha256:string;predictions:PublishedPrediction[]};
export type SnapshotState={kind:'ready';snapshot:PublishedSnapshot}|{kind:'missing'|'invalid'};
export type BacktestSummary={kind:'BACKTEST_PUBLIC_DATE_RECONSTRUCTION_NOT_LIVE';executed_at:string;company_count:number;source_matched_targets:number;summary:{n:number;mean_brier:Record<string,string>;outcomes:Record<string,number>;outcome_shares:Record<string,string>;own_history_predictions:number;pooled_predictions:number;below_guidance:BelowGuidance};by_history_mode:Record<'company'|'pooled',HistoryModeStats>;below_by_sector:Record<string,BelowGuidance & {companies:string[]}>;below_company_counts:Record<string,{n:number;below:number}>;company_cluster_bootstrap:CompanyBootstrap;company_cluster_bootstrap_sentence:string};
export type BelowGuidance={n:number;below:number;rate:string;interval:{low:string;high:string;method:string}};
export type HistoryModeStats={n:number;mean_brier:Record<string,string>};
export type CompanyBootstrap={kind:string;n_predictions:number;n_companies:number;resamples:number;seed:number;mean_difference:string;interval:{low:string;high:string};excludes_zero:boolean};
