from saga.services.web_entity_hint_service import WebEntityHintService


def test_web_entity_hint_service_prefers_biography_signals_over_article_noise():
    service = WebEntityHintService()
    categories = [
        "1980 births",
        "1994 Quidditch World Cup attendees",
        "Articles with information from Harry Potter: Hogwarts Mystery",
    ]
    entity_type = service._infer_entity_type(categories, "Harry Potter", "Harry Potter", "")
    assert entity_type == "character"
