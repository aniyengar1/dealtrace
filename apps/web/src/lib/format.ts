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

// True precision for a stat band number: a median that landed on a
// whole number (e.g. 2 bidders) shows as "2", not "2.0"; one that
// didn't (e.g. a days-to-signing median of 290.5, or any percentage)
// shows its real first decimal instead of rounding it away.
export function statDecimals(value: number): number {
  return Number.isInteger(value) ? 0 : 1;
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

function monthDayYear(isoDate: string): { month: string; day: number; year: number } {
  const [y, m, d] = isoDate.split("-").map(Number);
  const month = new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    month: "short",
    timeZone: "UTC",
  });
  return { month, day: d, year: y };
}

// Renders a date at exactly the precision the extraction actually
// resolved, never a fabricated day: "day" shows the real calendar date,
// "month" drops the (placeholder) day entirely, "range" shows both
// ends -- except a full Jan 1-Dec 31 range of one year, which is a
// synthetic "sometime this year" bound (see extract.py's date
// resolution), not two real days the filing mentions, so that renders
// as just the year. "unknown" (or a missing date_start) falls back to
// the filing's own phrase rather than inventing a date at all.
export function formatEventDate(event: {
  date_text: string;
  date_start: string | null;
  date_end: string | null;
  date_precision: "day" | "month" | "range" | "unknown";
}): string {
  const { date_text, date_start, date_end, date_precision } = event;

  if (date_precision === "unknown" || !date_start) {
    return date_text;
  }

  if (date_precision === "day") {
    return formatDate(date_start);
  }

  if (date_precision === "month") {
    const { month, year } = monthDayYear(date_start);
    return `${month} ${year}`;
  }

  // range
  if (!date_end) return formatDate(date_start);

  if (date_start.endsWith("-01-01") && date_end.endsWith("-12-31")) {
    const startYear = date_start.slice(0, 4);
    const endYear = date_end.slice(0, 4);
    if (startYear === endYear) return startYear;
  }

  const start = monthDayYear(date_start);
  const end = monthDayYear(date_end);
  if (start.year === end.year) {
    return `${start.month} ${start.day} – ${end.month} ${end.day}, ${start.year}`;
  }
  return `${start.month} ${start.day}, ${start.year} – ${end.month} ${end.day}, ${end.year}`;
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
