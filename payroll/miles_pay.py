def calculate_miles_pay(miles, rate_per_mile):
    """
    Trucking pay-per-mile calculation.
    """
  if miles < 0 or rate_per_mile < 0:
      raise ValueError("Miles and rate must be non-negative")
    return round(miles * rate_per_mile, 2)
