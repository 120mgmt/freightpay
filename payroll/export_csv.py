import csv
import io

def settlements_to_csv(payroll_results):
    """
    payroll_results: output of run_payroll()
    Return CSV string.
    """
  output = io.StringIO()
  writer.writerow([
      "contractor_id",
      "pay_type",
      "gross",
      "additions",
      "deductions",
      "net"
  ])
for r in payroll_results:
    s = r.get(settlement", {})
   writer.writerow([
       r.get("contractor_id"),
       r.get("pay_type"),
       r.get("gross"),
       r.get(  "additions"),
       r.get(  "deductions"),
       r.get( "deductions"),
       r.get( "net"),
   ])
return output.getvalue()              
