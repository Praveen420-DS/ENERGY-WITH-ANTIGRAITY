import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PredictionResult from "./components/PredictionResult";
import API, { logoutUser } from "./services/api";

describe("frontend security boundaries", () => {
    it("removes a stale token after an API 401", async () => {
        localStorage.setItem("access_token", "test-only-token");
        const rejected = API.interceptors.response.handlers[0].rejected;
        await expect(rejected({ response: { status: 401 } })).rejects.toEqual({
            response: { status: 401 },
        });
        expect(localStorage.getItem("access_token")).toBeNull();
    });

    it("logout removes authentication state", () => {
        localStorage.setItem("access_token", "test-only-token");
        logoutUser();
        expect(localStorage.getItem("access_token")).toBeNull();
    });

    it("renders hostile API error content as text", () => {
        const message = "<img src=x onerror=alert(1)>";
        const { container } = render(
            <PredictionResult
                result={null}
                loading={false}
                error={{ kind: "validation", message }}
            />,
        );
        expect(screen.getByText(message)).toBeInTheDocument();
        expect(container.querySelector("img")).toBeNull();
    });

    it("does not expose engineered targets or confidence", () => {
        render(
            <PredictionResult
                result={null}
                loading={false}
                error={null}
            />,
        );
        expect(screen.queryByText(/meter_reading/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
    });

    it("does not log tokens through the API interceptors", async () => {
        const consoleSpy = vi.spyOn(console, "log").mockImplementation(() => {});
        localStorage.setItem("access_token", "test-only-token");
        const fulfilled = API.interceptors.response.handlers[0].fulfilled;
        await fulfilled({ status: 200 });
        expect(consoleSpy).not.toHaveBeenCalled();
        consoleSpy.mockRestore();
    });

    it("does not expose backend secret environment names", () => {
        for (const secretName of [
            "JWT_SECRET_KEY",
            "SECRET_KEY",
            "DATABASE_URL",
            "POSTGRES_PASSWORD",
            "REDIS_PASSWORD",
        ]) {
            expect(import.meta.env[secretName]).toBeUndefined();
        }
    });
});
