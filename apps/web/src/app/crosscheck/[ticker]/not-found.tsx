import Link from 'next/link';
export default function NotCovered() {
  return <div role="status" className="rounded-xl border border-neutral-200 bg-white p-7"><p className="text-xs font-semibold uppercase tracking-widest text-neutral-500">Coverage unavailable</p><h1 className="mt-3 text-2xl font-semibold">This company is not supported yet.</h1><p className="mt-3 max-w-xl text-sm leading-6 text-neutral-600">Crosscheck currently covers a curated company universe. There are no financial metrics or management targets here for an unsupported ticker.</p><Link href="/crosscheck" className="mt-5 inline-block text-sm font-medium text-emerald-800 underline">Search supported companies →</Link></div>;
}
