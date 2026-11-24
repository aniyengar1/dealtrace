// Financial display uses string/BigInt arithmetic, never binary floats.
function parts(value:string){
  const match=/^(\d+)(?:\.(\d+))?$/.exec(value);
  if(!match)throw new Error('Invalid decimal');
  return {n:BigInt(match[1]+(match[2]??'')),scale:BigInt(10)**BigInt((match[2]??'').length)};
}
export function percent(value:string,places=1){
  if(![1,2].includes(places))throw new Error('Unsupported display precision');
  const power=BigInt(10)**BigInt(places);
  const {n,scale}=parts(value);const numerator=n*BigInt(100)*power;let q=numerator/scale;const r=numerator%scale;
  if(r*BigInt(2)>scale||(r*BigInt(2)===scale&&q%BigInt(2)===BigInt(1)))q++;
  const fraction=(q%power).toString().padStart(places,'0').replace(/0+$/,'');
  return `${q/power}${fraction?'.'+fraction:''}%`;
}
export function usd(value:string){
  const m=/^(\d+)(?:\.(\d+))?$/.exec(value);if(!m)throw new Error('Invalid amount');
  const fraction=(m[2]??'').replace(/0+$/,'');
  return `$${BigInt(m[1]).toLocaleString('en-US')}${fraction?'.'+fraction:''}`;
}
export function validProbabilities(p:Record<string,string>){
  try{const values=['below','within','above'].map(k=>parts(p[k]));const scale=values.reduce((s,v)=>s>v.scale?s:v.scale,BigInt(1));
    return values.every(v=>v.n<=v.scale)&&values.reduce((s,v)=>s+v.n*(scale/v.scale),BigInt(0))===scale;
  }catch{return false;}
}

function roundedScaled(value:string,unit:bigint,places:number){
  const {n,scale}=parts(value);const power=BigInt(10)**BigInt(places);const numerator=n*power;const denominator=scale*unit;
  let q=numerator/denominator;const r=numerator%denominator;
  if(r*BigInt(2)>denominator||(r*BigInt(2)===denominator&&q%BigInt(2)===BigInt(1)))q++;
  return `${q/power}.${(q%power).toString().padStart(places,'0')}`;
}
export function compactUsd(value:string){
  const {n,scale}=parts(value);
  if(n>=scale*BigInt(1000000000))return `$${roundedScaled(value,BigInt(1000000000),2)}B`;
  if(n>=scale*BigInt(1000000))return `$${roundedScaled(value,BigInt(1000000),2).replace(/\.?0+$/,'')}M`;
  return usd(value);
}
function formatTier(value:string,unit:bigint,places:number,suffix:string){
  if(!suffix)return usd(value);
  const scaled=roundedScaled(value,unit,places);
  const [intPart,fracPart]=scaled.split('.');
  return `$${intPart.replace(/\B(?=(\d{3})+(?!\d))/g,',')}${fracPart?'.'+fracPart:''}${suffix}`;
}
// Picks ONE unit/precision for both ends of a range, falling from billions
// toward millions (then finer decimals within millions) only until the
// display step (e.g. $0.01B = $10M) is no coarser than the range's own
// width -- otherwise two genuinely different endpoints a few million apart
// on a multi-billion base (CRWD's $1,523.2M-$1,529.2M, shown as compactUsd
// per side, rounds to "$1.52B-$1.53B": distinct strings, but each number is
// still unfaithful -- it could be anywhere in a $10M bucket on a $6M-wide
// range) round to numbers that are each individually unfaithful to the
// real endpoint, even when they happen to differ from each other.
export function compactUsdRange(low:string,high:string){
  const {n:ln,scale:ls}=parts(low);
  const {n:hn,scale:hs}=parts(high);
  if(ls!==hs)return `${usd(low)}–${usd(high)}`;
  const width=hn-ln;
  const tiers:{unit:bigint;places:number;suffix:string}[]=
    hn>=ls*BigInt(1000000000)
      ?[{unit:BigInt(1000000000),places:2,suffix:'B'},{unit:BigInt(1000000),places:1,suffix:'M'},{unit:BigInt(1000000),places:2,suffix:'M'},{unit:BigInt(1000000),places:3,suffix:'M'},{unit:BigInt(1),places:0,suffix:''}]
    :hn>=ls*BigInt(1000000)
      ?[{unit:BigInt(1000000),places:1,suffix:'M'},{unit:BigInt(1000000),places:2,suffix:'M'},{unit:BigInt(1000000),places:3,suffix:'M'},{unit:BigInt(1),places:0,suffix:''}]
      :[{unit:BigInt(1),places:0,suffix:''}];
  for(const {unit,places,suffix} of tiers){
    const granularity=unit/BigInt(10)**BigInt(places);
    if(suffix===''||granularity*ls<=width)return `${formatTier(low,unit,places,suffix)}–${formatTier(high,unit,places,suffix)}`;
  }
  return `${usd(low)}–${usd(high)}`;
}
export function dateLabel(value:string,year=true){
  return new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',...(year?{year:'numeric' as const}:{}),timeZone:'UTC'}).format(new Date(value+'T12:00:00Z'));
}
export function periodLabel(start:string,end:string){
  return `${dateLabel(start,start.slice(0,4)!==end.slice(0,4))} – ${dateLabel(end)}`;
}
export function leadDays(lockTimestamp:string,releaseDate:string,releaseTimezone:string){
  const local=new Intl.DateTimeFormat('en-US',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:releaseTimezone}).formatToParts(new Date(lockTimestamp));
  const part=(name:string)=>local.find(p=>p.type===name)!.value;
  const day=`${part('year')}-${part('month')}-${part('day')}`;
  return (Date.parse(releaseDate+'T00:00:00Z')-Date.parse(day+'T00:00:00Z'))/86400000;
}
// Emphasize all ties at the same one-decimal precision users see. The frozen
// residual convention may distinguish equal-count rates at the 24th place.
export function highestDisplayedBuckets(p:Record<'below'|'within'|'above',string>){
  const labels=['below','within','above'] as const;
  const value=(key:typeof labels[number])=>BigInt(percent(p[key]).replace(/[.%]/g,''));
  const max=labels.reduce((m,k)=>value(k)>m?value(k):m,BigInt(0));
  return labels.filter(k=>value(k)===max);
}

export function scoreLabel(value:string){return roundedScaled(value,BigInt(1),4);}
export function validBrier(value:string){try{const {n,scale}=parts(value);return n<=BigInt(2)*scale;}catch{return false;}}
export function validRate(value:string){try{const {n,scale}=parts(value);return n<=scale;}catch{return false;}}
