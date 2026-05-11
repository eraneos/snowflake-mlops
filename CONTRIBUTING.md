# Contributing

Actual contributions to the reference repo are welcome, and so are general questions about Snowflake ML and MLOps that are not necessarily tied to a change here.

## Contributions to this repo

Pull requests against the reference patterns themselves: a new project under `projects/`, an alternative feature store layout, a different DAG runtime, monitoring add-ons, doc corrections, ADR rebuttals. The most valuable PRs are usually the ones that surface gaps or things we got wrong.

Criticism and design challenges are welcome.

## Questions, including ones not specific to this repo

The maintainers work professionally on Snowflake ML and MLOps and have run into most of the friction the platform produces. If you are stuck getting Snowflake ML to work in your own setup, designing a feature store, debugging a Tasks DAG, or sanity-checking an architecture decision, open an issue. We would rather have the conversation than have you struggle in private, and the answer often becomes useful context for a future contribution to this repo.

Topics adjacent to Snowflake MLOps are in scope even if the answer is "this repo does not cover that yet."

## Ways to engage

- **Pull request.** Code, or docs changes. See the DCO section below for the signoff requirement.
- **Issue.** Questions, bug reports, design challenges, "how would you handle X" prompts. No formatting requirements at this stage.
- **Direct contact.** If an issue feels too formal, email the maintainers.

We do not yet ship pull request or issue templates. They will arrive once we see what kinds of contributions actually come in.

## Developer Certificate of Origin

This project requires that all contributions be signed off under the [Developer Certificate of Origin](https://developercertificate.org/) (DCO). The DCO is a lightweight statement that you wrote the contribution or otherwise have the right to submit it under this project's Apache 2.0 license. There is no separate document to sign; the certification lives in each commit's metadata.

We use the DCO instead of a Contributor License Agreement (CLA). The DCO is less friction for contributors and produces a permanent in-history record without a separate signature database.

### How to sign off

Add a `Signed-off-by` line to every commit message. The name and email must match the commit's author.

```
Signed-off-by: Jane Doe <jane@example.com>
```

The easiest way is the `-s` flag on commit:

```sh
git commit -s -m "Your commit message"
```

To make this automatic for this repo, run once after cloning:

```sh
git config format.signoff true
```

### Recovery

If you forget to sign off a single commit:

```sh
git commit --amend -s --no-edit
git push --force-with-lease
```

For multiple commits on a branch:

```sh
git rebase --signoff HEAD~N      # N = number of commits to re-sign
git push --force-with-lease
```

### Web UI commits

When you edit files directly on github.com, the web editor cannot add a signoff. The DCO bot provides a link to sign off retroactively, or you can comment `/dco` on the pull request.

### Identity

DCO applies to the commit's author identity, not your GitHub account. The `Signed-off-by` email must match the commit's author email. It does not need to match your GitHub username, and if your local git is configured with a different email than your GitHub login the check still passes.

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
