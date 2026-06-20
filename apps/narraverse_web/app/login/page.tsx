"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import loginimage from "@/public/login.jpeg";
import { login, googleLogin } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const router = useRouter();

  const handleLogin = async () => {
    try {
      await login(email, password);

      router.push("/");
    } catch (error) {
      if (error instanceof Error) alert(error.message);
      else alert("Something went wrong");
    }
  };

  const handleGoogleLogin = async () => {
    try {
      await googleLogin();

      router.push("/");
    } catch (error) {
      if (error instanceof Error) alert(error.message);
      else alert("Something went wrong");
    }
  };

  return (
    <div
      className="relative min-h-screen w-full flex items-center justify-end pr-[8vw] overflow-hidden pb-8"
      style={{ fontFamily: "sans-serif" }}
    >
      <div>
        <Image
          src={loginimage}
          alt="audiobook"
          fill
          priority
          className="object-cover"
        />
      </div>

      <div
        className="relative z-10 w-[490px] mt-24 flex flex-col items-center rounded-2xl px-10 py-1"
        style={{
          background: "rgba(30, 18, 55, 0.82)",
          backdropFilter: "blur(18px)",
          border: "1.5px solid rgba(255, 255, 255, 0.25)",
          boxShadow:
            "0 0 60px rgba(255,255,255,0.08), inset 0 0 40px rgba(255,255,255,0.03)",
        }}
      >
        <img
          src="/logo.png"
          alt="Logo"
          className="w-20 h-23 object-contain mb-1"
        />

        <h1
          className="text-5xl font-bold text-white text-center mb-2"
          style={{ fontFamily: "'Cormorant Garamond', serif" }}
        >
          Welcome Back!
        </h1>
        <p
          className="text-sm text-center mb-7"
          style={{ color: "rgba(217, 217, 217, 0.9)" }}
        >
          Sign in to continue your creative journey.
        </p>

        <label
          className="self-start text-xs font-medium mb-2"
          style={{ color: "rgba(255,255,255,0.9)" }}
        >
          Email
        </label>
        <div className="relative w-full mb-4">
          <input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-xl px-4 py-3 pr-11 text-sm outline-none placeholder-white/40"
            style={{
              background: "rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "rgba(255,255,255,0.9)",
            }}
          />
          <span
            className="absolute right-3.5 top-1/2 -translate-y-1/2"
            style={{ color: "rgba(255,255,255,0.5)" }}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
            >
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <path d="M2 8l10 6 10-6" />
            </svg>
          </span>
        </div>

        <label
          className="self-start text-xs font-medium mb-2"
          style={{ color: "rgba(255,255,255,0.9)" }}
        >
          Password
        </label>
        <div className="relative w-full">
          <input
            type={showPass ? "text" : "password"}
            placeholder="Enter your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl px-4 py-3 pr-11 text-sm outline-none placeholder-white/40"
            style={{
              background: "rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "rgba(255,255,255,0.9)",
            }}
          />
          <span
            className="absolute right-3.5 top-1/2 -translate-y-1/2 cursor-pointer"
            style={{ color: "rgba(255,255,255,0.5)" }}
            onClick={() => setShowPass(!showPass)}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
            >
              {showPass ? (
                <>
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </>
              ) : (
                <>
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </>
              )}
            </svg>
          </span>
        </div>

        <div className="w-full flex items-center justify-between mt-3.5">
          <label
            className="flex items-center gap-2 cursor-pointer text-sm"
            style={{ color: "rgba(255,255,255,0.6)" }}
          >
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="w-4 h-4 accent-white"
            />
            Remember me
          </label>
          <a
            href="#"
            className="text-sm transition-colors duration-200"
            style={{ color: "#B46850" }}
            onMouseOver={(e) => (e.currentTarget.style.color = "#ffd08a")}
            onMouseOut={(e) => (e.currentTarget.style.color = "#B46850")}
          >
            Forgot Password?
          </a>
        </div>

        <button
          onClick={handleLogin}
          className="w-full cursor-pointer mt-5 py-3.5 rounded-full text-white font text-base tracking-wide transition-opacity duration-200 hover:opacity-90 active:scale-[0.98]"
          style={{
            background: "linear-gradient(90deg, #e0557a 0%, #c87a30 100%)",
          }}
        >
          Login
        </button>

        <div className="w-full flex items-center gap-3 my-5">
          <span
            className="flex-1 h-px"
            style={{ background: "rgba(255,255,255,0.15)" }}
          />
          <span className="text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>
            Or
          </span>
          <span
            className="flex-1 h-px"
            style={{ background: "rgba(255,255,255,0.15)" }}
          />
        </div>

        <button
          onClick={handleGoogleLogin}
          className="w-full cursor-pointer flex items-center justify-center gap-3 py-3.5 rounded-full text-sm font-medium transition-all duration-200"
          style={{
            background: "rgba(255,255,255,0.08)",
            border: "1px solid rgba(255,255,255,0.12)",
            color: "rgba(255,255,255,0.9)",
          }}
          onMouseOver={(e) =>
            (e.currentTarget.style.background = "rgba(255,255,255,0.13)")
          }
          onMouseOut={(e) =>
            (e.currentTarget.style.background = "rgba(255,255,255,0.08)")
          }
        >
          <svg width="20" height="20" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          Sign In with Google
        </button>

        <p
          className="mt-6 text-sm"
          style={{ color: "rgba(217, 217, 217, 0.9)" }}
        >
          Don&apos;t have an account?{" "}
          <Link
            href="/signup"
            className="font underline transition-colors duration-200"
            style={{ color: "#B46850" }}
            onMouseOver={(e) => (e.currentTarget.style.color = "#ffd08a")}
            onMouseOut={(e) => (e.currentTarget.style.color = "#B46850")}
          >
            Sign Up
          </Link>
        </p>
      </div>
    </div>
  );
}
