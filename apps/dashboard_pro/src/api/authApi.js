import { request } from "./client";

export const authApi = {
  signUp: (payload) => request("/api/auth/signup", { method: "POST", body: JSON.stringify(payload) }),
  signIn: (payload) => request("/api/auth/signin", { method: "POST", body: JSON.stringify(payload) }),
};
