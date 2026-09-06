import { Route, Routes } from "react-router-dom";

import { HomePage } from "./pages/HomePage.jsx";
import { SttTestPage } from "./pages/SttTestPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/stt-test" element={<SttTestPage />} />
      <Route path="*" element={<HomePage />} />
    </Routes>
  );
}
