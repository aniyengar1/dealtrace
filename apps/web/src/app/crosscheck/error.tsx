'use client';
import Link from 'next/link';
export default function CrosscheckError({reset}:{error:Error & {digest?:string};reset:()=>void}) {
  return <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-6"><h1 className="text-xl font-semibold">Company research is unavailable</h1><p className="mt-3 text-sm leading-6">The research store could not be read. No financial values have been substituted. Try again after the database and earnings refresh are available.</p><div className="mt-5 flex gap-5 text-sm"><button onClick={reset} className="font-medium text-emerald-900 underline">Try again</button><Link href="/crosscheck" className="text-emerald-900 underline">Company search</Link></div></div>;
}
