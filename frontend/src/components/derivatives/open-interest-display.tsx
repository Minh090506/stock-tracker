/** Displays open interest from the derivatives history endpoint.
 * Note: OI is currently 0 (not yet provided by SSI stream).
 */

import { usePolling } from "../../hooks/use-polling";
import { apiFetch } from "../../utils/api-client";
import { formatVolume } from "../../utils/format-number";
import type { DerivativesHistory } from "../../types";

interface OpenInterestDisplayProps {
  contract: string | null;
}

export function OpenInterestDisplay({ contract }: OpenInterestDisplayProps) {
  // Fetch latest derivatives history to get OI
  const today = new Date().toISOString().split("T")[0];
  const { data } = usePolling(
    () => {
      if (!contract) return Promise.resolve([]);
      return apiFetch<DerivativesHistory[]>(
        `/history/derivatives/${contract}?start=${today}&end=${today}`,
      );
    },
    60_000, // poll every 60s — OI changes infrequently
  );

  const latestOI = data && data.length > 0 ? data[data.length - 1]!.open_interest : null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Open Interest
      </h3>

      {contract === null ? (
        <div className="text-gray-500 text-sm">No contract selected</div>
      ) : latestOI === null || latestOI === 0 ? (
        <div>
          <div className="text-lg font-semibold text-gray-500">N/A</div>
          <div className="text-xs text-gray-600 mt-1">
            Not yet available from data source
          </div>
        </div>
      ) : (
        <div>
          <div className="text-2xl font-semibold text-white">
            {formatVolume(latestOI)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {contract} contracts
          </div>
        </div>
      )}
    </div>
  );
}
