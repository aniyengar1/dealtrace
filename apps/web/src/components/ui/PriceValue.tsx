import { formatPrice } from "@/lib/format";

// deal_metrics.price_plausible is false when the pipeline's own sanity
// check on an extracted price failed (wrong units, a misread digit,
// etc.) -- rendering that number anyway would just present a known-bad
// figure with full confidence, so it's hidden behind a plain dash with
// a tooltip instead of formatted like a real price.
export function PriceValue({
  price,
  plausible,
  className,
}: {
  price: number | null;
  plausible: boolean | null;
  className?: string;
}) {
  if (plausible === false) {
    return (
      <span className={className} title="price not reliably extracted">
        —
      </span>
    );
  }
  return <span className={className}>{formatPrice(price)}</span>;
}
