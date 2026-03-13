import { useLocation, useNavigate } from "react-router-dom";

function formatRelative(value) {
  if (!value) return "Unavailable";
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return "Unavailable";
  const diffMinutes = Math.max(Math.round((Date.now() - timestamp) / 60000), 0);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.round(diffHours / 24)}d ago`;
}

function getBackLabel(pathname) {
  if (pathname.startsWith("/topics/history")) {
    return "Back to History";
  }
  if (pathname.startsWith("/feed")) {
    return "Back to Live Feed";
  }
  return "Back to Hub";
}

function getRankLabel(index) {
  return String(index + 1);
}

export function FeedTopicRow({ item, index }) {
  const navigate = useNavigate();
  const location = useLocation();
  const topicId = item.topic_id || item.id;
  const sources = item.sources?.length
    ? item.sources
    : item.source
      ? [item.source]
      : [];

  function openDiscussion() {
    if (topicId) {
      navigate(`/topics/${topicId}`, {
        state: {
          backTo: `${location.pathname}${location.search}`,
          backLabel: getBackLabel(location.pathname),
        },
      });
    }
  }

  return (
    <article className="feed-topic-row" onClick={openDiscussion}>
      <div className="feed-topic-index">
        <span>#{index + 1}</span>
      </div>
      <div className="feed-topic-main">
        <div className="feed-topic-meta">
          <div className="source-badges">
            {sources.map((source) => (
              <span key={`${item.id}-${source}`} className="source-badge">
                {source}
              </span>
            ))}
            <span className={`feed-type-chip type-${item.content_type}`}>
              {item.content_type.replaceAll("_", " ")}
            </span>
          </div>
          <div className="stats-mini">
            <span className="stat-item">{formatRelative(item.published_time || item.created_at)}</span>
          </div>
        </div>

        <button type="button" className="feed-topic-title" onClick={openDiscussion}>
          {item.title}
        </button>

        <div className="feed-topic-footer">
          <div className="stats-mini">
            <span className="stat-item">{item.likes_count || 0} likes</span>
            <span className="stat-item">{item.comments_count || 0} comments</span>
            <span className="stat-item">{item.source_clicks_count || 0} source clicks</span>
          </div>
        </div>
      </div>
    </article>
  );
}

export function DailyTopCard({ item, index }) {
  const navigate = useNavigate();
  const location = useLocation();
  const topicId = item.id || item.topic_id;
  const sources = item.sources?.length
    ? item.sources
    : item.source
      ? [item.source]
      : [];

  function openDiscussion() {
    if (topicId) {
      navigate(`/topics/${topicId}`, {
        state: {
          backTo: `${location.pathname}${location.search}`,
          backLabel: getBackLabel(location.pathname),
        },
      });
    }
  }

  return (
    <article className={`signal-card signal-rank-${index + 1}`} onClick={openDiscussion}>
      <div className="signal-card-body">
        <div className="signal-card-topline">
          <div className="signal-card-meta">
            <span
              className={`signal-rank-label ${index < 3 ? `signal-rank-top signal-rank-top-${index + 1}` : ""}`}
            >
              {getRankLabel(index)}
            </span>
            <div className="source-badges">
              {sources.map((source) => (
                <span key={`${item.id}-${source}`} className="source-badge">
                  {source}
                </span>
              ))}
            </div>
          </div>
          <span className="signal-time-label">
            {formatRelative(item.published_time || item.created_at)}
          </span>
        </div>

        <button type="button" className="signal-card-title" onClick={openDiscussion}>
          {item.title}
        </button>

        {item.summary && <p className="signal-card-summary">{item.summary}</p>}

        <div className="signal-card-grid">
          {item.key_insights && (
            <section className="signal-note signal-note-primary">
              <p className="signal-note-label">Insight Summary</p>
              <p className="signal-note-copy">{item.key_insights}</p>
            </section>
          )}
          {item.why_it_matters && (
            <section className="signal-note">
              <p className="signal-note-label">Why It Matters</p>
              <p className="signal-note-copy">{item.why_it_matters}</p>
            </section>
          )}
        </div>

        <div className="signal-card-footer">
          <div className="signal-stats">
            <span>{item.likes_count || 0} likes</span>
            <span>{item.comments_count || 0} comments</span>
            <span>{item.source_clicks_count || 0} source clicks</span>
          </div>
        </div>
      </div>
    </article>
  );
}
