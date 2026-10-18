import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { api, auth } = vi.hoisted(() => ({
  api: Object.fromEntries([
    "getDailyTopSignals", "getDailySignalHistory", "getDailySignalsForDate",
    "getTopic", "getComments", "getRankedComments", "createComment",
    "likeTopic", "likeComment", "reportComment", "recordTopicSourceClick",
    "getRealtimeFeedStream", "refreshRealtimeFeed", "getModerationQueue",
    "getReports", "getModerationLogs", "getProcessedComments",
  ].map((name) => [name, vi.fn()])),
  auth: { token: "" },
}));
vi.mock("../src/api", () => ({
  api,
  hasAdminToken: () => Boolean(auth.token),
  setAdminToken: (token) => { auth.token = token; },
}));

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

async function settle(request, value, failed = false) {
  await act(async () => { request[failed ? "reject" : "resolve"](value); });
}

function mount(Page, route, entry) {
  const router = createMemoryRouter([{ path: route, element: <Page /> }], {
    initialEntries: [entry],
  });
  const view = render(<RouterProvider router={router} />);
  return { ...view, router };
}

function topic(id, title) {
  return { id, title, content_type: "discussion", sources: [], likes_count: 0, comments_count: 0 };
}

const days = [
  { date_key: "2026-10-18", topics_count: 1 },
  { date_key: "2026-10-17", topics_count: 1 },
];

beforeEach(() => {
  vi.resetModules();
  for (const mock of Object.values(api)) mock.mockReset();
  auth.token = "";
  api.getDailySignalHistory.mockResolvedValue({ items: days });
  api.getComments.mockResolvedValue({ items: [] });
  api.getRankedComments.mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("daily signals", () => {
  it("shows loading until data arrives and preserves cached content when revalidation fails", async () => {
    const { default: Page } = await import("../src/pages/TopicsPage.jsx");
    const request = deferred();
    api.getDailyTopSignals.mockReturnValueOnce(request.promise);
    const first = mount(Page, "/topics", "/topics");
    expect(screen.getByText("Loading daily top signals...")).toBeTruthy();
    await settle(request, { items: [topic(1, "Daily result")] });
    expect(screen.getByRole("button", { name: "Daily result" })).toBeTruthy();
    first.unmount();
    api.getDailyTopSignals.mockRejectedValueOnce(new Error("Daily refresh failed"));
    mount(Page, "/topics", "/topics");
    expect(screen.getByRole("button", { name: "Daily result" })).toBeTruthy();
    expect(await screen.findByText("Daily refresh failed")).toBeTruthy();
    expect(screen.queryByText("Loading daily top signals...")).toBeNull();
  });

  it("does not populate the cache from a request completed after leaving the page", async () => {
    const { default: Page } = await import("../src/pages/TopicsPage.jsx");
    const old = deferred();
    api.getDailyTopSignals.mockReturnValueOnce(old.promise);
    mount(Page, "/topics", "/topics").unmount();
    await settle(old, { items: [topic(1, "Obsolete result")] });
    api.getDailyTopSignals.mockReturnValueOnce(new Promise(() => {}));
    mount(Page, "/topics", "/topics");
    expect(screen.queryByRole("button", { name: "Obsolete result" })).toBeNull();
    expect(screen.getByText("Loading daily top signals...")).toBeTruthy();
  });
});

describe("history navigation", () => {
  it("selects the newest day in the URL and displays its topics", async () => {
    const { default: Page } = await import("../src/pages/TopicsHistoryPage.jsx");
    api.getDailySignalsForDate.mockResolvedValue({ items: [topic(1, "Newest archive")] });
    const { router } = mount(Page, "/topics/history", "/topics/history?source=menu");
    expect(await screen.findByRole("button", { name: "Newest archive" })).toBeTruthy();
    expect(router.state.location.search).toBe("?source=menu&date=2026-10-18");
  });

  it("keeps the selected day when responses arrive out of order and shows cached results immediately", async () => {
    const { default: Page } = await import("../src/pages/TopicsHistoryPage.jsx");
    const older = deferred();
    const newer = deferred();
    api.getDailySignalsForDate.mockImplementation((date) => date === days[0].date_key ? older.promise : newer.promise);
    const { router } = mount(Page, "/topics/history", "/topics/history?date=2026-10-18");
    expect(await screen.findByText("Loading archived topics...")).toBeTruthy();
    await act(async () => { await router.navigate("/topics/history?date=2026-10-17"); });
    await settle(newer, { items: [topic(2, "Selected archive")] });
    await settle(older, { items: [topic(1, "Obsolete archive")] });
    expect(screen.getByRole("button", { name: "Selected archive" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Obsolete archive" })).toBeNull();
    api.getDailySignalsForDate.mockReturnValue(new Promise(() => {}));
    await act(async () => { await router.navigate("/topics/history?date=2026-10-18"); });
    expect(screen.queryByRole("button", { name: "Selected archive" })).toBeNull();
    await act(async () => { await router.navigate("/topics/history?date=2026-10-17"); });
    expect(screen.getByRole("button", { name: "Selected archive" })).toBeTruthy();
    expect(screen.queryByText("Loading archived topics...")).toBeNull();
  });

  it("does not clear a day request error when the independent history request succeeds", async () => {
    const { default: Page } = await import("../src/pages/TopicsHistoryPage.jsx");
    const history = deferred();
    api.getDailySignalHistory.mockReturnValue(history.promise);
    api.getDailySignalsForDate.mockRejectedValue(new Error("Archive unavailable"));
    const { router } = mount(Page, "/topics/history", "/topics/history?date=2026-10-18");
    expect(await screen.findByText("Archive unavailable")).toBeTruthy();
    await settle(history, { items: days });
    expect(screen.getByText("Archive unavailable")).toBeTruthy();
    expect(screen.queryByText("Loading archived topics...")).toBeNull();
    api.getDailySignalsForDate.mockResolvedValue({ items: [topic(2, "Working archive")] });
    await act(async () => { await router.navigate("/topics/history?date=2026-10-17"); });
    expect(await screen.findByRole("button", { name: "Working archive" })).toBeTruthy();
    expect(screen.queryByText("Archive unavailable")).toBeNull();
  });
});

describe("topic routes", () => {
  it.each(["invalid", "0", "1.5", "Infinity"])("rejects invalid topic id %s without requesting it", async (id) => {
    const { default: Page } = await import("../src/pages/TopicDetailPage.jsx");
    mount(Page, "/topics/:topicId", `/topics/${id}`);
    expect(screen.getByText("Invalid topic id")).toBeTruthy();
    expect(api.getTopic).not.toHaveBeenCalled();
    expect(api.getComments).not.toHaveBeenCalled();
  });

  it("resets the page and comment draft on a route change and ignores the abandoned request", async () => {
    const { default: Page } = await import("../src/pages/TopicDetailPage.jsx");
    const stale = deferred();
    const latest = deferred();
    api.getTopic.mockResolvedValueOnce(topic(1, "First topic"))
      .mockReturnValueOnce(stale.promise).mockReturnValueOnce(latest.promise);
    const { router } = mount(Page, "/topics/:topicId", "/topics/1");
    expect(await screen.findByRole("heading", { name: "First topic" })).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("Share your thoughts..."), { target: { value: "First draft" } });
    await act(async () => { await router.navigate("/topics/2"); });
    expect(screen.getByText("Loading topic...")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "First topic" })).toBeNull();
    await act(async () => { await router.navigate("/topics/3"); });
    await settle(latest, topic(3, "Current topic"));
    await settle(stale, topic(2, "Abandoned topic"));
    expect(screen.getByRole("heading", { name: "Current topic" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Abandoned topic" })).toBeNull();
    expect(screen.getByPlaceholderText("Share your thoughts...").value).toBe("");
    expect(api.getRankedComments.mock.calls.map(([id]) => id)).toEqual([1, 3]);
  });

  it("renders the topic when optional highlights fail, and reports a failed topic request", async () => {
    const { default: Page } = await import("../src/pages/TopicDetailPage.jsx");
    api.getTopic.mockResolvedValueOnce(topic(1, "Available topic")).mockRejectedValueOnce(new Error("Topic not found"));
    api.getRankedComments.mockRejectedValue(new Error("Highlights unavailable"));
    const { router } = mount(Page, "/topics/:topicId", "/topics/1");
    expect(await screen.findByRole("heading", { name: "Available topic" })).toBeTruthy();
    await act(async () => { await router.navigate("/topics/2"); });
    expect(await screen.findByText("Topic not found")).toBeTruthy();
    expect(screen.queryByText("Loading topic...")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Available topic" })).toBeNull();
  });
});

describe("live feed", () => {
  it("keeps polled updates pending until the user adopts them", async () => {
    const { default: Page } = await import("../src/pages/RealtimeFeedPage.jsx");
    vi.useFakeTimers();
    api.getRealtimeFeedStream.mockResolvedValueOnce({ items: [topic(1, "Visible feed item")] });
    await act(async () => { mount(Page, "/feed", "/feed"); });
    expect(screen.getByRole("button", { name: "Visible feed item" })).toBeTruthy();
    api.getRealtimeFeedStream.mockResolvedValueOnce({ items: [topic(2, "New feed item"), topic(1, "Visible feed item")] });
    await act(async () => { await vi.advanceTimersByTimeAsync(45000); });
    expect(screen.getByText("1 new items")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "New feed item" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Show latest" }));
    expect(screen.getByRole("button", { name: "New feed item" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Show latest" })).toBeNull();
  });

  it("does not replace an explicit refresh with an older in-flight initial response", async () => {
    const { default: Page } = await import("../src/pages/RealtimeFeedPage.jsx");
    const old = deferred();
    const latest = deferred();
    api.getRealtimeFeedStream.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise);
    mount(Page, "/feed", "/feed");
    fireEvent.click(screen.getByRole("button", { name: "Refresh Feed" }));
    await settle(latest, { items: [topic(2, "Refreshed item")] });
    await settle(old, { items: [topic(1, "Stale feed item")] });
    expect(screen.getByRole("button", { name: "Refreshed item" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Stale feed item" })).toBeNull();
    expect(screen.getByRole("button", { name: "Refresh Feed" }).disabled).toBe(false);
  });
});

describe("moderation lifecycle", () => {
  it("shows initial loading and discards a response that finishes after logout", async () => {
    const { default: Page } = await import("../src/pages/AdminModerationPage.jsx");
    auth.token = "test-token";
    const queue = deferred();
    api.getModerationQueue.mockReturnValueOnce(queue.promise);
    api.getReports.mockResolvedValue([]);
    api.getModerationLogs.mockResolvedValue([]);
    api.getProcessedComments.mockResolvedValue([]);
    const first = mount(Page, "/admin", "/admin");
    expect(screen.getByText("Loading...")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Logout" }));
    await settle(queue, [{ id: 1, text: "Private pending comment", author_name: "Reviewer" }]);
    expect(screen.getByPlaceholderText("Enter admin token")).toBeTruthy();
    first.unmount();
    auth.token = "another-test-token";
    api.getModerationQueue.mockReturnValueOnce(new Promise(() => {}));
    mount(Page, "/admin", "/admin");
    expect(screen.queryByText("Private pending comment")).toBeNull();
    expect(screen.getByText("Loading...")).toBeTruthy();
  });
});
