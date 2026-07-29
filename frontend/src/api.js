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

// Fetch a short-lived SIGNED URL for a document (kind = "job" | "candidate"), then return the
// absolute URL usable as an iframe src / window.open target. Auth (Bearer) + tenant check happen
// on the /url call; the returned URL carries a signed, expiring token.
export async function signedDocUrl(kind, id) {
  const { data } = await API.get(`/api/documents/${kind}/${id}/url`);
  return (API.defaults.baseURL || "") + data.url;
}

export default API;
