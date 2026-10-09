import pytest
from assistant.rag import cited_sources
from assistant.gemini import detach_sql_citations, numeric_claims_supported

SOURCES = [{'citation':'D1','text':'Positive-quantity valued shipped lines.'},
           {'citation':'D2','text':'No payment ledger or independently verified net revenue.'},
           {'citation':'D3','text':'Missing costs and refund reconciliation.'}]


def test_live_document_answer_displays_every_cited_passage():
    text = ('Shipped sales are a sales proxy [D1]. The dataset lacks payment '
            'and cost reconciliation [D1, D3]. Net revenue is not verified [D2].')
    used = cited_sources(text, SOURCES)
    assert [source['citation'] for source in used] == ['D1','D2','D3']


@pytest.mark.parametrize('citation', ['[D1,D99]', '[D1, D99]', '[D99]'])
def test_unknown_grouped_ids_reject_the_answer(citation):
    assert cited_sources('Definition [D1]. Further explanation ' + citation, SOURCES) is None


def test_grouped_citations_do_not_count_as_numeric_claims():
    assert numeric_claims_supported('A sales proxy [D99, D101].', [], SOURCES)
    assert not numeric_claims_supported('There are 999 orders [D1, D3].', [], SOURCES)


def test_sql_figures_are_not_attributed_to_grouped_document_citations():
    text = 'Shipped value is INR 200 [D1, D3]. Sales are a proxy [D2].'
    assert detach_sql_citations(text) == 'Shipped value is INR 200. Sales are a proxy [D2].'
