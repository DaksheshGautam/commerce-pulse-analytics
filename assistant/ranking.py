"""Resolve simple, explicit SKU rankings without unrelated model-selected tools.

Complex comparisons and documentation questions retain Gemini routing. This
parser only supplies catalog filters, a supported period and ranking metric.
"""
import calendar
from datetime import date
import re

from .queries import QuerySpec

MONTHS = {name.casefold(): number for number, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.casefold(): number for number, name in enumerate(calendar.month_abbr) if name})
COUNTS = {'one':1, 'two':2, 'three':3, 'four':4, 'five':5, 'six':6,
          'seven':7, 'eight':8, 'nine':9, 'ten':10}


def product_ranking_requested(question):
    return bool(re.search(r'\btop\b', question, re.I)
        and re.search(r'\b(?:items?|products?|skus?)\b', question, re.I))


def product_ranking_scope(question, catalog, context=None):
    if not product_ranking_requested(question):
        return None
    if re.search(r'\b(?:each|within|compare|versus|vs|profit|margin|forecast|except|exclude|excluding|cancelled|returned|returns|loss|collected|recognized|today|yesterday|last|this)\b', question, re.I):
        return None
    count = re.search(r'\btop\s+(\d+|' + '|'.join(COUNTS) + r')\b', question, re.I)
    if not count:
        return None
    word = count.group(1).casefold()
    limit = int(word) if word.isdigit() else COUNTS[word]
    if not 1 <= limit <= 200:
        raise ValueError('Choose between 1 and 200 ranked SKUs.')
    remaining = question[:count.start()] + question[count.end():]
    remaining = re.sub(r'\b\d{4}-\d{2}-\d{2}\b|\b20\d{2}\b', '', remaining)
    if re.search(r'\d', remaining):
        return None

    selected = {}
    follow_up = bool(re.search(r'\b(?:same|those|instead|previous)\b|^\s*(?:now|only)\b', question, re.I))
    if follow_up and context:
        previous = next((item for item in reversed(context) if item.get('queries')), None)
        if previous:
            queries = previous['queries']
            primary = next((item for item in queries if item.get('analysis') in {'sku_performance', 'sku_rank_within_category'}), queries[0])
            selected = {key:primary.get(key) for key in ('category', 'state', 'fulfillment', 'customer_type', 'start_date', 'end_date', 'rank_by')}
    # "Top" is also a real clothing category. Remove the ranking phrase before
    # matching catalog labels so "top 3" never becomes a category filter.
    filter_text = question[:count.start()] + question[count.end():]
    for key, values in [('state', catalog['states']), ('category', catalog['categories'])]:
        matches = [value for value in values if value and re.search(r'(?<!\w)' + re.escape(value) + r'(?!\w)', filter_text, re.I)]
        if len(matches) > 1:
            return None
        if matches:
            selected[key] = matches[0]
    if re.search(r'\bstate\s+(?:of\s+)?[a-z]', question, re.I) and not selected.get('state'):
        raise ValueError('Please choose a shipping state recorded in this dataset.')
    for match in re.finditer(r'\bin\s+(?:the\s+)?(?:state\s+(?:of\s+)?)?([a-z][a-z ]*?)(?=\s+(?:in|during|for|by|from|between|with|and|20\d{2})\b|[?.!,]|$)', question, re.I):
        place = match.group(1).strip().casefold()
        if place not in MONTHS and not any(place == value.casefold() for values in catalog.values() for value in values if value):
            raise ValueError('Please specify a shipping state or product category recorded in this dataset.')
    if re.search(r'\bmerchant\b', question, re.I):
        selected['fulfillment'] = 'Merchant'
    elif re.search(r'\bamazon\s+fulfil[l]?ment\b|\bfulfilled by amazon\b', question, re.I):
        selected['fulfillment'] = 'Amazon'
    if re.search(r'\bb2b\b|\bbusiness customers?\b', question, re.I):
        selected['customer_type'] = 'Business (B2B)'
    elif re.search(r'\bretail\b', question, re.I):
        selected['customer_type'] = 'Retail'

    dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', question)
    if not dates and re.search(r'\b(?:before|after|until|since|between)\b', question, re.I):
        return None
    months = {number for name, number in MONTHS.items() if re.search(r'\b' + name + r'\b', question, re.I)}
    years = {int(value) for value in re.findall(r'\b20\d{2}\b', question)}
    if dates:
        if len(dates) != 2:
            return None
        selected.update(start_date=dates[0], end_date=dates[1])
    elif months:
        if len(months) != 1 or len(years) > 1:
            return None
        month = next(iter(months))
        year = next(iter(years), 2022)
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
        if year != 2022 or month not in {3, 4, 5, 6}:
            raise ValueError('The available snapshot covers 31 March–29 June 2022.')
        selected.update(start_date=max(start, date(2022, 3, 31)), end_date=min(end, date(2022, 6, 29)))
    elif years:
        return None
    elif re.search(r'\b(?:today|yesterday|last|this)\b', question, re.I):
        return None
    if re.search(r'\b(?:units?|quantity|quantities|volume|pieces)\b', question, re.I):
        selected['rank_by'] = 'units'
    else:
        selected['rank_by'] = 'shipped_value'
    return QuerySpec(analysis='sku_performance', row_limit=limit, **selected)


def simple_product_ranking(question, catalog, context=None):
    if re.search(r'\b(?:explain|why|defined?|definitions?|meaning|methodology|cleaning|duplicates?|schema|columns?|dataset|documentation|policy|policies|reason|reasons)\b', question, re.I):
        return None
    return product_ranking_scope(question, catalog, context)
