Below is a **clean, opinionated PRD** for exactly what you asked: a tiny, boring, sharp-edged web server that serves **HTMX + Tailwind via CDN**, with **zero build system**, **zero Node**, **zero bundlers**, and no clever nonsense.

This is infrastructure as a hammer, not a Swiss Army chainsaw.

---

# PRD-01-minimal-htmx-server

## 1. Purpose

Build a **small, fast web server** that serves HTML pages enhanced with **HTMX** and styled with **Tailwind CSS**, using **CDN-hosted assets only**.

No build step.
No Node.js.
No package managers.
No transpilation.
No client-side framework.

The system should encourage **server-driven UI**, progressive enhancement, and boring reliability.

---

## 2. Non-Goals (Explicit)

This system will **not**:

* Use Node.js, npm, yarn, pnpm
* Use a Tailwind build pipeline
* Use React, Vue, Svelte, or similar
* Implement client-side routing
* Bundle or minify assets
* Solve authentication beyond basic placeholders
* Become a framework

If someone tries to “improve” this by adding a build step, they are doing it wrong.

---

## 3. Target Use Cases

* Internal tools
* Admin panels
* MVPs
* CRUD-heavy apps
* AI dashboards
* Prototypes that accidentally become production
* People who like HTML and sleep at night

---

## 4. Tech Stack

### Server

* Language: **Python**
* Framework: **FastAPI** or **Flask**
* Server: **Uvicorn** (if FastAPI)

Rationale: minimal ceremony, explicit control, boring correctness.

### Frontend

* HTML served directly from server templates
* **HTMX via CDN**
* **Tailwind CSS via CDN**
* Optional: Alpine.js via CDN (explicitly optional)

No JS build pipeline.

---

## 5. Architecture Overview

```
Client (Browser)
  |
  |  HTTP / HTML / HTMX
  v
Web Server
  ├── Routes (GET/POST)
  ├── HTML Templates
  ├── Partial Templates (HTMX targets)
  └── Static Assets (optional)
```

HTMX handles interaction.
The server owns state.
HTML is the API.

---

## 6. Directory Structure

```
/app
  /templates
    base.html
    index.html
    partials/
      list.html
      form.html
  /static
    styles.css   (optional, hand-written)
  main.py
```

No `dist/`, no `node_modules/`, no lockfiles.

---

## 7. HTML & Styling Strategy

### Tailwind

* Use **Tailwind CDN** (`https://cdn.tailwindcss.com`)
* Accept limitations (no custom build-time purge)
* Prefer utility classes over custom CSS
* Optional: small handwritten CSS file for edge cases

### HTML

* Server-rendered templates
* Semantic HTML first
* Progressive enhancement via HTMX attributes

---

## 8. Interaction Model (HTMX)

All interactivity must:

* Be driven by standard HTML elements
* Use `hx-get`, `hx-post`, `hx-target`, `hx-swap`
* Return **HTML fragments**, not JSON (unless justified)

Example patterns:

* Form submits → partial HTML response
* Buttons → server-rendered updates
* Polling → `hx-trigger="every 5s"`

JavaScript is a last resort.

---

## 9. Routing Rules

* `GET /` → full page
* `GET /partials/*` → HTML fragments
* `POST /actions/*` → state-changing operations
* HTMX requests must be distinguishable via headers

No SPA-style routing.

---

## 10. Performance Requirements

* Cold start < 200ms
* No blocking client-side JS execution
* HTML responses under 50kb (guideline)
* Server-side rendering only

---

## 11. Security Baseline

* CSRF protection for POST requests
* Escaped template variables by default
* No inline user-generated JS
* HTTP-only cookies if sessions are used

---

## 12. Development Workflow

1. Edit Python file
2. Edit HTML template
3. Refresh browser
4. Done

No watchers.
No compilers.
No dependency hell.

---

## 13. Deployment

* Single binary or container
* Works behind nginx or directly exposed
* No build phase required in CI
* One command to run

---

## 14. Success Criteria

The project is successful if:

* A page loads with **zero JavaScript written by us**
* Interactions work without page reloads
* The entire system can be explained in 10 minutes
* A junior dev can understand the flow in one afternoon
* Nobody asks “where is the frontend?”

---

## 15. Philosophy (Non-Negotiable)

This system embraces:

* HTML as a first-class interface
* Servers doing the thinking
* Browsers doing the rendering
* Fewer abstractions, fewer lies
* The radical idea that the web already works

Complexity is not sophistication.
Build steps are a tax.
State belongs on the server.
