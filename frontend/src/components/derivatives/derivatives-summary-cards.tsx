/** Four KPI cards: contract, price+change, basis value/pct, premium/discount badge. */

import { formatVolume, formatPercent } from "../../utils/format-number";
import type { DerivativesData } from "../../types";

interface DerivativesSummaryCardsProps {
  data: DerivativesData | null;
}

export function DerivativesSummaryCards({ data }: DerivativesSummaryCardsProps) {
  if (!data) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-gray-500 text-sm">
        Waiting for derivatives data...
      </div>
    );
  }

  // VN market: red=up/premium, green=down/discount
  const changeColor =
    data.change > 0 ? "text-red-400" : data.change < 0 ? "text-green-400" : "text-gray-400";

  const basisColor = data.is_premium ? "text-red-400" : "text-green-400";

  const badgeBg = data.is_premium
    ? "bg-red-900/40 text-red-400 border-red-800"
    : "bg-green-900/40 text-green-400 border-green-800";

  const changeSign = data.change > 0 ? "+" : "";

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Contract Symbol */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Contract</div>
        <div className="text-2xl font-semibold text-white">{data.symbol}</div>
        <div className="text-xs text-gray-500 mt-1">
          Vol: {formatVolume(data.volume)}
        </div>
      </div>

      {/* Price + Change */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Last Price</div>
        <div className={`text-2xl font-semibold ${changeColor}`}>
          {data.last_price.toFixed(1)}
        </div>
        <div className={`text-xs mt-1 ${changeColor}`}>
          {changeSign}{data.change.toFixed(1)} ({formatPercent(data.change_pct)})
        </div>
      </div>

      {/* Basis Value + Pct */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Basis</div>
        <div className={`text-2xl font-semibold ${basisColor}`}>
          {data.basis > 0 ? "+" : ""}{data.basis.toFixed(2)}
        </div>
        <div className={`text-xs mt-1 ${basisColor}`}>
          {formatPercent(data.basis_pct)}
        </div>
      </div>

      {/* Premium/Discount Badge */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-400 mb-1">Status</div>
        <div className="mt-1">
          <span className={`inline-block px-3 py-1.5 rounded-md border text-sm font-medium ${badgeBg}`}>
            {data.is_premium ? "Premium" : "Discount"}
          </span>
        </div>
        <div className="text-xs text-gray-500 mt-2">
          Bid: {data.bid_price.toFixed(1)} / Ask: {data.ask_price.toFixed(1)}
        </div>
      </div>
    </div>
  );
}
