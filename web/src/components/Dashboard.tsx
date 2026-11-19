import { useEffect, useRef, useState, type ReactNode } from "react";

export function Panel({
  title,
  children,
  className = "",
  right,
  bodyClassName = "p-4",
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  right?: ReactNode;
  bodyClassName?: string;
}) {
  return (
    <section
      className={`min-w-0 rounded-2xl border border-[var(--line)] bg-white shadow-[0_2px_10px_rgba(19,84,135,.05)] ${className}`}
    >
      {(title || right) && (
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] px-4 py-3">
          {title ? (
            <h3 className="text-sm font-bold text-[var(--p1)]">{title}</h3>
          ) : (
            <span />
          )}
          {right}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

export function KpiCard({
  label,
  value,
  icon,
  iconTone = "var(--p4)",
  iconColor = "var(--p1)",
  dense = false,
}: {
  label: string;
  value: string | number;
  icon?: ReactNode;
  iconTone?: string;
  iconColor?: string;
  dense?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border border-[var(--line)] bg-white text-left shadow-[0_2px_10px_rgba(19,84,135,.05)] ${
        dense ? "px-3 py-2" : "px-4 py-3.5"
      }`}
    >
      <div className={`flex items-start justify-between gap-2 ${dense ? "mb-1" : "mb-2.5"}`}>
        <div className="min-w-0 text-[13px] font-medium leading-snug text-[var(--muted)]">{label}</div>
        {icon ? (
          <span
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
            style={{ background: iconTone, color: iconColor }}
          >
            {icon}
          </span>
        ) : null}
      </div>
      <div
        className={`font-extrabold leading-none tracking-tight text-[var(--p1)] ${
          dense ? "text-2xl" : "text-[1.85rem]"
        }`}
      >
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
  const minWidth = Math.max(240, items.length * 54);
  return (
    <div className="max-w-full overflow-x-auto">
      <div
        className="flex h-[200px] items-end justify-around gap-2 border-b border-[var(--line)] px-1 pt-7"
        style={{ minWidth }}
      >
        {items.map((item) => {
          const h = Math.max(8, Math.round((item.value / max) * 140));
          return (
            <div
              key={item.label}
              className="flex h-full w-16 max-w-[88px] flex-1 flex-col items-center justify-end gap-2"
            >
              <div
                className="relative w-full rounded-t-lg"
                style={{
                  height: h,
                  background: "linear-gradient(180deg, var(--p5), var(--p2))",
                }}
              >
                <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[11px] font-medium tabular-nums text-[var(--p1)]">
                  {item.value.toLocaleString("pt-BR")}
                </span>
              </div>
              <div className="line-clamp-3 min-h-[2.5rem] w-full text-center text-[10px] font-medium leading-tight text-[var(--muted)] sm:text-[11px]">
                {item.label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function AngledLabel({ text }: { text: string }) {
  return (
    <span className="inline-block whitespace-nowrap px-px text-[10px] font-normal leading-[1.05] tracking-tight text-white [text-orientation:mixed] [writing-mode:vertical-lr]">
      {text}
    </span>
  );
}

export function formatPercent(part: number, total: number) {
  if (!total) return "0,0%";
  return `${((part / total) * 100).toFixed(1).replace(".", ",")}%`;
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
  const stroke = Math.max(11, Math.round(size * 0.07));
  const r = size / 2 - stroke / 2 - 1;
  const c = 2 * Math.PI * r;
  const dash = (pct / 100) * c;
  const cx = size / 2;
  const percentText = formatPercent(online, total);
  return (
    <div className="mx-auto flex w-full flex-col items-center" style={{ maxWidth: size }}>
      <svg
        viewBox={`0 0 ${size} ${size}`}
        className="block h-auto w-full"
        role="img"
        aria-label={
          label
            ? `${label}: ${percentText} online, ${formatPercent(offline, total)} offline`
            : `${percentText} online, ${formatPercent(offline, total)} offline`
        }
      >
        <circle cx={cx} cy={cx} r={r} fill="none" stroke="#E89A9A" strokeWidth={stroke} />
        <circle
          cx={cx}
          cy={cx}
          r={r}
          fill="none"
          stroke="#7BC67E"
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${Math.max(c - dash, 0)}`}
          strokeDashoffset={c * 0.25}
          transform={`rotate(-90 ${cx} ${cx})`}
        />
        <text
          x={cx}
          y={cx}
          textAnchor="middle"
          dominantBaseline="central"
          fill="#135487"
          fontSize={size * 0.105}
          fontWeight="500"
          fontFamily="var(--font-sans), Inter, system-ui, sans-serif"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {percentText}
        </text>
      </svg>
      {label ? (
        <div className="mt-1.5 text-center text-[12px] font-medium text-[var(--p1)]">{label}</div>
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
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_3.25rem] items-center gap-2">
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
    <div className="inline-flex max-w-full flex-wrap gap-0.5 rounded-[10px] bg-[var(--p4)] p-0.5">
      {opts.map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          className={`h-7 rounded-lg px-2 text-[11px] font-medium sm:h-8 sm:px-3 sm:text-xs ${
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

export function TableFrame({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`min-w-0 max-w-full overflow-x-auto ${className}`}>{children}</div>
  );
}

/** Wide matrix: vertical wheel pans sideways, and the mouse can drag to pan. */
export function WheelPan({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let drag: { x: number; y: number; left: number; top: number } | null = null;

    const onWheel = (event: WheelEvent) => {
      if (el.scrollWidth <= el.clientWidth + 1) return;
      let dx = event.deltaX;
      let dy = event.deltaY;
      if (event.deltaMode === 1) {
        dx *= 16;
        dy *= 16;
      } else if (event.deltaMode === 2) {
        dx *= el.clientWidth;
        dy *= el.clientHeight;
      }
      const delta = Math.abs(dy) >= Math.abs(dx) ? dy : dx;
      if (!delta) return;
      el.scrollLeft += delta;
      event.preventDefault();
    };

    const onMouseDown = (event: MouseEvent) => {
      if (event.button !== 0) return;
      const target = event.target as HTMLElement;
      if (target.closest("a, button, input, select, textarea, summary, label")) return;
      drag = {
        x: event.clientX,
        y: event.clientY,
        left: el.scrollLeft,
        top: el.scrollTop,
      };
      setDragging(true);
      event.preventDefault();
    };

    const onMouseMove = (event: MouseEvent) => {
      if (!drag) return;
      el.scrollLeft = drag.left - (event.clientX - drag.x);
      el.scrollTop = drag.top - (event.clientY - drag.y);
    };

    const endDrag = () => {
      drag = null;
      setDragging(false);
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    el.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", endDrag);
    return () => {
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", endDrag);
    };
  }, []);

  return (
    <div
      ref={ref}
      className={`pan-scroll min-w-0 max-w-full overflow-auto overscroll-x-contain ${
        dragging ? "cursor-grabbing select-none" : "cursor-grab"
      } ${className}`}
      style={{ touchAction: "pan-x pan-y" }}
    >
      {children}
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
