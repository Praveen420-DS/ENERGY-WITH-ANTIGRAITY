import re

EMAIL_REGEX = r"[^@]+@[^@]+\.[^@]+"

def validate_email(email: str) -> bool:
    return re.match(EMAIL_REGEX, email) is not None
