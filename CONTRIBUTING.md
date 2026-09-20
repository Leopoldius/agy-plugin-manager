# Contributing

Contributions are welcome.

## Branch workflow

The repository uses two long-lived branches:

- `main` is the public release branch.
- `develop` is the integration branch for ongoing work.

External contributions should not target `main` directly.

Use this workflow:

1. Fork the repository.
2. Create your topic branch from the current `develop` branch.
3. Make and test your changes.
4. Push the topic branch to your fork.
5. Open a pull request with `develop` as the base branch.

Accepted changes are integrated into `develop` first. The maintainer promotes tested changes from `develop` to `main`.

## Pull requests

Keep pull requests focused on one change or closely related set of changes.

Please include:

- a short description of the problem or goal;
- a summary of the implementation;
- relevant test or verification notes;
- documentation updates when behavior or usage changes.

Pull requests opened directly against `main` may be closed and redirected to `develop`, except for maintainer release pull requests from `develop` to `main`.

## Ownership

Repository merges and release decisions are handled by the repository maintainer.

A `CODEOWNERS` file requests maintainer review for changes across the repository.
