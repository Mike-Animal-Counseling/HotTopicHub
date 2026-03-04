const API_BASE = "http://127.0.0.1:8000";

// Read admin token from localStorage
function getAdminToken() {
  return localStorage.getItem("ADMIN_TOKEN") || "";
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = typeof payload === "object" ? payload.detail : payload;
    throw new Error(detail || "Request failed");
  }

  return payload;
}

export const api = {
  getTopics: (dateKey) =>
    request(`/api/topics/trending${dateKey ? `?date=${dateKey}` : ""}`),
  getTopicHistory: () => request("/api/topics/history"),
  getTopic: (topicId) => request(`/api/topics/${topicId}`),
  seedTopics: (dateKey) =>
    request(`/api/topics/seed-daily${dateKey ? `?date=${dateKey}` : ""}`, {
      method: "POST",
    }),
  likeTopic: (topicId, userIdentifier) =>
    request(`/api/topics/${topicId}/like`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_identifier: userIdentifier }),
    }),
  unlikeTopic: (topicId, userIdentifier) =>
    request(
      `/api/topics/${topicId}/like?user_identifier=${encodeURIComponent(userIdentifier)}`,
      {
        method: "DELETE",
      },
    ),
  getComments: (topicId) => request(`/api/topics/${topicId}/comments`),
  getRankedComments: (topicId) =>
    request(`/api/topics/${topicId}/comments/highlights`),
  createComment: (topicId, payload) =>
    request(`/api/topics/${topicId}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  likeComment: (commentId, userIdentifier) =>
    request(`/api/comments/${commentId}/like`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_identifier: userIdentifier }),
    }),
  unlikeComment: (commentId, userIdentifier) =>
    request(
      `/api/comments/${commentId}/like?user_identifier=${encodeURIComponent(userIdentifier)}`,
      {
        method: "DELETE",
      },
    ),
  reportComment: (commentId, payload) =>
    request(`/api/comments/${commentId}/report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  getModerationQueue: () => {
    const token = getAdminToken();
    return request("/api/admin/moderation/queue", {
      headers: { "X-ADMIN-TOKEN": token },
    });
  },
  moderateComment: (commentId, payload) => {
    const token = getAdminToken();
    return request(`/api/admin/comments/${commentId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-ADMIN-TOKEN": token,
      },
      body: JSON.stringify(payload),
    });
  },
  getReports: (status = "open") => {
    const token = getAdminToken();
    return request(`/api/admin/reports?status=${encodeURIComponent(status)}`, {
      headers: { "X-ADMIN-TOKEN": token },
    });
  },
  getModerationLogs: () => {
    const token = getAdminToken();
    return request("/api/admin/moderation/logs", {
      headers: { "X-ADMIN-TOKEN": token },
    });
  },
  getProcessedComments: () => {
    const token = getAdminToken();
    return request("/api/admin/moderation/processed", {
      headers: { "X-ADMIN-TOKEN": token },
    });
  },
  reopenComment: (commentId) => {
    const token = getAdminToken();
    return request(`/api/admin/comments/${commentId}/reopen`, {
      method: "POST",
      headers: { "X-ADMIN-TOKEN": token },
    });
  },
};

// Token management exports
export function setAdminToken(token) {
  if (token) {
    localStorage.setItem("ADMIN_TOKEN", token);
  } else {
    localStorage.removeItem("ADMIN_TOKEN");
  }
}

export function hasAdminToken() {
  return !!localStorage.getItem("ADMIN_TOKEN");
}

export function getStoredAdminToken() {
  return localStorage.getItem("ADMIN_TOKEN") || "";
}
