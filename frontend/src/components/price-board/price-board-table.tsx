/** Sortable 30-stock price table with flash animation and sparklines. */

import { useState, useRef, useEffect } from "react";
import type { PriceBoardRow } from "../../hooks/use-price-board-data";
import { PriceBoardSparkline } from "./price-board-sparkline";
import { formatVolume, formatPercent } from "../../utils/format-number";

type SortKey = "symbol" | "change_pct" | "volume";
type SortDir = "asc" | "desc";

// Color logic: ceiling/floor=yellow, up=green, down=red, neutral=gray
function priceColorClass(row: PriceBoardRow): string {
  const { last_price, ceiling, floor, change } = row.price;
  if (ceiling > 0 && last_price >= ceiling) return "text-yellow-400";
  if (floor > 0 && last_price <= floor) return "text-yellow-400";
  if (change > 0) return "text-green-400";
  if (change < 0) return "text-red-400";
  return "text-gray-300";
}

function formatPrice(price: number): string {
  return price > 0 ? price.toFixed(2) : "-";
}

interface PriceBoardTableProps {
  rows: PriceBoardRow[];
}

export function PriceBoardTable({ rows }: PriceBoardTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("symbol");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const prevPricesRef = useRef<Record<string, number>>({});
  const [flashSymbols, setFlashSymbols] = useState<Set<string>>(new Set());

  // Detect price changes for flash animation
  useEffect(() => {
    const flashing = new Set<string>();
    for (const row of rows) {
      const prev = prevPricesRef.current[row.symbol];
      if (prev !== undefined && prev !== row.price.last_price) {
        flashing.add(row.symbol);
      }
      prevPricesRef.current[row.symbol] = row.price.last_price;
    }

    let timer: ReturnType<typeof setTimeout> | undefined;
    if (flashing.size > 0) {
      setFlashSymbols(flashing);
      timer = setTimeout(() => setFlashSymbols(new Set()), 400);
    }
    return () => { if (timer) clearTimeout(timer); };
  }, [rows]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "symbol" ? "asc" : "desc");
    }
  };

  const sorted = [...rows].sort((a, b) => {
    let aVal: number | string;
    let bVal: number | string;
    switch (sortKey) {
      case "symbol":
        aVal = a.symbol; bVal = b.symbol; break;
      case "change_pct":
        aVal = a.price.change_pct; bVal = b.price.change_pct; break;
      case "volume":
        aVal = a.stats?.total_volume ?? 0;
        bVal = b.stats?.total_volume ?? 0; break;
    }
    if (aVal < bVal) return sortDir === "asc" ? -1 : 1;
    if (aVal > bVal) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  const sortIcon = (key: SortKey) =>
    sortKey === key ? (sortDir === "asc" ? " ↑" : " ↓") : "";

  const buyPressurePct = (row: PriceBoardRow): number | null => {
    const total = row.stats?.total_volume ?? 0;
    if (total === 0) return null;
    return (row.stats!.mua_chu_dong_volume / total) * 100;
  };

  const thClass = "px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider";
  const thSortable = `${thClass} cursor-pointer hover:bg-gray-700 select-none`;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-x-auto">
      <table className="w-full text-sm min-w-[700px]">
        <thead className="bg-gray-800">
          <tr>
            <th onClick={() => handleSort("symbol")} className={thSortable}>
              Symbol{sortIcon("symbol")}
            </th>
            <th className={`${thClass} text-right`}>Price</th>
            <th className={`${thClass} text-right`}>Change</th>
            <th onClick={() => handleSort("change_pct")} className={`${thSortable} text-right`}>
              Change%{sortIcon("change_pct")}
            </th>
            <th onClick={() => handleSort("volume")} className={`${thSortable} text-right`}>
              Volume{sortIcon("volume")}
            </th>
            <th className={`${thClass} text-right`}>Buy Pressure</th>
            <th className={`${thClass} text-center`}>Trend</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const colorClass = priceColorClass(row);
            const isFlashing = flashSymbols.has(row.symbol);
            const flashBg = isFlashing
              ? row.price.change >= 0 ? "bg-green-900/30" : "bg-red-900/30"
              : "";
            const bp = buyPressurePct(row);

            return (
              <tr
                key={row.symbol}
                className={`border-t border-gray-800 hover:bg-gray-800/50 transition-colors duration-300 ${flashBg}`}
              >
                <td className="px-4 py-2 font-semibold text-white">{row.symbol}</td>
                <td className={`px-4 py-2 text-right font-mono ${colorClass}`}>
                  {formatPrice(row.price.last_price)}
                </td>
                <td className={`px-4 py-2 text-right font-mono ${colorClass}`}>
                  {row.price.change > 0 ? "+" : ""}{row.price.change.toFixed(2)}
                </td>
                <td className={`px-4 py-2 text-right font-mono ${colorClass}`}>
                  {formatPercent(row.price.change_pct)}
                </td>
                <td className="px-4 py-2 text-right text-gray-300">
                  {row.stats ? formatVolume(row.stats.total_volume) : "-"}
                </td>
                <td className="px-4 py-2 text-right">
                  {bp !== null
                    ? <span className={bp > 50 ? "text-green-400" : "text-red-400"}>
                        {bp.toFixed(1)}%
                      </span>
                    : <span className="text-gray-500">-</span>}
                </td>
                <td className="px-4 py-2 text-center">
                  <PriceBoardSparkline data={row.sparkline} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
