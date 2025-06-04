# Pull Request Review Process - Deployment Guide

This document explains how to deploy and maintain the PR review process across multiple repositories.

## System Components

The PR review system consists of:

1. `Pull-Request-Approval-Workflow.yml` - GitHub Actions workflow 
2. `pr_review_manager.py` - Python script that handles the review logic
3. `REVIEWERS.yml` - Configuration file for team-based review rules
4. `deploy_pr_workflow.py` - Deployment script to add the review system to repositories

## Prerequisites

Before deploying the review system, ensure:

1. **GitHub App**: Create a GitHub App with repository and PR permissions
2. **Organization Teams**: Set up teams for reviewers, developers, etc.
3. **Python Environment**: Have Python 3.8+ with PyGithub installed
4. **Repository Variables**: Set up the following secrets/variables in the source repository:
   - `APP_ID`: GitHub App ID
   - `APP_KEY`: GitHub App private key
   - `PR_APP_ID`: GitHub App ID for PR operations
   - `PR_APP_KEY`: GitHub App private key for PR operations
5. **Branch Protection Configuration**: Ensure your branch protection rules allow the deployment:
   - If you have branch protection rules for `feature/*` branches, you must exclude `feature/push_new_pr_update*` 
   - This exclusion is necessary because the deployment process creates this branch

## Branch Protection Requirements

For successful deployment across repositories with branch protection:

1. **Exclude Deployment Branch**: In any repository with branch protection on `feature/*` patterns, add an exclusion for:
   - `feature/push_new_pr_update`
   - `feature/push_new_pr_update-*` (to cover randomly generated branch names when retrying)

2. **Example Branch Protection Configuration**:
   ```yaml
   - name: feature-branch-protection
     target: branch
     enforcement: active
     conditions:
       ref_name:
         include: ["refs/heads/feature/*"]
         exclude: ["refs/heads/feature/push_new_pr_update*"]  # Allow deployment branch
     rules:
       # Your protection rules here
   ```

3. **Organization-wide Settings**: If using organization-wide branch protection settings, ensure:
   - The GitHub App used for deployment has branch protection bypass permissions, OR
   - The pattern `feature/push_new_pr_update*` is excluded from protection rules

Failing to configure these exclusions will result in branch creation errors during deployment.

## Deployment Options

### Option 1: Using the GitHub Action

Use the `deploy-pr-workflow.yml` workflow from the GitHub Actions UI:

1. Navigate to the Actions tab
2. Select "Deploy PR Workflow and Config"
3. Click "Run workflow"
4. Enter parameters:
   - `target_repositories`: Comma-separated list of repos (e.g., `repo1:team1,repo2:team2`)
   - `default_team_name`: Default team name if not specified per repository

### Option 2: Using the Command Line

Run the deployment script directly:

```bash
# Set GitHub token
export GITHUB_TOKEN=your_token
export GITHUB_REPOSITORY=your_org/your_repo

# Deploy to multiple repositories
python scripts/deploy_pr_workflow.py "repo1:team1,repo2:team2" "Default-Team-Name"
```

## Deployment Process

When you deploy the PR review system:

1. A feature branch is created in each target repository
2. The workflow file, Python script, and REVIEWERS.yml are added/updated
3. A PR is opened to merge these changes into the target repository
4. A repository variable `TEAM_NAME` is set based on your input

## Configuration Parameters

### Repository Target Format

The `target_repositories` parameter accepts the following format:
```
repo1:team1,repo2:team2,repo3
```

Where:
- `repo1`, `repo2`, etc. are repository names
- `team1`, `team2`, etc. are the base team names for each repository
- Repositories without a team name use the default team name

### GitHub App Requirements

The GitHub App used for deployment needs these permissions:
- Repository contents: Read & write
- Pull requests: Read & write
- Actions variables: Read & write

## Maintaining the System

### Updating the Review Logic

To update the review logic across all repositories:

1. Make changes to `pr_review_manager.py` in the source repository
2. Run the deployment workflow to push updates to all target repositories

### Updating the Workflow File

To update the GitHub Actions workflow:

1. Modify `Pull-Request-Approval-Workflow.yml` in the source repository
2. Run the deployment workflow to push updates to all target repositories

### Changing Default Configuration

To change the default review configuration:

1. Update `REVIEWERS.yml` in the source repository
2. Run the deployment workflow to push the new configuration to target repositories

## Troubleshooting Deployment

### Common Deployment Issues

1. **Branch creation failures**: Check that your token has repository creation permissions
2. **Variable setting failures**: Ensure your token has permission to set repository variables
3. **PR creation failures**: Verify your token has pull request creation permissions
4. **"Reference update failed" errors**: Verify branch protection rules exclude `feature/push_new_pr_update*`

### Deployment Logs

The deployment script provides detailed logs for each step:

1. Check the Actions tab for the "Deploy PR Workflow and Config" workflow run
2. Review logs for specific error messages
3. For manual deployments, check the console output

### Retry Mechanisms

The deployment script includes retry logic for common issues:
- Branch creation retries with exponential backoff
- Unique branch name generation if conflicts occur
- Proper error handling for existing files/PRs

## Best Practices

1. **Test on a single repository** before deploying to multiple repositories
2. **Review PR content** in target repositories before merging
3. **Set up branch protection rules** to prevent bypassing the review requirements
4. **Document team structure** to ensure reviewers know their responsibilities
5. **Monitor initial deployments** to ensure the system works as expected
