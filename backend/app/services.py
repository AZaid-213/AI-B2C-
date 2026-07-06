import csv
import io
from typing import Dict, Any, List

import phonenumbers

from .models import Contact


def parse_contacts_csv(content: bytes) -> List[Dict[str, Any]]:
    """
    Parse a CSV file into a list of dicts.
    Handles:
    - BOM (utf-8-sig)
    - Any column name casing / extra spaces (normalised to lowercase)
    - Column aliases: mobile/telephone/tel/contact → phone
                      full_name/fullname/customer   → name
                      location/area/region          → city
    """
    # Try UTF-8 with BOM first, fall back to latin-1
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))

    # Aliases for flexible column names
    PHONE_ALIASES = {"phone", "mobile", "telephone", "tel", "contact", "number", "phone_number", "whatsapp"}
    NAME_ALIASES  = {"name", "full_name", "fullname", "customer", "customer_name", "contact_name"}
    CITY_ALIASES  = {"city", "location", "area", "region", "district", "town"}

    normalized_rows = []
    for raw_row in reader:
        row: Dict[str, str] = {}
        for raw_key, value in raw_row.items():
            if raw_key is None:
                continue
            key = raw_key.strip().lower().replace(" ", "_")
            val = (value or "").strip()

            if key in PHONE_ALIASES:
                row["phone"] = val
            elif key in NAME_ALIASES:
                row["name"] = val
            elif key in CITY_ALIASES:
                row["city"] = val
            else:
                row[key] = val   # keep unknown columns too

        normalized_rows.append(row)

    return normalized_rows


def normalize_phone(phone: str) -> str:
    """
    Normalise a phone number to E.164 digits (no +).
    Supports:
    - Numbers with country code:  +923001234567 → 923001234567
    - Pakistani 0-prefix:         03001234567  → 923001234567
    - Plain international digits: 923001234567 → 923001234567
    - Other countries:            +447911123456 → 447911123456
    Returns empty string for unparseable/invalid numbers.
    """
    raw = (phone or "").strip()
    if not raw:
        return ""

    # Remove common formatting characters
    cleaned = raw.replace("(", "").replace(")", "").replace("-", "").replace(" ", "").replace(".", "")

    # Try parsing with country code first (handles + prefix and full international)
    for region in (None, "PK", "IN", "AE", "US", "GB", "SA"):
        try:
            parsed = phonenumbers.parse(cleaned, region)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.E164
                ).lstrip("+")
        except phonenumbers.NumberParseException:
            continue

    # Last resort: if it looks like all digits and reasonable length, keep as-is
    digits_only = "".join(c for c in cleaned if c.isdigit())
    if 10 <= len(digits_only) <= 15:
        return digits_only

    return ""


def clean_contacts(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    unique_numbers: set = set()
    valid_contacts: List[Contact] = []
    duplicates = 0
    invalid = 0

    for row in rows:
        raw_phone = row.get("phone", "")
        phone = normalize_phone(raw_phone)

        if not phone:
            invalid += 1
            continue

        if phone in unique_numbers:
            duplicates += 1
            continue

        unique_numbers.add(phone)
        valid_contacts.append(Contact(
            id=str(len(valid_contacts) + 1),
            name=row.get("name") or None,
            phone=phone,
            city=row.get("city") or None,
            tags=[],
        ))

    return {
        "total": len(rows),
        "duplicates": duplicates,
        "invalid": invalid,
        "valid": len(valid_contacts),
        "contacts": valid_contacts,
    }
