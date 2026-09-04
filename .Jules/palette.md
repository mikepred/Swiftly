## 2025-05-18 - Theme Toggle ARIA & State Sync
**Learning:** Icon-only theme toggles need explicit `aria-label` and `aria-pressed` states for screen readers, as well as `focus-visible` ring styles for keyboard navigation. Reading DOM class state in `useState` lazy initializer avoids React synchronous `setState` in `useEffect` warnings/errors.
**Action:** Always provide `aria-label`, `aria-pressed`, and lazy state initialization for theme and state toggle buttons.
