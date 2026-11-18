# Predictions stylesheet delivery fix

Reproduced on the local copy-only preview, no browser automation or ledger connection.

## Root cause

The CSS module was imported correctly. Both global and predictions CSS assets returned200/text-css **before** the fix; this was not a404. However, the HTML had no class attributes on the page/cards/methods/leaders. `next.config.ts` applied the Tailwind Turbopack loader to every`*.css`, with `as:'*.css'`. That resource rewrite treated `predictions.module.css` as global CSS (`.module.css.css` in the emitted source), losing its CSS-module export map. React received undefined class names and omitted them. Existing unit-test CSS mocks and content-only HTTP checks had missed this actual bundler failure.

Tailwind4 source scanning is automatic from the app root; there are no restrictive content globs excluding these files. Global utilities are present. Changing scanner globs would not repair missing native CSS-module exports.

## Fix and verification

- Scope the existing Tailwind entry loader to `globals.css` only. Next handles module scoping/exports natively. No dependency, PostCSS, global stylesheet, data, scoring or ledger change.
- Next automatically restarted on the config edit. No cache deletion was necessary; the loader configuration, not stale cache, was the root cause. Other local dev processes must also pick up the config change.
- HTML now includes `predictions-module__VP_K2G__page`, `...__method` and `...__leading`, with matching selectors in the delivered module CSS. All8 method rows and10 displayed leaders/ties verified.
- Global CSS200,35306 bytes; native module CSS200,6380 bytes. Global stylesheet SHA256 is unchanged before/after: `4c3ee6d5d205a18c4c18be49d4c3cce819553d50babbab8e7a3180da69a594a4`.
- Explicit middle-dot separators make the stats readable even without styles: `8 locked predictions · 4 companies · 0 reviewed scores`.
- Guidance label has a colon, literal space and styled label margin: `Locked management range: $813M–$817M`.
- All33 frontend tests passed; TypeScript and scoped ESLint passed.

Actual HTTP evidence: `../validation/predictions_css_delivery_2026-11-18.json`.

Reproduce against a running local server:

```sh
node apps/web/scripts/verify-predictions-css.mjs http://127.0.0.1:3108
```

This checks the real HTML and stylesheet responses, not CSS-module mocks: asset status/type, emitted class attributes, matching selectors, black background rule, Tailwind utility availability and spacing. No browser automation, source DB fallback or ledger access.

Preview: http://127.0.0.1:3108/crosscheck/predictions . Reload to get the current HTML/CSS. Pre-existing announcement edits remain separate and unstaged. No merge, push or deployment.
