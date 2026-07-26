import axios from "axios";

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

export function setAuthToken(token) {
  if (token) {
    API.defaults.headers.common["authorization"] = `Bearer ${token}`;
  } else {
    delete API.defaults.headers.common["authorization"];
  }
}

export default API;
