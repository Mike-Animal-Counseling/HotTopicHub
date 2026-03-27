import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { FeedTopicRow } from "../components/TopicSignalCard";

let cachedFeedStream = null;
let cachedPendingFeed = null;
let cachedPendingCount = 0;
let cachedVisibleCount = 14;

const INITIAL_VISIBLE_COUNT = 14;
const LOAD_MORE_STEP = 10;

function isValidDateValue(value) {
  if (!value) return false;
  return !Number.isNaN(new Date(value).getTime());
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

function formatWindow(value) {
  if (!isValidDateValue(value)) return "Unavailable";
  const date = new Date(value);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function RealtimeFeedPage() {
  const [feed, setFeed] = useState(cachedFeedStream);
  const [loading, setLoading] = useState(!cachedFeedStream);
  const [refreshing, setRefreshing] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [pendingFeed, setPendingFeed] = useState(cachedPendingFeed);
  const [pendingCount, setPendingCount] = useState(cachedPendingCount);
  const [visibleCount, setVisibleCount] = useState(cachedVisibleCount);
  const feedRef = useRef(null);

  useEffect(() => {
    feedRef.current = feed;
  }, [feed]);

  const replaceFeed = useCallback((nextFeed) => {
    cachedFeedStream = nextFeed;
    cachedPendingFeed = null;
    cachedPendingCount = 0;
    cachedVisibleCount = INITIAL_VISIBLE_COUNT;
    setFeed(nextFeed);
    setPendingFeed(null);
    setPendingCount(0);
    setVisibleCount(INITIAL_VISIBLE_COUNT);
  }, []);

  const loadFeed = useCallback(
    async ({ silent = false, adopt = true } = {}) => {
      try {
        if (!silent && !cachedFeedStream) {
          setLoading(true);
        } else {
          setChecking(true);
        }
        const streamData = await api.getRealtimeFeedStream(60, 24);
        const currentFeed = feedRef.current;
        if (!adopt && currentFeed) {
          const currentIds = new Set((currentFeed.items || []).map((item) => item.id));
          const unseen = (streamData.items || []).filter((item) => !currentIds.has(item.id));
          if (unseen.length > 0) {
            cachedPendingFeed = streamData;
            cachedPendingCount = unseen.length;
            setPendingFeed(streamData);
            setPendingCount(unseen.length);
          } else {
            cachedPendingFeed = null;
            cachedPendingCount = 0;
            setPendingFeed(null);
            setPendingCount(0);
          }
        } else {
          replaceFeed(streamData);
        }
        setError("");
      } catch (err) {
        setError(err.message || "Failed to load live feed");
      } finally {
        setLoading(false);
        setChecking(false);
      }
    },
    [replaceFeed],
  );

  useEffect(() => {
    loadFeed();
  }, [loadFeed]);

  useEffect(() => {
    const interval = setInterval(() => {
      loadFeed({ silent: true, adopt: false });
    }, 45000);
    return () => clearInterval(interval);
  }, [loadFeed]);

  async function handleRefresh() {
    try {
      setRefreshing(true);
      await api.refreshRealtimeFeed(undefined, true);
      const streamData = await api.getRealtimeFeedStream(60, 24);
      replaceFeed(streamData);
      setError("");
    } catch (err) {
      setError(err.message || "Failed to refresh live feed");
    } finally {
      setRefreshing(false);
    }
  }

  const meta = feed?.meta;
  const visibleItems = (feed?.items || []).slice(0, visibleCount);
  const hasMoreItems = (feed?.items || []).length > visibleCount;
  const streamLabel = useMemo(() => {
    if (!meta?.window_start || !meta?.window_end) return "";
    return `${formatWindow(meta.window_start)} - ${formatWindow(meta.window_end)}`;
  }, [meta]);

  return (
    <div className="page-wrap feed-page feed-page-stream">
      <div className="feed-hero feed-hero-stream">
        <div className="feed-hero-copy header-content">
          <p className="eyebrow">Live Feed</p>
          <h1 className="feed-title">Live AI Builder Discussions</h1>
          <p className="subtitle">
            A live stream of fresh AI-builder signals.
          </p>
        </div>
        <div className="feed-hero-actions">
          <button
            className="feed-refresh-btn"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing..." : "Refresh Feed"}
          </button>
        </div>
      </div>

      {pendingCount > 0 && pendingFeed && (
        <div className="feed-new-items-banner" role="status" aria-live="polite">
          <div className="feed-new-items-copy">
            <strong>{pendingCount} new items</strong>
            <span>Fresh signals are ready to drop into the stream.</span>
          </div>
          <button
            className="feed-new-items-btn"
            onClick={() => replaceFeed(pendingFeed)}
          >
            Show latest
          </button>
        </div>
      )}

      {error && <div className="error-box">{error}</div>}

      {meta && (
        <div className="feed-stream-bar">
          <span>
            <strong>Coverage</strong> {streamLabel || "Last 24 hours"}
          </span>
          <span>
            <strong>Updated</strong> {formatRelative(meta.updated_at)}
          </span>
          <span>
            <strong>Live items</strong> {meta.total_items}
          </span>
          <span>
            <strong>Active windows</strong> {meta.active_hours}
          </span>
          {checking && <span className="feed-stream-pulse">Checking for new items...</span>}
        </div>
      )}

      <section className="feed-stream feed-stream-continuous">
        {loading && !feed ? (
          <div className="feed-empty-state">
            <h2>Loading live feed...</h2>
            <p>Pulling the latest stream of AI-builder topics.</p>
          </div>
        ) : (feed?.items || []).length === 0 ? (
          <div className="feed-empty-state">
            <h2>No live items yet</h2>
            <p>
              The feed has not surfaced enough qualifying AI builder topics in the latest stream window.
            </p>
          </div>
        ) : (
          visibleItems.map((item, index) => (
            <FeedTopicRow key={item.id} item={item} index={index} />
          ))
        )}
      </section>

      {hasMoreItems && (
        <div className="feed-load-more-shell">
          <button
            className="feed-load-more-btn"
            onClick={() => {
              const nextCount = visibleCount + LOAD_MORE_STEP;
              cachedVisibleCount = nextCount;
              setVisibleCount(nextCount);
            }}
          >
            Load more
          </button>
          <p className="feed-load-more-meta">
            Showing {visibleItems.length} of {(feed?.items || []).length} live items.
          </p>
        </div>
      )}
    </div>
  );
}
