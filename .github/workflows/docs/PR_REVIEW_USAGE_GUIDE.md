# Pull Request Review Process - User Guide

This document explains how to use and configure the automated PR review process in your repository.

## Overview

The PR review automation system automatically:

- Assigns appropriate reviewers and assignees to pull requests based on branch patterns
- Tracks required review approvals from specific teams
- Updates PR status checks based on review requirements
- Enforces branch protection rules

## How It Works

1. When a PR is opened or updated, the workflow triggers automatically
2. The system reads your repository's `REVIEWERS.yml` file
3. Based on the target branch, reviewers and assignees are assigned
4. As reviews come in, the system tracks which teams have approved
5. A status check shows whether all required approvals have been met

## Configuration: REVIEWERS.yml

The review process is configured through the `REVIEWERS.yml` file in your repository's root. This file defines team-based review requirements for different branches.

### Basic Structure

```yaml
pull_requests:
  branches:
    main:
      review_teams:
        - 'team-a-reviewers'
        - 'team-a-project-owners'
      assignees:
        - 'team-a-developers'
      required_approvals: 2
      required_teams:
        - 'team-a-reviewers'
        - 'team-a-operations'
```

### Configuration Options

#### Branch Patterns

You can use exact branch names or patterns with wildcards:

```yaml
branches:
  main:
    # Configuration for main branch
  "feature/*":
    # Configuration for all feature branches
  "release/*":
    # Configuration for all release branches
```

#### Team Variables

The system supports a `{{ team_name }}` variable that gets replaced with your repository's configured team name:

```yaml
review_teams:
  - '{{ team_name }}-reviewers'
  - '{{ team_name }}-project-owners'
```

#### Review Teams

Define which teams should be requested as reviewers:

```yaml
review_teams:
  - 'team-a-reviewers'
  - 'team-a-project-owners'
```

> **Important**: Teams specified in `review_teams` must be added as collaborators to the repository with at least "Read" permissions before they can be assigned as reviewers. GitHub will silently ignore review requests for teams that don't have repository access.

#### Assignees

Define which teams should be assigned to the PR:

```yaml
assignees:
  - 'team-a-developers'
```

#### Required Approvals

Set the minimum number of approvals needed:

```yaml
required_approvals: 2
```

#### Required Teams

Specify which teams must approve before the PR can be merged:

```yaml
required_teams:
  - 'team-a-reviewers'
  - 'team-a-operations'
```

#### Exclusions

Exclude specific branches from a pattern:

```yaml
"feature/*":
  # Configuration here
  exclude:
    - "feature/do-not-assign"
```

### Example: Complete Configuration

```yaml
pull_requests:
  branches:
    main:
      review_teams:
        - '{{ team_name }}-reviewers'
        - '{{ team_name }}-project-owners'
      assignees:
        - '{{ team_name }}-developers'
      required_approvals: 2
      required_teams:
        - '{{ team_name }}-reviewers'
        - '{{ team_name }}-operations'
    
    "feature/*":
      review_teams:
        - '{{ team_name }}-testers'
        - '{{ team_name }}-developers'
      assignees:
        - '{{ team_name }}-developers'
      required_approvals: 1
      required_teams:
        - '{{ team_name }}-reviewers'
      exclude:
        - "feature/do-not-assign"
```

## Team Structure Requirements

For the review system to work properly, your organization should have teams set up following this pattern:

1. **Base team name**: Configured as the `TEAM_NAME` repository variable
2. **Role-specific teams**: Append roles to the base name (e.g., `-reviewers`, `-developers`)

Example team structure:
- `team-a-reviewers`
- `team-a-developers`
- `team-a-project-owners`
- `team-a-operations`

## Status Checks

The workflow adds a status check called `pr-review-requirements` that shows:
- ✅ **Success**: All required team approvals have been received
- ⏱️ **Pending**: Still waiting for required team approvals

## Troubleshooting

### Common Issues

1. **No reviewers assigned**: Check that your teams exist and have the exact names specified in REVIEWERS.yml
2. **Status check not updating**: Ensure the workflow has proper permissions to create status checks
3. **Wrong teams assigned**: Verify the `TEAM_NAME` repository variable is set correctly

### Logs and Debugging

If you need to troubleshoot the review process:

1. Check the Actions tab in your repository
2. Find the "Pull Request Approval Workflow" run
3. View the logs for detailed information about the review assignment process
