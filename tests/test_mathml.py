import pytest

from idml_foundation.mathml import (
    MATHML_NS,
    canonical_mathml,
    parse_mathml_fragment,
)

VALID = (
    f'<mml:math xmlns:mml="{MATHML_NS}"><mml:mrow><mml:mi>x</mml:mi>'
    "<mml:mo>=</mml:mo><mml:mn>1</mml:mn></mml:mrow></mml:math>"
)


def test_mathml_fragment_is_canonicalized_with_required_display() -> None:
    assert 'display="block"' in canonical_mathml(VALID, display=True)
    assert parse_mathml_fragment(VALID, display=False).get("display") == "inline"


@pytest.mark.parametrize(
    "fragment,error",
    [
        ("<math><mi>x</mi></math>", "mml:math"),
        (
            f'<mml:math xmlns:mml="{MATHML_NS}" display="inline"><mml:mi>x</mml:mi></mml:math>',
            "display must be block",
        ),
        (
            f'<mml:math xmlns:mml="{MATHML_NS}"><script>alert(1)</script></mml:math>',
            "unsupported element",
        ),
        (
            f'<mml:math xmlns:mml="{MATHML_NS}"><mml:mi href="https://example.test">x</mml:mi></mml:math>',
            "unsafe attribute",
        ),
        (
            '<!DOCTYPE math [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            f'<mml:math xmlns:mml="{MATHML_NS}"><mml:mi>&xxe;</mml:mi></mml:math>',
            "must not contain DTD",
        ),
    ],
)
def test_mathml_fragment_rejects_unsafe_or_incompatible_content(
    fragment: str,
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        parse_mathml_fragment(fragment, display=True)
