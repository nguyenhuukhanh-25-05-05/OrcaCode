"""Debug FTS5 issue."""
from core.services.long_memory import LongMemory
import tempfile, shutil

d = tempfile.mkdtemp()
m = LongMemory(project_root=d)

# Add knowledge
kid = m.add_knowledge('auth_pattern', 'Always refresh JWT tokens before expiry')
print(f'Added knowledge id={kid}')

# Check FTS5 directly
rows = m.conn.execute('SELECT rowid, pattern_name, pattern_text FROM knowledge_fts').fetchall()
print(f'FTS5 rows: {len(rows)}')
for r in rows:
    print(f'  rowid={r[0]}, name={r[1]}, text={r[2]}')

# Check knowledge table
rows2 = m.conn.execute('SELECT id, pattern_name FROM knowledge').fetchall()
print(f'Knowledge rows: {len(rows2)}')
for r in rows2:
    print(f'  id={r[0]}, name={r[1]}')

# Direct FTS5 query
try:
    rows3 = m.conn.execute(
        'SELECT * FROM knowledge_fts WHERE knowledge_fts MATCH ?',
        ('authentication',)
    ).fetchall()
    print(f'Direct FTS5 query: {len(rows3)}')
    for r in rows3:
        print(f'  {r}')
except Exception as e:
    print(f'FTS5 error: {e}')

# Try with wildcard
try:
    rows4 = m.conn.execute(
        "SELECT * FROM knowledge_fts WHERE knowledge_fts MATCH 'auth*'",
    ).fetchall()
    print(f'Wildcard query: {len(rows4)}')
except Exception as e:
    print(f'Wildcard error: {e}')

# Check triggers exist
triggers = m.conn.execute(
    "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'knowledge%'"
).fetchall()
print(f'Triggers: {[t[0] for t in triggers]}')

m.close()
shutil.rmtree(d)