# Pinqnugets: What Exists and When to Use It

Use this as a quick map: **situation → use this from Pinqponq.***. No full parameter lists; see each package README under https://github.com/pinqponq/pinqnuqets (`src/Pinqponq.*/README.md`) for those.

Packages target `net8.0`, `net9.0`, and `net10.0`.

---

## Identity (`Pinqponq.Identity`)

| Situation | Use |
|---|---|
| Issue / validate JWT (HMAC or RSA) | `AddPinqponqIdentity` → `IJwtTokenGenerator`, `IJwtTokenValidator` |
| Refresh token issue / rotate / revoke (+ reuse / family revoke) | `IRefreshTokenService` + app `IRefreshTokenStore` |
| Password hash / verify (PBKDF2) | `IPasswordHasher` |
| Logout / revoke access by `jti` | Optional `IAccessTokenRevocationStore` + `IAccessTokenRevocationService` |

**Do not:** Hand-roll JWT creation, custom refresh-token rotation, or a second password hasher when this package fits.

---

## OTP (`Pinqponq.Identity.Otp`)

| Situation | Use |
|---|---|
| Generate / send / verify one-time codes | `AddPinqponqOtp` → `IOtpService` |
| Persist OTP hashes / attempts | App `IOtpStore` (`TryConsumeAsync` / `TryRemoveAsync` must be atomic) |
| Rate-limit sends | `OtpOptions.MinSendInterval` + replace default no-op `IOtpSendRateLimiter` |
| Deliver via SMS / email | Register only the channel you use: `AddPinqponqSms` / `AddPinqponqMail` |

**Do not:** Build a parallel OTP pipeline or require both SMS and mail senders when only one channel is used.

---

## TOTP (`Pinqponq.Auth.Totp`)

| Situation | Use |
|---|---|
| Authenticator 2FA (RFC 6238) | `AddPinqponqTotp` → `ITotpService` |
| Provisioning QR (`otpauth://`) | `GenerateSecret` + `GetProvisioningUri` |
| Validate with replay protection | `ValidateAsync` + app `ITotpReplayStore` (prefer over sync `Validate` in production) |

**Do not:** Reimplement TOTP math or authenticator URI formatting.

---

## SSO

| Situation | Use |
|---|---|
| Shared external IdP contract | `Pinqponq.Auth.Sso.Abstractions` — `IExternalAuthProvider`, `ExternalAuthRequest` / `Result` / `UserInfo` |
| Google OAuth2/OIDC id_token sign-in | `Pinqponq.Auth.Sso.Google` — `AddPinqponqGoogleSso` |

**Do not:** Validate Google id_tokens with ad-hoc JWT parsing when the Google package fits. Evaluate `hd` / Gmail authority before auto account-linking by email.

---

## Cache (`Pinqponq.Cache`)

| Situation | Use |
|---|---|
| Redis get / set / remove / exists | `AddPinqponqCache` → `ICacheService` |
| Distributed lock (+ optional fencing / renew) | `IDistributedLock` / `ILockHandle`, `DistributedLockAcquireOptions` |
| Redis health-check | `AddHealthChecks().AddPinqponqRedis()` |

**Do not:** Wrap StackExchange.Redis again or invent a second lock primitive when this package fits. Enforcing fencing tokens on the DB side stays in the app.

---

## SMS (`Pinqponq.Sms`)

| Situation | Use |
|---|---|
| Send SMS via NetGSM | `AddPinqponqSms` → `ISmsSender`, `SmsMessage` |
| Prefer modern transport | `SmsTransport.RestV2` (POST + Basic Auth); legacy `GetQuery` still exists |

**Do not:** Keep a project `ISmsService` / `IGSMService` beside `ISmsSender`. Do not log GET URLs that carry credentials.

---

## Mail (`Pinqponq.Mail`)

| Situation | Use |
|---|---|
| Send SMTP email | `AddPinqponqMail` → `IEmailSender`, `EmailMessage` |
| Attachments | Set `AttachmentRoot` (path jail); required when sending files |

**Do not:** Reimplement SMTP send + attachment path checks when this package fits.

---

## Database

| Situation | Use |
|---|---|
| Postgres connection + retry + health | `Pinqponq.Database.Postgres` — `AddPinqponqPostgres`, `IPostgresConnectionFactory`, `AddPinqponqPostgres()` health |
| MongoDB client + health | `Pinqponq.Database.Mongo` — `AddPinqponqMongo`, `IMongoClient` / `IMongoDatabase` |
| SQL Server connection + retry + health | `Pinqponq.Database.Mssql` — `AddPinqponqMssql`, `ISqlConnectionFactory` |

**Do not:** Put repositories or entities in these packages. Do not duplicate connection-factory + Polly retry + health wiring when the matching package fits.

---

## Messaging (`Pinqponq.Messaging.RabbitMq`)

| Situation | Use |
|---|---|
| Shared connection / publisher | `AddPinqponqRabbitMq` → `IMessagePublisher`, `IRabbitMqConnection` |
| Consumer host | `AddRabbitMqConsumer<THandler>` where `THandler : IMessageHandler` |
| Dead-letter / poison | DLX on by default; if DLX off, use `MaxRedeliveryCount` |

**Do not:** Reimplement connection/channel lifecycle, publisher confirms + mandatory, or DLX policy when this package fits. Message contracts stay in the app.

---

## Error handling (`Pinqponq.ErrorHandling`)

| Situation | Use |
|---|---|
| Global exception → standard body | `AddPinqponqErrorHandling` + `UsePinqponqErrorHandling()` (early in the pipeline) |
| Correlation | Incoming `X-Correlation-ID` maps into response / log fields per package docs |

**Do not:** Ship a second middleware that invents a different error JSON shape when this package fits.

---

## App-owned contracts

These interfaces are **implemented in the consuming app** (storage / policy), not inside the packages’ default DI:

| Interface | Package |
|---|---|
| `IRefreshTokenStore` | Identity |
| `IAccessTokenRevocationStore` (optional) | Identity |
| `IOtpStore` | Identity.Otp |
| `IOtpSendRateLimiter` (replace no-op to enforce) | Identity.Otp |
| `ITotpReplayStore` | Auth.Totp |
| `IMessageHandler` (per queue handler) | Messaging.RabbitMq |

---

## Migration notes

- Rename project SMS abstractions (`ISmsService`, `IGSMService`, …) to `ISmsSender` / `SmsMessage` call sites; delete the old types.
- Prefer RestV2 for NetGSM; if staying on GetQuery, never log full API URLs (password in query).
- Identity-only apps may omit `IRefreshTokenStore` until they resolve `IRefreshTokenService` — missing store fails at resolve time, not always at host build.
- OTP: register SMS and/or mail senders only for channels you route to.
- ErrorHandling: call `UsePinqponqErrorHandling()` near the start of the ASP.NET pipeline.
- Database packages: keep EF/Mongo repositories in the app; only connection + health come from Pinqponq.
- After any migration, update this file if you discovered a new situation mapping or pitfall.

---

## Source

- Monorepo: https://github.com/pinqponq/pinqnuqets  
- nuget.org profile: https://www.nuget.org/profiles/pinqponq  
- Rule that points here: `.pinq-doq/rules/dotnet-pinqnugets.md`
