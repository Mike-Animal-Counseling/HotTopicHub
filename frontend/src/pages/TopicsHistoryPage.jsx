import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function TopicsHistoryPage() {
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadHistory() {
      try {
        setLoading(true);
        const data = await api.getTopicHistory();
        setBatches(data.items || []);
        setError("");
      } catch (err) {
        setError(err.message || "Failed to load history");
      } finally {
        setLoading(false);
      }
    }
    loadHistory();
  }, []);

  if (loading) {
    return (
      <div className="page-wrap history-page">
        <div
          style={{
            textAlign: "center",
            padding: "3rem 1rem",
            color: "#A8A29E",
          }}
        >
          Loading archive...
        </div>
      </div>
    );
  }

  const formatDate = (dateStr) => {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const formatTime = (isoStr) => {
    const d = new Date(isoStr);
    return d.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="page-wrap history-page">
      {/* Hero Header */}
      <div className="history-hero">
        <p className="eyebrow">ARCHIVE</p>
        <h1 className="history-title">Daily Topic History</h1>
        <p className="history-subtitle">
          Browse and explore past daily topic batches
        </p>
      </div>

      {error && (
        <div
          style={{
            background: "#FEF2F2",
            border: "1px solid #FECACA",
            color: "#991B1B",
            padding: "1rem 1.25rem",
            borderRadius: "8px",
            marginBottom: "2rem",
            fontSize: "0.95rem",
          }}
        >
          {error}
        </div>
      )}

      {/* Timeline */}
      {batches.length > 0 ? (
        <div className="history-timeline">
          {batches.map((batch, index) => (
            <div key={batch.id} className="timeline-item">
              {/* Timeline Dot and Line */}
              <div className="timeline-marker">
                <div className="timeline-dot"></div>
                {index < batches.length - 1 && (
                  <div className="timeline-line"></div>
                )}
              </div>

              {/* Timeline Card */}
              <Link className="history-card" to={`/topics?date=${batch.date}`}>
                <div className="history-card-header">
                  <span className="history-date">{formatDate(batch.date)}</span>
                </div>
                <p className="history-card-label">Daily archive</p>
                <p className="history-card-time">
                  Generated at {formatTime(batch.created_at)}
                </p>
              </Link>
            </div>
          ))}
        </div>
      ) : (
        <div className="history-empty">
          <p>No archived topic batches yet</p>
          <p
            style={{
              fontSize: "0.9rem",
              color: "#A8A29E",
              marginTop: "0.5rem",
            }}
          >
            Check back when daily topics are generated
          </p>
        </div>
      )}
    </div>
  );
}
