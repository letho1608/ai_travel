from app.schemas import UserPreferencesRequest
from app.services.pdf_export import PDF_COPY


def test_pdf_copy_covers_every_supported_locale_without_vietnamese_fallback():
    locales = UserPreferencesRequest.model_fields["ngon_ngu"].annotation.__args__
    assert set(PDF_COPY) == set(locales)
    assert all(len(copy) == 13 for copy in PDF_COPY.values())
    assert all(all(value.strip() for value in copy) for copy in PDF_COPY.values())
    for locale in locales:
        if locale != "vi":
            assert PDF_COPY[locale] is not PDF_COPY["vi"]
            assert PDF_COPY[locale][1] != PDF_COPY["vi"][1]
