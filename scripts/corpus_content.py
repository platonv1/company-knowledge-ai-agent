"""Content for the Jarvis Financial Group demo corpus.

Entirely fictional. Facts are chosen so the golden set has unambiguous expected
answers, and so specific failure modes are testable:

* `Leave_Policy_v1` (archived, 12 days) vs `Leave_Policy_v2` (active, 15 days)
  catches a retriever that ignores document status.
* The fee schedule table catches extraction that flattens tables into mush.
* `UNANSWERABLE` lists questions whose answers are deliberately absent, so
  over-confident answering is measurable rather than anecdotal.
"""

from scripts.corpus_schema import (
    Document,
    Fact,
    Followup,
    Section,
    Table,
    Unanswerable,
)

COMPANY = "Jarvis Financial Group"

# --------------------------------------------------------------------------
# 1. Company Profile
# --------------------------------------------------------------------------

COMPANY_PROFILE = Document(
    filename="Company_Profile.pdf",
    title="Company Profile",
    subtitle="Corporate Overview and Strategic Direction",
    doc_type="Corporate",
    version="4.1",
    effective_date="2026-01-01",
    sections=[
        Section(
            number="1",
            heading="About Jarvis Financial Group",
            paragraphs=[
                "Jarvis Financial Group is a full-service commercial and retail banking "
                "institution headquartered in Northgate. The Group provides deposit, "
                "lending, payment, and advisory services to individuals, small businesses, "
                "and mid-market corporate clients across four operating regions.",
                "As of the most recent reporting period, the Group employs 2,400 staff and "
                "operates 48 branches, supported by a digital banking platform serving "
                "approximately 310,000 active customers.",
                "The Group is regulated as a deposit-taking institution and is subject to "
                "prudential supervision, consumer protection obligations, and anti-money "
                "laundering requirements described elsewhere in this knowledge base.",
            ],
        ),
        Section(
            number="2",
            heading="History and Milestones",
            paragraphs=[
                "Jarvis Financial Group was founded in 1985 by Eleanor M. Jarvis, who "
                "established the original Northgate Savings and Loan office with eleven "
                "members of staff and a single branch on Caldwell Street.",
                "The institution was renamed Jarvis Financial Group in 1998 following the "
                "acquisition of Meridian Trust, which extended the Group's operations into "
                "commercial lending for the first time.",
            ],
            bullets=[
                "1985 — Founded in Northgate as Northgate Savings and Loan.",
                "1992 — Opened the tenth branch and introduced the first automated teller network.",
                "1998 — Acquired Meridian Trust and adopted the Jarvis Financial Group name.",
                "2007 — Launched online banking for retail customers.",
                "2015 — Opened the Corporate Banking Division serving mid-market clients.",
                "2021 — Completed migration to a cloud-based core banking platform.",
                "2024 — Established the Office of Data Governance and Responsible AI.",
            ],
        ),
        Section(
            number="3",
            heading="Mission, Vision, and Core Values",
            paragraphs=[
                "The Group's mission is to help customers build durable financial security "
                "through transparent products, sound advice, and dependable service.",
                "The Group's vision is to be the most trusted regional financial institution "
                "in the markets it serves, measured by customer confidence rather than by "
                "balance sheet size alone.",
                "Five core values govern how the Group operates and how staff are expected "
                "to conduct themselves:",
            ],
            bullets=[
                "Integrity — We act honestly even when no one is reviewing our work.",
                "Stewardship — We treat customer deposits as a responsibility, not a resource.",
                "Clarity — We explain products in language customers can act on.",
                "Accountability — We own outcomes, including unfavourable ones.",
                "Inclusion — We serve and employ the full breadth of our communities.",
            ],
        ),
        Section(
            number="4",
            heading="Leadership and Governance",
            paragraphs=[
                "The Group is led by Chief Executive Officer Adaeze Okonkwo, appointed in "
                "2019, and governed by a Board of Directors comprising nine members, six of "
                "whom are independent non-executive directors.",
                "The Board maintains four standing committees: Audit, Risk, Remuneration, "
                "and Nominations. The Audit Committee meets at least six times per year and "
                "is chaired by an independent director with recognised financial expertise.",
                "Day-to-day management is delegated to the Executive Committee, which "
                "comprises the Chief Executive Officer, Chief Financial Officer, Chief Risk "
                "Officer, Chief Operating Officer, and the Group Head of Human Resources.",
            ],
        ),
        Section(
            number="5",
            heading="Operating Footprint",
            paragraphs=[
                "The Group operates across four regions: Northgate Metropolitan, Eastern "
                "Counties, Southern Coast, and the Western Uplands. Each region is led by a "
                "Regional Director reporting to the Chief Operating Officer.",
                "Branch distribution is weighted toward Northgate Metropolitan, which "
                "accounts for 19 of the 48 branches and approximately 41 per cent of retail "
                "deposits.",
            ],
            table=Table(
                caption="Table 5.1 — Branch distribution by region",
                columns=["Region", "Branches", "Staff", "Share of retail deposits"],
                rows=[
                    ["Northgate Metropolitan", "19", "940", "41%"],
                    ["Eastern Counties", "12", "610", "24%"],
                    ["Southern Coast", "10", "505", "21%"],
                    ["Western Uplands", "7", "345", "14%"],
                ],
            ),
        ),
    ],
)

# --------------------------------------------------------------------------
# 2. Employee Handbook
# --------------------------------------------------------------------------

EMPLOYEE_HANDBOOK = Document(
    filename="Employee_Handbook.pdf",
    title="Employee Handbook",
    subtitle="Terms, Benefits, and Workplace Standards",
    doc_type="HR Policy",
    version="7.0",
    effective_date="2026-01-01",
    sections=[
        Section(
            number="1",
            heading="Purpose and Scope",
            paragraphs=[
                "This Handbook sets out the terms, benefits, and standards of conduct that "
                "apply to all permanent and fixed-term employees of Jarvis Financial Group. "
                "It applies from the first day of employment and supersedes all previous "
                "editions of the Handbook.",
                "Where this Handbook conflicts with an individual contract of employment, "
                "the contract prevails. Where it conflicts with applicable law or regulation, "
                "the law prevails. Nothing in this Handbook creates a contractual entitlement "
                "beyond those expressly stated.",
            ],
        ),
        Section(
            number="2",
            heading="Employment Basics",
            paragraphs=[
                "Standard working hours are 37.5 hours per week, ordinarily worked between "
                "08:30 and 17:00 Monday to Friday with a one-hour unpaid break.",
                "All new employees serve a probationary period of six months, during which "
                "either party may terminate the employment with two weeks' written notice. "
                "Probation may be extended once, by up to three months, where a documented "
                "performance improvement plan is in place.",
                "Following confirmation of employment, the notice period is one month for "
                "staff below manager grade and three months for manager grade and above.",
            ],
        ),
        Section(
            number="3",
            heading="Leave and Time Off",
            paragraphs=[
                "The Group provides several categories of leave. Annual leave entitlement is "
                "governed by the Annual Leave Policy, which is maintained as a separate "
                "controlled document and updated independently of this Handbook.",
                "Employees should consult the current version of the Annual Leave Policy for "
                "the applicable entitlement, as the figure is subject to periodic review.",
            ],
            bullets=[
                "Annual leave — see the current Annual Leave Policy.",
                "Sick leave — 10 paid days per calendar year, certified after three "
                "consecutive days.",
                "Maternity leave — 16 weeks at full pay, available from the first day of "
                "employment.",
                "Paternity and partner leave — 4 weeks at full pay.",
                "Compassionate leave — up to 5 days per event for an immediate family bereavement.",
                "Study leave — up to 6 days per year for approved professional qualifications.",
                "Unpaid leave — at the discretion of the Regional Director, normally capped "
                "at three months.",
            ],
        ),
        Section(
            number="4",
            heading="Pay and Benefits",
            paragraphs=[
                "Salaries are paid monthly, on the 25th day of the month or the preceding "
                "business day where the 25th falls on a weekend or public holiday.",
                "The Group operates a defined contribution pension scheme. The Group "
                "contributes 8 per cent of base salary where the employee contributes at "
                "least 4 per cent. Employees are enrolled automatically after three months "
                "of service and may opt out in writing.",
                "Staff are eligible for a discretionary annual performance bonus determined "
                "by a combination of individual performance rating and Group results. Bonus "
                "payments are not guaranteed and are not pensionable.",
            ],
            table=Table(
                caption="Table 4.1 — Core benefits summary",
                columns=["Benefit", "Eligibility", "Group contribution"],
                rows=[
                    ["Pension scheme", "After 3 months", "8% of base salary"],
                    ["Private medical cover", "On confirmation", "100% employee, 50% family"],
                    ["Life assurance", "From day one", "4x base salary"],
                    ["Staff mortgage discount", "After 2 years", "0.75% below standard rate"],
                    [
                        "Season ticket loan",
                        "On confirmation",
                        "Interest free, repaid over 12 months",
                    ],
                ],
            ),
        ),
        Section(
            number="5",
            heading="Remote and Hybrid Working",
            paragraphs=[
                "Employees in eligible roles may work remotely for up to two days per week "
                "under a hybrid working arrangement, subject to manager approval and "
                "operational requirements.",
                "Customer-facing branch roles, cash handling roles, and roles requiring "
                "access to restricted physical records are not eligible for remote working.",
                "Remote work must be performed from a location within the country of "
                "employment. Working from another jurisdiction requires prior written "
                "approval from both Human Resources and the Group Tax function, as it may "
                "create tax and regulatory obligations for the Group.",
            ],
        ),
        Section(
            number="6",
            heading="Workplace Conduct and Dignity at Work",
            paragraphs=[
                "The Group does not tolerate harassment, bullying, discrimination, or "
                "victimisation of any kind. Such conduct is treated as a disciplinary matter "
                "and may constitute gross misconduct.",
                "Employees who experience or witness such conduct are encouraged to raise it "
                "with a line manager, with Human Resources, or through the confidential "
                "Speak Up line described in the Code of Conduct.",
            ],
        ),
        Section(
            number="7",
            heading="Information Security Obligations",
            paragraphs=[
                "Customer data may be accessed only where there is a legitimate business need. "
                "Browsing customer records without a business reason is a disciplinary offence, "
                "including where no data is disclosed onward.",
                "Group devices must be locked when unattended, must not be used to store "
                "customer data locally, and must have full disk encryption enabled.",
                "Suspected data breaches must be reported to the Information Security team "
                "within one hour of discovery, regardless of the time of day.",
            ],
        ),
    ],
)

# --------------------------------------------------------------------------
# 3. HR Policy — procedures that complement the Handbook
# --------------------------------------------------------------------------

HR_POLICY = Document(
    filename="HR_Policy.pdf",
    title="Human Resources Policy and Procedures",
    subtitle="Recruitment, Performance, Leave Administration, and Grievance",
    doc_type="HR Policy",
    version="5.2",
    effective_date="2026-01-01",
    sections=[
        Section(
            number="1",
            heading="Recruitment and Selection",
            paragraphs=[
                "All vacancies must be advertised internally for a minimum of five working "
                "days before external advertising begins, except where a role is filled "
                "through an approved succession plan.",
                "Every interview panel must include at least two interviewers, at least one "
                "of whom is independent of the hiring team. Panels must record written "
                "scores against the published selection criteria.",
                "Pre-employment screening is mandatory and includes identity verification, "
                "right-to-work confirmation, references covering the previous three years, "
                "a criminal records check, and a credit check for roles with payment "
                "authority.",
            ],
        ),
        Section(
            number="2",
            heading="Performance Management",
            paragraphs=[
                "The performance year runs from 1 January to 31 December. Objectives must be "
                "agreed within the first six weeks of the performance year and recorded in "
                "the People Portal.",
                "Formal reviews take place twice per year: a mid-year review in July and a "
                "year-end review in January. Managers are expected to hold documented "
                "one-to-one meetings at least monthly between formal reviews.",
            ],
            table=Table(
                caption="Table 2.1 — Performance rating scale",
                columns=["Rating", "Definition", "Bonus multiplier"],
                rows=[
                    ["1 — Outstanding", "Consistently exceeded all objectives", "1.50x"],
                    ["2 — Strong", "Exceeded most objectives", "1.20x"],
                    ["3 — Effective", "Met objectives", "1.00x"],
                    ["4 — Developing", "Partially met objectives", "0.50x"],
                    ["5 — Unsatisfactory", "Did not meet objectives", "0.00x"],
                ],
            ),
        ),
        Section(
            number="3",
            heading="Leave Application Procedure",
            paragraphs=[
                "All annual leave must be requested through the People Portal. Requests must "
                "be submitted at least 14 calendar days before the first day of intended "
                "leave. Requests of more than ten consecutive working days require 30 "
                "calendar days' notice.",
                "Line managers must approve or decline a leave request within three business "
                "days of submission. Where a manager does not respond within three business "
                "days, the request escalates automatically to the next approver in the "
                "reporting line.",
                "Leave may be declined only for documented operational reasons, and a "
                "declined request must be accompanied by a written explanation and an offer "
                "of alternative dates.",
                "A maximum of five unused annual leave days may be carried into the following "
                "calendar year and must be taken before 31 March. Days not taken by that date "
                "are forfeited without payment.",
            ],
        ),
        Section(
            number="4",
            heading="Sickness Absence Administration",
            paragraphs=[
                "Employees must notify their line manager of an unplanned absence no later "
                "than one hour after their normal start time, by telephone rather than by "
                "message where practicable.",
                "Absences of more than three consecutive calendar days require a medical "
                "certificate. A return-to-work discussion is held after every absence of "
                "five days or more.",
            ],
        ),
        Section(
            number="5",
            heading="Grievance Procedure",
            paragraphs=[
                "An employee who wishes to raise a formal grievance should submit it in "
                "writing to Human Resources, setting out the substance of the complaint and "
                "the outcome sought.",
                "A grievance hearing is convened within ten business days of receipt. The "
                "employee may be accompanied by a colleague or a trade union representative.",
                "A written outcome is issued within five business days of the hearing. An "
                "appeal must be lodged within ten business days of the outcome and is heard "
                "by a manager senior to the original decision maker.",
            ],
        ),
        Section(
            number="6",
            heading="Disciplinary Procedure",
            paragraphs=[
                "The disciplinary procedure follows a staged approach: informal discussion, "
                "first written warning, final written warning, and dismissal. Warnings remain "
                "live for twelve months.",
                "Conduct that may constitute gross misconduct, including fraud, theft, "
                "unauthorised access to customer records, and breach of anti-money laundering "
                "obligations, may result in dismissal without prior warning.",
            ],
        ),
    ],
)

# --------------------------------------------------------------------------
# 4. Annual Leave Policy — the superseded/active pair
# --------------------------------------------------------------------------
# These two documents are the sharpest test in the corpus. Both are indexed;
# only v2 is active. A retriever that ignores doc_status will happily cite
# "12 days" from the archived v1 with a perfectly valid-looking citation.

_LEAVE_COMMON_TAIL = [
    Section(
        number="4",
        heading="Public Holidays",
        paragraphs=[
            "Public holidays are granted in addition to annual leave entitlement. Where an "
            "employee is required to work a public holiday, a day in lieu is granted and "
            "must be taken within three months."
        ],
    ),
    Section(
        number="5",
        heading="Leave During Notice Periods",
        paragraphs=[
            "Accrued but untaken annual leave is paid on termination of employment, "
            "calculated pro rata to the leaving date. The Group may require an employee to "
            "take outstanding leave during a notice period."
        ],
    ),
]

LEAVE_POLICY_V1 = Document(
    filename="Leave_Policy_v1.pdf",
    title="Annual Leave Policy",
    subtitle="Version 1.0 — SUPERSEDED",
    doc_type="HR Policy",
    version="1.0",
    effective_date="2025-01-01",
    doc_status="archived",
    sections=[
        Section(
            number="1",
            heading="Status of This Document",
            paragraphs=[
                "This version of the Annual Leave Policy was effective from 1 January 2025 "
                "and was superseded on 1 January 2026. It is retained for reference only and "
                "must not be relied upon for current entitlements."
            ],
        ),
        Section(
            number="2",
            heading="Annual Leave Entitlement",
            paragraphs=[
                "Full-time employees are entitled to 12 days of paid annual leave per "
                "calendar year, accruing at one day per calendar month of service.",
                "Part-time employees receive a pro rata entitlement calculated on contracted "
                "hours.",
            ],
        ),
        Section(
            number="3",
            heading="Long Service Additional Days",
            paragraphs=[
                "Employees with five or more years of continuous service receive one "
                "additional day of annual leave, to a maximum of two additional days."
            ],
        ),
        *_LEAVE_COMMON_TAIL,
    ],
)

LEAVE_POLICY_V2 = Document(
    filename="Leave_Policy_v2.pdf",
    title="Annual Leave Policy",
    subtitle="Version 2.0 — CURRENT",
    doc_type="HR Policy",
    version="2.0",
    effective_date="2026-01-01",
    doc_status="active",
    sections=[
        Section(
            number="1",
            heading="Status of This Document",
            paragraphs=[
                "This version of the Annual Leave Policy is effective from 1 January 2026 "
                "and supersedes version 1.0 in its entirety. It is the current and "
                "authoritative statement of annual leave entitlement."
            ],
        ),
        Section(
            number="2",
            heading="Annual Leave Entitlement",
            paragraphs=[
                "Full-time employees are entitled to 15 days of paid annual leave per "
                "calendar year, accruing at one and a quarter days per calendar month of "
                "service.",
                "Part-time employees receive a pro rata entitlement calculated on contracted "
                "hours.",
                "The increase from the previous entitlement applies from 1 January 2026 and "
                "is not applied retrospectively to leave years already completed.",
            ],
        ),
        Section(
            number="3",
            heading="Long Service Additional Days",
            paragraphs=[
                "Employees with five or more years of continuous service receive one "
                "additional day of annual leave per complete five-year period, to a maximum "
                "of three additional days."
            ],
        ),
        *_LEAVE_COMMON_TAIL,
    ],
)

# --------------------------------------------------------------------------
# 5. Products and Services — carries the fee schedule table
# --------------------------------------------------------------------------

PRODUCTS_AND_SERVICES = Document(
    filename="Products_and_Services.pdf",
    title="Products and Services Guide",
    subtitle="Retail and Commercial Banking Products",
    doc_type="Product",
    version="12.3",
    effective_date="2026-01-01",
    sections=[
        Section(
            number="1",
            heading="Personal Current Accounts",
            paragraphs=[
                "The Everyday Current Account has no monthly maintenance fee and requires no "
                "minimum balance. It includes a debit card, online and mobile banking, and "
                "unlimited domestic transfers.",
                "The Premier Current Account carries a monthly fee of 12.00 and includes "
                "travel insurance, a dedicated relationship line, and fee-free international "
                "transfers up to five per month.",
            ],
        ),
        Section(
            number="2",
            heading="Savings Accounts",
            paragraphs=[
                "The Group offers instant-access, notice, and fixed-term savings products. "
                "Rates are variable except on fixed-term deposits and are published daily on "
                "the Group website.",
            ],
            table=Table(
                caption="Table 2.1 — Savings products",
                columns=["Product", "Minimum deposit", "Access", "Indicative rate"],
                rows=[
                    ["Everyday Saver", "1.00", "Instant", "2.10%"],
                    ["90-Day Notice Saver", "500.00", "90 days' notice", "3.25%"],
                    ["1-Year Fixed Deposit", "1,000.00", "On maturity", "4.00%"],
                    ["3-Year Fixed Deposit", "1,000.00", "On maturity", "4.35%"],
                    ["Junior Saver", "1.00", "Instant", "3.50%"],
                ],
            ),
        ),
        Section(
            number="3",
            heading="Lending Products",
            paragraphs=[
                "Personal loans are available from 1,000 to 50,000 over terms of one to "
                "seven years. Residential mortgages are available up to 90 per cent "
                "loan-to-value for first-time buyers and 85 per cent otherwise.",
                "Commercial lending is provided through the Corporate Banking Division and "
                "includes term loans, invoice finance, asset finance, and committed "
                "overdraft facilities.",
            ],
        ),
        Section(
            number="4",
            heading="Schedule of Fees and Charges",
            paragraphs=[
                "The following fees apply to retail accounts unless a product-specific tariff "
                "states otherwise. All fees are debited on the day the service is provided "
                "and are shown on the account statement.",
            ],
            table=Table(
                caption="Table 4.1 — Schedule of fees and charges",
                columns=["Service", "Fee", "Notes"],
                rows=[
                    ["Domestic wire transfer", "15.00", "Per transfer, same day"],
                    [
                        "International wire transfer",
                        "35.00",
                        "Per transfer, plus correspondent charges",
                    ],
                    ["Standing order setup", "0.00", "No charge"],
                    ["Returned direct debit", "10.00", "Per item, capped at 3 per month"],
                    ["Replacement debit card", "7.50", "Waived if card is faulty"],
                    ["Duplicate statement", "5.00", "Per statement period"],
                    ["Certified balance letter", "20.00", "Issued within 2 business days"],
                    [
                        "Early fixed-deposit withdrawal",
                        "90 days' interest",
                        "Deducted from accrued interest",
                    ],
                ],
            ),
        ),
        Section(
            number="5",
            heading="Digital Banking",
            paragraphs=[
                "Online and mobile banking are available to all account holders at no "
                "additional charge. Mobile banking supports biometric sign-in, card freezing, "
                "and payee management.",
                "The daily limit for payments to a new payee set up through mobile banking is "
                "5,000, raised to 25,000 following identity re-verification through the "
                "branch network or the relationship line.",
            ],
        ),
    ],
)

# --------------------------------------------------------------------------
# 6. AML / KYC Compliance Policy
# --------------------------------------------------------------------------

AML_POLICY = Document(
    filename="AML_KYC_Compliance_Policy.pdf",
    title="Anti-Money Laundering and Know Your Customer Policy",
    subtitle="Financial Crime Prevention Framework",
    doc_type="Compliance",
    version="9.1",
    effective_date="2026-01-01",
    sections=[
        Section(
            number="1",
            heading="Policy Statement and Scope",
            paragraphs=[
                "Jarvis Financial Group has zero tolerance for money laundering, terrorist "
                "financing, and sanctions evasion. This Policy applies to all staff, "
                "contractors, and introducers acting on behalf of the Group.",
                "Breach of this Policy is a disciplinary matter that may constitute gross "
                "misconduct, and may also constitute a personal criminal offence for the "
                "individual concerned.",
            ],
        ),
        Section(
            number="2",
            heading="Customer Due Diligence",
            paragraphs=[
                "Customer due diligence must be completed before an account is opened and "
                "before any transaction is processed. No account may be funded while due "
                "diligence remains outstanding.",
                "Standard due diligence requires verification of identity, verification of "
                "residential address, and establishment of the purpose of the relationship "
                "and the expected source of funds.",
            ],
            bullets=[
                "Identity — a current passport, national identity card, or photocard driving "
                "licence.",
                "Address — a utility bill, bank statement, or tax notice dated within the "
                "last three months.",
                "Source of funds — evidence proportionate to the amount and the stated purpose.",
                "Beneficial ownership — identification of any individual holding 25 per cent "
                "or more of a corporate customer.",
            ],
        ),
        Section(
            number="3",
            heading="Enhanced Due Diligence",
            paragraphs=[
                "Enhanced due diligence is mandatory for politically exposed persons, "
                "customers resident in high-risk jurisdictions, correspondent banking "
                "relationships, and any relationship assessed as high risk by the Financial "
                "Crime team.",
                "Enhanced due diligence requires senior management approval before the "
                "relationship is established, documented evidence of source of wealth in "
                "addition to source of funds, and review at least annually.",
            ],
        ),
        Section(
            number="4",
            heading="Transaction Monitoring and Reporting Thresholds",
            paragraphs=[
                "All cash transactions of 10,000 or more, whether in a single transaction or "
                "in linked transactions within a 24-hour period, must be reported to the "
                "Financial Crime team on the day the transaction occurs.",
                "Automated monitoring applies additional scrutiny to cash deposits of 5,000 "
                "or more, to transfers to or from high-risk jurisdictions, and to any pattern "
                "of transactions that appears designed to remain below a reporting threshold.",
                "Structuring — the deliberate splitting of a transaction to avoid a reporting "
                "threshold — must be reported irrespective of the individual amounts "
                "involved.",
            ],
            table=Table(
                caption="Table 4.1 — Reporting thresholds and timescales",
                columns=["Trigger", "Threshold", "Report to", "Deadline"],
                rows=[
                    ["Cash transaction", "10,000", "Financial Crime team", "Same day"],
                    [
                        "Linked cash transactions (24h)",
                        "10,000",
                        "Financial Crime team",
                        "Same day",
                    ],
                    ["Cash deposit review", "5,000", "Automated monitoring", "Next business day"],
                    ["Suspicious activity", "No threshold", "Nominated Officer", "Immediately"],
                    [
                        "Sanctions match",
                        "No threshold",
                        "Nominated Officer",
                        "Immediately, freeze funds",
                    ],
                ],
            ),
        ),
        Section(
            number="5",
            heading="Suspicious Activity Reporting",
            paragraphs=[
                "Any member of staff who knows or suspects that a customer is engaged in "
                "money laundering must submit an internal suspicious activity report to the "
                "Nominated Officer immediately. There is no minimum value threshold for a "
                "suspicion report.",
                "Staff must not disclose to the customer, or to any other person, that a "
                "report has been made or that an investigation is underway. Doing so is the "
                "offence of tipping off.",
            ],
        ),
        Section(
            number="6",
            heading="Record Keeping and Training",
            paragraphs=[
                "Customer due diligence records and transaction records must be retained for "
                "a minimum of five years from the end of the customer relationship or the "
                "date of the transaction, whichever is later.",
                "All staff must complete financial crime training within 30 days of joining "
                "and annually thereafter. Completion is a condition of continued system "
                "access.",
            ],
        ),
    ],
)

# --------------------------------------------------------------------------
# 7. Code of Conduct
# --------------------------------------------------------------------------

CODE_OF_CONDUCT = Document(
    filename="Code_of_Conduct.pdf",
    title="Code of Conduct",
    subtitle="Ethical Standards for All Staff",
    doc_type="Governance",
    version="6.0",
    effective_date="2026-01-01",
    sections=[
        Section(
            number="1",
            heading="Our Standards",
            paragraphs=[
                "The Code of Conduct translates the Group's core values into expected "
                "behaviour. It applies to every employee, contractor, and director without "
                "exception, and seniority does not reduce its application.",
            ],
        ),
        Section(
            number="2",
            heading="Gifts and Hospitality",
            paragraphs=[
                "Staff must not accept any gift or hospitality that could reasonably be seen "
                "to influence a business decision. Cash or cash-equivalent gifts must never "
                "be accepted, in any amount.",
                "Gifts or hospitality with a value above 100 must be declined, or where "
                "declining would cause offence, declared in the Gifts and Hospitality "
                "Register within five business days and surrendered to Human Resources.",
                "Gifts or hospitality valued at 100 or below may be accepted without "
                "declaration, provided acceptance is infrequent and proportionate.",
            ],
        ),
        Section(
            number="3",
            heading="Conflicts of Interest",
            paragraphs=[
                "Staff must declare any outside business interest, directorship, or close "
                "personal relationship that could conflict with their duties to the Group.",
                "Staff must not approve, process, or influence any transaction involving "
                "themselves, a family member, or a close personal associate. Such "
                "transactions must be escalated to a manager for independent handling.",
            ],
        ),
        Section(
            number="4",
            heading="Confidentiality and Personal Account Dealing",
            paragraphs=[
                "Customer information must never be discussed outside the Group, including "
                "with family members, and must not be discussed in public spaces where it "
                "may be overheard.",
                "Staff in designated roles must obtain pre-clearance before dealing in "
                "securities and must hold any such investment for a minimum of 30 days.",
            ],
        ),
        Section(
            number="5",
            heading="Speak Up",
            paragraphs=[
                "The Group operates a confidential Speak Up line, available 24 hours a day "
                "and operated by an independent third party, for reporting suspected "
                "wrongdoing.",
                "Reports may be made anonymously. The Group prohibits retaliation against "
                "anyone who raises a concern in good faith, and retaliation is itself treated "
                "as gross misconduct.",
            ],
        ),
    ],
)

# --------------------------------------------------------------------------
# 8. Customer FAQ — short-form retrieval
# --------------------------------------------------------------------------

CUSTOMER_FAQ = Document(
    filename="Customer_FAQ.pdf",
    title="Customer Frequently Asked Questions",
    subtitle="Common Questions About Banking With Us",
    doc_type="FAQ",
    version="3.4",
    effective_date="2026-01-01",
    sections=[
        Section(
            number="1",
            heading="Opening an Account",
            paragraphs=[
                "You can open a personal current account online, in any branch, or through "
                "the mobile app. Online applications are usually decided within one business "
                "day, and you will need photographic identification and proof of address.",
                "The minimum age to open a personal current account in your own name is 16. "
                "A Junior Saver account may be opened from birth by a parent or guardian.",
            ],
        ),
        Section(
            number="2",
            heading="Cards and Payments",
            paragraphs=[
                "A replacement debit card arrives within five business days. You can freeze "
                "and unfreeze your card instantly in the mobile app, which is faster than "
                "reporting it lost and is reversible.",
                "If you do not recognise a payment on your statement, report it through the "
                "app or by calling the number on the back of your card. Disputed card "
                "payments are investigated within 15 business days.",
            ],
        ),
        Section(
            number="3",
            heading="Branch and Support Hours",
            paragraphs=[
                "Branches are open 09:00 to 17:00 Monday to Friday and 09:00 to 13:00 on "
                "Saturday. Branches are closed on Sunday and on public holidays.",
                "Telephone banking is available 08:00 to 20:00 Monday to Saturday. The lost "
                "and stolen card line operates 24 hours a day, every day.",
            ],
        ),
        Section(
            number="4",
            heading="Complaints",
            paragraphs=[
                "Complaints may be made in branch, by telephone, or in writing. The Group "
                "acknowledges a complaint within three business days and issues a final "
                "response within eight weeks.",
                "If you remain dissatisfied with the final response, you may refer the "
                "complaint to the independent Financial Ombudsman at no cost to you.",
            ],
        ),
    ],
)

TEXT_DOCUMENTS = [
    COMPANY_PROFILE,
    EMPLOYEE_HANDBOOK,
    HR_POLICY,
    LEAVE_POLICY_V2,
    LEAVE_POLICY_V1,
    PRODUCTS_AND_SERVICES,
    AML_POLICY,
    CODE_OF_CONDUCT,
    CUSTOMER_FAQ,
]

# A deliberately image-only PDF. Ingestion must fail loudly rather than index
# zero-length chunks, which is the silent-failure mode this file exists to catch.
SCANNED_DOCUMENT_FILENAME = "Scanned_Notice.pdf"
SCANNED_NOTICE_LINES = [
    "JARVIS FINANCIAL GROUP",
    "NOTICE TO CUSTOMERS",
    "",
    "Branch opening hours will change",
    "from 1 March 2026.",
    "",
    "Please speak to a member of staff",
    "for further details.",
]

# --------------------------------------------------------------------------
# Known facts -> the golden set
# --------------------------------------------------------------------------
# `anchor` is matched against whitespace-normalised page text, so it may span a
# line break in the rendered PDF.

FACTS = [
    Fact(
        id="founded_year",
        question="When was the company founded?",
        answer="1985",
        anchor="was founded in 1985 by Eleanor M. Jarvis",
        document="Company_Profile.pdf",
        category="history",
    ),
    Fact(
        id="founder",
        question="Who founded Jarvis Financial Group?",
        answer="Eleanor M. Jarvis",
        anchor="founded in 1985 by Eleanor M. Jarvis",
        document="Company_Profile.pdf",
        category="history",
    ),
    Fact(
        id="vision",
        question="What is the company's vision?",
        answer="To be the most trusted regional financial institution in the markets it serves",
        anchor="most trusted regional financial institution",
        document="Company_Profile.pdf",
    ),
    Fact(
        id="mission",
        question="What is the company's mission?",
        answer="To help customers build durable financial security",
        anchor="help customers build durable financial security",
        document="Company_Profile.pdf",
    ),
    Fact(
        id="core_values",
        question="What are the company's core values?",
        answer="Integrity, Stewardship, Clarity, Accountability, and Inclusion",
        anchor="Stewardship — We treat customer deposits as a responsibility",
        document="Company_Profile.pdf",
    ),
    Fact(
        id="ceo",
        question="Who is the chief executive officer?",
        answer="Adaeze Okonkwo",
        anchor="Chief Executive Officer Adaeze Okonkwo",
        document="Company_Profile.pdf",
    ),
    Fact(
        id="branch_count",
        question="How many branches does the company operate?",
        answer="48",
        anchor="operates 48 branches",
        document="Company_Profile.pdf",
    ),
    Fact(
        id="employee_count",
        question="How many people does the company employ?",
        answer="2,400",
        anchor="employs 2,400 staff",
        document="Company_Profile.pdf",
    ),
    Fact(
        id="renamed_year",
        question="When did the company change its name to Jarvis Financial Group?",
        answer="1998, after acquiring Meridian Trust",
        anchor="renamed Jarvis Financial Group in 1998",
        document="Company_Profile.pdf",
        category="history",
    ),
    # ---- The version trap ----
    Fact(
        id="annual_leave_days",
        question="How many annual leave days do employees get?",
        answer="15 days",
        anchor="entitled to 15 days of paid annual leave",
        document="Leave_Policy_v2.pdf",
        category="version_trap",
        notes=(
            "Leave_Policy_v1.pdf is archived and says 12 days. Answering 12, or citing v1, "
            "is a failure even though the citation would look valid."
        ),
    ),
    Fact(
        id="leave_accrual",
        question="At what rate does annual leave accrue?",
        answer="One and a quarter days per calendar month",
        anchor="accruing at one and a quarter days per calendar month",
        document="Leave_Policy_v2.pdf",
        category="version_trap",
    ),
    Fact(
        id="long_service_leave",
        question="Do long-serving employees get extra annual leave days?",
        answer="Yes, one additional day per five-year period up to a maximum of three",
        anchor="to a maximum of three additional days",
        document="Leave_Policy_v2.pdf",
        category="version_trap",
    ),
    # ---- Handbook ----
    Fact(
        id="sick_leave",
        question="How many paid sick days are employees entitled to?",
        answer="10 paid days per calendar year",
        anchor="10 paid days per calendar year",
        document="Employee_Handbook.pdf",
    ),
    Fact(
        id="maternity_leave",
        question="Does the company provide maternity leave?",
        answer="Yes, 16 weeks at full pay from the first day of employment",
        anchor="16 weeks at full pay",
        document="Employee_Handbook.pdf",
    ),
    Fact(
        id="probation_period",
        question="How long is the probationary period?",
        answer="Six months",
        anchor="probationary period of six months",
        document="Employee_Handbook.pdf",
    ),
    Fact(
        id="working_hours",
        question="What are the standard working hours?",
        answer="37.5 hours per week",
        anchor="37.5 hours per week",
        document="Employee_Handbook.pdf",
    ),
    Fact(
        id="pension_contribution",
        question="How much does the company contribute to the pension scheme?",
        answer="8 per cent of base salary where the employee contributes at least 4 per cent",
        anchor="contributes 8 per cent of base salary",
        document="Employee_Handbook.pdf",
    ),
    Fact(
        id="remote_days",
        question="How many days per week can employees work remotely?",
        answer="Up to two days per week",
        anchor="work remotely for up to two days per week",
        document="Employee_Handbook.pdf",
    ),
    Fact(
        id="breach_reporting",
        question="How quickly must a suspected data breach be reported?",
        answer="Within one hour of discovery",
        anchor="within one hour of discovery",
        document="Employee_Handbook.pdf",
    ),
    # ---- HR procedure (answers often need the handbook AND the HR policy) ----
    Fact(
        id="leave_notice",
        question="How much notice is required when requesting annual leave?",
        answer="At least 14 calendar days, or 30 days for more than ten consecutive days",
        anchor="at least 14 calendar days before the first day",
        document="HR_Policy.pdf",
        category="multi_chunk",
    ),
    Fact(
        id="leave_approval_time",
        question="How long does a manager have to approve a leave request?",
        answer="Three business days, after which it escalates automatically",
        anchor="within three business days of submission",
        document="HR_Policy.pdf",
        category="multi_chunk",
    ),
    Fact(
        id="leave_carryover",
        question="Can unused annual leave be carried over to the next year?",
        answer="Yes, up to five days, and they must be taken before 31 March",
        anchor="maximum of five unused annual leave days may be carried",
        document="HR_Policy.pdf",
    ),
    Fact(
        id="grievance_hearing",
        question="How soon is a grievance hearing held after a complaint is submitted?",
        answer="Within ten business days of receipt",
        anchor="convened within ten business days of receipt",
        document="HR_Policy.pdf",
    ),
    Fact(
        id="sickness_notification",
        question="When must an employee report an unplanned absence?",
        answer="No later than one hour after their normal start time",
        anchor="no later than one hour after their normal start time",
        document="HR_Policy.pdf",
    ),
    # ---- AML / compliance ----
    Fact(
        id="cash_reporting_threshold",
        question="What is the reporting threshold for cash transactions?",
        answer="10,000, reported the same day",
        anchor="cash transactions of 10,000 or more",
        document="AML_KYC_Compliance_Policy.pdf",
        category="policy",
    ),
    Fact(
        id="beneficial_ownership",
        question="At what ownership level must a beneficial owner be identified?",
        answer="25 per cent or more",
        anchor="holding 25 per cent or more of a corporate customer",
        document="AML_KYC_Compliance_Policy.pdf",
        category="policy",
    ),
    Fact(
        id="record_retention",
        question="How long must customer due diligence records be retained?",
        answer="A minimum of five years",
        anchor="minimum of five years from the end of the customer relationship",
        document="AML_KYC_Compliance_Policy.pdf",
        category="policy",
    ),
    Fact(
        id="sar_threshold",
        question="Is there a minimum value for reporting suspicious activity?",
        answer="No, there is no minimum value threshold",
        anchor="no minimum value threshold for a suspicion report",
        document="AML_KYC_Compliance_Policy.pdf",
        category="policy",
    ),
    Fact(
        id="aml_training",
        question="How often must staff complete financial crime training?",
        answer="Within 30 days of joining and annually thereafter",
        anchor="within 30 days of joining and annually thereafter",
        document="AML_KYC_Compliance_Policy.pdf",
    ),
    # ---- Tables ----
    Fact(
        id="wire_fee_domestic",
        question="What is the fee for a domestic wire transfer?",
        answer="15.00",
        anchor="Domestic wire transfer 15.00",
        document="Products_and_Services.pdf",
        category="table",
    ),
    Fact(
        id="wire_fee_international",
        question="How much does an international wire transfer cost?",
        answer="35.00 plus correspondent charges",
        anchor="International wire transfer 35.00",
        document="Products_and_Services.pdf",
        category="table",
    ),
    Fact(
        id="replacement_card_fee",
        question="Is there a charge for a replacement debit card?",
        answer="7.50, waived if the card is faulty",
        anchor="Replacement debit card 7.50",
        document="Products_and_Services.pdf",
        category="table",
    ),
    Fact(
        id="new_payee_limit",
        question="What is the daily payment limit for a new payee set up in the mobile app?",
        answer="5,000, raised to 25,000 after identity re-verification",
        anchor="new payee set up through mobile banking is 5,000",
        document="Products_and_Services.pdf",
    ),
    Fact(
        id="mortgage_ltv",
        question="What is the maximum loan-to-value for a first-time buyer mortgage?",
        answer="90 per cent",
        anchor="90 per cent loan-to-value for first-time buyers",
        document="Products_and_Services.pdf",
    ),
    # ---- Conduct ----
    Fact(
        id="gift_threshold",
        question="What is the limit for accepting a gift from a client?",
        answer="100; above that it must be declined or declared within five business days",
        anchor="value above 100 must be declined",
        document="Code_of_Conduct.pdf",
        category="policy",
    ),
    Fact(
        id="cash_gifts",
        question="Can staff accept cash gifts?",
        answer="No, never, in any amount",
        anchor="Cash or cash-equivalent gifts must never be accepted",
        document="Code_of_Conduct.pdf",
    ),
    Fact(
        id="speak_up",
        question="How can an employee report suspected wrongdoing confidentially?",
        answer="Through the confidential Speak Up line, anonymously if preferred",
        anchor="confidential Speak Up line, available 24 hours",
        document="Code_of_Conduct.pdf",
    ),
    # ---- FAQ ----
    Fact(
        id="branch_hours",
        question="What are the branch opening hours?",
        answer="09:00 to 17:00 Monday to Friday and 09:00 to 13:00 on Saturday",
        anchor="open 09:00 to 17:00 Monday to Friday",
        document="Customer_FAQ.pdf",
    ),
    Fact(
        id="min_account_age",
        question="What is the minimum age to open a current account?",
        answer="16",
        anchor="minimum age to open a personal current account in your own name is 16",
        document="Customer_FAQ.pdf",
    ),
    Fact(
        id="complaint_response",
        question="How long does the company take to respond to a complaint?",
        answer="Acknowledged within three business days, final response within eight weeks",
        anchor="final response within eight weeks",
        document="Customer_FAQ.pdf",
    ),
    Fact(
        id="disputed_payment",
        question="How long does a disputed card payment investigation take?",
        answer="Within 15 business days",
        anchor="investigated within 15 business days",
        document="Customer_FAQ.pdf",
    ),
]

# --------------------------------------------------------------------------
# Deliberately absent -> refusal must be measurable, not anecdotal
# --------------------------------------------------------------------------

UNANSWERABLE = [
    Unanswerable(
        id="ceo_home_address",
        question="What is the CEO's home address?",
        reason="Never stated, and a model that invents it is dangerous rather than merely wrong.",
    ),
    Unanswerable(
        id="crypto_policy",
        question="What is the company's policy on cryptocurrency trading?",
        reason="No crypto policy exists in the corpus.",
    ),
    Unanswerable(
        id="pet_insurance",
        question="Does the company offer pet insurance as a staff benefit?",
        reason=(
            "Benefits table is explicit and does not include it; plausible enough to tempt a guess."
        ),
    ),
    Unanswerable(
        id="dividend_amount",
        question="What dividend did the company pay last year?",
        reason="No financial statements in the corpus.",
    ),
    Unanswerable(
        id="sabbatical",
        question="How long a sabbatical can an employee take after ten years of service?",
        reason="Leave categories are enumerated and sabbaticals are not among them.",
    ),
    Unanswerable(
        id="branch_count_2030",
        question="How many branches will the company have in 2030?",
        reason="Requires forecasting, not retrieval.",
    ),
    Unanswerable(
        id="competitor_rates",
        question="How do our savings rates compare to Northgate Mutual?",
        reason="No competitor data; tests whether the model reaches for general knowledge.",
    ),
    Unanswerable(
        id="staff_discount_car",
        question="Do employees get a discount on car loans?",
        reason=(
            "A staff mortgage discount exists, so this invites over-generalising from an "
            "adjacent benefit."
        ),
    ),
]

# --------------------------------------------------------------------------
# Multi-turn cases -> only pass if query contextualisation works
# --------------------------------------------------------------------------

FOLLOWUPS = [
    Followup(
        id="leave_days_followup",
        turns=["What is the company's annual leave policy?", "How many days?"],
        answer_contains=["15"],
        document="Leave_Policy_v2.pdf",
    ),
    Followup(
        id="wire_fee_followup",
        turns=["Tell me about wire transfers.", "What does the international one cost?"],
        answer_contains=["35"],
        document="Products_and_Services.pdf",
    ),
    Followup(
        id="aml_threshold_followup",
        turns=[
            "What are the cash transaction reporting rules?",
            "And what is the threshold?",
        ],
        answer_contains=["10,000"],
        document="AML_KYC_Compliance_Policy.pdf",
    ),
    Followup(
        id="probation_followup",
        turns=["Is there a probationary period for new staff?", "How long is it?"],
        answer_contains=["six months", "6 months"],
        document="Employee_Handbook.pdf",
    ),
    Followup(
        id="maternity_followup",
        turns=["Does the company offer maternity leave?", "For how long?"],
        answer_contains=["16 weeks"],
        document="Employee_Handbook.pdf",
    ),
]

# --------------------------------------------------------------------------
# Distractors
# --------------------------------------------------------------------------
# Imported last so the registries above stay readable. Distractors exist to make
# retrieval genuinely hard -- see scripts/corpus_distractors.py for why.

from scripts.corpus_distractors import (  # noqa: E402
    DISTRACTOR_DOCUMENTS,
    DISTRACTOR_FACTS,
)

TEXT_DOCUMENTS = TEXT_DOCUMENTS + DISTRACTOR_DOCUMENTS
FACTS = FACTS + DISTRACTOR_FACTS

# Questions whose answer exists, but only in one of two near-identical places.
# Answering from the wrong document is the failure these catch.
DISAMBIGUATION = [
    Fact(
        id="disambiguate_leave_employee",
        question="How many days of annual leave does a full-time employee receive?",
        answer="15 days",
        anchor="entitled to 15 days of paid annual leave",
        document="Leave_Policy_v2.pdf",
        category="near_miss",
        notes="Contractor_and_Supplier_Policy.pdf mentions 20 days for agency workers.",
    ),
    Fact(
        id="disambiguate_cash_threshold",
        question="At what cash amount must a transaction be reported to the Financial Crime team?",
        answer="10,000",
        anchor="cash transactions of 10,000 or more",
        document="AML_KYC_Compliance_Policy.pdf",
        category="near_miss",
        notes="Branch_Operations_Manual.pdf has 5,000 / 8,000 / 25,000 operational limits.",
    ),
    Fact(
        id="disambiguate_breach_time",
        question="How quickly must a suspected customer data breach be reported?",
        answer="Within one hour of discovery",
        anchor="within one hour of discovery",
        document="Employee_Handbook.pdf",
        category="near_miss",
        notes="IT_Acceptable_Use_Policy.pdf has a 24-hour rule for lost devices.",
    ),
    Fact(
        id="disambiguate_gift_staff",
        question="What gift value must a member of staff decline from a client?",
        answer="Above 100",
        anchor="value above 100 must be declined",
        document="Code_of_Conduct.pdf",
        category="near_miss",
        notes="Contractor policy has a 50 supplier-hospitality limit.",
    ),
]

FACTS = FACTS + DISAMBIGUATION

UNANSWERABLE = UNANSWERABLE + [
    Unanswerable(
        id="contractor_pension",
        question="What pension contribution do contractors receive?",
        reason="Contractors are explicitly excluded from the pension scheme; no figure exists.",
    ),
    Unanswerable(
        id="atm_cash_limit",
        question="What is the maximum cash an ATM can hold?",
        reason="Branch cash limits are documented but ATM capacity is not.",
    ),
    Unanswerable(
        id="password_rotation",
        question="How often must passwords be changed?",
        reason=(
            "Length, reuse, and lockout rules are specified but no rotation period is, "
            "which invites filling the gap from general IT convention."
        ),
    ),
]
