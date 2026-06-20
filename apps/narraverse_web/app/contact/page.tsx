"use client";
import Image from "next/image";
import contact from "@/public/conact.jpeg";
import logo2 from "@/public/logo2.png";
import { db } from "@/lib/firebase";
import { collection, addDoc, serverTimestamp } from "firebase/firestore";

import { useState } from "react";

export default function ContactPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("");

  async function handleSubmit() {
    if (!fullName || !email || !subject || !message) {
      setStatus("error");
      return;
    }
    setStatus("loading");
    try {
      await addDoc(collection(db, "contacts"), {
        fullName,
        email,
        subject,
        message,
        createdAt: serverTimestamp(),
      });
      setStatus("success");
      setFullName("");
      setEmail("");
      setSubject("");
      setMessage("");
    } catch (err) {
      console.error(err);
      setStatus("error");
    }
  }

  return (
    <div
      className="relative min-h-screen w-full flex flex-col items-center justify-center overflow-hidden py-1 pb-16"
      style={{ fontFamily: "sans-serif" }}
    >
      {/* Background */}
      <div>
        <Image
          src={contact}
          alt="audiobook"
          fill
          priority
          className="object-cover"
        />
      </div>

      {/* Title row */}
      <div className="relative z-10 flex items-center gap-1 mb-1 w-[620px] mt-6">
        <Image
          src={logo2}
          alt="logo2"
          className="w-[250px] h-[250px] object-contain"
        />

        <h1
          className="text-6xl font-bold text-white whitespace-nowrap"
          style={{
            fontFamily: "'Cormorant Garamond', serif",
            textShadow:
              "0 0 20px rgba(255,255,255,0.8), 0 0 40px rgba(180,130,255,0.6), 0 0 80px rgba(140,80,255,0.4)",
          }}
        >
          Contact Us
        </h1>
      </div>

      {/* Card */}
      <div
        className="relative z-10 w-[620px] flex flex-col rounded-2xl px-10 py-10"
        style={{
          background: "rgba(20, 19, 60, 0.6)",
          backdropFilter: "blur(18px)",
          border: "1.5px solid rgba(255, 255, 255, 0.25)",
          boxShadow:
            "0 0 60px rgba(255,255,255,0.08), inset 0 0 40px rgba(255,255,255,0.03)",
        }}
      >
        {/* Card title */}
        <h2
          className="text-2xl font-bold text-white mb-1"
          style={{ fontFamily: "'Cormorant Garamond', serif" }}
        >
          Send us an Inquiry
        </h2>
        <p className="text-sm mb-6" style={{ color: "rgba(217,217,217,0.9)" }}>
          Fill out the form below and we&apos;ll get back to you as soon as
          possible.
        </p>

        {/* Full Name */}
        <div className="relative w-full mb-4">
          <input
            type="text"
            placeholder="Enter your full name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full rounded-xl px-4 py-3 pr-11 text-sm outline-none placeholder-white/40"
            style={{
              background: "rgba(255,255,255,0.03)",
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
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </span>
        </div>

        {/* Email */}
        <div className="relative w-full mb-4">
          <input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-xl px-4 py-3 pr-11 text-sm outline-none placeholder-white/40"
            style={{
              background: "rgba(255,255,255,0.03)",
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

        {/* Subject */}
        <div className="relative w-full mb-4">
          <input
            type="text"
            placeholder="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="w-full rounded-xl px-4 py-3 pr-11 text-sm outline-none placeholder-white/40"
            style={{
              background: "rgba(255,255,255,0.03)",
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
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </span>
        </div>

        {/* Message */}
        <div className="relative w-full mb-6">
          <textarea
            placeholder="Describe your issue or inquiry..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={5}
            className="w-full rounded-xl px-4 py-3 pr-11 text-sm outline-none placeholder-white/40 resize-none"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "rgba(255,255,255,0.9)",
            }}
          />
          <span
            className="absolute right-3.5 top-4"
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
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </span>
        </div>

        {/* Submit Button */}
        <button
          onClick={handleSubmit}
          disabled={status === "loading"}
          className="w-full py-3.5 cursor-pointer rounded-full text-white font text-base tracking-wide transition-opacity duration-200 hover:opacity-90 active:scale-[0.98]"
          style={{
            background: "linear-gradient(90deg, #e0557a 0%, #c87a30 100%)",
            opacity: status === "loading" ? 0.6 : 1,
          }}
        >
          {status === "loading" ? "Sending..." : "Submit Inquiry"}
        </button>

        {/* Feedback messages — place right after the button */}
        {status === "success" && (
          <p className="text-green-400 text-sm text-center mt-3">
            ✓ Your message was sent successfully!
          </p>
        )}
        {status === "error" && (
          <p className="text-red-400 text-sm text-center mt-3">
            Please fill in all fields and try again.
          </p>
        )}
      </div>
    </div>
  );
}
