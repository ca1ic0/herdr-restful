import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";
import { api } from "../api/client";
import {
  applySnapshot,
  initialState,
  reducer,
  setConnection,
  type LogEntry,
  type SessionState,
} from "../store/session";
import type { HerdrEventEnvelope } from "../types/herdr";

export type AppAction =
  | { type: "event"; event: HerdrEventEnvelope }
  | { type: "snapshot"; state: SessionState }
  | { type: "connected"; connected: boolean }
  | { type: "select-pane"; paneId: string | null }
  | { type: "select-tab"; tabId: string | null }
  | { type: "select-workspace"; workspaceId: string | null };

function appReducer(state: SessionState, action: AppAction): SessionState {
  switch (action.type) {
    case "event":
      return reducer(state, action.event);
    case "snapshot":
      return action.state;
    case "connected":
      return setConnection(state, action.connected);
    case "select-pane":
      return { ...state, selectedPaneId: action.paneId };
    case "select-tab":
      return { ...state, focusedTabId: action.tabId, selectedPaneId: null };
    case "select-workspace":
      return {
        ...state,
        focusedWorkspaceId: action.workspaceId,
        focusedTabId: null,
        selectedPaneId: null,
      };
    default:
      return state;
  }
}

export interface UseHerdrSession {
  state: SessionState;
  dispatch: React.Dispatch<AppAction>;
  refresh: () => Promise<void>;
  logs: LogEntry[];
  error: string | null;
}

export function useHerdrSession(): UseHerdrSession {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const errorRef = useRef<string | null>(null);
  const [, force] = useReducer((x: number) => x + 1, 0);
  const sourceRef = useRef<EventSource | null>(null);

  const refresh = useCallback(async () => {
    try {
      const snap = await api.snapshot();
      errorRef.current = null;
      dispatch({ type: "snapshot", state: applySnapshot(initialState, snap.snapshot) });
    } catch (err) {
      errorRef.current = err instanceof Error ? err.message : String(err);
      force();
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (closed) return;
      const source = new EventSource("/api/v1/events");
      sourceRef.current = source;

      source.onopen = () => dispatch({ type: "connected", connected: true });

      source.onerror = () => {
        dispatch({ type: "connected", connected: false });
        source.close();
        if (!closed) retry = setTimeout(connect, 2000);
      };

      const handle = (ev: MessageEvent<string>) => {
        try {
          const envelope = JSON.parse(ev.data) as HerdrEventEnvelope;
          dispatch({ type: "event", event: envelope });
        } catch {
          /* ignore malformed frames */
        }
      };

      for (const name of [
        "workspace_created",
        "workspace_updated",
        "workspace_metadata_updated",
        "workspace_closed",
        "workspace_renamed",
        "workspace_moved",
        "workspace_reordered",
        "workspace_focused",
        "worktree_created",
        "worktree_opened",
        "worktree_removed",
        "tab_created",
        "tab_closed",
        "tab_focused",
        "tab_renamed",
        "tab_moved",
        "pane_created",
        "pane_closed",
        "pane_updated",
        "pane_focused",
        "pane_moved",
        "pane_output_changed",
        "pane_exited",
        "pane_agent_detected",
        "pane_agent_status_changed",
        "layout_updated",
      ]) {
        source.addEventListener(name, handle as EventListener);
      }
    };

    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      sourceRef.current?.close();
    };
  }, []);

  return useMemo(
    () => ({
      state,
      dispatch,
      refresh,
      logs: state.eventLog,
      error: errorRef.current,
    }),
    [state, refresh],
  );
}
