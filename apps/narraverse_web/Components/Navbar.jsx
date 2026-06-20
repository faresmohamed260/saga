"use client";

import Link from "next/link";
import Image from "next/image";
import { Outfit } from "next/font/google";
import logo from "@/public/logo.png";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";

const outfit = Outfit({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [scrolled, setScrolled] = useState(false);
  const { user, loading, logout } = useAuth();

  useEffect(() => {
    if (!loading && !user && pathname !== "/login" && pathname !== "/signup") {
      router.push("/login");
    }
  }, [user, loading, pathname, router]);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={`${outfit.className} fixed top-0 left-0 right-0 z-50 transition-all duration-300`}
      style={{
        background: scrolled ? "rgba(5, 0, 20, 0.6)" : "transparent",
        backdropFilter: scrolled ? "blur(10px)" : "none",
      }}
    >
      <div className="mx-auto flex w-full max-w-7xl flex-col items-center gap-4 px-4 py-4 sm:px-6 md:flex-row md:flex-wrap md:justify-between lg:px-10">
        <div className="flex min-w-0 items-center gap-3 self-start md:self-auto">
          <Image
            src={logo}
            alt="Logo"
            width={65}
            height={63}
            className="h-11 w-auto rotate-[0.5deg] sm:h-14"
          />
          <p className="truncate text-lg uppercase sm:text-2xl">Narraverse</p>
        </div>

        <div className="order-3 w-full md:order-2 md:w-auto">
          {!loading && user && (
            <ul className="flex flex-wrap items-center justify-center gap-3 text-sm sm:gap-4 md:text-base">
              <li>
                <Link
                  href="/"
                  className={
                    pathname === "/"
                      ? "rounded-full border border-[#ff9408] px-4 py-1 font-bold"
                      : "px-4 py-1"
                  }
                >
                  Home
                </Link>
              </li>
              <li>
                <Link
                  href="/services"
                  className={
                    [
                      "/services",
                      "/audioBook",
                      "/bookGeneration",
                      "/visual",
                    ].includes(pathname)
                      ? "rounded-full border border-[#ff9408] px-4 py-1 font-bold"
                      : "px-4 py-1"
                  }
                >
                  Services
                </Link>
              </li>
              <li>
                <Link
                  href="/contact"
                  className={
                    pathname === "/contact"
                      ? "rounded-full border border-[#ff9408] px-4 py-1 font-bold"
                      : "px-4 py-1"
                  }
                >
                  Contact Us
                </Link>
              </li>
            </ul>
          )}
        </div>

        <div className="order-2 flex w-full flex-wrap items-center justify-center gap-3 md:order-3 md:w-auto md:justify-end">
          {loading ? null : user ? (
            <button
              onClick={async () => {
                await logout();
                router.push("/login");
              }}
              className={`${outfit.className} cursor-pointer rounded-full px-5 py-2 text-sm font-medium text-white sm:px-8 sm:text-base`}
              style={{
                background: "linear-gradient(to right, #FF3A93, #FFC120)",
              }}
            >
              Logout
            </button>
          ) : (
            <>
              <Link
                href="/login"
                className={`${outfit.className} rounded-full px-5 py-2 text-sm font-medium text-white sm:px-8 sm:text-base`}
                style={{
                  background: "linear-gradient(to right, #FF3A93, #FFC120)",
                }}
              >
                Log In
              </Link>
              <Link
                href="/signup"
                className={`${outfit.className} rounded-full border border-[#ff9408] px-5 py-2 text-sm sm:px-8 sm:text-base`}
              >
                Sign Up
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
