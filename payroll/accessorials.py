# payroll/accessorials.py

def calculate_accessorials(data: dict) -> dict:
    """
    Handles trucking accessorials.
    All values are optional and default to 0.0
    """
    return {
        "tonu": float(data.get("tonu", 0.0)),
        "detention": float(data.get("detention", 0.0)),
        "layover": float(data.get("layover", 0.0)),
        "lumper": float(data.get("lumper", 0.0)),
        "stop_pay": float(data.get("stop_pay", 0.0)),
        "fuel_surcharge": float(data.get("fuel_surcharge", 0.0)),
    }
