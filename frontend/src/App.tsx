import { NavLink, Route, Routes } from "react-router-dom";
import CriteriaPage from "./pages/CriteriaPage";
import RecordScorePage from "./pages/RecordScorePage";
import RecordsListPage from "./pages/RecordsListPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">CallMetrics</div>
        <nav>
          <NavLink to="/" end>
            Chấm điểm
          </NavLink>
          <NavLink to="/criteria">Khung tiêu chí</NavLink>
        </nav>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<RecordsListPage />} />
          <Route path="/records/:id" element={<RecordScorePage />} />
          <Route path="/criteria" element={<CriteriaPage />} />
        </Routes>
      </main>
    </div>
  );
}
