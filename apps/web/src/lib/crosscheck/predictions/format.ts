// Financial display uses string/BigInt arithmetic, never binary floats.
function parts(value:string){
  const match=/^(\d+)(?:\.(\d+))?$/.exec(value);
  if(!match)throw new Error('Invalid decimal');
  return {n:BigInt(match[1]+(match[2]??'')),scale:BigInt(10)**BigInt((match[2]??'').length)};
}
export function percent(value:string){
  const {n,scale}=parts(value);const numerator=n*BigInt(10000);let q=numerator/scale;const r=numerator%scale;
  if(r*BigInt(2)>scale||(r*BigInt(2)===scale&&q%BigInt(2)===BigInt(1)))q++;
  return `${q/BigInt(100)}.${(q%BigInt(100)).toString().padStart(2,'0')}%`;
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
