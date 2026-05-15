import { useEffect, useMemo, useState } from "react";

import { formatNumber } from "../utils/format";

export type ColumnDef = {
  key: string;
  label?: string;
};

type DataTableProps = {
  rows: Record<string, unknown>[];
  columns?: ColumnDef[];
  defaultRows?: number;
  compact?: boolean;
  searchable?: boolean;
};

export function DataTable({ rows, columns, defaultRows = 10, compact = false, searchable = false }: DataTableProps) {
  const [rowLimit, setRowLimit] = useState(defaultRows);
  const [query, setQuery] = useState("");

  const tableColumns = useMemo<ColumnDef[]>(() => {
    if (columns?.length) return columns;
    return rows.length ? Object.keys(rows[0]).map((key) => ({ key })) : [];
  }, [columns, rows]);

  const filteredRows = useMemo(() => {
    if (!query.trim()) return rows;
    const normalized = query.trim().toLowerCase();
    return rows.filter((row) =>
      tableColumns.some((column) => String(row[column.key] ?? "").toLowerCase().includes(normalized)),
    );
  }, [query, rows, tableColumns]);

  useEffect(() => {
    setRowLimit(defaultRows);
  }, [defaultRows, rows]);

  if (!rows.length) {
    return <p className="empty-copy">No rows available yet.</p>;
  }

  return (
    <div className={`table-shell ${compact ? "compact" : ""}`}>
      <div className="table-toolbar">
        <span>{formatNumber(filteredRows.length, 0)} rows</span>
        {searchable ? (
          <input
            aria-label="Search table"
            className="table-search"
            value={query}
            placeholder="Search"
            onChange={(event) => setQuery(event.target.value)}
          />
        ) : null}
        <label>
          Show
          <select value={rowLimit} onChange={(event) => setRowLimit(Number(event.target.value))}>
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
            <option value={filteredRows.length}>All</option>
          </select>
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {tableColumns.map((column) => (
                <th key={column.key}>{column.label ?? column.key}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredRows.slice(0, rowLimit).map((row, index) => (
              <tr key={`${String(row["Job Family"] ?? "row")}-${index}`}>
                {tableColumns.map((column) => (
                  <td key={column.key}>{String(row[column.key] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filteredRows.length > rowLimit ? (
        <p className="table-note">
          Showing {rowLimit} of {filteredRows.length} rows. Use the export for full offline analysis.
        </p>
      ) : null}
    </div>
  );
}
