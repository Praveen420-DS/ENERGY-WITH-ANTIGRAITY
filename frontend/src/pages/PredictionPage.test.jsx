import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PredictionPage from "./PredictionPage";
import { predictEnergy } from "../services/api";

vi.mock("../services/api", () => ({
    predictEnergy: vi.fn(),
}));

describe("PredictionPage", () => {
    beforeEach(() => {
        predictEnergy.mockReset();
    });

    it("loads the business sample and resets it", async () => {
        const user = userEvent.setup();
        render(<PredictionPage />);
        await user.click(screen.getByRole("button", { name: "Use sample" }));
        expect(screen.getByLabelText(/Building/)).toHaveValue("0");
        expect(screen.getByLabelText(/Meter/)).toHaveValue("0");
        expect(screen.getByLabelText(/Current meter reading/)).toHaveValue(174.3);
        await user.click(screen.getByRole("button", { name: "Reset" }));
        expect(screen.getByLabelText(/Building/)).toHaveValue("");
    });

    it("converts raw numeric form fields and displays the API result", async () => {
        const user = userEvent.setup();
        predictEnergy.mockResolvedValue({
            predicted_meter_reading: 174.33691959802735,
            unit_note: "Meter-specific unit",
            meter: 0,
            model_version: "v1.0.0",
            input_timestamp: "2016-07-15T14:00:00",
            prediction_timestamp: "2026-07-25T10:00:00Z",
            processing_time_ms: 10,
            request_id: "page-test",
            warnings: [],
        });
        render(<PredictionPage />);
        await user.click(screen.getByRole("button", { name: "Use sample" }));
        await user.click(screen.getByRole("button", { name: "Generate forecast" }));

        await waitFor(() => expect(predictEnergy).toHaveBeenCalledOnce());
        const payload = predictEnergy.mock.calls[0][0];
        expect(payload.square_feet).toBe(7432);
        expect(payload.actual_kwh).toBe(174.3);
        expect(payload.timestamp).toBe("2016-07-15T14:00");
        expect(payload).not.toHaveProperty("forecastPeriod");
        expect(payload).not.toHaveProperty("hour");
        expect(screen.getByText("174.3369")).toBeInTheDocument();
    });

    it("maps API validation details to the matching raw field", async () => {
        const user = userEvent.setup();
        predictEnergy.mockRejectedValue({
            kind: "validation",
            message: "Input validation failed.",
            details: [{ field: "meter", message: "Meter must be between 0 and 3." }],
        });
        render(<PredictionPage />);
        await user.click(screen.getByRole("button", { name: "Use sample" }));
        await user.click(screen.getByRole("button", { name: "Generate forecast" }));

        expect(await screen.findByText("Meter must be between 0 and 3."))
            .toBeInTheDocument();
        expect(screen.getByRole("alert")).toHaveTextContent("Input validation failed.");
    });
});
