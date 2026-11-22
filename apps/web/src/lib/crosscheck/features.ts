import 'server-only';
import type { CompanyReport, PublicCompanyReport } from './types';

// Server-only, opt-in and checked at request time. Never expose a public env flag.
export function experimentalAnnualForecastEnabled(): boolean {
  return process.env.CROSSCHECK_EXPERIMENTAL_ANNUAL_FORECAST === 'true';
}

export function publicReport(report: CompanyReport): PublicCompanyReport {
  if (experimentalAnnualForecastEnabled()) return report;
  const { forecast: _forecast, forecast_display: _display, evaluation: _evaluation,
    evaluation_display: _evaluationDisplay, ...research } = report;
  // Preserve the stored report and evaluation; project a separate public view.
  void _forecast; void _display; void _evaluation; void _evaluationDisplay;
  return { ...research,
    changes: research.changes ? { ...research.changes,
      causes: research.changes.causes.filter(c=>!c.startsWith('forecast_') && c!=='historical_evaluation_changed') } : research.changes,
    coverage_notes: research.coverage_notes?.filter(note=>!/(forecast|evaluation|prediction)/i.test(note)),
  };
}
