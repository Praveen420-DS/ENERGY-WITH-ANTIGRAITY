import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import AnomaliesPage from "./AnomaliesPage";
import PeakPredictionPage from "./PeakPredictionPage";
import { detectAnomalies, getAnomalies, predictPeak } from "../services/api";

vi.mock("../services/api", () => ({ getAnomalies: vi.fn(), detectAnomalies: vi.fn(), predictPeak: vi.fn() }));

beforeEach(() => vi.clearAllMocks());

it("loads and reruns historical anomaly detection", async () => {
    getAnomalies.mockResolvedValue([]);
    detectAnomalies.mockResolvedValue({ detected_count: 0 });
    render(<AnomaliesPage />);
    await screen.findByText("No anomaly records");
    fireEvent.click(screen.getByRole("button", { name: "Run detection" }));
    await waitFor(() => expect(detectAnomalies).toHaveBeenCalled());
});

it("submits a meter and shows the peak outlook", async () => {
    predictPeak.mockResolvedValue({ is_peak_likely: true, forecast_kwh: 12.5, peak_threshold_kwh: 10, history_records: 8 });
    render(<PeakPredictionPage />);
    fireEvent.change(screen.getByLabelText("Meter ID"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate outlook" }));
    expect(await screen.findByText("Peak demand likely")).toBeTruthy();
    expect(predictPeak).toHaveBeenCalledWith({ meter_id: 3 });
});
