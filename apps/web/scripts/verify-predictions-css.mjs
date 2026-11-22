/** Real HTTP regression check: CSS module mocks cannot catch loader export loss.
 * node apps/web/scripts/verify-predictions-css.mjs http://127.0.0.1:3108 [report.json]
 * No browser automation, database imports, or writes beyond the optional report.
 */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {writeFile,mkdir} from 'node:fs/promises';
import {dirname} from 'node:path';
const base=new URL(process.argv[2]??'http://127.0.0.1:3108');
assert(['127.0.0.1','localhost','[::1]'].includes(base.hostname),'Local review server required');
const url=new URL('/crosscheck/predictions',base);
const response=await fetch(url);assert.equal(response.status,200);
const html=await response.text();
const attribute=(tag,name)=>new RegExp(`\\b${name}="([^"]*)"`).exec(tag)?.[1];
const tags=pattern=>[...html.matchAll(pattern)].map(match=>match[0]);
const links=tags(/<link\b[^>]*>/g).filter(tag=>attribute(tag,'rel')==='stylesheet');
assert(links.length>0,'No stylesheet links');
const assets=[];
for(const link of links){
 const href=attribute(link,'href');const assetUrl=new URL(href,base);
 assert.equal(assetUrl.origin,base.origin,'Unexpected stylesheet origin');
 const result=await fetch(assetUrl);assert.equal(result.status,200,`Stylesheet failed: ${href}`);
 assert.match(result.headers.get('content-type')??'',/^text\/css/);
 const css=await result.text();assets.push({url:assetUrl.href,status:result.status,bytes:Buffer.byteLength(css),sha256:createHash('sha256').update(css).digest('hex'),css});
}
const combined=assets.map(a=>a.css).join('\n');
const wrapper=tags(/<div\b[^>]*>/g).find(tag=>attribute(tag,'data-crosscheck-predictions')==='true');
assert(wrapper,'Missing page wrapper');
const methods=tags(/<section\b[^>]*>/g).filter(tag=>attribute(tag,'data-prediction-id'));
const leaders=tags(/<div\b[^>]*>/g).filter(tag=>attribute(tag,'data-leading-probability')==='true');
assert.equal(methods.length,8);assert.equal(leaders.length,10);
const checkedClasses=new Set();
for(const tag of [wrapper,...methods,...leaders]){
 const value=attribute(tag,'class');assert(value,'CSS-module export missing: rendered element has no class');
 for(const cls of value.split(/\s+/)){
  assert(combined.includes('.'+cls),`Rendered class has no stylesheet selector: ${cls}`);
  checkedClasses.add(cls);
 }
}
assert(assets.some(a=>a.css.includes('#0b0c0f')),'Black page styling missing');
assert(combined.includes('.bg-neutral-950')&&combined.includes('.max-w-5xl'),'Tailwind utilities missing');
const text=s=>s.replace(/<!--[^]*?-->/g,'').replace(/<[^>]+>/g,'');
const stats=/<div\b[^>]*data-prediction-stats="true"[^>]*>([^]*?)<\/div>/.exec(html)?.[1];
assert(stats);assert.match(text(stats),/8 locked predictions\s+·\s+4 companies\s+·\s+0 reviewed scores/);
const targets=[...html.matchAll(/<div\b[^>]*data-guidance-range="true"[^>]*>([^]*?)<\/div>/g)];
assert.equal(targets.length,4);for(const match of targets)assert.match(text(match[1]),/Locked management range:\s+\$/);
const report={checked_at:new Date().toISOString(),route:url.href,status:response.status,stylesheets:assets.map(a=>({url:a.url,status:a.status,bytes:a.bytes,sha256:a.sha256})),rendered_method_rows:methods.length,highlighted_buckets:leaders.length,matching_scoped_classes:[...checkedClasses],tailwind_utilities_present:true,stats_text:text(stats),first_target_text:text(targets[0][1]),browser_automation:false,ledger_access:false};
if(process.argv[3]){await mkdir(dirname(process.argv[3]),{recursive:true});await writeFile(process.argv[3],JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify(report,null,2));
