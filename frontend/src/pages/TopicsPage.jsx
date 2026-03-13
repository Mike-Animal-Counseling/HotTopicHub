import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { DailyTopCard } from "../components/TopicSignalCard";

export default function TopicsPage() {
  const [dailySignals, setDailySignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadSignals = useCallback(async () => {
    try {
      setLoading(true);
      const signalsData = await api.getDailyTopSignals();
      setDailySignals(signalsData.items || []);
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load daily top signals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSignals();
  }, [loadSignals]);

  if (loading) {
    return (
      <div className="page-wrap">
        <div className="loading-spinner">Loading daily top signals...</div>
      </div>
    );
  }

  return (
    <div className="page-wrap leaderboard-page">
      <div className="leaderboard-header">
        <div className="header-content">
          <p className="eyebrow">Daily Top 10</p>
          <h1>AI Builder Daily Top 10</h1>
          <p className="subtitle">What builders engaged with most in the last 24 hours.</p>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <section className="daily-signals-section">
        <div className="daily-signals-list">
          {dailySignals.length === 0 ? (
            <div className="daily-signals-empty">
              No engagement signals yet. Refresh the hourly feed, then add likes, comments, or source clicks.
            </div>
          ) : (
            dailySignals.map((topic, index) => (
              <DailyTopCard
                key={`signal-${topic.id}`}
                item={topic}
                index={index}
              />
            ))
          )}
        </div>
      </section>
    </div>
  );
}
