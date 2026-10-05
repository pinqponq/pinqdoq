# Vault CLI setup for developers

What you need on your machine so that a pinqponq .NET project starts with its settings coming from Vault. About ten minutes. In a project that has pinq-doq delivered you can also ask Claude ("vault hesabım var, projeyi ayağa kaldırmak istiyorum"): the `pinq_vault-dev-setup` skill does these steps with you, and `vault_config.py check` tells you what is missing. Your own Vault account and its access come from the DevOps unit. The background is in [vault-configuration.md](vault-configuration.md).

You need three things: the VPN (the Vault servers are on the internal network), the Vault CLI, and your own Vault account.

## 1. Install the Vault CLI

```bash
# Windows
winget install --id Hashicorp.Vault --exact

# macOS
brew tap hashicorp/tap
brew install hashicorp/tap/vault
```

Linux and other options: https://developer.hashicorp.com/vault/install

**Close every terminal window and open a new one.** The installer adds `vault` to your PATH, but windows that were already open never see the change. On Windows Terminal, closing a tab is not enough: close the whole application. If `vault` is still not found after that, sign out of Windows and back in.

To fix a single open PowerShell window without restarting it:

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
```

Check the install:

```bash
vault version
```

## 2. Log in

Use the address of the **test Vault** and your own user name (ask the DevOps unit for an account if you do not have one):

```bash
vault login -address=http://10.0.0.1:8200 -method=userpass username=<your-user-name>
```

It asks for your password (nothing appears while you type). On success it prints `Success! You are now authenticated` and saves a token to `~/.vault-token` (`C:\Users\<you>\.vault-token` on Windows).

Nothing else needs to be configured. Every pinqponq project that uses `Pinqponq.Configuration.Vault` finds that file by itself.

How long the login lasts is set by the Vault server (the time to live of its tokens). When a service reports that Vault rejected the token, run the same command again.

## 3. Start a project

```bash
dotnet run --project <service project>
```

The service reads its settings from the `local` record of the test Vault. Workers need the `Development` environment; the launch profiles already set it. From a plain terminal:

```powershell
$env:DOTNET_ENVIRONMENT = 'Development'
dotnet run --project <worker project>
```

## Editing a setting

Open the Vault UI (http://10.0.0.1:8200), sign in with the **Username** method and your account, then go to `apps` > `pinqponq` > `local` (or `test`) > the service. Choose **Create new version**, change the value, save, and restart the service.

Every save is a new version and the version history shows who made it. Older versions stay, so a wrong edit is undone by restoring the previous version.

Never edit the `prod` folder without agreeing it with the team lead first.

## Logging in to the prod Vault (only when a prod write is agreed)

The prod Vault is a different server with its own accounts. Do not run the plain `vault login` against it: it would replace the test login in `~/.vault-token`, and your services would then send a prod token to the test Vault and be rejected. Save the prod token in a separate file instead. Run this in your own terminal; the password is typed there and never goes anywhere else. The flags must come before the `key=value` arguments.

```powershell
# Windows (PowerShell)
vault login -no-store -token-only -address=<prod address> -method=userpass username=<your prod user name> | Set-Content -Path "$HOME\.vault-token-prod" -NoNewline -Encoding ascii
```

```bash
# macOS
(umask 077; vault login -no-store -token-only -address=<prod address> -method=userpass username=<your prod user name> > ~/.vault-token-prod)
```

`-no-store` leaves `~/.vault-token` alone and `-token-only` prints just the token, which the redirect writes to the file. If the prod Vault has no user accounts yet, use `-method=token` instead of `-method=userpass username=...`; the CLI then asks for the token with the input hidden. A failed login leaves an empty file, which the tools report as a failed login.

Pass the file to `scripts/vault_config.py` with `--prod-token-file`; the `pinq_vault-config-setup` skill does this for you. Delete the file when the prod write is done (`Remove-Item "$HOME\.vault-token-prod"` or `rm ~/.vault-token-prod`); the token itself expires with Vault's time to live.

## When something goes wrong

| Message or symptom | Meaning | Fix |
|---|---|---|
| `vault` is not recognized | The terminal started before the install, or PATH was not refreshed | Close all terminals and open a new one; see step 1 |
| `No Vault token was found` | You have not logged in on this machine | Step 2 |
| `Vault at '...' rejected the token saved by the Vault CLI` | The login expired, was made against a different Vault server, or your policy cannot read this record | Log in again against the address shown in the message |
| `Vault is unreachable` | No VPN, wrong address, or the Vault server is down | Connect the VPN and open http://10.0.0.1:8200 in a browser |
| `Vault configuration record '...' does not exist` | The service has no record for your environment yet | Ask the DevOps unit (or whoever moved the project to Vault); the record is created with `scripts/vault_config.py` |
| `Vault configuration setting 'Path' is required` | A settings file is missing the `VaultConfiguration` section | Compare with another service's `appsettings.Development.json` |
| `permission denied` in the UI | Your policy does not cover that folder | Ask the DevOps unit for read access to `apps/data/<project>/local/*` |

Two safety notes. Never paste your token or password into chat, an issue or a commit; `vault login` keeps it in the file for you. And do not copy a root token into a settings file to "make it work": ask for access instead.
