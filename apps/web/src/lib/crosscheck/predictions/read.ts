import 'server-only';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {validateSnapshot} from './validate';
import type {SnapshotState} from './types';
// Deliberately no pg, DATABASE_URL, or live research-query dependency.
export async function readPublishedPredictions():Promise<SnapshotState>{
 const location=process.env.CROSSCHECK_PUBLISHED_SNAPSHOT??path.resolve(process.cwd(),'../../earnings/publication/predictions.json');
 try{return {kind:'ready',snapshot:validateSnapshot(JSON.parse(await readFile(location,'utf8')))}}
 catch(error){return {kind:(error as NodeJS.ErrnoException).code==='ENOENT'?'missing':'invalid'};}
}
