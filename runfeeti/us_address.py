from __future__ import annotations

import re

# USPS-style state and DC; sorted by display name in GUI.
_US_STATES: tuple[tuple[str, str], ...] = (
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("DC", "District of Columbia"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
)

# Sorted by state name for the dropdown.
STATE_DISPLAY_CHOICES: tuple[str, ...] = tuple(
    f"{name} ({abbr})" for abbr, name in sorted(_US_STATES, key=lambda x: x[1].casefold())
)

_PLACEHOLDER = "— Select state —"

_ZIP_RE = re.compile(r"^\d{5}(?:-\d{4})?$")


def state_display_values() -> tuple[str, ...]:
    """Combobox values: placeholder plus 'Name (ST)' entries."""
    return (_PLACEHOLDER,) + STATE_DISPLAY_CHOICES


def abbrev_from_display(choice: str) -> str:
    """Parse 'Texas (TX)' -> TX; placeholder raises ValueError."""
    s = choice.strip()
    if not s or s == _PLACEHOLDER:
        raise ValueError("Choose a state.")
    if "(" in s and s.endswith(")"):
        inner = s[s.rfind("(") + 1 : -1].strip()
        if len(inner) == 2 and inner.isalpha():
            return inner.upper()
    raise ValueError("Choose a valid state from the list.")


def normalize_zip(raw: str) -> str:
    """Accept 12345 or 12345-6789; strip spaces."""
    z = raw.strip()
    if not z:
        raise ValueError("Enter a ZIP code.")
    digits = z.replace("-", "").replace(" ", "")
    if not digits.isdigit():
        raise ValueError("ZIP must be digits (optionally 12345-6789).")
    if len(digits) == 5:
        return digits
    if len(digits) == 9:
        combined = f"{digits[:5]}-{digits[5:]}"
        if _ZIP_RE.match(combined):
            return combined
    raise ValueError("ZIP must be 5 digits or 9 digits (ZIP+4).")


def build_geocode_line(street: str, city: str, state_abbr: str, zip_code: str) -> str:
    """Single line for Nominatim / geocode_address."""
    st = street.strip()
    ct = city.strip()
    if not st:
        raise ValueError("Enter a street address (number and street).")
    if not ct:
        raise ValueError("Enter a city.")
    ab = state_abbr.strip().upper()
    if len(ab) != 2:
        raise ValueError("State must be a two-letter code.")
    z = normalize_zip(zip_code)
    return f"{st}, {ct}, {ab} {z}"
