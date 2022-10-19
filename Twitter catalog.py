from collections import Counter
from pwinput import pwinput
import json
import pandas as pd
import requests
import time

twitter_username = input("\nUsername: ")
file = input("CSV file to save results: ")
min_common = int(input("Minimum number of common followers: "))

current_token = 0
token_count = int(input("Number of bearer tokens: "))
bearer_token = ["x"] * token_count
while current_token < token_count:
    bearer_token[current_token] = pwinput(prompt=f"Token {current_token + 1}: ", mask="*")
    current_token += 1

start_time_int = int(time.time())
start_time = time.localtime(start_time_int)
start_time = time.strftime("%H:%M:%S", start_time)
print(f"Start time: {start_time}\n")


def create_following_url(user_id):
    return f"https://api.twitter.com/2/users/{user_id}/following"


def create_followers_url(username):
    return f"https://api.twitter.com/2/users/by/username/{username}?user.fields=public_metrics"


def get_params():
    return {"user.fields": "protected,public_metrics",
            "max_results": "1000"
            }


def pagination_params(pagination_token):
    return {"user.fields": "protected,public_metrics",
            "max_results": "1000",
            "pagination_token": pagination_token
            }


def connect_to_endpoint(url, params, token_number):
    auth = {"Authorization": f"Bearer {bearer_token[token_number]}"}
    response = requests.request("GET", url, headers=auth, params=params)
    print(f"Request status: {response.status_code}")
    if (response.status_code == 429) & (token_count > 1):
        print("Attempting to get fresh token")

    if response.status_code == 401:
        raise Exception(
            "\nRequest status 401 -\nDouble-check bearer token input."
        )
    return [response.json(), response]


def connect_followers_endpoint(url, token_number):
    auth = {"Authorization": f"Bearer {bearer_token[token_number]}"}
    response = requests.request("GET", url, headers=auth)
    print(f"Request status: {response.status_code}")
    if (response.status_code == 429) & (token_count > 1):
        print("Attempting to get fresh token")

    if response.status_code == 401:
        raise Exception(
            "\nRequest status 401 -\nDouble-check bearer token input."
        )
    return [response.json(), response]


def followers_request(url, starting_token):
    token_number = len(bearer_token) - 1
    token = starting_token

    response = connect_followers_endpoint(url, token)
    while response[1].status_code == 429:
        token += 1
        while token <= token_number:
            response = connect_followers_endpoint(url, token)
            if response[1].status_code == 200:
                return [response, token]
            token += 1

        if token > token_number:
            current_time = int(time.time())
            resume_time = time.localtime(current_time + 900)
            print("All tokens used. Sleeping until", time.strftime("%H:%M:%S", resume_time), "to avoid rate limit")
            time.sleep(900)
            print("")
            token = 0
            response = connect_followers_endpoint(url, token)

    return [response, token]


def execute_request(url, starting_token):
    params = get_params()
    token_number = len(bearer_token) - 1
    token = starting_token

    response = connect_to_endpoint(url, params, token)
    while response[1].status_code == 429:
        token += 1
        while token <= token_number:
            response = connect_to_endpoint(url, params, token)
            if response[1].status_code == 200:
                return [response, token]
            token += 1

        if token > token_number:
            current_time = int(time.time())
            resume_time = time.localtime(current_time + 900)
            print("All tokens used. Sleeping until", time.strftime("%H:%M:%S", resume_time), "to avoid rate limit")
            time.sleep(900)
            print("")
            token = 0
            response = connect_to_endpoint(url, params, token)

    return [response, token]


def paginated_request(url, pagination_token, starting_token):
    params = pagination_params(pagination_token)
    token_number = len(bearer_token) - 1
    token = starting_token

    response = connect_to_endpoint(url, params, token)
    while response[1].status_code == 429:
        token += 1
        while token <= token_number:
            response = connect_to_endpoint(url, params, token)
            if response[1].status_code == 200:
                return [response, token]
            token += 1

        if token > token_number:
            current_time = int(time.time())
            resume_time = time.localtime(current_time + 900)
            print("All tokens used. Sleeping until", time.strftime("%H:%M:%S", resume_time), "to avoid rate limit")
            time.sleep(900)
            print("")
            token = 0
            response = connect_to_endpoint(url, params, token)

    return [response, token]


def pull_following(user_id, starting_token):
    url = create_following_url(user_id)
    raw_response = execute_request(url, starting_token)
    paginated_response = raw_response[0]
    starting_token = raw_response[1]
    if json.loads(json.dumps(paginated_response[0], indent=4, sort_keys=True))["meta"]["result_count"] != 0:
        response = pd.json_normalize(json.loads(json.dumps(paginated_response[0], indent=4, sort_keys=True))["data"])

        while "next_token" in (json.loads(json.dumps(paginated_response[0]))["meta"]):
            pagination_token = json.loads(json.dumps(paginated_response[0]))["meta"]["next_token"]
            raw_response = paginated_request(url, pagination_token, starting_token)
            paginated_response = raw_response[0]
            starting_token = raw_response[1]
            clean_page_response = paginated_response
            clean_page_response = json.dumps(clean_page_response[0])
            clean_page_response = pd.json_normalize(json.loads(clean_page_response)["data"])
            concatenate = [response, clean_page_response]
            response = pd.concat(concatenate)
        return [response, starting_token]
    else:
        blank = "skip"
        return [blank, starting_token]


def process_following(data):
    data = data.drop(
        columns=["name", "public_metrics.following_count", "public_metrics.listed_count",
                 "public_metrics.tweet_count"])
    data = data.rename(columns={"public_metrics.followers_count": "followers"})
    data = data.reset_index(drop=True)

    return data


def general_following():
    starting_token = 0
    url = create_followers_url(twitter_username)
    user_id = followers_request(url, starting_token)
    user_id = user_id[0][0]["data"]["id"]

    data = pull_following(user_id, starting_token)

    main_data = data[0]
    starting_token = data[1]
    main_data = main_data.loc[main_data["protected"] == False]
    main_data = main_data.reset_index(drop=True)

    length = len(main_data.index) - 1
    start_loop = 0
    follows_spot = 0
    follows = {}
    while start_loop <= length:
        userid = main_data.loc[start_loop]["id"]
        raw_data = pull_following(userid, starting_token)
        if isinstance(raw_data[0], pd.DataFrame):
            follows[follows_spot] = raw_data[0]
            follows_spot += 1
        starting_token = raw_data[1]
        start_loop += 1
    follows = pd.concat(follows)
    follows = process_following(follows)

    return follows


def remove_hole(data, token):
    username = data.iloc[0]["username"]
    url = create_followers_url(username)
    response = followers_request(url, token)
    new_token = response[1]
    response = response[0][0]
    followers_count = response["data"]["public_metrics"]["followers_count"]
    index_number = data.index[0]

    return [index_number, followers_count, new_token]


def analyze_following(data):
    count = list(data["username"])
    count = Counter(count)
    data2 = pd.DataFrame([count], index=["common_followers"])
    data2 = data2.T
    data2 = data2.reset_index()
    data2 = data2.sort_values(by=["index"])

    followinglist = data.drop_duplicates(subset="username", keep="first")
    followinglist = followinglist[["username", "id", "protected", "followers"]]
    followinglist = followinglist.sort_values(by=["username"])
    extracted_col = followinglist["followers"]
    data2.insert(2, "followers", extracted_col.values)
    data2.columns = ["username", "common_followers", "total_followers"]

    data3 = data2.loc[data2["common_followers"] > data2["total_followers"]]
    token = 0
    while len(data3.index) > 0:
        holeremoved = remove_hole(data3, token)
        data2.at[holeremoved[0], "total_followers"] = holeremoved[1]
        token = holeremoved[2]
        data3 = data2.loc[data2["common_followers"] > data2["total_followers"]]

    data2 = data2.loc[data2["total_followers"] != 0]
    data2["common_by_total"] = data2.apply(lambda row: row.common_followers / row.total_followers * 100, axis=1)
    extracted_col = followinglist["protected"]
    data2.insert(1, "protected", extracted_col.values)
    data2 = data2.sort_values(by="common_by_total", ascending=False)

    return data2


def main():
    output = general_following()
    output = analyze_following(output)
    output = output.loc[output["common_followers"] >= min_common]
    output = output.sort_values(by=["common_followers"])
    output = output.reset_index(drop=True)
    print("")
    print(output)
    output = output.sort_values(by=["common_followers"], ascending=False)
    output.to_csv(file, index=False)

    print("\nUser inputs:\n", f" Username: {twitter_username}\n", f" File location: {file}\n",
          f" Bearer token count: {token_count}")
    i = 0
    while i < token_count:
        print(f"  Token {i + 1}: {bearer_token[i][0:3]}...{bearer_token[i][111:114]}")
        i += 1

    print(f"\nStart time: {start_time}")

    end_time_int = int(time.time())
    end_time = time.localtime(end_time_int)
    end_time = time.strftime("%H:%M:%S", end_time)
    print(f"End time: {end_time}")

    time_elapsed = end_time_int - start_time_int
    time_elapsed = time.gmtime(time_elapsed)
    time_elapsed = time.strftime("%H:%M:%S", time_elapsed)
    print(f"Time elapsed: {time_elapsed}")


if __name__ == "__main__":
    main()