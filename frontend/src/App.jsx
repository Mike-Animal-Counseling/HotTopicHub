import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import AdminModerationPage from "./pages/AdminModerationPage";
import TopicDetailPage from "./pages/TopicDetailPage";
import TopicsHistoryPage from "./pages/TopicsHistoryPage";
import TopicsPage from "./pages/TopicsPage";
import "./App.css";
import { hasAdminToken } from "./api";

function App() {
  const [isAdmin, setIsAdmin] = useState(hasAdminToken());

  // Listen for localStorage changes to keep admin state in sync
  useEffect(() => {
    function handleStorageChange() {
      setIsAdmin(hasAdminToken());
    }

    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  // Poll admin state changes periodically
  useEffect(() => {
    const interval = setInterval(() => {
      setIsAdmin(hasAdminToken());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <header className="top-nav">
        <div className="nav-left">
          <Link to="/topics">📌 Topics</Link>
          <Link to="/topics/history">🗂️ History</Link>
          <Link to="/admin/moderation">⚙️ Admin</Link>
        </div>
        <div className="nav-right">
          {isAdmin ? (
            <span className="admin-badge">👤 Admin Mode</span>
          ) : (
            <span className="user-badge">👥 User Mode</span>
          )}
        </div>
      </header>
      <Routes>
        <Route path="/" element={<Navigate to="/topics" replace />} />
        <Route path="/topics" element={<TopicsPage />} />
        <Route path="/topics/history" element={<TopicsHistoryPage />} />
        <Route path="/topics/:topicId" element={<TopicDetailPage />} />
        <Route path="/admin/moderation" element={<AdminModerationPage />} />
      </Routes>
    </div>
  );
}

export default App;
