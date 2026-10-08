import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import Consent from "./pages/Consent";
import Live from "./pages/Live";
import ManualForm from "./pages/ManualForm";
import Official from "./pages/Official";

export default function App() {
  return (
    <BrowserRouter>
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          backgroundColor: "#f1f5f9",
          color: "#0f172a",
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        }}
      >
        <Navbar />
        <main style={{ flex: 1, paddingBottom: "2rem" }}>
          <Routes>
            <Route path="/" element={<Consent />} />
            <Route path="/consent" element={<Consent />} />
            <Route path="/live" element={<Live />} />
            <Route path="/form" element={<ManualForm />} />
            <Route path="/official" element={<Official />} />
            <Route path="*" element={<Navigate to="/consent" replace />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </BrowserRouter>
  );
}
