from random import randint

from conftest import CustomConfig


def test_list_index_names_type(custom_config: CustomConfig) -> None:
    custom_config.hci_h.request_token()
    list_of_indexes = custom_config.hci_h.list_index_names()
    assert type(list_of_indexes) is list


def test_look_up_all_indexes(custom_config: CustomConfig) -> None:
    custom_config.hci_h.request_token()
    list_of_indexes = custom_config.hci_h.list_index_names()
    for index in list_of_indexes:
        assert custom_config.hci_h.look_up_index(index)


def test_fail_index_look_up(custom_config: CustomConfig) -> None:
    custom_config.hci_h.request_token()
    assert not custom_config.hci_h.look_up_index("anIndexThatDoesNotExist")


def test_make_simple_raw_query(custom_config: CustomConfig) -> None:
    custom_config.hci_h.request_token()
    list_of_indexes = custom_config.hci_h.list_index_names()
    arbitrary_index = list_of_indexes[randint(0, len(list_of_indexes) - 1)]
    result = custom_config.hci_h.raw_query(
        {
            "indexName": arbitrary_index,
        },
    )
    assert result["indexName"] == arbitrary_index


def test_fail_raw_query(custom_config: CustomConfig) -> None:
    custom_config.hci_h.request_token()
    query = {}
    try:
        custom_config.hci_h.raw_query(query)
    except:
        assert True
    else:  # pragma: no cover
        assert False


def test_make_query(custom_config: CustomConfig) -> None:
    custom_config.hci_h.request_token()
    custom_config.hci_h.query(
        custom_config.test_index,
    )


def test_make_query_with_query_string(custom_config: CustomConfig) -> None:
    custom_config.hci_h.request_token()
    custom_config.hci_h.query(
        custom_config.test_index,
        custom_config.query_string,
    )


def test_make_query_with_query_string_and_facet(
    custom_config: CustomConfig,
) -> None:
    custom_config.hci_h.request_token()
    if custom_config.test_facet:
        custom_config.hci_h.query(
            custom_config.test_index,
            custom_config.query_string,
            [custom_config.test_facet],
        )
    else:
        custom_config.hci_h.query(
            custom_config.test_index,
            custom_config.query_string,
            [],
        )


def test_make_query_with_facet(custom_config: CustomConfig) -> None:
    custom_config.hci_h.request_token()
    if custom_config.test_facet:
        custom_config.hci_h.query(
            custom_config.test_index,
            facets=[custom_config.test_facet],
        )
    else:
        custom_config.hci_h.query(
            custom_config.test_index,
            facets=[],
        )
