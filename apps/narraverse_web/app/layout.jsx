import "./globals.css";
import Navbar from "@/Components/Navbar";
import Footer from "@/Components/Footer";
import { AuthProvider } from "@/context/AuthContext";
import { Toaster } from "react-hot-toast";

export const metadata = {
  title: "Narraverse",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="m-0 p-0 bg-transparent">
        <AuthProvider>
          <Navbar />
          {children}
          <Footer />
          <Toaster
            position="top-center"
            toastOptions={{
              style: {
                background: "rgba(30, 18, 55, 0.95)",
                color: "#fff",
                border: "1px solid rgba(255,255,255,0.15)",
                backdropFilter: "blur(10px)",
                borderRadius: "12px",
                fontSize: "14px",
              },
              success: {
                iconTheme: { primary: "#e0557a", secondary: "#fff" },
              },
              error: {
                iconTheme: { primary: "#ff6b6b", secondary: "#fff" },
              },
            }}
          />
        </AuthProvider>
      </body>
    </html>
  );
}
