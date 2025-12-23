# FreightPay/integrations/gusto/client.py

import requests
from .config import GustoConfig


class GustoClient:
    def __init__(self):
        self.config = GustoConfig()
        self.base_url = self.config.base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # ---------- Core ----------
    def _get(self, path, params=None):
        r = self.session.get(f"{self.base_url}{path}", params=params)
        r.raise_for_status()
        return r.json()

    def _post(self, path, payload=None):
        r = self.session.post(f"{self.base_url}{path}", json=payload or {})
        r.raise_for_status()
        return r.json()

    # ---------- Company ----------
    def get_companies(self):
        return self._get("/v1/companies")

    def get_company(self, company_id):
        return self._get(f"/v1/companies/{company_id}")

    # ---------- Contractors ----------
    def list_contractors(self, company_id):
        return self._get(f"/v1/companies/{company_id}/contractors")

    def create_contractor(self, company_id, payload):
        return self._post(f"/v1/companies/{company_id}/contractors", payload)

    # ---------- Employees ----------
    def list_employees(self, company_id):
        return self._get(f"/v1/companies/{company_id}/employees")

    def create_employee(self, company_id, payload):
        return self._post(f"/v1/companies/{company_id}/employees", payload)

    # ---------- Payroll ----------
    def get_payrolls(self, company_id):
        return self._get(f"/v1/companies/{company_id}/payrolls")

    def create_payroll(self, company_id, payload):
        return self._post(f"/v1/companies/{company_id}/payrolls", payload)

    def submit_payroll(self, company_id, payroll_id):
        return self._post(f"/v1/companies/{company_id}/payrolls/{payroll_id}/submit")

    # ---------- Earnings ----------
    def add_earnings(self, payroll_id, payload):
        return self._post(f"/v1/payrolls/{payroll_id}/earnings", payload)

    # ---------- Deductions ----------
    def add_deductions(self, payroll_id, payload):
        return self._post(f"/v1/payrolls/{payroll_id}/deductions", payload)

    # ---------- Reimbursements ----------
    def add_reimbursements(self, payroll_id, payload):
        return self._post(f"/v1/payrolls/{payroll_id}/reimbursements", payload)

