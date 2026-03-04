import { useCallback, useEffect, useState } from "react";
import { api, setAdminToken, hasAdminToken } from "../api";

export default function AdminModerationPage() {
  const [isAdmin, setIsAdmin] = useState(hasAdminToken());
  const [tokenInput, setTokenInput] = useState("");
  const [queue, setQueue] = useState([]);
  const [reports, setReports] = useState([]);
  const [logs, setLogs] = useState([]);
  const [processed, setProcessed] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadAdminData = useCallback(async () => {
    if (!hasAdminToken()) return;
    setLoading(true);
    try {
      const [queueData, reportsData, logsData, processedData] =
        await Promise.all([
          api.getModerationQueue(),
          api.getReports("open"),
          api.getModerationLogs(),
          api.getProcessedComments(),
        ]);
      setQueue(queueData || []);
      setReports(reportsData || []);
      setLogs(logsData || []);
      setProcessed(processedData || []);
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) {
      loadAdminData();
    }
  }, [isAdmin, loadAdminData]);

  // Token login
  async function handleTokenSubmit(e) {
    e.preventDefault();
    if (!tokenInput.trim()) {
      setError("Please enter a token");
      return;
    }
    // Validate token by requesting the moderation queue
    try {
      setLoading(true);
      setAdminToken(tokenInput);
      // Confirm token is valid
      await api.getModerationQueue();
      setIsAdmin(true);
      setTokenInput("");
      setError("");
    } catch {
      setAdminToken(""); // Remove invalid token
      setError("Invalid admin token");
    } finally {
      setLoading(false);
    }
  }

  // Logout
  function handleLogout() {
    setAdminToken("");
    setIsAdmin(false);
    setQueue([]);
    setReports([]);
    setLogs([]);
    setProcessed([]);
    setTokenInput("");
  }

  async function act(commentId, action) {
    try {
      await api.moderateComment(commentId, {
        action,
        reason: `Admin action: ${action}`,
      });
      await loadAdminData();
    } catch (err) {
      setError(err.message || "Admin action failed");
    }
  }

  async function reopenForReview(commentId) {
    try {
      await api.reopenComment(commentId);
      await loadAdminData();
    } catch (err) {
      setError(err.message || "Failed to reopen comment");
    }
  }

  // Show token input form when not logged in
  if (!isAdmin) {
    return (
      <div className="page-wrap">
        <h1>Admin Moderation</h1>
        <div className="token-login-form">
          <form onSubmit={handleTokenSubmit}>
            <div className="form-group">
              <label>Admin Token:</label>
              <input
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="Enter admin token"
                disabled={loading}
              />
            </div>
            <button type="submit" disabled={loading}>
              {loading ? "Verifying..." : "Login as Admin"}
            </button>
          </form>
          {error && <div className="error-box">{error}</div>}
          <p style={{ marginTop: "1rem", fontSize: "0.9rem", color: "#666" }}>
            Default token for testing: <code>dev-admin-token</code>
          </p>
        </div>
      </div>
    );
  }

  // Show moderation content when logged in
  return (
    <div className="page-wrap admin-page">
      <div className="admin-header">
        <div className="admin-header-content">
          <p className="eyebrow">Admin Panel</p>
          <h1>Moderation Dashboard</h1>
        </div>
        <button className="admin-logout-btn" onClick={handleLogout}>
          Logout
        </button>
      </div>
      {error && <div className="error-box">{error}</div>}
      {loading && <div className="admin-loading">Loading...</div>}

      {/* Pending Review Queue */}
      <section className="admin-panel-section">
        <div className="admin-section-header">
          <h2>Pending Review</h2>
          <span className="count-badge">{queue.length}</span>
        </div>
        {queue.length === 0 ? (
          <p className="empty-state">No pending comments</p>
        ) : (
          <div className="admin-cards">
            {queue.map((comment) => (
              <div key={comment.id} className="admin-comment-card">
                <div className="admin-comment-header">
                  <div className="admin-comment-meta">
                    <strong className="comment-author">
                      {comment.author_name}
                    </strong>
                    <span
                      className={`admin-status-badge status-${comment.moderation_status}`}
                    >
                      {comment.moderation_status}
                    </span>
                    <span className="comment-id">#{comment.id}</span>
                  </div>
                  <span className="comment-time">
                    {new Date(comment.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="admin-comment-text">{comment.text}</p>
                {comment.moderation_flags && (
                  <div className="admin-flags">
                    {comment.moderation_flags.split(",").map((flag, i) => (
                      <span key={i} className="flag-chip">
                        {flag}
                      </span>
                    ))}
                  </div>
                )}
                <div className="admin-comment-actions">
                  <button
                    className="admin-btn btn-approve"
                    onClick={() => act(comment.id, "approve")}
                  >
                    Approve
                  </button>
                  <button
                    className="admin-btn btn-reject"
                    onClick={() => act(comment.id, "reject")}
                  >
                    Reject
                  </button>
                  <button
                    className="admin-btn btn-hide"
                    onClick={() => act(comment.id, "hide")}
                  >
                    Hide
                  </button>
                  <button
                    className="admin-btn btn-restore"
                    onClick={() => act(comment.id, "restore")}
                  >
                    Restore
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Processed Comments */}
      <section className="admin-panel-section">
        <div className="admin-section-header">
          <h2>Processed</h2>
          <span className="count-badge">{processed.length}</span>
        </div>
        {processed.length === 0 ? (
          <p className="empty-state">No processed comments</p>
        ) : (
          <div className="admin-cards">
            {processed.map((comment) => (
              <div key={comment.id} className="admin-comment-card">
                <div className="admin-comment-header">
                  <div className="admin-comment-meta">
                    <strong className="comment-author">
                      {comment.author_name}
                    </strong>
                    <span
                      className={`admin-status-badge status-${comment.moderation_status}`}
                    >
                      {comment.moderation_status}
                    </span>
                    <span className="comment-id">#{comment.id}</span>
                  </div>
                  <span className="comment-time">
                    {new Date(comment.updated_at).toLocaleString()}
                  </span>
                </div>
                <p className="admin-comment-text">{comment.text}</p>
                <div className="admin-comment-actions">
                  <button
                    className="admin-btn btn-neutral"
                    onClick={() => reopenForReview(comment.id)}
                  >
                    Reopen for Review
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Reports Table */}
      <section className="admin-panel-section">
        <div className="admin-section-header">
          <h2>Reported</h2>
          <span className="count-badge">{reports.length}</span>
        </div>
        {reports.length === 0 ? (
          <p className="empty-state">No reports</p>
        ) : (
          <div className="admin-table">
            <div className="admin-table-header">
              <span>Comment ID</span>
              <span>Reason</span>
              <span>Reporter</span>
              <span>Date</span>
            </div>
            {reports.map((report) => (
              <div key={report.id} className="admin-table-row">
                <span className="table-cell-id">#{report.comment_id}</span>
                <span className="table-cell">{report.reason}</span>
                <span className="table-cell-mono">
                  {report.reporter_identifier}
                </span>
                <span className="table-cell-time">
                  {new Date(report.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Logs Table */}
      <section className="admin-panel-section">
        <div className="admin-section-header">
          <h2>Activity Logs</h2>
          <span className="count-badge">{logs.length}</span>
        </div>
        {logs.length === 0 ? (
          <p className="empty-state">No logs</p>
        ) : (
          <div className="admin-table">
            <div className="admin-table-header">
              <span>ID</span>
              <span>Source</span>
              <span>Action</span>
              <span>Result</span>
              <span>Date</span>
            </div>
            {logs.map((log) => (
              <div key={log.id} className="admin-table-row">
                <span className="table-cell-id">#{log.id}</span>
                <span className="table-cell-mono">{log.source}</span>
                <span className="table-cell">{log.action}</span>
                <span className="table-cell">{log.result}</span>
                <span className="table-cell-time">
                  {new Date(log.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
