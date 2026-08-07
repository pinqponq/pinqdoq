---
paths: ['**/*.cs', '**/*.csproj', '**/*.sln']
---

# Pinqnugets Library Guide (Vibecoding)

## Purpose

This guide ensures that when building or vibecoding a .NET backend that can use **Pinqponq.*** NuGet packages (pinqnugets), the agent uses those packages instead of reimplementing or duplicating infrastructure. Prefer the shared surface for every generic mechanism the library already covers.

## Non-Goals

- Does not document every options property or teach full call sites in detail.
- Does not replace reading the package README or source when in doubt; it directs *what to prefer* and *when*.
- Does not apply to projects that will never consume Pinqponq.* packages (then this guide does not apply).

## Scope

### In-scope

- Before implementing infrastructure (auth tokens, OTP/TOTP, SSO, cache, SMS, mail, DB connectivity, messaging, global error handling), check the **reference** and use the listed Pinqponq package.
- When the project already has its own implementation of the same mechanism → **remove it** and switch callers to the Pinqponq APIs (do not leave both).
- When a needed mechanism is **generic infrastructure** missing from pinqnugets → propose adding it to pinqnugets, then consume the package; do not invent a long-lived project-local stack for that capability.
- After integrating a mechanism, update `.pinq-doq/references/dotnet/pinqnugets-reference.md` with any new situation mapping or pitfall learned.

### Out-of-scope

- Inventing new Pinqponq public APIs or changing package contracts from a consumer project.
- Putting domain repositories, message contracts, OTP-role / product rules, or other business logic into pinqnugets packages.
- Using this guide for non-.NET stacks.

### Stop conditions

- **Prefer package:** If a feature maps to a reference situation, use the Pinqponq package; do not reimplement.
- **Assume:** If the reference lists an area (e.g. “Redis cache / distributed lock”) and the app needs that behavior, assume Pinqponq.Cache is intended unless the user explicitly asks for a different stack.
- **Refuse:** Do not generate a second JWT, SMS, Redis, RabbitMQ connection, or global exception middleware stack when a Pinqponq package fits. Do not “extend” a package by smuggling domain logic into the shared library from the consumer.

## Procedure

1. **Validate context:** Confirm the work is .NET backend infrastructure that Pinqponq packages can cover (or should cover as generic infra).
2. **Match situation:** Read `.pinq-doq/references/dotnet/pinqnugets-reference.md` — “situation → use this.”
3. **Inventory:** Search the project for an existing implementation of the same mechanism (DI registrations, options types, service names).
4. **Plan:** Prefer `AddPinqponqXxx(...)` plus the package’s interfaces; implement only **app-owned** store contracts listed in the reference.
5. **Execute:** Add/upgrade the package, wire DI and options, migrate call sites, **delete** the project-local duplicate.
6. **Verify:** Build/tests pass; no parallel stacks remain for the same job.
7. **Update pinq-doq:** Amend the reference (and, if needed, this rule’s MUST / MUST NOT) with what was integrated or any new trap.

## Rules

### MUST

- Use **Pinqponq.Identity** for JWT issue/validate, refresh token issue/rotate/revoke, and password hash/verify. Register `AddPinqponqIdentity`; implement `IRefreshTokenStore` (and optional `IAccessTokenRevocationStore`) in the app.
- Use **Pinqponq.Identity.Otp** for one-time codes over email/SMS (`AddPinqponqOtp`, `IOtpService`, app-owned `IOtpStore` / optional `IOtpSendRateLimiter`). Pair with Pinqponq.Sms / Pinqponq.Mail only for channels you use.
- Use **Pinqponq.Auth.Totp** for RFC 6238 authenticator 2FA (`AddPinqponqTotp`, `ITotpService`, app-owned `ITotpReplayStore` for production `ValidateAsync`).
- Use **Pinqponq.Auth.Sso.Abstractions** for the external-provider contract (`IExternalAuthProvider`) and **Pinqponq.Auth.Sso.Google** for Google id_token validation (`AddPinqponqGoogleSso`).
- Use **Pinqponq.Cache** for Redis get/set/remove/exists, distributed lock, and Redis health (`AddPinqponqCache`, `AddPinqponqRedis`).
- Use **Pinqponq.Sms** for NetGSM SMS (`AddPinqponqSms`, `ISmsSender`).
- Use **Pinqponq.Mail** for SMTP email (`AddPinqponqMail`, `IEmailSender`).
- Use **Pinqponq.Database.Postgres** / **Mongo** / **Mssql** for connection setup, retry/resiliency (where applicable), and health-checks — not for repositories or entities.
- Use **Pinqponq.Messaging.RabbitMq** for publish/consume transport, reconnect, and DLX / redelivery (`AddPinqponqRabbitMq`, `AddRabbitMqConsumer<THandler>`). Message contracts stay in the app.
- Use **Pinqponq.ErrorHandling** for global exception middleware and the standard error response / Pinqloq-oriented structured log shape (`AddPinqponqErrorHandling`, `UsePinqponqErrorHandling` early in the pipeline).
- **Replace, do not coexist:** When migrating, remove the project’s previous implementation of the same mechanism.
- **Respect package boundaries:** Keep domain/business logic in the app; implement only the app-owned storage/rate-limit interfaces the packages require.
- **Missing generic capability:** Prefer adding it to pinqnugets over a permanent project-only infrastructure stack.
- **Feedback loop:** After integration, update `.pinq-doq/references/dotnet/pinqnugets-reference.md`.

### SHOULD

- Prefer the package README under the pinqnugets repo (`src/Pinqponq.*/README.md`) for options and pitfalls once the package is chosen.
- Register infrastructure via DI extension methods (consistent with `dotnet-conventions.md` startup rules).
- When reviewing or scaffolding, scan the reference table before inventing helpers.

### MUST NOT

- Implement JWT creation/validation, refresh-token rotation/family revoke, or PBKDF2-style password hashing outside Pinqponq.Identity when that package fits.
- Implement OTP generate/send/verify outside Pinqponq.Identity.Otp when that package fits.
- Implement TOTP secret/URI/validation outside Pinqponq.Auth.Totp when that package fits.
- Implement Google id_token validation outside Pinqponq.Auth.Sso.Google when that package fits.
- Implement Redis cache wrappers or distributed locks outside Pinqponq.Cache when that package fits.
- Implement NetGSM / SMTP sending outside Pinqponq.Sms / Pinqponq.Mail when those packages fit.
- Implement DB connection factories + retry/health outside the matching Pinqponq.Database.* package when it fits.
- Implement RabbitMQ connection/channel/DLX transport outside Pinqponq.Messaging.RabbitMq when that package fits.
- Implement a parallel global exception middleware and error-body contract outside Pinqponq.ErrorHandling when that package fits.
- Leave a project-local stack beside the Pinqponq package “just in case.”
- Push product-specific domain rules into pinqnugets from a consumer change.

## Reference

See **`.pinq-doq/references/dotnet/pinqnugets-reference.md`** for: what exists in the packages and which API to use in which situation. Use it to decide “use this from pinqnugets” before writing app infrastructure code.

## Architecture note (package vs app)

Packages hold **fixed behavior that wraps an external dependency**. Persistence of refresh tokens, OTP records, TOTP replay keys, and jti revocation lists is **app-owned** via interfaces. Domain repositories, message DTOs/contracts, and product rules stay in the consuming project.

**Source:** https://github.com/pinqponq/pinqnuqets
