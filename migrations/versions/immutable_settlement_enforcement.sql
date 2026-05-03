-- File: migrations/versions/immutable_settlement_enforcement.sql
-- Purpose: Absolute immutability enforcement for locked settlements
-- Status: Enterprise hardened

-- ============================================================
-- 1. Prevent updates to locked settlement headers
-- ============================================================

CREATE OR REPLACE FUNCTION prevent_locked_settlement_update()
RETURNS trigger AS $$
BEGIN
    IF OLD.locked = TRUE THEN
        RAISE EXCEPTION 'Locked settlement cannot be modified';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_locked_settlement_update
ON driver_settlements;

CREATE TRIGGER trg_prevent_locked_settlement_update
BEFORE UPDATE OR DELETE
ON driver_settlements
FOR EACH ROW
EXECUTE FUNCTION prevent_locked_settlement_update();


-- ============================================================
-- 2. Prevent modification of settlement lines if parent locked
-- ============================================================

CREATE OR REPLACE FUNCTION prevent_locked_settlement_line_update()
RETURNS trigger AS $$
DECLARE
    parent_locked BOOLEAN;
BEGIN
    SELECT locked INTO parent_locked
    FROM driver_settlements
    WHERE id = COALESCE(NEW.settlement_id, OLD.settlement_id);

    IF parent_locked = TRUE THEN
        RAISE EXCEPTION 'Settlement lines cannot be modified after settlement is locked';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_locked_settlement_line_update
ON driver_settlement_lines;

CREATE TRIGGER trg_prevent_locked_settlement_line_update
BEFORE INSERT OR UPDATE OR DELETE
ON driver_settlement_lines
FOR EACH ROW
EXECUTE FUNCTION prevent_locked_settlement_line_update();


-- ============================================================
-- 3. Prevent load status reversal after settlement
-- ============================================================

CREATE OR REPLACE FUNCTION prevent_settled_load_reopen()
RETURNS trigger AS $$
BEGIN
    IF OLD.status = 'settled' AND NEW.status <> 'settled' THEN
        RAISE EXCEPTION 'Settled loads cannot be reopened';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_settled_load_reopen
ON loads;

CREATE TRIGGER trg_prevent_settled_load_reopen
BEFORE UPDATE
ON loads
FOR EACH ROW
EXECUTE FUNCTION prevent_settled_load_reopen();
