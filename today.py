import os
import requests
from lxml import etree

TOKEN = os.environ["ACCESS_TOKEN"]
USERNAME = os.environ.get("USER_NAME", "RazeYuki")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, first: 1) { totalCount }
    followers { totalCount }
    stargazers: repositories(ownerAffiliations: OWNER, first: 100) {
      edges { node { stargazers { totalCount } } }
    }
    contributionsCollection {
      contributionCalendar { totalContributions }
    }
  }
}
"""

# GitHub's repositories connection has a 100-item page size. Fetch all owned
# repositories so the star total remains accurate for larger accounts.
REPO_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, first: 100, after: $cursor) {
      edges { node { stargazers { totalCount } } }
      pageInfo { endCursor hasNextPage }
    }
  }
}
"""


def graphql(query, variables):
    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def get_stats():
    data = graphql(QUERY, {"login": USERNAME})["user"]
    repos = data["repositories"]["totalCount"]
    followers = data["followers"]["totalCount"]
    contributions = data["contributionsCollection"]["contributionCalendar"]["totalContributions"]

    stars = 0
    cursor = None
    while True:
        page = graphql(REPO_QUERY, {"login": USERNAME, "cursor": cursor})["user"]["repositories"]
        stars += sum(edge["node"]["stargazers"]["totalCount"] for edge in page["edges"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    return repos, followers, stars, contributions


def update_svg(filename, stats):
    repos, followers, stars, contributions = stats
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(filename, parser)
    root = tree.getroot()

    replacements = {
        "repo_data": f"{repos:,}",
        "star_data": f"{stars:,}",
        "follower_data": f"{followers:,}",
        "contrib_data": f"{contributions:,}",
    }

    for element in root.iter():
        element_id = element.get("id")
        if element_id in replacements:
            element.text = replacements[element_id]

    tree.write(filename, encoding="UTF-8", xml_declaration=True)


if __name__ == "__main__":
    stats = get_stats()
    update_svg("dark_mode.svg", stats)
    update_svg("light_mode.svg", stats)
    print(f"Updated {USERNAME}: repos={stats[0]}, followers={stats[1]}, stars={stats[2]}, contributions={stats[3]}")
