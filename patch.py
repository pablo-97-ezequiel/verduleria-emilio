import sqlite3

con = sqlite3.connect("database.db")

try:
    con.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'pendiente'")
    print("🆕 Columna 'status' agregada correctamente.")
except sqlite3.OperationalError:
    print("✔️ La columna 'status' ya existe.")

con.commit()
con.close()
