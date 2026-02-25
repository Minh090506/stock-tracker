/** KRX derivative symbol format utilities.
 *
 * KRX format (post May 5, 2025): 41I1{Y}{M}000
 *   4=derivative, 1=futures, I1=VN30, {year}{month}, 000=identifier
 *
 * Year encoding: 0-9=2010-2019, A=2020..F=2025, G=2026, H=2027, J=2028..W=2039
 *   (skipping I, O, U to avoid confusion with 1, 0)
 * Month encoding: 1-9=Jan-Sep, A=Oct, B=Nov, C=Dec
 */

const YEAR_LETTERS = "0123456789ABCDEFGHJKLMNPQRSTVW";
const YEAR_BASE = 2010;
const MONTH_CODES = "0123456789ABC"; // index 1-12 maps to '1'..'C' (index 0 unused)

/** Check if a symbol is a VN30 derivative in ANY format (KRX or legacy). */
export function isVn30fDerivative(symbol: string): boolean {
  return symbol.startsWith("VN30F") || symbol.startsWith("41I1");
}

/** Convert (year, month) to KRX code: 41I1{Y}{M}000. Month is 1-indexed. */
export function toKrxSymbol(year: number, month: number): string {
  const yearIdx = year - YEAR_BASE;
  if (yearIdx < 0 || yearIdx >= YEAR_LETTERS.length) return "";
  return `41I1${YEAR_LETTERS[yearIdx]}${MONTH_CODES[month]}000`;
}

/** Parse KRX symbol → human-readable label like "VN30F T03/2026". */
export function formatKrxLabel(symbol: string): string {
  if (!symbol.startsWith("41I1") || symbol.length !== 9) return symbol;
  const yearCh = symbol.charAt(4);
  const monthCh = symbol.charAt(5);
  const yearIdx = YEAR_LETTERS.indexOf(yearCh);
  const monthIdx = MONTH_CODES.indexOf(monthCh);
  if (yearIdx < 0 || monthIdx < 1) return symbol;
  const year = YEAR_BASE + yearIdx;
  const mm = String(monthIdx).padStart(2, "0");
  return `VN30F T${mm}/${year}`;
}
