import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { DailyTopCard } from "../components/TopicSignalCard";

function formatDateLabel(value) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function formatRelative(value) {
  if (!value) return "";
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return "";
  const diffHours = Math.max(Math.round((Date.now() - timestamp) / 3600000), 0);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.round(diffHours / 24)}d ago`;
}

export default function TopicsHistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [history, setHistory] = useState([]);
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const selectedDate = searchParams.get("date") || "";

  const loadHistory = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getDailySignalHistory(45);
      const items = data.items || [];
      setHistory(items);
      const initialDate = items[0]?.date_key || "";
      if (!selectedDate && initialDate) {
        const nextParams = new URLSearchParams(searchParams);
        nextParams.set("date", initialDate);
        setSearchParams(nextParams, { replace: true });
      }
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load daily history");
    } finally {
      setLoading(false);
    }
  }, [searchParams, selectedDate, setSearchParams]);

  const loadDateTopics = useCallback(async (dateKey) => {
    if (!dateKey) {
      setTopics([]);
      return;
    }
    try {
      const data = await api.getDailySignalsForDate(dateKey);
      setTopics(data.items || []);
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load archived daily topics");
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    if (selectedDate) {
      loadDateTopics(selectedDate);
    }
  }, [loadDateTopics, selectedDate]);

  const selectedLabel = useMemo(
    () => (selectedDate ? formatDateLabel(selectedDate) : "No day selected"),
    [selectedDate],
  );

  if (loading) {
    return (
      <div className="page-wrap leaderboard-page">
        <div className="loading-spinner">Loading daily history...</div>
      </div>
    );
  }

  return (
    <div className="page-wrap leaderboard-page history-shell">
      <div className="leaderboard-header history-header">
        <div className="header-content">
          <p className="eyebrow">Archive</p>
          <h1>Daily History</h1>
          <p className="subtitle">Browse past daily signal sets by day.</p>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <section className="history-strip">
        <div className="history-strip-header">
          <span className="history-strip-label">Days</span>
          <span className="history-strip-current">{selectedLabel}</span>
        </div>
        <div className="history-chip-list">
          {history.map((item) => {
            const isActive = item.date_key === selectedDate;
            return (
              <button
                key={item.date_key}
                type="button"
                className={`history-chip ${isActive ? "active" : ""}`}
                onClick={() => {
                  const nextParams = new URLSearchParams(searchParams);
                  nextParams.set("date", item.date_key);
                  setSearchParams(nextParams);
                }}
              >
                <strong>{formatDateLabel(item.date_key)}</strong>
                <span>{item.topics_count} topics</span>
                <small>{formatRelative(item.latest_topic_at)}</small>
              </button>
            );
          })}
        </div>
      </section>

      <section className="history-results">
        <div className="daily-signals-list">
          {topics.length === 0 ? (
            <div className="daily-signals-empty">
              No archived topics for this date yet.
            </div>
          ) : (
            topics.map((topic, index) => (
              <DailyTopCard key={`${topic.id}-${selectedDate}`} item={topic} index={index} />
            ))
          )}
        </div>
      </section>
    </div>
  );
}
