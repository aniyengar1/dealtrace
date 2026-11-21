import { ImageResponse } from "next/og";
import { getDealBySlug } from "@/lib/queries";
import { getDealMetricsBySlug } from "@/lib/dealMetrics";
import { dealTitle } from "@/lib/labels";
import { formatDate, formatPrice, formatMultiple } from "@/lib/format";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [deal, metrics] = await Promise.all([getDealBySlug(slug), getDealMetricsBySlug(slug)]);

  const title = deal && metrics ? dealTitle(metrics.acquirerDisplay, metrics.targetDisplay) : "DealTrace";
  const priceLabel =
    metrics?.finalPrice == null
      ? null
      : metrics.pricePlausible === false
        ? null
        : metrics.finalPriceIsRatio
          ? formatMultiple(metrics.finalPrice)
          : formatPrice(metrics.finalPrice);

  const stats = [
    priceLabel ? { label: metrics?.finalPriceIsRatio ? "Exchange ratio" : "Price per share", value: priceLabel } : null,
    metrics?.signingDate ? { label: "Signed", value: formatDate(metrics.signingDate) } : null,
    metrics ? { label: "Bidders", value: String(metrics.nBidders) } : null,
  ].filter((s): s is { label: string; value: string } => s !== null);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          backgroundColor: "#0a0a0b",
          color: "#f2f2f3",
          fontFamily: "serif",
        }}
      >
        <div style={{ display: "flex", fontSize: 28, color: "#c0c4cc", letterSpacing: 4, textTransform: "uppercase" }}>
          DealTrace
        </div>
        <div style={{ display: "flex", marginTop: 20, fontSize: 60, lineHeight: 1.15, maxWidth: 1000 }}>{title}</div>
        {stats.length > 0 && (
          <div style={{ display: "flex", marginTop: 48, gap: 56 }}>
            {stats.map((s) => (
              <div key={s.label} style={{ display: "flex", flexDirection: "column" }}>
                <div style={{ display: "flex", fontSize: 40, color: "#c0c4cc" }}>{s.value}</div>
                <div
                  style={{
                    display: "flex",
                    marginTop: 8,
                    fontSize: 20,
                    color: "#8b8e94",
                    fontFamily: "sans-serif",
                    textTransform: "uppercase",
                    letterSpacing: 2,
                  }}
                >
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    ),
    { ...size }
  );
}
