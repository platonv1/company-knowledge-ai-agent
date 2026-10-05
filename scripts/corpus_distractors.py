"""Distractor documents.

Retrieval difficulty comes from near-miss content, not page count. A corpus of
nine well-separated documents makes any retriever look excellent, because the
nearest wrong chunk is not close to the right one.

Each document here deliberately contains numbers and phrasing that sit close to
a golden-set answer while being about a genuinely different subject:

* contractors have a leave entitlement that is NOT employee annual leave (15)
* branch cash limits sit either side of the AML reporting threshold (10,000)
* IT incident timescales sit near the data-breach timescale (one hour)
* the supplier gift limit sits near the staff gift limit (100)

A retriever that keys on "leave days" or "threshold" alone will now fail, which
is the point: the eval numbers start meaning something.
"""

from scripts.corpus_schema import Document, Fact, Section, Table

# --------------------------------------------------------------------------
# Contractor and Supplier Policy -- near-miss for leave, gifts, and notice
# --------------------------------------------------------------------------

CONTRACTOR_POLICY = Document(
    filename="Contractor_and_Supplier_Policy.pdf",
    title="Contractor and Supplier Policy",
    subtitle="Engagement, Conduct, and Payment Terms for Third Parties",
    doc_type="Procurement",
    version="3.0",
    effective_date="2026-01-01",
    sections=[
        Section(
            number="1",
            heading="Scope and Status of Contractors",
            paragraphs=[
                "This Policy governs the engagement of contractors, consultants, agency "
                "workers, and suppliers. Individuals engaged under this Policy are not "
                "employees of Jarvis Financial Group and do not receive employee benefits.",
                "Contractors are not entitled to Group annual leave, Group sick pay, or "
                "membership of the Group pension scheme. Any paid time off is a matter "
                "between the contractor and the engaging agency.",
                "Where an agency framework applies, standard agency terms provide 20 days of "
                "paid time off per year for agency workers. This figure is an agency term and "
                "has no bearing on employee entitlements.",
            ],
        ),
        Section(
            number="2",
            heading="Engagement Approval and Notice",
            paragraphs=[
                "All contractor engagements require approval from the engaging Department "
                "Head and from Procurement before work begins. Engagements longer than six "
                "months additionally require Executive Committee approval.",
                "Either party may terminate a contractor engagement with seven days' written "
                "notice, unless the statement of work specifies otherwise.",
            ],
        ),
        Section(
            number="3",
            heading="Supplier Gifts and Entertainment",
            paragraphs=[
                "Suppliers and prospective suppliers must not offer gifts or entertainment to "
                "Group staff during an active tender process, in any amount.",
                "Outside a tender process, supplier-funded hospitality valued above 50 must "
                "be pre-approved by Procurement. This supplier limit is separate from, and "
                "lower than, the general staff gift limit set out in the Code of Conduct.",
            ],
        ),
        Section(
            number="4",
            heading="Payment Terms",
            paragraphs=[
                "Standard payment terms are 30 days from receipt of a valid invoice. Small "
                "and medium suppliers may apply for 14-day terms under the Group's prompt "
                "payment commitment.",
            ],
            table=Table(
                caption="Table 4.1 — Supplier payment and administration charges",
                columns=["Item", "Amount", "Notes"],
                rows=[
                    ["Standard payment terms", "30 days", "From receipt of valid invoice"],
                    ["Prompt payment terms", "14 days", "On application, SME suppliers"],
                    [
                        "Invoice re-issue administration",
                        "25.00",
                        "Where invoice details are incorrect",
                    ],
                    ["Late purchase order amendment", "40.00", "Within 5 days of delivery"],
                    ["Framework onboarding", "0.00", "No charge"],
                ],
            ),
        ),
        Section(
            number="5",
            heading="Due Diligence on Suppliers",
            paragraphs=[
                "Suppliers must complete financial crime and modern slavery due diligence "
                "before onboarding. Suppliers with an annual contract value above 100,000 are "
                "subject to enhanced review and an annual reassessment.",
                "Supplier due diligence records are retained for six years after the end of "
                "the contract, which is a longer period than the customer due diligence "
                "retention requirement.",
            ],
        ),
    ],
)

# --------------------------------------------------------------------------
# Branch Operations Manual -- near-miss for AML thresholds
# --------------------------------------------------------------------------

BRANCH_OPERATIONS = Document(
    filename="Branch_Operations_Manual.pdf",
    title="Branch Operations Manual",
    subtitle="Cash Handling, Authorisation Limits, and Daily Controls",
    doc_type="Operations",
    version="11.2",
    effective_date="2026-01-01",
    sections=[
        Section(
            number="1",
            heading="Opening and Closing Procedures",
            paragraphs=[
                "Branches must be opened by two authorised members of staff. The vault may "
                "not be accessed by a single individual under any circumstances.",
                "End-of-day balancing must be completed and signed by the Branch Manager or "
                "a nominated deputy before the branch is secured.",
            ],
        ),
        Section(
            number="2",
            heading="Teller Cash Limits",
            paragraphs=[
                "A teller drawer must not hold more than 5,000 in cash at any time. Amounts "
                "above the drawer limit must be transferred to the vault and recorded in the "
                "cash movement log.",
                "These limits are operational controls for the safety of staff and cash. They "
                "are not reporting thresholds, and they do not replace any obligation under "
                "the Anti-Money Laundering and Know Your Customer Policy.",
            ],
            table=Table(
                caption="Table 2.1 — Cash and authorisation limits",
                columns=["Control", "Limit", "Authorisation required"],
                rows=[
                    ["Teller drawer holding", "5,000", "None"],
                    ["Single counter withdrawal", "8,000", "Teller"],
                    ["Counter withdrawal, dual control", "25,000", "Teller plus supervisor"],
                    ["Vault transfer", "50,000", "Branch Manager"],
                    ["Overnight branch cash holding", "75,000", "Regional Director"],
                ],
            ),
        ),
        Section(
            number="3",
            heading="Large Withdrawal Notice",
            paragraphs=[
                "Customers wishing to withdraw more than 8,000 in cash should give two "
                "business days' notice so the branch can order currency. Notice is an "
                "operational convenience and may not be used to discourage a lawful "
                "withdrawal.",
                "Staff must not advise a customer to split a withdrawal or deposit in order "
                "to stay below any limit. Suggesting such a split is a serious breach and "
                "must itself be reported.",
            ],
        ),
        Section(
            number="4",
            heading="Cash Differences",
            paragraphs=[
                "Any cash difference above 50 must be reported to the Branch Manager on the "
                "day it is identified. Differences above 500 must additionally be reported to "
                "Regional Operations within one business day.",
                "Repeated differences by the same member of staff, regardless of amount, must "
                "be escalated to Human Resources.",
            ],
        ),
        Section(
            number="5",
            heading="Branch Security Incidents",
            paragraphs=[
                "Robbery, attempted robbery, and threats to staff must be reported to the "
                "police immediately and to Group Security within 15 minutes.",
                "Branches must complete a security drill twice per year, and the drill record "
                "must be retained for three years.",
            ],
        ),
    ],
)

# --------------------------------------------------------------------------
# IT Acceptable Use -- near-miss for incident reporting timescales
# --------------------------------------------------------------------------

IT_ACCEPTABLE_USE = Document(
    filename="IT_Acceptable_Use_Policy.pdf",
    title="IT Acceptable Use Policy",
    subtitle="Devices, Access, and Incident Handling",
    doc_type="Information Security",
    version="8.4",
    effective_date="2026-01-01",
    sections=[
        Section(
            number="1",
            heading="Acceptable Use of Group Systems",
            paragraphs=[
                "Group systems are provided for business purposes. Limited personal use is "
                "permitted provided it does not interfere with work, consume significant "
                "resources, or breach any other Group policy.",
                "Staff must not install unapproved software, connect unapproved storage "
                "devices, or route Group traffic through unapproved network services.",
            ],
        ),
        Section(
            number="2",
            heading="Authentication and Access",
            paragraphs=[
                "Passwords must be at least 14 characters and must not be reused across "
                "systems. Multi-factor authentication is mandatory for all remote access and "
                "for all administrative accounts.",
                "Accounts are locked after five consecutive failed sign-in attempts and are "
                "unlocked only after identity verification by the Service Desk.",
                "Access rights are reviewed quarterly. Access that has not been used for 90 "
                "days is revoked automatically.",
            ],
        ),
        Section(
            number="3",
            heading="Lost and Stolen Devices",
            paragraphs=[
                "A lost or stolen Group device must be reported to the Service Desk within 24 "
                "hours of discovery so the device can be wiped remotely.",
                "Where a lost device is known or suspected to hold customer data, the "
                "shorter data-breach timescale in the Employee Handbook applies instead, and "
                "the Information Security team must be notified immediately.",
            ],
        ),
        Section(
            number="4",
            heading="Incident Severity and Response",
            paragraphs=[
                "IT incidents are classified by severity. Severity determines the response "
                "target, not the reporting obligation: all incidents must be reported as soon "
                "as they are identified.",
            ],
            table=Table(
                caption="Table 4.1 — IT incident severity and response targets",
                columns=["Severity", "Example", "Response target", "Escalation"],
                rows=[
                    [
                        "P1 — Critical",
                        "Core banking unavailable",
                        "15 minutes",
                        "Chief Operating Officer",
                    ],
                    ["P2 — High", "Branch network degraded", "1 hour", "Head of IT Operations"],
                    [
                        "P3 — Medium",
                        "Single user unable to sign in",
                        "4 hours",
                        "Service Desk lead",
                    ],
                    ["P4 — Low", "Software request", "2 business days", "None"],
                ],
            ),
        ),
        Section(
            number="5",
            heading="Email and Phishing",
            paragraphs=[
                "Suspected phishing messages must be reported using the Report Phishing "
                "button rather than deleted, so that related messages can be removed from "
                "other mailboxes.",
                "Staff who report a phishing attempt are never penalised, including where "
                "they interacted with the message before reporting it.",
            ],
        ),
    ],
)

DISTRACTOR_DOCUMENTS = [CONTRACTOR_POLICY, BRANCH_OPERATIONS, IT_ACCEPTABLE_USE]

# Facts that can only be answered correctly by distinguishing a distractor from
# the document that actually governs the question.
DISTRACTOR_FACTS = [
    Fact(
        id="contractor_leave",
        question="Are contractors entitled to the company's annual leave?",
        answer="No; contractors are not entitled to Group annual leave",
        anchor="not entitled to Group annual leave",
        document="Contractor_and_Supplier_Policy.pdf",
        category="near_miss",
        notes="Must not be confused with the employee entitlement of 15 days.",
    ),
    Fact(
        id="supplier_gift_limit",
        question="What is the approval limit for supplier-funded hospitality?",
        answer="Above 50 it must be pre-approved by Procurement",
        anchor="supplier-funded hospitality valued above 50",
        document="Contractor_and_Supplier_Policy.pdf",
        category="near_miss",
        notes="Near-miss for the staff gift limit of 100 in the Code of Conduct.",
    ),
    Fact(
        id="supplier_payment_terms",
        question="What are the standard supplier payment terms?",
        answer="30 days from receipt of a valid invoice",
        anchor="Standard payment terms are 30 days",
        document="Contractor_and_Supplier_Policy.pdf",
    ),
    Fact(
        id="teller_drawer_limit",
        question="How much cash can a teller drawer hold?",
        answer="No more than 5,000",
        anchor="must not hold more than 5,000 in cash",
        document="Branch_Operations_Manual.pdf",
        category="near_miss",
        notes="Near-miss for the AML cash reporting threshold of 10,000.",
    ),
    Fact(
        id="vault_transfer_limit",
        question="What authorisation is needed for a vault transfer?",
        answer="Branch Manager authorisation, for transfers at the 50,000 limit",
        anchor="Vault transfer 50,000 Branch Manager",
        document="Branch_Operations_Manual.pdf",
        category="table",
    ),
    Fact(
        id="large_withdrawal_notice",
        question="How much notice should a customer give for a large cash withdrawal?",
        answer="Two business days for withdrawals over 8,000",
        anchor="more than 8,000 in cash should give two business days",
        document="Branch_Operations_Manual.pdf",
    ),
    Fact(
        id="lost_device_reporting",
        question="How quickly must a lost company device be reported?",
        answer="Within 24 hours of discovery",
        anchor="reported to the Service Desk within 24 hours",
        document="IT_Acceptable_Use_Policy.pdf",
        category="near_miss",
        notes="Near-miss for the one-hour data-breach reporting rule in the Handbook.",
    ),
    Fact(
        id="password_length",
        question="What is the minimum password length?",
        answer="14 characters",
        anchor="at least 14 characters",
        document="IT_Acceptable_Use_Policy.pdf",
    ),
    Fact(
        id="account_lockout",
        question="After how many failed sign-in attempts is an account locked?",
        answer="Five consecutive failed attempts",
        anchor="locked after five consecutive failed sign-in attempts",
        document="IT_Acceptable_Use_Policy.pdf",
    ),
    Fact(
        id="p1_response_target",
        question="What is the response target for a P1 critical IT incident?",
        answer="15 minutes",
        # Anchored on body text, not the table row: a wrapped table cell does not
        # extract in reading order (pdfplumber emits "Core banking" ... "unavailable"
        # either side of the next column), which is exactly why ingestion reads
        # tables with extract_tables() rather than from the page text.
        anchor="Severity determines the response target",
        document="IT_Acceptable_Use_Policy.pdf",
        category="table",
    ),
    Fact(
        id="access_revocation",
        question="When is unused system access revoked?",
        answer="After 90 days without use",
        anchor="not been used for 90 days is revoked automatically",
        document="IT_Acceptable_Use_Policy.pdf",
    ),
]
