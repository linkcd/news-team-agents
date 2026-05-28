# Git Troubleshooting Guide

## Issue: "There is no tracking information for the current branch"

### Symptoms
```bash
git pull
# Error: There is no tracking information for the current branch.
# Please specify which branch you want to merge with.
```

### Solution

Run this command to set the upstream tracking branch:

```bash
git branch --set-upstream-to=origin/main main
```

Then pull the changes:

```bash
git pull
```

### One-time Fix Alternative

Or merge the changes directly without setting upstream:

```bash
git pull origin main
```

### Verify Tracking is Set

After setting upstream, verify with:

```bash
git branch -vv
```

You should see:
```
* main [origin/main] <latest commit message>
```

The `[origin/main]` indicates tracking is properly configured.

### Why This Happens

This occurs when:
- The repository was cloned without proper tracking setup
- The branch was created locally before the remote branch existed
- The `.git/config` is missing the tracking configuration

### Permanent Fix

After running `git branch --set-upstream-to=origin/main main` once, future `git pull` commands will work normally without specifying the remote and branch.

## Other Common Issues

### Push Requires Upstream

If you see:
```
fatal: The current branch main has no upstream branch.
```

Use:
```bash
git push -u origin main
```

The `-u` flag sets the upstream for both pull and push.

### Multiple Remotes

To see all configured remotes:
```bash
git remote -v
```

To add a remote:
```bash
git remote add origin git@github.com:username/repo.git
```

### Check Current Configuration

View your git configuration:
```bash
git config --list --show-origin
```

View branch tracking:
```bash
git branch -vv
```
