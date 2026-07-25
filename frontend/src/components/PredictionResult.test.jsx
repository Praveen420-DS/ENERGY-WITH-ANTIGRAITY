import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PredictionResult from "./PredictionResult";

const RESULT = {
    predicted_meter_reading: 174.33691959802735,
    unit_note: "Meter-specific unit",
    meter: 0,
    model_version: "v1.0.0",
    input_timestamp: "2016-07-15T14:00:00",
    prediction_timestamp: "2026-07-25T10:00:00Z",
    processing_time_ms: 12.345,
    request_id: "test-request",
    warnings: [],
};

describe("PredictionResult", () => {
    it("shows the empty state", () => {
        render(<PredictionResult result={null} loading={false} error={null} />);
        expect(screen.getByText("No prediction yet")).toBeInTheDocument();
    });

    it("shows the loading state", () => {
        render(<PredictionResult result={null} loading error={null} />);
        expect(screen.getByText("Running production inference")).toBeInTheDocument();
    });

    it("formats a successful production result", () => {
        render(<PredictionResult result={RESULT} loading={false} error={null} />);
        expect(screen.getByText("174.3369")).toBeInTheDocument();
        expect(screen.getByText("v1.0.0")).toBeInTheDocument();
        expect(screen.getByText("12.35 ms")).toBeInTheDocument();
    });

    it("renders model warnings without inventing confidence", () => {
        const result = { ...RESULT, warnings: ["Unknown category was preserved."] };
        render(<PredictionResult result={result} loading={false} error={null} />);
        expect(screen.getByText("Unknown category was preserved.")).toBeInTheDocument();
        expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
    });

    it("renders a safe error", () => {
        const error = { kind: "network", message: "Service unavailable." };
        render(<PredictionResult result={null} loading={false} error={error} />);
        expect(screen.getByRole("alert")).toHaveTextContent("Service unavailable.");
    });
});
