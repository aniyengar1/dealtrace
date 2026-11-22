// Minimal CSV encoder -- quotes a field only when it contains a comma,
// quote, or newline, doubling any embedded quotes (RFC 4180). No
// library needed for a handful of flat, public-field rows.
function csvField(value: string | number | null): string {
  const s = value === null ? "" : String(value);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function toCsv(headers: string[], rows: (string | number | null)[][]): string {
  const lines = [headers.map(csvField).join(",")];
  for (const row of rows) lines.push(row.map(csvField).join(","));
  return lines.join("\r\n");
}
