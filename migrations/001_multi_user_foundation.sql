-- TRADEIN Multi-user Foundation
-- Phase 1 / Migration 001
--
-- SAFETY:
--   * This migration is additive only.
--   * Existing trade rows are NOT updated or deleted.
--   * user_id stays nullable until the Supabase Auth founder account exists
--     and its UUID has been verified.
--   * Do NOT enable RLS in this phase. The current app uses a direct
--     PostgreSQL connection and must be migrated to user-scoped access first.
--
-- Before running:
--   1. Export a full backup of public.trades from Supabase.
--   2. Confirm the backup can be opened and contains the expected row count.
--   3. Run this script in the Supabase SQL Editor.
--   4. Run the verification queries at the bottom.
--
-- This migration is designed for the existing Supabase PostgreSQL database.

BEGIN;

ALTER TABLE public.trades
    ADD COLUMN IF NOT EXISTS user_id UUID
    REFERENCES auth.users(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_trades_user_id
    ON public.trades(user_id);

COMMENT ON COLUMN public.trades.user_id IS
    'Owner of this trade. NULL is allowed temporarily for legacy rows until the founder Supabase Auth account is created and verified.';

COMMIT;

-- Verification (run after the migration):
-- 1) Confirm the new column exists:
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_schema = 'public'
--   AND table_name = 'trades'
--   AND column_name = 'user_id';
--
-- Expected: user_id | uuid | YES
--
-- 2) Confirm no legacy records were lost:
-- SELECT COUNT(*) AS total_trades,
--        COUNT(*) FILTER (WHERE user_id IS NULL) AS unassigned_legacy_trades
-- FROM public.trades;
--
-- Before the founder account is linked, all existing rows should remain
-- present and user_id should be NULL.
--
-- DO NOT make user_id NOT NULL, assign a guessed UUID, drop existing indexes,
-- or enable RLS as part of this migration.
