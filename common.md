# Common Coding Standards

These rules apply to all projects and all languages unless a language-specific file overrides them.

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

- Do not prefix interfaces with `I`.
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
- Comments must not explain magic values — the identifier name must carry the meaning.
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
