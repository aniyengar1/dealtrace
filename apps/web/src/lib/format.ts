export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `$${value.toFixed(2)}`;
}

export function formatPriceRange(
  low: number | null | undefined,
  high: number | null | undefined
): string {
  if (low === null && high === null) return "—";
  if (low === high || low === null || high === null) {
    return formatPrice(low ?? high);
  }
  return `${formatPrice(low)}–${formatPrice(high)}`;
}

export function formatMultiple(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}x`;
}

export function formatMultipleRange(
  low: number | null | undefined,
  high: number | null | undefined
): string {
  if (low === null && high === null) return "—";
  if (low === high || low === null || high === null) {
    return formatMultiple(low ?? high);
  }
  return `${formatMultiple(low)}–${formatMultiple(high)}`;
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-");
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function formatPercentWhole(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined) return "—";
  return `${Math.round(ratio * 100)}%`;
}

const MONTH_INDEX: Record<string, number> = {
  jan: 0, january: 0, feb: 1, february: 1, mar: 2, march: 2, apr: 3, april: 3,
  may: 4, jun: 5, june: 5, jul: 6, july: 6, aug: 7, august: 7,
  sep: 8, sept: 8, september: 8, oct: 9, october: 9, nov: 10, november: 10,
  dec: 11, december: 11,
};

// Proposal.date is the filing's own phrase ("September 27, 2022", or a
// relative one like "Later that same day"); date_resolved is only ever
// populated for the relative case (see schemas.Proposal), so an absolute
// date has to be parsed straight from date_text here instead.
export function parseFilingDate(dateText: string, dateResolved: string | null): Date | null {
  if (dateResolved) {
    const [y, m, d] = dateResolved.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d));
  }
  const monthMatch = dateText.match(/([A-Za-z]+)\s+(\d{1,2})/);
  const yearMatch = dateText.match(/(\d{4})/);
  if (!monthMatch || !yearMatch) return null;
  const monthIdx = MONTH_INDEX[monthMatch[1].toLowerCase()];
  if (monthIdx === undefined) return null;
  return new Date(Date.UTC(Number(yearMatch[1]), monthIdx, Number(monthMatch[2])));
}
