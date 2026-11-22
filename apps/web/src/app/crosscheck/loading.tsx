export default function Loading() {
  return <div role="status" aria-busy="true" className="space-y-5"><p className="text-sm text-neutral-600">Loading company research and evidence…</p><div className="h-12 w-2/3 animate-pulse rounded-lg bg-neutral-200"/><div className="h-52 animate-pulse rounded-xl bg-neutral-100"/><div className="grid grid-cols-3 gap-3">{[0,1,2].map(i=><div key={i} className="h-32 animate-pulse rounded-xl bg-neutral-100"/>)}</div></div>;
}
