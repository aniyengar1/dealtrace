export type PublishedPrediction={
 id:string;company:string;name:string;quarter:string;period_start:string;period_end:string;method:string;locked_at:string;sample_size:number;evidence_sha256:string;evidence_hash_version:string;score_versions:number;
 probabilities:Record<'below'|'within'|'above',string>;
 guidance:{id:string;low:string;high:string;unit:string;basis:string;source_url:string;accession:string;filed:string;quote:string};
 announcement:{source_url:string;source_sha256:string;release_date:string;timezone:string;verification_status:string};
 result:null|{id:string;status:'scored'|'blocked';outcome:'below'|'within'|'above'|null;brier:string|null;scored_at:string;supersedes_id:string|null;evidence_hash:string;actual:null|{value:string;unit:string;period_start:string;period_end:string;accession:string;filed:string;source_url:string}};
};
export type PublishedSnapshot={schema_version:'crosscheck-public-predictions-v1';copied_at:string;prediction_count:number;ledger_sha256:string;predictions:PublishedPrediction[]};
export type SnapshotState={kind:'ready';snapshot:PublishedSnapshot}|{kind:'missing'|'invalid'};
