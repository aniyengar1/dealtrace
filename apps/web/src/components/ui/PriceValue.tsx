import { formatMultiple, formatPrice } from "@/lib/format";

// deal_metrics.price_plausible is false when the pipeline's own sanity
// check on an extracted price failed (wrong units, a misread digit,
// etc.) -- rendering that number anyway would just present a known-bad
// figure with full confidence, so it's hidden behind a plain dash with
// a tooltip instead of formatted like a real price.
//
// A stock-for-stock deal's "price" is sometimes a bare exchange ratio
// ("0.3575" meaning 0.3575 shares of the acquirer per target share),
// not a dollar amount at all -- showing "$0.36" for that would be
// actively wrong, not just imprecise. consideration_type alone can't
// distinguish this, though: plenty of all-stock deals still state a
// genuine dollar "implied value per share" (Mr. Cooper/Rocket's
// $154.00), and a bare ratio can land in exactly the same numeric
// range as a real low-priced stock's per-share dollar price (both
// commonly fall between 0.5 and 3) -- there's no reliable value-based
// cutoff. deal_metrics.final_price_is_ratio (see
// src.bulk_stats.compute_final_price_is_ratio_for_deal) resolves this
// server-side by checking whether the final proposal's own quote ever
// spells the number out with a leading "$"; finalPriceIsRatio is
// rendered as a ratio ("0.36x", reusing the same "Nx" convention
// already used for valuation multiples elsewhere on the site) rather
// than with a "$" prefix implying a cash price that was never
// extracted.
export function PriceValue({
  price,
  plausible,
  finalPriceIsRatio,
  className,
}: {
  price: number | null;
  plausible: boolean | null;
  finalPriceIsRatio?: boolean | null;
  className?: string;
}) {
  if (plausible === false) {
    return (
      <span className={className} title="price not reliably extracted">
        —
      </span>
    );
  }
  if (finalPriceIsRatio) {
    return (
      <span className={className} title="stock-for-stock exchange ratio, not a cash price">
        {formatMultiple(price)}
      </span>
    );
  }
  return <span className={className}>{formatPrice(price)}</span>;
}
