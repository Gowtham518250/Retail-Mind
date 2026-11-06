"""Deterministic retrieval and routing for Retail Mind Help & Support chat.

This module intentionally has no LLM, network, database, or embedding dependency.
Application help is retrieved from a curated local knowledge base using lexical
ranking. Business-data intents are normalized for dispatch to safe SQL handlers
owned by query_retrival.py.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


_SUPPORT_ARTICLES: tuple[dict[str, Any], ...] = (
    {
        "id": "create_bill",
        "title": "Create a sales bill",
        "aliases": (
            "create a bill", "create bill", "bill create", "how do i create bill",
            "make a bill", "make bill", "generate a bill", "create invoice",
            "make invoice", "billing process", "how to bill", "bill preparation", "new sale",
            "add sale", "sales entry", "record a sale",
        ),
        "keywords": ("sales", "bill", "invoice", "customer", "payment", "quantity", "products"),
        "answer_en": (
            "To create a bill in Retail Mind:\n"
            "1. Open Sales or Add Sale from your shop dashboard.\n"
            "2. Select or add the customer, if needed.\n"
            "3. Add products and enter their quantities.\n"
            "4. Review the items and total, then choose the payment method.\n"
            "5. Save the sale. Open Invoices to view or share the saved bill."
        ),
        "answer_te": (
            "Retail Mind‌లో బిల్ చేయడానికి:\n"
            "1. డాష్‌బోర్డ్‌లో Sales లేదా Add Sale తెరవండి.\n"
            "2. అవసరమైతే కస్టమర్‌ను ఎంచుకోండి లేదా కొత్త కస్టమర్‌ను జోడించండి.\n"
            "3. ఉత్పత్తులను ఎంచుకుని పరిమాణాలు నమోదు చేయండి.\n"
            "4. వస్తువులు, మొత్తం మరియు చెల్లింపు విధానాన్ని తనిఖీ చేయండి.\n"
            "5. సేల్‌ను సేవ్ చేయండి. సేవ్ చేసిన బిల్‌ను Invoices‌లో చూడవచ్చు."
        ),
    },
    {
        "id": "voice_billing",
        "title": "Use voice billing",
        "aliases": (
            "voice billing", "bill using voice", "create bill by voice",
            "speak to create bill", "voice sale", "speech billing",
        ),
        "keywords": ("voice", "microphone", "speech", "billing", "bill", "product", "quantity"),
        "answer_en": (
            "To use Voice Billing, open the voice-billing option from the sales workflow, "
            "allow microphone access when Android asks, and speak the product names and quantities. "
            "Review every recognized product, quantity and price before confirming the bill. "
            "Correct or remove an uncertain item instead of confirming a guess."
        ),
        "answer_te": (
            "Voice Billing ఉపయోగించడానికి Sales‌లో వాయిస్ బిల్లింగ్ ఎంపికను తెరిచి, మైక్రోఫోన్ అనుమతి ఇవ్వండి. "
            "ఉత్పత్తుల పేర్లు మరియు పరిమాణాలను స్పష్టంగా చెప్పండి. బిల్‌ను నిర్ధారించే ముందు గుర్తించిన ప్రతి "
            "ఉత్పత్తి, పరిమాణం మరియు ధరను తనిఖీ చేయండి. సందేహాస్పదమైన వస్తువును సరిచేయండి."
        ),
    },
    {
        "id": "add_product",
        "title": "Add a product to inventory",
        "aliases": (
            "add a product", "create a product", "new product",
            "add item to inventory", "how to add stock item", "product entry",
        ),
        "keywords": ("product", "inventory", "item", "sku", "price", "stock"),
        "answer_en": (
            "To add a product, open Inventory and choose Add Product. Enter the product name "
            "and the details requested by the form, such as SKU, selling price and opening stock. "
            "Save the product and check that it appears in your inventory list."
        ),
        "answer_te": (
            "ఉత్పత్తిని జోడించడానికి Inventory తెరిచి Add Product ఎంచుకోండి. ఫారమ్‌లో అడిగిన ఉత్పత్తి పేరు, "
            "SKU, అమ్మకపు ధర మరియు ప్రారంభ స్టాక్ వివరాలను నమోదు చేసి సేవ్ చేయండి. తర్వాత ఇన్వెంటరీ జాబితాలో "
            "ఉత్పత్తి కనిపిస్తుందో చూడండి."
        ),
    },
    {
        "id": "password_recovery",
        "title": "Reset or recover a password",
        "aliases": (
            "reset my password", "forgot password", "change my password",
            "password reset", "recover account password", "cannot login password",
        ),
        "keywords": ("password", "reset", "forgot", "login", "account", "otp"),
        "answer_en": (
            "On the sign-in screen, choose Forgot Password and follow the verification steps "
            "sent to your registered contact method. Never share your password or verification OTP."
        ),
        "answer_te": (
            "సైన్-ఇన్ స్క్రీన్‌లో Forgot Password ఎంచుకుని, మీ రిజిస్టర్డ్ కాంటాక్ట్‌కు వచ్చే ధృవీకరణ దశలను "
            "అనుసరించండి. మీ పాస్‌వర్డ్ లేదా OTP ఎవరితోనూ పంచుకోవద్దు."
        ),
    },
    {
        "id": "add_customer",
        "title": "Add a customer",
        "aliases": (
            "add a customer", "create customer", "new customer",
            "customer registration", "save customer details",
        ),
        "keywords": ("customer", "customers", "buyer", "contact", "phone", "add"),
        "answer_en": (
            "Open Customers, choose Add Customer, enter the details requested by the form, "
            "and save. You can then select that customer when recording a sale."
        ),
        "answer_te": (
            "Customers తెరిచి Add Customer ఎంచుకోండి. ఫారమ్‌లో అడిగిన కస్టమర్ వివరాలను నమోదు చేసి సేవ్ చేయండి. "
            "తర్వాత సేల్ నమోదు చేసేటప్పుడు ఆ కస్టమర్‌ను ఎంచుకోవచ్చు."
        ),
    },
    {
        "id": "attendance",
        "title": "Record worker attendance",
        "aliases": (
            "worker attendance", "mark attendance", "staff attendance",
            "employee attendance", "attendance process", "check in worker",
        ),
        "keywords": ("worker", "staff", "employee", "attendance", "checkin", "shift"),
        "answer_en": (
            "Open Attendance from the dashboard, select the worker, and use the attendance "
            "or check-in action available on that screen. Review the saved entry in Attendance. "
            "If the device is offline, confirm that the pending change syncs when connectivity returns."
        ),
        "answer_te": (
            "డాష్‌బోర్డ్‌లో Attendance తెరిచి వర్కర్‌ను ఎంచుకోండి. ఆ స్క్రీన్‌లో ఉన్న attendance లేదా check-in "
            "చర్యను ఉపయోగించండి. సేవ్ అయిన ఎంట్రీని తనిఖీ చేయండి. ఫోన్ ఆఫ్‌లైన్‌లో ఉంటే, ఇంటర్నెట్ వచ్చిన తర్వాత "
            "పెండింగ్ మార్పు సింక్ అయిందో నిర్ధారించండి."
        ),
    },
    {
        "id": "online_store",
        "title": "Set up the online store",
        "aliases": (
            "online store", "enable online shopping", "online orders",
            "share shop link", "customer online shopping", "shop website",
        ),
        "keywords": ("online", "store", "shop", "shopping", "orders", "link", "products"),
        "answer_en": (
            "Open Online Store from the owner dashboard and follow the store setup shown there. "
            "Review the store settings and the products you want available online before sharing "
            "the shop link with customers."
        ),
        "answer_te": (
            "Owner డాష్‌బోర్డ్‌లో Online Store తెరిచి అక్కడ చూపించే సెటప్ దశలను అనుసరించండి. "
            "కస్టమర్లతో షాప్ లింక్ పంచుకునే ముందు స్టోర్ సెట్టింగ్‌లు మరియు ఆన్‌లైన్‌లో చూపించాల్సిన ఉత్పత్తులను తనిఖీ చేయండి."
        ),
    },
    {
        "id": "payment_announcements",
        "title": "Payment announcements",
        "aliases": (
            "payment announcements", "announce payments", "payment voice alert",
            "speak incoming payment", "upi notification announcement",
        ),
        "keywords": ("payment", "announcement", "voice", "upi", "notification", "alert"),
        "answer_en": (
            "Open the Payment Announcements or payment-detection settings in Retail Mind and "
            "review the permissions shown there. Android may require notification access and "
            "background-operation permissions. Verify a detected payment against your bank or "
            "UPI app; a notification alone is not proof that a payment settled."
        ),
        "answer_te": (
            "Retail Mind‌లో Payment Announcements లేదా payment-detection సెట్టింగ్‌లు తెరిచి, చూపించే "
            "అనుమతులను తనిఖీ చేయండి. Android‌లో notification access మరియు background permissions అవసరమవచ్చు. "
            "నోటిఫికేషన్ మాత్రమే చెల్లింపు పూర్తయిందనే నిర్ధారణ కాదు; బ్యాంక్ లేదా UPI యాప్‌లో ధృవీకరించండి."
        ),
    },
    {
        "id": "ai_queries",
        "title": "Ask questions about shop data",
        "aliases": (
            "ai query", "ask query", "ask about my shop", "business questions",
            "how to ask sales question", "shop data assistant",
        ),
        "keywords": ("ask", "query", "assistant", "sales", "inventory", "business", "question"),
        "answer_en": (
            "Open Help & Support or the AI Query assistant and ask a specific question about "
            "your shop, for example “Show my sales today” or “Which products are low in stock?”. "
            "Questions about exact figures are answered from your shop's saved records."
        ),
        "answer_te": (
            "Help & Support లేదా AI Query assistant తెరిచి మీ షాప్ గురించి స్పష్టమైన ప్రశ్న అడగండి. "
            "ఉదాహరణకు “Show my sales today” లేదా “Which products are low in stock?”. ఖచ్చితమైన సంఖ్యల కోసం "
            "మీ షాప్‌లో సేవ్ చేసిన రికార్డులనే ఉపయోగిస్తాము."
        ),
    },
)


_STOP_WORDS = {
    "a", "an", "the", "i", "my", "me", "our", "we", "you", "your", "is", "are",
    "was", "were", "do", "does", "did", "can", "could", "would", "please", "how",
    "what", "which", "where", "when", "to", "in", "on", "for", "of", "and", "about",
    "నా", "మీ", "మా", "లో", "కి", "కు", "ఎలా", "ఏమి", "ఏంటి", "చెప్పండి",
}


# Deterministic vocabulary normalization for common Telugu and Roman-Telugu
# retail questions. This is deliberately conservative; unknown wording is not guessed.
_TRANSLATIONS = (
    ("బిల్ ఎలా తయారు చేయాలి", "create bill"), ("బిల్ ఎలా చేయాలి", "create bill"),
    ("అమ్మిన ఉత్పత్తులు", "products sold"), ("పెండింగ్ ఆర్డర్లు", "pending orders"),
    ("బిల్", "bill"), ("బిల్లులు", "bills"), ("తయారు చేయాలి", "create"),
    ("వాయిస్ బిల్లింగ్", "voice billing"), ("వాయిస్", "voice"),
    ("ఉత్పత్తులు", "products"), ("ఉత్పత్తి", "product"),
    ("జోడించాలి", "add"), ("కస్టమర్ వివరాలు", "customer details"),
    ("ఈ రోజు", "today"), ("ఈరోజు", "today"), ("ఇవాళ", "today"),
    ("నిన్న", "yesterday"), ("ఈ నెల", "this month"), ("ఈనెల", "this month"),
    ("గత నెల", "last month"), ("గతవారం", "last week"), ("ఈ వారం", "this week"),
    ("అమ్మకాలు", "sales"), ("విక్రయాలు", "sales"), ("సేల్స్", "sales"),
    ("అమ్మిన", "sold"), ("అమ్మారు", "sold"), ("అమ్మిన ఉత్పత్తులు", "products sold"),
    ("తక్కువ స్టాక్", "low stock"), ("స్టాక్ తక్కువ", "low stock"),
    ("తక్కువ నిల్వ", "low stock"), ("స్టాక్", "stock"), ("నిల్వ", "stock"),
    ("లాభం", "profit"), ("లాభాలు", "profits"), ("ఖర్చులు", "expenses"),
    ("వ్యయాలు", "expenses"), ("బాకీ", "outstanding"), ("బకాయి", "outstanding"),
    ("ఉదారు", "udhar"), ("ఖాతా", "khata"), ("కస్టమర్లు", "customers"),
    ("కస్టమర్", "customer"), ("ఎంత", "how much"), ("మొత్తం", "total"),
    ("ఏ ఉత్పత్తులు", "which products"), ("ఏ వస్తువులు", "which items"),
    ("ఎన్ని", "how many"), ("పెండింగ్ ఆర్డర్లు", "pending orders"),
    ("ఆర్డర్లు", "orders"),
    ("sell", "sales"), ("ivala", "today"), ("eeroju", "today"), ("ee roju", "today"),
    ("ninna", "yesterday"), ("ee nela", "this month"), ("gata nela", "last month"),
    ("ammakalu", "sales"), ("ammakalu", "sales"), ("vikrayalu", "sales"),
    ("takkuva stock", "low stock"), ("stock takkuva", "low stock"),
    ("labham", "profit"), ("labhalu", "profits"), ("karchulu", "expenses"),
    ("baaki", "outstanding"), ("baki", "outstanding"), ("udhar", "udhar"),
    ("khata", "khata"), ("customers ki baaki", "customer outstanding"),
)


def normalize_support_query(value: str) -> str:
    """Normalize punctuation, common Telugu terms, and Roman-Telugu aliases."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    text = re.sub(r"[’']", "'", text)
    for source, target in _TRANSLATIONS:
        text = text.replace(source.casefold(), target)
    text = re.sub(r"[^\w\s₹.-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_simple_greeting(value: str) -> bool:
    # Check native Telugu greetings before applying the shared phrase
    # normalizer, which may rewrite language fragments as aliases.
    raw_question = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    greeting_pattern = (
        r"(?:hi|hello|hey|good morning|good afternoon|good evening|namaste|namaskaram|"
        r"హాయ్|హలో|నమస్కారం|namaskaram andi)(?: there)?"
    )
    if not raw_question:
        return False
    if re.fullmatch(greeting_pattern, raw_question):
        return True
    question = normalize_support_query(value)
    return bool(question and re.fullmatch(greeting_pattern, question))


def greeting_answer(language_code: str = "en") -> str:
    if str(language_code or "en").lower().startswith("te"):
        return "నమస్కారం! Retail Mind‌లో మీకు ఏ సహాయం కావాలి? మీ షాప్ డేటా లేదా యాప్ ఫీచర్ల గురించి అడగండి."
    return "Hello! I'm your Retail Mind assistant. You can ask about your shop's sales, inventory, customers, invoices, or how to use an app feature."


def classify_shop_data_intent(value: str) -> tuple[str | None, str]:
    """Return (intent, normalized English query) for supported deterministic data paths."""
    query = normalize_support_query(value)
    q = f" {query} "

    # Do not let a single-metric fast path silently answer only part of a
    # compound question. Ambiguous multi-metric requests must be clarified.
    domains = {
        "sales": bool(re.search(r"\b(sales?|revenue|turnover|sold)\b", q)),
        "expenses": bool(re.search(r"\b(expenses?|spending|spent)\b", q)),
        "profit": bool(re.search(r"\b(net profit|profit|profits|profit and loss|p&l)\b", q)),
        "stock": bool(re.search(r"\b(low stock|stock|inventory|reorder)\b", q)),
        "receivables": bool(re.search(r"\b(outstanding|owe|owes|owed|receivable|receivables|khata|udhar)\b", q)),
        "overpayments": bool(re.search(r"\b(overpayment|overpayments|overpaid|paid too much|extra payments)\b", q)),
    }
    if sum(domains.values()) > 1:
        return None

    if re.search(r"\b(low stock|low in stock|stock low|running low|reorder|below minimum)\b", q):
        return "low_stock", query
    if re.search(r"\b(overpayment|overpayments|overpaid|paid too much|extra payments)\b", q):
        return "overpayment", query
    if re.search(r"\b(net profit|profit|profits|profit and loss|p&l)\b", q):
        return "profit", query
    if re.search(r"\b(outstanding|owe|owes|owed|receivable|receivables|khata|udhar)\b", q):
        return "receivables", query
    if (
        re.search(r"\b(products?|items?)\b", q)
        and re.search(r"\b(highest|most|maximum|greatest|top|best|largest)\b", q)
        and re.search(r"\b(revenue|sales|earnings|income|turnover|amount)\b", q)
    ):
        return "top_product_revenue", query
    # The product-list shortcut returns items sold and quantities; it must not
    # reinterpret a requested sales-by-product/category breakdown as that list.
    if re.search(r"\b(sales|revenue|turnover)\s+by\b|\bby\s+(products?|items?|categories?|customers?|workers?)\b", q):
        return None
    if (
        re.search(r"\b(products?|items?)\b", q)
        and re.search(r"\b(sold|sales)\b", q)
        and re.search(r"\b(which|what|list|show|display|name)\b", q)
    ):
        return "sold_products", query
    if re.search(r"\b(expenses?|spending|spent)\b", q):
        return "expenses", query
    if re.search(r"\b(sales?|revenue|turnover)\b", q):
        if re.search(r"\b(by|per|each|every|breakdown|compare|comparison|trend|group|category|customer|customers|product|products|worker|workers)\b", q):
            return None
        if re.search(r"\b(how many|count|number of)\b", q) and re.search(r"\bsales?\b", q):
            return "sales_count", query
        if re.search(r"\b(units?|items?)\b", q) and re.search(r"\b(sold|sales?)\b", q):
            return "units_sold", query
        if re.search(r"\b(how much|total|amount|revenue|turnover|sales)\b", q):
            return "sales_amount", query
    return None, query


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[\w]+", normalize_support_query(value), flags=re.UNICODE)
        if len(token) > 1 and token not in _STOP_WORDS
    }


def retrieve_support_article(value: str, language_code: str = "en") -> dict[str, Any] | None:
    """Lexically rank verified help articles; return None when evidence is weak."""
    query = normalize_support_query(value)
    if not query:
        return None
    query_tokens = _tokens(query)
    if not query_tokens:
        return None

    ranked: list[tuple[float, dict[str, Any]]] = []
    for article in _SUPPORT_ARTICLES:
        score = 0.0
        matched_aliases = []
        for alias in article["aliases"]:
            normalized_alias = normalize_support_query(alias)
            if normalized_alias and normalized_alias in query:
                score += 8.0 + min(len(normalized_alias.split()), 4) * 0.4
                matched_aliases.append(alias)
        article_tokens = _tokens(" ".join(article["keywords"]) + " " + " ".join(article["aliases"]))
        overlap = query_tokens & article_tokens
        score += len(overlap) * 1.25
        # Require either a direct alias or at least two meaningful terms.
        if matched_aliases or len(overlap) >= 2:
            ranked.append((score, article))

    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    best_score, article = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    if best_score < 2.5 or (best_score < 8.0 and best_score - second_score < 1.0):
        return None

    is_telugu = str(language_code or "en").lower().startswith("te")
    return {
        "id": article["id"],
        "title": article["title"],
        "score": round(best_score, 3),
        "answer": article["answer_te"] if is_telugu else article["answer_en"],
        "retrieval": "lexical_support_rag",
    }


def clarification_answer(language_code: str = "en") -> str:
    if str(language_code or "en").lower().startswith("te"):
        return (
            "మీ ప్రశ్నను సరైన సహాయ అంశంతో సరిపోల్చలేకపోయాను. "
            "బిల్ తయారీ, ఉత్పత్తులు, కస్టమర్లు, పాస్‌వర్డ్ రీసెట్, వాయిస్ బిల్లింగ్, "
            "స్టాక్ లేదా అమ్మకాల గురించి కొంచెం వివరంగా అడగండి."
        )
    return (
        "I couldn't confidently match that question to verified Retail Mind help or a supported shop-data query. "
        "Please add a little detail—for example, creating a bill, adding a product, voice billing, "
        "sales today, low stock, profit, or customer outstanding balances."
    )
