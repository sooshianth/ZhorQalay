import sqlite3
conn = sqlite3.connect(r"C:\\Users\\arshi\\OneDrive\\Desktop\\Work\\Simurgh\\Websites\\CRM\\db.sqlite3")
conn.execute("CREATE TABLE IF NOT EXISTS testperm(id INT);")
conn.commit()
conn.close()
