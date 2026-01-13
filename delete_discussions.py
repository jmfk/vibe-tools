import json
import subprocess
import sys

def run_command(command):
    result = subprocess.run(command, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode

def get_repo_info():
    # Get owner/name from git remote
    stdout, code = run_command(["git", "remote", "get-url", "origin"])
    if code != 0:
        print("Error: Not a git repository.")
        sys.exit(1)
    
    url = stdout
    if "github.com" not in url:
        print("Error: Not a GitHub repository.")
        sys.exit(1)

    if url.startswith("git@github.com:"):
        repo = url.replace("git@github.com:", "").replace(".git", "")
    elif url.startswith("https://github.com/"):
        repo = url.replace("https://github.com/", "").replace(".git", "")
    else:
        parts = url.split("github.com/")
        repo = parts[1].replace(".git", "")
    
    owner, name = repo.split("/")
    return owner, name

def fetch_discussions(owner, name):
    all_discussions = []
    has_next_page = True
    after = None

    print(f"Fetching discussions for {owner}/{name}...")
    while has_next_page:
        query = """
        query($owner:String!, $name:String!, $after:String) {
          repository(owner:$owner, name:$name) {
            discussions(first:100, after:$after) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                id
                title
              }
            }
          }
        }
        """
        cmd = ["gh", "api", "graphql", "-f", f"query={query}", "-f", f"owner={owner}", "-f", f"name={name}"]
        if after:
            cmd.extend(["-f", f"after={after}"])
            
        stdout, code = run_command(cmd)
        if code != 0:
            print(f"Error fetching discussions: {stdout}")
            break

        data = json.loads(stdout)
        discs = data["data"]["repository"]["discussions"]
        all_discussions.extend(discs["nodes"])
        has_next_page = discs["pageInfo"]["hasNextPage"]
        after = discs["pageInfo"]["endCursor"]

    return all_discussions

def delete_discussion(discussion_id, title):
    print(f"Deleting: {title} ({discussion_id})")
    query = """
    mutation($id: ID!) {
      deleteDiscussion(input: {id: $id}) {
        clientMutationId
      }
    }
    """
    cmd = ["gh", "api", "graphql", "-f", f"query={query}", "-f", f"id={discussion_id}"]
    stdout, code = run_command(cmd)
    if code != 0:
        print(f"Failed to delete {title}: {stdout}")

def main():
    owner, name = get_repo_info()
    discussions = fetch_discussions(owner, name)
    
    if not discussions:
        print("No discussions found.")
        return

    print(f"Found {len(discussions)} discussions. Starting deletion...")
    for d in discussions:
        delete_discussion(d["id"], d["title"])
    
    print("Done.")

if __name__ == "__main__":
    main()
