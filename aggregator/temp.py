import mysql.connector
from dotenv import load_dotenv
load_dotenv()
import os

DB = mysql.connector.connect(
  host="lol-stats-instance-1.cv3oxvzkk5zr.us-east-1.rds.amazonaws.com",
  user=os.environ.get("DB_LOGIN"),
  password=os.environ.get("DB_PASSWORD"),
  database="lol_stats"
)

cursor = DB.cursor()
cursor.execute("""CREATE TABLE `games` (
	`gameId` int NOT NULL,
	`champion` int NOT NULL,
	`team` BOOLEAN NOT NULL,
	`win` BOOLEAN NOT NULL,
	`spell1` int NOT NULL,
	`spell2` int NOT NULL,
	`item0` int NOT NULL,
	`item1` int NOT NULL,
	`item2` int NOT NULL,
	`item3` int NOT NULL,
	`item4` int NOT NULL,
	`item5` int NOT NULL,
	`item6` int NOT NULL,
	`perk0` int NOT NULL,
	`perk1` int NOT NULL,
	`perk2` int NOT NULL,
	`perk3` int NOT NULL,
	`perk4` int NOT NULL,
	`perk5` int NOT NULL
);

""")