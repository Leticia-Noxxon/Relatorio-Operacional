import type { ReactNode } from "react";

export function Panel({
  title,
  children,
  className = "",
  right,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  right?: ReactNode;
}) {
  return (
    <section
      className={`rounded-2xl border border-[var(--line)] bg-white shadow-[0_2px_10px_rgba(19,84,135,.05)] ${className}`}
    >
      {(title || right) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] px-4 py-3">
          {title ? (
            <h3 className="text-sm font-bold text-[var(--p1)]">{title}</h3>
          ) : (
            <span />
          )}
          {right}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function KpiCard({
  label,
  value,
  icon,
  iconTone = "var(--p4)",
  iconColor = "var(--p1)",
}: {
  label: string;
  value: string | number;
  icon?: ReactNode;
  iconTone?: string;
  iconColor?: string;
}) {
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white px-4 py-3.5 text-left shadow-[0_2px_10px_rgba(19,84,135,.05)]">
      <div className="mb-2.5 flex items-start justify-between gap-2">
        <div className="text-[13px] font-semibold text-[var(--muted)]">{label}</div>
        {icon ? (
          <span
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
            style={{ background: iconTone, color: iconColor }}
          >
            {icon}
          </span>
        ) : null}
      </div>
      <div className="text-[1.85rem] font-extrabold leading-none tracking-tight text-[var(--p1)]">
        {value}
      </div>
    </div>
  );
}

export function VerticalBars({
  items,
}: {
  items: { label: string; value: number }[];
}) {
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="flex h-[210px] items-end justify-around gap-3 border-b border-[var(--line)] px-2 pt-6">
      {items.map((item) => {
        const h = Math.max(8, Math.round((item.value / max) * 150));
        return (
          <div
            key={item.label}
            className="flex h-full max-w-[96px] flex-1 flex-col items-center justify-end gap-2"
          >
            <div
              className="relative w-full rounded-t-lg"
              style={{
                height: h,
                background: "linear-gradient(180deg, var(--p5), var(--p2))",
              }}
            >
              <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-xs font-bold text-[var(--p1)]">
                {item.value.toLocaleString("pt-BR")}
              </span>
            </div>
            <div className="min-h-[32px] text-center text-[11px] font-semibold leading-tight text-[var(--muted)]">
              {item.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Doughnut({
  online,
  offline,
  label,
  size = 140,
}: {
  online: number;
  offline: number;
  label?: string;
  size?: number;
}) {
  const total = online + offline;
  const pct = total ? (online / total) * 100 : 0;
  const r = size * 0.36;
  const c = 2 * Math.PI * r;
  const dash = (pct / 100) * c;
  const stroke = Math.max(18, size * 0.16);
  const cx = size / 2;
  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
        <circle
          cx={cx}
          cy={cx}
          r={r}
          fill="none"
          stroke="#E89A9A"
          strokeWidth={stroke}
        />
        <circle
          cx={cx}
          cy={cx}
          r={r}
          fill="none"
          stroke="#7BC67E"
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${c - dash}`}
          strokeDashoffset={c * 0.25}
          transform={`rotate(-90 ${cx} ${cx})`}
        />
        <text
          x={cx}
          y={cx - 2}
          textAnchor="middle"
          fill="var(--p1)"
          fontSize={size * 0.12}
          fontWeight="800"
        >
          {pct.toFixed(1).replace(".", ",")}%
        </text>
        <text
          x={cx}
          y={cx + size * 0.1}
          textAnchor="middle"
          fill="var(--muted)"
          fontSize={size * 0.07}
          fontWeight="600"
        >
          Disponibilidade
        </text>
      </svg>
      {label ? (
        <div className="mt-1 text-xs font-bold text-[var(--p1)]">{label}</div>
      ) : null}
    </div>
  );
}

export function InlineQtyBar({
  value,
  max,
}: {
  value: number;
  max: number;
}) {
  const w = max ? Math.max(4, Math.round((value / max) * 100)) : 0;
  return (
    <div className="grid grid-cols-[1fr_52px] items-center gap-2">
      <div className="h-2 overflow-hidden rounded-full bg-[#eef5f8]">
        <div
          className="h-full rounded-full bg-[var(--p4)]"
          style={{ width: `${w}%` }}
        />
      </div>
      <div className="text-center text-sm font-semibold tabular-nums">
        {value.toLocaleString("pt-BR")}
      </div>
    </div>
  );
}

export function MonthSeg({
  months,
  value,
  onChange,
}: {
  months: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  const opts = ["Todos", ...months];
  return (
    <div className="inline-flex rounded-[10px] bg-[var(--p4)] p-0.5">
      {opts.map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          className={`h-8 rounded-lg px-3 text-xs font-semibold ${
            value === m
              ? "bg-[var(--p1)] text-white"
              : "bg-transparent text-[var(--p1)]"
          }`}
        >
          {m}
        </button>
      ))}
    </div>
  );
}

export const STATUS_COLOR: Record<string, string> = {
  ok: "#7BC67E",
  bad: "#E89A9A",
  erro: "#E89A9A",
  off: "#C5CED6",
  na: "#C5CED6",
};
