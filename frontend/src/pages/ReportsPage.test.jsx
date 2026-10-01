import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ReportsPage from "./ReportsPage";

const predictions = [
    {
        id: 1,
        meter_id: 1,
        actual_kwh: 174.3,
        predicted_kwh: 180.2,
        confidence: 0.9,
        predicted_at: "2026-09-29T10:00:00Z",
        target_start: "2026-09-29T11:00:00Z",
        horizon: "hourly",
    },
    {
        id: 2,
        meter_id: 1,
        actual_kwh: null,
        predicted_kwh: 160.5,
        confidence: 0.8,
        predicted_at: "2026-09-28T10:00:00Z",
        target_start: "2026-09-28T11:00:00Z",
        horizon: "hourly",
    },
];

describe("ReportsPage", () => {
    it("separates actual readings from forecast values and handles legacy nulls", () => {
        render(<ReportsPage predictions={predictions} />);

        const totalCard = screen.getByText("Total forecast").closest("article");
        expect(within(totalCard).getByRole("heading")).toHaveTextContent("340.7 kWh");
        expect(screen.queryByText("Total consumption")).not.toBeInTheDocument();
        const averageCard = screen.getByText("Average forecast").closest("article");
        expect(within(averageCard).getByRole("heading")).toHaveTextContent("170.4 kWh");
        expect(screen.getByText("Forecast trend")).toBeInTheDocument();
        const table = screen.getByRole("table");
        expect(within(table).getByRole("columnheader", { name: "Actual reading" })).toBeInTheDocument();
        expect(within(table).getByRole("columnheader", { name: "Predicted energy" })).toBeInTheDocument();
        expect(within(table).getByText("174.3 kWh")).toBeInTheDocument();
        expect(within(table).getByText("180.2 kWh")).toBeInTheDocument();
        expect(within(table).getByText("—")).toBeInTheDocument();
    });
});
