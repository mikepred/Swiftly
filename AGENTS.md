# Agent Instructions

Welcome, Agents (Jules, Hermes)! Here are the specific directives for modifying this repository:

- **Package Manager:** Use ONLY `npm` with `package-lock.json`. Do NOT use `pnpm`, `yarn`, or alternative lockfiles.
- **Workflow / Roles:** Jules implements, Hermes coordinates/reviews, human approves merges. Do not auto-merge. Work on one user-approved task/branch/PR at a time.
- **Scope Limitations:** Limit your work STRICTLY to requested files and the stated scope. Do NOT introduce unrequested changes (e.g. to UI, backend logic, architecture, dependencies, schemas, or auth mechanisms). Read files before editing.
- **Durable Lessons (Optional):** If needed, store optional durable lessons/context in `.jules/`. Do not use this as a general scratchpad or journal.
- **Testing Constraints:** Use mocked configurations or narrow setup tests. Do not use real bookmark data/secrets, call authenticated provider/X APIs during tests, or launch/attach to local/personal browsers. If screenshots are needed, use an approved isolated cloud browser.
- **Execution & Validation:** Run `npm test`, `npm run lint`, `npx --no-install tsc --noEmit`, and `npm run build`. You must report actual failures without suppressing them. For pre-existing failures requiring application edits, you must seek scope approval from the user before fixing them. The user values smallest useful changes—no open-ended daily polishing.
