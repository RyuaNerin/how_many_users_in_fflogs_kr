#!/bin/python3
# -*- coding: utf-8 -*-

import datetime
import os
import string
from collections import defaultdict

import requests
import tqdm

# PROXIES = {"http": "http://127.0.0.1:50000", "https": "http://127.0.0.1:50000"}
PROXIES = None

ZONE_ID = 38
SERVER_REGION = "kr"
PARTITIONS = {
    5: "54",  # 표준 구성 (5.4)
    11: "55",  # 표준 구성 (5.5)
    17: "ec",  # 표준 구성 (Echo)
}
ENCOUNTER = {
    73: "e9s",
    74: "e10s",
    75: "e11s",
    76: "e12s_d",
    77: "e12s_o",
}
JOBS = {
    "Paladin": "PLD",
    "Warrior": "WAR",
    "DarkKnight": "DRK",
    "Gunbreaker": "GNB",
    "WhiteMage": "WHM",
    "Scholar": "SCH",
    "Astrologian": "AST",
    # "Sage": "SAG",
    "Monk": "MNK",
    "Dragoon": "DRG",
    "Ninja": "NIN",
    "Samurai": "SAM",
    # "Reaper": "RPR",
    "Bard": "BRD",
    "Machinist": "MCH",
    "Dancer": "DNC",
    "BlackMage": "BLM",
    "Summoner": "SMN",
    "RedMage": "RDM",
}

####################################################################################################

r = requests.post(
    "https://www.fflogs.com/oauth/token",
    proxies=PROXIES,
    data={
        "grant_type": "client_credentials",
        "client_id": os.getenv("OAUTH2_ID"),
        "client_secret": os.getenv("OAUTH2_SECRET"),
    },
)
if r.status_code != 200:
    print(r.text)
    quit(1)
r = r.json()
if "error" in r and r["error"] != "":
    print(r)
    quit(1)

headers = {
    "Authorization": f"Bearer {r['access_token']}",
}

####################################################################################################

query_body = "\n".join(
    [
        f"""{job_short}_{part_str}: characterRankings(specName: "{job_full}", partition: {part_v})"""
        for job_full, job_short in JOBS.items()
        for part_v, part_str in PARTITIONS.items()
    ]
)
query = f"""{{
    worldData {{
		zone(id: {ZONE_ID}) {{
			encounters {{
                {query_body}
			}}
		}}
	}}
}}"""

r = requests.post(
    "https://ko.fflogs.com/api/v2/client",
    proxies=PROXIES,
    headers=headers,
    json={"query": query},
)
if r.status_code != 200:
    print(r.text)
    quit(1)
r = r.json()

char_names = set()

for encounter in r["data"]["worldData"]["zone"]["encounters"]:
    lambda_new_count = lambda: defaultdict(int)
    name_dict_each_job = defaultdict(lambda_new_count)

    for encounters_key, encounters_value in encounter.items():
        name_dict = name_dict_each_job[encounters_key[:3]]

        for rankings in encounters_value["rankings"]:
            rankings_name = rankings["name"]
            if rankings_name != "Anonymous":
                name_dict[(rankings_name, rankings["server"]["name"])] += 1

    for name_dict in name_dict_each_job.values():
        if len(name_dict) > 0:
            char_names.add(max(name_dict, key=name_dict.get))

####################################################################################################

content = {job_short: job_full for job_full, job_short in JOBS.items()}
content["NOW"] = datetime.datetime.now(
    tz=datetime.timezone(datetime.timedelta(hours=9))
).strftime("%Y-%m-%d %H:%M:%S")

query_body = "\n".join(
    f"""p_{part_str}: zoneRankings(zoneID: {ZONE_ID}, difficulty: 101, includePrivateLogs: true, partition: {part_v})"""
    for part_v, part_str in PARTITIONS.items()
)

todo = len(JOBS) * len(PARTITIONS)

with tqdm.tqdm(total=len(char_names)) as tq:
    for (char_name, char_server) in char_names:
        tq.update()
        tq.set_description(f"{char_name}@{char_server}")

        query = f"""{{
    characterData {{
        character(name: "{char_name}", serverSlug:"{char_server}", serverRegion: "{SERVER_REGION}") {{
            {query_body}
        }}
    }}
}}"""
        r = requests.post(
            "https://ko.fflogs.com/api/v2/client",
            proxies=PROXIES,
            headers=headers,
            json={"query": query},
        )
        if r.status_code != 200:
            print(r.text)
            quit(1)
        r = r.json()

        for ranking_key, allstar_data in r["data"]["characterData"][
            "character"
        ].items():
            part = ranking_key[ranking_key.index("_") + 1 :]

            for allstar in allstar_data["allStars"]:
                key = f"{JOBS[allstar['spec']]}_{part}"

                if key not in content:
                    todo -= 1

                content[key] = f"{allstar['total']:,}"

        if todo == 0:
            break


with open("README.tmpl.md", "r", encoding="utf-8") as fs:
    content_template = string.Template(fs.read())

with open("README.md", "w", encoding="utf-8") as fs:
    fs.truncate(0)
    fs.write(content_template.substitute(content))

