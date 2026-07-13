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
