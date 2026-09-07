/**
 * The demand curve, as a small inline SVG area chart.
 *
 * WHY NOT A CHART LIBRARY
 * -----------------------
 * `chart.js` sits in package.json but is imported nowhere in the app -- it is
 * a leftover dependency, so using it here would mean shipping a ~200KB runtime
 * to the Market Decision Center for the first time, to draw at most thirty
 * points. Rule 16 asks that the page stay fast and that heavy visualisation
 * assets not load before the farmer requests a forecast; the cheapest way to
 * honour that is not to introduce the weight at all. This is ~60 lines of SVG,
 * costs nothing, and needs no lazy-loading in front of it.
 *
 * ACCESSIBILITY
 * -------------
 * Direction is never carried by colour alone: the series is drawn as a line
 * with an area fill, and the caller states the trend in words beside it. The
 * chart exposes a text summary through <title>/aria-label so a screen reader
 * gets the shape and the totals rather than "graphic".
 *
 * A 30-day series is bucketed before drawing -- thirty labels on a phone is
 * unreadable, so long horizons are shown as their weekly shape while the
 * underlying daily numbers stay intact in the API response.
 */
import { useTranslation } from 'react-i18next';
import { number } from '@/utils/format';
import type { DemandForecastPoint } from '@/types/api';

interface Props {
  points: DemandForecastPoint[];
  /** Bucket into groups when the series is long, so labels stay readable. */
  bucketed?: boolean;
  ariaSummary: string;
}

interface Band {
  label: string;
  kg: number;
}

/** Group a long series into readable spans.
 *
 *  Bands carry the AVERAGE demand per day, not the sum. A 30-day series does
 *  not divide evenly into weeks, so summing made the final short band (days
 *  29-30, two days against seven) plot as a cliff -- the chart showed demand
 *  collapsing when the forecast said steady. An average is comparable however
 *  many days a band happens to hold, so the line reflects the actual shape.
 *  The headline total still comes from the API, summed over every day. */
function toBands(points: DemandForecastPoint[], bucketed: boolean): Band[] {
  if (!bucketed || points.length <= 7) {
    return points.map((p) => ({
      label: p.date.slice(8, 10),          // day of month, compact on mobile
      kg: p.predicted_demand_kg,
    }));
  }
  const size = points.length <= 15 ? 5 : 7;
  const bands: Band[] = [];
  for (let i = 0; i < points.length; i += size) {
    const chunk = points.slice(i, i + size);
    bands.push({
      label: `${i + 1}-${i + chunk.length}`,
      kg: chunk.reduce((s, p) => s + p.predicted_demand_kg, 0) / chunk.length,
    });
  }
  return bands;
}

export function DemandChart({ points, bucketed = false, ariaSummary }: Props) {
  const { t } = useTranslation();
  const bands = toBands(points, bucketed);
  if (!bands.length) return null;

  const W = 320;
  const H = 96;
  const PAD = 4;
  const max = Math.max(...bands.map((b) => b.kg), 1);
  const step = bands.length > 1 ? (W - PAD * 2) / (bands.length - 1) : 0;
  const x = (i: number) => (bands.length > 1 ? PAD + i * step : W / 2);
  const y = (kg: number) => H - PAD - (kg / max) * (H - PAD * 2);

  const line = bands.map((b, i) => `${x(i).toFixed(1)},${y(b.kg).toFixed(1)}`).join(' ');
  const area = `${PAD},${H - PAD} ${line} ${x(bands.length - 1).toFixed(1)},${H - PAD}`;

  return (
    <figure className="space-y-1.5">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-24 w-full"
        role="img"
        aria-label={ariaSummary}
        preserveAspectRatio="none"
      >
        <title>{ariaSummary}</title>
        <polygon points={area} className="fill-primary/15" />
        <polyline
          points={line}
          className="fill-none stroke-primary"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
        {bands.map((b, i) => (
          <circle
            key={i} cx={x(i)} cy={y(b.kg)} r={2.5}
            className="fill-primary"
          />
        ))}
      </svg>
      {/* Labels live outside the SVG so they never scale with preserveAspectRatio
          "none" and stay legible at phone width. */}
      <div className="flex justify-between text-label text-ink-muted">
        <span>{bands[0].label}</span>
        {bands.length > 2 && <span>{bands[Math.floor(bands.length / 2)].label}</span>}
        <span>{bands[bands.length - 1].label}</span>
      </div>
      <figcaption className="text-label text-ink-muted">
        {/* Bucketed bands plot a daily average, so the caption says so rather
            than implying the peak is a single day's total. */}
        {t(bucketed ? 'demand.chart_peak_daily' : 'demand.chart_peak',
           { kg: number(Math.round(max)) })}
      </figcaption>
    </figure>
  );
}
