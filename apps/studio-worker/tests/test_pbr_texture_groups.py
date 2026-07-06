from pathlib import Path

from studio_worker.pbr_texture_groups import merge_split_slot_groups


def test_merge_split_slot_main_and_orm() -> None:
    root = Path("/tmp/wall")
    groups = {
        "wall_04_variant_main": {
            "albedo": root / "wall_04_variant_main_albedo.png",
        },
        "wall_04_variant_orm": {
            "orm": root / "wall_04_variant_orm_orm.png",
        },
    }
    merged = merge_split_slot_groups(groups)
    assert merged["wall_04_variant_main"]["albedo"].name.endswith("_albedo.png")
    assert merged["wall_04_variant_main"]["orm"].name.endswith("_orm.png")


def test_merge_freight_deck_slot_names() -> None:
    root = Path("/tmp/deck")
    groups = {
        "0_main": {"albedo": root / "0_main_albedo.png"},
        "0_orm_slot_1": {"orm": root / "0_orm_slot_1_orm.png"},
    }
    merged = merge_split_slot_groups(groups)
    assert "orm" in merged["0_main"]
