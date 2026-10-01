# Resolve frontend

A single-page portfolio demo served directly by FastAPI. No npm, bundler, UI framework, or frontend credentials.

- `index.html`: semantic page, complaint form, graph, result panels, and project explanation.
- `assets/styles.css`: mint/charcoal design tokens, responsive layout, light/dark themes, transform-only floating motion and reduced-motion support.
- `assets/app.js`: sample inputs, streaming fetch, state rendering, clarification, saved requests, and export.
- `assets/graph.js`: renders real backend node events and inspected outputs. There is no fake progress timer.
- `assets/speech.js`: browser-native speech recognition, start/stop, interim preview, editable final text, permission/network errors, and unsupported-browser fallback.
- `assets/theme.js`: applies a saved color preference before paint. Complaint data is not saved to browser storage.

Run `./scripts/dev` from the repository root. Both the website and API use the same origin, including in Docker.

## Browser smoke checks

1. Run all four samples. Expect `respond`, `clarify`, `compliance_escalation`, and `billing_review` respectively.
2. Answer the missing-account question with `ACC1023`. Confirm the graph resumes at validation and the original request ID stays the same.
3. Select graph nodes and inspect actual output; compare the Activity tab with the final route. Live node timings are processing time; the result timing includes the network round trip.
4. Reload a request URL, reopen by ID, download JSON, and copy the output.
5. On a supported browser and HTTPS/localhost, clear the input, dictate a synthetic complaint, stop, edit it, and submit. Check microphone denial and unsupported browsers leave typing usable. Speech audio may leave the device through the browser provider, separately from our text-only API.
6. Check keyboard tab navigation, result-tab arrow keys, mobile graph scrolling, both themes, Pause motion, and the OS reduced-motion setting.
7. Stop the API or interrupt a run and confirm an honest error state, not a fabricated completed graph.

## Assets and design

The design-taste-frontend and Motion skills informed the editorial layout, custom loop artwork, restrained floating labels, explicit states, and accessibility. The backend remains in Python; the redesign adds no frontend dependency.

- Space Grotesk: self-hosted variable font from the Google Fonts repository, SIL Open Font License in `assets/FONT-LICENSE.txt`.
- Tabler outline icons: MIT license in `assets/ICONS-LICENSE.txt`.
- `assets/workflow-sculpture.jpg`: custom image generated with the built-in image generation tool, then resized and JPEG-compressed for the page. Art direction: a pale mint translucent glass ribbon forming a continuous sculptural loop, silver and glass spheres floating around it, soft studio shadows, warm off-white background, clean premium product photography, no text or logos. The original generation prompt is recorded in the generation tool history; this is the implementation art-direction summary.

No remote font or image request is needed to render the page. Speech recognition and optional backend LLM calls are separate services, enabled only by their respective user/configuration choices.
