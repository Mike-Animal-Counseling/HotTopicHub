import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";

const getMedalEmoji = (rank) => {
  if (rank === 1) return "🥇";
  if (rank === 2) return "🥈";
  if (rank === 3) return "🥉";
  return "";
};

const getEngagementTier = (rank) => {
  if (rank === 1) return { label: "Viral", icon: "🔥", cls: "tier-viral" };
  if (rank <= 3) return { label: "Hot", icon: "⚡", cls: "tier-hot" };
  if (rank <= 6) return { label: "Rising", icon: "📈", cls: "tier-rising" };
  return { label: "Notable", icon: "💡", cls: "tier-notable" };
};

export default function TopicsPage() {
  const [searchParams] = useSearchParams();
  const dateKey = searchParams.get("date") || "";
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [hoveredId, setHoveredId] = useState(null);

  const loadTopics = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getTopics(dateKey || undefined);
      setTopics(data.items || []);
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load topics");
    } finally {
      setLoading(false);
    }
  }, [dateKey]);

  useEffect(() => {
    loadTopics();
  }, [loadTopics]);

  if (loading) {
    return (
      <div className="page-wrap">
        <div className="loading-spinner">⏳ Loading topics...</div>
      </div>
    );
  }

  return (
    <div className="page-wrap leaderboard-page">
      <div className="leaderboard-header">
        <div className="header-content">
          <p className="eyebrow">
            Daily Digest ·{" "}
            {dateKey ||
              new Date().toLocaleDateString("en-US", {
                month: "long",
                day: "numeric",
                year: "numeric",
              })}
          </p>
          <h1>AI Builder Daily Hub</h1>
          <p className="subtitle">
            {dateKey
              ? `Showing topics for ${dateKey}`
              : "Today's top 10 signals from across the builder ecosystem"}
          </p>
        </div>
        <Link to="/topics/history" className="history-link">
          Archive
        </Link>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="leaderboard-container">
        {topics.map((topic, index) => {
          const rank = index + 1;
          const medal = getMedalEmoji(rank);
          const isMedalist = rank <= 3;
          const tier = getEngagementTier(rank);

          return (
            <Link
              key={topic.id}
              to={`/topics/${topic.id}`}
              data-rank={rank}
              className={`leaderboard-row ${isMedalist ? `rank-${rank}` : ""} ${
                hoveredId === topic.id ? "active" : ""
              }`}
              onMouseEnter={() => setHoveredId(topic.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              {isMedalist ? (
                <div className="rank-badge medal-badge" data-rank={rank}>
                  {medal}
                </div>
              ) : (
                <div className="rank-badge rank-chip" data-rank={rank}>
                  <span className="rank-chip-number">#{rank}</span>
                </div>
              )}

              <div className="topic-content">
                <h2 className="topic-title">{topic.title}</h2>
                <p className="topic-summary">
                  {topic.summary || "Aggregated from multiple sources"}
                </p>

                <div className="topic-meta">
                  <div className="source-badges">
                    {(topic.sources || []).map((source) => (
                      <span key={source} className="source-badge">
                        {source}
                      </span>
                    ))}
                  </div>

                  <div className="stats-mini">
                    <span className={`engagement-tier ${tier.cls}`}>
                      {tier.label}
                    </span>
                    <span className="stat-item">{topic.likes_count} likes</span>
                    <span className="stat-item">
                      {topic.comments_count} comments
                    </span>
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
