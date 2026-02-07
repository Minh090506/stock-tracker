/** Sortable table showing detailed foreign investor flow for all VN30 stocks. */

import { useState } from "react";
import { formatVolume, formatVnd } from "../../utils/format-number";
import type { ForeignInvestorData } from "../../types";

interface ForeignFlowDetailTableProps {
  stocks: ForeignInvestorData[];
}

type SortKey = keyof ForeignInvestorData;
type SortDir = "asc" | "desc";

export function ForeignFlowDetailTable({
  stocks,
}: ForeignFlowDetailTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("net_value");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sortedStocks = [...stocks].sort((a, b) => {
    const aVal = a[sortKey];
    const bVal = b[sortKey];
    const multiplier = sortDir === "asc" ? 1 : -1;

    if (typeof aVal === "number" && typeof bVal === "number") {
      return (aVal - bVal) * multiplier;
    }
    if (typeof aVal === "string" && typeof bVal === "string") {
      return aVal.localeCompare(bVal) * multiplier;
    }
    return 0;
  });

  const SortableHeader = ({ column, label }: { column: SortKey; label: string }) => (
    <th
      onClick={() => handleSort(column)}
      className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-gray-300 select-none"
    >
      {label}
      {sortKey === column && (
        <span className="ml-1">{sortDir === "asc" ? "↑" : "↓"}</span>
      )}
    </th>
  );

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-800">
          <thead className="bg-gray-950">
            <tr>
              <SortableHeader column="symbol" label="Symbol" />
              <SortableHeader column="buy_volume" label="Buy Vol" />
              <SortableHeader column="sell_volume" label="Sell Vol" />
              <SortableHeader column="net_volume" label="Net Vol" />
              <SortableHeader column="net_value" label="Net Value" />
              <SortableHeader column="buy_speed_per_min" label="Buy Speed" />
              <SortableHeader column="sell_speed_per_min" label="Sell Speed" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {sortedStocks.map((stock, idx) => {
              const netVolumeColor =
                stock.net_volume > 0
                  ? "text-red-400"
                  : stock.net_volume < 0
                    ? "text-green-400"
                    : "text-gray-400";
              const netValueColor =
                stock.net_value > 0
                  ? "text-red-400"
                  : stock.net_value < 0
                    ? "text-green-400"
                    : "text-gray-400";

              return (
                <tr
                  key={stock.symbol}
                  className={idx % 2 === 0 ? "bg-gray-900" : "bg-gray-950"}
                >
                  <td className="px-4 py-3 text-sm font-medium text-white">
                    {stock.symbol}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {formatVolume(stock.buy_volume)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {formatVolume(stock.sell_volume)}
                  </td>
                  <td className={`px-4 py-3 text-sm font-medium ${netVolumeColor}`}>
                    {formatVolume(stock.net_volume)}
                  </td>
                  <td className={`px-4 py-3 text-sm font-medium ${netValueColor}`}>
                    {formatVnd(stock.net_value)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {stock.buy_speed_per_min.toFixed(1)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {stock.sell_speed_per_min.toFixed(1)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
