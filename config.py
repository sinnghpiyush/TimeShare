import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="gateway01.ap-southeast-1.prod.aws.tidbcloud.com",
        port=4000,
        user="4Lq7F8DpS6p6Ush.root",
        password="56PHhV3u2bMq1AQe",
        database="test",
        ssl_ca="C:/tidb/ca.pem"
    )