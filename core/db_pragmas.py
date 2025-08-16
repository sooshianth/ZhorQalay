from django.db.backends.signals import connection_created

def set_sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout = 10000;")  # 10 seconds

# Connect handler to every new DB connection
connection_created.connect(set_sqlite_pragmas)
