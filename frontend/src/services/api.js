import axios from "axios";

const API = axios.create({
    baseURL: import.meta.env.VITE_API_URL || "/api",
    headers: {
        "Content-Type": "application/json",
    },
});

// Automatically attach JWT token
API.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem("access_token");

        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

API.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem("access_token");
        }
        return Promise.reject(error);
    },
);


// ===============================
// LOGIN
// ===============================
export const loginUser = async (email, password) => {
    const formData = new URLSearchParams();

    formData.append("grant_type", "password");
    formData.append("username", email);
    formData.append("password", password);
    formData.append("scope", "");
    formData.append("client_id", "");
    formData.append("client_secret", "");

    const response = await API.post(
        "/auth/login",
        formData,
        {
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
            },
        }
    );

    return response.data;
};


// ===============================
// GET AUTHENTICATED USERS
// ===============================
export const getUsers = async () => {
    const response = await API.get("/users/");

    return response.data;
};

export class PredictionApiError extends Error {
    constructor(message, kind, details = []) {
        super(message);
        this.name = "PredictionApiError";
        this.kind = kind;
        this.details = details;
    }
}

export const predictEnergy = async (payload) => {
    try {
        const response = await API.post("/predictions/", payload);
        return response.data;
    } catch (error) {
        if (!error.response) {
            throw new PredictionApiError(
                "The prediction service could not be reached.",
                "network",
            );
        }
        const status = error.response.status;
        const body = error.response.data?.error;
        if (status === 401) {
            throw new PredictionApiError(
                "Your session has expired. Please sign in again.",
                "unauthorized",
            );
        }
        if (status === 422 || status === 400) {
            throw new PredictionApiError(
                body?.message || "Please correct the highlighted fields.",
                "validation",
                body?.details || [],
            );
        }
        if (status === 503) {
            throw new PredictionApiError(
                "The production model is temporarily unavailable.",
                "unavailable",
            );
        }
        throw new PredictionApiError(
            "The prediction could not be completed. Please try again.",
            "unexpected",
        );
    }
};


// ===============================
// LOGOUT
// ===============================
export const logoutUser = () => {
    localStorage.removeItem("access_token");
};


// Export Axios instance
export default API;
