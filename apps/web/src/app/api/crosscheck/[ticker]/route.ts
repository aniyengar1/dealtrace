import { companyData } from '@/lib/crosscheck/queries';
import { validAsOf } from '@/lib/crosscheck/identity';
export const dynamic='force-dynamic';
export async function GET(request:Request,{params}:{params:Promise<{ticker:string}>}) {
  const {ticker}=await params;const asOf=new URL(request.url).searchParams.get('asOf')??undefined;
  if(asOf!==undefined&&!validAsOf(asOf)) return Response.json({error:'Invalid as-of date'},{status:400});
  try {
    const data=await companyData(ticker,asOf);
    if(!data) return Response.json({error:'Unsupported company'},{status:404});
    if(!data.report) return Response.json({error:'No report for this cutoff',available_dates:data.dates},{status:404});
    return Response.json(data.report,{headers:{'Cache-Control':'no-store'}});
  } catch {return Response.json({error:'Research store unavailable'},{status:503});}
}
