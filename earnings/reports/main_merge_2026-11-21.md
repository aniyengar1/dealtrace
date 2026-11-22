# Main merge validation — November 21, 2026

Announcement commit: `0050ff2`. It includes **only IOT, OKTA and S** and states that evidence was retrieved2026-11-17 06:28UTC during pre-lock refresh, already referenced by existing locks, committed late2026-11-21; key reordering is formatting-only and no prior version altered. Its message lists all three evidence IDs. CRM remains unstaged.

Merged the exact approved local main `06dc7592dbc8ae3d27276f245b7c02b67aebd2d7` into earnings, using `--no-ff --no-commit` to inspect before committing. **Zero conflicts and zero manual conflict resolutions.** No data-logic conflict occurred. Incoming data-query changes from main were accepted without modification, not rewritten.

## Conservative integration checks

- Main's root layout, global CSS, HeroMedia and deal-page directory match the approved main commit byte-for-byte.
- Earnings' Crosscheck page/library directories, earnings SQL, protected prediction code/data and migrations are unchanged from the pre-merge earnings commit. No production migration was executed.
- `NavBar.tsx`: retained the Crosscheck desktop/mobile link; otherwise main's navigation implementation.
- `next.config.ts`: retained `globals.css`-only Tailwind loading and native CSS-module identity. No wildcard CSS loader was reintroduced.
- `postcss.config.mjs`: retained the standard Tailwind PostCSS plugin.
- `package.json` / `package-lock.json`: retained the pinned PostCSS dependency and matching lock entries. All other dependencies agree with the incoming main package. Default build script remains `next build`.
- These five shared integration files match the pre-merge earnings versions. No dependency installation, model/provider call, inference, fresh extraction evaluation, or credential inspection occurred.

## Checks

- Typecheck (`tsc --noEmit`): passed.
- Lint (`npm run lint`): passed.
- Frontend (`npm test`): **69 passed,9 files**.
- Full Python suite: **821 passed,3 skipped,2 preserved expected failures**. It ran in the existing temporary PostgreSQL cluster at port65439, with DATABASE_URL assigned only to a scratch database and a psycopg guard rejecting non-scratch connections. Snapshot role/SQL enforcement tests were included. Database migrations and test ledger inserts occurred only inside this scratch cluster, never the live database.
- `npm run build -- --webpack`: passed compilation, TypeScript, static generation and route generation, including Crosscheck and the new incoming deal/stats export routes.
- Default Turbopack was not retried or represented as passed. The previously documented managed-worker-port issue remains separate. Visual compatibility remains unverified; no browser automation was used.

No live-ledger write, lock, backdating, push or deployment. Published prediction JSON is byte-identical to the pre-merge version. Old checkpoint tags were not moved. Detailed evidence: [validation](../validation/main_merge_2026-11-21.json).
