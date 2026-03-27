import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import "./App.css";
import { hasAdminToken } from "./api";
import AdminModerationPage from "./pages/AdminModerationPage";
import RealtimeFeedPage from "./pages/RealtimeFeedPage";
import TopicDetailPage from "./pages/TopicDetailPage";
import TopicsHistoryPage from "./pages/TopicsHistoryPage";
import TopicsPage from "./pages/TopicsPage";

function App() {
  const [isAdmin, setIsAdmin] = useState(hasAdminToken());
  const location = useLocation();

  useEffect(() => {
    function handleStorageChange() {
      setIsAdmin(hasAdminToken());
    }

    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setIsAdmin(hasAdminToken());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [location.pathname, location.search]);

  return (
    <div>
      <header className="top-nav">
        <div className="nav-left">
          <NavLink
            to="/topics"
            end
            className={({ isActive }) => `nav-pill ${isActive ? "active" : ""}`}
          >
            Daily Hub
          </NavLink>
          <NavLink
            to="/topics/history"
            className={({ isActive }) => `nav-pill ${isActive ? "active" : ""}`}
          >
            History
          </NavLink>
          <NavLink
            to="/feed"
            className={({ isActive }) => `nav-pill ${isActive ? "active" : ""}`}
          >
            Live Feed
          </NavLink>
          <NavLink
            to="/admin/moderation"
            className={({ isActive }) => `nav-pill ${isActive ? "active" : ""}`}
          >
            Admin
          </NavLink>
        </div>
        <div className="nav-right">
          {isAdmin ? (
            <span className="admin-badge">Admin Mode</span>
          ) : (
            <span className="user-badge">User Mode</span>
          )}
        </div>
      </header>
      <Routes>
        <Route path="/" element={<Navigate to="/topics" replace />} />
        <Route path="/topics" element={<TopicsPage />} />
        <Route path="/topics/history" element={<TopicsHistoryPage />} />
        <Route path="/feed" element={<RealtimeFeedPage />} />
        <Route path="/topics/:topicId" element={<TopicDetailPage />} />
        <Route path="/admin/moderation" element={<AdminModerationPage />} />
      </Routes>
    </div>
  );
}

export default App;
