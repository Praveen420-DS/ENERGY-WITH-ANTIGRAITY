import EmptyState from "./EmptyState";

export default function DataTable({ columns, rows, emptyTitle = "No records yet", emptyDescription = "New records will appear here." }) {
    if (!rows?.length) return <EmptyState title={emptyTitle} description={emptyDescription} />;
    return (
        <div className="table-wrap">
            <table>
                <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead>
                <tbody>{rows.map((row, index) => <tr key={row.id ?? index}>{columns.map((column) => <td key={column.key} data-label={column.label}>{column.render ? column.render(row) : row[column.key]}</td>)}</tr>)}</tbody>
            </table>
        </div>
    );
}
