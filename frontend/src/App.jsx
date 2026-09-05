import { Route, Routes } from "react-router-dom";

import { FoundationPage } from "./pages/FoundationPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<FoundationPage />} />
    </Routes>
  );
}
