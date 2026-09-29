import type { TabInfo } from "../types/herdr";

export function TabBar({
  tabs,
  focusedId,
  onSelect,
  onClose,
}: {
  tabs: TabInfo[];
  focusedId: string | null;
  onSelect: (id: string) => void;
  onClose: (id: string) => void;
}) {
  if (tabs.length === 0) return null;
  return (
    <div className="tabbar">
      {tabs.map((tab) => (
        <div
          key={tab.tab_id}
          className={`tab-item ${tab.tab_id === focusedId ? "active" : ""}`}
          onClick={() => onSelect(tab.tab_id)}
        >
          <span>
            <span className="meta">{tab.number}</span> {tab.label}
          </span>
          <button
            title="close tab"
            onClick={(e) => {
              e.stopPropagation();
              onClose(tab.tab_id);
            }}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
