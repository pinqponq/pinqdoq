# Vault configuration standard (.NET)

How PinqPonq .NET services read their settings from HashiCorp Vault: what lives in Vault, how the records are laid out, who reads which record, and how tokens work. The first project on this standard is pinqponq-server; the rest follow it.

The terse rule is in `rules/dotnet-conventions.md` (Configuration & Secrets). To apply the standard to a project, use the `pinq_vault-config-setup` skill. To get a developer machine ready, see [vault-cli-setup.md](vault-cli-setup.md) or use the `pinq_vault-dev-setup` skill, which runs `scripts/vault_config.py check` and says what is missing (VPN, login, access, record).

## The model in one table

There are three readers. Each one reads its own record per service, and the two Vault servers keep prod apart from everything else.

| Reader | Vault | Record | Settings file that points at it |
|---|---|---|---|
| Prod server | prod Vault | `apps/<project>/prod/<service>` | `appsettings.json` |
| Test server | test Vault | `apps/<project>/test/<service>` | `appsettings.Test.json` |
| Developer machine | test Vault | `apps/<project>/local/<service>` | `appsettings.Development.json` |

- `apps` is a KV version 2 mount that a Vault administrator creates (the tools check that it exists and is version 2, and never create it), `<project>` is the product in lower case (for example `pinqponq`; Vault paths are case sensitive, so every record, policy and token must spell it the same way), `<service>` is the service in lower case with dashes (`chat-api`, `notifications-worker`).
- Each record is JSON shaped exactly like `appsettings.json`, so every `IOptions<T>` binding keeps working. A key the record does not contain keeps its value from the settings files.
- `test` holds the same values as `prod` when both servers run the same containers under the same names. `local` holds the addresses a developer machine needs (`10.0.0.1:26379`, `localhost`). The records duplicate their secrets on purpose: every record is complete on its own, and nothing has to be layered in your head. The price is that a changed test secret is updated in two records.

## One Vault or two

The table above assumes two servers. Not every team has two, so the standard works with one as well. The three folders `prod`, `test` and `local` exist either way; only the server they sit on changes.

| | Prod Vault | Test Vault |
|---|---|---|
| **Two Vaults** | `prod/<service>` (`appsettings.json`) | `test/<service>` (`appsettings.Test.json`) and `local/<service>` (`appsettings.Development.json`) |
| **One Vault** (treated as the prod Vault) | `prod/<service>`, `test/<service>` and `local/<service>` | none |

How the tools know which case they are in: the settings files already hold the addresses (two different ones mean two Vaults, one means one), or, in a project that has none yet, the skill asks once for the prod address and whether a separate test Vault exists. No separate test address means one Vault. `scripts/vault_config.py` does the same: without `--test-vault-address` (and without a test address in the settings files) it uses the prod address for every reader.

With one Vault the isolation of prod is no longer a matter of a separate server, so it has to come from Vault policies, which these tools do not create:

```hcl
# developer accounts: local records only
path "apps/data/pinqponq/local/*" { capabilities = ["read", "create", "update"] }

# test server token, per service
path "apps/data/pinqponq/test/chat-api" { capabilities = ["read"] }

# prod server token, per service
path "apps/data/pinqponq/prod/chat-api" { capabilities = ["read"] }
```

Only the few people who maintain prod get write access to `apps/data/<project>/prod/*`. Developer machines and the test server also need network access to this Vault, which was not the case when prod had a server of its own.

## What lives where

Ask of every setting: **is it a secret, or does it differ between the prod server, the test server and a developer machine?** If yes, it is in Vault, in all three records. If no, it stays in `appsettings.json`.

| In Vault | In `appsettings.json` |
|---|---|
| Passwords, secret keys, signing and encryption keys, tokens, API keys | Timeouts, retry counts, limits, expiry durations |
| Connection strings (they carry a password) | Queue and worker intervals, feature switches that are the same everywhere |
| Host names, ports and URLs that differ per reader | Logging levels, `AllowedHosts` |
| External service identifiers that differ per environment (for example a LiveKit key and URL) | Lists such as `BypassPaths` that are identical for every reader |

Three consequences worth remembering:

- A setting that is only *sometimes* different (an address that equals the prod one today but will not tomorrow) belongs in Vault now. Moving it later means touching every record.
- Do not split one concern across both places by accident. Moving a whole section (`Redis`, `RabbitMQ`) keeps it readable; if only the password is secret and the rest is identical everywhere, the rest stays in the file, and that split is fine as long as it is deliberate.
- The settings files keep only the location of the record, and it is not a secret:

```json
"VaultConfiguration": {
  "Address": "http://10.0.0.2:8200",
  "Mount": "apps",
  "Path": "pinqponq/prod/chat-api"
}
```

`appsettings.Test.json` and `appsettings.Development.json` contain only the same section with the test Vault address and the `test` or `local` path.

## How a service reads it

The package `Pinqponq.Configuration.Vault` (repository `pinqnuqets`) adds one configuration source. Add it first thing in `Program.cs`, before any setting is read:

```csharp
using Pinqponq.Configuration.Vault;

var builder = WebApplication.CreateBuilder(args); // or Host.CreateApplicationBuilder(args) for workers
builder.Configuration.AddPinqponqVault("VaultConfiguration");
```

The section name is a parameter because a project that still uses a `Vault` section for something else (for example the old customer-secret code) cannot share it.

Which record a process reads is decided by its environment name:

| Where | Environment | Why |
|---|---|---|
| Developer machine | `Development` | Loads `appsettings.Development.json`, which points at the `local` record. Worker launch profiles set `DOTNET_ENVIRONMENT=Development`. |
| Test server | `Test` (`DOTNET_ENVIRONMENT=Test` in the compose file) | Loads `appsettings.Test.json`, which points at the test Vault and the `test` record. |
| Prod server | none (Production) | `appsettings.json` already points at the prod Vault and the `prod` record. |

**Never run the test server as `Development`.** The environment name is not only a file selector: `Development` also switches on development-only behaviour (OpenAPI endpoints, development-mode authentication) and would load the `local` record, whose addresses are developer-machine addresses.

Vault is the last configuration source, so a key that exists in the record **overrides the same key from environment variables and the command line** (for example a `Redis__EndPoints` set in the compose file or in Portainer). To change such a value, change the record. Keys that are not in the record still honour environment variables.

The record is read once at startup. A changed record takes effect when the service restarts. Startup fails fast, with a message that names the problem, when Vault is unreachable (after retries), the record is missing, or the token is rejected.

## Tokens

| Who | How they authenticate | What they can do |
|---|---|---|
| A person | Their own Vault account (`userpass`), in the UI or with `vault login` | Edit the records they are allowed to; every change records who made it in the version history |
| A server | A token for that service in `VAULT_TOKEN` (compose or Portainer environment) | Read its own record only |
| A developer's service run | The token `vault login` saved in `~/.vault-token` | Whatever the person's policy allows |

The package looks for the token in this order and uses the first that has a value: the `Token` setting, the `VAULT_TOKEN` environment variable, the `~/.vault-token` file.

**The prod Vault and the test Vault are separate servers** with their own addresses, accounts and tokens. Nothing is shared between them, and each reader only ever talks to its own: prod server to prod Vault, test server and developer machines to the test Vault. Two consequences for people:

- The login in `~/.vault-token` belongs to the test Vault. A prod login must not replace it; `vault-cli-setup.md` shows how to keep the prod token in a separate file (`vault login -no-store -token-only`).
- `scripts/vault_config.py` takes the two addresses separately (`--test-vault-address`, `--prod-vault-address`) and the prod token only from `VAULT_PROD_TOKEN` or `--prod-token-file`, never from `~/.vault-token`. An environment variable set in one terminal is not visible to a tool started from another, which is why the skill uses a file.

Root tokens do not belong in settings files, compose files or scripts that are committed. A server token needs a policy like this, one per service and environment:

```hcl
path "apps/data/pinqponq/test/chat-api" {
  capabilities = ["read"]
}
```

People get a policy that covers the records they maintain. Turn on a Vault audit device so that reads are recorded too; the version history only shows writes.

## Pitfalls that already happened

- **Arrays merge by index.** .NET merges an array defined in two places element by element. A shorter array in `appsettings.Development.json` keeps the remaining elements of the one in `appsettings.json`. Give every array exactly one home: the file when every reader sees the same list, otherwise the Vault records, each holding the complete list. `scripts/vault_config.py` detects this and reports it.
- **Developer addresses in the shared record.** Putting `localhost` or `10.0.0.1` into the record the test server reads breaks service-to-service calls inside containers. That is the reason for the separate `local` record.
- **Empty strings do not hide a value.** An empty string left in a Development file overrides the real value of `appsettings.json`. Remove keys when they move; do not blank them.
- **A removed secret is still in git history.** Moving a secret to Vault does not make the old value safe. Rotate it separately.
- **Package caching.** When the package is rebuilt locally with the same version number, NuGet keeps serving the cached copy. Clear `~/.nuget/packages/pinqponq.configuration.vault` after repacking.

## Rolling it out to a project

Use the skill; the order it follows is:

1. Record the git commit that holds the settings files from before the change (the baseline).
2. `scripts/vault_config.py plan`, review what would move, adjust with `--include` / `--exclude`. The script does not remember these flags: pass the same ones to every later `apply` and `verify`.
3. `scripts/vault_config.py apply --skip-prod` as a dry run, then with `--apply-changes`. This writes the `test` and `local` records only; the prod Vault is not contacted.
4. Add the package (`dotnet add package Pinqponq.Configuration.Vault`, newest stable version) and the `Program.cs` line to each service.
5. `scripts/vault_config.py verify --baseline-ref <commit> --skip-prod`: the `local` and `test` readers see what they saw before. Changes you made on purpose are acknowledged with `--accept-differences`, and stay listed in the output.
6. Build, then start a service on a developer machine with only `vault login` done.
7. Last, after testing, with a separate approval for prod and a prod token (`vault login -no-store -token-only`, see `vault-cli-setup.md`) saved in a file: `scripts/vault_config.py apply --only-prod --baseline-ref <commit> --prod-token-file <file>` (dry run first, then `--apply-changes`), then `verify --baseline-ref <commit> --prod-token-file <file>` without `--skip-prod`. Delete the file afterwards. `--baseline-ref` is needed here because the first `apply` already removed the values from the settings files.
8. Servers: set `VAULT_TOKEN` (and `DOTNET_ENVIRONMENT=Test` on the test server) before deploying.

Between steps 3 and 7 the settings files already point at the prod records, which do not exist yet: do not deploy that build to prod before step 7.

Leave the old records (and, on prod, the old secret location) in place until the new code is deployed and tested. Delete them only on the owner's explicit say-so; running prod code may still read them.
