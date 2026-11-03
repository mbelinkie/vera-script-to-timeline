"""Editable target for the bounded DeepSeek live pilot."""


def safe_relative_path(value: object) -> str:
    """Return an accepted relative POSIX path unchanged."""
    if not isinstance(value, str):
        raise ValueError("path must be a string")
    if not value.strip():
        raise ValueError("path must not be blank")
    if value.startswith("/") or value.startswith("~"):
        raise ValueError("path must be relative")
    for char in value:
        code = ord(char)
        if char == "\\" or char == ":" or code < 32 or code == 127:
            raise ValueError("path contains a forbidden character")
    segments = value.split("/")
    for index, segment in enumerate(segments):
        if segment == "":
            raise ValueError("path contains an empty segment")
        if segment == "." or segment == "..":
            raise ValueError("path contains a dot segment")
        if segment == ".git":
            raise ValueError("path contains a .git segment")
        if index == 0 and segment == ".github":
            raise ValueError("path starts with .github")
    return value
