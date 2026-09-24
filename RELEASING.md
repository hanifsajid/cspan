# Releasing to PyPI

Releases are published automatically by `.github/workflows/publish.yml` when a
GitHub Release is created. PyPI's *trusted publishing* means no API token is
stored anywhere.

## One-time setup

1. **Create a PyPI account** at https://pypi.org/account/register/ and enable
   two-factor authentication (required for new projects).
2. **Register the pending publisher** at
   https://pypi.org/manage/account/publishing/ with:
   - PyPI project name: `cspan`
   - Owner: `hanifsajid`
   - Repository: `cspan`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
3. **Create the `pypi` environment** in GitHub: repo Settings -> Environments ->
   New environment -> `pypi`. Optionally add yourself as a required reviewer
   so every upload needs a manual approval click.
4. (Optional) Repeat steps 1-3 on https://test.pypi.org to rehearse a release.

## Every release

1. Bump `__version__` in `src/cspan/_version.py` (the single source of truth;
   `pyproject.toml` reads it dynamically).
2. Move the `[Unreleased]` items in `CHANGELOG.md` under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading.
3. On the first PyPI release, replace the "not yet published to PyPI" notes in
   `README.md` and `docs/index.md` with `pip install cspan`.
4. Commit, then tag and push:

       git commit -am "Release vX.Y.Z"
       git tag vX.Y.Z
       git push && git push --tags

5. On GitHub, **Releases -> Draft a new release**, choose the tag, paste the
   changelog section, and click **Publish release**. The workflow builds the
   sdist and wheel, checks that the tag matches the package version, and uploads
   to PyPI. Watch it under the Actions tab.

## Verify locally first (recommended)

    pip install build twine
    python -m build            # writes dist/cspan-X.Y.Z.tar.gz and .whl
    twine check dist/*         # validates metadata and the README rendering

    # Install the wheel into a clean venv and smoke-test it
    python -m venv /tmp/cspan-check && /tmp/cspan-check/bin/pip install dist/*.whl
    /tmp/cspan-check/bin/python -c "import cspan; print(cspan.__version__)"

## Manual upload (fallback)

If you ever need to upload without GitHub Actions, create a *project-scoped*
API token at https://pypi.org/manage/account/token/ and run:

    twine upload dist/*

Enter `__token__` as the username and the token as the password. Never commit
the token or put it in `.env` files that could be tracked.
