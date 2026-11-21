# TRADEIN — Cloud deployment

## Important
- Do not commit `trades.db`, `.streamlit/secrets.toml`, passwords, or screenshots to GitHub.
- Use a Supabase PostgreSQL database for persistent cloud storage. The app retains SQLite mode for local use.
- Streamlit Community Cloud filesystem is not the permanent database.

## Deploy
1. Create a Supabase project and copy its PostgreSQL connection string (use a direct/session connection compatible with psycopg; require SSL).
2. Create a private GitHub repository and upload the contents of this folder **except** `trades.db`, `.streamlit/secrets.toml`, and `__pycache__`.
3. Deploy the repository on Streamlit Community Cloud with main file `app.py`.
4. In Streamlit app Settings → Secrets, paste:
   ```toml
   [database]
   url = "YOUR_SUPABASE_POSTGRES_CONNECTION_STRING"

   [auth]
   password = "YOUR_LONG_PRIVATE_APP_PASSWORD"
   ```
5. The app initializes the PostgreSQL schema on first launch.

## Import the existing SQLite history (run locally, not in GitHub)
1. Keep the original `trades.db` file on your own computer. Do not upload it to the public repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Set the environment variable `DATABASE_URL` to the same Supabase PostgreSQL connection string.
   - PowerShell: `$env:DATABASE_URL="postgresql://..."`
   - macOS/Linux: `export DATABASE_URL="postgresql://..."`
4. Run: `python migrate_sqlite_to_supabase.py "C:\path\to\trades.db"`
5. Check the printed imported row count. The migration script preserves trade IDs and all columns available in the SQLite source. It can be safely rerun for the same IDs (upsert).

## Local mode
If no `[database].url` secret exists, TRADEIN uses local `trades.db` as before.

## Notes
- The password gate is a single shared app password, not individual user accounts.
- Chart screenshot files stored only on the old laptop are not automatically moved by the SQLite migration. Keep them backed up separately.
- Keep regular CSV exports from Backup & Settings.
