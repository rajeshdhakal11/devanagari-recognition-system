import axios from 'axios';
import { hashPassword } from './security';

// Base API URL
const API_BASE_URL = "http://localhost:5000/api";

// Axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
});

// Function to get auth token from localStorage
const getAuthHeaders = () => {
  const token = localStorage.getItem("token");
  console.log("Using Token in API Requests:", token); // Debugging
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// Authentication APIs
export const signup = async (data) => {
  try {
    const response = await api.post("/signup", data);
    return response;
  } catch (error) {
    console.error("Signup Error:", error.response?.data || error.message);
    throw error;
  }
};

export const requestSignupOtp = async ({ phone_number }) => {
  try {
    const response = await api.post("/signup/request-otp", { phone_number });
    return response.data;
  } catch (error) {
    console.error("Signup OTP request error:", error.response?.data || error.message);
    throw error;
  }
};

export const verifySignupOtp = async ({ phone_number, otp }) => {
  try {
    const response = await api.post("/signup/verify-otp", { phone_number, otp });
    return response.data;
  } catch (error) {
    console.error("Signup OTP verify error:", error.response?.data || error.message);
    throw error;
  }
};

export const signin = async (data) => {
  try {
    const identifier = data?.identifier ?? data?.email ?? data?.username ?? '';
    const payload = {
      ...data,
      identifier,
      password: await hashPassword(data?.password ?? ""),
    };

    const response = await api.post("/signin", payload);
    
    // Extract the token from the correct response structure
    if (response.data.data && response.data.data.token) {
      console.log("Received Token:", response.data.data.token);  // Debugging
      localStorage.setItem("token", response.data.data.token);  // Store token
      localStorage.setItem("user_role", response.data.data.user?.role || "user");
    } else {
      console.error("No token received!");
    }

    // Return user data and token for further use if needed
    return {
      token: response.data.data.token,
      user: response.data.data.user
    };

  } catch (error) {
    console.error("Login Error:", error.response?.data || error.message);
    throw error;
  }
};

export const faceSignin = async ({ identifier, image }) => {
  try {
    const response = await api.post('/face/signin', { identifier, image });

    if (response.data?.data?.token) {
      localStorage.setItem('token', response.data.data.token);
      localStorage.setItem('user_role', response.data.data.user?.role || 'user');
    }

    return {
      token: response.data?.data?.token,
      user: response.data?.data?.user,
      face_similarity: response.data?.data?.face_similarity,
    };
  } catch (error) {
    console.error('Face login error:', error.response?.data || error.message);
    throw error;
  }
};

export const setupFaceLogin = async ({ identifier, password, image }) => {
  try {
    const payload = {
      identifier,
      password: await hashPassword(password ?? ''),
      image,
    };
    const response = await api.post('/face/setup', payload);
    return response.data;
  } catch (error) {
    console.error('Face setup error:', error.response?.data || error.message);
    throw error;
  }
};

// Profile APIs
export const getProfile = () => api.get("/user/profile", { headers: getAuthHeaders() });
export const updateProfile = (data) =>
  api.put("/user/profile", data, { headers: getAuthHeaders() });
export const changePassword = (data) =>
  api.post("/user/change-password", data, { headers: getAuthHeaders() });

// Prediction APIs
export const predictImage = (formData) =>
  api.post("/predict", formData, {
    headers: { ...getAuthHeaders(), "Content-Type": "multipart/form-data" },
  });
export const getAudio = (predictionId) =>
  api.get(`/generate-audio/${predictionId}`, { headers: getAuthHeaders() });

// History API
export const getHistory = () => api.get("/history", { headers: getAuthHeaders() });

// Admin APIs
export const listAdminUsers = () => api.get("/admin/users", { headers: getAuthHeaders() });
export const updateUserRole = (userId, role) =>
  api.put(`/admin/users/${userId}/role`, { role }, { headers: getAuthHeaders() });
export const bootstrapAdmin = (identifier, bootstrap_key) =>
  api.post("/admin/bootstrap", { identifier, bootstrap_key });
export const getAdminPredictionQualityAnalytics = (params = {}) =>
  api.get("/admin/analytics/prediction-quality", { headers: getAuthHeaders(), params });

// Logout Function
export const logout = () => {
  localStorage.removeItem("token");  // Remove token from localStorage
  localStorage.removeItem("user_role");
};

export const getUsernameSuggestions = async ({ first_name, last_name }) => {
  try {
    const response = await api.get("/username-suggestions", {
      params: {
        first_name,
        last_name,
      },
    });
    return response.data?.data?.suggestions || [];
  } catch (error) {
    console.error("Username suggestion error:", error.response?.data || error.message);
    throw error;
  }
};
