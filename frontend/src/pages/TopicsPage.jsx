import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { DailyTopCard } from "../components/TopicSignalCard";

let cachedDailySignals = [];

export default function TopicsPage() {
  const [dailySignals, setDailySignals] = useState(cachedDailySignals);
  const [loading, setLoading] = useState(cachedDailySignals.length === 0);
  const [error, setError] = useState("");

  const loadSignals = useCallback(async () => {
    try {
      if (cachedDailySignals.length === 0) {
        setLoading(true);
      }
      const signalsData = await api.getDailyTopSignals();
      const items = signalsData.items || [];
      cachedDailySignals = items;
      setDailySignals(items);
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

      <div className="daily-signals-list daily-signals-list-hub">
        {loading && dailySignals.length === 0 ? (
          <div className="daily-signals-empty">Loading daily top signals...</div>
        ) : dailySignals.length === 0 ? (
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
    </div>
  );
}
