#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Realtor Call Calculator (No Acronyms) + ZIP Income + Qualifying-Income Rule of Thumb
Author: ChatGPT (GPT-5 Thinking)
Date: 2025-08-15

What's new
----------
- Added **Rule-of-thumb qualifying income** section placed **right after** the ZIP income results.
  It shows both a Canada-style stress test estimate and a U.S. 28/36 guideline estimate.
- Kept buttons: "Fetch incomes by ZIP", "Fetch income + Calculate", and "Calculate".
- Added an optional input: **Other monthly debts ($/month)** to improve the "including debts" estimates.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math, re, json

# ---- Lightweight HTTP helper (requests if available; else urllib) -----------------
def http_get_json(url, timeout=10):
    try:
        import requests
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        # Fallback to urllib
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data = resp.read()
                return json.loads(data.decode('utf-8'))
        except Exception as e:
            raise e

# ---- Number helpers ----------------------------------------------------------------

def parse_money(s, default=0.0):
    if s is None: return float(default)
    s = s.strip()
    if not s: return float(default)
    s = re.sub(r'[,$% ]', '', s)
    try: return float(s)
    except ValueError: return float(default)

def money(x, zero='0'):
    try: x = float(x)
    except Exception: return zero
    sign = '-' if x < 0 else ''
    x = abs(x)
    if abs(x - round(x)) < 1e-6: return f"{sign}${int(round(x)):,}"
    return f"{sign}${x:,.2f}"

def pct(x):
    try: return f"{float(x):.2f}%"
    except Exception: return "0.00%"

def mortgage_payment(loan_amount, annual_rate_pct, years):
    L = float(loan_amount); r_annual = float(annual_rate_pct) / 100.0; n = int(years) * 12
    if n <= 0: return 0.0
    if r_annual == 0: return L / n
    r = r_annual / 12.0
    return (r * L) / (1.0 - (1.0 + r) ** -n)

def inverse_loan_amount(target_monthly_PI, annual_rate_pct, years):
    P = float(target_monthly_PI); r_annual = float(annual_rate_pct) / 100.0; n = int(years) * 12
    if n <= 0: return 0.0
    if r_annual == 0: return P * n
    r = r_annual / 12.0
    return P * (1.0 - (1.0 + r) ** -n) / r

def clamp_price(x):
    try: return max(0.0, math.floor(float(x) / 1000.0) * 1000.0)
    except Exception: return 0.0

# ---- GUI ---------------------------------------------------------------------------

class PlaceholderEntry(ttk.Entry):
    def __init__(self, master=None, placeholder="", **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder; self.default_fg = self.cget("foreground") or "black"
        self.placeholder_fg = "gray"; self.has_placeholder = False; self._add_placeholder()
        self.bind("<FocusIn>", self._focus_in); self.bind("<FocusOut>", self._focus_out)
    def _add_placeholder(self):
        if not self.get():
            self.has_placeholder = True; self.insert(0, self.placeholder); self.config(foreground=self.placeholder_fg)
    def _focus_in(self, _event):
        if self.has_placeholder:
            self.delete(0, tk.END); self.config(foreground=self.default_fg); self.has_placeholder = False
    def _focus_out(self, _event):
        if not self.get(): self._add_placeholder()
    def get_value(self):
        val = self.get().strip()
        if self.has_placeholder or val == self.placeholder: return ""
        return val

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Realtor Call Calculator (No Acronyms) + ZIP Income + Qualifying Rule")
        self.geometry("1080x860")
        self.minsize(1020, 800)
        self.fetched_zip = None
        self.fetched_median = None
        self.fetched_mean = None
        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=10); main.pack(fill="both", expand=True)

        # Inputs frame
        inputs = ttk.LabelFrame(main, text="Inputs")
        inputs.pack(side="top", fill="x", padx=5, pady=5)

        # Row 0 - Address + ZIP
        self.e_address = PlaceholderEntry(inputs, width=28, placeholder="123 Main St (optional)")
        self._add_labeled(inputs, "Address:", self.e_address, r=0, c=0)

        self.e_zip = PlaceholderEntry(inputs, width=12, placeholder="ZIP (US, e.g., 90210)")
        self._add_labeled(inputs, "ZIP (US):", self.e_zip, r=0, c=2)

        ttk.Button(inputs, text="Fetch incomes by ZIP", command=self.fetch_incomes).grid(row=0, column=4, padx=6, pady=4, sticky="w")
        ttk.Button(inputs, text="Fetch income + Calculate", command=self.fetch_and_calculate).grid(row=0, column=5, padx=6, pady=4, sticky="w")

        # Row 1 - Price/Rent
        self.e_ask = PlaceholderEntry(inputs, width=16, placeholder="500000")
        self._add_labeled(inputs, "Asking price ($):", self.e_ask, r=1, c=0)

        self.e_rent = PlaceholderEntry(inputs, width=12, placeholder="3000")
        self._add_labeled(inputs, "Market or actual rent ($/month):", self.e_rent, r=1, c=2)

        # Row 2 - Financing
        self.e_down = PlaceholderEntry(inputs, width=12, placeholder="20")
        self._add_labeled(inputs, "Down payment (%):", self.e_down, r=2, c=0)

        self.e_rate = PlaceholderEntry(inputs, width=12, placeholder="7.0")
        self._add_labeled(inputs, "Annual interest rate (%):", self.e_rate, r=2, c=2)

        self.e_years = PlaceholderEntry(inputs, width=12, placeholder="30")
        self._add_labeled(inputs, "Loan term (years):", self.e_years, r=2, c=4)

        # Row 3 - Carry costs
        self.e_taxes = PlaceholderEntry(inputs, width=12, placeholder="3600")
        self._add_labeled(inputs, "Property taxes ($/year):", self.e_taxes, r=3, c=0)

        self.e_ins = PlaceholderEntry(inputs, width=12, placeholder="1200")
        self._add_labeled(inputs, "Home insurance ($/year):", self.e_ins, r=3, c=2)

        self.e_hoa = PlaceholderEntry(inputs, width=12, placeholder="0")
        self._add_labeled(inputs, "Association/condo fees ($/month):", self.e_hoa, r=3, c=4)

        # Row 4 - Risk reserves
        self.e_vac = PlaceholderEntry(inputs, width=12, placeholder="10")
        self._add_labeled(inputs, "Vacancy (% of rent):", self.e_vac, r=4, c=0)

        self.e_maint = PlaceholderEntry(inputs, width=12, placeholder="8")
        self._add_labeled(inputs, "Maintenance (% of rent):", self.e_maint, r=4, c=2)

        # Row 5 - Seller net
        self.e_comm = PlaceholderEntry(inputs, width=12, placeholder="6")
        self._add_labeled(inputs, "Agent commission (% of price):", self.e_comm, r=5, c=0)

        self.e_closepct = PlaceholderEntry(inputs, width=12, placeholder="1")
        self._add_labeled(inputs, "Other closing costs (% of price):", self.e_closepct, r=5, c=2)

        self.e_payoff = PlaceholderEntry(inputs, width=12, placeholder="0")
        self._add_labeled(inputs, "Seller's mortgage payoff ($):", self.e_payoff, r=5, c=4)

        # Row 6 - Comparison price and targeting
        self.e_optimistic = PlaceholderEntry(inputs, width=12, placeholder="(blank = use asking price)")
        self._add_labeled(inputs, "Optimistic sale price for comparison ($):", self.e_optimistic, r=6, c=0)

        self.e_piti_share = PlaceholderEntry(inputs, width=12, placeholder="80")
        self._add_labeled(inputs, "Target maximum total monthly housing cost ≤ (% of rent):", self.e_piti_share, r=6, c=2)

        # Row 7 - Other debts
        self.e_other_debt = PlaceholderEntry(inputs, width=12, placeholder="0")
        self._add_labeled(inputs, "Other monthly debts ($/month):", self.e_other_debt, r=7, c=0)

        # Controls
        btns = ttk.Frame(main); btns.pack(fill="x", pady=(4, 0))
        ttk.Button(btns, text="Calculate", command=self.calculate).pack(side="left")
        ttk.Button(btns, text="Reset", command=self.reset).pack(side="left", padx=6)
        ttk.Button(btns, text="Copy Summary", command=self.copy_summary).pack(side="left")

        # Output
        out = ttk.LabelFrame(main, text="Results")
        out.pack(side="top", fill="both", expand=True, padx=5, pady=8)

        self.txt = tk.Text(out, wrap="word", height=30)
        self.txt.pack(fill="both", expand=True)
        self.txt.insert("1.0", "Enter inputs above and click Calculate. Optionally fetch incomes by ZIP (US).")

        # Footer tips
        tips = ttk.LabelFrame(main, text="Quick Rules / Tips (no acronyms)")
        tips.pack(side="bottom", fill="x", padx=5, pady=5)
        ttk.Label(
            tips, justify="left",
            text=("• Net to seller after a typical 6% agent commission ≈ price × 0.94\n"
                  "• Estimated income needed to qualify (28% rule): (total monthly housing cost × 12) ÷ 0.28\n"
                  "• Canada stress test uses the greater of (your rate + 2%) or 5.25% to compute the payment; housing-only limit ≈ 39%, including other debts ≈ 44%.\n"
                  "• Monthly cash flow: rent − total monthly housing cost − vacancy%×rent − maintenance%×rent\n"
                  "• Coverage ratio ≈ (monthly income after vacancy, taxes, insurance, association/condo fees, and maintenance) ÷ (monthly principal and interest)\n"
                  "• ZIP lookup uses Census ZCTA (most ZIPs match; PO boxes may not).")
        ).pack(side="left", padx=6, pady=6)

    def _add_labeled(self, parent, label, entry, r=0, c=0):
        ttk.Label(parent, text=label).grid(row=r, column=c, sticky="w", padx=6, pady=4)
        entry.grid(row=r, column=c+1, sticky="we", padx=4, pady=4)
        parent.grid_columnconfigure(c+1, weight=1)

    # ----- Income fetch internals --------------------------------------------------
    def _fetch_incomes_core(self, zcta):
        url = ("https://api.census.gov/data/2023/acs/acs5"
               "?get=NAME,B19013_001E,B19025_001E,B11001_001E"
               f"&for=zip%20code%20tabulation%20area:{zcta}")
        data = http_get_json(url, timeout=12)
        if not isinstance(data, list) or len(data) < 2:
            raise ValueError("No data returned for that ZIP (ZCTA).")
        headers = data[0]; vals = data[1]
        idx_median = headers.index("B19013_001E")
        idx_agg = headers.index("B19025_001E")
        idx_households = headers.index("B11001_001E")
        median = float(vals[idx_median]) if vals[idx_median] not in (None, "", "null") else float("nan")
        agg = float(vals[idx_agg]) if vals[idx_agg] not in (None, "", "null") else float("nan")
        hh = float(vals[idx_households]) if vals[idx_households] not in (None, "", "null") else float("nan")
        mean = (agg / hh) if (isinstance(agg, float) and isinstance(hh, float) and hh > 0) else float("nan")
        return median, mean

    def fetch_incomes(self):
        zip_raw = self.e_zip.get_value().strip()
        if not zip_raw or not zip_raw.isdigit() or len(zip_raw) != 5:
            messagebox.showwarning("ZIP required", "Please enter a 5-digit US ZIP code (digits only).")
            return
        zcta = zip_raw
        try:
            median, mean = self._fetch_incomes_core(zcta)
            self.fetched_zip = zcta; self.fetched_median = median; self.fetched_mean = mean
            info = (f"Fetched incomes for ZCTA {zcta}:\n"
                    f"• Median household income: {money(median)}\n"
                    f"• Average household income (computed): {money(mean)}\n\n"
                    "Click Calculate to include these in the results.")
            messagebox.showinfo("ZIP incomes", info)
        except Exception as e:
            messagebox.showerror("Fetch failed",
                                 f"Could not fetch data for ZIP {zcta}.\n"
                                 f"Reason: {e}\n\n"
                                 "Note: Some ZIPs (e.g., PO boxes) do not have ZCTA data.")

    def fetch_and_calculate(self):
        zip_raw = self.e_zip.get_value().strip()
        if not zip_raw or not zip_raw.isdigit() or len(zip_raw) != 5:
            messagebox.showwarning("ZIP required", "Please enter a 5-digit US ZIP code (digits only).")
            # Still run calculate without incomes, to be helpful
            self.calculate()
            return
        zcta = zip_raw
        try:
            median, mean = self._fetch_incomes_core(zcta)
            self.fetched_zip = zcta; self.fetched_median = median; self.fetched_mean = mean
        except Exception as e:
            messagebox.showerror("Fetch failed",
                                 f"Could not fetch data for ZIP {zcta}.\n"
                                 f"Reason: {e}\n\n"
                                 "Proceeding with calculation without ZIP incomes.")
        # Always run calculation so results include incomes if available
        self.calculate()

    # ----- Inputs and calculation --------------------------------------------------
    def get_inputs(self):
        def P(e, default): return parse_money(e.get_value(), default)
        ask = P(self.e_ask, 500000); rent = P(self.e_rent, 3000); down_pct = P(self.e_down, 20)
        rate = P(self.e_rate, 7.0); years = P(self.e_years, 30)
        taxes_y = P(self.e_taxes, 3600); ins_y = P(self.e_ins, 1200); hoa_m = P(self.e_hoa, 0)
        vac_pct = P(self.e_vac, 10); maint_pct = P(self.e_maint, 8)
        comm_pct = P(self.e_comm, 6); close_pct = P(self.e_closepct, 1); payoff = P(self.e_payoff, 0)
        optimistic = parse_money(self.e_optimistic.get_value(), ask)
        piti_share_pct = P(self.e_piti_share, 80)
        other_debt_m = P(self.e_other_debt, 0)
        address = self.e_address.get_value().strip()
        return dict(address=address, ask=ask, rent=rent, down_pct=down_pct, rate=rate, years=years,
                    taxes_y=taxes_y, ins_y=ins_y, hoa_m=hoa_m, vac_pct=vac_pct, maint_pct=maint_pct,
                    comm_pct=comm_pct, close_pct=close_pct, payoff=payoff, optimistic=optimistic,
                    piti_share_pct=piti_share_pct, other_debt_m=other_debt_m)

    def calculate(self):
        try:
            X = self.get_inputs()
            addr = X["address"]; ask = X["ask"]; rent = X["rent"]
            down_pct = X["down_pct"]; rate = X["rate"]; years = int(X["years"])
            taxes_y = X["taxes_y"]; ins_y = X["ins_y"]; hoa_m = X["hoa_m"]
            vac_pct = X["vac_pct"]/100.0; maint_pct = X["maint_pct"]/100.0
            comm_pct = X["comm_pct"]/100.0; close_pct = X["close_pct"]/100.0
            payoff = X["payoff"]; optimistic = X["optimistic"]; piti_share_pct = X["piti_share_pct"]/100.0
            other_debt_m = X["other_debt_m"]

            down = ask * (down_pct/100.0); loan = max(0.0, ask - down)
            principal_interest = mortgage_payment(loan, rate, years)
            total_housing = principal_interest + (taxes_y/12.0) + (ins_y/12.0) + hoa_m
            vacancy = rent * vac_pct; maintenance = rent * maint_pct
            cash_flow = rent - total_housing - vacancy - maintenance

            monthly_income_after_expenses = rent - vacancy - (taxes_y/12.0) - (ins_y/12.0) - hoa_m - maintenance
            coverage_ratio = (monthly_income_after_expenses / principal_interest) if principal_interest > 0 else float('inf')

            income_needed_28 = (total_housing / 0.28) if total_housing > 0 else 0.0  # monthly
            income_needed_28_y = income_needed_28 * 12.0

            # US 36% including other debts
            income_needed_36 = ((total_housing + other_debt_m) / 0.36) if total_housing > 0 else 0.0  # monthly
            income_needed_36_y = income_needed_36 * 12.0

            # Canada stress test: greater of (rate + 2%) or 5.25%
            stress_rate = max(rate + 2.0, 5.25)
            pi_stress = mortgage_payment(loan, stress_rate, years)
            total_housing_stress = pi_stress + (taxes_y/12.0) + (ins_y/12.0) + 0.5 * hoa_m

            income_needed_ca_housing = (total_housing_stress / 0.39) if total_housing_stress > 0 else 0.0  # monthly (housing-only limit 39%)
            income_needed_ca_housing_y = income_needed_ca_housing * 12.0

            income_needed_ca_debts = ((total_housing_stress + other_debt_m) / 0.44) if total_housing_stress > 0 else 0.0  # monthly (including debts limit 44%)
            income_needed_ca_debts_y = income_needed_ca_debts * 12.0

            ca_binding_y = max(income_needed_ca_housing_y, income_needed_ca_debts_y)

            gross = optimistic; fees = gross * comm_pct; other = gross * close_pct
            net_to_seller = gross - fees - other - payoff

            total_housing_cap = max(0.0, rent * (1.0 - (X['vac_pct']/100.0) - (X['maint_pct']/100.0)))
            principal_interest_cap = max(0.0, total_housing_cap - (taxes_y/12.0) - (ins_y/12.0) - hoa_m)
            loan_cap = inverse_loan_amount(principal_interest_cap, rate, years)
            price_cap_cf0 = loan_cap / (1.0 - (down_pct/100.0)) if (1.0 - (down_pct/100.0)) > 0 else 0.0
            price_cap_cf0 = clamp_price(price_cap_cf0)

            total_housing_cap2 = rent * piti_share_pct
            principal_interest_cap2 = max(0.0, total_housing_cap2 - (taxes_y/12.0) - (ins_y/12.0) - hoa_m)
            loan_cap2 = inverse_loan_amount(principal_interest_cap2, rate, years)
            price_cap_pitishare = loan_cap2 / (1.0 - (down_pct/100.0)) if (1.0 - (down_pct/100.0)) > 0 else 0.0
            price_cap_pitishare = clamp_price(price_cap_pitishare)

            lines = []
            header = f"Address: {addr}" if addr else "Address: (not provided)"
            lines += [header, "="*78,
                      f"Asking price: {money(ask)}",
                      f"Down payment: {pct(down_pct)} = {money(down)}",
                      f"Loan amount: {money(loan)}",
                      f"Interest rate / term: {X['rate']}% / {years} years",
                      f"Property taxes: {money(taxes_y)}/year  |  Home insurance: {money(ins_y)}/year  |  Association/condo: {money(hoa_m)}/month",
                      f"Rent: {money(rent)}/month  |  Vacancy: {pct(X['vac_pct'])} of rent  |  Maintenance: {pct(X['maint_pct'])} of rent",
                      "-"*78,
                      f"Monthly principal and interest payment: {money(principal_interest)}",
                      f"Total monthly housing cost (principal + interest + tax + insurance + association/condo): {money(total_housing)}",
                      f"Estimated monthly cash flow ≈ rent − total housing − vacancy − maintenance = {money(cash_flow)}/month",
                      f"Coverage ratio ≈ (monthly income after vacancy, taxes, insurance, association/condo, and maintenance) ÷ (monthly principal and interest) = {'infinite' if coverage_ratio == float('inf') else f'{coverage_ratio:.2f}'}",
                      f"Estimated gross annual income needed to qualify (28% rule): {money(income_needed_28_y)}/year",
                      "-"*78,
                      f"Comparison price: {money(optimistic)}  |  Agent commission: {pct(X['comm_pct'])}  |  Other closing costs: {pct(X['close_pct'])}",
                      f"Seller's mortgage payoff: {money(payoff)}  |  Estimated net to seller today: {money(net_to_seller)}",
                      "-"*78, "Offer targets",
                      f"• Maximum price that avoids negative monthly cash flow: {money(price_cap_cf0)}",
                      f"• Conservative price (total monthly housing cost ≤ {pct(X['piti_share_pct'])} of rent): {money(price_cap_pitishare)}",
                      "-"*78]

            # Append ZIP incomes if fetched
            if self.fetched_zip and (self.fetched_median is not None or self.fetched_mean is not None):
                lines.append(f"Area incomes for ZCTA {self.fetched_zip}:")
                if isinstance(self.fetched_median, float):
                    lines.append(f"• Median household income: {money(self.fetched_median)}")
                if isinstance(self.fetched_mean, float):
                    lines.append(f"• Average household income (computed): {money(self.fetched_mean)}")
                lines.append(f"• Your required income vs area median (28% rule): {money(income_needed_28_y)} vs {money(self.fetched_median)}")
                lines.append(f"• Your required income vs area average (28% rule): {money(income_needed_28_y)} vs {money(self.fetched_mean)}")
                # --- Rule-of-thumb qualifying income section (immediately after ZIP incomes) ---
                lines.append("Rule-of-thumb qualifying income estimates:")
                lines.append(f"• Canada stress test (greater of your rate + 2% or 5.25% → {stress_rate:.2f}%):")
                lines.append(f"    - Housing cost only (≈39% limit): {money(income_needed_ca_housing_y)}/year")
                lines.append(f"    - Including other monthly debts at {money(other_debt_m)}/month (≈44% limit): {money(income_needed_ca_debts_y)}/year")
                lines.append(f"    - Higher of the two applies: {money(ca_binding_y)}/year")
                lines.append("• U.S. style 28/36 guideline:")
                lines.append(f"    - Housing cost only (28%): {money(income_needed_28_y)}/year")
                lines.append(f"    - Including other monthly debts (36%): {money(income_needed_36_y)}/year")

            lines.append("="*78)

            self.last_summary = "\n".join(lines)
            self.txt.delete("1.0", tk.END); self.txt.insert("1.0", self.last_summary)

        except Exception as e:
            messagebox.showerror("Error", f"Calculation failed:\n{e}")

    # ----- Misc/UI helpers ---------------------------------------------------------
    def reset(self):
        for e in [self.e_address, self.e_zip, self.e_ask, self.e_rent, self.e_down, self.e_rate, self.e_years,
                  self.e_taxes, self.e_ins, self.e_hoa, self.e_vac, self.e_maint,
                  self.e_comm, self.e_closepct, self.e_payoff, self.e_optimistic, self.e_piti_share, self.e_other_debt]:
            e.delete(0, tk.END); e._add_placeholder()
        self.txt.delete("1.0", tk.END)
        self.txt.insert("1.0", "Enter inputs above and click Calculate. Optionally fetch incomes by ZIP (US).")
        self.last_summary = ""
        self.fetched_zip = self.fetched_median = self.fetched_mean = None

    def copy_summary(self):
        if not hasattr(self, "last_summary") or not self.last_summary:
            messagebox.showinfo("Nothing to copy", "Run Calculate first."); return
        try:
            import pyperclip; pyperclip.copy(self.last_summary); messagebox.showinfo("Copied", "Summary copied to clipboard.")
        except Exception:
            self.clipboard_clear(); self.clipboard_append(self.last_summary); messagebox.showinfo("Copied", "Summary copied to clipboard (Tk).")

if __name__ == "__main__":
    app = App(); app.mainloop()
