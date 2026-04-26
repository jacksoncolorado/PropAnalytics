from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable, KeepTogether,
    Table, TableStyle,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


OUTPUT = "test_plans.pdf"

NAVY = colors.HexColor("#1f2a44")
ACCENT = colors.HexColor("#3b5b8a")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#cbd5e1")


def build_styles():
    base = getSampleStyleSheet()
    styles = {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=28, leading=34, alignment=TA_CENTER, textColor=NAVY,
            spaceAfter=18,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle", parent=base["Title"], fontName="Helvetica",
            fontSize=18, leading=22, alignment=TA_CENTER, textColor=ACCENT,
            spaceAfter=40,
        ),
        "cover_meta_label": ParagraphStyle(
            "cover_meta_label", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=11, leading=14, textColor=MUTED, alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "cover_meta_value": ParagraphStyle(
            "cover_meta_value", parent=base["Normal"], fontName="Helvetica",
            fontSize=14, leading=18, textColor=NAVY, alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "plan_title": ParagraphStyle(
            "plan_title", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=20, leading=24, textColor=NAVY, spaceAfter=4,
        ),
        "plan_subtitle": ParagraphStyle(
            "plan_subtitle", parent=base["Heading2"], fontName="Helvetica",
            fontSize=12, leading=15, textColor=ACCENT, spaceAfter=14,
        ),
        "field_label": ParagraphStyle(
            "field_label", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=11, leading=14, textColor=NAVY, spaceBefore=10, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Helvetica",
            fontSize=10.5, leading=14, textColor=colors.black, spaceAfter=4,
            alignment=TA_LEFT,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Helvetica",
            fontSize=10.5, leading=14, textColor=colors.black,
            leftIndent=18, bulletIndent=6, spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=9, textColor=MUTED, alignment=TA_CENTER,
        ),
    }
    return styles


def hr(color=RULE, thickness=0.6, space_before=2, space_after=2):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                      spaceBefore=space_before, spaceAfter=space_after)


def cover_page(styles):
    elements = []
    elements.append(Spacer(1, 1.6 * inch))
    elements.append(Paragraph("Optimized Statistical NBA Tool", styles["cover_title"]))
    elements.append(hr(color=ACCENT, thickness=1.4, space_before=0, space_after=18))
    elements.append(Paragraph("Software Test Plans", styles["cover_subtitle"]))
    elements.append(Spacer(1, 0.8 * inch))

    elements.append(Paragraph("DATE", styles["cover_meta_label"]))
    elements.append(Paragraph("April 27, 2026", styles["cover_meta_value"]))

    elements.append(Paragraph("TEAM", styles["cover_meta_label"]))
    elements.append(Paragraph(
        "McGuire &nbsp;/&nbsp; Petrovic &nbsp;/&nbsp; Singh &nbsp;/&nbsp; Moua &nbsp;/&nbsp; Muterspaugh",
        styles["cover_meta_value"],
    ))

    elements.append(Paragraph("DOCUMENT", styles["cover_meta_label"]))
    elements.append(Paragraph("Test Plans 001 – 003", styles["cover_meta_value"]))

    elements.append(Spacer(1, 1.4 * inch))
    elements.append(hr(color=ACCENT, thickness=1.0, space_before=0, space_after=8))
    elements.append(Paragraph(
        "UCCS CS 3300 — Intro to Software Engineering &nbsp;|&nbsp; Spring 2026",
        styles["footer"],
    ))
    elements.append(PageBreak())
    return elements


def field(label, body_paragraphs, styles):
    out = [Paragraph(label, styles["field_label"])]
    for p in body_paragraphs:
        out.append(p)
    return out


def b(text, styles):
    return Paragraph(text, styles["body"])


def bullets(items, styles):
    return [Paragraph(item, styles["bullet"], bulletText="•") for item in items]


def plan_header(num, name, kind, styles):
    elements = []
    elements.append(Paragraph(f"Test Plan {num}", styles["plan_title"]))
    elements.append(Paragraph(f"{name} &nbsp;&middot;&nbsp; {kind}", styles["plan_subtitle"]))
    elements.append(hr(color=ACCENT, thickness=1.0, space_before=0, space_after=10))
    return elements


def plan_001(styles):
    elements = []
    elements.append(Paragraph("Project Title: Optimized Statistical NBA Tool", styles["body"]))
    elements.append(Spacer(1, 0.05 * inch))
    elements.extend(plan_header("001", "Derived Metrics — Hit Rate Function", "Unit Test, Logic", styles))

    elements.extend(field("Test Objectives", [
        b("Verify that the derived metrics function correctly computes the hit rate of a "
          "player's stat line over the last N games, returning accurate values for normal data, "
          "edge cases at the prop line boundary, and degenerate input (zero games played).", styles),
    ], styles))

    elements.extend(field("Test Approach", [
        b("Unit test, logic verification. Three hand-traced test cases will be executed "
          "against the <font face='Courier'>hit_rate()</font> function in "
          "<font face='Courier'>analytics.py</font>:", styles),
        *bullets([
            "<b>Normal case</b> — player with 10 game logs, prop line set to a value cleanly above or "
            "below their average; verify the returned percentage matches the manual calculation.",
            "<b>Boundary case</b> — game stat exactly equal to the prop line; verify the function applies "
            "the strict over/under definition consistently (over = strictly greater than line).",
            "<b>Empty case</b> — player with zero game logs in the database; verify the function returns "
            "a safe value (e.g., zero or null) instead of raising a divide-by-zero or returning a "
            "misleading percentage.",
        ], styles),
    ], styles))

    elements.extend(field("Manual or Automated Test", [
        b("Manual — three scripted logic traces executed against seeded test inputs.", styles),
    ], styles))

    elements.extend(field("Test Tools", [
        b("Python interpreter (REPL), local SQLite database with seeded test rows, "
          "hand-calculated expected results.", styles),
    ], styles))

    elements.extend(field("Test Environment", [
        b("Tester's local development machine running the Flask application against a "
          "controlled SQLite database.", styles),
    ], styles))

    elements.extend(field("Test Criteria", [
        b("Requirement <b>1.2.2 (Derived Metrics)</b> — function must compute hit rate accurately "
          "across normal, boundary, and empty inputs.", styles),
    ], styles))

    elements.extend(field("Test Schedule", [b("April 27, 2026", styles)], styles))

    elements.extend(field("Test Team", [
        *bullets([
            "<b>Tester:</b> Jack Muterspaugh",
            "<b>Developer (excluded from testing):</b> Joey Petrovic — author of derived metrics logic",
        ], styles),
    ], styles))

    return elements


def plan_002(styles):
    elements = []
    elements.append(Paragraph("Project Title: Optimized Statistical NBA Tool", styles["body"]))
    elements.append(Spacer(1, 0.05 * inch))
    elements.extend(plan_header("002", "Backend API ↔ Frontend Prop Screener", "Integration Test, Interface", styles))

    elements.extend(field("Test Objectives", [
        b("Verify that the backend API routes correctly fetch live NBA stats and odds from "
          "external services, parse the responses without data loss or malformation, and pass "
          "the resulting data accurately to the frontend prop screener for display.", styles),
    ], styles))

    elements.extend(field("Test Approach", [
        b("Integration test, interface verification. The tester will:", styles),
        *bullets([
            "Issue requests to the backend API endpoints directly using Postman, inspect the JSON "
            "response structure, and confirm that fields, types, and values match the upstream API contracts.",
            "Trigger error conditions (invalid endpoint parameters, simulated upstream timeout) and "
            "verify the backend returns appropriate error responses rather than crashing.",
            "Load the prop screener page in the browser and use DevTools (Network tab) to confirm the "
            "frontend receives the same data the backend produced and renders it correctly.",
        ], styles),
    ], styles))

    elements.extend(field("Manual or Automated Test", [
        b("Manual — performed through Postman and browser DevTools.", styles),
    ], styles))

    elements.extend(field("Test Tools", [
        b("Postman (API request inspection), Chrome DevTools (Network and Console tabs), the "
          "running Flask development server.", styles),
    ], styles))

    elements.extend(field("Test Environment", [
        b("Tester's local development machine running the full Flask application with valid "
          "Odds API credentials.", styles),
    ], styles))

    elements.extend(field("Test Criteria", [
        *bullets([
            "<b>1.1.1</b> — Backend route for data must be reachable and return valid responses",
            "<b>1.1.2</b> — API error handling must return a non-crashing error response on upstream failure",
            "<b>1.4.1</b> — Connection to The Odds API must succeed and return parseable JSON",
            "<b>1.4.2</b> — Odds data parsing must correctly extract player, market, line, and price "
            "fields without loss",
        ], styles),
    ], styles))

    elements.extend(field("Test Schedule", [b("April 27, 2026", styles)], styles))

    elements.extend(field("Test Team", [
        *bullets([
            "<b>Tester:</b> Gurjot Singh",
            "<b>Developers (excluded from testing):</b> Jack Muterspaugh (backend routes, nba_api), "
            "Jackson McGuire (Odds API integration, screener)",
        ], styles),
    ], styles))

    return elements


def plan_003(styles):
    elements = []
    elements.append(Paragraph("Project Title: Optimized Statistical NBA Tool", styles["body"]))
    elements.append(Spacer(1, 0.05 * inch))
    elements.extend(plan_header("003", "Full User Workflow — Cross-Browser & Cross-Device", "System Test, End-to-End Scenario", styles))

    elements.extend(field("Test Objectives", [
        b("Verify the full end-to-end user workflow operates correctly across browsers and screen "
          "sizes: a user can search for a player, the prop screener loads with stats and live odds, "
          "and the prop detail view shows the player's recent game logs and visual trend charts "
          "without errors or unacceptable latency.", styles),
    ], styles))

    elements.extend(field("Test Approach", [
        b("System test, end-to-end scenario. The tester will execute the following user flow on "
          "each target environment:", styles),
        *bullets([
            "Open the homepage and confirm today's games and the prop screener load within an "
            "acceptable response time.",
            "Use the search bar to look up a known active player and confirm the search resolves to "
            "that player's detail page.",
            "On the player detail page, confirm season averages, recent game logs, and Chart.js trend "
            "charts render correctly against current data.",
            "Navigate to a game detail page, confirm props for both teams render with correct "
            "hit-rate values.",
            "Repeat the entire flow on each target browser and viewport size; record any visual "
            "breakage, broken navigation, missing data, or response-time issues.",
        ], styles),
    ], styles))

    elements.extend(field("Manual or Automated Test", [
        b("Manual — scenario-based exploratory testing performed by a non-frontend-developer team member.", styles),
    ], styles))

    elements.extend(field("Test Tools", [
        b("Chrome (latest stable), Firefox (latest stable), Chrome DevTools device-emulation mode "
          "for mobile viewport testing, stopwatch or DevTools Performance tab for latency observation.", styles),
    ], styles))

    elements.extend(field("Test Environment", [
        b("Production deployment of the Optimized Statistical NBA Tool, accessed over the public "
          "Replit deployment URL. Testing performed on:", styles),
        *bullets([
            "<b>Desktop</b> — Chrome and Firefox at standard 1920×1080 resolution",
            "<b>Mobile</b> — Chrome DevTools mobile emulation (iPhone and Pixel viewports)",
        ], styles),
    ], styles))

    elements.extend(field("Test Criteria", [
        *bullets([
            "<b>1.0.3</b> — User can navigate the application end-to-end without dead links or broken pages",
            "<b>1.0.4</b> — Application surfaces live data on every page that requires it",
            "<b>1.2</b> — Statistical data and derived metrics are present and accurate on user-facing pages",
            "<b>1.4</b> — Live odds data is present and accurate on user-facing pages",
            "<b>2.1 (Speed)</b> — Page load and interaction response times remain within acceptable bounds",
            "<b>2.2 (Cross-browser/device)</b> — Full workflow operates correctly across target browsers "
            "and screen sizes",
        ], styles),
    ], styles))

    elements.extend(field("Test Schedule", [b("April 27, 2026", styles)], styles))

    elements.extend(field("Test Team", [
        *bullets([
            "<b>Tester:</b> Ywjfeej Moua",
            "<b>Developers (excluded from testing):</b> Gurjot Singh (frontend styling and framework), "
            "Jackson McGuire (frontend pages and screener)",
        ], styles),
    ], styles))

    return elements


def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    if doc.page > 1:
        canvas.drawCentredString(
            LETTER[0] / 2.0, 0.4 * inch,
            f"Optimized Statistical NBA Tool — Software Test Plans   |   Page {doc.page}",
        )
    canvas.restoreState()


def main():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=LETTER,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.85 * inch, bottomMargin=0.7 * inch,
        title="Optimized Statistical NBA Tool — Software Test Plans",
        author="McGuire / Petrovic / Singh / Moua / Muterspaugh",
    )
    styles = build_styles()

    story = []
    story.extend(cover_page(styles))
    story.extend(plan_001(styles))
    story.append(PageBreak())
    story.extend(plan_002(styles))
    story.append(PageBreak())
    story.extend(plan_003(styles))

    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
