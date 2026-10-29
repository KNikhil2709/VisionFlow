import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import TopNav from "./components/layout/TopNav";
import Inspect from "./pages/Inspect";
import Pipeline from "./pages/Pipeline";
import Review from "./pages/Review";
import HowItWorks from "./pages/HowItWorks";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <TopNav />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Inspect />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/review" element={<Review />} />
            <Route path="/how-it-works" element={<HowItWorks />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
