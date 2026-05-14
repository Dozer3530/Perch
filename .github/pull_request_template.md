# Summary

<!-- One or two sentences: what does this change do, and why? -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / cleanup (no behaviour change)
- [ ] Documentation
- [ ] Build / CI
- [ ] Other

## How was it tested?

<!--
For code changes:
  - Ran `pytest` locally  (✔ all green / output below)
  - Tried the GUI: <what you clicked>
  - For sorter changes: ran on a real flight folder and confirmed counts

For doc-only or CI-only changes: say so and skip.
-->

## Checklist

- [ ] `pytest` passes locally
- [ ] If a new sensor preset was added, the band map was confirmed against the
      manufacturer's documentation
- [ ] If a new runtime dependency was added, it's discussed in the PR
      description and added to `requirements.txt`
- [ ] If user-visible behaviour changed, the README is updated
- [ ] `perch/__init__.py` `__version__` was bumped if a release is intended
