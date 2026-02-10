/** Static sector mapping for VN30 component stocks. */

export const VN30_SECTORS: Record<string, string> = {
  // Banking
  ACB: "Banking",
  BID: "Banking",
  CTG: "Banking",
  HDB: "Banking",
  MBB: "Banking",
  SSB: "Banking",
  STB: "Banking",
  TCB: "Banking",
  TPB: "Banking",
  VCB: "Banking",
  VPB: "Banking",
  // Real Estate
  VHM: "Real Estate",
  VRE: "Real Estate",
  NVL: "Real Estate",
  PDR: "Real Estate",
  KDH: "Real Estate",
  // Oil & Gas
  GAS: "Oil & Gas",
  PLX: "Oil & Gas",
  // Consumer
  VNM: "Consumer",
  SAB: "Consumer",
  MSN: "Consumer",
  // Technology
  FPT: "Technology",
  // Steel
  HPG: "Steel",
  // Securities
  SSI: "Securities",
  // Insurance
  BVH: "Insurance",
  // Power
  POW: "Power",
  GEX: "Power",
  // Retail
  MWG: "Retail",
  // Aviation
  VJC: "Aviation",
  // Rubber
  GVR: "Rubber",
  // Conglomerates
  VIC: "Conglomerates",
};

/** Get sector for a symbol, defaulting to "Other". */
export function getSector(symbol: string): string {
  return VN30_SECTORS[symbol] ?? "Other";
}
