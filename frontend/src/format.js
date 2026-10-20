const time = (d) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

// "Today, 09:15 AM", "Yesterday, 04:30 PM" or "16 Sep 2026, 11:00 AM"
export function formatDateTime(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (sameDay(date, today)) return `Today, ${time(date)}`;
  if (sameDay(date, yesterday)) return `Yesterday, ${time(date)}`;
  return `${formatDate(iso)}, ${time(date)}`;
}

export function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}

export const percent = (value) => `${Math.round(value * 100)}%`;
export const score = (value) => Number(value).toFixed(2);
export const formatRationale = (rationale) => rationale.replace(/ \(C[123]\)/g, "");
