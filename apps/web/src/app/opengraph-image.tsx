import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
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
          backgroundColor: "#070b1f",
          color: "#eef0f8",
          fontFamily: "serif",
        }}
      >
        <div style={{ display: "flex", fontSize: 32, color: "#c9a44c", letterSpacing: 4, textTransform: "uppercase" }}>
          DealTrace
        </div>
        <div style={{ display: "flex", marginTop: 24, fontSize: 56, lineHeight: 1.15, maxWidth: 980 }}>
          Every public-company sale process, extracted from SEC filings.
        </div>
        <div style={{ display: "flex", marginTop: 32, fontSize: 24, color: "#97a0c3", fontFamily: "sans-serif" }}>
          Who was contacted · how bids moved · how long it took — every fact sourced.
        </div>
      </div>
    ),
    { ...size }
  );
}
