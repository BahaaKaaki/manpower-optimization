export function toNumber(value: unknown) {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatCurrency(value: unknown) {
  return `SAR ${toNumber(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function formatCompactCurrency(value: unknown) {
  return `SAR ${toNumber(value).toLocaleString(undefined, {
    notation: "compact",
    maximumFractionDigits: 1,
  })}`;
}

export function formatNumber(value: unknown, maximumFractionDigits = 1) {
  return toNumber(value).toLocaleString(undefined, { maximumFractionDigits });
}

export function formatPercent(value: unknown, fractionDigits = 1) {
  return `${toNumber(value).toFixed(fractionDigits)}%`;
}

export function getString(row: Record<string, unknown>, key: string) {
  return String(row[key] ?? "");
}

export function getRowNumber(row: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    if (key in row) return toNumber(row[key]);
  }
  return 0;
}

export function safeSavingsPercent(currentPayroll: number, optimizedPayroll: number) {
  if (!currentPayroll) return 0;
  return ((currentPayroll - optimizedPayroll) / currentPayroll) * 100;
}
