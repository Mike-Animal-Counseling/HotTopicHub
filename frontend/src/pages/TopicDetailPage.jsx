import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";

const DEFAULT_USER = "guest-user";

export default function TopicDetailPage() {
  const { topicId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [topic, setTopic] = useState(null);
  const [comments, setComments] = useState([]);
  const [rankedComments, setRankedComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [authorName, setAuthorName] = useState("Guest");
  const [userIdentifier, setUserIdentifier] = useState(DEFAULT_USER);
  const [text, setText] = useState("");
  const [imageUrl, setImageUrl] = useState("");

  const normalizedTopicId = useMemo(() => Number(topicId), [topicId]);
  const backTo = location.state?.backTo || "/topics";
  const backLabel = location.state?.backLabel || "Back to Hub";

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [topicData, commentsData] = await Promise.all([
        api.getTopic(normalizedTopicId),
        api.getComments(normalizedTopicId),
      ]);
      setTopic(topicData);
      setComments(commentsData.items || []);
      try {
        const rankedData = await api.getRankedComments(normalizedTopicId);
        setRankedComments(rankedData || []);
      } catch {
        setRankedComments([]);
      }
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load topic details");
    } finally {
      setLoading(false);
    }
  }, [normalizedTopicId]);

  useEffect(() => {
    if (Number.isNaN(normalizedTopicId)) {
      setError("Invalid topic id");
      setLoading(false);
      return;
    }
    loadAll();
  }, [loadAll, normalizedTopicId]);

  useEffect(() => {
    if (Number.isNaN(normalizedTopicId)) return;

    const intervalId = setInterval(() => {
      api.getComments(normalizedTopicId)
        .then((data) => {
          setComments(data.items || []);
        })
        .catch(() => {});
    }, 10000);

    return () => clearInterval(intervalId);
  }, [normalizedTopicId]);

  async function submitComment() {
    const payload = {
      author_name: authorName.trim() || "Guest",
      user_identifier: userIdentifier.trim() || DEFAULT_USER,
      text: text.trim(),
      image_url: imageUrl.trim() || null,
    };

    if (!payload.text) {
      setNotice("Please enter comment text.");
      return;
    }

    try {
      const response = await api.createComment(normalizedTopicId, payload);
      if (response.status === "pending_review") {
        setNotice(
          response.message ||
            "Your comment is awaiting moderation and will appear once reviewed.",
        );
      } else {
        setNotice("Comment published");
      }
      setText("");
      setImageUrl("");
      await loadAll();
    } catch (err) {
      setNotice(err.message || "Comment rejected");
    }
  }

  async function handleTopicLike() {
    try {
      await api.likeTopic(normalizedTopicId, userIdentifier.trim() || DEFAULT_USER);
      await loadAll();
    } catch (err) {
      setNotice(err.message || "Failed to like topic");
    }
  }

  function handleSourceClick() {
    api.recordTopicSourceClick(normalizedTopicId).catch(() => {});
  }

  async function likeComment(commentId) {
    try {
      await api.likeComment(commentId, userIdentifier.trim() || DEFAULT_USER);
      await loadAll();
    } catch (err) {
      setNotice(err.message || "Failed to like comment");
    }
  }

  async function reportComment(commentId) {
    try {
      await api.reportComment(commentId, {
        reporter_identifier: userIdentifier.trim() || DEFAULT_USER,
        reason: "other",
        details: "Reported by user from topic detail page.",
      });
      setNotice("Reported. Thank you.");
      await loadAll();
    } catch (err) {
      setNotice(err.message || "Failed to report comment");
    }
  }

  if (loading) {
    return (
      <div className="page-wrap">
        <div className="loading-spinner">Loading topic...</div>
      </div>
    );
  }

  return (
    <div className="page-wrap detail-page">
      <button
        type="button"
        className="detail-back-link"
        onClick={() => navigate(backTo)}
      >
        {backLabel}
      </button>
      {error && <div className="error-box">{error}</div>}

      {topic && (
        <>
          <div className="detail-hero">
            <div className="detail-hero-meta">
              {(topic.sources || []).map((source) => (
                <span key={source} className="source-badge">
                  {source}
                </span>
              ))}
              {topic.daily_rank && (
                <span className="detail-rank-chip">#{topic.daily_rank} today</span>
              )}
            </div>
            <h1 className="detail-title">{topic.title}</h1>
            <p className="detail-summary">{topic.summary}</p>
            <div className="detail-actions">
              <button className="detail-like-btn" onClick={handleTopicLike}>
                {topic.likes_count} likes
              </button>
              <span className="detail-stat">{topic.comments_count} comments</span>
              <span className="detail-stat">
                {topic.source_clicks_count || 0} source clicks
              </span>
              {(topic.canonical_url || topic.source_url) && (
                <a
                  href={topic.canonical_url || topic.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="detail-source-link"
                  onClick={handleSourceClick}
                >
                  View source ->
                </a>
              )}
            </div>
          </div>

          <div className="detail-insights-grid">
            {topic.key_insights && (
              <div className="detail-insight-card">
                <p className="insight-eyebrow">Key Insights</p>
                <p className="insight-body">{topic.key_insights}</p>
              </div>
            )}
            {topic.why_it_matters && (
              <div className="detail-insight-card">
                <p className="insight-eyebrow">Why It Matters</p>
                <p className="insight-body">{topic.why_it_matters}</p>
              </div>
            )}
            {topic.technical_summary && (
              <div className="detail-insight-card insight-card-wide">
                <p className="insight-eyebrow">Technical Summary</p>
                <p className="insight-body">{topic.technical_summary}</p>
              </div>
            )}
          </div>
        </>
      )}

      <div className="detail-comment-form">
        <h2 className="detail-section-title">Leave a comment</h2>
        <div className="detail-form-row">
          <input
            className="detail-input"
            value={authorName}
            onChange={(e) => setAuthorName(e.target.value)}
            placeholder="Your name"
          />
          <input
            className="detail-input"
            value={userIdentifier}
            onChange={(e) => setUserIdentifier(e.target.value)}
            placeholder="User identifier"
          />
        </div>
        <textarea
          className="detail-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Share your thoughts..."
          rows={3}
        />
        <input
          className="detail-input"
          value={imageUrl}
          onChange={(e) => setImageUrl(e.target.value)}
          placeholder="Image URL (optional)"
        />
        <button className="detail-submit-btn" onClick={submitComment}>
          Post comment
        </button>
        {notice && <div className="notice-box detail-form-notice">{notice}</div>}
      </div>

      <div className="detail-comments-block">
        <h2 className="detail-section-title">Discussion</h2>

        {rankedComments.slice(0, 3).length > 0 && (
          <div className="detail-highlights">
            {rankedComments.slice(0, 3).map((item) => (
              <div key={`hl-${item.id}`} className="detail-highlight-chip">
                <span className="highlight-label">{item.highlight}</span>
                <span className="highlight-author">{item.author_name}</span>
              </div>
            ))}
          </div>
        )}

        {comments.map((comment) => (
          <div key={comment.id} className="detail-comment-card">
            <div className="detail-comment-header">
              <strong className="comment-author">{comment.author_name}</strong>
              <span className="comment-time">
                {new Date(comment.created_at).toLocaleString()}
              </span>
            </div>
            {comment.is_hidden ? (
              <p className="hidden-placeholder">Hidden pending moderation.</p>
            ) : (
              <>
                <p className="comment-body">{comment.text}</p>
                {comment.image_url && (
                  <img
                    className="comment-image"
                    src={comment.image_url}
                    alt="Comment attachment"
                  />
                )}
              </>
            )}
            <div className="detail-comment-actions">
              <button
                className="comment-action-btn"
                onClick={() => likeComment(comment.id)}
              >
                {comment.likes_count} likes
              </button>
              <button
                className="comment-action-btn comment-report-btn"
                onClick={() => reportComment(comment.id)}
              >
                Report
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
