import axios from "axios";

const API = axios.create({
    baseURL: "http://127.0.0.1:8000/api",
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


// ===============================
// LOGOUT
// ===============================
export const logoutUser = () => {
    localStorage.removeItem("access_token");
};


// Export Axios instance
export default API;