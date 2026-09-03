# Common Coding Standards

These rules apply to all projects and all languages unless a language-specific file overrides them.

---

## Stack-specific rules

This file always loads. Stack-specific rules load automatically only when you touch a matching file, so they may not be in context yet. Before writing stack code, make sure the relevant rule is loaded:

- **Kotlin / KMP / Compose** (`*.kt`, `*.kts`) → `kotlin-architecture.md` (structure, MVI, shared module), `kotlin-naming.md`, `kotlin-conventions.md` (style), plus `kotlin-deveng-core.md` when the project depends on deveng-core-kmp. Deep references live in `.pinq-doq/references/kotlin/` (architecture, data-layer, mvi-pattern, naming, shared-module, …) and `.pinq-doq/references/kotlin/deveng-core-reference.md`, read on demand.
- **C# / .NET** (`*.cs`, `*.csproj`, `*.sln`) → `dotnet-conventions.md`.

---

## Naming Conventions

- Use English strictly. No Turkish identifiers, comments, or abbreviations.
- No abbreviations anywhere. Write it out.
- Variables are nouns. Methods are verbs. Names must reflect context, not just type.

| Identifier | Convention | Example |
|---|---|---|
| Classes & Interfaces | PascalCase | `DashboardRepository` |
| Functions / Methods | camelCase, verb-based | `loadUserData()` |
| Variables | camelCase, noun-based | `userName`, `isLoading` |
| Constants | SCREAMING_SNAKE_CASE | `MAX_RETRY_COUNT` |
| Packages | lowercase, dot-separated | `com.protein.android.domain.user.usecase` |
| Lambda / Callback Parameters | camelCase, contextual prefix | `onRegistrationItemClick` |

- Do not prefix interfaces with 'I' in Kotlin.
- Do not add an `Async` suffix to async methods — the return type already signals it.
- If a method only checks → use `validate`, `check`. If it creates or saves → use action verbs.

---

## Separation of Concerns & Single Responsibility

- Each code unit must have exactly one responsibility.
- Extract large logical blocks (retry logic, setup, try-catch) into well-named sub-functions.
- Apply SRP without over-engineering. Do not create abstractions without real value.
- Layer dependency rules:
  - Application depends only on Domain.
  - Domain must not depend on any other layer; Domain may only depend on other Domain modules.

---

## Error Handling

- Never hide stack traces — always pass the original exception, not just `ex.Message`.
- Never swallow errors silently. Every error must be logged.
- Do not use sentinel values (`-1`, `0`, `null`, empty string) to signal errors.
  - Value required but missing → throw an exception.
  - Value optional → model it as optional; do not fake validity.

---

## Null & Optional Safety

- If something can be optional, make it optional — do not fake non-nullability.
- If a method cannot return null, its return type must not be nullable.
- When using force-unwrap (`!!` in Kotlin, `!` in Swift), add an inline comment explaining why it is safe — or avoid it entirely.

---

## Magic Values & Configuration

- Never hardcode tunable or performance-sensitive values. Use named constants or config.
- Never use inline strings or numeric codes for domain-meaningful values. Use enums or constants.
- Never assign hardcoded numeric values to variables ending with `Id`. If a static value is needed, it should be an enum or well-named constant.

---

## Code Style & Readability

- Use guard clauses to fail fast. Avoid deeply nested `if` blocks.
- Extract long or complex conditions into well-named variables or methods.
- Do not place logic inside object initializers. Compute values into named variables first.
- State fields always assigned the same value must be set outside conditional branches.
- Variable names must clearly describe what the data represents, not its technical type.
- Do not create variables that simply mirror a parameter — unless they add validation or semantic meaning.
- Attributes/annotations must be on a separate line above the target member, never inline.

---

## Comment Standards

- Do not add comments by default. Prefer readable code, meaningful naming, and small functions.
- Do not write comments that only restate what the code already says.
- Only comment information that cannot be inferred from the code and can be verified from the existing context:
  - business rules and deliberate exceptions,
  - technical constraints and temporary workarounds,
  - security or performance trade-offs,
  - unexpected behavior of external systems,
  - deliberate implementations that look like a mistake at first glance.
- Do not guess a decision's rationale if it was not given by the user or is not explicit in the project. Ask the user for clarification when it is needed.
- If the need for a comment can be resolved with better naming or a refactor, improve the code first instead.
- When changing code, also check the comments tied to it: update or remove any that are no longer valid, but never delete a comment without understanding the context and rationale it carries.
- In `TODO` comments, state the rationale, a tracking reference, and the removal condition where possible.
- Do not auto-generate line-by-line comments just to explain generated code.
- Keep comments short and concrete.

**Core test:** if removing a comment would not lose an important, verifiable rationale or warning, the comment was unnecessary.

---

## Constructor & Dependency Naming

Constructor parameters must clearly express what they configure, not just repeat the type name.

```
// ❌ Wrong
RabbitMQService(options)

// ✅ Correct
RabbitMQService(rabbitOptions)
```

---

## Health & Connectivity

- Services must expose connectivity state via `isConnected`.
- Do not rely solely on exceptions for system health checks.
- Prepare for HealthCheck integration from the start.

---

## Configuration Validation

- Required config fields must be validated at startup.
- Fail fast during application boot, not at runtime.
