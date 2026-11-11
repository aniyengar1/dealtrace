import { listCompanies } from '@/lib/crosscheck/queries';
import Search from './Search';
export const dynamic='force-dynamic';
export default async function CrosscheckPage() {
  const companies=await listCompanies();
  return <div><p className="text-xs font-semibold uppercase tracking-widest text-emerald-800">DealTrace / Crosscheck</p>
    <h1 className="mt-3 text-4xl font-semibold tracking-tight">Can they hit the target?</h1>
    <p className="mt-4 max-w-2xl text-base leading-7 text-neutral-600">Follow reported financials, management’s annual revenue guidance, and the performance needed to get there. Explore a transparent baseline forecast, with the evidence behind every number.</p>
    <div className="mt-6 flex flex-wrap gap-2 text-xs text-neutral-600"><span className="rounded-full border border-neutral-200 bg-white px-3 py-1.5">{companies.length} supported companies</span><span className="rounded-full border border-neutral-200 bg-white px-3 py-1.5">SEC financial sources</span><span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-amber-900">Forecasts are experimental</span></div>
    {!companies.length ? <p role="status" className="mt-8 rounded-lg border p-6">No companies are loaded yet. Run the earnings ingestion and product refresh workflow.</p> : <Search companies={companies} />}
  </div>;
}
