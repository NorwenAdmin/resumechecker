"""Hardcoded skill-equivalence groups so Claude treats these as the same underlying skill
when doing semantic gap analysis, instead of flagging a real gap for a naming difference."""

EQUIVALENCE_GROUPS: list[list[str]] = [
    ["Charles", "Postman", "Fiddler", "Proxyman"],  # API testing / proxy tools
    ["Espresso", "XCUITest", "Appium"],  # mobile automation
    ["Jenkins", "Bamboo", "GitHub Actions", "GitLab CI", "CircleCI"],  # CI/CD
    ["Kotlin", "Java", "Scala"],  # JVM ecosystem
    ["C#", "Java"],  # OOP strongly typed
    ["Mentored engineers", "Team lead", "Coached", "Mentorship"],  # people leadership
    ["Selenium", "Cypress", "Playwright"],  # web automation
]


def as_prompt_block() -> str:
    lines = [" = ".join(group) for group in EQUIVALENCE_GROUPS]
    return "\n".join(f"- {line}" for line in lines)
