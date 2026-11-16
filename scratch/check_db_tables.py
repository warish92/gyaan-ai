import sqlite3

def check():
    conn1 = sqlite3.connect("data/gyaan_ai.db")
    t1 = [r[0] for r in conn1.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    conn1.close()

    conn2 = sqlite3.connect("data/documents.db")
    t2 = [r[0] for r in conn2.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    conn2.close()

    print("gyaan_ai.db tables:", t1)
    print("documents.db tables:", t2)

if __name__ == "__main__":
    check()
