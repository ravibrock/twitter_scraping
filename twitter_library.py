from pwinput import pwinput
import requests
import time


def create_following_url(user_id):
    return f"https://api.twitter.com/2/users/{user_id}/following"


def create_followers_url(username):
    return f"https://api.twitter.com/2/users/by/username/{username}?user.fields=public_metrics"


def get_bearer_tokens():
    current_token = 0
    token_count = int(input("Number of bearer tokens: "))
    bearer_token = ["x"] * token_count
    while current_token < token_count:
        bearer_token[current_token] = pwinput(prompt=f"Token {current_token + 1}: ", mask="*")
        current_token += 1

    return bearer_token


def connect_to_endpoint(url, params, bearer_token, token_number):
    token_count = len(bearer_token) - 1
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


def execute_request(url, params, bearer_token, starting_token):
    token_number = len(bearer_token) - 1
    token = starting_token

    response = connect_to_endpoint(url, params, bearer_token, token)
    while response[1].status_code == 429:
        token += 1
        while token <= token_number:
            response = connect_to_endpoint(url, params, bearer_token, token)
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
            response = connect_to_endpoint(url, params, bearer_token, token)

    return [response, token]
