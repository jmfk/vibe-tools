# Architecture Specification (Desired)

## 1. Core Philosophy
The project follows a **Server-Driven UI** philosophy. We prioritize HTML over JSON, and servers over complex client-side state. The goal is to minimize build-time complexity and maximize development velocity using AI-assisted tooling.

## 2. Tech Stack

### 2.1 Backend
- **Language**: Python 3.9+
- **Framework**: FastAPI (for performance and type safety)
- **CLI**: Click (for a robust command-line interface)
- **ORM**: Tortoise-ORM (async-first ORM)
- **Database**: PostgreSQL

### 2.2 Frontend
- **Framework**: HTMX (for dynamic interactions without heavy JS)
- **Styling**: Tailwind CSS (via Play CDN for zero build step)
- **Templating**: Jinja2 (server-side rendering)
- **Build Step**: Zero. No Node.js, no bundlers, no npm.

### 2.3 AI & Tooling
- **Vibe Tools**: Custom CLI tools (`vibe`) for PRD generation, test coverage improvement, and infrastructure management.
- **Prompts**: Version-controlled AI prompts in `prompts/`.

## 3. Project Structure
```text
/
├── vibe_tools/      # Core automation logic and CLI
├── app/             # Main application logic (FastAPI)
│   ├── routes/      # API and HTML endpoints
│   ├── models/      # Tortoise-ORM models
│   ├── templates/   # Jinja2 HTML templates
│   └── static/      # Minimal static assets (CSS/JS)
├── specs/           # Markdown PRDs and specifications
├── prompts/         # AI prompt templates
├── project/         # Architecture and infrastructure definitions (YAML)
└── tests/           # Comprehensive test suite
```

## 4. Key Design Patterns
- **HTML Fragments**: Routes return partial HTML for HTMX targets.
- **CLI-First Workflow**: All infrastructure and common tasks are driven by the `vibe` command.
- **PRD-Driven Development**: Changes start with a PRD in `specs/`, normalized into plans.
