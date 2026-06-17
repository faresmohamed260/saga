from __future__ import annotations

from sqlalchemy import func, select

from saga.services.entity_visual_prompt_service import EntityVisualPromptService
from saga.storage.models import Book, CharacterVisualBaseline, Entity, LocationVisualBaseline, ObjectVisualBaseline, VisualPrompt
from saga.storage.persistence import SagaSQLiteStore


def test_entity_visual_prompt_service_builds_prompts_for_all_supported_entities(tmp_path):
    db_path = tmp_path / "visuals.sqlite3"
    store = SagaSQLiteStore(db_path)
    with store.session_factory() as session:
        book = Book(series_id="hp1", book_index=1, title="HP1")
        session.add(book)
        session.flush()

        harry = Entity(
            book_id=book.id,
            canonical_name="Harry Potter",
            entity_type="character",
            entity_context="Young wizard with a lightning scar.",
            initial_physical_description={"description": "thin boy with messy black hair and round glasses"},
        )
        hogwarts = Entity(
            book_id=book.id,
            canonical_name="Hogwarts",
            entity_type="location",
            entity_context="vast stone castle",
        )
        hat = Entity(
            book_id=book.id,
            canonical_name="Sorting Hat",
            entity_type="object",
            entity_context="old pointed hat with a mouthlike tear",
        )
        ministry = Entity(
            book_id=book.id,
            canonical_name="Ministry of Magic",
            entity_type="organization",
            entity_context="the governing magical authority",
        )
        session.add_all([harry, hogwarts, hat, ministry])
        session.flush()

        session.add(
            CharacterVisualBaseline(
                book_id=book.id,
                entity_id=harry.id,
                gender_presentation="male",
                species_or_race="human wizard",
                apparent_age_group="school-age boy",
                build="thin",
                hair_color="black",
                hair_length_or_style="messy",
                eye_color="green",
                distinguishing_marks="lightning-shaped scar on forehead, round glasses",
                default_clothing_style="school uniform with black robe",
                evidence_excerpt="thin boy with messy black hair and round glasses",
            )
        )
        session.add(
            LocationVisualBaseline(
                book_id=book.id,
                entity_id=hogwarts.id,
                location_class="castle",
                indoor_outdoor="mixed indoor and outdoor",
                architecture_or_terrain_style="medieval stone castle",
                dominant_materials="stone",
                notable_features="high towers, torchlit halls",
                ambient_mood="majestic",
                evidence_excerpt="vast stone castle with high towers and torchlit halls",
            )
        )
        session.add(
            ObjectVisualBaseline(
                book_id=book.id,
                entity_id=hat.id,
                object_class="hat",
                function="sorting students",
                shape_form="old pointed hat",
                color_finish="weathered brown",
                surface_texture="creased cloth",
                symbolic_markings="mouthlike tear",
                evidence_excerpt="old pointed hat with a mouthlike tear",
            )
        )
        session.commit()

    service = EntityVisualPromptService(store)
    result = service.build_book_prompts(f"db://book/{book.id}")
    assert result.prompts_total == 4

    with store.session_factory() as session:
        total = session.execute(select(func.count()).select_from(VisualPrompt)).scalar_one()
        assert total == 4
        prompts = session.execute(select(VisualPrompt).order_by(VisualPrompt.entity_name.asc())).scalars().all()
        by_name = {row.entity_name: row for row in prompts}
        assert "three-view layout" in str(by_name["Harry Potter"].positive_prompt).lower()
        assert "photorealistic environment photograph" in str(by_name["Hogwarts"].positive_prompt).lower()
        assert "story-significant object or artifact" in str(by_name["Sorting Hat"].positive_prompt).lower()
        assert "story-significant entity" in str(by_name["Ministry of Magic"].positive_prompt).lower()
