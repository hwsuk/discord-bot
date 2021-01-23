import httpx

from bs4 import BeautifulSoup

usl_query_base_url = "https://universalscammerlist.com/api/query.php?query={}&hashtags=%23scammer%2C%23sketchy%2C%23troll&format=1"


async def fetch_usl_user_data(username):
    async with httpx.AsyncClient() as client:
        response = client.get(usl_query_base_url.format(username))

    if response.status_code != 200:
        raise RuntimeError(f"USL request failed: HTTP {response.status_code}")

    data = response.json()
