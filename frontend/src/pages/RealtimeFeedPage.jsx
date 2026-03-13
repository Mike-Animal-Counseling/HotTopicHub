import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { FeedTopicRow } from "../components/TopicSignalCard";

function isValidDateValue(value) {
  if (!value) return false;
  return !Number.isNaN(new Date(value).getTime());
}

function formatHour(value) {
  if (!isValidDateValue(value)) return "Unavailable";
  const date = new Date(value);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatRelative(value) {
  if (!isValidDateValue(value)) return "Unavailable";
  const timestamp = new Date(value).getTime();
  const diffMinutes = Math.max(Math.round((Date.now() - timestamp) / 60000), 0);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.round(diffHours / 24)}d ago`;
}

export default function RealtimeFeedPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [feed, setFeed] = useState(null);
  const [history, setHistory] = useState([]);
  const selectedHour = searchParams.get("hour") || "";
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadFeed = useCallback(async (hourKey = undefined) => {
    try {
      setLoading(true);
      const [feedData, historyData] = await Promise.all([
        api.getRealtimeFeed(hourKey),
        api.getFeedHistory(48),
      ]);
      setFeed(feedData);
      setHistory(historyData.items || []);
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load realtime feed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFeed(selectedHour || undefined);
  }, [loadFeed, selectedHour]);

  useEffect(() => {
    const interval = setInterval(() => {
      loadFeed(selectedHour || undefined);
    }, 60000);
    return () => clearInterval(interval);
  }, [loadFeed, selectedHour]);

  async function handleRefresh() {
    try {
      setRefreshing(true);
      const batch = await api.refreshRealtimeFeed(selectedHour || undefined, true);
      setFeed(batch);
      const historyData = await api.getFeedHistory(48);
      setHistory(historyData.items || []);
      setError("");
    } catch (err) {
      setError(err.message || "Failed to refresh realtime feed");
    } finally {
      setRefreshing(false);
    }
  }

  const windowLabel = useMemo(() => {
    if (!feed?.batch) return "";
    return `${formatHour(feed.batch.window_start)} - ${formatHour(feed.batch.window_end)}`;
  }, [feed]);

  if (loading) {
    return (
      <div className="page-wrap feed-page">
        <div className="loading-spinner">Loading realtime feed...</div>
      </div>
    );
  }

  return (
    <div className="page-wrap feed-page">
      <div className="feed-hero">
        <div className="feed-hero-copy">
          <p className="eyebrow">Hourly Feed</p>
          <h1 className="feed-title">Live AI Builder Discussions</h1>
          <p className="feed-subtitle">
            A lightweight stream of fresh titles. Open a topic to read the source, comment, and join the discussion.
          </p>
        </div>
        <div className="feed-hero-actions">
          <select
            className="feed-hour-select"
            value={selectedHour}
            onChange={(e) => {
              const nextHour = e.target.value;
              const nextParams = new URLSearchParams(searchParams);
              if (nextHour) {
                nextParams.set("hour", nextHour);
              } else {
                nextParams.delete("hour");
              }
              setSearchParams(nextParams);
            }}
          >
            <option value="">Current hour</option>
            {history.map((batch) => (
              <option key={batch.hour_key} value={batch.hour_key}>
                {formatHour(batch.hour_key)}
              </option>
            ))}
          </select>
          <button onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? "Refreshing..." : "Refresh Hour"}
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      {feed?.batch && (
        <div className="feed-batch-bar">
          <span>
            <strong>Window</strong> {windowLabel}
          </span>
          <span>
            <strong>Updated</strong> {formatRelative(feed.batch.created_at)}
          </span>
          <span>
            <strong>Items</strong> {feed.batch.items_count}
          </span>
        </div>
      )}

      <div className="feed-layout">
        <section className="feed-stream">
          {(feed?.items || []).length === 0 ? (
            <div className="feed-empty-state">
              <h2>No items for this hour yet</h2>
              <p>
                The selected hour did not surface enough qualifying AI builder topics yet.
              </p>
            </div>
          ) : (
            (feed?.items || []).map((item, index) => (
              <FeedTopicRow key={item.id} item={item} index={index} />
            ))
          )}
        </section>

        <aside className="feed-history-panel">
          <h2>Recent Batches</h2>
          <div className="feed-history-list">
            {history.map((batch) => {
              const isActive =
                (selectedHour || feed?.batch?.hour_key) === batch.hour_key;
              return (
                <button
                  key={batch.hour_key}
                  className={`feed-history-item ${isActive ? "active" : ""}`}
                  onClick={() => setSelectedHour(batch.hour_key)}
                >
                  <span className="feed-history-copy">
                    <strong>{formatHour(batch.hour_key)}</strong>
                    <small>{formatRelative(batch.created_at)}</small>
                  </span>
                  <small className="feed-history-count">{batch.items_count} items</small>
                </button>
              );
            })}
          </div>
        </aside>
      </div>
    </div>
  );
}
