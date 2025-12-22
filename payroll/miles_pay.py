def calculate_miles_pay(miles, rate_per_mile): 
    miles = float(miles)
    rate_per_mile = float(rate_per_mile)
   if miles < 0 or rate_per_mile < 0:
       raise ValueError("Miles and rate must be non-nagative")
       return round(miles * rate_per_mile, 2)
