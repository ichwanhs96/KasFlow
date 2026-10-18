COUNTRY = {
    "ID": {"currency": "IDR", "language": "id", "name": "Indonesia", "locale": "id-ID"},
    "PH": {"currency": "PHP", "language": "fil", "name": "the Philippines", "locale": "en-PH"},
    "VN": {"currency": "VND", "language": "vi", "name": "Vietnam", "locale": "vi-VN"},
}
LANGUAGE_NAME = {"id": "Bahasa Indonesia", "fil": "Filipino", "vi": "Vietnamese", "en": "English"}
CURRENCIES = {c["currency"] for c in COUNTRY.values()}


def currency_for(country: str) -> str:
    return COUNTRY[country]["currency"]


def language_for(country: str) -> str:
    return COUNTRY[country]["language"]


def country_name(country: str) -> str:
    return COUNTRY[country]["name"]
