# Frontend Reference Notes

## Source reviewed

The latest visual target was the provided screenshot: a clean white sidebar on the left and a light, minimal main panel with a large circular avatar, centered title, concise product explanation, and fixed lower input.

## What was borrowed

Headline Booster AI borrows visual ideas only:

- a white left sidebar;
- a strong brand block at the top;
- a large brown `+ Nuevo titular` button;
- a `HISTORIAL LOCAL` area;
- a centered hero with circular avatar;
- a clean bottom composer with one text field and a send button;
- generous spacing, soft cards, and a warm brown accent.

## What was not copied

The app does not copy unrelated product logic. It does not include:

- example chips under the hero;
- model selector controls;
- context fields;
- usage counters;
- status text such as `disponible`;
- topbar navigation;
- backend session history.

## How it is used in this app

The visual layer now lives entirely in `index.html`. The file contains the markup, styles, and JavaScript needed for the interface. It calls `fetch('/api/improve_headline')` and stores user sessions in `localStorage` so each browser has its own private local history.

## Responsive strategy

The layout now follows a compact app-shell pattern: a fixed 320px desktop sidebar, a scrollable message column, bubble-style user/assistant messages, a fixed composer offset by the sidebar, and mobile rules that hide the sidebar and keep the composer full-width. This avoids the oversized spacing from the earlier full-page hero implementation.
