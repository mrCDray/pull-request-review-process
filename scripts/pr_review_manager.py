import os
import re
from typing import Dict, List, Optional
import yaml
from github import Github
from github.GithubException import GithubException


class PRReviewManager:
    def __init__(self, github_token: str, repository: str, pr_number: int):
        """Initialize the PR Review Manager."""
        self.gh = Github(github_token)
        self.repo = self.gh.get_repo(repository)
        self.pr_number = pr_number
        self.pr = self.repo.get_pull(pr_number)
        self.config = self._load_config()
        self.org = self.repo.organization

    def _load_config(self) -> Dict:
        """Load the REVIEWERS.yml configuration file from PR's head branch."""
        try:
            # Get the PR's head branch ref and sha
            head_sha = self.pr.head.sha
            print(
                f"Debug: Looking for REVIEWERS.yml in PR #{self.pr_number} head branch: {self.pr.head.ref} (SHA: {head_sha})"
            )

            try:
                # Try to get the file from the PR's head branch
                config_file = self.repo.get_contents("REVIEWERS.yml", ref=self.pr.head.ref)
                print(f"Debug: Found REVIEWERS.yml in PR head branch {self.pr.head.ref}")
            except Exception as e:
                print(f"Debug: Could not find REVIEWERS.yml in PR head branch: {str(e)}")
                # Fallback to try getting from the base branch
                config_file = self.repo.get_contents("REVIEWERS.yml", ref=self.pr.base.ref)
                print(f"Debug: Found REVIEWERS.yml in base branch {self.pr.base.ref}")

            content = config_file.decoded_content
            if not content:
                raise ValueError("REVIEWERS.yml is empty")

            print(f"Debug: Successfully loaded REVIEWERS.yml, size: {len(content)} bytes")

            config = yaml.safe_load(content.decode("utf-8"))
            if not config:
                raise ValueError("REVIEWERS.yml contains no valid configuration")

            print("Debug: Successfully parsed YAML configuration")
            return config

        except yaml.YAMLError as e:
            print(f"Debug: YAML parsing error - {str(e)}")
            raise ValueError(f"Failed to parse REVIEWERS.yml: {str(e)}") from e
        except Exception as e:
            print(f"Debug: Unexpected error while loading config - {str(e)}")
            raise FileNotFoundError(f"Failed to load REVIEWERS.yml: {str(e)}") from e

    def _get_branch_config(self, branch_name: str) -> Optional[Dict]:
        """Get the configuration for a specific branch."""
        try:
            branch_configs = self.config["pull_requests"]["branches"]

            # First check for exact match
            if branch_name in branch_configs:
                print(f"Debug: Found exact match configuration for branch {branch_name}")
                return branch_configs[branch_name]

            # Then check pattern matches
            for pattern, config in branch_configs.items():
                if "*" in pattern:
                    regex_pattern = pattern.replace("*", ".*")
                    if re.match(regex_pattern, branch_name):
                        # Check if branch is excluded
                        if "exclude" in config and branch_name in config["exclude"]:
                            print(f"Debug: Branch {branch_name} is excluded from pattern {pattern}")
                            continue
                        print(
                            f"Debug: Found pattern match configuration for branch {branch_name} using pattern {pattern}"
                        )
                        return config

            print(f"Debug: No matching configuration found for branch {branch_name}")
            return None

        except KeyError as e:
            print(f"Debug: Missing key in configuration: {str(e)}")
            return None
        except Exception as e:
            print(f"Debug: Error getting branch configuration: {str(e)}")
            return None

    def _get_team_members(self, team_slug: str, org) -> List[str]:
        """Get list of usernames for members of a team."""
        try:
            team = org.get_team_by_slug(team_slug)
            members = list(team.get_members())
            print(f"team found: {team} from {team_slug}")
            if not members:
                print(f"Warning: No members found in team {team_slug}")
                return []
            return [member.login for member in members]
        except GithubException as e:
            if e.status == 404:
                print(f"Warning: Team {team_slug} not found")
                return []
            print(f"Warning: Error accessing team {team_slug}: {str(e)}")
            return []
        except Exception as e:
            print(f"Warning: Unexpected error getting team members for {team_slug}: {str(e)}")
            return []

    def _get_user_teams(self, username: str, org) -> List[str]:
        """Get all teams that a user belongs to in the organization."""
        try:
            teams = list(org.get_teams())
            user_teams = []

            for team in teams:
                try:
                    if team.has_in_members(self.gh.get_user(username)):
                        user_teams.append(team.slug)
                except Exception as e:
                    print(f"Warning: Error checking if user {username} is in team {team.slug}: {str(e)}")
                    continue

            return user_teams
        except Exception as e:
            print(f"Warning: Error getting teams for user {username}: {str(e)}")
            return []

    def _check_branch_protection(self, branch_name: str) -> bool:
        """Check if the branch has 'dismiss stale reviews' enabled in branch protection."""
        try:
            branch = self.repo.get_branch(branch_name)
            protection = branch.get_protection()
            return protection.required_pull_request_reviews.dismiss_stale_reviews
        except Exception as e:
            print(f"Warning: Could not check branch protection settings: {str(e)}")
            return False

    def _format_team_slug(self, team_name: str) -> str:
        """Format a team name into a proper team slug with variable substitution."""
        team_name = team_name.replace("{{ team_name }}", os.environ.get("TEAM_NAME", ""))
        return team_name.lower().strip().replace(" ", "-")

    def _check_required_reviews(self, pr, branch_config: Dict, org) -> bool:
        """Check if the PR has met the required review conditions."""
        try:
            required_approvals = branch_config.get("required_approvals", 0)
            required_teams = branch_config.get("required_teams", [])

            # Get all reviews
            reviews = pr.get_reviews()
            approved_reviewers = set()
            team_approvals = set()

            for review in reviews:
                if review.state == "APPROVED":
                    reviewer = review.user
                    approved_reviewers.add(reviewer.login)

                    # For team approvals, get all teams the user belongs to
                    try:
                        user_team_slugs = self._get_user_teams(reviewer.login, org)
                        for team_slug in user_team_slugs:
                            team_approvals.add(team_slug)
                            print(f"Debug: User {reviewer.login} approval counts for team {team_slug}")
                    except Exception as e:
                        print(f"Warning: Error processing team membership for {reviewer.login}: {str(e)}")

            # Check number of approvals
            if len(approved_reviewers) < required_approvals:
                print(f"Debug: Not enough approvals. Got {len(approved_reviewers)}, need {required_approvals}")
                return False

            # Check required teams - now a user in multiple teams counts for all those teams
            if required_teams:
                # Format each required team name to match the team slugs format
                required_team_slugs = [self._format_team_slug(team) for team in required_teams]

                print(f"Debug: Required team slugs: {required_team_slugs}")
                print(f"Debug: Teams with approvals: {team_approvals}")

                # Check if all required teams have at least one approver
                missing_teams = set(required_team_slugs) - team_approvals
                if missing_teams:
                    print(f"Debug: Missing required team approvals from: {missing_teams}")
                    return False

            return True

        except Exception as e:
            print(f"Warning: Error checking required reviews: {str(e)}")
            return False

    def process_pull_request(self, pr_number: int, org):
        """Process a pull request according to the configuration."""
        pr = self.repo.get_pull(pr_number)
        branch_name = pr.base.ref
        print(f"Debug: Processing PR #{pr_number} targeting branch {branch_name}")

        branch_config = self._get_branch_config(branch_name)
        if not branch_config:
            print(f"No configuration found for branch: {branch_name}")
            return

        # Check if stale reviews are dismissed for this branch
        dismiss_stale_reviews = self._check_branch_protection(branch_name)
        print(f"Debug: Dismiss stale reviews setting for branch {branch_name}: {dismiss_stale_reviews}")

        # Only add new reviewers if no reviews exist or if stale reviews are dismissed
        should_request_reviews = dismiss_stale_reviews or pr.get_reviews().totalCount == 0

        # Assign reviewers and assignees
        review_teams = branch_config.get("review_teams", [])
        assignee_teams = branch_config.get("assignees", [])

        try:
            # Add review teams using team slugs if needed
            if should_request_reviews:
                print("Debug: Requesting reviews since either no reviews exist or stale reviews are dismissed")
                for team in review_teams:
                    team_slug = self._format_team_slug(team)
                    try:
                        pr.create_review_request(team_reviewers=[team_slug])
                        print(f"Successfully requested review from team: {team_slug}")
                    except GithubException as e:
                        print(f"Warning: Could not request review from team {team_slug}: {str(e)}")
                        continue
            else:
                print("Debug: Skipping review requests as reviews exist and stale reviews are not dismissed")

            # Add assignees from teams
            assignees = set()
            for team in assignee_teams:
                team_slug = self._format_team_slug(team)
                team_members = self._get_team_members(team_slug, org)
                if team_members:
                    assignees.update(team_members)
                    print(f"Found {len(team_members)} members in team {team_slug}")

            # Only proceed if there are assignees to add
            if assignees:
                try:
                    # Add assignees in batches to handle GitHub's limitation
                    assignees_list = list(assignees)
                    for i in range(0, len(assignees_list), 10):
                        batch = assignees_list[i : i + 10]
                        pr.add_to_assignees(*batch)
                        print(f"Successfully added assignees: {', '.join(batch)}")
                except GithubException as e:
                    print(f"Warning: Error adding assignees: {str(e)}")
            else:
                print("No valid assignees found to add to the PR")

            # Check review requirements
            meets_requirements = self._check_required_reviews(pr, branch_config, org)

            status_context = "pr-review-requirements"
            try:
                if not meets_requirements:
                    self.repo.get_commit(pr.head.sha).create_status(
                        state="pending",
                        target_url="",
                        description="Required reviews not yet met",
                        context=status_context,
                    )
                else:
                    self.repo.get_commit(pr.head.sha).create_status(
                        state="success",
                        target_url="",
                        description="All review requirements met",
                        context=status_context,
                    )
            except GithubException as e:
                print(f"Warning: Could not update status check: {str(e)}")

        except Exception as e:
            print(f"Error processing PR #{pr_number}: {str(e)}")
            raise


def main():
    # Get inputs from GitHub Actions environment
    github_token = os.environ["GITHUB_TOKEN"]
    repository = os.environ["GITHUB_REPOSITORY"]
    pr_number = int(os.environ["PR_NUMBER"])
    org_name = os.environ["GITHUB_ORGANIZATION"]

    # Debug: Check repository access
    gh = Github(github_token)
    org = gh.get_organization(org_name)
    try:
        repo = gh.get_repo(repository)
        print(f"Debug: Successfully accessed repository {repository}")
        print(
            f"Debug: Repository permissions - admin: {repo.permissions.admin}, push: {repo.permissions.push}, pull: {repo.permissions.pull}"
        )
    except Exception as e:
        print(f"Debug: Error accessing repository - {str(e)}")

    # Initialize and run the PR Review Manager
    manager = PRReviewManager(github_token, repository, pr_number)
    manager.process_pull_request(pr_number, org)


if __name__ == "__main__":
    main()
