import { useCallback, useEffect, useState } from "react";
import { api, setAdminToken, hasAdminToken } from "../api";

export default function AdminModerationPage() {
  const [isAdmin, setIsAdmin] = useState(hasAdminToken());
  const [tokenInput, setTokenInput] = useState("");
  const [queue, setQueue] = useState([]);
  const [reports, setReports] = useState([]);
  const [logs, setLogs] = useState([]);
  const [approved, setApproved] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectCommentId, setRejectCommentId] = useState(null);
  const [rejectReason, setRejectReason] = useState("");

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
      const approvedData = (processedData || []).filter(
        (c) => c.moderation_status === "approved",
      );
      const rejectedData = (processedData || []).filter(
        (c) => c.moderation_status === "rejected",
      );
      setApproved(approvedData);
      setRejected(rejectedData);
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
    setApproved([]);
    setRejected([]);
    setTokenInput("");
  }

  async function act(commentId, action, reasonInput = null) {
    try {
      const reason = reasonInput || `Admin action: ${action}`;
      await api.moderateComment(commentId, {
        action,
        reason,
      });
      await loadAdminData();
    } catch (err) {
      setError(err.message || "Admin action failed");
    }
  }

  function openRejectModal(commentId) {
    setRejectCommentId(commentId);
    setRejectReason("");
    setShowRejectModal(true);
  }

  async function submitReject() {
    if (rejectCommentId) {
      await act(
        rejectCommentId,
        "reject",
        rejectReason.trim() || null
      );
      setShowRejectModal(false);
      setRejectCommentId(null);
      setRejectReason("");
    }
  }

  function closeRejectModal() {
    setShowRejectModal(false);
    setRejectCommentId(null);
    setRejectReason("");
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
  function scrollToSection(sectionId) {
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

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

      {/* Sidebar Navigation */}
      <div
        style={{
          position: "fixed",
          left: "1.5rem",
          top: "50%",
          transform: "translateY(-50%)",
          backgroundColor: "rgba(255, 255, 255, 0.85)",
          backdropFilter: "blur(8px)",
          padding: "0.75rem 0.5rem",
          borderRadius: "6px",
          border: "1px solid rgba(0, 0, 0, 0.06)",
          zIndex: 100,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <button
            onClick={() => scrollToSection("pending-review")}
            style={{
              textAlign: "left",
              padding: "0.4rem 0.6rem",
              border: "none",
              background: "none",
              cursor: "pointer",
              borderRadius: "3px",
              fontSize: "0.85rem",
              color: "#555",
              transition: "all 0.2s",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = "rgba(0, 0, 0, 0.04)";
              e.target.style.color = "#000";
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = "transparent";
              e.target.style.color = "#555";
            }}
          >
            <span style={{ fontSize: "8px" }}>●</span> Pending
          </button>
          <button
            onClick={() => scrollToSection("approved")}
            style={{
              textAlign: "left",
              padding: "0.4rem 0.6rem",
              border: "none",
              background: "none",
              cursor: "pointer",
              borderRadius: "3px",
              fontSize: "0.85rem",
              color: "#555",
              transition: "all 0.2s",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = "rgba(0, 0, 0, 0.04)";
              e.target.style.color = "#000";
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = "transparent";
              e.target.style.color = "#555";
            }}
          >
            <span style={{ fontSize: "8px" }}>●</span> Approved
          </button>
          <button
            onClick={() => scrollToSection("rejected")}
            style={{
              textAlign: "left",
              padding: "0.4rem 0.6rem",
              border: "none",
              background: "none",
              cursor: "pointer",
              borderRadius: "3px",
              fontSize: "0.85rem",
              color: "#555",
              transition: "all 0.2s",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = "rgba(0, 0, 0, 0.04)";
              e.target.style.color = "#000";
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = "transparent";
              e.target.style.color = "#555";
            }}
          >
            <span style={{ fontSize: "8px" }}>●</span> Rejected
          </button>
          <button
            onClick={() => scrollToSection("reported")}
            style={{
              textAlign: "left",
              padding: "0.4rem 0.6rem",
              border: "none",
              background: "none",
              cursor: "pointer",
              borderRadius: "3px",
              fontSize: "0.85rem",
              color: "#555",
              transition: "all 0.2s",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = "rgba(0, 0, 0, 0.04)";
              e.target.style.color = "#000";
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = "transparent";
              e.target.style.color = "#555";
            }}
          >
            <span style={{ fontSize: "8px" }}>●</span> Reports
          </button>
          <button
            onClick={() => scrollToSection("activity-logs")}
            style={{
              textAlign: "left",
              padding: "0.4rem 0.6rem",
              border: "none",
              background: "none",
              cursor: "pointer",
              borderRadius: "3px",
              fontSize: "0.85rem",
              color: "#555",
              transition: "all 0.2s",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = "rgba(0, 0, 0, 0.04)";
              e.target.style.color = "#000";
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = "transparent";
              e.target.style.color = "#555";
            }}
          >
            <span style={{ fontSize: "8px" }}>●</span> Logs
          </button>
        </div>
      </div>

      {/* Pending Review Queue */}
      <section id="pending-review" className="admin-panel-section">
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
                {comment.topic_title && (
                  <div style={{ marginBottom: "8px", fontSize: "0.85rem" }}>
                    <a
                      href={`/topics/${comment.topic_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        color: "#0066cc",
                        textDecoration: "none",
                        fontWeight: "500",
                      }}
                      onMouseEnter={(e) => e.target.style.textDecoration = "underline"}
                      onMouseLeave={(e) => e.target.style.textDecoration = "none"}
                    >
                      Source: {comment.topic_title}
                    </a>
                  </div>
                )}
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
                    onClick={() => openRejectModal(comment.id)}
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Approved Comments */}
      <section id="approved" className="admin-panel-section">
        <div className="admin-section-header">
          <h2>Approved</h2>
          <span className="count-badge">{approved.length}</span>
        </div>
        {approved.length === 0 ? (
          <p className="empty-state">No approved comments</p>
        ) : (
          <div className="admin-cards">
            {approved.map((comment) => (
              <div key={comment.id} className="admin-comment-card">
                <div className="admin-comment-header">
                  <div className="admin-comment-meta">
                    <strong className="comment-author">
                      {comment.author_name}
                    </strong>
                    <span className="comment-id">#{comment.id}</span>
                  </div>
                  <span className="comment-time">
                    {new Date(comment.updated_at).toLocaleString()}
                  </span>
                </div>
                {comment.topic_title && (
                  <div style={{ marginBottom: "8px", fontSize: "0.85rem" }}>
                    <a
                      href={`/topics/${comment.topic_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        color: "#0066cc",
                        textDecoration: "none",
                        fontWeight: "500",
                      }}
                      onMouseEnter={(e) => e.target.style.textDecoration = "underline"}
                      onMouseLeave={(e) => e.target.style.textDecoration = "none"}
                    >
                      Source: {comment.topic_title}
                    </a>
                  </div>
                )}
                <p className="admin-comment-text">{comment.text}</p>
                {comment.is_hidden && (
                  <div
                    style={{
                      padding: "8px 12px",
                      backgroundColor: "#fff3cd",
                      borderLeft: "3px solid #ffc107",
                      marginBottom: "12px",
                      fontSize: "0.9rem",
                    }}
                  >
                    Currently hidden from public view
                  </div>
                )}
                <div className="admin-comment-actions">
                  {comment.is_hidden ? (
                    <button
                      className="admin-btn btn-approve"
                      onClick={() => act(comment.id, "restore")}
                    >
                      Restore
                    </button>
                  ) : (
                    <button
                      className="admin-btn btn-hide"
                      onClick={() => act(comment.id, "hide")}
                    >
                      Hide
                    </button>
                  )}
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

      {/* Rejected Comments */}
      <section id="rejected" className="admin-panel-section">
        <div className="admin-section-header">
          <h2>Rejected</h2>
          <span className="count-badge">{rejected.length}</span>
        </div>
        {rejected.length === 0 ? (
          <p className="empty-state">No rejected comments</p>
        ) : (
          <div className="admin-cards">
            {rejected.map((comment) => (
              <div key={comment.id} className="admin-comment-card">
                <div className="admin-comment-header">
                  <div className="admin-comment-meta">
                    <strong className="comment-author">
                      {comment.author_name}
                    </strong>
                    <span className="comment-id">#{comment.id}</span>
                  </div>
                  <span className="comment-time">
                    {new Date(comment.updated_at).toLocaleString()}
                  </span>
                </div>
                {comment.topic_title && (
                  <div style={{ marginBottom: "8px", fontSize: "0.85rem" }}>
                    <a
                      href={`/topics/${comment.topic_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        color: "#0066cc",
                        textDecoration: "none",
                        fontWeight: "500",
                      }}
                      onMouseEnter={(e) => e.target.style.textDecoration = "underline"}
                      onMouseLeave={(e) => e.target.style.textDecoration = "none"}
                    >
                      Source: {comment.topic_title}
                    </a>
                  </div>
                )}
                <p className="admin-comment-text">{comment.text}</p>
                {comment.moderation_reason && (
                  <div
                    style={{
                      fontSize: "0.85rem",
                      color: "#666",
                      marginBottom: "12px",
                    }}
                  >
                    <strong>Reason:</strong> {comment.moderation_reason}
                  </div>
                )}
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
      <section id="reported" className="admin-panel-section">
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
      <section id="activity-logs" className="admin-panel-section">
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

      {/* Reject Reason Modal */}
      {showRejectModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              backgroundColor: "white",
              padding: "2rem",
              borderRadius: "8px",
              boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
              maxWidth: "500px",
              width: "90%",
            }}
          >
            <h2 style={{ marginTop: 0, marginBottom: "1rem" }}>
              Provide Rejection Reason
            </h2>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Enter the reason for rejection... (optional)"
              style={{
                width: "100%",
                minHeight: "100px",
                padding: "10px",
                borderRadius: "4px",
                border: "1px solid #ddd",
                fontFamily: "inherit",
                fontSize: "0.95rem",
                boxSizing: "border-box",
              }}
            />
            <div
              style={{
                display: "flex",
                gap: "10px",
                marginTop: "1.5rem",
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={closeRejectModal}
                style={{
                  padding: "10px 20px",
                  borderRadius: "4px",
                  border: "1px solid #ddd",
                  backgroundColor: "#f5f5f5",
                  cursor: "pointer",
                  fontSize: "0.95rem",
                }}
              >
                Cancel
              </button>
              <button
                onClick={submitReject}
                style={{
                  padding: "10px 20px",
                  borderRadius: "4px",
                  border: "none",
                  backgroundColor: "#dc3545",
                  color: "white",
                  cursor: "pointer",
                  fontSize: "0.95rem",
                }}
              >
                Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
