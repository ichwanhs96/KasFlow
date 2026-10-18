EXTRACTION_RULES = """Extract EVERY individual monetary transaction row. Rules:
- date: ISO YYYY-MM-DD. If the year is missing, assume the most recent year such that the date is not after {reference_date}.
- amount: positive number in major currency units. Indonesian/Vietnamese formats use "." for thousands and "," for decimals
  (e.g. "1.250.000" = 1250000). Philippine format uses "," for thousands. "Rp", "₱", "đ", "VND", "k" (= x1000) may appear.
- direction: "in" for money received (credit, CR, masuk, pemasukan, terima, natanggap, thu, +), otherwise "out".
- balance: only if a running-balance column is printed for that row; never compute it yourself; otherwise null.
- kind: "returned" for bounced/reversed/returned items; "loan_repayment" for loan instalments
  (cicilan, angsuran, hulog, trả góp, loan); otherwise "normal".
- counterparty: the other party's name if shown, else null.
- Skip opening/closing balances, totals and subtotals. Never invent rows. If a value is illegible, skip that row.
- For handwritten ledgers, a row with an amount in the income/masuk column is "in"; expense/keluar column is "out".
- If the document contains no transactions, return an empty rows list.
Return JSON matching the schema."""

EXTRACT_PROMPT = """You are a financial document parser working for a credit-assessment service in Southeast Asia.
The attached file was provided by a customer in {country_name}. It may be a bank statement, an
e-wallet transaction history screenshot, a QRIS merchant settlement report, a receipt, or a
photo of a handwritten cash ledger (e.g. Indonesian "buku kas", Filipino "kuwaderno", Vietnamese "sổ thu chi").

""" + EXTRACTION_RULES

JSON_MAP_PROMPT = """You are a financial data mapper for a credit-assessment service in Southeast Asia.
The JSON below was sent by a partner system for a customer in {country_name}. Find every monetary transaction in it.

""" + EXTRACTION_RULES + """

JSON:
{payload}"""

CSV_MAPPING_PROMPT = """You map the columns of a CSV export (bank, e-wallet or QRIS merchant report) from a customer in
{country_name} to transaction fields. Return only the mapping.
Header: {header}
First rows: {rows}
Rules:
- date_column and date_format (Python strftime, e.g. %d-%m-%Y) are required.
- Use amount_column for a single amount column; otherwise debit_column (money out) and credit_column (money in).
- direction_column and direction_in_values only if a separate column says in/out (e.g. CR/DR, Masuk/Keluar); else null and [].
- thousands_separator ("none" if the amounts have no thousands separator)/decimal_separator: Indonesian & Vietnamese exports use "." thousands and "," decimals;
  Philippine exports use "," thousands and "." decimals.
- channel: "qris" for QRIS merchant reports, "ewallet" for e-wallets, "bank" for bank exports, else "other".
- status_column and success_values: if a status column exists, list the values meaning success (e.g. BERHASIL, SUCCESS);
  otherwise null and [].
- Column names must be copied exactly from the header. Use null for absent fields."""

SUMMARY_PROMPT = """You are a credit analyst assistant. Write an assessment summary for a {purpose} decision using ONLY the data below.
Rules:
- Do not state any number that is not present in the input; do not recompute or change the score or recommendation.
- Every strength and risk must cite exactly one metric key from: {metric_keys}.
- 2-4 strengths, 2-4 risks, 1-3 data_notes (mention source trust, uploads vs verified data, tamper flags if any),
  2-3 next_steps for the analyst.
- Neutral, factual tone. Never reference gender, religion, ethnicity, age, or any protected attribute.
- customer_explanation_local: in {language_name}, 80-120 words, friendly plain language addressed to the customer:
  what their financial data shows and exactly 3 practical tips to strengthen their profile. Do NOT state the score,
  grade, or a final decision (the client company makes the decision).
- customer_explanation_en: the same text in English.
- headline at most 120 characters.
DATA:
{json}"""
