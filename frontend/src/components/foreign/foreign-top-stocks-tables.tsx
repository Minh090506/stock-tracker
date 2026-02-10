/** Side-by-side tables showing top 10 foreign net buy and top 10 net sell stocks. */

import { formatVnd, formatVolume } from "../../utils/format-number";
import type { ForeignInvestorData } from "../../types";

interface ForeignTopStocksTablesProps {
  stocks: ForeignInvestorData[];
}

function TopTable({
  title,
  items,
  isBuy,
}: {
  title: string;
  items: ForeignInvestorData[];
  isBuy: boolean;
}) {
  const valueColor = isBuy ? "text-red-400" : "text-green-400";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
      </div>
      <table className="min-w-full divide-y divide-gray-800">
        <thead className="bg-gray-950">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase">
              Symbol
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium text-gray-400 uppercase">
              Net Vol
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium text-gray-400 uppercase">
              Net Value
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {items.map((s, idx) => (
            <tr
              key={s.symbol}
              className={idx % 2 === 0 ? "bg-gray-900" : "bg-gray-950"}
            >
              <td className="px-3 py-2 text-sm font-medium text-white">
                {s.symbol}
              </td>
              <td className={`px-3 py-2 text-sm text-right ${valueColor}`}>
                {formatVolume(s.net_volume)}
              </td>
              <td className={`px-3 py-2 text-sm text-right font-medium ${valueColor}`}>
                {formatVnd(s.net_value)}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={3} className="px-3 py-4 text-center text-gray-500 text-sm">
                No data
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function ForeignTopStocksTables({ stocks }: ForeignTopStocksTablesProps) {
  const sorted = [...stocks].sort((a, b) => b.net_value - a.net_value);
  const topBuy = sorted.filter((s) => s.net_value > 0).slice(0, 10);
  const topSell = sorted.filter((s) => s.net_value < 0).slice(0, 10);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <TopTable title="Top 10 Foreign Net Buy" items={topBuy} isBuy />
      <TopTable title="Top 10 Foreign Net Sell" items={topSell} isBuy={false} />
    </div>
  );
}
