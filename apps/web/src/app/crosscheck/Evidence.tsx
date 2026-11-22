import type { Source } from '@/lib/crosscheck/types';
export default function Evidence({ sources, formula }: { sources: Source[]; formula?: string | null }) {
  return <details className="mt-2 text-left text-xs font-normal text-neutral-500"><summary className="cursor-pointer text-emerald-800 hover:underline">Evidence{formula?' & calculation':''}</summary>
    <div className="mt-2 space-y-3 rounded-lg border border-neutral-200 bg-neutral-50 p-3">
      {formula && <p className="leading-5 text-neutral-700">{formula}</p>}
      {sources.map(s=><div key={s.id} className="break-words leading-5"><p className="font-medium text-neutral-800">{s.value} {s.unit}</p><p>{s.start} → {s.end} · filed {s.filed}</p><p className="break-all">{s.concept}</p><p>Accession {s.accession}</p><p className="break-all font-mono text-[10px]">Record {s.id}</p><a href={s.source_url} target="_blank" rel="noreferrer" className="font-medium text-emerald-800 underline">Open SEC source ↗</a></div>)}
    </div>
  </details>;
}
