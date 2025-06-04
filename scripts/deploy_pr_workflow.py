import os
import random
import sys
import time

from github import Github
from github import GithubException


def set_team_name_variable(requester, full_repo_name, team_name):
    """Set the TEAM_NAME repository variable."""
    try:
        url = f"https://api.github.com/repos/{full_repo_name}/actions/variables"
        data = {"name": "TEAM_NAME", "value": team_name}

        try:
            requester.requestJson("POST", url, input=data)
            print(f"Created TEAM_NAME variable with value '{team_name}' in {full_repo_name}")
        except GithubException as e:
            # If variable already exists (typically 422 error), update it
            if e.status == 422 or "already exists" in str(e).lower():
                url = f"https://api.github.com/repos/{full_repo_name}/actions/variables/TEAM_NAME"
                requester.requestJson("PATCH", url, input={"value": team_name})
                print(f"Updated TEAM_NAME variable to '{team_name}' in {full_repo_name}")
            else:
                print(f"Error creating TEAM_NAME variable: {str(e)}")
    except Exception as var_error:
        print(f"Failed to set TEAM_NAME variable in {full_repo_name}: {str(var_error)}")


def create_or_get_branch(target_repo, default_branch, feature_branch_name):
    """Create or get feature branch with error handling."""
    branch_created = False

    # Check if branch exists
    try:
        target_repo.get_branch(feature_branch_name)
        print(f"Branch {feature_branch_name} already exists in {target_repo.full_name}")
        return True, feature_branch_name
    except GithubException as branch_error:
        if branch_error.status != 404:
            # Unexpected error
            print(f"Error checking branch: {branch_error.data.get('message', str(branch_error))}")
            return False, feature_branch_name

    # Branch doesn't exist, create it
    max_retries = 3
    retry_count = 0
    current_branch_name = feature_branch_name

    while retry_count < max_retries and not branch_created:
        try:
            # Get the latest commit on default branch
            try:
                default_branch_ref = target_repo.get_git_ref(f"heads/{default_branch}")
                base_sha = default_branch_ref.object.sha
                print(f"Got base SHA {base_sha} from default branch reference")
            except Exception as ref_error:
                print(f"Couldn't get ref directly: {str(ref_error)}, trying commits API")
                # Fallback to commits API
                default_branch_commits = target_repo.get_commits(sha=default_branch, per_page=1)
                if default_branch_commits.totalCount == 0:
                    print(f"No commits found in {target_repo.full_name}'s {default_branch} branch")
                    raise ValueError("No commits found in default branch") from ref_error

                base_sha = default_branch_commits[0].sha

            print(f"Creating branch {current_branch_name} from commit {base_sha} in {target_repo.full_name}")

            # Generate a unique branch name to avoid conflicts
            if retry_count > 0:
                current_branch_name = f"{feature_branch_name}-{random.randint(1000, 9999)}"
                print(f"Retry {retry_count}: Using unique branch name: {current_branch_name}")

            # Create the branch
            ref = f"refs/heads/{current_branch_name}"
            target_repo.create_git_ref(ref=ref, sha=base_sha)
            print(f"Successfully created branch {current_branch_name} in {target_repo.full_name}")
            branch_created = True

            # Small delay to ensure branch is available
            time.sleep(3)

        except GithubException as create_error:
            error_message = str(create_error.data) if hasattr(create_error, "data") else str(create_error)

            if create_error.status == 422 and "Reference already exists" in error_message:
                print(f"Branch {current_branch_name} already exists in {target_repo.full_name}")
                branch_created = True
                break

            if "Reference update failed" in error_message:
                retry_count += 1
                wait_time = 2 * retry_count  # Exponential backoff
                print(f"Reference update failed. Retrying in {wait_time} seconds... ({retry_count}/{max_retries})")
                print(f"Full error: {error_message}")
                time.sleep(wait_time)
            else:
                print(f"Failed to create branch: {error_message}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    wait_time = 2 * retry_count
                    print(f"Retrying in {wait_time} seconds... ({retry_count}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    break

        except Exception as general_error:
            print(f"Unexpected error creating branch: {str(general_error)}")
            if retry_count < max_retries - 1:
                retry_count += 1
                wait_time = 2 * retry_count
                print(f"Retrying in {wait_time} seconds... ({retry_count}/{max_retries})")
                time.sleep(wait_time)
            else:
                break

    if not branch_created:
        print(f"Failed to create branch after {max_retries} attempts. Skipping {target_repo.full_name}")

    return branch_created, current_branch_name


def handle_file_operations(target_repo, source_repo, feature_branch_name, default_branch):
    """Handle creation and updating of workflow files."""
    # Get file contents from source repo
    workflow_content = source_repo.get_contents(".github/workflows/Pull-Request-Approval-Workflow.yml")
    workflow_path = ".github/workflows/Pull-Request-Approval-Workflow.yml"

    pr_script_content = source_repo.get_contents("scripts/pr_review_manager.py")
    pr_script_path = "scripts/pr_review_manager.py"

    reviewers_content = source_repo.get_contents("REVIEWERS.yml")
    reviewers_path = "REVIEWERS.yml"

    # Update or create workflow file
    try:
        existing_workflow = target_repo.get_contents(workflow_path, ref=feature_branch_name)
        target_repo.update_file(
            workflow_path,
            "Update Pull Request Approval Workflow",
            workflow_content.decoded_content.decode("utf-8"),
            existing_workflow.sha,
            branch=feature_branch_name,
        )
    except Exception:
        target_repo.create_file(
            workflow_path,
            "Add Pull Request Approval Workflow",
            workflow_content.decoded_content.decode("utf-8"),
            branch=feature_branch_name,
        )

    # Handle PR review manager script
    handle_pr_script(target_repo, pr_script_content, pr_script_path, feature_branch_name)

    # Handle REVIEWERS.yml
    handle_reviewers_file(target_repo, reviewers_content, reviewers_path, feature_branch_name, default_branch)


def handle_pr_script(target_repo, pr_script_content, pr_script_path, feature_branch_name):
    """Handle the PR review manager script file."""
    try:
        existing_script = target_repo.get_contents(pr_script_path, ref=feature_branch_name)
        target_repo.update_file(
            pr_script_path,
            "Update PR Review Manager Script",
            pr_script_content.decoded_content.decode("utf-8"),
            existing_script.sha,
            branch=feature_branch_name,
        )
        print(f"Updated PR Review Manager script in {target_repo.full_name}")
    except Exception:
        # Create scripts directory if it doesn't exist
        try:
            target_repo.get_contents("scripts", ref=feature_branch_name)
        except Exception:
            print(f"Creating scripts directory in {target_repo.full_name}")
            target_repo.create_file(
                "scripts/.gitkeep",
                "Create scripts directory",
                "",
                branch=feature_branch_name,
            )

        # Create the script file
        target_repo.create_file(
            pr_script_path,
            "Add PR Review Manager Script",
            pr_script_content.decoded_content.decode("utf-8"),
            branch=feature_branch_name,
        )
        print(f"Added PR Review Manager script to {target_repo.full_name}")


def handle_reviewers_file(target_repo, reviewers_content, reviewers_path, feature_branch_name, default_branch):
    """Handle the REVIEWERS.yml file - only create if it doesn't exist."""
    try:
        # Check if REVIEWERS.yml exists in any branch
        try:
            # First check in feature branch
            target_repo.get_contents(reviewers_path, ref=feature_branch_name)
            print(f"REVIEWERS.yml already exists in feature branch of {target_repo.full_name}, preserving it")
        except Exception:
            # Then check in default branch
            try:
                target_repo.get_contents(reviewers_path, ref=default_branch)
                print(f"REVIEWERS.yml already exists in default branch of {target_repo.full_name}, preserving it")
            except Exception:
                # File doesn't exist in either branch, create it
                target_repo.create_file(
                    reviewers_path,
                    "Add REVIEWERS.yml",
                    reviewers_content.decoded_content.decode("utf-8"),
                    branch=feature_branch_name,
                )
                print(f"Added REVIEWERS.yml to {target_repo.full_name}")
    except Exception as e:
        print(f"Error handling REVIEWERS.yml: {str(e)}")


def create_or_check_pr(target_repo, org_name, feature_branch_name, default_branch, team_name):
    """Create a pull request if one doesn't exist."""
    # Update PR body to include info about TEAM_NAME variable
    pr_body = "Automated PR to deploy the Pull Request Approval Workflow and related configuration\n\n"
    pr_body += f"## Team Configuration\n\n"
    pr_body += f"This workflow is configured to use team: `{team_name}`\n\n"
    pr_body += f"A repository variable `TEAM_NAME` has been set with this value.\n"
    pr_body += f"You can change this in repository settings if needed.\n\n"

    # Check if PR already exists
    open_prs = target_repo.get_pulls(state="open", head=f"{org_name}:{feature_branch_name}", base=default_branch)
    pr_exists = open_prs.totalCount > 0

    if not pr_exists:
        # Create PR with updated body
        pr = target_repo.create_pull(
            title="Deploy Pull Request Approval Workflow",
            body=pr_body,
            head=feature_branch_name,
            base=default_branch,
        )
        print(f"Created PR #{pr.number} in {target_repo.full_name}")
    else:
        print(f"PR already exists in {target_repo.full_name}")


def process_repository(g, source_repo, full_repo_name, team_name, org_name):
    """Process a single repository."""
    try:
        target_repo = g.get_repo(full_repo_name)
        print(f"Processing repository: {full_repo_name} with team: {team_name}")

        # Set TEAM_NAME repository variable
        set_team_name_variable(g._Github__requester, full_repo_name, team_name)

        # Get default branch
        default_branch = target_repo.default_branch
        feature_branch_name = "feature/push_new_pr_update"

        # Create or get feature branch
        branch_created, feature_branch_name = create_or_get_branch(target_repo, default_branch, feature_branch_name)

        if not branch_created:
            return

        # Handle file operations
        handle_file_operations(target_repo, source_repo, feature_branch_name, default_branch)

        # Create or check for PR
        create_or_check_pr(target_repo, org_name, feature_branch_name, default_branch, team_name)

        print(f"Successfully deployed to {full_repo_name}")
    except Exception as e:
        print(f"Failed to deploy to {full_repo_name}: {str(e)}")


def deploy_workflow_and_config(target_repositories_input, default_team_name="Cloud-Platform-Owners"):
    """Deploy workflow and configuration to target repositories."""
    token = os.getenv("GITHUB_TOKEN")
    g = Github(token)
    source_repo = g.get_repo(os.getenv("GITHUB_REPOSITORY"))
    org_name = os.getenv("GITHUB_REPOSITORY").split("/")[0]

    # Parse repositories and team names
    repositories = parse_repositories(target_repositories_input, org_name, default_team_name)

    for full_repo_name, team_name in repositories:
        process_repository(g, source_repo, full_repo_name, team_name, org_name)


def parse_repositories(target_repositories_input, org_name, default_team_name):
    """Parse the repository input string into a list of (repo_name, team_name) tuples."""
    repositories = []
    for repo_entry in target_repositories_input.split(","):
        repo_entry = repo_entry.strip()
        if ":" in repo_entry:
            repo_name, team_name = repo_entry.split(":", 1)
            repo_name = repo_name.strip()
            team_name = team_name.strip()
        else:
            repo_name = repo_entry.strip()
            team_name = default_team_name

        # Ensure repo name is fully qualified with org name
        if "/" not in repo_name:
            full_repo_name = f"{org_name}/{repo_name}"
        else:
            full_repo_name = repo_name

        repositories.append((full_repo_name, team_name))

    return repositories


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: deploy_pr_workflow.py <comma-separated list of target repositories> [default_team_name]")
        sys.exit(1)

    default_team_name = "Cloud-Platform-Owners"
    if len(sys.argv) > 2:
        default_team_name = sys.argv[2]

    deploy_workflow_and_config(sys.argv[1], default_team_name)
