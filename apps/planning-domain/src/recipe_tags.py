def normalize_recipe_tag(tag: str) -> str:
    return "".join(char for char in tag.lower() if char.isalnum() or char == "-")


def automatic_recipe_tags(protein_subtype: str | None, cuisine: str | None) -> list[str]:
    tags = (normalize_recipe_tag(value)[:16] for value in (protein_subtype, cuisine) if value)
    return list(dict.fromkeys(tag for tag in tags if tag))
