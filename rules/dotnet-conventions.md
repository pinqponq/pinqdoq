---
paths: ['**/*.cs', '**/*.csproj', '**/*.sln']
---

# C# / .NET Standards

Extends `common.md`. These rules apply to all C# backend projects.

---

## Code Style

- Follow standard C# formatting rules. No Python-like or non-C# styling.
- Attributes must be on a separate line above the target member, never inline.

---

## LINQ Safety

Avoid crash-prone LINQ calls on collections.

```csharp
// ❌ Wrong
.First()

// ✅ Correct
.FirstOrDefault()
// or precede with .Any() check
```

---

## Entity Framework

- No single-letter variable names in EF queries.

```csharp
// ❌ Wrong
.Where(b => b.IsActive)

// ✅ Correct
.Where(branch => branch.IsActive)
```

---

## Database Filters

- Every new filter or search parameter on a large or write-heavy collection or table must use an index. Add the index in the same change, or do not add the filter.
- An index costs time on every write. Index only the fields a stated need filters by. Do not add an index per key "in case".
- A filter without an index scans the collection. Narrowing the time window does not make it safe. If an unindexed filter is really needed, it is a decision: record it and get it approved before the PR.

---

## Startup & Dependency Registration

- `Program.cs` must not become a God Object.
- Infrastructure setup must be moved to extension methods.

```csharp
// ✅ Correct
services.AddPostgresDatabase();
services.AddRabbitMq();
```

---

## Concurrency & Thread Safety

- Complex constructs like `Interlocked` must be hidden behind meaningful names.

```csharp
// ❌ Wrong
if (Interlocked.Exchange(ref _isDisposed, 1) == 1)

// ✅ Correct
if (IsDisposeAlreadyStarted())
```

---

## Guard Clauses

```csharp
if (request == null) throw new ArgumentNullException(nameof(request));
if (!request.Products.Any()) throw new Exception("Order cannot be created without products");
```

---

## No Logic in Object Initializers

```csharp
// ✅ Correct
var hasNextPage = page > 0 && currentPage < page;
return new Response { HasNextPage = hasNextPage };
```

---

## Configuration & Secrets

- Never commit a secret (password, key, token, connection string with a password) to an `appsettings*.json` file. Read it from Vault with `Pinqponq.Configuration.Vault`: `builder.Configuration.AddPinqponqVault("VaultConfiguration")`.
- A setting that differs between the prod server, the test server and a developer machine (an address, a URL) lives in Vault too. A setting that is identical everywhere (timeouts, limits, logging, lists) stays in `appsettings.json`.
- Records are `apps/<project>/<prod|test|local>/<service>`. The test server runs with `DOTNET_ENVIRONMENT=Test`, never `Development`.
- Define a list setting (a JSON array) in one settings file only: .NET merges the same list from two settings files element by element, so the leftover elements of the longer one leak through.
- Moving a project onto this standard: use the `pinq_vault-config-setup` skill. Details: `.pinq-doq/references/dotnet/vault-configuration.md`; developer machine setup: `.pinq-doq/references/dotnet/vault-cli-setup.md` or the `pinq_vault-dev-setup` skill (run a moved project locally).

---

## Error Handling

- Never pass only `ex.Message` — always pass the original exception to preserve the stack trace.
- Never use `_ = task.Exception` to discard errors silently.

---

## Magic Strings / Domain Codes

```csharp
// ❌ Wrong
"23503" // Foreign key violation

// ✅ Correct
PostgresErrorCodes.ForeignKeyViolation
```

---

## Shared Packages (pinqnuqets)

`pinqnuqets` holds only code that every Pinqponq ASP.NET Core API needs in the same form. A product-specific thing never goes into it.

- Test for every type, option, default, constant and message: would a product other than the one this code came from need exactly this? If the answer depends on one product, it stays in that product.
- Product-specific means: a header, query key, route, response code, message or default taken from one product's client or contract; an option that exists for one product only; a feature that only products with one kind of client (for example a mobile app) need.
- If you are not sure a part is shared, leave it in the product. You may instead move it into its own opt-in package as a setting with a neutral default, which means a default that was not copied from the first product. The setting is off by default.
- Technology-specific code (PostgreSQL, MongoDB, EF Core, Vault) is fine in its own opt-in package, as long as nothing in it names a product.
- When moving code out of a product into `pinqnuqets`, remove the product-specific parts first and leave them in the product. The product then keeps them as its own code on top of the package.
- A pull request that adds or changes a `pinqnuqets` package lists, for each package, what the package kept, what was left in the product, and why.
- Reviewers: a product-specific constant or default in a `pinqnuqets` change is a blocker.
- A package that targets several frameworks is tested on every one of them before the pull request: install the runtime of each `TargetFrameworks` entry and run `dotnet test` without `-f`. A green run on the newest runtime says nothing about the oldest one; for example, a `DispatchProxy` test double over a large SDK interface fails only on .NET 8.

---

## Mutation Testing

- Prove that new tests can fail with Stryker.NET, scoped to the changed files: from the test project, run `dotnet stryker -p <Project>.csproj -m "**/<ChangedFile>.cs"` for each changed production project.
- Count only the mutants on lines changed against the default branch, and report that score with every surviving mutant and its reason.
- Hand-written mutants do not count as mutation testing.
- `[Description]` and other attribute constants cannot be mutated; say so instead of counting them.
