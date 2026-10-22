import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank_layout = prs.slide_layouts[6]

DARK = RGBColor(15, 23, 42)
GREEN = RGBColor(16, 185, 129)
CARD_BG = RGBColor(241, 245, 249)

slides_data = [
    {
        "title": "GreenOps Engine",
        "subtitle": "Autonomous Carbon Arbitrage & Scope 2 ESG Compliance for Cloud Compute",
        "body": "Target Audience: CTOs, VPs of Infrastructure, Heads of FinOps, and CSOs\nStack: FastAPI | MotherDuck Cloud | DuckDB v1.5.6 | Prometheus",
    },
    {
        "title": "The Hidden Dual-Waste of Cloud Data",
        "subtitle": "Cost Volatility, Audit Gaps, and Engineering Barriers",
        "body": "• The Cost Trap: Grid electricity swings up to 300% daily (£0.09 vs £0.31/kWh).\n• The Audit Gap: Annual ESG carbon estimates fail modern SECR and CSRD audits.\n• The SLA Barrier: Data teams reject green tools that risk pipeline delivery deadlines.",
    },
    {
        "title": "Autonomous Workload Arbitrage",
        "subtitle": "Intelligent Gatekeeper Between Orchestrators and Cloud Compute",
        "body": "1. Telemetry Ingestion: UK NESO regional feeds continuously stream to MotherDuck.\n2. Arbitrage Logic: Automatically identifies sub-50 gCO2/kWh clean windows.\n3. Zero Friction: Decorator gate holds workloads or forces execution on SLA timeouts.\n4. Immutable Ledger: MotherDuck persists full financial and emissions audit trails.",
    },
    {
        "title": "Pillar 1: Frictionless Developer Adoption",
        "subtitle": "Integrate in 60 Seconds with Native SLA Fallbacks",
        "body": "• One-Line Decorator: Wrap functions with @client.gate(max_wait_seconds=1800).\n• Airflow Ready: Drop-in GreenOpsAirflowSensor compatible with enterprise DAGs.\n• SLA Guarantee: If green power fails to clear within timeout, execution is forced automatically.",
    },
    {
        "title": "Pillar 2: Proving ROI Every Monday",
        "subtitle": "Verifiable Financial Arbitrage Delivered Automatically",
        "body": "• Direct Cash Savings: Up to £20+ saved per standard 50kW 2-hour batch execution.\n• Monday Morning Digest: Pushes weekly £ and kg CO2 savings to Slack and MS Teams.\n• Prometheus Integration: Native /metrics endpoint exports directly to Grafana / Datadog.",
    },
    {
        "title": "Pillar 3: Audit-Ready ESG Compliance",
        "subtitle": "GHG Protocol Scope 2 Market-Based Accounting",
        "body": "• Certified Reporting: Measured against actual UK grid node intensity vs baseline.\n• Persistent Cloud Storage: gold_dispatch_ledger stores immutable microsecond records.\n• Instant Compliance Export: Dedicated GET /v1/reports/esg endpoint outputs ready-to-audit CSVs.",
    },
    {
        "title": "Commercial Model & 14-Day Pilot Plan",
        "subtitle": "Fast Payback with Zero Infrastructure Risk",
        "body": "• Pilot Evaluation: £3,500 one-time setup on 1–5 staging pipelines.\n• Enterprise Subscriptions: £1,800/mo (Standard) or £4,200/mo (Dedicated Tenant).\n• 14-Day Pilot Offer: Measure actual savings on your data before committing.",
    },
]

for item in slides_data:
    slide = prs.slides.add_slide(blank_layout)

    # Accent Header Bar
    top_bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(0.15))
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = GREEN
    top_bar.line.color.rgb = GREEN

    # Title & Subtitle Box
    tx_box = slide.shapes.add_textbox(Inches(1.0), Inches(0.8), Inches(11.333), Inches(1.8))
    tf = tx_box.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = item["title"]
    p.font.name = "Segoe UI"
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = DARK

    p2 = tf.add_paragraph()
    p2.text = item["subtitle"]
    p2.font.name = "Segoe UI"
    p2.font.size = Pt(18)
    p2.font.color.rgb = GREEN
    p2.space_before = Pt(8)

    # Content Card
    card = slide.shapes.add_shape(1, Inches(1.0), Inches(2.8), Inches(11.333), Inches(3.8))
    card.fill.solid()
    card.fill.fore_color.rgb = CARD_BG
    card.line.color.rgb = CARD_BG

    content_box = slide.shapes.add_textbox(Inches(1.4), Inches(3.1), Inches(10.5), Inches(3.2))
    ctf = content_box.text_frame
    ctf.word_wrap = True

    lines = item["body"].split("\n")
    for i, line in enumerate(lines):
        cp = ctf.paragraphs[0] if i == 0 else ctf.add_paragraph()
        cp.text = line
        cp.font.name = "Segoe UI"
        cp.font.size = Pt(16)
        cp.font.color.rgb = DARK
        cp.space_before = Pt(10)

prs.save("greenops_pitch_deck.pptx")
print("✅ Successfully generated greenops_pitch_deck.pptx")