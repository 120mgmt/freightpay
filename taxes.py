# payroll/taxes.py

def calculate_taxes(gross_pay, tax_rate=0.15):
    return round(gross_pay * tax_rate, 2)

def net_after_taxes(gross_pay, tax_rate=0.15):
    taxes = calculate_taxes(gross_pay, tax_rate)
    return round(gross_pay - taxes, 2)
