def expand_range(number_range_str: str) -> tuple[int, ...]:
    """Expand ranges like 2-5,8,22-45.

    Args:
        number_range_str (str): The range to expand.

    Raises:
        ValueError: The range of integers are invalid.
            Should be of the form 2-5,8,22-45.
        ValueError: The length of unique integers is not the same as the
            length of all integers.

    Returns:
        tuple[int, ...]: Tuple of integers.

    """
    numbers: list[int] = []
    for number_range in number_range_str.split(sep=","):
        start_stop: list[str] = number_range.split(sep="-")
        if len(start_stop) == 2:
            start = int(start_stop[0])
            stop = int(start_stop[1])
            numbers.extend(n for n in range(start, stop + 1))
        if len(start_stop) == 1:
            numbers.append(int(start_stop[0]))
        else:
            message: str = f"Invalid range: {number_range}"
            raise ValueError(message)
    if len(set(numbers)) != len(numbers):
        message: str = "len(set(numbers)) must be equal to len(numbers)."
        raise ValueError(message)
    return tuple(numbers)


def convert_to_set_commands(config_raw: str) -> str:
    """Convert a Juniper style config string into a list of set commands.

    Args:
        config_raw (str): The config string to convert to set commands
    Returns:
        config_raw (str): Configuration string

    """
    lines: list[str] = config_raw.split(sep="\n")

    # List of paths to the current command
    path: list[str] = []

    # The list of actual configuration commands
    set_commands: list[str] = []

    for line in lines:
        stripped_line: str = line.strip()

        # Skip empty lines
        if not stripped_line:
            continue

        # Strip ; from the end of the line
        if stripped_line.endswith(";"):
            stripped_line: str = stripped_line.replace(";", "")

        # Count the number of spaces at the beginning to determine the level
        level: int = line.find(stripped_line) // 4

        # Adjust the current path based on the level
        path = path[:level]

        # If the line ends with '{' or '}', it starts a new block
        if stripped_line.endswith(("{", "}")):
            path.append(stripped_line[:-1].strip())
        elif stripped_line.startswith(("set", "delete")):
            # It's already a set command, so just add it to the list
            set_commands.append(stripped_line)
        else:
            # It's a command line, construct the full command
            command: str = f"set {' '.join(path)} {stripped_line}"
            set_commands.append(command)

    return "\n".join(set_commands)
