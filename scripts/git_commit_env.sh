#!/usr/bin/env bash
# Source before git commit in this repo (agent-safe; does not touch ~/.gitconfig).
# Usage: source scripts/git_commit_env.sh && git commit ...
export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-naeemxnorabbasi}"
export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-naeemxnorabbasi@gmail.com}"
export GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-$GIT_AUTHOR_NAME}"
export GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-$GIT_AUTHOR_EMAIL}"
