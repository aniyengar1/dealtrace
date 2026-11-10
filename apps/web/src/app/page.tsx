import Link from "next/link";
import { listDealsSummary } from "@/lib/queries";
import { formatDate, formatPriceRange, formatPercentWhole } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const deals = await listDealsSummary();

  return (
    <div>
      <h1 className="text-xl font-semibold tracking-tight">Deals</h1>
      <p className="mt-1 text-sm text-neutral-500">
        {deals.length} deal{deals.length === 1 ? "" : "s"} tracked
      </p>

      <div className="mt-6 overflow-hidden rounded-lg border border-neutral-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-4 py-2.5 font-medium">Target</th>
              <th className="px-4 py-2.5 font-medium">Acquirer</th>
              <th className="px-4 py-2.5 font-medium">Final price</th>
              <th className="px-4 py-2.5 font-medium">Signing date</th>
              <th className="px-4 py-2.5 font-medium">Proposals</th>
              <th className="px-4 py-2.5 font-medium">Reviewed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {deals.map((deal) => {
              const reviewRatio =
                deal.n_facts_total > 0 ? deal.n_facts_reviewed / deal.n_facts_total : null;
              const hasData = deal.n_facts_total > 0;
              return (
                <tr key={deal.slug} className="hover:bg-neutral-50">
                  <td className="px-4 py-3 font-medium">
                    {hasData ? (
                      <Link href={`/deals/${deal.slug}`} className="hover:underline">
                        {deal.target}
                      </Link>
                    ) : (
                      <span className="text-neutral-400">{deal.target}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-neutral-600">{deal.acquirer}</td>
                  <td className="px-4 py-3 tabular-nums">
                    {formatPriceRange(deal.final_price_low, deal.final_price_high)}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{formatDate(deal.signing_date)}</td>
                  <td className="px-4 py-3 tabular-nums">{deal.n_proposals}</td>
                  <td className="px-4 py-3">
                    {hasData ? (
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-20 overflow-hidden rounded-full bg-neutral-200">
                          <div
                            className="h-full rounded-full bg-emerald-500"
                            style={{ width: `${Math.round((reviewRatio ?? 0) * 100)}%` }}
                          />
                        </div>
                        <span className="tabular-nums text-neutral-500">
                          {formatPercentWhole(reviewRatio)}
                        </span>
                      </div>
                    ) : (
                      <span className="text-neutral-400">not extracted</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
