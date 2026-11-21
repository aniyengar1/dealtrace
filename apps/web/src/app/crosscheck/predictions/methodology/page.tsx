import Link from 'next/link';
import styles from '../predictions.module.css';
export const metadata={title:'Prediction methodology | Crosscheck'};
export default function Methodology(){return <article className={styles.page}>
 <p className={styles.eyebrow}>DealTrace / Crosscheck</p><h1>Methodology</h1>
 <p><Link href="/crosscheck/predictions">Back to locked predictions</Link></p>
 <div className={styles.footer}>
 <p>Each prediction concerns consolidated reported revenue for an exact fiscal quarter and the original locked management guidance range. Below means less than its lower bound; within includes both endpoints; above means greater than its upper bound. Equality with point guidance is within.</p>
 <p>Empirical probabilities are observed below/within/above frequencies. Laplace adds one observation to each class before dividing by the sample size plus three. Both methods use the same eligible history and target. Company rates require at least six eligible quarters in the most recent eight-quarter window; otherwise the documented pooled fallback requires at least twelve eligible observations from two companies. The current published companies all use their own histories.</p>
 <p>The first two probabilities are rounded half-even to twenty-four decimal places; the third receives the residual so the stored total is exactly one. The page displays whole-number or one-decimal percentages and emphasizes every bucket tied for the highest displayed probability. Small, overlapping histories are not evidence of calibration or predictive certainty.</p>
 <section id="backtest"><h2>BACKTEST — public-date reconstruction</h2><p>The separate 73-company, 532-case walk-forward evaluation uses only earlier quarters whose result and SEC actual availability precede each simulated date. Simulated dates are fourteen days before known historical results. Frozen minimums and pooling remain unchanged; the research pool is larger than the ten-company live pool. Today’s source curation and survivor selection introduce hindsight. Most cases use pooled history. These are descriptive backtest results, not live predictions or evidence of calibration. The complete report, per-company results, calibration bins, source hashes and input IDs are in earnings/reports/backtest_walkforward.md and its JSON companion.</p></section>
 <p>Brier score is the unscaled sum of three squared probability errors: zero is best and two worst. Log score is not implemented in the frozen method; no clipping or new zero-probability convention has been added.</p>
 <p>Lead time counts calendar dates from the lock timestamp in the announcement’s documented timezone to the announced release date. It does not infer a publication clock time from an earnings call or change the lock deadline.</p>
 <p>Pending means no reviewed score in the publication copy, not proof that results remain unpublished. Acquisition scope, reporting basis and exact fiscal-period comparability require source-backed outcome review before scoring.</p>
 <p>The page reads a separate published copy, never the live ledger. Expand each method’s evidence to inspect its immutable input digest, lock timestamp and sources. Digests are calculated for publication from locked evidence; they are not external lock-time notarizations. Corrections remain separate versions.</p>
 </div>
 </article>;}
