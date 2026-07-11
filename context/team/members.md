# Pinqponq Team Members

Reference for task assignment suggestions. Each entry covers role, seniority, active projects, proven capabilities from work history, and assignment guidance.

---

## Furkan Türkan
- **Role:** Team Lead
- **Seniority:** Senior
- **Primary stack:** Compose Multiplatform (KMP), mobile
- **Scope:** Generalist — active across mobile architecture, backend integrations, product decisions, and cross-cutting concerns
- **Active projects:** Rindle, Pinqloq, Pinqponq (web panel), NacEvent
- **Proven capabilities (from work history):**
  - Chat system architecture and implementation (MVP-level, real-time)
  - KMP/CMP core module setup and upgrades (e.g. CMP 1.8.0 on Turan)
  - MCP server development (KMP-MCP-Server: review feature, toon feature, component documentation)
  - Logging integration into mobile apps (Logolog setup)
  - Test infrastructure setup for KMP projects
  - Cross-project coordination and architectural decisions
  - Backend API integration on the mobile side (logpanel API, upload pipelines)
- **Assign when:** task requires cross-project coordination, touches multiple layers at once, involves mobile architecture, chat systems, MCP/tooling, or no other specialist has clear ownership.

---

## Atakan
- **Role:** Team Lead
- **Seniority:** Senior
- **Primary stack:** Backend (.NET), DevOps
- **Secondary:** Vibe coding — can build and ship dashboards, admin panels; can contribute to Compose Multiplatform mobile projects
- **Active projects:** Pinqloq (backend, infra), Pinqponq (backend), Rindle (backend), DevOps for all products
- **Proven capabilities (from work history):**
  - Backend architecture and refactoring (file upload service entity refactor, nullable ID support, parameter and model cleanup)
  - JWT authentication and authorization systems
  - GIB e-fatura / e-Arsiv integration (queue-based, browse, send workflows)
  - OTP generation and rate limiting
  - Webhook design and implementation
  - PTS (Parking Time System) integrations (ABONE, Borçlandırma, kaçak detection)
  - Complex reservation and section table design
  - HGS (highway toll) integrations
  - API Gateway configuration
  - Database stored procedures and schema design
  - DevOps: server setup, deployment coordination
- **Assign when:** task involves backend architecture decisions, complex third-party integrations, JWT/auth systems, stored procedures, or DevOps and deployment.

---

## Berk Çelik
- **Role:** Mid-level developer
- **Seniority:** Mid
- **Primary stack:** Compose Multiplatform (KMP), mobile
- **Secondary:** Active in Rindle backend feature work (current project context)
- **Active projects:** Rindle (mobile + backend contributions), Pinqponq
- **Proven capabilities (from work history):**
  - Full mobile screen development: login, register, onboarding, favorites, notifications, profile, settings, reservation creation/detail, section entries, branch profile, call center, notes, campaigns
  - UI component work: custom date pickers, dropdowns, lazy list dialogs, image compression, photo handling
  - API connection layer implementation (register, onboarding, reservation, photo APIs)
  - Bug fixing: crashes, navigation issues, UI inconsistencies, color/style regressions
  - KMP core module integration (with Furkan)
  - Pinqponq DM screen and conversation screen UI
  - Refactors: component usage consolidation, `.toString()` cleanup
  - HuhuvAdmin (KMP CMP admin panel): call center features, notes, reservations, kampanya listesi, branch profile
- **Assign when:** task is a mobile screen, UI component, feature screen, API connection on the client, bug fix in the mobile layer, or admin panel UI work in KMP.

---

## Emir Şenler
- **Role:** Mid-level developer
- **Seniority:** Mid (output and scope are effectively senior-level)
- **Primary stack:** Backend (.NET), DevOps, Infrastructure
- **Secondary:** Vibe coding — can build dashboards and panels with AI assistance; can contribute to Compose Multiplatform mobile projects with pinq-doq guidance
- **Active projects:** Pinqloq (.NET SDK, NuGet, backend), Pinqponq (backend), all shared infra
- **Proven capabilities (from work history — 242 backend tasks across multiple products):**
  - **Message brokers:** RabbitMQ (DLL creation, producer/consumer service, AMQP fixes, Docker containerization, scoped lifetime refactor)
  - **Caching:** Redis (DLL, cache reads/writes, cache invalidation, symbol subscribe, scoped lifetime, config key backup, external domain exposure)
  - **Real-time:** WebSocket (symbol subscription/unsubscription, reconnection, dispose fixes, performance optimization)
  - **Search & logging:** ElasticSearch integration, Kibana log fixes, Grafana setup (Docker), MongoDB logging (multi-collection, log tagging, 15-day retention policy)
  - **Infrastructure & DevOps:** Docker (Dockerfiles, docker-compose, containerization of microservices and test environments), GitHub Actions (CI/CD pipelines, docker-publish, Slack webhook fixes), server setup (3 server instances), Portainer, RabbitMQ test environment, AWS endpoint configuration
  - **Payment:** Ziraat Bank 3D Pay / Auth / Cancel integration, payment log implementation
  - **Microservices:** Built sekompos-tools from scratch (SMS Queue, Mail Queue, Fatura Queue, RabbitMQ DLL, Logger DLL, ElasticSearch DLL, tools gateway, LLM PR review tooling)
  - **Feature CRUD:** Reservation, photo management, reviews, questions, favorites, user roles, permissions, pagination, content-type filtering, rate limiting (OTP, API-wide)
  - **.NET SDK / NuGet:** Pinqloq .NET SDK version compatibility, NuGet packaging and readme maintenance
  - **PinqPonq backend:** UserFetch, AuthUser, Middleware, Filters endpoints
  - **Performance:** Burze speed optimization, Grafana monitoring, Redis fallback to API
  - **Migrations:** .NET 8 upgrades, DB context changes, JSON serialization refactors
- **Assign when:** task involves any infrastructure layer (Redis, RabbitMQ, Docker, CI/CD, ElasticSearch, MongoDB logging), payment integration, microservice tooling, Pinqloq .NET SDK/NuGet, or high-volume backend feature work.

---

## Yiğit Ünal
- **Role:** Intern
- **Seniority:** Intern (joined 2026-07-10 — very early stage)
- **Primary stack:** TBD — onboarding in progress
- **Active projects:** Not yet assigned to a project
- **Proven capabilities:** None on record yet.
- **Assign when:** suitable for well-scoped, low-risk, clearly defined tasks with explicit acceptance criteria and a mentor reviewer. Do not assign tasks that are blocking, cross-cutting, or architecturally sensitive.

---

## Assignment Quick Reference

| Area | First choice | Second choice |
|---|---|---|
| Rindle mobile / KMP UI screens | Berk | Furkan |
| Mobile architecture / chat / MCP | Furkan | — |
| Backend architecture / JWT / integrations | Atakan | Emir |
| Redis / RabbitMQ / Docker / CI/CD | Emir | Atakan |
| ElasticSearch / MongoDB logging / Grafana | Emir | — |
| Payment integrations (Ziraat Bank, etc.) | Emir | — |
| Pinqloq .NET SDK / NuGet | Emir | Atakan |
| GIB / e-Fatura / e-Arsiv / PTS / HGS | Atakan | — |
| Microservice tooling / sekompos-tools | Emir | — |
| Dashboard / admin panel (vibe coding) | Atakan | Emir |
| Cross-project / multi-layer | Furkan | — |
| Pinqponq mobile / KMP | Furkan | Berk |
| Well-scoped intern task | Yiğit | — |
