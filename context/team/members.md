# Pinqponq Team Members

Reference for task assignment suggestions. Each entry covers role, seniority, capability areas, and assignment guidance.

---

## Furkan Türkan
- **GitHub:** furkanturkn
- **Role:** Team Lead
- **Seniority:** Senior
- **Primary stack:** Compose Multiplatform (KMP), mobile
- **Scope:** Generalist — mobile architecture, cross-layer integration, product decisions
- **Capabilities:**
  - KMP/CMP architecture and core module setup
  - Real-time and chat system design
  - MCP server development and tooling
  - Test infrastructure for KMP projects
  - Mobile-side backend integration
- **Assign when:** task requires cross-project coordination, mobile architecture decisions, chat/real-time systems, MCP tooling, or has no clear specialist owner.

---

## Atakan
- **GitHub:** atakancelik
- **Role:** Team Lead
- **Seniority:** Senior
- **Primary stack:** Backend (.NET), DevOps
- **Secondary:** Vibe coding — dashboards and admin panels; can contribute to KMP mobile
- **Capabilities:**
  - Backend architecture design and refactoring
  - Auth and JWT systems
  - Complex third-party integrations (payment providers, government APIs, hardware systems)
  - Database and stored procedure design
  - API Gateway configuration
  - Server setup and deployment
- **Assign when:** task involves backend architecture, complex integrations, auth systems, stored procedures, or infrastructure setup. For Rindle specifically, assign Atakan only for advanced architectural tasks — routine Rindle backend work goes to Berk.

---

## Berk Çelik
- **GitHub:** berkcelik99
- **Role:** Mid-level developer
- **Seniority:** Mid
- **Primary stack:** Compose Multiplatform (KMP), mobile
- **Secondary:** Backend feature contributions on current Rindle work
- **Capabilities:**
  - Full mobile screen implementation (feature screens, settings, onboarding, reservations)
  - Custom UI components and composables
  - Client-side API connection layer
  - Bug fixing and UI polish
  - KMP admin panel screens
  - Rindle backend feature development (active role on both backend and mobile sides)
- **Assign when:** task is a KMP/CMP mobile screen, UI component, client API connection, or mobile bug fix. For Pinqponq SDK mobile side, Berk is the primary. For Rindle, Berk is the primary for both mobile and backend tasks — Atakan only steps in for advanced architectural work on Rindle. **Do not assign Pinqloq dashboard or WASM panel tasks** — those go to whoever owns the Pinqloq backend (see project-specific rules below).

---

## Emir Şenler
- **GitHub:** emirsenler
- **Role:** Mid-level developer
- **Seniority:** Mid (output and scope are effectively senior-level)
- **Primary stack:** Backend (.NET), DevOps, Infrastructure
- **Secondary:** Vibe coding — dashboards and panels; can contribute to KMP mobile with pinq-doq guidance
- **Capabilities:**
  - Message brokers (RabbitMQ) and caching (Redis)
  - Observability stack (ElasticSearch, Kibana, Grafana, MongoDB logging)
  - Containerization and CI/CD (Docker, GitHub Actions)
  - Payment integrations
  - Microservice and shared tooling libraries
  - .NET SDK and NuGet packaging
  - High-volume backend feature delivery
- **Assign when:** task involves infrastructure (Redis, RabbitMQ, Docker, CI/CD, logging), payment integration, SDK/NuGet work, or large backend feature scope.

---

## Yunuscan Bartık
- **GitHub:** yunuscanbartik
- **Role:** Developer Advocate (title assigned 2026-08-09); also backend developer
- **Seniority:** Junior–Mid
- **Primary focus:** Developer relations — content, community, product advocacy
- **Primary stack:** Backend (.NET Core, ASP.NET Web API, ADO.NET, Entity Framework Core)
- **Secondary:** Vibe coding — dashboards and panels; can contribute to KMP mobile with pinq-doq guidance
- **Capabilities:**
  - Developer-facing content: feature announcements, use-case walkthroughs, technical storytelling
  - Community presence and engagement (X, developer groups and communities)
  - Research on developer advocacy practices and competitor devrel activity
  - RESTful API design and development (.NET Core, ADO.NET, Entity Framework Core)
  - MSSQL Server (T-SQL) — stored procedures, triggers, complex CRUD operations
  - PostgreSQL
  - Message queues (RabbitMQ) for high-volume data processing pipelines
  - Redis caching for real-time system performance optimization
  - Cloud & integrations: AWS (S3), Firebase, SMTP
- **Assign when:** task involves developer-facing content, product announcement strategy, community building, or devrel research. Also available for .NET backend API development, RabbitMQ/Redis infrastructure work, or MSSQL/PostgreSQL database design.

---

## Assignment Quick Reference

| Area | First choice | Second choice |
|---|---|---|
| KMP mobile screens / UI | Berk | Furkan |
| Mobile architecture / chat / MCP | Furkan | — |
| Backend architecture / auth / integrations | Atakan | Emir |
| Redis / RabbitMQ / Docker / CI/CD | Emir | Atakan |
| Observability (ElasticSearch, Grafana, logging) | Emir | — |
| Payment integrations | Emir | — |
| .NET SDK / NuGet | Emir | Atakan |
| Complex third-party / gov APIs | Atakan | — |
| Dashboard / admin panel (vibe coding) | Atakan | Emir |
| Pinqloq dashboard + WASM panel (vibe coding) | backend owner of that task | — |
| Pinqponq dashboard + WASM panel (vibe coding) | backend owner of that task | — |
| Pinqponq SDK — mobile (CMP/KMP) | Berk | Furkan |
| Pinqponq SDK — backend | Atakan | Emir |
| Cross-project / multi-layer | Furkan | — |
| Developer relations / content / community | Yunuscan | — |
| Product announcement strategy | Yunuscan | — |
| Pinqloq/Pinqponq dashboard UI-only (responsive, layout, CSS) | Atakan | Emir |
| Rindle — mobile | Berk | Furkan |
| Rindle — backend (routine) | Berk | — |
| Rindle — backend (advanced/architectural) | Atakan | — |

---

## Project-Specific Assignment Rules

### Rindle
Rindle has both a mobile (KMP/CMP) side and a backend side. Berk is the primary developer for both:
- **Mobile:** Berk. Second choice: Furkan.
- **Backend (routine features, bug fixes, config changes):** Berk.
- **Backend (advanced architectural work only):** Atakan. Do not assign Atakan routine Rindle backend tasks.

### Pinqloq
Pinqloq has two components:
- **Dashboard** — API key and project management (web app)
- **WASM panel** — log viewing interface used by customers (WebAssembly site)

Both are developed with **vibe coding**. The rule: whoever owns the backend task for a given Pinqloq feature also owns the client (dashboard/panel) side. Do not assign Pinqloq panel tasks to KMP mobile developers (Berk) by default — they go to the backend developer handling that feature (typically Emir or Atakan). Scoped UI-only tasks on the dashboard (responsive fixes, layout polish, CSS changes, copy/UX improvements) that require no backend knowledge go to Atakan or Emir.

### Pinqponq SDK
- **Mobile side (CMP/KMP):** vibe coding is allowed, but always assign to mobile team members — Berk (primary) or Furkan.
- **Backend side:** strictly backend developers — Atakan or Emir. No exceptions.
- **Dashboard + WASM panel:** same rule as Pinqloq — vibe coding, backend developer owns both backend and client. Do not assign to KMP mobile developers.
