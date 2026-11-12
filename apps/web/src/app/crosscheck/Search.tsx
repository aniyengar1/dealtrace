'use client';
import { useState } from 'react';
import Link from 'next/link';
import { filterCompanies } from '@/lib/crosscheck/identity';
import type { CompanySummary } from '@/lib/crosscheck/types';

export default function Search({ companies }: { companies: CompanySummary[] }) {
  const [query,setQuery]=useState('');
  const results=filterCompanies(companies,query);
  return <>
    <label htmlFor="company-search" className="mt-8 block text-sm font-medium">Find a supported company</label>
    <input id="company-search" type="search" autoComplete="off" placeholder="Search company name or ticker, e.g. PagerDuty or PD" value={query} onChange={e=>setQuery(e.target.value)} className="mt-2 w-full rounded-xl border border-neutral-300 bg-white px-4 py-4 text-base shadow-sm outline-none focus:border-emerald-700 focus:ring-2 focus:ring-emerald-100" />
    <p aria-live="polite" className="mt-3 text-sm text-neutral-500">{results.length} of {companies.length} supported companies</p>
    {!results.length && <div role="status" className="mt-6 rounded-xl border border-neutral-200 bg-white p-6"><h2 className="font-semibold">No supported company matches “{query}”.</h2><p className="mt-2 text-sm text-neutral-600">Coverage is limited to this curated universe. We do not have a financial report for that search.</p><button onClick={()=>setQuery('')} className="mt-4 text-sm font-medium text-emerald-800 underline">Show supported companies</button></div>}
    <div className="mt-5 grid gap-3 sm:grid-cols-2">
      {results.map(c=><Link key={c.ticker} href={`/crosscheck/${c.ticker}`} className="group rounded-xl border border-neutral-200 bg-white p-5 transition hover:border-emerald-600 hover:shadow-sm focus:outline-2 focus:outline-emerald-700">
        <div className="flex items-center justify-between gap-3"><span className="font-mono text-sm font-semibold text-emerald-800">{c.ticker}</span><span className="text-xs text-neutral-500">{c.forecast_status==='blocked'?'Comparison blocked':c.forecast_status==='experimental'?'Experimental forecast':c.hurdle_state==='blocked'?'Comparison blocked':c.as_of?'Research available':'Report pending'}</span></div>
        <h2 className="mt-2 font-semibold">{c.name}</h2><p className="mt-3 text-xs text-neutral-500">{c.as_of?`Research snapshot ${c.as_of}`:'No published snapshot yet'} <span className="float-right group-hover:text-emerald-800" aria-hidden="true">View company →</span></p>
      </Link>)}
    </div>
  </>;
}
