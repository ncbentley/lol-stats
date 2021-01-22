from boto3.session import Session
from datetime import datetime
import time
import requests
from dotenv import load_dotenv
load_dotenv()
import os
import mysql.connector

REGION = 'na1'
API_URL = f'https://{REGION}.api.riotgames.com'
HEADERS = {'X-Riot-Token': os.environ.get("RIOT_API_KEY")}
PATCH_TIME = 1610051083000
DB = mysql.connector.connect(
  host="lol-stats-instance-1.cv3oxvzkk5zr.us-east-1.rds.amazonaws.com",
  user=os.environ.get("DB_LOGIN"),
  password=os.environ.get("DB_PASSWORD"),
  database="lol_stats"
)

s = requests.Session()

get_last_modified = lambda obj: int(datetime.timestamp(obj.last_modified))

def get_next_player():
    session = Session(profile_name="Default")
    s3 = session.resource("s3")
    bckt = s3.Bucket("lol-stats-players-queue")
    players = [player for player in bckt.objects.all()]
    players = [player for player in sorted(players, key=get_last_modified)]
    if len(players) < 1:
        return None
    player = players[0].key
    # try:
    #     players[0].delete()
    # except:
    #     return get_next_player()
    return player

def get_next_game():
    session = Session(profile_name="Default")
    s3 = session.resource("s3")
    bckt = s3.Bucket("lol-stats-games-queue")
    games = [game for game in bckt.objects.all()]
    games = [game for game in sorted(games, key=get_last_modified)]
    if len(games) < 1:
        return None
    game = games[0].key
    try:
        games[0].delete()
    except:
        return get_next_game()
    return game

def get_player_or_game():
    session = Session(profile_name="Default")
    s3 = session.resource("s3")
    player_queue = s3.Bucket("lol-stats-players-queue")
    players = sum(1 for _ in player_queue.objects.all())
    game_queue = s3.Bucket("lol-stats-games-queue")
    games = sum(1 for _ in game_queue.objects.all())
    return get_next_player() if players >= games else get_next_game()

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

    response = s.get(f'{API_URL}/lol/match/v4/matchlists/by-account/{accountId}?queue=420&beginTime={begin_time}&beginIndex={begin}', headers=HEADERS)
    #TODO: Error handling for all possible repsonses!
    if response.status_code == 200:
        body = response.json()
        session = Session(profile_name="Default")
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
        pass #handle rate limit

def explore_game(gameId):
    # TODO: Check DB to see if game has been explored
    return "Exploring Game"

def explore(id):
    if len(id) > 12:
        return explore_player(id)
    else:
        return explore_game(id)

if __name__ == '__main__':
    start = time.time()
    id = get_player_or_game()
    print(explore(id))
    print(time.time() - start)