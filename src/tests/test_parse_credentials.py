from NGPIris.parse_credentials import CredentialsHandler


def incomplete_creds(path: str) -> None:
    try:
        CredentialsHandler(path)
    except:
        assert True
    else:  # pragma: no cover
        assert False


def test_incomplete_creds_0() -> None:
    incomplete_creds("tests/data/incomplete_creds_0.json")


def test_incomplete_creds_1() -> None:
    incomplete_creds("tests/data/incomplete_creds_1.json")


def test_incomplete_creds_2() -> None:
    incomplete_creds("tests/data/incomplete_creds_2.json")


def test_incomplete_creds_3() -> None:
    incomplete_creds("tests/data/incomplete_creds_3.json")


def complete_creds(path: str) -> None:
    try:
        CredentialsHandler(path)
    except:  # pragma: no cover
        assert False
    else:
        assert True


def test_complete_creds_0() -> None:
    complete_creds("tests/data/complete_creds_0.json")


def test_complete_creds_1() -> None:
    complete_creds("tests/data/complete_creds_1.json")


def test_complete_creds_2() -> None:
    complete_creds("tests/data/complete_creds_2.json")
