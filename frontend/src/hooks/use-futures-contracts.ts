/** Fetch active VN30F contracts (KRX format) and primary symbol from backend. */

import { useState, useEffect } from "react";
import { apiFetch } from "../utils/api-client";
import { toKrxSymbol, isVn30fDerivative } from "../utils/futures-format-utils";

interface FuturesContracts {
  contracts: string[];
  primary: string;
}

/** Compute approximate front-month KRX symbol as fallback before API responds. */
function fallbackPrimary(): string {
  const now = new Date();
  let year = now.getFullYear();
  let month = now.getMonth(); // 0-indexed

  // Third Thursday: first Thursday + 14 days
  const first = new Date(year, month, 1);
  const offset = (4 - first.getDay() + 7) % 7;
  const thirdThursday = new Date(year, month, 1 + offset + 14);

  if (now > thirdThursday) {
    month++;
    if (month > 11) {
      month = 0;
      year++;
    }
  }

  return toKrxSymbol(year, month + 1); // month+1 for 1-indexed
}

export { isVn30fDerivative };

export function useFuturesContracts() {
  const [contracts, setContracts] = useState<string[]>([]);
  const [primary, setPrimary] = useState(fallbackPrimary);

  useEffect(() => {
    apiFetch<FuturesContracts>("/market/futures-contracts")
      .then((res) => {
        setContracts(res.contracts);
        setPrimary(res.primary);
      })
      .catch(() => {
        // Keep fallback values
      });
  }, []);

  return { contracts, primary };
}
