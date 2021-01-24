from boto3.session import Session
import boto3
from datetime import datetime
import time
import requests
from dotenv import load_dotenv
load_dotenv()
import os
import mysql.connector
import random

REGION = 'na1'
API_URL = f'https://{REGION}.api.riotgames.com'
HEADERS = {'X-Riot-Token': os.environ.get("RIOT_API_KEY")}
PATCH_TIME = 1610051083000
DB = mysql.connector.connect(
  host=os.environ.get("DB_HOST"),
  user=os.environ.get("DB_LOGIN"),
  password=os.environ.get("DB_PASSWORD"),
  database="lol_stats"
)

player_list = []
game_list = []

s = requests.Session()

client = boto3.client('s3', aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"), aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"))

def get_next_player():
    if len(player_list) <= 0:
        paginator = client.get_paginator('list_objects')
        page_iterator = paginator.paginate(Bucket='lol-stats-players-queue')
        for page in page_iterator:
            player_list.extend([obj['Key'] for obj in page['Contents']])
    if len(player_list) < 1:
        return None
    player = random.choice(player_list)
    try:
        client.delete_object(Bucket='lol-stats-players-queue', Key=player)
    except:
        return get_next_player()
    return player

def get_next_game():
    if len(game_list) <= 0:
        try:
            paginator = client.get_paginator('list_objects')
            page_iterator = paginator.paginate(Bucket='lol-stats-games-queue')
            for page in page_iterator:
                game_list.extend([obj['Key'] for obj in page['Contents']])
        except:
            return get_next_player()
    if len(game_list) < 1:
        return None
    game = random.choice(game_list)
    try:
        client.delete_object(Bucket='lol-stats-games-queue', Key=game)
    except:
        return get_next_game()
    return game

def get_player_or_game():
    return get_next_player() if random.randrange(1, 100) <= 12 else get_next_game()

def explore_player(accountId, begin=0):
    begin_time = PATCH_TIME
    cursor = DB.cursor()
    cursor.execute("SELECT * FROM `players` WHERE `accountId` = %s", (accountId,))
    player = cursor.fetchone()
    cursor.close()
    if player:
        explored = player[1]
        if time.time() - explored > 86400*7:
            begin_time = explored + 1
        else:
            return
    response = s.get(f'{API_URL}/lol/summoner/v4/summoners/by-account/{accountId}', headers=HEADERS)
    if response.status_code != 200:
        print("couldn't get account")
        if response.status_code == 429:
            time.sleep(int(response.headers.get("Retry-After")))
    body = response.json()
    summonerId = body['id']
    response = s.get(f'{API_URL}/lol/league/v4/entries/by-summoner/{summonerId}', headers=HEADERS)
    if response.status_code != 200:
        print("couldn't get matches")
        if response.status_code == 429:
            time.sleep(int(response.headers.get("Retry-After")))
    body = response.json()
    keep = False
    for body in body:
        if body['queueType'] == 'RANKED_SOLO_5x5' and body['tier'] != 'GOLD' and body['tier'] != 'SILVER' and body['tier'] != 'BRONZE' and not (body['tier'] == 'PLATINUM' and (body['rank'] == 'III' or body['rank'] == 'IV')):
            keep = True
        if keep:
            print(body['tier'], body['rank'])
    if not keep:
        return
    response = s.get(f'{API_URL}/lol/match/v4/matchlists/by-account/{accountId}?queue=420&beginTime={begin_time}&beginIndex={begin}', headers=HEADERS)
    if response.status_code == 200:
        body = response.json()
        session = Session(aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"), aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"))
        s3 = session.resource("s3")
        for match in body['matches']:
            pass
            s3.Bucket('lol-stats-games-queue').put_object(Key=str(match["gameId"]), Body='')
        if (body['totalGames'] > body['endIndex']):
            return explore_player(accountId, begin=body['endIndex']+1)
        cursor = DB.cursor()
        sql = "INSERT INTO `players` (accountId, explored) VALUES (%s, %s)"
        cursor.execute(sql, (accountId, int(time.time())))
        DB.commit()
        cursor.close()
    elif response.status_code == 429:
        time.sleep(int(response.headers.get("Retry-After")))

def explore_game(gameId):
    cursor = DB.cursor()
    cursor.execute("SELECT * FROM `games` WHERE `gameId` = %s", (gameId,))
    game = cursor.fetchone()
    cursor.close()
    if not game:
        response = s.get(f'{API_URL}/lol/match/v4/matches/{gameId}', headers=HEADERS)
        if response.status_code == 200:
            body = response.json()
            players = []
            for player in body['participants']:
                team = player['teamId'] / 100
                win = player['stats']['win']
                champion = player['championId']
                spell1 = player['spell1Id']
                spell2 = player['spell2Id']
                item0 = player['stats']['item0']
                item1 = player['stats']['item1']
                item2 = player['stats']['item2']
                item3 = player['stats']['item3']
                item4 = player['stats']['item4']
                item5 = player['stats']['item5']
                item6 = player['stats']['item6']
                perk0 = player['stats']['perk0']
                perk1 = player['stats']['perk1']
                perk2 = player['stats']['perk2']
                perk3 = player['stats']['perk3']
                perk4 = player['stats']['perk4']
                perk5 = player['stats']['perk5']
                players.append((gameId, champion, team, win, spell1, spell2, item0, item1, item2, item3, item4, item5, item6, perk0, perk1, perk2, perk3, perk4, perk5))
            cursor = DB.cursor()
            sql = "INSERT INTO games (gameId, champion, team, win, spell1, spell2, item0, item1, item2, item3, item4, item5, item6, perk0, perk1, perk2, perk3, perk4, perk5) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            cursor.executemany(sql, players)
            DB.commit()
            cursor.close()
            for player in body['participantIdentities']:
                player = player['player']
                session = Session(aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"), aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"))
                s3 = session.resource("s3")
                s3.Bucket('lol-stats-players-queue').put_object(Key=player['accountId'], Body='')
        elif response.status_code == 429:
            time.sleep(int(response.headers.get("Retry-After")))
    

def explore(id):
    if len(id) > 12:
        return explore_player(id)
    else:
        return explore_game(id)

if __name__ == '__main__':
    while True:
        start = time.time()
        id = get_player_or_game()
        print(explore(id))
        print(time.time() - start)