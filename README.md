# TRADEIN Trading Journal

TRADEIN supports both local SQLite storage and cloud PostgreSQL storage.

- Local use: run `run_windows.bat` (uses `trades.db` in this folder).
- Cloud use: follow `README_DEPLOY.md` to deploy on Streamlit Community Cloud with Supabase PostgreSQL.
- Keep `trades.db` and `.streamlit/secrets.toml` out of GitHub. `.gitignore` is included.
- The cloud migration helper is `migrate_sqlite_to_supabase.py`.

The app keeps MT5 XLSX import and the existing journal/review fields.
