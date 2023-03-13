import httpx

usl_query_base_url = "https://universalscammerlist.com/api/query.php?query={}&hashtags=%23scammer%2C%23sketchy%2C%23troll&format=1"


async def fetch_usl_user_data(username):
    # The USL API is currently MIA, just return a placeholder for now
    return "Unknown - USL API down"

    # async with httpx.AsyncClient() as client:
    #     response = await client.get(usl_query_base_url.format(username))

    # if response.status_code != 200:
    #     raise RuntimeError(f"USL request failed: HTTP {response.status_code}")

    # json = response.json()

    # if not "data" in json:
    #     raise RuntimeError("Invalid response from USL API: no 'data' key")

    # return json["data"]
