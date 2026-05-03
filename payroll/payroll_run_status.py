# payroll/payroll_run_status.py

def can_edit_payroll_run(db, payroll_run_id: str) -> bool:
    row = db.execute(
        "SELECT status FROM payroll_runs WHERE id = %s",
        (payroll_run_id,),
    ).fetchone()

    if not row:
        return True
    return (row[0] or "").lower() == "draft"


def finalize_payroll_run(db, payroll_run_id: str, user_id: str) -> None:
    db.execute(
        """
        UPDATE payroll_runs
        SET status = 'finalized',
            finalized_at = NOW(),
            finalized_by = %s
        WHERE id = %s AND status = 'draft'
        """,
        (user_id, payroll_run_id),
    )
    db.commit()


def lock_payroll_run(db, payroll_run_id: str) -> None:
    db.execute(
        """
        UPDATE payroll_runs
        SET status = 'locked'
        WHERE id = %s AND status = 'finalized'
        """,
        (payroll_run_id,),
    )
    db.commit()


