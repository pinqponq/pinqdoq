# Packages: where they are published and where they come from

The company runs its own package server, a Nexus Repository at `https://nexus.pinqponq.io`. This document says which of our packages go to Nexus and which go to a public registry, how a project downloads them, and how a library publishes them. The `pinq_nexus-packages` skill applies the Gradle parts to a project.

## Where each package goes

| Package | Published to | Downloaded from |
|---|---|---|
| Kotlin / Maven libraries (`global.deveng:*` from deveng-core-kmp and deveng-networking-kmp, `io.pinqponq:*` such as pinqpos-SDK) | Nexus | Nexus |
| `pinqnuqets` (.NET, `Pinqponq.*`) | nuget.org | nuget.org |
| Any other shared .NET package that is not part of `pinqnuqets` | Nexus | Nexus |
| npm | not in use yet | not in use yet |

Maven Central no longer receives new versions of our Maven libraries: Sonatype limits how many files an organization may upload per month, and a Kotlin Multiplatform release uploads hundreds of files (one set per platform, each with signature and checksum files). Versions already on Maven Central stay there, and Nexus also serves them (see "Repositories").

Nexus allows no anonymous access. A new version is therefore not available to people outside the company. Say so in a library's README when you move it.

## Repositories

Nexus groups several repositories behind one address. A project downloads from the group address and never from a single repository.

| Format | Download from (group) | Publish to | What the group contains |
|---|---|---|---|
| Maven | `https://nexus.pinqponq.io/repository/maven-public/` | Releases: `.../maven-releases/`<br>Versions ending in `-SNAPSHOT`: `.../maven-snapshots/` | `maven-releases`, `maven-snapshots`, and a cache of Maven Central (`maven-central`) |
| NuGet | `https://nexus.pinqponq.io/repository/nuget-group/index.json` | `https://nexus.pinqponq.io/repository/nuget-hosted/` | `nuget-hosted` and a cache of nuget.org |
| npm | `https://nexus.pinqponq.io/repository/npm-group/` | `https://nexus.pinqponq.io/repository/npm-hosted/` | `npm-hosted` and a cache of registry.npmjs.org |

Rules that the server enforces:

- A release version is accepted once. Publishing the same version again fails with HTTP 400, so a fix gets a new version number.
- A `-SNAPSHOT` version can be published again. Snapshots that nobody downloaded for 30 days are deleted.
- One upload (one file) may be at most 100 MB, because Nexus sits behind Cloudflare.
- Cached packages from Maven Central, nuget.org and npm that nobody downloaded for 180 days are removed from the cache. They come back on the next download.

## Accounts and secrets

| Who | Account | Can do |
|---|---|---|
| A developer | their own Nexus account with the `pinq-developer` role | download from every repository |
| CI of an app (only downloads) | a shared read-only account | download from every repository |
| CI of a library (publishes) | the shared deploy account with the `pinq-deployer` role | download from every repository, upload to `maven-releases`, `maven-snapshots`, `nuget-hosted` and `npm-hosted` |

Accounts come from the DevOps unit. A password is never written into a repository, a build file, a script or a chat.

Gradle reads the credentials from two Gradle properties, `nexusUsername` and `nexusPassword`:

- **Developer machine:** in the user-wide file `~/.gradle/gradle.properties` (Windows: `%USERPROFILE%\.gradle\gradle.properties`), never in the project's own `gradle.properties`:
  ```properties
  nexusUsername=<your Nexus user name>
  nexusPassword=<your Nexus password>
  ```
- **GitHub Actions:** as environment variables, which Gradle turns into the same properties. The organization secrets are `NEXUS_USERNAME` / `NEXUS_PASSWORD` (the read-only account, for every repository) and `NEXUS_DEPLOY_USERNAME` / `NEXUS_DEPLOY_PASSWORD` (the deploy account, only for library repositories):
  ```yaml
  env:
    ORG_GRADLE_PROJECT_nexusUsername: ${{ secrets.NEXUS_USERNAME }}
    ORG_GRADLE_PROJECT_nexusPassword: ${{ secrets.NEXUS_PASSWORD }}
  ```

## Download our Maven libraries in a Gradle project

Add Nexus to both repository blocks of `settings.gradle.kts`. `exclusiveContent` makes Gradle fetch our groups only from Nexus and everything else from where it came before, so a build does not send every dependency request to Nexus. The `pluginManagement` block is needed because the `global.deveng.testing` Gradle plugin is also one of our packages.

```kotlin
// settings.gradle.kts
pluginManagement {
    repositories {
        // the existing google { ... }, mavenCentral(), gradlePluginPortal() stay
        exclusiveContent {
            forRepository {
                maven("https://nexus.pinqponq.io/repository/maven-public/") {
                    name = "nexus"
                    credentials(PasswordCredentials::class)
                }
            }
            filter {
                includeGroupAndSubgroups("global.deveng")
                includeGroupAndSubgroups("io.pinqponq")
            }
        }
    }
}

dependencyResolutionManagement {
    repositories {
        // the existing google { ... } and mavenCentral() stay
        exclusiveContent {
            forRepository {
                maven("https://nexus.pinqponq.io/repository/maven-public/") {
                    name = "nexus"
                    credentials(PasswordCredentials::class)
                }
            }
            filter {
                includeGroupAndSubgroups("global.deveng")
                includeGroupAndSubgroups("io.pinqponq")
            }
        }
    }
}
```

- `name = "nexus"` is what makes `credentials(PasswordCredentials::class)` read `nexusUsername` and `nexusPassword`.
- `includeGroupAndSubgroups` needs Gradle 8.1 or newer.
- Old versions that exist only on Maven Central still resolve, because `maven-public` contains a cache of Maven Central.
- A composite build (`includeBuild("../deveng-core-kmp")`, see `rules/kotlin-conventions.md`) still replaces the library with the local copy. Nexus is only asked when the library is not included.

## Publish a Maven library to Nexus

The libraries use the `com.vanniktech.maven.publish` plugin. Keep `coordinates` and `pom` as they are, remove the Maven Central parts, and add Nexus as a Gradle publishing repository. Do this in every module that publishes.

```kotlin
// <module>/build.gradle.kts
mavenPublishing {
    // removed: publishToMavenCentral(SonatypeHost.CENTRAL_PORTAL)
    // removed: signAllPublications() — Nexus does not require signed files, and signing needs GPG keys in CI
    coordinates(group.toString(), "core-kmp", version.toString())
    pom { /* unchanged */ }
}

publishing {
    repositories {
        maven {
            name = "nexus"
            val targetRepository = if (version.toString().endsWith("-SNAPSHOT")) "maven-snapshots" else "maven-releases"
            url = uri("https://nexus.pinqponq.io/repository/$targetRepository/")
            credentials(PasswordCredentials::class)
        }
    }
}
```

Also remove the `import com.vanniktech.maven.publish.SonatypeHost` line when nothing uses it any more.

Publish every module with:

```bash
./gradlew publishAllPublicationsToNexusRepository --no-configuration-cache
```

Before publishing for real, prove the build with `./gradlew publishToMavenLocal`. It writes to `~/.m2/repository` and uploads nothing.

A GitHub Actions publish job replaces its Maven Central step with:

```yaml
- name: Publish to Nexus
  run: ./gradlew publishAllPublicationsToNexusRepository --no-configuration-cache
  env:
    ORG_GRADLE_PROJECT_nexusUsername: ${{ secrets.NEXUS_DEPLOY_USERNAME }}
    ORG_GRADLE_PROJECT_nexusPassword: ${{ secrets.NEXUS_DEPLOY_PASSWORD }}
```

The old `MAVEN_CENTRAL_*` and signing secrets are then no longer used by the job.

## .NET packages that are not part of pinqnuqets

`pinqnuqets` keeps publishing to nuget.org and nothing below applies to it. A shared .NET package outside `pinqnuqets` publishes to Nexus:

```bash
dotnet nuget push <Package>.nupkg --source https://nexus.pinqponq.io/repository/nuget-hosted/ --api-key <NuGet API key>
```

The NuGet API key belongs to the publishing account. The account's owner creates it in the Nexus web interface (user menu, **NuGet API Key**); in CI it is a secret.

A project that downloads such a package adds the group as a source in its `nuget.config`. The credentials come from environment variables, never from the file:

```xml
<configuration>
  <packageSources>
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
    <add key="nexus" value="https://nexus.pinqponq.io/repository/nuget-group/index.json" />
  </packageSources>
  <packageSourceMapping>
    <packageSource key="nuget.org"><package pattern="*" /></packageSource>
    <packageSource key="nexus"><package pattern="<Private.Package.Prefix>.*" /></packageSource>
  </packageSourceMapping>
  <packageSourceCredentials>
    <nexus>
      <add key="Username" value="%NEXUS_USERNAME%" />
      <add key="ClearTextPassword" value="%NEXUS_PASSWORD%" />
    </nexus>
  </packageSourceCredentials>
</configuration>
```

`packageSourceMapping` sends only the private package names to Nexus, the same way `exclusiveContent` does in Gradle.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Gradle says the `nexusUsername` or `nexusPassword` property is missing | No credentials on this machine or in this CI job | Add them to `~/.gradle/gradle.properties`, or set the `ORG_GRADLE_PROJECT_*` variables in the job |
| HTTP 401 | Wrong user name or password, or the account is disabled | Check the values; ask the DevOps unit if the account is disabled |
| HTTP 403 on publish | The account may download but not upload | Publishing uses the deploy account, not a personal or read-only one |
| HTTP 400 on publish | This release version is already in `maven-releases` | Raise the version number |
| HTTP 413, or an upload stops around 100 MB | The file is larger than Cloudflare allows | Split the artifact or ask the DevOps unit |
| `Could not find global.deveng:...` | The version was never published to Nexus or to Maven Central | Check the version in the Nexus web interface (Browse, `maven-public`) |
